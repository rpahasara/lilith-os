#!/usr/bin/env python3
"""15B2b-B1b-3e M-B6: OFF-HOST owner computation of the expected ledger position (owner workstation).

Record: docs/architecture/slice-15b2b-b1b3e-mb6-ledger-remediation.md §5.

M-B6 must produce `ledgerHeadEqualsOwnerComputed`. The expected value is
computed here, by the owner, from the owner's own accepted Registry V1 copy
and the accepted registry-root anchor, never from DEV:

    expected sequence = 1
    GENESIS op        = authority_ledger_journal.genesis_op(registry v1)   (merged main, unchanged)
    expected head     = authority_ledger_journal.next_head(0^32, op)
                      = sha256("LILITH_AUTHORITY_LEDGER_HEAD_V1\\0" ‖ 0^32 ‖ JCS(op))

| Form | Output |
| --- | --- |
| `derive <authority-registry.v1.json> <registry-root.json>` | `OWNER_COMPUTED_FROM_REGISTRY_V1`: both files must hash to the accepted installable pins, parse as exact JCS, and the registry must verify under the root anchor at its own epoch (K-ROOT signature, single current K-ACT key); then the op, its JCS bytes and SHA-256, and the head |
| `pins` | `PIN_DERIVED_CROSS_CHECK`: the same op and head from the accepted public identities alone (no file); a cross-check, never the owner's value |

Every head is computed twice, by the merged-main journal and by an
independent restatement of the head function; they must be equal, and the
`derive` head must equal the pin-derived head. The ledger architecture
defines no separate GENESIS-op digest: `genesisOpJcsSha256` is reported for
reproducibility only and identifies nothing.

The result is a PROPOSED value for a later owner decision: this tool pins
nothing, accepts nothing and authorizes nothing. It reads two public files,
writes nothing, contacts nothing, and never touches K-ROOT, K-WIT or K-ACT
private material.

    owner-computed expected head != owner-accepted pin != host-observed head != authority
"""

from __future__ import annotations

import hashlib
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
for _path in (ROOT / "services/core-api", ROOT / "services/owner-memory-control"):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

RESULT_TYPE = "LILITH_MB6_OWNER_EXPECTED_LEDGER"
ENVIRONMENT = "dev"
HEAD_SEPARATOR = b"LILITH_AUTHORITY_LEDGER_HEAD_V1\x00"
MAX_INPUT = 64 * 1024


@dataclass(frozen=True)
class ExpectedPinsV1:
    registry_sha256: str
    root_anchor_sha256: str
    registry_digest: str
    kroot_public_key_sha256: str
    root_key_id: str
    kact_key_id: str
    kact_public_key_sha256: str
    epoch_random: str
    policy_version: str


# The owner-accepted installable representations and Registry V1 identities
# (M-B4/M-B5 continuity decision §3; completion record §1).
ACCEPTED_PINS = ExpectedPinsV1(
    registry_sha256="46b0bfc558ec3a19467206ada3dc53c18e8a6a4cd0782711b4800cfe099f8b1e",
    root_anchor_sha256="bc5f00a76b518c4f11b6804d35844c036db75eaa730d56c35f97f430558ff687",
    registry_digest="fa66272131a3ef076036616b07766a377de4fdc1e4fef4cb8a054726f05c14fc",
    kroot_public_key_sha256="cb36daf176d813359b8bd0fe6361f549fd3334a52d0cd1f85cc5247cb26592cf",
    root_key_id="test-only.registry-root.dev-synthetic.b1b3d.1",
    kact_key_id="test-only.dev-synthetic.actor.b1b3d.1",
    kact_public_key_sha256="dd13a1fb302375a4e7ec81131a72920e23e365e06a0b6dc9bb7ab124dadc01ed",
    epoch_random="11f184889f333dece054f3b91a301632",
    policy_version="policy.dev-synthetic.v1",
)


class OwnerToolError(Exception):
    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


def _need(condition: bool, reason: str) -> None:
    if not condition:
        raise OwnerToolError(reason)


def _sha(data: bytes) -> str:
    return hashlib.sha256(bytes(data)).hexdigest()


def independent_jcs(value: Any) -> bytes:
    """RFC 8785 restated for this value class only: objects, lists, printable-ASCII strings, ints < 2^53."""
    def check(item: Any) -> None:
        if isinstance(item, dict):
            for key, child in item.items():
                _need(isinstance(key, str) and key.isascii() and key.isprintable(), "OP_NOT_SIMPLE")
                check(child)
        elif isinstance(item, list):
            for child in item:
                check(child)
        elif isinstance(item, bool) or item is None:
            raise OwnerToolError("OP_NOT_SIMPLE")
        elif isinstance(item, int):
            _need(0 <= item < 2 ** 53, "OP_NOT_SIMPLE")
        else:
            _need(isinstance(item, str) and item.isascii() and item.isprintable() and '"' not in item
                  and "\\" not in item, "OP_NOT_SIMPLE")
    check(value)
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")


def independent_head(op: dict[str, Any]) -> str:
    return hashlib.sha256(HEAD_SEPARATOR + bytes(32) + independent_jcs(op)).hexdigest()


def pin_derived_op(pins: ExpectedPinsV1 = ACCEPTED_PINS) -> dict[str, Any]:
    return {"op": "GENESIS", "environment": ENVIRONMENT, "recoveryEpoch": {"counter": 1, "random": pins.epoch_random},
            "policyVersion": pins.policy_version, "registryVersion": 1, "signingKeyIds": [pins.kact_key_id]}


def _modules():
    from lilith_owner_memory import authority_contracts as A
    from lilith_owner_memory import authority_ledger_journal as J
    from lilith_owner_memory import authority_verifier as AV
    from lilith_owner_memory import rotation_contracts as RC
    from lilith_owner_memory.contracts import _canonical
    return A, J, AV, RC, _canonical


def _document(data: bytes, canonical) -> dict[str, Any]:
    def no_duplicates(pairs):
        value = {}
        for key, item in pairs:
            _need(key not in value, "INPUT_DUPLICATE_KEY")
            value[key] = item
        return value
    try:
        value = json.loads(data.decode("utf-8"), object_pairs_hook=no_duplicates)
    except (UnicodeDecodeError, ValueError) as exc:
        raise OwnerToolError("INPUT_NOT_JSON") from exc
    _need(isinstance(value, dict) and canonical(value) == data, "INPUT_NOT_CANONICAL")
    return value


def _read(path: Path) -> bytes:
    data = Path(path).read_bytes()
    _need(len(data) <= MAX_INPUT, "INPUT_TOO_LARGE")
    return data


def _position(op: dict[str, Any], J, canonical) -> dict[str, Any]:
    op_jcs = canonical(op)
    head = J.next_head("0" * 64, op)                  # R.LEDGER_HEAD_GENESIS, the pre-genesis head constant
    second = independent_head(op)
    _need(op_jcs == independent_jcs(op), "JCS_DISAGREES")
    _need(head == second, "HEAD_DISAGREES")
    return {"ledgerSequence": 1, "genesisOp": op, "genesisOpJcs": op_jcs.decode("ascii"),
            "genesisOpJcsSha256": _sha(op_jcs), "ledgerHead": head, "independentLedgerHead": second}


def from_pins(pins: ExpectedPinsV1 = ACCEPTED_PINS) -> dict[str, Any]:
    _A, J, _AV, _RC, canonical = _modules()
    op = pin_derived_op(pins)
    return {"resultType": RESULT_TYPE, "schemaVersion": 1, "derivation": "PIN_DERIVED_CROSS_CHECK",
            "environment": ENVIRONMENT, **_position(op, J, canonical), "ownerComputed": False, "accepted": False,
            "pinned": False, "authorityGranted": False}


def derive(registry_bytes: bytes, root_bytes: bytes, pins: ExpectedPinsV1 = ACCEPTED_PINS) -> dict[str, Any]:
    A, J, AV, RC, canonical = _modules()
    _need(_sha(registry_bytes) == pins.registry_sha256, "REGISTRY_NOT_THE_ACCEPTED_INSTALLABLE")
    _need(_sha(root_bytes) == pins.root_anchor_sha256, "ROOT_ANCHOR_NOT_THE_ACCEPTED_INSTALLABLE")
    registry, anchor = _document(registry_bytes, canonical), _document(root_bytes, canonical)
    try:
        root = A.TrustedRegistryRootV1.from_dict(anchor)
        epoch = A.RecoveryEpochV1.from_dict(registry["recoveryEpoch"])
        context = A.AuthorityVerificationContextV1(
            environment=ENVIRONMENT, purpose=A.NEW_ADMISSION, registry_root=root, trusted_minimum_registry_version=1,
            expected_recovery_epoch=epoch, policy_version=registry["policyVersion"])
        verified = AV.verify_authority_registry(context=context, registry=registry)
        digest = RC.registry_digest(registry)
        keys = registry.get("keys", [])
        kact = _sha(A._public_key(keys[0]["publicKey"])) if len(keys) == 1 else None
    except Exception as exc:  # noqa: BLE001 - any malformed accepted input fails closed
        raise OwnerToolError("REGISTRY_NOT_VERIFIED") from exc
    _need(verified.verified, "REGISTRY_NOT_VERIFIED")
    _need(digest == pins.registry_digest, "REGISTRY_DIGEST_MISMATCH")
    _need(_sha(root.public_key) == pins.kroot_public_key_sha256 and root.root_key_id == pins.root_key_id,
          "ROOT_ANCHOR_NOT_E21")
    _need((epoch.counter, epoch.random) == (1, pins.epoch_random) and registry["policyVersion"] == pins.policy_version
          and registry.get("registryVersion") == 1 and registry.get("environment") == ENVIRONMENT, "REGISTRY_NOT_E0")
    _need(kact == pins.kact_public_key_sha256 and keys[0].get("keyId") == pins.kact_key_id, "REGISTRY_KEY_NOT_KACT")
    try:
        op = J.genesis_op(registry)
        sequence, head = J.initial_position(registry)
    except J.LedgerRefusal as exc:
        raise OwnerToolError("GENESIS_OP_REFUSED:" + exc.reason) from exc
    position = _position(op, J, canonical)
    _need((sequence, head) == (1, position["ledgerHead"]), "INITIAL_POSITION_DISAGREES")
    cross = _position(pin_derived_op(pins), J, canonical)
    _need(op == cross["genesisOp"] and head == cross["ledgerHead"], "PIN_CROSS_CHECK_DISAGREES")
    return {"resultType": RESULT_TYPE, "schemaVersion": 1, "derivation": "OWNER_COMPUTED_FROM_REGISTRY_V1",
            "environment": ENVIRONMENT, "inputs": {"registrySha256": _sha(registry_bytes),
                                                   "rootAnchorSha256": _sha(root_bytes), "registryDigest": digest},
            "registryVerified": True, **position, "pinDerivedLedgerHead": cross["ledgerHead"], "ownerComputed": True,
            "accepted": False, "pinned": False, "authorityGranted": False}


def main(argv: list[str]) -> int:
    try:
        if argv == ["pins"]:
            result = from_pins()
        elif len(argv) == 3 and argv[0] == "derive":
            result = derive(_read(Path(argv[1])), _read(Path(argv[2])))
        else:
            raise OwnerToolError("USAGE")
    except (OwnerToolError, OSError) as exc:
        print(f"mb6_expected_ledger_head: REFUSED {getattr(exc, 'reason', type(exc).__name__)}", file=sys.stderr)
        return 2
    sys.stdout.write(json.dumps(result, sort_keys=True, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
