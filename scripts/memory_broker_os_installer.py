#!/usr/bin/env python3
"""Fixed-purpose, DEV-only privileged broker installer and rollback.

This trusted-main control is never invoked on a VM by B1b-2a. Mutating
operations additionally require a root-owned B1b-2b authorization marker,
which B1b-2a does not create. Candidate code is executed only as the newly
confined broker account during explicit synthetic-state provisioning.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import json
import os
import re
import socket
import stat
import subprocess
import sys
import uuid
from dataclasses import dataclass
from pathlib import Path
from urllib.request import ProxyHandler, Request, build_opener

if globals().get("__package__"):
    from scripts import memory_broker_os_release as release
else:  # Direct trusted execution, including an in-memory module preloaded by CI.
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
PROJECT = "lilith-agent-260823-27389"
ZONE = "asia-southeast1-b"
INSTANCE_ID = "7687007163730582258"
HOSTNAME = f"{release.DEV_HOST}.{ZONE}.c.{PROJECT}.internal"
MACHINE_ID = release.DEV_MACHINE_ID
SELECTED_RELEASE_SHA = "817a83e44cec8965479fd97fc30b7a0b3ae49ab2"
SELECTED_ARCHIVE_SHA256 = "b4cb4c1412908c1702d9cdf00717dff77574e70fc47abf31f05ff782eca04d87"
SELECTED_MANIFEST_SHA256 = "7a46ac83001411a29b1bc4be7e0f91f09c5879967386c452b2620e23d16e4614"
OWNER_ACTOR = "rpahasara"
STAGE_I = "B1B2B_I"
STAGE_II = "B1B2B_II"
STAGE_III = "B1B2B_III"
ROLLBACK_STAGE = "B1B2B_ROLLBACK"
PROD_INSTANCE_ID = "1332996232081478576"
METADATA_ROOT = "http://169.254.169.254/computeMetadata/v1/"


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

    @property
    def used_authorization(self) -> Path:
        return self.config / "b1b2b-authorization.used.json"

    @property
    def identities(self) -> Path:
        return self.config / "identities.json"


LIVE = Paths()


def _metadata(key: str) -> str:
    request = Request(METADATA_ROOT + key, headers={"Metadata-Flavor": "Google"})
    with build_opener(ProxyHandler({})).open(request, timeout=5) as response:
        if response.headers.get("Metadata-Flavor") != "Google":
            raise InstallError("UNTRUSTED_METADATA")
        return response.read(256).decode("ascii", "strict").strip()


def assert_dev_host(*, hostname: str | None = None, machine_id: str | None = None, metadata=None) -> None:
    """Require independent VM metadata and local identity to agree exactly."""
    hostname = hostname if hostname is not None else socket.getfqdn()
    machine_id = machine_id if machine_id is not None else Path("/etc/machine-id").read_text(encoding="ascii").strip()
    lookup = metadata or _metadata
    try:
        observed = {key: lookup(key) for key in ("project/project-id", "instance/zone", "instance/id", "instance/name")}
    except (OSError, UnicodeError, ValueError) as exc:
        raise InstallError("CLOUD_IDENTITY_UNAVAILABLE") from exc
    if hostname.startswith("lilith-01") or observed["instance/name"] == "lilith-01" or observed["instance/id"] == PROD_INSTANCE_ID:
        raise InstallError("PROD_HOST_FORBIDDEN")
    expected = {
        "project/project-id": PROJECT,
        "instance/zone": f"projects/763184673487/zones/{ZONE}",
        "instance/id": INSTANCE_ID,
        "instance/name": release.DEV_HOST,
    }
    if observed != expected or hostname != HOSTNAME or machine_id != MACHINE_ID:
        raise InstallError("PINNED_DEV_IDENTITY_REQUIRED")


def require_root() -> None:
    if not hasattr(os, "geteuid") or os.geteuid() != 0:
        raise InstallError("ROOT_REQUIRED")


def _authorization_value(sha: str, stage: str, issued_at: datetime, authorization_id: str) -> dict:
    return {
        "schemaVersion": 2, "purpose": "B1B2B_DEV_FIRST_INSTALL",
        "project": PROJECT, "zone": ZONE, "instanceId": INSTANCE_ID,
        "hostname": HOSTNAME, "machineId": MACHINE_ID,
        "candidateSha": sha, "authorityMode": "SYNTHETIC_ONLY",
        "canonicalCapability": "DISABLED", "allowedStage": stage,
        "ownerActor": OWNER_ACTOR, "authorizationId": authorization_id,
        "issuedAt": issued_at.isoformat(timespec="seconds").replace("+00:00", "Z"),
        "expiresAt": (issued_at + timedelta(minutes=30)).isoformat(timespec="seconds").replace("+00:00", "Z"),
    }


def require_authorization(paths: Paths, sha: str, stage: str = STAGE_I, *, now: datetime | None = None) -> dict:
    marker = paths.authorization
    if marker.is_symlink() or not marker.is_file():
        raise InstallError("B1B2B_AUTHORIZATION_MISSING")
    metadata = marker.stat()
    if metadata.st_uid != 0 or stat.S_IMODE(metadata.st_mode) != 0o600:
        raise InstallError("B1B2B_AUTHORIZATION_NOT_ROOT_OWNED")
    try:
        value = json.loads(marker.read_text(encoding="utf-8"))
        issued = datetime.fromisoformat(value["issuedAt"].replace("Z", "+00:00"))
        expires = datetime.fromisoformat(value["expiresAt"].replace("Z", "+00:00"))
        authorization_id = value["authorizationId"]
    except (KeyError, ValueError, TypeError, AttributeError) as exc:
        raise InstallError("B1B2B_AUTHORIZATION_MALFORMED") from exc
    if not isinstance(authorization_id, str) or not re.fullmatch(r"[0-9a-f]{32}", authorization_id):
        raise InstallError("B1B2B_AUTHORIZATION_ID_INVALID")
    if issued.tzinfo is None or expires != issued + timedelta(minutes=30):
        raise InstallError("B1B2B_AUTHORIZATION_WINDOW_INVALID")
    observed_now = now or datetime.now(timezone.utc)
    if observed_now < issued or observed_now >= expires:
        raise InstallError("B1B2B_AUTHORIZATION_EXPIRED")
    if value != _authorization_value(sha, stage, issued, authorization_id):
        raise InstallError("B1B2B_AUTHORIZATION_MISMATCH")
    return value


def consume_authorization(paths: Paths, sha: str, stage: str) -> None:
    """Claim once before the first operational mutation; preserve the record."""
    require_authorization(paths, sha, stage)
    used = paths.used_authorization
    if used.exists() or used.is_symlink():
        raise InstallError("B1B2B_AUTHORIZATION_REPLAY")
    os.replace(paths.authorization, used)


def staged_paths(sha: str) -> tuple[Path, Path]:
    if not release.SHA40.fullmatch(sha):
        raise InstallError("INVALID_CANDIDATE_SHA")
    prefix = f"lilith-broker-os-{sha}"
    return Path("/tmp") / (prefix + ".tar.gz"), Path("/tmp") / (prefix + ".attestation.json")


def assert_selected_release(sha: str) -> None:
    if sha != SELECTED_RELEASE_SHA:
        raise InstallError("UNAPPROVED_RELEASE_SHA")


def verify_selected_archive(archive: Path, attestation: Path, sha: str) -> tuple[dict, dict[str, bytes]]:
    assert_selected_release(sha)
    manifest, payloads = release.verify_archive(archive, attestation, sha)
    if (manifest.get("candidateSha") != sha or manifest.get("deploymentEnvironment") != "dev"
            or release.digest(archive.read_bytes()) != SELECTED_ARCHIVE_SHA256
            or release.digest(release.canonical(manifest)) != SELECTED_MANIFEST_SHA256):
        raise InstallError("SELECTED_RELEASE_MISMATCH")
    return manifest, payloads


def _unit_absent(name: str) -> None:
    result = subprocess.run(
        ("/usr/bin/systemctl", "show", name,
         "--property=LoadState,ActiveState,FragmentPath,DropInPaths,UnitFileState,Names",
         "--no-pager"),
        check=True, capture_output=True, text=True, timeout=10,
    )
    fields = dict(line.split("=", 1) for line in result.stdout.splitlines() if "=" in line)
    if (fields.get("LoadState") != "not-found" or fields.get("ActiveState") != "inactive"
            or fields.get("FragmentPath") or fields.get("DropInPaths")
            or fields.get("UnitFileState") not in ("", None)
            or fields.get("Names") not in ("", name)):
        raise InstallError("SYSTEMD_UNIT_COLLISION")


def assert_first_install_preflight(paths: Paths, *, marker_expected: bool) -> None:
    """Reject all pre-existing operational state before account creation."""
    if any(inspect_accounts()):
        raise InstallError("FIRST_INSTALL_ACCOUNT_COLLISION")
    for path in (paths.opt, paths.state, paths.runtime, paths.service, paths.socket, paths.tmpfiles,
                 Path(str(paths.service) + ".d"), Path(str(paths.socket) + ".d")):
        if path.exists() or path.is_symlink() or os.path.ismount(path):
            raise InstallError("FIRST_INSTALL_PATH_COLLISION")
    if marker_expected:
        if paths.config.is_symlink() or not paths.config.is_dir() or {p.name for p in paths.config.iterdir()} != {"b1b2b-authorization.json"}:
            raise InstallError("FIRST_INSTALL_MARKER_DIRECTORY_COLLISION")
        meta = paths.config.stat()
        if meta.st_uid != 0 or meta.st_gid != 0 or stat.S_IMODE(meta.st_mode) != 0o755:
            raise InstallError("FIRST_INSTALL_MARKER_DIRECTORY_OWNERSHIP")
    elif paths.config.exists() or paths.config.is_symlink():
        raise InstallError("FIRST_INSTALL_CONFIG_COLLISION")
    if paths == LIVE:
        runtime = Path("/run")
        result = subprocess.run(
            ("/usr/bin/findmnt", "-T", str(runtime), "-no", "TARGET,FSTYPE"),
            check=True, capture_output=True, text=True, timeout=10,
        )
        if result.stdout.strip().split() != ["/run", "tmpfs"]:
            raise InstallError("RUNTIME_PARENT_NOT_TMPFS")
        for root in ("/run/systemd/system", "/usr/lib/systemd/system", "/lib/systemd/system"):
            for name in (SERVICE, SOCKET):
                path = Path(root) / name
                if path.exists() or path.is_symlink() or Path(str(path) + ".d").exists():
                    raise InstallError("SYSTEMD_UNIT_SHADOW_COLLISION")
        _unit_absent(SERVICE)
        _unit_absent(SOCKET)


def authorize_dev(paths: Paths, sha: str, archive: Path, attestation: Path, *, stage: str = STAGE_I) -> dict:
    """Separate, owner-invoked first-run ceremony; never starts a service."""
    assert_dev_host()
    require_root()
    assert_selected_release(sha)
    if stage != STAGE_I:
        raise InstallError("STAGE_NOT_AVAILABLE")
    if (archive, attestation) != staged_paths(sha) or archive.is_symlink() or attestation.is_symlink():
        raise InstallError("UNEXPECTED_STAGING_PATH")
    assert_first_install_preflight(paths, marker_expected=False)
    verify_selected_archive(archive, attestation, sha)
    issued = datetime.now(timezone.utc)
    value = _authorization_value(sha, stage, issued, uuid.uuid4().hex)
    _ensure_dir(paths.config, 0, 0, 0o755)
    _write_fixed(paths.authorization, release.canonical(value), 0, 0, 0o600)
    return {"status": "STAGE_I_AUTHORIZED_ONLY", "authorizationId": value["authorizationId"],
            "expiresAt": value["expiresAt"], "candidateSha": sha}


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


def provision_accounts() -> tuple[int, int, int, int, int]:
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
    return broker.pw_uid, broker.pw_gid, relay.pw_uid, relay.pw_gid, group.gr_gid


def verify_account_contract() -> dict:
    """Assert OS-assigned local identities after creation and on later stages."""
    inspect_accounts()
    broker = pwd.getpwnam(BROKER)
    relay = pwd.getpwnam(RELAY)
    ipc = grp.getgrnam(IPC_GROUP)
    if (broker.pw_uid >= 1000 or relay.pw_uid >= 1000 or broker.pw_uid == relay.pw_uid
            or broker.pw_gid == relay.pw_gid or Path("/nonexistent").exists()
            or set(ipc.gr_mem) != {RELAY}):
        raise InstallError("ACCOUNT_IDENTITY_CONTRACT")
    local_lines = Path("/etc/passwd").read_text(encoding="utf-8").splitlines()
    shadow_lines = Path("/etc/shadow").read_text(encoding="utf-8").splitlines()
    for name, user in ((BROKER, broker), (RELAY, relay)):
        if sum(line.startswith(name + ":") for line in local_lines) != 1:
            raise InstallError("ACCOUNT_NOT_LOCAL")
        shadow = [line.split(":", 2)[1] for line in shadow_lines if line.startswith(name + ":")]
        if len(shadow) != 1 or not shadow[0].startswith(("!", "*")):
            raise InstallError("ACCOUNT_PASSWORD_NOT_LOCKED")
        if user.pw_dir != "/nonexistent" or user.pw_shell != "/usr/sbin/nologin":
            raise InstallError("ACCOUNT_LOGIN_CONTRACT")
        for path in (Path("/etc/ssh/authorized_keys") / name, Path("/home") / name):
            if path.exists() or path.is_symlink():
                raise InstallError("ACCOUNT_SSH_OR_HOME_COLLISION")
        sudo = subprocess.run(("/usr/bin/sudo", "-n", "-l", "-U", name),
                              capture_output=True, text=True, timeout=10)
        denied = f"User {name} is not allowed to run sudo on {release.DEV_HOST}."
        if sudo.stdout.strip() != denied or sudo.stderr.strip():
            raise InstallError("ACCOUNT_SUDO_PRIVILEGE")
    return {
        "schemaVersion": 1, "brokerUid": broker.pw_uid, "brokerGid": broker.pw_gid,
        "relayUid": relay.pw_uid, "relayGid": relay.pw_gid, "ipcGid": ipc.gr_gid,
        "broker": BROKER, "relay": RELAY, "ipcGroup": IPC_GROUP,
    }


def assert_recorded_accounts(paths: Paths) -> dict:
    path = paths.identities
    if path.is_symlink() or not path.is_file():
        raise InstallError("ACCOUNT_RECORD_MISSING")
    metadata = path.stat()
    if metadata.st_uid != 0 or metadata.st_gid != 0 or stat.S_IMODE(metadata.st_mode) != 0o600:
        raise InstallError("ACCOUNT_RECORD_OWNERSHIP")
    recorded = json.loads(path.read_text(encoding="utf-8"))
    if recorded != verify_account_contract():
        raise InstallError("ACCOUNT_MAPPING_CHANGED")
    return recorded


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
        (paths.config, {"b1b2b-authorization.json", "b1b2b-authorization.used.json",
                        "dev.json", "identities.json", "previous-release"}),
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
    assert_selected_release(sha)
    require_authorization(paths, sha, STAGE_I)
    if (archive, attestation) != staged_paths(sha) or archive.is_symlink() or attestation.is_symlink():
        raise InstallError("UNEXPECTED_STAGING_PATH")
    assert_first_install_preflight(paths, marker_expected=True)
    manifest, payloads = verify_selected_archive(archive, attestation, sha)
    _has_group, has_broker, _has_relay = inspect_accounts()
    for path in (paths.opt, paths.config, paths.state, paths.service, paths.socket, paths.tmpfiles):
        if path.is_symlink():
            raise InstallError("INSTALL_TARGET_SYMLINK")
    _current_target(paths)
    inspect_existing_state(paths, broker_account_present=has_broker)
    consume_authorization(paths, sha, STAGE_I)
    broker_uid, broker_gid, relay_uid, relay_gid, ipc_gid = provision_accounts()
    identities = verify_account_contract()
    if (broker_uid, broker_gid, relay_uid, relay_gid, ipc_gid) != (
            identities["brokerUid"], identities["brokerGid"], identities["relayUid"],
            identities["relayGid"], identities["ipcGid"]):
        raise InstallError("ACCOUNT_MAPPING_CHANGED")
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
    _write_fixed(paths.identities, release.canonical(identities), 0, 0, 0o600)
    _provision_synthetic_state(paths, release_dir)
    for name, target in ((SERVICE, paths.service), (SOCKET, paths.socket), ("lilith-memory-broker.tmpfiles.conf", paths.tmpfiles)):
        _write_fixed(target, payloads["assets/" + name], 0, 0, 0o644)
    _switch_release(paths, sha)
    return {"status": "INSTALLED_INACTIVE", "candidateSha": sha, "brokerUid": broker_uid}


def activate_dev(paths: Paths, sha: str) -> None:
    assert_dev_host()
    require_root()
    assert_selected_release(sha)
    require_authorization(paths, sha, STAGE_II)
    assert_recorded_accounts(paths)
    if _current_target(paths) != f"releases/{sha}":
        raise InstallError("ACTIVE_RELEASE_MISMATCH")
    _fixed_run("/usr/bin/systemd-tmpfiles", "--create", "--prefix=/run/lilith-memory")
    _fixed_run("/usr/bin/systemctl", "daemon-reload")
    _fixed_run("/usr/bin/systemctl", "enable", "--now", SOCKET)


def rollback_dev(paths: Paths, sha: str) -> dict:
    assert_dev_host()
    require_root()
    assert_selected_release(sha)
    require_authorization(paths, sha, ROLLBACK_STAGE)
    assert_recorded_accounts(paths)
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
    parser.add_argument("operation", choices=("verify", "authorize-dev", "install-dev", "activate-dev", "status-dev", "rollback-dev"))
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
        assert_selected_release(args.candidate_sha)
        manifest, _ = verify_selected_archive(archive, attestation, args.candidate_sha)
        print(json.dumps({"status": "VERIFIED", "candidateSha": manifest["candidateSha"]}, sort_keys=True))
    elif args.operation == "authorize-dev":
        print(json.dumps(authorize_dev(LIVE, args.candidate_sha, archive, attestation), sort_keys=True))
    elif args.operation == "install-dev":
        print(json.dumps(install_dev(LIVE, args.candidate_sha, archive, attestation), sort_keys=True))
    else:
        activate_dev(LIVE, args.candidate_sha)
        print(json.dumps({"status": "ACTIVATED", "candidateSha": args.candidate_sha}, sort_keys=True))


if __name__ == "__main__":
    main()
