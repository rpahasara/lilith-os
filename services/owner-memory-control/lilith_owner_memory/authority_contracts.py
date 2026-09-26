"""15B2b-B1b-3a authority evidence and key registry contracts (TEST-ONLY).

Design: docs/architecture/slice-15b2b-b1b3-custody-isolation-design.md.

This module defines closed, canonically serialized contracts only:

- `RecoveryEpochV1`: the `(counter, random)` recovery epoch;
- `AuthorityKeyRecordV1`: one public authority verification key;
- `AuthorityRegistryV1`: an owner-signed registry of key records, signed by a
  registry root that is distinct from the B1c activation key and from the
  owner WebAuthn credential;
- `OwnerEvidenceV2`: Ed25519 Owner/Actor authority evidence;
- `PrivacyAuthorizationV2`: Ed25519 Privacy erasure authorization, in its own
  cryptographic domain.

Nothing here holds, loads, derives, or stores a private key, reads a file, the
environment, or the network, or touches the broker, L04, or Privacy DB. The
B2a contracts (`contracts.py`) are reused for canonical JSON and B1a field
validators only; `BrokerVerificationKeyV1` and B2a revocation semantics are not
promoted.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Mapping

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from lilith_memory.owner_proof import _b64u_decode, _digest, _exact, _id, _instant, _optional_id

from .contracts import _LOGICAL_OWNER, DEPLOYMENT_ENVIRONMENTS, ContractViolation, _canonical, _choice, _pattern

# Frozen domain separators. Each signed artifact type has its own separator,
# so a signature over one type can never verify as another.
REGISTRY_DOMAIN_SEPARATOR = b"LILITH_AUTHORITY_REGISTRY_V1\x00"
OWNER_EVIDENCE_DOMAIN_SEPARATOR = b"LILITH_ACTOR_EVIDENCE_V2\x00"
PRIVACY_AUTHORIZATION_DOMAIN_SEPARATOR = b"LILITH_PRIVACY_AUTHORIZATION_V2\x00"

REGISTRY_PROTOCOL = "LILITH_AUTHORITY_REGISTRY"
REGISTRY_SCHEMA_VERSION = 1
KEY_RECORD_SCHEMA_VERSION = 1
OWNER_EVIDENCE_PROTOCOL = "LILITH_ACTOR_EVIDENCE"
OWNER_EVIDENCE_SCHEMA_VERSION = 2
PRIVACY_AUTHORIZATION_PROTOCOL = "LILITH_PRIVACY_AUTHORIZATION"
PRIVACY_AUTHORIZATION_SCHEMA_VERSION = 2

ALGORITHM = "Ed25519"

# Cryptographic signing domains (`signingDomain`). They isolate keys and
# signatures. They are NOT the logical authority context: `authorityDomain`
# keeps its established B2a meaning (the logical authority scope within an
# environment). logical authority context != cryptographic signing domain.
# Containment is deliberately absent: the containment key is a detection PRF
# and never an authority-signing key.
OWNER_ACTOR = "OWNER_ACTOR"
PRIVACY = "PRIVACY"
SIGNING_DOMAINS = frozenset({OWNER_ACTOR, PRIVACY})
OWNER_MEMORY_OPERATION = "OWNER_MEMORY_OPERATION"
PRIVACY_ERASURE_AUTHORIZATION = "PRIVACY_ERASURE_AUTHORIZATION"
EVIDENCE_TYPES_BY_DOMAIN = {
    OWNER_ACTOR: frozenset({OWNER_MEMORY_OPERATION}),
    PRIVACY: frozenset({PRIVACY_ERASURE_AUTHORIZATION}),
}
EVIDENCE_TYPES = frozenset().union(*EVIDENCE_TYPES_BY_DOMAIN.values())

COMPROMISED = "COMPROMISED"
REVOCATION_REASONS = frozenset({"ROUTINE", COMPROMISED, "SUPERSEDED"})

# B1b-3a refuses any registry root that is not explicitly labelled TEST-ONLY.
# Promoting these contracts to a real root requires a new, reviewed version.
TEST_ONLY_ROOT_PREFIX = "test-only."

_MAX_JSON_INT = 2**53 - 1
_EPOCH_RANDOM = re.compile(r"[0-9a-f]{32}\Z")


def _int(value: Any, name: str, minimum: int) -> int:
    if type(value) is not int or not minimum <= value <= _MAX_JSON_INT:
        raise ContractViolation("INVALID_" + name.upper())
    return value


def _schema(value: Mapping[str, Any], protocol: str, version: int) -> None:
    if value.get("protocol") != protocol:
        raise ContractViolation("UNSUPPORTED_SCHEMA_VERSION")
    if type(value.get("schemaVersion")) is not int or value["schemaVersion"] != version:
        raise ContractViolation("UNSUPPORTED_SCHEMA_VERSION")


def _public_key(value: Any) -> bytes:
    raw = _b64u_decode(value, "public_key", 32, 32)
    try:
        Ed25519PublicKey.from_public_bytes(raw)
    except ValueError as exc:
        raise ContractViolation("INVALID_PUBLIC_KEY") from exc
    return raw


def _signature(value: Any) -> bytes:
    return _b64u_decode(value, "signature", 64, 64)


def _optional_instant(value: Any) -> datetime | None:
    return None if value is None else _instant(value)


@dataclass(frozen=True)
class RecoveryEpochV1:
    """`(counter, random)`. `random` distinguishes divergent restores that
    advance to the same counter. Equality is exact on both parts."""

    counter: int
    random: str

    @classmethod
    def from_dict(cls, value: Any) -> RecoveryEpochV1:
        _exact(value, frozenset({"counter", "random"}))
        return cls(_int(value["counter"], "recovery_epoch", 0),
                   _pattern(value["random"], _EPOCH_RANDOM, "recovery_epoch"))

    def to_dict(self) -> dict[str, Any]:
        return {"counter": self.counter, "random": self.random}


KEY_RECORD_FIELDS = frozenset({
    "schemaVersion", "keyId", "signingDomain", "evidenceTypes", "environment",
    "algorithm", "publicKey", "createdAt", "notBefore", "retiredAt", "revokedAt",
    "revocationReason", "compromisedSince", "recoveryEpoch", "policyVersion",
    "registryVersion",
})


@dataclass(frozen=True)
class AuthorityKeyRecordV1:
    """One public authority verification key. No private material.

    `signingDomain` is the cryptographic domain the key may sign for. A key
    record carries no logical `authorityDomain`.

    `registryVersion` is the registry version in which this key was first
    published. It is immutable: it does not change when the record is later
    retired or revoked, and evidence can never claim an earlier version.
    """

    key_id: str
    signing_domain: str
    evidence_types: frozenset[str]
    environment: str
    public_key: bytes
    created_at: datetime
    not_before: datetime
    retired_at: datetime | None
    revoked_at: datetime | None
    revocation_reason: str | None
    compromised_since: datetime | None
    recovery_epoch: RecoveryEpochV1
    policy_version: str
    registry_version: int

    @property
    def compromised(self) -> bool:
        return self.revocation_reason == COMPROMISED

    @property
    def current(self) -> bool:
        return self.retired_at is None and self.revoked_at is None

    @classmethod
    def from_dict(cls, value: Any) -> AuthorityKeyRecordV1:
        _exact(value, KEY_RECORD_FIELDS)
        if type(value["schemaVersion"]) is not int or value["schemaVersion"] != KEY_RECORD_SCHEMA_VERSION:
            raise ContractViolation("UNSUPPORTED_SCHEMA_VERSION")
        if value["algorithm"] != ALGORITHM:
            raise ContractViolation("UNSUPPORTED_ALGORITHM")
        domain = _choice(value["signingDomain"], SIGNING_DOMAINS, "signing_domain")
        types = value["evidenceTypes"]
        if (not isinstance(types, list) or not types or types != sorted(set(types))
                or not all(isinstance(t, str) for t in types)
                or not set(types) <= EVIDENCE_TYPES_BY_DOMAIN[domain]):
            raise ContractViolation("INVALID_EVIDENCE_TYPES")
        record = cls(
            _id(value["keyId"], "key_id"), domain, frozenset(types),
            _choice(value["environment"], DEPLOYMENT_ENVIRONMENTS, "environment"),
            _public_key(value["publicKey"]),
            _instant(value["createdAt"]), _instant(value["notBefore"]),
            _optional_instant(value["retiredAt"]), _optional_instant(value["revokedAt"]),
            None if value["revocationReason"] is None
            else _choice(value["revocationReason"], REVOCATION_REASONS, "revocation_reason"),
            _optional_instant(value["compromisedSince"]),
            RecoveryEpochV1.from_dict(value["recoveryEpoch"]),
            _id(value["policyVersion"], "policy_version"),
            _int(value["registryVersion"], "registry_version", 1),
        )
        if record.not_before < record.created_at:
            raise ContractViolation("INVALID_VALIDITY_INTERVAL")
        if record.retired_at is not None and record.retired_at < record.not_before:
            raise ContractViolation("INVALID_VALIDITY_INTERVAL")
        if (record.revoked_at is None) != (record.revocation_reason is None):
            raise ContractViolation("INVALID_REVOCATION")
        if record.revoked_at is not None and record.revoked_at < record.created_at:
            raise ContractViolation("INVALID_REVOCATION")
        if record.compromised != (record.compromised_since is not None):
            raise ContractViolation("INVALID_REVOCATION")
        if record.compromised_since is not None and record.compromised_since > record.revoked_at:
            raise ContractViolation("INVALID_REVOCATION")
        return record


REGISTRY_FIELDS = frozenset({
    "protocol", "schemaVersion", "environment", "registryVersion", "recoveryEpoch",
    "policyVersion", "registryRootKeyId", "issuedAt", "keys", "signature",
})
REGISTRY_SIGNED_FIELDS = REGISTRY_FIELDS - {"signature"}


@dataclass(frozen=True)
class AuthorityRegistryV1:
    """An owner-signed registry document. Its signature covers every field
    except `signature`, so contents, schema, environment, registry version,
    recovery epoch, and policy version are all bound."""

    environment: str
    registry_version: int
    recovery_epoch: RecoveryEpochV1
    policy_version: str
    registry_root_key_id: str
    issued_at: datetime
    keys: Mapping[str, AuthorityKeyRecordV1]

    @classmethod
    def from_verified_dict(cls, value: Mapping[str, Any]) -> AuthorityRegistryV1:
        """Parse a registry whose signature has already been verified."""
        _exact(value, REGISTRY_FIELDS)
        _schema(value, REGISTRY_PROTOCOL, REGISTRY_SCHEMA_VERSION)
        environment = _choice(value["environment"], DEPLOYMENT_ENVIRONMENTS, "environment")
        version = _int(value["registryVersion"], "registry_version", 1)
        epoch = RecoveryEpochV1.from_dict(value["recoveryEpoch"])
        policy = _id(value["policyVersion"], "policy_version")
        issued = _instant(value["issuedAt"])
        if not isinstance(value["keys"], list):
            raise ContractViolation("INVALID_KEYS")
        keys: dict[str, AuthorityKeyRecordV1] = {}
        public_keys: set[bytes] = set()
        for raw in value["keys"]:
            record = AuthorityKeyRecordV1.from_dict(raw)
            if record.environment != environment:
                raise ContractViolation("KEY_ENVIRONMENT_MISMATCH")
            if keys and record.key_id <= max(keys):
                raise ContractViolation("INVALID_KEY_ORDER")  # strictly ascending, unique
            if record.public_key in public_keys:
                raise ContractViolation("DUPLICATE_PUBLIC_KEY")  # no key serves two roles
            if record.registry_version > version:
                raise ContractViolation("INVALID_KEY_REGISTRY_VERSION")
            for instant in (record.created_at, record.retired_at, record.revoked_at, record.compromised_since):
                if instant is not None and instant > issued:
                    raise ContractViolation("INVALID_KEY_TIMESTAMP")
            older = record.recovery_epoch.counter < epoch.counter
            if not older and record.recovery_epoch != epoch:
                raise ContractViolation("INVALID_KEY_RECOVERY_EPOCH")  # future or forked epoch
            if record.current and (older or record.policy_version != policy):
                raise ContractViolation("INVALID_KEY_RECOVERY_EPOCH" if older else "INVALID_KEY_POLICY_VERSION")
            keys[record.key_id] = record
            public_keys.add(record.public_key)
        return cls(environment, version, epoch, policy,
                   _id(value["registryRootKeyId"], "registry_root_key_id"), issued, keys)


def registry_signing_bytes(unsigned: Mapping[str, Any]) -> bytes:
    """Bytes the registry root signs; used by TEST-ONLY fixtures."""
    _exact(unsigned, REGISTRY_SIGNED_FIELDS)
    return REGISTRY_DOMAIN_SEPARATOR + _canonical(unsigned)


TRUSTED_ROOT_FIELDS = frozenset({"schemaVersion", "rootKeyId", "environment", "algorithm", "publicKey"})


@dataclass(frozen=True)
class TrustedRegistryRootV1:
    """The caller-supplied trust anchor for one environment's registry.

    It is a distinct root: never the B1c activation key, never an owner
    WebAuthn credential. In B1b-3a only `test-only.` roots are accepted.
    """

    root_key_id: str
    environment: str
    public_key: bytes

    @classmethod
    def from_dict(cls, value: Any) -> TrustedRegistryRootV1:
        _exact(value, TRUSTED_ROOT_FIELDS)
        if type(value["schemaVersion"]) is not int or value["schemaVersion"] != 1:
            raise ContractViolation("UNSUPPORTED_SCHEMA_VERSION")
        if value["algorithm"] != ALGORITHM:
            raise ContractViolation("UNSUPPORTED_ALGORITHM")
        return cls(_id(value["rootKeyId"], "root_key_id"),
                   _choice(value["environment"], DEPLOYMENT_ENVIRONMENTS, "environment"),
                   _public_key(value["publicKey"]))

    @property
    def test_only(self) -> bool:
        return self.root_key_id.startswith(TEST_ONLY_ROOT_PREFIX)


class _SignedEvidence:
    """Shared shape for the two V2 evidence contracts."""

    PROTOCOL: str
    SCHEMA_VERSION: int
    DOMAIN_SEPARATOR: bytes
    FIELDS: frozenset[str]
    ID_FIELDS: tuple[str, ...]
    DIGEST_FIELDS: tuple[str, ...]

    def __init__(self, fields: Mapping[str, Any], signature: bytes,
                 recovery_epoch: RecoveryEpochV1, issued_at: datetime):
        self.fields = fields
        self.signature = signature
        self.recovery_epoch = recovery_epoch
        self.issued_at = issued_at

    @classmethod
    def signed_fields(cls) -> frozenset[str]:
        return cls.FIELDS - {"signature"}

    @classmethod
    def from_dict(cls, value: Any):
        if not isinstance(value, Mapping):
            raise ContractViolation("INVALID_FIELDS")
        if value.get("protocol") == cls.PROTOCOL and value.get("schemaVersion") != cls.SCHEMA_VERSION:
            raise ContractViolation("UNSUPPORTED_SCHEMA_VERSION")
        _exact(value, cls.FIELDS)
        _schema(value, cls.PROTOCOL, cls.SCHEMA_VERSION)
        _choice(value["signingDomain"], SIGNING_DOMAINS, "signing_domain")
        # Logical authority context, B2a meaning. A signing-domain name is never
        # accepted here, so the two fields cannot be confused.
        if _id(value["authorityDomain"], "authority_domain") in SIGNING_DOMAINS:
            raise ContractViolation("INVALID_AUTHORITY_DOMAIN")
        _choice(value["evidenceType"], EVIDENCE_TYPES, "evidence_type")
        _choice(value["environment"], DEPLOYMENT_ENVIRONMENTS, "environment")
        for name in cls.ID_FIELDS + ("keyId", "policyVersion"):
            _id(value[name], name)
        for name in cls.DIGEST_FIELDS:
            _digest(value[name], name)
        _int(value["registryVersion"], "registry_version", 1)
        epoch = RecoveryEpochV1.from_dict(value["recoveryEpoch"])
        issued = _instant(value["issuedAt"])
        cls._validate_specific(value)
        signature = _signature(value["signature"])
        return cls({name: value[name] for name in cls.signed_fields()}, signature, epoch, issued)

    @classmethod
    def _validate_specific(cls, value: Mapping[str, Any]) -> None:
        del value

    def __getitem__(self, name: str) -> Any:
        return self.fields[name]

    def signing_bytes(self) -> bytes:
        return self.DOMAIN_SEPARATOR + _canonical(self.fields)

    @classmethod
    def unsigned_signing_bytes(cls, unsigned: Mapping[str, Any]) -> bytes:
        _exact(unsigned, cls.signed_fields())
        return cls.DOMAIN_SEPARATOR + _canonical(unsigned)


_COMMON_EVIDENCE_FIELDS = frozenset({
    "protocol", "schemaVersion", "signingDomain", "authorityDomain", "evidenceType", "environment",
    "logicalOwnerId", "keyId", "registryVersion", "recoveryEpoch", "policyVersion",
    "issuedAt", "signature",
})


class OwnerEvidenceV2(_SignedEvidence):
    """Owner/Actor authority evidence over one verified owner operation.

    `evidenceNonce` must equal `challengeId` (B1b-1: the challenge ID is the
    unique evidence nonce). `challengeId`/`challengeDigest` and
    `credentialRecordId`/`assertionDigest` are the owner-proof reference.
    """

    PROTOCOL = OWNER_EVIDENCE_PROTOCOL
    SCHEMA_VERSION = OWNER_EVIDENCE_SCHEMA_VERSION
    DOMAIN_SEPARATOR = OWNER_EVIDENCE_DOMAIN_SEPARATOR
    FIELDS = _COMMON_EVIDENCE_FIELDS | {
        "evidenceId", "evidenceNonce", "challengeId", "challengeDigest",
        "credentialRecordId", "assertionDigest", "actionDigest", "requestDigest",
        "payloadDigest",
    }
    ID_FIELDS = ("evidenceId", "evidenceNonce", "challengeId", "credentialRecordId")
    DIGEST_FIELDS = ("challengeDigest", "assertionDigest", "actionDigest", "requestDigest", "payloadDigest")

    @classmethod
    def _validate_specific(cls, value: Mapping[str, Any]) -> None:
        _pattern(value["logicalOwnerId"], _LOGICAL_OWNER, "logical_owner_id")


class PrivacyAuthorizationV2(_SignedEvidence):
    """Privacy erasure authorization for exactly one canonical identity.

    It carries the grounding Owner/Actor evidence ID, the hold that precedes
    erasure, and the required resource owners. It moves no Privacy DB and
    migrates no selector PRF.
    """

    PROTOCOL = PRIVACY_AUTHORIZATION_PROTOCOL
    SCHEMA_VERSION = PRIVACY_AUTHORIZATION_SCHEMA_VERSION
    DOMAIN_SEPARATOR = PRIVACY_AUTHORIZATION_DOMAIN_SEPARATOR
    FIELDS = _COMMON_EVIDENCE_FIELDS | {
        "authorizationId", "executionNonce", "forgetRequestId", "holdId",
        "ownerEvidenceId", "memoryClass", "subjectNamespace", "subjectKey",
        "memoryItemId", "actionDigest", "resourceOwners",
    }
    ID_FIELDS = ("authorizationId", "executionNonce", "forgetRequestId", "holdId",
                 "ownerEvidenceId", "memoryClass", "subjectNamespace", "subjectKey")
    DIGEST_FIELDS = ("actionDigest",)

    @classmethod
    def _validate_specific(cls, value: Mapping[str, Any]) -> None:
        _pattern(value["logicalOwnerId"], _LOGICAL_OWNER, "logical_owner_id")
        _optional_id(value["memoryItemId"], "memory_item_id")
        owners = value["resourceOwners"]
        if (not isinstance(owners, list) or not owners or not all(isinstance(o, str) for o in owners)
                or owners != sorted(set(owners))):
            raise ContractViolation("INVALID_RESOURCE_OWNERS")
        for owner in owners:
            _id(owner, "resource_owners")


def owner_evidence_signing_bytes(unsigned: Mapping[str, Any]) -> bytes:
    """Bytes an Owner/Actor authority key signs; used by TEST-ONLY fixtures."""
    return OwnerEvidenceV2.unsigned_signing_bytes(unsigned)


def privacy_authorization_signing_bytes(unsigned: Mapping[str, Any]) -> bytes:
    """Bytes a Privacy authority key signs; used by TEST-ONLY fixtures."""
    return PrivacyAuthorizationV2.unsigned_signing_bytes(unsigned)


NEW_ADMISSION = "NEW_ADMISSION"
HISTORICAL_VERIFICATION = "HISTORICAL_VERIFICATION"
PURPOSES = frozenset({NEW_ADMISSION, HISTORICAL_VERIFICATION})


@dataclass(frozen=True)
class AuthorityVerificationContextV1:
    """Trusted caller expectations; never read from the artifacts verified.

    `trusted_minimum_registry_version` is a monotonic value the caller already
    trusts. Where it comes from is out of scope for B1b-3a; local filesystem
    state is not assumed to be a monotonic authority.
    """

    environment: str
    purpose: str
    registry_root: TrustedRegistryRootV1
    trusted_minimum_registry_version: int
    expected_recovery_epoch: RecoveryEpochV1
    policy_version: str

    def validate(self) -> None:
        _choice(self.environment, DEPLOYMENT_ENVIRONMENTS, "environment")
        _choice(self.purpose, PURPOSES, "purpose")
        if not isinstance(self.registry_root, TrustedRegistryRootV1):
            raise ContractViolation("INVALID_REGISTRY_ROOT")
        _int(self.trusted_minimum_registry_version, "trusted_minimum_registry_version", 1)
        if not isinstance(self.expected_recovery_epoch, RecoveryEpochV1):
            raise ContractViolation("INVALID_RECOVERY_EPOCH")
        RecoveryEpochV1.from_dict(self.expected_recovery_epoch.to_dict())
        _id(self.policy_version, "policy_version")


@dataclass(frozen=True)
class OwnerEvidenceExpectationV2:
    """What the caller already verified independently (owner proof, frozen
    action, admission link). Evidence must match every field."""

    evidence_id: str
    challenge_id: str
    challenge_digest: str
    credential_record_id: str
    assertion_digest: str
    action_digest: str
    request_digest: str
    payload_digest: str
    logical_owner_id: str
    authority_domain: str


@dataclass(frozen=True)
class PrivacyAuthorizationExpectationV2:
    """What the caller already verified independently (forget request, hold,
    grounding owner evidence, required owners)."""

    authorization_id: str
    execution_nonce: str
    forget_request_id: str
    hold_id: str
    owner_evidence_id: str
    memory_class: str
    subject_namespace: str
    subject_key: str
    memory_item_id: str | None
    action_digest: str
    resource_owners: tuple[str, ...]
    logical_owner_id: str
    authority_domain: str
