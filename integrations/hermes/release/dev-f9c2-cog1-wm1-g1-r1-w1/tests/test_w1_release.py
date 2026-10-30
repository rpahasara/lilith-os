"""Offline acceptance contract for f293e72-f9c2-cog1-wm1-g1-r1-w1 (World Model, Goals, Reasoning and Workspace lanes in shadow). TEST_ONLY.

    python -m unittest discover -s integrations/hermes/release/dev-f9c2-cog1-wm1-g1-r1-w1/tests -p "test_*.py"

The release is r1 with three member changes (RELEASE-DELTA.json): RELEASE_ID, router.yaml and the verifier template,
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

W1 = Path(__file__).resolve().parents[1]
REPO = W1.parents[3]
REL = REPO / "integrations" / "hermes" / "release"
COW1 = REL / "dev-f9c2-cog1"
R1 = REL / "dev-f9c2-cog1-wm1-g1-r1"
F9C2 = REL / "dev-f9c2"
sys.path.insert(0, str(COW1 / "tests"))

import test_cog1_release as C  # noqa: E402  (load_verifier, run_verifier, assemble_dev_cognition, constants)

DELTA = json.loads((W1 / "RELEASE-DELTA.json").read_text(encoding="utf-8"))
R1_TEMPLATE = R1 / "templates" / "bin" / "verify_release.py.tmpl"
W1_TEMPLATE = W1 / "templates" / "bin" / "verify_release.py.tmpl"
R1_ROUTER = R1 / "home" / "router.yaml"
W1_ROUTER = W1 / "home" / "router.yaml"
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
        self.assertEqual((W1 / "RELEASE_ID").read_bytes(), b"f293e72-f9c2-cog1-wm1-g1-r1-w1\n")
        self.assertEqual(DELTA["release"], "f293e72-f9c2-cog1-wm1-g1-r1-w1")
        self.assertEqual(DELTA["base_release"], (R1 / "RELEASE_ID").read_text().strip())
        self.assertEqual(set(DELTA["members"]), {"RELEASE_ID", "bin/verify_release.py", "home/router.yaml"})
        for member, change in DELTA["members"].items():
            with self.subTest(member=member):
                if change.get("source"):
                    self.assertEqual(sha(REPO / change["source"]), change["sha256"])
        self.assertEqual(DELTA["members"]["RELEASE_ID"]["from"], sha(R1 / "RELEASE_ID"))
        verifier = DELTA["members"]["bin/verify_release.py"]
        self.assertEqual(sha(REPO / verifier["template"]), verifier["template_sha256"])
        self.assertEqual(sha(REPO / verifier["base_template"]), verifier["base_template_sha256"])
        self.assertEqual(verifier["base_template_sha256"],
                         "12fa37c226dff639199fe9482679ddb73fed149e619496009706d15ba6940c2b")   # installed g1 template
        self.assertEqual(DELTA["members"]["home/router.yaml"]["from"], sha(R1_ROUTER))
        self.assertEqual(sha(R1_ROUTER), "47579562bbaa2c217657efa478d960b3fb7f0949ba534012823f9f293ebea0d7")

    def test_router_changes_only_the_workspace_lane(self):
        removed, added = changed_lines(R1_ROUTER, W1_ROUTER)
        self.assertEqual(removed, ["workspace_enabled: false"])
        self.assertEqual([l for l in added if not l.startswith("#")], ["workspace_enabled: true", "workspace_mode: shadow"])
        base, w1 = (yaml.safe_load(p.read_text(encoding="utf-8")) for p in (R1_ROUTER, W1_ROUTER))
        self.assertEqual({k: v for k, v in w1.items() if base.get(k) != v}, {"workspace_enabled": True, "workspace_mode": "shadow"})
        self.assertEqual([lane for lane in LANES if w1[lane] is not False],
                         ["cognitive_enabled", "goals_enabled", "reasoning_enabled", "workspace_enabled"])
        self.assertEqual({k: v for k, v in w1.items() if k == "mode" or k.endswith("_mode")},
                         {"mode": "shadow", "cognitive_mode": "shadow", "goals_mode": "shadow", "reasoning_mode": "shadow", "workspace_mode": "shadow"})

    def test_verifier_changes_only_the_lane_policy_and_the_schema_rule(self):
        removed, added = changed_lines(R1_TEMPLATE, W1_TEMPLATE)
        self.assertEqual([l for l in removed if not l.startswith("#")],
                         ['SHADOW_LANES = {"cognitive_enabled": "cognitive_mode", "goals_enabled": "goals_mode", "reasoning_enabled": "reasoning_mode"}'])
        cand = W1_TEMPLATE.read_text(encoding="utf-8")
        self.assertIn("check_cognition_schema()", cand)
        self.assertIn('"drafts": ("draft_id"', cand)
        self.assertEqual(cand.count(C.PLACEHOLDER), R1_TEMPLATE.read_text(encoding="utf-8").count(C.PLACEHOLDER))

    def test_router_key_allowlist_is_exactly_what_the_router_reads(self):
        # ROUTER_KEYS must equal the keys lilith_router/config.py loads from router.yaml (raw.get("...")), so a
        # misspelt lane or mode is refused rather than silently defaulted.
        import re
        read = set(re.findall(r'raw\.get\("([a-z_]+)"', CONFIG_PY.read_text(encoding="utf-8")))
        module = C.load_verifier(W1_TEMPLATE, Path(tempfile.mkdtemp(prefix="r1-keys-")))
        self.assertEqual(set(module.ROUTER_KEYS), read)
        self.assertLessEqual(set(yaml.safe_load(W1_ROUTER.read_text(encoding="utf-8"))), set(module.ROUTER_KEYS))

    def test_no_credential_material(self):
        for p in W1.rglob("*"):
            if p.is_file() and "__pycache__" not in p.parts:
                text = p.read_text(encoding="utf-8")
                for marker in ("gsk" + "_", "PRIVATE" + " KEY", "BEGIN" + " OPENSSH", "Bearer" + " "):
                    self.assertNotIn(marker, text, p.name)


class VerifierBehaviourTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp(prefix="r1-verify-"))
        cls.r1 = C.load_verifier(R1_TEMPLATE, cls.tmp)
        cls.w1 = C.load_verifier(W1_TEMPLATE, cls.tmp)

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
    def w1_router(self) -> dict:
        return yaml.safe_load(W1_ROUTER.read_text(encoding="utf-8"))

    def test_w1_accepts_exactly_its_router_and_otherwise_matches_r1(self):
        root = self.host("w1", self.w1_router)
        w1, r1 = self.codes(self.w1, root), self.codes(self.r1, root)
        self.assertFalse(kinds(w1) & (LANE_CODES | C.WORLD_CONTEXT_CODES))
        self.assertIn("LANE_NOT_OFF workspace_enabled", r1)
        schema = {"GOAL_DB_MISSING", "GOAL_STORE_NOT_EMPTY", "COGNITION_SCHEMA_NOT_BOOTSTRAPPED", "COGNITION_SCHEMA_MISMATCH", "GOAL_DB_UNREADABLE"}
        self.assertEqual({c for c in w1 if not kinds({c}) & (LANE_CODES | schema)},
                         {c for c in r1 if not kinds({c}) & (LANE_CODES | schema)})

    def test_w1_refuses_the_r1_router_workspace_off(self):
        root = self.host("r1-router", yaml.safe_load(R1_ROUTER.read_text(encoding="utf-8")))
        self.assertEqual({c for c in self.codes(self.w1, root) if kinds({c}) & LANE_CODES},
                         {"SHADOW_LANE_NOT_ON workspace_enabled", "SHADOW_LANE_NOT_SHADOW workspace_mode"})

    def test_w1_refuses_live_lanes_other_channels_and_any_other_lane(self):
        cases = {
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
        for lane in LANES[4:]:
            cases[lane] = ({lane: True}, f"LANE_NOT_OFF {lane}")
        for name, (change, code) in cases.items():
            with self.subTest(case=name):
                router = dict(self.w1_router, **change)
                router = {k: v for k, v in router.items() if v is not None}
                self.assertIn(code, self.codes(self.w1, self.host(f"case-{name}", router)))

    def schema_codes(self, name: str, build):
        import sqlite3
        db = Path(tempfile.mkdtemp(prefix="w1-db-")) / "d.db"
        build(sqlite3.connect(db))
        self.w1.GOAL_DB = db
        self.w1.failures.clear()
        self.w1.check_cognition_schema()
        return set(self.w1.failures)

    def test_schema_rule(self):
        goal = ", ".join(self.w1.GOAL_SCHEMA["goal"])
        trace = ", ".join(self.w1.GOAL_SCHEMA["goal_trace"])
        draft = ", ".join(self.w1.GOAL_SCHEMA["drafts"])
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

    def test_w1_still_pins_the_adapter_and_the_prod_module(self):
        root = self.host("adapter-changed", self.w1_router)
        adapter = root / "home" / "lilith_router" / "world_context.py"
        adapter.write_bytes(adapter.read_bytes() + b"\n# TEST_ONLY\n")
        (root / "home" / "lilith_router" / "_prod_world_context.py").unlink()
        self.assertEqual(kinds(self.codes(self.w1, root)) & C.WORLD_CONTEXT_CODES,
                         {"WORLD_CONTEXT_NOT_THE_COG1_ADAPTER", "PROD_WORKING_MEMORY_NOT_PINNED"})


if __name__ == "__main__":
    unittest.main()
