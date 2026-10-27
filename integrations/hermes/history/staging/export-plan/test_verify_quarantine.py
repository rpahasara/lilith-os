#!/usr/bin/env python3
"""Synthetic self-tests for verify_quarantine.py. TEST_ONLY data, temporary folders, no PROD/DEV access.

Run: python test_verify_quarantine.py   (needs git and the verified upstream copy ../hermes-agent-f293e72)
"""

from __future__ import annotations

import base64
import hashlib
import io
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
VERIFY = HERE / "verify_quarantine.py"
UPSTREAM = HERE.parent / "hermes-agent-f293e72"

FAKE_KEY = "gsk_" + "TESTONLY" * 4                       # synthetic, matches the groq-key pattern
FILES = {
    "lilith_router/__init__.py": b"# TEST_ONLY synthetic package\n",
    "plugins/lilith_os/adapter.py": (
        "PORT = 9901  # TEST_ONLY\n"
        "OWNER = 'Ravindu'  # TEST_ONLY personal\n"
        "CONTACT = 'owner@example.invalid'\n"
        "DATA = '/home/lilith/.hermes/lilith-os/data'\n"
        f"KEY = '{FAKE_KEY}'\n"
    ).encode("utf-8"),
}
RAW_VALUES = ("Ravindu", "owner@example.invalid", "/home/lilith", FAKE_KEY, "TESTONLY")


def synthetic_diff() -> tuple[bytes, str]:
    with tempfile.TemporaryDirectory() as tmp:
        subprocess.run(["git", "init", "-q", tmp], check=True)
        (Path(tmp) / "gateway").mkdir()
        shutil.copyfile(UPSTREAM / "gateway" / "run.py", Path(tmp) / "gateway" / "run.py")
        subprocess.run(["git", "-C", tmp, "add", "."], check=True)
        subprocess.run(["git", "-C", tmp, "-c", "user.name=t", "-c", "user.email=t@t.invalid", "commit", "-qm", "u"],
                       check=True)
        run_py = Path(tmp) / "gateway" / "run.py"
        run_py.write_bytes(run_py.read_bytes() + b"# TEST_ONLY synthetic hook\n")
        diff = subprocess.run(["git", "-C", tmp, "diff", "HEAD", "--", "gateway/run.py"], capture_output=True,
                              check=True).stdout
        return diff, hashlib.sha256(run_py.read_bytes()).hexdigest()


DIFF, DIFF_RESULT = synthetic_diff()


def make_junction(link: Path, target: Path) -> bool:
    if os.name != "nt":
        link.symlink_to(target, target_is_directory=True)
        return True
    proc = subprocess.run(["cmd", "/c", "mklink", "/J", str(link), str(target)], capture_output=True)
    return proc.returncode == 0


class VerifyQuarantineTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def quarantine(self, name="q", members=None, links=(), diff=DIFF, entries=None, parent=None) -> Path:
        q = (parent or self.root) / name
        q.mkdir(parents=True)
        members = FILES if members is None else members
        entries = {k: hashlib.sha256(v).hexdigest() for k, v in FILES.items()} if entries is None else entries
        rows = ["stage\tkind\tprod_path\texpected_sha256\tbytes\treview\treason",
                f"1\tgit-diff\trun\tAPPLIED_RESULT={DIFF_RESULT}\t-\tcode\tx"]
        rows += [f"1\tfile\t{k}\t{v}\t-\tcode\tx" for k, v in entries.items()]
        (self.root / f"{name}.allow.tsv").write_text("\n".join(rows) + "\n", encoding="utf-8")
        buf = io.BytesIO()
        with tarfile.open(fileobj=buf, mode="w") as tar:
            for key, body in members.items():
                info = tarfile.TarInfo(key)
                info.size = len(body)
                tar.addfile(info, io.BytesIO(body))
            for key in links:
                info = tarfile.TarInfo(key)
                info.type = tarfile.SYMTYPE
                info.linkname = "/etc/passwd"
                tar.addfile(info)
        (q / "stage1.tar.b64").write_bytes(base64.b64encode(buf.getvalue()))
        (q / "run.py.diff.b64").write_bytes(base64.b64encode(diff))
        return q

    def run_verify(self, q: Path, name="q") -> subprocess.CompletedProcess:
        return subprocess.run([sys.executable, str(VERIFY), str(q), "--allowlist", str(self.root / f"{name}.allow.tsv"),
                               "--upstream", str(UPSTREAM)], capture_output=True, text=True)

    def assert_failed(self, proc, fragment):
        self.assertEqual(proc.returncode, 2, proc.stdout + proc.stderr)
        self.assertIn(fragment, proc.stdout)

    # ---- original integrity cases ----
    def test_good_export_verifies(self):
        q = self.quarantine()
        self.assertEqual(self.run_verify(q).returncode, 0)
        self.assertFalse(os.access(q / "extracted" / "lilith_router" / "__init__.py", os.W_OK))

    def test_integrity_failures(self):
        good = {k: hashlib.sha256(v).hexdigest() for k, v in FILES.items()}
        cases = {
            "extra": (dict(members={**FILES, "lilith_router/extra.py": b"x"}), "not on the allowlist"),
            "mismatch": (dict(members={**FILES, "lilith_router/__init__.py": b"tampered\n"}), "sha256 mismatch"),
            "missing": (dict(members={"lilith_router/__init__.py": FILES["lilith_router/__init__.py"]}),
                        "missing from archive"),
            "link": (dict(links=("lilith_router/link.py",)), "non-regular member"),
            "traversal": (dict(members={**FILES, "../escape.py": b"x"}), "unsafe path"),
            "diffother": (dict(diff=DIFF.replace(b"gateway/run.py", b"gateway/other.py", 2)), "gateway/run.py only"),
            "diffwrong": (dict(diff=DIFF.replace(b"+# TEST_ONLY synthetic hook", b"+# TEST_ONLY altered")),
                          "expected PROD run.py"),
        }
        for name, (kwargs, fragment) in cases.items():
            with self.subTest(name):
                q = self.quarantine(name=name, entries=good, **kwargs)
                self.assert_failed(self.run_verify(q, name), fragment)
                self.assertFalse((q / "extracted").exists())
                self.assertFalse((q / "REVIEW.md").exists())

    # ---- correction 1: every finding value redacted ----
    def test_review_redacts_all_finding_values(self):
        q = self.quarantine()
        self.assertEqual(self.run_verify(q).returncode, 0)
        review = (q / "REVIEW.md").read_text(encoding="utf-8")
        for category in ("SECRET:groq-key", "PERSONAL:owner-name", "PERSONAL:email", "CONFIDENTIAL:home-path"):
            self.assertIn(category, review)
        self.assertIn("| plugins/lilith_os/adapter.py | 2 | PERSONAL:owner-name | [redacted 7 chars] |", review)
        self.assertIn("| plugins/lilith_os/adapter.py | 5 | SECRET:groq-key |", review)
        for raw in RAW_VALUES:
            self.assertNotIn(raw, review)

    # ---- correction 2: fail closed on existing or linked destinations ----
    def test_existing_extracted_is_never_overwritten(self):
        q = self.quarantine()
        (q / "extracted").mkdir()
        sentinel = q / "extracted" / "sentinel.txt"
        sentinel.write_text("TEST_ONLY keep", encoding="utf-8")
        self.assert_failed(self.run_verify(q), "refusing to overwrite existing extracted")
        self.assertEqual(sentinel.read_text(encoding="utf-8"), "TEST_ONLY keep")
        self.assertEqual(sorted(p.name for p in (q / "extracted").iterdir()), ["sentinel.txt"])
        self.assertFalse((q / "REVIEW.md").exists())

    def test_existing_review_is_never_overwritten_and_rerun_refuses(self):
        q = self.quarantine()
        self.assertEqual(self.run_verify(q).returncode, 0)
        before = (q / "REVIEW.md").read_bytes()
        self.assert_failed(self.run_verify(q), "refusing to overwrite existing")
        self.assertEqual((q / "REVIEW.md").read_bytes(), before)
        q2 = self.quarantine(name="q2")
        (q2 / "REVIEW.md").write_text("TEST_ONLY previous review", encoding="utf-8")
        self.assert_failed(self.run_verify(q2, "q2"), "refusing to overwrite existing REVIEW.md")
        self.assertEqual((q2 / "REVIEW.md").read_text(encoding="utf-8"), "TEST_ONLY previous review")
        self.assertFalse((q2 / "extracted").exists())

    def test_quarantine_that_is_a_link_is_refused(self):
        real = self.quarantine(name="real")
        link = self.root / "qlink"
        if not make_junction(link, real):
            self.skipTest("cannot create a junction/symlink here")
        proc = subprocess.run([sys.executable, str(VERIFY), str(link), "--allowlist",
                               str(self.root / "real.allow.tsv"), "--upstream", str(UPSTREAM)],
                              capture_output=True, text=True)
        self.assert_failed(proc, "symlink/junction")
        self.assertFalse((real / "extracted").exists())
        self.assertFalse((real / "REVIEW.md").exists())

    def test_quarantine_under_a_linked_parent_is_refused(self):
        real_parent = self.root / "real_parent"
        real_parent.mkdir()
        q = self.quarantine(name="inner", parent=real_parent)
        link_parent = self.root / "linked_parent"
        if not make_junction(link_parent, real_parent):
            self.skipTest("cannot create a junction/symlink here")
        proc = subprocess.run([sys.executable, str(VERIFY), str(link_parent / "inner"), "--allowlist",
                               str(self.root / "inner.allow.tsv"), "--upstream", str(UPSTREAM)],
                              capture_output=True, text=True)
        self.assert_failed(proc, "symlink/junction")
        self.assertFalse((q / "extracted").exists())

    def test_extracted_that_is_a_link_to_outside_is_refused(self):
        q = self.quarantine()
        outside = self.root / "outside"
        outside.mkdir()
        if not make_junction(q / "extracted", outside):
            self.skipTest("cannot create a junction/symlink here")
        self.assert_failed(self.run_verify(q), "refusing to overwrite existing extracted")
        self.assertEqual(list(outside.iterdir()), [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
