"""F9-C governed Privacy Governance schema v2: the Hermes DEV conversation erasure owner and its required-owner floor.

Offline, backup-gated tool (never imported by the serving store). Privacy Governance stays the only FORGET authority; this
only lets an authorization name the peer owner HERMES_DEV_CONVERSATION, and only where a governed floor requires it.

upgrade_privacy_v1_to_v2 runs in ONE exclusive transaction on a Slice 15B2a v1 database (so a crash leaves v1 intact):
* privacy_erasure_authorization_owner is rebuilt with HERMES_DEV_CONVERSATION added to its CHECK list (SQLite cannot
  alter a CHECK); every row, including owners of in-flight authorizations, is copied byte-for-byte and verified;
* privacy_required_owner_floor is created; the serving store may read it but never write it;
* ledger version 2 with the v2 schema fingerprint; every pre-existing table's content digest is verified unchanged.
It is idempotent: an already-v2 database with the expected fingerprint is accepted unchanged.

provision_hermes_owner_floor adds the single permitted floor row (First Interaction identity scope, HERMES owner,
DEV_SYNTHETIC only) together with two enforcement triggers, in one transaction. The triggers hold the scope as literals
and read only v1 tables, so they bind every Privacy code version, including a rolled-back release that knows nothing
about the floor (the b9eb32c store's SQLite authorizer would deny a read of the floor table itself):
* a First Interaction authorization cannot be created without a HERMES_DEV_CONVERSATION owner row;
* a First Interaction hold cannot be released unless the receipt being written records HERMES COMPLETE.
Provisioning refuses while a First Interaction authorization without HERMES is in flight (it could never complete).
retire_hermes_owner_floor removes the row and both triggers together (governed rollback of the Hermes owner);
authorizations already issued keep the owners they were issued with.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path
from typing import Dict, Optional, Tuple

try:
    from . import memory_action_v2 as MA
    from . import privacy_governance as P
    from . import slice15b2a_migration as M15
except ImportError:  # deploy-exact flat-directory tests
    import memory_action_v2 as MA
    import privacy_governance as P
    import slice15b2a_migration as M15

MigrationError = M15.MigrationError

OWNER_TABLE = "privacy_erasure_authorization_owner"
OWNER_TABLE_RETIRED = "privacy_erasure_authorization_owner_v1_retired"
OWNER_TRIGGER = "privacy_erasure_authorization_owner_no_update"
FLOOR_TABLE = P.REQUIRED_OWNER_FLOOR_TABLE
FLOOR_TRIGGER = "privacy_required_owner_floor_no_update"
DEV_SYNTHETIC = "DEV_SYNTHETIC"
FLOOR_SCOPE = MA.FIRST_INTERACTION_IDENTITY[:2]      # (memory_class, subject_namespace) of the First Interaction


def _v1_statement(marker: str) -> str:
    found = [s for s in P.PRIVACY_MIGRATION_STATEMENTS if marker in s]
    if len(found) != 1:
        raise MigrationError(f"v1 schema statement not found exactly once: {marker}")
    return found[0]


_V1_OWNER_SQL = _v1_statement(f"CREATE TABLE IF NOT EXISTS {OWNER_TABLE} (")
_V1_OWNER_LIST = "'LEGACY_MEMORY','LEGACY_SKILLS','PENDING'"
if _V1_OWNER_SQL.count(_V1_OWNER_LIST) != 1:
    raise MigrationError("v1 owner CHECK list has an unexpected shape")
V2_OWNER_SQL = _V1_OWNER_SQL.replace(_V1_OWNER_LIST, _V1_OWNER_LIST + f",'{P.HERMES_DEV_CONVERSATION}'")
OWNER_TRIGGER_SQL = _v1_statement(f"TRIGGER IF NOT EXISTS {OWNER_TRIGGER}")
FLOOR_SQL = f"""
    CREATE TABLE IF NOT EXISTS {FLOOR_TABLE} (
        memory_class TEXT NOT NULL,
        subject_namespace TEXT NOT NULL,
        resource_owner TEXT NOT NULL CHECK(resource_owner='{P.HERMES_DEV_CONVERSATION}'),
        deployment_environment TEXT NOT NULL CHECK(deployment_environment='{DEV_SYNTHETIC}'),
        provisioned_at TEXT NOT NULL,
        PRIMARY KEY(memory_class, subject_namespace, resource_owner)
    )
    """
FLOOR_TRIGGER_SQL = (f"""CREATE TRIGGER IF NOT EXISTS {FLOOR_TRIGGER}
        BEFORE UPDATE ON {FLOOR_TABLE} BEGIN SELECT RAISE(ABORT,'required owner floor is immutable'); END""")
V2_SCHEMA_OBJECTS = P.PRIVACY_SCHEMA_OBJECTS | frozenset({FLOOR_TABLE, FLOOR_TRIGGER})
V2_TABLES = P.PRIVACY_TABLES | frozenset({FLOOR_TABLE})

_FI_SCOPE_SQL = "memory_class='%s' AND {a}subject_namespace='%s'" % FLOOR_SCOPE
FLOOR_ENFORCEMENT_SQL = {
    # Within begin_forget the authorization row is inserted, then its owner rows, then the suppression row; the
    # authorization with the largest rowid is therefore the one being created (single writer, BEGIN IMMEDIATE).
    P.FLOOR_ENFORCEMENT_TRIGGERS[0]: f"""CREATE TRIGGER {P.FLOOR_ENFORCEMENT_TRIGGERS[0]}
        BEFORE INSERT ON privacy_restore_suppression_manifest
        WHEN EXISTS (SELECT 1 FROM privacy_erasure_authorization a
            WHERE a.rowid=(SELECT MAX(rowid) FROM privacy_erasure_authorization)
            AND a.{_FI_SCOPE_SQL.format(a='a.')}
            AND NOT EXISTS (SELECT 1 FROM privacy_erasure_authorization_owner o
                WHERE o.authorization_ref_id=a.authorization_ref_id
                AND o.resource_owner='{P.HERMES_DEV_CONVERSATION}'))
        BEGIN SELECT RAISE(ABORT,'required erasure owner {P.HERMES_DEV_CONVERSATION} is missing'); END""",
    # Holds are deleted only by complete(), after it inserts the receipt for the same authorization; receipts are
    # immutable and never deleted, so the receipt with the largest rowid is the one being written.
    P.FLOOR_ENFORCEMENT_TRIGGERS[1]: f"""CREATE TRIGGER {P.FLOOR_ENFORCEMENT_TRIGGERS[1]}
        BEFORE DELETE ON privacy_hold
        WHEN OLD.{_FI_SCOPE_SQL.format(a='OLD.')}
        AND NOT EXISTS (SELECT 1 FROM privacy_completion_owner_result r
            WHERE r.receipt_id=(SELECT receipt_id FROM privacy_completion_receipt ORDER BY rowid DESC LIMIT 1)
            AND r.resource_owner='{P.HERMES_DEV_CONVERSATION}' AND r.status='COMPLETE')
        BEGIN SELECT RAISE(ABORT,'First Interaction FORGET cannot complete without {P.HERMES_DEV_CONVERSATION}'); END""",
}


def _content_digests(conn: sqlite3.Connection, tables) -> Dict[str, str]:
    """Order-independent digest of every row of each table (column order as declared)."""
    out = {}
    for table in sorted(tables):
        columns = [str(row[1]) for row in conn.execute(f'PRAGMA table_info("{table}")')]
        rows = conn.execute(f'SELECT * FROM "{table}" ORDER BY ' + ",".join(f'"{c}"' for c in columns)).fetchall()
        payload = json.dumps([list(map(lambda v: v if not isinstance(v, bytes) else v.hex(), r)) for r in rows],
                             separators=(",", ":"), ensure_ascii=True)
        out[table] = hashlib.sha256(payload.encode("ascii")).hexdigest()
    return out


def _ledger(conn: sqlite3.Connection) -> Dict[int, str]:
    return {int(row[0]): str(row[1]) for row in
            conn.execute("SELECT version,schema_fingerprint FROM privacy_schema_migration ORDER BY version")}


def _tables(conn: sqlite3.Connection) -> set:
    return {str(row[0]) for row in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")}


def _verify_db(conn: sqlite3.Connection) -> None:
    if conn.execute("PRAGMA foreign_key_check").fetchall():
        raise MigrationError("privacy foreign-key check failed")
    if str(conn.execute("PRAGMA integrity_check").fetchone()[0]) != "ok":
        raise MigrationError("privacy integrity check failed")


def upgrade_privacy_v1_to_v2(path: Path, *, applied_at: Optional[str] = None) -> Tuple[str, str]:
    """Upgrade an existing Slice 15B2a v1 Privacy database to v2. Returns (v2 fingerprint, complete fingerprint)."""
    target = Path(path)
    if not target.is_file():
        raise MigrationError("privacy governance database is unavailable")
    conn = M15._connect(target)
    try:
        conn.execute("BEGIN EXCLUSIVE")
        ledger = _ledger(conn)
        if max(ledger, default=0) == P.PRIVACY_SCHEMA_V2:
            if set(ledger) != {P.PRIVACY_SCHEMA_V1, P.PRIVACY_SCHEMA_V2} or _tables(conn) != set(V2_TABLES) \
                    or M15.schema_fingerprint(conn, V2_SCHEMA_OBJECTS) != ledger[P.PRIVACY_SCHEMA_V2]:
                raise MigrationError("privacy schema v2 does not match its recorded fingerprint")
            _verify_db(conn)
            complete = M15.complete_schema_fingerprint(conn)
            conn.rollback()
            return ledger[P.PRIVACY_SCHEMA_V2], complete
        if set(ledger) != {P.PRIVACY_SCHEMA_V1}:
            raise MigrationError("privacy schema version is not an upgradeable v1")
        if _tables(conn) != set(P.PRIVACY_TABLES):
            raise MigrationError("privacy database table set is not the v1 set")
        if M15.schema_fingerprint(conn, P.PRIVACY_SCHEMA_OBJECTS) != ledger[P.PRIVACY_SCHEMA_V1]:
            raise MigrationError("privacy schema v1 does not match its recorded fingerprint")
        _verify_db(conn)
        owners = {str(row[0]) for row in conn.execute(f"SELECT DISTINCT resource_owner FROM {OWNER_TABLE}")}
        if not owners.issubset(P.OWNER_SET_V1):
            raise MigrationError("v1 owner table holds an unknown owner")
        before = _content_digests(conn, P.PRIVACY_TABLES)
        conn.execute(f'DROP TRIGGER "{OWNER_TRIGGER}"')
        conn.execute(f'ALTER TABLE "{OWNER_TABLE}" RENAME TO "{OWNER_TABLE_RETIRED}"')
        conn.execute(V2_OWNER_SQL)
        conn.execute(f'INSERT INTO "{OWNER_TABLE}" (authorization_ref_id,resource_owner) '
                     f'SELECT authorization_ref_id,resource_owner FROM "{OWNER_TABLE_RETIRED}"')
        conn.execute(f'DROP TABLE "{OWNER_TABLE_RETIRED}"')
        conn.execute(OWNER_TRIGGER_SQL)
        conn.execute(FLOOR_SQL)
        conn.execute(FLOOR_TRIGGER_SQL)
        after = _content_digests(conn, P.PRIVACY_TABLES)
        if after != before:
            changed = sorted(t for t in before if before[t] != after.get(t))
            raise MigrationError(f"privacy data changed during the upgrade: {changed}")
        fingerprint = M15.schema_fingerprint(conn, V2_SCHEMA_OBJECTS)
        conn.execute("INSERT INTO privacy_schema_migration VALUES (?,?,?)",
                     (P.PRIVACY_SCHEMA_V2, fingerprint, applied_at or M15.utc_now()))
        _verify_db(conn)
        complete = M15.complete_schema_fingerprint(conn)
        conn.commit()
    except Exception:
        if conn.in_transaction:
            conn.rollback()
        raise
    finally:
        conn.close()
    return fingerprint, complete


def _require_v2(conn: sqlite3.Connection) -> None:
    ledger = _ledger(conn)
    if max(ledger, default=0) != P.PRIVACY_SCHEMA_V2 \
            or M15.schema_fingerprint(conn, V2_SCHEMA_OBJECTS) != ledger[P.PRIVACY_SCHEMA_V2]:
        raise MigrationError("privacy schema v2 is required")


def _enforcement_state(conn: sqlite3.Connection) -> Dict[str, Optional[str]]:
    rows = {str(r[0]): str(r[1]) for r in conn.execute(
        "SELECT name,sql FROM sqlite_master WHERE type='trigger' AND name IN (%s)"
        % ",".join("?" for _ in P.FLOOR_ENFORCEMENT_TRIGGERS), P.FLOOR_ENFORCEMENT_TRIGGERS)}
    return {name: rows.get(name) for name in P.FLOOR_ENFORCEMENT_TRIGGERS}


def _floor_row_present(conn: sqlite3.Connection) -> bool:
    return conn.execute(f"SELECT 1 FROM {FLOOR_TABLE} WHERE memory_class=? AND subject_namespace=? "
                        "AND resource_owner=?", (*FLOOR_SCOPE, P.HERMES_DEV_CONVERSATION)).fetchone() is not None


def _enforcement_exact(conn: sqlite3.Connection) -> bool:
    return all(sql is not None and M15._normal_sql(sql) == M15._normal_sql(FLOOR_ENFORCEMENT_SQL[name])
               for name, sql in _enforcement_state(conn).items())


def provision_hermes_owner_floor(path: Path, *, deployment_environment: str,
                                 applied_at: Optional[str] = None) -> bool:
    """Require HERMES_DEV_CONVERSATION for First Interaction FORGETs. DEV_SYNTHETIC only. Returns True if added."""
    if deployment_environment != DEV_SYNTHETIC:
        raise MigrationError("the Hermes erasure owner floor is DEV_SYNTHETIC only")
    conn = M15._connect(Path(path))
    try:
        conn.execute("BEGIN EXCLUSIVE")
        _require_v2(conn)
        present, triggers = _floor_row_present(conn), _enforcement_state(conn)
        if present or any(triggers.values()):
            if present and _enforcement_exact(conn):
                conn.rollback()
                return False                                                  # already provisioned exactly
            raise MigrationError("the Hermes owner floor is partially provisioned or altered")
        blocking = conn.execute(
            "SELECT COUNT(*) FROM privacy_erasure_authorization a WHERE a.memory_class=? AND a.subject_namespace=? "
            "AND NOT EXISTS (SELECT 1 FROM privacy_erasure_authorization_owner o "
            "WHERE o.authorization_ref_id=a.authorization_ref_id AND o.resource_owner=?)",
            (*FLOOR_SCOPE, P.HERMES_DEV_CONVERSATION)).fetchone()[0]
        if int(blocking):
            raise MigrationError("a First Interaction FORGET without the Hermes owner is in flight; complete it first")
        conn.execute(f"INSERT INTO {FLOOR_TABLE} VALUES (?,?,?,?,?)",
                     (*FLOOR_SCOPE, P.HERMES_DEV_CONVERSATION, DEV_SYNTHETIC, applied_at or M15.utc_now()))
        for name in P.FLOOR_ENFORCEMENT_TRIGGERS:
            conn.execute(FLOOR_ENFORCEMENT_SQL[name])
        if not _enforcement_exact(conn):
            raise MigrationError("Hermes owner floor enforcement did not install exactly")
        _verify_db(conn)
        conn.commit()
        return True
    except Exception:
        if conn.in_transaction:
            conn.rollback()
        raise
    finally:
        conn.close()


def retire_hermes_owner_floor(path: Path) -> bool:
    """Governed rollback of the Hermes owner floor. Returns True if a row was removed."""
    conn = M15._connect(Path(path))
    try:
        conn.execute("BEGIN EXCLUSIVE")
        _require_v2(conn)
        cursor = conn.execute(
            f"DELETE FROM {FLOOR_TABLE} WHERE memory_class=? AND subject_namespace=? AND resource_owner=?",
            (*FLOOR_SCOPE, P.HERMES_DEV_CONVERSATION))
        for name in P.FLOOR_ENFORCEMENT_TRIGGERS:
            conn.execute(f'DROP TRIGGER IF EXISTS "{name}"')
        conn.commit()
        return cursor.rowcount == 1
    except Exception:
        if conn.in_transaction:
            conn.rollback()
        raise
    finally:
        conn.close()
