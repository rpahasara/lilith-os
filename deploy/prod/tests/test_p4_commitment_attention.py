"""P-4 P4-5c: a missed or failed commitment of LILITH's is surfaced once, on owner turns, on the full-agent path only,
with scheduler evidence and no delivery claim; shadow logs only. Also: commitments are never the owner's goals."""
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_p2_social_preferences import load_router  # noqa: E402

NOW = 1_800_000_000.0


def iso(ts):
    import datetime as dt
    return dt.datetime.fromtimestamp(ts, dt.timezone.utc).isoformat()


GOALS = [
    {"goalId": "c1", "type": "commitment.once", "title": "Call the bank", "lifecycleState": "BLOCKED",
     "deadline": "2027-01-15T09:00:00Z"},
    {"goalId": "c2", "type": "commitment.once", "title": "Release notes", "lifecycleState": "FAILED",
     "failedAt": iso(NOW - 86400), "deadline": "2027-01-14T09:00:00Z"},
    {"goalId": "c3", "type": "commitment.once", "title": "Old", "lifecycleState": "FAILED", "failedAt": iso(NOW - 30 * 86400)},
    {"goalId": "c4", "type": "commitment.once", "title": "Water", "lifecycleState": "COMPLETED"},
    {"goalId": "c5", "type": "commitment.once", "title": "Later", "lifecycleState": "ACTIVE"},
    {"goalId": "g1", "type": "career.followup", "title": "Pass the CKA exam", "lifecycleState": "BLOCKED"}]


class CommitmentAttentionTests(unittest.TestCase):
    def setUp(self):
        self.tmp, self.gi = load_router()
        self.log = Path(tempfile.mkdtemp()) / "decisions.log"
        self.gi._COMMITMENTS = self.gi._commitments.UnresolvedSource(fetch=lambda: GOALS, clock=lambda: NOW)

    def tearDown(self):
        self.gi._tc.begin()
        shutil.rmtree(self.tmp, ignore_errors=True)
        shutil.rmtree(self.log.parent, ignore_errors=True)

    def turn(self, mode, owner=True):
        gi = self.gi
        ctx = gi._tc.begin("telegram_owner_dm" if owner else "public", owner)
        gi._canonical_memory.set_owner_turn(owner, "telegram_owner_dm" if owner else "public")
        gi._turn_id.set("c" * 16)
        gi._apply_commitments(gi._config.RouterConfig(enabled=True, log_path=str(self.log), commitments_mode=mode))
        return ctx

    def records(self):
        return [json.loads(l) for l in self.log.read_text(encoding="utf-8").splitlines()] if self.log.exists() else []

    def test_only_missed_or_recent_failures(self):
        got = [g["goalId"] for g in self.gi._commitments.unresolved(GOALS, NOW)]
        self.assertEqual(got, ["c1", "c2"])

    def test_live_agent_hint_only_once_and_no_delivery_claim(self):
        tc = self.gi._tc
        ctx = self.turn("live")
        hint = tc.agent_hint(ctx)
        self.assertIn('the reminder "Call the bank" (due 2027-01-15T09:00:00Z): the scheduler has not run it', hint)
        self.assertIn("its scheduled run failed", hint)
        self.assertIn("never say it was sent", hint)
        self.assertNotIn("was delivered", hint)
        self.assertEqual(tc.lean_suffix(ctx), "")                          # never on the fast path (N-48)
        self.assertEqual(ctx.summary()["responsibility"], 2)
        rec = self.records()[-1]
        self.assertEqual((rec["lane"], rec["unresolved"], rec["surfaced"]), ("commitments", 2, True))
        self.assertNotIn("Call the bank", json.dumps(rec))
        again = self.turn("live")                                          # once per commitment per process
        self.assertEqual(again.responsibility, ())
        self.assertIsNone(tc.responsibility_text(again))
        text = (ROOT / "deploy/prod/lilith_router/gateway_integration.py").read_text(encoding="utf-8")
        self.assertIn('if not why and tctx.responsibility:\n        why = "responsibility"', text)

    def test_shadow_logs_only_and_non_owner_gets_nothing(self):
        ctx = self.turn("shadow")
        self.assertEqual(ctx.responsibility, ())
        self.assertIsNone(self.gi._tc.agent_hint(ctx))
        self.assertEqual(self.records()[-1]["surfaced"], False)
        self.gi._COMMITMENTS.surfaced.clear()
        before = len(self.records())
        self.assertEqual(self.turn("live", owner=False).responsibility, ())
        self.assertEqual(self.turn("off").responsibility, ())
        self.assertEqual(len(self.records()), before)

    def test_goals_store_down_means_no_note(self):
        self.gi._COMMITMENTS = self.gi._commitments.UnresolvedSource(fetch=mock.Mock(side_effect=OSError("down")))
        self.assertEqual(self.turn("live").responsibility, ())

    def test_commitments_are_not_the_owners_goals(self):
        ap = self.gi._appraisal
        goals = [{"goalId": "c9", "type": "commitment.once", "title": "Drink water reminder", "lifecycleState": "ACTIVE"},
                 {"goalId": "g9", "type": "career.followup", "title": "Pass the CKA exam", "lifecycleState": "ACTIVE"}]
        self.assertEqual(ap.related_goals("time to drink water lol", goals), [])
        self.assertEqual([g["goalId"] for g in ap.related_goals("CKA tonight", goals)], ["g9"])

    def test_router_yaml(self):
        cfg = self.gi._config
        with mock.patch.object(cfg, "CONFIG_PATH", ROOT / "deploy/prod/lilith_router/router.yaml"):
            self.assertEqual(cfg.load().commitments_mode, "shadow")


if __name__ == "__main__":
    unittest.main()
