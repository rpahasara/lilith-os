# -*- coding: utf-8 -*-
"""P-4 P4-4: the commitment sync against the REAL Goals API (in-process, throwaway DB, TEST_ONLY): typed
commitment goals, SCHEDULED source, scheduler deadline, FSM paths with reasons in the goal trace, idempotency."""
import importlib.util
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

try:
    from fastapi.testclient import TestClient
except Exception:       # CI may have no httpx
    TestClient = None

ROOT = Path(__file__).resolve().parents[3]
OWNER = "1111794198"
T0 = 1_800_000_000.0


def _load_sync():
    spec = importlib.util.spec_from_file_location(
        "commitment_sync_it", ROOT / "deploy/prod/hermes_scripts/commitment_sync.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@unittest.skipIf(TestClient is None, "httpx not installed")
class CommitmentGoalsIntegration(unittest.TestCase):
    def setUp(self):
        env = {"LILITH_OS_WRITE_AUTH": "enforced", "LILITH_OS_WRITE_TOKEN": "TEST_ONLY" + "w" * 32,
               "LILITH_OS_READ_AUTH": "enforced", "LILITH_OS_READ_TOKEN": "TEST_ONLY" + "r" * 32,
               "LILITH_OS_TRUST_LOOPBACK": "1"}
        patch = mock.patch.dict(os.environ, env)
        patch.start()
        self.addCleanup(patch.stop)
        self.tmp = Path(tempfile.mkdtemp(prefix="commit-it-"))
        self.addCleanup(shutil.rmtree, self.tmp, True)
        app.DB = self.tmp / "core.db"
        app._goal_schema_ready = False
        app._goals_db().close()
        self.client = TestClient(app.app, client=("127.0.0.1", 40000), raise_server_exceptions=False)
        self.cs = _load_sync()
        self.home = self.tmp / "hermes"
        (self.home / "lilith_router").mkdir(parents=True)
        (self.home / "lilith_router" / "canonical_memory.json").write_text(
            json.dumps({"schemaVersion": 1, "enabled": True, "ownerTelegramUserIds": [OWNER]}), encoding="ascii")
        (self.home / "cron").mkdir()
        con = sqlite3.connect(self.home / "cron" / "executions.db")
        con.execute("CREATE TABLE executions (id TEXT PRIMARY KEY, job_id TEXT, source TEXT, process_id TEXT, pid INT,"
                    " process_started_at INT, status TEXT, claimed_at TEXT, started_at TEXT, finished_at TEXT, error TEXT)")
        con.commit()
        con.close()

    def api(self, method, path, body=None):
        r = self.client.request(method, path, json=body)
        if r.status_code >= 400:
            raise self.cs.urllib.error.HTTPError(path, r.status_code, r.text[:200], None, None)
        return r.json()

    def jobs(self, *jobs):
        (self.home / "cron" / "jobs.json").write_text(json.dumps({"jobs": list(jobs)}), encoding="utf-8")

    def test_reminder_lifecycle_on_the_real_goals_api(self):
        iso = self.cs._iso
        self.jobs({"id": "abc123", "name": "TEST_ONLY call", "origin": {"platform": "telegram", "chat_id": OWNER},
                   "schedule": {"kind": "once"}, "repeat": {"times": 1, "completed": 0},
                   "next_run_at": iso(T0 + 3600), "created_at": iso(T0), "enabled": True, "state": "scheduled"})
        self.cs.sync(self.home, now=T0 + 10, api=self.api)
        goals = self.client.get("/os/goals?type=commitment.once").json()["goals"]
        self.assertEqual(len(goals), 1)
        g = goals[0]
        self.assertEqual((g["lifecycleState"], g["source"], g["target"]), ("ACTIVE", "SCHEDULED",
                                                                          {"type": "hermes.cron", "id": "abc123"}))
        self.assertEqual(g["deadline"], iso(T0 + 3600))
        self.assertEqual(self.cs.sync(self.home, now=T0 + 20, api=self.api), [])          # idempotent
        self.cs.sync(self.home, now=T0 + 3600 + self.cs.GRACE_S + 60, api=self.api)        # missed
        self.assertEqual(self.client.get("/os/goals/" + g["goalId"]).json()["goal"]["lifecycleState"], "BLOCKED")
        con = sqlite3.connect(self.home / "cron" / "executions.db")
        con.execute("INSERT INTO executions VALUES ('e1','abc123','tick','p',1,0,'completed',?,?,?,NULL)",
                    (iso(T0 + 5500), iso(T0 + 5500), iso(T0 + 5510)))
        con.commit()
        con.close()
        self.jobs()                                                                         # auto-deleted after run
        self.cs.sync(self.home, now=T0 + 5600, api=self.api)
        final = self.client.get("/os/goals/" + g["goalId"]).json()["goal"]
        self.assertEqual(final["lifecycleState"], "COMPLETED")
        self.assertEqual(len(self.client.get("/os/goals?type=commitment.once").json()["goals"]), 1)


if __name__ == "__main__":
    unittest.main()
