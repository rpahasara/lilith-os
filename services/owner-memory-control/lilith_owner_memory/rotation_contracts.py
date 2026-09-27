"""15B2b-B1b-3e rotation, revocation, restore and recovery contracts (TEST-ONLY).

Design: docs/architecture/slice-15b2b-b1b3e-rotation-revocation-recovery.md.
Record: docs/architecture/slice-15b2b-b1b3e-source-contracts.md.

Four stories are kept apart, and nothing here lets one acquire another's role:

1. Authority: K-ROOT-signed `AuthorityRegistryV1` generations and the two
   K-ROOT-signed execution authorizations defined here
   (`EpochAdvanceAuthorizationV1`, `RegistryHeadAdvanceAuthorizationV1`).
2. Freshness: `RecoveryWitnessV2`, which binds the exact trusted registry head
   `(registryVersion, registryDigest)`. A witness is freshness / rollback
   evidence only; it never authorizes and never authors registry content.
3. Issuance readiness: the independently reproduced loaded-key binding and
   the rotation state machine's `S_CURRENT` conditions.
4. Storage / observation: registry bytes, ledger observations
   (`REGISTRY_VIEW`), signer HEALTH reports, ceremony publications. These are
   inputs that stories 1-3 evaluate; they are never authority.

Pinned:

    signed registry        != effective current registry head
    registry existence     != head-advance permission
    K-ROOT authorization   != witness execution
    witness execution      != independent verification
    registry-head advance  != key issuance readiness
    REGISTRY_VIEW          != authority
    loaded credential      != current authority
    signer claim           != verification
    S_ACTIVATED            != S_CURRENT
    ledger evidence        != registry authority

Unchanged here: `AuthorityKeyRecordV1`, `AuthorityRegistryV1`,
`RecoveryEpochV1`, `RecoveryWitnessV1`, the B1b-3a verifier (compromise stays
retroactive for every piece of evidence of a COMPROMISED key), and every
earlier golden vector. `RecoveryWitnessV2` coexists with V1.

Threat limit: the witness detects rollback only while it survives. A
witness, registry and authority recovery ledger rolled back together
(whole-host / whole-snapshot rollback) are not detected. Nothing here is
whole-host rollback protection.

The module holds public verification material only. It reads no file,
environment, network, database or credential, and never signs.
"""

from __future__ import annotations

import base64
import hashlib
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Mapping, Sequence

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from lilith_memory.owner_proof import OwnerProofError, _digest, _exact, _id, _instant

from . import authority_contracts as A
from . import authority_verifier as AV
from . import recovery_contracts as R
from .contracts import DEPLOYMENT_ENVIRONMENTS, ContractViolation, _canonical, _choice, _pattern

# Frozen domain separators, distinct from every earlier separator.
EPOCH_ADVANCE_AUTHORIZATION_DOMAIN_SEPARATOR = b"LILITH_EPOCH_ADVANCE_AUTHORIZATION_V1\x00"
REGISTRY_HEAD_ADVANCE_AUTHORIZATION_DOMAIN_SEPARATOR = b"LILITH_REGISTRY_HEAD_ADVANCE_AUTHORIZATION_V1\x00"
WITNESS_V2_DOMAIN_SEPARATOR = b"LILITH_RECOVERY_WITNESS_V2\x00"

EPOCH_ADVANCE_AUTHORIZATION_PROTOCOL = "LILITH_EPOCH_ADVANCE_AUTHORIZATION"
REGISTRY_HEAD_ADVANCE_AUTHORIZATION_PROTOCOL = "LILITH_REGISTRY_HEAD_ADVANCE_AUTHORIZATION"
AUTHORIZATION_SCHEMA_VERSION = 1
# V2 keeps the V1 protocol name and bumps the schema version, so a V1 parser
# refuses a V2 document (and vice versa) instead of misreading it.
WITNESS_V2_SCHEMA_VERSION = 2

# The closed B1b-3c epoch-advance reasons (equal to the TEST recovery ledger's
# `RECOVERY_REASONS`; asserted by tests without importing the signer package).
EPOCH_ADVANCE_REASONS = frozenset({
    "LEDGER_RESTORE_DETECTED", "WITNESS_LEDGER_MISMATCH", "KEY_COMPROMISE", "OPERATOR_RECOVERY",
})
# The closed in-epoch head-advance reasons.
HEAD_ADVANCE_REASONS = frozenset({"SUCCESSOR_ROTATION", "ADMINISTRATIVE_REVOCATION", "COMPROMISE_MARKING"})

_NONCE = re.compile(r"[0-9a-f]{32}\Z")  # 128-bit, lowercase hex

# The issuance scope under current source: `signingDomain` + `evidenceType`.
# `AuthorityKeyRecordV1` has no `authorityDomain`; that field is the logical
# context on evidence contracts only.
ISSUANCE_SCOPES = frozenset((domain, evidence_type)
                            for domain, types in A.EVIDENCE_TYPES_BY_DOMAIN.items() for evidence_type in types)

# The keygen publication and signer HEALTH shapes (B1b-3d L2 §7, L1 core).
KEY_PUBLICATION_TYPE = "LILITH_AUTHORITY_KEY_PUBLICATION"
KEY_PUBLICATION_SCHEMA_VERSION = 1
HEALTH_CREDENTIAL_PRESENT = "CREDENTIAL_PRESENT_UNVERIFIED"


class _Reject(Exception):
    def __init__(self, reason: str, detail: str | None = None):
        super().__init__(reason)
        self.reason = reason
        self.detail = detail


def _require(condition: bool, reason: str, detail: str | None = None) -> None:
    if not condition:
        raise _Reject(reason, detail)


def _b64u_decode(value: Any, size: int) -> bytes:
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9_-]+", value):
        raise ContractViolation("INVALID_ENCODING")
    raw = base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))
    if len(raw) != size:
        raise ContractViolation("INVALID_ENCODING")
    return raw


def _verify(public_key: bytes, signature: bytes, message: bytes) -> bool:
    try:
        Ed25519PublicKey.from_public_bytes(public_key).verify(signature, message)
    except (InvalidSignature, ValueError):
        return False
    return True


def _epoch(value: Any) -> A.RecoveryEpochV1:
    return A.RecoveryEpochV1.from_dict(value)


# ---------------------------------------------------------- registry head ---

@dataclass(frozen=True)
class RegistryHeadV1:
    """One exact authority-registry generation: version plus digest."""

    version: int
    digest: str

    def to_dict(self) -> dict[str, Any]:
        return {"registryVersion": self.version, "registryDigest": self.digest}


def registry_digest(registry: Mapping[str, Any]) -> str:
    """The one canonical registry digest.

    `sha256(LILITH_AUTHORITY_REGISTRY_V1\\0 ‖ RFC 8785 JCS of every registry field
    except `signature`)`: exactly the bytes K-ROOT signs
    (`authority_contracts.registry_signing_bytes`). It covers the complete
    canonical registry content (protocol, schema, environment, version,
    epoch, policy, root key ID, issuedAt, every key record) and excludes only
    the signature and any transport representation. It equals the B1b-3a
    golden `registrySigningDigest`.
    """
    if not isinstance(registry, Mapping):
        raise ContractViolation("INVALID_REGISTRY")
    _exact(registry, A.REGISTRY_FIELDS)
    unsigned = {name: registry[name] for name in A.REGISTRY_SIGNED_FIELDS}
    return hashlib.sha256(A.registry_signing_bytes(unsigned)).hexdigest()


def registry_head(registry: Mapping[str, Any]) -> RegistryHeadV1:
    return RegistryHeadV1(A._int(registry["registryVersion"], "registry_version", 1), registry_digest(registry))


# ------------------------------------------------ single current key (RR-3) ---

def current_issuance_keys(registry: A.AuthorityRegistryV1) -> dict[tuple[str, str], tuple[str, ...]]:
    """Current issuance keys per `(signingDomain, evidenceType)`.

    A current issuance key is a record whose K-ROOT-signed lifecycle is current
    (`retiredAt` and `revokedAt` both null) in the registry's own recovery
    epoch. `notBefore` and `evidence.issuedAt` are never used to choose it: a
    lifecycle-current key counts even before its `notBefore`, so two keys can
    never be issuance-current during an overlap.
    """
    found: dict[tuple[str, str], list[str]] = {scope: [] for scope in ISSUANCE_SCOPES}
    for key_id, record in sorted(registry.keys.items()):
        if record.current and record.recovery_epoch == registry.recovery_epoch:
            for evidence_type in sorted(record.evidence_types):
                found[(record.signing_domain, evidence_type)].append(key_id)
    return {scope: tuple(ids) for scope, ids in found.items()}


def single_current_key_reason(registry: A.AuthorityRegistryV1) -> str | None:
    """`MULTIPLE_CURRENT_ISSUANCE_KEYS` when any scope has more than one."""
    if any(len(ids) > 1 for ids in current_issuance_keys(registry).values()):
        return "MULTIPLE_CURRENT_ISSUANCE_KEYS"
    return None


def select_current_issuance_key(registry: A.AuthorityRegistryV1, signing_domain: str,
                                evidence_type: str) -> A.AuthorityKeyRecordV1:
    """The single current issuance key for one scope, or a closed refusal."""
    if (signing_domain, evidence_type) not in ISSUANCE_SCOPES:
        raise ContractViolation("ISSUANCE_SCOPE_INVALID")
    ids = current_issuance_keys(registry)[(signing_domain, evidence_type)]
    if not ids:
        raise ContractViolation("NO_CURRENT_ISSUANCE_KEY")
    if len(ids) > 1:
        raise ContractViolation("MULTIPLE_CURRENT_ISSUANCE_KEYS")
    return registry.keys[ids[0]]


# ---------------------------------------------- registry succession (§10.1) ---

SUCCEEDS = "SUCCEEDS"
NOT_A_SUCCESSOR = "NOT_A_SUCCESSOR"

# Closed, ordered succession taxonomy.
SUCCESSION_REASONS = (
    "SUCCESSION_MALFORMED",
    "SUCCESSION_PREVIOUS_NOT_TRUSTED_HEAD",
    "SUCCESSION_ROOT_OR_ENVIRONMENT_CHANGED",
    "SUCCESSION_VERSION_REGRESSION",
    "SUCCESSION_SAME_VERSION_FORK",
    "SUCCESSION_NO_CHANGE",
    "SUCCESSION_VERSION_GAP",
    "SUCCESSION_TIME_REGRESSION",
    "SUCCESSION_EPOCH_INVALID",
    "SUCCESSION_RECORD_REMOVED",
    "SUCCESSION_RECORD_MUTATED",
    "SUCCESSION_LIFECYCLE_REOPENED",
    "SUCCESSION_LIFECYCLE_REWRITTEN",
    "SUCCESSION_COMPROMISE_CLEARED",
    "SUCCESSION_NEW_RECORD_VERSION",
    "SUCCESSION_CURRENT_KEY_SCOPE",
)

# Per-record fields that never change once published.
IMMUTABLE_RECORD_FIELDS = (
    "signingDomain", "evidenceTypes", "environment", "algorithm", "publicKey", "createdAt", "notBefore",
    "recoveryEpoch", "policyVersion", "registryVersion",
)


@dataclass(frozen=True)
class SuccessionResultV1:
    status: str
    reason: str | None = None
    detail: str | None = None

    @property
    def succeeds(self) -> bool:
        return self.status == SUCCEEDS


def _lifecycle_reason(before: Mapping[str, Any], after: Mapping[str, Any]) -> str | None:
    """Lifecycle facts are additive: null -> value once, then final. The only
    later change is escalation of ROUTINE/SUPERSEDED to COMPROMISED, with
    `revokedAt` unchanged and `compromisedSince` added (B1b-3a requires
    `compromisedSince <= revokedAt`)."""
    if before["retiredAt"] is not None and after["retiredAt"] is None:
        return "SUCCESSION_LIFECYCLE_REOPENED"
    if before["retiredAt"] is not None and after["retiredAt"] != before["retiredAt"]:
        return "SUCCESSION_LIFECYCLE_REWRITTEN"
    if before["revokedAt"] is None:
        return None
    if after["revokedAt"] is None:
        return "SUCCESSION_LIFECYCLE_REOPENED"
    if after["revokedAt"] != before["revokedAt"]:
        return "SUCCESSION_LIFECYCLE_REWRITTEN"
    if before["revocationReason"] == A.COMPROMISED:
        if after["revocationReason"] != A.COMPROMISED:
            return "SUCCESSION_COMPROMISE_CLEARED"
        if after["compromisedSince"] != before["compromisedSince"]:
            return "SUCCESSION_LIFECYCLE_REWRITTEN"
        return None
    if after["revocationReason"] != before["revocationReason"] and after["revocationReason"] != A.COMPROMISED:
        return "SUCCESSION_LIFECYCLE_REWRITTEN"
    return None


def verify_registry_succession(previous: Mapping[str, Any], following: Mapping[str, Any], *,
                               trusted_head: RegistryHeadV1 | None = None) -> SuccessionResultV1:
    """Is `following` an additive successor of `previous`?

    Both inputs must already be authenticated (signature verified under
    K-ROOT by the caller). `trusted_head`, when given, must name `previous`
    exactly; its trusted owner is the recovery witness (V2 head).

    Limit: this is a pure function over its inputs. It proves additive history
    between the two registries given; it does not by itself create durable
    fork or rollback protection. That depends on who supplies `previous`.
    """
    try:
        try:
            old = A.AuthorityRegistryV1.from_verified_dict(previous)
            new = A.AuthorityRegistryV1.from_verified_dict(following)
            old_head, new_head = registry_head(previous), registry_head(following)
        except (OwnerProofError, TypeError, KeyError, ValueError) as exc:
            raise _Reject("SUCCESSION_MALFORMED") from exc
        if trusted_head is not None:
            _require(isinstance(trusted_head, RegistryHeadV1) and trusted_head == old_head,
                     "SUCCESSION_PREVIOUS_NOT_TRUSTED_HEAD")
        _require(old.environment == new.environment and old.registry_root_key_id == new.registry_root_key_id,
                 "SUCCESSION_ROOT_OR_ENVIRONMENT_CHANGED")
        _require(new.registry_version >= old.registry_version, "SUCCESSION_VERSION_REGRESSION")
        if new.registry_version == old.registry_version:
            _require(new_head.digest == old_head.digest, "SUCCESSION_SAME_VERSION_FORK")
            raise _Reject("SUCCESSION_NO_CHANGE")
        _require(new.registry_version == old.registry_version + 1, "SUCCESSION_VERSION_GAP")
        _require(new.issued_at >= old.issued_at, "SUCCESSION_TIME_REGRESSION")
        order = R.compare_epochs(old.recovery_epoch, new.recovery_epoch)
        _require(order == R.EPOCH_EQUAL or (order == R.EPOCH_NEWER
                                            and new.recovery_epoch.counter == old.recovery_epoch.counter + 1),
                 "SUCCESSION_EPOCH_INVALID", order)
        before = {record["keyId"]: record for record in previous["keys"]}
        after = {record["keyId"]: record for record in following["keys"]}
        for key_id in sorted(before):
            _require(key_id in after, "SUCCESSION_RECORD_REMOVED", key_id)
            for name in IMMUTABLE_RECORD_FIELDS:
                _require(after[key_id][name] == before[key_id][name], "SUCCESSION_RECORD_MUTATED",
                         f"{key_id}.{name}")
            reason = _lifecycle_reason(before[key_id], after[key_id])
            _require(reason is None, reason or "", key_id)
        for key_id in sorted(set(after) - set(before)):
            _require(after[key_id]["registryVersion"] == new.registry_version, "SUCCESSION_NEW_RECORD_VERSION",
                     key_id)
        _require(single_current_key_reason(new) is None, "SUCCESSION_CURRENT_KEY_SCOPE")
    except _Reject as rejected:
        return SuccessionResultV1(NOT_A_SUCCESSOR, rejected.reason, rejected.detail)
    return SuccessionResultV1(SUCCEEDS)


# --------------------------------------------------- execution authorizations ---

AUTHORIZATION_COMMON_FIELDS = frozenset({
    "protocol", "schemaVersion", "authorizationId", "nonce", "environment", "reason", "registryRootKeyId",
    "issuedAt", "notAfter", "signature",
})
EPOCH_ADVANCE_AUTHORIZATION_FIELDS = AUTHORIZATION_COMMON_FIELDS | frozenset({
    "priorRecoveryEpoch", "successorRecoveryEpoch", "targetRegistryVersion", "targetRegistryDigest",
    "expectedPriorWitnessVersion", "expectedPriorWitnessDigest",
})
REGISTRY_HEAD_ADVANCE_AUTHORIZATION_FIELDS = AUTHORIZATION_COMMON_FIELDS | frozenset({
    "recoveryEpoch", "priorRegistryVersion", "priorRegistryDigest", "targetRegistryVersion", "targetRegistryDigest",
})


def _common(value: Mapping[str, Any], protocol: str, reasons: frozenset[str]) -> dict[str, Any]:
    if value.get("protocol") != protocol or type(value.get("schemaVersion")) is not int \
            or value["schemaVersion"] != AUTHORIZATION_SCHEMA_VERSION:
        raise ContractViolation("UNSUPPORTED_SCHEMA_VERSION")
    issued, not_after = _instant(value["issuedAt"]), _instant(value["notAfter"])
    if not_after <= issued:
        raise ContractViolation("INVALID_VALIDITY_WINDOW")
    return {
        "authorization_id": _id(value["authorizationId"], "authorization_id"),
        "nonce": _pattern(value["nonce"], _NONCE, "nonce"),
        "environment": _choice(value["environment"], DEPLOYMENT_ENVIRONMENTS, "environment"),
        "reason": _choice(value["reason"], reasons, "reason"),
        "registry_root_key_id": _id(value["registryRootKeyId"], "registry_root_key_id"),
        "issued_at": issued,
        "not_after": not_after,
    }


@dataclass(frozen=True)
class EpochAdvanceAuthorizationV1:
    """K-ROOT permission for exactly one recovery-epoch transition.

    It is authority for one transition only. It mutates nothing: the witness
    executes it (`authorization != execution`), and an independent verifier
    confirms the result (`execution != verification`).
    """

    authorization_id: str
    nonce: str
    environment: str
    reason: str
    registry_root_key_id: str
    issued_at: datetime
    not_after: datetime
    prior_recovery_epoch: A.RecoveryEpochV1
    successor_recovery_epoch: A.RecoveryEpochV1
    target: RegistryHeadV1
    expected_prior_witness_version: int
    expected_prior_witness_digest: str

    @classmethod
    def from_verified_dict(cls, value: Mapping[str, Any]) -> EpochAdvanceAuthorizationV1:
        _exact(value, EPOCH_ADVANCE_AUTHORIZATION_FIELDS)
        common = _common(value, EPOCH_ADVANCE_AUTHORIZATION_PROTOCOL, EPOCH_ADVANCE_REASONS)
        prior, successor = _epoch(value["priorRecoveryEpoch"]), _epoch(value["successorRecoveryEpoch"])
        order = R.compare_epochs(prior, successor)
        if order == R.EPOCH_FORKED:
            raise ContractViolation("EPOCH_FORKED")  # same counter, different random: never succession
        if order != R.EPOCH_NEWER or successor.counter != prior.counter + 1:
            raise ContractViolation("EPOCH_NOT_SUCCESSOR")
        if successor.random == prior.random:
            raise ContractViolation("EPOCH_RANDOM_REUSED")
        return cls(prior_recovery_epoch=prior, successor_recovery_epoch=successor,
                   target=RegistryHeadV1(A._int(value["targetRegistryVersion"], "target_registry_version", 2),
                                         _digest(value["targetRegistryDigest"], "target_registry_digest")),
                   expected_prior_witness_version=A._int(value["expectedPriorWitnessVersion"],
                                                         "expected_prior_witness_version", 1),
                   expected_prior_witness_digest=_digest(value["expectedPriorWitnessDigest"],
                                                         "expected_prior_witness_digest"),
                   **common)


@dataclass(frozen=True)
class RegistryHeadAdvanceAuthorizationV1:
    """K-ROOT permission to advance the witnessed registry head from one exact
    head to the next exact head inside the same recovery epoch. Single use."""

    authorization_id: str
    nonce: str
    environment: str
    reason: str
    registry_root_key_id: str
    issued_at: datetime
    not_after: datetime
    recovery_epoch: A.RecoveryEpochV1
    prior: RegistryHeadV1
    target: RegistryHeadV1

    @classmethod
    def from_verified_dict(cls, value: Mapping[str, Any]) -> RegistryHeadAdvanceAuthorizationV1:
        _exact(value, REGISTRY_HEAD_ADVANCE_AUTHORIZATION_FIELDS)
        common = _common(value, REGISTRY_HEAD_ADVANCE_AUTHORIZATION_PROTOCOL, HEAD_ADVANCE_REASONS)
        prior = RegistryHeadV1(A._int(value["priorRegistryVersion"], "prior_registry_version", 1),
                               _digest(value["priorRegistryDigest"], "prior_registry_digest"))
        target = RegistryHeadV1(A._int(value["targetRegistryVersion"], "target_registry_version", 1),
                                _digest(value["targetRegistryDigest"], "target_registry_digest"))
        if target.version == prior.version:
            raise ContractViolation("SAME_VERSION_ADVANCE")
        if target.version != prior.version + 1:
            raise ContractViolation("TARGET_NOT_CONTIGUOUS")
        if target.digest == prior.digest:
            raise ContractViolation("TARGET_DIGEST_EQUALS_PRIOR")
        return cls(recovery_epoch=_epoch(value["recoveryEpoch"]), prior=prior, target=target, **common)


def epoch_advance_authorization_signing_bytes(unsigned: Mapping[str, Any]) -> bytes:
    _exact(unsigned, EPOCH_ADVANCE_AUTHORIZATION_FIELDS - {"signature"})
    return EPOCH_ADVANCE_AUTHORIZATION_DOMAIN_SEPARATOR + _canonical(unsigned)


def registry_head_advance_authorization_signing_bytes(unsigned: Mapping[str, Any]) -> bytes:
    _exact(unsigned, REGISTRY_HEAD_ADVANCE_AUTHORIZATION_FIELDS - {"signature"})
    return REGISTRY_HEAD_ADVANCE_AUTHORIZATION_DOMAIN_SEPARATOR + _canonical(unsigned)


VERIFIED_AUTHORIZATION = "VERIFIED_AUTHORIZATION"
AUTHORIZATION_NOT_VERIFIED = "AUTHORIZATION_NOT_VERIFIED"

# Closed, ordered authorization verification taxonomy.
AUTHORIZATION_REASONS = (
    "MALFORMED_CONTEXT",
    "REGISTRY_ROOT_NOT_TEST_ONLY",
    "AUTHORIZATION_MISSING",
    "AUTHORIZATION_MALFORMED",
    "AUTHORIZATION_UNSIGNED",
    "AUTHORIZATION_ROOT_MISMATCH",
    "AUTHORIZATION_SIGNATURE_INVALID",
    "UNSUPPORTED_SCHEMA_VERSION",
    "AUTHORIZATION_INVALID",
    "AUTHORIZATION_ENVIRONMENT_MISMATCH",
)


@dataclass(frozen=True)
class AuthorizationResultV1:
    status: str
    reason: str | None = None
    detail: str | None = None
    authorization: Any = None

    @property
    def verified(self) -> bool:
        return self.status == VERIFIED_AUTHORIZATION


def _verify_authorization(value: Any, *, fields: frozenset[str], signing_bytes, parser,
                          registry_root: A.TrustedRegistryRootV1, environment: str) -> AuthorizationResultV1:
    try:
        _require(isinstance(registry_root, A.TrustedRegistryRootV1) and environment in DEPLOYMENT_ENVIRONMENTS,
                 "MALFORMED_CONTEXT")
        _require(registry_root.test_only, "REGISTRY_ROOT_NOT_TEST_ONLY")
        _require(value is not None, "AUTHORIZATION_MISSING")
        _require(isinstance(value, Mapping), "AUTHORIZATION_MALFORMED")
        _require(value.get("signature") is not None, "AUTHORIZATION_UNSIGNED")
        try:
            _exact(value, fields)
            signature = A._signature(value["signature"])
            message = signing_bytes({k: value[k] for k in fields - {"signature"}})
        except (OwnerProofError, TypeError, ValueError) as exc:
            raise _Reject("AUTHORIZATION_MALFORMED") from exc
        # The signature is verified before any content is trusted.
        _require(value["registryRootKeyId"] == registry_root.root_key_id, "AUTHORIZATION_ROOT_MISMATCH")
        _require(_verify(registry_root.public_key, signature, message), "AUTHORIZATION_SIGNATURE_INVALID")
        try:
            parsed = parser(value)
        except OwnerProofError as exc:
            if exc.code == "UNSUPPORTED_SCHEMA_VERSION":
                raise _Reject("UNSUPPORTED_SCHEMA_VERSION") from exc
            raise _Reject("AUTHORIZATION_INVALID", exc.code) from exc
        _require(parsed.environment == environment == registry_root.environment,
                 "AUTHORIZATION_ENVIRONMENT_MISMATCH")
    except _Reject as rejected:
        return AuthorizationResultV1(AUTHORIZATION_NOT_VERIFIED, rejected.reason, rejected.detail)
    return AuthorizationResultV1(VERIFIED_AUTHORIZATION, None, None, parsed)


def verify_epoch_advance_authorization(*, authorization: Mapping[str, Any] | None,
                                       registry_root: A.TrustedRegistryRootV1,
                                       environment: str) -> AuthorizationResultV1:
    return _verify_authorization(authorization, fields=EPOCH_ADVANCE_AUTHORIZATION_FIELDS,
                                 signing_bytes=epoch_advance_authorization_signing_bytes,
                                 parser=EpochAdvanceAuthorizationV1.from_verified_dict,
                                 registry_root=registry_root, environment=environment)


def verify_registry_head_advance_authorization(*, authorization: Mapping[str, Any] | None,
                                               registry_root: A.TrustedRegistryRootV1,
                                               environment: str) -> AuthorizationResultV1:
    return _verify_authorization(authorization, fields=REGISTRY_HEAD_ADVANCE_AUTHORIZATION_FIELDS,
                                 signing_bytes=registry_head_advance_authorization_signing_bytes,
                                 parser=RegistryHeadAdvanceAuthorizationV1.from_verified_dict,
                                 registry_root=registry_root, environment=environment)


# ------------------------------------------------------- RecoveryWitnessV2 ---

WITNESS_V2_FIELDS = frozenset({
    "protocol", "schemaVersion", "environment", "witnessVersion", "previousWitnessDigest",
    "currentRecoveryEpoch", "registryVersion", "registryDigest", "policyVersion", "ledgerSequence",
    "ledgerHead", "consumedAuthorizationId", "updatedAt", "witnessKeyId", "signature",
})
WITNESS_V2_SIGNED_FIELDS = WITNESS_V2_FIELDS - {"signature"}


@dataclass(frozen=True)
class RecoveryWitnessV2:
    """Freshness / rollback evidence for one environment. Never authority.

    Field mapping from V1 (semantics unchanged unless stated):

    - `ledgerSequence` / `ledgerHead`: unchanged names and meaning: the
      authority recovery ledger's journal length and hash-chain head (the
      B1b-3e design calls it the authority recovery ledger; V1 names kept);
    - `minimumRegistryVersion` (V1 floor) is replaced by the exact head
      `(registryVersion, registryDigest)`. The inherited floor rule is
      `trusted_minimum_registry_version = registryVersion`, and verification
      now also requires the digest (`minimum_registry_version` property);
    - `consumedAuthorizationId` (new): the K-ROOT authorization whose
      execution produced this witness, or null for a ledger-only advance and
      for the genesis witness.
    """

    environment: str
    witness_version: int
    previous_witness_digest: str | None
    current_recovery_epoch: A.RecoveryEpochV1
    registry_version: int
    registry_digest: str
    policy_version: str
    ledger_sequence: int
    ledger_head: str
    consumed_authorization_id: str | None
    updated_at: datetime
    witness_key_id: str
    digest: str

    @property
    def registry_head(self) -> RegistryHeadV1:
        return RegistryHeadV1(self.registry_version, self.registry_digest)

    @property
    def minimum_registry_version(self) -> int:
        return self.registry_version

    @property
    def ledger_epoch(self) -> str:
        return R.ledger_epoch_id(self.current_recovery_epoch, self.environment)

    @classmethod
    def from_verified_dict(cls, value: Mapping[str, Any]) -> RecoveryWitnessV2:
        _exact(value, WITNESS_V2_FIELDS)
        if value.get("protocol") != R.WITNESS_PROTOCOL or type(value.get("schemaVersion")) is not int \
                or value["schemaVersion"] != WITNESS_V2_SCHEMA_VERSION:
            raise ContractViolation("UNSUPPORTED_SCHEMA_VERSION")
        version = A._int(value["witnessVersion"], "witness_version", 1)
        previous, consumed = value["previousWitnessDigest"], value["consumedAuthorizationId"]
        if (version == 1) != (previous is None):
            raise ContractViolation("INVALID_WITNESS_CHAIN")
        if version == 1 and consumed is not None:
            raise ContractViolation("INVALID_WITNESS_CHAIN")
        return cls(
            _choice(value["environment"], DEPLOYMENT_ENVIRONMENTS, "environment"), version,
            None if previous is None else _digest(previous, "previous_witness_digest"),
            _epoch(value["currentRecoveryEpoch"]),
            A._int(value["registryVersion"], "registry_version", 1),
            _digest(value["registryDigest"], "registry_digest"),
            _id(value["policyVersion"], "policy_version"),
            A._int(value["ledgerSequence"], "ledger_sequence", 1),
            _digest(value["ledgerHead"], "ledger_head"),
            None if consumed is None else _id(consumed, "consumed_authorization_id"),
            _instant(value["updatedAt"]),
            _id(value["witnessKeyId"], "witness_key_id"),
            witness_v2_digest(value),
        )


def witness_v2_signing_bytes(unsigned: Mapping[str, Any]) -> bytes:
    _exact(unsigned, WITNESS_V2_SIGNED_FIELDS)
    return WITNESS_V2_DOMAIN_SEPARATOR + _canonical(unsigned)


def witness_v2_digest(witness: Mapping[str, Any]) -> str:
    """SHA-256 over the exact signed bytes; the next witness's `previousWitnessDigest`."""
    return hashlib.sha256(witness_v2_signing_bytes({k: witness[k] for k in WITNESS_V2_SIGNED_FIELDS})).hexdigest()


VERIFIED_WITNESS_V2 = "VERIFIED_WITNESS_V2"


@dataclass(frozen=True)
class WitnessV2ResultV1:
    status: str
    reason: str | None = None
    witness: RecoveryWitnessV2 | None = None

    @property
    def verified(self) -> bool:
        return self.status == VERIFIED_WITNESS_V2


def verify_recovery_witness_v2(*, anchor: R.TrustedWitnessAnchorV1, witness: Mapping[str, Any] | None,
                               environment: str, registry_root: A.TrustedRegistryRootV1,
                               authority_public_keys: frozenset[bytes] = frozenset()) -> WitnessV2ResultV1:
    """Verify one V2 witness document. Reasons are the V1 witness taxonomy
    (`recovery_contracts.WITNESS_REASONS`); `witness != authority` as in V1."""
    try:
        _require(isinstance(anchor, R.TrustedWitnessAnchorV1) and isinstance(registry_root, A.TrustedRegistryRootV1)
                 and environment in DEPLOYMENT_ENVIRONMENTS and isinstance(authority_public_keys, frozenset),
                 "MALFORMED_CONTEXT")
        _require(anchor.test_only, "WITNESS_ANCHOR_NOT_TEST_ONLY")
        _require(anchor.public_key != registry_root.public_key and anchor.public_key not in authority_public_keys,
                 "WITNESS_KEY_IS_AUTHORITY_KEY")
        _require(witness is not None, "WITNESS_MISSING")
        _require(isinstance(witness, Mapping), "WITNESS_MALFORMED")
        _require(witness.get("signature") is not None, "WITNESS_UNSIGNED")
        try:
            _exact(witness, WITNESS_V2_FIELDS)
            signature = A._signature(witness["signature"])
            message = witness_v2_signing_bytes({k: witness[k] for k in WITNESS_V2_SIGNED_FIELDS})
        except (OwnerProofError, TypeError, ValueError) as exc:
            raise _Reject("WITNESS_MALFORMED") from exc
        _require(witness["witnessKeyId"] == anchor.witness_key_id, "WITNESS_KEY_MISMATCH")
        _require(_verify(anchor.public_key, signature, message), "WITNESS_SIGNATURE_INVALID")
        try:
            parsed = RecoveryWitnessV2.from_verified_dict(witness)
        except OwnerProofError as exc:
            raise _Reject("UNSUPPORTED_SCHEMA_VERSION" if exc.code == "UNSUPPORTED_SCHEMA_VERSION"
                          else "WITNESS_MALFORMED") from exc
        _require(parsed.environment == environment == anchor.environment == registry_root.environment,
                 "WITNESS_ENVIRONMENT_MISMATCH")
    except _Reject as rejected:
        return WitnessV2ResultV1(R.WITNESS_NOT_VERIFIED, rejected.reason)
    return WitnessV2ResultV1(VERIFIED_WITNESS_V2, None, parsed)


# Closed, ordered V2 succession taxonomy (V1 reasons plus the head rules).
WITNESS_V2_SUCCESSION_REASONS = (
    "WITNESS_ENVIRONMENT_MISMATCH",
    "WITNESS_KEY_CHANGED",
    "WITNESS_VERSION_NOT_SUCCESSOR",
    "WITNESS_CHAIN_BROKEN",
    "WITNESS_EPOCH_REGRESSION",
    "WITNESS_EPOCH_NOT_SUCCESSOR",
    "WITNESS_REGISTRY_REGRESSION",
    "WITNESS_REGISTRY_FORK",
    "WITNESS_REGISTRY_GAP",
    "WITNESS_REGISTRY_NOT_ADVANCED_WITH_EPOCH",
    "WITNESS_POLICY_CHANGE_WITHOUT_REGISTRY",
    "WITNESS_TRANSITION_UNAUTHORIZED",
    "WITNESS_AUTHORIZATION_WITHOUT_TRANSITION",
    "WITNESS_LEDGER_REGRESSION",
    "WITNESS_TIME_REGRESSION",
)


def witness_v2_succession_reason(previous: RecoveryWitnessV2, following: RecoveryWitnessV2) -> str | None:
    """None when `following` is a valid monotonic successor of `previous`.

    Head rules: the registry head never regresses; the same version with a
    different digest is a fork; versions are contiguous (no gaps); an epoch
    advance always moves the head by exactly one. Every head or epoch change
    must name the authorization it consumed, and a ledger-only advance names
    none. Whether that authorization verifies is the executor's check.
    """
    if following.environment != previous.environment:
        return "WITNESS_ENVIRONMENT_MISMATCH"
    if following.witness_key_id != previous.witness_key_id:
        return "WITNESS_KEY_CHANGED"
    if following.witness_version != previous.witness_version + 1:
        return "WITNESS_VERSION_NOT_SUCCESSOR"
    if following.previous_witness_digest != previous.digest:
        return "WITNESS_CHAIN_BROKEN"
    order = R.compare_epochs(previous.current_recovery_epoch, following.current_recovery_epoch)
    if order in {R.EPOCH_OLDER, R.EPOCH_FORKED}:
        return "WITNESS_EPOCH_REGRESSION"
    advanced = order == R.EPOCH_NEWER
    if advanced and following.current_recovery_epoch.counter != previous.current_recovery_epoch.counter + 1:
        return "WITNESS_EPOCH_NOT_SUCCESSOR"
    if following.registry_version < previous.registry_version:
        return "WITNESS_REGISTRY_REGRESSION"
    if following.registry_version == previous.registry_version and following.registry_digest != previous.registry_digest:
        return "WITNESS_REGISTRY_FORK"
    if following.registry_version > previous.registry_version + 1:
        return "WITNESS_REGISTRY_GAP"
    head_changed = following.registry_version == previous.registry_version + 1
    if advanced and not head_changed:
        return "WITNESS_REGISTRY_NOT_ADVANCED_WITH_EPOCH"
    if following.policy_version != previous.policy_version and not head_changed:
        return "WITNESS_POLICY_CHANGE_WITHOUT_REGISTRY"
    transition = advanced or head_changed
    if transition and following.consumed_authorization_id is None:
        return "WITNESS_TRANSITION_UNAUTHORIZED"
    if not transition and following.consumed_authorization_id is not None:
        return "WITNESS_AUTHORIZATION_WITHOUT_TRANSITION"
    # Ledger rules unchanged from V1 (B1b-3c): within one epoch the journal only
    # grows; an epoch advance binds a different (post-journal) head.
    if advanced:
        if following.ledger_head == previous.ledger_head:
            return "WITNESS_LEDGER_REGRESSION"
    elif following.ledger_sequence < previous.ledger_sequence \
            or (following.ledger_sequence == previous.ledger_sequence
                and following.ledger_head != previous.ledger_head):
        return "WITNESS_LEDGER_REGRESSION"
    if following.updated_at < previous.updated_at:
        return "WITNESS_TIME_REGRESSION"
    return None


@dataclass(frozen=True)
class WitnessChainFactsV1:
    """What a verified, linear V2 chain establishes."""

    head: RecoveryWitnessV2
    witnesses: tuple[RecoveryWitnessV2, ...]
    consumed_authorization_ids: frozenset[str]
    seen_epoch_randoms: frozenset[str]

    def entry_consuming(self, authorization_id: str) -> tuple[RecoveryWitnessV2, RecoveryWitnessV2] | None:
        """(predecessor, successor) for the entry that consumed this ID."""
        for index, witness in enumerate(self.witnesses[1:], start=1):
            if witness.consumed_authorization_id == authorization_id:
                return self.witnesses[index - 1], witness
        return None


CHAIN_VERIFIED = "CHAIN_VERIFIED"
CHAIN_NOT_VERIFIED = "CHAIN_NOT_VERIFIED"
CHAIN_REASONS = ("CHAIN_EMPTY", "CHAIN_ENTRY_INVALID", "CHAIN_NOT_FROM_GENESIS", "CHAIN_SUCCESSION_INVALID",
                 "CHAIN_AUTHORIZATION_REPLAYED")


@dataclass(frozen=True)
class ChainResultV1:
    status: str
    reason: str | None = None
    detail: str | None = None
    facts: WitnessChainFactsV1 | None = None

    @property
    def verified(self) -> bool:
        return self.status == CHAIN_VERIFIED


def witness_v2_chain_facts(chain: Sequence[RecoveryWitnessV2]) -> ChainResultV1:
    """Linearity, succession and single use over already-verified witnesses."""
    try:
        _require(len(chain) > 0, "CHAIN_EMPTY")
        _require(chain[0].witness_version == 1, "CHAIN_NOT_FROM_GENESIS")
        consumed: set[str] = set()
        for previous, following in zip(chain, chain[1:]):
            reason = witness_v2_succession_reason(previous, following)
            _require(reason is None, "CHAIN_SUCCESSION_INVALID", reason)
            if following.consumed_authorization_id is not None:
                _require(following.consumed_authorization_id not in consumed, "CHAIN_AUTHORIZATION_REPLAYED",
                         following.consumed_authorization_id)
                consumed.add(following.consumed_authorization_id)
    except _Reject as rejected:
        return ChainResultV1(CHAIN_NOT_VERIFIED, rejected.reason, rejected.detail)
    return ChainResultV1(CHAIN_VERIFIED, facts=WitnessChainFactsV1(
        chain[-1], tuple(chain), frozenset(consumed),
        frozenset(w.current_recovery_epoch.random for w in chain)))


def verify_witness_v2_chain(*, anchor: R.TrustedWitnessAnchorV1, chain: Sequence[Mapping[str, Any]],
                            environment: str, registry_root: A.TrustedRegistryRootV1,
                            authority_public_keys: frozenset[bytes] = frozenset()) -> ChainResultV1:
    """Verify every document from genesis, then the chain facts."""
    if not isinstance(chain, (list, tuple)) or not chain:
        return ChainResultV1(CHAIN_NOT_VERIFIED, "CHAIN_EMPTY")
    parsed = []
    for index, document in enumerate(chain):
        result = verify_recovery_witness_v2(anchor=anchor, witness=document, environment=environment,
                                            registry_root=registry_root, authority_public_keys=authority_public_keys)
        if not result.verified:
            return ChainResultV1(CHAIN_NOT_VERIFIED, "CHAIN_ENTRY_INVALID", f"{index}:{result.reason}")
        parsed.append(result.witness)
    return witness_v2_chain_facts(parsed)


def witness_v2_authority_context(witness: RecoveryWitnessV2, *, registry_root: A.TrustedRegistryRootV1,
                                 purpose: str) -> A.AuthorityVerificationContextV1:
    """The B1b-3a context with its trusted monotonic inputs taken from the V2
    witness only: the floor is the witnessed head version."""
    if not isinstance(witness, RecoveryWitnessV2):
        raise ContractViolation("INVALID_WITNESS")
    context = A.AuthorityVerificationContextV1(
        environment=witness.environment, purpose=purpose, registry_root=registry_root,
        trusted_minimum_registry_version=witness.registry_version,
        expected_recovery_epoch=witness.current_recovery_epoch, policy_version=witness.policy_version)
    context.validate()
    return context


VERIFIED_HEAD_REGISTRY = "VERIFIED_HEAD_REGISTRY"
HEAD_REGISTRY_REASONS = ("MALFORMED_INPUT", "REGISTRY_MISSING", "REGISTRY_DOWNGRADE", "REGISTRY_UNVERIFIED",
                         "REGISTRY_NOT_WITNESSED_HEAD", "REGISTRY_HEAD_DIGEST_MISMATCH")


@dataclass(frozen=True)
class HeadRegistryResultV1:
    status: str
    reason: str | None = None
    detail: str | None = None
    registry: A.AuthorityRegistryV1 | None = None

    @property
    def verified(self) -> bool:
        return self.status == VERIFIED_HEAD_REGISTRY


def verify_registry_at_witness_head(*, witness: RecoveryWitnessV2, registry: Mapping[str, Any] | None,
                                    registry_root: A.TrustedRegistryRootV1,
                                    purpose: str = A.NEW_ADMISSION) -> HeadRegistryResultV1:
    """Authority (K-ROOT signature) combined with freshness (the V2 head).

    A registry below the head is a downgrade; one above it is staged or
    abandoned (never current merely because it exists); one at the head
    version with another digest is a same-version fork.
    """
    try:
        _require(isinstance(witness, RecoveryWitnessV2) and isinstance(registry_root, A.TrustedRegistryRootV1),
                 "MALFORMED_INPUT")
        _require(registry is not None, "REGISTRY_MISSING")
        try:
            context = witness_v2_authority_context(witness, registry_root=registry_root, purpose=purpose)
        except OwnerProofError as exc:
            raise _Reject("MALFORMED_INPUT") from exc
        result = AV.verify_authority_registry(context=context, registry=registry)
        _require(result.verified or result.reason != "REGISTRY_DOWNGRADE", "REGISTRY_DOWNGRADE")
        _require(result.verified, "REGISTRY_UNVERIFIED", result.reason)
        head = registry_head(registry)
        _require(head.version == witness.registry_version, "REGISTRY_NOT_WITNESSED_HEAD")
        _require(head.digest == witness.registry_digest, "REGISTRY_HEAD_DIGEST_MISMATCH")
        parsed = A.AuthorityRegistryV1.from_verified_dict(registry)
    except _Reject as rejected:
        return HeadRegistryResultV1(AV.NOT_ACCEPTED, rejected.reason, rejected.detail)
    return HeadRegistryResultV1(VERIFIED_HEAD_REGISTRY, None, None, parsed)


# --------------------------------------------- witness execution validators ---

PLANNED = "PLANNED"
REFUSED = "REFUSED"

# Closed, ordered execution taxonomy (what the witness checks before it signs).
EXECUTION_REASONS = (
    "MALFORMED_INPUT",
    "AUTHORIZATION_NOT_VERIFIED",
    "PRIOR_WITNESS_MISMATCH",
    "PRIOR_EPOCH_MISMATCH",
    "PRIOR_HEAD_MISMATCH",
    "PRIOR_REGISTRY_NOT_HEAD",
    "AUTHORIZATION_EPOCH_MISMATCH",
    "TARGET_EPOCH_MISMATCH",
    "TARGET_REGISTRY_UNVERIFIED",
    "TARGET_REGISTRY_MISMATCH",
    "TARGET_NOT_CONTIGUOUS",
    "REGISTRY_SUCCESSION_INVALID",
    "TARGET_HAS_NO_ISSUANCE_KEY",
    "EPOCH_RANDOM_REUSED",
    "ADOPTION_RECORD_MISMATCH",
    "AUTHORIZATION_CONSUMED",
    "AUTHORIZATION_NOT_YET_VALID",
    "AUTHORIZATION_EXPIRED",
    "WITNESS_TIME_REGRESSION",
    "LEDGER_NOT_ADVANCING",
    "WITNESS_SUCCESSION_INVALID",
)


@dataclass(frozen=True)
class ExecutionPlanV1:
    """A planned witness successor (unsigned, without `witnessKeyId`). A plan
    is not execution; the witness signs it, and verification is separate."""

    status: str
    reason: str | None = None
    detail: str | None = None
    successor_unsigned: Mapping[str, Any] | None = None

    @property
    def planned(self) -> bool:
        return self.status == PLANNED


def _successor(witness: RecoveryWitnessV2, **changes: Any) -> dict[str, Any]:
    value = {
        "protocol": R.WITNESS_PROTOCOL,
        "schemaVersion": WITNESS_V2_SCHEMA_VERSION,
        "environment": witness.environment,
        "witnessVersion": witness.witness_version + 1,
        "previousWitnessDigest": witness.digest,
        "currentRecoveryEpoch": witness.current_recovery_epoch.to_dict(),
        "registryVersion": witness.registry_version,
        "registryDigest": witness.registry_digest,
        "policyVersion": witness.policy_version,
        "ledgerSequence": witness.ledger_sequence,
        "ledgerHead": witness.ledger_head,
        "consumedAuthorizationId": None,
    }
    value.update(changes)
    return value


def _parse_unsigned(witness: RecoveryWitnessV2, unsigned: Mapping[str, Any]) -> RecoveryWitnessV2:
    document = {**unsigned, "witnessKeyId": witness.witness_key_id, "signature": "unsigned-plan"}
    return RecoveryWitnessV2.from_verified_dict(document)


def _time_checks(authorization, witness: RecoveryWitnessV2, updated_at: datetime) -> None:
    # Clock expiry is defence in depth only; replay is prevented by the
    # prior-witness/prior-head binding, the linear chain, and consumed IDs.
    _require(updated_at >= witness.updated_at, "WITNESS_TIME_REGRESSION")
    _require(updated_at >= authorization.issued_at, "AUTHORIZATION_NOT_YET_VALID")
    _require(updated_at <= authorization.not_after, "AUTHORIZATION_EXPIRED")


def _verify_target(target_registry: Any, *, witness: RecoveryWitnessV2, registry_root, epoch, floor: int):
    _require(isinstance(target_registry, Mapping) and isinstance(target_registry.get("policyVersion"), str),
             "MALFORMED_INPUT")
    try:
        context = A.AuthorityVerificationContextV1(
            environment=witness.environment, purpose=A.NEW_ADMISSION, registry_root=registry_root,
            trusted_minimum_registry_version=floor, expected_recovery_epoch=epoch,
            policy_version=target_registry["policyVersion"])
        context.validate()
    except (OwnerProofError, TypeError, ValueError) as exc:
        raise _Reject("MALFORMED_INPUT") from exc
    result = AV.verify_authority_registry(context=context, registry=target_registry)
    _require(result.verified or result.reason != "REGISTRY_EPOCH_MISMATCH", "TARGET_EPOCH_MISMATCH")
    _require(result.verified, "TARGET_REGISTRY_UNVERIFIED", result.reason)
    return A.AuthorityRegistryV1.from_verified_dict(target_registry)


def _prior_registry(prior_registry: Any, witness: RecoveryWitnessV2) -> None:
    _require(isinstance(prior_registry, Mapping), "MALFORMED_INPUT")
    try:
        head = registry_head(prior_registry)
    except (OwnerProofError, TypeError, KeyError) as exc:
        raise _Reject("MALFORMED_INPUT") from exc
    _require(head == witness.registry_head, "PRIOR_REGISTRY_NOT_HEAD")


def plan_registry_head_advance(*, chain: WitnessChainFactsV1, authorization: Mapping[str, Any] | None,
                               registry_root: A.TrustedRegistryRootV1, prior_registry: Mapping[str, Any] | None,
                               target_registry: Mapping[str, Any] | None, updated_at: str) -> ExecutionPlanV1:
    """RR-15: plan the witness successor for one in-epoch head advance.

    Refuses unless: the authorization verifies under K-ROOT; the witness's
    current head equals the authorized prior head exactly; the target registry
    verifies under K-ROOT in the witness's current epoch; its version and
    digest equal the authorization; it is contiguous and an additive
    successor of the head registry; the authorization ID is unconsumed; and
    the clock window holds (defence in depth only).
    """
    try:
        _require(isinstance(chain, WitnessChainFactsV1), "MALFORMED_INPUT")
        witness = chain.head
        try:
            now = _instant(updated_at)
        except OwnerProofError as exc:
            raise _Reject("MALFORMED_INPUT") from exc
        checked = verify_registry_head_advance_authorization(authorization=authorization, registry_root=registry_root,
                                                             environment=witness.environment)
        _require(checked.verified, "AUTHORIZATION_NOT_VERIFIED", checked.reason)
        auth: RegistryHeadAdvanceAuthorizationV1 = checked.authorization
        _require(auth.prior == witness.registry_head, "PRIOR_HEAD_MISMATCH")
        _prior_registry(prior_registry, witness)
        _require(auth.recovery_epoch == witness.current_recovery_epoch, "AUTHORIZATION_EPOCH_MISMATCH")
        target = _verify_target(target_registry, witness=witness, registry_root=registry_root,
                                epoch=witness.current_recovery_epoch, floor=witness.registry_version)
        head = registry_head(target_registry)
        _require(head == auth.target, "TARGET_REGISTRY_MISMATCH")
        _require(head.version == witness.registry_version + 1, "TARGET_NOT_CONTIGUOUS")
        succession = verify_registry_succession(prior_registry, target_registry, trusted_head=witness.registry_head)
        _require(succession.succeeds, "REGISTRY_SUCCESSION_INVALID", succession.reason)
        _require(auth.authorization_id not in chain.consumed_authorization_ids, "AUTHORIZATION_CONSUMED")
        _time_checks(auth, witness, now)
        unsigned = _successor(witness, registryVersion=head.version, registryDigest=head.digest,
                              policyVersion=target.policy_version, consumedAuthorizationId=auth.authorization_id,
                              updatedAt=updated_at)
        _require(witness_v2_succession_reason(witness, _parse_unsigned(witness, unsigned)) is None,
                 "WITNESS_SUCCESSION_INVALID")
    except _Reject as rejected:
        return ExecutionPlanV1(REFUSED, rejected.reason, rejected.detail)
    return ExecutionPlanV1(PLANNED, successor_unsigned=unsigned)


def plan_epoch_advance(*, chain: WitnessChainFactsV1, authorization: Mapping[str, Any] | None,
                       registry_root: A.TrustedRegistryRootV1, prior_registry: Mapping[str, Any] | None,
                       target_registry: Mapping[str, Any] | None, adoption_record: Mapping[str, Any] | None,
                       ledger_sequence: int, ledger_head: str, updated_at: str) -> ExecutionPlanV1:
    """RR-2 under C-4: plan the witness successor for one epoch advance.

    The authority recovery ledger must already have journalled the adoption
    record (`ADVANCE_EPOCH` naming this authorization and successor epoch);
    the witness then binds the post-journal `ledgerSequence`/`ledgerHead`.
    """
    try:
        _require(isinstance(chain, WitnessChainFactsV1), "MALFORMED_INPUT")
        witness = chain.head
        try:
            now = _instant(updated_at)
            A._int(ledger_sequence, "ledger_sequence", 1)
            _digest(ledger_head, "ledger_head")
        except OwnerProofError as exc:
            raise _Reject("MALFORMED_INPUT") from exc
        checked = verify_epoch_advance_authorization(authorization=authorization, registry_root=registry_root,
                                                     environment=witness.environment)
        _require(checked.verified, "AUTHORIZATION_NOT_VERIFIED", checked.reason)
        auth: EpochAdvanceAuthorizationV1 = checked.authorization
        _require(auth.expected_prior_witness_digest == witness.digest
                 and auth.expected_prior_witness_version == witness.witness_version, "PRIOR_WITNESS_MISMATCH")
        _require(auth.prior_recovery_epoch == witness.current_recovery_epoch, "PRIOR_EPOCH_MISMATCH")
        _prior_registry(prior_registry, witness)
        _require(auth.successor_recovery_epoch.random not in chain.seen_epoch_randoms, "EPOCH_RANDOM_REUSED")
        target = _verify_target(target_registry, witness=witness, registry_root=registry_root,
                                epoch=auth.successor_recovery_epoch, floor=witness.registry_version + 1)
        head = registry_head(target_registry)
        _require(head == auth.target, "TARGET_REGISTRY_MISMATCH")
        _require(head.version == witness.registry_version + 1, "TARGET_NOT_CONTIGUOUS")
        succession = verify_registry_succession(prior_registry, target_registry, trusted_head=witness.registry_head)
        _require(succession.succeeds, "REGISTRY_SUCCESSION_INVALID", succession.reason)
        _require(any(ids for ids in current_issuance_keys(target).values()), "TARGET_HAS_NO_ISSUANCE_KEY")
        record = adoption_record
        _require(isinstance(record, Mapping) and record.get("op") == "ADVANCE_EPOCH"
                 and record.get("authorizationId") == auth.authorization_id
                 and record.get("newEpoch") == auth.successor_recovery_epoch.to_dict()
                 and record.get("fromWitnessDigest") == witness.digest
                 and record.get("registryVersion") == head.version, "ADOPTION_RECORD_MISMATCH")
        _require(ledger_head != witness.ledger_head, "LEDGER_NOT_ADVANCING")
        _require(auth.authorization_id not in chain.consumed_authorization_ids, "AUTHORIZATION_CONSUMED")
        _time_checks(auth, witness, now)
        unsigned = _successor(witness, currentRecoveryEpoch=auth.successor_recovery_epoch.to_dict(),
                              registryVersion=head.version, registryDigest=head.digest,
                              policyVersion=target.policy_version, ledgerSequence=ledger_sequence,
                              ledgerHead=ledger_head, consumedAuthorizationId=auth.authorization_id,
                              updatedAt=updated_at)
        reason = witness_v2_succession_reason(witness, _parse_unsigned(witness, unsigned))
        _require(reason is None, "WITNESS_SUCCESSION_INVALID", reason)
    except _Reject as rejected:
        return ExecutionPlanV1(REFUSED, rejected.reason, rejected.detail)
    return ExecutionPlanV1(PLANNED, successor_unsigned=unsigned)


def plan_ledger_advance(*, chain: WitnessChainFactsV1, ledger_sequence: int, ledger_head: str,
                        updated_at: str) -> ExecutionPlanV1:
    """Record an authority recovery ledger advance inside the current epoch
    and head. It needs no authorization and can change nothing else."""
    try:
        _require(isinstance(chain, WitnessChainFactsV1), "MALFORMED_INPUT")
        witness = chain.head
        try:
            now = _instant(updated_at)
            A._int(ledger_sequence, "ledger_sequence", 1)
            _digest(ledger_head, "ledger_head")
        except OwnerProofError as exc:
            raise _Reject("MALFORMED_INPUT") from exc
        _require(ledger_sequence > witness.ledger_sequence, "LEDGER_NOT_ADVANCING")
        _require(now >= witness.updated_at, "WITNESS_TIME_REGRESSION")
        unsigned = _successor(witness, ledgerSequence=ledger_sequence, ledgerHead=ledger_head, updatedAt=updated_at)
        reason = witness_v2_succession_reason(witness, _parse_unsigned(witness, unsigned))
        _require(reason is None, "WITNESS_SUCCESSION_INVALID", reason)
    except _Reject as rejected:
        return ExecutionPlanV1(REFUSED, rejected.reason, rejected.detail)
    return ExecutionPlanV1(PLANNED, successor_unsigned=unsigned)


def plan_witness_v2_genesis(*, environment: str, registry: Mapping[str, Any] | None,
                            registry_root: A.TrustedRegistryRootV1, ledger_sequence: int, ledger_head: str,
                            updated_at: str) -> ExecutionPlanV1:
    """The V2 genesis witness: the head is a registry that verifies under
    K-ROOT at its own epoch and satisfies the single-current-key rule."""
    try:
        _require(isinstance(registry, Mapping) and isinstance(registry.get("policyVersion"), str)
                 and isinstance(registry.get("recoveryEpoch"), Mapping), "MALFORMED_INPUT")
        try:
            epoch = _epoch(registry["recoveryEpoch"])
            head = registry_head(registry)
            context = A.AuthorityVerificationContextV1(
                environment=environment, purpose=A.NEW_ADMISSION, registry_root=registry_root,
                trusted_minimum_registry_version=head.version, expected_recovery_epoch=epoch,
                policy_version=registry["policyVersion"])
            context.validate()
            A._int(ledger_sequence, "ledger_sequence", 1)
            _digest(ledger_head, "ledger_head")
            _instant(updated_at)
        except (OwnerProofError, TypeError, ValueError, KeyError) as exc:
            raise _Reject("MALFORMED_INPUT") from exc
        result = AV.verify_authority_registry(context=context, registry=registry)
        _require(result.verified, "TARGET_REGISTRY_UNVERIFIED", result.reason)
        parsed = A.AuthorityRegistryV1.from_verified_dict(registry)
        _require(single_current_key_reason(parsed) is None, "REGISTRY_SUCCESSION_INVALID",
                 "SUCCESSION_CURRENT_KEY_SCOPE")
        unsigned = {
            "protocol": R.WITNESS_PROTOCOL, "schemaVersion": WITNESS_V2_SCHEMA_VERSION, "environment": environment,
            "witnessVersion": 1, "previousWitnessDigest": None, "currentRecoveryEpoch": epoch.to_dict(),
            "registryVersion": head.version, "registryDigest": head.digest, "policyVersion": parsed.policy_version,
            "ledgerSequence": ledger_sequence, "ledgerHead": ledger_head, "consumedAuthorizationId": None,
            "updatedAt": updated_at,
        }
    except _Reject as rejected:
        return ExecutionPlanV1(REFUSED, rejected.reason, rejected.detail)
    return ExecutionPlanV1(PLANNED, successor_unsigned=unsigned)


# ---------------------------------------- authority recovery ledger position ---

@dataclass(frozen=True)
class AuthorityLedgerObservationV1:
    """Story 4: what the authority recovery ledger's journal says (built from
    a replay by the ledger's owner). Never authority; compared to freshness."""

    environment: str
    recovery_epoch: A.RecoveryEpochV1
    sequence: int
    head: str
    registry_view: int
    signing_key_ids: tuple[str, ...]
    rows_consistent: bool = True
    terminal_reopened: bool = False


LEDGER_POSITION_REASONS = (
    "MALFORMED_INPUT", "TERMINAL_STATE_REOPENED", "LEDGER_INTEGRITY_FAILED", "ENVIRONMENT_MISMATCH",
    "LEDGER_EPOCH_STALE", "LEDGER_EPOCH_FORKED", "LEDGER_EPOCH_AHEAD_OF_WITNESS", "LEDGER_BEHIND_WITNESS",
    "LEDGER_AHEAD_OF_WITNESS", "LEDGER_HEAD_MISMATCH", "BROKER_REGISTRY_VIEW_STALE",
)


def authority_ledger_position_reason(observation: AuthorityLedgerObservationV1,
                                     witness: RecoveryWitnessV2) -> str | None:
    """None when the observed ledger equals the surviving witness exactly.
    Names follow the B1b-3c readiness taxonomy."""
    if not isinstance(observation, AuthorityLedgerObservationV1) or not isinstance(witness, RecoveryWitnessV2):
        return "MALFORMED_INPUT"
    if observation.terminal_reopened:
        return "TERMINAL_STATE_REOPENED"
    if not observation.rows_consistent:
        return "LEDGER_INTEGRITY_FAILED"
    if observation.environment != witness.environment:
        return "ENVIRONMENT_MISMATCH"
    order = R.compare_epochs(witness.current_recovery_epoch, observation.recovery_epoch)
    if order != R.EPOCH_EQUAL:
        return {R.EPOCH_OLDER: "LEDGER_EPOCH_STALE", R.EPOCH_FORKED: "LEDGER_EPOCH_FORKED",
                R.EPOCH_NEWER: "LEDGER_EPOCH_AHEAD_OF_WITNESS"}[order]
    if observation.sequence < witness.ledger_sequence:
        return "LEDGER_BEHIND_WITNESS"
    if observation.sequence > witness.ledger_sequence:
        return "LEDGER_AHEAD_OF_WITNESS"
    if observation.head != witness.ledger_head:
        return "LEDGER_HEAD_MISMATCH"
    if observation.registry_view != witness.registry_version:
        return "BROKER_REGISTRY_VIEW_STALE"
    return None


# ---------------------------------------- loaded-key / current-key binding ---

BINDING_VERIFIED = "BINDING_VERIFIED"
BINDING_NOT_VERIFIED = "BINDING_NOT_VERIFIED"

# Closed, ordered binding taxonomy.
BINDING_REASONS = (
    "BINDING_INPUT_MISSING",
    "BINDING_INPUT_MALFORMED",
    "REGISTRY_NOT_AT_WITNESSED_HEAD",
    "ISSUANCE_SCOPE_INVALID",
    "NO_CURRENT_ISSUANCE_KEY",
    "MULTIPLE_CURRENT_ISSUANCE_KEYS",
    "PUBLICATION_FINGERPRINT_INVALID",
    "PUBLICATION_SCOPE_MISMATCH",
    "PUBLICATION_KEY_MISMATCH",
    "BLOB_HASH_MISMATCH",
    "HEALTH_CREDENTIAL_NOT_PRESENT",
    "HEALTH_SCOPE_MISMATCH",
    "HEALTH_FINGERPRINT_MISMATCH",
)

_PUBLICATION_FIELDS = frozenset({"publicationType", "schemaVersion", "profile", "publicVerificationMaterial",
                                 "custodyEvidence"})
_PUBLIC_MATERIAL_FIELDS = frozenset({"keyId", "signingDomain", "evidenceTypes", "environment", "algorithm",
                                     "publicKey", "publicKeySha256"})


@dataclass(frozen=True)
class KeyPublicationV1:
    """B3: the keygen ceremony's public output (B1b-3d L2 §7). Public only."""

    key_id: str
    signing_domain: str
    evidence_types: tuple[str, ...]
    environment: str
    public_key: bytes
    public_key_sha256: str
    blob_sha256: str

    @classmethod
    def from_dict(cls, value: Any) -> KeyPublicationV1:
        _exact(value, _PUBLICATION_FIELDS)
        if value["publicationType"] != KEY_PUBLICATION_TYPE or type(value["schemaVersion"]) is not int \
                or value["schemaVersion"] != KEY_PUBLICATION_SCHEMA_VERSION:
            raise ContractViolation("UNSUPPORTED_SCHEMA_VERSION")
        _id(value["profile"], "profile")
        material, custody = value["publicVerificationMaterial"], value["custodyEvidence"]
        _exact(material, _PUBLIC_MATERIAL_FIELDS)
        if not isinstance(custody, Mapping):
            raise ContractViolation("INVALID_CUSTODY_EVIDENCE")
        if material["algorithm"] != A.ALGORITHM:
            raise ContractViolation("UNSUPPORTED_ALGORITHM")
        types = material["evidenceTypes"]
        if not isinstance(types, list) or not types or not all(isinstance(t, str) for t in types):
            raise ContractViolation("INVALID_EVIDENCE_TYPES")
        return cls(_id(material["keyId"], "key_id"),
                   _choice(material["signingDomain"], A.SIGNING_DOMAINS, "signing_domain"),
                   tuple(types), _choice(material["environment"], DEPLOYMENT_ENVIRONMENTS, "environment"),
                   _b64u_decode(material["publicKey"], 32),
                   _digest(material["publicKeySha256"], "public_key_sha256"),
                   _digest(custody.get("blobSha256"), "blob_sha256"))


@dataclass(frozen=True)
class BindingResultV1:
    status: str
    reason: str | None = None
    detail: str | None = None
    facts: Mapping[str, Any] = field(default_factory=dict)

    @property
    def verified(self) -> bool:
        return self.status == BINDING_VERIFIED


def verify_loaded_key_binding(*, registry_root: A.TrustedRegistryRootV1, witness: RecoveryWitnessV2 | None,
                              head_registry: Mapping[str, Any] | None, signing_domain: str, evidence_type: str,
                              observed_blob_sha256: str | None, publication: Mapping[str, Any] | None,
                              health: Mapping[str, Any] | None) -> BindingResultV1:
    """RR-14: is the key the signer actually loaded the single current key?

    - B1: the single current issuance key of the K-ROOT registry at the fresh
      witnessed head (`head_registry` + `witness`), reproduced here;
    - B2: `observed_blob_sha256`, root-observed hash of the unit-slot blob
      (no decryption);
    - B3: `publication`, the keygen ceremony's public output;
    - B4: `health`, the signer HEALTH report. Its `publicKeySha256` is derived
      by the signer at runtime from the loaded private material, but it is
      still a signer claim: B2 + B3 carry the independent ceremony binding.

    A positive result grants nothing. It is one input to `S_CURRENT`.
    Proof-of-possession beyond this is RR-14a (deferred).
    """
    try:
        for name, value in (("B1_WITNESS", witness), ("B1_REGISTRY", head_registry),
                            ("B2_BLOB_HASH", observed_blob_sha256), ("B3_PUBLICATION", publication),
                            ("B4_HEALTH", health)):
            _require(value is not None, "BINDING_INPUT_MISSING", name)
        try:
            _digest(observed_blob_sha256, "observed_blob_sha256")
            published = KeyPublicationV1.from_dict(publication)
            _require(isinstance(health, Mapping), "BINDING_INPUT_MALFORMED", "B4_HEALTH")
            reported = health.get("publicKeySha256")
        except (OwnerProofError, TypeError, ValueError) as exc:
            raise _Reject("BINDING_INPUT_MALFORMED", getattr(exc, "code", "INVALID_ENCODING")) from exc
        at_head = verify_registry_at_witness_head(witness=witness, registry=head_registry,
                                                  registry_root=registry_root)
        _require(at_head.verified, "REGISTRY_NOT_AT_WITNESSED_HEAD", at_head.reason)
        try:
            current = select_current_issuance_key(at_head.registry, signing_domain, evidence_type)
        except OwnerProofError as exc:
            raise _Reject(exc.code) from exc
        _require(hashlib.sha256(published.public_key).hexdigest() == published.public_key_sha256,
                 "PUBLICATION_FINGERPRINT_INVALID")
        _require(published.key_id == current.key_id and published.signing_domain == current.signing_domain
                 and tuple(sorted(current.evidence_types)) == tuple(sorted(published.evidence_types))
                 and published.environment == current.environment == at_head.registry.environment,
                 "PUBLICATION_SCOPE_MISMATCH")
        _require(published.public_key == current.public_key, "PUBLICATION_KEY_MISMATCH")
        _require(observed_blob_sha256 == published.blob_sha256, "BLOB_HASH_MISMATCH")
        _require(health.get("credential") == HEALTH_CREDENTIAL_PRESENT, "HEALTH_CREDENTIAL_NOT_PRESENT")
        _require(health.get("signingDomain") == signing_domain, "HEALTH_SCOPE_MISMATCH")
        _require(reported == published.public_key_sha256, "HEALTH_FINGERPRINT_MISMATCH")
    except _Reject as rejected:
        return BindingResultV1(BINDING_NOT_VERIFIED, rejected.reason, rejected.detail)
    return BindingResultV1(BINDING_VERIFIED, facts={
        "keyId": current.key_id,
        "signingDomain": signing_domain,
        "evidenceType": evidence_type,
        "publicKeySha256": published.public_key_sha256,
        "registryHead": witness.registry_head.to_dict(),
        "independentInputs": ["B1", "B2", "B3"],
        "signerClaim": "B4",
        "proofOfPossession": "NOT_PERFORMED_RR14A_DEFERRED",
        "authorityGranted": False,
    })


# ------------------------------------------------- rotation state machine ---

P_ACTIVE = "P_ACTIVE"
S_PROPOSED = "S_PROPOSED"
S_PREPARED = "S_PREPARED"
S_AUTHORIZED = "S_AUTHORIZED"
S_PUBLISHED = "S_PUBLISHED"
S_ACTIVATED = "S_ACTIVATED"
S_CURRENT = "S_CURRENT"
ROTATION_STATES = (P_ACTIVE, S_PROPOSED, S_PREPARED, S_AUTHORIZED, S_PUBLISHED, S_ACTIVATED, S_CURRENT)
# The predecessor's end state. The merged design names it P_SUPERSEDED
# (`revocationReason = SUPERSEDED`); it is reached only together with S_CURRENT.
P_SUPERSEDED = "P_SUPERSEDED"
NOT_EVALUABLE = "NOT_EVALUABLE"

# Forward edges are single steps. Aborts return to P_ACTIVE only before the
# witness executed the head advance; S_PUBLISHED onwards is forward only.
ALLOWED_TRANSITIONS = {
    P_ACTIVE: frozenset({S_PROPOSED}),
    S_PROPOSED: frozenset({S_PREPARED, P_ACTIVE}),
    S_PREPARED: frozenset({S_AUTHORIZED, P_ACTIVE}),
    S_AUTHORIZED: frozenset({S_PUBLISHED, P_ACTIVE}),
    S_PUBLISHED: frozenset({S_ACTIVATED}),
    S_ACTIVATED: frozenset({S_CURRENT}),
    S_CURRENT: frozenset(),
}

ROTATION_REASONS = (
    "MALFORMED_EVIDENCE",
    "WITNESS_CHAIN_NOT_VERIFIED",
    "PRIOR_REGISTRY_NOT_WITNESSED",
    "PREDECESSOR_NOT_SINGLE_CURRENT",
    "OWNER_INTENT_ABSENT",
    "SUCCESSOR_PUBLICATION_INVALID",
    "CANDIDATE_REGISTRY_MISSING",
    "CANDIDATE_REGISTRY_UNVERIFIED",
    "CANDIDATE_NOT_CONTIGUOUS",
    "CANDIDATE_SUCCESSION_INVALID",
    "CANDIDATE_SUCCESSOR_NOT_SINGLE_CURRENT",
    "CANDIDATE_SUCCESSOR_KEY_MISMATCH",
    "CANDIDATE_PREDECESSOR_NOT_SUPERSEDED",
    "HEAD_AUTHORIZATION_MISSING",
    "HEAD_AUTHORIZATION_UNVERIFIED",
    "HEAD_AUTHORIZATION_NOT_FOR_TRANSITION",
    "HEAD_AUTHORIZATION_CONSUMED_ELSEWHERE",
    "HEAD_NOT_ADVANCED",
    "HEAD_ADVANCED_ELSEWHERE",
    "SIGNER_HEALTH_ABSENT",
    "SIGNER_NOT_REPORTING_SUCCESSOR",
    "LEDGER_OBSERVATION_ABSENT",
    "LEDGER_NOT_OBSERVING_SUCCESSOR",
    "HEAD_REGISTRY_NOT_VERIFIED",
    "SINGLE_CURRENT_KEY_FAILED",
    "LEDGER_POSITION_NOT_WITNESSED",
    "LOADED_KEY_BINDING_FAILED",
    "LOCAL_HOLD_PRESENT",
)


@dataclass(frozen=True)
class RotationEvidenceV1:
    """Everything a verifier may consider for one predecessor -> successor
    rotation. Every item is story-4 material until a check here verifies it."""

    environment: str
    signing_domain: str
    evidence_type: str
    predecessor_key_id: str
    successor_key_id: str
    registry_root: A.TrustedRegistryRootV1
    witness_anchor: R.TrustedWitnessAnchorV1
    witness_chain: tuple[Mapping[str, Any], ...]
    prior_registry: Mapping[str, Any] | None
    owner_intent_recorded: bool = False
    hold_present: bool = False
    successor_publication: Mapping[str, Any] | None = None
    candidate_registry: Mapping[str, Any] | None = None
    head_authorization: Mapping[str, Any] | None = None
    signer_health: Mapping[str, Any] | None = None
    ledger_observation: AuthorityLedgerObservationV1 | None = None
    observed_blob_sha256: str | None = None


@dataclass(frozen=True)
class RotationAssessmentV1:
    """The highest rotation state the evidence independently supports, and
    why the next one is not reached. Only S_CURRENT permits issuance."""

    state: str
    blocked_reason: str | None
    detail: str | None
    facts: Mapping[str, Any]

    @property
    def issuance_ready(self) -> bool:
        return self.state == S_CURRENT


class _Stop(Exception):
    def __init__(self, reason: str, detail: str | None = None):
        super().__init__(reason)
        self.reason = reason
        self.detail = detail


def _stop_unless(condition: bool, reason: str, detail: str | None = None) -> None:
    if not condition:
        raise _Stop(reason, detail)


def _authority_keys(*registries: Any) -> frozenset[bytes]:
    keys: set[bytes] = set()
    for registry in registries:
        if isinstance(registry, Mapping) and isinstance(registry.get("keys"), list):
            for record in registry["keys"]:
                try:
                    keys.add(A._public_key(record["publicKey"]))
                except (OwnerProofError, KeyError, TypeError):
                    continue
    return frozenset(keys)


def evaluate_rotation(evidence: RotationEvidenceV1) -> RotationAssessmentV1:
    """Pure, fail-closed evaluation of one rotation (§7.4 of the design).

    Each state requires every earlier one:

    - P_ACTIVE: the prior registry was a witnessed head and names the
      predecessor as the single current issuance key;
    - S_PROPOSED: owner intent is recorded (not authority);
    - S_PREPARED: the successor publication is valid (still cannot issue);
    - S_AUTHORIZED: (A) a K-ROOT-signed candidate registry, contiguous and an
      additive successor, with the successor as the single current key and
      the predecessor SUPERSEDED; and (B) an exact, verified
      `RegistryHeadAdvanceAuthorizationV1` from the prior head to it. Neither
      implies witness execution;
    - S_PUBLISHED: the witness executed that authorization and its current
      head is exactly the candidate. Not issuance readiness;
    - S_ACTIVATED: the signer reports the successor fingerprint and the
      authority recovery ledger observes the new head (claims only);
    - S_CURRENT: the head registry verifies under K-ROOT at the fresh V2
      head, the single-current rule selects the successor, the ledger
      position equals the witness, the loaded-key binding reproduces
      independently, and the local hold is released.
    """
    state = NOT_EVALUABLE
    facts: dict[str, Any] = {"issuanceReady": False, "authorityGranted": False,
                             "predecessorState": None, "rollbackDetectionScope": R.ROLLBACK_DETECTION_SCOPE,
                             "wholeHostRollbackProtected": R.WHOLE_HOST_ROLLBACK_PROTECTED}
    try:
        _stop_unless(isinstance(evidence, RotationEvidenceV1)
                     and (evidence.signing_domain, evidence.evidence_type) in ISSUANCE_SCOPES
                     and evidence.predecessor_key_id != evidence.successor_key_id, "MALFORMED_EVIDENCE")
        e = evidence
        publics = _authority_keys(e.prior_registry, e.candidate_registry)
        chain_result = verify_witness_v2_chain(anchor=e.witness_anchor, chain=list(e.witness_chain),
                                               environment=e.environment, registry_root=e.registry_root,
                                               authority_public_keys=publics)
        _stop_unless(chain_result.verified, "WITNESS_CHAIN_NOT_VERIFIED",
                     chain_result.detail or chain_result.reason)
        chain = chain_result.facts
        head = chain.head
        facts["witnessedHead"] = head.registry_head.to_dict()

        # P_ACTIVE ----------------------------------------------------------
        _stop_unless(isinstance(e.prior_registry, Mapping), "PRIOR_REGISTRY_NOT_WITNESSED")
        try:
            prior_head = registry_head(e.prior_registry)
        except (OwnerProofError, TypeError, KeyError) as exc:
            raise _Stop("PRIOR_REGISTRY_NOT_WITNESSED") from exc
        witnessed = [w for w in chain.witnesses if w.registry_head == prior_head]
        _stop_unless(bool(witnessed), "PRIOR_REGISTRY_NOT_WITNESSED")
        prior_check = verify_registry_at_witness_head(witness=witnessed[-1], registry=e.prior_registry,
                                                      registry_root=e.registry_root)
        _stop_unless(prior_check.verified, "PRIOR_REGISTRY_NOT_WITNESSED", prior_check.reason)
        try:
            prior_key = select_current_issuance_key(prior_check.registry, e.signing_domain, e.evidence_type)
        except OwnerProofError as exc:
            raise _Stop("PREDECESSOR_NOT_SINGLE_CURRENT", exc.code) from exc
        _stop_unless(prior_key.key_id == e.predecessor_key_id, "PREDECESSOR_NOT_SINGLE_CURRENT")
        state = P_ACTIVE
        facts["predecessorState"] = P_ACTIVE

        # S_PROPOSED --------------------------------------------------------
        _stop_unless(e.owner_intent_recorded, "OWNER_INTENT_ABSENT")
        state = S_PROPOSED

        # S_PREPARED --------------------------------------------------------
        try:
            publication = KeyPublicationV1.from_dict(e.successor_publication)
        except (OwnerProofError, TypeError, ValueError) as exc:
            raise _Stop("SUCCESSOR_PUBLICATION_INVALID") from exc
        _stop_unless(publication.key_id == e.successor_key_id and publication.environment == e.environment
                     and publication.signing_domain == e.signing_domain
                     and e.evidence_type in publication.evidence_types
                     and hashlib.sha256(publication.public_key).hexdigest() == publication.public_key_sha256,
                     "SUCCESSOR_PUBLICATION_INVALID")
        state = S_PREPARED

        # S_AUTHORIZED: (A) successor/key authorization --------------------
        _stop_unless(isinstance(e.candidate_registry, Mapping), "CANDIDATE_REGISTRY_MISSING")
        try:
            candidate_head = registry_head(e.candidate_registry)
            policy = e.candidate_registry["policyVersion"]
            context = A.AuthorityVerificationContextV1(
                environment=e.environment, purpose=A.NEW_ADMISSION, registry_root=e.registry_root,
                trusted_minimum_registry_version=prior_head.version,
                expected_recovery_epoch=prior_check.registry.recovery_epoch, policy_version=policy)
            context.validate()
        except (OwnerProofError, TypeError, KeyError, ValueError) as exc:
            raise _Stop("CANDIDATE_REGISTRY_UNVERIFIED") from exc
        candidate_result = AV.verify_authority_registry(context=context, registry=e.candidate_registry)
        _stop_unless(candidate_result.verified, "CANDIDATE_REGISTRY_UNVERIFIED", candidate_result.reason)
        _stop_unless(candidate_head.version == prior_head.version + 1, "CANDIDATE_NOT_CONTIGUOUS")
        succession = verify_registry_succession(e.prior_registry, e.candidate_registry, trusted_head=prior_head)
        _stop_unless(succession.succeeds, "CANDIDATE_SUCCESSION_INVALID", succession.reason)
        candidate = A.AuthorityRegistryV1.from_verified_dict(e.candidate_registry)
        try:
            successor_key = select_current_issuance_key(candidate, e.signing_domain, e.evidence_type)
        except OwnerProofError as exc:
            raise _Stop("CANDIDATE_SUCCESSOR_NOT_SINGLE_CURRENT", exc.code) from exc
        _stop_unless(successor_key.key_id == e.successor_key_id, "CANDIDATE_SUCCESSOR_NOT_SINGLE_CURRENT")
        _stop_unless(successor_key.public_key == publication.public_key, "CANDIDATE_SUCCESSOR_KEY_MISMATCH")
        predecessor_after = candidate.keys.get(e.predecessor_key_id)
        _stop_unless(predecessor_after is not None and predecessor_after.revoked_at is not None
                     and predecessor_after.revocation_reason == "SUPERSEDED", "CANDIDATE_PREDECESSOR_NOT_SUPERSEDED")
        # (B) head-advance execution authorization ------------------------
        _stop_unless(e.head_authorization is not None, "HEAD_AUTHORIZATION_MISSING")
        checked = verify_registry_head_advance_authorization(authorization=e.head_authorization,
                                                             registry_root=e.registry_root,
                                                             environment=e.environment)
        _stop_unless(checked.verified, "HEAD_AUTHORIZATION_UNVERIFIED", checked.reason)
        auth: RegistryHeadAdvanceAuthorizationV1 = checked.authorization
        _stop_unless(auth.prior == prior_head and auth.target == candidate_head
                     and auth.recovery_epoch == prior_check.registry.recovery_epoch,
                     "HEAD_AUTHORIZATION_NOT_FOR_TRANSITION")
        consuming = chain.entry_consuming(auth.authorization_id)
        if consuming is not None:
            before, after = consuming
            _stop_unless(before.registry_head == prior_head and after.registry_head == candidate_head,
                         "HEAD_AUTHORIZATION_CONSUMED_ELSEWHERE")
        else:
            # Not yet executed: it is executable only while the witnessed head
            # is still exactly the authorized prior head.
            _stop_unless(head.registry_head == prior_head, "HEAD_ADVANCED_ELSEWHERE")
        state = S_AUTHORIZED
        facts["witnessExecuted"] = consuming is not None

        # S_PUBLISHED -------------------------------------------------------
        _stop_unless(consuming is not None, "HEAD_NOT_ADVANCED")
        _stop_unless(head.registry_head == candidate_head, "HEAD_ADVANCED_ELSEWHERE")
        state = S_PUBLISHED
        facts["predecessorState"] = None  # no issuing key between S_PUBLISHED and S_CURRENT

        # S_ACTIVATED (signer claim + ledger observation; not verification) --
        health = e.signer_health
        _stop_unless(isinstance(health, Mapping), "SIGNER_HEALTH_ABSENT")
        _stop_unless(health.get("credential") == HEALTH_CREDENTIAL_PRESENT
                     and health.get("publicKeySha256") == publication.public_key_sha256,
                     "SIGNER_NOT_REPORTING_SUCCESSOR")
        observation = e.ledger_observation
        _stop_unless(isinstance(observation, AuthorityLedgerObservationV1), "LEDGER_OBSERVATION_ABSENT")
        _stop_unless(observation.registry_view == candidate_head.version
                     and observation.signing_key_ids == (e.successor_key_id,), "LEDGER_NOT_OBSERVING_SUCCESSOR")
        state = S_ACTIVATED

        # S_CURRENT: all five conditions, independently reproduced ----------
        at_head = verify_registry_at_witness_head(witness=head, registry=e.candidate_registry,
                                                  registry_root=e.registry_root)
        _stop_unless(at_head.verified, "HEAD_REGISTRY_NOT_VERIFIED", at_head.reason)            # 1 + 2
        _stop_unless(single_current_key_reason(at_head.registry) is None, "SINGLE_CURRENT_KEY_FAILED")  # 3
        position = authority_ledger_position_reason(observation, head)
        _stop_unless(position is None, "LEDGER_POSITION_NOT_WITNESSED", position)
        binding = verify_loaded_key_binding(registry_root=e.registry_root, witness=head,
                                            head_registry=e.candidate_registry, signing_domain=e.signing_domain,
                                            evidence_type=e.evidence_type,
                                            observed_blob_sha256=e.observed_blob_sha256,
                                            publication=e.successor_publication, health=health)
        _stop_unless(binding.verified, "LOADED_KEY_BINDING_FAILED", binding.reason)            # 4
        _stop_unless(not e.hold_present, "LOCAL_HOLD_PRESENT")                                 # 5
        state = S_CURRENT
        facts.update(issuanceReady=True, predecessorState=P_SUPERSEDED, loadedKeyBinding=dict(binding.facts))
    except _Stop as stopped:
        return RotationAssessmentV1(state, stopped.reason, stopped.detail, facts)
    return RotationAssessmentV1(state, None, None, facts)


TRANSITION_ALLOWED = "TRANSITION_ALLOWED"
TRANSITION_REFUSED = "TRANSITION_REFUSED"


@dataclass(frozen=True)
class TransitionCheckV1:
    status: str
    reason: str | None = None
    detail: str | None = None

    @property
    def allowed(self) -> bool:
        return self.status == TRANSITION_ALLOWED


def validate_rotation_transition(current: str, proposed: str, evidence: RotationEvidenceV1) -> TransitionCheckV1:
    """May the rotation move from `current` to `proposed` on this evidence?

    Only single forward steps (or a pre-execution abort) are allowed, and the
    evidence must independently support the proposed state. Entering
    S_PROPOSED also requires the local hold (fail safe) to be in force.
    """
    if current not in ALLOWED_TRANSITIONS or proposed not in ALLOWED_TRANSITIONS:
        return TransitionCheckV1(TRANSITION_REFUSED, "UNKNOWN_STATE")
    if proposed not in ALLOWED_TRANSITIONS[current]:
        return TransitionCheckV1(TRANSITION_REFUSED, "TRANSITION_NOT_ALLOWED", f"{current}->{proposed}")
    assessment = evaluate_rotation(evidence)
    if assessment.state == NOT_EVALUABLE:
        return TransitionCheckV1(TRANSITION_REFUSED, "EVIDENCE_NOT_EVALUABLE", assessment.blocked_reason)
    reached = ROTATION_STATES.index(assessment.state)
    if proposed == P_ACTIVE:
        if assessment.facts.get("witnessExecuted") or reached >= ROTATION_STATES.index(S_PUBLISHED):
            return TransitionCheckV1(TRANSITION_REFUSED, "ABORT_AFTER_WITNESS_EXECUTION")
        return TransitionCheckV1(TRANSITION_ALLOWED)
    if reached < ROTATION_STATES.index(proposed):
        return TransitionCheckV1(TRANSITION_REFUSED, "EVIDENCE_INSUFFICIENT", assessment.blocked_reason)
    if proposed == S_PROPOSED and not evidence.hold_present:
        return TransitionCheckV1(TRANSITION_REFUSED, "LOCAL_HOLD_ABSENT")
    return TransitionCheckV1(TRANSITION_ALLOWED)
