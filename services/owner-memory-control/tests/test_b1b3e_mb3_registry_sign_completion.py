"""15B2b-B1b-3e: M-B3 / SIGN_REGISTRY_V1 completion and owner acceptance, attempt 2 (TEST-ONLY).

Record: docs/architecture/slice-15b2b-b1b3e-mb3-registry-sign-completion.md.

Pins that M-B3 completed and was accepted at attempt 2, the exact accepted
Registry V1 identifiers, exactly one verified SIGN with no burn, the attempt-1
history (closed, unsigned, not burned, not reusable, disposition completed),
the evidence-recording-gap classification, the non-retroactive K-ROOT forward
baseline, and that the signed registry is neither installed nor effective while
M-B4/M-B5, genesis, record 1, First Memory and PROD stay unauthorized with
FRESHNESS UNKNOWN. It also checks the accepted digests against the canonical
burned set in code.
"""

from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
ARCH = ROOT / "docs/architecture"
RECORD = ARCH / "slice-15b2b-b1b3e-mb3-registry-sign-completion.md"
LEDGER = ARCH / "current-architecture-acceptance-ledger-v0.1.md"
DIGEST = "fa66272131a3ef076036616b07766a377de4fdc1e4fef4cb8a054726f05c14fc"
SIGNED_SHA = "3f0a59c0a104934730184d28bc16e1c9215bdaa6ec1f9d94753722862f486156"
EXPORT_SHA = "c4ea3d66fdef3f6b30c63a1f7f4903a3d2d5427f0419c6e1bd7aadd12c9564d8"
MANIFEST_SHA = "9ce94816a28cac159b768f998d072c829b4a7fdd36d1dba3b88c2e57572aa319"
READBACK_SHA = "eda0d4099365df740534b7c1e40a8755661fb7d2a6830d1251e1b3335d2382cf"
EPOCH_RANDOM = "11f184889f333dece054f3b91a301632"
ISSUED_AT = "2026-10-06T15:16:21Z"
E21 = "cb36daf176d813359b8bd0fe6361f549fd3334a52d0cd1f85cc5247cb26592cf"
KACT = "dd13a1fb302375a4e7ec81131a72920e23e365e06a0b6dc9bb7ab124dadc01ed"
KWIT = "5d778701def439b6c896392750c12685c26b67edfc908bed1a80f02eab0d0bdf"
ATTEMPT1 = "b7e24530a21757a5bef996ec9adb13ed5932ab04edb1943321f529e3206c0e53"
CONTROL = "ea74e1b36ee36c372b434be38d1eae34e5a1bb78"
SOURCE = "f9fb9e14dc6a14ac796379938d3092f6214194cb"
BUNDLE = "ad37758ebf892e773a7019cb2c084d4d30920e34fb5318ba9f82999f48ffa736"
SCRIPT = "b58b93215dc5c1e724846c7fc16acc2c29d81725a2ba13badcdccfd7b9eaecc7"
KACT_PUBLICATION = "d76479762007afef828f3901591647dc4a2fb2205f4afac527b66d2cc9c6b032"
POINTED = ("slice-15b2b-b1b3e-mb3-signing-continuity-owner-decision.md", "slice-15b2b-b1b3e-mb3-sign-attempt1-incident.md",
           "slice-15b2b-b1b3e-mb3-replacement-final-package-pins.md",
           "slice-15b2b-b1b3e-mb3-attempt1-disposition-completion.md", "README.md")

sys.path.insert(0, str(ROOT / "services/owner-memory-control"))
from lilith_owner_memory import burned_identities as BI  # noqa: E402


def section(text: str, start: str, end: str | None = None) -> str:
    body = text.split(start, 1)[1]
    return body.split(end, 1)[0] if end else body


def flat(text: str) -> str:
    return " ".join(re.sub(r"^\s*>", " ", text, flags=re.MULTILINE).split())


class MB3CompletionTests(unittest.TestCase):
    def setUp(self):
        self.text = RECORD.read_text(encoding="utf-8")
        self.state = section(self.text, "## 11. State")
        acceptance = section(self.text, "## 9. Owner acceptance (verbatim excerpt)", "## 10.")
        self.acceptance = flat("\n".join(line for line in acceptance.splitlines() if line.startswith(">")))

    def test_completed_and_accepted(self):
        for line in ("M-B3 / SIGN_REGISTRY_V1 = COMPLETED / ACCEPTED (ATTEMPT 2)", "REGISTRY_V1 = SIGNED / OWNER-ACCEPTED",
                     "TECHNICAL_STATE = REGISTRY_SIGNED", "OUTCOME = B_SIGNED_PENDING_OWNER_ACCEPTANCE -> OWNER-ACCEPTED"):
            self.assertIn(line, self.state)
        self.assertTrue(self.acceptance.startswith(
            "I accept the independently verified M-B3 attempt-2 SIGN_REGISTRY_V1 result."))
        for line in ("M-B3 / SIGN_REGISTRY_V1 = COMPLETED / ACCEPTED", "REGISTRY_V1 = SIGNED / OWNER-ACCEPTED",
                     "This acceptance applies ONLY to the exact signed Registry V1 identified by the hashes above.",
                     "It does NOT authorize modification, substitution or regeneration of that Registry V1."):
            self.assertIn(line, self.acceptance)

    def test_exact_registry_identifiers(self):
        for line in (f"REGISTRY_V1_DIGEST = {DIGEST}", f"SIGNED_REGISTRY_SHA256 = {SIGNED_SHA}",
                     f"EXPORT_SHA256 = {EXPORT_SHA}", f"MANIFEST_SHA256 = {MANIFEST_SHA}",
                     f"PREPARE_READBACK_SHA256 = {READBACK_SHA}", f"EPOCH_RANDOM = {EPOCH_RANDOM}",
                     f"ISSUED_AT = {ISSUED_AT}", "POLICY_VERSION = policy.dev-synthetic.v1",
                     "ROOT_KEY_ID = test-only.registry-root.dev-synthetic.b1b3d.1"):
            self.assertIn(line, self.state)
        identities = section(self.text, "## 1. Identities", "## 2.")
        for value in (CONTROL, SOURCE, BUNDLE, SCRIPT, KACT_PUBLICATION, E21, KACT, KWIT, DIGEST, SIGNED_SHA,
                      EXPORT_SHA, MANIFEST_SHA, READBACK_SHA):
            self.assertIn(value, identities)
        for value in (DIGEST, SIGNED_SHA, EXPORT_SHA, MANIFEST_SHA, READBACK_SHA, E21, KACT, KWIT, ATTEMPT1):
            self.assertEqual(len(value), 64)
        self.assertEqual(len(EPOCH_RANDOM), 32)

    def test_exactly_one_verified_sign(self):
        for line in ("PREPARE INVOCATIONS = 1", "EXACTLY ONE ATTEMPT-2 SIGN INVOCATION; SIGNER EXIT 0; SIGNER STDERR EMPTY",
                     "SIGNATURE COUNT = 1", "SIGNATURE VERIFIED UNDER E-21 (S25, REVIEWED LAPTOP VERIFIER, INDEPENDENT ED25519)",
                     "MB3_LAPTOP_VERIFIED", "OWNER_TOOL_RECONSTRUCTION_EQUAL", "NO CANDIDATE SUBSTITUTION"):
            self.assertIn(line, self.state)
        sign = section(self.text, "## 7. SIGN (exactly one invocation)", "## 8.")
        for fact in ("| invocations | **exactly one**; no retry |", "| signer exit | **0**; signer stderr **empty** |",
                     "KROOT_SIGNATURE_VERIFIED", "| burn | **none** |"):
            self.assertIn(fact, sign)

    def test_keys_distinct_and_kwit_absent(self):
        self.assertEqual(len({E21, KACT, KWIT}), 3)
        for line in ("(SOLE CURRENT KEY)", "(NOT IN REGISTRY V1)", "K-ROOT, K-ACT, K-WIT DISTINCT"):
            self.assertIn(line, self.state)

    def test_no_burn_in_code(self):
        every = BI.BURNED_PUBLIC_KEY_SHA256 | BI.BURNED_REGISTRY_DIGESTS | BI.BURNED_GENESIS_WITNESS_DIGESTS
        self.assertEqual(BI.CANONICAL_COUNT, 20)
        self.assertEqual(len(every), 20)
        for value in (DIGEST, ATTEMPT1, E21, KACT, KWIT):
            self.assertNotIn(value, every)
        self.assertIn("BURN = NONE", self.state)

    def test_attempt1_history(self):
        for line in ("ATTEMPT 1 = CLOSED / INCIDENT / A_NO_SIGNATURE",
                     f"ATTEMPT-1 CANDIDATE {ATTEMPT1} = HISTORICAL_ABANDONED_UNSIGNED_CANDIDATE; NOT BURNED; NOT REUSABLE",
                     "ATTEMPT-1 PHONE DISPOSITION = COMPLETED / ACCEPTED"):
            self.assertIn(line, self.state)
        self.assertNotEqual(DIGEST, ATTEMPT1)

    def test_evidence_recording_gap_not_overstated(self):
        self.assertIn("P1/P3 ORIGINAL OUTPUT = EVIDENCE-RECORDING GAP; NOT A PROTOCOL DEVIATION", self.state)
        gap = flat(section(self.text, "## 6. PREPARE", "## 7."))
        self.assertIn("**EVIDENCE-RECORDING GAP, NOT a protocol deviation**", gap)
        self.assertIn("It is **not** a capture of the original P1 / P3 values", gap)
        self.assertIn("**before** the single attempt-2 PREPARE (311)", gap)
        self.assertIn("The earlier P1/P3 evidence issue is accepted as an EVIDENCE-RECORDING GAP, not a protocol deviation.",
                      self.acceptance)

    def test_kroot_forward_baseline_not_retroactive(self):
        for line in ("KROOT_FORWARD_BASELINE = 0700 / only k-root.der / 0600 / 166 / 1791270756",
                     "KROOT FORWARD BASELINE IS NOT RETROACTIVE TO M-B1"):
            self.assertIn(line, self.state)
        baseline = flat(section(self.text, "## 5. K-ROOT forward custody baseline", "## 6."))
        self.assertIn("This **does not** retroactively prove the metadata unchanged since M-B1.", baseline)
        self.assertIn("**NOT ESTABLISHED**", baseline)

    def test_signed_but_not_installed_or_effective(self):
        for line in ("REGISTRY_EFFECTIVE = NO", "TRUST_INSTALLED = NO", "AUTHORITY ACTIVE = NO"):
            self.assertIn(line, self.state)
        head = section(self.text, "```text", "```")
        for line in ("REGISTRY_SIGNED + owner acceptance != registry installed != registry effective",
                     "M-B3 completion != M-B4/M-B5 authorization",
                     "forward K-ROOT baseline != retroactive continuity proof"):
            self.assertIn(line, head)
        for item in ("registry installed", "registry effective", "trust installed", "authority active"):
            self.assertIn(item, self.acceptance)

    def test_later_stages_not_authorized(self):
        for line in ("M-B4/M-B5 = NOT AUTHORIZED", "INSTALL_TRUST_AND_REGISTRY = NOT AUTHORIZED",
                     "GENESIS = NOT AUTHORIZED", "RECORD 1 = NOT AUTHORIZED", "FIRST MEMORY = NOT AUTHORIZED",
                     "PROD = NOT AUTHORIZED", "FRESHNESS=UNKNOWN"):
            self.assertIn(line, self.state)
        for claim in ("M-B4/M-B5 = AUTHORIZED", "INSTALL_TRUST_AND_REGISTRY = AUTHORIZED", "GENESIS = AUTHORIZED",
                      "RECORD 1 = AUTHORIZED", "FIRST MEMORY = AUTHORIZED", "PROD = AUTHORIZED", "FRESHNESS=CURRENT",
                      "REGISTRY_EFFECTIVE = YES", "TRUST_INSTALLED = YES"):
            self.assertNotIn(claim, self.text)

    def test_pointers_ledger_and_index(self):
        for name in POINTED:
            text = (ARCH / name).read_text(encoding="utf-8")
            self.assertIn("(slice-15b2b-b1b3e-mb3-registry-sign-completion.md)", text, name)
        ledger = LEDGER.read_text(encoding="utf-8")
        self.assertIn("### 13.1z Current-state reconciliation (M-B3 / SIGN_REGISTRY_V1 completion and owner acceptance",
                      ledger)
        auth02 = next(line for line in ledger.splitlines() if line.startswith("| AUTH-02 |"))
        self.assertIn("(§13.1z)", auth02)                       # later passes append after it (§13.1aa …)
        self.assertTrue(auth02.endswith("| UNASSIGNED |"))
        for name in POINTED[:4]:
            if name.endswith("-completion.md") or name.endswith("-pins.md"):
                self.assertNotIn("REGISTRY_SIGNED = REACHED", (ARCH / name).read_text(encoding="utf-8"))

    def test_no_private_paths(self):
        self.assertNotRegex(self.text, r"[A-Za-z]:\\Users\\|/root/|/home/|/data/data/")
        self.assertNotRegex(self.text, r"%USERPROFILE%|lilith-mb3r-a2")


if __name__ == "__main__":
    unittest.main()
