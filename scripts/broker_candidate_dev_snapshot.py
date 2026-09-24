#!/usr/bin/env python3
"""Trusted-main read-only DEV snapshot for the broker-only required-check lane.

Candidate code never runs here or on the VM. The only remote staging is this
trusted lifecycle source in a bounded temporary directory, removed afterward.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path


PROJECT = "lilith-agent-260823-27389"
ZONE = "asia-southeast1-b"
INSTANCE = "lilith-dev-01"
INSTANCE_ID = "7687007163730582258"
ACCEPTED_PROFILE = "POST_STAGE_II_ACCEPTED_V1"
ACCEPTED_DIGEST = "abc33ebf8d43e8805f43ff11e663a4757bf558d9b62eda9669dabecbb7c9839a"
ACCEPTED_RELEASE = "817a83e44cec8965479fd97fc30b7a0b3ae49ab2"
ACCEPTED_API_PID = "88740"
ACCEPTED_BROKER_PID = "96650"
TEMP_PATTERN = re.compile(r"/tmp/lilith-broker-candidate-lifecycle-[A-Za-z0-9]{8}\Z")


class SnapshotError(RuntimeError):
    pass


def command(*args: str) -> str:
    return subprocess.run(args, check=True, capture_output=True, text=True, timeout=120).stdout.strip()


def gcloud(*args: str) -> str:
    return command("gcloud", "compute", *args, "--quiet", f"--project={PROJECT}", f"--zone={ZONE}")


def capture() -> dict:
    instance = json.loads(gcloud("instances", "describe", INSTANCE, "--format=json"))
    if (instance.get("name"), str(instance.get("id")), instance.get("status")) != (
        INSTANCE, INSTANCE_ID, "RUNNING"
    ):
        raise SnapshotError("DEV_INSTANCE_IDENTITY")
    directory = gcloud("ssh", INSTANCE, "--tunnel-through-iap",
                       "--command=umask 077; mktemp -d /tmp/lilith-broker-candidate-lifecycle-XXXXXXXX")
    if not TEMP_PATTERN.fullmatch(directory):
        raise SnapshotError("REMOTE_STAGING_PATH")
    lifecycle = Path(__file__).with_name("verify_broker_dev_lifecycle.py")
    if not lifecycle.is_file() or lifecycle.is_symlink():
        raise SnapshotError("TRUSTED_LIFECYCLE_SOURCE")
    failure = None
    try:
        gcloud("scp", "--tunnel-through-iap", str(lifecycle), f"{INSTANCE}:{directory}/lifecycle.py")
        raw = gcloud("ssh", INSTANCE, "--tunnel-through-iap",
                     f"--command=sudo -n /usr/bin/python3 -B '{directory}/lifecycle.py' snapshot")
        snapshot = json.loads(raw)
    except Exception as exc:
        failure = exc
        raise
    finally:
        try:
            gcloud("ssh", INSTANCE, "--tunnel-through-iap",
                   f"--command=rm -f -- '{directory}/lifecycle.py'; rmdir -- '{directory}'")
        except Exception as exc:
            if failure is None:
                raise SnapshotError("REMOTE_STAGING_CLEANUP") from exc
    return snapshot


def summarize(snapshot: dict) -> dict:
    baseline = snapshot.get("stage2AcceptedBaseline", {})
    release = snapshot.get("release", {})
    units = snapshot.get("units", {})
    service = units.get("lilith-memory-broker.service", {})
    broker_socket = units.get("lilith-memory-broker.socket", {})
    api = snapshot.get("api", {})
    incarnations = snapshot.get("runtimeIncarnations", {})
    if (snapshot.get("profile") != ACCEPTED_PROFILE
            or baseline.get("stage2AcceptedBaselineDigest") != ACCEPTED_DIGEST
            or release.get("candidateSha") != ACCEPTED_RELEASE
            or service.get("ActiveState") != "active"
            or service.get("MainPID") != ACCEPTED_BROKER_PID
            or broker_socket.get("ActiveState") != "active"
            or snapshot.get("ownerSocket", {}).get("listening") is not True
            or api.get("health") != {"status": "ok", "database": True}
            or api.get("MainPID") != ACCEPTED_API_PID
            or incarnations.get("broker", {}).get("pid") != int(service.get("MainPID", "0"))
            or incarnations.get("api", {}).get("pid") != int(api.get("MainPID", "0"))
            or any(not item.get("bootId") or not isinstance(item.get("startTicks"), int)
                   or item["startTicks"] <= 0 for item in incarnations.values())
            or set(incarnations) != {"broker", "api"}):
        raise SnapshotError("ACCEPTED_DEV_PREFLIGHT")
    encoded = json.dumps(snapshot, sort_keys=True, separators=(",", ":")).encode("utf-8")
    files = {key.replace("\\", "/"): value for key, value in snapshot["files"].items()}
    return {
        "snapshotSha256": hashlib.sha256(encoded).hexdigest(),
        "acceptedBaselineDigest": ACCEPTED_DIGEST,
        "installedReleaseSha": ACCEPTED_RELEASE,
        "brokerPid": service["MainPID"],
        "brokerInvocationId": service["InvocationID"],
        "brokerStartTicks": incarnations["broker"]["startTicks"],
        "apiPid": api["MainPID"],
        "apiStartTicks": incarnations["api"]["startTicks"],
        "ownerDbSha256": files["/var/lib/lilith-memory-broker/owner-control/owner_control.db"]["sha256"],
        "evidenceDbSha256": files["/var/lib/lilith-memory-broker/state/synthetic_evidence.db"]["sha256"],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--expected-snapshot-sha", default=None)
    args = parser.parse_args()
    result = summarize(capture())
    if args.expected_snapshot_sha is not None and result["snapshotSha256"] != args.expected_snapshot_sha:
        raise SnapshotError("DEV_STATE_CHANGED_DURING_BROKER_CANDIDATE_VALIDATION")
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))


if __name__ == "__main__":
    main()
