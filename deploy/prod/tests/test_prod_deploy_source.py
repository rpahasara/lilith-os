"""The PROD deploy sources: the router mirror is exactly what the reviewed overlay ships, and every file is deployable."""
import ast
import hashlib
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
MIRROR = ROOT / "deploy/prod/lilith_router"
OVERLAY = ROOT / "integrations/hermes/overlays/prod-canonical-memory-context"
ALLOWED = __import__("re").compile(r"^([a-z_][a-z0-9_]*\.py|router\.yaml)$")


class MirrorTests(unittest.TestCase):
    def test_names_are_deployable(self):
        names = sorted(p.name for p in MIRROR.iterdir() if p.name != ".gitattributes")
        self.assertIn("router.yaml", names)
        self.assertGreaterEqual(len(names), 30)
        for name in names:
            self.assertRegex(name, ALLOWED)

    def test_every_python_file_compiles(self):
        for path in MIRROR.glob("*.py"):
            ast.parse(path.read_text(encoding="utf-8"), str(path))

    def test_router_yaml_is_a_mapping(self):
        try:
            import yaml
        except ImportError:
            self.skipTest("PyYAML not installed")
        self.assertIsInstance(yaml.safe_load((MIRROR / "router.yaml").read_text(encoding="utf-8")), dict)

    def test_overlay_files_equal_the_mirror(self):
        for name in ("canonical_memory.py", "lilith_memory_context.py", "gateway_integration.py"):
            self.assertEqual(hashlib.sha256((MIRROR / name).read_bytes()).hexdigest(),
                             hashlib.sha256((OVERLAY / name).read_bytes()).hexdigest(), name)

    def test_no_line_endings_or_settings_files(self):
        for path in MIRROR.iterdir():
            if path.name == ".gitattributes":
                continue
            self.assertNotIn(b"\r\n", path.read_bytes(), path.name)
        self.assertFalse((MIRROR / "canonical_memory.json").exists())   # root-owned settings stay on the host


if __name__ == "__main__":
    unittest.main()
