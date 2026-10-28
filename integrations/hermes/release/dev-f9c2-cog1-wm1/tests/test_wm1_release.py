"""Offline acceptance contract for f293e72-f9c2-cog1-wm1 (World Model lane in shadow). TEST_ONLY; no host.

    python -m unittest discover -s integrations/hermes/release/dev-f9c2-cog1-wm1/tests -p "test_*.py"

The release is cog1 with three member changes (RELEASE-DELTA.json): RELEASE_ID, router.yaml and the verifier
template, whose only change is the lane policy. The verifier helpers come from the cog1 acceptance tests.
"""

from __future__ import annotations

import difflib
import hashlib
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

WM1 = Path(__file__).resolve().parents[1]
REPO = WM1.parents[3]
COG1 = REPO / "integrations" / "hermes" / "release" / "dev-f9c2-cog1"
F9C2 = REPO / "integrations" / "hermes" / "release" / "dev-f9c2"
sys.path.insert(0, str(COG1 / "tests"))

import test_cog1_release as C  # noqa: E402  (load_verifier, run_verifier, assemble_dev_cognition, constants)

DELTA = json.loads((WM1 / "RELEASE-DELTA.json").read_text(encoding="utf-8"))
COG1_TEMPLATE = COG1 / "templates" / "bin" / "verify_release.py.tmpl"
WM1_TEMPLATE = WM1 / "templates" / "bin" / "verify_release.py.tmpl"
COG1_ROUTER = REPO / "integrations" / "hermes" / "home" / "variants" / "dev-f9c2" / "router.yaml"
WM1_ROUTER = WM1 / "home" / "router.yaml"
LANES = ("cognitive_enabled", "goals_enabled", "reasoning_enabled", "workspace_enabled", "motivation_enabled",
         "planning_enabled", "ethics_enabled", "social_cognition_enabled", "memory_consolidation_enabled",
         "canonical_ltm_enabled")
LANE_CODES = {"LANE_NOT_OFF", "COGNITIVE_CHANNELS_SET", "SHADOW_LANE_NOT_ON", "SHADOW_LANE_NOT_SHADOW",
              "SHADOW_LANE_CHANNELS", "LANE_MODE_NOT_SHADOW"}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def changed_lines(a: Path, b: Path) -> tuple[list[str], list[str]]:
    diff = list(difflib.unified_diff(a.read_text(encoding="utf-8").splitlines(),
                                     b.read_text(encoding="utf-8").splitlines(), lineterm="", n=0))
    return ([l[1:] for l in diff if l.startswith("-") and not l.startswith("---")],
            [l[1:] for l in diff if l.startswith("+") and not l.startswith("+++")])


class ReleaseDefinitionTest(unittest.TestCase):
    def test_identity_base_and_members(self):
        self.assertEqual((WM1 / "RELEASE_ID").read_bytes(), b"f293e72-f9c2-cog1-wm1\n")
        self.assertEqual(DELTA["base_release"], (COG1 / "RELEASE_ID").read_text().strip())
        self.assertEqual(set(DELTA["members"]), {"RELEASE_ID", "bin/verify_release.py", "home/router.yaml"})
        for member, change in DELTA["members"].items():
            with self.subTest(member=member):
                if change.get("source"):
                    self.assertEqual(sha(REPO / change["source"]), change["sha256"])
        verifier = DELTA["members"]["bin/verify_release.py"]
        self.assertEqual(sha(REPO / verifier["template"]), verifier["template_sha256"])
        self.assertEqual(sha(REPO / verifier["base_template"]), verifier["base_template_sha256"])
        self.assertEqual(DELTA["members"]["home/router.yaml"]["from"], sha(COG1_ROUTER))
        self.assertEqual(sha(COG1_ROUTER), "7bb4fbb5cb0db6c711a8094d1678ebba8ae93c5a561b2fa5794a85686ec82b15")

    def test_router_changes_only_the_world_model_lane(self):
        removed, added = changed_lines(COG1_ROUTER, WM1_ROUTER)
        self.assertEqual(removed, ["# Every cognitive lane OFF (the DEV world_context.py is an import-only stub).",
                                   "cognitive_enabled: false", "cognitive_channels: []"])
        self.assertEqual([l for l in added if not l.startswith("#")],
                         ["cognitive_enabled: true", "cognitive_mode: shadow", "cognitive_channels:", "  - lilith_os"])
        base, wm1 = (yaml.safe_load(p.read_text(encoding="utf-8")) for p in (COG1_ROUTER, WM1_ROUTER))
        self.assertEqual({k: v for k, v in wm1.items() if base.get(k) != v},
                         {"cognitive_enabled": True, "cognitive_mode": "shadow", "cognitive_channels": ["lilith_os"]})
        self.assertEqual((wm1["mode"], wm1["live_channels"]), ("shadow", ["lilith_os"]))
        self.assertEqual([lane for lane in LANES if wm1[lane] is not False], ["cognitive_enabled"])

    def test_verifier_changes_only_the_lane_policy(self):
        removed, added = changed_lines(COG1_TEMPLATE, WM1_TEMPLATE)
        self.assertEqual(removed, ['        if router.get(lane) is not False:', '    if router.get("cognitive_channels"):',
                                   '        fail("COGNITIVE_CHANNELS_SET")'])
        self.assertEqual(len(added), 13)
        self.assertIn('SHADOW_LANE = "cognitive_enabled"', added)
        cand = WM1_TEMPLATE.read_text(encoding="utf-8")
        self.assertEqual(cand.count(C.PLACEHOLDER), COG1_TEMPLATE.read_text(encoding="utf-8").count(C.PLACEHOLDER))
        for pin in ("WORLD_CONTEXT_ADAPTER_SHA256", "PROD_WORKING_MEMORY_SHA256", "LANES_OFF = ("):
            self.assertIn(pin, cand)                                        # adapter / PROD pins and lane list kept

    def test_no_credential_material(self):
        for p in WM1.rglob("*"):
            if p.is_file() and "__pycache__" not in p.parts:
                text = p.read_text(encoding="utf-8")
                for marker in ("gsk" + "_", "PRIVATE" + " KEY", "BEGIN" + " OPENSSH", "Bearer" + " "):
                    self.assertNotIn(marker, text, p.name)


class VerifierBehaviourTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp(prefix="wm1-verify-"))
        cls.cog1 = C.load_verifier(COG1_TEMPLATE, cls.tmp)
        cls.wm1 = C.load_verifier(WM1_TEMPLATE, cls.tmp)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, True)

    def host(self, name: str, router: dict) -> Path:
        root = self.tmp / name
        home = root / "home"
        assert C.assemble_dev_cognition.assemble(home) == []
        (home / "router.yaml").unlink()
        (home / "lilith_router" / "router.yaml").write_text(yaml.safe_dump(router), encoding="utf-8")
        config = (F9C2 / "templates" / "home" / "config.yaml.tmpl").read_text(encoding="utf-8")
        (home / "config.yaml").write_text(config.replace(C.PLACEHOLDER, C.TEST_TOKEN), encoding="utf-8")
        for d in C.RO_STUBS:
            (home / d).mkdir()
        (home / "cron").mkdir()
        (home / "cron" / "jobs.json").write_text('{"jobs": []}\n', encoding="utf-8")
        (root / "opt" / "releases").mkdir(parents=True)
        (root / "opt" / "current").mkdir()
        (root / "etc-gateway").mkdir()
        (root / "etc-gateway" / "critical.sha256").write_text("", encoding="utf-8")
        (root / "etc-gate" / "credentials").mkdir(parents=True)
        gate = (F9C2 / "templates" / "gate" / "gate.json.tmpl").read_text(encoding="utf-8")
        (root / "etc-gate" / "gate.json").write_text(gate.replace(C.PLACEHOLDER, C.TEST_TOKEN), encoding="utf-8")
        return root

    def codes(self, module, root: Path) -> set[str]:
        return C.run_verifier(module, root)

    @property
    def wm1_router(self) -> dict:
        return yaml.safe_load(WM1_ROUTER.read_text(encoding="utf-8"))

    def test_wm1_accepts_exactly_its_router_and_otherwise_matches_cog1(self):
        root = self.host("wm1", self.wm1_router)
        wm1, cog1 = self.codes(self.wm1, root), self.codes(self.cog1, root)
        self.assertFalse(wm1 & (LANE_CODES | C.WORLD_CONTEXT_CODES))
        self.assertEqual(cog1 & LANE_CODES, {"LANE_NOT_OFF", "COGNITIVE_CHANNELS_SET"})   # cog1 refuses the lane
        self.assertEqual(wm1 - LANE_CODES, cog1 - LANE_CODES)                              # nothing else differs

    def test_wm1_refuses_the_lanes_off_router(self):
        root = self.host("cog1-router", yaml.safe_load(COG1_ROUTER.read_text(encoding="utf-8")))
        self.assertEqual(self.codes(self.wm1, root) & LANE_CODES,
                         {"SHADOW_LANE_NOT_ON", "SHADOW_LANE_NOT_SHADOW", "SHADOW_LANE_CHANNELS"})
        self.assertFalse(self.codes(self.cog1, root) & LANE_CODES)

    def test_wm1_refuses_live_cognition_other_channels_and_any_other_lane(self):
        cases = {
            "live": ({"cognitive_mode": "live"}, "SHADOW_LANE_NOT_SHADOW"),
            "mode-missing": ({"cognitive_mode": None}, "SHADOW_LANE_NOT_SHADOW"),
            "all-channels": ({"cognitive_channels": ["*"]}, "SHADOW_LANE_CHANNELS"),
            "telegram-too": ({"cognitive_channels": ["lilith_os", "telegram"]}, "SHADOW_LANE_CHANNELS"),
            "chat-scoped": ({"cognitive_channels": ["lilith_os:one"]}, "SHADOW_LANE_CHANNELS"),
            "no-channel": ({"cognitive_channels": []}, "SHADOW_LANE_CHANNELS"),
            "string-true": ({"cognitive_enabled": "true"}, "SHADOW_LANE_NOT_ON"),
            "goals-live-mode": ({"goals_mode": "live"}, "LANE_MODE_NOT_SHADOW"),
        }
        for lane in LANES[1:]:
            cases[lane] = ({lane: True}, "LANE_NOT_OFF")
        for name, (change, code) in cases.items():
            with self.subTest(case=name):
                router = dict(self.wm1_router, **change)
                router = {k: v for k, v in router.items() if v is not None}
                self.assertIn(code, self.codes(self.wm1, self.host(f"case-{name}", router)))

    def test_wm1_still_pins_the_adapter_and_the_prod_module(self):
        root = self.host("adapter-changed", self.wm1_router)
        adapter = root / "home" / "lilith_router" / "world_context.py"
        adapter.write_bytes(adapter.read_bytes() + b"\n# TEST_ONLY\n")
        (root / "home" / "lilith_router" / "_prod_world_context.py").unlink()
        self.assertEqual(self.codes(self.wm1, root) & C.WORLD_CONTEXT_CODES,
                         {"WORLD_CONTEXT_NOT_THE_COG1_ADAPTER", "PROD_WORKING_MEMORY_NOT_PINNED"})


if __name__ == "__main__":
    unittest.main()
