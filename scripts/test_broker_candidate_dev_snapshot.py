"""Pure accepted-state comparison tests; no GCP or VM access."""

from __future__ import annotations

import copy
import base64
import hashlib
import json
import os
import secrets
import stat
import subprocess
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
        compile(guard._REMOTE_SOURCE, "<trusted-remote-staging>", "exec")
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
                       ("1", "1\n", "preflight"), ("1;touch", "1", "preflight"),
                       ("1 2", "1", "preflight"), ("1..2", "1", "preflight"),
                       ("1" * 100, "1", "preflight")):
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
                 patch.object(sys, "argv", ["remote", path, action, "5",
                                            hashlib.sha256(b"hello").hexdigest()]):
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
        """Old stdout-path rejection and both zero-byte SCP timeouts stay impossible."""
        path = guard.staging_path("35977618907", "1", "preflight")
        calls = []

        def gcloud(*args):
            if args[:2] == ("instances", "describe"):
                return json.dumps({"name": guard.INSTANCE, "id": guard.INSTANCE_ID,
                                   "status": "RUNNING"})
            self.fail("SCP must not be invoked after run 35980507708 attempts 1 and 2")

        data = json.dumps(fixture()).encode()
        frame = (guard.SNAPSHOT_FRAME + str(len(data)).encode() + b":" +
                 hashlib.sha256(data).hexdigest().encode() + b":" + base64.b64encode(data))
        def action(p, a, size, digest, **kwargs):
            calls.append((p, a))
            return b"transport notice\n" + frame + b"\n" if a == "read" else b"transport notice\n"

        with patch.object(guard, "gcloud", side_effect=gcloud), \
             patch.object(guard, "remote_action", side_effect=action):
            result = guard.capture("35977618907", "1", "preflight")
        self.assertEqual(result, fixture())
        self.assertEqual(calls, [(path, "create"), (path, "upload"), (path, "snapshot"),
                                 (path, "read"), (path, "cleanup")])

    def test_remote_transport_stdout_never_becomes_staging_path(self):
        path = guard.staging_path("35977618907", "1", "preflight")
        with patch.object(guard.subprocess, "run", return_value=SimpleNamespace(
                returncode=0, stdout=b"transport notice\n" + path.encode())) as transport:
            guard.remote_action(path, "create", 5, hashlib.sha256(b"hello").hexdigest())
        args = transport.call_args.args[0]
        self.assertEqual(args[:4], ("gcloud", "compute", "ssh", guard.INSTANCE))
        self.assertIn("--tunnel-through-iap", args)
        self.assertIn("--ssh-flag=-T", args)
        self.assertIn(path + " create 5 ", args[6])

    def test_stream_is_exact_and_transport_failures_are_bounded(self):
        path = guard.staging_path("35980507708", "3", "preflight")
        data = b"trusted protected-main bytes"
        digest = hashlib.sha256(data).hexdigest()
        with patch.object(guard.subprocess, "run", return_value=SimpleNamespace(
                returncode=0, stdout=b"diagnostic only")) as transport:
            guard.remote_action(path, "upload", len(data), digest, source_bytes=data)
        self.assertEqual(transport.call_args.kwargs["input"], data)
        self.assertEqual(transport.call_args.kwargs["timeout"], 120)
        args = transport.call_args.args[0]
        self.assertNotIn(data.decode(), " ".join(args))
        self.assertIn(path + " upload " + str(len(data)) + " " + digest, args[6])
        for bad in (b"", data[:-1], data + b"x", b"X" + data[1:]):
            with self.subTest(bad=bad), self.assertRaises(guard.SnapshotError):
                guard.remote_action(path, "upload", len(data), digest, source_bytes=bad)
        with patch.object(guard.subprocess, "run", side_effect=subprocess.TimeoutExpired("gcloud", 120)):
            with self.assertRaisesRegex(guard.SnapshotError, "TRUSTED_SSH_TIMEOUT action=upload"):
                guard.remote_action(path, "upload", len(data), digest, source_bytes=data)
        with patch.object(guard.subprocess, "run", return_value=SimpleNamespace(
                returncode=7, stdout=b"", stderr=b"REMOTE_SOURCE_HASH_MISMATCH")):
            with self.assertRaisesRegex(guard.SnapshotError,
                                        "TRUSTED_SSH_EXIT action=upload code=7 reason=REMOTE_SOURCE_HASH_MISMATCH"):
                guard.remote_action(path, "upload", len(data), digest, source_bytes=data)

    def test_framed_snapshot_rejects_chatter_as_payload_and_bad_identity(self):
        data = json.dumps(fixture()).encode()
        frame = (guard.SNAPSHOT_FRAME + str(len(data)).encode() + b":" +
                 hashlib.sha256(data).hexdigest().encode() + b":" + base64.b64encode(data))
        self.assertEqual(guard.decode_snapshot_frame(b"transport chatter\n" + frame + b"\n"), fixture())
        for raw in (b"transport chatter\n", frame + b"\n" + frame,
                    frame.replace(str(len(data)).encode() + b":", b"1:", 1),
                    frame[:-1] + b"!", b"LILITH_TRUSTED_SNAPSHOT_V1:0:" + b"0" * 64 + b":"):
            with self.subTest(raw=raw[:60]), self.assertRaises(guard.SnapshotError):
                guard.decode_snapshot_frame(raw)

    @unittest.skipUnless(os.name == "posix", "real remote file semantics require Linux")
    def test_linux_remote_stream_publication_and_failure_states(self):
        data = b"trusted non-candidate source\n"
        digest = hashlib.sha256(data).hexdigest()

        def exercise(payload, *, expected_digest=digest, prefix="", preexisting=None,
                     expect_success=False):
            run_id = str(secrets.randbelow(10**12 - 10**11) + 10**11)
            path = guard.staging_path(run_id, "1", "preflight")
            def remote(action, incoming=b"", code=guard._REMOTE_SOURCE):
                return subprocess.run([sys.executable, "-B", "-c", code, path, action,
                                       str(len(data)), expected_digest], input=incoming,
                                      stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=10)
            self.assertFalse(os.path.lexists(path))
            try:
                self.assertEqual(remote("create").returncode, 0)
                self.assertEqual(stat.S_IMODE(os.lstat(path).st_mode), 0o700)
                if preexisting:
                    Path(path, preexisting).write_bytes(b"existing")
                    os.chmod(Path(path, preexisting), 0o600)
                result = remote("upload", payload, prefix + guard._REMOTE_SOURCE)
                self.assertEqual(result.returncode == 0, expect_success, result.stderr)
                self.assertEqual(Path(path, "lifecycle.py").exists(), expect_success)
                if expect_success:
                    self.assertEqual(Path(path, "lifecycle.py").read_bytes(), data)
                    self.assertFalse(Path(path, "lifecycle.py.part").exists())
                    self.assertEqual(stat.S_IMODE(os.lstat(Path(path, "lifecycle.py")).st_mode), 0o600)
                    snapshot = Path(path, "snapshot.json")
                    snapshot.write_bytes(b'{"profile":"test"}')
                    os.chmod(snapshot, 0o600)
                    read = remote("read")
                    self.assertEqual(read.returncode, 0, read.stderr)
                    self.assertEqual(guard.decode_snapshot_frame(read.stdout), {"profile": "test"})
                self.assertEqual(remote("cleanup").returncode, 0)
                self.assertFalse(os.path.lexists(path))
            finally:
                if os.path.lexists(path):
                    # Only this test's unique, verified /tmp namespace is removable.
                    for name in ("lifecycle.py.part", "lifecycle.py", "snapshot.json"):
                        child = Path(path, name)
                        if child.is_file():
                            child.unlink()
                    os.rmdir(path)

        exercise(data, expect_success=True)
        exercise(data[:-1])  # short stream: .part only, never final
        exercise(data + b"x")  # extra byte
        exercise(b"X" + data[1:])  # wrong SHA
        exercise(data, preexisting="lifecycle.py.part")
        exercise(data, preexisting="lifecycle.py")
        exercise(data, prefix="import os\nos.rename=lambda *args: (_ for _ in ()).throw(OSError('rename'))\n")

    @unittest.skipUnless(os.name == "posix", "real remote custody checks require Linux")
    def test_linux_remote_cleanup_preserves_unexpected_contents_and_symlinks(self):
        data = b"trusted test bytes"
        digest = hashlib.sha256(data).hexdigest()
        run_id = str(secrets.randbelow(10**12 - 10**11) + 10**11)
        path = guard.staging_path(run_id, "2", "postflight")
        def remote(action):
            return subprocess.run([sys.executable, "-B", "-c", guard._REMOTE_SOURCE,
                                   path, action, str(len(data)), digest], input=b"",
                                  stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=10)
        self.assertFalse(os.path.lexists(path))
        try:
            self.assertEqual(remote("create").returncode, 0)
            unexpected = Path(path, "candidate.tar.gz")
            unexpected.write_bytes(b"evidence")
            self.assertNotEqual(remote("cleanup").returncode, 0)
            self.assertEqual(unexpected.read_bytes(), b"evidence")
            unexpected.unlink()
            link = Path(path, "lifecycle.py.part")
            os.symlink("/dev/null", link)
            self.assertNotEqual(remote("cleanup").returncode, 0)
            self.assertTrue(link.is_symlink())
            link.unlink()
            os.chmod(path, 0o755)
            self.assertNotEqual(remote("cleanup").returncode, 0)
            os.chmod(path, 0o700)
            self.assertEqual(remote("cleanup").returncode, 0)
            self.assertFalse(os.path.lexists(path))
        finally:
            if os.path.isdir(path) and not os.path.islink(path):
                for name in ("candidate.tar.gz", "lifecycle.py.part"):
                    child = Path(path, name)
                    if child.exists() or child.is_symlink():
                        child.unlink()
                os.chmod(path, 0o700)
                os.rmdir(path)

    def test_prod_identity_refused_before_staging_and_failure_cleanup_attempted(self):
        with patch.object(guard, "gcloud", return_value=json.dumps(
            {"name": "lilith-01", "id": "1332996232081478576", "status": "RUNNING"})), \
             patch.object(guard, "remote_action") as remote:
            with self.assertRaisesRegex(guard.SnapshotError, "DEV_INSTANCE_IDENTITY"):
                guard.capture("35977618907", "1", "preflight")
            remote.assert_not_called()
        calls = []
        def identity(*args):
            if args[:2] == ("instances", "describe"):
                return json.dumps({"name": guard.INSTANCE, "id": guard.INSTANCE_ID,
                                   "status": "RUNNING"})
            self.fail("SCP must not be invoked")
        def action(_path, name, _size, _digest, **kwargs):
            calls.append(name)
            if name == "upload":
                raise guard.SnapshotError("SSH_STREAM_TIMEOUT")
        with patch.object(guard, "gcloud", side_effect=identity), \
             patch.object(guard, "remote_action", side_effect=action):
            with self.assertRaisesRegex(guard.SnapshotError, "SSH_STREAM_TIMEOUT"):
                guard.capture("35977618907", "1", "preflight")
        self.assertEqual(calls, ["create", "upload", "cleanup"])

    def test_uncertain_create_and_cleanup_failure_report_exact_path(self):
        path = guard.staging_path("35977618907", "1", "postflight")
        identity = json.dumps({"name": guard.INSTANCE, "id": guard.INSTANCE_ID, "status": "RUNNING"})
        with patch.object(guard, "gcloud", return_value=identity), \
             patch.object(guard, "remote_action", side_effect=RuntimeError("transport failed")):
            with self.assertRaisesRegex(guard.SnapshotError, "REMOTE_STAGING_CREATE_UNCERTAIN path=" + path):
                guard.capture("35977618907", "1", "postflight")
        def action(_path, name, _size, _digest, **kwargs):
            if name == "cleanup":
                raise RuntimeError("unexpected contents")
            if name == "upload":
                raise RuntimeError("upload failed")
        with patch.object(guard, "gcloud", return_value=identity), \
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
