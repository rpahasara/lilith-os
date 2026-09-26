#!/usr/bin/python3 -IB
"""LILITH 15B2b-B1b-3d L2: owner break-glass installer for the DEV authority signer.

Run only by the owner, as root, on `lilith-dev-01`, through the owner's own
IAP session, from a copy of the reviewed protected-main commit. Never from
GitHub Actions or the routine deployer. Runbook:
docs/architecture/slice-15b2b-b1b3d-l2-custody-preparation.md.

    sudo /usr/bin/python3 -I -B install_authority_dev.py <stage> [...]

Provenance (N-45):

- RELEASE_SHA: the protected-main commit the installed, immutable signer
  release was built from. It is the `<sha>` argument of every stage below,
  and the only commit this installer reads state for.
- CONTROL_SHA: the protected-main commit this installer, the verifiers, and
  the runbook are taken from and streamed. It may be newer than RELEASE_SHA.
  A control-only change never requires rebuilding or reinstalling
  RELEASE_SHA, unless the signer release payload changes. This file is
  never part of that payload (tests pin this).

Each mutating stage performs exactly one logical state transition and then
prints its POST evidence. Every stage refuses on any collision instead of
correcting existing state.

| Stage | Ladder | Mutation |
| --- | --- | --- |
| `status --expect <S>` | POST of S | none (read-only) |
| `preflight` | L0 | none (read-only) |
| `accounts` | L1a | create system user+group `lilith-authority-dev` |
| `release` | L1b.1 | install `/opt/lilith-authority-dev/releases/<RELEASE_SHA>` from a verified archive |
| `select` | L1b.2 | create the `current` selector |
| `units` | L1c.1 | install unit, socket, and tmpfiles files (no reload, no enable) |
| `cli` | L1c.3 | install `/usr/local/sbin/lilith-authority-keygen-dev` |
| `credstore` | L2b.1 | create `/etc/credstore.encrypted` `root:root 0700` if absent; adopt it unchanged if already exactly secure and empty |

`systemctl daemon-reload` (L1c.2), `systemd-creds setup` (L2a), and the
keygen ceremony (L2b.2) are separate owner commands in the runbook; this
installer never runs them. It never creates a key, a credential, the host
credential key, `/etc/lilith-authority-dev`, `/var/lib/lilith-authority-dev`,
`/run/lilith-authority-dev`, or anything for the recovery witness, and it
never starts, enables, or reloads a unit.
"""

from __future__ import annotations

import gzip
import hashlib
import io
import json
import os
import re
import stat
import subprocess
import sys
import tarfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

ROLE = "lilith-authority-dev-synthetic-owner-actor-release-v1"
DEV_HOSTNAME = "lilith-dev-01"
DEV_MACHINE_ID = "ae929170e6fa4c8ab9cc7b9547238d9d"
SERVICE_USER = "lilith-authority-dev"
SERVICE_GROUP = "lilith-authority-dev"
DISTINCT_PRINCIPALS = ("lilith", "lilith-memory-broker", "lilith-memory-relay")
NOLOGIN = "/usr/sbin/nologin"
NO_HOME = "/nonexistent"
FIXED_ENV = {"PATH": "/usr/sbin:/usr/bin:/sbin:/bin", "LANG": "C", "HOME": "/nonexistent"}
SHA40 = re.compile(r"[0-9a-f]{40}\Z")
MAX_FILE = 8 * 1024 * 1024
MAX_ARCHIVE = 20 * 1024 * 1024

OPT = "/opt/lilith-authority-dev"
RELEASES = OPT + "/releases"
CURRENT = OPT + "/current"
UNIT_DIR = "/etc/systemd/system"
SERVICE_UNIT = UNIT_DIR + "/lilith-authority-dev.service"
SOCKET_UNIT = UNIT_DIR + "/lilith-authority-dev.socket"
TMPFILES = "/etc/tmpfiles.d/lilith-authority-dev.conf"
KEYGEN_CLI = "/usr/local/sbin/lilith-authority-keygen-dev"
CREDSTORE = "/etc/credstore.encrypted"
CREDENTIAL = CREDSTORE + "/lilith-authority-dev.owner-actor.cred"
HOST_KEY = "/var/lib/systemd/credential.secret"
NEEDRESTART = "/etc/needrestart/conf.d/lilith-authority-sensitive.conf"
NEEDRESTART_SHA256 = "503279315ccc884d8a68505c86b51dfd09387b393c9becba684b1fa1c28068d2"
# Deferred to later ladder steps; they must stay absent through L2b.
DEFERRED_PATHS = (
    "/etc/lilith-authority-dev", "/var/lib/lilith-authority-dev", "/run/lilith-authority-dev",
    "/run/credentials/lilith-authority-dev.service", "/var/lib/lilith-recovery-witness",
    "/run/lilith-recovery-witness", CREDSTORE + "/lilith-recovery-witness.witness.cred",
)

# Archive layout. Pinned against services/authority-dev/release_file_set.py by tests.
RUNTIME_PATHS = frozenset({
    *(f"lilith_authority_dev/{name}" for name in (
        "__init__.py", "profile.py", "credential.py", "evidence_minter.py", "protocol.py", "core.py", "server.py")),
    "lilith_memory/__init__.py", "lilith_memory/canonical_contracts.py", "lilith_memory/owner_proof.py",
    "lilith_owner_memory/__init__.py", "lilith_owner_memory/contracts.py", "lilith_owner_memory/authority_contracts.py",
    "assets/lilith-authority-dev.service", "assets/lilith-authority-dev.socket", "assets/lilith-authority-dev.tmpfiles.conf",
})
CLI_PATH = "cli/lilith-authority-keygen-dev"
# Same pinned offline wheel set and lock as the accepted broker release.
WHEEL_HASHES = {
    "cffi-2.1.1-cp312-cp312-manylinux2014_x86_64.manylinux_2_17_x86_64.whl": "c1453022f490d2459a11819d83ad1d586e9ff65a12ac3e705ffebd46d3685dcf",
    "cryptography-50.0.1-cp311-abi3-manylinux2014_x86_64.manylinux_2_17_x86_64.whl": "ff838d62ec1bfce4f9ba7fa16f4a7b554cd8d0c299e6be37502161a660c84eef",
    "fido2-2.2.1-py3-none-any.whl": "ed397da981b9ab133da6ead7309e41f924b566b749956129efe286fae097749f",
    "pycparser-3.0-py3-none-any.whl": "b727414169a36b7d524c1c3e31839a521725078d7b2ff038656844266160a992",
    "rfc8785-0.1.4-py3-none-any.whl": "520d690b448ecf0703691c76e1a34a24ddcd4fc5bc41d589cb7c58ec651bcd48",
}
LOCK = "".join(
    f"{package}=={version} --hash=sha256:{WHEEL_HASHES[wheel]}\n"
    for package, version, wheel in (
        ("cffi", "2.1.1", "cffi-2.1.1-cp312-cp312-manylinux2014_x86_64.manylinux_2_17_x86_64.whl"),
        ("cryptography", "50.0.1", "cryptography-50.0.1-cp311-abi3-manylinux2014_x86_64.manylinux_2_17_x86_64.whl"),
        ("fido2", "2.2.1", "fido2-2.2.1-py3-none-any.whl"),
        ("pycparser", "3.0", "pycparser-3.0-py3-none-any.whl"),
        ("rfc8785", "0.1.4", "rfc8785-0.1.4-py3-none-any.whl"),
    )
).encode()
EXPECTED_PATHS = RUNTIME_PATHS | {CLI_PATH, "requirements.lock"} | {"wheels/" + name for name in WHEEL_HASHES}
MANIFEST = "release-manifest.json"
# Installed host files come only from these archive members.
UNIT_TARGETS = {
    "assets/lilith-authority-dev.service": SERVICE_UNIT,
    "assets/lilith-authority-dev.socket": SOCKET_UNIT,
    "assets/lilith-authority-dev.tmpfiles.conf": TMPFILES,
}
# Nothing that looks like custody material may be a release member.
FORBIDDEN_MEMBER = re.compile(r"(\.cred|\.pem|\.key|\.der|credstore|secret)", re.IGNORECASE)
FORBIDDEN_MARKERS = (b"-----" + b"BEGIN", b"PRIVATE" + b" KEY-----", b"OPENSSH" + b" PRIVATE", b"TEST_ONLY ",
                     b"from_private_bytes", b"lilith_authority_signer", b"synthetic_authority")


class InstallError(RuntimeError):
    def __init__(self, reason: str):
        self.reason = reason
        super().__init__(reason)


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True) + "\n").encode("ascii")


def manifest_for(sha: str, payloads: dict[str, bytes]) -> dict:
    return {
        "schemaVersion": 1, "artifactRole": ROLE, "candidateSha": sha, "deploymentEnvironment": "dev",
        "expectedHost": DEV_HOSTNAME, "expectedMachineId": DEV_MACHINE_ID,
        "files": [{"path": path, "byteSize": len(data), "sha256": digest(data)}
                  for path, data in sorted(payloads.items())],
    }


def check_payloads(payloads: dict[str, bytes]) -> None:
    if set(payloads) != EXPECTED_PATHS:
        raise InstallError("RELEASE_FILE_SET_MISMATCH")
    for name, data in payloads.items():
        if FORBIDDEN_MEMBER.search(name):
            raise InstallError("CUSTODY_MATERIAL_IN_RELEASE")
        if name.startswith("wheels/"):
            if digest(data) != WHEEL_HASHES[name[len("wheels/"):]]:
                raise InstallError("WHEEL_HASH_MISMATCH")
            continue
        if any(marker in data for marker in FORBIDDEN_MARKERS):
            raise InstallError("FORBIDDEN_RUNTIME_MARKER")
    if payloads["requirements.lock"] != LOCK:
        raise InstallError("DEPENDENCY_LOCK_MISMATCH")


def verify_archive(archive: Path, attestation: Path, expected_sha: str) -> tuple[dict, dict[str, bytes]]:
    if not SHA40.fullmatch(expected_sha):
        raise InstallError("INVALID_CANDIDATE_SHA")
    archive, attestation = Path(archive), Path(attestation)
    for path in (archive, attestation):
        if path.is_symlink() or not path.is_file():
            raise InstallError("ARCHIVE_MISSING")
    raw = archive.read_bytes()
    if len(raw) > MAX_ARCHIVE:
        raise InstallError("ARCHIVE_OVERSIZED")
    stamp = json.loads(attestation.read_bytes())
    if not isinstance(stamp, dict) or set(stamp) != {"schemaVersion", "artifactRole", "candidateSha",
                                                     "archiveByteSize", "archiveSha256", "manifestSha256"}:
        raise InstallError("INVALID_ATTESTATION")
    if (stamp["schemaVersion"], stamp["artifactRole"], stamp["candidateSha"], stamp["archiveByteSize"],
            stamp["archiveSha256"]) != (1, ROLE, expected_sha, len(raw), digest(raw)):
        raise InstallError("ATTESTATION_MISMATCH")
    payloads: dict[str, bytes] = {}
    with tarfile.open(fileobj=io.BytesIO(raw), mode="r:gz") as tar:
        for item in tar:
            if (item.name in payloads or item.name not in EXPECTED_PATHS | {MANIFEST} or not item.isfile()
                    or item.size > MAX_FILE):
                raise InstallError("UNSAFE_ARCHIVE_MEMBER")
            stream = tar.extractfile(item)
            data = b"" if stream is None else stream.read(MAX_FILE + 1)
            if len(data) != item.size:
                raise InstallError("ARCHIVE_MEMBER_SIZE_MISMATCH")
            payloads[item.name] = data
    manifest_bytes = payloads.pop(MANIFEST, None)
    if manifest_bytes is None or digest(manifest_bytes) != stamp["manifestSha256"]:
        raise InstallError("MANIFEST_HASH_MISMATCH")
    check_payloads(payloads)
    manifest = manifest_for(expected_sha, payloads)
    if manifest_bytes != canonical(manifest):
        raise InstallError("MANIFEST_CONTENT_MISMATCH")
    return manifest, payloads


def write_archive(payloads: dict[str, bytes], manifest: dict) -> bytes:
    """Deterministic tar.gz (sorted members, mtime 0, mode 0600, PAX)."""
    buffer = io.BytesIO()
    with gzip.GzipFile(filename="", mode="wb", fileobj=buffer, mtime=0) as zipped:
        with tarfile.open(fileobj=zipped, mode="w", format=tarfile.PAX_FORMAT) as tar:
            for path, data in sorted({**payloads, MANIFEST: canonical(manifest)}.items()):
                member = tarfile.TarInfo(path)
                member.size, member.mode, member.mtime = len(data), 0o600, 0
                tar.addfile(member, io.BytesIO(data))
    return buffer.getvalue()


# ------------------------------------------------------------------ host ---

@dataclass
class System:
    """Host access. Tests replace the root and every OS lookup and command."""

    root: Path = Path("/")
    run: Callable[..., subprocess.CompletedProcess] = field(default=None)  # type: ignore[assignment]
    user: Callable[[str], Any] = field(default=None)  # type: ignore[assignment]
    group: Callable[[str], Any] = field(default=None)  # type: ignore[assignment]
    grouplist: Callable[[str, int], list[int]] = field(default=None)  # type: ignore[assignment]
    euid: Callable[[], int] = field(default=None)  # type: ignore[assignment]
    hostname: Callable[[], str] = field(default=None)  # type: ignore[assignment]
    chown: bool = True
    # Owner expected on root-owned paths. Only tests change it.
    owner_uid: int = 0
    owner_gid: int = 0

    def __post_init__(self) -> None:
        if self.run is None:
            self.run = lambda argv, **kw: subprocess.run(argv, env=FIXED_ENV, capture_output=True, text=True,
                                                         timeout=kw.pop("timeout", 120), check=False, **kw)
        if self.user is None or self.group is None or self.grouplist is None:
            import grp
            import pwd

            def user(name: str):
                try:
                    return pwd.getpwnam(name)
                except KeyError:
                    return None

            def group(name: str):
                try:
                    return grp.getgrnam(name)
                except KeyError:
                    return None

            self.user, self.group, self.grouplist = user, group, os.getgrouplist
        if self.euid is None:
            self.euid = os.geteuid
        if self.hostname is None:
            self.hostname = lambda: os.uname().nodename

    def path(self, absolute: str) -> Path:
        return self.root / absolute.lstrip("/")

    def fixed(self, *argv: str, cwd: Path | None = None) -> subprocess.CompletedProcess:
        result = self.run(list(argv), cwd=cwd)
        if result.returncode != 0:
            raise InstallError("COMMAND_FAILED:" + Path(argv[0]).name)
        return result


def require_dev_root(system: System) -> None:
    if system.euid() != 0:
        raise InstallError("NOT_ROOT")
    try:
        machine_id = system.path("/etc/machine-id").read_text(encoding="ascii").strip()
    except OSError as exc:
        raise InstallError("NOT_DEV_HOST") from exc
    if machine_id != DEV_MACHINE_ID or system.hostname().split(".", 1)[0] != DEV_HOSTNAME:
        raise InstallError("NOT_DEV_HOST")


def _meta(system: System, absolute: str) -> dict | None:
    try:
        meta = os.lstat(system.path(absolute))
    except FileNotFoundError:
        return None
    kind = ("symlink" if stat.S_ISLNK(meta.st_mode) else "dir" if stat.S_ISDIR(meta.st_mode)
            else "file" if stat.S_ISREG(meta.st_mode) else "other")
    return {"kind": kind, "uid": meta.st_uid, "gid": meta.st_gid, "mode": format(stat.S_IMODE(meta.st_mode), "04o")}


def _file_sha(system: System, absolute: str) -> str | None:
    path = system.path(absolute)
    if path.is_symlink() or not path.is_file():
        return None
    return digest(path.read_bytes())


def _unit_state(system: System, unit: str) -> dict:
    result = system.run(["/usr/bin/systemctl", "show", "--property=LoadState,ActiveState,UnitFileState,NeedDaemonReload",
                         "--", unit])
    values = dict(line.split("=", 1) for line in result.stdout.splitlines() if "=" in line)
    return {key: values.get(key) for key in ("LoadState", "ActiveState", "UnitFileState", "NeedDaemonReload")}


def account_facts(system: System) -> dict | None:
    user, group = system.user(SERVICE_USER), system.group(SERVICE_GROUP)
    if user is None and group is None:
        return None
    if user is None or group is None:
        raise InstallError("ACCOUNT_PARTIAL")
    return {"uid": user.pw_uid, "gid": user.pw_gid, "groupGid": group.gr_gid, "home": user.pw_dir,
            "shell": user.pw_shell, "groups": sorted(set(system.grouplist(SERVICE_USER, user.pw_gid))),
            "groupMembers": sorted(group.gr_mem)}


def verify_account_contract(system: System) -> dict:
    facts = account_facts(system)
    if facts is None:
        raise InstallError("ACCOUNT_ABSENT")
    if (facts["uid"] >= 1000 or facts["uid"] == 0 or facts["gid"] != facts["groupGid"]
            or facts["home"] != NO_HOME or facts["shell"] != NOLOGIN or facts["groups"] != [facts["gid"]]
            or facts["groupMembers"] or system.path(NO_HOME).exists()):
        raise InstallError("ACCOUNT_CONTRACT")
    for name in DISTINCT_PRINCIPALS:
        other = system.user(name)
        if other is not None and (other.pw_uid == facts["uid"] or other.pw_gid == facts["gid"]):
            raise InstallError("ACCOUNT_UID_COLLISION")
    shadow = [line.split(":", 2)[1] for line in system.path("/etc/shadow").read_text(encoding="utf-8").splitlines()
              if line.startswith(SERVICE_USER + ":")]
    if len(shadow) != 1 or not shadow[0].startswith(("!", "*")):
        raise InstallError("ACCOUNT_PASSWORD_NOT_LOCKED")
    sudo = system.run(["/usr/bin/sudo", "-n", "-l", "-U", SERVICE_USER])
    if sudo.stdout.strip() != f"User {SERVICE_USER} is not allowed to run sudo on {DEV_HOSTNAME}.":
        raise InstallError("ACCOUNT_SUDO_PRIVILEGE")
    return facts


# ------------------------------------------------- expected state per stage ---

STAGES = ("L0", "L1a", "L1b.1", "L1b.2", "L1c.1", "L1c.2", "L1c.3", "L2a", "L2b.1", "L2b.2")

# AMBIENT HOST PREREQUISITE != LILITH CEREMONY ARTIFACT != LILITH MATURITY
# EVIDENCE. These generic systemd paths may pre-exist (run 36264031829). Before
# the step that requires them they may be ABSENT or PRESENT_SECURE (exact
# spec); anything else is PRESENT_UNSAFE and fails. From that step on they
# must be PRESENT_SECURE. They never indicate that a LILITH ceremony ran.
HOST_PREREQUISITES = {HOST_KEY: ("file", 0, 0, "0400"), CREDSTORE: ("dir", 0, 0, "0700")}


class HostPrerequisite(tuple):
    """Expected-path marker: ABSENT or exactly this spec; never required yet."""


def expected_paths(stage: str, sha: str | None) -> dict[str, tuple | None]:
    """Cumulative path contract after `stage`. None means must be absent.

    Tuple: (kind, owner, group, mode); owner/group "svc" is the service
    account. Only paths the ladder touches through L2b are listed.
    """
    order = STAGES.index(stage)
    at = lambda s: order >= STAGES.index(s)  # noqa: E731
    release = f"{RELEASES}/{sha}" if sha else None
    paths: dict[str, tuple | None] = {
        OPT: ("dir", 0, 0, "0755") if at("L1b.1") else None,
        RELEASES: ("dir", 0, 0, "0755") if at("L1b.1") else None,
        CURRENT: ("symlink", 0, 0, None) if at("L1b.2") else None,
        SERVICE_UNIT: ("file", 0, 0, "0644") if at("L1c.1") else None,
        SOCKET_UNIT: ("file", 0, 0, "0644") if at("L1c.1") else None,
        TMPFILES: ("file", 0, 0, "0644") if at("L1c.1") else None,
        KEYGEN_CLI: ("file", 0, 0, "0755") if at("L1c.3") else None,
        HOST_KEY: HOST_PREREQUISITES[HOST_KEY] if at("L2a") else HostPrerequisite(HOST_PREREQUISITES[HOST_KEY]),
        CREDSTORE: HOST_PREREQUISITES[CREDSTORE] if at("L2b.1") else HostPrerequisite(HOST_PREREQUISITES[CREDSTORE]),
        CREDENTIAL: ("file", 0, 0, "0600") if at("L2b.2") else None,
        **{path: None for path in DEFERRED_PATHS},
    }
    if release:
        paths[release] = ("dir", 0, 0, "0755") if at("L1b.1") else None
    return paths


def prerequisite_state(system: System, absolute: str, meta: dict | None) -> str:
    if meta is None:
        return "ABSENT"
    kind, uid, gid, mode = HOST_PREREQUISITES[absolute]
    if (meta["kind"], meta["uid"], meta["gid"], meta["mode"]) == (kind, system.owner_uid, system.owner_gid, mode):
        return "PRESENT_SECURE"
    return "PRESENT_UNSAFE"


def status(system: System, stage: str, sha: str | None = None) -> dict:
    """Read-only POST evidence for `stage`, and PASS only if it matches exactly."""
    if stage not in STAGES:
        raise InstallError("UNKNOWN_STAGE")
    if STAGES.index(stage) >= STAGES.index("L1b.1") and (sha is None or not SHA40.fullmatch(sha)):
        raise InstallError("CANDIDATE_SHA_REQUIRED")
    failures: list[str] = []
    observed: dict[str, Any] = {}
    account = account_facts(system)
    observed["account"] = account
    if STAGES.index(stage) >= STAGES.index("L1a"):
        try:
            verify_account_contract(system)
        except InstallError as exc:
            failures.append(exc.reason)
    elif account is not None:
        failures.append("ACCOUNT_PRESENT_TOO_EARLY")
    prerequisites: dict[str, str] = {}
    for absolute, expected in expected_paths(stage, sha).items():
        meta = _meta(system, absolute)
        observed[absolute] = meta
        if absolute in HOST_PREREQUISITES:
            prerequisites[absolute] = prerequisite_state(system, absolute, meta)
            if prerequisites[absolute] == "PRESENT_UNSAFE":
                failures.append("HOST_PREREQ_UNSAFE:" + absolute)
                continue
            if isinstance(expected, HostPrerequisite):
                continue  # ABSENT or PRESENT_SECURE: both valid, neither is maturity
        if expected is None:
            if meta is not None:
                failures.append("UNEXPECTED_PRESENT:" + absolute)
            continue
        if meta is None:
            failures.append("MISSING:" + absolute)
            continue
        kind, uid, gid, mode = expected
        uid, gid = (system.owner_uid if uid == 0 else uid), (system.owner_gid if gid == 0 else gid)
        if meta["kind"] != kind or meta["uid"] != uid or meta["gid"] != gid or (mode and meta["mode"] != mode):
            failures.append("CONTRACT:" + absolute)
    if sha and STAGES.index(stage) >= STAGES.index("L1b.1") and system.path(RELEASES).is_dir():
        entries = sorted(entry.name for entry in system.path(RELEASES).iterdir())
        observed["releaseEntries"] = entries
        if entries != [sha]:
            failures.append("RELEASE_SET")  # exactly RELEASE_SHA; no second release or staging leftover
    if sha and STAGES.index(stage) >= STAGES.index("L1b.2"):
        target = os.readlink(system.path(CURRENT)) if system.path(CURRENT).is_symlink() else None
        observed["currentTarget"] = target
        if target != f"releases/{sha}":
            failures.append("CURRENT_TARGET")
    if STAGES.index(stage) >= STAGES.index("L1c.1") and sha:
        for member, target in UNIT_TARGETS.items():
            if _file_sha(system, target) != _file_sha(system, f"{RELEASES}/{sha}/{member}"):
                failures.append("UNIT_BYTES:" + target)
    if STAGES.index(stage) >= STAGES.index("L1c.3") and sha:
        if _file_sha(system, KEYGEN_CLI) != _file_sha(system, f"{RELEASES}/{sha}/{CLI_PATH}"):
            failures.append("CLI_BYTES")
    for unit in ("lilith-authority-dev.service", "lilith-authority-dev.socket"):
        state = _unit_state(system, unit)
        observed[unit] = state
        if state["ActiveState"] not in (None, "inactive"):
            failures.append("UNIT_ACTIVE:" + unit)
        if state["UnitFileState"] not in (None, "", "static"):
            failures.append("UNIT_ENABLEABLE_OR_ENABLED:" + unit)
        if STAGES.index(stage) >= STAGES.index("L1c.2") and \
                (state["LoadState"], state["NeedDaemonReload"]) != ("loaded", "no"):
            failures.append("UNIT_NOT_LOADED:" + unit)
    observed["needrestartSha256"] = _file_sha(system, NEEDRESTART)
    if observed["needrestartSha256"] != NEEDRESTART_SHA256:
        failures.append("NEEDRESTART_CONTROL_CHANGED")
    if STAGES.index(stage) < STAGES.index("L2b.2") and system.path(CREDSTORE).is_dir() \
            and any(system.path(CREDSTORE).iterdir()):
        failures.append("CREDSTORE_NOT_EMPTY")
    observed["credentialBlobSha256"] = _file_sha(system, CREDENTIAL)
    observed["hostPrerequisites"] = prerequisites
    return {"schemaVersion": 1, "stage": stage, "releaseSha": sha,
            "result": "PASS" if not failures else "FAIL", "failures": failures, "observed": observed}


# ------------------------------------------------------ mutating stages ---

def _require(report: dict) -> None:
    if report["result"] != "PASS":
        raise InstallError("PRECONDITION_FAILED:" + ",".join(report["failures"]))


def _mkdir(system: System, absolute: str, mode: int) -> None:
    path = system.path(absolute)
    path.mkdir(mode=mode)
    if system.chown:
        os.chown(path, 0, 0)
    os.chmod(path, mode)


def _write_new(system: System, target: Path, data: bytes, mode: int) -> None:
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(target, flags, mode)
    try:
        os.write(fd, data)
        os.fsync(fd)
    finally:
        os.close(fd)
    if system.chown:
        os.chown(target, 0, 0)
    os.chmod(target, mode)


def stage_accounts(system: System) -> dict:
    require_dev_root(system)
    _require(status(system, "L0"))
    system.fixed("/usr/sbin/useradd", "--system", "--user-group", "--no-create-home", "--home-dir", NO_HOME,
                 "--shell", NOLOGIN, SERVICE_USER)
    return status(system, "L1a")


def _normalize_tree(system: System, top: Path) -> None:
    """root-owned, dirs 0755, files 0644 or 0755; symlinks are never followed."""
    for directory, subdirs, files in os.walk(top):
        for name in subdirs + files:
            path = Path(directory) / name
            if system.chown:
                os.lchown(path, 0, 0)
            if path.is_symlink():
                continue
            if path.is_dir():
                os.chmod(path, 0o755)
            else:
                os.chmod(path, 0o755 if os.stat(path).st_mode & 0o111 else 0o644)
    if system.chown:
        os.chown(top, 0, 0)
    os.chmod(top, 0o755)


def stage_release(system: System, sha: str, archive: Path, attestation: Path) -> dict:
    require_dev_root(system)
    _require(status(system, "L1a"))
    manifest, payloads = verify_archive(archive, attestation, sha)
    if not system.path(OPT).exists():
        _mkdir(system, OPT, 0o755)
    if not system.path(RELEASES).exists():
        _mkdir(system, RELEASES, 0o755)
    staging = system.path(f"{RELEASES}/.{sha}.staging")
    if os.path.lexists(staging):
        raise InstallError("RELEASE_STAGING_COLLISION")
    staging.mkdir(mode=0o700)
    for relative, data in sorted({**payloads, MANIFEST: canonical(manifest)}.items()):
        target = staging.joinpath(*relative.split("/"))
        target.parent.mkdir(parents=True, exist_ok=True, mode=0o755)
        _write_new(system, target, data, 0o755 if relative == CLI_PATH else 0o644)
    system.fixed("/usr/bin/python3", "-m", "venv", str(staging / "venv"))
    system.fixed(str(staging / "venv/bin/python"), "-m", "pip", "install", "--no-index", "--no-input",
                 "--disable-pip-version-check", "--require-hashes", "--find-links", str(staging / "wheels"),
                 "-r", str(staging / "requirements.lock"))
    _normalize_tree(system, staging)
    # Import check as the unprivileged service identity, never as root.
    system.fixed("/usr/sbin/runuser", "-u", SERVICE_USER, "--", str(staging / "venv/bin/python"), "-I", "-B", "-c",
                 "import sys; sys.path.insert(0, sys.argv[1]); import lilith_authority_dev.server", str(staging),
                 cwd=staging)
    staging.rename(system.path(f"{RELEASES}/{sha}"))
    return status(system, "L1b.1", sha)


def stage_select(system: System, sha: str) -> dict:
    require_dev_root(system)
    _require(status(system, "L1b.1", sha))
    tmp = system.path(f"{OPT}/.current.tmp")
    if os.path.lexists(tmp):
        raise InstallError("SELECTOR_STAGING_COLLISION")
    os.symlink(f"releases/{sha}", tmp)
    if system.chown:
        os.lchown(tmp, 0, 0)
    os.rename(tmp, system.path(CURRENT))
    return status(system, "L1b.2", sha)


def stage_units(system: System, sha: str) -> dict:
    require_dev_root(system)
    _require(status(system, "L1b.2", sha))
    for member, target in UNIT_TARGETS.items():
        data = system.path(f"{RELEASES}/{sha}/{member}").read_bytes()
        _write_new(system, system.path(target), data, 0o644)
    return status(system, "L1c.1", sha)


def stage_cli(system: System, sha: str) -> dict:
    require_dev_root(system)
    _require(status(system, "L1c.2", sha))
    data = system.path(f"{RELEASES}/{sha}/{CLI_PATH}").read_bytes()
    _write_new(system, system.path(KEYGEN_CLI), data, 0o755)
    return status(system, "L1c.3", sha)


def stage_credstore(system: System, sha: str) -> dict:
    """L2b.1: create the credstore if ABSENT; adopt it unchanged if PRESENT_SECURE.

    The L2a POST already requires it to be absent or exactly root:root 0700 and
    empty. Zero mutation is valid when the prerequisite already exists in the
    accepted state; that is not evidence that a LILITH ceremony ran.
    """
    require_dev_root(system)
    before = status(system, "L2a", sha)
    _require(before)
    if before["observed"]["hostPrerequisites"][CREDSTORE] == "ABSENT":
        _mkdir(system, CREDSTORE, 0o700)
        mutation = "CREATED"
    else:
        mutation = "ADOPTED_NO_MUTATION"
    report = status(system, "L2b.1", sha)
    report["mutation"] = mutation
    return report


def main(argv: list[str], system: System | None = None) -> int:
    system = system or System()
    try:
        if not argv:
            raise InstallError("USAGE")
        stage, rest = argv[0], argv[1:]
        if stage == "status" and len(rest) in (2, 3) and rest[0] == "--expect":
            require_dev_root(system)
            report = status(system, rest[1], rest[2] if len(rest) == 3 else None)
        elif stage == "preflight" and not rest:
            require_dev_root(system)
            report = status(system, "L0")
        elif stage == "accounts" and not rest:
            report = stage_accounts(system)
        elif stage == "release" and len(rest) == 3:
            report = stage_release(system, rest[0], Path(rest[1]), Path(rest[2]))
        elif stage == "select" and len(rest) == 1:
            report = stage_select(system, rest[0])
        elif stage == "units" and len(rest) == 1:
            report = stage_units(system, rest[0])
        elif stage == "cli" and len(rest) == 1:
            report = stage_cli(system, rest[0])
        elif stage == "credstore" and len(rest) == 1:
            report = stage_credstore(system, rest[0])
        else:
            raise InstallError("USAGE")
    except InstallError as exc:
        print(f"install_authority_dev: REFUSED {exc.reason}", file=sys.stderr)
        return 2
    sys.stdout.write(json.dumps(report, sort_keys=True, indent=2) + "\n")
    return 0 if report["result"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
