"""Planning shadow findings on the real gateway, adapter and Core API, with the m1 router plus Planning. TEST_ONLY; no network.

    python -B integrations/hermes/proposals/planning-shadow-v0.1/test_planning_shadow_findings.py

Each test pins a defect in DESIGN.md. They describe today's behaviour and are not acceptance criteria: when a fix lands, the test must change.
"""

from __future__ import annotations

import gc
import json
import sqlite3
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "integrations" / "hermes" / "release" / "dev-f9c2-cog1-wm1-g1-r1-w1" / "tests"))

import test_w1_workspace as W  # noqa: E402

C = W.C
FOLLOWUP = "TEST_ONLY plan how to follow up on application 14 but do not do it"
GENERAL = "TEST_ONLY plan the steps for the job search"
CASUAL = "TEST_ONLY make a plan for dinner"
M1 = REPO / "integrations" / "hermes" / "release" / "dev-f9c2-cog1-wm1-g1-r1-w1-m1"


def setUpModule():
    W.setUpModule()
    router = (M1 / "home" / "router.yaml").read_text(encoding="utf-8").replace(
        "/home/lilith/.hermes-dev/logs/lilith-router-decisions.log", C.LOG.as_posix())
    assert "planning_enabled: false\n" in router
    router = router.replace("planning_enabled: false\n", "planning_enabled: true\nplanning_mode: shadow\n")
    (C.HOME / "lilith_router" / "router.yaml").write_text(router, encoding="utf-8")


def tearDownModule():
    gc.collect()
    C.tearDownModule()


class Findings(W.Base):
    def populate(self):
        core = C.STATE["core"]
        conn = core._goals_db()
        core._create_goal_impl(conn, {"type": "test_only.synthetic", "title": "TEST_ONLY", "source": "SYSTEM_MAINTENANCE", "owner": "user", "priority": "HIGH", "goalId": "g.test-only-p"})
        conn.close()

    def planning_record(self):
        return next(r for r in self.new_log() if r.get("lane") == "planning")

    def test_shadow_keeps_the_reply_and_writes_nothing(self):
        db = W.bootstrap_drafts("p-w")
        before = C.rows(db), C.schema(db)
        self.assertIsNone(self.route(FOLLOWUP, "p-w"))
        self.assertEqual((C.rows(db), C.schema(db)), before)
        self.assertEqual(self.wc.status()["writes_refused"], 0)

    def test_p1_a_casual_plan_is_a_planning_turn(self):
        W.bootstrap_drafts("p-1")
        self.route(CASUAL, "p-1")
        self.assertEqual(self.planning_record()["trace"]["outcome"], "INSUFFICIENT_INFORMATION")
        self.assertEqual(len(self.bridge.calls), 14)

    def test_p2_a_followup_turn_makes_fifteen_reads(self):
        W.bootstrap_drafts("p-2")
        self.route(FOLLOWUP, "p-2")
        self.assertEqual(len(self.bridge.calls), 15)
        self.assertEqual(sum(1 for p, _ in self.bridge.calls if p.startswith("/os/goals")), 7)

    def test_p3_a_goal_id_reaches_the_record(self):
        W.bootstrap_drafts("p-3")
        self.populate()
        self.route(GENERAL, "p-3")
        self.assertEqual(self.planning_record()["trace"]["goal_ref"], "g.test-only-p")

    def test_p4_the_target_reaches_the_record(self):
        W.bootstrap_drafts("p-4")
        self.route(FOLLOWUP, "p-4")
        record = self.planning_record()
        self.assertEqual(record["trace"]["subject_target"], "application:14")
        self.assertEqual(record["intent"]["app_id"], "14")

    def test_p5_the_plan_snapshot_id_is_stable_across_sessions(self):
        W.bootstrap_drafts("p-5")
        ids = []
        for session in ("p-5a", "p-5b"):
            self.route(FOLLOWUP, session)
            ids.append(self.planning_record()["trace"]["plan_snapshot_id"])
            self.log0 = len(C.LOG.read_text(encoding="utf-8").splitlines())
        self.assertEqual(ids[0], ids[1])
        self.assertTrue(ids[0].startswith("ps."))

    def test_no_message_text_or_stored_text_reaches_the_record(self):
        db = W.bootstrap_drafts("p-t")
        conn = sqlite3.connect(db)
        conn.execute("INSERT INTO drafts (draft_id, schema_version, kind, status, target_type, target_id, subject, body, content_hash, idempotency_key, created_at, updated_at) "
                     "VALUES ('d.test-only-p', 1, 'followup', 'created', 'career.application', '14', 'TEST_ONLY_CANARY_P', 'TEST_ONLY_CANARY_P', 'h', 'k', 1, 1)")
        conn.commit(); conn.close()
        self.route(FOLLOWUP, "p-t")
        raw = json.dumps(self.new_log())
        self.assertNotIn("TEST_ONLY", raw)


if __name__ == "__main__":
    unittest.main()
