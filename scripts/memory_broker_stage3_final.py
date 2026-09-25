#!/usr/bin/env python3
"""Dormant, fixed one-shot Stage-III A2 controller; no CLI or workflow entrypoint.

Only a separately reviewed execution dispatch may call execute_once(). The
controller is intentionally synchronous: the existing pidfd liveness guard is
bound to this root process for the entire experimental interval.
"""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import select
import signal
import stat
import subprocess
import time

from scripts import memory_broker_stage2_control as control
from scripts import memory_broker_stage3_adapters as adapters
from scripts import memory_broker_stage3_liveness as liveness
from scripts import memory_broker_stage3_transition as transition


class FinalError(control.Stage2Error):
    pass


FINAL_ATTEMPT = transition.VAULT.with_name(
    ".lilith-memory-broker-stage3-a2-final-attempt.json")


def require(ok: bool, code: str) -> None:
    if not ok:
        raise FinalError(code)


def canonical(value: object) -> bytes:
    return transition.canonical(value)


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def linux_pidfd_available() -> bool:
    return (os.name == "posix" and hasattr(os, "pidfd_open") and
            hasattr(signal, "pidfd_send_signal"))


def process_identity(pid: int, invocation_id: str) -> tuple[dict, str]:
    """Bind systemd's main PID to the exact kernel incarnation and command."""
    require(type(pid) is int and pid > 1 and
            isinstance(invocation_id, str) and
            re.fullmatch(r"[0-9a-f]{32}", invocation_id) is not None,
            "STAGE3_FINAL_PROCESS_INPUT")
    proc = Path("/proc") / str(pid)
    try:
        fields = (proc / "stat").read_text(encoding="ascii").rsplit(") ", 1)[1].split()
        status = (proc / "status").read_text(encoding="ascii").splitlines()
        uid = next(line for line in status if line.startswith("Uid:\t")).split()[1:]
        gid = next(line for line in status if line.startswith("Gid:\t")).split()[1:]
        command = (proc / "cmdline").read_bytes().rstrip(b"\0").split(b"\0")
        boot = Path("/proc/sys/kernel/random/boot_id").read_text(
            encoding="ascii").strip()
        state = fields[0]
        ticks = int(fields[19])
    except (OSError, StopIteration, ValueError, IndexError, UnicodeError) as exc:
        raise FinalError("STAGE3_FINAL_PROCESS_UNOBSERVABLE") from exc
    expected_command = [str(control.ROOT / "current/venv/bin/python").encode(),
                        b"-B", b"-m", b"lilith_memory_broker.server"]
    require(len(fields) > 19 and ticks > 0 and
            re.fullmatch(r"[0-9a-f-]{36}", boot) is not None and
            uid == ["999"] * 4 and gid == ["987"] * 4 and
            command == expected_command and state in ("S", "R", "T"),
            "STAGE3_FINAL_PROCESS_IDENTITY")
    return ({"pid": pid, "bootId": boot, "startTicks": ticks,
             "invocationId": invocation_id, "releaseSha": control.STAGE3_RELEASE},
            state)


def require_only_broker_process(pid: int) -> None:
    """Do not hash or kill while another broker-UID process can touch the fork."""
    observed = set()
    for entry in Path("/proc").iterdir():
        if not entry.name.isdecimal():
            continue
        try:
            status = (entry / "status").read_text(encoding="ascii")
        except (FileNotFoundError, ProcessLookupError):
            continue
        for line in status.splitlines():
            if line.startswith("Uid:\t") and "999" in line.split()[1:]:
                observed.add(int(entry.name))
                break
    require(observed == {pid}, "STAGE3_FINAL_BROKER_UID_PROCESS_SET")


def validate_barrier(message: str, metadata: dict, identity: dict,
                     proposal: dict) -> bytes:
    """Only the candidate's exact journald-stamped canonical A2 line counts."""
    require(isinstance(message, str) and isinstance(metadata, dict) and
            metadata.get("_PID") == str(identity["pid"]) and
            metadata.get("_BOOT_ID") == identity["bootId"].replace("-", "") and
            metadata.get("_SYSTEMD_INVOCATION_ID") == identity["invocationId"] and
            metadata.get("_SYSTEMD_UNIT") == control.SERVICE,
            "STAGE3_FINAL_BARRIER_PROVENANCE")
    try:
        value = json.loads(message)
        moment = datetime.fromisoformat(value["timestamp"].replace("Z", "+00:00"))
        issued = datetime.fromisoformat(
            proposal["arm"]["issuedAt"].replace("Z", "+00:00"))
        expires = datetime.fromisoformat(
            proposal["arm"]["expiresAt"].replace("Z", "+00:00"))
    except (ValueError, TypeError, KeyError, AttributeError) as exc:
        raise FinalError("STAGE3_FINAL_BARRIER_MALFORMED") from exc
    expected = {
        "eventType": "STAGE3_A2_BARRIER_V1",
        "experimentId": control.STAGE3_EXPERIMENT,
        "faultPoint": control.STAGE3_FAULT,
        "brokerPid": identity["pid"],
        "instrumentedReleaseId": control.STAGE3_RELEASE,
        "challengeId": proposal["challenge"]["challengeId"],
        "requestDigest": proposal["challenge"]["requestDigest"],
        "actionDigest": proposal["challenge"]["actionDigest"],
        "timestamp": value.get("timestamp"),
    }
    raw = canonical(value)
    require(value == expected and type(value["brokerPid"]) is int and
            moment.tzinfo is not None and moment.utcoffset().total_seconds() == 0 and
            issued <= moment < expires and
            raw == (message + "\n").encode("ascii"),
            "STAGE3_FINAL_BARRIER_BINDING")
    return raw


def journal_barrier(identity: dict, proposal: dict) -> bytes | None:
    args = ["/usr/bin/journalctl", "--no-pager", "--output=json",
            "_SYSTEMD_INVOCATION_ID=" + identity["invocationId"],
            "_PID=" + str(identity["pid"]),
            "_SYSTEMD_UNIT=" + control.SERVICE]
    result = subprocess.run(args, check=True, capture_output=True, timeout=5,
                            env={"PATH": "/usr/sbin:/usr/bin:/sbin:/bin",
                                 "LANG": "C", "HOME": "/nonexistent"})
    require(len(result.stdout) <= 64 * 1024 and len(result.stderr) == 0,
            "STAGE3_FINAL_JOURNAL_BOUNDS")
    events = []
    for line in result.stdout.splitlines():
        try:
            entry = json.loads(line)
            message = entry.get("MESSAGE")
            value = json.loads(message) if isinstance(message, str) else None
        except (ValueError, TypeError, UnicodeError):
            continue
        if isinstance(value, dict) and value.get("eventType") == "STAGE3_A2_BARRIER_V1":
            events.append(validate_barrier(message, entry, identity, proposal))
    require(len(events) <= 1, "STAGE3_FINAL_MULTIPLE_BARRIERS")
    return events[0] if events else None


class FinalController:
    """One process, one V2 authorization, one stopped PID and one restoration."""

    def __init__(self):
        self.paths = transition.Paths()
        self.transition = transition.TransitionController(self.paths)
        self._entered = False

    def _claim_attempt(self) -> None:
        require(not os.path.lexists(self.paths.vault) and
                not os.path.lexists(FINAL_ATTEMPT),
                "STAGE3_FINAL_PRIOR_ATTEMPT")
        parent = FINAL_ATTEMPT.parent.lstat()
        require(stat.S_ISDIR(parent.st_mode) and parent.st_uid == 0 and
                parent.st_gid == 0 and not parent.st_mode & 0o022,
                "STAGE3_FINAL_ATTEMPT_PARENT")
        transition.exclusive(FINAL_ATTEMPT, canonical({
            "schema": "Stage3A2FinalAttemptV1", "reviewedBaseSha":
            "d3d9ba3d57ad3dc69069be1ed3347b81f991cd3a",
            "candidateRelease": control.STAGE3_RELEASE,
            "acceptedSnapshotSha256": control.STAGE3_ACCEPTED_SNAPSHOT_SHA}))

    def _arm(self, proposal: dict) -> None:
        parent = control.STAGE3_ARM.parent
        require(not os.path.lexists(control.STAGE3_ARM),
                "STAGE3_FINAL_ARM_COLLISION")
        base = parent.parent.lstat()
        require(stat.S_ISDIR(base.st_mode) and base.st_uid == 0 and
                base.st_gid == 0 and not base.st_mode & 0o022,
                "STAGE3_FINAL_ARM_PARENT")
        if not os.path.lexists(parent):
            parent.mkdir(mode=0o750)
            os.chown(parent, 0, 987)
            os.chmod(parent, 0o750)
            transition.fsync_dir(parent.parent)
        info = parent.lstat()
        require(stat.S_ISDIR(info.st_mode) and
                (info.st_uid, info.st_gid, stat.S_IMODE(info.st_mode)) ==
                    (0, 987, 0o750) and not any(parent.iterdir()),
                "STAGE3_FINAL_ARM_DIRECTORY")
        raw = json.dumps(proposal["arm"], sort_keys=True, separators=(",", ":"),
                         ensure_ascii=False).encode("utf-8")
        require(len(raw) <= 4096 and sha(raw) == proposal["armSha256"],
                "STAGE3_FINAL_ARM_BYTES")
        transition.exclusive(control.STAGE3_ARM, raw, mode=0o640, uid=0, gid=987)
        require(transition.regular(control.STAGE3_ARM, uid=0, gid=987,
                                   mode=0o640) == raw,
                "STAGE3_FINAL_ARM_WRITE")
        transition.exclusive(self.paths.vault / "a2-arm-written.json", canonical({
            "schema": "Stage3A2ArmWriteV1", "armSha256": sha(raw),
            "challengeId": proposal["challenge"]["challengeId"]}))

    def _disarm(self, proposal: dict) -> None:
        raw = transition.regular(control.STAGE3_ARM, uid=0, gid=987, mode=0o640)
        require(sha(raw) == proposal["armSha256"], "STAGE3_FINAL_ARM_DRIFT")
        control.STAGE3_ARM.unlink()
        transition.fsync_dir(control.STAGE3_ARM.parent)
        require(not os.path.lexists(control.STAGE3_ARM),
                "STAGE3_FINAL_ARM_REMAINS")

    def _observe_stopped(self, pidfd: int, identity: dict, proposal: dict,
                         session: adapters.Session) -> tuple[bytes, str]:
        deadline = time.monotonic() + 15
        polling = select.poll()
        polling.register(pidfd, select.POLLIN)
        while time.monotonic() < deadline:
            require(not polling.poll(0), "STAGE3_FINAL_PROCESS_EXITED_BEFORE_BARRIER")
            observed = control.show(control.SERVICE, "InvocationID", "MainPID",
                                    "NRestarts", "ActiveState")
            require(observed == {"InvocationID": identity["invocationId"],
                                 "MainPID": str(identity["pid"]),
                                 "NRestarts": "0", "ActiveState": "active"},
                    "STAGE3_FINAL_BARRIER_SERVICE_DRIFT")
            current, state = process_identity(identity["pid"], identity["invocationId"])
            require(current == identity, "STAGE3_FINAL_BARRIER_PROCESS_DRIFT")
            event = journal_barrier(identity, proposal)
            if state == "T" and event is not None:
                require_only_broker_process(identity["pid"])
                session._db_state("CONSUMED")
                wal = self.paths.active("owner") / transition.OWNER_FILES[1]
                wal_raw = transition.regular(wal, uid=999, gid=987, mode=0o600)
                require(0 < len(wal_raw) <= 32 * 1024 * 1024,
                        "STAGE3_FINAL_STOPPED_WAL_BOUNDS")
                transition.tree_fingerprints(self.paths, experimental=True)
                transition.exclusive(self.paths.vault / "a2-barrier.json", event)
                return event, sha(wal_raw)
            time.sleep(0.1)
        raise FinalError("STAGE3_FINAL_BARRIER_TIMEOUT")

    def _kill_exact(self, pidfd: int, identity: dict, proposal: dict) -> None:
        require(not os.path.lexists(control.STAGE3_ARM),
                "STAGE3_FINAL_KILL_ARM_PRESENT")
        observed, state = process_identity(identity["pid"], identity["invocationId"])
        require(observed == identity and state == "T" and
                journal_barrier(identity, proposal) is not None,
                "STAGE3_FINAL_KILL_TARGET_DRIFT")
        require_only_broker_process(identity["pid"])
        polling = select.poll()
        polling.register(pidfd, select.POLLIN)
        require(not polling.poll(0), "STAGE3_FINAL_KILL_TARGET_EXITED")
        transition.exclusive(self.paths.vault / "a2-kill-attempt.json", canonical({
            "schema": "Stage3A2KillAttemptV1", "process": identity,
            "signal": "SIGKILL"}))
        signal.pidfd_send_signal(pidfd, signal.SIGKILL, None, 0)
        events = polling.poll(10000)
        require(len(events) == 1 and events[0][0] == pidfd and
                events[0][1] & select.POLLIN,
                "STAGE3_FINAL_KILL_UNOBSERVED")
        transition.exclusive(self.paths.vault / "a2-kill-observed.json", canonical({
            "schema": "Stage3A2KillObservedV1", "process": identity}))

    def _restart(self, identity: dict, session: adapters.Session) -> dict:
        deadline = time.monotonic() + 25
        while time.monotonic() < deadline:
            service = control.show(control.SERVICE, "InvocationID", "MainPID",
                                   "NRestarts", "ActiveState")
            require((service.get("NRestarts") == "0" and
                     service.get("InvocationID") in
                         (identity["invocationId"], "")) or
                    (service.get("NRestarts") == "1" and
                     service.get("InvocationID") != identity["invocationId"]),
                    "STAGE3_FINAL_RESTART_DRIFT")
            if (service.get("NRestarts") == "1" and
                    service.get("ActiveState") == "active" and
                    service.get("InvocationID") != identity["invocationId"]):
                candidate = transition.active(expected_restarts="1")
                restarted_identity, restarted_state = process_identity(
                    candidate["pid"], candidate["invocationId"])
                require(candidate["invocationId"] == service["InvocationID"] and
                        candidate["pid"] != identity["pid"] and
                        restarted_identity["invocationId"] ==
                            candidate["invocationId"] and
                        restarted_state in ("S", "R") and
                        not os.path.lexists(control.STAGE3_ARM) and
                        control.relay("health").get("status") == "HEALTH_OK",
                        "STAGE3_FINAL_RESTART_UNACCEPTED")
                control.stage3_verify_candidate_release(selected=True)
                intent = json.loads(transition.regular(
                    self.paths.vault / "000-INTENT.json", uid=0, gid=0,
                    mode=0o600))["record"]
                liveness.verify(self.transition.guard, intent["authorizationId"])
                session._db_state("CONSUMED")
                return candidate
            time.sleep(0.2)
        raise FinalError("STAGE3_FINAL_RESTART_TIMEOUT")

    def _contain_if_needed(self) -> None:
        if os.path.lexists(self.paths.vault):
            try:
                phase = self.transition.journal.last()[0]
            except BaseException:
                # contain_failure closes the OS gate and stops both units
                # before attempting its journal append, even if the journal
                # itself is unreadable.
                transition.contain_failure(self.transition.journal,
                                           self.transition.guard,
                                           "FINAL_JOURNAL_UNCERTAIN")
                raise
            if phase not in ("FAILED_INERT", "RESTORED"):
                transition.contain_failure(self.transition.journal,
                                           self.transition.guard,
                                           "FINAL_CONTROLLER_REVIEW_REQUIRED")

    def execute_once(self) -> dict:
        """Dormant composition only; no CLI, workflow, or dispatch registration."""
        require(not self._entered, "STAGE3_FINAL_ALREADY_ENTERED")
        self._entered = True
        pidfd = None
        try:
            require(linux_pidfd_available(),
                    "STAGE3_FINAL_LINUX_PIDFD_REQUIRED")
            control.assert_host()
            self._claim_attempt()
            issued = control.stage3_issue_authorization()
            activated = self.transition.activate()
            require(activated["candidateRelease"] == control.STAGE3_RELEASE and
                    activated["profile"] == transition.PROFILE_ACTIVE,
                    "STAGE3_FINAL_ACTIVATION")
            proposal = control.stage3_prepare_package()
            require(proposal["authorizationId"] == issued["authorizationId"],
                    "STAGE3_FINAL_AUTHORIZATION_DRIFT")
            session = adapters.Session(proposal)
            self._arm(proposal)
            candidate = transition.active(expected_restarts="0")
            require(candidate["invocationId"] == activated["invocationId"],
                    "STAGE3_FINAL_INITIAL_INVOCATION")
            identity, _state = process_identity(candidate["pid"],
                                                candidate["invocationId"])
            pidfd = os.pidfd_open(identity["pid"], 0)
            session.submit_initial_once()
            event, wal_sha = self._observe_stopped(pidfd, identity,
                                                    proposal, session)
            self._disarm(proposal)
            self._kill_exact(pidfd, identity, proposal)
            restarted = self._restart(identity, session)
            recovered = session.recover_once()
            require(recovered == {"status": "PROOF_BURNED_NO_CLAIM",
                                  "challengeId": identity_challenge(proposal)},
                    "STAGE3_FINAL_RECOVERY_RESULT")
            replay = session.replay_exact_once()
            restarted_identity, restarted_state = process_identity(
                restarted["pid"], restarted["invocationId"])
            require(replay == {"status": "NO_RESPONSE",
                               "frameSha256": session.frame_sha256} and
                    restarted_identity["invocationId"] == restarted["invocationId"] and
                    restarted_state in ("S", "R") and
                    journal_barrier(identity, proposal) == event and
                    journal_barrier(restarted_identity, proposal) is None,
                    "STAGE3_FINAL_REPLAY_RESULT")
            completed = {
                "schema": "Stage3A2CompletedEvidenceV1",
                "candidateRelease": control.STAGE3_RELEASE,
                "challengeId": identity_challenge(proposal),
                "requestDigest": proposal["challenge"]["requestDigest"],
                "actionDigest": proposal["challenge"]["actionDigest"],
                "barrierEventSha256": sha(event),
                "stoppedProcessIdentity": identity,
                "killedProcessIdentity": identity,
                "restartedInvocationId": restarted["invocationId"],
                "recoveryOutcome": "PROOF_BURNED_NO_CLAIM",
                "replayOutcome": "REJECTED_BEFORE_CLAIM",
                "stoppedWalSha256": wal_sha,
            }
            self.transition.seal_evidence(completed)
            restored = self.transition.restore()
            require(restored["profile"] == transition.PROFILE_RESTORED and
                    self.transition.journal.last()[0] == "RESTORED",
                    "STAGE3_FINAL_RESTORED_STATE")
            report = {"schema": "Stage3A2FinalReportV1",
                      "status": "RESTORED", "candidateRelease": control.STAGE3_RELEASE,
                      "authorizationId": issued["authorizationId"],
                      "challengeId": identity_challenge(proposal),
                      "frameSha256": session.frame_sha256,
                      "completedEvidenceSha256": sha(canonical(completed)),
                      "restoredInvocationId": restored["invocationId"]}
            transition.exclusive(self.paths.vault / "final-report.json",
                                 canonical(report))
            return report
        except BaseException:
            self._contain_if_needed()
            raise
        finally:
            if pidfd is not None:
                os.close(pidfd)


def identity_challenge(proposal: dict) -> str:
    return proposal["challenge"]["challengeId"]
