"""F9-C Track A: the durable First Interaction FORGET intent, the hold-first runner and the relay refusal.

The root hold is simulated by re-owning the intent to the holder uid (what ``hermes_forget_executor.py --hold`` does);
the gateway is a fake probe. Everything else is real: the Slice 3 runner, Privacy, L04, L18_V2 and the mock Hermes
executor of the runner tests. Linux, run as root (ownership changes). Synthetic data only.
"""

from __future__ import annotations

import json
import os
import stat
import sys
import unittest
from pathlib import Path
from unittest import mock

from fastapi import HTTPException

from test_privacy_forget_runner import FI, RunnerCase

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import app  # noqa: E402

from lilith_memory import privacy_forget_intent as I  # noqa: E402
from lilith_memory import privacy_forget_runner as R  # noqa: E402

HOLDER = 4242


class FakeGateway:
    def __init__(self, stopped: bool = True):
        self.is_stopped = stopped

    def stopped(self) -> bool:
        return self.is_stopped


@unittest.skipUnless(hasattr(os, "geteuid") and os.geteuid() == 0, "ownership changes need root")
class IntentCase(RunnerCase):
    def setUp(self) -> None:
        super().setUp()
        self.intent_dir = self.root / "intent"
        self.intent_dir.mkdir()
        os.chmod(self.intent_dir, 0o1770)
        self.intents = I.ForgetIntentStore(self.intent_dir, holder_uid=HOLDER)
        self.gateway = FakeGateway()
        self.ticks = 0.0
        self.on_tick = None

    def tick(self, seconds: float) -> None:
        self.ticks += seconds
        if self.on_tick:
            self.on_tick()

    def root_hold(self) -> None:
        os.chown(self.intents.path, HOLDER, -1)

    def hold_first(self, runner=None, timeout=5.0):
        return I.HoldFirstForgetRunner(runner or self.runner(), self.intents, self.gateway,
                                       hold_timeout_seconds=timeout, sleep=self.tick, monotonic=lambda: self.ticks)

    def forget_hf(self, hf=None, evidence=None, intent="intent.hf.1"):
        evidence = evidence or self.evidence()
        return (hf or self.hold_first()).forget(
            actor_ref_id=self.actor.ACTOR.actor_ref_id, actor_evidence_ref_id=evidence.actor_evidence_ref_id,
            intent_ref_id=intent, confirmation_event_ref="confirm.hf.1")


class IntentStoreTests(IntentCase):
    def test_record_is_durable_exact_and_never_overwrites(self):
        intent = self.intents.record(intent_ref_id="intent.a", actor_ref_id="actor.a")
        st = os.lstat(self.intents.path)
        self.assertEqual((stat.S_IMODE(st.st_mode), st.st_nlink), (0o640, 1))
        self.assertEqual(json.loads(self.intents.path.read_text()), intent)
        self.assertEqual(set(intent), I.INTENT_FIELDS)
        self.assertEqual([p.name for p in self.intent_dir.iterdir()], [I.INTENT_NAME])     # no temp left
        self.assertEqual(self.intents.record(intent_ref_id="intent.a", actor_ref_id="actor.a"), intent)
        with self.assertRaises(I.ForgetIntentError) as caught:
            self.intents.record(intent_ref_id="intent.b", actor_ref_id="actor.a")
        self.assertEqual(caught.exception.code, "FORGET_INTENT_PENDING")
        self.assertEqual(json.loads(self.intents.path.read_text()), intent)

    def test_states(self):
        self.assertEqual(self.intents.state(), I.ABSENT)
        self.intents.record(intent_ref_id="intent.a", actor_ref_id="actor.a")
        self.assertEqual(self.intents.state(), I.RECORDED)
        self.root_hold()
        self.assertEqual(self.intents.state(), I.HELD)

    def as_core_api(self, fn) -> int:
        """Run ``fn`` in a child with the Core API's real privileges: an ordinary uid in the intent group only."""
        pid = os.fork()
        if pid == 0:
            try:
                os.setgroups([HOLDER + 1])
                os.setgid(HOLDER + 1)
                os.setuid(HOLDER + 2)
                fn()
                os._exit(0)
            except PermissionError:
                os._exit(13)
            except BaseException:
                os._exit(1)
        return os.waitstatus_to_exitcode(os.waitpid(pid, 0)[1])

    def test_the_core_api_uid_records_durably_but_never_removes_a_held_intent(self):
        os.chmod(self.root, 0o755)
        os.chown(self.intent_dir, 0, HOLDER + 1)
        record = lambda: self.intents.record(intent_ref_id="intent.a", actor_ref_id="actor.a")  # noqa: E731
        os.chmod(self.intent_dir, 0o1730)                       # create-only: the directory fsync is refused
        self.assertEqual(self.as_core_api(record), 13)
        for p in self.intent_dir.iterdir():
            p.unlink()
        os.chmod(self.intent_dir, 0o1770)                       # the shipped mode
        self.assertEqual(self.as_core_api(record), 0)
        self.assertEqual(os.lstat(self.intents.path).st_uid, HOLDER + 2)
        os.chown(self.intents.path, 0, HOLDER + 1)              # the root hold
        self.assertEqual(self.as_core_api(lambda: os.unlink(self.intents.path)), 13)   # sticky: not removable
        self.assertTrue(self.intents.path.exists())
        self.assertEqual(self.as_core_api(self.intents.read), 0)                         # still group-readable

    def test_malformed_or_symlinked_intent_is_never_trusted(self):
        target = self.root / "elsewhere.json"
        target.write_text("{}")
        os.symlink(target, self.intents.path)
        with self.assertRaises(OSError):
            self.intents.read()


class HoldFirstTests(IntentCase):
    def test_no_privacy_action_until_the_root_hold_and_a_stopped_gateway(self):
        self.gateway.is_stopped = False
        evidence = self.evidence()
        result = self.forget_hf(evidence=evidence)                              # H2/H3: intent only
        self.assertEqual((result.status, result.failure_code),
                         (I.INTENT_RECORDED_HOLD_PENDING, "HOLD_NOT_ESTABLISHED"))
        self.assertIsNone(self.privacy.in_flight_authorization(FI))
        self.assertEqual(self.intents.state(), I.RECORDED)
        self.root_hold()                                                              # H4: held, gateway still up
        self.assertEqual(self.forget_hf(evidence=evidence).status, I.INTENT_RECORDED_HOLD_PENDING)
        self.assertIsNone(self.privacy.in_flight_authorization(FI))
        self.gateway.is_stopped = True                                           # H5: same, unconsumed evidence
        result = self.forget_hf(evidence=evidence)
        self.assertEqual(result.status, R.COMPLETE, result)
        self.assert_fi_erased()
        self.assertTrue(self.intents.path.exists())          # only root removes it (reconcile, after completion)
        self.assertTrue(self.privacy.identity_forget_completed(FI, R.P.HERMES_DEV_CONVERSATION))

    def test_hold_established_while_waiting(self):
        self.on_tick = lambda: self.intents.path.exists() and self.root_hold()
        self.assertEqual(self.forget_hf().status, R.COMPLETE)

    def test_H6_evidence_consumed_before_the_privacy_transaction_keeps_the_intent_blocking(self):
        self.intents.record(intent_ref_id="intent.hf.1", actor_ref_id=self.actor.ACTOR.actor_ref_id)
        self.root_hold()
        evidence = self.evidence()

        def crash_after_consumption(**kw):
            self.privacy.actor_authority.resolve_and_consume(
                kw["actor_evidence_ref_id"], action=kw["action"], consumer_ref="privacy.forget.v1")
            raise SystemExit("TEST_ONLY crash between evidence consumption and the Privacy transaction")

        with mock.patch.object(self.privacy, "begin_forget", crash_after_consumption):
            with self.assertRaises(SystemExit):
                self.forget_hf(evidence=evidence)
        self.assertIsNone(self.privacy.in_flight_authorization(FI))
        result = self.forget_hf(evidence=evidence)
        self.assertEqual(result.status, I.INTENT_STALLED_EVIDENCE_REFUSED)
        self.assertTrue(self.intents.path.exists())
        self.assertFalse(self.privacy.identity_forget_completed(FI, R.P.HERMES_DEV_CONVERSATION))
        self.assertEqual(self.forget_hf().status, R.COMPLETE)                   # owner re-confirms (fresh evidence)

    def test_H7_crash_after_begin_forget_resumes_through_the_same_intent(self):
        self.intents.record(intent_ref_id="intent.hf.1", actor_ref_id=self.actor.ACTOR.actor_ref_id)
        self.root_hold()
        runner = self.runner()
        with mock.patch.object(runner, "resume", side_effect=SystemExit("TEST_ONLY crash after begin_forget")):
            with self.assertRaises(SystemExit):
                self.forget_hf(self.hold_first(runner))
        self.assertIsNotNone(self.privacy.in_flight_authorization(FI))
        self.assertEqual(self.hold_first().resume().status, R.COMPLETE)

    def test_replay_after_completion_is_already_complete(self):
        self.intents.record(intent_ref_id="intent.hf.1", actor_ref_id=self.actor.ACTOR.actor_ref_id)
        self.root_hold()
        self.assertEqual(self.forget_hf().status, R.COMPLETE)
        self.assertEqual(self.forget_hf().status, R.ALREADY_COMPLETE)

    def test_completion_proof_requires_the_hermes_owner_and_a_verifying_receipt(self):
        self.assertFalse(self.privacy.identity_forget_completed(FI, R.P.HERMES_DEV_CONVERSATION))
        self.intents.record(intent_ref_id="intent.hf.1", actor_ref_id=self.actor.ACTOR.actor_ref_id)
        self.root_hold()
        self.assertEqual(self.forget_hf().status, R.COMPLETE)
        self.assertTrue(self.privacy.identity_forget_completed(FI, R.P.HERMES_DEV_CONVERSATION))
        self.assertFalse(self.privacy.identity_forget_completed(FI, "L18_V2_NOT_AN_OWNER"))
        other = R.P.PrivacyGovernanceStore(self.privacy_db, b"TEST_ONLY another secret, 32+ bytes long",
                                           self.actor, now_fn=lambda: self.now)
        self.assertFalse(other.identity_forget_completed(FI, R.P.HERMES_DEV_CONVERSATION))
        # Tamper (not reachable through the API): an ACTIVE hold beside the verified receipt is never "completed".
        import sqlite3
        conn = sqlite3.connect(self.privacy_db)
        conn.execute("INSERT INTO privacy_hold VALUES (?,?,?,?,?,?,?,?)",
                     ("hold.tamper", "forget.tamper", *FI, "0" * 64, "ACTIVE", "2026-10-24T00:00:00Z"))
        conn.commit()
        conn.close()
        self.assertFalse(self.privacy.identity_forget_completed(FI, R.P.HERMES_DEV_CONVERSATION))


class RelayRefusalTests(unittest.TestCase):
    def setUp(self) -> None:
        import tempfile
        self.root = Path(tempfile.mkdtemp(prefix="f9c-relay-"))
        self.path = self.root / "hermes-forget" / "intent" / "first-interaction.intent"
        self.env = mock.patch.dict(os.environ, {"LILITH_FORGET_INTENT_PATH": str(self.path)})
        self.env.start()
        self.addCleanup(self.env.stop)
        self.console_calls = 0

    def tearDown(self) -> None:
        import shutil
        shutil.rmtree(self.root, ignore_errors=True)

    def console(self, *a, **k):
        self.console_calls += 1
        raise OSError("TEST_ONLY console unreachable")

    def relay(self, session="lilith-os"):
        with mock.patch.object(app._urlreq, "urlopen", self.console), \
                mock.patch.object(app, "_hermes_env", lambda key, default="": default):
            return app.os_conversation({"message": "TEST_ONLY hello", "session": session}, None)

    def status(self, session="lilith-os"):
        with self.assertRaises(HTTPException) as caught:
            self.relay(session)
        return caught.exception.status_code, caught.exception.detail

    def test_no_f9c_host_relays_as_before(self):
        self.assertEqual(self.status(), (502, "LILITH conversation console unreachable"))
        self.assertEqual(self.console_calls, 1)

    def test_intent_directory_present_without_intent_relays(self):
        self.path.parent.mkdir(parents=True)
        self.assertEqual(self.status()[0], 502)

    def test_pending_intent_refuses_every_turn_before_the_console_is_reached(self):
        self.path.parent.mkdir(parents=True)
        self.path.write_text("{}")
        for session in ("lilith-os", app._CAPTURE_PREFIX + "x"):
            with self.subTest(session=session):
                self.assertEqual(self.status(session), (503, "FORGET_HOLD_ACTIVE"))
        self.assertEqual(self.console_calls, 0)
        with mock.patch.object(app._urlreq, "urlopen", self.console):
            with self.assertRaises(HTTPException) as caught:
                app._relay_conversation("TEST_ONLY direct", "lilith-os")
        self.assertEqual(caught.exception.detail, "FORGET_HOLD_ACTIVE")
        self.assertEqual(self.console_calls, 0)

    def test_f9c_host_without_intent_directory_or_unreadable_state_refuses(self):
        self.path.parent.parent.mkdir(parents=True)
        self.assertEqual(self.status(), (503, "FORGET_STATE_UNAVAILABLE"))
        self.path.parent.mkdir()
        with mock.patch.object(app._os, "lstat", side_effect=PermissionError(13, "denied")):
            self.assertEqual(self.status(), (503, "FORGET_STATE_UNAVAILABLE"))
        self.assertEqual(self.console_calls, 0)

    def test_app_still_never_imports_the_memory_runtime(self):
        self.assertNotIn("lilith_memory", Path(app.__file__).read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
