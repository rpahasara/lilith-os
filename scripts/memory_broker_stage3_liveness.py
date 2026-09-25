"""Exact runtime systemd liveness binding for dormant DEV-only Stage-III A2.

The two broker units are runtime-masked during construction and teardown.
While experimental, both have BindsTo=/After= on a non-restarting, one-shot
Type=notify guard whose main process watches the controller's kernel pidfd.
There is no generalized unit name, command, or service-control input.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import stat

from scripts import memory_broker_stage2_control as control


GUARD = "lilith-stage3-a2-guard.service"
GUARD_WORKER_SHA = "cdb933cd1ea9170d533a39d1cb5379f6834621f6911bc6afa3ff34057261feb2"
DROP_NAME = "90-stage3-a2-liveness.conf"
GUARD_UNIT = """[Unit]
Description=LILITH DEV synthetic Stage-III A2 one-shot controller pidfd guard

[Service]
Type=notify
NotifyAccess=main
User=root
Group=root
ExecStart={worker} --run
Restart=no
TimeoutStartSec=10s
TimeoutStopSec=10s
NoNewPrivileges=yes
PrivateTmp=yes
PrivateDevices=yes
ProtectSystem=strict
ProtectHome=yes
ProtectKernelTunables=yes
ProtectKernelModules=yes
ProtectControlGroups=yes
RestrictNamespaces=yes
LockPersonality=yes
CapabilityBoundingSet=
AmbientCapabilities=
RestrictAddressFamilies=AF_UNIX
IPAddressDeny=any
ReadOnlyPaths=/etc/lilith-memory-broker /opt/lilith-memory-broker
ReadWritePaths=/var/lib/.lilith-memory-broker-stage3-a2
"""
DROPIN = """[Unit]
BindsTo=lilith-stage3-a2-guard.service
After=lilith-stage3-a2-guard.service
"""


class LivenessError(control.Stage2Error):
    pass


def require(ok: bool, code: str) -> None:
    if not ok:
        raise LivenessError(code)


def canonical(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":"),
                       ensure_ascii=False) + "\n").encode()


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def fsync_dir(path: Path) -> None:
    if os.name == "nt":
        return
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def regular(path: Path, *, mode: int, uid: int = 0, gid: int = 0) -> bytes:
    info = path.lstat()
    require(stat.S_ISREG(info.st_mode) and info.st_nlink == 1 and
            (os.name == "nt" or (info.st_uid, info.st_gid,
             stat.S_IMODE(info.st_mode)) == (uid, gid, mode)),
            "GUARD_SOURCE_CUSTODY")
    fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    try:
        require(os.fstat(fd).st_ino == info.st_ino, "GUARD_SOURCE_REPLACED")
        with os.fdopen(fd, "rb", closefd=False) as stream:
            data = stream.read()
        require(len(data) == info.st_size, "GUARD_SOURCE_SIZE")
        return data
    finally:
        os.close(fd)


def exclusive(path: Path, data: bytes, mode: int) -> None:
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL |
                 getattr(os, "O_NOFOLLOW", 0), mode)
    try:
        if os.name != "nt":
            os.fchmod(fd, mode)
        with os.fdopen(fd, "wb", closefd=False) as stream:
            stream.write(data)
            stream.flush()
        os.fsync(fd)
    finally:
        os.close(fd)
    fsync_dir(path.parent)


@dataclass(frozen=True)
class Paths:
    systemd: Path = Path("/run/systemd/system")
    runtime: Path = Path("/run/lilith-stage3-a2")
    vault: Path = Path("/var/lib/.lilith-memory-broker-stage3-a2")
    worker_source: Path = Path(__file__).with_name(
        "memory_broker_stage3_guard_worker.py")

    @property
    def guard_unit(self) -> Path:
        return self.systemd / GUARD

    @property
    def worker(self) -> Path:
        return self.runtime / "guard.py"

    @property
    def config(self) -> Path:
        return self.runtime / "guard.json"

    @property
    def claim(self) -> Path:
        return self.vault / "guard.claim.json"

    def drop_directory(self, unit: str) -> Path:
        require(unit in (control.SERVICE, control.SOCKET), "GUARD_UNIT_SCOPE")
        return self.systemd / (unit + ".d")

    def drop(self, unit: str) -> Path:
        return self.drop_directory(unit) / DROP_NAME


def controller_identity() -> tuple[int, str, int]:
    pid = os.getpid()
    require(pid > 1, "GUARD_CONTROLLER_PID")
    raw = (Path("/proc") / str(pid) / "stat").read_text(encoding="ascii")
    fields = raw.rsplit(") ", 1)[1].split()
    boot = Path("/proc/sys/kernel/random/boot_id").read_text(
        encoding="ascii").strip()
    require(len(fields) > 19 and re.fullmatch(r"[0-9a-f-]{36}", boot) is not None,
            "GUARD_CONTROLLER_KERNEL_IDENTITY")
    ticks = int(fields[19])
    require(ticks > 0, "GUARD_CONTROLLER_START_TICKS")
    return pid, boot, ticks


def config_value(authorization_id: str) -> dict:
    require(re.fullmatch(r"[0-9a-f]{32}", authorization_id) is not None,
            "GUARD_AUTHORIZATION_ID")
    pid, boot, ticks = controller_identity()
    return {
        "schema": "Stage3A2LivenessGuardV1", "project": control.PROJECT,
        "zone": control.ZONE, "instanceId": control.INSTANCE_ID,
        "hostname": control.HOSTNAME, "machineId": control.MACHINE_ID,
        "acceptedRelease": control.RELEASE,
        "candidateRelease": control.STAGE3_RELEASE,
        "acceptedBaselineDigest": control.STAGE3_ACCEPTED_BASELINE,
        "authorityMode": "SYNTHETIC_ONLY", "canonicalCapability": "DISABLED",
        "experimentId": control.STAGE3_EXPERIMENT,
        "authorizationId": authorization_id,
        "controllerPid": pid, "controllerBootId": boot,
        "controllerStartTicks": ticks, "nonce": secrets.token_hex(32),
    }


def guard_unit_bytes(paths: Paths) -> bytes:
    return GUARD_UNIT.format(worker="/usr/bin/python3 -I -B " +
                             paths.worker.as_posix()).encode()


def source_bytes(paths: Paths) -> bytes:
    raw = regular(paths.worker_source, mode=0o644)
    require(len(raw) < 32 * 1024 and sha(raw) == GUARD_WORKER_SHA,
            "GUARD_WORKER_SOURCE_DRIFT")
    return raw


def unit_state(unit: str) -> dict:
    return control.show(unit, "ActiveState", "SubState", "MainPID",
                        "UnitFileState", "BindsTo", "After", "DropInPaths")


def require_inert(*, masked: bool) -> None:
    for unit in (control.SERVICE, control.SOCKET):
        value = unit_state(unit)
        require(value.get("ActiveState") == "inactive" and
                value.get("MainPID", "0") == "0" and
                value.get("UnitFileState") == (
                    "masked-runtime" if masked else
                    "static" if unit == control.SERVICE else "disabled"),
                "GUARD_UNITS_NOT_INERT")


def require_dependencies(paths: Paths, *, present: bool) -> None:
    for unit in (control.SERVICE, control.SOCKET):
        value = unit_state(unit)
        bound = set(value.get("BindsTo", "").split())
        after = set(value.get("After", "").split())
        if present:
            require(bound == {GUARD} and GUARD in after and
                    value.get("DropInPaths") == paths.drop(unit).as_posix() and
                    regular(paths.drop(unit), mode=0o644) == DROPIN.encode(),
                    "GUARD_DEPENDENCY_DRIFT")
        else:
            require(GUARD not in bound and GUARD not in after and
                    value.get("DropInPaths") == "", "GUARD_DEPENDENCY_REMAINS")


def verify_guard(paths: Paths, authorization_id: str) -> dict:
    require(regular(paths.guard_unit, mode=0o644) == guard_unit_bytes(paths) and
            sha(regular(paths.worker, mode=0o600)) == GUARD_WORKER_SHA,
            "GUARD_INSTALLED_BYTES_DRIFT")
    value = control.show(GUARD, "ActiveState", "SubState", "MainPID",
                         "NRestarts", "FragmentPath", "UnitFileState")
    require(value.get("ActiveState") == "active" and
            value.get("SubState") == "running" and
            value.get("NRestarts") == "0" and
            value.get("FragmentPath") == paths.guard_unit.as_posix() and
            int(value.get("MainPID", "0")) > 1 and
            value.get("UnitFileState") in ("static", "disabled"),
            "GUARD_NOT_ACTIVE")
    claim = json.loads(regular(paths.claim, mode=0o600))
    config_raw = regular(paths.config, mode=0o600)
    config = json.loads(config_raw)
    require(claim == {"schema": "Stage3A2GuardClaimV1",
                      "authorizationId": authorization_id,
                      "controllerPid": config["controllerPid"],
                      "controllerBootId": config["controllerBootId"],
                      "controllerStartTicks": config["controllerStartTicks"],
                      "nonce": config["nonce"]} and
            config_raw == canonical(config) and
            config["authorizationId"] == authorization_id and
            config["controllerPid"] == os.getpid(), "GUARD_CLAIM_MISMATCH")
    return {"guardPid": int(value["MainPID"]), "controllerPid": os.getpid(),
            "claimSha256": sha(regular(paths.claim, mode=0o600))}


def verify(paths: Paths, authorization_id: str) -> dict:
    control.assert_host()
    require_dependencies(paths, present=True)
    return verify_guard(paths, authorization_id)


def mask_for_transition() -> None:
    """Close both activation paths before any accepted binding is changed."""
    control.assert_host()
    require_inert(masked=False)
    require_dependencies(Paths(), present=False)
    control.run_fixed("/usr/bin/systemctl", "mask", "--runtime",
                      control.SOCKET, control.SERVICE)
    require_inert(masked=True)


def install(paths: Paths, authorization_id: str) -> dict:
    control.assert_host()
    require_inert(masked=True)
    require(paths.systemd.is_dir() and not paths.systemd.is_symlink() and
            paths.vault.is_dir() and not paths.vault.is_symlink() and
            not any(os.path.lexists(item) for item in (
                paths.runtime, paths.guard_unit, paths.claim,
                paths.drop(control.SERVICE), paths.drop(control.SOCKET))) and
            all(not os.path.lexists(paths.drop_directory(unit)) for unit in
                (control.SERVICE, control.SOCKET)),
            "GUARD_INSTALL_COLLISION")
    worker = source_bytes(paths)
    config = canonical(config_value(authorization_id))
    paths.runtime.mkdir(mode=0o700)
    fsync_dir(paths.runtime.parent)
    exclusive(paths.worker, worker, 0o600)
    exclusive(paths.config, config, 0o600)
    exclusive(paths.guard_unit, guard_unit_bytes(paths), 0o644)
    for unit in (control.SERVICE, control.SOCKET):
        folder = paths.drop_directory(unit)
        folder.mkdir(mode=0o755)
        fsync_dir(folder.parent)
        exclusive(paths.drop(unit), DROPIN.encode(), 0o644)
    control.run_fixed("/usr/bin/systemctl", "daemon-reload")
    require_inert(masked=True)
    control.run_fixed("/usr/bin/systemctl", "start", GUARD)
    bound = verify_guard(paths, authorization_id)
    control.run_fixed("/usr/bin/systemctl", "unmask", "--runtime",
                      control.SOCKET, control.SERVICE)
    require_inert(masked=False)
    require_dependencies(paths, present=True)
    verify(paths, authorization_id)
    return bound


def release(paths: Paths, authorization_id: str) -> None:
    control.assert_host()
    require_inert(masked=True)
    verify_guard(paths, authorization_id)
    for unit in (control.SERVICE, control.SOCKET):
        path = paths.drop(unit)
        require(regular(path, mode=0o644) == DROPIN.encode(),
                "GUARD_DROPIN_DRIFT")
        path.unlink()
        fsync_dir(path.parent)
        path.parent.rmdir()  # Fails closed if another drop-in appeared.
        fsync_dir(paths.systemd)
    control.run_fixed("/usr/bin/systemctl", "daemon-reload")
    control.run_fixed("/usr/bin/systemctl", "stop", GUARD)
    require(control.show(GUARD, "ActiveState").get("ActiveState") == "inactive",
            "GUARD_NOT_STOPPED")
    control.run_fixed("/usr/bin/systemctl", "unmask", "--runtime",
                      control.SOCKET, control.SERVICE)
    require_inert(masked=False)
    require_dependencies(paths, present=False)
    # Retain the one-shot claim and guard unit/source as forensic evidence.
