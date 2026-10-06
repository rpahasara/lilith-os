"""15B2b-B1b-3e: the M-B2 / GENERATE_K_WIT PR-2 continuity owner decision and preflight (TEST-ONLY).

Records:
- docs/architecture/slice-15b2b-b1b3e-mb2-pr2-continuity-owner-decision.md
- docs/architecture/slice-15b2b-b1b3e-mb2-kwit-preflight.md

Pins MB2_PR2_CONTINUITY = OWNER_ATTENDED_EVENT_BOUNDED_SINGLE_ATTEMPT: no TTL,
event- and sequence-bounded PR-2, PR-2 last before the go, the deployment
freeze, every terminator, one invocation per go, refusal consumption, the
passphrase prohibition, the exact go bindings, public-only off-host recording,
known and unknown burn handling, no same-sequence replacement, the
K_WIT_CUSTODIED terminal state with no authority, and that every later stage
stays unauthorized. It also checks that the repository facts the decision
relies on still hold in the keygen and the sequencer.
"""

from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
ARCH = ROOT / "docs/architecture"
DECISION = ARCH / "slice-15b2b-b1b3e-mb2-pr2-continuity-owner-decision.md"
PREFLIGHT = ARCH / "slice-15b2b-b1b3e-mb2-kwit-preflight.md"
KEYGEN = ROOT / "services/authority-dev/ceremony/lilith_authority_keygen_dev.py"
SEQUENCING = ROOT / "services/owner-memory-control/lilith_owner_memory/pr1b_sequencing.py"

CLASSIFICATION = "MB2_PR2_CONTINUITY = OWNER_ATTENDED_EVENT_BOUNDED_SINGLE_ATTEMPT"
E21 = "cb36daf176d813359b8bd0fe6361f549fd3334a52d0cd1f85cc5247cb26592cf"
HOST = "lilith-dev-01"
KEY_ID = "test-only.witness.dev-synthetic.b1b3d.1"
COMMAND = "lilith-authority-keygen-dev witness"
CRED_PATH = "/etc/lilith-recovery-witness/credentials/lilith-recovery-witness.witness.cred"

sys.path.insert(0, str(ROOT / "services/owner-memory-control"))
from lilith_owner_memory import burned_identities as BI  # noqa: E402


def section(text: str, start: str, end: str | None = None) -> str:
    body = text.split(start, 1)[1]
    return body.split(end, 1)[0] if end else body


def flat(text: str) -> str:
    """Join lines, dropping only the leading blockquote marker (placeholders keep `<…>`)."""
    return " ".join(re.sub(r"^\s*>", " ", text, flags=re.MULTILINE).split())


class DecisionTests(unittest.TestCase):
    def setUp(self):
        self.text = DECISION.read_text(encoding="utf-8")
        self.state = section(self.text, "## 9. State")
        self.verbatim = flat(section(self.text, "## 1. Owner decision (verbatim)", "## 2."))
        self.semantics = section(self.text, "## 2. Semantics recorded", "## 3.")

    def test_exact_classification_and_verbatim(self):
        self.assertIn(CLASSIFICATION, self.state)
        self.assertTrue(self.verbatim.startswith(f"I adopt `{CLASSIFICATION}`."))
        self.assertTrue(self.verbatim.endswith("`FRESHNESS=UNKNOWN` remains unchanged."))
        self.assertEqual(len(re.findall(r"^- \*\*`MB2_PR2_CONTINUITY = ", self.text, re.MULTILINE)), 1)

    def test_no_wall_clock_ttl_event_and_sequence_bounded(self):
        self.assertIn("There is no wall-clock TTL; validity is event-bounded and sequence-bounded.", self.verbatim)
        self.assertIn("a fresh PR-2 result is usable only inside one explicitly owner-authorized, owner-attended "
                      "M-B2 sequence", self.verbatim)
        for line in ("FRESH PR-2 USABLE ONLY INSIDE ONE OWNER-AUTHORIZED, OWNER-ATTENDED M-B2 SEQUENCE",
                     "NO WALL-CLOCK TTL; VALIDITY EVENT-BOUNDED AND SEQUENCE-BOUNDED"):
            self.assertIn(line, self.state)
        self.assertNotRegex(self.state, r"\b\d+\s*(minutes?|hours?|days?)\b")

    def test_pr2_last_before_go(self):
        for line in ("FRESH DR-5 AND ALL OTHER PREREQUISITES FIRST; FRESH PR-2 LAST, BEFORE THE GO",
                     "BETWEEN PR-2 PASS AND KEYGEN: ONLY READ-ONLY FINAL GATE CHECKS AND THE OWNER GO"):
            self.assertIn(line, self.state)
        self.assertIn("no unrelated work or relevant mutation may intervene", self.verbatim)

    def test_deployment_freeze(self):
        self.assertIn("DEPLOYMENT FREEZE FROM FRESH DR-5 UNTIL M-B2 COMPLETES OR THE SEQUENCE ABORTS", self.state)
        self.assertIn("merges to `main`, workflow reruns capable of deployment, manual deployments, or other actions "
                      "capable of changing relevant DEV deployment state are frozen until M-B2 completes or the "
                      "sequence aborts", self.verbatim)

    def test_all_invalidation_triggers(self):
        table = section(self.semantics, "**Sequence terminators.**", "**The go.**")
        expected = {
            "T-1": "a new or unreviewed deployment",
            "T-2": "any PR-2-scope topology, snapshot, image, backup, disk, replication, sync or "
                   "owner-freshness-topology change",
            "T-3": "a reboot",
            "T-4": "broker replacement",
            "T-5": "an IAM or relevant host-topology change",
            "T-6": "a K-ACT CURRENT change",
            "T-7": "an installed release or keygen change",
            "T-8": "the witness credential already present",
            "T-9": "the owner register no longer `KNOWN_EMPTY`",
            "T-10": "an applicable B-5 stop or invalidator",
            "T-11": "an explicit owner pause, suspension or end",
            "T-12": "any uncertainty about the required current evidence",
        }
        rows = [line for line in table.splitlines() if re.match(r"^\| T-\d+ \|", line)]
        self.assertEqual(len(rows), len(expected))
        for tid, wording in expected.items():
            self.assertIn(f"| {tid} | {wording} |", table)
        self.assertIn("**or becomes uncertain**", flat(table))
        self.assertIn("TERMINATORS T-1 … T-12 END THE SEQUENCE; FRESH PR-2 THEN NON-REUSABLE", self.state)

    def test_one_invocation_per_go_and_refusal_consumes(self):
        for line in (f"M-B2 GO ONE-ATTEMPT: EXACTLY ONE INVOCATION OF {COMMAND} ON {HOST}",
                     "REFUSED / FAILED / UNEXPECTED PROMPT / STOP CONSUMES THE GO AND ENDS THE SEQUENCE",
                     "NEW ATTEMPT = NEW SEQUENCE + FRESH PR-2 + NEW OWNER GO"):
            self.assertIn(line, self.state)
        self.assertIn("even if no private K-WIT candidate was created", self.verbatim)

    def test_k_root_passphrase_prohibited(self):
        self.assertIn("K-ROOT PASSPHRASE NOT REQUESTED OR ENTERED; ANY PASSPHRASE PROMPT IS A STOP", self.state)
        self.assertIn("The K-ROOT passphrase must not be requested or entered during M-B2. Any passphrase prompt is "
                      "a STOP.", self.verbatim)

    def test_exact_bindings_in_state_and_verbatim(self):
        self.assertIn(f"E-21 publicKeySha256={E21}", self.state)
        self.assertIn(f"KEYID {KEY_ID}", self.state)
        self.assertIn(f"CREDENTIAL PATH {CRED_PATH}", self.state)
        for value in (f"publicKeySha256={E21}", f"host `{HOST}`", f"keyId `{KEY_ID}`", f"command `{COMMAND}`",
                      f"`{CRED_PATH}`", "exactly one invocation", "DEV_SYNTHETIC scope",
                      "current accepted control commit", "the successful fresh PR-2 window"):
            self.assertIn(value, self.verbatim)

    def test_go_template_binds_everything(self):
        template = flat(section(self.text, "## 6. M-B2 owner-go template", "## 7."))
        self.assertIn("TEMPLATE ONLY; not given", template)
        for value in ("Scope: DEV_SYNTHETIC only.", "Control commit: `<CONTROL_SHA>`",
                      "Fresh PR-2 window: `<PR2_WINDOW_START>`–`<PR2_WINDOW_END>`, result PASS.",
                      f"`publicKeySha256={E21}`", f"host `{HOST}`", f"`{COMMAND}`", f"`{KEY_ID}`", f"`{CRED_PATH}`",
                      "exactly one invocation",
                      "The K-ROOT passphrase must not be requested or entered. Any passphrase prompt is a STOP.",
                      "Any `REFUSED`, `FAILED`, unexpected prompt, or other STOP consumes this go and ends the "
                      "sequence",
                      "There is no retry in this sequence.",
                      "This authorization does not authorize M-B3 / `SIGN_REGISTRY_V1`, registry/genesis mutation, "
                      "record 1, First Memory, PROD activity, or any later bootstrap stage."):
            self.assertIn(value, template)

    def test_public_only_off_host_recording(self):
        self.assertIn("PUBLIC K-WIT FINGERPRINT RECORDED IMMEDIATELY OFF-HOST IN THE OWNER EXTERNAL M-B2 EVIDENCE "
                      "SET ON THE LAPTOP; PUBLIC ONLY", self.state)
        self.assertIn("No private K-WIT material may enter that evidence set.", self.verbatim)

    def test_known_burn_and_unknown_tombstone(self):
        self.assertIn("KNOWN BURNED REAL K-WIT: RECORDED; CANONICAL BURNED SET UPDATED AND REVIEWED BEFORE ANY "
                      "REPLACEMENT", self.state)
        self.assertIn("UNKNOWN_REAL_KWIT_BURN: APPEND-ONLY TOMBSTONE; NO INVENTED FINGERPRINT", self.state)
        burns = section(self.text, "## 7. Abort and burn handling", "## 8.")
        self.assertIn("**`UNKNOWN_REAL_KWIT_BURN`**", burns)
        for field in ("control commit;", "host (`lilith-dev-01`);", f"keyId (`{KEY_ID}`);", "timestamp;",
                      "failure window", "blob SHA-256, **only if a blob exists and can be read safely**",
                      "fingerprint: `UNKNOWN`. It is never filled in afterwards."):
            self.assertIn(field, burns)
        self.assertIn("**never invent or infer a fingerprint**", burns)
        self.assertIn("The M-B2 go does not authorize its destruction.", flat(burns))

    def test_no_same_sequence_replacement(self):
        self.assertIn("NO REPLACEMENT K-WIT UNDER THE SAME GO OR SEQUENCE", self.state)
        self.assertIn("No replacement K-WIT may be generated under the same go or sequence. Replacement requires a "
                      "new owner-authorized sequence.", self.verbatim)

    def test_k_wit_custodied_confers_no_authority(self):
        for line in ("SUCCESSFUL TERMINAL STATE: K_WIT_CUSTODIED", "K_WIT_CUSTODIED CONFERS NO SIGNING OR REGISTRY "
                                                                  "AUTHORITY"):
            self.assertIn(line, self.state)
        terminal = section(self.text, "## 8. Terminal state", "## 9.")
        self.assertIn("K_WIT_CUSTODIED != registry / signing authority", terminal)

    def test_gaps_resolved(self):
        self.assertIn("M2-A … M2-F RESOLVED", self.state)
        gaps = section(self.text, "## 3. Gap reconciliation", "## 4.")
        for gap in ("M2-A", "M2-B", "M2-C", "M2-D", "M2-E", "M2-F"):
            row = next(line for line in gaps.splitlines() if line.startswith(f"| {gap} "))
            self.assertIn("**RESOLVED**", row)

    def test_runbook_order(self):
        runbook = section(self.text, "## 5. Future M-B2 runbook", "## 6.")
        self.assertIn("NOT executed, NOT authorized", runbook)
        order = ["authorizes **one M-B2 sequence**", "**fresh DR-5 through the latest deployment**",
                 "**deployment freeze ACTIVE**", "fresh read-only **Replica A** read",
                 "**owner register = `KNOWN_EMPTY`**", "**re-prove K-ACT CURRENT and host / install preservation**",
                 "**fresh PR-2** as the final topology / rollback-currentness revalidation",
                 "**required read-only final gate checks only**", "**separate one-attempt M-B2 go**",
                 "**exactly one invocation**", "**capture the public publication / fingerprint**",
                 "**verify the blob against the publication**", "**verify distinct from K-ACT and E-21 K-ROOT**",
                 "**verify not a burned identity**", "**secret scan / no private-output leakage**",
                 "**immediately record the public fingerprint off-host**", "`status --expect P1B-2",
                 "**`K_WIT_CUSTODIED`**", "**the sequence completes**"]
        positions = [runbook.index(step) for step in order]
        self.assertEqual(positions, sorted(positions))
        self.assertIn("abort, and burn handling under §7", runbook)

    def test_everything_later_unauthorized(self):
        for line in ("RUNBOOK DOCUMENTED; NOT AUTHORIZED; NOT EXECUTED", "M-B2 GO TEMPLATE ONLY; NOT GIVEN",
                     "M-B2 / GENERATE_K_WIT = NOT AUTHORIZED", "M-B3 / SIGN_REGISTRY_V1 = NOT AUTHORIZED",
                     "REGISTRY / GENESIS = NOT AUTHORIZED", "RECORD 1 = NOT AUTHORIZED",
                     "FIRST MEMORY = NOT AUTHORIZED", "PROD = NOT AUTHORIZED", "FRESHNESS=UNKNOWN",
                     "NO LIVE SYSTEM CONTACTED"):
            self.assertIn(line, self.state)
        for text in (self.text, PREFLIGHT.read_text(encoding="utf-8")):
            for claim in ("M-B2 / GENERATE_K_WIT = AUTHORIZED", "M-B3 / SIGN_REGISTRY_V1 = AUTHORIZED",
                          "REGISTRY / GENESIS = AUTHORIZED", "RECORD 1 = AUTHORIZED", "FIRST MEMORY = AUTHORIZED",
                          "PROD = AUTHORIZED", "FRESHNESS=CURRENT", "M-B2 GO GIVEN"):
                self.assertNotIn(claim, text)

    def test_no_private_paths(self):
        for text in (self.text, PREFLIGHT.read_text(encoding="utf-8")):
            self.assertNotRegex(text, r"[A-Za-z]:\\Users\\|/root/|/home/|/data/data/")


class PreflightTests(unittest.TestCase):
    def setUp(self):
        self.text = PREFLIGHT.read_text(encoding="utf-8")
        self.state = section(self.text, "## 5. Current classification")

    def test_pre_decision_kept_current_ready(self):
        for line in ("PRE-DECISION: NOT_READY_FOR_OWNER_MB2_DECISION", "CURRENT: READY_FOR_OWNER_MB2_DECISION",
                     f"M2-A … M2-F RESOLVED BY {CLASSIFICATION}",
                     "NO RUNTIME, SEQUENCER, KEYGEN, INSTALLER, WORKFLOW OR INFRASTRUCTURE CHANGE REQUIRED",
                     "M-B2 / GENERATE_K_WIT = NOT AUTHORIZED", "M-B3 / SIGN_REGISTRY_V1 = NOT AUTHORIZED",
                     "FIRST MEMORY = NOT AUTHORIZED", "FRESHNESS=UNKNOWN"):
            self.assertIn(line, self.state)
        self.assertIn("**It authorizes nothing.**", self.text)
        gaps = section(self.text, "## 4. Pre-decision gaps", "## 5.")
        for gap in ("M2-A", "M2-B", "M2-C", "M2-D", "M2-E", "M2-F"):
            self.assertIn(f"| {gap} |", gaps)


class RepositoryFactsTests(unittest.TestCase):
    """The decision relies on these; a change here must be re-reviewed."""

    def test_keygen_fixed_witness_form(self):
        code = KEYGEN.read_text(encoding="utf-8")
        self.assertIn(f'WITNESS_KEY_ID = "{KEY_ID}"', code)
        self.assertIn('WITNESS_BLOB_NAME = "lilith-recovery-witness.witness.cred"', code)
        self.assertIn('WITNESS_PARENT = "/etc/lilith-recovery-witness"', code)
        self.assertIn(f'DEV_HOSTNAME = "{HOST}"', code)
        self.assertIn('raise Refused("WITNESS_CREDENTIAL_ALREADY_PRESENT")', code)
        self.assertIn("    lilith-authority-keygen-dev witness\n", code)
        # A refusal happens in preflight, before the ceremony generates any key.
        main = section(code, "def main(", 'if __name__ == "__main__":')
        self.assertLess(main.index("witness_preflight(host"), main.index("witness_ceremony(host"))
        self.assertLess(main.index("except Refused"), main.index("witness_ceremony(host"))

    def test_sequencer_m_b2_step(self):
        # Read as text: importing the sequencer needs core-api and rfc8785.
        code = SEQUENCING.read_text(encoding="utf-8")
        step = section(code, 'StepV1("GENERATE_K_WIT",', 'StepV1("SIGN_REGISTRY_V1",')
        self.assertTrue(step.startswith(' "K_ROOT_GENERATED", "K_WIT_CUSTODIED", "M-B2", REQUIRED_UNKNOWN_BLOCK,'))
        for evidence in ("pr2RevalidatedImmediatelyBefore", "kWitPublicationCaptured", "kWitFingerprintRecordedOffHost",
                         "secretScansClean", "currentKActUnchanged", "kWitDistinctFromKActAndKRoot", "PONR_CUSTODY"):
            self.assertIn(evidence, step)
        self.assertIn('StepV1("SIGN_REGISTRY_V1", "K_WIT_CUSTODIED", "REGISTRY_SIGNED", "M-B3"', code)

    def test_e21_not_burned(self):
        every = BI.BURNED_PUBLIC_KEY_SHA256 | BI.BURNED_REGISTRY_DIGESTS | BI.BURNED_GENESIS_WITNESS_DIGESTS
        self.assertEqual(BI.CANONICAL_COUNT, 20)
        self.assertNotIn(E21, every)


if __name__ == "__main__":
    unittest.main()
