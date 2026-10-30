"""Workspace shadow (f293e72-f9c2-cog1-wm1-g1-r1-w1) on the real gateway, adapter and Core API. TEST_ONLY; no network.

    python -m unittest discover -s integrations/hermes/release/dev-f9c2-cog1-wm1-g1-r1-w1/tests -p "test_*.py"

Reuses the g2 Core API harness with the exact w1 router. Each scenario has its own DB, bootstrapped as the gates would.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import sys
import unittest
from pathlib import Path

W1 = Path(__file__).resolve().parents[1]
REPO = W1.parents[3]
sys.path.insert(0, str(REPO / "integrations" / "hermes" / "release" / "dev-f9c2-cog1-wm1-g2" / "tests"))

import test_g2_core_api_compat as C  # noqa: E402

ANALYTIC = "TEST_ONLY what are my options for application 14?"
NO_APP = "TEST_ONLY what information is missing to resolve this?"
OVER_MATCH = "TEST_ONLY what next on the playlist?"
FIVE = ["/os/goals?limit=200", "/os/goals/focus", "/os/drafts?limit=200", "/os/tasks?limit=200",
        "/os/world?entity_type=career.application&entity_id=14"]
CANARY = "TEST_ONLY_WORKSPACE_CANARY_7W"
REF_EMPTY = "b291372517242ef683f53a3b2f0f875d613f8ffe38b0b3151a258192c89ffbaa"


def setUpModule():
    C.setUpModule()
    router = (W1 / "home" / "router.yaml").read_text(encoding="utf-8").replace(
        "/home/lilith/.hermes-dev/logs/lilith-router-decisions.log", C.LOG.as_posix())
    (C.HOME / "lilith_router" / "router.yaml").write_text(router, encoding="utf-8")


def tearDownModule():
    C.tearDownModule()


def digest(db: Path) -> str:
    with sqlite3.connect(db) as c:
        d = {"schema": hashlib.sha256(repr(c.execute("SELECT type, name, tbl_name, COALESCE(sql, '') FROM sqlite_master ORDER BY type, name").fetchall()).encode()).hexdigest()}
        for (t,) in c.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name").fetchall():
            d[t] = hashlib.sha256("\n".join(sorted(repr(tuple(r)) for r in c.execute(f'SELECT * FROM "{t}"').fetchall())).encode()).hexdigest()
        d["all"] = hashlib.sha256(json.dumps(d, sort_keys=True).encode()).hexdigest()
    return d["all"]


def bootstrap_drafts(name: str) -> Path:
    core = C.STATE["core"]
    core._world_schema_ready = False                          # otherwise only the first DB of this process gets the world tables
    db = C.use_db(name, goal_schema=True)
    conn = core.db()
    core._ensure_world_ingest_schema(conn)                    # the installed DB has it; the harness DB does not
    conn.close()
    core._drafts_db().close()
    return db


class Base(C.GoalsLiveOnTheRealCoreApiTest):
    pass


for attr in [n for n in dir(C.GoalsLiveOnTheRealCoreApiTest) if n.startswith("test_")]:
    setattr(Base, attr, None)


class WorkspaceShadow(Base):
    def test_exact_five_reads_no_writes_and_the_reply_path_unchanged(self):
        db = bootstrap_drafts("five")
        before = C.rows(db), C.schema(db)
        result = self.route(ANALYTIC, "ws-five")
        self.assertIsNone(result)
        self.assertEqual([p for p, _ in self.bridge.calls], FIVE)
        self.assertTrue(all(code == 200 for _, code in self.bridge.calls), self.bridge.calls)
        self.assertEqual((C.rows(db), C.schema(db)), before)   # no schema, row or trace change
        self.assertEqual(self.wc.status()["writes_refused"], 0)

    def test_on_a_db_without_drafts_the_first_read_would_create_it(self):
        db = C.use_db("contrast", goal_schema=True)              # why the verifier refuses this shape
        self.assertNotIn("drafts", C.rows(db))
        self.route(ANALYTIC, "ws-contrast")
        self.assertIn("drafts", C.rows(db))

    def test_detector_over_match_costs_bounded_reads_and_writes_nothing(self):
        db = bootstrap_drafts("over")
        before = C.rows(db), C.schema(db)
        self.assertIsNone(self.route(OVER_MATCH, "ws-over"))
        self.assertLessEqual(len(self.bridge.calls), 5)
        self.assertEqual((C.rows(db), C.schema(db)), before)

    def test_non_analytic_turns_make_no_read(self):
        bootstrap_drafts("none")
        for i, message in enumerate(("TEST_ONLY hey how are you", "TEST_ONLY which goal has priority?", "TEST_ONLY what is pending right now?")):
            self.bridge.calls.clear()
            self.assertIsNone(self.route(message, f"ws-none-{i}"))
            if i < 2:
                self.assertEqual(self.bridge.calls, [])

    def test_record_shape_and_no_message_text(self):
        bootstrap_drafts("shape")
        self.route(ANALYTIC, "ws-shape")
        records = self.new_log()
        self.assertEqual([r.get("lane", "routing") for r in records], ["workspace", "reasoning", "cognitive", "routing"])
        ws = records[0]
        self.assertEqual(set(ws), {"ts", "platform", "chat_id", "lane", "workspace_mode", "trace", "event_id", "msg_chars", "msg_lines"})
        self.assertEqual(ws["workspace_mode"], "shadow")
        self.assertNotIn("TEST_ONLY", json.dumps(records))

    def test_candidate_ids_hold_no_title_body_or_message_text(self):
        # A populated store, in a test DB only: the trace carries ids and classes, never titles or draft bodies.
        core = C.STATE["core"]
        db = bootstrap_drafts("privacy")
        conn = core._goals_db()
        core._create_goal_impl(conn, {"type": "test_only.synthetic", "title": f"{CANARY} goal title", "source": "SYSTEM_MAINTENANCE",
                                      "owner": "user", "priority": "HIGH", "goalId": "g.test-only-w1", "description": f"{CANARY} text"})
        conn.close()
        conn = sqlite3.connect(db)
        conn.execute("INSERT INTO drafts (draft_id, schema_version, kind, status, target_type, target_id, subject, body, content_hash, idempotency_key, created_at, updated_at) "
                     "VALUES ('d.test-only', 1, 'followup', 'created', 'career.application', '14', ?, ?, 'h', 'k', 1, 1)", (f"{CANARY} subject", f"{CANARY} body"))
        conn.commit(); conn.close()
        self.route(ANALYTIC, "ws-privacy")
        ws = [r for r in self.new_log() if r.get("lane") == "workspace"][0]
        raw = json.dumps(ws)
        self.assertNotIn(CANARY, raw)
        self.assertGreater(ws["trace"]["candidate_count"], 0)
        self.assertIsNone(ws["trace"]["fallback_reason"])
        print("\nW1_TRACE_KEYS", sorted(ws["trace"]), "PRIMARY", ws["trace"]["selected_primary_id"], ws["trace"]["selected_primary_class"])

    def test_a_focus_read_with_a_goal_would_write_a_trace_which_is_why_the_verifier_needs_an_empty_store(self):
        core = C.STATE["core"]
        db = bootstrap_drafts("trace")
        conn = core._goals_db()
        core._create_goal_impl(conn, {"type": "test_only.synthetic", "title": "TEST_ONLY", "source": "SYSTEM_MAINTENANCE", "owner": "user", "priority": "NORMAL", "goalId": "g.test-only-tr"})
        conn.close()
        before = C.rows(db)["goal_trace"][0]
        self.route(ANALYTIC, "ws-trace")
        self.assertEqual(C.rows(db)["goal_trace"][0], before + 1)

    def test_core_api_outage_fails_open(self):
        bootstrap_drafts("outage")

        class Down:
            def open(self, req, timeout=None):
                raise OSError("TEST_ONLY down")
        self.wc._OPENER = Down()
        self.assertIsNone(self.route(ANALYTIC, "ws-outage"))


class DraftsBootstrap(unittest.TestCase):
    """The design in DRAFTS-BOOTSTRAP.md: one idempotent DDL step and an exact reversal, proven on the real Core API."""

    def test_bootstrap_is_additive_and_the_reverse_returns_to_the_goal_reference(self):
        core = C.STATE["core"]
        db = C.use_db("drafts-ref", goal_schema=True)
        ref0 = digest(db)
        core._drafts_db().close()
        ref1 = digest(db)
        self.assertNotEqual(ref0, ref1)
        core._drafts_db().close()
        self.assertEqual(digest(db), ref1)                    # idempotent
        with sqlite3.connect(db) as c:
            objs = {r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE tbl_name='drafts'")}
            self.assertEqual(objs, {"drafts", "sqlite_autoindex_drafts_1", "sqlite_autoindex_drafts_2", "idx_drafts_target", "idx_drafts_task", "idx_drafts_created"})
            self.assertEqual(c.execute("SELECT COUNT(*) FROM drafts").fetchone()[0], 0)
            c.execute("DROP TABLE drafts")
        self.assertEqual(digest(db), ref0)
        print("\nDRAFTS_REF_SHAPE", ref0[:8], "->", ref1[:8])


if __name__ == "__main__":
    unittest.main()
