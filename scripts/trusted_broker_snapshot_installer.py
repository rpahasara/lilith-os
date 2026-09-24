#!/usr/bin/env python3
"""First-install-only DEV installer for TrustedBrokerSnapshotReleaseV1."""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import re
import socket
import stat
import subprocess
from pathlib import Path
from urllib.request import ProxyHandler, Request, build_opener

if __package__:
    from scripts import trusted_broker_snapshot_invocation as invocation
    from scripts import trusted_broker_snapshot_release as release
else:
    import trusted_broker_snapshot_invocation as invocation
    import trusted_broker_snapshot_release as release


CONTROL = Path("/opt/lilith-trusted-controls/broker-snapshot")
APPROVED_FIRST_RELEASE = "8b4dbee055f5ca6b8e899d9cab8130ed4a6cbd9abb27fa71b7bbee88c41c6958"
DEV_HOST = "lilith-dev-01"
DEV_MACHINE_ID = "ae929170e6fa4c8ab9cc7b9547238d9d"
DEV_PROJECT = "lilith-agent-260823-27389"
DEV_ZONE = "projects/763184673487/zones/asia-southeast1-b"
DEV_INSTANCE_ID = "7687007163730582258"
BASELINE = "abc33ebf8d43e8805f43ff11e663a4757bf558d9b62eda9669dabecbb7c9839a"
FRAME = b"LILITH_BROKER_CANDIDATE_DEV_SNAPSHOT_V1:"
INCOMING_FILES = {
    "trusted_broker_snapshot_installer.py", "trusted_broker_snapshot_release.py",
    "trusted_broker_snapshot_invocation.py", "snapshot-release.tar.gz",
    "snapshot-release.attestation.json",
}


class InstallError(RuntimeError):
    pass


def _metadata(key: str) -> str:
    request = Request("http://169.254.169.254/computeMetadata/v1/" + key,
                      headers={"Metadata-Flavor": "Google"})
    with build_opener(ProxyHandler({})).open(request, timeout=5) as response:
        if response.headers.get("Metadata-Flavor") != "Google":
            raise InstallError("UNTRUSTED_METADATA")
        return response.read(256).decode("ascii", "strict").strip()


def assert_dev_host(*, hostname: str | None = None, machine_id: str | None = None,
                    metadata=None) -> None:
    hostname = hostname if hostname is not None else socket.getfqdn()
    machine_id = machine_id if machine_id is not None else Path("/etc/machine-id").read_text().strip()
    lookup = metadata or _metadata
    observed = {key: lookup(key) for key in
                ("project/project-id", "instance/zone", "instance/id", "instance/name")}
    if hostname.startswith("lilith-01") or observed["instance/name"] == "lilith-01":
        raise InstallError("PROD_HOST_FORBIDDEN")
    if (hostname != DEV_HOST or machine_id != DEV_MACHINE_ID or observed != {
        "project/project-id": DEV_PROJECT,
        "instance/zone": DEV_ZONE,
        "instance/id": DEV_INSTANCE_ID,
        "instance/name": DEV_HOST,
    }):
        raise InstallError("PINNED_DEV_IDENTITY_REQUIRED")


def _directory(path: Path, mode: int, *, root_custody: bool) -> None:
    info = path.lstat()
    if (not stat.S_ISDIR(info.st_mode) or stat.S_IMODE(info.st_mode) != mode or
            (root_custody and (info.st_uid, info.st_gid) != (0, 0))):
        raise InstallError("INSTALL_DIRECTORY_CUSTODY")


def _file(path: Path, mode: int, *, root_custody: bool) -> None:
    info = path.lstat()
    if (not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or
            stat.S_IMODE(info.st_mode) != mode or
            (root_custody and (info.st_uid, info.st_gid) != (0, 0))):
        raise InstallError("INSTALL_FILE_CUSTODY")


def _mkdir(path: Path, mode: int, *, root_custody: bool) -> None:
    os.mkdir(path, mode)
    os.chmod(path, mode)
    if root_custody:
        os.chown(path, 0, 0)
    _directory(path, mode, root_custody=root_custody)


def _write(path: Path, content: bytes, mode: int, *, root_custody: bool) -> None:
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(path, flags, mode)
    with os.fdopen(fd, "wb") as target:
        target.write(content)
        target.flush()
        os.fsync(target.fileno())
    os.chmod(path, mode)
    if root_custody:
        os.chown(path, 0, 0)
    _file(path, mode, root_custody=root_custody)


def _fsync_dir(path: Path) -> None:
    fd = os.open(path, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def _self_test() -> dict:
    result = subprocess.run(invocation.command(), stdin=subprocess.DEVNULL,
                            capture_output=True, timeout=120)
    if result.returncode != 0:
        raise InstallError("SNAPSHOT_SELF_TEST_FAILED")
    lines = [line for line in result.stdout.splitlines() if line.startswith(FRAME)]
    if len(lines) != 1 or len(result.stdout) > 3 * 1024 * 1024:
        raise InstallError("SNAPSHOT_SELF_TEST_FRAME")
    try:
        size, sha, encoded = lines[0][len(FRAME):].split(b":", 2)
        data = base64.b64decode(encoded, validate=True)
        if len(data) != int(size) or hashlib.sha256(data).hexdigest().encode() != sha:
            raise ValueError("digest")
        value = json.loads(data)
        if (value.get("toolReleaseId") != APPROVED_FIRST_RELEASE or
                value.get("acceptedBaselineDigest") != BASELINE or
                value.get("validation") != "PASS"):
            raise ValueError("accepted state")
        return value
    except (ValueError, UnicodeError, json.JSONDecodeError) as exc:
        raise InstallError("SNAPSHOT_SELF_TEST_RESULT") from exc


def install(control: Path, release_id: str, *, root_custody: bool = True,
            self_test=None) -> dict:
    if not release.SHA64.fullmatch(release_id) or release_id != APPROVED_FIRST_RELEASE:
        raise InstallError("UNAPPROVED_FIRST_RELEASE")
    if root_custody:
        if not hasattr(os, "geteuid") or os.geteuid() != 0:
            raise InstallError("ROOT_REQUIRED")
        assert_dev_host()
    _directory(control.parent, 0o755, root_custody=root_custody)
    _directory(control, 0o755, root_custody=root_custody)
    incoming = control / "incoming" / release_id
    _directory(control / "incoming", 0o755, root_custody=root_custody)
    _directory(incoming, 0o700, root_custody=root_custody)
    if {p.name for p in incoming.iterdir()} != INCOMING_FILES:
        raise InstallError("INSTALL_INCOMING_FILE_SET")
    archive = incoming / "snapshot-release.tar.gz"
    attestation = incoming / "snapshot-release.attestation.json"
    for path in incoming.iterdir():
        _file(path, 0o600, root_custody=root_custody)
    evidence, payloads = release.verify(archive, attestation)
    if evidence["releaseId"] != release_id:
        raise InstallError("RELEASE_ID_MISMATCH")
    releases = control / "releases"
    current = control / "current"
    final = releases / release_id
    staging = releases / (release_id + ".staging")
    if current.exists() or current.is_symlink() or final.exists() or final.is_symlink() or \
            staging.exists() or staging.is_symlink():
        raise InstallError("INSTALL_EXISTING_RELEASE_OR_POINTER")
    if releases.exists() or releases.is_symlink():
        _directory(releases, 0o755, root_custody=root_custody)
        if any(releases.iterdir()):
            raise InstallError("INSTALL_UNEXPECTED_RELEASE")
    else:
        _mkdir(releases, 0o755, root_custody=root_custody)
    _mkdir(staging, 0o755, root_custody=root_custody)
    for name in ("bin", "lib"):
        _mkdir(staging / name, 0o755, root_custody=root_custody)
    for name, data in sorted(payloads.items()):
        _write(staging / name, data, 0o755 if name.startswith("bin/") else 0o644,
               root_custody=root_custody)
    _write(staging / "release-manifest.json", release.canonical(release.make_manifest(payloads)),
           0o644, root_custody=root_custody)
    _fsync_dir(staging)
    os.rename(staging, final)
    _fsync_dir(releases)
    temporary = control / (".current-" + release_id)
    if temporary.exists() or temporary.is_symlink():
        raise InstallError("INSTALL_POINTER_COLLISION")
    os.symlink("releases/" + release_id, temporary)
    os.replace(temporary, current)
    _fsync_dir(control)
    for name in payloads:
        _file(final / name, 0o755 if name.startswith("bin/") else 0o644,
              root_custody=root_custody)
    _file(final / "release-manifest.json", 0o644, root_custody=root_custody)
    if hashlib.sha256((final / "release-manifest.json").read_bytes()).hexdigest() != release_id:
        raise InstallError("INSTALLED_MANIFEST_MISMATCH")
    for name, data in payloads.items():
        if hashlib.sha256((final / name).read_bytes()).hexdigest() != hashlib.sha256(data).hexdigest():
            raise InstallError("INSTALLED_PAYLOAD_MISMATCH")
    pointer = current.lstat()
    if (not stat.S_ISLNK(pointer.st_mode) or os.readlink(current) != "releases/" + release_id or
            (root_custody and (pointer.st_uid, pointer.st_gid) != (0, 0))):
        raise InstallError("INSTALLED_POINTER_CUSTODY")
    checker = self_test or _self_test
    result = checker()
    return {"result": "INSTALLED_AND_SELF_TESTED", "releaseId": release_id,
            "acceptedBaselineDigest": result["acceptedBaselineDigest"]}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--release-id", required=True)
    args = parser.parse_args()
    result = install(CONTROL, args.release_id)
    print(release.canonical(result).decode(), end="")


if __name__ == "__main__":
    main()
