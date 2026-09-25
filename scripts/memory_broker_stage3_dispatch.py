#!/usr/bin/env python3
"""Fixed, manually started Stage-III A2 final-controller process.

This module is installed only as part of the byte-pinned control release. It
has no command-line parameters and is not a CI/CD or broker IPC entrypoint.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import time


BASE_SHA = "6de7f6dddd93cd65671b58e627ad3c92746c9fbd"
RELEASE = Path("/opt/lilith-stage3-a2-final-v1")
SERVICE = "lilith-stage3-a2-final.service"
UNIT = Path("/etc/systemd/system") / SERVICE
ATTEMPT = Path("/var/lib/.lilith-memory-broker-stage3-a2-dispatch-attempt.json")
HELPERS = {
    "memory_broker_stage2_control.py": "ee370ae75a2d0b4b6bd4037c010fe5bc084033d47a0bd2feab3af54a0baa269a",
    "memory_broker_stage3_transition.py": "a830f6ebbde3d320475921a228fba34d39504e495eca76f05d376cb3a4d0d197",
    "memory_broker_stage3_liveness.py": "08d0d55ff655826a298d9405883406f5dcb6f8de3fd3451b8d9f151e648be888",
    "memory_broker_stage3_guard_worker.py": "cdb933cd1ea9170d533a39d1cb5379f6834621f6911bc6afa3ff34057261feb2",
    "memory_broker_stage3_adapters.py": "191d072bd9d5f89cc1dc1357ecab9ff995f00bbdcba624642adc4eeaf009ccf9",
    "memory_broker_stage3_final.py": "a057dc62b575cc3159b84d12cae1c27a9997572e81a4c5c045459b0849389a3b",
}


class DispatchError(RuntimeError):
    pass


def require(ok: bool, code: str) -> None:
    if not ok:
        raise DispatchError(code)


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
            (0, 0, mode), "STAGE3_DISPATCH_DIRECTORY_CUSTODY")


def regular(path: Path, mode: int = 0o644) -> bytes:
    info = path.lstat()
    require(stat.S_ISREG(info.st_mode) and info.st_nlink == 1 and
            (info.st_uid, info.st_gid, stat.S_IMODE(info.st_mode)) ==
            (0, 0, mode) and 0 < info.st_size <= 256 * 1024,
            "STAGE3_DISPATCH_FILE_CUSTODY")
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    try:
        opened = os.fstat(fd)
        require((opened.st_dev, opened.st_ino, opened.st_size) ==
                (info.st_dev, info.st_ino, info.st_size),
                "STAGE3_DISPATCH_FILE_REPLACED")
        with os.fdopen(fd, "rb", closefd=False) as stream:
            return stream.read()
    finally:
        os.close(fd)


def verify_release() -> str:
    require(Path(__file__).absolute() ==
            RELEASE / "scripts/memory_broker_stage3_dispatch.py",
            "STAGE3_DISPATCH_SOURCE_PATH")
    directory(Path("/opt"), 0o755)
    directory(RELEASE, 0o555)
    directory(RELEASE / "scripts", 0o555)
    names = {item.name for item in (RELEASE / "scripts").iterdir()}
    require(names == set(HELPERS) | {"memory_broker_stage3_dispatch.py"},
            "STAGE3_DISPATCH_RELEASE_MEMBERS")
    observed = {name: hashlib.sha256(regular(RELEASE / "scripts" / name)).hexdigest()
                for name in sorted(names)}
    require({name: observed[name] for name in HELPERS} == HELPERS,
            "STAGE3_DISPATCH_HELPER_DRIFT")
    manifest = regular(RELEASE / "manifest.json")
    expected = {"schema": "Stage3A2FixedControlReleaseV1", "baseSha": BASE_SHA,
                "files": observed}
    require(manifest == canonical(expected), "STAGE3_DISPATCH_MANIFEST_DRIFT")
    require({item.name for item in RELEASE.iterdir()} == {"scripts", "manifest.json"},
            "STAGE3_DISPATCH_RELEASE_COLLISION")
    return hashlib.sha256(manifest).hexdigest()


def valid_origin(fields: dict, invocation: str | None, argv: bytes, pid: int) -> bool:
    expected = (b"/usr/bin/python3\0-I\0-B\0" +
                str(RELEASE / "scripts/memory_broker_stage3_dispatch.py").encode() + b"\0")
    return (isinstance(invocation, str) and
            re.fullmatch(r"[0-9a-f]{32}", invocation) is not None and
            argv == expected and fields == {
                "ActiveState": "active", "MainPID": str(pid),
                "InvocationID": invocation, "NRestarts": "0",
                "FragmentPath": str(UNIT)})


def verify_systemd_origin() -> str:
    regular(UNIT)
    invocation = os.environ.get("INVOCATION_ID")
    argv = Path("/proc/self/cmdline").read_bytes()
    deadline = time.monotonic() + 5
    while True:
        result = subprocess.run(
            ["/usr/bin/systemctl", "show", SERVICE,
             "--property=ActiveState,MainPID,InvocationID,NRestarts,FragmentPath",
             "--no-pager"], check=True, capture_output=True, text=True,
            timeout=5)
        fields = dict(line.split("=", 1) for line in result.stdout.splitlines()
                      if "=" in line)
        if valid_origin(fields, invocation, argv, os.getpid()):
            return invocation
        require(time.monotonic() < deadline,
                "STAGE3_DISPATCH_NOT_EXACT_SYSTEMD_PROCESS")
        time.sleep(0.05)


def claim_once(release_digest: str, invocation: str) -> None:
    parent = ATTEMPT.parent
    directory(parent, 0o755)
    require(not os.path.lexists(ATTEMPT) and
            not os.path.lexists(parent / ".lilith-memory-broker-stage3-a2") and
            not os.path.lexists(parent /
                                  ".lilith-memory-broker-stage3-a2-final-attempt.json"),
            "STAGE3_DISPATCH_PRIOR_ATTEMPT")
    raw = canonical({"schema": "Stage3A2DispatchAttemptV1", "baseSha": BASE_SHA,
                     "releaseDigestSha256": release_digest,
                     "systemdInvocationId": invocation})
    fd = os.open(ATTEMPT, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                 0o600)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "wb", closefd=False) as stream:
            stream.write(raw)
            stream.flush()
        os.fsync(fd)
    finally:
        os.close(fd)
    fsync_dir(parent)


def main() -> None:
    require(sys.argv == [str(RELEASE / "scripts/memory_broker_stage3_dispatch.py")]
            and os.geteuid() == os.getegid() == 0,
            "STAGE3_DISPATCH_ROOT_FIXED_ARGV")
    release_digest = verify_release()
    invocation = verify_systemd_origin()
    sys.path.insert(0, str(RELEASE))
    from scripts import memory_broker_stage2_control as control
    from scripts import memory_broker_stage3_final as final
    control.assert_host()
    claim_once(release_digest, invocation)
    result = final.FinalController().execute_once()
    require(result["status"] == "RESTORED", "STAGE3_DISPATCH_NOT_RESTORED")
    print(canonical(result).decode("utf-8"), end="", flush=True)


if __name__ == "__main__":
    main()
