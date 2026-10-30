"""Regressions for the candidate adapter beyond the held-out corpus (NOT IN ANY RELEASE). TEST_ONLY; no network.

    python -m unittest discover -s integrations/hermes/overlays/dev-goals-hardening/tests -p "test_goals_hardening_regressions.py"

The pinned sets are measurements of the candidate as it stands. A set that names a defect is a finding, not an approved behaviour.
"""

from __future__ import annotations

import shutil
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
REPO = HERE.parents[3]
sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_goals_hardening_overlay import BASE_ADAPTER, CANDIDATE, HELD_OUT_OTHER, load  # noqa: E402

NEGATED_CREATES = [
    "don't track application 12 as a goal",
    "do not create a goal for application 8",
    "never add this as a goal",
    "should I make a goal for application 2?",
    "how do I add a goal?",
]
SPELLING = [
    "WHICH GOAL HAS PRIORITY?",
    "which goal has priority",
    "what’s the top goal?",
    "what is the\ngoal list?",
]
CAREER_READ_ROUTES = ["track application 21 as a goal", "add this as a goal"]


class Regressions(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(prefix="goal-reg-", ignore_cleanup_errors=True)
        directory = Path(cls.tmp.name)
        cls.base = load(BASE_ADAPTER, "base_reg", directory)
        cls.cand = load(CANDIDATE, "cand_reg", directory)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_measure_negated_creates(self):
        cand = sorted(m for m in NEGATED_CREATES if self.cand.detect_goal_intent(m)["goal_create"])
        base = sorted(m for m in NEGATED_CREATES if self.base.detect_goal_intent(m)["goal_create"])
        print("\nREG negated_as_create candidate", cand, "deployed", base)
        self.assertEqual(cand, NEGATED_AS_CREATE)
        self.assertLessEqual(len(cand), len(base))

    def test_spelling_variants_still_reach_the_goal_lane(self):
        missed = [m for m in SPELLING if not self.cand.detect_goal_intent(m)["goal_query"]]
        print("\nREG spelling_missed", missed)
        self.assertEqual(missed, [])

    def test_messages_released_by_goals_reach_reasoning_only_as_measured(self):
        moved = sorted(m for m in HELD_OUT_OTHER if self.base.detect_goal_intent(m)["any"] and self.cand.detect_reasoning_intent(m)["any"])
        print("\nREG moved_to_reasoning", moved)
        self.assertEqual(moved, MOVED_TO_REASONING)

    def test_a_refused_create_makes_no_career_read_on_either_create_wording(self):
        for message in CAREER_READ_ROUTES:
            paths = []
            legacy = self.cand._LEGACY
            real = legacy._get_json
            legacy._get_json = lambda path, timeout=2.5: paths.append(path)
            token = self.cand._BUDGET.set([16])
            try:
                legacy.build_goal_grounding(message, "s", legacy.detect_goal_intent(message), do_write=True)
            finally:
                self.cand._BUDGET.reset(token)
                legacy._get_json = real
            self.assertEqual([p for p in paths if p.startswith("/career")], [], message)

    def test_a_goal_read_with_an_application_number_makes_no_career_read(self):
        paths = []
        legacy = self.cand._LEGACY
        real = legacy._get_json
        legacy._get_json = lambda path, timeout=2.5: paths.append(path)
        token = self.cand._BUDGET.set([16])
        try:
            message = "which goal covers application 14?"
            legacy.build_goal_grounding(message, "s", legacy.detect_goal_intent(message), do_write=False)
        finally:
            self.cand._BUDGET.reset(token)
            legacy._get_json = real
        self.assertEqual([p for p in paths if p.startswith("/career")], [])


# Finding: two negated wordings still look like creates. The deployed detector has 5 of 5. Not tuned here: the adapter refuses creates on DEV.
NEGATED_AS_CREATE = ["don't track application 12 as a goal", "never add this as a goal"]
MOVED_TO_REASONING = []

if __name__ == "__main__":
    unittest.main()
