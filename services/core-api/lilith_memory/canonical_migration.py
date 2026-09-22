"""Explicit backup-gated family-neutral L04 schema migration.

Nothing in this module runs at import time.  ``migrate`` is the only schema
mutation boundary and it accepts verified backup evidence for the current
database image.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sqlite3
from dataclasses import fields
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, Tuple

from . import backup as governed_backup
from . import learning_v2
from . import memory_store


MIGRATION_VERSION = 2
V1_FAMILY = learning_v2.V1_PROPOSAL_FAMILY


class CanonicalMigrationError(RuntimeError):
    pass


_IMMUTABILITY_TRIGGERS = (
    "memory_revision_no_update",
    "memory_revision_no_delete",
    "memory_revision_source_no_update",
    "memory_revision_source_no_delete",
    "memory_admission_no_update",
    "memory_admission_no_delete",
    "memory_apply_audit_no_update",
    "memory_apply_audit_no_delete",
    "memory_active_revision_no_delete",
    "memory_active_revision_identity_guard",
)


_V2_STATEMENTS = (
    """
    CREATE TABLE memory_revision_v2_new (
        revision_id TEXT PRIMARY KEY,
        memory_item_id TEXT NOT NULL REFERENCES memory_item(memory_item_id),
        schema_version INTEGER NOT NULL CHECK (schema_version = 1),
        value_schema TEXT NOT NULL CHECK (length(value_schema) BETWEEN 1 AND 64),
        normalized_value_json TEXT NOT NULL CHECK (json_valid(normalized_value_json)),
        value_digest TEXT NOT NULL CHECK (length(value_digest) = 64),
        created_from_proposal_ref_id TEXT NOT NULL UNIQUE
            REFERENCES learning_proposal_ref(proposal_ref_id),
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
    """
    CREATE TABLE memory_revision_source_v2_new (
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
    """
    CREATE TABLE memory_admission_v2_new (
        admission_id TEXT PRIMARY KEY,
        proposal_ref_id TEXT NOT NULL UNIQUE
            REFERENCES learning_proposal_ref(proposal_ref_id),
        schema_version INTEGER NOT NULL CHECK (schema_version = 1),
        outcome TEXT NOT NULL
            CHECK (outcome IN ('ACCEPTED','REJECTED','PRECONDITION_FAILED')),
        failure_code TEXT,
        evaluated_at TEXT NOT NULL,
        CHECK (
            (outcome = 'ACCEPTED' AND failure_code IS NULL)
            OR (outcome <> 'ACCEPTED' AND failure_code IS NOT NULL)
        )
    )
    """,
    """
    CREATE TABLE memory_apply_audit_v2_new (
        operation_id TEXT PRIMARY KEY,
        proposal_ref_id TEXT NOT NULL UNIQUE
            REFERENCES learning_proposal_ref(proposal_ref_id),
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
            (operation = 'CREATE' AND prior_revision_id IS NULL
             AND rollback_authorization_ref_id IS NULL)
            OR (operation = 'SUPERSEDE' AND prior_revision_id IS NOT NULL
                AND rollback_authorization_ref_id IS NULL)
            OR (operation = 'RESTORE' AND prior_revision_id IS NOT NULL
                AND rollback_authorization_ref_id IS NOT NULL)
        )
    )
    """,
    """
    CREATE TABLE memory_active_revision_v2_new (
        memory_item_id TEXT PRIMARY KEY REFERENCES memory_item(memory_item_id),
        revision_id TEXT NOT NULL UNIQUE,
        updated_at TEXT NOT NULL,
        last_operation_id TEXT NOT NULL UNIQUE REFERENCES memory_apply_audit(operation_id)
            DEFERRABLE INITIALLY DEFERRED,
        FOREIGN KEY(memory_item_id, revision_id)
            REFERENCES memory_revision(memory_item_id, revision_id)
    )
    """,
)


_POST_STATEMENTS = (
    "CREATE INDEX memory_revision_item_created ON memory_revision(memory_item_id,created_at,revision_id)",
    "CREATE INDEX memory_revision_item_digest ON memory_revision(memory_item_id,value_digest)",
    "CREATE INDEX memory_revision_source_lookup ON memory_revision_source(source_owner,source_stream,source_record_id)",
    "CREATE INDEX memory_apply_audit_item_time ON memory_apply_audit(memory_item_id,applied_at,operation_id)",
    """CREATE TRIGGER memory_revision_no_update BEFORE UPDATE ON memory_revision
        BEGIN SELECT RAISE(ABORT,'memory revision is immutable'); END""",
    """CREATE TRIGGER memory_revision_no_delete BEFORE DELETE ON memory_revision
        BEGIN SELECT RAISE(ABORT,'memory revision deletion is unavailable'); END""",
    """CREATE TRIGGER memory_revision_source_no_update BEFORE UPDATE ON memory_revision_source
        BEGIN SELECT RAISE(ABORT,'revision provenance is immutable'); END""",
    """CREATE TRIGGER memory_revision_source_no_delete BEFORE DELETE ON memory_revision_source
        BEGIN SELECT RAISE(ABORT,'revision provenance deletion is unavailable'); END""",
    """CREATE TRIGGER memory_admission_no_update BEFORE UPDATE ON memory_admission
        BEGIN SELECT RAISE(ABORT,'memory admission is immutable'); END""",
    """CREATE TRIGGER memory_admission_no_delete BEFORE DELETE ON memory_admission
        BEGIN SELECT RAISE(ABORT,'memory admission is immutable'); END""",
    """CREATE TRIGGER memory_apply_audit_no_update BEFORE UPDATE ON memory_apply_audit
        BEGIN SELECT RAISE(ABORT,'memory apply audit is immutable'); END""",
    """CREATE TRIGGER memory_apply_audit_no_delete BEFORE DELETE ON memory_apply_audit
        BEGIN SELECT RAISE(ABORT,'memory apply audit deletion is unavailable'); END""",
    """CREATE TRIGGER memory_active_revision_no_delete BEFORE DELETE ON memory_active_revision
        BEGIN SELECT RAISE(ABORT,'active revision deletion is unavailable'); END""",
    """CREATE TRIGGER memory_active_revision_identity_guard
        BEFORE UPDATE OF memory_item_id ON memory_active_revision
        BEGIN SELECT RAISE(ABORT,'active revision item identity is immutable'); END""",
    """
    CREATE TABLE IF NOT EXISTS canonical_runtime_schema_migration (
        version INTEGER PRIMARY KEY,
        schema_fingerprint TEXT NOT NULL,
        source_memory_schema_version INTEGER NOT NULL,
        applied_at TEXT NOT NULL
    )
    """,
)


RUNTIME_OBJECTS = frozenset(
    {
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
        "canonical_runtime_schema_migration",
    }
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds").replace(
        "+00:00", "Z"
    )


def _normal_sql(sql: str) -> str:
    return " ".join(str(sql).split())


def schema_fingerprint(conn: sqlite3.Connection) -> str:
    marks = ",".join("?" for _ in RUNTIME_OBJECTS)
    rows = conn.execute(
        "SELECT type,name,sql FROM sqlite_master WHERE sql IS NOT NULL "
        f"AND name IN ({marks}) ORDER BY type,name",
        tuple(sorted(RUNTIME_OBJECTS)),
    ).fetchall()
    if {str(row[1]) for row in rows} != RUNTIME_OBJECTS:
        raise CanonicalMigrationError("canonical runtime schema object set mismatch")
    payload = "\n".join(
        f"{row[0]}:{row[1]}:{_normal_sql(row[2])}" for row in rows
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _v1_ref_id(proposal_id: str) -> str:
    return "proposal-ref.v1." + hashlib.sha256(proposal_id.encode("utf-8")).hexdigest()[:48]


def _table_counts(conn: sqlite3.Connection, names: Iterable[str]) -> Dict[str, int]:
    return {
        name: int(conn.execute(f'SELECT COUNT(*) FROM "{name}"').fetchone()[0])
        for name in names
    }


def _verify_source_schema(conn: sqlite3.Connection) -> None:
    required = {
        "learning_proposal",
        "learning_proposal_ref",
        "learning_proposal_v2",
        "memory_schema_migration",
        "memory_revision",
        "memory_revision_source",
        "memory_admission",
        "memory_apply_audit",
        "memory_active_revision",
    }
    actual = {
        str(row[0])
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        )
    }
    if not required.issubset(actual):
        raise CanonicalMigrationError("recognized Slice 15B2a source schema is unavailable")
    columns = {
        str(row[1]) for row in conn.execute("PRAGMA table_info(memory_revision)")
    }
    if "created_from_proposal_id" not in columns or "created_from_proposal_ref_id" in columns:
        raise CanonicalMigrationError("source memory schema is not version 1")
    ledger = conn.execute(
        "SELECT version,schema_fingerprint FROM memory_schema_migration "
        "ORDER BY version DESC LIMIT 1"
    ).fetchone()
    if (
        ledger is None
        or int(ledger[0]) != 1
        or str(ledger[1]) != memory_store.memory_schema_fingerprint(conn)
    ):
        raise CanonicalMigrationError("source memory schema fingerprint is unknown")


def _verify_current_schema(conn: sqlite3.Connection) -> str:
    columns = {
        str(row[1]) for row in conn.execute("PRAGMA table_info(memory_revision)")
    }
    if "created_from_proposal_ref_id" not in columns:
        raise CanonicalMigrationError("canonical runtime schema is malformed")
    fingerprint = schema_fingerprint(conn)
    ledger = conn.execute(
        "SELECT version,schema_fingerprint FROM canonical_runtime_schema_migration "
        "ORDER BY version DESC LIMIT 1"
    ).fetchone()
    if ledger is None or int(ledger[0]) != MIGRATION_VERSION or str(ledger[1]) != fingerprint:
        raise CanonicalMigrationError("canonical runtime fingerprint mismatch")
    return fingerprint


def migrate(
    path: Path,
    *,
    backup_manifest: governed_backup.BackupManifest,
    applied_at: str | None = None,
) -> Tuple[int, str]:
    """Migrate the current Slice 15B2a database to family-neutral L04 rows."""
    target = Path(path).resolve()
    governed_backup.verify_backup(target, backup_manifest, expected_role="cognitive")
    conn = sqlite3.connect(str(target), timeout=5.0)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA foreign_keys=ON")
        existing = {
            str(row[0])
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
            )
        }
        if "canonical_runtime_schema_migration" in existing:
            fingerprint = _verify_current_schema(conn)
            if conn.execute("PRAGMA foreign_key_check").fetchall():
                raise CanonicalMigrationError("canonical runtime foreign-key check failed")
            if str(conn.execute("PRAGMA integrity_check").fetchone()[0]) != "ok":
                raise CanonicalMigrationError("canonical runtime integrity check failed")
            return MIGRATION_VERSION, fingerprint
        _verify_source_schema(conn)
    finally:
        conn.close()

    conn = sqlite3.connect(str(target), timeout=5.0)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA foreign_keys=OFF")
        conn.execute("BEGIN IMMEDIATE")
        before = _table_counts(
            conn,
            (
                "memory_item",
                "memory_revision",
                "memory_revision_source",
                "memory_admission",
                "memory_apply_audit",
                "memory_active_revision",
            ),
        )
        v1_rows = conn.execute(
            "SELECT proposal_id,proposal_fingerprint,created_at FROM learning_proposal "
            "ORDER BY proposal_id"
        ).fetchall()
        for row in v1_rows:
            values = (
                _v1_ref_id(str(row[0])),
                V1_FAMILY,
                1,
                str(row[0]),
                str(row[1]),
                str(row[2]),
            )
            conn.execute(
                "INSERT OR IGNORE INTO learning_proposal_ref VALUES (?,?,?,?,?,?)",
                values,
            )
            actual = conn.execute(
                "SELECT proposal_ref_id,proposal_family,proposal_schema_version,"
                "family_proposal_id,immutable_fingerprint,created_at "
                "FROM learning_proposal_ref WHERE proposal_family=? AND family_proposal_id=?",
                (V1_FAMILY, str(row[0])),
            ).fetchone()
            if actual is None or tuple(actual) != values:
                raise CanonicalMigrationError("V1 proposal reference conflicts with source")
        for trigger in _IMMUTABILITY_TRIGGERS:
            conn.execute(f'DROP TRIGGER "{trigger}"')
        for index in (
            "memory_revision_item_created",
            "memory_revision_item_digest",
            "memory_revision_source_lookup",
            "memory_apply_audit_item_time",
        ):
            conn.execute(f'DROP INDEX "{index}"')
        for statement in _V2_STATEMENTS:
            conn.execute(statement)
        conn.execute(
            "INSERT INTO memory_revision_v2_new "
            "SELECT r.revision_id,r.memory_item_id,r.schema_version,r.value_schema,"
            "r.normalized_value_json,r.value_digest,p.proposal_ref_id,"
            "r.supersedes_revision_id,r.restores_revision_id,r.epistemic_basis,"
            "r.admission_basis,r.consent_ref_id,r.verification_outcome_ref_id,"
            "r.rollback_authorization_ref_id,r.created_at "
            "FROM memory_revision r JOIN learning_proposal_ref p "
            "ON p.proposal_family=? AND p.family_proposal_id=r.created_from_proposal_id",
            (V1_FAMILY,),
        )
        conn.execute("INSERT INTO memory_revision_source_v2_new SELECT * FROM memory_revision_source")
        conn.execute(
            "INSERT INTO memory_admission_v2_new "
            "SELECT a.admission_id,p.proposal_ref_id,a.schema_version,a.outcome,"
            "a.failure_code,a.evaluated_at FROM memory_admission a "
            "JOIN learning_proposal_ref p ON p.proposal_family=? "
            "AND p.family_proposal_id=a.proposal_id",
            (V1_FAMILY,),
        )
        conn.execute(
            "INSERT INTO memory_apply_audit_v2_new "
            "SELECT a.operation_id,p.proposal_ref_id,a.admission_id,a.schema_version,"
            "a.operation,a.memory_item_id,a.prior_revision_id,a.created_revision_id,"
            "a.resulting_active_revision_id,a.rollback_authorization_ref_id,a.applied_at "
            "FROM memory_apply_audit a JOIN learning_proposal_ref p "
            "ON p.proposal_family=? AND p.family_proposal_id=a.proposal_id",
            (V1_FAMILY,),
        )
        conn.execute("INSERT INTO memory_active_revision_v2_new SELECT * FROM memory_active_revision")
        for table in (
            "memory_active_revision",
            "memory_apply_audit",
            "memory_admission",
            "memory_revision_source",
            "memory_revision",
        ):
            conn.execute(f'DROP TABLE "{table}"')
        for temporary, final in (
            ("memory_revision_v2_new", "memory_revision"),
            ("memory_revision_source_v2_new", "memory_revision_source"),
            ("memory_admission_v2_new", "memory_admission"),
            ("memory_apply_audit_v2_new", "memory_apply_audit"),
            ("memory_active_revision_v2_new", "memory_active_revision"),
        ):
            conn.execute(f'ALTER TABLE "{temporary}" RENAME TO "{final}"')
        for statement in _POST_STATEMENTS:
            conn.execute(statement)
        fingerprint = schema_fingerprint(conn)
        conn.execute(
            "INSERT INTO canonical_runtime_schema_migration VALUES (?,?,?,?)",
            (MIGRATION_VERSION, fingerprint, 1, applied_at or _now()),
        )
        after = _table_counts(conn, before)
        if before != after:
            raise CanonicalMigrationError("canonical row counts changed during migration")
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    verify = sqlite3.connect(str(target), timeout=5.0)
    try:
        verify.execute("PRAGMA foreign_keys=ON")
        if verify.execute("PRAGMA foreign_key_check").fetchall():
            raise CanonicalMigrationError("post-migration foreign-key check failed")
        if str(verify.execute("PRAGMA integrity_check").fetchone()[0]) != "ok":
            raise CanonicalMigrationError("post-migration integrity check failed")
        fingerprint = _verify_current_schema(verify)
    finally:
        verify.close()
    try:
        os.chmod(target, 0o600)
    except OSError:
        pass
    return MIGRATION_VERSION, fingerprint


def _load_manifest(path: Path) -> governed_backup.BackupManifest:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    raw["source_table_counts"] = tuple(tuple(value) for value in raw["source_table_counts"])
    allowed = {field.name for field in fields(governed_backup.BackupManifest)}
    if set(raw) != allowed:
        raise CanonicalMigrationError("backup manifest shape is invalid")
    return governed_backup.BackupManifest(**raw)


def main() -> int:
    parser = argparse.ArgumentParser(description="Apply Slice 15B2b-A canonical migration")
    parser.add_argument("--database", required=True, type=Path)
    parser.add_argument("--backup-manifest", required=True, type=Path)
    args = parser.parse_args()
    version, fingerprint = migrate(
        args.database, backup_manifest=_load_manifest(args.backup_manifest)
    )
    print(json.dumps({"version": version, "schemaFingerprint": fingerprint}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
