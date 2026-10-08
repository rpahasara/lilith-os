#!/usr/bin/env python3
"""15B2b-B1b-3e Package B (M-B9b): OWNER-SIDE offline verification of the committed witness genesis.

Record: docs/architecture/slice-15b2b-b1b3e-mb9-witness-genesis-package.md §9 (owner decision OD-B11).

Owner workstation (laptop WSL), read-only. It writes nothing, contacts nothing, and never touches an owner
freshness replica or record. Inputs are owner-held or exported bytes only:

    verify <pin-dir> <witness-anchor.json> <chain-1.json> <witness.json>

- `<pin-dir>`: the owner record P-A (`/root/lilith-genesis-pin-dev-synthetic`): `genesis-pin.json`,
  `authorization-register.json`, `pin-record.json`, exactly;
- `<witness-anchor.json>`: the owner's accepted installable witness anchor (`be360da2…`);
- `<chain-1.json>`, `<witness.json>`: the bytes exported from DEV after M-B9b (`chain-export`; evidence only).

It is a thin wrapper over the pinned Package A owner restatement (`mb7_genesis_candidate.py`: the expected
unsigned genesis from the accepted identities alone, the RFC 8785 restatement and the V2 digest) plus one
Ed25519 verification (`cryptography`). It establishes, each separately:

- the P-A record files are exactly the bytes the accepted candidate implies (pin, register, pin record);
- the anchor is the accepted installable, names the accepted K-WIT key ID and its public key hashes to the
  accepted K-WIT fingerprint;
- `chain/1.json` is one canonical `RecoveryWitnessV2` document whose unsigned body equals the expected genesis
  field by field (protocol, schema, environment, witnessVersion 1, previousWitnessDigest null, the recovery
  epoch, registry version / digest, policyVersion, ledger sequence / head, consumedAuthorizationId null,
  updatedAt, witnessKeyId);
- its K-WIT signature verifies under the anchor key over the V2 signing bytes;
- its digest equals the accepted candidate digest, the owner pin and the pin record;
- `witness.json` is byte-identical to `chain/1.json` (pointer = genesis).

`inspect-chain` (owner_freshness_tool) is not used: it needs a different trust-input format and does not check
the pin, `policyVersion`, `updatedAt` or the two null fields. It stays unchanged.

    offline verification != record 1;  verified genesis != FRESHNESS=CURRENT;  evidence storage != replica write
"""

from __future__ import annotations

import base64
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import mb7_genesis_candidate as C  # noqa: E402  (pinned Package A owner tool; stdlib at import)

RESULT_TYPE = "LILITH_MB9_OWNER_GENESIS_VERIFICATION"
# The owner-accepted Package A values (Package A completion record): the one lineage this package commits.
ACCEPTED_CANDIDATE_DIGEST = "ac892dc2b14ca7db108400258abfcf2320ff498f2a674058058e16a8a6fb65e4"
ACCEPTED_UPDATED_AT = "2026-10-08T07:21:43Z"
MAX_INPUT = 64 * 1024


class VerifyError(Exception):
    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


def _need(condition: bool, reason: str) -> None:
    if not condition:
        raise VerifyError(reason)


def _sha(data: bytes) -> str:
    return hashlib.sha256(bytes(data)).hexdigest()


def _read(path: Path) -> bytes:
    path = Path(path)
    _need(path.is_file() and not path.is_symlink(), "INPUT_ABSENT:" + path.name)
    data = path.read_bytes()
    _need(len(data) <= MAX_INPUT, "INPUT_TOO_LARGE:" + path.name)
    return data


def _b64u(value: Any, size: int, reason: str) -> bytes:
    _need(isinstance(value, str) and value and "=" not in value, reason)
    try:
        raw = base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))
    except ValueError as exc:
        raise VerifyError(reason) from exc
    _need(len(raw) == size and base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii") == value, reason)
    return raw


def _ed25519_verify(public_key: bytes, signature: bytes, message: bytes) -> bool:
    try:
        from cryptography.exceptions import InvalidSignature
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
    except ImportError as exc:                     # fail closed: no signature check, no verification
        raise VerifyError("CRYPTOGRAPHY_UNAVAILABLE") from exc
    try:
        Ed25519PublicKey.from_public_bytes(public_key).verify(signature, message)
    except (InvalidSignature, ValueError):
        return False
    return True


def verify(pin_dir: Path, anchor_path: Path, chain_path: Path, pointer_path: Path, *,
           expected_digest: str = ACCEPTED_CANDIDATE_DIGEST, updated_at: str = ACCEPTED_UPDATED_AT,
           pins: C.CandidatePinsV1 = C.ACCEPTED_PINS) -> dict[str, Any]:
    """`expected_digest`, `updated_at` and `pins` are TEST seams; the defaults are the owner-accepted values."""
    checks: dict[str, bool] = {}
    # 1. the expected genesis from the accepted identities alone, and the P-A owner record it implies
    expected = C.expected_unsigned(updated_at, pins)
    digest = C.independent_digest(expected)
    checks["expectedDigestEqualsAcceptedCandidate"] = digest == expected_digest
    pin_dir = Path(pin_dir)
    _need(pin_dir.is_dir() and not pin_dir.is_symlink(), "PIN_DIRECTORY_ABSENT")
    _need(sorted(p.name for p in pin_dir.iterdir()) == sorted(C.OWNER_RECORD_FILES), "PIN_DIRECTORY_INEXACT")
    pin, register, record = (_read(pin_dir / name) for name in (C.PIN_FILE, C.REGISTER_FILE, C.RECORD_FILE))
    checks["ownerPinBytesExact"] = pin == C.document_bytes(C.pin_document(expected_digest))
    checks["ownerRegisterBytesExact"] = register == C.document_bytes(C.register_document(pins))
    checks["ownerPinRecordBytesExact"] = record == C.document_bytes(
        C.pin_record_document(expected_digest, updated_at, pin, register, pins))
    # 2. the anchor: the accepted installable, the accepted K-WIT identity
    anchor_bytes = _read(Path(anchor_path))
    checks["anchorIsAcceptedInstallable"] = _sha(anchor_bytes) == pins.witness_anchor_sha256
    try:
        anchor = json.loads(anchor_bytes.decode("ascii"))
    except (UnicodeDecodeError, ValueError) as exc:
        raise VerifyError("ANCHOR_INVALID") from exc
    _need(isinstance(anchor, dict), "ANCHOR_INVALID")
    public_key = _b64u(anchor.get("publicKey"), 32, "ANCHOR_PUBLIC_KEY_INVALID")
    checks["anchorNamesKWitKeyId"] = anchor.get("witnessKeyId") == pins.kwit_key_id
    checks["anchorEnvironmentDev"] = anchor.get("environment") == C.ENVIRONMENT and anchor.get("algorithm") == "Ed25519"
    checks["kwitFingerprintExact"] = _sha(public_key) == pins.kwit_public_key_sha256
    # 3. the committed genesis: one canonical document; every field; the signature; the digest
    genesis_bytes = _read(Path(chain_path))
    try:
        document = json.loads(genesis_bytes.decode("ascii"))
    except (UnicodeDecodeError, ValueError) as exc:
        raise VerifyError("GENESIS_DOCUMENT_INVALID") from exc
    _need(isinstance(document, dict), "GENESIS_DOCUMENT_INVALID")
    try:
        canonical = C.independent_jcs(document) == genesis_bytes
    except C.CandidateError:
        canonical = False
    checks["genesisCanonicalBytes"] = canonical
    unsigned = {key: value for key, value in document.items() if key != "signature"}
    checks["genesisFieldsEqualExpected"] = unsigned == expected and set(document) == set(expected) | {"signature"}
    fields = {name: unsigned.get(name) == expected[name] for name in sorted(expected)}
    signature = _b64u(document.get("signature"), 64, "GENESIS_SIGNATURE_INVALID")
    checks["kwitSignatureVerifies"] = (checks["genesisFieldsEqualExpected"]
                                       and _ed25519_verify(public_key, signature,
                                                           C.WITNESS_V2_SEPARATOR + C.independent_jcs(unsigned)))
    committed = C.independent_digest(unsigned) if checks["genesisFieldsEqualExpected"] else None
    checks["committedDigestEqualsAcceptedCandidate"] = committed == expected_digest
    checks["committedDigestEqualsOwnerPin"] = (committed is not None
                                               and json.loads(pin).get("genesisWitnessDigest") == committed)
    checks["committedDigestEqualsPinRecord"] = (committed is not None
                                                and json.loads(record).get("candidateDigest") == committed)
    # 4. the pointer
    checks["pointerEqualsGenesis"] = _read(Path(pointer_path)) == genesis_bytes
    verified = all(checks.values())
    return {"resultType": RESULT_TYPE, "schemaVersion": 1, "checks": checks, "fields": fields,
            "committedDigest": committed, "expectedDigest": expected_digest, "updatedAt": updated_at,
            "genesisSha256": _sha(genesis_bytes),
            "result": "MB9B_OWNER_GENESIS_VERIFIED" if verified else "MB9B_OWNER_GENESIS_NOT_VERIFIED",
            "record1": "NOT CREATED", "freshness": "UNKNOWN", "accepted": False, "authorityGranted": False}


def main(argv: list[str]) -> int:
    try:
        if len(argv) == 5 and argv[0] == "verify":
            result = verify(*(Path(arg) for arg in argv[1:]))
        else:
            raise VerifyError("USAGE")
    except VerifyError as exc:
        print(f"mb9_owner_genesis_verify: REFUSED {exc.reason}", file=sys.stderr)
        return 2
    sys.stdout.write(json.dumps(result, sort_keys=True, indent=2) + "\n")
    return 0 if result["result"] == "MB9B_OWNER_GENESIS_VERIFIED" else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
