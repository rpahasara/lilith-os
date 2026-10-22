"""Explicit, backup-gated schema v2 for the FM-02 First Interaction family.

Nothing here runs at import time, and no runtime path calls ``migrate``. It moves
three owner ledgers from version 1 to version 2 in ONE transaction:

- ``consent_schema_migration``: ``consent_grant`` is rebuilt so its purpose CHECK
  admits the First Interaction purpose, paired with the exact CREATE-only tuple;
- ``policy_schema_migration``: ``policy_decision`` is rebuilt the same way, pairing
  each capability with its own purpose;
- ``learning_v2_schema_migration``: ``learning_proposal_ref`` is rebuilt so its
  family CHECK admits ``OWNER_DIRECTED_FIRST_INTERACTION_V1`` (L04 rows reference it,
  so it cannot be duplicated), and the five First Interaction L18 tables are added.

Every other object keeps its exact SQL. Rebuilt tables keep every row byte-for-byte
(verified by digest), indexes and triggers are re-created from their exact prior
SQL, and the migration fails closed (rollback) on any mismatch. The v1
``migrate_cognitive`` and the canonical runtime migration are unchanged; on a v2
database ``migrate_cognitive`` refuses, by design.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Dict, Iterable, Optional, Tuple

from . import backup as governed_backup
from . import canonical_authority as A
from . import canonical_migration
from . import learning_v2 as L
from . import slice15b2a_migration as S


FIRST_INTERACTION_SCHEMA_VERSION = 2
FAULT_POINTS = ("after_rebuild", "after_first_interaction_tables", "before_ledger", "before_commit")

_V1_OBJECTS = dict(S.OWNER_SCHEMAS)
# ledger -> (rebuilt table, its v2 DDL, v1 object set, v2 object set)
_LEDGERS = (
    ("consent_schema_migration", "consent_grant", A.CONSENT_GRANT_V2_DDL,
     _V1_OBJECTS["consent_schema_migration"], _V1_OBJECTS["consent_schema_migration"]),
    ("policy_schema_migration", "policy_decision", A.POLICY_DECISION_V2_DDL,
     _V1_OBJECTS["policy_schema_migration"], _V1_OBJECTS["policy_schema_migration"]),
    ("learning_v2_schema_migration", "learning_proposal_ref", L.LEARNING_PROPOSAL_REF_V2_DDL,
     L.LEARNING_V2_SCHEMA_OBJECTS, L.LEARNING_V2_SCHEMA_OBJECTS_V2),
)
_RETIRED_SUFFIX = "__fm02_v1_retired"


class FirstInteractionMigrationError(RuntimeError):
    pass


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def _latest(conn: sqlite3.Connection, ledger: str) -> Optional[Tuple[int, str]]:
    row = conn.execute(
        f'SELECT version,schema_fingerprint FROM "{ledger}" ORDER BY version DESC LIMIT 1'
    ).fetchone()
    return None if row is None else (int(row[0]), str(row[1]))


def _state(conn: sqlite3.Connection) -> str:
    """V1 or V2 when every ledger agrees and matches its object set exactly; otherwise refuse."""
    states = set()
    for ledger, _table, _ddl, v1_objects, v2_objects in _LEDGERS:
        latest = _latest(conn, ledger)
        if latest == (S.SCHEMA_VERSION, _fingerprint(conn, v1_objects)):
            states.add("V1")
        elif latest == (FIRST_INTERACTION_SCHEMA_VERSION, _fingerprint(conn, v2_objects)):
            states.add("V2")
        else:
            raise FirstInteractionMigrationError(f"{ledger} is at an unknown version or fingerprint")
    if len(states) != 1:
        raise FirstInteractionMigrationError("owner ledgers are at mixed schema versions")
    return states.pop()


def _fingerprint(conn: sqlite3.Connection, objects: Iterable[str]) -> Optional[str]:
    try:
        return S.schema_fingerprint(conn, objects)
    except S.MigrationError:
        return None


def _rows_digest(conn: sqlite3.Connection, table: str) -> Tuple[int, str]:
    columns = [str(row[1]) for row in conn.execute(f'PRAGMA table_info("{table}")')]
    rows = conn.execute(
        f'SELECT {",".join(columns)} FROM "{table}" ORDER BY {columns[0]}'
    ).fetchall()
    payload = json.dumps([columns, [list(row) for row in rows]], separators=(",", ":"))
    return len(rows), hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _other_objects(conn: sqlite3.Connection, rebuilt: Iterable[str]) -> Dict[str, str]:
    skip = set(rebuilt)
    return {
        f"{row[0]}:{row[1]}": " ".join(str(row[3]).split())
        for row in conn.execute("SELECT type,name,tbl_name,sql FROM sqlite_master WHERE sql IS NOT NULL")
        if str(row[2]) not in skip
    }


def _counts(conn: sqlite3.Connection) -> Dict[str, int]:
    return S.table_counts(conn)


def _rebuild(conn: sqlite3.Connection, table: str, ddl: str) -> None:
    dependents = [
        str(row[0])
        for row in conn.execute(
            "SELECT sql FROM sqlite_master WHERE tbl_name=? AND type IN ('index','trigger') "
            "AND sql IS NOT NULL ORDER BY type,name",
            (table,),
        )
    ]
    before = [str(row[1]) for row in conn.execute(f'PRAGMA table_info("{table}")')]
    retired = table + _RETIRED_SUFFIX
    conn.execute(f'ALTER TABLE "{table}" RENAME TO "{retired}"')
    conn.execute(ddl)
    after = [str(row[1]) for row in conn.execute(f'PRAGMA table_info("{table}")')]
    if after != before:
        raise FirstInteractionMigrationError(f"{table} column layout changed")
    conn.execute(f'INSERT INTO "{table}" ({",".join(after)}) SELECT {",".join(after)} FROM "{retired}"')
    conn.execute(f'DROP TABLE "{retired}"')
    for sql in dependents:
        conn.execute(sql)


def migrate(
    path: Path,
    *,
    backup_manifest: governed_backup.BackupManifest,
    applied_at: Optional[str] = None,
    fault_hook: Optional[Callable[[str], None]] = None,
) -> Dict[str, str]:
    """Move the three owner ledgers to schema v2. Idempotent on a v2 database; fails closed otherwise."""
    target = Path(path).resolve()
    governed_backup.verify_backup(target, backup_manifest, expected_role="cognitive")
    conn = sqlite3.connect(str(target), timeout=5.0)
    conn.row_factory = sqlite3.Row
    try:
        # Both pragmas must be set outside a transaction. foreign_keys=OFF and legacy_alter_table=ON keep every
        # REFERENCES clause naming the rebuilt tables exactly as written while a table is renamed and replaced.
        conn.execute("PRAGMA foreign_keys=OFF")
        conn.execute("PRAGMA legacy_alter_table=ON")
        # Freed pages of the retired tables are overwritten (they hold ids and digests only, never memory content).
        conn.execute("PRAGMA secure_delete=ON")
        conn.execute("PRAGMA busy_timeout=5000")
        conn.execute("BEGIN IMMEDIATE")
        try:
            canonical_migration._verify_current_schema(conn)
        except Exception as exc:
            raise FirstInteractionMigrationError("canonical runtime schema v2 is required") from exc
        if _state(conn) == "V2":
            if conn.execute("PRAGMA foreign_key_check").fetchall():
                raise FirstInteractionMigrationError("foreign-key check failed")
            conn.rollback()
            return {ledger: _fingerprint(conn, v2) or "" for ledger, _t, _d, _v1, v2 in _LEDGERS}
        rebuilt = [table for _ledger, table, _ddl, _v1, _v2 in _LEDGERS]
        counts = _counts(conn)
        rows = {table: _rows_digest(conn, table) for table in rebuilt}
        others = _other_objects(conn, rebuilt)
        for _ledger, table, ddl, _v1, _v2 in _LEDGERS:
            _rebuild(conn, table, ddl)
        if fault_hook:
            fault_hook("after_rebuild")
        for statement in L.FIRST_INTERACTION_MIGRATION_STATEMENTS:
            conn.execute(statement)
        if fault_hook:
            fault_hook("after_first_interaction_tables")
        if {table: _rows_digest(conn, table) for table in rebuilt} != rows:
            raise FirstInteractionMigrationError("rebuilt table rows changed")
        after = _counts(conn)
        if {t: n for t, n in after.items() if t not in L.FIRST_INTERACTION_TABLES} != counts:
            raise FirstInteractionMigrationError("pre-existing table counts changed")
        if any(after.get(table) != 0 for table in L.FIRST_INTERACTION_TABLES):
            raise FirstInteractionMigrationError("new First Interaction tables are not empty")
        current = _other_objects(conn, rebuilt)
        added = {key for key in current if key.split(":", 1)[1] in L.FIRST_INTERACTION_SCHEMA_OBJECTS}
        if {k: v for k, v in current.items() if k not in added} != others:
            raise FirstInteractionMigrationError("an unrelated schema object changed")
        if conn.execute("PRAGMA foreign_key_check").fetchall():
            raise FirstInteractionMigrationError("foreign-key check failed")
        if str(conn.execute("PRAGMA integrity_check").fetchone()[0]) != "ok":
            raise FirstInteractionMigrationError("integrity check failed")
        if fault_hook:
            fault_hook("before_ledger")
        timestamp = applied_at or _now()
        fingerprints: Dict[str, str] = {}
        for ledger, _table, _ddl, _v1, v2_objects in _LEDGERS:
            fingerprints[ledger] = S.schema_fingerprint(conn, v2_objects)
            conn.execute(
                f'INSERT INTO "{ledger}"(version,schema_fingerprint,applied_at) VALUES (?,?,?)',
                (FIRST_INTERACTION_SCHEMA_VERSION, fingerprints[ledger], timestamp),
            )
        if _state(conn) != "V2":
            raise FirstInteractionMigrationError("schema v2 did not verify")
        if fault_hook:
            fault_hook("before_commit")
        conn.commit()
        return fingerprints
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def schema_state(path: Path) -> str:
    """Read-only: "V1" or "V2" when the owner ledgers verify exactly, else FirstInteractionMigrationError."""
    conn = sqlite3.connect(f"file:{Path(path).resolve().as_posix()}?mode=ro", uri=True)
    try:
        return _state(conn)
    finally:
        conn.close()
