"""Durable Slice 15A Learning ledger.

The database contains only L18-owned job, cursor, candidate, provenance, and
shadow-assessment metadata.  It contains no L04 memory tables or retrieval
surface.  Schema creation is explicit through :func:`migrate`; normal worker
opens never create or migrate a database implicitly.
"""

from __future__ import annotations

import hashlib
import os
import sqlite3
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

try:
    from . import memory_contracts as C
except ImportError:  # deploy-exact flat-directory tests
    import memory_contracts as C


SCHEMA_VERSION = 1
DEFAULT_LEASE_SECONDS = 60
MAX_ATTEMPTS = 3
DEFAULT_LEDGER_CAPACITY = 10_000

QUEUED = "QUEUED"
LEASED = "LEASED"
SUCCEEDED = "SUCCEEDED"
FAILED_TERMINAL = "FAILED_TERMINAL"
CANCELLED = "CANCELLED"
JOB_STATUSES = frozenset({QUEUED, LEASED, SUCCEEDED, FAILED_TERMINAL, CANCELLED})

FAILURE_CODES = frozenset({
    "SOURCE_UNAVAILABLE",
    "SOURCE_SCHEMA_MISMATCH",
    "SOURCE_TOO_LARGE",
    "INVALID_SOURCE_RECORD",
    "CANDIDATE_VALIDATION_FAILED",
    "DB_BUSY",
    "LEASE_LOST",
    "LEASE_EXPIRED",
    "CURSOR_CONFLICT",
    "CAPACITY_PAUSED",
})

ALLOWED_TABLES = frozenset({
    "learning_schema_migration",
    "learning_job",
    "learning_cursor",
    "learning_candidate",
    "learning_candidate_source",
    "learning_assessment",
})


# Slice 15B1 adds a durable L18 proposal handoff and L04-owned tables.  The
# original Slice 15A migration fingerprint remains scoped to its exact V1
# objects; the new migration authority fingerprints every 15B1 object.
PROPOSAL_TABLES = frozenset({"learning_proposal"})
SHARED_L04_TABLES = frozenset({
    "memory_schema_migration", "memory_item", "memory_revision",
    "memory_revision_source", "memory_active_revision", "memory_admission",
    "memory_apply_audit",
})
KNOWN_COGNITIVE_TABLES = ALLOWED_TABLES | PROPOSAL_TABLES | SHARED_L04_TABLES

# Slice 15B2a canonical memory authority foundations: additive owner tables are recognized but never writable by L18 V1.
try:
    from .slice15b2a_migration import COGNITIVE_15B2A_TABLES as _SLICE15B2A_TABLES
except ImportError:  # older isolated Slice 15A/15B1 fixtures
    _SLICE15B2A_TABLES = frozenset()
KNOWN_COGNITIVE_TABLES = KNOWN_COGNITIVE_TABLES | _SLICE15B2A_TABLES
L18_V1_SCHEMA_OBJECTS = ALLOWED_TABLES | frozenset({
    "learning_job_one_open_stream", "learning_candidate_source_record",
})

_STAGE_SQL = ",".join(f"'{value}'" for value in sorted({
    "career.discovered", "career.applied", "career.recruiter_contact",
    "career.screening", "career.assessment", "career.interview",
    "career.final_interview", "career.offer", "career.rejected",
    "career.withdrawn", "career.closed",
}))
_FAILURE_SQL = ",".join(f"'{value}'" for value in sorted(FAILURE_CODES))

MIGRATION_STATEMENTS = (
    """
    CREATE TABLE IF NOT EXISTS learning_schema_migration (
        version INTEGER PRIMARY KEY,
        schema_fingerprint TEXT NOT NULL,
        applied_at TEXT NOT NULL
    )
    """,
    f"""
    CREATE TABLE IF NOT EXISTS learning_job (
        job_id TEXT PRIMARY KEY,
        schema_version INTEGER NOT NULL CHECK (schema_version = 1),
        mode TEXT NOT NULL CHECK (mode = 'SHADOW'),
        source_owner TEXT NOT NULL CHECK (source_owner = 'CAREER_WATCHER'),
        source_stream TEXT NOT NULL CHECK (source_stream = 'career_events'),
        cursor_from INTEGER NOT NULL CHECK (cursor_from >= 0),
        cursor_through INTEGER CHECK (cursor_through IS NULL OR cursor_through >= cursor_from),
        status TEXT NOT NULL CHECK (status IN ('QUEUED','LEASED','SUCCEEDED','FAILED_TERMINAL','CANCELLED')),
        lease_owner TEXT,
        lease_token TEXT,
        lease_expires_at TEXT,
        attempt_count INTEGER NOT NULL DEFAULT 0 CHECK (attempt_count >= 0),
        created_at TEXT NOT NULL,
        started_at TEXT,
        completed_at TEXT,
        failure_code TEXT CHECK (failure_code IS NULL OR failure_code IN ({_FAILURE_SQL})),
        CHECK (
            (status = 'LEASED' AND lease_owner IS NOT NULL AND lease_token IS NOT NULL AND lease_expires_at IS NOT NULL)
            OR
            (status <> 'LEASED' AND lease_owner IS NULL AND lease_token IS NULL AND lease_expires_at IS NULL)
        )
    )
    """,
    """
    CREATE UNIQUE INDEX IF NOT EXISTS learning_job_one_open_stream
    ON learning_job(source_owner, source_stream)
    WHERE status IN ('QUEUED', 'LEASED')
    """,
    """
    CREATE TABLE IF NOT EXISTS learning_cursor (
        source_owner TEXT NOT NULL CHECK (source_owner = 'CAREER_WATCHER'),
        source_stream TEXT NOT NULL CHECK (source_stream = 'career_events'),
        cursor_kind TEXT NOT NULL CHECK (cursor_kind = 'INTEGER_EVENT_ID'),
        committed_value INTEGER NOT NULL CHECK (committed_value >= 0),
        source_schema_version INTEGER NOT NULL CHECK (source_schema_version = 1),
        updated_at TEXT NOT NULL,
        PRIMARY KEY (source_owner, source_stream)
    )
    """,
    f"""
    CREATE TABLE IF NOT EXISTS learning_candidate (
        candidate_id TEXT PRIMARY KEY,
        schema_version INTEGER NOT NULL CHECK (schema_version = 1),
        candidate_class TEXT NOT NULL CHECK (candidate_class = 'SOURCE_EVENT_CONSOLIDATION_CANDIDATE'),
        admission_basis TEXT NOT NULL CHECK (admission_basis = 'SOURCE_EVENT_SHADOW_EVALUATION'),
        epistemic_basis TEXT NOT NULL CHECK (epistemic_basis = 'SOURCE_EVENT'),
        validation_state TEXT NOT NULL CHECK (validation_state IN ('VALID','INVALID')),
        idempotency_key TEXT NOT NULL UNIQUE,
        event_type TEXT NOT NULL CHECK (event_type IN ({_STAGE_SQL})),
        subject_ref TEXT NOT NULL,
        created_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS learning_candidate_source (
        candidate_id TEXT PRIMARY KEY REFERENCES learning_candidate(candidate_id),
        source_owner TEXT NOT NULL CHECK (source_owner = 'CAREER_WATCHER'),
        source_stream TEXT NOT NULL CHECK (source_stream = 'career_events'),
        source_record_id INTEGER NOT NULL CHECK (source_record_id > 0),
        source_schema_version INTEGER NOT NULL CHECK (source_schema_version = 1),
        source_digest TEXT NOT NULL CHECK (length(source_digest) = 64),
        occurred_at TEXT NOT NULL,
        subject_ref TEXT NOT NULL,
        UNIQUE (source_owner, source_stream, source_record_id, source_schema_version, source_digest)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS learning_assessment (
        candidate_id TEXT PRIMARY KEY REFERENCES learning_candidate(candidate_id),
        schema_version INTEGER NOT NULL CHECK (schema_version = 1),
        outcome TEXT NOT NULL CHECK (outcome IN ('SHADOW_ELIGIBLE','SHADOW_REJECTED','SHADOW_DEFERRED')),
        reason_code TEXT NOT NULL CHECK (reason_code IN (
            'SOURCE_EVENT_INFRASTRUCTURE_PROOF',
            'CANDIDATE_VALIDATION_FAILED',
            'NO_CANONICAL_LTM_APPLY_PATH'
        )),
        assessed_at TEXT NOT NULL
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS learning_candidate_source_record
    ON learning_candidate_source(source_owner, source_stream, source_record_id)
    """,
)


class LearningStoreError(RuntimeError):
    code = "DB_BUSY"


class SchemaError(LearningStoreError):
    code = "SOURCE_SCHEMA_MISMATCH"


class LeaseLost(LearningStoreError):
    code = "LEASE_LOST"


class CursorConflict(LearningStoreError):
    code = "CURSOR_CONFLICT"


class CapacityPaused(LearningStoreError):
    code = "CAPACITY_PAUSED"


def utc_now(value: Optional[datetime] = None) -> str:
    stamp = value or datetime.now(timezone.utc)
    if stamp.tzinfo is None:
        stamp = stamp.replace(tzinfo=timezone.utc)
    return stamp.astimezone(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def add_seconds(stamp: str, seconds: int) -> str:
    parsed = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
    return utc_now(parsed + timedelta(seconds=seconds))


def _normal_sql(sql: str) -> str:
    return " ".join(sql.split())


def schema_fingerprint(conn: sqlite3.Connection) -> str:
    rows = conn.execute(
        "SELECT type,name,sql FROM sqlite_master WHERE sql IS NOT NULL ORDER BY type,name"
    ).fetchall()
    selected = [row for row in rows if str(row[1]) in L18_V1_SCHEMA_OBJECTS]
    if {str(row[1]) for row in selected} != L18_V1_SCHEMA_OBJECTS:
        raise SchemaError("Slice 15A schema object set is incomplete")
    payload = "\n".join(f"{row[0]}:{row[1]}:{_normal_sql(row[2])}" for row in selected)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _connect(path: Path, *, create: bool) -> sqlite3.Connection:
    path = Path(path)
    if not create and not path.is_file():
        raise SchemaError("Learning database has not been explicitly migrated")
    conn = sqlite3.connect(str(path), timeout=5.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 5000")
    conn.execute("PRAGMA synchronous = FULL")
    return conn


def _assert_only_learning_tables(conn: sqlite3.Connection) -> None:
    tables = {
        str(row[0]) for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        )
    }
    if not tables.issubset(KNOWN_COGNITIVE_TABLES):
        raise SchemaError("database contains an unrecognized cognitive table")




def _l18_authorizer(
    action: int,
    arg1: Optional[str],
    arg2: Optional[str],
    database: Optional[str],
    trigger: Optional[str],
) -> int:
    """Deny L18 runtime access outside its learning-owned SQL scope."""
    del arg2, database, trigger
    table = str(arg1 or "")
    if action == sqlite3.SQLITE_READ:
        return sqlite3.SQLITE_OK if table.startswith("learning_") or table in {
            "sqlite_master", "sqlite_schema",
        } else sqlite3.SQLITE_DENY
    if action in {sqlite3.SQLITE_INSERT, sqlite3.SQLITE_UPDATE, sqlite3.SQLITE_DELETE}:
        return sqlite3.SQLITE_OK if table.startswith("learning_") else sqlite3.SQLITE_DENY
    schema_actions = {
        sqlite3.SQLITE_CREATE_INDEX, sqlite3.SQLITE_CREATE_TABLE,
        sqlite3.SQLITE_CREATE_TRIGGER, sqlite3.SQLITE_CREATE_VIEW,
        sqlite3.SQLITE_DROP_INDEX, sqlite3.SQLITE_DROP_TABLE,
        sqlite3.SQLITE_DROP_TRIGGER, sqlite3.SQLITE_DROP_VIEW,
        sqlite3.SQLITE_ALTER_TABLE, sqlite3.SQLITE_REINDEX,
    }
    if action in schema_actions:
        return sqlite3.SQLITE_DENY
    return sqlite3.SQLITE_OK

def migrate(path: Path, applied_at: Optional[str] = None) -> str:
    """Create or verify schema version 1.  This is the only implicit-create path."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    old_umask = os.umask(0o077)
    try:
        conn = _connect(path, create=True)
    finally:
        os.umask(old_umask)
    try:
        conn.execute("PRAGMA journal_mode = WAL")
        conn.execute("BEGIN IMMEDIATE")
        _assert_only_learning_tables(conn)
        for statement in MIGRATION_STATEMENTS:
            conn.execute(statement)
        fingerprint = schema_fingerprint(conn)
        row = conn.execute(
            "SELECT version, schema_fingerprint FROM learning_schema_migration "
            "ORDER BY version DESC LIMIT 1"
        ).fetchone()
        if row is None:
            conn.execute(
                "INSERT INTO learning_schema_migration(version, schema_fingerprint, applied_at) "
                "VALUES (?, ?, ?)",
                (SCHEMA_VERSION, fingerprint, applied_at or utc_now()),
            )
        elif int(row["version"]) != SCHEMA_VERSION or row["schema_fingerprint"] != fingerprint:
            raise SchemaError("Learning schema version or fingerprint mismatch")
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass
    return fingerprint


class LearningStore:
    """Transactional repository for the L18-only shadow ledger."""

    def __init__(self, path: Path, capacity: int = DEFAULT_LEDGER_CAPACITY):
        self.path = Path(path)
        if isinstance(capacity, bool) or not isinstance(capacity, int) or capacity < 1:
            raise ValueError("capacity must be a positive integer")
        self.capacity = capacity

    def connect(self) -> sqlite3.Connection:
        conn = _connect(self.path, create=False)
        try:
            _assert_only_learning_tables(conn)
            row = conn.execute(
                "SELECT version, schema_fingerprint FROM learning_schema_migration "
                "ORDER BY version DESC LIMIT 1"
            ).fetchone()
            if row is None or int(row["version"]) != SCHEMA_VERSION:
                raise SchemaError("Learning schema version is unavailable")
            if row["schema_fingerprint"] != schema_fingerprint(conn):
                raise SchemaError("Learning schema fingerprint mismatch")
            conn.set_authorizer(_l18_authorizer)
            return conn
        except Exception:
            conn.close()
            raise

    def get_cursor(self, conn: Optional[sqlite3.Connection] = None) -> int:
        owned = conn is None
        connection = conn or self.connect()
        try:
            row = connection.execute(
                "SELECT committed_value FROM learning_cursor "
                "WHERE source_owner=? AND source_stream=?",
                (C.SOURCE_OWNER, C.SOURCE_STREAM),
            ).fetchone()
            return int(row[0]) if row else 0
        finally:
            if owned:
                connection.close()

    def lease_job(
        self,
        worker_id: str,
        now: str,
        lease_seconds: int = DEFAULT_LEASE_SECONDS,
    ) -> Dict[str, Any]:
        if not worker_id or len(worker_id) > 128:
            raise ValueError("worker_id is required and bounded")
        if not 1 <= int(lease_seconds) <= 300:
            raise ValueError("lease_seconds is outside the approved bound")
        conn = self.connect()
        try:
            conn.execute("BEGIN IMMEDIATE")
            conn.execute(
                "UPDATE learning_job SET status='QUEUED', lease_owner=NULL, lease_token=NULL, "
                "lease_expires_at=NULL, failure_code='LEASE_EXPIRED' "
                "WHERE status='LEASED' AND lease_expires_at <= ? AND attempt_count < ?",
                (now, MAX_ATTEMPTS),
            )
            conn.execute(
                "UPDATE learning_job SET status='FAILED_TERMINAL', lease_owner=NULL, lease_token=NULL, "
                "lease_expires_at=NULL, completed_at=?, failure_code='LEASE_EXPIRED' "
                "WHERE status='LEASED' AND lease_expires_at <= ? AND attempt_count >= ?",
                (now, now, MAX_ATTEMPTS),
            )
            row = conn.execute(
                "SELECT * FROM learning_job WHERE status='QUEUED' "
                "AND source_owner=? AND source_stream=? ORDER BY created_at, job_id LIMIT 1",
                (C.SOURCE_OWNER, C.SOURCE_STREAM),
            ).fetchone()
            if row is None:
                cursor_from = self.get_cursor(conn)
                job_id = "ljob." + uuid.uuid4().hex
                conn.execute(
                    "INSERT INTO learning_job(job_id,schema_version,mode,source_owner,source_stream,"
                    "cursor_from,status,created_at) VALUES (?,?,?,?,?,?,?,?)",
                    (job_id, SCHEMA_VERSION, "SHADOW", C.SOURCE_OWNER, C.SOURCE_STREAM,
                     cursor_from, QUEUED, now),
                )
            else:
                job_id = str(row["job_id"])

            token = uuid.uuid4().hex
            expiry = add_seconds(now, int(lease_seconds))
            updated = conn.execute(
                "UPDATE learning_job SET status='LEASED', lease_owner=?, lease_token=?, "
                "lease_expires_at=?, attempt_count=attempt_count+1, "
                "started_at=COALESCE(started_at,?), completed_at=NULL, failure_code=NULL "
                "WHERE job_id=? AND status='QUEUED' AND attempt_count < ?",
                (worker_id, token, expiry, now, job_id, MAX_ATTEMPTS),
            )
            if updated.rowcount != 1:
                conn.execute(
                    "UPDATE learning_job SET status='FAILED_TERMINAL', completed_at=?, "
                    "failure_code=COALESCE(failure_code,'LEASE_LOST'), lease_owner=NULL, "
                    "lease_token=NULL, lease_expires_at=NULL WHERE job_id=? AND status='QUEUED'",
                    (now, job_id),
                )
                raise LeaseLost("job could not be leased")
            leased = dict(conn.execute("SELECT * FROM learning_job WHERE job_id=?", (job_id,)).fetchone())
            conn.commit()
            return leased
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
    @staticmethod
    def _require_lease(conn: sqlite3.Connection, job_id: str, token: str, now: str) -> sqlite3.Row:
        row = conn.execute(
            "SELECT * FROM learning_job WHERE job_id=? AND status='LEASED' "
            "AND lease_token=? AND lease_expires_at > ?",
            (job_id, token, now),
        ).fetchone()
        if row is None:
            raise LeaseLost("job lease is no longer authoritative")
        return row

    def commit_batch(
        self,
        job_id: str,
        lease_token: str,
        processed: Sequence[Tuple[C.LearningCandidate, C.LearningSourceRecordRef, C.LearningAssessment]],
        cursor_through: int,
        now: str,
    ) -> Dict[str, int]:
        conn = self.connect()
        inserted = 0
        replayed = 0
        try:
            conn.execute("BEGIN IMMEDIATE")
            job = self._require_lease(conn, job_id, lease_token, now)
            current_cursor = self.get_cursor(conn)
            if current_cursor != int(job["cursor_from"]):
                raise CursorConflict("source cursor changed after the job was created")
            if cursor_through < current_cursor:
                raise CursorConflict("cursor cannot move backwards")

            new_keys = []
            for candidate, _, _ in processed:
                row = conn.execute(
                    "SELECT candidate_id FROM learning_candidate WHERE idempotency_key=?",
                    (candidate.idempotency_key,),
                ).fetchone()
                if row is None:
                    new_keys.append(candidate.idempotency_key)
                elif row["candidate_id"] != candidate.candidate_id:
                    raise LearningStoreError("idempotency key maps to a different candidate")
            existing_count = int(conn.execute("SELECT COUNT(*) FROM learning_candidate").fetchone()[0])
            if existing_count + len(set(new_keys)) > self.capacity:
                raise CapacityPaused("Learning ledger capacity reached")

            for candidate, source_ref, assessment in processed:
                existing = conn.execute(
                    "SELECT candidate_id FROM learning_candidate WHERE idempotency_key=?",
                    (candidate.idempotency_key,),
                ).fetchone()
                if existing is not None:
                    replayed += 1
                    continue
                conn.execute(
                    "INSERT INTO learning_candidate(candidate_id,schema_version,candidate_class,"
                    "admission_basis,epistemic_basis,validation_state,idempotency_key,event_type,"
                    "subject_ref,created_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
                    (
                        candidate.candidate_id, candidate.schema_version, candidate.candidate_class,
                        candidate.admission_basis, candidate.epistemic_basis,
                        candidate.validation_state, candidate.idempotency_key,
                        candidate.descriptor.event_type, candidate.descriptor.subject_ref,
                        candidate.created_at,
                    ),
                )
                conn.execute(
                    "INSERT INTO learning_candidate_source(candidate_id,source_owner,source_stream,"
                    "source_record_id,source_schema_version,source_digest,occurred_at,subject_ref) "
                    "VALUES (?,?,?,?,?,?,?,?)",
                    (
                        candidate.candidate_id, source_ref.source_owner, source_ref.source_stream,
                        source_ref.source_record_id, source_ref.source_schema_version,
                        source_ref.source_digest, source_ref.occurred_at,
                        source_ref.subject_refs[0],
                    ),
                )
                conn.execute(
                    "INSERT INTO learning_assessment(candidate_id,schema_version,outcome,reason_code,assessed_at) "
                    "VALUES (?,?,?,?,?)",
                    (
                        assessment.candidate_id, assessment.schema_version, assessment.outcome,
                        assessment.reason_code, assessment.assessed_at,
                    ),
                )
                inserted += 1

            conn.execute(
                "INSERT INTO learning_cursor(source_owner,source_stream,cursor_kind,committed_value,"
                "source_schema_version,updated_at) VALUES (?,?,?,?,?,?) "
                "ON CONFLICT(source_owner,source_stream) DO UPDATE SET "
                "committed_value=excluded.committed_value, "
                "source_schema_version=excluded.source_schema_version, updated_at=excluded.updated_at",
                (C.SOURCE_OWNER, C.SOURCE_STREAM, C.CURSOR_KIND, cursor_through,
                 C.SOURCE_SCHEMA_VERSION, now),
            )
            updated = conn.execute(
                "UPDATE learning_job SET status='SUCCEEDED', cursor_through=?, completed_at=?, "
                "lease_owner=NULL, lease_token=NULL, lease_expires_at=NULL, failure_code=NULL "
                "WHERE job_id=? AND status='LEASED' AND lease_token=? AND lease_expires_at > ?",
                (cursor_through, now, job_id, lease_token, now),
            )
            if updated.rowcount != 1:
                raise LeaseLost("lease was lost before job completion")
            conn.commit()
            return {"inserted": inserted, "replayed": replayed}
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def fail_job(
        self,
        job_id: str,
        lease_token: str,
        failure_code: str,
        retryable: bool,
        now: str,
    ) -> str:
        if failure_code not in FAILURE_CODES:
            raise ValueError("unsupported failure code")
        conn = self.connect()
        try:
            conn.execute("BEGIN IMMEDIATE")
            job = self._require_lease(conn, job_id, lease_token, now)
            will_retry = bool(retryable) and int(job["attempt_count"]) < MAX_ATTEMPTS
            status = QUEUED if will_retry else FAILED_TERMINAL
            completed_at = None if will_retry else now
            conn.execute(
                "UPDATE learning_job SET status=?, completed_at=?, failure_code=?, "
                "lease_owner=NULL, lease_token=NULL, lease_expires_at=NULL "
                "WHERE job_id=? AND lease_token=?",
                (status, completed_at, failure_code, job_id, lease_token),
            )
            conn.commit()
            return status
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()


    @staticmethod
    def _proposal_from_row(row: sqlite3.Row) -> C.MemoryWriteProposal:
        return C.MemoryWriteProposal(
            proposal_id=str(row["proposal_id"]),
            candidate_id=str(row["candidate_id"]),
            schema_version=int(row["schema_version"]),
            operation=str(row["operation"]),
            target_memory_class=str(row["target_memory_class"]),
            subject_namespace=str(row["subject_namespace"]),
            subject_key=str(row["subject_key"]),
            expected_active_revision_id=row["expected_active_revision_id"],
            restore_revision_id=row["restore_revision_id"],
            value_schema=row["value_schema"],
            proposed_value_json=row["proposed_value_json"],
            proposed_value_digest=row["proposed_value_digest"],
            admission_basis=str(row["admission_basis"]),
            epistemic_basis=str(row["epistemic_basis"]),
            consent_ref_id=row["consent_ref_id"],
            verification_outcome_ref_id=row["verification_outcome_ref_id"],
            rollback_authorization_ref_id=row["rollback_authorization_ref_id"],
            proposal_fingerprint=str(row["proposal_fingerprint"]),
            created_at=str(row["created_at"]),
        )

    @staticmethod
    def _candidate_binding(conn: sqlite3.Connection, candidate_id: str) -> C.CandidateProvenanceBinding:
        row = conn.execute(
            "SELECT c.candidate_id,c.schema_version,c.candidate_class,c.idempotency_key,"
            "c.admission_basis,c.epistemic_basis,c.validation_state,c.event_type,"
            "c.subject_ref,s.source_owner,s.source_stream,s.source_record_id,"
            "s.source_schema_version,s.source_digest,s.occurred_at,"
            "s.subject_ref AS source_subject_ref,a.outcome AS assessment_outcome "
            "FROM learning_candidate c "
            "JOIN learning_candidate_source s ON s.candidate_id=c.candidate_id "
            "JOIN learning_assessment a ON a.candidate_id=c.candidate_id "
            "WHERE c.candidate_id=?",
            (candidate_id,),
        ).fetchone()
        if row is None:
            raise LearningStoreError("candidate provenance is unavailable")
        if row["validation_state"] != C.VALID or row["assessment_outcome"] != C.SHADOW_ELIGIBLE:
            raise LearningStoreError("candidate is not proposal-eligible")
        return C.CandidateProvenanceBinding(
            candidate_id=str(row["candidate_id"]),
            candidate_schema_version=int(row["schema_version"]),
            candidate_class=str(row["candidate_class"]),
            candidate_idempotency_key=str(row["idempotency_key"]),
            candidate_admission_basis=str(row["admission_basis"]),
            candidate_epistemic_basis=str(row["epistemic_basis"]),
            validation_state=str(row["validation_state"]),
            event_type=str(row["event_type"]),
            subject_ref=str(row["subject_ref"]),
            source_owner=str(row["source_owner"]),
            source_stream=str(row["source_stream"]),
            source_record_id=int(row["source_record_id"]),
            source_schema_version=int(row["source_schema_version"]),
            source_digest=str(row["source_digest"]),
            occurred_at=str(row["occurred_at"]),
            source_subject_ref=str(row["source_subject_ref"]),
        )

    def insert_proposal(self, proposal: C.MemoryWriteProposal) -> C.MemoryWriteProposal:
        """Commit one immutable L18 proposal after rebinding persisted provenance."""
        proposal.validate()
        conn = self.connect()
        try:
            conn.execute("BEGIN IMMEDIATE")
            binding = self._candidate_binding(conn, proposal.candidate_id)
            expected = C.compute_proposal_fingerprint(proposal, binding)
            if expected != proposal.proposal_fingerprint:
                raise LearningStoreError("proposal fingerprint does not bind persisted provenance")
            existing = conn.execute(
                "SELECT * FROM learning_proposal WHERE proposal_fingerprint=?",
                (proposal.proposal_fingerprint,),
            ).fetchone()
            if existing is not None:
                stored = self._proposal_from_row(existing)
                conn.rollback()
                return stored
            conn.execute(
                "INSERT INTO learning_proposal(proposal_id,candidate_id,schema_version,operation,"
                "target_memory_class,subject_namespace,subject_key,expected_active_revision_id,"
                "restore_revision_id,value_schema,proposed_value_json,proposed_value_digest,"
                "admission_basis,epistemic_basis,consent_ref_id,verification_outcome_ref_id,"
                "rollback_authorization_ref_id,proposal_fingerprint,created_at) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    proposal.proposal_id, proposal.candidate_id, proposal.schema_version,
                    proposal.operation, proposal.target_memory_class, proposal.subject_namespace,
                    proposal.subject_key, proposal.expected_active_revision_id,
                    proposal.restore_revision_id, proposal.value_schema,
                    proposal.proposed_value_json, proposal.proposed_value_digest,
                    proposal.admission_basis, proposal.epistemic_basis,
                    proposal.consent_ref_id, proposal.verification_outcome_ref_id,
                    proposal.rollback_authorization_ref_id, proposal.proposal_fingerprint,
                    proposal.created_at,
                ),
            )
            conn.commit()
            return proposal
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def proposal(self, proposal_id: str) -> Optional[C.MemoryWriteProposal]:
        conn = self.connect()
        try:
            row = conn.execute(
                "SELECT * FROM learning_proposal WHERE proposal_id=?", (proposal_id,),
            ).fetchone()
            return self._proposal_from_row(row) if row else None
        finally:
            conn.close()

    def counts(self) -> Dict[str, int]:
        conn = self.connect()
        try:
            return {
                table: int(conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
                for table in sorted(ALLOWED_TABLES)
            }
        finally:
            conn.close()

    def job(self, job_id: str) -> Dict[str, Any]:
        conn = self.connect()
        try:
            row = conn.execute("SELECT * FROM learning_job WHERE job_id=?", (job_id,)).fetchone()
            return dict(row) if row else {}
        finally:
            conn.close()
