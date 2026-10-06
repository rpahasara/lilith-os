"""15B2b-B1b-3e M-B4/M-B5: the installable-representation owner decision and the remediation record (TEST-ONLY).

Records:
- docs/architecture/slice-15b2b-b1b3e-mb4-mb5-installable-representation-owner-decision.md;
- docs/architecture/slice-15b2b-b1b3e-mb4-mb5-trust-install-remediation.md.

Pins the three derivation rules and their fail-closed rule, the exact source
and representation pins (equal to the tool constants), that the continuity
model is PROPOSED and not accepted, the G-7 erratum, and the authority
boundary: nothing installed or effective, and M-B4, M-B5,
INSTALL_TRUST_AND_REGISTRY, genesis, record 1, First Memory and PROD not
authorized, with FRESHNESS UNKNOWN. Pure text checks; stdlib only.
"""

from __future__ import annotations

import ast
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
ARCH = ROOT / "docs/architecture"
DECISION = ARCH / "slice-15b2b-b1b3e-mb4-mb5-installable-representation-owner-decision.md"
REMEDIATION = ARCH / "slice-15b2b-b1b3e-mb4-mb5-trust-install-remediation.md"
PREFLIGHT = ARCH / "slice-15b2b-b1b3e-pr1-live-install-preflight.md"
LEDGER = ARCH / "current-architecture-acceptance-ledger-v0.1.md"
INDEX = ARCH / "README.md"
TOOLS = ROOT / "services/owner-memory-control/tools"
INSTALLER = ROOT / "services/authority-dev/ceremony/install_authority_dev.py"

CONTROL = "69dc8373ef64bbff9fd1e334a144203cff53a78f"
DIGEST = "fa66272131a3ef076036616b07766a377de4fdc1e4fef4cb8a054726f05c14fc"
TRANSPORT = "3f0a59c0a104934730184d28bc16e1c9215bdaa6ec1f9d94753722862f486156"
WRAPPER = "300a57dc01690868f7e6fa5dede4f7ca7278505e95b4fbbf0a2d505a18ffdb3f"
KWIT_PUBLICATION = "9e9dd0787b3d6df8d40730c6abab728cacbe5136269ca4421160da830bb23472"
E21 = "cb36daf176d813359b8bd0fe6361f549fd3334a52d0cd1f85cc5247cb26592cf"
KWIT = "5d778701def439b6c896392750c12685c26b67edfc908bed1a80f02eab0d0bdf"
REGISTRY_PIN = "46b0bfc558ec3a19467206ada3dc53c18e8a6a4cd0782711b4800cfe099f8b1e"
ROOT_PIN = "bc5f00a76b518c4f11b6804d35844c036db75eaa730d56c35f97f430558ff687"
WITNESS_PIN = "be360da2324880d725aea509bb0f41500f51ecfc3c2995dd3057824bb471ab5a"
INSTALLER_SHA = "fe10d9a37c53d4a32ca49d79ee5987c6546866feeebcee3c882087f51ed55487"
CONTINUITY = "MB4_MB5_CONTINUITY = OWNER_ATTENDED_EVENT_BOUNDED_SINGLE_SEQUENCE_TWO_GO"
UNAUTHORIZED = ("TRUST_INSTALLED = NO", "REGISTRY_INSTALLED = NO", "REGISTRY_EFFECTIVE = NO", "AUTHORITY_ACTIVE = NO",
                "M-B4 = NOT AUTHORIZED", "M-B5 = NOT AUTHORIZED", "INSTALL_TRUST_AND_REGISTRY = NOT AUTHORIZED",
                "GENESIS = NOT AUTHORIZED", "RECORD_1 = NOT AUTHORIZED", "FIRST_MEMORY = NOT AUTHORIZED",
                "PROD = NOT AUTHORIZED", "FRESHNESS=UNKNOWN")
FORBIDDEN_CLAIMS = ("M-B4 = AUTHORIZED", "M-B5 = AUTHORIZED", "INSTALL_TRUST_AND_REGISTRY = AUTHORIZED",
                    "TRUST_INSTALLED = YES", "REGISTRY_EFFECTIVE = YES", "AUTHORITY_ACTIVE = YES",
                    "GENESIS = AUTHORIZED", "RECORD_1 = AUTHORIZED", "FIRST_MEMORY = AUTHORIZED", "PROD = AUTHORIZED",
                    "FRESHNESS=CURRENT", "CONTINUITY = ACCEPTED", "(ACCEPTED)")


def section(text: str, start: str, end: str | None = None) -> str:
    body = text.split(start, 1)[1]
    return body.split(end, 1)[0] if end else body


def flat(text: str) -> str:
    return " ".join(text.split())


def constant(path: Path, name: str):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == name for t in node.targets):
            return node.value
    raise AssertionError(name)


class OwnerDecisionTests(unittest.TestCase):
    def setUp(self):
        self.text = DECISION.read_text(encoding="utf-8")
        self.flat = flat(self.text)
        self.state = section(self.text, "## 7. Authority boundary")

    def test_control_and_installer(self):
        self.assertIn(CONTROL, self.text)
        self.assertIn(INSTALLER_SHA, self.text)
        import hashlib
        self.assertEqual(hashlib.sha256(INSTALLER.read_bytes()).hexdigest(), INSTALLER_SHA)   # installer unchanged

    def test_registry_rule(self):
        rule = flat(section(self.text, "## 2. Registry V1", "## 3."))
        for phrase in (f"REGISTRY_V1_DIGEST = {DIGEST}", f"SIGNED_TRANSPORT_FILE_SHA256 = {TRANSPORT}",
                       "removing **exactly one terminal LF byte**", "no other normalization is done",
                       "RFC 8785 JCS(parse(R)) == R, byte for byte", "the E-21 signature still verifies",
                       "no semantic field changes", "**representation pin**, not a new Registry V1 identity",
                       "The original signed transport file is preserved unchanged."):
            self.assertIn(phrase, rule)

    def test_witness_anchor_rule(self):
        rule = flat(section(self.text, "## 3. K-WIT witness anchor derivation", "## 4."))
        for phrase in (KWIT_PUBLICATION, KWIT, "test-only.witness.dev-synthetic.b1b3d.1",
                       "with NO trailing newline and no extra transport bytes", "without changing them",
                       "Derive independently at least twice off-host and require byte-identical output.",
                       "No K-WIT private material may be read, decrypted or used.",
                       "does NOT permit using an arbitrary witness-anchor export"):
            self.assertIn(phrase, rule)

    def test_root_anchor_rule(self):
        rule = flat(section(self.text, "## 4. E-21 / K-ROOT registry-root anchor derivation", "## 5."))
        for phrase in (WRAPPER, E21, "test-only.registry-root.dev-synthetic.b1b3d.1", "Extract ONLY the `registryRoot` object.",
                       "**`Ed25519`**", "No new value is invented.", "no wrapper fields",
                       "No K-ROOT private material may be opened, read, decrypted or otherwise used.",
                       "it does NOT replace or redefine the E-21 identity"):
            self.assertIn(phrase, rule)
        source = (ROOT / "services/owner-memory-control/lilith_owner_memory/authority_contracts.py").read_text()
        self.assertIn('ALGORITHM = "Ed25519"', source)                 # the pinned literal is the reviewed schema's

    def test_fail_closed_and_results(self):
        rule = flat(section(self.text, "## 5. Fail-closed rule", "## 6."))
        self.assertIn("means **STOP**", rule)
        self.assertIn("no fallback representation, no permissive normalization, no runtime relaxation, no re-signing "
                      "and no regeneration", rule)
        results = section(self.text, "## 6. Results", "## 7.")
        for pin in (ROOT_PIN, WITNESS_PIN, REGISTRY_PIN, WRAPPER, KWIT_PUBLICATION, TRANSPORT):
            self.assertIn(pin, results)

    def test_authority_boundary(self):
        for line in UNAUTHORIZED:
            self.assertIn(line, self.state)
        for claim in FORBIDDEN_CLAIMS:
            self.assertNotIn(claim, self.state)
        self.assertIn("**This decision does NOT authorize M-B4/M-B5 execution.**", self.text)


class RemediationTests(unittest.TestCase):
    def setUp(self):
        self.text = REMEDIATION.read_text(encoding="utf-8")
        self.state = section(self.text, "## 11. State")

    def test_pins_equal_the_tool_constants(self):
        for path in (TOOLS / "mb4_mb5_installable_inputs.py", TOOLS / "mb4_mb5_trust_install_verifier.py"):
            text = path.read_text(encoding="utf-8")
            for pin in (ROOT_PIN, WITNESS_PIN, REGISTRY_PIN, DIGEST):
                self.assertEqual(text.count(pin), 1, (path.name, pin[:8]))
        derived = constant(TOOLS / "mb4_mb5_installable_inputs.py", "DERIVED_SHA256")
        self.assertEqual(sorted(v.value for v in derived.values), sorted((ROOT_PIN, WITNESS_PIN, REGISTRY_PIN)))
        for line in (f"REGISTRY_V1_INSTALLABLE_SHA256 = {REGISTRY_PIN}", f"ROOT_ANCHOR_INSTALLABLE_SHA256 = {ROOT_PIN}",
                     f"WITNESS_ANCHOR_INSTALLABLE_SHA256 = {WITNESS_PIN}",
                     "DERIVED THREE TIMES (TOOL x2, INDEPENDENT x1); BYTE-IDENTICAL",
                     f"SIGNED_TRANSPORT_FILE_SHA256 = {TRANSPORT} (PRESERVED UNCHANGED)"):
            self.assertIn(line, self.state)

    def test_continuity_is_proposed_not_accepted(self):
        self.assertIn(f"{CONTINUITY} (PROPOSED; NOT ACCEPTED; SEPARATE OWNER DECISION REQUIRED)", self.state)
        proposal = flat(section(self.text, "## 8. M-B4/M-B5 continuity: PROPOSED (not accepted)", "## 9."))
        self.assertIn("**Status: PROPOSED ONLY. A separate explicit owner decision is required.**", proposal)
        self.assertIn("neither executes nor activates it", proposal)
        self.assertIn("K-WIT burn/regenerate option closes at M-B4", proposal)
        for text in (self.text, DECISION.read_text(encoding="utf-8"), LEDGER.read_text(encoding="utf-8"),
                     INDEX.read_text(encoding="utf-8")):
            self.assertNotRegex(text, r"MB4_MB5_CONTINUITY[^\n]{0,80}\b(ACCEPTED|ADOPTED)\b(?<!NOT ACCEPTED)")

    def test_gap_status(self):
        gaps = section(self.text, "## 2. Gap status", "## 3.")
        for gap, status in (("G-1", "CLOSED IN SOURCE"), ("G-2", "CLOSED IN SOURCE"), ("G-3", "CLOSED"),
                            ("G-4", "CLOSED IN SOURCE"), ("G-5", "PREPARED, OPEN"), ("G-6", "CLOSED IN SOURCE"),
                            ("G-7", "CLOSED")):
            row = next(line for line in gaps.splitlines() if line.startswith(f"| {gap} |"))
            self.assertIn(f"**{status}", row)

    def test_verifier_semantics_documented(self):
        verifier = flat(section(self.text, "## 5. Read-only pre-ledger content verifier", "## 6."))
        for name in ("`anchorsEqualOwnerCopies`", "`witnessAnchorNamesKWit`", "`registryVerifiesOnHost`"):
            self.assertIn(name, verifier)
        self.assertIn("under the **installed** root anchor", verifier)
        self.assertIn("It is not owner acceptance and it authorizes nothing.", verifier)
        crash = section(self.text, "## 6. Crash windows", "## 7.")
        for phase in ("W0_PRE_INSTALL", "W1_ROOT_ANCHOR_INCOMPLETE", "W2_WITNESS_ANCHOR_INCOMPLETE",
                      "W3_ANCHORS_INSTALLED_REGISTRY_ABSENT", "W4_REGISTRY_INCOMPLETE", "W5_INSTALLED_CONTENT_VERIFIED"):
            self.assertIn(phase, crash)
        self.assertIn("**the K-WIT burn/regenerate option, closed at M-B4, does not reopen**", flat(crash))

    def test_authority_boundary(self):
        for line in UNAUTHORIZED + ("VERIFIER RUN ON DEV = NOT AUTHORIZED", "REMOVAL TOOL RUN = NOT AUTHORIZED",
                                    "INSTALLER / RUNTIME / SEQUENCER / RELEASE FILE SET / WORKFLOWS UNCHANGED"):
            self.assertIn(line, self.state)
        for claim in FORBIDDEN_CLAIMS:
            self.assertNotIn(claim, self.state)


class ErratumAndIndexTests(unittest.TestCase):
    def test_g7_erratum(self):
        text = PREFLIGHT.read_text(encoding="utf-8")
        row = next(line for line in text.splitlines() if line.startswith("| M-B5 | root | registry bytes |"))
        self.assertNotIn("`current` pointer", row)
        self.assertIn("no pointer — the witness decides the head at M-B9b", row)
        self.assertIn('previously read "install registry v1 + `current` pointer"', flat(text))
        installer = INSTALLER.read_text(encoding="utf-8")
        self.assertIn(r'_REGISTRY_FILE = re.compile(r"authority-registry\.v[1-9][0-9]{0,15}\.json\Z")', installer)

    def test_index_and_ledger(self):
        index = INDEX.read_text(encoding="utf-8")
        for name in (DECISION.name, REMEDIATION.name):
            self.assertIn(f"]({name})", index)
        ledger = LEDGER.read_text(encoding="utf-8")
        self.assertIn("### 13.1aa Current-state reconciliation (M-B4/M-B5 installable representations", ledger)
        block = section(ledger, "### 13.1aa", "### 13.2 Checks")
        self.assertIn("M-B4 / M-B5 / `INSTALL_TRUST_AND_REGISTRY` NOT AUTHORIZED", block)
        self.assertIn("FRESHNESS=UNKNOWN", block)
        self.assertIn("(§13.1aa) | UNASSIGNED |", ledger)
        for text in (index, ledger):
            self.assertNotRegex(text, re.escape("M-B4/M-B5") + r"[^\n]{0,40}= AUTHORIZED")


if __name__ == "__main__":
    unittest.main()
