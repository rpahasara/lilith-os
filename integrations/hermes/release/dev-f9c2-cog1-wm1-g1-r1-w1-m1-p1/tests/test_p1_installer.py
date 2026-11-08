"""Offline checks for bin/install_p1.sh. TEST_ONLY; no host.

    python -m unittest discover -s integrations/hermes/release/dev-f9c2-cog1-wm1-g1-r1-w1-m1-p1/tests -p "test_*.py"

install_p1.sh is the merged install_m1.sh moved one release step (base m1, revert target m1): the tests
require every line outside the payload pins to be install_m1.sh after those renames. The install / revert simulation
(tests/sim_install_p1.sh) runs only with COG1_RUN_SIM=1 as root.
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

M1 = Path(__file__).resolve().parents[1]
REPO = M1.parents[3]
REL = REPO / "integrations" / "hermes" / "release"
INSTALLER = M1 / "bin" / "install_p1.sh"
SIM = M1 / "tests" / "sim_install_p1.sh"
TEXT = INSTALLER.read_text(encoding="utf-8")
RID_M1 = "f293e72-f9c2-cog1-wm1-g1-r1-w1-m1"
RID = "f293e72-f9c2-cog1-wm1-g1-r1-w1-m1-p1"
SOURCES = {
    "router.p1.yaml": "integrations/hermes/release/dev-f9c2-cog1-wm1-g1-r1-w1-m1-p1/home/router.yaml",
    "router.m1.yaml": "integrations/hermes/release/dev-f9c2-cog1-wm1-g1-r1-w1-m1/home/router.yaml",
    "verify_release.p1.py.tmpl": "integrations/hermes/release/dev-f9c2-cog1-wm1-g1-r1-w1-m1-p1/templates/bin/verify_release.py.tmpl",
    "verify_release.m1.py.tmpl": "integrations/hermes/release/dev-f9c2-cog1-wm1-g1-r1-w1-m1/templates/bin/verify_release.py.tmpl",
    "planning.p1.py": "integrations/hermes/overlays/dev-planning-hardening/lilith_router/planning.py",
    "planning.m1.py": "docs/architecture/slice-12/planning.py",
    "world_context.p1.py": "integrations/hermes/overlays/dev-cognition-private-intent/lilith_router/world_context.py",
    "world_context.m1.py": "integrations/hermes/overlays/dev-reasoning-hardening/lilith_router/world_context.py",
    "RELEASE_ID": "integrations/hermes/release/dev-f9c2-cog1-wm1-g1-r1-w1-m1-p1/RELEASE_ID",
}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class InstallerContractTest(unittest.TestCase):
    def test_payload_pins_are_the_repository_bytes(self):
        block = TEXT.split("declare -A PAYLOAD=(", 1)[1].split("\n)", 1)[0]
        self.assertEqual(dict(re.findall(r"\[([^\]]+)\]=([0-9a-f]{64})", block)),
                         {name: sha(REPO / path) for name, path in SOURCES.items()})

    def test_release_ids_and_the_only_home_change(self):
        self.assertIn(f"OLD_ID={RID_M1}\n", TEXT)
        self.assertIn(f"NEW_ID={RID}\n", TEXT)
        install = TEXT.split("  install)", 1)[1].split("  revert)", 1)[0]
        home_part = install.split("PHASE=home", 1)[1]
        self.assertEqual(re.findall(r"put_router \S+", home_part), ['put_router "${PAY}/router.p1.yaml"'])
        self.assertEqual(re.findall(r'put_code "\$\{PAY\}/(\S+)" (\S+)', home_part), [("world_context.p1.py", "world_context.py"), ("planning.p1.py", "planning.py")])
        reverting = TEXT.split("revert() {", 1)[1].split("PHASE=done", 1)[0]
        self.assertEqual(re.findall(r'put_code "\$\{PAY\}/(\S+)" (\S+)', reverting), [("world_context.m1.py", "world_context.py"), ("planning.m1.py", "planning.py")])
        self.assertIn('[[ $(sha "${LR}/world_context.py") == "${ADAPTER_SHA}" ]] || die "installed world_context is not the m1 adapter"', TEXT)
        self.assertIn('sys.exit("M1_RENDER_MISMATCH")', TEXT)
        self.assertIn('"${PAY}/verify_release.p1.py.tmpl" "${STAGE}/bin/verify_release.py"', TEXT)

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
