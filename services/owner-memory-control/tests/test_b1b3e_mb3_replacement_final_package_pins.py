"""15B2b-B1b-3e M-B3: the post-incident replacement package final pins (finalization record) (TEST-ONLY).

Record: docs/architecture/slice-15b2b-b1b3e-mb3-replacement-final-package-pins.md.

Nothing here contacts anything, touches a key, or rebuilds the real bundle (the
real vendor set is not in the repository). It pins the record's replacement
values and history, checks that the tools still hash to them, that the
attempt-1 script and candidate stay historical, and, with git available, that
the replacement source commit is an ancestor of HEAD with every bundled file and
the phone script unchanged since it.
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
RECORD = ARCH / "slice-15b2b-b1b3e-mb3-replacement-final-package-pins.md"

SOURCE = "f9fb9e14dc6a14ac796379938d3092f6214194cb"
TAR = "lilith-mb3-registry-f9fb9e1.tar"
TAR_SHA = "ad37758ebf892e773a7019cb2c084d4d30920e34fb5318ba9f82999f48ffa736"
SUMS_SHA = "58eb1b8269f8a54dd4153d1bde68f1bf1440cb7d52459081f81884599240f683"
FILE_PINS = {
    "mb3_phone_ceremony.py": "b58b93215dc5c1e724846c7fc16acc2c29d81725a2ba13badcdccfd7b9eaecc7",
    "mb3_registry_ceremony.py": "c77b651ca2ae9d5f6c5526f958469a01c0d42e6ebdf189fc206ac2132af61320",
    "build_mb3_registry_bundle.py": "7f90d3ed05c370735f330805ae2a16b68598b77a8901a9ad492719774bad7293",
    "verify_mb3_registry.py": "e710cfa623d494e243ab4a1fbaefe28e8d079e58398368f9dcabd645e06b5507",
}
OLD_SCRIPT = "db02909d8f769f5a0570386aef55c3a472bdbc6c52949830ab94c1b624e6bd54"
OLD_BUNDLE = "fce71811073eeb98ce82b5db60dcefb5b7abb12119ed609d35a055bee7360cb0"
OLD_CANDIDATE = "b7e24530a21757a5bef996ec9adb13ed5932ab04edb1943321f529e3206c0e53"
UNAUTHORIZED = ("PHONE INCIDENT DISPOSITION = NOT AUTHORIZED", "REPLACEMENT M-B3 PREPARATION = NOT AUTHORIZED",
                "REPLACEMENT PREPARE = NOT AUTHORIZED", "REPLACEMENT SIGN_REGISTRY_V1 = NOT AUTHORIZED",
                "REGISTRY_SIGNED = NOT REACHED", "M-B4/M-B5 = NOT AUTHORIZED", "GENESIS = NOT AUTHORIZED",
                "RECORD 1 = NOT AUTHORIZED", "FIRST MEMORY = NOT AUTHORIZED", "PROD = NOT AUTHORIZED",
                "FRESHNESS=UNKNOWN")


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
        self.text = RECORD.read_text(encoding="utf-8")
        self.state = self.text.split("## 8. State", 1)[1]

    def test_status_and_replacement_pins(self):
        self.assertIn("**`M-B3 REPLACEMENT PACKAGE STATUS = REVIEWED FIX / MERGED / FINALIZED FOR NEW "
                      "PREPARATION-SEQUENCE CONSIDERATION`.**", self.text)
        for value in (SOURCE, TAR, TAR_SHA, SUMS_SHA, *FILE_PINS.values()):
            self.assertIn(value, self.text)
        self.assertIn(f"REPLACEMENT BUNDLE {TAR} {TAR_SHA} (1454080 BYTES, 75 FILES, 19 DIRECTORIES)", self.state)
        self.assertIn(f"CORRECTED PHONE SCRIPT {FILE_PINS['mb3_phone_ceremony.py']}", self.state)
        self.assertIn("MB3_REPLACEMENT_BUNDLE_REPRODUCIBLE_BYTE_IDENTICAL", self.state)
        self.assertIn("verifies **74 / 74** other members", self.text)
        self.assertNotEqual(FILE_PINS["mb3_phone_ceremony.py"], OLD_SCRIPT)

    def test_history_is_preserved(self):
        for line in (f"ATTEMPT-1 PACKAGE {OLD_BUNDLE} = HISTORICAL / SUPERSEDED",
                     f"ATTEMPT-1 SCRIPT {OLD_SCRIPT} = HISTORICAL / SUPERSEDED",
                     f"ATTEMPT-1 CANDIDATE {OLD_CANDIDATE} = HISTORICAL_ABANDONED_UNSIGNED_CANDIDATE; NOT BURNED; NOT REUSABLE",
                     "M-B3 SIGN ATTEMPT 1 = CLOSED / INCIDENT / A_NO_SIGNATURE", "NO_REAL_REGISTRY_BURN",
                     "REPLACEMENT PACKAGE FINALIZED; NOT TRANSFERRED"):
            self.assertIn(line, self.state)

    def test_historical_runs_are_not_freshness(self):
        for run in ("`37466905265` = **SUCCESS**", "`37467113188` = **SUCCESS**"):
            self.assertIn(run, self.text)
        self.assertIn("HISTORICAL RUNS 37466905265 / 37467113188 = SUCCESS; NOT FRESHNESS; NOT CURRENTNESS", self.state)

    def test_distinctions_and_nothing_authorized(self):
        for line in ("package reviewed       != package transferred",
                     "package finalized      != M-B3 preparation authorized", "PREPARE                != SIGN",
                     "candidate manifest     != authority", "REGISTRY_SIGNED        != registry effective"):
            self.assertIn(line, self.text)
        for line in UNAUTHORIZED:
            self.assertIn(line, self.state)
        for claim in ("DISPOSITION = AUTHORIZED", "PREPARATION = AUTHORIZED", "PREPARE = AUTHORIZED",
                      "SIGN_REGISTRY_V1 = AUTHORIZED", "REGISTRY_SIGNED = REACHED", "FRESHNESS=CURRENT"):
            self.assertNotIn(claim, self.state)

    def test_disposition_ordering_and_old_transfer_folder(self):
        self.assertIn("**must be archived by the reviewed\n  disposition procedure before any replacement file is transferred.**",
                      self.text)
        self.assertIn("`%USERPROFILE%\\lilith-mb3-transfer\\`", self.text)

    def test_pointers(self):
        for name in ("slice-15b2b-b1b3e-mb3-sign-attempt1-incident.md", "slice-15b2b-b1b3e-mb3-final-package-pins.md",
                     "README.md"):
            self.assertIn("(slice-15b2b-b1b3e-mb3-replacement-final-package-pins.md)",
                          (ARCH / name).read_text(encoding="utf-8"), name)


class SourceTests(unittest.TestCase):
    def test_tools_hash_to_the_replacement_pins(self):
        for name, digest in FILE_PINS.items():
            self.assertEqual(hashlib.sha256((TOOLS / name).read_bytes()).hexdigest(), digest, name)

    def test_old_candidate_is_not_burned(self):
        sys.path.insert(0, str(ROOT / "services/owner-memory-control"))
        from lilith_owner_memory import burned_identities as BI
        self.assertIsNone(BI.burned_identity(registry_digests=[OLD_CANDIDATE]))
        self.assertEqual(BI.CANONICAL_COUNT, 20)

    def test_builder_layout_matches_the_pinned_bundle(self):
        build = _load("build_mb3_registry_bundle_replacement", TOOLS / "build_mb3_registry_bundle.py")
        self.assertEqual(len(build.CLOSURE), 18)
        self.assertNotIn(build.PHONE_SCRIPT, build.CLOSURE)
        self.assertEqual(f"lilith-mb3-registry-{SOURCE[:7]}.tar", TAR)

    def test_source_is_an_ancestor_and_the_package_is_unchanged_since(self):
        if _git("cat-file", "-e", f"{SOURCE}^{{commit}}").returncode != 0:
            self.skipTest("git or the replacement source commit is unavailable")
        self.assertEqual(_git("merge-base", "--is-ancestor", SOURCE, "HEAD").returncode, 0)
        build = _load("build_mb3_registry_bundle_replacement2", TOOLS / "build_mb3_registry_bundle.py")
        changed = _git("diff", "--name-only", SOURCE, "HEAD", "--", *build.CLOSURE, build.PHONE_SCRIPT)
        self.assertEqual(changed.returncode, 0)
        self.assertEqual(changed.stdout.strip(), "")


if __name__ == "__main__":
    unittest.main()
