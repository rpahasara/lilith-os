#!/usr/bin/env python3
"""Trusted-main read-only DEV snapshot for the broker-only required-check lane.

Candidate code never runs here or on the VM. The only remote staging is this
trusted lifecycle source in a bounded temporary directory, removed afterward.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import re
import shlex
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
STAGING_PATTERN = re.compile(
    r"/tmp/lilith-broker-candidate-(?:preflight|postflight)-[1-9][0-9]{0,19}-[1-9][0-9]{0,7}\Z"
)
RUN_ID = re.compile(r"[1-9][0-9]{0,19}\Z")
RUN_ATTEMPT = re.compile(r"[1-9][0-9]{0,7}\Z")
MAX_SNAPSHOT_BYTES = 2 * 1024 * 1024
MAX_SOURCE_BYTES = 512 * 1024
SOURCE_SHA = re.compile(r"[0-9a-f]{64}\Z")
SNAPSHOT_FRAME = b"LILITH_TRUSTED_SNAPSHOT_V1:"

# Executed only by protected-main code as the GitHub OS Login account. No
# candidate source, workflow input, or remote stdout chooses a path.
_REMOTE_SOURCE = r'''
import os
import base64
import hashlib
import re
import stat
import subprocess
import sys

path, action, size_text, expected_sha = sys.argv[1:]
if not re.fullmatch(__STAGING_REGEX__, path) or os.path.dirname(path) != "/tmp":
    raise SystemExit("REMOTE_STAGING_PATH")
if not re.fullmatch(r"[1-9][0-9]{0,6}", size_text) or not re.fullmatch(r"[0-9a-f]{64}", expected_sha):
    raise SystemExit("REMOTE_SOURCE_IDENTITY")
source_size = int(size_text)
if source_size > 524288:
    raise SystemExit("REMOTE_SOURCE_SIZE")
parent = os.lstat("/tmp")
if not stat.S_ISDIR(parent.st_mode) or parent.st_uid != 0 or parent.st_gid != 0 or stat.S_IMODE(parent.st_mode) != 0o1777:
    raise SystemExit("REMOTE_STAGING_PARENT")

def directory():
    info = os.lstat(path)
    if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.geteuid() or info.st_gid != os.getegid() or stat.S_IMODE(info.st_mode) != 0o700:
        raise SystemExit("REMOTE_STAGING_CUSTODY")
    return info

def file_info(name, modes):
    info = os.lstat(os.path.join(path, name))
    if not stat.S_ISREG(info.st_mode) or info.st_uid != os.geteuid() or info.st_gid != os.getegid() or stat.S_IMODE(info.st_mode) not in modes or info.st_nlink != 1:
        raise SystemExit("REMOTE_STAGING_FILE_CUSTODY")
    return info

if action == "create":
    os.mkdir(path, 0o700)  # Exclusive. Never reuse a pre-existing path.
    directory()
    if os.listdir(path):
        raise SystemExit("REMOTE_STAGING_NOT_EMPTY")
elif action == "snapshot":
    directory()
    if sorted(os.listdir(path)) != ["lifecycle.py"]:
        raise SystemExit("REMOTE_STAGING_CONTENTS")
    source = os.path.join(path, "lifecycle.py")
    file_info("lifecycle.py", {0o600})
    source_fd = os.open(source, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC)
    with os.fdopen(source_fd, "rb") as trusted:
        trusted_info = os.fstat(trusted.fileno())
        if not stat.S_ISREG(trusted_info.st_mode) or trusted_info.st_uid != os.geteuid() or trusted_info.st_gid != os.getegid() or stat.S_IMODE(trusted_info.st_mode) != 0o600 or trusted_info.st_nlink != 1:
            raise SystemExit("REMOTE_SOURCE_CUSTODY")
        content = trusted.read(source_size + 1)
    if len(content) != source_size or hashlib.sha256(content).hexdigest() != expected_sha:
        raise SystemExit("REMOTE_SOURCE_IDENTITY")
    output = os.path.join(path, "snapshot.json")
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC
    fd = os.open(output, flags, 0o600)
    with os.fdopen(fd, "wb") as target:
        subprocess.run(["sudo", "-n", "/usr/bin/python3", "-B", source, "snapshot"],
                       stdout=target, check=True, timeout=90)
        target.flush()
        os.fsync(target.fileno())
    file_info("snapshot.json", {0o600})
elif action == "upload":
    directory()
    if os.listdir(path):
        raise SystemExit("REMOTE_STAGING_CONTENTS")
    part = os.path.join(path, "lifecycle.py.part")
    final = os.path.join(path, "lifecycle.py")
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC
    fd = os.open(part, flags, 0o600)
    count = 0
    digest = hashlib.sha256()
    with os.fdopen(fd, "wb") as target:
        while True:
            chunk = sys.stdin.buffer.read(min(65536, source_size + 1 - count))
            if not chunk:
                break
            count += len(chunk)
            if count > source_size:
                raise SystemExit("REMOTE_SOURCE_SIZE_MISMATCH")
            target.write(chunk)
            digest.update(chunk)
        target.flush()
        os.fsync(target.fileno())
    info = file_info("lifecycle.py.part", {0o600})
    if count != source_size or info.st_size != source_size:
        raise SystemExit("REMOTE_SOURCE_SIZE_MISMATCH")
    if digest.hexdigest() != expected_sha:
        raise SystemExit("REMOTE_SOURCE_HASH_MISMATCH")
    if os.path.lexists(final):
        raise SystemExit("REMOTE_FINAL_EXISTS")
    os.rename(part, final)
    file_info("lifecycle.py", {0o600})
    directory_fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC)
    try:
        os.fsync(directory_fd)
    finally:
        os.close(directory_fd)
elif action == "read":
    directory()
    if sorted(os.listdir(path)) != ["lifecycle.py", "snapshot.json"]:
        raise SystemExit("REMOTE_STAGING_CONTENTS")
    file_info("lifecycle.py", {0o600})
    info = file_info("snapshot.json", {0o600})
    if not 0 < info.st_size <= 2097152:
        raise SystemExit("REMOTE_SNAPSHOT_SIZE")
    flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC
    fd = os.open(os.path.join(path, "snapshot.json"), flags)
    with os.fdopen(fd, "rb") as source:
        opened = os.fstat(source.fileno())
        if not stat.S_ISREG(opened.st_mode) or opened.st_uid != os.geteuid() or opened.st_gid != os.getegid() or stat.S_IMODE(opened.st_mode) != 0o600 or opened.st_nlink != 1:
            raise SystemExit("REMOTE_SNAPSHOT_CUSTODY")
        data = source.read(2097153)
    if len(data) != info.st_size:
        raise SystemExit("REMOTE_SNAPSHOT_SIZE")
    frame = "LILITH_TRUSTED_SNAPSHOT_V1:{}:{}:{}".format(
        len(data), hashlib.sha256(data).hexdigest(), base64.b64encode(data).decode("ascii"))
    print(frame)
elif action == "cleanup":
    directory()
    names = os.listdir(path)
    if not set(names) <= {"lifecycle.py.part", "lifecycle.py", "snapshot.json"}:
        raise SystemExit("REMOTE_STAGING_UNEXPECTED_CONTENTS")
    for name in names:
        file_info(name, {0o600})
    for name in names:
        os.unlink(os.path.join(path, name))
    os.rmdir(path)
else:
    raise SystemExit("REMOTE_STAGING_ACTION")
'''.replace("__STAGING_REGEX__", repr(STAGING_PATTERN.pattern))


class SnapshotError(RuntimeError):
    pass


def command(*args: str) -> str:
    return subprocess.run(args, check=True, capture_output=True, text=True, timeout=120).stdout.strip()


def gcloud(*args: str) -> str:
    return command("gcloud", "compute", *args, "--quiet", f"--project={PROJECT}", f"--zone={ZONE}")


def staging_path(run_id: str, run_attempt: str, phase: str) -> str:
    if (phase not in {"preflight", "postflight"} or
            not isinstance(run_id, str) or not RUN_ID.fullmatch(run_id) or
            not isinstance(run_attempt, str) or not RUN_ATTEMPT.fullmatch(run_attempt)):
        raise SnapshotError("TRUSTED_RUN_IDENTITY")
    return validate_staging_path(f"/tmp/lilith-broker-candidate-{phase}-{run_id}-{run_attempt}")


def validate_staging_path(path: str) -> str:
    if (not isinstance(path, str) or len(path) > 100 or
            not STAGING_PATTERN.fullmatch(path) or Path(path).as_posix().rsplit("/", 1)[0] != "/tmp"):
        raise SnapshotError("REMOTE_STAGING_PATH")
    return path


def remote_action(path: str, action: str, source_size: int, source_sha: str,
                  *, source_bytes: bytes = b"") -> bytes:
    path = validate_staging_path(path)
    if action not in {"create", "upload", "snapshot", "read", "cleanup"}:
        raise SnapshotError("REMOTE_STAGING_ACTION")
    if (not isinstance(source_size, int) or not 0 < source_size <= MAX_SOURCE_BYTES or
            not isinstance(source_sha, str) or not SOURCE_SHA.fullmatch(source_sha) or
            (action == "upload" and
             (len(source_bytes) != source_size or hashlib.sha256(source_bytes).hexdigest() != source_sha)) or
            (action != "upload" and source_bytes)):
        raise SnapshotError("TRUSTED_SOURCE_IDENTITY")
    encoded = base64.b64encode(_REMOTE_SOURCE.encode("utf-8")).decode("ascii")
    remote_command = (
        "/usr/bin/python3 -B -c 'import base64;exec(base64.b64decode(\""
        + encoded + "\"))' " + shlex.quote(path) + " " + action +
        " " + str(source_size) + " " + source_sha
    )
    args = ("gcloud", "compute", "ssh", INSTANCE, "--tunnel-through-iap", "--ssh-flag=-T",
            f"--command={remote_command}", "--quiet", f"--project={PROJECT}", f"--zone={ZONE}")
    try:
        result = subprocess.run(args, input=source_bytes, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, timeout=120)
    except subprocess.TimeoutExpired as exc:
        raise SnapshotError(f"TRUSTED_SSH_TIMEOUT action={action} path={path}") from exc
    if result.returncode != 0:
        reason = re.search(rb"\bREMOTE_[A-Z0-9_]+\b", result.stderr[:8192])
        label = reason.group().decode("ascii") if reason else "TRANSPORT_OR_PROCESS"
        raise SnapshotError(f"TRUSTED_SSH_EXIT action={action} code={result.returncode} reason={label} path={path}")
    if len(result.stdout) > MAX_SNAPSHOT_BYTES * 2:
        raise SnapshotError(f"TRUSTED_SSH_OUTPUT_SIZE action={action}")
    return result.stdout


def decode_snapshot_frame(raw: bytes) -> dict:
    lines = [line for line in raw.splitlines() if line.startswith(SNAPSHOT_FRAME)]
    if len(lines) != 1:
        raise SnapshotError("SNAPSHOT_FRAME_COUNT")
    try:
        size_text, digest, encoded = lines[0][len(SNAPSHOT_FRAME):].split(b":", 2)
        if not re.fullmatch(rb"[1-9][0-9]{0,6}", size_text) or not re.fullmatch(rb"[0-9a-f]{64}", digest):
            raise ValueError("invalid frame identity")
        size = int(size_text)
        if size > MAX_SNAPSHOT_BYTES:
            raise ValueError("oversized frame")
        data = base64.b64decode(encoded, validate=True)
        if len(data) != size or hashlib.sha256(data).hexdigest().encode() != digest:
            raise ValueError("frame digest mismatch")
        return json.loads(data)
    except (ValueError, UnicodeError, json.JSONDecodeError) as exc:
        raise SnapshotError("SNAPSHOT_FRAME_INVALID") from exc


def capture(run_id: str, run_attempt: str, phase: str) -> dict:
    instance = json.loads(gcloud("instances", "describe", INSTANCE, "--format=json"))
    if (instance.get("name"), str(instance.get("id")), instance.get("status")) != (
        INSTANCE, INSTANCE_ID, "RUNNING"
    ):
        raise SnapshotError("DEV_INSTANCE_IDENTITY")
    directory = staging_path(run_id, run_attempt, phase)
    lifecycle = Path(__file__).with_name("verify_broker_dev_lifecycle.py")
    if not lifecycle.is_file() or lifecycle.is_symlink():
        raise SnapshotError("TRUSTED_LIFECYCLE_SOURCE")
    source_bytes = lifecycle.read_bytes()
    if not 0 < len(source_bytes) <= MAX_SOURCE_BYTES:
        raise SnapshotError("TRUSTED_SOURCE_SIZE")
    source_sha = hashlib.sha256(source_bytes).hexdigest()
    source_size = len(source_bytes)
    try:
        remote_action(directory, "create", source_size, source_sha)
    except Exception as exc:
        # Creation may have occurred before transport failure. Do not delete a
        # possibly pre-existing path; report exact run-bound residue for audit.
        raise SnapshotError(f"REMOTE_STAGING_CREATE_UNCERTAIN path={directory}") from exc
    try:
        remote_action(directory, "upload", source_size, source_sha, source_bytes=source_bytes)
        remote_action(directory, "snapshot", source_size, source_sha)
        snapshot = decode_snapshot_frame(remote_action(directory, "read", source_size, source_sha))
    finally:
        try:
            remote_action(directory, "cleanup", source_size, source_sha)
        except Exception as exc:
            raise SnapshotError(f"REMOTE_STAGING_CLEANUP_FAILED path={directory}") from exc
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
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--run-attempt", required=True)
    parser.add_argument("--phase", choices=("preflight", "postflight"), required=True)
    args = parser.parse_args()
    result = summarize(capture(args.run_id, args.run_attempt, args.phase))
    if args.expected_snapshot_sha is not None and result["snapshotSha256"] != args.expected_snapshot_sha:
        raise SnapshotError("DEV_STATE_CHANGED_DURING_BROKER_CANDIDATE_VALIDATION")
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))


if __name__ == "__main__":
    main()
