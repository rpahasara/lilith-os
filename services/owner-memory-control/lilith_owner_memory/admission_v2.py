"""15B2b-B1b-3b V2 owner-authority chain, admission link, and acceptance (TEST-ONLY).

Design: docs/architecture/slice-15b2b-b1b3-custody-isolation-design.md.

Four distinct stages, never collapsed:

    VERIFIED_AUTHORITY_EVIDENCE  (B1b-3a verifier: a registry key signed it)
    != L04_ADMITTED              (L04 V2 adapter: L04 applied it, linked to evidence)
    != ACCEPTED_MEMORY           (this module: the complete chain re-verifies)
    != TRUTH                     (never claimed; the epistemic basis is unchanged)

For the V2 path only asymmetric OwnerEvidenceV2, signed by a key published
in an owner-signed registry, can authorize. Legacy V1 `ActorEvidenceRefV1`
(application-owned HMAC) and the B2a TEST broker envelope are recognised and
refused here; their historical semantics elsewhere are untouched. Policy,
Consent, Rollback and ActorEvidenceRefV1 rows are internal L04 state, never
authority: nothing in this module reads them.

`AdmissionAuthorityLinkV1` is the smallest TEST-level link between an L04
admission and the exact evidence that authorized it. The current L04 schema
has no such column; a production schema migration is required before any
live V2 admission (see the B1b-3b implementation record).

This module holds public verification material only. It never signs, never
imports a signer, and reads only its arguments.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Any, Mapping

from lilith_memory import canonical_contracts as C
from lilith_memory.owner_proof import OwnerProofError, _digest, _exact, _id, _instant, _optional_id

from . import authority_contracts as A
from . import authority_verifier as AV
from . import contracts as K
from . import verifier as B2A

ACCEPTED_MEMORY = B2A.ACCEPTED_MEMORY
NOT_ACCEPTED = "NOT_ACCEPTED"
VERIFIED_OWNER_AUTHORITY = "VERIFIED_OWNER_AUTHORITY"
ACCEPTANCE_V2_SEMANTICS = "OWNER_AUTHORIZED_AUTHORITY_SIGNED_L04_ADMITTED_NOT_A_TRUTH_CLAIM"

# The unchanged L04 V2 apply writes exactly these bases for every admission.
# OwnerEvidenceV2 does not sign an epistemic basis, so acceptance pins them:
# any other value means the row was not produced by that apply.
L04_V2_EPISTEMIC_BASIS = "USER_ASSERTED"
L04_V2_ADMISSION_BASIS = "OWNER_DIRECTED_EXACT_ACTION"

ACTOR_EVIDENCE_REF_V1 = "ACTOR_EVIDENCE_REF_V1"
B2A_BROKER_EVIDENCE_V1 = "B2A_BROKER_EVIDENCE_V1"

# Closed, ordered NOT_ACCEPTED reason taxonomy shared by the V2 adapter and
# the V2 acceptance verifier. `detail` carries the underlying B2a owner-proof
# reason, B1b-3a authority reason, legacy kind, or L04 outcome.
REASONS = (
    "MALFORMED_CONTEXT",
    "AUTHORITY_EVIDENCE_MISSING",
    "NON_V2_EVIDENCE_NOT_ACCEPTED",
    "PROPOSAL_UNRESOLVED",
    "PRIVACY_OWNED_OPERATION",
    "PRIVACY_STATE_UNAVAILABLE",
    "PRIVACY_HOLD_ACTIVE",
    "OWNER_PROOF_REJECTED",
    "CHALLENGE_AUTHORITY_CONTEXT_MISMATCH",
    "AUTHORITY_EVIDENCE_REJECTED",
    "EVIDENCE_ORDER_INVALID",
    "EVIDENCE_ALREADY_CONSUMED",
    "L04_NOT_ADMITTED",
    "ADMISSION_LINK_MISSING",
    "ADMISSION_LINK_MALFORMED",
    "ADMISSION_LINK_MISMATCH",
    "ADMISSION_MISSING",
    "ADMISSION_MALFORMED",
    "ADMISSION_NOT_ACCEPTED",
    "ADMISSION_BINDING_MISMATCH",
)


class Reject(Exception):
    def __init__(self, reason: str, detail: str | None = None):
        assert reason in REASONS, reason
        self.reason = reason
        self.detail = detail


def require(condition: bool, reason: str, detail: str | None = None) -> None:
    if not condition:
        raise Reject(reason, detail)


@dataclass(frozen=True)
class V2ResultV1:
    status: str
    reason: str | None = None
    detail: str | None = None
    facts: Mapping[str, Any] = field(default_factory=dict)


def evidence_digest(evidence: Mapping[str, Any]) -> str:
    """SHA-256 over the exact signed bytes (separator ‖ canonical fields)."""
    return hashlib.sha256(A.OwnerEvidenceV2.from_dict(evidence).signing_bytes()).hexdigest()


def non_v2_evidence_kind(evidence: Any) -> str | None:
    """Recognise evidence that must never authorize the V2 path."""
    if isinstance(evidence, C.ActorEvidenceRefV1):
        return ACTOR_EVIDENCE_REF_V1
    if isinstance(evidence, Mapping):
        if {"actorEvidenceRefId", "evidenceFingerprint"} & set(evidence) \
                or {"actor_evidence_ref_id", "evidence_fingerprint"} & set(evidence):
            return ACTOR_EVIDENCE_REF_V1
        if evidence.get("protocol") == K.EVIDENCE_PROTOCOL or "brokerKeyId" in evidence:
            return B2A_BROKER_EVIDENCE_V1
    return None


@dataclass(frozen=True)
class VerifiedOwnerAuthorityV1:
    """Owner proof (B2a steps 1-6) plus verified OwnerEvidenceV2 bound to it.
    Authority only: not an admission and not ACCEPTED_MEMORY."""

    owner: B2A.VerifiedOwnerProofV1
    evidence: A.OwnerEvidenceV2
    evidence_digest: str
    authority_facts: Mapping[str, Any]


def verify_owner_authority(
    *,
    owner_context: K.AcceptanceContextV1,
    authority_context: A.AuthorityVerificationContextV1,
    action: C.FrozenMemoryActionV1,
    challenge_json: bytes | None,
    challenge_record: Mapping[str, Any] | None,
    assertion: Mapping[str, Any] | None,
    owner_credential: Mapping[str, Any] | None,
    registry: Mapping[str, Any] | None,
    evidence: Any,
    expected_evidence_id: str | None,
) -> VerifiedOwnerAuthorityV1:
    """Verify owner proof → OwnerEvidenceV2 → registry. Raises `Reject`.

    `expected_evidence_id` is the independently known evidence identity (the
    admission link, for acceptance). None means "the evidence names itself",
    which is only used at admission time, before any link exists.
    """
    require(isinstance(owner_context, K.AcceptanceContextV1)
            and isinstance(authority_context, A.AuthorityVerificationContextV1), "MALFORMED_CONTEXT")
    require(owner_context.deployment_environment == authority_context.environment, "MALFORMED_CONTEXT")
    require(evidence is not None, "AUTHORITY_EVIDENCE_MISSING")
    legacy = non_v2_evidence_kind(evidence)
    require(legacy is None, "NON_V2_EVIDENCE_NOT_ACCEPTED", legacy)
    require(isinstance(action, C.FrozenMemoryActionV1), "PROPOSAL_UNRESOLVED")
    require(action.operation != C.FORGET, "PRIVACY_OWNED_OPERATION")

    owner = B2A.verify_owner_proof(context=owner_context, action=action, challenge_json=challenge_json,
                                   challenge_record=challenge_record, assertion=assertion,
                                   owner_credential=owner_credential)
    require(owner.verified, "OWNER_PROOF_REJECTED", owner.reason)
    proof = owner.proof
    challenge = proof.challenge
    # The owner challenge and the authority context must name the same policy.
    require(challenge["policyVersion"] == authority_context.policy_version,
            "CHALLENGE_AUTHORITY_CONTEXT_MISMATCH")

    if expected_evidence_id is None:
        claimed = evidence.get("evidenceId") if isinstance(evidence, Mapping) else None
        expected_evidence_id = claimed if isinstance(claimed, str) else ""
    expectation = A.OwnerEvidenceExpectationV2(
        evidence_id=expected_evidence_id,
        challenge_id=challenge["challengeId"],
        challenge_digest=challenge.challenge_digest(),
        credential_record_id=proof.credential.record_id,
        assertion_digest=proof.assertion_digest,
        action_digest=action.action_digest,
        request_digest=challenge["requestDigest"],
        payload_digest=action.payload_digest,
        logical_owner_id=owner_context.logical_owner_id,
        authority_domain=owner_context.authority_domain,
    )
    result = AV.verify_owner_evidence(context=authority_context, registry=registry,
                                      evidence=evidence, expectation=expectation)
    require(result.verified, "AUTHORITY_EVIDENCE_REJECTED", result.reason)
    envelope = A.OwnerEvidenceV2.from_dict(evidence)
    # Evidence can only follow the consumption it attests.
    require(envelope.issued_at >= proof.consumed_at, "EVIDENCE_ORDER_INVALID")
    return VerifiedOwnerAuthorityV1(proof, envelope, hashlib.sha256(envelope.signing_bytes()).hexdigest(),
                                    result.facts)


# ------------------------------------------------------------ admission ---

LINK_FIELDS = frozenset({
    "schemaVersion", "proposalRefId", "admissionId", "applyAuditId", "memoryItemId",
    "revisionId", "authorityEvidenceId", "authorityEvidenceDigest", "challengeId",
    "actionDigest", "payloadDigest",
})


@dataclass(frozen=True)
class AdmissionAuthorityLinkV1:
    """TEST-ONLY link: this L04 admission was authorized by exactly this
    OwnerEvidenceV2 (identified by ID and by digest of its signed bytes).

    It is application-held metadata and carries no authority by itself: the
    acceptance verifier re-verifies the evidence it names and every binding.
    """

    fields: Mapping[str, Any]

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> AdmissionAuthorityLinkV1:
        _exact(value, LINK_FIELDS)
        if type(value["schemaVersion"]) is not int or value["schemaVersion"] != 1:
            raise K.ContractViolation("UNSUPPORTED_SCHEMA_VERSION")
        for name in ("proposalRefId", "admissionId", "applyAuditId", "memoryItemId", "revisionId",
                     "authorityEvidenceId", "challengeId"):
            _id(value[name], name)
        for name in ("authorityEvidenceDigest", "actionDigest", "payloadDigest"):
            _digest(value[name], name)
        return cls(dict(value))

    def __getitem__(self, name: str) -> Any:
        return self.fields[name]


ADMISSION_VIEW_FIELDS = frozenset({
    "schemaVersion", "proposalRefId", "admissionId", "admissionOutcome", "applyAuditId",
    "memoryItemId", "revisionId", "operation", "memoryClass", "subjectNamespace",
    "subjectKey", "payloadDigest", "actionDigest", "epistemicBasis", "admissionBasis",
})


@dataclass(frozen=True)
class L04AdmissionViewV1:
    """TEST-ONLY typed view of one L04 admission, read from the unchanged L04
    rows (memory_admission, memory_apply_audit, memory_revision, memory_item)
    plus the proposal's action digest. A view is data, never authority."""

    fields: Mapping[str, Any]

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> L04AdmissionViewV1:
        _exact(value, ADMISSION_VIEW_FIELDS)
        if type(value["schemaVersion"]) is not int or value["schemaVersion"] != 1:
            raise K.ContractViolation("UNSUPPORTED_SCHEMA_VERSION")
        K._choice(value["admissionOutcome"], K.ADMISSION_OUTCOMES, "admission_outcome")
        for name in ("proposalRefId", "admissionId", "memoryClass", "subjectNamespace", "subjectKey"):
            _id(value[name], name)
        for name in ("applyAuditId", "memoryItemId", "revisionId"):
            _optional_id(value[name], name)
        _optional_id(value["operation"], "operation")
        _digest(value["actionDigest"], "action_digest")
        if value["payloadDigest"] is not None:
            _digest(value["payloadDigest"], "payload_digest")
        for name in ("epistemicBasis", "admissionBasis"):
            if value[name] is not None:
                K._pattern(value[name], K._BASIS, name)
        if (value["admissionOutcome"] == "ACCEPTED") != (value["applyAuditId"] is not None):
            raise K.ContractViolation("INVALID_ADMISSION_SHAPE")
        return cls(dict(value))

    def __getitem__(self, name: str) -> Any:
        return self.fields[name]


def _parse(parser, value, reason: str):
    try:
        return parser(value)
    except (OwnerProofError, KeyError, TypeError, ValueError, AttributeError) as exc:
        raise Reject(reason) from exc


def check_admission_link(authority: VerifiedOwnerAuthorityV1, action: C.FrozenMemoryActionV1,
                         admission: Any, link: Any) -> tuple[L04AdmissionViewV1, AdmissionAuthorityLinkV1]:
    """Bind an L04 admission view and its link to verified authority."""
    require(link is not None, "ADMISSION_LINK_MISSING")
    linked = _parse(AdmissionAuthorityLinkV1.from_dict, link, "ADMISSION_LINK_MALFORMED")
    envelope = authority.evidence
    require((linked["authorityEvidenceId"], linked["authorityEvidenceDigest"], linked["challengeId"],
             linked["actionDigest"], linked["payloadDigest"])
            == (envelope["evidenceId"], authority.evidence_digest, envelope["challengeId"],
                envelope["actionDigest"], envelope["payloadDigest"]), "ADMISSION_LINK_MISMATCH")
    require(admission is not None, "ADMISSION_MISSING")
    admitted = _parse(L04AdmissionViewV1.from_dict, admission, "ADMISSION_MALFORMED")
    require(admitted["admissionOutcome"] == "ACCEPTED", "ADMISSION_NOT_ACCEPTED")
    require((linked["proposalRefId"], linked["admissionId"], linked["applyAuditId"], linked["memoryItemId"],
             linked["revisionId"])
            == (admitted["proposalRefId"], admitted["admissionId"], admitted["applyAuditId"],
                admitted["memoryItemId"], admitted["revisionId"]), "ADMISSION_LINK_MISMATCH")
    require((admitted["operation"], admitted["memoryClass"], admitted["subjectNamespace"], admitted["subjectKey"],
             admitted["payloadDigest"], admitted["actionDigest"])
            == (action.operation, action.memory_class, action.subject_namespace, action.subject_key,
                action.payload_digest, action.action_digest), "ADMISSION_BINDING_MISMATCH")
    if action.operation != C.CREATE:
        require(admitted["memoryItemId"] == authority.owner.challenge["memoryItemId"], "ADMISSION_BINDING_MISMATCH")
    require((admitted["epistemicBasis"], admitted["admissionBasis"])
            == (L04_V2_EPISTEMIC_BASIS, L04_V2_ADMISSION_BASIS), "ADMISSION_BINDING_MISMATCH")
    return admitted, linked


def verify_accepted_memory_v2(
    *,
    owner_context: K.AcceptanceContextV1,
    authority_context: A.AuthorityVerificationContextV1,
    action: C.FrozenMemoryActionV1 | None,
    challenge_json: bytes | None,
    challenge_record: Mapping[str, Any] | None,
    assertion: Mapping[str, Any] | None,
    owner_credential: Mapping[str, Any] | None,
    registry: Mapping[str, Any] | None,
    evidence: Any,
    admission: Mapping[str, Any] | None,
    link: Mapping[str, Any] | None,
) -> V2ResultV1:
    """ACCEPTED_MEMORY only when owner proof → broker-signed OwnerEvidenceV2 →
    registry → linked L04 admission all verify. Never a truth claim.

    The evidence identity is taken from the link, independently of the
    evidence. `authority_context.purpose` may be NEW_ADMISSION (verifying at
    admission time) or HISTORICAL_VERIFICATION (re-verifying later, where
    routine retirement keeps pre-retirement evidence valid and compromise
    remains retroactive).
    """
    try:
        require(isinstance(owner_context, K.AcceptanceContextV1)
                and isinstance(authority_context, A.AuthorityVerificationContextV1)
                and owner_context.deployment_environment == authority_context.environment, "MALFORMED_CONTEXT")
        require(link is None or isinstance(link, Mapping), "ADMISSION_LINK_MALFORMED")
        expected_id = link.get("authorityEvidenceId") if isinstance(link, Mapping) else None
        if link is None:
            # No independent evidence identity exists: fail as a missing link
            # only after evidence presence/kind, so DB-only rows report the
            # missing authority first.
            require(evidence is not None, "AUTHORITY_EVIDENCE_MISSING")
            require(non_v2_evidence_kind(evidence) is None, "NON_V2_EVIDENCE_NOT_ACCEPTED",
                    non_v2_evidence_kind(evidence))
            require(False, "ADMISSION_LINK_MISSING")
        authority = verify_owner_authority(
            owner_context=owner_context, authority_context=authority_context, action=action,
            challenge_json=challenge_json, challenge_record=challenge_record, assertion=assertion,
            owner_credential=owner_credential, registry=registry, evidence=evidence,
            expected_evidence_id=expected_id if isinstance(expected_id, str) else "")
        admitted, linked = check_admission_link(authority, action, admission, link)
    except Reject as rejected:
        return V2ResultV1(NOT_ACCEPTED, rejected.reason, rejected.detail)
    challenge = authority.owner.challenge
    return V2ResultV1(ACCEPTED_MEMORY, None, None, {
        "semantics": ACCEPTANCE_V2_SEMANTICS,
        "stage": ACCEPTED_MEMORY,
        "truthClaim": False,
        "epistemicBasis": admitted["epistemicBasis"],
        "admissionBasis": admitted["admissionBasis"],
        "operation": action.operation,
        "memoryClass": action.memory_class,
        "subjectNamespace": action.subject_namespace,
        "subjectKey": action.subject_key,
        "payloadDigest": action.payload_digest,
        "actionDigest": action.action_digest,
        "proposalRefId": admitted["proposalRefId"],
        "admissionId": admitted["admissionId"],
        "applyAuditId": admitted["applyAuditId"],
        "memoryItemId": admitted["memoryItemId"],
        "revisionId": admitted["revisionId"],
        "challengeId": challenge["challengeId"],
        "challengeDigest": challenge.challenge_digest(),
        "ownerCredentialRecordId": authority.owner.credential.record_id,
        "ownerCredentialStatus": authority.owner.owner_credential_status,
        "authorityEvidenceId": linked["authorityEvidenceId"],
        "authorityEvidenceDigest": authority.evidence_digest,
        "authority": dict(authority.authority_facts),
    })
