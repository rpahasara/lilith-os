"""Control-only Stage-II tests; never activate a broker or VM service."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import subprocess
import time
import unittest
from unittest.mock import MagicMock, patch
import uuid

from scripts import memory_broker_stage2_control as stage2


ROOT = Path(__file__).resolve().parents[1]


class Stage2ControlContracts(unittest.TestCase):
    @staticmethod
    def api_fields(pid=88740, started="Wed 2026-09-23 19:28:51 UTC"):
        return {
            "LoadState": "loaded", "ActiveState": "active", "SubState": "running",
            "MainPID": str(pid), "NRestarts": "0",
            "ExecMainStartTimestamp": started, "User": "lilith", "Group": "lilith",
            "WorkingDirectory": stage2.API_WORKDIR,
            "FragmentPath": stage2.API_UNIT.as_posix(), "DropInPaths": "",
            "ExecStart": "{ path=" + stage2.API_EXECUTABLE + " ; argv[]=" +
                         stage2.API_COMMAND + " ; ignore_errors=no ; start_time=[" +
                         started + "] ; stop_time=[n/a] ; pid=" + str(pid) +
                         " ; code=(null) ; status=0/0 }",
        }

    def api_snapshot(self, fields=None, hashes=None, health=None):
        fields = fields or self.api_fields()
        hashes = hashes or {}
        health = health or {"status": "ok", "database": True}
        def file_digest(path):
            return hashes.get(path, stage2.API_APP_SHA if path == stage2.API_APP
                              else stage2.API_FILES[path])
        with patch.object(stage2, "show", return_value=fields), \
             patch.object(stage2, "digest", side_effect=file_digest), \
             patch.object(stage2, "api_health", return_value=health):
            return stage2.capture_api_runtime_baseline(captured_at="2026-09-23T19:30:00Z")

    def test_marker_is_closed_fresh_and_not_stage_iii(self):
        issued = datetime(2026, 9, 23, 16, 0, tzinfo=timezone.utc)
        baseline = self.api_snapshot()
        value = stage2.marker_value(issued, "a" * 32, baseline)
        self.assertEqual(value["schemaVersion"], 2)
        self.assertEqual(value["apiRuntimeBaseline"], baseline)
        self.assertEqual(value["apiBaselineDigest"], stage2.baseline_digest(baseline))
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

    def test_legitimate_restart_captures_new_session_without_source_repin(self):
        old = self.api_snapshot(self.api_fields(80100, "Wed 2026-09-23 15:03:22 UTC"))
        new = self.api_snapshot(self.api_fields())
        self.assertEqual((old["MainPID"], new["MainPID"]), (80100, 88740))
        self.assertNotEqual(stage2.baseline_digest(old), stage2.baseline_digest(new))
        self.assertEqual(new["appSha256"], stage2.API_APP_SHA)
        self.assertEqual(new["NRestarts"], 0)
        self.assertEqual(stage2.baseline_digest(new),
                         "6892d54c5bbdd8dda7f3378b8c8c1e22d660cac04fc902833df171458ae34316")
        self.assertNotIn("API_PID", vars(stage2))
        self.assertNotIn("API_START", vars(stage2))

    def test_api_service_selection_and_wrong_dev_host_fail_closed(self):
        with patch.object(stage2, "show", return_value=self.api_fields()) as selected, \
             patch.object(stage2, "digest", side_effect=lambda path: stage2.API_APP_SHA
                          if path == stage2.API_APP else stage2.API_FILES[path]), \
             patch.object(stage2, "api_health", return_value={"status": "ok", "database": True}):
            stage2.capture_api_runtime_baseline(captured_at="2026-09-23T19:30:00Z")
            self.assertEqual(selected.call_args.args[0], "lilith-os-api-dev.service")
        wrong = {
            "project/project-id": stage2.PROJECT,
            "instance/zone": f"projects/763184673487/zones/{stage2.ZONE}",
            "instance/id": stage2.INSTANCE_ID,
            "instance/name": "wrong-dev",
        }
        with patch.object(stage2.os, "geteuid", return_value=0, create=True):
            with self.assertRaisesRegex(stage2.Stage2Error, "DEV_METADATA_MISMATCH"):
                stage2.assert_host(lookup=wrong.__getitem__,
                                   hostname=stage2.HOSTNAME,
                                   machine_id=stage2.MACHINE_ID)

    def test_api_durable_identity_and_custody_drift_fail_closed(self):
        for changed, code in (
            ({"ActiveState": "inactive"}, "API_SERVICE_DRIFT"),
            ({"User": "root"}, "API_SERVICE_DRIFT"),
            ({"Group": "root"}, "API_SERVICE_DRIFT"),
            ({"WorkingDirectory": "/wrong"}, "API_SERVICE_DRIFT"),
            ({"FragmentPath": "/wrong"}, "API_SERVICE_DRIFT"),
            ({"ExecStart": "{ path=/wrong ; argv[]=/wrong ;"}, "API_SERVICE_DRIFT"),
            ({"NRestarts": "1"}, "API_SERVICE_DRIFT"),
            ({"MainPID": "abc"}, "API_SERVICE_DRIFT"),
        ):
            with self.subTest(changed=changed):
                with self.assertRaisesRegex(stage2.Stage2Error, code):
                    self.api_snapshot({**self.api_fields(), **changed})
        with self.assertRaisesRegex(stage2.Stage2Error, "API_SERVICE_DATA_MALFORMED"):
            self.api_snapshot({key: value for key, value in self.api_fields().items()
                               if key != "User"})
        for path, code in ((stage2.API_APP, "API_APP_DRIFT"),
                           (stage2.API_UNIT, "API_CUSTODY_DRIFT"),
                           (next(path for path in stage2.API_FILES if path != stage2.API_UNIT),
                            "API_CUSTODY_DRIFT")):
            with self.subTest(path=path):
                with self.assertRaisesRegex(stage2.Stage2Error, code):
                    self.api_snapshot(hashes={path: "0" * 64})
        with patch.object(stage2, "api_health", side_effect=stage2.Stage2Error("API_UNHEALTHY")), \
             patch.object(stage2, "show", return_value=self.api_fields()), \
             patch.object(stage2, "digest", side_effect=lambda path: stage2.API_APP_SHA
                          if path == stage2.API_APP else stage2.API_FILES[path]):
            with self.assertRaisesRegex(stage2.Stage2Error, "API_UNHEALTHY"):
                stage2.capture_api_runtime_baseline()

    def test_authorized_baseline_detects_toctou_and_post_run_change(self):
        authorized = self.api_snapshot()
        with patch.object(stage2, "capture_api_runtime_baseline", return_value=authorized):
            self.assertEqual(stage2.require_api_baseline_unchanged(authorized), authorized)
        for changed in (
            {"MainPID": 88741}, {"ExecMainStartTimestamp": "later"},
            {"NRestarts": 1}, {"appSha256": "0" * 64},
            {"serviceUnitSha256": "0" * 64}, {"health": {"status": "fail"}},
            {"custodySha256": {}},
        ):
            with self.subTest(changed=changed):
                with patch.object(stage2, "capture_api_runtime_baseline",
                                  return_value={**authorized, **changed}):
                    with self.assertRaisesRegex(stage2.Stage2Error, "API_BASELINE_CHANGED"):
                        stage2.require_api_baseline_unchanged(authorized)
        self.assertLess(stage2.execute.__code__.co_firstlineno,
                        stage2.failure_stop.__code__.co_firstlineno)

    def test_execute_rechecks_before_marker_consumption_and_after_experiment(self):
        baseline = self.api_snapshot()
        marker = {"authorizationId": "a" * 32, "apiRuntimeBaseline": baseline,
                  "apiBaselineDigest": stage2.baseline_digest(baseline)}
        preflight = {"status": "STAGE_II_PREFLIGHT_OK",
                     "apiRuntimeBaseline": baseline,
                     "apiBaselineDigest": stage2.baseline_digest(baseline)}
        operations = []
        with patch.object(stage2, "verify_marker", return_value=marker), \
             patch.object(stage2, "preflight", return_value=preflight), \
             patch.object(stage2.os, "replace", side_effect=lambda *_: operations.append("consume")), \
             patch.object(stage2, "run_fixed", side_effect=lambda *_: operations.append("mutation")), \
             patch.object(stage2, "assert_broker_hardening", return_value={}), \
             patch.object(stage2, "inspect_run_directory", return_value={}), \
             patch.object(stage2, "inspect_socket", return_value={}), \
             patch.object(stage2, "assert_unit_state", return_value=({"MainPID": "111"}, {})), \
             patch.object(stage2, "relay", return_value={"status": "HEALTH_OK"}), \
             patch.object(stage2, "inspect_process", return_value={}), \
             patch.object(stage2, "trace_peer_uid", return_value={}), \
             patch.object(stage2, "negative_peer", return_value={}), \
             patch.object(stage2, "probe_equivalent_sandbox", return_value={}), \
             patch.object(stage2, "assert_relay_restrictions", return_value={}), \
             patch.object(stage2, "functional_tests", return_value={}), \
             patch.object(stage2.subprocess, "run") as stopped:
            with patch.object(stage2, "capture_api_runtime_baseline",
                              side_effect=lambda **_: operations.append("recheck") or baseline):
                self.assertEqual(stage2.execute()["apiUnchanged"], True)
            self.assertEqual(operations[:3], ["recheck", "consume", "mutation"])
            self.assertEqual(operations[-1], "recheck")
            stopped.assert_not_called()

            changed = {**baseline, "MainPID": baseline["MainPID"] + 1}
            operations.clear()
            with patch.object(stage2, "capture_api_runtime_baseline", return_value=changed):
                with self.assertRaisesRegex(stage2.Stage2Error, "API_BASELINE_CHANGED"):
                    stage2.execute()
            self.assertEqual(operations, [])  # No marker claim or activation mutation.

            operations.clear()
            with patch.object(stage2, "capture_api_runtime_baseline",
                              side_effect=[baseline, changed]):
                with self.assertRaisesRegex(stage2.Stage2Error, "API_BASELINE_CHANGED"):
                    stage2.execute()
            self.assertEqual(operations[:3], ["consume", "mutation", "mutation"])
            self.assertEqual(stopped.call_count, 2)  # Existing failure-stop policy.

    def test_marker_rejects_old_schema_and_baseline_tamper(self):
        baseline = self.api_snapshot()
        issued = datetime(2026, 9, 23, 19, 30, 1, tzinfo=timezone.utc)
        value = stage2.marker_value(issued, "a" * 32, baseline)
        marker = MagicMock()
        marker.lstat.return_value = os.stat_result((0o100600, 0, 0, 0, 0, 0, 0, 0, 0, 0))
        used = MagicMock()
        used.exists.return_value = False
        used.is_symlink.return_value = False
        with patch.object(stage2, "MARKER", marker), patch.object(stage2, "USED", used):
            marker.read_bytes.return_value = json.dumps(value).encode()
            self.assertEqual(stage2.verify_marker(now=issued), value)
            for bad in ({**value, "schemaVersion": 1},
                        {**value, "apiBaselineDigest": "0" * 64}):
                marker.read_bytes.return_value = json.dumps(bad).encode()
                with self.assertRaises(stage2.Stage2Error):
                    stage2.verify_marker(now=issued)

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
