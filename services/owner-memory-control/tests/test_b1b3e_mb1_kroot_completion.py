"""15B2b-B1b-3e: M-B1 / GENERATE_K_ROOT completion and owner acceptance (TEST-ONLY).

Record: docs/architecture/slice-15b2b-b1b3e-mb1-kroot-completion.md.

Pins that M-B1 / GENERATE_K_ROOT completed and was accepted, the exact E-21
fingerprint, the single-call eligibility prerequisite and the one-attempt go, the
execution and export evidence, that the deployment freeze ended at completion,
and that K-WIT (with its fresh PR-2), registry / genesis, record 1 and First
Memory stay unauthorized with FRESHNESS UNKNOWN. It also checks the E-21
fingerprint against the canonical burned set in code.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
RECORD = ROOT / "docs/architecture/slice-15b2b-b1b3e-mb1-kroot-completion.md"
FINGERPRINT = "cb36daf176d813359b8bd0fe6361f549fd3334a52d0cd1f85cc5247cb26592cf"
SCRIPT_SHA = "09cbc9bee7b58af7bab45bb903c6e10cb51ae6c62b20705be12de274bbe5216b"
BUNDLE_SHA = "7f07e158aa5a0b3c31ee63e25ae25116c92f26a402bc6924422d7c95e2edc2c1"

sys.path.insert(0, str(ROOT / "services/owner-memory-control"))
from lilith_owner_memory import burned_identities as BI  # noqa: E402


def section(text: str, start: str, end: str | None = None) -> str:
    body = text.split(start, 1)[1]
    return body.split(end, 1)[0] if end else body


def flat(text: str) -> str:
    return " ".join(text.replace(">", " ").split())


class MB1CompletionTests(unittest.TestCase):
    def setUp(self):
        self.text = RECORD.read_text(encoding="utf-8")
        self.state = section(self.text, "## 9. State")

    def test_completed_and_accepted(self):
        for line in ("M-B1 = COMPLETED / ACCEPTED", "GENERATE_K_ROOT = COMPLETED / ACCEPTED",
                     "OWNER ACCEPTANCE RECORDED (VERBATIM)"):
            self.assertIn(line, self.state)
        acceptance = flat(section(self.text, "## 7. Owner acceptance (verbatim)", "## 8."))
        self.assertTrue(acceptance.startswith(
            "I accept M-B1 as successfully completed for the current DEV_SYNTHETIC bootstrap."))
        self.assertIn("This acceptance closes M-B1 / GENERATE_K_ROOT for this DEV_SYNTHETIC bootstrap.", acceptance)
        self.assertIn("FRESHNESS=UNKNOWN remains unchanged.", acceptance)

    def test_exact_e21_fingerprint(self):
        self.assertIn(f"E-21 publicKeySha256={FINGERPRINT}", self.state)
        acceptance = flat(section(self.text, "## 7. Owner acceptance (verbatim)", "## 8."))
        self.assertIn(f"publicKeySha256={FINGERPRINT}", acceptance)
        self.assertIn(f"MB1_KROOT_FINGERPRINT publicKeySha256={FINGERPRINT}", self.text)

    def test_eligibility_prerequisite_and_one_attempt_go(self):
        self.assertIn("ELIGIBILITY PREREQUISITE: CHECK_ELIGIBILITY CALLED EXACTLY ONCE IN THIS SEQUENCE -> "
                      "PR1B_ELIGIBLE", self.state)
        self.assertIn("OWNER M-B1 GO: ONE ATTEMPT, AFTER PR1B_ELIGIBLE, NAMING BOTH PINS", self.state)
        go = flat(section(self.text, "## 3. Owner M-B1 go (one attempt)", "## 4."))
        self.assertIn("I authorize M-B1 now for exactly one attempt within this current DEV_SYNTHETIC continuous "
                      "sequence.", go)
        self.assertIn(SCRIPT_SHA, go)
        self.assertIn(BUNDLE_SHA, go)
        prereq = section(self.text, "## 2. Prerequisites and eligibility", "## 3.")
        self.assertIn("**called exactly once** at `06:57:37Z`: `PR1B_ELIGIBLE`, `reasons = []`, all 12 inputs `True`",
                      prereq)

    def test_execution_evidence(self):
        for line in ("RUN_EXIT=0", "STOP LINES = 0", "MB1_KROOT_GENERATED",
                     "PUBLIC EXPORT VERIFIED (EXACT 14-FILE ALLOWLIST)", "NOT IN THE CANONICAL 20 BURNED IDENTITIES",
                     "REPLICA B PRESERVED", "TRANSPORT COPY REMOVED", "PRIVATE K-ROOT REMAINED S25-ONLY"):
            self.assertIn(line, self.state)
        self.assertIn("740cf10ab9042b95eef192af6ca9e63b661cf91af3a36fe5d0aafbd2b3547db5", self.text)

    def test_fingerprint_not_burned_in_code(self):
        every = BI.BURNED_PUBLIC_KEY_SHA256 | BI.BURNED_REGISTRY_DIGESTS | BI.BURNED_GENESIS_WITNESS_DIGESTS
        self.assertEqual(BI.CANONICAL_COUNT, 20)
        self.assertEqual(len(every), 20)
        self.assertNotIn(FINGERPRINT, every)

    def test_freeze_ended_at_completion(self):
        self.assertIn("DEPLOYMENT FREEZE ENDED AT SEQUENCE COMPLETION (2026-10-06T07:21:35Z)", self.state)

    def test_kwit_and_later_not_authorized(self):
        for line in ("GENERATE_K_WIT / M-B2 = NOT AUTHORIZED",
                     "FRESH PR-2 IMMEDIATELY BEFORE GENERATE_K_WIT REMAINS MANDATORY; M-B1 COMPLETION CANNOT "
                     "SUBSTITUTE FOR IT",
                     "M-B1 COMPLETION DOES NOT AUTHORIZE M-B2 OR LATER STAGES", "REGISTRY / GENESIS = NOT AUTHORIZED",
                     "RECORD 1 = NOT AUTHORIZED", "FIRST MEMORY = NOT AUTHORIZED", "FRESHNESS=UNKNOWN"):
            self.assertIn(line, self.state)
        for claim in ("GENERATE_K_WIT / M-B2 = AUTHORIZED", "KWIT = AUTHORIZED", "FIRST MEMORY = AUTHORIZED",
                      "FRESHNESS=CURRENT", "RECORD 1 = AUTHORIZED"):
            self.assertNotIn(claim, self.text)

    def test_no_private_paths(self):
        self.assertNotRegex(self.text, r"[A-Za-z]:\\Users\\|/root/|/home/|/data/data/")


if __name__ == "__main__":
    unittest.main()
