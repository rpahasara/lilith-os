"""Pure accepted-state comparison tests; no GCP or VM access."""

from __future__ import annotations

import copy
import json
import os
import stat
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from scripts import broker_candidate_dev_snapshot as guard
from scripts import verify_broker_dev_lifecycle as lifecycle
from scripts.test_broker_dev_lifecycle import accepted_fixture


def fixture() -> dict:
    value = accepted_fixture()
    value["api"]["MainPID"] = "88740"
    value["runtimeIncarnations"] = {
        "broker": {"pid": 96650, "bootId": "a" * 36, "startTicks": 91036598},
        "api": {"pid": 88740, "bootId": "a" * 36, "startTicks": 86941441},
    }
    return value


class BrokerCandidateSnapshotTests(unittest.TestCase):
    def test_run_bound_path_contract_rejects_untrusted_paths(self):
        valid = guard.staging_path("35977618907", "1", "preflight")
        self.assertEqual(valid, "/tmp/lilith-broker-candidate-preflight-35977618907-1")
        self.assertEqual(guard.validate_staging_path(valid), valid)
        self.assertEqual(guard.staging_path("35977618907", "2", "postflight"),
                         "/tmp/lilith-broker-candidate-postflight-35977618907-2")
        for path in ("/tmp", "tmp/lilith-broker-candidate-preflight-1-1",
                     "/tmp/other-preflight-1-1", "/tmp/lilith-broker-candidate-preflight-1-1-evil",
                     "/tmp/lilith-broker-candidate-preflight-1-1/../escape",
                     "/tmp/lilith-broker-candidate-preflight-1-1\n",
                     "/tmp/lilith-broker-candidate-preflight-1-1" + "x" * 101,
                     "/opt/lilith-memory-broker/current", "/run/lilith-memory/owner.sock"):
            with self.subTest(path=path), self.assertRaises(guard.SnapshotError):
                guard.validate_staging_path(path)
        for values in (("1/evil", "1", "preflight"), ("1", "1", "candidate"),
                       ("0", "1", "preflight"), ("1", "0", "preflight"),
                       ("1", "1\n", "preflight")):
            with self.subTest(values=values), self.assertRaises(guard.SnapshotError):
                guard.staging_path(*values)

    def test_remote_contract_rejects_symlink_wrong_owner_mode_and_contents(self):
        path = guard.staging_path("35977618907", "1", "preflight")
        uid, gid = 12345, 12345
        parent = SimpleNamespace(st_mode=stat.S_IFDIR | 0o1777, st_uid=0, st_gid=0)
        target = SimpleNamespace(st_mode=stat.S_IFDIR | 0o700, st_uid=uid, st_gid=gid)

        def run(action, target_info=target, names=(), parent_info=parent):
            def lstat(name):
                return parent_info if name == "/tmp" else target_info
            with patch.object(os, "lstat", side_effect=lstat), \
                 patch.object(os, "geteuid", return_value=uid, create=True), \
                 patch.object(os, "getegid", return_value=gid, create=True), \
                 patch.object(os, "mkdir") as mkdir, \
                 patch.object(os, "listdir", return_value=list(names)), \
                 patch.object(os, "unlink") as unlink, \
                 patch.object(os, "rmdir") as rmdir, \
                 patch.object(sys, "argv", ["remote", path, action]):
                try:
                    exec(compile(guard._REMOTE_SOURCE, "<trusted-remote-staging>", "exec"), {})
                finally:
                    if action == "cleanup" and names:
                        unlink.assert_not_called()
                        rmdir.assert_not_called()
                return mkdir

        mkdir = run("create")
        mkdir.assert_called_once_with(path, 0o700)
        for info in (SimpleNamespace(st_mode=stat.S_IFLNK | 0o777, st_uid=uid, st_gid=gid),
                     SimpleNamespace(st_mode=stat.S_IFDIR | 0o700, st_uid=uid + 1, st_gid=gid),
                     SimpleNamespace(st_mode=stat.S_IFDIR | 0o755, st_uid=uid, st_gid=gid)):
            with self.subTest(info=info), self.assertRaises(SystemExit):
                run("cleanup", target_info=info)
        with self.assertRaises(SystemExit):
            run("create", names=("unexpected",))
        with self.assertRaises(SystemExit):
            run("cleanup", names=("unexpected",))
        with self.assertRaises(SystemExit):
            run("create", parent_info=SimpleNamespace(
                st_mode=stat.S_IFLNK | 0o777, st_uid=0, st_gid=0))

    def test_pr38_empty_directory_stdout_regression_is_cleaned(self):
        """Run 35977618907 created empty staging before old stdout-path rejection."""
        path = guard.staging_path("35977618907", "1", "preflight")
        calls = []

        def gcloud(*args):
            if args[:2] == ("instances", "describe"):
                return json.dumps({"name": guard.INSTANCE, "id": guard.INSTANCE_ID,
                                   "status": "RUNNING"})
            if args[0] == "scp" and args[-2] == f"{guard.INSTANCE}:{path}/snapshot.json":
                Path(args[-1]).write_text(json.dumps(fixture()), encoding="utf-8")
            # Reproduces the observed failure class: transport stdout is not
            # solely the path. The exact PR #38 stdout bytes were not retained.
            return "transport notice\n" + path

        with patch.object(guard, "gcloud", side_effect=gcloud), \
             patch.object(guard, "remote_action", side_effect=lambda p, a: calls.append((p, a))):
            result = guard.capture("35977618907", "1", "preflight")
        self.assertEqual(result, fixture())
        self.assertEqual(calls, [(path, "create"), (path, "snapshot"), (path, "cleanup")])

    def test_remote_transport_stdout_never_becomes_staging_path(self):
        path = guard.staging_path("35977618907", "1", "preflight")
        with patch.object(guard, "gcloud", return_value="transport notice\n" + path) as transport:
            guard.remote_action(path, "create")
        args = transport.call_args.args
        self.assertEqual(args[:3], ("ssh", guard.INSTANCE, "--tunnel-through-iap"))
        self.assertIn("--command=/usr/bin/python3 -B -c", args[3])
        self.assertIn(path + " create", args[3])

    def test_prod_identity_refused_before_staging_and_failure_cleanup_attempted(self):
        with patch.object(guard, "gcloud", return_value=json.dumps(
            {"name": "lilith-01", "id": "1332996232081478576", "status": "RUNNING"})), \
             patch.object(guard, "remote_action") as remote:
            with self.assertRaisesRegex(guard.SnapshotError, "DEV_INSTANCE_IDENTITY"):
                guard.capture("35977618907", "1", "preflight")
            remote.assert_not_called()
        calls = []
        def fail_after_creation(*args):
            if args[:2] == ("instances", "describe"):
                return json.dumps({"name": guard.INSTANCE, "id": guard.INSTANCE_ID,
                                   "status": "RUNNING"})
            raise guard.SnapshotError("SCP_FAILED")
        with patch.object(guard, "gcloud", side_effect=fail_after_creation), \
             patch.object(guard, "remote_action", side_effect=lambda p, a: calls.append(a)):
            with self.assertRaisesRegex(guard.SnapshotError, "SCP_FAILED"):
                guard.capture("35977618907", "1", "preflight")
        self.assertEqual(calls, ["create", "cleanup"])

    def test_uncertain_create_and_cleanup_failure_report_exact_path(self):
        path = guard.staging_path("35977618907", "1", "postflight")
        identity = json.dumps({"name": guard.INSTANCE, "id": guard.INSTANCE_ID, "status": "RUNNING"})
        with patch.object(guard, "gcloud", return_value=identity), \
             patch.object(guard, "remote_action", side_effect=RuntimeError("transport failed")):
            with self.assertRaisesRegex(guard.SnapshotError, "REMOTE_STAGING_CREATE_UNCERTAIN path=" + path):
                guard.capture("35977618907", "1", "postflight")
        def action(_path, name):
            if name == "cleanup":
                raise RuntimeError("unexpected contents")
        with patch.object(guard, "gcloud", side_effect=lambda *args: identity if args[0] == "instances" else ""), \
             patch.object(guard, "remote_action", side_effect=action):
            with self.assertRaisesRegex(guard.SnapshotError, "REMOTE_STAGING_CLEANUP_FAILED path=" + path):
                guard.capture("35977618907", "1", "postflight")

    def test_exact_accepted_snapshot_has_stable_digest(self):
        observed = guard.summarize(fixture())
        self.assertEqual(observed["acceptedBaselineDigest"], guard.ACCEPTED_DIGEST)
        self.assertEqual(observed["installedReleaseSha"], lifecycle.RELEASE_SHA)
        self.assertEqual(observed["brokerPid"], "96650")
        self.assertEqual(observed["apiPid"], "88740")
        self.assertEqual(observed["ownerDbSha256"], lifecycle.ACCEPTED_OWNER_DB_SHA)
        self.assertEqual(observed["evidenceDbSha256"], lifecycle.ACCEPTED_EVIDENCE_DB_SHA)
        self.assertEqual(observed, guard.summarize(fixture()))

    def test_api_broker_and_history_drift_change_complete_snapshot(self):
        original = guard.summarize(fixture())["snapshotSha256"]
        mutations = (
            lambda s: s["runtimeIncarnations"]["api"].__setitem__("startTicks", 2),
            lambda s: s["runtimeIncarnations"]["broker"].__setitem__("startTicks", 2),
            lambda s: s["api"].__setitem__("MainPID", "88741"),
            lambda s: s["units"][lifecycle.SERVICE].__setitem__("MainPID", "96651"),
            lambda s: s["databases"]["owner"]["rowHashes"]["owner_request_v1"].__setitem__(
                lifecycle.ACCEPTED_RETRY_CHALLENGE, "0" * 64),
            lambda s: s["usedAuthorizations"]["retry2"].__setitem__("sha256", "0" * 64),
            lambda s: s["api"]["custody"][str(lifecycle.API_ROOT / "data/lilith-dev.db")].__setitem__(
                "sha256", "0" * 64),
        )
        for mutation in mutations:
            with self.subTest(mutation=mutation):
                value = fixture()
                mutation(value)
                try:
                    changed = guard.summarize(value)["snapshotSha256"]
                except guard.SnapshotError:
                    continue
                self.assertNotEqual(changed, original)

    def test_wrong_profile_release_digest_or_unhealthy_api_rejected(self):
        mutations = (
            lambda s: s.__setitem__("profile", lifecycle.POST_STAGE_I),
            lambda s: s["stage2AcceptedBaseline"].__setitem__(
                "stage2AcceptedBaselineDigest", "0" * 64),
            lambda s: s["release"].__setitem__("candidateSha", "0" * 40),
            lambda s: s["ownerSocket"].__setitem__("listening", False),
            lambda s: s["api"]["health"].__setitem__("status", "down"),
            lambda s: s.__setitem__("runtimeIncarnations", {}),
        )
        for mutation in mutations:
            with self.subTest(mutation=mutation):
                value = copy.deepcopy(fixture())
                mutation(value)
                with self.assertRaises(guard.SnapshotError):
                    guard.summarize(value)


if __name__ == "__main__":
    unittest.main()
