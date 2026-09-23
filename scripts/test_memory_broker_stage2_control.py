"""Control-only Stage-II tests; never activate a broker or VM service."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import os
from pathlib import Path
import subprocess
import time
import unittest
from unittest.mock import patch
import uuid

from scripts import memory_broker_stage2_control as stage2


ROOT = Path(__file__).resolve().parents[1]


class Stage2ControlContracts(unittest.TestCase):
    def test_marker_is_closed_fresh_and_not_stage_iii(self):
        issued = datetime(2026, 9, 23, 16, 0, tzinfo=timezone.utc)
        value = stage2.marker_value(issued, "a" * 32)
        self.assertEqual(value["purpose"], stage2.PURPOSE)
        self.assertEqual(value["stage"], "B1B2B_II / ACTIVATE_AND_ISOLATION_TEST")
        self.assertEqual(value["authorityMode"], "SYNTHETIC_ONLY")
        self.assertEqual(value["canonicalCapability"], "DISABLED")
        self.assertEqual(value["releaseSha"], stage2.RELEASE)
        self.assertEqual(value["ownerActor"], "rpahasara")
        self.assertEqual(value["expiresAt"], (issued + timedelta(minutes=30))
                         .isoformat(timespec="seconds").replace("+00:00", "Z"))
        self.assertNotIn("B1B2B_III", str(value))
        self.assertEqual(value["serviceSha256"], stage2.HASHES[
            Path("/etc/systemd/system/lilith-memory-broker.service")])
        self.assertEqual(value["identityMapSha256"], stage2.HASHES[
            stage2.CONFIG / "identities.json"])

    def test_prod_metadata_is_rejected_before_any_mutation(self):
        observed = {
            "project/project-id": stage2.PROJECT,
            "instance/zone": f"projects/763184673487/zones/{stage2.ZONE}",
            "instance/id": "1332996232081478576",
            "instance/name": "lilith-01",
        }
        with patch.object(stage2.os, "geteuid", return_value=0, create=True):
            with self.assertRaisesRegex(stage2.Stage2Error, "PROD_FORBIDDEN"):
                stage2.assert_host(lookup=observed.__getitem__,
                                   hostname=stage2.HOSTNAME,
                                   machine_id=stage2.MACHINE_ID)

    def test_no_mutation_when_preflight_or_marker_fails(self):
        with patch.object(stage2, "preflight",
                          side_effect=stage2.Stage2Error("DRIFT")):
            with patch.object(stage2.os, "open") as opening:
                with self.assertRaisesRegex(stage2.Stage2Error, "DRIFT"):
                    stage2.authorize()
                opening.assert_not_called()
        with patch.object(stage2, "verify_marker",
                          side_effect=stage2.Stage2Error("NO_OWNER_AUTH")):
            with patch.object(stage2, "run_fixed") as command:
                with self.assertRaisesRegex(stage2.Stage2Error, "NO_OWNER_AUTH"):
                    stage2.execute()
                command.assert_not_called()

    def test_effective_broker_and_probe_hardening_are_exact(self):
        expected = stage2.EXPECTED_HARDENING
        self.assertEqual(set(expected), set(stage2.HARDENING))
        self.assertEqual(expected["RestrictAddressFamilies"], "AF_UNIX")
        self.assertEqual(expected["IPAddressDeny"], "0.0.0.0/0 ::/0")
        self.assertEqual(expected["ProtectHome"], "yes")
        self.assertEqual(expected["ProtectSystem"], "strict")
        self.assertEqual(expected["CapabilityBoundingSet"], "")
        self.assertEqual(expected["AmbientCapabilities"], "")
        with patch.object(stage2, "effective_hardening", return_value=expected):
            self.assertEqual(stage2.assert_broker_hardening(), expected)
        with patch.object(stage2, "effective_hardening",
                          return_value={**expected, "ProtectHome": "no"}):
            with self.assertRaisesRegex(stage2.Stage2Error, "HARDENING_DRIFT"):
                stage2.assert_broker_hardening()

    def test_probe_and_relay_sources_are_closed(self):
        compile(stage2.ISOLATION_PROBE, "fixed-isolation-probe", "exec")
        compile(stage2.RELAY_SOURCE, "transient-relay-harness", "exec")
        compile(stage2.NEGATIVE_CLIENT, "fixed-negative-peer", "exec")
        for name in ("home", "legacy_dev_db", "release", "venv", "config",
                     "identities", "outside_state", "af_unix", "af_inet", "af_inet6"):
            self.assertIn(name, stage2.ISOLATION_PROBE)
        self.assertIn("SO_PEERCRED", stage2.trace_peer_uid.__doc__)
        self.assertNotIn("subprocess", stage2.ISOLATION_PROBE)
        self.assertNotIn("eval(", stage2.ISOLATION_PROBE)
        self.assertNotIn("exec(", stage2.ISOLATION_PROBE)
        self.assertNotIn("argparse", stage2.ISOLATION_PROBE)

    def test_workflow_is_separate_owner_only_main_only_no_auto_trigger(self):
        workflow = (ROOT / ".github/workflows/memory-broker-dev-stage2-runtime.yml"
                    ).read_text(encoding="utf-8")
        self.assertIn("workflow_dispatch:", workflow)
        self.assertNotIn("\n  push:", workflow)
        self.assertNotIn("\n  pull_request:", workflow)
        self.assertIn("github.actor == 'rpahasara'", workflow)
        self.assertIn("github.ref == 'refs/heads/main'", workflow)
        self.assertIn("I AUTHORIZE B1B2B_II ACTIVATE_AND_ISOLATION_TEST", workflow)
        self.assertIn("instances describe", workflow)
        self.assertIn("< scripts/memory_broker_stage2_control.py", workflow)
        self.assertIn("failure-stop", workflow)
        self.assertIn("audit_core_api_production_read_only.py", workflow)
        self.assertNotIn("systemctl enable", workflow)
        self.assertNotIn("Stage III", workflow)
        self.assertNotIn("deploy.yml", workflow)

    @unittest.skipUnless(os.name == "posix", "Linux systemd option check")
    def test_linux_transient_unit_options_exist_without_running_unit(self):
        help_text = subprocess.run(
            ["/usr/bin/systemd-run", "--help"], check=True, capture_output=True,
            text=True, timeout=10).stdout
        for option in ("--remain-after-exit", "--pipe", "--service-type",
                       "--property", "--unit"):
            self.assertIn(option, help_text)
        self.assertTrue(any("systemd-run" in value for value in
                            stage2.probe_equivalent_sandbox.__code__.co_consts
                            if isinstance(value, str)))

    @unittest.skipUnless(os.name == "posix", "Linux transient-unit integration")
    def test_linux_transient_probe_lifecycle_on_ci_only(self):
        if not Path("/run/systemd/system").is_dir():
            self.skipTest("systemd is not PID 1")
        if subprocess.run(["sudo", "-n", "true"], capture_output=True).returncode:
            self.skipTest("passwordless CI sudo unavailable")
        unit = "lilith-stage2-ci-" + uuid.uuid4().hex + ".service"
        runner = subprocess.Popen(
            ["sudo", "-n", "/usr/bin/systemd-run", "--quiet", "--pipe",
             "--service-type=oneshot", "--remain-after-exit",
             "--unit=" + unit, "/usr/bin/printf", "PROBE_OK"],
            stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, text=True,
        )
        try:
            for _ in range(100):
                result = subprocess.run(
                    ["sudo", "-n", "/usr/bin/systemctl", "show", unit,
                     "--property=ActiveState,SubState", "--no-pager"],
                    capture_output=True, text=True, timeout=5,
                )
                if "ActiveState=active" in result.stdout and "SubState=exited" in result.stdout:
                    break
                self.assertIn(runner.poll(), (None, 0),
                              "transient unit failed to start")
                time.sleep(0.1)
            else:
                self.fail("transient unit did not reach active/exited")
        finally:
            subprocess.run(["sudo", "-n", "/usr/bin/systemctl", "stop", unit],
                           capture_output=True, timeout=10)
        stdout, stderr = runner.communicate(timeout=10)
        self.assertEqual(runner.returncode, 0, stderr)
        self.assertEqual(stdout, "PROBE_OK")


if __name__ == "__main__":
    unittest.main()
