"""Isolated kernel-level pidfd and one-shot claim tests; no systemd or DEV."""

from __future__ import annotations

import os
from pathlib import Path
import select
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from scripts import memory_broker_stage3_guard_worker as guard


@unittest.skipUnless(sys.platform.startswith("linux") and hasattr(os, "pidfd_open"),
                     "Linux pidfd required")
class Stage3GuardLinuxContracts(unittest.TestCase):
    def test_pidfd_becomes_readable_when_synthetic_process_exits_naturally(self):
        child = subprocess.Popen([sys.executable, "-c",
                                  "import time; time.sleep(0.25)"])
        try:
            descriptor = os.pidfd_open(child.pid)
            try:
                boot, ticks = guard.process_identity(child.pid)
                self.assertEqual(len(boot), 36)
                self.assertGreater(ticks, 0)
                polling = select.poll()
                polling.register(descriptor, select.POLLIN | select.POLLHUP |
                                 select.POLLERR)
                self.assertFalse(polling.poll(0))
                self.assertEqual(child.wait(timeout=3), 0)
                self.assertTrue(polling.poll(3000))
            finally:
                os.close(descriptor)
        finally:
            child.wait(timeout=3)

    def test_claim_is_durable_and_cannot_be_reissued(self):
        with tempfile.TemporaryDirectory() as directory:
            claim = Path(directory) / "guard.claim.json"
            value = {
                "authorizationId": "a" * 32, "controllerPid": 123,
                "controllerBootId": "b" * 36, "controllerStartTicks": 456,
                "nonce": "c" * 64,
            }
            with patch.object(guard, "CLAIM", claim):
                guard.claim_once(value)
                self.assertEqual(claim.read_bytes(), guard.canonical({
                    "schema": "Stage3A2GuardClaimV1", **value}))
                self.assertEqual(claim.stat().st_mode & 0o777, 0o600)
                with self.assertRaises(FileExistsError):
                    guard.claim_once(value)

    def test_worker_exits_terminally_on_synthetic_controller_exit(self):
        with tempfile.TemporaryDirectory() as directory:
            child = subprocess.Popen([sys.executable, "-c",
                                      "import time; time.sleep(0.75)"])
            try:
                boot, ticks = guard.process_identity(child.pid)
                value = {
                    "authorizationId": "a" * 32,
                    "controllerPid": child.pid,
                    "controllerBootId": boot,
                    "controllerStartTicks": ticks,
                    "nonce": "b" * 64,
                }
                claim = Path(directory) / "guard.claim.json"
                with patch.object(guard, "CLAIM", claim), \
                     patch.object(guard, "read_config", return_value=value), \
                     patch.object(guard, "validate_context"), \
                     patch.object(guard, "notify_ready"), \
                     patch.object(sys, "argv", ["guard.py", "--run"]), \
                     self.assertRaisesRegex(guard.GuardError,
                                            "GUARD_CONTROLLER_EXITED"):
                    guard.run()
                self.assertEqual(child.wait(timeout=3), 0)
                self.assertTrue(claim.is_file())
            finally:
                child.wait(timeout=3)


if __name__ == "__main__":
    unittest.main()
