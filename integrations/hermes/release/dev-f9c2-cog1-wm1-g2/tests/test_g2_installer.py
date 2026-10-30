"""Offline checks for bin/install_g2.sh. TEST_ONLY; no host.

    python -m unittest discover -s integrations/hermes/release/dev-f9c2-cog1-wm1-g2/tests -p "test_*.py"

install_g2.sh is the merged install_g1.sh moved one release step (base g1, revert target g1): the tests require its
guard functions to be the g1, wm2, wm1 (and so the reviewed cog1) ones verbatim, and every other line to be
install_g1.sh with only the release step renamed. The install / revert simulation (tests/sim_install_g2.sh) runs only
with COG1_RUN_SIM=1 as root.
"""

from __future__ import annotations

import hashlib
import os
import re
import shutil
import subprocess
import sys
import unittest
from pathlib import Path

G2 = Path(__file__).resolve().parents[1]
REPO = G2.parents[3]
REL = REPO / "integrations" / "hermes" / "release"
INSTALLER = G2 / "bin" / "install_g2.sh"
SIM = G2 / "tests" / "sim_install_g2.sh"
TEXT = INSTALLER.read_text(encoding="utf-8")
G1_TEXT = (REL / "dev-f9c2-cog1-wm1-g1" / "bin" / "install_g1.sh").read_text(encoding="utf-8")
WM2_TEXT = (REL / "dev-f9c2-cog1-wm2" / "bin" / "install_wm2.sh").read_text(encoding="utf-8")
WM1_TEXT = (REL / "dev-f9c2-cog1-wm1" / "bin" / "install_wm1.sh").read_text(encoding="utf-8")
COG1_TEXT = (REL / "dev-f9c2-cog1" / "bin" / "install_cog1.sh").read_text(encoding="utf-8")
SOURCES = {
    "router.g2.yaml": "integrations/hermes/release/dev-f9c2-cog1-wm1-g2/home/router.yaml",
    "router.g1.yaml": "integrations/hermes/release/dev-f9c2-cog1-wm1-g1/home/router.yaml",
    "verify_release.g2.py.tmpl": "integrations/hermes/release/dev-f9c2-cog1-wm1-g2/templates/bin/verify_release.py.tmpl",
    "verify_release.g1.py.tmpl": "integrations/hermes/release/dev-f9c2-cog1-wm1-g1/templates/bin/verify_release.py.tmpl",
    "RELEASE_ID": "integrations/hermes/release/dev-f9c2-cog1-wm1-g2/RELEASE_ID",
}
GUARDS = ("gateway_stopped", "no_forget_pending", "take_forget_lock", "payload_ok", "verify_full", "switch_current",
          "inject")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def function(text: str, name: str) -> str:
    return text.split(f"{name}() {{", 1)[1].split("\n}\n", 1)[0]


def g1_to_g2(text: str) -> str:
    """install_g1.sh with only the mechanical release-step renames applied (new g1 -> g2, base wm1 -> g1)."""
    for a, b in (("f293e72-f9c2-cog1-wm1-g1", "@N"), ("f9c2-cog1-wm1-g1 DEV", "f9c2-cog1-wm1-g2 DEV"), ("install_g1.sh", "install_g2.sh"),
                 ("router.g1.yaml", "router.@n.yaml"), ("verify_release.g1", "verify_release.@n"), ("G1_", "G2_"), (".g1-", ".g2-"),
                 ("the g1 ", "the g2 "), ("while g1 is current", "while g2 is current"), ("unchanged by g1", "unchanged by g2"),
                 ("OLD_ID=f293e72-f9c2-cog1-wm1\n", "OLD_ID=@N1\n"), ("router.wm1.yaml", "router.g1.yaml"),
                 ("verify_release.wm1", "verify_release.g1"), ("WM1_RENDER_MISMATCH", "G1_RENDER_MISMATCH"), ("the wm1 one", "the g1 one"),
                 ("@N1", "f293e72-f9c2-cog1-wm1-g1"), ("@N", "f293e72-f9c2-cog1-wm1-g2"), ("@n", "g2")):
        text = text.replace(a, b)
    return text


class InstallerContractTest(unittest.TestCase):
    def test_payload_pins_are_the_reviewed_repository_bytes(self):
        block = TEXT.split("declare -A PAYLOAD=(", 1)[1].split("\n)", 1)[0]
        self.assertEqual(dict(re.findall(r"\[([^\]]+)\]=([0-9a-f]{64})", block)),
                         {name: sha(REPO / path) for name, path in SOURCES.items()})

    def test_the_guards_are_the_reviewed_g1_wm2_wm1_and_cog1_guards(self):
        for base in (G1_TEXT, WM2_TEXT, WM1_TEXT):
            for name in GUARDS + ("preconditions",):
                with self.subTest(function=name):
                    self.assertEqual(function(TEXT, name), function(base, name))
        for name in GUARDS:
            with self.subTest(function=name):
                self.assertEqual(function(TEXT, name), function(COG1_TEXT, name))
        sim_guard = lambda text: text.split("SIM=0\n", 1)[1].split("\nfi\n", 1)[0]
        self.assertEqual(sim_guard(TEXT), sim_guard(G1_TEXT))
        self.assertIn("FORGET_LOCK=${FORGET}/state/.lock\n", TEXT)
        pre = function(TEXT, "preconditions")
        self.assertLess(pre.index("take_forget_lock"), pre.index("no_forget_pending"))

    def test_the_text_is_install_g1_with_only_the_release_step_renamed(self):
        pin = re.compile(r"^  \[[^\]]+\]=[0-9a-f]{64}")                       # PAYLOAD pins: checked above
        lines = lambda text: [l for l in text.splitlines() if not pin.match(l)]
        mine, base = lines(TEXT), lines(g1_to_g2(G1_TEXT))
        self.assertEqual(len(mine), len(base))
        # Beyond the mechanical renames, only wording differs: base-release names in comments/messages and the lane
        # description (g1: World Model and Goals shadow; g2: World Model shadow, Goals LIVE). No logic line differs.
        self.assertEqual([(a, b) for a, b in zip(base, mine) if a != b], [
            ('# holds exactly the five PAYLOAD files below (from Git: this release, the wm1 router and the wm1 verifier template):', '# holds exactly the five PAYLOAD files below (from Git: this release, the g1 router and the g1 verifier template):'),
            ('#   sudo bash install_g2.sh install <payload-dir>    stage releases/f293e72-f9c2-cog1-wm1-g2 beside wm1, install the g1', '#   sudo bash install_g2.sh install <payload-dir>    stage releases/f293e72-f9c2-cog1-wm1-g2 beside g1, install the g2'),
            ('#                                                    router.yaml (World Model and Goals lanes in shadow on lilith_os),', '#                                                    router.yaml (World Model shadow, Goals LIVE on lilith_os),'),
            ('#   sudo bash install_g2.sh revert  <payload-dir>    restore the wm1 router.yaml (World Model shadow), switch current', '#   sudo bash install_g2.sh revert  <payload-dir>    restore the g1 router.yaml (World Model + Goals shadow), switch'),
            ('#                                                    back to wm1, re-pin, verify --full', '#                                                    current back to g1, re-pin, verify --full'),
            ('# Adapted from install_wm2.sh (same lock, gateway, staging, revert and simulation guards). The gateway must be fully', '# Adapted from install_g1.sh (same lock, gateway, staging, revert and simulation guards). The gateway must be fully'),
            ('# The provider-gate client token never leaves the host: the g2 verifier is rendered from the installed wm1', '# The provider-gate client token never leaves the host: the g2 verifier is rendered from the installed g1'),
            ('# verifier, after proving the wm1 template renders to exactly those installed bytes.', '# verifier, after proving the g1 template renders to exactly those installed bytes.'),
            ('# f9c2, cog1 and wm1 must all stay in place while g2 is current. wm1 is the revert target.', '# f9c2, cog1, wm1 and g1 must all stay in place while g2 is current. g1 is the revert target.'),
            ('  verify_full "${OLD_ID}" || { echo "G2_REVERT_FAIL wm1 verify --full after revert" >&2; exit 1; }', '  verify_full "${OLD_ID}" || { echo "G2_REVERT_FAIL g1 verify --full after revert" >&2; exit 1; }'),
            ('  echo "G2_REVERTED current=${OLD_ID} (World Model shadow)"', '  echo "G2_REVERTED current=${OLD_ID} (World Model + Goals shadow)"'),
            ('    verify_full "${OLD_ID}" || die "wm1 verify --full before install"', '    verify_full "${OLD_ID}" || die "g1 verify --full before install"'),
            ('    step "install the g2 router.yaml (World Model and Goals lanes in shadow on lilith_os); switch current"', '    step "install the g2 router.yaml (World Model shadow, Goals LIVE on lilith_os); switch current"'),
            ('    verify_full "${NEW_ID}" || { echo "G2_INSTALL_FAIL g1 verify --full" >&2; exit 1; }', '    verify_full "${NEW_ID}" || { echo "G2_INSTALL_FAIL g2 verify --full" >&2; exit 1; }'),
            ('    echo "G2_INSTALLED current=${NEW_ID} (gateway not started; World Model and Goals lanes shadow on lilith_os, every other lane off)"', '    echo "G2_INSTALLED current=${NEW_ID} (gateway not started; World Model shadow, Goals LIVE on lilith_os, every other lane off)"'),
        ])
        comments = lambda text: [l for l in text.splitlines() if pin.match(l)]
        self.assertEqual([l.split("#", 1)[1] for l in comments(TEXT) if "#" in l],
                         [" World Model shadow + Goals LIVE", " installed g1: World Model + Goals shadow"])

    def test_release_ids_and_the_only_home_change(self):
        self.assertIn("OLD_ID=f293e72-f9c2-cog1-wm1-g1\n", TEXT)
        self.assertIn("NEW_ID=f293e72-f9c2-cog1-wm1-g2\n", TEXT)
        self.assertIn('install -o root -g lilith -m 0640 "$1" "${LR}/router.yaml.g2-new"', TEXT)
        install = TEXT.split("  install)", 1)[1].split("  revert)", 1)[0]
        home_part = install.split("PHASE=home", 1)[1]
        self.assertEqual(re.findall(r"put_router \S+", home_part), ['put_router "${PAY}/router.g2.yaml"'])
        self.assertEqual(re.findall(r"put_router \S+", function(TEXT, "revert")), ['put_router "${PAY}/router.g1.yaml"'])
        self.assertNotIn("world_context.py\"", home_part)                  # adapter and PROD module untouched
        self.assertIn('sys.exit("G1_RENDER_MISMATCH")', TEXT)              # rendered from the installed g1 verifier
        self.assertIn('"${PAY}/verify_release.g1.py.tmpl" "${OLD}/bin/verify_release.py"', TEXT)
        self.assertIn('"${PAY}/verify_release.g2.py.tmpl" "${STAGE}/bin/verify_release.py"', TEXT)

    def test_installer_never_controls_services_deletes_or_touches_data(self):
        code = "\n".join(line for line in TEXT.splitlines() if not line.lstrip().startswith("#"))
        for forbidden in (r"systemctl\s+(start|stop|restart|reload|enable|disable|daemon-reload|kill|mask|reset-failed)",
                          r"\brm\s", r"\bshred\b", r"\bunlink\b", r"\bcurl\b", r"\bwget\b", r"\bgcloud\b", r"\bsqlite3\b",
                          r"mktemp -u", r"gate_budget", r"\breset\b", r"lilith-os/data", r"\.db\b", r"/os/goals",
                          r"_goals_db", r"CREATE TABLE", r"executescript"):   # never bootstraps the goal schema
            with self.subTest(pattern=forbidden):
                self.assertIsNone(re.search(forbidden, code))
        self.assertEqual(re.findall(r"systemctl\s+\w+", code), ["systemctl show"])

    @unittest.skipUnless(shutil.which("bash") and sys.platform != "win32", "bash syntax check needs Linux bash")
    def test_shell_syntax(self):
        for script in (INSTALLER, SIM):
            subprocess.run(["bash", "-n", str(script)], check=True)

    @unittest.skipUnless(os.environ.get("COG1_RUN_SIM") == "1" and hasattr(os, "geteuid") and os.geteuid() == 0,
                         "simulation needs COG1_RUN_SIM=1 and root on a disposable Linux machine")
    def test_install_and_revert_simulation(self):
        out = subprocess.run(["bash", str(SIM), str(REPO)], capture_output=True, text=True, timeout=1200)
        self.assertEqual(out.returncode, 0, out.stdout[-4000:] + out.stderr[-2000:])
        self.assertIn("SIM_RESULT PASS", out.stdout)


if __name__ == "__main__":
    unittest.main()
