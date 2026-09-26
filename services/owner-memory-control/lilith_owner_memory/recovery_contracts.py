"""15B2b-B1b-3c recovery epoch and recovery witness contracts (TEST-ONLY).

Design: docs/architecture/slice-15b2b-b1b3c-recovery-epoch-witness.md.

Core rule: RESTORE != AUTHORITY RESTORATION. Old valid evidence is never
permission for a new post-recovery admission.

This module defines, as public contracts only:

- the canonical encoding, digest, and ordering of the unchanged B1b-3a
  `RecoveryEpochV1 = (counter, random)`;
- the one derivation from a recovery epoch to the owner challenge's
  `ledgerEpoch`, so the two can never be independently mutable;
- `RecoveryWitnessV1`: the minimum independently trusted freshness state
  (current recovery epoch, minimum authority registry version, policy
  version, broker ledger sequence and hash-chain head). A witness is
  freshness / monotonic-state evidence only. It never authorizes: its key
  must be disjoint from the registry root and from every authority key;
- the witness as the explicit source of `trusted_minimum_registry_version`
  and `expected_recovery_epoch` for the B1b-3a verifier;
- a Privacy boundary observation slot. No canonical Privacy epoch exists in
  this repository, so none is invented here (B1b-3f).

Threat limit, stated once and asserted by tests: a witness detects a
LEDGER-ONLY restore only while the witness itself survives. A same-host
witness restored together with the broker ledger (whole-host or whole-disk
rollback) is not detected. Nothing here is WHOLE_HOST_ROLLBACK_PROTECTED.

Nothing here holds or loads a private key, reads a file, the environment, or
the network, or touches the broker, L04, or Privacy DB.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Mapping

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from lilith_memory.owner_proof import OwnerProofError, _digest, _exact, _id, _instant

from . import authority_contracts as A
from .contracts import DEPLOYMENT_ENVIRONMENTS, ContractViolation, _canonical, _choice

# Frozen domain separators, distinct from every B2a / B1b-3a separator.
RECOVERY_EPOCH_DOMAIN_SEPARATOR = b"LILITH_RECOVERY_EPOCH_V1\x00"
WITNESS_DOMAIN_SEPARATOR = b"LILITH_RECOVERY_WITNESS_V1\x00"

LEDGER_EPOCH_PREFIX = "lep1."
WITNESS_PROTOCOL = "LILITH_RECOVERY_WITNESS"
WITNESS_SCHEMA_VERSION = 1
TEST_ONLY_WITNESS_PREFIX = "test-only.witness."
LEDGER_HEAD_GENESIS = "0" * 64

# Epoch comparison, from the point of view of a reference (the witness).
EPOCH_EQUAL = "EQUAL"
EPOCH_OLDER = "OLDER"
EPOCH_NEWER = "NEWER"
EPOCH_FORKED = "FORKED"

# The two questions a verifier may be asked. They are never collapsed.
HISTORICAL_VALIDITY = "HISTORICAL_VALIDITY"
NEW_ADMISSION_AUTHORITY = "NEW_ADMISSION_AUTHORITY"

# What a same-host witness can detect. Never "WHOLE_HOST".
ROLLBACK_DETECTION_SCOPE = "LEDGER_ONLY"
WHOLE_HOST_ROLLBACK_PROTECTED = False


# ------------------------------------------------------------- epoch ---

def _epoch(value: Any) -> A.RecoveryEpochV1:
    if not isinstance(value, A.RecoveryEpochV1):
        raise ContractViolation("INVALID_RECOVERY_EPOCH")
    return A.RecoveryEpochV1.from_dict(value.to_dict())


def epoch_canonical_bytes(epoch: A.RecoveryEpochV1) -> bytes:
    """RFC 8785 bytes of `{"counter", "random"}`: the exact B1b-3a shape that
    registries and OwnerEvidenceV2 already sign."""
    return _canonical(_epoch(epoch).to_dict())


def epoch_digest(epoch: A.RecoveryEpochV1, environment: str) -> str:
    """Environment-bound epoch digest. The same `(counter, random)` in two
    environments is two different epochs."""
    value = _epoch(epoch)
    env = _choice(environment, DEPLOYMENT_ENVIRONMENTS, "environment")
    return hashlib.sha256(RECOVERY_EPOCH_DOMAIN_SEPARATOR + _canonical(
        {"counter": value.counter, "environment": env, "random": value.random})).hexdigest()


def ledger_epoch_id(epoch: A.RecoveryEpochV1, environment: str) -> str:
    """The only valid `OwnerMemoryChallengeV2.ledgerEpoch` for this epoch.

    ledgerEpoch is derived, never chosen: `lep1.` + `epoch_digest`. A value
    of 69 characters that satisfies the unchanged B1a identifier rule.
    """
    return LEDGER_EPOCH_PREFIX + epoch_digest(epoch, environment)


def ledger_epoch_matches(ledger_epoch: Any, epoch: A.RecoveryEpochV1, environment: str) -> bool:
    return isinstance(ledger_epoch, str) and ledger_epoch == ledger_epoch_id(epoch, environment)


def compare_epochs(reference: A.RecoveryEpochV1, other: A.RecoveryEpochV1) -> str:
    """Partial order. Equality is exact on both parts; a shared counter with a
    different random is a fork, never "equal" and never "newer"."""
    ref, oth = _epoch(reference), _epoch(other)
    if ref == oth:
        return EPOCH_EQUAL
    if ref.counter == oth.counter:
        return EPOCH_FORKED
    return EPOCH_OLDER if oth.counter < ref.counter else EPOCH_NEWER


# ----------------------------------------------------------- witness ---

WITNESS_FIELDS = frozenset({
    "protocol", "schemaVersion", "environment", "witnessVersion", "previousWitnessDigest",
    "currentRecoveryEpoch", "minimumRegistryVersion", "policyVersion", "ledgerSequence",
    "ledgerHead", "updatedAt", "witnessKeyId", "signature",
})
WITNESS_SIGNED_FIELDS = WITNESS_FIELDS - {"signature"}


@dataclass(frozen=True)
class RecoveryWitnessV1:
    """Minimum independently trusted freshness state for one environment.

    - `currentRecoveryEpoch`: the only epoch in which new authority may be
      issued; `ledgerEpoch` is derived from it;
    - `minimumRegistryVersion`: the trusted monotonic floor for the authority
      key registry (B1b-3a `trusted_minimum_registry_version`);
    - `ledgerSequence` / `ledgerHead`: the broker ledger's journal length and
      hash-chain head, so a restore *within* one epoch is also detected;
    - `previousWitnessDigest`: the witness chain (null only at version 1).

    Freshness evidence only: never authority, never an authority key.
    """

    environment: str
    witness_version: int
    previous_witness_digest: str | None
    current_recovery_epoch: A.RecoveryEpochV1
    minimum_registry_version: int
    policy_version: str
    ledger_sequence: int
    ledger_head: str
    updated_at: datetime
    witness_key_id: str
    digest: str

    @property
    def ledger_epoch(self) -> str:
        return ledger_epoch_id(self.current_recovery_epoch, self.environment)

    @classmethod
    def from_verified_dict(cls, value: Mapping[str, Any]) -> RecoveryWitnessV1:
        """Parse a witness whose signature has already been verified."""
        _exact(value, WITNESS_FIELDS)
        if value.get("protocol") != WITNESS_PROTOCOL or type(value.get("schemaVersion")) is not int \
                or value["schemaVersion"] != WITNESS_SCHEMA_VERSION:
            raise ContractViolation("UNSUPPORTED_SCHEMA_VERSION")
        version = A._int(value["witnessVersion"], "witness_version", 1)
        previous = value["previousWitnessDigest"]
        if (version == 1) != (previous is None):
            raise ContractViolation("INVALID_WITNESS_CHAIN")
        if previous is not None:
            _digest(previous, "previous_witness_digest")
        return cls(
            _choice(value["environment"], DEPLOYMENT_ENVIRONMENTS, "environment"), version, previous,
            A.RecoveryEpochV1.from_dict(value["currentRecoveryEpoch"]),
            A._int(value["minimumRegistryVersion"], "minimum_registry_version", 1),
            _id(value["policyVersion"], "policy_version"),
            A._int(value["ledgerSequence"], "ledger_sequence", 1),
            _digest(value["ledgerHead"], "ledger_head"),
            _instant(value["updatedAt"]),
            _id(value["witnessKeyId"], "witness_key_id"),
            witness_digest(value),
        )


def witness_signing_bytes(unsigned: Mapping[str, Any]) -> bytes:
    """Bytes a witness key signs; used by TEST-ONLY fixtures."""
    _exact(unsigned, WITNESS_SIGNED_FIELDS)
    return WITNESS_DOMAIN_SEPARATOR + _canonical(unsigned)


def witness_digest(witness: Mapping[str, Any]) -> str:
    """SHA-256 over the exact signed bytes; the next witness's `previousWitnessDigest`."""
    return hashlib.sha256(witness_signing_bytes({k: witness[k] for k in WITNESS_SIGNED_FIELDS})).hexdigest()


ANCHOR_FIELDS = frozenset({"schemaVersion", "witnessKeyId", "environment", "algorithm", "publicKey"})


@dataclass(frozen=True)
class TrustedWitnessAnchorV1:
    """The caller-supplied public key that witness documents must verify
    under. Only `test-only.witness.` anchors are accepted in B1b-3c."""

    witness_key_id: str
    environment: str
    public_key: bytes

    @classmethod
    def from_dict(cls, value: Any) -> TrustedWitnessAnchorV1:
        _exact(value, ANCHOR_FIELDS)
        if type(value["schemaVersion"]) is not int or value["schemaVersion"] != 1:
            raise ContractViolation("UNSUPPORTED_SCHEMA_VERSION")
        if value["algorithm"] != A.ALGORITHM:
            raise ContractViolation("UNSUPPORTED_ALGORITHM")
        return cls(_id(value["witnessKeyId"], "witness_key_id"),
                   _choice(value["environment"], DEPLOYMENT_ENVIRONMENTS, "environment"),
                   A._public_key(value["publicKey"]))

    @property
    def test_only(self) -> bool:
        return self.witness_key_id.startswith(TEST_ONLY_WITNESS_PREFIX)


VERIFIED_WITNESS = "VERIFIED_WITNESS"
WITNESS_NOT_VERIFIED = "WITNESS_NOT_VERIFIED"

# Closed, ordered witness reason taxonomy.
WITNESS_REASONS = (
    "MALFORMED_CONTEXT",
    "WITNESS_ANCHOR_NOT_TEST_ONLY",
    "WITNESS_MISSING",
    "WITNESS_MALFORMED",
    "WITNESS_UNSIGNED",
    "WITNESS_KEY_MISMATCH",
    "WITNESS_SIGNATURE_INVALID",
    "UNSUPPORTED_SCHEMA_VERSION",
    "WITNESS_ENVIRONMENT_MISMATCH",
    "WITNESS_KEY_IS_AUTHORITY_KEY",
)


@dataclass(frozen=True)
class WitnessResultV1:
    status: str
    reason: str | None = None
    witness: RecoveryWitnessV1 | None = None

    @property
    def verified(self) -> bool:
        return self.status == VERIFIED_WITNESS


class _Reject(Exception):
    def __init__(self, reason: str):
        assert reason in WITNESS_REASONS, reason
        self.reason = reason


def _require(condition: bool, reason: str) -> None:
    if not condition:
        raise _Reject(reason)


def verify_recovery_witness(*, anchor: TrustedWitnessAnchorV1, witness: Mapping[str, Any] | None,
                            environment: str, registry_root: A.TrustedRegistryRootV1,
                            authority_public_keys: frozenset[bytes] = frozenset()) -> WitnessResultV1:
    """Verify one witness document. `witness != authority`: the anchor key
    must differ from the registry root and from every supplied authority key."""
    try:
        _require(isinstance(anchor, TrustedWitnessAnchorV1) and isinstance(registry_root, A.TrustedRegistryRootV1)
                 and environment in DEPLOYMENT_ENVIRONMENTS and isinstance(authority_public_keys, frozenset),
                 "MALFORMED_CONTEXT")
        _require(anchor.test_only, "WITNESS_ANCHOR_NOT_TEST_ONLY")
        _require(anchor.public_key != registry_root.public_key and anchor.public_key not in authority_public_keys,
                 "WITNESS_KEY_IS_AUTHORITY_KEY")
        _require(witness is not None, "WITNESS_MISSING")
        _require(isinstance(witness, Mapping), "WITNESS_MALFORMED")
        _require(witness.get("signature") is not None, "WITNESS_UNSIGNED")
        try:
            _exact(witness, WITNESS_FIELDS)
            signature = A._signature(witness["signature"])
            message = witness_signing_bytes({k: witness[k] for k in WITNESS_SIGNED_FIELDS})
        except (OwnerProofError, TypeError, ValueError) as exc:
            raise _Reject("WITNESS_MALFORMED") from exc
        _require(witness["witnessKeyId"] == anchor.witness_key_id, "WITNESS_KEY_MISMATCH")
        try:
            Ed25519PublicKey.from_public_bytes(anchor.public_key).verify(signature, message)
        except (InvalidSignature, ValueError) as exc:
            raise _Reject("WITNESS_SIGNATURE_INVALID") from exc
        try:
            parsed = RecoveryWitnessV1.from_verified_dict(witness)
        except OwnerProofError as exc:
            raise _Reject("UNSUPPORTED_SCHEMA_VERSION" if exc.code == "UNSUPPORTED_SCHEMA_VERSION"
                          else "WITNESS_MALFORMED") from exc
        _require(parsed.environment == environment == anchor.environment == registry_root.environment,
                 "WITNESS_ENVIRONMENT_MISMATCH")
    except _Reject as rejected:
        return WitnessResultV1(WITNESS_NOT_VERIFIED, rejected.reason)
    return WitnessResultV1(VERIFIED_WITNESS, None, parsed)


def witness_authority_context(witness: RecoveryWitnessV1, *, registry_root: A.TrustedRegistryRootV1,
                              purpose: str) -> A.AuthorityVerificationContextV1:
    """The B1b-3a verification context, with its trusted monotonic inputs
    taken from the verified witness and nowhere else."""
    if not isinstance(witness, RecoveryWitnessV1):
        raise ContractViolation("INVALID_WITNESS")
    context = A.AuthorityVerificationContextV1(
        environment=witness.environment, purpose=purpose, registry_root=registry_root,
        trusted_minimum_registry_version=witness.minimum_registry_version,
        expected_recovery_epoch=witness.current_recovery_epoch, policy_version=witness.policy_version)
    context.validate()
    return context


# Closed, ordered succession reason taxonomy (a witness update is valid only
# as a monotonic successor of the current witness).
SUCCESSION_REASONS = (
    "WITNESS_ENVIRONMENT_MISMATCH",
    "WITNESS_VERSION_NOT_SUCCESSOR",
    "WITNESS_CHAIN_BROKEN",
    "WITNESS_EPOCH_REGRESSION",
    "WITNESS_EPOCH_NOT_SUCCESSOR",
    "WITNESS_REGISTRY_MINIMUM_REGRESSION",
    "WITNESS_POLICY_CHANGE_WITHOUT_REGISTRY",
    "WITNESS_LEDGER_REGRESSION",
    "WITNESS_TIME_REGRESSION",
)


def witness_succession_reason(previous: RecoveryWitnessV1, following: RecoveryWitnessV1) -> str | None:
    """None when `following` is a valid monotonic successor of `previous`."""
    if following.environment != previous.environment:
        return "WITNESS_ENVIRONMENT_MISMATCH"
    if following.witness_version != previous.witness_version + 1:
        return "WITNESS_VERSION_NOT_SUCCESSOR"
    if following.previous_witness_digest != previous.digest:
        return "WITNESS_CHAIN_BROKEN"
    order = compare_epochs(previous.current_recovery_epoch, following.current_recovery_epoch)
    if order in {EPOCH_OLDER, EPOCH_FORKED}:
        return "WITNESS_EPOCH_REGRESSION"
    advanced = order == EPOCH_NEWER
    if advanced and following.current_recovery_epoch.counter != previous.current_recovery_epoch.counter + 1:
        return "WITNESS_EPOCH_NOT_SUCCESSOR"
    if following.minimum_registry_version < previous.minimum_registry_version \
            or (advanced and following.minimum_registry_version == previous.minimum_registry_version):
        return "WITNESS_REGISTRY_MINIMUM_REGRESSION"
    if following.policy_version != previous.policy_version \
            and following.minimum_registry_version == previous.minimum_registry_version:
        return "WITNESS_POLICY_CHANGE_WITHOUT_REGISTRY"
    # Within one epoch the ledger journal only grows. An epoch advance may
    # start from a restored (shorter) ledger: that is safe because every
    # pre-advance artifact is bound to the old epoch and can never create new
    # authority. It must still name a different journal head.
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


# ----------------------------------------------------------- privacy ---

# No canonical Privacy epoch exists in this repository. B1b-3c models only the
# contractual slot a readiness gate needs; B1b-3f must define its source.
CANONICAL_PRIVACY_EPOCH_EXISTS = False
PRIVACY_AT_OR_AFTER_REQUIRED = "AT_OR_AFTER_REQUIRED"
PRIVACY_OLDER_THAN_REQUIRED = "OLDER_THAN_REQUIRED"
PRIVACY_UNAVAILABLE = "UNAVAILABLE"
PRIVACY_NOT_MODELLED = "NOT_MODELLED"
PRIVACY_BOUNDARY_STATUSES = frozenset({
    PRIVACY_AT_OR_AFTER_REQUIRED, PRIVACY_OLDER_THAN_REQUIRED, PRIVACY_UNAVAILABLE, PRIVACY_NOT_MODELLED,
})


@dataclass(frozen=True)
class PrivacyBoundaryObservationV1:
    """What a restored runtime knows about its Privacy state relative to the
    required current Privacy boundary (newer suppression/deletion). Only
    AT_OR_AFTER_REQUIRED permits readiness; everything else fails closed.
    In B1b-3c the only source is a synthetic TEST observation."""

    status: str
    source: str = "TEST_SYNTHETIC"
    facts: Mapping[str, Any] = field(default_factory=dict)

    def validate(self) -> None:
        _choice(self.status, PRIVACY_BOUNDARY_STATUSES, "privacy_boundary_status")
        if self.source != "TEST_SYNTHETIC":
            raise ContractViolation("INVALID_PRIVACY_BOUNDARY_SOURCE")
