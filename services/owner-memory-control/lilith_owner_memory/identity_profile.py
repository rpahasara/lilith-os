"""TEST-ONLY identity profile and First Memory identity-binding check (Identity V1 draft).

Implements the DRAFT LILITH Identity Charter V1 (docs/architecture/lilith-identity-charter-v1-draft.md) for
synthetic fixtures only. No real `lilithIdentityId` exists; nothing here creates, stores or activates one.

Option III (owner decision D-3), corrected:

- **Genuine verification (D-A).** `verify_identity_bound_memory_v1` runs the unchanged
  `admission_v2.verify_accepted_memory_v2` itself, from its established trusted inputs. It never accepts a
  caller-supplied verification result.
- **Admitted value only (D-B).** The binding is read from the exact class-normalized value L04 stored for that
  admission. The value is accepted only if `sha256(value.encode("ascii"))` equals the owner-signed `payloadDigest`
  that V2 just verified (the existing L04 rule), so neither a caller packet nor an edited stored value can stand in.
  The FM-02 First Interaction class (`OWNER_DIRECTED_FIRST_INTERACTION`, value schema `FirstInteractionEpisodeV1`)
  carries this binding inside its admitted value; every other class fails closed (`IDENTITY_BINDING_MISSING`).
  Known limitation, a blocker for real use: the environment check compares the trusted profile with the caller's
  identity context only; it is not yet bound to the verified V2 authority/owner environment, and no owner-accepted,
  repository-pinned profile source exists yet.
- **No independence claim (D-C).** `lid1.` structure and known-value collision checks catch some mistakes. They
  cannot prove that an identifier was generated independently; that rests on the reviewed generation procedure.

The result never admits, authorizes or makes memory content true. Pure: no I/O, no store, no signer.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping

import rfc8785

from . import admission_v2 as V2

CHARTER_DOMAIN_SEPARATOR = b"LILITH_IDENTITY_CHARTER_V1\x00"
PROFILE_DOMAIN_SEPARATOR = b"LILITH_IDENTITY_PROFILE_V1\x00"
PROFILE_PROTOCOL = "lilith.identity.profile"
PROFILE_SCHEMA_VERSION = 1

IDENTITY_BOUND = "IDENTITY_BOUND"
IDENTITY_NOT_BOUND = "IDENTITY_NOT_BOUND"
BINDING_SEMANTICS = "BINDS_ACCEPTED_MEMORY_TO_IDENTITY_PROFILE_NOT_A_TRUTH_OR_AUTHORITY_CLAIM"
# Where a First Memory value carries its binding (the FM-02 FirstInteractionEpisodeV1 schema uses this field).
BINDING_FIELD = "identityBinding"

REASONS = frozenset({
    "ACCEPTED_MEMORY_REQUIRED",
    "MALFORMED_CONTEXT",
    "ADMITTED_VALUE_UNAVAILABLE",
    "ADMITTED_VALUE_MISMATCH",
    "ADMITTED_VALUE_MALFORMED",
    "IDENTITY_BINDING_MISSING",
    "IDENTITY_BINDING_MALFORMED",
    "IDENTITY_ID_INVALID",
    "IDENTITY_ID_KNOWN_VALUE_COLLISION",
    "IDENTITY_ENVIRONMENT_MISMATCH",
    "IDENTITY_BINDING_MISMATCH",
    "CHARTER_MISMATCH",
})

ENVIRONMENTS = frozenset({"test", "dev", "prod"})
_IDENTITY_ID = re.compile(r"lid1\.[0-9a-f]{32}\Z")
_HEX64 = re.compile(r"[0-9a-f]{64}\Z")
_LONG_HEX = re.compile(r"[0-9a-f]{32,}\Z")
_VERSION = re.compile(r"[0-9]+\.[0-9]+\.[0-9]+(?:-[a-z0-9.]+)?\Z")
BINDING_FIELDS = frozenset({"lilithIdentityId", "charterVersion", "charterDigest", "identityProfileDigest"})


class IdentityContractViolation(ValueError):
    pass


def _canonical(value: Mapping[str, Any]) -> bytes:
    try:
        return rfc8785.dumps(dict(value))
    except rfc8785.CanonicalizationError as exc:
        raise IdentityContractViolation("INVALID_CANONICALIZATION") from exc


def charter_digest(charter_bytes: bytes) -> str:
    """SHA-256 over the domain separator and the exact charter bytes."""
    if not isinstance(charter_bytes, (bytes, bytearray)) or not charter_bytes:
        raise IdentityContractViolation("INVALID_CHARTER_BYTES")
    return hashlib.sha256(CHARTER_DOMAIN_SEPARATOR + bytes(charter_bytes)).hexdigest()


@dataclass(frozen=True)
class IdentityProfileV1:
    environment: str
    lilith_identity_id: str
    charter_version: str
    charter_digest: str

    def __post_init__(self) -> None:
        if self.environment not in ENVIRONMENTS:
            raise IdentityContractViolation("INVALID_ENVIRONMENT")
        if not isinstance(self.lilith_identity_id, str) or not _IDENTITY_ID.fullmatch(self.lilith_identity_id):
            raise IdentityContractViolation("INVALID_IDENTITY_ID")
        if not isinstance(self.charter_version, str) or not _VERSION.fullmatch(self.charter_version):
            raise IdentityContractViolation("INVALID_CHARTER_VERSION")
        if not isinstance(self.charter_digest, str) or not _HEX64.fullmatch(self.charter_digest):
            raise IdentityContractViolation("INVALID_CHARTER_DIGEST")

    def fields(self) -> dict[str, Any]:
        return {
            "protocol": PROFILE_PROTOCOL,
            "schemaVersion": PROFILE_SCHEMA_VERSION,
            "environment": self.environment,
            "lilithIdentityId": self.lilith_identity_id,
            "charter": {"charterVersion": self.charter_version, "charterDigest": self.charter_digest},
        }

    def canonical_bytes(self) -> bytes:
        return _canonical(self.fields())

    def digest(self) -> str:
        return hashlib.sha256(PROFILE_DOMAIN_SEPARATOR + self.canonical_bytes()).hexdigest()

    def binding(self) -> dict[str, str]:
        """The exact binding an admitted First Memory value would carry for this profile."""
        return {
            "lilithIdentityId": self.lilith_identity_id,
            "charterVersion": self.charter_version,
            "charterDigest": self.charter_digest,
            "identityProfileDigest": self.digest(),
        }


def known_value_collisions(identity_id: str, known_values: Iterable[str]) -> list[str]:
    """Known values the identifier collides with: exact equality (whole ID or its hex body), or the hex body
    appearing inside a known hex digest. This catches some mistakes only. It cannot show that an identifier was
    generated independently: an ID derived from the owner ID or a key would pass."""
    ident = identity_id.lower()
    body = ident.split(".", 1)[-1]
    out = []
    for raw in known_values:
        value = str(raw).lower()
        if value in (ident, body) or (_LONG_HEX.fullmatch(value) and body in value):
            out.append(str(raw))
    return out


@dataclass(frozen=True)
class IdentityVerificationContextV1:
    """The trusted profile comes from trusted code (an owner-accepted, repository-pinned profile), never from a
    memory value or a caller packet."""
    environment: str
    trusted_profile: IdentityProfileV1
    known_values: frozenset[str] = field(default_factory=frozenset)

    def __post_init__(self) -> None:
        if not isinstance(self.trusted_profile, IdentityProfileV1) or self.environment not in ENVIRONMENTS:
            raise IdentityContractViolation("MALFORMED_CONTEXT")
        if known_value_collisions(self.trusted_profile.lilith_identity_id, self.known_values):
            raise IdentityContractViolation("TRUSTED_IDENTITY_COLLIDES_WITH_KNOWN_VALUE")


@dataclass(frozen=True)
class IdentityBindingResultV1:
    status: str
    reason: str | None = None
    detail: str | None = None
    facts: Mapping[str, Any] = field(default_factory=dict)


class _Reject(Exception):
    def __init__(self, reason: str, detail: str | None = None) -> None:
        assert reason in REASONS, reason
        super().__init__(reason)
        self.reason, self.detail = reason, detail


def _require(condition: bool, reason: str, detail: str | None = None) -> None:
    if not condition:
        raise _Reject(reason, detail)


def _compare_binding(binding: Any, context: IdentityVerificationContextV1) -> None:
    """Comparison only: does `binding` equal the trusted profile's binding? Raises _Reject otherwise. It proves
    nothing about admission; only `verify_identity_bound_memory_v1` composes it with genuine V2 verification."""
    _require(binding is not None, "IDENTITY_BINDING_MISSING")
    _require(isinstance(binding, Mapping) and set(binding) == BINDING_FIELDS
             and all(isinstance(v, str) for v in binding.values()), "IDENTITY_BINDING_MALFORMED")
    identity_id = binding["lilithIdentityId"]
    _require(bool(_IDENTITY_ID.fullmatch(identity_id)), "IDENTITY_ID_INVALID")
    collisions = known_value_collisions(identity_id, context.known_values)
    _require(not collisions, "IDENTITY_ID_KNOWN_VALUE_COLLISION", ",".join(sorted(collisions)))
    trusted = context.trusted_profile
    _require(trusted.environment == context.environment, "IDENTITY_ENVIRONMENT_MISMATCH")
    _require((binding["charterVersion"], binding["charterDigest"])
             == (trusted.charter_version, trusted.charter_digest), "CHARTER_MISMATCH")
    _require(dict(binding) == trusted.binding(), "IDENTITY_BINDING_MISMATCH")


def _not_bound(rejected: _Reject) -> IdentityBindingResultV1:
    return IdentityBindingResultV1(IDENTITY_NOT_BOUND, rejected.reason, rejected.detail,
                                   {"truthClaim": False, "authorizesAdmission": False})


def verify_identity_bound_memory_v1(*, admitted_value: Any, identity_context: IdentityVerificationContextV1,
                                    **v2_inputs: Any) -> IdentityBindingResultV1:
    """IDENTITY_BOUND only when genuine V2 verification (run here, from `v2_inputs`) returns ACCEPTED_MEMORY, the
    stored class-normalized `admitted_value` hashes to that verified owner-signed `payloadDigest`, and the value's
    binding equals the trusted profile. Never an admission, an authorization or a truth claim."""
    try:
        _require(isinstance(identity_context, IdentityVerificationContextV1), "MALFORMED_CONTEXT")
        accepted = V2.verify_accepted_memory_v2(**v2_inputs)
        _require(accepted.status == V2.ACCEPTED_MEMORY and accepted.facts.get("truthClaim") is False,
                 "ACCEPTED_MEMORY_REQUIRED", accepted.reason)
        _require(isinstance(admitted_value, str), "ADMITTED_VALUE_UNAVAILABLE")
        try:
            encoded = admitted_value.encode("ascii")
        except UnicodeEncodeError:
            raise _Reject("ADMITTED_VALUE_MISMATCH") from None
        _require(hashlib.sha256(encoded).hexdigest() == accepted.facts.get("payloadDigest"), "ADMITTED_VALUE_MISMATCH")
        try:
            value = json.loads(admitted_value)
        except ValueError:
            raise _Reject("ADMITTED_VALUE_MALFORMED") from None
        _require(isinstance(value, dict), "ADMITTED_VALUE_MALFORMED")
        _compare_binding(value.get(BINDING_FIELD), identity_context)
    except _Reject as rejected:
        return _not_bound(rejected)
    trusted = identity_context.trusted_profile
    return IdentityBindingResultV1(IDENTITY_BOUND, None, None, {
        "semantics": BINDING_SEMANTICS,
        "truthClaim": False,
        "authorizesAdmission": False,
        "lilithIdentityId": trusted.lilith_identity_id,
        "charterVersion": trusted.charter_version,
        "charterDigest": trusted.charter_digest,
        "identityProfileDigest": trusted.digest(),
        "payloadDigest": accepted.facts.get("payloadDigest"),
        "proposalRefId": accepted.facts.get("proposalRefId"),
    })
