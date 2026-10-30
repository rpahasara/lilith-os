"""The counts-only Motivation trace. TEST_ONLY; no network."""
import difflib
import importlib.util
import json
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
REPO = HERE.parents[3]
BASE = REPO / "docs/architecture/slice-11/motivation.py"
OVERLAY = HERE / "lilith_router/motivation.py"


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


BLOCKED = [{"goalId": "g.test-only-secret", "lifecycleState": "BLOCKED", "isFocus": True, "userReferenced": True, "source": "USER_REQUESTED",
            "blockedBy": ["t.test-only-secret"], "targetApp": "14", "hardBlockerFailedTaskIds": ["t.test-only-secret"]}]


class Trace(unittest.TestCase):
    def snapshot(self, module):
        return module.build_snapshot(coherence=None, goal_completion=module.classify_goal_completion(BLOCKED, channel="lilith_os"), safety=None,
                                     raw_refs=None, channel="lilith_os", source_availability={}, partial=False)

    def test_only_the_two_trace_lines_differ(self):
        diff = [l for l in difflib.ndiff(BASE.read_text(encoding="utf-8").splitlines(), OVERLAY.read_text(encoding="utf-8").splitlines()) if l[:2] in ("- ", "+ ")]
        self.assertEqual(len(diff), 4, diff)
        self.assertTrue(all("related" in l or "resolutionCondition" in l for l in diff))

    def test_a_blocked_goal_reaches_the_record_as_a_count(self):
        base, cand = load(BASE, "mot_base"), load(OVERLAY, "mot_cand")
        self.assertIn("g.test-only-secret", json.dumps(base.build_trace(self.snapshot(base))))
        trace = cand.build_trace(self.snapshot(cand))
        raw = json.dumps(trace)
        for secret in ("g.test-only-secret", "t.test-only-secret", "blocker cleared", "application"):
            self.assertNotIn(secret, raw)
        drive = next(d for d in trace["per_drive"] if d["driveType"] == "GOAL_COMPLETION")
        self.assertEqual((drive["intensityClass"], drive["relatedGoalCount"], drive["resolutionConditionCount"]), ("CRITICAL", 1, 1))

    def test_two_snapshots_of_the_same_state_differ_only_in_turn_scoped_fields(self):
        cand = load(OVERLAY, "mot_cand2")
        first, second = (cand.build_trace(self.snapshot(cand)) for _ in range(2))
        volatile = {"correlation_id", "timestamp", "duration_ms"}
        self.assertEqual({k: v for k, v in first.items() if k not in volatile}, {k: v for k, v in second.items() if k not in volatile})
        self.assertNotEqual(first["correlation_id"], second["correlation_id"])


if __name__ == "__main__":
    unittest.main()
