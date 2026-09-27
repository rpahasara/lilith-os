#!/usr/bin/python3 -IB
"""LILITH 15B2b-B1b-3d L2b / B1b-3e SW-2: DEV_SYNTHETIC OWNER_ACTOR key ceremony CLI.

Installed as `/usr/local/sbin/lilith-authority-keygen-dev` (root:root 0755)
from a verified authority release. Run only by the owner, as root, on
`lilith-dev-01`, inside a separately authorized ceremony step. Usage:

    lilith-authority-keygen-dev actor
    lilith-authority-keygen-dev successor <N>

There are exactly two forms. `witness` is refused (the recovery witness is a
later slice). There is no algorithm, domain, key ID, environment, path,
output, export, seed, or force option. The only variable input anywhere is
the successor ordinal `N` (decimal, no leading zero, 2..9999).

`actor` (B1b-3d L2b, docs/architecture/slice-15b2b-b1b3d-l2-custody-preparation.md)
is the initial custody form, unchanged. `successor <N>` (B1b-3e Source Prep B,
docs/architecture/slice-15b2b-b1b3e-source-prep-b-successor-custody.md) is
the closed side-by-side successor form: it derives
`keyId = test-only.dev-synthetic.actor.b1b3e.<N>` and
`ceremonyId = dev-synthetic.owner-actor.successor.<N>` from N alone, writes
only the PREPARED slot, never writes CURRENT or RETIRED, never mutates an
existing PREPARED blob, and proves CURRENT unchanged before and after. It
never reads or judges authority state: the successor key is KEY_UNKNOWN
until a witnessed K-ROOT head names it.

    credential exists   != authority
    PREPARED successor  != current successor
    filesystem path     != authority

One `actor` run does exactly this:

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

One `successor <N>` run is the same pipeline with a different fixed target.
Its preflight also requires: the credstore holds exactly the CURRENT slot (a
root:root 0600 regular file, observed "before"); the custody root and its
`prepared/` and `retired/` directories are root:root 0700 and not symlinks,
and the two slot directories are empty; and the credstore, `prepared/`, and
`retired/` report one `st_dev` (every later cutover is a same-filesystem
rename). The blob is created `O_EXCL|O_NOFOLLOW` through a descriptor of the
PREPARED directory; file and directory are fsynced; CURRENT is observed
again, and any change of identity, owner, mode, size, or SHA-256 is `FAILED
CURRENT_CHANGED` with nothing printed. A PREPARED blob left by a failed run is
an abandoned successor: its ordinal is burned and the blob is destroyed,
never reused.

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
import re
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
# B1b-3e Source Prep B (RR-11-D1, RR-11-D2, RR-26). The runtime credential
# name above never changes; only the blob and its slot role rotate.
SUCCESSOR_KEY_ID_PREFIX = "test-only.dev-synthetic.actor.b1b3e."
SUCCESSOR_CEREMONY_ID_PREFIX = "dev-synthetic.owner-actor.successor."
SUCCESSOR_ORDINAL_MIN = 2
SUCCESSOR_ORDINAL_MAX = 9999
_ORDINAL_TEXT = re.compile(r"[1-9][0-9]{0,3}\Z")
SLOT_NAME = "lilith-authority-dev.owner-actor.cred"
CUSTODY_ROOT = "/etc/lilith-authority-custody"
PREPARED_DIR = CUSTODY_ROOT + "/prepared"
RETIRED_DIR = CUSTODY_ROOT + "/retired"
PREPARED_PATH = PREPARED_DIR + "/" + SLOT_NAME
RETIRED_PATH = RETIRED_DIR + "/" + SLOT_NAME
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


# ------------------------------------------------------- successor identity ---

def _ordinal(value: object) -> int:
    if type(value) is not int or not SUCCESSOR_ORDINAL_MIN <= value <= SUCCESSOR_ORDINAL_MAX:
        raise ValueError("successor ordinal out of range")
    return value


def successor_key_id(ordinal: int) -> str:
    """RR-11-D1: the only keyId a successor ordinal can produce."""
    return SUCCESSOR_KEY_ID_PREFIX + str(_ordinal(ordinal))


def successor_ceremony_id(ordinal: int) -> str:
    """RR-11-D1: the only ceremonyId a successor ordinal can produce (never printed)."""
    return SUCCESSOR_CEREMONY_ID_PREFIX + str(_ordinal(ordinal))


def successor_ordinal(key_id: object) -> int | None:
    """The ordinal a successor keyId was derived from, or None."""
    if not isinstance(key_id, str) or not key_id.startswith(SUCCESSOR_KEY_ID_PREFIX):
        return None
    text = key_id[len(SUCCESSOR_KEY_ID_PREFIX):]
    if not text.isascii() or _ORDINAL_TEXT.fullmatch(text) is None:
        return None
    value = int(text)
    return value if SUCCESSOR_ORDINAL_MIN <= value <= SUCCESSOR_ORDINAL_MAX else None


def publication(public_key: bytes, ciphertext: bytes, machine_id: str, *, key_id: str = KEY_ID,
                credential_path: str = CREDENTIAL_PATH) -> dict:
    """The public output of one ceremony. Holds no private material.

    `publicVerificationMaterial` is what a later, offline, owner-signed
    `AuthorityKeyRecordV1` needs (the registry adds its own validity,
    epoch, policy, and version fields). `custodyEvidence` records where the
    ciphertext was written and its hash; it is never registry material.
    Both forms emit the unchanged v1 shape: a successor differs only in its
    derived `keyId` and in `credentialPath`, which records where the keygen
    wrote the blob (PREPARED), never its later slot role.
    """
    if not isinstance(public_key, bytes) or len(public_key) != 32:
        raise ValueError("public key must be 32 raw Ed25519 bytes")
    if not isinstance(ciphertext, bytes) or not 0 < len(ciphertext) <= MAX_CIPHERTEXT:
        raise ValueError("ciphertext is empty or oversized")
    if (key_id, credential_path) != (KEY_ID, CREDENTIAL_PATH) and \
            (successor_ordinal(key_id) is None or credential_path != PREPARED_PATH):
        raise ValueError("publication identity is not one of the two closed forms")
    return {
        "publicationType": PUBLICATION_TYPE,
        "schemaVersion": PUBLICATION_SCHEMA_VERSION,
        "profile": PROFILE,
        "publicVerificationMaterial": {
            "keyId": key_id,
            "signingDomain": SIGNING_DOMAIN,
            "evidenceTypes": list(EVIDENCE_TYPES),
            "environment": ENVIRONMENT,
            "algorithm": ALGORITHM,
            "publicKey": _b64u(public_key),
            "publicKeySha256": hashlib.sha256(public_key).hexdigest(),
        },
        "custodyEvidence": {
            "credentialName": CREDENTIAL_NAME,
            "credentialPath": credential_path,
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
    # `st_dev` of a slot directory. Only tests replace it, to model a mount
    # boundary that a temporary directory cannot have.
    device_of: Callable[[Path], int] | None = None

    def path(self, absolute: str) -> Path:
        return self.root / absolute.lstrip("/")

    def device(self, path: Path) -> int:
        return os.lstat(path).st_dev if self.device_of is None else self.device_of(path)


ACTOR = "actor"
SUCCESSOR = "successor"


@dataclass(frozen=True)
class Form:
    """The parsed invocation: `actor`, or `successor` with its ordinal."""

    kind: str
    ordinal: int | None = None


def parse_argv(argv: list[str]) -> Form:
    if argv == [ACTOR]:
        return Form(ACTOR)
    if argv == ["witness"]:
        raise Refused("WITNESS_NOT_IN_SCOPE")
    if argv[:1] == [SUCCESSOR]:
        if len(argv) != 2:
            raise Refused("USAGE_SUCCESSOR_ORDINAL")
        text = argv[1]
        if not isinstance(text, str) or not text.isascii() or not re.fullmatch(r"[0-9]{1,16}", text):
            raise Refused("SUCCESSOR_ORDINAL_INVALID")
        if text[0] == "0":
            raise Refused("SUCCESSOR_ORDINAL_INVALID")  # no leading zero, and 0 is never an ordinal
        if not SUCCESSOR_ORDINAL_MIN <= int(text) <= SUCCESSOR_ORDINAL_MAX:
            raise Refused("SUCCESSOR_ORDINAL_OUT_OF_RANGE")
        return Form(SUCCESSOR, int(text))
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


def _host_preflight(host: Host, *, euid: int, isolated: bool, hostname: str) -> str:
    """Checks common to both forms. Returns the machine ID. Never reads the host key."""
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
    return machine_id


def preflight(host: Host, *, euid: int, isolated: bool, hostname: str) -> str:
    """`actor`: read-only checks. Returns the machine ID. Never reads the host key."""
    machine_id = _host_preflight(host, euid=euid, isolated=isolated, hostname=hostname)
    if os.path.lexists(host.path(CREDENTIAL_PATH)):
        raise Refused("CREDENTIAL_ALREADY_PRESENT")
    if any(host.path(CREDSTORE).iterdir()):
        raise Refused("CREDSTORE_NOT_EMPTY")
    return machine_id


@dataclass(frozen=True)
class CurrentFacts:
    """CURRENT as observed without following links: identity, custody, bytes."""

    device: int
    inode: int
    mode: int
    uid: int
    gid: int
    size: int
    sha256: str


def current_facts(host: Host) -> CurrentFacts:
    """Observe CURRENT (ciphertext only, never decrypted). Raises OSError."""
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_CLOEXEC", 0)
    fd = os.open(host.path(CREDENTIAL_PATH), flags)
    try:
        meta = os.fstat(fd)
        if not stat.S_ISREG(meta.st_mode) or meta.st_size > MAX_CIPHERTEXT:
            raise OSError("CURRENT is not a bounded regular file")
        digest = hashlib.sha256()
        while chunk := os.read(fd, 65536):
            digest.update(chunk)
    finally:
        os.close(fd)
    return CurrentFacts(meta.st_dev, meta.st_ino, meta.st_mode, meta.st_uid, meta.st_gid, meta.st_size,
                        digest.hexdigest())


def successor_preflight(host: Host, ordinal: int, *, euid: int, isolated: bool,
                        hostname: str) -> tuple[str, CurrentFacts]:
    """`successor <N>`: read-only checks. Returns the machine ID and CURRENT "before".

    Nothing here consults authority state. The derived keyId is compared only
    with the initial K-ACT ID; burned ordinals are refused by the owner
    ceremony register and the ceremony-record verifier, not by keygen state.
    """
    machine_id = _host_preflight(host, euid=euid, isolated=isolated, hostname=hostname)
    if successor_key_id(ordinal) == KEY_ID:
        raise Refused("SUCCESSOR_KEY_ID_IS_INITIAL")
    if sorted(entry.name for entry in host.path(CREDSTORE).iterdir()) != [SLOT_NAME]:
        raise Refused("CREDSTORE_NOT_EXACTLY_CURRENT")
    _root_owned(host, host.path(CREDENTIAL_PATH), kind="file", mode=0o600,
                missing="CURRENT_ABSENT", bad="CURRENT_CUSTODY")
    _root_owned(host, host.path(CUSTODY_ROOT), kind="dir", mode=0o700,
                missing="CUSTODY_ROOT_ABSENT", bad="CUSTODY_ROOT_CUSTODY")
    if sorted(entry.name for entry in host.path(CUSTODY_ROOT).iterdir()) != ["prepared", "retired"]:
        raise Refused("CUSTODY_ROOT_UNEXPECTED_ENTRY")
    _root_owned(host, host.path(PREPARED_DIR), kind="dir", mode=0o700,
                missing="PREPARED_ABSENT", bad="PREPARED_CUSTODY")
    _root_owned(host, host.path(RETIRED_DIR), kind="dir", mode=0o700,
                missing="RETIRED_ABSENT", bad="RETIRED_CUSTODY")
    if any(host.path(PREPARED_DIR).iterdir()):
        raise Refused("PREPARED_NOT_EMPTY")
    if any(host.path(RETIRED_DIR).iterdir()):
        raise Refused("RETIRED_NOT_EMPTY")
    if len({host.device(host.path(p)) for p in (CREDSTORE, PREPARED_DIR, RETIRED_DIR)}) != 1:
        raise Refused("CUSTODY_FILESYSTEM_MISMATCH")
    try:
        before = current_facts(host)
    except OSError as exc:
        raise Refused("CURRENT_CUSTODY") from exc
    return machine_id, before


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


def write_successor_blob(host: Host, ciphertext: bytes, device: int) -> None:
    """Create the PREPARED blob exclusively, through a descriptor of PREPARED.

    The directory is opened `O_DIRECTORY|O_NOFOLLOW` and re-checked on that
    descriptor (root 0700, the credstore's `st_dev`, still empty), so a
    swapped path cannot redirect the write. The blob is `O_EXCL|O_NOFOLLOW`
    `0600`; the file and then the directory are fsynced.
    """
    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_CLOEXEC", 0)
    try:
        directory = os.open(host.path(PREPARED_DIR), flags)
    except OSError as exc:
        raise Failed("PREPARED_CUSTODY") from exc
    try:
        meta = os.fstat(directory)
        observed_device = meta.st_dev if host.device_of is None else host.device_of(host.path(PREPARED_DIR))
        if (not stat.S_ISDIR(meta.st_mode) or (meta.st_uid, meta.st_gid) != (host.owner_uid, host.owner_gid)
                or stat.S_IMODE(meta.st_mode) != 0o700 or observed_device != device):
            raise Failed("PREPARED_CUSTODY")
        if os.listdir(directory):
            raise Failed("PREPARED_NOT_EMPTY")
        create = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_CLOEXEC", 0)
        try:
            fd = os.open(SLOT_NAME, create, 0o600, dir_fd=directory)
        except FileExistsError as exc:
            raise Failed("PREPARED_NOT_EMPTY") from exc
        try:
            view = memoryview(ciphertext)
            while view:
                written = os.write(fd, view)
                view = view[written:]
            os.fchmod(fd, 0o600)
            os.fsync(fd)
        finally:
            os.close(fd)
        os.fsync(directory)
    finally:
        os.close(directory)


def _encrypted_key(key_factory: Callable[[], Ed25519PrivateKey],
                   encrypt: Callable[[bytes], bytes]) -> tuple[bytes, bytes]:
    """(raw public key, ciphertext). The plaintext exists only in memory and the pipe."""
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
    return public, ciphertext


def ceremony(host: Host, machine_id: str, *,
             key_factory: Callable[[], Ed25519PrivateKey] = Ed25519PrivateKey.generate,
             encrypt: Callable[[bytes], bytes] = systemd_encrypt) -> dict:
    public, ciphertext = _encrypted_key(key_factory, encrypt)
    write_blob(host, ciphertext)
    return publication(public, ciphertext, machine_id)


def _require_current_unchanged(host: Host, before: CurrentFacts) -> None:
    try:
        after = current_facts(host)
    except OSError as exc:
        raise Failed("CURRENT_CHANGED") from exc
    if after != before:
        raise Failed("CURRENT_CHANGED")


def successor_ceremony(host: Host, machine_id: str, ordinal: int, before: CurrentFacts, *,
                       key_factory: Callable[[], Ed25519PrivateKey] = Ed25519PrivateKey.generate,
                       encrypt: Callable[[bytes], bytes] = systemd_encrypt) -> dict:
    """Write PREPARED only; CURRENT must be unchanged before and after the write."""
    key_id = successor_key_id(ordinal)
    public, ciphertext = _encrypted_key(key_factory, encrypt)
    _require_current_unchanged(host, before)
    write_successor_blob(host, ciphertext, host.device(host.path(CREDSTORE)))
    _require_current_unchanged(host, before)
    return publication(public, ciphertext, machine_id, key_id=key_id, credential_path=PREPARED_PATH)


def main(argv: list[str] | None = None, *, host: Host = Host()) -> int:
    before: CurrentFacts | None = None
    try:
        form = parse_argv(sys.argv[1:] if argv is None else argv)
        facts = dict(euid=os.geteuid(), isolated=bool(sys.flags.isolated), hostname=os.uname().nodename)
        if form.kind == SUCCESSOR:
            machine_id, before = successor_preflight(host, form.ordinal, **facts)
        else:
            machine_id = preflight(host, **facts)
        restrict_process()
    except Refused as refused:
        print(f"lilith-authority-keygen-dev: REFUSED {refused.reason}", file=sys.stderr)
        return EXIT_REFUSED
    try:
        if form.kind == SUCCESSOR:
            result = successor_ceremony(host, machine_id, form.ordinal, before)
        else:
            result = ceremony(host, machine_id)
    except Failed as failed:
        print(f"lilith-authority-keygen-dev: FAILED {failed.reason}", file=sys.stderr)
        return EXIT_FAILED
    sys.stdout.buffer.write(canonical(result))
    sys.stdout.flush()
    return 0


if __name__ == "__main__":
    sys.exit(main())
