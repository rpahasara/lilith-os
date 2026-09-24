#!/usr/bin/env python3
"""Installed fixed-purpose, read-only accepted DEV lifecycle snapshot CLI."""

from __future__ import annotations

import base64
import hashlib
import importlib.util
import json
import os
import re
import sqlite3
import stat
import sys
from pathlib import Path


CONTROL = Path("/opt/lilith-trusted-controls/broker-snapshot")
FRAME = b"LILITH_BROKER_CANDIDATE_DEV_SNAPSHOT_V1:"
OPERATION = "SNAPSHOT_ACCEPTED_STAGE2"
PROFILE = "POST_STAGE_II_ACCEPTED_V1"
SCHEMA = "BrokerCandidateDevSnapshotV1"
RELEASE_SCHEMA = "TrustedBrokerSnapshotReleaseV1"
MAX_OUTPUT = 2 * 1024 * 1024
SHA64 = re.compile(r"[0-9a-f]{64}\Z")
PAYLOADS = {"bin/lilith-broker-dev-snapshot", "lib/verify_broker_dev_lifecycle.py"}
RUNTIME_KEYS = {
    "pythonExecutable", "pythonVersion", "pythonSha256", "sqliteVersion",
    "sqliteModuleSha256", "sqliteExtensionSha256", "pythonPackage", "sqlitePackage",
}


class SnapshotError(RuntimeError):
    pass


def canonical(value: dict) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _regular(path: Path, mode: int, *, root_custody: bool = True) -> bytes:
    info = path.lstat()
    if (not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or
            (root_custody and stat.S_IMODE(info.st_mode) != mode) or
            (root_custody and (info.st_uid, info.st_gid) != (0, 0))):
        raise SnapshotError("SNAPSHOT_RELEASE_CUSTODY")
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_CLOEXEC", 0)
    fd = os.open(path, flags)
    try:
        opened = os.fstat(fd)
        if (opened.st_dev, opened.st_ino) != (info.st_dev, info.st_ino):
            raise SnapshotError("SNAPSHOT_RELEASE_RACE")
        with os.fdopen(fd, "rb", closefd=False) as stream:
            content = stream.read(512 * 1024 + 1)
    finally:
        os.close(fd)
    if len(content) > 512 * 1024 or len(content) != opened.st_size:
        raise SnapshotError("SNAPSHOT_RELEASE_SIZE")
    return content


def _directory(path: Path, *, root_custody: bool = True) -> None:
    info = path.lstat()
    if (not stat.S_ISDIR(info.st_mode) or
            (root_custody and stat.S_IMODE(info.st_mode) != 0o755) or
            (root_custody and (info.st_uid, info.st_gid) != (0, 0))):
        raise SnapshotError("SNAPSHOT_RELEASE_CUSTODY")


def verify_release(release_dir: Path, *, root_custody: bool = True) -> tuple[str, dict]:
    _directory(release_dir, root_custody=root_custody)
    for name in ("bin", "lib"):
        _directory(release_dir / name, root_custody=root_custody)
    expected = {"release-manifest.json", "bin", "lib"}
    if {p.name for p in release_dir.iterdir()} != expected:
        raise SnapshotError("SNAPSHOT_RELEASE_FILE_SET")
    if {p.name for p in (release_dir / "bin").iterdir()} != {"lilith-broker-dev-snapshot"} or \
            {p.name for p in (release_dir / "lib").iterdir()} != {"verify_broker_dev_lifecycle.py"}:
        raise SnapshotError("SNAPSHOT_RELEASE_FILE_SET")
    manifest_bytes = _regular(release_dir / "release-manifest.json", 0o644, root_custody=root_custody)
    try:
        manifest = json.loads(manifest_bytes)
    except (ValueError, UnicodeError) as exc:
        raise SnapshotError("SNAPSHOT_MANIFEST_JSON") from exc
    release_id = digest(manifest_bytes)
    if not SHA64.fullmatch(release_dir.name) or release_dir.name != release_id:
        raise SnapshotError("SNAPSHOT_MANIFEST_IDENTITY")
    if (manifest_bytes != canonical(manifest) + b"\n" or set(manifest) !=
            {"schema", "operation", "lifecycleProfile", "outputSchema", "runtime", "payloads"} or
            manifest["schema"] != RELEASE_SCHEMA or manifest["operation"] != OPERATION or
            manifest["lifecycleProfile"] != PROFILE or manifest["outputSchema"] != SCHEMA or
            not isinstance(manifest["runtime"], dict) or set(manifest["runtime"]) != RUNTIME_KEYS or
            not isinstance(manifest["payloads"], list) or len(manifest["payloads"]) != 2):
        raise SnapshotError("SNAPSHOT_MANIFEST_SCHEMA")
    actual = []
    for path in sorted(PAYLOADS):
        content = _regular(release_dir / path, 0o755 if path.startswith("bin/") else 0o644,
                           root_custody=root_custody)
        actual.append({"path": path, "size": len(content), "sha256": digest(content)})
    if manifest["payloads"] != actual:
        raise SnapshotError("SNAPSHOT_PAYLOAD_HASH")
    return release_id, manifest


def verify_runtime(runtime: dict) -> None:
    import _sqlite3
    python = Path(runtime["pythonExecutable"])
    if (str(python) != "/usr/bin/python3" or Path(sys.executable).resolve() != python.resolve() or
            ".".join(map(str, sys.version_info[:3])) != runtime["pythonVersion"] or
            sqlite3.sqlite_version != runtime["sqliteVersion"] or
            digest(python.read_bytes()) != runtime["pythonSha256"] or
            digest(Path(sqlite3.__file__).read_bytes()) != runtime["sqliteModuleSha256"] or
            digest(Path(_sqlite3.__file__).read_bytes()) != runtime["sqliteExtensionSha256"]):
        raise SnapshotError("SNAPSHOT_RUNTIME_MISMATCH")


def verify_confinement() -> None:
    if os.name != "posix" or os.geteuid() != 0:
        raise SnapshotError("SNAPSHOT_ROOT_REQUIRED")
    for path in ("/", "/etc", "/opt", "/var/lib", "/home", "/run"):
        if not os.statvfs(path).f_flag & os.ST_RDONLY:
            raise SnapshotError("SNAPSHOT_WRITABLE_HOST_PATH:" + path)
    status = Path("/proc/self/status").read_text(encoding="ascii")
    fields = dict(line.split(":", 1) for line in status.splitlines() if ":" in line)
    if fields.get("NoNewPrivs", "").strip() != "1":
        raise SnapshotError("SNAPSHOT_PRIVILEGE_REGAIN")
    # CAP_DAC_READ_SEARCH (bit 2) is needed for broker-owned mode-0600 DBs;
    # no effective capability that grants writes is permitted.
    if int(fields.get("CapEff", "-1").strip(), 16) & ~0x4:
        raise SnapshotError("SNAPSHOT_EXCESS_CAPABILITIES")


def _lifecycle(release_dir: Path):
    path = release_dir / "lib/verify_broker_dev_lifecycle.py"
    spec = importlib.util.spec_from_file_location("trusted_broker_dev_lifecycle", path)
    if spec is None or spec.loader is None:
        raise SnapshotError("SNAPSHOT_LIFECYCLE_IMPORT")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def collect(release_dir: Path, *, enforce_host_custody: bool = True) -> dict:
    if enforce_host_custody:
        verify_confinement()
    release_id, manifest = verify_release(release_dir, root_custody=enforce_host_custody)
    if enforce_host_custody:
        verify_runtime(manifest["runtime"])
    lifecycle = _lifecycle(release_dir)
    if enforce_host_custody and lifecycle._host() != lifecycle.expected_host():
        raise SnapshotError("SNAPSHOT_DEV_HOST_ONLY")
    snapshot = lifecycle.collect_accepted()
    lifecycle.validate_accepted(snapshot)
    snapshot_bytes = canonical(snapshot)
    if len(snapshot_bytes) > MAX_OUTPUT // 2:
        raise SnapshotError("SNAPSHOT_OUTPUT_SIZE")
    baseline = snapshot["stage2AcceptedBaseline"]["stage2AcceptedBaselineDigest"]
    result = {
        "schema": SCHEMA,
        "operation": OPERATION,
        "profile": PROFILE,
        "toolReleaseId": release_id,
        "manifestSha256": release_id,
        "acceptedBaselineDigest": baseline,
        "completeDigestSha256": digest(snapshot_bytes),
        "validation": "PASS",
        "snapshot": snapshot,
    }
    if snapshot.get("profile") != PROFILE:
        raise SnapshotError("SNAPSHOT_PROFILE")
    return result


def frame(result: dict) -> bytes:
    data = canonical(result)
    if not data or len(data) > MAX_OUTPUT:
        raise SnapshotError("SNAPSHOT_OUTPUT_SIZE")
    return FRAME + str(len(data)).encode() + b":" + digest(data).encode() + b":" + base64.b64encode(data) + b"\n"


def main() -> None:
    if sys.argv[1:] != [OPERATION]:
        raise SnapshotError("FIXED_SNAPSHOT_OPERATION_ONLY")
    selector = CONTROL / "current"
    info = selector.lstat()
    if not stat.S_ISLNK(info.st_mode) or (info.st_uid, info.st_gid) != (0, 0):
        raise SnapshotError("SNAPSHOT_SELECTOR_CUSTODY")
    target = os.readlink(selector)
    if not re.fullmatch(r"releases/[0-9a-f]{64}", target):
        raise SnapshotError("SNAPSHOT_SELECTOR_TARGET")
    for path in (CONTROL.parent, CONTROL, CONTROL / "releases"):
        _directory(path)
    release_dir = CONTROL / target
    if Path(__file__).resolve() != release_dir / "bin/lilith-broker-dev-snapshot":
        raise SnapshotError("SNAPSHOT_EXECUTABLE_NOT_SELECTED")
    sys.stdout.buffer.write(frame(collect(release_dir)))


if __name__ == "__main__":
    main()
