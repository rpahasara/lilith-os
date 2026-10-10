"""15B2b-B1b-3e: Package C sequence 4 completion record (TEST-ONLY, stdlib).

Record: docs/architecture/slice-15b2b-b1b3e-pkgc-completion.md.

Pins: sequence 4 COMPLETED / OWNER-ACCEPTED on control 896716e with the operator at this control; record 1 on
Replica A and B (AUTHENTIC + CURRENT) and envelope 1 on copies A and B (ACCEPTANCE_COMPLETE); the owner acts, gates
and acquisitions; the verbatim C5 (its SHA-256 recomputed from the quoted text, every canonical C5 line present with
the bound values) ending the freeze and authorizing nothing further; the historical first `record` invocation;
sequences 1 … 3 historical; the first post-C5 deploy (running-witness target, not yet occurred); and HELD, the
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
RECORD = ARCH / "slice-15b2b-b1b3e-pkgc-completion.md"
DESIGN = ARCH / "slice-15b2b-b1b3e-pkgc-record1-envelope-package.md"
LEDGER = ARCH / "current-architecture-acceptance-ledger-v0.1.md"
TOOLS = ROOT / "services/owner-memory-control/tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import mb9_dr5_target as T  # noqa: E402
import pkgc_operator as P  # noqa: E402

CONTROL = "896716e8c7bd705bcbe6e25f154afff4ae1d4dba"
SEQUENCE = "e6b7a3334cda25efe9259741cda1b3ae"
OPERATOR = "c5e5a5cc265f48721715e43b4bec40ccbaf865c4149d095c86c853331c2767c0"
FRESHNESS_TOOL = "fd7abe2aa5e5efae41b87553efe8fe8058b437748accf866c2fa5ee71c8a7c27"
BINDING = "bd1c35e79c3833710196f51186741160e81c0532632f5050fd5134fc0ca70793"
RECORD_1 = "77752db11d80eef50eaeaa8b931d65a489bb919f9e864584fbf8d00746e2cec6"
ENVELOPE_1 = "95da36cd6edd49c2bae244611cc429a174dee72ec2454c4f73c57a83bfcb0f0c"
GENESIS = "ac892dc2b14ca7db108400258abfcf2320ff498f2a674058058e16a8a6fb65e4"
C4B_BLOCK = "7c59fe6833f1eb152f11648533d30681577909fd0fe10d714a22a4a7dbf5e7b1"
C5_GATE = "962aa9579a51ce607661a084017e54fae2ae0584cc019be5d3b41beba7f6b18e"
C5_TEXT = "6161ffcd438bef1f7e030cc94569655747cd44327bb81604fdfcefd2d81060dd"
C5_JSON = "16afa08a0e5dae54d1a9dbf0cceb4857ca6bf34284515bd6a97a6d69ca4cf755"
SEAL = "f702128b36b2fac8a3b78f4f232c55e5ec86e061cb4aa59a0a9ffec245443470"
PRIOR_SEAL = "709ab556a9a9f219e0ee7a9bde7f66ff7fc6715275dbd9a7b678e19baba31871"
INVOCATION = "8af12bd64d024d0eba56bbcedbc534a6"
STORE_B_VIEW = "5cb0bc77318a91a02d8890ac0ad636960d8432a387e055ba13f7eebe05ed56d1"
ENDED = ("6dff580d71f521d0c566c6af159e7b93", "f360367e05b44a6208652f701f4491fc", "03553f6a31bdf32938fb265bcc33d64f")
GATES = {"01-C2": "3a87fd726a2d6cb1e114aabeb4b1a1fb486e54db1a2af3e7d72eecef6b36d0fe",
         "02-C3": "6ad845b6f5860ef9e1ed7df11b5a35c95cb91d9bda6ee2bcafc8c1a7f726bc0e",
         "03-C4A": "fc0a29a017fde637376fb2b72d502c126215a3b446855f4f373e6ddcc5aef6e2",
         "04-C4B": "8982d7f0fb1c3a20e28adddb8b48f7b5cd6f010dee818443f7e3cd9cdcf5f238",
         "05-C5": C5_GATE}
FORBIDDEN = ("REGISTRY_EFFECTIVE = YES", "AUTHORITY_ACTIVE = YES", "authorityGranted = true", "SIGNER = ACTIVE",
             "SIGNER = STARTED", "HELD = WRITTEN", "HELD = AUTHORIZED", "HELD = PRESENT", "AUTHORITY ACTIVATION = AUTHORIZED",
             "FIRST_MEMORY = AUTHORIZED", "FIRST_MEMORY_READY = REACHED", "PROD = AUTHORIZED", "RECORD 1 = ABSENT",
             "FIRST_POST_C5_DEPLOY = EQUAL", "FIRST_POST_C5_DEPLOY = OCCURRED", "PACKAGE_C_FREEZE = IN FORCE")


def flat(text: str) -> str:
    return " ".join(re.sub(r"^\s*>", " ", text, flags=re.MULTILINE).split())


def section(text: str, start: str, end: str) -> str:
    return text.split(start, 1)[1].split(end, 1)[0]


class PackageCCompletionRecordTests(unittest.TestCase):
    def setUp(self):
        self.text = RECORD.read_text(encoding="utf-8")
        self.state_lines = set(self.text.split("## 11. State", 1)[1].splitlines())

    def test_completed_and_owner_accepted_on_control(self):
        self.assertIn("`PACKAGE_C = COMPLETED / OWNER-ACCEPTED` (`PC5_PACKAGE_C_ACCEPTED`)", self.text.split("## 1.", 1)[0])
        self.assertEqual(P.PC5, "PC5_PACKAGE_C_ACCEPTED")
        for line in ("PACKAGE_C = COMPLETED / OWNER-ACCEPTED", f"PACKAGE_C_STATE = {P.PC5}",
                     f"PACKAGE_C_SEQUENCE = {SEQUENCE}", f"PACKAGE_C_CONTROL = {CONTROL}", f"BINDING_SHA256 = {BINDING}"):
            self.assertIn(line, self.state_lines)
        ids = section(self.text, "## 1. Identities", "## 2.")
        self.assertIn(f"| control | `{CONTROL}` (merge of PR #178", ids)
        self.assertIn(f"`services/owner-memory-control/tools/pkgc_operator.py`, SHA-256 `{OPERATOR}`", ids)
        self.assertIn(f"SHA-256 `{FRESHNESS_TOOL}` (unchanged", ids)

    def test_the_operator_pin_is_the_one_at_this_control(self):
        self.assertEqual(hashlib.sha256(Path(P.__file__).read_bytes()).hexdigest(), OPERATOR)
        self.assertEqual(P.ACCEPTED_PINS.witness_invocation_id, INVOCATION)
        self.assertIn(INVOCATION, section(self.text, "## 1. Identities", "## 2."))

    def test_record_1_on_both_replicas_current(self):
        for line in (f"RECORD_1_DIGEST = {RECORD_1}", "RECORD_1 = PRESENT ON REPLICA A AND REPLICA B",
                     "RECORD_1_FRESHNESS = AUTHENTIC + CURRENT"):
            self.assertIn(line, self.state_lines)
        rec = flat(section(self.text, "## 4. Record 1", "## 5."))
        for needed in ("`RECORD_APPENDED`, replication `PEER_PENDING`", "`REPLICAS_IDENTICAL`",
                       "`FRESHNESS=AUTHENTIC:CURRENT`", "laptop freshness **AUTHENTIC + CURRENT**",
                       f"**Record 1 digest: `{RECORD_1}`**", f"bound to the witness genesis `{GENESIS[:8]}…"):
            self.assertIn(needed, rec)

    def test_envelope_1_on_both_copies_complete(self):
        for line in (f"ENVELOPE_1_DIGEST = {ENVELOPE_1}", "ENVELOPE_1 = PRESENT ON COPIES A AND B",
                     "ACCEPTANCE = ACCEPTANCE_COMPLETE", f"C4B_RESULT_BLOCK_SHA256 = {C4B_BLOCK}"):
            self.assertIn(line, self.state_lines)
        env = flat(section(self.text, "## 5. Acceptance envelope 1", "## 6."))
        for needed in ("Acceptance `ACCEPTANCE_PARTIAL`", "`PKGC_C4B_ELIGIBLE`", "copy A exact, copy B absent",
                       "`COPIES_IDENTICAL`", "`ACCEPTANCE=ACCEPTANCE_COMPLETE`", f"result block `{C4B_BLOCK}` (24 lines)",
                       f"`store-b-1` `{STORE_B_VIEW}`", "envelope bytes identical on copies A and B",
                       f"**Envelope 1 digest: `{ENVELOPE_1}`**"):
            self.assertIn(needed, env)

    def test_owner_acts_gates_and_acquisitions(self):
        acts = flat(section(self.text, "## 3. The owner acts of sequence 4", "## 4."))
        for name, sha in GATES.items():
            self.assertIn(f"`{name}` `{sha}`", acts)
        for step in ("APPEND_RECORD_1_REPLICA_A", "APPEND_RECORD_1_REPLICA_B", "APPEND_ENVELOPE_1_COPY_A",
                     "APPEND_ENVELOPE_1_COPY_B"):
            self.assertIn(f"`{step}`", acts)
            self.assertIn(step, P.BOOTSTRAP_STEP.values())
        for state in (P.PC1B, P.PC2, P.PC3, P.PC4AP, P.PC4B, P.PC5):
            self.assertIn(f"`{state}`", acts)
        self.assertEqual(len(re.findall(r"\| `0[1-6]-[0-9a-f]{32}` \|", acts)), 6)
        self.assertIn("events `[]` and route `CONTINUE`", acts)

    def test_c5_verbatim_hash_canonical_lines_and_nothing_further(self):
        quote = section(self.text, "## 7. C5 owner acceptance (verbatim)", "`pkgc_operator.py record")
        text = " ".join(line[2:] for line in quote.splitlines() if line.startswith("> "))
        self.assertEqual(hashlib.sha256(text.encode("utf-8")).hexdigest(), C5_TEXT)
        P.check_text(text, P.C5_LINES, record=RECORD_1, envelope=ENVELOPE_1, binding=BINDING)
        self.assertIn(f"`{C5_TEXT}`", quote)
        for line in (f"C5_ACCEPTANCE_TEXT_SHA256 = {C5_TEXT}", f"C5_ACCEPTANCE_JSON_SHA256 = {C5_JSON}",
                     f"C5_GATE_SHA256 = {C5_GATE}", "PACKAGE_C_FREEZE = ENDED"):
            self.assertIn(line, self.state_lines)
        after = flat(self.text.split("## 7.", 1)[1].split("## 8.", 1)[0])
        self.assertIn(f"wrote only `C5_ACCEPTANCE.json`, SHA-256 `{C5_JSON}`", after)
        self.assertIn("C5 ended the Package C freeze and authorized nothing further", after)
        self.assertIn("The second invocation, with the file path, is the accepted C5 event.", after)
        self.assertIn("wrote nothing. C5 has no attempt marker, so nothing was consumed.", after)

    def test_earlier_sequences_historical(self):
        ended = section(self.text, "## 2. Earlier sequences", "## 3.")
        for seq in ENDED:
            self.assertIn(f"`{seq}`", ended)
        self.assertIn("PACKAGE_C_SEQUENCES_1_2_3 = ENDED / HISTORICAL / NON-REUSABLE", self.state_lines)

    def test_first_post_c5_deploy_running_target_not_yet_occurred(self):
        self.assertEqual(T.PHASE_TARGETS["W9_5_GENESIS_COMMITTED_EXACT"], T.RUNNING)
        running = T.TARGETS[T.RUNNING]
        deploy = flat(section(self.text, "## 8. The first post-C5 deploy", "## 9."))
        self.assertIn(f"192 lines `{running['result-set'][1]}`", deploy)
        self.assertIn(f"DR-5 block `{running['dr5-block'][1]}`", deploy)
        self.assertIn(f"pre-deploy `{running['predeploy-block'][1]}`", deploy)
        self.assertEqual(running["result-set"][0], 192)
        for needed in ("`W9_5_GENESIS_COMMITTED_EXACT` on the committed genesis", GENESIS,
                       "Package C adds no DR-5 line", "is a STOP and enters revalidation",
                       "must not intentionally reboot the host or restart the witness or broker",
                       "FIRST_POST_C5_DEPLOY = NOT YET OCCURRED"):
            self.assertIn(needed, deploy)
        self.assertIn("Record 1 and the envelopes are not host-observable, so Package C adds no DR-5",
                      flat(DESIGN.read_text(encoding="utf-8")))

    def test_evidence_seals(self):
        seal = flat(section(self.text, "## 9. Evidence seal", "## 10."))
        self.assertIn(f"(`SHA256SUMS`, 195 entries, every evidence file except the seal files): `{SEAL}`", seal)
        self.assertIn(f"`{PRIOR_SEAL}` (184 entries)", seal)
        self.assertIn(f"PACKAGE_C_EVIDENCE_SEAL = {SEAL}", self.state_lines)

    def test_authority_boundary_unchanged(self):
        self.assertEqual(P.AUTHORITY_BOUNDARY, {"REGISTRY_EFFECTIVE": "NO", "AUTHORITY_ACTIVE": "NO",
                                                "authorityGranted": False, "signer": "INACTIVE",
                                                "HELD": "NOT AUTHORIZED", "FIRST_MEMORY": "NOT AUTHORIZED",
                                                "PROD": "NOT AUTHORIZED"})
        for line in ("REGISTRY_EFFECTIVE = NO", "AUTHORITY_ACTIVE = NO", "authorityGranted = false", "SIGNER = INACTIVE",
                     "HELD = NOT WRITTEN", "HELD = NOT AUTHORIZED", "AUTHORITY ACTIVATION = NOT AUTHORIZED",
                     "FIRST_MEMORY = NOT AUTHORIZED", "FIRST_MEMORY_READY = NOT REACHED", "PROD = NOT AUTHORIZED",
                     f"WITNESS_GENESIS_DIGEST = {GENESIS}"):
            self.assertIn(line, self.state_lines)
        for claim in FORBIDDEN:
            self.assertNotIn(claim, self.text, claim)
        boundary = flat(section(self.text, "## 10. Boundaries", "## 11."))
        self.assertIn("Each needs its own owner authorization; none follows from Package C completion.", boundary)
        self.assertIn("Tooling must not infer, choose, draft or write LILITH's First Memory", boundary)
        self.assertIn("the process **STOPS** there", boundary)

    def test_design_record_keeps_its_history(self):
        design = DESIGN.read_text(encoding="utf-8")
        self.assertIn("RECORD 1 = ABSENT", design)
        self.assertIn("This record supersedes it on the Package C outcome only, from 2026-10-10", flat(self.text))

    def test_ledger_and_index(self):
        ledger = LEDGER.read_text(encoding="utf-8")
        self.assertIn("### 13.1ar Current-state reconciliation (Package C sequence 4: record 1 and acceptance envelope 1 "
                      "completed, 2026-10-10)", ledger)
        self.assertLess(ledger.index("### 13.1aq"), ledger.index("### 13.1ar"))
        self.assertLess(ledger.index("### 13.1ar"), ledger.index("### 13.2 Checks"))
        self.assertIn("NOT AUTHORIZED (§13.1ar) | UNASSIGNED |", ledger)   # the AUTH-02 cell
        ar = section(ledger, "### 13.1ar", "### 13.2 Checks")
        for needed in ("`PACKAGE_C = COMPLETED / OWNER-ACCEPTED`", SEQUENCE, RECORD_1, ENVELOPE_1, "AUTHENTIC + CURRENT",
                       "`ACCEPTANCE_COMPLETE`", "None has happened.", "This pass contacted no live system.", "193 rows"):
            self.assertIn(needed, ar)
        for claim in FORBIDDEN:
            self.assertNotIn(claim, ar, claim)
        readme = (ARCH / "README.md").read_text(encoding="utf-8")
        self.assertIn("(slice-15b2b-b1b3e-pkgc-completion.md)", readme)


if __name__ == "__main__":
    unittest.main()
