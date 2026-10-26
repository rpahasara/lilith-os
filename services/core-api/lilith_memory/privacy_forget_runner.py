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

Identities (closed; ``ForgetProfileV1``): the runner is built for exactly one profile and never takes an identity from
a caller. ``FIRST_INTERACTION_FORGET`` (the default, unchanged: floor exactly HERMES_DEV_CONVERSATION) and
``RELATIONSHIP_ORIGIN_FORGET``: the owner-provided relationship-origin memory, owned by L04 and L18_V2. Privacy admits
the Hermes owner only for a scope whose floor provisions it, so HERMES_DEV_CONVERSATION joins this FORGET exactly when
the governed floor names it for the origin scope (and never otherwise); the Hermes read route serves the memory to
Hermes only under that same floor.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Mapping, Optional, Tuple

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


@dataclass(frozen=True)
class ForgetProfileV1:
    """One governed FORGET identity: its FORGET action purpose, its owners in execution order (floor owners follow,
    sorted) and the exact Privacy floors it accepts. ``label`` names it in the durable intent."""

    label: str
    identity: Tuple[str, str, str]
    purpose: str
    family_owners: Tuple[str, ...]
    allowed_floors: Tuple[frozenset, ...]


FIRST_INTERACTION_FORGET = ForgetProfileV1("FIRST_INTERACTION", IDENTITY, MA.OWNER_AUTOBIOGRAPHICAL_EPISODE_ADMISSION,
                                           FAMILY_OWNERS, (REQUIRED_FLOOR,))
RELATIONSHIP_ORIGIN_FORGET = ForgetProfileV1(
    "RELATIONSHIP_ORIGIN", MA.RELATIONSHIP_ORIGIN_IDENTITY, MA.LONG_TERM_OWNER_RELATIONSHIP_ORIGIN_RECALL,
    FAMILY_OWNERS, (frozenset(), REQUIRED_FLOOR))
PROFILES = (FIRST_INTERACTION_FORGET, RELATIONSHIP_ORIGIN_FORGET)

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


def forget_action(profile: ForgetProfileV1, actor_ref_id: str) -> C.FrozenMemoryActionV1:
    """The one FORGET action a runner of ``profile`` submits; actor evidence must be issued for exactly this action."""
    memory_class, namespace, key = profile.identity
    return MA.action_from_fields(
        schema_version=1, actor_ref_id=actor_ref_id, operation=C.FORGET, memory_class=memory_class,
        subject_namespace=namespace, subject_key=key, value_schema=None, payload_digest="0" * 64,
        expected_active_revision_id=None, restore_revision_id=None, purpose=profile.purpose)


def first_interaction_forget_action(actor_ref_id: str) -> C.FrozenMemoryActionV1:
    """The one First Interaction FORGET action; actor evidence must be issued for exactly this action."""
    return forget_action(FIRST_INTERACTION_FORGET, actor_ref_id)


class FirstInteractionForgetRunner:
    def __init__(self, privacy_authority: Any, owners: Mapping[str, Any], *, deployment_environment: str,
                 durability_barrier: Optional[Callable[[], Optional[str]]] = None,
                 profile: ForgetProfileV1 = FIRST_INTERACTION_FORGET):
        """``durability_barrier`` (Track B, durable-before-erase; REQUIRED): called before any owner erases; None
        means the current suppression set is anchored and owner-checkpointed, anything else is a refusal code and the
        FORGET stays INCOMPLETE_HOLD_ACTIVE with nothing erased (``resume`` continues once the checkpoint is applied).
        The governed barrier is ``privacy_freshness.DurabilityBarrier``. The historical F9c2 DEV_SYNTHETIC drill ran
        before Track B with none; a runner without one is now refused, so no composition can erase undurably."""
        if deployment_environment != DEV_SYNTHETIC:
            raise ForgetRunnerError("INTERIM_V1_PATH_DEV_SYNTHETIC_ONLY")
        for name, owner in owners.items():
            if name not in P.OWNER_SET or getattr(owner, "OWNER", None) != name:
                raise ForgetRunnerError("OWNER_ADAPTER_INVALID")
        if durability_barrier is None:
            raise ForgetRunnerError("DURABILITY_BARRIER_REQUIRED")
        if not callable(durability_barrier):
            raise ForgetRunnerError("DURABILITY_BARRIER_INVALID")
        if profile not in PROFILES:                                       # a closed set, never a caller's identity
            raise ForgetRunnerError("FORGET_PROFILE_UNKNOWN")
        self.profile = profile
        self.identity = profile.identity
        self.privacy_authority = privacy_authority
        self.owners = dict(owners)
        self.durability_barrier = durability_barrier

    def _policy_owners(self) -> Tuple[str, ...]:
        """Family owners plus the governed floor; refuses unless the floor is provisioned exactly as the profile
        accepts (First Interaction: exactly HERMES_DEV_CONVERSATION; relationship origin: empty or exactly that)."""
        try:
            floor = self.privacy_authority.required_owners(self.identity[0], self.identity[1])
        except P.PrivacyError as exc:
            raise ForgetRunnerError("REQUIRED_OWNER_FLOOR_UNAVAILABLE") from exc
        if frozenset(floor) not in self.profile.allowed_floors:
            raise ForgetRunnerError("REQUIRED_OWNER_FLOOR_UNPROVISIONED")
        family = self.profile.family_owners
        return family + tuple(sorted(set(floor) - set(family)))

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
        if self.privacy_authority.in_flight_authorization(self.identity) is not None:
            raise ForgetRunnerError("FORGET_IN_FLIGHT")                 # resume() it; evidence stays unconsumed
        self.privacy_authority.begin_forget(
            action=forget_action(self.profile, actor_ref_id),
            actor_evidence_ref_id=actor_evidence_ref_id,
            intent_ref_id=intent_ref_id,
            memory_item_id=None,
            resource_owners=owners,
            confirmation_event_ref=confirmation_event_ref,
        )
        return self.resume()

    def resume(self) -> ForgetRunResult:
        in_flight = self.privacy_authority.in_flight_authorization(self.identity)
        if in_flight is None:
            if self.privacy_authority.suppression_matches(self.identity):
                return ForgetRunResult(ALREADY_COMPLETE)                 # replay after completion: nothing to do
            return ForgetRunResult(NOT_STARTED)
        ref, nonce = in_flight
        try:
            policy = self._policy_owners()
        except ForgetRunnerError as exc:
            return ForgetRunResult(INCOMPLETE_HOLD_ACTIVE, ref, failure_code=exc.code)
        authorization = self.privacy_authority.resolve_erasure_authorization(
            ref, owner=self.profile.family_owners[0], execution_nonce=nonce)
        if authorization is None or authorization.identity != self.identity:
            return ForgetRunResult(INCOMPLETE_HOLD_ACTIVE, ref, failure_code="PRIVACY_ERASURE_NOT_AUTHORIZED")
        if set(authorization.resource_owners) != set(policy):
            return ForgetRunResult(INCOMPLETE_HOLD_ACTIVE, ref, failure_code="AUTHORIZATION_OWNER_SET_MISMATCH")
        try:
            refusal = self.durability_barrier()
        except Exception as exc:                                            # an unverifiable barrier is a refusal
            refusal = "DURABILITY_BARRIER:" + type(exc).__name__
        if refusal is not None:
            return ForgetRunResult(INCOMPLETE_HOLD_ACTIVE, ref, (), policy, failure_code=str(refusal))
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
            if self.privacy_authority.in_flight_authorization(self.identity) is None:  # committed, failed after
                return self.resume()
            return ForgetRunResult(INCOMPLETE_HOLD_ACTIVE, ref, tuple(completed),
                                   failure_code="PRIVACY_COMPLETION_FAILED:" + type(exc).__name__,
                                   owner_results=results)
        if self.privacy_authority.in_flight_authorization(self.identity) is not None or not \
                self.privacy_authority.suppression_matches(self.identity):
            raise P.PrivacyError(f"Privacy completion left the {self.profile.label} identity unsuppressed")
        return ForgetRunResult(COMPLETE, ref, tuple(completed), receipt_id=receipt.receipt_id,
                               owner_results=results)
