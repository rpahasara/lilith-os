"""Offline checks for bin/install_w1.sh. TEST_ONLY; no host.

    python -m unittest discover -s integrations/hermes/release/dev-f9c2-cog1-wm1-g1-r1-w1/tests -p "test_*.py"

install_w1.sh is the merged install_r1.sh moved one release step (base r1, revert target r1): the tests
require every line outside the payload pins to be install_r1.sh after those renames. The install / revert simulation
(tests/sim_install_w1.sh) runs only with COG1_RUN_SIM=1 as root.
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
INSTALLER = R1 / "bin" / "install_w1.sh"
SIM = R1 / "tests" / "sim_install_w1.sh"
TEXT = INSTALLER.read_text(encoding="utf-8")
R1_TEXT = (REL / "dev-f9c2-cog1-wm1-g1-r1" / "bin" / "install_r1.sh").read_text(encoding="utf-8")
RID_R1 = "f293e72-f9c2-cog1-wm1-g1-r1"
RID = "f293e72-f9c2-cog1-wm1-g1-r1-w1"
SOURCES = {
    "router.w1.yaml": "integrations/hermes/release/dev-f9c2-cog1-wm1-g1-r1-w1/home/router.yaml",
    "router.r1.yaml": "integrations/hermes/release/dev-f9c2-cog1-wm1-g1-r1/home/router.yaml",
    "verify_release.w1.py.tmpl": "integrations/hermes/release/dev-f9c2-cog1-wm1-g1-r1-w1/templates/bin/verify_release.py.tmpl",
    "verify_release.r1.py.tmpl": "integrations/hermes/release/dev-f9c2-cog1-wm1-g1-r1/templates/bin/verify_release.py.tmpl",
    "RELEASE_ID": "integrations/hermes/release/dev-f9c2-cog1-wm1-g1-r1-w1/RELEASE_ID",
}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def r1_to_w1(text: str) -> str:
    for a, b in ((RID_R1, "@NEW"), ("f293e72-f9c2-cog1-wm1-g1", RID_R1), ("@NEW", RID), ("f9c2-cog1-wm1-g1-r1 DEV", "f9c2-cog1-wm1-g1-r1-w1 DEV"), ("Adapted from install_g2.sh", "Adapted from install_r1.sh"),
                 ("install_r1.sh install", "install_w1.sh install"), ("install_r1.sh revert", "install_w1.sh revert"), ("usage: install_r1.sh", "usage: install_w1.sh"),
                 ("router.r1.yaml", "router.@w.yaml"), ("router.g1.yaml", "router.r1.yaml"), ("router.@w.yaml", "router.w1.yaml"), ("router.yaml.r1-new", "router.yaml.w1-new"),
                 ("verify_release.r1", "verify_release.@w"), ("verify_release.g1", "verify_release.r1"), ("verify_release.@w", "verify_release.w1"),
                 ("R1_INSTALL", "W1_INSTALL"), ("R1_REVERT", "W1_REVERT"), (".r1-failed", ".w1-failed"), ("G1_RENDER_MISMATCH", "R1_RENDER_MISMATCH"),
                 ("install the r1\n", "install the w1\n"), ("install the r1 ", "install the w1 "), ("the r1 router.yaml", "the w1 router.yaml"), ("the r1 verifier", "the w1 verifier"),
                 ("while r1 is current", "while w1 is current"), ("unchanged by r1", "unchanged by w1"), ("r1 verify --full", "w1 verify --full"),
                 ("g1 verify --full", "r1 verify --full"), ("the g1 ", "the r1 "), ("installed g1", "installed r1"), ("g1 is the revert target", "r1 is the revert target"), ("beside g1", "beside r1"), ("back to g1", "back to r1"), ("cog1, wm1 and g1", "cog1, wm1, g1 and r1"),
                 ("World Model, Goals and Reasoning shadow on lilith_os", "World Model, Goals, Reasoning and Workspace shadow on lilith_os"),
                 ("(World Model + Goals shadow)", "(World Model, Goals and Reasoning shadow)"), ("World Model + Goals shadow", "World Model, Goals and Reasoning shadow")):
        text = text.replace(a, b)
    return text


class InstallerContractTest(unittest.TestCase):
    def test_payload_pins_are_the_repository_bytes(self):
        block = TEXT.split("declare -A PAYLOAD=(", 1)[1].split("\n)", 1)[0]
        self.assertEqual(dict(re.findall(r"\[([^\]]+)\]=([0-9a-f]{64})", block)),
                         {name: sha(REPO / path) for name, path in SOURCES.items()})

    def test_the_text_is_install_r1_with_only_the_release_moved_one_step(self):
        pin = re.compile(r"^(  \[[^\]]+\]=)[0-9a-f]{64}")
        strip = lambda text: [pin.sub(r"\1@", l) for l in text.splitlines()]
        self.assertEqual(strip(TEXT), strip(r1_to_w1(R1_TEXT)))

    def test_release_ids_and_the_only_home_change(self):
        self.assertIn(f"OLD_ID={RID_R1}\n", TEXT)
        self.assertIn(f"NEW_ID={RID}\n", TEXT)
        install = TEXT.split("  install)", 1)[1].split("  revert)", 1)[0]
        home_part = install.split("PHASE=home", 1)[1]
        self.assertEqual(re.findall(r"put_router \S+", home_part), ['put_router "${PAY}/router.w1.yaml"'])
        self.assertNotIn('world_context.py"', home_part)
        self.assertIn('sys.exit("R1_RENDER_MISMATCH")', TEXT)
        self.assertIn('"${PAY}/verify_release.w1.py.tmpl" "${STAGE}/bin/verify_release.py"', TEXT)

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
