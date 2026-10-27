"""F7 offline validation of the assembled DEV Hermes runtime. TEST_ONLY: synthetic inputs, no model calls, no network
beyond 127.0.0.1, no PROD/DEV access. Runs against a throwaway copy of hermes-home-dev.

Run (from dev-build-20261022):  venv\\Scripts\\python.exe tests\\test_f7_offline.py
"""

from __future__ import annotations

import asyncio
import json
import os
import shutil
import socket
import sys
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request
from pathlib import Path
from types import SimpleNamespace

BUILD = Path(__file__).resolve().parents[1]
HERMES_SRC = BUILD / "hermes-agent"
HOME_TEMPLATE = Path(os.environ.get("F7_HOME_TEMPLATE") or (BUILD / "hermes-home-dev"))   # override: negative control
GOOD_TOKEN = "TEST_ONLY-" + "a1" * 20          # 50 chars, synthetic

_TMP = tempfile.TemporaryDirectory(prefix="f7-hermes-home-")
HERMES_HOME = Path(_TMP.name) / "hermes-home-dev"
shutil.copytree(HOME_TEMPLATE, HERMES_HOME)
for key in [k for k in os.environ if k.startswith(("LILITH_OS_", "DISCORD", "TELEGRAM", "WHATSAPP", "GROQ", "OPENAI",
                                                     "ANTHROPIC", "OPENROUTER", "XAI", "HASS"))]:
    del os.environ[key]
os.environ["HERMES_HOME"] = str(HERMES_HOME)
os.environ["HOME"] = os.environ["USERPROFILE"] = str(Path(_TMP.name))   # no fallback to the real ~/.hermes
sys.path.insert(0, str(HERMES_SRC))
sys.path.insert(0, str(HERMES_HOME))                                      # as run.py's hook does
BEFORE = {p.relative_to(HERMES_HOME).as_posix() for p in HERMES_HOME.rglob("*")}
def venv_dists() -> list:
    import importlib.metadata as m
    return sorted(f"{d.metadata['Name'].lower()}=={d.version}" for d in m.distributions())


VENV_BEFORE = venv_dists()


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def non_loopback_ip() -> str | None:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("192.0.2.1", 9))                                    # TEST-NET, no packet is sent
            ip = s.getsockname()[0]
            return None if ip.startswith("127.") else ip
    except OSError:
        return None


class AdapterTests(unittest.TestCase):
    """The hardened lilith_os adapter, loaded through Hermes's real plugin discovery."""

    @classmethod
    def setUpClass(cls):
        from hermes_cli.plugins import discover_plugins
        from gateway.platform_registry import platform_registry
        from gateway.config import PlatformConfig

        discover_plugins(force=True)
        entry = platform_registry.get("lilith_os")
        assert entry is not None, "lilith_os plugin was not discovered from HERMES_HOME/plugins"
        cls.entry = entry
        cls.port = free_port()
        os.environ["LILITH_OS_PORT"] = str(cls.port)
        cls.adapter = entry.adapter_factory(PlatformConfig())
        cls.loop = asyncio.new_event_loop()
        threading.Thread(target=cls.loop.run_forever, daemon=True).start()

        async def fake_handle_message(event):                              # no gateway, no model
            await asyncio.sleep(0)
            await cls.adapter.send(event.source.chat_id, f"TEST_ONLY reply to: {event.text}",
                                   metadata={"notify": True})
        cls.adapter.handle_message = fake_handle_message
        cls.adapter._message_handler = object()
        ok = asyncio.run_coroutine_threadsafe(cls.adapter.connect(), cls.loop).result(10)
        assert ok, "adapter.connect() failed"

    @classmethod
    def tearDownClass(cls):
        asyncio.run_coroutine_threadsafe(cls.adapter.disconnect(), cls.loop).result(10)
        cls.loop.call_soon_threadsafe(cls.loop.stop)
        os.environ.pop("LILITH_OS_PORT", None)
        os.environ.pop("LILITH_OS_TOKEN", None)

    def post(self, body: bytes, token: str | None, host="127.0.0.1", content_length=None):
        req = urllib.request.Request(f"http://{host}:{self.port}/", data=body, method="POST",
                                     headers={"Content-Type": "application/json"})
        if token is not None:
            req.add_header("X-LILITH-OS-Token", token)
        if content_length is not None:
            req.add_header("Content-Length", str(content_length))
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                return resp.status, json.loads(resp.read())
        except urllib.error.HTTPError as exc:
            return exc.code, json.loads(exc.read() or b"{}")

    def body(self, **fields) -> bytes:
        return json.dumps({"message": "TEST_ONLY hello", "session": "lilith-os-test", **fields}).encode()

    def with_token(self, value):
        if value is None:
            os.environ.pop("LILITH_OS_TOKEN", None)
        else:
            os.environ["LILITH_OS_TOKEN"] = value

    def test_platform_registration_and_identity(self):
        self.assertEqual(self.adapter.host, "127.0.0.1")
        self.assertEqual(self.adapter._httpd.server_address[0], "127.0.0.1")
        self.assertTrue(self.adapter.authorization_is_upstream)
        self.assertEqual(self.entry.allow_all_env, "LILITH_OS_ALLOW_ALL_USERS")

    def test_missing_or_short_token_rejected(self):
        for value in (None, "", "short-token"):
            with self.subTest(token=value):
                self.with_token(value)
                self.assertEqual(self.post(self.body(), GOOD_TOKEN), (503, {"error": "console token not configured"}))

    def test_incorrect_or_absent_presented_token_rejected(self):
        self.with_token(GOOD_TOKEN)
        for presented in (None, "", GOOD_TOKEN[:-1] + "b", "x" * 50):
            with self.subTest(presented=presented):
                self.assertEqual(self.post(self.body(), presented), (401, {"error": "unauthorized"}))

    def test_correct_token_and_contract(self):
        self.with_token(GOOD_TOKEN)
        status, reply = self.post(self.body(), GOOD_TOKEN)
        self.assertEqual(status, 200)
        self.assertEqual(set(reply), {"reply", "state", "session"})
        self.assertEqual((reply["state"], reply["session"]), ("completed", "lilith-os-test"))
        self.assertEqual(reply["reply"], "TEST_ONLY reply to: TEST_ONLY hello")
        self.assertEqual(self.post(self.body(message=""), GOOD_TOKEN)[0], 400)
        self.assertEqual(self.post(b"not json", GOOD_TOKEN)[0], 400)

    def test_oversized_request_rejected(self):
        self.with_token(GOOD_TOKEN)
        big = self.body(message="x" * (70 * 1024))
        self.assertEqual(self.post(big, GOOD_TOKEN), (413, {"error": "request too large"}))

    def test_not_reachable_on_a_non_loopback_address(self):
        ip = non_loopback_ip()
        if ip is None:
            self.skipTest("no non-loopback IPv4 address on this machine")
        with socket.socket() as s:
            s.settimeout(2)
            self.assertNotEqual(s.connect_ex((ip, self.port)), 0)


TOOL_PROBE = r"""
import json, os, sys
sys.path.insert(0, sys.argv[1])
from hermes_cli.plugins import discover_plugins
discover_plugins(force=True)
from gateway.platform_registry import platform_registry
from model_tools import get_tool_definitions            # loads the tool registry first, as the gateway does
get_tool_definitions(enabled_toolsets=[], quiet_mode=True)
from hermes_cli.config import load_config
from hermes_cli.tools_config import _get_platform_tools
from agent.skill_utils import parse_config_string_list
cfg = load_config()
deny = parse_config_string_list((cfg.get("agent") or {}).get("disabled_toolsets")) or []
names = lambda en, dis: sorted(d["function"]["name"] for d in (get_tool_definitions(enabled_toolsets=en, disabled_toolsets=dis, quiet_mode=True) or []))
unpinned_cfg = dict(cfg); unpinned_cfg["platform_toolsets"] = {}
unpinned = sorted(_get_platform_tools(unpinned_cfg, "lilith_os"))
pinned = sorted(_get_platform_tools(cfg, "lilith_os"))
out = {"registered": platform_registry.is_registered("lilith_os"), "deny": deny,
       "unpinned_enabled": unpinned, "unpinned_tools": names(unpinned, None),
       "pinned_enabled": pinned, "pinned_tools_no_deny": names(pinned, None), "pinned_tools_with_deny": names(pinned, deny)}
os.environ["HERMES_KANBAN_TASK"] = "TEST_ONLY-task"
out["kanban_forced_with_deny"] = names(pinned, deny)
from toolsets import TOOLSETS
out["worst_case_no_deny"] = names(sorted(TOOLSETS), None)
out["worst_case_with_deny"] = names(sorted(TOOLSETS), deny)
print("@@" + json.dumps(out))
"""


class ToolResolutionTests(unittest.TestCase):
    """What tools a lilith_os turn actually gets under the DEV config (fresh process, plugin registration asserted)."""

    @classmethod
    def setUpClass(cls):
        import subprocess
        proc = subprocess.run([sys.executable, "-c", TOOL_PROBE, str(HERMES_SRC)], capture_output=True, text=True,
                              env=dict(os.environ), timeout=600)
        line = [l for l in proc.stdout.splitlines() if l.startswith("@@")]
        assert line, proc.stdout[-2000:] + proc.stderr[-2000:]
        cls.r = json.loads(line[-1][2:])
        from hermes_cli.config import load_config
        cls.config = load_config()

    def test_probe_ran_with_the_console_registered(self):
        self.assertTrue(self.r["registered"])

    def test_negative_control_worst_case_exposes_command_and_file_tools(self):
        self.assertTrue({"terminal", "write_file", "patch", "read_file"} <= set(self.r["worst_case_no_deny"]),
                        self.r["worst_case_no_deny"])

    def test_deny_list_leaves_no_tools_even_with_every_toolset_enabled(self):
        self.assertEqual(self.r["worst_case_with_deny"], [])

    def test_pinned_console_resolves_no_tools(self):
        print(f"\n  [info] pinned lilith_os toolsets: {self.r['pinned_enabled']}; "
              f"unpinned: {self.r['unpinned_enabled']}")
        self.assertEqual(self.r["pinned_tools_no_deny"], [])
        self.assertEqual(self.r["pinned_tools_with_deny"], [])
        self.assertEqual(self.r["kanban_forced_with_deny"], [])

    def test_dev_config_disables_background_writers(self):
        c = self.config
        self.assertFalse(c["memory"]["memory_enabled"])
        self.assertFalse(c["memory"]["user_profile_enabled"])
        self.assertEqual(c["memory"]["nudge_interval"], 0)
        self.assertEqual(c["skills"]["creation_nudge_interval"], 0)
        self.assertFalse(c["auxiliary"]["background_review"]["enabled"])
        self.assertFalse(c["curator"]["enabled"])
        self.assertFalse(c["kanban"]["dispatch_in_gateway"])
        self.assertFalse(c["cron"]["allow_agent_scheduling"])
        self.assertTrue(c["sessions"]["auto_prune"])
        self.assertEqual(c["sessions"]["retention_days"], 7)
        self.assertEqual((c["session_reset"]["mode"], c["session_reset"]["idle_minutes"]), ("idle", 1440))
        self.assertEqual(c["max_concurrent_sessions"], 4)
        self.assertFalse(c.get("mcp_servers"))
        self.assertEqual(c["plugins"]["enabled"], ["lilith_os"])
        self.assertFalse(c["security"]["allow_lazy_installs"])


class RouterTests(unittest.TestCase):
    """Router V2 with the import-only world_context stub and every cognitive lane off."""

    @classmethod
    def setUpClass(cls):
        from lilith_router import config as rconfig, gateway_integration as gi, world_context
        cls.rconfig, cls.gi, cls.world_context = rconfig, gi, world_context
        cls.router_yaml = HERMES_HOME / "lilith_router" / "router.yaml"
        cls.original_yaml = cls.router_yaml.read_text(encoding="utf-8")

    def tearDown(self):
        self.router_yaml.write_text(self.original_yaml, encoding="utf-8")

    def ctx(self, message, chat_id="lilith-os-test"):
        return SimpleNamespace(source=SimpleNamespace(platform=SimpleNamespace(value="lilith_os"), chat_id=chat_id),
                               session_key=f"agent:lilith_os:{chat_id}", message=message)

    def route(self, message, runner=None, cached_agent=None, **kw):
        return self.gi.route_turn(runner=runner or SimpleNamespace(), ctx=self.ctx(message, **kw), model="dev-model",
                                  runtime_kwargs={}, turn_route={"model": "dev-model"},
                                  combined_ephemeral="TEST_ONLY base", cached_agent=cached_agent)

    def set_yaml(self, **changes):
        import yaml
        data = yaml.safe_load(self.original_yaml)
        data.update(changes)
        self.router_yaml.write_text(yaml.safe_dump(data), encoding="utf-8")

    def test_imports_and_paths_are_dev(self):
        self.assertTrue(self.world_context.DEV_IMPORT_STUB)
        self.assertEqual(self.rconfig.CONFIG_PATH, HERMES_HOME / "lilith_router" / "router.yaml")
        cfg = self.rconfig.load()
        self.assertEqual((cfg.enabled, cfg.mode, cfg.live_channels), (True, "shadow", ["lilith_os"]))
        self.assertFalse(any([cfg.cognitive_enabled, cfg.goals_enabled, cfg.reasoning_enabled, cfg.workspace_enabled,
                              cfg.motivation_enabled, cfg.planning_enabled, cfg.ethics_enabled,
                              cfg.social_cognition_enabled, cfg.memory_consolidation_enabled]))
        self.assertFalse(cfg.canonical_ltm_is_enabled())
        self.assertEqual(cfg.resolved_log_path(), HERMES_HOME / "lilith_router" / "decisions.log")

    def test_shadow_mode_never_overrides_and_logs_no_message_text(self):
        for message in ("TEST_ONLY hey how are you 😊", "TEST_ONLY why is my kubernetes pod pending?"):
            self.assertIsNone(self.route(message))
        raw = (HERMES_HOME / "lilith_router" / "decisions.log").read_text(encoding="utf-8")
        last = json.loads(raw.splitlines()[-1])
        self.assertEqual((last["platform"], last["mode"], last["live"]), ("lilith_os", "technical", False))
        self.assertNotIn("preview", last)                                              # F9-A D-2
        self.assertEqual(last["msg_chars"], len("TEST_ONLY why is my kubernetes pod pending?"))
        self.assertNotIn("kubernetes", raw)

    def test_live_social_without_groq_credentials_fails_open(self):
        self.set_yaml(mode="live")
        runner = SimpleNamespace(_resolve_runtime_agent_kwargs_for_provider=lambda p: {"api_key": None})
        self.assertIsNone(self.route("TEST_ONLY hey how are you 😊", runner=runner))

    def test_live_social_with_synthetic_groq_runtime_routes_without_network(self):
        self.set_yaml(mode="live")
        runner = SimpleNamespace(
            _resolve_runtime_agent_kwargs_for_provider=lambda p: {"api_key": "TEST_ONLY-not-a-key"},
            _resolve_turn_agent_config=lambda message, model, rt: {"model": model, "provider": "groq"})
        res = self.route("TEST_ONLY hey how are you 😊", runner=runner)
        self.assertEqual(res["mode"], "social")
        self.assertEqual(res["turn_route"], {"model": "qwen/qwen3.8-27b", "provider": "groq"})
        self.assertIn("[conversation mode]", res["combined_ephemeral"])
        self.assertEqual(res["fallback_model"][0]["model"], "<DEV-MODEL-PENDING-OWNER-DECISION>")
        self.assertIsNone(self.route("TEST_ONLY why is my kubernetes pod pending?", runner=runner))   # native

    def test_enabling_a_lane_with_the_stub_fails_open(self):
        self.set_yaml(cognitive_enabled=True, cognitive_mode="live", cognitive_channels=["lilith_os"],
                      reasoning_enabled=True, reasoning_mode="live", planning_enabled=True, planning_mode="live")
        self.assertIsNone(self.route("TEST_ONLY what's pending for the recruiter follow-up?"))

    def test_enforce_reply_passes_through_outside_live_social(self):
        self.assertEqual(self.gi.enforce_reply("TEST_ONLY plain reply", self.ctx("TEST_ONLY hi")),
                         "TEST_ONLY plain reply")


class PersistenceInventory(unittest.TestCase):
    def test_zz_files_created_under_hermes_home(self):
        after = {p.relative_to(HERMES_HOME).as_posix() for p in HERMES_HOME.rglob("*")}
        created = sorted(after - BEFORE)
        print("\nFILES CREATED UNDER HERMES_HOME DURING THE OFFLINE TESTS:\n  " + "\n  ".join(created or ["(none)"]))
        real_home = Path(os.path.expanduser("~")) / ".hermes"
        self.assertFalse(real_home.exists(), f"something wrote to a fallback home {real_home}")


class ZZVenvImmutability(unittest.TestCase):
    def test_no_package_was_installed_during_the_run(self):
        added = sorted(set(venv_dists()) - set(VENV_BEFORE))
        self.assertEqual(added, [], f"lazy installs changed the venv: {added}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
