#!/usr/bin/env python3
"""LILITH 15B2b-B1b-3e PR-1S (S-11): owner-workstation tooling for the DEV_SYNTHETIC bootstrap.

Run by the owner on the OWNER WORKSTATION only, from a clean checkout of the
reviewed protected-main commit, with the pinned dependencies. Never on DEV,
never in GitHub Actions, never by the routine deployer. It contacts nothing.
It is control tooling, never release payload. Record:
docs/architecture/slice-15b2b-b1b3e-pr1s-runtime-wiring.md.

    python services/authority-dev/ceremony/lilith_authority_owner_dev.py <form> ...

| Form | Output |
| --- | --- |
| `root-keygen <key-out>` | K-ROOT: one Ed25519 key, PKCS#8 DER encrypted under a passphrase read from the terminal, written exclusively (`0600`) to `<key-out>`; prints the `TrustedRegistryRootV1` anchor |
| `registry-v1 <key> <kact-publication> <epochRandom> <policyVersion> <issuedAt>` | registry v1 at E0 = (1, epochRandom) with the K-ACT publication as the single current OWNER_ACTOR key, signed by K-ROOT |
| `witness-anchor <kwit-publication>` | the `TrustedWitnessAnchorV1` for the K-WIT publication |
| `reproduce <registry> <registry-root> <witness-anchor> <updatedAt>` | RR-38 B off-host reproduction: registry verification and digest, the ledger GENESIS op and its `(1, head)`, the exact genesis candidate digest, the pin, and the empty-authorization register |
| `package-digest <package>` | the canonical PR-1 package digest |

K-ROOT never leaves the workstation. Nothing here writes to DEV, and no
output is authority except the K-ROOT registry signature itself, which the
witness makes a head only through its own checks:

    owner record / provenance != K-ROOT authority
    pin                       != K-ROOT, != K-WIT
"""

from __future__ import annotations

import base64
import getpass
import hashlib
import json
import os
import re
import sys
from pathlib import Path
from typing import Any, Callable

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
for path in (ROOT / "services/core-api", ROOT / "services/owner-memory-control"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey  # noqa: E402
from cryptography.hazmat.primitives.serialization import (  # noqa: E402
    BestAvailableEncryption, Encoding, PrivateFormat, PublicFormat, load_der_private_key,
)
from lilith_owner_memory import authority_contracts as A  # noqa: E402
from lilith_owner_memory import authority_ledger_journal as J  # noqa: E402
from lilith_owner_memory import authority_verifier as AV  # noqa: E402
from lilith_owner_memory import pr1_acceptance as PA  # noqa: E402
from lilith_owner_memory import pr1_bootstrap as B  # noqa: E402
from lilith_owner_memory import recovery_contracts as R  # noqa: E402
from lilith_owner_memory import rotation_contracts as RC  # noqa: E402
from lilith_owner_memory import witness_readiness as WR  # noqa: E402
from lilith_owner_memory.contracts import _canonical  # noqa: E402

ENVIRONMENT = "dev"
ROOT_KEY_ID = "test-only.registry-root.dev-synthetic.b1b3d.1"  # B1b-3d §4
E0_COUNTER = 1
_HEX32 = re.compile(r"[0-9a-f]{32}\Z")
_INSTANT = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z\Z")


class OwnerToolError(Exception):
    pass


def _b64u(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _load(path: str) -> Any:
    return json.loads(Path(path).read_bytes())


def _jcs(value: Any) -> str:
    return _canonical(value).decode("utf-8")


def root_keygen(key_out: Path, *, passphrase: bytes,
                key_factory: Callable[[], Ed25519PrivateKey] = Ed25519PrivateKey.generate) -> dict[str, Any]:
    """K-ROOT on the workstation: encrypted PKCS#8 DER, exclusive create, 0600."""
    if len(passphrase) < 12:
        raise OwnerToolError("PASSPHRASE_TOO_SHORT")
    key = key_factory()
    data = key.private_bytes(Encoding.DER, PrivateFormat.PKCS8, BestAvailableEncryption(passphrase))
    public = key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
    del key
    fd = os.open(key_out, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0), 0o600)
    try:
        os.write(fd, data)
        os.fsync(fd)
    finally:
        os.close(fd)
    anchor = {"schemaVersion": 1, "rootKeyId": ROOT_KEY_ID, "environment": ENVIRONMENT, "algorithm": A.ALGORITHM,
              "publicKey": _b64u(public)}
    A.TrustedRegistryRootV1.from_dict(anchor)
    return {"registryRoot": anchor, "publicKeySha256": hashlib.sha256(public).hexdigest()}


def _root_key(path: Path, passphrase: bytes) -> Ed25519PrivateKey:
    key = load_der_private_key(Path(path).read_bytes(), password=passphrase)
    if not isinstance(key, Ed25519PrivateKey):
        raise OwnerToolError("ROOT_KEY_NOT_ED25519")
    return key


def registry_v1(key: Ed25519PrivateKey, publication: dict[str, Any], *, epoch_random: str, policy_version: str,
                issued_at: str) -> dict[str, Any]:
    """Registry v1 at E0 naming exactly the published K-ACT as current."""
    if not _HEX32.fullmatch(epoch_random) or not _INSTANT.fullmatch(issued_at):
        raise OwnerToolError("REGISTRY_ARGUMENT_INVALID")
    parsed = RC.KeyPublicationV1.from_dict(publication)
    if parsed.environment != ENVIRONMENT or parsed.signing_domain != A.OWNER_ACTOR:
        raise OwnerToolError("PUBLICATION_SCOPE")
    epoch = {"counter": E0_COUNTER, "random": epoch_random}
    record = {"schemaVersion": 1, "keyId": parsed.key_id, "signingDomain": A.OWNER_ACTOR,
              "evidenceTypes": sorted(parsed.evidence_types), "environment": ENVIRONMENT, "algorithm": A.ALGORITHM,
              "publicKey": _b64u(parsed.public_key), "createdAt": issued_at, "notBefore": issued_at,
              "retiredAt": None, "revokedAt": None, "revocationReason": None, "compromisedSince": None,
              "recoveryEpoch": epoch, "policyVersion": policy_version, "registryVersion": 1}
    unsigned = {"protocol": A.REGISTRY_PROTOCOL, "schemaVersion": A.REGISTRY_SCHEMA_VERSION,
                "environment": ENVIRONMENT, "registryVersion": 1, "recoveryEpoch": epoch,
                "policyVersion": policy_version, "registryRootKeyId": ROOT_KEY_ID, "issuedAt": issued_at,
                "keys": [record]}
    return {**unsigned, "signature": _b64u(key.sign(A.registry_signing_bytes(unsigned)))}


def witness_anchor(publication: dict[str, Any]) -> dict[str, Any]:
    return B.witness_anchor_document(B.WitnessKeyPublicationV1.from_dict(publication))


def reproduce(registry: dict[str, Any], registry_root: dict[str, Any], anchor: dict[str, Any],
              updated_at: str) -> dict[str, Any]:
    """RR-38 B: every owner-derivable digest from off-host material only."""
    root = A.TrustedRegistryRootV1.from_dict(registry_root)
    parsed_anchor = R.TrustedWitnessAnchorV1.from_dict(anchor)
    epoch = A.RecoveryEpochV1.from_dict(registry["recoveryEpoch"])
    context = A.AuthorityVerificationContextV1(
        environment=ENVIRONMENT, purpose=A.NEW_ADMISSION, registry_root=root, trusted_minimum_registry_version=1,
        expected_recovery_epoch=epoch, policy_version=registry["policyVersion"])
    verified = AV.verify_authority_registry(context=context, registry=registry)
    op = J.genesis_op(registry)
    sequence, head = J.initial_position(registry)
    ledger = RC.AuthorityLedgerObservationV1(environment=ENVIRONMENT, recovery_epoch=epoch, sequence=sequence,
                                             head=head, registry_view=registry["registryVersion"],
                                             signing_key_ids=tuple(op["signingKeyIds"]))
    built = B.build_genesis_candidate(registry=registry, registry_root=root, ledger_observation=ledger,
                                      updated_at=updated_at, profile=B.witness_profile(ENVIRONMENT))
    if not built.built:
        raise OwnerToolError("GENESIS_CANDIDATE_REFUSED:" + str(built.reason))
    head_registry = RC.registry_head(registry)
    return {
        "registryVerified": verified.verified, "registryReason": verified.reason,
        "registryHead": head_registry.to_dict(), "ledgerGenesisOp": op, "ledgerSequence": sequence,
        "ledgerHead": head, "genesisCandidateDigest": built.digest, "unsignedGenesis": dict(built.unsigned),
        "witnessKeyId": parsed_anchor.witness_key_id,
        "genesisPin": WR.OwnerGenesisPinV1(ENVIRONMENT, built.digest).to_dict(),
        "authorizationRegister": {"registerType": WR.REGISTER_TYPE, "schemaVersion": WR.REGISTER_SCHEMA_VERSION,
                                  "environment": ENVIRONMENT, "authorizations": [],
                                  "headRegistries": [head_registry.to_dict()]},
        "authorityGranted": False,
    }


def main(argv: list[str], *, passphrase: Callable[[], bytes] | None = None) -> int:
    ask = passphrase or (lambda: getpass.getpass("K-ROOT passphrase: ").encode("utf-8"))
    try:
        if argv[:1] == ["root-keygen"] and len(argv) == 2:
            first = ask()
            if passphrase is None and first != getpass.getpass("repeat: ").encode("utf-8"):
                raise OwnerToolError("PASSPHRASE_MISMATCH")
            result = root_keygen(Path(argv[1]), passphrase=first)
        elif argv[:1] == ["registry-v1"] and len(argv) == 6:
            result = registry_v1(_root_key(Path(argv[1]), ask()), _load(argv[2]), epoch_random=argv[3],
                                 policy_version=argv[4], issued_at=argv[5])
        elif argv[:1] == ["witness-anchor"] and len(argv) == 2:
            result = witness_anchor(_load(argv[1]))
        elif argv[:1] == ["reproduce"] and len(argv) == 5:
            result = reproduce(_load(argv[1]), _load(argv[2]), _load(argv[3]), argv[4])
        elif argv[:1] == ["package-digest"] and len(argv) == 2:
            result = {"packageDigest": PA.package_digest(_load(argv[1]))}
        else:
            raise OwnerToolError("USAGE")
    except (OwnerToolError, ValueError, KeyError, TypeError, OSError) as exc:
        print(f"lilith_authority_owner_dev: REFUSED {exc}", file=sys.stderr)
        return 2
    sys.stdout.write(_jcs(result) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
