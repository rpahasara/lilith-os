"""15B2b-B1b-3e Source Prep B: successor readiness and compromise recovery (SW-1, SW-9; TEST-ONLY, pure).

Design: docs/architecture/slice-15b2b-b1b3e-source-prep-b-design.md.
Record: docs/architecture/slice-15b2b-b1b3e-source-prep-b-successor-custody.md.

Everything here is recomputed from verified authoritative inputs on every
call: the Prep A witness chain (owner-pinned genesis, K-WIT), the K-ROOT
registry at every witnessed head, and the re-verified K-ROOT authorization
behind every transition. No latch, flag file, or new state owner is created,
and no new authority contract is introduced.

- `verify_history`: the verified chain with each head's registry and each
  transition's retained authorization. Story-1..3 inputs, re-verified.
- `compromise_epoch_reason` (§10.3): after a verified marking of the CURRENT
  issuance key, no successor in that epoch is ever ready:
  `COMPROMISE_EPOCH_ADVANCE_REQUIRED`, cleared only by the verified
  `KEY_COMPROMISE` epoch advance out of that epoch.
  `owner signing error != valid readiness`.
- `evaluate_compromise_recovery` (SW-9, RR-22): marking head advance first,
  then the KEY_COMPROMISE epoch advance; never collapsed.
- `derive_key_transition` / `AuthorityKeyTransitionV1` (RR-23): a derived,
  reproducible, NON-AUTHORITY report. Never required as an authority proof.
- `evaluate_recovery_gate` (RR-28): the narrow C-4 gate for a future signer
  that still holds the COMPROMISED key. Pure; not wired into any signer.
  `private key loaded != issuance authority`.
- `evaluate_successor_readiness`: Prep A readiness with the boolean
  `hold_present` superseded by a bound `CeremonyHoldV1`, split into
  HOLD_RELEASE_ELIGIBILITY and FULL_READINESS.
  `hold-release eligibility != readiness`; `hold release != S_CURRENT`.
- `authorize_custody_step` / `verify_destruction_order` (SW-1): custody
  moves and predecessor destruction gated on the authority head and the hold.
  `filesystem contents alone never justify a transition`.

Threat limit (unchanged): a chain, pointer, registries, and ledger restored
together are CONSISTENT at an old head. Whole-host rollback is not detected.
"""

from __future__ import annotations

import dataclasses
import hashlib
from dataclasses import dataclass, field
from typing import Any, ClassVar, Mapping, Sequence

from lilith_memory.owner_proof import OwnerProofError

from . import authority_contracts as A
from . import recovery_contracts as R
from . import rotation_contracts as RC
from . import successor_custody as SC
from . import witness_readiness as WR


class _Reject(Exception):
    def __init__(self, reason: str, detail: str | None = None):
        super().__init__(reason)
        self.reason = reason
        self.detail = detail


def _require(condition: bool, reason: str, detail: str | None = None) -> None:
    if not condition:
        raise _Reject(reason, detail)


SCOPE = (A.OWNER_ACTOR, A.OWNER_MEMORY_OPERATION)
HEAD_ADVANCE = "HEAD_ADVANCE"
EPOCH_ADVANCE = "EPOCH_ADVANCE"
COMPROMISE_MARKING = "COMPROMISE_MARKING"
SUCCESSOR_ROTATION = "SUCCESSOR_ROTATION"
KEY_COMPROMISE = "KEY_COMPROMISE"


# ---------------------------------------------------------- verified history ---

@dataclass(frozen=True)
class TransitionStepV1:
    """One executed authority transition of the verified chain (derived)."""

    witness_version: int
    kind: str                       # HEAD_ADVANCE | EPOCH_ADVANCE
    reason: str                     # the re-verified K-ROOT authorization's reason
    authorization_id: str
    prior_epoch: A.RecoveryEpochV1
    epoch: A.RecoveryEpochV1
    prior_current: str | None       # OWNER_ACTOR issuance key before
    current: str | None             # OWNER_ACTOR issuance key after
    marked_compromised: tuple[str, ...]


@dataclass(frozen=True)
class VerifiedHistoryV1:
    """A CONSISTENT witness chain from the owner-pinned genesis, every head's
    K-ROOT registry, and every transition's re-verified authorization."""

    chain: RC.WitnessChainFactsV1
    registries: tuple[A.AuthorityRegistryV1, ...]     # aligned with chain.witnesses
    authorizations: Mapping[str, Mapping[str, Any]]
    steps: tuple[TransitionStepV1, ...]

    @property
    def head(self) -> RC.RecoveryWitnessV2:
        return self.chain.head

    @property
    def genesis(self) -> RC.RecoveryWitnessV2:
        return self.chain.witnesses[0]

    @property
    def head_registry(self) -> A.AuthorityRegistryV1:
        return self.registries[-1]


HISTORY_REASONS = (
    "HISTORY_INPUT_MALFORMED",
    "HISTORY_WITNESS_NOT_CONSISTENT",
    "HISTORY_AUTHORIZATION_NOT_VERIFIED",
    "HISTORY_REGISTRY_NOT_VERIFIED",
    "HISTORY_MULTIPLE_CURRENT_KEYS",
)


def _current_key(registry: A.AuthorityRegistryV1) -> str | None:
    ids = RC.current_issuance_keys(registry)[SCOPE]
    if len(ids) > 1:
        raise _Reject("HISTORY_MULTIPLE_CURRENT_KEYS")
    return ids[0] if ids else None


def _compromised(registry: A.AuthorityRegistryV1) -> frozenset[str]:
    return frozenset(key_id for key_id, record in registry.keys.items() if record.compromised)


def verify_history(*, store: WR.WitnessStoreContextV1, witness_store: WR.WitnessStoreObservationV1,
                   head_registries: Sequence[Mapping[str, Any]]) -> tuple[VerifiedHistoryV1 | None, str | None, str | None]:
    """(history, None, None) or (None, reason, detail). Readers never repair:
    a pointer that needs a roll-forward is not CONSISTENT here."""
    try:
        _require(isinstance(store, WR.WitnessStoreContextV1) and isinstance(witness_store, WR.WitnessStoreObservationV1)
                 and isinstance(head_registries, (list, tuple)), "HISTORY_INPUT_MALFORMED")
        recovery = WR.classify_witness_store(observation=witness_store, context=store)
        _require(recovery.classification == WR.CONSISTENT and recovery.chain is not None,
                 "HISTORY_WITNESS_NOT_CONSISTENT", recovery.classification)
        chain = recovery.chain
        history = WR.verify_authorization_history(chain=chain, retained=recovery.retained,
                                                  register=store.owner_register, registry_root=store.registry_root)
        _require(history.verified, "HISTORY_AUTHORIZATION_NOT_VERIFIED",
                 f"{history.reason}:{history.detail}" if history.detail else history.reason)
        reason, detail = WR.verify_head_registry_history(chain=chain, registries=list(head_registries),
                                                         registry_root=store.registry_root)
        _require(reason is None, "HISTORY_REGISTRY_NOT_VERIFIED", f"{reason}:{detail}")
        by_digest: dict[str, Mapping[str, Any]] = {}
        for registry in head_registries:
            try:
                by_digest.setdefault(RC.registry_digest(registry), registry)
            except (OwnerProofError, TypeError, KeyError) as exc:
                raise _Reject("HISTORY_INPUT_MALFORMED") from exc
        parsed = []
        for witness in chain.witnesses:
            at_head = RC.verify_registry_at_witness_head(witness=witness, registry=by_digest.get(witness.registry_digest),
                                                         registry_root=store.registry_root)
            _require(at_head.verified, "HISTORY_REGISTRY_NOT_VERIFIED", f"{witness.witness_version}:{at_head.reason}")
            parsed.append(at_head.registry)
        documents = {authorization_id: WR.parse_document_bytes(raw) for authorization_id, raw in recovery.retained.items()
                     if authorization_id in chain.consumed_authorization_ids}
        steps = []
        for index in range(1, len(chain.witnesses)):
            before, entry = chain.witnesses[index - 1], chain.witnesses[index]
            if entry.consumed_authorization_id is None:
                continue
            epoch_changed = R.compare_epochs(before.current_recovery_epoch, entry.current_recovery_epoch) != R.EPOCH_EQUAL
            prior_registry, registry = parsed[index - 1], parsed[index]
            steps.append(TransitionStepV1(
                entry.witness_version, EPOCH_ADVANCE if epoch_changed else HEAD_ADVANCE,
                documents[entry.consumed_authorization_id]["reason"], entry.consumed_authorization_id,
                before.current_recovery_epoch, entry.current_recovery_epoch, _current_key(prior_registry),
                _current_key(registry), tuple(sorted(_compromised(registry) - _compromised(prior_registry)))))
        _current_key(parsed[-1])
    except _Reject as rejected:
        return None, rejected.reason, rejected.detail
    return VerifiedHistoryV1(chain, tuple(parsed), documents, tuple(steps)), None, None


# ------------------------------------------- compromise-epoch rule (§10.3) ---

COMPROMISE_EPOCH_ADVANCE_REQUIRED = "COMPROMISE_EPOCH_ADVANCE_REQUIRED"


def compromise_epoch_reason(history: VerifiedHistoryV1) -> tuple[str | None, str | None]:
    """(COMPROMISE_EPOCH_ADVANCE_REQUIRED, detail) or (None, None).

    Triggered by the verified lifecycle FACT, not by the reason label: any
    in-epoch head transition that turns the then-current OWNER_ACTOR issuance
    key COMPROMISED (the accepted `COMPROMISE_MARKING`, or a mistaken K-ROOT
    registry doing the same under another reason). It clears only when the
    epoch advance immediately out of that epoch is a re-verified
    `KEY_COMPROMISE` advance executed into the chain. An advance out of that
    epoch under any other reason never clears it (fail closed; §10.3
    "through a re-verified EpochAdvanceAuthorizationV1 with reason
    KEY_COMPROMISE"). Recomputed from verified history; no latch exists.
    """
    for index, step in enumerate(history.steps):
        if step.kind != HEAD_ADVANCE or step.prior_current is None or step.prior_current not in step.marked_compromised:
            continue
        detail = f"{step.prior_current}@E{step.epoch.counter}:w{step.witness_version}"
        advance = next((later for later in history.steps[index + 1:]
                        if later.kind == EPOCH_ADVANCE and later.prior_epoch == step.epoch), None)
        if advance is None:
            return COMPROMISE_EPOCH_ADVANCE_REQUIRED, detail
        if advance.reason != KEY_COMPROMISE:
            return COMPROMISE_EPOCH_ADVANCE_REQUIRED, f"{detail}:ADVANCE_REASON_{advance.reason}"
    return None, None


# --------------------------------------------- SW-9 recovery sequence (RR-22) ---

RECOVERY_NOT_STARTED = "RECOVERY_NOT_STARTED"
RECOVERY_MARKED = "RECOVERY_MARKED"                  # marking committed; epoch advance pending (C-4 window)
RECOVERY_EPOCH_ADVANCED = "RECOVERY_EPOCH_ADVANCED"  # KEY_COMPROMISE advance committed; successor current
RECOVERY_INVALID = "RECOVERY_INVALID"

COMPROMISE_RECOVERY_REASONS = (
    "RECOVERY_INPUT_MALFORMED",
    "PREDECESSOR_NEVER_CURRENT",
    "MARKING_NOT_CURRENT_KEY",
    "SUCCESSOR_BEFORE_MARKING",
    "EPOCH_ADVANCE_WITHOUT_MARKING",
    "WRONG_MARKING_KEY",
    "MARKING_REASON_INVALID",
    "MARKING_INCLUDES_SUCCESSOR",
    "SAME_EPOCH_SUCCESSOR_AFTER_MARKING",
    "WRONG_EPOCH_ADVANCE_REASON",
    "RECOVERY_SUCCESSOR_INVALID",
)


@dataclass(frozen=True)
class CompromiseRecoveryResultV1:
    phase: str
    reason: str | None = None
    detail: str | None = None
    facts: Mapping[str, Any] = field(default_factory=dict)

    @property
    def valid(self) -> bool:
        return self.phase != RECOVERY_INVALID


def evaluate_compromise_recovery(history: VerifiedHistoryV1, *, predecessor_key_id: str) -> CompromiseRecoveryResultV1:
    """SW-9: does the verified history follow the accepted current-key order?

    1. P is the current issuance key at a witnessed head in epoch E;
    2. an in-epoch head advance, authorized `COMPROMISE_MARKING`, marks P
       COMPROMISED and names no current key;
    3. no head advance in E names a successor after that;
    4. the epoch advance out of E is authorized `KEY_COMPROMISE` and names the
       successor current in E+1.

    RECOVERY_MARKED is the only phase in which the C-4 adoption may run;
    RECOVERY_EPOCH_ADVANCED is the only phase in which C-4 quarantine may run.
    Neither is S_CURRENT. Stale witness heads, skipped or unregistered
    authorizations, and replays fail earlier, in `verify_history`.
    """
    facts: dict[str, Any] = {"authorityGranted": False, "predecessorKeyId": predecessor_key_id}

    def invalid(reason: str, detail: str | None = None) -> CompromiseRecoveryResultV1:
        return CompromiseRecoveryResultV1(RECOVERY_INVALID, reason, detail, facts)

    if not isinstance(history, VerifiedHistoryV1) or not isinstance(predecessor_key_id, str):
        return invalid("RECOVERY_INPUT_MALFORMED")
    currents = [_current_key(registry) for registry in history.registries]
    marks = [step for step in history.steps if predecessor_key_id in step.marked_compromised]
    if predecessor_key_id not in currents:
        return invalid("MARKING_NOT_CURRENT_KEY" if marks else "PREDECESSOR_NEVER_CURRENT")
    first_current = history.chain.witnesses[currents.index(predecessor_key_id)].witness_version
    marking = None
    others: list[str] = []
    for step in history.steps:
        if step.witness_version <= first_current:
            continue
        if step.prior_current == predecessor_key_id and step.current != predecessor_key_id:
            if step.kind == EPOCH_ADVANCE:
                return invalid("EPOCH_ADVANCE_WITHOUT_MARKING", str(step.witness_version))
            if predecessor_key_id not in step.marked_compromised:
                return invalid("MARKING_NOT_CURRENT_KEY" if marks else "SUCCESSOR_BEFORE_MARKING",
                               str(step.witness_version))
            if step.reason != COMPROMISE_MARKING:
                return invalid("MARKING_REASON_INVALID", step.reason)
            if step.current is not None:
                return invalid("MARKING_INCLUDES_SUCCESSOR", step.current)
            marking = step
            break
        if step.reason == COMPROMISE_MARKING and step.marked_compromised:
            others.extend(step.marked_compromised)
    if marking is None:
        if others:
            return CompromiseRecoveryResultV1(RECOVERY_NOT_STARTED, "WRONG_MARKING_KEY", ",".join(others), facts)
        return CompromiseRecoveryResultV1(RECOVERY_NOT_STARTED, None, None, facts)
    facts.update(markingWitnessVersion=marking.witness_version, markingAuthorizationId=marking.authorization_id,
                 markedEpochCounter=marking.epoch.counter)
    advance = None
    for step in history.steps:
        if step.witness_version <= marking.witness_version:
            continue
        if step.kind == HEAD_ADVANCE and step.epoch == marking.epoch:
            if step.current is not None:
                return invalid("SAME_EPOCH_SUCCESSOR_AFTER_MARKING", f"{step.current}:w{step.witness_version}")
            continue
        if step.kind == EPOCH_ADVANCE and step.prior_epoch == marking.epoch:
            if step.reason != KEY_COMPROMISE:
                return invalid("WRONG_EPOCH_ADVANCE_REASON", step.reason)
            if step.current is None or step.current == predecessor_key_id:
                return invalid("RECOVERY_SUCCESSOR_INVALID")
            advance = step
            break
    if advance is None:
        return CompromiseRecoveryResultV1(RECOVERY_MARKED, None, None, facts)
    facts.update(epochAdvanceWitnessVersion=advance.witness_version,
                 epochAdvanceAuthorizationId=advance.authorization_id, recoveredEpochCounter=advance.epoch.counter,
                 successorKeyId=advance.current)
    return CompromiseRecoveryResultV1(RECOVERY_EPOCH_ADVANCED, None, None, facts)


# ------------------------------------ derived key transition (RR-23, non-authority) ---

AUTHORITY_KEY_TRANSITION_TYPE = "LILITH_AUTHORITY_KEY_TRANSITION"
AUTHORITY_KEY_TRANSITION_SCHEMA_VERSION = 1

KEY_TRANSITION_REASONS = (
    "NO_CURRENT_ISSUANCE_KEY",
    "INITIAL_KEY_MISMATCH",
    "TRANSITION_KIND_NOT_SUPPORTED",
    "TRANSITION_SAME_EPOCH_AFTER_MARKING",
    "COMBINED_COMPROMISE_AND_SUCCESSOR",
    "TRANSITION_REASON_UNEXPECTED",
    "TRANSITION_PREDECESSOR_NOT_SUPERSEDED",
    "EPOCH_ADVANCE_WITHOUT_MARKING",
    "COMPROMISE_RECOVERY_SEQUENCE_INVALID",
    "SUCCESSOR_KEY_ID_NOT_DERIVED",
)


@dataclass(frozen=True)
class KeyTransitionV1:
    """The ladder the verified history shows for the head's current key."""

    kind: str
    predecessor_key_id: str | None
    successor_key_id: str
    ceremony_id: str
    establishing_witness_version: int
    ceremony_start_witness_version: int   # a primary HELD hold must predate this entry

    authority_granted: ClassVar[bool] = False


def derive_key_transition(history: VerifiedHistoryV1, *,
                          profile: SC.CustodyProfileV1 = SC.DEV_SYNTHETIC_CUSTODY_PROFILE
                          ) -> tuple[KeyTransitionV1 | None, str | None, str | None]:
    try:
        successor = _current_key(history.head_registry)
        _require(successor is not None, "NO_CURRENT_ISSUANCE_KEY")
        if history.head.registry_head == history.genesis.registry_head:
            _require(successor == profile.initial_key_id, "INITIAL_KEY_MISMATCH", successor)
            return KeyTransitionV1(SC.INITIAL_CUSTODY, None, successor,
                                   SC.initial_ceremony_id(profile.environment, profile.initial_key_id), 1, 1), None, None
        establishing = next((step for step in reversed(history.steps) if step.current != step.prior_current), None)
        _require(establishing is not None, "TRANSITION_KIND_NOT_SUPPORTED", "HEAD_MOVED_WITHOUT_KEY_CHANGE")
        if establishing.kind == HEAD_ADVANCE:
            _require(establishing.prior_current is not None, "TRANSITION_SAME_EPOCH_AFTER_MARKING")
            _require(establishing.prior_current not in establishing.marked_compromised,
                     "COMBINED_COMPROMISE_AND_SUCCESSOR")
            _require(establishing.reason == SUCCESSOR_ROTATION, "TRANSITION_REASON_UNEXPECTED", establishing.reason)
            index = [w.witness_version for w in history.chain.witnesses].index(establishing.witness_version)
            record = history.registries[index].keys[establishing.prior_current]
            _require(record.revocation_reason == "SUPERSEDED", "TRANSITION_PREDECESSOR_NOT_SUPERSEDED")
            kind, predecessor, start = SC.ROTATION, establishing.prior_current, establishing.witness_version
        else:
            _require(establishing.reason == KEY_COMPROMISE, "TRANSITION_KIND_NOT_SUPPORTED", establishing.reason)
            marking = next((step for step in reversed(history.steps)
                            if step.witness_version < establishing.witness_version and step.kind == HEAD_ADVANCE
                            and step.epoch == establishing.prior_epoch and step.prior_current is not None
                            and step.prior_current in step.marked_compromised), None)
            _require(marking is not None, "EPOCH_ADVANCE_WITHOUT_MARKING")
            recovery = evaluate_compromise_recovery(history, predecessor_key_id=marking.prior_current)
            _require(recovery.phase == RECOVERY_EPOCH_ADVANCED and recovery.facts.get("successorKeyId") == successor
                     and recovery.facts.get("epochAdvanceWitnessVersion") == establishing.witness_version,
                     "COMPROMISE_RECOVERY_SEQUENCE_INVALID", recovery.reason)
            kind, predecessor, start = SC.KEY_COMPROMISE_RECOVERY, marking.prior_current, marking.witness_version
        ordinal = SC.successor_ordinal_of_key_id(successor)
        _require(ordinal is not None, "SUCCESSOR_KEY_ID_NOT_DERIVED", successor)
        identity = SC.successor_identity(ordinal)
    except _Reject as rejected:
        return None, rejected.reason, rejected.detail
    return KeyTransitionV1(kind, predecessor, successor, identity.ceremony_id, establishing.witness_version,
                           start), None, None


def authority_key_transition(transition: KeyTransitionV1, history: VerifiedHistoryV1, *, readiness_digest: str,
                             predecessor_material: str) -> dict[str, Any]:
    """RR-23 `AuthorityKeyTransitionV1`: a verifier OUTPUT, reproducible from
    the authoritative inputs, with no signature root. It is consumed by
    nothing that decides authority and is never required as an authority
    proof."""
    witnesses = history.chain.witnesses
    if transition.kind == SC.INITIAL_CUSTODY:
        before = history.genesis
    else:
        versions = [w.witness_version for w in witnesses]
        before = witnesses[versions.index(transition.ceremony_start_witness_version) - 1]
    return {
        "recordType": AUTHORITY_KEY_TRANSITION_TYPE, "schemaVersion": AUTHORITY_KEY_TRANSITION_SCHEMA_VERSION,
        "authorityGranted": False, "authorityProof": False, "kind": transition.kind,
        "predecessorKeyId": transition.predecessor_key_id, "successorKeyId": transition.successor_key_id,
        "ceremonyId": transition.ceremony_id, "fromHead": before.registry_head.to_dict(),
        "toHead": history.head.registry_head.to_dict(),
        "fromEpoch": before.current_recovery_epoch.to_dict(), "toEpoch": history.head.current_recovery_epoch.to_dict(),
        "fromWitnessDigest": before.digest, "toWitnessDigest": history.head.digest,
        "readinessDigest": readiness_digest, "predecessorMaterial": predecessor_material,
    }


# -------------------------------------------------- hold binding (RR-24, RR-30) ---

HOLD_RELEASE_ELIGIBILITY = "HOLD_RELEASE_ELIGIBILITY"
FULL_READINESS = "FULL_READINESS"
READINESS_MODES = frozenset({HOLD_RELEASE_ELIGIBILITY, FULL_READINESS})

HOLD_BINDING_REASONS = (
    "CEREMONY_HOLD_HELD",
    "HOLD_NOT_HELD",
    "HOLD_TRANSITION_KIND_MISMATCH",
    "HOLD_CEREMONY_MISMATCH",
    "HOLD_PREDECESSOR_MISMATCH",
    "HOLD_SUCCESSOR_MISMATCH",
    "HOLD_WITNESS_NOT_IN_CHAIN",
    "HOLD_WITNESS_NOT_GENESIS",
    "HOLD_ENGAGED_AFTER_TRANSITION",
    "HOLD_WITNESS_HEAD_MISMATCH",
    "HOLD_CUSTODY_DEBT_OPEN",
)


def hold_binding_reason(hold: SC.CeremonyHoldV1, *, mode: str, transition: KeyTransitionV1,
                        history: VerifiedHistoryV1, inventory_phase: str) -> tuple[str | None, str | None]:
    """Does this parsed hold correspond to exactly the verified state?

    - ELIGIBILITY needs HELD; FULL needs RELEASED (HELD -> CEREMONY_HOLD_HELD).
    - kind, ceremony, predecessor, and successor equal the derived transition.
    - `observedWitnessDigest` names a verified chain entry: for a primary HELD
      hold, an entry before the ceremony's first authority step (INITIAL: the
      pinned genesis itself); for RELEASED, and for the custody-debt HELD
      hold, an entry with the head's exact registry head (later ledger-only
      entries allowed; another head is not).
    - a RELEASED custody-debt hold also needs the STEADY inventory.
    """
    if mode == HOLD_RELEASE_ELIGIBILITY and hold.state != SC.HELD:
        return "HOLD_NOT_HELD", hold.state
    if mode == FULL_READINESS and hold.state != SC.RELEASED:
        return "CEREMONY_HOLD_HELD", hold.reason
    if hold.transition_kind != transition.kind:
        return "HOLD_TRANSITION_KIND_MISMATCH", f"{hold.transition_kind}!={transition.kind}"
    if SC.primary_ceremony_id(hold.ceremony_id) != transition.ceremony_id:
        return "HOLD_CEREMONY_MISMATCH", hold.ceremony_id
    if hold.expected_predecessor_key_id != transition.predecessor_key_id:
        return "HOLD_PREDECESSOR_MISMATCH", str(hold.expected_predecessor_key_id)
    if hold.expected_successor_key_id != transition.successor_key_id:
        return "HOLD_SUCCESSOR_MISMATCH", str(hold.expected_successor_key_id)
    entry = next((w for w in history.chain.witnesses if w.digest == hold.observed_witness_digest), None)
    if entry is None:
        return "HOLD_WITNESS_NOT_IN_CHAIN", None
    if hold.state == SC.HELD and not hold.custody_debt:
        if transition.kind == SC.INITIAL_CUSTODY:
            if entry.digest != history.genesis.digest:
                return "HOLD_WITNESS_NOT_GENESIS", str(entry.witness_version)
        elif entry.witness_version >= transition.ceremony_start_witness_version:
            return "HOLD_ENGAGED_AFTER_TRANSITION", str(entry.witness_version)
        return None, None
    if entry.registry_head != history.head.registry_head:
        return "HOLD_WITNESS_HEAD_MISMATCH", str(entry.witness_version)
    if hold.state == SC.RELEASED and hold.custody_debt and inventory_phase != WR.STEADY:
        return "HOLD_CUSTODY_DEBT_OPEN", inventory_phase
    return None, None


# ------------------------------------------------- successor readiness ---

# Prep A checks (CEREMONY_HOLD superseded), then the Source Prep B checks.
SUCCESSOR_READINESS_CHECKS = tuple(name for name in WR.READINESS_CHECKS if name != "CEREMONY_HOLD") + (
    "PUBLICATION_BYTES",
    "KEY_TRANSITION",
    "COMPROMISE_EPOCH",
    "CEREMONY_PROVENANCE",
    "CEREMONY_HOLD",
)


@dataclass(frozen=True)
class SuccessorReadinessInputsV1:
    """Prep A inputs plus the Source Prep B ones. `base.hold_present` is
    superseded and ignored: only a bound `CeremonyHoldV1` passes the hold."""

    base: WR.WitnessReadinessInputsV1
    hold: Mapping[str, Any] | None
    publication_bytes: bytes | None
    ceremony_record: Mapping[str, Any] | None = None
    reviewed_release_sha: str | None = None
    ceremony_register: Any = None
    profile: SC.CustodyProfileV1 = SC.DEV_SYNTHETIC_CUSTODY_PROFILE


@dataclass(frozen=True)
class SuccessorReadinessResultV1:
    status: str
    mode: str
    reasons: tuple[str, ...]
    checks: Mapping[str, WR.CheckOutcomeV1]
    facts: Mapping[str, Any]

    @property
    def ready(self) -> bool:
        return self.status == WR.READY


def _readiness_digest(mode: str, status: str, checks: Mapping[str, WR.CheckOutcomeV1], head: str | None,
                      transition: KeyTransitionV1 | None) -> str:
    return hashlib.sha256(WR.document_bytes({
        "mode": mode, "status": status, "headWitnessDigest": head,
        "checks": {name: [c.status, c.reason] for name, c in checks.items()},
        "transition": None if transition is None else [transition.kind, transition.predecessor_key_id,
                                                        transition.successor_key_id, transition.ceremony_id],
    })).hexdigest()


def evaluate_successor_readiness(inputs: SuccessorReadinessInputsV1, *, mode: str) -> SuccessorReadinessResultV1:
    """HOLD_RELEASE_ELIGIBILITY or FULL_READINESS over the same verified inputs.

    ELIGIBILITY = every applicable readiness condition except "the hold is
    RELEASED", and it needs a bound HELD hold of the same ceremony. FULL =
    every condition plus a bound RELEASED hold. The order is always HELD ->
    eligibility -> explicit owner release -> RELEASED -> FULL re-run; FULL
    never implies a release. FULL READY is the independently reproduced
    `S_CURRENT` for issuance readiness only: it grants no authority and
    authorizes no live entry.
    """
    checks: dict[str, WR.CheckOutcomeV1] = {}

    def record(name: str, reason: str | None, detail: str | None = None) -> None:
        checks[name] = WR.CheckOutcomeV1(WR.PASS) if reason is None else WR.CheckOutcomeV1(WR.FAIL, reason, detail)

    def skip(name: str, detail: str) -> None:
        checks[name] = WR.CheckOutcomeV1(WR.NOT_EVALUATED, "PREREQUISITE_NOT_VERIFIED", detail)

    facts: dict[str, Any] = {"authorityGranted": False, "liveEntryAuthorized": False, "issuanceReady": False,
                             "holdReleaseEligible": False, "successorCurrent": False, "mode": mode,
                             "rollbackDetectionScope": R.ROLLBACK_DETECTION_SCOPE,
                             "wholeHostRollbackProtected": R.WHOLE_HOST_ROLLBACK_PROTECTED}
    if mode not in READINESS_MODES or not isinstance(inputs, SuccessorReadinessInputsV1) \
            or not isinstance(inputs.base, WR.WitnessReadinessInputsV1):
        checks = {name: WR.CheckOutcomeV1(WR.FAIL, "MALFORMED_INPUT") for name in SUCCESSOR_READINESS_CHECKS}
        return SuccessorReadinessResultV1(WR.NOT_READY, str(mode),
                                          tuple(f"{n}:MALFORMED_INPUT" for n in SUCCESSOR_READINESS_CHECKS),
                                          checks, facts)
    profile = inputs.profile
    base_inputs = dataclasses.replace(inputs.base, hold_present=False)
    facts["inventoryPhase"] = base_inputs.inventory_phase
    base = WR.evaluate_witness_readiness(base_inputs)
    for name, outcome in base.checks.items():
        if name != "CEREMONY_HOLD":
            checks[name] = outcome
    for key in ("witnessClassification", "witnessedHead", "loadedKeyBinding"):
        if key in base.facts:
            facts[key] = base.facts[key]
    if not SC.is_dev_synthetic(profile) or base_inputs.environment != profile.environment:
        for name in ("PUBLICATION_BYTES", "KEY_TRANSITION", "COMPROMISE_EPOCH", "CEREMONY_PROVENANCE",
                     "CEREMONY_HOLD"):
            record(name, "PROFILE_NOT_DEV_SYNTHETIC")
        return _finish(mode, checks, facts, None, None)

    # PUBLICATION_BYTES: the exact bytes the ceremony record binds are the
    # same publication the Prep A binding (B3) used.
    published = None
    try:
        published_value, published = SC.parse_publication_bytes(inputs.publication_bytes)
        record("PUBLICATION_BYTES", None if published_value == base_inputs.publication
               else "PUBLICATION_BYTES_MISMATCH")
    except (OwnerProofError, TypeError) as exc:
        record("PUBLICATION_BYTES", getattr(exc, "code", "PUBLICATION_MALFORMED"))
        published_value = None

    history, reason, detail = verify_history(store=base_inputs.store, witness_store=base_inputs.witness_store,
                                             head_registries=base_inputs.head_registries)
    transition = None
    if history is None:
        record("KEY_TRANSITION", reason, detail)
        for name in ("COMPROMISE_EPOCH", "CEREMONY_PROVENANCE", "CEREMONY_HOLD"):
            skip(name, "KEY_TRANSITION")
        return _finish(mode, checks, facts, None, None)
    transition, reason, detail = derive_key_transition(history, profile=profile)
    record("KEY_TRANSITION", reason, detail)
    record("COMPROMISE_EPOCH", *compromise_epoch_reason(history))
    if transition is None:
        skip("CEREMONY_PROVENANCE", "KEY_TRANSITION")
        skip("CEREMONY_HOLD", "KEY_TRANSITION")
        return _finish(mode, checks, facts, history, None)
    facts["keyTransition"] = {"kind": transition.kind, "predecessorKeyId": transition.predecessor_key_id,
                              "successorKeyId": transition.successor_key_id, "ceremonyId": transition.ceremony_id}

    # CEREMONY_PROVENANCE: INITIAL_CUSTODY is the initial keygen publication
    # (CURRENT path) with no successor record; every successor needs its
    # verified RR-27 record, bound to the same publication bytes, registered
    # once in the burned-ordinal register.
    try:
        _require(published is not None, "PUBLICATION_MISSING")
        if transition.kind == SC.INITIAL_CUSTODY:
            _require(inputs.ceremony_record is None, "CEREMONY_RECORD_UNEXPECTED")
            code = SC.publication_profile_reason(published_value, published, profile=profile,
                                                 key_id=profile.initial_key_id, credential_path=profile.current_path)
            _require(code is None, code or "")
        else:
            verified = SC.verify_successor_ceremony_record(record=inputs.ceremony_record,
                                                           publication_bytes=inputs.publication_bytes,
                                                           reviewed_release_sha=inputs.reviewed_release_sha,
                                                           profile=profile)
            _require(verified.verified, verified.reason or "", verified.detail)
            _require(verified.record.key_id == transition.successor_key_id
                     and verified.record.ceremony_id == transition.ceremony_id, "CEREMONY_RECORD_NOT_HEAD_SUCCESSOR")
            registered = SC.verify_registered_ceremony(inputs.ceremony_register, inputs.ceremony_record,
                                                       profile=profile)
            _require(registered.ok, registered.reason or "", registered.detail)
        record("CEREMONY_PROVENANCE", None)
    except _Reject as rejected:
        record("CEREMONY_PROVENANCE", rejected.reason, rejected.detail)

    hold, reason = SC.parse_ceremony_hold(inputs.hold, profile=profile)
    if hold is None:
        record("CEREMONY_HOLD", reason)
    else:
        facts["hold"] = {"state": hold.state, "ceremonyId": hold.ceremony_id, "custodyDebt": hold.custody_debt}
        record("CEREMONY_HOLD", *hold_binding_reason(hold, mode=mode, transition=transition, history=history,
                                                     inventory_phase=base_inputs.inventory_phase))
    return _finish(mode, checks, facts, history, transition)


def _finish(mode: str, checks: dict[str, WR.CheckOutcomeV1], facts: dict[str, Any],
            history: VerifiedHistoryV1 | None, transition: KeyTransitionV1 | None) -> SuccessorReadinessResultV1:
    for name in SUCCESSOR_READINESS_CHECKS:
        checks.setdefault(name, WR.CheckOutcomeV1(WR.NOT_EVALUATED, "PREREQUISITE_NOT_VERIFIED", "INPUT"))
    ordered = {name: checks[name] for name in SUCCESSOR_READINESS_CHECKS}
    reasons = tuple(f"{name}:{outcome.reason}" for name, outcome in ordered.items() if outcome.status != WR.PASS)
    status = WR.READY if not reasons else WR.NOT_READY
    head = None if history is None else history.head.digest
    digest = _readiness_digest(mode, status, ordered, head, transition)
    facts["readinessDigest"] = digest
    if history is not None:
        facts["headWitnessDigest"] = head
        facts["headRegistry"] = history.head.registry_head.to_dict()
        facts["headCurrentKeyId"] = _current_key(history.head_registry)
    if status == WR.READY:
        facts["holdReleaseEligible"] = mode == HOLD_RELEASE_ELIGIBILITY
        facts["issuanceReady"] = facts["successorCurrent"] = mode == FULL_READINESS
    if transition is not None and history is not None:
        material = "NONE" if transition.kind == SC.INITIAL_CUSTODY else (
            "DESTROYED_FROM_ACTIVE_CUSTODY" if facts.get("inventoryPhase") == WR.STEADY else "RETAINED")
        facts["authorityKeyTransition"] = authority_key_transition(transition, history, readiness_digest=digest,
                                                                   predecessor_material=material)
    return SuccessorReadinessResultV1(status, mode, reasons, ordered, facts)


# -------------------------------------------- narrow C-4 recovery gate (RR-28) ---

ADVANCE_EPOCH = "ADVANCE_EPOCH"
VOID_CHALLENGE = "VOID_CHALLENGE"
QUARANTINE_USE = "QUARANTINE_USE"
# The closed allowlist. Everything else (ISSUE, PREPARE, CONSUME, RESERVE,
# CONFIRM, REGISTRY_VIEW, every signing request, any admin or unknown
# operation) is denied, even with the private key loaded.
RECOVERY_ALLOWLIST = frozenset({ADVANCE_EPOCH, VOID_CHALLENGE, QUARANTINE_USE})

RECOVERY_GATE_PERMITTED = "RECOVERY_OPERATION_PERMITTED"
RECOVERY_GATE_DENIED = "RECOVERY_OPERATION_DENIED"

RECOVERY_GATE_REASONS = (
    "PROFILE_NOT_DEV_SYNTHETIC",
    "OPERATION_NOT_ALLOWLISTED",
    "HOLD_INVALID",
    "HOLD_NOT_HELD",
    "HOLD_NOT_COMPROMISE_RECOVERY",
    "HISTORY_NOT_VERIFIED",
    "RECOVERY_SEQUENCE_INVALID",
    "RECOVERY_PHASE_MISMATCH",
    "PREDECESSOR_NOT_COMPROMISED_AT_HEAD",
    "ISSUANCE_NOT_DISABLED",
    "EPOCH_AUTHORIZATION_MISSING",
    "EPOCH_AUTHORIZATION_NOT_VERIFIED",
    "EPOCH_AUTHORIZATION_REASON_INVALID",
    "EPOCH_AUTHORIZATION_NOT_BOUND_TO_HEAD",
    "AUTHORIZATION_CONSUMED",
    "ADOPTION_ALREADY_JOURNALLED",
    "HOLD_SUCCESSOR_MISMATCH",
)


@dataclass(frozen=True)
class RecoveryGateResultV1:
    status: str
    reason: str | None = None
    detail: str | None = None
    facts: Mapping[str, Any] = field(default_factory=dict)

    @property
    def permitted(self) -> bool:
        return self.status == RECOVERY_GATE_PERMITTED


def evaluate_recovery_gate(*, operation: Any, hold: Mapping[str, Any] | None, store: WR.WitnessStoreContextV1,
                           witness_store: WR.WitnessStoreObservationV1, head_registries: Sequence[Mapping[str, Any]],
                           epoch_authorization: Mapping[str, Any] | None = None,
                           ledger_observation: RC.AuthorityLedgerObservationV1 | None = None,
                           profile: SC.CustodyProfileV1 = SC.DEV_SYNTHETIC_CUSTODY_PROFILE) -> RecoveryGateResultV1:
    """May a future signer that still loads the COMPROMISED P perform ONLY this
    C-4 recovery-ledger operation? A permitted result is permission for one
    narrow runtime action, never authority: signing, evidence issuance,
    evidence reservation or consumption, registry or Privacy signing, and
    generic admin stay denied, and no credential-less signer mode exists.
    `COMPROMISED key loaded for recovery != valid evidence issuer`.
    """
    facts: dict[str, Any] = {"authorityGranted": False, "signingPermitted": False, "issuancePermitted": False,
                             "evidenceReservationPermitted": False, "operation": operation}
    try:
        _require(SC.is_dev_synthetic(profile) and isinstance(store, WR.WitnessStoreContextV1)
                 and store.environment == profile.environment, "PROFILE_NOT_DEV_SYNTHETIC")
        _require(isinstance(operation, str) and operation in RECOVERY_ALLOWLIST, "OPERATION_NOT_ALLOWLISTED",
                 str(operation))
        parsed, reason = SC.parse_ceremony_hold(hold, profile=profile)
        _require(parsed is not None, "HOLD_INVALID", reason)
        _require(parsed.state == SC.HELD, "HOLD_NOT_HELD")
        _require(parsed.transition_kind == SC.KEY_COMPROMISE_RECOVERY and not parsed.custody_debt,
                 "HOLD_NOT_COMPROMISE_RECOVERY", parsed.transition_kind)
        history, reason, detail = verify_history(store=store, witness_store=witness_store,
                                                 head_registries=head_registries)
        _require(history is not None, "HISTORY_NOT_VERIFIED", f"{reason}:{detail}")
        predecessor = parsed.expected_predecessor_key_id
        recovery = evaluate_compromise_recovery(history, predecessor_key_id=predecessor)
        _require(recovery.valid and recovery.reason is None, "RECOVERY_SEQUENCE_INVALID", recovery.reason)
        wanted = RECOVERY_MARKED if operation == ADVANCE_EPOCH else RECOVERY_EPOCH_ADVANCED
        _require(recovery.phase == wanted, "RECOVERY_PHASE_MISMATCH", recovery.phase)
        head_record = history.head_registry.keys.get(predecessor)
        _require(head_record is not None and head_record.compromised, "PREDECESSOR_NOT_COMPROMISED_AT_HEAD")
        _require(_current_key(history.head_registry) != predecessor, "ISSUANCE_NOT_DISABLED")
        if operation == ADVANCE_EPOCH:
            _require(epoch_authorization is not None, "EPOCH_AUTHORIZATION_MISSING")
            checked = RC.verify_epoch_advance_authorization(authorization=epoch_authorization,
                                                            registry_root=store.registry_root,
                                                            environment=store.environment)
            _require(checked.verified, "EPOCH_AUTHORIZATION_NOT_VERIFIED", checked.reason)
            auth = checked.authorization
            _require(auth.reason == KEY_COMPROMISE, "EPOCH_AUTHORIZATION_REASON_INVALID", auth.reason)
            head = history.head
            _require(auth.expected_prior_witness_digest == head.digest
                     and auth.expected_prior_witness_version == head.witness_version
                     and auth.prior_recovery_epoch == head.current_recovery_epoch,
                     "EPOCH_AUTHORIZATION_NOT_BOUND_TO_HEAD")
            _require(auth.authorization_id not in history.chain.consumed_authorization_ids, "AUTHORIZATION_CONSUMED")
            if ledger_observation is not None:
                _require(R.compare_epochs(head.current_recovery_epoch, ledger_observation.recovery_epoch)
                         == R.EPOCH_EQUAL, "ADOPTION_ALREADY_JOURNALLED")
            facts["epochAuthorizationId"] = auth.authorization_id
        else:
            successor = recovery.facts.get("successorKeyId")
            _require(parsed.expected_successor_key_id in (None, successor), "HOLD_SUCCESSOR_MISMATCH")
    except _Reject as rejected:
        return RecoveryGateResultV1(RECOVERY_GATE_DENIED, rejected.reason, rejected.detail, facts)
    facts["permittedOperation"] = operation
    return RecoveryGateResultV1(RECOVERY_GATE_PERMITTED, facts=facts)


# ----------------------------------- custody steps and destruction order (SW-1) ---

@dataclass(frozen=True)
class CustodyAuthorityFactsV1:
    """What the verified head says about one ceremony's keys (derived)."""

    head_current_key_id: str | None
    predecessor_compromised: bool
    authority_ponr_passed: bool      # the witnessed head names the successor current


def custody_authority_facts(history: VerifiedHistoryV1, ceremony: SC.CustodyCeremonyV1) -> CustodyAuthorityFactsV1:
    current = _current_key(history.head_registry)
    record = history.head_registry.keys.get(ceremony.predecessor_key_id)
    return CustodyAuthorityFactsV1(current, bool(record is not None and record.compromised),
                                   current == ceremony.successor_key_id)


def authorize_custody_step(*, step: str, custody: SC.CustodyObservationV1, ceremony: SC.CustodyCeremonyV1,
                           hold: Mapping[str, Any] | None, store: WR.WitnessStoreContextV1,
                           witness_store: WR.WitnessStoreObservationV1, head_registries: Sequence[Mapping[str, Any]],
                           ceremony_register: Any = None,
                           profile: SC.CustodyProfileV1 = SC.DEV_SYNTHETIC_CUSTODY_PROFILE) -> SC.CustodyStepPlanV1:
    """PREPARE, ABANDON, VACATE, or INSTALL: the filesystem preconditions
    (same filesystem, exact P / S hashes, roles, custody facts, no extras)
    AND the authority head AND a bound HELD primary hold. DESTROY is decided
    only by `verify_destruction_order`.

    - PREPARE: P is the head's current key (ROTATION) or P is COMPROMISED at
      the head with no current key (KEY_COMPROMISE_RECOVERY after the
      marking); the ordinal is unburned. CURRENT stays P.
    - ABANDON: before the authority PONR only (the successor is not current).
    - VACATE / INSTALL: after the authority PONR only; forward only.
    """
    facts = {"authorityGranted": False}
    try:
        _require(step in (SC.PREPARE, SC.ABANDON, SC.VACATE, SC.INSTALL), "CUSTODY_STEP_UNKNOWN", str(step))
        _require(SC.is_dev_synthetic(profile) and isinstance(ceremony, SC.CustodyCeremonyV1)
                 and isinstance(store, WR.WitnessStoreContextV1) and store.environment == profile.environment,
                 "PROFILE_NOT_DEV_SYNTHETIC")
        parsed, reason = SC.parse_ceremony_hold(hold, profile=profile)
        _require(parsed is not None, reason or "HOLD_MISSING")
        _require(parsed.state == SC.HELD and not parsed.custody_debt, "HOLD_NOT_HELD")
        _require(parsed.transition_kind in (SC.ROTATION, SC.KEY_COMPROMISE_RECOVERY)
                 and parsed.ceremony_id == ceremony.ceremony_id
                 and parsed.expected_predecessor_key_id == ceremony.predecessor_key_id
                 and parsed.expected_successor_key_id in (None, ceremony.successor_key_id), "HOLD_CEREMONY_MISMATCH")
        ordinal = SC.successor_ordinal_of_ceremony_id(ceremony.ceremony_id)
        _require(ordinal is not None and SC.successor_identity(ordinal).key_id == ceremony.successor_key_id,
                 "CUSTODY_CEREMONY_NOT_DERIVED")
        history, reason, detail = verify_history(store=store, witness_store=witness_store,
                                                 head_registries=head_registries)
        _require(history is not None, "HISTORY_NOT_VERIFIED", f"{reason}:{detail}")
        authority = custody_authority_facts(history, ceremony)
        source, target = SC.CUSTODY_STEPS[step]
        code = SC.custody_transition_reason(source, target, authority_ponr_passed=authority.authority_ponr_passed)
        _require(code is None, code or "")
        if step == SC.PREPARE:
            _require(parsed.expected_successor_key_id is None or parsed.expected_successor_key_id
                     == ceremony.successor_key_id, "HOLD_CEREMONY_MISMATCH")
            if parsed.transition_kind == SC.ROTATION:
                _require(authority.head_current_key_id == ceremony.predecessor_key_id, "PREDECESSOR_NOT_CURRENT")
            else:
                _require(authority.predecessor_compromised and authority.head_current_key_id is None,
                         "COMPROMISE_MARKING_NOT_COMMITTED")
            unburned = SC.check_ordinal_unburned(ceremony_register, ordinal, profile=profile)
            _require(unburned.ok, unburned.reason or "", unburned.detail)
            state = SC.custody_state(custody, ceremony)
            _require(state.verified and state.state == SC.PREDECESSOR_STEADY, state.reason or
                     "CUSTODY_STATE_NOT_FROM_STATE", state.state)
            _require(SC.same_filesystem_reason(custody) is None, SC.same_filesystem_reason(custody) or "")
            return SC.CustodyStepPlanV1(RC.PLANNED, step=step, operation=("KEYGEN", "successor", str(ordinal)),
                                        expected_sha256=ceremony.predecessor_blob_sha256,
                                        facts={**facts, "currentMustRemain": ceremony.predecessor_blob_sha256})
        _require(authority.head_current_key_id != ceremony.predecessor_key_id or step == SC.ABANDON,
                 "PREDECESSOR_STILL_CURRENT")
        plan = SC.plan_custody_filesystem_step(step=step, observation=custody, ceremony=ceremony, profile=profile)
        _require(plan.planned, plan.reason or "", plan.detail)
    except (_Reject, OwnerProofError) as rejected:
        reason = rejected.reason if isinstance(rejected, _Reject) else rejected.code
        return SC.CustodyStepPlanV1(RC.REFUSED, reason, getattr(rejected, "detail", None), step, facts=facts)
    return plan


DESTRUCTION_PERMITTED = "DESTRUCTION_PERMITTED"
DESTRUCTION_DENIED = "DESTRUCTION_DENIED"

DESTRUCTION_ORDER_REASONS = (
    "DESTRUCTION_INPUT_MALFORMED",
    "DESTRUCTION_BEFORE_S_CURRENT",
    "DESTRUCTION_CEREMONY_MISMATCH",
    "PREDECESSOR_STILL_CURRENT",
    "RELEASED_HOLD_NOT_BOUND",
    "PREDECESSOR_NOT_RETIRED",
)


@dataclass(frozen=True)
class DestructionOrderResultV1:
    status: str
    reason: str | None = None
    detail: str | None = None
    plan: SC.CustodyStepPlanV1 | None = None
    facts: Mapping[str, Any] = field(default_factory=dict)

    @property
    def permitted(self) -> bool:
        return self.status == DESTRUCTION_PERMITTED


def verify_destruction_order(*, readiness: SuccessorReadinessResultV1, custody: SC.CustodyObservationV1,
                             ceremony: SC.CustodyCeremonyV1, released_hold: Mapping[str, Any] | None = None,
                             profile: SC.CustodyProfileV1 = SC.DEV_SYNTHETIC_CUSTODY_PROFILE
                             ) -> DestructionOrderResultV1:
    """SW-1 / RR-29: may P's RETIRED blob be logically destroyed now?

    Only after an independently reproduced `S_CURRENT`: a FULL_READINESS READY
    result at the head naming S, with P in RETIRED only (state C) and not
    authority-current. A retry after a failed destruction runs under the
    custody-debt HELD hold: then HOLD_RELEASE_ELIGIBILITY READY for that hold
    plus the ceremony's own RELEASED hold (which only an owner release after
    eligibility writes) are required. Before S_CURRENT: always denied. No
    rollback to P is ever permitted.
    """
    facts = {"authorityGranted": False, "rollbackToPredecessorPermitted": False,
             "destructionIsRevocation": False}
    try:
        _require(isinstance(readiness, SuccessorReadinessResultV1) and isinstance(ceremony, SC.CustodyCeremonyV1),
                 "DESTRUCTION_INPUT_MALFORMED")
        _require(readiness.ready, "DESTRUCTION_BEFORE_S_CURRENT", ",".join(readiness.reasons[:3]))
        transition = readiness.facts.get("keyTransition") or {}
        hold = readiness.facts.get("hold") or {}
        _require(transition.get("kind") in (SC.ROTATION, SC.KEY_COMPROMISE_RECOVERY)
                 and transition.get("ceremonyId") == ceremony.ceremony_id
                 and transition.get("predecessorKeyId") == ceremony.predecessor_key_id
                 and transition.get("successorKeyId") == ceremony.successor_key_id, "DESTRUCTION_CEREMONY_MISMATCH")
        _require(readiness.facts.get("headCurrentKeyId") == ceremony.successor_key_id, "PREDECESSOR_STILL_CURRENT")
        binding = readiness.facts.get("loadedKeyBinding") or {}
        _require(binding.get("keyId") == ceremony.successor_key_id, "DESTRUCTION_BEFORE_S_CURRENT", "BINDING")
        if readiness.mode == FULL_READINESS:
            _require(hold.get("state") == SC.RELEASED and not hold.get("custodyDebt"), "DESTRUCTION_BEFORE_S_CURRENT")
        else:
            _require(hold.get("state") == SC.HELD and hold.get("custodyDebt") is True
                     and hold.get("ceremonyId") == SC.custody_debt_ceremony_id(ceremony.ceremony_id),
                     "DESTRUCTION_BEFORE_S_CURRENT", "NOT_A_CUSTODY_DEBT_RETRY")
            released, reason = SC.parse_ceremony_hold(released_hold, profile=profile)
            _require(released is not None and released.state == SC.RELEASED and not released.custody_debt
                     and released.ceremony_id == ceremony.ceremony_id
                     and released.transition_kind == transition.get("kind")
                     and released.expected_predecessor_key_id == ceremony.predecessor_key_id
                     and released.expected_successor_key_id == ceremony.successor_key_id,
                     "RELEASED_HOLD_NOT_BOUND", reason)
        state = SC.custody_state(custody, ceremony)
        _require(state.verified and state.state == SC.STATE_C_INSTALLED, "PREDECESSOR_NOT_RETIRED",
                 state.reason or state.state)
        plan = SC.plan_custody_filesystem_step(step=SC.DESTROY, observation=custody, ceremony=ceremony,
                                               profile=profile)
        _require(plan.planned, plan.reason or "", plan.detail)
    except _Reject as rejected:
        return DestructionOrderResultV1(DESTRUCTION_DENIED, rejected.reason, rejected.detail, facts=facts)
    return DestructionOrderResultV1(DESTRUCTION_PERMITTED, plan=plan,
                                    facts={**facts, "readinessDigest": readiness.facts["readinessDigest"]})


def destruction_failure_outcome(outcome: SC.DestructionOutcomeV1, *, ceremony: SC.CustodyCeremonyV1,
                                transition_kind: str, head_witness_digest: str,
                                profile: SC.CustodyProfileV1 = SC.DEV_SYNTHETIC_CUSTODY_PROFILE) -> dict[str, Any]:
    """After S_CURRENT, a DESTRUCTION_INCOMPLETE outcome never rolls authority
    back and never restores P: S stays authority-current, issuance fails
    closed under the custody-debt availability hold, and the owner retries.
    Returns the HELD custody-debt hold to engage (a new, derived ceremony)."""
    if outcome.destroyed:
        raise ValueError("destruction completed; no availability hold is needed")
    if transition_kind not in (SC.ROTATION, SC.KEY_COMPROMISE_RECOVERY):
        raise ValueError("custody debt exists only for a successor ceremony")
    hold = SC.CeremonyHoldV1(
        SC.require_dev_synthetic(profile).environment, SC.custody_debt_ceremony_id(ceremony.ceremony_id),
        transition_kind, SC.HELD, SC.PREDECESSOR_DESTRUCTION_INCOMPLETE, ceremony.predecessor_key_id,
        ceremony.successor_key_id, head_witness_digest)
    return SC.CeremonyHoldV1.from_dict(hold.to_dict(), profile=profile).to_dict()
