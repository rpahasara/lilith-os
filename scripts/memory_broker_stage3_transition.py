#!/usr/bin/env python3
"""Dormant Stage-III A2 release/state transition; not a dispatch entrypoint.

The final one-shot experiment controller must explicitly call this module after
issuing its closed V2 authorization. Nothing here is registered as a CLI action
or in CI/CD. A phase is never resumed automatically after process or host loss.
"""

from __future__ import annotations

from dataclasses import dataclass
from contextlib import closing
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import stat

from scripts import memory_broker_stage2_control as control
from scripts import memory_broker_stage3_liveness as liveness


PROFILE_ACTIVE = "STAGE_III_A_EXPERIMENTAL_V1"
PROFILE_RESTORED = "POST_STAGE_III_A_RESTORED_V1"
VAULT = Path("/var/lib/.lilith-memory-broker-stage3-a2")
OWNER_FILES = ("owner_control.db", "owner_control.db-wal", "owner_control.db-shm")
EVIDENCE_FILES = ("synthetic_evidence.db", "synthetic_evidence.db-wal",
                  "synthetic_evidence.db-shm")
HISTORY = {
    "owner": ("broker_schema_v1", "owner_identity_v1", "owner_access_identity_v1",
              "owner_credential_v1", "owner_proof_challenge_v1", "owner_request_v1",
              "synthetic_claim_v1"),
    "evidence": ("synthetic_evidence_v1",),
}


class TransitionError(control.Stage2Error):
    pass


def require(ok: bool, code: str) -> None:
    if not ok:
        raise TransitionError(code)


def canonical(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":"),
                       ensure_ascii=False) + "\n").encode("utf-8")


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def fsync_dir(path: Path) -> None:
    if os.name == "nt":  # Only the pure contract tests run on Windows.
        return
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def regular(path: Path, *, uid: int | None = None, gid: int | None = None,
            mode: int | None = None) -> bytes:
    info = path.lstat()
    require(stat.S_ISREG(info.st_mode) and info.st_nlink == 1 and
            (uid is None or info.st_uid == uid) and
            (gid is None or info.st_gid == gid) and
            (mode is None or stat.S_IMODE(info.st_mode) == mode),
            "STAGE3_FILE_CUSTODY")
    fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    try:
        opened = os.fstat(fd)
        require((opened.st_dev, opened.st_ino) == (info.st_dev, info.st_ino),
                "STAGE3_FILE_REPLACED")
        with os.fdopen(fd, "rb", closefd=False) as stream:
            raw = stream.read()
        require(len(raw) == opened.st_size, "STAGE3_FILE_SIZE_CHANGED")
        return raw
    finally:
        os.close(fd)


def exclusive(path: Path, raw: bytes, *, mode: int = 0o600,
              uid: int | None = None, gid: int | None = None) -> None:
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL |
                 getattr(os, "O_NOFOLLOW", 0), mode)
    try:
        if uid is not None and gid is not None and os.name != "nt":
            os.fchown(fd, uid, gid)
        os.fchmod(fd, mode) if os.name != "nt" else None
        with os.fdopen(fd, "wb", closefd=False) as stream:
            stream.write(raw)
            stream.flush()
        os.fsync(fd)
    finally:
        os.close(fd)
    fsync_dir(path.parent)


def replace_file(path: Path, raw: bytes, *, mode: int, uid: int, gid: int) -> None:
    temporary = path.with_name(".stage3-a2-" + path.name)
    require(not os.path.lexists(temporary), "STAGE3_TEMP_COLLISION")
    exclusive(temporary, raw, mode=mode, uid=uid, gid=gid)
    os.replace(temporary, path)
    fsync_dir(path.parent)


def replace_selector(path: Path, target: str) -> None:
    require(target in (f"releases/{control.RELEASE}",
                       f"releases/{control.STAGE3_RELEASE}"),
            "STAGE3_SELECTOR_TARGET")
    temporary = path.with_name(".stage3-a2-current")
    require(not os.path.lexists(temporary), "STAGE3_SELECTOR_COLLISION")
    os.symlink(target, temporary)
    os.replace(temporary, path)
    fsync_dir(path.parent)


@dataclass(frozen=True)
class Paths:
    root: Path = control.ROOT
    config: Path = control.CONFIG
    state: Path = control.STATE
    vault: Path = VAULT

    @property
    def current(self) -> Path:
        return self.root / "current"

    @property
    def dev_config(self) -> Path:
        return self.config / "dev.json"

    def active(self, kind: str) -> Path:
        return self.state / ("owner-control" if kind == "owner" else "state")

    def saved(self, kind: str) -> Path:
        return self.vault / ("accepted-owner" if kind == "owner" else "accepted-evidence")

    def fork(self, kind: str) -> Path:
        return self.vault / ("fork-owner" if kind == "owner" else "fork-evidence")

    def experiment(self, kind: str) -> Path:
        return self.vault / ("experiment-owner" if kind == "owner" else "experiment-evidence")


def tree_fingerprints(paths: Paths, *, saved: bool = False,
                      experimental: bool = False, retained: bool = False,
                      fork: bool = False) -> dict:
    require(sum((saved, retained, fork)) <= 1, "STAGE3_TREE_LOCATION")
    result = {}
    for kind, names in (("owner", OWNER_FILES), ("evidence", EVIDENCE_FILES)):
        folder = (paths.saved(kind) if saved else paths.experiment(kind) if retained
                  else paths.fork(kind) if fork else paths.active(kind))
        info = folder.lstat()
        present = {item.name for item in folder.iterdir()}
        allowed = set(names)
        required = {names[0]} if experimental else allowed
        require(stat.S_ISDIR(info.st_mode) and not stat.S_ISLNK(info.st_mode) and
                (info.st_uid, info.st_gid, stat.S_IMODE(info.st_mode)) ==
                (999, 987, 0o700) and
                required <= present <= allowed,
                "STAGE3_STATE_TREE_CUSTODY")
        result[kind] = {name: sha(regular(folder / name, uid=999, gid=987, mode=0o600))
                        for name in names if name in present}
    return result


def bind_accepted_bytes(snapshot: dict, state_hashes: dict,
                        config_sha: str) -> None:
    """Close the gap between trusted snapshot capture and quiescence."""
    observed = snapshot["snapshot"]
    require(config_sha == observed["files"][str(control.CONFIG / "dev.json")]["sha256"] and
            state_hashes["owner"][OWNER_FILES[0]] ==
                observed["files"][str(control.OWNER_DB)]["sha256"] and
            state_hashes["evidence"][EVIDENCE_FILES[0]] ==
                observed["files"][str(control.EVIDENCE_DB)]["sha256"],
            "STAGE3_ACCEPTED_SNAPSHOT_BYTE_DRIFT")
    for kind in ("owner", "evidence"):
        for suffix in ("-wal", "-shm"):
            name = (OWNER_FILES[0] if kind == "owner" else EVIDENCE_FILES[0]) + suffix
            require(state_hashes[kind][name] ==
                    observed["databases"][kind]["sidecars"][suffix]["sha256"],
                    "STAGE3_ACCEPTED_SNAPSHOT_SIDECAR_DRIFT")


def verify_accepted_release(paths: Paths) -> None:
    release = paths.root / "releases" / control.RELEASE
    info = release.lstat()
    require(stat.S_ISDIR(info.st_mode) and
            (info.st_uid, info.st_gid, stat.S_IMODE(info.st_mode)) ==
            (0, 0, 0o755), "STAGE3_ACCEPTED_RELEASE_CUSTODY")
    raw = regular(release / "release-manifest.json", uid=0, gid=0, mode=0o644)
    manifest = json.loads(raw)
    require(sha(raw) == control.MANIFEST_SHA and
            manifest.get("candidateSha") == control.RELEASE and
            isinstance(manifest.get("files"), list) and
            len(manifest["files"]) == 23, "STAGE3_ACCEPTED_RELEASE_IDENTITY")
    seen = set()
    for item in manifest["files"]:
        require(isinstance(item, dict) and
                set(item) == {"path", "byteSize", "sha256"} and
                isinstance(item["path"], str) and
                all(part not in ("", ".", "..") for part in item["path"].split("/")) and
                item["path"] not in seen, "STAGE3_ACCEPTED_PAYLOAD_PATH")
        seen.add(item["path"])
        payload = release
        for part in item["path"].split("/")[:-1]:
            payload = payload / part
            parent = payload.lstat()
            require(stat.S_ISDIR(parent.st_mode) and
                    (parent.st_uid, parent.st_gid, stat.S_IMODE(parent.st_mode)) ==
                    (0, 0, 0o755), "STAGE3_ACCEPTED_PAYLOAD_PARENT")
        data = regular(payload / item["path"].split("/")[-1],
                       uid=0, gid=0, mode=0o644)
        require(len(data) == item["byteSize"] and sha(data) == item["sha256"],
                "STAGE3_ACCEPTED_PAYLOAD_DRIFT")


def copy_state_tree(source: Path, target: Path, names: tuple[str, ...]) -> None:
    """Never move or open the accepted original for writing."""
    require(not os.path.lexists(target), "STAGE3_COPY_COLLISION")
    target.mkdir(mode=0o700)
    if os.name != "nt":
        os.chown(target, 999, 987)
    for name in names:
        exclusive(target / name, regular(source / name, uid=999, gid=987,
                                        mode=0o600), uid=999, gid=987)
    fsync_dir(target)


def row_fingerprints(owner: Path, evidence: Path) -> dict:
    result = {}
    for kind, path in (("owner", owner), ("evidence", evidence)):
        # Only a quiescent private fork or retained experiment is passed here.
        with closing(sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True)) as db:
            require(db.execute("PRAGMA integrity_check").fetchone() == ("ok",) and
                    not db.execute("PRAGMA foreign_key_check").fetchall(),
                    "STAGE3_FORK_DATABASE_INVALID")
            result[kind] = {}
            for table in HISTORY[kind]:
                rows = db.execute(f'SELECT * FROM "{table}" ORDER BY 1').fetchall()
                result[kind][table] = {str(row[0]): control.row_hash(row) for row in rows}
                require(len(result[kind][table]) == len(rows),
                        "STAGE3_FORK_DUPLICATE_ROW")
    return result


def fork_state(paths: Paths, accepted_bytes: dict) -> dict:
    """Copy stopped accepted bytes; change release metadata only in the fork."""
    for kind, names in (("owner", OWNER_FILES), ("evidence", EVIDENCE_FILES)):
        source, target = paths.saved(kind), paths.fork(kind)
        copy_state_tree(source, target, names)
    require(tree_fingerprints(paths, fork=True) == accepted_bytes,
            "STAGE3_FORK_BYTES_CHANGED")
    before = row_fingerprints(paths.fork("owner") / OWNER_FILES[0],
                              paths.fork("evidence") / EVIDENCE_FILES[0])
    database = paths.fork("evidence") / EVIDENCE_FILES[0]
    with closing(sqlite3.connect(database, isolation_level=None)) as db:
        db.execute("PRAGMA synchronous=FULL")
        db.execute("BEGIN IMMEDIATE")
        changed = db.execute(
            "UPDATE synthetic_schema_v1 SET release_sha=? "
            "WHERE profile=? AND release_sha=?",
            (control.STAGE3_RELEASE, "B1B2_SYNTHETIC_EVIDENCE_V1", control.RELEASE))
        require(changed.rowcount == 1, "STAGE3_FORK_RELEASE_BINDING")
        db.commit()
        require(db.execute("PRAGMA integrity_check").fetchone() == ("ok",),
                "STAGE3_FORK_INTEGRITY")
    after = row_fingerprints(paths.fork("owner") / OWNER_FILES[0], database)
    require(after == before, "STAGE3_FORK_HISTORY_CHANGED")
    return {"inheritedRows": before, "forkRows": after,
            "candidateRelease": control.STAGE3_RELEASE}


class Journal:
    def __init__(self, path: Path):
        self.path = path

    def create(self, intent: dict) -> None:
        require(not os.path.lexists(self.path) and
                self.path.parent.is_dir() and
                self.path.parent.stat().st_dev == intent["stateDevice"],
                "STAGE3_VAULT_COLLISION_OR_FILESYSTEM")
        self.path.mkdir(mode=0o700)
        fsync_dir(self.path.parent)
        self.append("INTENT", intent)

    def append(self, phase: str, record: dict) -> None:
        require(phase in {"INTENT", "QUIESCED", "ACCEPTED_VAULTED", "FORK_READY",
            "BINDINGS_SWITCHED", "LIVENESS_BOUND", "CANDIDATE_ACTIVE",
            "EVIDENCE_SEALED",
                          "RESTORE_QUIESCED", "EXPERIMENT_PRESERVED",
                          "ACCEPTED_REBOUND", "RESTORED", "FAILED_INERT"},
                "STAGE3_JOURNAL_PHASE")
        info = self.path.lstat()
        require(stat.S_ISDIR(info.st_mode) and
                (os.name == "nt" or stat.S_IMODE(info.st_mode) == 0o700) and
                (os.name == "nt" or info.st_uid == 0),
                "STAGE3_JOURNAL_CUSTODY")
        names = self._names()
        previous = self.last()[0] if names else None
        permitted = {
            None: ("INTENT",), "INTENT": ("QUIESCED", "FAILED_INERT"),
            "QUIESCED": ("ACCEPTED_VAULTED", "FAILED_INERT"),
            "ACCEPTED_VAULTED": ("FORK_READY", "FAILED_INERT"),
            "FORK_READY": ("BINDINGS_SWITCHED", "FAILED_INERT"),
            "BINDINGS_SWITCHED": ("LIVENESS_BOUND", "FAILED_INERT"),
            "LIVENESS_BOUND": ("CANDIDATE_ACTIVE", "FAILED_INERT"),
            "CANDIDATE_ACTIVE": ("EVIDENCE_SEALED", "FAILED_INERT"),
            "EVIDENCE_SEALED": ("RESTORE_QUIESCED", "FAILED_INERT"),
            "RESTORE_QUIESCED": ("EXPERIMENT_PRESERVED", "FAILED_INERT"),
            "EXPERIMENT_PRESERVED": ("ACCEPTED_REBOUND", "FAILED_INERT"),
            "ACCEPTED_REBOUND": ("RESTORED", "FAILED_INERT"),
            "RESTORED": (), "FAILED_INERT": (),
        }
        require(phase in permitted[previous], "STAGE3_JOURNAL_ILLEGAL_TRANSITION")
        previous_sha = sha(regular(self.path / names[-1])) if names else None
        exclusive(self.path / f"{len(names):03d}-{phase}.json",
                  canonical({"schema": "Stage3A2TransitionJournalV1", "phase": phase,
                             "previousSha256": previous_sha, "record": record}))

    def _names(self) -> list[str]:
        info = self.path.lstat()
        require(stat.S_ISDIR(info.st_mode) and not stat.S_ISLNK(info.st_mode) and
                (os.name == "nt" or
                 (info.st_uid == 0 and stat.S_IMODE(info.st_mode) == 0o700)),
                "STAGE3_JOURNAL_CUSTODY")
        names = sorted(item.name for item in self.path.iterdir()
                       if item.name.endswith(".json") and item.name[:3].isdigit())
        require(len(names) < 20 and all(name.startswith(f"{index:03d}-")
                                        for index, name in enumerate(names)) and
                not any(item.is_symlink() for item in self.path.iterdir()),
                "STAGE3_JOURNAL_SEQUENCE")
        return names

    def last(self) -> tuple[str, dict]:
        names = self._names()
        require(names, "STAGE3_JOURNAL_EMPTY")
        previous_sha = None
        final = None
        for name in names:
            phase = name.split("-", 1)[1][:-5]
            raw = regular(self.path / name, uid=0 if os.name != "nt" else None,
                          mode=0o600 if os.name != "nt" else None)
            value = json.loads(raw)
            require(raw == canonical(value) and
                    value == {"schema": "Stage3A2TransitionJournalV1", "phase": phase,
                              "previousSha256": previous_sha,
                              "record": value.get("record")},
                    "STAGE3_JOURNAL_INVALID")
            previous_sha = sha(raw)
            final = (phase, value["record"])
        return final


def stopped() -> None:
    for name in (control.SOCKET, control.SERVICE):
        if control.show(name, "ActiveState").get("ActiveState") != "inactive":
            control.run_fixed("/usr/bin/systemctl", "stop", name)
    for name, allowed in ((control.SOCKET, {"disabled", "masked-runtime"}),
                          (control.SERVICE, {"static", "masked-runtime"})):
        observed = control.show(name, "ActiveState", "SubState", "MainPID",
                                "UnitFileState")
        require(observed.get("ActiveState") == "inactive" and
                observed.get("MainPID") == "0" and
                observed.get("UnitFileState") in allowed,
                "STAGE3_UNIT_NOT_INERT")
    # No broker-UID process can retain the SQLite stores after service stop.
    if os.name != "nt":
        for entry in Path("/proc").iterdir():
            if entry.name.isdecimal():
                try:
                    status = (entry / "status").read_text(encoding="ascii")
                except (FileNotFoundError, ProcessLookupError):
                    continue
                require(not any(line.startswith("Uid:\t999\t") for line in
                                status.splitlines()), "STAGE3_BROKER_UID_PROCESS_PRESENT")


def active(*, expected_restarts: str = "0") -> dict:
    service, sock = control.assert_unit_state(socket_active=True, service_active=True)
    observed = control.show(control.SERVICE, "InvocationID", "MainPID", "NRestarts")
    require(observed.get("InvocationID") and int(observed.get("MainPID", "0")) > 1 and
            observed.get("NRestarts") == expected_restarts,
            "STAGE3_ACTIVE_INCARNATION")
    return {"invocationId": observed["InvocationID"],
            "pid": int(observed["MainPID"]), "service": service["ActiveState"],
            "socket": sock["ActiveState"]}


def validate_restored_state(intent: dict, observed: dict) -> None:
    """New profile: accepted bytes and authority, but a new broker incarnation.

    The prior POST_STAGE_II_ACCEPTED_V1 profile is intentionally not reused:
    its invocation ID and start time are historical facts, not restart targets.
    """
    require(isinstance(intent, dict) and isinstance(observed, dict) and
            set(observed) == {
                "profile", "acceptedRelease", "candidateRelease", "selector",
                "acceptedSnapshotSha256", "configSha256", "stateHashes",
                "vaultAcceptedHashes", "experimentHashes", "invocationId",
                "previousInvocationId", "apiBaseline", "authorizationId",
                "evidenceSha256", "armAbsent"} and
            observed["profile"] == PROFILE_RESTORED and
            observed["acceptedRelease"] == intent["acceptedRelease"] == control.RELEASE and
            observed["candidateRelease"] == intent["candidateRelease"] ==
                control.STAGE3_RELEASE and
            observed["selector"] == f"releases/{control.RELEASE}" and
            observed["acceptedSnapshotSha256"] == intent["acceptedSnapshotSha256"] ==
                control.STAGE3_ACCEPTED_SNAPSHOT_SHA and
            observed["configSha256"] == intent["configSha256"] and
            observed["stateHashes"] == observed["vaultAcceptedHashes"] ==
                intent["stateHashes"] and
            observed["experimentHashes"] and
            observed["invocationId"] and
            observed["invocationId"] !=
                observed["previousInvocationId"] == intent["acceptedInvocationId"] and
            observed["apiBaseline"] == intent["apiBaseline"] and
            observed["authorizationId"] == intent["authorizationId"] and
            isinstance(observed["evidenceSha256"], str) and
            re.fullmatch(r"[0-9a-f]{64}", observed["evidenceSha256"]) is not None and
            observed["armAbsent"] is True,
            "STAGE3_RESTORED_PROFILE_MISMATCH")


def contain_failure(journal: Journal, guard: liveness.Paths, reason: str) -> None:
    """A containment failure is terminal and must be visible, never swallowed."""
    def stop_guard() -> None:
        if os.path.lexists(guard.guard_unit) and control.show(
                liveness.GUARD, "ActiveState").get("ActiveState") == "active":
            control.run_fixed("/usr/bin/systemctl", "stop", liveness.GUARD)

    failures = []
    for action in (lambda: liveness.close_gate(guard), stop_guard, stopped):
        try:
            action()
        except Exception as exc:
            failures.append(exc)
    if failures:
        raise TransitionError("STAGE3_CONTAINMENT_UNVERIFIED") from failures[0]
    try:
        journal.append("FAILED_INERT", {"reason": reason})
    except Exception as exc:
        raise TransitionError("STAGE3_CONTAINMENT_UNVERIFIED") from exc


class TransitionController:
    def __init__(self, paths: Paths = Paths()):
        self.paths = paths
        self.journal = Journal(paths.vault)
        self.guard = liveness.Paths(vault=paths.vault)

    def activate(self) -> dict:
        """One-shot accepted -> experimental transition; no A2 proof or signal."""
        p = self.paths
        accepted = control.stage3_accepted_snapshot()
        control.stage3_verify_inactive_release()
        verify_accepted_release(p)
        marker = control.stage3_verify_authorization()
        require(not os.path.lexists(p.vault) and
                not os.path.lexists(control.STAGE3_ARM) and
                os.readlink(p.current) == f"releases/{control.RELEASE}",
                "STAGE3_TRANSITION_PRECONDITION")
        before = tree_fingerprints(p)
        config_raw = regular(p.dev_config, uid=0, gid=987, mode=0o640)
        config = json.loads(config_raw)
        require(config.get("releaseSha") == control.RELEASE and
                config.get("authorityMode") == "SYNTHETIC_ONLY" and
                config.get("canonicalCapability") == "DISABLED",
                "STAGE3_ACCEPTED_CONFIG")
        bind_accepted_bytes(accepted, before, sha(config_raw))
        intent = {"acceptedSnapshotSha256": accepted["completeDigestSha256"],
                  "acceptedRelease": control.RELEASE,
                  "candidateRelease": control.STAGE3_RELEASE,
                  "candidateManifestSha256": control.STAGE3_MANIFEST_SHA,
                  "authorizationId": marker["authorizationId"],
                  "configSha256": sha(config_raw), "stateHashes": before,
                  "acceptedInvocationId": accepted["snapshot"]["units"][
                      control.SERVICE]["InvocationID"],
                  "apiBaseline": control.capture_api_runtime_baseline(),
                  "stateDevice": p.state.stat().st_dev}
        self.journal.create(intent)  # Durable one-shot claim before first mutation.
        try:
            stopped()
            original_units = liveness.prepare_inert(self.guard)
            require(tree_fingerprints(p) == before and
                    sha(regular(p.dev_config, uid=0, gid=987, mode=0o640)) ==
                    intent["configSha256"], "STAGE3_QUIESCE_CHANGED_ACCEPTED_BYTES")
            self.journal.append("QUIESCED", {"stateHashes": before,
                                            "originalUnitHashes": original_units})
            exclusive(p.vault / "accepted-dev.json", config_raw)
            for kind in ("owner", "evidence"):
                require(not os.path.lexists(p.saved(kind)), "STAGE3_VAULT_TARGET_COLLISION")
                p.active(kind).rename(p.saved(kind))
                fsync_dir(p.state)
                fsync_dir(p.vault)
            require(tree_fingerprints(p, saved=True) == before,
                    "STAGE3_VAULT_BYTES_CHANGED")
            self.journal.append("ACCEPTED_VAULTED", {"stateHashes": before})
            provenance = fork_state(p, before)
            inherited = provenance["inheritedRows"]
            exclusive(p.vault / "fork-provenance.json", canonical({
                "schema": "Stage3A2ForkProvenanceV1", "accepted": intent,
                **provenance}))
            self.journal.append("FORK_READY", {"provenanceSha256": sha(
                regular(p.vault / "fork-provenance.json"))})
            for kind in ("owner", "evidence"):
                require(not os.path.lexists(p.active(kind)), "STAGE3_ACTIVE_STATE_COLLISION")
                p.fork(kind).rename(p.active(kind))
                fsync_dir(p.state)
                fsync_dir(p.vault)
            new_config = dict(config, releaseSha=control.STAGE3_RELEASE)
            replace_file(p.dev_config, canonical(new_config), mode=0o640, uid=0, gid=987)
            replace_selector(p.current, f"releases/{control.STAGE3_RELEASE}")
            self.journal.append("BINDINGS_SWITCHED", {
                "candidateConfigSha256": sha(canonical(new_config))})
            control.stage3_verify_candidate_release(selected=True)
            require(json.loads(regular(p.dev_config, uid=0, gid=987,
                                       mode=0o640)) == new_config and
                    row_fingerprints(p.active("owner") / OWNER_FILES[0],
                                     p.active("evidence") / EVIDENCE_FILES[0]) ==
                    inherited, "STAGE3_CANDIDATE_BINDING_DRIFT")
            with closing(sqlite3.connect(
                f"file:{(p.active('evidence') / EVIDENCE_FILES[0]).as_posix()}?mode=ro",
                uri=True)) as db:
                require(db.execute("SELECT release_sha FROM synthetic_schema_v1")
                        .fetchall() == [(control.STAGE3_RELEASE,)],
                        "STAGE3_CANDIDATE_EVIDENCE_BINDING")
            require(control.stage3_verify_authorization() == marker,
                    "STAGE3_AUTHORIZATION_EXPIRED_DURING_TRANSITION")
            guard = liveness.install(self.guard, marker["authorizationId"])
            self.journal.append("LIVENESS_BOUND", guard)
            control.run_fixed("/usr/bin/systemctl", "start", control.SOCKET)
            control.run_fixed("/usr/bin/systemctl", "start", control.SERVICE)
            incarnation = active()
            liveness.verify(self.guard, marker["authorizationId"])
            require(control.relay("health").get("status") == "HEALTH_OK",
                    "STAGE3_CANDIDATE_STARTUP_REJECTED")
            require(row_fingerprints(p.active("owner") / OWNER_FILES[0],
                                     p.active("evidence") / EVIDENCE_FILES[0]) ==
                    inherited, "STAGE3_STARTUP_HISTORY_DRIFT")
            control.require_api_baseline_unchanged(intent["apiBaseline"])
            require(incarnation["invocationId"] != intent["acceptedInvocationId"],
                    "STAGE3_CANDIDATE_INVOCATION_NOT_NEW")
            self.journal.append("CANDIDATE_ACTIVE", {
                "profile": PROFILE_ACTIVE, **incarnation})
            return {"profile": PROFILE_ACTIVE, "candidateRelease": control.STAGE3_RELEASE,
                    "invocationId": incarnation["invocationId"]}
        except BaseException:
            contain_failure(self.journal, self.guard, "ACTIVATION_REVIEW_REQUIRED")
            raise

    def seal_evidence(self, evidence: dict) -> None:
        control.assert_host()
        try:
            self._seal_evidence(evidence)
        except BaseException:
            contain_failure(self.journal, self.guard, "EVIDENCE_REVIEW_REQUIRED")
            raise

    def _seal_evidence(self, evidence: dict) -> None:
        """Accept a final-controller record only after independent state checks.

        This does not manufacture barrier, kill, restart, recovery, or replay
        evidence; the future execution controller must supply and verify it.
        """
        phase, candidate_incarnation = self.journal.last()
        require(phase == "CANDIDATE_ACTIVE",
                "STAGE3_EVIDENCE_PHASE")
        require(isinstance(evidence, dict) and set(evidence) == {
            "schema", "candidateRelease", "challengeId", "requestDigest",
            "actionDigest", "barrierEventSha256", "stoppedProcessIdentity",
            "killedProcessIdentity", "restartedInvocationId", "recoveryOutcome",
            "replayOutcome", "stoppedWalSha256"} and
            evidence["schema"] == "Stage3A2CompletedEvidenceV1" and
            evidence["candidateRelease"] == control.STAGE3_RELEASE and
            isinstance(evidence["challengeId"], str) and
            re.fullmatch(r"och\.[0-9a-f]{32}", evidence["challengeId"]) is not None and
            isinstance(evidence["stoppedProcessIdentity"], dict) and
            set(evidence["stoppedProcessIdentity"]) == {
                "pid", "bootId", "startTicks", "invocationId", "releaseSha"} and
            type(evidence["stoppedProcessIdentity"]["pid"]) is int and
            evidence["stoppedProcessIdentity"]["pid"] > 1 and
            type(evidence["stoppedProcessIdentity"]["startTicks"]) is int and
            evidence["stoppedProcessIdentity"]["startTicks"] > 0 and
            evidence["stoppedProcessIdentity"]["releaseSha"] == control.STAGE3_RELEASE and
            evidence["stoppedProcessIdentity"]["invocationId"] ==
                candidate_incarnation["invocationId"] and
            isinstance(evidence["restartedInvocationId"], str) and
            evidence["restartedInvocationId"] !=
                evidence["stoppedProcessIdentity"]["invocationId"] and
            evidence["stoppedProcessIdentity"] == evidence["killedProcessIdentity"] and
            evidence["recoveryOutcome"] == "PROOF_BURNED_NO_CLAIM" and
            evidence["replayOutcome"] == "REJECTED_BEFORE_CLAIM" and
            all(isinstance(evidence[key], str) and len(evidence[key]) == 64 and
                all(ch in "0123456789abcdef" for ch in evidence[key])
                for key in ("requestDigest", "actionDigest", "barrierEventSha256",
                            "stoppedWalSha256")) and
            not os.path.lexists(control.STAGE3_ARM) and
            control.STAGE3_USED.is_file() and not control.STAGE3_MARKER.exists(),
            "STAGE3_EVIDENCE_CONTRACT")
        p = self.paths
        control.assert_unit_state(socket_active=True, service_active=True)
        require(control.show(control.SERVICE, "InvocationID")["InvocationID"] ==
                evidence["restartedInvocationId"],
                "STAGE3_RESTART_IDENTITY_DRIFT")
        control.stage3_verify_candidate_release(selected=True)
        intent = json.loads(regular(p.vault / "000-INTENT.json"))["record"]
        used = json.loads(regular(control.STAGE3_USED, uid=0, gid=0, mode=0o600))
        liveness.verify(self.guard, intent["authorizationId"])
        require(used.get("authorizationId") == intent["authorizationId"] and
                os.readlink(p.current) == f"releases/{control.STAGE3_RELEASE}",
                "STAGE3_EVIDENCE_AUTHORIZATION_OR_SELECTOR")
        inherited = json.loads(regular(p.vault / "fork-provenance.json"))["inheritedRows"]
        current = row_fingerprints(p.active("owner") / OWNER_FILES[0],
                                   p.active("evidence") / EVIDENCE_FILES[0])
        challenge_id = evidence["challengeId"]
        for kind in HISTORY:
            for table in HISTORY[kind]:
                old_rows, new_rows = inherited[kind][table], current[kind][table]
                expected = set(old_rows) | ({challenge_id} if
                    table in ("owner_proof_challenge_v1", "owner_request_v1") else set())
                require(set(new_rows) == expected and
                        all(new_rows[key] == value for key, value in old_rows.items()),
                        "STAGE3_EVIDENCE_HISTORY_DRIFT")
        with closing(sqlite3.connect(
            f"file:{(p.active('owner') / OWNER_FILES[0]).as_posix()}?mode=ro",
            uri=True)) as owner, closing(sqlite3.connect(
            f"file:{(p.active('evidence') / EVIDENCE_FILES[0]).as_posix()}?mode=ro",
            uri=True)) as store:
            challenge = owner.execute(
                "SELECT state,challenge_json FROM owner_proof_challenge_v1 "
                "WHERE challenge_id=?", (challenge_id,)).fetchall()
            request = owner.execute(
                "SELECT request_digest,request_json FROM owner_request_v1 "
                "WHERE challenge_id=?", (challenge_id,)).fetchall()
            claims = owner.execute(
                "SELECT COUNT(*) FROM synthetic_claim_v1 WHERE challenge_id=?",
                (challenge_id,)).fetchone()[0]
            emitted = store.execute(
                "SELECT COUNT(*) FROM synthetic_evidence_v1 WHERE challenge_id=?",
                (challenge_id,)).fetchone()[0]
            release = store.execute("SELECT release_sha FROM synthetic_schema_v1").fetchall()
        require(len(challenge) == len(request) == 1 and
                challenge[0][0] == "CONSUMED" and
                request[0][0] == evidence["requestDigest"] and
                json.loads(bytes(challenge[0][1]))["requestDigest"] ==
                    evidence["requestDigest"] and
                json.loads(bytes(challenge[0][1]))["actionDigest"] ==
                    evidence["actionDigest"] and
                json.loads(bytes(request[0][1]))["actionDigest"] ==
                    evidence["actionDigest"] and
                release == [(control.STAGE3_RELEASE,)] and
                claims == emitted == 0, "STAGE3_A2_DB_DELTA")
        retained = canonical(evidence)
        exclusive(p.vault / "completed-evidence.json", retained)
        self.journal.append("EVIDENCE_SEALED", {"evidenceSha256": sha(retained)})

    def restore(self) -> dict:
        """One-shot experimental -> accepted transition after sealed evidence."""
        p = self.paths
        control.assert_host()
        require(self.journal.last()[0] == "EVIDENCE_SEALED",
                "STAGE3_RESTORE_REQUIRES_EVIDENCE")
        try:
            require(regular(p.vault / "completed-evidence.json"),
                    "STAGE3_RESTORE_REQUIRES_EVIDENCE")
            intent = json.loads(regular(p.vault / "000-INTENT.json"))["record"]
            control.stage3_verify_candidate_release(selected=True)
            require(not os.path.lexists(control.STAGE3_ARM) and
                    not os.path.lexists(control.STAGE3_MARKER) and
                    json.loads(regular(control.STAGE3_USED, uid=0, gid=0,
                                       mode=0o600)).get("authorizationId") ==
                    intent["authorizationId"], "STAGE3_RESTORE_AUTHORITY_NOT_TERMINAL")
            require(tree_fingerprints(p, saved=True) == intent["stateHashes"] and
                    sha(regular(p.vault / "accepted-dev.json")) ==
                    intent["configSha256"] and
                    os.readlink(p.current) == f"releases/{control.STAGE3_RELEASE}",
                    "STAGE3_RESTORE_ACCEPTED_CUSTODY")
            liveness.verify(self.guard, intent["authorizationId"])
            stopped()
            liveness.close_gate(self.guard)
            liveness.require_inert()
            self.journal.append("RESTORE_QUIESCED", {})
            experimental = tree_fingerprints(p, experimental=True)
            for kind in ("owner", "evidence"):
                require(not os.path.lexists(p.experiment(kind)),
                        "STAGE3_EXPERIMENT_VAULT_COLLISION")
                p.active(kind).rename(p.experiment(kind))
                fsync_dir(p.state)
                fsync_dir(p.vault)
            require(tree_fingerprints(p, experimental=True, retained=True) ==
                    experimental, "STAGE3_EXPERIMENT_EVIDENCE_CHANGED")
            self.journal.append("EXPERIMENT_PRESERVED", {"stateHashes": experimental})
            for kind, names in (("owner", OWNER_FILES), ("evidence", EVIDENCE_FILES)):
                require(not os.path.lexists(p.active(kind)),
                        "STAGE3_RESTORE_ACTIVE_COLLISION")
                copy_state_tree(p.saved(kind), p.active(kind), names)
                fsync_dir(p.state)
            replace_file(p.dev_config, regular(p.vault / "accepted-dev.json"),
                         mode=0o640, uid=0, gid=987)
            replace_selector(p.current, f"releases/{control.RELEASE}")
            verify_accepted_release(p)
            require(all(control.digest(path) == expected
                        for path, expected in control.HASHES.items()),
                    "STAGE3_ACCEPTED_CONTROL_FILE_DRIFT")
            require(tree_fingerprints(p) == intent["stateHashes"],
                    "STAGE3_RESTORE_BYTES_CHANGED")
            self.journal.append("ACCEPTED_REBOUND", {"stateHashes": intent["stateHashes"]})
            liveness.release(self.guard, intent["authorizationId"])
            restart_count = control.show(control.SERVICE, "NRestarts")["NRestarts"]
            control.run_fixed("/usr/bin/systemctl", "start", control.SOCKET)
            control.run_fixed("/usr/bin/systemctl", "start", control.SERVICE)
            incarnation = active(expected_restarts=restart_count)
            require(control.relay("health").get("status") == "HEALTH_OK" and
                    tree_fingerprints(p) == intent["stateHashes"] and
                    sha(regular(p.dev_config, uid=0, gid=987, mode=0o640)) ==
                    intent["configSha256"] and
                    incarnation["invocationId"] != intent["acceptedInvocationId"],
                    "STAGE3_RESTORED_STATE_DRIFT")
            control.require_api_baseline_unchanged(intent["apiBaseline"])
            liveness.require_dependencies(self.guard, present=False)
            observed = {
                "profile": PROFILE_RESTORED,
                "acceptedRelease": control.RELEASE,
                "candidateRelease": control.STAGE3_RELEASE,
                "selector": os.readlink(p.current),
                "acceptedSnapshotSha256": intent["acceptedSnapshotSha256"],
                "configSha256": sha(regular(p.dev_config, uid=0, gid=987,
                                             mode=0o640)),
                "stateHashes": tree_fingerprints(p),
                "vaultAcceptedHashes": tree_fingerprints(p, saved=True),
                "experimentHashes": tree_fingerprints(p, experimental=True,
                                                       retained=True),
                "invocationId": incarnation["invocationId"],
                "previousInvocationId": intent["acceptedInvocationId"],
                "apiBaseline": control.capture_api_runtime_baseline(
                    captured_at=intent["apiBaseline"]["capturedAt"]),
                "authorizationId": json.loads(regular(
                    control.STAGE3_USED, uid=0, gid=0, mode=0o600))["authorizationId"],
                "evidenceSha256": sha(regular(p.vault / "completed-evidence.json")),
                "armAbsent": not os.path.lexists(control.STAGE3_ARM),
            }
            validate_restored_state(intent, observed)
            self.journal.append("RESTORED", observed)
            return {"profile": PROFILE_RESTORED,
                    "acceptedRelease": control.RELEASE,
                    "invocationId": incarnation["invocationId"]}
        except BaseException:
            contain_failure(self.journal, self.guard, "RESTORATION_REVIEW_REQUIRED")
            raise
