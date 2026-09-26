#!/usr/bin/python3 -IB
"""LILITH 15B2b-B1b-3d L2b: DEV_SYNTHETIC OWNER_ACTOR key ceremony CLI.

Installed as `/usr/local/sbin/lilith-authority-keygen-dev` (root:root 0755)
from a verified authority release. Run only by the owner, as root, on
`lilith-dev-01`, inside the separately authorized L2b step of
docs/architecture/slice-15b2b-b1b3d-l2-custody-preparation.md. Usage:

    lilith-authority-keygen-dev actor

There is no other form. `witness` is refused (the recovery witness is a
later slice). There is no algorithm, domain, key ID, environment, path,
output, export, seed, or force option.

One run does exactly this:

1. refuses unless every precondition holds (root, isolated interpreter, DEV
   host, no active swap, the host credential key present, an empty
   root-only `/etc/credstore.encrypted`, no existing blob);
2. generates one fresh Ed25519 key in process memory (no seed);
3. serialises it as unencrypted PKCS#8 DER in memory and writes those bytes
   only to the stdin pipe of
   `/usr/bin/systemd-creds encrypt --with-key=host --name=owner-actor-signing-key - -`;
4. reads the ciphertext from that process's stdout and writes it with
   `O_EXCL` to `/etc/credstore.encrypted/lilith-authority-dev.owner-actor.cred`
   (`root:root 0600`);
5. prints one canonical JSON public publication on stdout.

Plaintext private material is never written to a file, argument, environment
variable, terminal, log, or network. It exists in this process's memory, in
the kernel pipe buffer, and in the `systemd-creds` process's memory. Process
exit and pipe closure are **not** secure erasure: memory zeroization and
remanence are NOT_PROVEN (Python bytes are immutable and cannot be wiped).
Core dumps are disabled for this process and the process is marked
non-dumpable, which narrows but does not remove that exposure.

The host-bound credential protects the blob against ordinary application and
routine-deployer access only. It is NOT whole-host or snapshot rollback
protection: a disk snapshot contains both the blob and
`/var/lib/systemd/credential.secret`. It is NOT real-owner-grade custody.

This CLI has no network access, writes no database, changes no registry,
starts or enables no unit, and never falls back to any other key.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import stat
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, NoEncryption, PrivateFormat, PublicFormat

# Fixed contract. Tests pin every value against the L1 profile and the design.
PROFILE = "DEV_SYNTHETIC"
ENVIRONMENT = "dev"
KEY_ID = "test-only.dev-synthetic.actor.b1b3d.1"
SIGNING_DOMAIN = "OWNER_ACTOR"
EVIDENCE_TYPES = ("OWNER_MEMORY_OPERATION",)
ALGORITHM = "Ed25519"
CREDENTIAL_NAME = "owner-actor-signing-key"
CREDSTORE = "/etc/credstore.encrypted"
CREDENTIAL_PATH = CREDSTORE + "/lilith-authority-dev.owner-actor.cred"
HOST_KEY = "/var/lib/systemd/credential.secret"
SYSTEMD_CREDS = "/usr/bin/systemd-creds"
ENCRYPT_ARGV = (SYSTEMD_CREDS, "encrypt", "--with-key=host", "--name=" + CREDENTIAL_NAME, "-", "-")
DEV_HOSTNAME = "lilith-dev-01"
DEV_MACHINE_ID = "ae929170e6fa4c8ab9cc7b9547238d9d"
PUBLICATION_TYPE = "LILITH_AUTHORITY_KEY_PUBLICATION"
PUBLICATION_SCHEMA_VERSION = 1
MAX_CIPHERTEXT = 64 * 1024
ENCRYPT_TIMEOUT_SECONDS = 30
FIXED_ENV = {"PATH": "/usr/sbin:/usr/bin:/sbin:/bin", "LANG": "C", "HOME": "/nonexistent"}

EXIT_REFUSED = 2
EXIT_FAILED = 3


class Refused(Exception):
    """A precondition does not hold. Nothing was generated or written."""

    def __init__(self, reason: str):
        self.reason = reason
        super().__init__(reason)


class Failed(Exception):
    """The ceremony started and did not complete. See the runbook STOP rules."""

    def __init__(self, reason: str):
        self.reason = reason
        super().__init__(reason)


def _b64u(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def canonical(value: dict) -> bytes:
    """Deterministic JSON: sorted keys, no whitespace, ASCII, one newline."""
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True) + "\n").encode("ascii")


def publication(public_key: bytes, ciphertext: bytes, machine_id: str) -> dict:
    """The public output of one ceremony. Holds no private material.

    `publicVerificationMaterial` is what a later, offline, owner-signed
    `AuthorityKeyRecordV1` needs (the registry adds its own validity,
    epoch, policy, and version fields). `custodyEvidence` records where the
    ciphertext was written and its hash; it is never registry material.
    """
    if not isinstance(public_key, bytes) or len(public_key) != 32:
        raise ValueError("public key must be 32 raw Ed25519 bytes")
    if not isinstance(ciphertext, bytes) or not 0 < len(ciphertext) <= MAX_CIPHERTEXT:
        raise ValueError("ciphertext is empty or oversized")
    return {
        "publicationType": PUBLICATION_TYPE,
        "schemaVersion": PUBLICATION_SCHEMA_VERSION,
        "profile": PROFILE,
        "publicVerificationMaterial": {
            "keyId": KEY_ID,
            "signingDomain": SIGNING_DOMAIN,
            "evidenceTypes": list(EVIDENCE_TYPES),
            "environment": ENVIRONMENT,
            "algorithm": ALGORITHM,
            "publicKey": _b64u(public_key),
            "publicKeySha256": hashlib.sha256(public_key).hexdigest(),
        },
        "custodyEvidence": {
            "credentialName": CREDENTIAL_NAME,
            "credentialPath": CREDENTIAL_PATH,
            "withKey": "host",
            "machineId": machine_id,
            "blobByteSize": len(ciphertext),
            "blobSha256": hashlib.sha256(ciphertext).hexdigest(),
        },
    }


@dataclass(frozen=True)
class Host:
    """Everything the ceremony reads from or writes to the host. Tests replace it."""

    root: Path = Path("/")
    # Owner expected on root-owned paths. Only tests change it.
    owner_uid: int = 0
    owner_gid: int = 0

    def path(self, absolute: str) -> Path:
        return self.root / absolute.lstrip("/")


def parse_argv(argv: list[str]) -> None:
    if argv == ["actor"]:
        return
    if argv == ["witness"]:
        raise Refused("WITNESS_NOT_IN_SCOPE")
    raise Refused("USAGE_ONLY_ACTOR")


def _root_owned(host: Host, path: Path, *, kind: str, mode: int, missing: str, bad: str) -> None:
    try:
        meta = os.lstat(path)
    except FileNotFoundError as exc:
        raise Refused(missing) from exc
    is_kind = stat.S_ISDIR(meta.st_mode) if kind == "dir" else stat.S_ISREG(meta.st_mode)
    if (not is_kind or (meta.st_uid, meta.st_gid) != (host.owner_uid, host.owner_gid)
            or stat.S_IMODE(meta.st_mode) != mode):
        raise Refused(bad)


def preflight(host: Host, *, euid: int, isolated: bool, hostname: str) -> str:
    """Read-only checks. Returns the machine ID. Never reads the host key."""
    if euid != 0:
        raise Refused("NOT_ROOT")
    if not isolated:
        raise Refused("INTERPRETER_NOT_ISOLATED")
    try:
        machine_id = host.path("/etc/machine-id").read_text(encoding="ascii").strip()
    except OSError as exc:
        raise Refused("NOT_DEV_HOST") from exc
    if machine_id != DEV_MACHINE_ID or hostname.split(".", 1)[0] != DEV_HOSTNAME:
        raise Refused("NOT_DEV_HOST")
    try:
        swaps = host.path("/proc/swaps").read_text(encoding="ascii").splitlines()
    except OSError as exc:
        raise Refused("SWAP_STATE_UNKNOWN") from exc
    if not swaps or any(line.strip() for line in swaps[1:]):
        raise Refused("SWAP_ACTIVE")
    _root_owned(host, host.path(HOST_KEY), kind="file", mode=0o400,
                missing="HOST_CREDENTIAL_KEY_ABSENT", bad="HOST_CREDENTIAL_KEY_CUSTODY")
    _root_owned(host, host.path(SYSTEMD_CREDS), kind="file", mode=0o755,
                missing="SYSTEMD_CREDS_ABSENT", bad="SYSTEMD_CREDS_CUSTODY")
    _root_owned(host, host.path(CREDSTORE), kind="dir", mode=0o700,
                missing="CREDSTORE_ABSENT", bad="CREDSTORE_CUSTODY")
    if os.path.lexists(host.path(CREDENTIAL_PATH)):
        raise Refused("CREDENTIAL_ALREADY_PRESENT")
    if any(host.path(CREDSTORE).iterdir()):
        raise Refused("CREDSTORE_NOT_EMPTY")
    return machine_id


def restrict_process() -> None:
    """Disable core dumps and mark the process non-dumpable (Linux)."""
    import ctypes
    import resource

    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    libc = ctypes.CDLL(None, use_errno=True)
    pr_set_dumpable = 4
    if libc.prctl(pr_set_dumpable, 0, 0, 0, 0) != 0:
        raise Refused("DUMPABLE_CONTROL_FAILED")


def systemd_encrypt(plaintext: bytes) -> bytes:
    """Plaintext goes only to the child's stdin; ciphertext comes from stdout."""
    try:
        result = subprocess.run(ENCRYPT_ARGV, input=plaintext, capture_output=True, env=FIXED_ENV,
                                timeout=ENCRYPT_TIMEOUT_SECONDS, check=False, close_fds=True)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise Failed("ENCRYPT_FAILED") from exc
    if result.returncode != 0:
        raise Failed("ENCRYPT_FAILED")  # stderr is never echoed
    return result.stdout


def write_blob(host: Host, ciphertext: bytes) -> None:
    path = host.path(CREDENTIAL_PATH)
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_CLOEXEC", 0)
    try:
        fd = os.open(path, flags, 0o600)
    except FileExistsError as exc:
        raise Failed("CREDENTIAL_ALREADY_PRESENT") from exc
    try:
        view = memoryview(ciphertext)
        while view:
            written = os.write(fd, view)
            view = view[written:]
        os.fchmod(fd, 0o600)
        os.fsync(fd)
    finally:
        os.close(fd)
    directory = os.open(host.path(CREDSTORE), os.O_RDONLY)
    try:
        os.fsync(directory)
    finally:
        os.close(directory)


def ceremony(host: Host, machine_id: str, *,
             key_factory: Callable[[], Ed25519PrivateKey] = Ed25519PrivateKey.generate,
             encrypt: Callable[[bytes], bytes] = systemd_encrypt) -> dict:
    key = key_factory()
    if not isinstance(key, Ed25519PrivateKey):
        raise Failed("KEY_FACTORY_INVALID")
    public = key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
    plaintext = key.private_bytes(Encoding.DER, PrivateFormat.PKCS8, NoEncryption())
    del key  # releases this reference only; zeroization is NOT_PROVEN
    try:
        ciphertext = encrypt(plaintext)
        if not isinstance(ciphertext, bytes) or not 0 < len(ciphertext) <= MAX_CIPHERTEXT:
            raise Failed("CIPHERTEXT_INVALID")
        if plaintext in ciphertext or _b64u(plaintext).encode() in ciphertext \
                or base64.b64encode(plaintext) in ciphertext:
            raise Failed("CIPHERTEXT_CONTAINS_PLAINTEXT")
    finally:
        del plaintext
    write_blob(host, ciphertext)
    return publication(public, ciphertext, machine_id)


def main(argv: list[str] | None = None, *, host: Host = Host()) -> int:
    try:
        parse_argv(sys.argv[1:] if argv is None else argv)
        machine_id = preflight(host, euid=os.geteuid(), isolated=bool(sys.flags.isolated),
                               hostname=os.uname().nodename)
        restrict_process()
    except Refused as refused:
        print(f"lilith-authority-keygen-dev: REFUSED {refused.reason}", file=sys.stderr)
        return EXIT_REFUSED
    try:
        result = ceremony(host, machine_id)
    except Failed as failed:
        print(f"lilith-authority-keygen-dev: FAILED {failed.reason}", file=sys.stderr)
        return EXIT_FAILED
    sys.stdout.buffer.write(canonical(result))
    sys.stdout.flush()
    return 0


if __name__ == "__main__":
    sys.exit(main())
