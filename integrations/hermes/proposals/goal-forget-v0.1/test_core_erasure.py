"""Principal FORGET across the Core API DB, and the routes back, on the real app.py ingest. TEST_ONLY; throwaway DBs; no network.

    python -B integrations/hermes/proposals/goal-forget-v0.1/test_core_erasure.py
"""

import json
import os
import shutil
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO / "services" / "core-api"))

import app  # noqa: E402
import core_erasure as E  # noqa: E402
from goal_erasure import Refused  # noqa: E402

KEY = b"TEST_ONLY-erasure-key-0123456789-abcdef"
CANARY = "TEST_ONLY_FORGET_CANARY_5F"
SOURCES = """
CREATE TABLE IF NOT EXISTS companies (id INTEGER PRIMARY KEY, name TEXT);
CREATE TABLE IF NOT EXISTS job_applications (id INTEGER PRIMARY KEY, role_title TEXT, stage TEXT, status TEXT, last_activity TEXT, source_account TEXT, company_id INTEGER);
CREATE TABLE IF NOT EXISTS career_events (id INTEGER PRIMARY KEY AUTOINCREMENT, entity_type TEXT, entity_id INTEGER, source TEXT, confidence REAL, created_at TEXT);
"""
ALLOW = E.SOURCE_TABLES
VECTOR = "cc0def16c773e9b5fdce469075e7ae026b48e3046153c1b2ce9ed67ca4f8fe0b"


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="core-erasure-"))
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.db = self.tmp / "core.db"
        self.ledger = E.Ledger(self.tmp / "ledger.jsonl")
        self.hold = self.tmp / "hold"
        app.DB = self.db
        app._goal_schema_ready = False
        app._world_schema_ready = False
        conn = app._goals_db()
        app._create_goal_impl(conn, {"type": "test_only.synthetic", "title": f"{CANARY} goal", "source": "SYSTEM_MAINTENANCE", "owner": "user", "priority": "HIGH", "goalId": "g.test-only-f"})
        app._ensure_task_schema(conn) if hasattr(app, "_ensure_task_schema") else None
        conn.close()
        conn = app.db()
        app._ensure_world_schema(conn)
        app._ensure_world_ingest_schema(conn)
        conn.commit(); conn.close()
        c = sqlite3.connect(self.db)
        c.executescript(SOURCES)
        c.execute("CREATE TABLE IF NOT EXISTS tasks (task_id TEXT PRIMARY KEY, title TEXT)")
        c.execute("CREATE TABLE IF NOT EXISTS drafts (draft_id TEXT PRIMARY KEY, target_type TEXT, target_id TEXT, subject TEXT, body TEXT)")
        c.execute("INSERT INTO companies VALUES (1, ?)", (f"{CANARY} company",))
        c.execute("INSERT INTO job_applications VALUES (14, ?, 'interview', 'open', '2026-10-01', 'acct', 1)", (f"{CANARY} role",))
        c.execute("INSERT INTO tasks (task_id, title) VALUES ('t.test-only-f', ?)", (f"{CANARY} task",))
        c.execute("INSERT INTO drafts (draft_id, target_type, target_id, subject, body) VALUES ('d.test-only-f', 'career.application', '14', ?, ?)", (f"{CANARY} subject", f"{CANARY} body"))
        c.commit(); c.close()
        self.event()
        app.world_ingest_from_events()

    def event(self):
        c = sqlite3.connect(self.db)
        c.execute("INSERT INTO career_events (entity_type, entity_id, source, confidence, created_at) VALUES ('job_application', 14, 'test', 0.9, '2026-10-01')")
        c.commit(); c.close()

    def beliefs(self):
        c = sqlite3.connect(self.db)
        try:
            return c.execute("SELECT COUNT(*) FROM world_belief").fetchone()[0]
        finally:
            c.close()

    def erase(self, **kw):
        kw.setdefault("allow", ALLOW)
        return E.erase_principal(self.db, self.ledger, KEY, self.hold, **kw)


class Coverage(Base):
    def test_every_owner_store_goes_in_one_call(self):
        self.assertGreater(self.beliefs(), 0)
        result = self.erase()
        self.assertEqual(result["result"], "erased")
        self.assertEqual(set(result["rows_left"].values()), {0})
        for table in ("goal", "tasks", "drafts", "world_belief", "world_belief_evidence"):
            self.assertIn(table, result["rows_left"])

    def test_the_text_leaves_the_file_when_the_source_goes_too(self):
        self.erase(source_too=True)
        self.assertTrue(E.text_gone(self.db, [CANARY]))

    def test_the_source_tables_stay_unless_the_owner_decides(self):
        self.erase()
        c = sqlite3.connect(self.db)
        self.assertEqual(c.execute("SELECT COUNT(*) FROM job_applications").fetchone()[0], 1)
        c.close()
        self.assertFalse(E.text_gone(self.db, [CANARY]))      # which is why this is an owner decision, not a detail

    def test_a_failure_part_way_changes_nothing(self):
        before = E.rows_left(self.db)
        c = sqlite3.connect(self.db)
        c.executescript("CREATE TRIGGER keep BEFORE DELETE ON drafts BEGIN SELECT RAISE(ABORT, 'TEST_ONLY'); END;")
        c.commit(); c.close()
        with self.assertRaises(sqlite3.Error):
            self.erase()
        self.assertEqual(E.rows_left(self.db), before)
        self.assertEqual([e["state"] for e in self.ledger.entries()], ["PENDING", "ABORTED"])
        self.assertEqual(self.ledger.unfinished(), [])

    def test_a_hold_stops_it_and_an_unreadable_hold_counts_as_a_hold(self):
        self.hold.touch()
        self.assertEqual(self.erase(), {"result": "held"})
        self.assertGreater(self.beliefs(), 0)
        self.assertEqual(self.ledger.entries(), [])

    def test_a_held_lock_and_an_unknown_table_refuse_before_any_change(self):
        c = sqlite3.connect(self.db)
        c.execute("BEGIN IMMEDIATE")
        with self.assertRaises(Refused):
            self.erase()
        c.rollback()
        c.execute("CREATE TABLE mystery (x)")
        c.commit(); c.close()
        with self.assertRaises(Refused):
            self.erase()
        self.assertEqual(self.ledger.entries(), [])
        self.assertGreater(self.beliefs(), 0)

    def test_a_short_key_refuses(self):
        with self.assertRaises(Refused):
            E.erase_principal(self.db, self.ledger, b"short", self.hold, allow=ALLOW)


class RoutesBack(Base):
    def test_finding_the_kept_cursor_does_not_stop_a_new_event_rebuilding_a_belief(self):
        # Corrects an earlier claim. Ingest re-reads job_applications for any new event, so this needs the guard in the Core API, or the source gone.
        self.erase()
        self.assertEqual(self.beliefs(), 0)
        app.world_ingest_from_events()
        self.assertEqual(self.beliefs(), 0)                   # replay of old events: the cursor holds
        self.event()
        app.world_ingest_from_events()
        self.assertGreater(self.beliefs(), 0)                 # a new event: the belief is back

    def test_finding_the_full_career_ingest_rebuilds_everything(self):
        self.erase()
        app.world_ingest_career()
        self.assertGreater(self.beliefs(), 0)

    def test_erasing_the_source_closes_both_routes(self):
        self.erase(source_too=True)
        c = sqlite3.connect(self.db)
        c.execute("INSERT INTO career_events (entity_type, entity_id, source, confidence, created_at) VALUES ('job_application', 14, 'test', 0.9, '2026-10-02')")
        c.commit(); c.close()
        app.world_ingest_from_events()
        app.world_ingest_career()
        self.assertEqual(self.beliefs(), 0)

    def test_the_ledger_holds_no_content_and_a_keyed_hash_only(self):
        self.erase()
        raw = self.ledger.path.read_text(encoding="utf-8")
        for secret in (CANARY, "career.application", "acct", "g.test-only-f"):
            self.assertNotIn(secret, raw)
        self.assertIn(E.tombstone("career.application", "14", KEY), self.ledger.complete()[0]["tombstones"])
        self.assertNotEqual(E.tombstone("career.application", "14", KEY), E.tombstone("career.application", "14", KEY[::-1]))

    def test_the_tombstone_format_is_pinned_for_the_core_api_reader(self):
        # The same vector is pinned in services/core-api/tests/test_owner_security.py on the implementation branch.
        self.assertEqual(E.tombstone("career.application", "14", b"TEST_ONLY-vector-key-0123456789abcdef"), VECTOR)


class Restore(Base):
    def backup(self):
        path = self.tmp / "backup.db"
        shutil.copy2(self.db, path)
        return path

    def test_a_backup_from_before_the_erasure_needs_a_replay(self):
        backup = self.backup()
        self.erase()
        self.assertEqual(E.restore_decision(backup, self.ledger), "REPLAY")

    def test_replay_runs_on_a_quarantine_copy_and_clears_it(self):
        backup = self.backup()
        self.erase()
        result = E.replay_after_restore(backup, self.db, self.ledger, KEY, self.hold, allow=ALLOW)
        self.assertEqual(result["result"], "erased")
        self.assertEqual(set(E.rows_left(backup).values()), {0})
        self.assertEqual(E.restore_decision(backup, self.ledger), "CLEAN")

    def test_replay_refuses_the_live_file(self):
        with self.assertRaises(Refused):
            E.replay_after_restore(self.db, self.db, self.ledger, KEY, self.hold, allow=ALLOW)

    def test_an_unfinished_or_unreadable_ledger_refuses_a_restore(self):
        backup = self.backup()
        self.ledger.append({"erasure_id": "er.x", "state": "PENDING", "at": 1, "through_event_id": 0, "tombstones": [], "counts": {}})
        self.assertEqual(E.restore_decision(backup, self.ledger), "REFUSE")
        self.ledger.path.write_text("{not json\n", encoding="utf-8")
        self.assertEqual(E.restore_decision(backup, self.ledger), "REFUSE")

    def test_no_erasure_means_a_backup_is_clean(self):
        self.assertEqual(E.restore_decision(self.backup(), self.ledger), "CLEAN")

    def test_a_snapshot_from_before_an_erasure_is_named_and_nothing_is_deleted(self):
        self.erase()
        at = self.ledger.complete()[0]["at"]
        self.assertEqual(E.snapshot_report({"prod-20261027": at - 100, "after": at + 100}, self.ledger), {"prod-20261027": "PREDATES_ERASURE", "after": "AFTER_ERASURE"})


if __name__ == "__main__":
    unittest.main()
