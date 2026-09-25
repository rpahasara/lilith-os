#!/usr/bin/env python3
"""Install one byte-pinned Stage-III A2 control release and dormant systemd unit.

The operational entrypoint has one fixed verb and no path, release, service,
database, or signal parameters. Installation never starts or enables the unit.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import types


STAGING = Path("/tmp/lilith-stage3-a2-final-control-staging")
INSTALLER = Path("/tmp/lilith-stage3-a2-final-control-installer.py")
BASE_SHA = "6de7f6dddd93cd65671b58e627ad3c92746c9fbd"
RELEASE = Path("/opt/lilith-stage3-a2-final-v1")
SERVICE = "lilith-stage3-a2-final.service"
UNIT = Path("/etc/systemd/system") / SERVICE
ATTEMPT = Path("/var/lib/.lilith-memory-broker-stage3-a2-dispatch-attempt.json")
DISPATCH_SHA = "33d258f9f18ad5c89ffc360be3565238f8e5a245b21bdbfe86ac70086eeb70ba"
FILES = {
    "memory_broker_stage2_control.py": "ee370ae75a2d0b4b6bd4037c010fe5bc084033d47a0bd2feab3af54a0baa269a",
    "memory_broker_stage3_transition.py": "a830f6ebbde3d320475921a228fba34d39504e495eca76f05d376cb3a4d0d197",
    "memory_broker_stage3_liveness.py": "08d0d55ff655826a298d9405883406f5dcb6f8de3fd3451b8d9f151e648be888",
    "memory_broker_stage3_guard_worker.py": "cdb933cd1ea9170d533a39d1cb5379f6834621f6911bc6afa3ff34057261feb2",
    "memory_broker_stage3_adapters.py": "191d072bd9d5f89cc1dc1357ecab9ff995f00bbdcba624642adc4eeaf009ccf9",
    "memory_broker_stage3_final.py": "a057dc62b575cc3159b84d12cae1c27a9997572e81a4c5c045459b0849389a3b",
    "memory_broker_stage3_dispatch.py": DISPATCH_SHA,
}
UNIT_BYTES = f"""[Unit]
Description=LILITH DEV synthetic Stage-III A2 fixed one-shot final controller
After=network-online.target
StartLimitIntervalSec=infinity
StartLimitBurst=1

[Service]
Type=exec
User=root
Group=root
WorkingDirectory=/
ExecStart=/usr/bin/python3 -I -B {RELEASE.as_posix()}/scripts/memory_broker_stage3_dispatch.py
Restart=no
RemainAfterExit=no
RuntimeMaxSec=600
TimeoutStopSec=10s
UMask=0077
StandardInput=null
StandardOutput=journal
StandardError=journal
""".encode("ascii")


class WiringInstallError(RuntimeError):
    pass


def require(ok: bool, code: str) -> None:
    if not ok:
        raise WiringInstallError(code)


def canonical(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":"),
                       ensure_ascii=False) + "\n").encode("utf-8")


def fsync_dir(path: Path) -> None:
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def directory(path: Path, mode: int) -> None:
    info = path.lstat()
    require(stat.S_ISDIR(info.st_mode) and not path.is_symlink() and
            (info.st_uid, info.st_gid, stat.S_IMODE(info.st_mode)) ==
            (0, 0, mode), "STAGE3_WIRING_DIRECTORY_CUSTODY")


def regular(path: Path, *, mode: int) -> bytes:
    info = path.lstat()
    require(stat.S_ISREG(info.st_mode) and info.st_nlink == 1 and
            (info.st_uid, info.st_gid, stat.S_IMODE(info.st_mode)) ==
            (0, 0, mode) and 0 < info.st_size <= 256 * 1024,
            "STAGE3_WIRING_SOURCE_CUSTODY")
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    try:
        opened = os.fstat(fd)
        require((opened.st_dev, opened.st_ino, opened.st_size) ==
                (info.st_dev, info.st_ino, info.st_size),
                "STAGE3_WIRING_SOURCE_REPLACED")
        with os.fdopen(fd, "rb", closefd=False) as stream:
            raw = stream.read()
        require(len(raw) == info.st_size, "STAGE3_WIRING_SOURCE_SIZE")
        return raw
    finally:
        os.close(fd)


def exclusive(path: Path, raw: bytes, mode: int) -> None:
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                 mode)
    try:
        os.fchmod(fd, mode)
        with os.fdopen(fd, "wb", closefd=False) as stream:
            stream.write(raw)
            stream.flush()
        os.fsync(fd)
    finally:
        os.close(fd)
    fsync_dir(path.parent)


def staged_bytes() -> dict[str, bytes]:
    directory(Path("/tmp"), 0o1777)
    directory(STAGING, 0o700)
    require({item.name for item in STAGING.iterdir()} == set(FILES),
            "STAGE3_WIRING_STAGING_MEMBERS")
    payloads = {name: regular(STAGING / name, mode=0o600)
                for name in sorted(FILES)}
    require({name: hashlib.sha256(raw).hexdigest()
             for name, raw in payloads.items()} == FILES,
            "STAGE3_WIRING_SOURCE_DIGEST")
    return payloads


def unit_fields() -> dict[str, str]:
    result = subprocess.run(
        ["/usr/bin/systemctl", "show", SERVICE,
         "--property=LoadState,ActiveState,MainPID,FragmentPath,DropInPaths,UnitFileState",
         "--no-pager"], check=True, capture_output=True, text=True, timeout=10)
    return dict(line.split("=", 1) for line in result.stdout.splitlines()
                if "=" in line)


def pinned_control(payloads: dict[str, bytes]):
    """Execute only the already verified exact source bytes, never a path import."""
    module = types.ModuleType("stage3_verified_control")
    module.__file__ = str(STAGING / "memory_broker_stage2_control.py")
    exec(compile(payloads["memory_broker_stage2_control.py"], module.__file__,
                 "exec"), module.__dict__)
    return module


def preflight(payloads: dict[str, bytes]) -> None:
    require(os.geteuid() == os.getegid() == 0,
            "STAGE3_WIRING_ROOT_REQUIRED")
    require(Path(__file__).absolute() == INSTALLER,
            "STAGE3_WIRING_INSTALLER_PATH")
    regular(INSTALLER, mode=0o600)
    control = pinned_control(payloads)
    control.assert_host()
    control.stage3_accepted_snapshot()
    directory(Path("/opt"), 0o755)
    directory(Path("/etc/systemd/system"), 0o755)
    require(not any(os.path.lexists(path) for path in (
        RELEASE, UNIT, ATTEMPT,
        Path("/var/lib/.lilith-memory-broker-stage3-a2"),
        Path("/var/lib/.lilith-memory-broker-stage3-a2-final-attempt.json"),
        control.STAGE3_MARKER, control.STAGE3_USED, control.STAGE3_ARM)),
        "STAGE3_WIRING_PRIOR_STATE")
    require(unit_fields() == {
        "LoadState": "not-found", "ActiveState": "inactive", "MainPID": "0",
        "FragmentPath": "", "DropInPaths": "", "UnitFileState": ""},
        "STAGE3_WIRING_UNIT_COLLISION")


def install_fixed() -> dict:
    """One-time installation only; source collision leaves reviewable inert state."""
    payloads = staged_bytes()
    preflight(payloads)
    RELEASE.mkdir(mode=0o755)
    fsync_dir(RELEASE.parent)
    scripts = RELEASE / "scripts"
    scripts.mkdir(mode=0o755)
    fsync_dir(RELEASE)
    for name, raw in payloads.items():
        exclusive(scripts / name, raw, 0o644)
    manifest = canonical({
        "schema": "Stage3A2FixedControlReleaseV1",
        "baseSha": BASE_SHA, "files": FILES})
    exclusive(RELEASE / "manifest.json", manifest, 0o644)
    os.chmod(scripts, 0o555)
    fsync_dir(scripts)
    os.chmod(RELEASE, 0o555)
    fsync_dir(RELEASE)
    require({name: hashlib.sha256(regular(scripts / name, mode=0o644)).hexdigest()
             for name in FILES} == FILES and
            regular(RELEASE / "manifest.json", mode=0o644) == manifest,
            "STAGE3_WIRING_INSTALLED_DRIFT")
    exclusive(UNIT, UNIT_BYTES, 0o644)
    subprocess.run(["/usr/bin/systemctl", "daemon-reload"], check=True,
                   capture_output=True, timeout=15)
    require(regular(UNIT, mode=0o644) == UNIT_BYTES and
            unit_fields() == {
                "LoadState": "loaded", "ActiveState": "inactive", "MainPID": "0",
                "FragmentPath": str(UNIT), "DropInPaths": "",
                "UnitFileState": "static"},
            "STAGE3_WIRING_UNIT_NOT_DORMANT")
    return {"status": "STAGE3_FINAL_CONTROL_INSTALLED_INACTIVE",
            "baseSha": BASE_SHA,
            "releaseDigestSha256": hashlib.sha256(manifest).hexdigest(),
            "unit": SERVICE, "started": False, "enabled": False}


def main() -> None:
    require(sys.argv == [sys.argv[0], "--install-fixed"],
            "STAGE3_WIRING_FIXED_VERB_ONLY")
    print(canonical(install_fixed()).decode("utf-8"), end="")


if __name__ == "__main__":
    main()
