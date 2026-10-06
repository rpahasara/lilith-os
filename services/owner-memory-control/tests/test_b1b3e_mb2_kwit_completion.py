"""15B2b-B1b-3e: M-B2 / GENERATE_K_WIT completion and owner acceptance (TEST-ONLY).

Record: docs/architecture/slice-15b2b-b1b3e-mb2-kwit-completion.md.

Pins that M-B2 / GENERATE_K_WIT completed and was accepted, the exact K-WIT
public identity, the ordered sequence (DR-5, freeze, KNOWN_EMPTY, preservation,
fresh PR-2, final gates, one-attempt go, one invocation), the execution and
post-step evidence, K_WIT_CUSTODIED with KNOWN_CUSTODY_DEBT, that the deployment
freeze ended at completion, and that M-B3, registry / genesis, record 1, First
Memory and PROD stay unauthorized with FRESHNESS UNKNOWN. It also checks the
K-WIT fingerprint against the canonical burned set in code.
"""

from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
ARCH = ROOT / "docs/architecture"
RECORD = ARCH / "slice-15b2b-b1b3e-mb2-kwit-completion.md"
DECISION = ARCH / "slice-15b2b-b1b3e-mb2-pr2-continuity-owner-decision.md"
PREFLIGHT = ARCH / "slice-15b2b-b1b3e-mb2-kwit-preflight.md"
FINGERPRINT = "5d778701def439b6c896392750c12685c26b67edfc908bed1a80f02eab0d0bdf"
KEY_ID = "test-only.witness.dev-synthetic.b1b3d.1"
BLOB_SHA = "f87593701ee5e9272363a473a115b87cc06179df3c0b233af4aa62bb5b9b97be"
E21 = "cb36daf176d813359b8bd0fe6361f549fd3334a52d0cd1f85cc5247cb26592cf"
KACT_PUBLIC = "dd13a1fb302375a4e7ec81131a72920e23e365e06a0b6dc9bb7ab124dadc01ed"
KACT_BLOB = "6a61c350e848a833868f4573982fca9c75e2af79ccc9bd3716ae0303c26973f3"
CONTROL = "4d16d762f00e43783b9b388b526a969fbffa6772"
CRED_PATH = "/etc/lilith-recovery-witness/credentials/lilith-recovery-witness.witness.cred"

sys.path.insert(0, str(ROOT / "services/owner-memory-control"))
from lilith_owner_memory import burned_identities as BI  # noqa: E402


def section(text: str, start: str, end: str | None = None) -> str:
    body = text.split(start, 1)[1]
    return body.split(end, 1)[0] if end else body


def flat(text: str) -> str:
    return " ".join(re.sub(r"^\s*>", " ", text, flags=re.MULTILINE).split())


class MB2CompletionTests(unittest.TestCase):
    def setUp(self):
        self.text = RECORD.read_text(encoding="utf-8")
        self.state = section(self.text, "## 10. State")
        acceptance = section(self.text, "## 8. Owner acceptance (verbatim)", "## 9.")
        self.acceptance = flat("\n".join(line for line in acceptance.splitlines() if line.startswith(">")))
        go = section(self.text, "## 4. Owner M-B2 go (one attempt)", "## 5.")
        self.go = flat("\n".join(line for line in go.splitlines() if line.startswith(">")))

    def test_completed_and_accepted(self):
        for line in ("M-B2 = COMPLETED / ACCEPTED", "GENERATE_K_WIT = COMPLETED / ACCEPTED",
                     "OWNER ACCEPTANCE RECORDED (VERBATIM)"):
            self.assertIn(line, self.state)
        self.assertTrue(self.acceptance.startswith(
            "I accept M-B2 / GENERATE_K_WIT as successfully completed for the current DEV_SYNTHETIC bootstrap."))
        self.assertIn("This acceptance closes M-B2 / GENERATE_K_WIT for the current DEV_SYNTHETIC bootstrap.",
                      self.acceptance)
        self.assertTrue(self.acceptance.endswith("FRESHNESS=UNKNOWN remains unchanged."))

    def test_exact_kwit_public_identity(self):
        for line in (f"K-WIT publicKeySha256={FINGERPRINT}", f"K-WIT witnessKeyId={KEY_ID}",
                     f"K-WIT blobSha256={BLOB_SHA}"):
            self.assertIn(line, self.state)
        for value in (f"publicKeySha256={FINGERPRINT}", KEY_ID, BLOB_SHA):
            self.assertIn(value, self.acceptance)
        self.assertIn(f"MB2_KWIT_FINGERPRINT publicKeySha256={FINGERPRINT}", self.text)

    def test_custodied_and_custody_debt(self):
        for line in ("K_WIT_CUSTODIED = ESTABLISHED", "KNOWN_CUSTODY_DEBT = RECORDED"):
            self.assertIn(line, self.state)
        self.assertIn("I accept the resulting state as K_WIT_CUSTODIED and the crash-window classification as "
                      "KNOWN_CUSTODY_DEBT.", self.acceptance)

    def test_distinctions_kept(self):
        head = section(self.text, "```text", "```")
        order = ["M-B2 sequence authorized", "fresh DR-5", "deployment freeze", "owner register KNOWN_EMPTY",
                 "K-ACT / host preservation", "fresh PR-2", "final read-only gates", "one-attempt M-B2 go",
                 "one GENERATE_K_WIT invocation", "technical success", "K_WIT_CUSTODIED", "owner acceptance"]
        positions = [head.index(step) for step in order]
        self.assertEqual(positions, sorted(positions))
        for line in ("K_WIT_CUSTODIED != signing authority", "K_WIT_CUSTODIED != registry authority",
                     "M-B2 completion != M-B3 authorization"):
            self.assertIn(line, head)
        for line in ("K_WIT_CUSTODIED != SIGNING AUTHORITY", "K_WIT_CUSTODIED != REGISTRY AUTHORITY",
                     "M-B2 COMPLETION != M-B3 AUTHORIZATION"):
            self.assertIn(line, self.state)

    def test_sequence_order_pr2_last_before_go(self):
        order = ["FRESH DR-5 CURRENT THROUGH 37435321602", "DEPLOYMENT FREEZE ACTIVE FROM FRESH DR-5",
                 "OWNER REGISTER KNOWN_EMPTY", "K-ACT / HOST PRESERVATION PASS BEFORE PR-2",
                 "FRESH PR-2 PASS 2026-10-06T08:59:59Z-2026-10-06T09:04:46Z", "FINAL READ-ONLY GATES PASS",
                 "OWNER M-B2 GO: ONE ATTEMPT, AFTER PR-2 PASS AND FINAL GATES",
                 "EXACTLY ONE INVOCATION OF lilith-authority-keygen-dev witness ON lilith-dev-01 AS ROOT"]
        positions = [self.state.index(step) for step in order]
        self.assertEqual(positions, sorted(positions))
        self.assertIn("SEQUENCE AUTHORIZATION: ONE OWNER-ATTENDED M-B2 PREPARATION SEQUENCE; NOT THE GO", self.state)

    def test_go_binds_template_items(self):
        self.assertTrue(self.go.startswith("I authorize M-B2 / GENERATE_K_WIT now for exactly one attempt within "
                                           "this current DEV_SYNTHETIC M-B2 sequence."))
        for item in ("Scope: DEV_SYNTHETIC only.", CONTROL, "2026-10-06T08:59:59Z–2026-10-06T09:04:46Z, result PASS",
                     f"publicKeySha256={E21}", "lilith-dev-01", "lilith-authority-keygen-dev witness", KEY_ID,
                     CRED_PATH, "exactly one invocation"):
            self.assertIn(item, self.go)

    def test_exactly_one_invocation_no_prompt(self):
        execution = section(self.text, "## 5. Execution (exactly one invocation)", "## 6.")
        for fact in ("| invocations | **exactly one**", "| exit code | **0** |", "| stderr | **0 bytes**",
                     "| stdin | `/dev/null` |", "as root", "the K-ROOT passphrase was not requested or entered"):
            self.assertIn(fact, execution)
        for line in ("STDIN /dev/null; EXIT 0; STDERR 0 BYTES", "NO PROMPT; NO K-ROOT PASSPHRASE REQUESTED OR ENTERED"):
            self.assertIn(line, self.state)
        self.assertIn("KG_RC=0", self.text)
        self.assertIn("KG_STDERR_BYTES=0", self.text)

    def test_distinct_from_kroot_and_kact(self):
        for line in ("K-WIT DISTINCT FROM E-21 K-ROOT", "K-WIT DISTINCT FROM K-ACT", "K-WIT BLOB DISTINCT FROM K-ACT BLOB"):
            self.assertIn(line, self.state)
        self.assertEqual(len({FINGERPRINT, E21, KACT_PUBLIC}), 3)
        self.assertNotEqual(BLOB_SHA, KACT_BLOB)
        self.assertIn(KACT_PUBLIC, self.text)

    def test_fingerprint_not_burned_in_code(self):
        every = BI.BURNED_PUBLIC_KEY_SHA256 | BI.BURNED_REGISTRY_DIGESTS | BI.BURNED_GENESIS_WITNESS_DIGESTS
        self.assertEqual(BI.CANONICAL_COUNT, 20)
        self.assertEqual(len(every), 20)
        self.assertNotIn(FINGERPRINT, every)
        self.assertIn("NOT IN THE CANONICAL 20 BURNED IDENTITIES", self.state)
        self.assertIn("NO BURN; CANONICAL BURNED SET UNCHANGED", self.state)

    def test_public_only_offhost_evidence(self):
        for line in ("PUBLICATION CAPTURED OFF-HOST", "PUBLIC FINGERPRINT RECORDED OFF-HOST; PUBLIC ONLY",
                     "SECRET SCAN 0 HITS", "BLOB HASH / SIZE / PATH / MODE VERIFIED"):
            self.assertIn(line, self.state)

    def test_post_step_p1b2_and_kact_preservation(self):
        for line in ("POST-STEP status --expect P1B-2 PASS", "K-ACT CURRENT UNCHANGED", "SAME BOOT",
                     "BROKER PRESERVATION PASS", "ACTIVATION GRANT_ABSENT",
                     "OBSERVER stableSha256 CHANGED AS EXPECTED (K-WIT EXISTS); NEW VALUE RECORDED"):
            self.assertIn(line, self.state)

    def test_freeze_ended_at_completion(self):
        self.assertIn("DEPLOYMENT FREEZE ENDED AT SEQUENCE COMPLETION (2026-10-06T09:11:38Z)", self.state)

    def test_later_stages_not_authorized(self):
        for line in ("M-B3 / SIGN_REGISTRY_V1 = NOT AUTHORIZED", "REGISTRY / GENESIS = NOT AUTHORIZED",
                     "RECORD 1 = NOT AUTHORIZED", "FIRST MEMORY = NOT AUTHORIZED", "PROD = NOT AUTHORIZED",
                     "FRESHNESS=UNKNOWN"):
            self.assertIn(line, self.state)
        for claim in ("M-B3 / SIGN_REGISTRY_V1 = AUTHORIZED", "REGISTRY / GENESIS = AUTHORIZED",
                      "RECORD 1 = AUTHORIZED", "FIRST MEMORY = AUTHORIZED", "PROD = AUTHORIZED", "FRESHNESS=CURRENT",
                      "SIGNING AUTHORITY = GRANTED", "K-WIT MAY SIGN"):
            self.assertNotIn(claim, self.text)

    def test_pointers_on_decision_and_preflight(self):
        for path in (DECISION, PREFLIGHT):
            text = path.read_text(encoding="utf-8")
            self.assertIn("slice-15b2b-b1b3e-mb2-kwit-completion.md", text)
            self.assertIn("M-B2 / `GENERATE_K_WIT` COMPLETED / ACCEPTED", text)

    def test_no_private_paths(self):
        self.assertNotRegex(self.text, r"[A-Za-z]:\\Users\\|/root/|/home/|/data/data/")


if __name__ == "__main__":
    unittest.main()
