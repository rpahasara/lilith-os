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
    def classify(self, *entries, blobs=None, ci_step_exact=False):
        return gate.classify_entries(list(entries), blobs or {}, ci_step_exact)

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

    def test_ci_change_must_be_exact_stage_ii_test_addition(self):
        self.assertEqual(self.classify(changed(gate.CI_PATH), ci_step_exact=True), gate.CONTROL_ONLY_NO_DEPLOY)
        self.assertEqual(self.classify(changed(gate.CI_PATH)), gate.DEPLOY_REQUIRED)
        baseline = b"name: Repository validation\n" + gate.CI_ANCHOR + b"\n  other: true\n"
        accepted = baseline.replace(gate.CI_ANCHOR, gate.CI_ANCHOR + gate.CI_ADDITION)
        self.assertTrue(gate.ci_change_is_exact(baseline, accepted))
        self.assertFalse(gate.ci_change_is_exact(baseline, accepted + b"\n  weakened: true\n"))
        self.assertFalse(gate.ci_change_is_exact(baseline, baseline))

    def test_runtime_and_unknown_paths_require_deploy(self):
        for path in (
            "services/core-api/app.py",
            "services/memory-broker/lilith_memory_broker/server.py",
            "scripts/deploy_core_api_dev_remote.sh",
            "scripts/classify_dev_deployment.py",
            "scripts/verify_broker_dev_lifecycle.py",
            "scripts/run_memory_broker_dev_validation.sh",
            "scripts/audit_core_api_production_read_only.py",
            ".github/workflows/deploy-dev.yml",
            ".github/changed-mode.json",
            "docs/architecture/unreviewed.md",
        ):
            with self.subTest(path=path):
                self.assertEqual(self.classify(changed(path)), gate.DEPLOY_REQUIRED)

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
