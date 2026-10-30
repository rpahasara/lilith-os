"""Offline acceptance contract for f293e72-f9c2-cog1-wm1-g1-r1 (World Model, Goals and Reasoning lanes in shadow). TEST_ONLY.

    python -m unittest discover -s integrations/hermes/release/dev-f9c2-cog1-wm1-g1-r1/tests -p "test_*.py"

The release is g1 with three member changes (RELEASE-DELTA.json): RELEASE_ID, router.yaml and the verifier template,
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

R1 = Path(__file__).resolve().parents[1]
REPO = R1.parents[3]
REL = REPO / "integrations" / "hermes" / "release"
COR1 = REL / "dev-f9c2-cog1"
G1 = REL / "dev-f9c2-cog1-wm1-g1"
F9C2 = REL / "dev-f9c2"
sys.path.insert(0, str(COR1 / "tests"))

import test_cog1_release as C  # noqa: E402  (load_verifier, run_verifier, assemble_dev_cognition, constants)

DELTA = json.loads((R1 / "RELEASE-DELTA.json").read_text(encoding="utf-8"))
G1_TEMPLATE = G1 / "templates" / "bin" / "verify_release.py.tmpl"
R1_TEMPLATE = R1 / "templates" / "bin" / "verify_release.py.tmpl"
G1_ROUTER = G1 / "home" / "router.yaml"
R1_ROUTER = R1 / "home" / "router.yaml"
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
        self.assertEqual((R1 / "RELEASE_ID").read_bytes(), b"f293e72-f9c2-cog1-wm1-g1-r1\n")
        self.assertEqual(DELTA["release"], "f293e72-f9c2-cog1-wm1-g1-r1")
        self.assertEqual(DELTA["base_release"], (G1 / "RELEASE_ID").read_text().strip())
        self.assertEqual(set(DELTA["members"]), {"RELEASE_ID", "bin/verify_release.py", "home/router.yaml"})
        for member, change in DELTA["members"].items():
            with self.subTest(member=member):
                if change.get("source"):
                    self.assertEqual(sha(REPO / change["source"]), change["sha256"])
        self.assertEqual(DELTA["members"]["RELEASE_ID"]["from"], sha(G1 / "RELEASE_ID"))
        verifier = DELTA["members"]["bin/verify_release.py"]
        self.assertEqual(sha(REPO / verifier["template"]), verifier["template_sha256"])
        self.assertEqual(sha(REPO / verifier["base_template"]), verifier["base_template_sha256"])
        self.assertEqual(verifier["base_template_sha256"],
                         "839a52b8643c9a0e5b2b25642330b2f321dc203fecb130791aeab5ef9bbec2b5")   # installed g1 template
        self.assertEqual(DELTA["members"]["home/router.yaml"]["from"], sha(G1_ROUTER))
        self.assertEqual(sha(G1_ROUTER), "d931f1b6d6e8099f63e894dffee3b8ff76ce35f35fdf87b748373256ac30e418")

    def test_router_changes_only_the_reasoning_lane(self):
        removed, added = changed_lines(G1_ROUTER, R1_ROUTER)
        self.assertEqual(removed, ["reasoning_enabled: false"])
        self.assertEqual([l for l in added if not l.startswith("#")], ["reasoning_enabled: true", "reasoning_mode: shadow"])
        base, r1 = (yaml.safe_load(p.read_text(encoding="utf-8")) for p in (G1_ROUTER, R1_ROUTER))
        self.assertEqual({k: v for k, v in r1.items() if base.get(k) != v},
                         {"reasoning_enabled": True, "reasoning_mode": "shadow"})
        self.assertEqual((r1["mode"], r1["live_channels"], r1["cognitive_channels"]),
                         ("shadow", ["lilith_os"], ["lilith_os"]))
        self.assertEqual([lane for lane in LANES if r1[lane] is not False],
                         ["cognitive_enabled", "goals_enabled", "reasoning_enabled"])
        self.assertEqual({k: v for k, v in r1.items() if k == "mode" or k.endswith("_mode")},
                         {"mode": "shadow", "cognitive_mode": "shadow", "goals_mode": "shadow", "reasoning_mode": "shadow"})

    def test_verifier_changes_only_the_lane_policy(self):
        removed, added = changed_lines(G1_TEMPLATE, R1_TEMPLATE)
        self.assertEqual([l for l in removed if not l.startswith("#")],
                         ['SHADOW_LANES = {"cognitive_enabled": "cognitive_mode", "goals_enabled": "goals_mode"}'])
        self.assertEqual([l for l in added if not l.startswith("#")],
                         ['SHADOW_LANES = {"cognitive_enabled": "cognitive_mode", "goals_enabled": "goals_mode", "reasoning_enabled": "reasoning_mode"}'])
        cand = R1_TEMPLATE.read_text(encoding="utf-8")
        self.assertEqual(cand.count(C.PLACEHOLDER), G1_TEMPLATE.read_text(encoding="utf-8").count(C.PLACEHOLDER))
        for pin in ("WORLD_CONTEXT_ADAPTER_SHA256", "PROD_WORKING_MEMORY_SHA256", "LANES_OFF = (", "REQUIRED_DENY"):
            self.assertIn(pin, cand)

    def test_router_key_allowlist_is_exactly_what_the_router_reads(self):
        # ROUTER_KEYS must equal the keys lilith_router/config.py loads from router.yaml (raw.get("...")), so a
        # misspelt lane or mode is refused rather than silently defaulted.
        import re
        read = set(re.findall(r'raw\.get\("([a-z_]+)"', CONFIG_PY.read_text(encoding="utf-8")))
        module = C.load_verifier(R1_TEMPLATE, Path(tempfile.mkdtemp(prefix="r1-keys-")))
        self.assertEqual(set(module.ROUTER_KEYS), read)
        self.assertLessEqual(set(yaml.safe_load(R1_ROUTER.read_text(encoding="utf-8"))), set(module.ROUTER_KEYS))

    def test_no_credential_material(self):
        for p in R1.rglob("*"):
            if p.is_file() and "__pycache__" not in p.parts:
                text = p.read_text(encoding="utf-8")
                for marker in ("gsk" + "_", "PRIVATE" + " KEY", "BEGIN" + " OPENSSH", "Bearer" + " "):
                    self.assertNotIn(marker, text, p.name)


class VerifierBehaviourTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp(prefix="r1-verify-"))
        cls.g1 = C.load_verifier(G1_TEMPLATE, cls.tmp)
        cls.r1 = C.load_verifier(R1_TEMPLATE, cls.tmp)

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
    def r1_router(self) -> dict:
        return yaml.safe_load(R1_ROUTER.read_text(encoding="utf-8"))

    def test_r1_accepts_exactly_its_router_and_otherwise_matches_g1(self):
        root = self.host("r1", self.r1_router)
        r1, g1 = self.codes(self.r1, root), self.codes(self.g1, root)
        self.assertFalse(kinds(r1) & (LANE_CODES | C.WORLD_CONTEXT_CODES))
        self.assertEqual({c for c in g1 if kinds({c}) & LANE_CODES},
                         {"LANE_NOT_OFF reasoning_enabled", "LANE_MODE_NOT_SHADOW reasoning_mode"} & {c for c in g1 if kinds({c}) & LANE_CODES} or {"LANE_NOT_OFF reasoning_enabled"})
        self.assertEqual({c for c in r1 if not kinds({c}) & LANE_CODES},                   # nothing else differs
                         {c for c in g1 if not kinds({c}) & LANE_CODES})

    def test_r1_refuses_the_g1_router_reasoning_off(self):
        root = self.host("g1-router", yaml.safe_load(G1_ROUTER.read_text(encoding="utf-8")))
        self.assertEqual({c for c in self.codes(self.r1, root) if kinds({c}) & LANE_CODES},
                         {"SHADOW_LANE_NOT_ON reasoning_enabled", "SHADOW_LANE_NOT_SHADOW reasoning_mode"})
        self.assertFalse(kinds(self.codes(self.g1, root)) & LANE_CODES)

    def test_r1_refuses_live_lanes_other_channels_unknown_keys_and_any_other_lane(self):
        cases = {
            "reasoning-live": ({"reasoning_mode": "live"}, "SHADOW_LANE_NOT_SHADOW reasoning_mode"),
            "reasoning-mode-missing": ({"reasoning_mode": None}, "SHADOW_LANE_NOT_SHADOW reasoning_mode"),
            "reasoning-mode-empty": ({"reasoning_mode": ""}, "SHADOW_LANE_NOT_SHADOW reasoning_mode"),
            "reasoning-mode-upper": ({"reasoning_mode": "SHADOW"}, "SHADOW_LANE_NOT_SHADOW reasoning_mode"),
            "reasoning-string-true": ({"reasoning_enabled": "true"}, "SHADOW_LANE_NOT_ON reasoning_enabled"),
            "reasoning-off": ({"reasoning_enabled": False}, "SHADOW_LANE_NOT_ON reasoning_enabled"),
            "goals-live": ({"goals_mode": "live"}, "SHADOW_LANE_NOT_SHADOW goals_mode"),
            "goals-off": ({"goals_enabled": False}, "SHADOW_LANE_NOT_ON goals_enabled"),
            "wm-live": ({"cognitive_mode": "live"}, "SHADOW_LANE_NOT_SHADOW cognitive_mode"),
            "wm-off": ({"cognitive_enabled": False}, "SHADOW_LANE_NOT_ON cognitive_enabled"),
            "all-channels": ({"cognitive_channels": ["*"]}, "SHADOW_LANE_CHANNELS cognitive_channels"),
            "telegram-too": ({"cognitive_channels": ["lilith_os", "telegram"]}, "SHADOW_LANE_CHANNELS cognitive_channels"),
            "reasoning-own-channels": ({"reasoning_channels": ["telegram"]}, "ROUTER_KEY_UNKNOWN reasoning_channels"),
            "misspelt-lane": ({"reason_enabled": True}, "ROUTER_KEY_UNKNOWN reason_enabled"),
            "router-live": ({"mode": "live"}, "ROUTER_MODE_NOT_SHADOW"),
            "router-wider": ({"live_channels": ["lilith_os", "telegram"]}, "ROUTER_SCOPE"),
            "workspace-live-mode": ({"workspace_mode": "live"}, "LANE_MODE_NOT_SHADOW workspace_mode"),
        }
        for lane in LANES[3:]:
            cases[lane] = ({lane: True}, f"LANE_NOT_OFF {lane}")
        for name, (change, code) in cases.items():
            with self.subTest(case=name):
                router = dict(self.r1_router, **change)
                router = {k: v for k, v in router.items() if v is not None}
                self.assertIn(code, self.codes(self.r1, self.host(f"case-{name}", router)))

    def test_r1_still_pins_the_adapter_and_the_prod_module(self):
        root = self.host("adapter-changed", self.r1_router)
        adapter = root / "home" / "lilith_router" / "world_context.py"
        adapter.write_bytes(adapter.read_bytes() + b"\n# TEST_ONLY\n")
        (root / "home" / "lilith_router" / "_prod_world_context.py").unlink()
        self.assertEqual(kinds(self.codes(self.r1, root)) & C.WORLD_CONTEXT_CODES,
                         {"WORLD_CONTEXT_NOT_THE_COG1_ADAPTER", "PROD_WORKING_MEMORY_NOT_PINNED"})


if __name__ == "__main__":
    unittest.main()
