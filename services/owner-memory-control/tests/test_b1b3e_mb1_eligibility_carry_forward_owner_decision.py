"""15B2b-B1b-3e: the M-B1 eligibility carry-forward owner decision (TEST-ONLY).

Record: docs/architecture/slice-15b2b-b1b3e-mb1-eligibility-carry-forward-owner-decision.md.

Pins owner decision B: Sequence 3 stays a completed PR1B_ELIGIBLE result but is
not reusable for a later M-B1; a future M-B1 sequence must freshly establish
eligibility (fresh Condition 3, CHECK_ELIGIBILITY exactly once, same continuous
sequence); M-B1 still needs a separate owner go; nothing is authorized; and the
rule matches the sequencer crash matrix C-1 entry in code.
"""

from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
RECORD = ROOT / "docs/architecture/slice-15b2b-b1b3e-mb1-eligibility-carry-forward-owner-decision.md"
SEQUENCING = ROOT / "services/owner-memory-control/lilith_owner_memory/pr1b_sequencing.py"


def section(text: str, start: str, end: str | None = None) -> str:
    body = text.split(start, 1)[1]
    return body.split(end, 1)[0] if end else body


def flat(text: str) -> str:
    return " ".join(text.replace(">", " ").split())


class CarryForwardOwnerDecisionTests(unittest.TestCase):
    def setUp(self):
        self.text = RECORD.read_text(encoding="utf-8")
        self.state = section(self.text, "## 6. State")

    def test_owner_selected_b_not_a_c_resolved(self):
        statement = flat(section(self.text, "## 1. Owner decision (verbatim)", "## 2."))
        self.assertTrue(statement.startswith("I choose B: a fresh eligibility evaluation is required for M-B1."))
        for line in ("MB1_ELIGIBILITY_CARRY_FORWARD = B. FRESH_ELIGIBILITY_EVALUATION_REQUIRED_FOR_M_B1",
                     "CARRY-FORWARD A (EVALUATION_RESULT_CARRIES_FORWARD) NOT ACCEPTED",
                     "CARRY-FORWARD C (AMBIGUOUS) RESOLVED; NO LONGER CURRENT"):
            self.assertIn(line, self.state)

    def test_sequence3_stays_successful_but_not_reusable(self):
        for line in ("SEQUENCE 3: COMPLETED_HISTORICAL_RESULT = PR1B_ELIGIBLE",
                     "SEQUENCE 3: REUSABLE_FOR_LATER_M_B1 = NO",
                     "SEQUENCE 3 CONDITION 3 EXPIRED (TRIGGER (h)): REVALIDATE, NOT FAIL"):
            self.assertIn(line, self.state)
        facts = flat(section(self.text, "## 2. Sequence 3 stays a successful result", "## 3."))
        for phrase in ("`PR1B_ELIGIBLE`, `reasons = []`", "all 12 `True`", "exactly 1",
                       "does **not** make Sequence 3 unsuccessful after the fact"):
            self.assertIn(phrase, facts)

    def test_future_m_b1_sequence_rule(self):
        for line in ("FUTURE M-B1 SEQUENCE: FRESH FINAL CONDITION 3 REQUIRED",
                     "FUTURE M-B1 SEQUENCE: CHECK_ELIGIBILITY EXACTLY ONCE",
                     "FUTURE M-B1 SEQUENCE: ELIGIBILITY AND M-B1 IN THE SAME CONTINUOUS SEQUENCE",
                     "NO WALL-CLOCK TTL; SEQUENCE-BASED"):
            self.assertIn(line, self.state)
        rule = flat(section(self.text, "## 3. The rule", "## 4."))
        for phrase in ("**not sufficient by itself to begin a later M-B1 ceremony**",
                       "a fresh final Condition 3 window", "**exactly once**",
                       "**only inside that same continuous sequence**",
                       "M-B1 only if the owner has **separately** authorized M-B1", "It sets no wall-clock TTL"):
            self.assertIn(phrase, rule)

    def test_crash_matrix_alignment_matches_code(self):
        code = SEQUENCING.read_text(encoding="utf-8")
        self.assertIn('"C-1 eligibility checked / K-ROOT absent": ("PR1B_ELIGIBLE", SAFE_RETRY, '
                      '"re-check eligibility; nothing written")', code)
        alignment = flat(section(self.text, "## 4. Alignment with the sequencer crash matrix", "## 5."))
        for phrase in ("C-1 eligibility checked / K-ROOT absent", "re-check eligibility; nothing written",
                       "**No implementation changed.**"):
            self.assertIn(phrase, alignment)

    def test_execution_authorization_separate_and_pins(self):
        go = section(self.text, "## 5. Execution authorization stays separate", "## 6.")
        for pin in ("09cbc9bee7b58af7bab45bb903c6e10cb51ae6c62b20705be12de274bbe5216b",
                    "7f07e158aa5a0b3c31ee63e25ae25116c92f26a402bc6924422d7c95e2edc2c1"):
            self.assertIn(pin, go)
        self.assertIn("immediately before `GENERATE_K_WIT` (M-B2) remains mandatory", flat(go))
        for line in ("PR1B_ELIGIBLE != M-B1 AUTHORIZATION", "M-B1 GO STATEMENT NOT GIVEN",
                     "FRESH PR-2 IMMEDIATELY BEFORE GENERATE_K_WIT REMAINS MANDATORY"):
            self.assertIn(line, self.state)

    def test_nothing_authorized(self):
        for line in ("M-B1 = NOT AUTHORIZED", "KROOT = NOT AUTHORIZED", "KWIT = NOT AUTHORIZED",
                     "REGISTRY / GENESIS MUTATION = NOT AUTHORIZED", "FIRST MEMORY = NOT AUTHORIZED",
                     "FRESHNESS=UNKNOWN", "NO LIVE SYSTEM CONTACTED"):
            self.assertIn(line, self.state)
        for claim in ("M-B1 = AUTHORIZED", "KROOT = AUTHORIZED", "KWIT = AUTHORIZED", "FIRST MEMORY = AUTHORIZED",
                      "FRESHNESS=CURRENT", "M-B1 GO STATEMENT GIVEN"):
            self.assertNotIn(claim, self.text)


if __name__ == "__main__":
    unittest.main()
