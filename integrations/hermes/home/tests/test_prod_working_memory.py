"""Offline checks for the recovered PROD Working Memory and Router V2 source.

    python -m unittest discover -s integrations/hermes/home/tests -p "test_*.py"
"""

from __future__ import annotations

import ast
import hashlib
import sys
import tempfile
import unittest
from pathlib import Path

HOME = Path(__file__).resolve().parents[1]
REPO = HOME.parents[2]
sys.path.insert(0, str(HOME / "tools"))

import assemble_prod_complete  # noqa: E402

PROD = HOME / "variants" / "prod-lilith-01"
DEV = HOME / "variants" / "dev-f9c2"
WORLD_CONTEXT = PROD / "lilith_router" / "world_context.py"
PROD_SHA = "46b8187e3f6f2ac72c920de9dab12fd9c2841551f6c2aa7c20fd91941e3f0104"
TEMPLATE = PROD / "router.yaml.tmpl"
LANE_MODULES = {"motivation", "planning", "planning_capabilities", "ethics"}


class ProdWorkingMemoryTest(unittest.TestCase):
    def test_world_context_is_the_exact_deployed_prod_file(self) -> None:
        data = WORLD_CONTEXT.read_bytes()
        self.assertEqual(len(data), 91351)
        self.assertEqual(hashlib.sha256(data).hexdigest(), PROD_SHA)

    def test_world_context_is_not_the_dev_stub(self) -> None:
        stub = (DEV / "lilith_router" / "world_context.py").read_bytes()
        self.assertLess(len(stub), 1024)
        self.assertNotEqual(hashlib.sha256(stub).hexdigest(), PROD_SHA)
        self.assertNotEqual(stub, WORLD_CONTEXT.read_bytes())

    def test_world_context_contains_every_tracked_slice_block_verbatim(self) -> None:
        text = WORLD_CONTEXT.read_text(encoding="utf-8")
        blocks = sorted(REPO.glob("docs/architecture/slice-*/world_context*.py"))
        self.assertEqual(len(blocks), 6)
        for block in blocks:
            with self.subTest(block=block.relative_to(REPO).as_posix()):
                self.assertIn(block.read_text(encoding="utf-8").strip(), text)

    def test_world_context_depends_only_on_stdlib_and_router_lanes(self) -> None:
        tree = ast.parse(WORLD_CONTEXT.read_text(encoding="utf-8"))
        top, lazy = set(), set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names = {alias.name.split(".")[0] for alias in node.names}
            elif isinstance(node, ast.ImportFrom):
                names = {alias.name for alias in node.names} if node.level else {node.module.split(".")[0]}
            else:
                continue
            (top if node in tree.body else lazy).update(names)
        self.assertEqual(top, {"__future__", "hashlib", "json", "logging", "re", "urllib"})
        self.assertEqual(lazy - {"hashlib", "time", "datetime"}, LANE_MODULES)

    def test_router_template_hides_only_the_channel_id(self) -> None:
        text = TEMPLATE.read_text(encoding="utf-8")
        self.assertEqual(text.count("__LILITH_DISCORD_CHANNEL_ID__"), 1)
        self.assertIsNone(__import__("re").search(r"[0-9]{17,20}", text))

    def test_complete_prod_tree_assembles_byte_exact_except_private_config(self) -> None:
        with tempfile.TemporaryDirectory() as out:
            problems, pending = assemble_prod_complete.assemble(Path(out))
            self.assertEqual(problems, [])
            self.assertEqual(pending, ["PRIVATE_VALUE_REQUIRED lilith_router/router.yaml"])
            tests = sorted(p.name for p in (Path(out) / "lilith_router" / "tests").glob("test_*.py"))
            self.assertEqual(len(tests), 13)
            wc = Path(out) / "lilith_router" / "world_context.py"
            self.assertEqual(hashlib.sha256(wc.read_bytes()).hexdigest(), PROD_SHA)


if __name__ == "__main__":
    unittest.main()
