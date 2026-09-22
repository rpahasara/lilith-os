"""Explicit, consistent SQLite backup evidence for governed migrations."""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import stat
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Optional, Tuple


MANIFEST_SCHEMA_VERSION = 1


class BackupError(RuntimeError):
    pass


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds").replace(
        "+00:00", "Z"
    )


def _sha256(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def _normal_sql(value: str) -> str:
    return " ".join(str(value).split())


def _schema_fingerprint(conn: sqlite3.Connection) -> str:
    rows = conn.execute(
        "SELECT type,name,sql FROM sqlite_master WHERE sql IS NOT NULL "
        "ORDER BY type,name"
    ).fetchall()
    payload = "\n".join(
        f"{row[0]}:{row[1]}:{_normal_sql(row[2])}" for row in rows
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _counts(conn: sqlite3.Connection) -> Tuple[Tuple[str, int], ...]:
    tables = tuple(
        str(row[0])
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' "
            "AND name NOT LIKE 'sqlite_%' ORDER BY name"
        )
    )
    return tuple(
        (name, int(conn.execute(f'SELECT COUNT(*) FROM "{name}"').fetchone()[0]))
        for name in tables
    )


def _source_identity(path: Path) -> str:
    details = path.stat()
    return hashlib.sha256(
        f"{path.resolve()}:{details.st_dev}:{details.st_ino}".encode("utf-8")
    ).hexdigest()


@dataclass(frozen=True)
class BackupManifest:
    manifest_schema_version: int
    role: str
    source_path: str
    source_identity: str
    source_schema_fingerprint: str
    source_table_counts: Tuple[Tuple[str, int], ...]
    backup_path: str
    backup_sha256: str
    backup_byte_size: int
    backup_mode: int
    backup_uid: Optional[int]
    backup_gid: Optional[int]
    integrity_check: str
    foreign_key_violations: int
    created_at: str
    privacy_precedence_required: bool


def _inspect(path: Path) -> Tuple[str, Tuple[Tuple[str, int], ...], str, int]:
    conn = sqlite3.connect(f"file:{path.resolve()}?mode=ro", uri=True, timeout=5.0)
    try:
        conn.execute("PRAGMA foreign_keys=ON")
        integrity = str(conn.execute("PRAGMA integrity_check").fetchone()[0])
        violations = len(conn.execute("PRAGMA foreign_key_check").fetchall())
        return _schema_fingerprint(conn), _counts(conn), integrity, violations
    finally:
        conn.close()


def create_backup(
    source: Path,
    destination: Path,
    manifest_path: Path,
    *,
    role: str,
) -> BackupManifest:
    """Create one online SQLite backup and a timestamped JSON manifest."""
    if role not in {"cognitive", "privacy"}:
        raise BackupError("backup role is unsupported")
    source_path = Path(source).resolve()
    backup_path = Path(destination).resolve()
    output_manifest = Path(manifest_path).resolve()
    if not source_path.is_file() or source_path in {backup_path, output_manifest}:
        raise BackupError("backup paths are invalid")
    if backup_path.exists() or output_manifest.exists():
        raise BackupError("backup destination must not already exist")
    backup_path.parent.mkdir(parents=True, exist_ok=True)
    output_manifest.parent.mkdir(parents=True, exist_ok=True)
    source_conn = sqlite3.connect(
        f"file:{source_path}?mode=ro", uri=True, timeout=5.0
    )
    destination_conn = sqlite3.connect(str(backup_path), timeout=5.0)
    try:
        source_conn.backup(destination_conn)
    finally:
        destination_conn.close()
        source_conn.close()
    try:
        os.chmod(backup_path, 0o600)
    except OSError as exc:
        raise BackupError("backup permissions could not be restricted") from exc
    source_fp, source_counts, source_integrity, source_fk = _inspect(source_path)
    backup_fp, backup_counts, integrity, violations = _inspect(backup_path)
    if (
        source_integrity != "ok"
        or source_fk
        or integrity != "ok"
        or violations
        or source_fp != backup_fp
        or source_counts != backup_counts
    ):
        raise BackupError("backup verification failed")
    details = backup_path.stat()
    mode = stat.S_IMODE(details.st_mode)
    if os.name != "nt" and mode != 0o600:
        raise BackupError("backup mode is not 0600")
    manifest = BackupManifest(
        manifest_schema_version=MANIFEST_SCHEMA_VERSION,
        role=role,
        source_path=str(source_path),
        source_identity=_source_identity(source_path),
        source_schema_fingerprint=source_fp,
        source_table_counts=source_counts,
        backup_path=str(backup_path),
        backup_sha256=_sha256(backup_path),
        backup_byte_size=details.st_size,
        backup_mode=mode,
        backup_uid=getattr(details, "st_uid", None),
        backup_gid=getattr(details, "st_gid", None),
        integrity_check=integrity,
        foreign_key_violations=violations,
        created_at=_utc_now(),
        privacy_precedence_required=True,
    )
    output_manifest.write_text(
        json.dumps(asdict(manifest), sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    try:
        os.chmod(output_manifest, 0o600)
    except OSError as exc:
        raise BackupError("manifest permissions could not be restricted") from exc
    return manifest


def verify_backup(
    source: Path,
    manifest: BackupManifest,
    *,
    expected_role: str,
) -> BackupManifest:
    """Revalidate backup evidence immediately before migration."""
    source_path = Path(source).resolve()
    backup_path = Path(manifest.backup_path).resolve()
    if (
        manifest.manifest_schema_version != MANIFEST_SCHEMA_VERSION
        or manifest.role != expected_role
        or Path(manifest.source_path).resolve() != source_path
        or manifest.source_identity != _source_identity(source_path)
        or not manifest.privacy_precedence_required
        or not backup_path.is_file()
    ):
        raise BackupError("backup evidence does not identify this source")
    source_fp, source_counts, source_integrity, source_fk = _inspect(source_path)
    backup_fp, backup_counts, integrity, violations = _inspect(backup_path)
    details = backup_path.stat()
    expected = {
        "source_fp": manifest.source_schema_fingerprint,
        "source_counts": manifest.source_table_counts,
        "backup_sha": manifest.backup_sha256,
        "backup_size": manifest.backup_byte_size,
        "backup_mode": manifest.backup_mode,
    }
    actual = {
        "source_fp": source_fp,
        "source_counts": source_counts,
        "backup_sha": _sha256(backup_path),
        "backup_size": details.st_size,
        "backup_mode": stat.S_IMODE(details.st_mode),
    }
    if (
        actual != expected
        or source_integrity != "ok"
        or source_fk
        or backup_fp != source_fp
        or backup_counts != source_counts
        or integrity != "ok"
        or violations
        or (os.name != "nt" and actual["backup_mode"] != 0o600)
    ):
        raise BackupError("backup evidence is stale or invalid")
    return manifest
