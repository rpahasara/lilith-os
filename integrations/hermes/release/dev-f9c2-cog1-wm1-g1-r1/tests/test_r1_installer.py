"""Offline checks for bin/install_r1.sh. TEST_ONLY; no host.

    python -m unittest discover -s integrations/hermes/release/dev-f9c2-cog1-wm1-g1-r1/tests -p "test_*.py"

install_r1.sh is the merged install_g2.sh (same base g1, same revert target g1) with only the release renamed: the tests
require every line outside the payload pins to be install_g2.sh after those renames. The install / revert simulation
(tests/sim_install_r1.sh) runs only with COG1_RUN_SIM=1 as root.
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

R1 = Path(__file__).resolve().parents[1]
REPO = R1.parents[3]
REL = REPO / "integrations" / "hermes" / "release"
INSTALLER = R1 / "bin" / "install_r1.sh"
SIM = R1 / "tests" / "sim_install_r1.sh"
TEXT = INSTALLER.read_text(encoding="utf-8")
G2_TEXT = (REL / "dev-f9c2-cog1-wm1-g2" / "bin" / "install_g2.sh").read_text(encoding="utf-8")
RID = "f293e72-f9c2-cog1-wm1-g1-r1"
SOURCES = {
    "router.r1.yaml": "integrations/hermes/release/dev-f9c2-cog1-wm1-g1-r1/home/router.yaml",
    "router.g1.yaml": "integrations/hermes/release/dev-f9c2-cog1-wm1-g1/home/router.yaml",
    "verify_release.r1.py.tmpl": "integrations/hermes/release/dev-f9c2-cog1-wm1-g1-r1/templates/bin/verify_release.py.tmpl",
    "verify_release.g1.py.tmpl": "integrations/hermes/release/dev-f9c2-cog1-wm1-g1/templates/bin/verify_release.py.tmpl",
    "RELEASE_ID": "integrations/hermes/release/dev-f9c2-cog1-wm1-g1-r1/RELEASE_ID",
}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def g2_to_r1(text: str) -> str:
    for a, b in (("f293e72-f9c2-cog1-wm1-g2", RID), ("f9c2-cog1-wm1-g2 DEV", "f9c2-cog1-wm1-g1-r1 DEV"),
                 ("Adapted from install_g1.sh", "Adapted from install_g2.sh"), ("install_g2.sh install", "install_r1.sh install"),
                 ("install_g2.sh revert", "install_r1.sh revert"), ("usage: install_g2.sh", "usage: install_r1.sh"),
                 ("router.g2.yaml", "router.r1.yaml"), ("router.yaml.g2-new", "router.yaml.r1-new"),
                 ("verify_release.g2", "verify_release.r1"), ("G2_", "R1_"), (".g2-failed", ".r1-failed"),
                 ("install the g2\n", "install the r1\n"), ("the g2 ", "the r1 "), ("while g2 is current", "while r1 is current"),
                 ("unchanged by g2", "unchanged by r1"),
                 ("World Model shadow, Goals LIVE on lilith_os", "World Model, Goals and Reasoning shadow on lilith_os"),
                 ("World Model shadow + Goals LIVE", "World Model, Goals and Reasoning shadow"),
                 ("g2 verify --full", "r1 verify --full")):
        text = text.replace(a, b)
    return text


class InstallerContractTest(unittest.TestCase):
    def test_payload_pins_are_the_repository_bytes(self):
        block = TEXT.split("declare -A PAYLOAD=(", 1)[1].split("\n)", 1)[0]
        self.assertEqual(dict(re.findall(r"\[([^\]]+)\]=([0-9a-f]{64})", block)),
                         {name: sha(REPO / path) for name, path in SOURCES.items()})

    def test_the_text_is_install_g2_with_only_the_release_renamed(self):
        pin = re.compile(r"^(  \[[^\]]+\]=)[0-9a-f]{64}")
        strip = lambda text: [pin.sub(r"\1@", l) for l in text.splitlines()]
        self.assertEqual(strip(TEXT), strip(g2_to_r1(G2_TEXT)))

    def test_release_ids_and_the_only_home_change(self):
        self.assertIn("OLD_ID=f293e72-f9c2-cog1-wm1-g1\n", TEXT)
        self.assertIn(f"NEW_ID={RID}\n", TEXT)
        install = TEXT.split("  install)", 1)[1].split("  revert)", 1)[0]
        home_part = install.split("PHASE=home", 1)[1]
        self.assertEqual(re.findall(r"put_router \S+", home_part), ['put_router "${PAY}/router.r1.yaml"'])
        self.assertNotIn('world_context.py"', home_part)
        self.assertIn('sys.exit("G1_RENDER_MISMATCH")', TEXT)
        self.assertIn('"${PAY}/verify_release.r1.py.tmpl" "${STAGE}/bin/verify_release.py"', TEXT)

    def test_installer_never_controls_services_deletes_or_touches_data(self):
        code = "\n".join(line for line in TEXT.splitlines() if not line.lstrip().startswith("#"))
        for forbidden in (r"systemctl\s+(start|stop|restart|reload|enable|disable|daemon-reload|kill|mask|reset-failed)",
                          r"\brm\s", r"\bshred\b", r"\bunlink\b", r"\bcurl\b", r"\bwget\b", r"\bgcloud\b", r"\bsqlite3\b",
                          r"mktemp -u", r"gate_budget", r"\breset\b", r"lilith-os/data", r"\.db\b", r"/os/goals",
                          r"_goals_db", r"CREATE TABLE", r"executescript"):
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
