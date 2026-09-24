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
import sys
import zlib
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
MAX_COMPRESSED_BYTES = 36 * 1024
MAX_ENCODED_BYTES = 48 * 1024
MAX_REMOTE_COMMAND_BYTES = 48 * 1024
SOURCE_SHA = re.compile(r"[0-9a-f]{64}\Z")
SNAPSHOT_FRAME = b"LILITH_TRUSTED_SNAPSHOT_V1:"
PUBLISH_FRAME = b"LILITH_TRUSTED_PUBLISH_V1:"
PACKED_ALPHABET = re.compile(rb"[A-Za-z0-9_-]+={0,2}\Z")

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
import json
import zlib

path, action, size_text, expected_sha, *payload_args = sys.argv[1:]
if not re.fullmatch(__STAGING_REGEX__, path) or os.path.dirname(path) != "/tmp":
    raise SystemExit("REMOTE_STAGING_PATH")
if not re.fullmatch(r"[1-9][0-9]{0,6}", size_text) or not re.fullmatch(r"[0-9a-f]{64}", expected_sha):
    raise SystemExit("REMOTE_SOURCE_IDENTITY")
source_size = int(size_text)
if source_size > 524288:
    raise SystemExit("REMOTE_SOURCE_SIZE")
if action != "publish" and payload_args:
    raise SystemExit("REMOTE_PACKED_ARGUMENTS")
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
elif action == "publish":
    directory()
    if os.listdir(path):
        raise SystemExit("REMOTE_STAGING_CONTENTS")
    if len(payload_args) != 2:
        raise SystemExit("REMOTE_PACKED_ARGUMENTS")
    compressed_size_text, packed = payload_args
    if not re.fullmatch(r"[1-9][0-9]{0,4}", compressed_size_text):
        raise SystemExit("REMOTE_PACKED_SIZE")
    if not re.fullmatch(r"[A-Za-z0-9_-]+={0,2}", packed) or len(packed) > 49152:
        raise SystemExit("REMOTE_PACKED_ALPHABET")
    try:
        compressed = base64.b64decode(packed, altchars=b"-_", validate=True)
        if len(compressed) != int(compressed_size_text) or len(compressed) > 36864:
            raise ValueError("packed size")
        inflater = zlib.decompressobj()
        content = inflater.decompress(compressed, source_size + 1)
        if (len(content) != source_size or not inflater.eof or inflater.unused_data or
                inflater.unconsumed_tail or inflater.flush()):
            raise ValueError("packed stream")
    except (ValueError, zlib.error) as exc:
        raise SystemExit("REMOTE_PACKED_DECODE") from None
    if hashlib.sha256(content).hexdigest() != expected_sha:
        raise SystemExit("REMOTE_SOURCE_HASH_MISMATCH")
    part = os.path.join(path, "lifecycle.py.part")
    final = os.path.join(path, "lifecycle.py")
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC
    fd = os.open(part, flags, 0o600)
    with os.fdopen(fd, "wb") as target:
        target.write(content)
        target.flush()
        os.fsync(target.fileno())
    info = file_info("lifecycle.py.part", {0o600})
    if info.st_size != source_size:
        raise SystemExit("REMOTE_SOURCE_SIZE_MISMATCH")
    with open(part, "rb") as written:
        if hashlib.sha256(written.read(source_size + 1)).hexdigest() != expected_sha:
            raise SystemExit("REMOTE_SOURCE_HASH_MISMATCH")
    if os.path.lexists(final):
        raise SystemExit("REMOTE_FINAL_EXISTS")
    os.rename(part, final)
    final_info = file_info("lifecycle.py", {0o600})
    if final_info.st_size != source_size:
        raise SystemExit("REMOTE_FINAL_SIZE_MISMATCH")
    with open(final, "rb") as published:
        if hashlib.sha256(published.read(source_size + 1)).hexdigest() != expected_sha:
            raise SystemExit("REMOTE_FINAL_HASH_MISMATCH")
    directory_fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC)
    try:
        os.fsync(directory_fd)
    finally:
        os.close(directory_fd)
    print("LILITH_TRUSTED_PUBLISH_V1:" + json.dumps({
        "schemaVersion": 1, "action": "TRUSTED_PAYLOAD_PUBLISH",
        "rawSize": source_size, "sha256": expected_sha, "result": "OK",
    }, sort_keys=True, separators=(",", ":")))
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
elif action in {"cleanup_empty", "cleanup_part", "cleanup_publish_uncertain", "cleanup_full"}:
    directory()
    names = os.listdir(path)
    allowed = {"cleanup_empty": set(),
                "cleanup_part": {"lifecycle.py.part"},
                "cleanup_publish_uncertain": {"lifecycle.py.part", "lifecycle.py"},
                "cleanup_full": {"lifecycle.py", "snapshot.json"}}[action]
    if not set(names) <= allowed:
        raise SystemExit("REMOTE_STAGING_UNEXPECTED_CONTENTS")
    if action == "cleanup_publish_uncertain" and len(names) > 1:
        raise SystemExit("REMOTE_STAGING_UNEXPECTED_CONTENTS")
    for name in names:
        file_info(name, {0o600})
    if "lifecycle.py" in names:
        source = os.path.join(path, "lifecycle.py")
        with open(source, "rb") as trusted:
            content = trusted.read(source_size + 1)
        if len(content) != source_size or hashlib.sha256(content).hexdigest() != expected_sha:
            raise SystemExit("REMOTE_SOURCE_IDENTITY")
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


def trusted_source_bytes() -> bytes:
    # This module runs from the protected-main checkout. No candidate path or
    # caller-supplied root is accepted as a source selector.
    lifecycle = Path(__file__).with_name("verify_broker_dev_lifecycle.py")
    if not lifecycle.is_file() or lifecycle.is_symlink():
        raise SnapshotError("TRUSTED_LIFECYCLE_SOURCE")
    source = lifecycle.read_bytes()
    if not 0 < len(source) <= MAX_SOURCE_BYTES:
        raise SnapshotError("TRUSTED_SOURCE_SIZE")
    return source


def pack_source(source: bytes) -> tuple[str, int]:
    if not isinstance(source, bytes) or not 0 < len(source) <= MAX_SOURCE_BYTES:
        raise SnapshotError("TRUSTED_SOURCE_SIZE")
    compressed = zlib.compress(source, level=9)
    packed = base64.urlsafe_b64encode(compressed)
    if (not 0 < len(compressed) <= MAX_COMPRESSED_BYTES or
            not 0 < len(packed) <= MAX_ENCODED_BYTES or
            not PACKED_ALPHABET.fullmatch(packed)):
        raise SnapshotError("TRUSTED_PACKED_SIZE_OR_ALPHABET")
    return packed.decode("ascii"), len(compressed)


def publish_result(raw: bytes, source_size: int, source_sha: str) -> None:
    frames = [line[len(PUBLISH_FRAME):] for line in raw.splitlines()
              if line.startswith(PUBLISH_FRAME)]
    if len(frames) != 1 or len(frames[0]) > 512:
        raise SnapshotError("TRUSTED_PUBLISH_FRAME")
    try:
        result = json.loads(frames[0])
    except (UnicodeError, json.JSONDecodeError):
        raise SnapshotError("TRUSTED_PUBLISH_FRAME") from None
    if result != {"schemaVersion": 1, "action": "TRUSTED_PAYLOAD_PUBLISH",
                  "rawSize": source_size, "sha256": source_sha, "result": "OK"}:
        raise SnapshotError("TRUSTED_PUBLISH_RESULT")


def remote_action(path: str, action: str, source_size: int, source_sha: str,
                  *, source_bytes: bytes = b"") -> bytes:
    path = validate_staging_path(path)
    if action not in {"create", "publish", "snapshot", "read",
                      "cleanup_empty", "cleanup_part", "cleanup_publish_uncertain", "cleanup_full"}:
        raise SnapshotError("REMOTE_STAGING_ACTION")
    if (not isinstance(source_size, int) or not 0 < source_size <= MAX_SOURCE_BYTES or
            not isinstance(source_sha, str) or not SOURCE_SHA.fullmatch(source_sha) or
            (action == "publish" and
             (len(source_bytes) != source_size or hashlib.sha256(source_bytes).hexdigest() != source_sha)) or
            (action != "publish" and source_bytes)):
        raise SnapshotError("TRUSTED_SOURCE_IDENTITY")
    # The decoder is fixed protected-main code, compressed only to keep the
    # complete command well below process argument limits. Candidate bytes
    # cannot select either decoder or packed lifecycle source.
    encoded = base64.urlsafe_b64encode(zlib.compress(_REMOTE_SOURCE.encode("utf-8"), 9)).decode("ascii")
    remote_command = (
        "/usr/bin/python3 -B -c 'import base64,zlib;exec(zlib.decompress(base64.urlsafe_b64decode(\""
        + encoded + "\")))' " + shlex.quote(path) + " " + action +
        " " + str(source_size) + " " + source_sha
    )
    compressed_size = 0
    encoded_size = 0
    if action == "publish":
        packed, compressed_size = pack_source(source_bytes)
        encoded_size = len(packed)
        remote_command += " " + str(compressed_size) + " " + packed
    command_size = len(remote_command.encode("ascii"))
    if command_size > MAX_REMOTE_COMMAND_BYTES:
        raise SnapshotError("TRUSTED_COMMAND_SIZE")
    args = ("gcloud", "compute", "ssh", INSTANCE, "--tunnel-through-iap", "--ssh-flag=-T",
            f"--command={remote_command}", "--quiet", f"--project={PROJECT}", f"--zone={ZONE}")
    try:
        result = subprocess.run(args, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, timeout=120)
    except subprocess.TimeoutExpired:
        # TimeoutExpired includes the full command, including packed source.
        raise SnapshotError(f"TRUSTED_SSH_TIMEOUT action={action} path={path}") from None
    except OSError:
        # OS process-creation exceptions can also contain the packed argv.
        raise SnapshotError(f"TRUSTED_SSH_INVOCATION action={action} path={path}") from None
    if result.returncode != 0:
        reason = re.search(rb"\bREMOTE_[A-Z0-9_]+\b", result.stderr[:8192])
        label = reason.group().decode("ascii") if reason else "TRANSPORT_OR_PROCESS"
        raise SnapshotError(f"TRUSTED_SSH_EXIT action={action} code={result.returncode} reason={label} path={path}")
    if len(result.stdout) > MAX_SNAPSHOT_BYTES * 2:
        raise SnapshotError(f"TRUSTED_SSH_OUTPUT_SIZE action={action}")
    if action == "publish":
        publish_result(result.stdout, source_size, source_sha)
        print(json.dumps({"transportAction": "publish", "rawSize": source_size,
                          "compressedSize": compressed_size, "encodedSize": encoded_size,
                          "remoteCommandSize": command_size, "rawSha256": source_sha,
                          "result": "OK"}, sort_keys=True), file=sys.stderr)
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
    source_bytes = trusted_source_bytes()
    source_sha = hashlib.sha256(source_bytes).hexdigest()
    source_size = len(source_bytes)
    try:
        remote_action(directory, "create", source_size, source_sha)
    except Exception as exc:
        # Creation may have occurred before transport failure. Do not delete a
        # possibly pre-existing path; report exact run-bound residue for audit.
        raise SnapshotError(f"REMOTE_STAGING_CREATE_UNCERTAIN path={directory}") from exc
    cleanup_action = "cleanup_empty"
    try:
        try:
            cleanup_action = "cleanup_publish_uncertain"
            remote_action(directory, "publish", source_size, source_sha, source_bytes=source_bytes)
        except SnapshotError as exc:
            if ("reason=REMOTE_STAGING_CONTENTS" in str(exc) or
                    "TRUSTED_SOURCE_IDENTITY" in str(exc) or
                    "TRUSTED_PACKED_SIZE_OR_ALPHABET" in str(exc) or
                    "TRUSTED_COMMAND_SIZE" in str(exc)):
                cleanup_action = "cleanup_empty"
            raise
        cleanup_action = "cleanup_full"
        remote_action(directory, "snapshot", source_size, source_sha)
        snapshot = decode_snapshot_frame(remote_action(directory, "read", source_size, source_sha))
    finally:
        try:
            remote_action(directory, cleanup_action, source_size, source_sha)
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
