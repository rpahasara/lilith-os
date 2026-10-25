#!/usr/bin/python3 -IB
"""Track B B3: the one-time DEV_SYNTHETIC K-PAN (Privacy anchor signing key) ceremony. SOURCE ONLY; never installed.

Run only by the owner, as root, on `lilith-dev-01`, inside a separately authorized ceremony step, streamed (no host
file): `python3 -I -B - keygen`. There is exactly one form and no option: no algorithm, key ID, path, output, export,
seed or force. It mirrors the accepted K-WIT form of `lilith-authority-keygen-dev witness` (RR-36) without changing
that release CLI:

1. refuses unless every precondition holds: root; isolated interpreter; the DEV host (hostname + machine-id); no
   active swap; the host credential key `/var/lib/systemd/credential.secret` root:root 0400; `systemd-creds`
   root:root 0755; `/etc/lilith-recovery-witness` and its `credentials/` root:root 0700, not symlinks; `credentials/`
   holding EXACTLY the K-WIT blob (observed "before"), and no K-PAN blob;
2. generates one fresh Ed25519 key in process memory (no seed);
3. writes its unencrypted PKCS#8 DER only to the stdin pipe of
   `/usr/bin/systemd-creds encrypt --with-key=host --name=privacy-anchor-signing-key - -`;
4. writes the ciphertext `O_EXCL|O_NOFOLLOW` through a descriptor of `credentials/` as
   `lilith-recovery-witness.privacy-anchor.cred` (root:root 0600), fsyncs file and directory;
5. observes the K-WIT blob again (identity, owner, mode, size, SHA-256): any change is `FAILED KWIT_CHANGED`;
6. prints one canonical JSON public pin (`LILITH_PRIVACY_KEY_PIN_V1`, family K-PAN, keyId `kpan.dev-synthetic.01`)
   plus custody evidence (blob SHA-256 and size). No private material is ever printed or written to a file.

One-time: an existing K-PAN blob is a refusal; a blob left by a failed run is destroyed and the key burned (a new key),
never reused. K-PAN signs only `PrivacyAnchorV1` strict extensions (witness `privacy_anchor`); nothing here makes it an
authority, witness (K-WIT), checkpoint (K-PCK) or root (K-ROOT) key.

Memory zeroization and remanence are NOT_PROVEN (Python bytes are immutable). The host-bound credential protects the
blob against ordinary application and deployer access only; it is NOT snapshot-rollback protection (that is exactly
what the off-host K-PCK checkpoint chain covers).
"""

from __future__ import annotations

import hashlib
import json
import os
import socket
import stat
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, NoEncryption, PrivateFormat, PublicFormat

ENVIRONMENT = "DEV_SYNTHETIC"
KEY_ID = "kpan.dev-synthetic.01"
CREDENTIAL_NAME = "privacy-anchor-signing-key"
WITNESS_PARENT = "/etc/lilith-recovery-witness"
CREDENTIAL_DIR = WITNESS_PARENT + "/credentials"
KWIT_BLOB_NAME = "lilith-recovery-witness.witness.cred"
KPAN_BLOB_NAME = "lilith-recovery-witness.privacy-anchor.cred"
KPAN_BLOB_PATH = CREDENTIAL_DIR + "/" + KPAN_BLOB_NAME
HOST_KEY = "/var/lib/systemd/credential.secret"
SYSTEMD_CREDS = "/usr/bin/systemd-creds"
ENCRYPT_ARGV = (SYSTEMD_CREDS, "encrypt", "--with-key=host", "--name=" + CREDENTIAL_NAME, "-", "-")
DEV_HOSTNAME = "lilith-dev-01"
DEV_MACHINE_ID = "ae929170e6fa4c8ab9cc7b9547238d9d"
PIN_TYPE = "LILITH_PRIVACY_KEY_PIN_V1"
MAX_CIPHERTEXT = 64 * 1024
ENCRYPT_TIMEOUT_SECONDS = 30
FIXED_ENV = {"PATH": "/usr/sbin:/usr/bin:/sbin:/bin", "LANG": "C", "HOME": "/nonexistent"}
EXIT_REFUSED, EXIT_FAILED = 2, 3


class Refused(Exception):
    """A precondition does not hold. Nothing was generated or written."""

    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


class Failed(Exception):
    """The ceremony started and did not complete: STOP, burn the key, destroy any blob (runbook)."""

    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


def canonical(value: dict) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True) + "\n").encode("ascii")


@dataclass(frozen=True)
class Host:
    """Everything the ceremony reads or writes. Tests replace root, owner and the encryptor."""

    root: Path = Path("/")
    owner_uid: int = 0
    owner_gid: int = 0
    encrypt: Callable[[bytes], bytes] | None = None

    def path(self, absolute: str) -> Path:
        return self.root / absolute.lstrip("/")


def _root_owned(host: Host, path: Path, *, kind: str, mode: int, missing: str, bad: str) -> os.stat_result:
    try:
        meta = os.lstat(path)
    except FileNotFoundError as exc:
        raise Refused(missing) from exc
    is_kind = stat.S_ISDIR(meta.st_mode) if kind == "dir" else stat.S_ISREG(meta.st_mode)
    if not is_kind or (meta.st_uid, meta.st_gid) != (host.owner_uid, host.owner_gid) or stat.S_IMODE(meta.st_mode) != mode:
        raise Refused(bad)
    return meta


@dataclass(frozen=True)
class BlobFacts:
    device: int
    inode: int
    mode: int
    uid: int
    gid: int
    size: int
    sha256: str


def blob_facts(path: Path) -> BlobFacts:
    """Observe a ciphertext blob without following links (never decrypted). Raises OSError."""
    fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_BINARY", 0))
    try:
        meta = os.fstat(fd)
        if not stat.S_ISREG(meta.st_mode) or meta.st_size > MAX_CIPHERTEXT:
            raise OSError("not a bounded regular file")
        digest = hashlib.sha256()
        while chunk := os.read(fd, 65536):
            digest.update(chunk)
    finally:
        os.close(fd)
    return BlobFacts(meta.st_dev, meta.st_ino, meta.st_mode, meta.st_uid, meta.st_gid, meta.st_size, digest.hexdigest())


def preflight(host: Host, *, euid: int, isolated: bool, hostname: str) -> tuple[str, BlobFacts]:
    """Read-only. Returns the machine ID and the K-WIT blob "before"."""
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
    _root_owned(host, host.path(HOST_KEY), kind="file", mode=0o400, missing="HOST_CREDENTIAL_KEY_ABSENT",
                bad="HOST_CREDENTIAL_KEY_CUSTODY")
    _root_owned(host, host.path(SYSTEMD_CREDS), kind="file", mode=0o755, missing="SYSTEMD_CREDS_ABSENT",
                bad="SYSTEMD_CREDS_CUSTODY")
    _root_owned(host, host.path(WITNESS_PARENT), kind="dir", mode=0o700, missing="WITNESS_PARENT_ABSENT",
                bad="WITNESS_PARENT_CUSTODY")
    _root_owned(host, host.path(CREDENTIAL_DIR), kind="dir", mode=0o700, missing="CREDENTIAL_DIR_ABSENT",
                bad="CREDENTIAL_DIR_CUSTODY")
    names = sorted(entry.name for entry in host.path(CREDENTIAL_DIR).iterdir())
    if KPAN_BLOB_NAME in names:
        raise Refused("KPAN_ALREADY_PRESENT")
    if names != [KWIT_BLOB_NAME]:
        raise Refused("CREDENTIAL_DIR_NOT_EXACTLY_KWIT")
    _root_owned(host, host.path(CREDENTIAL_DIR + "/" + KWIT_BLOB_NAME), kind="file", mode=0o600,
                missing="KWIT_ABSENT", bad="KWIT_CUSTODY")
    return machine_id, blob_facts(host.path(CREDENTIAL_DIR + "/" + KWIT_BLOB_NAME))


def _encrypt(host: Host, der: bytes) -> bytes:
    if host.encrypt is not None:
        return host.encrypt(der)
    result = subprocess.run(ENCRYPT_ARGV, input=der, capture_output=True, env=FIXED_ENV,
                            timeout=ENCRYPT_TIMEOUT_SECONDS, check=False)
    if result.returncode != 0:
        raise Failed("ENCRYPT_FAILED")
    return result.stdout


def _no_core_dumps() -> None:
    try:
        import resource

        resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    except (ImportError, ValueError, OSError):
        pass
    try:
        import ctypes

        ctypes.CDLL(None).prctl(4, 0, 0, 0, 0)          # PR_SET_DUMPABLE = 0
    except (OSError, AttributeError, TypeError):
        pass


def keygen(host: Host, *, euid: int, isolated: bool, hostname: str) -> dict:
    machine_id, kwit_before = preflight(host, euid=euid, isolated=isolated, hostname=hostname)
    key = Ed25519PrivateKey.generate()
    public = key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
    ciphertext = _encrypt(host, key.private_bytes(Encoding.DER, PrivateFormat.PKCS8, NoEncryption()))
    del key
    if not isinstance(ciphertext, bytes) or not 0 < len(ciphertext) <= MAX_CIPHERTEXT:
        raise Failed("CIPHERTEXT_INVALID")
    folder = os.open(host.path(CREDENTIAL_DIR), os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
                     | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_CLOEXEC", 0))
    try:
        try:
            fd = os.open(KPAN_BLOB_NAME, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
                         | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_BINARY", 0), 0o600, dir_fd=folder)
        except OSError as exc:
            raise Failed("BLOB_CREATE_FAILED") from exc
        try:
            view = memoryview(ciphertext)
            while view:
                view = view[os.write(fd, view):]
            os.fsync(fd)
        finally:
            os.close(fd)
        os.fsync(folder)
    finally:
        os.close(folder)
    try:
        if blob_facts(host.path(CREDENTIAL_DIR + "/" + KWIT_BLOB_NAME)) != kwit_before:
            raise Failed("KWIT_CHANGED")
        written = blob_facts(host.path(KPAN_BLOB_PATH))
    except OSError as exc:
        raise Failed("POST_OBSERVATION_FAILED") from exc
    if written.sha256 != hashlib.sha256(ciphertext).hexdigest() or written.size != len(ciphertext) \
            or stat.S_IMODE(written.mode) != 0o600:
        raise Failed("BLOB_NOT_AS_WRITTEN")
    return {
        "pin": {"type": PIN_TYPE, "family": "K-PAN", "environment": ENVIRONMENT, "keyId": KEY_ID,
                "publicKeyHex": public.hex()},
        "publicKeySha256": hashlib.sha256(public).hexdigest(),
        "custodyEvidence": {"credentialName": CREDENTIAL_NAME, "credentialPath": KPAN_BLOB_PATH, "withKey": "host",
                            "machineId": machine_id, "blobByteSize": len(ciphertext),
                            "blobSha256": hashlib.sha256(ciphertext).hexdigest(),
                            "kwitBlobSha256Unchanged": kwit_before.sha256},
    }


def main(argv: list[str]) -> int:
    if argv != ["keygen"]:
        print("REFUSED USAGE_ONLY_KEYGEN")
        return EXIT_REFUSED
    _no_core_dumps()
    try:
        result = keygen(Host(), euid=os.geteuid(), isolated=bool(sys.flags.isolated), hostname=socket.gethostname())
    except Refused as exc:
        print("REFUSED " + exc.reason)
        return EXIT_REFUSED
    except Failed as exc:
        print("FAILED " + exc.reason)
        return EXIT_FAILED
    sys.stdout.buffer.write(canonical(result))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
