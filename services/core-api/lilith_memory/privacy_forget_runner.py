"""F9-C Slice 3: the governed First Interaction FORGET runner (DEV_SYNTHETIC only).

Privacy Governance stays the only FORGET authority; this runner is its single orchestrating caller for the First
Interaction identity and holds no authority of its own:

1. ``forget`` builds the one canonical First Interaction FORGET action (the identity is fixed, never caller-supplied),
   derives the owner set from the governed policy (the family owners L04 + L18_V2, plus the Privacy required-owner
   floor read from the database, which must name HERMES_DEV_CONVERSATION), checks that every owner has an adapter,
   and only then calls ``begin_forget`` with actor evidence that was issued elsewhere. It never issues or mints
   evidence; Privacy resolves and consumes it, re-checks the floor in its transaction, and the database triggers
   enforce the floor even against other code.
2. ``resume`` drives the in-flight authorization of that identity (located through Privacy, never named by the
   caller). Owners run in a fixed order, each validating the authorization independently; an owner already COMPLETE
   is skipped, so a retry is idempotent. COMPLETE counts only when Privacy itself has recorded it.
3. ``complete()`` is called only when every owner of the authorization is COMPLETE. Any failure (missing adapter,
   refused authorization, interrupted execution, incomplete receipt, terminal result) returns INCOMPLETE_HOLD_ACTIVE:
   nothing is completed, the hold stays ACTIVE and ``resume`` can be retried.

Interim V1 (HMAC) path: refused outside DEV_SYNTHETIC. No HTTP route, no privileged operation, no session input.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Mapping, Optional, Tuple

try:
    from . import canonical_contracts as C
    from . import memory_action_v2 as MA
    from . import privacy_governance as P
except ImportError:  # deploy-exact flat-directory tests
    import canonical_contracts as C
    import memory_action_v2 as MA
    import privacy_governance as P

DEV_SYNTHETIC = "DEV_SYNTHETIC"
IDENTITY = MA.FIRST_INTERACTION_IDENTITY
# Governed owner policy of the First Interaction family, in execution order (L04 before L18_V2: L04 admissions
# reference L18 proposal rows). Floor owners follow, sorted.
FAMILY_OWNERS = ("L04", "L18_V2")
REQUIRED_FLOOR = frozenset({P.HERMES_DEV_CONVERSATION})

COMPLETE = "COMPLETE"
INCOMPLETE_HOLD_ACTIVE = "INCOMPLETE_HOLD_ACTIVE"
ALREADY_COMPLETE = "ALREADY_COMPLETE"
NOT_STARTED = "NOT_STARTED"


class ForgetRunnerError(RuntimeError):
    """Refused before anything was written (no evidence consumed, no hold created)."""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class ForgetRunResult:
    status: str
    authorization_ref_id: Optional[str] = None
    completed_owners: Tuple[str, ...] = ()
    pending_owners: Tuple[str, ...] = ()
    failure_code: Optional[str] = None
    failed_owner: Optional[str] = None
    receipt_id: Optional[str] = None
    owner_results: Dict[str, Any] = field(default_factory=dict)


def first_interaction_forget_action(actor_ref_id: str) -> C.FrozenMemoryActionV1:
    """The one FORGET action this runner submits; actor evidence must be issued for exactly this action."""
    memory_class, namespace, key = IDENTITY
    return MA.action_from_fields(
        schema_version=1, actor_ref_id=actor_ref_id, operation=C.FORGET, memory_class=memory_class,
        subject_namespace=namespace, subject_key=key, value_schema=None, payload_digest="0" * 64,
        expected_active_revision_id=None, restore_revision_id=None,
        purpose=MA.OWNER_AUTOBIOGRAPHICAL_EPISODE_ADMISSION)


class FirstInteractionForgetRunner:
    def __init__(self, privacy_authority: Any, owners: Mapping[str, Any], *, deployment_environment: str):
        if deployment_environment != DEV_SYNTHETIC:
            raise ForgetRunnerError("INTERIM_V1_PATH_DEV_SYNTHETIC_ONLY")
        for name, owner in owners.items():
            if name not in P.OWNER_SET or getattr(owner, "OWNER", None) != name:
                raise ForgetRunnerError("OWNER_ADAPTER_INVALID")
        self.privacy_authority = privacy_authority
        self.owners = dict(owners)

    def _policy_owners(self) -> Tuple[str, ...]:
        """Family owners plus the governed floor; refuses unless the floor is provisioned exactly as F9-C requires."""
        try:
            floor = self.privacy_authority.required_owners(IDENTITY[0], IDENTITY[1])
        except P.PrivacyError as exc:
            raise ForgetRunnerError("REQUIRED_OWNER_FLOOR_UNAVAILABLE") from exc
        if frozenset(floor) != REQUIRED_FLOOR:
            raise ForgetRunnerError("REQUIRED_OWNER_FLOOR_UNPROVISIONED")
        return FAMILY_OWNERS + tuple(sorted(set(floor) - set(FAMILY_OWNERS)))

    def forget(
        self,
        *,
        actor_ref_id: str,
        actor_evidence_ref_id: str,
        intent_ref_id: str,
        confirmation_event_ref: str,
    ) -> ForgetRunResult:
        owners = self._policy_owners()
        missing = [owner for owner in owners if owner not in self.owners]
        if missing:
            raise ForgetRunnerError("OWNER_ADAPTER_MISSING")            # before a hold exists that no one could finish
        if self.privacy_authority.in_flight_authorization(IDENTITY) is not None:
            raise ForgetRunnerError("FORGET_IN_FLIGHT")                 # resume() it; evidence stays unconsumed
        self.privacy_authority.begin_forget(
            action=first_interaction_forget_action(actor_ref_id),
            actor_evidence_ref_id=actor_evidence_ref_id,
            intent_ref_id=intent_ref_id,
            memory_item_id=None,
            resource_owners=owners,
            confirmation_event_ref=confirmation_event_ref,
        )
        return self.resume()

    def resume(self) -> ForgetRunResult:
        in_flight = self.privacy_authority.in_flight_authorization(IDENTITY)
        if in_flight is None:
            if self.privacy_authority.suppression_matches(IDENTITY):
                return ForgetRunResult(ALREADY_COMPLETE)                 # replay after completion: nothing to do
            return ForgetRunResult(NOT_STARTED)
        ref, nonce = in_flight
        try:
            policy = self._policy_owners()
        except ForgetRunnerError as exc:
            return ForgetRunResult(INCOMPLETE_HOLD_ACTIVE, ref, failure_code=exc.code)
        authorization = self.privacy_authority.resolve_erasure_authorization(
            ref, owner=FAMILY_OWNERS[0], execution_nonce=nonce)
        if authorization is None or authorization.identity != IDENTITY:
            return ForgetRunResult(INCOMPLETE_HOLD_ACTIVE, ref, failure_code="PRIVACY_ERASURE_NOT_AUTHORIZED")
        if set(authorization.resource_owners) != set(policy):
            return ForgetRunResult(INCOMPLETE_HOLD_ACTIVE, ref, failure_code="AUTHORIZATION_OWNER_SET_MISMATCH")
        completed, results = [], {}
        for position, owner in enumerate(policy):
            status = self.privacy_authority.owner_result(ref, nonce, owner)
            if status is None:
                adapter = self.owners.get(owner)
                code = None
                if adapter is None:
                    code = "OWNER_ADAPTER_MISSING"
                else:
                    try:
                        results[owner] = adapter.erase_authorized(ref, nonce)
                    except Exception as exc:                                # owners raise and record nothing
                        code = getattr(exc, "code", None) or (str(exc) if isinstance(exc, PermissionError)
                                                              else type(exc).__name__)
                status = self.privacy_authority.owner_result(ref, nonce, owner)     # only Privacy's record counts
                if code is None and status != COMPLETE:
                    code = "OWNER_RESULT_UNVERIFIED"
                if code is not None:
                    return ForgetRunResult(INCOMPLETE_HOLD_ACTIVE, ref, tuple(completed), policy[position:],
                                           failure_code=code, failed_owner=owner, owner_results=results)
            if status != COMPLETE:
                return ForgetRunResult(INCOMPLETE_HOLD_ACTIVE, ref, tuple(completed), policy[position:],
                                       failure_code="OWNER_RESULT_TERMINAL", failed_owner=owner, owner_results=results)
            completed.append(owner)
        try:
            receipt = self.privacy_authority.complete(ref, nonce)
        except Exception as exc:
            if self.privacy_authority.in_flight_authorization(IDENTITY) is None:   # committed, then failed after
                return self.resume()
            return ForgetRunResult(INCOMPLETE_HOLD_ACTIVE, ref, tuple(completed),
                                   failure_code="PRIVACY_COMPLETION_FAILED:" + type(exc).__name__,
                                   owner_results=results)
        if self.privacy_authority.in_flight_authorization(IDENTITY) is not None or not \
                self.privacy_authority.suppression_matches(IDENTITY):
            raise P.PrivacyError("Privacy completion left the First Interaction identity unsuppressed")
        return ForgetRunResult(COMPLETE, ref, tuple(completed), receipt_id=receipt.receipt_id,
                               owner_results=results)
