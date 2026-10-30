"""Candidate adapter with the Goals hardening (NOT IN ANY RELEASE). TEST_ONLY; no network.

    python -m unittest discover -s integrations/hermes/overlays/dev-goals-hardening/tests -p "test_*.py"

The held-out corpus below was written before the regular expressions were tested against it and is never used to tune
them. If a held-out case fails, record it; do not edit the expression to fit this file.
"""

from __future__ import annotations

import hashlib
import importlib.util
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
REPO = HERE.parents[3]
BASE_ADAPTER = REPO / "integrations/hermes/overlays/dev-unified-cognition/lilith_router/world_context.py"
PROD = REPO / "integrations/hermes/home/variants/prod-lilith-01/lilith_router/world_context.py"
CANDIDATE = HERE / "lilith_router" / "world_context.py"

HELD_OUT_QUERIES = [
    "what goals do you have?", "which goals are blocked?", "tell me about your current goals", "do you have any active goals?",
    "what is the status of my goals?", "show me the open goals", "which of the goals matters most?", "what are you pursuing?",
    "what is on hold?", "why are you stalled on this?", "what is suspended?", "is there a current focus?", "what should I resume?",
    "list goals", "what does the goal list look like?",
]
HELD_OUT_CREATES = [
    "please track that as a goal", "add this as a goal", "let's make a goal for application 12", "could you create a goal for application 8?",
    "record a goal for application 40", "register a goal for this role", "track it as a goal", "set a goal for application 2",
]
HELD_OUT_OTHER = [
    "the goalie made a brilliant save", "my goal is to finish this book by Sunday", "he scored the winning goal in extra time",
    "our sales goal was missed last quarter", "the end goal of the refactor is simpler code", "I have a personal goal to run more",
    "goal-line technology changed football", "she set a new personal best", "add salt to the soup", "track my parcel please",
    "what time is the match?", "the track was fast today", "I record podcasts at home", "make me a sandwich",
]


def load(path: Path, name: str, directory: Path):
    target = directory / f"{name}.py"
    shutil.copy2(path, target)
    shutil.copy2(PROD, directory / "_prod_world_context.py")
    spec = importlib.util.spec_from_file_location(name, target)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module._LEGACY is not None, module._UNAVAILABLE_REASON
    return module


class HardeningOverlay(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(prefix="goal-overlay-", ignore_cleanup_errors=True)
        directory = Path(cls.tmp.name)
        cls.base = load(BASE_ADAPTER, "base_adapter", directory)
        cls.cand = load(CANDIDATE, "cand_adapter", directory)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_the_candidate_is_the_base_adapter_plus_only_the_two_changes(self):
        base, cand = (p.read_text(encoding="utf-8").splitlines() for p in (BASE_ADAPTER, CANDIDATE))
        removed = [l for l in base if l not in cand]
        added = [l for l in cand if l not in base]
        self.assertEqual(removed, [])
        self.assertTrue(all("GOAL" in l or "_title_without_career_read" in l or "Follow up on application" in l or l.startswith(("#", "    r\"", "    re.IGNORECASE", ")", "    r'", "HARDENED", "\"\"\"", "_HARDENED")) or not l.strip() for l in added), added)

    def test_prod_bytes_are_untouched(self):
        self.assertEqual(hashlib.sha256(PROD.read_bytes()).hexdigest(), "46b8187e3f6f2ac72c920de9dab12fd9c2841551f6c2aa7c20fd91941e3f0104")

    def test_held_out_corpus(self):
        d = lambda m: self.cand.detect_goal_intent(m)
        missed_q = [m for m in HELD_OUT_QUERIES if not d(m)["goal_query"]]
        missed_c = [m for m in HELD_OUT_CREATES if not d(m)["goal_create"]]
        false_any = [m for m in HELD_OUT_OTHER if d(m)["any"]]
        false_create = [m for m in HELD_OUT_OTHER + HELD_OUT_QUERIES if d(m)["goal_create"]]
        base = lambda m: self.base.detect_goal_intent(m)
        print(f"\nHELD_OUT candidate queries {len(HELD_OUT_QUERIES) - len(missed_q)}/{len(HELD_OUT_QUERIES)} creates {len(HELD_OUT_CREATES) - len(missed_c)}/{len(HELD_OUT_CREATES)} "
              f"false_any {len(false_any)}/{len(HELD_OUT_OTHER)} false_create {len(false_create)}")
        print("HELD_OUT deployed false_any", sum(base(m)["any"] for m in HELD_OUT_OTHER), "missed", missed_q, missed_c, "false", false_any, false_create)
        self.assertLess(len(false_any), sum(base(m)["any"] for m in HELD_OUT_OTHER))
        self.assertEqual(false_create, [])                   # a chat message must never look like a create

    def test_reasoning_precedence_follows_the_tighter_detector(self):
        self.assertFalse(self.cand.detect_reasoning_intent("TEST_ONLY which goal has priority?")["any"])
        self.assertTrue(self.cand.detect_reasoning_intent("TEST_ONLY what are my options for application 14?")["any"])

    def test_a_refused_create_makes_no_career_read(self):
        paths = []
        legacy = self.cand._LEGACY
        real = legacy._get_json
        legacy._get_json = lambda path, timeout=2.5: paths.append(path)
        token = self.cand._BUDGET.set([16])
        try:
            message = "track application 21 as a goal"
            suffix, action = legacy.build_goal_grounding(message, "s", legacy.detect_goal_intent(message), do_write=True)
        finally:
            self.cand._BUDGET.reset(token)
            legacy._get_json = real
        self.assertEqual(paths, ["/os/goals?limit=200", "/os/goals/focus"])
        self.assertIn("could not track the goal", suffix)
        self.assertIsNone(action)


if __name__ == "__main__":
    unittest.main()
