"""The RR-34 hold store: its complete root observer and its only writer (PR-1S, S-11).

`/var/lib/lilith-authority-custody/holds/` (`root:root 0700`, inside a
root-owned `0700` parent that holds only `holds`); records `root:root 0600`
regular files named `<sha256(ceremonyId)>.json`, RFC 8785 bytes.

Observer (preflight §17): the parent and the store are opened
`O_DIRECTORY|O_NOFOLLOW`; every later operation is relative to those
descriptors with no link following; the store directory descriptor is
`flock`ed (shared for observation, exclusive for writing; no lock file
inside the store); the directory's `(st_ino, st_mtime_ns, st_ctime_ns)` is
recorded before and after the listing and must not change; EVERY entry is
judged (no dot-file, temp, or backup exemption); every record is parsed and
its name re-derived. The result is the complete `HoldStoreObservationV1`,
sorted by name, with its listing digest. A caller-selected subset is never
an observation.

Writer: bounded operations only. Each builds its record from fixed
derivations and the verified host state, checks
`hold_store_transition_reason(previous, proposed)` (no record disappears,
new ceremonies start HELD, RELEASED never returns to HELD), writes a
temporary file OUTSIDE the store (in the parent), fsyncs it, renames it
into the store, and fsyncs the store and the parent. INITIAL_CUSTODY
RELEASED requires the owner-approved package digest to equal a current
re-run (RR-38). There is no generic JSON write.

    complete observation != authority
    hold release         != authority
    hold release         != S_CURRENT
"""

from __future__ import annotations

import contextlib
import os
import stat
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Iterator, Mapping

from lilith_authority_host import paths as P
from lilith_memory.owner_proof import OwnerProofError
from lilith_owner_memory import authority_contracts as A
from lilith_owner_memory import pr1_acceptance as PA
from lilith_owner_memory import rotation_contracts as RC
from lilith_owner_memory import successor_custody as SC
from lilith_owner_memory import successor_readiness as SR
from lilith_owner_memory import witness_readiness as WR

_O_DIR = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC
STORE_NAME = "holds"
RECORD_MODE = 0o600
DIRECTORY_MODE = 0o700

HOLD_STORE_ERRORS = (
    "HOLD_PARENT_MISSING",
    "HOLD_PARENT_UNSAFE",
    "HOLD_PARENT_UNEXPECTED_ENTRY",
    "HOLD_DIRECTORY_MISSING",
    "HOLD_DIRECTORY_UNSAFE",
    "HOLD_STORE_BUSY",
    "HOLD_STORE_ENTRY_INVALID",
    "HOLD_STORE_CHANGED_DURING_OBSERVATION",
    "HOLD_STORE_RECORDS_INVALID",
    "HOLD_STORE_NOT_EMPTY",
    "HOLD_CEREMONY_EXISTS",
    "HOLD_CEREMONY_ABSENT",
    "HOLD_WITNESS_NOT_CONSISTENT",
    "HOLD_GENESIS_NOT_PINNED",
    "HOLD_TRANSITION_REFUSED",
    "HOLD_RELEASE_NOT_PERMITTED",
    "HOLD_ARGUMENT_INVALID",
)


class HoldStoreError(Exception):
    def __init__(self, reason: str, detail: str | None = None):
        assert reason in HOLD_STORE_ERRORS, reason
        super().__init__(reason)
        self.reason = reason
        self.detail = detail


@dataclass(frozen=True)
class CompleteHoldObservationV1:
    """The complete root observation. `snapshot` is the one wire form."""

    observation: SC.HoldStoreObservationV1
    listing_digest: str
    directory_identity: tuple[int, int, int]
    snapshot: Mapping[str, Any]


class HoldStoreV1:
    """Fixed paths. `root`, `owner_uid`, `owner_gid` are TEST seams only."""

    def __init__(self, *, environment: str = "dev", root: Path | str = Path("/"), owner_uid: int = 0,
                 owner_gid: int = 0):
        self.profile = SC.custody_profile(environment)
        self.root = Path(root)
        self.parent = self.root / P.HOLD_STORE_PARENT.lstrip("/")
        self.owner = (owner_uid, owner_gid)

    # ---------------------------------------------------------- descriptors ---

    def _check_directory(self, fd: int, missing_unsafe: str) -> os.stat_result:
        meta = os.fstat(fd)
        if not stat.S_ISDIR(meta.st_mode) or (meta.st_uid, meta.st_gid) != self.owner \
                or stat.S_IMODE(meta.st_mode) != DIRECTORY_MODE:
            raise HoldStoreError(missing_unsafe)
        return meta

    @contextlib.contextmanager
    def _open(self, *, exclusive: bool) -> Iterator[tuple[int, int]]:
        import fcntl

        try:
            parent = os.open(self.parent, _O_DIR)
        except FileNotFoundError as exc:
            raise HoldStoreError("HOLD_PARENT_MISSING") from exc
        except OSError as exc:
            raise HoldStoreError("HOLD_PARENT_UNSAFE") from exc
        try:
            self._check_directory(parent, "HOLD_PARENT_UNSAFE")
            try:
                store = os.open(STORE_NAME, _O_DIR, dir_fd=parent)
            except FileNotFoundError as exc:
                raise HoldStoreError("HOLD_DIRECTORY_MISSING") from exc
            except OSError as exc:
                raise HoldStoreError("HOLD_DIRECTORY_UNSAFE") from exc
            try:
                self._check_directory(store, "HOLD_DIRECTORY_UNSAFE")
                try:
                    fcntl.flock(store, (fcntl.LOCK_EX if exclusive else fcntl.LOCK_SH) | fcntl.LOCK_NB)
                except BlockingIOError as exc:
                    raise HoldStoreError("HOLD_STORE_BUSY") from exc
                yield parent, store
            finally:
                os.close(store)
        finally:
            os.close(parent)

    # ------------------------------------------------------------ observer ---

    def _observe_locked(self, parent: int, store: int) -> CompleteHoldObservationV1:
        parent_names = sorted(os.listdir(parent))
        if parent_names != [STORE_NAME]:  # a leftover write scratch fails closed too
            raise HoldStoreError("HOLD_PARENT_UNEXPECTED_ENTRY", ",".join(n for n in parent_names if n != STORE_NAME))
        before = os.fstat(store)
        entries = []
        for name in sorted(os.listdir(store)):
            meta = os.stat(name, dir_fd=store, follow_symlinks=False)
            if not stat.S_ISREG(meta.st_mode) or (meta.st_uid, meta.st_gid) != self.owner \
                    or stat.S_IMODE(meta.st_mode) != RECORD_MODE or not PA._HOLD_NAME.fullmatch(name) \
                    or meta.st_size > PA.MAX_HOLD_RECORD_BYTES:
                raise HoldStoreError("HOLD_STORE_ENTRY_INVALID", name)
            fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=store)
            try:
                if os.fstat(fd).st_ino != meta.st_ino:
                    raise HoldStoreError("HOLD_STORE_CHANGED_DURING_OBSERVATION", name)
                data = os.read(fd, PA.MAX_HOLD_RECORD_BYTES + 1)
            finally:
                os.close(fd)
            entries.append(WR.StoreEntryV1(name, WR.REGULAR, data))
        after = os.fstat(store)
        identity = (before.st_ino, before.st_mtime_ns, before.st_ctime_ns)
        if identity != (after.st_ino, after.st_mtime_ns, after.st_ctime_ns):
            raise HoldStoreError("HOLD_STORE_CHANGED_DURING_OBSERVATION")
        observation = SC.HoldStoreObservationV1(tuple(entries))
        holds, reason, detail = SC.parse_hold_store(observation, profile=self.profile)
        if holds is None:
            raise HoldStoreError("HOLD_STORE_RECORDS_INVALID", f"{reason}:{detail}")
        return CompleteHoldObservationV1(observation, PA.hold_listing_digest(observation), identity,
                                         PA.hold_snapshot_document(observation, environment=self.profile.environment))

    def observe(self) -> CompleteHoldObservationV1:
        """The complete, read-consistent observation (shared lock)."""
        with self._open(exclusive=False) as (parent, store):
            return self._observe_locked(parent, store)

    # -------------------------------------------------------------- writer ---

    def _publish(self, parent: int, store: int, previous: CompleteHoldObservationV1, record: Mapping[str, Any]) -> None:
        proposed_entries = {entry.name: entry for entry in previous.observation.entries}
        name = SC.hold_record_name(record["ceremonyId"])
        data = SC.hold_record_bytes(record)
        proposed_entries[name] = WR.StoreEntryV1(name, WR.REGULAR, data)
        proposed = SC.HoldStoreObservationV1(tuple(proposed_entries[n] for n in sorted(proposed_entries)))
        reason = SC.hold_store_transition_reason(previous.observation, proposed, profile=self.profile)
        if reason is not None:
            raise HoldStoreError("HOLD_TRANSITION_REFUSED", reason)
        scratch = f".{name}.tmp"
        fd = os.open(scratch, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC, RECORD_MODE,
                     dir_fd=parent)
        try:
            view = memoryview(data)
            while view:
                view = view[os.write(fd, view):]
            os.fchmod(fd, RECORD_MODE)
            os.fsync(fd)
        finally:
            os.close(fd)
        os.rename(scratch, name, src_dir_fd=parent, dst_dir_fd=store)
        os.fsync(store)
        os.fsync(parent)

    def _witness(self, witness_store: WR.WitnessStoreObservationV1, context: WR.WitnessStoreContextV1
                 ) -> WR.WitnessRecoveryResultV1:
        scan = WR.classify_witness_store(observation=witness_store, context=context)
        if scan.classification != WR.CONSISTENT or scan.head is None or scan.genesis is None:
            raise HoldStoreError("HOLD_WITNESS_NOT_CONSISTENT", scan.classification)
        return scan

    def create_initial_held(self, *, witness_store: WR.WitnessStoreObservationV1,
                            context: WR.WitnessStoreContextV1) -> dict[str, Any]:
        """M-B10: INITIAL_CUSTODY HELD, bound to the committed, pinned V2
        genesis. Only into an EMPTY store (RR-40: never deleted or recreated)."""
        scan = self._witness(witness_store, context)
        if WR.genesis_pin_reason(context.genesis_pin, scan.genesis, environment=self.profile.environment) is not None:
            raise HoldStoreError("HOLD_GENESIS_NOT_PINNED")
        record = SC.CeremonyHoldV1(
            self.profile.environment, SC.initial_ceremony_id(self.profile.environment, self.profile.initial_key_id),
            SC.INITIAL_CUSTODY, SC.HELD, SC.INITIAL_CUSTODY_BOOTSTRAP, None, self.profile.initial_key_id,
            scan.genesis.digest).to_dict()
        with self._open(exclusive=True) as (parent, store):
            previous = self._observe_locked(parent, store)
            if previous.observation.entries:
                raise HoldStoreError("HOLD_STORE_NOT_EMPTY")
            self._publish(parent, store, previous, record)
        return record

    def release_initial(self, *, approved_package_digest: str,
                        rerun: Callable[[CompleteHoldObservationV1], PA.Pr1AcceptanceResultV1],
                        witness_store: WR.WitnessStoreObservationV1,
                        context: WR.WitnessStoreContextV1) -> dict[str, Any]:
        """M-B14: INITIAL_CUSTODY HELD -> RELEASED only when the owner-approved
        package digest equals a current HOLD_RELEASE_ELIGIBILITY re-run over
        exactly the hold store observed under this exclusive lock."""
        scan = self._witness(witness_store, context)
        ceremony = SC.initial_ceremony_id(self.profile.environment, self.profile.initial_key_id)
        with self._open(exclusive=True) as (parent, store):
            previous = self._observe_locked(parent, store)
            holds, _, _ = SC.parse_hold_store(previous.observation, profile=self.profile)
            held = holds.get(ceremony)
            if held is None or held.state != SC.HELD:
                raise HoldStoreError("HOLD_CEREMONY_ABSENT", ceremony)
            decision = PA.release_decision(approved_package_digest, rerun(previous))
            if not decision.permitted:
                raise HoldStoreError("HOLD_RELEASE_NOT_PERMITTED", decision.reason)
            if scan.head.registry_head != scan.genesis.registry_head:
                raise HoldStoreError("HOLD_RELEASE_NOT_PERMITTED", "HEAD_NOT_GENESIS_REGISTRY")
            record = SC.CeremonyHoldV1(
                held.environment, held.ceremony_id, held.transition_kind, SC.RELEASED,
                SC.OWNER_RELEASE_AFTER_ELIGIBILITY, held.expected_predecessor_key_id, held.expected_successor_key_id,
                scan.head.digest).to_dict()
            self._publish(parent, store, previous, record)
        return record

    def _head_current_key(self, scan: WR.WitnessRecoveryResultV1, registries: tuple[Mapping[str, Any], ...]) -> str:
        registry = next((r for r in registries if RC.registry_digest(r) == scan.head.registry_digest), None)
        if registry is None:
            raise HoldStoreError("HOLD_WITNESS_NOT_CONSISTENT", "HEAD_REGISTRY_NOT_INSTALLED")
        ids = RC.current_issuance_keys(A.AuthorityRegistryV1.from_verified_dict(registry))[SR.SCOPE]
        if len(ids) != 1:
            raise HoldStoreError("HOLD_WITNESS_NOT_CONSISTENT", "NO_SINGLE_CURRENT_KEY")
        return ids[0]

    def create_successor_held(self, *, kind: str, ordinal: int, witness_store: WR.WitnessStoreObservationV1,
                              context: WR.WitnessStoreContextV1,
                              registries: tuple[Mapping[str, Any], ...]) -> dict[str, Any]:
        """A ROTATION or KEY_COMPROMISE_RECOVERY HELD hold for successor N,
        engaged before its first authority step, predecessor = the head's
        current key (B1b-3e rehearsal; never run in PR-1)."""
        if kind not in SC.SUCCESSOR_KINDS:
            raise HoldStoreError("HOLD_ARGUMENT_INVALID", "kind")
        try:
            identity = SC.successor_identity(ordinal)
        except OwnerProofError as exc:
            raise HoldStoreError("HOLD_ARGUMENT_INVALID", "ordinal") from exc
        scan = self._witness(witness_store, context)
        current = self._head_current_key(scan, registries)
        reason = SC.ROTATION_IN_PROGRESS if kind == SC.ROTATION else SC.KEY_COMPROMISE_RECOVERY_IN_PROGRESS
        record = SC.CeremonyHoldV1(self.profile.environment, identity.ceremony_id, kind, SC.HELD, reason, current,
                                   identity.key_id, scan.head.digest).to_dict()
        return self._create_new(record)

    def create_maintenance_held(self, *, authorization_id: str, target_registry: Mapping[str, Any],
                                witness_store: WR.WitnessStoreObservationV1, context: WR.WitnessStoreContextV1,
                                registries: tuple[Mapping[str, Any], ...]) -> dict[str, Any]:
        """RR-31 REGISTRY_MAINTENANCE HELD for one exact head change."""
        scan = self._witness(witness_store, context)
        current = self._head_current_key(scan, registries)
        try:
            ceremony = SC.registry_maintenance_ceremony_id(
                environment=self.profile.environment, current_key_id=current, prior_head=scan.head.registry_head,
                target_head=RC.registry_head(target_registry), authorization_id=authorization_id)
        except (OwnerProofError, TypeError, KeyError) as exc:
            raise HoldStoreError("HOLD_ARGUMENT_INVALID", "maintenance") from exc
        record = SC.CeremonyHoldV1(self.profile.environment, ceremony, SC.REGISTRY_MAINTENANCE, SC.HELD,
                                   SC.REGISTRY_MAINTENANCE_IN_PROGRESS, current, current, scan.head.digest).to_dict()
        return self._create_new(record)

    def create_custody_debt_held(self, *, ordinal: int, witness_store: WR.WitnessStoreObservationV1,
                                 context: WR.WitnessStoreContextV1) -> dict[str, Any]:
        """§13: the deterministic custody-debt HELD hold after a destruction
        failure; only after the successor ceremony's own RELEASED record."""
        try:
            base_id = SC.successor_identity(ordinal).ceremony_id
        except OwnerProofError as exc:
            raise HoldStoreError("HOLD_ARGUMENT_INVALID", "ordinal") from exc
        scan = self._witness(witness_store, context)
        with self._open(exclusive=True) as (parent, store):
            previous = self._observe_locked(parent, store)
            holds, _, _ = SC.parse_hold_store(previous.observation, profile=self.profile)
            base = holds.get(base_id)
            if base is None or base.state != SC.RELEASED:
                raise HoldStoreError("HOLD_CEREMONY_ABSENT", base_id)
            debt_id = SC.custody_debt_ceremony_id(base_id)
            if debt_id in holds:
                raise HoldStoreError("HOLD_CEREMONY_EXISTS", debt_id)
            record = SC.CeremonyHoldV1(self.profile.environment, debt_id, base.transition_kind, SC.HELD,
                                       SC.PREDECESSOR_DESTRUCTION_INCOMPLETE, base.expected_predecessor_key_id,
                                       base.expected_successor_key_id, scan.head.digest).to_dict()
            self._publish(parent, store, previous, record)
        return record

    def release_with_readiness(self, *, ceremony_id: str, approved_readiness_digest: str,
                               rerun: Callable[[CompleteHoldObservationV1], SR.SuccessorReadinessResultV1],
                               witness_store: WR.WitnessStoreObservationV1,
                               context: WR.WitnessStoreContextV1) -> dict[str, Any]:
        """HELD -> RELEASED for a successor, maintenance, or custody-debt
        ceremony: a current HOLD_RELEASE_ELIGIBILITY re-run must be READY and
        its readiness digest must equal the owner-approved one."""
        scan = self._witness(witness_store, context)
        with self._open(exclusive=True) as (parent, store):
            previous = self._observe_locked(parent, store)
            holds, _, _ = SC.parse_hold_store(previous.observation, profile=self.profile)
            held = holds.get(ceremony_id)
            if held is None or held.state != SC.HELD or held.transition_kind == SC.INITIAL_CUSTODY:
                raise HoldStoreError("HOLD_CEREMONY_ABSENT", ceremony_id)
            result = rerun(previous)
            if not isinstance(result, SR.SuccessorReadinessResultV1) or result.mode != SR.HOLD_RELEASE_ELIGIBILITY \
                    or not result.ready or result.facts.get("readinessDigest") != approved_readiness_digest:
                raise HoldStoreError("HOLD_RELEASE_NOT_PERMITTED", "READINESS_DIGEST")
            record = SC.CeremonyHoldV1(held.environment, held.ceremony_id, held.transition_kind, SC.RELEASED,
                                       SC.OWNER_RELEASE_AFTER_ELIGIBILITY, held.expected_predecessor_key_id,
                                       held.expected_successor_key_id, scan.head.digest).to_dict()
            self._publish(parent, store, previous, record)
        return record

    def _create_new(self, record: Mapping[str, Any]) -> dict[str, Any]:
        with self._open(exclusive=True) as (parent, store):
            previous = self._observe_locked(parent, store)
            holds, _, _ = SC.parse_hold_store(previous.observation, profile=self.profile)
            if record["ceremonyId"] in holds:
                raise HoldStoreError("HOLD_CEREMONY_EXISTS", record["ceremonyId"])
            self._publish(parent, store, previous, record)
        return dict(record)
