"""P-1 trace (2026-11-08): one turn id on every decision-log record; metadata only, never message text."""
import json
import shutil
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_owner_memory import OWNER, ROOT, load_router, src  # noqa: E402

SETTINGS = {"schemaVersion": 1, "enabled": True, "ownerTelegramUserIds": [OWNER]}
SECRET = "my-private-message-text-xyz"


class TurnIdTests(unittest.TestCase):
    def setUp(self):
        self.tmp, self.gi = load_router()
        self.log = Path(tempfile.mkdtemp()) / "decisions.log"
        self.cfg = self.gi._config.RouterConfig(enabled=True, log_path=str(self.log))

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)
        shutil.rmtree(self.log.parent, ignore_errors=True)

    def records(self):
        return [json.loads(l) for l in self.log.read_text(encoding="utf-8").splitlines()] if self.log.exists() else []

    def turn(self, flag=True):
        """One routed turn whose impl writes through several existing lane writers."""
        gi, cfg = self.gi, self.cfg
        cfg.turn_trace_enabled = flag

        def impl(**kw):
            d = types.SimpleNamespace(mode="social", confidence=0.9, reason="r", signals={"tech": 0})
            gi._log_decision(cfg, "telegram", OWNER, d, True, SECRET)
            gi._note_social_route(cfg, "telegram", OWNER, "groq_lean")
            gi._log_goal(cfg, "telegram", OWNER, {"goal_query": True}, "live", SECRET)
            gi._log_social_cognition(cfg, {"lane": "social_cognition", "cue_types": []})
            return None
        gi._route_turn_impl = impl
        gi._canonical_memory.load_settings = lambda home, **k: SETTINGS
        gi._canonical_memory.turn_note = lambda *a, **k: None
        gi._platform_name = lambda s: "telegram"
        with mock.patch.object(gi._config, "load", return_value=cfg):
            ctx = types.SimpleNamespace(source=src(user_id=OWNER, chat_id=OWNER, chat_type="dm"),
                                        session_key="k", message=SECRET)
            gi.route_turn(runner=None, ctx=ctx, model="m", runtime_kwargs={}, turn_route={}, combined_ephemeral="")

    def test_all_records_of_one_turn_share_one_id_and_turns_differ(self):
        self.turn()
        self.turn()
        recs = self.records()
        self.assertEqual(len(recs), 8)
        first, second = {r["turn_id"] for r in recs[:4]}, {r["turn_id"] for r in recs[4:]}
        self.assertEqual(len(first), 1)
        self.assertEqual(len(second), 1)
        self.assertNotEqual(first, second)
        self.assertTrue(all(len(r["turn_id"]) == 16 and "ts" in r for r in recs))

    def test_no_message_text_anywhere(self):
        self.turn()
        raw = self.log.read_text(encoding="utf-8")
        self.assertNotIn(SECRET, raw)
        self.assertNotIn("preview", raw)

    def test_flag_off_means_no_turn_id(self):
        self.turn(flag=False)
        self.assertTrue(self.records())
        self.assertFalse(any("turn_id" in r for r in self.records()))

    def test_write_failure_never_raises(self):
        self.cfg.log_path = str(Path(self.tmp) / "no" / "\0bad")
        self.gi._append_log(self.cfg, {"lane": "x"})                    # must not raise

    def test_writers_only_go_through_append_log(self):
        text = (ROOT / "deploy/prod/lilith_router/gateway_integration.py").read_text(encoding="utf-8")
        self.assertEqual(text.count("cfg.resolved_log_path()"), 1)      # inside _append_log only
        self.assertEqual(text.count('path.open("a"'), 1)

    def test_router_yaml_default_on(self):
        cfg = self.gi._config
        with mock.patch.object(cfg, "CONFIG_PATH", ROOT / "deploy/prod/lilith_router/router.yaml"):
            self.assertTrue(cfg.load().turn_trace_enabled)


class TurnEndTests(TurnIdTests):
    """P-1 T-2: one metadata-only turn-end record per turn."""

    def end(self, **kw):
        gi = self.gi
        with mock.patch.object(gi._config, "load", return_value=self.cfg):
            gi.log_turn_end(types.SimpleNamespace(source=src(user_id=OWNER, chat_id=OWNER, chat_type="dm"),
                                                  session_key="k", message=SECRET), **kw)
        return [r for r in self.records() if r.get("lane") == "turn"]

    def test_lean_turn(self):
        self.turn()
        self.gi._social_lean.LAST_USAGE.set({"model": "qwen", "provider": "groq", "tokens_in": 2400, "tokens_out": 120})
        rec = self.end(result={"api_calls": 0}, reply_chars=42)[-1]
        self.assertEqual((rec["answered_by"], rec["model"], rec["tokens_in"], rec["tokens_out"]), ("lean", "qwen", 2400, 120))
        self.assertEqual((rec["route"], rec["owner"], rec["reply_chars"]), ("groq_lean", True, 42))
        self.assertEqual(rec["turn_id"], self.records()[0]["turn_id"])           # joins the lane records
        self.assertIn("duration_ms", rec)

    def test_agent_turn_token_delta_and_fallback(self):
        agent = types.SimpleNamespace(model="gpt-4.1", provider="copilot", _fallback_activated=True,
                                      session_prompt_tokens=9000, session_completion_tokens=300)
        self.turn()
        first = self.end(agent=agent, result={"api_calls": 2})[-1]
        self.assertEqual((first["tokens_in"], first["tokens_out"], first["fallback_activated"]), (9000, 300, True))
        agent.session_prompt_tokens, agent.session_completion_tokens = 15000, 450
        self.turn()
        second = self.end(agent=agent, result={"api_calls": 1})[-1]
        self.assertEqual((second["tokens_in"], second["tokens_out"]), (6000, 150))   # this turn only
        self.assertEqual((second["answered_by"], second["provider"]), ("agent", "copilot"))

    def test_ready_answer_and_guard_flags(self):
        self.turn()
        rec = self.end(result={"api_calls": 0}, guard_changed=True, d1_recorded=True)[-1]
        self.assertEqual((rec["answered_by"], rec["guard_changed"], rec["d1_recorded"]), ("router", True, True))

    def test_turn_end_has_no_text_and_respects_flag(self):
        self.turn()
        self.end(result={"api_calls": 0}, reply_chars=10)
        self.assertNotIn(SECRET, self.log.read_text(encoding="utf-8"))
        self.turn(flag=False)
        before = len(self.records())
        self.end(result={"api_calls": 0})
        self.assertEqual(len(self.records()), before)                            # no turn id -> no record

    def test_run_py_calls_it_once_after_the_guard(self):
        text = (ROOT / "deploy/prod/hermes_gateway/run.py").read_text(encoding="utf-8")
        self.assertEqual(text.count("_lilith_router.log_turn_end("), 1)
        self.assertLess(text.index("final_response = _lilith_router.enforce_reply(final_response, ctx)"),
                        text.index("_lilith_router.log_turn_end("))


class RetentionTests(TurnIdTests):
    """P-1 T-6: bounded log; legacy preview scrub keeps every other field."""

    def test_rotation_keeps_one_generation(self):
        self.cfg.decision_log_max_bytes = 300
        for i in range(40):
            self.gi._append_log(self.cfg, {"lane": "x", "n": i})
        rotated = self.log.with_name(self.log.name + ".1")
        self.assertTrue(rotated.exists())
        self.assertLess(self.log.stat().st_size, 400)
        self.assertFalse(self.log.with_name(self.log.name + ".2").exists())
        ns = [json.loads(l)["n"] for l in rotated.read_text(encoding="utf-8").splitlines()]
        ns += [json.loads(l)["n"] for l in self.log.read_text(encoding="utf-8").splitlines()]
        self.assertEqual(ns, sorted(ns))                                         # order preserved, newest kept

    def test_config_bounds(self):
        cfg = self.gi._config
        with tempfile.TemporaryDirectory() as d:
            y = Path(d) / "router.yaml"
            for raw, want in (("decision_log_max_bytes: 10", 100_000), ("decision_log_max_bytes: 9999999999", 50_000_000),
                              ("decision_log_max_bytes: abc", 2_000_000)):
                y.write_text("enabled: true" + chr(10) + raw + chr(10), encoding="utf-8")
                with mock.patch.object(cfg, "CONFIG_PATH", y):
                    self.assertEqual(cfg.load().decision_log_max_bytes, want, raw)

    def test_scrub_removes_only_preview(self):
        sys.path.insert(0, str(ROOT / "scripts" / "cognitive_eval"))
        import scrub_legacy_preview as S
        self.log.write_text(chr(10).join([
            json.dumps({"ts": 1, "mode": "social", "msg_chars": 30, "preview": SECRET}),
            json.dumps({"ts": 2, "lane": "turn", "turn_id": "a" * 16}),
            "not json"]) + chr(10), encoding="utf-8")
        out = S.scrub_file(self.log)
        self.assertEqual((out["status"], out["removed"], out["records"]), ("SCRUBBED", 1, 3))
        text = self.log.read_text(encoding="utf-8")
        self.assertNotIn(SECRET, text)
        self.assertNotIn("preview", text)
        first = json.loads(text.splitlines()[0])
        self.assertEqual(first, {"ts": 1, "mode": "social", "msg_chars": 30})     # metadata kept
        self.assertIn("not json", text)
        self.assertEqual(S.scrub_file(self.log)["status"], "CLEAN")


if __name__ == "__main__":
    unittest.main()
