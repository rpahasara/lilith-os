"""Pure accepted-state comparison tests; no GCP or VM access."""

from __future__ import annotations

import copy
import base64
import contextlib
import hashlib
import io
import json
import os
import secrets
import stat
import subprocess
import sys
import tempfile
import traceback
import unittest
import zlib
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


def publish_frame(data: bytes) -> bytes:
    return guard.PUBLISH_FRAME + json.dumps({
        "schemaVersion": 1, "action": "TRUSTED_PAYLOAD_PUBLISH",
        "rawSize": len(data), "sha256": hashlib.sha256(data).hexdigest(),
        "result": "OK",
    }, sort_keys=True, separators=(",", ":")).encode()


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
                    if action.startswith("cleanup") and names:
                        unlink.assert_not_called()
                        rmdir.assert_not_called()
                return mkdir

        mkdir = run("create")
        mkdir.assert_called_once_with(path, 0o700)
        for info in (SimpleNamespace(st_mode=stat.S_IFLNK | 0o777, st_uid=uid, st_gid=gid),
                     SimpleNamespace(st_mode=stat.S_IFDIR | 0o700, st_uid=uid + 1, st_gid=gid),
                     SimpleNamespace(st_mode=stat.S_IFDIR | 0o755, st_uid=uid, st_gid=gid)):
            with self.subTest(info=info), self.assertRaises(SystemExit):
                run("cleanup_full", target_info=info)
        with self.assertRaises(SystemExit):
            run("create", names=("unexpected",))
        with self.assertRaises(SystemExit):
            run("cleanup_full", names=("unexpected",))
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
        self.assertEqual(calls, [(path, "create"), (path, "publish"), (path, "snapshot"),
                                 (path, "read"), (path, "cleanup_full")])

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

    def test_packed_command_is_exact_and_transport_failures_are_bounded(self):
        path = guard.staging_path("35980507708", "3", "preflight")
        data = b"trusted protected-main bytes"
        digest = hashlib.sha256(data).hexdigest()
        with patch.object(guard.subprocess, "run", return_value=SimpleNamespace(
                returncode=0, stdout=b"diagnostic only\n" + publish_frame(data))) as transport:
            guard.remote_action(path, "publish", len(data), digest, source_bytes=data)
        self.assertEqual(transport.call_args.kwargs["stdin"], subprocess.DEVNULL)
        self.assertEqual(transport.call_args.kwargs["timeout"], 120)
        args = transport.call_args.args[0]
        self.assertNotIn(data.decode(), " ".join(args))
        self.assertIn(path + " publish " + str(len(data)) + " " + digest, args[6])
        packed, compressed_size = guard.pack_source(data)
        self.assertIn(" " + str(compressed_size) + " " + packed, args[6])
        for bad in (b"", data[:-1], data + b"x", b"X" + data[1:]):
            with self.subTest(bad=bad), self.assertRaises(guard.SnapshotError):
                guard.remote_action(path, "publish", len(data), digest, source_bytes=bad)
        with patch.object(guard.subprocess, "run", side_effect=subprocess.TimeoutExpired("gcloud", 120)):
            with self.assertRaisesRegex(guard.SnapshotError, "TRUSTED_SSH_TIMEOUT action=publish"):
                guard.remote_action(path, "publish", len(data), digest, source_bytes=data)
        with patch.object(guard.subprocess, "run", return_value=SimpleNamespace(
                returncode=7, stdout=b"", stderr=b"REMOTE_SOURCE_HASH_MISMATCH")):
            with self.assertRaisesRegex(guard.SnapshotError,
                                        "TRUSTED_SSH_EXIT action=publish code=7 reason=REMOTE_SOURCE_HASH_MISMATCH"):
                guard.remote_action(path, "publish", len(data), digest, source_bytes=data)

    def test_protected_main_source_is_fixed_and_candidate_copy_is_ignored(self):
        with tempfile.TemporaryDirectory() as root:
            protected = Path(root, "protected")
            candidate = Path(root, "candidate")
            protected.mkdir()
            candidate.mkdir()
            trusted = b"fixed protected-main lifecycle source"
            (protected / "verify_broker_dev_lifecycle.py").write_bytes(trusted)
            (candidate / "verify_broker_dev_lifecycle.py").write_bytes(b"candidate-modified validator")
            with patch.object(guard, "__file__", str(protected / "broker_candidate_dev_snapshot.py")):
                self.assertEqual(guard.trusted_source_bytes(), trusted)
            self.assertNotEqual(trusted, (candidate / "verify_broker_dev_lifecycle.py").read_bytes())

    def test_pack_codec_bounds_and_command_argument_margin(self):
        source = guard.trusted_source_bytes()
        packed, compressed_size = guard.pack_source(source)
        self.assertEqual(len(source), 66984)
        self.assertEqual(hashlib.sha256(source).hexdigest(),
                         "ba558b293e6ceba30fc3a3d373731ac05f83396a4e4bf58c3bc0bb4d6e95da9b")
        self.assertEqual(compressed_size, len(zlib.compress(source, 9)))
        self.assertEqual(zlib.decompress(base64.urlsafe_b64decode(packed)), source)
        self.assertRegex(packed, r"\A[A-Za-z0-9_-]+={0,2}\Z")
        self.assertLess(len(packed), guard.MAX_ENCODED_BYTES)
        with patch.object(guard.subprocess, "run", return_value=SimpleNamespace(
                returncode=0, stdout=publish_frame(source), stderr=b"")) as transport:
            log = io.StringIO()
            with contextlib.redirect_stderr(log):
                guard.remote_action(guard.staging_path("35977618907", "1", "preflight"),
                                    "publish", len(source), hashlib.sha256(source).hexdigest(),
                                    source_bytes=source)
        command = transport.call_args.args[0][6].removeprefix("--command=")
        self.assertLess(len(command.encode("ascii")), guard.MAX_REMOTE_COMMAND_BYTES)
        self.assertLess(len(command.encode("ascii")), 32767)
        self.assertEqual(transport.call_args.kwargs["stdin"], subprocess.DEVNULL)
        self.assertNotIn(packed, log.getvalue())
        self.assertNotIn(source[:40].decode("ascii"), log.getvalue())
        self.assertIn('"encodedSize": 23832', log.getvalue())
        for bad in (b"", b"x" * (guard.MAX_SOURCE_BYTES + 1), os.urandom(40000)):
            with self.subTest(size=len(bad)), self.assertRaises(guard.SnapshotError):
                guard.pack_source(bad)

    def test_publish_frame_and_injection_guards(self):
        data = b"trusted"
        digest = hashlib.sha256(data).hexdigest()
        frame = publish_frame(data)
        guard.publish_result(b"transport diagnostic\n" + frame + b"\n", len(data), digest)
        for raw in (b"noise", frame + b"\n" + frame,
                    frame.replace(b'"result":"OK"', b'"result":"FAIL"'),
                    frame.replace(digest.encode(), b"0" * 64)):
            with self.subTest(raw=raw[:60]), self.assertRaises(guard.SnapshotError):
                guard.publish_result(raw, len(data), digest)
        for value in ("1 2", "1\n2", "1'2", "1;2", "1$2", "1`2", "1|2",
                      "1&2", "1/2", "1..2", "1\\2"):
            with self.subTest(value=value), self.assertRaises(guard.SnapshotError):
                guard.staging_path(value, "1", "preflight")

    def test_transport_exception_cannot_print_packed_command(self):
        data = b"trusted payload"
        path = guard.staging_path("35977618907", "1", "preflight")
        digest = hashlib.sha256(data).hexdigest()
        for error in (subprocess.TimeoutExpired("PACKED_SOURCE_SENTINEL", 120),
                      OSError("PACKED_SOURCE_SENTINEL")):
            with self.subTest(error=type(error).__name__), \
                 patch.object(guard.subprocess, "run", side_effect=error):
                try:
                    guard.remote_action(path, "publish", len(data), digest, source_bytes=data)
                except guard.SnapshotError as exc:
                    self.assertNotIn("PACKED_SOURCE_SENTINEL", "".join(traceback.format_exception(exc)))
                else:
                    self.fail("transport exception must fail closed")

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
    def test_linux_remote_packed_publication_and_failure_states(self):
        data = b"trusted non-candidate source\n"
        digest = hashlib.sha256(data).hexdigest()

        def exercise(payload, *, size=len(data), expected_digest=digest, prefix="",
                     preexisting=None, packed_override=None, compressed_override=None,
                     expect_success=False):
            run_id = str(secrets.randbelow(10**12 - 10**11) + 10**11)
            path = guard.staging_path(run_id, "1", "preflight")
            packed, compressed_size = guard.pack_source(payload)
            if packed_override is not None:
                packed = packed_override
            if compressed_override is not None:
                compressed_size = compressed_override
            def remote(action, code=guard._REMOTE_SOURCE):
                extra = [str(compressed_size), packed] if action == "publish" else []
                return subprocess.run([sys.executable, "-B", "-c", code, path, action,
                                       str(size), expected_digest, *extra], stdin=subprocess.DEVNULL,
                                      stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=10)
            self.assertFalse(os.path.lexists(path))
            try:
                self.assertEqual(remote("create").returncode, 0)
                self.assertEqual(stat.S_IMODE(os.lstat(path).st_mode), 0o700)
                if preexisting:
                    Path(path, preexisting).write_bytes(b"existing")
                    os.chmod(Path(path, preexisting), 0o600)
                result = remote("publish", prefix + guard._REMOTE_SOURCE)
                self.assertEqual(result.returncode == 0, expect_success, result.stderr)
                self.assertEqual(Path(path, "lifecycle.py").exists(),
                                 expect_success or preexisting == "lifecycle.py")
                if expect_success:
                    guard.publish_result(result.stdout, len(data), digest)
                    self.assertEqual(Path(path, "lifecycle.py").read_bytes(), data)
                    self.assertFalse(Path(path, "lifecycle.py.part").exists())
                    self.assertEqual(stat.S_IMODE(os.lstat(Path(path, "lifecycle.py")).st_mode), 0o600)
                    snapshot = Path(path, "snapshot.json")
                    snapshot.write_bytes(b'{"profile":"test"}')
                    os.chmod(snapshot, 0o600)
                    read = remote("read")
                    self.assertEqual(read.returncode, 0, read.stderr)
                    self.assertEqual(guard.decode_snapshot_frame(read.stdout), {"profile": "test"})
                if preexisting:
                    self.assertNotEqual(remote("cleanup_empty").returncode, 0)
                    self.assertEqual(Path(path, preexisting).read_bytes(), b"existing")
                    Path(path, preexisting).unlink()
                    self.assertEqual(remote("cleanup_empty").returncode, 0)
                else:
                    self.assertEqual(remote("cleanup_full" if expect_success else
                                            "cleanup_publish_uncertain").returncode, 0)
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
        exercise(data[:-1])
        exercise(data + b"x")
        exercise(b"X" + data[1:])
        exercise(data, size=len(data) - 1)
        exercise(data, packed_override="!")
        exercise(data, packed_override=guard.pack_source(data)[0][:-4])
        exercise(data, packed_override=base64.urlsafe_b64encode(
            b"\x00" * len(zlib.compress(data, 9))).decode())
        trailing = zlib.compress(data, 9) + b"trailing"
        exercise(data, packed_override=base64.urlsafe_b64encode(trailing).decode(),
                 compressed_override=len(trailing))
        bomb = zlib.compress(b"B" * (guard.MAX_SOURCE_BYTES + 1), 9)
        exercise(data, packed_override=base64.urlsafe_b64encode(bomb).decode(),
                 compressed_override=len(bomb))
        empty = zlib.compress(b"", 9)
        exercise(data, packed_override=base64.urlsafe_b64encode(empty).decode(),
                 compressed_override=len(empty))
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
            self.assertNotEqual(remote("cleanup_full").returncode, 0)
            self.assertEqual(unexpected.read_bytes(), b"evidence")
            unexpected.unlink()
            link = Path(path, "lifecycle.py.part")
            os.symlink("/dev/null", link)
            self.assertNotEqual(remote("cleanup_full").returncode, 0)
            self.assertTrue(link.is_symlink())
            link.unlink()
            link.write_bytes(data)
            os.chmod(link, 0o644)
            self.assertNotEqual(remote("cleanup_publish_uncertain").returncode, 0)
            self.assertTrue(link.exists())
            os.chmod(link, 0o600)
            other = Path(path, "hardlink")
            os.link(link, other)
            self.assertNotEqual(remote("cleanup_publish_uncertain").returncode, 0)
            self.assertTrue(link.exists())
            other.unlink()
            link.unlink()
            os.chmod(path, 0o755)
            self.assertNotEqual(remote("cleanup_full").returncode, 0)
            os.chmod(path, 0o700)
            self.assertEqual(remote("cleanup_empty").returncode, 0)
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
            if name == "publish":
                raise guard.SnapshotError("TRUSTED_SSH_TIMEOUT action=publish")
        with patch.object(guard, "gcloud", side_effect=identity), \
             patch.object(guard, "remote_action", side_effect=action):
            with self.assertRaisesRegex(guard.SnapshotError, "TRUSTED_SSH_TIMEOUT"):
                guard.capture("35977618907", "1", "preflight")
        self.assertEqual(calls, ["create", "publish", "cleanup_publish_uncertain"])

    def test_uncertain_create_and_cleanup_failure_report_exact_path(self):
        path = guard.staging_path("35977618907", "1", "postflight")
        identity = json.dumps({"name": guard.INSTANCE, "id": guard.INSTANCE_ID, "status": "RUNNING"})
        with patch.object(guard, "gcloud", return_value=identity), \
             patch.object(guard, "remote_action", side_effect=RuntimeError("transport failed")):
            with self.assertRaisesRegex(guard.SnapshotError, "REMOTE_STAGING_CREATE_UNCERTAIN path=" + path):
                guard.capture("35977618907", "1", "postflight")
        def action(_path, name, _size, _digest, **kwargs):
            if name.startswith("cleanup"):
                raise RuntimeError("unexpected contents")
            if name == "publish":
                raise RuntimeError("publish failed")
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
