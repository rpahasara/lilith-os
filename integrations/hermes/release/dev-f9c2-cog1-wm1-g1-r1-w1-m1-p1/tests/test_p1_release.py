"""Offline acceptance contract for f293e72-f9c2-cog1-wm1-g1-r1-w1-m1-p1 (World Model, Goals, Reasoning, Workspace, Motivation and Planning lanes in shadow). TEST_ONLY.

    python -m unittest discover -s integrations/hermes/release/dev-f9c2-cog1-wm1-g1-r1-w1-m1-p1/tests -p "test_*.py"

The release is m1 with five member changes (RELEASE-DELTA.json): RELEASE_ID, router.yaml, the verifier template, planning.py and the adapter. The verifier helpers come from the cog1 acceptance tests.
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

P1 = Path(__file__).resolve().parents[1]
REPO = P1.parents[3]
REL = REPO / "integrations" / "hermes" / "release"
COW1 = REL / "dev-f9c2-cog1"
M1 = REL / "dev-f9c2-cog1-wm1-g1-r1-w1-m1"
F9C2 = REL / "dev-f9c2"
sys.path.insert(0, str(COW1 / "tests"))

import test_cog1_release as C  # noqa: E402  (load_verifier, run_verifier, assemble_dev_cognition, constants)

DELTA = json.loads((P1 / "RELEASE-DELTA.json").read_text(encoding="utf-8"))
M1_TEMPLATE = M1 / "templates" / "bin" / "verify_release.py.tmpl"
P1_TEMPLATE = P1 / "templates" / "bin" / "verify_release.py.tmpl"
M1_ROUTER = M1 / "home" / "router.yaml"
P1_ROUTER = P1 / "home" / "router.yaml"
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
        self.assertEqual((P1 / "RELEASE_ID").read_bytes(), b"f293e72-f9c2-cog1-wm1-g1-r1-w1-m1-p1\n")
        self.assertEqual(DELTA["release"], "f293e72-f9c2-cog1-wm1-g1-r1-w1-m1-p1")
        self.assertEqual(DELTA["base_release"], (M1 / "RELEASE_ID").read_text().strip())
        self.assertEqual(set(DELTA["members"]), {"RELEASE_ID", "bin/verify_release.py", "home/router.yaml", "home/lilith_router/planning.py", "home/lilith_router/world_context.py"})
        for member, change in DELTA["members"].items():
            with self.subTest(member=member):
                if change.get("source"):
                    self.assertEqual(sha(REPO / change["source"]), change["sha256"])
        self.assertEqual(DELTA["members"]["RELEASE_ID"]["from"], sha(M1 / "RELEASE_ID"))
        verifier = DELTA["members"]["bin/verify_release.py"]
        self.assertEqual(sha(REPO / verifier["template"]), verifier["template_sha256"])
        self.assertEqual(sha(REPO / verifier["base_template"]), verifier["base_template_sha256"])
        self.assertEqual(verifier["base_template_sha256"],
                         "9d2e914b18bac139aa62a83fb5a09b944649b98c674a1b75f7f5d5c49fae599a")   # installed m1 template
        self.assertEqual(DELTA["members"]["home/router.yaml"]["from"], sha(M1_ROUTER))
        self.assertEqual(sha(M1_ROUTER), "3ff4d3dc5f0dcfda11b79ca2e026e98b0be5e6460c4e936f2912e268cdd527ff")

    def test_router_changes_only_the_planning_lane(self):
        removed, added = changed_lines(M1_ROUTER, P1_ROUTER)
        self.assertEqual(removed, ["planning_enabled: false"])
        self.assertEqual([l for l in added if not l.startswith("#")], ["planning_enabled: true", "planning_mode: shadow"])
        base, p1 = (yaml.safe_load(p.read_text(encoding="utf-8")) for p in (M1_ROUTER, P1_ROUTER))
        self.assertEqual({k: v for k, v in p1.items() if base.get(k) != v}, {"planning_enabled": True, "planning_mode": "shadow"})
        self.assertEqual([lane for lane in LANES if p1[lane] is not False],
                         ["cognitive_enabled", "goals_enabled", "reasoning_enabled", "workspace_enabled", "motivation_enabled", "planning_enabled"])
        self.assertEqual({k: v for k, v in p1.items() if k == "mode" or k.endswith("_mode")},
                         {"mode": "shadow", "cognitive_mode": "shadow", "goals_mode": "shadow", "reasoning_mode": "shadow", "workspace_mode": "shadow", "motivation_mode": "shadow", "planning_mode": "shadow"})

    def test_verifier_changes_only_the_lane_policy_and_the_pins(self):
        removed, added = changed_lines(M1_TEMPLATE, P1_TEMPLATE)
        removed = sorted(l for l in removed if not l.startswith("#"))
        self.assertEqual(len(removed), 3, removed)
        cand = P1_TEMPLATE.read_text(encoding="utf-8")
        self.assertTrue(any('"motivation_enabled": "motivation_mode"}' in l for l in removed))
        self.assertTrue(any("MOTIVATION_NOT_PINNED" in l for l in removed))
        self.assertTrue(any("WORLD_CONTEXT_ADAPTER_SHA256" in l for l in removed))
        self.assertIn('PLANNING_SHA256 = "' + sha(REPO / "integrations/hermes/overlays/dev-planning-hardening/lilith_router/planning.py") + '"', cand)
        self.assertIn('WORLD_CONTEXT_ADAPTER_SHA256 = "' + sha(REPO / "integrations/hermes/overlays/dev-cognition-private-intent/lilith_router/world_context.py") + '"', cand)
        self.assertIn('"planning_enabled": "planning_mode"', cand)
        self.assertEqual(cand.count(C.PLACEHOLDER), M1_TEMPLATE.read_text(encoding="utf-8").count(C.PLACEHOLDER))

    def test_router_key_allowlist_is_exactly_what_the_router_reads(self):
        # ROUTER_KEYS must equal the keys lilith_router/config.py loads from router.yaml (raw.get("...")), so a
        # misspelt lane or mode is refused rather than silently defaulted.
        import re
        read = set(re.findall(r'raw\.get\("([a-z_]+)"', CONFIG_PY.read_text(encoding="utf-8")))
        module = C.load_verifier(P1_TEMPLATE, Path(tempfile.mkdtemp(prefix="m1-keys-")))
        self.assertEqual(set(module.ROUTER_KEYS), read)
        self.assertLessEqual(set(yaml.safe_load(P1_ROUTER.read_text(encoding="utf-8"))), set(module.ROUTER_KEYS))

    def test_no_credential_material(self):
        for p in P1.rglob("*"):
            if p.is_file() and "__pycache__" not in p.parts:
                text = p.read_text(encoding="utf-8")
                for marker in ("gsk" + "_", "PRIVATE" + " KEY", "BEGIN" + " OPENSSH", "Bearer" + " "):
                    self.assertNotIn(marker, text, p.name)


class VerifierBehaviourTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp(prefix="m1-verify-"))
        cls.m1 = C.load_verifier(M1_TEMPLATE, cls.tmp)
        cls.p1 = C.load_verifier(P1_TEMPLATE, cls.tmp)

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
    def p1_router(self) -> dict:
        return yaml.safe_load(P1_ROUTER.read_text(encoding="utf-8"))

    def test_p1_accepts_exactly_its_router_and_otherwise_matches_m1(self):
        O = REPO / "integrations/hermes/overlays"
        shared = ((O / "dev-workspace-private-trace/lilith_router/workspace.py", "workspace.py"), (O / "dev-motivation-private-trace/lilith_router/motivation.py", "motivation.py"))
        root, base = self.host("p1", self.p1_router), self.host("p1-m1-code", self.p1_router)
        for source, name in shared + ((O / "dev-cognition-private-intent/lilith_router/world_context.py", "world_context.py"), (O / "dev-planning-hardening/lilith_router/planning.py", "planning.py")):
            (root / "home" / "lilith_router" / name).write_bytes(source.read_bytes())
        for source, name in shared + ((O / "dev-reasoning-hardening/lilith_router/world_context.py", "world_context.py"),):
            (base / "home" / "lilith_router" / name).write_bytes(source.read_bytes())
        p1 = {c.replace(str(root), "ROOT") for c in self.codes(self.p1, root)}
        m1 = {c.replace(str(base), "ROOT") for c in self.codes(self.m1, base)}
        self.assertFalse(kinds(p1) & (LANE_CODES | C.WORLD_CONTEXT_CODES))
        self.assertNotIn("PLANNING_NOT_PINNED", kinds(p1))
        self.assertIn("LANE_NOT_OFF planning_enabled", m1)
        schema = {"GOAL_DB_MISSING", "GOAL_STORE_NOT_EMPTY", "COGNITION_SCHEMA_NOT_BOOTSTRAPPED", "COGNITION_SCHEMA_MISMATCH", "GOAL_DB_UNREADABLE"}
        self.assertEqual({c for c in p1 if not kinds({c}) & (LANE_CODES | schema)},
                         {c for c in m1 if not kinds({c}) & (LANE_CODES | schema)})

    def test_p1_refuses_the_m1_router_planning_off(self):
        root = self.host("m1-router", yaml.safe_load(M1_ROUTER.read_text(encoding="utf-8")))
        self.assertEqual({c for c in self.codes(self.p1, root) if kinds({c}) & LANE_CODES},
                         {"SHADOW_LANE_NOT_ON planning_enabled", "SHADOW_LANE_NOT_SHADOW planning_mode"})

    def test_m1_refuses_live_lanes_other_channels_and_any_other_lane(self):
        cases = {
            "planning-live": ({"planning_mode": "live"}, "SHADOW_LANE_NOT_SHADOW planning_mode"),
            "planning-mode-missing": ({"planning_mode": None}, "SHADOW_LANE_NOT_SHADOW planning_mode"),
            "planning-off": ({"planning_enabled": False}, "SHADOW_LANE_NOT_ON planning_enabled"),
            "motivation-live": ({"motivation_mode": "live"}, "SHADOW_LANE_NOT_SHADOW motivation_mode"),
            "motivation-mode-missing": ({"motivation_mode": None}, "SHADOW_LANE_NOT_SHADOW motivation_mode"),
            "motivation-off": ({"motivation_enabled": False}, "SHADOW_LANE_NOT_ON motivation_enabled"),
            "workspace-live": ({"workspace_mode": "live"}, "SHADOW_LANE_NOT_SHADOW workspace_mode"),
            "workspace-mode-missing": ({"workspace_mode": None}, "SHADOW_LANE_NOT_SHADOW workspace_mode"),
            "workspace-off": ({"workspace_enabled": False}, "SHADOW_LANE_NOT_ON workspace_enabled"),
            "reasoning-live": ({"reasoning_mode": "live"}, "SHADOW_LANE_NOT_SHADOW reasoning_mode"),
            "goals-live": ({"goals_mode": "live"}, "SHADOW_LANE_NOT_SHADOW goals_mode"),
            "wm-live": ({"cognitive_mode": "live"}, "SHADOW_LANE_NOT_SHADOW cognitive_mode"),
            "all-channels": ({"cognitive_channels": ["*"]}, "SHADOW_LANE_CHANNELS cognitive_channels"),
            "misspelt": ({"workspaces_enabled": True}, "ROUTER_KEY_UNKNOWN workspaces_enabled"),
            "router-live": ({"mode": "live"}, "ROUTER_MODE_NOT_SHADOW"),
        }
        for lane in LANES[6:]:
            cases[lane] = ({lane: True}, f"LANE_NOT_OFF {lane}")
        for name, (change, code) in cases.items():
            with self.subTest(case=name):
                router = dict(self.p1_router, **change)
                router = {k: v for k, v in router.items() if v is not None}
                self.assertIn(code, self.codes(self.p1, self.host(f"case-{name}", router)))

    def schema_codes(self, name: str, build):
        import sqlite3
        db = Path(tempfile.mkdtemp(prefix="p1-db-")) / "d.db"
        build(sqlite3.connect(db))
        self.p1.GOAL_DB = db
        self.p1.failures.clear()
        self.p1.check_cognition_schema()
        return set(self.p1.failures)

    def test_schema_rule(self):
        goal = ", ".join(self.p1.GOAL_SCHEMA["goal"])
        trace = ", ".join(self.p1.GOAL_SCHEMA["goal_trace"])
        draft = ", ".join(self.p1.GOAL_SCHEMA["drafts"])
        ok = lambda c: (c.executescript(f"CREATE TABLE goal ({goal}); CREATE TABLE goal_trace ({trace}); CREATE TABLE drafts ({draft});"), c.close())
        self.assertEqual(self.schema_codes("ok", ok), set())
        self.assertEqual(self.schema_codes("no-drafts", lambda c: (c.executescript(f"CREATE TABLE goal ({goal}); CREATE TABLE goal_trace ({trace});"), c.close())),
                         {"COGNITION_SCHEMA_NOT_BOOTSTRAPPED drafts"})
        self.assertEqual(self.schema_codes("bad-drafts", lambda c: (c.executescript(f"CREATE TABLE goal ({goal}); CREATE TABLE goal_trace ({trace}); CREATE TABLE drafts (draft_id);"), c.close())),
                         {"COGNITION_SCHEMA_MISMATCH drafts"})
        def goalrow(c):
            ok_c = c.executescript(f"CREATE TABLE goal ({goal}); CREATE TABLE goal_trace ({trace}); CREATE TABLE drafts ({draft}); INSERT INTO goal (goal_id) VALUES ('x');")
            c.commit(); c.close()
        self.assertEqual(self.schema_codes("goal-row", goalrow), {"GOAL_STORE_NOT_EMPTY"})

    def test_p1_pins_the_planning_module(self):
        root = self.host("plan-changed", self.p1_router)
        (root / "home" / "lilith_router" / "planning.py").write_bytes(b"# TEST_ONLY\n")
        self.assertIn("PLANNING_NOT_PINNED", kinds(self.codes(self.p1, root)))

    def test_m1_still_pins_the_adapter_and_the_prod_module(self):
        root = self.host("adapter-changed", self.p1_router)
        adapter = root / "home" / "lilith_router" / "world_context.py"
        adapter.write_bytes(adapter.read_bytes() + b"\n# TEST_ONLY\n")
        (root / "home" / "lilith_router" / "_prod_world_context.py").unlink()
        self.assertEqual(kinds(self.codes(self.p1, root)) & C.WORLD_CONTEXT_CODES,
                         {"WORLD_CONTEXT_NOT_THE_COG1_ADAPTER", "PROD_WORKING_MEMORY_NOT_PINNED"})


if __name__ == "__main__":
    unittest.main()
