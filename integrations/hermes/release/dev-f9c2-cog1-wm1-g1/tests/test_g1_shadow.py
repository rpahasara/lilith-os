"""World Model + Goals lanes in SHADOW (f293e72-f9c2-cog1-wm1-g1): offline behaviour of the real DEV gateway + adapter.

    python -m unittest discover -s integrations/hermes/release/dev-f9c2-cog1-wm1-g1/tests -p "test_*.py"

TEST_ONLY synthetic messages; every socket blocked; no model call; the cog1 HERMES_HOME tree is assembled from Git.
Each scenario runs in a fresh process (tests/_g1_probe.py) so the router configuration is loaded as on the host. The
baseline is the installed wm1 router (World Model shadow, Goals off).
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

G1 = Path(__file__).resolve().parents[1]
REPO = G1.parents[3]
sys.path.insert(0, str(REPO / "integrations" / "hermes" / "overlays" / "dev-unified-cognition" / "tools"))

import assemble_dev_cognition  # noqa: E402

_spec = importlib.util.spec_from_file_location(
    "prod_world_context", REPO / "integrations/hermes/home/variants/prod-lilith-01/lilith_router/world_context.py")
PROD_WM = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(PROD_WM)            # stdlib-only at import; detect_intent / detect_goal_intent are pure

PROBE = Path(__file__).resolve().with_name("_g1_probe.py")
WM1_ROUTER = REPO / "integrations" / "hermes" / "release" / "dev-f9c2-cog1-wm1" / "home" / "router.yaml"
G1_ROUTER = G1 / "home" / "router.yaml"
CANARY = "TEST_ONLY_GOALS_SHADOW_CANARY_8G"
MESSAGES = [
    f"TEST_ONLY which goal has priority? {CANARY}",
    f"TEST_ONLY what are you trying to do right now? {CANARY}",
    f"TEST_ONLY what is blocked and why? {CANARY}",
    f"TEST_ONLY I want to follow up on application 14. Track that as a goal. {CANARY}",
    f"TEST_ONLY track application 21 as a goal {CANARY}",
    f"TEST_ONLY what do you believe about application 14? {CANARY}",
    f"TEST_ONLY what is pending right now? {CANARY}",
    f"TEST_ONLY create a follow-up draft for application 14 {CANARY}",
    f"TEST_ONLY what are my options for application 14? {CANARY}",
    f"TEST_ONLY is it okay to share my salary with the recruiter? {CANARY}",
    f"TEST_ONLY hey how are you {CANARY}",
    f"TEST_ONLY my goal for the weekend is to relax {CANARY}",
    f"TEST_ONLY why is my kubernetes pod pending? {CANARY}",
]
# Words that occur only in the messages (the subtype labels such as "priority" or "blocked" are fixed enum values).
SENSITIVE_WORDS = ("kubernetes", "salary", "recruiter", "weekend", "relax", "follow up", "trying", "track")
MEMORY_MODULES = {"lilith_router.memory_store", "lilith_router.memory_v2", "lilith_router.canonical_authority",
                  "lilith_router.canonical_contracts", "lilith_router.privacy_governance",
                  "lilith_router.learning_store", "lilith_router.learning_v2", "lilith_router.learning_worker"}
GOAL_RECORD_KEYS = {"platform", "chat_id", "lane", "goal_mode", "intent", "msg_chars", "msg_lines"}
GOAL_INTENT_KEYS = {"goal_query", "goal_create", "app_id", "subtype"}
SUBTYPES = {"general", "why_blocked", "blocked", "priority", "resume", "active"}

_TMP = tempfile.TemporaryDirectory(prefix="g1-shadow-", ignore_cleanup_errors=True)
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


class GoalsShadowTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base = probe("wm1", WM1_ROUTER)
        cls.g1 = probe("g1", G1_ROUTER)

    # -- positive ------------------------------------------------------------------------------------------------
    def test_both_lanes_are_on_in_shadow_for_lilith_os_only(self):
        self.assertEqual(self.g1["config"], {"enabled": True, "mode": "shadow", "cognitive_enabled": True,
                                             "cognitive_mode": "shadow", "cognitive_channels": ["lilith_os"],
                                             "goals_enabled": True, "goals_mode": "shadow"})
        self.assertEqual((self.base["config"]["goals_enabled"], self.base["config"]["cognitive_mode"]),
                         (False, "shadow"))

    def test_goal_turns_produce_one_content_free_shadow_record_each(self):
        goals = [r for r in self.g1["log"] if r.get("lane") == "goal"]
        expected = [m for m in MESSAGES if PROD_WM.detect_goal_intent(m)["any"]]   # the recovered PROD detector
        self.assertEqual(len(goals), len(expected))
        self.assertGreaterEqual(len(expected), 4)
        self.assertTrue(any(PROD_WM.detect_goal_intent(m)["goal_create"] for m in expected))   # a create is covered
        self.assertTrue(any(PROD_WM.detect_goal_intent(m)["goal_query"] for m in expected))    # and a query
        for record, message in zip(goals, expected):
            self.assertEqual(set(record), GOAL_RECORD_KEYS)
            self.assertEqual((record["lane"], record["goal_mode"], record["platform"]), ("goal", "shadow", "lilith_os"))
            self.assertEqual(set(record["intent"]), GOAL_INTENT_KEYS)
            self.assertIn(record["intent"]["subtype"], SUBTYPES)
            self.assertIn(record["intent"]["app_id"], (None, "14", "21"))
            self.assertEqual(record["msg_chars"], len(message))

    # -- negative: no Core API, no write, no model, no other lane -------------------------------------------------
    def test_user_visible_routing_is_unchanged(self):
        self.assertEqual(self.g1["results"], self.base["results"])
        self.assertTrue(all(r is None for r in self.g1["results"]))

    def test_no_core_api_read_no_write_no_network(self):
        # Goals shadow never calls /os/goals or /os/goals/focus, so the Core API cannot create the goal schema or
        # write goal_trace; goal creation is not even attempted (writes_refused stays 0).
        for run in (self.base, self.g1):
            self.assertEqual(run["socket_attempts"], [])
            self.assertEqual({k: run["adapter"][k] for k in ("reads", "reads_refused", "reads_skipped_breaker",
                                                              "writes_refused")},
                             {"reads": 0, "reads_refused": 0, "reads_skipped_breaker": 0, "writes_refused": 0})
            self.assertTrue(run["adapter"]["legacy_loaded"])

    def test_world_model_shadow_records_and_routing_records_are_unchanged(self):
        self.assertEqual([r for r in self.g1["log"] if r.get("lane") != "goal"], self.base["log"])
        self.assertFalse([r for r in self.base["log"] if r.get("lane") == "goal"])

    def test_no_other_lane_and_no_canonical_memory_module_runs(self):
        self.assertFalse({r.get("lane") for r in self.g1["log"]} - {None, "cognitive", "goal"})
        for run in (self.base, self.g1):
            self.assertFalse(set(run["modules"]) & MEMORY_MODULES)
            for lane in ("planning", "ethics", "reasoning", "workspace", "motivation"):
                self.assertNotIn(f"lilith_router.{lane}", run["modules"])
        self.assertEqual(self.g1["modules"], self.base["modules"])

    def test_nothing_under_hermes_home_changes_except_the_probe_config(self):
        for run in (self.base, self.g1):
            self.assertEqual(run["changed_files"], [])

    # -- privacy -------------------------------------------------------------------------------------------------
    def test_decision_log_holds_metadata_only_never_conversation_text(self):
        raw = json.dumps(self.g1["log"])
        self.assertNotIn(CANARY, raw)
        self.assertNotIn("TEST_ONLY", raw)
        for word in SENSITIVE_WORDS:
            self.assertNotIn(word, raw.lower())
        for record in self.g1["log"]:
            for key, value in record.items():
                if isinstance(value, str):
                    self.assertLessEqual(len(value), 40, (key, value))   # ids, lane names, modes: never text

    def test_other_platforms_are_not_observed(self):
        other = probe("g1-telegram", G1_ROUTER, messages=MESSAGES[:5], platform="telegram")
        self.assertFalse([r for r in other["log"] if r.get("lane") in ("goal", "cognitive")])
        self.assertEqual(other["adapter"]["reads"], 0)

    # -- rollback ------------------------------------------------------------------------------------------------
    def test_reverting_the_router_restores_the_wm1_behaviour(self):
        reverted = probe("reverted", WM1_ROUTER)
        self.assertEqual(reverted["results"], self.base["results"])
        self.assertEqual(reverted["log"], self.base["log"])


if __name__ == "__main__":
    unittest.main()
