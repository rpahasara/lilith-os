"""Offline acceptance contract for f293e72-f9c2-cog1-wm1-g2 (World Model shadow, Goals LIVE). TEST_ONLY; no host.

    python -m unittest discover -s integrations/hermes/release/dev-f9c2-cog1-wm1-g2/tests -p "test_*.py"

The release is g1 with three member changes (RELEASE-DELTA.json): RELEASE_ID, router.yaml (goals_mode live) and the
verifier template, whose only changes are the lane policy and the goal-schema requirement. The verifier helpers come
from the cog1 acceptance tests; the fixture goal schema is built from the Core API's own Slice 8 DDL.
"""

from __future__ import annotations

import difflib
import hashlib
import json
import re
import shutil
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

G2 = Path(__file__).resolve().parents[1]
REPO = G2.parents[3]
REL = REPO / "integrations" / "hermes" / "release"
COG1 = REL / "dev-f9c2-cog1"
G1 = REL / "dev-f9c2-cog1-wm1-g1"
F9C2 = REL / "dev-f9c2"
sys.path.insert(0, str(COG1 / "tests"))

import test_cog1_release as C  # noqa: E402  (load_verifier, run_verifier, assemble_dev_cognition, constants)

DELTA = json.loads((G2 / "RELEASE-DELTA.json").read_text(encoding="utf-8"))
G1_TEMPLATE = G1 / "templates" / "bin" / "verify_release.py.tmpl"
G2_TEMPLATE = G2 / "templates" / "bin" / "verify_release.py.tmpl"
G1_ROUTER = G1 / "home" / "router.yaml"
G2_ROUTER = G2 / "home" / "router.yaml"
CONFIG_PY = REPO / "integrations" / "hermes" / "home" / "lilith_router" / "config.py"
APP_PY = REPO / "services" / "core-api" / "app.py"
LANES = ("cognitive_enabled", "goals_enabled", "reasoning_enabled", "workspace_enabled", "motivation_enabled",
         "planning_enabled", "ethics_enabled", "social_cognition_enabled", "memory_consolidation_enabled",
         "canonical_ltm_enabled")
LANE_CODES = {"LANE_NOT_OFF", "LANE_NOT_ON", "LANE_MODE_NOT_SHADOW", "LANE_MODE_NOT_LIVE", "LANE_CHANNELS",
              "ROUTER_KEY_UNKNOWN", "ROUTER_MODE_NOT_SHADOW", "ROUTER_SCOPE", "SHADOW_LANE_NOT_ON",
              "SHADOW_LANE_NOT_SHADOW", "SHADOW_LANE_CHANNELS"}
GOAL_CODES = {"GOAL_DB_MISSING", "GOAL_SCHEMA_NOT_BOOTSTRAPPED", "GOAL_SCHEMA_MISMATCH", "GOAL_DB_UNREADABLE"}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def changed_lines(a: Path, b: Path) -> tuple[list[str], list[str]]:
    diff = list(difflib.unified_diff(a.read_text(encoding="utf-8").splitlines(),
                                     b.read_text(encoding="utf-8").splitlines(), lineterm="", n=0))
    return ([l[1:] for l in diff if l.startswith("-") and not l.startswith("---")],
            [l[1:] for l in diff if l.startswith("+") and not l.startswith("+++")])


def kinds(codes: set[str]) -> set[str]:
    return {c.split(" ", 1)[0] for c in codes}


def goal_ddl() -> str:
    """The exact Slice 8 DDL from services/core-api/app.py _goals_db() (the bootstrap gate runs this code)."""
    text = APP_PY.read_text(encoding="utf-8")
    body = text.split("def _goals_db():", 1)[1]
    return body.split('conn.executescript(\n            """', 1)[1].split('"""', 1)[0]


def make_db(path: Path, *, goal_schema: bool) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as c:
        c.execute("CREATE TABLE IF NOT EXISTS world_belief (key TEXT PRIMARY KEY)")
        if goal_schema:
            c.executescript(goal_ddl())
    return path


class ReleaseDefinitionTest(unittest.TestCase):
    def test_identity_base_and_members(self):
        self.assertEqual((G2 / "RELEASE_ID").read_bytes(), b"f293e72-f9c2-cog1-wm1-g2\n")
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

    def test_router_changes_only_the_goals_mode(self):
        removed, added = changed_lines(G1_ROUTER, G2_ROUTER)
        self.assertEqual([l for l in removed if not l.startswith("#")], ["goals_mode: shadow"])
        self.assertEqual([l for l in added if not l.startswith("#")], ["goals_mode: live"])
        base, g2 = (yaml.safe_load(p.read_text(encoding="utf-8")) for p in (G1_ROUTER, G2_ROUTER))
        self.assertEqual({k: v for k, v in g2.items() if base.get(k) != v}, {"goals_mode": "live"})
        self.assertEqual((g2["mode"], g2["live_channels"], g2["cognitive_channels"]), ("shadow", ["lilith_os"], ["lilith_os"]))
        self.assertEqual([lane for lane in LANES if g2[lane] is not False], ["cognitive_enabled", "goals_enabled"])
        self.assertEqual({k: v for k, v in g2.items() if k == "mode" or k.endswith("_mode")},
                         {"mode": "shadow", "cognitive_mode": "shadow", "goals_mode": "live"})

    def test_verifier_changes_only_the_lane_policy_and_the_goal_schema_check(self):
        removed, added = changed_lines(G1_TEMPLATE, G2_TEMPLATE)
        code_removed = [l for l in removed if not l.lstrip().startswith("#")]
        self.assertEqual(code_removed, [
            'SHADOW_LANES = {"cognitive_enabled": "cognitive_mode", "goals_enabled": "goals_mode"}',
            "        if lane in SHADOW_LANES:",
            '                fail(f"SHADOW_LANE_NOT_ON {lane}")',
            '            if router.get(SHADOW_LANES[lane]) != "shadow":',
            '                fail(f"SHADOW_LANE_NOT_SHADOW {SHADOW_LANES[lane]}")',
            '        fail("SHADOW_LANE_CHANNELS cognitive_channels")',
            '        if key.endswith("_mode") and value != "shadow":',
        ])
        self.assertIn('LANE_MODES = {"cognitive_enabled": ("cognitive_mode", "shadow"), "goals_enabled": ("goals_mode", "live")}', added)
        self.assertIn("    check_goal_schema()", added)
        cand = G2_TEMPLATE.read_text(encoding="utf-8")
        self.assertEqual(cand.count(C.PLACEHOLDER), G1_TEMPLATE.read_text(encoding="utf-8").count(C.PLACEHOLDER))
        for pin in ("WORLD_CONTEXT_ADAPTER_SHA256", "PROD_WORKING_MEMORY_SHA256", "LANES_OFF = (", "REQUIRED_DENY", "ROUTER_KEYS"):
            self.assertIn(pin, cand)
        # The schema check is read-only: mode=ro URI, PRAGMA only; no DDL/DML keyword anywhere in the template.
        fn = cand.split("def check_goal_schema()", 1)[1].split("\ndef ", 1)[0]
        self.assertIn('mode=ro', fn)
        self.assertNotRegex(cand, r"(?i)\b(CREATE|INSERT|UPDATE|DELETE|DROP|ALTER|REPLACE)\s+(TABLE|INTO|FROM|INDEX)\b")

    def test_goal_schema_constant_matches_the_core_api_ddl(self):
        module = C.load_verifier(G2_TEMPLATE, Path(tempfile.mkdtemp(prefix="g2-schema-")))
        db = make_db(Path(tempfile.mkdtemp(prefix="g2-ddl-")) / "x.db", goal_schema=True)
        with sqlite3.connect(db) as c:
            for table, cols in module.GOAL_SCHEMA.items():
                self.assertEqual(tuple(r[1] for r in c.execute(f'PRAGMA table_info("{table}")')), cols)
        self.assertEqual(module.GOAL_DB.as_posix(), "/home/lilith/.hermes/lilith-os-dev/data/lilith-dev.db")

    def test_router_key_allowlist_is_exactly_what_the_router_reads(self):
        read = set(re.findall(r'raw\.get\("([a-z_]+)"', CONFIG_PY.read_text(encoding="utf-8")))
        module = C.load_verifier(G2_TEMPLATE, Path(tempfile.mkdtemp(prefix="g2-keys-")))
        self.assertEqual(set(module.ROUTER_KEYS), read)

    def test_no_credential_material(self):
        for p in G2.rglob("*"):
            if p.is_file() and "__pycache__" not in p.parts:
                text = p.read_text(encoding="utf-8")
                for marker in ("gsk" + "_", "PRIVATE" + " KEY", "BEGIN" + " OPENSSH", "Bearer" + " "):
                    self.assertNotIn(marker, text, p.name)


class VerifierBehaviourTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp(prefix="g2-verify-"))
        cls.g1 = C.load_verifier(G1_TEMPLATE, cls.tmp)
        cls.g2 = C.load_verifier(G2_TEMPLATE, cls.tmp)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, True)

    def host(self, name: str, router: dict, *, goal_schema: bool = True, db: bool = True) -> Path:
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
        if db:
            make_db(root / "core" / "lilith-dev.db", goal_schema=goal_schema)
        return root

    def codes(self, module, root: Path) -> set[str]:
        """Full failure lines ("CODE detail"); the goal DB path is moved into the fixture host."""
        module.GOAL_DB = root / "core" / "lilith-dev.db"
        C.run_verifier(module, root)
        return set(module.failures)

    @property
    def g2_router(self) -> dict:
        return yaml.safe_load(G2_ROUTER.read_text(encoding="utf-8"))

    def test_g2_accepts_exactly_its_router_on_a_bootstrapped_db(self):
        root = self.host("g2", self.g2_router)
        g2, g1 = self.codes(self.g2, root), self.codes(self.g1, root)
        self.assertFalse(kinds(g2) & (LANE_CODES | GOAL_CODES | C.WORLD_CONTEXT_CODES))
        self.assertEqual({c for c in g1 if kinds({c}) & LANE_CODES}, {"SHADOW_LANE_NOT_SHADOW goals_mode", "LANE_MODE_NOT_SHADOW goals_mode"})   # g1 refuses
        self.assertEqual({c for c in g2 if not kinds({c}) & (LANE_CODES | GOAL_CODES)},                       # nothing else differs
                         {c for c in g1 if not kinds({c}) & LANE_CODES})

    def test_g2_refuses_to_start_until_the_goal_schema_is_bootstrapped(self):
        router = self.g2_router
        no_tables = self.host("no-goal-tables", router, goal_schema=False)
        db = no_tables / "core" / "lilith-dev.db"
        before = db.read_bytes()
        self.assertEqual({c for c in self.codes(self.g2, no_tables) if kinds({c}) & GOAL_CODES},
                         {"GOAL_SCHEMA_NOT_BOOTSTRAPPED goal", "GOAL_SCHEMA_NOT_BOOTSTRAPPED goal_trace"})
        self.assertEqual(db.read_bytes(), before)                                  # the check created nothing
        self.assertEqual(sorted(p.name for p in db.parent.iterdir()), ["lilith-dev.db"])   # no journal/WAL left
        self.assertIn("GOAL_DB_MISSING", self.codes(self.g2, self.host("no-db", router, db=False)))
        drifted = self.host("drifted", router)
        with sqlite3.connect(drifted / "core" / "lilith-dev.db") as c:
            c.execute("ALTER TABLE goal_trace ADD COLUMN extra TEXT")
        self.assertIn("GOAL_SCHEMA_MISMATCH goal_trace", self.codes(self.g2, drifted))
        garbage = self.host("garbage", router, db=False)
        (garbage / "core").mkdir(); (garbage / "core" / "lilith-dev.db").write_bytes(b"TEST_ONLY not a database" * 64)
        self.assertIn("GOAL_DB_UNREADABLE", self.codes(self.g2, garbage))

    def test_g2_refuses_the_g1_router_and_any_other_lane_mode_channel_or_key(self):
        cases = {
            "g1-router-goals-shadow": ({"goals_mode": "shadow"}, "LANE_MODE_NOT_LIVE goals_mode"),
            "goals-mode-missing": ({"goals_mode": None}, "LANE_MODE_NOT_LIVE goals_mode"),
            "goals-mode-upper": ({"goals_mode": "LIVE"}, "LANE_MODE_NOT_LIVE goals_mode"),
            "goals-mode-unknown": ({"goals_mode": "on"}, "LANE_MODE_NOT_LIVE goals_mode"),
            "goals-off": ({"goals_enabled": False}, "LANE_NOT_ON goals_enabled"),
            "goals-string-true": ({"goals_enabled": "true"}, "LANE_NOT_ON goals_enabled"),
            "wm-live": ({"cognitive_mode": "live"}, "LANE_MODE_NOT_SHADOW cognitive_mode"),
            "wm-mode-missing": ({"cognitive_mode": None}, "LANE_MODE_NOT_SHADOW cognitive_mode"),
            "wm-off": ({"cognitive_enabled": False}, "LANE_NOT_ON cognitive_enabled"),
            "all-channels": ({"cognitive_channels": ["*"]}, "LANE_CHANNELS cognitive_channels"),
            "telegram-too": ({"cognitive_channels": ["lilith_os", "telegram"]}, "LANE_CHANNELS cognitive_channels"),
            "discord": ({"cognitive_channels": ["discord"]}, "LANE_CHANNELS cognitive_channels"),
            "chat-scoped": ({"cognitive_channels": ["lilith_os:one"]}, "LANE_CHANNELS cognitive_channels"),
            "no-channel": ({"cognitive_channels": []}, "LANE_CHANNELS cognitive_channels"),
            "goals-own-channels": ({"goals_channels": ["telegram"]}, "ROUTER_KEY_UNKNOWN goals_channels"),
            "misspelt-mode": ({"goal_mode": "live"}, "ROUTER_KEY_UNKNOWN goal_mode"),
            "router-live": ({"mode": "live"}, "ROUTER_MODE_NOT_SHADOW"),
            "router-wider": ({"live_channels": ["lilith_os", "telegram"]}, "ROUTER_SCOPE"),
            "reasoning-live-mode": ({"reasoning_mode": "live"}, "LANE_MODE_NOT_SHADOW reasoning_mode"),
            "planning-live-mode": ({"planning_mode": "live"}, "LANE_MODE_NOT_SHADOW planning_mode"),
            "canonical-config": ({"canonical_ltm_config_valid": True}, "ROUTER_KEY_UNKNOWN canonical_ltm_config_valid"),
        }
        for lane in LANES[2:]:
            cases[lane] = ({lane: True}, f"LANE_NOT_OFF {lane}")
        for name, (change, code) in cases.items():
            with self.subTest(case=name):
                router = dict(self.g2_router, **change)
                router = {k: v for k, v in router.items() if v is not None}
                self.assertIn(code, self.codes(self.g2, self.host(f"case-{name}", router)))

    def test_g2_still_pins_the_adapter_and_the_prod_module(self):
        root = self.host("adapter-changed", self.g2_router)
        adapter = root / "home" / "lilith_router" / "world_context.py"
        adapter.write_bytes(adapter.read_bytes() + b"\n# TEST_ONLY\n")
        (root / "home" / "lilith_router" / "_prod_world_context.py").unlink()
        self.assertEqual(kinds(self.codes(self.g2, root)) & C.WORLD_CONTEXT_CODES,
                         {"WORLD_CONTEXT_NOT_THE_COG1_ADAPTER", "PROD_WORKING_MEMORY_NOT_PINNED"})


if __name__ == "__main__":
    unittest.main()
