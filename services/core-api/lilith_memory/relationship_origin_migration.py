"""Explicit, backup-gated schema v3 for the relationship-origin family.

Nothing here runs at import time, and no runtime path calls ``migrate``. It moves the three owner ledgers from version
1 (DEV today) or version 2 (FM-02 First Interaction) to version 3 in ONE transaction, using the reviewed FM-02
rebuild procedure (``first_interaction_migration``):

- ``consent_grant`` and ``policy_decision`` are rebuilt with the v3 paired CHECKs (each versioned family admits only
  CREATE of its own tuple; the codename purpose can name no family tuple);
- ``learning_proposal_ref`` is rebuilt so its family CHECK admits ``OWNER_DIRECTED_RELATIONSHIP_ORIGIN_V1``;
- the five relationship-origin L18 tables are added, and, from version 1, the five First Interaction tables as well
  (v3 contains v2). Those stay empty: the First Interaction identity is permanently suppressed.

Every other object keeps its exact SQL. Rebuilt tables keep every row byte-for-byte (verified by digest), indexes and
triggers are re-created from their exact prior SQL, and the migration fails closed (rollback) on any mismatch.

    schema v3 installed != memory creation enabled
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Dict, Optional

from . import backup as governed_backup
from . import canonical_authority as A
from . import canonical_migration
from . import first_interaction_migration as FIM
from . import learning_v2 as L
from . import slice15b2a_migration as S


RELATIONSHIP_ORIGIN_SCHEMA_VERSION = 3
FAULT_POINTS = ("after_rebuild", "after_family_tables", "before_ledger", "before_commit")

_V1_OBJECTS = dict(S.OWNER_SCHEMAS)
# ledger -> (rebuilt table, its v3 DDL, {version: object set})
_LEDGERS = (
    ("consent_schema_migration", "consent_grant", A.CONSENT_GRANT_V3_DDL,
     {1: _V1_OBJECTS["consent_schema_migration"], 2: _V1_OBJECTS["consent_schema_migration"],
      3: _V1_OBJECTS["consent_schema_migration"]}),
    ("policy_schema_migration", "policy_decision", A.POLICY_DECISION_V3_DDL,
     {1: _V1_OBJECTS["policy_schema_migration"], 2: _V1_OBJECTS["policy_schema_migration"],
      3: _V1_OBJECTS["policy_schema_migration"]}),
    ("learning_v2_schema_migration", "learning_proposal_ref", L.LEARNING_PROPOSAL_REF_V3_DDL,
     {1: L.LEARNING_V2_SCHEMA_OBJECTS, 2: L.LEARNING_V2_SCHEMA_OBJECTS_V2, 3: L.LEARNING_V2_SCHEMA_OBJECTS_V3}),
)


class RelationshipOriginMigrationError(RuntimeError):
    pass


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def _state(conn: sqlite3.Connection) -> int:
    """1, 2 or 3 when every ledger agrees and matches its object set exactly; otherwise refuse."""
    states = set()
    for ledger, _table, _ddl, objects in _LEDGERS:
        latest = FIM._latest(conn, ledger)
        version = latest[0] if latest else None
        if version not in objects or latest[1] != FIM._fingerprint(conn, objects[version]):
            raise RelationshipOriginMigrationError(f"{ledger} is at an unknown version or fingerprint")
        states.add(version)
    if len(states) != 1:
        raise RelationshipOriginMigrationError("owner ledgers are at mixed schema versions")
    return states.pop()


def migrate(
    path: Path,
    *,
    backup_manifest: governed_backup.BackupManifest,
    applied_at: Optional[str] = None,
    fault_hook: Optional[Callable[[str], None]] = None,
) -> Dict[str, str]:
    """Move the three owner ledgers to schema v3. Idempotent on a v3 database; fails closed otherwise."""
    target = Path(path).resolve()
    governed_backup.verify_backup(target, backup_manifest, expected_role="cognitive")
    conn = sqlite3.connect(str(target), timeout=5.0)
    conn.row_factory = sqlite3.Row
    try:
        # As in FM-02: both pragmas outside a transaction keep every REFERENCES clause naming the rebuilt tables.
        conn.execute("PRAGMA foreign_keys=OFF")
        conn.execute("PRAGMA legacy_alter_table=ON")
        conn.execute("PRAGMA secure_delete=ON")
        conn.execute("PRAGMA busy_timeout=5000")
        conn.execute("BEGIN IMMEDIATE")
        try:
            canonical_migration._verify_current_schema(conn)
        except Exception as exc:
            raise RelationshipOriginMigrationError("canonical runtime schema v2 is required") from exc
        current = _state(conn)
        if current == RELATIONSHIP_ORIGIN_SCHEMA_VERSION:
            if conn.execute("PRAGMA foreign_key_check").fetchall():
                raise RelationshipOriginMigrationError("foreign-key check failed")
            conn.rollback()
            return {ledger: FIM._fingerprint(conn, objects[3]) or "" for ledger, _t, _d, objects in _LEDGERS}
        added_tables = L.RELATIONSHIP_ORIGIN_TABLES | (L.FIRST_INTERACTION_TABLES if current == 1 else frozenset())
        added_objects = L.RELATIONSHIP_ORIGIN_SCHEMA_OBJECTS | (
            L.FIRST_INTERACTION_SCHEMA_OBJECTS if current == 1 else frozenset())
        statements = (L.FIRST_INTERACTION_MIGRATION_STATEMENTS if current == 1 else ()) \
            + L.RELATIONSHIP_ORIGIN_MIGRATION_STATEMENTS
        rebuilt = [table for _ledger, table, _ddl, _objects in _LEDGERS]
        counts = FIM._counts(conn)
        rows = {table: FIM._rows_digest(conn, table) for table in rebuilt}
        others = FIM._other_objects(conn, rebuilt)
        for _ledger, table, ddl, _objects in _LEDGERS:
            FIM._rebuild(conn, table, ddl)
        if fault_hook:
            fault_hook("after_rebuild")
        for statement in statements:
            conn.execute(statement)
        if fault_hook:
            fault_hook("after_family_tables")
        if {table: FIM._rows_digest(conn, table) for table in rebuilt} != rows:
            raise RelationshipOriginMigrationError("rebuilt table rows changed")
        after = FIM._counts(conn)
        if {t: n for t, n in after.items() if t not in added_tables} != counts:
            raise RelationshipOriginMigrationError("pre-existing table counts changed")
        if any(after.get(table) != 0 for table in added_tables):
            raise RelationshipOriginMigrationError("new family tables are not empty")
        objects_now = FIM._other_objects(conn, rebuilt)
        added = {key for key in objects_now if key.split(":", 1)[1] in added_objects}
        if {k: v for k, v in objects_now.items() if k not in added} != others:
            raise RelationshipOriginMigrationError("an unrelated schema object changed")
        if conn.execute("PRAGMA foreign_key_check").fetchall():
            raise RelationshipOriginMigrationError("foreign-key check failed")
        if str(conn.execute("PRAGMA integrity_check").fetchone()[0]) != "ok":
            raise RelationshipOriginMigrationError("integrity check failed")
        if fault_hook:
            fault_hook("before_ledger")
        timestamp = applied_at or _now()
        fingerprints: Dict[str, str] = {}
        for ledger, _table, _ddl, objects in _LEDGERS:
            fingerprints[ledger] = S.schema_fingerprint(conn, objects[3])
            conn.execute(
                f'INSERT INTO "{ledger}"(version,schema_fingerprint,applied_at) VALUES (?,?,?)',
                (RELATIONSHIP_ORIGIN_SCHEMA_VERSION, fingerprints[ledger], timestamp),
            )
        if _state(conn) != RELATIONSHIP_ORIGIN_SCHEMA_VERSION:
            raise RelationshipOriginMigrationError("schema v3 did not verify")
        if fault_hook:
            fault_hook("before_commit")
        conn.commit()
        return fingerprints
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def schema_state(path: Path) -> int:
    """Read-only: 1, 2 or 3 when the owner ledgers verify exactly, else RelationshipOriginMigrationError."""
    conn = sqlite3.connect(f"file:{Path(path).resolve().as_posix()}?mode=ro", uri=True)
    try:
        return _state(conn)
    finally:
        conn.close()
