"""15B2b-B1b-3e M-B1: the final package pins (finalization record) (TEST-ONLY).

Record: docs/architecture/slice-15b2b-b1b3e-mb1-final-package-pins.md.

Nothing here runs on the phone, generates a key, or rebuilds the real bundle
(the real vendor set is not in the repository). It pins the final operator
script to the reviewed v3 block plus exactly the six pin substitutions (r1,
superseded) plus the one burned-count comment correction (r2).
"""

from __future__ import annotations

import hashlib
import importlib.util
import re
import subprocess
import sys
import tarfile
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
TOOLS = ROOT / "services/owner-memory-control/tools"
PACKAGE = ROOT / "docs/architecture/slice-15b2b-b1b3e-mb1-kroot-ceremony-package.md"
FINAL = ROOT / "docs/architecture/slice-15b2b-b1b3e-mb1-final-package-pins.md"
sys.path.insert(0, str(ROOT / "services/owner-memory-control"))

from lilith_owner_memory import burned_identities as BI  # noqa: E402

V3_SCRIPT_SHA = "a63bf5aa97d6a098923afc52fb9f71ebc0939c8526de28a1afb4271c4a84599e"
R1_SCRIPT_SHA = "4e463796ced5c8375fd45bbf318cee9c7222ab9e5d9b9e20190ab451a470c091"   # superseded by r2
SRC = "1e2eae30fb7023a44776d1f8d25e2bb958955e6a"
TAR_SHA = "7f07e158aa5a0b3c31ee63e25ae25116c92f26a402bc6924422d7c95e2edc2c1"
SUMS_SHA = "4816f8c93de7a2088fd3570edbdf141a2a1db12bedd330da46d83fd9336c6498"
PIN_SUBSTITUTIONS = (
    ("(bundle lilith-mb1-kroot-3ec71c1) =====", "(bundle lilith-mb1-kroot-1e2eae3) ====="),
    ("TAR=lilith-mb1-kroot-3ec71c1.tar\n", "TAR=lilith-mb1-kroot-1e2eae3.tar\n"),
    ("TAR_SHA=08cfe650024c1440c0fc56ebef226ad936d728bf3141e33d8e98aa361cb8ec78\n", f"TAR_SHA={TAR_SHA}\n"),
    ("SUMS_SHA=44e453acd0209177cc964a741447c2701345628e73c87d11884cf20edbb7a619\n", f"SUMS_SHA={SUMS_SHA}\n"),
    ("SRC=3ec71c176963a26b1b7d14333130bd7aebd2d555\n", f"SRC={SRC}\n"),
    ('B="$W/lilith-mb1-kroot-3ec71c1"', 'B="$W/lilith-mb1-kroot-1e2eae3"'),
)
COMMENT_SUBSTITUTION = (
    "# Refuses a real identity that equals ANY of the 12 permanently burned rehearsal identities (argv[1] = fingerprint).\n",
    "# Refuses a real identity that equals ANY of the 20 canonical permanently burned identities (argv[1] = fingerprint).\n",
)


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


BUILD = _load("build_mb1_kroot_bundle", TOOLS / "build_mb1_kroot_bundle.py")


def _block(record: Path) -> str:
    parts = [p.split("\n```", 1)[0] + "\n" for p in record.read_text(encoding="utf-8").split("```bash\n")[1:]]
    found = [p for p in parts if p.startswith("# ===== M-B1")]
    assert len(found) == 1
    return found[0]


def _git(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(ROOT), *args], check=True, capture_output=True)


class FinalPinTests(unittest.TestCase):
    def test_merged_v3_block_is_unchanged(self):
        self.assertEqual(hashlib.sha256(_block(PACKAGE).encode()).hexdigest(), V3_SCRIPT_SHA)

    def test_final_block_is_v3_with_six_pins_then_one_comment_correction(self):
        derived = _block(PACKAGE)
        for old, new in PIN_SUBSTITUTIONS:
            self.assertEqual(derived.count(old), 1)
            derived = derived.replace(old, new)
        self.assertEqual(hashlib.sha256(derived.encode()).hexdigest(), R1_SCRIPT_SHA)
        old, new = COMMENT_SUBSTITUTION
        self.assertEqual(derived.count(old), 1)
        derived = derived.replace(old, new)
        self.assertEqual(_block(FINAL), derived)
        self.assertNotEqual(hashlib.sha256(_block(FINAL).encode()).hexdigest(), R1_SCRIPT_SHA)
        for stale in ("3ec71c1", "08cfe650", "44e453ac"):
            self.assertNotIn(stale, _block(FINAL))

    def test_comment_correction_is_outside_executed_code(self):
        lines = _block(FINAL).splitlines()
        at = lines.index(COMMENT_SUBSTITUTION[1].rstrip("\n"))
        self.assertTrue(lines[at].startswith("# "))
        self.assertEqual(lines[at + 1], "BURNED_CHECK=$(cat <<'PYEOF'")   # a shell comment above the heredoc, never executed

    def test_no_stale_burned_count_in_the_block(self):
        for line in _block(FINAL).splitlines():
            if "burned" in line.lower():
                numbers = set(re.findall(r"\b\d+\b", re.sub(r"argv\[\d+\]", "", line)))
                self.assertLessEqual(numbers, {"20"}, line)

    def test_recorded_pins_match_the_block(self):
        text, block = FINAL.read_text(encoding="utf-8"), _block(FINAL)
        start = text.index("`mb1_phone_commands.sh` (SHA-256 `")
        self.assertEqual(text[start:start + 200].split("`")[3], hashlib.sha256(block.encode()).hexdigest())
        self.assertEqual(re.search(r"\*\*bundle SHA-256\*\* \| `([0-9a-f]{64})`", text).group(1), TAR_SHA)
        self.assertEqual(re.search(r"`SHA256SUMS` \(inside the bundle\) \| `([0-9a-f]{64})`", text).group(1), SUMS_SHA)
        self.assertEqual(re.search(r"\*\*source commit\*\* \| `([0-9a-f]{40})`", text).group(1), SRC)
        for pin in (f"TAR_SHA={TAR_SHA}", f"SUMS_SHA={SUMS_SHA}", f"SRC={SRC}", "NFILES=74",
                    f"TAR=lilith-mb1-kroot-{SRC[:7]}.tar", f'B="$W/lilith-mb1-kroot-{SRC[:7]}"'):
            self.assertIn(pin, block)

    def test_state_does_not_claim_authorization(self):
        state = FINAL.read_text(encoding="utf-8").split("## 7. State", 1)[1]
        for line in ("MB1_FINAL_PACKAGE_PINNED_READY_FOR_REVIEW", "CONDITION 1 NOT YET CLOSED", "M-B1 NOT AUTHORIZED",
                     "NO M-B1 COMMAND ISSUED", "NO REAL K-ROOT", "FRESHNESS=UNKNOWN", "FIRST MEMORY NOT AUTHORIZED"):
            self.assertIn(line, state)

    def test_burned_set_is_the_canonical_20(self):
        every = BI.BURNED_PUBLIC_KEY_SHA256 | BI.BURNED_REGISTRY_DIGESTS | BI.BURNED_GENESIS_WITNESS_DIGESTS
        self.assertEqual(len(every), BI.CANONICAL_COUNT)
        self.assertEqual(BI.CANONICAL_COUNT, 20)


class SourceCommitTests(unittest.TestCase):
    def setUp(self):
        try:
            _git("cat-file", "-e", f"{SRC}^{{commit}}")
        except (OSError, subprocess.CalledProcessError):
            self.skipTest("git or the source commit is unavailable")

    def test_source_commit_is_an_ancestor_and_the_closure_is_unchanged(self):
        _git("merge-base", "--is-ancestor", SRC, "HEAD")
        self.assertEqual(_git("diff", "--name-only", SRC, "HEAD", "--", *BUILD.CLOSURE).stdout, b"")

    def test_bundle_source_commit_and_members(self):
        with tempfile.TemporaryDirectory() as directory:
            d = Path(directory)
            vendor = d / "vendor"
            for top in BUILD.VENDOR_TOPS:
                (vendor / top).mkdir(parents=True)
                (vendor / top / "__init__.py").write_text(f"# {top}\n", encoding="utf-8")
            result = BUILD.build(ROOT, SRC, vendor, d / "a.tar")
            self.assertEqual((result["top"], result["sourceCommit"]), (f"lilith-mb1-kroot-{SRC[:7]}", SRC))
            with tarfile.open(d / "a.tar") as tar:
                files = {m.name.split("/", 1)[1]: tar.extractfile(m).read() for m in tar.getmembers() if m.isfile()}
            self.assertEqual(files["SOURCE_COMMIT"], (SRC + "\n").encode("ascii"))
            for path in BUILD.CLOSURE:
                self.assertEqual(files[path], _git("show", f"{SRC}:{path}").stdout)


if __name__ == "__main__":
    unittest.main()
