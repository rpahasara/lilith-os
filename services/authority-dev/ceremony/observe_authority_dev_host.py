#!/usr/bin/env python3
"""Fixed read-only host observer for B1b-3e PR-1A PRE/POST evidence (DEV).

Record: docs/architecture/slice-15b2b-b1b3e-pr1a-build-attestation.md §12.
It replaces the scratch stat probe used by the first read-only preflight
(docs/architecture/slice-15b2b-b1b3e-pr1a-readonly-preflight.md, D-8) with
reviewed source. Stream it like the installer:

    echo <gzip+base64> | base64 -d | gunzip | sudo /usr/bin/python3 -I -B - observe

It takes no path argument and observes only the fixed PR-1 path set below.
It uses `lstat`, directory listings, `O_NOATIME` reads of release files and
of the CURRENT *ciphertext*, and `systemctl show`. It never:

- opens `/var/lib/systemd/credential.secret` (stat only; hard refusal);
- decrypts anything, or runs `systemd-creds`, a keygen, or the signer;
- starts, stops, reloads, or enables a unit;
- creates, writes, chmods, or removes any path;
- contacts the network.

It records facts and judges nothing. Exact authority state stays owned by
`install_authority_dev.py status` / `upgrade-status`. Broker continuity is
owned by `verify_broker_dev_current_incarnation.py preservation`, and
routine-deployer denial by DR-5. `stableSha256` covers every fact except
the two volatile ones (`host.utcNow`, `host.uptimeSeconds`), so an unchanged
host reproduces it. `sectionSha256` lets PRE and POST be compared section by
section across an intended change.

    observation != judgment;  observation != authority
"""

from __future__ import annotations

import grp
import hashlib
import json
import os
import pwd
import stat
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

SCHEMA = "LILITH_AUTHORITY_DEV_HOST_OBSERVATION"
DEV_HOSTNAME = "lilith-dev-01"
DEV_MACHINE_ID = "ae929170e6fa4c8ab9cc7b9547238d9d"
FIXED_ENV = {"PATH": "/usr/sbin:/usr/bin:/sbin:/bin", "LANG": "C"}
NEVER_OPEN = frozenset({"/var/lib/systemd/credential.secret"})
VOLATILE = (("host", "utcNow"), ("host", "uptimeSeconds"))

OPT = "/opt/lilith-authority-dev"
RELEASES = OPT + "/releases"
MANIFEST = "release-manifest.json"
CREDSTORE = "/etc/credstore.encrypted"
CURRENT = CREDSTORE + "/lilith-authority-dev.owner-actor.cred"
HOST_KEY = "/var/lib/systemd/credential.secret"
UNIT_DIR = "/etc/systemd/system"
HOST_FILES = (
    UNIT_DIR + "/lilith-authority-dev.service", UNIT_DIR + "/lilith-authority-dev.socket",
    "/etc/tmpfiles.d/lilith-authority-dev.conf",
    UNIT_DIR + "/lilith-recovery-witness.service", UNIT_DIR + "/lilith-recovery-witness-owner.socket",
    UNIT_DIR + "/lilith-recovery-witness-signer.socket", "/etc/tmpfiles.d/lilith-recovery-witness.conf",
    "/usr/local/sbin/lilith-authority-keygen-dev", "/usr/local/sbin/lilith-authority-ledger-dev",
    "/usr/local/sbin/lilith-authority-hold-dev", "/usr/local/sbin/lilith-authority-verify-dev",
    "/usr/local/sbin/lilith-authority-recovery-dev", "/usr/local/sbin/lilith-recovery-witness-owner-dev",
    "/usr/local/sbin/lilith-activation-verify",
    "/etc/needrestart/conf.d/lilith-authority-sensitive.conf",
)
UNITS = ("lilith-authority-dev.service", "lilith-authority-dev.socket", "lilith-recovery-witness.service",
         "lilith-recovery-witness-owner.socket", "lilith-recovery-witness-signer.socket",
         "lilith-memory-broker.service")
UNIT_PROPERTIES = ("Id,LoadState,ActiveState,SubState,UnitFileState,NeedDaemonReload,NRestarts,MainPID,InvocationID,"
                   "ExecMainStartTimestamp,InactiveExitTimestamp,ActiveEnterTimestamp,FragmentPath,DropInPaths,"
                   "WorkingDirectory,User,Group,StateDirectory,Listen,InaccessiblePaths,ReadOnlyPaths")
ACCOUNTS = ("lilith-authority-dev", "lilith-recovery-witness")
# Every PR-1 object (preflight §27 M-A7..M-A10 and PR-1B) plus the superseded names.
PR1_OBJECTS = (
    "/etc/lilith-authority-custody", "/etc/lilith-authority-custody/prepared", "/etc/lilith-authority-custody/retired",
    "/var/lib/lilith-authority-custody", "/var/lib/lilith-authority-custody/holds",
    "/etc/lilith-recovery-witness", "/etc/lilith-recovery-witness/credentials",
    "/etc/lilith-recovery-witness/credentials/lilith-recovery-witness.witness.cred",
    "/etc/credstore.encrypted/lilith-recovery-witness.witness.cred",
    "/etc/lilith-authority-dev", "/etc/lilith-authority-dev/trust", "/etc/lilith-authority-dev/registry",
    "/etc/lilith-authority-dev/owner", "/etc/lilith-authority-dev/hold", "/etc/lilith-authority-dev/INSTALLED",
    "/var/lib/lilith-authority-dev", "/var/lib/lilith-authority-dev/authority_ledger.db",
    "/var/lib/lilith-recovery-witness", "/run/lilith-authority-dev", "/run/lilith-recovery-witness",
    "/run/credentials/lilith-authority-dev.service", "/run/credentials/lilith-recovery-witness.service",
)
LISTED_DIRS = (CREDSTORE, "/etc/credstore", "/run/credentials", "/var/lib/lilith-authority-dev",
               "/etc/lilith-authority-custody", "/etc/lilith-authority-custody/prepared",
               "/etc/lilith-authority-custody/retired", "/var/lib/lilith-authority-custody/holds",
               "/etc/lilith-recovery-witness/credentials", "/var/lib/lilith-recovery-witness",
               "/etc/lilith-os-dev/activation", OPT, RELEASES)
# Future custody paths resolve to their nearest existing parent (no creation).
FILESYSTEM_PATHS = (CURRENT, CREDSTORE, HOST_KEY, "/etc", "/var/lib", "/opt", OPT, "/usr/local/sbin", UNIT_DIR,
                    "/etc/lilith-authority-custody", "/etc/lilith-recovery-witness/credentials",
                    "/var/lib/lilith-authority-custody/holds", "/var/lib/lilith-authority-dev",
                    "/var/lib/lilith-recovery-witness")
NAMESPACE_ROOTS = ("/etc", "/opt", "/var/lib", "/usr/local/sbin", "/run", "/etc/tmpfiles.d", UNIT_DIR)
NAMESPACE_MARKERS = ("lilith", "recovery-witness")


class ObserveError(RuntimeError):
    def __init__(self, reason: str):
        self.reason = reason
        super().__init__(reason)


@dataclass
class Host:
    """Host access. Tests replace the root and the OS lookups."""

    root: Path = Path("/")
    run: Callable[..., subprocess.CompletedProcess] = field(default=None)  # type: ignore[assignment]
    euid: Callable[[], int] = field(default=None)  # type: ignore[assignment]
    hostname: Callable[[], str] = field(default=None)  # type: ignore[assignment]
    user: Callable[[str], Any] = field(default=None)  # type: ignore[assignment]
    group: Callable[[str], Any] = field(default=None)  # type: ignore[assignment]
    grouplist: Callable[[str, int], list[int]] = field(default=None)  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.run is None:
            self.run = lambda argv: subprocess.run(argv, env=FIXED_ENV, capture_output=True, text=True,
                                                   timeout=30, check=False)
        if self.euid is None:
            self.euid = os.geteuid
        if self.hostname is None:
            self.hostname = lambda: os.uname().nodename
        if self.user is None:
            self.user = _lookup(pwd.getpwnam)
        if self.group is None:
            self.group = _lookup(grp.getgrnam)
        if self.grouplist is None:
            self.grouplist = os.getgrouplist

    def path(self, absolute: str) -> Path:
        return self.root / absolute.lstrip("/")


def _lookup(function: Callable[[str], Any]) -> Callable[[str], Any]:
    def lookup(name: str) -> Any:
        try:
            return function(name)
        except KeyError:
            return None
    return lookup


def lstat_facts(host: Host, absolute: str) -> dict | None:
    try:
        meta = os.lstat(host.path(absolute))
    except FileNotFoundError:
        return None
    mode = meta.st_mode
    kind = ("symlink" if stat.S_ISLNK(mode) else "dir" if stat.S_ISDIR(mode) else "file" if stat.S_ISREG(mode)
            else "socket" if stat.S_ISSOCK(mode) else "other")
    facts = {"kind": kind, "uid": meta.st_uid, "gid": meta.st_gid, "mode": format(stat.S_IMODE(mode), "04o"),
             "device": meta.st_dev, "inode": meta.st_ino, "size": meta.st_size, "nlink": meta.st_nlink,
             "mtimeNs": meta.st_mtime_ns, "ctimeNs": meta.st_ctime_ns}
    if kind == "symlink":
        facts["target"] = os.readlink(host.path(absolute))
    return facts


def file_sha256(host: Host, absolute: str) -> str | None:
    """SHA-256 of a regular file read with O_NOFOLLOW|O_NOATIME. Refuses the host key."""
    if absolute in NEVER_OPEN or any(absolute.startswith(p + "/") for p in NEVER_OPEN):
        raise ObserveError("NEVER_OPEN:" + absolute)
    path = host.path(absolute)
    try:
        meta = os.lstat(path)
    except FileNotFoundError:
        return None
    if not stat.S_ISREG(meta.st_mode):
        return None
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | getattr(os, "O_NOATIME", 0))
    digest = hashlib.sha256()
    try:
        while True:
            chunk = os.read(fd, 1 << 20)
            if not chunk:
                return digest.hexdigest()
            digest.update(chunk)
    finally:
        os.close(fd)


def read_bytes(host: Host, absolute: str, *, follow: bool = False, limit: int = 1 << 20) -> bytes | None:
    if absolute in NEVER_OPEN:
        raise ObserveError("NEVER_OPEN:" + absolute)
    try:
        fd = os.open(host.path(absolute), os.O_RDONLY | (0 if follow else os.O_NOFOLLOW) | getattr(os, "O_NOATIME", 0))
    except OSError:
        return None
    chunks, size = [], 0
    try:
        while size <= limit:
            chunk = os.read(fd, 1 << 16)
            if not chunk:
                break
            chunks.append(chunk)
            size += len(chunk)
    finally:
        os.close(fd)
    return b"".join(chunks)[:limit]


def read_text(host: Host, absolute: str, *, follow: bool = False) -> str | None:
    data = read_bytes(host, absolute, follow=follow, limit=1 << 16)
    return None if data is None else data.decode("utf-8", "replace")


def listing(host: Host, absolute: str) -> dict | None:
    facts = lstat_facts(host, absolute)
    if facts is None or facts["kind"] != "dir":
        return None
    return {name: lstat_facts(host, f"{absolute.rstrip('/')}/{name}") for name in sorted(os.listdir(host.path(absolute)))}


def observe_host(host: Host) -> dict:
    os_release = read_text(host, "/etc/os-release", follow=True) or ""
    values = dict(line.split("=", 1) for line in os_release.splitlines() if "=" in line)
    uptime = (read_text(host, "/proc/uptime") or "").split()
    return {"hostname": host.hostname().split(".", 1)[0],
            "machineId": (read_text(host, "/etc/machine-id") or "").strip(),
            "bootId": (read_text(host, "/proc/sys/kernel/random/boot_id") or "").strip(),
            "kernel": (read_text(host, "/proc/sys/kernel/osrelease") or "").strip(),
            "osPrettyName": values.get("PRETTY_NAME", "").strip('"'),
            "swaps": (read_text(host, "/proc/swaps") or "").strip().splitlines()[1:],
            "rebootRequired": lstat_facts(host, "/var/run/reboot-required") is not None,
            "localtime": lstat_facts(host, "/etc/localtime"),
            "uptimeSeconds": uptime[0] if uptime else None,
            "utcNow": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}


def observe_release_tree(host: Host, name: str) -> dict:
    """One release directory against its own manifest (bytes, owners, modes)."""
    top = f"{RELEASES}/{name}"
    report: dict[str, Any] = {"root": lstat_facts(host, top)}
    if report["root"] is None or report["root"]["kind"] != "dir":
        return report
    files: dict[str, dict] = {}
    unexpected: list[str] = []
    venv = hashlib.sha256()
    venv_entries = 0
    for directory, subdirs, names in os.walk(host.path(top), followlinks=False):
        subdirs.sort()
        for entry in sorted(names) + [d for d in subdirs if os.path.islink(os.path.join(directory, d))]:
            relative = Path(directory, entry).relative_to(host.path(top)).as_posix()
            absolute = f"{top}/{relative}"
            facts = lstat_facts(host, absolute)
            if relative.startswith("venv/"):
                venv_entries += 1
                content = (file_sha256(host, absolute) if facts["kind"] == "file"
                           else facts.get("target", "") if facts["kind"] == "symlink" else "")
                venv.update(f"{relative}\0{facts['kind']}\0{facts['mode']}\0{facts['uid']}\0{facts['gid']}\0"
                            f"{content}\n".encode())
                continue
            if facts["kind"] != "file":
                unexpected.append(f"{facts['kind']}:{relative}")
                continue
            files[relative] = {"sha256": file_sha256(host, absolute), "size": facts["size"], "uid": facts["uid"],
                               "gid": facts["gid"], "mode": facts["mode"]}
        for sub in subdirs:
            facts = lstat_facts(host, f"{top}/{Path(directory, sub).relative_to(host.path(top)).as_posix()}")
            if facts["kind"] == "dir" and (facts["mode"] != "0755" or facts["uid"] != report["root"]["uid"]):
                unexpected.append("dirmode:" + Path(directory, sub).relative_to(host.path(top)).as_posix())
    report.update(venvEntries=venv_entries, venvSha256=venv.hexdigest(), unexpected=sorted(unexpected),
                  owners=sorted({f"{v['uid']}:{v['gid']}" for v in files.values()}),
                  modes=sorted({v["mode"] for v in files.values()}),
                  treeSha256=hashlib.sha256("".join(f"{p}\0{v['sha256']}\n" for p, v in sorted(files.items()))
                                            .encode()).hexdigest(),
                  members={p: v["sha256"] for p, v in sorted(files.items())
                           if p.startswith(("assets/", "cli/")) or p == MANIFEST})
    manifest_bytes = read_bytes(host, f"{top}/{MANIFEST}") if MANIFEST in files else None
    if manifest_bytes is None:
        report["manifest"] = "ABSENT"
        return report
    try:
        manifest = json.loads(manifest_bytes)
        expected = {item["path"]: (item["sha256"], item["byteSize"]) for item in manifest["files"]}
    except (ValueError, KeyError, TypeError):
        report["manifest"] = "MALFORMED"
        return report
    report["manifest"] = {
        "sha256": files[MANIFEST]["sha256"],
        "header": {k: v for k, v in manifest.items() if k != "files"},
        "fileCount": len(expected),
        "mismatched": sorted(p for p, (sha, size) in expected.items()
                             if p not in files or (files[p]["sha256"], files[p]["size"]) != (sha, size)),
        "notInManifest": sorted(set(files) - set(expected) - {MANIFEST}),
    }
    return report


def observe_releases(host: Host) -> dict:
    entries = listing(host, RELEASES) or {}
    return {"opt": lstat_facts(host, OPT), "current": lstat_facts(host, OPT + "/current"),
            "releaseEntries": sorted(entries), "trees": {name: observe_release_tree(host, name) for name in entries}}


def observe_units(host: Host) -> dict:
    units = {}
    for unit in UNITS:
        result = host.run(["/usr/bin/systemctl", "show", "--property=" + UNIT_PROPERTIES, "--", unit])
        units[unit] = dict(line.split("=", 1) for line in result.stdout.splitlines() if "=" in line)
    links = []
    unit_dir = host.path(UNIT_DIR)
    if unit_dir.is_dir():
        for directory, subdirs, names in os.walk(unit_dir, followlinks=False):
            if Path(directory) == unit_dir:
                continue
            for name in sorted(names + subdirs):
                if any(marker in name for marker in ("lilith-authority", "recovery-witness")) \
                        or any(marker in Path(directory).name for marker in ("lilith-authority", "recovery-witness")):
                    links.append(Path(directory, name).relative_to(host.root).as_posix())
    return {"show": units, "enablementOrDropInEntries": sorted(links)}


def observe_account(host: Host, name: str) -> dict | None:
    user, group = host.user(name), host.group(name)
    if user is None and group is None:
        return None
    return {"uid": None if user is None else user.pw_uid, "gid": None if user is None else user.pw_gid,
            "home": None if user is None else user.pw_dir, "shell": None if user is None else user.pw_shell,
            "groupGid": None if group is None else group.gr_gid,
            "groupMembers": None if group is None else sorted(group.gr_mem),
            "groups": None if user is None else sorted(set(host.grouplist(name, user.pw_gid))),
            "homeExists": None if user is None else lstat_facts(host, user.pw_dir) is not None}


def _mounts(host: Host) -> list[dict]:
    mounts = []
    for line in (read_text(host, "/proc/self/mountinfo") or "").splitlines():
        if " - " not in line:
            continue
        left, right = line.split(" - ", 1)
        fields, rest = left.split(), right.split()
        mounts.append({"mountPoint": fields[4], "majMin": fields[2], "fstype": rest[0], "source": rest[1]})
    return mounts


def observe_filesystems(host: Host) -> dict:
    mounts = _mounts(host)
    result = {}
    for absolute in FILESYSTEM_PATHS:
        existing = absolute
        while lstat_facts(host, existing) is None and existing != "/":
            existing = str(Path(existing).parent)
        facts = lstat_facts(host, existing)
        best = None
        for mount in mounts:
            point = mount["mountPoint"]
            if point == "/" or existing == point or existing.startswith(point.rstrip("/") + "/"):
                if best is None or len(point) >= len(best["mountPoint"]):
                    best = mount
        result[absolute] = {"nearestExisting": existing, "device": None if facts is None else facts["device"],
                            "mount": best}
    return result


def observe(host: Host) -> dict:
    current = lstat_facts(host, CURRENT)
    if current is not None:
        current["sha256"] = file_sha256(host, CURRENT)
    inventory = {}
    for base in NAMESPACE_ROOTS:
        path = host.path(base)
        if path.is_dir():
            inventory[base] = sorted(n for n in os.listdir(path) if any(m in n for m in NAMESPACE_MARKERS))
    return {
        "host": observe_host(host),
        "releases": observe_releases(host),
        "hostFiles": {p: (None if lstat_facts(host, p) is None else {**lstat_facts(host, p), "sha256": file_sha256(host, p)})
                      for p in HOST_FILES},
        "units": observe_units(host),
        "accounts": {name: observe_account(host, name) for name in ACCOUNTS},
        "currentBlob": current,
        "hostKey": lstat_facts(host, HOST_KEY),  # stat only: never opened
        "listings": {p: listing(host, p) for p in LISTED_DIRS},
        "pr1Objects": {p: lstat_facts(host, p) for p in PR1_OBJECTS},
        "filesystems": observe_filesystems(host),
        "namespaceInventory": inventory,
    }


def _digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
                          .encode("ascii")).hexdigest()


def report(facts: dict) -> dict:
    stable = json.loads(json.dumps(facts))
    for section, key in VOLATILE:
        stable[section].pop(key, None)
    return {"schema": SCHEMA, "schemaVersion": 1, "operation": "READ_ONLY_OBSERVATION", "judgment": "NOT_PERFORMED",
            "facts": facts, "sectionSha256": {name: _digest(value) for name, value in sorted(stable.items())},
            "stableSha256": _digest(stable)}


def require_dev_root(host: Host) -> None:
    if host.euid() != 0:
        raise ObserveError("NOT_ROOT")
    machine_id = (read_text(host, "/etc/machine-id") or "").strip()
    if machine_id != DEV_MACHINE_ID or host.hostname().split(".", 1)[0] != DEV_HOSTNAME:
        raise ObserveError("NOT_DEV_HOST")


def main(argv: list[str], host: Host | None = None) -> int:
    host = host or Host()
    try:
        if argv != ["observe"]:
            raise ObserveError("USAGE")
        require_dev_root(host)
        value = report(observe(host))
    except ObserveError as exc:
        print(f"observe_authority_dev_host: REFUSED {exc.reason}", file=sys.stderr)
        return 2
    sys.stdout.write(json.dumps(value, sort_keys=True, indent=1) + "\n")
    sys.stdout.write(f"PR1A_HOST_OBSERVATION=COMPLETE stableSha256={value['stableSha256']}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
