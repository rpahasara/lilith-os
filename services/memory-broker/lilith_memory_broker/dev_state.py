"""Explicitly provisioned, persistent synthetic DEV owner-control ledger."""

from __future__ import annotations

import json
import os
import secrets
import sqlite3
import stat
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

import rfc8785
from lilith_memory import owner_proof as P

from . import state as legacy
from .dev_config import DevConfig, credential_fingerprint
from .request import LOGICAL_OWNER_ID, SYNTHETIC_ACCESS_IDENTITY


DEV_MODE = "B1B2_SYNTHETIC_DEV_V1"
_DDL = tuple(
    statement.replace("CHECK(version=1)", "CHECK(version=2)").replace(
        "('SYNTHETIC_TEST','PRODUCTION_GOVERNED')", "('B1B2_SYNTHETIC_DEV_V1')"
    )
    for statement in legacy._DDL
    if not statement.startswith("CREATE TABLE owner_authority_claim_v1")
) + (
    "CREATE TABLE synthetic_claim_v1 (challenge_id TEXT PRIMARY KEY REFERENCES owner_proof_challenge_v1(challenge_id), request_digest TEXT NOT NULL CHECK(length(request_digest)=64), action_digest TEXT NOT NULL CHECK(length(action_digest)=64), synthetic_credential_record_id TEXT NOT NULL, status TEXT NOT NULL CHECK(status IN ('CLAIMED','SYNTHETIC_EVIDENCE_COMMITTED','ABANDONED')), synthetic_evidence_id TEXT UNIQUE, claimed_at TEXT NOT NULL, completed_at TEXT, failure_code TEXT, CHECK((status='SYNTHETIC_EVIDENCE_COMMITTED')=(synthetic_evidence_id IS NOT NULL)))",
)


def schema_fingerprint() -> str:
    with closing(sqlite3.connect(":memory:")) as conn:
        for statement in _DDL:
            conn.execute(statement)
        return legacy._fingerprint(conn)


class DevOwnerControlState(legacy.OwnerControlState):
    """B1a challenge ABI with a claim table that cannot imply Actor authority."""

    def __init__(self, path: Path, config: DevConfig, *, expected_uid: int | None = None):
        self.path = Path(path)
        if self.path.name != "owner_control.db" or self.path.is_symlink():
            raise legacy.StateError("INVALID_DEV_STATE_PATH")
        self.mode = DEV_MODE
        self.config = config
        self.expected_uid = expected_uid
        self.challenge_store = legacy.BrokerChallengeStore(self.path)

    @classmethod
    def provision(cls, path: Path, config: DevConfig, credential: P.OwnerCredentialV1, *, expected_uid: int | None = None) -> DevOwnerControlState:
        if os.environ.get("LILITH_ENV") != "dev":
            raise legacy.StateError("DEV_ONLY_PROVISION")
        result = cls(path, config, expected_uid=expected_uid)
        if result.path.exists() or not result.path.parent.is_dir() or result.path.parent.is_symlink():
            raise legacy.StateError("STATE_COLLISION")
        credential.validate()
        if credential.status != "ACTIVE" or credential.rp_id != P.SYNTHETIC_RP_ID or credential.owner_principal != SYNTHETIC_ACCESS_IDENTITY or credential_fingerprint(credential) != config.credential_fingerprint:
            raise legacy.StateError("SYNTHETIC_CREDENTIAL_REQUIRED")
        if schema_fingerprint() != config.owner_schema_fingerprint:
            raise legacy.StateError("SCHEMA_FINGERPRINT_MISMATCH")
        old = os.umask(0o077)
        try:
            with closing(sqlite3.connect(result.path, isolation_level=None)) as conn:
                conn.execute("PRAGMA foreign_keys=ON")
                conn.execute("PRAGMA journal_mode=WAL")
                conn.execute("PRAGMA synchronous=FULL")
                conn.execute("BEGIN IMMEDIATE")
                for statement in _DDL:
                    conn.execute(statement)
                conn.execute("INSERT INTO broker_schema_v1 VALUES (?,?,?,?,?)", (
                    2, schema_fingerprint(), DEV_MODE, secrets.token_hex(16),
                    datetime.now(timezone.utc).isoformat(timespec="seconds"),
                ))
                conn.execute("INSERT INTO owner_identity_v1 VALUES (?)", (LOGICAL_OWNER_ID,))
                conn.execute("INSERT INTO owner_access_identity_v1 VALUES (?,?,?)", (LOGICAL_OWNER_ID, SYNTHETIC_ACCESS_IDENTITY, "ACTIVE"))
                conn.execute("INSERT INTO owner_credential_v1 VALUES (?,?,?)", (
                    credential.record_id, LOGICAL_OWNER_ID, rfc8785.dumps(credential.to_dict()),
                ))
                conn.commit()
        finally:
            os.umask(old)
        if os.name != "nt":
            os.chmod(result.path, 0o600)
        result.validate_startup()
        return result

    def validate_startup(self) -> None:
        if not self.path.is_file() or self.path.is_symlink():
            raise legacy.StateError("OWNER_CONTROL_MISSING")
        metadata = self.path.stat()
        if os.name != "nt" and (stat.S_IMODE(metadata.st_mode) != 0o600 or (self.expected_uid is not None and metadata.st_uid != self.expected_uid)):
            raise legacy.StateError("OWNER_CONTROL_OWNERSHIP")
        with closing(self._connect()) as conn:
            if conn.execute("PRAGMA foreign_keys").fetchone()[0] != 1 or conn.execute("PRAGMA synchronous").fetchone()[0] != 2:
                raise legacy.StateError("SQLITE_POLICY_MISMATCH")
            if conn.execute("PRAGMA integrity_check").fetchone()[0] != "ok" or conn.execute("PRAGMA foreign_key_check").fetchall():
                raise legacy.StateError("OWNER_CONTROL_CORRUPT")
            expected = schema_fingerprint()
            if expected != self.config.owner_schema_fingerprint or legacy._fingerprint(conn) != expected:
                raise legacy.StateError("OWNER_CONTROL_SCHEMA_MISMATCH")
            rows = conn.execute("SELECT version,fingerprint,mode,authority_epoch FROM broker_schema_v1").fetchall()
            if len(rows) != 1 or rows[0][:3] != (2, expected, DEV_MODE) or not rows[0][3]:
                raise legacy.StateError("OWNER_CONTROL_METADATA_MISMATCH")
            if conn.execute("SELECT owner_id FROM owner_identity_v1").fetchall() != [(LOGICAL_OWNER_ID,)]:
                raise legacy.StateError("OWNER_IDENTITY_MISMATCH")
            if conn.execute("SELECT owner_id,access_identity,status FROM owner_access_identity_v1").fetchall() != [(LOGICAL_OWNER_ID, SYNTHETIC_ACCESS_IDENTITY, "ACTIVE")]:
                raise legacy.StateError("ACCESS_IDENTITY_MISMATCH")
            credentials = conn.execute("SELECT record_id,owner_id,credential_json FROM owner_credential_v1").fetchall()
            if len(credentials) != 1:
                raise legacy.StateError("SYNTHETIC_CREDENTIAL_MISSING")
            record_id, owner_id, raw = credentials[0]
            credential = P.OwnerCredentialV1.from_dict(json.loads(bytes(raw)))
            if owner_id != LOGICAL_OWNER_ID or record_id != credential.record_id or credential.status != "ACTIVE" or credential.rp_id != P.SYNTHETIC_RP_ID or credential.owner_principal != SYNTHETIC_ACCESS_IDENTITY or bytes(raw) != rfc8785.dumps(credential.to_dict()) or credential_fingerprint(credential) != self.config.credential_fingerprint:
                raise legacy.StateError("SYNTHETIC_CREDENTIAL_MISMATCH")

    def claim(self, proof: P.OwnerProofVerificationResultV1) -> None:
        if not isinstance(proof, P.OwnerProofVerificationResultV1) or proof.status != "VERIFIED_PROOF_ONLY":
            raise legacy.StateError("VERIFIED_PROOF_REQUIRED")
        request = self.request(proof.challenge_id)
        if proof.owner_principal != request.access_identity or proof.action_digest != request.action.action_digest or proof.request_digest != request.request_digest:
            raise legacy.StateError("PROOF_BINDING_MISMATCH")
        with closing(self._connect()) as conn:
            try:
                conn.execute("BEGIN IMMEDIATE")
                row = conn.execute("SELECT state,consumed_credential_record_id FROM owner_proof_challenge_v1 WHERE challenge_id=?", (proof.challenge_id,)).fetchone()
                if row != ("CONSUMED", proof.credential_record_id):
                    raise legacy.StateError("CONSUMED_CHALLENGE_REQUIRED")
                conn.execute("INSERT INTO synthetic_claim_v1 VALUES (?,?,?,?,?,?,?,?,?)", (
                    proof.challenge_id, proof.request_digest, proof.action_digest,
                    proof.credential_record_id, "CLAIMED", None,
                    datetime.now(timezone.utc).isoformat(), None, None,
                ))
                conn.commit()
            except sqlite3.IntegrityError as exc:
                conn.rollback()
                raise legacy.StateError("CLAIM_ALREADY_EXISTS") from exc
            except Exception:
                conn.rollback()
                raise

    def claim_row(self, challenge_id: str) -> tuple | None:
        with closing(self._connect()) as conn:
            return conn.execute("SELECT challenge_id,request_digest,action_digest,synthetic_credential_record_id,status,synthetic_evidence_id FROM synthetic_claim_v1 WHERE challenge_id=?", (challenge_id,)).fetchone()

    def link_evidence(self, challenge_id: str, evidence_id: str, request_digest: str, action_digest: str) -> None:
        if not evidence_id.startswith("se."):
            raise legacy.StateError("NON_SYNTHETIC_EVIDENCE")
        with closing(self._connect()) as conn:
            try:
                conn.execute("BEGIN IMMEDIATE")
                row = conn.execute("SELECT request_digest,action_digest,status,synthetic_evidence_id FROM synthetic_claim_v1 WHERE challenge_id=?", (challenge_id,)).fetchone()
                if row is None or row[:2] != (request_digest, action_digest):
                    raise legacy.StateError("CLAIM_BINDING_MISMATCH")
                if row[2] == "SYNTHETIC_EVIDENCE_COMMITTED":
                    if row[3] != evidence_id:
                        raise legacy.StateError("EVIDENCE_LINK_CONFLICT")
                else:
                    conn.execute("UPDATE synthetic_claim_v1 SET status='SYNTHETIC_EVIDENCE_COMMITTED',synthetic_evidence_id=?,completed_at=?,failure_code=NULL WHERE challenge_id=? AND status IN ('CLAIMED','ABANDONED')", (evidence_id, datetime.now(timezone.utc).isoformat(), challenge_id))
                conn.commit()
            except Exception:
                conn.rollback()
                raise

    def abandon(self, challenge_id: str) -> None:
        with closing(self._connect()) as conn:
            conn.execute("UPDATE synthetic_claim_v1 SET status='ABANDONED',completed_at=?,failure_code='SYNTHETIC_EVIDENCE_ABSENT' WHERE challenge_id=? AND status='CLAIMED'", (datetime.now(timezone.utc).isoformat(), challenge_id))
