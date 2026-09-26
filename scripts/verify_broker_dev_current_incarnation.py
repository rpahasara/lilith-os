#!/usr/bin/env python3
"""Read-only current-incarnation baseline candidate for the DEV memory broker.

DR-1 (docs/architecture/slice15b2b-dr1-broker-restart-forensics.md): the
accepted Stage II broker process no longer exists. This observer records the
replacement incarnation's facts and compares everything that is *not* process
identity against the accepted Stage II artifact contract.

Stream protected-main source to ``sudo python3 -I -B - baseline`` on
lilith-dev-01 only, and only when the owner has separately authorized the run.

It never starts, stops, restarts, or reloads a unit; never opens SQLite (file
bytes are hashed, so no -wal/-shm is created); never connects to owner.sock;
never runs ``sudo -u``; never creates, chmods, or removes a path. The only
subprocess is ``systemctl show``.

The output is a *candidate* for separate owner acceptance. It never claims
Stage II acceptance for this incarnation, and it never reports a missing path
as a denial.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import socket
import stat
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import ProxyHandler, Request, build_opener

try:  # Pure-policy regressions also run on Windows.
    import grp
    import pwd
except ImportError:  # pragma: no cover
    grp = None
    pwd = None


SCHEMA = "BrokerDevCurrentIncarnationBaselineCandidateV1"
PROJECT = "lilith-agent-260823-27389"
ZONE = "asia-southeast1-b"
DEV_INSTANCE = "lilith-dev-01"
DEV_INSTANCE_ID = "7687007163730582258"
DEV_MACHINE_ID = "ae929170e6fa4c8ab9cc7b9547238d9d"
DEV_HOSTNAME = f"{DEV_INSTANCE}.{ZONE}.c.{PROJECT}.internal"
RELEASE_SHA = "817a83e44cec8965479fd97fc30b7a0b3ae49ab2"
MANIFEST_SHA = "7a46ac83001411a29b1bc4be7e0f91f09c5879967386c452b2620e23d16e4614"

ROOT = Path("/opt/lilith-memory-broker")
CONFIG = Path("/etc/lilith-memory-broker")
STATE = Path("/var/lib/lilith-memory-broker")
RUNTIME = Path("/run/lilith-memory")
OWNER_DB = STATE / "owner-control/owner_control.db"
EVIDENCE_DB = STATE / "state/synthetic_evidence.db"
SERVICE = "lilith-memory-broker.service"
SOCKET = "lilith-memory-broker.socket"
CONTROLLER = "lilith-stage3-a2-final.service"
BROKER_CMDLINE = "/opt/lilith-memory-broker/current/venv/bin/python -B -m lilith_memory_broker.server"

# Accepted Stage II process identity (run 35965971283). Reference only: this
# observer never requires it and reports processContinuity from it.
ACCEPTED_SERVICE_INVOCATION = "5c1eb955e2dc44e78139c416f0c9469a"
ACCEPTED_BROKER_PID = 96650
ACCEPTED_BROKER_START_TICKS = 91036598
ACCEPTED_BROKER_BOOT_ID = "24d1771d-e1b5-4e5f-816d-da08ad8b367a"

# Accepted Stage II artifact contract (verify_broker_dev_lifecycle.ACCEPTED_FILES,
# minus the API app and unit, which routine B1c deployments legitimately change).
UNIT_FILES = {
    "/etc/systemd/system/lilith-memory-broker.service": ("6a9dca54b9051cc7788587a0f37601f67e16fc07de043cbc5d64e7123ed35689", 0, 0, 0o644),
    "/etc/systemd/system/lilith-memory-broker.socket": ("d9f21223b837fd4be98d3c67eb95625b00c8a0ee6922d06eb79605edb382e793", 0, 0, 0o644),
    "/etc/tmpfiles.d/lilith-memory-broker.conf": ("e6139f16b001a3c36e9ff3db733f19a3a7ce06b1d0fbc923591bc17b2d4df86e", 0, 0, 0o644),
}
CONFIG_FILES = {
    str(CONFIG / "dev.json"): ("c1787b34e5f1969fe98a0d3499c7913fde01a6eba7f2ee04f427a39cd02f27fb", 0, 987, 0o640),
    str(CONFIG / "identities.json"): ("e1c808901bea374d7a0d16d49140125d8572012497905a690d634373a2070d23", 0, 0, 0o600),
    str(CONFIG / "b1b2b-authorization.used.json"): ("2c9975086f7bc41aec872ae0bdeb9e5f9da7d312495ab193e46879de5302274b", 0, 0, 0o600),
    str(CONFIG / "b1b2b-stage2-authorization.used.json"): ("d75394b18906546095650851b0c18aac3208ac3fb04bde43655c80482602ef51", 0, 0, 0o600),
    str(CONFIG / "b1b2b-stage2-retry2-authorization.used.json"): ("ad43a9e3b822390b227d4e72d4a29a9f2915773f646b192015d98f7f9e720249", 0, 0, 0o600),
}
STATE_FILES = {
    str(OWNER_DB): ("939b5a0e4c5471bac5843f9c17de9548494ab49bfa54a062994f57900de2b7bb", 999, 987, 0o600),
    str(EVIDENCE_DB): ("a4ff3d076a51019a6287c2a492a44e755dae5e9a7da55c9d9e942d9b9362c785", 999, 987, 0o600),
}
DIRECTORIES = {
    str(ROOT): (0, 0, 0o755), str(ROOT / "releases"): (0, 0, 0o755),
    str(CONFIG): (0, 0, 0o755), str(STATE): (999, 987, 0o700),
    str(STATE / "owner-control"): (999, 987, 0o700), str(STATE / "state"): (999, 987, 0o700),
}
SERVICE_EXPECTED = {
    "LoadState": "loaded", "ActiveState": "active", "SubState": "running",
    "UnitFileState": "static", "FragmentPath": "/etc/systemd/system/lilith-memory-broker.service",
    "DropInPaths": "", "User": "lilith-memory-broker", "Group": "lilith-memory-broker",
    "Restart": "on-failure", "NRestarts": "0",
}
SANDBOX_EXPECTED = {
    "NoNewPrivileges": "yes", "PrivateTmp": "yes", "PrivateDevices": "yes",
    "ProtectSystem": "strict", "ProtectHome": "yes", "ProtectKernelTunables": "yes",
    "ProtectKernelModules": "yes", "ProtectControlGroups": "yes", "RestrictNamespaces": "yes",
    "LockPersonality": "yes", "CapabilityBoundingSet": "", "AmbientCapabilities": "",
    "RestrictAddressFamilies": "AF_UNIX", "IPAddressDeny": "0.0.0.0/0 ::/0",
    "ReadOnlyPaths": "/opt/lilith-memory-broker /etc/lilith-memory-broker",
    "ReadWritePaths": "/var/lib/lilith-memory-broker", "UMask": "0077",
    "StateDirectory": "lilith-memory-broker", "StateDirectoryMode": "0700",
    "DynamicUser": "no", "SupplementaryGroups": "",
    "Environment": "LILITH_ENV=dev PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1",
}
SOCKET_EXPECTED = {
    "LoadState": "loaded", "ActiveState": "active", "UnitFileState": "disabled",
    "FragmentPath": "/etc/systemd/system/lilith-memory-broker.socket", "DropInPaths": "",
    "Listen": "/run/lilith-memory/owner.sock (Stream)", "SocketUser": "lilith-memory-broker",
    "SocketGroup": "lilith-memory-ipc", "SocketMode": "0660",
}
CONTROLLER_EXPECTED = {
    "ActiveState": "failed", "SubState": "failed", "Result": "exit-code",
    "ExecMainStatus": "1", "Restart": "no", "NRestarts": "0",
}

# Stage III artifacts as observed read-only by the DR-1 forensics on
# 2026-09-26 (no earlier record pinned their hashes).
STAGE3_VAULT = Path("/var/lib/.lilith-memory-broker-stage3-a2")
STAGE3_JOURNAL = {"000-INTENT.json": "1ef684467f40d25731edb4e871ad7d5f7fd238821a2484b371fe664fea555bd7"}
STAGE3_PRESENT = {
    "/var/lib/.lilith-memory-broker-stage3-a2-dispatch-attempt.json": "d4f75cb5a7b40d142695ee8f3627394031597714a613ca4258a87f6ac5e71b4d",
    "/var/lib/.lilith-memory-broker-stage3-a2-final-attempt.json": "b389f62e74bf0c0e9476d2d6d321a5f0719a13125942e7d85cb41aef1cdb4374",
    str(CONFIG / "b1b2b-stage3-a2-authorization.json"): "84049b4b97b7d262efa1a5e5ccd5dc279e25d9f51dec685e7b64933ba171805c",
}
STAGE3_ABSENT = (
    str(CONFIG / "b1b2b-stage3-a2-authorization.used.json"),
    "/run/lilith-memory-stage3/a2-arm.json",
    "/run/lilith-stage3-a2/guard.json",
    "/run/lilith-stage3-a2/activation.ready",
    str(STAGE3_VAULT / "guard.claim.json"),
)

# B1c routine deployer boundary: policy text and helper identity only.
DEPLOYER = "sa_112096412008414111981"
DEPLOYER_SUDOERS = Path("/etc/sudoers.d/lilith-dev-deployer")
DEPLOYER_SUDOERS_TEXT = (
    "# LILITH 15B2b-B1c: the routine DEV deployer may run only the fixed DEV Core API\n"
    "# deployment helper. No shell, interpreter, systemctl, broker, or Stage III rule.\n"
    f"{DEPLOYER} ALL=(root) NOPASSWD: /usr/local/sbin/lilith-dev-deploy deploy *, "
    "/usr/local/sbin/lilith-dev-deploy status\n"
)
DEPLOY_HELPER = Path("/usr/local/sbin/lilith-dev-deploy")
DEPLOY_HELPER_SHA = "85b260a29f29c182d7da867c25a1e9406fc713591e217eaa927031696e8755b8"

# Planned B1b-3d custody paths (design §15). Before B1b-3d L1 they must not
# exist. Absence is reported as NOT_YET_PRESENT, never as DENIED (DR-5).
CUSTODY_PATHS = (
    "/etc/credstore.encrypted/lilith-authority-dev.owner-actor.cred",
    "/etc/credstore.encrypted/lilith-recovery-witness.witness.cred",
    "/etc/lilith-authority-dev", "/etc/lilith-authority-dev/INSTALLED",
    "/var/lib/lilith-authority-dev", "/var/lib/lilith-recovery-witness",
    "/run/lilith-authority-dev", "/run/lilith-recovery-witness",
    "/etc/systemd/system/lilith-authority-dev.service",
    "/etc/systemd/system/lilith-recovery-witness.service",
    "/opt/lilith-authority-dev",
)
AUTHORITY_SENSITIVE_SERVICES = ("lilith-memory-broker", "lilith-authority-dev",
                                "lilith-recovery-witness")
NEEDRESTART_CONFIG = (Path("/etc/needrestart/needrestart.conf"), Path("/etc/needrestart/conf.d"))

READ_ONLY_SYSTEMCTL = "/usr/bin/systemctl"
MAX_FILE = 64 * 1024 * 1024


class BaselineError(RuntimeError):
    pass


def require(condition: bool, code: str) -> None:
    if not condition:
        raise BaselineError(code)


# ---------------------------------------------------------------- pure parsers

def readonly_argv(argv: list[str]) -> list[str]:
    """The only subprocess allowed is `systemctl show <unit> --property=...`."""
    require(len(argv) == 5 and argv[0] == READ_ONLY_SYSTEMCTL and argv[1] == "show"
            and re.fullmatch(r"[A-Za-z0-9@_.-]+\.(service|socket)", argv[2]) is not None
            and argv[3].startswith("--property=") and argv[4] == "--no-pager",
            "NON_READ_ONLY_COMMAND_REFUSED")
    return argv


def parse_show(text: str) -> dict[str, str]:
    return dict(line.split("=", 1) for line in text.splitlines() if "=" in line)


def parse_status(text: str) -> dict:
    fields = dict((k, v.strip()) for k, v in
                  (line.split(":", 1) for line in text.splitlines() if ":" in line))
    return {
        "uid": [int(x) for x in fields["Uid"].split()],
        "gid": [int(x) for x in fields["Gid"].split()],
        "groups": [int(x) for x in fields.get("Groups", "").split()],
        "ppid": int(fields["PPid"]),
        "noNewPrivs": fields.get("NoNewPrivs"),
        "seccomp": fields.get("Seccomp"),
        "capabilities": {name: fields.get(name) for name in ("CapPrm", "CapEff", "CapBnd", "CapAmb")},
    }


def parse_start_ticks(proc_stat: str) -> int:
    marker = proc_stat.rfind(") ")
    require(marker > 0, "PROCESS_STAT_FORMAT")
    fields = proc_stat[marker + 2:].split()
    require(len(fields) > 19, "PROCESS_STAT_FIELDS")
    return int(fields[19])


def start_time_utc(start_ticks: int, boot_time: int, clock_ticks: int) -> str:
    seconds = boot_time + start_ticks // clock_ticks
    return datetime.fromtimestamp(seconds, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_maps(text: str) -> dict[str, dict]:
    """Return file-backed mappings: path -> {inode, deleted}. Anonymous and
    pseudo mappings are skipped."""
    found: dict[str, dict] = {}
    for line in text.splitlines():
        parts = line.split(None, 5)
        if len(parts) < 6 or not parts[5].startswith("/") or parts[4] == "0":
            continue
        path = parts[5]
        deleted = path.endswith(" (deleted)")
        if deleted:
            path = path[: -len(" (deleted)")]
        if path.startswith(("/dev/", "/memfd:", "/SYSV")):
            continue
        entry = found.setdefault(path, {"inode": int(parts[4]), "deleted": False})
        entry["deleted"] = entry["deleted"] or deleted
    return found


def parse_needrestart(texts: list[str]) -> dict:
    """Report the effective restart mode and any service-specific override."""
    active = []
    for text in texts:
        for line in text.splitlines():
            stripped = line.strip()
            if stripped and not stripped.startswith("#"):
                active.append(stripped)
    restart = "DEFAULT"
    for line in active:
        match = re.match(r"\$nrconf\{restart\}\s*=\s*'([a-z])'", line)
        if match:
            restart = match.group(1)
    overrides = [line for line in active if "override_rc" in line or "blacklist_rc" in line]
    return {
        "restartMode": restart,
        "serviceSpecificExclusion": {
            name: any(name in line for line in overrides) for name in AUTHORITY_SENSITIVE_SERVICES
        },
    }


def classify_custody_path(meta: dict) -> str:
    """DR-5: a missing path is never a denial. Only PATH_EXISTS may later be
    followed by an ACCESS_DENIED proof; this observer proves no denial."""
    return "PRESENT" if meta.get("present") else "NOT_YET_PRESENT"


def canonical_sha256(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                     ensure_ascii=False).encode()).hexdigest()


# ------------------------------------------------------------------ evaluation

def _matches(files: dict, contract: dict) -> bool:
    return all(files.get(path) == {"present": True, "sha256": sha, "uid": uid, "gid": gid, "mode": mode}
               for path, (sha, uid, gid, mode) in contract.items())


def _subset(observed: dict, expected: dict) -> bool:
    return all(observed.get(key) == value for key, value in expected.items())


def evaluate(obs: dict) -> dict:
    """Pure: observation -> result. Missing keys fail closed."""
    failures: list[str] = []

    def check(condition: bool, code: str) -> bool:
        if not condition:
            failures.append(code)
        return condition

    host = obs.get("host", {})
    check(host == {"hostname": DEV_INSTANCE, "fqdn": DEV_HOSTNAME, "machineId": DEV_MACHINE_ID,
                   "instanceName": DEV_INSTANCE, "instanceId": DEV_INSTANCE_ID,
                   "bootId": host.get("bootId")}
          and re.fullmatch(r"[0-9a-f-]{36}", str(host.get("bootId"))) is not None, "HOST_MISMATCH")

    units = obs.get("units", {})
    service = units.get(SERVICE, {})
    process = obs.get("process", {})
    release = obs.get("release", {})
    release_ok = all((
        check(release.get("target") == f"releases/{RELEASE_SHA}" and release.get("linkOwner") == [0, 0],
              "RELEASE_SELECTOR_CHANGED"),
        check(release.get("manifestSha256") == MANIFEST_SHA, "RELEASE_MANIFEST_CHANGED"),
        check(release.get("payloadMismatches") == [] and release.get("payloadCount", 0) > 0,
              "RELEASE_PAYLOAD_CHANGED"),
        check(process.get("cwd") == str(ROOT / "releases" / RELEASE_SHA)
              and process.get("cmdline") == BROKER_CMDLINE, "PROCESS_NOT_ON_SELECTED_RELEASE"),
    ))
    files = obs.get("files", {})
    config_ok = all((
        check(_matches(files, UNIT_FILES), "UNIT_FILE_CHANGED"),
        check(_matches(files, CONFIG_FILES), "BROKER_CONFIG_CHANGED"),
        check(obs.get("directories") == {path: {"present": True, "uid": u, "gid": g, "mode": m}
                                         for path, (u, g, m) in DIRECTORIES.items()},
              "DIRECTORY_CUSTODY_CHANGED"),
    ))
    state_ok = check(_matches(files, STATE_FILES), "BROKER_STATE_CHANGED")

    account = obs.get("accounts", {})
    identity_ok = all((
        check(account.get("broker") == {"uid": 999, "gid": 987, "home": "/nonexistent",
                                        "shell": "/usr/sbin/nologin", "groups": [987]},
              "BROKER_ACCOUNT_CHANGED"),
        check(account.get("ipc") == {"gid": 988, "members": ["lilith-memory-relay"]},
              "IPC_GROUP_CHANGED"),
        check(process.get("status", {}).get("uid") == [999] * 4
              and process.get("status", {}).get("gid") == [987] * 4
              and process.get("status", {}).get("groups") == [987]
              and process.get("status", {}).get("ppid") == 1, "BROKER_PROCESS_IDENTITY_CHANGED"),
        check(process.get("status", {}).get("noNewPrivs") == "1"
              and all(value == "0000000000000000" for value in
                      process.get("status", {}).get("capabilities", {"x": None}).values()),
              "BROKER_PROCESS_PRIVILEGE_CHANGED"),
        check(_subset(service, SANDBOX_EXPECTED), "BROKER_SANDBOX_CHANGED"),
    ))
    runtime_dir = obs.get("runtimeDirectory", {})
    owner_sock = obs.get("ownerSocket", {})
    socket_ok = all((
        check(_subset(units.get(SOCKET, {}), SOCKET_EXPECTED), "SOCKET_UNIT_CHANGED"),
        check(runtime_dir == {"present": True, "uid": 0, "gid": 988, "mode": 0o710},
              "RUNTIME_DIRECTORY_CHANGED"),
        check(owner_sock == {"present": True, "type": "socket", "uid": 999, "gid": 988,
                             "mode": 0o660, "listening": True}, "OWNER_SOCKET_CHANGED"),
    ))

    stage3 = obs.get("stage3", {})
    stage3_ok = all((
        check(stage3.get("vault") == {"present": True, "uid": 0, "gid": 0, "mode": 0o700}
              and stage3.get("journal") == STAGE3_JOURNAL
              and stage3.get("phases") == ["INTENT"], "STAGE3_JOURNAL_CHANGED"),
        check(stage3.get("present") == STAGE3_PRESENT, "STAGE3_ARTIFACT_CHANGED"),
        check(stage3.get("absent") == {path: True for path in STAGE3_ABSENT},
              "STAGE3_ARM_GUARD_OR_CONSUMPTION_PRESENT"),
        check(_subset(units.get(CONTROLLER, {}), CONTROLLER_EXPECTED), "STAGE3_CONTROLLER_CHANGED"),
    ))

    deployer = obs.get("deployer", {})
    deployer_ok = check(deployer.get("sudoers") == {"present": True, "exactText": True,
                                                    "uid": 0, "gid": 0, "mode": 0o440}
                        and deployer.get("helperSha256") == DEPLOY_HELPER_SHA,
                        "DEPLOYER_POLICY_CHANGED")

    custody = obs.get("custodyPaths", {})
    custody_states = {path: classify_custody_path(custody.get(path, {"present": True}))
                      for path in CUSTODY_PATHS}
    check(all(state == "NOT_YET_PRESENT" for state in custody_states.values()),
          "CUSTODY_PATH_PRESENT_BEFORE_B1B3D")

    libraries = obs.get("libraries", {})
    library_list = sorted(
        ({"path": path, **values} for path, values in libraries.items()), key=lambda x: x["path"])
    check(bool(library_list) and all(not item["deleted"] and item.get("diskInode") == item["inode"]
                                     and re.fullmatch(r"[0-9a-f]{64}", str(item.get("sha256")))
                                     for item in library_list), "RUNTIME_SUBSTRATE_STALE_OR_UNREADABLE")

    invocation = service.get("InvocationID", "")
    pid = process.get("pid")
    incarnation_ok = all((
        check(_subset(service, SERVICE_EXPECTED), "BROKER_SERVICE_STATE_UNEXPECTED"),
        check(re.fullmatch(r"[0-9a-f]{32}", invocation) is not None, "INVOCATION_ID_INVALID"),
        check(isinstance(pid, int) and pid > 1 and str(pid) == service.get("MainPID")
              and obs.get("brokerProcesses") == [pid], "BROKER_PROCESS_AMBIGUOUS"),
    ))
    process_continuity = (invocation == ACCEPTED_SERVICE_INVOCATION and pid == ACCEPTED_BROKER_PID
                          and process.get("startTicks") == ACCEPTED_BROKER_START_TICKS
                          and host.get("bootId") == ACCEPTED_BROKER_BOOT_ID)

    candidate = {
        "schema": SCHEMA,
        "runtimeIncarnation": invocation,
        "pid": pid,
        "bootId": host.get("bootId"),
        "startTicks": process.get("startTicks"),
        "startTime": process.get("startTime"),
        "execMainStartTimestamp": service.get("ExecMainStartTimestamp"),
        "nRestarts": service.get("NRestarts"),
        "releaseSha": RELEASE_SHA,
        "manifestSha256": release.get("manifestSha256"),
        "sharedLibraries": library_list,
        "sharedLibrariesSha256": canonical_sha256(library_list),
    }
    passed = not failures
    return {
        "schema": SCHEMA,
        "operation": "READ_ONLY_OBSERVATION",
        "CURRENT_RUNTIME_BASELINE": "PASS" if passed else "FAIL",
        "failures": failures,
        "releaseEquivalent": release_ok,
        "configEquivalent": config_ok,
        "stateEquivalent": state_ok,
        "identityBoundaryEquivalent": identity_ok,
        "socketBoundaryEquivalent": socket_ok,
        "stageIIIUntouched": stage3_ok,
        "deployerPolicyTextEquivalent": deployer_ok,
        "incarnationHealthy": incarnation_ok,
        "processContinuity": process_continuity,
        "runtimeBehavioralEquivalence": "NOT_PROVEN_BY_OBSERVATION",
        "stageIIAcceptance": "HISTORICAL_RECORD_UNCHANGED_NOT_EXTENDED_TO_THIS_INCARNATION",
        "ownerAcceptance": "PENDING_SEPARATE_EXPLICIT_OWNER_DECISION",
        "runtimeIncarnation": invocation,
        "bootId": host.get("bootId"),
        "startTime": process.get("startTime"),
        "baselineCandidate": candidate,
        "baselineCandidateSha256": canonical_sha256(candidate) if passed else None,
        "custodyPaths": custody_states,
        "informational": {
            "deployerBoundary": "POLICY_TEXT_ONLY_NOT_A_DENIAL_PROOF",
            "sudoAsBrokerDenial": "NOT_TESTED_DR5_OPEN",
            "dr3Ubuntu": obs.get("ubuntu"),
            "needrestart": obs.get("needrestart"),
        },
    }


# ------------------------------------------------------------------ collection

def _read_regular(path: Path) -> tuple[bytes, os.stat_result] | None:
    try:
        before = path.lstat()
    except FileNotFoundError:
        return None
    require(stat.S_ISREG(before.st_mode) and before.st_size <= MAX_FILE, "EXPECTED_REGULAR_FILE:" + str(path))
    fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_CLOEXEC", 0))
    try:
        opened = os.fstat(fd)
        require((opened.st_dev, opened.st_ino) == (before.st_dev, before.st_ino), "FILE_REPLACED:" + str(path))
        with os.fdopen(fd, "rb", closefd=False) as stream:
            data = stream.read(MAX_FILE + 1)
    finally:
        os.close(fd)
    require(len(data) == opened.st_size, "FILE_SIZE_CHANGED:" + str(path))
    return data, opened


def _file(path: str | Path) -> dict:
    found = _read_regular(Path(path))
    if found is None:
        return {"present": False}
    data, meta = found
    return {"present": True, "sha256": hashlib.sha256(data).hexdigest(),
            "uid": meta.st_uid, "gid": meta.st_gid, "mode": stat.S_IMODE(meta.st_mode)}


def _meta(path: str | Path) -> dict:
    try:
        meta = Path(path).lstat()
    except FileNotFoundError:
        return {"present": False}
    return {"present": True, "uid": meta.st_uid, "gid": meta.st_gid, "mode": stat.S_IMODE(meta.st_mode)}


def _unit(name: str, properties: tuple[str, ...]) -> dict[str, str]:
    argv = readonly_argv([READ_ONLY_SYSTEMCTL, "show", name, "--property=" + ",".join(properties), "--no-pager"])
    return parse_show(subprocess.run(argv, check=True, text=True, capture_output=True, timeout=15).stdout)


def _metadata(key: str) -> str:
    request = Request("http://169.254.169.254/computeMetadata/v1/" + key, headers={"Metadata-Flavor": "Google"})
    with build_opener(ProxyHandler({})).open(request, timeout=5) as response:
        require(response.headers.get("Metadata-Flavor") == "Google", "UNTRUSTED_HOST_METADATA")
        return response.read(256).decode("ascii", "strict").strip()


def _host() -> dict:
    # Identify the DEV host before reading anything else (DR-1 process deviation).
    require(socket.gethostname() == DEV_INSTANCE, "WRONG_HOST_REFUSED")
    return {
        "hostname": socket.gethostname(), "fqdn": socket.getfqdn(),
        "machineId": Path("/etc/machine-id").read_text(encoding="ascii").strip(),
        "instanceName": _metadata("instance/name"), "instanceId": _metadata("instance/id"),
        "bootId": Path("/proc/sys/kernel/random/boot_id").read_text(encoding="ascii").strip(),
    }


def _release() -> dict:
    current = ROOT / "current"
    link = current.lstat()
    require(stat.S_ISLNK(link.st_mode), "RELEASE_SELECTOR_TYPE")
    target = os.readlink(current)
    release_dir = ROOT / target
    manifest = _read_regular(release_dir / "release-manifest.json")
    require(manifest is not None, "RELEASE_MANIFEST_MISSING")
    items = json.loads(manifest[0])["files"]
    mismatches = []
    for item in items:
        name = item["path"]
        require(isinstance(name, str) and not name.startswith("/")
                and all(part not in ("", ".", "..") for part in name.split("/")), "RELEASE_MANIFEST_PATH")
        observed = _file(release_dir / name)
        if observed.get("sha256") != item["sha256"]:
            mismatches.append(name)
    return {"target": target, "linkOwner": [link.st_uid, link.st_gid],
            "manifestSha256": hashlib.sha256(manifest[0]).hexdigest(),
            "payloadCount": len(items), "payloadMismatches": sorted(mismatches)}


def _broker_processes() -> list[int]:
    found = []
    for entry in Path("/proc").iterdir():
        if not entry.name.isdigit() or int(entry.name) == os.getpid():
            continue
        try:
            if entry.stat().st_uid == 999 or b"lilith_memory_broker.server" in (entry / "cmdline").read_bytes():
                found.append(int(entry.name))
        except (FileNotFoundError, ProcessLookupError):
            continue
    return sorted(found)


def _process(pid: int) -> dict:
    proc = Path("/proc") / str(pid)
    ticks = parse_start_ticks((proc / "stat").read_text(encoding="ascii"))
    boot_time = next(int(line.split()[1]) for line in
                     Path("/proc/stat").read_text(encoding="ascii").splitlines() if line.startswith("btime "))
    return {
        "pid": pid,
        "status": parse_status((proc / "status").read_text(encoding="ascii")),
        "cmdline": (proc / "cmdline").read_bytes().replace(b"\x00", b" ").decode("utf-8").strip(),
        "exe": os.readlink(proc / "exe"), "cwd": os.readlink(proc / "cwd"),
        "startTicks": ticks,
        "startTime": start_time_utc(ticks, boot_time, os.sysconf("SC_CLK_TCK")),
    }


def _libraries(pid: int) -> dict:
    mapped = parse_maps((Path("/proc") / str(pid) / "maps").read_text(encoding="utf-8"))
    for path, entry in mapped.items():
        disk = _file(path) if not entry["deleted"] else {"present": False}
        entry["sha256"] = disk.get("sha256")
        try:
            entry["diskInode"] = Path(path).lstat().st_ino
        except FileNotFoundError:
            entry["diskInode"] = None
    return mapped


def _owner_socket() -> dict:
    path = RUNTIME / "owner.sock"
    try:
        meta = path.lstat()
    except FileNotFoundError:
        return {"present": False}
    # /proc/net/unix exposes the listening flag; no connection is made.
    listening = any(len(parts) >= 8 and parts[7] == str(path) and parts[3] == "00010000" and parts[4] == "0001"
                    for line in Path("/proc/net/unix").read_text(encoding="ascii").splitlines()[1:]
                    if (parts := line.split()))
    return {"present": True, "type": "socket" if stat.S_ISSOCK(meta.st_mode) else "other",
            "uid": meta.st_uid, "gid": meta.st_gid, "mode": stat.S_IMODE(meta.st_mode),
            "listening": listening}


def _stage3() -> dict:
    vault = _meta(STAGE3_VAULT)
    journal, phases = {}, []
    if vault.get("present"):
        for name in sorted(item.name for item in STAGE3_VAULT.iterdir()):
            journal[name] = _file(STAGE3_VAULT / name).get("sha256")
            if re.fullmatch(r"\d{3}-[A-Z_]+\.json", name):
                phases.append(name.split("-", 1)[1][:-5])
    return {"vault": vault, "journal": journal, "phases": phases,
            "present": {path: _file(path).get("sha256") for path in STAGE3_PRESENT},
            "absent": {path: not os.path.lexists(path) for path in STAGE3_ABSENT}}


def _accounts() -> dict:
    user = pwd.getpwnam("lilith-memory-broker")
    ipc = grp.getgrnam("lilith-memory-ipc")
    return {"broker": {"uid": user.pw_uid, "gid": user.pw_gid, "home": user.pw_dir, "shell": user.pw_shell,
                       "groups": sorted(set(os.getgrouplist(user.pw_name, user.pw_gid)))},
            "ipc": {"gid": ipc.gr_gid, "members": sorted(ipc.gr_mem)}}


def _ubuntu() -> dict:
    """DR-3 facts only. Reports; never asserts exploitability; never mutates."""
    try:
        user = pwd.getpwnam("ubuntu")
    except KeyError:
        return {"present": False}
    names = sorted(g.gr_name for g in grp.getgrall()
                   if g.gr_gid in os.getgrouplist("ubuntu", user.pw_gid))
    shadow = [line.split(":", 2)[1] for line in Path("/etc/shadow").read_text(encoding="utf-8").splitlines()
              if line.startswith("ubuntu:")]
    keys = _meta(Path(user.pw_dir) / ".ssh/authorized_keys")
    keys_size = (Path(user.pw_dir) / ".ssh/authorized_keys").lstat().st_size if keys.get("present") else None
    return {"present": True, "groups": names,
            "rootEquivalentGroups": sorted(set(names) & {"sudo", "lxd", "admin", "wheel"}),
            "passwordLocked": bool(shadow) and shadow[0].startswith(("!", "*")),
            "authorizedKeysBytes": keys_size}


def _needrestart() -> dict:
    main_conf, conf_dir = NEEDRESTART_CONFIG
    paths = [main_conf] + (sorted(conf_dir.glob("*.conf")) if conf_dir.is_dir() else [])
    texts = [found[0].decode("utf-8") for path in paths if (found := _read_regular(path)) is not None]
    return {"installed": main_conf.exists(), **parse_needrestart(texts)}


def _deployer() -> dict:
    sudoers = _read_regular(DEPLOYER_SUDOERS)
    helper = _file(DEPLOY_HELPER)
    if sudoers is None:
        return {"sudoers": {"present": False}, "helperSha256": helper.get("sha256")}
    data, meta = sudoers
    return {"sudoers": {"present": True, "exactText": data == DEPLOYER_SUDOERS_TEXT.encode(),
                        "uid": meta.st_uid, "gid": meta.st_gid, "mode": stat.S_IMODE(meta.st_mode)},
            "helperSha256": helper.get("sha256")}


SERVICE_PROPERTIES = tuple(SERVICE_EXPECTED) + tuple(SANDBOX_EXPECTED) + (
    "MainPID", "InvocationID", "ExecMainStartTimestamp")
SOCKET_PROPERTIES = tuple(SOCKET_EXPECTED) + ("InvocationID",)
CONTROLLER_PROPERTIES = tuple(CONTROLLER_EXPECTED)


def collect() -> dict:
    """Read only. Host identity is checked before any other read."""
    host = _host()
    units = {SERVICE: _unit(SERVICE, SERVICE_PROPERTIES), SOCKET: _unit(SOCKET, SOCKET_PROPERTIES),
             CONTROLLER: _unit(CONTROLLER, CONTROLLER_PROPERTIES)}
    pid = int(units[SERVICE].get("MainPID", "0"))
    return {
        "host": host,
        "units": units,
        "release": _release(),
        "files": {path: _file(path) for path in {**UNIT_FILES, **CONFIG_FILES, **STATE_FILES}},
        "directories": {path: _meta(path) for path in DIRECTORIES},
        "accounts": _accounts(),
        "process": _process(pid) if pid > 1 else {},
        "libraries": _libraries(pid) if pid > 1 else {},
        "brokerProcesses": _broker_processes(),
        "runtimeDirectory": _meta(RUNTIME),
        "ownerSocket": _owner_socket(),
        "stage3": _stage3(),
        "deployer": _deployer(),
        "custodyPaths": {path: _meta(path) for path in CUSTODY_PATHS},
        "ubuntu": _ubuntu(),
        "needrestart": _needrestart(),
    }


def main(argv: list[str]) -> int:
    require(argv == ["baseline"], "FIXED_BASELINE_COMMAND_ONLY")
    require(os.name == "posix" and os.geteuid() == 0 and pwd is not None, "ROOT_LINUX_REQUIRED")
    result = evaluate(collect())
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))
    return 0 if result["CURRENT_RUNTIME_BASELINE"] == "PASS" else 2


if __name__ == "__main__":
    try:
        raise SystemExit(main(sys.argv[1:]))
    except (BaselineError, OSError, KeyError, ValueError, subprocess.SubprocessError) as exc:
        print(f"CURRENT_INCARNATION_BASELINE_FAILED:{exc}", file=sys.stderr)
        raise SystemExit(1) from exc
