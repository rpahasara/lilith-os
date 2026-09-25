"""Source-only contracts for the fixed consumed-run read-only inspector."""

from __future__ import annotations

import ast
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from scripts import classify_dev_deployment as classifier
from scripts import memory_broker_stage3_forensics as forensic

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = (ROOT / ".github/workflows/memory-broker-dev-stage3-a2-forensics.yml").read_text()
SOURCE = (ROOT / "scripts/memory_broker_stage3_forensics.py").read_text()


class FixedForensicContracts(unittest.TestCase):
    def test_workflow_is_dormant_owner_gated_and_fixed_read_only(self):
        self.assertIn("on:\n  workflow_dispatch:\n", WORKFLOW)
        header = WORKFLOW.split("permissions:", 1)[0]
        for trigger in ("  push:", "  pull_request:", "  workflow_run:", "  schedule:"):
            self.assertNotIn(trigger, header)
        guard = WORKFLOW.index("- name: Fail closed before DEV authentication")
        auth = WORKFLOW.index("uses: google-github-actions/auth@v3")
        self.assertLess(guard, auth)
        for required in ('test "$GITHUB_ACTOR" = rpahasara',
                         'test "$GITHUB_REF" = refs/heads/main',
                         'test "$GITHUB_RUN_ATTEMPT" = 1',
                         'test "$GITHUB_SHA" = "$APPROVED_MAIN_SHA"',
                         "RUN_36145190507", "persist-credentials: false"):
            self.assertIn(required, WORKFLOW)
        self.assertIn("--command='sudo -n /usr/bin/python3 -I -B -'", WORKFLOW)
        self.assertEqual(WORKFLOW.count("gcloud compute ssh"), 1)
        for forbidden in ("compute scp", "systemctl start", "systemctl stop",
                          "systemctl restart", "dispatch-once", "install-control",
                          "gcloud iam", "add-iam-policy-binding"):
            self.assertNotIn(forbidden, WORKFLOW)

    def test_exact_source_surface_classifies_control_only(self):
        for path in (".github/workflows/memory-broker-dev-stage3-a2-forensics.yml",
                     "scripts/memory_broker_stage3_forensics.py",
                     "scripts/test_memory_broker_stage3_forensics.py",
                     "docs/architecture/slice15b2b-stage3-a2-consumed-run-forensics.md"):
            self.assertIn(path, classifier.CONTROL_ONLY_PATHS)
            self.assertEqual(classifier.classify_entries(
                [(path, "A", "000000", "100644")], {}),
                classifier.CONTROL_ONLY_NO_DEPLOY)

    def test_collector_has_no_mutating_primitive_or_variable_command(self):
        tree = ast.parse(SOURCE)
        calls = [node for node in ast.walk(tree) if isinstance(node, ast.Call)]
        banned = {"write_text", "write_bytes", "unlink", "rmdir", "mkdir", "replace",
                  "rename", "chmod", "chown", "kill", "system", "popen", "execv"}
        for call in calls:
            if isinstance(call.func, ast.Attribute):
                self.assertNotIn(call.func.attr, banned)
        for forbidden in ('"start"', '"stop"', '"restart"', '"reset-failed"',
                          '"systemd-run"', '"recover"', '"dispatch-once"',
                          '"stage3_accepted_snapshot"', "sqlite3.connect"):
            self.assertNotIn(forbidden, SOURCE)
        self.assertEqual(forensic.RUN_ID, "36145190507")
        self.assertEqual(forensic.UNITS[0], forensic.SERVICE)

    def test_journal_reports_phase_not_record_contents(self):
        with TemporaryDirectory() as temp:
            vault = Path(temp)
            first = {"schema": "Stage3A2TransitionJournalV1", "phase": "INTENT",
                     "previousSha256": None, "record": {"secret": "do-not-report"}}
            raw = (json.dumps(first, sort_keys=True, separators=(",", ":")) + "\n").encode()
            (vault / "000-INTENT.json").write_bytes(raw)
            with patch.object(forensic, "VAULT", vault), patch.object(
                    forensic, "read_fixed", return_value=raw), patch.object(
                    forensic, "stat") as fake_stat:
                fake_stat.S_ISDIR.return_value = True
                fake_stat.S_IMODE.return_value = 0o700
                with patch.object(Path, "lstat") as lstat:
                    lstat.return_value.st_mode = 0o40700
                    lstat.return_value.st_uid = 0
                    result = forensic.phase_journal()
            self.assertEqual(result["terminalPhase"], "INTENT")
            self.assertTrue(result["verifiedHashChain"])
            self.assertNotIn("do-not-report", json.dumps(result))

    def test_journal_message_is_hashed_and_not_printed(self):
        line = json.dumps({"_SYSTEMD_UNIT": forensic.SERVICE,
                           "_SYSTEMD_INVOCATION_ID": "abc",
                           "__REALTIME_TIMESTAMP": "123",
                           "MESSAGE": "secret proof bytes"}).encode() + b"\n"
        with patch.object(forensic, "fixed_command", return_value=line):
            result = forensic.journal_metadata("abc")
        self.assertEqual(result["entryCount"], 1)
        self.assertNotIn("secret proof bytes", json.dumps(result))
        self.assertEqual(result["entries"][0]["messageSha256"],
                         forensic.digest(b"secret proof bytes"))


if __name__ == "__main__":
    unittest.main()
