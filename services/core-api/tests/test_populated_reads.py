# -*- coding: utf-8 -*-
"""Every route on a PROD-shaped synthetic store: what a read changes, and which routes need a credential. TEST_ONLY; throwaway DB; nothing leaves the process.

Counts follow the PROD audit of 2026-10-27: 3 goals, 7 tasks, 10 drafts, beliefs from career events. The rows are synthetic: real rows stay on PROD.
"""
import json
import os
import re
import shutil
import socket
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

SOURCES = """
CREATE TABLE IF NOT EXISTS companies (id INTEGER PRIMARY KEY, name TEXT);
CREATE TABLE IF NOT EXISTS job_applications (id INTEGER PRIMARY KEY AUTOINCREMENT, role_title TEXT, stage TEXT, status TEXT, last_activity TEXT, source_account TEXT, company_id INTEGER);
CREATE TABLE IF NOT EXISTS career_events (id INTEGER PRIMARY KEY AUTOINCREMENT, entity_type TEXT, entity_id INTEGER, source TEXT, confidence REAL, created_at TEXT);
"""
FILL = {"goal_id": "g.test-only-1", "task_id": "t.test-only-1", "draft_id": "d.test-only-1", "key": "career.application:1:status", "app_id": "1", "id": "1", "entity_id": "1", "entity_type": "career.application", "channel": "test"}
PUBLIC_WRITES = frozenset()     # no write route is public


def fill(path):
    return re.sub(r"\{([^}:]+)[^}]*\}", lambda m: FILL.get(m.group(1), "1"), path)


def populate(db):
    goals = app._goals_db()
    for i, priority in ((1, "HIGH"), (2, "NORMAL"), (3, "LOW")):
        app._create_goal_impl(goals, {"type": "test_only.synthetic", "title": f"TEST_ONLY goal {i}", "source": "SYSTEM_MAINTENANCE", "owner": "user", "priority": priority, "goalId": f"g.test-only-{i}"})
    goals.close()
    conn = app.db()
    app._ensure_world_schema(conn)
    app._ensure_world_ingest_schema(conn)
    conn.commit(); conn.close()
    app._tasks_db().close()
    app._drafts_db().close()
    c = sqlite3.connect(db)
    c.executescript(SOURCES)
    c.execute("INSERT INTO companies VALUES (1, 'TEST_ONLY company')")
    for i in range(1, 9):
        c.execute("INSERT INTO job_applications (role_title, stage, status, last_activity, source_account, company_id) VALUES (?, 'interview', 'open', '2026-10-01', 'acct', 1)", (f"TEST_ONLY role {i}",))
        c.execute("INSERT INTO career_events (entity_type, entity_id, source, confidence, created_at) VALUES ('job_application', ?, 'test', 0.9, '2026-10-01')", (i,))
    c.commit(); c.close()
    app.world_ingest_from_events()
    c = sqlite3.connect(db)
    columns = {t: [r[1] for r in c.execute(f"PRAGMA table_info({t})")] for t in ("tasks", "drafts")}
    for table, count, prefix in (("tasks", 7, "t.test-only-"), ("drafts", 10, "d.test-only-")):
        for i in range(1, count + 1):
            values = {name: 1 for name in columns[table]}
            values.update({columns[table][0]: f"{prefix}{i}", "status": "queued" if table == "tasks" else "created", "kind": "followup", "title": "TEST_ONLY", "subject": "TEST_ONLY", "body": "TEST_ONLY", "target_type": "career.application", "target_id": str(i),
                           "idempotency_key": f"k{table}{i}", "content_hash": "h", "payload_json": "{}", "input_json": "{}", "metadata_json": "{}"})
            names = ",".join(columns[table])
            c.execute(f"INSERT INTO {table} ({names}) VALUES ({','.join('?' * len(columns[table]))})", [values[n] for n in columns[table]])
    c.commit(); c.close()


def snapshot(db):
    c = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        tables = [r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name != 'sqlite_sequence' ORDER BY name")]
        return {t: c.execute(f'SELECT * FROM "{t}" ORDER BY 1').fetchall() for t in tables}
    finally:
        c.close()


def routes(*methods):
    return sorted({(m, r.path) for r in app.app.routes if getattr(r, "methods", None) for m in r.methods if m in methods})


@unittest.skipIf(TestClient is None, "httpx not installed")
class Populated(unittest.TestCase):
    def setUp(self):
        patch = mock.patch.dict(os.environ, {"LILITH_OS_READ_AUTH": "open-acknowledged", "LILITH_OS_WRITE_AUTH": "open-acknowledged"})
        patch.start()
        self.addCleanup(patch.stop)
        os.environ.pop("LILITH_OS_FOCUS_READ_ONLY", None)
        self.tmp = Path(tempfile.mkdtemp(prefix="populated-"))
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.db = self.tmp / "core.db"
        app.DB = self.db
        app._goal_schema_ready = False
        app._world_schema_ready = False
        populate(self.db)
        real = socket.socket.connect
        def local_only(sock, address):
            if isinstance(address, tuple) and address[0] not in ("127.0.0.1", "::1", "localhost", "testserver"):
                raise OSError("TEST_ONLY no route off this host")
            return real(sock, address)
        net = mock.patch.object(socket.socket, "connect", local_only)
        net.start()
        self.addCleanup(net.stop)
        self.client = TestClient(app.app, raise_server_exceptions=False)

    def sweep(self):
        """Each GET route once, in order. Returns {path: tables whose rows changed}."""
        found = {}
        for _, path in routes("GET"):
            before = snapshot(self.db)
            self.client.get(fill(path))
            after = snapshot(self.db)
            changed = sorted(t for t in set(before) | set(after) if before.get(t) != after.get(t))
            if changed:
                found[path] = changed
        return found

    def test_the_store_has_the_audited_shape(self):
        rows = snapshot(self.db)
        self.assertEqual((len(rows["goal"]), len(rows["tasks"]), len(rows["drafts"])), (3, 7, 10))
        self.assertGreaterEqual(len(rows["world_belief"]), 24)

    def test_today_a_changed_focus_writes_a_trace_and_no_other_read_writes(self):
        """The finding: focus is the only GET that writes owner data. It writes when focus changes, so a held focus is not one row but one per change."""
        found = self.sweep()
        print("\nGET_WRITES_DEFAULT", json.dumps(found))
        self.assertEqual(found, {"/os/goals/focus": ["goal_trace"]})

    def test_the_focus_trace_grows_only_when_the_focus_changes(self):
        trace = lambda: len(snapshot(self.db)["goal_trace"])
        self.client.get("/os/goals/focus")
        settled = trace()
        for _ in range(3):
            self.client.get("/os/goals/focus")
        self.assertEqual(trace(), settled)

    def test_with_the_flag_no_get_route_changes_a_row(self):
        os.environ["LILITH_OS_FOCUS_READ_ONLY"] = "1"
        self.assertEqual(self.sweep(), {})

    def test_with_the_flag_the_answer_is_the_same(self):
        first = self.client.get("/os/goals/focus").json()
        os.environ["LILITH_OS_FOCUS_READ_ONLY"] = "1"
        second = self.client.get("/os/goals/focus").json()
        self.assertEqual({k: v for k, v in first.items() if k != "evaluatedAt"}, {k: v for k, v in second.items() if k != "evaluatedAt"})


@unittest.skipIf(TestClient is None, "httpx not installed")
class EveryRoute(unittest.TestCase):
    def setUp(self):
        patch = mock.patch.dict(os.environ)
        patch.start()
        self.addCleanup(patch.stop)
        for name in ("LILITH_OS_READ_AUTH", "LILITH_OS_READ_TOKEN", "LILITH_OS_WRITE_AUTH", "LILITH_OS_WRITE_TOKEN", "LILITH_OS_OWNER_CAPTURE_TOKEN"):
            os.environ.pop(name, None)
        self.tmp = Path(tempfile.mkdtemp(prefix="routes-"))
        self.addCleanup(shutil.rmtree, self.tmp, True)
        app.DB = self.tmp / "core.db"
        app._goal_schema_ready = False
        self.client = TestClient(app.app, raise_server_exceptions=False)

    def call(self, method, path, headers=None):
        return self.client.request(method, fill(path), json={"message": "TEST_ONLY", "action": "open"}, headers=headers or {})

    def test_no_route_answers_without_configuration_except_health(self):
        with mock.patch.object(app, "_relay_conversation", side_effect=AssertionError("relayed")):
            for method, path in routes("GET", "POST", "PATCH", "PUT", "DELETE"):
                status = self.call(method, path).status_code
                if path == "/health":
                    self.assertEqual(status, 200)
                else:
                    self.assertIn(status, (401, 403, 503), f"{method} {path}")
        self.assertFalse(app.DB.exists())

    def test_no_route_answers_a_stranger_once_configured(self):
        os.environ.update(LILITH_OS_READ_AUTH="enforced", LILITH_OS_READ_TOKEN="TEST_ONLY" + "r" * 32, LILITH_OS_WRITE_AUTH="enforced", LILITH_OS_WRITE_TOKEN="TEST_ONLY" + "w" * 32)
        wrong = {"X-LILITH-OS-Read": "wrong", "X-LILITH-OS-Write": "wrong"}
        with mock.patch.object(app, "_relay_conversation", side_effect=AssertionError("relayed")):
            for method, path in routes("GET", "POST", "PATCH", "PUT", "DELETE"):
                if path != "/health":
                    self.assertIn(self.call(method, path, wrong).status_code, (401, 403, 503), f"{method} {path}")

    def test_the_conversation_relays_only_for_the_owner(self):
        token = "TEST_ONLY" + "r" * 32
        os.environ.update(LILITH_OS_READ_AUTH="enforced", LILITH_OS_READ_TOKEN=token)
        with mock.patch.object(app, "_relay_conversation", return_value={"reply": "TEST_ONLY"}) as relay:
            self.assertEqual(self.client.post("/os/conversation", json={"message": "TEST_ONLY"}).status_code, 401)
            relay.assert_not_called()
            self.assertEqual(self.client.post("/os/conversation", json={"message": "TEST_ONLY"}, headers={"X-LILITH-OS-Read": token}).status_code, 200)
            relay.assert_called_once()

    def test_the_docs_are_not_a_way_around_it(self):
        for path in ("/docs", "/redoc", "/openapi.json"):
            self.assertIn(self.client.get(path).status_code, (401, 503), path)


if __name__ == "__main__":
    unittest.main()
