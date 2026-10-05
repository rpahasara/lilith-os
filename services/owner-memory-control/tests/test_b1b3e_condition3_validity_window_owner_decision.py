"""15B2b-B1b-3e M-B1 Condition 3: the validity-window owner decision record (TEST-ONLY).

Record: docs/architecture/slice-15b2b-b1b3e-condition3-validity-window-owner-decision.md.

Pins the event- and sequence-bounded validity model, the expiry semantics
(REVALIDATE, not FAIL), the package / apt-timer / needrestart decisions, and
that the record authorizes nothing downstream (B-5, eligibility, M-B1).
"""

from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
RECORD = ROOT / "docs/architecture/slice-15b2b-b1b3e-condition3-validity-window-owner-decision.md"


class Condition3ValidityWindowDecisionTests(unittest.TestCase):
    def setUp(self):
        self.text = RECORD.read_text(encoding="utf-8")
        self.model = self.text.split("## 1. Condition 3 validity model", 1)[1].split("## 2.", 1)[0]
        self.model = " ".join(self.model.split())
        self.posture = self.text.split("## 5. Current posture", 1)[1]
        self.flat = " ".join(self.text.split())

    def test_validity_model(self):
        self.assertIn("CONDITION_3_VALIDITY_MODEL=EVENT_BOUNDED_AND_SEQUENCE_BOUNDED", self.text)
        self.assertIn("NO UNIVERSAL FIXED WALL-CLOCK DURATION", self.model)

    def test_use_requirements(self):
        self.assertIn("**immediately before** `CHECK_ELIGIBILITY`", self.model)
        self.assertIn("**same continuous owner-authorized eligibility sequence**", self.model)
        self.assertIn("all required evidence remains current under", self.model)
        self.assertIn("ADR-0015", self.model)

    def test_expiry_is_revalidate_not_fail(self):
        self.assertIn("time / sequence expiry -> evidence NOT CURRENT / REVALIDATE (not reusable)", self.text)
        self.assertIn("time / sequence expiry -/-> control FAIL", self.text)
        for trigger in ("unattended package-install opportunity", "material dependency drift",
                        "G-1 … G-9", "broker process replacement", "host reboot",
                        "freshly re-compared", "suspension or end of the authorized eligibility sequence"):
            self.assertIn(trigger, self.flat)

    def test_package_timer_needrestart_decisions(self):
        self.assertIn("**No package-hold strategy is accepted.**", self.text)
        self.assertIn("**no apt timer change**", self.text)
        self.assertIn("**remains unchanged**; no needrestart mutation is authorized", self.flat)
        for line in ("NO PACKAGE HOLD", "NO APT TIMER CHANGE", "NO NEEDRESTART CHANGE"):
            self.assertIn(line, self.posture)

    def test_authorizes_nothing_downstream(self):
        for line in ("B-5 = WITHHELD", "CHECK_ELIGIBILITY = NOT RUN / NOT AUTHORIZED", "M-B1 NOT AUTHORIZED",
                     "FIRST MEMORY NOT AUTHORIZED", "NO CHECK_ELIGIBILITY RUN", "NO B-5 GRANT"):
            self.assertIn(line, self.posture)
        for claim in ("PR1B_ELIGIBLE", "B5_OWNER_AUTHORIZATION=GRANTED", "CONDITION_3_FRESH_PR2=PASS"):
            self.assertNotIn(claim, self.text)


if __name__ == "__main__":
    unittest.main()
