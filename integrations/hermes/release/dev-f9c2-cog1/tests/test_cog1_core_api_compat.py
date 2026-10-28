"""Core API compatibility of f293e72-f9c2-cog1 against the real Core API source. TEST_ONLY synthetic data.

    python -m unittest discover -s integrations/hermes/release/dev-f9c2-cog1/tests -p "test_*.py"

services/core-api/app.py (unchanged since the last DEV Core API deployment, d82f7da) runs in-process on a throwaway
SQLite database seeded with synthetic rows. The adapter's transport is bridged to FastAPI's TestClient, so every
lane reads through the real route handlers with no socket. Startup events (the maintenance thread) are not run.
"""

from __future__ import annotations

import hashlib
import io
import json
import os
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

COG1 = Path(__file__).resolve().parents[1]
REPO = COG1.parents[3]
sys.path.insert(0, str(REPO / "integrations" / "hermes" / "overlays" / "dev-unified-cognition" / "tools"))

import assemble_dev_cognition  # noqa: E402

RECRUITER_CANARY = "test-only-recruiter-canary@example.invalid"
MESSAGE_CANARY = "TEST_ONLY_MSG_CANARY_5R"
MESSAGES = {
    "belief": f"TEST_ONLY what do you believe about application 14? {MESSAGE_CANARY}",
    "pending": f"TEST_ONLY what is pending right now? {MESSAGE_CANARY}",
    "draft": f"TEST_ONLY create a follow-up draft for application 14 {MESSAGE_CANARY}",
    "goal_query": f"TEST_ONLY which goal has priority? {MESSAGE_CANARY}",
    "goal_create": f"TEST_ONLY track application 14 as a goal {MESSAGE_CANARY}",
    "reasoning": f"TEST_ONLY what are my options for application 14? {MESSAGE_CANARY}",
    "planning": f"TEST_ONLY make a plan to follow up on application 14 but do not create anything {MESSAGE_CANARY}",
    "ethics": f"TEST_ONLY is it okay to share my salary with the recruiter? {MESSAGE_CANARY}",
}
LANES = ("cognitive", "goals", "reasoning", "workspace", "motivation", "planning", "ethics")

_TMP = tempfile.TemporaryDirectory(prefix="cog1-coreapi-", ignore_cleanup_errors=True)   # Windows: open SQLite
TMP = Path(_TMP.name)
HOME = TMP / "hermes-home"
DB = TMP / "core" / "lilith.db"
STATE = {}


def setUpModule():
    try:
        import fastapi.testclient  # noqa: F401  (Core API test dependency, services/core-api/requirements.txt)
    except ImportError:
        raise unittest.SkipTest("fastapi/httpx not installed: Core API compatibility NOT RUN")
    DB.parent.mkdir(parents=True)
    saved = {k: os.environ.get(k) for k in ("LILITH_HOME", "LILITH_DATA_DIR", "LILITH_DB_PATH", "HERMES_HOME")}
    os.environ.update(LILITH_HOME=str(TMP / "core"), LILITH_DATA_DIR=str(DB.parent), LILITH_DB_PATH=str(DB),
                      HERMES_HOME=str(TMP / "core-hermes"))
    sys.path.insert(0, str(REPO / "services" / "core-api"))
    import app as core                                       # the real Core API module
    from fastapi.testclient import TestClient
    core.DB = DB
    STATE["core"], STATE["client"] = core, TestClient(core.app)
    _seed(core, STATE["client"])
    for k, v in saved.items():
        os.environ.pop(k, None) if v is None else os.environ.__setitem__(k, v)

    assert assemble_dev_cognition.assemble(HOME) == []
    (HOME / "router.yaml").replace(HOME / "lilith_router" / "router.yaml")
    os.environ["HERMES_HOME"] = str(HOME)
    sys.path.insert(0, str(HOME))
    from lilith_router import gateway_integration, reasoning, world_context
    STATE.update(gi=gateway_integration, wc=world_context, reasoning=reasoning)


def tearDownModule():
    for mod in [m for m in sys.modules if m == "lilith_router" or m.startswith("lilith_router.") or m == "app"]:
        del sys.modules[mod]
    _TMP.cleanup()


def _seed(core, client):
    with sqlite3.connect(DB) as c:
        c.executescript(
            "CREATE TABLE companies (id INTEGER PRIMARY KEY, name TEXT);"
            "CREATE TABLE people (id INTEGER PRIMARY KEY, name TEXT, email TEXT);"
            "CREATE TABLE job_applications (id INTEGER PRIMARY KEY, company_id INTEGER, role_title TEXT, stage TEXT,"
            " status TEXT, source_account TEXT, confidence REAL, first_seen TEXT, last_activity TEXT,"
            " recruiter_id INTEGER);"
            "CREATE TABLE career_activities (id INTEGER PRIMARY KEY, application_id INTEGER, title TEXT,"
            " occurred_at TEXT);")
        c.execute("INSERT INTO companies VALUES (1, 'TEST_ONLY Co')")
        c.execute("INSERT INTO people VALUES (1, 'TEST_ONLY Recruiter', ?)", (RECRUITER_CANARY,))
        c.execute("INSERT INTO job_applications VALUES (14, 1, 'TEST_ONLY Engineer', 'interviewing', 'active',"
                  " 'test-only', 0.9, '2026-10-01T00:00:00Z', '2026-10-20T00:00:00Z', 1)")
        c.execute("INSERT INTO career_activities VALUES (1, 14, 'TEST_ONLY interview scheduled', '2026-10-20')")
    core.world_ingest_career()
    tasks = core._tasks_db()
    try:
        tasks.execute(
            "INSERT INTO tasks (task_id, schema_version, revision, source, kind, status, title, created_at,"
            " updated_at, ended_at, last_operation_id, record_json) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            ("t.test.1", 1, 1, "core", "career", "waiting_for_approval", "TEST_ONLY review", 1, 2, None, None,
             json.dumps({"taskId": "t.test.1", "title": "TEST_ONLY review", "status": "waiting_for_approval",
                         "approvalState": "required", "createdAt": 1, "updatedAt": 2})))
        tasks.commit()
    finally:
        tasks.close()
    draft = client.post("/os/drafts", json={
        "draftId": "d.test.seed1", "idempotencyKey": "test.seed.1", "kind": "career_followup",
        "target": {"type": "application", "id": "14"}, "subject": "TEST_ONLY subject", "body": "TEST_ONLY body",
        "stepId": "s3", "schemaVersion": 1})
    assert draft.status_code in (200, 201), draft.text
    goal = client.post("/os/goals", json={
        "type": "career.followup", "title": "TEST_ONLY follow up on application 14", "source": "USER_REQUESTED",
        "owner": "user", "priority": "NORMAL", "target": {"type": "career.application", "id": "14"},
        "sourceChannel": "test", "createdVia": "conversation"})
    assert goal.status_code in (200, 201), goal.text
    STATE["goal_id"] = goal.json()["goal"]["goalId"]


class FakeResponse(io.BytesIO):
    def __init__(self, body: bytes, code: int, content_type: str):
        super().__init__(body)
        self.code, self.headers = code, {"content-type": content_type}

    def getcode(self):
        return self.code

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()


class CoreApiBridge:
    """Adapter transport -> FastAPI TestClient. Records each request and the real response status."""

    def __init__(self, client):
        self.client, self.calls = client, []

    def open(self, req, timeout=None):
        path = req.full_url.split("127.0.0.1:8765", 1)[1]
        assert req.get_method() == "GET" and req.data is None, (req.get_method(), path)
        resp = self.client.get(path)
        self.calls.append((path, resp.status_code, resp.headers.get("content-type", "")))
        return FakeResponse(resp.content, resp.status_code, resp.headers.get("content-type", ""))


def table_digests() -> dict[str, tuple[int, str]]:
    with sqlite3.connect(DB) as c:
        names = [r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
        out = {}
        for n in names:
            rows = c.execute(f'SELECT * FROM "{n}" ORDER BY rowid').fetchall()
            out[n] = (len(rows), hashlib.sha256(repr(rows).encode()).hexdigest())
        return out


class CoreApiCompatibilityTest(unittest.TestCase):
    def setUp(self):
        self.gi, self.wc, self.reasoning = STATE["gi"], STATE["wc"], STATE["reasoning"]
        self.bridge = CoreApiBridge(STATE["client"])
        self.saved = (self.wc._OPENER, self.reasoning._default_model_call)
        self.wc._OPENER = self.bridge
        self.wc._BREAKER["open_until"] = 0.0
        self.prompts = []
        self.reasoning._default_model_call = lambda prompt: self.prompts.append(prompt) or "not json"
        self.log = TMP / f"{self._testMethodName}.log"

    def tearDown(self):
        self.wc._OPENER, self.reasoning._default_model_call = self.saved

    def configure(self, mode):
        import yaml
        router = HOME / "lilith_router" / "router.yaml"
        data = yaml.safe_load(router.read_text(encoding="utf-8"))
        data.update(log_path=str(self.log), cognitive_channels=["lilith_os"])
        for lane in LANES:
            data[f"{lane}_enabled"], data[f"{lane}_mode"] = True, mode
        router.write_text(yaml.safe_dump(data), encoding="utf-8")

    def route_all(self, tag):
        out = {}
        for key, message in MESSAGES.items():
            chat = f"{tag}-{key}"
            ctx = SimpleNamespace(source=SimpleNamespace(platform=SimpleNamespace(value="lilith_os"), chat_id=chat),
                                  session_key=f"agent:lilith_os:{chat}", message=message)
            out[key] = self.gi.route_turn(runner=SimpleNamespace(), ctx=ctx, model="dev-model", runtime_kwargs={},
                                          turn_route={"model": "dev-model"}, combined_ephemeral="TEST_ONLY base",
                                          cached_agent=None)
        return out

    def assert_every_read_is_a_200_json_from_an_allowlisted_route(self):
        self.assertTrue(self.bridge.calls)
        for path, status, ctype in self.bridge.calls:
            self.assertTrue(self.wc._path_allowed(path), path)
            self.assertEqual(status, 200, path)
            self.assertIn("application/json", ctype, path)

    def assert_only_focus_traces_changed(self, before, after):
        changed = {t for t in set(before) | set(after) if before.get(t) != after.get(t)}
        self.assertLessEqual(changed, {"goal_trace"})
        if "goal_trace" in changed:
            self.assertEqual(after["goal_trace"][0] - before["goal_trace"][0], 1)   # one arbitration record

    def test_shadow_reads_real_routes_calls_no_model_and_changes_only_a_focus_trace(self):
        self.configure("shadow")
        before = table_digests()
        results = self.route_all("shadow")
        after = table_digests()
        self.assertTrue(all(r is None for r in results.values()), results)
        self.assert_every_read_is_a_200_json_from_an_allowlisted_route()
        self.assertEqual(self.prompts, [])
        self.assert_only_focus_traces_changed(before, after)
        log = self.log.read_text(encoding="utf-8")
        for canary in (MESSAGE_CANARY, RECRUITER_CANARY, "TEST_ONLY Engineer", "TEST_ONLY review"):
            self.assertNotIn(canary, log)

    def test_live_lanes_ground_from_real_routes_and_write_nothing(self):
        self.configure("live")
        self.route_all("warm")                              # settle the one-off focus trace first
        self.bridge.calls.clear()
        self.prompts.clear()
        before = table_digests()
        results = self.route_all("live")
        after = table_digests()
        self.assertEqual(before, after)                     # drafts, goals, tasks, world, trace: no change at all
        self.assert_every_read_is_a_200_json_from_an_allowlisted_route()
        modes = {k: (v or {}).get("mode") for k, v in results.items()}
        self.assertEqual(modes["belief"], "cognitive")
        self.assertIn("career.application:14", results["belief"]["combined_ephemeral"])
        self.assertIn("interviewing", results["belief"]["combined_ephemeral"])
        self.assertIn("TASK t.test.1", results["pending"]["combined_ephemeral"])
        self.assertIn("DRAFT d.test.seed1", results["pending"]["combined_ephemeral"])
        # The seeded unsent draft for application 14 is reused (Slice 7.3 de-dup); no write is attempted.
        self.assertIn("existing draft reused", results["draft"]["combined_ephemeral"])
        self.assertIn("d.test.seed1", results["draft"]["combined_ephemeral"])
        self.assertEqual(modes["goal_query"], "goal")
        self.assertIn(STATE["goal_id"], results["goal_query"]["combined_ephemeral"])
        self.assertIn("could not track the goal", results["goal_create"]["combined_ephemeral"])
        self.assertEqual((modes["planning"], modes["ethics"]), ("planning", "ethics"))
        self.assertEqual(len(self.prompts), 1)              # Slice 9: the only model call, tool-less
        texts = [json.dumps(results)] + self.prompts + [self.log.read_text(encoding="utf-8")]
        for text in texts:
            self.assertNotIn(RECRUITER_CANARY, text)        # third-party contact data never reaches a prompt
            self.assertNotIn("TEST_ONLY Recruiter", text)


if __name__ == "__main__":
    unittest.main()
