"""Offline checks for the Router V2 HERMES_HOME source map.

    python -m unittest discover -s integrations/hermes/home/tests -p "test_*.py"
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

HOME = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HOME / "tools"))

import assemble_home  # noqa: E402

PROD_WORLD_CONTEXT = "46b8187e3f6f2ac72c920de9dab12fd9c2841551f6c2aa7c20fd91941e3f0104"
DEV_WORLD_CONTEXT_STUB = "5c1fbf98"


class AssembleHomeTest(unittest.TestCase):
    def test_dev_tree_is_complete_and_byte_exact(self) -> None:
        with tempfile.TemporaryDirectory() as out:
            problems, gaps = assemble_home.assemble("dev-f9c2", Path(out))
            self.assertEqual((problems, gaps), ([], []))
            files = [p for p in Path(out).rglob("*") if p.is_file()]
            self.assertEqual(len(files), len(assemble_home.load("dev-f9c2")))

    def test_prod_gaps_are_exactly_the_vm_only_files(self) -> None:
        problems, gaps = assemble_home.assemble("prod-lilith-01", None)
        self.assertEqual(problems, [])
        self.assertEqual(sorted(g.split()[1] for g in gaps), ["lilith_router/world_context.py", "router.yaml"])

    def test_dev_stub_is_never_presented_as_the_prod_lane(self) -> None:
        prod = assemble_home.load("prod-lilith-01")["lilith_router/world_context.py"]
        dev = assemble_home.load("dev-f9c2")["lilith_router/world_context.py"]
        self.assertEqual(prod["sha256"], PROD_WORLD_CONTEXT)
        self.assertIsNone(prod["source"])
        self.assertTrue(dev["sha256"].startswith(DEV_WORLD_CONTEXT_STUB))

    def test_shared_lane_modules_are_not_duplicated(self) -> None:
        for variant in ("prod-lilith-01", "dev-f9c2"):
            for rel, entry in assemble_home.load(variant).items():
                if entry["source"] and not entry["source"].startswith("integrations/hermes/home/"):
                    self.assertFalse((HOME / rel).exists(), f"{rel} duplicated under home/")


if __name__ == "__main__":
    unittest.main()
