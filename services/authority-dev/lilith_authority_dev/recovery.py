"""Narrow C-4 recovery-ledger runtime wiring (B1b-3e PR-1S, S-10).

Design: docs/architecture/slice-15b2b-b1b3e-pr1-live-install-preflight.md §15;
Source Prep B §12 (RR-28). Record: docs/architecture/slice-15b2b-b1b3e-pr1s-runtime-wiring.md.

The root owner socket carries exactly three recovery operations, each a
signer-owned authority recovery ledger JOURNAL WRITE, never a signature:

    RECOVERY_ADVANCE_EPOCH    -> ADVANCE_EPOCH   (pre-witness C-4 adoption)
    RECOVERY_VOID_CHALLENGE   -> VOID_CHALLENGE  (every stale PREPARED challenge)
    RECOVERY_QUARANTINE_USE   -> QUARANTINE_USE  (every stale RESERVED use)

Flow (a root caller invokes; root is not authority):

1. the request carries only the operation, the COMPLETE root hold-store
   snapshot (never one record), and for the advance the exact K-ROOT
   `EpochAdvanceAuthorizationV1`;
2. the signer reads everything else itself from fixed paths: the witness
   chain (read-only), every installed registry, the trust anchors, the
   on-host pin and register copies, and its own ledger (observation
   MANDATORY here, so `ADOPTION_ALREADY_JOURNALLED` is always checked);
3. the snapshot is parsed and re-judged as a whole: exactly one HELD record
   may govern, and it is handed to the pure `evaluate_recovery_gate`;
4. only a `RECOVERY_OPERATION_PERMITTED` result journals exactly the named
   ledger operation(s) in one transaction at the evaluated position;
5. VOID / QUARANTINE then report the new position to the witness
   (`RECORD_LEDGER_ADVANCE`); the advance does not, because the witness's
   own epoch-advance execution binds the post-adoption position (C-4).

This module imports no minter, holds no key, and has no path to issuance,
reservation, consumption, registry, Privacy, or generic signing.

    COMPROMISED key loaded for recovery != valid evidence issuer
    root caller                          != authority
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Mapping

from lilith_memory.owner_proof import OwnerProofError
from lilith_owner_memory import authority_ledger_journal as J
from lilith_owner_memory import pr1_acceptance as PA
from lilith_owner_memory import rotation_contracts as RC
from lilith_owner_memory import successor_custody as SC
from lilith_owner_memory import successor_readiness as SR
from lilith_owner_memory import witness_readiness as WR

from .ledger import DurableAuthorityLedgerV1, LedgerError
from .protocol import RECOVERY_ADVANCE_EPOCH, RECOVERY_QUARANTINE_USE, RECOVERY_VOID_CHALLENGE

GATE_OPERATIONS = {RECOVERY_ADVANCE_EPOCH: SR.ADVANCE_EPOCH, RECOVERY_VOID_CHALLENGE: SR.VOID_CHALLENGE,
                   RECOVERY_QUARANTINE_USE: SR.QUARANTINE_USE}
RECOVERY_OPERATIONS = frozenset(GATE_OPERATIONS)

OK = "OK"
REFUSED = "REFUSED"
LEDGER_AHEAD_OF_WITNESS = "LEDGER_AHEAD_OF_WITNESS"

HANDLER_REASONS = (
    "RECOVERY_OPERATION_UNKNOWN",
    "SIGNER_INPUTS_INCOMPLETE",
    "AUTHORITY_STATE_MISSING",
    "LEDGER_UNAVAILABLE",
    "LEDGER_OBSERVATION_INCONSISTENT",
    "LEDGER_NOT_AT_WITNESS",
    "HOLD_SET_NO_HELD",
    "HOLD_SET_OTHER_HELD",
    "WITNESS_NOT_CONSISTENT",
    "EPOCH_TARGET_REGISTRY_NOT_INSTALLED",
    "ADOPTION_REFUSED",
    "LEDGER_WRITE_REFUSED",
    "NO_PRE_RECOVERY_WORK",
) + PA.HOLD_SNAPSHOT_REASONS + SR.RECOVERY_GATE_REASONS


MARKING_LAG = "BROKER_REGISTRY_VIEW_STALE"
# Closed refusals of the one tolerated registry-view lag (details of LEDGER_NOT_AT_WITNESS).
MARKING_LAG_REASONS = (
    "LAG_HOLD_NOT_COMPROMISE_RECOVERY",
    "LAG_HISTORY_NOT_VERIFIED",
    "LAG_RECOVERY_NOT_MARKED",
    "LAG_MARKING_NOT_HEAD_TRANSITION",
    "LAG_TRANSITION_NOT_MARKING",
    "LAG_NOT_EXACT_PREDECESSOR",
)


def marking_lag_reason(*, observation: RC.AuthorityLedgerObservationV1, view: "SignerViewV1",
                       governing: Mapping[str, Any], profile: SC.CustodyProfileV1) -> str | None:
    """None only when the ledger's registry view lags the witness by exactly the
    accepted in-epoch COMPROMISE_MARKING step of a KEY_COMPROMISE recovery.

    Independently re-derived from the verified history (never from the gate's
    verdict alone): the governing hold is KEY_COMPROMISE_RECOVERY / HELD; the
    recovery is in RECOVERY_MARKED; the witness head's own transition is that
    marking (a HEAD_ADVANCE authorized COMPROMISE_MARKING, marking the hold's
    expected predecessor, which was current before it, and naming no current
    key); and it moved the registry from exactly the ledger's view to the
    next version. This is not "a registry may be one version stale".
    """
    parsed, _reason = SC.parse_ceremony_hold(governing, profile=profile)
    if (parsed is None or parsed.state != SC.HELD or parsed.transition_kind != SC.KEY_COMPROMISE_RECOVERY
            or parsed.custody_debt):
        return "LAG_HOLD_NOT_COMPROMISE_RECOVERY"
    history, _reason, _detail = SR.verify_history(store=view.context, witness_store=view.witness_store,
                                                  head_registries=view.registries)
    if history is None or not history.steps:
        return "LAG_HISTORY_NOT_VERIFIED"
    predecessor = parsed.expected_predecessor_key_id
    recovery = SR.evaluate_compromise_recovery(history, predecessor_key_id=predecessor)
    if recovery.phase != SR.RECOVERY_MARKED or recovery.reason is not None:
        return "LAG_RECOVERY_NOT_MARKED"
    head, last = history.head, history.steps[-1]
    if last.witness_version != head.witness_version or recovery.facts.get("markingWitnessVersion") != head.witness_version:
        return "LAG_MARKING_NOT_HEAD_TRANSITION"
    if (last.kind != SR.HEAD_ADVANCE or last.reason != SR.COMPROMISE_MARKING or last.prior_current != predecessor
            or predecessor not in last.marked_compromised or last.current is not None
            or last.prior_epoch != last.epoch):
        return "LAG_TRANSITION_NOT_MARKING"
    if (last.prior_head.version != observation.registry_view
            or last.head.version != observation.registry_view + 1
            or head.registry_version != last.head.version):
        return "LAG_NOT_EXACT_PREDECESSOR"
    return None


@dataclass(frozen=True)
class SignerViewV1:
    """What the signer reads itself (fixed paths, read-only). Never caller input."""

    context: WR.WitnessStoreContextV1 | None
    registries: tuple[Mapping[str, Any], ...]
    witness_store: WR.WitnessStoreObservationV1
    incomplete: tuple[str, ...] = ()


def _refused(reason: str, detail: str | None = None, **facts: Any) -> dict[str, Any]:
    assert reason in HANDLER_REASONS, reason
    return {"status": REFUSED, "reason": reason, "detail": detail, "authorityGranted": False,
            "signingPermitted": False, **facts}


class RecoveryHandlerV1:
    """The only recovery surface. Constructed with fixed-path readers."""

    def __init__(self, *, view: Callable[[], SignerViewV1], open_ledger: Callable[[], DurableAuthorityLedgerV1],
                 record_ledger_advance: Callable[[str, int, str], Mapping[str, Any]],
                 profile: SC.CustodyProfileV1 = SC.DEV_SYNTHETIC_CUSTODY_PROFILE):
        SC.require_dev_synthetic(profile)
        self._view = view
        self._open_ledger = open_ledger
        self._record_ledger_advance = record_ledger_advance
        self._profile = profile

    def __reduce__(self):
        raise TypeError("the recovery handler is not serializable")

    def handle(self, operation: str, payload: Mapping[str, Any]) -> dict[str, Any]:
        if operation not in RECOVERY_OPERATIONS:
            return _refused("RECOVERY_OPERATION_UNKNOWN")
        holds, reason, detail = PA.parse_hold_snapshot(payload.get("holdStore"), environment=self._profile.environment)
        if holds is None:
            return _refused(reason, detail)
        view = self._view()
        if not isinstance(view, SignerViewV1) or view.context is None or view.incomplete:
            return _refused("SIGNER_INPUTS_INCOMPLETE", ",".join(getattr(view, "incomplete", ())) or None)
        governing, reason, detail = self._governing(holds)
        if reason is not None:
            return _refused(reason, detail)
        try:
            ledger = self._open_ledger()
        except LedgerError as exc:
            return _refused("AUTHORITY_STATE_MISSING" if exc.reason == "AUTHORITY_STATE_MISSING"
                            else "LEDGER_UNAVAILABLE", exc.reason)
        try:
            return self._handle(operation, payload, view, governing, ledger)
        finally:
            ledger.close()

    def _governing(self, holds: SC.HoldStoreObservationV1) -> tuple[Mapping[str, Any] | None, str | None, str | None]:
        """Re-judge the COMPLETE set: exactly one HELD record may govern."""
        parsed, reason, detail = SC.parse_hold_store(holds, profile=self._profile)
        if parsed is None:
            return None, "HOLD_INVALID", reason
        held = [hold for _, hold in sorted(parsed.items()) if hold.state == SC.HELD]
        if not held:
            return None, "HOLD_SET_NO_HELD", None
        if len(held) != 1:
            return None, "HOLD_SET_OTHER_HELD", ",".join(hold.ceremony_id for hold in held)
        return held[0].to_dict(), None, None

    def _handle(self, operation: str, payload: Mapping[str, Any], view: SignerViewV1, governing: Mapping[str, Any],
                ledger: DurableAuthorityLedgerV1) -> dict[str, Any]:
        try:
            observation = ledger.observe()
        except LedgerError as exc:
            return _refused("LEDGER_UNAVAILABLE", exc.reason)
        if not observation.rows_consistent or observation.terminal_reopened:
            return _refused("LEDGER_OBSERVATION_INCONSISTENT")
        authorization = payload.get("epochAuthorization") if operation == RECOVERY_ADVANCE_EPOCH else None
        gate = SR.evaluate_recovery_gate(operation=GATE_OPERATIONS[operation], hold=governing, store=view.context,
                                         witness_store=view.witness_store, head_registries=view.registries,
                                         epoch_authorization=authorization, ledger_observation=observation,
                                         profile=self._profile)
        if not gate.permitted:
            return _refused(gate.reason, gate.detail)
        scan = WR.classify_witness_store(observation=view.witness_store, context=view.context)
        if scan.classification != WR.CONSISTENT or scan.head is None:
            return _refused("WITNESS_NOT_CONSISTENT", scan.classification)
        head = scan.head
        position = RC.authority_ledger_position_reason(observation, head)
        if operation == RECOVERY_ADVANCE_EPOCH:
            # The adoption itself carries the registry view to the target (Prep B C-4 model): after the in-epoch
            # COMPROMISE_MARKING head advance the ledger's view legitimately lags the witness by exactly that one
            # marking step. Nothing else is tolerated (`marking_lag_reason`), and never outside ADVANCE_EPOCH.
            if position == MARKING_LAG:
                lag = marking_lag_reason(observation=observation, view=view, governing=governing,
                                         profile=self._profile)
                if lag is not None:
                    return _refused("LEDGER_NOT_AT_WITNESS", lag)
            elif position is not None:
                return _refused("LEDGER_NOT_AT_WITNESS", position)
            checked = RC.verify_epoch_advance_authorization(authorization=authorization,
                                                            registry_root=view.context.registry_root,
                                                            environment=self._profile.environment)
            target = next((r for r in view.registries if _digest_of(r) == checked.authorization.target.digest), None)
            if target is None:
                return _refused("EPOCH_TARGET_REGISTRY_NOT_INSTALLED")
            try:
                op = J.epoch_adoption_op(ledger.journal(), authorization=authorization, witness=head,
                                         target_registry=target, registry_root=view.context.registry_root)
            except J.AdoptionRefusal as exc:
                return _refused("ADOPTION_REFUSED", exc.reason)
            ops = [op]
        else:
            if position is not None:
                return _refused("LEDGER_NOT_AT_WITNESS", position)
            replayed = ledger.replay()
            if operation == RECOVERY_VOID_CHALLENGE:
                ops = [{"op": J.VOID_CHALLENGE, "challengeId": cid} for cid in J.stale_prepared_challenges(replayed)]
            else:
                ops = [{"op": J.QUARANTINE_USE, "evidenceId": eid} for eid in J.stale_reserved_uses(replayed)]
            if not ops:
                return _refused("NO_PRE_RECOVERY_WORK")
        try:
            after = ledger.append_recovery(ops, expected_sequence=observation.sequence, expected_head=observation.head)
        except LedgerError as exc:
            return _refused("LEDGER_WRITE_REFUSED", exc.reason)
        result = {"status": OK, "operation": operation, "journalled": [op["op"] for op in ops],
                  "ledgerSequence": after.sequence, "ledgerHead": after.head, "authorityGranted": False,
                  "signingPermitted": False, "issuancePermitted": False}
        if operation == RECOVERY_ADVANCE_EPOCH:
            result["witness"] = "AWAITING_EPOCH_ADVANCE_EXECUTION"
            return result
        try:
            witnessed = self._record_ledger_advance(head.digest, after.sequence, after.head)
        except (OSError, ValueError) as exc:
            witnessed = {"status": REFUSED, "reason": type(exc).__name__}
        if not isinstance(witnessed, Mapping) or witnessed.get("status") != OK:
            # Committed, not witnessed: fail closed (LEDGER_AHEAD_OF_WITNESS) until the owner resolves it.
            result.update(status=LEDGER_AHEAD_OF_WITNESS, witness=dict(witnessed) if isinstance(witnessed, Mapping)
                          else None)
            return result
        result["witness"] = "RECORDED"
        return result


def _digest_of(registry: Mapping[str, Any]) -> str | None:
    try:
        return RC.registry_digest(registry)
    except (OwnerProofError, TypeError, KeyError):
        return None
