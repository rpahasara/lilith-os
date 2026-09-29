"""15B2b-B1b-3e PR-3 P3-6: owner acceptance envelope foundation (pure, offline).

Record: docs/architecture/slice-15b2b-b1b3e-pr3-owner-acceptance-envelope.md.

Evidence that the owner performed the explicit acceptance ceremony for one
exact `OwnerFreshnessRecordV1` and one exact review package, kept outside the
record so the record's identity never changes:

- `OwnerFreshnessReviewPackageV1` / `build_review_package`: the canonical,
  independently reproducible package the owner reviewed before the append.
- `OwnerFreshnessAcceptanceEnvelopeV1`: binds the record digest, the package
  digest, the genesis pin, and the owner custody set (replica IDs only). It
  is chained one-to-one with the freshness records.
- `classify_acceptance`: acceptance-evidence state (`ACCEPTANCE_*`), kept
  separate from freshness (`CURRENT`/`STALE`/…). One never downgrades into
  the other.
- `real_acceptance_block`: the source-level switch for real-profile
  acceptance writes. It was a hard block while P3-3 was incomplete; B-3
  lifts it (`REAL_ACCEPTANCE_ENABLED = True`). Lifting it authorizes
  nothing: not PR-1B (B-5), not M-B1, and not any record 1.

    record identity != acceptance evidence;  file existence != acceptance
    signature != acceptance;  model output != acceptance
    unsigned != unauthenticated storage;  signed != owner accepted
    acceptance envelope complete != any authorization (K-ROOT, registry,
        RecoveryEpoch, memory, privacy, activation, recovery, First Memory)

The envelope is unsigned (PR3-D2). Its authority comes only from the owner
ceremony and from custody of the owner copies. It holds no key and signs
nothing.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from lilith_memory.owner_proof import OwnerProofError, _digest, _exact

from . import authority_contracts as A
from . import owner_freshness as OF
from . import rotation_contracts as RC
from .contracts import ContractViolation, _canonical, _choice

# ------------------------------------------------------------------ blocking ---

# B-3: real-profile acceptance writes (freshness `append`, `append-envelope`)
# are enabled in source. Only a reviewed source change may set this; no
# input, flag, or envelope can. Setting it back to False is the reversible
# source-level disable, reported as REAL_ACCEPTANCE_DISABLED_IN_SOURCE.
#
#     REAL_ACCEPTANCE_ENABLED != PR-1B authorized (B-5) != M-B1 authorized
#     enabled != any record exists;  enabled != freshness CURRENT
REAL_PROFILES = frozenset({"DEV_SYNTHETIC"})
REAL_ACCEPTANCE_ENABLED = True
REAL_ACCEPTANCE_BLOCK_REASON = "REAL_ACCEPTANCE_DISABLED_IN_SOURCE"


def real_acceptance_block(authority_profile: str) -> str | None:
    """None when an acceptance write for this profile may proceed."""
    if authority_profile in REAL_PROFILES and not REAL_ACCEPTANCE_ENABLED:
        return REAL_ACCEPTANCE_BLOCK_REASON
    return None


# ------------------------------------------------------------------ digests ---

PACKAGE_DOMAIN = b"LILITH_OWNER_FRESHNESS_REVIEW_PACKAGE_V1\x00"
ENVELOPE_DOMAIN = b"LILITH_OWNER_FRESHNESS_ACCEPTANCE_ENVELOPE_V1\x00"
REPLICA_SET_DOMAIN = b"LILITH_OWNER_FRESHNESS_REPLICA_SET_V1\x00"
PIN_DOMAIN = b"LILITH_OWNER_GENESIS_PIN_DOCUMENT_V1\x00"
TRUST_DOMAIN = b"LILITH_OWNER_FRESHNESS_TRUST_INPUTS_V1\x00"
CHAIN_DOMAIN = b"LILITH_OWNER_FRESHNESS_PRESENTED_CHAIN_V1\x00"


def _sha(domain: bytes, value: Any) -> str:
    return hashlib.sha256(domain + _canonical(value if isinstance(value, Mapping) else {"v": value})).hexdigest()


def replica_set_digest(*, environment: str, authority_profile: str, replica_ids: Sequence[str]) -> str:
    """The owner custody set: stable replica IDs only. Never paths, devices,
    mounts, or timestamps."""
    ids = sorted(replica_ids) if isinstance(replica_ids, (list, tuple, set, frozenset)) else None
    if not ids or len(ids) != 2 or len(set(ids)) != 2 or not all(isinstance(i, str) and i for i in ids):
        raise ContractViolation("INVALID_REPLICA_SET")
    return _sha(REPLICA_SET_DOMAIN, {"environment": environment, "authorityProfile": authority_profile,
                                     "replicaIds": ids})


def genesis_pin_digest(pin: Mapping[str, Any]) -> str:
    from . import witness_readiness as WR
    WR.OwnerGenesisPinV1.from_dict(pin)
    return _sha(PIN_DOMAIN, pin)


def trust_inputs_digest(trust_document: Mapping[str, Any]) -> str:
    if not isinstance(trust_document, Mapping):
        raise ContractViolation("INVALID_TRUST_INPUTS")
    return _sha(TRUST_DOMAIN, trust_document)


def presented_chain_digest(chain: RC.WitnessChainFactsV1) -> str:
    return _sha(CHAIN_DOMAIN, {"witnessDigests": [w.digest for w in chain.witnesses]})


# ------------------------------------------------------------ review package ---

PACKAGE_TYPE = "LILITH_OWNER_FRESHNESS_REVIEW_PACKAGE"
RECORD_1, SUCCESSOR = "RECORD_1", "SUCCESSOR"
RECORD_1_REQUIRED_EVIDENCE = frozenset({"PR2_REVALIDATION", "P3_3_INDEPENDENCE"})
PACKAGE_FIELDS = frozenset({
    "packageType", "schemaVersion", "environment", "authorityProfile", "packageKind", "decision",
    "candidateRecordVersion", "candidateRecordDigest", "priorRecordDigest", "genesisPinDigest", "replicaSetDigest",
    "trustInputsDigest", "presentedChainDigest", "presentedChainLength", "presentedHead", "freshnessBefore",
    "attachedEvidence",
})


def review_package_digest(package: Mapping[str, Any]) -> str:
    _exact(package, PACKAGE_FIELDS)
    return _sha(PACKAGE_DOMAIN, package)


def _head(witness: RC.RecoveryWitnessV2, chain: RC.WitnessChainFactsV1) -> dict[str, Any]:
    return {"witnessVersion": witness.witness_version, "witnessDigest": witness.digest,
            "recoveryEpoch": witness.current_recovery_epoch.to_dict(), "registryVersion": witness.registry_version,
            "registryDigest": witness.registry_digest, "ledgerSequence": witness.ledger_sequence,
            "ledgerHead": witness.ledger_head, "witnessKeyId": witness.witness_key_id,
            "consumedAuthorizationIds": sorted(chain.consumed_authorization_ids)}


def build_review_package(*, prior_records: Sequence[Mapping[str, Any]], chain: RC.ChainResultV1,
                         candidate_record: Mapping[str, Any], trust_document: Mapping[str, Any],
                         pin: Mapping[str, Any], replica_ids: Sequence[str], environment: str,
                         authority_profile: str, attached_evidence: Mapping[str, str]) -> dict[str, Any]:
    """Rebuild the owner review package from owner-held inputs.

    Everything except `attachedEvidence` (digests of owner-held evidence
    outside the tool, such as the PR-2 revalidation and P3-3 independence
    records) is re-derived, and the candidate record is re-proposed from the
    prior register and the chain. A hand-edited or mismatched candidate
    therefore cannot enter a package. Raises `ContractViolation` on any
    inconsistency.
    """
    if OF.PROFILE_ENVIRONMENTS.get(authority_profile) != environment:
        raise ContractViolation("PROFILE_MISMATCH")
    if not isinstance(chain, RC.ChainResultV1) or not chain.verified:
        raise ContractViolation("PRESENTED_NOT_AUTHENTIC")
    if not isinstance(attached_evidence, Mapping) or not all(
            isinstance(k, str) and k and isinstance(v, str) for k, v in attached_evidence.items()):
        raise ContractViolation("INVALID_ATTACHED_EVIDENCE")
    for value in attached_evidence.values():
        _digest(value, "attached_evidence")
    record = OF.OwnerFreshnessRecordV1.from_dict(candidate_record)
    prior = list(prior_records)
    pin_digest = genesis_pin_digest(pin)
    if pin["genesisWitnessDigest"] != record.genesis_witness_digest or pin["environment"] != environment:
        raise ContractViolation("GENESIS_PIN_MISMATCH")
    if not prior:
        kind = RECORD_1
        if not RECORD_1_REQUIRED_EVIDENCE <= set(attached_evidence):
            raise ContractViolation("RECORD_1_EVIDENCE_MISSING")
        register = OF.OwnerRegisterResultV1(OF.REGISTER_NOT_VERIFIED, "OWNER_REGISTER_EMPTY")
        expected = OF.propose_genesis_record(chain=chain, environment=environment, authority_profile=authority_profile)
        previous_digest = None
    else:
        kind = SUCCESSOR
        register = OF.reconcile_owner_replicas([prior, prior])
        propose = OF.propose_acceptance if record.decision == OF.ACCEPT_CURRENT else OF.propose_rejection
        expected = propose(register=register, chain=chain, environment=environment, authority_profile=authority_profile)
        previous_digest = register.facts.head_digest if register.verified else None
    if not expected.proposed or dict(expected.record) != dict(candidate_record):
        raise ContractViolation("CANDIDATE_NOT_DERIVABLE")
    before = OF.classify_presented_world(register=register, chain=chain, environment=environment,
                                         authority_profile=authority_profile)
    return {
        "packageType": PACKAGE_TYPE, "schemaVersion": 1, "environment": environment,
        "authorityProfile": authority_profile, "packageKind": kind, "decision": record.decision,
        "candidateRecordVersion": record.record_version, "candidateRecordDigest": record.digest,
        "priorRecordDigest": previous_digest, "genesisPinDigest": pin_digest,
        "replicaSetDigest": replica_set_digest(environment=environment, authority_profile=authority_profile,
                                               replica_ids=replica_ids),
        "trustInputsDigest": trust_inputs_digest(trust_document),
        "presentedChainDigest": presented_chain_digest(chain.facts),
        "presentedChainLength": len(chain.facts.witnesses),
        "presentedHead": _head(chain.facts.head, chain.facts),
        "freshnessBefore": {"authenticity": before.authenticity, "freshness": before.freshness,
                            "reason": before.reason},
        "attachedEvidence": dict(sorted(attached_evidence.items())),
    }


# ------------------------------------------------------------------ envelope ---

ENVELOPE_TYPE = "LILITH_OWNER_FRESHNESS_ACCEPTANCE_ENVELOPE"
CEREMONY_VERSION = "LILITH_OWNER_FRESHNESS_CEREMONY_V1"          # the P3-4 ten-step + envelope steps
EXPLICIT_OWNER_DIGEST_CONFIRMATION = "EXPLICIT_OWNER_DIGEST_CONFIRMATION"
ACCEPTANCE_METHODS = frozenset({EXPLICIT_OWNER_DIGEST_CONFIRMATION})
# Reserved for a future, separately scoped hardware owner-presence proof. Refused in V1.
RESERVED_METHODS = frozenset({"HARDWARE_OWNER_PRESENCE_V1"})
ENVELOPE_FIELDS = frozenset({
    "envelopeType", "schemaVersion", "environment", "authorityProfile", "freshnessRecordVersion",
    "freshnessRecordDigest", "decision", "previousAcceptanceEnvelopeDigest", "genesisPinDigest",
    "ownerReviewPackageDigest", "replicaSetDigest", "ceremonyVersion", "acceptanceMethod",
})


def envelope_digest(envelope: Mapping[str, Any]) -> str:
    _exact(envelope, ENVELOPE_FIELDS)
    return _sha(ENVELOPE_DOMAIN, envelope)


@dataclass(frozen=True)
class OwnerFreshnessAcceptanceEnvelopeV1:
    """Owner-acceptance evidence for exactly one freshness record (1:1, same
    version). Unsigned. No self-digest, no timestamp, no signature field."""

    environment: str
    authority_profile: str
    freshness_record_version: int
    freshness_record_digest: str
    decision: str
    previous_envelope_digest: str | None
    genesis_pin_digest: str
    review_package_digest: str
    replica_set_digest: str
    digest: str

    @classmethod
    def from_dict(cls, value: Any) -> OwnerFreshnessAcceptanceEnvelopeV1:
        _exact(value, ENVELOPE_FIELDS)
        if value["envelopeType"] != ENVELOPE_TYPE or type(value["schemaVersion"]) is not int \
                or value["schemaVersion"] != 1:
            raise ContractViolation("UNSUPPORTED_SCHEMA_VERSION")
        profile = _choice(value["authorityProfile"], frozenset(OF.PROFILE_ENVIRONMENTS), "authority_profile")
        if value["environment"] != OF.PROFILE_ENVIRONMENTS[profile]:
            raise ContractViolation("PROFILE_ENVIRONMENT_MISMATCH")
        if value["ceremonyVersion"] != CEREMONY_VERSION:
            raise ContractViolation("UNSUPPORTED_CEREMONY_VERSION")
        if value["acceptanceMethod"] not in ACCEPTANCE_METHODS:
            raise ContractViolation("UNSUPPORTED_ACCEPTANCE_METHOD")
        version = A._int(value["freshnessRecordVersion"], "freshness_record_version", 1)
        previous = value["previousAcceptanceEnvelopeDigest"]
        if (version == 1) != (previous is None):
            raise ContractViolation("INVALID_ENVELOPE_CHAIN")
        return cls(value["environment"], profile, version,
                   _digest(value["freshnessRecordDigest"], "freshness_record_digest"),
                   _choice(value["decision"], OF.DECISIONS, "decision"),
                   None if previous is None else _digest(previous, "previous_envelope_digest"),
                   _digest(value["genesisPinDigest"], "genesis_pin_digest"),
                   _digest(value["ownerReviewPackageDigest"], "owner_review_package_digest"),
                   _digest(value["replicaSetDigest"], "replica_set_digest"),
                   envelope_digest(value))


def build_envelope(*, record: Mapping[str, Any], package: Mapping[str, Any],
                   previous_envelope: Mapping[str, Any] | None) -> dict[str, Any]:
    """The only envelope for this record + package + predecessor."""
    parsed = OF.OwnerFreshnessRecordV1.from_dict(record)
    package_digest = review_package_digest(package)
    if package["candidateRecordDigest"] != parsed.digest or package["candidateRecordVersion"] != parsed.record_version \
            or package["decision"] != parsed.decision or package["environment"] != parsed.environment \
            or package["authorityProfile"] != parsed.authority_profile:
        raise ContractViolation("PACKAGE_RECORD_MISMATCH")
    if (parsed.record_version == 1) != (previous_envelope is None):
        raise ContractViolation("INVALID_ENVELOPE_CHAIN")
    return {
        "envelopeType": ENVELOPE_TYPE, "schemaVersion": 1, "environment": parsed.environment,
        "authorityProfile": parsed.authority_profile, "freshnessRecordVersion": parsed.record_version,
        "freshnessRecordDigest": parsed.digest, "decision": parsed.decision,
        "previousAcceptanceEnvelopeDigest": None if previous_envelope is None else envelope_digest(previous_envelope),
        "genesisPinDigest": package["genesisPinDigest"], "ownerReviewPackageDigest": package_digest,
        "replicaSetDigest": package["replicaSetDigest"], "ceremonyVersion": CEREMONY_VERSION,
        "acceptanceMethod": EXPLICIT_OWNER_DIGEST_CONFIRMATION,
    }


# ------------------------------------------------------------ acceptance state ---

ACCEPTANCE_NOT_PRESENT = "ACCEPTANCE_NOT_PRESENT"
ACCEPTANCE_PARTIAL = "ACCEPTANCE_PARTIAL"
ACCEPTANCE_COMPLETE = "ACCEPTANCE_COMPLETE"
ACCEPTANCE_CONFLICTING = "ACCEPTANCE_CONFLICTING"
ACCEPTANCE_INVALID = "ACCEPTANCE_INVALID"
ACCEPTANCE_UNKNOWN = "ACCEPTANCE_UNKNOWN"
ACCEPTANCE_STATES = (ACCEPTANCE_NOT_PRESENT, ACCEPTANCE_PARTIAL, ACCEPTANCE_COMPLETE, ACCEPTANCE_CONFLICTING,
                     ACCEPTANCE_INVALID, ACCEPTANCE_UNKNOWN)

BUNDLE_FIELDS = frozenset({"envelope", "package"})


@dataclass(frozen=True)
class AcceptanceResultV1:
    state: str
    reason: str | None = None
    detail: str | None = None
    evidenced_record_version: int = 0

    @property
    def complete(self) -> bool:
        return self.state == ACCEPTANCE_COMPLETE


class _State(Exception):
    def __init__(self, state: str, reason: str, detail: str | None = None):
        super().__init__(reason)
        self.state, self.reason, self.detail = state, reason, detail


def _validate_copy(bundles: Sequence[Mapping[str, Any]], records: Sequence[OF.OwnerFreshnessRecordV1], *,
                   environment: str, profile: str, replica_set: str, pin_digest: str) -> tuple[str, ...]:
    """Envelope-chain and binding checks for one custody copy. Returns the envelope digests."""
    digests: list[str] = []
    previous: str | None = None
    for index, bundle in enumerate(bundles, start=1):
        try:
            _exact(bundle, BUNDLE_FIELDS)
            envelope = OwnerFreshnessAcceptanceEnvelopeV1.from_dict(bundle["envelope"])
            package_digest = review_package_digest(bundle["package"])
        except (OwnerProofError, TypeError, KeyError) as exc:
            raise _State(ACCEPTANCE_INVALID, "ENVELOPE_MALFORMED", f"{index}:{exc}") from exc
        package = bundle["package"]
        if envelope.freshness_record_version != index:
            raise _State(ACCEPTANCE_INVALID, "ENVELOPE_VERSION_NOT_SUCCESSOR", str(index))
        if envelope.previous_envelope_digest != previous:
            raise _State(ACCEPTANCE_INVALID, "PREVIOUS_ENVELOPE_DIGEST_MISMATCH", str(index))
        if (envelope.environment, envelope.authority_profile) != (environment, profile):
            raise _State(ACCEPTANCE_INVALID, "ENVELOPE_PROFILE_MISMATCH", str(index))
        if envelope.replica_set_digest != replica_set:
            raise _State(ACCEPTANCE_INVALID, "ENVELOPE_REPLICA_SET_MISMATCH", str(index))
        if envelope.genesis_pin_digest != pin_digest:
            raise _State(ACCEPTANCE_INVALID, "ENVELOPE_GENESIS_PIN_MISMATCH", str(index))
        if envelope.review_package_digest != package_digest:
            raise _State(ACCEPTANCE_INVALID, "ENVELOPE_PACKAGE_MISMATCH", str(index))
        if index > len(records):
            raise _State(ACCEPTANCE_CONFLICTING, "ENVELOPE_AHEAD_OF_REGISTER", str(index))
        record = records[index - 1]
        if envelope.freshness_record_digest != record.digest or envelope.decision != record.decision:
            raise _State(ACCEPTANCE_INVALID, "ENVELOPE_RECORD_MISMATCH", str(index))
        prior = records[index - 2].digest if index > 1 else None
        if package["candidateRecordDigest"] != record.digest or package["priorRecordDigest"] != prior \
                or package["replicaSetDigest"] != replica_set or package["genesisPinDigest"] != pin_digest \
                or package["candidateRecordVersion"] != index or package["decision"] != record.decision \
                or package["packageKind"] != (RECORD_1 if index == 1 else SUCCESSOR):
            raise _State(ACCEPTANCE_INVALID, "PACKAGE_BINDING_MISMATCH", str(index))
        previous = envelope.digest
        digests.append(envelope.digest)
    return tuple(digests)


def classify_acceptance(*, register: OF.OwnerRegisterResultV1, copies: Any, replica_ids: Sequence[str],
                        pin: Mapping[str, Any]) -> AcceptanceResultV1:
    """Owner-acceptance evidence for the latest freshness record, from the two
    custody copies of the acceptance store. Never a freshness state."""
    if not isinstance(register, OF.OwnerRegisterResultV1) or not register.verified:
        reason = register.reason if isinstance(register, OF.OwnerRegisterResultV1) else "MALFORMED_INPUT"
        return AcceptanceResultV1(ACCEPTANCE_UNKNOWN, "OWNER_REGISTER_NOT_VERIFIED", reason)
    if not isinstance(copies, (list, tuple)) or len(copies) != 2 or any(c is None for c in copies):
        return AcceptanceResultV1(ACCEPTANCE_UNKNOWN, "ACCEPTANCE_COPY_MISSING")
    facts = register.facts
    try:
        replica_set = replica_set_digest(environment=facts.environment, authority_profile=facts.authority_profile,
                                         replica_ids=replica_ids)
        pin_digest = genesis_pin_digest(pin)
    except (OwnerProofError, TypeError, KeyError):
        return AcceptanceResultV1(ACCEPTANCE_UNKNOWN, "ACCEPTANCE_INPUT_MALFORMED")
    if pin.get("genesisWitnessDigest") != facts.genesis_witness_digest:
        return AcceptanceResultV1(ACCEPTANCE_INVALID, "ENVELOPE_GENESIS_PIN_MISMATCH")
    try:
        sequences = [_validate_copy(list(c), facts.records, environment=facts.environment,
                                    profile=facts.authority_profile, replica_set=replica_set, pin_digest=pin_digest)
                     for c in copies]
    except _State as state:
        return AcceptanceResultV1(state.state, state.reason, state.detail)
    except TypeError:
        return AcceptanceResultV1(ACCEPTANCE_UNKNOWN, "ACCEPTANCE_INPUT_MALFORMED")
    latest = facts.records[-1].record_version
    left, right = sequences
    if left != right:
        shorter, longer = sorted((left, right), key=len)
        if longer[:len(shorter)] != shorter:
            return AcceptanceResultV1(ACCEPTANCE_CONFLICTING, "ACCEPTANCE_COPIES_FORKED")
        if len(longer) == latest:
            return AcceptanceResultV1(ACCEPTANCE_PARTIAL, "ACCEPTANCE_ON_ONE_COPY", str(latest), len(shorter))
        return AcceptanceResultV1(ACCEPTANCE_NOT_PRESENT, "LATEST_RECORD_NOT_EVIDENCED", str(latest), len(shorter))
    if len(left) < latest:
        return AcceptanceResultV1(ACCEPTANCE_NOT_PRESENT, "LATEST_RECORD_NOT_EVIDENCED", str(latest), len(left))
    return AcceptanceResultV1(ACCEPTANCE_COMPLETE, None, None, latest)


REAL_ACCEPTANCE_GATE_MET = "REAL_ACCEPTANCE_GATE_MET"
REAL_ACCEPTANCE_GATE_BLOCKED = "REAL_ACCEPTANCE_GATE_BLOCKED"


def real_acceptance_gate(result: Any, *, authority_profile: str) -> tuple[str, str | None]:
    """The gate a REAL (non-synthetic) step would use. A TEST_ONLY (synthetic)
    envelope never satisfies it, and while real acceptance is disabled in
    source nothing does. It has no production caller; it is not PR-1B
    authorization."""
    if authority_profile not in REAL_PROFILES:
        return REAL_ACCEPTANCE_GATE_BLOCKED, "SYNTHETIC_PROFILE"
    block = real_acceptance_block(authority_profile)
    if block is not None:
        return REAL_ACCEPTANCE_GATE_BLOCKED, block
    if not isinstance(result, AcceptanceResultV1) or not result.complete:
        return REAL_ACCEPTANCE_GATE_BLOCKED, "ACCEPTANCE_NOT_COMPLETE"
    return REAL_ACCEPTANCE_GATE_MET, None
