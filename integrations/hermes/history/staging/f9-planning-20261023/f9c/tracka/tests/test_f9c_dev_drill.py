"""f9c2 drill tool, offline (WSL, root; no systemd). The tool's own provision builds fresh stores; its forget runs the
governed hold-first FORGET with the real Privacy store, real actor evidence, real L04 / L18_V2 owners and the Slice 2
Hermes adapter over the runner tests' resolving mock executor (the root executor is exercised by the matrix/mirror).

Answers the open question: with NO First Interaction rows in the stores, do L04 and L18_V2 record COMPLETE so that
Privacy completes? Also: guards (root, probe paths), one-time provisioning, evidence replay, and that the deploy-time
probe paths are never created.

    F9C_CORE_API=<core-api dir> F9C_EXECUTOR_PKG=<pkgfiles dir> python3 -m unittest test_f9c_dev_drill
"""

from __future__ import annotations

import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

CORE = Path(os.environ["F9C_CORE_API"])
PKG = Path(os.environ["F9C_EXECUTOR_PKG"])
sys.path.insert(0, str(CORE / "tests"))
sys.path.insert(0, str(PKG / "bin"))

from test_hermes_erasure_owner import FakeClock  # noqa: E402
from test_privacy_forget_runner import ResolvingExecutor  # noqa: E402

import f9c_dev_drill as D  # noqa: E402


class FakeGateway:
    def stopped(self):
        return True


class DrillToolTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="f9c-drill-"))
        self.drill = self.tmp / "f9-drill"
        self.drill.mkdir(mode=0o700)
        self.intent_dir = self.tmp / "intent"
        self.intent_dir.mkdir(mode=0o1770)
        self.paths = D.Paths(self.drill)
        self.rt = D.load_runtime(CORE)
        self.clock = FakeClock()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def kw(self, privacy):
        H, I = self.rt["hermes_erasure_owner"], self.rt["privacy_forget_intent"]
        hermes = H.HermesConversationErasureOwner(
            privacy, ResolvingExecutor(self.tmp / "receipts", privacy), deployment_environment="DEV_SYNTHETIC",
            timeout_seconds=10.0, poll_seconds=1.0, sleep=self.clock.sleep, monotonic=self.clock.monotonic)
        return {"hermes": hermes, "intents": I.ForgetIntentStore(self.intent_dir, holder_uid=0), "gateway": FakeGateway()}

    def forget(self, approval="owner-ok.f9c2.test"):
        _actor, privacy = D.stores(self.rt, self.paths)
        return D.forget(self.rt, self.paths, approval, **self.kw(privacy)), privacy

    def test_provision_builds_v2_floor_stores_once(self):
        out = D.provision(self.rt, self.paths)
        self.assertEqual(out["status"], "PROVISIONED")
        self.assertTrue(out["floorAdded"])
        for p in (self.paths.cognitive, self.paths.privacy, self.paths.actor_key, self.paths.privacy_key):
            self.assertEqual(os.stat(p).st_mode & 0o777, 0o600, p)
        _a, privacy = D.stores(self.rt, self.paths)
        self.assertEqual(privacy.required_owners(*self.rt["privacy_forget_runner"].IDENTITY[:2]),
                         frozenset({self.rt["privacy_governance"].HERMES_DEV_CONVERSATION}))
        with self.assertRaises(D.DrillError):
            D.provision(self.rt, self.paths)                                  # one-time; nothing changed
        for probe in D.PROBE_PATHS:
            self.assertFalse(str(probe).startswith(str(self.tmp)))

    def test_forget_with_no_first_interaction_rows_completes_through_l04_l18_and_hermes(self):
        D.provision(self.rt, self.paths)
        out, privacy = self.forget()
        self.assertEqual(out["status"], "COMPLETE", out)
        self.assertEqual(out["completedOwners"], ["L04", "L18_V2", "HERMES_DEV_CONVERSATION"])
        R = self.rt["privacy_forget_runner"]
        self.assertIsNone(privacy.in_flight_authorization(R.IDENTITY))
        self.assertTrue(privacy.identity_forget_completed(R.IDENTITY, "HERMES_DEV_CONVERSATION"))
        self.assertTrue(privacy.suppression_matches(R.IDENTITY))
        self.assertEqual(privacy.verify_suppression_integrity(), 1)
        with self.assertRaises(D.DrillError):                                  # until root releases the first intent:
            self.forget("owner-ok.f9c2.second")                               # refused BEFORE any evidence is issued
        (self.intent_dir / "first-interaction.intent").unlink()                # what root reconcile does on proof
        again, _ = self.forget("owner-ok.f9c2.second")
        self.assertEqual(again["status"], "ALREADY_COMPLETE")                 # replay: nothing to do
        (self.intent_dir / "first-interaction.intent").unlink()
        with self.assertRaises(D.DrillError):                                  # an approval reference is single-use
            self.forget("owner-ok.f9c2.second")

    def test_reused_approval_reference_is_evidence_replay_and_stays_blocking(self):
        D.provision(self.rt, self.paths)
        _a, privacy = D.stores(self.rt, self.paths)
        actor, _p = D.stores(self.rt, self.paths)
        action = self.rt["privacy_forget_runner"].first_interaction_forget_action(actor.ACTOR.actor_ref_id)
        import hashlib
        ev = actor.issue(action=action, request_digest=hashlib.sha256(b"x").hexdigest(), nonce="f9c-dev-drill.dup",
                         ttl_seconds=300)
        actor.resolve_and_consume(ev.actor_evidence_ref_id, action=action, consumer_ref="privacy.forget.v1")
        r = D.runner(self.rt, self.paths, privacy, **self.kw(privacy)).forget(
            actor_ref_id=actor.ACTOR.actor_ref_id, actor_evidence_ref_id=ev.actor_evidence_ref_id,
            intent_ref_id="intent.dup", confirmation_event_ref="owner-approval.dup")
        self.assertEqual(r.status, self.rt["privacy_forget_intent"].INTENT_STALLED_EVIDENCE_REFUSED)
        self.assertTrue((self.intent_dir / "first-interaction.intent").exists())

    def test_guards(self):
        with self.assertRaises(D.DrillError):
            D.guard(self.paths, test_root=True)                                # run as root here: refused
        with self.assertRaises(D.DrillError):
            D.guard(D.Paths(D.DATA_DIR), test_root=True)                       # the probe's data directory
        with self.assertRaises(D.DrillError):
            D.guard(D.Paths(D.DATA_DIR / "f9-drill"), test_root=True)          # anything under it

    def test_bad_owner_approval_reference_is_refused_before_anything(self):
        D.provision(self.rt, self.paths)
        with self.assertRaises(D.DrillError):
            D.forget(self.rt, self.paths, "has spaces / slashes")
        _a, privacy = D.stores(self.rt, self.paths)
        self.assertIsNone(privacy.in_flight_authorization(self.rt["privacy_forget_runner"].IDENTITY))


if __name__ == "__main__":
    unittest.main()
