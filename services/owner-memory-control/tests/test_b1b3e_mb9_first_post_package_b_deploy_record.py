"""15B2b-B1b-3e: first post-Package-B-freeze deploy record (TEST-ONLY, stdlib).

Record: docs/architecture/slice-15b2b-b1b3e-mb9-first-post-package-b-deploy.md.

Pins: the deploy run, control (PR #174 merge), validation run, base and previous deploy; Package B completed before
it; the W9-verified phase W9_5_GENESIS_COMMITTED_EXACT with the genesis and incarnation unchanged; the running-witness
DR-5 target (equal to the derivation pins and the phase map) and its counts; acceptance as a phase-bound target
only, never a global baseline; the verbatim owner acceptance (SHA-256 recomputed from the quoted text, kept without
the leading "I"); the evidence seals; the next deploy unauthorized; and record 1, the signer, activation, First
Memory and PROD unauthorized.
"""

from __future__ import annotations

import hashlib
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
ARCH = ROOT / "docs/architecture"
RECORD = ARCH / "slice-15b2b-b1b3e-mb9-first-post-package-b-deploy.md"
COMPLETION = ARCH / "slice-15b2b-b1b3e-mb9-package-b-completion.md"
LEDGER = ARCH / "current-architecture-acceptance-ledger-v0.1.md"
TOOLS = ROOT / "services/owner-memory-control/tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import mb9_dr5_target as T  # noqa: E402

RUN = "37888892605"
VALIDATION = "37888756220"
PREVIOUS_RUN = "37829794035"
CONTROL = "2532176d5faeff0d9b1fe73bd193297d591fee2e"
HEAD = "c15005cdb5d580a0c729efac3d337b69b544564e"
BASE = "050e7c5c4c6238eee09eb67b094348127d2953c6"
PHASE = "W9_5_GENESIS_COMMITTED_EXACT"
OPERATOR = "066fc8213b40c392e3e2bfd609da4a7f2a4e0b6f05da011daee9add3caf13973"
FULL = "593c90e1778b0e90326cdf96314b328948c00b2207960d27be2b41874d05ff65"
BLOCK = "ace51f27ac17a2d719ec19da582d09e21f0c7fb4be7b6ec81e1dd53cb369fd5a"
PRE_DEPLOY = "f50870420c10149914b8d2a02116708ec89ea5a8f746a847fbe88df058f54cae"
GENESIS = "ac892dc2b14ca7db108400258abfcf2320ff498f2a674058058e16a8a6fb65e4"
CHAIN_1 = "252c32204bebf3fa1ca0981d8791115e2abb6cd8ddb0925285c64213317cfb99"
INVOCATION, MAINPID = "5136ea7af2544450b9370fa412786c98", "143946"
ACCEPTANCE = "ff9ecac4dc8a6f1d87fdb74620530a9eea04fd29446d255f462ee52a948ab353"
DRAFT = "528da7f08b89ab7ba241f5b61146c97f6c3fe867087bfc006890045f17d5eae1"
SEAL = "4582edfd348a25f6d49119e54b6228936556f2e0e0d00a330cfcaf52af1cf453"
PRIOR_SEAL = "95d13af50409c2a88a64f6951a07f1278a0d94bd762907f210c37d2024728677"
FORBIDDEN = ("NEW_GLOBAL_DR5_BASELINE = ACCEPTED", "GLOBAL BASELINE = ACCEPTED", "RECORD 1 = PRESENT",
             "SIGNER = ACTIVE", "REGISTRY_EFFECTIVE = YES", "AUTHORITY_ACTIVE = YES", "authorityGranted = true",
             "FIRST_MEMORY = AUTHORIZED", "FIRST_MEMORY_READY = REACHED", "PROD = AUTHORIZED", "HELD = AUTHORIZED",
             "ACCEPTANCE_ENVELOPE = AUTHORIZED", "AUTHORITY ACTIVATION = AUTHORIZED", "FRESHNESS=CURRENT",
             "FIRST_POSTB_DEPLOY_RECORD_MERGE = AUTHORIZED", "NEXT_DEPLOY = EQUAL", "STOPPED_WITNESS_DR5_TARGET = ACCEPTED")


def flat(text: str) -> str:
    return " ".join(re.sub(r"^\s*>", " ", text, flags=re.MULTILINE).split())


def section(text: str, start: str, end: str) -> str:
    return text.split(start, 1)[1].split(end, 1)[0]


class FirstPostPackageBDeployRecordTests(unittest.TestCase):
    def setUp(self):
        self.text = RECORD.read_text(encoding="utf-8")
        self.state_lines = set(self.text.split("## 10. State", 1)[1].splitlines())

    def test_owner_accepted_and_package_b_already_completed(self):
        self.assertTrue(RECORD.is_file())
        head = flat(self.text.split("## 1.", 1)[0])
        self.assertIn("`FIRST_POST_PACKAGE_B_FREEZE_DEPLOY = EQUAL / OWNER-ACCEPTED`", head)
        self.assertIn("**Package B was already completed and owner-accepted before this deploy**", head)
        for line in ("FIRST_POST_PACKAGE_B_FREEZE_DEPLOY = EQUAL / OWNER-ACCEPTED", "PACKAGE_B = COMPLETED / OWNER-ACCEPTED"):
            self.assertIn(line, self.state_lines)
        self.assertIn("PACKAGE_B = COMPLETED / OWNER-ACCEPTED", COMPLETION.read_text(encoding="utf-8"))

    def test_run_control_validation_and_first_deploy(self):
        ids = section(self.text, "## 1. Identities", "## 2.")
        self.assertIn(f"| control | `{CONTROL}` (merge of PR #174, the Package B completion record", ids)
        self.assertIn(f"reviewed head `{HEAD}`", ids)
        self.assertIn(f"| source validation | `{VALIDATION}` (`push`), success |", ids)
        self.assertIn(f"| `FIRST_POST_PACKAGE_B_FREEZE_DEPLOY_RUN` | `{RUN}`, \"Deploy LILITH Core API to DEV\", "
                      "`workflow_run`, branch `main`, success", ids)
        self.assertIn(f"| mode / base | `DEPLOY_REQUIRED`; base `{BASE}` |", ids)
        self.assertIn(f"| previous DEV deploy | `{PREVIOUS_RUN}`", ids)
        self.assertIn(f"SHA-256 `{OPERATOR}`", ids)
        for line in (f"FIRST_POST_PACKAGE_B_FREEZE_DEPLOY_RUN = {RUN}", f"FIRST_POST_PACKAGE_B_FREEZE_DEPLOY_CONTROL = {CONTROL}",
                     f"SOURCE_VALIDATION_RUN = {VALIDATION}", f"PREVIOUS_DEV_DEPLOY = {PREVIOUS_RUN}"):
            self.assertIn(line, self.state_lines)
        self.assertIn(f"No deploy ran between `{PREVIOUS_RUN}` and `{RUN}`",
                      flat(section(self.text, "## 2. The first post-Package-B-freeze deploy", "## 3.")))

    def test_w9_phase_and_unchanged_genesis(self):
        gate = flat(section(self.text, "## 3. Phase gate", "## 4."))
        for needed in ("**`MB9_HOST_POST9B_PASS`**, all 10 codes 0", f"**W9 phase: `{PHASE}`.**", GENESIS, CHAIN_1,
                       "store `CONSISTENT`", "**The witness genesis is unchanged.**",
                       f"InvocationID `{INVOCATION}`, MainPID `{MAINPID}`, NRestarts 0", "**Witness health:** `CONSISTENT`",
                       "`registryEffective = false`, `authorityActive = false`, `authorityGranted = false`",
                       "`ACTIVATION=NOT_ACCEPTED reason=GRANT_ABSENT`", "**Signer:** units inactive", "**Record 1:** absent",
                       "`REBOOT_REQUIRED=absent`"):
            self.assertIn(needed, gate)
        for line in (f"W9_PHASE = {PHASE}", f"WITNESS_GENESIS_DIGEST = {GENESIS}", f"CHAIN_1_SHA256 = {CHAIN_1}",
                     f"WITNESS_INVOCATION_ID = {INVOCATION}", f"WITNESS_MAIN_PID = {MAINPID}", "WITNESS_NRESTARTS = 0",
                     "WITNESS_HEALTH = CONSISTENT"):
            self.assertIn(line, self.state_lines)

    def test_running_target_equals_the_derivation_pins_and_phase_map(self):
        self.assertEqual(T.PHASE_TARGETS[PHASE], T.RUNNING)
        running = T.TARGETS[T.RUNNING]
        self.assertEqual(running["result-set"], (192, FULL))
        self.assertEqual(running["dr5-block"], (153, BLOCK))
        self.assertEqual(running["predeploy-block"], (29, PRE_DEPLOY))
        dr5 = section(self.text, "## 4. DR-5 comparison", "## 5.")
        self.assertIn(f"| full result set | 192 | `{FULL}` | 167 `DENIED`, 0 `ALLOWED`, 0 `FAIL`, 1 "
                      "`DEFERRED_UNTIL_OBJECT_EXISTS`, 6 `UNOBSERVABLE_BY_DESIGN` |", dr5)
        self.assertIn(f"| DR-5 block | 153 | `{BLOCK}` | 139 `DENIED`, 0 `ALLOWED` |", dr5)
        self.assertIn(f"| pre-deploy block | 29 | `{PRE_DEPLOY}` | 28 `DENIED` |", dr5)
        self.assertIn(f"`mb9_operator.py dr5 <repo> {PHASE} <log>` returned **`EQUAL`**, target `WITNESS_RUNNING`, "
                      "with `unequal = []`, `allowed = 0` and `fail = 0`", flat(dr5))
        for line in ("RUNNING_WITNESS_DR5_COMPARISON = EQUAL", f"RUNNING_DR5_FULL_SHA256 = {FULL}",
                     f"RUNNING_DR5_BLOCK_SHA256 = {BLOCK}", f"RUNNING_DR5_PREDEPLOY_SHA256 = {PRE_DEPLOY}"):
            self.assertIn(line, self.state_lines)

    def test_accepted_only_as_the_phase_bound_target_never_global(self):
        self.assertIn(f"RUNNING_WITNESS_DR5_TARGET = ACCEPTED (PHASE-BOUND: {PHASE} ONLY)", self.state_lines)
        self.assertIn("NEW_GLOBAL_DR5_BASELINE = NONE", self.state_lines)
        accepted = flat(section(self.text, "## 5. What is accepted", "## 6."))
        self.assertIn(f"accepted **only** as the phase-bound comparison target for `{PHASE}`", accepted)
        self.assertIn("It is not a new global baseline.", accepted)
        self.assertIn("The stopped-witness target (`7f70aa3b…`) stays PROPOSED / NOT ACCEPTED.", accepted)
        self.assertIn("remains the target for `W9_0_PRE_WITNESS` only", accepted)
        self.assertIn("**It is not a new global baseline.**", flat(self.text.split("## 1.", 1)[0]))

    def test_owner_acceptance_verbatim_without_rewriting(self):
        quote = section(self.text, "## 6. Owner acceptance (verbatim)", "The text is preserved exactly as issued.")
        text = " ".join(line[2:] for line in quote.splitlines() if line.startswith("> "))
        self.assertEqual(hashlib.sha256((text + "\n").encode("utf-8")).hexdigest(), ACCEPTANCE)
        self.assertTrue(text.startswith("accept deployment run 37888892605 (“Deploy LILITH Core API to DEV”"))
        self.assertIn(f"Owner acceptance text SHA-256 (the text plus one terminal LF): `{ACCEPTANCE}`", quote)
        self.assertIn(f"OWNER_ACCEPTANCE_TEXT_SHA256 = {ACCEPTANCE}", self.state_lines)
        for needed in (RUN, CONTROL, VALIDATION, FULL, BLOCK, PRE_DEPLOY, GENESIS, CHAIN_1, INVOCATION,
                       "Therefore FIRST_POST_PACKAGE_B_FREEZE_DEPLOY = EQUAL and is ACCEPTED",
                       "it is not a new global baseline", "This acceptance authorizes nothing further"):
            self.assertIn(needed, text)
        note = flat(section(self.text, "The text is preserved exactly as issued.", "## 7."))
        self.assertIn(f"`{DRAFT}`", note)
        self.assertIn('the leading "I" is absent', note)

    def test_evidence_seals(self):
        seal = flat(section(self.text, "## 7. Evidence seal", "## 8."))
        self.assertIn(f"(`SHA256SUMS`, 58 entries, every evidence file except the checkout copy and the seal files): "
                      f"`{SEAL}`. It covers the verbatim acceptance file", seal)
        self.assertIn(f"`SHA256SUMS.seal-1-95d13af5`: `{PRIOR_SEAL}` (56 entries)", seal)
        self.assertIn(f"EVIDENCE_SEAL = {SEAL}", self.state_lines)
        self.assertIn(f"PRIOR_SEAL_PRESERVED = {PRIOR_SEAL}", self.state_lines)

    def test_next_deploy_order_unauthorized(self):
        order = flat(section(self.text, "## 8. Ordering after this acceptance", "## 9."))
        steps = ("this record PR, reviewed", "a separate owner merge authorization",
                 f"must establish `{PHASE}`", "must compare `EQUAL` to the accepted running-witness phase-bound target",
                 "a separate owner acceptance of that deploy")
        positions = [order.index(step) for step in steps]
        self.assertEqual(positions, sorted(positions))
        self.assertIn("FIRST_POSTB_DEPLOY_RECORD_MERGE = NOT AUTHORIZED", self.state_lines)
        self.assertIn("NEXT_DEPLOY = NOT YET OCCURRED; NOT AUTHORIZED", order)

    def test_boundaries(self):
        for line in ("REGISTRY_EFFECTIVE = NO", "AUTHORITY_ACTIVE = NO", "authorityGranted = false", "GRANT_ABSENT = TRUE",
                     "SIGNER = INACTIVE", "RECORD 1 = ABSENT", "ACCEPTANCE_ENVELOPE = NOT AUTHORIZED",
                     "HELD = NOT AUTHORIZED", "AUTHORITY ACTIVATION = NOT AUTHORIZED", "FIRST_MEMORY = NOT AUTHORIZED",
                     "PROD = NOT AUTHORIZED", "FRESHNESS=UNKNOWN"):
            self.assertIn(line, self.state_lines)
        for claim in FORBIDDEN:
            self.assertNotIn(claim, self.text, claim)
        boundary = flat(section(self.text, "## 9. Boundaries", "## 10."))
        self.assertIn("Tooling must not infer, choose, draft or write LILITH's First Memory", boundary)
        self.assertIn("the process **STOPS** there", boundary)

    def test_completion_record_keeps_its_history(self):
        self.assertIn("FIRST_POST_PACKAGE_B_FREEZE_DEPLOY = NOT YET OCCURRED", COMPLETION.read_text(encoding="utf-8"))
        self.assertIn("This record supersedes it on this one point only, from 2026-10-09", flat(self.text))

    def test_ledger_and_index(self):
        ledger = LEDGER.read_text(encoding="utf-8")
        self.assertIn("### 13.1aq Current-state reconciliation (first post-Package-B-freeze deploy: running-witness DR-5 "
                      "comparison, 2026-10-09)", ledger)
        self.assertLess(ledger.index("### 13.1ap"), ledger.index("### 13.1aq"))
        self.assertLess(ledger.index("### 13.1aq"), ledger.index("### 13.2 Checks"))
        self.assertIn("FRESHNESS=UNKNOWN (§13.1aq) | UNASSIGNED |", ledger)   # the AUTH-02 cell
        aq = section(ledger, "### 13.1aq", "### 13.2 Checks")
        for needed in (RUN, CONTROL, VALIDATION, ACCEPTANCE, PHASE, "**it is not a new global baseline**",
                       "None has happened.", "This pass contacted no live system.", "193 rows"):
            self.assertIn(needed, aq)
        for claim in FORBIDDEN:
            self.assertNotIn(claim, aq, claim)
        readme = (ARCH / "README.md").read_text(encoding="utf-8")
        self.assertIn("(slice-15b2b-b1b3e-mb9-first-post-package-b-deploy.md)", readme)


if __name__ == "__main__":
    unittest.main()
