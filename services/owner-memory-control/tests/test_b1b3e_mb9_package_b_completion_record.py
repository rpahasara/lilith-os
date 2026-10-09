"""15B2b-B1b-3e: Package B sequence 3 completion record (TEST-ONLY, stdlib).

Record: docs/architecture/slice-15b2b-b1b3e-mb9-package-b-completion.md.

Pins: sequence 3 COMPLETED / OWNER-ACCEPTED on control 050e7c5; the B3-accepted witness incarnation and POST9A; the
committed genesis digest (= the owner pin = the Package A candidate), chain/1.json and POST9B; the owner offline
verification; the irreversible lineage; P1B-9a / P1B-9b counts (equal to the denial proof's own row table); the
verbatim B5 acceptance (its SHA-256 recomputed from the quoted text) ending the freeze and authorizing nothing
further; the evidence seals; sequences 1 and 2 historical; the RUNNING DR-5 target (equal to the derivation pins)
as the comparison for the first post-freeze deploy, which has not occurred; and record 1, the envelope, HELD, the
signer, activation, First Memory and PROD unauthorized.
"""

from __future__ import annotations

import hashlib
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
ARCH = ROOT / "docs/architecture"
RECORD = ARCH / "slice-15b2b-b1b3e-mb9-package-b-completion.md"
PACKAGE_B = ARCH / "slice-15b2b-b1b3e-mb9-witness-genesis-package.md"
LEDGER = ARCH / "current-architecture-acceptance-ledger-v0.1.md"
TOOLS = ROOT / "services/owner-memory-control/tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import mb9_dr5_target as T  # noqa: E402

CONTROL = "050e7c5c4c6238eee09eb67b094348127d2953c6"
PRESERVATION_RUN = "37829794035"
OPERATOR = "066fc8213b40c392e3e2bfd609da4a7f2a4e0b6f05da011daee9add3caf13973"
INVOCATION = "5136ea7af2544450b9370fa412786c98"
MAINPID = "143946"
POST9A = "50a2ef262df099190074dbad1f9358587db76ace10a1e22a077e3c3123f6fcfa"
CANDIDATE = "ac892dc2b14ca7db108400258abfcf2320ff498f2a674058058e16a8a6fb65e4"
CHAIN_1 = "252c32204bebf3fa1ca0981d8791115e2abb6cd8ddb0925285c64213317cfb99"
POST9B = "7f41541b4f633187382d9235c07ef1987ffb94bc384f6679623fa5edcbef98af"
ANCHOR = "be360da2324880d725aea509bb0f41500f51ecfc3c2995dd3057824bb471ab5a"
B5 = "1312c01db3d3439ecec7fab22e8141402aa62278e7e7754049d0efd3d6cef6f7"
SEAL = "7e45706f74f8d8faefbd648d0a91329e859ef9ba227f9ed9d546cb57377a6bf6"
PRIOR_SEALS = ("8d1f4ace8ae5e7cf1f1c716527e13b44381777f56bc657fd19f5aee98c168b60",
               "1277299c75d4515cfec319642999cbe1d702b3402849e5a95a226107082af197")
HEAD = "19bf9091a96cdc2378a68508feb0c119721f7fcef7b9c3a480a6cd6b72fa1630"
REGISTRY = "fa66272131a3ef076036616b07766a377de4fdc1e4fef4cb8a054726f05c14fc"
RUNNING_FULL = "593c90e1778b0e90326cdf96314b328948c00b2207960d27be2b41874d05ff65"
RUNNING_BLOCK = "ace51f27ac17a2d719ec19da582d09e21f0c7fb4be7b6ec81e1dd53cb369fd5a"
PRE_DEPLOY = "f50870420c10149914b8d2a02116708ec89ea5a8f746a847fbe88df058f54cae"
SEQ1, SEQ2 = "5ce067cf485cafed6ea2487635027955396e7844", "103efe50d42ea8f016d671d8ee5f052b9ce961ae"
FORBIDDEN = ("RECORD 1 = PRESENT", "RECORD 1 = CREATED", "SIGNER = ACTIVE", "SIGNER = STARTED",
             "REGISTRY_EFFECTIVE = YES", "AUTHORITY_ACTIVE = YES", "authorityGranted = true", "FIRST_MEMORY = AUTHORIZED",
             "FIRST_MEMORY_READY = REACHED", "PROD = AUTHORIZED", "HELD = AUTHORIZED", "ACCEPTANCE_ENVELOPE = AUTHORIZED",
             "AUTHORITY ACTIVATION = AUTHORIZED", "FRESHNESS=CURRENT", "LINEAGE_REVERSIBLE = YES",
             "PACKAGE_B_COMPLETION_RECORD_MERGE = AUTHORIZED", "FIRST_POST_PACKAGE_B_FREEZE_DEPLOY = EQUAL",
             "FIRST_POST_PACKAGE_B_FREEZE_DEPLOY = OCCURRED", "RUNNING_DR5_TARGET = ACCEPTED", "NEW_DR5_BASELINE = ACCEPTED")


def flat(text: str) -> str:
    return " ".join(re.sub(r"^\s*>", " ", text, flags=re.MULTILINE).split())


def section(text: str, start: str, end: str) -> str:
    return text.split(start, 1)[1].split(end, 1)[0]


class PackageBCompletionRecordTests(unittest.TestCase):
    def setUp(self):
        self.text = RECORD.read_text(encoding="utf-8")
        self.state = self.text.split("## 12. State", 1)[1]
        self.state_lines = set(self.state.splitlines())

    def test_completed_and_owner_accepted_on_control(self):
        self.assertTrue(RECORD.is_file())
        self.assertIn("`PACKAGE_B = COMPLETED / OWNER-ACCEPTED`", self.text.split("## 1.", 1)[0])
        for line in ("PACKAGE_B = COMPLETED / OWNER-ACCEPTED", "PACKAGE_B_SEQUENCE = 3", f"PACKAGE_B_CONTROL = {CONTROL}",
                     "M-B9a = COMPLETED", "M-B9b = COMPLETED"):
            self.assertIn(line, self.state_lines)
        ids = section(self.text, "## 1. Identities", "## 2.")
        self.assertIn(f"| control | `{CONTROL}` (merge of PR #173", ids)
        self.assertIn(f"| control preservation deploy | `{PRESERVATION_RUN}`", ids)
        self.assertIn(f"`services/owner-memory-control/tools/mb9_operator.py`, SHA-256 `{OPERATOR}`", ids)

    def test_the_operator_pin_is_the_one_at_this_control(self):
        import mb9_operator as O

        self.assertEqual(hashlib.sha256(Path(O.__file__).read_bytes()).hexdigest(), OPERATOR)
        self.assertEqual(O.TOOL_PINS[O.VERIFIER], "e4aca11dcc925e8ebdb280c2d4a7da1cf4f9a8fcc4e2abb080e22d6917080e78")

    def test_b3_accepted_the_exact_incarnation_and_post9a(self):
        for line in ("WITNESS_STARTED = OWNER-ACCEPTED", f"WITNESS_INVOCATION_ID = {INVOCATION}",
                     f"WITNESS_MAIN_PID = {MAINPID}", f"POST9A_VERIFIED_SHA256 = {POST9A}", "WITNESS = RUNNING"):
            self.assertIn(line, self.state_lines)
        mb9a = flat(section(self.text, "## 4. M-B9a", "## 5."))
        self.assertIn(f"InvocationID `{INVOCATION}`, MainPID `{MAINPID}`", mb9a)
        self.assertIn(f"`POST9A_VERIFIED.json` SHA-256 `{POST9A}`", mb9a)
        self.assertIn("host **`W9_2_STARTED_UNINITIALIZED`**", mb9a)
        self.assertIn("**B3** accepted `WITNESS_STARTED` for exactly that InvocationID, MainPID and POST9A evidence",
                      mb9a)

    def test_genesis_committed_exactly_and_irreversibly(self):
        for line in ("WITNESS_GENESIS = COMMITTED / IRREVERSIBLE", f"WITNESS_GENESIS_DIGEST = {CANDIDATE}",
                     f"CHAIN_1_SHA256 = {CHAIN_1}", f"POST9B_VERIFIED_SHA256 = {POST9B}"):
            self.assertIn(line, self.state_lines)
        mb9b = flat(section(self.text, "## 6. M-B9b", "## 7."))
        for needed in ("`mb9b` was invoked once", "transcript `BOOTSTRAP_PASS`", "**`W9_5_GENESIS_COMMITTED_EXACT`**",
                       f"Digest `{CANDIDATE}` = the owner pin = the Package A candidate",
                       f"`chain/1.json` SHA-256 `{CHAIN_1}`; `witness.json` is byte-identical to it",
                       f"`POST9B_VERIFIED.json` SHA-256 `{POST9B}`", "LINEAGE_REVERSIBLE = NO",
                       "SECOND_WITNESS_GENESIS = FORBIDDEN", f"registryDigest `{REGISTRY}`", "ledgerSequence 1",
                       f"ledgerHead `{HEAD}`", "previousWitnessDigest null", "consumedAuthorizationId null",
                       "witnessKeyId `test-only.witness.dev-synthetic.b1b3d.1`", "updatedAt `2026-10-08T07:21:43Z`"):
            self.assertIn(needed, mb9b)

    def test_the_candidate_is_the_package_a_candidate_bound_by_the_package(self):
        package = PACKAGE_B.read_text(encoding="utf-8")
        self.assertIn("ac892dc2…65e4", package)          # the owner offline verifier's expected digest (record §9)
        self.assertIn(CANDIDATE, self.text.split("## 2.", 1)[0])

    def test_owner_offline_verification(self):
        self.assertIn("OWNER_OFFLINE_VERIFICATION = MB9B_OWNER_GENESIS_VERIFIED", self.state_lines)
        offline = flat(section(self.text, "## 7. Owner offline verification", "## 8."))
        for needed in ("**`MB9B_OWNER_GENESIS_VERIFIED`**", "All 15 checks true", "the K-WIT signature, which verifies",
                       "all 14 genesis-field checks true", f"`{ANCHOR}`", "`record1 = NOT CREATED`"):
            self.assertIn(needed, offline)

    def test_witness_denial_counts_equal_the_proofs_own_table(self):
        self.assertIn("P1B-9a = PASS (91 DENIED, 5 ALLOWED_BY_DESIGN, 0 ALLOWED)", self.state_lines)
        self.assertIn("P1B-9b = PASS (125 DENIED, 11 ALLOWED_BY_DESIGN, 0 ALLOWED)", self.state_lines)
        self.assertIn("**P1B-9a PASS: 107 lines, 91 `DENIED`, 5 `ALLOWED_BY_DESIGN`, 0 unexpected `ALLOWED`**",
                      flat(section(self.text, "## 4.", "## 5.")))
        self.assertIn("**P1B-9b PASS: 148 lines, 125 `DENIED`, 11 `ALLOWED_BY_DESIGN`, 0 unexpected `ALLOWED`**",
                      flat(section(self.text, "## 6.", "## 7.")))
        table = flat(section(PACKAGE_B.read_text(encoding="utf-8"), "## 11. Denial proofs", "## 12."))
        self.assertIn("| P1B-9a | 91 | 5 | 107 |", table)
        self.assertIn("| P1B-9b | 125 | 11 | 148 |", table)
        self.assertIn("P1B-6 and P1B-8 are out of their valid phase once witness state exists",
                      flat(section(self.text, "## 6.", "## 7.")))

    def test_b5_verbatim_hash_freeze_ended_and_nothing_further(self):
        quote = section(self.text, "## 8. B5 owner acceptance (verbatim)", "B5 ended the Package B deployment freeze")
        text = " ".join(line[2:] for line in quote.splitlines() if line.startswith("> "))
        self.assertEqual(hashlib.sha256((text + "\n").encode("utf-8")).hexdigest(), B5)
        self.assertIn(f"Owner acceptance text SHA-256 (the text plus one terminal LF): `{B5}`", quote)
        self.assertIn(f"B5_ACCEPTANCE_TEXT_SHA256 = {B5}", self.state_lines)
        import mb9_operator as O

        for line in O.PACKAGE_B_ACCEPTANCE_LINES:
            self.assertIn(" ".join(line.format(candidate=CANDIDATE, genesis=CHAIN_1, post9b=POST9B).split()), text)
        self.assertIn("This acceptance authorizes nothing further.", text)
        self.assertIn("The Package B deployment freeze ends now", text)
        self.assertIn("PACKAGE_B_FREEZE = ENDED", self.state_lines)
        self.assertIn("B5 ended the Package B deployment freeze and authorized nothing further",
                      flat(self.text.split("## 8.", 1)[1]))

    def test_evidence_seals(self):
        seal = flat(section(self.text, "## 9. Evidence seal", "## 10."))
        self.assertIn(f"(`SHA256SUMS`, 360 entries, every evidence file except the checkout copy and the seal files): "
                      f"`{SEAL}`. It covers the verbatim B5 file", seal)
        for prior in PRIOR_SEALS:
            self.assertIn(f"`{prior}`", seal)
        self.assertIn(f"PACKAGE_B_EVIDENCE_SEAL = {SEAL}", self.state_lines)

    def test_sequences_1_and_2_remain_historical(self):
        self.assertIn("PACKAGE_B_SEQUENCE_1 = STOPPED / HISTORICAL / NON-REUSABLE", self.state_lines)
        self.assertIn("PACKAGE_B_SEQUENCE_2 = STOPPED BEFORE M-B9a / HISTORICAL / NON-REUSABLE", self.state_lines)
        boundary = section(self.text, "## 11. Boundaries", "## 12.")
        self.assertIn(f"| Package B sequence 1 (control `{SEQ1}`) | STOPPED / HISTORICAL / NON-REUSABLE |", boundary)
        self.assertIn(f"| Package B sequence 2 (control `{SEQ2}`) | STOPPED BEFORE M-B9a / HISTORICAL / NON-REUSABLE |",
                      boundary)
        self.assertIn("nothing from sequences 1 or 2 was used as eligibility evidence",
                      flat(section(self.text, "## 3.", "## 4.")))

    def test_running_target_is_the_derived_pin_for_the_committed_running_phase(self):
        self.assertEqual(T.PHASE_TARGETS["W9_5_GENESIS_COMMITTED_EXACT"], T.RUNNING)
        running = T.TARGETS[T.RUNNING]
        self.assertEqual(running["result-set"], (192, RUNNING_FULL))
        self.assertEqual(running["dr5-block"], (153, RUNNING_BLOCK))
        self.assertEqual(running["predeploy-block"], (29, PRE_DEPLOY))
        target = section(self.text, "## 10. The first post-Package-B-freeze deploy", "## 11.")
        self.assertIn(f"| full result set | 192 | `{RUNNING_FULL}` | 167 `DENIED`, 0 `ALLOWED`, 0 `FAIL`, 1 "
                      "`DEFERRED_UNTIL_OBJECT_EXISTS`, 6 `UNOBSERVABLE_BY_DESIGN` |", target)
        self.assertIn(f"| DR-5 block | 153 | `{RUNNING_BLOCK}` | 139 `DENIED`, 0 `ALLOWED` |", target)
        self.assertIn(f"| pre-deploy block | 29 | `{PRE_DEPLOY}` | 28 `DENIED` |", target)
        self.assertIn("it is **not** a newly accepted global baseline", flat(target))
        for line in (f"RUNNING_DR5_TARGET_FULL_SHA256 = {RUNNING_FULL}", f"RUNNING_DR5_TARGET_BLOCK_SHA256 = {RUNNING_BLOCK}",
                     f"RUNNING_DR5_TARGET_PREDEPLOY_SHA256 = {PRE_DEPLOY}"):
            self.assertIn(line, self.state_lines)

    def test_first_post_freeze_deploy_order_and_not_yet_occurred(self):
        order = flat(section(self.text, "## 10. The first post-Package-B-freeze deploy", "## 11."))
        steps = ("this Package B completion-record PR, reviewed", "a separate owner merge authorization",
                 "the **first post-Package-B-freeze deploy**", "must establish `W9_5_GENESIS_COMMITTED_EXACT`",
                 "`mb9_operator.py dr5 <repo> W9_5_GENESIS_COMMITTED_EXACT <deploy-log>` must compare `EQUAL` to the "
                 "RUNNING target", "a separate owner acceptance of that first post-freeze deploy")
        positions = [order.index(step) for step in steps]
        self.assertEqual(positions, sorted(positions))
        for line in ("PACKAGE_B_COMPLETION_RECORD_MERGE = NOT AUTHORIZED",
                     "FIRST_POST_PACKAGE_B_FREEZE_DEPLOY = NOT YET OCCURRED"):
            self.assertIn(line, self.state_lines)
        self.assertIn("RUNNING_DR5_TARGET = DERIVED; NOT ACCEPTED AS A GLOBAL BASELINE", order)

    def test_later_stages_remain_unauthorized(self):
        for line in ("REGISTRY_EFFECTIVE = NO", "AUTHORITY_ACTIVE = NO", "authorityGranted = false", "SIGNER = INACTIVE",
                     "RECORD 1 = ABSENT", "ACCEPTANCE_ENVELOPE = NOT AUTHORIZED", "HELD = NOT AUTHORIZED",
                     "AUTHORITY ACTIVATION = NOT AUTHORIZED", "FIRST_MEMORY = NOT AUTHORIZED", "PROD = NOT AUTHORIZED",
                     "FRESHNESS=UNKNOWN", "LEDGER SEQUENCE = 1", f"LEDGER HEAD = {HEAD}"):
            self.assertIn(line, self.state_lines)
        for claim in FORBIDDEN:
            self.assertNotIn(claim, self.text, claim)
        boundary = flat(section(self.text, "## 11. Boundaries", "## 12."))
        self.assertIn("Record 1, the acceptance envelope, HELD, signer start and authority activation are later stages. "
                      "Each needs its own owner authorization; none follows from Package B completion.", boundary)
        self.assertIn("Tooling must not infer, choose, draft or write LILITH's First Memory", boundary)
        self.assertIn("the process **STOPS** there", boundary)

    def test_earlier_records_keep_their_history(self):
        self.assertIn("WITNESS_GENESIS = NOT COMMITTED", PACKAGE_B.read_text(encoding="utf-8"))
        self.assertIn("This record supersedes them on the Package B outcome only, from 2026-10-09", flat(self.text))

    def test_ledger_and_index(self):
        ledger = LEDGER.read_text(encoding="utf-8")
        self.assertIn("### 13.1ap Current-state reconciliation (Package B sequence 3: witness start and witness genesis "
                      "completed, 2026-10-09)", ledger)
        self.assertLess(ledger.index("### 13.1ao"), ledger.index("### 13.1ap"))
        self.assertLess(ledger.index("### 13.1ap"), ledger.index("### 13.2 Checks"))
        self.assertIn("FRESHNESS=UNKNOWN (§13.1ap) | UNASSIGNED |", ledger)   # the AUTH-02 cell
        ap = section(ledger, "### 13.1ap", "### 13.2 Checks")
        for needed in ("`PACKAGE_B = COMPLETED / OWNER-ACCEPTED`", CONTROL, INVOCATION, CANDIDATE, CHAIN_1,
                       "**The lineage is irreversible; no second witness genesis is permitted.**", "None has happened.",
                       "This pass contacted no live system.", "193 rows"):
            self.assertIn(needed, ap)
        for claim in FORBIDDEN:
            self.assertNotIn(claim, ap, claim)
        self.assertIn("Package B NOT OPEN", section(ledger, "### 13.1ao", "### 13.1ap"))   # history unchanged
        readme = (ARCH / "README.md").read_text(encoding="utf-8")
        self.assertIn("(slice-15b2b-b1b3e-mb9-package-b-completion.md)", readme)


if __name__ == "__main__":
    unittest.main()
