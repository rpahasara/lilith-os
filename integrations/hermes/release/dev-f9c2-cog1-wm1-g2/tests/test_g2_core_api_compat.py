"""Goals LIVE of f293e72-f9c2-cog1-wm1-g2 against the real Core API source. TEST_ONLY; no socket; no model call.

    python -m unittest discover -s integrations/hermes/release/dev-f9c2-cog1-wm1-g2/tests -p "test_*.py"

As g1's test_g1_core_api_compat.py: services/core-api/app.py runs in-process behind FastAPI's TestClient, bridged to
the adapter's transport (GET only; any other method fails the test), with the exact g2 router.yaml. Each scenario
uses its own database:
- post-bootstrap (the DEV shape after the separately approved goal-schema gate: World Model schema, empty tasks, the
  goal tables created by the Core API's own _goals_db(), 0 rows);
- pre-bootstrap (today's DEV shape: no goal tables), as a contrast only: the g2 verifier refuses to start there;
- populated (post-bootstrap + ONE synthetic TEST_ONLY goal created by the Core API's own internal create).
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

G2 = Path(__file__).resolve().parents[1]
REPO = G2.parents[3]
sys.path.insert(0, str(REPO / "integrations" / "hermes" / "overlays" / "dev-unified-cognition" / "tools"))

import assemble_dev_cognition  # noqa: E402

QUERY = "TEST_ONLY which goal has priority?"
CREATE = "TEST_ONLY track application 21 as a goal"
CONTROL = "TEST_ONLY hey how are you"
CASUAL = "TEST_ONLY my goal for the weekend is to relax"
GOAL_READS = ["/os/goals?limit=200", "/os/goals/focus"]
POLICY = "[LILITH cognitive policy - Goal/Executive]"

_TMP = tempfile.TemporaryDirectory(prefix="g2-coreapi-", ignore_cleanup_errors=True)   # Windows: open SQLite
TMP = Path(_TMP.name)
HOME = TMP / "hermes-home"
LOG = TMP / "decisions.log"
STATE = {}


def setUpModule():
    try:
        import fastapi.testclient  # noqa: F401  (Core API test dependency, services/core-api/requirements.txt)
    except ImportError:
        raise unittest.SkipTest("fastapi/httpx not installed: Core API compatibility NOT RUN")
    first = TMP / "core" / "post.db"
    first.parent.mkdir(parents=True)
    saved = {k: os.environ.get(k) for k in ("LILITH_HOME", "LILITH_DATA_DIR", "LILITH_DB_PATH", "HERMES_HOME")}
    os.environ.update(LILITH_HOME=str(TMP / "core"), LILITH_DATA_DIR=str(first.parent), LILITH_DB_PATH=str(first),
                      HERMES_HOME=str(TMP / "core-hermes"))
    sys.path.insert(0, str(REPO / "services" / "core-api"))
    import app as core                                       # the real Core API module
    from fastapi.testclient import TestClient
    # raise_server_exceptions=False: a server error reaches the adapter as the HTTP 500 the real uvicorn returns
    # (for example /career/applications, whose tables are absent on DEV), not as a Python exception.
    STATE["core"], STATE["client"] = core, TestClient(core.app, raise_server_exceptions=False)
    for k, v in saved.items():
        os.environ.pop(k, None) if v is None else os.environ.__setitem__(k, v)
    assert assemble_dev_cognition.assemble(HOME) == []
    (HOME / "router.yaml").unlink()
    router = (G2 / "home" / "router.yaml").read_text(encoding="utf-8").replace(
        "/home/lilith/.hermes-dev/logs/lilith-router-decisions.log", LOG.as_posix())
    (HOME / "lilith_router" / "router.yaml").write_text(router, encoding="utf-8")
    os.environ["HERMES_HOME"] = str(HOME)
    sys.path.insert(0, str(HOME))
    from lilith_router import gateway_integration, world_context
    STATE.update(gi=gateway_integration, wc=world_context)


def tearDownModule():
    for mod in [m for m in sys.modules if m == "lilith_router" or m.startswith("lilith_router.") or m == "app"]:
        del sys.modules[mod]
    _TMP.cleanup()


def use_db(name: str, *, goal_schema: bool) -> Path:
    """A fresh DB of the DEV shape; with goal_schema, bootstrapped exactly as the gate would (the app's _goals_db())."""
    core = STATE["core"]
    db = TMP / "core" / f"{name}.db"
    core.DB = db
    core._goal_schema_ready = False                          # a freshly started Core API process
    conn = core.db()
    try:
        core._ensure_world_schema(conn)
    finally:
        conn.close()
    core._tasks_db().close()
    if goal_schema:
        core._goals_db().close()
    core._goal_schema_ready = False                          # the gate ran in its own process
    return db


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
    """Adapter transport -> FastAPI TestClient. GET only; records each request and the real response status."""

    def __init__(self, client):
        self.client, self.calls = client, []

    def open(self, req, timeout=None):
        path = req.full_url.split("127.0.0.1:8765", 1)[1]
        assert req.get_method() == "GET" and req.data is None, (req.get_method(), path)
        resp = self.client.get(path)
        self.calls.append((path, resp.status_code))
        return FakeResponse(resp.content, resp.status_code, resp.headers.get("content-type", ""))


def schema(db: Path) -> list[tuple]:
    with sqlite3.connect(db) as c:
        return c.execute("SELECT type, name, tbl_name, sql FROM sqlite_master ORDER BY type, name").fetchall()


def rows(db: Path) -> dict[str, tuple[int, str]]:
    with sqlite3.connect(db) as c:
        names = [r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
        return {n: (len(r := c.execute(f'SELECT * FROM "{n}" ORDER BY rowid').fetchall()),
                    hashlib.sha256(repr(r).encode()).hexdigest()) for n in names}


class GoalsLiveOnTheRealCoreApiTest(unittest.TestCase):
    def setUp(self):
        self.gi, self.wc = STATE["gi"], STATE["wc"]
        self.bridge = CoreApiBridge(STATE["client"])
        self.saved = self.wc._OPENER
        self.wc._OPENER = self.bridge
        self.wc._BREAKER["open_until"] = 0.0
        self.log0 = len(LOG.read_text(encoding="utf-8").splitlines()) if LOG.exists() else 0

    def tearDown(self):
        self.wc._OPENER = self.saved

    def route(self, message, chat):
        ctx = SimpleNamespace(source=SimpleNamespace(platform=SimpleNamespace(value="lilith_os"), chat_id=chat),
                              session_key=f"agent:lilith_os:{chat}", message=message)
        return self.gi.route_turn(runner=SimpleNamespace(), ctx=ctx, model="dev-model", runtime_kwargs={},
                                  turn_route={"model": "dev-model"}, combined_ephemeral="TEST_ONLY base",
                                  cached_agent=None)

    def new_log(self) -> list[dict]:
        return [json.loads(l) for l in LOG.read_text(encoding="utf-8").splitlines()[self.log0:]]

    def test_1_empty_store_query_reads_exactly_the_two_goal_routes_and_changes_nothing(self):
        db = use_db("post-empty", goal_schema=True)
        s0, r0 = schema(db), rows(db)
        self.assertEqual((r0["goal"][0], r0["goal_trace"][0]), (0, 0))
        res = self.route(QUERY, "live-query")
        self.assertEqual(self.bridge.calls, [(p, 200) for p in GOAL_READS])
        self.assertEqual(res["mode"], "goal")
        grounding = res["combined_ephemeral"]
        self.assertIn(POLICY, grounding)
        self.assertIn("(no goals are recorded in durable Goal/Executive state)", grounding)
        self.assertIn("CURRENT FOCUS: none", grounding)
        self.assertEqual((schema(db), rows(db)), (s0, r0))                   # no DDL, no row, no focus trace
        recs = self.new_log()
        goal = [r for r in recs if r.get("lane") == "goal"]
        self.assertEqual(len(goal), 1)
        self.assertEqual({k: goal[0][k] for k in ("lane", "goal_mode", "intent")},
                         {"lane": "goal", "goal_mode": "live",
                          "intent": {"goal_query": True, "goal_create": False, "app_id": None, "subtype": "priority"}})
        self.assertEqual(set(goal[0]), {"ts", "platform", "chat_id", "lane", "goal_mode", "intent", "event_id", "msg_chars", "msg_lines"})
        self.assertNotIn("which goal", json.dumps(recs))

    def test_2_track_as_goal_never_writes_and_says_it_could_not_track(self):
        db = use_db("post-create", goal_schema=True)
        s0, r0 = schema(db), rows(db)
        res = self.route(CREATE, "live-create")                             # the bridge fails on any non-GET
        paths = [p for p, _ in self.bridge.calls]
        self.assertEqual(paths[-2:], GOAL_READS)                            # after the (failed) title lookup
        self.assertTrue(all(p.startswith(("/career/applications", "/os/goals")) for p in paths), paths)
        self.assertEqual(self.wc.status()["reads_skipped_breaker"], 0)      # an HTTP 500 does not open the breaker
        self.assertIn("could not track the goal", res["combined_ephemeral"])
        self.assertEqual((schema(db), rows(db)), (s0, r0))                   # 0 goals, 0 traces
        self.assertGreaterEqual(self.wc.status()["writes_refused"], 1)      # the POST was refused by the adapter

    def test_3_unrelated_turn_makes_no_core_api_call(self):
        db = use_db("post-control", goal_schema=True)
        s0, r0 = schema(db), rows(db)
        self.assertIsNone(self.route(CONTROL, "live-control"))
        self.assertEqual(self.bridge.calls, [])
        self.assertEqual((schema(db), rows(db)), (s0, r0))

    def test_4_casual_goal_prose_is_a_detector_false_positive_reads_only(self):
        # Documented limitation: the PROD detector treats this as a goal query; in live it reads, never writes.
        db = use_db("post-casual", goal_schema=True)
        s0, r0 = schema(db), rows(db)
        res = self.route(CASUAL, "live-casual")
        self.assertEqual((res or {}).get("mode"), "goal")
        self.assertEqual([p for p, _ in self.bridge.calls], GOAL_READS)
        self.assertEqual((schema(db), rows(db)), (s0, r0))

    def test_5_contrast_pre_bootstrap_db_the_first_live_read_creates_the_goal_schema(self):
        # Why g2 refuses to start until the bootstrap gate ran: on today's DEV shape a live read is DDL.
        db = use_db("pre", goal_schema=False)
        before = rows(db)
        self.assertFalse({"goal", "goal_trace"} & set(before))
        self.route(QUERY, "pre-query")
        self.assertTrue({"goal", "goal_trace"} <= set(rows(db)))

    def test_6_populated_one_synthetic_goal_first_focus_read_writes_exactly_one_trace_row(self):
        core = STATE["core"]
        db = use_db("populated", goal_schema=True)
        conn = core._goals_db()
        try:
            goal, created = core._create_goal_impl(conn, {
                "type": "test_only.synthetic", "title": "TEST_ONLY synthetic goal", "source": "SYSTEM_MAINTENANCE",
                "owner": "user", "priority": "NORMAL", "goalId": "g.test-only-synthetic-1"})
        finally:
            conn.close()
        self.assertTrue(created)
        r0 = rows(db)
        self.assertEqual((r0["goal"][0], r0["goal_trace"][0]), (1, 1))      # goal + goal_created trace
        res = self.route(QUERY, "pop-query-1")
        self.assertEqual([p for p, _ in self.bridge.calls], GOAL_READS)
        self.assertIn("TEST_ONLY synthetic goal", res["combined_ephemeral"])
        self.assertIn("CURRENT FOCUS (deterministic arbitration): g.test-only-synthetic-1", res["combined_ephemeral"])
        r1 = rows(db)
        self.assertEqual((r1["goal"], r1["goal_trace"][0]), (r0["goal"], 2))   # +1 arbitration row only
        with sqlite3.connect(db) as c:
            self.assertEqual(c.execute("SELECT kind, arbitration_winner FROM goal_trace ORDER BY id DESC LIMIT 1").fetchone(),
                             ("arbitration", "g.test-only-synthetic-1"))
        self.bridge.calls.clear()
        self.route(QUERY, "pop-query-2")
        self.assertEqual(rows(db), r1)                                       # same winner: no further write


if __name__ == "__main__":
    unittest.main()
