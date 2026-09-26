"""Structured-only OWNER_ACTOR evidence minter (B1b-3d L1, source only).

This is the only code in the signer that may use a private key. It signs
exactly one artifact type, the accepted B1b-3a `OwnerEvidenceV2`, and exactly
its bytes:

    LILITH_ACTOR_EVIDENCE_V2\\0 || RFC8785(unsigned OwnerEvidenceV2 fields)

It has no operation that accepts bytes, text, a digest to sign, a domain
separator, or a signing domain chosen by the caller. The input is a field
mapping that must parse under `OwnerEvidenceV2.from_dict`; the signed bytes
are always re-derived from it by `owner_evidence_signing_bytes`.

Refuse-to-sign guards bind the evidence to the minter's own published
`AuthorityKeyRecordV1` (keyId, OWNER_ACTOR, OWNER_MEMORY_OPERATION, dev,
public key, current, recovery epoch, policy) and require
`key.registryVersion <= evidence.registryVersion`, keeping the accepted
first-published-version semantics. The guards only narrow what is signed.
Acceptance stays exclusively with the B1b-3a verifier, which also enforces
`evidence.registryVersion <= verified registry.registryVersion`, downgrade,
and revocation. This module never decides that evidence is valid authority.

L1: nothing in the service constructs a minter. It is exercised by tests
with TEST-only in-process keys, and is wired only by a later slice after the
registry, witness, and durable ledger exist.
"""

from __future__ import annotations

import base64
import copy
from typing import Any, Mapping

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
from lilith_memory.owner_proof import OwnerProofError
from lilith_owner_memory import authority_contracts as A

from .profile import ENVIRONMENT, EVIDENCE_TYPE, SIGNING_DOMAIN, DevSyntheticSignerProfileV1, ProfileError

# Closed, ordered refusal taxonomy.
MINT_REASONS = (
    "MINT_REQUEST_NOT_STRUCTURED",
    "MINT_FIELDS_MISMATCH",
    "MINT_EVIDENCE_MALFORMED",
    "SIGNING_DOMAIN_REFUSED",
    "EVIDENCE_TYPE_REFUSED",
    "ENVIRONMENT_REFUSED",
    "KEY_ID_MISMATCH",
    "PROFILE_BINDING_MISMATCH",
    "EVIDENCE_NONCE_MISMATCH",
    "RECOVERY_EPOCH_MISMATCH",
    "REGISTRY_VERSION_BELOW_KEY",
    "ISSUED_BEFORE_KEY_VALIDITY",
)

_SIGNED_FIELDS = A.OwnerEvidenceV2.signed_fields()
# Only a placeholder for contract-shape validation; it is never emitted.
_SHAPE_ONLY_SIGNATURE = "A" * 86  # 64 zero bytes, base64url


class MinterConfigurationError(ValueError):
    """The minter was constructed outside its DEV_SYNTHETIC OWNER_ACTOR envelope."""


class MintRefused(Exception):
    def __init__(self, reason: str):
        assert reason in MINT_REASONS, reason
        self.reason = reason
        super().__init__(reason)


def _b64(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


class OwnerActorEvidenceMinterV1:
    """Holds one OWNER_ACTOR private key object; signs only OwnerEvidenceV2.

    The key is in a name-mangled attribute with no accessor. The object
    refuses pickling and copying and prints no key material.
    """

    def __init__(self, *, signing_key: Ed25519PrivateKey, profile: DevSyntheticSignerProfileV1,
                 key_record: A.AuthorityKeyRecordV1):
        if not isinstance(signing_key, Ed25519PrivateKey):
            raise MinterConfigurationError("signing key must be an in-process Ed25519 key object")
        if not isinstance(profile, DevSyntheticSignerProfileV1):
            raise MinterConfigurationError("profile is invalid")
        try:
            profile.validate()
        except ProfileError as exc:
            raise MinterConfigurationError(str(exc)) from exc
        if not isinstance(key_record, A.AuthorityKeyRecordV1):
            raise MinterConfigurationError("key record is invalid")
        public = signing_key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
        if key_record.public_key != public:
            raise MinterConfigurationError("the key record does not publish this key")
        if key_record.key_id != profile.key_id:
            raise MinterConfigurationError("the key record names another key")
        if key_record.signing_domain != SIGNING_DOMAIN or key_record.evidence_types != frozenset({EVIDENCE_TYPE}):
            raise MinterConfigurationError("the key record is not an OWNER_ACTOR OWNER_MEMORY_OPERATION key")
        if key_record.environment != ENVIRONMENT:
            raise MinterConfigurationError("the key record is not a dev key")
        if not key_record.current:
            raise MinterConfigurationError("the key record is retired or revoked")
        if key_record.policy_version != profile.policy_version:
            raise MinterConfigurationError("the key record and profile disagree on policy")
        self.__signing_key = signing_key
        self._profile = profile
        self._key_record = key_record

    def __repr__(self) -> str:
        return f"OwnerActorEvidenceMinterV1(keyId={self._profile.key_id!r}, signingDomain='OWNER_ACTOR')"

    def __reduce__(self):
        raise TypeError("the OWNER_ACTOR minter is not serializable")

    def __copy__(self):
        raise TypeError("the OWNER_ACTOR minter is not copyable")

    def __deepcopy__(self, memo):
        raise TypeError("the OWNER_ACTOR minter is not copyable")

    @property
    def key_id(self) -> str:
        return self._profile.key_id

    def mint(self, unsigned: Mapping[str, Any]) -> dict[str, Any]:
        """Sign one structured OwnerEvidenceV2 and return the signed document."""
        if not isinstance(unsigned, Mapping) or isinstance(unsigned, (bytes, bytearray, str)):
            raise MintRefused("MINT_REQUEST_NOT_STRUCTURED")
        if set(unsigned) != _SIGNED_FIELDS:
            raise MintRefused("MINT_FIELDS_MISMATCH")
        fields = copy.deepcopy(dict(unsigned))  # validated and signed bytes come from one private copy
        try:
            evidence = A.OwnerEvidenceV2.from_dict({**fields, "signature": _SHAPE_ONLY_SIGNATURE})
        except OwnerProofError as exc:
            raise MintRefused("MINT_EVIDENCE_MALFORMED") from exc
        self._guard(evidence)
        signature = self.__signing_key.sign(A.owner_evidence_signing_bytes(fields))
        return {**fields, "signature": _b64(signature)}

    def _guard(self, evidence: A.OwnerEvidenceV2) -> None:
        profile, record = self._profile, self._key_record
        if evidence["signingDomain"] != SIGNING_DOMAIN:
            raise MintRefused("SIGNING_DOMAIN_REFUSED")
        if evidence["evidenceType"] != EVIDENCE_TYPE:
            raise MintRefused("EVIDENCE_TYPE_REFUSED")
        if evidence["environment"] != ENVIRONMENT:
            raise MintRefused("ENVIRONMENT_REFUSED")
        if evidence["keyId"] != record.key_id:
            raise MintRefused("KEY_ID_MISMATCH")
        if (evidence["authorityDomain"], evidence["logicalOwnerId"], evidence["policyVersion"]) \
                != (profile.authority_domain, profile.logical_owner_id, profile.policy_version):
            raise MintRefused("PROFILE_BINDING_MISMATCH")
        if evidence["evidenceNonce"] != evidence["challengeId"]:
            raise MintRefused("EVIDENCE_NONCE_MISMATCH")
        if evidence.recovery_epoch != record.recovery_epoch:
            raise MintRefused("RECOVERY_EPOCH_MISMATCH")
        if evidence["registryVersion"] < record.registry_version:
            raise MintRefused("REGISTRY_VERSION_BELOW_KEY")
        if evidence.issued_at < record.not_before:
            raise MintRefused("ISSUED_BEFORE_KEY_VALIDITY")
