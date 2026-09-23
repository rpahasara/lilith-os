"""Non-canonical synthetic evidence: never an ActorEvidenceRefV1."""

from __future__ import annotations

import hashlib
import os
import sqlite3
import stat
from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from .request import LOGICAL_OWNER_ID


PROFILE = "B1B2_SYNTHETIC_EVIDENCE_V1"
_DDL = (
    "CREATE TABLE synthetic_schema_v1 (profile TEXT PRIMARY KEY, release_sha TEXT NOT NULL, created_at TEXT NOT NULL)",
    "CREATE TABLE synthetic_evidence_v1 (challenge_id TEXT PRIMARY KEY, synthetic_evidence_id TEXT NOT NULL UNIQUE CHECK(synthetic_evidence_id LIKE 'se.%'), request_digest TEXT NOT NULL CHECK(length(request_digest)=64), action_digest TEXT NOT NULL CHECK(length(action_digest)=64), logical_owner_id TEXT NOT NULL, synthetic_credential_record_id TEXT NOT NULL, fixture_marker TEXT NOT NULL, created_at TEXT NOT NULL, state TEXT NOT NULL CHECK(state='SYNTHETIC_COMMITTED'))",
)


class SyntheticEvidenceError(RuntimeError):
    pass


@dataclass(frozen=True)
class SyntheticEvidenceV1:
    synthetic_evidence_id: str
    challenge_id: str
    request_digest: str
    action_digest: str
    logical_owner_id: str
    synthetic_credential_record_id: str
    fixture_marker: str
    created_at: str
    state: str = "SYNTHETIC_COMMITTED"

    def __post_init__(self) -> None:
        if not self.synthetic_evidence_id.startswith("se.") or self.logical_owner_id != LOGICAL_OWNER_ID or self.state != "SYNTHETIC_COMMITTED":
            raise SyntheticEvidenceError("NON_SYNTHETIC_EVIDENCE")


def schema_fingerprint() -> str:
    return hashlib.sha256("\n".join(_DDL).encode()).hexdigest()


class SyntheticEvidenceStore:
    def __init__(self, path: Path, *, release_sha: str, expected_uid: int | None = None):
        self.path = Path(path)
        self.release_sha = release_sha
        self.expected_uid = expected_uid
        if self.path.is_symlink() or self.path.name != "synthetic_evidence.db":
            raise SyntheticEvidenceError("INVALID_SYNTHETIC_PATH")

    @classmethod
    def provision(cls, path: Path, *, release_sha: str, expected_uid: int | None = None) -> SyntheticEvidenceStore:
        if os.environ.get("LILITH_ENV") != "dev":
            raise SyntheticEvidenceError("DEV_ONLY")
        store = cls(path, release_sha=release_sha, expected_uid=expected_uid)
        if store.path.exists() or not store.path.parent.is_dir():
            raise SyntheticEvidenceError("STATE_COLLISION")
        old = os.umask(0o077)
        try:
            with closing(sqlite3.connect(store.path, isolation_level=None)) as conn:
                conn.execute("PRAGMA journal_mode=WAL")
                conn.execute("PRAGMA synchronous=FULL")
                for item in _DDL:
                    conn.execute(item)
                conn.execute("INSERT INTO synthetic_schema_v1 VALUES (?,?,?)", (PROFILE, release_sha, datetime.now(timezone.utc).isoformat()))
        finally:
            os.umask(old)
        if os.name != "nt":
            os.chmod(store.path, 0o600)
        store.validate_startup()
        return store

    def _connect(self) -> sqlite3.Connection:
        if not self.path.is_file() or self.path.is_symlink():
            raise SyntheticEvidenceError("SYNTHETIC_STATE_MISSING")
        conn = sqlite3.connect(f"file:{self.path.resolve().as_posix()}?mode=rw", uri=True, timeout=5, isolation_level=None)
        conn.execute("PRAGMA busy_timeout=5000")
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA synchronous=FULL")
        if conn.execute("PRAGMA journal_mode").fetchone()[0].lower() != "wal":
            conn.close()
            raise SyntheticEvidenceError("JOURNAL_MODE_MISMATCH")
        return conn

    def validate_startup(self) -> None:
        if not self.path.is_file() or self.path.is_symlink():
            raise SyntheticEvidenceError("SYNTHETIC_STATE_MISSING")
        metadata = self.path.stat()
        if os.name != "nt" and (stat.S_IMODE(metadata.st_mode) != 0o600 or (self.expected_uid is not None and metadata.st_uid != self.expected_uid)):
            raise SyntheticEvidenceError("SYNTHETIC_STATE_OWNERSHIP")
        with closing(self._connect()) as conn:
            if conn.execute("PRAGMA integrity_check").fetchone()[0] != "ok" or conn.execute("PRAGMA foreign_key_check").fetchall():
                raise SyntheticEvidenceError("SYNTHETIC_STATE_CORRUPT")
            objects = [row[0] for row in conn.execute("SELECT sql FROM sqlite_master WHERE sql IS NOT NULL")]
            if sorted(objects) != sorted(_DDL):
                raise SyntheticEvidenceError("SYNTHETIC_SCHEMA_MISMATCH")
            if conn.execute("SELECT profile,release_sha FROM synthetic_schema_v1").fetchall() != [(PROFILE, self.release_sha)]:
                raise SyntheticEvidenceError("SYNTHETIC_METADATA_MISMATCH")

    def find(self, challenge_id: str) -> SyntheticEvidenceV1 | None:
        with closing(self._connect()) as conn:
            row = conn.execute("SELECT synthetic_evidence_id,challenge_id,request_digest,action_digest,logical_owner_id,synthetic_credential_record_id,fixture_marker,created_at,state FROM synthetic_evidence_v1 WHERE challenge_id=?", (challenge_id,)).fetchone()
        return SyntheticEvidenceV1(*row) if row else None

    def commit_once(self, *, challenge_id: str, request_digest: str, action_digest: str, credential_record_id: str, fixture_marker: str) -> SyntheticEvidenceV1:
        if not challenge_id.startswith("och.") or len(request_digest) != 64 or len(action_digest) != 64 or not credential_record_id.startswith("ocred.") or fixture_marker != "fixture.b1b1.synthetic-codename.v1":
            raise SyntheticEvidenceError("INVALID_SYNTHETIC_BINDING")
        identifier = "se." + hashlib.sha256((PROFILE + "\0" + challenge_id).encode()).hexdigest()
        created = datetime.now(timezone.utc).isoformat()
        with closing(self._connect()) as conn:
            try:
                conn.execute("BEGIN IMMEDIATE")
                conn.execute("INSERT INTO synthetic_evidence_v1 VALUES (?,?,?,?,?,?,?,?,?)", (
                    challenge_id, identifier, request_digest, action_digest, LOGICAL_OWNER_ID,
                    credential_record_id, fixture_marker, created, "SYNTHETIC_COMMITTED",
                ))
                conn.commit()
            except sqlite3.IntegrityError as exc:
                conn.rollback()
                raise SyntheticEvidenceError("SYNTHETIC_EVIDENCE_ALREADY_EXISTS") from exc
        return SyntheticEvidenceV1(identifier, challenge_id, request_digest, action_digest, LOGICAL_OWNER_ID, credential_record_id, fixture_marker, created)
