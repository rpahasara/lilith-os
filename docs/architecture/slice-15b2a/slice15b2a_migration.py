"""Dedicated, backup-gated Slice 15B2a schema migration authorities."""

from __future__ import annotations

import hashlib
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, Optional, Tuple

try:
    from . import canonical_authority as A
    from . import learning_v2 as L
    from . import memory_v2 as M
    from . import privacy_governance as P
except ImportError:  # deploy-exact flat-directory tests
    import canonical_authority as A
    import learning_v2 as L
    import memory_v2 as M
    import privacy_governance as P


SCHEMA_VERSION = 1

COGNITIVE_15B2A_TABLES = (
    A.COGNITIVE_AUTHORITY_TABLES | L.LEARNING_V2_TABLES | M.REGISTRY_TABLES
)
COGNITIVE_15B2A_SCHEMA_OBJECTS = (
    A.AUTHORITY_SCHEMA_OBJECTS | L.LEARNING_V2_SCHEMA_OBJECTS | M.REGISTRY_SCHEMA_OBJECTS
)
COGNITIVE_MIGRATION_STATEMENTS = (
    A.AUTHORITY_MIGRATION_STATEMENTS
    + L.LEARNING_V2_MIGRATION_STATEMENTS
    + M.REGISTRY_MIGRATION_STATEMENTS
)

OWNER_SCHEMAS = (
    ("actor_schema_migration", A.ACTOR_TABLES | frozenset({
        "actor_evidence_ref_no_update", "actor_evidence_ref_no_delete",
        "actor_evidence_consumption_no_update", "actor_evidence_consumption_no_delete",
    })),
    ("consent_schema_migration", A.CONSENT_TABLES | frozenset({
        "consent_grant_fingerprint", "consent_grant_no_update", "consent_grant_no_delete",
        "consent_revocation_one_per_grant", "consent_revocation_no_update",
        "consent_revocation_no_delete",
    })),
    ("policy_schema_migration", A.POLICY_TABLES | frozenset({
        "policy_decision_fingerprint", "policy_decision_action",
        "policy_decision_no_update", "policy_decision_no_delete",
    })),
    ("rollback_schema_migration", A.ROLLBACK_TABLES | frozenset({
        "rollback_authorization_fingerprint", "rollback_authorization_no_update",
        "rollback_authorization_no_delete", "rollback_consumption_no_update",
        "rollback_consumption_no_delete",
    })),
    ("learning_v2_schema_migration", L.LEARNING_V2_SCHEMA_OBJECTS),
    ("memory_registry_schema_migration", M.REGISTRY_SCHEMA_OBJECTS),
)


class MigrationError(RuntimeError):
    pass


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds").replace(
        "+00:00", "Z"
    )


def _normal_sql(sql: str) -> str:
    return " ".join(str(sql).split())


def schema_fingerprint(conn: sqlite3.Connection, objects: Iterable[str]) -> str:
    expected = frozenset(objects)
    marks = ",".join("?" for _ in expected)
    rows = conn.execute(
        "SELECT type,name,sql FROM sqlite_master WHERE sql IS NOT NULL "
        f"AND name IN ({marks}) ORDER BY type,name",
        tuple(sorted(expected)),
    ).fetchall()
    names = {str(row[1]) for row in rows}
    if names != expected:
        raise MigrationError(
            "schema object set mismatch: missing=%s extra=%s"
            % (sorted(expected - names), sorted(names - expected))
        )
    payload = "\n".join(
        f"{row[0]}:{row[1]}:{_normal_sql(row[2])}" for row in rows
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def complete_schema_fingerprint(conn: sqlite3.Connection) -> str:
    rows = conn.execute(
        "SELECT type,name,sql FROM sqlite_master WHERE sql IS NOT NULL ORDER BY type,name"
    ).fetchall()
    payload = "\n".join(
        f"{row[0]}:{row[1]}:{_normal_sql(row[2])}" for row in rows
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def table_counts(conn: sqlite3.Connection) -> Dict[str, int]:
    tables = [
        str(row[0])
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' "
            "ORDER BY name"
        )
    ]
    return {
        table: int(conn.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0])
        for table in tables
    }


def _connect(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(path), timeout=5.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA busy_timeout=5000")
    conn.execute("PRAGMA synchronous=FULL")
    return conn


def migrate_cognitive(
    path: Path,
    *,
    verified_backup: Optional[Any] = None,
    production_path: Optional[Path] = None,
    applied_at: Optional[str] = None,
) -> Tuple[Dict[str, str], str]:
    """Apply every cognitive owner schema atomically after backup revalidation."""
    target = Path(path).resolve()
    production = Path(production_path).resolve() if production_path else None
    if production is not None and target == production:
        if verified_backup is None:
            raise MigrationError("production migration requires verified backup")
        try:
            try:
                from . import memory_store
            except ImportError:
                import memory_store
            memory_store._validate_verified_backup(target, verified_backup)
        except Exception as exc:
            raise MigrationError("production backup proof is invalid or stale") from exc
    if not target.is_file():
        raise MigrationError("cognitive database is unavailable")
    conn = _connect(target)
    try:
        before = table_counts(conn)
        baseline_tables = set(before)
        if not {
            "learning_schema_migration",
            "learning_candidate",
            "learning_proposal",
            "memory_schema_migration",
            "memory_item",
        }.issubset(baseline_tables):
            raise MigrationError("Slice 15B1 baseline is unavailable")
        conn.execute("BEGIN IMMEDIATE")
        for statement in COGNITIVE_MIGRATION_STATEMENTS:
            conn.execute(statement)
        timestamp = applied_at or utc_now()
        fingerprints: Dict[str, str] = {}
        for ledger, objects in OWNER_SCHEMAS:
            fingerprint = schema_fingerprint(conn, objects)
            fingerprints[ledger] = fingerprint
            row = conn.execute(
                f'SELECT version,schema_fingerprint FROM "{ledger}" '
                "ORDER BY version DESC LIMIT 1"
            ).fetchone()
            if row is None:
                conn.execute(
                    f'INSERT INTO "{ledger}"(version,schema_fingerprint,applied_at) '
                    "VALUES (?,?,?)",
                    (SCHEMA_VERSION, fingerprint, timestamp),
                )
            elif int(row[0]) != SCHEMA_VERSION or str(row[1]) != fingerprint:
                raise MigrationError(f"{ledger} fingerprint mismatch")
        after = table_counts(conn)
        for table, count in before.items():
            if after.get(table) != count:
                raise MigrationError(f"pre-existing table count changed: {table}")
        for table in COGNITIVE_15B2A_TABLES:
            expected = 1 if table.endswith("_schema_migration") else 0
            if after.get(table) != expected:
                raise MigrationError(f"new cognitive table was not empty: {table}")
        if conn.execute("PRAGMA foreign_key_check").fetchall():
            raise MigrationError("cognitive foreign-key check failed")
        if str(conn.execute("PRAGMA integrity_check").fetchone()[0]) != "ok":
            raise MigrationError("cognitive integrity check failed")
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
    return fingerprints, complete


def migrate_privacy(
    path: Path,
    *,
    applied_at: Optional[str] = None,
    max_backup_retention_days: int = P.DEFAULT_MAX_BACKUP_RETENTION_DAYS,
) -> Tuple[str, str]:
    """Create/verify the physically separate Privacy Governance database."""
    if isinstance(max_backup_retention_days, bool) or not 1 <= int(max_backup_retention_days) <= 30:
        raise MigrationError("backup retention ceiling is invalid")
    target = Path(path).resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    old_umask = os.umask(0o077)
    try:
        conn = _connect(target)
    finally:
        os.umask(old_umask)
    try:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("BEGIN IMMEDIATE")
        existing = {
            str(row[0])
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
            )
        }
        if not existing.issubset(P.PRIVACY_TABLES):
            raise MigrationError("privacy database contains an unrecognized table")
        for statement in P.PRIVACY_MIGRATION_STATEMENTS:
            conn.execute(statement)
        timestamp = applied_at or utc_now()
        fingerprint = schema_fingerprint(conn, P.PRIVACY_SCHEMA_OBJECTS)
        row = conn.execute(
            "SELECT version,schema_fingerprint FROM privacy_schema_migration "
            "ORDER BY version DESC LIMIT 1"
        ).fetchone()
        if row is None:
            conn.execute(
                "INSERT INTO privacy_schema_migration VALUES (?,?,?)",
                (SCHEMA_VERSION, fingerprint, timestamp),
            )
        elif int(row[0]) != SCHEMA_VERSION or str(row[1]) != fingerprint:
            raise MigrationError("privacy schema fingerprint mismatch")
        config = conn.execute(
            "SELECT authority_version,max_backup_retention_days,restore_suppression_required "
            "FROM privacy_governance_config WHERE config_id='production'"
        ).fetchone()
        expected_config = (
            "PRIVACY_GOVERNANCE_AUTHORITY_V1",
            int(max_backup_retention_days),
            1,
        )
        if config is None:
            conn.execute(
                "INSERT INTO privacy_governance_config VALUES (?,?,?,?,?)",
                ("production", *expected_config, timestamp),
            )
        elif tuple(config) != expected_config:
            raise MigrationError("privacy governance config mismatch")
        counts = table_counts(conn)
        for table in P.PRIVACY_TABLES:
            expected = 1 if table in {
                "privacy_schema_migration", "privacy_governance_config"
            } else 0
            if counts.get(table) != expected:
                raise MigrationError(f"privacy table was not empty: {table}")
        if conn.execute("PRAGMA foreign_key_check").fetchall():
            raise MigrationError("privacy foreign-key check failed")
        if str(conn.execute("PRAGMA integrity_check").fetchone()[0]) != "ok":
            raise MigrationError("privacy integrity check failed")
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
