"""15B2b-B2a pure accepted-memory verifier (TEST-ONLY; no live authority).

Authoritative acceptance is a verifier result over the complete authority and
provenance chain. No mutable database flag is authority.

A positive result means only that the supplied chain establishes that this
memory operation/value was validly owner-authorized, broker-attested and
L04-admitted under the stated policy context. It is never a claim that the
memory's content is true, and it never changes the epistemic basis.

The verifier only reads the artifacts it is given. It writes nothing, mints
nothing, repairs nothing, calls no model, runtime or network, and infers no
missing link. In this slice it refuses any context other than the synthetic
TEST environment with a `.invalid` relying party.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from fido2 import cbor
from fido2.cose import CoseKey
from fido2.server import Fido2Server
from fido2.webauthn import (
    AttestedCredentialData,
    AuthenticationResponse,
    AuthenticatorAssertionResponse,
    AuthenticatorData,
    CollectedClientData,
    PublicKeyCredentialRpEntity,
    UserVerificationRequirement,
)
from lilith_memory import canonical_contracts as C
from lilith_memory import owner_proof as P
from lilith_memory.owner_proof import OwnerProofError, _b64u_decode, _instant

from . import contracts as K


ACCEPTED_MEMORY = "ACCEPTED_MEMORY"
NOT_ACCEPTED = "NOT_ACCEPTED"
ACCEPTANCE_SEMANTICS = "OWNER_AUTHORIZED_BROKER_ATTESTED_L04_ADMITTED_NOT_A_TRUTH_CLAIM"
SUPPORTED_OPERATIONS = frozenset({C.CREATE, C.SUPERSEDE, C.RESTORE})

# Closed, ordered NOT_ACCEPTED reason taxonomy for this slice.
REASONS = (
    "ENVIRONMENT_NOT_SUPPORTED",
    "MALFORMED_ARTIFACT",
    "UNSUPPORTED_SCHEMA_VERSION",
    "ACTION_MISSING",
    "OPERATION_NOT_SUPPORTED",
    "OWNER_PROOF_MISSING",
    "RP_MISMATCH",
    "LOGICAL_OWNER_MISMATCH",
    "AUTHORITY_DOMAIN_MISMATCH",
    "DEPLOYMENT_ENVIRONMENT_MISMATCH",
    "POLICY_VERSION_MISMATCH",
    "REGISTRY_VERSION_MISMATCH",
    "LEDGER_EPOCH_MISMATCH",
    "PRIVACY_NOTICE_MISMATCH",
    "OPERATION_MISMATCH",
    "MEMORY_IDENTITY_MISMATCH",
    "PAYLOAD_DIGEST_MISMATCH",
    "ACTION_DIGEST_MISMATCH",
    "CHALLENGE_STATE_MISSING",
    "CHALLENGE_LEDGER_MISMATCH",
    "CHALLENGE_NOT_CONSUMED",
    "CHALLENGE_NOT_YET_VALID",
    "CHALLENGE_EXPIRED",
    "OWNER_CREDENTIAL_MISMATCH",
    "OWNER_CREDENTIAL_NOT_AUTHORIZED",
    "OWNER_CREDENTIAL_REVOKED",
    "OWNER_SIGNATURE_INVALID",
    "BROKER_EVIDENCE_MISSING",
    "BROKER_KEY_UNKNOWN",
    "BROKER_KEY_SCOPE_MISMATCH",
    "BROKER_SIGNATURE_INVALID",
    "BROKER_KEY_REVOKED",
    "BROKER_RELEASE_NOT_ALLOWED",
    "EVIDENCE_NONCE_MISMATCH",
    "EVIDENCE_CHALLENGE_MISMATCH",
    "EVIDENCE_OWNER_PROOF_MISMATCH",
    "REQUEST_DIGEST_MISMATCH",
    "EVIDENCE_BINDING_MISMATCH",
    "EVIDENCE_ORDER_INVALID",
    "ADMISSION_EVIDENCE_MISSING",
    "ADMISSION_NOT_ACCEPTED",
    "ADMISSION_BINDING_MISMATCH",
    "PROVENANCE_MISMATCH",
)


@dataclass(frozen=True)
class AcceptanceResultV1:
    status: str
    reason: str | None = None
    facts: Mapping[str, Any] = field(default_factory=dict)

    @property
    def accepted(self) -> bool:
        return self.status == ACCEPTED_MEMORY


class _Reject(Exception):
    def __init__(self, reason: str):
        assert reason in REASONS, reason
        self.reason = reason


def _require(condition: bool, reason: str) -> None:
    if not condition:
        raise _Reject(reason)


_VERSION_CODES = frozenset({
    "UNSUPPORTED_SCHEMA_VERSION", "UNSUPPORTED_CHALLENGE_VERSION", "UNSUPPORTED_CREDENTIAL_VERSION",
})


def _parse(parser, value):
    try:
        return parser(value)
    except OwnerProofError as exc:
        if exc.code in _VERSION_CODES:
            raise _Reject("UNSUPPORTED_SCHEMA_VERSION") from exc
        raise _Reject("MALFORMED_ARTIFACT") from exc
    except (KeyError, TypeError, ValueError, AttributeError) as exc:
        raise _Reject("MALFORMED_ARTIFACT") from exc


def _challenge_from_bytes(raw: bytes) -> K.OwnerMemoryChallengeV2:
    if not isinstance(raw, (bytes, bytearray)):
        raise K.ContractViolation("INVALID_CHALLENGE_BYTES")

    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise K.ContractViolation("DUPLICATE_JSON_FIELD")
            result[key] = value
        return result

    try:
        data = json.loads(bytes(raw).decode("utf-8"), object_pairs_hook=unique)
    except (UnicodeError, ValueError) as exc:
        raise K.ContractViolation("INVALID_CHALLENGE_BYTES") from exc
    challenge = K.OwnerMemoryChallengeV2.from_dict(data)
    if bytes(raw) != challenge.canonical_bytes():
        raise K.ContractViolation("NONCANONICAL_CHALLENGE")
    return challenge


def parse_challenge_v2(raw: bytes) -> K.OwnerMemoryChallengeV2:
    """Parse exact canonical V2 challenge bytes (duplicate fields rejected).
    Raises `OwnerProofError` on any malformed or non-canonical input."""
    return _challenge_from_bytes(raw)


def _verify_webauthn(challenge: K.OwnerMemoryChallengeV2, assertion: P.OwnerAssertionV1,
                     credential: P.OwnerCredentialV1, *, rp_id: str, origin: str) -> None:
    """The unchanged B1a WebAuthn sequence, over the V2 challenge bytes."""
    try:
        client_raw = _b64u_decode(assertion.client_data_json, "client_data", 1, 2048)
        client_fields = P._json_object(client_raw, allowed=frozenset({"type", "challenge", "origin", "crossOrigin"}))
        if set(client_fields) not in ({"type", "challenge", "origin"}, {"type", "challenge", "origin", "crossOrigin"}) \
                or client_fields.get("crossOrigin", False) is not False:
            raise ValueError("invalid client data")
        auth_raw = _b64u_decode(assertion.authenticator_data, "authenticator_data", 37, 1024)
        signature = _b64u_decode(assertion.signature, "signature", 1, 512)
        cose_raw = _b64u_decode(credential.public_key_cose, "public_key", 16, 2048)
        cose_map, rest = cbor.decode_from(cose_raw)
        if rest or not isinstance(cose_map, dict) or cose_map.get(3) != -7:
            raise ValueError("unsupported COSE key")
        public_credential = AttestedCredentialData.create(
            b"\x00" * 16, _b64u_decode(credential.credential_id, "credential_id", 16, 1024), CoseKey.parse(cose_map))
        response = AuthenticationResponse(
            raw_id=public_credential.credential_id,
            response=AuthenticatorAssertionResponse(
                client_data=CollectedClientData(client_raw),
                authenticator_data=AuthenticatorData(auth_raw),
                signature=signature,
            ),
        )
        server = Fido2Server(PublicKeyCredentialRpEntity(name="LILITH owner proof", id=rp_id),
                             verify_origin=lambda value: value == origin)
        _, state = server.authenticate_begin([public_credential], user_verification=UserVerificationRequirement.REQUIRED,
                                             challenge=challenge.webauthn_challenge())
        server.authenticate_complete(state, [public_credential], response)
    except (OwnerProofError, ValueError, TypeError, KeyError, IndexError, OverflowError) as exc:
        raise _Reject("OWNER_SIGNATURE_INVALID") from exc


def verify_accepted_memory(
    *,
    context: K.AcceptanceContextV1,
    action: C.FrozenMemoryActionV1 | None,
    challenge_json: bytes | None,
    challenge_record: Mapping[str, Any] | None,
    assertion: Mapping[str, Any] | None,
    owner_credential: Mapping[str, Any] | None,
    evidence: Mapping[str, Any] | None,
    broker_keys: Iterable[Mapping[str, Any]],
    admission: Mapping[str, Any] | None,
) -> AcceptanceResultV1:
    """Return ACCEPTED_MEMORY only when every required link verifies."""
    try:
        return AcceptanceResultV1(ACCEPTED_MEMORY, None, _verify(
            context, action, challenge_json, challenge_record, assertion,
            owner_credential, evidence, tuple(broker_keys), admission,
        ))
    except _Reject as rejected:
        return AcceptanceResultV1(NOT_ACCEPTED, rejected.reason)


VERIFIED_OWNER_PROOF = "VERIFIED_OWNER_PROOF"


@dataclass(frozen=True)
class VerifiedOwnerProofV1:
    """Steps 1-6 of the chain: a consumed, owner-signed V2 challenge bound to
    the frozen action. It is owner authorization only: never broker evidence,
    never an admission, never ACCEPTED_MEMORY."""

    challenge: K.OwnerMemoryChallengeV2
    record: K.OwnerChallengeLedgerRecordV2
    assertion: P.OwnerAssertionV1
    credential: P.OwnerCredentialV1
    consumed_at: Any
    owner_credential_status: str

    @property
    def assertion_digest(self) -> str:
        return K.assertion_digest(self.assertion)


@dataclass(frozen=True)
class OwnerProofResultV1:
    status: str
    reason: str | None = None
    proof: VerifiedOwnerProofV1 | None = None

    @property
    def verified(self) -> bool:
        return self.status == VERIFIED_OWNER_PROOF


def verify_owner_proof(
    *,
    context: K.AcceptanceContextV1,
    action: C.FrozenMemoryActionV1 | None,
    challenge_json: bytes | None,
    challenge_record: Mapping[str, Any] | None,
    assertion: Mapping[str, Any] | None,
    owner_credential: Mapping[str, Any] | None,
) -> OwnerProofResultV1:
    """Verify only the owner-proof part of the chain (steps 1-6), with the same
    rules and reasons as `verify_accepted_memory`."""
    try:
        return OwnerProofResultV1(VERIFIED_OWNER_PROOF, None, _verify_owner_proof(
            context, action, challenge_json, challenge_record, assertion, owner_credential))
    except _Reject as rejected:
        return OwnerProofResultV1(NOT_ACCEPTED, rejected.reason)


def _verify_owner_proof(context, action, challenge_json, challenge_record, assertion,
                        owner_credential) -> VerifiedOwnerProofV1:
    # 1. Trusted context. B2a supports only the synthetic TEST environment.
    _require(isinstance(context, K.AcceptanceContextV1), "MALFORMED_ARTIFACT")
    _parse(lambda value: value.validate(), context)
    _require(context.deployment_environment == "test" and context.rp_id.endswith(".invalid")
             and context.origin == "https://" + context.rp_id, "ENVIRONMENT_NOT_SUPPORTED")

    # 2. The intended operation (the frozen action) is required and must be valid.
    _require(action is not None, "ACTION_MISSING")
    _require(isinstance(action, C.FrozenMemoryActionV1), "MALFORMED_ARTIFACT")
    _parse(lambda value: value.validate(), action)
    _require(action.operation in SUPPORTED_OPERATIONS, "OPERATION_NOT_SUPPORTED")

    # 3. Owner-signed challenge (V2 only; canonical bytes only).
    _require(challenge_json is not None and assertion is not None and owner_credential is not None,
             "OWNER_PROOF_MISSING")
    challenge = _parse(_challenge_from_bytes, challenge_json)
    _require(challenge["rpId"] == context.rp_id, "RP_MISMATCH")
    _require(challenge["logicalOwnerId"] == context.logical_owner_id
             and challenge["ownerPrincipal"] == context.owner_principal, "LOGICAL_OWNER_MISMATCH")
    _require(challenge["authorityDomain"] == context.authority_domain, "AUTHORITY_DOMAIN_MISMATCH")
    _require(challenge["deploymentEnvironment"] == context.deployment_environment, "DEPLOYMENT_ENVIRONMENT_MISMATCH")
    _require(challenge["policyVersion"] == context.policy_version, "POLICY_VERSION_MISMATCH")
    _require(challenge["registryTupleVersion"] == context.registry_tuple_version, "REGISTRY_VERSION_MISMATCH")
    _require(challenge["ledgerEpoch"] == context.ledger_epoch, "LEDGER_EPOCH_MISMATCH")
    _require(challenge["privacyNoticeVersion"] == context.privacy_notice_version, "PRIVACY_NOTICE_MISMATCH")

    # 4. Challenge ↔ intended action. Specific fields first, then the action digest.
    _require(challenge["operation"] == action.operation, "OPERATION_MISMATCH")
    _require((challenge["memoryClass"], challenge["subjectNamespace"], challenge["subjectKey"],
              challenge["purpose"], challenge["expectedActiveRevisionId"], challenge["restoreTargetRevisionId"])
             == (action.memory_class, action.subject_namespace, action.subject_key, action.purpose,
                 action.expected_active_revision_id, action.restore_revision_id), "MEMORY_IDENTITY_MISMATCH")
    _require(challenge["payloadDigest"] == action.payload_digest, "PAYLOAD_DIGEST_MISMATCH")
    _require(challenge["actionDigest"] == action.action_digest, "ACTION_DIGEST_MISMATCH")

    # 5. Durable challenge state: consumed once, by this credential, in time.
    _require(challenge_record is not None, "CHALLENGE_STATE_MISSING")
    record = _parse(K.OwnerChallengeLedgerRecordV2.from_dict, challenge_record)
    proof = _parse(P.OwnerAssertionV1.from_dict, assertion)
    _require(record.challenge_id == challenge["challengeId"] and record.ledger_epoch == challenge["ledgerEpoch"],
             "CHALLENGE_LEDGER_MISMATCH")
    _require(record.state == "CONSUMED", "CHALLENGE_NOT_CONSUMED")
    _require(record.consumed_credential_record_id == proof.credential_record_id, "CHALLENGE_LEDGER_MISMATCH")
    consumed = _instant(record.consumed_at)
    _require(consumed >= _instant(challenge["issuedAt"]), "CHALLENGE_NOT_YET_VALID")
    _require(consumed < _instant(challenge["expiresAt"]), "CHALLENGE_EXPIRED")

    # 6. Owner credential and the WebAuthn signature over the V2 challenge.
    credential = _parse(P.OwnerCredentialV1.from_dict, owner_credential)
    _require(proof.credential_record_id == credential.record_id
             and proof.credential_id == credential.credential_id, "OWNER_CREDENTIAL_MISMATCH")
    _require(credential.owner_principal == context.owner_principal
             and credential.rp_id == context.rp_id, "OWNER_CREDENTIAL_NOT_AUTHORIZED")
    owner_credential_status = "ACTIVE"
    if credential.status == "REVOKED":
        _require(_instant(credential.revoked_at) > consumed, "OWNER_CREDENTIAL_REVOKED")
        owner_credential_status = "REVOKED_AFTER_AUTHORIZATION"
    _verify_webauthn(challenge, proof, credential, rp_id=context.rp_id, origin=context.origin)
    return VerifiedOwnerProofV1(challenge, record, proof, credential, consumed, owner_credential_status)


def _verify(context, action, challenge_json, challenge_record, assertion,
            owner_credential, evidence, broker_keys, admission) -> dict[str, Any]:
    owner = _verify_owner_proof(context, action, challenge_json, challenge_record, assertion, owner_credential)
    challenge, proof, credential = owner.challenge, owner.assertion, owner.credential
    consumed, owner_credential_status = owner.consumed_at, owner.owner_credential_status

    # 7. Broker evidence: known, in-scope key; valid signature; allowed release.
    _require(evidence is not None, "BROKER_EVIDENCE_MISSING")
    envelope = _parse(K.BrokerMemoryEvidenceEnvelopeV1.from_dict, evidence)
    keys = {}
    for raw_key in broker_keys:
        key = _parse(K.BrokerVerificationKeyV1.from_dict, raw_key)
        _require(key.broker_key_id not in keys, "MALFORMED_ARTIFACT")
        keys[key.broker_key_id] = key
    key = keys.get(envelope["brokerKeyId"])
    _require(key is not None, "BROKER_KEY_UNKNOWN")
    _require(key.deployment_environment == envelope["deploymentEnvironment"]
             and key.authority_domain == envelope["authorityDomain"], "BROKER_KEY_SCOPE_MISMATCH")
    try:
        Ed25519PublicKey.from_public_bytes(key.public_key).verify(envelope.signature, envelope.signing_bytes())
    except (InvalidSignature, ValueError) as exc:
        raise _Reject("BROKER_SIGNATURE_INVALID") from exc
    issued = _instant(envelope["issuedAt"])
    broker_key_status = "ACTIVE"
    if key.status == "REVOKED":
        _require(_instant(key.revoked_at) > issued, "BROKER_KEY_REVOKED")
        broker_key_status = "REVOKED_AFTER_ISSUANCE"
    _require(envelope["brokerRelease"] in context.broker_releases, "BROKER_RELEASE_NOT_ALLOWED")

    # 8. Evidence ↔ owner proof ↔ challenge. Broker evidence alone is not
    #    owner authority: it must bind this exact consumed owner proof.
    _require(envelope["evidenceNonce"] == challenge["challengeId"], "EVIDENCE_NONCE_MISMATCH")
    _require(envelope["challengeId"] == challenge["challengeId"]
             and envelope["challengeDigest"] == challenge.challenge_digest(), "EVIDENCE_CHALLENGE_MISMATCH")
    _require(envelope["credentialRecordId"] == credential.record_id
             and envelope["assertionDigest"] == K.assertion_digest(proof), "EVIDENCE_OWNER_PROOF_MISMATCH")
    _require(envelope["requestDigest"] == challenge["requestDigest"], "REQUEST_DIGEST_MISMATCH")
    _require((envelope["actionDigest"], envelope["payloadDigest"], envelope["deploymentEnvironment"],
              envelope["authorityDomain"], envelope["logicalOwnerId"], envelope["policyVersion"],
              envelope["registryTupleVersion"], envelope["ledgerEpoch"])
             == (challenge["actionDigest"], challenge["payloadDigest"], challenge["deploymentEnvironment"],
                 challenge["authorityDomain"], challenge["logicalOwnerId"], challenge["policyVersion"],
                 challenge["registryTupleVersion"], challenge["ledgerEpoch"]), "EVIDENCE_BINDING_MISMATCH")
    _require(issued >= consumed, "EVIDENCE_ORDER_INVALID")

    # 9. L04 admission and apply audit bound to this evidence. A row alone is
    #    not acceptance; an orphan row fails above for missing evidence.
    _require(admission is not None, "ADMISSION_EVIDENCE_MISSING")
    admitted = _parse(K.CanonicalAdmissionRecordV1.from_dict, admission)
    _require(admitted["admissionOutcome"] == "ACCEPTED", "ADMISSION_NOT_ACCEPTED")
    _require(admitted["brokerEvidenceId"] == envelope["evidenceId"]
             and (admitted["operation"], admitted["memoryClass"], admitted["subjectNamespace"],
                  admitted["subjectKey"], admitted["payloadDigest"], admitted["actionDigest"])
             == (action.operation, action.memory_class, action.subject_namespace, action.subject_key,
                 action.payload_digest, action.action_digest), "ADMISSION_BINDING_MISMATCH")
    if action.operation != C.CREATE:
        _require(admitted["memoryItemId"] == challenge["memoryItemId"], "ADMISSION_BINDING_MISMATCH")
    _require(admitted["proposalRefId"] == envelope["proposalRefId"]
             and admitted["epistemicBasis"] == envelope["epistemicBasis"], "PROVENANCE_MISMATCH")

    return {
        "semantics": ACCEPTANCE_SEMANTICS,
        "truthClaim": False,
        "epistemicBasis": admitted["epistemicBasis"],
        "operation": action.operation,
        "memoryClass": action.memory_class,
        "subjectNamespace": action.subject_namespace,
        "subjectKey": action.subject_key,
        "payloadDigest": action.payload_digest,
        "actionDigest": action.action_digest,
        "proposalRefId": admitted["proposalRefId"],
        "memoryItemId": admitted["memoryItemId"],
        "revisionId": admitted["revisionId"],
        "applyAuditId": admitted["applyAuditId"],
        "challengeId": challenge["challengeId"],
        "challengeDigest": challenge.challenge_digest(),
        "evidenceId": envelope["evidenceId"],
        "evidenceDigest": envelope.evidence_digest(),
        "brokerKeyId": envelope["brokerKeyId"],
        "brokerRelease": envelope["brokerRelease"],
        "brokerKeyStatus": broker_key_status,
        "ownerCredentialRecordId": credential.record_id,
        "ownerCredentialStatus": owner_credential_status,
        "logicalOwnerId": challenge["logicalOwnerId"],
        "authorityDomain": challenge["authorityDomain"],
        "deploymentEnvironment": challenge["deploymentEnvironment"],
        "policyVersion": challenge["policyVersion"],
        "registryTupleVersion": challenge["registryTupleVersion"],
        "ledgerEpoch": challenge["ledgerEpoch"],
    }
