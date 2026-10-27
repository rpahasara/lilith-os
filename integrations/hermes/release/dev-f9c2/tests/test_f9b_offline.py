"""F9-B offline regression tests (conversation-logging privacy). TEST_ONLY: synthetic text, no model calls, no network.

Same layout as the F7 suite (BUILD/hermes-agent -> release src). Config paths are passed explicitly:
    F9B_DEV_CONFIG=<pkg>/home/config.yaml F9B_OPERATE_CONFIG=<pkg>/profiles/operate/config.yaml \
        <venv>/bin/python -B tests/test_f9b_offline.py
"""

from __future__ import annotations

import ast
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

BUILD = Path(__file__).resolve().parents[1]
HERMES_SRC = BUILD / "hermes-agent"
_TMP = tempfile.TemporaryDirectory(prefix="f9b-")
os.environ["HERMES_HOME"] = str(Path(_TMP.name) / "hh")
os.environ["HOME"] = _TMP.name
sys.path.insert(0, str(HERMES_SRC))

CANARY = "F9B-UNIT-CANARY-4K8M synthetic"


def log_calls(path: Path, marker: str) -> list:
    """logger.<level>(...) calls whose format string contains `marker`."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return [n for n in ast.walk(tree) if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
            and n.func.attr in ("debug", "info", "warning", "error", "exception", "critical") and n.args
            and isinstance(n.args[0], ast.Constant) and marker in str(n.args[0].value)]


class OperatingLogTests(unittest.TestCase):
    """The two INFO lines that carried message text now carry sizes only."""

    def check(self, path, marker, fmt_must, fmt_must_not):
        calls = log_calls(path, marker)
        self.assertEqual(len(calls), 1, f"{marker} call sites")
        fmt = calls[0].args[0].value
        for s in fmt_must:
            self.assertIn(s, fmt)
        for s in fmt_must_not:
            self.assertNotIn(s, fmt)
        args = " ".join(ast.unparse(a) for a in calls[0].args[1:])
        self.assertNotIn("preview", args)
        return args

    def test_inbound_message_log_has_sizes_not_text(self):
        args = self.check(HERMES_SRC / "gateway" / "run.py", "inbound message:",
                          ("msg_chars=%d", "reply_to_chars=%d"), ("msg=%r", "reply_to_text"))
        self.assertIn("len(event.text", args)

    def test_conversation_turn_log_has_size_not_text(self):
        args = self.check(HERMES_SRC / "agent" / "turn_context.py", "conversation turn:",
                          ("msg_chars=%d",), ("msg=%r",))
        self.assertTrue(args.strip().endswith("len(summarize_user_message_for_log(user_message))"))


class RequestDumpTests(unittest.TestCase):
    """Request debug dumps (written unconditionally on API errors) carry no conversation content."""

    @classmethod
    def setUpClass(cls):
        from agent import agent_runtime_helpers as h
        cls.h = h

    def payload(self):
        return {"timestamp": "t", "session_id": "s", "reason": "max_retries_exhausted",
                "request": {"method": "POST", "url": "http://127.0.0.1:9911/openai/v1/chat/completions",
                            "headers": {"Authorization": "Bearer ***"},
                            "body": {"model": "openai/gpt-oss-120b", "stream": True, "max_completion_tokens": 1024,
                                     "reasoning_effort": "low", "stream_options": {"include_usage": True},
                                     "messages": [{"role": "system", "content": "SOUL " + CANARY},
                                                  {"role": "user", "content": [{"type": "text", "text": CANARY}]},
                                                  {"role": "assistant", "content": "earlier " + CANARY},
                                                  {"role": "user", "content": CANARY}],
                                     "tools": [{"type": "function", "function": {"name": "noop", "description": CANARY}}],
                                     "extra_body": {"note": CANARY}}},
                "error": {"type": "APIStatusError", "message": CANARY, "status_code": 500, "code": "x",
                          "body": {"echo": CANARY}, "response_text": CANARY, "response_status": 500}}

    def test_sanitizer_keeps_diagnostics_drops_content(self):
        out = self.h._content_free_request_dump(self.payload())
        raw = json.dumps(out)
        self.assertNotIn("CANARY", raw)
        body = out["request"]["body"]
        self.assertEqual([m["role"] for m in body["messages"]], ["system", "user", "assistant", "user"])
        self.assertEqual(body["messages"][3]["chars"], len(CANARY))
        self.assertEqual(body["messages"][1]["chars"], len(CANARY))
        self.assertEqual((body["model"], body["stream"], body["max_completion_tokens"], body["reasoning_effort"]),
                         ("openai/gpt-oss-120b", True, 1024, "low"))
        self.assertEqual(body["tools"], ["noop"])
        self.assertEqual(out["error"], {"type": "APIStatusError", "status_code": 500, "code": "x", "response_status": 500})
        self.assertTrue(out["content_free"])
        self.assertEqual(out["reason"], "max_retries_exhausted")

    def test_dump_file_written_on_error_is_content_free(self):
        logs = Path(_TMP.name) / "sessions"
        logs.mkdir(parents=True, exist_ok=True)
        agent = SimpleNamespace(client=SimpleNamespace(api_key="TEST_ONLY-not-a-key"), session_id="f9b-unit",
                                base_url="http://127.0.0.1:9911/openai/v1", api_mode="chat_completions",
                                logs_dir=logs, log_prefix="", verbose_logging=True,
                                _mask_api_key_for_logs=lambda k: "***", _vprint=lambda *a, **k: None)
        err = RuntimeError(CANARY)
        err.status_code = 503
        path = self.h.dump_api_request_debug(agent, {"model": "openai/gpt-oss-120b", "timeout": 60,
                                                     "messages": [{"role": "user", "content": CANARY}]},
                                             reason="non_retryable_client_error", error=err)
        self.assertIsNotNone(path)
        raw = Path(path).read_text(encoding="utf-8")
        self.assertNotIn("CANARY", raw)
        rec = json.loads(raw)
        self.assertTrue(rec["content_free"])
        self.assertEqual(rec["error"]["status_code"], 503)
        self.assertEqual(rec["request"]["body"]["messages"], [{"role": "user", "chars": len(CANARY)}])


class ProfileConfigTests(unittest.TestCase):
    """F9-A onboarding off survives the OPERATE profile switch (which replaces config.yaml)."""

    def test_both_profiles_disable_profile_build(self):
        import yaml
        from agent.onboarding import profile_build_mode
        for env in ("F9B_DEV_CONFIG", "F9B_OPERATE_CONFIG"):
            cfg = yaml.safe_load(Path(os.environ[env]).read_text(encoding="utf-8"))
            self.assertEqual(cfg["onboarding"]["profile_build"], "off", env)
            self.assertEqual(profile_build_mode(cfg), "off", env)
            self.assertFalse(cfg["memory"]["memory_enabled"] or cfg["memory"]["user_profile_enabled"], env)

    def test_operate_profile_logs_at_warning(self):
        import yaml
        cfg = yaml.safe_load(Path(os.environ["F9B_OPERATE_CONFIG"]).read_text(encoding="utf-8"))
        self.assertEqual(cfg["logging"]["level"], "WARNING")


if __name__ == "__main__":
    unittest.main(verbosity=2)
