# -*- coding: utf-8 -*-
"""Fail-closed write authentication for Goals, Tasks and Drafts. TEST_ONLY; throwaway DB; no network.

Unset or unknown refuses writes. Handlers are called directly, because CI has no httpx.
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
WRITES = {
    "/os/goals": lambda c: app.post_goal(dict(GOAL), x_lilith_os_write=c),
    "/os/goals/{goal_id}/transition": lambda c: app.post_goal_transition("g.x", {"action": "start"}, x_lilith_os_write=c),
    "/os/goals/{goal_id}/link_task": lambda c: app.post_goal_link_task("g.x", {"taskId": "t1"}, x_lilith_os_write=c),
    "/os/tasks": lambda c: app.create_task({}, x_lilith_os_write=c),
    "/os/tasks/{task_id}": lambda c: app.update_task("t.x", {}, x_lilith_os_write=c),
    "/os/drafts": lambda c: app.create_draft({}, x_lilith_os_write=c),
    "/os/drafts/{draft_id}": lambda c: app.discard_draft("d.x", x_lilith_os_write=c),
}
OTHER_AUTH = {"/os/conversation", "/os/conversation/evidence"}          # fail-closed through _require_capture_auth


class WriteAuthTest(unittest.TestCase):
    def setUp(self):
        fd, path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        self.addCleanup(lambda: os.path.exists(path) and os.unlink(path))
        app.DB = Path(path)
        app._goal_schema_ready = False
        patch = mock.patch.dict(os.environ)
        patch.start()
        self.addCleanup(patch.stop)
        os.environ.pop("LILITH_OS_WRITE_AUTH", None)
        os.environ.pop("LILITH_OS_WRITE_TOKEN", None)

    def assert_code(self, write, cred, code):
        with self.assertRaises(HTTPException) as caught:
            write(cred)
        self.assertEqual(caught.exception.status_code, code)

    def test_every_os_write_route_is_covered(self):
        routes = {r.path for r in app.app.routes if getattr(r, "methods", None) and r.methods & {"POST", "PUT", "PATCH", "DELETE"}
                  and r.path.startswith("/os/")}
        covered = {r.path for r in app.app.routes if getattr(r, "dependant", None) is not None
                   and any(p.alias == "x-lilith-os-write" for p in r.dependant.header_params)}
        self.assertEqual(routes - OTHER_AUTH, covered)
        self.assertEqual(covered, set(WRITES))

    def test_unset_refuses_every_write_and_changes_nothing(self):
        for path, write in WRITES.items():
            with self.subTest(path=path):
                self.assert_code(write, TOKEN, 503)
        self.assertFalse(app.DB.stat().st_size)

    def test_unknown_mode_refuses(self):
        for mode in ("", "ENFORCED", "off", "open", "true"):
            os.environ["LILITH_OS_WRITE_AUTH"] = mode
            self.assertEqual(app._write_auth_state(), "refused", mode)

    def test_enforced_with_a_missing_or_short_token_refuses(self):
        os.environ["LILITH_OS_WRITE_AUTH"] = "enforced"
        self.assert_code(WRITES["/os/goals"], None, 503)
        os.environ["LILITH_OS_WRITE_TOKEN"] = "short"
        self.assert_code(WRITES["/os/goals"], "short", 503)

    def test_enforced_needs_the_exact_token_before_any_db_access(self):
        os.environ.update(LILITH_OS_WRITE_AUTH="enforced", LILITH_OS_WRITE_TOKEN=TOKEN)
        for path, write in WRITES.items():
            for cred in (None, "", TOKEN[:-1], TOKEN + "x", "\u00e9"):
                with self.subTest(path=path, cred=cred):
                    self.assert_code(write, cred, 401)
        self.assertFalse(app.DB.stat().st_size)
        self.assertTrue(app.post_goal(dict(GOAL), x_lilith_os_write=TOKEN)["created"])

    def test_open_mode_must_be_explicit(self):
        os.environ["LILITH_OS_WRITE_AUTH"] = "open-acknowledged"
        self.assertTrue(app.post_goal(dict(GOAL), x_lilith_os_write=None)["created"])

    def test_the_preflight_probe_is_refused_before_body_handling(self):
        # SECURITY-PLAN: a POST with no header and an invalid body must never reach validation or the DB on a protected service.
        try:
            from fastapi.testclient import TestClient
        except Exception:
            self.skipTest("httpx not installed")
        client = TestClient(app.app, raise_server_exceptions=False)
        probe = {"title": "TEST_ONLY"}                                 # fails validation if it ever gets that far
        self.assertEqual(client.post("/os/goals", json=probe).status_code, 503)
        os.environ.update(LILITH_OS_WRITE_AUTH="enforced", LILITH_OS_WRITE_TOKEN=TOKEN)
        self.assertEqual(client.post("/os/goals", json=probe).status_code, 401)
        self.assertEqual(client.post("/os/goals", json=probe, headers={"X-LILITH-OS-Write": "wrong"}).status_code, 401)
        self.assertEqual(client.post("/os/goals", json=probe, headers={"X-LILITH-OS-Write": TOKEN}).status_code, 400)
        os.environ["LILITH_OS_WRITE_AUTH"] = "open-acknowledged"
        self.assertEqual(client.post("/os/goals", json=probe).status_code, 400)

    def test_health_reports_the_state_and_no_secret(self):
        self.assertEqual(app.health()["writeAuth"], "refused")
        os.environ.update(LILITH_OS_WRITE_AUTH="enforced", LILITH_OS_WRITE_TOKEN=TOKEN)
        body = app.health()
        self.assertEqual(body["writeAuth"], "enforced")
        self.assertNotIn(TOKEN, repr(body))


if __name__ == "__main__":
    unittest.main()
