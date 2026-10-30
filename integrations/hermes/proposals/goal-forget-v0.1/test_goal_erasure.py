"""Candidate goal erasure on the real Core API schema. TEST_ONLY; throwaway DBs. Needs fastapi.

    python -B -m unittest discover -s integrations/hermes/proposals/goal-forget-v0.1 -p "test_*.py"
"""

import importlib.util
import os
import sqlite3
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import goal_erasure as E  # noqa: E402

CANARY = "TEST_ONLY_FORGET_CANARY_5F"
tmp = tempfile.mkdtemp(prefix="gforget.")
os.environ.update(LILITH_DB_PATH=str(Path(tmp) / "boot.db"), HERMES_HOME=tmp, LILITH_HOME=tmp)
sys.path.insert(0, str(REPO / "services/core-api"))
sys.dont_write_bytecode = True
spec = importlib.util.spec_from_file_location("app", REPO / "services/core-api/app.py")
app = importlib.util.module_from_spec(spec)
sys.modules["app"] = app
spec.loader.exec_module(app)


def fresh(name, goals=()):
    db = Path(tmp) / f"{name}.db"
    app.DB = db
    app._goal_schema_ready = False
    conn = app._goals_db()
    for i, title in enumerate(goals):
        app._create_goal_impl(conn, {"type": "test_only.synthetic", "title": title, "source": "SYSTEM_MAINTENANCE", "owner": "user",
                                     "priority": "NORMAL", "goalId": f"g.test-only-{i}", "description": f"{title} description"})
    conn.close()
    return db


def rows(db):
    c = sqlite3.connect(db)
    out = tuple(c.execute(q).fetchone()[0] for q in ("SELECT COUNT(*) FROM goal", "SELECT COUNT(*) FROM goal_trace"))
    c.close()
    return out


class Erasure(unittest.TestCase):
    def test_a_canary_is_gone_from_the_file_bytes(self):
        db = fresh("canary", [CANARY])
        self.assertIn(CANARY.encode(), db.read_bytes())
        E.erase_all_goals(db)
        self.assertEqual(rows(db), (0, 0))
        self.assertNotIn(CANARY.encode(), db.read_bytes())

    def test_no_activity_counter_remains_and_a_rerun_is_harmless(self):
        db = fresh("seq", ["TEST_ONLY a"])
        E.erase_all_goals(db)
        E.erase_all_goals(db)
        c = sqlite3.connect(db)
        self.assertEqual(c.execute("SELECT COUNT(*) FROM sqlite_sequence WHERE name LIKE 'goal%'").fetchone()[0], 0)
        c.close()

    def test_an_unknown_table_refuses_and_changes_nothing(self):
        db = fresh("foreign", ["TEST_ONLY a"])
        c = sqlite3.connect(db)
        c.execute("CREATE TABLE test_only_foreign (x)")
        c.commit(); c.close()
        with self.assertRaises(E.Refused):
            E.erase_all_goals(db)
        self.assertEqual(rows(db)[0], 1)

    def test_a_held_write_lock_refuses(self):
        db = fresh("lock", ["TEST_ONLY a"])
        c = sqlite3.connect(db, isolation_level=None)
        c.execute("BEGIN IMMEDIATE")
        with self.assertRaises(E.Refused):
            E.erase_all_goals(db)
        c.execute("ROLLBACK"); c.close()
        self.assertEqual(rows(db)[0], 1)

    def test_retention_removes_only_old_terminal_goals(self):
        db = fresh("retain", ["TEST_ONLY old done", "TEST_ONLY new done", "TEST_ONLY old active"])
        old = (datetime.now(timezone.utc) - timedelta(days=40)).isoformat()
        c = sqlite3.connect(db)
        c.execute("UPDATE goal SET lifecycle_state='COMPLETED', updated_at=? WHERE goal_id='g.test-only-0'", (old,))
        c.execute("UPDATE goal SET lifecycle_state='COMPLETED' WHERE goal_id='g.test-only-1'")
        c.execute("UPDATE goal SET updated_at=? WHERE goal_id='g.test-only-2'", (old,))
        c.commit(); c.close()
        self.assertEqual(E.prune_terminal_goals(db), 1)
        c = sqlite3.connect(db)
        self.assertEqual({r[0] for r in c.execute("SELECT goal_id FROM goal")}, {"g.test-only-1", "g.test-only-2"})
        self.assertEqual(c.execute("SELECT COUNT(*) FROM goal_trace WHERE goal_id='g.test-only-0'").fetchone()[0], 0)
        c.close()
        self.assertNotIn(b"old done", db.read_bytes())

    def test_a_hold_blocks_erasure_and_changes_nothing(self):
        db = fresh("hold", [CANARY])
        before = db.read_bytes()
        self.assertEqual(E.forget_goals_unless_held(db, True), "held")
        self.assertEqual(db.read_bytes(), before)
        self.assertEqual(E.forget_goals_unless_held(db, False), "erased")
        self.assertTrue(E.goal_rows_zero(db))

    def test_goal_rows_zero_sees_a_remaining_row_and_writes_nothing(self):
        db = fresh("zero", [CANARY])
        before = db.read_bytes()
        self.assertFalse(E.goal_rows_zero(db))
        self.assertEqual(db.read_bytes(), before)

    def test_a_backup_with_goal_rows_cannot_be_restored(self):
        self.assertFalse(E.backup_restore_allowed(fresh("bk1", [CANARY])))
        self.assertTrue(E.backup_restore_allowed(fresh("bk2")))

    def test_channel_label_drops_the_session_key(self):
        self.assertEqual(E.channel_label("lilith_os:TEST_ONLY-session-7"), "lilith_os")
        self.assertEqual(E.channel_label("discord:12345"), "discord")
        for bad in (None, "", "a b:c", "x/y"):
            self.assertEqual(E.channel_label(bad), "unknown")

    def test_forget_step_honours_a_hold_marker_and_reports_its_check(self):
        db = fresh("step", [CANARY])
        hold = Path(tmp) / "hold.marker"
        hold.write_text("TEST_ONLY")
        self.assertEqual(E.forget_step(db, hold), {"goal_forget": "held", "goal_rows_zero": False})
        hold.unlink()
        self.assertEqual(E.forget_step(db, hold), {"goal_forget": "erased", "goal_rows_zero": True})

    def test_a_hold_marker_that_cannot_be_checked_counts_as_a_hold(self):
        class Unreadable:
            def exists(self):
                raise OSError("TEST_ONLY")
        db = fresh("step2", [CANARY])
        self.assertEqual(E.forget_step(db, Unreadable())["goal_forget"], "held")

    def test_the_retention_entry_point_prints_a_count_and_refuses_cleanly(self):
        import contextlib, io
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.assertEqual(E.main(["x", "prune", str(fresh("cli"))]), 0)
            self.assertEqual(E.main(["x"]), 2)
        self.assertIn("GOAL_RETENTION pruned=0", out.getvalue())
        self.assertNotIn(CANARY, out.getvalue())


if __name__ == "__main__":
    unittest.main()
