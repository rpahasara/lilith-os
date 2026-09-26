"""Fail-closed inspection of the OWNER_ACTOR systemd credential (B1b-3d L1).

The only private-material source is `$CREDENTIALS_DIRECTORY/owner-actor-signing-key`,
which systemd 255 populates for `lilith-authority-dev.service` from the
root-owned encrypted blob (`LoadCredentialEncrypted=`, design §5). This module:

- never generates, derives, or embeds a key;
- never falls back to a repository, TEST, default, or ephemeral key;
- never reads an environment variable holding key bytes, a database row, or
  any other path;
- keeps absence (`CREDENTIAL_ABSENT`) distinct from a present but unusable
  credential (`CREDENTIAL_INVALID`).

L1 inspects only. It returns public facts (state and public-key fingerprint)
and drops the private key object: nothing in L1 signs.
"""

from __future__ import annotations

import hashlib
import os
import stat
from dataclasses import dataclass
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat, load_der_private_key

from .profile import CREDENTIAL_NAME, CREDENTIALS_DIRECTORY

CREDENTIAL_ABSENT = "CREDENTIAL_ABSENT"
CREDENTIAL_INVALID = "CREDENTIAL_INVALID"
# Present and parseable as Ed25519. NOT verified against any registry record.
CREDENTIAL_PRESENT_UNVERIFIED = "CREDENTIAL_PRESENT_UNVERIFIED"
CREDENTIAL_STATES = (CREDENTIAL_ABSENT, CREDENTIAL_INVALID, CREDENTIAL_PRESENT_UNVERIFIED)

# PKCS#8 DER for Ed25519 is 48 bytes; anything far larger is not this key.
MAX_CREDENTIAL_BYTES = 256


@dataclass(frozen=True)
class CredentialStatusV1:
    """Public facts only. Never holds or prints private bytes."""

    state: str
    public_key_sha256: str | None = None

    def __post_init__(self) -> None:
        if self.state not in CREDENTIAL_STATES:
            raise ValueError("unknown credential state")
        if (self.state == CREDENTIAL_PRESENT_UNVERIFIED) != (self.public_key_sha256 is not None):
            raise ValueError("a public fingerprint exists only for a present credential")


def inspect_owner_actor_credential(credentials_directory: str | None, *,
                                   expected_directory: str = CREDENTIALS_DIRECTORY) -> CredentialStatusV1:
    """Classify the credential systemd delivered, without keeping the key.

    `credentials_directory` is the value of `$CREDENTIALS_DIRECTORY`. Unset
    means systemd delivered nothing: `CREDENTIAL_ABSENT`. A directory other
    than the unit's own is refused as `CREDENTIAL_INVALID`.
    """
    if credentials_directory is None or credentials_directory == "":
        return CredentialStatusV1(CREDENTIAL_ABSENT)
    if credentials_directory != expected_directory:
        return CredentialStatusV1(CREDENTIAL_INVALID)
    path = Path(credentials_directory) / CREDENTIAL_NAME
    try:
        fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_CLOEXEC", 0))
    except FileNotFoundError:
        return CredentialStatusV1(CREDENTIAL_ABSENT)
    except OSError:
        return CredentialStatusV1(CREDENTIAL_INVALID)
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_size > MAX_CREDENTIAL_BYTES:
            return CredentialStatusV1(CREDENTIAL_INVALID)
        raw = os.read(fd, MAX_CREDENTIAL_BYTES + 1)
    except OSError:
        return CredentialStatusV1(CREDENTIAL_INVALID)
    finally:
        os.close(fd)
    return _classify(raw)


def _classify(raw: bytes) -> CredentialStatusV1:
    if not raw or len(raw) > MAX_CREDENTIAL_BYTES:
        return CredentialStatusV1(CREDENTIAL_INVALID)
    try:
        key = load_der_private_key(raw, password=None)
    except Exception:  # malformed DER, encrypted PKCS#8, unsupported algorithm
        return CredentialStatusV1(CREDENTIAL_INVALID)
    if not isinstance(key, Ed25519PrivateKey):
        return CredentialStatusV1(CREDENTIAL_INVALID)
    public = key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
    del key
    return CredentialStatusV1(CREDENTIAL_PRESENT_UNVERIFIED, hashlib.sha256(public).hexdigest())
