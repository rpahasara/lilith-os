"""TEST_ONLY fixtures for 15B2b-B1b-3e Source Prep A (witness durability and readiness).

- `SimulatedDurableStorage`: an in-memory model of a POSIX directory tree with
  explicit durability. File contents become durable only on `fsync_file`; a
  directory entry (create, rename, unlink) becomes durable only on
  `fsync_directory`. `crash()` discards everything not yet durable. Every
  operation is logged, so tests prove ORDER, not only final files.
- `TempDirectoryStorage`: the same port over a real temporary directory
  (`O_EXCL | O_NOFOLLOW`, `fsync`, directory `fsync`, `os.replace`, `flock`).
  POSIX only; never pointed at any real witness path.
- `DurableScenario`: bootstrap at V2 genesis over the B1b-3e synthetic v3
  registry, the owner pin and register, rotation to v4, and an epoch advance.

No real key, credential, witness, registry, ledger, or authority exists.
Run `python synthetic_b1b3e_prep_a.py --write-golden` only to regenerate the
golden file deliberately.
"""

from __future__ import annotations

import contextlib
import copy
import hashlib
import json
import os
import stat
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

import synthetic_b1b3e as F
from lilith_authority_signer import synthetic_witness_store as WS
from lilith_authority_signer import synthetic_witness_v2 as W2
from lilith_owner_memory import authority_contracts as A
from lilith_owner_memory import rotation_contracts as RC
from lilith_owner_memory import witness_readiness as WR

GOLDEN_PATH = Path(__file__).with_name("b1b3e_prep_a_golden.json")
STATE = WS.STATE


# ----------------------------------------------------- in-memory durability ---

class LockHeld(RuntimeError):
    pass


class _Inode:
    def __init__(self, kind: str, data: bytes = b""):
        self.kind = kind
        self.volatile = data
        self.durable = b""


class _Directory:
    def __init__(self) -> None:
        self.volatile: dict[str, _Inode] = {}
        self.durable: dict[str, _Inode] = {}


class SimulatedDurableStorage:
    """TEST model: what survives a crash is exactly what was fsynced."""

    def __init__(self) -> None:
        self.tree: dict[str, _Directory] = {STATE: _Directory()}
        self.log: list[tuple[str, ...]] = []
        self._locked = False
        self.reverse_listing = False

    # port -----------------------------------------------------------------
    @contextlib.contextmanager
    def lock(self):
        if self._locked:
            raise LockHeld("witness.lock is held")
        self._locked = True
        self.log.append(("lock",))
        try:
            yield
        finally:
            self._locked = False
            self.log.append(("unlock",))

    def listing(self, directory: str) -> tuple[WR.StoreEntryV1, ...]:
        entries = [WR.StoreEntryV1(name, inode.kind, inode.volatile if inode.kind == WR.REGULAR else None)
                   for name, inode in self.tree[directory].volatile.items()]
        entries.sort(key=lambda e: e.name, reverse=self.reverse_listing)
        return tuple(entries)

    def make_directory(self, directory: str) -> None:
        self.log.append(("mkdir", directory))
        if directory not in self.tree[STATE].volatile:
            self.tree[STATE].volatile[directory] = _Inode(WR.DIRECTORY)
            self.tree[directory] = _Directory()

    def create_exclusive(self, directory: str, name: str, data: bytes) -> None:
        self.log.append(("create", directory, name))
        folder = self.tree[directory]
        if name in folder.volatile:
            raise FileExistsError(name)
        folder.volatile[name] = _Inode(WR.REGULAR, bytes(data))

    def write_scratch(self, directory: str, name: str, data: bytes) -> None:
        self.log.append(("write", directory, name))
        folder = self.tree[directory]
        if name in folder.volatile:
            folder.volatile[name].volatile = bytes(data)
        else:
            folder.volatile[name] = _Inode(WR.REGULAR, bytes(data))

    def fsync_file(self, directory: str, name: str) -> None:
        self.log.append(("fsync_file", directory, name))
        inode = self.tree[directory].volatile[name]
        inode.durable = inode.volatile

    def fsync_directory(self, directory: str) -> None:
        self.log.append(("fsync_dir", directory))
        folder = self.tree[directory]
        folder.durable = dict(folder.volatile)

    def replace(self, directory: str, source: str, target: str) -> None:
        self.log.append(("replace", directory, source, target))
        folder = self.tree[directory]
        folder.volatile[target] = folder.volatile.pop(source)

    def remove(self, directory: str, name: str) -> None:
        self.log.append(("remove", directory, name))
        del self.tree[directory].volatile[name]

    # TEST controls --------------------------------------------------------
    def crash(self) -> None:
        """Power loss: keep only durable entries and durable contents."""
        state = self.tree[STATE]
        state.volatile = dict(state.durable)
        for name in list(self.tree):
            if name != STATE and name not in state.durable:
                del self.tree[name]
        for folder in self.tree.values():
            folder.volatile = dict(folder.durable)
            for inode in folder.volatile.values():
                inode.volatile = inode.durable
        self._locked = False
        self.log.append(("crash",))

    def plant(self, directory: str, name: str, data: bytes | None = None, *, kind: str = WR.REGULAR) -> None:
        """Durably place an entry (a TEST adversary or corruption model)."""
        folder = self.tree[directory]
        inode = _Inode(kind, b"" if data is None else bytes(data))
        inode.durable = inode.volatile
        folder.volatile[name] = inode
        folder.durable[name] = inode

    def drop(self, directory: str, name: str) -> None:
        self.tree[directory].volatile.pop(name, None)
        self.tree[directory].durable.pop(name, None)

    def read(self, directory: str, name: str) -> bytes | None:
        inode = self.tree.get(directory, _Directory()).volatile.get(name)
        return None if inode is None else inode.volatile

    def names(self, directory: str) -> list[str]:
        return sorted(self.tree.get(directory, _Directory()).volatile)

    def snapshot(self) -> dict[str, dict[str, bytes | None]]:
        return {d: {n: (i.volatile if i.kind == WR.REGULAR else None) for n, i in f.volatile.items()}
                for d, f in self.tree.items()}


# ------------------------------------------------- real temp directory (POSIX) ---

class TempDirectoryStorage:
    """The storage port over a real temporary directory. POSIX only."""

    def __init__(self, root: str):
        self.root = root
        self.log: list[tuple[str, ...]] = []

    def _path(self, directory: str, name: str | None = None) -> str:
        parts = [self.root] + ([directory] if directory else []) + ([name] if name else [])
        return os.path.join(*parts)

    @contextlib.contextmanager
    def lock(self):
        import fcntl
        fd = os.open(self._path(STATE, WR.LOCK_NAME), os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600)
        try:
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as exc:
                raise LockHeld("witness.lock is held") from exc
            self.log.append(("lock",))
            yield
        finally:
            os.close(fd)
            self.log.append(("unlock",))

    def listing(self, directory: str) -> tuple[WR.StoreEntryV1, ...]:
        found = []
        with os.scandir(self._path(directory)) as it:
            for item in it:
                mode = os.lstat(item.path).st_mode
                if stat.S_ISLNK(mode):
                    found.append(WR.StoreEntryV1(item.name, WR.SYMLINK))
                elif stat.S_ISDIR(mode):
                    found.append(WR.StoreEntryV1(item.name, WR.DIRECTORY))
                elif stat.S_ISREG(mode):
                    fd = os.open(item.path, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC)
                    try:
                        chunks = []
                        while chunk := os.read(fd, 65536):
                            chunks.append(chunk)
                    finally:
                        os.close(fd)
                    found.append(WR.StoreEntryV1(item.name, WR.REGULAR, b"".join(chunks)))
                else:
                    found.append(WR.StoreEntryV1(item.name, WR.OTHER))
        return tuple(found)

    def make_directory(self, directory: str) -> None:
        self.log.append(("mkdir", directory))
        try:
            os.mkdir(self._path(directory), 0o700)
        except FileExistsError:
            pass

    def _write(self, path: str, data: bytes, flags: int) -> None:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_NOFOLLOW | os.O_CLOEXEC | flags, 0o600)
        try:
            view = memoryview(data)
            while view:
                view = view[os.write(fd, view):]
        finally:
            os.close(fd)

    def create_exclusive(self, directory: str, name: str, data: bytes) -> None:
        self.log.append(("create", directory, name))
        self._write(self._path(directory, name), data, os.O_EXCL)

    def write_scratch(self, directory: str, name: str, data: bytes) -> None:
        self.log.append(("write", directory, name))
        self._write(self._path(directory, name), data, os.O_TRUNC)

    def fsync_file(self, directory: str, name: str) -> None:
        self.log.append(("fsync_file", directory, name))
        fd = os.open(self._path(directory, name), os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)

    def fsync_directory(self, directory: str) -> None:
        self.log.append(("fsync_dir", directory))
        fd = os.open(self._path(directory), os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)

    def replace(self, directory: str, source: str, target: str) -> None:
        self.log.append(("replace", directory, source, target))
        os.replace(self._path(directory, source), self._path(directory, target))

    def remove(self, directory: str, name: str) -> None:
        self.log.append(("remove", directory, name))
        os.unlink(self._path(directory, name))


# -------------------------------------------------------- fault injection ---

class InjectedFault(Exception):
    """A synthetic crash signal raised at one durability seam."""


def fault_at(point: str) -> Callable[[str], None]:
    def hook(seen: str) -> None:
        if seen == point:
            raise InjectedFault(point)
    return hook


# --------------------------------------------------------- owner inputs ---

def genesis_expectation(registry: dict[str, Any] | None = None, ledger=None,
                        **overrides: Any) -> WR.WitnessV2GenesisExpectationV1:
    registry = registry or F.v3()
    ledger = ledger or F.seeded_ledger()
    value = dict(environment=F.ENV, registry_head=RC.registry_head(registry),
                 recovery_epoch=A.RecoveryEpochV1.from_dict(registry["recoveryEpoch"]),
                 policy_version=registry["policyVersion"], ledger_sequence=ledger.sequence,
                 ledger_head=ledger.head)
    value.update(overrides)
    return WR.WitnessV2GenesisExpectationV1(**value)


def genesis_pin(genesis: dict[str, Any], **overrides: Any) -> dict[str, Any]:
    value = WR.OwnerGenesisPinV1(F.ENV, RC.witness_v2_digest(genesis)).to_dict()
    value.update(overrides)
    return value


def owner_register(authorizations: dict[str, tuple[str, str]], heads, **overrides: Any) -> dict[str, Any]:
    value = {
        "registerType": WR.REGISTER_TYPE, "schemaVersion": WR.REGISTER_SCHEMA_VERSION, "environment": F.ENV,
        "authorizations": [{"authorizationId": i, "kind": k, "authorizationSha256": d}
                           for i, (k, d) in sorted(authorizations.items())],
        "headRegistries": [{"registryVersion": h.version, "registryDigest": h.digest}
                           for h in sorted(heads, key=lambda h: (h.version, h.digest))],
    }
    value.update(overrides)
    return value


def register_entry(authorization: dict[str, Any], kind: str) -> tuple[str, tuple[str, str]]:
    return authorization["authorizationId"], (kind, WR.authorization_sha256(WR.document_bytes(authorization)))


# ------------------------------------------------------------- scenario ---

@dataclass
class DurableScenario:
    """One synthetic witness host: bootstrap, rotation, ledger advances, recovery."""

    storage: Any = field(default_factory=SimulatedDurableStorage)
    ledger: Any = field(default_factory=F.seeded_ledger)
    ticks: int = 0
    fault_hook: Callable[[str], None] | None = None

    def __post_init__(self) -> None:
        self.issued: dict[str, tuple[str, str]] = {}
        self.heads = {RC.registry_head(F.v3())}
        self.registries: list[dict[str, Any]] = [F.v3()]
        self.registry = F.v3()
        self.pin: dict[str, Any] | None = None
        self.writer = WS.DurableWitnessV2WriterV1(signing_key=F.private("witness"), witness_key_id=F.WITNESS_KEY_ID,
                                                  environment=F.ENV, storage=self.storage,
                                                  fault_hook=lambda p: self.fault_hook and self.fault_hook(p))
        armed, self.fault_hook = self.fault_hook, None  # faults are armed only after genesis
        self.genesis = self.writer.bootstrap(expectation=genesis_expectation(self.registry, self.ledger),
                                             registry=self.registry, context=self.context(), updated_at=self.tick())
        self.pin = genesis_pin(self.genesis)
        self.fault_hook = armed

    def tick(self) -> str:
        self.ticks += 1
        return F.stamp(self.ticks)

    def clone(self) -> DurableScenario:
        """An independent copy (storage, ledger, owner inputs) with its own writer."""
        other = object.__new__(DurableScenario)
        other.__dict__.update({k: copy.deepcopy(v) for k, v in self.__dict__.items() if k != "writer"})
        other.writer = WS.DurableWitnessV2WriterV1(signing_key=F.private("witness"), witness_key_id=F.WITNESS_KEY_ID,
                                                   environment=F.ENV, storage=other.storage,
                                                   fault_hook=lambda p: other.fault_hook and other.fault_hook(p))
        return other

    def register(self, **overrides: Any) -> dict[str, Any]:
        return owner_register(self.issued, self.heads, **overrides)

    def context(self, **overrides: Any) -> WR.WitnessStoreContextV1:
        value = dict(anchor=F.anchor(), environment=F.ENV, registry_root=F.root(), genesis_pin=self.pin,
                     owner_register=self.register(), authority_public_keys=frozenset())
        value.update(overrides)
        return WR.WitnessStoreContextV1(**value)

    def scan(self, **overrides: Any) -> WR.WitnessRecoveryResultV1:
        return WR.classify_witness_store(observation=WS.observe_witness_store(self.storage),
                                         context=self.context(**overrides))

    def recover(self, fault_hook=None, **overrides: Any) -> WS.RecoveryRunV1:
        return WS.recover_witness_store(self.storage, context=self.context(**overrides), fault_hook=fault_hook)

    @property
    def head(self) -> RC.RecoveryWitnessV2:
        return RC.RecoveryWitnessV2.from_verified_dict(json.loads(self.storage.read(STATE, WR.POINTER_NAME)))

    # owner / K-ROOT side ---------------------------------------------------
    def issue_head_advance(self, prior=None, target=None, **overrides: Any) -> dict[str, Any]:
        prior, target = prior or F.v3(), target or F.v4()
        authorization = F.head_authorization(prior, target, **overrides)
        key, value = register_entry(authorization, WR.REGISTRY_HEAD_ADVANCE)
        self.issued[key] = value
        self.heads.add(RC.registry_head(target))
        self.registries.append(target)
        return authorization

    def issue_epoch_advance(self, target=None, **overrides: Any) -> dict[str, Any]:
        target = target or F.v5()
        authorization = F.epoch_authorization(self.head, target, **overrides)
        key, value = register_entry(authorization, WR.EPOCH_ADVANCE)
        self.issued[key] = value
        self.heads.add(RC.registry_head(target))
        self.registries.append(target)
        return authorization

    # witness side ----------------------------------------------------------
    def publish(self, authorization: dict[str, Any], prior=None, target=None, **context: Any) -> dict[str, Any]:
        target = target or F.v4()
        signed = self.writer.execute_registry_head_advance(
            authorization=authorization, prior_registry=prior or self.registry, target_registry=target,
            context=self.context(**context), updated_at=self.tick())
        self.registry = target
        return signed

    def record_ledger(self) -> dict[str, Any]:
        return self.writer.record_ledger_advance(ledger_sequence=self.ledger.sequence, ledger_head=self.ledger.head,
                                                 context=self.context(), updated_at=self.tick())

    def activate(self) -> dict[str, Any]:
        """Signer-side registry view journalled; the witness records the ledger advance."""
        self.ledger = self.ledger.record_registry(self.registry["registryVersion"], (F.SUCCESSOR,), F.POLICY)
        return self.record_ledger()

    def rotate(self) -> DurableScenario:
        self.publish(self.issue_head_advance())
        self.activate()
        return self

    def epoch_advance(self, target=None) -> dict[str, Any]:
        target = target or F.v5()
        authorization = self.issue_epoch_advance(target)
        self.ledger = W2.adopt_authorized_epoch(self.ledger, authorization=authorization, witness=self.head,
                                                target_registry=target, registry_root=F.root())
        signed = self.writer.execute_epoch_advance(
            authorization=authorization, prior_registry=self.registry, target_registry=target,
            adoption_record=self.ledger.log[-1], ledger_sequence=self.ledger.sequence,
            ledger_head=self.ledger.head, context=self.context(), updated_at=self.tick())
        self.registry = target
        return signed

    # readiness inputs ------------------------------------------------------
    def readiness_inputs(self, **overrides: Any) -> WR.WitnessReadinessInputsV1:
        value = dict(
            environment=F.ENV, signing_domain=A.OWNER_ACTOR, evidence_type=A.OWNER_MEMORY_OPERATION,
            store=self.context(), witness_store=WS.observe_witness_store(self.storage),
            head_registries=tuple(self.registries), ledger_observation=W2.observe_authority_recovery_ledger(self.ledger),
            observed_blob_sha256=F.SUCCESSOR_BLOB_SHA256, publication=F.publication(), health=F.health(),
            unit_credentials=unit_credentials(), credential_inventory=inventory(), inventory_phase=WR.STEADY,
            hold_present=False)
        value.update(overrides)
        return WR.WitnessReadinessInputsV1(**value)


# ----------------------------------------------------- credential observations ---

C = WR.DEV_SYNTHETIC_SLOT_CONTRACT
OTHER_BLOB_SHA256 = hashlib.sha256(b"TEST_ONLY Source Prep A other encrypted credential blob").hexdigest()
PREDECESSOR_BLOB_SHA256 = hashlib.sha256(b"TEST_ONLY Source Prep A predecessor encrypted blob").hexdigest()


def blob(name: str = C.current_slot_name, sha256: str = F.SUCCESSOR_BLOB_SHA256, **overrides: Any
         ) -> WR.CredentialFileObservationV1:
    value = dict(name=name, kind=WR.REGULAR, uid=0, gid=0, mode=0o600, sha256=sha256)
    value.update(overrides)
    return WR.CredentialFileObservationV1(**value)


def location(role: str, *entries: WR.CredentialFileObservationV1, **overrides: Any
             ) -> WR.CredentialLocationObservationV1:
    value = dict(role=role, kind=WR.DIRECTORY, uid=0, gid=0, mode=0o700, entries=tuple(entries))
    value.update(overrides)
    return WR.CredentialLocationObservationV1(**value)


def inventory(*, current: tuple = (None,), prepared: tuple = (), retired: tuple = (),
              extra: tuple = ()) -> WR.CredentialInventoryObservationV1:
    """Default: STEADY, CURRENT = the successor blob; PREPARED/RETIRED absent."""
    current_entries = tuple(blob() if item is None else item for item in current)
    locations = [location(WR.CREDSTORE, *current_entries)]
    locations.append(location(WR.PREPARED, *prepared) if prepared
                     else WR.CredentialLocationObservationV1(WR.PREPARED, WR.ABSENT))
    locations.append(location(WR.RETIRED, *retired) if retired
                     else WR.CredentialLocationObservationV1(WR.RETIRED, WR.ABSENT))
    return WR.CredentialInventoryObservationV1(tuple(locations) + tuple(extra))


def unit_credentials(*references: WR.UnitCredentialReferenceV1, unit: str = C.unit_name
                     ) -> WR.UnitCredentialObservationV1:
    if not references:
        references = (WR.UnitCredentialReferenceV1(WR.LOAD_CREDENTIAL_ENCRYPTED, C.credential_name,
                                                    C.current_slot_path),)
    return WR.UnitCredentialObservationV1(unit, tuple(references))


# ---------------------------------------------------------------- golden ---

def golden_document() -> dict[str, Any]:
    scenario = DurableScenario()
    genesis = dict(scenario.genesis)
    scenario.rotate()
    authorization = next(iter(sorted(scenario.issued)))
    retained = scenario.storage.read(WR.AUTHORIZATION_DIRECTORY, WR.retained_authorization_name(authorization))
    log = [list(item) for item in scenario.storage.log]
    return {
        "note": "TEST_ONLY synthetic vectors for 15B2b-B1b-3e Source Prep A. No real key, witness, or authority.",
        "genesisExpectation": {"registryHead": RC.registry_head(F.v3()).to_dict(),
                               "recoveryEpoch": F.E2.to_dict(), "policyVersion": F.POLICY,
                               "ledgerSequence": F.seeded_ledger().sequence, "ledgerHead": F.seeded_ledger().head},
        "genesisWitness": genesis,
        "genesisWitnessDigest": RC.witness_v2_digest(genesis),
        "genesisPin": scenario.pin,
        "ownerRegister": scenario.register(),
        "retainedAuthorizationName": WR.retained_authorization_name(authorization),
        "retainedAuthorizationSha256": WR.authorization_sha256(retained),
        "chainEntryNames": scenario.storage.names(WR.CHAIN_DIRECTORY),
        "rotationOperationLog": log,
    }


if __name__ == "__main__":
    if sys.argv[1:] != ["--write-golden"]:
        raise SystemExit("usage: synthetic_b1b3e_prep_a.py --write-golden")
    with GOLDEN_PATH.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(golden_document(), indent=2, sort_keys=True) + "\n")
