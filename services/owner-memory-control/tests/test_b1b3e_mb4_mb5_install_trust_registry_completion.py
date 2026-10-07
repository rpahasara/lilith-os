"""15B2b-B1b-3e: M-B4/M-B5 INSTALL_TRUST_AND_REGISTRY completion and owner acceptance, Sequence 2 (TEST-ONLY).

Record: docs/architecture/slice-15b2b-b1b3e-mb4-mb5-install-trust-registry-completion.md.

Pins that INSTALL_TRUST_AND_REGISTRY completed and was accepted; that M-B4 and
M-B5 each ran exactly once with one consumed go; the installed identities
(equal to the operator's and the verifier's accepted pins in code); that the
first M-B4 POST anomaly is preserved and was resolved by one read-only
re-classification, not a retry; the K-1 classification as sequence-only; the
verbatim §12.3 acceptance (equal to the package template); the cleanup; the
K-WIT option closed; Sequence 1 historical; that trust is installed while the
registry is not effective and no authority is active; and that M-B6, genesis,
record 1, First Memory and PROD stay unauthorized with FRESHNESS UNKNOWN.
Stdlib only.
"""

from __future__ import annotations

import hashlib
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
ARCH = ROOT / "docs/architecture"
RECORD = ARCH / "slice-15b2b-b1b3e-mb4-mb5-install-trust-registry-completion.md"
PACKAGE = ARCH / "slice-15b2b-b1b3e-mb4-mb5-ceremony-package.md"
LEDGER = ARCH / "current-architecture-acceptance-ledger-v0.1.md"
TOOLS = ROOT / "services/owner-memory-control/tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import mb4_mb5_operator as O  # noqa: E402

CONTROL = "82b89a32f619ed3e41f0f4d1c642bf5187c74710"
ROOT_ANCHOR = "bc5f00a76b518c4f11b6804d35844c036db75eaa730d56c35f97f430558ff687"
WITNESS_ANCHOR = "be360da2324880d725aea509bb0f41500f51ecfc3c2995dd3057824bb471ab5a"
REGISTRY = "46b0bfc558ec3a19467206ada3dc53c18e8a6a4cd0782711b4800cfe099f8b1e"
DIGEST = "fa66272131a3ef076036616b07766a377de4fdc1e4fef4cb8a054726f05c14fc"
E21 = "cb36daf176d813359b8bd0fe6361f549fd3334a52d0cd1f85cc5247cb26592cf"
KWIT = "5d778701def439b6c896392750c12685c26b67edfc908bed1a80f02eab0d0bdf"
OPERATOR = "e380ab1852ba72fe511c650446867c8d229d95776af3c1d4266fa949c0a9de1a"
MB4_GO = "f7b1bab66cbf83c10d27cc1fe960bbd7f11c3049ba644e2d7c7b354cf668c10a"
MB5_GO = "d0441a5abae0bb8054c9a74b78c0f8bb0f5ddfe91a562948b96c3e85a9cc0513"
POINTED = ("slice-15b2b-b1b3e-mb4-mb5-ceremony-package.md", "slice-15b2b-b1b3e-mb4-mb5-continuity-owner-decision.md",
           "slice-15b2b-b1b3e-mb4-mb5-prep-seq1-operator-loader-incident.md",
           "slice-15b2b-b1b3e-mb4-mb5-trust-install-remediation.md",
           "slice-15b2b-b1b3e-mb4-mb5-installable-representation-owner-decision.md",
           "slice-15b2b-b1b3e-mb3-registry-sign-completion.md", "README.md")


def section(text: str, start: str, end: str | None = None) -> str:
    body = text.split(start, 1)[1]
    return body.split(end, 1)[0] if end else body


def flat(text: str) -> str:
    return " ".join(re.sub(r"^\s*>", " ", text, flags=re.MULTILINE).split())


class MB4MB5CompletionTests(unittest.TestCase):
    def setUp(self):
        self.text = RECORD.read_text(encoding="utf-8")
        self.state = section(self.text, "## 12. State")

    def test_completed_and_accepted(self):
        for line in ("INSTALL_TRUST_AND_REGISTRY = COMPLETED / ACCEPTED", "M-B4 = COMPLETED / ACCEPTED",
                     "M-B4 INSTALLER = PASS / P1B-4", "W3 = W3_ANCHORS_INSTALLED_REGISTRY_ABSENT / CONFIRMED",
                     "M-B5 = COMPLETED / ACCEPTED", "M-B5 INSTALLER = PASS / P1B-5", "M-B5 POST = PASS",
                     "W5 = W5_INSTALLED_CONTENT_VERIFIED / CONFIRMED",
                     "DENIAL PROOF = PASS / PHASE P1B-5 (92 DENIED, 0 ALLOWED, 0 FAIL)",
                     "MB4_MB5_PREPARATION_SEQUENCE_2 = COMPLETE", "STAGING = CLEANED (STAGE_DIR_ABSENT)",
                     "DEPLOYMENT_FREEZE = ENDED"):
            self.assertIn(line, self.state)
        self.assertIn(CONTROL, section(self.text, "## 1. Identities", "## 2."))

    def test_each_installer_ran_exactly_once(self):
        self.assertIn("M-B4 GO = CONSUMED EXACTLY ONCE; INSTALL-ANCHORS INVOCATIONS = 1; NO RETRY", self.state)
        self.assertIn("M-B5 GO = CONSUMED EXACTLY ONCE; INSTALL-REGISTRY INVOCATIONS = 1", self.state)
        mb4 = section(self.text, "## 5. M-B4 (exactly one invocation)", "## 6.")
        mb5 = section(self.text, "## 8. M-B5 (exactly one invocation)", "## 9.")
        for body, go, marker in ((mb4, "12", "07:00:19Z"), (mb5, "11", "07:27:34Z")):
            self.assertIn("| invocations | **exactly one**", body)
            self.assertIn(f"all {go} binding lines present", body)
            self.assertIn(marker, body)
        self.assertEqual(len(O.MB4_GO_LINES), 12)
        self.assertEqual(len(O.MB5_GO_LINES), 11)
        identities = section(self.text, "## 1. Identities", "## 2.")
        for value in (MB4_GO, MB5_GO, OPERATOR):
            self.assertIn(value, identities)

    def test_installed_identities_equal_the_accepted_pins(self):
        self.assertEqual(O.DERIVED, {"registry-root.json": ROOT_ANCHOR, "witness-anchor.json": WITNESS_ANCHOR,
                                     "authority-registry.v1.json": REGISTRY})
        self.assertEqual((O.REGISTRY_DIGEST, O.E21, O.KWIT), (DIGEST, E21, KWIT))
        for line in (f"INSTALLED registry-root.json = {ROOT_ANCHOR}", f"INSTALLED witness-anchor.json = {WITNESS_ANCHOR}",
                     f"INSTALLED authority-registry.v1.json = {REGISTRY}", f"REGISTRY_V1_DIGEST = {DIGEST}",
                     f"E-21 publicKeySha256={E21}", f"K-WIT publicKeySha256={KWIT}"):
            self.assertIn(line, self.state)
        self.assertEqual(hashlib.sha256((TOOLS / "mb4_mb5_operator.py").read_bytes()).hexdigest(), OPERATOR)

    def test_post_anomaly_preserved_and_not_a_retry(self):
        self.assertIn("M-B4 POST = PASS (FIRST POST NOT_PASS: LOCAL CUSTODY CLIENT EXIT 3221225477 / 0xC0000005; "
                      "ONE READ-ONLY RE-CLASSIFICATION MB4_MB5_HOST_W3_PASS, ALL CODES 0)", self.state)
        incident = flat(section(self.text, "## 6. M-B4 POST incident", "## 7."))
        for phrase in ("`MB4_MB5_HOST_W3_NOT_PASS`", "`3221225477`", "`0xC0000005`", "**No mutation was retried.**",
                       "It did not authorize another M-B4 attempt.", "All seven sub-read exit codes were 0, including custody",
                       "**Result: M-B4 POST = PASS; W3 CONFIRMED.**"):
            self.assertIn(phrase, incident)
        head = section(self.text, "```text", "```")
        self.assertIn("a read-only re-classification after a STOP != a retry of the mutation", head)

    def test_k1_classification_is_sequence_only(self):
        self.assertIn("K1_TO_K8 = PASS (K-1 OWNER CLASSIFICATION: ATTENDED_OWNER_ADJUDICATION_WITHOUT_CONTINUITY_BREAK; "
                      "THIS SEQUENCE ONLY)", self.state)
        k = flat(section(self.text, "## 7. Inter-stage continuity", "## 8."))
        self.assertIn("It does **not** establish that arbitrary STOPs or pauses preserve continuity.", k)
        self.assertIn("**K-1 … K-8 PASS.**", k)

    def test_w5_post_facts(self):
        post = section(self.text, "**POST (`host … W5`", "## 9.")
        for row in ("| `status --expect P1B-5` | PASS |",
                    "| `anchorsEqualOwnerCopies` / `witnessAnchorNamesKWit` / `registryVerifiesOnHost` | true / true / true |",
                    "| `trustInstalledCandidate` / `registryEffective` / `authorityGranted` | true / false / false |",
                    f"| `registryDigest` | `{DIGEST}` |",
                    "| `hostInputReasons` | exactly `AUTHORIZATION_REGISTER_COPY_MISSING`, `GENESIS_PIN_COPY_MISSING` |"):
            self.assertIn(row, post)

    def test_acceptance_is_the_package_template(self):
        quoted = [line[2:] for line in section(self.text, "## 9. Owner acceptance", "## 10.").splitlines()
                  if line.startswith("> ")]
        template = [line[2:].replace("`", "") for line in
                    section(PACKAGE.read_text(encoding="utf-8"), "**12.3 Acceptance after W5", "**12.4").splitlines()
                    if line.startswith("> ")]
        self.assertEqual(quoted, template)
        self.assertEqual(len(quoted), 3)

    def test_trust_installed_but_not_effective_or_active(self):
        for line in ("TRUST_INSTALLED = YES (TECHNICAL, OWNER-ACCEPTED)", "REGISTRY_INSTALLED = YES",
                     "REGISTRY_EFFECTIVE = NO", "AUTHORITY_ACTIVE = NO", "K-WIT_BURN_REGENERATE_OPTION = CLOSED"):
            self.assertIn(line, self.state)
        for claim in ("REGISTRY_EFFECTIVE = YES", "AUTHORITY_ACTIVE = YES", "AUTHORITY ACTIVE = YES"):
            self.assertNotIn(claim, self.text)
        head = section(self.text, "```text", "```")
        self.assertIn("trust installed + registry installed != registry effective != authority active", head)

    def test_later_stages_not_authorized(self):
        for line in ("M-B6 = NOT AUTHORIZED", "GENESIS = NOT AUTHORIZED", "RECORD_1 = NOT AUTHORIZED",
                     "FIRST_MEMORY = NOT AUTHORIZED", "PROD = NOT AUTHORIZED", "FRESHNESS=UNKNOWN"):
            self.assertIn(line, self.state)
        for claim in ("M-B6 = AUTHORIZED", "GENESIS = AUTHORIZED", "RECORD_1 = AUTHORIZED", "FIRST_MEMORY = AUTHORIZED",
                      "PROD = AUTHORIZED", "FRESHNESS=CURRENT", "FRESHNESS = CURRENT"):
            self.assertNotIn(claim, self.text)

    def test_sequence1_historical_and_cleanup(self):
        self.assertIn("MB4_MB5_PREPARATION_SEQUENCE_1 = ENDED / HISTORICAL / NON-REUSABLE", self.state)
        self.assertIn("Nothing from Sequence 1 was replayed in Sequence 2.", self.text)
        cleanup = flat(section(self.text, "## 10. Staging cleanup", "## 11."))
        for phrase in ("`MB4_MB5_STAGED_FILES_PINNED_ON_HOST`", "**without `sudo`**", "`STAGE_DIR_ABSENT`",
                       "`status --expect P1B-5` PASS", "**The deployment freeze ended at 07:34:02Z**, only after cleanup."):
            self.assertIn(phrase, cleanup)

    def test_pointers_ledger_and_index(self):
        for name in POINTED:
            text = (ARCH / name).read_text(encoding="utf-8")
            self.assertIn("(slice-15b2b-b1b3e-mb4-mb5-install-trust-registry-completion.md)", text, name)
        ledger = LEDGER.read_text(encoding="utf-8")
        self.assertIn("### 13.1ad Current-state reconciliation (M-B4/M-B5 INSTALL_TRUST_AND_REGISTRY completed", ledger)
        auth02 = next(line for line in ledger.splitlines() if line.startswith("| AUTH-02 |"))
        self.assertIn("(§13.1ad)", auth02)                      # later passes append after it
        self.assertTrue(auth02.endswith("| UNASSIGNED |"))

    def test_no_private_paths(self):
        self.assertNotRegex(self.text, r"[A-Za-z]:\\Users\\|/root/|/data/data/|%USERPROFILE%")
        self.assertNotIn("lilith-mb4-mb5-prep-seq", self.text)


if __name__ == "__main__":
    unittest.main()
