"""P-3 batch 3: deterministic appraisal. Event/goal signals only (no emotion score, nothing persisted), mapped onto the
approved Social Cognition lines and one bounded goal-context line; owner-only; shadow logs without applying."""
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

GOALS = [{"goalId": "g1", "title": "Pass the CKA exam", "lifecycleState": "ACTIVE"},
         {"goalId": "g2", "title": "Follow up on application 12 - Data Engineer at Acme", "lifecycleState": "ACTIVE"},
         {"goalId": "g3", "title": "Learn Rust", "lifecycleState": "COMPLETED"}]


class SignalTests(unittest.TestCase):
    def setUp(self):
        self.tmp, self.gi = load_router()
        self.ap = self.gi._appraisal

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def kinds(self, msg, goals=GOALS):
        return [(s.kind, s.ref) for s in self.ap.appraise(msg, goals)]

    def test_outcomes(self):
        for m in ("ugh I got rejected today", "I failed my mock exam lol", "I didn't pass", "another rejection, love that",
                  "my flight got cancelled", "they passed on me", "we lost the match", "failed my CKA mock exam haha",
                  "didn't get the job at Acme", "my conference talk got rejected lmao", "we didn't make the cut"):
            self.assertEqual(self.ap.outcome(m), "setback", m)
        for m in ("I passed!!", "I just got the offer", "got the job!!", "I'm officially certified", "we shipped it"):
            self.assertEqual(self.ap.outcome(m), "progress", m)
        for m in ("good morning", "how do I pass the CKA?", "did you get my message?", "what's up",
                  "failed to see the point lol", "didn't get your message", "I didn't get it lol"):
            self.assertIsNone(self.ap.outcome(m), m)

    def test_goal_relevance_is_active_and_specific(self):
        self.assertEqual(self.kinds("studying for the CKA tonight"), [("goal", "g1")])
        self.assertEqual(self.kinds("I got rejected by Acme"), [("setback", ""), ("goal", "g2")])
        self.assertEqual(self.kinds("learning Rust is fun"), [])                         # completed goal: no signal
        self.assertEqual(self.kinds("I'll follow up on that application"), [])           # title boilerplate only
        self.assertEqual(self.kinds("I failed the CKA", goals=()), [("setback", "")])

    def test_line_mapping_uses_only_approved_keys(self):
        setback = self.ap.appraise("I got rejected", ())
        adj = self.ap.adjust_lines
        self.assertEqual(adj(("playful",), setback, focused=False), ("mixed",))
        self.assertEqual(adj((), setback, focused=False), ("difficulty",))
        self.assertEqual(adj(("correction", "humor"), setback, focused=False), ("correction", "difficulty", "humor"))
        self.assertEqual(adj(("support",), setback, focused=False), ("support",))
        self.assertEqual(adj(("playful",), setback, focused=True), ("playful",))           # a focused turn keeps focus
        self.assertEqual(adj(("formal",), setback, focused=False), ("formal",))
        progress = self.ap.appraise("I passed!", ())
        self.assertEqual(adj(("playful",), progress, focused=False), ("playful",))       # no new celebration line
        from lilith_router import social_cognition as sc
        for lines in (adj(("playful",), setback, focused=False), adj((), setback, focused=False)):
            self.assertTrue(set(lines) <= set(sc.TONE_LINES))

    def test_goal_line_never_exposes_internal_labels(self):
        for title, want in (("Follow up on application 12 - Senior Data Engineer at Acme",
                             "their application for Senior Data Engineer at Acme"),
                            ("Follow up on application 9", "a job application they're following up on"),
                            ("Pass the CKA exam", "Pass the CKA exam"), ("Learn Rust (app 5)", "Learn Rust")):
            self.assertEqual(self.ap.goal_topic(title), want, title)
        note = self.ap.goal_note([{"goalId": "g_abcd1234", "title": "Follow up on application 12 - Data Engineer at Acme",
                                   "lifecycleState": "ACTIVE"}])
        for leak in ("application 12", "12", "g_abcd1234", "ACTIVE", "active"):
            self.assertNotIn(leak, note)
        self.assertIsNone(self.ap.goal_note([{"title": "#4"}]))

    def test_goal_note_is_bounded(self):
        note = self.ap.goal_note([{"title": "x" * 500, "lifecycleState": "ACTIVE"}])
        self.assertLess(len(note), 300)
        self.assertIsNone(self.ap.goal_note([]))

    def test_goal_source_fails_open_and_caches(self):
        calls = []
        src = self.ap.GoalSource(fetch=lambda: calls.append(1) or GOALS, clock=lambda: 0.0)
        self.assertEqual(len(src.current()), 3)
        src.current()
        self.assertEqual(len(calls), 1)
        bad = self.ap.GoalSource(fetch=mock.Mock(side_effect=OSError("down")))
        self.assertEqual(bad.current(), ())


class WiringTests(unittest.TestCase):
    def setUp(self):
        self.tmp, self.gi = load_router()
        self.log = Path(tempfile.mkdtemp()) / "decisions.log"
        self.gi._GOALS = self.gi._appraisal.GoalSource(fetch=lambda: GOALS)

    def tearDown(self):
        self.gi._tc.begin()
        shutil.rmtree(self.tmp, ignore_errors=True)
        shutil.rmtree(self.log.parent, ignore_errors=True)

    def run_turn(self, mode, message, owner=True, lines=(), focused=False):
        gi = self.gi
        ctx = gi._tc.begin("telegram_owner_dm" if owner else "public", owner)
        ctx.focused = focused
        ctx.style = gi._tc.directive(lines, focused=focused)
        gi._canonical_memory.set_owner_turn(owner, "telegram_owner_dm" if owner else "public")
        gi._turn_id.set("a" * 16)
        gi._apply_appraisal(gi._config.RouterConfig(enabled=True, log_path=str(self.log), appraisal_mode=mode), message)
        return ctx

    def records(self):
        return [json.loads(l) for l in self.log.read_text(encoding="utf-8").splitlines()] if self.log.exists() else []

    def test_live_setback_on_a_goal(self):
        from lilith_router import social_cognition as sc
        ctx = self.run_turn("live", "lol I got rejected by Acme, love that for me", lines=("playful",))
        self.assertEqual(ctx.style.lines, ("mixed",))
        self.assertEqual(ctx.style.appraisal_refs, ("setback", "goal:g2"))
        hint = self.gi._tc.agent_hint(ctx)
        self.assertIn(sc.TONE_LINES["mixed"], hint)
        self.assertNotIn(sc.TONE_LINES["playful"], hint)
        self.assertIn("Data Engineer at Acme", hint)
        self.assertNotIn("application 12", hint)
        self.assertIn("Data Engineer at Acme", self.gi._tc.lean_suffix(ctx))
        rec = self.records()[-1]
        self.assertEqual((rec["lane"], rec["signals"], rec["goal_refs"]), ("appraisal", ["setback", "goal"], ["g2"]))
        self.assertNotIn("Acme", json.dumps(rec))                                        # ids and keys only
        self.assertEqual(ctx.summary()["appraisal"], ["setback", "goal"])

    def test_shadow_traces_but_changes_nothing(self):
        ctx = self.run_turn("shadow", "I got rejected by Acme", lines=("playful",))
        self.assertEqual(ctx.style.lines, ("playful",))
        self.assertNotIn("Acme", self.gi._tc.agent_hint(ctx) or "")
        rec = self.records()[-1]
        self.assertEqual((rec["mode"], rec["lines_before"], rec["lines_after"]), ("shadow", ["playful"], ["mixed"]))

    def test_never_on_non_owner_off_or_goal_status_turns(self):
        self.assertEqual(self.run_turn("live", "I got rejected by Acme", owner=False).appraisal, ())
        self.assertEqual(self.run_turn("off", "I got rejected by Acme").appraisal, ())
        self.assertEqual(self.run_turn("live", "what am I working toward right now?").appraisal, ())
        self.assertEqual(self.run_turn("live", "good morning!").appraisal, ())
        self.assertEqual(self.records(), [])

    def test_goal_status_hint_carries_no_extra_goal_line(self):
        ctx = self.run_turn("live", "studying for the CKA tonight")
        self.assertIn("Pass the CKA exam", self.gi._tc.agent_hint(ctx))
        self.assertNotIn("Pass the CKA exam", self.gi._tc.agent_hint(ctx, "[status]"))

    def test_router_yaml_and_config(self):
        cfg = self.gi._config
        self.assertEqual(cfg.RouterConfig().appraisal_mode, "off")
        with mock.patch.object(cfg, "CONFIG_PATH", ROOT / "deploy/prod/lilith_router/router.yaml"):
            self.assertEqual(cfg.load().appraisal_mode, "shadow")


if __name__ == "__main__":
    unittest.main()
