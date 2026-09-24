"""Control-only Stage-II tests; never activate a broker or VM service."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import copy
import json
import os
from pathlib import Path
import subprocess
import time
import unittest
from unittest.mock import MagicMock, patch
import uuid

from scripts import memory_broker_stage2_control as stage2
from scripts import verify_broker_dev_lifecycle as lifecycle


ROOT = Path(__file__).resolve().parents[1]


class Stage2ControlContracts(unittest.TestCase):
    @staticmethod
    def retry_snapshot():
        return {"schemaVersion": 1, "historicalBaselineDigest": stage2.HISTORICAL_DIGEST,
                "historicalAuthorizationId": stage2.HISTORICAL_AUTHORIZATION}

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
        incarnation = {"bootId": "24d1771d-e1b5-4e5f-816d-da08ad8b367a",
                       "startTicks": 86941441 if fields["MainPID"] == "88740" else 80000000,
                       "executable": "/usr/bin/python3.12",
                       "cmdline": [stage2.API_EXECUTABLE.replace("/uvicorn", "/python"),
                                   stage2.API_EXECUTABLE, "app:app", "--host", "0.0.0.0",
                                   "--port", "8765"]}
        with patch.object(stage2, "show", return_value=fields), \
             patch.object(stage2, "digest", side_effect=file_digest), \
             patch.object(stage2, "api_health", return_value=health), \
             patch.object(stage2, "process_incarnation", return_value=incarnation), \
             patch.object(stage2.socket, "getfqdn", return_value=stage2.HOSTNAME), \
             patch.object(stage2.Path, "read_text", return_value=stage2.MACHINE_ID):
            return stage2.capture_api_runtime_baseline(captured_at="2026-09-23T19:30:00Z")

    def test_marker_is_closed_fresh_and_not_stage_iii(self):
        issued = datetime(2026, 9, 23, 16, 0, tzinfo=timezone.utc)
        baseline = self.api_snapshot()
        retry = self.retry_snapshot()
        value = stage2.marker_value(issued, "a" * 32, baseline, retry)
        self.assertEqual(value["schemaVersion"], 3)
        self.assertEqual(value["apiRuntimeBaseline"], baseline)
        self.assertEqual(value["retryBaselineDigest"], stage2.baseline_digest(retry))
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
        self.assertEqual(new["schemaVersion"], 2)
        self.assertEqual(new["processIncarnation"]["startTicks"], 86941441)
        self.assertNotIn("API_PID", vars(stage2))
        self.assertNotIn("API_START", vars(stage2))

    def test_api_service_selection_and_wrong_dev_host_fail_closed(self):
        with patch.object(stage2, "show", return_value=self.api_fields()) as selected, \
             patch.object(stage2, "digest", side_effect=lambda path: stage2.API_APP_SHA
                          if path == stage2.API_APP else stage2.API_FILES[path]), \
             patch.object(stage2, "api_health", return_value={"status": "ok", "database": True}), \
             patch.object(stage2, "process_incarnation", return_value={}), \
             patch.object(stage2.socket, "getfqdn", return_value=stage2.HOSTNAME), \
             patch.object(stage2.Path, "read_text", return_value=stage2.MACHINE_ID):
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
            ({"ExecStart": "{ path=/wrong ; argv[]=/wrong ;"}, "API_EXECSTART_MALFORMED"),
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
                          if path == stage2.API_APP else stage2.API_FILES[path]), \
             patch.object(stage2, "process_incarnation", return_value={}), \
             patch.object(stage2.socket, "getfqdn", return_value=stage2.HOSTNAME), \
             patch.object(stage2.Path, "read_text", return_value=stage2.MACHINE_ID):
            with self.assertRaisesRegex(stage2.Stage2Error, "API_UNHEALTHY"):
                stage2.capture_api_runtime_baseline()

    def test_authorized_baseline_detects_toctou_and_post_run_change(self):
        authorized = self.api_snapshot()
        with patch.object(stage2, "assert_host"), \
             patch.object(stage2, "capture_api_runtime_baseline", return_value=authorized):
            self.assertEqual(stage2.require_api_baseline_unchanged(authorized), authorized)
        for changed in (
            {"MainPID": 88741}, {"ExecMainStartTimestamp": "later"},
            {"processIncarnation": {**authorized["processIncarnation"], "startTicks": 1}},
            {"NRestarts": 1}, {"appSha256": "0" * 64},
            {"serviceUnitSha256": "0" * 64}, {"health": {"status": "fail"}},
            {"custodySha256": {}}, {"configuredExecStart": {}}, {"host": {}},
        ):
            with self.subTest(changed=changed):
                with patch.object(stage2, "assert_host"), \
                     patch.object(stage2, "capture_api_runtime_baseline",
                                  return_value={**authorized, **changed}):
                    with self.assertRaisesRegex(stage2.Stage2Error, "API_BASELINE_CHANGED"):
                        stage2.require_api_baseline_unchanged(authorized)
        self.assertLess(stage2.execute.__code__.co_firstlineno,
                        stage2.failure_stop.__code__.co_firstlineno)

    def test_api_v2_ignores_only_execstart_bookkeeping(self):
        before = self.api_snapshot()
        fields = self.api_fields()
        fields["ExecStart"] = fields["ExecStart"].replace(
            "start_time=[Wed 2026-09-23 19:28:51 UTC]", "start_time=[n/a]").replace(
            "pid=88740", "pid=0")
        after = self.api_snapshot(fields)
        self.assertEqual(before, after)
        self.assertEqual(before["MainPID"], 88740)
        self.assertEqual(before["processIncarnation"]["startTicks"], 86941441)
        self.assertEqual(before["NRestarts"], 0)
        self.assertNotIn("execStart", before)
        for changed in ("/wrong app:app --host 0.0.0.0 --port 8765",
                        stage2.API_EXECUTABLE + " other:app --host 0.0.0.0 --port 8765"):
            with self.subTest(changed=changed):
                altered = {**fields, "ExecStart": fields["ExecStart"].replace(
                    stage2.API_COMMAND, changed)}
                with self.assertRaisesRegex(stage2.Stage2Error,
                                            "API_CONFIGURED_EXECSTART_DRIFT"):
                    self.api_snapshot(altered)
        with patch.object(stage2, "assert_host"), \
             patch.object(stage2, "capture_api_runtime_baseline",
                          return_value={**before, "processIncarnation":
                                        {**before["processIncarnation"], "startTicks": 86941442}}):
            with self.assertRaisesRegex(stage2.Stage2Error, "API_BASELINE_CHANGED"):
                stage2.require_api_baseline_unchanged(before)

    def test_actual_process_incarnation_reads_kernel_start_and_rejects_cmdline_drift(self):
        stat_line = "88740 (uvicorn) " + " ".join(["S"] + ["0"] * 18 + ["86941441"])
        command = [stage2.API_EXECUTABLE.replace("/uvicorn", "/python"),
                   stage2.API_EXECUTABLE, "app:app", "--host", "0.0.0.0",
                   "--port", "8765"]
        def read_text(path, *_):
            return stat_line if path.name == "stat" else \
                "24d1771d-e1b5-4e5f-816d-da08ad8b367a"
        with patch.object(stage2.Path, "read_text", read_text), \
             patch.object(stage2.Path, "read_bytes",
                          return_value="\0".join(command).encode() + b"\0"), \
             patch.object(stage2.os, "readlink", return_value="/usr/bin/python3.12"):
            self.assertEqual(stage2.process_incarnation(88740)["startTicks"], 86941441)
        with patch.object(stage2.Path, "read_text", read_text), \
             patch.object(stage2.Path, "read_bytes", return_value=b"/wrong\0"), \
             patch.object(stage2.os, "readlink", return_value="/usr/bin/python3.12"):
            with self.assertRaisesRegex(stage2.Stage2Error, "API_PROCESS_COMMAND_DRIFT"):
                stage2.process_incarnation(88740)

    def test_retry_deltas_preserve_history_and_reject_unexplained_rows(self):
        new_ids = ["och.new" + str(i) for i in range(12)]
        states = {key: "CONSUMED" if i == 0 else "EXPIRED" if i == 2 else "CANCELLED"
                  for i, key in enumerate(new_ids)}
        old_claim = ["och.old", "a" * 64, "b" * 64, "ocred.synthetic",
                     "SYNTHETIC_EVIDENCE_COMMITTED", stage2.HISTORICAL_EVIDENCE]
        new_claim = [new_ids[0], "c" * 64, "d" * 64, "ocred.synthetic",
                     "SYNTHETIC_EVIDENCE_COMMITTED", "se.new"]
        old_evidence = ["och.old", stage2.HISTORICAL_EVIDENCE, "a" * 64,
                        "b" * 64, "owner.ravindu.v1", "ocred.synthetic",
                        "fixture.b1b1.synthetic-codename.v1", "SYNTHETIC_COMMITTED"]
        new_evidence = [new_ids[0], "se.new", "c" * 64, "d" * 64,
                        "owner.ravindu.v1", "ocred.synthetic",
                        "fixture.b1b1.synthetic-codename.v1", "SYNTHETIC_COMMITTED"]
        old_rows = {table: {"och.old": "a" * 64} for _, table in stage2.HISTORY_TABLES}
        baseline = {"schemaVersion": 1,
                    "historicalBaselineDigest": stage2.HISTORICAL_DIGEST,
                    "rowHashes": old_rows,
                    "requestDigests": {"och.old": "a" * 64},
                    "staticRowHashes": {"broker_schema_v1": ["x"]},
                    "schemaSqlSha256": {"owner": "x", "evidence": "y"},
                    "counts": {"owner": stage2.HISTORICAL_OWNER_COUNTS,
                               "evidence": stage2.HISTORICAL_EVIDENCE_COUNTS}}
        current = {"rowHashes": {table: {"och.old": "a" * 64,
                                      **({key: "b" * 64 for key in new_ids}
                                         if table in ("owner_proof_challenge_v1",
                                                      "owner_request_v1") else
                                         {new_ids[0]: "b" * 64})}
                                 for table in old_rows},
                   "challengeStates": {"och.old": "CONSUMED", **states},
                   "requestDigests": {"och.old": "a" * 64,
                                      **{key: "c" * 64 for key in new_ids}},
                   "claims": [old_claim, new_claim],
                   "evidenceRows": [old_evidence, new_evidence],
                   "staticRowHashes": baseline["staticRowHashes"],
                   "schemaSqlSha256": baseline["schemaSqlSha256"],
                   "counts": {"owner": {**stage2.HISTORICAL_OWNER_COUNTS,
                                        "owner_proof_challenge_v1": 24,
                                        "owner_request_v1": 24,
                                        "synthetic_claim_v1": 2},
                              "evidence": {**stage2.HISTORICAL_EVIDENCE_COUNTS,
                                           "synthetic_evidence_v1": 2}}}
        with patch.object(stage2, "digest", return_value=stage2.HISTORICAL_USED_SHA), \
             patch.object(stage2, "snapshot_retry_rows", return_value=(current, {})):
            result = stage2.verify_retry_deltas(baseline, states, new_ids[0])
            self.assertEqual(result["historicalAttempt1"]["syntheticEvidenceId"],
                             stage2.HISTORICAL_EVIDENCE)
            self.assertEqual(result["currentRetry"]["evidenceAdded"], 1)
            mutated = copy.deepcopy(current)
            mutated["rowHashes"]["owner_request_v1"]["och.old"] = "0" * 64
            with patch.object(stage2, "snapshot_retry_rows", return_value=(mutated, {})):
                with self.assertRaisesRegex(stage2.Stage2Error, "HISTORICAL_ROW_MUTATION"):
                    stage2.verify_retry_deltas(baseline, states, new_ids[0])
            unexplained = copy.deepcopy(current)
            unexplained["challengeStates"]["och.unexplained"] = "CANCELLED"
            with patch.object(stage2, "snapshot_retry_rows", return_value=(unexplained, {})):
                with self.assertRaisesRegex(stage2.Stage2Error,
                                            "RETRY_CHALLENGE_REQUEST_DELTA"):
                    stage2.verify_retry_deltas(baseline, states, new_ids[0])
            relinked = copy.deepcopy(current)
            relinked["evidenceRows"][1][1] = stage2.HISTORICAL_EVIDENCE
            with patch.object(stage2, "snapshot_retry_rows", return_value=(relinked, {})):
                with self.assertRaisesRegex(stage2.Stage2Error, "RETRY_EVIDENCE_DELTA"):
                    stage2.verify_retry_deltas(baseline, states, new_ids[0])

    def test_exact_failed_inert_history_is_retry_baseline_input(self):
        snapshot = {"counts": {"owner": lifecycle.FAILED_OWNER_COUNTS,
                               "evidence": lifecycle.FAILED_EVIDENCE_COUNTS},
                    "challengeStates": lifecycle.FAILED_CHALLENGES,
                    "requestDigests": lifecycle.FAILED_REQUESTS,
                    "claims": [[lifecycle.FAILED_CONSUMED_CHALLENGE,
                                lifecycle.FAILED_REQUEST_DIGEST,
                                lifecycle.FAILED_ACTION_DIGEST, "ocred.synthetic",
                                "SYNTHETIC_EVIDENCE_COMMITTED",
                                stage2.HISTORICAL_EVIDENCE]],
                    "evidenceRows": [[lifecycle.FAILED_CONSUMED_CHALLENGE,
                                      stage2.HISTORICAL_EVIDENCE,
                                      lifecycle.FAILED_REQUEST_DIGEST,
                                      lifecycle.FAILED_ACTION_DIGEST,
                                      "owner.ravindu.v1", "ocred.synthetic",
                                      "fixture.b1b1.synthetic-codename.v1",
                                      "SYNTHETIC_COMMITTED"]],
                    "rowHashes": {}, "staticRowHashes": {}, "schemaSqlSha256": {}}
        used = MagicMock()
        used.lstat.return_value = os.stat_result((0o100600, 0, 0, 0, 0, 0, 0, 0, 0, 0))
        used.read_bytes.return_value = json.dumps({
            "authorizationId": stage2.HISTORICAL_AUTHORIZATION,
            "schemaVersion": 2, "stage": stage2.STAGE,
            "authorityMode": "SYNTHETIC_ONLY", "canonicalCapability": "DISABLED",
            "releaseSha": stage2.RELEASE, "ownerActor": stage2.OWNER}).encode()
        run = MagicMock()
        run.lstat.return_value = os.stat_result((0o040710, 0, 0, 0, 0, 988, 0, 0, 0, 0))
        run.iterdir.return_value = iter(())
        def file_digest(path):
            return {stage2.OWNER_DB: stage2.HISTORICAL_OWNER_DB_SHA,
                    stage2.EVIDENCE_DB: stage2.HISTORICAL_EVIDENCE_DB_SHA,
                    used: stage2.HISTORICAL_USED_SHA}[path]
        def unit_fields(unit, *_):
            return ({"ActiveState": "inactive", "SubState": "dead",
                     "MainPID": "0", "UnitFileState": "static"} if unit == stage2.SERVICE else
                    {"ActiveState": "inactive", "SubState": "dead",
                     "UnitFileState": "disabled"})
        with patch.object(stage2, "HISTORICAL_USED", used), \
             patch.object(stage2, "RUN", run), \
             patch.object(stage2, "digest", side_effect=file_digest), \
             patch.object(stage2, "verify_historical_sidecars"), \
             patch.object(stage2, "snapshot_retry_rows", return_value=(snapshot, {})), \
             patch.object(stage2, "show", side_effect=unit_fields):
            baseline = stage2.capture_retry_baseline()
            self.assertEqual(baseline["historicalBaselineDigest"],
                             stage2.HISTORICAL_DIGEST)
            self.assertEqual(baseline["historicalAuthorizationId"],
                             stage2.HISTORICAL_AUTHORIZATION)
            tampered = copy.deepcopy(snapshot)
            tampered["requestDigests"][lifecycle.FAILED_CONSUMED_CHALLENGE] = "0" * 64
            with patch.object(stage2, "snapshot_retry_rows", return_value=(tampered, {})):
                with self.assertRaisesRegex(stage2.Stage2Error, "HISTORICAL_DIGEST_DRIFT"):
                    stage2.capture_retry_baseline()

    def test_old_authorization_cannot_be_reissued(self):
        marker = MagicMock()
        marker.exists.return_value = marker.is_symlink.return_value = False
        used = MagicMock()
        used.exists.return_value = used.is_symlink.return_value = False
        with patch.object(stage2, "preflight", return_value={
                "apiRuntimeBaseline": self.api_snapshot(),
                "retryBaseline": self.retry_snapshot()}), \
             patch.object(stage2, "MARKER", marker), \
             patch.object(stage2, "USED", used), \
             patch.object(stage2.uuid, "uuid4", return_value=MagicMock(hex=stage2.HISTORICAL_AUTHORIZATION)), \
             patch.object(stage2.os, "open") as opening:
            with self.assertRaisesRegex(stage2.Stage2Error, "OLD_AUTHORIZATION_REUSE"):
                stage2.authorize()
            opening.assert_not_called()

    def test_execute_rechecks_before_marker_consumption_and_after_experiment(self):
        baseline = self.api_snapshot()
        retry = self.retry_snapshot()
        marker = {"authorizationId": "a" * 32, "apiRuntimeBaseline": baseline,
                  "apiBaselineDigest": stage2.baseline_digest(baseline),
                  "retryBaseline": retry,
                  "retryBaselineDigest": stage2.baseline_digest(retry)}
        preflight = {"status": "STAGE_II_PREFLIGHT_OK",
                     "apiRuntimeBaseline": baseline,
                     "apiBaselineDigest": stage2.baseline_digest(baseline),
                     "retryBaseline": retry,
                     "retryBaselineDigest": stage2.baseline_digest(retry)}
        operations = []
        with patch.object(stage2, "verify_marker", return_value=marker), \
             patch.object(stage2, "preflight", return_value=preflight), \
             patch.object(stage2, "assert_host"), \
             patch.object(stage2, "capture_retry_baseline", return_value=retry), \
             patch.object(stage2.os, "replace", side_effect=lambda *_: operations.append("consume")), \
             patch.object(stage2, "run_fixed", side_effect=lambda *_: operations.append("mutation")), \
             patch.object(stage2, "assert_broker_hardening", return_value={}), \
             patch.object(stage2, "inspect_run_directory", return_value={}), \
             patch.object(stage2, "inspect_socket", return_value={}), \
             patch.object(stage2, "assert_unit_state", return_value=({"MainPID": "111"}, {})), \
             patch.object(stage2, "relay", side_effect=lambda *_: operations.append("health") or
                          {"status": "HEALTH_OK"}), \
             patch.object(stage2, "inspect_process", return_value={}), \
             patch.object(stage2, "trace_peer_uid",
                          side_effect=lambda *_: operations.append("SO_PEERCRED") or {}), \
             patch.object(stage2, "negative_peer", side_effect=lambda user:
                          operations.append("negative:" + user) or
                          {"layer": "filesystem_or_socket"}), \
             patch.object(stage2, "probe_equivalent_sandbox", return_value={}), \
             patch.object(stage2, "assert_relay_restrictions", return_value={}), \
             patch.object(stage2, "functional_tests", return_value={}), \
             patch.object(stage2.subprocess, "run") as stopped:
            with patch.object(stage2, "capture_api_runtime_baseline",
                              side_effect=lambda **_: operations.append("recheck") or baseline):
                self.assertEqual(stage2.execute()["apiUnchanged"], True)
            self.assertEqual(operations[:3], ["recheck", "consume", "mutation"])
            self.assertLess(operations.index("negative:lilith"), operations.index("health"))
            self.assertLess(operations.index("negative:nobody"), operations.index("health"))
            self.assertLess(operations.index("health"), operations.index("SO_PEERCRED"))
            self.assertLess(operations.index("SO_PEERCRED"),
                            operations.index("negative:lilith-memory-broker"))
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
        retry = self.retry_snapshot()
        issued = datetime(2026, 9, 23, 19, 30, 1, tzinfo=timezone.utc)
        value = stage2.marker_value(issued, "a" * 32, baseline, retry)
        marker = MagicMock()
        marker.lstat.return_value = os.stat_result((0o100600, 0, 0, 0, 0, 0, 0, 0, 0, 0))
        used = MagicMock()
        used.exists.return_value = False
        used.is_symlink.return_value = False
        with patch.object(stage2, "MARKER", marker), patch.object(stage2, "USED", used):
            marker.read_bytes.return_value = json.dumps(value).encode()
            self.assertEqual(stage2.verify_marker(now=issued), value)
            for bad in ({**value, "schemaVersion": 2},
                        {**value, "apiBaselineDigest": "0" * 64},
                        {**value, "retryBaselineDigest": "0" * 64},
                        {**value, "authorizationId": stage2.HISTORICAL_AUTHORIZATION},
                        {**value, "apiRuntimeBaseline": {**baseline, "schemaVersion": 1}}):
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

    def test_workflow_registration_push_cannot_reach_stage_ii(self):
        workflow = (ROOT / ".github/workflows/memory-broker-dev-stage2-runtime.yml"
                    ).read_text(encoding="utf-8")
        triggers = workflow.split("\npermissions:\n", 1)[0]
        registration = workflow.split("\n  registration_audit:\n", 1)[1].split(
            "\n  activate_and_isolation_test:\n", 1)[0]
        privileged = workflow.split("\n  activate_and_isolation_test:\n", 1)[1]
        self.assertIn("\n  workflow_dispatch:\n", triggers)
        self.assertEqual(triggers.count("\n  push:\n"), 1)
        self.assertIn("\n  push:\n    branches:\n      - main\n    paths:\n"
                      "      - \".github/workflows/memory-broker-dev-stage2-runtime.yml\"\n",
                      triggers)
        self.assertNotIn("\n  pull_request:", triggers)
        self.assertIn("permissions:\n  contents: read\n", workflow)
        self.assertNotIn("permissions:\n  contents: read\n  id-token: write\n", workflow)
        self.assertIn("if: github.event_name == 'push' && github.ref == 'refs/heads/main'",
                      registration)
        self.assertIn("permissions:\n      contents: read\n", registration)
        self.assertIn("uses: actions/checkout@v4", registration)
        self.assertIn("$GITHUB_SHA", registration)
        self.assertIn("sha256sum \"$workflow\"", registration)
        for forbidden in ("id-token: write", "gcloud", "sudo", "ssh", "auth@",
                          "memory_broker_stage2_control.py", "GCP_DEPLOY_SA"):
            self.assertNotIn(forbidden, registration)
        self.assertIn("if: >-\n      github.event_name == 'workflow_dispatch' &&\n",
                      privileged)
        self.assertIn("github.actor == 'rpahasara'", privileged)
        self.assertIn("github.ref == 'refs/heads/main'", privileged)
        self.assertIn("permissions:\n      contents: read\n      id-token: write\n",
                      privileged)
        self.assertIn("GCP_DEPLOY_SA:", privileged)
        self.assertIn("I AUTHORIZE B1B2B_II ACTIVATE_AND_ISOLATION_TEST", workflow)
        self.assertIn("instances describe", privileged)
        self.assertIn("< scripts/memory_broker_stage2_control.py", privileged)
        self.assertIn("failure-stop", privileged)
        self.assertIn("audit_core_api_production_read_only.py", privileged)
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
