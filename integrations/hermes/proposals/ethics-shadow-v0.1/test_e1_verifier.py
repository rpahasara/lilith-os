"""The e1 startup verifier, run on real assembled homes. Each change below must make it refuse. TEST_ONLY; no host.

    python -B integrations/hermes/proposals/ethics-shadow-v0.1/test_e1_verifier.py
"""
from __future__ import annotations

import shutil
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
REL = REPO / "integrations/hermes/release"
P1 = REL / "dev-f9c2-cog1-wm1-g1-r1-w1-m1-p1"
E1 = REL / "dev-f9c2-cog1-wm1-g1-r1-w1-m1-p1-e1"
O = REPO / "integrations/hermes/overlays"
sys.path.insert(0, str(REL / "dev-f9c2-cog1-wm1-g1-r1-w1" / "tests"))
sys.path.insert(0, str(P1 / "tests"))

import test_p1_release as PR  # noqa: E402

C = PR.C
MEMBERS = (("dev-workspace-private-trace", "workspace.py"), ("dev-motivation-private-trace", "motivation.py"), ("dev-planning-hardening", "planning.py"), ("dev-ethics-hardening", "world_context.py"), ("dev-ethics-hardening", "ethics.py"))
LANE = {"LANE_NOT_OFF", "LANE_NOT_ON", "LANE_MODE", "LANE_MODE_NOT_SHADOW", "LANE_MODE_UNEXPECTED", "LANES_MISMATCH", "ROUTER_MODE", "CHANNELS", "COGNITIVE_CHANNELS", "ROUTER_MISMATCH"}


def kinds(found):
    return {line.split()[0] for line in found}


class Verifier(unittest.TestCase):
    clean = None

    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp(prefix="e1-verify-"))
        cls.e1 = C.load_verifier(E1 / "templates/bin/verify_release.py.tmpl", cls.tmp)
        cls.p1 = C.load_verifier(P1 / "templates/bin/verify_release.py.tmpl", cls.tmp)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, True)

    host = PR.VerifierBehaviourTest.host

    @property
    def router(self):
        return yaml.safe_load((E1 / "home/router.yaml").read_text(encoding="utf-8"))

    def built(self, name, router=None):
        root = self.host(name, router or self.router)
        for overlay, member in MEMBERS:
            (root / "home/lilith_router" / member).write_bytes((O / overlay / "lilith_router" / member).read_bytes())
        return root

    def failures(self, module, root):
        C.run_verifier(module, root)
        return set(module.failures)

    def baseline(self):
        if Verifier.clean is None:
            Verifier.clean = self.failures(self.e1, self.built("clean"))
        return Verifier.clean

    def refuses(self, name, change, code=None):
        router = self.router
        change(router)
        found = self.failures(self.e1, self.built(name, router))
        extra = {line.replace(str(self.tmp / name), "ROOT") for line in found} - {line.replace(str(self.tmp / "clean"), "ROOT") for line in self.baseline()}
        self.assertTrue(extra, name)
        if code:
            self.assertTrue(any(code in line for line in extra), extra)

    def test_its_own_router_raises_no_lane_or_pin_failure(self):
        found = self.baseline()
        self.assertFalse({line for line in found if any(w in line for w in ("LANE", "ETHICS", "PLANNING", "ADAPTER", "CHANNEL"))}, found)

    def test_ethics_off_is_refused(self):
        self.refuses("no-ethics", lambda r: r.update(ethics_enabled=False), "ethics")

    def test_ethics_mode_missing_is_refused(self):
        self.refuses("no-mode", lambda r: r.pop("ethics_mode"), "ethics")

    def test_ethics_live_is_refused(self):
        self.refuses("eth-live", lambda r: r.update(ethics_mode="live"), "ethics")

    def test_each_shadow_lane_going_live_is_refused(self):
        for key in ("cognitive_mode", "goals_mode", "reasoning_mode", "workspace_mode", "motivation_mode", "planning_mode"):
            with self.subTest(key=key):
                self.refuses("live-" + key, lambda r, k=key: r.update({k: "live"}), key)

    def test_each_lane_turned_off_is_refused(self):
        for key in ("goals_enabled", "reasoning_enabled", "workspace_enabled", "motivation_enabled", "planning_enabled"):
            with self.subTest(key=key):
                self.refuses("off-" + key, lambda r, k=key: r.update({k: False}), key)

    def test_each_experimental_lane_turned_on_is_refused(self):
        for key in ("social_cognition_enabled", "memory_consolidation_enabled", "canonical_ltm_enabled"):
            with self.subTest(key=key):
                self.refuses("on-" + key, lambda r, k=key: r.update({k: True}), key)

    def test_an_unknown_flag_is_refused(self):
        self.refuses("unknown", lambda r: r.update(experimental_enabled=True), "experimental_enabled")

    def test_an_unknown_mode_key_is_refused(self):
        self.refuses("unknown-mode", lambda r: r.update(dream_mode="shadow"), "dream_mode")

    def test_router_mode_live_is_refused(self):
        self.refuses("router-live", lambda r: r.update(mode="live"))

    def test_an_added_channel_is_refused(self):
        self.refuses("channel", lambda r: r.update(cognitive_channels=["lilith_os", "telegram"]))

    def test_a_changed_or_missing_member_is_refused(self):
        clean = {line.replace(str(self.tmp / "clean"), "ROOT") for line in self.baseline()}
        for _, member in MEMBERS:
            for how in ("changed", "missing"):
                with self.subTest(member=member, how=how):
                    root = self.built(f"{how}-{member}")
                    target = root / "home/lilith_router" / member
                    if how == "changed":
                        target.write_bytes(target.read_bytes() + b"\n# TEST_ONLY\n")
                    else:
                        target.unlink()
                    self.assertTrue({line.replace(str(root), "ROOT") for line in self.failures(self.e1, root)} - clean, member)

    def test_the_p1_verifier_refuses_this_adapter(self):
        found = self.failures(self.p1, self.built("p1-verifier"))
        self.assertTrue(found)
        self.assertTrue(any("ethics" in line.lower() or "WORLD_CONTEXT" in line for line in found), found)


if __name__ == "__main__":
    unittest.main()
