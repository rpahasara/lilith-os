#!/usr/bin/env python3
"""Trusted-main, DEV-only Stage-II control. Never invoked by Stage-I.

The workflow streams this source to the pinned VM; it never installs this
control in the broker release. No command runs without a fresh owner dispatch.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import socket
import sqlite3
import stat
import subprocess
import sys
import uuid
from urllib.request import ProxyHandler, Request, build_opener

try:
    import pwd
    import grp
except ImportError:  # Pure control-contract tests also run on Windows.
    pwd = None
    grp = None

PROJECT = "lilith-agent-260823-27389"
ZONE = "asia-southeast1-b"
INSTANCE = "lilith-dev-01"
INSTANCE_ID = "7687007163730582258"
HOSTNAME = f"{INSTANCE}.{ZONE}.c.{PROJECT}.internal"
MACHINE_ID = "ae929170e6fa4c8ab9cc7b9547238d9d"
RELEASE = "817a83e44cec8965479fd97fc30b7a0b3ae49ab2"
OWNER = "rpahasara"
STAGE = "B1B2B_II / ACTIVATE_AND_ISOLATION_TEST"
PURPOSE = "B1B2B_DEV_RUNTIME_ISOLATION"
SERVICE = "lilith-memory-broker.service"
SOCKET = "lilith-memory-broker.socket"
ROOT = Path("/opt/lilith-memory-broker")
CONFIG = Path("/etc/lilith-memory-broker")
STATE = Path("/var/lib/lilith-memory-broker")
RUN = Path("/run/lilith-memory")
MARKER = CONFIG / "b1b2b-stage2-authorization.json"
USED = CONFIG / "b1b2b-stage2-authorization.used.json"
MANIFEST_SHA = "7a46ac83001411a29b1bc4be7e0f91f09c5879967386c452b2620e23d16e4614"
HASHES = {
    CONFIG / "dev.json": "c1787b34e5f1969fe98a0d3499c7913fde01a6eba7f2ee04f427a39cd02f27fb",
    CONFIG / "identities.json": "e1c808901bea374d7a0d16d49140125d8572012497905a690d634373a2070d23",
    Path("/etc/systemd/system/lilith-memory-broker.service"): "6a9dca54b9051cc7788587a0f37601f67e16fc07de043cbc5d64e7123ed35689",
    Path("/etc/systemd/system/lilith-memory-broker.socket"): "d9f21223b837fd4be98d3c67eb95625b00c8a0ee6922d06eb79605edb382e793",
    Path("/etc/tmpfiles.d/lilith-memory-broker.conf"): "e6139f16b001a3c36e9ff3db733f19a3a7ce06b1d0fbc923591bc17b2d4df86e",
}
OWNER_DB = STATE / "owner-control/owner_control.db"
EVIDENCE_DB = STATE / "state/synthetic_evidence.db"
OWNER_DB_SHA = "8c0c8a617b199b60eddb10d5b6123f6ec9a511646fe4d754ac1ce23881f4e69d"
EVIDENCE_DB_SHA = "b8f619e5e6ede9dc9ea8a721150ea52d7082f5eb95543b0d11453efcb9581654"
OWNER_SCHEMA = "8074e95c1a1b1de6081cc686efc10159793f7c4768f362b64e9e6a34705eb314"
EVIDENCE_SCHEMA = "c18c904a9f2b4f1c48fa3aeafb3f587a33f59f35219c872f7c33d972d996e718"
API = "lilith-os-api-dev.service"
API_APP = Path("/home/lilith/.hermes/lilith-os-dev/current/app.py")
API_APP_SHA = "bb0a4139641c0a81607263b07fa854deb34241b5fcfcdcab965c6a82dd8826d3"
API_UNIT = Path("/etc/systemd/system/lilith-os-api-dev.service")
API_WORKDIR = "/home/lilith/.hermes/lilith-os-dev/current"
API_EXECUTABLE = "/home/lilith/.hermes/lilith-os-dev/api-venv/bin/uvicorn"
API_COMMAND = API_EXECUTABLE + " app:app --host 0.0.0.0 --port 8765"
API_FILES = {
    Path("/home/lilith/.hermes/lilith-os-dev/data/canonical-runtime.json"): "65ac5077486cfe25665fc8f5815661b1653878182492a0309ec974e9394c08e7",
    Path("/home/lilith/.hermes/lilith-os-dev/data/lilith-dev.db"): "e4080d47ac782dc5578c4537b8aab277e73b27546e704ee2fff6fda506f67e6c",
    API_UNIT: "bacfbac4b0f9502ebfe0a745cd2a9ff691f6a16bad9a8706f03085d588c21243",
}
OPTIONAL_CUSTODY = {
    "cognitive": Path("/home/lilith/.hermes/lilith-os-dev/data/cognitive_memory.dev.db"),
    "privacy": Path("/home/lilith/.hermes/lilith-os-dev/data/privacy_governance.dev.db"),
    "actor_key": Path("/home/lilith/.hermes/lilith-os-dev/data/actor-authority.key"),
    "privacy_key": Path("/home/lilith/.hermes/lilith-os-dev/data/privacy-authority.key"),
    "containment_key": Path("/home/lilith/.hermes/lilith-os-dev/data/legacy_containment.key"),
}
META = "http://169.254.169.254/computeMetadata/v1/"


class Stage2Error(RuntimeError):
    pass


def require(condition: bool, code: str) -> None:
    if not condition:
        raise Stage2Error(code)


def digest(path: Path) -> str:
    require(path.is_file() and not path.is_symlink(), "FILE_MISSING_OR_SYMLINK")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def metadata(key: str) -> str:
    request = Request(META + key, headers={"Metadata-Flavor": "Google"})
    with build_opener(ProxyHandler({})).open(request, timeout=5) as response:
        require(response.headers.get("Metadata-Flavor") == "Google", "METADATA_UNTRUSTED")
        return response.read(256).decode("ascii", "strict").strip()


def assert_host(*, lookup=metadata, hostname=None, machine_id=None) -> None:
    """Both GCE control-plane identity and local identity must pin DEV."""
    require(getattr(os, "geteuid", lambda: -1)() == 0, "ROOT_REQUIRED")
    observed = {key: lookup(key) for key in
                ("project/project-id", "instance/zone", "instance/id", "instance/name")}
    require(observed.get("instance/name") != "lilith-01" and
            observed.get("instance/id") != "1332996232081478576", "PROD_FORBIDDEN")
    require(observed == {
        "project/project-id": PROJECT,
        "instance/zone": f"projects/763184673487/zones/{ZONE}",
        "instance/id": INSTANCE_ID,
        "instance/name": INSTANCE,
    }, "DEV_METADATA_MISMATCH")
    require((hostname or socket.getfqdn()) == HOSTNAME, "DEV_HOSTNAME_MISMATCH")
    require((machine_id or Path("/etc/machine-id").read_text().strip()) == MACHINE_ID,
            "DEV_MACHINE_ID_MISMATCH")


def show(unit: str, *properties: str) -> dict[str, str]:
    result = subprocess.run(
        ["/usr/bin/systemctl", "show", unit, "--no-pager",
         "--property=" + ",".join(properties)],
        check=True, capture_output=True, text=True, timeout=10,
    )
    return dict(line.split("=", 1) for line in result.stdout.splitlines() if "=" in line)


def verify_accounts() -> dict:
    broker = pwd.getpwnam("lilith-memory-broker")
    relay = pwd.getpwnam("lilith-memory-relay")
    ipc = grp.getgrnam("lilith-memory-ipc")
    require((broker.pw_uid, broker.pw_gid, broker.pw_dir, broker.pw_shell) ==
            (999, 987, "/nonexistent", "/usr/sbin/nologin"), "BROKER_IDENTITY_DRIFT")
    require((relay.pw_uid, relay.pw_gid, relay.pw_dir, relay.pw_shell) ==
            (997, 986, "/nonexistent", "/usr/sbin/nologin"), "RELAY_IDENTITY_DRIFT")
    require(ipc.gr_gid == 988 and ipc.gr_mem == ["lilith-memory-relay"] and
            set(os.getgrouplist(broker.pw_name, broker.pw_gid)) == {987} and
            set(os.getgrouplist(relay.pw_name, relay.pw_gid)) == {986, 988},
            "IPC_MEMBERSHIP_DRIFT")
    shadow = Path("/etc/shadow").read_text().splitlines()
    for name in ("lilith-memory-broker", "lilith-memory-relay"):
        values = [line.split(":", 2)[1] for line in shadow if line.startswith(name + ":")]
        require(len(values) == 1 and values[0].startswith(("!", "*")) and
                not (Path("/home") / name).exists(),
                "ACCOUNT_LOCK_OR_HOME_DRIFT")
        result = subprocess.run(["/usr/bin/sudo", "-n", "-l", "-U", name],
                                capture_output=True, text=True, timeout=10)
        require(result.stdout.strip() ==
                f"User {name} is not allowed to run sudo on {INSTANCE}." and
                not result.stderr.strip(), "ACCOUNT_SUDO_DRIFT")
    mapping = json.loads((CONFIG / "identities.json").read_bytes())
    require(mapping == {
        "schemaVersion": 1, "brokerUid": 999, "brokerGid": 987,
        "relayUid": 997, "relayGid": 986, "ipcGid": 988,
        "broker": "lilith-memory-broker", "relay": "lilith-memory-relay",
        "ipcGroup": "lilith-memory-ipc",
    }, "RECORDED_IDENTITY_DRIFT")
    return mapping


def verify_database(path: Path, expected_sha: str, expected_tables: dict[str, int]) -> None:
    info = path.lstat()
    require(stat.S_ISREG(info.st_mode) and info.st_uid == 999 and
            info.st_gid == 987 and stat.S_IMODE(info.st_mode) == 0o600,
            "DATABASE_OWNERSHIP_DRIFT")
    require(digest(path) == expected_sha, "DATABASE_HASH_DRIFT")
    require(not Path(str(path) + "-wal").exists() and
            not Path(str(path) + "-shm").exists(), "DATABASE_WAL_DRIFT")
    db = sqlite3.connect(f"file:{path}?mode=ro&immutable=1", uri=True)
    try:
        db.execute("PRAGMA query_only=ON")
        require(db.execute("PRAGMA integrity_check").fetchone()[0] == "ok" and
                not db.execute("PRAGMA foreign_key_check").fetchall(), "DATABASE_INTEGRITY")
        for table, count in expected_tables.items():
            require(db.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0] == count,
                    "DATABASE_ROW_DRIFT")
        if path == OWNER_DB:
            record = db.execute(
                "SELECT version,fingerprint,mode,authority_epoch FROM broker_schema_v1"
            ).fetchall()
            require(record == [(2, OWNER_SCHEMA, "B1B2_SYNTHETIC_DEV_V1",
                                "f9408d8dbda7c4e22b2487b0f4792e36")],
                    "OWNER_SCHEMA_DRIFT")
            raw = db.execute("SELECT credential_json FROM owner_credential_v1").fetchone()[0]
            credential = json.loads(raw)
            require(credential["recordId"] == "ocred.synthetic" and
                    credential["rpId"] == "owner.lilith.invalid" and
                    credential["ownerPrincipal"] == "user:synthetic-owner@example.invalid" and
                    credential["status"] == "ACTIVE", "NON_SYNTHETIC_CREDENTIAL")
        else:
            require(db.execute("SELECT profile,release_sha FROM synthetic_schema_v1").fetchall()
                    == [("B1B2_SYNTHETIC_EVIDENCE_V1", RELEASE)], "EVIDENCE_SCHEMA_DRIFT")
    finally:
        db.close()


def baseline_digest(value: dict) -> str:
    """Digest the complete closed observation using the marker's JSON convention."""
    return hashlib.sha256(json.dumps(value, sort_keys=True,
                                     separators=(",", ":")).encode()).hexdigest()


def capture_api_runtime_baseline(*, captured_at: str | None = None) -> dict:
    """Pin durable API identity, then observe one process session, read-only."""
    fields = show(API, "LoadState", "ActiveState", "SubState", "MainPID",
                  "NRestarts", "ExecMainStartTimestamp", "User", "Group",
                  "WorkingDirectory", "FragmentPath", "DropInPaths", "ExecStart")
    require(set(fields) == {"LoadState", "ActiveState", "SubState", "MainPID",
                            "NRestarts", "ExecMainStartTimestamp", "User", "Group",
                            "WorkingDirectory", "FragmentPath", "DropInPaths", "ExecStart"},
            "API_SERVICE_DATA_MALFORMED")
    expected = {
        "LoadState": "loaded", "ActiveState": "active", "SubState": "running",
        "NRestarts": "0", "User": "lilith", "Group": "lilith",
        "WorkingDirectory": API_WORKDIR, "FragmentPath": API_UNIT.as_posix(),
        "DropInPaths": "",
    }
    require(all(fields[key] == value for key, value in expected.items()),
            "API_SERVICE_DRIFT")
    require(fields["MainPID"].isdigit() and int(fields["MainPID"]) > 0 and
            fields["ExecMainStartTimestamp"] and
            fields["ExecMainStartTimestamp"] != "n/a" and
            fields["ExecStart"].startswith(
                "{ path=" + API_EXECUTABLE + " ; argv[]=" + API_COMMAND + " ; ") and
            " ; start_time=[" + fields["ExecMainStartTimestamp"] + "] ; " in
            fields["ExecStart"] and
            " ; pid=" + fields["MainPID"] + " ; " in fields["ExecStart"],
            "API_SERVICE_DRIFT")
    app_sha = digest(API_APP)
    require(app_sha == API_APP_SHA, "API_APP_DRIFT")
    custody = {path.as_posix(): digest(path) for path in API_FILES}
    require(all(custody[path.as_posix()] == expected for path, expected in API_FILES.items()),
            "API_CUSTODY_DRIFT")
    health = api_health()
    require(health == {"status": "ok", "database": True}, "API_UNHEALTHY")
    timestamp = captured_at or datetime.now(timezone.utc).isoformat(
        timespec="seconds").replace("+00:00", "Z")
    return {
        "schemaVersion": 1, "serviceName": API,
        "MainPID": int(fields["MainPID"]),
        "ExecMainStartTimestamp": fields["ExecMainStartTimestamp"],
        "NRestarts": int(fields["NRestarts"]),
        "ActiveState": fields["ActiveState"], "SubState": fields["SubState"],
        "serviceUser": fields["User"], "serviceGroup": fields["Group"],
        "workingDirectory": fields["WorkingDirectory"],
        "execStart": fields["ExecStart"],
        "appSha256": app_sha, "serviceUnitSha256": custody[API_UNIT.as_posix()],
        "health": health, "custodySha256": custody, "capturedAt": timestamp,
    }


def require_api_baseline_unchanged(authorized: dict) -> dict:
    """Re-observe without adopting a changed PID, start, health, or custody."""
    observed = capture_api_runtime_baseline(captured_at=authorized["capturedAt"])
    require(observed == authorized, "API_BASELINE_CHANGED")
    return observed


def preflight() -> dict:
    assert_host()
    mapping = verify_accounts()
    require(ROOT.is_dir() and not ROOT.is_symlink() and
            (ROOT / "current").is_symlink() and
            os.readlink(ROOT / "current") == f"releases/{RELEASE}",
            "RELEASE_POINTER_DRIFT")
    for directory, uid, gid, mode in (
        (ROOT, 0, 0, 0o755), (ROOT / "releases", 0, 0, 0o755),
        (CONFIG, 0, 0, 0o755), (STATE, 999, 987, 0o700),
        (STATE / "owner-control", 999, 987, 0o700),
        (STATE / "state", 999, 987, 0o700),
    ):
        info = directory.lstat()
        require(stat.S_ISDIR(info.st_mode) and (info.st_uid, info.st_gid) ==
                (uid, gid) and stat.S_IMODE(info.st_mode) == mode,
                "STAGE_I_DIRECTORY_PERMISSION_DRIFT")
    release_dir = ROOT / "releases" / RELEASE
    require(release_dir.is_dir() and not release_dir.is_symlink() and
            digest(release_dir / "release-manifest.json") == MANIFEST_SHA,
            "RELEASE_MANIFEST_DRIFT")
    release_info = release_dir.lstat()
    manifest_info = (release_dir / "release-manifest.json").lstat()
    pointer_info = (ROOT / "current").lstat()
    require((release_info.st_uid, release_info.st_gid,
             stat.S_IMODE(release_info.st_mode)) == (0, 0, 0o755) and
            (manifest_info.st_uid, manifest_info.st_gid,
             stat.S_IMODE(manifest_info.st_mode)) == (0, 0, 0o644) and
            pointer_info.st_uid == 0, "RELEASE_OWNERSHIP_DRIFT")
    manifest = json.loads((release_dir / "release-manifest.json").read_bytes())
    require(manifest.get("candidateSha") == RELEASE and
            len(manifest.get("files", [])) == 23, "RELEASE_CONTENT_DRIFT")
    for item in manifest["files"]:
        relative = item["path"]
        require(isinstance(relative, str) and ".." not in Path(relative).parts and
                not Path(relative).is_absolute(), "RELEASE_PATH_INVALID")
        path = release_dir / relative
        current = release_dir
        for part in Path(relative).parts[:-1]:
            current = current / part
            require(current.is_dir() and not current.is_symlink(),
                    "RELEASE_PARENT_SYMLINK")
        info = path.lstat()
        require(stat.S_ISREG(info.st_mode) and info.st_uid == 0 and
                info.st_gid == 0 and not info.st_mode & 0o022 and
                info.st_size == item["byteSize"] and digest(path) == item["sha256"],
                "RELEASE_PAYLOAD_DRIFT")
    for path, expected in HASHES.items():
        require(digest(path) == expected, "STAGE_I_FILE_DRIFT")
        info = path.lstat()
        owner = (0, 987, 0o640) if path == CONFIG / "dev.json" else (
            (0, 0, 0o600) if path == CONFIG / "identities.json"
            else (0, 0, 0o644))
        require(stat.S_ISREG(info.st_mode) and
                (info.st_uid, info.st_gid, stat.S_IMODE(info.st_mode)) == owner,
                "STAGE_I_FILE_PERMISSION_DRIFT")
    config = json.loads((CONFIG / "dev.json").read_bytes())
    require(config["authorityMode"] == "SYNTHETIC_ONLY" and
            config["canonicalCapability"] == "DISABLED" and
            config["releaseSha"] == RELEASE and
            set(config["custody"].values()) == {"ABSENT"} and
            config["ownerSchemaFingerprint"] == OWNER_SCHEMA and
            config["evidenceSchemaFingerprint"] == EVIDENCE_SCHEMA,
            "SYNTHETIC_CONFIG_DRIFT")
    verify_database(OWNER_DB, OWNER_DB_SHA, {
        "owner_credential_v1": 1, "owner_proof_challenge_v1": 0,
        "owner_request_v1": 0, "synthetic_claim_v1": 0,
    })
    verify_database(EVIDENCE_DB, EVIDENCE_DB_SHA, {"synthetic_evidence_v1": 0})
    service = show(SERVICE, "ActiveState", "SubState", "MainPID", "UnitFileState")
    sock = show(SOCKET, "ActiveState", "SubState", "UnitFileState")
    require(service["ActiveState"] == "inactive" and service["SubState"] == "dead" and
            service["MainPID"] == "0" and sock["ActiveState"] == "inactive" and
            sock["SubState"] == "dead" and sock["UnitFileState"] == "disabled",
            "BROKER_NOT_INERT")
    require(not RUN.exists() and not RUN.is_symlink() and
            not Path("/run/lilith-memory/owner.sock").exists(), "RUNTIME_COLLISION")
    for suffix in (".tar.gz", ".attestation.json"):
        path = Path(f"/tmp/lilith-broker-os-{RELEASE}{suffix}")
        require(not path.exists() and not path.is_symlink(),
                "STAGE_I_STAGING_RESIDUE")
    require(subprocess.run(["/usr/bin/pgrep", "-u", "999"],
                           capture_output=True, timeout=5).returncode == 1,
            "UNEXPECTED_BROKER_PROCESS")
    api_baseline = capture_api_runtime_baseline()
    return {"status": "STAGE_II_PREFLIGHT_OK", "release": RELEASE,
            "identities": mapping, "payloadsVerified": 23,
            "apiRuntimeBaseline": api_baseline,
            "apiBaselineDigest": baseline_digest(api_baseline)}


def marker_value(issued: datetime, authorization_id: str, api_baseline: dict) -> dict:
    return {
        "schemaVersion": 2, "purpose": PURPOSE, "stage": STAGE,
        "project": PROJECT, "zone": ZONE, "instanceId": INSTANCE_ID,
        "hostname": HOSTNAME, "machineId": MACHINE_ID,
        "releaseSha": RELEASE, "manifestSha256": MANIFEST_SHA,
        "identityMapSha256": HASHES[CONFIG / "identities.json"],
        "serviceSha256": HASHES[Path("/etc/systemd/system/lilith-memory-broker.service")],
        "socketSha256": HASHES[Path("/etc/systemd/system/lilith-memory-broker.socket")],
        "tmpfilesSha256": HASHES[Path("/etc/tmpfiles.d/lilith-memory-broker.conf")],
        "configSha256": HASHES[CONFIG / "dev.json"],
        "ownerSchemaFingerprint": OWNER_SCHEMA,
        "evidenceSchemaFingerprint": EVIDENCE_SCHEMA,
        "ownerActor": OWNER, "authorityMode": "SYNTHETIC_ONLY",
        "canonicalCapability": "DISABLED", "authorizationId": authorization_id,
        "apiRuntimeBaseline": api_baseline,
        "apiBaselineDigest": baseline_digest(api_baseline),
        "issuedAt": issued.isoformat(timespec="seconds").replace("+00:00", "Z"),
        "expiresAt": (issued + timedelta(minutes=30)).isoformat(timespec="seconds").replace("+00:00", "Z"),
    }


def authorize() -> dict:
    baseline = preflight()["apiRuntimeBaseline"]
    require(not MARKER.exists() and not MARKER.is_symlink() and
            not USED.exists() and not USED.is_symlink(), "STAGE_II_AUTHORIZATION_COLLISION")
    issued = datetime.now(timezone.utc)
    value = marker_value(issued, uuid.uuid4().hex, baseline)
    payload = json.dumps(value, sort_keys=True, separators=(",", ":")).encode() + b"\n"
    fd = os.open(MARKER, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "wb") as stream:
        stream.write(payload)
        stream.flush()
        os.fsync(stream.fileno())
    os.chown(MARKER, 0, 0)
    os.chmod(MARKER, 0o600)
    return {"status": "STAGE_II_AUTHORIZED_ONLY", "authorizationId": value["authorizationId"],
            "expiresAt": value["expiresAt"], "apiBaselineDigest": value["apiBaselineDigest"]}


def verify_marker(*, now: datetime | None = None) -> dict:
    info = MARKER.lstat()
    require(stat.S_ISREG(info.st_mode) and info.st_uid == 0 and
            info.st_gid == 0 and stat.S_IMODE(info.st_mode) == 0o600 and
            not USED.exists() and not USED.is_symlink(), "STAGE_II_MARKER_INVALID")
    value = json.loads(MARKER.read_bytes())
    try:
        issued = datetime.fromisoformat(value["issuedAt"].replace("Z", "+00:00"))
        expires = datetime.fromisoformat(value["expiresAt"].replace("Z", "+00:00"))
        authorization_id = value["authorizationId"]
        api_baseline = value["apiRuntimeBaseline"]
        captured = datetime.fromisoformat(api_baseline["capturedAt"].replace("Z", "+00:00"))
    except (KeyError, TypeError, ValueError, AttributeError) as exc:
        raise Stage2Error("STAGE_II_MARKER_MALFORMED") from exc
    require(issued.tzinfo is not None and issued.utcoffset() == timedelta(0) and
            expires == issued + timedelta(minutes=30) and
            captured.tzinfo is not None and captured.utcoffset() == timedelta(0) and
            timedelta(0) <= issued - captured <= timedelta(minutes=5) and
            isinstance(authorization_id, str) and
            re.fullmatch(r"[0-9a-f]{32}", authorization_id) is not None,
            "STAGE_II_MARKER_WINDOW")
    moment = now or datetime.now(timezone.utc)
    require(isinstance(api_baseline, dict) and
            set(api_baseline) == {"schemaVersion", "serviceName", "MainPID",
                                  "ExecMainStartTimestamp", "NRestarts", "ActiveState",
                                  "SubState", "serviceUser", "serviceGroup",
                                  "workingDirectory", "execStart", "appSha256",
                                  "serviceUnitSha256", "health", "custodySha256",
                                  "capturedAt"} and
            api_baseline["schemaVersion"] == 1 and
            value.get("apiBaselineDigest") == baseline_digest(api_baseline),
            "STAGE_II_MARKER_BASELINE_INVALID")
    require(issued <= moment < expires and
            value == marker_value(issued, authorization_id, api_baseline),
            "STAGE_II_MARKER_MISMATCH")
    return value


# This source runs only under a dedicated transient systemd service whose
# relevant hardening properties are compared with the actual broker unit.
# It never imports broker code and never writes to a prohibited path.
ISOLATION_PROBE = r'''
import errno, json, os, socket, stat, tempfile
from pathlib import Path

def attempt(name, operation):
    try:
        operation()
        return [name, "ALLOWED", 0]
    except OSError as exc:
        return [name, "DENIED", exc.errno]

def read_directory(path):
    os.listdir(path)

def read_file(path):
    fd=os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    os.close(fd)

def write_open(path):
    fd=os.open(path, os.O_WRONLY | os.O_NOFOLLOW)
    os.close(fd)

def family(value):
    sock=socket.socket(value, socket.SOCK_STREAM)
    sock.close()

paths={
    "home": "/home/lilith",
    "legacy_dev_db": "/home/lilith/.hermes/lilith-os-dev/data/lilith-dev.db",
    "release": "/opt/lilith-memory-broker/current/release-manifest.json",
    "venv": "/opt/lilith-memory-broker/current/venv/pyvenv.cfg",
    "config": "/etc/lilith-memory-broker/dev.json",
    "identities": "/etc/lilith-memory-broker/identities.json",
    "outside_state": "/etc/hostname",
    "cognitive": "/home/lilith/.hermes/lilith-os-dev/data/cognitive_memory.dev.db",
    "privacy": "/home/lilith/.hermes/lilith-os-dev/data/privacy_governance.dev.db",
    "actor_key": "/home/lilith/.hermes/lilith-os-dev/data/actor-authority.key",
    "privacy_key": "/home/lilith/.hermes/lilith-os-dev/data/privacy-authority.key",
    "containment_key": "/home/lilith/.hermes/lilith-os-dev/data/legacy_containment.key",
}
results=[attempt("home", lambda: read_directory(paths["home"])),
         attempt("legacy_dev_db", lambda: read_file(paths["legacy_dev_db"]))]
for name in ("release", "venv", "config", "identities", "outside_state"):
    results.append(attempt(name, lambda path=paths[name]: write_open(path)))
for name in ("cognitive", "privacy", "actor_key", "privacy_key", "containment_key"):
    results.append(attempt(name, lambda path=paths[name]: read_file(path)))
for name, value in (("af_unix", socket.AF_UNIX), ("af_inet", socket.AF_INET),
                    ("af_inet6", socket.AF_INET6)):
    results.append(attempt(name, lambda value=value: family(value)))
host_marker=Path("/tmp/lilith-memory-broker-stage2-host-marker")
results.append(["private_tmp_host_marker", "VISIBLE" if host_marker.exists() else "HIDDEN", 0])
with tempfile.NamedTemporaryFile(prefix="lilith-stage2-", dir="/tmp") as tmp:
    results.append(["private_tmp_writable", "ALLOWED" if tmp.file else "DENIED", 0])
status={}
for line in Path("/proc/self/status").read_text().splitlines():
    if line.startswith(("Uid:", "Gid:", "Groups:", "CapEff:", "NoNewPrivs:")):
        key,value=line.split(":",1)
        status[key]=value.strip()
print(json.dumps({"results":results,"status":status},sort_keys=True))
'''


def run_fixed(*args: str, timeout: int = 30, input_text: str | None = None) -> subprocess.CompletedProcess:
    try:
        return subprocess.run(args, check=True, capture_output=True, text=True,
                              timeout=timeout, input=input_text,
                              env={"PATH": "/usr/sbin:/usr/bin:/sbin:/bin", "LANG": "C",
                                   "HOME": "/nonexistent", "PYTHONDONTWRITEBYTECODE": "1"})
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        label = Path(args[0]).name.upper().replace("-", "_")
        step = args[1].upper().replace("-", "_") if len(args) > 1 else "RUN"
        raise Stage2Error(f"FIXED_COMMAND_FAILED_{label}_{step}") from exc


HARDENING = (
    "NoNewPrivileges", "PrivateTmp", "PrivateDevices", "ProtectSystem",
    "ProtectHome", "ProtectKernelTunables", "ProtectKernelModules",
    "ProtectControlGroups", "RestrictNamespaces", "LockPersonality",
    "CapabilityBoundingSet", "AmbientCapabilities", "RestrictAddressFamilies",
    "IPAddressDeny", "UMask", "ReadOnlyPaths", "ReadWritePaths",
    "StateDirectory", "StateDirectoryMode", "User", "Group",
)
EXPECTED_HARDENING = {
    "NoNewPrivileges": "yes", "PrivateTmp": "yes", "PrivateDevices": "yes",
    "ProtectSystem": "strict", "ProtectHome": "yes",
    "ProtectKernelTunables": "yes", "ProtectKernelModules": "yes",
    "ProtectControlGroups": "yes", "RestrictNamespaces": "yes",
    "LockPersonality": "yes", "CapabilityBoundingSet": "",
    "AmbientCapabilities": "", "RestrictAddressFamilies": "AF_UNIX",
    # systemd 255 normalizes IPAddressDeny=any to these two CIDRs.
    "IPAddressDeny": "0.0.0.0/0 ::/0", "UMask": "0077",
    "ReadOnlyPaths": "/opt/lilith-memory-broker /etc/lilith-memory-broker",
    "ReadWritePaths": "/var/lib/lilith-memory-broker",
    "StateDirectory": "lilith-memory-broker", "StateDirectoryMode": "0700",
    "User": "lilith-memory-broker", "Group": "lilith-memory-broker",
}


def effective_hardening(unit: str) -> dict[str, str]:
    values = show(unit, *HARDENING)
    require(set(values) == set(HARDENING), "EFFECTIVE_HARDENING_INCOMPLETE")
    return values


def assert_broker_hardening() -> dict[str, str]:
    actual = effective_hardening(SERVICE)
    # Exact installed unit hash above pins source. Effective values must also
    # match; any systemd version/normalization difference requires review.
    require(actual == EXPECTED_HARDENING, "EFFECTIVE_BROKER_HARDENING_DRIFT")
    return actual


def inspect_run_directory() -> dict:
    info = RUN.lstat()
    require(stat.S_ISDIR(info.st_mode) and info.st_uid == 0 and
            info.st_gid == 988 and stat.S_IMODE(info.st_mode) == 0o710,
            "RUN_DIRECTORY_CONTRACT")
    require({p.name for p in RUN.iterdir()} == set(), "RUN_PRE_SOCKET_COLLISION")
    return {"inode": info.st_ino, "uid": info.st_uid, "gid": info.st_gid,
            "mode": "0710"}


def inspect_socket() -> dict:
    path = RUN / "owner.sock"
    info = path.lstat()
    require(stat.S_ISSOCK(info.st_mode) and info.st_uid == 999 and
            info.st_gid == 988 and stat.S_IMODE(info.st_mode) == 0o660,
            "OWNER_SOCKET_CONTRACT")
    require({p.name for p in RUN.iterdir()} == {"owner.sock"},
            "RUN_SOCKET_SIBLING_COLLISION")
    return {"inode": info.st_ino, "uid": info.st_uid, "gid": info.st_gid,
            "mode": "0660", "type": "socket"}


def assert_unit_state(*, socket_active: bool, service_active: bool) -> tuple[dict, dict]:
    s = show(SERVICE, "ActiveState", "SubState", "MainPID", "UnitFileState")
    k = show(SOCKET, "ActiveState", "SubState", "UnitFileState")
    require(s["ActiveState"] == ("active" if service_active else "inactive") and
            k["ActiveState"] == ("active" if socket_active else "inactive") and
            k["UnitFileState"] == "disabled", "UNIT_STATE_DRIFT")
    require((int(s["MainPID"]) > 0) == service_active, "BROKER_PID_STATE_DRIFT")
    require(s["UnitFileState"] != "enabled", "BOOT_ENABLE_FORBIDDEN")
    return s, k


def inspect_process(pid: int) -> dict:
    root = Path("/proc") / str(pid)
    require(root.is_dir(), "BROKER_PROCESS_MISSING")
    lines = (root / "status").read_text().splitlines()
    status = dict(line.split(":", 1) for line in lines if ":" in line)
    uid = status["Uid"].split()
    gid = status["Gid"].split()
    require(uid == ["999"] * 4 and gid == ["987"] * 4 and
            status["Groups"].strip() == "987" and
            status["CapEff"].strip() == "0000000000000000" and
            status["NoNewPrivs"].strip() == "1", "BROKER_PROCESS_IDENTITY")
    exe = os.readlink(root / "exe")
    cwd = os.readlink(root / "cwd")
    require(cwd == str(ROOT / "releases" / RELEASE) or cwd == str(ROOT / "current"),
            "BROKER_PROCESS_CWD")
    require(exe.startswith(str(ROOT / "releases" / RELEASE / "venv")) or
            exe.startswith("/usr/bin/python3"), "BROKER_PROCESS_EXECUTABLE")
    env = (root / "environ").read_bytes().split(b"\0")
    names = sorted(item.split(b"=", 1)[0].decode("ascii") for item in env if b"=" in item)
    namespaces = {name: os.readlink(root / "ns" / name)
                  for name in ("mnt", "net", "user", "pid")}
    return {"pid": pid, "ppid": int(status["PPid"].strip()), "uid": uid,
            "gid": gid, "groups": status["Groups"].strip(), "exe": exe,
            "cwd": cwd, "environmentNames": names,
            "CapEff": status["CapEff"].strip(),
            "NoNewPrivs": status["NoNewPrivs"].strip(), "namespaces": namespaces}


def probe_equivalent_sandbox(expected: dict[str, str]) -> dict:
    unit = "lilith-memory-broker-stage2-probe.service"
    require(show(unit, "LoadState")["LoadState"] == "not-found",
            "PROBE_UNIT_COLLISION")
    host_marker = Path("/tmp/lilith-memory-broker-stage2-host-marker")
    require(not host_marker.exists() and not host_marker.is_symlink(),
            "PROBE_MARKER_COLLISION")
    fd = os.open(host_marker, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o644)
    os.close(fd)
    runner = None
    try:
        args = ["/usr/bin/systemd-run", "--quiet", "--pipe",
                "--service-type=oneshot", "--remain-after-exit",
                "--unit=" + unit]
        for key, value in expected.items():
            configured = "any" if key == "IPAddressDeny" else value
            args.append("--property=" + key + "=" + configured)
        args.extend(["/usr/bin/python3", "-B", "-c", ISOLATION_PROBE])
        runner = subprocess.Popen(
            args, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, text=True,
            env={"PATH": "/usr/sbin:/usr/bin:/sbin:/bin", "LANG": "C",
                 "HOME": "/nonexistent", "PYTHONDONTWRITEBYTECODE": "1"},
        )
        import time
        for _ in range(100):
            state = show(unit, "LoadState", "ActiveState", "SubState")
            if state.get("ActiveState") == "active" and state.get("SubState") == "exited":
                break
            require(runner.poll() in (None, 0), "PROBE_UNIT_FAILED_TO_START")
            time.sleep(0.1)
        else:
            raise Stage2Error("PROBE_UNIT_TIMEOUT")
        loaded = effective_hardening(unit)
        require(loaded == expected, "PROBE_BROKER_SANDBOX_NOT_EQUIVALENT")
        # RemainAfterExit keeps the effective unit observable. Stop it to
        # complete --pipe, then parse only fixed, bounded probe output.
        run_fixed("/usr/bin/systemctl", "stop", unit)
        stdout, stderr = runner.communicate(timeout=10)
        require(runner.returncode == 0 and len(stdout) < 8192 and
                not stderr.strip(), "PROBE_OUTPUT_INVALID")
        data = json.loads(stdout)
        results = {name: (result, error) for name, result, error in data["results"]}
        expected_denied = {
            "home", "legacy_dev_db", "release", "venv", "config",
            "identities", "outside_state", "af_inet", "af_inet6",
        }
        require(all(results[name][0] == "DENIED" for name in expected_denied) and
                results["af_unix"][0] == "ALLOWED" and
                results["private_tmp_host_marker"][0] == "HIDDEN" and
                results["private_tmp_writable"][0] == "ALLOWED",
                "ISOLATION_PROBE_FAILED")
        custody_presence = {name: path.exists() or path.is_symlink()
                            for name, path in OPTIONAL_CUSTODY.items()}
        require(all(results[name][0] == "DENIED" for name, present in
                    custody_presence.items() if present),
                "CUSTODY_PROBE_FAILED")
        require(data["status"]["Uid"].split() == ["999"] * 4 and
                data["status"]["Gid"].split() == ["987"] * 4 and
                data["status"]["Groups"] == "987" and
                data["status"]["CapEff"] == "0000000000000000" and
                data["status"]["NoNewPrivs"] == "1", "PROBE_PROCESS_IDENTITY")
        return {"results": results, "process": data["status"],
                "custodyPathPresence": custody_presence,
                "effectiveUnitEquivalent": True}
    finally:
        subprocess.run(["/usr/bin/systemctl", "stop", unit],
                       capture_output=True, timeout=15)
        if runner is not None and runner.poll() is None:
            runner.terminate()
            runner.communicate(timeout=10)
        host_marker.unlink(missing_ok=True)


# Streamed to a relay-UID child over stdin. The accepted TEST_ONLY scalar
# never goes into a release, VM file, marker, database, journal, or output.
# Child stderr is never forwarded because tracebacks can include source lines.
RELAY_SOURCE = r'''
import base64, hashlib, json, socket, struct, sys
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec
from lilith_memory import owner_proof as P
from lilith_memory_broker import protocol
from lilith_memory_broker.request import SYNTHETIC_FIXTURE_ID

SOCKET="/run/lilith-memory/owner.sock"
TEST_ONLY_PRIVATE_SCALAR=0x8A98159F36D8F33E8F26E728AFCB09F3
def b64(raw):
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")
def exchange(operation, payload):
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as conn:
        conn.settimeout(5)
        conn.connect(SOCKET)
        conn.sendall(protocol.encode_frame(operation,payload))
        header=conn.recv(4)
        if not header:
            return None
        if len(header)!=4:
            raise RuntimeError("TRUNCATED_RESPONSE")
        size=struct.unpack(">I",header)[0]
        if not 0<size<=protocol.MAX_FRAME_BYTES:
            raise RuntimeError("RESPONSE_SIZE")
        raw=b""
        while len(raw)<size:
            chunk=conn.recv(size-len(raw))
            if not chunk:
                raise RuntimeError("TRUNCATED_RESPONSE")
            raw+=chunk
        return json.loads(raw)
def assertion(challenge,variant="valid"):
    ch=P.OwnerMemoryChallengeV1.from_dict(challenge)
    credential=json.load(open("/opt/lilith-memory-broker/current/assets/public-synthetic-credential.json"))
    client=json.dumps({"type":"webauthn.get","challenge":b64(ch.webauthn_challenge()),
                       "origin":"https://wrong.invalid" if variant=="origin" else P.SYNTHETIC_ORIGIN,
                       "crossOrigin":False},
                      separators=(",",":")).encode()
    if variant=="challenge":
        client=json.dumps({"type":"webauthn.get","challenge":b64(b"x"*32),
                           "origin":P.SYNTHETIC_ORIGIN,"crossOrigin":False},
                          separators=(",",":")).encode()
    rp="wrong.invalid" if variant=="rp" else P.SYNTHETIC_RP_ID
    flag=0x04 if variant=="up" else 0x01 if variant=="uv" else 0x05
    auth=hashlib.sha256(rp.encode()).digest()+bytes([flag])+(0).to_bytes(4,"big")
    key=ec.derive_private_key(TEST_ONLY_PRIVATE_SCALAR,ec.SECP256R1())
    signature=key.sign(auth+hashlib.sha256(client).digest(),ec.ECDSA(hashes.SHA256()))
    if variant=="signature":
        signature=b"invalid-signature"
    return {"credentialRecordId":credential["recordId"],
            "credentialId":b64(b"TEST_ONLY_OTHER_CREDENTIAL_01") if variant=="credential" else credential["credentialId"],
            "clientDataJSON":b64(client),
            "authenticatorData":b64(auth),"signature":b64(signature)}
scenario=sys.argv[1]
if scenario=="health":
    value=exchange("HEALTH",{})
    assert value["payload"]["status"]=="OK"
    assert value["payload"]["result"]["status"]=="SYNTHETIC_DEV_ONLY"
    print(json.dumps({"status":"HEALTH_OK"}))
elif scenario=="prepare":
    value=exchange("PREPARE_SYNTHETIC",{"fixtureId":SYNTHETIC_FIXTURE_ID})
    assert value["payload"]["status"]=="OK"
    challenge=value["payload"]["result"]["challenge"]
    P.OwnerMemoryChallengeV1.from_dict(challenge)
    print(json.dumps({"status":"PREPARED","challenge":challenge}))
elif scenario=="confirm":
    challenge=json.loads(sys.argv[2])
    variant=sys.argv[3]
    value=exchange("CONFIRM_SYNTHETIC",{"challengeId":challenge["challengeId"],
                                        "assertion":assertion(challenge,variant)})
    if value is None:
        print(json.dumps({"status":"REJECTED"}))
    else:
        assert value["payload"]["status"]=="OK"
        assert value["payload"]["result"]["status"]=="SYNTHETIC_EVIDENCE_COMMITTED"
        print(json.dumps({"status":"CONFIRMED","challengeId":challenge["challengeId"]}))
elif scenario=="cancel":
    value=exchange("CANCEL",{"challengeId":sys.argv[2]})
    assert value["payload"]["status"]=="OK"
    print(json.dumps({"status":"CANCELLED"}))
elif scenario=="forged_identity":
    import rfc8785
    raw=rfc8785.dumps({"protocol":protocol.PROTOCOL,"schemaVersion":1,
                        "operation":"HEALTH","payload":{},"relayUid":997})
    with socket.socket(socket.AF_UNIX,socket.SOCK_STREAM) as conn:
        conn.settimeout(5)
        conn.connect(SOCKET)
        conn.sendall(struct.pack(">I",len(raw))+raw)
        assert conn.recv(4)==b""
    print(json.dumps({"status":"FORGED_FIELD_REJECTED"}))
else:
    raise RuntimeError("UNSUPPORTED_SCENARIO")
'''


def relay(scenario: str, public_challenge: dict | None = None,
          variant: str = "valid") -> dict:
    require(scenario in {"health", "prepare", "confirm", "cancel", "forged_identity"},
            "RELAY_SCENARIO_INVALID")
    args = ["/usr/sbin/runuser", "-u", "lilith-memory-relay", "--",
            "/usr/bin/env", "LILITH_ENV=dev", "PYTHONDONTWRITEBYTECODE=1",
            "PYTHONNOUSERSITE=1",
            str(ROOT / "current/venv/bin/python"), "-B", "-", scenario]
    if public_challenge is not None:
        require(scenario in {"confirm", "cancel"}, "RELAY_CHALLENGE_UNEXPECTED")
        args.append(json.dumps(public_challenge, separators=(",", ":"))
                    if scenario == "confirm" else public_challenge["challengeId"])
    if scenario == "confirm":
        require(variant in {"valid", "origin", "rp", "challenge", "signature",
                            "credential", "up", "uv"}, "ASSERTION_VARIANT_INVALID")
        args.append(variant)
    result = subprocess.run(args, cwd=ROOT / "current", input=RELAY_SOURCE,
                            text=True, capture_output=True, timeout=15,
                            env={"PATH": "/usr/sbin:/usr/bin:/sbin:/bin",
                                 "LANG": "C", "HOME": "/nonexistent"})
    require(result.returncode == 0 and len(result.stdout) < 8192,
            "RELAY_" + scenario.upper() + "_FAILED")
    return json.loads(result.stdout)


NEGATIVE_CLIENT = r'''
import json,socket,struct,sys
path="/run/lilith-memory/owner.sock"
try:
    with socket.socket(socket.AF_UNIX,socket.SOCK_STREAM) as conn:
        conn.settimeout(3)
        conn.connect(path)
        raw=b'{"operation":"HEALTH","payload":{},"protocol":"LILITH_MEMORY_BROKER","schemaVersion":1}'
        conn.sendall(struct.pack(">I",len(raw))+raw)
        result=conn.recv(4)
        print(json.dumps({"layer":"peer_rejection" if not result else "UNEXPECTED_RESPONSE"}))
except OSError as exc:
    print(json.dumps({"layer":"filesystem_or_socket","errno":exc.errno}))
'''


def negative_peer(user: str) -> dict:
    require(user in {"lilith", "nobody", "lilith-memory-broker"},
            "NEGATIVE_IDENTITY_INVALID")
    result = subprocess.run(
        ["/usr/sbin/runuser", "-u", user, "--", "/usr/bin/python3", "-B", "-"],
        input=NEGATIVE_CLIENT, text=True, capture_output=True, timeout=10,
        env={"PATH": "/usr/bin:/bin", "LANG": "C", "HOME": "/nonexistent"},
    )
    require(result.returncode == 0 and len(result.stdout) < 1024,
            "NEGATIVE_CLIENT_FAILED")
    value = json.loads(result.stdout)
    require(value["layer"] in {"filesystem_or_socket", "peer_rejection"},
            "NEGATIVE_PEER_ACCEPTED")
    return value


def trace_peer_uid(pid: int) -> dict:
    """Observe the actual SO_PEERCRED getsockopt, not a JSON identity claim."""
    trace = subprocess.Popen(
        ["/usr/bin/strace", "-f", "-e", "trace=getsockopt", "-s", "64",
         "-p", str(pid)],
        stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True,
        env={"PATH": "/usr/bin:/bin", "LANG": "C"},
    )
    try:
        # strace attaches asynchronously; require the attachment notice.
        import time
        time.sleep(1)
        require(trace.poll() is None, "PEER_TRACE_ATTACH_FAILED")
        require(relay("health")["status"] == "HEALTH_OK", "TRACED_HEALTH_FAILED")
    finally:
        trace.terminate()
    try:
        _out, output = trace.communicate(timeout=10)
    except subprocess.TimeoutExpired as exc:
        trace.kill()
        trace.communicate(timeout=10)
        raise Stage2Error("PEER_TRACE_DID_NOT_DETACH") from exc
    require(len(output) < 8192 and
            re.search(r"SO_PEERCRED,\s*\{pid=\d+, uid=997, gid=986\}", output)
            is not None, "KERNEL_PEER_UID_NOT_OBSERVED")
    return {"kernelPeerUid": 997, "kernelPeerGid": 986,
            "method": "strace_getsockopt_SO_PEERCRED_actual_broker"}


def inspect_prepared(challenge: dict) -> None:
    challenge_id = challenge["challengeId"]
    db = sqlite3.connect(f"file:{OWNER_DB}?mode=ro", uri=True)
    try:
        db.execute("PRAGMA query_only=ON")
        require(db.execute(
            "SELECT state FROM owner_proof_challenge_v1 WHERE challenge_id=?",
            (challenge_id,)).fetchone() == ("PREPARED",), "CHALLENGE_NOT_DURABLE")
        require(db.execute(
            "SELECT COUNT(*) FROM owner_request_v1 WHERE challenge_id=?",
            (challenge_id,)).fetchone()[0] == 1, "REQUEST_NOT_DURABLE")
    finally:
        db.close()


def verify_runtime_database(path: Path) -> tuple[sqlite3.Connection, dict]:
    info = path.lstat()
    require(stat.S_ISREG(info.st_mode) and (info.st_uid, info.st_gid) == (999, 987)
            and stat.S_IMODE(info.st_mode) == 0o600, "RUNTIME_DATABASE_OWNERSHIP")
    sidecars = {}
    for suffix in ("-wal", "-shm"):
        side = Path(str(path) + suffix)
        if side.exists() or side.is_symlink():
            details = side.lstat()
            require(stat.S_ISREG(details.st_mode) and
                    (details.st_uid, details.st_gid) == (999, 987) and
                    stat.S_IMODE(details.st_mode) == 0o600, "RUNTIME_SIDECAR_OWNERSHIP")
            sidecars[suffix] = {"inode": details.st_ino, "mode": "0600"}
    db = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    db.execute("PRAGMA query_only=ON")
    require(db.execute("PRAGMA integrity_check").fetchone()[0] == "ok" and
            not db.execute("PRAGMA foreign_key_check").fetchall(),
            "RUNTIME_DATABASE_INTEGRITY")
    return db, {"inode": info.st_ino, "mode": "0600", "sidecars": sidecars}


def functional_tests() -> dict:
    require(relay("forged_identity")["status"] == "FORGED_FIELD_REJECTED",
            "FORGED_IDENTITY_ACCEPTED")
    first = relay("prepare")
    require(first["status"] == "PREPARED", "PREPARE_FAILED")
    challenge = first["challenge"]
    inspect_prepared(challenge)
    require(relay("confirm", challenge)["status"] == "CONFIRMED",
            "SYNTHETIC_CONFIRM_FAILED")
    require(relay("confirm", challenge)["status"] == "REJECTED",
            "REPLAY_ACCEPTED")
    cancelled = relay("prepare")["challenge"]
    inspect_prepared(cancelled)
    require(relay("cancel", cancelled)["status"] == "CANCELLED",
            "CANCEL_FAILED")
    require(relay("confirm", cancelled)["status"] == "REJECTED",
            "CANCELLED_PROOF_ACCEPTED")
    expired = relay("prepare")["challenge"]
    inspect_prepared(expired)
    from datetime import datetime
    import time
    deadline = datetime.fromisoformat(expired["expiresAt"].replace("Z", "+00:00"))
    time.sleep(max(0, (deadline - datetime.now(timezone.utc)).total_seconds()) + 1.5)
    require(relay("confirm", expired)["status"] == "REJECTED",
            "EXPIRED_PROOF_ACCEPTED")
    variants = ("origin", "rp", "challenge", "signature", "credential", "up", "uv")
    for variant in variants:
        item = relay("prepare")["challenge"]
        inspect_prepared(item)
        require(relay("confirm", item, variant)["status"] == "REJECTED",
                "INVALID_ASSERTION_ACCEPTED_" + variant.upper())
        require(relay("cancel", item)["status"] == "CANCELLED",
                "INVALID_ASSERTION_CANCEL_FAILED")
    for field in ("actionDigest", "requestDigest"):
        item = relay("prepare")["challenge"]
        inspect_prepared(item)
        altered = dict(item, **{field: "0" * 64})
        require(relay("confirm", altered)["status"] == "REJECTED",
                "BINDING_MISMATCH_ACCEPTED_" + field)
        require(relay("cancel", item)["status"] == "CANCELLED",
                "BINDING_TEST_CANCEL_FAILED")
    owner, owner_meta = verify_runtime_database(OWNER_DB)
    evidence, evidence_meta = verify_runtime_database(EVIDENCE_DB)
    try:
        states = dict(owner.execute(
            "SELECT state,COUNT(*) FROM owner_proof_challenge_v1 GROUP BY state"
        ).fetchall())
        require(states.get("CONSUMED") == 1 and states.get("CANCELLED") == 10 and
                states.get("EXPIRED") == 1, "CHALLENGE_STATE_DRIFT")
        require(owner.execute("SELECT COUNT(*) FROM owner_request_v1").fetchone()[0]
                == 12, "REQUEST_COUNT_DRIFT")
        claims = owner.execute(
            "SELECT challenge_id,status,synthetic_evidence_id FROM synthetic_claim_v1"
        ).fetchall()
        require(len(claims) == 1 and claims[0][0] == challenge["challengeId"] and
                claims[0][1] == "SYNTHETIC_EVIDENCE_COMMITTED" and
                claims[0][2].startswith("se."), "SYNTHETIC_CLAIM_DRIFT")
        items = evidence.execute(
            "SELECT challenge_id,synthetic_evidence_id,state FROM synthetic_evidence_v1"
        ).fetchall()
        require(items == [(challenge["challengeId"], claims[0][2],
                           "SYNTHETIC_COMMITTED")], "SYNTHETIC_EVIDENCE_DRIFT")
        require(owner.execute("SELECT fingerprint FROM broker_schema_v1").fetchone()[0]
                == OWNER_SCHEMA and evidence.execute(
                    "SELECT profile FROM synthetic_schema_v1").fetchone()[0]
                == "B1B2_SYNTHETIC_EVIDENCE_V1", "RUNTIME_SCHEMA_DRIFT")
    finally:
        owner.close()
        evidence.close()
    return {"challengeStates": states, "requests": 12, "claims": 1,
            "syntheticEvidenceId": items[0][1], "ownerDb": owner_meta,
            "evidenceDb": evidence_meta,
            "invalidProofVariants": list(variants) +
            ["actionDigest", "requestDigest"]}


def assert_relay_restrictions() -> dict:
    checks = (
        ("-r", OWNER_DB), ("-w", OWNER_DB), ("-r", EVIDENCE_DB),
        ("-w", EVIDENCE_DB), ("-w", ROOT / "current"),
        ("-w", CONFIG / "dev.json"),
        ("-r", Path("/home/lilith/.hermes/lilith-os-dev/data/canonical-runtime.json")),
    )
    for option, path in checks:
        result = subprocess.run(
            ["/usr/sbin/runuser", "-u", "lilith-memory-relay", "--",
             "/usr/bin/test", option, str(path)],
            capture_output=True, timeout=10,
        )
        require(result.returncode != 0, "RELAY_PERMISSION_BREACH")
    sudo = run_fixed("/usr/bin/sudo", "-n", "-l", "-U", "lilith-memory-relay")
    require(sudo.stdout.strip() ==
            "User lilith-memory-relay is not allowed to run sudo on lilith-dev-01.",
            "RELAY_SUDO_BREACH")
    require(pwd.getpwnam("lilith-memory-relay").pw_shell == "/usr/sbin/nologin",
            "RELAY_LOGIN_BREACH")
    return {"state": "denied", "releaseConfig": "denied",
            "otherCustody": "denied", "sudo": "denied", "login": "nologin"}


def api_health() -> dict:
    request = Request("http://127.0.0.1:8765/health")
    with build_opener(ProxyHandler({})).open(request, timeout=5) as response:
        require(response.status == 200, "API_UNHEALTHY")
        data = json.loads(response.read(1024))
    require(data.get("status") == "ok" and data.get("database") is True,
            "API_UNHEALTHY")
    return {"status": "ok", "database": True}


def execute() -> dict:
    # No operational mutation before all host, marker, and Stage-I gates pass.
    marker = verify_marker()
    baseline = preflight()
    require(marker["apiBaselineDigest"] == baseline_digest(
        {**baseline["apiRuntimeBaseline"],
         "capturedAt": marker["apiRuntimeBaseline"]["capturedAt"]}),
        "API_BASELINE_CHANGED")
    require_api_baseline_unchanged(marker["apiRuntimeBaseline"])
    os.replace(MARKER, USED)  # One-time claim before daemon-reload.
    try:
        run_fixed("/usr/bin/systemctl", "daemon-reload")
        effective = assert_broker_hardening()
        run_fixed("/usr/bin/systemd-tmpfiles", "--create",
                  "--prefix=/run/lilith-memory")
        runtime_dir = inspect_run_directory()
        run_fixed("/usr/bin/systemctl", "start", SOCKET)
        sock = inspect_socket()
        assert_unit_state(socket_active=True, service_active=False)
        require(relay("health")["status"] == "HEALTH_OK", "RELAY_HEALTH_FAILED")
        service, _ = assert_unit_state(socket_active=True, service_active=True)
        process = inspect_process(int(service["MainPID"]))
        peer = trace_peer_uid(int(service["MainPID"]))
        negative = {user: negative_peer(user) for user in
                    ("lilith", "nobody", "lilith-memory-broker")}
        probe = probe_equivalent_sandbox(effective)
        relay_limits = assert_relay_restrictions()
        functional = functional_tests()
        require_api_baseline_unchanged(marker["apiRuntimeBaseline"])
        assert_unit_state(socket_active=True, service_active=True)
        return {"status": "STAGE_II_RUNTIME_EVIDENCE_COLLECTED",
                "authorizationId": marker["authorizationId"],
                "stage1": baseline["status"], "runDirectory": runtime_dir,
                "socket": sock, "actualBrokerProcess": process,
                "effectiveBrokerUnit": effective, "kernelPeer": peer,
                "negativePeers": negative, "equivalentSandboxProbe": probe,
                "relayRestrictions": relay_limits, "syntheticFunction": functional,
                "apiUnchanged": True, "bootEnabled": False}
    except Exception:
        # Preserve DBs, release, config, marker record, and journal for review.
        for unit in (SERVICE, SOCKET):
            subprocess.run(["/usr/bin/systemctl", "stop", unit],
                           capture_output=True, timeout=20)
        raise


def failure_stop() -> dict:
    """Workflow-only containment if a later evidence step fails."""
    assert_host()
    if USED.is_file() and not USED.is_symlink():
        for unit in (SERVICE, SOCKET):
            run_fixed("/usr/bin/systemctl", "stop", unit)
        return {"status": "STAGE_II_FAILURE_STOPPED_EVIDENCE_PRESERVED"}
    return {"status": "STAGE_II_NOT_CONSUMED_NO_SHUTDOWN_NEEDED"}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("operation", choices=("preflight", "authorize", "execute",
                                               "failure-stop"))
    args = parser.parse_args()
    try:
        result = {"preflight": preflight, "authorize": authorize,
                  "execute": execute, "failure-stop": failure_stop}[args.operation]()
        print(json.dumps(result, sort_keys=True))
    except Stage2Error as exc:
        print(json.dumps({"status": "STAGE_II_FAILED", "code": str(exc)}))
        raise SystemExit(1) from None
    except Exception:
        # Neither a Python traceback nor child stderr may expose fixture code.
        print(json.dumps({"status": "STAGE_II_FAILED",
                          "code": "CONTROL_EXCEPTION_REVIEW_REQUIRED"}))
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
