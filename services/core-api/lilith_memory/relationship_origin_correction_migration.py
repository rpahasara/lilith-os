"""Explicit, backup-gated schema v4: owner-approved correction (SUPERSEDE) of the relationship-origin memory.

Nothing here runs at import time, and no runtime path calls ``migrate``. It moves the three owner ledgers from version
3 (``relationship_origin_migration``) to version 4 in ONE transaction, using the reviewed FM-02 / v3 rebuild procedure
(``first_interaction_migration``):

- ``consent_grant`` and ``policy_decision`` are rebuilt with the v4 paired CHECKs: the relationship-origin family may
  record CREATE (no prior revision) or SUPERSEDE (bound to the active revision it replaces) of its one tuple; every
  other family and the codename scope are exactly v3's;
- ``learning_ro_intent_v1``, ``learning_ro_candidate_v1`` and ``learning_ro_proposal_v1`` are rebuilt with the same
  widening; their indexes and immutability triggers are re-created from their exact prior SQL.

The original memory and every admitted revision stay untouched: rows are copied byte-for-byte (verified by digest), a
correction is a NEW successor revision written later through the normal governed chain, and FORGET stays Privacy's.
The migration fails closed (rollback) on any mismatch; a v4 database is refused by the v3 tooling.

    schema v4 installed != a correction admitted
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
from . import relationship_origin_migration as ROM
from . import slice15b2a_migration as S

CORRECTION_SCHEMA_VERSION = 4
FROM_VERSION = ROM.RELATIONSHIP_ORIGIN_SCHEMA_VERSION            # 3
FAULT_POINTS = ("after_rebuild", "before_ledger", "before_commit")

_V3_OBJECTS = {ledger: objects[FROM_VERSION] for ledger, _table, _ddl, objects in ROM._LEDGERS}
# ledger -> [(table, v3 DDL, v4 DDL)]; object names are unchanged from v3, only their SQL widens.
_REBUILDS = {
    "consent_schema_migration": [("consent_grant", A.CONSENT_GRANT_V3_DDL, A.CONSENT_GRANT_V4_DDL)],
    "policy_schema_migration": [("policy_decision", A.POLICY_DECISION_V3_DDL, A.POLICY_DECISION_V4_DDL)],
    "learning_v2_schema_migration": [
        (table, ddl_v3, L.RELATIONSHIP_ORIGIN_V4_TABLE_DDL[table])
        for table in ("learning_ro_intent_v1", "learning_ro_candidate_v1", "learning_ro_proposal_v1")
        for ddl_v3 in [s for s in L.RELATIONSHIP_ORIGIN_MIGRATION_STATEMENTS if s.startswith(f"CREATE TABLE {table} (")]
    ],
}


class RelationshipOriginCorrectionMigrationError(RuntimeError):
    pass


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def _norm(sql: str) -> str:
    return " ".join(str(sql).split())


def _table_sql(conn: sqlite3.Connection, table: str) -> str:
    row = conn.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name=?", (table,)).fetchone()
    return _norm(row[0]) if row else ""


def _state(conn: sqlite3.Connection) -> int:
    """3 or 4 when every ledger agrees, matches its object set, and each rebuilt table has exactly that version's DDL;
    otherwise refuse."""
    states = set()
    for ledger, objects in _V3_OBJECTS.items():
        latest = FIM._latest(conn, ledger)
        if latest is None or latest[0] not in (FROM_VERSION, CORRECTION_SCHEMA_VERSION) \
                or latest[1] != FIM._fingerprint(conn, objects):
            raise RelationshipOriginCorrectionMigrationError(f"{ledger} is at an unknown version or fingerprint")
        version = latest[0]
        for table, ddl_v3, ddl_v4 in _REBUILDS[ledger]:
            if _table_sql(conn, table) != _norm(ddl_v3 if version == FROM_VERSION else ddl_v4):
                raise RelationshipOriginCorrectionMigrationError(f"{table} is not the exact v{version} table")
        states.add(version)
    if len(states) != 1:
        raise RelationshipOriginCorrectionMigrationError("owner ledgers are at mixed schema versions")
    return states.pop()


def migrate(
    path: Path,
    *,
    backup_manifest: governed_backup.BackupManifest,
    applied_at: Optional[str] = None,
    fault_hook: Optional[Callable[[str], None]] = None,
) -> Dict[str, str]:
    """Move the three owner ledgers from schema v3 to v4. Idempotent on a v4 database; fails closed otherwise."""
    target = Path(path).resolve()
    governed_backup.verify_backup(target, backup_manifest, expected_role="cognitive")
    conn = sqlite3.connect(str(target), timeout=5.0)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA foreign_keys=OFF")              # as v3: keep every REFERENCES naming the rebuilt tables
        conn.execute("PRAGMA legacy_alter_table=ON")
        conn.execute("PRAGMA secure_delete=ON")
        conn.execute("PRAGMA busy_timeout=5000")
        conn.execute("BEGIN IMMEDIATE")
        try:
            canonical_migration._verify_current_schema(conn)
        except Exception as exc:
            raise RelationshipOriginCorrectionMigrationError("canonical runtime schema v2 is required") from exc
        current = _state(conn)
        if current == CORRECTION_SCHEMA_VERSION:
            if conn.execute("PRAGMA foreign_key_check").fetchall():
                raise RelationshipOriginCorrectionMigrationError("foreign-key check failed")
            conn.rollback()
            return {ledger: FIM._fingerprint(conn, objects) or "" for ledger, objects in _V3_OBJECTS.items()}
        rebuilt = [table for entries in _REBUILDS.values() for table, _v3, _v4 in entries]
        counts = FIM._counts(conn)
        rows = {table: FIM._rows_digest(conn, table) for table in rebuilt}
        others = FIM._other_objects(conn, rebuilt)
        dependents = {table: sorted(_norm(r[0]) for r in conn.execute(
            "SELECT sql FROM sqlite_master WHERE tbl_name=? AND type IN ('index','trigger') AND sql IS NOT NULL",
            (table,))) for table in rebuilt}
        for entries in _REBUILDS.values():
            for table, _v3, ddl_v4 in entries:
                FIM._rebuild(conn, table, ddl_v4)
        if fault_hook:
            fault_hook("after_rebuild")
        if {table: FIM._rows_digest(conn, table) for table in rebuilt} != rows:
            raise RelationshipOriginCorrectionMigrationError("rebuilt table rows changed")
        if FIM._counts(conn) != counts:
            raise RelationshipOriginCorrectionMigrationError("table counts changed")
        if FIM._other_objects(conn, rebuilt) != others:
            raise RelationshipOriginCorrectionMigrationError("an unrelated schema object changed")
        for table in rebuilt:
            now = sorted(_norm(r[0]) for r in conn.execute(
                "SELECT sql FROM sqlite_master WHERE tbl_name=? AND type IN ('index','trigger') AND sql IS NOT NULL",
                (table,)))
            if now != dependents[table]:
                raise RelationshipOriginCorrectionMigrationError(f"{table} indexes or triggers changed")
        if conn.execute("PRAGMA foreign_key_check").fetchall():
            raise RelationshipOriginCorrectionMigrationError("foreign-key check failed")
        if str(conn.execute("PRAGMA integrity_check").fetchone()[0]) != "ok":
            raise RelationshipOriginCorrectionMigrationError("integrity check failed")
        if fault_hook:
            fault_hook("before_ledger")
        timestamp = applied_at or _now()
        fingerprints: Dict[str, str] = {}
        for ledger, objects in _V3_OBJECTS.items():
            fingerprints[ledger] = S.schema_fingerprint(conn, objects)
            conn.execute(
                f'INSERT INTO "{ledger}"(version,schema_fingerprint,applied_at) VALUES (?,?,?)',
                (CORRECTION_SCHEMA_VERSION, fingerprints[ledger], timestamp),
            )
        if _state(conn) != CORRECTION_SCHEMA_VERSION:
            raise RelationshipOriginCorrectionMigrationError("schema v4 did not verify")
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
    """Read-only: 3 or 4 when the owner ledgers verify exactly, else RelationshipOriginCorrectionMigrationError."""
    conn = sqlite3.connect(f"file:{Path(path).resolve().as_posix()}?mode=ro", uri=True)
    try:
        return _state(conn)
    finally:
        conn.close()
