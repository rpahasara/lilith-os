"""Synthetic contracts for the dormant, fixed Stage-III installation/dispatch."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import stat
import subprocess
import tempfile
import time
import unittest
from unittest.mock import patch

from scripts import memory_broker_stage3_dispatch as dispatch
from scripts import memory_broker_stage3_wiring_install as wiring


class FixedWiringContracts(unittest.TestCase):
    def test_installer_loads_only_verified_bytes_after_staging_gate(self):
        self.assertNotIn("control", wiring.__dict__)
        self.assertNotIn("dispatch", wiring.__dict__)
        source = Path(__file__).with_name("memory_broker_stage2_control.py")
        module = wiring.pinned_control({
            "memory_broker_stage2_control.py": source.read_bytes()})
        self.assertEqual(module.RELEASE,
                         "817a83e44cec8965479fd97fc30b7a0b3ae49ab2")
        with patch.object(wiring, "staged_bytes", side_effect=wiring.WiringInstallError(
                "STAGE3_WIRING_SOURCE_DIGEST")), \
             patch.object(wiring, "preflight") as preflight:
            with self.assertRaises(wiring.WiringInstallError):
                wiring.install_fixed()
            preflight.assert_not_called()

    def test_exact_protected_helper_and_dispatch_bytes_are_pinned(self):
        source = Path(__file__).parent
        for name, expected in wiring.FILES.items():
            with self.subTest(name=name):
                self.assertEqual(hashlib.sha256((source / name).read_bytes()).hexdigest(),
                                 expected)
        self.assertEqual(set(wiring.FILES), set(dispatch.HELPERS) |
                         {"memory_broker_stage3_dispatch.py"})

    def test_unit_is_fixed_manual_one_shot_not_enabled_or_restartable(self):
        unit = wiring.UNIT_BYTES.decode("ascii")
        self.assertIn("Type=exec\n", unit)
        self.assertIn("User=root\nGroup=root\n", unit)
        self.assertIn("Restart=no\n", unit)
        self.assertIn("RuntimeMaxSec=600\n", unit)
        self.assertIn("StartLimitBurst=1\n", unit)
        self.assertIn("ExecStart=/usr/bin/python3 -I -B " +
                      (dispatch.RELEASE / "scripts/memory_broker_stage3_dispatch.py").as_posix(),
                      unit)
        self.assertNotIn("[Install]", unit)
        self.assertNotIn("WantedBy=", unit)
        self.assertNotIn("ExecStartPre=", unit)
        self.assertNotIn("ExecStop=", unit)
        self.assertNotIn("Restart=on-", unit)

    def test_systemd_origin_binds_exact_incarnation_and_argv(self):
        invocation = "a" * 32
        argv = (b"/usr/bin/python3\0-I\0-B\0" +
                str(dispatch.RELEASE / "scripts/memory_broker_stage3_dispatch.py")
                .encode() + b"\0")
        fields = {"ActiveState": "active", "MainPID": "42001",
                  "InvocationID": invocation, "NRestarts": "0",
                  "FragmentPath": str(dispatch.UNIT)}
        self.assertTrue(dispatch.valid_origin(fields, invocation, argv, 42001))
        for changed, value in (("MainPID", "42002"),
                               ("NRestarts", "1"),
                               ("FragmentPath", "/run/systemd/system/other.service"),
                               ("ActiveState", "activating")):
            with self.subTest(changed=changed):
                self.assertFalse(dispatch.valid_origin(
                    dict(fields, **{changed: value}), invocation, argv, 42001))
        self.assertFalse(dispatch.valid_origin(fields, "b" * 32, argv, 42001))
        self.assertFalse(dispatch.valid_origin(fields, invocation,
                                               argv + b"--arbitrary\0", 42001))

    def test_release_manifest_is_exact_and_extra_members_fail_closed(self):
        with tempfile.TemporaryDirectory() as folder:
            release = Path(folder)
            scripts = release / "scripts"
            scripts.mkdir()
            helpers = {"helper.py": hashlib.sha256(b"fixed\n").hexdigest()}
            (scripts / "helper.py").write_bytes(b"fixed\n")
            (scripts / "memory_broker_stage3_dispatch.py").write_bytes(b"dispatch\n")
            files = {"helper.py": helpers["helper.py"],
                     "memory_broker_stage3_dispatch.py": hashlib.sha256(
                         b"dispatch\n").hexdigest()}
            (release / "manifest.json").write_bytes(dispatch.canonical({
                "schema": "Stage3A2FixedControlReleaseV1",
                "baseSha": dispatch.BASE_SHA, "files": files}))
            with patch.object(dispatch, "RELEASE", release), \
                 patch.object(dispatch, "HELPERS", helpers), \
                 patch.object(dispatch, "__file__", str(scripts /
                              "memory_broker_stage3_dispatch.py")), \
                 patch.object(dispatch, "directory"), \
                 patch.object(dispatch, "regular", side_effect=lambda path: path.read_bytes()):
                self.assertEqual(dispatch.verify_release(), hashlib.sha256(
                    (release / "manifest.json").read_bytes()).hexdigest())
                (scripts / "unexpected.py").write_bytes(b"x")
                with self.assertRaises(dispatch.DispatchError):
                    dispatch.verify_release()

    def test_staging_rejects_unlisted_members_and_digest_drift(self):
        with tempfile.TemporaryDirectory() as folder:
            staging = Path(folder)
            (staging / "one.py").write_bytes(b"wrong\n")
            with patch.object(wiring, "STAGING", staging), \
                 patch.object(wiring, "FILES", {"one.py": hashlib.sha256(
                     b"right\n").hexdigest()}), \
                 patch.object(wiring, "directory"), \
                 patch.object(wiring, "regular", side_effect=lambda path, mode:
                              path.read_bytes()):
                with self.assertRaises(wiring.WiringInstallError):
                    wiring.staged_bytes()
                (staging / "extra.py").write_bytes(b"extra\n")
                with self.assertRaises(wiring.WiringInstallError):
                    wiring.staged_bytes()

    @unittest.skipIf(os.name == "nt", "Linux O_NOFOLLOW/fsync contract")
    def test_dispatch_claim_is_durable_one_shot_without_authority_payload(self):
        with tempfile.TemporaryDirectory() as folder:
            marker = Path(folder) / "dispatch-attempt.json"
            with patch.object(dispatch, "ATTEMPT", marker), \
                 patch.object(dispatch, "directory"):
                dispatch.claim_once("a" * 64, "b" * 32)
                value = json.loads(marker.read_bytes())
                self.assertEqual(value, {
                    "schema": "Stage3A2DispatchAttemptV1",
                    "baseSha": dispatch.BASE_SHA,
                    "releaseDigestSha256": "a" * 64,
                    "systemdInvocationId": "b" * 32})
                self.assertEqual(stat.S_IMODE(marker.stat().st_mode), 0o600)
                with self.assertRaises(dispatch.DispatchError):
                    dispatch.claim_once("a" * 64, "b" * 32)


@unittest.skipUnless(
    os.name == "posix" and hasattr(os, "geteuid") and os.geteuid() == 0 and
    os.environ.get("STAGE3_WIRING_SYSTEMD_FIXTURE") == "1" and
    Path("/proc/1/comm").exists() and
    Path("/proc/1/comm").read_text().strip() == "systemd",
    "explicit root-only disposable real-systemd fixture")
class RealSystemdFixture(unittest.TestCase):
    def test_fixed_exec_stays_alive_and_never_restarts(self):
        """Only a synthetic runtime unit; never uses LILITH paths or authority."""
        unit_name = "stage3-a2-wiring-synthetic-fixture.service"
        unit_path = Path("/run/systemd/system") / unit_name
        self.assertFalse(unit_path.exists())
        self.assertEqual(subprocess.run(
            ["/usr/bin/systemctl", "show", unit_name,
             "--property=LoadState", "--no-pager"], check=True,
            capture_output=True, text=True).stdout.strip(),
            "LoadState=not-found")
        with tempfile.TemporaryDirectory(prefix="stage3-wiring-synthetic-") as folder:
            worker = Path(folder) / "worker.py"
            worker.write_text("import time\nwhile True: time.sleep(1)\n")
            raw = wiring.UNIT_BYTES.replace(
                f"{dispatch.RELEASE.as_posix()}/scripts/memory_broker_stage3_dispatch.py".encode(),
                str(worker).encode()).replace(
                    b"Description=LILITH DEV synthetic Stage-III A2 fixed one-shot final controller",
                    b"Description=Disposable synthetic Stage-III process-lifetime fixture")
            unit_path.write_bytes(raw)
            try:
                subprocess.run(["/usr/bin/systemctl", "daemon-reload"], check=True,
                               capture_output=True, timeout=15)
                before = wiring.UNIT_BYTES
                self.assertIn(b"Type=exec\n", raw)
                self.assertIn(b"Restart=no\n", raw)
                self.assertNotIn(b"[Install]", before)
                subprocess.run(["/usr/bin/systemctl", "start", unit_name],
                               check=True, capture_output=True, timeout=15)
                observed = subprocess.run(
                    ["/usr/bin/systemctl", "show", unit_name,
                     "--property=ActiveState,MainPID,NRestarts,UnitFileState",
                     "--no-pager"], check=True, capture_output=True,
                    text=True, timeout=10).stdout
                fields = dict(line.split("=", 1) for line in observed.splitlines())
                self.assertEqual(fields["ActiveState"], "active")
                self.assertGreater(int(fields["MainPID"]), 1)
                self.assertEqual(fields["NRestarts"], "0")
                self.assertEqual(fields["UnitFileState"], "static")
                self.assertEqual((Path("/proc") / fields["MainPID"] /
                                  "cmdline").read_bytes(),
                                 b"/usr/bin/python3\0-I\0-B\0" +
                                 str(worker).encode() + b"\0")
                subprocess.run(["/usr/bin/systemctl", "kill",
                                "--kill-whom=main", "--signal=SIGKILL", unit_name],
                               check=True, capture_output=True, timeout=10)
                deadline = time.monotonic() + 5
                while time.monotonic() < deadline:
                    state = subprocess.run(
                        ["/usr/bin/systemctl", "show", unit_name,
                         "--property=ActiveState,MainPID,NRestarts",
                         "--no-pager"], check=True, capture_output=True,
                        text=True, timeout=10).stdout
                    after = dict(line.split("=", 1) for line in state.splitlines())
                    if after["ActiveState"] != "active":
                        break
                    time.sleep(0.05)
                self.assertNotEqual(after["ActiveState"], "active")
                self.assertEqual(after["MainPID"], "0")
                self.assertEqual(after["NRestarts"], "0")
            finally:
                subprocess.run(["/usr/bin/systemctl", "stop", unit_name],
                               capture_output=True, timeout=10)
                subprocess.run(["/usr/bin/systemctl", "reset-failed", unit_name],
                               capture_output=True, timeout=10)
                if unit_path.exists():
                    unit_path.unlink()
                subprocess.run(["/usr/bin/systemctl", "daemon-reload"],
                               capture_output=True, timeout=15)


if __name__ == "__main__":
    unittest.main()
