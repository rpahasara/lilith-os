"""Offline integrity checks for the Hermes integration source. No Hermes, network or credentials needed.

    python -m unittest discover -s integrations/hermes/tests -p "test_*.py"
"""

from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

HERMES = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERMES / "tools"))

import verify_dev_f9c2_source  # noqa: E402

PATCHES = HERMES / "patches"
SHA_LINE = re.compile(r"^[0-9a-f]{64}  [\w./-]+$")


class SourceIntegrityTest(unittest.TestCase):
    def test_dev_release_files_match_the_deployed_manifest(self) -> None:
        self.assertEqual(verify_dev_f9c2_source.verify(), [])

    def test_every_patched_file_has_a_recorded_digest(self) -> None:
        for variant in ("prod-lilith-01", "dev-f9c2"):
            patch = (PATCHES / f"{variant}.patch").read_text(encoding="utf-8")
            touched = set(re.findall(r"^\+\+\+ b/(\S+)$", patch, re.MULTILINE))
            lines = (PATCHES / f"{variant}.sha256").read_text(encoding="utf-8").splitlines()
            self.assertTrue(all(SHA_LINE.match(line) for line in lines), variant)
            self.assertEqual(touched, {line.split("  ", 1)[1] for line in lines}, variant)

    def test_no_token_bearing_release_file_is_tracked_outside_templates(self) -> None:
        release = HERMES / "release" / "dev-f9c2"
        for path in ("home/config.yaml", "profiles/operate/config.yaml", "gate/gate.json", "bin/verify_release.py"):
            self.assertFalse((release / path).exists(), path)
            self.assertTrue((release / "templates" / (path + ".tmpl")).is_file(), path)


if __name__ == "__main__":
    unittest.main()
