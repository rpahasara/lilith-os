"""Slice 15B1 canonical Long-Term Memory storage foundation.

L18 creates immutable proposals.  L04 loads those proposals by identifier,
validates the durable candidate/provenance binding, resolves required external
authorities, and owns every ``memory_*`` mutation.  Production construction
uses an empty registry and a strict, fail-closed kill switch.  This module has
no conversation, prompt, World, Goal, Policy, SOUL, Verifier, connector, or
legacy-memory integration.
"""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import stat
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

try:
    from . import memory_contracts as C
except ImportError:  # deploy-exact flat-directory tests
    import memory_contracts as C


SCHEMA_VERSION = 1
DEFAULT_CAPACITY = 10_000

APPLIED = "APPLIED"
ALREADY_APPLIED = "ALREADY_APPLIED"
REJECTED = "REJECTED"
PRECONDITION_FAILED = "PRECONDITION_FAILED"
RETRYABLE_FAILURE = "RETRYABLE_FAILURE"

ACCEPTED = "ACCEPTED"

CONFIRMED = "CONFIRMED"
INVALID = "INVALID"
REVOKED = "REVOKED"
UNAVAILABLE = "UNAVAILABLE"

FAILURE_CODES = frozenset({
    "CANONICAL_LTM_DISABLED",
    "UNKNOWN_MEMORY_CLASS",
    "UNKNOWN_NAMESPACE",
    "UNKNOWN_VALUE_SCHEMA",
    "INVALID_PROPOSAL",
    "PROPOSAL_FINGERPRINT_MISMATCH",
    "CANDIDATE_NOT_FOUND",
    "CANDIDATE_INVALID",
    "CANDIDATE_NOT_ELIGIBLE",
    "ITEM_ALREADY_EXISTS",
    "ITEM_NOT_FOUND",
    "ACTIVE_REVISION_MISMATCH",
    "RESTORE_REVISION_NOT_FOUND",
    "RESTORE_ITEM_MISMATCH",
    "CONSENT_AUTHORITY_UNAVAILABLE",
    "CONSENT_INVALID",
    "VERIFIER_UNAVAILABLE",
    "VERIFICATION_NOT_CONFIRMED",
    "ROLLBACK_AUTHORITY_UNAVAILABLE",
    "ROLLBACK_NOT_AUTHORIZED",
    "CAPACITY_PAUSED",
    "DB_BUSY",
    "SCHEMA_MISMATCH",
})

L18_READ_TABLES = frozenset({
    "learning_proposal",
    "learning_candidate",
    "learning_candidate_source",
    "learning_assessment",
})

MEMORY_TABLES = frozenset({
    "memory_schema_migration",
    "memory_item",
    "memory_revision",
    "memory_revision_source",
    "memory_active_revision",
    "memory_admission",
    "memory_apply_audit",
})

L18_CORE_TABLES = frozenset({
    "learning_schema_migration",
    "learning_job",
    "learning_cursor",
    "learning_candidate",
    "learning_candidate_source",
    "learning_assessment",
})

ALL_15B1_TABLES = L18_CORE_TABLES | {"learning_proposal"} | MEMORY_TABLES

# Slice 15B2a canonical memory authority foundations: these remain externally owned and outside the L04 V1 authorizer.
try:
    from .slice15b2a_migration import COGNITIVE_15B2A_TABLES as _SLICE15B2A_TABLES
except ImportError:  # older isolated Slice 15B1 fixture
    _SLICE15B2A_TABLES = frozenset()
ALL_15B1_TABLES = ALL_15B1_TABLES | _SLICE15B2A_TABLES

MIGRATION_OBJECT_NAMES = frozenset({
    "learning_proposal",
    "learning_proposal_fingerprint",
    "learning_proposal_no_update",
    "learning_proposal_no_delete",
    "learning_candidate_no_update",
    "learning_candidate_no_delete",
    "learning_candidate_source_no_update",
    "learning_candidate_source_no_delete",
    "learning_assessment_no_update",
    "learning_assessment_no_delete",
    "memory_schema_migration",
    "memory_item",
    "memory_item_identity",
    "memory_item_no_update",
    "memory_item_no_delete",
    "memory_revision",
    "memory_revision_item_created",
    "memory_revision_item_digest",
    "memory_revision_no_update",
    "memory_revision_no_delete",
    "memory_revision_source",
    "memory_revision_source_lookup",
    "memory_revision_source_no_update",
    "memory_revision_source_no_delete",
    "memory_admission",
    "memory_admission_no_update",
    "memory_admission_no_delete",
    "memory_apply_audit",
    "memory_apply_audit_item_time",
    "memory_apply_audit_no_update",
    "memory_apply_audit_no_delete",
    "memory_active_revision",
    "memory_active_revision_no_delete",
    "memory_active_revision_identity_guard",
})


class MemoryStoreError(RuntimeError):
    code = "SCHEMA_MISMATCH"


class MemorySchemaError(MemoryStoreError):
    code = "SCHEMA_MISMATCH"


class BackupRequired(MemoryStoreError):
    code = "SCHEMA_MISMATCH"


class ProposalError(MemoryStoreError):
    code = "INVALID_PROPOSAL"


@dataclass(frozen=True)
class AuthorityResolution:
    status: str

    def __post_init__(self) -> None:
        if self.status not in {CONFIRMED, INVALID, REVOKED, UNAVAILABLE}:
            raise ValueError("unsupported authority resolution")


class UnavailableAuthorityResolver:
    """Production-safe resolver used while a real authority does not exist."""

    def resolve(
        self,
        reference_id: Optional[str],
        *,
        proposal: C.MemoryWriteProposal,
        value_digest: str,
    ) -> AuthorityResolution:
        del reference_id, proposal, value_digest
        return AuthorityResolution(UNAVAILABLE)


@dataclass(frozen=True)
class MemoryClassPolicy:
    """Closed class policy supplied by an explicitly selected registry."""

    memory_class: str
    subject_namespace: str
    value_schema: str
    normalize: Callable[[Mapping[str, Any]], Mapping[str, Any]]
    requires_consent: bool = False
    requires_verification: bool = False


class MemoryRegistry:
    def __init__(self, policies: Iterable[MemoryClassPolicy] = ()):
        entries: Dict[Tuple[str, str], MemoryClassPolicy] = {}
        for policy in policies:
            key = (policy.memory_class, policy.subject_namespace)
            if key in entries:
                raise ValueError("duplicate memory class/namespace policy")
            entries[key] = policy
        self._entries = entries

    def resolve(self, memory_class: str, namespace: str) -> Optional[MemoryClassPolicy]:
        return self._entries.get((memory_class, namespace))

    def active_keys(self) -> Tuple[Tuple[str, str], ...]:
        return tuple(sorted(self._entries))


@dataclass(frozen=True)
class VerifiedBackup:
    source_path: str
    source_identity: str
    source_schema_fingerprint: str
    source_table_counts: Tuple[Tuple[str, int], ...]
    backup_path: str
    backup_sha256: str
    backup_integrity: str
    backup_mode: int


MIGRATION_STATEMENTS = (
    """
    CREATE TABLE IF NOT EXISTS learning_proposal (
        proposal_id TEXT PRIMARY KEY,
        candidate_id TEXT NOT NULL UNIQUE REFERENCES learning_candidate(candidate_id),
        schema_version INTEGER NOT NULL CHECK (schema_version = 1),
        operation TEXT NOT NULL CHECK (operation IN ('CREATE','SUPERSEDE','RESTORE')),
        target_memory_class TEXT NOT NULL CHECK (length(target_memory_class) BETWEEN 1 AND 64),
        subject_namespace TEXT NOT NULL CHECK (length(subject_namespace) BETWEEN 1 AND 64),
        subject_key TEXT NOT NULL CHECK (length(subject_key) BETWEEN 1 AND 128),
        expected_active_revision_id TEXT,
        restore_revision_id TEXT,
        value_schema TEXT,
        proposed_value_json TEXT CHECK (proposed_value_json IS NULL OR json_valid(proposed_value_json)),
        proposed_value_digest TEXT CHECK (proposed_value_digest IS NULL OR length(proposed_value_digest) = 64),
        admission_basis TEXT NOT NULL CHECK (length(admission_basis) BETWEEN 1 AND 64),
        epistemic_basis TEXT NOT NULL CHECK (length(epistemic_basis) BETWEEN 1 AND 64),
        consent_ref_id TEXT,
        verification_outcome_ref_id TEXT,
        rollback_authorization_ref_id TEXT,
        proposal_fingerprint TEXT NOT NULL CHECK (length(proposal_fingerprint) = 64),
        created_at TEXT NOT NULL,
        CHECK (
            (operation = 'CREATE' AND expected_active_revision_id IS NULL
             AND restore_revision_id IS NULL AND value_schema IS NOT NULL
             AND proposed_value_json IS NOT NULL AND proposed_value_digest IS NOT NULL
             AND rollback_authorization_ref_id IS NULL)
            OR
            (operation = 'SUPERSEDE' AND expected_active_revision_id IS NOT NULL
             AND restore_revision_id IS NULL AND value_schema IS NOT NULL
             AND proposed_value_json IS NOT NULL AND proposed_value_digest IS NOT NULL
             AND rollback_authorization_ref_id IS NULL)
            OR
            (operation = 'RESTORE' AND expected_active_revision_id IS NOT NULL
             AND restore_revision_id IS NOT NULL AND value_schema IS NULL
             AND proposed_value_json IS NULL AND proposed_value_digest IS NULL
             AND rollback_authorization_ref_id IS NOT NULL)
        )
    )
    """,
    "CREATE UNIQUE INDEX IF NOT EXISTS learning_proposal_fingerprint ON learning_proposal(proposal_fingerprint)",
    """
    CREATE TABLE IF NOT EXISTS memory_schema_migration (
        version INTEGER PRIMARY KEY,
        schema_fingerprint TEXT NOT NULL,
        applied_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS memory_item (
        memory_item_id TEXT PRIMARY KEY,
        memory_class TEXT NOT NULL CHECK (length(memory_class) BETWEEN 1 AND 64),
        subject_namespace TEXT NOT NULL CHECK (length(subject_namespace) BETWEEN 1 AND 64),
        subject_key TEXT NOT NULL CHECK (length(subject_key) BETWEEN 1 AND 128),
        created_at TEXT NOT NULL,
        UNIQUE(memory_class, subject_namespace, subject_key)
    )
    """,
    "CREATE UNIQUE INDEX IF NOT EXISTS memory_item_identity ON memory_item(memory_class,subject_namespace,subject_key)",
    """
    CREATE TABLE IF NOT EXISTS memory_revision (
        revision_id TEXT PRIMARY KEY,
        memory_item_id TEXT NOT NULL REFERENCES memory_item(memory_item_id),
        schema_version INTEGER NOT NULL CHECK (schema_version = 1),
        value_schema TEXT NOT NULL CHECK (length(value_schema) BETWEEN 1 AND 64),
        normalized_value_json TEXT NOT NULL CHECK (json_valid(normalized_value_json)),
        value_digest TEXT NOT NULL CHECK (length(value_digest) = 64),
        created_from_proposal_id TEXT NOT NULL UNIQUE REFERENCES learning_proposal(proposal_id),
        supersedes_revision_id TEXT REFERENCES memory_revision(revision_id),
        restores_revision_id TEXT REFERENCES memory_revision(revision_id),
        epistemic_basis TEXT NOT NULL CHECK (length(epistemic_basis) BETWEEN 1 AND 64),
        admission_basis TEXT NOT NULL CHECK (length(admission_basis) BETWEEN 1 AND 64),
        consent_ref_id TEXT,
        verification_outcome_ref_id TEXT,
        rollback_authorization_ref_id TEXT,
        created_at TEXT NOT NULL,
        UNIQUE(memory_item_id, revision_id)
    )
    """,
    "CREATE INDEX IF NOT EXISTS memory_revision_item_created ON memory_revision(memory_item_id,created_at,revision_id)",
    "CREATE INDEX IF NOT EXISTS memory_revision_item_digest ON memory_revision(memory_item_id,value_digest)",
    """
    CREATE TABLE IF NOT EXISTS memory_revision_source (
        revision_id TEXT NOT NULL REFERENCES memory_revision(revision_id),
        source_ordinal INTEGER NOT NULL CHECK (source_ordinal >= 0),
        source_owner TEXT NOT NULL CHECK (length(source_owner) BETWEEN 1 AND 64),
        source_stream TEXT NOT NULL CHECK (length(source_stream) BETWEEN 1 AND 64),
        source_record_id INTEGER NOT NULL CHECK (source_record_id > 0),
        source_schema_version INTEGER NOT NULL CHECK (source_schema_version > 0),
        source_digest TEXT NOT NULL CHECK (length(source_digest) = 64),
        occurred_at TEXT NOT NULL,
        subject_ref TEXT,
        PRIMARY KEY(revision_id, source_ordinal)
    )
    """,
    "CREATE INDEX IF NOT EXISTS memory_revision_source_lookup ON memory_revision_source(source_owner,source_stream,source_record_id)",
    """
    CREATE TABLE IF NOT EXISTS memory_admission (
        admission_id TEXT PRIMARY KEY,
        proposal_id TEXT NOT NULL UNIQUE REFERENCES learning_proposal(proposal_id),
        schema_version INTEGER NOT NULL CHECK (schema_version = 1),
        outcome TEXT NOT NULL CHECK (outcome IN ('ACCEPTED','REJECTED','PRECONDITION_FAILED')),
        failure_code TEXT,
        evaluated_at TEXT NOT NULL,
        CHECK (
            (outcome = 'ACCEPTED' AND failure_code IS NULL)
            OR
            (outcome <> 'ACCEPTED' AND failure_code IS NOT NULL)
        )
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS memory_apply_audit (
        operation_id TEXT PRIMARY KEY,
        proposal_id TEXT NOT NULL UNIQUE REFERENCES learning_proposal(proposal_id),
        admission_id TEXT NOT NULL UNIQUE REFERENCES memory_admission(admission_id),
        schema_version INTEGER NOT NULL CHECK (schema_version = 1),
        operation TEXT NOT NULL CHECK (operation IN ('CREATE','SUPERSEDE','RESTORE')),
        memory_item_id TEXT NOT NULL REFERENCES memory_item(memory_item_id),
        prior_revision_id TEXT REFERENCES memory_revision(revision_id),
        created_revision_id TEXT NOT NULL UNIQUE REFERENCES memory_revision(revision_id),
        resulting_active_revision_id TEXT NOT NULL REFERENCES memory_revision(revision_id),
        rollback_authorization_ref_id TEXT,
        applied_at TEXT NOT NULL,
        CHECK (created_revision_id = resulting_active_revision_id),
        CHECK (
            (operation = 'CREATE' AND prior_revision_id IS NULL AND rollback_authorization_ref_id IS NULL)
            OR
            (operation = 'SUPERSEDE' AND prior_revision_id IS NOT NULL AND rollback_authorization_ref_id IS NULL)
            OR
            (operation = 'RESTORE' AND prior_revision_id IS NOT NULL AND rollback_authorization_ref_id IS NOT NULL)
        )
    )
    """,
    "CREATE INDEX IF NOT EXISTS memory_apply_audit_item_time ON memory_apply_audit(memory_item_id,applied_at,operation_id)",
    """
    CREATE TABLE IF NOT EXISTS memory_active_revision (
        memory_item_id TEXT PRIMARY KEY REFERENCES memory_item(memory_item_id),
        revision_id TEXT NOT NULL UNIQUE,
        updated_at TEXT NOT NULL,
        last_operation_id TEXT NOT NULL UNIQUE REFERENCES memory_apply_audit(operation_id)
            DEFERRABLE INITIALLY DEFERRED,
        FOREIGN KEY(memory_item_id, revision_id)
            REFERENCES memory_revision(memory_item_id, revision_id)
    )
    """,
    """CREATE TRIGGER IF NOT EXISTS learning_proposal_no_update
        BEFORE UPDATE ON learning_proposal BEGIN SELECT RAISE(ABORT,'learning proposal is immutable'); END""",
    """CREATE TRIGGER IF NOT EXISTS learning_proposal_no_delete
        BEFORE DELETE ON learning_proposal BEGIN SELECT RAISE(ABORT,'learning proposal is immutable'); END""",
    """CREATE TRIGGER IF NOT EXISTS learning_candidate_no_update
        BEFORE UPDATE ON learning_candidate BEGIN SELECT RAISE(ABORT,'learning candidate is immutable'); END""",
    """CREATE TRIGGER IF NOT EXISTS learning_candidate_no_delete
        BEFORE DELETE ON learning_candidate BEGIN SELECT RAISE(ABORT,'learning candidate is immutable'); END""",
    """CREATE TRIGGER IF NOT EXISTS learning_candidate_source_no_update
        BEFORE UPDATE ON learning_candidate_source BEGIN SELECT RAISE(ABORT,'candidate provenance is immutable'); END""",
    """CREATE TRIGGER IF NOT EXISTS learning_candidate_source_no_delete
        BEFORE DELETE ON learning_candidate_source BEGIN SELECT RAISE(ABORT,'candidate provenance is immutable'); END""",
    """CREATE TRIGGER IF NOT EXISTS learning_assessment_no_update
        BEFORE UPDATE ON learning_assessment BEGIN SELECT RAISE(ABORT,'learning assessment is immutable'); END""",
    """CREATE TRIGGER IF NOT EXISTS learning_assessment_no_delete
        BEFORE DELETE ON learning_assessment BEGIN SELECT RAISE(ABORT,'learning assessment is immutable'); END""",
    """CREATE TRIGGER IF NOT EXISTS memory_item_no_update
        BEFORE UPDATE ON memory_item BEGIN SELECT RAISE(ABORT,'memory item identity is immutable'); END""",
    """CREATE TRIGGER IF NOT EXISTS memory_item_no_delete
        BEFORE DELETE ON memory_item BEGIN SELECT RAISE(ABORT,'memory item deletion is unavailable'); END""",
    """CREATE TRIGGER IF NOT EXISTS memory_revision_no_update
        BEFORE UPDATE ON memory_revision BEGIN SELECT RAISE(ABORT,'memory revision is immutable'); END""",
    """CREATE TRIGGER IF NOT EXISTS memory_revision_no_delete
        BEFORE DELETE ON memory_revision BEGIN SELECT RAISE(ABORT,'memory revision deletion is unavailable'); END""",
    """CREATE TRIGGER IF NOT EXISTS memory_revision_source_no_update
        BEFORE UPDATE ON memory_revision_source BEGIN SELECT RAISE(ABORT,'revision provenance is immutable'); END""",
    """CREATE TRIGGER IF NOT EXISTS memory_revision_source_no_delete
        BEFORE DELETE ON memory_revision_source BEGIN SELECT RAISE(ABORT,'revision provenance deletion is unavailable'); END""",
    """CREATE TRIGGER IF NOT EXISTS memory_admission_no_update
        BEFORE UPDATE ON memory_admission BEGIN SELECT RAISE(ABORT,'memory admission is immutable'); END""",
    """CREATE TRIGGER IF NOT EXISTS memory_admission_no_delete
        BEFORE DELETE ON memory_admission BEGIN SELECT RAISE(ABORT,'memory admission is immutable'); END""",
    """CREATE TRIGGER IF NOT EXISTS memory_apply_audit_no_update
        BEFORE UPDATE ON memory_apply_audit BEGIN SELECT RAISE(ABORT,'memory apply audit is immutable'); END""",
    """CREATE TRIGGER IF NOT EXISTS memory_apply_audit_no_delete
        BEFORE DELETE ON memory_apply_audit BEGIN SELECT RAISE(ABORT,'memory apply audit deletion is unavailable'); END""",
    """CREATE TRIGGER IF NOT EXISTS memory_active_revision_no_delete
        BEFORE DELETE ON memory_active_revision BEGIN SELECT RAISE(ABORT,'active revision deletion is unavailable'); END""",
    """CREATE TRIGGER IF NOT EXISTS memory_active_revision_identity_guard
        BEFORE UPDATE OF memory_item_id ON memory_active_revision
        BEGIN SELECT RAISE(ABORT,'active revision item identity is immutable'); END""",
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def _normal_sql(sql: str) -> str:
    return " ".join(sql.split())


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _open_read_only(path: Path) -> sqlite3.Connection:
    resolved = Path(path).resolve()
    if not resolved.is_file():
        raise MemorySchemaError("database is unavailable")
    conn = sqlite3.connect(f"file:{resolved.as_posix()}?mode=ro", uri=True, timeout=5.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA query_only = ON")
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def complete_schema_fingerprint(conn: sqlite3.Connection) -> str:
    """Complete DB fingerprint using the established Slice 15A convention."""
    rows = conn.execute(
        "SELECT type,name,tbl_name,sql FROM sqlite_master "
        "WHERE name NOT LIKE 'sqlite_%' AND sql IS NOT NULL ORDER BY type,name"
    ).fetchall()
    payload = json.dumps([tuple(row) for row in rows], sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def memory_schema_fingerprint(conn: sqlite3.Connection) -> str:
    rows = conn.execute(
        "SELECT type,name,sql FROM sqlite_master WHERE sql IS NOT NULL ORDER BY type,name"
    ).fetchall()
    selected = [row for row in rows if str(row[1]) in MIGRATION_OBJECT_NAMES]
    names = {str(row[1]) for row in selected}
    if names != MIGRATION_OBJECT_NAMES:
        missing = sorted(MIGRATION_OBJECT_NAMES - names)
        raise MemorySchemaError(f"Slice 15B1 schema objects missing: {','.join(missing)}")
    payload = "\n".join(
        f"{row[0]}:{row[1]}:{_normal_sql(str(row[2]))}" for row in selected
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _table_counts(conn: sqlite3.Connection) -> Tuple[Tuple[str, int], ...]:
    tables = [
        str(row[0]) for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
        )
    ]
    return tuple(
        (table, int(conn.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]))
        for table in tables
    )


def _source_identity(path: Path) -> str:
    resolved = Path(path).resolve()
    details = resolved.stat()
    return f"{resolved}:{details.st_dev}:{details.st_ino}"


def verify_backup(source_path: Path, backup_path: Path) -> VerifiedBackup:
    source = Path(source_path).resolve()
    backup = Path(backup_path).resolve()
    if source == backup or not backup.is_file():
        raise BackupRequired("verified backup is unavailable")
    source_conn = _open_read_only(source)
    backup_conn = _open_read_only(backup)
    try:
        source_integrity = str(source_conn.execute("PRAGMA integrity_check").fetchone()[0])
        backup_integrity = str(backup_conn.execute("PRAGMA integrity_check").fetchone()[0])
        source_schema = complete_schema_fingerprint(source_conn)
        backup_schema = complete_schema_fingerprint(backup_conn)
        source_counts = _table_counts(source_conn)
        backup_counts = _table_counts(backup_conn)
    finally:
        source_conn.close()
        backup_conn.close()
    if source_integrity != "ok" or backup_integrity != "ok":
        raise BackupRequired("source or backup integrity check failed")
    if source_schema != backup_schema or source_counts != backup_counts:
        raise BackupRequired("backup does not match the source schema and row counts")
    mode = stat.S_IMODE(backup.stat().st_mode)
    if os.name != "nt" and mode != 0o600:
        raise BackupRequired("backup permissions are not owner-only")
    return VerifiedBackup(
        source_path=str(source),
        source_identity=_source_identity(source),
        source_schema_fingerprint=source_schema,
        source_table_counts=source_counts,
        backup_path=str(backup),
        backup_sha256=_sha256_file(backup),
        backup_integrity=backup_integrity,
        backup_mode=mode,
    )


def create_verified_backup(source_path: Path, backup_path: Path) -> VerifiedBackup:
    source = Path(source_path).resolve()
    backup = Path(backup_path).resolve()
    if source == backup or backup.exists():
        raise BackupRequired("backup target must be a new distinct file")
    backup.parent.mkdir(parents=True, exist_ok=True)
    source_conn = _open_read_only(source)
    destination = sqlite3.connect(str(backup), timeout=5.0)
    try:
        source_conn.backup(destination)
        destination.commit()
    except Exception:
        destination.close()
        source_conn.close()
        try:
            backup.unlink()
        except OSError:
            pass
        raise
    else:
        destination.close()
        source_conn.close()
    try:
        os.chmod(backup, 0o600)
    except OSError:
        pass
    return verify_backup(source, backup)


def production_database_path() -> Path:
    home = Path(os.environ.get("HERMES_HOME") or (Path.home() / ".hermes"))
    return (home / "lilith-os" / "data" / "cognitive_memory.db").resolve()


def assert_isolated_test_database(test_path: Path, production_path: Optional[Path] = None) -> None:
    production = Path(production_path or production_database_path()).resolve()
    if Path(test_path).resolve() == production:
        raise ValueError("synthetic acceptance cannot use the production database")


def _validate_verified_backup(source: Path, proof: VerifiedBackup) -> None:
    source = Path(source).resolve()
    if proof.source_path != str(source) or proof.source_identity != _source_identity(source):
        raise BackupRequired("backup proof belongs to a different source database")
    if _sha256_file(Path(proof.backup_path)) != proof.backup_sha256:
        raise BackupRequired("backup checksum changed after verification")
    current = verify_backup(source, Path(proof.backup_path))
    if current != proof:
        raise BackupRequired("backup proof is stale")


def _migration_connect(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(path), timeout=5.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 5000")
    conn.execute("PRAGMA synchronous = FULL")
    return conn


def _existing_tables(conn: sqlite3.Connection) -> frozenset[str]:
    return frozenset(
        str(row[0]) for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        )
    )


def migrate(
    path: Path,
    *,
    applied_at: Optional[str] = None,
    verified_backup: Optional[VerifiedBackup] = None,
    production_path: Optional[Path] = None,
) -> Tuple[str, str]:
    """Dedicated Slice 15B1 schema migration authority.

    Production-path migration requires a verified, still-current SQLite backup.
    Isolated empty databases receive the existing Slice 15A schema first.
    """
    target = Path(path).resolve()
    production = Path(production_path or production_database_path()).resolve()
    if target == production:
        if verified_backup is None:
            raise BackupRequired("production migration requires a verified backup")
        _validate_verified_backup(target, verified_backup)

    needs_learning_schema = not target.exists()
    if target.exists() and target != production:
        probe = sqlite3.connect(str(target), timeout=5.0)
        try:
            needs_learning_schema = not bool(_existing_tables(probe))
        finally:
            probe.close()
    if needs_learning_schema:
        if target == production:
            raise MemorySchemaError("production cognitive database is unavailable")
        try:
            from . import learning_store
        except ImportError:
            import learning_store
        learning_store.migrate(target, applied_at=applied_at)

    old_umask = os.umask(0o077)
    try:
        conn = _migration_connect(target)
    finally:
        os.umask(old_umask)
    try:
        conn.execute("PRAGMA journal_mode = WAL")
        conn.execute("BEGIN IMMEDIATE")
        existing = _existing_tables(conn)
        if not L18_CORE_TABLES.issubset(existing):
            raise MemorySchemaError("Slice 15A schema is missing or malformed")
        if not existing.issubset(ALL_15B1_TABLES):
            raise MemorySchemaError("cognitive database contains an unrecognized table")
        before_counts = {
            table: int(conn.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0])
            for table in L18_CORE_TABLES
        }
        for statement in MIGRATION_STATEMENTS:
            conn.execute(statement)
        fingerprint = memory_schema_fingerprint(conn)
        row = conn.execute(
            "SELECT version,schema_fingerprint FROM memory_schema_migration "
            "ORDER BY version DESC LIMIT 1"
        ).fetchone()
        if row is None:
            conn.execute(
                "INSERT INTO memory_schema_migration(version,schema_fingerprint,applied_at) VALUES (?,?,?)",
                (SCHEMA_VERSION, fingerprint, applied_at or utc_now()),
            )
        elif int(row["version"]) != SCHEMA_VERSION or str(row["schema_fingerprint"]) != fingerprint:
            raise MemorySchemaError("L04 schema version or fingerprint mismatch")
        after_counts = {
            table: int(conn.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0])
            for table in L18_CORE_TABLES
        }
        if before_counts != after_counts:
            raise MemorySchemaError("L18 row counts changed during L04 migration")
        if conn.execute("PRAGMA foreign_key_check").fetchall():
            raise MemorySchemaError("foreign-key check failed")
        if str(conn.execute("PRAGMA integrity_check").fetchone()[0]) != "ok":
            raise MemorySchemaError("integrity check failed")
        complete = complete_schema_fingerprint(conn)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    try:
        os.chmod(target, 0o600)
    except OSError:
        pass
    return fingerprint, complete


def _l04_authorizer(
    action: int,
    arg1: Optional[str],
    arg2: Optional[str],
    database: Optional[str],
    trigger: Optional[str],
) -> int:
    del arg2, database, trigger
    table = str(arg1 or "")
    if action == sqlite3.SQLITE_READ:
        return sqlite3.SQLITE_OK if table in (L18_READ_TABLES | MEMORY_TABLES) else sqlite3.SQLITE_DENY
    if action in {sqlite3.SQLITE_INSERT, sqlite3.SQLITE_UPDATE, sqlite3.SQLITE_DELETE}:
        return sqlite3.SQLITE_OK if table in (MEMORY_TABLES - {"memory_schema_migration"}) else sqlite3.SQLITE_DENY
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


class MemoryStore:
    """L04-owned apply and internal exact-key read boundary."""

    def __init__(
        self,
        path: Path,
        *,
        enabled_provider: Callable[[], Optional[bool]],
        registry: MemoryRegistry,
        consent_resolver: Optional[Any] = None,
        verifier_resolver: Optional[Any] = None,
        rollback_resolver: Optional[Any] = None,
        capacity: int = DEFAULT_CAPACITY,
        trace_sink: Optional[Callable[[Mapping[str, Any]], None]] = None,
        now_fn: Callable[[], str] = utc_now,
        fault_hook: Optional[Callable[[str], None]] = None,
        production_path: Optional[Path] = None,
    ):
        if isinstance(capacity, bool) or not isinstance(capacity, int) or capacity < 1:
            raise ValueError("capacity must be a positive integer")
        self.path = Path(path)
        protected_production_path = Path(
            production_path or production_database_path()
        ).resolve()
        if self.path.resolve() == protected_production_path and registry.active_keys():
            raise ValueError("Slice 15B1 production registry must remain empty")
        self.enabled_provider = enabled_provider
        self.registry = registry
        self.consent_resolver = consent_resolver or UnavailableAuthorityResolver()
        self.verifier_resolver = verifier_resolver or UnavailableAuthorityResolver()
        self.rollback_resolver = rollback_resolver or UnavailableAuthorityResolver()
        self.capacity = capacity
        self.trace_sink = trace_sink
        self.now_fn = now_fn
        self.fault_hook = fault_hook

    @classmethod
    def production(cls, path: Optional[Path] = None) -> "MemoryStore":
        try:
            from . import config
        except ImportError:
            import config

        def enabled() -> Optional[bool]:
            cfg = config.load()
            if not getattr(cfg, "canonical_ltm_config_valid", False):
                return None
            value = getattr(cfg, "canonical_ltm_enabled", None)
            return value if isinstance(value, bool) else None

        return cls(
            path or production_database_path(),
            enabled_provider=enabled,
            registry=MemoryRegistry(),
            production_path=production_database_path(),
        )

    def _connect(self) -> sqlite3.Connection:
        if not self.path.is_file():
            raise MemorySchemaError("canonical memory database is unavailable")
        conn = sqlite3.connect(str(self.path), timeout=5.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA busy_timeout = 5000")
        row = conn.execute(
            "SELECT version,schema_fingerprint FROM memory_schema_migration "
            "ORDER BY version DESC LIMIT 1"
        ).fetchone()
        if row is None or int(row["version"]) != SCHEMA_VERSION:
            conn.close()
            raise MemorySchemaError("L04 schema is unavailable")
        if str(row["schema_fingerprint"]) != memory_schema_fingerprint(conn):
            conn.close()
            raise MemorySchemaError("L04 schema fingerprint mismatch")
        conn.set_authorizer(_l04_authorizer)
        return conn

    def _emit(self, **values: Any) -> None:
        if self.trace_sink is None:
            return
        allowed = {
            "lane": "canonical_ltm",
            "proposalId": values.get("proposalId"),
            "operation": values.get("operation"),
            "admissionOutcome": values.get("admissionOutcome"),
            "failureCode": values.get("failureCode"),
            "memoryClass": values.get("memoryClass"),
            "revisionId": values.get("revisionId"),
            "priorRevisionId": values.get("priorRevisionId"),
            "durationMs": values.get("durationMs", 0),
            "mode": values.get("mode", "DISABLED"),
            "schemaVersion": SCHEMA_VERSION,
        }
        self.trace_sink(allowed)

    def _result(
        self,
        proposal_id: str,
        outcome: str,
        *,
        failure_code: Optional[str] = None,
        item_id: Optional[str] = None,
        revision_id: Optional[str] = None,
        active_revision_id: Optional[str] = None,
        operation_id: Optional[str] = None,
    ) -> C.MemoryApplyResult:
        return C.MemoryApplyResult(
            proposal_id=proposal_id,
            outcome=outcome,
            failure_code=failure_code,
            memory_item_id=item_id,
            revision_id=revision_id,
            active_revision_id=active_revision_id,
            operation_id=operation_id,
        )

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
    def _binding_from_row(row: sqlite3.Row) -> C.CandidateProvenanceBinding:
        return C.CandidateProvenanceBinding(
            candidate_id=str(row["candidate_id"]),
            candidate_schema_version=int(row["candidate_schema_version"]),
            candidate_class=str(row["candidate_class"]),
            candidate_idempotency_key=str(row["idempotency_key"]),
            candidate_admission_basis=str(row["candidate_admission_basis"]),
            candidate_epistemic_basis=str(row["candidate_epistemic_basis"]),
            validation_state=str(row["validation_state"]),
            event_type=str(row["event_type"]),
            subject_ref=str(row["candidate_subject_ref"]),
            source_owner=str(row["source_owner"]),
            source_stream=str(row["source_stream"]),
            source_record_id=int(row["source_record_id"]),
            source_schema_version=int(row["source_schema_version"]),
            source_digest=str(row["source_digest"]),
            occurred_at=str(row["occurred_at"]),
            source_subject_ref=str(row["source_subject_ref"]),
        )

    @staticmethod
    def _load_proposal(conn: sqlite3.Connection, proposal_id: str) -> Optional[sqlite3.Row]:
        return conn.execute(
            "SELECT p.*,c.schema_version AS candidate_schema_version,c.candidate_class,"
            "c.idempotency_key,c.admission_basis AS candidate_admission_basis,"
            "c.epistemic_basis AS candidate_epistemic_basis,c.validation_state,c.event_type,"
            "c.subject_ref AS candidate_subject_ref,s.source_owner,s.source_stream,"
            "s.source_record_id,s.source_schema_version,s.source_digest,s.occurred_at,"
            "s.subject_ref AS source_subject_ref,a.outcome AS assessment_outcome "
            "FROM learning_proposal p "
            "JOIN learning_candidate c ON c.candidate_id=p.candidate_id "
            "JOIN learning_candidate_source s ON s.candidate_id=c.candidate_id "
            "JOIN learning_assessment a ON a.candidate_id=c.candidate_id "
            "WHERE p.proposal_id=?",
            (proposal_id,),
        ).fetchone()

    @staticmethod
    def _applied_result(conn: sqlite3.Connection, proposal_id: str) -> Optional[C.MemoryApplyResult]:
        row = conn.execute(
            "SELECT operation_id,memory_item_id,created_revision_id,resulting_active_revision_id "
            "FROM memory_apply_audit WHERE proposal_id=?",
            (proposal_id,),
        ).fetchone()
        if row is None:
            return None
        return C.MemoryApplyResult(
            proposal_id=proposal_id,
            outcome=ALREADY_APPLIED,
            failure_code=None,
            memory_item_id=str(row["memory_item_id"]),
            revision_id=str(row["created_revision_id"]),
            active_revision_id=str(row["resulting_active_revision_id"]),
            operation_id=str(row["operation_id"]),
        )

    @staticmethod
    def _terminal_result(conn: sqlite3.Connection, proposal_id: str) -> Optional[C.MemoryApplyResult]:
        row = conn.execute(
            "SELECT outcome,failure_code FROM memory_admission WHERE proposal_id=?",
            (proposal_id,),
        ).fetchone()
        if row is None or row["outcome"] == ACCEPTED:
            return None
        return C.MemoryApplyResult(
            proposal_id=proposal_id,
            outcome=str(row["outcome"]),
            failure_code=str(row["failure_code"]),
            memory_item_id=None,
            revision_id=None,
            active_revision_id=None,
            operation_id=None,
        )

    def _record_failure(
        self,
        conn: sqlite3.Connection,
        proposal_id: str,
        outcome: str,
        failure_code: str,
        now: str,
    ) -> C.MemoryApplyResult:
        if outcome not in {REJECTED, PRECONDITION_FAILED} or failure_code not in FAILURE_CODES:
            raise ValueError("invalid terminal admission")
        conn.execute(
            "INSERT INTO memory_admission(admission_id,proposal_id,schema_version,outcome,failure_code,evaluated_at) "
            "VALUES (?,?,?,?,?,?)",
            ("madm." + uuid.uuid4().hex, proposal_id, SCHEMA_VERSION, outcome, failure_code, now),
        )
        return self._result(proposal_id, outcome, failure_code=failure_code)

    @staticmethod
    def _authority_failure(
        resolver: Any,
        reference_id: Optional[str],
        *,
        proposal: C.MemoryWriteProposal,
        value_digest: str,
        unavailable_code: str,
        invalid_code: str,
    ) -> Optional[str]:
        resolution = resolver.resolve(reference_id, proposal=proposal, value_digest=value_digest)
        if resolution.status == CONFIRMED:
            return None
        if resolution.status == UNAVAILABLE:
            return unavailable_code
        return invalid_code

    def apply(self, proposal_id: str) -> C.MemoryApplyResult:
        """Apply one committed proposal. The kill switch is checked first."""
        try:
            enabled = self.enabled_provider()
        except Exception:
            enabled = None
        if enabled is not True:
            self._emit(
                proposalId=proposal_id, operation=None, admissionOutcome=REJECTED,
                failureCode="CANONICAL_LTM_DISABLED", memoryClass=None, mode="DISABLED",
            )
            return self._result(proposal_id, REJECTED, failure_code="CANONICAL_LTM_DISABLED")

        try:
            conn = self._connect()
        except sqlite3.OperationalError:
            return self._result(proposal_id, RETRYABLE_FAILURE, failure_code="DB_BUSY")
        except MemoryStoreError:
            return self._result(proposal_id, REJECTED, failure_code="SCHEMA_MISMATCH")

        try:
            conn.execute("BEGIN IMMEDIATE")
            applied = self._applied_result(conn, proposal_id)
            if applied is not None:
                conn.rollback()
                return applied
            terminal = self._terminal_result(conn, proposal_id)
            if terminal is not None:
                conn.rollback()
                return terminal

            row = self._load_proposal(conn, proposal_id)
            if row is None:
                conn.rollback()
                return self._result(proposal_id, REJECTED, failure_code="CANDIDATE_NOT_FOUND")
            try:
                proposal = self._proposal_from_row(row)
                binding = self._binding_from_row(row)
                proposal.validate()
            except (C.LearningContractError, ValueError, TypeError):
                result = self._record_failure(conn, proposal_id, REJECTED, "INVALID_PROPOSAL", self.now_fn())
                conn.commit()
                return result

            now = self.now_fn()
            if binding.validation_state != C.VALID:
                result = self._record_failure(conn, proposal_id, REJECTED, "CANDIDATE_INVALID", now)
                conn.commit()
                return result
            if str(row["assessment_outcome"]) != C.SHADOW_ELIGIBLE:
                result = self._record_failure(conn, proposal_id, REJECTED, "CANDIDATE_NOT_ELIGIBLE", now)
                conn.commit()
                return result
            expected_fingerprint = C.compute_proposal_fingerprint(proposal, binding)
            if proposal.proposal_fingerprint != expected_fingerprint:
                result = self._record_failure(
                    conn, proposal_id, REJECTED, "PROPOSAL_FINGERPRINT_MISMATCH", now,
                )
                conn.commit()
                return result

            policy = self.registry.resolve(
                proposal.target_memory_class, proposal.subject_namespace,
            )
            if policy is None:
                result = self._record_failure(conn, proposal_id, REJECTED, "UNKNOWN_MEMORY_CLASS", now)
                conn.commit()
                return result

            item = conn.execute(
                "SELECT * FROM memory_item WHERE memory_class=? AND subject_namespace=? AND subject_key=?",
                (proposal.target_memory_class, proposal.subject_namespace, proposal.subject_key),
            ).fetchone()
            prior_revision_id: Optional[str] = None
            restore_row: Optional[sqlite3.Row] = None

            if proposal.operation == C.CREATE:
                if item is not None:
                    result = self._record_failure(conn, proposal_id, PRECONDITION_FAILED, "ITEM_ALREADY_EXISTS", now)
                    conn.commit()
                    return result
                count = int(conn.execute("SELECT COUNT(*) FROM memory_item").fetchone()[0])
                if count >= self.capacity:
                    result = self._record_failure(conn, proposal_id, PRECONDITION_FAILED, "CAPACITY_PAUSED", now)
                    conn.commit()
                    return result
            else:
                if item is None:
                    result = self._record_failure(conn, proposal_id, PRECONDITION_FAILED, "ITEM_NOT_FOUND", now)
                    conn.commit()
                    return result
                active = conn.execute(
                    "SELECT revision_id FROM memory_active_revision WHERE memory_item_id=?",
                    (item["memory_item_id"],),
                ).fetchone()
                if active is None or str(active["revision_id"]) != proposal.expected_active_revision_id:
                    result = self._record_failure(
                        conn, proposal_id, PRECONDITION_FAILED, "ACTIVE_REVISION_MISMATCH", now,
                    )
                    conn.commit()
                    return result
                prior_revision_id = str(active["revision_id"])

            if proposal.operation == C.RESTORE:
                restore_row = conn.execute(
                    "SELECT * FROM memory_revision WHERE revision_id=?",
                    (proposal.restore_revision_id,),
                ).fetchone()
                if restore_row is None:
                    result = self._record_failure(
                        conn, proposal_id, PRECONDITION_FAILED, "RESTORE_REVISION_NOT_FOUND", now,
                    )
                    conn.commit()
                    return result
                if str(restore_row["memory_item_id"]) != str(item["memory_item_id"]):
                    result = self._record_failure(
                        conn, proposal_id, PRECONDITION_FAILED, "RESTORE_ITEM_MISMATCH", now,
                    )
                    conn.commit()
                    return result
                value_schema = str(restore_row["value_schema"])
                proposed_json = str(restore_row["normalized_value_json"])
            else:
                value_schema = str(proposal.value_schema)
                proposed_json = str(proposal.proposed_value_json)

            if value_schema != policy.value_schema:
                result = self._record_failure(conn, proposal_id, REJECTED, "UNKNOWN_VALUE_SCHEMA", now)
                conn.commit()
                return result
            try:
                decoded = json.loads(proposed_json)
                if not isinstance(decoded, dict):
                    raise ValueError("memory value must be an object")
                normalized_object = policy.normalize(decoded)
                normalized_json, value_digest = C.normalize_proposed_value(normalized_object)
            except Exception:
                result = self._record_failure(conn, proposal_id, REJECTED, "INVALID_PROPOSAL", now)
                conn.commit()
                return result
            if proposal.operation != C.RESTORE and (
                normalized_json != proposal.proposed_value_json
                or value_digest != proposal.proposed_value_digest
            ):
                result = self._record_failure(conn, proposal_id, REJECTED, "INVALID_PROPOSAL", now)
                conn.commit()
                return result
            if restore_row is not None and value_digest != str(restore_row["value_digest"]):
                result = self._record_failure(conn, proposal_id, REJECTED, "SCHEMA_MISMATCH", now)
                conn.commit()
                return result

            if policy.requires_consent:
                code = self._authority_failure(
                    self.consent_resolver, proposal.consent_ref_id,
                    proposal=proposal, value_digest=value_digest,
                    unavailable_code="CONSENT_AUTHORITY_UNAVAILABLE", invalid_code="CONSENT_INVALID",
                )
                if code:
                    result = self._record_failure(conn, proposal_id, REJECTED, code, now)
                    conn.commit()
                    return result
            if policy.requires_verification:
                code = self._authority_failure(
                    self.verifier_resolver, proposal.verification_outcome_ref_id,
                    proposal=proposal, value_digest=value_digest,
                    unavailable_code="VERIFIER_UNAVAILABLE", invalid_code="VERIFICATION_NOT_CONFIRMED",
                )
                if code:
                    result = self._record_failure(conn, proposal_id, REJECTED, code, now)
                    conn.commit()
                    return result
            if proposal.operation == C.RESTORE:
                code = self._authority_failure(
                    self.rollback_resolver, proposal.rollback_authorization_ref_id,
                    proposal=proposal, value_digest=value_digest,
                    unavailable_code="ROLLBACK_AUTHORITY_UNAVAILABLE", invalid_code="ROLLBACK_NOT_AUTHORIZED",
                )
                if code:
                    result = self._record_failure(conn, proposal_id, REJECTED, code, now)
                    conn.commit()
                    return result

            item_id = str(item["memory_item_id"]) if item is not None else "mitem." + uuid.uuid4().hex
            revision_id = "mrev." + uuid.uuid4().hex
            admission_id = "madm." + uuid.uuid4().hex
            operation_id = "mop." + uuid.uuid4().hex
            if item is None:
                conn.execute(
                    "INSERT INTO memory_item(memory_item_id,memory_class,subject_namespace,subject_key,created_at) "
                    "VALUES (?,?,?,?,?)",
                    (item_id, proposal.target_memory_class, proposal.subject_namespace, proposal.subject_key, now),
                )
            conn.execute(
                "INSERT INTO memory_admission(admission_id,proposal_id,schema_version,outcome,failure_code,evaluated_at) "
                "VALUES (?,?,?,?,NULL,?)",
                (admission_id, proposal_id, SCHEMA_VERSION, ACCEPTED, now),
            )
            conn.execute(
                "INSERT INTO memory_revision(revision_id,memory_item_id,schema_version,value_schema,"
                "normalized_value_json,value_digest,created_from_proposal_id,supersedes_revision_id,"
                "restores_revision_id,epistemic_basis,admission_basis,consent_ref_id,"
                "verification_outcome_ref_id,rollback_authorization_ref_id,created_at) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    revision_id, item_id, SCHEMA_VERSION, value_schema, normalized_json,
                    value_digest, proposal_id, prior_revision_id,
                    proposal.restore_revision_id if proposal.operation == C.RESTORE else None,
                    proposal.epistemic_basis, proposal.admission_basis, proposal.consent_ref_id,
                    proposal.verification_outcome_ref_id, proposal.rollback_authorization_ref_id, now,
                ),
            )
            conn.execute(
                "INSERT INTO memory_revision_source(revision_id,source_ordinal,source_owner,source_stream,"
                "source_record_id,source_schema_version,source_digest,occurred_at,subject_ref) "
                "VALUES (?,?,?,?,?,?,?,?,?)",
                (
                    revision_id, 0, binding.source_owner, binding.source_stream,
                    binding.source_record_id, binding.source_schema_version,
                    binding.source_digest, binding.occurred_at, binding.source_subject_ref,
                ),
            )
            if self.fault_hook:
                self.fault_hook("after_revision")
            conn.execute(
                "INSERT INTO memory_apply_audit(operation_id,proposal_id,admission_id,schema_version,"
                "operation,memory_item_id,prior_revision_id,created_revision_id,"
                "resulting_active_revision_id,rollback_authorization_ref_id,applied_at) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (
                    operation_id, proposal_id, admission_id, SCHEMA_VERSION, proposal.operation,
                    item_id, prior_revision_id, revision_id, revision_id,
                    proposal.rollback_authorization_ref_id, now,
                ),
            )
            if proposal.operation == C.CREATE:
                conn.execute(
                    "INSERT INTO memory_active_revision(memory_item_id,revision_id,updated_at,last_operation_id) "
                    "VALUES (?,?,?,?)",
                    (item_id, revision_id, now, operation_id),
                )
            else:
                updated = conn.execute(
                    "UPDATE memory_active_revision SET revision_id=?,updated_at=?,last_operation_id=? "
                    "WHERE memory_item_id=? AND revision_id=?",
                    (revision_id, now, operation_id, item_id, proposal.expected_active_revision_id),
                )
                if updated.rowcount != 1:
                    raise ProposalError("active revision changed during apply")
            if self.fault_hook:
                self.fault_hook("before_commit")
            conn.commit()
            self._emit(
                proposalId=proposal_id, operation=proposal.operation,
                admissionOutcome=ACCEPTED, failureCode=None,
                memoryClass=proposal.target_memory_class, revisionId=revision_id,
                priorRevisionId=prior_revision_id, mode="APPLY_TEST",
            )
            return self._result(
                proposal_id, APPLIED, item_id=item_id, revision_id=revision_id,
                active_revision_id=revision_id, operation_id=operation_id,
            )
        except sqlite3.OperationalError as exc:
            conn.rollback()
            if "locked" in str(exc).lower() or "busy" in str(exc).lower():
                return self._result(proposal_id, RETRYABLE_FAILURE, failure_code="DB_BUSY")
            raise
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
    def get_active(self, memory_class: str, namespace: str, subject_key: str) -> Optional[Dict[str, Any]]:
        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT i.memory_item_id,i.memory_class,i.subject_namespace,i.subject_key,"
                "r.revision_id,r.value_schema,r.normalized_value_json,r.value_digest,"
                "r.created_from_proposal_id,r.supersedes_revision_id,r.restores_revision_id,"
                "r.epistemic_basis,r.admission_basis,r.consent_ref_id,"
                "r.verification_outcome_ref_id,r.rollback_authorization_ref_id,r.created_at "
                "FROM memory_item i JOIN memory_active_revision a ON a.memory_item_id=i.memory_item_id "
                "JOIN memory_revision r ON r.revision_id=a.revision_id "
                "WHERE i.memory_class=? AND i.subject_namespace=? AND i.subject_key=?",
                (memory_class, namespace, subject_key),
            ).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def get_revision(self, revision_id: str) -> Optional[Dict[str, Any]]:
        conn = self._connect()
        try:
            row = conn.execute("SELECT * FROM memory_revision WHERE revision_id=?", (revision_id,)).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def get_lineage(self, memory_item_id: str) -> List[Dict[str, Any]]:
        conn = self._connect()
        try:
            return [
                dict(row) for row in conn.execute(
                    "SELECT r.* FROM memory_revision r "
                    "JOIN memory_apply_audit a ON a.created_revision_id=r.revision_id "
                    "WHERE r.memory_item_id=? ORDER BY a.rowid",
                    (memory_item_id,),
                )
            ]
        finally:
            conn.close()

    def explain(self, revision_id: str) -> Optional[Dict[str, Any]]:
        conn = self._connect()
        try:
            revision = conn.execute(
                "SELECT r.*,p.candidate_id,a.operation_id,a.operation,a.prior_revision_id,"
                "a.resulting_active_revision_id FROM memory_revision r "
                "JOIN learning_proposal p ON p.proposal_id=r.created_from_proposal_id "
                "JOIN memory_apply_audit a ON a.created_revision_id=r.revision_id "
                "WHERE r.revision_id=?",
                (revision_id,),
            ).fetchone()
            if revision is None:
                return None
            sources = [
                dict(row) for row in conn.execute(
                    "SELECT source_owner,source_stream,source_record_id,source_schema_version,"
                    "source_digest,occurred_at,subject_ref FROM memory_revision_source "
                    "WHERE revision_id=? ORDER BY source_ordinal",
                    (revision_id,),
                )
            ]
            return {"revision": dict(revision), "sources": sources}
        finally:
            conn.close()

    def counts(self) -> Dict[str, int]:
        conn = self._connect()
        try:
            return {
                table: int(conn.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0])
                for table in sorted(MEMORY_TABLES | {"learning_proposal"})
            }
        finally:
            conn.close()
