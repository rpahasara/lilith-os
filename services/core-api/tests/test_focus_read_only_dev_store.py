# -*- coding: utf-8 -*-
"""gv1 contract for the DEV startup verifier: on a DEV-shaped goal store (six terminal TEST_ONLY commitment goals and their
20 transition traces, as left by the 2026-11-09 P4-4 test), a normal focus read through the real app writes nothing. With
LILITH_OS_FOCUS_READ_ONLY=1 it writes nothing even if a candidate goal appears. TEST_ONLY; throwaway DB; loopback only.
"""
import os
import shutil
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import app  # noqa: E402

try:
    from fastapi.testclient import TestClient
except Exception:       # CI has no httpx
    TestClient = None

GV1_TEMPLATE = (Path(__file__).resolve().parents[3] / "integrations" / "hermes" / "release"
                / "dev-f9c2-cog1-wm1-g1-r1-w1-m1-p1-e1-gv1" / "templates" / "bin" / "verify_release.py.tmpl")


class FocusGuardContract(unittest.TestCase):
    """The DEV gateway's startup verifier (gv1) refuses to start unless this app's focus route writes its trace only under
    LILITH_OS_FOCUS_READ_ONLY != "1", from goal_focus alone. Runs in CI (no httpx needed), so a refactor of the focus
    route fails here, at review, instead of as a refused DEV gateway start after the next deploy."""

    def test_app_py_satisfies_the_gv1_focus_guard(self):
        import types
        src = GV1_TEMPLATE.read_text(encoding="utf-8")
        module = types.ModuleType("gv1_verifier")
        with mock.patch.dict(sys.modules, {"yaml": sys.modules.get("yaml") or types.ModuleType("yaml")}):
            exec(compile(src, str(GV1_TEMPLATE), "exec"), module.__dict__)
        app_src = Path(app.__file__).read_text(encoding="utf-8")
        self.assertEqual(module.focus_guard_problems(app_src), [])
        self.assertEqual(module.focus_guard_problems(app_src.replace('_os.getenv("LILITH_OS_FOCUS_READ_ONLY") != "1"', "True")),
                         ["FOCUS_GUARD_MISSING"])

TERMINAL = ("COMPLETED", "COMPLETED", "FAILED", "FAILED", "CANCELLED", "CANCELLED")


def snapshot(db):
    c = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        return {t: c.execute(f'SELECT * FROM "{t}" ORDER BY 1').fetchall() for t in ("goal", "goal_trace")}
    finally:
        c.close()


@unittest.skipIf(TestClient is None, "httpx not installed")
class FocusReadOnDevShapedStore(unittest.TestCase):
    def setUp(self):
        patch = mock.patch.dict(os.environ, {"LILITH_OS_READ_AUTH": "open-acknowledged", "LILITH_OS_WRITE_AUTH": "open-acknowledged"})
        patch.start()
        self.addCleanup(patch.stop)
        os.environ.pop("LILITH_OS_FOCUS_READ_ONLY", None)
        self.tmp = Path(tempfile.mkdtemp(prefix="gv1-focus-"))
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.db = self.tmp / "lilith-dev.db"
        app.DB = self.db
        app._goal_schema_ready = False
        conn = app._goals_db()
        for i, state in enumerate(TERMINAL):           # through the real create + transition paths, like the P4-4 test
            gid = f"g.test-only-{i}"
            app._create_goal_impl(conn, {"type": "commitment.once", "title": f"TEST_ONLY {i}", "source": "SCHEDULED",
                                         "owner": "user", "priority": "NORMAL", "goalId": gid})
            for action in ("activate", {"COMPLETED": "complete", "FAILED": "fail", "CANCELLED": "cancel"}[state]):
                app._transition_goal_impl(conn, gid, {"action": action, "reason": "TEST_ONLY"})
        conn.close()
        self.client = TestClient(app.app, raise_server_exceptions=False)

    def kinds(self):
        return sorted({r[4] for r in snapshot(self.db)["goal_trace"]})

    def focus(self):
        r = self.client.get("/os/goals/focus")
        self.assertEqual(r.status_code, 200)
        return r.json()

    def test_the_store_is_dev_shaped(self):
        rows = snapshot(self.db)
        self.assertEqual(sorted(r[7] for r in rows["goal"]), sorted(TERMINAL))
        self.assertEqual(self.kinds(), ["transition"])

    def test_with_the_flag_focus_reads_write_nothing(self):
        os.environ["LILITH_OS_FOCUS_READ_ONLY"] = "1"
        before = snapshot(self.db)
        for _ in range(5):
            doc = self.focus()
            self.assertIsNone(doc["focus"])
            self.assertIsNone(doc["arbitration"]["winner"])
        self.assertEqual(snapshot(self.db), before)

    def test_terminal_only_store_writes_nothing_even_without_the_flag(self):
        before = snapshot(self.db)
        self.focus(); self.focus()
        self.assertEqual(snapshot(self.db), before)

    def test_with_the_flag_a_new_candidate_still_writes_nothing(self):
        os.environ["LILITH_OS_FOCUS_READ_ONLY"] = "1"
        conn = app._goals_db()
        app._create_goal_impl(conn, {"type": "test_only.synthetic", "title": "TEST_ONLY candidate", "source": "SYSTEM_MAINTENANCE",
                                     "owner": "user", "priority": "HIGH", "goalId": "g.test-only-candidate"})
        conn.close()
        before = snapshot(self.db)
        self.assertEqual(self.focus()["arbitration"]["winner"], "g.test-only-candidate")
        self.assertEqual(snapshot(self.db), before)
        self.assertNotIn("arbitration", self.kinds())

    def test_with_the_flag_a_reopened_terminal_goal_still_writes_nothing(self):
        os.environ["LILITH_OS_FOCUS_READ_ONLY"] = "1"
        conn = app._goals_db()
        app._transition_goal_impl(conn, "g.test-only-0", {"action": "reopen", "reason": "TEST_ONLY"})   # COMPLETED -> PENDING
        conn.close()
        before = snapshot(self.db)
        self.assertEqual(self.focus()["arbitration"]["winner"], "g.test-only-0")
        self.assertEqual(snapshot(self.db), before)

    def test_control_without_the_flag_a_candidate_makes_the_read_write(self):
        conn = app._goals_db()
        app._create_goal_impl(conn, {"type": "test_only.synthetic", "title": "TEST_ONLY candidate", "source": "SYSTEM_MAINTENANCE",
                                     "owner": "user", "priority": "HIGH", "goalId": "g.test-only-candidate"})
        conn.close()
        self.focus()
        self.assertIn("arbitration", self.kinds())        # exactly what the verifier's two guards keep from happening


if __name__ == "__main__":
    unittest.main()
