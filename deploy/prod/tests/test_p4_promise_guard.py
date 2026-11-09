"""P-4 P4-4b: unbacked-promise shadow check. Flags only; a promise counts as backed only by an accepted cronjob create
in the same turn; never on text alone."""
import json
import shutil
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_p2_social_preferences import load_router  # noqa: E402


def call(cid, action="create"):
    return {"id": cid, "type": "function",
            "function": {"name": "cronjob", "arguments": json.dumps({"action": action, "schedule": "10m"})}}


class PromiseGuardTests(unittest.TestCase):
    def setUp(self):
        self.tmp, self.gi = load_router()
        self.pg = self.gi._promise_guard

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_detection(self):
        for t in ("I'll remind you at six.", "Okay, I’ll check in tomorrow morning.", "I will follow up on Friday.",
                  "I'm going to ping you later."):
            self.assertTrue(self.pg.check(t, [])["promise"], t)
        for t in ("I've set a reminder for 6pm.", "Done, your reminder is set.", "I have scheduled a follow-up."):
            self.assertTrue(self.pg.check(t, [])["scheduling_claim"], t)
        for t in ("Remind me what you meant?", "I'll think about it.", "You should set a reminder.",
                  "I'll let you know what I think.", "Check in with your manager tomorrow."):
            r = self.pg.check(t, [])
            self.assertFalse(r["promise"] or r["scheduling_claim"], t)

    def test_backed_only_by_an_accepted_create_in_this_turn(self):
        ok = [{"role": "user", "content": "remind me in 10 min"},
              {"role": "assistant", "content": None, "tool_calls": [call("c1")]},
              {"role": "tool", "tool_call_id": "c1", "content": json.dumps({"success": True, "job_id": "abc"})}]
        r = self.pg.check("I'll remind you in 10 minutes.", ok)
        self.assertEqual((r["scheduled"], r["unbacked_promise"]), (True, False))
        failed = ok[:2] + [{"role": "tool", "tool_call_id": "c1", "content": json.dumps({"error": "bad schedule"})}]
        self.assertTrue(self.pg.check("I've set a reminder.", failed)["unbacked_promise"])
        listing = [ok[0], {"role": "assistant", "tool_calls": [call("c2", "list")]},
                   {"role": "tool", "tool_call_id": "c2", "content": "[]"}]
        self.assertTrue(self.pg.check("I'll remind you.", listing)["unbacked_promise"])
        earlier = ok + [{"role": "assistant", "content": "done"}, {"role": "user", "content": "thanks"}]
        self.assertTrue(self.pg.check("I'll check in tomorrow.", earlier)["unbacked_promise"])   # previous turn
        no_result = ok[:2]
        self.assertFalse(self.pg.check("x", no_result)["scheduled"])
        self.assertEqual(self.pg.check("Sounds good!", [])["unbacked_promise"], False)

    def test_turn_record_has_flags_only_when_shadow(self):
        gi = self.gi
        log = Path(tempfile.mkdtemp()) / "decisions.log"
        try:
            for mode in ("shadow", "off"):
                cfg = gi._config.RouterConfig(enabled=True, log_path=str(log), promise_guard_mode=mode)
                with mock.patch.object(gi._config, "load", return_value=cfg):
                    gi._turn_id.set("p" * 16)
                    gi.log_turn_end(types.SimpleNamespace(source=None, session_key="k"),
                                    result={"final_response": "PRIVATE I'll remind you tomorrow", "messages": []})
            recs = [json.loads(l) for l in log.read_text(encoding="utf-8").splitlines()]
            self.assertTrue(recs[0]["unbacked_promise"])
            self.assertNotIn("promise", recs[1])
            self.assertNotIn("PRIVATE", log.read_text(encoding="utf-8"))
        finally:
            shutil.rmtree(log.parent, ignore_errors=True)

    def test_router_yaml(self):
        cfg = self.gi._config
        with mock.patch.object(cfg, "CONFIG_PATH", ROOT / "deploy/prod/lilith_router/router.yaml"):
            self.assertEqual(cfg.load().promise_guard_mode, "shadow")


if __name__ == "__main__":
    unittest.main()
