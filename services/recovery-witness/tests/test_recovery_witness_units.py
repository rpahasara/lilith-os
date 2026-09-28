"""`systemd-analyze verify` of every shipped recovery-witness unit (repository only).

CI runs this module through `services/authority-dev/tests/test_recovery_witness_suite.py`
in the existing backend job (ubuntu-latest, where `systemd-analyze` exists). It
verifies temporary copies of the repository unit files only: the one pinned
`ExecStart` is replaced by `/usr/bin/true` (the `/opt` release is absent), as the
authority-dev CI step does. Nothing is installed, loaded, enabled, or started,
and nothing contacts DEV or PROD.

`systemd-analyze verify` exits 0 on many malformed settings (an unknown key, an
unparseable value): it only warns. A unit therefore passes only when the exit
status is 0 AND no diagnostic names a witness unit.
"""

from __future__ import annotations

import importlib.util
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SERVICE = Path(__file__).resolve().parents[1]
DEPLOY = SERVICE / "deploy"
SERVICE_UNIT = "lilith-recovery-witness.service"
EXEC_START = "ExecStart=/opt/lilith-authority-dev/current/venv/bin/python -B -m lilith_recovery_witness.server"
STAND_IN = "ExecStart=/usr/bin/true"
ANALYZE = shutil.which("systemd-analyze") if sys.platform.startswith("linux") else None
# In CI a missing verifier is a failure, never a skip.
IN_CI = os.environ.get("GITHUB_ACTIONS") == "true"


def shipped_units(deploy: Path = DEPLOY) -> tuple[str, ...]:
    """Every systemd unit file in the witness deploy tree (discovered, not listed)."""
    return tuple(sorted(path.name for path in deploy.iterdir()
                        if path.is_file() and path.suffix in (".service", ".socket")))


def stage(directory: Path, overrides: dict[str, str] | None = None, *, deploy: Path = DEPLOY) -> list[Path]:
    """Copy every shipped unit into `directory`, stubbing only the pinned ExecStart."""
    staged = []
    for name in shipped_units(deploy):
        text = (deploy / name).read_text(encoding="utf-8")
        if name == SERVICE_UNIT:
            lines = text.splitlines()
            if lines.count(EXEC_START) != 1 or sum(line.startswith("ExecStart=") for line in lines) != 1:
                raise AssertionError("the witness service must carry exactly the pinned ExecStart")
            text = text.replace(EXEC_START + "\n", STAND_IN + "\n")
        if overrides and name in overrides:
            text = overrides[name]
        target = directory / name
        target.write_text(text, encoding="utf-8")
        staged.append(target)
    return staged


def verify(units: list[Path]) -> tuple[int, list[str], list[str]]:
    """(exit status, diagnostics naming a witness unit, argv). Read-only on temp copies."""
    argv = [ANALYZE, "--man=no", "verify", *[str(unit) for unit in units]]
    result = subprocess.run(argv, capture_output=True, text=True, timeout=120, cwd=units[0].parent,
                            env={"PATH": "/usr/sbin:/usr/bin:/sbin:/bin", "SYSTEMD_LOG_COLOR": "0"})
    names = [unit.name for unit in units] + [str(units[0].parent)]
    lines = (result.stdout + result.stderr).splitlines()
    return result.returncode, [line for line in lines if any(name in line for name in names)], argv


class ShippedUnitSetTests(unittest.TestCase):
    def test_discovery_equals_the_shipped_release_units(self):
        spec = importlib.util.spec_from_file_location("witness_file_set_units", SERVICE / "witness_release_file_set.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        shipped = {name for name in module.DEPLOY_ASSETS if name.endswith((".service", ".socket"))}
        self.assertEqual(set(shipped_units()), shipped)
        self.assertEqual(shipped_units(), ("lilith-recovery-witness-owner.socket",
                                           "lilith-recovery-witness-signer.socket", SERVICE_UNIT))

    def test_the_verifier_never_touches_a_live_manager(self):
        # The only process this module runs is `systemd-analyze --man=no verify <temp copies>`.
        source = Path(__file__).read_text(encoding="utf-8")
        self.assertEqual(source.count("subprocess." + "run("), 1)
        for needle in ("system" + "ctl", "daemon-" + "reload", "g" + "cloud", "su" + "do ", "/etc/" + "systemd"):
            self.assertNotIn(needle, source)

    def test_the_pinned_exec_start_is_required(self):
        broken = (DEPLOY / SERVICE_UNIT).read_text(encoding="utf-8").replace(EXEC_START, EXEC_START + " --extra")
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "deploy"
            source.mkdir()
            for name in shipped_units():
                shutil.copy(DEPLOY / name, source / name)
            (source / SERVICE_UNIT).write_text(broken, encoding="utf-8")
            with self.assertRaises(AssertionError):
                stage(Path(directory), deploy=source)


@unittest.skipUnless(ANALYZE or IN_CI, "systemd-analyze is Linux-only (required in CI)")
class SystemdAnalyzeVerifyTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(ANALYZE, "systemd-analyze is required in CI")
        self.directory = tempfile.TemporaryDirectory()
        self.root = Path(self.directory.name)

    def tearDown(self):
        self.directory.cleanup()

    def test_every_shipped_witness_unit_verifies_clean(self):
        units = stage(self.root)
        self.assertEqual([unit.name for unit in units], list(shipped_units()))
        code, diagnostics, argv = verify(units)
        self.assertEqual((code, diagnostics), (0, []), diagnostics)
        self.assertEqual(argv[1:3], ["--man=no", "verify"])
        self.assertTrue(all(Path(arg).parent == self.root for arg in argv[3:]))  # temp copies only

    def test_a_malformed_unit_fails(self):
        service = (DEPLOY / SERVICE_UNIT).read_text(encoding="utf-8").replace(EXEC_START + "\n", STAND_IN + "\n")
        signer = (DEPLOY / "lilith-recovery-witness-signer.socket").read_text(encoding="utf-8")
        cases = {
            "unknown key": {SERVICE_UNIT: service.replace("[Service]\n", "[Service]\nBogusKey=1\n", 1)},
            "unparseable value": {SERVICE_UNIT: service.replace("[Service]\n", "[Service]\nType=bogus\n", 1)},
            "no ExecStart": {SERVICE_UNIT: "\n".join(line for line in service.splitlines()
                                                      if not line.startswith("ExecStart=")) + "\n"},
            "misspelled section": {SERVICE_UNIT: service.replace("[Service]", "[Servce]", 1)},
            "socket without a listener": {"lilith-recovery-witness-signer.socket": "\n".join(
                line for line in signer.splitlines() if not line.startswith("ListenStream=")) + "\n"},
        }
        for label, overrides in cases.items():
            with self.subTest(label=label), tempfile.TemporaryDirectory() as directory:
                code, diagnostics, _argv = verify(stage(Path(directory), overrides))
                self.assertTrue(code != 0 or diagnostics, (label, code, diagnostics))


if __name__ == "__main__":
    unittest.main()
