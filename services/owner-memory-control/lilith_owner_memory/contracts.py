"""15B2b-B2a closed contracts for accepted-memory verification (TEST-ONLY).

Design: docs/architecture/slice-15b2b-b-owner-memory-control-design.md.

`OwnerMemoryChallengeV2` is a new version of the B1a owner challenge. The B1a
`OwnerMemoryChallengeV1` class, its domain separator and its golden vectors are
reused unchanged: every V1 field keeps its canonical name and validation rule,
and V1 validation is delegated to the V1 class itself. V2 adds only logical
authority context. It carries no VM, host, instance, or broker-key binding and
no identity-charter reference (a deferred schema extension).

`BrokerMemoryEvidenceEnvelopeV1` is broker-issued evidence over a verified
owner operation. It carries `brokerKeyId`, the broker release and an Ed25519
signature. Broker evidence alone is not owner authorization.

`OwnerChallengeLedgerRecordV2` and `CanonicalAdmissionRecordV1` are TEST-ONLY
typed representations of state that exists elsewhere (the B1a durable challenge
row plus the broker ledger epoch, and the L04 admission/apply audit). They
carry no authority on their own.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from typing import Any, Mapping

import rfc8785
from lilith_memory import owner_proof as P
# B1a validators are reused, not re-implemented, so V1 and V2 share one set of
# field rules.
from lilith_memory.owner_proof import (
    OwnerProofError,
    _b64u_decode,
    _digest,
    _exact,
    _id,
    _instant,
    _optional_id,
    _text,
)


CHALLENGE_V2_SCHEMA_VERSION = 2
CHALLENGE_V2_DOMAIN_SEPARATOR = b"LILITH_OWNER_MEMORY_CHALLENGE_V2\x00"
ASSERTION_DIGEST_DOMAIN_SEPARATOR = b"LILITH_OWNER_MEMORY_ASSERTION_DIGEST_V1\x00"
EVIDENCE_PROTOCOL = "LILITH_BROKER_MEMORY_EVIDENCE"
EVIDENCE_SCHEMA_VERSION = 1
EVIDENCE_DOMAIN_SEPARATOR = b"LILITH_BROKER_MEMORY_EVIDENCE_V1\x00"
DEPLOYMENT_ENVIRONMENTS = frozenset({"test", "dev", "prod"})
LEDGER_STATES = frozenset({"PREPARED", "CONSUMED", "CANCELLED", "EXPIRED"})
ADMISSION_OUTCOMES = frozenset({"ACCEPTED", "REJECTED", "PRECONDITION_FAILED"})
BROKER_KEY_ALGORITHM = "Ed25519"

_LOGICAL_OWNER = re.compile(r"owner\.[a-z0-9][a-z0-9-]{0,62}\.v[1-9][0-9]{0,3}\Z")
_RELEASE = re.compile(r"[0-9a-f]{40}\Z")
_BASIS = re.compile(r"[A-Z][A-Z0-9_]{0,63}\Z")  # memory_contracts._BASIS_RE


class ContractViolation(OwnerProofError):
    """Closed failure code for a B2a artifact; never contains memory values."""


def _schema_version(value: Any, expected: int) -> None:
    if type(value) is not int or value != expected:
        raise ContractViolation("UNSUPPORTED_SCHEMA_VERSION")


def _choice(value: Any, allowed: frozenset[str], name: str) -> str:
    if not isinstance(value, str) or value not in allowed:
        raise ContractViolation("INVALID_" + name.upper())
    return value


def _pattern(value: Any, pattern: re.Pattern[str], name: str) -> str:
    if not isinstance(value, str) or not pattern.fullmatch(value):
        raise ContractViolation("INVALID_" + name.upper())
    return value


def _canonical(value: Mapping[str, Any]) -> bytes:
    try:
        return rfc8785.dumps(dict(value))
    except rfc8785.CanonicalizationError as exc:
        raise ContractViolation("INVALID_CANONICALIZATION") from exc


_V1_FIELDS = tuple(sorted(P._CHALLENGE_FIELDS))
_V2_EXTRA_FIELDS = (
    "deploymentEnvironment", "authorityDomain", "logicalOwnerId",
    "policyVersion", "registryTupleVersion", "ledgerEpoch",
)
CHALLENGE_V2_FIELDS = frozenset(_V1_FIELDS + _V2_EXTRA_FIELDS)


@dataclass(frozen=True)
class OwnerMemoryChallengeV2:
    """The owner-signed operation intent: V1 fields plus logical authority context."""

    fields: Mapping[str, Any]

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> OwnerMemoryChallengeV2:
        if not isinstance(value, Mapping):
            raise ContractViolation("INVALID_FIELDS")
        if value.get("schemaVersion") != CHALLENGE_V2_SCHEMA_VERSION and set(value) == P._CHALLENGE_FIELDS:
            raise ContractViolation("UNSUPPORTED_SCHEMA_VERSION")
        _exact(value, CHALLENGE_V2_FIELDS)
        result = cls(dict(value))
        result.validate()
        return result

    def __getitem__(self, name: str) -> Any:
        return self.fields[name]

    def validate(self) -> None:
        value = self.fields
        _exact(value, CHALLENGE_V2_FIELDS)
        if value["protocol"] != P.PROTOCOL:
            raise ContractViolation("UNSUPPORTED_SCHEMA_VERSION")
        _schema_version(value["schemaVersion"], CHALLENGE_V2_SCHEMA_VERSION)
        # Every shared field is validated by the unchanged V1 contract.
        shared = {name: value[name] for name in _V1_FIELDS}
        shared["schemaVersion"] = P.SCHEMA_VERSION
        P.OwnerMemoryChallengeV1.from_dict(shared)
        _choice(value["deploymentEnvironment"], DEPLOYMENT_ENVIRONMENTS, "deployment_environment")
        _id(value["authorityDomain"], "authority_domain")
        _pattern(value["logicalOwnerId"], _LOGICAL_OWNER, "logical_owner_id")
        _id(value["policyVersion"], "policy_version")
        _id(value["registryTupleVersion"], "registry_tuple_version")
        _id(value["ledgerEpoch"], "ledger_epoch")

    def to_dict(self) -> dict[str, Any]:
        self.validate()
        return {name: self.fields[name] for name in sorted(CHALLENGE_V2_FIELDS)}

    def canonical_bytes(self) -> bytes:
        return _canonical(self.to_dict())

    def webauthn_challenge(self) -> bytes:
        return hashlib.sha256(CHALLENGE_V2_DOMAIN_SEPARATOR + self.canonical_bytes()).digest()

    def challenge_digest(self) -> str:
        return self.webauthn_challenge().hex()


def assertion_digest(assertion: P.OwnerAssertionV1) -> str:
    """Re-verifiable owner-proof reference carried by broker evidence."""
    assertion.validate()
    return hashlib.sha256(ASSERTION_DIGEST_DOMAIN_SEPARATOR + _canonical({
        "credentialRecordId": assertion.credential_record_id,
        "credentialId": assertion.credential_id,
        "clientDataJSON": assertion.client_data_json,
        "authenticatorData": assertion.authenticator_data,
        "signature": assertion.signature,
    })).hexdigest()


LEDGER_RECORD_FIELDS = frozenset({
    "schemaVersion", "challengeId", "state", "consumedCredentialRecordId",
    "consumedAt", "ledgerEpoch",
})


@dataclass(frozen=True)
class OwnerChallengeLedgerRecordV2:
    """TEST-ONLY view of the B1a durable challenge row plus the ledger epoch."""

    challenge_id: str
    state: str
    consumed_credential_record_id: str | None
    consumed_at: str | None
    ledger_epoch: str

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> OwnerChallengeLedgerRecordV2:
        _exact(value, LEDGER_RECORD_FIELDS)
        _schema_version(value["schemaVersion"], 1)
        state = _choice(value["state"], LEDGER_STATES, "ledger_state")
        record = cls(
            _id(value["challengeId"], "challenge_id"), state,
            _optional_id(value["consumedCredentialRecordId"], "record_id"),
            value["consumedAt"], _id(value["ledgerEpoch"], "ledger_epoch"),
        )
        if state == "CONSUMED":
            if record.consumed_credential_record_id is None or record.consumed_at is None:
                raise ContractViolation("INVALID_LEDGER_STATE")
            _instant(record.consumed_at)
        elif record.consumed_credential_record_id is not None or record.consumed_at is not None:
            raise ContractViolation("INVALID_LEDGER_STATE")
        return record


BROKER_KEY_FIELDS = frozenset({
    "schemaVersion", "brokerKeyId", "algorithm", "publicKey", "status",
    "createdAt", "revokedAt", "deploymentEnvironment", "authorityDomain",
})


@dataclass(frozen=True)
class BrokerVerificationKeyV1:
    """Public broker evidence-verification material; no private key."""

    broker_key_id: str
    public_key: bytes
    status: str
    created_at: str
    revoked_at: str | None
    deployment_environment: str
    authority_domain: str

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> BrokerVerificationKeyV1:
        _exact(value, BROKER_KEY_FIELDS)
        _schema_version(value["schemaVersion"], 1)
        if value["algorithm"] != BROKER_KEY_ALGORITHM:
            raise ContractViolation("UNSUPPORTED_ALGORITHM")
        status = _choice(value["status"], frozenset({"ACTIVE", "REVOKED"}), "broker_key_status")
        key = cls(
            _id(value["brokerKeyId"], "broker_key_id"),
            _b64u_decode(value["publicKey"], "public_key", 32, 32),
            status, value["createdAt"], value["revokedAt"],
            _choice(value["deploymentEnvironment"], DEPLOYMENT_ENVIRONMENTS, "deployment_environment"),
            _id(value["authorityDomain"], "authority_domain"),
        )
        created = _instant(key.created_at)
        if status == "ACTIVE" and key.revoked_at is not None:
            raise ContractViolation("INVALID_REVOCATION")
        if status == "REVOKED" and (key.revoked_at is None or _instant(key.revoked_at) < created):
            raise ContractViolation("INVALID_REVOCATION")
        return key


EVIDENCE_FIELDS = frozenset({
    "protocol", "schemaVersion", "evidenceId", "evidenceNonce", "challengeId",
    "challengeDigest", "credentialRecordId", "assertionDigest", "proposalRefId",
    "actionDigest", "requestDigest", "payloadDigest", "epistemicBasis",
    "deploymentEnvironment", "authorityDomain", "logicalOwnerId",
    "policyVersion", "registryTupleVersion", "ledgerEpoch", "brokerKeyId",
    "brokerRelease", "issuedAt", "signature",
})
EVIDENCE_SIGNED_FIELDS = EVIDENCE_FIELDS - {"signature"}


@dataclass(frozen=True)
class BrokerMemoryEvidenceEnvelopeV1:
    """Broker-issued evidence over one verified owner operation."""

    fields: Mapping[str, Any]
    signature: bytes

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> BrokerMemoryEvidenceEnvelopeV1:
        if not isinstance(value, Mapping):
            raise ContractViolation("INVALID_FIELDS")
        if value.get("protocol") == EVIDENCE_PROTOCOL and value.get("schemaVersion") != EVIDENCE_SCHEMA_VERSION:
            raise ContractViolation("UNSUPPORTED_SCHEMA_VERSION")
        _exact(value, EVIDENCE_FIELDS)
        if value["protocol"] != EVIDENCE_PROTOCOL:
            raise ContractViolation("UNSUPPORTED_SCHEMA_VERSION")
        _schema_version(value["schemaVersion"], EVIDENCE_SCHEMA_VERSION)
        for name in ("evidenceId", "evidenceNonce", "challengeId", "credentialRecordId",
                     "proposalRefId", "authorityDomain", "policyVersion",
                     "registryTupleVersion", "ledgerEpoch", "brokerKeyId"):
            _id(value[name], name)
        for name in ("challengeDigest", "assertionDigest", "actionDigest",
                     "requestDigest", "payloadDigest"):
            _digest(value[name], name)
        _pattern(value["epistemicBasis"], _BASIS, "epistemic_basis")
        _choice(value["deploymentEnvironment"], DEPLOYMENT_ENVIRONMENTS, "deployment_environment")
        _pattern(value["logicalOwnerId"], _LOGICAL_OWNER, "logical_owner_id")
        _pattern(value["brokerRelease"], _RELEASE, "broker_release")
        _instant(value["issuedAt"])
        signature = _b64u_decode(value["signature"], "signature", 64, 64)
        return cls({name: value[name] for name in EVIDENCE_SIGNED_FIELDS}, signature)

    def __getitem__(self, name: str) -> Any:
        return self.fields[name]

    def signing_bytes(self) -> bytes:
        return EVIDENCE_DOMAIN_SEPARATOR + _canonical(self.fields)

    def evidence_digest(self) -> str:
        return hashlib.sha256(self.signing_bytes()).hexdigest()


def evidence_signing_bytes(unsigned: Mapping[str, Any]) -> bytes:
    """Bytes a broker signs; used by TEST-ONLY fixtures to issue evidence."""
    _exact(unsigned, EVIDENCE_SIGNED_FIELDS)
    return EVIDENCE_DOMAIN_SEPARATOR + _canonical(unsigned)


ADMISSION_FIELDS = frozenset({
    "schemaVersion", "proposalRefId", "admissionOutcome", "applyAuditId",
    "memoryItemId", "revisionId", "operation", "memoryClass",
    "subjectNamespace", "subjectKey", "payloadDigest", "actionDigest",
    "epistemicBasis", "brokerEvidenceId",
})


@dataclass(frozen=True)
class CanonicalAdmissionRecordV1:
    """TEST-ONLY view of an L04 terminal admission and its apply audit."""

    fields: Mapping[str, Any]

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> CanonicalAdmissionRecordV1:
        _exact(value, ADMISSION_FIELDS)
        _schema_version(value["schemaVersion"], 1)
        outcome = _choice(value["admissionOutcome"], ADMISSION_OUTCOMES, "admission_outcome")
        for name in ("proposalRefId", "memoryItemId", "revisionId", "memoryClass",
                     "subjectNamespace", "subjectKey", "brokerEvidenceId"):
            _id(value[name], name)
        _optional_id(value["applyAuditId"], "apply_audit_id")
        _choice(value["operation"], frozenset({"CREATE", "SUPERSEDE", "RESTORE"}), "operation")
        _digest(value["payloadDigest"], "payload_digest")
        _digest(value["actionDigest"], "action_digest")
        _pattern(value["epistemicBasis"], _BASIS, "epistemic_basis")
        if (outcome == "ACCEPTED") != (value["applyAuditId"] is not None):
            raise ContractViolation("INVALID_ADMISSION_SHAPE")
        return cls(dict(value))

    def __getitem__(self, name: str) -> Any:
        return self.fields[name]


@dataclass(frozen=True)
class AcceptanceContextV1:
    """Trusted expectations supplied by the caller; never read from artifacts."""

    deployment_environment: str
    authority_domain: str
    logical_owner_id: str
    owner_principal: str
    rp_id: str
    origin: str
    policy_version: str
    registry_tuple_version: str
    ledger_epoch: str
    privacy_notice_version: str
    broker_releases: frozenset[str]

    def validate(self) -> None:
        _choice(self.deployment_environment, DEPLOYMENT_ENVIRONMENTS, "deployment_environment")
        _id(self.authority_domain, "authority_domain")
        _pattern(self.logical_owner_id, _LOGICAL_OWNER, "logical_owner_id")
        _text(self.owner_principal, "owner_principal", 256)
        _text(self.rp_id, "rp_id", 253)
        _text(self.origin, "origin", 300)
        for name in ("policy_version", "registry_tuple_version", "ledger_epoch",
                     "privacy_notice_version"):
            _id(getattr(self, name), name)
        if not isinstance(self.broker_releases, frozenset) or not self.broker_releases:
            raise ContractViolation("INVALID_BROKER_RELEASES")
        for release in self.broker_releases:
            _pattern(release, _RELEASE, "broker_release")
