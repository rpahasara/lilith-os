"""Offline contract for review_window.sh: every pinned hash is the real file. TEST_ONLY.
python -m unittest discover -s <this dir> -p "test_*.py" (from the repo root)."""
import hashlib
import re
import subprocess
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
S = REPO / "deploy" / "prod" / "hermes_scripts"
TEXT = (HERE / "review_window.sh").read_text(encoding="utf-8")


def sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def git_main(path: str) -> bytes:
    return subprocess.run(["git", "-C", str(REPO), "show", f"origin/main:{path}"], capture_output=True, check=True).stdout


class PinTests(unittest.TestCase):
    def pin(self, name):
        m = re.search(rf"^{name}=([0-9a-f]{{64}})", TEXT, re.M)
        self.assertIsNotNone(m, name)
        return m.group(1)

    def test_new_is_this_branch_review_script(self):
        self.assertEqual(self.pin("NEW_SHA"), sha((S / "owner_memory_review.py").read_bytes()))

    def test_live_is_mains_review_script(self):
        self.assertEqual(self.pin("LIVE_SHA"), sha(git_main("deploy/prod/hermes_scripts/owner_memory_review.py")))

    def test_dependants_are_this_branch_and_mains(self):
        deps = dict(re.findall(r"\[([a-z_]+\.py)\]=([0-9a-f]{64})", TEXT))
        self.assertEqual(set(deps), {"owner_memory_snapshot.py", "commitment_sync.py"})
        for name, digest in deps.items():
            self.assertEqual(digest, sha((S / name).read_bytes()), name)
            self.assertEqual(digest, sha(git_main(f"deploy/prod/hermes_scripts/{name}")), name)   # #412 leaves them alone

    def test_never_restarts_or_deletes(self):
        for bad in ("systemctl restart", "systemctl stop", "systemctl start", "rm -", "rmdir", "unlink"):
            self.assertNotIn(bad, TEXT, bad)


if __name__ == "__main__":
    unittest.main()
