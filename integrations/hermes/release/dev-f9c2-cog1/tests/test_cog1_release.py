"""Offline acceptance contract for the DEV release candidate f293e72-f9c2-cog1. TEST_ONLY; no host, no network.

    python -m unittest discover -s integrations/hermes/release/dev-f9c2-cog1/tests -p "test_*.py"

The candidate is the f9c2 package with the four member changes in RELEASE-DELTA.json. The historical f9c2 release
and its own tests (which require the import stub) are left as they are. Routing, lane and transport behaviour of the
adapter are covered by integrations/hermes/overlays/dev-unified-cognition/tests.
"""

from __future__ import annotations

import difflib
import hashlib
import importlib.util
import io
import json
import shutil
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

COG1 = Path(__file__).resolve().parents[1]
REPO = COG1.parents[3]
F9C2 = REPO / "integrations" / "hermes" / "release" / "dev-f9c2"
sys.path.insert(0, str(REPO / "integrations" / "hermes" / "overlays" / "dev-unified-cognition" / "tools"))

import assemble_dev_cognition  # noqa: E402

DELTA = json.loads((COG1 / "RELEASE-DELTA.json").read_text(encoding="utf-8"))
PLACEHOLDER = "__LILITH_GATE_CLIENT_TOKEN__"
TEST_TOKEN = "TEST_ONLY-" + "c0" * 20
STUB_SHA = "5c1fbf98ead049013aa79fdfb4e74dd3dd210ab0c3386f257ce0b4e334e6a3d5"
PROD_SHA = "46b8187e3f6f2ac72c920de9dab12fd9c2841551f6c2aa7c20fd91941e3f0104"
WORLD_CONTEXT_CODES = {"WORLD_CONTEXT_NOT_THE_F7_STUB", "WORLD_CONTEXT_NOT_THE_COG1_ADAPTER",
                       "PROD_WORKING_MEMORY_NOT_PINNED"}
RO_STUBS = ("skills", "optional-skills", "optional-mcps", "hooks", "scripts", "bin", "node", "node_modules")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def base_manifest() -> dict[str, str]:
    entries = {}
    for line in (F9C2 / "MANIFEST.sha256").read_text(encoding="utf-8").splitlines():
        digest, path = line.split("  ", 1)
        entries[path.removeprefix("./")] = digest
    return entries


def candidate_manifest() -> dict[str, str | None]:
    entries: dict[str, str | None] = dict(base_manifest())
    for member, change in DELTA["members"].items():
        entries[member] = change["sha256"]
    return entries


def home_files(root: Path) -> dict[str, str]:
    """``home/...`` digests of an assembled HERMES_HOME code tree, in package member names."""
    return {"home/" + p.relative_to(root).as_posix(): sha(p)
            for p in root.rglob("*") if p.is_file() and "__pycache__" not in p.parts}


def load_verifier(template: Path, out: Path):
    rendered = out / f"verify_{template.parents[2].name.replace('-', '_')}.py"
    rendered.write_text(template.read_text(encoding="utf-8").replace(PLACEHOLDER, TEST_TOKEN), encoding="utf-8")
    spec = importlib.util.spec_from_file_location(rendered.stem, rendered)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def run_verifier(module, root: Path) -> set[str]:
    """Run the release gate against a fixture host rooted at ``root``; return its failure codes."""
    module.BASE, module.HH = root / "opt", root / "home"
    module.ETC, module.GATE_ETC = root / "etc-gateway", root / "etc-gate"
    module.failures = []
    with redirect_stdout(io.StringIO()):
        module.main(["--pre-start"])
    return {f.split(" ", 1)[0] for f in module.failures}


class ReleaseDefinitionTest(unittest.TestCase):
    def test_release_identity_and_base(self):
        self.assertEqual((COG1 / "RELEASE_ID").read_bytes(), b"f293e72-f9c2-cog1\n")
        self.assertEqual(DELTA["release"], "f293e72-f9c2-cog1")
        self.assertEqual(DELTA["base_release"], (F9C2 / "RELEASE_ID").read_text().strip())
        self.assertEqual(sha(REPO / DELTA["base_manifest"]), DELTA["base_manifest_sha256"])

    def test_delta_starts_from_the_recorded_base_members(self):
        base = base_manifest()
        self.assertEqual(set(DELTA["members"]), {"RELEASE_ID", "bin/verify_release.py",
                                                 "home/lilith_router/world_context.py",
                                                 "home/lilith_router/_prod_world_context.py"})
        for member, change in DELTA["members"].items():
            with self.subTest(member=member):
                if change["change"] == "add":
                    self.assertNotIn(member, base)
                else:
                    self.assertEqual(base[member], change["from"])
                if change.get("source"):
                    self.assertEqual(sha(REPO / change["source"]), change["sha256"])
        self.assertEqual(base["home/lilith_router/world_context.py"], STUB_SHA)
        self.assertEqual(DELTA["members"]["home/lilith_router/_prod_world_context.py"]["sha256"], PROD_SHA)

    def test_delta_and_overlay_name_the_same_adapter(self):
        overlay = assemble_dev_cognition.load()["files"]
        self.assertEqual(DELTA["members"]["home/lilith_router/world_context.py"]["sha256"],
                         overlay["lilith_router/world_context.py"]["sha256"])
        self.assertEqual(overlay["lilith_router/_prod_world_context.py"]["sha256"], PROD_SHA)

    def test_historical_f9c2_inputs_are_untouched(self):
        verifier = DELTA["members"]["bin/verify_release.py"]
        self.assertEqual(sha(REPO / verifier["base_template"]), verifier["base_template_sha256"])
        self.assertEqual(sha(REPO / verifier["template"]), verifier["template_sha256"])
        self.assertIn(rb'"\nDEV_IMPORT_STUB = True\n" not in', (REPO / verifier["base_template"]).read_bytes())
        f7 = F9C2 / "tests" / "test_f7_offline.py"
        self.assertEqual(sha(f7), base_manifest()["tests/test_f7_offline.py"])   # still asserts the stub, for f9c2


class HomeTreeTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="cog1-home-"))
        self.addCleanup(shutil.rmtree, self.tmp, True)

    def test_candidate_home_is_the_base_home_with_exactly_the_delta(self):
        assert assemble_dev_cognition.assemble(self.tmp) == []
        built = home_files(self.tmp)
        expected = {m: d for m, d in candidate_manifest().items()
                    if m.startswith("home/") and m != "home/config.yaml"}     # config.yaml: template, not code
        self.assertEqual(built, expected)
        changed = {m for m in expected if base_manifest().get(m) != expected[m]}
        self.assertEqual(changed, {"home/lilith_router/world_context.py", "home/lilith_router/_prod_world_context.py"})

    def test_rollback_restores_the_exact_f9c2_home(self):
        assert assemble_dev_cognition.assemble(self.tmp) == []
        lr = self.tmp / "lilith_router"
        (lr / "_prod_world_context.py").unlink()
        shutil.copyfile(REPO / "integrations/hermes/home/variants/dev-f9c2/lilith_router/world_context.py",
                        lr / "world_context.py")
        self.assertEqual(home_files(self.tmp),
                         {m: d for m, d in base_manifest().items() if m.startswith("home/") and m != "home/config.yaml"})

    def test_critical_pin_already_covers_the_new_file(self):
        pin = (F9C2 / "bin" / "pin_critical.sh").read_text(encoding="utf-8")
        self.assertIn('find "${HH}/lilith_router" "${HH}/plugins" -type f ! -path \'*/__pycache__/*\'', pin)


class VerifierChangeTest(unittest.TestCase):
    def test_template_changes_only_the_world_context_check(self):
        base = (REPO / DELTA["members"]["bin/verify_release.py"]["base_template"]).read_text(encoding="utf-8")
        cand = (COG1 / "templates" / "bin" / "verify_release.py.tmpl").read_text(encoding="utf-8")
        removed = [l[1:] for l in difflib.unified_diff(base.splitlines(), cand.splitlines(), lineterm="", n=0)
                   if l.startswith("-") and not l.startswith("---")]
        added = [l[1:] for l in difflib.unified_diff(base.splitlines(), cand.splitlines(), lineterm="", n=0)
                 if l.startswith("+") and not l.startswith("+++")]
        self.assertEqual(removed, [
            "    # The DEV world_context is an import stub; it is only acceptable while every lane above is off.",
            '    if "\\nDEV_IMPORT_STUB = True\\n" not in (HH / "lilith_router" / "world_context.py").read_text():',
            '        fail("WORLD_CONTEXT_NOT_THE_F7_STUB")',
        ])
        self.assertEqual(len(added), 11)
        self.assertTrue(all("fail(" not in l or "fail(code)" in l for l in added))
        self.assertIn("LANES_OFF = (", cand)                      # the lanes-off pin is untouched
        self.assertEqual(cand.count(PLACEHOLDER), base.count(PLACEHOLDER))

    def test_no_credential_material_in_the_candidate(self):
        for p in COG1.rglob("*"):
            if p.is_file() and "__pycache__" not in p.parts:
                text = p.read_text(encoding="utf-8")
                with self.subTest(file=p.name):
                    for marker in ("gsk" + "_", "PRIVATE" + " KEY", "BEGIN" + " OPENSSH", "Bearer" + " "):
                        self.assertNotIn(marker, text, p.name)


class VerifierBehaviourTest(unittest.TestCase):
    """Both verifiers rendered with a synthetic token, run against the same non-root fixture hosts."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp(prefix="cog1-verify-"))
        cls.f9c2 = load_verifier(F9C2 / "templates" / "bin" / "verify_release.py.tmpl", cls.tmp)
        cls.cog1 = load_verifier(COG1 / "templates" / "bin" / "verify_release.py.tmpl", cls.tmp)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, True)

    def host(self, name: str) -> Path:
        root = self.tmp / name
        home = root / "home"
        assert assemble_dev_cognition.assemble(home) == []
        (home / "router.yaml").replace(home / "lilith_router" / "router.yaml")       # as install.sh places it
        config = (F9C2 / "templates" / "home" / "config.yaml.tmpl").read_text(encoding="utf-8")
        (home / "config.yaml").write_text(config.replace(PLACEHOLDER, TEST_TOKEN), encoding="utf-8")
        for d in RO_STUBS:
            (home / d).mkdir()
        (home / "cron").mkdir()
        (home / "cron" / "jobs.json").write_text('{"jobs": []}\n', encoding="utf-8")
        (root / "opt" / "releases").mkdir(parents=True)
        (root / "opt" / "current").mkdir()
        (root / "etc-gateway").mkdir()
        (root / "etc-gateway" / "critical.sha256").write_text("", encoding="utf-8")
        (root / "etc-gate" / "credentials").mkdir(parents=True)
        gate = (F9C2 / "templates" / "gate" / "gate.json.tmpl").read_text(encoding="utf-8")
        (root / "etc-gate" / "gate.json").write_text(gate.replace(PLACEHOLDER, TEST_TOKEN), encoding="utf-8")
        return root

    def to_stub(self, root: Path) -> None:
        lr = root / "home" / "lilith_router"
        (lr / "_prod_world_context.py").unlink()
        shutil.copyfile(REPO / "integrations/hermes/home/variants/dev-f9c2/lilith_router/world_context.py",
                        lr / "world_context.py")

    def test_cog1_accepts_its_tree_and_differs_from_f9c2_only_in_the_world_context_check(self):
        root = self.host("cog1")
        cog1, f9c2 = run_verifier(self.cog1, root), run_verifier(self.f9c2, root)
        self.assertFalse(cog1 & WORLD_CONTEXT_CODES)
        self.assertFalse(cog1 & {"LANE_NOT_OFF", "COGNITIVE_CHANNELS_SET", "ROUTER_SCOPE", "GATE_PIN", "MODEL_PIN"})
        self.assertIn("WORLD_CONTEXT_NOT_THE_F7_STUB", f9c2)   # why f9c2 cannot start the overlay as is
        self.assertEqual(cog1 - WORLD_CONTEXT_CODES, f9c2 - WORLD_CONTEXT_CODES)

    def test_cog1_refuses_the_stub_and_f9c2_accepts_it_after_rollback(self):
        root = self.host("rolled-back")
        self.to_stub(root)
        self.assertFalse(run_verifier(self.f9c2, root) & WORLD_CONTEXT_CODES)
        self.assertEqual(run_verifier(self.cog1, root) & WORLD_CONTEXT_CODES,
                         {"WORLD_CONTEXT_NOT_THE_COG1_ADAPTER", "PROD_WORKING_MEMORY_NOT_PINNED"})

    def test_cog1_refuses_a_changed_or_missing_prod_module(self):
        root = self.host("prod-changed")
        prod = root / "home" / "lilith_router" / "_prod_world_context.py"
        prod.write_bytes(prod.read_bytes() + b"\n# TEST_ONLY\n")
        self.assertIn("PROD_WORKING_MEMORY_NOT_PINNED", run_verifier(self.cog1, root))
        prod.unlink()
        self.assertIn("PROD_WORKING_MEMORY_NOT_PINNED", run_verifier(self.cog1, root))
        adapter = root / "home" / "lilith_router" / "world_context.py"
        adapter.write_bytes(adapter.read_bytes().replace(b"MAX_CALLS_PER_ENTRY = 16", b"MAX_CALLS_PER_ENTRY = 99"))
        self.assertIn("WORLD_CONTEXT_NOT_THE_COG1_ADAPTER", run_verifier(self.cog1, root))

    def test_cog1_still_refuses_any_enabled_lane(self):
        import yaml
        root = self.host("lane-on")
        router = root / "home" / "lilith_router" / "router.yaml"
        data = yaml.safe_load(router.read_text(encoding="utf-8"))
        for lane in self.cog1.LANES_OFF:
            with self.subTest(lane=lane):
                router.write_text(yaml.safe_dump(dict(data, **{lane: True})), encoding="utf-8")
                self.assertIn("LANE_NOT_OFF", run_verifier(self.cog1, root))
        router.write_text(yaml.safe_dump(dict(data, cognitive_channels=["lilith_os"])), encoding="utf-8")
        self.assertIn("COGNITIVE_CHANNELS_SET", run_verifier(self.cog1, root))


if __name__ == "__main__":
    unittest.main()
