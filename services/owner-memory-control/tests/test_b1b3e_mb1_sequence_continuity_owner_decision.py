"""15B2b-B1b-3e: the M-B1 sequence continuity owner decision and handoff preflight (TEST-ONLY).

Records:
- docs/architecture/slice-15b2b-b1b3e-mb1-sequence-continuity-owner-decision.md
- docs/architecture/slice-15b2b-b1b3e-mb1-handoff-preflight.md

Pins MB1_SEQUENCE_CONTINUITY = OWNER_ATTENDED_EVENT_BOUNDED_HANDOFF, its
continuity, freeze, eligibility, go and STOP semantics, the G-A … G-E
resolution, the pinned script and bundle, and that nothing is authorized. It
also checks the facts the decision relies on still hold in the pinned script
(C0 before K1) and the sequencer (M-B1 is GENERATE_K_ROOT).
"""

from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
ARCH = ROOT / "docs/architecture"
DECISION = ARCH / "slice-15b2b-b1b3e-mb1-sequence-continuity-owner-decision.md"
PREFLIGHT = ARCH / "slice-15b2b-b1b3e-mb1-handoff-preflight.md"
PINS = ARCH / "slice-15b2b-b1b3e-mb1-final-package-pins.md"
SEQUENCING = ROOT / "services/owner-memory-control/lilith_owner_memory/pr1b_sequencing.py"
SCRIPT_SHA = "09cbc9bee7b58af7bab45bb903c6e10cb51ae6c62b20705be12de274bbe5216b"
BUNDLE_SHA = "7f07e158aa5a0b3c31ee63e25ae25116c92f26a402bc6924422d7c95e2edc2c1"


def section(text: str, start: str, end: str | None = None) -> str:
    body = text.split(start, 1)[1]
    return body.split(end, 1)[0] if end else body


def flat(text: str) -> str:
    return " ".join(text.split())


class SequenceContinuityDecisionTests(unittest.TestCase):
    def setUp(self):
        self.text = DECISION.read_text(encoding="utf-8")
        self.state = section(self.text, "## 5. State")
        self.verbatim = flat(section(self.text, "## 1. Owner decision (verbatim)", "## 2.").replace(">", " "))

    def test_classification_and_verbatim(self):
        self.assertIn("MB1_SEQUENCE_CONTINUITY = OWNER_ATTENDED_EVENT_BOUNDED_HANDOFF", self.state)
        self.assertTrue(self.verbatim.startswith(
            "I adopt `MB1_SEQUENCE_CONTINUITY = OWNER_ATTENDED_EVENT_BOUNDED_HANDOFF`."))
        self.assertTrue(self.verbatim.endswith("handoff file, implementation, or runtime mechanism."))

    def test_governance_continuity_no_ttl_handoff_does_not_end(self):
        for line in ("CONTINUITY = GOVERNANCE CONTINUITY (NOT PROCESS / SHELL / TERMINAL / SESSION / NETWORK / HOST / "
                     "DEVICE)",
                     "LAPTOP -> S25 HANDOFF (MTP, UNPLUG, AIRPLANE MODE, TERMUX) DOES NOT END THE SEQUENCE",
                     "NO WALL-CLOCK TTL; FINITE DELAY ALONE IS NOT TERMINATION",
                     "LAPTOP LOCK / SLEEP / TERMINAL CLOSE / SHELL EXIT / CLAUDE SESSION END / TRANSIENT LAPTOP "
                     "NETWORK LOSS: NOT INTRINSIC TERMINATORS",
                     "UNCERTAINTY ABOUT REQUIRED CURRENT EVIDENCE ENDS THE SEQUENCE"):
            self.assertIn(line, self.state)
        self.assertIn("It is not tied to a Python process, shell, terminal, Claude session, network connection, "
                      "host, or physical device.", self.verbatim)

    def test_freeze_dev_side_and_in_sequence_eligibility(self):
        for line in ("DEPLOY FREEZE FROM FRESH DR-5 UNTIL M-B1 COMPLETES OR ABORTS",
                     "NO ACTIVE DEV RE-POLLING REQUIRED FOR THE HANDOFF",
                     "KNOWN, SUSPECTED OR UNCERTAIN B-5 §9 STOP OR G-1…G-9 ENDS THE SEQUENCE",
                     "OWNER-RUN PHONE / REPLICA B / CUSTODY BLOCK REPEATED IN-SEQUENCE BEFORE FINAL CONDITION 3",
                     "FINAL CONDITION 3 FRESH",
                     "CHECK_ELIGIBILITY EXACTLY ONCE; PR1B_ELIGIBLE REQUIRED"):
            self.assertIn(line, self.state)

    def test_go_semantics_and_pins(self):
        for line in ("M-B1 GO ONLY AFTER PR1B_ELIGIBLE", "M-B1 GO ONE-ATTEMPT AND SEQUENCE-SCOPED; NAMES BOTH PINS",
                     "M-B1 == GENERATE_K_ROOT", "C0 GENERATE PERMITS K-ROOT GENERATION IN THAT INVOCATION"):
            self.assertIn(line, self.state)
        semantics = section(self.text, "## 2. Semantics recorded", "## 3.")
        self.assertIn(SCRIPT_SHA, semantics)
        self.assertIn(BUNDLE_SHA, semantics)
        pins = PINS.read_text(encoding="utf-8")
        self.assertIn(SCRIPT_SHA, pins)
        self.assertIn(BUNDLE_SHA[:8], pins)

    def test_stop_no_reuse_and_historical_eligibility(self):
        for line in ("STOP BEFORE C0: NO K-ROOT; SEQUENCE ENDS; GO NOT REUSABLE",
                     "STOP AFTER K1: FAILED-CANDIDATE CUSTODY; NO RETRY UNDER THE SAME SEQUENCE OR GO",
                     "ENDED SEQUENCE: PR1B_ELIGIBLE HISTORICAL ONLY; NOT REUSABLE"):
            self.assertIn(line, self.state)

    def test_kwit_pr2_separate_no_bridge(self):
        for line in ("FRESH PR-2 IMMEDIATELY BEFORE GENERATE_K_WIT REMAINS MANDATORY AND SEPARATE",
                     "NO BRIDGE TOKEN, NONCE, SIGNED ARTIFACT, HANDOFF FILE, RUNTIME STATE OR IMPLEMENTATION"):
            self.assertIn(line, self.state)

    def test_gaps_resolved_and_runbook_order(self):
        self.assertIn("G-A … G-E RESOLVED", self.state)
        gaps = section(self.text, "## 3. Gap reconciliation", "## 4.")
        for gap in ("G-A", "G-B", "G-C", "G-D", "G-E"):
            row = next(line for line in gaps.splitlines() if line.startswith(f"| {gap} "))
            self.assertIn("**RESOLVED**", row)
        runbook = section(self.text, "## 4. Resulting future sequence", "## 5.")
        order = ["fresh DR-5", "owner-run phone / Replica B / custody block", "fresh final Condition 3",
                 "`CHECK_ELIGIBILITY` exactly once", "one-attempt M-B1 go", "MTP transfer", "G0 / G1 / T1",
                 "C0 `GENERATE`", "K1 `root-keygen`"]
        positions = [runbook.index(step) for step in order]
        self.assertEqual(positions, sorted(positions))
        self.assertIn("NOT executed, NOT authorized", runbook)

    def test_nothing_authorized(self):
        for line in ("RUNBOOK NOT AUTHORIZED; NOT EXECUTED", "M-B1 GO STATEMENT NOT GIVEN", "M-B1 = NOT AUTHORIZED",
                     "KROOT = NOT AUTHORIZED", "KWIT = NOT AUTHORIZED", "REGISTRY / GENESIS MUTATION = NOT AUTHORIZED",
                     "FIRST MEMORY = NOT AUTHORIZED", "FRESHNESS=UNKNOWN", "NO LIVE SYSTEM CONTACTED"):
            self.assertIn(line, self.state)
        for claim in ("M-B1 = AUTHORIZED", "KROOT = AUTHORIZED", "KWIT = AUTHORIZED", "FIRST MEMORY = AUTHORIZED",
                      "M-B1 GO STATEMENT GIVEN", "FRESHNESS=CURRENT"):
            self.assertNotIn(claim, self.text)


class HandoffPreflightTests(unittest.TestCase):
    def setUp(self):
        self.text = PREFLIGHT.read_text(encoding="utf-8")
        self.state = section(self.text, "## 4. Current classification")

    def test_pre_decision_kept_current_ready(self):
        for line in ("PRE-DECISION: NOT_READY_FOR_OWNER_M_B1_DECISION", "CURRENT: READY_FOR_OWNER_M_B1_DECISION",
                     "G-A … G-E RESOLVED BY MB1_SEQUENCE_CONTINUITY = OWNER_ATTENDED_EVENT_BOUNDED_HANDOFF",
                     "NO CODE, SCRIPT, BUNDLE OR WORKFLOW CHANGE REQUIRED", "M-B1 = NOT AUTHORIZED",
                     "KROOT = NOT AUTHORIZED", "KWIT = NOT AUTHORIZED", "FIRST MEMORY = NOT AUTHORIZED"):
            self.assertIn(line, self.state)
        self.assertIn("**It authorizes nothing.**", self.text)


class RepositoryFactsTests(unittest.TestCase):
    def test_m_b1_is_generate_k_root_in_sequencer(self):
        code = SEQUENCING.read_text(encoding="utf-8")
        self.assertIn('StepV1("GENERATE_K_ROOT", "PR1B_ELIGIBLE", "K_ROOT_GENERATED", "M-B1"', code)

    def test_pinned_script_has_gates_then_c0_then_k1(self):
        script = section(PINS.read_text(encoding="utf-8"), "## 3. Final operator script", "## 4.")
        marks = ["# ---- G0 phone state", "# ---- G1 Replica B baseline", "# ---- T1 transport copy",
                 "# ---- C0 last owner confirmation", "# ---- K1 the ONLY private write: root-keygen"]
        positions = [script.index(mark) for mark in marks]
        self.assertEqual(positions, sorted(positions))
        self.assertIn('[ "$answer" = GENERATE ]', script)
        self.assertNotIn("PR1B_ELIGIBLE", script)


if __name__ == "__main__":
    unittest.main()
