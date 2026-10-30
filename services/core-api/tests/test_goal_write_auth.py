# -*- coding: utf-8 -*-
"""Opt-in caller check on the goal write routes. TEST_ONLY; throwaway DB; no network.

With LILITH_OS_GOAL_WRITE_TOKEN unset the routes behave exactly as before. With it set, a write needs the exact token in
X-LILITH-OS-Goal-Write. Reads are never affected. Handlers are called directly, as in test_goal_executive.py.
"""
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import app  # noqa: E402
from fastapi import HTTPException  # noqa: E402

TOKEN = "TEST_ONLY" + "x" * 32
GOAL = {"type": "test_only.synthetic", "title": "TEST_ONLY goal", "source": "SYSTEM_MAINTENANCE", "owner": "user",
        "priority": "NORMAL", "goalId": "g.test-only-auth-1"}
WRITES = (
    lambda cred: app.post_goal(dict(GOAL), x_lilith_os_goal_write=cred),
    lambda cred: app.post_goal_transition("g.x", {"action": "start"}, x_lilith_os_goal_write=cred),
    lambda cred: app.post_goal_link_task("g.x", {"taskId": "t1"}, x_lilith_os_goal_write=cred),
)


class GoalWriteAuthTest(unittest.TestCase):
    def setUp(self):
        fd, path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        self.addCleanup(lambda: os.path.exists(path) and os.unlink(path))
        app.DB = Path(path)
        app._goal_schema_ready = False
        patch = mock.patch.dict(os.environ)
        patch.start()
        self.addCleanup(patch.stop)
        os.environ.pop("LILITH_OS_GOAL_WRITE_TOKEN", None)

    def rows(self):
        c = app._goals_db()
        try:
            return c.execute("SELECT COUNT(*) FROM goal").fetchone()[0]
        finally:
            c.close()

    def test_the_header_is_wired_to_exactly_the_three_write_routes(self):
        wired = {r.path for r in app.app.routes if getattr(r, "dependant", None) is not None
                 and any(p.alias == "x-lilith-os-goal-write" for p in r.dependant.header_params)}
        self.assertEqual(wired, {"/os/goals", "/os/goals/{goal_id}/transition", "/os/goals/{goal_id}/link_task"})

    def test_unset_token_keeps_todays_behaviour(self):
        self.assertTrue(app.post_goal(dict(GOAL), x_lilith_os_goal_write=None)["created"])
        self.assertEqual(self.rows(), 1)

    def test_every_write_route_refuses_without_the_exact_token_and_changes_nothing(self):
        os.environ["LILITH_OS_GOAL_WRITE_TOKEN"] = TOKEN
        for write in WRITES:
            for cred in (None, "", TOKEN[:-1], TOKEN + "x"):
                with self.subTest(cred=cred):
                    with self.assertRaises(HTTPException) as caught:
                        write(cred)
                    self.assertEqual((caught.exception.status_code, caught.exception.detail),
                                     (401, "GOAL_WRITE_NOT_AUTHENTICATED"))
        self.assertEqual(self.rows(), 0)

    def test_the_exact_token_is_accepted(self):
        os.environ["LILITH_OS_GOAL_WRITE_TOKEN"] = TOKEN
        self.assertTrue(app.post_goal(dict(GOAL), x_lilith_os_goal_write=TOKEN)["created"])
        self.assertEqual(self.rows(), 1)

    def test_a_short_configured_token_fails_closed(self):
        os.environ["LILITH_OS_GOAL_WRITE_TOKEN"] = "short"
        with self.assertRaises(HTTPException) as caught:
            app.post_goal(dict(GOAL), x_lilith_os_goal_write="short")
        self.assertEqual((caught.exception.status_code, caught.exception.detail),
                         (503, "GOAL_WRITE_CREDENTIAL_UNCONFIGURED"))
        self.assertEqual(self.rows(), 0)

    def test_reads_never_need_the_token(self):
        os.environ["LILITH_OS_GOAL_WRITE_TOKEN"] = TOKEN
        self.assertEqual(app.list_goals(limit=200)["count"], 0)
        self.assertIsNone(app.goal_focus()["focus"])


if __name__ == "__main__":
    unittest.main()
