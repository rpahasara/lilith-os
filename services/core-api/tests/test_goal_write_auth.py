# -*- coding: utf-8 -*-
"""Opt-in caller check on the goal write routes. TEST_ONLY; throwaway DB; no network.

With LILITH_OS_GOAL_WRITE_TOKEN unset the routes behave exactly as before. With it set, a write needs the exact token in
X-LILITH-OS-Goal-Write. Reads are never affected.
"""
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import app  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

TOKEN = "TEST_ONLY" + "x" * 32
HEADER = "X-LILITH-OS-Goal-Write"
GOAL = {"type": "test_only.synthetic", "title": "TEST_ONLY goal", "source": "SYSTEM_MAINTENANCE", "owner": "user",
        "priority": "NORMAL", "goalId": "g.test-only-auth-1"}


class GoalWriteAuthTest(unittest.TestCase):
    def setUp(self):
        fd, path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        self.addCleanup(lambda: os.path.exists(path) and os.unlink(path))
        app.DB = Path(path)
        app._goal_schema_ready = False
        self.client = TestClient(app.app, raise_server_exceptions=False)

    def rows(self):
        c = app._goals_db()
        try:
            return c.execute("SELECT COUNT(*) FROM goal").fetchone()[0]
        finally:
            c.close()

    def env(self, value):
        patch = mock.patch.dict(os.environ, {"LILITH_OS_GOAL_WRITE_TOKEN": value} if value is not None else {})
        patch.start()
        self.addCleanup(patch.stop)
        if value is None:
            os.environ.pop("LILITH_OS_GOAL_WRITE_TOKEN", None)

    def test_unset_token_keeps_todays_behaviour(self):
        self.env(None)
        self.assertEqual(self.client.post("/os/goals", json=GOAL).status_code, 200)
        self.assertEqual(self.rows(), 1)

    def test_every_write_route_refuses_without_the_exact_token_and_changes_nothing(self):
        self.env(TOKEN)
        for path, body in (("/os/goals", GOAL), ("/os/goals/g.x/transition", {"action": "start"}),
                           ("/os/goals/g.x/link_task", {"taskId": "t1"})):
            for headers in ({}, {HEADER: ""}, {HEADER: TOKEN[:-1]}, {HEADER: TOKEN + "x"}):
                with self.subTest(path=path, headers=headers):
                    response = self.client.post(path, json=body, headers=headers)
                    self.assertEqual(response.status_code, 401)
                    self.assertEqual(response.json()["detail"], "GOAL_WRITE_NOT_AUTHENTICATED")
        self.assertEqual(self.rows(), 0)

    def test_the_exact_token_is_accepted(self):
        self.env(TOKEN)
        self.assertEqual(self.client.post("/os/goals", json=GOAL, headers={HEADER: TOKEN}).status_code, 200)
        self.assertEqual(self.rows(), 1)

    def test_a_short_configured_token_fails_closed(self):
        self.env("short")
        response = self.client.post("/os/goals", json=GOAL, headers={HEADER: "short"})
        self.assertEqual((response.status_code, response.json()["detail"]), (503, "GOAL_WRITE_CREDENTIAL_UNCONFIGURED"))
        self.assertEqual(self.rows(), 0)

    def test_reads_never_need_the_token(self):
        self.env(TOKEN)
        self.assertEqual(self.client.get("/os/goals?limit=200").status_code, 200)
        self.assertEqual(self.client.get("/os/goals/focus").status_code, 200)


if __name__ == "__main__":
    unittest.main()
