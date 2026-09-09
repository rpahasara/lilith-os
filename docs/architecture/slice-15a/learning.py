"""Slice 15A deterministic career-event source adapter and candidate logic.

The adapter reads a closed projection of ``career_events`` through a SQLite
read-only connection.  It excludes free-form payloads and produces shadow
Learning metadata only.  Nothing in this module writes source state, calls a
model, or interacts with another cognitive owner.
"""

from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Tuple

try:
    from . import memory_contracts as C
except ImportError:  # deploy-exact flat-directory tests
    import memory_contracts as C


MAX_BATCH_RECORDS = 25
MAX_APPROVED_RECORD_BYTES = 512
MAX_APPROVED_BATCH_BYTES = MAX_BATCH_RECORDS * MAX_APPROVED_RECORD_BYTES
MAX_REFS_PER_CANDIDATE = 1

CAREER_STAGES = frozenset({
    "discovered", "applied", "recruiter_contact", "screening",
    "assessment", "interview", "final_interview", "offer", "rejected",
    "withdrawn", "closed",
})
CAREER_EVENT_TYPES = frozenset(f"career.{stage}" for stage in CAREER_STAGES)

SOURCE_FIELD_ALLOWLIST = (
    "id", "event_type", "entity_type", "entity_id", "source", "created_at",
)
SOURCE_SELECT_SQL = (
    "SELECT id, event_type, entity_type, entity_id, source, created_at "
    "FROM career_events WHERE id > ? ORDER BY id ASC LIMIT ?"
)

# The source schema is versioned as a whole, including columns that this adapter
# intentionally does not select.  A schema change must receive a new reviewed
# adapter version rather than silently changing source meaning.
EXPECTED_SOURCE_COLUMNS = (
    ("id", "INTEGER", 0, 1),
    ("event_type", "TEXT", 1, 0),
    ("entity_type", "TEXT", 1, 0),
    ("entity_id", "INTEGER", 0, 0),
    ("source", "TEXT", 0, 0),
    ("confidence", "REAL", 1, 0),
    ("payload_json", "TEXT", 0, 0),
    ("created_at", "TEXT", 1, 0),
    ("processed", "INTEGER", 1, 0),
)

_HEX64 = re.compile(r"^[0-9a-f]{64}$")
_SOURCE_REF_RE = re.compile(r"^career_events:[1-9][0-9]*$")
_SUBJECT_REF_RE = re.compile(r"^career\.application:[1-9][0-9]*$")
_CREATED_AT_FORMAT = "%Y-%m-%d %H:%M:%S"


class LearningSourceError(RuntimeError):
    code = "SOURCE_UNAVAILABLE"
    retryable = True


class SourceUnavailable(LearningSourceError):
    code = "SOURCE_UNAVAILABLE"
    retryable = True


class SourceSchemaMismatch(LearningSourceError):
    code = "SOURCE_SCHEMA_MISMATCH"
    retryable = False


class SourceTooLarge(LearningSourceError):
    code = "SOURCE_TOO_LARGE"
    retryable = False


class InvalidSourceRecord(LearningSourceError):
    code = "INVALID_SOURCE_RECORD"
    retryable = False


def _canonical_json(value: Mapping[str, Any]) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
    ).encode("ascii")


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _source_uri(path: Path) -> str:
    # The path is supplied by the operator, not source data.  Existence is
    # checked before connect so mode=ro can never create the source database.
    return f"file:{path.resolve().as_posix()}?mode=ro"


def _source_schema(conn: sqlite3.Connection) -> Tuple[Tuple[Any, ...], ...]:
    rows = conn.execute("PRAGMA table_info(career_events)").fetchall()
    return tuple(
        (str(row[1]), str(row[2]).upper(), int(row[3]), int(row[5]))
        for row in rows
    )


def validate_source_schema(conn: sqlite3.Connection) -> None:
    if _source_schema(conn) != EXPECTED_SOURCE_COLUMNS:
        raise SourceSchemaMismatch("career_events schema does not match source version 1")


class CareerEventsSource:
    """Read-only, bounded adapter for the career watcher's event stream."""

    def __init__(self, db_path: Path):
        self.db_path = Path(db_path)

    def read_batch(self, after_id: int, limit: int) -> List[Dict[str, Any]]:
        if isinstance(after_id, bool) or not isinstance(after_id, int) or after_id < 0:
            raise InvalidSourceRecord("after_id must be a non-negative integer")
        if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= MAX_BATCH_RECORDS:
            raise SourceTooLarge("source batch limit is outside the approved bound")
        if not self.db_path.is_file():
            raise SourceUnavailable("career source database is unavailable")

        try:
            conn = sqlite3.connect(_source_uri(self.db_path), uri=True, timeout=5.0)
        except sqlite3.Error as exc:
            raise SourceUnavailable("career source database could not be opened") from exc
        try:
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA query_only = ON")
            validate_source_schema(conn)
            rows = [dict(row) for row in conn.execute(SOURCE_SELECT_SQL, (after_id, limit))]
        except SourceSchemaMismatch:
            raise
        except sqlite3.Error as exc:
            raise SourceUnavailable("career source read failed") from exc
        finally:
            conn.close()

        approved_bytes = sum(len(_canonical_json(row)) for row in rows)
        if approved_bytes > MAX_APPROVED_BATCH_BYTES:
            raise SourceTooLarge("approved source batch exceeds the byte bound")
        return rows


def _normalized_occurred_at(value: Any) -> str:
    if not isinstance(value, str) or len(value) > 32:
        raise InvalidSourceRecord("created_at is invalid")
    try:
        parsed = datetime.strptime(value, _CREATED_AT_FORMAT).replace(tzinfo=timezone.utc)
    except ValueError as exc:
        raise InvalidSourceRecord("created_at is invalid") from exc
    return parsed.isoformat().replace("+00:00", "Z")


def build_source_record_ref(row: Mapping[str, Any]) -> Tuple[C.LearningSourceRecordRef, C.CareerEventCandidateDescriptor]:
    if set(row) != set(SOURCE_FIELD_ALLOWLIST):
        raise InvalidSourceRecord("source projection is not closed")

    record_id = row.get("id")
    entity_id = row.get("entity_id")
    event_type = row.get("event_type")
    entity_type = row.get("entity_type")
    source = row.get("source")

    if isinstance(record_id, bool) or not isinstance(record_id, int) or record_id <= 0:
        raise InvalidSourceRecord("source record id is invalid")
    if isinstance(entity_id, bool) or not isinstance(entity_id, int) or entity_id <= 0:
        raise InvalidSourceRecord("source entity id is invalid")
    if not isinstance(event_type, str) or len(event_type) > 64:
        raise SourceTooLarge("event type exceeds the approved bound")
    if event_type not in CAREER_EVENT_TYPES:
        raise InvalidSourceRecord("event type is outside the closed career vocabulary")
    if entity_type != "job_application":
        raise InvalidSourceRecord("entity type is outside the closed source contract")
    if source != "gmail":
        raise InvalidSourceRecord("source category is outside the closed source contract")

    occurred_at = _normalized_occurred_at(row.get("created_at"))
    subject_ref = f"career.application:{entity_id}"
    approved = {
        "createdAt": row["created_at"],
        "entityId": entity_id,
        "entityType": entity_type,
        "eventType": event_type,
        "id": record_id,
        "source": source,
        "sourceOwner": C.SOURCE_OWNER,
        "sourceSchemaVersion": C.SOURCE_SCHEMA_VERSION,
        "sourceStream": C.SOURCE_STREAM,
    }
    encoded = _canonical_json(approved)
    if len(encoded) > MAX_APPROVED_RECORD_BYTES:
        raise SourceTooLarge("approved source record exceeds the byte bound")
    digest = _sha256(encoded)
    ref = C.LearningSourceRecordRef(
        schema_version=C.SCHEMA_VERSION,
        source_owner=C.SOURCE_OWNER,
        source_stream=C.SOURCE_STREAM,
        source_record_id=record_id,
        source_schema_version=C.SOURCE_SCHEMA_VERSION,
        source_digest=digest,
        occurred_at=occurred_at,
        subject_refs=(subject_ref,),
        evidence_refs=(),
    )
    return ref, C.CareerEventCandidateDescriptor(event_type, subject_ref)


def derive_candidate(
    source_ref: C.LearningSourceRecordRef,
    descriptor: C.CareerEventCandidateDescriptor,
    created_at: str,
) -> C.LearningCandidate:
    source_ref_text = f"{source_ref.source_stream}:{source_ref.source_record_id}"
    fingerprint_value = {
        "candidateClass": C.CANDIDATE_CLASS,
        "descriptor": descriptor.to_dict(),
        "schemaVersion": C.SCHEMA_VERSION,
        "sourceDigest": source_ref.source_digest,
        "sourceOwner": source_ref.source_owner,
        "sourceRecordId": source_ref.source_record_id,
        "sourceSchemaVersion": source_ref.source_schema_version,
        "sourceStream": source_ref.source_stream,
    }
    fingerprint = _sha256(_canonical_json(fingerprint_value))
    return C.LearningCandidate(
        candidate_id="lcand." + fingerprint[:32],
        schema_version=C.SCHEMA_VERSION,
        candidate_class=C.CANDIDATE_CLASS,
        source_refs=(source_ref_text,),
        source_digests=(source_ref.source_digest,),
        subject_refs=source_ref.subject_refs,
        admission_basis=C.ADMISSION_BASIS,
        epistemic_basis=C.EPISTEMIC_BASIS,
        validation_state=C.VALID,
        idempotency_key="lcid." + fingerprint,
        created_at=created_at,
        descriptor=descriptor,
    )


def validate_candidate(candidate: C.LearningCandidate) -> C.CandidateValidationResult:
    valid = (
        candidate.schema_version == C.SCHEMA_VERSION
        and candidate.candidate_class == C.CANDIDATE_CLASS
        and candidate.admission_basis == C.ADMISSION_BASIS
        and candidate.epistemic_basis == C.EPISTEMIC_BASIS
        and candidate.validation_state == C.VALID
        and len(candidate.source_refs) == MAX_REFS_PER_CANDIDATE
        and len(candidate.source_digests) == MAX_REFS_PER_CANDIDATE
        and len(candidate.subject_refs) == MAX_REFS_PER_CANDIDATE
        and bool(_SOURCE_REF_RE.fullmatch(candidate.source_refs[0]))
        and bool(_HEX64.fullmatch(candidate.source_digests[0]))
        and bool(_SUBJECT_REF_RE.fullmatch(candidate.subject_refs[0]))
        and candidate.descriptor.event_type in CAREER_EVENT_TYPES
        and candidate.descriptor.subject_ref == candidate.subject_refs[0]
        and candidate.idempotency_key.startswith("lcid.")
        and len(candidate.idempotency_key) == 69
    )
    return C.CandidateValidationResult(
        C.VALID if valid else C.INVALID,
        C.VALIDATION_OK if valid else C.CANDIDATE_VALIDATION_FAILED,
    )


def assess_candidate(
    candidate: C.LearningCandidate,
    validation: C.CandidateValidationResult,
    assessed_at: str,
    defer_reason: Optional[str] = None,
) -> C.LearningAssessment:
    if validation.state != C.VALID:
        outcome = C.SHADOW_REJECTED
        reason = C.CANDIDATE_VALIDATION_FAILED
    elif defer_reason is not None:
        if defer_reason != C.NO_CANONICAL_LTM_APPLY_PATH:
            raise C.LearningContractError("unsupported shadow deferral reason")
        outcome = C.SHADOW_DEFERRED
        reason = defer_reason
    else:
        outcome = C.SHADOW_ELIGIBLE
        reason = C.SOURCE_EVENT_INFRASTRUCTURE_PROOF
    return C.LearningAssessment(
        candidate_id=candidate.candidate_id,
        schema_version=C.SCHEMA_VERSION,
        outcome=outcome,
        reason_code=reason,
        assessed_at=assessed_at,
    )
