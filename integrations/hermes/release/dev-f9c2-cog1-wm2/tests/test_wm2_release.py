"""Offline acceptance contract for f293e72-f9c2-cog1-wm2 (World Model lane LIVE). TEST_ONLY; no host.

    python -m unittest discover -s integrations/hermes/release/dev-f9c2-cog1-wm2/tests -p "test_*.py"

The release is wm1 with three member changes (RELEASE-DELTA.json): RELEASE_ID, router.yaml (cognitive_mode live) and
the verifier template, whose only change is the lane policy. The verifier helpers come from the cog1 acceptance tests.
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

WM2 = Path(__file__).resolve().parents[1]
REPO = WM2.parents[3]
REL = REPO / "integrations" / "hermes" / "release"
COG1, WM1, F9C2 = REL / "dev-f9c2-cog1", REL / "dev-f9c2-cog1-wm1", REL / "dev-f9c2"
sys.path.insert(0, str(COG1 / "tests"))

import test_cog1_release as C  # noqa: E402  (load_verifier, run_verifier, assemble_dev_cognition, constants)

DELTA = json.loads((WM2 / "RELEASE-DELTA.json").read_text(encoding="utf-8"))
WM1_TEMPLATE = WM1 / "templates" / "bin" / "verify_release.py.tmpl"
WM2_TEMPLATE = WM2 / "templates" / "bin" / "verify_release.py.tmpl"
COG1_ROUTER = REPO / "integrations" / "hermes" / "home" / "variants" / "dev-f9c2" / "router.yaml"
WM1_ROUTER = WM1 / "home" / "router.yaml"
WM2_ROUTER = WM2 / "home" / "router.yaml"
LANES = ("cognitive_enabled", "goals_enabled", "reasoning_enabled", "workspace_enabled", "motivation_enabled",
         "planning_enabled", "ethics_enabled", "social_cognition_enabled", "memory_consolidation_enabled",
         "canonical_ltm_enabled")
LANE_CODES = {"LANE_NOT_OFF", "COGNITIVE_CHANNELS_SET", "SHADOW_LANE_NOT_ON", "SHADOW_LANE_NOT_SHADOW",
              "SHADOW_LANE_CHANNELS", "LANE_MODE_NOT_SHADOW", "WM_LANE_NOT_ON", "WM_LANE_NOT_LIVE",
              "WM_LANE_CHANNELS", "ROUTER_MODE_NOT_SHADOW"}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def changed_lines(a: Path, b: Path) -> tuple[list[str], list[str]]:
    diff = list(difflib.unified_diff(a.read_text(encoding="utf-8").splitlines(),
                                     b.read_text(encoding="utf-8").splitlines(), lineterm="", n=0))
    return ([l[1:] for l in diff if l.startswith("-") and not l.startswith("---")],
            [l[1:] for l in diff if l.startswith("+") and not l.startswith("+++")])


def code(lines: list[str]) -> list[str]:
    return [l for l in lines if not l.lstrip().startswith("#")]


class ReleaseDefinitionTest(unittest.TestCase):
    def test_identity_base_and_members(self):
        self.assertEqual((WM2 / "RELEASE_ID").read_bytes(), b"f293e72-f9c2-cog1-wm2\n")
        self.assertEqual(DELTA["base_release"], (WM1 / "RELEASE_ID").read_text().strip())
        self.assertEqual(set(DELTA["members"]), {"RELEASE_ID", "bin/verify_release.py", "home/router.yaml"})
        for member, change in DELTA["members"].items():
            with self.subTest(member=member):
                if change.get("source"):
                    self.assertEqual(sha(REPO / change["source"]), change["sha256"])
        verifier = DELTA["members"]["bin/verify_release.py"]
        self.assertEqual(sha(REPO / verifier["template"]), verifier["template_sha256"])
        self.assertEqual(sha(REPO / verifier["base_template"]), verifier["base_template_sha256"])
        self.assertEqual(DELTA["members"]["home/router.yaml"]["from"], sha(WM1_ROUTER))
        self.assertEqual(DELTA["members"]["RELEASE_ID"]["from"], sha(WM1 / "RELEASE_ID"))
        # wm1 as merged (#281) and installed on DEV
        self.assertEqual(sha(WM1_ROUTER), "4035f0a175ea6bf130287a49e7428b8ef588bf0b0b4bdb021b6ad27bf84ee57a")
        self.assertEqual(sha(WM1_TEMPLATE), "b69b2344f8637be0fc7488e231c2a91e79fb145a875638f23d16c8257443fbaa")

    def test_router_changes_only_the_world_model_mode(self):
        removed, added = changed_lines(WM1_ROUTER, WM2_ROUTER)
        self.assertEqual(code(removed), ["cognitive_mode: shadow"])
        self.assertEqual(code(added), ["cognitive_mode: live"])
        wm1, wm2 = (yaml.safe_load(p.read_text(encoding="utf-8")) for p in (WM1_ROUTER, WM2_ROUTER))
        self.assertEqual({k: v for k, v in wm2.items() if wm1.get(k) != v}, {"cognitive_mode": "live"})
        self.assertEqual(set(wm2), set(wm1))
        # the router itself stays in shadow: no social switch to the Groq model
        self.assertEqual((wm2["mode"], wm2["live_channels"]), ("shadow", ["lilith_os"]))
        self.assertEqual(wm2["cognitive_channels"], ["lilith_os"])
        self.assertEqual([lane for lane in LANES if wm2[lane] is not False], ["cognitive_enabled"])
        self.assertNotIn("cognitive_draft_dedup", wm2)            # default; writes are refused by the adapter anyway

    def test_verifier_changes_only_the_lane_policy(self):
        removed, added = changed_lines(WM1_TEMPLATE, WM2_TEMPLATE)
        self.assertEqual(code(removed), [
            'SHADOW_LANE = "cognitive_enabled"',
            '        if lane == SHADOW_LANE:',
            '                fail(f"SHADOW_LANE_NOT_ON {lane}")',
            '    if router.get("cognitive_mode") != "shadow":',
            '        fail("SHADOW_LANE_NOT_SHADOW cognitive_mode")',
            '        fail("SHADOW_LANE_CHANNELS cognitive_channels")',
            '        if key.endswith("_mode") and value != "shadow":',
        ])
        self.assertEqual(code(added), [
            'WM_LANE = "cognitive_enabled"',
            '        if lane == WM_LANE:',
            '                fail(f"WM_LANE_NOT_ON {lane}")',
            '    if router.get("cognitive_mode") != "live":',
            '        fail("WM_LANE_NOT_LIVE cognitive_mode")',
            '    if router.get("mode") != "shadow":',
            '        fail("ROUTER_MODE_NOT_SHADOW")',
            '        fail("WM_LANE_CHANNELS cognitive_channels")',
            '        if key.endswith("_mode") and key != "cognitive_mode" and value != "shadow":',
        ])
        cand = WM2_TEMPLATE.read_text(encoding="utf-8")
        self.assertEqual(cand.count(C.PLACEHOLDER), WM1_TEMPLATE.read_text(encoding="utf-8").count(C.PLACEHOLDER))
        for pin in ("WORLD_CONTEXT_ADAPTER_SHA256", "PROD_WORKING_MEMORY_SHA256", "LANES_OFF = ("):
            self.assertIn(pin, cand)                                        # adapter / PROD pins and lane list kept

    def test_no_credential_material(self):
        for p in WM2.rglob("*"):
            if p.is_file() and "__pycache__" not in p.parts:
                text = p.read_text(encoding="utf-8")
                for marker in ("gsk" + "_", "PRIVATE" + " KEY", "BEGIN" + " OPENSSH", "Bearer" + " "):
                    self.assertNotIn(marker, text, p.name)


class VerifierBehaviourTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp(prefix="wm2-verify-"))
        cls.wm1 = C.load_verifier(WM1_TEMPLATE, cls.tmp)
        cls.wm2 = C.load_verifier(WM2_TEMPLATE, cls.tmp)

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

    @staticmethod
    def router(path: Path) -> dict:
        return yaml.safe_load(path.read_text(encoding="utf-8"))

    def test_wm2_accepts_exactly_its_router_and_otherwise_matches_wm1(self):
        root = self.host("wm2", self.router(WM2_ROUTER))
        wm2, wm1 = self.codes(self.wm2, root), self.codes(self.wm1, root)
        self.assertFalse(wm2 & (LANE_CODES | C.WORLD_CONTEXT_CODES))
        self.assertEqual(wm1 & LANE_CODES, {"SHADOW_LANE_NOT_SHADOW", "LANE_MODE_NOT_SHADOW"})  # wm1 refuses live
        self.assertEqual(wm2 - LANE_CODES, wm1 - LANE_CODES)                                  # nothing else differs

    def test_wm2_refuses_the_wm1_and_cog1_routers(self):
        self.assertEqual(self.codes(self.wm2, self.host("wm1-router", self.router(WM1_ROUTER))) & LANE_CODES,
                         {"WM_LANE_NOT_LIVE"})
        self.assertEqual(self.codes(self.wm2, self.host("cog1-router", self.router(COG1_ROUTER))) & LANE_CODES,
                         {"WM_LANE_NOT_ON", "WM_LANE_NOT_LIVE", "WM_LANE_CHANNELS"})

    def test_wm2_refuses_a_live_router_other_channels_and_any_other_lane(self):
        cases = {
            "router-live": ({"mode": "live"}, "ROUTER_MODE_NOT_SHADOW"),
            "router-mode-missing": ({"mode": None}, "ROUTER_MODE_NOT_SHADOW"),
            "shadow": ({"cognitive_mode": "shadow"}, "WM_LANE_NOT_LIVE"),
            "upper-case": ({"cognitive_mode": "LIVE"}, "WM_LANE_NOT_LIVE"),
            "mode-missing": ({"cognitive_mode": None}, "WM_LANE_NOT_LIVE"),
            "all-channels": ({"cognitive_channels": ["*"]}, "WM_LANE_CHANNELS"),
            "telegram-too": ({"cognitive_channels": ["lilith_os", "telegram"]}, "WM_LANE_CHANNELS"),
            "chat-scoped": ({"cognitive_channels": ["lilith_os:one"]}, "WM_LANE_CHANNELS"),
            "no-channel": ({"cognitive_channels": []}, "WM_LANE_CHANNELS"),
            "string-true": ({"cognitive_enabled": "true"}, "WM_LANE_NOT_ON"),
            "goals-live-mode": ({"goals_mode": "live"}, "LANE_MODE_NOT_SHADOW"),
            "planning-live-mode": ({"planning_mode": "live"}, "LANE_MODE_NOT_SHADOW"),
        }
        for lane in LANES[1:]:
            cases[lane] = ({lane: True}, "LANE_NOT_OFF")
        for name, (change, code_) in cases.items():
            with self.subTest(case=name):
                router = dict(self.router(WM2_ROUTER), **change)
                router = {k: v for k, v in router.items() if v is not None}
                self.assertIn(code_, self.codes(self.wm2, self.host(f"case-{name}", router)))

    def test_wm2_still_pins_the_adapter_and_the_prod_module(self):
        root = self.host("adapter-changed", self.router(WM2_ROUTER))
        adapter = root / "home" / "lilith_router" / "world_context.py"
        adapter.write_bytes(adapter.read_bytes() + b"\n# TEST_ONLY\n")
        (root / "home" / "lilith_router" / "_prod_world_context.py").unlink()
        self.assertEqual(self.codes(self.wm2, root) & C.WORLD_CONTEXT_CODES,
                         {"WORLD_CONTEXT_NOT_THE_COG1_ADAPTER", "PROD_WORKING_MEMORY_NOT_PINNED"})


if __name__ == "__main__":
    unittest.main()
