"""15B2b-B1b-3a pure authority registry and evidence verifier (TEST-ONLY).

Design: docs/architecture/slice-15b2b-b1b3-custody-isolation-design.md.

A positive result means only that the supplied evidence was signed by a key
that the supplied owner-signed registry publishes for exactly this
environment, authority domain, evidence type, recovery epoch, registry
version, and policy version, and that it binds exactly the caller's
independently verified expectation. It is **not** ACCEPTED_MEMORY, not an L04
admission, and not a truth claim.

Semantics frozen here:

- routine retirement or non-compromise revocation keeps historical evidence
  valid inside `[notBefore, retiredAt/revokedAt)`, for HISTORICAL_VERIFICATION
  only; a retired or revoked key never supports NEW_ADMISSION;
- compromise is retroactive: every piece of evidence the key signed is
  rejected, whatever its signer-controlled `issuedAt`, because re-attestation
  does not exist yet;
- NEW_ADMISSION requires the current recovery epoch, registry version, and
  policy version; HISTORICAL_VERIFICATION accepts older-epoch evidence as
  history only (`authorizesNewAdmission` is false);
- a registry below the caller's trusted monotonic version is a downgrade.

This detects stale-epoch evidence given a trusted expected epoch. It does not
detect whole-host or whole-disk rollback; that needs an off-host or
independently monotonic anchor and remains unresolved.

The verifier reads only its arguments: no file, environment, network, model,
runtime, broker, L04, or Privacy DB access, and no writes.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from lilith_memory.owner_proof import OwnerProofError, _exact

from . import authority_contracts as A
from .contracts import _canonical

VERIFIED_REGISTRY = "VERIFIED_REGISTRY"
VERIFIED_AUTHORITY_EVIDENCE = "VERIFIED_AUTHORITY_EVIDENCE"
NOT_ACCEPTED = "NOT_ACCEPTED"
EVIDENCE_SEMANTICS = "REGISTRY_KEY_SIGNED_AUTHORITY_EVIDENCE_NOT_MEMORY_ACCEPTANCE"

# Closed, ordered NOT_ACCEPTED reason taxonomy for this slice.
REASONS = (
    "MALFORMED_CONTEXT",
    "REGISTRY_ROOT_NOT_TEST_ONLY",
    "REGISTRY_MISSING",
    "REGISTRY_MALFORMED",
    "REGISTRY_UNSIGNED",
    "REGISTRY_ROOT_MISMATCH",
    "REGISTRY_SIGNATURE_INVALID",
    "UNSUPPORTED_SCHEMA_VERSION",
    "KEY_ALGORITHM_UNSUPPORTED",
    "KEY_RECORD_INVALID",
    "KEY_ENVIRONMENT_MISMATCH",
    "REGISTRY_ENVIRONMENT_MISMATCH",
    "REGISTRY_DOWNGRADE",
    "REGISTRY_EPOCH_MISMATCH",
    "REGISTRY_POLICY_MISMATCH",
    "EVIDENCE_MISSING",
    "EVIDENCE_MALFORMED",
    "EVIDENCE_DOMAIN_MISMATCH",
    "EVIDENCE_TYPE_MISMATCH",
    "ENVIRONMENT_MISMATCH",
    "KEY_UNKNOWN",
    "KEY_DOMAIN_MISMATCH",
    "SIGNATURE_INVALID",
    "KEY_COMPROMISED",
    "RECOVERY_EPOCH_MISMATCH",
    "REGISTRY_VERSION_MISMATCH",
    "POLICY_VERSION_MISMATCH",
    "KEY_NOT_YET_VALID",
    "KEY_REVOKED",
    "KEY_RETIRED",
    "LOGICAL_OWNER_MISMATCH",
    "EVIDENCE_ID_MISMATCH",
    "EVIDENCE_NONCE_MISMATCH",
    "CHALLENGE_REFERENCE_MISMATCH",
    "OWNER_PROOF_REFERENCE_MISMATCH",
    "REQUEST_DIGEST_MISMATCH",
    "ACTION_DIGEST_MISMATCH",
    "PAYLOAD_DIGEST_MISMATCH",
    "FORGET_REQUEST_MISMATCH",
    "HOLD_MISMATCH",
    "OWNER_EVIDENCE_REFERENCE_MISMATCH",
    "MEMORY_IDENTITY_MISMATCH",
    "RESOURCE_OWNERS_MISMATCH",
)


@dataclass(frozen=True)
class AuthorityResultV1:
    status: str
    reason: str | None = None
    facts: Mapping[str, Any] = field(default_factory=dict)

    @property
    def verified(self) -> bool:
        return self.status in {VERIFIED_REGISTRY, VERIFIED_AUTHORITY_EVIDENCE}


class _Reject(Exception):
    def __init__(self, reason: str):
        assert reason in REASONS, reason
        self.reason = reason


def _require(condition: bool, reason: str) -> None:
    if not condition:
        raise _Reject(reason)


_REGISTRY_CODES = {
    "UNSUPPORTED_SCHEMA_VERSION": "UNSUPPORTED_SCHEMA_VERSION",
    "UNSUPPORTED_ALGORITHM": "KEY_ALGORITHM_UNSUPPORTED",
    "KEY_ENVIRONMENT_MISMATCH": "KEY_ENVIRONMENT_MISMATCH",
}
_KEY_RECORD_CODES = frozenset({
    "INVALID_AUTHORITY_DOMAIN", "INVALID_EVIDENCE_TYPES", "INVALID_PUBLIC_KEY",
    "INVALID_VALIDITY_INTERVAL", "INVALID_REVOCATION", "INVALID_REVOCATION_REASON",
    "INVALID_KEY_ORDER", "DUPLICATE_PUBLIC_KEY", "INVALID_KEY_REGISTRY_VERSION",
    "INVALID_KEY_TIMESTAMP", "INVALID_KEY_RECOVERY_EPOCH", "INVALID_KEY_POLICY_VERSION",
    "INVALID_KEY_ID",
})


def _parse_registry(value: Mapping[str, Any]) -> A.AuthorityRegistryV1:
    try:
        return A.AuthorityRegistryV1.from_verified_dict(value)
    except OwnerProofError as exc:
        if exc.code in _REGISTRY_CODES:
            raise _Reject(_REGISTRY_CODES[exc.code]) from exc
        raise _Reject("KEY_RECORD_INVALID" if exc.code in _KEY_RECORD_CODES else "REGISTRY_MALFORMED") from exc
    except (KeyError, TypeError, ValueError, AttributeError) as exc:
        raise _Reject("REGISTRY_MALFORMED") from exc


def _verify_signature(public_key: bytes, signature: bytes, message: bytes, reason: str) -> None:
    try:
        Ed25519PublicKey.from_public_bytes(public_key).verify(signature, message)
    except (InvalidSignature, ValueError) as exc:
        raise _Reject(reason) from exc


def _check_context(context: Any) -> A.AuthorityVerificationContextV1:
    _require(isinstance(context, A.AuthorityVerificationContextV1), "MALFORMED_CONTEXT")
    try:
        context.validate()
    except (OwnerProofError, TypeError, ValueError, AttributeError) as exc:
        raise _Reject("MALFORMED_CONTEXT") from exc
    _require(context.registry_root.test_only, "REGISTRY_ROOT_NOT_TEST_ONLY")
    return context


def _verify_registry(context: A.AuthorityVerificationContextV1, registry: Any) -> A.AuthorityRegistryV1:
    _require(registry is not None, "REGISTRY_MISSING")
    _require(isinstance(registry, Mapping), "REGISTRY_MALFORMED")
    _require(registry.get("signature") is not None, "REGISTRY_UNSIGNED")
    # Verify the signature over the exact signed fields before trusting any
    # content. Only the top-level shape and the signature encoding are read.
    try:
        _exact(registry, A.REGISTRY_FIELDS)
        signature = A._signature(registry["signature"])
        unsigned = {name: registry[name] for name in A.REGISTRY_SIGNED_FIELDS}
        message = A.REGISTRY_DOMAIN_SEPARATOR + _canonical(unsigned)
    except (OwnerProofError, TypeError, ValueError) as exc:
        raise _Reject("REGISTRY_MALFORMED") from exc
    root = context.registry_root
    _require(registry["registryRootKeyId"] == root.root_key_id, "REGISTRY_ROOT_MISMATCH")
    _verify_signature(root.public_key, signature, message, "REGISTRY_SIGNATURE_INVALID")

    parsed = _parse_registry(registry)
    # The registry root is its own trust anchor and never an authority key.
    _require(all(record.public_key != root.public_key for record in parsed.keys.values()), "KEY_RECORD_INVALID")
    _require(parsed.environment == context.environment and root.environment == context.environment,
             "REGISTRY_ENVIRONMENT_MISMATCH")
    _require(parsed.registry_version >= context.trusted_minimum_registry_version, "REGISTRY_DOWNGRADE")
    _require(parsed.recovery_epoch == context.expected_recovery_epoch, "REGISTRY_EPOCH_MISMATCH")
    _require(parsed.policy_version == context.policy_version, "REGISTRY_POLICY_MISMATCH")
    return parsed


def verify_authority_registry(*, context: A.AuthorityVerificationContextV1,
                              registry: Mapping[str, Any] | None) -> AuthorityResultV1:
    """Verify one owner-signed registry document against a trusted root."""
    try:
        parsed = _verify_registry(_check_context(context), registry)
    except _Reject as rejected:
        return AuthorityResultV1(NOT_ACCEPTED, rejected.reason)
    return AuthorityResultV1(VERIFIED_REGISTRY, None, {
        "environment": parsed.environment,
        "registryVersion": parsed.registry_version,
        "recoveryEpoch": parsed.recovery_epoch.to_dict(),
        "policyVersion": parsed.policy_version,
        "registryRootKeyId": parsed.registry_root_key_id,
        "keyIds": sorted(parsed.keys),
    })


def _parse_evidence(parser, value):
    try:
        return parser(value)
    except OwnerProofError as exc:
        raise _Reject("UNSUPPORTED_SCHEMA_VERSION" if exc.code == "UNSUPPORTED_SCHEMA_VERSION"
                      else "EVIDENCE_MALFORMED") from exc
    except (KeyError, TypeError, ValueError, AttributeError) as exc:
        raise _Reject("EVIDENCE_MALFORMED") from exc


def _verify_evidence(context, registry, evidence, contract, domain, evidence_type):
    context = _check_context(context)
    parsed = _verify_registry(context, registry)
    _require(evidence is not None, "EVIDENCE_MISSING")
    envelope = _parse_evidence(contract.from_dict, evidence)

    # Domain and type before key lookup: a Privacy artifact is never Actor
    # evidence and vice versa, regardless of which key signed it.
    _require(envelope["authorityDomain"] == domain, "EVIDENCE_DOMAIN_MISMATCH")
    _require(envelope["evidenceType"] == evidence_type, "EVIDENCE_TYPE_MISMATCH")
    _require(envelope["environment"] == context.environment, "ENVIRONMENT_MISMATCH")
    key = parsed.keys.get(envelope["keyId"])
    _require(key is not None, "KEY_UNKNOWN")
    _require(key.authority_domain == domain, "KEY_DOMAIN_MISMATCH")
    _require(evidence_type in key.evidence_types, "EVIDENCE_TYPE_MISMATCH")
    _verify_signature(key.public_key, envelope.signature, envelope.signing_bytes(), "SIGNATURE_INVALID")

    # Compromise is retroactive; signer-controlled issuedAt cannot rescue it.
    _require(not key.compromised, "KEY_COMPROMISED")

    new_admission = context.purpose == A.NEW_ADMISSION
    _require(envelope.recovery_epoch == key.recovery_epoch, "RECOVERY_EPOCH_MISMATCH")
    if new_admission:
        _require(envelope.recovery_epoch == context.expected_recovery_epoch, "RECOVERY_EPOCH_MISMATCH")
    version = envelope["registryVersion"]
    _require(key.registry_version <= version <= parsed.registry_version, "REGISTRY_VERSION_MISMATCH")
    if new_admission:
        _require(version == parsed.registry_version, "REGISTRY_VERSION_MISMATCH")
    _require(envelope["policyVersion"] == key.policy_version, "POLICY_VERSION_MISMATCH")
    if new_admission:
        _require(envelope["policyVersion"] == context.policy_version, "POLICY_VERSION_MISMATCH")

    issued = envelope.issued_at
    _require(issued >= key.not_before, "KEY_NOT_YET_VALID")
    key_status = "CURRENT"
    if key.revoked_at is not None:
        _require(not new_admission and issued < key.revoked_at, "KEY_REVOKED")
        key_status = "REVOKED_AFTER_ISSUANCE"
    if key.retired_at is not None:
        _require(not new_admission and issued < key.retired_at, "KEY_RETIRED")
        key_status = "RETIRED_AFTER_ISSUANCE" if key_status == "CURRENT" else key_status
    return envelope, key, key_status, parsed


def _facts(context, envelope, key_status, parsed, id_field) -> dict[str, Any]:
    return {
        "semantics": EVIDENCE_SEMANTICS,
        "memoryAcceptance": False,
        "truthClaim": False,
        "purpose": context.purpose,
        "authorizesNewAdmission": context.purpose == A.NEW_ADMISSION,
        id_field: envelope[id_field],
        "authorityDomain": envelope["authorityDomain"],
        "evidenceType": envelope["evidenceType"],
        "environment": envelope["environment"],
        "keyId": envelope["keyId"],
        "keyStatus": key_status,
        "evidenceRecoveryEpoch": envelope.recovery_epoch.to_dict(),
        "evidenceRegistryVersion": envelope["registryVersion"],
        "evidencePolicyVersion": envelope["policyVersion"],
        "registryVersion": parsed.registry_version,
        "issuedAt": envelope["issuedAt"],
    }


def verify_owner_evidence(*, context: A.AuthorityVerificationContextV1, registry: Mapping[str, Any] | None,
                          evidence: Mapping[str, Any] | None,
                          expectation: A.OwnerEvidenceExpectationV2) -> AuthorityResultV1:
    """Verify Owner/Actor evidence. Never ACCEPTED_MEMORY on its own."""
    try:
        _require(isinstance(expectation, A.OwnerEvidenceExpectationV2), "MALFORMED_CONTEXT")
        envelope, _key, key_status, parsed = _verify_evidence(
            context, registry, evidence, A.OwnerEvidenceV2, A.OWNER_ACTOR, A.OWNER_MEMORY_OPERATION)
        e = expectation
        _require(envelope["logicalOwnerId"] == e.logical_owner_id, "LOGICAL_OWNER_MISMATCH")
        _require(envelope["evidenceId"] == e.evidence_id, "EVIDENCE_ID_MISMATCH")
        # B1b-1: the challenge ID is the unique evidence nonce.
        _require(envelope["evidenceNonce"] == envelope["challengeId"], "EVIDENCE_NONCE_MISMATCH")
        _require(envelope["challengeId"] == e.challenge_id
                 and envelope["challengeDigest"] == e.challenge_digest, "CHALLENGE_REFERENCE_MISMATCH")
        _require(envelope["credentialRecordId"] == e.credential_record_id
                 and envelope["assertionDigest"] == e.assertion_digest, "OWNER_PROOF_REFERENCE_MISMATCH")
        _require(envelope["requestDigest"] == e.request_digest, "REQUEST_DIGEST_MISMATCH")
        _require(envelope["actionDigest"] == e.action_digest, "ACTION_DIGEST_MISMATCH")
        _require(envelope["payloadDigest"] == e.payload_digest, "PAYLOAD_DIGEST_MISMATCH")
    except _Reject as rejected:
        return AuthorityResultV1(NOT_ACCEPTED, rejected.reason)
    return AuthorityResultV1(VERIFIED_AUTHORITY_EVIDENCE, None,
                             _facts(context, envelope, key_status, parsed, "evidenceId"))


def verify_privacy_authorization(*, context: A.AuthorityVerificationContextV1,
                                 registry: Mapping[str, Any] | None,
                                 authorization: Mapping[str, Any] | None,
                                 expectation: A.PrivacyAuthorizationExpectationV2) -> AuthorityResultV1:
    """Verify a Privacy erasure authorization. Owner/Actor keys never verify."""
    try:
        _require(isinstance(expectation, A.PrivacyAuthorizationExpectationV2), "MALFORMED_CONTEXT")
        envelope, _key, key_status, parsed = _verify_evidence(
            context, registry, authorization, A.PrivacyAuthorizationV2, A.PRIVACY,
            A.PRIVACY_ERASURE_AUTHORIZATION)
        e = expectation
        _require(envelope["logicalOwnerId"] == e.logical_owner_id, "LOGICAL_OWNER_MISMATCH")
        _require(envelope["authorizationId"] == e.authorization_id, "EVIDENCE_ID_MISMATCH")
        _require(envelope["executionNonce"] == e.execution_nonce, "EVIDENCE_NONCE_MISMATCH")
        _require(envelope["forgetRequestId"] == e.forget_request_id, "FORGET_REQUEST_MISMATCH")
        _require(envelope["holdId"] == e.hold_id, "HOLD_MISMATCH")
        _require(envelope["ownerEvidenceId"] == e.owner_evidence_id, "OWNER_EVIDENCE_REFERENCE_MISMATCH")
        _require((envelope["memoryClass"], envelope["subjectNamespace"], envelope["subjectKey"],
                  envelope["memoryItemId"])
                 == (e.memory_class, e.subject_namespace, e.subject_key, e.memory_item_id),
                 "MEMORY_IDENTITY_MISMATCH")
        _require(envelope["actionDigest"] == e.action_digest, "ACTION_DIGEST_MISMATCH")
        _require(tuple(envelope["resourceOwners"]) == tuple(e.resource_owners), "RESOURCE_OWNERS_MISMATCH")
    except _Reject as rejected:
        return AuthorityResultV1(NOT_ACCEPTED, rejected.reason)
    return AuthorityResultV1(VERIFIED_AUTHORITY_EVIDENCE, None,
                             _facts(context, envelope, key_status, parsed, "authorizationId"))
