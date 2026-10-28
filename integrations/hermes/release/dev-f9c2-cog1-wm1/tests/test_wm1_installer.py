"""Offline checks for bin/install_wm1.sh. TEST_ONLY; no host.

    python -m unittest discover -s integrations/hermes/release/dev-f9c2-cog1-wm1/tests -p "test_*.py"

install_wm1.sh is adapted from the reviewed install_cog1.sh: the tests require its guard functions to be the cog1
ones verbatim. The install / revert simulation (tests/sim_install_wm1.sh) runs only with COG1_RUN_SIM=1 as root.
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

WM1 = Path(__file__).resolve().parents[1]
REPO = WM1.parents[3]
INSTALLER = WM1 / "bin" / "install_wm1.sh"
COG1_INSTALLER = REPO / "integrations" / "hermes" / "release" / "dev-f9c2-cog1" / "bin" / "install_cog1.sh"
SIM = WM1 / "tests" / "sim_install_wm1.sh"
TEXT = INSTALLER.read_text(encoding="utf-8")
COG1_TEXT = COG1_INSTALLER.read_text(encoding="utf-8")
SOURCES = {
    "router.wm1.yaml": "integrations/hermes/release/dev-f9c2-cog1-wm1/home/router.yaml",
    "router.cog1.yaml": "integrations/hermes/home/variants/dev-f9c2/router.yaml",
    "verify_release.wm1.py.tmpl": "integrations/hermes/release/dev-f9c2-cog1-wm1/templates/bin/verify_release.py.tmpl",
    "verify_release.cog1.py.tmpl": "integrations/hermes/release/dev-f9c2-cog1/templates/bin/verify_release.py.tmpl",
    "RELEASE_ID": "integrations/hermes/release/dev-f9c2-cog1-wm1/RELEASE_ID",
}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def function(text: str, name: str) -> str:
    return text.split(f"{name}() {{", 1)[1].split("\n}\n", 1)[0]


class InstallerContractTest(unittest.TestCase):
    def test_payload_pins_are_the_reviewed_repository_bytes(self):
        block = TEXT.split("declare -A PAYLOAD=(", 1)[1].split("\n)", 1)[0]
        self.assertEqual(dict(re.findall(r"\[([^\]]+)\]=([0-9a-f]{64})", block)),
                         {name: sha(REPO / path) for name, path in SOURCES.items()})

    def test_the_guards_are_the_reviewed_cog1_guards(self):
        for name in ("gateway_stopped", "no_forget_pending", "take_forget_lock", "payload_ok", "verify_full",
                     "switch_current", "inject"):
            with self.subTest(function=name):
                self.assertEqual(function(TEXT, name), function(COG1_TEXT, name))
        sim_guard = lambda text: text.split("SIM=0\n", 1)[1].split("\nfi\n", 1)[0]
        self.assertEqual(sim_guard(TEXT), sim_guard(COG1_TEXT))
        self.assertIn("FORGET_LOCK=${FORGET}/state/.lock\n", TEXT)
        pre = function(TEXT, "preconditions")
        self.assertLess(pre.index("take_forget_lock"), pre.index("no_forget_pending"))

    def test_release_ids_and_the_only_home_change(self):
        self.assertIn("OLD_ID=f293e72-f9c2-cog1\n", TEXT)
        self.assertIn("NEW_ID=f293e72-f9c2-cog1-wm1\n", TEXT)
        self.assertIn('install -o root -g lilith -m 0640 "$1" "${LR}/router.yaml.wm1-new"', TEXT)
        install = TEXT.split("  install)", 1)[1].split("  revert)", 1)[0]
        home_part = install.split("PHASE=home", 1)[1]
        self.assertEqual(re.findall(r"put_router \S+", home_part), ['put_router "${PAY}/router.wm1.yaml"'])
        self.assertNotIn("world_context.py\"", home_part)                  # adapter and PROD module untouched
        self.assertIn('sys.exit("COG1_RENDER_MISMATCH")', TEXT)            # rendered from the installed cog1 verifier

    def test_installer_never_controls_services_or_deletes(self):
        code = "\n".join(line for line in TEXT.splitlines() if not line.lstrip().startswith("#"))
        for forbidden in (r"systemctl\s+(start|stop|restart|reload|enable|disable|daemon-reload|kill|mask|reset-failed)",
                          r"\brm\s", r"\bshred\b", r"\bunlink\b", r"\bcurl\b", r"\bwget\b", r"\bgcloud\b", r"\bsqlite3\b",
                          r"mktemp -u"):
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
        out = subprocess.run(["bash", str(SIM), str(REPO)], capture_output=True, text=True, timeout=900)
        self.assertEqual(out.returncode, 0, out.stdout[-4000:] + out.stderr[-2000:])
        self.assertIn("SIM_RESULT PASS", out.stdout)


if __name__ == "__main__":
    unittest.main()
