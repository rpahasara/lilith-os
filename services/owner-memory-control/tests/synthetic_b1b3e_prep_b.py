"""TEST_ONLY fixtures for 15B2b-B1b-3e Source Prep B (successor custody, compromise recovery).

Everything is in-process and runs in the TEST environment `test`, the only
environment the B1b-3e TEST witness writers accept. The keys use the real
DEV_SYNTHETIC keyId forms (`...b1b3d.1` initial, `...b1b3e.<N>` successors)
with TEST_ONLY seeds, so the contracts are exercised on the accepted
identifiers without any real key.

- `PrepBScenario`: a durable TEST witness at V2 genesis over registry v1
  (the initial K-ACT current), an owner pin and register, the TEST authority
  recovery ledger, and drivers for a routine rotation (v1 -> v2), the SW-9
  ladder (marking v1 -> v2, `KEY_COMPROMISE` epoch advance v2 -> v3), and the
  error paths (a mistaken same-epoch successor, a wrong-reason advance, the
  forbidden combined marking + successor).
- custody observations (pure) and `TempCustody`, a real temporary-directory
  custody tree for POSIX tests. It is never pointed at any real custody path.

No real key, credential, witness, registry, ledger, or authority exists.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
import os
import stat
from dataclasses import dataclass, field
from typing import Any

import synthetic_authority as SA
import synthetic_b1b3e as F
import synthetic_b1b3e_prep_a as P
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
from lilith_authority_signer import synthetic_recovery_ledger as RL
from lilith_authority_signer import synthetic_witness_store as WS
from lilith_authority_signer import synthetic_witness_v2 as W2
from lilith_owner_memory import authority_contracts as A
from lilith_owner_memory import recovery_contracts as R
from lilith_owner_memory import rotation_contracts as RC
from lilith_owner_memory import successor_custody as SC
from lilith_owner_memory import successor_readiness as SR
from lilith_owner_memory import witness_readiness as WR

ENV = F.ENV                                    # "test": the TEST writers' only environment
POLICY = "policy.dev-synthetic.v1"
# The TEST fixture binds its own exact expected environment; nothing maps it onto DEV.
PROFILE = SC.custody_profile(ENV)
P0 = SC.INITIAL_KEY_ID                          # test-only.dev-synthetic.actor.b1b3d.1
S2 = SC.successor_identity(2).key_id            # test-only.dev-synthetic.actor.b1b3e.2
S3 = SC.successor_identity(3).key_id
S5 = SC.successor_identity(5).key_id           # only ever published already COMPROMISED
C2 = SC.successor_identity(2).ceremony_id
C3 = SC.successor_identity(3).ceremony_id
INITIAL_CEREMONY = SC.initial_ceremony_id(ENV, P0)
EG = A.RecoveryEpochV1(1, SA._label_hex("TEST_ONLY Prep B genesis epoch 1"))
EN = A.RecoveryEpochV1(2, SA._label_hex("TEST_ONLY Prep B recovery epoch 2"))
RELEASE_SHA = hashlib.sha1(b"TEST_ONLY Prep B reviewed successor-capable release").hexdigest()
OTHER_RELEASE_SHA = hashlib.sha1(b"TEST_ONLY Prep B unreviewed release").hexdigest()
MACHINE_ID = "ae929170e6fa4c8ab9cc7b9547238d9d"

SEEDS = {
    P0: hashlib.sha256(b"TEST_ONLY Prep B initial K-ACT").digest(),
    S2: hashlib.sha256(b"TEST_ONLY Prep B successor 2").digest(),
    S3: hashlib.sha256(b"TEST_ONLY Prep B successor 3").digest(),
    S5: hashlib.sha256(b"TEST_ONLY Prep B successor 5").digest(),
}
BLOB = {key_id: hashlib.sha256(b"TEST_ONLY Prep B encrypted blob " + key_id.encode()).hexdigest()
        for key_id in SEEDS}
OTHER_BLOB = hashlib.sha256(b"TEST_ONLY Prep B unrelated blob").hexdigest()

T0 = "2026-09-26T00:00:00Z"
T_CUT = "2026-09-27T09:00:00Z"
T_MARK = "2026-09-27T09:10:00Z"
T_REC = "2026-09-27T10:00:00Z"


def private(key_id: str) -> Ed25519PrivateKey:
    return Ed25519PrivateKey.from_private_bytes(SEEDS[key_id])


def raw_public(key_id: str) -> bytes:
    return private(key_id).public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)


# ------------------------------------------------------------ registries ---

def key(key_id: str, *, version: int, epoch: A.RecoveryEpochV1 = EG, created: str = T0, **lifecycle: Any
        ) -> dict[str, Any]:
    value = dict(publicKey=SA.b64(raw_public(key_id)), createdAt=created, notBefore=created,
                 recoveryEpoch=epoch.to_dict(), policyVersion=POLICY, registryVersion=version)
    value.update(lifecycle)
    return SA.key_record(key_id, seed_name="actor.current-2", **value)


def registry(version: int, keys: list[dict[str, Any]], *, epoch: A.RecoveryEpochV1 = EG,
             issued: str = "2026-09-27T11:00:00Z") -> dict[str, Any]:
    return SA.registry(keys=sorted(keys, key=lambda k: k["keyId"]), registryVersion=version,
                       recoveryEpoch=epoch.to_dict(), policyVersion=POLICY, issuedAt=issued)


SUPERSEDED = dict(revokedAt=T_CUT, revocationReason="SUPERSEDED")
COMPROMISED = dict(revokedAt=T_MARK, revocationReason="COMPROMISED", compromisedSince=T0)


def g1() -> dict[str, Any]:
    """Genesis registry: the initial K-ACT is the single current key."""
    return registry(1, [key(P0, version=1)], issued="2026-09-26T06:00:00Z")


def rot2() -> dict[str, Any]:
    """Routine rotation: P0 SUPERSEDED, S2 current (same epoch)."""
    return registry(2, [key(P0, version=1, **SUPERSEDED), key(S2, version=2, created=T_CUT)])


def rot3() -> dict[str, Any]:
    """A second routine rotation after rot2: S2 SUPERSEDED, S3 current."""
    return registry(3, [key(P0, version=1, **SUPERSEDED), key(S2, version=2, created=T_CUT, **SUPERSEDED),
                        key(S3, version=3, created=T_CUT)], issued="2026-09-27T11:30:00Z")


def mark2() -> dict[str, Any]:
    """SW-9 step 1: P0 COMPROMISED, no current Actor key."""
    return registry(2, [key(P0, version=1, **COMPROMISED)])


def rec3(*, epoch: A.RecoveryEpochV1 = EN) -> dict[str, Any]:
    """SW-9 step 2 target at the new epoch: S2 current, P0 stays COMPROMISED."""
    return registry(3, [key(P0, version=1, **COMPROMISED), key(S2, version=3, epoch=epoch, created=T_REC)],
                    epoch=epoch, issued="2026-09-27T11:10:00Z")


def mistaken3() -> dict[str, Any]:
    """K-ROOT error: a same-epoch successor registry after the current-key marking."""
    return rec3(epoch=EG)


def combined2() -> dict[str, Any]:
    """RR-22 option B (forbidden): the epoch-advance target marks P0 and names S2."""
    return registry(2, [key(P0, version=1, **COMPROMISED), key(S2, version=2, epoch=EN, created=T_REC)],
                    epoch=EN, issued="2026-09-27T11:10:00Z")


def mark_noncurrent3() -> dict[str, Any]:
    """In-epoch marking of the non-current P0 after rot2 (S2 stays current)."""
    return registry(3, [key(P0, version=1, revokedAt=T_CUT, revocationReason="COMPROMISED", compromisedSince=T0),
                        key(S2, version=2, created=T_CUT)], issued="2026-09-27T11:20:00Z")


# ---------------------------------------------------------- publications ---

def publication(key_id: str, *, credential_path: str | None = None, blob: str | None = None,
                environment: str = ENV, **custody: Any) -> dict[str, Any]:
    """The exact keygen v1 publication shape. P0 -> CURRENT path; successors -> PREPARED."""
    raw = raw_public(key_id)
    path = credential_path or (SC.CURRENT_PATH if key_id == P0 else SC.PREPARED_PATH)
    custody_evidence = {"credentialName": SC.CREDENTIAL_NAME, "credentialPath": path, "withKey": "host",
                        "machineId": MACHINE_ID, "blobByteSize": 128, "blobSha256": blob or BLOB[key_id]}
    custody_evidence.update(custody)
    return {
        "publicationType": RC.KEY_PUBLICATION_TYPE, "schemaVersion": RC.KEY_PUBLICATION_SCHEMA_VERSION,
        "profile": "DEV_SYNTHETIC",
        "publicVerificationMaterial": {
            "keyId": key_id, "signingDomain": A.OWNER_ACTOR, "evidenceTypes": [A.OWNER_MEMORY_OPERATION],
            "environment": environment, "algorithm": "Ed25519", "publicKey": SA.b64(raw),
            "publicKeySha256": hashlib.sha256(raw).hexdigest()},
        "custodyEvidence": custody_evidence,
    }


def publication_bytes(key_id: str, **overrides: Any) -> bytes:
    return SC.canonical_publication_bytes(publication(key_id, **overrides))


def health(key_id: str, **overrides: Any) -> dict[str, Any]:
    value = F.health()
    value["publicKeySha256"] = hashlib.sha256(raw_public(key_id)).hexdigest()
    value.update(overrides)
    return value


def ceremony_record(key_id: str = S2, *, release: str = RELEASE_SHA, **publication_overrides: Any) -> dict[str, Any]:
    return SC.build_successor_ceremony_record(publication_bytes=publication_bytes(key_id, **publication_overrides),
                                              reviewed_release_sha=release, profile=PROFILE)


def ceremony_register(*records: dict[str, Any]) -> dict[str, Any]:
    register = SC.empty_ceremony_register(ENV)
    for item in records:
        result = SC.register_successor_ceremony(register, item, profile=PROFILE)
        assert result.ok, result.reason
        register = result.register
    return register


# ----------------------------------------------------------------- holds ---

def hold(*, kind: str = SC.ROTATION, state: str = SC.HELD, ceremony: str = C2, predecessor: str | None = P0,
         successor: str | None = S2, witness: str, reason: str | None = None) -> dict[str, Any]:
    if reason is None:
        if state == SC.RELEASED:
            reason = SC.OWNER_RELEASE_AFTER_ELIGIBILITY
        elif ceremony.endswith(SC.CUSTODY_DEBT_SUFFIX):
            reason = SC.PREDECESSOR_DESTRUCTION_INCOMPLETE
        else:
            reason = {SC.INITIAL_CUSTODY: SC.INITIAL_CUSTODY_BOOTSTRAP, SC.ROTATION: SC.ROTATION_IN_PROGRESS,
                      SC.KEY_COMPROMISE_RECOVERY: SC.KEY_COMPROMISE_RECOVERY_IN_PROGRESS,
                      SC.REGISTRY_MAINTENANCE: SC.REGISTRY_MAINTENANCE_IN_PROGRESS}[kind]
    return {"protocol": SC.HOLD_PROTOCOL, "schemaVersion": SC.HOLD_SCHEMA_VERSION, "environment": ENV,
            "ceremonyId": ceremony, "transitionKind": kind, "state": state, "reason": reason,
            "expectedPredecessorKeyId": predecessor, "expectedSuccessorKeyId": successor,
            "observedWitnessDigest": witness}


def initial_hold(*, state: str = SC.HELD, witness: str) -> dict[str, Any]:
    return hold(kind=SC.INITIAL_CUSTODY, state=state, ceremony=INITIAL_CEREMONY, predecessor=None, successor=P0,
                witness=witness)


# ------------------------------------------------------------- inventory ---

def slot(sha256: str | None, *, name: str = SC.SLOT_NAME, **overrides: Any) -> WR.CredentialFileObservationV1:
    return P.blob(name, sha256, **overrides)


def inventory(*, current: str | None, prepared: str | None = None, retired: str | None = None,
              extra: dict[str, tuple] | None = None) -> WR.CredentialInventoryObservationV1:
    """All three slot directories present (the custody root is installed)."""
    extra = extra or {}
    entries = {WR.CREDSTORE: current, WR.PREPARED: prepared, WR.RETIRED: retired}
    return WR.CredentialInventoryObservationV1(tuple(
        P.location(role, *(((slot(sha),) if sha else ()) + tuple(extra.get(role, ())))) for role, sha in entries.items()))


def custody(*, current: str | None, prepared: str | None = None, retired: str | None = None,
            devices: dict[str, int | None] | None = None, root: SC.CustodyRootFactsV1 | None = None,
            identity: tuple[int, int] | None = (7, 100), extra: dict[str, tuple] | None = None,
            ) -> SC.CustodyObservationV1:
    return SC.CustodyObservationV1(
        inventory(current=current, prepared=prepared, retired=retired, extra=extra),
        devices if devices is not None else {SC.CURRENT: 7, SC.PREPARED: 7, SC.RETIRED: 7},
        root if root is not None else SC.CustodyRootFactsV1(WR.DIRECTORY, 0, 0, 0o700, SC.CUSTODY_ROOT_NAMES),
        identity if current else None)


def ceremony(predecessor: str = P0, successor: str = S2) -> SC.CustodyCeremonyV1:
    ordinal = SC.successor_ordinal_of_key_id(successor)
    return SC.CustodyCeremonyV1(SC.successor_identity(ordinal).ceremony_id, predecessor, BLOB[predecessor],
                                successor, BLOB[successor])


# -------------------------------------------------------------- scenario ---

def _seeded_ledger() -> RL.AuthorityLedgerStateV1:
    state = RL.AuthorityLedgerStateV1.genesis(environment=ENV, recovery_epoch=EG, policy_version=POLICY,
                                              registry_version=1, signing_key_ids=(P0,))
    lep = R.ledger_epoch_id(EG, ENV)
    state = state.prepare("c1", lep, ready=F.seeded_ready(state))
    state = state.consume("c1", ready=F.seeded_ready(state))
    state = state.issue("c1", "aev.c1", F.digest("prep-b evidence aev.c1"), ready=F.seeded_ready(state))
    return state.prepare("c2", lep, ready=F.seeded_ready(state))


@dataclass
class PrepBScenario:
    """One synthetic authority host: V2 genesis at g1, then a rotation or the SW-9 ladder."""

    storage: Any = field(default_factory=P.SimulatedDurableStorage)
    ledger: Any = field(default_factory=_seeded_ledger)
    ticks: int = 0

    def __post_init__(self) -> None:
        self.issued: dict[str, tuple[str, str]] = {}
        self.registry = g1()
        self.registries: list[dict[str, Any]] = [self.registry]
        self.heads = {RC.registry_head(self.registry)}
        self.pin: dict[str, Any] | None = None
        self.writer = WS.DurableWitnessV2WriterV1(signing_key=F.private("witness"), witness_key_id=F.WITNESS_KEY_ID,
                                                  environment=ENV, storage=self.storage)
        expectation = P.genesis_expectation(self.registry, self.ledger)
        self.genesis = self.writer.bootstrap(expectation=expectation, registry=self.registry,
                                             context=self.context(), updated_at=self.tick())
        self.pin = P.genesis_pin(self.genesis)
        self.digests: dict[str, str] = {"genesis": RC.witness_v2_digest(self.genesis)}

    def tick(self) -> str:
        self.ticks += 1
        return F.stamp(self.ticks)

    def register(self, **overrides: Any) -> dict[str, Any]:
        return P.owner_register(self.issued, self.heads, **overrides)

    def context(self, **overrides: Any) -> WR.WitnessStoreContextV1:
        value = dict(anchor=F.anchor(), environment=ENV, registry_root=F.root(), genesis_pin=self.pin,
                     owner_register=self.register(), authority_public_keys=frozenset())
        value.update(overrides)
        return WR.WitnessStoreContextV1(**value)

    @property
    def head(self) -> RC.RecoveryWitnessV2:
        return RC.RecoveryWitnessV2.from_verified_dict(json.loads(self.storage.read(WS.STATE, WR.POINTER_NAME)))

    def observation(self) -> WR.WitnessStoreObservationV1:
        return WS.observe_witness_store(self.storage)

    def history(self) -> SR.VerifiedHistoryV1:
        history, reason, detail = SR.verify_history(store=self.context(), witness_store=self.observation(),
                                                    head_registries=tuple(self.registries))
        assert history is not None, (reason, detail)
        return history

    # K-ROOT / owner side ---------------------------------------------------
    def issue_head_advance(self, target: dict[str, Any], *, reason: str, authorization_id: str,
                           **overrides: Any) -> dict[str, Any]:
        authorization = F.head_authorization(self.registry, target, reason=reason, recoveryEpoch=self.head
                                             .current_recovery_epoch.to_dict(), authorizationId=authorization_id,
                                             nonce=F.nonce("prep-b " + authorization_id), **overrides)
        key_id, value = P.register_entry(authorization, WR.REGISTRY_HEAD_ADVANCE)
        self.issued[key_id] = value
        self.heads.add(RC.registry_head(target))
        self.registries.append(target)
        return authorization

    def issue_epoch_advance(self, target: dict[str, Any], *, reason: str = SR.KEY_COMPROMISE,
                            authorization_id: str = "eaa.prep-b-recovery-1", **overrides: Any) -> dict[str, Any]:
        authorization = F.epoch_authorization(self.head, target, reason=reason, authorizationId=authorization_id,
                                              successorRecoveryEpoch=target["recoveryEpoch"],
                                              nonce=F.nonce("prep-b " + authorization_id), **overrides)
        key_id, value = P.register_entry(authorization, WR.EPOCH_ADVANCE)
        self.issued[key_id] = value
        self.heads.add(RC.registry_head(target))
        self.registries.append(target)
        return authorization

    # witness side ----------------------------------------------------------
    def publish(self, authorization: dict[str, Any], target: dict[str, Any]) -> dict[str, Any]:
        signed = self.writer.execute_registry_head_advance(
            authorization=authorization, prior_registry=self.registry, target_registry=target,
            context=self.context(), updated_at=self.tick())
        self.registry = target
        return signed

    def record_ledger(self) -> dict[str, Any]:
        return self.writer.record_ledger_advance(ledger_sequence=self.ledger.sequence, ledger_head=self.ledger.head,
                                                 context=self.context(), updated_at=self.tick())

    def activate(self, *key_ids: str) -> dict[str, Any]:
        self.ledger = self.ledger.record_registry(self.registry["registryVersion"], tuple(key_ids), POLICY)
        return self.record_ledger()

    def adopt(self, authorization: dict[str, Any], target: dict[str, Any]) -> None:
        """C-4 step: the signer-owned ledger journals ADVANCE_EPOCH (pre-witness)."""
        self.ledger = W2.adopt_authorized_epoch(self.ledger, authorization=authorization, witness=self.head,
                                                target_registry=target, registry_root=F.root())

    def execute_epoch_advance(self, authorization: dict[str, Any], target: dict[str, Any]) -> dict[str, Any]:
        signed = self.writer.execute_epoch_advance(
            authorization=authorization, prior_registry=self.registry, target_registry=target,
            adoption_record=self.ledger.log[-1], ledger_sequence=self.ledger.sequence,
            ledger_head=self.ledger.head, context=self.context(), updated_at=self.tick())
        self.registry = target
        return signed

    def quarantine(self) -> None:
        quarantined = RL.quarantine_pre_recovery(self.ledger)
        if quarantined.sequence != self.ledger.sequence:
            self.ledger = quarantined
            self.record_ledger()

    # ladders ---------------------------------------------------------------
    def rotate(self) -> PrepBScenario:
        """Routine rotation: the hold is engaged at genesis; v1 -> v2 names S2."""
        self.digests["holdEngaged"] = self.head.digest
        self.publish(self.issue_head_advance(rot2(), reason=SR.SUCCESSOR_ROTATION,
                                             authorization_id="rhaa.prep-b-rotation-1"), rot2())
        self.activate(S2)
        self.digests["successorHead"] = self.head.digest
        return self

    def mark(self) -> PrepBScenario:
        """SW-9 step 1: the separate in-epoch COMPROMISE_MARKING head advance."""
        self.digests["holdEngaged"] = self.head.digest
        self.publish(self.issue_head_advance(mark2(), reason=SR.COMPROMISE_MARKING,
                                             authorization_id="rhaa.prep-b-marking-1"), mark2())
        self.digests["marked"] = self.head.digest
        return self

    def recover(self, *, reason: str = SR.KEY_COMPROMISE, stop_after: str | None = None) -> dict[str, Any]:
        """SW-9 step 2 under C-4: adoption, witness execution, quarantine, witness again."""
        target = rec3()
        authorization = self.issue_epoch_advance(target, reason=reason)
        self.adopt(authorization, target)
        if stop_after == "adoption":
            return authorization
        self.execute_epoch_advance(authorization, target)
        if stop_after == "execution":
            return authorization
        self.quarantine()
        self.digests["successorHead"] = self.head.digest
        return authorization

    # readiness -------------------------------------------------------------
    def readiness_inputs(self, *, key_id: str = S2, hold_value: dict[str, Any] | None = None,
                         holds: tuple[dict[str, Any], ...] | None = None, store_value: Any = "default",
                         phase: str = WR.CUTOVER_INSTALLED, inventory_value: Any = None,
                         record: dict[str, Any] | None | str = "default", register: Any = "default",
                         release: str | None = RELEASE_SHA, pub: bytes | None = None,
                         health_value: dict[str, Any] | None = None, blob: str | None = None,
                         **base: Any) -> SR.SuccessorReadinessInputsV1:
        pub = pub if pub is not None else publication_bytes(key_id)
        if inventory_value is None:
            inventory_value = inventory(current=BLOB[key_id], retired=BLOB[P0]) if phase == WR.CUTOVER_INSTALLED \
                else inventory(current=BLOB[key_id])
        if record == "default":
            record = None if key_id == P0 else ceremony_record(key_id)
        if register == "default":
            register = ceremony_register() if record is None else ceremony_register(record)
        value = dict(environment=ENV, signing_domain=A.OWNER_ACTOR, evidence_type=A.OWNER_MEMORY_OPERATION,
                     store=self.context(), witness_store=self.observation(), head_registries=tuple(self.registries),
                     ledger_observation=W2.observe_authority_recovery_ledger(self.ledger),
                     observed_blob_sha256=blob or BLOB[key_id], publication=json.loads(pub),
                     health=health(key_id) if health_value is None else health_value,
                     unit_credentials=P.unit_credentials(),
                     credential_inventory=inventory_value, inventory_phase=phase, hold_present=False)
        value.update(base)
        if holds is None:
            holds = () if hold_value is None else (hold_value,)
        if store_value == "default":
            store_value = SC.hold_store(*holds)
        return SR.SuccessorReadinessInputsV1(WR.WitnessReadinessInputsV1(**value), store_value, pub, record,
                                             release,
                                             register, PROFILE)

    def readiness(self, mode: str, **overrides: Any) -> SR.SuccessorReadinessResultV1:
        return SR.evaluate_successor_readiness(self.readiness_inputs(**overrides), mode=mode)

    def gate(self, operation: Any, hold_value: dict[str, Any] | None, **overrides: Any) -> SR.RecoveryGateResultV1:
        value = dict(operation=operation, hold=hold_value, store=self.context(), witness_store=self.observation(),
                     head_registries=tuple(self.registries), profile=PROFILE)
        value.update(overrides)
        return SR.evaluate_recovery_gate(**value)


def rotated() -> PrepBScenario:
    return PrepBScenario().rotate()


def recovered() -> PrepBScenario:
    scenario = PrepBScenario().mark()
    scenario.recover()
    return scenario


# -------------------------------------------------- real temporary custody ---

class TempCustody:
    """A real custody tree in a temporary directory (POSIX only). TEST only.

    Layout mirrors RR-26 under `root`: `etc/credstore.encrypted`,
    `etc/lilith-authority-custody/{prepared,retired}`. The test user stands in
    for root: an observed owner equal to the test uid/gid is reported as 0.
    """

    def __init__(self, root: str):
        self.root = root
        self.log: list[tuple[str, ...]] = []
        for relative in ("etc/credstore.encrypted", "etc/lilith-authority-custody",
                         "etc/lilith-authority-custody/prepared", "etc/lilith-authority-custody/retired"):
            path = os.path.join(root, relative)
            os.makedirs(path, exist_ok=True)
            os.chmod(path, 0o700)

    def path(self, absolute: str) -> str:
        return os.path.join(self.root, absolute.lstrip("/"))

    def write(self, absolute: str, data: bytes) -> None:
        fd = os.open(self.path(absolute), os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        try:
            os.write(fd, data)
            os.fsync(fd)
        finally:
            os.close(fd)

    def _fsync_dir(self, absolute: str) -> None:
        fd = os.open(self.path(absolute), os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
        self.log.append(("fsync_dir", absolute))

    def execute(self, plan: SC.CustodyStepPlanV1) -> None:
        """Perform exactly the one rename / unlink a PLANNED step names."""
        assert plan.planned, plan.reason
        if plan.operation[0] == "RENAME":
            _, source, target = plan.operation
            with open(self.path(source), "rb") as handle:
                assert hashlib.sha256(handle.read()).hexdigest() == plan.expected_sha256
            assert not os.path.lexists(self.path(target))
            os.rename(self.path(source), self.path(target))
            self.log.append(("rename", source, target))
            for directory in {os.path.dirname(source), os.path.dirname(target)}:
                self._fsync_dir(directory)
        else:
            _, target = plan.operation
            os.unlink(self.path(target))
            self.log.append(("unlink", target))
            self._fsync_dir(os.path.dirname(target))

    def _owner(self, value: int, mine: int) -> int:
        return 0 if value == mine else value

    def _file(self, path: str) -> WR.CredentialFileObservationV1:
        meta = os.lstat(path)
        kind = WR.SYMLINK if stat.S_ISLNK(meta.st_mode) else WR.REGULAR if stat.S_ISREG(meta.st_mode) else WR.OTHER
        sha = None
        if kind == WR.REGULAR:
            with open(path, "rb") as handle:
                sha = hashlib.sha256(handle.read()).hexdigest()
        return WR.CredentialFileObservationV1(os.path.basename(path), kind, self._owner(meta.st_uid, os.getuid()),
                                              self._owner(meta.st_gid, os.getgid()), stat.S_IMODE(meta.st_mode), sha)

    def _location(self, role: str, absolute: str) -> tuple[WR.CredentialLocationObservationV1, int | None]:
        path = self.path(absolute)
        try:
            meta = os.lstat(path)
        except FileNotFoundError:
            return WR.CredentialLocationObservationV1(role, WR.ABSENT), None
        if not stat.S_ISDIR(meta.st_mode):
            return WR.CredentialLocationObservationV1(role, WR.OTHER), None
        entries = tuple(self._file(os.path.join(path, name)) for name in sorted(os.listdir(path)))
        return WR.CredentialLocationObservationV1(role, WR.DIRECTORY, self._owner(meta.st_uid, os.getuid()),
                                                  self._owner(meta.st_gid, os.getgid()), stat.S_IMODE(meta.st_mode),
                                                  entries), meta.st_dev

    def observe(self) -> SC.CustodyObservationV1:
        locations, devices = [], {}
        for role, logical, absolute in ((WR.CREDSTORE, SC.CURRENT, SC.CREDSTORE_DIR),
                                        (WR.PREPARED, SC.PREPARED, SC.PREPARED_DIR),
                                        (WR.RETIRED, SC.RETIRED, SC.RETIRED_DIR)):
            location, device = self._location(role, absolute)
            locations.append(location)
            devices[logical] = device
        root = self.path(SC.CUSTODY_ROOT)
        meta = os.lstat(root)
        root_facts = SC.CustodyRootFactsV1(WR.DIRECTORY if stat.S_ISDIR(meta.st_mode) else WR.OTHER,
                                           self._owner(meta.st_uid, os.getuid()), self._owner(meta.st_gid, os.getgid()),
                                           stat.S_IMODE(meta.st_mode), tuple(sorted(os.listdir(root))))
        current = self.path(SC.CURRENT_PATH)
        identity = None
        if os.path.lexists(current):
            info = os.lstat(current)
            identity = (info.st_dev, info.st_ino)
        return SC.CustodyObservationV1(WR.CredentialInventoryObservationV1(tuple(locations)), devices, root_facts,
                                       identity)
