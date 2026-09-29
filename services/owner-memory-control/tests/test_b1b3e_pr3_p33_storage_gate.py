"""15B2b-B1b-3e PR-3 P3-3: owner storage-capability gate (TEST-ONLY, offline).

Record: docs/architecture/slice-15b2b-b1b3e-pr3-owner-offhost-foundation.md (§25).

Every replica and probe directory here is a throwaway temporary directory.
No real owner replica, DEV host, cloud resource, or key is touched.
"""

from __future__ import annotations

import errno
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import synthetic_authority as SA  # noqa: F401  (sets sys.path)
from lilith_owner_memory import owner_freshness_tool as T

ENV, PROFILE = "dev", "DEV_SYNTHETIC"
POSIX = os.name == "posix"


class Temp:
    def __init__(self, test: unittest.TestCase):
        self.dir = Path(tempfile.mkdtemp(prefix="p33-"))
        test.addCleanup(shutil.rmtree, self.dir, True)

    def sub(self, *parts: str) -> Path:
        path = self.dir.joinpath(*parts)
        path.mkdir(parents=True, exist_ok=True)
        return path


@unittest.skipUnless(POSIX, "the P3-3 gate requires POSIX directory fsync")
class ProbeTests(unittest.TestCase):
    def setUp(self):
        self.t = Temp(self)

    def assert_clean(self, parent: Path) -> None:
        self.assertEqual([n for n in os.listdir(parent) if n.startswith(T.PROBE_PREFIX)], [])

    def test_capable_filesystem_passes_every_check_and_cleans_up(self):
        parent = self.t.sub("probe")
        result = T.probe_storage(parent)
        self.assertEqual(result["result"], T.P3_STORAGE_CAPABLE, result)
        self.assertEqual(set(result["checks"]), set(T.PROBE_CHECKS))
        self.assertTrue(all(value is True for value in result["checks"].values()))
        self.assertEqual(set(result["backends"].values()), {T.PASS})
        self.assertEqual(result["admittedBackend"], "RENAME_NOREPLACE_V1")
        self.assertEqual(os.listdir(parent), [])

    def test_hard_link_unsupported_falls_to_rename_noreplace_not_to_overwrite(self):
        # P3-3A: hard links are no longer required when another reviewed create-only backend passes.
        parent = self.t.sub("probe")
        with mock.patch.object(T.os, "link", side_effect=OSError(errno.EPERM, "no hard links")):
            result = T.probe_storage(parent)
        self.assertEqual(result["backends"]["hardlinkPublish"], T.FAIL)
        self.assertEqual(result["admittedBackend"], "RENAME_NOREPLACE_V1")
        self.assertEqual(result["result"], T.P3_STORAGE_CAPABLE)
        self.assertTrue(result["checks"]["cleanup"])
        self.assert_clean(parent)

    def test_no_admitted_backend_is_incapable(self):
        parent = self.t.sub("probe")
        from lilith_owner_memory import create_only_publish as COP
        with mock.patch.object(T.os, "link", side_effect=OSError(errno.EPERM, "no hard links")), \
                mock.patch.object(COP, "rename_noreplace", side_effect=COP.RenameNoReplaceUnavailable(errno.ENOSYS, "x")):
            result = T.probe_storage(parent)
        self.assertEqual((result["result"], result["admittedBackend"]), (T.P3_STORAGE_INCAPABLE, "NONE"))
        self.assertEqual(result["backends"]["renameNoReplace"], T.UNAVAILABLE)
        self.assertEqual(result["backends"]["directExclusiveFinal"], T.PASS)       # evaluated, never admitted
        self.assert_clean(parent)

    def test_link_that_replaces_an_existing_path_fails_the_backend(self):
        parent = self.t.sub("probe")
        real_link = os.link

        def replacing_link(src, dst):
            if os.path.lexists(dst):
                os.unlink(dst)
            real_link(src, dst)

        with mock.patch.object(T.os, "link", side_effect=replacing_link):
            result = T.probe_storage(parent)
        self.assertEqual(result["backends"]["hardlinkPublish"], T.FAIL)
        self.assertNotEqual(result["admittedBackend"], "HARDLINK_PUBLISH_V1")
        self.assert_clean(parent)

    def test_directory_fsync_unsupported_is_incapable(self):
        parent = self.t.sub("probe")
        with mock.patch.object(T, "_directory_fsync_strict", side_effect=OSError(errno.EINVAL, "no dir fsync")):
            result = T.probe_storage(parent)
        self.assertEqual((result["result"], result["checks"]["directoryFsync"]), (T.P3_STORAGE_INCAPABLE, False))
        self.assert_clean(parent)

    def test_symlink_creation_unavailable_is_incapable(self):
        parent = self.t.sub("probe")
        with mock.patch.object(T.os, "symlink", side_effect=OSError(errno.EPERM, "no symlinks")):
            result = T.probe_storage(parent)
        self.assertEqual(result["result"], T.P3_STORAGE_INCAPABLE)
        self.assertFalse(result["checks"]["symlinkDetection"])

    def test_probe_never_runs_inside_a_replica(self):
        replica = self.t.dir / "replica"
        T.init_replica(replica, replica_id="r1", environment=ENV, authority_profile=PROFILE)
        for target in (replica, replica / T.RECORDS):
            with self.assertRaises(T.ToolRefusal) as caught:
                T.probe_storage(target)
            self.assertEqual(caught.exception.reason, "PROBE_INSIDE_REPLICA")
        self.assertEqual(os.listdir(replica / T.RECORDS), [])

    def test_init_real_replica_refuses_when_probe_fails(self):
        target = self.t.sub("store") / "replica-a"
        with mock.patch.object(T, "_directory_fsync_strict", side_effect=OSError(errno.EINVAL, "no dir fsync")):
            with self.assertRaises(T.ToolRefusal) as caught:
                T.init_real_replica(target, replica_id="owner-primary-dev-synthetic-01", environment=ENV,
                                    authority_profile=PROFILE)
        self.assertEqual(caught.exception.reason, T.P3_STORAGE_INCAPABLE)
        self.assertFalse(os.path.lexists(target))                   # nothing initialized

    def test_directory_fsync_is_required_for_real_replicas(self):
        target = self.t.sub("store") / "replica-a"
        with mock.patch.object(T, "_fsync_directory", return_value="UNSUPPORTED_PLATFORM"):
            with self.assertRaises(T.ToolRefusal) as caught:
                T.init_real_replica(target, replica_id="owner-primary-dev-synthetic-01", environment=ENV,
                                    authority_profile=PROFILE)
        self.assertEqual(caught.exception.reason, "DIRECTORY_FSYNC_NOT_PERFORMED")


@unittest.skipUnless(POSIX, "the P3-3 gate requires POSIX directory fsync")
class RealReplicaGateTests(unittest.TestCase):
    def setUp(self):
        self.t = Temp(self)

    def init(self, path: Path, replica_id: str = "owner-primary-dev-synthetic-01", **kwargs):
        return T.init_real_replica(path, replica_id=replica_id, environment=ENV, authority_profile=PROFILE, **kwargs)

    def test_initialized_real_replica_is_empty(self):
        target = self.t.sub("store") / "replica-a"
        result = self.init(target)
        self.assertEqual((result["status"], result["records"]), ("REAL_REPLICA_INITIALIZED_EMPTY", 0))
        self.assertEqual(sorted(os.listdir(target)), [T.MANIFEST, T.RECORDS])
        self.assertEqual(os.listdir(target / T.RECORDS), [])
        self.assertEqual(result["mode"], "0o700")
        self.assertEqual(result["probe"]["result"], T.P3_STORAGE_CAPABLE)
        replica = T.load_replica(target)
        self.assertEqual((replica.replica_id, replica.environment, replica.authority_profile, replica.records),
                         ("owner-primary-dev-synthetic-01", ENV, PROFILE, ()))
        self.assertEqual([n for n in os.listdir(target.parent) if n.startswith(T.PROBE_PREFIX)], [])

    def test_initialization_refuses_an_existing_directory(self):
        target = self.t.sub("store", "replica-a")
        with self.assertRaises(T.ToolRefusal) as caught:
            self.init(target)
        self.assertEqual(caught.exception.reason, "REPLICA_PATH_EXISTS")
        self.assertEqual(os.listdir(target), [])

    def test_git_working_tree_location_refused(self):
        worktree = self.t.sub("repo")
        (worktree / ".git").mkdir()
        for target in (worktree / "replica", worktree / "nested" / "deeper" / "replica"):
            with self.assertRaises(T.ToolRefusal) as caught:
                self.init(target)
            self.assertEqual(caught.exception.reason, "LOCATION_IN_GIT_WORKTREE")
        linked = self.t.sub("linked-worktree")
        (linked / ".git").write_text("gitdir: /elsewhere\n", encoding="utf-8")   # a worktree's .git file
        with self.assertRaises(T.ToolRefusal):
            self.init(linked / "replica")

    def test_known_auto_sync_location_refused(self):
        for root in ("OneDrive", "OneDrive - Contoso", "Dropbox", "Google Drive", "iCloudDrive", "Nextcloud"):
            target = self.t.sub(root) / "replica"
            with self.assertRaises(T.ToolRefusal) as caught:
                self.init(target)
            self.assertEqual(caught.exception.reason, "LOCATION_AUTO_SYNC_ROOT", root)
        synced = self.t.sub("custom-synced")
        with mock.patch.dict(os.environ, {"OneDriveCommercial": str(synced)}):
            with self.assertRaises(T.ToolRefusal) as caught:
                self.init(synced / "replica")
        self.assertEqual(caught.exception.reason, "LOCATION_AUTO_SYNC_ROOT")

    def test_same_replica_id_refused(self):
        first = self.t.sub("a") / "replica"
        T.init_replica(first, replica_id="owner-primary-dev-synthetic-01", environment=ENV, authority_profile=PROFILE)
        with self.assertRaises(T.ToolRefusal) as caught:
            self.init(self.t.sub("b") / "replica", other_replica=first)
        self.assertEqual(caught.exception.reason, "REPLICA_ID_DUPLICATED")

    def test_same_device_refused(self):
        first = self.t.sub("a") / "replica"
        T.init_replica(first, replica_id="owner-primary-dev-synthetic-01", environment=ENV, authority_profile=PROFILE)
        second = self.t.sub("b") / "replica"
        with self.assertRaises(T.ToolRefusal) as caught:
            self.init(second, replica_id="owner-offline-dev-synthetic-01", other_replica=first)
        self.assertEqual(caught.exception.reason, "REPLICA_SAME_DEVICE")      # one temp filesystem
        self.assertFalse(os.path.lexists(second))
        T.init_replica(second, replica_id="owner-offline-dev-synthetic-01", environment=ENV, authority_profile=PROFILE)
        with self.assertRaises(T.ToolRefusal) as caught:
            T.check_independence(first, second)
        self.assertEqual(caught.exception.reason, "REPLICA_SAME_DEVICE")

    def test_same_replica_path_refused(self):
        first = self.t.sub("a") / "replica"
        T.init_replica(first, replica_id="owner-primary-dev-synthetic-01", environment=ENV, authority_profile=PROFILE)
        with self.assertRaises(T.ToolRefusal) as caught:
            T.check_independence(first, first)
        self.assertIn(caught.exception.reason, {"REPLICA_ID_DUPLICATED", "REPLICA_SAME_LOCATION"})
        with self.assertRaises(T.ToolRefusal) as caught:
            self.init(first, replica_id="owner-offline-dev-synthetic-01")
        self.assertEqual(caught.exception.reason, "REPLICA_PATH_EXISTS")

    def test_cli_commands(self):
        store = self.t.sub("store")
        code, result = T.run(["probe-storage", "--probe-parent", str(store)])
        self.assertEqual((code, result["result"]), (T.EXIT_OK, T.P3_STORAGE_CAPABLE))
        code, result = T.run(["location-check", "--path", str(store / "replica-a")])
        self.assertEqual(code, T.EXIT_OK)
        code, result = T.run(["init-real-replica", "--replica", str(store / "replica-a"), "--replica-id",
                              "owner-primary-dev-synthetic-01", "--environment", ENV, "--profile", PROFILE])
        self.assertEqual((code, result["records"]), (T.EXIT_OK, 0))
        code, result = T.run(["verify-replica", "--replica", str(store / "replica-a")])
        self.assertEqual((code, result["records"], result["headDigest"]), (T.EXIT_OK, 0, None))
        code, result = T.run(["init-real-replica", "--replica", str(store / "replica-b"), "--replica-id",
                              "owner-offline-dev-synthetic-01", "--environment", ENV, "--profile", PROFILE,
                              "--other-replica", str(store / "replica-a")])
        self.assertEqual((code, result["reason"]), (T.EXIT_REFUSED, "REPLICA_SAME_DEVICE"))
        code, result = T.run(["init-real-replica", "--replica", str(store / "replica-c"), "--replica-id", "c",
                              "--environment", "test", "--profile", PROFILE])
        self.assertEqual((code, result["reason"]), (T.EXIT_REFUSED, "PROFILE_MISMATCH"))


if __name__ == "__main__":
    unittest.main()
