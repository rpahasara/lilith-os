"""Regression and bypass checks for the protected-main DEV gate classifier."""

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import classify_dev_deployment as gate


def changed(path, status="M", old="100644", new="100644"):
    return path, status, old, new


class DevGateClassifierTests(unittest.TestCase):
    def classify(self, *entries, blobs=None):
        return gate.classify_entries(list(entries), blobs or {})

    def test_exact_stage_ii_workflow_is_control_only(self):
        self.assertEqual(
            self.classify(changed(".github/workflows/memory-broker-dev-stage2-runtime.yml", "A", "000000")),
            gate.CONTROL_ONLY_NO_DEPLOY,
        )

    def test_exact_stage_ii_harness_test_is_control_only(self):
        self.assertEqual(
            self.classify(changed("scripts/test_memory_broker_stage2_control.py", "A", "000000")),
            gate.CONTROL_ONLY_NO_DEPLOY,
        )

    def test_architecture_and_allowed_control_are_control_only(self):
        self.assertEqual(
            self.classify(
                changed("docs/architecture/slice-15b2b-b1b2b-stage2-runtime-control.md", "A", "000000"),
                changed("scripts/memory_broker_stage2_control.py", "A", "000000"),
            ),
            gate.CONTROL_ONLY_NO_DEPLOY,
        )

    def test_reviewed_installer_revision_only(self):
        for path, pinned in gate.PINNED_CANDIDATE_BLOBS.items():
            self.assertEqual(self.classify(changed(path), blobs={path: pinned}), gate.CONTROL_ONLY_NO_DEPLOY)
            self.assertEqual(self.classify(changed(path), blobs={path: "0" * 40}), gate.DEPLOY_REQUIRED)

    def test_exact_pr_46_control_plane_surface_needs_no_application_deploy(self):
        self.assertEqual(
            self.classify(*(changed(path) for path in (
                ".github/workflows/ci.yml",
                ".github/workflows/deploy-dev.yml",
                "scripts/test_pr_ci_dev_separation.py",
                "scripts/classify_dev_deployment.py",
                "scripts/test_classify_dev_deployment.py",
            ))),
            gate.CONTROL_ONLY_NO_DEPLOY,
        )

    def test_exact_premerge_broker_validation_control_tests_are_control_only(self):
        self.assertEqual(self.classify(*(changed(path) for path in (
            ".github/workflows/deploy-dev.yml",
            "scripts/test_broker_only_dev_workflow.py",
            "scripts/test_pr_ci_dev_separation.py",
            "scripts/classify_dev_deployment.py",
            "scripts/test_classify_dev_deployment.py",
        ))), gate.CONTROL_ONLY_NO_DEPLOY)
        self.assertEqual(self.classify(changed("scripts/unreviewed_broker_workflow.py")),
                         gate.DEPLOY_REQUIRED)

    def test_docs_and_tests_only_need_no_application_deploy(self):
        self.assertEqual(self.classify(
            changed("docs/architecture/slice-15b2b-b1b2b-stage2-runtime-control.md"),
            changed("scripts/test_broker_dev_lifecycle.py"),
        ), gate.CONTROL_ONLY_NO_DEPLOY)

    def test_snapshot_validator_and_tests_use_separate_install_path(self):
        self.assertEqual(self.classify(*(changed(path) for path in (
            "scripts/verify_broker_dev_lifecycle.py",
            "scripts/test_broker_dev_lifecycle.py",
            "scripts/test_trusted_broker_snapshot_linux.py",
            "scripts/test_broker_candidate_dev_snapshot.py",
        ))), gate.CONTROL_ONLY_NO_DEPLOY)

    def test_exact_snapshot_control_plane_is_control_only(self):
        installer = "scripts/trusted_broker_snapshot_installer.py"
        snapshot = "scripts/broker_candidate_dev_snapshot.py"
        for path in (installer, snapshot):
            with self.subTest(path=path):
                self.assertEqual(self.classify(changed(path)), gate.CONTROL_ONLY_NO_DEPLOY)
        self.assertEqual(self.classify(*(changed(path) for path in (
            installer, snapshot,
            "scripts/test_trusted_broker_snapshot.py",
            "scripts/test_broker_candidate_dev_snapshot.py",
            "docs/architecture/slice15b2b-trusted-snapshot-install-acceptance-contract.md",
        ))), gate.CONTROL_ONLY_NO_DEPLOY)
        self.assertEqual(self.classify(
            changed("scripts/classify_dev_deployment.py"),
            changed("scripts/test_classify_dev_deployment.py"),
        ), gate.CONTROL_ONLY_NO_DEPLOY)
        for runtime in (
            "services/memory-broker/lilith_memory_broker/unreviewed.py",
            "services/core-api/app.py",
            "services/memory-broker/deploy/lilith-memory-broker.service",
            "scripts/unreviewed_runtime.py",
        ):
            with self.subTest(runtime=runtime):
                self.assertEqual(self.classify(changed(runtime)), gate.DEPLOY_REQUIRED)
                self.assertEqual(self.classify(changed(installer), changed(runtime)),
                                 gate.DEPLOY_REQUIRED)

    def test_runtime_and_unknown_paths_require_deploy(self):
        for path in (
            "services/core-api/app.py",
            "services/core-api/lilith_memory/owner_proof.py",
            "services/core-api/requirements.txt",
            "services/memory-broker/deploy/lilith-memory-broker.service",
            "services/memory-broker/lilith_memory_broker/unreviewed.py",
            "scripts/memory_broker_os_release.py",
            "scripts/memory_broker_validation.py",
            "scripts/deploy_core_api_dev_remote.sh",
            "scripts/run_memory_broker_dev_validation.sh",
            "scripts/audit_core_api_production_read_only.py",
            ".github/workflows/unreviewed.yml",
            ".github/changed-mode.json",
            "docs/architecture/unreviewed.md",
        ):
            with self.subTest(path=path):
                self.assertEqual(self.classify(changed(path)), gate.DEPLOY_REQUIRED)

    def test_exact_broker_source_and_test_paths_use_candidate_lane(self):
        for path in sorted(gate.BROKER_CANDIDATE_PATHS):
            with self.subTest(path=path):
                self.assertEqual(self.classify(changed(path)), gate.BROKER_CANDIDATE_VALIDATE_ONLY)
        self.assertEqual(self.classify(
            changed("services/memory-broker/lilith_memory_broker/dev_core.py"),
            changed("services/memory-broker/tests/test_dev_synthetic.py"),
            changed("docs/architecture/slice15b2b-stage3-a2-fault-seam.md", "A", "000000"),
        ), gate.BROKER_CANDIDATE_VALIDATE_ONLY)

    def test_stage3_transition_is_control_only_and_not_a_dev_deployment(self):
        for path in (
            "scripts/memory_broker_stage3_transition.py",
            "scripts/memory_broker_stage3_liveness.py",
            "scripts/memory_broker_stage3_guard_worker.py",
            "scripts/memory_broker_stage3_adapters.py",
            "scripts/memory_broker_stage3_final.py",
            "scripts/test_memory_broker_stage3_transition.py",
            "scripts/test_memory_broker_stage3_liveness.py",
            "scripts/test_memory_broker_stage3_guard_linux.py",
            "scripts/test_memory_broker_stage3_adapters.py",
            "scripts/test_memory_broker_stage3_final.py",
            "docs/architecture/slice15b2b-stage3-a2-reversible-transition.md",
            "docs/architecture/slice15b2b-stage3-a2-control-adapters.md",
            "docs/architecture/slice15b2b-stage3-a2-final-controller.md",
        ):
            with self.subTest(path=path):
                self.assertEqual(self.classify(changed(path, "A", "000000")),
                                 gate.CONTROL_ONLY_NO_DEPLOY)

    def test_broker_mixed_or_self_modifying_diff_requires_full_deploy(self):
        broker = changed("services/memory-broker/lilith_memory_broker/dev_core.py")
        for other in (
            changed("services/core-api/app.py"),
            changed("services/core-api/lilith_memory/owner_proof.py"),
            changed(".github/workflows/deploy-dev.yml"),
            changed("scripts/classify_dev_deployment.py"),
            changed("scripts/run_memory_broker_dev_validation.sh"),
            changed("scripts/memory_broker_validation.py"),
            changed("services/memory-broker/lilith_memory_broker/unknown.py", "A", "000000"),
            changed("scripts/test_memory_broker_stage2_control.py"),
        ):
            with self.subTest(other=other):
                self.assertEqual(self.classify(broker, other), gate.DEPLOY_REQUIRED)
        for status, old, new in (("D", "100644", "000000"),
                                 ("M", "100644", "120000"),
                                 ("M", "120000", "100644")):
            self.assertEqual(self.classify(changed(broker[0], status, old, new)),
                             gate.DEPLOY_REQUIRED)

    def test_mixed_control_and_runtime_requires_deploy(self):
        self.assertEqual(
            self.classify(
                changed("scripts/test_memory_broker_stage2_control.py"),
                changed("services/core-api/app.py"),
            ),
            gate.DEPLOY_REQUIRED,
        )

    def test_symlink_and_mode_tricks_require_deploy(self):
        path = "scripts/memory_broker_stage2_control.py"
        for entry in (
            changed(path, "M", "100644", "120000"),
            changed(path, "M", "120000", "100644"),
            changed(path, "A", "000000", "160000"),
            changed(path, "D", "100644", "000000"),
        ):
            self.assertEqual(self.classify(entry), gate.DEPLOY_REQUIRED)

    def test_renamed_runtime_cannot_hide_in_control_diff(self):
        self.assertEqual(
            self.classify(
                changed("services/core-api/app.py", "D", "100644", "000000"),
                changed("scripts/memory_broker_stage2_control.py", "A", "000000"),
            ),
            gate.DEPLOY_REQUIRED,
        )

    def test_empty_malformed_and_noncanonical_diff_fail_closed(self):
        for raw in (
            b"",
            b"broken",
            b":100644 100644 " + b"0" * 40 + b" " + b"1" * 40 + b" M\0../escape\0",
            b":100644 100644 " + b"0" * 40 + b" " + b"1" * 40 + b" R100\0services/core-api/app.py\0",
        ):
            with self.subTest(raw=raw):
                with self.assertRaises(ValueError):
                    gate.parse_raw_diff(raw)
        self.assertEqual(self.classify(), gate.DEPLOY_REQUIRED)

    def test_candidate_mode_override_is_not_an_input(self):
        script = Path(gate.__file__)
        env = dict(os.environ, LILITH_DEV_DEPLOYMENT_MODE=gate.CONTROL_ONLY_NO_DEPLOY)
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "output"
            result = subprocess.run(
                [sys.executable, str(script), "--candidate-root", temp,
                 "--base-sha", "0" * 40, "--candidate-sha", "1" * 40,
                 "--github-output", str(output), "--mode", gate.CONTROL_ONLY_NO_DEPLOY],
                env=env, capture_output=True, text=True,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertFalse(output.exists())

    def test_environment_mode_override_is_ignored(self):
        with patch.dict(os.environ, LILITH_DEV_DEPLOYMENT_MODE=gate.CONTROL_ONLY_NO_DEPLOY):
            self.assertEqual(self.classify(changed("services/core-api/app.py")), gate.DEPLOY_REQUIRED)


if __name__ == "__main__":
    unittest.main()
