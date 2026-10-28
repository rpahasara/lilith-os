"""The planned G3 turns of f293e72-f9c2-cog1-wm2 against the real Core API source. TEST_ONLY; no socket.

    python -m unittest discover -s integrations/hermes/release/dev-f9c2-cog1-wm2/tests -p "test_*.py"

As dev-f9c2-cog1/tests/test_cog1_core_api_compat.py: services/core-api/app.py (unchanged since the last DEV Core API
deployment, d82f7da) runs in-process behind FastAPI's TestClient, bridged to the adapter's transport. The database
has the shape F1 found on DEV (2026-10-28): the World Model schema with 0 beliefs, an empty tasks table, and no
drafts or career tables. The exact wm2 router.yaml is installed. Nothing is seeded.
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

WM2 = Path(__file__).resolve().parents[1]
REPO = WM2.parents[3]
sys.path.insert(0, str(REPO / "integrations" / "hermes" / "overlays" / "dev-unified-cognition" / "tools"))

import assemble_dev_cognition  # noqa: E402

G3_BELIEF = "TEST_ONLY what do you believe about application 999?"
G3_CONTROL = "TEST_ONLY hey how are you"
PENDING = "TEST_ONLY what is pending right now?"
WORLD_999 = "/os/world?entity_type=career.application&entity_id=999"

_TMP = tempfile.TemporaryDirectory(prefix="wm2-coreapi-", ignore_cleanup_errors=True)   # Windows: open SQLite
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
    STATE["core"], STATE["client"] = core, TestClient(core.app)
    for k, v in saved.items():
        os.environ.pop(k, None) if v is None else os.environ.__setitem__(k, v)

    assert assemble_dev_cognition.assemble(HOME) == []
    (HOME / "router.yaml").unlink()
    router = (WM2 / "home" / "router.yaml").read_text(encoding="utf-8").replace(
        "/home/lilith/.hermes-dev/logs/lilith-router-decisions.log", (TMP / "decisions.log").as_posix())
    (HOME / "lilith_router" / "router.yaml").write_text(router, encoding="utf-8")
    os.environ["HERMES_HOME"] = str(HOME)
    sys.path.insert(0, str(HOME))
    from lilith_router import gateway_integration, world_context
    STATE.update(gi=gateway_integration, wc=world_context)


def tearDownModule():
    for mod in [m for m in sys.modules if m == "lilith_router" or m.startswith("lilith_router.") or m == "app"]:
        del sys.modules[mod]
    _TMP.cleanup()


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


class G3OnTheRealCoreApiTest(unittest.TestCase):
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

    def test_1_the_g3_turns_read_one_world_route_and_change_no_table(self):
        before = table_digests()
        self.assertIn("world_belief", before)
        self.assertEqual(before["world_belief"][0], 0)
        self.assertNotIn("drafts", before)
        belief, control = self.route(G3_BELIEF, "g3-belief"), self.route(G3_CONTROL, "g3-control")
        self.assertEqual(self.bridge.calls, [(WORLD_999, 200, "application/json")])
        self.assertEqual(belief["mode"], "cognitive")
        self.assertTrue(belief["combined_ephemeral"].endswith(
            "WORLD MODEL BELIEFS (durable, reconciled; showing 0 of 0; conflicted=0, stale=0, last_reconciled=None):\n"
            "(no beliefs are recorded for this focus)"))
        self.assertIsNone(control)
        self.assertEqual(table_digests(), before)                  # no row, no table: the drafts table stays absent

    def test_2_a_pending_turn_would_create_the_drafts_table(self):
        # Why G3 has no pending or draft turn (F2): GET /os/drafts runs the drafts DDL on first use.
        before = table_digests()
        self.assertNotIn("drafts", before)
        res = self.route(PENDING, "pending")
        self.assertEqual([p for p, _, _ in self.bridge.calls], ["/os/tasks?limit=200", "/os/drafts?limit=200"])
        self.assertEqual({s for _, s, _ in self.bridge.calls}, {200})
        self.assertIn("DURABLE PENDING STATE", res["combined_ephemeral"])
        after = table_digests()
        self.assertEqual(after.get("drafts"), (0, hashlib.sha256(repr([]).encode()).hexdigest()))
        self.assertEqual({k: v for k, v in after.items() if k != "drafts"}, before)


if __name__ == "__main__":
    unittest.main()
