"""15B2b-B1b-3e M-B1 Condition 2: the cfa0b3e DEV deploy boundary review record (TEST-ONLY).

Record: docs/architecture/slice-15b2b-b1b3e-condition2-dev-deploy-boundary.md.

The run logs are evidence outside the repository; this pins what the record
claims, so that a later edit cannot silently change the reviewed result or
over-claim authorization.
"""

from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
RECORD = ROOT / "docs/architecture/slice-15b2b-b1b3e-condition2-dev-deploy-boundary.md"

ACCEPTED_RUN = "36552218231"
CFA0B3E_RUN = "36619219267"
FULL_RESULT_SET = "f18692342cd62572affa54c83f9d390d21ac183e85dc8496dbadb0d5f3f49f9b"
DR5_BLOCK = "a1d98773bcd07c39b2a17f0628f75db858a3e1e6bcd19e7bcd8918c0e79f1390"
PREDEPLOY_BLOCK = "f50870420c10149914b8d2a02116708ec89ea5a8f746a847fbe88df058f54cae"
REPLICA_A_MANIFEST = "fbdd045c390506f8174192dbea6a6444e6f3e819c9a24e90c61155ec9238978b"


class Condition2RecordTests(unittest.TestCase):
    def setUp(self):
        self.text = RECORD.read_text(encoding="utf-8")

    def test_reviewed_runs_and_digests(self):
        for value in (ACCEPTED_RUN, CFA0B3E_RUN, "36673169614", "36989394282", "36985542087",
                      FULL_RESULT_SET, DR5_BLOCK, PREDEPLOY_BLOCK, REPLICA_A_MANIFEST):
            self.assertIn(value, self.text)

    def test_boundary_lines(self):
        for line in ("PR1_AUTHORITY_BOUNDARY maturity=P1A-9", "AUTHORITY_BOUNDARY_PROOF=PASS maturity=L1c.3",
                     "ACTIVATION=NOT_ACCEPTED reason=GRANT_ABSENT", "FEDERATION_BOUNDARY=PASS"):
            self.assertIn(line, self.text)

    def test_acceptance_is_only_effective_on_merge(self):
        self.assertIn("CONDITION_2_DEV_DEPLOY_BOUNDARY=ACCEPTED   (effective when this record is reviewed and merged)",
                      self.text)

    def test_state_does_not_claim_authorization(self):
        state = self.text.split("## 9. State", 1)[1]
        for line in ("CONDITION_2_READY_FOR_OWNER_REVIEW", "CONDITION 1 CLOSED", "CONDITION 2 OPEN UNTIL OWNER REVIEW",
                     "CONDITION 3 OPEN", "CONDITION 4 OPEN", "CONDITION 5 OPEN", "M-B1 NOT AUTHORIZED",
                     "NO M-B1 COMMAND ISSUED", "NO REAL K-ROOT", "NO K-WIT", "NO REGISTRY V1", "NO GENESIS PIN",
                     "NO REAL RECORD 1", "FRESHNESS=UNKNOWN", "FIRST MEMORY NOT AUTHORIZED"):
            self.assertIn(line, state)
        for claim in ("M-B1 AUTHORIZED\n", "PR1B_ELIGIBLE", "CONDITION 3 CLOSED"):
            self.assertNotIn(claim, state)

    def test_condition3_items_are_not_claimed_as_observed(self):
        self.assertIn("not re-observed by a deploy, by design", self.text)
        self.assertIn("Condition 3 re-observes", self.text)


if __name__ == "__main__":
    unittest.main()
