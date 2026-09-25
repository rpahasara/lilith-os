"""Synthetic source contracts only; no DEV identity, service, proof or signal."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import select
import signal
import stat
import subprocess
import sys
import time
import unittest
from unittest.mock import Mock, patch

from scripts import memory_broker_stage2_control as control
from scripts import memory_broker_stage3_final as final
from scripts import memory_broker_stage3_transition as transition


ISSUED = datetime(2026, 9, 25, 10, 0, tzinfo=timezone.utc)
CHALLENGE = "och." + "b" * 32
INVOCATION = "a" * 32
RESTARTED = "c" * 32
IDENTITY = {"pid": 42001, "bootId": "24d1771d-e1b5-4e5f-816d-da08ad8b367a",
            "startTicks": 1000, "invocationId": INVOCATION,
            "releaseSha": control.STAGE3_RELEASE}


def proposal() -> dict:
    return {"authorizationId": "d" * 32,
            "challenge": {"challengeId": CHALLENGE,
                          "requestDigest": "e" * 64,
                          "actionDigest": "f" * 64},
            "arm": {"issuedAt": ISSUED.isoformat(timespec="seconds").replace(
                        "+00:00", "Z"),
                    "expiresAt": (ISSUED + timedelta(seconds=30)).isoformat(
                        timespec="seconds").replace("+00:00", "Z")},
            "armSha256": "0" * 64}


def event() -> dict:
    return {"eventType": "STAGE3_A2_BARRIER_V1",
            "experimentId": control.STAGE3_EXPERIMENT,
            "faultPoint": control.STAGE3_FAULT,
            "brokerPid": IDENTITY["pid"],
            "instrumentedReleaseId": control.STAGE3_RELEASE,
            "challengeId": CHALLENGE,
            "requestDigest": "e" * 64,
            "actionDigest": "f" * 64,
            "timestamp": (ISSUED + timedelta(seconds=2)).isoformat(
                timespec="seconds").replace("+00:00", "Z")}


def metadata(message: str) -> dict:
    return {"MESSAGE": message, "_PID": str(IDENTITY["pid"]),
            "_BOOT_ID": IDENTITY["bootId"].replace("-", ""),
            "_SYSTEMD_INVOCATION_ID": INVOCATION,
            "_SYSTEMD_UNIT": control.SERVICE}


class FinalControllerContracts(unittest.TestCase):
    @unittest.skipUnless(sys.platform.startswith("linux") and
                         hasattr(os, "pidfd_open") and
                         hasattr(signal, "pidfd_send_signal"),
                         "isolated Linux pidfd fixture required")
    def test_kernel_pidfd_kills_only_stopped_synthetic_child(self):
        child = subprocess.Popen([sys.executable, "-c",
            "import os,signal; os.kill(os.getpid(),signal.SIGSTOP)"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        descriptor = None
        try:
            descriptor = os.pidfd_open(child.pid, 0)
            deadline = time.monotonic() + 5
            state = None
            while time.monotonic() < deadline:
                raw = (Path("/proc") / str(child.pid) / "stat").read_text(
                    encoding="ascii")
                state = raw.rsplit(") ", 1)[1].split()[0]
                if state == "T":
                    break
                time.sleep(0.01)
            self.assertEqual(state, "T")
            polling = select.poll()
            polling.register(descriptor, select.POLLIN)
            self.assertFalse(polling.poll(0))
            signal.pidfd_send_signal(descriptor, signal.SIGKILL, None, 0)
            self.assertTrue(any(mask & select.POLLIN
                                for _fd, mask in polling.poll(5000)))
            self.assertEqual(child.wait(timeout=5), -signal.SIGKILL)
        finally:
            if child.poll() is None:
                child.kill()
                child.wait(timeout=5)
            if descriptor is not None:
                os.close(descriptor)

    def test_durable_attempt_precedes_authorization_and_denies_collision(self):
        controller = final.FinalController()
        parent = Mock(st_mode=stat.S_IFDIR | 0o755, st_uid=0, st_gid=0)
        with patch.object(final.os.path, "lexists", return_value=False), \
             patch.object(final.Path, "lstat", return_value=parent), \
             patch.object(transition, "exclusive") as write:
            controller._claim_attempt()
        self.assertEqual(write.call_args.args[0], final.FINAL_ATTEMPT)
        self.assertEqual(json.loads(write.call_args.args[1])["schema"],
                         "Stage3A2FinalAttemptV1")
        with patch.object(final.os.path, "lexists", return_value=True):
            with self.assertRaisesRegex(final.FinalError, "PRIOR_ATTEMPT"):
                controller._claim_attempt()

    def test_barrier_requires_canonical_exact_candidate_and_journal_provenance(self):
        message = final.canonical(event()).decode().rstrip("\n")
        self.assertEqual(final.validate_barrier(message, metadata(message),
                                                IDENTITY, proposal()),
                         final.canonical(event()))
        altered = {**event(), "challengeId": "och." + "c" * 32}
        with self.assertRaisesRegex(final.FinalError, "BARRIER_BINDING"):
            final.validate_barrier(final.canonical(altered).decode().strip(),
                                   metadata(message), IDENTITY, proposal())
        with self.assertRaisesRegex(final.FinalError, "BARRIER_PROVENANCE"):
            final.validate_barrier(message, {**metadata(message),
                                             "_PID": "42002"},
                                   IDENTITY, proposal())
        with self.assertRaisesRegex(final.FinalError, "BARRIER_BINDING"):
            final.validate_barrier(json.dumps(event()), metadata(message),
                                   IDENTITY, proposal())

    def test_journal_reader_admits_one_exact_event_only(self):
        message = final.canonical(event()).decode().strip()
        fake = subprocess.CompletedProcess([], 0,
                                           (json.dumps(metadata(message)) + "\n").encode(),
                                           b"")
        with patch.object(final.subprocess, "run", return_value=fake) as run:
            self.assertEqual(final.journal_barrier(IDENTITY, proposal()),
                             final.canonical(event()))
        args = run.call_args.args[0]
        self.assertEqual(args[0], "/usr/bin/journalctl")
        self.assertIn("_SYSTEMD_INVOCATION_ID=" + INVOCATION, args)
        self.assertIn("_PID=42001", args)
        self.assertIn("_SYSTEMD_UNIT=" + control.SERVICE, args)
        duplicate = subprocess.CompletedProcess([], 0, fake.stdout * 2, b"")
        with patch.object(final.subprocess, "run", return_value=duplicate):
            with self.assertRaisesRegex(final.FinalError, "MULTIPLE_BARRIERS"):
                final.journal_barrier(IDENTITY, proposal())

    def test_pidfd_kill_is_exact_and_attempt_is_durable_before_signal(self):
        controller = final.FinalController()
        recorded = []
        poller = Mock()
        poller.poll.side_effect = [[], [(21, 1)]]
        with patch.object(final, "process_identity", return_value=(IDENTITY, "T")), \
             patch.object(final, "require_only_broker_process"), \
             patch.object(final, "journal_barrier", return_value=b"event\n"), \
             patch.object(final.os.path, "lexists", return_value=False), \
             patch.object(final.select, "poll", return_value=poller, create=True), \
             patch.object(final.select, "POLLIN", 1, create=True), \
             patch.object(final.signal, "SIGKILL", 9, create=True), \
             patch.object(transition, "exclusive",
                          side_effect=lambda path, _raw: recorded.append(path.name)), \
             patch.object(final.signal, "pidfd_send_signal", create=True,
                          side_effect=lambda *_args: self.assertEqual(
                              recorded, ["a2-kill-attempt.json"])) as send:
            controller._kill_exact(21, IDENTITY, proposal())
        send.assert_called_once_with(21, 9, None, 0)
        self.assertEqual(recorded, ["a2-kill-attempt.json",
                                    "a2-kill-observed.json"])

    def test_barrier_requires_stopped_same_incarnation_and_consumed_state(self):
        controller = final.FinalController()
        session = Mock()
        poller = Mock()
        poller.poll.return_value = []
        raw = final.canonical(event())
        service = {"InvocationID": INVOCATION, "MainPID": "42001",
                   "NRestarts": "0", "ActiveState": "active"}
        with patch.object(final.select, "poll", return_value=poller, create=True), \
             patch.object(final.select, "POLLIN", 1, create=True), \
             patch.object(control, "show", return_value=service), \
             patch.object(final, "process_identity", return_value=(IDENTITY, "T")), \
             patch.object(final, "require_only_broker_process"), \
             patch.object(final, "journal_barrier", return_value=raw), \
             patch.object(transition, "regular", return_value=b"synthetic-wal"), \
             patch.object(transition, "tree_fingerprints"), \
             patch.object(transition, "exclusive") as write:
            observed, wal_sha = controller._observe_stopped(
                21, IDENTITY, proposal(), session)
        self.assertEqual(observed, raw)
        self.assertEqual(wal_sha, final.sha(b"synthetic-wal"))
        session._db_state.assert_called_once_with("CONSUMED")
        self.assertEqual(write.call_args.args[0].name, "a2-barrier.json")

    def test_restart_requires_exactly_one_new_healthy_invocation(self):
        controller = final.FinalController()
        session = Mock()
        service = {"InvocationID": RESTARTED, "MainPID": "42002",
                   "NRestarts": "1", "ActiveState": "active"}
        candidate = {"invocationId": RESTARTED, "pid": 42002}
        intent = {"record": {"authorizationId": "d" * 32}}
        with patch.object(control, "show", return_value=service), \
             patch.object(transition, "active", return_value=candidate), \
             patch.object(final, "process_identity", return_value=(
                 {**IDENTITY, "pid": 42002, "invocationId": RESTARTED,
                  "startTicks": 2000}, "S")), \
             patch.object(final.os.path, "lexists", return_value=False), \
             patch.object(control, "relay", return_value={"status": "HEALTH_OK"}), \
             patch.object(control, "stage3_verify_candidate_release"), \
             patch.object(transition, "regular", return_value=final.canonical(intent)), \
             patch.object(final.liveness, "verify"):
            self.assertEqual(controller._restart(IDENTITY, session), candidate)
        session._db_state.assert_called_once_with("CONSUMED")
        with patch.object(control, "show", return_value={**service,
                                                           "NRestarts": "2"}):
            with self.assertRaisesRegex(final.FinalError, "RESTART_DRIFT"):
                controller._restart(IDENTITY, session)

    def test_execute_composes_exact_order_and_seals_no_proof(self):
        controller = final.FinalController()
        steps = []
        session = Mock()
        session.frame_sha256 = "9" * 64
        session.submit_initial_once.side_effect = lambda: steps.append("initial")
        session.recover_once.side_effect = lambda: (steps.append("recover"), {
            "status": "PROOF_BURNED_NO_CLAIM", "challengeId": CHALLENGE})[1]
        session.replay_exact_once.side_effect = lambda: (steps.append("replay"), {
            "status": "NO_RESPONSE", "frameSha256": "9" * 64})[1]
        event_raw = final.canonical(event())
        controller.transition.activate = Mock(side_effect=lambda: (
            steps.append("activate"), {"profile": transition.PROFILE_ACTIVE,
                                       "candidateRelease": control.STAGE3_RELEASE,
                                       "invocationId": INVOCATION})[1])
        controller.transition.seal_evidence = Mock(
            side_effect=lambda _value: steps.append("seal"))
        controller.transition.restore = Mock(side_effect=lambda: (
            steps.append("restore"), {"profile": transition.PROFILE_RESTORED,
                                      "invocationId": "2" * 32})[1])
        controller.transition.journal.last = Mock(return_value=("RESTORED", {}))
        controller._claim_attempt = Mock(side_effect=lambda: steps.append("attempt"))
        controller._arm = Mock(side_effect=lambda _value: steps.append("arm"))
        controller._observe_stopped = Mock(side_effect=lambda *_args: (
            steps.append("barrier"), (event_raw, "8" * 64))[1])
        controller._disarm = Mock(side_effect=lambda _value: steps.append("disarm"))
        controller._kill_exact = Mock(side_effect=lambda *_args: steps.append("kill"))
        controller._restart = Mock(side_effect=lambda *_args: (
            steps.append("restart"), {"invocationId": RESTARTED,
                                      "pid": 42002})[1])
        with patch.object(final, "linux_pidfd_available", return_value=True), \
             patch.object(control, "assert_host"), \
             patch.object(final.os.path, "lexists", return_value=False), \
             patch.object(control, "stage3_issue_authorization",
                          side_effect=lambda: (steps.append("authorize"), {
                              "authorizationId": "d" * 32})[1]), \
             patch.object(control, "stage3_prepare_package",
                          side_effect=lambda: (steps.append("prepare"), proposal())[1]), \
             patch.object(final.adapters, "Session", return_value=session), \
             patch.object(transition, "active", return_value={
                 "pid": 42001, "invocationId": INVOCATION}), \
             patch.object(final, "process_identity", side_effect=lambda pid, _inv: (
                 (IDENTITY, "S") if pid == 42001 else
                 ({**IDENTITY, "pid": 42002,
                   "invocationId": RESTARTED, "startTicks": 2000}, "S"))), \
             patch.object(final.os, "pidfd_open", return_value=21, create=True), \
             patch.object(final.os, "close"), \
             patch.object(final, "journal_barrier", side_effect=lambda identity,
                          _proposal: event_raw if identity["pid"] == 42001
                          else None), \
             patch.object(transition, "exclusive") as write:
            result = controller.execute_once()
        self.assertEqual(steps, ["attempt", "authorize", "activate", "prepare", "arm",
                                 "initial", "barrier", "disarm", "kill",
                                 "restart", "recover", "replay", "seal", "restore"])
        evidence = controller.transition.seal_evidence.call_args.args[0]
        self.assertEqual(evidence["stoppedProcessIdentity"], IDENTITY)
        self.assertEqual(evidence["killedProcessIdentity"], IDENTITY)
        self.assertEqual(evidence["replayOutcome"], "REJECTED_BEFORE_CLAIM")
        self.assertEqual(result["status"], "RESTORED")
        self.assertNotIn("assertion", str(evidence))
        self.assertNotIn("signature", str(result))
        self.assertEqual(write.call_args.args[0].name, "final-report.json")
        with self.assertRaisesRegex(final.FinalError, "ALREADY_ENTERED"):
            controller.execute_once()

    def test_failure_after_attempt_is_terminal_and_contained(self):
        controller = final.FinalController()
        controller.transition.activate = Mock(
            side_effect=final.FinalError("SYNTHETIC_ACTIVATION_FAILURE"))
        controller._claim_attempt = Mock()
        with patch.object(final, "linux_pidfd_available", return_value=True), \
             patch.object(control, "assert_host"), \
             patch.object(final.os.path, "lexists", return_value=False), \
             patch.object(control, "stage3_issue_authorization",
                          return_value={"authorizationId": "d" * 32}), \
             patch.object(controller, "_contain_if_needed") as contain:
            with self.assertRaisesRegex(final.FinalError,
                                        "SYNTHETIC_ACTIVATION_FAILURE"):
                controller.execute_once()
        contain.assert_called_once()
        self.assertTrue(controller._entered)


if __name__ == "__main__":
    unittest.main()
