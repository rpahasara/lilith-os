# -*- coding: utf-8 -*-
"""Offline unit tests for the Slice 8 goal conversation lane (detection +
formatting only; no network). Import path is set by the runner."""
import unittest
import world_context as wc


class GoalDetectTests(unittest.TestCase):
    def q(self, m):
        return wc.detect_goal_intent(m)

    def test_trying_to_do_is_query(self):
        i = self.q("What are you currently trying to do?")
        self.assertTrue(i["any"]) ; self.assertTrue(i["goal_query"]) ; self.assertFalse(i["goal_create"])

    def test_track_as_goal_is_create(self):
        i = self.q("I want to follow up on application 14. Track that as a goal.")
        self.assertTrue(i["goal_create"]) ; self.assertEqual(i["app_id"], "14")

    def test_active_goals_query(self):
        i = self.q("What goals are active?")
        self.assertTrue(i["goal_query"]) ; self.assertEqual(i["subtype"], "active")

    def test_blocked_why(self):
        i = self.q("Why is goal for application 14 blocked?")
        self.assertTrue(i["goal_query"]) ; self.assertEqual(i["subtype"], "why_blocked")

    def test_priority(self):
        i = self.q("Which goal has priority and why?")
        self.assertTrue(i["goal_query"]) ; self.assertEqual(i["subtype"], "priority")

    def test_draft_turn_not_goal(self):
        # a plain draft request must NOT be captured by the goal lane
        i = self.q("draft a follow-up for application 17")
        self.assertFalse(i["any"])

    def test_casual_not_goal(self):
        for m in ("hey, how are you?", "what are you doing later?", "good morning"):
            self.assertFalse(self.q(m)["any"], m)

    def test_make_it_a_goal(self):
        i = self.q("set a goal to follow up on application 14")
        self.assertTrue(i["goal_create"]) ; self.assertEqual(i["app_id"], "14")


class GoalFormatTests(unittest.TestCase):
    def test_block_render_blocked_and_focus(self):
        goals = {"goals": [
            {"goalId": "g.a", "title": "Follow up 14", "lifecycleState": "BLOCKED",
             "priority": "NORMAL", "source": "USER_REQUESTED",
             "target": {"type": "career.application", "id": "14"},
             "blockedReason": "two unsent drafts require reconciliation",
             "blockedBy": ["draft:d1", "draft:d2"],
             "resumeConditions": "keep one draft", "linkedTaskIds": []},
            {"goalId": "g.b", "title": "Prep 17", "lifecycleState": "ACTIVE",
             "priority": "HIGH", "source": "USER_REQUESTED", "target": {},
             "linkedTaskIds": ["t1"]},
        ]}
        focus = {"focus": {"goalId": "g.b", "title": "Prep 17"},
                 "arbitration": {"winner": "g.b", "ruleFired": "lifecycle",
                                 "alternatives": [{"goalId": "g.a", "eliminatedBy": "lifecycle"}]}}
        txt = wc.build_goal_block(goals, focus)
        self.assertIn("BLOCKED", txt)
        self.assertIn("reconciliation", txt)
        self.assertIn("CURRENT FOCUS", txt)
        self.assertIn("g.b", txt)


if __name__ == "__main__":
    unittest.main(verbosity=2)
