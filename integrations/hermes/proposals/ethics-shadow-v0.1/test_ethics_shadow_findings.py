"""Ethics shadow findings on the real gateway, adapter and Core API, with the m1 router plus Ethics. TEST_ONLY; no network.

    python -B integrations/hermes/proposals/ethics-shadow-v0.1/test_ethics_shadow_findings.py

Each test pins today's behaviour from DESIGN.md. These are findings, not acceptance criteria: when a fix lands, the test must change.
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
M1 = REPO / "integrations" / "hermes" / "release" / "dev-f9c2-cog1-wm1-g1-r1-w1-m1"
sys.path.insert(0, str(REPO / "integrations" / "hermes" / "release" / "dev-f9c2-cog1-wm1-g1-r1-w1" / "tests"))

import test_w1_workspace as W  # noqa: E402

C = W.C
WORK = "TEST_ONLY is it ethical to contact the recruiter's manager about application 14?"
LIE = "TEST_ONLY is it okay to lie on my cover letter?"
CASUAL = ("TEST_ONLY is it ok to wear jeans?", "TEST_ONLY is it okay if we eat at 7?", "TEST_ONLY is it fair that my team lost?")
CANARY = "TEST_ONLY_ETHICS_CANARY_3E"


def setUpModule():
    W.setUpModule()
    router = (M1 / "home" / "router.yaml").read_text(encoding="utf-8").replace("/home/lilith/.hermes-dev/logs/lilith-router-decisions.log", C.LOG.as_posix())
    assert "ethics_enabled: false\n" in router
    (C.HOME / "lilith_router" / "router.yaml").write_text(router.replace("ethics_enabled: false\n", "ethics_enabled: true\nethics_mode: shadow\n"), encoding="utf-8")
    (C.HOME / "lilith_router" / "motivation.py").write_bytes((REPO / "integrations/hermes/overlays/dev-motivation-private-trace/lilith_router/motivation.py").read_bytes())


def tearDownModule():
    gc.collect()
    C.tearDownModule()


class Findings(W.Base):
    def ethics(self):
        return next(r for r in self.new_log() if r.get("lane") == "ethics")

    def test_shadow_keeps_the_reply_and_writes_nothing(self):
        db = W.bootstrap_drafts("e-w")
        before = C.rows(db), C.schema(db)
        self.assertIsNone(self.route(WORK, "e-w"))
        self.assertEqual((C.rows(db), C.schema(db)), before)
        self.assertEqual(self.wc.status()["writes_refused"], 0)

    def test_the_lane_stays_advisory(self):
        W.bootstrap_drafts("e-a")
        self.route(WORK, "e-a")
        trace = self.ethics()["trace"]
        self.assertIs(trace["authoritative_policy_evaluation"], False)
        self.assertEqual(trace["candidate_source"], "deterministic")

    def test_e1_casual_questions_are_ethics_turns(self):
        W.bootstrap_drafts("e-1")
        for i, message in enumerate(CASUAL):
            self.bridge.calls.clear()
            self.route(message, f"e-1-{i}")
            self.assertEqual(len(self.bridge.calls), 10, message)
        self.assertEqual(len([r for r in self.new_log() if r.get("lane") == "ethics"]), 3)

    def test_e2_a_plain_question_gets_no_concern(self):
        W.bootstrap_drafts("e-2")
        self.route(LIE, "e-2")
        trace = self.ethics()["trace"]
        self.assertEqual((trace["outcome"], trace["concern_count"]), ("INSUFFICIENT_CONTEXT", 0))

    def test_e3_a_risk_question_runs_both_lanes_in_shadow(self):
        # In shadow both record, at 18 reads. Ethics runs first, so Ethics Live would take this turn from Reasoning.
        W.bootstrap_drafts("e-3")
        self.route("TEST_ONLY what are the risks of accepting this offer?", "e-3")
        lanes = [r.get("lane", "routing") for r in self.new_log()]
        self.assertEqual(lanes, ["ethics", "motivation", "workspace", "reasoning", "routing"])
        self.assertEqual(len(self.bridge.calls), 18)

    def test_e4_ten_reads_on_a_matching_turn(self):
        W.bootstrap_drafts("e-4")
        self.route(WORK, "e-4")
        self.assertEqual(len(self.bridge.calls), 10)

    def test_e5_the_application_reaches_the_record(self):
        W.bootstrap_drafts("e-5")
        self.route(WORK, "e-5")
        self.assertEqual(self.ethics()["intent"]["app_id"], "14")

    def test_no_stored_text_reaches_the_record_and_ids_are_turn_scoped(self):
        db = W.bootstrap_drafts("e-t")
        conn = sqlite3.connect(db)
        conn.execute("INSERT INTO drafts (draft_id, schema_version, kind, status, target_type, target_id, subject, body, content_hash, idempotency_key, created_at, updated_at) "
                     "VALUES ('d.test-only-e', 1, 'followup', 'created', 'career.application', '14', ?, ?, 'h', 'k', 1, 1)", (CANARY, CANARY))
        conn.commit(); conn.close()
        refs = []
        for session in ("e-ta", "e-tb"):
            self.route(WORK, session)
            records = self.new_log()
            self.assertNotIn("TEST_ONLY", json.dumps(records))
            self.assertNotIn("d.test-only-e", json.dumps(records))
            refs.append(next(r for r in records if r.get("lane") == "ethics")["trace"]["ethical_subject_ref"])
            self.log0 = len(C.LOG.read_text(encoding="utf-8").splitlines())
        self.assertNotEqual(refs[0], refs[1])


if __name__ == "__main__":
    unittest.main()
