"""World Model lane LIVE (f293e72-f9c2-cog1-wm2): offline behaviour of the real DEV gateway + governed adapter.

    python -m unittest discover -s integrations/hermes/release/dev-f9c2-cog1-wm2/tests -p "test_*.py"

TEST_ONLY synthetic messages and Core API fixtures; every socket blocked; no model call; the cog1 HERMES_HOME tree is
assembled from Git and run with the exact wm2 (and wm1) router.yaml. Each scenario runs in a fresh process
(tests/_wm2_probe.py), with a fake Core API standing in for 127.0.0.1:8765.

The G3 live test of the plan is two turns: a belief question about synthetic application 999 and a non-matching
control, against DEV's World Model, which F1 found empty. Those two turns are reproduced first.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

WM2 = Path(__file__).resolve().parents[1]
REPO = WM2.parents[3]
sys.path.insert(0, str(REPO / "integrations" / "hermes" / "overlays" / "dev-unified-cognition" / "tools"))

import assemble_dev_cognition  # noqa: E402
import importlib.util  # noqa: E402

_spec = importlib.util.spec_from_file_location(
    "prod_world_context", REPO / "integrations/hermes/home/variants/prod-lilith-01/lilith_router/world_context.py")
PROD_WM = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(PROD_WM)            # stdlib-only at import; detect_intent is pure

PROBE = Path(__file__).resolve().with_name("_wm2_probe.py")
WM1_ROUTER = REPO / "integrations" / "hermes" / "release" / "dev-f9c2-cog1-wm1" / "home" / "router.yaml"
WM2_ROUTER = WM2 / "home" / "router.yaml"
CANARY = "TEST_ONLY_LIVE_CANARY_8M"
BELIEF_CANARY = "TEST_ONLY_BELIEF_CANARY_2P"
G3_BELIEF = "TEST_ONLY what do you believe about application 999?"
G3_CONTROL = "TEST_ONLY hey how are you"
VARIED = [f"TEST_ONLY hey how are you {CANARY}", f"TEST_ONLY which goal has priority? {CANARY}",
          f"TEST_ONLY is it okay to share my salary with the recruiter? {CANARY}",
          f"TEST_ONLY make a plan to follow up on application 999 {CANARY}",
          f"TEST_ONLY what are my options for application 999? {CANARY}",
          f"TEST_ONLY why is my kubernetes pod pending? {CANARY}", f"TEST_ONLY thanks, that helps {CANARY}"]
PENDING = f"TEST_ONLY what is pending right now? {CANARY}"
DRAFT = f"TEST_ONLY create a follow-up draft for application 999 {CANARY}"
MEMORY_MODULES = {"lilith_router.memory_store", "lilith_router.memory_v2", "lilith_router.canonical_authority",
                  "lilith_router.canonical_contracts", "lilith_router.privacy_governance",
                  "lilith_router.learning_store", "lilith_router.learning_v2", "lilith_router.learning_worker"}
COGNITIVE_RECORD_KEYS = {"platform", "chat_id", "lane", "cognitive_mode", "intent", "msg_chars", "msg_lines"}
WORLD_999 = "/os/world?entity_type=career.application&entity_id=999"

# DEV as F1 found it (2026-10-28): world_belief present with 0 beliefs; 0 tasks; no drafts table.
EMPTY_WORLD = {"beliefs": [], "meta": {"total": 0, "by_lifecycle": {}, "by_epistemic": {}, "conflicted": 0,
                                       "stale": 0, "last_reconciled_at": None}}
DEV_EMPTY = {"/os/world": EMPTY_WORLD, "/os/tasks": {"tasks": []}, "/os/drafts": {"drafts": []}}


def _belief(i: int, value: str) -> dict:
    return {"key": f"career.application:999:p{i:02d}", "entity_type": "career.application", "entity_id": "999",
            "predicate": f"p{i:02d}", "value": value, "lifecycle_state": "ACTIVE", "epistemic_state": "OBSERVED",
            "confidence": {"value": 0.5, "tier": "medium", "basis": "test"},
            "provenance": [{"source_class": "TEST_ONLY", "source_id": "synthetic", "freshness": "fresh",
                            "origin_ref": "TEST_ONLY_ORIGIN_REF", "note": "TEST_ONLY_NOTE"}]}


# Explicitly synthetic application 999 (the F2 option (a) shape): more beliefs than shown, one long value.
SYNTHETIC_999 = {
    "/os/world": {"beliefs": [_belief(0, f"{BELIEF_CANARY} " + "x" * 300)]
                  + [_belief(i, f"TEST_ONLY value {i}") for i in range(1, 20)],
                  "meta": {"total": 20, "conflicted": 0, "stale": 0, "last_reconciled_at": "2026-10-28T00:00:00Z"}},
}

_TMP = tempfile.TemporaryDirectory(prefix="wm2-live-", ignore_cleanup_errors=True)
TMP = Path(_TMP.name)


def tearDownModule():
    _TMP.cleanup()


def probe(name: str, router: Path, messages, fixtures=None, platform="lilith_os", unavailable=False) -> dict:
    home = TMP / name / "hermes-home"
    assert assemble_dev_cognition.assemble(home) == []
    log = TMP / name / "decisions.log"
    text = router.read_text(encoding="utf-8").replace(
        "/home/lilith/.hermes-dev/logs/lilith-router-decisions.log", log.as_posix())
    scenario = TMP / name / "scenario.json"
    scenario.write_text(json.dumps({"router_yaml": text, "messages": list(messages), "log_path": str(log),
                                    "platform": platform, "fixtures": fixtures or {}, "unavailable": unavailable}),
                        encoding="utf-8")
    out = subprocess.run([sys.executable, "-B", str(PROBE), str(home), str(scenario)], check=True,
                         cwd=home.parent, capture_output=True, text=True, timeout=120)
    result = json.loads(out.stdout)
    assert result["config"]["enabled"] is True, result["config"]   # the router configuration really loaded
    assert result["socket_attempts"] == [], result["socket_attempts"]
    assert result["adapter"]["legacy_loaded"] is True, result["adapter"]
    return result


def cognitive(run: dict) -> list:
    return [r for r in run["log"] if r.get("lane") == "cognitive"]


class G3TurnsTest(unittest.TestCase):
    """The two planned live turns, against DEV's empty World Model."""

    @classmethod
    def setUpClass(cls):
        cls.wm2 = probe("g3-wm2", WM2_ROUTER, [G3_BELIEF, G3_CONTROL], DEV_EMPTY)
        cls.wm1 = probe("g3-wm1", WM1_ROUTER, [G3_BELIEF, G3_CONTROL], DEV_EMPTY)

    def test_the_lane_is_live_for_lilith_os_and_the_router_stays_in_shadow(self):
        self.assertEqual(self.wm2["config"], {"enabled": True, "mode": "shadow", "cognitive_enabled": True,
                                              "cognitive_mode": "live", "cognitive_channels": ["lilith_os"]})

    def test_the_messages_are_classified_as_planned(self):
        self.assertEqual(PROD_WM.detect_intent(G3_BELIEF), {"any": True, "draft": False, "pending": False,
                                                            "belief": True, "example_only": False, "app_id": "999"})
        self.assertFalse(PROD_WM.detect_intent(G3_CONTROL)["any"])

    def test_belief_turn_makes_exactly_one_world_read_and_no_write(self):
        self.assertEqual(self.wm2["calls"][0], [{"method": "GET", "url": WORLD_999, "data": False}])
        self.assertEqual({k: self.wm2["adapter"][k] for k in ("reads", "reads_refused", "reads_skipped_breaker",
                                                               "writes_refused")},
                         {"reads": 1, "reads_refused": 0, "reads_skipped_breaker": 0, "writes_refused": 0})

    def test_belief_turn_grounding_is_the_policy_and_an_empty_belief_block(self):
        res = self.wm2["results"][0]
        self.assertEqual(set(res), {"turn_route", "combined_ephemeral", "force_rebuild", "mode"})
        self.assertEqual((res["mode"], res["turn_route"], res["force_rebuild"]),
                         ("cognitive", {"model": "dev-model"}, True))      # model and route unchanged
        self.assertEqual(res["combined_ephemeral"], "TEST_ONLY base\n\n" + PROD_WM.FALLBACK_POLICY + "\n\n"
                         "WORLD MODEL BELIEFS (durable, reconciled; showing 0 of 0; conflicted=0, stale=0, "
                         "last_reconciled=None):\n(no beliefs are recorded for this focus)")

    def test_control_turn_is_untouched(self):
        self.assertEqual(self.wm2["calls"][1], [])
        self.assertEqual(self.wm2["results"][1], self.wm1["results"][1])
        self.assertIsNone(self.wm2["results"][1])

    def test_one_live_record_flags_only(self):
        self.assertEqual(cognitive(self.wm2), [{"platform": "lilith_os", "chat_id": "probe-0", "lane": "cognitive",
                                               "cognitive_mode": "live",
                                               "intent": {"belief": True, "pending": False, "draft": False,
                                                          "example_only": False, "app_id": "999"},
                                               "msg_chars": len(G3_BELIEF), "msg_lines": 1}])
        # A grounded turn returns before the routing decision, so its routing record is replaced by the live one.
        self.assertEqual([r for r in self.wm2["log"] if r.get("lane") != "cognitive"],
                         [r for r in self.wm1["log"] if r.get("lane") != "cognitive" and r["chat_id"] != "probe-0"])

    def test_wm1_shadow_makes_no_read_for_the_same_turns(self):
        self.assertEqual(self.wm1["calls"], [[], []])
        self.assertEqual(self.wm1["results"], [None, None])

    def test_nothing_under_hermes_home_changes_and_no_memory_module_runs(self):
        self.assertEqual(self.wm2["changed_files"], [])
        self.assertFalse(set(self.wm2["modules"]) & MEMORY_MODULES)
        for lane in ("planning", "ethics", "reasoning", "workspace", "motivation"):
            self.assertNotIn(f"lilith_router.{lane}", self.wm2["modules"])


class LiveScopeTest(unittest.TestCase):
    def test_only_turns_the_prod_detector_matches_change(self):
        wm2 = probe("varied-wm2", WM2_ROUTER, VARIED, DEV_EMPTY)
        wm1 = probe("varied-wm1", WM1_ROUTER, VARIED, DEV_EMPTY)
        matched = [PROD_WM.detect_intent(m)["any"] for m in VARIED]
        self.assertIn(True, matched)
        self.assertIn(False, matched)
        for i, (m, hit) in enumerate(zip(VARIED, matched)):
            with self.subTest(message=m):
                if hit:     # even "why is my kubernetes pod pending?" is a pending-state question to the detector
                    self.assertEqual(wm2["results"][i]["mode"], "cognitive")
                    self.assertTrue(wm2["calls"][i])
                else:
                    self.assertEqual(wm2["results"][i], wm1["results"][i])
                    self.assertEqual(wm2["calls"][i], [])
        self.assertEqual(len(cognitive(wm2)), sum(matched))
        self.assertEqual({c["method"] for turn in wm2["calls"] for c in turn}, {"GET"})
        # "make a plan to follow up on application 999" is a draft request to the detector: the write is refused.
        drafts = [m for m in VARIED if PROD_WM.detect_intent(m)["draft"]]
        self.assertEqual(drafts, [VARIED[3]])
        self.assertEqual(wm2["adapter"]["writes_refused"], len(drafts))
        self.assertNotIn(CANARY, json.dumps(wm2["log"]))

    def test_synthetic_beliefs_are_capped_and_the_provenance_detail_is_dropped(self):
        run = probe("synthetic", WM2_ROUTER, [G3_BELIEF], SYNTHETIC_999)
        grounding = run["results"][0]["combined_ephemeral"]
        self.assertIn("showing 12 of 20", grounding)
        self.assertEqual(grounding.count("- career.application:999 · p"), 12)
        self.assertNotIn("p12 =", grounding)
        long_line = next(l for l in grounding.splitlines() if BELIEF_CANARY in l)
        self.assertIn(BELIEF_CANARY + " " + "x" * (117 - len(BELIEF_CANARY) - 1) + "...", long_line)
        self.assertNotIn("x" * 118, grounding)
        for hidden in ("TEST_ONLY_ORIGIN_REF", "TEST_ONLY_NOTE"):
            self.assertNotIn(hidden, grounding)
        self.assertIn("sources=TEST_ONLY:synthetic (fresh)", grounding)
        self.assertEqual(run["calls"], [[{"method": "GET", "url": WORLD_999, "data": False}]])
        self.assertNotIn(BELIEF_CANARY, json.dumps(run["log"]))           # grounding never reaches the log

    def test_pending_and_draft_turns_read_drafts_and_never_write(self):
        # Excluded from G3 (F2): on DEV, any /os/drafts read would create the empty drafts table.
        run = probe("pending-draft", WM2_ROUTER, [PENDING, DRAFT], DEV_EMPTY)
        self.assertEqual([c["url"] for c in run["calls"][0]], ["/os/tasks?limit=200", "/os/drafts?limit=200"])
        self.assertIn("/os/drafts?target_id=999", [c["url"] for c in run["calls"][1]])
        self.assertEqual({c["method"] for turn in run["calls"] for c in turn}, {"GET"})
        self.assertEqual(run["adapter"]["writes_refused"], 1)
        draft = run["results"][1]["combined_ephemeral"]
        self.assertIn("did not confirm it", draft)
        self.assertNotIn("DURABLE ACTION RESULT:", draft)
        self.assertNotIn("DURABLE ACTION RESULT (existing draft reused)", draft)
        self.assertNotIn(CANARY, json.dumps(run["log"]))

    def test_an_unavailable_core_api_is_reported_honestly(self):
        run = probe("unavailable", WM2_ROUTER, [G3_BELIEF, G3_BELIEF], DEV_EMPTY, unavailable=True)
        for res in run["results"]:
            self.assertIn("WORLD MODEL: temporarily unavailable", res["combined_ephemeral"])
        self.assertEqual(len(run["calls"][0]), 1)                  # one attempt, then the breaker
        self.assertEqual(run["calls"][1], [])
        self.assertEqual(run["adapter"]["reads_skipped_breaker"], 1)

    def test_other_platforms_are_not_grounded(self):
        run = probe("telegram", WM2_ROUTER, [G3_BELIEF, PENDING, DRAFT], DEV_EMPTY, platform="telegram")
        self.assertEqual(run["calls"], [[], [], []])
        self.assertFalse(cognitive(run))
        self.assertFalse([r for r in run["results"] if r and r.get("mode") == "cognitive"])

    def test_reverting_to_the_wm1_router_stops_every_read(self):
        run = probe("reverted", WM1_ROUTER, [G3_BELIEF, PENDING, DRAFT], DEV_EMPTY)
        self.assertEqual(run["calls"], [[], [], []])
        self.assertEqual({r["cognitive_mode"] for r in cognitive(run)}, {"shadow"})


if __name__ == "__main__":
    unittest.main()
