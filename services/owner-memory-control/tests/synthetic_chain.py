"""TEST_ONLY synthetic accepted-memory chain builder for 15B2b-B2a.

Every credential, key, value and identifier here is synthetic. Owner (ES256)
and broker (Ed25519) keys are derived in-process from labelled TEST_ONLY
constants; nothing is enrolled, persisted, packaged or read from a machine,
user or CI credential store. No real owner, memory or authority exists.
"""

from __future__ import annotations

import base64
import dataclasses
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
from fido2 import cbor
from fido2.cose import ES256

ROOT = Path(__file__).resolve().parents[3]
for path in (ROOT / "services/core-api", ROOT / "services/owner-memory-control"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from lilith_memory import canonical_contracts as C  # noqa: E402
from lilith_memory import owner_proof as P  # noqa: E402
from lilith_owner_memory import contracts as K  # noqa: E402


OWNER_PRINCIPAL = "user:synthetic-owner@example.invalid"
RP = P.SYNTHETIC_RP_ID
ORIGIN = P.SYNTHETIC_ORIGIN
LOGICAL_OWNER = "owner.synthetic.v1"
AUTHORITY_DOMAIN = "authority.synthetic.memory"
ENVIRONMENT = "test"
POLICY_VERSION = "policy.synthetic.v1"
REGISTRY_VERSION = "registry.synthetic.v1"
LEDGER_EPOCH = "0123456789abcdef0123456789abcdef"
PRIVACY_NOTICE = "privacy.synthetic.v1"
BROKER_RELEASE = hashlib.sha1(b"TEST_ONLY broker release").hexdigest()
BROKER_KEY_ID = "bkey.synthetic-1"
# Deliberately fixed TEST_ONLY scalars/seeds. They are not packaged anywhere.
TEST_ONLY_OWNER_SCALAR = 0x5EC7E7B2A0C0FFEE5EC7E7B2A0C0FFEE
TEST_ONLY_ATTACKER_SCALAR = 0x0BADC0DE0BADC0DE0BADC0DE0BADC0DE
TEST_ONLY_BROKER_SEED = hashlib.sha256(b"TEST_ONLY broker evidence key 1").digest()
TEST_ONLY_BROKER_SEED_2 = hashlib.sha256(b"TEST_ONLY broker evidence key 2").digest()


def b64(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def owner_key(scalar: int = TEST_ONLY_OWNER_SCALAR):
    return ec.derive_private_key(scalar, ec.SECP256R1())


def broker_key(seed: bytes = TEST_ONLY_BROKER_SEED) -> Ed25519PrivateKey:
    return Ed25519PrivateKey.from_private_bytes(seed)


def action(operation: str = "CREATE", memory_class: str = "PROJECT_CODENAME_FACT") -> C.FrozenMemoryActionV1:
    return C.FrozenMemoryActionV1(
        schema_version=1,
        actor_ref_id="actor.synthetic",
        operation=operation,
        memory_class=memory_class,
        subject_namespace="project.homelab",
        subject_key="codename",
        value_schema="HomelabCodenameV1" if operation in {"CREATE", "SUPERSEDE"} else None,
        payload_digest=hashlib.sha256(
            b"TEST_ONLY old value" if operation == "RESTORE" else b"TEST_ONLY synthetic value binding"
        ).hexdigest(),
        expected_active_revision_id="mrev.synthetic-current" if operation in {"SUPERSEDE", "RESTORE"} else None,
        restore_revision_id="mrev.synthetic-history" if operation == "RESTORE" else None,
        purpose=C.LONG_TERM_PERSONAL_PROJECT_RECALL,
    )


def challenge_dict(a: C.FrozenMemoryActionV1, **overrides: Any) -> dict[str, Any]:
    value = {
        "protocol": P.PROTOCOL,
        "schemaVersion": K.CHALLENGE_V2_SCHEMA_VERSION,
        "ownerPrincipal": OWNER_PRINCIPAL,
        "challengeId": "och.synthetic-" + a.operation.lower(),
        "actionDigest": a.action_digest,
        "requestDigest": hashlib.sha256(("TEST_ONLY synthetic request:" + a.operation).encode()).hexdigest(),
        "payloadDigest": a.payload_digest,
        "operation": a.operation,
        "memoryClass": a.memory_class,
        "subjectNamespace": a.subject_namespace,
        "subjectKey": a.subject_key,
        "purpose": a.purpose,
        "memoryItemId": None if a.operation == "CREATE" else "mitem.synthetic",
        "expectedActiveRevisionId": a.expected_active_revision_id,
        "restoreTargetRevisionId": a.restore_revision_id,
        "restoreTargetDigest": a.payload_digest if a.operation == "RESTORE" else None,
        "privacyNoticeVersion": PRIVACY_NOTICE,
        "nonce": b64(bytes(range(32))),
        "issuedAt": "2026-09-26T12:00:00Z",
        "expiresAt": "2026-09-26T12:01:00Z",
        "rpId": RP,
        "deploymentEnvironment": ENVIRONMENT,
        "authorityDomain": AUTHORITY_DOMAIN,
        "logicalOwnerId": LOGICAL_OWNER,
        "policyVersion": POLICY_VERSION,
        "registryTupleVersion": REGISTRY_VERSION,
        "ledgerEpoch": LEDGER_EPOCH,
    }
    value.update(overrides)
    return value


def credential_dict(private=None, **overrides: Any) -> dict[str, Any]:
    private = private or owner_key()
    value = {
        "schemaVersion": 1,
        "recordId": "ocred.synthetic",
        "ownerPrincipal": OWNER_PRINCIPAL,
        "credentialId": b64(b"TEST_ONLY_CREDENTIAL_ID_00001"),
        "publicKeyCose": b64(cbor.encode(ES256.from_cryptography_key(private.public_key()))),
        "algorithm": -7,
        "rpId": RP,
        "status": "ACTIVE",
        "createdAt": "2026-09-26T11:00:00Z",
        "revokedAt": None,
        "lastObservedSignCount": 0,
    }
    value.update(overrides)
    return value


def assertion_dict(webauthn_challenge: bytes, private=None, *, origin=ORIGIN, rp=RP, flags=0x05,
                   client_type="webauthn.get", credential_record_id="ocred.synthetic",
                   credential_id=None) -> dict[str, Any]:
    private = private or owner_key()
    client_raw = json.dumps({
        "type": client_type, "challenge": b64(webauthn_challenge),
        "origin": origin, "crossOrigin": False,
    }, separators=(",", ":")).encode()
    auth_raw = hashlib.sha256(rp.encode()).digest() + bytes([flags]) + (0).to_bytes(4, "big")
    signature = private.sign(auth_raw + hashlib.sha256(client_raw).digest(), ec.ECDSA(hashes.SHA256()))
    return {
        "credentialRecordId": credential_record_id,
        "credentialId": credential_id or b64(b"TEST_ONLY_CREDENTIAL_ID_00001"),
        "clientDataJSON": b64(client_raw),
        "authenticatorData": b64(auth_raw),
        "signature": b64(signature),
    }


def broker_key_dict(private: Ed25519PrivateKey | None = None, **overrides: Any) -> dict[str, Any]:
    private = private or broker_key()
    value = {
        "schemaVersion": 1,
        "brokerKeyId": BROKER_KEY_ID,
        "algorithm": "Ed25519",
        "publicKey": b64(private.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)),
        "status": "ACTIVE",
        "createdAt": "2026-09-26T10:00:00Z",
        "revokedAt": None,
        "deploymentEnvironment": ENVIRONMENT,
        "authorityDomain": AUTHORITY_DOMAIN,
    }
    value.update(overrides)
    return value


def sign_evidence(unsigned: dict[str, Any], private: Ed25519PrivateKey | None = None) -> dict[str, Any]:
    private = private or broker_key()
    return {**unsigned, "signature": b64(private.sign(K.evidence_signing_bytes(unsigned)))}


def context(**overrides: Any) -> K.AcceptanceContextV1:
    value = dict(
        deployment_environment=ENVIRONMENT, authority_domain=AUTHORITY_DOMAIN,
        logical_owner_id=LOGICAL_OWNER, owner_principal=OWNER_PRINCIPAL, rp_id=RP, origin=ORIGIN,
        policy_version=POLICY_VERSION, registry_tuple_version=REGISTRY_VERSION,
        ledger_epoch=LEDGER_EPOCH, privacy_notice_version=PRIVACY_NOTICE,
        broker_releases=frozenset({BROKER_RELEASE}),
    )
    value.update(overrides)
    return K.AcceptanceContextV1(**value)


class Chain:
    """One complete, valid synthetic chain; tests break exactly one link."""

    def __init__(self, operation: str = "CREATE", *, memory_class: str = "PROJECT_CODENAME_FACT",
                 action_overrides: dict | None = None, challenge_overrides: dict | None = None,
                 assertion_options: dict | None = None, credential_overrides: dict | None = None,
                 record_overrides: dict | None = None, evidence_overrides: dict | None = None,
                 admission_overrides: dict | None = None, signing_owner=None, evidence_signer=None,
                 epistemic_basis: str = "USER_ASSERTED"):
        base = action(operation, memory_class)
        self.action = dataclasses.replace(base, **(action_overrides or {}))
        self.challenge = K.OwnerMemoryChallengeV2.from_dict(challenge_dict(base, **(challenge_overrides or {})))
        self.challenge_json = self.challenge.canonical_bytes()
        self.assertion = assertion_dict(self.challenge.webauthn_challenge(), signing_owner,
                                        **(assertion_options or {}))
        self.owner_credential = credential_dict(**(credential_overrides or {}))
        self.challenge_record = {
            "schemaVersion": 1, "challengeId": self.challenge["challengeId"], "state": "CONSUMED",
            "consumedCredentialRecordId": "ocred.synthetic", "consumedAt": "2026-09-26T12:00:20Z",
            "ledgerEpoch": self.challenge["ledgerEpoch"],
        }
        self.challenge_record.update(record_overrides or {})
        unsigned = {
            "protocol": K.EVIDENCE_PROTOCOL, "schemaVersion": K.EVIDENCE_SCHEMA_VERSION,
            "evidenceId": "bev.synthetic-" + operation.lower(),
            "evidenceNonce": self.challenge["challengeId"],
            "challengeId": self.challenge["challengeId"],
            "challengeDigest": self.challenge.challenge_digest(),
            "credentialRecordId": "ocred.synthetic",
            "assertionDigest": K.assertion_digest(P.OwnerAssertionV1.from_dict(self.assertion)),
            "proposalRefId": "proposal-ref.synthetic-" + operation.lower(),
            "actionDigest": self.challenge["actionDigest"],
            "requestDigest": self.challenge["requestDigest"],
            "payloadDigest": self.challenge["payloadDigest"],
            "epistemicBasis": epistemic_basis,
            "deploymentEnvironment": self.challenge["deploymentEnvironment"],
            "authorityDomain": self.challenge["authorityDomain"],
            "logicalOwnerId": self.challenge["logicalOwnerId"],
            "policyVersion": self.challenge["policyVersion"],
            "registryTupleVersion": self.challenge["registryTupleVersion"],
            "ledgerEpoch": self.challenge["ledgerEpoch"],
            "brokerKeyId": BROKER_KEY_ID,
            "brokerRelease": BROKER_RELEASE,
            "issuedAt": "2026-09-26T12:00:21Z",
        }
        unsigned.update(evidence_overrides or {})
        self.evidence = sign_evidence(unsigned, evidence_signer)
        self.broker_keys = [broker_key_dict()]
        self.admission = {
            "schemaVersion": 1, "proposalRefId": unsigned["proposalRefId"], "admissionOutcome": "ACCEPTED",
            "applyAuditId": "maudit.synthetic-" + operation.lower(),
            "memoryItemId": "mitem.synthetic", "revisionId": "mrev.synthetic-new",
            "operation": base.operation, "memoryClass": base.memory_class,
            "subjectNamespace": base.subject_namespace, "subjectKey": base.subject_key,
            "payloadDigest": base.payload_digest, "actionDigest": base.action_digest,
            "epistemicBasis": epistemic_basis, "brokerEvidenceId": unsigned["evidenceId"],
        }
        self.admission.update(admission_overrides or {})
        self.context = context()

    def kwargs(self, **replace: Any) -> dict[str, Any]:
        value = {
            "context": self.context, "action": self.action, "challenge_json": self.challenge_json,
            "challenge_record": self.challenge_record, "assertion": self.assertion,
            "owner_credential": self.owner_credential, "evidence": self.evidence,
            "broker_keys": self.broker_keys, "admission": self.admission,
        }
        value.update(replace)
        return value
