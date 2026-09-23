"""Fail-closed broker ledger and B1a-compatible SQLite adapter."""

from __future__ import annotations

import hashlib
import json
import os
import secrets
import sqlite3
import stat
import tempfile
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

import rfc8785

from lilith_memory import owner_proof as P
from .request import LOGICAL_OWNER_ID, SYNTHETIC_ACCESS_IDENTITY, OwnerRequestV1


SCHEMA_VERSION = 1
TEST_MODE = "SYNTHETIC_TEST"
PRODUCTION_MODE = "PRODUCTION_GOVERNED"
BUSY_TIMEOUT_MS = 5000
_DDL = (
    "CREATE TABLE broker_schema_v1 (version INTEGER PRIMARY KEY CHECK(version=1), fingerprint TEXT NOT NULL CHECK(length(fingerprint)=64), mode TEXT NOT NULL CHECK(mode IN ('SYNTHETIC_TEST','PRODUCTION_GOVERNED')), authority_epoch TEXT NOT NULL, created_at TEXT NOT NULL)",
    "CREATE TABLE owner_identity_v1 (owner_id TEXT PRIMARY KEY)",
    "CREATE TABLE owner_access_identity_v1 (owner_id TEXT NOT NULL REFERENCES owner_identity_v1(owner_id), access_identity TEXT NOT NULL UNIQUE, status TEXT NOT NULL CHECK(status IN ('ACTIVE','REVOKED')), PRIMARY KEY(owner_id,access_identity))",
    "CREATE TABLE owner_proof_challenge_v1 (challenge_id TEXT PRIMARY KEY, challenge_json BLOB NOT NULL, state TEXT NOT NULL CHECK(state IN ('PREPARED','CANCELLED','EXPIRED','CONSUMED')), consumed_credential_record_id TEXT, consumed_at TEXT)",
    "CREATE TABLE owner_request_v1 (challenge_id TEXT PRIMARY KEY REFERENCES owner_proof_challenge_v1(challenge_id), request_json BLOB NOT NULL, request_digest TEXT NOT NULL CHECK(length(request_digest)=64))",
    "CREATE TABLE owner_credential_v1 (record_id TEXT PRIMARY KEY, owner_id TEXT NOT NULL REFERENCES owner_identity_v1(owner_id), credential_json BLOB NOT NULL)",
    "CREATE VIEW owner_proof_test_credential_v1 AS SELECT record_id,credential_json FROM owner_credential_v1",
    "CREATE TRIGGER owner_proof_test_credential_update INSTEAD OF UPDATE OF credential_json ON owner_proof_test_credential_v1 BEGIN UPDATE owner_credential_v1 SET credential_json=NEW.credential_json WHERE record_id=OLD.record_id; END",
    "CREATE TABLE owner_authority_claim_v1 (challenge_id TEXT PRIMARY KEY REFERENCES owner_proof_challenge_v1(challenge_id), request_digest TEXT NOT NULL CHECK(length(request_digest)=64), action_digest TEXT NOT NULL CHECK(length(action_digest)=64), status TEXT NOT NULL CHECK(status IN ('CLAIMED','EVIDENCE_COMMITTED','ABANDONED')), actor_evidence_ref_id TEXT UNIQUE, claimed_at TEXT NOT NULL, completed_at TEXT, failure_code TEXT, CHECK((status='EVIDENCE_COMMITTED')=(actor_evidence_ref_id IS NOT NULL)))",
)


class StateError(RuntimeError):
    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


def _fingerprint(conn: sqlite3.Connection) -> str:
    rows = conn.execute(
        "SELECT type,name,sql FROM sqlite_master WHERE sql IS NOT NULL ORDER BY type,name"
    ).fetchall()
    source = "\n".join(f"{row[0]}:{row[1]}:{' '.join(row[2].split())}" for row in rows)
    return hashlib.sha256(source.encode("utf-8")).hexdigest()


def expected_schema_fingerprint() -> str:
    with closing(sqlite3.connect(":memory:")) as conn:
        for statement in _DDL:
            conn.execute(statement)
        return _fingerprint(conn)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


class BrokerChallengeStore(P.DurableOwnerChallengeStore):
    """B1a verifier ABI backed by the broker public registry view."""

    def _connect(self) -> sqlite3.Connection:
        if not self.path.is_file():
            raise StateError("OWNER_CONTROL_MISSING")
        conn = sqlite3.connect(f"file:{self.path.resolve().as_posix()}?mode=rw", uri=True, timeout=5, isolation_level=None)
        try:
            conn.execute("PRAGMA busy_timeout=5000")
            conn.execute("PRAGMA foreign_keys=ON")
            conn.execute("PRAGMA synchronous=FULL")
            if conn.execute("PRAGMA journal_mode").fetchone()[0].lower() != "wal":
                raise StateError("JOURNAL_MODE_MISMATCH")
            return conn
        except Exception:
            conn.close()
            raise

    def initialize(self) -> None:
        raise StateError("GOVERNED_INITIALIZATION_REQUIRED")


class OwnerControlState:
    def __init__(self, path: Path, *, mode: str):
        self.path = Path(path)
        forbidden = {"cognitive_memory.db", "privacy_governance.db", "lilith.db"}
        if self.path.is_symlink() or self.path.name in forbidden or self.path.resolve().name in forbidden:
            raise StateError("GOVERNED_DATABASE_FORBIDDEN")
        if mode not in {TEST_MODE, PRODUCTION_MODE}:
            raise StateError("INVALID_MODE")
        self.mode = mode
        self.challenge_store = BrokerChallengeStore(self.path)

    @classmethod
    def initialize_test(cls, path: Path) -> OwnerControlState:
        target = Path(path).resolve()
        if os.environ.get("LILITH_ENV") != "test" or not target.is_relative_to(Path(tempfile.gettempdir()).resolve()):
            raise StateError("TEST_INITIALIZATION_FORBIDDEN")
        if target.exists() or not target.parent.is_dir():
            raise StateError("TEST_STATE_ALREADY_EXISTS_OR_PARENT_MISSING")
        state = cls(target, mode=TEST_MODE)
        old_umask = os.umask(0o077)
        try:
            conn = sqlite3.connect(str(target), timeout=5, isolation_level=None)
        finally:
            os.umask(old_umask)
        try:
            conn.execute("PRAGMA busy_timeout=5000")
            conn.execute("PRAGMA foreign_keys=ON")
            conn.execute("PRAGMA synchronous=FULL")
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("BEGIN IMMEDIATE")
            for statement in _DDL:
                conn.execute(statement)
            fingerprint = _fingerprint(conn)
            conn.execute("INSERT INTO broker_schema_v1 VALUES (?,?,?,?,?)", (
                SCHEMA_VERSION, fingerprint, TEST_MODE, secrets.token_hex(16), _utc_now(),
            ))
            conn.execute("INSERT INTO owner_identity_v1 VALUES (?)", (LOGICAL_OWNER_ID,))
            conn.execute("INSERT INTO owner_access_identity_v1 VALUES (?,?,?)", (
                LOGICAL_OWNER_ID, SYNTHETIC_ACCESS_IDENTITY, "ACTIVE",
            ))
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
        if os.name != "nt":
            os.chmod(target, 0o600)
        state.validate_startup()
        return state

    def _connect(self) -> sqlite3.Connection:
        return self.challenge_store._connect()

    def validate_startup(self) -> None:
        if not self.path.is_file():
            raise StateError("OWNER_CONTROL_MISSING")
        if os.name != "nt" and stat.S_IMODE(self.path.stat().st_mode) != 0o600:
            raise StateError("OWNER_CONTROL_PERMISSIONS")
        try:
            with closing(self._connect()) as conn:
                if conn.execute("PRAGMA foreign_keys").fetchone()[0] != 1:
                    raise StateError("FOREIGN_KEYS_DISABLED")
                if conn.execute("PRAGMA synchronous").fetchone()[0] != 2:
                    raise StateError("SYNC_MODE_MISMATCH")
                if conn.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                    raise StateError("OWNER_CONTROL_CORRUPT")
                if conn.execute("PRAGMA foreign_key_check").fetchall():
                    raise StateError("OWNER_CONTROL_FOREIGN_KEY_VIOLATION")
                if _fingerprint(conn) != expected_schema_fingerprint():
                    raise StateError("OWNER_CONTROL_SCHEMA_MISMATCH")
                rows = conn.execute("SELECT version,fingerprint,mode,authority_epoch FROM broker_schema_v1").fetchall()
                if len(rows) != 1 or rows[0][0] != SCHEMA_VERSION or rows[0][1] != expected_schema_fingerprint() or rows[0][2] != self.mode or not rows[0][3]:
                    raise StateError("OWNER_CONTROL_METADATA_MISMATCH")
                owners = conn.execute("SELECT owner_id FROM owner_identity_v1").fetchall()
                if owners != [(LOGICAL_OWNER_ID,)]:
                    raise StateError("OWNER_IDENTITY_MISMATCH")
                credentials = conn.execute("SELECT record_id,owner_id,credential_json FROM owner_credential_v1").fetchall()
                for record_id, owner_id, raw in credentials:
                    value = json.loads(bytes(raw).decode("utf-8"))
                    credential = P.OwnerCredentialV1.from_dict(value)
                    if bytes(raw) != rfc8785.dumps(credential.to_dict()) or credential.record_id != record_id or owner_id != LOGICAL_OWNER_ID:
                        raise StateError("CREDENTIAL_REGISTRY_MISMATCH")
                    if self.mode == PRODUCTION_MODE and (credential.rp_id.endswith(".invalid") or credential.owner_principal.endswith("@example.invalid")):
                        raise StateError("SYNTHETIC_CREDENTIAL_IN_PRODUCTION")
                if self.mode == PRODUCTION_MODE:
                    synthetic = conn.execute("SELECT 1 FROM owner_access_identity_v1 WHERE access_identity=?", (SYNTHETIC_ACCESS_IDENTITY,)).fetchone()
                    if synthetic:
                        raise StateError("SYNTHETIC_ACCESS_IN_PRODUCTION")
        except StateError:
            raise
        except (sqlite3.Error, ValueError, TypeError, UnicodeError, P.OwnerProofError) as exc:
            raise StateError("OWNER_CONTROL_INVALID") from exc

    def install_synthetic_credential(self, credential: P.OwnerCredentialV1) -> None:
        if self.mode != TEST_MODE or os.environ.get("LILITH_ENV") != "test":
            raise StateError("SYNTHETIC_CREDENTIAL_FORBIDDEN")
        credential.validate()
        if credential.owner_principal != SYNTHETIC_ACCESS_IDENTITY or credential.rp_id != P.SYNTHETIC_RP_ID:
            raise StateError("NON_SYNTHETIC_CREDENTIAL")
        with closing(self._connect()) as conn:
            conn.execute("INSERT INTO owner_credential_v1 VALUES (?,?,?)", (
                credential.record_id, LOGICAL_OWNER_ID, rfc8785.dumps(credential.to_dict()),
            ))

    def save_request_after_prepare(self, request: OwnerRequestV1) -> None:
        request.validate()
        with closing(self._connect()) as conn:
            conn.execute("BEGIN IMMEDIATE")
            try:
                row = conn.execute("SELECT challenge_json,state FROM owner_proof_challenge_v1 WHERE challenge_id=?", (request.challenge_id,)).fetchone()
                if row is None or row[1] != "PREPARED":
                    raise StateError("CHALLENGE_NOT_PREPARED")
                challenge = P.OwnerMemoryChallengeV1.from_dict(json.loads(bytes(row[0])))
                if challenge.action_digest != request.action.action_digest or challenge.request_digest != request.request_digest:
                    raise StateError("PREPARED_BINDING_MISMATCH")
                conn.execute("INSERT INTO owner_request_v1 VALUES (?,?,?)", (
                    request.challenge_id, request.canonical_bytes(), request.request_digest,
                ))
                conn.commit()
            except Exception:
                conn.rollback()
                raise

    def request(self, challenge_id: str) -> OwnerRequestV1:
        with closing(self._connect()) as conn:
            row = conn.execute("SELECT request_json,request_digest FROM owner_request_v1 WHERE challenge_id=?", (challenge_id,)).fetchone()
        if row is None:
            raise StateError("REQUEST_UNAVAILABLE")
        try:
            request = OwnerRequestV1.from_dict(json.loads(bytes(row[0])))
            if request.challenge_id != challenge_id or request.canonical_bytes() != bytes(row[0]) or request.request_digest != row[1]:
                raise StateError("REQUEST_BINDING_MISMATCH")
            return request
        except (ValueError, TypeError, UnicodeError) as exc:
            raise StateError("REQUEST_INVALID") from exc

    def claim(self, proof: P.OwnerProofVerificationResultV1) -> None:
        if not isinstance(proof, P.OwnerProofVerificationResultV1) or proof.status != "VERIFIED_PROOF_ONLY":
            raise StateError("VERIFIED_PROOF_REQUIRED")
        request = self.request(proof.challenge_id)
        if proof.owner_principal != request.access_identity or proof.action_digest != request.action.action_digest or proof.request_digest != request.request_digest:
            raise StateError("PROOF_BINDING_MISMATCH")
        with closing(self._connect()) as conn:
            conn.execute("BEGIN IMMEDIATE")
            try:
                row = conn.execute("SELECT state,challenge_json,consumed_credential_record_id FROM owner_proof_challenge_v1 WHERE challenge_id=?", (proof.challenge_id,)).fetchone()
                if row is None or row[0] != "CONSUMED" or row[2] != proof.credential_record_id:
                    raise StateError("CONSUMED_CHALLENGE_REQUIRED")
                challenge = P.OwnerMemoryChallengeV1.from_dict(json.loads(bytes(row[1])))
                if challenge.request_digest != request.request_digest or challenge.action_digest != request.action.action_digest:
                    raise StateError("CHALLENGE_BINDING_MISMATCH")
                conn.execute("INSERT INTO owner_authority_claim_v1 VALUES (?,?,?,?,?,?,?,?)", (
                    proof.challenge_id, proof.request_digest, proof.action_digest,
                    "CLAIMED", None, _utc_now(), None, None,
                ))
                conn.commit()
            except sqlite3.IntegrityError as exc:
                conn.rollback()
                raise StateError("CLAIM_ALREADY_EXISTS") from exc
            except Exception:
                conn.rollback()
                raise

    def claim_row(self, challenge_id: str) -> tuple | None:
        with closing(self._connect()) as conn:
            return conn.execute("SELECT challenge_id,request_digest,action_digest,status,actor_evidence_ref_id,claimed_at,completed_at,failure_code FROM owner_authority_claim_v1 WHERE challenge_id=?", (challenge_id,)).fetchone()

    def link_evidence(self, challenge_id: str, evidence_ref_id: str, request_digest: str, action_digest: str) -> None:
        with closing(self._connect()) as conn:
            conn.execute("BEGIN IMMEDIATE")
            try:
                row = conn.execute("SELECT request_digest,action_digest,status,actor_evidence_ref_id FROM owner_authority_claim_v1 WHERE challenge_id=?", (challenge_id,)).fetchone()
                if row is None or row[0] != request_digest or row[1] != action_digest:
                    raise StateError("CLAIM_BINDING_MISMATCH")
                if row[2] == "EVIDENCE_COMMITTED":
                    if row[3] != evidence_ref_id:
                        raise StateError("EVIDENCE_LINK_CONFLICT")
                    conn.commit()
                    return
                conn.execute("UPDATE owner_authority_claim_v1 SET status='EVIDENCE_COMMITTED',actor_evidence_ref_id=?,completed_at=?,failure_code=NULL WHERE challenge_id=? AND status IN ('CLAIMED','ABANDONED')", (evidence_ref_id, _utc_now(), challenge_id))
                conn.commit()
            except Exception:
                conn.rollback()
                raise

    def abandon(self, challenge_id: str, code: str) -> None:
        if code not in {"EVIDENCE_ABSENT", "EVIDENCE_INVALID", "PRIVACY_ERASED"}:
            raise StateError("INVALID_FAILURE_CODE")
        with closing(self._connect()) as conn:
            conn.execute("UPDATE owner_authority_claim_v1 SET status='ABANDONED',completed_at=?,failure_code=? WHERE challenge_id=? AND status='CLAIMED'", (_utc_now(), code, challenge_id))
