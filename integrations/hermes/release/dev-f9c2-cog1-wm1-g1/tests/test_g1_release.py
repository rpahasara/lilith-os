"""Offline acceptance contract for f293e72-f9c2-cog1-wm1-g1 (World Model and Goals lanes in shadow). TEST_ONLY.

    python -m unittest discover -s integrations/hermes/release/dev-f9c2-cog1-wm1-g1/tests -p "test_*.py"

The release is wm1 with three member changes (RELEASE-DELTA.json): RELEASE_ID, router.yaml and the verifier template,
whose only change is the lane policy. The verifier helpers come from the cog1 acceptance tests.
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

G1 = Path(__file__).resolve().parents[1]
REPO = G1.parents[3]
REL = REPO / "integrations" / "hermes" / "release"
COG1 = REL / "dev-f9c2-cog1"
WM1 = REL / "dev-f9c2-cog1-wm1"
F9C2 = REL / "dev-f9c2"
sys.path.insert(0, str(COG1 / "tests"))

import test_cog1_release as C  # noqa: E402  (load_verifier, run_verifier, assemble_dev_cognition, constants)

DELTA = json.loads((G1 / "RELEASE-DELTA.json").read_text(encoding="utf-8"))
WM1_TEMPLATE = WM1 / "templates" / "bin" / "verify_release.py.tmpl"
G1_TEMPLATE = G1 / "templates" / "bin" / "verify_release.py.tmpl"
WM1_ROUTER = WM1 / "home" / "router.yaml"
G1_ROUTER = G1 / "home" / "router.yaml"
CONFIG_PY = REPO / "integrations" / "hermes" / "home" / "lilith_router" / "config.py"
LANES = ("cognitive_enabled", "goals_enabled", "reasoning_enabled", "workspace_enabled", "motivation_enabled",
         "planning_enabled", "ethics_enabled", "social_cognition_enabled", "memory_consolidation_enabled",
         "canonical_ltm_enabled")
LANE_CODES = {"LANE_NOT_OFF", "SHADOW_LANE_NOT_ON", "SHADOW_LANE_NOT_SHADOW", "SHADOW_LANE_CHANNELS",
              "LANE_MODE_NOT_SHADOW", "ROUTER_KEY_UNKNOWN", "ROUTER_MODE_NOT_SHADOW", "ROUTER_SCOPE"}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def changed_lines(a: Path, b: Path) -> tuple[list[str], list[str]]:
    diff = list(difflib.unified_diff(a.read_text(encoding="utf-8").splitlines(),
                                     b.read_text(encoding="utf-8").splitlines(), lineterm="", n=0))
    return ([l[1:] for l in diff if l.startswith("-") and not l.startswith("---")],
            [l[1:] for l in diff if l.startswith("+") and not l.startswith("+++")])


def kinds(codes: set[str]) -> set[str]:
    return {c.split(" ", 1)[0] for c in codes}


class ReleaseDefinitionTest(unittest.TestCase):
    def test_identity_base_and_members(self):
        self.assertEqual((G1 / "RELEASE_ID").read_bytes(), b"f293e72-f9c2-cog1-wm1-g1\n")
        self.assertEqual(DELTA["release"], "f293e72-f9c2-cog1-wm1-g1")
        self.assertEqual(DELTA["base_release"], (WM1 / "RELEASE_ID").read_text().strip())
        self.assertEqual(set(DELTA["members"]), {"RELEASE_ID", "bin/verify_release.py", "home/router.yaml"})
        for member, change in DELTA["members"].items():
            with self.subTest(member=member):
                if change.get("source"):
                    self.assertEqual(sha(REPO / change["source"]), change["sha256"])
        self.assertEqual(DELTA["members"]["RELEASE_ID"]["from"], sha(WM1 / "RELEASE_ID"))
        verifier = DELTA["members"]["bin/verify_release.py"]
        self.assertEqual(sha(REPO / verifier["template"]), verifier["template_sha256"])
        self.assertEqual(sha(REPO / verifier["base_template"]), verifier["base_template_sha256"])
        self.assertEqual(verifier["base_template_sha256"],
                         "b69b2344f8637be0fc7488e231c2a91e79fb145a875638f23d16c8257443fbaa")   # installed wm1 template
        self.assertEqual(DELTA["members"]["home/router.yaml"]["from"], sha(WM1_ROUTER))
        self.assertEqual(sha(WM1_ROUTER), "4035f0a175ea6bf130287a49e7428b8ef588bf0b0b4bdb021b6ad27bf84ee57a")

    def test_router_changes_only_the_goals_lane(self):
        removed, added = changed_lines(WM1_ROUTER, G1_ROUTER)
        self.assertEqual(removed, ["goals_enabled: false"])
        self.assertEqual([l for l in added if not l.startswith("#")], ["goals_enabled: true", "goals_mode: shadow"])
        base, g1 = (yaml.safe_load(p.read_text(encoding="utf-8")) for p in (WM1_ROUTER, G1_ROUTER))
        self.assertEqual({k: v for k, v in g1.items() if base.get(k) != v},
                         {"goals_enabled": True, "goals_mode": "shadow"})
        self.assertEqual((g1["mode"], g1["live_channels"], g1["cognitive_channels"]),
                         ("shadow", ["lilith_os"], ["lilith_os"]))
        self.assertEqual([lane for lane in LANES if g1[lane] is not False], ["cognitive_enabled", "goals_enabled"])
        self.assertEqual({k: v for k, v in g1.items() if k == "mode" or k.endswith("_mode")},
                         {"mode": "shadow", "cognitive_mode": "shadow", "goals_mode": "shadow"})

    def test_verifier_changes_only_the_lane_policy(self):
        removed, added = changed_lines(WM1_TEMPLATE, G1_TEMPLATE)
        self.assertEqual(removed, [
            "# f9c2-cog1-wm1: exactly one lane, Slice 7.2 World Model, is on, in shadow, for lilith_os only. Every other lane off.",
            'SHADOW_LANE = "cognitive_enabled"',
            "        if lane == SHADOW_LANE:",
            '    if router.get("cognitive_mode") != "shadow":',
            '        fail("SHADOW_LANE_NOT_SHADOW cognitive_mode")',
        ])
        self.assertIn('SHADOW_LANES = {"cognitive_enabled": "cognitive_mode", "goals_enabled": "goals_mode"}', added)
        cand = G1_TEMPLATE.read_text(encoding="utf-8")
        self.assertEqual(cand.count(C.PLACEHOLDER), WM1_TEMPLATE.read_text(encoding="utf-8").count(C.PLACEHOLDER))
        for pin in ("WORLD_CONTEXT_ADAPTER_SHA256", "PROD_WORKING_MEMORY_SHA256", "LANES_OFF = (", "REQUIRED_DENY"):
            self.assertIn(pin, cand)                                        # adapter / PROD pins and lane list kept

    def test_router_key_allowlist_is_exactly_what_the_router_reads(self):
        # ROUTER_KEYS must equal the keys lilith_router/config.py loads from router.yaml (raw.get("...")), so a
        # misspelt lane or mode is refused rather than silently defaulted.
        import re
        read = set(re.findall(r'raw\.get\("([a-z_]+)"', CONFIG_PY.read_text(encoding="utf-8")))
        module = C.load_verifier(G1_TEMPLATE, Path(tempfile.mkdtemp(prefix="g1-keys-")))
        self.assertEqual(set(module.ROUTER_KEYS), read)
        self.assertLessEqual(set(yaml.safe_load(G1_ROUTER.read_text(encoding="utf-8"))), set(module.ROUTER_KEYS))

    def test_no_credential_material(self):
        for p in G1.rglob("*"):
            if p.is_file() and "__pycache__" not in p.parts:
                text = p.read_text(encoding="utf-8")
                for marker in ("gsk" + "_", "PRIVATE" + " KEY", "BEGIN" + " OPENSSH", "Bearer" + " "):
                    self.assertNotIn(marker, text, p.name)


class VerifierBehaviourTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp(prefix="g1-verify-"))
        cls.wm1 = C.load_verifier(WM1_TEMPLATE, cls.tmp)
        cls.g1 = C.load_verifier(G1_TEMPLATE, cls.tmp)

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
        """The full failure lines ("CODE detail"); C.run_verifier itself returns only the codes."""
        C.run_verifier(module, root)
        return set(module.failures)

    @property
    def g1_router(self) -> dict:
        return yaml.safe_load(G1_ROUTER.read_text(encoding="utf-8"))

    def test_g1_accepts_exactly_its_router_and_otherwise_matches_wm1(self):
        root = self.host("g1", self.g1_router)
        g1, wm1 = self.codes(self.g1, root), self.codes(self.wm1, root)
        self.assertFalse(kinds(g1) & (LANE_CODES | C.WORLD_CONTEXT_CODES))
        self.assertEqual({c for c in wm1 if kinds({c}) & LANE_CODES}, {"LANE_NOT_OFF goals_enabled"})
        self.assertEqual({c for c in g1 if not kinds({c}) & LANE_CODES},                   # nothing else differs
                         {c for c in wm1 if not kinds({c}) & LANE_CODES})

    def test_g1_refuses_the_wm1_router_goals_off(self):
        root = self.host("wm1-router", yaml.safe_load(WM1_ROUTER.read_text(encoding="utf-8")))
        self.assertEqual({c for c in self.codes(self.g1, root) if kinds({c}) & LANE_CODES},
                         {"SHADOW_LANE_NOT_ON goals_enabled", "SHADOW_LANE_NOT_SHADOW goals_mode"})
        self.assertFalse(kinds(self.codes(self.wm1, root)) & LANE_CODES)

    def test_g1_refuses_live_lanes_other_channels_unknown_keys_and_any_other_lane(self):
        cases = {
            "goals-live": ({"goals_mode": "live"}, "SHADOW_LANE_NOT_SHADOW goals_mode"),
            "goals-mode-missing": ({"goals_mode": None}, "SHADOW_LANE_NOT_SHADOW goals_mode"),
            "goals-mode-empty": ({"goals_mode": ""}, "SHADOW_LANE_NOT_SHADOW goals_mode"),
            "goals-mode-upper": ({"goals_mode": "SHADOW"}, "SHADOW_LANE_NOT_SHADOW goals_mode"),
            "goals-string-true": ({"goals_enabled": "true"}, "SHADOW_LANE_NOT_ON goals_enabled"),
            "goals-off": ({"goals_enabled": False}, "SHADOW_LANE_NOT_ON goals_enabled"),
            "wm-live": ({"cognitive_mode": "live"}, "SHADOW_LANE_NOT_SHADOW cognitive_mode"),
            "wm-mode-missing": ({"cognitive_mode": None}, "SHADOW_LANE_NOT_SHADOW cognitive_mode"),
            "wm-off": ({"cognitive_enabled": False}, "SHADOW_LANE_NOT_ON cognitive_enabled"),
            "all-channels": ({"cognitive_channels": ["*"]}, "SHADOW_LANE_CHANNELS cognitive_channels"),
            "telegram-too": ({"cognitive_channels": ["lilith_os", "telegram"]}, "SHADOW_LANE_CHANNELS cognitive_channels"),
            "chat-scoped": ({"cognitive_channels": ["lilith_os:one"]}, "SHADOW_LANE_CHANNELS cognitive_channels"),
            "no-channel": ({"cognitive_channels": []}, "SHADOW_LANE_CHANNELS cognitive_channels"),
            "goals-own-channels": ({"goals_channels": ["telegram"]}, "ROUTER_KEY_UNKNOWN goals_channels"),
            "misspelt-lane": ({"goal_enabled": True}, "ROUTER_KEY_UNKNOWN goal_enabled"),
            "router-live": ({"mode": "live"}, "ROUTER_MODE_NOT_SHADOW"),
            "router-wider": ({"live_channels": ["lilith_os", "telegram"]}, "ROUTER_SCOPE"),
            "reasoning-live-mode": ({"reasoning_mode": "live"}, "LANE_MODE_NOT_SHADOW reasoning_mode"),
            "canonical-config": ({"canonical_ltm_config_valid": True}, "ROUTER_KEY_UNKNOWN canonical_ltm_config_valid"),
        }
        for lane in LANES[2:]:
            cases[lane] = ({lane: True}, f"LANE_NOT_OFF {lane}")
        for name, (change, code) in cases.items():
            with self.subTest(case=name):
                router = dict(self.g1_router, **change)
                router = {k: v for k, v in router.items() if v is not None}
                self.assertIn(code, self.codes(self.g1, self.host(f"case-{name}", router)))

    def test_g1_still_pins_the_adapter_and_the_prod_module(self):
        root = self.host("adapter-changed", self.g1_router)
        adapter = root / "home" / "lilith_router" / "world_context.py"
        adapter.write_bytes(adapter.read_bytes() + b"\n# TEST_ONLY\n")
        (root / "home" / "lilith_router" / "_prod_world_context.py").unlink()
        self.assertEqual(kinds(self.codes(self.g1, root)) & C.WORLD_CONTEXT_CODES,
                         {"WORLD_CONTEXT_NOT_THE_COG1_ADAPTER", "PROD_WORKING_MEMORY_NOT_PINNED"})


if __name__ == "__main__":
    unittest.main()
