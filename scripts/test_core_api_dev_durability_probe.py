#!/usr/bin/env python3
"""Safety tests for the trusted persistent-DEV durability probe control."""

from __future__ import annotations

import importlib.util
import json
import os
import sys
import tempfile
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

    def test_production_safety_check_is_read_only_and_requires_zero_rows(self) -> None:
        config = self.root / "canonical-runtime.json"
        cognitive = self.root / "cognitive.db"
        privacy = self.root / "privacy.db"
        config.write_text(
            json.dumps(
                {
                    "schemaVersion": 1,
                    "canonicalLtmEnabled": False,
                    "activeCapabilities": [],
                }
            ),
            encoding="utf-8",
        )
        import sqlite3

        cognitive_tables = {
            table
            for tables in probe.PRODUCTION_COGNITIVE_ZERO_TABLES.values()
            for table in tables
        }
        for database, tables in (
            (cognitive, cognitive_tables),
            (privacy, probe.PRODUCTION_PRIVACY_OPERATIONAL_TABLES),
        ):
            connection = sqlite3.connect(database)
            try:
                for table in tables:
                    connection.execute(f'CREATE TABLE "{table}" (id INTEGER)')
                connection.commit()
            finally:
                connection.close()
        result = probe.production_read_only_safety(config, cognitive, privacy)
        self.assertEqual(result["inspectionMode"], "READ_ONLY")
        self.assertTrue(result["productionRowsRemainZero"])
        connection = sqlite3.connect(cognitive)
        try:
            connection.execute("INSERT INTO memory_item VALUES (1)")
            connection.commit()
        finally:
            connection.close()
        with self.assertRaisesRegex(probe.ProbeError, "production read-only"):
            probe.production_read_only_safety(config, cognitive, privacy)


class DurabilityProbeTrustedWiringTests(unittest.TestCase):
    def test_workflow_uploads_probe_through_iap_and_passes_exact_sha(self) -> None:
        workflow = (ROOT / ".github" / "workflows" / "deploy-dev.yml").read_text(
            encoding="utf-8"
        )
        self.assertIn("scripts/run_core_api_dev_durability_probe.py", workflow)
        self.assertIn("--tunnel-through-iap", workflow)
        self.assertIn("'${VALIDATED_SHA}' '${REMOTE_VERIFIER}' '${REMOTE_DURABILITY_PROBE}'", workflow)
        self.assertNotIn("service_account_key", workflow)

    def test_remote_control_prepares_before_restart_and_verifies_after(self) -> None:
        deploy = (ROOT / "scripts" / "deploy_core_api_dev_remote.sh").read_text(
            encoding="utf-8"
        )
        prepare = deploy.index('"${TRUSTED_DURABILITY_PROBE}" prepare')
        restart = deploy.index('systemctl restart "${SERVICE_NAME}"', prepare)
        verify = deploy.index('"${TRUSTED_DURABILITY_PROBE}" verify')
        cleanup = deploy.index('"${TRUSTED_DURABILITY_PROBE}" cleanup', verify)
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


if __name__ == "__main__":
    unittest.main(verbosity=2)
