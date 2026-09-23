"""Local fixture tests for trusted release and inert DEV installer policy."""

from __future__ import annotations

import hashlib
import io
import json
import os
import shutil
import stat
import subprocess
import tarfile
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

try:
    from scripts import memory_broker_os_release as release
    from scripts import memory_broker_os_installer as installer
except ImportError:  # direct script discovery
    import memory_broker_os_release as release
    import memory_broker_os_installer as installer


def digest(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


class TrustedReleaseCase(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.candidate = self.root / "candidate"
        self.candidate.mkdir()
        self.wheels = self.root / "wheels"
        self.wheels.mkdir()
        assets = {key: ("approved asset " + key).encode() for key in release.ASSET_HASHES}
        shared = {key: ("governed shared " + key).encode() for key in release.SHARED_HASHES}
        wheels = {key: ("approved wheel " + key).encode() for key in release.WHEEL_HASHES}
        patches = (
            patch.dict(release.ASSET_HASHES, {key: digest(value) for key, value in assets.items()}),
            patch.dict(release.SHARED_HASHES, {key: digest(value) for key, value in shared.items()}),
            patch.dict(release.WHEEL_HASHES, {key: digest(value) for key, value in wheels.items()}),
        )
        for item in patches:
            item.start()
            self.addCleanup(item.stop)
        self.original_lock = release.LOCK
        release.LOCK = b"trusted-offline-lock\n"
        self.addCleanup(setattr, release, "LOCK", self.original_lock)
        for source in release.SOURCE_MAP:
            path = self.candidate / source
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(shared.get(source, ("# approved module " + source + "\n").encode()))
        legacy_core = self.candidate / "services/memory-broker/lilith_memory_broker/core.py"
        legacy_core.write_text("# B1b-1 test-only module\n", encoding="utf-8")
        for source, data in assets.items():
            path = self.candidate / source
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        for filename, data in wheels.items():
            (self.wheels / filename).write_bytes(data)
        subprocess.run(("git", "init", "-q", str(self.candidate)), check=True)
        subprocess.run(("git", "-C", str(self.candidate), "-c", "user.name=Test", "-c", "user.email=test@example.invalid", "add", "."), check=True)
        subprocess.run(("git", "-C", str(self.candidate), "-c", "user.name=Test", "-c", "user.email=test@example.invalid", "commit", "-qm", "fixture"), check=True)
        self.sha = subprocess.run(("git", "-C", str(self.candidate), "rev-parse", "HEAD"), capture_output=True, text=True, check=True).stdout.strip()
        self.archive = self.root / "release.tar.gz"
        self.attestation = self.root / "release.attestation.json"

    def test_exact_release_build_and_verify(self):
        release.build(self.candidate, self.wheels, self.sha, self.archive, self.attestation)
        manifest, payloads = release.verify_archive(self.archive, self.attestation, self.sha)
        self.assertEqual(manifest["candidateSha"], self.sha)
        self.assertEqual(set(payloads), release.EXPECTED_PATHS)
        self.assertNotIn("lilith_memory_broker/core.py", payloads)
        self.assertNotIn("lilith_memory/canonical_authority.py", payloads)

    def test_wrong_sha_dirty_tree_and_extra_module(self):
        with self.assertRaises(release.ReleaseError):
            release.build_payloads(self.candidate, self.wheels, "0" * 40)
        extra = self.candidate / "services/memory-broker/lilith_memory_broker/surprise.py"
        extra.write_text("pass\n")
        with self.assertRaises(release.ReleaseError):
            release.build_payloads(self.candidate, self.wheels, self.sha)

    def test_unit_and_wheel_tamper(self):
        with patch.dict(release.ASSET_HASHES, {next(iter(release.ASSET_HASHES)): "0" * 64}):
            with self.assertRaises(release.ReleaseError):
                release.build_payloads(self.candidate, self.wheels, self.sha)
        (self.wheels / next(iter(release.WHEEL_HASHES))).write_bytes(b"tampered")
        with self.assertRaises(release.ReleaseError):
            release.build_payloads(self.candidate, self.wheels, self.sha)

    def test_archive_tamper_and_closed_destinations(self):
        release.build(self.candidate, self.wheels, self.sha, self.archive, self.attestation)
        self.archive.write_bytes(self.archive.read_bytes() + b"tamper")
        with self.assertRaises(release.ReleaseError):
            release.verify_archive(self.archive, self.attestation, self.sha)
        self.assertNotIn("/etc/systemd/system/evil.service", release.EXPECTED_PATHS)

    def _rewrite_archive(self, changes: dict[str, bytes], extra: tuple[str, bytes] | None = None):
        with tarfile.open(self.archive, "r:gz") as old:
            payloads = {item.name: old.extractfile(item).read() for item in old}
        payloads.update(changes)
        if extra is not None:
            payloads[extra[0]] = extra[1]
        with tarfile.open(self.archive, "w:gz") as output:
            for name, data in payloads.items():
                member = tarfile.TarInfo(name)
                member.size = len(data)
                output.addfile(member, io.BytesIO(data))
        stamp = json.loads(self.attestation.read_bytes())
        stamp["archiveByteSize"] = self.archive.stat().st_size
        stamp["archiveSha256"] = digest(self.archive.read_bytes())
        stamp["manifestSha256"] = digest(payloads["release-manifest.json"])
        self.attestation.write_bytes(release.canonical(stamp))

    def test_archive_rejects_traversal_with_rehashed_attestation(self):
        release.build(self.candidate, self.wheels, self.sha, self.archive, self.attestation)
        self._rewrite_archive({}, ("../escape", b"unexpected executable"))
        with self.assertRaises(release.ReleaseError):
            release.verify_archive(self.archive, self.attestation, self.sha)

    def test_manifest_mismatch_with_rehashed_attestation(self):
        release.build(self.candidate, self.wheels, self.sha, self.archive, self.attestation)
        with tarfile.open(self.archive, "r:gz") as old:
            manifest = json.loads(old.extractfile("release-manifest.json").read())
        manifest["deploymentEnvironment"] = "production"
        self._rewrite_archive({"release-manifest.json": release.canonical(manifest)})
        with self.assertRaisesRegex(release.ReleaseError, "MANIFEST_CONTENT_MISMATCH"):
            release.verify_archive(self.archive, self.attestation, self.sha)


class TrustedInstallerCase(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        root = Path(temp.name)
        self.paths = installer.Paths(
            opt=root / "opt", config=root / "etc", state=root / "state", runtime=root / "run",
            service=root / "units/broker.service", socket=root / "units/broker.socket", tmpfiles=root / "tmpfiles/broker.conf",
        )
        self.sha = installer.SELECTED_RELEASE_SHA

    def test_host_and_staging_are_pinned(self):
        metadata = {
            "project/project-id": installer.PROJECT,
            "instance/zone": "projects/763184673487/zones/" + installer.ZONE,
            "instance/id": installer.INSTANCE_ID,
            "instance/name": release.DEV_HOST,
        }
        installer.assert_dev_host(hostname=installer.HOSTNAME, machine_id=release.DEV_MACHINE_ID, metadata=metadata.__getitem__)
        for host, machine in (("lilith-01", release.DEV_MACHINE_ID), (installer.HOSTNAME, "0" * 32)):
            with self.assertRaises(installer.InstallError):
                installer.assert_dev_host(hostname=host, machine_id=machine, metadata=metadata.__getitem__)
        archive, attestation = installer.staged_paths(self.sha)
        self.assertEqual(archive.name, f"lilith-broker-os-{self.sha}.tar.gz")
        self.assertEqual(attestation.name, f"lilith-broker-os-{self.sha}.attestation.json")
        with self.assertRaises(installer.InstallError):
            installer.staged_paths("../../evil")

    def test_full_cloud_identity_and_explicit_prod_denial(self):
        correct = {
            "project/project-id": installer.PROJECT,
            "instance/zone": "projects/763184673487/zones/" + installer.ZONE,
            "instance/id": installer.INSTANCE_ID,
            "instance/name": release.DEV_HOST,
        }
        installer.assert_dev_host(hostname=installer.HOSTNAME, machine_id=installer.MACHINE_ID, metadata=correct.__getitem__)
        wrong = {
            "project/project-id": "other-project",
            "instance/zone": "projects/763184673487/zones/elsewhere",
            "instance/id": installer.PROD_INSTANCE_ID,
            "instance/name": "lilith-01",
        }
        for key, value in wrong.items():
            with self.subTest(key=key):
                observed = {**correct, key: value}
                with self.assertRaises(installer.InstallError):
                    installer.assert_dev_host(hostname=installer.HOSTNAME, machine_id=installer.MACHINE_ID, metadata=observed.__getitem__)
        for hostname in ("lilith-01", "unknown", release.DEV_HOST):
            with self.subTest(hostname=hostname), self.assertRaises(installer.InstallError):
                installer.assert_dev_host(hostname=hostname, machine_id=installer.MACHINE_ID, metadata=correct.__getitem__)
        with self.assertRaisesRegex(installer.InstallError, "CLOUD_IDENTITY_UNAVAILABLE"):
            installer.assert_dev_host(hostname=installer.HOSTNAME, machine_id=installer.MACHINE_ID,
                                      metadata=lambda key: (_ for _ in ()).throw(OSError("metadata unavailable")))

    def test_marker_is_closed_stage_bound_and_expires(self):
        self.paths.config.mkdir()
        issued = datetime(2026, 9, 23, 13, 0, tzinfo=timezone.utc)
        value = installer._authorization_value(self.sha, installer.STAGE_I, issued, "a" * 32)
        self.paths.authorization.write_bytes(release.canonical(value))
        os.chmod(self.paths.authorization, 0o600)
        original_stat = Path.stat

        def owned_stat(path, *args, **kwargs):
            found = original_stat(path, *args, **kwargs)
            if path == self.paths.authorization:
                return SimpleNamespace(st_uid=0, st_mode=stat.S_IFREG | 0o600)
            return found

        with patch.object(Path, "stat", owned_stat):
            installer.require_authorization(self.paths, self.sha, installer.STAGE_I, now=issued + timedelta(minutes=1))
            for stage in (installer.STAGE_II, installer.STAGE_III, installer.ROLLBACK_STAGE):
                with self.subTest(stage=stage), self.assertRaisesRegex(installer.InstallError, "AUTHORIZATION_MISMATCH"):
                    installer.require_authorization(self.paths, self.sha, stage, now=issued + timedelta(minutes=1))
            with self.assertRaisesRegex(installer.InstallError, "AUTHORIZATION_EXPIRED"):
                installer.require_authorization(self.paths, self.sha, now=issued + timedelta(minutes=30))
            for field, replacement in (
                ("schemaVersion", 1), ("purpose", "OTHER"), ("candidateSha", "0" * 40),
                ("instanceId", installer.PROD_INSTANCE_ID), ("ownerActor", "candidate"),
                ("allowedStage", installer.STAGE_II), ("authorizationId", "not-an-id"),
            ):
                with self.subTest(field=field):
                    changed = {**value, field: replacement}
                    self.paths.authorization.write_bytes(release.canonical(changed))
                    with self.assertRaises(installer.InstallError):
                        installer.require_authorization(self.paths, self.sha, now=issued + timedelta(minutes=1))

    def test_stage_i_marker_is_claimed_once_and_preserved(self):
        self.paths.config.mkdir()
        issued = datetime.now(timezone.utc).replace(microsecond=0)
        value = installer._authorization_value(self.sha, installer.STAGE_I, issued, "b" * 32)
        self.paths.authorization.write_bytes(release.canonical(value))
        original_stat = Path.stat

        def owned_stat(path, *args, **kwargs):
            found = original_stat(path, *args, **kwargs)
            if path == self.paths.authorization:
                return SimpleNamespace(st_uid=0, st_mode=stat.S_IFREG | 0o600)
            return found

        with patch.object(Path, "stat", owned_stat):
            installer.consume_authorization(self.paths, self.sha, installer.STAGE_I)
        self.assertFalse(self.paths.authorization.exists())
        self.assertEqual(json.loads(self.paths.used_authorization.read_bytes()), value)
        with self.assertRaisesRegex(installer.InstallError, "AUTHORIZATION_MISSING"):
            installer.consume_authorization(self.paths, self.sha, installer.STAGE_I)

    def test_first_install_collision_matrix(self):
        with patch.object(installer, "inspect_accounts", return_value=(False, False, False)):
            installer.assert_first_install_preflight(self.paths, marker_expected=False)
            for path in (self.paths.opt, self.paths.config, self.paths.state, self.paths.runtime,
                         self.paths.service, self.paths.socket, self.paths.tmpfiles,
                         Path(str(self.paths.service) + ".d"), Path(str(self.paths.socket) + ".d")):
                with self.subTest(path=path):
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.mkdir()
                    with self.assertRaisesRegex(installer.InstallError, "FIRST_INSTALL_"):
                        installer.assert_first_install_preflight(self.paths, marker_expected=False)
                    path.rmdir()
            with patch.object(installer, "inspect_accounts", return_value=(True, False, False)):
                with self.assertRaisesRegex(installer.InstallError, "FIRST_INSTALL_ACCOUNT_COLLISION"):
                    installer.assert_first_install_preflight(self.paths, marker_expected=False)

    def test_marker_creation_never_precedes_preflight_or_artifact_verification(self):
        archive, attestation = installer.staged_paths(self.sha)
        with patch.object(installer, "assert_dev_host"), patch.object(installer, "require_root"), patch.object(installer, "assert_first_install_preflight", side_effect=installer.InstallError("collision")), patch.object(release, "verify_archive") as verify, patch.object(installer, "_ensure_dir") as create:
            with self.assertRaisesRegex(installer.InstallError, "collision"):
                installer.authorize_dev(self.paths, self.sha, archive, attestation)
            verify.assert_not_called()
            create.assert_not_called()
        with patch.object(installer, "assert_dev_host"), patch.object(installer, "require_root"), patch.object(installer, "assert_first_install_preflight"), patch.object(release, "verify_archive", side_effect=release.ReleaseError("bad artifact")), patch.object(installer, "_ensure_dir") as create:
            with self.assertRaisesRegex(release.ReleaseError, "bad artifact"):
                installer.authorize_dev(self.paths, self.sha, archive, attestation)
            create.assert_not_called()

    def test_stage_i_marker_never_authorizes_activation(self):
        issued = datetime(2026, 9, 23, 13, 0, tzinfo=timezone.utc)
        self.paths.config.mkdir()
        self.paths.authorization.write_bytes(release.canonical(installer._authorization_value(self.sha, installer.STAGE_I, issued, "a" * 32)))
        with patch.object(installer, "assert_dev_host"), patch.object(installer, "require_root"), patch.object(installer, "_current_target") as current, patch.object(installer, "_fixed_run") as run:
            with self.assertRaises(installer.InstallError):
                installer.activate_dev(self.paths, self.sha)
            current.assert_not_called()
            run.assert_not_called()

    def test_systemd_unit_preflight_rejects_alias_dropin_and_active_unit(self):
        clean = "Names=lilith-memory-broker.service\nLoadState=not-found\nActiveState=inactive\nFragmentPath=\nDropInPaths=\nUnitFileState=\n"
        with patch.object(installer.subprocess, "run", return_value=SimpleNamespace(stdout=clean)):
            installer._unit_absent(installer.SERVICE)
        for replacement in (
            "Names=unexpected.service",
            "LoadState=loaded",
            "ActiveState=active",
            "FragmentPath=/etc/systemd/system/lilith-memory-broker.service",
            "DropInPaths=/etc/systemd/system/lilith-memory-broker.service.d/override.conf",
            "UnitFileState=enabled",
        ):
            field = replacement.split("=", 1)[0]
            lines = [replacement if line.startswith(field + "=") else line for line in clean.splitlines()]
            with self.subTest(replacement=replacement), patch.object(
                installer.subprocess, "run", return_value=SimpleNamespace(stdout="\n".join(lines))
            ), self.assertRaisesRegex(installer.InstallError, "SYSTEMD_UNIT_COLLISION"):
                installer._unit_absent(installer.SERVICE)

    def test_selected_release_rejects_other_sha(self):
        with self.assertRaisesRegex(installer.InstallError, "UNAPPROVED_RELEASE_SHA"):
            installer.assert_selected_release("0" * 40)
        installer.assert_selected_release(self.sha)

    def test_metadata_requires_google_flavor_and_proxy_free_opener(self):
        class Response:
            headers = {"Metadata-Flavor": "other"}

            def __enter__(self):
                return self

            def __exit__(self, *unused):
                return None

        with patch.object(installer, "build_opener") as opener:
            opener.return_value.open.return_value = Response()
            with self.assertRaisesRegex(installer.InstallError, "UNTRUSTED_METADATA"):
                installer._metadata("instance/id")
            request = opener.return_value.open.call_args.args[0]
            self.assertTrue(request.full_url.startswith("http://169.254.169.254/"))
            self.assertEqual(request.get_header("Metadata-flavor"), "Google")

    def test_manual_workflow_is_stage_i_only_and_uses_trusted_main(self):
        workflow = (Path(__file__).resolve().parents[1] /
                    ".github/workflows/memory-broker-dev-first-install.yml").read_text(encoding="utf-8")
        self.assertIn("workflow_dispatch:", workflow)
        self.assertNotIn("\n  push:", workflow)
        self.assertNotIn("\n  pull_request:", workflow)
        self.assertIn("github.actor == 'rpahasara'", workflow)
        self.assertIn("github.ref == 'refs/heads/main'", workflow)
        self.assertIn("I AUTHORIZE B1B2B_I PROVISION_ONLY", workflow)
        self.assertIn(installer.SELECTED_RELEASE_SHA, workflow)
        self.assertIn(installer.SELECTED_ARCHIVE_SHA256, workflow)
        self.assertIn("authorize-dev --candidate-sha", workflow)
        self.assertIn("install-dev --candidate-sha", workflow)
        self.assertNotIn("activate-dev --candidate-sha", workflow)
        self.assertNotIn("sudo bash", workflow)
        self.assertNotIn("sudo python candidate", workflow)
        self.assertIn("types.ModuleType", workflow)

    def test_config_is_closed_and_no_live_custody(self):
        value = json.loads(installer._config_bytes(self.sha))
        self.assertEqual(value["deploymentEnvironment"], "dev")
        self.assertEqual(value["authorityMode"], "SYNTHETIC_ONLY")
        self.assertEqual(value["canonicalCapability"], "DISABLED")
        self.assertEqual(set(value["custody"].values()), {"ABSENT"})
        self.assertEqual(value["credentialFingerprint"], release.CREDENTIAL_FINGERPRINT)

    def test_install_refuses_without_b1b2b_authorization(self):
        with patch.object(installer, "assert_dev_host"), patch.object(installer, "require_root"):
            with self.assertRaisesRegex(installer.InstallError, "AUTHORIZATION_MISSING"):
                installer.install_dev(self.paths, self.sha, Path("/tmp/anything"), Path("/tmp/anything"))
        self.assertFalse(self.paths.opt.exists())
        self.assertFalse(self.paths.state.exists())

    def test_install_refuses_unknown_state_before_account_provision(self):
        self.paths.state.mkdir()
        (self.paths.state / "unknown.db").write_bytes(b"preserve")
        archive, attestation = installer.staged_paths(self.sha)
        with patch.object(installer, "assert_dev_host"), patch.object(installer, "require_root"), patch.object(installer, "require_authorization"), patch.object(release, "verify_archive", return_value=({}, {})), patch.object(installer, "inspect_accounts", return_value=(False, False, False)), patch.object(installer, "provision_accounts") as provision:
            with self.assertRaisesRegex(installer.InstallError, "FIRST_INSTALL_PATH_COLLISION"):
                installer.install_dev(self.paths, self.sha, archive, attestation)
            provision.assert_not_called()
        self.assertEqual((self.paths.state / "unknown.db").read_bytes(), b"preserve")

    def test_rollback_also_requires_b1b2b_authorization(self):
        with patch.object(installer, "assert_dev_host"), patch.object(installer, "require_root"), patch.object(installer, "_fixed_run") as run:
            with self.assertRaisesRegex(installer.InstallError, "AUTHORIZATION_MISSING"):
                installer.rollback_dev(self.paths, self.sha)
            run.assert_not_called()

    def test_account_and_group_collisions_fail_closed(self):
        invalid_user = SimpleNamespace(
            pw_name=installer.BROKER, pw_shell="/bin/bash", pw_dir="/nonexistent",
            pw_gid=900, pw_uid=900,
        )
        with patch.object(installer, "_lookup_user", side_effect=lambda name: invalid_user if name == installer.BROKER else None), patch.object(installer, "_lookup_group", return_value=None):
            with self.assertRaisesRegex(installer.InstallError, "ACCOUNT_COLLISION"):
                installer.inspect_accounts()
        invalid_group = SimpleNamespace(gr_name=installer.IPC_GROUP, gr_mem=["outsider"], gr_gid=901)
        with patch.object(installer, "_lookup_user", return_value=None), patch.object(installer, "_lookup_group", side_effect=lambda name: invalid_group if name == installer.IPC_GROUP else None):
            with self.assertRaisesRegex(installer.InstallError, "IPC_GROUP_COLLISION"):
                installer.inspect_accounts()

    def test_activation_has_only_fixed_systemctl_commands(self):
        with patch.object(installer, "assert_dev_host"), patch.object(installer, "require_root"), patch.object(installer, "require_authorization"), patch.object(installer, "assert_recorded_accounts"), patch.object(installer, "_current_target", return_value=f"releases/{self.sha}"), patch.object(installer, "_fixed_run") as run:
            installer.activate_dev(self.paths, self.sha)
        self.assertEqual([call.args for call in run.call_args_list], [
            ("/usr/bin/systemd-tmpfiles", "--create", "--prefix=/run/lilith-memory"),
            ("/usr/bin/systemctl", "daemon-reload"),
            ("/usr/bin/systemctl", "enable", "--now", installer.SOCKET),
        ])

    def test_current_pointer_rejects_escape(self):
        self.paths.opt.mkdir()
        try:
            self.paths.current.symlink_to("../../outside")
        except OSError:
            self.skipTest("symlink creation unavailable on this Windows host")
        with self.assertRaises(installer.InstallError):
            installer._current_target(self.paths)

    def test_rollback_refuses_unknown_pointer_before_service_change(self):
        self.paths.config.mkdir()
        self.paths.previous.write_text("../../outside\n")
        os.chmod(self.paths.previous, 0o600)
        with patch.object(installer, "assert_dev_host"), patch.object(installer, "require_root"), patch.object(installer, "require_authorization"), patch.object(installer, "assert_recorded_accounts"), patch.object(installer, "_fixed_run") as run:
            with self.assertRaises(installer.InstallError):
                installer.rollback_dev(self.paths, self.sha)
            run.assert_not_called()

    def test_rollback_preserves_state_and_accounts(self):
        self.paths.config.mkdir()
        self.paths.opt.mkdir()
        self.paths.state.mkdir()
        owner = self.paths.state / "owner_control.db"
        evidence = self.paths.state / "synthetic_evidence.db"
        owner.write_bytes(b"owner forensic fixture")
        evidence.write_bytes(b"synthetic evidence fixture")
        self.paths.previous.write_text("NONE\n")
        os.chmod(self.paths.previous, 0o600)
        try:
            self.paths.current.symlink_to("releases/" + self.sha)
        except OSError:
            self.skipTest("symlink creation unavailable on this Windows host")
        (self.paths.releases / self.sha).mkdir(parents=True)
        original_stat = Path.stat

        def owned_stat(path, *args, **kwargs):
            if path == self.paths.previous:
                return SimpleNamespace(st_uid=0, st_mode=stat.S_IFREG | 0o600)
            return original_stat(path, *args, **kwargs)

        with patch.object(installer, "assert_dev_host"), patch.object(installer, "require_root"), patch.object(installer, "require_authorization"), patch.object(installer, "assert_recorded_accounts"), patch.object(installer, "_fixed_run") as run, patch.object(Path, "stat", owned_stat):
            result = installer.rollback_dev(self.paths, self.sha)
        self.assertEqual(result["status"], "INACTIVE_EVIDENCE_PRESERVED")
        self.assertEqual(owner.read_bytes(), b"owner forensic fixture")
        self.assertEqual(evidence.read_bytes(), b"synthetic evidence fixture")
        self.assertFalse(self.paths.current.is_symlink())
        run.assert_called_once_with("/usr/bin/systemctl", "disable", "--now", installer.SERVICE, installer.SOCKET)


class TrustedSourceAncestryCase(unittest.TestCase):
    """Execute the workflow's actual source gate against disposable Git graphs."""

    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.origin = self.root / "origin"
        self.origin.mkdir()
        self._git(self.origin, "init", "-q", "-b", "main")
        self._git(self.origin, "config", "user.name", "Test")
        self._git(self.origin, "config", "user.email", "test@example.invalid")
        self.source = self._commit("approved source")
        self._commit("intermediate main")
        self._git(self.origin, "branch", "feature")
        self.main = self._commit("governed main")
        self._git(self.origin, "switch", "-q", "feature")
        self.non_ancestor = self._commit("divergent feature")
        self._git(self.origin, "switch", "-q", "main")
        workflow = (Path(__file__).resolve().parents[1] /
                    ".github/workflows/memory-broker-dev-first-install.yml").read_text(encoding="utf-8")
        self.workflow = workflow
        step = workflow.split("      - name: Verify trusted control source\n", 1)[1].split("\n      - name:", 1)[0]
        self.script = "\n".join(line[10:] for line in step.split("        run: |\n", 1)[1].splitlines())
        git_path = Path(shutil.which("git"))
        self.bash = (git_path.parent.parent / "bin/bash.exe") if os.name == "nt" else Path(shutil.which("bash"))

    @staticmethod
    def _git(where: Path, *args: str) -> str:
        result = subprocess.run(("git", "-C", str(where), *args), check=True,
                                capture_output=True, text=True)
        return result.stdout.strip()

    def _commit(self, message: str) -> str:
        path = self.origin / "history.txt"
        with path.open("a", encoding="utf-8") as stream:
            stream.write(message + "\n")
        self._git(self.origin, "add", "history.txt")
        self._git(self.origin, "commit", "-qm", message)
        return self._git(self.origin, "rev-parse", "HEAD")

    def _clone(self, name: str, *, shallow: bool = False, branch: str = "main") -> Path:
        destination = self.root / name
        args = ["git", "clone", "--quiet", "--no-local", "--branch", branch]
        if shallow:
            args.extend(("--depth", "1"))
        subprocess.run((*args, self.origin.as_uri(), str(destination)), check=True,
                       capture_output=True, text=True)
        return destination

    def _check(self, checkout: Path, source: str, *, ref: str = "refs/heads/main",
               workflow_sha: str | None = None) -> subprocess.CompletedProcess:
        environment = {**os.environ, "RELEASE_SHA": source, "GITHUB_REF": ref,
                       "GITHUB_SHA": workflow_sha or self._git(checkout, "rev-parse", "HEAD")}
        return subprocess.run((str(self.bash), "-e", "-o", "pipefail", "-c", self.script),
                              cwd=checkout, env=environment, capture_output=True, text=True)

    def test_workflow_retains_complete_history_and_exact_main_gate(self):
        checkout_step = self.workflow.split("      - name: Check out trusted main controls\n", 1)[1].split("\n      - name:", 1)[0]
        self.assertIn("fetch-depth: 0", checkout_step)
        self.assertIn('test "$GITHUB_REF" = refs/heads/main', self.script)
        self.assertIn('test "$GITHUB_SHA" = "$checked_out_main"', self.script)
        self.assertIn('git cat-file -e "${RELEASE_SHA}^{commit}"', self.script)
        self.assertIn('git merge-base --is-ancestor "$RELEASE_SHA" "$checked_out_main"', self.script)

    def test_full_history_proves_approved_ancestor(self):
        checkout = self._clone("full")
        self.assertEqual(self._git(checkout, "rev-parse", "--is-shallow-repository"), "false")
        result = self._check(checkout, self.source)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("WORKFLOW_REF=refs/heads/main", result.stdout)
        self.assertIn(f"CHECKED_OUT_MAIN_SHA={self.main}", result.stdout)

    def test_shallow_tip_fails_closed_then_unshallow_passes(self):
        checkout = self._clone("shallow", shallow=True)
        self.assertEqual(self._git(checkout, "rev-parse", "--is-shallow-repository"), "true")
        self.assertNotEqual(self._check(checkout, self.source).returncode, 0)
        self._git(checkout, "fetch", "--unshallow")
        self.assertEqual(self._git(checkout, "rev-parse", "--is-shallow-repository"), "false")
        result = self._check(checkout, self.source)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_existing_non_ancestor_fails(self):
        checkout = self._clone("non-ancestor")
        self._git(checkout, "cat-file", "-e", self.non_ancestor + "^{commit}")
        self.assertNotEqual(self._check(checkout, self.non_ancestor).returncode, 0)

    def test_unknown_and_malformed_sha_fail(self):
        checkout = self._clone("unknown")
        for source in ("0" * 40, "not-a-sha"):
            with self.subTest(source=source):
                self.assertNotEqual(self._check(checkout, source).returncode, 0)

    def test_feature_ref_and_branch_substitution_fail(self):
        checkout = self._clone("feature", branch="feature")
        self.assertNotEqual(self._check(checkout, self.source, ref="refs/heads/feature").returncode, 0)
        self.assertNotEqual(self._check(checkout, self.source).returncode, 0)

    def test_workflow_sha_mismatch_fails(self):
        checkout = self._clone("mismatch")
        self.assertNotEqual(self._check(checkout, self.source, workflow_sha=self.source).returncode, 0)


if __name__ == "__main__":
    unittest.main()
