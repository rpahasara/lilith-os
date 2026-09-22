"""Deterministic allowlisted Core API bundle tests."""

from __future__ import annotations

import importlib.util
import json
import tarfile
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]


def _module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


builder = _module("bundle_builder", ROOT / "scripts" / "build_core_api_bundle.py")
verifier = _module("bundle_verifier", ROOT / "scripts" / "verify_core_api_bundle.py")


class DeploymentBundleTest(unittest.TestCase):
    SHA = "a" * 40

    def test_bundle_is_deterministic_allowlisted_and_verifiable(self):
        with tempfile.TemporaryDirectory() as value:
            root = Path(value)
            one = root / "one.tar.gz"
            two = root / "two.tar.gz"
            attestation_one = root / "one.json"
            attestation_two = root / "two.json"
            first = builder.build(ROOT, one, attestation_one, self.SHA)
            second = builder.build(ROOT, two, attestation_two, self.SHA)
            self.assertEqual(one.read_bytes(), two.read_bytes())
            self.assertEqual(first, second)
            output = root / "release"
            verified = verifier.verify_and_extract(
                one, attestation_one, output, self.SHA
            )
            self.assertEqual(verified["candidateSha"], self.SHA)
            paths = {entry["path"] for entry in verified["files"]}
            self.assertIn("lilith_memory/canonical_store.py", paths)
            self.assertNotIn("public/assets/assets/animations/hsin-relaxed-idle.vrma", paths)
            self.assertFalse(any("__pycache__" in path for path in paths))
            self.assertEqual(
                json.loads((output / "deployment-manifest.json").read_text())["candidateSha"],
                self.SHA,
            )

    def test_tampered_archive_and_wrong_sha_are_rejected(self):
        with tempfile.TemporaryDirectory() as value:
            root = Path(value)
            archive = root / "bundle.tar.gz"
            attestation = root / "bundle.json"
            builder.build(ROOT, archive, attestation, self.SHA)
            with self.assertRaises(ValueError):
                verifier.verify_and_extract(
                    archive, attestation, root / "bad-sha", "not-a-sha"
                )
            archive.write_bytes(archive.read_bytes() + b"tamper")
            with self.assertRaises(RuntimeError):
                verifier.verify_and_extract(
                    archive, attestation, root / "tampered", self.SHA
                )

    def test_bundle_has_no_links_or_path_traversal(self):
        with tempfile.TemporaryDirectory() as value:
            root = Path(value)
            archive = root / "bundle.tar.gz"
            attestation = root / "bundle.json"
            builder.build(ROOT, archive, attestation, self.SHA)
            with tarfile.open(archive, "r:gz") as tar:
                for member in tar.getmembers():
                    self.assertTrue(member.isfile())
                    self.assertNotIn("..", Path(member.name).parts)


if __name__ == "__main__":
    unittest.main()
