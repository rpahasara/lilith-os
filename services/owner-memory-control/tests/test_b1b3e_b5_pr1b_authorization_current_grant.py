"""15B2b-B1b-3e: the B-5 owner grant for the current DEV_SYNTHETIC packet (TEST-ONLY).

Record: docs/architecture/slice-15b2b-b1b3e-b5-pr1b-authorization-current-grant.md.

Pins that the owner explicitly granted B-5 for the current DEV_SYNTHETIC
packet only, after the packet and owner risk review were complete; that the
grant is not eligibility; that nothing downstream (Condition 3,
CHECK_ELIGIBILITY, M-B1, First Memory, freshness) is claimed; that it stays
subject to the packet §9 void and ADR-0015 revalidation rules; and that no
live action is represented as having occurred.
"""

from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
ARCH = ROOT / "docs/architecture"
RECORD = ARCH / "slice-15b2b-b1b3e-b5-pr1b-authorization-current-grant.md"
PACKET = ARCH / "slice-15b2b-b1b3e-b5-packet-refresh-owner-risk-review.md"
WITHHELD = ARCH / "slice-15b2b-b1b3e-b5-pr1b-authorization-withheld.md"


def flat(text: str) -> str:
    return " ".join(text.replace(">", " ").split())


def section(text: str, start: str, end: str | None = None) -> str:
    body = text.split(start, 1)[1]
    return body.split(end, 1)[0] if end else body


class B5CurrentGrantTests(unittest.TestCase):
    def setUp(self):
        self.text = RECORD.read_text(encoding="utf-8")
        self.flat = flat(self.text)
        self.state = section(self.text, "## 10. State")
        self.validity = " ".join(section(self.text, "## 7. Validity", "## 8.").split())

    def test_owner_explicitly_granted(self):
        statement = flat(section(self.text, "## 1. Owner statement (verbatim)", "## 2."))
        self.assertEqual(statement, "I grant B-5 for the current DEV_SYNTHETIC packet.")
        self.assertIn("B5_OWNER_AUTHORIZATION=GRANTED", self.state)
        self.assertIn("B5_OWNER_AUTHORIZATION=GRANTED", section(self.text, "Status:", "## 1."))

    def test_scope_is_current_dev_synthetic_packet_only(self):
        self.assertIn("SCOPE = CURRENT DEV_SYNTHETIC PACKET (PR #145) ONLY", self.state)
        self.assertIn("NOT APPLICABLE TO PROD", self.state)
        scope = flat(section(self.text, "## 4. Scope", "## 5."))
        for phrase in ("DEV_SYNTHETIC only", "current accepted B-5 packet", "not applicable to PROD",
                       "not a general future grant", "not permission to bypass later sequencing"):
            self.assertIn(phrase, scope)
        self.assertIn(PACKET.name, self.text)

    def test_packet_and_risk_review_complete_before_grant(self):
        for line in ("TECHNICAL PACKET COMPLETE BEFORE GRANT", "OWNER RISK REVIEW COMPLETE BEFORE GRANT"):
            self.assertIn(line, self.state)
        pre = section(self.text, "## 2. Preconditions satisfied before the grant", "## 3.")
        for line in ("TECHNICAL_PACKET_COMPONENTS_COMPLETE = YES", "B5_PACKET_READY_FOR_SEPARATE_OWNER_DECISION"):
            self.assertIn(line, pre)

    def test_grant_is_not_eligibility(self):
        for line in ("B-5 GRANTED != PR1B_ELIGIBLE", "PR1B_ELIGIBLE = NOT ESTABLISHED",
                     "pr1bAuthorized INPUT AUTHORIZED FOR A FUTURE CHECK_ELIGIBILITY ONLY; NOT SUPPLIED; "
                     "NOTHING EVALUATED"):
            self.assertIn(line, self.state)
        for claim in ("PR1B_ELIGIBLE = ESTABLISHED", "PR1B_ELIGIBLE=ESTABLISHED", "CHECK_ELIGIBILITY = PASS",
                      "M-B1 = AUTHORIZED", "FRESHNESS=CURRENT"):
            self.assertNotIn(claim, self.text)

    def test_downstream_posture(self):
        for line in ("CONDITION_3_CURRENT = NOT_ESTABLISHED", "CHECK_ELIGIBILITY = NOT RUN / NOT AUTHORIZED",
                     "M-B1 = NOT AUTHORIZED", "FIRST MEMORY = NOT AUTHORIZED", "FRESHNESS=UNKNOWN"):
            self.assertIn(line, self.state)

    def test_subject_to_void_and_revalidation_rules(self):
        self.assertIn("GRANT SUBJECT TO DECISION PACKET §9 (VOID) AND ADR-0015 (REVALIDATE)", self.state)
        for phrase in ("REVALIDATE -/-> B-5 FAILED, unless the controlling record says the grant is void",
                       "any one of its stop conditions **voids** a GRANTED authorization",
                       "means **REVALIDATE, not FAIL**, and does not by itself void the grant",
                       "the matching §9 stop applies and the grant is **VOID**",
                       "the grant may not be relied on until the owner records a determination",
                       "G-1 … G-9", "No universal wall-clock TTL is set",
                       "does not start, extend or substitute for that window"):
            self.assertIn(phrase, self.validity)

    def test_or_state_preserved(self):
        risk = section(self.text, "## 8. Owner risk state", "## 9.")
        for row in ("| OR-1 | REAFFIRMED |", "| OR-2 / DR-3 | REAFFIRMED |",
                    "| cross-environment `osAdminLogin` | REAFFIRMED |", "| OR-3 | REAFFIRMED (bounded) |",
                    "| OR-4 | REAFFIRMED (qualified) |", "| OR-5 | CLOSED |", "| OR-6 | CLOSED |",
                    "| OR-7 | REAFFIRMED |", "| OR-8 | NEW ACKNOWLEDGEMENT ADOPTED |",
                    "| OR-9 | LIMIT / NOTED (not an accepted risk) |"):
            self.assertIn(row, risk)
        risk_flat = flat(risk)
        for residual in ("mapped-package drift can interrupt the future eligibility sequence",
                         "F-2 structured eligibility evidence binding remains unimplemented",
                         "mechanical phone-compromise detection remains unestablished"):
            self.assertIn(residual, risk_flat)

    def test_no_live_action_represented(self):
        for line in ("NO LIVE SYSTEM CONTACTED", "NO DEV, CLOUD, PACKAGE OR RUNTIME MUTATION",
                     "NO REAL K-ROOT / K-WIT / REGISTRY V1 / GENESIS PIN / RECORD 1", "NO REPLICA A / B CHANGE"):
            self.assertIn(line, self.state)
        self.assertIn("No live system was contacted and nothing was executed.", self.flat)

    def test_historical_records_preserved(self):
        withheld = WITHHELD.read_text(encoding="utf-8")
        self.assertIn("B5_OWNER_AUTHORIZATION=WITHHELD", withheld)
        self.assertIn(RECORD.name, withheld)
        packet_state = section(PACKET.read_text(encoding="utf-8"), "## 7. State")
        self.assertIn("B5_PACKET_READY_FOR_SEPARATE_OWNER_DECISION", packet_state)
        self.assertIn(RECORD.name, packet_state)


if __name__ == "__main__":
    unittest.main()
