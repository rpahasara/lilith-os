"""G3 follow-up on the real gateway, adapter and Core API, with the g2 router (Goals live) and a populated test DB. TEST_ONLY; no network.

G3 (2026-10-30) failed on title presentation, and its negative control never ran. These tests pin what can be known offline. They are
not a substitute for either live check: a model reply is only simulated here.
"""

from __future__ import annotations

import gc
import importlib
import importlib.util
import json
import re
import shutil
import sys
import tempfile
import unicodedata
import unittest
from pathlib import Path

W1 = Path(__file__).resolve().parents[1]
REPO = W1.parents[3]
sys.path.insert(0, str(REPO / "integrations" / "hermes" / "release" / "dev-f9c2-cog1-wm1-g2" / "tests"))

import test_g2_core_api_compat as C  # noqa: E402

HIGH = {"id": "g.test-only-regress-high", "marker": "-".join(("ROWAN", "PLOVER", "6204")), "priority": "HIGH"}
NORMAL = {"id": "g.test-only-regress-normal", "marker": "-".join(("SEDGE", "MARTEN", "1937")), "priority": "NORMAL"}
G3_REPLY = "The goal with higher priority is **g.test-only-regress-high** (priority HIGH)."
TITLE_REPLY = f"The priority goal is TEST_ONLY synthetic goal {HIGH['marker']}."
CANDIDATE = REPO / "integrations/hermes/overlays/dev-reasoning-hardening/lilith_router/world_context.py"
DEPLOYED = REPO / "integrations/hermes/overlays/dev-unified-cognition/lilith_router/world_context.py"
NEGATIVES = (C.CONTROL, "TEST_ONLY thanks, that was helpful", "TEST_ONLY what's a good film tonight?", "TEST_ONLY my priority today is lunch")
OVER_MATCHES = (C.CASUAL, "TEST_ONLY nice goal last night", "TEST_ONLY who scored that goal?")   # found by this test; the G3 L2 message would not have shown it


def setUpModule():
    C.setUpModule()                                           # g2 router: Goals live, the state these findings are about
    shutil.copy2(CANDIDATE, C.HOME / "lilith_router" / "world_context.py")
    importlib.reload(C.STATE["wc"])


def tearDownModule():
    gc.collect()                                              # Windows: open SQLite handles would keep the shared temp dir for the next module
    C.tearDownModule()


def fold(text: str) -> str:
    """The G3 comparison: Unicode hyphens, spaces and zero-width characters cannot hide a match."""
    text = unicodedata.normalize("NFKC", text)
    text = re.sub(r"[‐-―−­]", "-", text)
    return re.sub(r"[​-‍⁠﻿]", "", text).casefold()


def named_by(reply: str, goal: dict) -> str:
    """The future live criterion: 'title' passes. 'id' is correct selection, reported apart, and is not a title pass."""
    text = fold(reply)
    return "title" if fold(goal["marker"]) in text else "id" if fold(goal["id"]) in text else "none"


class Base(C.GoalsLiveOnTheRealCoreApiTest):
    pass


for attr in [n for n in dir(C.GoalsLiveOnTheRealCoreApiTest) if n.startswith("test_")]:
    setattr(Base, attr, None)


class PopulatedGoals(Base):
    def seed(self, name: str):
        db = C.use_db(name, goal_schema=True)
        core = C.STATE["core"]
        conn = core._goals_db()
        for goal in (NORMAL, HIGH):
            core._create_goal_impl(conn, {"type": "test_only.synthetic", "title": f"TEST_ONLY synthetic goal {goal['marker']}", "source": "SYSTEM_MAINTENANCE",
                                          "owner": "user", "priority": goal["priority"], "goalId": goal["id"]})
        conn.close()
        return db

    def test_the_title_reaches_the_prompt_for_both_goals_and_the_focus(self):
        self.seed("title")
        result = self.route(C.QUERY, "reg-title")
        text = result["combined_ephemeral"]
        self.assertIn(f"- GOAL {HIGH['id']}: TEST_ONLY synthetic goal {HIGH['marker']}", text)
        self.assertIn(f"- GOAL {NORMAL['id']}: TEST_ONLY synthetic goal {NORMAL['marker']}", text)
        focus = next(l for l in text.splitlines() if l.startswith("CURRENT FOCUS"))
        self.assertIn(HIGH["marker"], focus)
        self.assertIn(f"{NORMAL['id']} eliminated by rule 'priority'", focus)

    def test_the_id_is_the_first_handle_on_every_goal_line(self):
        # The root cause of the G3 FAIL: both forms are offered, the id first.
        self.seed("order")
        text = self.route(C.QUERY, "reg-order")["combined_ephemeral"]
        focus = next(l for l in text.splitlines() if l.startswith("CURRENT FOCUS"))
        self.assertLess(focus.index(HIGH["id"]), focus.index(HIGH["marker"]))

    def test_the_policy_tells_the_model_to_name_a_goal_by_its_title(self):
        # Text only: whether a model follows it needs a live check, which has not run.
        self.seed("policy")
        text = self.route(C.QUERY, "reg-policy")["combined_ephemeral"]
        rule = "- Name a goal by its title. Give its goal id only if you are asked for it.\n"
        self.assertEqual(text.count(rule), 1)
        self.assertLess(text.index(rule), text.index("\nGOAL / EXECUTIVE STATE (durable"))     # in the policy, ahead of the state it governs

    def test_the_g3_reply_shape_stays_a_title_failure(self):
        self.assertEqual(named_by(G3_REPLY, HIGH), "id")
        self.assertEqual(named_by(TITLE_REPLY, HIGH), "title")
        self.assertEqual(named_by(TITLE_REPLY.replace("-", "‑"), HIGH), "title")
        self.assertEqual(named_by("I cannot tell.", HIGH), "none")

    def test_negative_control_on_a_populated_store_reads_and_writes_nothing(self):
        db = self.seed("negative")
        before = C.schema(db), C.rows(db)
        for i, message in enumerate(NEGATIVES):
            self.bridge.calls.clear()
            self.assertIsNone(self.route(message, f"reg-neg-{i}"), message)
            self.assertEqual(self.bridge.calls, [], message)
        self.assertEqual((C.schema(db), C.rows(db)), before)
        raw = json.dumps(self.new_log())
        for goal in (HIGH, NORMAL):
            self.assertNotIn(goal["id"], raw)
            self.assertNotIn(goal["marker"], raw)

    def test_casual_mentions_of_the_word_goal_stay_out_of_the_goal_lane(self):
        # With Goals live and a populated store: no read, no trace, no title near the prompt.
        db = self.seed("over")
        before = C.schema(db), C.rows(db)
        for i, message in enumerate(OVER_MATCHES):
            self.bridge.calls.clear()
            self.assertIsNone(self.route(message, f"reg-over-{i}"), message)
            self.assertEqual(self.bridge.calls, [], message)
        self.assertEqual((C.schema(db), C.rows(db)), before)

    def test_the_deployed_adapter_still_has_the_defect(self):
        # r1 and g2 carry this adapter. Goals stays in shadow there, so nothing reaches a provider, but g2 must not be used with real goals.
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            shutil.copy2(DEPLOYED, Path(tmp) / "wc_dep.py")
            shutil.copy2(REPO / "integrations/hermes/home/variants/prod-lilith-01/lilith_router/world_context.py", Path(tmp) / "_prod_world_context.py")
            spec = importlib.util.spec_from_file_location("wc_dep", Path(tmp) / "wc_dep.py")
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
        self.assertEqual([m for m in OVER_MATCHES if not module.detect_goal_intent(m)["any"]], [])

    def test_a_live_negative_reply_must_name_neither_goal(self):
        self.assertEqual(named_by("TEST_ONLY doing well, thanks.", HIGH), "none")
        self.assertEqual(named_by("TEST_ONLY doing well, thanks.", NORMAL), "none")


if __name__ == "__main__":
    unittest.main()
