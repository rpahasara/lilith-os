"""Closed contracts for Slice 15A Learning and Slice 15B1 LTM proposals.

The proposal contract is immutable data.  It cannot mutate L04 storage, mint
Consent or Verification outcomes, select a revision identifier, or assign an
active pointer.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from typing import Any, Dict, Mapping, Optional, Tuple


SCHEMA_VERSION = 1
SOURCE_SCHEMA_VERSION = 1

SOURCE_OWNER = "CAREER_WATCHER"
SOURCE_STREAM = "career_events"
CURSOR_KIND = "INTEGER_EVENT_ID"

CANDIDATE_CLASS = "SOURCE_EVENT_CONSOLIDATION_CANDIDATE"
ADMISSION_BASIS = "SOURCE_EVENT_SHADOW_EVALUATION"
EPISTEMIC_BASIS = "SOURCE_EVENT"

VALID = "VALID"
INVALID = "INVALID"
VALIDATION_STATES = frozenset({VALID, INVALID})

SHADOW_ELIGIBLE = "SHADOW_ELIGIBLE"
SHADOW_REJECTED = "SHADOW_REJECTED"
SHADOW_DEFERRED = "SHADOW_DEFERRED"
ASSESSMENT_OUTCOMES = frozenset({
    SHADOW_ELIGIBLE, SHADOW_REJECTED, SHADOW_DEFERRED,
})

VALIDATION_OK = "VALIDATION_OK"
INVALID_SOURCE_RECORD = "INVALID_SOURCE_RECORD"
CANDIDATE_VALIDATION_FAILED = "CANDIDATE_VALIDATION_FAILED"
SOURCE_EVENT_INFRASTRUCTURE_PROOF = "SOURCE_EVENT_INFRASTRUCTURE_PROOF"
NO_CANONICAL_LTM_APPLY_PATH = "NO_CANONICAL_LTM_APPLY_PATH"

CREATE = "CREATE"
SUPERSEDE = "SUPERSEDE"
RESTORE = "RESTORE"
MEMORY_OPERATIONS = frozenset({CREATE, SUPERSEDE, RESTORE})

APPLY_OUTCOMES = frozenset({
    "APPLIED", "ALREADY_APPLIED", "REJECTED", "PRECONDITION_FAILED",
    "RETRYABLE_FAILURE",
})

_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_CLASS_RE = re.compile(r"^[A-Z][A-Z0-9_]{0,63}$")
_NAMESPACE_RE = re.compile(r"^[a-z][a-z0-9_.-]{0,63}$")
_BASIS_RE = re.compile(r"^[A-Z][A-Z0-9_]{0,63}$")
_HEX64_RE = re.compile(r"^[0-9a-f]{64}$")


class LearningContractError(ValueError):
    """Raised when a closed Learning/LTM proposal object is invalid."""


@dataclass(frozen=True)
class LearningSourceRecordRef:
    """Immutable reference to one source-owned career event snapshot."""

    schema_version: int
    source_owner: str
    source_stream: str
    source_record_id: int
    source_schema_version: int
    source_digest: str
    occurred_at: str
    subject_refs: Tuple[str, ...]
    evidence_refs: Tuple[str, ...] = ()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schemaVersion": self.schema_version,
            "sourceOwner": self.source_owner,
            "sourceStream": self.source_stream,
            "sourceRecordId": self.source_record_id,
            "sourceSchemaVersion": self.source_schema_version,
            "sourceDigest": self.source_digest,
            "occurredAt": self.occurred_at,
            "subjectRefs": list(self.subject_refs),
            "evidenceRefs": list(self.evidence_refs),
        }


@dataclass(frozen=True)
class CareerEventCandidateDescriptor:
    """Closed source-specific metadata; deliberately contains no prose."""

    event_type: str
    subject_ref: str

    def to_dict(self) -> Dict[str, str]:
        return {"eventType": self.event_type, "subjectRef": self.subject_ref}


@dataclass(frozen=True)
class LearningCandidate:
    """Durable shadow metadata, not a memory item or admission result."""

    candidate_id: str
    schema_version: int
    candidate_class: str
    source_refs: Tuple[str, ...]
    source_digests: Tuple[str, ...]
    subject_refs: Tuple[str, ...]
    admission_basis: str
    epistemic_basis: str
    validation_state: str
    idempotency_key: str
    created_at: str
    descriptor: CareerEventCandidateDescriptor

    def to_dict(self) -> Dict[str, Any]:
        return {
            "candidateId": self.candidate_id,
            "schemaVersion": self.schema_version,
            "candidateClass": self.candidate_class,
            "sourceRefs": list(self.source_refs),
            "sourceDigests": list(self.source_digests),
            "subjectRefs": list(self.subject_refs),
            "admissionBasis": self.admission_basis,
            "epistemicBasis": self.epistemic_basis,
            "validationState": self.validation_state,
            "idempotencyKey": self.idempotency_key,
            "createdAt": self.created_at,
            "descriptor": self.descriptor.to_dict(),
        }


@dataclass(frozen=True)
class CandidateValidationResult:
    state: str
    reason_code: str

    def __post_init__(self) -> None:
        if self.state not in VALIDATION_STATES:
            raise LearningContractError("unsupported validation state")


@dataclass(frozen=True)
class LearningAssessment:
    candidate_id: str
    schema_version: int
    outcome: str
    reason_code: str
    assessed_at: str

    def __post_init__(self) -> None:
        if self.outcome not in ASSESSMENT_OUTCOMES:
            raise LearningContractError("unsupported assessment outcome")


@dataclass(frozen=True)
class CandidateProvenanceBinding:
    """Exact persisted candidate meaning included in proposal fingerprints."""

    candidate_id: str
    candidate_schema_version: int
    candidate_class: str
    candidate_idempotency_key: str
    candidate_admission_basis: str
    candidate_epistemic_basis: str
    validation_state: str
    event_type: str
    subject_ref: str
    source_owner: str
    source_stream: str
    source_record_id: int
    source_schema_version: int
    source_digest: str
    occurred_at: str
    source_subject_ref: str

    def to_fingerprint_dict(self) -> Dict[str, Any]:
        return {
            "candidateId": self.candidate_id,
            "candidateSchemaVersion": self.candidate_schema_version,
            "candidateClass": self.candidate_class,
            "candidateIdempotencyKey": self.candidate_idempotency_key,
            "candidateAdmissionBasis": self.candidate_admission_basis,
            "candidateEpistemicBasis": self.candidate_epistemic_basis,
            "candidateValidationState": self.validation_state,
            "candidateEventType": self.event_type,
            "candidateSubjectRef": self.subject_ref,
            "sources": [{
                "sourceOwner": self.source_owner,
                "sourceStream": self.source_stream,
                "sourceRecordId": self.source_record_id,
                "sourceSchemaVersion": self.source_schema_version,
                "sourceDigest": self.source_digest,
                "subjectRef": self.source_subject_ref,
            }],
        }


def _require_optional_id(value: Optional[str], field_name: str) -> None:
    if value is not None and not _ID_RE.fullmatch(value):
        raise LearningContractError(f"{field_name} is invalid")


def normalize_proposed_value(value: Mapping[str, Any]) -> Tuple[str, str]:
    """Canonicalize a class-validated object; this does not validate its class."""
    if not isinstance(value, Mapping):
        raise LearningContractError("proposed value must be an object")
    try:
        encoded = json.dumps(
            dict(value), sort_keys=True, separators=(",", ":"), ensure_ascii=True,
            allow_nan=False,
        )
    except (TypeError, ValueError) as exc:
        raise LearningContractError("proposed value is not canonical JSON") from exc
    if len(encoded.encode("ascii")) > 2048:
        raise LearningContractError("proposed value exceeds the V1 bound")
    return encoded, hashlib.sha256(encoded.encode("ascii")).hexdigest()


@dataclass(frozen=True)
class MemoryWriteProposal:
    """Immutable L18 request. It has no L04 mutation capability."""

    proposal_id: str
    candidate_id: str
    schema_version: int
    operation: str
    target_memory_class: str
    subject_namespace: str
    subject_key: str
    expected_active_revision_id: Optional[str]
    restore_revision_id: Optional[str]
    value_schema: Optional[str]
    proposed_value_json: Optional[str]
    proposed_value_digest: Optional[str]
    admission_basis: str
    epistemic_basis: str
    consent_ref_id: Optional[str]
    verification_outcome_ref_id: Optional[str]
    rollback_authorization_ref_id: Optional[str]
    proposal_fingerprint: str
    created_at: str

    def validate(self) -> None:
        if self.schema_version != SCHEMA_VERSION:
            raise LearningContractError("proposal schema version is unsupported")
        if not _ID_RE.fullmatch(self.proposal_id) or not _ID_RE.fullmatch(self.candidate_id):
            raise LearningContractError("proposal or candidate identifier is invalid")
        if self.operation not in MEMORY_OPERATIONS:
            raise LearningContractError("proposal operation is unsupported")
        if not _CLASS_RE.fullmatch(self.target_memory_class):
            raise LearningContractError("memory class is invalid")
        if not _NAMESPACE_RE.fullmatch(self.subject_namespace):
            raise LearningContractError("subject namespace is invalid")
        if not _ID_RE.fullmatch(self.subject_key):
            raise LearningContractError("subject key is invalid")
        if not _BASIS_RE.fullmatch(self.admission_basis) or not _BASIS_RE.fullmatch(self.epistemic_basis):
            raise LearningContractError("proposal basis is invalid")
        for name, value in (
            ("expectedActiveRevisionId", self.expected_active_revision_id),
            ("restoreRevisionId", self.restore_revision_id),
            ("consentRefId", self.consent_ref_id),
            ("verificationOutcomeRefId", self.verification_outcome_ref_id),
            ("rollbackAuthorizationRefId", self.rollback_authorization_ref_id),
        ):
            _require_optional_id(value, name)
        if not _HEX64_RE.fullmatch(self.proposal_fingerprint):
            raise LearningContractError("proposal fingerprint is invalid")
        if self.operation in {CREATE, SUPERSEDE}:
            if not self.value_schema or not _ID_RE.fullmatch(self.value_schema):
                raise LearningContractError("value schema is required")
            if self.proposed_value_json is None or self.proposed_value_digest is None:
                raise LearningContractError("proposed value and digest are required")
            try:
                decoded = json.loads(self.proposed_value_json)
            except (TypeError, ValueError) as exc:
                raise LearningContractError("proposed value JSON is invalid") from exc
            normalized, digest = normalize_proposed_value(decoded)
            if normalized != self.proposed_value_json or digest != self.proposed_value_digest:
                raise LearningContractError("proposed value is not normalized")
        if self.operation == CREATE and (
            self.expected_active_revision_id is not None
            or self.restore_revision_id is not None
            or self.rollback_authorization_ref_id is not None
        ):
            raise LearningContractError("CREATE proposal shape is invalid")
        if self.operation == SUPERSEDE and (
            self.expected_active_revision_id is None
            or self.restore_revision_id is not None
            or self.rollback_authorization_ref_id is not None
        ):
            raise LearningContractError("SUPERSEDE proposal shape is invalid")
        if self.operation == RESTORE and (
            self.expected_active_revision_id is None
            or self.restore_revision_id is None
            or self.rollback_authorization_ref_id is None
            or self.value_schema is not None
            or self.proposed_value_json is not None
            or self.proposed_value_digest is not None
        ):
            raise LearningContractError("RESTORE proposal shape is invalid")

    def fingerprint_dict(self, binding: CandidateProvenanceBinding) -> Dict[str, Any]:
        return {
            "candidate": binding.to_fingerprint_dict(),
            "proposalSchemaVersion": self.schema_version,
            "operation": self.operation,
            "targetMemoryClass": self.target_memory_class,
            "subjectNamespace": self.subject_namespace,
            "subjectKey": self.subject_key,
            "expectedActiveRevisionId": self.expected_active_revision_id,
            "restoreRevisionId": self.restore_revision_id,
            "valueSchema": self.value_schema,
            "proposedValueDigest": self.proposed_value_digest,
            "admissionBasis": self.admission_basis,
            "epistemicBasis": self.epistemic_basis,
            "consentRefId": self.consent_ref_id,
            "verificationOutcomeRefId": self.verification_outcome_ref_id,
            "rollbackAuthorizationRefId": self.rollback_authorization_ref_id,
        }

    def to_dict(self) -> Dict[str, Any]:
        return {
            "proposalId": self.proposal_id,
            "candidateId": self.candidate_id,
            "schemaVersion": self.schema_version,
            "operation": self.operation,
            "targetMemoryClass": self.target_memory_class,
            "subjectNamespace": self.subject_namespace,
            "subjectKey": self.subject_key,
            "expectedActiveRevisionId": self.expected_active_revision_id,
            "restoreRevisionId": self.restore_revision_id,
            "valueSchema": self.value_schema,
            "proposedValue": json.loads(self.proposed_value_json) if self.proposed_value_json else None,
            "proposedValueDigest": self.proposed_value_digest,
            "admissionBasis": self.admission_basis,
            "epistemicBasis": self.epistemic_basis,
            "consentRefId": self.consent_ref_id,
            "verificationOutcomeRefId": self.verification_outcome_ref_id,
            "rollbackAuthorizationRefId": self.rollback_authorization_ref_id,
            "proposalFingerprint": self.proposal_fingerprint,
            "createdAt": self.created_at,
        }


def compute_proposal_fingerprint(
    proposal: MemoryWriteProposal,
    binding: CandidateProvenanceBinding,
) -> str:
    payload = json.dumps(
        proposal.fingerprint_dict(binding), sort_keys=True, separators=(",", ":"),
        ensure_ascii=True, allow_nan=False,
    ).encode("ascii")
    return hashlib.sha256(payload).hexdigest()


@dataclass(frozen=True)
class AdmissionDecision:
    proposal_id: str
    outcome: str
    failure_code: Optional[str]
    evaluated_at: str


@dataclass(frozen=True)
class MemoryApplyResult:
    proposal_id: str
    outcome: str
    failure_code: Optional[str]
    memory_item_id: Optional[str]
    revision_id: Optional[str]
    active_revision_id: Optional[str]
    operation_id: Optional[str]

    def __post_init__(self) -> None:
        if self.outcome not in APPLY_OUTCOMES:
            raise LearningContractError("unsupported apply outcome")
