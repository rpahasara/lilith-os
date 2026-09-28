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
| `custody` | L2c | B1b-3e (RR-26): create `/etc/lilith-authority-custody` and its `prepared/` and `retired/` directories, each `root:root 0700`, on the credstore's filesystem |

B1b-3e PR-1S adds, SOURCE ONLY (docs/architecture/slice-15b2b-b1b3e-pr1s-runtime-wiring.md):

| Stage | Phase | Mutation |
| --- | --- | --- |
| `upgrade-baseline <OLD>` | P1A-0 | none: print the observed baseline document for the owner to record |
| `upgrade-status <OLD> <NEW> <baseline>` | any | none: upgrade classification and preservation |
| `upgrade-stage <OLD> <NEW> <archive> <attestation> <baseline>` | M-A1 | `releases/<NEW>` beside `<OLD>` |
| `upgrade-select <OLD> <NEW> <baseline>` | M-A2 | `current -> releases/<NEW>` (atomic replace) |
| `upgrade-units <OLD> <NEW> <baseline>` | M-A3 | replace the signer unit, socket, tmpfiles files |
| `upgrade-cli <OLD> <NEW> <baseline>` | M-A5 | replace the keygen; create the new fixed CLIs |
| `upgrade-retire-old <OLD> <NEW> <baseline>` | M-A6 | remove `releases/<OLD>` after the NEW tree verifies |
| `witness-account` | P1A-8a | create system user+group `lilith-recovery-witness` |
| `witness-units` | P1A-8b | install the witness unit, two sockets, tmpfiles (no reload) |
| `skeleton` | P1A-9 | empty root-owned `/etc/lilith-authority-dev/{trust,registry,owner}`, `/etc/lilith-recovery-witness/credentials`, `/var/lib/lilith-authority-custody/holds` |
| `install-anchors <sha> <registry-root> <witness-anchor>` | P1B-4 | the two public trust anchors (write-once) |
| `install-registry <sha> <registry>` | P1B-5 | one public registry generation (write-once) |
| `install-owner-inputs <sha> <genesis-pin> <register>` | P1B-8 | the on-host owner pin and register copies (write-once) |
| `witness-state <sha>` | P1B-9a | `/var/lib/lilith-recovery-witness` `lilith-recovery-witness:lilith-authority-dev 2750` |

`UPGRADE_EXISTING_DEV_SYNTHETIC` (preflight §7.2) is the closed upgrade
mode of the existing custody host: it enters only from `status --expect
L2b.2 <OLD>` PASS with an owner-recorded accepted baseline, re-proves the
§6.2 preservation facts before and after every stage, and ends at
`status --expect L2b.2 <NEW>` PASS. It never runs a keygen, `systemd-creds`,
`useradd` for the signer, or a unit start, enable, or reload. A mismatch is
a STOP; there is no force and no repair. The K-WIT keygen, the ledger
provisioning, genesis, and holds are fixed release CLIs, never this file.

`systemctl daemon-reload` (L1c.2), `systemd-creds setup` (L2a), and the
keygen ceremony (L2b.2) are separate owner commands in the runbook; this
installer never runs them. The `custody` stage (L2c) belongs to the B1b-3e
successor-capable release and is SOURCE ONLY until a separately authorized
PR-1 install: docs/architecture/slice-15b2b-b1b3e-source-prep-b-successor-custody.md.
It creates empty directories only; it never writes, moves, or deletes a
credential blob. This installer never creates a key, a credential, the host
credential key, `/var/lib/lilith-authority-dev`, `/run/lilith-authority-dev`,
or the authority ledger, and it never starts, enables, or reloads a unit.
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
# B1b-3e RR-26 side-by-side custody. Referenced by no unit directive; the
# signer unit denies the whole root (`InaccessiblePaths=`).
CUSTODY_ROOT = "/etc/lilith-authority-custody"
PREPARED_DIR = CUSTODY_ROOT + "/prepared"
RETIRED_DIR = CUSTODY_ROOT + "/retired"
CUSTODY_DIRS = (CUSTODY_ROOT, PREPARED_DIR, RETIRED_DIR)
HOST_KEY = "/var/lib/systemd/credential.secret"
# B1b-3e PR-1S. Pinned against lilith_authority_host.paths by tests (this file
# runs as one streamed script and imports nothing from the repository).
WITNESS_USER = "lilith-recovery-witness"
WITNESS_DISTINCT_PRINCIPALS = ("lilith", "lilith-memory-broker", "lilith-memory-relay", SERVICE_USER)
AUTHORITY_CONFIG = "/etc/lilith-authority-dev"
TRUST_DIR = AUTHORITY_CONFIG + "/trust"
REGISTRY_DIR = AUTHORITY_CONFIG + "/registry"
OWNER_INPUT_DIR = AUTHORITY_CONFIG + "/owner"
REGISTRY_ROOT_ANCHOR = TRUST_DIR + "/registry-root.json"
WITNESS_ANCHOR = TRUST_DIR + "/witness-anchor.json"
GENESIS_PIN_COPY = OWNER_INPUT_DIR + "/genesis-pin.json"
AUTHORIZATION_REGISTER_COPY = OWNER_INPUT_DIR + "/authorization-register.json"
WITNESS_CREDENTIAL_PARENT = "/etc/lilith-recovery-witness"
WITNESS_CREDENTIAL_ROOT = WITNESS_CREDENTIAL_PARENT + "/credentials"
WITNESS_BLOB = WITNESS_CREDENTIAL_ROOT + "/lilith-recovery-witness.witness.cred"
HOLD_PARENT = "/var/lib/lilith-authority-custody"
HOLD_STORE = HOLD_PARENT + "/holds"
AUTHORITY_STATE = "/var/lib/lilith-authority-dev"
AUTHORITY_LEDGER = AUTHORITY_STATE + "/authority_ledger.db"
AUTHORITY_RUNTIME = "/run/lilith-authority-dev"
AUTHORITY_CREDENTIALS_RUNTIME = "/run/credentials/lilith-authority-dev.service"
WITNESS_STATE = "/var/lib/lilith-recovery-witness"
WITNESS_RUNTIME = "/run/lilith-recovery-witness"
WITNESS_CREDENTIALS_RUNTIME = "/run/credentials/lilith-recovery-witness.service"
SUPERSEDED_WITNESS_CREDSTORE = "/etc/credstore.encrypted/lilith-recovery-witness.witness.cred"
AUTHORITY_UNITS = ("lilith-authority-dev.service", "lilith-authority-dev.socket")
WITNESS_UNITS = ("lilith-recovery-witness.service", "lilith-recovery-witness-owner.socket",
                 "lilith-recovery-witness-signer.socket")
SKELETON_DIRS = (  # (path, mode) in creation order; all root:root, all empty
    (AUTHORITY_CONFIG, 0o755), (TRUST_DIR, 0o755), (REGISTRY_DIR, 0o755), (OWNER_INPUT_DIR, 0o755),
    (WITNESS_CREDENTIAL_PARENT, 0o700), (WITNESS_CREDENTIAL_ROOT, 0o700), (HOLD_PARENT, 0o700), (HOLD_STORE, 0o700),
)
# The accepted live baseline (preflight §4, KNOWN): the installed release and
# the CURRENT ciphertext SHA-256. Everything else the owner records at P1A-0.
ACCEPTED_OLD_RELEASE = "9ac7de22bf977385ceb954624677e33f0bae062b"
ACCEPTED_CURRENT_SHA256 = "6a61c350e848a833868f4573982fca9c75e2af79ccc9bd3716ae0303c26973f3"
UNKNOWN_UNTIL_LIVE_PREFLIGHT = "UNKNOWN_UNTIL_LIVE_PREFLIGHT"
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
        "__init__.py", "profile.py", "credential.py", "evidence_minter.py", "protocol.py", "core.py", "server.py",
        "ledger.py", "recovery.py", "state.py", "witness_client.py")),
    *(f"lilith_authority_host/{name}" for name in ("__init__.py", "paths.py", "inputs.py", "store_observer.py")),
    *(f"lilith_authority_root/{name}" for name in (
        "__init__.py", "hold_store.py", "observers.py", "verifier.py", "genesis.py", "ledger_tool.py", "clients.py",
        "cli.py")),
    *(f"lilith_recovery_witness/{name}" for name in (
        "__init__.py", "profile.py", "credential.py", "storage.py", "writer.py", "protocol.py", "core.py", "server.py")),
    "lilith_memory/__init__.py", "lilith_memory/canonical_contracts.py", "lilith_memory/owner_proof.py",
    *(f"lilith_owner_memory/{name}" for name in (
        "__init__.py", "contracts.py", "authority_contracts.py", "authority_verifier.py", "recovery_contracts.py",
        "rotation_contracts.py", "witness_readiness.py", "successor_custody.py", "successor_readiness.py",
        "authority_ledger_journal.py", "pr1_bootstrap.py", "pr1_acceptance.py")),
    "assets/lilith-authority-dev.service", "assets/lilith-authority-dev.socket", "assets/lilith-authority-dev.tmpfiles.conf",
    "assets/lilith-recovery-witness.service", "assets/lilith-recovery-witness-owner.socket",
    "assets/lilith-recovery-witness-signer.socket", "assets/lilith-recovery-witness.tmpfiles.conf",
})
CLI_PATH = "cli/lilith-authority-keygen-dev"
# Every fixed release CLI and its host path (M-A5). The keygen keeps its name.
CLI_TARGETS = {CLI_PATH: KEYGEN_CLI, **{f"cli/{name}": f"/usr/local/sbin/{name}" for name in (
    "lilith-authority-ledger-dev", "lilith-authority-hold-dev", "lilith-authority-verify-dev",
    "lilith-authority-recovery-dev", "lilith-recovery-witness-owner-dev")}}
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
EXPECTED_PATHS = RUNTIME_PATHS | set(CLI_TARGETS) | {"requirements.lock"} | {"wheels/" + name for name in WHEEL_HASHES}
MANIFEST = "release-manifest.json"
# Installed host files come only from these archive members.
UNIT_TARGETS = {
    "assets/lilith-authority-dev.service": SERVICE_UNIT,
    "assets/lilith-authority-dev.socket": SOCKET_UNIT,
    "assets/lilith-authority-dev.tmpfiles.conf": TMPFILES,
}
WITNESS_UNIT_TARGETS = {
    "assets/lilith-recovery-witness.service": UNIT_DIR + "/lilith-recovery-witness.service",
    "assets/lilith-recovery-witness-owner.socket": UNIT_DIR + "/lilith-recovery-witness-owner.socket",
    "assets/lilith-recovery-witness-signer.socket": UNIT_DIR + "/lilith-recovery-witness-signer.socket",
    "assets/lilith-recovery-witness.tmpfiles.conf": "/etc/tmpfiles.d/lilith-recovery-witness.conf",
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


def _principal(system: System, value: Any, *, owner: bool) -> int | None:
    """Spec owner/group -> expected numeric id. 0 is root (TEST seam aware)."""
    if value is None:
        return None
    if value == 0:
        return system.owner_uid if owner else system.owner_gid
    user = system.user(SERVICE_USER if value == "svc" else WITNESS_USER)
    if user is None:
        return -1  # the account is missing: every comparison fails closed
    return user.pw_uid if owner else user.pw_gid


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


def verify_account_contract(system: System, name: str = SERVICE_USER,
                            distinct: tuple[str, ...] = DISTINCT_PRINCIPALS + (WITNESS_USER,)) -> dict:
    """The L1a service-account contract (system, < 1000, primary group only,
    nologin, `/nonexistent`, locked, no sudo, no shared uid or gid). The
    signer and the witness each satisfy it with their own identity."""
    facts = named_account_facts(system, name)
    if facts is None:
        raise InstallError("ACCOUNT_ABSENT")
    if (facts["uid"] >= 1000 or facts["uid"] == 0 or facts["gid"] != facts["groupGid"]
            or facts["home"] != NO_HOME or facts["shell"] != NOLOGIN or facts["groups"] != [facts["gid"]]
            or facts["groupMembers"] or system.path(NO_HOME).exists()):
        raise InstallError("ACCOUNT_CONTRACT")
    for other_name in distinct:
        if other_name == name:
            continue
        other = system.user(other_name)
        if other is not None and (other.pw_uid == facts["uid"] or other.pw_gid == facts["gid"]):
            raise InstallError("ACCOUNT_UID_COLLISION")
    shadow = [line.split(":", 2)[1] for line in system.path("/etc/shadow").read_text(encoding="utf-8").splitlines()
              if line.startswith(name + ":")]
    if len(shadow) != 1 or not shadow[0].startswith(("!", "*")):
        raise InstallError("ACCOUNT_PASSWORD_NOT_LOCKED")
    sudo = system.run(["/usr/bin/sudo", "-n", "-l", "-U", name])
    if sudo.stdout.strip() != f"User {name} is not allowed to run sudo on {DEV_HOSTNAME}.":
        raise InstallError("ACCOUNT_SUDO_PRIVILEGE")
    return facts


def named_account_facts(system: System, name: str) -> dict | None:
    user, group = system.user(name), system.group(name)
    if user is None and group is None:
        return None
    if user is None or group is None:
        raise InstallError("ACCOUNT_PARTIAL")
    return {"uid": user.pw_uid, "gid": user.pw_gid, "groupGid": group.gr_gid, "home": user.pw_dir,
            "shell": user.pw_shell, "groups": sorted(set(system.grouplist(name, user.pw_gid))),
            "groupMembers": sorted(group.gr_mem)}


def verify_witness_account_contract(system: System) -> dict:
    """PR-1S S-4: the witness identity is its own; it shares no uid or gid,
    belongs to no application, broker, or signer group, and has no sudo."""
    facts = verify_account_contract(system, WITNESS_USER, WITNESS_DISTINCT_PRINCIPALS)
    signer_group = system.group(SERVICE_GROUP)
    if signer_group is not None and (WITNESS_USER in signer_group.gr_mem or signer_group.gr_gid in facts["groups"]):
        raise InstallError("WITNESS_IN_SIGNER_GROUP")
    return facts


# ------------------------------------------------- expected state per stage ---

STAGES = ("L0", "L1a", "L1b.1", "L1b.2", "L1c.1", "L1c.2", "L1c.3", "L2a", "L2b.1", "L2b.2", "L2c",
          # B1b-3e PR-1S phase contracts (shape only; content is the root verifier's).
          "P1A-8a", "P1A-8b", "P1A-8c", "P1A-9",
          "P1B-2", "P1B-4", "P1B-5", "P1B-6", "P1B-8", "P1B-9a", "P1B-9b", "P1B-10", "P1B-11")

# AMBIENT HOST PREREQUISITE != LILITH CEREMONY ARTIFACT != LILITH MATURITY
# EVIDENCE. These generic systemd paths may pre-exist (run 36264031829). Before
# the step that requires them they may be ABSENT or PRESENT_SECURE (exact
# spec); anything else is PRESENT_UNSAFE and fails. From that step on they
# must be PRESENT_SECURE. They never indicate that a LILITH ceremony ran.
HOST_PREREQUISITES = {HOST_KEY: ("file", 0, 0, "0400"), CREDSTORE: ("dir", 0, 0, "0700")}


class HostPrerequisite(tuple):
    """Expected-path marker: ABSENT or exactly this spec; never required yet."""


class RuntimeDirectory(tuple):
    """PR-1 marker: a tmpfiles-created runtime directory that may already
    exist (boot or `systemd-tmpfiles`) once its tmpfiles file is installed:
    ABSENT or exactly this spec, until the phase that requires it."""


# PR-1 paths: (stage from which required, spec). Before that stage: absent.
# Owner/group "svc" is the signer account, "wit" the witness account, None
# is not checked (systemd-managed runtime credentials).
PR1_PATHS = {
    WITNESS_UNIT_TARGETS["assets/lilith-recovery-witness.service"]: ("P1A-8b", ("file", 0, 0, "0644")),
    WITNESS_UNIT_TARGETS["assets/lilith-recovery-witness-owner.socket"]: ("P1A-8b", ("file", 0, 0, "0644")),
    WITNESS_UNIT_TARGETS["assets/lilith-recovery-witness-signer.socket"]: ("P1A-8b", ("file", 0, 0, "0644")),
    WITNESS_UNIT_TARGETS["assets/lilith-recovery-witness.tmpfiles.conf"]: ("P1A-8b", ("file", 0, 0, "0644")),
    **{path: ("P1A-9", ("dir", 0, 0, format(mode, "04o"))) for path, mode in SKELETON_DIRS},
    WITNESS_BLOB: ("P1B-2", ("file", 0, 0, "0600")),
    REGISTRY_ROOT_ANCHOR: ("P1B-4", ("file", 0, 0, "0644")),
    WITNESS_ANCHOR: ("P1B-4", ("file", 0, 0, "0644")),
    AUTHORITY_STATE: ("P1B-6", ("dir", "svc", "svc", "0700")),
    AUTHORITY_LEDGER: ("P1B-6", ("file", "svc", "svc", "0600")),
    GENESIS_PIN_COPY: ("P1B-8", ("file", 0, 0, "0644")),
    AUTHORIZATION_REGISTER_COPY: ("P1B-8", ("file", 0, 0, "0644")),
    WITNESS_STATE: ("P1B-9a", ("dir", "wit", "svc", "2750")),
}
# Runtime directories (tmpfiles, or systemd while a unit runs): from their
# phase they may exist with exactly this spec; they are never required.
PR1_RUNTIME_DIRECTORIES = {
    AUTHORITY_RUNTIME: ("P1A-8a", ("dir", 0, 0, "0700")),
    WITNESS_RUNTIME: ("P1A-8b", ("dir", 0, "svc", "0710")),
    WITNESS_CREDENTIALS_RUNTIME: ("P1B-9a", ("dir", None, None, None)),
    AUTHORITY_CREDENTIALS_RUNTIME: ("P1B-11", ("dir", None, None, None)),
}
# Exact directory listings once each directory exists (stage, allowed names).
PR1_LISTINGS = {
    AUTHORITY_CONFIG: (("P1A-9", ("owner", "registry", "trust")),),
    TRUST_DIR: (("P1A-9", ()), ("P1B-4", ("registry-root.json", "witness-anchor.json"))),
    OWNER_INPUT_DIR: (("P1A-9", ()), ("P1B-8", ("authorization-register.json", "genesis-pin.json"))),
    WITNESS_CREDENTIAL_PARENT: (("P1A-9", ("credentials",)),),
    WITNESS_CREDENTIAL_ROOT: (("P1A-9", ()), ("P1B-2", ("lilith-recovery-witness.witness.cred",))),
    HOLD_PARENT: (("P1A-9", ("holds",)),),
    HOLD_STORE: (("P1A-9", ()),),
}
_REGISTRY_FILE = re.compile(r"authority-registry\.v[1-9][0-9]{0,15}\.json\Z")
_HOLD_FILE = re.compile(r"[0-9a-f]{64}\.json\Z")


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
        **{path: ("dir", 0, 0, "0700") if at("L2c") else None for path in CUSTODY_DIRS},
        **{path: None for path in DEFERRED_PATHS},
    }
    for path, (required, spec) in PR1_PATHS.items():
        paths[path] = spec if at(required) else None
    for path, (allowed, spec) in PR1_RUNTIME_DIRECTORIES.items():
        paths[path] = RuntimeDirectory(spec) if at(allowed) else None
    paths[SUPERSEDED_WITNESS_CREDSTORE] = None  # RR-36: never in the K-ACT credstore
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
            if not isinstance(expected, RuntimeDirectory):
                failures.append("MISSING:" + absolute)
            continue
        kind, uid, gid, mode = expected
        uid, gid = _principal(system, uid, owner=True), _principal(system, gid, owner=False)
        if meta["kind"] != kind or (uid is not None and meta["uid"] != uid) \
                or (gid is not None and meta["gid"] != gid) or (mode and meta["mode"] != mode):
            failures.append("CONTRACT:" + absolute)
    if sha and STAGES.index(stage) >= STAGES.index("L1b.1") and system.path(RELEASES).is_dir():
        entries = sorted(entry.name for entry in system.path(RELEASES).iterdir())
        observed["releaseEntries"] = entries
        if entries != [sha]:
            # RELEASE_SET began as the B1b-3d *initial-custody* ceremony invariant:
            # exactly one installed release, RELEASE_SHA, and no staging leftover.
            # It was not a permanent release-retention or rotation policy. B1b-3e
            # RR-25 accepted it as the single-installed-release contract: exactly
            # one executable release (the successor-capable one), and no retained
            # executable release for rollback. Release rollback != authority rollback.
            failures.append("RELEASE_SET")
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
        failures.extend(cli_set_failures(system, sha))
    if at_stage(stage, "P1A-8b") and sha:
        for member, target in WITNESS_UNIT_TARGETS.items():
            if _file_sha(system, target) != _file_sha(system, f"{RELEASES}/{sha}/{member}"):
                failures.append("UNIT_BYTES:" + target)
    for unit in AUTHORITY_UNITS + WITNESS_UNITS:
        state = _unit_state(system, unit)
        observed[unit] = state
        may_run = at_stage(stage, "P1B-11") if unit in AUTHORITY_UNITS else at_stage(stage, "P1B-9a")
        if state["ActiveState"] not in (None, "inactive") and not (may_run and state["ActiveState"] == "active"):
            failures.append("UNIT_ACTIVE:" + unit)
        if state["UnitFileState"] not in (None, "", "static"):
            failures.append("UNIT_ENABLEABLE_OR_ENABLED:" + unit)
        loaded_from = "L1c.2" if unit in AUTHORITY_UNITS else "P1A-8c"
        if at_stage(stage, loaded_from) and (state["LoadState"], state["NeedDaemonReload"]) != ("loaded", "no"):
            failures.append("UNIT_NOT_LOADED:" + unit)
    observed["needrestartSha256"] = _file_sha(system, NEEDRESTART)
    if observed["needrestartSha256"] != NEEDRESTART_SHA256:
        failures.append("NEEDRESTART_CONTROL_CHANGED")
    if STAGES.index(stage) < STAGES.index("L2b.2") and system.path(CREDSTORE).is_dir() \
            and any(system.path(CREDSTORE).iterdir()):
        failures.append("CREDSTORE_NOT_EMPTY")
    observed["credentialBlobSha256"] = _file_sha(system, CREDENTIAL)
    if STAGES.index(stage) >= STAGES.index("L2c"):
        failures.extend(custody_failures(system))
    if at_stage(stage, "P1A-8a"):
        try:
            observed["witnessAccount"] = verify_witness_account_contract(system)
        except InstallError as exc:
            failures.append("WITNESS_" + exc.reason)
    else:
        try:
            if named_account_facts(system, WITNESS_USER) is not None:
                failures.append("WITNESS_ACCOUNT_PRESENT_TOO_EARLY")
        except InstallError:
            failures.append("WITNESS_ACCOUNT_PARTIAL")
    failures.extend(pr1_listing_failures(system, stage))
    observed["hostPrerequisites"] = prerequisites
    # `releaseSha` is canonical. `candidateSha` is a deprecated compatibility
    # alias kept for existing V1 consumers; it always meant the installed release
    # artifact SHA and always equals `releaseSha`. Control-tool provenance
    # (CONTROL_SHA) is deliberately absent: status owns installed release state.
    return {"schemaVersion": 1, "stage": stage, "releaseSha": sha, "candidateSha": sha,
            "result": "PASS" if not failures else "FAIL", "failures": failures, "observed": observed}


def custody_failures(system: System) -> list[str]:
    """RR-26 POST facts beyond owner and mode: exact names, empty slot
    directories, and one filesystem with the credstore (renames only)."""
    failures: list[str] = []
    root = system.path(CUSTODY_ROOT)
    if root.is_dir() and not root.is_symlink() and sorted(p.name for p in root.iterdir()) != ["prepared", "retired"]:
        failures.append("CUSTODY_ROOT_UNEXPECTED_ENTRY")
    for directory in (PREPARED_DIR, RETIRED_DIR):
        path = system.path(directory)
        if path.is_dir() and not path.is_symlink() and any(path.iterdir()):
            failures.append("CUSTODY_NOT_EMPTY:" + directory)
    try:
        devices = {os.lstat(system.path(p)).st_dev for p in (CREDSTORE, PREPARED_DIR, RETIRED_DIR)}
    except OSError:
        devices = set()
    if len(devices) != 1:
        failures.append("CUSTODY_FILESYSTEM_MISMATCH")
    return failures


def at_stage(stage: str, required: str) -> bool:
    return STAGES.index(stage) >= STAGES.index(required)


def cli_set_failures(system: System, sha: str) -> list[str]:
    """Every fixed CLI the selected release ships equals its release copy on
    the host; a CLI the release does not ship must be absent (the installed
    `9ac7de2` ships only the keygen)."""
    failures = []
    for member, target in CLI_TARGETS.items():
        if member == CLI_PATH:
            continue
        shipped = _file_sha(system, f"{RELEASES}/{sha}/{member}")
        installed = _meta(system, target)
        if shipped is None:
            if installed is not None:
                failures.append("CLI_NOT_IN_RELEASE:" + target)
        elif _file_sha(system, target) != shipped or installed != {"kind": "file", "uid": system.owner_uid,
                                                                    "gid": system.owner_gid, "mode": "0755"}:
            failures.append("CLI_BYTES:" + target)
    return failures


def pr1_listing_failures(system: System, stage: str) -> list[str]:
    """Exact directory listings of the PR-1 skeleton, per phase (shape only)."""
    failures = []
    for directory, steps in PR1_LISTINGS.items():
        allowed = None
        for required, names in steps:
            if at_stage(stage, required):
                allowed = names
        path = system.path(directory)
        if allowed is None or not path.is_dir() or path.is_symlink():
            continue
        names = sorted(entry.name for entry in path.iterdir())
        if directory == HOLD_STORE and at_stage(stage, "P1B-10"):
            if len(names) != 1 or not _HOLD_FILE.fullmatch(names[0]):
                failures.append("LISTING:" + directory)
            continue
        if names != sorted(allowed):
            failures.append("LISTING:" + directory)
    registry = system.path(REGISTRY_DIR)
    if at_stage(stage, "P1A-9") and registry.is_dir() and not registry.is_symlink():
        names = sorted(entry.name for entry in registry.iterdir())
        if (at_stage(stage, "P1B-5") and not names) or (not at_stage(stage, "P1B-5") and names) \
                or any(not _REGISTRY_FILE.fullmatch(name) for name in names):
            failures.append("LISTING:" + REGISTRY_DIR)
    state = system.path(AUTHORITY_STATE)
    if at_stage(stage, "P1B-6") and state.is_dir() and not state.is_symlink():
        names = {entry.name for entry in state.iterdir()}
        if not names <= {"authority_ledger.db", "authority_ledger.db-wal", "authority_ledger.db-shm"}:
            failures.append("LISTING:" + AUTHORITY_STATE)
    witness = system.path(WITNESS_STATE)
    if at_stage(stage, "P1B-9a") and witness.is_dir() and not witness.is_symlink():
        names = {entry.name for entry in witness.iterdir()}
        allowed = {"witness.lock"} if not at_stage(stage, "P1B-9b") else {
            "witness.lock", "witness.json", "chain", "authorizations"}
        if not names <= allowed or (at_stage(stage, "P1B-9b") and not {"witness.json", "chain"} <= names):
            failures.append("LISTING:" + WITNESS_STATE)
    return failures


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
    # Fresh install: the keygen plus every other fixed CLI the release ships (each created, never replaced).
    for member, target in CLI_TARGETS.items():
        source = system.path(f"{RELEASES}/{sha}/{member}")
        if member == CLI_PATH or source.is_file():
            _write_new(system, system.path(target), source.read_bytes(), 0o755)
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


def stage_custody(system: System, sha: str) -> dict:
    """L2c (B1b-3e RR-26): create the empty PREPARED and RETIRED custody directories.

    Requires the exact L2b.2 POST (the successor-capable release installed and
    the CURRENT blob present). Creates `/etc/lilith-authority-custody`,
    `prepared/`, and `retired/`, each root:root 0700, and nothing else. It
    never writes, moves, or deletes a credential blob, and a directory that
    already exists is a collision (the L2b.2 POST requires all three absent).
    """
    require_dev_root(system)
    _require(status(system, "L2b.2", sha))
    for directory in CUSTODY_DIRS:
        _mkdir(system, directory, 0o700)
    for directory in (CUSTODY_ROOT, "/etc"):
        _fsync_directory(system, directory)
    return status(system, "L2c", sha)


def _fsync_directory(system: System, absolute: str) -> None:
    fd = os.open(system.path(absolute), os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


# ===================================== B1b-3e PR-1S: UPGRADE_EXISTING_DEV_SYNTHETIC ===

BASELINE_TYPE = "LILITH_AUTHORITY_DEV_UPGRADE_BASELINE"
BASELINE_FIELDS = frozenset({"baselineType", "schemaVersion", "oldRelease", "currentBlob", "hostKey",
                             "signerAccount"})
IDENTITY_FIELDS = ("device", "inode", "size", "uid", "gid", "mode", "mtimeNs", "ctimeNs")

# Closed upgrade states (preflight §7.2; prompt §40). No fuzzy success.
FRESH_ABSENT = "FRESH_ABSENT"
EXISTING_ACCEPTED_OLD_RELEASE = "EXISTING_ACCEPTED_OLD_RELEASE"
STAGED_NEW_RELEASE = "STAGED_NEW_RELEASE"
SELECTED_NEW_RELEASE = "SELECTED_NEW_RELEASE"
UNITS_UPDATED = "UNITS_UPDATED"            # files replaced; daemon-reload pending (owner command)
UNITS_RELOADED = "UNITS_RELOADED"
CLI_UPDATED = "CLI_UPDATED"
COMPLETE_NEW_RELEASE = "COMPLETE_NEW_RELEASE"
INCONSISTENT = "INCONSISTENT"
UPGRADE_STATES = (FRESH_ABSENT, EXISTING_ACCEPTED_OLD_RELEASE, STAGED_NEW_RELEASE, SELECTED_NEW_RELEASE,
                  UNITS_UPDATED, UNITS_RELOADED, CLI_UPDATED, COMPLETE_NEW_RELEASE, INCONSISTENT)


def _identity(system: System, absolute: str) -> dict | None:
    """lstat identity only (no read): the host key is never opened."""
    try:
        meta = os.lstat(system.path(absolute))
    except FileNotFoundError:
        return None
    return {"kind": "file" if stat.S_ISREG(meta.st_mode) else "other", "device": meta.st_dev, "inode": meta.st_ino,
            "size": meta.st_size, "uid": meta.st_uid, "gid": meta.st_gid,
            "mode": format(stat.S_IMODE(meta.st_mode), "04o"), "mtimeNs": meta.st_mtime_ns,
            "ctimeNs": meta.st_ctime_ns}


def current_blob_observation(system: System) -> dict | None:
    """CURRENT: lstat identity plus the ciphertext SHA-256 (never decrypted)."""
    facts = _identity(system, CREDENTIAL)
    if facts is None:
        return None
    facts["sha256"] = _file_sha(system, CREDENTIAL)
    return facts


def observe_baseline(system: System, old: str) -> dict:
    """P1A-0 (read-only): what the owner records as the accepted baseline.
    The accepted KNOWN values are compared here; numeric identities are
    UNKNOWN_UNTIL_LIVE_PREFLIGHT until this observation records them."""
    report = status(system, "L2b.2", old)
    account = account_facts(system)
    return {
        "baselineType": BASELINE_TYPE, "schemaVersion": 1, "oldRelease": old,
        "currentBlob": current_blob_observation(system), "hostKey": _identity(system, HOST_KEY),
        "signerAccount": None if account is None else {"uid": account["uid"], "gid": account["gid"]},
        "statusL2b2Old": report["result"], "statusFailures": report["failures"],
        "acceptedOldRelease": old == ACCEPTED_OLD_RELEASE,
        "acceptedCurrentSha256": (current_blob_observation(system) or {}).get("sha256") == ACCEPTED_CURRENT_SHA256,
    }


def parse_baseline(path: Path, old: str) -> dict:
    """The owner-recorded accepted baseline: closed fields, exact KNOWN values."""
    target = Path(path)
    if target.is_symlink() or not target.is_file() or target.stat().st_size > 64 * 1024:
        raise InstallError("BASELINE_UNREADABLE")
    try:
        value = json.loads(target.read_bytes())
    except ValueError as exc:
        raise InstallError("BASELINE_UNREADABLE") from exc
    if not isinstance(value, dict) or set(value) != BASELINE_FIELDS or value["baselineType"] != BASELINE_TYPE \
            or value["schemaVersion"] != 1:
        raise InstallError("BASELINE_MALFORMED")
    if value["oldRelease"] != old or old != ACCEPTED_OLD_RELEASE:
        raise InstallError("BASELINE_OLD_RELEASE_NOT_ACCEPTED")
    blob, key, account = value["currentBlob"], value["hostKey"], value["signerAccount"]
    for item, fields in ((blob, IDENTITY_FIELDS + ("kind", "sha256")), (key, IDENTITY_FIELDS + ("kind",)),
                         (account, ("uid", "gid"))):
        if not isinstance(item, dict) or set(item) != set(fields):
            raise InstallError("BASELINE_MALFORMED")
    if blob["sha256"] != ACCEPTED_CURRENT_SHA256:
        raise InstallError("BASELINE_CURRENT_SHA256_NOT_ACCEPTED")
    return value


def preservation_failures(system: System, baseline: dict) -> list[str]:
    """Preflight §6.2 / §24: CURRENT byte-identical and identity-identical,
    credstore = CURRENT only, host key identity unchanged (never read), the
    signer account adopted unchanged, no PREPARED / RETIRED / K-WIT blob,
    and no custody root before the `custody` stage runs."""
    failures = []
    current = current_blob_observation(system)
    expected = baseline["currentBlob"]
    if current is None:
        failures.append("PRESERVATION:CURRENT_MISSING")
    else:
        for name in IDENTITY_FIELDS + ("kind", "sha256"):
            if current[name] != expected[name]:
                failures.append("PRESERVATION:CURRENT_" + name.upper())
    store = system.path(CREDSTORE)
    if not store.is_dir() or sorted(entry.name for entry in store.iterdir()) != [Path(CREDENTIAL).name]:
        failures.append("PRESERVATION:CREDSTORE_NOT_EXACTLY_CURRENT")
    key = _identity(system, HOST_KEY)
    if key is None or any(key[name] != baseline["hostKey"][name] for name in IDENTITY_FIELDS + ("kind",)):
        failures.append("PRESERVATION:HOST_KEY_IDENTITY")
    account = account_facts(system)
    if account is None or (account["uid"], account["gid"]) != (baseline["signerAccount"]["uid"],
                                                                baseline["signerAccount"]["gid"]):
        failures.append("PRESERVATION:SIGNER_ACCOUNT")
    for directory in (PREPARED_DIR, RETIRED_DIR):
        path = system.path(directory)
        if path.is_dir() and any(path.iterdir()):
            failures.append("PRESERVATION:CUSTODY_SLOT_NOT_EMPTY:" + directory)
    for forbidden in (WITNESS_BLOB, SUPERSEDED_WITNESS_CREDSTORE):
        if os.path.lexists(system.path(forbidden)):
            failures.append("PRESERVATION:UNEXPECTED_WITNESS_CREDENTIAL")
    return failures


def _release_entries(system: System) -> list[str]:
    path = system.path(RELEASES)
    return sorted(entry.name for entry in path.iterdir()) if path.is_dir() and not path.is_symlink() else []


def _all_equal(system: System, sha: str, targets: dict[str, str]) -> bool:
    """Every target exists and equals `sha`'s member. Members identical in
    OLD and NEW satisfy both sides; a mixed set satisfies neither."""
    return all(_file_sha(system, target) is not None
               and _file_sha(system, target) == _file_sha(system, f"{RELEASES}/{sha}/{member}")
               for member, target in targets.items())


def _cli_side(system: System, sha: str) -> bool | None:
    """True when every CLI target equals `sha`'s CLI set exactly (absent when not shipped)."""
    if _file_sha(system, KEYGEN_CLI) != _file_sha(system, f"{RELEASES}/{sha}/{CLI_PATH}"):
        return False
    return not cli_set_failures(system, sha)


def upgrade_status(system: System, old: str, new: str, baseline: dict | None) -> dict:
    """Read-only classification of the existing-host upgrade. Mixed or
    unknown states are INCONSISTENT (STOP); nothing is ever repaired."""
    for sha in (old, new):
        if not SHA40.fullmatch(sha):
            raise InstallError("CANDIDATE_SHA_REQUIRED")
    if old == new:
        raise InstallError("UPGRADE_SAME_RELEASE")
    observed: dict[str, Any] = {"releaseEntries": _release_entries(system)}
    failures = [] if baseline is None else preservation_failures(system, baseline)
    if not system.path(OPT).exists():
        state = FRESH_ABSENT
    else:
        entries = observed["releaseEntries"]
        target = os.readlink(system.path(CURRENT)) if system.path(CURRENT).is_symlink() else None
        observed["currentTarget"] = target
        units_old, units_new = _all_equal(system, old, UNIT_TARGETS), _all_equal(system, new, UNIT_TARGETS)
        cli_old, cli_new = _cli_side(system, old), _cli_side(system, new)
        reload_state = [_unit_state(system, unit) for unit in AUTHORITY_UNITS]
        reloaded = all((s["LoadState"], s["NeedDaemonReload"]) == ("loaded", "no") for s in reload_state)
        idle = all(s["ActiveState"] in (None, "inactive") and s["UnitFileState"] in (None, "", "static")
                   for s in reload_state)
        observed.update(unitsOld=units_old, unitsNew=units_new, cliOld=cli_old, cliNew=cli_new, reloaded=reloaded,
                        idle=idle)
        key = (tuple(entries), target, units_old, units_new, cli_old, cli_new, reloaded)
        both = tuple(sorted((old, new)))
        table = {
            ((old,), f"releases/{old}", True, False, True, False, True): EXISTING_ACCEPTED_OLD_RELEASE,
            (both, f"releases/{old}", True, False, True, False, True): STAGED_NEW_RELEASE,
            (both, f"releases/{new}", True, False, True, False, True): SELECTED_NEW_RELEASE,
            (both, f"releases/{new}", False, True, True, False, False): UNITS_UPDATED,
            (both, f"releases/{new}", False, True, True, False, True): UNITS_RELOADED,
            (both, f"releases/{new}", False, True, False, True, True): CLI_UPDATED,
            ((new,), f"releases/{new}", False, True, False, True, True): COMPLETE_NEW_RELEASE,
        }
        # Identical OLD/NEW unit sets would make the unit step undecidable; the
        # reviewed NEW signer unit differs (InaccessiblePaths), so both-true is
        # never this upgrade and is refused.
        state = table.get(key, INCONSISTENT) if idle and not (units_old and units_new) else INCONSISTENT
    return {"schemaVersion": 1, "mode": "UPGRADE_EXISTING_DEV_SYNTHETIC", "oldRelease": old, "newRelease": new,
            "state": state, "failures": failures, "observed": observed,
            "result": "PASS" if state != INCONSISTENT and not failures else "FAIL"}


def _require_upgrade(system: System, old: str, new: str, baseline: dict, allowed: tuple[str, ...]) -> dict:
    require_dev_root(system)
    report = upgrade_status(system, old, new, baseline)
    if report["failures"]:
        raise InstallError("PRESERVATION_FAILED:" + ",".join(report["failures"]))
    if report["state"] not in allowed:
        raise InstallError("UPGRADE_STATE:" + report["state"])
    for path in DEFERRED_PATHS + tuple(CUSTODY_DIRS):
        if os.path.lexists(system.path(path)):
            raise InstallError("UPGRADE_UNEXPECTED_PRESENT:" + path)
    return report


def _post(system: System, old: str, new: str, baseline: dict, expected: str | tuple[str, ...], mutation: str) -> dict:
    report = upgrade_status(system, old, new, baseline)
    report["mutation"] = mutation
    if report["state"] not in ((expected,) if isinstance(expected, str) else expected):
        report["result"] = "FAIL"
        report["failures"].append("UPGRADE_POST_STATE:" + report["state"])
    return report


def release_tree_failures(system: System, sha: str) -> list[str]:
    """§23 full tree check: every manifest file present with its bytes;
    root-owned; dirs 0755; files 0644/0755; no symlink; nothing extra outside venv/."""
    top = system.path(f"{RELEASES}/{sha}")
    manifest_path = top / MANIFEST
    if top.is_symlink() or not top.is_dir() or manifest_path.is_symlink() or not manifest_path.is_file():
        return ["TREE_MANIFEST_MISSING"]
    try:
        manifest = json.loads(manifest_path.read_bytes())
        expected = {item["path"]: item["sha256"] for item in manifest["files"]}
    except (ValueError, KeyError, TypeError):
        return ["TREE_MANIFEST_MALFORMED"]
    if manifest.get("candidateSha") != sha or manifest_path.read_bytes() != canonical(manifest):
        return ["TREE_MANIFEST_MISMATCH"]
    expected[MANIFEST] = digest(manifest_path.read_bytes())
    failures, seen = [], set()
    for directory, subdirs, files in os.walk(top, followlinks=False):
        here = Path(directory)
        if here == top and "venv" in subdirs:
            subdirs.remove("venv")
        for name in subdirs + files:
            path = here / name
            relative = path.relative_to(top).as_posix()
            meta = os.lstat(path)
            if (meta.st_uid, meta.st_gid) != (system.owner_uid, system.owner_gid):
                failures.append("TREE_OWNERSHIP:" + relative)
            if stat.S_ISLNK(meta.st_mode):
                failures.append("TREE_SYMLINK:" + relative)
            elif stat.S_ISDIR(meta.st_mode):
                if stat.S_IMODE(meta.st_mode) != 0o755:
                    failures.append("TREE_MODE:" + relative)
            elif relative not in expected:
                failures.append("TREE_EXTRA_FILE:" + relative)
            else:
                seen.add(relative)
                if stat.S_IMODE(meta.st_mode) not in (0o644, 0o755) or digest(path.read_bytes()) != expected[relative]:
                    failures.append("TREE_FILE:" + relative)
    failures.extend("TREE_FILE_MISSING:" + name for name in sorted(set(expected) - seen))
    return failures


def stage_upgrade_stage(system: System, old: str, new: str, archive: Path, attestation: Path,
                        baseline: dict) -> dict:
    """M-A1: stage NEW beside OLD. Idempotent: a complete, verifying NEW tree
    with the selector still at OLD returns ALREADY_COMPLETE."""
    report = _require_upgrade(system, old, new, baseline, (EXISTING_ACCEPTED_OLD_RELEASE, STAGED_NEW_RELEASE))
    if report["state"] == STAGED_NEW_RELEASE:
        failures = release_tree_failures(system, new)
        if failures:
            raise InstallError("STAGED_TREE_INVALID:" + ",".join(failures))
        return _post(system, old, new, baseline, STAGED_NEW_RELEASE, "ALREADY_COMPLETE")
    _require(status(system, "L2b.2", old))
    manifest, payloads = verify_archive(archive, attestation, new)
    staging = system.path(f"{RELEASES}/.{new}.staging")
    if os.path.lexists(staging):
        raise InstallError("RELEASE_STAGING_COLLISION")
    staging.mkdir(mode=0o700)
    for relative, data in sorted({**payloads, MANIFEST: canonical(manifest)}.items()):
        target = staging.joinpath(*relative.split("/"))
        target.parent.mkdir(parents=True, exist_ok=True, mode=0o755)
        _write_new(system, target, data, 0o755 if relative in CLI_TARGETS else 0o644)
    system.fixed("/usr/bin/python3", "-m", "venv", str(staging / "venv"))
    system.fixed(str(staging / "venv/bin/python"), "-m", "pip", "install", "--no-index", "--no-input",
                 "--disable-pip-version-check", "--require-hashes", "--find-links", str(staging / "wheels"),
                 "-r", str(staging / "requirements.lock"))
    _normalize_tree(system, staging)
    system.fixed("/usr/sbin/runuser", "-u", SERVICE_USER, "--", str(staging / "venv/bin/python"), "-I", "-B", "-c",
                 "import sys; sys.path.insert(0, sys.argv[1]); import lilith_authority_dev.server, "
                 "lilith_recovery_witness.server, lilith_authority_root.cli", str(staging), cwd=staging)
    staging.rename(system.path(f"{RELEASES}/{new}"))
    _fsync_directory(system, RELEASES)
    failures = release_tree_failures(system, new)
    report = _post(system, old, new, baseline, STAGED_NEW_RELEASE, "STAGED")
    if failures:
        report["result"] = "FAIL"
        report["failures"].extend(failures)
    return report


def stage_upgrade_select(system: System, old: str, new: str, baseline: dict) -> dict:
    """M-A2: `current -> releases/<NEW>` by symlink(tmp) + rename (atomic)."""
    report = _require_upgrade(system, old, new, baseline, (STAGED_NEW_RELEASE, SELECTED_NEW_RELEASE))
    if report["state"] == SELECTED_NEW_RELEASE:
        return _post(system, old, new, baseline, SELECTED_NEW_RELEASE, "ALREADY_COMPLETE")
    failures = release_tree_failures(system, new)
    if failures:
        raise InstallError("STAGED_TREE_INVALID:" + ",".join(failures))
    tmp = system.path(f"{OPT}/.current.tmp")
    if os.path.lexists(tmp):
        raise InstallError("SELECTOR_STAGING_COLLISION")
    os.symlink(f"releases/{new}", tmp)
    if system.chown:
        os.lchown(tmp, 0, 0)
    os.rename(tmp, system.path(CURRENT))
    _fsync_directory(system, OPT)
    return _post(system, old, new, baseline, SELECTED_NEW_RELEASE, "SELECTED")


def _replace_file(system: System, absolute: str, data: bytes, mode: int) -> None:
    """tmp (O_EXCL) -> fsync -> rename over -> directory fsync. Never a window
    with no file, never a partial file."""
    target = system.path(absolute)
    tmp = target.with_name(f".{target.name}.lilith-upgrade.tmp")
    if os.path.lexists(tmp):
        raise InstallError("REPLACE_STAGING_COLLISION:" + absolute)
    _write_new(system, tmp, data, mode)
    os.rename(tmp, target)
    _fsync_directory(system, str(Path(absolute).parent))


def stage_upgrade_units(system: System, old: str, new: str, baseline: dict) -> dict:
    """M-A3: replace the signer unit, socket, and tmpfiles files with NEW's.
    The daemon-reload is the owner's separate command (M-A4)."""
    report = _require_upgrade(system, old, new, baseline, (SELECTED_NEW_RELEASE, UNITS_UPDATED, UNITS_RELOADED))
    if report["state"] in (UNITS_UPDATED, UNITS_RELOADED):
        return _post(system, old, new, baseline, report["state"], "ALREADY_COMPLETE")
    for member, target in UNIT_TARGETS.items():
        _replace_file(system, target, system.path(f"{RELEASES}/{new}/{member}").read_bytes(), 0o644)
    # systemd reports NeedDaemonReload=yes for the changed service file until the
    # owner's daemon-reload (M-A4); either state is this stage's POST.
    return _post(system, old, new, baseline, (UNITS_UPDATED, UNITS_RELOADED), "REPLACED")


def stage_upgrade_cli(system: System, old: str, new: str, baseline: dict) -> dict:
    """M-A5: replace the keygen; create each new fixed CLI (a collision with
    other bytes is refused)."""
    report = _require_upgrade(system, old, new, baseline, (UNITS_RELOADED, CLI_UPDATED))
    if report["state"] == CLI_UPDATED:
        return _post(system, old, new, baseline, CLI_UPDATED, "ALREADY_COMPLETE")
    for member, target in CLI_TARGETS.items():
        data = system.path(f"{RELEASES}/{new}/{member}").read_bytes()
        if member == CLI_PATH:
            _replace_file(system, target, data, 0o755)
            continue
        existing = _file_sha(system, target)
        if existing is None and not os.path.lexists(system.path(target)):
            _write_new(system, system.path(target), data, 0o755)
        elif existing != digest(data):
            raise InstallError("CLI_COLLISION:" + target)
    _fsync_directory(system, "/usr/local/sbin")
    return _post(system, old, new, baseline, CLI_UPDATED, "REPLACED")


def stage_upgrade_retire_old(system: System, old: str, new: str, baseline: dict) -> dict:
    """M-A6 (RR-25): remove `releases/<OLD>` only after NEW is selected, its
    units reloaded, its CLIs installed, and its tree verifies. Release
    rollback != authority rollback. POST: `status --expect L2b.2 <NEW>`."""
    report = _require_upgrade(system, old, new, baseline, (CLI_UPDATED, COMPLETE_NEW_RELEASE))
    if report["state"] == CLI_UPDATED:
        failures = release_tree_failures(system, new)
        if failures:
            raise InstallError("NEW_TREE_INVALID:" + ",".join(failures))
        doomed = system.path(f"{RELEASES}/{old}")
        if doomed.is_symlink() or not doomed.is_dir() or os.readlink(system.path(CURRENT)) != f"releases/{new}":
            raise InstallError("RETIRE_TARGET_UNSAFE")
        import shutil

        shutil.rmtree(doomed)
        _fsync_directory(system, RELEASES)
        mutation = "RETIRED"
    else:
        mutation = "ALREADY_COMPLETE"
    report = _post(system, old, new, baseline, COMPLETE_NEW_RELEASE, mutation)
    final = status(system, "L2b.2", new)
    report["statusL2b2New"] = final["result"]
    if final["result"] != "PASS":
        report["result"] = "FAIL"
        report["failures"].extend(final["failures"])
    return report


# ------------------------------------------------ PR-1A: witness, skeleton ---

def stage_witness_account(system: System, sha: str) -> dict:
    """P1A-8a (S-4): the distinct witness identity. Never corrects an existing one."""
    require_dev_root(system)
    _require(status(system, "L2c", sha))
    system.fixed("/usr/sbin/useradd", "--system", "--user-group", "--no-create-home", "--home-dir", NO_HOME,
                 "--shell", NOLOGIN, WITNESS_USER)
    return status(system, "P1A-8a", sha)


def stage_witness_units(system: System, sha: str) -> dict:
    """P1A-8b (S-8): install the witness unit, sockets, tmpfiles (O_EXCL; no
    reload, no enable, no start)."""
    require_dev_root(system)
    _require(status(system, "P1A-8a", sha))
    for member, target in WITNESS_UNIT_TARGETS.items():
        _write_new(system, system.path(target), system.path(f"{RELEASES}/{sha}/{member}").read_bytes(), 0o644)
    return status(system, "P1A-8b", sha)


def stage_skeleton(system: System, sha: str) -> dict:
    """P1A-9 (M-A10): empty root-owned skeleton directories only."""
    require_dev_root(system)
    _require(status(system, "P1A-8c", sha))
    for directory, mode in SKELETON_DIRS:
        _mkdir(system, directory, mode)
    for parent in ("/etc", AUTHORITY_CONFIG, WITNESS_CREDENTIAL_PARENT, "/var/lib", HOLD_PARENT):
        _fsync_directory(system, parent)
    return status(system, "P1A-9", sha)


# ------------------------------------------- PR-1B: public on-host inputs ---

def _refuse_float(_value: str) -> float:
    raise ValueError("floats are not part of any stored document")


def _canonical_document(path: Path) -> bytes:
    """A public JSON document in its one stored form (sorted keys, no
    whitespace, ASCII, no floats). Content is judged by the witness and the
    root verifier; this only refuses anything that is not a plain document."""
    source = Path(path)
    if source.is_symlink() or not source.is_file() or source.stat().st_size > 64 * 1024:
        raise InstallError("INPUT_DOCUMENT_UNREADABLE")
    raw = source.read_bytes()
    try:
        value = json.loads(raw.decode("ascii"), parse_float=_refuse_float)
    except (UnicodeError, ValueError) as exc:
        raise InstallError("INPUT_DOCUMENT_MALFORMED") from exc
    if not isinstance(value, dict) or value.get("environment") != "dev":
        raise InstallError("INPUT_DOCUMENT_MALFORMED")
    data = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")
    if data != raw:
        raise InstallError("INPUT_DOCUMENT_NOT_CANONICAL")
    return data


def _install_once(system: System, absolute: str, data: bytes) -> None:
    _write_new(system, system.path(absolute), data, 0o644)
    _fsync_directory(system, str(Path(absolute).parent))


def stage_install_anchors(system: System, sha: str, registry_root: Path, witness_anchor: Path) -> dict:
    """P1B-4 (M-B4): the two public trust anchors, write-once."""
    require_dev_root(system)
    _require(status(system, "P1B-2", sha))
    root_doc, anchor_doc = _canonical_document(registry_root), _canonical_document(witness_anchor)
    if set(json.loads(root_doc)) != {"schemaVersion", "rootKeyId", "environment", "algorithm", "publicKey"} or \
            set(json.loads(anchor_doc)) != {"schemaVersion", "witnessKeyId", "environment", "algorithm", "publicKey"}:
        raise InstallError("ANCHOR_SHAPE")
    _install_once(system, REGISTRY_ROOT_ANCHOR, root_doc)
    _install_once(system, WITNESS_ANCHOR, anchor_doc)
    return status(system, "P1B-4", sha)


def stage_install_registry(system: System, sha: str, registry: Path) -> dict:
    """P1B-5 (M-B5): one public K-ROOT registry generation, write-once."""
    require_dev_root(system)
    _require(status(system, "P1B-4", sha))
    document = _canonical_document(registry)
    version = json.loads(document).get("registryVersion")
    if type(version) is not int or version < 1:
        raise InstallError("REGISTRY_SHAPE")
    _install_once(system, f"{REGISTRY_DIR}/authority-registry.v{version}.json", document)
    return status(system, "P1B-5", sha)


def stage_install_owner_inputs(system: System, sha: str, pin: Path, register: Path) -> dict:
    """P1B-8 (M-B8): the on-host copies of the owner pin and register, write-once."""
    require_dev_root(system)
    _require(status(system, "P1B-6", sha))
    pin_doc, register_doc = _canonical_document(pin), _canonical_document(register)
    if set(json.loads(pin_doc)) != {"pinType", "schemaVersion", "environment", "genesisWitnessDigest"} or \
            set(json.loads(register_doc)) != {"registerType", "schemaVersion", "environment", "authorizations",
                                              "headRegistries"}:
        raise InstallError("OWNER_INPUT_SHAPE")
    _install_once(system, GENESIS_PIN_COPY, pin_doc)
    _install_once(system, AUTHORIZATION_REGISTER_COPY, register_doc)
    return status(system, "P1B-8", sha)


def stage_witness_state(system: System, sha: str) -> dict:
    """P1B-9a (pre-start): the witness state directory, setgid so every entry
    the witness creates is group-readable by the signer only."""
    require_dev_root(system)
    _require(status(system, "P1B-8", sha))
    witness, signer = system.user(WITNESS_USER), system.group(SERVICE_GROUP)
    if witness is None or signer is None:
        raise InstallError("ACCOUNT_ABSENT")
    path = system.path(WITNESS_STATE)
    path.mkdir(mode=0o750)
    if system.chown:
        os.chown(path, witness.pw_uid, signer.gr_gid)
    os.chmod(path, 0o2750)
    _fsync_directory(system, "/var/lib")
    return status(system, "P1B-9a", sha)


UPGRADE_STAGES = {"upgrade-select": stage_upgrade_select, "upgrade-units": stage_upgrade_units,
                  "upgrade-cli": stage_upgrade_cli, "upgrade-retire-old": stage_upgrade_retire_old}
PR1_STAGES = {"witness-account": stage_witness_account, "witness-units": stage_witness_units,
              "skeleton": stage_skeleton, "witness-state": stage_witness_state}


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
        elif stage == "custody" and len(rest) == 1:
            report = stage_custody(system, rest[0])
        elif stage == "upgrade-baseline" and len(rest) == 1:
            require_dev_root(system)
            report = observe_baseline(system, rest[0])
            report["result"] = "PASS" if report["statusL2b2Old"] == "PASS" else "FAIL"
        elif stage == "upgrade-status" and len(rest) == 3:
            require_dev_root(system)
            report = upgrade_status(system, rest[0], rest[1], parse_baseline(Path(rest[2]), rest[0]))
        elif stage == "upgrade-stage" and len(rest) == 5:
            report = stage_upgrade_stage(system, rest[0], rest[1], Path(rest[2]), Path(rest[3]),
                                         parse_baseline(Path(rest[4]), rest[0]))
        elif stage in UPGRADE_STAGES and len(rest) == 3:
            report = UPGRADE_STAGES[stage](system, rest[0], rest[1], parse_baseline(Path(rest[2]), rest[0]))
        elif stage in PR1_STAGES and len(rest) == 1:
            report = PR1_STAGES[stage](system, rest[0])
        elif stage == "install-anchors" and len(rest) == 3:
            report = stage_install_anchors(system, rest[0], Path(rest[1]), Path(rest[2]))
        elif stage == "install-registry" and len(rest) == 2:
            report = stage_install_registry(system, rest[0], Path(rest[1]))
        elif stage == "install-owner-inputs" and len(rest) == 3:
            report = stage_install_owner_inputs(system, rest[0], Path(rest[1]), Path(rest[2]))
        else:
            raise InstallError("USAGE")
    except InstallError as exc:
        print(f"install_authority_dev: REFUSED {exc.reason}", file=sys.stderr)
        return 2
    sys.stdout.write(json.dumps(report, sort_keys=True, indent=2) + "\n")
    return 0 if report["result"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
