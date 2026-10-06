"""15B2b-B1b-3e: PR-1B eligibility sequence 3 record (TEST-ONLY).

Record: docs/architecture/slice-15b2b-b1b3e-pr1b-eligibility-sequence3.md.

Pins the import-only preflight, the single evaluator call, the 12 inputs, the
PR1B_ELIGIBLE result, that Condition 3 expired after the sequence without a
FAIL claim, the M-B1 carry-forward classification, and that nothing downstream
is authorized. It also checks the record's input list against the code.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
ARCH = ROOT / "docs/architecture"
RECORD = ARCH / "slice-15b2b-b1b3e-pr1b-eligibility-sequence3.md"
SEQUENCING = ROOT / "services/owner-memory-control/lilith_owner_memory/pr1b_sequencing.py"
INPUTS = ("p33Complete", "twoRealReplicasExist", "replicasCapabilityAdmitted", "replicaIndependenceEstablished",
          "replicasAgentUnreachableCopy", "ownerRegisterKnownEmpty", "pr3ToolingAccepted", "pr1aBaselineValid",
          "pr2InventoryRevalidated", "noUnreviewedTopologyChange", "openRisksAcknowledged", "pr1bAuthorized")


def section(text: str, start: str, end: str | None = None) -> str:
    body = text.split(start, 1)[1]
    return body.split(end, 1)[0] if end else body


def flat(text: str) -> str:
    return " ".join(text.split())


class EligibilitySequence3Tests(unittest.TestCase):
    def setUp(self):
        self.text = RECORD.read_text(encoding="utf-8")
        self.state = section(self.text, "## 12. State")
        self.flat = flat(self.text)

    def test_preflight_pass_explicit_ubuntu_zero_calls(self):
        pre = section(self.text, "## 3. Evaluator preflight", "## 4.")
        for line in ("WSL_DISTRO = Ubuntu-24.04", "LILITH_MEMORY_IMPORT = PASS", "RFC8785_IMPORT = PASS",
                     "PR1B_SEQUENCING_IMPORT = PASS", "EVALUATE_ELIGIBILITY_CALLABLE = YES",
                     "EVALUATE_ELIGIBILITY_CALL_COUNT = 0", "EVALUATOR_PREFLIGHT = PASS"):
            self.assertIn(line, pre)
        self.assertIn("`-d Ubuntu-24.04`", pre)
        self.assertIn("EVALUATOR_PREFLIGHT = PASS (WSL Ubuntu-24.04; EVALUATE_ELIGIBILITY_CALL_COUNT = 0)",
                      self.state)

    def test_condition3_pass_then_expired_without_fail(self):
        for line in ("CONDITION_3_FRESH_PR2 = PASS (2026-10-05T20:10:01Z-20:15:09Z)",
                     "CONDITION_3_CURRENT = NOT_ESTABLISHED AFTER SEQUENCE END (EXPIRED; REVALIDATE, NOT FAIL)"):
            self.assertIn(line, self.state)
        self.assertIn("CONDITION_3_CURRENT = ESTABLISHED (at the evaluator call)", self.text)
        self.assertIn("That expiry is REVALIDATE, not FAIL.", self.flat)
        self.assertNotIn("CONDITION_3_FRESH_PR2 = FAIL", self.text)

    def test_single_call_all_inputs_true_result(self):
        for line in ("EVALUATOR CALL COUNT = 1", "ALL 12 INPUTS TRUE",
                     "EVALUATOR RESULT = PR1B_ELIGIBLE; REASONS = []", "PR1B_ELIGIBLE = TRUE"):
            self.assertIn(line, self.state)
        self.assertIn("RESULT status = PR1B_ELIGIBLE | reasons = [] | eligible = True", self.text)
        table = section(self.text, "## 6. Eligibility inputs", "## 7.")
        rows = re.findall(r"^\| `(\w+)` \|", table, flags=re.M)
        self.assertEqual(tuple(rows), INPUTS)

    def test_record_inputs_match_code(self):
        code = SEQUENCING.read_text(encoding="utf-8")
        block = code.split("PRECONDITIONS = {", 1)[1].split("}", 1)[0]
        self.assertEqual(tuple(re.findall(r'"(\w+)":', block)), INPUTS)

    def test_carry_forward_resolved_as_b_with_c_kept_as_history(self):
        for line in ("COMPLETED_HISTORICAL_RESULT = PR1B_ELIGIBLE", "REUSABLE_FOR_LATER_M_B1 = NO",
                     "M-B1 CARRY-FORWARD (PRE-DECISION) = C. AMBIGUOUS — OWNER/ARCHITECTURE DECISION REQUIRED",
                     "M-B1 CARRY-FORWARD (CURRENT, OWNER DECISION) = "
                     "B. FRESH_ELIGIBILITY_EVALUATION_REQUIRED_FOR_M_B1"):
            self.assertIn(line, self.state)
        self.assertNotIn("M-B1 CARRY-FORWARD = C.", self.state)
        determination = flat(section(self.text, "## 9. M-B1 carry-forward determination (pre-decision analysis)",
                                     "## 10."))
        self.assertIn("its `C` classification is no longer current", determination)
        self.assertIn("**Pre-decision classification: `C. AMBIGUOUS — OWNER/ARCHITECTURE DECISION REQUIRED`.**",
                      determination)
        for phrase in ("re-check eligibility; nothing written",
                       "does **not** retroactively invalidate the completed evaluation"):
            self.assertIn(phrase, determination)
        self.assertNotIn("EVALUATION_RESULT_CARRIES_FORWARD", self.text)
        self.assertIn("slice-15b2b-b1b3e-mb1-eligibility-carry-forward-owner-decision.md", self.text)

    def test_kwit_pr2_and_downstream_not_authorized(self):
        for line in ("FRESH PR-2 IMMEDIATELY BEFORE GENERATE_K_WIT REMAINS MANDATORY", "M-B1 = NOT AUTHORIZED",
                     "KROOT = NOT AUTHORIZED", "KWIT = NOT AUTHORIZED",
                     "REGISTRY / GENESIS MUTATION = NOT AUTHORIZED", "FIRST MEMORY = NOT AUTHORIZED",
                     "FRESHNESS=UNKNOWN"):
            self.assertIn(line, self.state)
        for claim in ("M-B1 = AUTHORIZED", "KROOT = AUTHORIZED", "KWIT = AUTHORIZED", "FIRST MEMORY = AUTHORIZED",
                      "FRESHNESS=CURRENT"):
            self.assertNotIn(claim, self.text)

    def test_no_mutation_and_no_private_paths(self):
        for line in ("NO PACKAGE INSTALLATION", "NO DEV, CLOUD, IAM, REPLICA OR RUNTIME MUTATION",
                     "NO REPOSITORY CHANGE DURING THE LIVE SEQUENCE"):
            self.assertIn(line, self.state)
        self.assertNotRegex(self.text, r"[A-Za-z]:\\Users\\|/root/|/home/")
        self.assertIn("6a94d85387ef51aca8d7b432bfaf2d38385744e12b6e21949f3c28965b80137c", self.text)


if __name__ == "__main__":
    unittest.main()
