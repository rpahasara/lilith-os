"""Focused fixed snapshot release, CLI, installer, and host-contract tests."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import sqlite3
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from scripts import trusted_broker_snapshot as tool
from scripts import trusted_broker_snapshot_installer as installer
from scripts import trusted_broker_snapshot_release as release
from scripts import verify_broker_dev_lifecycle as lifecycle
from scripts.test_broker_dev_lifecycle import accepted_fixture


ROOT = Path(__file__).resolve().parents[1]


def sources() -> dict[str, bytes]:
    return {target: (ROOT / source).read_bytes() for source, target in release.SOURCE_MAP.items()}


def fixture_release(parent: Path) -> tuple[Path, str]:
    payloads = sources()
    manifest = release.canonical(release.make_manifest(payloads))
    release_id = release.digest(manifest)
    folder = parent / release_id
    (folder / "bin").mkdir(parents=True)
    (folder / "lib").mkdir()
    for name, data in payloads.items():
        target = folder / name
        target.write_bytes(data)
        target.chmod(0o755 if name.startswith("bin/") else 0o644)
    (folder / "release-manifest.json").write_bytes(manifest)
    (folder / "release-manifest.json").chmod(0o644)
    folder.chmod(0o755)
    (folder / "bin").chmod(0o755)
    (folder / "lib").chmod(0o755)
    return folder, release_id


class SnapshotFoundationTests(unittest.TestCase):
    def test_cli_operation_is_closed(self):
        with patch.object(sys, "argv", ["snapshot", "anything"]):
            with self.assertRaisesRegex(tool.SnapshotError, "FIXED_SNAPSHOT_OPERATION_ONLY"):
                tool.main()
        with patch.object(sys, "argv", ["snapshot", tool.OPERATION, "--path=/tmp"]):
            with self.assertRaisesRegex(tool.SnapshotError, "FIXED_SNAPSHOT_OPERATION_ONLY"):
                tool.main()

    def test_release_manifest_and_custody_reject_tampering(self):
        with tempfile.TemporaryDirectory() as temp:
            folder, release_id = fixture_release(Path(temp))
            self.assertEqual(tool.verify_release(folder, root_custody=False)[0], release_id)
            validator = folder / "lib/verify_broker_dev_lifecycle.py"
            validator.write_bytes(validator.read_bytes() + b"\n# tamper\n")
            with self.assertRaisesRegex(tool.SnapshotError, "SNAPSHOT_PAYLOAD_HASH"):
                tool.verify_release(folder, root_custody=False)
            validator.write_bytes(sources()["lib/verify_broker_dev_lifecycle.py"])
            (folder / "unknown").write_bytes(b"x")
            with self.assertRaisesRegex(tool.SnapshotError, "SNAPSHOT_RELEASE_FILE_SET"):
                tool.verify_release(folder, root_custody=False)

    def test_snapshot_schema_digest_and_lifecycle_reuse(self):
        with tempfile.TemporaryDirectory() as temp:
            folder, release_id = fixture_release(Path(temp))
            snapshot = accepted_fixture()
            mock = SimpleNamespace(collect_accepted=lambda: snapshot, validate_accepted=lambda value: None)
            with patch.object(tool, "_lifecycle", return_value=mock):
                value = tool.collect(folder, enforce_host_custody=False)
            self.assertEqual(value["schema"], tool.SCHEMA)
            self.assertEqual(value["toolReleaseId"], release_id)
            self.assertEqual(value["completeDigestSha256"], tool.digest(tool.canonical(snapshot)))
            self.assertEqual(value["snapshot"], snapshot)
            self.assertIn(b"LILITH_BROKER_CANDIDATE_DEV_SNAPSHOT_V1:", tool.frame(value))

    def test_exact_dev_and_prod_refusal(self):
        lookup = {
            "project/project-id": installer.DEV_PROJECT,
            "instance/zone": installer.DEV_ZONE,
            "instance/id": installer.DEV_INSTANCE_ID,
            "instance/name": installer.DEV_HOST,
        }
        self.assertEqual(installer.DEV_FQDN, lifecycle.DEV_HOSTNAME)
        for hostname in (installer.DEV_HOST, installer.DEV_FQDN):
            with self.subTest(accepted_hostname=hostname):
                installer.assert_dev_host(hostname=hostname, machine_id=installer.DEV_MACHINE_ID,
                                          metadata=lookup.__getitem__)
        failures = (
            ("wrong short", "other", lookup, installer.DEV_MACHINE_ID,
             "PINNED_DEV_IDENTITY_REQUIRED"),
            ("similar prefix", installer.DEV_FQDN + ".other", lookup, installer.DEV_MACHINE_ID,
             "PINNED_DEV_IDENTITY_REQUIRED"),
            ("different FQDN", "other.asia-southeast1-b.c.lilith-agent-260823-27389.internal",
             lookup, installer.DEV_MACHINE_ID, "PINNED_DEV_IDENTITY_REQUIRED"),
            ("wrong instance", installer.DEV_FQDN,
             {**lookup, "instance/id": "other"}, installer.DEV_MACHINE_ID,
             "PINNED_DEV_IDENTITY_REQUIRED"),
            ("wrong instance name", installer.DEV_FQDN,
             {**lookup, "instance/name": "other"}, installer.DEV_MACHINE_ID,
             "PINNED_DEV_IDENTITY_REQUIRED"),
            ("wrong project", installer.DEV_FQDN,
             {**lookup, "project/project-id": "other"}, installer.DEV_MACHINE_ID,
             "PINNED_DEV_IDENTITY_REQUIRED"),
            ("wrong zone", installer.DEV_FQDN,
             {**lookup, "instance/zone": "other"}, installer.DEV_MACHINE_ID,
             "PINNED_DEV_IDENTITY_REQUIRED"),
            ("wrong machine", installer.DEV_FQDN, lookup, "other",
             "PINNED_DEV_IDENTITY_REQUIRED"),
            ("prod hostname", "lilith-01", lookup, installer.DEV_MACHINE_ID,
             "PROD_HOST_FORBIDDEN"),
            ("prod instance", installer.DEV_FQDN,
             {**lookup, "instance/name": "lilith-01"}, installer.DEV_MACHINE_ID,
             "PROD_HOST_FORBIDDEN"),
        )
        for name, hostname, observed, machine_id, error in failures:
            with self.subTest(rejected_identity=name):
                with self.assertRaisesRegex(installer.InstallError, error):
                    installer.assert_dev_host(hostname=hostname, machine_id=machine_id,
                                              metadata=observed.__getitem__)

    def test_manifest_content_identity_is_deterministic(self):
        payloads = sources()
        one = release.canonical(release.make_manifest(payloads))
        two = release.canonical(release.make_manifest(dict(reversed(list(payloads.items())))))
        self.assertEqual(one, two)
        self.assertEqual(release.digest(one), release.digest(two))
        with self.assertRaisesRegex(release.ReleaseError, "PAYLOAD_SET"):
            release.make_manifest({**payloads, "unknown": b"x"})

    def test_immutable_query_only_sqlite_reader_preserves_db_wal_shm(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp, "owner_control.db")
            writer = sqlite3.connect(path)
            try:
                writer.execute("PRAGMA journal_mode=WAL")
                writer.execute("CREATE TABLE accepted (id INTEGER PRIMARY KEY)")
                writer.execute("INSERT INTO accepted VALUES (1)")
                writer.commit()
                writer.execute("PRAGMA wal_checkpoint(TRUNCATE)")
                paths = [path, Path(str(path) + "-wal"), Path(str(path) + "-shm")]
                before = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
                reader, result = lifecycle._database(path, {"accepted": 1}, historical=True)
                try:
                    self.assertEqual(result["counts"]["accepted"], 1)
                finally:
                    reader.close()
                after = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
                self.assertEqual(before, after)
            finally:
                writer.close()

    def test_builder_archive_and_attestation_are_deterministic(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "source"
            source.mkdir()
            subprocess.run(("git", "init", "-q", str(source)), check=True)
            subprocess.run(("git", "-C", str(source), "config", "user.email", "test@example.invalid"), check=True)
            subprocess.run(("git", "-C", str(source), "config", "user.name", "Test"), check=True)
            for path in release.SOURCE_MAP:
                target = source / path
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes((ROOT / path).read_bytes())
            subprocess.run(("git", "-C", str(source), "add", "scripts"), check=True)
            subprocess.run(("git", "-C", str(source), "commit", "-qm", "fixture"), check=True)
            commit = subprocess.check_output(("git", "-C", str(source), "rev-parse", "HEAD"), text=True).strip()
            outputs = []
            for number in (1, 2):
                archive = root / f"release-{number}.tar.gz"
                attestation = root / f"attestation-{number}.json"
                built = release.build(source, commit, archive, attestation)
                verified, files = release.verify(archive, attestation)
                self.assertEqual(built, verified)
                self.assertEqual(files, sources())
                outputs.append((archive.read_bytes(), built["releaseId"]))
            self.assertEqual(outputs[0], outputs[1])
            archive.write_bytes(archive.read_bytes() + b"tamper")
            with self.assertRaisesRegex(release.ReleaseError, "ARCHIVE_HASH"):
                release.verify(archive, attestation)

    @unittest.skipUnless(os.name == "posix", "real installer file modes require Linux")
    def test_installer_first_install_only_fixture(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            control = root / "broker-snapshot"
            incoming = control / "incoming"
            incoming.mkdir(parents=True)
            for path in (root, control, incoming):
                path.chmod(0o755)
            source = root / "source"
            source.mkdir()
            subprocess.run(("git", "init", "-q", str(source)), check=True)
            subprocess.run(("git", "-C", str(source), "config", "user.email", "test@example.invalid"), check=True)
            subprocess.run(("git", "-C", str(source), "config", "user.name", "Test"), check=True)
            for name in release.SOURCE_MAP:
                target = source / name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes((ROOT / name).read_bytes())
            subprocess.run(("git", "-C", str(source), "add", "scripts"), check=True)
            subprocess.run(("git", "-C", str(source), "commit", "-qm", "fixture"), check=True)
            commit = subprocess.check_output(("git", "-C", str(source), "rev-parse", "HEAD"), text=True).strip()
            payloads = sources()
            release_id = release.digest(release.canonical(release.make_manifest(payloads)))
            staged = incoming / release_id
            staged.mkdir()
            staged.chmod(0o700)
            for name in installer.INCOMING_FILES - {"snapshot-release.tar.gz", "snapshot-release.attestation.json"}:
                (staged / name).write_bytes((ROOT / "scripts" / name).read_bytes())
            release.build(source, commit, staged / "snapshot-release.tar.gz",
                          staged / "snapshot-release.attestation.json")
            for path in staged.iterdir():
                path.chmod(0o600)
            with patch.object(installer, "APPROVED_FIRST_RELEASE", release_id):
                result = installer.install(control, release_id, root_custody=False,
                                           self_test=lambda: {"acceptedBaselineDigest": installer.BASELINE})
                self.assertEqual(result["releaseId"], release_id)
                self.assertEqual(os.readlink(control / "current"), "releases/" + release_id)
                with self.assertRaisesRegex(installer.InstallError, "INSTALL_EXISTING"):
                    installer.install(control, release_id, root_custody=False,
                                      self_test=lambda: {"acceptedBaselineDigest": installer.BASELINE})


if __name__ == "__main__":
    unittest.main()
