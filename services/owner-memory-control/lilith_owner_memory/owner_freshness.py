"""15B2b-B1b-3e PR-3: owner / off-host freshness foundation (pure, offline).

Record: docs/architecture/slice-15b2b-b1b3e-pr3-owner-offhost-foundation.md.

PR-2 established that every persistent authority and custody object on DEV
shares one rollback domain: a restored boot disk presents a self-consistent,
cryptographically valid, old authority world. This module is the owner-side
comparison that lets such a world be identified as stale:

- `OwnerFreshnessRecordV1`: one owner decision (accept a witness head as the
  latest world, or reject a candidate), hash-chained to the previous record.
  Canonical bytes are RFC 8785 JCS; the record digest is
  `sha256(LILITH_OWNER_FRESHNESS_RECORD_V1\\0 || JCS(record))`.
- `verify_owner_register` / `reconcile_owner_replicas`: chain and
  monotonicity rules over the owner's records, and the fail-closed rule that
  divergent replicas are never resolved by length or by the latest write.
- `classify_presented_world`: authenticity (the caller's K-WIT chain
  verification) kept separate from freshness (`CURRENT`, `STALE`,
  `AHEAD_UNACCEPTED`, `CONFLICTING`, `FRESHNESS_UNKNOWN`, `REFUSED`).
- `freshness_gate`: which owner-side operations stay blocked unless the
  presented world is exactly the latest owner-accepted one.
- `propose_*`: candidate records for an owner ceremony. A candidate is not an
  acceptance.

It never reads a file, the environment, a network, or a credential, holds no
key, and produces no signature.

    storage != acceptance;  file existence != owner authority
    DEV proposal != owner acceptance;  signature validity != freshness
    K-ROOT authorization != owner freshness acceptance
    RecoveryWitness freshness != owner off-host freshness
    freshness precondition met != authorization

Threat limit: the register establishes freshness only relative to the owner's
latest accepted checkpoint, and only while the owner's copies are not all
rolled back together. It proves nothing about time and prevents no rollback.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence

from lilith_memory.owner_proof import OwnerProofError, _digest, _exact

from . import authority_contracts as A
from . import recovery_contracts as R
from . import rotation_contracts as RC
from . import witness_readiness as WR
from .contracts import ContractViolation, _canonical, _choice

# ---------------------------------------------------------------- contract ---

RECORD_TYPE = "LILITH_OWNER_FRESHNESS_RECORD"
RECORD_SCHEMA_VERSION = 1
RECORD_DOMAIN_SEPARATOR = b"LILITH_OWNER_FRESHNESS_RECORD_V1\x00"

# authorityProfile -> the only environment it admits. PROD is not modelled.
PROFILE_ENVIRONMENTS = {"TEST_ONLY": "test", "DEV_SYNTHETIC": "dev"}

ACCEPT_CURRENT = "ACCEPT_CURRENT"
REJECT_CANDIDATE = "REJECT_CANDIDATE"
DECISIONS = frozenset({ACCEPT_CURRENT, REJECT_CANDIDATE})

RECORD_FIELDS = frozenset({
    "recordType", "schemaVersion", "environment", "authorityProfile", "recordVersion",
    "previousRecordDigest", "decision", "genesisWitnessDigest", "witnessVersion", "witnessDigest",
    "recoveryEpoch", "registryVersion", "registryDigest",
})


class _Reject(Exception):
    def __init__(self, reason: str, detail: str | None = None):
        super().__init__(reason)
        self.reason = reason
        self.detail = detail


def _require(condition: bool, reason: str, detail: str | None = None) -> None:
    if not condition:
        raise _Reject(reason, detail)


def record_digest(record: Mapping[str, Any]) -> str:
    """The record's identity and the next record's `previousRecordDigest`.

    It covers every record field. There is no self-digest field, and no
    signature or acceptance envelope is inside the digested bytes, so an
    acceptance mechanism can be added later without changing record identity.
    """
    _exact(record, RECORD_FIELDS)
    return hashlib.sha256(RECORD_DOMAIN_SEPARATOR + _canonical(record)).hexdigest()


def record_bytes(record: Mapping[str, Any]) -> bytes:
    """The one stored byte form of a record (RFC 8785 JCS)."""
    return WR.document_bytes(record)


def parse_record_bytes(raw: Any) -> dict[str, Any]:
    """Strict parse: one JSON object, no duplicate keys, canonical bytes only."""
    return WR.parse_document_bytes(raw)


@dataclass(frozen=True)
class OwnerFreshnessRecordV1:
    """One owner decision about one authentic witness head.

    - `ACCEPT_CURRENT`: this witness head is the latest authority world the
      owner accepts for this environment and profile.
    - `REJECT_CANDIDATE`: the owner declines this witness head (a fork, an
      unwanted transition, an ambiguous recovery). Terminal: it can never be
      accepted later, and every chain that contains it is refused.

    `recoveryEpoch` and `registryVersion`/`registryDigest` are REQUIRED
    copies of fields the witness digest already commits to. They exist so a
    presented world that is not on the owner's lineage can still be ordered
    (epoch or registry regression), and so the owner can read what they
    accept. They must equal the witness they name.
    """

    environment: str
    authority_profile: str
    record_version: int
    previous_record_digest: str | None
    decision: str
    genesis_witness_digest: str
    witness_version: int
    witness_digest: str
    recovery_epoch: A.RecoveryEpochV1
    registry_version: int
    registry_digest: str
    digest: str

    @property
    def accepts(self) -> bool:
        return self.decision == ACCEPT_CURRENT

    @classmethod
    def from_dict(cls, value: Any) -> OwnerFreshnessRecordV1:
        _exact(value, RECORD_FIELDS)
        if value["recordType"] != RECORD_TYPE or type(value["schemaVersion"]) is not int \
                or value["schemaVersion"] != RECORD_SCHEMA_VERSION:
            raise ContractViolation("UNSUPPORTED_SCHEMA_VERSION")
        profile = _choice(value["authorityProfile"], frozenset(PROFILE_ENVIRONMENTS), "authority_profile")
        environment = value["environment"]
        if environment != PROFILE_ENVIRONMENTS[profile]:
            raise ContractViolation("PROFILE_ENVIRONMENT_MISMATCH")
        version = A._int(value["recordVersion"], "record_version", 1)
        previous = value["previousRecordDigest"]
        if (version == 1) != (previous is None):
            raise ContractViolation("INVALID_RECORD_CHAIN")
        decision = _choice(value["decision"], DECISIONS, "decision")
        genesis = _digest(value["genesisWitnessDigest"], "genesis_witness_digest")
        witness_version = A._int(value["witnessVersion"], "witness_version", 1)
        witness_digest = _digest(value["witnessDigest"], "witness_digest")
        if version == 1 and (decision != ACCEPT_CURRENT or witness_version != 1 or witness_digest != genesis):
            raise ContractViolation("INVALID_GENESIS_RECORD")
        if (witness_version == 1) != (witness_digest == genesis):
            raise ContractViolation("INVALID_GENESIS_BINDING")
        if decision == REJECT_CANDIDATE and witness_version == 1:
            raise ContractViolation("INVALID_REJECTION")
        return cls(environment, profile, version,
                   None if previous is None else _digest(previous, "previous_record_digest"),
                   decision, genesis, witness_version, witness_digest,
                   A.RecoveryEpochV1.from_dict(value["recoveryEpoch"]),
                   A._int(value["registryVersion"], "registry_version", 1),
                   _digest(value["registryDigest"], "registry_digest"),
                   record_digest(value))

    def to_dict(self) -> dict[str, Any]:
        return {
            "recordType": RECORD_TYPE, "schemaVersion": RECORD_SCHEMA_VERSION, "environment": self.environment,
            "authorityProfile": self.authority_profile, "recordVersion": self.record_version,
            "previousRecordDigest": self.previous_record_digest, "decision": self.decision,
            "genesisWitnessDigest": self.genesis_witness_digest, "witnessVersion": self.witness_version,
            "witnessDigest": self.witness_digest, "recoveryEpoch": self.recovery_epoch.to_dict(),
            "registryVersion": self.registry_version, "registryDigest": self.registry_digest,
        }

    def matches(self, witness: RC.RecoveryWitnessV2) -> bool:
        """Every copied field equals the witness it names."""
        return (witness.digest == self.witness_digest and witness.witness_version == self.witness_version
                and witness.current_recovery_epoch == self.recovery_epoch
                and witness.registry_head == RC.RegistryHeadV1(self.registry_version, self.registry_digest))


# ---------------------------------------------------------------- register ---

REGISTER_VERIFIED = "OWNER_REGISTER_VERIFIED"
REGISTER_NOT_VERIFIED = "OWNER_REGISTER_NOT_VERIFIED"
REGISTER_REASONS = (
    "OWNER_REGISTER_UNAVAILABLE",
    "REPLICA_QUORUM_UNMET",
    "REPLICAS_DIVERGENT",
    "OWNER_REGISTER_EMPTY",
    "RECORD_MALFORMED",
    "RECORD_VERSION_NOT_SUCCESSOR",
    "PREVIOUS_RECORD_DIGEST_MISMATCH",
    "REGISTER_ENVIRONMENT_CHANGED",
    "REGISTER_PROFILE_CHANGED",
    "REGISTER_GENESIS_CHANGED",
    "ACCEPTED_WITNESS_NOT_ADVANCING",
    "ACCEPTED_EPOCH_REGRESSION",
    "ACCEPTED_EPOCH_FORKED",
    "ACCEPTED_REGISTRY_REGRESSION",
    "ACCEPTED_REGISTRY_DIGEST_CONFLICT",
    "WITNESS_DECIDED_TWICE",
)


@dataclass(frozen=True)
class OwnerRegisterFactsV1:
    """What a verified owner register establishes. Freshness is relative to
    `latest`, the last ACCEPT_CURRENT record."""

    records: tuple[OwnerFreshnessRecordV1, ...]
    latest: OwnerFreshnessRecordV1
    accepted: Mapping[int, OwnerFreshnessRecordV1]    # witnessVersion -> accepted record
    rejected: frozenset[str]                          # rejected witness digests

    @property
    def environment(self) -> str:
        return self.latest.environment

    @property
    def authority_profile(self) -> str:
        return self.latest.authority_profile

    @property
    def genesis_witness_digest(self) -> str:
        return self.latest.genesis_witness_digest

    @property
    def head_digest(self) -> str:
        """Digest of the last record, of either decision."""
        return self.records[-1].digest


@dataclass(frozen=True)
class OwnerRegisterResultV1:
    status: str
    reason: str | None = None
    detail: str | None = None
    facts: OwnerRegisterFactsV1 | None = None

    @property
    def verified(self) -> bool:
        return self.status == REGISTER_VERIFIED


def _accept_order(previous: OwnerFreshnessRecordV1, following: OwnerFreshnessRecordV1) -> None:
    _require(following.witness_version > previous.witness_version, "ACCEPTED_WITNESS_NOT_ADVANCING")
    order = R.compare_epochs(previous.recovery_epoch, following.recovery_epoch)
    _require(order != R.EPOCH_OLDER, "ACCEPTED_EPOCH_REGRESSION")
    _require(order != R.EPOCH_FORKED, "ACCEPTED_EPOCH_FORKED")
    _require(following.registry_version >= previous.registry_version, "ACCEPTED_REGISTRY_REGRESSION")
    _require(following.registry_version != previous.registry_version
             or following.registry_digest == previous.registry_digest, "ACCEPTED_REGISTRY_DIGEST_CONFLICT")


def verify_owner_register(records: Any) -> OwnerRegisterResultV1:
    """Chain, identity, and monotonicity over one copy of the owner register.

    The chain detects a truncated, reordered, edited, or spliced copy only
    when compared against something outside that copy (another replica, or
    the owner's own memory of the head). A hash chain held in one rollback
    domain does not establish freshness on its own.
    """
    try:
        _require(records is not None, "OWNER_REGISTER_UNAVAILABLE")
        _require(isinstance(records, (list, tuple)), "RECORD_MALFORMED")
        _require(len(records) > 0, "OWNER_REGISTER_EMPTY")
        parsed: list[OwnerFreshnessRecordV1] = []
        for index, raw in enumerate(records):
            try:
                parsed.append(OwnerFreshnessRecordV1.from_dict(
                    parse_record_bytes(raw) if isinstance(raw, (bytes, bytearray)) else raw))
            except (OwnerProofError, TypeError) as exc:
                raise _Reject("RECORD_MALFORMED", f"{index}:{exc}") from exc
        first = parsed[0]
        accepted: dict[int, OwnerFreshnessRecordV1] = {1: first}
        decided: set[str] = {first.witness_digest}
        rejected: set[str] = set()
        latest = first
        for previous, following in zip(parsed, parsed[1:]):
            _require(following.record_version == previous.record_version + 1, "RECORD_VERSION_NOT_SUCCESSOR",
                     str(following.record_version))
            _require(following.previous_record_digest == previous.digest, "PREVIOUS_RECORD_DIGEST_MISMATCH",
                     str(following.record_version))
            _require(following.environment == first.environment, "REGISTER_ENVIRONMENT_CHANGED")
            _require(following.authority_profile == first.authority_profile, "REGISTER_PROFILE_CHANGED")
            _require(following.genesis_witness_digest == first.genesis_witness_digest, "REGISTER_GENESIS_CHANGED")
            _require(following.witness_digest not in decided, "WITNESS_DECIDED_TWICE", following.witness_digest)
            decided.add(following.witness_digest)
            if following.accepts:
                _accept_order(latest, following)
                accepted[following.witness_version] = following
                latest = following
            else:
                rejected.add(following.witness_digest)
    except _Reject as rejected_register:
        return OwnerRegisterResultV1(REGISTER_NOT_VERIFIED, rejected_register.reason, rejected_register.detail)
    return OwnerRegisterResultV1(REGISTER_VERIFIED, facts=OwnerRegisterFactsV1(
        tuple(parsed), latest, dict(accepted), frozenset(rejected)))


def reconcile_owner_replicas(replicas: Any, *, minimum_replicas: int = 2) -> OwnerRegisterResultV1:
    """The owner register as read from its independent copies.

    Every copy must verify and all copies must be identical, record for
    record. A copy that is behind, ahead, or forked makes the result
    `REPLICAS_DIVERGENT`, which is never resolved by length, by newest file,
    or by last write. The owner resolves it by ceremony.
    """
    if replicas is None or (isinstance(replicas, (list, tuple)) and len(replicas) == 0):
        return OwnerRegisterResultV1(REGISTER_NOT_VERIFIED, "OWNER_REGISTER_UNAVAILABLE")
    if not isinstance(replicas, (list, tuple)) or type(minimum_replicas) is not int or minimum_replicas < 1:
        return OwnerRegisterResultV1(REGISTER_NOT_VERIFIED, "RECORD_MALFORMED")
    if len(replicas) < minimum_replicas:
        return OwnerRegisterResultV1(REGISTER_NOT_VERIFIED, "REPLICA_QUORUM_UNMET", str(len(replicas)))
    results = [verify_owner_register(replica) for replica in replicas]
    for index, result in enumerate(results):
        if not result.verified:
            return OwnerRegisterResultV1(REGISTER_NOT_VERIFIED, result.reason, f"replica{index}:{result.detail}")
    sequences = [tuple(r.digest for r in result.facts.records) for result in results]
    for index, sequence in enumerate(sequences[1:], start=1):
        if sequence != sequences[0]:
            shorter, longer = sorted((sequence, sequences[0]), key=len)
            shape = "PREFIX" if longer[:len(shorter)] == shorter else "FORK"
            return OwnerRegisterResultV1(REGISTER_NOT_VERIFIED, "REPLICAS_DIVERGENT", f"replica{index}:{shape}")
    return results[0]


# --------------------------------------------------------------- freshness ---

AUTHENTIC = "AUTHENTIC"
NOT_AUTHENTIC = "NOT_AUTHENTIC"

CURRENT = "CURRENT"
STALE = "STALE"
AHEAD_UNACCEPTED = "AHEAD_UNACCEPTED"
CONFLICTING = "CONFLICTING"
FRESHNESS_UNKNOWN = "FRESHNESS_UNKNOWN"
REFUSED = "REFUSED"
FRESHNESS_STATES = (CURRENT, STALE, AHEAD_UNACCEPTED, CONFLICTING, FRESHNESS_UNKNOWN, REFUSED)

FRESHNESS_REASONS = (
    # REFUSED
    "MALFORMED_INPUT", "ENVIRONMENT_MISMATCH", "PROFILE_MISMATCH",
    # FRESHNESS_UNKNOWN
    "OWNER_REGISTER_NOT_VERIFIED", "PRESENTED_NOT_AUTHENTIC", "OWNER_RECORD_INCONSISTENT",
    # CONFLICTING
    "GENESIS_MISMATCH", "OWNER_REJECTED_LINEAGE", "SAME_VERSION_DIGEST_MISMATCH",
    "FORKED_FROM_ACCEPTED_HISTORY", "RECOVERY_EPOCH_FORKED",
    # STALE
    "EARLIER_ACCEPTED_STATE", "RECOVERY_EPOCH_REGRESSION", "REGISTRY_REGRESSION",
    "WITNESS_SEQUENCE_REGRESSION",
    # AHEAD_UNACCEPTED
    "AHEAD_LEDGER_ONLY", "AHEAD_AUTHORITY_CHANGING",
)

DEV_STATE_STALE = "DEV_STATE_STALE"   # the recovery-facing name for a STALE presented world


class _Classified(Exception):
    def __init__(self, freshness: str, reason: str, detail: str | None = None):
        super().__init__(reason)
        self.freshness, self.reason, self.detail = freshness, reason, detail


@dataclass(frozen=True)
class FreshnessResultV1:
    """Authenticity and freshness, never collapsed. `AUTHENTIC` + `STALE` is
    an old world that verifies; it is not current."""

    authenticity: str
    freshness: str
    reason: str | None = None
    detail: str | None = None
    facts: Mapping[str, Any] = field(default_factory=dict)

    @property
    def current(self) -> bool:
        return self.authenticity == AUTHENTIC and self.freshness == CURRENT


def _lineage(register: OwnerRegisterFactsV1, by_version: Mapping[int, RC.RecoveryWitnessV2]) -> None:
    """Every accepted checkpoint the presented chain reaches must be on it."""
    for version, record in register.accepted.items():
        entry = by_version.get(version)
        if entry is None:
            continue
        if entry.digest != record.witness_digest:
            raise _Classified(CONFLICTING, "FORKED_FROM_ACCEPTED_HISTORY", str(version))
        if not record.matches(entry):
            raise _Classified(FRESHNESS_UNKNOWN, "OWNER_RECORD_INCONSISTENT", str(version))


def _classify(register: OwnerRegisterFactsV1, chain: RC.WitnessChainFactsV1) -> tuple[str, str, str | None]:
    by_version = {w.witness_version: w for w in chain.witnesses}
    head, latest = chain.head, register.latest
    genesis = by_version.get(1)
    if genesis is None or genesis.digest != register.genesis_witness_digest:
        raise _Classified(CONFLICTING, "GENESIS_MISMATCH")
    for witness in chain.witnesses:
        if witness.digest in register.rejected:
            raise _Classified(CONFLICTING, "OWNER_REJECTED_LINEAGE", str(witness.witness_version))
    epoch_order = R.compare_epochs(latest.recovery_epoch, head.current_recovery_epoch)
    if head.witness_version < latest.witness_version:
        accepted = register.accepted.get(head.witness_version)
        if accepted is not None and accepted.witness_digest == head.digest:
            _lineage(register, by_version)
            return STALE, "EARLIER_ACCEPTED_STATE", str(accepted.record_version)
        _lineage(register, by_version)
        if epoch_order == R.EPOCH_FORKED:
            return CONFLICTING, "RECOVERY_EPOCH_FORKED", None
        if epoch_order == R.EPOCH_NEWER or head.registry_version > latest.registry_version:
            # behind the owner in witness sequence yet ahead in epoch or registry: not one lineage
            return CONFLICTING, "FORKED_FROM_ACCEPTED_HISTORY", "DIVERGENT_BEHIND"
        if epoch_order == R.EPOCH_OLDER:
            return STALE, "RECOVERY_EPOCH_REGRESSION", None
        if head.registry_version < latest.registry_version:
            return STALE, "REGISTRY_REGRESSION", None
        return STALE, "WITNESS_SEQUENCE_REGRESSION", None
    if head.witness_version == latest.witness_version:
        if head.digest != latest.witness_digest:
            raise _Classified(CONFLICTING, "SAME_VERSION_DIGEST_MISMATCH")
        _lineage(register, by_version)
        return CURRENT, None, None
    _lineage(register, by_version)
    suffix = [w for w in chain.witnesses if w.witness_version > latest.witness_version]
    ledger_only = all(w.consumed_authorization_id is None
                      and w.current_recovery_epoch == latest.recovery_epoch
                      and w.registry_head == RC.RegistryHeadV1(latest.registry_version, latest.registry_digest)
                      for w in suffix)
    return AHEAD_UNACCEPTED, "AHEAD_LEDGER_ONLY" if ledger_only else "AHEAD_AUTHORITY_CHANGING", \
        str(head.witness_version - latest.witness_version)


def classify_presented_world(*, register: OwnerRegisterResultV1, chain: RC.ChainResultV1, environment: str,
                             authority_profile: str) -> FreshnessResultV1:
    """Compare a presented DEV authority world against the latest owner-accepted record.

    `chain` is the caller's K-WIT verification of the presented witness chain
    from genesis (`verify_witness_v2_chain`); that verification is the whole
    authenticity judgment. Freshness comes only from `register`, the owner's
    off-host copies. Internal consistency of the presented world is never
    evidence that it is current.
    """
    if not isinstance(register, OwnerRegisterResultV1) or not isinstance(chain, RC.ChainResultV1) \
            or authority_profile not in PROFILE_ENVIRONMENTS:
        return FreshnessResultV1(NOT_AUTHENTIC, REFUSED, "MALFORMED_INPUT")
    if PROFILE_ENVIRONMENTS[authority_profile] != environment:
        return FreshnessResultV1(NOT_AUTHENTIC, REFUSED, "PROFILE_MISMATCH")
    authenticity = AUTHENTIC if chain.verified else NOT_AUTHENTIC
    if not chain.verified:
        return FreshnessResultV1(authenticity, FRESHNESS_UNKNOWN, "PRESENTED_NOT_AUTHENTIC", chain.reason)
    if chain.facts.head.environment != environment:
        return FreshnessResultV1(authenticity, REFUSED, "ENVIRONMENT_MISMATCH")
    if not register.verified:
        return FreshnessResultV1(authenticity, FRESHNESS_UNKNOWN, "OWNER_REGISTER_NOT_VERIFIED",
                                 f"{register.reason}:{register.detail}" if register.detail else register.reason)
    facts = register.facts
    if facts.environment != environment:
        return FreshnessResultV1(authenticity, REFUSED, "ENVIRONMENT_MISMATCH")
    if facts.authority_profile != authority_profile:
        return FreshnessResultV1(authenticity, REFUSED, "PROFILE_MISMATCH")
    observed = {"presentedWitnessVersion": chain.facts.head.witness_version,
                "presentedWitnessDigest": chain.facts.head.digest,
                "ownerLatestWitnessVersion": facts.latest.witness_version,
                "ownerLatestWitnessDigest": facts.latest.witness_digest,
                "ownerLatestRecordVersion": facts.latest.record_version,
                "ownerRegisterHeadDigest": facts.head_digest}
    try:
        freshness, reason, detail = _classify(facts, chain.facts)
    except _Classified as classified:
        return FreshnessResultV1(authenticity, classified.freshness, classified.reason, classified.detail, observed)
    return FreshnessResultV1(authenticity, freshness, reason, detail, observed)


# -------------------------------------------------------------------- gate ---

REGISTRY_HEAD_ADVANCE = "REGISTRY_HEAD_ADVANCE"
RECOVERY_EPOCH_ADVANCE = "RECOVERY_EPOCH_ADVANCE"
SUCCESSOR_READINESS = "SUCCESSOR_READINESS"
INITIAL_CUSTODY_RELEASE = "INITIAL_CUSTODY_RELEASE"
FIRST_MEMORY = "FIRST_MEMORY"
GATED_OPERATIONS = frozenset({REGISTRY_HEAD_ADVANCE, RECOVERY_EPOCH_ADVANCE, SUCCESSOR_READINESS,
                              INITIAL_CUSTODY_RELEASE, FIRST_MEMORY})

FRESHNESS_PRECONDITION_MET = "FRESHNESS_PRECONDITION_MET"
FRESHNESS_BLOCKED = "FRESHNESS_BLOCKED"


@dataclass(frozen=True)
class FreshnessGateResultV1:
    status: str
    operation: str | None
    reason: str | None = None

    @property
    def met(self) -> bool:
        return self.status == FRESHNESS_PRECONDITION_MET


def freshness_gate(result: Any, operation: Any) -> FreshnessGateResultV1:
    """Owner-side precondition only: the presented world must be AUTHENTIC and
    exactly CURRENT. Meeting it authorizes nothing (K-ROOT, the witness, the
    hold store, and owner acceptance still decide). Every other state,
    including `AHEAD_LEDGER_ONLY`, blocks every gated operation."""
    if operation not in GATED_OPERATIONS:
        return FreshnessGateResultV1(FRESHNESS_BLOCKED, None, "UNKNOWN_OPERATION")
    if not isinstance(result, FreshnessResultV1):
        return FreshnessGateResultV1(FRESHNESS_BLOCKED, operation, "MALFORMED_INPUT")
    if not result.current:
        return FreshnessGateResultV1(FRESHNESS_BLOCKED, operation, f"{result.authenticity}:{result.freshness}")
    return FreshnessGateResultV1(FRESHNESS_PRECONDITION_MET, operation)


# ---------------------------------------------------------------- proposal ---

PROPOSED = "CANDIDATE_PROPOSED"
NOT_PROPOSED = "CANDIDATE_NOT_PROPOSED"


@dataclass(frozen=True)
class OwnerRecordCandidateV1:
    """An unsigned candidate for an owner ceremony. It is not an acceptance:
    it gains meaning only when the owner reviews it and appends it to their
    authoritative copies (PR3-D1)."""

    status: str
    reason: str | None = None
    record: Mapping[str, Any] | None = None
    record_digest: str | None = None

    @property
    def proposed(self) -> bool:
        return self.status == PROPOSED


def _record(*, environment: str, profile: str, version: int, previous: str | None, decision: str,
            genesis: str, witness: RC.RecoveryWitnessV2) -> OwnerRecordCandidateV1:
    value = {
        "recordType": RECORD_TYPE, "schemaVersion": RECORD_SCHEMA_VERSION, "environment": environment,
        "authorityProfile": profile, "recordVersion": version, "previousRecordDigest": previous,
        "decision": decision, "genesisWitnessDigest": genesis, "witnessVersion": witness.witness_version,
        "witnessDigest": witness.digest, "recoveryEpoch": witness.current_recovery_epoch.to_dict(),
        "registryVersion": witness.registry_version, "registryDigest": witness.registry_digest,
    }
    parsed = OwnerFreshnessRecordV1.from_dict(value)
    return OwnerRecordCandidateV1(PROPOSED, record=value, record_digest=parsed.digest)


def propose_genesis_record(*, chain: RC.ChainResultV1, environment: str,
                           authority_profile: str) -> OwnerRecordCandidateV1:
    """Record 1 accepts the verified V2 genesis witness, and nothing after it."""
    if not isinstance(chain, RC.ChainResultV1) or authority_profile not in PROFILE_ENVIRONMENTS:
        return OwnerRecordCandidateV1(NOT_PROPOSED, "MALFORMED_INPUT")
    if PROFILE_ENVIRONMENTS[authority_profile] != environment:
        return OwnerRecordCandidateV1(NOT_PROPOSED, "PROFILE_MISMATCH")
    if not chain.verified:
        return OwnerRecordCandidateV1(NOT_PROPOSED, "PRESENTED_NOT_AUTHENTIC")
    genesis = chain.facts.head
    if genesis.environment != environment:
        return OwnerRecordCandidateV1(NOT_PROPOSED, "ENVIRONMENT_MISMATCH")
    if len(chain.facts.witnesses) != 1 or genesis.witness_version != 1:
        return OwnerRecordCandidateV1(NOT_PROPOSED, "NOT_GENESIS")
    return _record(environment=environment, profile=authority_profile, version=1, previous=None,
                   decision=ACCEPT_CURRENT, genesis=genesis.digest, witness=genesis)


def _next(register: OwnerRegisterResultV1, chain: RC.ChainResultV1, environment: str, profile: str,
          decision: str, allowed: frozenset[str]) -> OwnerRecordCandidateV1:
    result = classify_presented_world(register=register, chain=chain, environment=environment,
                                      authority_profile=profile)
    if result.authenticity != AUTHENTIC or result.freshness not in allowed:
        return OwnerRecordCandidateV1(NOT_PROPOSED, f"{result.freshness}:{result.reason}")
    facts = register.facts
    return _record(environment=environment, profile=profile, version=facts.records[-1].record_version + 1,
                   previous=facts.head_digest, decision=decision, genesis=facts.genesis_witness_digest,
                   witness=chain.facts.head)


def propose_acceptance(*, register: OwnerRegisterResultV1, chain: RC.ChainResultV1, environment: str,
                       authority_profile: str) -> OwnerRecordCandidateV1:
    """Accept the presented head as the new latest world. Only an authentic
    descendant of the latest accepted record can be proposed: a stale,
    conflicting, rejected, or unknown world never can."""
    return _next(register, chain, environment, authority_profile, ACCEPT_CURRENT, frozenset({AHEAD_UNACCEPTED}))


def propose_rejection(*, register: OwnerRegisterResultV1, chain: RC.ChainResultV1, environment: str,
                      authority_profile: str) -> OwnerRecordCandidateV1:
    """Record the owner's refusal of the presented head (a fork or an unwanted
    descendant). A current or stale world is not rejectable: rejecting it
    would rewrite accepted history."""
    candidate = _next(register, chain, environment, authority_profile, REJECT_CANDIDATE,
                      frozenset({AHEAD_UNACCEPTED, CONFLICTING}))
    if candidate.proposed and chain.facts.head.witness_version == 1:
        return OwnerRecordCandidateV1(NOT_PROPOSED, "GENESIS_NOT_REJECTABLE")
    return candidate


def genesis_pin_consistent(register: OwnerRegisterResultV1, pin: Mapping[str, Any]) -> bool:
    """Record 1 names exactly the SW-8 owner genesis pin (same environment, same digest)."""
    try:
        parsed = WR.OwnerGenesisPinV1.from_dict(pin)
    except (OwnerProofError, TypeError):
        return False
    return (isinstance(register, OwnerRegisterResultV1) and register.verified
            and parsed.environment == register.facts.environment
            and parsed.genesis_witness_digest == register.facts.genesis_witness_digest)
