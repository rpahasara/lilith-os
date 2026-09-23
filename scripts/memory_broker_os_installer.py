#!/usr/bin/env python3
"""Fixed-purpose, DEV-only privileged broker installer and rollback.

This trusted-main control is never invoked on a VM by B1b-2a. Mutating
operations additionally require a root-owned B1b-2b authorization marker,
which B1b-2a does not create. Candidate code is executed only as the newly
confined broker account during explicit synthetic-state provisioning.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import socket
import stat
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

try:
    from scripts import memory_broker_os_release as release
except ImportError:  # Direct execution after trusted standalone installation.
    import memory_broker_os_release as release

try:  # The pure policy is testable on Windows; host operations are Linux-only.
    import grp
    import pwd
except ImportError:  # pragma: no cover - exercised by local Windows tests
    grp = None
    pwd = None


BROKER = "lilith-memory-broker"
RELAY = "lilith-memory-relay"
IPC_GROUP = "lilith-memory-ipc"
SERVICE = "lilith-memory-broker.service"
SOCKET = "lilith-memory-broker.socket"


class InstallError(RuntimeError):
    pass


@dataclass(frozen=True)
class Paths:
    opt: Path = Path("/opt/lilith-memory-broker")
    config: Path = Path("/etc/lilith-memory-broker")
    state: Path = Path("/var/lib/lilith-memory-broker")
    runtime: Path = Path("/run/lilith-memory")
    service: Path = Path("/etc/systemd/system/lilith-memory-broker.service")
    socket: Path = Path("/etc/systemd/system/lilith-memory-broker.socket")
    tmpfiles: Path = Path("/etc/tmpfiles.d/lilith-memory-broker.conf")

    @property
    def releases(self) -> Path:
        return self.opt / "releases"

    @property
    def current(self) -> Path:
        return self.opt / "current"

    @property
    def previous(self) -> Path:
        return self.config / "previous-release"

    @property
    def dev_config(self) -> Path:
        return self.config / "dev.json"

    @property
    def authorization(self) -> Path:
        return self.config / "b1b2b-authorization.json"


LIVE = Paths()


def assert_dev_host(*, hostname: str | None = None, machine_id: str | None = None) -> None:
    hostname = hostname or socket.gethostname()
    machine_id = machine_id or Path("/etc/machine-id").read_text(encoding="ascii").strip()
    if hostname != release.DEV_HOST or machine_id != release.DEV_MACHINE_ID:
        raise InstallError("PINNED_DEV_HOST_REQUIRED")


def require_root() -> None:
    if not hasattr(os, "geteuid") or os.geteuid() != 0:
        raise InstallError("ROOT_REQUIRED")


def require_authorization(paths: Paths, sha: str) -> None:
    marker = paths.authorization
    if marker.is_symlink() or not marker.is_file():
        raise InstallError("B1B2B_AUTHORIZATION_MISSING")
    metadata = marker.stat()
    if metadata.st_uid != 0 or stat.S_IMODE(metadata.st_mode) != 0o600:
        raise InstallError("B1B2B_AUTHORIZATION_NOT_ROOT_OWNED")
    value = json.loads(marker.read_text(encoding="utf-8"))
    if not isinstance(value, dict) or value != {
        "schemaVersion": 1, "candidateSha": sha,
        "host": release.DEV_HOST, "machineId": release.DEV_MACHINE_ID,
        "scope": "B1B2B_DEV_OS_ISOLATION_ONLY",
    }:
        raise InstallError("B1B2B_AUTHORIZATION_MISMATCH")


def staged_paths(sha: str) -> tuple[Path, Path]:
    if not release.SHA40.fullmatch(sha):
        raise InstallError("INVALID_CANDIDATE_SHA")
    prefix = f"lilith-broker-os-{sha}"
    return Path("/tmp") / (prefix + ".tar.gz"), Path("/tmp") / (prefix + ".attestation.json")


def _fixed_run(*args: str, cwd: Path | None = None) -> None:
    subprocess.run(args, cwd=cwd, check=True, timeout=120, env={
        "PATH": "/usr/sbin:/usr/bin:/sbin:/bin", "LANG": "C", "HOME": "/nonexistent",
    })


def _lookup_user(name: str):
    try:
        return pwd.getpwnam(name)
    except KeyError:
        return None


def _lookup_group(name: str):
    try:
        return grp.getgrnam(name)
    except KeyError:
        return None


def inspect_accounts() -> tuple[bool, bool, bool]:
    """Reject collisions; no correction of an unexpected existing identity."""
    group = _lookup_group(IPC_GROUP)
    broker = _lookup_user(BROKER)
    relay = _lookup_user(RELAY)
    for name, user in ((BROKER, broker), (RELAY, relay)):
        if user is None:
            continue
        primary = _lookup_group(name)
        if (user.pw_name != name or user.pw_shell != "/usr/sbin/nologin" or
                user.pw_dir != "/nonexistent" or primary is None or user.pw_gid != primary.gr_gid or
                user.pw_uid >= 1000):
            raise InstallError("ACCOUNT_COLLISION")
        groups = set(os.getgrouplist(name, user.pw_gid))
        allowed = {user.pw_gid} | ({group.gr_gid} if name == RELAY and group else set())
        if groups != allowed:
            raise InstallError("ACCOUNT_SUPPLEMENTARY_GROUP_COLLISION")
    if group and (group.gr_name != IPC_GROUP or (group.gr_mem and set(group.gr_mem) != {RELAY})):
        raise InstallError("IPC_GROUP_COLLISION")
    return group is not None, broker is not None, relay is not None


def provision_accounts() -> tuple[int, int, int]:
    has_group, has_broker, has_relay = inspect_accounts()
    if not has_group:
        _fixed_run("/usr/sbin/groupadd", "--system", IPC_GROUP)
    if not has_broker:
        _fixed_run("/usr/sbin/useradd", "--system", "--user-group", "--no-create-home", "--home-dir", "/nonexistent", "--shell", "/usr/sbin/nologin", BROKER)
    if not has_relay:
        _fixed_run("/usr/sbin/useradd", "--system", "--user-group", "--no-create-home", "--home-dir", "/nonexistent", "--shell", "/usr/sbin/nologin", RELAY)
        _fixed_run("/usr/sbin/usermod", "-G", IPC_GROUP, RELAY)
    inspect_accounts()
    broker = pwd.getpwnam(BROKER)
    relay = pwd.getpwnam(RELAY)
    group = grp.getgrnam(IPC_GROUP)
    if broker.pw_uid == relay.pw_uid or broker.pw_uid == pwd.getpwnam("lilith").pw_uid:
        raise InstallError("ACCOUNT_UID_COLLISION")
    return broker.pw_uid, broker.pw_gid, group.gr_gid


def _ensure_dir(path: Path, uid: int, gid: int, mode: int) -> None:
    if path.is_symlink():
        raise InstallError("DIRECTORY_SYMLINK")
    if path.exists():
        meta = path.stat()
        if not path.is_dir() or meta.st_uid != uid or meta.st_gid != gid or stat.S_IMODE(meta.st_mode) != mode:
            raise InstallError("DIRECTORY_COLLISION")
        return
    path.mkdir(mode=mode)
    os.chown(path, uid, gid)
    os.chmod(path, mode)


def _write_fixed(path: Path, data: bytes, uid: int, gid: int, mode: int) -> None:
    if path.is_symlink():
        raise InstallError("FILE_SYMLINK")
    if path.exists():
        meta = path.stat()
        if not path.is_file() or path.read_bytes() != data or meta.st_uid != uid or meta.st_gid != gid or stat.S_IMODE(meta.st_mode) != mode:
            raise InstallError("FILE_COLLISION")
        return
    fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY | getattr(os, "O_NOFOLLOW", 0), mode)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
    except Exception:
        raise
    os.chown(path, uid, gid)
    os.chmod(path, mode)


def _config_bytes(sha: str) -> bytes:
    value = {
        "deploymentEnvironment": "dev", "authorityMode": "SYNTHETIC_ONLY",
        "stateProfile": "B1B2_SYNTHETIC_DEV_V1", "canonicalCapability": "DISABLED",
        "expectedHost": release.DEV_HOST, "machineId": release.DEV_MACHINE_ID,
        "releaseSha": sha, "logicalOwnerId": "owner.ravindu.v1",
        "accessIdentity": "user:synthetic-owner@example.invalid",
        "fixtureId": "fixture.b1b1.synthetic-codename.v1",
        "fixtureFingerprint": release.FIXTURE_FINGERPRINT,
        "credentialFingerprint": release.CREDENTIAL_FINGERPRINT,
        "rpId": "owner.lilith.invalid", "origin": "https://owner.lilith.invalid",
        "ownerSchemaFingerprint": release.OWNER_SCHEMA_FINGERPRINT,
        "evidenceSchemaFingerprint": release.EVIDENCE_SCHEMA_FINGERPRINT,
        "custody": {name: "ABSENT" for name in ("cognitiveDb", "privacyDb", "actorKey", "privacyKey", "containmentKey")},
    }
    return release.canonical(value)


def _current_target(paths: Paths) -> str | None:
    if not paths.current.exists() and not paths.current.is_symlink():
        return None
    if not paths.current.is_symlink():
        raise InstallError("CURRENT_POINTER_NOT_SYMLINK")
    target = os.readlink(paths.current)
    if not re.fullmatch(r"releases/[0-9a-f]{40}", target):
        raise InstallError("CURRENT_POINTER_OUTSIDE_RELEASES")
    if (paths.opt / target).is_symlink() or not (paths.opt / target).is_dir():
        raise InstallError("CURRENT_POINTER_TARGET_MISSING")
    return target


def inspect_existing_state(paths: Paths, *, broker_account_present: bool) -> None:
    """Refuse unknown operational data before creating accounts or directories."""
    expected = (
        (paths.opt, {"releases", "current"}),
        (paths.config, {"b1b2b-authorization.json", "dev.json", "previous-release"}),
        (paths.state, {"owner-control", "state"}),
        (paths.state / "owner-control", {"owner_control.db", "owner_control.db-wal", "owner_control.db-shm"}),
        (paths.state / "state", {"synthetic_evidence.db", "synthetic_evidence.db-wal", "synthetic_evidence.db-shm"}),
    )
    for directory, allowed in expected:
        if directory.is_symlink():
            raise InstallError("STATE_DIRECTORY_SYMLINK")
        if not directory.exists():
            continue
        if not directory.is_dir():
            raise InstallError("STATE_DIRECTORY_COLLISION")
        for child in directory.iterdir():
            if child.name not in allowed or child.is_symlink():
                raise InstallError("UNEXPECTED_STATE_ENTRY")
    if paths.state.exists() and not broker_account_present:
        raise InstallError("STATE_WITHOUT_BROKER_ACCOUNT")
    if paths.releases.exists():
        if paths.releases.is_symlink() or not paths.releases.is_dir():
            raise InstallError("RELEASE_DIRECTORY_COLLISION")
        for child in paths.releases.iterdir():
            if not release.SHA40.fullmatch(child.name) or child.is_symlink() or not child.is_dir():
                raise InstallError("UNEXPECTED_RELEASE_ENTRY")


def _switch_release(paths: Paths, sha: str) -> None:
    target = f"releases/{sha}"
    previous = _current_target(paths)
    if previous == target:
        return
    prior = (previous or "NONE").encode() + b"\n"
    if paths.previous.exists():
        meta = paths.previous.lstat()
        if paths.previous.is_symlink() or not paths.previous.is_file() or meta.st_uid != 0 or stat.S_IMODE(meta.st_mode) != 0o600:
            raise InstallError("PREVIOUS_POINTER_COLLISION")
        with paths.previous.open("wb") as stream:
            stream.write(prior)
            stream.flush()
            os.fsync(stream.fileno())
    else:
        _write_fixed(paths.previous, prior, 0, 0, 0o600)
    temporary = paths.opt / (".current-" + sha)
    if temporary.exists() or temporary.is_symlink():
        raise InstallError("POINTER_COLLISION")
    os.symlink(target, temporary)
    os.replace(temporary, paths.current)


def _provision_synthetic_state(paths: Paths, release_dir: Path) -> None:
    owner = paths.state / "owner-control/owner_control.db"
    evidence = paths.state / "state/synthetic_evidence.db"
    if owner.exists() != evidence.exists():
        raise InstallError("PARTIAL_SYNTHETIC_STATE")
    if owner.exists():
        return  # Normal startup validates both; provisioning never resets them.
    code = (
        "import json,os,socket; from pathlib import Path; "
        "from lilith_memory.owner_proof import OwnerCredentialV1; "
        "from lilith_memory_broker.dev_config import DevConfig; "
        "from lilith_memory_broker.dev_state import DevOwnerControlState; "
        "from lilith_memory_broker.synthetic_evidence import SyntheticEvidenceStore; "
        "c=DevConfig.from_file(Path('/etc/lilith-memory-broker/dev.json')); "
        "c.validate_runtime(hostname=socket.gethostname(),machine_id=Path('/etc/machine-id').read_text().strip(),release_sha=c.release_sha); "
        "k=OwnerCredentialV1.from_dict(json.loads(Path('assets/public-synthetic-credential.json').read_text())); "
        "DevOwnerControlState.provision(Path('/var/lib/lilith-memory-broker/owner-control/owner_control.db'),c,k,expected_uid=os.getuid()); "
        "SyntheticEvidenceStore.provision(Path('/var/lib/lilith-memory-broker/state/synthetic_evidence.db'),release_sha=c.release_sha,expected_uid=os.getuid())"
    )
    _fixed_run("/usr/sbin/runuser", "-u", BROKER, "--", "/usr/bin/env", "LILITH_ENV=dev", "PYTHONNOUSERSITE=1", str(release_dir / "venv/bin/python"), "-B", "-c", code, cwd=release_dir)


def install_dev(paths: Paths, sha: str, archive: Path, attestation: Path) -> dict:
    assert_dev_host()
    require_root()
    require_authorization(paths, sha)
    if (archive, attestation) != staged_paths(sha) or archive.is_symlink() or attestation.is_symlink():
        raise InstallError("UNEXPECTED_STAGING_PATH")
    manifest, payloads = release.verify_archive(archive, attestation, sha)
    _has_group, has_broker, _has_relay = inspect_accounts()  # Fail on known collisions before any mutation.
    for path in (paths.opt, paths.config, paths.state, paths.service, paths.socket, paths.tmpfiles):
        if path.is_symlink():
            raise InstallError("INSTALL_TARGET_SYMLINK")
    _current_target(paths)
    inspect_existing_state(paths, broker_account_present=has_broker)
    broker_uid, broker_gid, _ipc_gid = provision_accounts()
    _ensure_dir(paths.opt, 0, 0, 0o755)
    _ensure_dir(paths.releases, 0, 0, 0o755)
    _ensure_dir(paths.config, 0, 0, 0o755)
    _ensure_dir(paths.state, broker_uid, broker_gid, 0o700)
    _ensure_dir(paths.state / "owner-control", broker_uid, broker_gid, 0o700)
    _ensure_dir(paths.state / "state", broker_uid, broker_gid, 0o700)
    release_dir = paths.releases / sha
    if not release_dir.exists():
        staging = paths.releases / (sha + ".staging")
        if staging.exists() or staging.is_symlink():
            raise InstallError("RELEASE_STAGING_COLLISION")
        _ensure_dir(staging, 0, 0, 0o755)
        for relative, data in sorted(payloads.items()):
            target = staging.joinpath(*relative.split("/"))
            if target.parent != staging and not target.parent.exists():
                target.parent.mkdir(parents=True, mode=0o755)
            _write_fixed(target, data, 0, 0, 0o644)
        _write_fixed(staging / "release-manifest.json", release.canonical(manifest), 0, 0, 0o644)
        _fixed_run("/usr/bin/python3", "-m", "venv", str(staging / "venv"))
        _fixed_run(str(staging / "venv/bin/python"), "-m", "pip", "install", "--no-index", "--no-input", "--disable-pip-version-check", "--require-hashes", "--find-links", str(staging / "wheels"), "-r", str(staging / "requirements.lock"))
        staging.rename(release_dir)
    else:
        if release_dir.is_symlink() or not release_dir.is_dir() or (release_dir / "release-manifest.json").read_bytes() != release.canonical(manifest):
            raise InstallError("EXISTING_RELEASE_COLLISION")
    _write_fixed(paths.dev_config, _config_bytes(sha), 0, broker_gid, 0o640)
    _provision_synthetic_state(paths, release_dir)
    for name, target in ((SERVICE, paths.service), (SOCKET, paths.socket), ("lilith-memory-broker.tmpfiles.conf", paths.tmpfiles)):
        _write_fixed(target, payloads["assets/" + name], 0, 0, 0o644)
    _switch_release(paths, sha)
    return {"status": "INSTALLED_INACTIVE", "candidateSha": sha, "brokerUid": broker_uid}


def activate_dev(paths: Paths, sha: str) -> None:
    assert_dev_host()
    require_root()
    require_authorization(paths, sha)
    if _current_target(paths) != f"releases/{sha}":
        raise InstallError("ACTIVE_RELEASE_MISMATCH")
    _fixed_run("/usr/bin/systemd-tmpfiles", "--create", "--prefix=/run/lilith-memory")
    _fixed_run("/usr/bin/systemctl", "daemon-reload")
    _fixed_run("/usr/bin/systemctl", "enable", "--now", SOCKET)


def rollback_dev(paths: Paths, sha: str) -> dict:
    assert_dev_host()
    require_root()
    require_authorization(paths, sha)
    previous = paths.previous
    if previous.is_symlink() or not previous.is_file() or previous.stat().st_uid != 0 or stat.S_IMODE(previous.stat().st_mode) != 0o600:
        raise InstallError("PREVIOUS_POINTER_INVALID")
    value = previous.read_text(encoding="ascii").strip()
    current = _current_target(paths)
    if current != f"releases/{sha}":
        raise InstallError("ROLLBACK_CURRENT_SHA_MISMATCH")
    if value != "NONE" and (not re.fullmatch(r"releases/[0-9a-f]{40}", value) or (paths.opt / value).is_symlink() or not (paths.opt / value).is_dir()):
        raise InstallError("PREVIOUS_POINTER_OUTSIDE_RELEASES")
    _fixed_run("/usr/bin/systemctl", "disable", "--now", SERVICE, SOCKET)
    if value == "NONE":
        if current is not None:
            paths.current.unlink()
    else:
        temporary = paths.opt / ".rollback-current"
        if temporary.exists() or temporary.is_symlink():
            raise InstallError("ROLLBACK_POINTER_COLLISION")
        os.symlink(value, temporary)
        os.replace(temporary, paths.current)
    return {"status": "INACTIVE_EVIDENCE_PRESERVED", "statePreserved": True, "accountsPreserved": True}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("operation", choices=("verify", "install-dev", "activate-dev", "status-dev", "rollback-dev"))
    parser.add_argument("--candidate-sha", required=True)
    args = parser.parse_args()
    if not release.SHA40.fullmatch(args.candidate_sha):
        parser.error("invalid candidate SHA")
    if args.operation == "status-dev":
        assert_dev_host()
        print(json.dumps({"host": release.DEV_HOST, "current": _current_target(LIVE), "accountPresent": _lookup_user(BROKER) is not None}, sort_keys=True))
        return
    if args.operation == "rollback-dev":
        print(json.dumps(rollback_dev(LIVE, args.candidate_sha), sort_keys=True))
        return
    archive, attestation = staged_paths(args.candidate_sha)
    if args.operation == "verify":
        assert_dev_host()
        manifest, _ = release.verify_archive(archive, attestation, args.candidate_sha)
        print(json.dumps({"status": "VERIFIED", "candidateSha": manifest["candidateSha"]}, sort_keys=True))
    elif args.operation == "install-dev":
        print(json.dumps(install_dev(LIVE, args.candidate_sha, archive, attestation), sort_keys=True))
    else:
        activate_dev(LIVE, args.candidate_sha)
        print(json.dumps({"status": "ACTIVATED", "candidateSha": args.candidate_sha}, sort_keys=True))


if __name__ == "__main__":
    main()
