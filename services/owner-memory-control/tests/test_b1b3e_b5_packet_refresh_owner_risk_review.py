"""15B2b-B1b-3e: the B-5 packet refresh and owner risk review record (TEST-ONLY).

Record: docs/architecture/slice-15b2b-b1b3e-b5-packet-refresh-owner-risk-review.md.

Pins the owner dispositions of OR-1 … OR-9, the replacement OR-8
acknowledgement, the packet-ready state, and that nothing downstream (a B-5
grant, `pr1bAuthorized`, eligibility, M-B1, First Memory) is claimed.
"""

from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
RECORD = ROOT / "docs/architecture/slice-15b2b-b1b3e-b5-packet-refresh-owner-risk-review.md"


class B5PacketRefreshRiskReviewTests(unittest.TestCase):
    def setUp(self):
        self.text = RECORD.read_text(encoding="utf-8")
        self.state = self.text.split("## 7. State", 1)[1]
        self.or8 = " ".join(self.text.split("## 5. Replacement OR-8 acknowledgement", 1)[1]
                            .split("## 6.", 1)[0].replace(">", " ").split())

    def test_or_dispositions(self):
        for line in ("OR-1 REAFFIRMED", "OR-2 / DR-3 REAFFIRMED", "CROSS-ENVIRONMENT osAdminLogin REAFFIRMED",
                     "OR-3 REAFFIRMED (BOUNDED)", "OR-4 REAFFIRMED (QUALIFIED)", "OR-5 REMAINS CLOSED",
                     "OR-6 REMAINS CLOSED", "OR-7 REAFFIRMED",
                     "OR-8 NEW ACKNOWLEDGEMENT ADOPTED (2026-09-29 ACKNOWLEDGEMENT VOID AND SUPERSEDED)",
                     "OR-9 NOTED AS LIMIT (NOT AN ACCEPTED RISK)"):
            self.assertIn(line, self.state)

    def test_or4_qualification_keeps_both_replica_limit(self):
        flat = " ".join(self.text.split())
        self.assertIn("owner freshness does not protect against rollback or compromise of both replicas "
                      "simultaneously", flat)

    def test_replacement_or8_acknowledgement(self):
        for phrase in ("ACCEPTABLE_PRECONDITION_DEBT for LILITH DEV_SYNTHETIC only",
                       "CONDITION_3_VALIDITY_MODEL=EVENT_BOUNDED_AND_SEQUENCE_BOUNDED",
                       "freshly collected immediately before `CHECK_ELIGIBILITY`",
                       "inside one continuous owner-authorized eligibility sequence",
                       "no expiry trigger (a)-(h) occurs between collection and use",
                       "immediately before `GENERATE_K_WIT`",
                       "Expiry means REVALIDATE, not FAIL.",
                       "grants no B-5", "authorizes no CHECK_ELIGIBILITY", "authorizes no M-B1",
                       "does not apply to PROD"):
            self.assertIn(phrase, self.or8)

    def test_packet_ready_but_not_granted(self):
        for line in ("TECHNICAL_PACKET_COMPONENTS_COMPLETE = YES", "B5_PACKET_READY_FOR_SEPARATE_OWNER_DECISION",
                     "B-5 = WITHHELD", "NO B-5 GRANT; NO pr1bAuthorized INPUT ESTABLISHED"):
            self.assertIn(line, self.state)
        for claim in ("B5_OWNER_AUTHORIZATION=GRANTED", "pr1bAuthorized=True", "pr1bAuthorized = True",
                      "PR1B_ELIGIBLE"):
            self.assertNotIn(claim, self.text)

    def test_posture_claims_no_downstream_authorization(self):
        for line in ("CONDITION 3 = NOT CURRENTLY ESTABLISHED", "CHECK_ELIGIBILITY = NOT RUN / NOT AUTHORIZED",
                     "M-B1 NOT AUTHORIZED", "FIRST MEMORY NOT AUTHORIZED", "FRESHNESS=UNKNOWN"):
            self.assertIn(line, self.state)


if __name__ == "__main__":
    unittest.main()
