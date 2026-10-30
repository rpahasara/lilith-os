"""World Model shadow + Goals LIVE (f293e72-f9c2-cog1-wm1-g2): offline gateway behaviour vs g1. TEST_ONLY.

    python -m unittest discover -s integrations/hermes/release/dev-f9c2-cog1-wm1-g2/tests -p "test_*.py"

The real DEV gateway and governed adapter on an assembled cog1 HERMES_HOME, in a fresh process (tests/_g2_probe.py)
with every socket blocked, so a live goal read reaches the adapter but never a network. Grounding against the real
Core API is covered by test_g2_core_api_compat.py; this file covers routing scope and privacy.
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

G2 = Path(__file__).resolve().parents[1]
REPO = G2.parents[3]
sys.path.insert(0, str(REPO / "integrations" / "hermes" / "overlays" / "dev-unified-cognition" / "tools"))

import assemble_dev_cognition  # noqa: E402

_spec = importlib.util.spec_from_file_location(
    "prod_world_context", REPO / "integrations/hermes/home/variants/prod-lilith-01/lilith_router/world_context.py")
PROD_WM = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(PROD_WM)

PROBE = Path(__file__).resolve().with_name("_g2_probe.py")
G1_ROUTER = REPO / "integrations" / "hermes" / "release" / "dev-f9c2-cog1-wm1-g1" / "home" / "router.yaml"
G2_ROUTER = G2 / "home" / "router.yaml"
CANARY = "TEST_ONLY_GOALS_LIVE_CANARY_9L"
GOAL_MESSAGES = [f"TEST_ONLY which goal has priority? {CANARY}", f"TEST_ONLY what is blocked and why? {CANARY}"]
CREATE_MESSAGE = f"TEST_ONLY track application 21 as a goal {CANARY}"
OTHER_MESSAGES = [
    f"TEST_ONLY what do you believe about application 14? {CANARY}",
    f"TEST_ONLY what is pending right now? {CANARY}",
    f"TEST_ONLY is it okay to share my salary with the recruiter? {CANARY}",
    f"TEST_ONLY hey how are you {CANARY}",
    f"TEST_ONLY why is my kubernetes pod pending? {CANARY}",
]
MESSAGES = GOAL_MESSAGES + [CREATE_MESSAGE] + OTHER_MESSAGES
MEMORY_MODULES = {"lilith_router.memory_store", "lilith_router.memory_v2", "lilith_router.canonical_authority",
                  "lilith_router.canonical_contracts", "lilith_router.privacy_governance",
                  "lilith_router.learning_store", "lilith_router.learning_v2", "lilith_router.learning_worker"}

_TMP = tempfile.TemporaryDirectory(prefix="g2-live-", ignore_cleanup_errors=True)
TMP = Path(_TMP.name)


def tearDownModule():
    _TMP.cleanup()


def probe(name: str, router: Path, messages, platform="lilith_os") -> dict:
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
    assert result["config"]["enabled"] is True, result["config"]
    return result


class GoalsLiveScopeTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.g1_other = probe("g1-other", G1_ROUTER, OTHER_MESSAGES)
        cls.g2_other = probe("g2-other", G2_ROUTER, OTHER_MESSAGES)
        cls.g2_goal = probe("g2-goal", G2_ROUTER, GOAL_MESSAGES)
        cls.g2_create = probe("g2-create", G2_ROUTER, [CREATE_MESSAGE])

    def test_only_goal_turns_change_non_goal_routing_and_logs_are_g1s(self):
        self.assertTrue(all(not PROD_WM.detect_goal_intent(m)["any"] for m in OTHER_MESSAGES))
        self.assertEqual(self.g2_other["results"], self.g1_other["results"])
        self.assertEqual(self.g2_other["log"], self.g1_other["log"])
        self.assertEqual(self.g2_other["adapter"]["reads"] + self.g2_other["adapter"]["reads_skipped_breaker"], 0)

    def test_goal_turns_are_live_goal_turns_on_lilith_os(self):
        modes = [(r or {}).get("mode") for r in self.g2_goal["results"]]
        self.assertEqual(modes, ["goal", "goal"])
        goal = [r for r in self.g2_goal["log"] if r.get("lane") == "goal"]
        self.assertEqual([r["goal_mode"] for r in goal], ["live", "live"])
        for r in goal:
            self.assertEqual(set(r), {"platform", "chat_id", "lane", "goal_mode", "intent", "msg_chars", "msg_lines"})
        # sockets blocked: the adapter tried only allowlisted goal reads, refused none, and wrote nothing
        a = self.g2_goal["adapter"]
        self.assertEqual((a["reads_refused"], a["writes_refused"]), (0, 0))
        self.assertGreater(a["reads"] + a["reads_skipped_breaker"], 0)
        self.assertEqual(self.g2_goal["socket_attempts"] and all("8765" in s for s in self.g2_goal["socket_attempts"]), True)
        for r in self.g2_goal["results"]:
            self.assertIn("temporarily unavailable", r["combined_ephemeral"])   # honest when the store is unreachable

    def test_goal_creation_is_never_sent(self):
        a = self.g2_create["adapter"]
        self.assertEqual(a["writes_refused"], 1)                             # POST /os/goals refused by the adapter
        self.assertFalse(a["writes_enabled"])
        self.assertIn("could not track the goal", self.g2_create["results"][0]["combined_ephemeral"])

    def test_no_message_text_in_the_decision_log(self):
        raw = json.dumps(self.g2_goal["log"] + self.g2_create["log"] + self.g2_other["log"])
        for text in (CANARY, "TEST_ONLY", "which goal", "track application", "salary", "kubernetes"):
            self.assertNotIn(text, raw)

    def test_no_other_lane_or_memory_module_and_no_home_change(self):
        for run in (self.g2_goal, self.g2_create, self.g2_other):
            self.assertFalse({r.get("lane") for r in run["log"]} - {None, "cognitive", "goal"})
            self.assertFalse(set(run["modules"]) & MEMORY_MODULES)
            for lane in ("planning", "ethics", "reasoning", "workspace", "motivation"):
                self.assertNotIn(f"lilith_router.{lane}", run["modules"])
            self.assertEqual(run["changed_files"], [])

    def test_other_platforms_are_not_observed(self):
        other = probe("g2-telegram", G2_ROUTER, MESSAGES[:3], platform="telegram")
        self.assertFalse([r for r in other["log"] if r.get("lane") in ("goal", "cognitive")])
        self.assertEqual(other["adapter"]["reads"] + other["adapter"]["reads_skipped_breaker"], 0)
        self.assertEqual(other["socket_attempts"], [])

    def test_reverting_the_router_restores_g1_goal_shadow(self):
        reverted = probe("reverted", G1_ROUTER, GOAL_MESSAGES)
        self.assertEqual(reverted["results"], [None, None])
        self.assertEqual([r["goal_mode"] for r in reverted["log"] if r.get("lane") == "goal"], ["shadow", "shadow"])
        self.assertEqual(reverted["adapter"]["reads"] + reverted["adapter"]["reads_skipped_breaker"], 0)


if __name__ == "__main__":
    unittest.main()
