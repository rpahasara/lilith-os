"""15B2b-B1b-3e Source Prep A: TEST-ONLY durable RecoveryWitnessV2 writer and
recovery executor.

Gate: docs/architecture/slice-15b2b-b1b3e-live-rehearsal-gate.md (RR-9 §6,
RR-18, RR-20a, RR-21; SW-4, SW-5, SW-7).
Record: docs/architecture/slice-15b2b-b1b3e-source-prep-a-witness-readiness.md.

Two pieces, both outside any live path:

- `DurableWitnessV2WriterV1`: the RR-9 §6.2 commit order over an injected
  `WitnessStoragePortV1`. It signs only planner output, retains the exact
  K-ROOT authorization bytes write-once and durably BEFORE the chain entry
  exists, and counts a successor as committed only after the entry's file
  and the `chain/` directory are both fsynced. The pointer is published
  after commit and is derived state only.
- `recover_witness_store`: runs the pure `witness_readiness` scan and
  applies only what it permits. It never holds or uses K-WIT, never
  produces a witness, never rolls backward, and never picks between
  candidates.

This module performs no I/O of its own: every filesystem effect goes through
the storage port, which TEST code supplies (an in-memory durability model or
a temporary directory). There is no live adapter here, no DEV_SYNTHETIC
profile, and no path to a real witness directory.

Deterministic fault seams (`FAULT_POINTS`, `RECOVERY_FAULT_POINTS`) let tests
stop the sequence at each durability boundary with a synthetic exception.
"""

from __future__ import annotations

import base64
from contextlib import AbstractContextManager
from dataclasses import dataclass, field
from typing import Any, Callable, Mapping, Protocol

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
from lilith_memory.owner_proof import OwnerProofError

from lilith_owner_memory import authority_contracts as A
from lilith_owner_memory import recovery_contracts as R
from lilith_owner_memory import rotation_contracts as RC
from lilith_owner_memory import witness_readiness as WR

STATE = ""  # the witness state directory itself

# Writer seams, in commit order (RR-9 §6.2).
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
# Recovery seams, in repair order.
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


class WitnessStoragePortV1(Protocol):
    """Every filesystem effect the writer and recovery may have.

    Directories are `STATE` (""), `chain`, and `authorizations`. Semantics a
    TEST implementation must model: `create_exclusive` is O_CREAT|O_EXCL (+
    O_NOFOLLOW) and writes the bytes; nothing is durable until `fsync_file`
    (contents) and `fsync_directory` (the entry) are called; `replace` is an
    atomic rename within one directory.
    """

    def lock(self) -> AbstractContextManager[None]: ...
    def listing(self, directory: str) -> tuple[WR.StoreEntryV1, ...]: ...
    def make_directory(self, directory: str) -> None: ...
    def create_exclusive(self, directory: str, name: str, data: bytes) -> None: ...
    def write_scratch(self, directory: str, name: str, data: bytes) -> None: ...
    def fsync_file(self, directory: str, name: str) -> None: ...
    def fsync_directory(self, directory: str) -> None: ...
    def replace(self, directory: str, source: str, target: str) -> None: ...
    def remove(self, directory: str, name: str) -> None: ...


def observe_witness_store(storage: WitnessStoragePortV1) -> WR.WitnessStoreObservationV1:
    """Story 4: read the state directory through the port. Never repairs."""
    state = tuple(storage.listing(STATE))
    kinds = {entry.name: entry.kind for entry in state}
    chain = tuple(storage.listing(WR.CHAIN_DIRECTORY)) if kinds.get(WR.CHAIN_DIRECTORY) == WR.DIRECTORY else ()
    retained = (tuple(storage.listing(WR.AUTHORIZATION_DIRECTORY))
                if kinds.get(WR.AUTHORIZATION_DIRECTORY) == WR.DIRECTORY else ())
    return WR.WitnessStoreObservationV1(state, chain, retained)


def _b64(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _no_fault(point: str) -> None:
    return None


def _publish_pointer(storage: WitnessStoragePortV1, data: bytes, fault: FaultHook, labels: tuple[str, ...]) -> None:
    """tmp write -> tmp fsync -> rename over `witness.json` -> state-dir fsync.
    Publication only: the chain entry was already committed."""
    storage.write_scratch(STATE, WR.POINTER_SCRATCH_NAME, data)
    fault(labels[0])
    storage.fsync_file(STATE, WR.POINTER_SCRATCH_NAME)
    fault(labels[1])
    storage.replace(STATE, WR.POINTER_SCRATCH_NAME, WR.POINTER_NAME)
    fault(labels[2])
    storage.fsync_directory(STATE)
    fault(labels[3])


# ------------------------------------------------------------ the writer ---

WRITER_REFUSAL_REASONS = (
    "STORE_NOT_UNINITIALIZED",
    "STORE_NOT_CONSISTENT",
    "GENESIS_REFUSED",
    "AUTHORIZATION_NOT_VERIFIED",
    "AUTHORIZATION_NOT_REGISTERED",
    "AUTHORIZATION_REGISTER_MISMATCH",
    "RETAINED_AUTHORIZATION_CONFLICT",
    "PLAN_REFUSED",
    "SUCCESSION_INVALID",
    "CHAIN_ENTRY_EXISTS",
)


class DurableWitnessRefusal(Exception):
    """Refused before the commit point; nothing was committed."""

    def __init__(self, reason: str, detail: str | None = None):
        assert reason in WRITER_REFUSAL_REASONS, reason
        super().__init__(reason)
        self.reason = reason
        self.detail = detail


class DurableWitnessV2WriterV1:
    """TEST-ONLY durable V2 witness writer (the sole writer; single instance).

    Every operation takes the store lock, re-runs the recovery scan, and
    proceeds only from `CONSISTENT` (or `UNINITIALIZED` for the owner
    `BOOTSTRAP`). A store left mid-sequence by a fault is therefore never
    written again until `recover_witness_store` has run.
    """

    def __init__(self, *, signing_key: Ed25519PrivateKey, witness_key_id: str, environment: str,
                 storage: WitnessStoragePortV1, fault_hook: FaultHook | None = None):
        if not isinstance(signing_key, Ed25519PrivateKey):
            raise TypeError("signing key must be an in-process Ed25519 key object")
        if not (isinstance(witness_key_id, str) and witness_key_id.startswith(R.TEST_ONLY_WITNESS_PREFIX)):
            raise ValueError("the durable B1b-3e witness writer is TEST-only")
        if environment != "test":
            raise ValueError("the durable B1b-3e witness writer is TEST-only")
        self.__signing_key = signing_key
        self.witness_key_id = witness_key_id
        self.environment = environment
        self._storage = storage
        self._fault = fault_hook or _no_fault

    def __reduce__(self):
        raise TypeError("the TEST witness writer is not serializable")

    def __copy__(self):
        raise TypeError("the TEST witness writer is not copyable")

    def __deepcopy__(self, memo):
        raise TypeError("the TEST witness writer is not copyable")

    def public_key_b64(self) -> str:
        return _b64(self.__signing_key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw))

    def _classify(self, context: WR.WitnessStoreContextV1) -> WR.WitnessRecoveryResultV1:
        if context.environment != self.environment or context.anchor.witness_key_id != self.witness_key_id \
                or context.anchor.public_key != self.__signing_key.public_key().public_bytes(Encoding.Raw,
                                                                                           PublicFormat.Raw):
            raise ValueError("the store context does not name this writer's anchor")
        return WR.classify_witness_store(observation=observe_witness_store(self._storage), context=context)

    def _consistent(self, context: WR.WitnessStoreContextV1) -> RC.WitnessChainFactsV1:
        scan = self._classify(context)
        if scan.classification != WR.CONSISTENT:
            raise DurableWitnessRefusal("STORE_NOT_CONSISTENT", scan.classification)
        return scan.chain

    def _signed(self, plan: RC.ExecutionPlanV1, previous: RC.RecoveryWitnessV2 | None) -> tuple[dict[str, Any], bytes]:
        if not plan.planned:
            raise DurableWitnessRefusal("PLAN_REFUSED", plan.reason)
        unsigned = {**plan.successor_unsigned, "witnessKeyId": self.witness_key_id}
        signed = {**unsigned, "signature": _b64(self.__signing_key.sign(RC.witness_v2_signing_bytes(unsigned)))}
        parsed = RC.RecoveryWitnessV2.from_verified_dict(signed)
        reason = None if previous is None else RC.witness_v2_succession_reason(previous, parsed)
        if reason is not None:
            raise DurableWitnessRefusal("SUCCESSION_INVALID", reason)
        return signed, WR.document_bytes(signed)

    def _commit(self, signed: Mapping[str, Any], data: bytes) -> dict[str, Any]:
        """chain/<v>.json O_EXCL -> file fsync -> chain/ fsync (commit) -> pointer."""
        name = WR.chain_entry_name(signed["witnessVersion"])
        if any(entry.name == name for entry in self._storage.listing(WR.CHAIN_DIRECTORY)):
            raise DurableWitnessRefusal("CHAIN_ENTRY_EXISTS", name)
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
                context: WR.WitnessStoreContextV1) -> None:
        """Owner register check, then a durable write-once copy (RR-20a §6.8)."""
        try:
            register = WR.parse_owner_register(context.owner_register)
            data = WR.document_bytes(authorization)
        except (OwnerProofError, TypeError) as exc:
            raise DurableWitnessRefusal("AUTHORIZATION_NOT_REGISTERED") from exc
        registered = register.authorizations.get(authorization_id)
        if registered is None:
            raise DurableWitnessRefusal("AUTHORIZATION_NOT_REGISTERED", authorization_id)
        if registered != (kind, WR.authorization_sha256(data)):
            raise DurableWitnessRefusal("AUTHORIZATION_REGISTER_MISMATCH", authorization_id)
        name = WR.retained_authorization_name(authorization_id)
        existing = {entry.name: entry for entry in self._storage.listing(WR.AUTHORIZATION_DIRECTORY)}
        if name in existing:
            # Write-once: an identical earlier copy (a retry after a fault
            # before commit) is kept; any other bytes are a conflict.
            if existing[name].data != data:
                raise DurableWitnessRefusal("RETAINED_AUTHORIZATION_CONFLICT", authorization_id)
        else:
            self._fault("BEFORE_RETENTION_CREATE")
            self._storage.create_exclusive(WR.AUTHORIZATION_DIRECTORY, name, data)
            self._fault("AFTER_RETENTION_WRITE")
        self._storage.fsync_file(WR.AUTHORIZATION_DIRECTORY, name)
        self._fault("AFTER_RETENTION_FILE_FSYNC")
        self._storage.fsync_directory(WR.AUTHORIZATION_DIRECTORY)
        self._fault("AFTER_RETENTION_DIRECTORY_FSYNC")

    # --------------------------------------------------------- operations ---

    def bootstrap(self, *, expectation: WR.WitnessV2GenesisExpectationV1, registry: Mapping[str, Any],
                  context: WR.WitnessStoreContextV1, updated_at: str) -> dict[str, Any]:
        """Owner `BOOTSTRAP` at V2 genesis (RR-18). Refused over any existing
        chain, pointer, scratch, or retained authorization. There is no V1
        operation and no V1 -> V2 migration."""
        with self._storage.lock():
            scan = self._classify(context)
            if scan.classification != WR.UNINITIALIZED:
                raise DurableWitnessRefusal("STORE_NOT_UNINITIALIZED", scan.classification)
            plan = WR.plan_bound_witness_v2_genesis(expectation=expectation, registry=registry,
                                                    registry_root=context.registry_root, updated_at=updated_at)
            if not plan.planned:
                raise DurableWitnessRefusal("GENESIS_REFUSED", plan.reason)
            signed, data = self._signed(plan, None)
            checked = WR.verify_witness_v2_genesis(anchor=context.anchor, genesis=signed, expectation=expectation,
                                                   registry=registry, registry_root=context.registry_root,
                                                   authority_public_keys=context.authority_public_keys)
            if not checked.verified:
                raise DurableWitnessRefusal("GENESIS_REFUSED", checked.reason)
            for directory in (WR.CHAIN_DIRECTORY, WR.AUTHORIZATION_DIRECTORY):
                self._storage.make_directory(directory)
            self._storage.fsync_directory(STATE)
            return self._commit(signed, data)

    def record_ledger_advance(self, *, ledger_sequence: int, ledger_head: str, context: WR.WitnessStoreContextV1,
                              updated_at: str) -> dict[str, Any]:
        with self._storage.lock():
            chain = self._consistent(context)
            plan = RC.plan_ledger_advance(chain=chain, ledger_sequence=ledger_sequence, ledger_head=ledger_head,
                                          updated_at=updated_at)
            return self._commit(*self._signed(plan, chain.head))

    def execute_registry_head_advance(self, *, authorization: Mapping[str, Any], prior_registry: Mapping[str, Any],
                                      target_registry: Mapping[str, Any], context: WR.WitnessStoreContextV1,
                                      updated_at: str) -> dict[str, Any]:
        """verify K-ROOT authorization -> owner register expects it -> durable
        write-once retention -> verify target registry (planner) -> sign ->
        commit -> pointer."""
        with self._storage.lock():
            chain = self._consistent(context)
            checked = RC.verify_registry_head_advance_authorization(
                authorization=authorization, registry_root=context.registry_root, environment=self.environment)
            if not checked.verified:
                raise DurableWitnessRefusal("AUTHORIZATION_NOT_VERIFIED", checked.reason)
            self._retain(authorization, WR.REGISTRY_HEAD_ADVANCE, checked.authorization.authorization_id, context)
            plan = RC.plan_registry_head_advance(chain=chain, authorization=authorization,
                                                 registry_root=context.registry_root, prior_registry=prior_registry,
                                                 target_registry=target_registry, updated_at=updated_at)
            return self._commit(*self._signed(plan, chain.head))

    def execute_epoch_advance(self, *, authorization: Mapping[str, Any], prior_registry: Mapping[str, Any],
                              target_registry: Mapping[str, Any], adoption_record: Mapping[str, Any],
                              ledger_sequence: int, ledger_head: str, context: WR.WitnessStoreContextV1,
                              updated_at: str) -> dict[str, Any]:
        """As the head advance, for `EpochAdvanceAuthorizationV1` over the
        post-adoption authority recovery ledger position (C-4)."""
        with self._storage.lock():
            chain = self._consistent(context)
            checked = RC.verify_epoch_advance_authorization(
                authorization=authorization, registry_root=context.registry_root, environment=self.environment)
            if not checked.verified:
                raise DurableWitnessRefusal("AUTHORIZATION_NOT_VERIFIED", checked.reason)
            self._retain(authorization, WR.EPOCH_ADVANCE, checked.authorization.authorization_id, context)
            plan = RC.plan_epoch_advance(chain=chain, authorization=authorization,
                                         registry_root=context.registry_root, prior_registry=prior_registry,
                                         target_registry=target_registry, adoption_record=adoption_record,
                                         ledger_sequence=ledger_sequence, ledger_head=ledger_head,
                                         updated_at=updated_at)
            return self._commit(*self._signed(plan, chain.head))


# ------------------------------------------------------------ recovery ---

@dataclass(frozen=True)
class RecoveryRunV1:
    """One recovery run: the scan before, the actions taken, the scan after."""

    before: WR.WitnessRecoveryResultV1
    after: WR.WitnessRecoveryResultV1
    actions: tuple[str, ...]
    facts: Mapping[str, Any] = field(default_factory=dict)


def recover_witness_store(storage: WitnessStoragePortV1, *, context: WR.WitnessStoreContextV1,
                          fault_hook: FaultHook | None = None) -> RecoveryRunV1:
    """RR-9 §6.3, run at witness start holding the lock, before any operation.

    ROLL_FORWARD first makes the head entry durable (file fsync, then
    `chain/` fsync: a head visible but not yet durable becomes committed
    without any new signature), then writes the pointer by tmp / fsync /
    rename / fsync. Scratch the scan marks discardable is removed. Every
    other outcome changes nothing. Idempotent: a restart re-runs it to the
    same result. It takes no signing key and cannot produce a witness.
    """
    fault = fault_hook or _no_fault
    actions: list[str] = []
    with storage.lock():
        before = WR.classify_witness_store(observation=observe_witness_store(storage), context=context)
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
        after = WR.classify_witness_store(observation=observe_witness_store(storage), context=context)
    return RecoveryRunV1(before, after, tuple(actions), {
        "producedWitness": False, "usedWitnessKey": False,
        "chainLengthBefore": before.facts.get("chainLength"), "chainLengthAfter": after.facts.get("chainLength"),
    })
