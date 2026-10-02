"""15B2b-B1b-3e M-B1 Condition 3: the fresh PR-2 revalidation STOP record (TEST-ONLY).

Record: docs/architecture/slice-15b2b-b1b3e-condition3-fresh-pr2-stop.md.

Pins the failure and that nothing downstream is claimed: no eligibility, no
authorization, and the B-5 section 9 consequence stated.
"""

from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
RECORD = ROOT / "docs/architecture/slice-15b2b-b1b3e-condition3-fresh-pr2-stop.md"


class Condition3StopRecordTests(unittest.TestCase):
    def setUp(self):
        self.text = RECORD.read_text(encoding="utf-8")
        self.state = self.text.split("## 6. State", 1)[1]

    def test_failure_is_recorded(self):
        for value in ("BROKER_PRESERVATION=FAIL", "RUNTIME_SUBSTRATE_STALE_OR_UNREADABLE",
                      "ACCEPTED_IDENTITY_CHANGED:sharedLibrariesSha256", "/usr/lib/x86_64-linux-gnu/libcrypto.so.3",
                      "libssl3t64:amd64 3.0.13-0ubuntu3.15 3.0.13-0ubuntu3.16",
                      "b4e83101a277f4d0c98f77bfc3eaaafc7ae29a59a87f57d51af9e9846c8df6cb"):
            self.assertIn(value, self.text)

    def test_state_claims_no_pass_and_no_eligibility(self):
        for line in ("CONDITION_3_FRESH_PR2=FAIL", "CONDITION 4 NOT EVALUATED", "B5 GRANT VOID UNDER", "M-B1 NOT AUTHORIZED",
                     "NO M-B1 COMMAND ISSUED", "NO BROKER RESTART", "NO REAL K-ROOT", "NO K-WIT", "NO REGISTRY V1",
                     "NO GENESIS PIN", "NO REAL RECORD 1", "FRESHNESS=UNKNOWN", "FIRST MEMORY NOT AUTHORIZED"):
            self.assertIn(line, self.state)
        for claim in ("CONDITION_3_FRESH_PR2=PASS", "PR1B_ELIGIBLE", "CONDITION_4_PR1B_ELIGIBILITY=ACCEPTED"):
            self.assertNotIn(claim, self.text)

    def test_rollback_conclusions_re_established(self):
        for line in ("WHOLE-HOST / WHOLE-DISK ROLLBACK CAN PRESENT A SELF-CONSISTENT OLD AUTHORITY WORLD.",
                     "WHOLE-HOST ROLLBACK RESISTANCE = NOT ESTABLISHED.",
                     "INDEPENDENTLY PERSISTED FRESHNESS STATE = NONE."):
            self.assertIn(line, self.text)


if __name__ == "__main__":
    unittest.main()
