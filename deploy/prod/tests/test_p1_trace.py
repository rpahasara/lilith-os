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


if __name__ == "__main__":
    unittest.main()
