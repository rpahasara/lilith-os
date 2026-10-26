#!/usr/bin/env python3
"""Relationship origin: the reviewed L04 owner-ledger schema v3 migration for the First Memory DEV database.

`lilith_memory.relationship_origin_migration.migrate` moves the consent, policy and learning ledgers to v3 (from v1, as
DEV is today, or v2) in one backup-gated transaction. This tool is its one operator path, as
`first_memory_l04_migration.py` is for the admission link:

    plan  <cognitive-db>                 read-only: the canonical runtime schema, the reviewed admission-link table,
                                         the owner-ledger schema version, and the canonical rows that must survive
    apply <cognitive-db> <backup-dir>    a verified online backup first (`backup.create_backup`, role cognitive),
                                         then exactly the v3 migration, then re-verified: every admission, revision,
                                         item and link exactly as before (row digests), schema v3, integrity ok

Run as the L04 owner (`lilith`), on the stopped-writer DB the owner names. It adds tables and rebuilds three CHECKs; it
writes no memory, no registry entry, no capability and nothing in Privacy. An already-migrated v3 database is
reported, never touched.

    schema v3 installed != relationship-origin creation enabled
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
for _path in (ROOT / "services/core-api", ROOT / "services/owner-memory-control", HERE):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

import first_memory_l04_migration as LINK  # noqa: E402
from lilith_memory import backup  # noqa: E402
from lilith_memory import relationship_origin_migration as ROM  # noqa: E402

# The canonical rows the migration must leave exactly as they are (the admitted First Memory and its chain).
PRESERVED_TABLES = ("memory_item", "memory_revision", "memory_admission", "memory_active_revision",
                    "memory_apply_audit", LINK.AD.LINK_TABLE, "consent_grant", "policy_decision",
                    "learning_proposal_ref")
V3 = ROM.RELATIONSHIP_ORIGIN_SCHEMA_VERSION


class Refused(Exception):
    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


def _digests(path: Path) -> dict[str, list]:
    conn = LINK._read_only(Path(path))
    try:
        out = {}
        for table in PRESERVED_TABLES:
            columns = [str(row[1]) for row in conn.execute(f'PRAGMA table_info("{table}")')]
            rows = conn.execute(f'SELECT * FROM "{table}" ORDER BY ' + ",".join(f'"{c}"' for c in columns)).fetchall()
            payload = json.dumps([columns, [list(r) for r in rows]], separators=(",", ":"), default=str)
            out[table] = [len(rows), hashlib.sha256(payload.encode("utf-8")).hexdigest()]
        return out
    finally:
        conn.close()


def plan(path: Path) -> dict[str, Any]:
    path = Path(path)
    try:
        link = LINK.plan(path)                         # canonical runtime schema, integrity, the reviewed link DDL
    except LINK.Refused as exc:
        raise Refused(exc.reason) from exc
    if link["state"] != LINK.LINK_INSTALLED:
        raise Refused("ADMISSION_LINK_TABLE_ABSENT")
    try:
        version = ROM.schema_state(path)
    except ROM.RelationshipOriginMigrationError as exc:
        raise Refused("OWNER_LEDGERS_UNKNOWN") from exc
    return {"schemaVersion": version, "preserved": _digests(path), "mutation": "NONE"}


def apply(path: Path, backup_dir: Path, *, now: datetime | None = None) -> dict[str, Any]:
    path, backup_dir = Path(path), Path(backup_dir)
    before = plan(path)
    if before["schemaVersion"] == V3:
        return {**before, "mutation": "NONE_ALREADY_V3"}
    stamp = (now or datetime.now(timezone.utc)).strftime("%Y%m%dT%H%M%SZ")
    if not backup_dir.is_dir():
        raise Refused("BACKUP_DIR_UNAVAILABLE")
    target = backup_dir / f"{path.name}.pre-relationship-origin-v3.{stamp}.db"
    manifest_path = backup_dir / f"{path.name}.pre-relationship-origin-v3.{stamp}.manifest.json"
    if target.exists() or manifest_path.exists():
        raise Refused("BACKUP_COLLISION")
    manifest = backup.create_backup(path, target, manifest_path, role="cognitive")
    fingerprints = ROM.migrate(path, backup_manifest=manifest)
    after = plan(path)
    if after["schemaVersion"] != V3:
        raise Refused("SCHEMA_V3_NOT_VERIFIED")
    changed = sorted(t for t in PRESERVED_TABLES if after["preserved"][t] != before["preserved"][t])
    if changed:                                         # the rebuilt ledgers too: every row byte-for-byte
        raise Refused("CANONICAL_ROWS_CHANGED:" + ",".join(changed))
    return {"schemaVersion": V3, "mutation": "SCHEMA_V3_APPLIED", "fingerprints": fingerprints,
            "fromVersion": before["schemaVersion"], "preserved": after["preserved"], "backup": str(target),
            "backupManifest": str(manifest_path), "backupSha256": manifest.backup_sha256}


def main(argv: list[str]) -> int:
    try:
        if argv[:1] == ["plan"] and len(argv) == 2:
            out = plan(Path(argv[1]))
        elif argv[:1] == ["apply"] and len(argv) == 3:
            out = apply(Path(argv[1]), Path(argv[2]))
        else:
            raise Refused("USAGE")
    except Refused as exc:
        print(f"relationship-origin-l04-migration: REFUSED {exc.reason}", file=sys.stderr)
        return 2
    except (OSError, sqlite3.Error, backup.BackupError, ROM.RelationshipOriginMigrationError) as exc:
        print(f"relationship-origin-l04-migration: REFUSED {type(exc).__name__}", file=sys.stderr)
        return 2
    sys.stdout.write(json.dumps(out, sort_keys=True, separators=(",", ":")) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
