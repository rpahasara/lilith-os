"""Motivation shadow (f293e72-f9c2-cog1-wm1-g1-r1-w1-m1) on the real gateway, adapter and Core API. TEST_ONLY; no network.

    python -m unittest discover -s integrations/hermes/release/dev-f9c2-cog1-wm1-g1-r1-w1-m1/tests -p "test_*.py"

Reuses the w1 harness with the exact m1 router. Each scenario has its own DB, bootstrapped as the gates did.
"""

from __future__ import annotations

import gc
import json
import sqlite3
import sys
import unittest
from pathlib import Path

M1 = Path(__file__).resolve().parents[1]
REPO = M1.parents[3]
sys.path.insert(0, str(REPO / "integrations" / "hermes" / "release" / "dev-f9c2-cog1-wm1-g1-r1-w1" / "tests"))

import test_w1_workspace as W  # noqa: E402

C = W.C
ANALYTIC = W.ANALYTIC
NO_APP = W.NO_APP
EIGHT = W.FIVE + ["/os/goals?limit=200", "/os/goals/focus", "/os/tasks?limit=200"]
CANARY = "TEST_ONLY_MOTIVATION_CANARY_8M"
TRACE_KEYS = {"correlation_id", "channel", "drive_count", "active_drive_types", "satisfied_drive_types", "highest_intensity_class", "per_drive",
              "source_availability", "partial", "fallback_reason", "schema_version", "timestamp", "duration_ms", "candidate_count", "eligible_count"}


def setUpModule():
    W.setUpModule()
    router = (M1 / "home" / "router.yaml").read_text(encoding="utf-8").replace(
        "/home/lilith/.hermes-dev/logs/lilith-router-decisions.log", C.LOG.as_posix())
    (C.HOME / "lilith_router" / "router.yaml").write_text(router, encoding="utf-8")


def tearDownModule():
    gc.collect()
    C.tearDownModule()


class MotivationShadow(W.Base):
    def populate(self, db):
        core = C.STATE["core"]
        conn = core._goals_db()
        core._create_goal_impl(conn, {"type": "test_only.synthetic", "title": f"{CANARY} title", "source": "SYSTEM_MAINTENANCE", "owner": "user",
                                      "priority": "HIGH", "goalId": "g.test-only-m1"})
        conn.close()
        conn = sqlite3.connect(db)
        conn.execute("INSERT INTO drafts (draft_id, schema_version, kind, status, target_type, target_id, subject, body, content_hash, idempotency_key, created_at, updated_at) "
                     "VALUES ('d.test-only-m1', 1, 'followup', 'created', 'career.application', '14', ?, ?, 'h', 'k', 1, 1)", (f"{CANARY} subject", f"{CANARY} body"))
        conn.commit(); conn.close()

    def test_exact_eight_reads_no_writes_and_the_reply_path_unchanged(self):
        db = W.bootstrap_drafts("m-eight")
        before = C.rows(db), C.schema(db)
        self.assertIsNone(self.route(ANALYTIC, "m-eight"))
        self.assertEqual([p for p, _ in self.bridge.calls], EIGHT)
        self.assertTrue(all(code == 200 for _, code in self.bridge.calls), self.bridge.calls)
        self.assertEqual((C.rows(db), C.schema(db)), before)
        self.assertEqual(self.wc.status()["writes_refused"], 0)

    def test_record_order_shape_and_no_message_text(self):
        W.bootstrap_drafts("m-shape")
        self.route(ANALYTIC, "m-shape")
        records = self.new_log()
        self.assertEqual([r.get("lane", "routing") for r in records], ["motivation", "workspace", "reasoning", "cognitive", "routing"])
        mot = records[0]
        self.assertEqual(set(mot), {"ts", "platform", "chat_id", "lane", "motivation_mode", "trace", "event_id", "msg_chars", "msg_lines"})
        self.assertEqual(mot["motivation_mode"], "shadow")
        self.assertEqual(mot["trace"]["active_drive_types"], [])
        self.assertEqual(sorted(mot["trace"]["satisfied_drive_types"]), ["COHERENCE", "GOAL_COMPLETION"])
        self.assertNotIn("TEST_ONLY", json.dumps(records))
        print("\nM1_TRACE", json.dumps(mot["trace"], sort_keys=True))

    def test_shadow_candidates_never_reach_the_workspace_pool(self):
        db = W.bootstrap_drafts("m-pool")
        self.populate(db)
        self.route(ANALYTIC, "m-pool")
        records = self.new_log()
        ws = next(r for r in records if r.get("lane") == "workspace")
        self.assertNotIn("motivation", ws["trace"]["source_type_counts"])

    def test_no_stable_identifier_or_stored_text_on_a_populated_store(self):
        db = W.bootstrap_drafts("m-ids")
        self.populate(db)
        turns = []
        for _ in range(2):
            self.route(ANALYTIC, "m-ids")
            turns.append(self.new_log())
            self.log0 += len(turns[-1])
        raw = json.dumps(turns)
        for secret in (CANARY, "g.test-only-m1", "d.test-only-m1", "TEST_ONLY"):
            self.assertNotIn(secret, raw)
        self.assertNotRegex(raw, r"wc\.[0-9a-f]{16}")
        first, second = (next(r for r in t if r.get("lane") == "motivation")["trace"] for t in turns)
        self.assertNotEqual(first["correlation_id"], second["correlation_id"])
        self.assertRegex(first["correlation_id"], r"^m\.[0-9a-f]{16}$")

    def test_a_goal_makes_two_focus_reads_in_a_turn_but_one_trace(self):
        # Why the verifier needs an empty goal store: the extra focus read must not double the write.
        db = W.bootstrap_drafts("m-trace")
        self.populate(db)
        before = C.rows(db)["goal_trace"][0]
        self.route(ANALYTIC, "m-trace")
        self.assertEqual(C.rows(db)["goal_trace"][0], before + 1)

    def test_non_analytic_turns_make_no_read_and_no_motivation_record(self):
        W.bootstrap_drafts("m-none")
        for i, message in enumerate(("TEST_ONLY hey how are you", "TEST_ONLY which goal has priority?", "TEST_ONLY plan the steps for the job search")):
            self.bridge.calls.clear()
            self.assertIsNone(self.route(message, f"m-none-{i}"))
            self.assertEqual(self.bridge.calls, [], message)
        self.assertFalse([r for r in self.new_log() if r.get("lane") == "motivation"])

    def test_planning_and_reasoning_modules_stay_unused_in_shadow(self):
        W.bootstrap_drafts("m-mods")
        self.route(ANALYTIC, "m-mods")
        self.assertNotIn("lilith_router.planning", sys.modules)
        self.assertNotIn("lilith_router.reasoning", sys.modules)

    def test_a_blocked_goal_would_put_its_id_in_the_record(self):
        # A limit, pinned: harmless while the verifier requires an empty goal store, and a blocker for non-empty stores.
        sys.path.insert(0, str(REPO / "docs" / "architecture" / "slice-11"))
        import motivation
        blocked = [{"goalId": "g.test-only-m1", "lifecycleState": "BLOCKED", "isFocus": True, "userReferenced": False, "source": "USER_REQUESTED", "blockedBy": ["t.1"],
                    "targetApp": "14", "hardBlockerFailedTaskIds": ["t.1"]}]
        snapshot = motivation.build_snapshot(coherence=None, goal_completion=motivation.classify_goal_completion(blocked, channel="lilith_os"), safety=None,
                                             raw_refs=None, channel="lilith_os", source_availability={}, partial=False)
        self.assertIn("g.test-only-m1", json.dumps(motivation.build_trace(snapshot)))

    def test_core_api_outage_fails_open(self):
        W.bootstrap_drafts("m-outage")

        class Down:
            def open(self, req, timeout=None):
                raise OSError("TEST_ONLY down")
        self.wc._OPENER = Down()
        self.assertIsNone(self.route(ANALYTIC, "m-outage"))


if __name__ == "__main__":
    unittest.main()
