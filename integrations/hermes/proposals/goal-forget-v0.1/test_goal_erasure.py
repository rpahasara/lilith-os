"""Candidate goal erasure on the real Core API schema. TEST_ONLY; throwaway DBs. Needs fastapi.

    python -B -m unittest discover -s integrations/hermes/proposals/goal-forget-v0.1 -p "test_*.py"
"""

import importlib.util
import os
import shutil
import sqlite3
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

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

    def seed_other_stores(self, db, status="created", updated=1):
        app.DB = db
        app._tasks_db().close()
        app._drafts_db().close()
        c = sqlite3.connect(db)
        c.execute("INSERT INTO tasks (task_id, schema_version, revision, source, kind, status, title, created_at, updated_at, record_json) VALUES ('t', 1, 1, 's', 'k', 'running', ?, 1, 1, ?)", (CANARY, CANARY))
        c.execute("INSERT INTO drafts (draft_id, schema_version, kind, status, target_type, target_id, body, content_hash, idempotency_key, created_at, updated_at) VALUES ('d', 1, 'followup', ?, 'career.application', '1', ?, 'h', 'k', 1, ?)", (status, CANARY, updated))
        c.commit(); c.close()

    def test_task_and_draft_text_is_gone_from_the_file_bytes(self):
        db = fresh("other")
        self.seed_other_stores(db)
        self.assertIn(CANARY.encode(), db.read_bytes())
        E.erase_tasks_and_drafts(db)
        self.assertNotIn(CANARY.encode(), db.read_bytes())
        E.erase_tasks_and_drafts(db)

    def test_retention_removes_only_old_discarded_drafts(self):
        db = fresh("dr1")
        self.seed_other_stores(db, status="created")
        self.assertEqual(E.prune_discarded_drafts(db), 0)
        db = fresh("dr2")
        self.seed_other_stores(db, status="discarded")
        self.assertEqual(E.prune_discarded_drafts(db), 1)

    def seed_world(self, db, superseded=0, ingested="2020-01-01T00:00:00+00:00"):
        app.DB = db
        app._world_schema_ready = False
        conn = app.db()
        app._ensure_world_schema(conn)
        app._ensure_world_ingest_schema(conn)
        conn.close()
        c = sqlite3.connect(db)
        c.execute("INSERT INTO world_belief (key, entity_type, entity_id, predicate, value_json, lifecycle_state, epistemic_state, confidence, confidence_tier, confidence_basis, created_at, updated_at) "
                  "VALUES ('k', 'career.application', '14', 'p', ?, 'ACTIVE', 'OBSERVED', 1, 'HIGH', 'b', 'a', 'a')", (f'"{CANARY}"',))
        cols = [r[1] for r in c.execute("PRAGMA table_info(world_belief_evidence)")]
        c.execute("INSERT INTO world_belief_evidence (belief_key, source_class, value_json, epistemic_state, confidence, ingested_at, superseded) VALUES ('k', 's', ?, 'OBSERVED', 1, ?, ?)", (f'"{CANARY}"', ingested, superseded))
        c.execute("INSERT INTO world_ingest_cursor (name, last_id, updated_at) VALUES ('career_events', 41, 'a')")
        c.commit(); c.close()

    def test_world_model_text_is_gone_and_the_cursor_stays(self):
        db = fresh("world")
        self.seed_world(db)
        self.assertFalse(E.world_rows_zero(db))
        E.erase_world_model(db)
        self.assertTrue(E.world_rows_zero(db))
        self.assertNotIn(CANARY.encode(), db.read_bytes())
        c = sqlite3.connect(db)
        self.assertEqual(c.execute("SELECT last_id FROM world_ingest_cursor").fetchone()[0], 41)    # resetting it would rebuild the beliefs
        c.close()
        E.erase_world_model(db)

    def test_retention_removes_only_old_superseded_evidence(self):
        db = fresh("ev1")
        self.seed_world(db, superseded=0)
        self.assertEqual(E.prune_superseded_evidence(db), 0)
        db = fresh("ev2")
        self.seed_world(db, superseded=1)
        self.assertEqual(E.prune_superseded_evidence(db), 1)
        db = fresh("ev3")
        self.seed_world(db, superseded=1, ingested=datetime.now(timezone.utc).isoformat())
        self.assertEqual(E.prune_superseded_evidence(db), 0)

    def test_an_unknown_table_refuses_world_erasure_so_prod_needs_its_own_list(self):
        db = fresh("world-other")
        self.seed_world(db)
        c = sqlite3.connect(db); c.execute("CREATE TABLE career_events (id INTEGER)"); c.commit(); c.close()
        with self.assertRaises(E.Refused):
            E.erase_world_model(db)
        self.assertFalse(E.world_rows_zero(db))


class Retention(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="retention-"))
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.db = self.tmp / "core.db"
        self.hold = self.tmp / "hold"
        conn = sqlite3.connect(self.db)
        conn.executescript("""
            CREATE TABLE goal (goal_id TEXT PRIMARY KEY, lifecycle_state TEXT, updated_at TEXT);
            CREATE TABLE goal_trace (goal_id TEXT);
            CREATE TABLE tasks (task_id TEXT PRIMARY KEY, status TEXT, updated_at INTEGER);
            CREATE TABLE drafts (draft_id TEXT PRIMARY KEY, status TEXT, updated_at INTEGER);
            CREATE TABLE world_belief_evidence (id INTEGER PRIMARY KEY, belief_key TEXT, created_at TEXT, superseded INTEGER);
        """)
        for task_id, status, at in (("old-done", "succeeded", 1), ("old-open", "running", 1), ("new-done", "succeeded", 4102444800)):
            conn.execute("INSERT INTO tasks VALUES (?,?,?)", (task_id, status, at))
        for draft_id, status, at in (("old-gone", "discarded", 1), ("old-live", "created", 1)):
            conn.execute("INSERT INTO drafts VALUES (?,?,?)", (draft_id, status, at))
        conn.commit(); conn.close()

    def rows(self, table):
        conn = sqlite3.connect(self.db)
        try:
            return sorted(r[0] for r in conn.execute(f"SELECT {'task_id' if table == 'tasks' else 'draft_id'} FROM {table}"))
        finally:
            conn.close()

    def test_tasks_only_go_when_their_age_was_decided(self):
        with mock.patch.object(E, "prune_superseded_evidence", return_value=0):
            result = E.retention_step(self.db, self.hold)
            self.assertEqual(result["tasks"], "not_decided")
            self.assertEqual(self.rows("tasks"), ["new-done", "old-done", "old-open"])
            self.assertEqual(E.retention_step(self.db, self.hold, task_days=90)["tasks"], 1)
        self.assertEqual(self.rows("tasks"), ["new-done", "old-open"])

    def test_discarded_drafts_go_and_live_ones_never_age_out(self):
        with mock.patch.object(E, "prune_superseded_evidence", return_value=0):
            self.assertEqual(E.retention_step(self.db, self.hold)["drafts"], 1)
        self.assertEqual(self.rows("drafts"), ["old-live"])

    def test_a_hold_stops_every_part(self):
        self.hold.write_text("TEST_ONLY", encoding="utf-8")
        self.assertEqual(E.retention_step(self.db, self.hold, task_days=1), {"result": "held"})
        self.assertEqual(self.rows("tasks"), ["new-done", "old-done", "old-open"])
        self.assertEqual(self.rows("drafts"), ["old-gone", "old-live"])

    def test_an_unreadable_hold_counts_as_a_hold(self):
        class Broken:
            def exists(self):
                raise OSError("TEST_ONLY")
        self.assertEqual(E.retention_step(self.db, Broken(), task_days=1), {"result": "held"})


if __name__ == "__main__":
    unittest.main()
