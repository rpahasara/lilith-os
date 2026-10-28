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

    def test_simulation_mode_is_refused_on_any_real_host(self):
        guard = TEXT.split("SIM=0\n", 1)[1].split("\nfi\n", 1)[0]
        for condition in ('[[ ${F8_SIM} == 1 ]] || die',
                          '[[ $(hostname) != lilith-* ]] || die',
                          '[[ $(cat /etc/machine-id 2>/dev/null) != "${DEV_MACHINE_ID}" ]] || die',
                          '[[ $(readlink /proc/1/ns/mnt) != "$(readlink /proc/self/ns/mnt)" ]] || die',
                          '[[ $(stat -f -c %T /opt) == overlayfs ]] || die'):
            self.assertIn(condition, guard)
        self.assertIn("DEV_MACHINE_ID=ae929170e6fa4c8ab9cc7b9547238d9d\n", TEXT)
        self.assertIn('[[ ${SIM} == 1 ]] || return 0', TEXT)                     # hooks are inert outside the sim
        self.assertIn('if [[ ${SIM} != 1 ]]; then [[ $(hostname) == lilith-dev-01 ]] || die', TEXT)

    def test_holds_the_forget_executors_own_lock(self):
        self.assertIn("FORGET_LOCK=${FORGET}/state/.lock\n", TEXT)
        self.assertIn("FORGET=/var/lib/hermes-forget\n", TEXT)
        self.assertIn('"stateDir": "/var/lib/hermes-forget/state"',
                      (REPO / "integrations/hermes/release/dev-f9c2/bin/install_f9c.sh").read_text(encoding="utf-8"))
        for executor in ("integrations/hermes/release/dev-f9c2/bin/hermes_forget_executor.py",
                         "integrations/hermes/overlays/dev-origin-forget-executor/hermes_forget_executor.py"):
            self.assertIn('self.cfg.state_dir / ".lock"', (REPO / executor).read_text(encoding="utf-8"))
        self.assertIn('flock -w 30 9 || die', TEXT)
        pre = TEXT.split("preconditions() {", 1)[1].split("\n}\n", 1)[0]
        self.assertLess(pre.index("take_forget_lock"), pre.index("no_forget_pending"))   # checked under the lock
        install = TEXT.split("  install)", 1)[1]
        self.assertLess(install.index("no_forget_pending"), install.index('PHASE=home'))  # re-checked before changes

    def test_only_a_fully_stopped_gateway_is_accepted(self):
        body = TEXT.split("gateway_stopped() {", 1)[1].split("\n}\n", 1)[0]
        self.assertEqual(re.findall(r'"(ActiveState=[^"]+)"', body),
                         ["ActiveState=inactive LoadState=loaded MainPID=0 SubState=dead",
                          "ActiveState=failed LoadState=loaded MainPID=0 SubState=failed"])

    def test_new_directories_never_reuse_an_existing_path(self):
        self.assertNotIn("mktemp -u", TEXT)
        self.assertIn('q=$(mktemp -d "${BACKUP}/cog1-revert-', TEXT)
        self.assertIn('kept=$(mktemp -d "${BASE}/releases/.cog1-failed-staging-', TEXT)
        self.assertIn('mv -n "${LR}/_prod_world_context.py" "${q}/"', TEXT)

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
