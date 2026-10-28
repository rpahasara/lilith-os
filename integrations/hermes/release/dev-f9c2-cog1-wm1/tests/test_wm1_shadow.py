"""World Model lane in SHADOW (f293e72-f9c2-cog1-wm1): offline behaviour of the real DEV gateway + governed adapter.

    python -m unittest discover -s integrations/hermes/release/dev-f9c2-cog1-wm1/tests -p "test_*.py"

TEST_ONLY synthetic messages; every socket blocked; no model call; the cog1 HERMES_HOME tree is assembled from Git.
Each scenario runs in a fresh process (tests/_wm1_probe.py) so the router configuration is loaded as on the host.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

WM1 = Path(__file__).resolve().parents[1]
REPO = WM1.parents[3]
sys.path.insert(0, str(REPO / "integrations" / "hermes" / "overlays" / "dev-unified-cognition" / "tools"))

import assemble_dev_cognition  # noqa: E402
import importlib.util  # noqa: E402

_spec = importlib.util.spec_from_file_location(
    "prod_world_context", REPO / "integrations/hermes/home/variants/prod-lilith-01/lilith_router/world_context.py")
PROD_WM = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(PROD_WM)            # stdlib-only at import; detect_intent is pure

PROBE = Path(__file__).resolve().with_name("_wm1_probe.py")
COG1_ROUTER = REPO / "integrations" / "hermes" / "home" / "variants" / "dev-f9c2" / "router.yaml"
WM1_ROUTER = WM1 / "home" / "router.yaml"
CANARY = "TEST_ONLY_SHADOW_CANARY_3W"
MESSAGES = [
    f"TEST_ONLY what do you believe about application 14? {CANARY}",
    f"TEST_ONLY what is pending right now? {CANARY}",
    f"TEST_ONLY create a follow-up draft for application 14 {CANARY}",
    f"TEST_ONLY which goal has priority? {CANARY}",
    f"TEST_ONLY what are my options for application 14? {CANARY}",
    f"TEST_ONLY make a plan to follow up on application 14 {CANARY}",
    f"TEST_ONLY is it okay to share my salary with the recruiter? {CANARY}",
    f"TEST_ONLY hey how are you {CANARY}",
    f"TEST_ONLY why is my kubernetes pod pending? {CANARY}",
]
MEMORY_MODULES = {"lilith_router.memory_store", "lilith_router.memory_v2", "lilith_router.canonical_authority",
                  "lilith_router.canonical_contracts", "lilith_router.privacy_governance",
                  "lilith_router.learning_store", "lilith_router.learning_v2", "lilith_router.learning_worker"}
COGNITIVE_RECORD_KEYS = {"platform", "chat_id", "lane", "cognitive_mode", "intent", "msg_chars", "msg_lines"}

_TMP = tempfile.TemporaryDirectory(prefix="wm1-shadow-", ignore_cleanup_errors=True)
TMP = Path(_TMP.name)


def tearDownModule():
    _TMP.cleanup()


def probe(name: str, router: Path, messages=MESSAGES, platform="lilith_os") -> dict:
    home = TMP / name / "hermes-home"
    assert assemble_dev_cognition.assemble(home) == []
    log = TMP / name / "decisions.log"
    text = router.read_text(encoding="utf-8").replace(
        "/home/lilith/.hermes-dev/logs/lilith-router-decisions.log", log.as_posix())
    scenario = TMP / name / "scenario.json"
    scenario.write_text(json.dumps({"router_yaml": text, "messages": list(messages), "log_path": str(log),
                                    "platform": platform}), encoding="utf-8")
    out = subprocess.run([sys.executable, "-B", str(PROBE), str(home), str(scenario)], check=True,
                         cwd=home.parent, capture_output=True, text=True, timeout=120)
    result = json.loads(out.stdout)
    assert result["config"]["enabled"] is True, result["config"]   # the router configuration really loaded
    return result


class WorldModelShadowTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base = probe("cog1", COG1_ROUTER)
        cls.wm1 = probe("wm1", WM1_ROUTER)

    def test_the_lane_is_on_in_shadow_for_lilith_os_only(self):
        self.assertEqual(self.wm1["config"], {"enabled": True, "mode": "shadow", "cognitive_enabled": True,
                                              "cognitive_mode": "shadow", "cognitive_channels": ["lilith_os"]})
        self.assertFalse(self.base["config"]["cognitive_enabled"])

    def test_user_visible_routing_is_unchanged(self):
        self.assertEqual(self.wm1["results"], self.base["results"])
        self.assertTrue(all(r is None for r in self.wm1["results"]))

    def test_no_core_api_read_no_write_no_network(self):
        for run in (self.base, self.wm1):
            self.assertEqual(run["socket_attempts"], [])
            self.assertEqual({k: run["adapter"][k] for k in ("reads", "reads_refused", "reads_skipped_breaker",
                                                              "writes_refused")},
                             {"reads": 0, "reads_refused": 0, "reads_skipped_breaker": 0, "writes_refused": 0})
            self.assertTrue(run["adapter"]["legacy_loaded"])

    def test_the_only_new_output_is_content_free_cognitive_records(self):
        base, wm1 = self.base["log"], self.wm1["log"]
        cognitive = [r for r in wm1 if r.get("lane") == "cognitive"]
        self.assertEqual([r for r in wm1 if r.get("lane") != "cognitive"], base)   # routing records unchanged
        expected = [m for m in MESSAGES if PROD_WM.detect_intent(m)["any"]]   # the recovered PROD detector decides
        self.assertEqual(len(cognitive), len(expected))
        self.assertGreater(len(expected), 0)
        for record in cognitive:
            self.assertEqual(set(record), COGNITIVE_RECORD_KEYS)
            self.assertEqual(record["cognitive_mode"], "shadow")
            self.assertEqual(set(record["intent"]), {"belief", "pending", "draft", "example_only", "app_id"})
            self.assertIn(record["intent"]["app_id"], (None, "14"))
        raw = json.dumps(wm1)
        self.assertNotIn(CANARY, raw)
        self.assertNotIn("kubernetes", raw)
        self.assertNotIn("salary", raw)

    def test_no_other_lane_and_no_canonical_memory_module_runs(self):
        self.assertFalse({r.get("lane") for r in self.wm1["log"]} - {None, "cognitive"})
        for run in (self.base, self.wm1):
            self.assertFalse(set(run["modules"]) & MEMORY_MODULES)
            for lane in ("planning", "ethics", "reasoning", "workspace", "motivation"):
                self.assertNotIn(f"lilith_router.{lane}", run["modules"])

    def test_nothing_under_hermes_home_changes_except_the_probe_config(self):
        for run in (self.base, self.wm1):
            self.assertEqual(run["changed_files"], [])

    def test_other_platforms_are_not_observed(self):
        other = probe("wm1-telegram", WM1_ROUTER, messages=MESSAGES[:3], platform="telegram")
        self.assertFalse([r for r in other["log"] if r.get("lane") == "cognitive"])

    def test_reverting_the_router_restores_the_lanes_off_behaviour(self):
        reverted = probe("reverted", COG1_ROUTER)
        self.assertEqual(reverted["results"], self.base["results"])
        self.assertEqual(reverted["log"], self.base["log"])


if __name__ == "__main__":
    unittest.main()
