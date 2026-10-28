"""Offline checks for bin/install_wm2.sh. TEST_ONLY; no host.

    python -m unittest discover -s integrations/hermes/release/dev-f9c2-cog1-wm2/tests -p "test_*.py"

install_wm2.sh is adapted from the merged install_wm1.sh: the tests require its guard functions to be the wm1 (and so
the reviewed cog1) ones verbatim. The install / revert simulation (tests/sim_install_wm2.sh) runs only with
COG1_RUN_SIM=1 as root.
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

WM2 = Path(__file__).resolve().parents[1]
REPO = WM2.parents[3]
REL = REPO / "integrations" / "hermes" / "release"
INSTALLER = WM2 / "bin" / "install_wm2.sh"
SIM = WM2 / "tests" / "sim_install_wm2.sh"
TEXT = INSTALLER.read_text(encoding="utf-8")
WM1_TEXT = (REL / "dev-f9c2-cog1-wm1" / "bin" / "install_wm1.sh").read_text(encoding="utf-8")
COG1_TEXT = (REL / "dev-f9c2-cog1" / "bin" / "install_cog1.sh").read_text(encoding="utf-8")
SOURCES = {
    "router.wm2.yaml": "integrations/hermes/release/dev-f9c2-cog1-wm2/home/router.yaml",
    "router.wm1.yaml": "integrations/hermes/release/dev-f9c2-cog1-wm1/home/router.yaml",
    "verify_release.wm2.py.tmpl": "integrations/hermes/release/dev-f9c2-cog1-wm2/templates/bin/verify_release.py.tmpl",
    "verify_release.wm1.py.tmpl": "integrations/hermes/release/dev-f9c2-cog1-wm1/templates/bin/verify_release.py.tmpl",
    "RELEASE_ID": "integrations/hermes/release/dev-f9c2-cog1-wm2/RELEASE_ID",
}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def function(text: str, name: str) -> str:
    return text.split(f"{name}() {{", 1)[1].split("\n}\n", 1)[0]


def wm1_to_wm2(text: str) -> str:
    """install_wm1.sh with only the release-step renames applied (ids, payload names, labels)."""
    for a, b in (("cog1.yaml", "@OLD.yaml"), ("verify_release.cog1", "verify_release.@OLD"), ("wm1", "wm2"),
                 ("WM1", "WM2"), ("@OLD", "wm1"), ("COG1_RENDER_MISMATCH", "WM1_RENDER_MISMATCH")):
        text = text.replace(a, b)
    return text


class InstallerContractTest(unittest.TestCase):
    def test_payload_pins_are_the_reviewed_repository_bytes(self):
        block = TEXT.split("declare -A PAYLOAD=(", 1)[1].split("\n)", 1)[0]
        self.assertEqual(dict(re.findall(r"\[([^\]]+)\]=([0-9a-f]{64})", block)),
                         {name: sha(REPO / path) for name, path in SOURCES.items()})

    def test_the_guards_are_the_reviewed_wm1_and_cog1_guards(self):
        for name in ("gateway_stopped", "no_forget_pending", "take_forget_lock", "payload_ok", "verify_full",
                     "switch_current", "inject", "preconditions"):
            with self.subTest(function=name):
                self.assertEqual(function(TEXT, name), function(WM1_TEXT, name))
        for name in ("gateway_stopped", "no_forget_pending", "take_forget_lock", "payload_ok", "verify_full",
                     "switch_current", "inject"):
            with self.subTest(function=name):
                self.assertEqual(function(TEXT, name), function(COG1_TEXT, name))
        sim_guard = lambda text: text.split("SIM=0\n", 1)[1].split("\nfi\n", 1)[0]
        self.assertEqual(sim_guard(TEXT), sim_guard(WM1_TEXT))
        self.assertIn("FORGET_LOCK=${FORGET}/state/.lock\n", TEXT)
        pre = function(TEXT, "preconditions")
        self.assertLess(pre.index("take_forget_lock"), pre.index("no_forget_pending"))

    def test_the_body_is_install_wm1_with_only_the_release_step_renamed(self):
        pin = re.compile(r"^  \[[^\]]+\]=[0-9a-f]{64}")                       # PAYLOAD pins: checked above
        body = lambda text: [l for l in text.split("set -Eeuo pipefail\n", 1)[1].splitlines() if not pin.match(l)]
        mine, base = body(TEXT), body(wm1_to_wm2(WM1_TEXT))
        self.assertEqual(len(mine), len(base))
        # Beyond the renames, only the revert target (wm1, World Model shadow) and the wm2 lane wording differ.
        self.assertEqual([(a, b) for a, b in zip(base, mine) if a != b], [
            ("OLD_ID=f293e72-f9c2-cog1", "OLD_ID=f293e72-f9c2-cog1-wm1"),
            ('  verify_full "${OLD_ID}" || { echo "WM2_REVERT_FAIL cog1 verify --full after revert" >&2; exit 1; }',
             '  verify_full "${OLD_ID}" || { echo "WM2_REVERT_FAIL wm1 verify --full after revert" >&2; exit 1; }'),
            ('  echo "WM2_REVERTED current=${OLD_ID} (every lane off)"',
             '  echo "WM2_REVERTED current=${OLD_ID} (World Model shadow)"'),
            ('    [[ $(sha "${LR}/router.yaml") == "${PAYLOAD[router.wm1.yaml]}" ]] || die "installed router.yaml is not the cog1 one"',
             '    [[ $(sha "${LR}/router.yaml") == "${PAYLOAD[router.wm1.yaml]}" ]] || die "installed router.yaml is not the wm1 one"'),
            ('    verify_full "${OLD_ID}" || die "cog1 verify --full before install"',
             '    verify_full "${OLD_ID}" || die "wm1 verify --full before install"'),
            ('    step "install the wm2 router.yaml (World Model lane in shadow on lilith_os); switch current"',
             '    step "install the wm2 router.yaml (World Model lane LIVE on lilith_os); switch current"'),
            ('    echo "WM2_INSTALLED current=${NEW_ID} (gateway not started; World Model lane shadow on lilith_os, every other lane off)"',
             '    echo "WM2_INSTALLED current=${NEW_ID} (gateway not started; World Model lane LIVE on lilith_os, every other lane off)"'),
        ])

    def test_release_ids_and_the_only_home_change(self):
        self.assertIn("OLD_ID=f293e72-f9c2-cog1-wm1\n", TEXT)
        self.assertIn("NEW_ID=f293e72-f9c2-cog1-wm2\n", TEXT)
        self.assertIn('install -o root -g lilith -m 0640 "$1" "${LR}/router.yaml.wm2-new"', TEXT)
        install = TEXT.split("  install)", 1)[1].split("  revert)", 1)[0]
        home_part = install.split("PHASE=home", 1)[1]
        self.assertEqual(re.findall(r"put_router \S+", home_part), ['put_router "${PAY}/router.wm2.yaml"'])
        self.assertEqual(re.findall(r"put_router \S+", function(TEXT, "revert")), ['put_router "${PAY}/router.wm1.yaml"'])
        self.assertNotIn("world_context.py\"", home_part)                  # adapter and PROD module untouched
        self.assertIn('sys.exit("WM1_RENDER_MISMATCH")', TEXT)             # rendered from the installed wm1 verifier
        self.assertIn('"${PAY}/verify_release.wm1.py.tmpl" "${OLD}/bin/verify_release.py"', TEXT)
        self.assertIn('"${PAY}/verify_release.wm2.py.tmpl" "${STAGE}/bin/verify_release.py"', TEXT)

    def test_installer_never_controls_services_or_deletes(self):
        code = "\n".join(line for line in TEXT.splitlines() if not line.lstrip().startswith("#"))
        for forbidden in (r"systemctl\s+(start|stop|restart|reload|enable|disable|daemon-reload|kill|mask|reset-failed)",
                          r"\brm\s", r"\bshred\b", r"\bunlink\b", r"\bcurl\b", r"\bwget\b", r"\bgcloud\b", r"\bsqlite3\b",
                          r"mktemp -u", r"gate_budget", r"\breset\b"):
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
