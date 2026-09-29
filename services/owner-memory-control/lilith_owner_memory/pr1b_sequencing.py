"""15B2b-B1b-3e PR-3 P3-5: PR-1B bootstrap sequencing (pure, offline, design-only).

Record: docs/architecture/slice-15b2b-b1b3e-pr3-pr1b-bootstrap-sequencing.md.

A checklist state machine for the PR-1B bootstrap. It encodes the exact
order of the accepted PR-1 mutation ledger (M-B1 … M-B15) with owner
freshness record 1 placed in it, the evidence each step requires, the owner
freshness gate category of each step, the points of no return, and the crash
classification of every window between adjacent steps.

    sequencer != verifier

The sequencer never verifies evidence itself. Each evidence item is the
boolean outcome of the named verifier (installer status, root verifier, P3-2
tool, owner off-host reproduction), and the sequencer refuses unless every
required item is literally `True`. The only evidence it inspects is
freshness: it takes an `owner_freshness.FreshnessResultV1`, never a boolean.

It performs no I/O, holds no key, and authorizes nothing: not PR-1B, not
A1–A7, not First Memory.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from . import owner_freshness as OF

# --------------------------------------------------------------- eligibility ---

PR1B_ELIGIBLE = "PR1B_ELIGIBLE"
PR1B_NOT_ELIGIBLE = "PR1B_NOT_ELIGIBLE"
PR2_REVALIDATION_REQUIRED = "PR2_REVALIDATION_REQUIRED"

# precondition -> the reason reported when it is not literally True (§3 of the record)
PRECONDITIONS = {
    "p33Complete": "P3_3_INCOMPLETE",
    "twoRealReplicasExist": "OWNER_REPLICAS_MISSING",
    "replicasCapabilityAdmitted": "OWNER_REPLICAS_NOT_ADMITTED",
    "replicaIndependenceEstablished": "OWNER_REPLICA_INDEPENDENCE_NOT_ESTABLISHED",
    "replicasAgentUnreachableCopy": "OWNER_REPLICA_CUSTODY_NOT_AGENT_EXCLUSIVE",
    "ownerRegisterKnownEmpty": "OWNER_REGISTER_NOT_KNOWN_EMPTY",
    "pr3ToolingAccepted": "PR3_TOOLING_NOT_ACCEPTED",
    "pr1aBaselineValid": "PR1A_BASELINE_NOT_VALID",
    "pr2InventoryRevalidated": PR2_REVALIDATION_REQUIRED,
    "noUnreviewedTopologyChange": PR2_REVALIDATION_REQUIRED,
    "openRisksAcknowledged": "OPEN_RISKS_NOT_ACKNOWLEDGED",
    "pr1bAuthorized": "PR1B_NOT_AUTHORIZED",
}


@dataclass(frozen=True)
class EligibilityResultV1:
    status: str
    reasons: tuple[str, ...] = ()

    @property
    def eligible(self) -> bool:
        return self.status == PR1B_ELIGIBLE


def evaluate_eligibility(facts: Mapping[str, Any] | None) -> EligibilityResultV1:
    """PR1B_ELIGIBLE only when every precondition is literally True. A
    synthetic rehearsal result is not an input and cannot override P3-3."""
    facts = facts if isinstance(facts, Mapping) else {}
    unknown = sorted(set(facts) - set(PRECONDITIONS))
    reasons = [PRECONDITIONS[name] for name in PRECONDITIONS if facts.get(name) is not True]
    if unknown:
        reasons.append("UNKNOWN_PRECONDITION:" + ",".join(unknown))
    reasons = tuple(dict.fromkeys(reasons))
    return EligibilityResultV1(PR1B_NOT_ELIGIBLE if reasons else PR1B_ELIGIBLE, reasons)


# -------------------------------------------------------- freshness categories ---

NOT_APPLICABLE_PRE_GENESIS = "NOT_APPLICABLE_PRE_GENESIS"    # no lineage exists; off-host or read-only
REQUIRED_UNKNOWN_BLOCK = "REQUIRED_UNKNOWN_BLOCK"            # pre-genesis host write: register must be KNOWN_EMPTY
REQUIRED_CURRENT = "REQUIRED_CURRENT"                        # AUTHENTIC + CURRENT against owner record 1+
BOOTSTRAP_SPECIAL_CASE = "BOOTSTRAP_SPECIAL_CASE"            # the lineage-creating acts; explicitly justified
GATE_CATEGORIES = frozenset({NOT_APPLICABLE_PRE_GENESIS, REQUIRED_UNKNOWN_BLOCK, REQUIRED_CURRENT,
                             BOOTSTRAP_SPECIAL_CASE})

# Owner register states the sequencer distinguishes.
KNOWN_EMPTY = "KNOWN_EMPTY"          # exactly two admitted replicas, identical, zero records
REGISTER_UNKNOWN = "UNKNOWN"


def owner_register_state(register: Any) -> str:
    """KNOWN_EMPTY only for the P3-2 `OWNER_REGISTER_EMPTY` result (two
    replicas, all empty). Divergent, missing, below quorum, or non-empty is
    not KNOWN_EMPTY."""
    if isinstance(register, OF.OwnerRegisterResultV1) and not register.verified \
            and register.reason == "OWNER_REGISTER_EMPTY":
        return KNOWN_EMPTY
    return REGISTER_UNKNOWN


# --------------------------------------------------------------- the machine ---

PONR_CUSTODY = "CUSTODY"          # private key material existed
PONR_RECORD = "RECORD"            # owner-held record that is never silently replaced
PONR_LINEAGE = "LINEAGE"          # witness genesis committed
PONR_OWNER_RECORD = "OWNER_RECORD"
PONR_HOLD = "HOLD"
PONR_READINESS = "READINESS"


@dataclass(frozen=True)
class StepV1:
    action: str
    source: str
    target: str
    mutation: str          # the accepted PR-1 mutation-ledger row, or "P3" for owner freshness steps
    gate: str
    evidence: tuple[str, ...]
    ponr: str | None = None
    special_case_justification: str | None = None


STEPS: tuple[StepV1, ...] = (
    StepV1("CHECK_ELIGIBILITY", "PR1B_INELIGIBLE", "PR1B_ELIGIBLE", "P1B-0", NOT_APPLICABLE_PRE_GENESIS,
           ("eligibilityResult",)),
    StepV1("GENERATE_K_ROOT", "PR1B_ELIGIBLE", "K_ROOT_GENERATED", "M-B1", NOT_APPLICABLE_PRE_GENESIS,
           ("offHostWorkstation", "kRootFingerprintRecordedOffHost")),
    StepV1("GENERATE_K_WIT", "K_ROOT_GENERATED", "K_WIT_CUSTODIED", "M-B2", REQUIRED_UNKNOWN_BLOCK,
           ("pr2RevalidatedImmediatelyBefore", "kWitPublicationCaptured", "kWitFingerprintRecordedOffHost",
            "secretScansClean", "currentKActUnchanged", "kWitDistinctFromKActAndKRoot"), PONR_CUSTODY),
    StepV1("SIGN_REGISTRY_V1", "K_WIT_CUSTODIED", "REGISTRY_SIGNED", "M-B3", NOT_APPLICABLE_PRE_GENESIS,
           ("singleCurrentKeyHolds", "kActRecordEqualsPublication", "kWitNotInRegistry",
            "registryDigestRecordedOffHost")),
    StepV1("INSTALL_TRUST_AND_REGISTRY", "REGISTRY_SIGNED", "TRUST_INSTALLED", "M-B4+M-B5", REQUIRED_UNKNOWN_BLOCK,
           ("anchorsEqualOwnerCopies", "witnessAnchorNamesKWit", "registryVerifiesOnHost")),
    StepV1("PROVISION_LEDGER", "TRUST_INSTALLED", "LEDGER_PROVISIONED", "M-B6", REQUIRED_UNKNOWN_BLOCK,
           ("ledgerSequenceIsOne", "ledgerHeadEqualsOwnerComputed", "ledgerSchemaFingerprintVerified")),
    StepV1("PREPARE_GENESIS_CANDIDATE", "LEDGER_PROVISIONED", "GENESIS_PREPARED", "M-B7",
           NOT_APPLICABLE_PRE_GENESIS, ("hostCandidateDigestEqualsOwnerDigest",)),
    StepV1("PIN_GENESIS", "GENESIS_PREPARED", "GENESIS_PINNED", "M-B8", REQUIRED_UNKNOWN_BLOCK,
           ("pinStoredOffHostTwoCopies", "onHostPinCopyEqualsOffHost", "pinEqualsCandidateDigest"), PONR_RECORD),
    StepV1("START_WITNESS", "GENESIS_PINNED", "WITNESS_STARTED", "M-B9a", REQUIRED_UNKNOWN_BLOCK,
           ("witnessStoreUninitialized", "witnessNotEnabled")),
    StepV1("COMMIT_WITNESS_GENESIS", "WITNESS_STARTED", "WITNESS_GENESIS_COMMITTED", "M-B9b", BOOTSTRAP_SPECIAL_CASE,
           ("pinEqualsCandidateDigest", "committedDigestEqualsPin", "chainIsGenesisOnly", "witnessRecoveryConsistent"),
           PONR_LINEAGE,
           "creates the lineage that owner freshness later accepts; no owner record can exist before it. "
           "The owner's pre-commit genesis pin is the owner anchor, and the register must be KNOWN_EMPTY"),
    StepV1("APPEND_RECORD_1_REPLICA_A", "WITNESS_GENESIS_COMMITTED", "OWNER_RECORD_PARTIAL", "P3",
           BOOTSTRAP_SPECIAL_CASE,
           ("chainAuthenticGenesisOnly", "record1BindsPin", "record1WitnessEqualsCommittedGenesis",
            "ownerReviewedCandidate", "ownerConfirmedDigest", "appendReplicationPeerPending"), PONR_OWNER_RECORD,
           "the act that creates owner freshness cannot itself require CURRENT. It is gated instead by P3-2 "
           "re-derivation, the pin, and a KNOWN_EMPTY register"),
    StepV1("APPEND_RECORD_1_REPLICA_B", "OWNER_RECORD_PARTIAL", "OWNER_FRESHNESS_CURRENT", "P3",
           BOOTSTRAP_SPECIAL_CASE,
           ("sameCandidateAndDigest", "appendReplicationReplicasIdentical", "compareReplicasVerified"),
           PONR_OWNER_RECORD,
           "completes the same record-1 ceremony. Its result must classify AUTHENTIC + CURRENT"),
    StepV1("WRITE_HELD", "OWNER_FRESHNESS_CURRENT", "INITIAL_CUSTODY_HELD", "M-B10", REQUIRED_CURRENT,
           ("holdStoreEmptyBefore", "heldBoundToGenesisDigest"), PONR_HOLD),
    StepV1("START_SIGNER", "INITIAL_CUSTODY_HELD", "SIGNER_STARTED", "M-B11", REQUIRED_CURRENT,
           ("healthB4EqualsB3", "notReadyOnlyHoldReason", "signerNotEnabled")),
    StepV1("EVALUATE_ELIGIBILITY", "SIGNER_STARTED", "ELIGIBILITY_READY", "M-B12", REQUIRED_CURRENT,
           ("eligibilityReady", "packageDigestComputed", "denialProofsPass")),
    StepV1("OWNER_ACCEPTANCE", "ELIGIBILITY_READY", "OWNER_ACCEPTANCE_COMPLETE", "M-B13", REQUIRED_CURRENT,
           ("ownerOffHostReproductionEqual", "ownerDecisionRecordedOffHost", "pr2EvidenceAccepted",
            "pr3FullMaterialPresent")),
    StepV1("WRITE_RELEASED", "OWNER_ACCEPTANCE_COMPLETE", "INITIAL_CUSTODY_RELEASED", "M-B14", REQUIRED_CURRENT,
           ("rerunPackageDigestEqualsApproved", "releasedBoundToGenesisHead"), PONR_READINESS),
    StepV1("EVALUATE_FULL_READINESS", "INITIAL_CUSTODY_RELEASED", "FULL_READINESS", "M-B15", REQUIRED_CURRENT,
           ("fullReadinessReady", "activationDark", "dr5AndPreservationPass")),
)

STATES = tuple(["PR1B_INELIGIBLE"] + [step.target for step in STEPS])
BY_ACTION = {step.action: step for step in STEPS}
BY_SOURCE = {step.source: step for step in STEPS}
TERMINAL_HALT = "BOOTSTRAP_HALTED_MANUAL_RECOVERY"

# During the one-replica record-1 window, the only permitted action is completing it.
PARTIAL_STATE = "OWNER_RECORD_PARTIAL"

ADVANCED = "ADVANCED"
REFUSED = "REFUSED"


@dataclass(frozen=True)
class TransitionResultV1:
    status: str
    state: str
    reason: str | None = None
    detail: str | None = None

    @property
    def advanced(self) -> bool:
        return self.status == ADVANCED


@dataclass
class BootstrapSequencerV1:
    """Tracks one PR-1B bootstrap. Forward only: no reset, no re-entry, no
    skipping, and no repeat of a passed point of no return."""

    state: str = "PR1B_INELIGIBLE"
    history: list[str] = field(default_factory=list)

    def _refuse(self, reason: str, detail: str | None = None) -> TransitionResultV1:
        return TransitionResultV1(REFUSED, self.state, reason, detail)

    def advance(self, action: str, evidence: Mapping[str, Any] | None = None) -> TransitionResultV1:
        evidence = evidence if isinstance(evidence, Mapping) else {}
        if self.state == TERMINAL_HALT:
            return self._refuse("BOOTSTRAP_HALTED")
        step = BY_ACTION.get(action)
        if step is None:
            return self._refuse("UNKNOWN_ACTION", str(action))
        if action in self.history:
            return self._refuse("REPEATED_IRREVERSIBLE_TRANSITION" if step.ponr else "REPEATED_TRANSITION", action)
        if step.source != self.state:
            return self._refuse("TRANSITION_OUT_OF_ORDER", f"{self.state}->{action}")
        if action == "CHECK_ELIGIBILITY":
            result = evidence.get("eligibilityResult")
            if not isinstance(result, EligibilityResultV1) or not result.eligible:
                reasons = result.reasons if isinstance(result, EligibilityResultV1) else ("MALFORMED_EVIDENCE",)
                return self._refuse(PR1B_NOT_ELIGIBLE, ",".join(reasons))
        else:
            missing = [name for name in step.evidence if evidence.get(name) is not True]
            if missing:
                return self._refuse("EVIDENCE_MISSING", ",".join(missing))
        gate = self._gate(step, evidence)
        if gate is not None:
            return self._refuse(*gate)
        self.history.append(action)
        self.state = step.target
        return TransitionResultV1(ADVANCED, self.state)

    @staticmethod
    def _gate(step: StepV1, evidence: Mapping[str, Any]) -> tuple[str, str] | None:
        if step.gate == REQUIRED_UNKNOWN_BLOCK or step.action in ("COMMIT_WITNESS_GENESIS",
                                                                  "APPEND_RECORD_1_REPLICA_A"):
            state = owner_register_state(evidence.get("ownerRegister"))
            if state != KNOWN_EMPTY:
                return "OWNER_REGISTER_NOT_KNOWN_EMPTY", state
        if step.gate == REQUIRED_CURRENT or step.action == "APPEND_RECORD_1_REPLICA_B":
            freshness = evidence.get("freshness")
            if not isinstance(freshness, OF.FreshnessResultV1) or not freshness.current:
                detail = (f"{freshness.authenticity}:{freshness.freshness}" if isinstance(freshness, OF.FreshnessResultV1)
                          else "MISSING")
                return "FRESHNESS_NOT_CURRENT", detail
        return None

    def halt(self) -> TransitionResultV1:
        """Enter manual recovery (e.g. committed genesis != pin). Irreversible."""
        self.history.append("HALT")
        self.state = TERMINAL_HALT
        return TransitionResultV1(ADVANCED, self.state, "MANUAL_RECOVERY_REQUIRED")

    def reset(self) -> TransitionResultV1:
        """Re-bootstrap is allowed only while nothing irreversible happened."""
        if any(BY_ACTION[a].ponr for a in self.history if a in BY_ACTION) or self.state == TERMINAL_HALT:
            return self._refuse("REBOOTSTRAP_FORBIDDEN")
        self.state, self.history = "PR1B_INELIGIBLE", []
        return TransitionResultV1(ADVANCED, self.state, "RESET_BEFORE_ANY_PONR")


def authority_changing_permitted(state: str, freshness: Any) -> bool:
    """Only FULL_READINESS with AUTHENTIC + CURRENT freshness permits
    authority-changing operations, and even then only through their own
    gates. Never during the one-replica partial state."""
    return state == "FULL_READINESS" and isinstance(freshness, OF.FreshnessResultV1) and freshness.current


# ------------------------------------------------------------------ crashes ---

SAFE_RETRY = "SAFE_RETRY"
RECOVERABLE_INCOMPLETE = "RECOVERABLE_INCOMPLETE"
KNOWN_CUSTODY_DEBT = "KNOWN_CUSTODY_DEBT"
REBOOTSTRAP_FORBIDDEN = "REBOOTSTRAP_FORBIDDEN"
MANUAL_RECOVERY_REQUIRED = "MANUAL_RECOVERY_REQUIRED"
CRASH_CLASSES = frozenset({SAFE_RETRY, RECOVERABLE_INCOMPLETE, KNOWN_CUSTODY_DEBT, REBOOTSTRAP_FORBIDDEN,
                           MANUAL_RECOVERY_REQUIRED})

# window -> (last completed state, class, what to do). Record §16.
CRASH_MATRIX: dict[str, tuple[str, str, str]] = {
    "C-1 eligibility checked / K-ROOT absent": ("PR1B_ELIGIBLE", SAFE_RETRY, "re-check eligibility; nothing written"),
    "C-2 K-ROOT generated / fingerprint not recorded": (
        "PR1B_ELIGIBLE", SAFE_RETRY, "off-host only: discard and regenerate before anything uses it"),
    "C-3 K-WIT generated / publication not captured": (
        "K_ROOT_GENERATED", MANUAL_RECOVERY_REQUIRED,
        "identity unknown: burn the blob (record it as burned), generate a new K-WIT; before M-B4 only"),
    "C-4 K-WIT custodied / registry not signed": (
        "K_WIT_CUSTODIED", KNOWN_CUSTODY_DEBT,
        "continue forward; the blob and host key share the PR-2 snapshot domain (bounded, documented)"),
    "C-5 registry signed / not installed": ("REGISTRY_SIGNED", RECOVERABLE_INCOMPLETE,
                                            "install the same bytes; registry harmless until genesis"),
    "C-6 trust installed / ledger absent": ("TRUST_INSTALLED", RECOVERABLE_INCOMPLETE, "provision the ledger"),
    "C-7 ledger provisioning interrupted": (
        "TRUST_INSTALLED", MANUAL_RECOVERY_REQUIRED,
        "a DB without exactly one GENESIS op is not adopted; inspect, remove the partial DB (before M-B9b only), re-run"),
    "C-8 ledger provisioned / candidate not prepared": ("LEDGER_PROVISIONED", SAFE_RETRY, "read-only step; re-run"),
    "C-9 candidate prepared / pin absent": ("GENESIS_PREPARED", SAFE_RETRY, "owner reproduces and pins"),
    "C-10 pin stored / witness not started": ("GENESIS_PINNED", SAFE_RETRY, "start the witness"),
    "C-11 genesis pinned / witness commit absent": (
        "WITNESS_STARTED", SAFE_RETRY, "witness recovery reads UNINITIALIZED; BOOTSTRAP the same candidate"),
    "C-12 committed genesis differs from pin": (
        "WITNESS_STARTED", REBOOTSTRAP_FORBIDDEN, "STOP; no second genesis (RR-35, RR-40); manual recovery design"),
    "C-13 witness genesis committed / record 1 absent": (
        "WITNESS_GENESIS_COMMITTED", RECOVERABLE_INCOMPLETE,
        "propose record 1 against the same genesis; nothing is effective; freshness UNKNOWN"),
    "C-14 record 1 in Replica A / Replica B absent": (
        "OWNER_RECORD_PARTIAL", RECOVERABLE_INCOMPLETE,
        "append the same candidate to Replica B; FRESHNESS_UNKNOWN until then"),
    "C-15 append interrupted (pending file left)": (
        "OWNER_RECORD_PARTIAL", MANUAL_RECOVERY_REQUIRED,
        "REPLICA_PENDING_WRITE; owner inspects; never auto-deleted"),
    "C-16 record 1 CURRENT / HELD not written": ("OWNER_FRESHNESS_CURRENT", SAFE_RETRY,
                                                "write HELD (hold store still empty)"),
    "C-17 HELD / owner package incomplete": (
        "INITIAL_CUSTODY_HELD", RECOVERABLE_INCOMPLETE,
        "correct the condition and re-evaluate the SAME HELD ceremony; never delete or recreate HELD"),
    "C-18 owner acceptance complete / RELEASED absent": (
        "OWNER_ACCEPTANCE_COMPLETE", SAFE_RETRY,
        "re-run the package; its digest must equal the approved digest, else owner re-review"),
    "C-19 RELEASED write interrupted": (
        "OWNER_ACCEPTANCE_COMPLETE", MANUAL_RECOVERY_REQUIRED,
        "root observer decides HELD vs RELEASED from the store; never re-create; ambiguous = STOP"),
    "C-20 RELEASED / FULL_READINESS fails": ("INITIAL_CUSTODY_RELEASED", RECOVERABLE_INCOMPLETE,
                                            "diagnose; RELEASED never returns to HELD"),
}


# ------------------------------------------------------------- First Memory ---

FIRST_MEMORY_BLOCKED = "FIRST_MEMORY_BLOCKED"
FIRST_MEMORY_REVIEW_ELIGIBLE = "FIRST_MEMORY_REVIEW_ELIGIBLE"   # the most this module can ever say


def first_memory_gate(state: str, *, freshness: Any, a1_a7_accepted: bool, owner_accepted_proofs: bool
                      ) -> tuple[str, str | None]:
    """First Memory is strictly later than FULL_READINESS: fresh A1–A7, then
    owner acceptance of those proofs, then an eligibility review. This module
    never returns an authorization."""
    if state != "FULL_READINESS":
        return FIRST_MEMORY_BLOCKED, "FULL_READINESS_REQUIRED"
    if not (isinstance(freshness, OF.FreshnessResultV1) and freshness.current):
        return FIRST_MEMORY_BLOCKED, "FRESHNESS_NOT_CURRENT"
    if a1_a7_accepted is not True:
        return FIRST_MEMORY_BLOCKED, "A1_A7_REQUIRED"
    if owner_accepted_proofs is not True:
        return FIRST_MEMORY_BLOCKED, "OWNER_ACCEPTANCE_OF_A1_A7_REQUIRED"
    return FIRST_MEMORY_REVIEW_ELIGIBLE, None
