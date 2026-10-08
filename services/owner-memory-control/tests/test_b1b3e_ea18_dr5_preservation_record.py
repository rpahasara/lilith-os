"""15B2b-B1b-3e: E-A18 first post-Package-A-freeze DR-5 preservation record (TEST-ONLY, stdlib).

Record: docs/architecture/slice-15b2b-b1b3e-ea18-first-post-package-a-dr5-preservation.md.

Pins: the E-A18 deploy run, control, base and previous deploy; the W8-verified phase; the accepted post-M-B6 DR-5
baseline (equal to the canonical extractor's pinned target and the Package A operator's phase set); the counts; the
verbatim owner acceptance (its SHA-256 recomputed from the quoted text); the evidence seals; no new baseline; the
earlier records keeping NOT YET PERFORMED as history; the ordering that puts a preservation deploy before any
Package B control; and Package B, M-B9a, M-B9b, witness genesis, record 1, First Memory and PROD unauthorized.
"""

from __future__ import annotations

import hashlib
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
ARCH = ROOT / "docs/architecture"
RECORD = ARCH / "slice-15b2b-b1b3e-ea18-first-post-package-a-dr5-preservation.md"
PACKAGE_A_COMPLETION = ARCH / "slice-15b2b-b1b3e-mb7-mb8-package-a-completion.md"
PACKAGE_B = ARCH / "slice-15b2b-b1b3e-mb9-witness-genesis-package.md"
LEDGER = ARCH / "current-architecture-acceptance-ledger-v0.1.md"
TOOLS = ROOT / "services/owner-memory-control/tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import mb6_dr5_target as T  # noqa: E402

RUN = "37791575032"
PREVIOUS_RUN = "37741374796"
CONTROL = "36b21c90dfe8e5e4243b56f24de503ea0a4f8b91"
BASE = "29c2b824cae187037e4434a1ad7f9466f4eb2ab6"
PHASE = "OWNER_INPUTS_INSTALLED_EXACT"
FULL = "3640ca0136e5740835f7047480e472e737b2556c14b48db66ff1c1983350f494"
BLOCK = "d05aa017672c370b49518297c98709c0381765b9c98a7e29ac9a1edf094e7801"
PRE_DEPLOY = "f50870420c10149914b8d2a02116708ec89ea5a8f746a847fbe88df058f54cae"
ACCEPTANCE = "df80425edcc3d3f29b527345f227f944667f9bddd7b0c71d48207453daa4a4c2"
SEAL = "997fd9049ba1dac7ab0676c9c7638efca854dada61483207dcfd8b4ca8c18e9b"
PRIOR_SEAL = "93921edaafff3f2f32dec143d387e612011c943508d37c9a45e1b49de949baf2"
PIN = "357477369ab53790245b42cbecbe2a630110477bede5b599696699e4f5c3a590"
REGISTER = "8d5ab87564d0e531b7d1467c18b6d106f2a468d5d155ce9f2acb64758df85575"
HEAD = "19bf9091a96cdc2378a68508feb0c119721f7fcef7b9c3a480a6cd6b72fa1630"
FORBIDDEN = ("PACKAGE_B = OPEN", "B1 = AUTHORIZED", "M-B9a = AUTHORIZED", "M-B9b = AUTHORIZED",
             "WITNESS_GENESIS = COMMITTED", "RECORD 1 = PRESENT", "FIRST_MEMORY = AUTHORIZED", "PROD = AUTHORIZED",
             "REGISTRY_EFFECTIVE = YES", "AUTHORITY_ACTIVE = YES", "FRESHNESS=CURRENT", "NEW_DR5_BASELINE = ACCEPTED",
             "EA18_RECORD_MERGE = AUTHORIZED", "EA18_RECORD_PRESERVATION_DEPLOY = EQUAL", "PACKAGE_B_CONTROL = SELECTED")


def flat(text: str) -> str:
    return " ".join(re.sub(r"^\s*>", " ", text, flags=re.MULTILINE).split())


def section(text: str, start: str, end: str) -> str:
    return text.split(start, 1)[1].split(end, 1)[0]


class Ea18RecordTests(unittest.TestCase):
    def setUp(self):
        self.text = RECORD.read_text(encoding="utf-8")
        self.state = self.text.split("## 10. State", 1)[1]
        self.state_lines = set(self.state.splitlines())

    def test_record_exists_and_is_owner_accepted(self):
        self.assertTrue(RECORD.is_file())
        self.assertIn("`E-A18 = COMPLETED / OWNER-ACCEPTED`", self.text.split("## 1.", 1)[0])
        self.assertIn("E-A18 = COMPLETED / OWNER-ACCEPTED", self.state_lines)
        self.assertIn("POST_MB6_ACCEPTED_DR5_BASELINE_PRESERVED = YES", self.state_lines)

    def test_deploy_control_and_first_post_freeze(self):
        ids = section(self.text, "## 1. Identities", "## 2.")
        self.assertIn(f"| `E-A18_DEPLOY_RUN` | `{RUN}`, \"Deploy LILITH Core API to DEV\", `workflow_run`, branch `main`, "
                      "success", ids)
        self.assertIn(f"| control | `{CONTROL}` (merge of PR #170", ids)
        self.assertIn(f"| mode / base | `DEPLOY_REQUIRED`; base `{BASE}` |", ids)
        self.assertIn(f"| previous DEV deploy | `{PREVIOUS_RUN}` (`29c2b82`", ids)
        for line in (f"E-A18_DEPLOY_RUN = {RUN}", f"E-A18_CONTROL = {CONTROL}", "FIRST_POST_PACKAGE_A_FREEZE_DEPLOY = YES",
                     f"PREVIOUS_DEV_DEPLOY = {PREVIOUS_RUN}"):
            self.assertIn(line, self.state_lines)
        first = flat(section(self.text, "## 2. The first post-Package-A-freeze deploy", "## 3."))
        self.assertIn(f"No deploy ran between `{PREVIOUS_RUN}` and `{RUN}`", first)
        self.assertIn("no historical PASS was replayed", first)

    def test_phase_is_w8_verified_exact(self):
        self.assertIn(f"E-A18_PHASE = {PHASE}", self.state_lines)
        gate = flat(section(self.text, "## 3. Phase gate", "## 4."))
        for needed in ("**`MB7_MB8_HOST_POST_PASS`**, all 9 codes 0", f"**W8 phase: `{PHASE}`.**", PIN, REGISTER,
                       f"exact, sequence 1, head `{HEAD}`", "`registryEffective = false`, `authorityActive = false`, "
                       "`authorityGranted = false`", "`ACTIVATION=NOT_ACCEPTED reason=GRANT_ABSENT`",
                       "`/var/lib/lilith-recovery-witness` is absent", "`witnessGenesisPresent = false`",
                       "no record 1 and no M-B9a or M-B9b state"):
            self.assertIn(needed, gate)

    def test_dr5_hashes_equal_the_accepted_baseline(self):
        self.assertEqual(T.POST["result-set"], (188, FULL))
        self.assertEqual(T.POST["dr5-block"], (149, BLOCK))
        self.assertEqual(T.POST["predeploy-block"], (29, PRE_DEPLOY))
        dr5 = section(self.text, "## 4. DR-5 comparison", "## 5.")
        self.assertIn(f"| full result set | 188 | `{FULL}` | 161 `DENIED`, 0 `ALLOWED`, 0 `FAIL`, 3 "
                      "`DEFERRED_UNTIL_OBJECT_EXISTS`, 6 `UNOBSERVABLE_BY_DESIGN` |", dr5)
        self.assertIn(f"| DR-5 block | 149 | `{BLOCK}` | 133 `DENIED`, 0 `ALLOWED` |", dr5)
        self.assertIn(f"| pre-deploy block | 29 | `{PRE_DEPLOY}` | 28 `DENIED` |", dr5)
        self.assertIn("returned **`EQUAL`**, target `POST_MB6_ACCEPTED_BASELINE_UNCHANGED_BY_PACKAGE_A`, with "
                      "`unequal = []`, `allowed = 0` and `fail = 0`", flat(dr5))
        for line in ("POST_MB6_DR5_COMPARISON = EQUAL", f"DR5_FULL_SHA256 = {FULL}", f"DR5_BLOCK_SHA256 = {BLOCK}",
                     f"DR5_PREDEPLOY_SHA256 = {PRE_DEPLOY}"):
            self.assertIn(line, self.state_lines)

    def test_the_phase_is_one_the_package_a_operator_accepts(self):
        import mb7_mb8_operator as O

        self.assertIn(PHASE, O.DR5_PHASES)
        self.assertEqual(O.W8_PHASE["POST"], PHASE)

    def test_no_new_baseline(self):
        self.assertIn("NEW_DR5_BASELINE = NONE", self.state_lines)
        self.assertIn("**No new baseline was created.**", flat(self.text.split("## 1.", 1)[0]))

    def test_owner_acceptance_verbatim_and_hash(self):
        quote = section(self.text, "## 6. Owner acceptance (verbatim)", "The owner separately authorized")
        lines = [line[2:] for line in quote.splitlines() if line.startswith("> ")]
        text = " ".join(lines)
        self.assertEqual(hashlib.sha256((text + "\n").encode("utf-8")).hexdigest(), ACCEPTANCE)
        self.assertIn(f"Owner acceptance text SHA-256 (the text plus one terminal LF): `{ACCEPTANCE}`", quote)
        self.assertIn(f"OWNER_ACCEPTANCE_TEXT_SHA256 = {ACCEPTANCE}", self.state_lines)
        for needed in (f"Deployment run {RUN}", CONTROL, FULL, BLOCK, PRE_DEPLOY,
                       "Therefore E-A18 = COMPLETED / OWNER-ACCEPTED and POST_MB6_ACCEPTED_DR5_BASELINE_PRESERVED = YES.",
                       "It does not authorize creating or merging the E-A18 record PR"):
            self.assertIn(needed, text)

    def test_evidence_seals(self):
        seal = flat(section(self.text, "## 7. Evidence seal", "## 8."))
        self.assertIn(f"`{SEAL}`. It covers the verbatim acceptance file", seal)
        self.assertIn(f"preserved byte-identically beside it: `{PRIOR_SEAL}`", seal)
        self.assertIn(f"EA18_EVIDENCE_SEAL = {SEAL}", self.state_lines)
        self.assertIn(f"EA18_PRIOR_SEAL_PRESERVED = {PRIOR_SEAL}", self.state_lines)

    def test_ordering_preservation_deploy_before_package_b_control(self):
        order = flat(section(self.text, "## 8. Ordering after E-A18", "## 9."))
        steps = ("this E-A18 record PR, reviewed", "a separate owner merge authorization", "**preservation deploy**",
                 "a separate owner acceptance of that preservation result",
                 "only then may that merge commit become the Package B live control", "B1 opens Package B")
        positions = [order.index(step) for step in steps]
        self.assertEqual(positions, sorted(positions))
        for line in ("EA18_RECORD_MERGE = NOT AUTHORIZED", "EA18_RECORD_PRESERVATION_DEPLOY = NOT YET OCCURRED",
                     "PACKAGE_B_CONTROL = NOT SELECTED"):
            self.assertIn(line, self.state_lines)
        package_b = flat(section(PACKAGE_B.read_text(encoding="utf-8"), "## 13. E-A18", "## 14."))
        self.assertLess(package_b.index("a small E-A18 record PR"),
                        package_b.index("only then may that merge commit become the Package B live control"))

    def test_package_b_and_later_stages_unauthorized(self):
        for line in ("PACKAGE_B = NOT OPEN", "B1 = NOT AUTHORIZED", "M-B9a = NOT AUTHORIZED", "M-B9b = NOT AUTHORIZED",
                     "WITNESS_GENESIS = NOT COMMITTED", "RECORD 1 = ABSENT", "FIRST_MEMORY = NOT AUTHORIZED",
                     "AUTHORITY ACTIVATION = NOT AUTHORIZED", "PROD = NOT AUTHORIZED", "REGISTRY_EFFECTIVE = NO",
                     "AUTHORITY_ACTIVE = NO", "GRANT_ABSENT = TRUE", "SIGNER = INACTIVE", "WITNESS = INACTIVE",
                     "FRESHNESS=UNKNOWN"):
            self.assertIn(line, self.state_lines)
        for claim in FORBIDDEN:
            self.assertNotIn(claim, self.text, claim)
        boundary = flat(section(self.text, "## 9. Boundaries", "## 10."))
        self.assertIn("Tooling must not infer, choose, draft or write LILITH's First Memory", boundary)
        self.assertIn("the process **STOPS** there", boundary)

    def test_earlier_records_keep_not_yet_performed_history(self):
        self.assertIn("**`E-A18 = NOT YET PERFORMED`.**", PACKAGE_A_COMPLETION.read_text(encoding="utf-8"))
        self.assertIn("E-A18 = NOT YET PERFORMED", PACKAGE_B.read_text(encoding="utf-8"))
        self.assertIn("This record supersedes them on this one point only, from 2026-10-08", flat(self.text))

    def test_ledger_and_index(self):
        ledger = LEDGER.read_text(encoding="utf-8")
        self.assertIn("### 13.1am Current-state reconciliation (E-A18: first post-Package-A-freeze DR-5 preservation", ledger)
        self.assertLess(ledger.index("### 13.1al"), ledger.index("### 13.1am"))
        self.assertLess(ledger.index("### 13.1am"), ledger.index("### 13.2 Checks"))
        self.assertIn("FRESHNESS=UNKNOWN (§13.1am) | UNASSIGNED |", ledger)   # the AUTH-02 cell
        am = section(ledger, "### 13.1am", "### 13.2 Checks")
        for needed in ("`E-A18 = COMPLETED / OWNER-ACCEPTED`", "**no new baseline was created**", RUN, PREVIOUS_RUN,
                       "None of these has happened.", "Package B NOT OPEN"):
            self.assertIn(needed, am)
        for claim in FORBIDDEN:
            self.assertNotIn(claim, am, claim)
        self.assertIn("**E-A18 is NOT YET PERFORMED.**", section(ledger, "### 13.1ak", "### 13.1al"))   # history unchanged
        readme = (ARCH / "README.md").read_text(encoding="utf-8")
        self.assertIn("(slice-15b2b-b1b3e-ea18-first-post-package-a-dr5-preservation.md)", readme)


if __name__ == "__main__":
    unittest.main()
