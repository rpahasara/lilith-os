#!/usr/bin/env python3
"""Exact known-old-unaccepted to reviewed-repair DEV snapshot transition."""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import re
import socket
import sqlite3
import stat
import subprocess
import sys
from pathlib import Path
from urllib.parse import quote
from urllib.request import ProxyHandler, Request, build_opener

if __package__:
    from scripts import trusted_broker_snapshot_invocation as invocation
    from scripts import trusted_broker_snapshot_release as release
else:
    import trusted_broker_snapshot_invocation as invocation
    import trusted_broker_snapshot_release as release


CONTROL = Path("/opt/lilith-trusted-controls/broker-snapshot")
KNOWN_OLD_UNACCEPTED = "8b4dbee055f5ca6b8e899d9cab8130ed4a6cbd9abb27fa71b7bbee88c41c6958"
APPROVED_REPAIRED_RELEASE = "36a3c93e5cb3556f5f2deb00bd4e4e0f72b71146b9f182f820b04bfa03db1aec"
DEV_HOST = "lilith-dev-01"
DEV_MACHINE_ID = "ae929170e6fa4c8ab9cc7b9547238d9d"
DEV_PROJECT = "lilith-agent-260823-27389"
DEV_ZONE = "projects/763184673487/zones/asia-southeast1-b"
DEV_INSTANCE_ID = "7687007163730582258"
DEV_FQDN = f"{DEV_HOST}.{DEV_ZONE.rsplit('/', 1)[-1]}.c.{DEV_PROJECT}.internal"
BASELINE = "abc33ebf8d43e8805f43ff11e663a4757bf558d9b62eda9669dabecbb7c9839a"
FRAME = b"LILITH_BROKER_CANDIDATE_DEV_SNAPSHOT_V1:"
ANCHOR_SCHEMA = "Stage2AcceptedInstallAnchorV1"
ACCEPTED_BOOT_ID = "24d1771d-e1b5-4e5f-816d-da08ad8b367a"
ACCEPTED_API_START_TICKS = 86941441
ACCEPTED_BROKER_START_TICKS = 91036598
ACCEPTED_BROKER_RELEASE = "817a83e44cec8965479fd97fc30b7a0b3ae49ab2"
ACCEPTED_BROKER_INVOCATION = "5c1eb955e2dc44e78139c416f0c9469a"
OWNER_DB = Path("/var/lib/lilith-memory-broker/owner-control/owner_control.db")
EVIDENCE_DB = Path("/var/lib/lilith-memory-broker/state/synthetic_evidence.db")
ANCHOR_FILE_SHA = {
    "/etc/systemd/system/lilith-os-api-dev.service": "bacfbac4b0f9502ebfe0a745cd2a9ff691f6a16bad9a8706f03085d588c21243",
    "/home/lilith/.hermes/lilith-os-dev/current/app.py": "bb0a4139641c0a81607263b07fa854deb34241b5fcfcdcab965c6a82dd8826d3",
    "/home/lilith/.hermes/lilith-os-dev/data/lilith-dev.db": "e4080d47ac782dc5578c4537b8aab277e73b27546e704ee2fff6fda506f67e6c",
    "/home/lilith/.hermes/lilith-os-dev/data/canonical-runtime.json": "65ac5077486cfe25665fc8f5815661b1653878182492a0309ec974e9394c08e7",
    "/etc/systemd/system/lilith-memory-broker.service": "6a9dca54b9051cc7788587a0f37601f67e16fc07de043cbc5d64e7123ed35689",
    "/etc/systemd/system/lilith-memory-broker.socket": "d9f21223b837fd4be98d3c67eb95625b00c8a0ee6922d06eb79605edb382e793",
    "/etc/lilith-memory-broker/dev.json": "c1787b34e5f1969fe98a0d3499c7913fde01a6eba7f2ee04f427a39cd02f27fb",
    "/etc/lilith-memory-broker/identities.json": "e1c808901bea374d7a0d16d49140125d8572012497905a690d634373a2070d23",
    str(OWNER_DB): "939b5a0e4c5471bac5843f9c17de9548494ab49bfa54a062994f57900de2b7bb",
    str(EVIDENCE_DB): "a4ff3d076a51019a6287c2a492a44e755dae5e9a7da55c9d9e942d9b9362c785",
}
ANCHOR_FILE_CUSTODY = {
    "/etc/systemd/system/lilith-os-api-dev.service": (0, 0, 0o644),
    "/home/lilith/.hermes/lilith-os-dev/current/app.py": (1001, 1002, 0o640),
    "/home/lilith/.hermes/lilith-os-dev/data/lilith-dev.db": (1001, 1002, 0o644),
    "/home/lilith/.hermes/lilith-os-dev/data/canonical-runtime.json": (1001, 1002, 0o600),
    "/etc/systemd/system/lilith-memory-broker.service": (0, 0, 0o644),
    "/etc/systemd/system/lilith-memory-broker.socket": (0, 0, 0o644),
    "/etc/lilith-memory-broker/dev.json": (0, 987, 0o640),
    "/etc/lilith-memory-broker/identities.json": (0, 0, 0o600),
    str(OWNER_DB): (999, 987, 0o600),
    str(EVIDENCE_DB): (999, 987, 0o600),
}
INCOMING_FILES = {
    "trusted_broker_snapshot_installer.py", "trusted_broker_snapshot_release.py",
    "trusted_broker_snapshot_invocation.py", "snapshot-release.tar.gz",
    "snapshot-release.attestation.json",
}


class InstallError(RuntimeError):
    def __init__(self, code: str, diagnostics: dict | None = None):
        super().__init__(code)
        self.code = code
        self.diagnostics = diagnostics or {}


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
    if (hostname not in (DEV_HOST, DEV_FQDN) or machine_id != DEV_MACHINE_ID or observed != {
        "project/project-id": DEV_PROJECT,
        "instance/zone": DEV_ZONE,
        "instance/id": DEV_INSTANCE_ID,
        "instance/name": DEV_HOST,
    }):
        raise InstallError("PINNED_DEV_IDENTITY_REQUIRED")


def _anchor_unit(name: str, properties: tuple[str, ...]) -> dict:
    result = subprocess.run(("/usr/bin/systemctl", "show", name,
                             "--property=" + ",".join(properties), "--no-pager"),
                            stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=10)
    if result.returncode != 0 or result.stderr.strip() or len(result.stdout) > 8192:
        raise InstallError("INSTALL_ANCHOR_UNIT_READ:" + name)
    values = dict(line.split("=", 1) for line in result.stdout.splitlines() if "=" in line)
    if set(values) != set(properties):
        raise InstallError("INSTALL_ANCHOR_UNIT_FIELDS:" + name)
    return values


def _anchor_incarnation(pid: int) -> dict:
    if pid <= 1:
        raise InstallError("INSTALL_ANCHOR_PID")
    raw = (Path("/proc") / str(pid) / "stat").read_text(encoding="ascii")
    marker = raw.rfind(") ")
    if marker < 0:
        raise InstallError("INSTALL_ANCHOR_PROC_STAT")
    fields = raw[marker + 2:].split()
    if len(fields) <= 19:
        raise InstallError("INSTALL_ANCHOR_PROC_FIELDS")
    return {"pid": pid,
            "bootId": Path("/proc/sys/kernel/random/boot_id").read_text(encoding="ascii").strip(),
            "startTicks": int(fields[19])}


def _anchor_file(path: str) -> dict:
    target = Path(path)
    info = target.lstat()
    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_size > 16 * 1024 * 1024:
        raise InstallError("INSTALL_ANCHOR_FILE_CUSTODY:" + path)
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_CLOEXEC", 0)
    fd = os.open(target, flags)
    try:
        opened = os.fstat(fd)
        if (opened.st_dev, opened.st_ino) != (info.st_dev, info.st_ino):
            raise InstallError("INSTALL_ANCHOR_FILE_RACE:" + path)
        with os.fdopen(fd, "rb", closefd=False) as stream:
            content = stream.read(16 * 1024 * 1024 + 1)
    finally:
        os.close(fd)
    if len(content) != opened.st_size or len(content) > 16 * 1024 * 1024:
        raise InstallError("INSTALL_ANCHOR_FILE_SIZE:" + path)
    return {"sha256": hashlib.sha256(content).hexdigest(), "uid": opened.st_uid,
            "gid": opened.st_gid, "mode": stat.S_IMODE(opened.st_mode)}


def _anchor_counts(path: Path, tables: tuple[str, ...]) -> dict[str, int]:
    uri = "file:" + quote(str(path), safe="/") + "?mode=ro&immutable=1"
    connection = sqlite3.connect(uri, uri=True, timeout=5)
    try:
        connection.execute("PRAGMA query_only=ON")
        return {table: int(connection.execute("SELECT COUNT(*) FROM " + table).fetchone()[0])
                for table in tables}
    finally:
        connection.close()


def collect_install_anchor() -> dict:
    """Small direct continuity gate; deliberately not lifecycle validation."""
    host_keys = ("project/project-id", "instance/zone", "instance/id", "instance/name")
    host = {key: _metadata(key) for key in host_keys}
    host["hostname"] = socket.getfqdn()
    host["machineId"] = Path("/etc/machine-id").read_text(encoding="ascii").strip()
    properties = ("LoadState", "ActiveState", "SubState", "MainPID", "NRestarts",
                  "ExecMainStartTimestamp", "InvocationID")
    api = _anchor_unit("lilith-os-api-dev.service", properties)
    broker = _anchor_unit("lilith-memory-broker.service", properties)
    broker_socket = _anchor_unit("lilith-memory-broker.socket",
                                 ("LoadState", "ActiveState", "SubState", "UnitFileState"))
    request = Request("http://127.0.0.1:8765/health")
    with build_opener(ProxyHandler({})).open(request, timeout=5) as response:
        health = json.loads(response.read(4097))
    owner_socket = Path("/run/lilith-memory/owner.sock").lstat()
    if not stat.S_ISSOCK(owner_socket.st_mode):
        raise InstallError("INSTALL_ANCHOR_OWNER_SOCKET")
    listening = any(len(parts) >= 8 and parts[7] == "/run/lilith-memory/owner.sock"
                    and parts[3] == "00010000" and parts[4] == "0001"
                    for line in Path("/proc/net/unix").read_text(encoding="ascii").splitlines()[1:]
                    if (parts := line.split()))
    files_before = {path: _anchor_file(path) for path in ANCHOR_FILE_SHA}
    counts = {
        "owner": _anchor_counts(OWNER_DB, ("owner_proof_challenge_v1", "owner_request_v1",
                                           "synthetic_claim_v1")),
        "evidence": _anchor_counts(EVIDENCE_DB, ("synthetic_evidence_v1",)),
    }
    if files_before != {path: _anchor_file(path) for path in ANCHOR_FILE_SHA}:
        raise InstallError("INSTALL_ANCHOR_CONCURRENT_DRIFT")
    return {
        "schema": ANCHOR_SCHEMA,
        "host": host,
        "api": {"unit": api, "incarnation": _anchor_incarnation(int(api["MainPID"])),
                "health": {"status": health.get("status"), "database": health.get("database")}},
        "broker": {"unit": broker, "socketUnit": broker_socket,
                   "incarnation": _anchor_incarnation(int(broker["MainPID"])),
                   "releaseTarget": os.readlink("/opt/lilith-memory-broker/current"),
                   "ownerSocket": {"uid": owner_socket.st_uid, "gid": owner_socket.st_gid,
                                   "mode": stat.S_IMODE(owner_socket.st_mode),
                                   "listening": listening}},
        "files": files_before,
        "counts": counts,
    }


def validate_install_anchor(value: dict) -> None:
    host = value.get("host", {})
    if (value.get("schema") != ANCHOR_SCHEMA or set(value) !=
            {"schema", "host", "api", "broker", "files", "counts"} or
            host.get("hostname") not in (DEV_HOST, DEV_FQDN) or
            {key: host.get(key) for key in ("project/project-id", "instance/zone", "instance/id", "instance/name", "machineId")} != {
                "project/project-id": DEV_PROJECT, "instance/zone": DEV_ZONE,
                "instance/id": DEV_INSTANCE_ID, "instance/name": DEV_HOST,
                "machineId": DEV_MACHINE_ID,
            } or value.get("files") != {
                path: {"sha256": sha, "uid": ANCHOR_FILE_CUSTODY[path][0],
                       "gid": ANCHOR_FILE_CUSTODY[path][1], "mode": ANCHOR_FILE_CUSTODY[path][2]}
                for path, sha in ANCHOR_FILE_SHA.items()
            } or value.get("counts") != {
                "owner": {"owner_proof_challenge_v1": 24, "owner_request_v1": 24,
                          "synthetic_claim_v1": 2},
                "evidence": {"synthetic_evidence_v1": 2},
            }):
        raise InstallError("INSTALL_ANCHOR_DRIFT")
    api, broker = value.get("api", {}), value.get("broker", {})
    if (api.get("unit", {}).get("LoadState") != "loaded" or
            api["unit"].get("ActiveState") != "active" or api["unit"].get("SubState") != "running" or
            api["unit"].get("MainPID") != "88740" or api["unit"].get("NRestarts") != "0" or
            api.get("incarnation") != {"pid": 88740, "bootId": ACCEPTED_BOOT_ID,
                                       "startTicks": ACCEPTED_API_START_TICKS} or
            api.get("health") != {"status": "ok", "database": True} or
            broker.get("unit", {}).get("LoadState") != "loaded" or
            broker["unit"].get("ActiveState") != "active" or
            broker["unit"].get("SubState") != "running" or
            broker["unit"].get("MainPID") != "96650" or
            broker["unit"].get("NRestarts") != "0" or
            broker["unit"].get("InvocationID") != ACCEPTED_BROKER_INVOCATION or
            broker["unit"].get("ExecMainStartTimestamp") != "Thu 2026-09-24 06:51:22 UTC" or
            broker.get("incarnation") != {"pid": 96650, "bootId": ACCEPTED_BOOT_ID,
                                          "startTicks": ACCEPTED_BROKER_START_TICKS} or
            broker.get("releaseTarget") != "releases/" + ACCEPTED_BROKER_RELEASE or
            broker.get("socketUnit") != {"LoadState": "loaded", "ActiveState": "active",
                                         "SubState": "running", "UnitFileState": "disabled"} or
            broker.get("ownerSocket") != {"uid": 999, "gid": 988, "mode": 0o660,
                                           "listening": True}):
        raise InstallError("INSTALL_ANCHOR_RUNTIME_DRIFT")


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


def _verify_runtime_pins() -> None:
    import _sqlite3
    pins = release.RUNTIME
    if Path(sys.executable).resolve() != Path(pins["pythonExecutable"]).resolve():
        raise InstallError("INSTALL_RUNTIME_PIN_DRIFT")
    actual = {"pythonVersion": ".".join(map(str, sys.version_info[:3])),
              "pythonSha256": hashlib.sha256(Path("/usr/bin/python3").read_bytes()).hexdigest(),
              "sqliteVersion": sqlite3.sqlite_version,
              "sqliteModuleSha256": hashlib.sha256(Path(sqlite3.__file__).read_bytes()).hexdigest(),
              "sqliteExtensionSha256": hashlib.sha256(Path(_sqlite3.__file__).read_bytes()).hexdigest()}
    if any(actual[key] != pins[key] for key in actual):
        raise InstallError("INSTALL_RUNTIME_PIN_DRIFT")
    for name, expected in (("python3.12-minimal", pins["pythonPackage"]),
                           ("libsqlite3-0", pins["sqlitePackage"])):
        result = subprocess.run(("/usr/bin/dpkg-query", "-W", "-f=${Version}", name),
                                stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=10)
        if result.returncode != 0 or name + "=" + result.stdout != expected:
            raise InstallError("INSTALL_RUNTIME_PACKAGE_DRIFT:" + name)


def _installed_bytes(final: Path, release_id: str, payloads: dict[str, bytes],
                     *, root_custody: bool) -> None:
    _directory(final, 0o755, root_custody=root_custody)
    if {p.name for p in final.iterdir()} != {"bin", "lib", "release-manifest.json"}:
        raise InstallError("INSTALLED_FILE_SET")
    for name, expected in (("bin", {"lilith-broker-dev-snapshot", "lilith-broker-dev-invocation"}),
                           ("lib", {"verify_broker_dev_lifecycle.py"})):
        _directory(final / name, 0o755, root_custody=root_custody)
        if {p.name for p in (final / name).iterdir()} != expected:
            raise InstallError("INSTALLED_FILE_SET")
    manifest = final / "release-manifest.json"
    _file(manifest, 0o644, root_custody=root_custody)
    expected_manifest = release.canonical(release.make_manifest(payloads))
    actual_manifest = manifest.read_bytes()
    if actual_manifest != expected_manifest or hashlib.sha256(actual_manifest).hexdigest() != release_id:
        raise InstallError("INSTALLED_MANIFEST_MISMATCH")
    for name, data in payloads.items():
        path = final / name
        _file(path, 0o755 if name.startswith("bin/") else 0o644, root_custody=root_custody)
        if hashlib.sha256(path.read_bytes()).digest() != hashlib.sha256(data).digest():
            raise InstallError("INSTALLED_PAYLOAD_MISMATCH:" + name)


# This fixed loader is installer-private. The selected CLI's public interface
# still has no release-path argument; the installed CLI rechecks its own bytes.
DIRECT_LOADER = f"""import errno,importlib.machinery,os,pathlib,types,sys
p=pathlib.Path('/opt/lilith-trusted-controls/broker-snapshot/releases/{APPROVED_REPAIRED_RELEASE}')
m=types.ModuleType('installed_snapshot')
importlib.machinery.SourceFileLoader(m.__name__,str(p/'bin/lilith-broker-dev-snapshot')).exec_module(m)
o=m.decode_sudo_observation(os.environ.get('LILITH_TRUSTED_SUDO_OBSERVATION_V1'))
result=m.collect(p,sudo_observation=o)
for path in ('/var/lib/lilith-memory-broker/owner-control/owner_control.db',
             '/etc/lilith-memory-broker/dev.json',
             '/home/lilith/.hermes/lilith-os-dev/data/canonical-runtime.json',
             str(p/'release-manifest.json')):
    try:
        fd=os.open(path,os.O_WRONLY|os.O_NOFOLLOW)
    except OSError as exc:
        if exc.errno not in (errno.EACCES,errno.EPERM,errno.EROFS):
            raise
    else:
        os.close(fd)
        raise RuntimeError('SNAPSHOT_REPRESENTATIVE_WRITE_PERMITTED')
sys.stdout.buffer.write(b'LILITH_CONFINEMENT_EVIDENCE_V1:READ_PASS_WRITE_DENIED\\n')
sys.stdout.buffer.write(m.frame(result))
"""


def direct_command(encoded_observation: str) -> tuple[str, ...]:
    # Validate the transport with the same closed policy used by the release
    # invoker; only replace its fixed selected-tool executable and operation.
    command = invocation.command(encoded_observation)
    if command[-5:] != ("/usr/bin/python3", "-I", "-B", invocation.TOOL, invocation.OPERATION):
        raise InstallError("SNAPSHOT_INVOCATION_POLICY_DRIFT")
    return (*command[:-5], "/usr/bin/python3", "-I", "-B", "-c", DIRECT_LOADER)


def _diagnostics(result: subprocess.CompletedProcess) -> dict:
    def excerpt(raw: bytes) -> str:
        # Bound output and suppress long token-like strings from errors.
        value = raw[:768].decode("utf-8", "replace")
        value = re.sub(r"[A-Za-z0-9_+/=-]{40,}", "[redacted]", value)
        return "".join(ch if ch.isprintable() or ch in "\n\t" else "?" for ch in value)
    return {"returncode": result.returncode, "stdoutBytes": len(result.stdout),
            "stderrBytes": len(result.stderr), "stdoutExcerpt": excerpt(result.stdout),
            "stderrExcerpt": excerpt(result.stderr)}


def _snapshot_result(result: subprocess.CompletedProcess, *, direct: bool = False) -> dict:
    if len(result.stdout) > 3 * 1024 * 1024 or len(result.stderr) > 4096:
        raise InstallError("SNAPSHOT_SELF_TEST_BOUNDS", _diagnostics(result))
    if result.returncode != 0:
        raise InstallError("SNAPSHOT_SELF_TEST_FAILED", _diagnostics(result))
    lines = result.stdout.splitlines()
    proof = b"LILITH_CONFINEMENT_EVIDENCE_V1:READ_PASS_WRITE_DENIED"
    if direct and (len(lines) != 2 or lines[0] != proof or not lines[1].startswith(FRAME)):
        raise InstallError("SNAPSHOT_CONFINEMENT_EVIDENCE", _diagnostics(result))
    if not direct and (len(lines) != 1 or not lines[0].startswith(FRAME)):
        raise InstallError("SNAPSHOT_SELF_TEST_FRAME", _diagnostics(result))
    frame_line = lines[-1]
    try:
        size, sha, encoded = frame_line[len(FRAME):].split(b":", 2)
        if not re.fullmatch(rb"[1-9][0-9]{0,6}", size) or not re.fullmatch(rb"[0-9a-f]{64}", sha):
            raise ValueError("frame")
        data = base64.b64decode(encoded, validate=True)
        if len(data) != int(size) or len(data) > 2 * 1024 * 1024 or \
                hashlib.sha256(data).hexdigest().encode() != sha:
            raise ValueError("digest")
        value = json.loads(data)
        if not isinstance(value, dict) or json.dumps(value, sort_keys=True, separators=(",", ":"),
                                                    ensure_ascii=False).encode() != data:
            raise ValueError("accepted state")
        _validate_snapshot(value)
        return value
    except (ValueError, UnicodeError, KeyError, TypeError, InstallError) as exc:
        raise InstallError("SNAPSHOT_SELF_TEST_RESULT", _diagnostics(result)) from exc


def _self_test(*, direct: bool) -> dict:
    try:
        if direct:
            encoded = invocation.observe_sudo()
            command = direct_command(encoded)
        else:
            command = ("/usr/bin/python3", "-I", "-B", invocation.INVOKER)
        result = subprocess.run(command, stdin=subprocess.DEVNULL, capture_output=True, timeout=120)
    except (OSError, subprocess.TimeoutExpired, invocation.InvocationError) as exc:
        raise InstallError("SNAPSHOT_SELF_TEST_INVOCATION", {"exception": type(exc).__name__}) from exc
    return _snapshot_result(result, direct=direct)


def install(control: Path, release_id: str, *, root_custody: bool = True,
            self_test=None) -> dict:
    if not release.SHA64.fullmatch(release_id) or release_id != APPROVED_REPAIRED_RELEASE:
        raise InstallError("UNAPPROVED_REPAIRED_RELEASE")
    if root_custody:
        if not hasattr(os, "geteuid") or os.geteuid() != 0:
            raise InstallError("ROOT_REQUIRED")
        assert_dev_host()
        validate_install_anchor(collect_install_anchor())
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
    if root_custody:
        _verify_runtime_pins()
    if hashlib.sha256((incoming / "trusted_broker_snapshot_invocation.py").read_bytes()).hexdigest() != \
            hashlib.sha256(payloads["bin/lilith-broker-dev-invocation"]).hexdigest():
        raise InstallError("INVOKER_SOURCE_MISMATCH")
    releases = control / "releases"
    current = control / "current"
    final = releases / release_id
    staging = releases / (release_id + ".staging")
    _directory(releases, 0o755, root_custody=root_custody)
    if final.exists() or final.is_symlink() or staging.exists() or staging.is_symlink():
        raise InstallError("INSTALL_EXISTING_RELEASE")
    if {p.name for p in releases.iterdir()} != {KNOWN_OLD_UNACCEPTED}:
        raise InstallError("INSTALL_UNEXPECTED_RELEASE")
    _directory(releases / KNOWN_OLD_UNACCEPTED, 0o755, root_custody=root_custody)
    pointer = current.lstat()
    if not stat.S_ISLNK(pointer.st_mode) or os.readlink(current) != "releases/" + KNOWN_OLD_UNACCEPTED or \
            (root_custody and (pointer.st_uid, pointer.st_gid) != (0, 0)):
        raise InstallError("INSTALL_UNEXPECTED_CURRENT")
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
    # Re-open actual installed files before executing any of them or touching
    # the selected pointer. The archive check alone is not installation proof.
    _installed_bytes(final, release_id, payloads, root_custody=root_custody)
    checker = self_test or _self_test
    try:
        first = checker(direct=True)
        _validate_snapshot(first)
    except Exception as exc:
        diagnostics = exc.diagnostics if isinstance(exc, InstallError) else {
            "exception": type(exc).__name__}
        raise InstallError("NEW_RELEASE_INSTALLED_UNSELECTED_UNACCEPTED", {
            "selfTestResult": "FAIL", "reason": str(exc)[:128],
            "diagnostics": diagnostics}) from exc
    temporary = control / (".current-" + release_id)
    if temporary.exists() or temporary.is_symlink():
        raise InstallError("INSTALL_POINTER_COLLISION")
    pointer = current.lstat()
    if not stat.S_ISLNK(pointer.st_mode) or os.readlink(current) != "releases/" + KNOWN_OLD_UNACCEPTED or \
            (root_custody and (pointer.st_uid, pointer.st_gid) != (0, 0)):
        raise InstallError("INSTALL_UNEXPECTED_CURRENT")
    os.symlink("releases/" + release_id, temporary)
    os.replace(temporary, current)
    _fsync_dir(control)
    pointer = current.lstat()
    if (not stat.S_ISLNK(pointer.st_mode) or os.readlink(current) != "releases/" + release_id or
            (root_custody and (pointer.st_uid, pointer.st_gid) != (0, 0))):
        raise InstallError("INSTALLED_POINTER_CUSTODY")
    try:
        second = checker(direct=False)
        _validate_snapshot(second)
    except Exception as exc:
        diagnostics = exc.diagnostics if isinstance(exc, InstallError) else {
            "exception": type(exc).__name__}
        raise InstallError("SELECTED_BUT_UNACCEPTED_SECOND_SNAPSHOT_FAILED", {
            "firstCompleteSnapshotDigest": first["completeDigestSha256"],
            "reason": str(exc)[:128], "diagnostics": diagnostics}) from exc
    if first["completeDigestSha256"] != second["completeDigestSha256"]:
        raise InstallError("SELECTED_BUT_UNACCEPTED_DIGEST_MISMATCH", {
            "firstCompleteSnapshotDigest": first["completeDigestSha256"],
            "secondCompleteSnapshotDigest": second["completeDigestSha256"]})
    return {
        "result": "TRUSTED_SNAPSHOT_RELEASE_ACCEPTED", "releaseId": release_id,
        "oldPreservedReleaseId": KNOWN_OLD_UNACCEPTED,
        "currentTarget": "releases/" + release_id,
        "selfTestResult": "PASS", "selfTestReleaseId": release_id,
        "selfTestLifecycleProfile": first["profile"],
        "selfTestAcceptedBaselineDigest": first["acceptedBaselineDigest"],
        "selfTestCompleteSnapshotDigest": first["completeDigestSha256"],
        "secondCompleteSnapshotDigest": second["completeDigestSha256"],
        "confinementResult": "PASS_BY_INSTALLED_CLI",
        "representativeReadResult": "PASS_BY_ACCEPTED_LIFECYCLE",
        "representativeWriteDenialResult": "PASS_BY_CONFINED_OPEN_PROBE",
    }


def _validate_snapshot(value: dict) -> None:
    if (not isinstance(value, dict) or set(value) != {
            "schema", "operation", "profile", "toolReleaseId", "manifestSha256",
            "acceptedBaselineDigest", "completeDigestSha256", "validation", "snapshot"} or
            value["schema"] != "BrokerCandidateDevSnapshotV1" or
            value["operation"] != "SNAPSHOT_ACCEPTED_STAGE2" or
            value["profile"] != "POST_STAGE_II_ACCEPTED_V1" or
            value["toolReleaseId"] != APPROVED_REPAIRED_RELEASE or
            value["manifestSha256"] != APPROVED_REPAIRED_RELEASE or
            value["acceptedBaselineDigest"] != BASELINE or value["validation"] != "PASS" or
            not isinstance(value["snapshot"], dict) or
            value["snapshot"].get("profile") != "POST_STAGE_II_ACCEPTED_V1" or
            value["snapshot"].get("stage2AcceptedBaseline", {}).get(
                "stage2AcceptedBaselineDigest") != BASELINE or
            not isinstance(value["completeDigestSha256"], str) or
            value["completeDigestSha256"] != hashlib.sha256(json.dumps(
                value["snapshot"], sort_keys=True, separators=(",", ":"),
                ensure_ascii=False).encode()).hexdigest()):
        raise InstallError("SNAPSHOT_RESULT_CONTRACT")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--release-id")
    parser.add_argument("--check-anchor", action="store_true")
    args = parser.parse_args()
    try:
        if args.check_anchor:
            if args.release_id is not None:
                parser.error("--check-anchor accepts no release ID")
            if not hasattr(os, "geteuid") or os.geteuid() != 0:
                raise InstallError("ROOT_REQUIRED")
            assert_dev_host()
            validate_install_anchor(collect_install_anchor())
            result = {"result": "STAGE2_ACCEPTED_INSTALL_ANCHOR_PASS",
                      "schema": ANCHOR_SCHEMA}
        else:
            if args.release_id is None:
                parser.error("--release-id required for installation")
            result = install(CONTROL, args.release_id)
    except InstallError as exc:
        print(release.canonical({"result": exc.code, "diagnostics": exc.diagnostics}).decode(), end="")
        raise SystemExit(1) from None
    print(release.canonical(result).decode(), end="")


if __name__ == "__main__":
    main()
