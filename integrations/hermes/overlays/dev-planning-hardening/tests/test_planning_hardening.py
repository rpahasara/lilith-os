"""Planning shadow candidate (NOT IN ANY RELEASE) on the real gateway, adapter and Core API. TEST_ONLY; no network.

    python -B integrations/hermes/overlays/dev-planning-hardening/tests/test_planning_hardening.py

Runs the candidate adapter and planning.py with the w1 router plus Motivation and Planning in shadow. The Motivation base module is used as shipped.
"""

from __future__ import annotations

import gc
import importlib
import json
import shutil
import sqlite3
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
REPO = HERE.parents[3]
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(REPO / "integrations" / "hermes" / "release" / "dev-f9c2-cog1-wm1-g1-r1-w1" / "tests"))

import planning_corpus as PC  # noqa: E402
import test_w1_workspace as W  # noqa: E402

C = W.C
FOLLOWUP = "TEST_ONLY plan how to follow up on application 14 but do not do it"
GENERAL = "TEST_ONLY plan the steps for the job search"
RESULTS = Path(__file__).with_name("planning_results.json")


def setUpModule():
    W.setUpModule()
    router = (REPO / "integrations/hermes/release/dev-f9c2-cog1-wm1-g1-r1-w1/home/router.yaml").read_text(encoding="utf-8").replace(
        "/home/lilith/.hermes-dev/logs/lilith-router-decisions.log", C.LOG.as_posix())
    router = router.replace("motivation_enabled: false\n", "motivation_enabled: true\nmotivation_mode: shadow\n").replace("planning_enabled: false\n", "planning_enabled: true\nplanning_mode: shadow\n")
    (C.HOME / "lilith_router" / "router.yaml").write_text(router, encoding="utf-8")
    shutil.copy2(HERE / "lilith_router" / "world_context.py", C.HOME / "lilith_router" / "world_context.py")
    shutil.copy2(HERE / "lilith_router" / "planning.py", C.HOME / "lilith_router" / "planning.py")
    importlib.reload(C.STATE["wc"])


def tearDownModule():
    gc.collect()
    C.tearDownModule()


class Candidate(W.Base):
    def setUp(self):
        super().setUp()
        self.wc._READ_MEMO.clear()

    def populate(self):
        core = C.STATE["core"]
        conn = core._goals_db()
        core._create_goal_impl(conn, {"type": "test_only.synthetic", "title": "TEST_ONLY", "source": "SYSTEM_MAINTENANCE", "owner": "user", "priority": "HIGH", "goalId": "g.test-only-p"})
        conn.close()

    def record(self):
        return next(r for r in self.new_log() if r.get("lane") == "planning")

    def test_p1_casual_plans_make_no_read_and_no_record(self):
        W.bootstrap_drafts("c-1")
        for i, m in enumerate(("TEST_ONLY make a plan for dinner", "TEST_ONLY plan a trip to Lisbon")):
            self.assertIsNone(self.route(m, f"c-1-{i}"))
        self.assertEqual(self.bridge.calls, [])
        self.assertFalse([r for r in self.new_log() if r.get("lane") == "planning"])

    def test_p2_each_route_is_read_once_in_a_turn(self):
        W.bootstrap_drafts("c-2")
        self.route(FOLLOWUP, "c-2")
        paths = [p for p, _ in self.bridge.calls]
        print("\nPLANNING_READS", len(paths), paths)
        self.assertEqual(len(paths), len(set(paths)))
        self.assertLessEqual(len(paths), 6)

    def test_p2_a_memo_expires_and_never_outlives_a_turn_gap(self):
        W.bootstrap_drafts("c-2b")
        self.route(FOLLOWUP, "c-2b")
        n = len(self.bridge.calls)
        for key, (_, text) in list(self.wc._READ_MEMO.items()):
            self.wc._READ_MEMO[key] = (0.0, text)
        self.route(FOLLOWUP, "c-2b")
        self.assertEqual(len(self.bridge.calls), 2 * n)

    def test_p3_a_goal_id_stays_out_of_the_record(self):
        W.bootstrap_drafts("c-3")
        self.populate()
        self.route(GENERAL, "c-3")
        trace = self.record()["trace"]
        self.assertNotIn("g.test-only-p", json.dumps(trace))
        self.assertTrue(trace["goal_ref_present"])

    def test_p4_the_application_stays_out_of_the_record_and_still_reaches_the_plan(self):
        W.bootstrap_drafts("c-4")
        self.route(FOLLOWUP, "c-4")
        record = self.record()
        self.assertIsNone(record["intent"]["app_id"])
        self.assertEqual(record["trace"]["subject_target_type"], "application")
        self.assertNotIn("14", json.dumps(record["trace"]).replace(str(record["trace"]["ts"]), ""))
        self.assertEqual((record["trace"]["outcome"], record["trace"]["step_count"]), ("PLAN_PROPOSED", 3))    # the template still found its target
        self.assertIn("/os/world?entity_type=career.application&entity_id=14", [p for p, _ in self.bridge.calls])

    def test_p5_no_stable_identifier_across_sessions(self):
        W.bootstrap_drafts("c-5")
        traces = []
        for session in ("c-5a", "c-5b"):
            self.wc._READ_MEMO.clear()
            self.route(FOLLOWUP, session)
            traces.append(self.record()["trace"])
            self.log0 = len(C.LOG.read_text(encoding="utf-8").splitlines())
        raw = json.dumps(traces)
        self.assertNotIn("ps.", raw)
        self.assertNotEqual(traces[0]["correlation_id"], traces[1]["correlation_id"])
        self.assertTrue(traces[0]["plan_snapshot_present"])

    def test_shadow_keeps_the_reply_writes_nothing_and_calls_no_model(self):
        db = W.bootstrap_drafts("c-w")
        before = C.rows(db), C.schema(db)
        self.assertIsNone(self.route(FOLLOWUP, "c-w"))
        self.assertEqual((C.rows(db), C.schema(db)), before)
        self.assertEqual(self.wc.status()["writes_refused"], 0)
        self.assertNotIn("TEST_ONLY", json.dumps(self.new_log()))

    def test_a_failed_read_is_not_memoized(self):
        W.bootstrap_drafts("c-out")

        class Down:
            def open(self, req, timeout=None):
                raise OSError("TEST_ONLY down")
        self.wc._OPENER = Down()
        self.assertIsNone(self.route(FOLLOWUP, "c-out"))
        self.assertEqual(self.wc._READ_MEMO, {})

    def test_the_corpus_result_is_pinned(self):
        detect = self.wc.detect_planning_intent
        got = {"WORK_MISSED": sorted(m for m in PC.WORK if not PC.in_tune(m) and not detect(m)["any"]),
               "CASUAL_MATCHED": sorted(m for m in PC.CASUAL if not PC.in_tune(m) and detect(m)["any"]),
               "NEGATED_MATCHED": sorted(m for m in PC.NEGATED if not PC.in_tune(m) and detect(m)["any"]),
               "YIELDS_MATCHED": sorted(m for m in PC.YIELDS if not PC.in_tune(m) and detect(m)["any"])}
        self.assertEqual(got, json.loads(RESULTS.read_text(encoding="utf-8")))


if __name__ == "__main__":
    unittest.main()
