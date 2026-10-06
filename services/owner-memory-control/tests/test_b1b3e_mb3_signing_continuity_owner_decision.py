"""15B2b-B1b-3e: the M-B3 / SIGN_REGISTRY_V1 signing continuity owner decision and ceremony package records (TEST-ONLY).

Records:
- docs/architecture/slice-15b2b-b1b3e-mb3-signing-continuity-owner-decision.md
- docs/architecture/slice-15b2b-b1b3e-mb3-registry-ceremony-package.md

Pins MB3_SIGNING_CONTINUITY = OWNER_ATTENDED_EVENT_BOUNDED_SINGLE_ATTEMPT_OFFHOST:
preparation sequence != go, the fresh gates, no PR-2 / full DR-5 solely for
M-B3, the terminators, S25-only signing, the frozen parameter rules, PREPARE
without K-ROOT, the non-authoritative manifest, the go bindings, one attempt,
burn cases A-E, the C-5 resolution, double verification, K-WIT as a
distinctness input only, REGISTRY_SIGNED with separate owner acceptance, and
that everything later stays unauthorized. It also checks the repository facts
the decision relies on (unchanged signer, sequencer step, release file set),
the phone-script pin, and the minimal pointers.
"""

from __future__ import annotations

import hashlib
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
ARCH = ROOT / "docs/architecture"
DECISION = ARCH / "slice-15b2b-b1b3e-mb3-signing-continuity-owner-decision.md"
PACKAGE = ARCH / "slice-15b2b-b1b3e-mb3-registry-ceremony-package.md"
OWNER_TOOL = ROOT / "services/authority-dev/ceremony/lilith_authority_owner_dev.py"
SEQUENCING = ROOT / "services/owner-memory-control/lilith_owner_memory/pr1b_sequencing.py"
RELEASE_SET = ROOT / "services/authority-dev/release_file_set.py"
PHONE_SCRIPT = ROOT / "services/owner-memory-control/tools/mb3_phone_ceremony.py"
CLASSIFICATION = "MB3_SIGNING_CONTINUITY = OWNER_ATTENDED_EVENT_BOUNDED_SINGLE_ATTEMPT_OFFHOST"
E21 = "cb36daf176d813359b8bd0fe6361f549fd3334a52d0cd1f85cc5247cb26592cf"
KWIT = "5d778701def439b6c896392750c12685c26b67edfc908bed1a80f02eab0d0bdf"
KACT = "dd13a1fb302375a4e7ec81131a72920e23e365e06a0b6dc9bb7ab124dadc01ed"
SCRIPT_PIN = "db02909d8f769f5a0570386aef55c3a472bdbc6c52949830ab94c1b624e6bd54"   # reviewed pin; superseded by the attempt-1 fix
CURRENT_SCRIPT_PIN = "b58b93215dc5c1e724846c7fc16acc2c29d81725a2ba13badcdccfd7b9eaecc7"   # pre-merge fixed script (incident record)
UNAUTHORIZED = ("M-B3 / SIGN_REGISTRY_V1 = NOT AUTHORIZED", "M-B4/M-B5 / INSTALL_TRUST_AND_REGISTRY = NOT AUTHORIZED",
                "REGISTRY EFFECTIVENESS = NOT AUTHORIZED", "GENESIS = NOT AUTHORIZED", "RECORD 1 = NOT AUTHORIZED",
                "FIRST MEMORY = NOT AUTHORIZED", "PROD = NOT AUTHORIZED", "FRESHNESS=UNKNOWN")

sys.path.insert(0, str(ROOT / "services/owner-memory-control"))
from lilith_owner_memory import burned_identities as BI  # noqa: E402


def section(text: str, start: str, end: str | None = None) -> str:
    body = text.split(start, 1)[1]
    return body.split(end, 1)[0] if end else body


def flat(text: str) -> str:
    return " ".join(re.sub(r"^\s*>", " ", text, flags=re.MULTILINE).split())


class DecisionTests(unittest.TestCase):
    def setUp(self):
        self.text = DECISION.read_text(encoding="utf-8")
        self.semantics = flat(section(self.text, "## 2. Semantics recorded", "## 3."))
        self.state = section(self.text, "## 5. State")

    def test_classification_and_no_execution_authority(self):
        self.assertIn(CLASSIFICATION, self.state)
        self.assertIn("THIS DECISION DOES NOT AUTHORIZE M-B3 EXECUTION", self.state)
        self.assertIn("**This decision does NOT authorize M-B3 execution.**", self.text)
        for line in UNAUTHORIZED:
            self.assertIn(line, self.state)
        for claim in ("M-B3 / SIGN_REGISTRY_V1 = AUTHORIZED", "GENESIS = AUTHORIZED", "FIRST MEMORY = AUTHORIZED",
                      "PROD = AUTHORIZED", "FRESHNESS=CURRENT"):
            self.assertNotIn(claim, self.text)

    def test_preparation_sequence_is_not_the_go(self):
        self.assertIn("Its authorization does **not** authorize K-ROOT signing.", self.semantics)
        self.assertIn("A **separate explicit owner go** is required immediately before the single real K-ROOT "
                      "signing invocation.", self.semantics)
        self.assertIn("PREPARATION SEQUENCE != SIGNING GO", self.state)

    def test_fresh_gates_and_kact_provenance(self):
        for gate in ("K-ACT CURRENT re-proof on DEV", "obtained read-only in that fresh re-proof and cryptographically "
                     "pinned", "K-WIT public identity / credential preservation", "K-ROOT custody attestation on the S25",
                     "an acceptable boot / broker / exposure posture", "never trusts an unverified `publicKeySha256` field"):
            self.assertIn(gate, self.semantics)

    def test_pr2_dr5_rule_and_terminators(self):
        self.assertIn("No fresh PR-2 and no full fresh DR-5 are required solely for M-B3", self.semantics)
        self.assertEqual(re.findall(r"^\| (M3-T\d+) \|", self.text, re.M), [f"M3-T{i}" for i in range(1, 12)])
        self.assertIn("A terminated sequence cannot reuse its final evidence.", self.semantics)

    def test_frozen_parameters(self):
        self.assertIn("| `policyVersion` | `policy.dev-synthetic.v1` |", self.text)
        self.assertIn("`secrets.token_hex(16)`", self.text)
        self.assertIn("one UTC RFC 3339 second-resolution timestamp, generated on the S25", self.text)
        self.assertIn("permanently bound into E0 and the K-ROOT signature", self.semantics)

    def test_prepare_sign_manifest_go(self):
        self.assertIn("PREPARE must not access, load or decrypt K-ROOT.", self.semantics)
        self.assertIn("SIGN uses the already-frozen manifest and never regenerates `epochRandom` or `issuedAt`.",
                      self.semantics)
        self.assertIn("**not authoritative LILITH state and not authorization**", self.semantics)
        self.assertIn("**An archive never embeds its own SHA-256**", self.semantics)
        self.assertIn("**No UI, flag, confirmation prompt or manifest is authority by itself.**", self.semantics)
        self.assertIn("It authorizes exactly one real SIGN operation.", self.semantics)

    def test_consumption_burns_and_c5(self):
        self.assertIn("There is no automatic or same-go retry.", self.semantics)
        for case in ("| A. no signature produced |", "| B. signature produced, candidate later accepted |",
                     "| D. signed output lost after signing |", "`UNKNOWN_REAL_REGISTRY_BURN`", "never invent a digest"):
            self.assertIn(case, self.text)
        self.assertIn("M-B4/M-B5 must install those same bytes", self.semantics)

    def test_verification_kwit_terminal(self):
        self.assertIn("**The S25 signed copy is authoritative for M-B3 custody; the laptop copy is a verified "
                      "public mirror / evidence copy.**", self.semantics)
        self.assertIn("K-WIT does not sign M-B3. The private K-WIT credential is never decrypted or touched.",
                      self.semantics)
        self.assertIn("Technical success terminal state: **`REGISTRY_SIGNED`**", self.semantics)
        self.assertIn("A separate explicit owner acceptance is required to close M-B3.", self.semantics)

    def test_identities(self):
        for value in (E21, KWIT, "test-only.witness.dev-synthetic.b1b3d.1"):
            self.assertIn(value, self.text)
        self.assertTrue({E21, KWIT, KACT}.isdisjoint(BI.BURNED_PUBLIC_KEY_SHA256))


class RepositoryFactsTests(unittest.TestCase):
    def test_signer_is_unchanged_and_sequencer_step_holds(self):
        tool = OWNER_TOOL.read_text(encoding="utf-8")
        self.assertIn('ROOT_KEY_ID = "test-only.registry-root.dev-synthetic.b1b3d.1"', tool)
        self.assertIn('elif argv[:1] == ["registry-v1"] and len(argv) == 6:', tool)
        self.assertIn('ask = passphrase or (lambda: getpass.getpass("K-ROOT passphrase: ").encode("utf-8"))', tool)
        self.assertIn('return {**unsigned, "signature": _b64u(key.sign(A.registry_signing_bytes(unsigned)))}', tool)
        # every failure inside main's try prints REFUSED and exits 2; the stdout write is after it
        self.assertIn('    sys.stdout.write(_jcs(result) + "\\n")\n    return 0', tool)
        self.assertIn('StepV1("SIGN_REGISTRY_V1", "K_WIT_CUSTODIED", "REGISTRY_SIGNED", "M-B3", NOT_APPLICABLE_PRE_GENESIS,',
                      SEQUENCING.read_text(encoding="utf-8"))
        for evidence in ("singleCurrentKeyHolds", "kActRecordEqualsPublication", "kWitNotInRegistry",
                         "registryDigestRecordedOffHost"):
            self.assertIn(evidence, SEQUENCING.read_text(encoding="utf-8"))

    def test_no_new_code_in_the_release_file_set(self):
        release = RELEASE_SET.read_text(encoding="utf-8")
        self.assertNotIn("mb3", release.lower())
        self.assertFalse(list((ROOT / "services/authority-dev").rglob("*mb3*")))


class PackageTests(unittest.TestCase):
    def setUp(self):
        self.text = PACKAGE.read_text(encoding="utf-8")

    def test_phone_script_pin(self):
        # The package record keeps the reviewed pin as history; the attempt-1 incident record supersedes it.
        self.assertGreaterEqual(self.text.count(SCRIPT_PIN), 3)
        self.assertIn("(slice-15b2b-b1b3e-mb3-sign-attempt1-incident.md)", self.text)
        self.assertEqual(hashlib.sha256(PHONE_SCRIPT.read_bytes()).hexdigest(), CURRENT_SCRIPT_PIN)
        incident = (ARCH / "slice-15b2b-b1b3e-mb3-sign-attempt1-incident.md").read_text(encoding="utf-8")
        self.assertIn(CURRENT_SCRIPT_PIN, incident)

    def test_status_and_deferred_pins(self):
        self.assertIn("**`MB3_PACKAGE_SOURCE_AND_DESIGN_READY_FOR_REVIEW`.**", self.text)
        self.assertIn("**The runnable bundle is NOT built yet.**", self.text)
        self.assertIn("printed by the builder (`tarSha256`); never written inside the bundle", self.text)
        for line in UNAUTHORIZED:
            self.assertIn(line, section(self.text, "## 15. Boundaries"))

    def test_go_template_binds_every_required_field(self):
        go = flat(section(self.text, "## 8. Owner STOP and the go template", "## 9."))
        for field in ("DEV_SYNTHETIC only", "`<CONTROL_SHA>`", "`<BUNDLE_SHA256>`", SCRIPT_PIN, "`<MANIFEST_SHA256>`",
                      "`<KACT_PUBLICATION_SHA256>`", KACT, E21, KWIT, "test-only.witness.dev-synthetic.b1b3d.1",
                      "`policyVersion=policy.dev-synthetic.v1`", "`epochRandom=<EPOCH_RANDOM>`",
                      "`issuedAt=<ISSUED_AT>`", "`<EXPECTED_REGISTRY_DIGEST>`", "~/lilith-kroot-dev-synthetic/k-root.der",
                      "registry-v1", "exactly one invocation", "There is no retry."):
            self.assertIn(field, go)
        self.assertIn("does not authorize M-B4/M-B5", go)

    def test_export_allowlist_matches_the_script(self):
        sys.path.insert(0, str(PHONE_SCRIPT.parent))
        import importlib.util
        spec = importlib.util.spec_from_file_location("mb3_phone_ceremony_doc", PHONE_SCRIPT)
        phone = importlib.util.module_from_spec(spec)
        sys.modules["mb3_phone_ceremony_doc"] = phone
        spec.loader.exec_module(phone)
        block = section(self.text, "**Success** (`~/lilith-mb3-export.tar`), exactly:\n\n```text\n", "```")
        self.assertEqual(tuple(block.split()), phone.SUCCESS_EXPORT)
        self.assertEqual(list(phone.SUCCESS_EXPORT), sorted(phone.SUCCESS_EXPORT))
        for name in phone.SUCCESS_EXPORT + phone.FAILURE_EXPORT_OPTIONAL:
            for part in phone.FORBIDDEN_EXPORT_PARTS:
                self.assertNotIn(part, name)

    def test_minimal_pointers(self):
        readme = (ARCH / "README.md").read_text(encoding="utf-8")
        self.assertIn("(slice-15b2b-b1b3e-mb3-signing-continuity-owner-decision.md)", readme)
        self.assertIn("(slice-15b2b-b1b3e-mb3-registry-ceremony-package.md)", readme)
        ledger = (ARCH / "current-architecture-acceptance-ledger-v0.1.md").read_text(encoding="utf-8")
        self.assertIn("### 13.1x Current-state reconciliation (M-B3 / SIGN_REGISTRY_V1", ledger)
        self.assertIn("193 rows; COVERED 11, PARTIAL 109", section(ledger, "### 13.1x", "### 13.2"))
        completion = (ARCH / "slice-15b2b-b1b3e-mb2-kwit-completion.md").read_text(encoding="utf-8")
        self.assertIn("M-B3 / `SIGN_REGISTRY_V1`, M-B4/M-B5, registry\n> effectiveness, genesis, record 1, First Memory "
                      "and PROD remain NOT\n> AUTHORIZED", completion)


if __name__ == "__main__":
    unittest.main()
