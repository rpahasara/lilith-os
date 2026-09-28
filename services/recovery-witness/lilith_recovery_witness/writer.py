"""The live-capable durable RecoveryWitnessV2 writer and recovery (PR-1S, S-5, S-7, S-20).

The Source Prep A RR-9 commit order, bound to the fixed witness profile
(`pr1_bootstrap.witness_profile_reason` must pass; `prod` and any altered
identity are refused) and to one `WitnessSigningKeyV1`. It re-implements the
TEST writer's algorithm over the same storage port (tests run both writers
on identical inputs and compare every stored byte and every port operation):

    chain/<v>.json O_EXCL -> file fsync -> chain/ fsync   (commit point)
    -> pointer scratch write -> scratch fsync -> rename -> state-dir fsync

Operations (all take the store lock and re-run the recovery scan first):

- `bootstrap`: V2 genesis only, from UNINITIALIZED only, PIN-BEFORE-COMMIT
  (RR-35): the exact candidate is rebuilt from registry v1 and the ledger's
  initial position; the owner pin must equal its digest BEFORE K-WIT signs;
  K-WIT signs that exact body; after the commit the committed genesis is
  re-verified equal to the pin, and a mismatch is `GenesisCommitMismatch`
  (STOP; never a second genesis, RR-40).
- `record_ledger_advance`: the signer-path ledger-only advance.
- `execute_registry_head_advance` / `execute_epoch_advance` (RR-37, inert):
  shipped and TEST-proven, never invoked in PR-1. Each requires a K-ROOT
  authorization registered in the owner register, the governing HELD hold of
  the matching ceremony kind in a complete hold snapshot, a CONSISTENT chain
  from the pinned genesis, and the profile's environment.

Nothing here reads a file, the clock, or the environment: the core supplies
inputs. There is no generic sign operation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Mapping

from lilith_memory.owner_proof import OwnerProofError
from lilith_owner_memory import authority_contracts as A
from lilith_owner_memory import pr1_bootstrap as B
from lilith_owner_memory import rotation_contracts as RC
from lilith_owner_memory import successor_custody as SC
from lilith_owner_memory import successor_readiness as SR
from lilith_owner_memory import witness_readiness as WR

from .credential import WitnessSigningKeyV1
from .storage import STATE

# Writer seams, in commit order (identical to Source Prep A).
FAULT_POINTS = (
    "BEFORE_RETENTION_CREATE",
    "AFTER_RETENTION_WRITE",
    "AFTER_RETENTION_FILE_FSYNC",
    "AFTER_RETENTION_DIRECTORY_FSYNC",
    "BEFORE_CHAIN_CREATE",
    "AFTER_CHAIN_WRITE",
    "AFTER_CHAIN_FILE_FSYNC",
    "AFTER_CHAIN_DIRECTORY_FSYNC",       # the commit point has been reached
    "AFTER_POINTER_SCRATCH_WRITE",
    "AFTER_POINTER_SCRATCH_FSYNC",
    "AFTER_POINTER_REPLACE",
    "AFTER_POINTER_DIRECTORY_FSYNC",
)
RECOVERY_FAULT_POINTS = (
    "RECOVERY_AFTER_HEAD_FILE_FSYNC",
    "RECOVERY_AFTER_CHAIN_DIRECTORY_FSYNC",
    "RECOVERY_AFTER_POINTER_SCRATCH_WRITE",
    "RECOVERY_AFTER_POINTER_SCRATCH_FSYNC",
    "RECOVERY_AFTER_POINTER_REPLACE",
    "RECOVERY_AFTER_POINTER_DIRECTORY_FSYNC",
    "RECOVERY_AFTER_SCRATCH_REMOVE",
)

FaultHook = Callable[[str], None]

WRITER_REFUSAL_REASONS = (
    "PROFILE_INVALID",
    "CONTEXT_NOT_THIS_WITNESS",
    "STORE_NOT_UNINITIALIZED",
    "STORE_NOT_CONSISTENT",
    "GENESIS_CANDIDATE_REFUSED",
    "GENESIS_PIN_MISMATCH",
    "GENESIS_REFUSED",
    "AUTHORIZATION_NOT_VERIFIED",
    "AUTHORIZATION_CONSUMED",
    "AUTHORIZATION_NOT_REGISTERED",
    "AUTHORIZATION_REGISTER_MISMATCH",
    "RETAINED_AUTHORIZATION_CONFLICT",
    "EPOCH_ADVANCE_REASON_UNSUPPORTED",
    "HOLD_STORE_INVALID",
    "HOLD_NOT_HELD_FOR_TRANSITION",
    "HOLD_SET_OTHER_HELD",
    "HOLD_BINDING_MISMATCH",
    "PLAN_REFUSED",
    "SUCCESSION_INVALID",
    "CHAIN_ENTRY_EXISTS",
)


class WitnessRefusal(Exception):
    """Refused before the commit point; nothing was committed."""

    def __init__(self, reason: str, detail: str | None = None):
        assert reason in WRITER_REFUSAL_REASONS, reason
        super().__init__(reason)
        self.reason = reason
        self.detail = detail


class GenesisCommitMismatch(Exception):
    """The committed genesis is not the pinned candidate. STOP (RR-35, RR-40)."""


def _no_fault(point: str) -> None:
    return None


def _publish_pointer(storage: Any, data: bytes, fault: FaultHook, labels: tuple[str, ...]) -> None:
    storage.write_scratch(STATE, WR.POINTER_SCRATCH_NAME, data)
    fault(labels[0])
    storage.fsync_file(STATE, WR.POINTER_SCRATCH_NAME)
    fault(labels[1])
    storage.replace(STATE, WR.POINTER_SCRATCH_NAME, WR.POINTER_NAME)
    fault(labels[2])
    storage.fsync_directory(STATE)
    fault(labels[3])


def observe(storage: Any) -> WR.WitnessStoreObservationV1:
    """Story 4: one read of the store through the port. Never repairs."""
    state = tuple(storage.listing(STATE))
    kinds = {entry.name: entry.kind for entry in state}
    chain = tuple(storage.listing(WR.CHAIN_DIRECTORY)) if kinds.get(WR.CHAIN_DIRECTORY) == WR.DIRECTORY else ()
    retained = (tuple(storage.listing(WR.AUTHORIZATION_DIRECTORY))
                if kinds.get(WR.AUTHORIZATION_DIRECTORY) == WR.DIRECTORY else ())
    return WR.WitnessStoreObservationV1(state, chain, retained)


# --------------------------------------------------- the transition hold gate ---

# In-epoch head-advance reason -> the ceremony kind that must be HELD (RR-24, RR-31).
HEAD_ADVANCE_HOLD_KIND = {"SUCCESSOR_ROTATION": SC.ROTATION, "COMPROMISE_MARKING": SC.KEY_COMPROMISE_RECOVERY,
                          "ADMINISTRATIVE_REVOCATION": SC.REGISTRY_MAINTENANCE}


def _current_key(registry: A.AuthorityRegistryV1) -> str | None:
    ids = RC.current_issuance_keys(registry)[SR.SCOPE]
    return ids[0] if len(ids) == 1 else None


def transition_hold_reason(hold_store: Any, *, kind: str, profile: SC.CustodyProfileV1,
                           prior_registry: Mapping[str, Any], target_registry: Mapping[str, Any],
                           authorization_id: str) -> tuple[str | None, str | None]:
    """The governing HELD hold of `kind` binds this exact change (RR-37 gate).

    Over the COMPLETE hold snapshot: exactly one primary HELD hold of `kind`
    and no other HELD record; its predecessor is the prior head's current
    key; a ROTATION successor (when named) is the target's current key; a
    KEY_COMPROMISE_RECOVERY marking marks that predecessor COMPROMISED; a
    REGISTRY_MAINTENANCE ceremony ID is derived from this exact change.
    Defence in depth: K-ROOT authorizes, the hold only gates.
    """
    holds, reason, detail = SC.parse_hold_store(hold_store, profile=profile)
    if holds is None:
        return "HOLD_STORE_INVALID", reason
    held = [hold for _, hold in sorted(holds.items()) if hold.state == SC.HELD]
    governing = [hold for hold in held if hold.transition_kind == kind and not hold.custody_debt]
    if len(governing) != 1:
        return "HOLD_NOT_HELD_FOR_TRANSITION", kind
    if len(held) != 1:
        return "HOLD_SET_OTHER_HELD", ",".join(h.ceremony_id for h in held if h is not governing[0])
    hold = governing[0]
    try:
        prior = A.AuthorityRegistryV1.from_verified_dict(prior_registry)
        target = A.AuthorityRegistryV1.from_verified_dict(target_registry)
    except (OwnerProofError, TypeError, KeyError):
        return "HOLD_BINDING_MISMATCH", "REGISTRY_UNPARSED"
    current = _current_key(prior)
    if current is None or hold.expected_predecessor_key_id != current:
        return "HOLD_BINDING_MISMATCH", "PREDECESSOR"
    if kind == SC.ROTATION:
        if hold.expected_successor_key_id not in (None, _current_key(target)):
            return "HOLD_BINDING_MISMATCH", "SUCCESSOR"
    elif kind == SC.KEY_COMPROMISE_RECOVERY:
        record = target.keys.get(current)
        if record is None or not record.compromised:
            return "HOLD_BINDING_MISMATCH", "PREDECESSOR_NOT_MARKED"
    elif kind == SC.REGISTRY_MAINTENANCE:
        expected = SC.registry_maintenance_ceremony_id(
            environment=profile.environment, current_key_id=current, prior_head=RC.registry_head(prior_registry),
            target_head=RC.registry_head(target_registry), authorization_id=authorization_id)
        if hold.ceremony_id != expected or _current_key(target) != current:
            return "HOLD_BINDING_MISMATCH", "MAINTENANCE_CEREMONY"
    return None, None


def epoch_hold_reason(hold_store: Any, *, profile: SC.CustodyProfileV1, prior_registry: Mapping[str, Any]
                      ) -> tuple[str | None, str | None]:
    """An epoch advance needs the HELD KEY_COMPROMISE_RECOVERY hold naming the
    predecessor the prior head marks COMPROMISED (and no other HELD record)."""
    holds, reason, detail = SC.parse_hold_store(hold_store, profile=profile)
    if holds is None:
        return "HOLD_STORE_INVALID", reason
    held = [hold for _, hold in sorted(holds.items()) if hold.state == SC.HELD]
    governing = [hold for hold in held if hold.transition_kind == SC.KEY_COMPROMISE_RECOVERY and not hold.custody_debt]
    if len(governing) != 1:
        return "HOLD_NOT_HELD_FOR_TRANSITION", SC.KEY_COMPROMISE_RECOVERY
    if len(held) != 1:
        return "HOLD_SET_OTHER_HELD", None
    try:
        prior = A.AuthorityRegistryV1.from_verified_dict(prior_registry)
    except (OwnerProofError, TypeError, KeyError):
        return "HOLD_BINDING_MISMATCH", "REGISTRY_UNPARSED"
    record = prior.keys.get(governing[0].expected_predecessor_key_id)
    if record is None or not record.compromised:
        return "HOLD_BINDING_MISMATCH", "PREDECESSOR_NOT_COMPROMISED_AT_HEAD"
    return None, None


# ------------------------------------------------------------- the writer ---

class DevSyntheticWitnessWriterV1:
    """The one durable V2 writer (single instance; the store lock serializes)."""

    def __init__(self, *, signing_key: WitnessSigningKeyV1, storage: Any,
                 profile: B.WitnessProfileV1 = B.DEV_SYNTHETIC_WITNESS_PROFILE, fault_hook: FaultHook | None = None):
        reason = B.witness_profile_reason(profile)
        if reason is not None:
            raise WitnessRefusal("PROFILE_INVALID", reason)
        if not isinstance(signing_key, WitnessSigningKeyV1) or signing_key.witness_key_id != profile.witness_key_id:
            raise WitnessRefusal("PROFILE_INVALID", "SIGNING_KEY_NOT_PROFILE_KEY")
        self.profile = profile
        self.custody_profile = SC.custody_profile(profile.environment)
        self.__key = signing_key
        self._storage = storage
        self._fault = fault_hook or _no_fault
        self.last_retention: str | None = None

    def __reduce__(self):
        raise TypeError("the witness writer is not serializable")

    def __copy__(self):
        raise TypeError("the witness writer is not copyable")

    def __deepcopy__(self, memo):
        raise TypeError("the witness writer is not copyable")

    def public_key(self) -> bytes:
        return self.__key.public_key()

    # ------------------------------------------------------------ helpers ---

    def _check_context(self, context: WR.WitnessStoreContextV1) -> None:
        if not isinstance(context, WR.WitnessStoreContextV1) or context.environment != self.profile.environment \
                or context.anchor.witness_key_id != self.profile.witness_key_id \
                or context.anchor.public_key != self.__key.public_key() \
                or context.anchor.environment != self.profile.environment:
            raise WitnessRefusal("CONTEXT_NOT_THIS_WITNESS")

    def classify(self, context: WR.WitnessStoreContextV1) -> WR.WitnessRecoveryResultV1:
        self._check_context(context)
        return WR.classify_witness_store(observation=observe(self._storage), context=context)

    def _consistent(self, context: WR.WitnessStoreContextV1) -> RC.WitnessChainFactsV1:
        scan = self.classify(context)
        if scan.classification != WR.CONSISTENT:
            raise WitnessRefusal("STORE_NOT_CONSISTENT", scan.classification)
        return scan.chain

    def _signed(self, plan: RC.ExecutionPlanV1, previous: RC.RecoveryWitnessV2 | None) -> tuple[dict[str, Any], bytes]:
        if not plan.planned:
            raise WitnessRefusal("PLAN_REFUSED", plan.reason)
        unsigned = {**plan.successor_unsigned, "witnessKeyId": self.profile.witness_key_id}
        signed = self.__key.sign_recovery_witness_v2(unsigned)
        parsed = RC.RecoveryWitnessV2.from_verified_dict(signed)
        reason = None if previous is None else RC.witness_v2_succession_reason(previous, parsed)
        if reason is not None:
            raise WitnessRefusal("SUCCESSION_INVALID", reason)
        return signed, WR.document_bytes(signed)

    def _commit(self, signed: Mapping[str, Any], data: bytes) -> dict[str, Any]:
        name = WR.chain_entry_name(signed["witnessVersion"])
        if any(entry.name == name for entry in self._storage.listing(WR.CHAIN_DIRECTORY)):
            raise WitnessRefusal("CHAIN_ENTRY_EXISTS", name)
        self._fault("BEFORE_CHAIN_CREATE")
        self._storage.create_exclusive(WR.CHAIN_DIRECTORY, name, data)
        self._fault("AFTER_CHAIN_WRITE")
        self._storage.fsync_file(WR.CHAIN_DIRECTORY, name)
        self._fault("AFTER_CHAIN_FILE_FSYNC")
        self._storage.fsync_directory(WR.CHAIN_DIRECTORY)
        self._fault("AFTER_CHAIN_DIRECTORY_FSYNC")
        _publish_pointer(self._storage, data, self._fault, FAULT_POINTS[8:12])
        return dict(signed)

    def _retain(self, authorization: Mapping[str, Any], kind: str, authorization_id: str,
                context: WR.WitnessStoreContextV1) -> str:
        try:
            register = WR.parse_owner_register(context.owner_register)
            data = WR.document_bytes(authorization)
        except (OwnerProofError, TypeError) as exc:
            raise WitnessRefusal("AUTHORIZATION_NOT_REGISTERED") from exc
        registered = register.authorizations.get(authorization_id)
        if registered is None:
            raise WitnessRefusal("AUTHORIZATION_NOT_REGISTERED", authorization_id)
        if registered != (kind, WR.authorization_sha256(data)):
            raise WitnessRefusal("AUTHORIZATION_REGISTER_MISMATCH", authorization_id)
        name = WR.retained_authorization_name(authorization_id)
        existing = {entry.name: entry for entry in self._storage.listing(WR.AUTHORIZATION_DIRECTORY)}
        if name in existing:
            if existing[name].data != data:
                raise WitnessRefusal("RETAINED_AUTHORIZATION_CONFLICT", authorization_id)
            status = "ALREADY_RETAINED"
        else:
            self._fault("BEFORE_RETENTION_CREATE")
            self._storage.create_exclusive(WR.AUTHORIZATION_DIRECTORY, name, data)
            self._fault("AFTER_RETENTION_WRITE")
            status = "RETAINED"
        self._storage.fsync_file(WR.AUTHORIZATION_DIRECTORY, name)
        self._fault("AFTER_RETENTION_FILE_FSYNC")
        self._storage.fsync_directory(WR.AUTHORIZATION_DIRECTORY)
        self._fault("AFTER_RETENTION_DIRECTORY_FSYNC")
        return status

    # --------------------------------------------------------- operations ---

    def bootstrap(self, *, registry: Mapping[str, Any], ledger_observation: RC.AuthorityLedgerObservationV1 | None,
                  context: WR.WitnessStoreContextV1, updated_at: str) -> dict[str, Any]:
        """Owner `BOOTSTRAP` (RR-18, RR-35). Only from UNINITIALIZED."""
        with self._storage.lock():
            scan = self.classify(context)
            if scan.classification != WR.UNINITIALIZED:
                raise WitnessRefusal("STORE_NOT_UNINITIALIZED", scan.classification)
            candidate = B.build_genesis_candidate(registry=registry, registry_root=context.registry_root,
                                                  ledger_observation=ledger_observation, updated_at=updated_at,
                                                  profile=self.profile)
            if not candidate.built:
                raise WitnessRefusal("GENESIS_CANDIDATE_REFUSED", candidate.reason)
            pin_reason = B.candidate_pin_reason(context.genesis_pin, candidate, environment=self.profile.environment)
            if pin_reason is not None:
                raise WitnessRefusal("GENESIS_PIN_MISMATCH", pin_reason)  # nothing was signed
            signed = self.__key.sign_recovery_witness_v2(candidate.unsigned)
            if RC.witness_v2_digest(signed) != candidate.digest:
                raise WitnessRefusal("GENESIS_REFUSED", "SIGNED_BODY_CHANGED")
            checked = WR.verify_witness_v2_genesis(anchor=context.anchor, genesis=signed,
                                                   expectation=candidate.expectation, registry=registry,
                                                   registry_root=context.registry_root,
                                                   authority_public_keys=context.authority_public_keys)
            if not checked.verified:
                raise WitnessRefusal("GENESIS_REFUSED", checked.reason)
            for directory in (WR.CHAIN_DIRECTORY, WR.AUTHORIZATION_DIRECTORY):
                self._storage.make_directory(directory)
            self._storage.fsync_directory(STATE)
            committed = self._commit(signed, WR.document_bytes(signed))
            after = WR.classify_witness_store(observation=observe(self._storage), context=context)
            if after.classification != WR.CONSISTENT or after.genesis is None \
                    or WR.genesis_pin_reason(context.genesis_pin, after.genesis,
                                             environment=self.profile.environment) is not None:
                raise GenesisCommitMismatch(after.classification)
            return committed

    def record_ledger_advance(self, *, previous_witness_digest: str, ledger_sequence: int, ledger_head: str,
                              context: WR.WitnessStoreContextV1, updated_at: str) -> dict[str, Any]:
        """Signer path (B1b-3d §10): same epoch, same head, strictly later ledger."""
        with self._storage.lock():
            chain = self._consistent(context)
            if previous_witness_digest != chain.head.digest:
                raise WitnessRefusal("PLAN_REFUSED", "PREVIOUS_WITNESS_MISMATCH")
            plan = RC.plan_ledger_advance(chain=chain, ledger_sequence=ledger_sequence, ledger_head=ledger_head,
                                          updated_at=updated_at)
            return self._commit(*self._signed(plan, chain.head))

    def execute_registry_head_advance(self, *, authorization: Mapping[str, Any], prior_registry: Mapping[str, Any],
                                      target_registry: Mapping[str, Any], hold_store: SC.HoldStoreObservationV1,
                                      context: WR.WitnessStoreContextV1, updated_at: str) -> dict[str, Any]:
        """RR-37, inert in PR-1: K-ROOT authorization -> register -> hold gate
        -> write-once retention -> planner -> sign -> commit -> pointer."""
        with self._storage.lock():
            chain = self._consistent(context)
            checked = RC.verify_registry_head_advance_authorization(
                authorization=authorization, registry_root=context.registry_root, environment=self.profile.environment)
            if not checked.verified:
                raise WitnessRefusal("AUTHORIZATION_NOT_VERIFIED", checked.reason)
            auth = checked.authorization
            if auth.authorization_id in chain.consumed_authorization_ids:
                raise WitnessRefusal("AUTHORIZATION_CONSUMED", auth.authorization_id)
            reason, detail = transition_hold_reason(
                hold_store, kind=HEAD_ADVANCE_HOLD_KIND.get(auth.reason, ""), profile=self.custody_profile,
                prior_registry=prior_registry, target_registry=target_registry,
                authorization_id=auth.authorization_id)
            if reason is not None:
                raise WitnessRefusal(reason, detail)
            self.last_retention = self._retain(authorization, WR.REGISTRY_HEAD_ADVANCE, auth.authorization_id, context)
            plan = RC.plan_registry_head_advance(chain=chain, authorization=authorization,
                                                 registry_root=context.registry_root, prior_registry=prior_registry,
                                                 target_registry=target_registry, updated_at=updated_at)
            return self._commit(*self._signed(plan, chain.head))

    def execute_epoch_advance(self, *, authorization: Mapping[str, Any], prior_registry: Mapping[str, Any],
                              target_registry: Mapping[str, Any], adoption_record: Mapping[str, Any],
                              ledger_sequence: int, ledger_head: str, hold_store: SC.HoldStoreObservationV1,
                              context: WR.WitnessStoreContextV1, updated_at: str) -> dict[str, Any]:
        """RR-37, inert in PR-1: the C-4 witness step over the post-adoption
        ledger position. Only `KEY_COMPROMISE` (RR-32)."""
        with self._storage.lock():
            chain = self._consistent(context)
            checked = RC.verify_epoch_advance_authorization(
                authorization=authorization, registry_root=context.registry_root, environment=self.profile.environment)
            if not checked.verified:
                raise WitnessRefusal("AUTHORIZATION_NOT_VERIFIED", checked.reason)
            auth = checked.authorization
            if auth.reason != SR.KEY_COMPROMISE:
                raise WitnessRefusal("EPOCH_ADVANCE_REASON_UNSUPPORTED", auth.reason)
            if auth.authorization_id in chain.consumed_authorization_ids:
                raise WitnessRefusal("AUTHORIZATION_CONSUMED", auth.authorization_id)
            reason, detail = epoch_hold_reason(hold_store, profile=self.custody_profile, prior_registry=prior_registry)
            if reason is not None:
                raise WitnessRefusal(reason, detail)
            self.last_retention = self._retain(authorization, WR.EPOCH_ADVANCE, auth.authorization_id, context)
            plan = RC.plan_epoch_advance(chain=chain, authorization=authorization,
                                         registry_root=context.registry_root, prior_registry=prior_registry,
                                         target_registry=target_registry, adoption_record=adoption_record,
                                         ledger_sequence=ledger_sequence, ledger_head=ledger_head,
                                         updated_at=updated_at)
            return self._commit(*self._signed(plan, chain.head))


# ------------------------------------------------------------ recovery ---

@dataclass(frozen=True)
class RecoveryRunV1:
    before: WR.WitnessRecoveryResultV1
    after: WR.WitnessRecoveryResultV1
    actions: tuple[str, ...]
    facts: Mapping[str, Any] = field(default_factory=dict)


def recover(storage: Any, *, context: WR.WitnessStoreContextV1, fault_hook: FaultHook | None = None) -> RecoveryRunV1:
    """RR-9 §6.3 at witness start, holding the lock, before any operation.

    ROLL_FORWARD makes the unique verified head durable and republishes the
    pointer; discardable scratch is removed; every other outcome changes
    nothing. Idempotent. It takes no key and can never produce a witness,
    roll backward, or pick between candidates.
    """
    fault = fault_hook or _no_fault
    actions: list[str] = []
    with storage.lock():
        before = WR.classify_witness_store(observation=observe(storage), context=context)
        if before.decision == WR.ROLL_FORWARD:
            name = WR.chain_entry_name(before.head.witness_version)
            storage.fsync_file(WR.CHAIN_DIRECTORY, name)
            fault("RECOVERY_AFTER_HEAD_FILE_FSYNC")
            storage.fsync_directory(WR.CHAIN_DIRECTORY)
            fault("RECOVERY_AFTER_CHAIN_DIRECTORY_FSYNC")
            _publish_pointer(storage, before.head_bytes, fault, RECOVERY_FAULT_POINTS[2:6])
            actions.append("POINTER_ROLLED_FORWARD")
        elif before.decision == WR.NO_ACTION and before.discard_scratch:
            storage.remove(STATE, WR.POINTER_SCRATCH_NAME)
            fault("RECOVERY_AFTER_SCRATCH_REMOVE")
            storage.fsync_directory(STATE)
            actions.append("SCRATCH_DISCARDED")
        after = WR.classify_witness_store(observation=observe(storage), context=context)
    return RecoveryRunV1(before, after, tuple(actions), {
        "producedWitness": False, "usedWitnessKey": False,
        "chainLengthBefore": before.facts.get("chainLength"), "chainLengthAfter": after.facts.get("chainLength"),
    })
