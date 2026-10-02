"""15B2b-B1b-3e M-B1 Condition 3 re-run: the fresh PR-2 revalidation PASS record (TEST-ONLY).

Record: docs/architecture/slice-15b2b-b1b3e-condition3-fresh-pr2-pass.md.

Pins the window, the recovered broker identity, the re-established rollback
conclusions, and that nothing downstream (B-5, eligibility, M-B1) is claimed.
"""

from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
RECORD = ROOT / "docs/architecture/slice-15b2b-b1b3e-condition3-fresh-pr2-pass.md"


class Condition3PassRecordTests(unittest.TestCase):
    def setUp(self):
        self.text = RECORD.read_text(encoding="utf-8")
        self.state = self.text.split("## 8. State", 1)[1]

    def test_window_and_evidence(self):
        for value in ("2026-10-02T12:08:38Z", "12:24:19Z", "fbaad554fd53fb3c31ca75159f53fdf24c333ca3",
                      "6afa46597ffeb5c9faf4c5e13552a3c50730ce219d8d63c85a04194bf5ad6d0c",
                      "2e68160971a3b0dd05ffcb6cdc464fc612afb2b522a57fb534b25c6af83c10ba"):
            self.assertIn(value, self.text)

    def test_recovered_broker_identity(self):
        for value in ("BROKER_PRESERVATION=PASS", "c4b9cb38d7a041dc91db0d8ada7e8d04",
                      "a30bd7d6e26a75e4eba863c08622aebbbaf72928bc9dc7737fc1f7aa6473069d",
                      "eea461c3-60f0-4b10-8ee9-556dcef19711", "`35622`", "`26369693`", "**0** of 25"):
            self.assertIn(value, self.text)

    def test_rollback_conclusions_re_established(self):
        for line in ("WHOLE-HOST / WHOLE-DISK ROLLBACK CAN PRESENT A SELF-CONSISTENT OLD AUTHORITY WORLD.",
                     "WHOLE-HOST ROLLBACK RESISTANCE = NOT ESTABLISHED.",
                     "INDEPENDENTLY PERSISTED FRESHNESS STATE = NONE."):
            self.assertIn(line, self.text)

    def test_package_window_bound_is_stated(self):
        self.assertIn("2026-10-03T06:39:01Z", self.text)
        self.assertIn("**none**", self.text)

    def test_state_claims_no_downstream_authorization(self):
        for line in ("CONDITION_3_FRESH_PR2=PASS", "CONDITION 3 OPEN UNTIL OWNER REVIEW", "CONDITION 4 NOT EVALUATED",
                     "CONDITION 5 OPEN", "B-5 GRANT REMAINS VOID", "M-B1 NOT AUTHORIZED", "NO M-B1 COMMAND ISSUED",
                     "NO REAL K-ROOT", "NO K-WIT", "NO REGISTRY V1", "NO GENESIS PIN", "NO REAL RECORD 1",
                     "FRESHNESS=UNKNOWN", "FIRST MEMORY NOT AUTHORIZED"):
            self.assertIn(line, self.state)
        for claim in ("PR1B_ELIGIBLE", "CONDITION_4_PR1B_ELIGIBILITY=ACCEPTED", "B5_OWNER_AUTHORIZATION=GRANTED"):
            self.assertNotIn(claim, self.text)


if __name__ == "__main__":
    unittest.main()
