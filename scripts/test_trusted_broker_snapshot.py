"""Focused fixed snapshot release, CLI, installer, and host-contract tests."""

from __future__ import annotations

import hashlib
import base64
import copy
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
from scripts import trusted_broker_snapshot_invocation as invocation
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


def sudo_entries() -> list[dict]:
    return [{"account": name, "argv": ["/usr/bin/sudo", "-n", "-l", "-U", name],
             "returncode": 1, "stdout": f"User {name} is not allowed to run sudo on {lifecycle.DEV_INSTANCE}.\n",
             "stderr": ""} for name in tool.SUDO_ACCOUNTS]


def encode_sudo(entries: list[dict]) -> str:
    return base64.urlsafe_b64encode(tool.canonical({"schema": tool.SUDO_SCHEMA,
                                                   "accounts": entries})).decode("ascii")


def accepted_anchor() -> dict:
    unit = {"LoadState": "loaded", "ActiveState": "active", "SubState": "running",
            "NRestarts": "0", "ExecMainStartTimestamp": "Thu 2026-09-24 06:51:22 UTC",
            "InvocationID": installer.ACCEPTED_BROKER_INVOCATION}
    return {
        "schema": installer.ANCHOR_SCHEMA,
        "host": {"project/project-id": installer.DEV_PROJECT,
                 "instance/zone": installer.DEV_ZONE,
                 "instance/id": installer.DEV_INSTANCE_ID,
                 "instance/name": installer.DEV_HOST,
                 "hostname": installer.DEV_FQDN,
                 "machineId": installer.DEV_MACHINE_ID},
        "api": {"unit": {**unit, "MainPID": "88740"},
                "incarnation": {"pid": 88740, "bootId": installer.ACCEPTED_BOOT_ID,
                                "startTicks": installer.ACCEPTED_API_START_TICKS},
                "health": {"status": "ok", "database": True}},
        "broker": {"unit": {**unit, "MainPID": "96650"},
                   "incarnation": {"pid": 96650, "bootId": installer.ACCEPTED_BOOT_ID,
                                   "startTicks": installer.ACCEPTED_BROKER_START_TICKS},
                   "socketUnit": {"LoadState": "loaded", "ActiveState": "active",
                                  "SubState": "running", "UnitFileState": "disabled"},
                   "releaseTarget": "releases/" + installer.ACCEPTED_BROKER_RELEASE,
                   "ownerSocket": {"uid": 999, "gid": 988, "mode": 0o660,
                                   "listening": True}},
        "files": {path: {"sha256": sha, "uid": installer.ANCHOR_FILE_CUSTODY[path][0],
                         "gid": installer.ANCHOR_FILE_CUSTODY[path][1],
                         "mode": installer.ANCHOR_FILE_CUSTODY[path][2]}
                  for path, sha in installer.ANCHOR_FILE_SHA.items()},
        "counts": {"owner": {"owner_proof_challenge_v1": 24,
                             "owner_request_v1": 24, "synthetic_claim_v1": 2},
                   "evidence": {"synthetic_evidence_v1": 2}},
    }


def accepted_snapshot(release_id: str, *, variant: str = "first") -> dict:
    snapshot = {"profile": "POST_STAGE_II_ACCEPTED_V1",
                "stage2AcceptedBaseline": {"stage2AcceptedBaselineDigest": installer.BASELINE},
                "fixture": variant}
    digest = hashlib.sha256(tool.canonical(snapshot)).hexdigest()
    return {"schema": tool.SCHEMA, "operation": tool.OPERATION, "profile": tool.PROFILE,
            "toolReleaseId": release_id, "manifestSha256": release_id,
            "acceptedBaselineDigest": installer.BASELINE, "completeDigestSha256": digest,
            "validation": "PASS", "snapshot": snapshot}


def installer_fixture(root: Path) -> tuple[Path, Path, str]:
    control = root / "broker-snapshot"
    incoming = control / "incoming"
    incoming.mkdir(parents=True)
    for path in (root, control, incoming):
        path.chmod(0o755)
    releases = control / "releases"
    old = releases / installer.KNOWN_OLD_UNACCEPTED
    old.mkdir(parents=True)
    failed = releases / installer.KNOWN_FAILED_UNACCEPTED
    failed.mkdir()
    releases.chmod(0o755)
    old.chmod(0o755)
    failed.chmod(0o755)
    (control / "current").symlink_to("releases/" + installer.KNOWN_OLD_UNACCEPTED)
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
    return control, old, release_id


def isolated_fixture_install(control: Path, release_id: str, *, self_test) -> dict:
    # Exercise installer state transitions with the rebuilt fixture only;
    # the protected production target pin remains unchanged and rejects it.
    with patch.object(installer, "APPROVED_REPAIRED_RELEASE", release_id):
        return installer.install(control, release_id, root_custody=False, self_test=self_test)


class SnapshotFoundationTests(unittest.TestCase):
    def test_new_payload_is_not_authorized_by_old_installer_target(self):
        release_id = release.digest(release.canonical(release.make_manifest(sources())))
        self.assertNotEqual(release_id, installer.APPROVED_REPAIRED_RELEASE)
        with self.assertRaisesRegex(installer.InstallError, "UNAPPROVED_REPAIRED_RELEASE"):
            installer.install(Path("/nonexistent-control"), release_id, root_custody=False)

    def test_installer_rejects_arbitrary_release_before_file_access(self):
        with self.assertRaisesRegex(installer.InstallError, "UNAPPROVED_REPAIRED_RELEASE"):
            installer.install(Path("/nonexistent-control"), "a" * 64, root_custody=False)

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
            mock = SimpleNamespace(collect_accepted=lambda observation: snapshot,
                                   validate_accepted=lambda value: None)
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

    def test_closed_sudo_observation_contract(self):
        entries = sudo_entries()
        decoded = tool.decode_sudo_observation(encode_sudo(entries))
        self.assertEqual(set(decoded), set(tool.SUDO_ACCOUNTS))
        for changed in (None, "not-base64!", base64.urlsafe_b64encode(b"{").decode()):
            with self.subTest(changed=changed), self.assertRaises(tool.SnapshotError):
                tool.decode_sudo_observation(changed)
        mutations = []
        for field, value in (("account", "wrong-account"), ("account", tool.SUDO_ACCOUNTS[1]),
                             ("argv", ["/usr/bin/true"]), ("stdout", "x" * (tool.MAX_SUDO_TEXT + 1)),
                             ("stderr", "x" * (tool.MAX_SUDO_TEXT + 1)),
                             ("returncode", True)):
            changed = copy.deepcopy(entries)
            changed[0][field] = value
            mutations.append(changed)
        mutations.extend((entries[:1], entries + [entries[0]]))
        for changed in mutations:
            with self.subTest(changed=changed), self.assertRaises(tool.SnapshotError):
                tool.decode_sudo_observation(encode_sudo(changed))

    def test_root_invoker_uses_only_fixed_sudo_queries(self):
        results = [SimpleNamespace(returncode=1, stdout=item["stdout"].encode(), stderr=b"")
                   for item in sudo_entries()]
        with patch.object(invocation.os, "name", "posix"), \
             patch.object(invocation.os, "geteuid", return_value=0, create=True), \
             patch.object(invocation.subprocess, "run", side_effect=results) as query:
            encoded = invocation.observe_sudo()
        self.assertEqual(set(tool.decode_sudo_observation(encoded)), set(tool.SUDO_ACCOUNTS))
        self.assertEqual([call.args[0] for call in query.call_args_list],
                         [tuple(item["argv"]) for item in sudo_entries()])
        self.assertIn("--setenv=" + invocation.SUDO_ENV + "=" + encoded,
                      invocation.command(encoded))
        self.assertEqual(invocation.command(encoded)[-5:],
                         ("/usr/bin/python3", "-I", "-B", invocation.TOOL, invocation.OPERATION))

    def test_external_and_direct_account_sudo_share_exact_decision(self):
        name = tool.SUDO_ACCOUNTS[0]
        user = SimpleNamespace(pw_uid=999, pw_gid=999, pw_dir="/nonexistent", pw_shell="/usr/sbin/nologin")
        def read_text(path, **kwargs):
            return (name + ":x:999:999::/nonexistent:/usr/sbin/nologin\n" if str(path) == "/etc/passwd"
                    else name + ":!:0:0:99999:7:::\n")
        with patch.object(lifecycle, "pwd", SimpleNamespace(getpwnam=lambda _: user)), \
             patch.object(lifecycle.Path, "read_text", read_text), \
             patch.object(lifecycle.Path, "exists", return_value=False), \
             patch.object(lifecycle.os, "getgrouplist", return_value=[999], create=True):
            valid = tool.decode_sudo_observation(encode_sudo(sudo_entries()))
            with patch.object(lifecycle.subprocess, "run", side_effect=AssertionError("nested sudo")):
                self.assertEqual(lifecycle._account(name, valid)["uid"], 999)
            with patch.object(lifecycle.subprocess, "run", return_value=SimpleNamespace(
                    returncode=1, stdout=valid[name]["stdout"], stderr="")) as direct:
                self.assertEqual(lifecycle._account(name)["uid"], 999)
                direct.assert_called_once_with(("/usr/bin/sudo", "-n", "-l", "-U", name),
                                               capture_output=True, text=True, timeout=10)
            for stdout, stderr in (("User has privileges", ""), (valid[name]["stdout"], "error")):
                bad = copy.deepcopy(valid)
                bad[name]["stdout"], bad[name]["stderr"] = stdout, stderr
                with self.assertRaisesRegex(lifecycle.LifecycleError, "ACCOUNT_SUDO_PRIVILEGE"):
                    lifecycle._account(name, bad)
                with patch.object(lifecycle.subprocess, "run", return_value=SimpleNamespace(
                        returncode=1, stdout=stdout, stderr=stderr)):
                    with self.assertRaisesRegex(lifecycle.LifecycleError, "ACCOUNT_SUDO_PRIVILEGE"):
                        lifecycle._account(name)

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
    def test_installer_only_known_old_unaccepted_transition(self):
        with tempfile.TemporaryDirectory() as temp:
            control, old, release_id = installer_fixture(Path(temp))
            self.assertNotEqual(release_id, installer.APPROVED_REPAIRED_RELEASE)
            failed = control / "releases" / installer.KNOWN_FAILED_UNACCEPTED
            calls = []
            def check(*, direct):
                target = os.readlink(control / "current")
                calls.append((direct, target))
                if direct:
                    self.assertEqual({p.name for p in (control / "releases").iterdir()},
                                     {installer.KNOWN_OLD_UNACCEPTED,
                                      installer.KNOWN_FAILED_UNACCEPTED, release_id})
                    installer._installed_bytes(control / "releases" / release_id,
                                               release_id, sources(), root_custody=False)
                return accepted_snapshot(release_id)
            result = isolated_fixture_install(control, release_id, self_test=check)
            self.assertEqual(result["releaseId"], release_id)
            self.assertEqual(result["result"], "TRUSTED_SNAPSHOT_RELEASE_ACCEPTED")
            self.assertEqual(result["failedPreservedReleaseId"], installer.KNOWN_FAILED_UNACCEPTED)
            self.assertEqual(result["selfTestCompleteSnapshotDigest"],
                             result["secondCompleteSnapshotDigest"])
            self.assertEqual(calls, [
                (True, "releases/" + installer.KNOWN_OLD_UNACCEPTED),
                (False, "releases/" + release_id)])
            self.assertEqual(os.readlink(control / "current"), "releases/" + release_id)
            self.assertTrue(old.is_dir())
            self.assertTrue(failed.is_dir())
            with self.assertRaisesRegex(installer.InstallError, "INSTALL_EXISTING"):
                isolated_fixture_install(control, release_id, self_test=check)

    @unittest.skipUnless(os.name == "posix", "real installer file modes require Linux")
    def test_installer_rejects_unapproved_release_topology(self):
        for variant in ("missing_old", "missing_failed", "extra", "wrong_current", "target_present"):
            with self.subTest(variant=variant), tempfile.TemporaryDirectory() as temp:
                control, _, release_id = installer_fixture(Path(temp))
                releases = control / "releases"
                if variant == "missing_old":
                    (releases / installer.KNOWN_OLD_UNACCEPTED).rmdir()
                elif variant == "missing_failed":
                    (releases / installer.KNOWN_FAILED_UNACCEPTED).rmdir()
                elif variant == "extra":
                    (releases / ("f" * 64)).mkdir(mode=0o755)
                elif variant == "wrong_current":
                    (control / "current").unlink()
                    (control / "current").symlink_to("releases/" + installer.KNOWN_FAILED_UNACCEPTED)
                else:
                    (releases / release_id).mkdir(mode=0o755)
                with self.assertRaisesRegex(installer.InstallError,
                                            "INSTALL_EXISTING_RELEASE" if variant == "target_present"
                                            else "INSTALL_UNEXPECTED_RELEASE" if variant != "wrong_current"
                                            else "INSTALL_UNEXPECTED_CURRENT"):
                    isolated_fixture_install(
                        control, release_id,
                        self_test=lambda **_: self.fail("unexpected self-test"),
                    )

    @unittest.skipUnless(os.name == "posix", "real installer file modes require Linux")
    def test_failed_first_self_test_leaves_old_selected(self):
        with tempfile.TemporaryDirectory() as temp:
            control, old, release_id = installer_fixture(Path(temp))
            calls = []
            def fail(*, direct):
                calls.append(direct)
                raise installer.InstallError("SNAPSHOT_SELF_TEST_FAILED", {"stderrExcerpt": "fixture"})
            with self.assertRaisesRegex(installer.InstallError,
                                        "NEW_RELEASE_INSTALLED_UNSELECTED_UNACCEPTED") as caught:
                isolated_fixture_install(control, release_id, self_test=fail)
            self.assertEqual(calls, [True])
            self.assertEqual(caught.exception.diagnostics["diagnostics"]["stderrExcerpt"], "fixture")
            self.assertEqual(caught.exception.diagnostics["selfTestResult"], "FAIL")
            self.assertEqual(caught.exception.diagnostics["selfTestReleaseId"], release_id)
            self.assertEqual(os.readlink(control / "current"),
                             "releases/" + installer.KNOWN_OLD_UNACCEPTED)
            self.assertTrue(old.is_dir())
            self.assertTrue((control / "releases" / installer.KNOWN_FAILED_UNACCEPTED).is_dir())
            self.assertTrue((control / "releases" / release_id).is_dir())

    @unittest.skipUnless(os.name == "posix", "real installer file modes require Linux")
    def test_installed_byte_failure_precedes_self_test_and_switch(self):
        with tempfile.TemporaryDirectory() as temp:
            control, old, release_id = installer_fixture(Path(temp))
            def forbidden(*, direct):
                self.fail("self-test ran before installed-byte verification")
            with patch.object(installer, "_installed_bytes",
                              side_effect=installer.InstallError("INSTALLED_PAYLOAD_MISMATCH")):
                with self.assertRaisesRegex(installer.InstallError, "INSTALLED_PAYLOAD_MISMATCH"):
                    isolated_fixture_install(control, release_id, self_test=forbidden)
            self.assertEqual(os.readlink(control / "current"),
                             "releases/" + installer.KNOWN_OLD_UNACCEPTED)
            self.assertTrue(old.is_dir())
            self.assertTrue((control / "releases" / release_id).is_dir())

    @unittest.skipUnless(os.name == "posix", "real installer file modes require Linux")
    def test_digest_mismatch_is_selected_but_unaccepted(self):
        with tempfile.TemporaryDirectory() as temp:
            control, old, release_id = installer_fixture(Path(temp))
            calls = []
            def check(*, direct):
                calls.append(direct)
                return accepted_snapshot(release_id, variant="first" if direct else "second")
            with self.assertRaisesRegex(installer.InstallError,
                                        "SELECTED_BUT_UNACCEPTED_DIGEST_MISMATCH") as caught:
                isolated_fixture_install(control, release_id, self_test=check)
            self.assertEqual(calls, [True, False])
            self.assertNotEqual(caught.exception.diagnostics["firstCompleteSnapshotDigest"],
                                caught.exception.diagnostics["secondCompleteSnapshotDigest"])
            self.assertEqual(caught.exception.diagnostics["selfTestLifecycleProfile"], tool.PROFILE)
            self.assertEqual(caught.exception.diagnostics["selfTestAcceptedBaselineDigest"],
                             installer.BASELINE)
            self.assertEqual(os.readlink(control / "current"), "releases/" + release_id)
            self.assertTrue(old.is_dir())

    @unittest.skipUnless(os.name == "posix", "real installer file modes require Linux")
    def test_second_failure_retains_first_result(self):
        with tempfile.TemporaryDirectory() as temp:
            control, old, release_id = installer_fixture(Path(temp))
            def check(*, direct):
                if direct:
                    return accepted_snapshot(release_id)
                raise installer.InstallError("SNAPSHOT_SELF_TEST_FAILED", {"stderrExcerpt": "fixture"})
            with self.assertRaisesRegex(installer.InstallError,
                                        "SELECTED_BUT_UNACCEPTED_SECOND_SNAPSHOT_FAILED") as caught:
                isolated_fixture_install(control, release_id, self_test=check)
            details = caught.exception.diagnostics
            self.assertEqual(details["firstCompleteSnapshotDigest"],
                             accepted_snapshot(release_id)["completeDigestSha256"])
            self.assertEqual(details["selfTestLifecycleProfile"], tool.PROFILE)
            self.assertEqual(details["selfTestAcceptedBaselineDigest"], installer.BASELINE)
            self.assertEqual(os.readlink(control / "current"), "releases/" + release_id)
            self.assertTrue(old.is_dir())

    def test_stage2_install_anchor_accepts_only_exact_pins(self):
        value = accepted_anchor()
        installer.validate_install_anchor(value)
        mutations = [
            ("API incarnation", lambda v: v["api"]["incarnation"].__setitem__("startTicks", 1)),
            ("API restart", lambda v: v["api"]["unit"].__setitem__("NRestarts", "1")),
            ("broker incarnation", lambda v: v["broker"]["incarnation"].__setitem__("bootId", "wrong")),
            ("broker release", lambda v: v["broker"].__setitem__("releaseTarget", "releases/wrong")),
            ("owner DB", lambda v: v["files"][str(installer.OWNER_DB)].__setitem__("sha256", "0" * 64)),
            ("evidence DB", lambda v: v["files"][str(installer.EVIDENCE_DB)].__setitem__("sha256", "0" * 64)),
            ("counts", lambda v: v["counts"]["owner"].__setitem__("owner_request_v1", 23)),
            ("DEV identity", lambda v: v["host"].__setitem__("instance/id", "wrong")),
            ("PROD", lambda v: v["host"].__setitem__("instance/name", "lilith-01")),
        ]
        for name, mutate in mutations:
            with self.subTest(name=name):
                changed = copy.deepcopy(value)
                mutate(changed)
                with self.assertRaises(installer.InstallError):
                    installer.validate_install_anchor(changed)

    def test_direct_command_fixed_release_and_snapshot_result_contract(self):
        command = installer.direct_command("YWJj")
        self.assertEqual(command[-5:], ("/usr/bin/python3", "-I", "-B", "-c",
                                        installer.DIRECT_LOADER))
        self.assertIn(installer.APPROVED_REPAIRED_RELEASE, command[-1])
        self.assertNotIn("--release-path", command)
        value = accepted_snapshot(installer.APPROVED_REPAIRED_RELEASE)
        framed = tool.frame(value)
        proof = b"LILITH_CONFINEMENT_EVIDENCE_V1:READ_PASS_WRITE_DENIED\n"
        result = SimpleNamespace(returncode=0, stdout=proof + framed, stderr=b"")
        self.assertEqual(installer._snapshot_result(result, direct=True)["completeDigestSha256"],
                         value["completeDigestSha256"])
        with self.assertRaisesRegex(installer.InstallError, "SNAPSHOT_CONFINEMENT_EVIDENCE"):
            installer._snapshot_result(SimpleNamespace(returncode=0, stdout=framed, stderr=b""),
                                       direct=True)
        with self.assertRaisesRegex(installer.InstallError, "SNAPSHOT_SELF_TEST_FAILED") as caught:
            installer._snapshot_result(SimpleNamespace(returncode=1, stdout=b"bad", stderr=b"failure"),
                                       direct=True)
        self.assertEqual(caught.exception.diagnostics["stderrExcerpt"], "failure")
        overlong = SimpleNamespace(returncode=1, stdout=b"x" * 1000, stderr=b"y" * 5000)
        with self.assertRaisesRegex(installer.InstallError, "SNAPSHOT_SELF_TEST_BOUNDS") as caught:
            installer._snapshot_result(overlong, direct=True)
        self.assertLessEqual(len(caught.exception.diagnostics["stdoutExcerpt"]), 768)
        self.assertLessEqual(len(caught.exception.diagnostics["stderrExcerpt"]), 768)

    def test_bounded_diagnostics_preserve_final_lifecycle_failure(self):
        expected = {"bootId": "24d1771d-e1b5-4e5f-816d-da08ad8b367a",
                    "pid": 96650, "startTicks": 91036598}
        observed = {**expected, "bootId": expected["bootId"].replace("-", "")}
        final = ("installed_lifecycle.LifecycleError: ACCEPTED_BROKER_INCARNATION "
                 "field=runtimeIncarnations.broker expected="
                 + json.dumps(expected, sort_keys=True, separators=(",", ":"))
                 + " observed=" + json.dumps(observed, sort_keys=True, separators=(",", ":")))
        stderr = ("Traceback (most recent call last):\n" + "x" * 900 + "\n" + final + "\n").encode()
        details = installer._diagnostics(SimpleNamespace(returncode=1, stdout=b"", stderr=stderr))
        self.assertEqual(details["exceptionType"], "LifecycleError")
        self.assertEqual(details["validationCode"], "ACCEPTED_BROKER_INCARNATION")
        self.assertEqual(details["failingField"], "runtimeIncarnations.broker")
        self.assertEqual(details["expectedObservedSummary"],
                         {"expected": expected, "observed": observed})
        self.assertIn("ACCEPTED_BROKER_INCARNATION", details["stderrTail"])
        self.assertNotIn("ACCEPTED_BROKER_INCARNATION", details["stderrExcerpt"])


if __name__ == "__main__":
    unittest.main()
