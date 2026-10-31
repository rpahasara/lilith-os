"""Offline contract for the e1 candidate (seven lanes in shadow). TEST_ONLY. NOT INSTALLED.

    python -B integrations/hermes/proposals/ethics-shadow-v0.1/test_e1_release.py

The candidate is generated from p1, so it must stay exactly what the generator writes, with only the intended differences from p1.
"""
from __future__ import annotations

import difflib
import hashlib
import importlib.util
import json
import re
import sys
import unittest
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
REL = REPO / "integrations/hermes/release"
P1 = REL / "dev-f9c2-cog1-wm1-g1-r1-w1-m1-p1"
E1 = REL / "dev-f9c2-cog1-wm1-g1-r1-w1-m1-p1-e1"
spec = importlib.util.spec_from_file_location("gen_e1_release", HERE / "gen_e1_release.py")
GEN = importlib.util.module_from_spec(spec)
sys.modules["gen_e1_release"] = GEN
spec.loader.exec_module(GEN)


def read(path):
    return path.read_bytes().decode("utf-8").replace("\r\n", "\n")


def changes(a, b):
    diff = list(difflib.unified_diff(read(a).splitlines(), read(b).splitlines(), lineterm="", n=0))
    return [l[1:] for l in diff if l[:1] == "-" and l[:3] != "---"], [l[1:] for l in diff if l[:1] == "+" and l[:3] != "+++"]


class Candidate(unittest.TestCase):
    def test_router_adds_only_ethics_in_shadow(self):
        a, b = yaml.safe_load(read(P1 / "home/router.yaml")), yaml.safe_load(read(E1 / "home/router.yaml"))
        self.assertEqual({k for k in set(a) | set(b) if a.get(k) != b.get(k)}, {"ethics_enabled", "ethics_mode"})
        self.assertEqual((b["ethics_enabled"], b["ethics_mode"], b["mode"]), (True, "shadow", "shadow"))
        self.assertEqual(b["cognitive_channels"], ["lilith_os"])

    def test_verifier_changes_are_exactly_the_lane_and_the_pins(self):
        gone, added = changes(P1 / "templates/bin/verify_release.py.tmpl", E1 / "templates/bin/verify_release.py.tmpl")
        self.assertEqual(len(gone), 5, gone)
        for needle in ("WORLD_CONTEXT_ADAPTER_SHA256", "exactly six lanes", "Slice 12 Planning, are on", "planning_mode", "PLANNING_NOT_PINNED"):
            self.assertTrue(any(needle in l for l in gone), needle)
        joined = "\n".join(added)
        for needle in ('"ethics_enabled": "ethics_mode"', "ETHICS_NOT_PINNED", "ETHICS_PRINCIPLES_NOT_PINNED"):
            self.assertIn(needle, joined)

    def test_pins_are_the_real_bytes(self):
        tmpl = read(E1 / "templates/bin/verify_release.py.tmpl")
        pin = lambda name: re.search(name + r' = "([0-9a-f]{64})"', tmpl).group(1)
        self.assertEqual(pin("WORLD_CONTEXT_ADAPTER_SHA256"), GEN.sha_blob(GEN.ADAPTER))
        self.assertEqual(pin("ETHICS_SHA256"), GEN.sha_blob(GEN.ETHICS))
        self.assertEqual(pin("ETHICS_PRINCIPLES_SHA256")[:8], "178990e5")
        self.assertEqual(pin("PLANNING_SHA256")[:8], "4c74337d")

    def test_the_adapter_cannot_ship_without_ethics_on(self):
        """Reasoning yields to Ethics in this adapter. One verifier requires the adapter's pin and Ethics in shadow, and p1's pin refuses the adapter."""
        tmpl = read(E1 / "templates/bin/verify_release.py.tmpl")
        self.assertIn('"ethics_enabled": "ethics_mode"', tmpl)
        self.assertNotIn(GEN.sha_blob(GEN.ADAPTER), read(P1 / "templates/bin/verify_release.py.tmpl"))

    def test_installer_pins_and_revert_targets(self):
        s = read(E1 / "bin/install_e1.sh")
        delta = json.loads(read(E1 / "RELEASE-DELTA.json"))
        for name, member in delta["members"].items():
            self.assertIn(f"[{name}]={member['sha256']}", s)
        self.assertEqual(len(delta["members"]), 9)
        self.assertIn(f"OLD_ID={GEN.P1_ID}\n", s)
        self.assertIn(f"NEW_ID={GEN.E1_ID}\n", s)
        self.assertIn('put_router "${PAY}/router.p1.yaml"', s)
        self.assertIn('put_code "${PAY}/ethics.p1.py" ethics.py', s)
        self.assertIn('put_code "${PAY}/world_context.p1.py" world_context.py', s)
        self.assertNotIn("planning.", s)
        for bad in ("m1.yaml", "m1.py", "P1_INSTALL", "P1_REVERT"):
            self.assertNotIn(bad, s)

    def test_the_candidate_is_what_the_generator_writes(self):
        self.assertEqual(read(E1 / "home/router.yaml"), GEN.router())
        self.assertEqual(read(E1 / "tests/sim_install_e1.sh"), GEN.simulator())

    def test_digest_of_release_id(self):
        self.assertEqual(hashlib.sha256((GEN.E1_ID + "\n").encode()).hexdigest(), json.loads(read(E1 / "RELEASE-DELTA.json"))["members"]["RELEASE_ID"]["sha256"])


if __name__ == "__main__":
    unittest.main()
