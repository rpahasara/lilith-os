"""Offline checks for bin/install_cog1.sh. TEST_ONLY; no host.

    python -m unittest discover -s integrations/hermes/release/dev-f9c2-cog1/tests -p "test_*.py"

The full install / revert simulation (tests/sim_install_cog1.sh) needs root on a disposable Linux machine with
unshare and overlayfs; it runs here only when COG1_RUN_SIM=1 and the process is root, otherwise it is skipped.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import unittest
from pathlib import Path

COG1 = Path(__file__).resolve().parents[1]
REPO = COG1.parents[3]
INSTALLER = COG1 / "bin" / "install_cog1.sh"
SIM = COG1 / "tests" / "sim_install_cog1.sh"
TEXT = INSTALLER.read_text(encoding="utf-8")
DELTA = json.loads((COG1 / "RELEASE-DELTA.json").read_text(encoding="utf-8"))
SOURCES = {
    "world_context.py": DELTA["members"]["home/lilith_router/world_context.py"]["source"],
    "_prod_world_context.py": DELTA["members"]["home/lilith_router/_prod_world_context.py"]["source"],
    "world_context.f9c2-stub.py": "integrations/hermes/home/variants/dev-f9c2/lilith_router/world_context.py",
    "verify_release.cog1.py.tmpl": DELTA["members"]["bin/verify_release.py"]["template"],
    "verify_release.f9c2.py.tmpl": DELTA["members"]["bin/verify_release.py"]["base_template"],
    "RELEASE_ID": DELTA["members"]["RELEASE_ID"]["source"],
}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def payload_pins() -> dict[str, str]:
    block = TEXT.split("declare -A PAYLOAD=(", 1)[1].split("\n)", 1)[0]
    return dict(re.findall(r"\[([^\]]+)\]=([0-9a-f]{64})", block))


class InstallerContractTest(unittest.TestCase):
    def test_payload_pins_are_the_reviewed_repository_bytes(self):
        self.assertEqual(payload_pins(), {name: sha(REPO / path) for name, path in SOURCES.items()})

    def test_installed_f9c2_verifier_pin_is_the_f9c2_manifest_digest(self):
        manifest = dict(reversed(line.split("  ", 1)) for line in
                        (REPO / DELTA["base_manifest"]).read_text(encoding="utf-8").splitlines())
        pin = re.search(r"^F9C2_VERIFY_SHA=([0-9a-f]{64})", TEXT, re.M).group(1)
        self.assertEqual(pin, manifest["bin/verify_release.py"])
        self.assertEqual(pin, DELTA["members"]["bin/verify_release.py"]["from"])

    def test_release_ids_match_the_delta(self):
        self.assertIn(f"OLD_ID={DELTA['base_release']}\n", TEXT)
        self.assertIn(f"NEW_ID={DELTA['release']}\n", TEXT)

    def test_installer_never_controls_services_or_deletes(self):
        code = "\n".join(line for line in TEXT.splitlines() if not line.lstrip().startswith("#"))
        for forbidden in (r"systemctl\s+(start|stop|restart|reload|enable|disable|daemon-reload|kill|mask)",
                          r"\brm\s", r"\bshred\b", r"\bunlink\b", r"\bcurl\b", r"\bwget\b", r"\bgcloud\b",
                          r"\bsqlite3\b", r"\bchown\s+-R\s+\S+\s+\$\{HH\}"):
            with self.subTest(pattern=forbidden):
                self.assertIsNone(re.search(forbidden, code))
        self.assertEqual(re.findall(r"systemctl\s+\w+", code), ["systemctl show"])

    def test_simulation_hooks_are_refused_on_the_dev_host(self):
        self.assertIn('[[ $(hostname) != lilith-dev-01 ]] || die "F8_SIM refused on lilith-dev-01"', TEXT)
        self.assertIn('inject() { if [[ ${F8_SIM:-} == 1 && ${F8_FAIL_AT:-} == "$1" ]]', TEXT)

    @unittest.skipUnless(shutil.which("bash") and sys.platform != "win32", "bash syntax check needs Linux bash")
    def test_shell_syntax(self):
        for script in (INSTALLER, SIM):
            subprocess.run(["bash", "-n", str(script)], check=True)

    @unittest.skipUnless(os.environ.get("COG1_RUN_SIM") == "1" and hasattr(os, "geteuid") and os.geteuid() == 0,
                         "simulation needs COG1_RUN_SIM=1 and root on a disposable Linux machine")
    def test_install_and_revert_simulation(self):
        out = subprocess.run(["bash", str(SIM), str(REPO)], capture_output=True, text=True, timeout=600)
        self.assertEqual(out.returncode, 0, out.stdout[-4000:] + out.stderr[-2000:])
        self.assertIn("SIM_RESULT PASS", out.stdout)


if __name__ == "__main__":
    unittest.main()
