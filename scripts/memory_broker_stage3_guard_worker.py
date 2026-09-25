#!/usr/bin/env python3
"""One-shot, non-restarting Linux pidfd guard for the DEV A2 controller.

This worker has no service-control API. systemd's BindsTo=/After= dependencies
on both the broker service and socket perform containment if this worker exits.
It is written to a root-only runtime path from reviewed source, never imported
by or packaged into the broker candidate.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import select
import socket
import stat
import sys


CONFIG = Path("/run/lilith-stage3-a2/guard.json")
CLAIM = Path("/var/lib/.lilith-memory-broker-stage3-a2/guard.claim.json")
JOURNAL = Path("/var/lib/.lilith-memory-broker-stage3-a2/004-BINDINGS_SWITCHED.json")
DEV_CONFIG = Path("/etc/lilith-memory-broker/dev.json")
SELECTOR = Path("/opt/lilith-memory-broker/current")
PROJECT = "lilith-agent-260823-27389"
ZONE = "asia-southeast1-b"
INSTANCE = "lilith-dev-01"
INSTANCE_ID = "7687007163730582258"
HOSTNAME = f"{INSTANCE}.{ZONE}.c.{PROJECT}.internal"
MACHINE_ID = "ae929170e6fa4c8ab9cc7b9547238d9d"
ACCEPTED = "817a83e44cec8965479fd97fc30b7a0b3ae49ab2"
CANDIDATE = "4a04f2d09a2b32aecedfe777090fd2e1a27ec909"
BASELINE = "abc33ebf8d43e8805f43ff11e663a4757bf558d9b62eda9669dabecbb7c9839a"
HEX32 = re.compile(r"[0-9a-f]{32}\Z")
HEX64 = re.compile(r"[0-9a-f]{64}\Z")


class GuardError(RuntimeError):
    pass


def require(ok: bool, code: str) -> None:
    if not ok:
        raise GuardError(code)


def canonical(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":"),
                       ensure_ascii=False) + "\n").encode()


def owned_bytes(path: Path, *, mode: int, gid: int = 0,
                limit: int = 8192) -> bytes:
    info = path.lstat()
    require(stat.S_ISREG(info.st_mode) and info.st_uid == 0 and info.st_gid == gid and
            stat.S_IMODE(info.st_mode) == mode and info.st_nlink == 1 and
            0 < info.st_size <= limit, "GUARD_FILE_CUSTODY")
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC)
    try:
        opened = os.fstat(fd)
        require((opened.st_dev, opened.st_ino) == (info.st_dev, info.st_ino),
                "GUARD_FILE_REPLACED")
        raw = os.read(fd, limit + 1)
        require(len(raw) == opened.st_size, "GUARD_FILE_SIZE")
        return raw
    finally:
        os.close(fd)


def process_identity(pid: int) -> tuple[str, int]:
    raw = (Path("/proc") / str(pid) / "stat").read_text(encoding="ascii")
    fields = raw.rsplit(") ", 1)[1].split()
    require(len(fields) > 19, "GUARD_CONTROLLER_STAT")
    boot = Path("/proc/sys/kernel/random/boot_id").read_text(
        encoding="ascii").strip()
    return boot, int(fields[19])


def validate_config(value: dict) -> None:
    require(isinstance(value, dict) and set(value) == {
        "schema", "project", "zone", "instanceId", "hostname", "machineId",
        "acceptedRelease", "candidateRelease", "acceptedBaselineDigest",
        "authorityMode", "canonicalCapability", "experimentId",
        "controllerPid", "controllerBootId", "controllerStartTicks",
        "authorizationId", "nonce"} and
        value["schema"] == "Stage3A2LivenessGuardV1" and
        value["project"] == PROJECT and value["zone"] == ZONE and
        value["instanceId"] == INSTANCE_ID and value["hostname"] == HOSTNAME and
        value["machineId"] == MACHINE_ID and
        value["acceptedRelease"] == ACCEPTED and
        value["candidateRelease"] == CANDIDATE and
        value["acceptedBaselineDigest"] == BASELINE and
        value["authorityMode"] == "SYNTHETIC_ONLY" and
        value["canonicalCapability"] == "DISABLED" and
        value["experimentId"] == "B1B2B_III_A_A2_V1" and
        type(value["controllerPid"]) is int and value["controllerPid"] > 1 and
        type(value["controllerStartTicks"]) is int and
        value["controllerStartTicks"] > 0 and
        isinstance(value["controllerBootId"], str) and
        re.fullmatch(r"[0-9a-f-]{36}", value["controllerBootId"]) is not None and
        isinstance(value["authorizationId"], str) and
        HEX32.fullmatch(value["authorizationId"]) is not None and
        isinstance(value["nonce"], str) and HEX64.fullmatch(value["nonce"]) is not None,
        "GUARD_CLOSED_CONFIG")


def read_config() -> dict:
    require(os.name == "posix" and os.geteuid() == 0 and
            hasattr(os, "pidfd_open") and
            socket.gethostname() in (INSTANCE, HOSTNAME) and
            Path("/etc/machine-id").read_text(encoding="ascii").strip() == MACHINE_ID,
            "GUARD_DEV_ROOT_LINUX_ONLY")
    directory = CONFIG.parent.lstat()
    require(stat.S_ISDIR(directory.st_mode) and directory.st_uid ==
            directory.st_gid == 0 and stat.S_IMODE(directory.st_mode) == 0o700,
            "GUARD_RUNTIME_DIR_CUSTODY")
    raw = owned_bytes(CONFIG, mode=0o600)
    value = json.loads(raw)
    require(raw == canonical(value), "GUARD_CONFIG_NOT_CANONICAL")
    validate_config(value)
    return value


def validate_context(value: dict) -> None:
    require(not os.path.lexists(CLAIM) and
            os.readlink(SELECTOR) == f"releases/{CANDIDATE}",
            "GUARD_ALREADY_CLAIMED_OR_SELECTOR")
    config_raw = owned_bytes(DEV_CONFIG, mode=0o640, gid=987)
    config = json.loads(config_raw)
    require(config.get("deploymentEnvironment") == "dev" and
            config.get("authorityMode") == "SYNTHETIC_ONLY" and
            config.get("canonicalCapability") == "DISABLED" and
            config.get("stateProfile") == "B1B2_SYNTHETIC_DEV_V1" and
            config.get("releaseSha") == CANDIDATE,
            "GUARD_DEV_CONFIG")
    journal = json.loads(owned_bytes(JOURNAL, mode=0o600))
    require(journal.get("schema") == "Stage3A2TransitionJournalV1" and
            journal.get("phase") == "BINDINGS_SWITCHED" and
            journal.get("record", {}).get("candidateConfigSha256") ==
                hashlib.sha256(config_raw).hexdigest(),
            "GUARD_JOURNAL_PHASE_OR_CONFIG")
    intent = json.loads(owned_bytes(JOURNAL.with_name("000-INTENT.json"),
                                    mode=0o600))["record"]
    require(intent.get("authorizationId") == value["authorizationId"] and
            intent.get("candidateRelease") == CANDIDATE and
            intent.get("acceptedRelease") == ACCEPTED,
            "GUARD_JOURNAL_AUTHORIZATION")


def claim_once(value: dict) -> None:
    raw = canonical({"schema": "Stage3A2GuardClaimV1",
                     "authorizationId": value["authorizationId"],
                     "controllerPid": value["controllerPid"],
                     "controllerBootId": value["controllerBootId"],
                     "controllerStartTicks": value["controllerStartTicks"],
                     "nonce": value["nonce"]})
    fd = os.open(CLAIM, os.O_WRONLY | os.O_CREAT | os.O_EXCL |
                 os.O_NOFOLLOW | os.O_CLOEXEC, 0o600)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "wb", closefd=False) as stream:
            stream.write(raw)
            stream.flush()
        os.fsync(fd)
    finally:
        os.close(fd)
    parent = os.open(CLAIM.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        os.fsync(parent)
    finally:
        os.close(parent)


def notify_ready() -> None:
    target = os.environ.get("NOTIFY_SOCKET", "")
    require(target.startswith(("/", "@")) and len(target) < 108,
            "GUARD_NOTIFY_SOCKET_MISSING")
    address = "\0" + target[1:] if target.startswith("@") else target
    with socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM | socket.SOCK_CLOEXEC) as conn:
        conn.sendto(b"READY=1\nSTATUS=Stage-III A2 controller pidfd bound", address)


def run() -> None:
    require(sys.argv[1:] == ["--run"], "GUARD_FIXED_COMMAND_ONLY")
    value = read_config()
    validate_context(value)
    pid = value["controllerPid"]
    descriptor = os.pidfd_open(pid, 0)
    try:
        require(process_identity(pid) ==
                (value["controllerBootId"], value["controllerStartTicks"]),
                "GUARD_CONTROLLER_INCARNATION")
        polling = select.poll()
        polling.register(descriptor, select.POLLIN | select.POLLHUP | select.POLLERR)
        require(not polling.poll(0), "GUARD_CONTROLLER_ALREADY_DEAD")
        claim_once(value)
        require(not polling.poll(0), "GUARD_CONTROLLER_DIED_BEFORE_READY")
        notify_ready()
        polling.poll()  # A kernel pidfd event, not a Python heartbeat or PID reuse check.
        raise GuardError("GUARD_CONTROLLER_EXITED")
    finally:
        os.close(descriptor)


if __name__ == "__main__":
    try:
        run()
    except (GuardError, OSError, ValueError, KeyError, TypeError, IndexError) as exc:
        print("STAGE3_GUARD_TERMINAL:" + str(exc), file=sys.stderr)
        raise SystemExit(1) from None
