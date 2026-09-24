#!/usr/bin/env python3
"""Protected-main, read-only invocation of the pinned installed DEV snapshot tool."""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import re
import subprocess
from pathlib import Path

if __package__:
    from scripts import trusted_broker_snapshot_invocation as invocation
    from scripts import verify_broker_dev_lifecycle as lifecycle
else:
    import trusted_broker_snapshot_invocation as invocation
    import verify_broker_dev_lifecycle as lifecycle


PROJECT = "lilith-agent-260823-27389"
ZONE = "asia-southeast1-b"
INSTANCE = "lilith-dev-01"
INSTANCE_ID = "7687007163730582258"
EXPECTED_RELEASE = "c4d60b9c19debc9fcfece256641a9f83ca82b15b5343cd15cb81a1988c1c6261"
ACCEPTED_DIGEST = "abc33ebf8d43e8805f43ff11e663a4757bf558d9b62eda9669dabecbb7c9839a"
ACCEPTED_BROKER_RELEASE = "817a83e44cec8965479fd97fc30b7a0b3ae49ab2"
API_PID = "88740"
BROKER_PID = "96650"
MAX_FRAME = 3 * 1024 * 1024
PREFIX = b"LILITH_BROKER_CANDIDATE_DEV_SNAPSHOT_V1:"
SHA64 = re.compile(r"[0-9a-f]{64}\Z")


class SnapshotError(RuntimeError):
    pass


def canonical(value: dict) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _gcloud(*args: str) -> bytes:
    try:
        result = subprocess.run(
            ("gcloud", "compute", *args, "--quiet", f"--project={PROJECT}", f"--zone={ZONE}"),
            stdin=subprocess.DEVNULL, capture_output=True, timeout=120,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise SnapshotError("TRUSTED_SNAPSHOT_TRANSPORT_UNAVAILABLE") from exc
    if result.returncode != 0 or len(result.stdout) > MAX_FRAME:
        raise SnapshotError("TRUSTED_SNAPSHOT_TRANSPORT_FAILED")
    return result.stdout


def decode_frame(raw: bytes) -> dict:
    if len(raw) > MAX_FRAME:
        raise SnapshotError("TRUSTED_SNAPSHOT_FRAME_SIZE")
    lines = [line for line in raw.splitlines() if line.startswith(PREFIX)]
    if len(lines) != 1:
        raise SnapshotError("TRUSTED_SNAPSHOT_FRAME_COUNT")
    try:
        size_text, expected, encoded = lines[0][len(PREFIX):].split(b":", 2)
        if not re.fullmatch(rb"[1-9][0-9]{0,6}", size_text) or not re.fullmatch(rb"[0-9a-f]{64}", expected):
            raise ValueError("identity")
        size = int(size_text)
        if size > 2 * 1024 * 1024:
            raise ValueError("size")
        data = base64.b64decode(encoded, validate=True)
        if len(data) != size or hashlib.sha256(data).hexdigest().encode() != expected:
            raise ValueError("digest")
        value = json.loads(data)
        if not isinstance(value, dict) or canonical(value) != data:
            raise ValueError("canonical")
        return value
    except (ValueError, UnicodeError, json.JSONDecodeError) as exc:
        raise SnapshotError("TRUSTED_SNAPSHOT_FRAME_INVALID") from exc


def validate_result(value: dict) -> dict:
    if set(value) != {
        "schema", "operation", "profile", "toolReleaseId", "manifestSha256",
        "acceptedBaselineDigest", "completeDigestSha256", "validation", "snapshot",
    }:
        raise SnapshotError("TRUSTED_SNAPSHOT_SCHEMA")
    if value["toolReleaseId"] != EXPECTED_RELEASE or value["manifestSha256"] != EXPECTED_RELEASE:
        raise SnapshotError("TRUSTED_SNAPSHOT_RELEASE_MISMATCH")
    if (value["schema"] != "BrokerCandidateDevSnapshotV1" or
            value["operation"] != "SNAPSHOT_ACCEPTED_STAGE2" or
            value["profile"] != lifecycle.POST_STAGE_II_ACCEPTED_V1 or
            value["acceptedBaselineDigest"] != ACCEPTED_DIGEST or
            value["validation"] != "PASS" or not isinstance(value["snapshot"], dict)):
        raise SnapshotError("TRUSTED_SNAPSHOT_RESULT")
    snapshot = value["snapshot"]
    try:
        lifecycle.validate_accepted(snapshot)
        baseline = snapshot["stage2AcceptedBaseline"]["stage2AcceptedBaselineDigest"]
        service = snapshot["units"][lifecycle.SERVICE]
        api = snapshot["api"]
        if (baseline != ACCEPTED_DIGEST or snapshot["release"]["candidateSha"] != ACCEPTED_BROKER_RELEASE or
                service["MainPID"] != BROKER_PID or api["MainPID"] != API_PID or
                api["NRestarts"] != "0" or api["health"] != {"status": "ok", "database": True}):
            raise SnapshotError("ACCEPTED_DEV_PREFLIGHT")
    except (KeyError, TypeError, ValueError, lifecycle.LifecycleError) as exc:
        raise SnapshotError("ACCEPTED_DEV_PREFLIGHT") from exc
    digest = hashlib.sha256(canonical(snapshot)).hexdigest()
    if value["completeDigestSha256"] != digest:
        raise SnapshotError("TRUSTED_SNAPSHOT_DIGEST")
    return {
        "snapshotSha256": digest,
        "toolReleaseId": EXPECTED_RELEASE,
        "acceptedBaselineDigest": ACCEPTED_DIGEST,
        "brokerPid": BROKER_PID,
        "apiPid": API_PID,
        "brokerInvocationId": service["InvocationID"],
    }


def capture() -> dict:
    instance = json.loads(_gcloud("instances", "describe", INSTANCE, "--format=json"))
    if (instance.get("name"), str(instance.get("id")), instance.get("status")) != (
            INSTANCE, INSTANCE_ID, "RUNNING"):
        raise SnapshotError("DEV_INSTANCE_IDENTITY")
    remote = _gcloud(
        "ssh", INSTANCE, "--tunnel-through-iap", "--ssh-flag=-T",
        "--command=" + invocation.ssh_command(),
    )
    return validate_result(decode_frame(remote))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase", choices=("preflight", "postflight"), required=True)
    parser.add_argument("--expected-snapshot-sha")
    args = parser.parse_args()
    if args.phase == "preflight" and args.expected_snapshot_sha is not None:
        raise SnapshotError("UNEXPECTED_PRE_SNAPSHOT_IDENTITY")
    if args.phase == "postflight" and (args.expected_snapshot_sha is None or
            not SHA64.fullmatch(args.expected_snapshot_sha)):
        raise SnapshotError("EXPECTED_POST_SNAPSHOT_IDENTITY")
    result = capture()
    if args.expected_snapshot_sha is not None and result["snapshotSha256"] != args.expected_snapshot_sha:
        raise SnapshotError("DEV_STATE_CHANGED_DURING_BROKER_CANDIDATE_VALIDATION")
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))


if __name__ == "__main__":
    main()
