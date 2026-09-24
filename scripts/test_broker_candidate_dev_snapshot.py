"""Closed installed-tool snapshot comparison; no VM or cloud access."""

from __future__ import annotations

import base64
import hashlib
import json
import unittest
from unittest.mock import patch

from scripts import broker_candidate_dev_snapshot as guard
from scripts import trusted_broker_snapshot as tool
from scripts import trusted_broker_snapshot_invocation as invocation
from scripts.test_broker_dev_lifecycle import accepted_fixture


RELEASE = "a" * 64


def accepted_result() -> dict:
    snapshot = accepted_fixture()
    snapshot["api"]["MainPID"] = guard.API_PID
    snapshot["runtimeIncarnations"] = {
        "broker": {"pid": 96650, "bootId": "a" * 36, "startTicks": 91036598},
        "api": {"pid": 88740, "bootId": "a" * 36, "startTicks": 86941441},
    }
    return {
        "schema": tool.SCHEMA, "operation": tool.OPERATION,
        "profile": tool.PROFILE, "toolReleaseId": RELEASE,
        "manifestSha256": RELEASE, "acceptedBaselineDigest": guard.ACCEPTED_DIGEST,
        "completeDigestSha256": hashlib.sha256(tool.canonical(snapshot)).hexdigest(),
        "validation": "PASS", "snapshot": snapshot,
    }


class BrokerCandidateSnapshotTests(unittest.TestCase):
    def test_one_frame_and_closed_schema(self):
        value = accepted_result()
        frame = tool.frame(value)
        self.assertEqual(guard.decode_frame(frame), value)
        self.assertEqual(guard.decode_frame(b"gcloud diagnostic\n" + frame), value)
        for raw in (b"", frame + frame, frame[:-2] + b"!\n"):
            with self.subTest(raw=raw[:30]), self.assertRaises(guard.SnapshotError):
                guard.decode_frame(raw)
        with patch.object(guard, "EXPECTED_RELEASE", RELEASE):
            self.assertEqual(guard.validate_result(value)["snapshotSha256"], value["completeDigestSha256"])
            modified = {**value, "unknown": True}
            with self.assertRaisesRegex(guard.SnapshotError, "SCHEMA"):
                guard.validate_result(modified)

    def test_release_mismatch_and_digest_drift_fail_closed(self):
        value = accepted_result()
        with self.assertRaisesRegex(guard.SnapshotError, "TRUSTED_SNAPSHOT_RELEASE_MISMATCH"):
            guard.validate_result(value)
        with patch.object(guard, "EXPECTED_RELEASE", RELEASE):
            bad = {**value, "completeDigestSha256": "0" * 64}
            with self.assertRaisesRegex(guard.SnapshotError, "TRUSTED_SNAPSHOT_DIGEST"):
                guard.validate_result(bad)
            bad = {**value, "acceptedBaselineDigest": "0" * 64}
            with self.assertRaisesRegex(guard.SnapshotError, "TRUSTED_SNAPSHOT_RESULT"):
                guard.validate_result(bad)

    def test_only_fixed_installed_command_reaches_dev(self):
        value = accepted_result()
        calls = []
        def cloud(*args):
            calls.append(args)
            if args[0] == "instances":
                return json.dumps({"name": guard.INSTANCE, "id": guard.INSTANCE_ID,
                                   "status": "RUNNING"}).encode()
            return tool.frame(value)
        with patch.object(guard, "_gcloud", side_effect=cloud), \
             patch.object(guard, "EXPECTED_RELEASE", RELEASE):
            self.assertEqual(guard.capture()["toolReleaseId"], RELEASE)
        self.assertEqual(calls[1][:2], ("ssh", guard.INSTANCE))
        command = calls[1][-1]
        self.assertEqual(command, "--command=" + invocation.ssh_command())
        self.assertIn(invocation.INVOKER, command)
        self.assertNotIn("lifecycle.py", command)
        self.assertNotIn("candidate", command.lower().replace("/lilith-broker-dev-snapshot", ""))

    def test_preflight_failure_blocks_candidate_and_post_requires_equality(self):
        with patch.object(guard, "_gcloud", return_value=b'{"name":"wrong"}'):
            with self.assertRaisesRegex(guard.SnapshotError, "DEV_INSTANCE_IDENTITY"):
                guard.capture()
        with patch.object(guard, "capture", return_value={"snapshotSha256": "a" * 64}):
            with patch("sys.argv", ["snapshot", "--phase", "postflight", "--expected-snapshot-sha", "b" * 64]):
                with self.assertRaisesRegex(guard.SnapshotError, "DEV_STATE_CHANGED"):
                    guard.main()


if __name__ == "__main__":
    unittest.main()
