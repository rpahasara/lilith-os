"""World Model + Goals + Reasoning in SHADOW (f293e72-f9c2-cog1-wm1-g1-r1): offline behaviour of the real gateway + adapter.

    python -m unittest discover -s integrations/hermes/release/dev-f9c2-cog1-wm1-g1-r1/tests -p "test_*.py"

TEST_ONLY synthetic messages; every socket blocked; no model call; the cog1 HERMES_HOME tree is assembled from Git. Each
scenario runs in a fresh process (tests/_r1_probe.py) so the router configuration is loaded as on the host. The baseline
is the installed g1 router (World Model and Goals shadow, Reasoning off).
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

R1 = Path(__file__).resolve().parents[1]
REPO = R1.parents[3]
sys.path.insert(0, str(REPO / "integrations" / "hermes" / "overlays" / "dev-unified-cognition" / "tools"))

import assemble_dev_cognition  # noqa: E402

_spec = importlib.util.spec_from_file_location(
    "prod_world_context", REPO / "integrations/hermes/home/variants/prod-lilith-01/lilith_router/world_context.py")
PROD_WM = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(PROD_WM)            # stdlib-only at import; the detectors are pure

PROBE = Path(__file__).resolve().with_name("_r1_probe.py")
G1_ROUTER = REPO / "integrations" / "hermes" / "release" / "dev-f9c2-cog1-wm1-g1" / "home" / "router.yaml"
R1_ROUTER = R1 / "home" / "router.yaml"
CANARY = "TEST_ONLY_REASONING_SHADOW_CANARY_9R"
REASONING = {
    f"TEST_ONLY why can't you send the follow up for application 14? {CANARY}": ("BLOCKER_ANALYSIS", "blocker", "14"),
    f"TEST_ONLY what are my options for application 14? {CANARY}": ("OPTION_GENERATION", "options", "14"),
    f"TEST_ONLY what information is missing to resolve this? {CANARY}": ("UNCERTAINTY_ANALYSIS", "uncertainty", None),
    f"TEST_ONLY how confident are you about that? {CANARY}": ("UNCERTAINTY_ANALYSIS", "uncertainty", None),
    f"TEST_ONLY analyze what this rejection means {CANARY}": ("FACTUAL_INTERPRETATION", "analyze", None),
}
YIELDS = [                                   # precedence: another accepted lane owns these turns
    f"TEST_ONLY which goal has priority? {CANARY}",
    f"TEST_ONLY what is blocked and why? {CANARY}",
    f"TEST_ONLY track application 21 as a goal {CANARY}",
    f"TEST_ONLY what is pending right now? {CANARY}",
    f"TEST_ONLY create a follow-up draft for application 14 {CANARY}",
]
UNRELATED = [
    f"TEST_ONLY what do you believe about application 14? {CANARY}",
    f"TEST_ONLY hey how are you {CANARY}",
    f"TEST_ONLY my goal for the weekend is to relax {CANARY}",
    f"TEST_ONLY why is my kubernetes pod pending? {CANARY}",
]
# Known over-matches of the recovered detector, measured here so they stay visible. Harmless in shadow (one record); a
# blocker for Reasoning LIVE, which would answer these with a tool-less reasoning call. The detector is NOT changed.
OVER_MATCHES = [
    "TEST_ONLY what next on the playlist?",
    "TEST_ONLY the next step is to feed the cat",
    "TEST_ONLY I am not sure what to cook tonight",
    "TEST_ONLY the song title is unknown",
    "TEST_ONLY please evaluate this python expression",
]
MESSAGES = list(REASONING) + YIELDS + UNRELATED
SENSITIVE_WORDS = ("kubernetes", "weekend", "relax", "rejection", "follow up", "track", "confident", "missing")
MEMORY_MODULES = {"lilith_router.memory_store", "lilith_router.memory_v2", "lilith_router.canonical_authority",
                  "lilith_router.canonical_contracts", "lilith_router.privacy_governance",
                  "lilith_router.learning_store", "lilith_router.learning_v2", "lilith_router.learning_worker"}
RECORD_KEYS = {"platform", "chat_id", "lane", "reasoning_mode", "intent", "trace", "msg_chars", "msg_lines"}

_TMP = tempfile.TemporaryDirectory(prefix="r1-shadow-", ignore_cleanup_errors=True)
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


class ReasoningShadowTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base = probe("g1", G1_ROUTER)
        cls.r1 = probe("r1", R1_ROUTER)

    # -- positive ------------------------------------------------------------------------------------------------
    def test_three_lanes_are_on_in_shadow_for_lilith_os_only(self):
        self.assertEqual(self.r1["config"], {
            "enabled": True, "mode": "shadow", "cognitive_enabled": True, "cognitive_mode": "shadow",
            "cognitive_channels": ["lilith_os"], "goals_enabled": True, "goals_mode": "shadow",
            "reasoning_enabled": True, "reasoning_mode": "shadow"})
        self.assertEqual((self.base["config"]["reasoning_enabled"], self.base["config"]["goals_mode"]), (False, "shadow"))

    def test_each_analytic_turn_gives_one_content_free_shadow_record_with_the_exact_intent(self):
        records = [r for r in self.r1["log"] if r.get("lane") == "reasoning"]
        self.assertEqual(len(records), len(REASONING))
        for record, (message, (mode, subtype, app_id)) in zip(records, REASONING.items()):
            self.assertEqual(set(record), RECORD_KEYS)
            self.assertEqual((record["reasoning_mode"], record["platform"], record["trace"]), ("shadow", "lilith_os", None))
            self.assertEqual(record["intent"], {"mode": mode, "subtype": subtype, "app_id": app_id})
            self.assertEqual(record["msg_chars"], len(message))

    def test_reasoning_yields_to_every_accepted_lane(self):
        for message in YIELDS + UNRELATED:
            with self.subTest(message=message):
                self.assertFalse(PROD_WM.detect_reasoning_intent(message)["any"])

    def test_detector_over_matches_are_recorded_as_a_known_limit(self):
        self.assertEqual([PROD_WM.detect_reasoning_intent(m)["any"] for m in OVER_MATCHES], [True] * len(OVER_MATCHES))

    # -- negative: no Core API, no write, no model, no other lane -------------------------------------------------
    def test_user_visible_routing_is_unchanged(self):
        self.assertEqual(self.r1["results"], self.base["results"])
        self.assertTrue(all(r is None for r in self.r1["results"]))

    def test_no_core_api_read_no_write_no_network(self):
        for run in (self.base, self.r1):
            self.assertEqual(run["socket_attempts"], [])
            self.assertEqual({k: run["adapter"][k] for k in ("reads", "reads_refused", "reads_skipped_breaker",
                                                              "writes_refused")},
                             {"reads": 0, "reads_refused": 0, "reads_skipped_breaker": 0, "writes_refused": 0})

    def test_world_model_goals_and_routing_records_are_unchanged(self):
        self.assertEqual([r for r in self.r1["log"] if r.get("lane") != "reasoning"], self.base["log"])

    def test_the_reasoning_engine_and_every_later_lane_are_not_even_imported(self):
        self.assertFalse({r.get("lane") for r in self.r1["log"]} - {None, "cognitive", "goal", "reasoning"})
        for run in (self.base, self.r1):
            self.assertFalse(set(run["modules"]) & MEMORY_MODULES)
            for lane in ("planning", "ethics", "reasoning", "workspace", "motivation"):
                self.assertNotIn(f"lilith_router.{lane}", run["modules"])
        self.assertEqual(self.r1["modules"], self.base["modules"])

    def test_nothing_under_hermes_home_changes(self):
        self.assertEqual(self.r1["changed_files"], [])

    # -- privacy -------------------------------------------------------------------------------------------------
    def test_decision_log_holds_metadata_only_never_conversation_text(self):
        raw = json.dumps(self.r1["log"])
        self.assertNotIn(CANARY, raw)
        self.assertNotIn("TEST_ONLY", raw)
        for word in SENSITIVE_WORDS:
            self.assertNotIn(word, raw.lower())
        for record in [r for r in self.r1["log"] if r.get("lane") == "reasoning"]:
            for key, value in record.items():
                if isinstance(value, str):
                    self.assertLessEqual(len(value), 40, (key, value))

    def test_other_platforms_are_not_observed(self):
        other = probe("r1-telegram", R1_ROUTER, messages=list(REASONING), platform="telegram")
        self.assertFalse([r for r in other["log"] if r.get("lane") == "reasoning"])
        self.assertEqual(other["adapter"]["reads"], 0)

    # -- rollback ------------------------------------------------------------------------------------------------
    def test_reverting_the_router_restores_the_g1_behaviour(self):
        reverted = probe("reverted", G1_ROUTER)
        self.assertEqual((reverted["results"], reverted["log"]), (self.base["results"], self.base["log"]))


if __name__ == "__main__":
    unittest.main()
