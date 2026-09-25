"""Source-only contracts for the manual Stage-III DEV transport boundary."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from scripts import classify_dev_deployment as classifier
from scripts import memory_broker_stage3_dev_transport as transport
from scripts import memory_broker_stage3_wiring_install as wiring


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = (ROOT / ".github/workflows/memory-broker-dev-stage3-a2-final.yml").read_text(
    encoding="utf-8")
STAGE2 = (ROOT / ".github/workflows/memory-broker-dev-stage2-runtime.yml").read_text(
    encoding="utf-8")


class Stage3DevTransportContracts(unittest.TestCase):
    def test_exact_source_identity_is_independent_of_transfer_payload(self):
        transport.local_source_gate()
        self.assertEqual(
            {name: value for name, value in transport.FILES.items()
             if name != "memory_broker_stage3_wiring_install.py"}, wiring.FILES)
        self.assertEqual(transport.UNIT_BYTES, wiring.UNIT_BYTES)
        self.assertEqual(transport.BASE_SHA, wiring.BASE_SHA)
        for name, expected in transport.FILES.items():
            with self.subTest(name=name):
                self.assertEqual(hashlib.sha256((ROOT / "scripts" / name).read_bytes()).hexdigest(),
                                 expected)

    def test_manual_main_owner_gate_precedes_existing_cloud_identity(self):
        self.assertIn("on:\n  workflow_dispatch:\n", WORKFLOW)
        header = WORKFLOW.split("permissions:", 1)[0]
        for forbidden in ("  push:", "  pull_request:", "  schedule:",
                          "  workflow_run:"):
            self.assertNotIn(forbidden, header)
        guard = WORKFLOW.index("- name: Fail closed before DEV authentication")
        auth = WORKFLOW.index("uses: google-github-actions/auth@v3")
        self.assertLess(guard, auth)
        for required in ('test "$GITHUB_ACTOR" = rpahasara',
                         'test "$GITHUB_REF" = refs/heads/main',
                         'test "$GITHUB_RUN_ATTEMPT" = 1',
                         'test "$GITHUB_SHA" = "$APPROVED_MAIN_SHA"',
                         "python3 scripts/memory_broker_stage3_dev_transport.py verify-source"):
            self.assertIn(required, WORKFLOW[guard:auth])
        self.assertIn("persist-credentials: false", WORKFLOW[:auth])
        self.assertIn("cancel-in-progress: false", WORKFLOW)
        for identity in ("lilith-agent-260823-27389", "asia-southeast1-b",
                         "lilith-dev-01", "7687007163730582258",
                         "github-lilith-deployer@lilith-agent-260823-27389.iam.gserviceaccount.com"):
            self.assertIn(identity, WORKFLOW)
            self.assertIn(identity, STAGE2)
        for forbidden in ("gcloud iam", "add-iam-policy-binding", "service-account create",
                          "--impersonate-service-account", "secrets."):
            self.assertNotIn(forbidden, WORKFLOW)

    def test_install_and_dispatch_are_distinct_manual_operations(self):
        self.assertIn("INSTALL_CONTROL_ONLY:I AUTHORIZE STAGE3_A2_FINAL CONTROL_INSTALL_ONLY",
                      WORKFLOW)
        self.assertIn("DISPATCH_ONCE:I AUTHORIZE STAGE3_A2_FINAL ONE_SHOT_DISPATCH",
                      WORKFLOW)
        self.assertEqual(WORKFLOW.count("if: inputs.operation == 'DISPATCH_ONCE'"), 1)
        self.assertEqual(WORKFLOW.count("if: inputs.operation == 'INSTALL_CONTROL_ONLY'"), 3)
        self.assertIn("--command='sudo -n /usr/bin/python3 -I -B - install-control'",
                      WORKFLOW)
        self.assertIn("--command='sudo -n /usr/bin/python3 -I -B - dispatch-once'",
                      WORKFLOW)
        self.assertNotIn("systemctl start", WORKFLOW)
        self.assertNotIn("systemctl restart", WORKFLOW)
        self.assertEqual(transport.SERVICE, wiring.SERVICE)
        self.assertEqual(transport.STAGING, wiring.STAGING)
        self.assertEqual(transport.INSTALLER, wiring.INSTALLER)
        self.assertEqual(transport.RELEASE, wiring.RELEASE)
        self.assertEqual(transport.UNIT, wiring.UNIT)

    def test_only_exact_reviewed_control_paths_are_control_only(self):
        for path in (
            ".github/workflows/memory-broker-dev-stage3-a2-final.yml",
            "scripts/memory_broker_stage3_dev_transport.py",
            "scripts/test_memory_broker_stage3_dev_transport.py",
        ):
            self.assertIn(path, classifier.CONTROL_ONLY_PATHS)
            self.assertEqual(classifier.classify_entries(
                [(path, "A", "000000", "100644")], {}),
                classifier.CONTROL_ONLY_NO_DEPLOY)
        self.assertNotIn(".github/workflows/unreviewed.yml",
                         classifier.CONTROL_ONLY_PATHS)

    def test_preflight_failure_cannot_start_service(self):
        with patch.object(transport, "verify_installed", side_effect=transport.TransportError(
                "DRIFT")), patch.object(transport.os, "geteuid", return_value=0,
                                          create=True), patch.object(transport.os, "getegid",
                                                             return_value=0, create=True), \
             patch.object(transport.subprocess, "run") as run:
            with self.assertRaises(transport.TransportError):
                transport.dispatch_once()
            run.assert_not_called()

    def test_successful_dispatch_starts_exact_service_once_and_reads_report(self):
        report = {"schema": "Stage3A2FinalReportV1", "status": "RESTORED"}
        raw = json.dumps(report).encode()
        control = SimpleNamespace(
            STAGE3_MARKER=Path("/tmp/unused-marker"),
            STAGE3_USED=Path("/tmp/unused-used"),
            STAGE3_ARM=Path("/tmp/unused-arm"),
            assert_host=Mock(), stage3_accepted_snapshot=Mock(),
            stage3_verify_inactive_release=Mock())
        before = {"ActiveState": "inactive", "MainPID": "0", "NRestarts": "0",
                  "UnitFileState": "static", "DropInPaths": ""}
        after = dict(before, Result="success", ExecMainStatus="0")
        with patch.object(transport, "verify_installed"), \
             patch.object(transport, "module_from_bytes", return_value=control), \
             patch.object(transport, "regular", side_effect=lambda path, uid, mode:
                          raw if path.name == "final-report.json" else b"verified"), \
             patch.object(transport, "fields", side_effect=[before, after]), \
             patch.object(transport.os.path, "lexists", return_value=False), \
             patch.object(transport.os, "geteuid", return_value=0, create=True), \
             patch.object(transport.os, "getegid", return_value=0, create=True), \
             patch.object(transport.subprocess, "run") as run:
            result = transport.dispatch_once()
        self.assertEqual(result["status"], "STAGE3_A2_RESTORED")
        self.assertEqual(result["reportSha256"], hashlib.sha256(raw).hexdigest())
        run.assert_called_once_with(
            ["/usr/bin/systemctl", "start", transport.SERVICE],
            check=True, capture_output=True, timeout=15)
        control.stage3_accepted_snapshot.assert_called_once()
        control.stage3_verify_inactive_release.assert_called_once()


if __name__ == "__main__":
    unittest.main()
