"""Planning shadow (f293e72-f9c2-cog1-wm1-g1-r1-w1-m1-p1) on the real gateway, adapter and Core API. TEST_ONLY; no network.

    python -m unittest discover -s integrations/hermes/release/dev-f9c2-cog1-wm1-g1-r1-w1-m1-p1/tests -p "test_*.py"

Reuses the w1 harness with the exact p1 router, adapter, planning.py and motivation.py. Each scenario has its own DB, bootstrapped as the gates did.
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

P1 = Path(__file__).resolve().parents[1]
REPO = P1.parents[3]
sys.path.insert(0, str(REPO / "integrations" / "hermes" / "release" / "dev-f9c2-cog1-wm1-g1-r1-w1" / "tests"))

import test_w1_workspace as W  # noqa: E402

C = W.C
O = REPO / "integrations" / "hermes" / "overlays"
OPTIONS = "TEST_ONLY what are my options for application 14?"
MISSING = "TEST_ONLY what information is missing to resolve this?"
GOAL = "TEST_ONLY which goal has priority?"
CASUAL = "TEST_ONLY hey how are you"
PLAN = "TEST_ONLY plan how to follow up on application 14 but do not do it"
PLAN_GENERAL = "TEST_ONLY plan the steps for the job search"
PLAN_CASUAL = "TEST_ONLY make a plan for dinner"
CANARY = "TEST_ONLY_PLANNING_CANARY_9P"
FIVE = ["/os/goals?limit=200", "/os/goals/focus", "/os/drafts?limit=200", "/os/tasks?limit=200", "/os/world?entity_type=career.application&entity_id=14"]
FORBIDDEN_RECORD_KEYS = ("goal_ref", "subject_target", "plan_snapshot_id", "relatedGoalIds", "resolutionConditions", "selected_primary_id")


def setUpModule():
    W.setUpModule()
    router = (P1 / "home" / "router.yaml").read_text(encoding="utf-8").replace(
        "/home/lilith/.hermes-dev/logs/lilith-router-decisions.log", C.LOG.as_posix())
    (C.HOME / "lilith_router" / "router.yaml").write_text(router, encoding="utf-8")
    shutil.copy2(O / "dev-motivation-private-trace/lilith_router/motivation.py", C.HOME / "lilith_router" / "motivation.py")
    shutil.copy2(O / "dev-planning-hardening/lilith_router/planning.py", C.HOME / "lilith_router" / "planning.py")
    shutil.copy2(O / "dev-cognition-private-intent/lilith_router/world_context.py", C.HOME / "lilith_router" / "world_context.py")
    importlib.reload(C.STATE["wc"])


def tearDownModule():
    gc.collect()
    C.tearDownModule()


class PlanningShadow(W.Base):
    def setUp(self):
        super().setUp()
        self.wc._READ_MEMO.clear()

    def populate(self, db):
        core = C.STATE["core"]
        conn = core._goals_db()
        core._create_goal_impl(conn, {"type": "test_only.synthetic", "title": f"{CANARY} title", "source": "SYSTEM_MAINTENANCE", "owner": "user",
                                      "priority": "HIGH", "goalId": "g.test-only-p1"})
        conn.close()
        conn = sqlite3.connect(db)
        conn.execute("INSERT INTO drafts (draft_id, schema_version, kind, status, target_type, target_id, subject, body, content_hash, idempotency_key, created_at, updated_at) "
                     "VALUES ('d.test-only-p1', 1, 'followup', 'created', 'career.application', '14', ?, ?, 'h', 'k', 1, 1)", (f"{CANARY} subject", f"{CANARY} body"))
        conn.commit(); conn.close()

    def turn(self, message, session):
        self.wc._READ_MEMO.clear()
        self.bridge.calls.clear()
        result = self.route(message, session)
        records = self.new_log()
        self.log0 += len(records)
        return result, records, list(self.bridge.calls)

    def test_exact_records_and_reads_for_the_window_turns(self):
        db = W.bootstrap_drafts("p-window")
        before = C.rows(db), C.schema(db)
        expected = ((OPTIONS, ["motivation", "workspace", "reasoning", "cognitive", "routing"], 5), (MISSING, ["motivation", "workspace", "reasoning", "routing"], 5),
                    (GOAL, ["goal", "routing"], 0), (CASUAL, ["routing"], 0), (PLAN, ["planning", "routing"], 6), (PLAN_CASUAL, ["routing"], 0))
        for i, (message, lanes, reads) in enumerate(expected):
            result, records, calls = self.turn(message, f"p-window-{i}")
            print("\nP1_WINDOW", message, [r.get("lane", "routing") for r in records], len(calls), [p for p, _ in calls])
            self.assertIsNone(result, message)
            self.assertEqual([r.get("lane", "routing") for r in records], lanes, message)
            self.assertEqual(len(calls), reads, message)
            self.assertEqual(len({p for p, _ in calls}), reads, message)
            self.assertTrue(all(code == 200 for _, code in calls), calls)
        self.assertEqual((C.rows(db), C.schema(db)), before)
        self.assertEqual(self.wc.status()["writes_refused"], 0)

    def test_the_application_number_stays_out_of_every_record(self):
        W.bootstrap_drafts("p-app")
        for i, message in enumerate((OPTIONS, PLAN, "TEST_ONLY what do you know about application 14?", "TEST_ONLY draft a follow up for application 14")):
            _, records, _ = self.turn(message, f"p-app-{i}")
            self.assertTrue(records)
            for record in records:
                intent = record.get("intent") or {}
                self.assertIsNone(intent.get("app_id"), record.get("lane"))
                self.assertNotIn("private_app_id", intent)
            self.assertNotIn('"14"', json.dumps(records))

    def test_the_application_still_reaches_the_reads(self):
        W.bootstrap_drafts("p-scope")
        _, _, calls = self.turn(OPTIONS, "p-scope")
        self.assertEqual({p for p, _ in calls}, set(FIVE))
        _, records, calls = self.turn(PLAN, "p-scope-2")
        self.assertIn("/os/world?entity_type=career.application&entity_id=14", [p for p, _ in calls])
        plan = next(r for r in records if r.get("lane") == "planning")["trace"]
        self.assertEqual((plan["outcome"], plan["subject_target_type"]), ("PLAN_PROPOSED", "application"))

    def test_populated_store_keeps_records_free_of_ids_and_text(self):
        db = W.bootstrap_drafts("p-pop")
        self.populate(db)
        turns = [self.turn(m, f"p-pop-{i}")[1] for i, m in enumerate((OPTIONS, PLAN, PLAN_GENERAL, OPTIONS))]
        raw = json.dumps(turns)
        for secret in (CANARY, "g.test-only-p1", "d.test-only-p1", "TEST_ONLY"):
            self.assertNotIn(secret, raw)
        for key in FORBIDDEN_RECORD_KEYS:
            self.assertNotIn(f'"{key}"', raw)
        self.assertNotRegex(raw, r"\bps\.[0-9a-f]")
        self.assertNotRegex(raw, r"wc\.[0-9a-f]{16}")

    def test_no_identifier_links_two_sessions(self):
        W.bootstrap_drafts("p-link")
        traces = [next(r for r in self.turn(PLAN, s)[1] if r.get("lane") == "planning")["trace"] for s in ("p-link-a", "p-link-b")]
        self.assertNotEqual(traces[0]["correlation_id"], traces[1]["correlation_id"])
        volatile = {"correlation_id", "timestamp", "ts", "duration_ms"}
        self.assertEqual({k: v for k, v in traces[0].items() if k not in volatile}, {k: v for k, v in traces[1].items() if k not in volatile})

    def test_a_goal_makes_one_focus_read_and_one_trace_in_a_planning_turn(self):
        # The write the empty-store rule refuses: one focus read now, so one trace.
        db = W.bootstrap_drafts("p-trace")
        self.populate(db)
        before = C.rows(db)["goal_trace"][0]
        _, _, calls = self.turn(PLAN_GENERAL, "p-trace")
        self.assertEqual([p for p, _ in calls].count("/os/goals/focus"), 1)
        self.assertEqual(C.rows(db)["goal_trace"][0], before + 1)

    def test_planning_does_not_take_a_turn_from_an_earlier_lane(self):
        W.bootstrap_drafts("p-order")
        for i, (message, absent) in enumerate((("TEST_ONLY draft a follow up for application 14", "planning"), (GOAL, "planning"), ("TEST_ONLY why is application 14 stuck?", "planning"))):
            _, records, _ = self.turn(message, f"p-order-{i}")
            self.assertNotIn(absent, [r.get("lane") for r in records], message)

    def test_a_failed_read_is_not_kept_and_an_outage_fails_open(self):
        W.bootstrap_drafts("p-outage")

        class Down:
            def open(self, req, timeout=None):
                raise OSError("TEST_ONLY down")
        self.wc._OPENER = Down()
        self.assertIsNone(self.route(PLAN, "p-outage"))
        self.assertEqual(self.wc._READ_MEMO, {})

    def test_the_memo_is_process_memory_with_a_short_life_and_a_path_limit(self):
        self.assertEqual((self.wc.READ_MEMO_SECONDS, self.wc.READ_MEMO_MAX_PATHS), (1.5, 32))
        for i in range(40):
            self.wc._READ_MEMO[f"/x{i}"] = (0.0, "null")
        self.assertGreater(len(self.wc._READ_MEMO), 32)      # an expired entry is only ever replaced by a fresh read, and a full memo is cleared first
        W.bootstrap_drafts("p-memo")
        self.route(PLAN, "p-memo")
        self.assertLessEqual(len(self.wc._READ_MEMO), 32)

    def test_shadow_never_loads_a_model_or_writes(self):
        db = W.bootstrap_drafts("p-write")
        before = C.rows(db), C.schema(db)
        for i, m in enumerate((PLAN, PLAN_GENERAL)):
            self.assertIsNone(self.turn(m, f"p-write-{i}")[0])
        self.assertEqual((C.rows(db), C.schema(db)), before)
        self.assertEqual(self.wc.status()["writes_refused"], 0)


if __name__ == "__main__":
    unittest.main()
