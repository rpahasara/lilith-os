"""Reasoning and Goals shadow of f293e72-f9c2-cog1-wm1-g1-r1 against the real Core API source. TEST_ONLY; no socket.

    python -m unittest discover -s integrations/hermes/release/dev-f9c2-cog1-wm1-g1-r1/tests -p "test_*.py"

As dev-f9c2-cog1-wm2/tests/test_wm2_core_api_compat.py: services/core-api/app.py runs in-process behind FastAPI's
TestClient, bridged to the adapter's transport, so any Core API read would really execute. The database has the shape
F1 found on DEV (2026-10-28): the World Model schema with 0 beliefs, an empty tasks table, and no drafts, goal or
career tables. On this shape a first GET /os/goals or /os/goals/focus runs the goal DDL (`_goals_db`), so the absence
of any read is what keeps the goal schema and goal_trace untouched.

Test 1 runs the exact r1 router.yaml. Test 2 is a contrast only: the same turns with goals_mode switched to live in a
throwaway copy (never shipped) do read the goal routes and do create the goal tables, which shows test 1 would see it.
"""

from __future__ import annotations

import hashlib
import io
import os
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

R1 = Path(__file__).resolve().parents[1]
REPO = R1.parents[3]
sys.path.insert(0, str(REPO / "integrations" / "hermes" / "overlays" / "dev-unified-cognition" / "tools"))

import assemble_dev_cognition  # noqa: E402

GOAL_TURNS = {
    "query": "TEST_ONLY which goal has priority?",
    "doing": "TEST_ONLY what are you trying to do right now?",
    "blocked": "TEST_ONLY what is blocked and why?",
    "create": "TEST_ONLY I want to follow up on application 14. Track that as a goal.",
    "reasoning-options": "TEST_ONLY what are my options for application 14?",
    "reasoning-why": "TEST_ONLY why can't you send the follow up for application 14?",
}
CONTROL = "TEST_ONLY hey how are you"

_TMP = tempfile.TemporaryDirectory(prefix="r1-coreapi-", ignore_cleanup_errors=True)   # Windows: open SQLite
TMP = Path(_TMP.name)
HOME = TMP / "hermes-home"
DB = TMP / "core" / "lilith-dev.db"
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
    conn = core.db()                                         # DEV shape (F1): World Model schema + empty tasks
    try:
        core._ensure_world_schema(conn)
    finally:
        conn.close()
    core._tasks_db().close()
    core._goal_schema_ready = False                          # as on a freshly started DEV Core API process
    STATE["core"], STATE["client"] = core, TestClient(core.app)
    for k, v in saved.items():
        os.environ.pop(k, None) if v is None else os.environ.__setitem__(k, v)

    assert assemble_dev_cognition.assemble(HOME) == []
    (HOME / "router.yaml").unlink()
    os.environ["HERMES_HOME"] = str(HOME)
    sys.path.insert(0, str(HOME))
    from lilith_router import gateway_integration, world_context
    STATE.update(gi=gateway_integration, wc=world_context)


def tearDownModule():
    for mod in [m for m in sys.modules if m == "lilith_router" or m.startswith("lilith_router.") or m == "app"]:
        del sys.modules[mod]
    _TMP.cleanup()


def install_router(goals_mode: str = "shadow") -> None:
    text = (R1 / "home" / "router.yaml").read_text(encoding="utf-8").replace(
        "/home/lilith/.hermes-dev/logs/lilith-router-decisions.log", (TMP / "decisions.log").as_posix())
    if goals_mode != "shadow":                                # contrast only; the shipped router stays shadow
        text = text.replace("goals_mode: shadow", f"goals_mode: {goals_mode}")
    (HOME / "lilith_router" / "router.yaml").write_text(text, encoding="utf-8")


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


def schema() -> list[tuple]:
    with sqlite3.connect(DB) as c:
        return c.execute("SELECT type, name, tbl_name, sql FROM sqlite_master ORDER BY type, name").fetchall()


def table_digests() -> dict[str, tuple[int, str]]:
    with sqlite3.connect(DB) as c:
        names = [r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
        out = {}
        for n in names:
            rows = c.execute(f'SELECT * FROM "{n}" ORDER BY rowid').fetchall()
            out[n] = (len(rows), hashlib.sha256(repr(rows).encode()).hexdigest())
        return out


class GoalsShadowOnTheRealCoreApiTest(unittest.TestCase):
    def setUp(self):
        self.gi, self.wc = STATE["gi"], STATE["wc"]
        self.bridge = CoreApiBridge(STATE["client"])
        self.saved = self.wc._OPENER
        self.wc._OPENER = self.bridge
        self.wc._BREAKER["open_until"] = 0.0

    def tearDown(self):
        self.wc._OPENER = self.saved

    def route(self, message, chat):
        ctx = SimpleNamespace(source=SimpleNamespace(platform=SimpleNamespace(value="lilith_os"), chat_id=chat),
                              session_key=f"agent:lilith_os:{chat}", message=message)
        return self.gi.route_turn(runner=SimpleNamespace(), ctx=ctx, model="dev-model", runtime_kwargs={},
                                  turn_route={"model": "dev-model"}, combined_ephemeral="TEST_ONLY base",
                                  cached_agent=None)

    def test_1_goal_turns_in_shadow_make_no_core_api_call_and_change_no_schema_or_row(self):
        install_router("shadow")
        before_schema, before_rows = schema(), table_digests()
        self.assertFalse({"goal", "goal_trace"} & set(before_rows))          # DEV shape: no goal tables
        results = {k: self.route(m, f"shadow-{k}") for k, m in GOAL_TURNS.items()}
        results["control"] = self.route(CONTROL, "shadow-control")
        self.assertEqual(self.bridge.calls, [])                              # not one Core API request
        self.assertTrue(all(r is None for r in results.values()), results)  # routing falls through unchanged
        self.assertEqual(schema(), before_schema)                            # no goal / goal_trace DDL
        self.assertEqual(table_digests(), before_rows)                       # no row anywhere
        self.assertFalse(STATE["core"]._goal_schema_ready)                   # _goals_db() never ran

    def test_2_contrast_goals_live_would_create_the_goal_schema(self):
        # Why live Goals stays out of this release: on the DEV shape the first goal read creates the goal tables.
        install_router("live")
        try:
            before = table_digests()
            res = self.route(GOAL_TURNS["query"], "live-query")
            paths = [p for p, _, _ in self.bridge.calls]
            self.assertTrue(paths and all(p.startswith("/os/goals") for p in paths), paths)
            self.assertIn("/os/goals/focus", paths)
            self.assertEqual(res["mode"], "goal")
            after = table_digests()
            self.assertFalse({"goal", "goal_trace"} & set(before))
            self.assertTrue({"goal", "goal_trace"} <= set(after))                # created by a GET
            self.assertEqual((after["goal"][0], after["goal_trace"][0]), (0, 0))   # empty: no focus winner, no trace
        finally:
            install_router("shadow")


if __name__ == "__main__":
    unittest.main()
