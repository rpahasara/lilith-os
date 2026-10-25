"""The K-WIT systemd credential and the one signing capability it enables (PR-1S).

The only private-material source is `$CREDENTIALS_DIRECTORY/recovery-witness-signing-key`,
which systemd populates for `lilith-recovery-witness.service` from the
root-owned encrypted blob under `/etc/lilith-recovery-witness/credentials/`
(RR-36, `LoadCredentialEncrypted=`). This module never generates, derives,
embeds, or falls back to a key, and never reads another path or the
environment for key bytes.

`WitnessSigningKeyV1` is the service's only signer. Its single method signs
the RFC 8785 bytes of one exact unsigned `RecoveryWitnessV2` body under the
V2 domain separator, after re-checking the body's shape and its
`witnessKeyId`. There is no method that signs caller bytes, a digest, an
OwnerEvidence, a registry, an authorization, or Privacy material.
Process-memory zeroization is NOT_PROVEN.

Track B B2 adds a second, separate key: K-PAN (`PrivacyAnchorSigningKeyV1`),
loaded only from `$CREDENTIALS_DIRECTORY/privacy-anchor-signing-key`. It signs
only `PrivacyAnchorV1` bodies (`lilith_memory.privacy_anchor_contracts`, its
own domain), and only a body that verifies as a strict extension of the chain
it is given. K-WIT never signs an anchor; K-PAN never signs a
RecoveryWitnessV2 body. An absent K-PAN disables only the anchor operations.
"""

from __future__ import annotations

import base64
import hashlib
import os
import stat
from pathlib import Path
from typing import Any, Mapping

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat, load_der_private_key
from lilith_memory import privacy_anchor_contracts as PA
from lilith_memory.owner_proof import OwnerProofError
from lilith_owner_memory import recovery_contracts as R
from lilith_owner_memory import rotation_contracts as RC

from .profile import CREDENTIAL_NAME, CREDENTIALS_DIRECTORY, WITNESS_KEY_ID

CREDENTIAL_ABSENT = "CREDENTIAL_ABSENT"
CREDENTIAL_INVALID = "CREDENTIAL_INVALID"
CREDENTIAL_PRESENT_UNVERIFIED = "CREDENTIAL_PRESENT_UNVERIFIED"
MAX_CREDENTIAL_BYTES = 256
# K-PAN (Track B): its own credential name, key id and Privacy environment, distinct from K-WIT's.
PRIVACY_ANCHOR_CREDENTIAL_NAME = "privacy-anchor-signing-key"
PRIVACY_ANCHOR_KEY_ID = "kpan.dev-synthetic.01"
PRIVACY_ANCHOR_ENVIRONMENT = "DEV_SYNTHETIC"


class WitnessCredentialError(Exception):
    def __init__(self, state: str):
        super().__init__(state)
        self.state = state


class WitnessSigningKeyV1:
    """Signs RecoveryWitnessV2 bodies only. Not serializable, not copyable."""

    def __init__(self, private_key: Ed25519PrivateKey, *, witness_key_id: str = WITNESS_KEY_ID):
        if not isinstance(private_key, Ed25519PrivateKey):
            raise TypeError("an in-process Ed25519 key object is required")
        if not isinstance(witness_key_id, str) or not witness_key_id.startswith(R.TEST_ONLY_WITNESS_PREFIX):
            raise ValueError("the K-WIT key ID must be a test-only witness key ID")
        self.__key = private_key
        self.witness_key_id = witness_key_id

    def __reduce__(self):
        raise TypeError("the witness signing key is not serializable")

    def __copy__(self):
        raise TypeError("the witness signing key is not copyable")

    def __deepcopy__(self, memo):
        raise TypeError("the witness signing key is not copyable")

    def public_key(self) -> bytes:
        return self.__key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)

    def public_key_sha256(self) -> str:
        return hashlib.sha256(self.public_key()).hexdigest()

    def sign_recovery_witness_v2(self, unsigned: Mapping[str, Any]) -> dict[str, Any]:
        """The signed V2 document for one exact unsigned body (with `witnessKeyId`)."""
        if not isinstance(unsigned, Mapping) or set(unsigned) != RC.WITNESS_V2_SIGNED_FIELDS:
            raise ValueError("not an unsigned RecoveryWitnessV2 body")
        if unsigned.get("protocol") != R.WITNESS_PROTOCOL or unsigned.get("schemaVersion") != RC.WITNESS_V2_SCHEMA_VERSION \
                or unsigned.get("witnessKeyId") != self.witness_key_id:
            raise ValueError("not a RecoveryWitnessV2 body for this key")
        try:
            message = RC.witness_v2_signing_bytes(dict(unsigned))
            RC.RecoveryWitnessV2.from_verified_dict({**unsigned, "signature": "unsigned-body-check"})
        except OwnerProofError as exc:
            raise ValueError("malformed RecoveryWitnessV2 body") from exc
        signature = base64.urlsafe_b64encode(self.__key.sign(message)).rstrip(b"=").decode("ascii")
        return {**dict(unsigned), "signature": signature}


def load_witness_signing_key(credentials_directory: str | None, *,
                             expected_directory: str = CREDENTIALS_DIRECTORY) -> WitnessSigningKeyV1:
    """Load K-WIT from the unit's own credentials directory, or refuse.

    Unset -> `CREDENTIAL_ABSENT` (systemd delivered nothing). Another
    directory, a non-regular or oversized file, or anything but Ed25519
    PKCS#8 DER -> `CREDENTIAL_INVALID`.
    """
    if not credentials_directory:
        raise WitnessCredentialError(CREDENTIAL_ABSENT)
    if credentials_directory != expected_directory:
        raise WitnessCredentialError(CREDENTIAL_INVALID)
    path = Path(credentials_directory) / CREDENTIAL_NAME
    try:
        fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_CLOEXEC", 0))
    except FileNotFoundError as exc:
        raise WitnessCredentialError(CREDENTIAL_ABSENT) from exc
    except OSError as exc:
        raise WitnessCredentialError(CREDENTIAL_INVALID) from exc
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_size > MAX_CREDENTIAL_BYTES:
            raise WitnessCredentialError(CREDENTIAL_INVALID)
        raw = os.read(fd, MAX_CREDENTIAL_BYTES + 1)
    except OSError as exc:
        raise WitnessCredentialError(CREDENTIAL_INVALID) from exc
    finally:
        os.close(fd)
    if not raw or len(raw) > MAX_CREDENTIAL_BYTES:
        raise WitnessCredentialError(CREDENTIAL_INVALID)
    try:
        key = load_der_private_key(raw, password=None)
    except Exception as exc:  # malformed DER, encrypted PKCS#8, unsupported algorithm
        raise WitnessCredentialError(CREDENTIAL_INVALID) from exc
    if not isinstance(key, Ed25519PrivateKey):
        raise WitnessCredentialError(CREDENTIAL_INVALID)
    return WitnessSigningKeyV1(key)


class PrivacyAnchorSigningKeyV1:
    """K-PAN: signs PrivacyAnchorV1 extensions only. Not serializable, not copyable."""

    def __init__(self, private_key: Ed25519PrivateKey, *, anchor_key_id: str = PRIVACY_ANCHOR_KEY_ID,
                 environment: str = PRIVACY_ANCHOR_ENVIRONMENT):
        if not isinstance(private_key, Ed25519PrivateKey):
            raise TypeError("an in-process Ed25519 key object is required")
        if not isinstance(anchor_key_id, str) or not anchor_key_id.startswith(PA.KPAN_KEY_PREFIX)                 or anchor_key_id.startswith(R.TEST_ONLY_WITNESS_PREFIX):
            raise ValueError("the K-PAN key ID must carry the kpan. prefix and never a K-WIT prefix")
        self.__key = private_key
        self.anchor_key_id = anchor_key_id
        self.environment = environment

    def __reduce__(self):
        raise TypeError("the privacy anchor signing key is not serializable")

    def __copy__(self):
        raise TypeError("the privacy anchor signing key is not copyable")

    def __deepcopy__(self, memo):
        raise TypeError("the privacy anchor signing key is not copyable")

    def public_key(self) -> bytes:
        return self.__key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)

    def public_key_sha256(self) -> str:
        return hashlib.sha256(self.public_key()).hexdigest()

    def verifying_key(self) -> Ed25519PublicKey:
        return self.__key.public_key()

    def sign_privacy_anchor(self, previous: list[Mapping[str, Any]], unsigned: Mapping[str, Any]) -> dict[str, Any]:
        """The signed anchor for one exact unsigned body. `previous` (the stored chain, possibly empty) is verified
        first, and the result is re-verified as the next version of exactly that chain before it is returned."""
        if not isinstance(unsigned, Mapping) or set(unsigned) != set(PA.ANCHOR_FIELDS)                 or unsigned.get("anchorKeyId") != self.anchor_key_id or unsigned.get("environment") != self.environment:
            raise ValueError("not a PrivacyAnchorV1 body for this key")
        previous = [dict(doc) for doc in previous]
        try:
            if previous:
                PA.verify_anchor_chain(previous, self.verifying_key(), environment=self.environment,
                                       key_id=self.anchor_key_id)
            signed = {**dict(unsigned), "signature": self.__key.sign(PA.signing_bytes("anchor", dict(unsigned))).hex()}
            PA.verify_anchor_chain(previous + [signed], self.verifying_key(), environment=self.environment,
                                   key_id=self.anchor_key_id)
        except PA.PrivacyAnchorError as exc:
            raise ValueError("not a strict extension: " + exc.code) from exc
        return signed


def load_privacy_anchor_key(credentials_directory: str | None, *, expected_directory: str = CREDENTIALS_DIRECTORY,
                            witness_key: WitnessSigningKeyV1 | None = None) -> PrivacyAnchorSigningKeyV1:
    """Load K-PAN from the unit's own credentials directory, or refuse, by the same rules as K-WIT. Key material
    identical to the loaded K-WIT is refused: the two families never share a key."""
    if not credentials_directory:
        raise WitnessCredentialError(CREDENTIAL_ABSENT)
    if credentials_directory != expected_directory:
        raise WitnessCredentialError(CREDENTIAL_INVALID)
    path = Path(credentials_directory) / PRIVACY_ANCHOR_CREDENTIAL_NAME
    try:
        fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_CLOEXEC", 0)
                     | getattr(os, "O_BINARY", 0))
    except FileNotFoundError as exc:
        raise WitnessCredentialError(CREDENTIAL_ABSENT) from exc
    except OSError as exc:
        raise WitnessCredentialError(CREDENTIAL_INVALID) from exc
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_size > MAX_CREDENTIAL_BYTES:
            raise WitnessCredentialError(CREDENTIAL_INVALID)
        raw = os.read(fd, MAX_CREDENTIAL_BYTES + 1)
    except OSError as exc:
        raise WitnessCredentialError(CREDENTIAL_INVALID) from exc
    finally:
        os.close(fd)
    if not raw or len(raw) > MAX_CREDENTIAL_BYTES:
        raise WitnessCredentialError(CREDENTIAL_INVALID)
    try:
        key = load_der_private_key(raw, password=None)
    except Exception as exc:  # malformed DER, encrypted PKCS#8, unsupported algorithm
        raise WitnessCredentialError(CREDENTIAL_INVALID) from exc
    if not isinstance(key, Ed25519PrivateKey):
        raise WitnessCredentialError(CREDENTIAL_INVALID)
    anchor_key = PrivacyAnchorSigningKeyV1(key)
    if witness_key is not None and anchor_key.public_key() == witness_key.public_key():
        raise WitnessCredentialError(CREDENTIAL_INVALID)
    return anchor_key
