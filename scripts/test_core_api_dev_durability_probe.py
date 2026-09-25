#!/usr/bin/env python3
"""Safety tests for the trusted persistent-DEV durability probe control."""

from __future__ import annotations

import importlib.util
import json
import os
import sqlite3
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock


SCRIPT = Path(__file__).with_name("run_core_api_dev_durability_probe.py")
ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("dev_durability_probe", SCRIPT)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("durability probe control could not be loaded")
probe = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = probe
SPEC.loader.exec_module(probe)
AUDIT_SCRIPT = Path(__file__).with_name("audit_core_api_production_read_only.py")
AUDIT_SPEC = importlib.util.spec_from_file_location("production_durability_audit", AUDIT_SCRIPT)
if AUDIT_SPEC is None or AUDIT_SPEC.loader is None:
    raise RuntimeError("production durability audit could not be loaded")
audit = importlib.util.module_from_spec(AUDIT_SPEC)
sys.modules[AUDIT_SPEC.name] = audit
AUDIT_SPEC.loader.exec_module(audit)


class DurabilityProbePathSafetyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.dev = self.root / "dev"
        self.dev_data = self.dev / "data"
        self.prod = self.root / "prod"
        self.prod_data = self.prod / "data"
        self.dev_data.mkdir(parents=True)
        self.prod_data.mkdir(parents=True)
        self.cognitive = self.dev_data / "cognitive_memory.dev.db"
        self.privacy = self.dev_data / "privacy_governance.dev.db"
        self.prod_cognitive = self.prod_data / "cognitive_memory.db"
        self.prod_privacy = self.prod_data / "privacy_governance.db"

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def guard(self, cognitive: Path | None = None, privacy: Path | None = None):
        return probe.guard_probe_paths(
            self.dev,
            self.dev_data,
            cognitive or self.cognitive,
            privacy or self.privacy,
            self.prod_cognitive,
            self.prod_privacy,
        )

    def test_accepts_distinct_paths_below_isolated_dev_root(self) -> None:
        selected = self.guard()
        self.assertEqual(selected.cognitive_db, self.cognitive.resolve())
        self.assertEqual(selected.privacy_db, self.privacy.resolve())

    def test_rejects_exact_production_paths(self) -> None:
        with self.assertRaisesRegex(probe.ProbeError, "production"):
            self.guard(cognitive=self.prod_cognitive)
        with self.assertRaisesRegex(probe.ProbeError, "production"):
            self.guard(privacy=self.prod_privacy)

    def test_rejects_paths_outside_isolated_dev_root(self) -> None:
        with self.assertRaisesRegex(probe.ProbeError, "outside"):
            self.guard(cognitive=self.root / "other.db")

    def test_rejects_cognitive_privacy_alias(self) -> None:
        with self.assertRaisesRegex(probe.ProbeError, "physically separate"):
            self.guard(privacy=self.cognitive)

    def test_rejects_hardlink_to_production_database(self) -> None:
        self.prod_cognitive.write_bytes(b"production")
        os.link(self.prod_cognitive, self.cognitive)
        with self.assertRaisesRegex(probe.ProbeError, "aliases"):
            self.guard()

    def test_rejects_bind_mount_equivalent_directory_alias(self) -> None:
        original = probe._same_file

        def alias(left: Path, right: Path) -> bool:
            if Path(left) == self.dev_data and Path(right) == self.prod_data:
                return True
            return original(left, right)

        with mock.patch.object(probe, "_same_file", side_effect=alias):
            with self.assertRaisesRegex(probe.ProbeError, "aliases"):
                self.guard()

    @unittest.skipIf(os.name == "nt", "unprivileged symlink creation is not portable")
    def test_rejects_symlinked_dev_database(self) -> None:
        self.prod_cognitive.write_bytes(b"production")
        self.cognitive.symlink_to(self.prod_cognitive)
        with self.assertRaisesRegex(probe.ProbeError, "production|symlink"):
            self.guard()

    def test_clean_baseline_rejects_any_existing_database(self) -> None:
        selected = self.guard()
        self.cognitive.touch()
        with self.assertRaisesRegex(probe.ProbeError, "unexpected"):
            probe.assert_clean_baseline(selected, self.dev_data / "probe")

    def test_clean_baseline_rejects_leftover_sidecar(self) -> None:
        selected = self.guard()
        Path(str(self.privacy) + "-wal").touch()
        with self.assertRaisesRegex(probe.ProbeError, "unexpected"):
            probe.assert_clean_baseline(selected, self.dev_data / "probe")


class DurabilityProbeEvidenceSafetyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_target_record_is_stable_and_detects_synthetic_value(self) -> None:
        target = self.root / "legacy"
        target.mkdir()
        file_path = target / "MEMORY.md"
        file_path.write_text("unrelated", encoding="utf-8")
        first = probe._target_record(target, b"SYNTHETIC-VALUE")
        second = probe._target_record(target, b"SYNTHETIC-VALUE")
        self.assertEqual(first, second)
        self.assertFalse(first["tokenFound"])
        file_path.write_text("SYNTHETIC-VALUE", encoding="utf-8")
        changed = probe._target_record(target, b"SYNTHETIC-VALUE")
        self.assertNotEqual(first["treeSha256"], changed["treeSha256"])
        self.assertTrue(changed["tokenFound"])

    def test_marker_validation_is_candidate_and_path_bound(self) -> None:
        candidate = "a" * 40
        marker = self.root / "marker.json"
        marker.write_text(json.dumps(probe._marker(candidate)), encoding="utf-8")
        self.assertEqual(probe.validate_marker(candidate, marker), probe._marker(candidate))
        with self.assertRaisesRegex(probe.ProbeError, "does not match"):
            probe.validate_marker("b" * 40, marker)

    def test_invalid_candidate_sha_is_rejected_by_cli(self) -> None:
        self.assertIsNone(probe.SHA_RE.fullmatch("not-a-sha"))

class DurabilityProbeTrustedWiringTests(unittest.TestCase):
    def test_probe_is_owner_pinned_and_workflow_passes_exact_sha(self) -> None:
        workflow = (ROOT / ".github" / "workflows" / "deploy-dev.yml").read_text(
            encoding="utf-8"
        )
        installer = (ROOT / "scripts" / "dev_deployer" / "install_dev_deployer_boundary.sh").read_text(
            encoding="utf-8"
        )
        # 15B2b-B1c: the probe is installed root-owned by the owner, never uploaded.
        self.assertNotIn("scripts/run_core_api_dev_durability_probe.py", workflow)
        self.assertIn('"${LIB_DIR}/run_core_api_dev_durability_probe.py"', installer)
        self.assertIn("--tunnel-through-iap", workflow)
        self.assertIn("sudo -n /usr/local/sbin/lilith-dev-deploy deploy ${VALIDATED_SHA}", workflow)
        self.assertNotIn("service_account_key", workflow)

    def test_helper_prepares_before_restart_and_verifies_after(self) -> None:
        helper = (ROOT / "scripts" / "dev_deployer" / "lilith-dev-deploy").read_text(
            encoding="utf-8"
        )
        prepare = helper.index('"${PROBE}" prepare')
        restart = helper.index('systemctl restart "${SERVICE_NAME}"', prepare)
        verify = helper.index('"${PROBE}" verify')
        cleanup = helper.index('"${PROBE}" cleanup', verify)
        self.assertLess(prepare, restart)
        self.assertLess(restart, verify)
        self.assertLess(verify, cleanup)

    def test_probe_has_only_explicit_production_rejection_paths(self) -> None:
        source = SCRIPT.read_text(encoding="utf-8")
        self.assertIn(
            "/home/lilith/.hermes/lilith-os/data/cognitive_memory.db", source
        )
        self.assertIn(
            "/home/lilith/.hermes/lilith-os/data/privacy_governance.db", source
        )
        self.assertIn("resolves to a production database", source)
        self.assertIn("?mode=ro", source)
        self.assertNotIn("systemctl restart lilith-os-api.service", source)
        self.assertNotIn("_atomic_json(DEFAULT_CONFIG_PATH", source)
        self.assertNotIn("_atomic_json(PRODUCTION_CONFIG_PATH", source)

    def test_routine_dev_workflow_has_no_production_login(self) -> None:
        workflow = (ROOT / ".github" / "workflows" / "deploy-dev.yml").read_text(
            encoding="utf-8"
        )
        # 15B2b-B1c: PROD darkness is a future separately governed read-only proof.
        self.assertNotIn("Audit production darkness", workflow)
        self.assertNotIn("GCP_PROD_INSTANCE", workflow)
        self.assertNotIn('gcloud compute ssh "${GCP_PROD', workflow)
        self.assertNotIn("audit_core_api_production_read_only.py", workflow)


class DurabilityProbeCleanupTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.app = self.root / "dev"
        self.data = self.app / "data"
        self.data.mkdir(parents=True)
        self.prod = self.root / "prod"
        self.prod.mkdir()
        self.cognitive = self.data / "cognitive_memory.dev.db"
        self.privacy = self.data / "privacy_governance.dev.db"
        self.probe_dir = self.data / "canonical-durability-probe"
        self.candidate = "a" * 40
        self.paths = probe.guard_probe_paths(
            self.app, self.data, self.cognitive, self.privacy,
            self.prod / "cognitive_memory.db", self.prod / "privacy_governance.db",
        )
        patches = {
            "default_probe_paths": mock.Mock(return_value=self.paths),
            "PROBE_DIR": self.probe_dir,
            "MARKER_PATH": self.probe_dir / "owned-probe.json",
            "STATE_PATH": self.probe_dir / "pre-restart-state.json",
            "PROBE_CONFIG_PATH": self.probe_dir / "canonical-runtime.probe.json",
            "CONTAINMENT_PATH": self.probe_dir / "containment.json",
            "ACTOR_SECRET_PATH": self.probe_dir / "actor.key",
            "PRIVACY_SECRET_PATH": self.probe_dir / "privacy.key",
            "CONTAINMENT_SECRET_PATH": self.probe_dir / "containment.key",
            "BACKUP_DIR": self.probe_dir / "backups",
            "COGNITIVE_DB": self.cognitive,
            "PRIVACY_DB": self.privacy,
        }
        self.patchers = [mock.patch.object(probe, key, value) for key, value in patches.items()]
        for patcher in self.patchers:
            patcher.start()

    def tearDown(self) -> None:
        for patcher in reversed(self.patchers):
            patcher.stop()
        self.temporary.cleanup()

    def owned(self) -> None:
        self.probe_dir.mkdir(mode=0o700)
        marker = self.probe_dir / "owned-probe.json"
        marker.write_text(json.dumps(probe._marker(self.candidate)), encoding="utf-8")
        os.chmod(marker, 0o600)
        for path in (self.cognitive, self.privacy):
            path.write_bytes(b"synthetic")
            os.chmod(path, 0o600)

    def test_first_cleanup_then_retry_preserves_unrelated_dev_file(self) -> None:
        unrelated = self.data / "unrelated.txt"
        unrelated.write_text("preserve", encoding="utf-8")
        self.owned()
        first = probe._cleanup_generated(self.candidate, require_marker=True)
        self.assertEqual(first["status"], "CLEANUP_COMPLETE")
        self.assertTrue(first["cognitiveDatabaseAbsent"])
        self.assertTrue(first["privacyDatabaseAbsent"])
        self.assertTrue(first["probeDirectoryAbsent"])
        second = probe._cleanup_generated(self.candidate, require_marker=True)
        self.assertEqual(second["status"], "CLEANUP_ALREADY_COMPLETE")
        self.assertEqual(unrelated.read_text(encoding="utf-8"), "preserve")

    def test_missing_marker_with_existing_database_fails_closed(self) -> None:
        self.cognitive.write_bytes(b"synthetic")
        os.chmod(self.cognitive, 0o600)
        with self.assertRaisesRegex(probe.ProbeError, "lacks its ownership marker"):
            probe._cleanup_generated(self.candidate, require_marker=True)
        self.assertTrue(self.cognitive.exists())

    def test_malformed_marker_fails_closed(self) -> None:
        self.owned()
        marker = self.probe_dir / "owned-probe.json"
        marker.write_text("{}", encoding="utf-8")
        with self.assertRaisesRegex(probe.ProbeError, "does not match"):
            probe._cleanup_generated(self.candidate, require_marker=True)
        self.assertTrue(self.cognitive.exists())

    def test_external_hardlink_fails_closed(self) -> None:
        self.owned()
        external = self.root / "external.db"
        os.link(self.cognitive, external)
        with self.assertRaisesRegex(probe.ProbeError, "external hardlink"):
            probe._cleanup_generated(self.candidate, require_marker=True)

    def test_bind_mount_equivalent_fails_closed(self) -> None:
        self.owned()
        with mock.patch.object(probe, "_mount_targets", return_value={self.data}):
            with self.assertRaisesRegex(probe.ProbeError, "mount or bind alias"):
                probe._cleanup_generated(self.candidate, require_marker=True)

    @unittest.skipIf(os.name == "nt", "unprivileged symlink creation is not portable")
    def test_symlinked_probe_directory_fails_closed(self) -> None:
        self.probe_dir.symlink_to(self.prod, target_is_directory=True)
        with self.assertRaisesRegex(probe.ProbeError, "symlink"):
            probe._cleanup_generated(self.candidate, require_marker=True)


class ProductionReadOnlyAuditTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    @staticmethod
    def metadata(key: str) -> str:
        return {
            "instance/name": audit.INSTANCE,
            "instance/id": audit.INSTANCE_ID,
            "project/project-id": audit.PROJECT,
            "instance/zone": f"projects/763184673487/zones/{audit.ZONE}",
        }[key]

    @staticmethod
    def service() -> dict[str, str]:
        return {
            "LoadState": "loaded",
            "ActiveState": "active",
            "SubState": "running",
            "FragmentPath": audit.SERVICE_FRAGMENT,
            "MainPID": "1234",
        }

    def test_pinned_host_accepts_exact_identity_and_rejects_dev_or_unknown(self) -> None:
        with mock.patch.object(audit, "pwd", types.SimpleNamespace(
            getpwnam=lambda _: types.SimpleNamespace(pw_uid=42)
        )):
            result = audit.validate_host(
                metadata=self.metadata, hostname=lambda: audit.HOSTNAME,
                service_state=self.service, effective_uid=42,
            )
            self.assertEqual(result["instanceId"], audit.INSTANCE_ID)
            for wrong in ("lilith-dev-01", "unknown-host"):
                with self.assertRaisesRegex(audit.AuditError, "identity mismatch"):
                    audit.validate_host(
                        metadata=lambda key, wrong=wrong: wrong if key == "instance/name" else self.metadata(key),
                        hostname=lambda: audit.HOSTNAME,
                        service_state=self.service, effective_uid=42,
                    )
            with self.assertRaisesRegex(audit.AuditError, "identity mismatch"):
                audit.validate_host(
                    metadata=self.metadata, hostname=lambda: "lilith-dev-01",
                    service_state=self.service, effective_uid=42,
                )

    def test_wrong_service_identity_fails_closed(self) -> None:
        with mock.patch.object(audit, "pwd", types.SimpleNamespace(
            getpwnam=lambda _: types.SimpleNamespace(pw_uid=42)
        )):
            with self.assertRaisesRegex(audit.AuditError, "service identity"):
                audit.validate_host(
                    metadata=self.metadata, hostname=lambda: audit.HOSTNAME,
                    service_state=lambda: {**self.service(), "FragmentPath": "/tmp/other.service"},
                    effective_uid=42,
                )

    def test_sqlite_is_mode_ro_query_only_and_zero_rows(self) -> None:
        database = self.root / "production.db"
        connection = sqlite3.connect(database)
        try:
            connection.execute('CREATE TABLE "memory_item" (id INTEGER)')
            connection.commit()
        finally:
            connection.close()
        calls = []
        original_connect = sqlite3.connect

        def observing_connect(*args, **kwargs):
            calls.append((args, kwargs))
            selected = original_connect(*args, **kwargs)
            selected.set_trace_callback(lambda statement: calls.append(statement))
            return selected

        with mock.patch.object(audit, "PRODUCTION_ROOT", self.root), mock.patch.object(
            audit, "_regular_file", return_value={"mode": "0600"}
        ), mock.patch.object(audit.sqlite3, "connect", side_effect=observing_connect):
            result = audit._database(database, ("memory_item",))
        self.assertEqual(result["counts"], {"memory_item": 0})
        self.assertEqual(result["integrityCheck"], "ok")
        self.assertEqual(result["foreignKeyViolations"], 0)
        self.assertIn("?mode=ro", calls[0][0][0])
        self.assertTrue(calls[0][1]["uri"])
        self.assertIn("PRAGMA query_only=ON", calls)
        self.assertFalse(any(
            isinstance(statement, str) and statement.upper().startswith(
                ("INSERT ", "UPDATE ", "DELETE ", "CREATE ", "DROP ", "ALTER ", "VACUUM", "REPLACE ")
            ) for statement in calls
        ))

    def test_audit_source_has_no_mutation_or_restart_operation(self) -> None:
        source = AUDIT_SCRIPT.read_text(encoding="utf-8")
        self.assertIn("mode=ro", source)
        self.assertIn("PRAGMA query_only=ON", source)
        for forbidden in (
            "systemctl restart", "compute scp", "gcloud compute ssh", "sqlite3.connect(str(",
            "INSERT INTO", "UPDATE ", "DELETE FROM", "CREATE TABLE", "DROP TABLE",
            "VACUUM", "chmod(", "chown(", "write_text(", "write_bytes(",
        ):
            self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main(verbosity=2)
