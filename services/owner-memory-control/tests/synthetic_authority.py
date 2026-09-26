"""TEST_ONLY synthetic authority registry and evidence builder for 15B2b-B1b-3a.

Every key here is an in-process Ed25519 key derived from a labelled TEST_ONLY
constant. The registry root is a separate synthetic signer: it is not the B1c
activation key, not an owner key, and not a WebAuthn credential. Nothing is
enrolled, persisted, packaged, or read from a machine, user, cloud, or CI
credential store. No real owner, memory, registry, or authority exists.

Run `python synthetic_authority.py --write-golden` only to regenerate the
golden file deliberately; tests compare against the committed file.
"""

from __future__ import annotations

import base64
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

ROOT = Path(__file__).resolve().parents[3]
for path in (ROOT / "services/core-api", ROOT / "services/owner-memory-control"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from lilith_owner_memory import authority_contracts as A  # noqa: E402
from lilith_owner_memory import authority_verifier as V  # noqa: E402

GOLDEN_PATH = Path(__file__).with_name("authority_b1b3a_golden.json")

ENV = "test"
POLICY = "policy.synthetic.v2"
REGISTRY_VERSION = 3
ROOT_KEY_ID = "test-only.registry-root-1"
DEV_ROOT_KEY_ID = "test-only.registry-root-dev-1"
LOGICAL_OWNER = "owner.synthetic.v1"
REGISTRY_ISSUED_AT = "2026-09-26T06:00:00Z"


def _label_hex(label: str) -> str:
    return hashlib.sha256(label.encode()).hexdigest()[:32]


EPOCH = A.RecoveryEpochV1(2, _label_hex("TEST_ONLY recovery epoch 2"))
OLD_EPOCH = A.RecoveryEpochV1(1, _label_hex("TEST_ONLY recovery epoch 1"))
FORK_EPOCH = A.RecoveryEpochV1(2, _label_hex("TEST_ONLY recovery epoch 2 divergent restore"))


def _seed(label: str) -> bytes:
    return hashlib.sha256(("TEST_ONLY " + label).encode()).digest()


# Deliberately fixed TEST_ONLY seeds. They are not packaged anywhere.
SEEDS = {
    "root": _seed("authority registry root 1"),
    "dev-root": _seed("authority registry root dev 1"),
    "attacker-root": _seed("attacker registry root"),
    "actor.current-2": _seed("actor evidence key current 2"),
    "actor.retired-1": _seed("actor evidence key retired 1"),
    "actor.revoked-1": _seed("actor evidence key routinely revoked 1"),
    "actor.compromised-1": _seed("actor evidence key compromised 1"),
    "actor.epoch1-1": _seed("actor evidence key epoch 1"),
    "privacy.current-1": _seed("privacy authorization key current 1"),
    "dev.actor.current-1": _seed("dev actor evidence key 1"),
    "attacker": _seed("attacker evidence key"),
}
# Stand-in for the 15B2a containment key: 32 bytes of HMAC PRF material. It is
# a detection key, never an authority-signing key.
TEST_ONLY_CONTAINMENT_KEY = _seed("legacy containment PRF key")


def b64(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def private(name: str) -> Ed25519PrivateKey:
    return Ed25519PrivateKey.from_private_bytes(SEEDS[name])


def public_b64(name_or_key) -> str:
    key = private(name_or_key) if isinstance(name_or_key, str) else name_or_key
    return b64(key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw))


def key_record(key_id: str, *, seed_name: str | None = None, **overrides: Any) -> dict[str, Any]:
    domain = A.PRIVACY if key_id.startswith("privacy.") else A.OWNER_ACTOR
    value = {
        "schemaVersion": 1,
        "keyId": key_id,
        "authorityDomain": domain,
        "evidenceTypes": sorted(A.EVIDENCE_TYPES_BY_DOMAIN[domain]),
        "environment": ENV,
        "algorithm": "Ed25519",
        "publicKey": public_b64(seed_name or key_id),
        "createdAt": "2026-09-10T00:00:00Z",
        "notBefore": "2026-09-10T00:00:00Z",
        "retiredAt": None,
        "revokedAt": None,
        "revocationReason": None,
        "compromisedSince": None,
        "recoveryEpoch": EPOCH.to_dict(),
        "policyVersion": POLICY,
        "registryVersion": 2,
    }
    value.update(overrides)
    return value


def default_keys() -> list[dict[str, Any]]:
    return [
        key_record("actor.compromised-1", revokedAt="2026-09-25T00:00:00Z", revocationReason="COMPROMISED",
                   compromisedSince="2026-09-24T00:00:00Z"),
        key_record("actor.current-2", createdAt="2026-09-26T00:00:00Z", notBefore="2026-09-26T00:00:00Z",
                   registryVersion=3),
        key_record("actor.epoch1-1", createdAt="2026-08-01T00:00:00Z", notBefore="2026-08-01T00:00:00Z",
                   retiredAt="2026-09-10T00:00:00Z", recoveryEpoch=OLD_EPOCH.to_dict(), registryVersion=1),
        key_record("actor.retired-1", retiredAt="2026-09-26T00:00:00Z"),
        key_record("actor.revoked-1", revokedAt="2026-09-20T00:00:00Z", revocationReason="ROUTINE"),
        key_record("privacy.current-1"),
    ]


def registry_unsigned(*, keys: list[dict[str, Any]] | None = None, **overrides: Any) -> dict[str, Any]:
    value = {
        "protocol": A.REGISTRY_PROTOCOL,
        "schemaVersion": A.REGISTRY_SCHEMA_VERSION,
        "environment": ENV,
        "registryVersion": REGISTRY_VERSION,
        "recoveryEpoch": EPOCH.to_dict(),
        "policyVersion": POLICY,
        "registryRootKeyId": ROOT_KEY_ID,
        "issuedAt": REGISTRY_ISSUED_AT,
        "keys": default_keys() if keys is None else keys,
    }
    value.update(overrides)
    return value


def sign_registry(unsigned: dict[str, Any], signer: str = "root") -> dict[str, Any]:
    return {**unsigned, "signature": b64(private(signer).sign(A.registry_signing_bytes(unsigned)))}


def registry(signer: str = "root", **overrides: Any) -> dict[str, Any]:
    return sign_registry(registry_unsigned(**overrides), signer)


def dev_registry() -> dict[str, Any]:
    keys = [key_record("actor.current-2", seed_name="dev.actor.current-1", environment="dev",
                       createdAt="2026-09-26T00:00:00Z", notBefore="2026-09-26T00:00:00Z", registryVersion=3)]
    return registry("dev-root", keys=keys, environment="dev", registryRootKeyId=DEV_ROOT_KEY_ID)


def trusted_root(name: str = "root", key_id: str = ROOT_KEY_ID, environment: str = ENV) -> A.TrustedRegistryRootV1:
    return A.TrustedRegistryRootV1.from_dict({
        "schemaVersion": 1, "rootKeyId": key_id, "environment": environment,
        "algorithm": "Ed25519", "publicKey": public_b64(name),
    })


def context(**overrides: Any) -> A.AuthorityVerificationContextV1:
    value = dict(environment=ENV, purpose=A.NEW_ADMISSION, registry_root=trusted_root(),
                 trusted_minimum_registry_version=REGISTRY_VERSION, expected_recovery_epoch=EPOCH,
                 policy_version=POLICY)
    value.update(overrides)
    return A.AuthorityVerificationContextV1(**value)


def dev_context(**overrides: Any) -> A.AuthorityVerificationContextV1:
    return context(environment="dev", registry_root=trusted_root("dev-root", DEV_ROOT_KEY_ID, "dev"), **overrides)


def historical_context(**overrides: Any) -> A.AuthorityVerificationContextV1:
    return context(purpose=A.HISTORICAL_VERIFICATION, **overrides)


def _digest(label: str) -> str:
    return hashlib.sha256(("TEST_ONLY " + label).encode()).hexdigest()


def owner_evidence_unsigned(**overrides: Any) -> dict[str, Any]:
    value = {
        "protocol": A.OWNER_EVIDENCE_PROTOCOL,
        "schemaVersion": A.OWNER_EVIDENCE_SCHEMA_VERSION,
        "evidenceId": "aev.synthetic-create",
        "evidenceNonce": "och.synthetic-create",
        "challengeId": "och.synthetic-create",
        "challengeDigest": _digest("owner challenge v2 create"),
        "credentialRecordId": "ocred.synthetic",
        "assertionDigest": _digest("owner assertion create"),
        "actionDigest": _digest("frozen action create"),
        "requestDigest": _digest("owner request create"),
        "payloadDigest": _digest("payload create"),
        "authorityDomain": A.OWNER_ACTOR,
        "evidenceType": A.OWNER_MEMORY_OPERATION,
        "environment": ENV,
        "logicalOwnerId": LOGICAL_OWNER,
        "keyId": "actor.current-2",
        "registryVersion": REGISTRY_VERSION,
        "recoveryEpoch": EPOCH.to_dict(),
        "policyVersion": POLICY,
        "issuedAt": "2026-09-26T12:00:21Z",
    }
    value.update(overrides)
    return value


def sign_owner(unsigned: dict[str, Any], signer: str | None = None) -> dict[str, Any]:
    key = private(signer or unsigned["keyId"])
    return {**unsigned, "signature": b64(key.sign(A.owner_evidence_signing_bytes(unsigned)))}


def owner_evidence(signer: str | None = None, **overrides: Any) -> dict[str, Any]:
    return sign_owner(owner_evidence_unsigned(**overrides), signer)


def owner_expectation(**overrides: Any) -> A.OwnerEvidenceExpectationV2:
    base = owner_evidence_unsigned()
    value = dict(
        evidence_id=base["evidenceId"], challenge_id=base["challengeId"],
        challenge_digest=base["challengeDigest"], credential_record_id=base["credentialRecordId"],
        assertion_digest=base["assertionDigest"], action_digest=base["actionDigest"],
        request_digest=base["requestDigest"], payload_digest=base["payloadDigest"],
        logical_owner_id=LOGICAL_OWNER,
    )
    value.update(overrides)
    return A.OwnerEvidenceExpectationV2(**value)


def privacy_unsigned(**overrides: Any) -> dict[str, Any]:
    value = {
        "protocol": A.PRIVACY_AUTHORIZATION_PROTOCOL,
        "schemaVersion": A.PRIVACY_AUTHORIZATION_SCHEMA_VERSION,
        "authorizationId": "pauth.synthetic-forget",
        "executionNonce": "pnonce.synthetic-forget",
        "forgetRequestId": "pforget.synthetic",
        "holdId": "phold.synthetic",
        "ownerEvidenceId": "aev.synthetic-forget",
        "memoryClass": "PROJECT_CODENAME_FACT",
        "subjectNamespace": "project.homelab",
        "subjectKey": "codename",
        "memoryItemId": "mitem.synthetic",
        "actionDigest": _digest("frozen action forget"),
        "resourceOwners": ["L04", "L18_V2", "PRIVACY"],
        "authorityDomain": A.PRIVACY,
        "evidenceType": A.PRIVACY_ERASURE_AUTHORIZATION,
        "environment": ENV,
        "logicalOwnerId": LOGICAL_OWNER,
        "keyId": "privacy.current-1",
        "registryVersion": REGISTRY_VERSION,
        "recoveryEpoch": EPOCH.to_dict(),
        "policyVersion": POLICY,
        "issuedAt": "2026-09-26T12:05:00Z",
    }
    value.update(overrides)
    return value


def sign_privacy(unsigned: dict[str, Any], signer: str | None = None) -> dict[str, Any]:
    key = private(signer or unsigned["keyId"])
    return {**unsigned, "signature": b64(key.sign(A.privacy_authorization_signing_bytes(unsigned)))}


def privacy_authorization(signer: str | None = None, **overrides: Any) -> dict[str, Any]:
    return sign_privacy(privacy_unsigned(**overrides), signer)


def privacy_expectation(**overrides: Any) -> A.PrivacyAuthorizationExpectationV2:
    base = privacy_unsigned()
    value = dict(
        authorization_id=base["authorizationId"], execution_nonce=base["executionNonce"],
        forget_request_id=base["forgetRequestId"], hold_id=base["holdId"],
        owner_evidence_id=base["ownerEvidenceId"], memory_class=base["memoryClass"],
        subject_namespace=base["subjectNamespace"], subject_key=base["subjectKey"],
        memory_item_id=base["memoryItemId"], action_digest=base["actionDigest"],
        resource_owners=tuple(base["resourceOwners"]), logical_owner_id=LOGICAL_OWNER,
    )
    value.update(overrides)
    return A.PrivacyAuthorizationExpectationV2(**value)


def verify_owner(evidence=None, *, ctx=None, reg=None, expectation=None):
    return V.verify_owner_evidence(
        context=ctx or context(), registry=registry() if reg is None else reg,
        evidence=owner_evidence() if evidence is None else evidence,
        expectation=expectation or owner_expectation())


def verify_privacy(authorization=None, *, ctx=None, reg=None, expectation=None):
    return V.verify_privacy_authorization(
        context=ctx or context(), registry=registry() if reg is None else reg,
        authorization=privacy_authorization() if authorization is None else authorization,
        expectation=expectation or privacy_expectation())


# ---------------------------------------------------------------- golden ---

def _outcome_vectors() -> list[dict[str, Any]]:
    """Named artifacts whose verification outcome is frozen."""
    retired_historical = owner_evidence(keyId="actor.retired-1", registryVersion=2,
                                        issuedAt="2026-09-20T12:00:00Z")
    retired_new = owner_evidence(keyId="actor.retired-1", issuedAt="2026-09-26T12:00:21Z")
    compromised_backdated = owner_evidence(keyId="actor.compromised-1", registryVersion=2,
                                           issuedAt="2026-09-20T12:00:00Z")
    old_epoch = owner_evidence(keyId="actor.epoch1-1", registryVersion=1, recoveryEpoch=OLD_EPOCH.to_dict(),
                               issuedAt="2026-09-05T12:00:00Z")
    actor_signed_privacy = privacy_authorization(signer="actor.current-2", keyId="actor.current-2")
    privacy_signed_actor = owner_evidence(signer="privacy.current-1", keyId="privacy.current-1")
    owner_as_privacy = {**owner_evidence(), "protocol": A.PRIVACY_AUTHORIZATION_PROTOCOL}
    cross_env = owner_evidence()  # valid TEST evidence replayed into a DEV context
    return [
        {"name": "retirement-historical-accepted", "kind": "owner", "context": "historical",
         "artifact": retired_historical, "status": V.VERIFIED_AUTHORITY_EVIDENCE, "reason": None,
         "keyStatus": "RETIRED_AFTER_ISSUANCE"},
        {"name": "retirement-new-admission-rejected", "kind": "owner", "context": "new",
         "artifact": retired_new, "status": V.NOT_ACCEPTED, "reason": "KEY_RETIRED"},
        {"name": "compromise-backdated-rejected", "kind": "owner", "context": "historical",
         "artifact": compromised_backdated, "status": V.NOT_ACCEPTED, "reason": "KEY_COMPROMISED"},
        {"name": "epoch-old-evidence-historical-only", "kind": "owner", "context": "historical",
         "artifact": old_epoch, "status": V.VERIFIED_AUTHORITY_EVIDENCE, "reason": None,
         "keyStatus": "RETIRED_AFTER_ISSUANCE"},
        {"name": "epoch-old-evidence-new-admission-rejected", "kind": "owner", "context": "new",
         "artifact": old_epoch, "status": V.NOT_ACCEPTED, "reason": "RECOVERY_EPOCH_MISMATCH"},
        {"name": "cross-domain-actor-key-signs-privacy", "kind": "privacy", "context": "new",
         "artifact": actor_signed_privacy, "status": V.NOT_ACCEPTED, "reason": "KEY_DOMAIN_MISMATCH"},
        {"name": "cross-domain-privacy-key-signs-actor", "kind": "owner", "context": "new",
         "artifact": privacy_signed_actor, "status": V.NOT_ACCEPTED, "reason": "KEY_DOMAIN_MISMATCH"},
        {"name": "cross-domain-owner-evidence-as-privacy", "kind": "privacy", "context": "new",
         "artifact": owner_as_privacy, "status": V.NOT_ACCEPTED, "reason": "EVIDENCE_MALFORMED"},
        {"name": "environment-test-evidence-in-dev", "kind": "owner", "context": "dev",
         "artifact": cross_env, "status": V.NOT_ACCEPTED, "reason": "ENVIRONMENT_MISMATCH"},
    ]


def evaluate_vector(vector: dict[str, Any]):
    ctx, reg = {
        "new": (context(), registry()),
        "historical": (historical_context(), registry()),
        "dev": (dev_context(), dev_registry()),
    }[vector["context"]]
    if vector["kind"] == "owner":
        return V.verify_owner_evidence(context=ctx, registry=reg, evidence=vector["artifact"],
                                       expectation=owner_expectation())
    return V.verify_privacy_authorization(context=ctx, registry=reg, authorization=vector["artifact"],
                                          expectation=privacy_expectation())


def golden_document() -> dict[str, Any]:
    reg = registry()
    owner = owner_evidence()
    priv = privacy_authorization()
    return {
        "note": "TEST_ONLY synthetic vectors for 15B2b-B1b-3a. No real key, owner, registry, or authority.",
        "domainSeparators": {
            "registry": A.REGISTRY_DOMAIN_SEPARATOR.decode("ascii"),
            "ownerEvidence": A.OWNER_EVIDENCE_DOMAIN_SEPARATOR.decode("ascii"),
            "privacyAuthorization": A.PRIVACY_AUTHORIZATION_DOMAIN_SEPARATOR.decode("ascii"),
        },
        "publicKeys": {name: public_b64(name) for name in ("root", "dev-root", "actor.current-2",
                                                          "privacy.current-1")},
        "registry": reg,
        "registrySigningDigest": hashlib.sha256(
            A.registry_signing_bytes({k: v for k, v in reg.items() if k != "signature"})).hexdigest(),
        "devRegistry": dev_registry(),
        "ownerEvidenceV2": owner,
        "ownerEvidenceSigningDigest": hashlib.sha256(
            A.owner_evidence_signing_bytes({k: v for k, v in owner.items() if k != "signature"})).hexdigest(),
        "privacyAuthorizationV2": priv,
        "privacyAuthorizationSigningDigest": hashlib.sha256(
            A.privacy_authorization_signing_bytes({k: v for k, v in priv.items() if k != "signature"})).hexdigest(),
        "outcomes": _outcome_vectors(),
    }


if __name__ == "__main__":
    if sys.argv[1:] != ["--write-golden"]:
        raise SystemExit("usage: synthetic_authority.py --write-golden")
    with GOLDEN_PATH.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(golden_document(), indent=2, sort_keys=True) + "\n")
