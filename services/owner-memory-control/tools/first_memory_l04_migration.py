#!/usr/bin/env python3
"""First Memory: the reviewed L04 migration that installs the durable admission-link table (DEV_SYNTHETIC).

The L04 V2 adapter only opens L04 read-only and requires `memory_admission_authority_link` (`l04_v2_adapter.LINK_DDL`,
fresh A1-A7) to exist; until now only TEST fixtures created it. This tool is the one production path:

    plan  <cognitive-db>                 read-only: the L04 schema is canonical-migrated, the link table's state
    apply <cognitive-db> <backup-dir>    a verified online backup first (`backup.create_backup`, role cognitive),
                                         then exactly `LINK_DDL` in one IMMEDIATE transaction, then re-verified

Run as the L04 owner (`lilith`), on the stopped-writer DB the owner names. It adds one empty table and nothing
else: no row, no registry entry, no capability, no Privacy change. An already-installed exact table is reported, never
re-created; any other table of that name refuses.

    link table installed != memory creation enabled
"""

from __future__ import annotations

import json
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
for _path in (ROOT / "services/core-api", ROOT / "services/owner-memory-control"):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

from lilith_memory import backup  # noqa: E402
from lilith_owner_memory import l04_v2_adapter as AD  # noqa: E402

# The 15B2b canonical runtime schema (canonical_migration renames its rebuilt tables to these names).
REQUIRED_L04_TABLES = frozenset({"canonical_runtime_schema_migration", "memory_revision", "memory_admission",
                                 "memory_active_revision", "memory_apply_audit"})
LINK_INSTALLED = "LINK_TABLE_INSTALLED"
LINK_ABSENT = "LINK_TABLE_ABSENT"


class Refused(Exception):
    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


def expected_link_sql() -> str:
    conn = sqlite3.connect(":memory:")
    try:
        conn.execute(AD.LINK_DDL)
        return conn.execute("SELECT sql FROM sqlite_master WHERE name=?", (AD.LINK_TABLE,)).fetchone()[0]
    finally:
        conn.close()


def _read_only(path: Path) -> sqlite3.Connection:
    if not path.is_file() or path.is_symlink():
        raise Refused("COGNITIVE_DB_UNAVAILABLE")
    return sqlite3.connect(f"file:{path.resolve()}?mode=ro", uri=True)


def plan(path: Path) -> dict[str, Any]:
    conn = _read_only(Path(path))
    try:
        tables = {row[0]: row[1] for row in conn.execute("SELECT name, sql FROM sqlite_master WHERE type='table'")}
        integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
    except sqlite3.Error as exc:
        raise Refused("COGNITIVE_DB_UNREADABLE") from exc
    finally:
        conn.close()
    if integrity != "ok":
        raise Refused("COGNITIVE_DB_INTEGRITY")
    missing = sorted(REQUIRED_L04_TABLES - set(tables))
    if missing:
        raise Refused("L04_NOT_CANONICAL_MIGRATED:" + ",".join(missing))
    if AD.LINK_TABLE in tables:
        if tables[AD.LINK_TABLE] != expected_link_sql():
            raise Refused("LINK_TABLE_NOT_THE_REVIEWED_DDL")
        return {"state": LINK_INSTALLED, "linkSql": tables[AD.LINK_TABLE], "mutation": "NONE"}
    return {"state": LINK_ABSENT, "linkSql": expected_link_sql(), "mutation": "NONE"}


def apply(path: Path, backup_dir: Path, *, now: datetime | None = None) -> dict[str, Any]:
    path, backup_dir = Path(path), Path(backup_dir)
    before = plan(path)
    if before["state"] == LINK_INSTALLED:
        return {**before, "mutation": "NONE_ALREADY_INSTALLED"}
    stamp = (now or datetime.now(timezone.utc)).strftime("%Y%m%dT%H%M%SZ")
    if not backup_dir.is_dir():
        raise Refused("BACKUP_DIR_UNAVAILABLE")
    target = backup_dir / f"{path.name}.pre-first-memory-link.{stamp}.db"
    manifest_path = backup_dir / f"{path.name}.pre-first-memory-link.{stamp}.manifest.json"
    if target.exists() or manifest_path.exists():
        raise Refused("BACKUP_COLLISION")
    manifest = backup.create_backup(path, target, manifest_path, role="cognitive")
    conn = sqlite3.connect(str(path), isolation_level=None)
    try:
        conn.execute("BEGIN IMMEDIATE")
        try:
            if conn.execute("SELECT 1 FROM sqlite_master WHERE name=?", (AD.LINK_TABLE,)).fetchone() is not None:
                raise Refused("LINK_TABLE_APPEARED")
            conn.execute(AD.LINK_DDL)
            conn.execute("COMMIT")
        except BaseException:
            conn.execute("ROLLBACK")
            raise
    finally:
        conn.close()
    after = plan(path)
    if after["state"] != LINK_INSTALLED:
        raise Refused("LINK_TABLE_NOT_VERIFIED")
    rows = _read_only(path)
    try:
        count = rows.execute(f"SELECT COUNT(*) FROM {AD.LINK_TABLE}").fetchone()[0]
    finally:
        rows.close()
    return {"state": LINK_INSTALLED, "mutation": "LINK_TABLE_CREATED", "linkRows": count,
            "backup": str(target), "backupManifest": str(manifest_path),
            "backupSha256": manifest.backup_sha256}


def main(argv: list[str]) -> int:
    try:
        if argv[:1] == ["plan"] and len(argv) == 2:
            out = plan(Path(argv[1]))
        elif argv[:1] == ["apply"] and len(argv) == 3:
            out = apply(Path(argv[1]), Path(argv[2]))
        else:
            raise Refused("USAGE")
    except Refused as exc:
        print(f"first-memory-l04-migration: REFUSED {exc.reason}", file=sys.stderr)
        return 2
    except (OSError, sqlite3.Error, backup.BackupError) as exc:
        print(f"first-memory-l04-migration: REFUSED {type(exc).__name__}", file=sys.stderr)
        return 2
    sys.stdout.write(json.dumps(out, sort_keys=True, separators=(",", ":")) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
