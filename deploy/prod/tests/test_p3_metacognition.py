"""P-3 batch 2: the L16 recall-gap signal and its controls (G-ASK / G-ESCALATE). Deterministic, owner-only, shadow
logs without applying, live renders one note on both reply paths, nothing logged as text."""
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

PROFILE = ("[About them]\nUser's real name is Ravindu; friends call him Sara.\n§\nHe is studying for the CKA exam and "
           "works on Kubernetes.")


class SignalTests(unittest.TestCase):
    def setUp(self):
        self.tmp, self.gi = load_router()
        self.mc = self.gi._meta

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_personal_fact_questions(self):
        for q in ("what's my sister's name?", "how did my interview go?", "what did I eat yesterday?",
                  "do you remember my dog's name?", "which band did I say I liked?", "did I tell you about the trip?",
                  "how long have I been learning guitar?", "when is my CKA exam?"):
            self.assertTrue(self.mc.personal_fact_question(q), q)
        for q in ("how do I fix this?", "what should I wear tonight?", "what do you think of my plan?",
                  "good morning!", "my sister is visiting", "what time is it?", "where should I start?",
                  "what am I going to do lol", "how can I tell my boss?", "what if I quit?"):
            self.assertFalse(self.mc.personal_fact_question(q), q)

    def test_gap_fires_only_when_nothing_covers_it(self):
        self.assertTrue(self.mc.recall_gap("what's my sister's name?", PROFILE)["fired"])
        self.assertTrue(self.mc.recall_gap("how did my interview go?", PROFILE)["fired"])
        self.assertFalse(self.mc.recall_gap("when is my CKA exam?", PROFILE)["fired"])
        self.assertFalse(self.mc.recall_gap("what's my real name?", PROFILE)["fired"])
        self.assertIsNone(self.mc.recall_gap("who am I to you?", PROFILE))           # nothing specific asked
        self.assertIsNone(self.mc.recall_gap("how do I rebase?", PROFILE))
        sig = self.mc.recall_gap("what's my sister's name?", "")
        self.assertEqual(set(sig), {"signal", "fired", "terms"})                       # counts, never words

    def test_notes_exist_for_each_control(self):
        for c in self.mc.CONTROLS:
            self.assertTrue(self.mc.note_for(c).startswith("["))
        self.assertIsNone(self.mc.note_for(None))
        self.assertIn("Don't guess", self.mc.ASK_NOTE)


class GateWiringTests(unittest.TestCase):
    def setUp(self):
        self.tmp, self.gi = load_router()
        self.log = Path(tempfile.mkdtemp()) / "decisions.log"
        self.gi._social_lean.profile = lambda home: PROFILE

    def tearDown(self):
        self.gi._tc.begin()
        shutil.rmtree(self.tmp, ignore_errors=True)
        shutil.rmtree(self.log.parent, ignore_errors=True)

    def cfg(self, mode, control="ask"):
        return self.gi._config.RouterConfig(enabled=True, log_path=str(self.log), metacognition_mode=mode,
                                            metacognition_recall_control=control)

    def run_gate(self, mode, message, owner=True, control="ask", focused=False):
        gi = self.gi
        ctx = gi._tc.begin("telegram_owner_dm" if owner else "public", owner)
        ctx.focused = focused
        gi._canonical_memory.set_owner_turn(owner, "telegram_owner_dm" if owner else "public")
        gi._turn_id.set("m" * 16)
        gi._apply_metacognition(self.cfg(mode, control), message)
        return ctx

    def records(self):
        return [json.loads(l) for l in self.log.read_text(encoding="utf-8").splitlines()] if self.log.exists() else []

    def test_live_ask_renders_the_note_on_both_paths(self):
        ctx = self.run_gate("live", "what's my sister's name?")
        self.assertEqual(ctx.meta["control"], "ask")
        self.assertTrue(ctx.meta["applied"])
        self.assertIn(self.gi._meta.ASK_NOTE, self.gi._tc.lean_suffix(ctx))
        self.assertIn(self.gi._meta.ASK_NOTE, self.gi._tc.agent_hint(ctx))
        rec = self.records()[-1]
        self.assertEqual((rec["lane"], rec["mode"], rec["recall_gap"]), ("metacognition", "live", True))
        self.assertNotIn("sister", json.dumps(rec))

    def test_shadow_logs_but_renders_nothing(self):
        ctx = self.run_gate("shadow", "what's my sister's name?")
        self.assertFalse(ctx.meta["applied"])
        self.assertEqual(self.gi._tc.lean_suffix(ctx), "")
        self.assertIsNone(self.gi._tc.agent_hint(ctx))
        self.assertEqual(self.records()[-1]["mode"], "shadow")

    def test_grounded_question_gets_no_control(self):
        ctx = self.run_gate("live", "when is my CKA exam?")
        self.assertEqual((ctx.meta["recall_gap"], ctx.meta["control"], ctx.meta["applied"]), (False, None, False))
        self.assertEqual(self.gi._tc.lean_suffix(ctx), "")

    def test_never_on_non_owner_focused_off_or_goal_status(self):
        for kw in ({"owner": False}, {"focused": True}):
            ctx = self.run_gate("live", "what's my sister's name?", **kw)
            self.assertEqual(ctx.meta, {}, kw)
        self.assertEqual(self.run_gate("off", "what's my sister's name?").meta, {})
        self.assertEqual(self.run_gate("live", "what am I working toward right now?").meta, {})
        self.assertEqual(self.records(), [])

    def test_escalate_moves_a_lean_turn_to_the_agent(self):
        ctx = self.run_gate("live", "how did my interview go?", control="escalate")
        self.assertEqual(ctx.meta["control"], "escalate")
        self.assertIn(self.gi._meta.ESCALATE_NOTE, self.gi._tc.agent_hint(ctx))
        text = (ROOT / "deploy/prod/lilith_router/gateway_integration.py").read_text(encoding="utf-8")
        self.assertIn('tctx.meta.get("control") == "escalate":\n                why = "recall_gap"', text)

    def test_failure_is_fail_open(self):
        self.gi._social_lean.profile = mock.Mock(side_effect=OSError("boom"))
        ctx = self.run_gate("live", "what's my sister's name?")
        self.assertEqual(ctx.meta, {})

    def test_config_parsing_and_router_yaml(self):
        cfg = self.gi._config
        self.assertEqual(cfg.RouterConfig().metacognition_mode, "off")
        tmp = Path(tempfile.mkdtemp())
        try:
            for raw, ctl, want in (("live", "escalate", ("live", "escalate")), ("LIVE", "x", ("live", "ask")),
                                   ("on", "ask", ("off", "ask"))):
                (tmp / "r.yaml").write_text("enabled: true\nmetacognition_mode: %s\nmetacognition_recall_control: %s\n"
                                            % (raw, ctl), encoding="utf-8")
                with mock.patch.object(cfg, "CONFIG_PATH", tmp / "r.yaml"):
                    got = cfg.load()
                    self.assertEqual((got.metacognition_mode, got.metacognition_recall_control), want)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
        with mock.patch.object(cfg, "CONFIG_PATH", ROOT / "deploy/prod/lilith_router/router.yaml"):
            got = cfg.load()
            self.assertEqual((got.metacognition_mode, got.metacognition_recall_control), ("shadow", "ask"))


if __name__ == "__main__":
    unittest.main()
