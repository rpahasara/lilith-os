"""Offline measurements behind REVIEW.md. TEST_ONLY; no network; nothing here is wired into a release.

    python -m unittest discover -s integrations/hermes/proposals/goals-hardening-v0.1 -p "test_*.py"
"""

from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO / "integrations" / "hermes" / "overlays" / "dev-unified-cognition" / "tools"))

import assemble_dev_cognition  # noqa: E402
import goal_detector_candidate as CAND  # noqa: E402

_spec = importlib.util.spec_from_file_location(
    "prod_world_context", REPO / "integrations/hermes/home/variants/prod-lilith-01/lilith_router/world_context.py")
PROD = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(PROD)

QUERIES = [
    "which goal has priority?", "what are your goals?", "what goals are active?", "what are you trying to do right now?",
    "what is blocked and why?", "why is the follow up on hold?", "what should you resume?", "what is your current focus?",
    "show my goals", "list the active goals", "any goals blocked?", "goal status please", "what are you working on?",
    "how many goals do I have?", "what takes priority here?",
]
CREATES = [
    "track application 21 as a goal", "I want to follow up on application 14. Track that as a goal.",
    "please set a goal for application 9", "add a goal to follow up on application 3", "track this as a goal",
    "create a goal for application 5", "can you make a goal for this?",
]
OTHER = [
    "my goal for the weekend is to relax", "that was a great goal by the striker", "my life goals are simple",
    "the goal of this function is to parse dates", "our team scored two goals last night", "goal setting is hard",
    "he could make a great goal from there", "I started running with a goal of 5 km", "we set out to reach our goal",
    "hey how are you", "why is my kubernetes pod pending?", "tell me a joke about goalkeepers",
]


class DetectorMeasurement(unittest.TestCase):
    def rates(self, fn):
        q = sum(fn(m)["goal_query"] or fn(m)["goal_create"] for m in QUERIES)
        c = sum(fn(m)["goal_create"] for m in CREATES)
        fp = [m for m in OTHER if fn(m)["any"]]
        fc = [m for m in OTHER + QUERIES if fn(m)["goal_create"]]
        return q, c, fp, fc

    def test_deployed_detector_over_matches_and_the_candidate_keeps_every_true_case(self):
        q0, c0, fp0, fc0 = self.rates(PROD.detect_goal_intent)
        q1, c1, fp1, fc1 = self.rates(CAND.classify)
        print(f"\nDEPLOYED queries {q0}/{len(QUERIES)} creates {c0}/{len(CREATES)} false_any {len(fp0)}/{len(OTHER)} false_create {len(fc0)}")
        print(f"CANDIDATE queries {q1}/{len(QUERIES)} creates {c1}/{len(CREATES)} false_any {len(fp1)}/{len(OTHER)} false_create {len(fc1)}")
        self.assertEqual((q0, c0), (len(QUERIES), len(CREATES)))
        self.assertGreaterEqual(len(fp0), 6)                 # the finding
        self.assertEqual((q1, c1), (len(QUERIES), len(CREATES)))   # no regression on this corpus
        self.assertEqual(fp1, [])
        self.assertEqual(fc1, [])

    def test_the_accepted_window_message_still_classifies_identically(self):
        for message in ("TEST_ONLY which goal has priority?", "TEST_ONLY hey how are you"):
            d, c = PROD.detect_goal_intent(message), CAND.classify(message)
            self.assertEqual({k: d[k] for k in ("any", "goal_create", "goal_query")}, c)


class CareerReadPatch(unittest.TestCase):
    """The patch in adapter_career_read.patch, applied to a temp copy: a refused create stops reading career data."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(prefix="goal-prop-", ignore_cleanup_errors=True)
        cls.home = Path(cls.tmp.name) / "home"
        assert assemble_dev_cognition.assemble(cls.home) == []

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def load(self, patched: bool):
        src = (self.home / "lilith_router" / "world_context.py").read_text(encoding="utf-8")
        if patched:
            anchor = "        module._post_goal_json = _refused_post_goal_json\n"
            self.assertEqual(src.count(anchor), 1)
            src = src.replace(anchor, anchor + "        module._goal_title_for = _title_without_career_read\n")
            src = src.replace("def _load_legacy():", 'def _title_without_career_read(app_id):\n    return "Follow up on application {aid}".format(aid=app_id)\n\n\ndef _load_legacy():', 1)
        name = f"adapter_{'p' if patched else 'b'}"
        f = self.home / "lilith_router" / f"{name}.py"
        f.write_text(src, encoding="utf-8")
        spec = importlib.util.spec_from_file_location(name, f)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        self.assertIsNotNone(mod._LEGACY, mod._UNAVAILABLE_REASON)
        return mod

    def reads(self, patched: bool):
        mod = self.load(patched)
        paths, real = [], mod._LEGACY._get_json
        def spy(path, timeout=2.5):
            paths.append(path)
            return None
        mod._LEGACY._get_json = spy
        token = mod._BUDGET.set([16])
        try:
            gi = mod._LEGACY.detect_goal_intent("track application 21 as a goal")
            suffix, _ = mod._LEGACY.build_goal_grounding("track application 21 as a goal", "s", gi, do_write=True)
        finally:
            mod._BUDGET.reset(token)
            mod._LEGACY._get_json = real
        return paths, suffix

    def test_refused_create_reads_career_data_today_and_not_after_the_patch(self):
        before, text0 = self.reads(False)
        after, text1 = self.reads(True)
        self.assertEqual(before, ["/career/applications", "/os/goals?limit=200", "/os/goals/focus"])
        self.assertEqual(after, ["/os/goals?limit=200", "/os/goals/focus"])
        self.assertEqual(text0, text1)                       # the same honest "could not track" prompt


if __name__ == "__main__":
    unittest.main()
