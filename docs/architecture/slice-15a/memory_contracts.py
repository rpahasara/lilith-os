"""Slice 15A closed contracts for shadow Learning metadata.

These objects are not Long-Term Memory, current truth, Verifier results, or
storage-admission decisions.  Slice 15A contains no L04 apply contract.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Tuple


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


class LearningContractError(ValueError):
    """Raised when a Slice 15A object violates its closed contract."""


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
        return {
            "eventType": self.event_type,
            "subjectRef": self.subject_ref,
        }


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
