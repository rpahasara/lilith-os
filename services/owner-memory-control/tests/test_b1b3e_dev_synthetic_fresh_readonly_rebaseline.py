"""15B2b-B1b-3e: the 2026-10-05 fresh read-only DEV_SYNTHETIC rebaseline record (TEST-ONLY).

Record: docs/architecture/slice-15b2b-b1b3e-dev-synthetic-fresh-readonly-rebaseline.md.

Pins the window, control SHA and raw evidence digest, the observed broker
identity, the owner disposition of the unrelated cloud project, and that the
record is observational evidence only: nothing downstream (Condition 3, B-5,
eligibility, M-B1, First Memory) is claimed.
"""

from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
RECORD = ROOT / "docs/architecture/slice-15b2b-b1b3e-dev-synthetic-fresh-readonly-rebaseline.md"


class FreshReadonlyRebaselineRecordTests(unittest.TestCase):
    def setUp(self):
        self.text = RECORD.read_text(encoding="utf-8")
        self.state = self.text.split("## 9. State", 1)[1]
        self.flat = " ".join(self.text.split())

    def test_accepted_as_observational_evidence_only(self):
        self.assertIn("DEV_SYNTHETIC_FRESH_READONLY_REBASELINE=ACCEPTED_AS_OBSERVATIONAL_EVIDENCE", self.state)

    def test_window_control_and_evidence(self):
        for value in ("2026-10-05T16:12:17Z", "16:31:27Z", "a73fa5e9e9cee68e026981fbee80a9aadd594191",
                      "e7bc0df5e3a32d6bf63d1dcc51bf3d54157b557b2dae0a47695d2782d46aa429"):
            self.assertIn(value, self.text)

    def test_no_global_invalidator_and_broker_identity(self):
        self.assertIn("NO GLOBAL INVALIDATOR G-1..G-9 OBSERVED", self.state)
        for value in ("BROKER_PRESERVATION=PASS", "c4b9cb38d7a041dc91db0d8ada7e8d04",
                      "a30bd7d6e26a75e4eba863c08622aebbbaf72928bc9dc7737fc1f7aa6473069d",
                      "eea461c3-60f0-4b10-8ee9-556dcef19711"):
            self.assertIn(value, self.text)

    def test_unrelated_project_owner_confirmed(self):
        self.assertIn("AU4LABS-WEB-RP-2026 = OWNER_CONFIRMED_UNRELATED / NON_MATERIAL", self.state)
        self.assertNotIn("OWNER_CONFIRMATION_PENDING", self.text)
        self.assertIn("applies to the **observed 2026-10-05 state only**. It is **not** a permanent exemption",
                      self.flat)

    def test_state_claims_no_downstream_authorization(self):
        for line in ("B-5 = WITHHELD", "FRESHNESS=UNKNOWN", "CONDITION 3 = NOT CURRENTLY ESTABLISHED",
                     "CHECK_ELIGIBILITY = NOT RUN / NOT AUTHORIZED", "M-B1 NOT AUTHORIZED",
                     "FIRST MEMORY NOT AUTHORIZED", "B5_EVIDENCE_PACKET_READINESS = NOT_READY",
                     "REPLICA B NOT CONTACTED"):
            self.assertIn(line, self.state)
        self.assertIn("**Condition 3 current satisfaction = NOT ESTABLISHED.**", self.text)
        for claim in ("PR1B_ELIGIBLE", "CONDITION_3_FRESH_PR2=PASS", "B5_OWNER_AUTHORIZATION=GRANTED",
                      "B5_EVIDENCE_PACKET_READINESS = READY"):
            self.assertNotIn(claim, self.text)


if __name__ == "__main__":
    unittest.main()
