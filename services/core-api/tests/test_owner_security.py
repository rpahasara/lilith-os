# -*- coding: utf-8 -*-
"""Owner-content read authentication, a read-only focus path, and the ingest guard after FORGET. TEST_ONLY; throwaway DBs; no network.

Pure decisions are tested directly, because CI has no httpx; the middleware test skips without it.
"""
import hashlib
import hmac
import json
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

TOKEN = "TEST_ONLY" + "r" * 32
KEY = b"TEST_ONLY-erasure-key-0123456789-abcdef"
VECTOR = "cc0def16c773e9b5fdce469075e7ae026b48e3046153c1b2ce9ed67ca4f8fe0b"     # the same vector is pinned on the ledger writer, in proposals/goal-forget-v0.1
SOURCES = """
CREATE TABLE IF NOT EXISTS companies (id INTEGER PRIMARY KEY, name TEXT);
CREATE TABLE IF NOT EXISTS job_applications (id INTEGER PRIMARY KEY, role_title TEXT, stage TEXT, status TEXT, last_activity TEXT, source_account TEXT, company_id INTEGER);
CREATE TABLE IF NOT EXISTS career_events (id INTEGER PRIMARY KEY AUTOINCREMENT, entity_type TEXT, entity_id INTEGER, source TEXT, confidence REAL, created_at TEXT);
"""


def stone(entity_id):
    return hmac.new(KEY, ("career.application|%s" % entity_id).encode("utf-8"), hashlib.sha256).hexdigest()


class Env(unittest.TestCase):
    def setUp(self):
        patch = mock.patch.dict(os.environ)
        patch.start()
        self.addCleanup(patch.stop)
        for name in ("LILITH_OS_READ_AUTH", "LILITH_OS_READ_TOKEN", "LILITH_WORLD_ERASURE_LEDGER", "LILITH_WORLD_ERASURE_KEY", "LILITH_OS_FOCUS_READ_ONLY"):
            os.environ.pop(name, None)
        self.tmp = Path(tempfile.mkdtemp(prefix="owner-security-"))
        self.addCleanup(shutil.rmtree, self.tmp, True)
        app.DB = self.tmp / "core.db"
        app._goal_schema_ready = False
        app._world_schema_ready = False


class ReadAuth(Env):
    def test_every_get_route_is_protected_unless_listed(self):
        gets = {r.path for r in app.app.routes if getattr(r, "methods", None) and "GET" in r.methods}
        self.assertEqual(app._PUBLIC_READS, {"/health"})
        os.environ.update(LILITH_OS_READ_AUTH="enforced", LILITH_OS_READ_TOKEN=TOKEN)
        for path in sorted(gets - app._PUBLIC_READS):
            with self.subTest(path=path):
                self.assertEqual(app._read_auth_decision(path, None), (401, "READ_NOT_AUTHENTICATED"))

    def test_the_owner_content_routes_are_all_in_that_set(self):
        gets = {r.path for r in app.app.routes if getattr(r, "methods", None) and "GET" in r.methods}
        for path in ("/os/goals", "/os/goals/focus", "/os/tasks", "/os/drafts", "/os/world", "/memory/records", "/career/applications", "/audit/recent", "/os/overview"):
            self.assertIn(path, gets)

    def test_unset_or_unknown_refuses(self):
        self.assertEqual(app._read_auth_decision("/os/goals", TOKEN), (503, "READ_AUTH_UNCONFIGURED"))
        for mode in ("", "ENFORCED", "off", "open", "true"):
            os.environ["LILITH_OS_READ_AUTH"] = mode
            self.assertEqual(app._read_auth_state(), "refused", mode)

    def test_a_short_or_missing_token_refuses(self):
        os.environ["LILITH_OS_READ_AUTH"] = "enforced"
        self.assertEqual(app._read_auth_decision("/os/goals", None)[0], 503)
        os.environ["LILITH_OS_READ_TOKEN"] = "short"
        self.assertEqual(app._read_auth_decision("/os/goals", "short")[0], 503)

    def test_enforced_needs_the_exact_token(self):
        os.environ.update(LILITH_OS_READ_AUTH="enforced", LILITH_OS_READ_TOKEN=TOKEN)
        for cred in (None, "", TOKEN[:-1], TOKEN + "x", "é"):
            self.assertEqual(app._read_auth_decision("/os/world", cred)[0], 401)
        self.assertIsNone(app._read_auth_decision("/os/world", TOKEN))

    def test_the_write_token_is_not_a_read_token(self):
        os.environ.update(LILITH_OS_READ_AUTH="enforced", LILITH_OS_READ_TOKEN=TOKEN, LILITH_OS_WRITE_TOKEN="TEST_ONLY" + "w" * 32)
        self.assertEqual(app._read_auth_decision("/os/world", os.environ["LILITH_OS_WRITE_TOKEN"])[0], 401)

    def test_open_must_be_explicit_and_health_stays_public(self):
        self.assertIsNone(app._read_auth_decision("/health", None))
        os.environ["LILITH_OS_READ_AUTH"] = "open-acknowledged"
        self.assertIsNone(app._read_auth_decision("/os/goals", None))

    def test_health_reports_the_state_and_no_secret(self):
        os.environ.update(LILITH_OS_READ_AUTH="enforced", LILITH_OS_READ_TOKEN=TOKEN)
        body = app.health()
        self.assertEqual(body["readAuth"], "enforced")
        self.assertNotIn(TOKEN, repr(body))

    def test_the_middleware_refuses_before_any_handler(self):
        try:
            from fastapi.testclient import TestClient
        except Exception:
            self.skipTest("httpx not installed")
        client = TestClient(app.app, raise_server_exceptions=False)
        self.assertEqual(client.get("/os/goals").status_code, 503)
        self.assertEqual(client.get("/health").status_code, 200)
        self.assertFalse(app.DB.exists())                     # refused before the handler could create a schema
        os.environ.update(LILITH_OS_READ_AUTH="enforced", LILITH_OS_READ_TOKEN=TOKEN)
        self.assertEqual(client.get("/os/goals").status_code, 401)
        self.assertEqual(client.get("/os/goals", headers={"X-LILITH-OS-Read": "wrong"}).status_code, 401)
        self.assertEqual(client.get("/os/goals", headers={"X-LILITH-OS-Read": TOKEN}).status_code, 200)


class FocusRead(Env):
    def goal(self):
        conn = app._goals_db()
        app._create_goal_impl(conn, {"type": "test_only.synthetic", "title": "TEST_ONLY", "source": "SYSTEM_MAINTENANCE", "owner": "user", "priority": "HIGH", "goalId": "g.test-only-s"})
        conn.close()

    def traces(self):
        conn = sqlite3.connect(app.DB)
        try:
            return conn.execute("SELECT COUNT(*) FROM goal_trace").fetchone()[0]
        finally:
            conn.close()

    def test_default_keeps_todays_trace(self):
        self.goal()
        before = self.traces()
        app.goal_focus()
        self.assertEqual(self.traces(), before + 1)

    def test_read_only_answers_the_same_and_writes_nothing(self):
        self.goal()
        before = self.traces()
        first = app.goal_focus()
        os.environ["LILITH_OS_FOCUS_READ_ONLY"] = "1"
        written = self.traces()
        self.assertEqual(written, before + 1)
        again = app.goal_focus()
        self.assertEqual(self.traces(), written)
        self.assertEqual(set(again), set(first))


class Guard(Env):
    def setUp(self):
        super().setUp()
        self.ledger = self.tmp / "ledger.jsonl"
        self.keyfile = self.tmp / "key"
        self.keyfile.write_bytes(KEY)
        conn = app.db()
        app._ensure_world_schema(conn)
        app._ensure_world_ingest_schema(conn)
        conn.commit(); conn.close()
        c = sqlite3.connect(app.DB)
        c.executescript(SOURCES)
        c.execute("INSERT INTO companies VALUES (1, 'TEST_ONLY')")
        for i in (14, 15):
            c.execute("INSERT INTO job_applications VALUES (?, 'TEST_ONLY', 'interview', 'open', '2026-10-01', 'acct', 1)", (i,))
        c.commit(); c.close()

    def event(self, entity_id):
        c = sqlite3.connect(app.DB)
        c.execute("INSERT INTO career_events (entity_type, entity_id, source, confidence, created_at) VALUES ('job_application', ?, 'test', 0.9, '2026-10-01')", (entity_id,))
        c.commit(); c.close()

    def beliefs(self):
        c = sqlite3.connect(app.DB)
        try:
            return sorted({r[0] for r in c.execute("SELECT entity_id FROM world_belief")})
        finally:
            c.close()

    def write(self, *entries):
        self.ledger.write_text("".join(json.dumps(e) + "\n" for e in entries), encoding="utf-8")
        os.environ.update(LILITH_WORLD_ERASURE_LEDGER=str(self.ledger), LILITH_WORLD_ERASURE_KEY=str(self.keyfile))

    def complete(self, through=0, stones=()):
        return {"erasure_id": "er.1", "state": "COMPLETE", "at": 1, "through_event_id": through, "tombstones": list(stones), "counts": {}}

    def test_the_tombstone_format_matches_the_ledger_writer(self):
        self.assertEqual(hmac.new(b"TEST_ONLY-vector-key-0123456789abcdef", b"career.application|14", hashlib.sha256).hexdigest(), VECTOR)

    def test_without_a_ledger_nothing_changes(self):
        self.event(14)
        app.world_ingest_from_events()
        self.assertEqual(self.beliefs(), ["14"])

    def test_a_new_event_cannot_rebuild_an_erased_application(self):
        self.write(self.complete(stones=[stone(14)]))
        self.event(14)
        result = app.world_ingest_from_events()
        self.assertEqual(self.beliefs(), [])
        self.assertEqual(result["new_events"], 1)             # the cursor still moves, so the event isn't retried for ever

    def test_a_different_application_still_ingests(self):
        self.write(self.complete(stones=[stone(14)]))
        self.event(14)
        self.event(15)
        app.world_ingest_from_events()
        self.assertEqual(self.beliefs(), ["15"])

    def test_the_full_career_ingest_skips_it_too(self):
        self.write(self.complete(stones=[stone(14)]))
        app.world_ingest_career()
        self.assertEqual(self.beliefs(), ["15"])

    def test_a_restored_cursor_cannot_replay_covered_events(self):
        self.event(15)
        self.event(15)
        self.write(self.complete(through=2))
        self.assertEqual(app.world_ingest_from_events()["new_events"], 0)
        self.assertEqual(self.beliefs(), [])

    def test_anything_unreadable_stops_ingest(self):
        self.event(15)
        self.write(self.complete())
        self.ledger.write_text("{not json\n", encoding="utf-8")
        self.assertEqual(app.world_ingest_from_events()["refused"], "erasure_ledger_unreadable")
        self.assertEqual(app.world_ingest_career()["refused"], "erasure_ledger_unreadable")
        self.assertEqual(self.beliefs(), [])

    def test_a_missing_key_stops_ingest(self):
        self.event(15)
        self.write(self.complete())
        self.keyfile.unlink()
        self.assertEqual(app.world_ingest_from_events()["refused"], "erasure_ledger_unreadable")

    def test_an_erasure_in_progress_stops_ingest(self):
        self.event(15)
        self.write({"erasure_id": "er.2", "state": "PENDING", "at": 1, "through_event_id": 0, "tombstones": [], "counts": {}})
        self.assertEqual(app.world_ingest_from_events()["refused"], "erasure_ledger_unreadable")
        self.assertEqual(self.beliefs(), [])


if __name__ == "__main__":
    unittest.main()
