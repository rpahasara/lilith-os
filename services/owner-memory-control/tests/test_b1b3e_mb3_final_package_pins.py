"""15B2b-B1b-3e M-B3: the post-merge final package pins (finalization record) (TEST-ONLY).

Record: docs/architecture/slice-15b2b-b1b3e-mb3-final-package-pins.md.

Nothing here contacts anything, touches a key, or rebuilds the real bundle (the
real vendor set is not in the repository). It pins the record's values, checks
that the phone script, library, builder and verifier still hash to them, and,
with git available, that the control commit is an ancestor of HEAD with every
bundled file unchanged since it, so the pinned bundle stays reproducible.
"""

from __future__ import annotations

import hashlib
import importlib.util
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
TOOLS = ROOT / "services/owner-memory-control/tools"
ARCH = ROOT / "docs/architecture"
FINAL = ARCH / "slice-15b2b-b1b3e-mb3-final-package-pins.md"
PACKAGE = ARCH / "slice-15b2b-b1b3e-mb3-registry-ceremony-package.md"

CONTROL = "1f544e695742fd4a93fcf4fd8dc5d706e24eb452"
TAR = "lilith-mb3-registry-1f544e6.tar"
TAR_SHA = "fce71811073eeb98ce82b5db60dcefb5b7abb12119ed609d35a055bee7360cb0"
TAR_SIZE = "1454080"
SUMS_SHA = "0e3fa7cde854ed08e9826cf175c1d13bdb215bd6a9c664a75390ce6bbad0a18f"
FILE_PINS = {
    "mb3_phone_ceremony.py": "db02909d8f769f5a0570386aef55c3a472bdbc6c52949830ab94c1b624e6bd54",
    "mb3_registry_ceremony.py": "c77b651ca2ae9d5f6c5526f958469a01c0d42e6ebdf189fc206ac2132af61320",
    "build_mb3_registry_bundle.py": "7f90d3ed05c370735f330805ae2a16b68598b77a8901a9ad492719774bad7293",
    "verify_mb3_registry.py": "e710cfa623d494e243ab4a1fbaefe28e8d079e58398368f9dcabd645e06b5507",
}
FIXED_SCRIPT_SHA = "b58b93215dc5c1e724846c7fc16acc2c29d81725a2ba13badcdccfd7b9eaecc7"   # pre-merge attempt-1 fix; final pin after re-finalization
UNAUTHORIZED = ("M-B3 PREPARATION SEQUENCE = NOT AUTHORIZED", "M-B3 PREPARE ON S25 = NOT AUTHORIZED",
                "M-B3 / SIGN_REGISTRY_V1 = NOT AUTHORIZED", "REGISTRY_SIGNED = NOT REACHED",
                "M-B4/M-B5 / INSTALL_TRUST_AND_REGISTRY = NOT AUTHORIZED", "REGISTRY EFFECTIVENESS = NOT AUTHORIZED",
                "GENESIS = NOT AUTHORIZED", "RECORD 1 = NOT AUTHORIZED", "FIRST MEMORY = NOT AUTHORIZED",
                "PROD = NOT AUTHORIZED", "FRESHNESS=UNKNOWN")


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _git(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(ROOT), *args], capture_output=True, text=True)


class RecordTests(unittest.TestCase):
    def setUp(self):
        self.text = FINAL.read_text(encoding="utf-8")
        self.state = self.text.split("## 8. State", 1)[1]

    def test_status_and_pins(self):
        self.assertIn("**`M-B3 PACKAGE STATUS = REVIEWED / MERGED / FINALIZED FOR PREPARATION-SEQUENCE CONSIDERATION`.**",
                      self.text)
        for value in (CONTROL, TAR, TAR_SHA, TAR_SIZE, SUMS_SHA, *FILE_PINS.values()):
            self.assertIn(value, self.text)
        self.assertIn(f"BUNDLE {TAR} {TAR_SHA} ({TAR_SIZE} BYTES, 75 FILES)", self.state)
        self.assertIn("MB3_BUNDLE_REPRODUCIBLE_BYTE_IDENTICAL", self.state)
        self.assertIn("verifies **74 / 74** other members", self.text)

    def test_historical_runs_are_not_freshness(self):
        for run in ("`37452396528` = **SUCCESS**", "`37452579297` = **SUCCESS**"):
            self.assertIn(run, self.text)
        self.assertIn("They do **not**\nestablish M-B3 freshness or currentness", self.text)
        self.assertIn("HISTORICAL RUNS 37452396528 / 37452579297 = SUCCESS; NOT FRESHNESS; NOT CURRENTNESS", self.state)

    def test_distinctions_and_unauthorized_state(self):
        for line in ("package reviewed       != package transferred",
                     "package finalized      != M-B3 preparation authorized",
                     "M-B3 preparation       != signing go", "PREPARE                != SIGN",
                     "candidate manifest     != authority", "SIGN_REGISTRY_V1 execution != owner acceptance",
                     "REGISTRY_SIGNED        != registry effective"):
            self.assertIn(line, self.text)
        for line in UNAUTHORIZED:
            self.assertIn(line, self.state)
        for claim in ("SIGN_REGISTRY_V1 = AUTHORIZED", "REGISTRY_SIGNED = REACHED", "FRESHNESS=CURRENT",
                      "PREPARATION SEQUENCE = AUTHORIZED"):
            self.assertNotIn(claim, self.state)

    def test_package_points_to_finalization(self):
        self.assertIn("(slice-15b2b-b1b3e-mb3-final-package-pins.md)", PACKAGE.read_text(encoding="utf-8"))
        self.assertIn("(slice-15b2b-b1b3e-mb3-final-package-pins.md)", (ARCH / "README.md").read_text(encoding="utf-8"))


class SourceTests(unittest.TestCase):
    def test_tool_files_still_hash_to_the_pins(self):
        # The phone script is superseded by the attempt-1 incident fix (incident record); the other tools are unchanged.
        for name, digest in FILE_PINS.items():
            if name == "mb3_phone_ceremony.py":
                continue
            self.assertEqual(hashlib.sha256((TOOLS / name).read_bytes()).hexdigest(), digest, name)
        self.assertEqual(hashlib.sha256((TOOLS / "mb3_phone_ceremony.py").read_bytes()).hexdigest(), FIXED_SCRIPT_SHA)
        incident = _load("mb3_incident_tests_for_pins", Path(__file__).resolve().with_name("test_b1b3e_mb3_sign_incident.py"))
        self.assertEqual(hashlib.sha256(incident.attempt1_script_bytes()).hexdigest(), FILE_PINS["mb3_phone_ceremony.py"])
        self.assertIn("(slice-15b2b-b1b3e-mb3-sign-attempt1-incident.md)", self.text_final())

    def text_final(self) -> str:
        return FINAL.read_text(encoding="utf-8")

    def test_builder_layout_matches_the_pinned_bundle(self):
        build = _load("build_mb3_registry_bundle_final", TOOLS / "build_mb3_registry_bundle.py")
        self.assertEqual(len(build.CLOSURE), 18)
        self.assertNotIn(build.PHONE_SCRIPT, build.CLOSURE)
        self.assertEqual(f"lilith-mb3-registry-{CONTROL[:7]}.tar", TAR)

    def test_control_is_an_ancestor_and_the_bundled_sources_are_unchanged(self):
        if _git("cat-file", "-e", f"{CONTROL}^{{commit}}").returncode != 0:
            self.skipTest("git or the control commit is unavailable")
        self.assertEqual(_git("merge-base", "--is-ancestor", CONTROL, "HEAD").returncode, 0)
        build = _load("build_mb3_registry_bundle_final2", TOOLS / "build_mb3_registry_bundle.py")
        changed = _git("diff", "--name-only", CONTROL, "HEAD", "--", *build.CLOSURE)
        self.assertEqual(changed.returncode, 0)
        self.assertEqual(changed.stdout.strip(), "")
        # The phone script (outside the bundle) differs from the control commit only by the attempt-1 fix.
        incident = _load("mb3_incident_tests_for_ancestry", Path(__file__).resolve().with_name("test_b1b3e_mb3_sign_incident.py"))
        at_control = subprocess.run(["git", "-C", str(ROOT), "show", f"{CONTROL}:{build.PHONE_SCRIPT}"],
                                    capture_output=True, check=True).stdout
        self.assertEqual(incident.attempt1_script_bytes(), at_control)


if __name__ == "__main__":
    unittest.main()
