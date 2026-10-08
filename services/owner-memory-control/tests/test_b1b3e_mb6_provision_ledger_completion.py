"""15B2b-B1b-3e: M-B6 PROVISION_LEDGER completion and owner acceptance (TEST-ONLY, stdlib).

Record: docs/architecture/slice-15b2b-b1b3e-mb6-provision-ledger-completion.md.

Pins: M-B6 completed and was owner-accepted after exactly one `provision 1` with one consumed go; the
accepted ledger identities (equal to the owner-accepted head and the code's pins); the verbatim §12 acceptance
(equal to the package template with only its four placeholders filled); the append-only 27-line P1B-6 erratum
(original "28" text preserved, live transcript = the tested fixture); the DR-5 target still NOT accepted; and
that M-B7 and every later stage, First Memory and PROD stay unauthorized, with the First Memory boundary.
"""

from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
ARCH = ROOT / "docs/architecture"
RECORD = ARCH / "slice-15b2b-b1b3e-mb6-provision-ledger-completion.md"
PACKAGE = ARCH / "slice-15b2b-b1b3e-mb6-ceremony-package.md"
REMEDIATION = ARCH / "slice-15b2b-b1b3e-mb6-ledger-remediation.md"
HEAD_RECORD = ARCH / "slice-15b2b-b1b3e-mb6-owner-ledger-head-acceptance.md"
LEDGER = ARCH / "current-architecture-acceptance-ledger-v0.1.md"
TOOLS = ROOT / "services/owner-memory-control/tools"
TESTS = ROOT / "services/owner-memory-control/tests"
for path in (TOOLS, TESTS):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import mb6_dr5_target as T  # noqa: E402
import mb6_ledger_verifier as V  # noqa: E402
import mb6_operator as O  # noqa: E402

CONTROL = "5752bc8e2ee267ae47db04b37c50cbdfa3a0a361"
HEAD = "19bf9091a96cdc2378a68508feb0c119721f7fcef7b9c3a480a6cd6b72fa1630"
OP_JCS_SHA = "8e3bdbdf3f3730de5ad031d36eb390888fc6e0f65307d947522b0138ffcd7b60"
SCHEMA = "65127a68c61d4dba390e01c61d01a76fdc54e830c374cb05069b0ab0c50d9cb7"
VALUES = {"<CONTROL>": CONTROL,
          "<MARKER_SHA256>": "75e7307983b3b14150856ad6a953ba9eeaffa2d2e816a4cccaf9980362417f87",
          "<POST_SHA256>": "733377bc62fc908aa8a46d2df05ba59078bb68e2ec9f2b8830706d06048bf93b",
          "<P1B6_SHA256>": "f8722cb7e2cb2ee91b73e4722715ee790c6eb564692ad5cf4d3de38094b92e2b"}
FORBIDDEN_CLAIMS = ("M-B7 = AUTHORIZED", "M-B8 = AUTHORIZED", "REGISTRY_EFFECTIVE = YES", "AUTHORITY_ACTIVE = YES",
                    "POST_MB6_DR5_TARGET_ACCEPTED = YES", "FIRST_MEMORY = AUTHORIZED", "FRESHNESS=CURRENT",
                    "WITNESS GENESIS = AUTHORIZED", "RECORD_1 = AUTHORIZED", "PROD = AUTHORIZED")


def flat(text: str) -> str:
    return " ".join(re.sub(r"^\s*>", " ", text, flags=re.MULTILINE).split())


def section(text: str, start: str, end: str) -> str:
    return text.split(start, 1)[1].split(end, 1)[0]


class Mb6CompletionRecordTests(unittest.TestCase):
    def setUp(self):
        self.text = RECORD.read_text(encoding="utf-8")
        self.state = self.text.split("## 11. State", 1)[1]

    def test_state(self):
        for line in ("M-B6 = COMPLETED / OWNER-ACCEPTED", "M-B6 GO = CONSUMED", "PROVISION INVOCATIONS = EXACTLY ONE",
                     "CLI RESULT = CLI_SUCCESS_EXACT", "POST PHASE BEFORE ACCEPTANCE = W6_6_POST_VERIFIED_ACCEPTANCE_PENDING",
                     "LEDGER_PROVISIONED = OWNER-ACCEPTED", "LEDGER SEQUENCE = 1", f"LEDGER HEAD = {HEAD}",
                     "P1B-6 = PASS (20 DENIED, 0 ALLOWED; 27-line transcript)", "P1B-5 = PASS (92 DENIED, 0 ALLOWED)",
                     "P1B6_LINE_COUNT_DISCREPANCY = DOCUMENTATION_ERRATUM_ONLY", "GRANT_ABSENT = TRUE",
                     "REGISTRY_EFFECTIVE = NO", "AUTHORITY_ACTIVE = NO", "AUTHORIZATION_REGISTER_COPY_MISSING = TRUE",
                     "GENESIS_PIN_COPY_MISSING = TRUE", "POST_MB6_DR5_TARGET_ACCEPTED = NO", "M-B7 = NOT AUTHORIZED",
                     "M-B8 = NOT AUTHORIZED", "M-B9a / M-B9b = NOT AUTHORIZED", "WITNESS GENESIS = NOT AUTHORIZED",
                     "RECORD_1 = NOT AUTHORIZED", "FIRST_MEMORY = NOT AUTHORIZED", "AUTHORITY ACTIVATION = NOT AUTHORIZED",
                     "PROD = NOT AUTHORIZED", "FRESHNESS=UNKNOWN"):
            self.assertIn(line, self.state)
        self.assertIn("DEPLOYMENT_FREEZE = ENDED (after owner §12 acceptance and acceptance-time host verification)",
                      self.state)
        for claim in FORBIDDEN_CLAIMS:
            self.assertNotIn(claim, self.text)

    def test_identities_equal_the_accepted_head_and_code(self):
        identities = section(self.text, "## 1. Identities", "## 2.")
        for value in (CONTROL, O.RELEASE_SHA, HEAD, OP_JCS_SHA, SCHEMA, O.REGISTRY_DIGEST, *VALUES.values(),
                      O.TOOL_PINS[O.VERIFIER], O.TOOL_PINS[O.LEDGER_DENIAL]):
            self.assertIn(value, identities)
        self.assertEqual(V.ledger_head(V.pinned_genesis_op()), HEAD)
        self.assertEqual(V.ACCEPTED_PINS.schema_fingerprint, SCHEMA)
        self.assertIn(f"EXPECTED_LEDGER_HEAD = {HEAD}", HEAD_RECORD.read_text(encoding="utf-8"))
        self.assertIn("4a91d98421e38326858e141152180c127f5a67306eebe51a8ca8762f0504dcc5", identities)

    def test_exactly_one_invocation_and_post(self):
        invocation = flat(section(self.text, "## 4. M-B6 (exactly one invocation)", "## 5."))
        for needed in ("**exactly one**", "`provision` was never invoked again", "**`CLI_SUCCESS_EXACT`**",
                       "written `O_EXCL` at **18:57:49Z**", "`stateDirectory=CREATED`"):
            self.assertIn(needed, invocation)
        post = flat(section(self.text, "## 5. POST", "## 6."))
        for needed in ("**`W6_6_POST_VERIFIED_ACCEPTANCE_PENDING`** before owner acceptance", "`LEDGER_COMMITTED_EXACT`",
                       "**The database is the only state-directory entry**", "`registryEffective=false`, "
                       "`authorityActive=false`, `authorityGranted=false`", "`MB6_LEDGER_DENIAL_PROOF=PASS phase=P1B-6 "
                       "denied=20 allowed=0`", "92 `DENIED`, 0 `ALLOWED`", "`fae62c87…`"):
            self.assertIn(needed, post)

    def test_acceptance_is_the_package_template_with_only_placeholders_filled(self):
        package = PACKAGE.read_text(encoding="utf-8")
        template = section(section(package, "## 12. Owner acceptance", "## 13."), "```text\n", "```")
        self.assertEqual(sorted(set(re.findall(r"<[A-Z0-9_]+>", template))), sorted(VALUES))
        filled = template
        for key, value in VALUES.items():
            filled = filled.replace(key, value)
        quoted = section(self.text, "## 6. Owner acceptance (verbatim, package §12)", "**The deployment freeze ended")
        quote = " ".join(line[1:].strip() for line in quoted.splitlines() if line.startswith(">"))
        self.assertEqual(quote.split(), filled.split())
        self.assertIn("**The deployment freeze ended at 19:08:52Z** (package §13)", self.text)
        self.assertIn("It did not end at technical success.", flat(self.text))

    def test_p1b6_erratum_is_append_only_and_matches_the_tested_transcript(self):
        import test_b1b3e_mb6_ledger_denial_proof as D

        self.assertEqual(len(D.PASS_TRANSCRIPT), 27)
        self.assertEqual(D.PASS_TRANSCRIPT[-1], "MB6_LEDGER_DENIAL_PROOF=PASS phase=P1B-6 denied=20 allowed=0")
        erratum = flat(section(self.text, "## 7. P1B-6 line-count erratum", "## 8."))
        for needed in ("P1B6_LINE_COUNT_DISCREPANCY = DOCUMENTATION_ERRATUM_ONLY",
                       "correct deterministic transcript line count = 27",
                       "2 state + 2 unit + 1 GRANT_ABSENT + 20 DENIED probes + 1 scope + 1 PASS"):
            self.assertIn(needed, erratum)
        for item in ("P1B-6 PASS;", "M-B6 technical success;", "W6-6;", "the owner acceptance;",
                     "the ledger sequence, head, op or schema fingerprint;", "the denial semantics;",
                     "the deployment-freeze history;", "any previous evidence result."):
            self.assertIn(item, erratum)
        remediation = REMEDIATION.read_text(encoding="utf-8")
        package = PACKAGE.read_text(encoding="utf-8")
        self.assertIn("**Expected PASS transcript: 28 lines.**", remediation)               # original preserved
        self.assertIn("28-line transcript of the remediation record §13", package)            # original preserved
        for text, original in ((remediation, "**Expected PASS transcript: 28 lines.**"),
                               (package, "28-line transcript of the remediation record §13")):
            block = "> **Erratum (2026-10-07, M-B6 completion; owner determination `P1B6_LINE_COUNT_DISCREPANCY = " \
                    "DOCUMENTATION_ERRATUM_ONLY`; the text above is unchanged).**"
            self.assertEqual(text.count(block), 1)
            self.assertLess(text.index(original), text.index(block))
            self.assertIn("The P1B-6 PASS transcript has **27** lines, not 28", text)

    def test_dr5_target_not_pre_accepted(self):
        dr5 = section(self.text, "## 8. DR-5 state", "## 9.")
        self.assertIn("| `PHASE_BOUND_DR5_BASELINE_WITH_DERIVED_DELTA` | **APPLIES** |", dr5)
        self.assertIn("| `POST_MB6_DR5_TARGET_ACCEPTED` | **NO** |", dr5)
        self.assertIn(f"`{T.POST['result-set'][1]}`, 188 lines, 161 `DENIED`, 0 `ALLOWED`, 0 `FAIL`", dr5)
        self.assertEqual(T.POST["result-set"][0], 188)
        self.assertIn("compare LEDGER_COMMITTED_EXACT <log>", dr5)
        self.assertIn("**Not pre-accepted.**", dr5)

    def test_authority_and_first_memory_boundaries(self):
        boundaries = flat(section(self.text, "## 9. Boundaries", "## 10."))
        for needed in ("ledger provision does not make Registry V1 effective", "ledger provision does not activate authority",
                       "ledger provision does not authorize any memory write", "**not** witness genesis",
                       "M-B6 acceptance granted no M-B7 authority"):
            self.assertIn(needed, boundaries)
        for row in ("| M-B8 | **NOT AUTHORIZED** |", "| witness genesis | **NOT AUTHORIZED** |", "| record 1 | **NOT AUTHORIZED** |",
                    "| First Memory | **NOT AUTHORIZED** |", "| authority activation | **NOT AUTHORIZED** |",
                    "| PROD | **NOT AUTHORIZED** |"):
            self.assertIn(row, boundaries)
        self.assertIn("First Memory must **not** be auto-generated, inferred or chosen by tooling", boundaries)
        self.assertIn("the process **STOPS** there", boundaries)
        self.assertIn("separate explicit owner authorization are required before any First Memory content is created or "
                      "written", boundaries)

    def test_index_and_ledger(self):
        readme = (ARCH / "README.md").read_text(encoding="utf-8")
        self.assertIn("(slice-15b2b-b1b3e-mb6-provision-ledger-completion.md)", readme)
        ledger = LEDGER.read_text(encoding="utf-8")
        self.assertIn("### 13.1ah Current-state reconciliation (M-B6 PROVISION_LEDGER completion and owner acceptance", ledger)
        self.assertIn("FRESHNESS=UNKNOWN (§13.1ah) | UNASSIGNED |", ledger)
        self.assertIn("[`M-B6 = COMPLETED / OWNER-ACCEPTED`](slice-15b2b-b1b3e-mb6-provision-ledger-completion.md)", ledger)
        self.assertLess(ledger.index("### 13.1ag"), ledger.index("### 13.1ah"))
        self.assertLess(ledger.index("### 13.1ah"), ledger.index("### 13.2 Checks"))


if __name__ == "__main__":
    unittest.main()
