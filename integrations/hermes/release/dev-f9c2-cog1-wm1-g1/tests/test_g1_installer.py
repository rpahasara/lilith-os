"""Offline checks for bin/install_g1.sh. TEST_ONLY; no host.

    python -m unittest discover -s integrations/hermes/release/dev-f9c2-cog1-wm1-g1/tests -p "test_*.py"

install_g1.sh is adapted from the merged install_wm2.sh, which has the same base (wm1) and the same revert target: the
tests require its guard functions to be the wm2, wm1 (and so the reviewed cog1) ones verbatim, and every other line to
be install_wm2.sh with only the release step renamed. The install / revert simulation (tests/sim_install_g1.sh) runs
only with COG1_RUN_SIM=1 as root.
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

G1 = Path(__file__).resolve().parents[1]
REPO = G1.parents[3]
REL = REPO / "integrations" / "hermes" / "release"
INSTALLER = G1 / "bin" / "install_g1.sh"
SIM = G1 / "tests" / "sim_install_g1.sh"
TEXT = INSTALLER.read_text(encoding="utf-8")
WM2_TEXT = (REL / "dev-f9c2-cog1-wm2" / "bin" / "install_wm2.sh").read_text(encoding="utf-8")
WM1_TEXT = (REL / "dev-f9c2-cog1-wm1" / "bin" / "install_wm1.sh").read_text(encoding="utf-8")
COG1_TEXT = (REL / "dev-f9c2-cog1" / "bin" / "install_cog1.sh").read_text(encoding="utf-8")
SOURCES = {
    "router.g1.yaml": "integrations/hermes/release/dev-f9c2-cog1-wm1-g1/home/router.yaml",
    "router.wm1.yaml": "integrations/hermes/release/dev-f9c2-cog1-wm1/home/router.yaml",
    "verify_release.g1.py.tmpl": "integrations/hermes/release/dev-f9c2-cog1-wm1-g1/templates/bin/verify_release.py.tmpl",
    "verify_release.wm1.py.tmpl": "integrations/hermes/release/dev-f9c2-cog1-wm1/templates/bin/verify_release.py.tmpl",
    "RELEASE_ID": "integrations/hermes/release/dev-f9c2-cog1-wm1-g1/RELEASE_ID",
}
GUARDS = ("gateway_stopped", "no_forget_pending", "take_forget_lock", "payload_ok", "verify_full", "switch_current",
          "inject")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def function(text: str, name: str) -> str:
    return text.split(f"{name}() {{", 1)[1].split("\n}\n", 1)[0]


def wm2_to_g1(text: str) -> str:
    """install_wm2.sh with only the release-step renames applied (ids, payload names, labels)."""
    for a, b in (("f293e72-f9c2-cog1-wm2", "f293e72-f9c2-cog1-wm1-g1"), ("install_wm2.sh", "install_g1.sh"),
                 ("router.wm2.yaml", "router.g1.yaml"), ("verify_release.wm2", "verify_release.g1"),
                 ("WM2_", "G1_"), (".wm2-", ".g1-"), ("yaml.wm2-new", "yaml.g1-new"), ("the wm2 ", "the g1 "),
                 ("f9c2-cog1-wm2 DEV", "f9c2-cog1-wm1-g1 DEV"), ("while wm2 is current", "while g1 is current"),
                 ("unchanged by wm2", "unchanged by g1"), ("Adapted from install_wm1.sh", "Adapted from install_wm2.sh")):
        text = text.replace(a, b)
    return text


class InstallerContractTest(unittest.TestCase):
    def test_payload_pins_are_the_reviewed_repository_bytes(self):
        block = TEXT.split("declare -A PAYLOAD=(", 1)[1].split("\n)", 1)[0]
        self.assertEqual(dict(re.findall(r"\[([^\]]+)\]=([0-9a-f]{64})", block)),
                         {name: sha(REPO / path) for name, path in SOURCES.items()})

    def test_the_guards_are_the_reviewed_wm2_wm1_and_cog1_guards(self):
        for base in (WM2_TEXT, WM1_TEXT):
            for name in GUARDS + ("preconditions",):
                with self.subTest(function=name):
                    self.assertEqual(function(TEXT, name), function(base, name))
        for name in GUARDS:
            with self.subTest(function=name):
                self.assertEqual(function(TEXT, name), function(COG1_TEXT, name))
        sim_guard = lambda text: text.split("SIM=0\n", 1)[1].split("\nfi\n", 1)[0]
        self.assertEqual(sim_guard(TEXT), sim_guard(WM2_TEXT))
        self.assertIn("FORGET_LOCK=${FORGET}/state/.lock\n", TEXT)
        pre = function(TEXT, "preconditions")
        self.assertLess(pre.index("take_forget_lock"), pre.index("no_forget_pending"))

    def test_the_text_is_install_wm2_with_only_the_release_step_renamed(self):
        pin = re.compile(r"^  \[[^\]]+\]=[0-9a-f]{64}")                       # PAYLOAD pins: checked above
        lines = lambda text: [l for l in text.splitlines() if not pin.match(l)]
        mine, base = lines(TEXT), lines(wm2_to_g1(WM2_TEXT))
        self.assertEqual(len(mine), len(base))
        # Beyond the renames, only the description of the installed lanes differs (wm2: World Model LIVE; g1: World
        # Model and Goals in shadow).
        self.assertEqual([(a, b) for a, b in zip(base, mine) if a != b], [
            ("#   sudo bash install_g1.sh install <payload-dir>   stage releases/f293e72-f9c2-cog1-wm1-g1 beside wm1, install the wm2",
             "#   sudo bash install_g1.sh install <payload-dir>    stage releases/f293e72-f9c2-cog1-wm1-g1 beside wm1, install the g1"),
            ("#                                                    router.yaml (World Model lane LIVE on lilith_os), switch current,",
             "#                                                    router.yaml (World Model and Goals lanes in shadow on lilith_os),"),
            ("#                                                    re-pin, verify --full",
             "#                                                    switch current, re-pin, verify --full"),
            ("#   sudo bash install_g1.sh revert  <payload-dir>   restore the wm1 router.yaml (World Model shadow), switch current",
             "#   sudo bash install_g1.sh revert  <payload-dir>    restore the wm1 router.yaml (World Model shadow), switch current"),
            ('    step "install the g1 router.yaml (World Model lane LIVE on lilith_os); switch current"',
             '    step "install the g1 router.yaml (World Model and Goals lanes in shadow on lilith_os); switch current"'),
            ('    verify_full "${NEW_ID}" || { echo "G1_INSTALL_FAIL wm2 verify --full" >&2; exit 1; }',
             '    verify_full "${NEW_ID}" || { echo "G1_INSTALL_FAIL g1 verify --full" >&2; exit 1; }'),
            ('    echo "G1_INSTALLED current=${NEW_ID} (gateway not started; World Model lane LIVE on lilith_os, every other lane off)"',
             '    echo "G1_INSTALLED current=${NEW_ID} (gateway not started; World Model and Goals lanes shadow on lilith_os, every other lane off)"'),
        ])
        comments = lambda text: [l for l in text.splitlines() if pin.match(l)]
        self.assertEqual([l.split("#", 1)[1] for l in comments(TEXT) if "#" in l],
                         [" World Model + Goals shadow", " installed wm1: World Model shadow"])

    def test_release_ids_and_the_only_home_change(self):
        self.assertIn("OLD_ID=f293e72-f9c2-cog1-wm1\n", TEXT)
        self.assertIn("NEW_ID=f293e72-f9c2-cog1-wm1-g1\n", TEXT)
        self.assertIn('install -o root -g lilith -m 0640 "$1" "${LR}/router.yaml.g1-new"', TEXT)
        install = TEXT.split("  install)", 1)[1].split("  revert)", 1)[0]
        home_part = install.split("PHASE=home", 1)[1]
        self.assertEqual(re.findall(r"put_router \S+", home_part), ['put_router "${PAY}/router.g1.yaml"'])
        self.assertEqual(re.findall(r"put_router \S+", function(TEXT, "revert")), ['put_router "${PAY}/router.wm1.yaml"'])
        self.assertNotIn("world_context.py\"", home_part)                  # adapter and PROD module untouched
        self.assertIn('sys.exit("WM1_RENDER_MISMATCH")', TEXT)             # rendered from the installed wm1 verifier
        self.assertIn('"${PAY}/verify_release.wm1.py.tmpl" "${OLD}/bin/verify_release.py"', TEXT)
        self.assertIn('"${PAY}/verify_release.g1.py.tmpl" "${STAGE}/bin/verify_release.py"', TEXT)

    def test_installer_never_controls_services_deletes_or_touches_data(self):
        code = "\n".join(line for line in TEXT.splitlines() if not line.lstrip().startswith("#"))
        for forbidden in (r"systemctl\s+(start|stop|restart|reload|enable|disable|daemon-reload|kill|mask|reset-failed)",
                          r"\brm\s", r"\bshred\b", r"\bunlink\b", r"\bcurl\b", r"\bwget\b", r"\bgcloud\b", r"\bsqlite3\b",
                          r"mktemp -u", r"gate_budget", r"\breset\b", r"lilith-os/data", r"\.db\b", r"/os/goals"):
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
