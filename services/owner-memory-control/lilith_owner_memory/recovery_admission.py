"""15B2b-B1b-3c recovery-bound V2 admission and historical verification (TEST-ONLY).

Design: docs/architecture/slice-15b2b-b1b3c-recovery-epoch-witness.md.

Two different questions, never collapsed:

- NEW_ADMISSION_AUTHORITY: may this evidence authorize a *new* L04 admission
  now? Only if the owner challenge's `ledgerEpoch` is derived from the
  witness's current recovery epoch, the evidence was signed in that epoch,
  and the B1b-3a context takes its trusted minimum registry version and
  expected epoch from the verified witness. Then the unchanged B1b-3b
  adapter decides.
- HISTORICAL_VALIDITY: was this admission validly authorized in the epoch in
  which it happened? The owner challenge is checked against the ledger epoch
  derived from the evidence's own signed recovery epoch. That epoch is
  anchored by the current owner-signed registry: the evidence epoch must
  equal its key record's epoch there. Current compromise still applies
  retroactively. A positive answer never authorizes a new admission.

Recovery does not rewrite history, and history never becomes new authority.

This module holds public verification material only and never signs.
Nothing here detects whole-host rollback (see `recovery_contracts`).
"""

from __future__ import annotations

import dataclasses
from typing import Any, Callable, Mapping

from lilith_memory.owner_proof import OwnerProofError

from . import admission_v2 as V2
from . import authority_contracts as A
from . import contracts as K
from . import l04_v2_adapter as AD
from . import recovery_contracts as R
from . import verifier as B2A

# Closed, ordered recovery refusal taxonomy. Anything that passes these
# checks is then decided by the unchanged B1b-3b adapter / acceptance chain,
# whose own reasons are returned unchanged.
RECOVERY_REASONS = (
    "MALFORMED_CONTEXT",
    "RECOVERY_WITNESS_UNVERIFIED",
    "AUTHORITY_CONTEXT_NOT_BOUND_TO_WITNESS",
    "LEDGER_EPOCH_NOT_BOUND_TO_WITNESS",
    "STALE_EPOCH_CHALLENGE",
    "STALE_EPOCH_EVIDENCE",
    "HISTORICAL_EPOCH_UNRESOLVED",
)


class _Refuse(Exception):
    def __init__(self, reason: str, detail: str | None = None):
        assert reason in RECOVERY_REASONS, reason
        self.reason = reason
        self.detail = detail


def _require(condition: bool, reason: str, detail: str | None = None) -> None:
    if not condition:
        raise _Refuse(reason, detail)


def _witness(anchor, witness_doc, environment, registry_root) -> R.RecoveryWitnessV1:
    result = R.verify_recovery_witness(anchor=anchor, witness=witness_doc, environment=environment,
                                       registry_root=registry_root)
    _require(result.verified, "RECOVERY_WITNESS_UNVERIFIED", result.reason)
    return result.witness


def _challenge_ledger_epoch(challenge_json: Any) -> str | None:
    try:
        return B2A.parse_challenge_v2(challenge_json)["ledgerEpoch"]
    except (OwnerProofError, TypeError, ValueError, KeyError):
        return None  # malformed: the owner-proof check reports it


def _evidence_epoch(evidence: Any) -> A.RecoveryEpochV1 | None:
    if not isinstance(evidence, Mapping):
        return None
    try:
        return A.RecoveryEpochV1.from_dict(evidence.get("recoveryEpoch"))
    except (OwnerProofError, TypeError, ValueError, KeyError):
        return None  # malformed: the authority verifier reports it


def _recovery_facts(witness: R.RecoveryWitnessV1, validity: str, evidence_epoch: A.RecoveryEpochV1) -> dict:
    return {
        "validity": validity,
        "authorizesNewAdmission": validity == R.NEW_ADMISSION_AUTHORITY,
        "currentRecoveryEpoch": witness.current_recovery_epoch.to_dict(),
        "currentLedgerEpoch": witness.ledger_epoch,
        "evidenceRecoveryEpoch": evidence_epoch.to_dict(),
        "evidenceLedgerEpoch": R.ledger_epoch_id(evidence_epoch, witness.environment),
        "evidenceEpochIsCurrent": evidence_epoch == witness.current_recovery_epoch,
        "witnessVersion": witness.witness_version,
        "minimumRegistryVersion": witness.minimum_registry_version,
        "rollbackDetectionScope": R.ROLLBACK_DETECTION_SCOPE,
        "wholeHostRollbackProtected": R.WHOLE_HOST_ROLLBACK_PROTECTED,
    }


class RecoveryBoundAdmissionGateV1:
    """NEW_ADMISSION_AUTHORITY in front of the unchanged B1b-3b adapter.

    The gate reads the witness on every admission, so a witness advanced by a
    recovery ceremony immediately voids every adapter still configured for
    the old epoch, whatever the application's databases say.
    """

    def __init__(self, adapter: AD.L04V2AdmissionAdapter, *,
                 witness_provider: Callable[[], Mapping[str, Any] | None],
                 witness_anchor: R.TrustedWitnessAnchorV1, registry_root: A.TrustedRegistryRootV1):
        if not isinstance(adapter, AD.L04V2AdmissionAdapter):
            raise TypeError("the gate wraps the unchanged B1b-3b L04V2AdmissionAdapter")
        if not callable(witness_provider) or not isinstance(witness_anchor, R.TrustedWitnessAnchorV1) \
                or not isinstance(registry_root, A.TrustedRegistryRootV1):
            raise TypeError("witness provider, witness anchor, or registry root is invalid")
        self.adapter = adapter
        self.witness_provider = witness_provider
        self.witness_anchor = witness_anchor
        self.registry_root = registry_root

    def admit(self, request: AD.V2AdmissionRequestV1) -> V2.V2ResultV1:
        try:
            _require(isinstance(request, AD.V2AdmissionRequestV1), "MALFORMED_CONTEXT")
            owner, authority = self.adapter.owner_context, self.adapter.authority_context
            witness = _witness(self.witness_anchor, self.witness_provider(), authority.environment,
                               self.registry_root)
            _require(authority == R.witness_authority_context(
                witness, registry_root=self.registry_root, purpose=A.NEW_ADMISSION),
                "AUTHORITY_CONTEXT_NOT_BOUND_TO_WITNESS")
            _require(owner.deployment_environment == witness.environment
                     and owner.ledger_epoch == witness.ledger_epoch, "LEDGER_EPOCH_NOT_BOUND_TO_WITNESS")
            challenge_epoch = _challenge_ledger_epoch(request.challenge_json)
            _require(challenge_epoch is None or challenge_epoch == witness.ledger_epoch, "STALE_EPOCH_CHALLENGE")
            evidence_epoch = _evidence_epoch(request.evidence)
            _require(evidence_epoch is None or evidence_epoch == witness.current_recovery_epoch,
                     "STALE_EPOCH_EVIDENCE")
        except _Refuse as refused:
            return V2.V2ResultV1(V2.NOT_ACCEPTED, refused.reason, refused.detail)
        result = self.adapter.admit(request)
        if result.status != AD.L04_ADMITTED:
            return result
        return V2.V2ResultV1(result.status, None, None, {
            **result.facts, "recovery": _recovery_facts(witness, R.NEW_ADMISSION_AUTHORITY, evidence_epoch)})


def verify_historical_accepted_memory(
    *,
    witness: Mapping[str, Any] | None,
    witness_anchor: R.TrustedWitnessAnchorV1,
    registry_root: A.TrustedRegistryRootV1,
    owner_context: K.AcceptanceContextV1,
    **chain: Any,
) -> V2.V2ResultV1:
    """HISTORICAL_VALIDITY of one V2 admission after any number of recoveries.

    `chain` is the B1b-3b `verify_accepted_memory_v2` artifact set (action,
    challenge_json, challenge_record, assertion, owner_credential, registry,
    evidence, admission, link, evidence_use). The registry must be the
    current one (verified against the witness floor), so compromise and
    downgrade rules stay current. The owner context's ledger epoch is
    replaced by the one derived from the evidence's own signed epoch.
    """
    try:
        _require(isinstance(owner_context, K.AcceptanceContextV1), "MALFORMED_CONTEXT")
        verified = _witness(witness_anchor, witness, owner_context.deployment_environment, registry_root)
        evidence_epoch = _evidence_epoch(chain.get("evidence"))
        _require(evidence_epoch is not None, "HISTORICAL_EPOCH_UNRESOLVED")
        historical_ledger_epoch = R.ledger_epoch_id(evidence_epoch, verified.environment)
        _require(_challenge_ledger_epoch(chain.get("challenge_json")) in {None, historical_ledger_epoch},
                 "STALE_EPOCH_CHALLENGE")
        context = R.witness_authority_context(verified, registry_root=registry_root,
                                              purpose=A.HISTORICAL_VERIFICATION)
    except _Refuse as refused:
        return V2.V2ResultV1(V2.NOT_ACCEPTED, refused.reason, refused.detail)
    result = V2.verify_accepted_memory_v2(
        owner_context=dataclasses.replace(owner_context, ledger_epoch=historical_ledger_epoch),
        authority_context=context, **chain)
    if result.status != V2.ACCEPTED_MEMORY:
        return result
    return V2.V2ResultV1(result.status, None, None, {
        **result.facts, "recovery": _recovery_facts(verified, R.HISTORICAL_VALIDITY, evidence_epoch)})
