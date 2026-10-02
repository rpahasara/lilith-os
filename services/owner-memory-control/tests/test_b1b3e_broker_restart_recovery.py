"""15B2b-B1b-3e: the controlled broker-restart recovery record (TEST-ONLY).

Record: docs/architecture/slice-15b2b-b1b3e-broker-restart-recovery.md.

Pins the reviewed candidate and that the record restores nothing by itself:
owner acceptance and the separate re-pin are still required, and nothing
downstream (B-5, Condition 3/4, M-B1) is claimed.
"""

from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
RECORD = ROOT / "docs/architecture/slice-15b2b-b1b3e-broker-restart-recovery.md"

CANDIDATE = "a30bd7d6e26a75e4eba863c08622aebbbaf72928bc9dc7737fc1f7aa6473069d"
INCARNATION = "c4b9cb38d7a041dc91db0d8ada7e8d04"
BOOT = "eea461c3-60f0-4b10-8ee9-556dcef19711"
LIBRARIES = "818994544397da37d5a97e3799afff314608a7aa00cad50c968a90b86f41ce60"


class BrokerRestartRecoveryRecordTests(unittest.TestCase):
    def setUp(self):
        self.text = RECORD.read_text(encoding="utf-8")
        self.state = self.text.split("## 9. State", 1)[1]

    def test_candidate_identity(self):
        for value in (CANDIDATE, INCARNATION, BOOT, LIBRARIES, "35622", "26369693",
                      "4df22e74fc616136970707fd039bc72d06811cadf68177343bf0f5b3376ff42d"):
            self.assertIn(value, self.text)

    def test_only_mutation_is_the_broker_restart(self):
        self.assertIn("sudo -n /usr/bin/systemctl restart lilith-memory-broker.service", self.text)
        for line in ("NO REBOOT", "NO PACKAGE HOLD", "BROKER PRESERVATION NOT YET RESTORED"):
            self.assertIn(line, self.state)

    def test_acceptance_is_pending_and_nothing_downstream_is_claimed(self):
        self.assertIn("OWNER ACCEPTED (§6, broker runtime scope only)", self.state)
        for line in ("B-5 GRANT REMAINS VOID", "CONDITION 3 NOT YET RE-RUN", "CONDITION 4 NOT EVALUATED",
                     "CONDITION 5 OPEN", "M-B1 NOT AUTHORIZED", "NO REAL K-ROOT", "NO K-WIT", "NO REGISTRY V1",
                     "NO GENESIS PIN", "NO REAL RECORD 1", "FRESHNESS=UNKNOWN", "FIRST MEMORY NOT AUTHORIZED"):
            self.assertIn(line, self.state)
        for claim in ("BROKER_PRESERVATION=PASS", "CONDITION_3_FRESH_PR2=PASS", "PR1B_ELIGIBLE",
                      "B5_OWNER_AUTHORIZATION=GRANTED"):
            self.assertNotIn(claim, self.state)


    def test_owner_statement_is_recorded_verbatim_and_scoped(self):
        section = self.text.split("## 6. Owner acceptance", 1)[1].split("## 7.", 1)[0]
        self.assertNotIn("<to be supplied by the owner before merge>", self.text)
        for line in ("I accept the recovered broker candidate:", CANDIDATE, INCARNATION,
                     "- the boot remains eea461c3-60f0-4b10-8ee9-556dcef19711;",
                     "This acceptance authorizes only the reviewed broker re-pin in PR #128.",
                     "It does not re-grant B-5.", "It does not authorize Condition 3.",
                     "It does not authorize PR-1B eligibility.", "It does not authorize M-B1.",
                     "It does not authorize K-ROOT generation.", "It does not authorize First Memory."):
            self.assertIn(line, section)


if __name__ == "__main__":
    unittest.main()
