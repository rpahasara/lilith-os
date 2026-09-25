#!/usr/bin/env python3
"""Fixed, owner-dispatched DEV transport for the pinned Stage-III A2 control.

The protected-main workflow streams this file over the existing authenticated
DEV command channel. It accepts only the two closed remote operations below;
neither accepts an operator-supplied path, service, release, or command.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import time
import types


INBOUND = Path("/tmp/lilith-stage3-a2-final-control-inbound")
STAGING = Path("/tmp/lilith-stage3-a2-final-control-staging")
INSTALLER = Path("/tmp/lilith-stage3-a2-final-control-installer.py")
RELEASE = Path("/opt/lilith-stage3-a2-final-v1")
UNIT = Path("/etc/systemd/system/lilith-stage3-a2-final.service")
SERVICE = "lilith-stage3-a2-final.service"
BASE_SHA = "6de7f6dddd93cd65671b58e627ad3c92746c9fbd"
ATTEMPT = Path("/var/lib/.lilith-memory-broker-stage3-a2-dispatch-attempt.json")
VAULT = Path("/var/lib/.lilith-memory-broker-stage3-a2")
FINAL_ATTEMPT = Path("/var/lib/.lilith-memory-broker-stage3-a2-final-attempt.json")
FILES = {
    "memory_broker_stage2_control.py": "ee370ae75a2d0b4b6bd4037c010fe5bc084033d47a0bd2feab3af54a0baa269a",
    "memory_broker_stage3_transition.py": "a830f6ebbde3d320475921a228fba34d39504e495eca76f05d376cb3a4d0d197",
    "memory_broker_stage3_liveness.py": "08d0d55ff655826a298d9405883406f5dcb6f8de3fd3451b8d9f151e648be888",
    "memory_broker_stage3_guard_worker.py": "cdb933cd1ea9170d533a39d1cb5379f6834621f6911bc6afa3ff34057261feb2",
    "memory_broker_stage3_adapters.py": "191d072bd9d5f89cc1dc1357ecab9ff995f00bbdcba624642adc4eeaf009ccf9",
    "memory_broker_stage3_final.py": "a057dc62b575cc3159b84d12cae1c27a9997572e81a4c5c045459b0849389a3b",
    "memory_broker_stage3_dispatch.py": "33d258f9f18ad5c89ffc360be3565238f8e5a245b21bdbfe86ac70086eeb70ba",
    "memory_broker_stage3_wiring_install.py": "1f47160ef31b4c4bc07f950598d8fc3db63c0effeddb91ff5ca259c50d95b3d8",
}
PINNED_FILES = {name: value for name, value in FILES.items()
                if name != "memory_broker_stage3_wiring_install.py"}
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


class TransportError(RuntimeError):
    pass


def require(ok: bool, code: str) -> None:
    if not ok:
        raise TransportError(code)


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def canonical(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":"),
                       ensure_ascii=False) + "\n").encode("utf-8")


def local_source_gate() -> None:
    root = Path(__file__).resolve().parent
    for name, expected in FILES.items():
        require(digest((root / name).read_bytes()) == expected,
                "STAGE3_TRANSPORT_PROTECTED_SOURCE_DRIFT")


def directory(path: Path, uid: int, mode: int) -> None:
    info = path.lstat()
    require(stat.S_ISDIR(info.st_mode) and not path.is_symlink() and
            info.st_uid == info.st_gid == uid and
            stat.S_IMODE(info.st_mode) == mode,
            "STAGE3_TRANSPORT_DIRECTORY_CUSTODY")


def regular(path: Path, uid: int, mode: int) -> bytes:
    info = path.lstat()
    require(stat.S_ISREG(info.st_mode) and info.st_uid == uid and
            (uid != 0 or info.st_gid == 0) and
            info.st_nlink == 1 and stat.S_IMODE(info.st_mode) == mode and
            0 < info.st_size <= 256 * 1024,
            "STAGE3_TRANSPORT_FILE_CUSTODY")
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    try:
        opened = os.fstat(fd)
        require((opened.st_dev, opened.st_ino, opened.st_size, opened.st_uid) ==
                (info.st_dev, info.st_ino, info.st_size, info.st_uid),
                "STAGE3_TRANSPORT_FILE_REPLACED")
        raw = os.read(fd, 256 * 1024 + 1)
        require(len(raw) == info.st_size, "STAGE3_TRANSPORT_FILE_SIZE")
        return raw
    finally:
        os.close(fd)


def fsync_dir(path: Path) -> None:
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def exclusive(path: Path, raw: bytes) -> None:
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                 0o600)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "wb", closefd=False) as stream:
            stream.write(raw)
            stream.flush()
        os.fsync(fd)
    finally:
        os.close(fd)
    fsync_dir(path.parent)


def uploaded_bytes() -> dict[str, bytes]:
    directory(Path("/tmp"), 0, 0o1777)
    info = INBOUND.lstat()
    require(stat.S_ISDIR(info.st_mode) and not INBOUND.is_symlink() and
            info.st_uid != 0 and stat.S_IMODE(info.st_mode) == 0o700,
            "STAGE3_TRANSPORT_INBOUND_CUSTODY")
    require({item.name for item in INBOUND.iterdir()} == set(FILES),
            "STAGE3_TRANSPORT_INBOUND_MEMBERS")
    payloads = {name: regular(INBOUND / name, info.st_uid, 0o600)
                for name in sorted(FILES)}
    require({name: digest(raw) for name, raw in payloads.items()} == FILES,
            "STAGE3_TRANSPORT_INBOUND_DIGEST")
    return payloads


def module_from_bytes(raw: bytes, name: str, path: Path):
    module = types.ModuleType(name)
    module.__file__ = str(path)
    exec(compile(raw, str(path), "exec"), module.__dict__)
    return module


def fields() -> dict[str, str]:
    result = subprocess.run(
        ["/usr/bin/systemctl", "show", SERVICE,
         "--property=LoadState,ActiveState,MainPID,FragmentPath,DropInPaths,UnitFileState,NRestarts,Result,ExecMainStatus",
         "--no-pager"], check=True, capture_output=True, text=True, timeout=10)
    return dict(line.split("=", 1) for line in result.stdout.splitlines()
                if "=" in line)


def install_control() -> dict:
    require(os.geteuid() == os.getegid() == 0,
            "STAGE3_TRANSPORT_ROOT_REQUIRED")
    payloads = uploaded_bytes()
    control = module_from_bytes(payloads["memory_broker_stage2_control.py"],
                                "stage3_transport_control",
                                INBOUND / "memory_broker_stage2_control.py")
    control.assert_host()
    control.stage3_accepted_snapshot()
    require(not any(os.path.lexists(path) for path in
                    (STAGING, INSTALLER, RELEASE, UNIT, ATTEMPT, VAULT,
                     FINAL_ATTEMPT, control.STAGE3_MARKER,
                     control.STAGE3_USED, control.STAGE3_ARM)),
            "STAGE3_TRANSPORT_PRIOR_STATE")
    require(fields()["LoadState"] == "not-found",
            "STAGE3_TRANSPORT_UNIT_COLLISION")
    STAGING.mkdir(mode=0o700)
    os.chmod(STAGING, 0o700)
    fsync_dir(STAGING.parent)
    for name in sorted(FILES):
        if name != "memory_broker_stage3_wiring_install.py":
            exclusive(STAGING / name, payloads[name])
    exclusive(INSTALLER, payloads["memory_broker_stage3_wiring_install.py"])
    result = subprocess.run(
        ["/usr/bin/python3", "-I", "-B", str(INSTALLER), "--install-fixed"],
        check=True, capture_output=True, text=True, timeout=180)
    require(result.stderr == "", "STAGE3_TRANSPORT_INSTALLER_STDERR")
    verify_installed(payloads)
    output = json.loads(result.stdout)
    require(output.get("status") == "STAGE3_FINAL_CONTROL_INSTALLED_INACTIVE" and
            output.get("started") is False and output.get("enabled") is False,
            "STAGE3_TRANSPORT_INSTALL_RESULT")
    return output


def verify_installed(payloads: dict[str, bytes] | None = None):
    directory(Path("/opt"), 0, 0o755)
    directory(RELEASE, 0, 0o555)
    directory(RELEASE / "scripts", 0, 0o555)
    require({item.name for item in (RELEASE / "scripts").iterdir()} ==
            set(PINNED_FILES),
            "STAGE3_TRANSPORT_RELEASE_MEMBERS")
    for name, expected in PINNED_FILES.items():
        raw = regular(RELEASE / "scripts" / name, 0, 0o644)
        require(digest(raw) == expected and
                (payloads is None or raw == payloads[name]),
                "STAGE3_TRANSPORT_INSTALLED_DRIFT")
    require({item.name for item in RELEASE.iterdir()} ==
            {"scripts", "manifest.json"} and
            regular(RELEASE / "manifest.json", 0, 0o644) == canonical({
                "schema": "Stage3A2FixedControlReleaseV1",
                "baseSha": BASE_SHA, "files": PINNED_FILES}),
            "STAGE3_TRANSPORT_MANIFEST_DRIFT")
    require(regular(UNIT, 0, 0o644) == UNIT_BYTES,
            "STAGE3_TRANSPORT_UNIT_DRIFT")
    observed = fields()
    require(observed["LoadState"] == "loaded" and
            observed["UnitFileState"] == "static" and
            observed["FragmentPath"] == str(UNIT) and
            observed["DropInPaths"] == "",
            "STAGE3_TRANSPORT_UNIT_NOT_FIXED")


def dispatch_once() -> dict:
    require(os.geteuid() == os.getegid() == 0,
            "STAGE3_TRANSPORT_ROOT_REQUIRED")
    verify_installed()
    control = module_from_bytes(
        regular(RELEASE / "scripts/memory_broker_stage2_control.py", 0, 0o644),
        "stage3_transport_control",
        RELEASE / "scripts/memory_broker_stage2_control.py")
    control.assert_host()
    control.stage3_accepted_snapshot()
    control.stage3_verify_inactive_release()
    require(not any(os.path.lexists(path) for path in
                    (ATTEMPT, VAULT, FINAL_ATTEMPT, control.STAGE3_MARKER,
                     control.STAGE3_USED, control.STAGE3_ARM)),
            "STAGE3_TRANSPORT_PRIOR_ATTEMPT")
    before = fields()
    require(before["ActiveState"] == "inactive" and before["MainPID"] == "0" and
            before["NRestarts"] == "0" and before["UnitFileState"] == "static" and
            before["DropInPaths"] == "",
            "STAGE3_TRANSPORT_DISPATCH_NOT_DORMANT")
    # The only launch in this file. No failure path starts, restarts, or retries.
    subprocess.run(["/usr/bin/systemctl", "start", SERVICE],
                   check=True, capture_output=True, timeout=15)
    deadline = time.monotonic() + 650
    while time.monotonic() < deadline:
        observed = fields()
        require(observed["NRestarts"] == "0",
                "STAGE3_TRANSPORT_UNEXPECTED_RESTART")
        if observed["ActiveState"] in ("inactive", "failed"):
            require(observed["ActiveState"] == "inactive" and
                    observed["Result"] == "success" and
                    observed["ExecMainStatus"] == "0" and
                    observed["MainPID"] == "0",
                    "STAGE3_TRANSPORT_DISPATCH_FAILED")
            report_path = VAULT / "final-report.json"
            report = json.loads(regular(report_path, 0, 0o600))
            require(report.get("schema") == "Stage3A2FinalReportV1" and
                    report.get("status") == "RESTORED",
                    "STAGE3_TRANSPORT_NO_RESTORED_REPORT")
            return {"status": "STAGE3_A2_RESTORED", "reportSha256":
                    digest(regular(report_path, 0, 0o600))}
        time.sleep(2)
    raise TransportError("STAGE3_TRANSPORT_DISPATCH_TIMEOUT_REVIEW_REQUIRED")


def main() -> None:
    require(len(sys.argv) == 2 and sys.argv[1] in
            ("verify-source", "install-control", "dispatch-once"),
            "STAGE3_TRANSPORT_FIXED_VERB_ONLY")
    operation = sys.argv[1]
    if operation == "verify-source":
        local_source_gate()
        result = {"status": "STAGE3_CONTROL_SOURCE_PINNED"}
    else:
        require(sys.argv[0] == "-", "STAGE3_TRANSPORT_STDIN_ONLY")
        result = install_control() if operation == "install-control" else dispatch_once()
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))


if __name__ == "__main__":
    main()
