"""15B2b-B1b-3e M-B4/M-B5: the continuity owner decision and the ceremony package (TEST-ONLY).

Records:
- docs/architecture/slice-15b2b-b1b3e-mb4-mb5-continuity-owner-decision.md;
- docs/architecture/slice-15b2b-b1b3e-mb4-mb5-ceremony-package.md.

Pins the fifteen accepted continuity semantics; that the package's tool,
module and representation pins equal the code and the files; that the go and
removal templates in the record are exactly the operator's binding lines; the
W0/W3/W5 checkpoints; the post-M-B3 deploy classification; the DR-5 extension
designed-not-implemented and the denial-proof P1B-5 phase; and the authority
boundary. Stdlib only.
"""

from __future__ import annotations

import hashlib
import importlib.util
import os
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
ARCH = ROOT / "docs/architecture"
DECISION = ARCH / "slice-15b2b-b1b3e-mb4-mb5-continuity-owner-decision.md"
PACKAGE = ARCH / "slice-15b2b-b1b3e-mb4-mb5-ceremony-package.md"
TOOLS = ROOT / "services/owner-memory-control/tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import mb4_mb5_operator as O  # noqa: E402

CONTROL = "b0299f3966de051042b7c906b89559a179ed998d"
CONTINUITY = "MB4_MB5_CONTINUITY = OWNER_ATTENDED_EVENT_BOUNDED_SINGLE_SEQUENCE_TWO_GO"
UNAUTHORIZED = ("M-B4 = NOT AUTHORIZED", "M-B5 = NOT AUTHORIZED", "INSTALL_TRUST_AND_REGISTRY = NOT AUTHORIZED",
                "TRUST_INSTALLED = NO", "REGISTRY_INSTALLED = NO", "REGISTRY_EFFECTIVE = NO", "AUTHORITY_ACTIVE = NO",
                "GENESIS = NOT AUTHORIZED", "RECORD_1 = NOT AUTHORIZED", "FIRST_MEMORY = NOT AUTHORIZED",
                "PROD = NOT AUTHORIZED", "FRESHNESS=UNKNOWN")
FORBIDDEN = ("M-B4 = AUTHORIZED", "M-B5 = AUTHORIZED", "INSTALL_TRUST_AND_REGISTRY = AUTHORIZED", "TRUST_INSTALLED = YES",
             "REGISTRY_EFFECTIVE = YES", "AUTHORITY_ACTIVE = YES", "GENESIS = AUTHORIZED", "RECORD_1 = AUTHORIZED",
             "FIRST_MEMORY = AUTHORIZED", "PROD = AUTHORIZED", "FRESHNESS=CURRENT")


def section(text: str, start: str, end: str | None = None) -> str:
    body = text.split(start, 1)[1]
    return body.split(end, 1)[0] if end else body


def flat(text: str) -> str:
    return " ".join(text.split())


def quoted(block: str) -> list[str]:
    return [line[2:].replace("`", "") for line in block.splitlines() if line.startswith("> ")]


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class ContinuityDecisionTests(unittest.TestCase):
    def setUp(self):
        self.text = DECISION.read_text(encoding="utf-8")
        self.state = section(self.text, "## 5. Authority boundary")

    def test_accepted_and_control(self):
        self.assertIn(CONTROL, self.text)
        self.assertIn(f"{CONTINUITY} (ACCEPTED)", self.state)
        self.assertIn("CONTINUITY SEMANTICS ONLY; NO EXECUTION AUTHORIZED", self.state)
        self.assertIn("G-5 CLOSED IN GOVERNANCE", self.state)

    def test_fifteen_semantics(self):
        semantics = flat(section(self.text, "## 2. Semantics recorded", "## 3."))
        for number in range(1, 16):
            self.assertIn(f"**C-{number}.", semantics)
        for phrase in ("one owner-attended, evidence-bounded sequence", "one freshly established evidence set",
                       "separate, explicit, ONE-ATTEMPT owner go", "HARD STOP after M-B4",
                       "M-B5 is not implicitly authorized by M-B4 success", "a fresh re-proof is required",
                       "M-B4 closes the K-WIT burn/regenerate option",
                       "that option does not reopen merely because installed files are later removed before M-B6",
                       "`REGISTRY_SIGNED -> TRUST_INSTALLED`", "Successful M-B4 alone does not mean `TRUST_INSTALLED`",
                       "It is subject to separate owner acceptance", "No wall-clock TTL is introduced",
                       "REVALIDATE / sequence unusable, not PASS",
                       "Historical PASS evidence may not be replayed as current evidence"):
            self.assertIn(phrase, semantics)

    def test_pins_and_boundary(self):
        pins = section(self.text, "## 3. Accepted installable representation pins", "## 4.")
        for value in list(O.DERIVED.values()) + [O.REGISTRY_DIGEST, O.TRANSPORT_SHA256, O.EXPORT_SHA256, O.E21, O.KWIT]:
            self.assertIn(value, pins)
        for line in UNAUTHORIZED:
            self.assertIn(line, self.state)
        for claim in FORBIDDEN:
            self.assertNotIn(claim, self.state)
        self.assertIn("**This decision accepts continuity semantics only. It does NOT authorize\n  execution.**", self.text)


class PackageTests(unittest.TestCase):
    def setUp(self):
        self.text = PACKAGE.read_text(encoding="utf-8")
        self.state = section(self.text, "## 17. State")

    def test_tool_pins_equal_code_and_files(self):
        table = section(self.text, "## 1. Control and pinned tools", "**Hash-gated streaming.**")
        operator_sha = sha(TOOLS / "mb4_mb5_operator.py")
        self.assertIn(f"`services/owner-memory-control/tools/mb4_mb5_operator.py` | owner laptop", table)
        self.assertIn(operator_sha, table)
        for path, pin in O.TOOL_PINS.items():
            self.assertEqual(sha(ROOT / path), pin, path)
            row = next(line for line in table.splitlines() if line.startswith(f"| `{path}`"))
            self.assertIn(pin, row)
        for extra in ("services/owner-memory-control/lilith_owner_memory/owner_freshness_tool.py",
                      "scripts/deployer_authority_boundary_proof.sh"):
            row = next(line for line in table.splitlines() if line.startswith(f"| `{extra}`"))
            self.assertIn(sha(ROOT / extra), row)
        gate = section(self.text, "**Hash-gated streaming.**", "## 2.")
        self.assertIn("sha256sum | cut -c1-64 | grep -qx '<pin>' || exit 96", gate)

    def test_module_and_representation_pins(self):
        modules = section(self.text, "**R-3 module pins**", "## 6.")
        for module, pin in O.RELEASE_MODULES.items():
            self.assertIn(f"| `{module}` | `{pin}` |", modules)
        self.assertEqual(len(re.findall(r"^\| `lilith_", modules, re.M)), len(O.RELEASE_MODULES))
        artifacts = section(self.text, "### 5.1", "### 5.2")
        for name, pin in O.DERIVED.items():
            self.assertIn(f"| `{name}` | `{pin}` |", artifacts)

    def test_go_templates_are_the_operator_binding_lines(self):
        mb4 = quoted(section(self.text, "### 7.2 M-B4 owner go template", "The operator"))
        self.assertEqual(mb4, [line.format(control="<CONTROL>") for line in O.MB4_GO_LINES])
        mb5 = quoted(section(self.text, "### 9.2 M-B5 owner go template", "The operator"))
        self.assertEqual(mb5, [line.format(control="<CONTROL>") for line in O.MB5_GO_LINES])
        removal = quoted(section(self.text, "**12.4 Bounded removal.**", "## 13."))
        self.assertEqual(removal, [line.format(plan="<planDigest>") for line in O.REMOVAL_LINES])

    def test_checkpoints(self):
        self.assertIn("VERIFIER CHECKPOINTS: BEFORE M-B4 = W0_PRE_INSTALL; AFTER M-B4 = W3_ANCHORS_INSTALLED_REGISTRY_ABSENT; "
                      "AFTER M-B5 = W5_INSTALLED_CONTENT_VERIFIED", self.state)
        self.assertEqual(O.VERIFIER_PHASE, {"W0": "W0_PRE_INSTALL", "W3": "W3_ANCHORS_INSTALLED_REGISTRY_ABSENT",
                                            "W5": "W5_INSTALLED_CONTENT_VERIFIED"})
        self.assertEqual(O.INSTALLER_STAGE, {"W0": "P1B-2", "W3": "P1B-4", "W5": "P1B-5"})
        post4 = flat(section(self.text, "## 8. M-B4 POST", "## 9."))
        for phrase in ("`anchorsEqualOwnerCopies=true`", "`witnessAnchorNamesKWit=true`", "`registryVerifiesOnHost=false`",
                       "**Then HARD STOP (C-5).**"):
            self.assertIn(phrase, post4)
        post5 = flat(section(self.text, "## 10. M-B5 POST", "## 11."))
        for phrase in ("`trustInstalledCandidate=true`", "`AUTHORITY_CUSTODY_DENIAL_PROOF=PASS phase=P1B-5`",
                       "**separate explicit owner acceptance**"):
            self.assertIn(phrase, post5)
        evidence = flat(section(self.text, "## 4. Fresh preparation", "## 5."))
        for number in range(1, 23):
            self.assertIn(f"| E-{number} |", evidence)

    def test_deploy_classification_and_dr5(self):
        classification = section(self.text, "## 13. Post-M-B3 deploy classification", "## 14.")
        for run, short in (("37445851939", "14fbe03"), ("37452579297", "1f544e6"), ("37455735513", "a86d032"),
                           ("37467113188", "f9fb9e1"), ("37470507011", "cb07608"), ("37475815074", "ea74e1b"),
                           ("37506016808", "1fb73e0"), ("37507920435", "69dc837"), ("37517400764", "b0299f3")):
            row = next(line for line in classification.splitlines() if line.startswith(f"| `{run}` |"))
            self.assertIn(short, row)
            self.assertIn("DR-5 MUST_RECOLLECT", row)
        self.assertIn("**Materially invalidating: none** by content", classification)
        self.assertIn("**UNKNOWN** here", classification)
        dr5 = flat(section(self.text, "## 14. DR-5 design", "## 15."))
        self.assertIn("f18692342cd62572affa54c83f9d390d21ac183e85dc8496dbadb0d5f3f49f9b", dr5)
        self.assertIn("### 14.2 Extension of DR-5 to the three files: NOT IMPLEMENTED (by design)", self.text)
        script = (ROOT / "scripts/deployer_authority_boundary_proof.sh").read_text(encoding="utf-8")
        self.assertNotIn("P1B-4", script)
        self.assertIn('readonly AB_PR1_STEPS="PR1_ABSENT P1A-5 P1A-7 P1A-8a P1A-8b P1A-9"', script)
        self.assertIn("DR-5 EXTENSION = DESIGNED, NOT IMPLEMENTED (B-5 §9 RESULT-SET RULE); DENIAL PROOF P1B-5 = "
                      "IMPLEMENTED", self.state)

    def test_authority_boundary(self):
        for line in UNAUTHORIZED + ("PREPARATION SEQUENCE = NOT AUTHORIZED", "TRANSFER = NOT AUTHORIZED",
                                    "REMOVAL = NOT AUTHORIZED"):
            self.assertIn(line, self.state)
        for claim in FORBIDDEN:
            self.assertNotIn(claim, self.state)


@unittest.skipUnless(os.name == "posix", "the denial proof is a POSIX root tool")
class DenialProofP1B5Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        spec = importlib.util.spec_from_file_location("denial_p1b5", ROOT / "scripts/authority_custody_denial_proof.py")
        cls.D = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.D)

    def prove(self, phase, *, allowed=(), absent=()):
        lines = []
        ok = self.D.prove(phase, run=lambda argv: 0 if (argv[2], argv[-2], argv[-1]) in allowed else 1,
                          exists=lambda path: path not in absent, euid=lambda: 0, signer_pid=lambda: "4242",
                          signer_ids=lambda: (990, 980), say=lines.append)
        return ok, lines

    def test_phase_order_and_rows(self):
        self.assertEqual(self.D.PHASES, ("P1A-10", "P1B-5", "P1B-12"))
        files = (self.D.REGISTRY_ROOT_ANCHOR, self.D.WITNESS_ANCHOR, self.D.REGISTRY_V1)
        self.assertEqual(files, ("/etc/lilith-authority-dev/trust/registry-root.json",
                                 "/etc/lilith-authority-dev/trust/witness-anchor.json",
                                 "/etc/lilith-authority-dev/registry/authority-registry.v1.json"))
        rows = [row for row in self.D.ROWS if row[0] == "P1B-5"]
        self.assertEqual([(r[2], r[3]) for r in rows], [("-w", f) for f in files])
        for row in rows:
            self.assertEqual(set(row[1]), {"lilith", "sa_112096412008414111981", "lilith-memory-broker",
                                           "lilith-authority-dev", "lilith-recovery-witness"})

    def test_p1b5_pass_absent_and_allowed(self):
        ok, lines = self.prove("P1B-5")
        self.assertTrue(ok, lines)
        self.assertEqual(lines[-1], "AUTHORITY_CUSTODY_DENIAL_PROOF=PASS phase=P1B-5")
        self.assertIn("DENIED: lilith-authority-dev test -w /etc/lilith-authority-dev/registry/authority-registry.v1.json",
                      lines)
        self.assertTrue(any(line.startswith("DEFERRED_UNTIL_PHASE: P1B-12") for line in lines))
        self.assertFalse(any("signer-namespace" in line for line in lines))
        ok, lines = self.prove("P1B-5", absent=(self.D.WITNESS_ANCHOR,))
        self.assertFalse(ok)
        self.assertIn(f"FAIL: DENIAL_VACUOUS_PATH_ABSENT -w {self.D.WITNESS_ANCHOR}", lines)
        ok, lines = self.prove("P1B-5", allowed={("lilith-recovery-witness", "-w", self.D.REGISTRY_ROOT_ANCHOR)})
        self.assertFalse(ok)
        ok, lines = self.prove("P1A-10")
        self.assertTrue(ok)
        self.assertTrue(any(line.startswith("DEFERRED_UNTIL_PHASE: P1B-5 -w") for line in lines))


if __name__ == "__main__":
    unittest.main()
