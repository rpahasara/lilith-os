"""Slice 15B2a actor, consent, Policy, and rollback authorities.

Each logical owner has a disjoint SQLite table set and a runtime authorizer.
Schema mutation is intentionally absent from runtime store constructors; the
separate Slice 15B2a migration authority creates and fingerprints the tables.
"""

from __future__ import annotations

import hashlib
import hmac
import os
import secrets
import sqlite3
import stat
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Dict, FrozenSet, Optional, Tuple

try:
    from . import canonical_contracts as C
except ImportError:  # deploy-exact flat-directory tests
    import canonical_contracts as C


AUTHORITY_SCHEMA_VERSION = 1
POLICY_VERSION = "canonical-memory-policy-v1"
DEFAULT_EVIDENCE_TTL_SECONDS = 90
DEFAULT_CHALLENGE_TTL_SECONDS = 300

CONFIRMED = "CONFIRMED"
INVALID = "INVALID"
REVOKED = "REVOKED"
UNAVAILABLE = "UNAVAILABLE"
ALLOWED = "ALLOWED"
DENIED = "DENIED"

ACTOR_TABLES = frozenset({
    "actor_schema_migration",
    "actor_evidence_ref",
    "actor_evidence_consumption",
})
CONSENT_TABLES = frozenset({
    "consent_schema_migration",
    "consent_grant",
    "consent_revocation",
})
POLICY_TABLES = frozenset({"policy_schema_migration", "policy_decision"})
ROLLBACK_TABLES = frozenset({
    "rollback_schema_migration",
    "rollback_authorization",
    "rollback_consumption",
})
COGNITIVE_AUTHORITY_TABLES = (
    ACTOR_TABLES | CONSENT_TABLES | POLICY_TABLES | ROLLBACK_TABLES
)

AUTHORITY_SCHEMA_OBJECTS = frozenset({
    *COGNITIVE_AUTHORITY_TABLES,
    "actor_evidence_ref_no_update",
    "actor_evidence_ref_no_delete",
    "actor_evidence_consumption_no_update",
    "actor_evidence_consumption_no_delete",
    "consent_grant_fingerprint",
    "consent_grant_no_update",
    "consent_grant_no_delete",
    "consent_revocation_one_per_grant",
    "consent_revocation_no_update",
    "consent_revocation_no_delete",
    "policy_decision_fingerprint",
    "policy_decision_action",
    "policy_decision_no_update",
    "policy_decision_no_delete",
    "rollback_authorization_fingerprint",
    "rollback_authorization_no_update",
    "rollback_authorization_no_delete",
    "rollback_consumption_no_update",
    "rollback_consumption_no_delete",
})

AUTHORITY_MIGRATION_STATEMENTS = (
    """
    CREATE TABLE IF NOT EXISTS actor_schema_migration (
        version INTEGER PRIMARY KEY,
        schema_fingerprint TEXT NOT NULL,
        applied_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS actor_evidence_ref (
        actor_evidence_ref_id TEXT PRIMARY KEY,
        schema_version INTEGER NOT NULL CHECK(schema_version=1),
        actor_ref_id TEXT NOT NULL,
        authority TEXT NOT NULL CHECK(authority='LOCAL_OWNER_AUTHORITY_V1'),
        request_digest TEXT NOT NULL CHECK(length(request_digest)=64),
        action_digest TEXT NOT NULL CHECK(length(action_digest)=64),
        nonce TEXT NOT NULL UNIQUE,
        issued_at TEXT NOT NULL,
        expires_at TEXT NOT NULL,
        issuer_ref TEXT NOT NULL,
        evidence_fingerprint TEXT NOT NULL UNIQUE CHECK(length(evidence_fingerprint)=64)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS actor_evidence_consumption (
        actor_evidence_ref_id TEXT PRIMARY KEY
            REFERENCES actor_evidence_ref(actor_evidence_ref_id),
        action_digest TEXT NOT NULL CHECK(length(action_digest)=64),
        consumed_at TEXT NOT NULL,
        consumer_ref TEXT NOT NULL
    )
    """,
    """CREATE TRIGGER IF NOT EXISTS actor_evidence_ref_no_update
        BEFORE UPDATE ON actor_evidence_ref BEGIN
        SELECT RAISE(ABORT,'actor evidence is immutable'); END""",
    """CREATE TRIGGER IF NOT EXISTS actor_evidence_ref_no_delete
        BEFORE DELETE ON actor_evidence_ref BEGIN
        SELECT RAISE(ABORT,'actor evidence deletion requires Privacy authority'); END""",
    """CREATE TRIGGER IF NOT EXISTS actor_evidence_consumption_no_update
        BEFORE UPDATE ON actor_evidence_consumption BEGIN
        SELECT RAISE(ABORT,'actor evidence consumption is immutable'); END""",
    """CREATE TRIGGER IF NOT EXISTS actor_evidence_consumption_no_delete
        BEFORE DELETE ON actor_evidence_consumption BEGIN
        SELECT RAISE(ABORT,'actor evidence consumption deletion requires Privacy authority'); END""",
    """
    CREATE TABLE IF NOT EXISTS consent_schema_migration (
        version INTEGER PRIMARY KEY,
        schema_fingerprint TEXT NOT NULL,
        applied_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS consent_grant (
        consent_id TEXT PRIMARY KEY,
        schema_version INTEGER NOT NULL CHECK(schema_version=1),
        authority TEXT NOT NULL CHECK(authority='LOCAL_CONSENT_AUTHORITY_V1'),
        actor_ref_id TEXT NOT NULL,
        actor_evidence_ref_id TEXT NOT NULL REFERENCES actor_evidence_ref(actor_evidence_ref_id),
        memory_class TEXT NOT NULL,
        subject_namespace TEXT NOT NULL,
        subject_key TEXT NOT NULL,
        operation TEXT NOT NULL CHECK(operation IN ('CREATE','SUPERSEDE','RESTORE')),
        payload_digest TEXT NOT NULL CHECK(length(payload_digest)=64),
        expected_active_revision_id TEXT,
        restore_revision_id TEXT,
        purpose TEXT NOT NULL CHECK(purpose='LONG_TERM_PERSONAL_PROJECT_RECALL'),
        granted_at TEXT NOT NULL,
        issuer_type TEXT NOT NULL CHECK(issuer_type='USER_CONFIRMATION'),
        issuer_ref TEXT NOT NULL,
        intent_ref_id TEXT NOT NULL,
        privacy_notice_version TEXT NOT NULL,
        action_digest TEXT NOT NULL CHECK(length(action_digest)=64),
        consent_fingerprint TEXT NOT NULL CHECK(length(consent_fingerprint)=64)
    )
    """,
    """CREATE UNIQUE INDEX IF NOT EXISTS consent_grant_fingerprint
        ON consent_grant(consent_fingerprint)""",
    """CREATE TRIGGER IF NOT EXISTS consent_grant_no_update
        BEFORE UPDATE ON consent_grant BEGIN
        SELECT RAISE(ABORT,'consent grant is immutable'); END""",
    """CREATE TRIGGER IF NOT EXISTS consent_grant_no_delete
        BEFORE DELETE ON consent_grant BEGIN
        SELECT RAISE(ABORT,'consent deletion requires Privacy authority'); END""",
    """
    CREATE TABLE IF NOT EXISTS consent_revocation (
        revocation_id TEXT PRIMARY KEY,
        consent_id TEXT NOT NULL REFERENCES consent_grant(consent_id),
        actor_ref_id TEXT NOT NULL,
        actor_evidence_ref_id TEXT NOT NULL REFERENCES actor_evidence_ref(actor_evidence_ref_id),
        reason_code TEXT NOT NULL CHECK(reason_code='USER_REVOKED'),
        revoked_at TEXT NOT NULL,
        revocation_fingerprint TEXT NOT NULL UNIQUE CHECK(length(revocation_fingerprint)=64)
    )
    """,
    """CREATE UNIQUE INDEX IF NOT EXISTS consent_revocation_one_per_grant
        ON consent_revocation(consent_id)""",
    """CREATE TRIGGER IF NOT EXISTS consent_revocation_no_update
        BEFORE UPDATE ON consent_revocation BEGIN
        SELECT RAISE(ABORT,'consent revocation is append-only'); END""",
    """CREATE TRIGGER IF NOT EXISTS consent_revocation_no_delete
        BEFORE DELETE ON consent_revocation BEGIN
        SELECT RAISE(ABORT,'consent revocation deletion requires Privacy authority'); END""",
    """
    CREATE TABLE IF NOT EXISTS policy_schema_migration (
        version INTEGER PRIMARY KEY,
        schema_fingerprint TEXT NOT NULL,
        applied_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS policy_decision (
        decision_ref_id TEXT PRIMARY KEY,
        schema_version INTEGER NOT NULL CHECK(schema_version=1),
        actor_ref_id TEXT NOT NULL,
        actor_evidence_ref_id TEXT NOT NULL REFERENCES actor_evidence_ref(actor_evidence_ref_id),
        capability TEXT NOT NULL CHECK(capability='canonical_memory.project_codename.mutate'),
        operation TEXT NOT NULL CHECK(operation IN ('CREATE','SUPERSEDE','RESTORE')),
        memory_class TEXT NOT NULL,
        subject_namespace TEXT NOT NULL,
        subject_key TEXT NOT NULL,
        payload_digest TEXT NOT NULL CHECK(length(payload_digest)=64),
        expected_active_revision_id TEXT,
        restore_revision_id TEXT,
        purpose TEXT NOT NULL CHECK(purpose='LONG_TERM_PERSONAL_PROJECT_RECALL'),
        policy_version TEXT NOT NULL,
        decision TEXT NOT NULL CHECK(decision IN ('ALLOWED','DENIED')),
        action_digest TEXT NOT NULL CHECK(length(action_digest)=64),
        created_at TEXT NOT NULL,
        decision_fingerprint TEXT NOT NULL CHECK(length(decision_fingerprint)=64)
    )
    """,
    """CREATE UNIQUE INDEX IF NOT EXISTS policy_decision_fingerprint
        ON policy_decision(decision_fingerprint)""",
    """CREATE UNIQUE INDEX IF NOT EXISTS policy_decision_action
        ON policy_decision(actor_evidence_ref_id,capability,action_digest,policy_version)""",
    """CREATE TRIGGER IF NOT EXISTS policy_decision_no_update
        BEFORE UPDATE ON policy_decision BEGIN
        SELECT RAISE(ABORT,'Policy decision is immutable'); END""",
    """CREATE TRIGGER IF NOT EXISTS policy_decision_no_delete
        BEFORE DELETE ON policy_decision BEGIN
        SELECT RAISE(ABORT,'Policy decision deletion requires Privacy authority'); END""",
    """
    CREATE TABLE IF NOT EXISTS rollback_schema_migration (
        version INTEGER PRIMARY KEY,
        schema_fingerprint TEXT NOT NULL,
        applied_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS rollback_authorization (
        rollback_authorization_ref_id TEXT PRIMARY KEY,
        schema_version INTEGER NOT NULL CHECK(schema_version=1),
        authority TEXT NOT NULL CHECK(authority='USER_ROLLBACK_AUTHORITY_V1'),
        actor_ref_id TEXT NOT NULL,
        actor_evidence_ref_id TEXT NOT NULL REFERENCES actor_evidence_ref(actor_evidence_ref_id),
        consent_ref_id TEXT NOT NULL REFERENCES consent_grant(consent_id),
        memory_item_id TEXT NOT NULL,
        memory_class TEXT NOT NULL,
        subject_namespace TEXT NOT NULL,
        subject_key TEXT NOT NULL,
        expected_active_revision_id TEXT NOT NULL,
        restore_revision_id TEXT NOT NULL,
        target_value_digest TEXT NOT NULL CHECK(length(target_value_digest)=64),
        operation TEXT NOT NULL CHECK(operation='RESTORE'),
        purpose TEXT NOT NULL CHECK(purpose='LONG_TERM_PERSONAL_PROJECT_RECALL'),
        confirmation_event_ref TEXT NOT NULL,
        action_digest TEXT NOT NULL CHECK(length(action_digest)=64),
        authorized_at TEXT NOT NULL,
        authorization_fingerprint TEXT NOT NULL CHECK(length(authorization_fingerprint)=64)
    )
    """,
    """CREATE UNIQUE INDEX IF NOT EXISTS rollback_authorization_fingerprint
        ON rollback_authorization(authorization_fingerprint)""",
    """
    CREATE TABLE IF NOT EXISTS rollback_consumption (
        rollback_authorization_ref_id TEXT PRIMARY KEY
            REFERENCES rollback_authorization(rollback_authorization_ref_id),
        action_digest TEXT NOT NULL CHECK(length(action_digest)=64),
        consumed_at TEXT NOT NULL,
        consumer_ref TEXT NOT NULL
    )
    """,
    """CREATE TRIGGER IF NOT EXISTS rollback_authorization_no_update
        BEFORE UPDATE ON rollback_authorization BEGIN
        SELECT RAISE(ABORT,'rollback authorization is immutable'); END""",
    """CREATE TRIGGER IF NOT EXISTS rollback_authorization_no_delete
        BEFORE DELETE ON rollback_authorization BEGIN
        SELECT RAISE(ABORT,'rollback authorization deletion requires Privacy authority'); END""",
    """CREATE TRIGGER IF NOT EXISTS rollback_consumption_no_update
        BEFORE UPDATE ON rollback_consumption BEGIN
        SELECT RAISE(ABORT,'rollback consumption is immutable'); END""",
    """CREATE TRIGGER IF NOT EXISTS rollback_consumption_no_delete
        BEFORE DELETE ON rollback_consumption BEGIN
        SELECT RAISE(ABORT,'rollback consumption deletion requires Privacy authority'); END""",
)


class AuthorityError(RuntimeError):
    code = INVALID


class ActorEvidenceError(AuthorityError):
    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


class ConsentError(AuthorityError):
    pass


class PolicyError(AuthorityError):
    pass


class RollbackError(AuthorityError):
    pass


def utc_now(value: Optional[datetime] = None) -> str:
    stamp = value or datetime.now(timezone.utc)
    if stamp.tzinfo is None:
        stamp = stamp.replace(tzinfo=timezone.utc)
    return stamp.astimezone(timezone.utc).isoformat(timespec="microseconds").replace(
        "+00:00", "Z"
    )


def parse_time(value: str) -> datetime:
    try:
        stamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (TypeError, ValueError) as exc:
        raise AuthorityError("invalid authority timestamp") from exc
    if stamp.tzinfo is None:
        raise AuthorityError("authority timestamp must be timezone-aware")
    return stamp.astimezone(timezone.utc)


def _hmac_digest(secret: bytes, value: Dict[str, Any]) -> str:
    return hmac.new(
        secret, C.canonical_json(value).encode("ascii"), hashlib.sha256
    ).hexdigest()


def load_owner_only_secret(path: Path) -> bytes:
    """Load a server-only key without logging it or accepting weak permissions."""
    target = Path(path)
    data = target.read_bytes()
    if len(data) < 32:
        raise AuthorityError("authority secret is too short")
    if os.name != "nt" and stat.S_IMODE(target.stat().st_mode) != 0o600:
        raise AuthorityError("authority secret must be mode 0600")
    return data


def create_owner_only_secret(path: Path) -> None:
    """Provision a new key; never overwrite or return secret material."""
    target = Path(path)
    if target.exists():
        load_owner_only_secret(target)
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    fd = os.open(str(target), flags, 0o600)
    try:
        os.write(fd, secrets.token_bytes(32))
        os.fsync(fd)
    finally:
        os.close(fd)
    try:
        os.chmod(target, 0o600)
    except OSError:
        pass


def _authorizer(tables: FrozenSet[str], writable: FrozenSet[str]):
    def authorize(
        action: int,
        arg1: Optional[str],
        arg2: Optional[str],
        database: Optional[str],
        trigger: Optional[str],
    ) -> int:
        del arg2, database, trigger
        table = str(arg1 or "")
        if action == sqlite3.SQLITE_READ:
            return sqlite3.SQLITE_OK if table in (tables | {"sqlite_master"}) else sqlite3.SQLITE_DENY
        if action in {sqlite3.SQLITE_INSERT, sqlite3.SQLITE_UPDATE, sqlite3.SQLITE_DELETE}:
            return sqlite3.SQLITE_OK if table in writable else sqlite3.SQLITE_DENY
        if action in {
            sqlite3.SQLITE_CREATE_INDEX,
            sqlite3.SQLITE_CREATE_TABLE,
            sqlite3.SQLITE_CREATE_TRIGGER,
            sqlite3.SQLITE_CREATE_VIEW,
            sqlite3.SQLITE_DROP_INDEX,
            sqlite3.SQLITE_DROP_TABLE,
            sqlite3.SQLITE_DROP_TRIGGER,
            sqlite3.SQLITE_DROP_VIEW,
            sqlite3.SQLITE_ALTER_TABLE,
            sqlite3.SQLITE_REINDEX,
        }:
            return sqlite3.SQLITE_DENY
        return sqlite3.SQLITE_OK

    return authorize


def _connect(path: Path, tables: FrozenSet[str], writable: FrozenSet[str]) -> sqlite3.Connection:
    if not Path(path).is_file():
        raise AuthorityError("authority database is unavailable")
    conn = sqlite3.connect(str(path), timeout=5.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA busy_timeout=5000")
    existing = {
        str(row[0])
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        )
    }
    if not tables.issubset(existing):
        conn.close()
        raise AuthorityError("authority schema is unavailable")
    conn.set_authorizer(_authorizer(tables, writable))
    return conn


@dataclass(frozen=True)
class AuthorityResolution:
    status: str
    reference_id: Optional[str] = None
    failure_code: Optional[str] = None


@dataclass(frozen=True)
class ConsentChallengeV1:
    schema_version: int
    challenge_id: str
    actor_evidence_ref_id: str
    policy_decision_ref_id: str
    action: C.FrozenMemoryActionV1
    created_at: str
    expires_at: str


class LocalOwnerAuthority:
    """HMAC-backed, request/action-bound proof for the owner-controlled Home seam."""

    ACTOR = C.ActorRefV1(
        schema_version=1,
        actor_ref_id="actor.local-owner.v1",
        actor_id=C.LOCAL_OWNER_ACTOR_ID,
        authority=C.LOCAL_OWNER_AUTHORITY_V1,
        assurance=C.OWNER_CONTROLLED_HOME_CONTEXT,
    )

    def __init__(
        self,
        path: Path,
        secret: bytes,
        *,
        issuer_ref: str = "lilith-os-home-server",
        now_fn: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
    ):
        if len(secret) < 32:
            raise ValueError("actor authority secret must be at least 32 bytes")
        C.require_id(issuer_ref, "issuerRef")
        self.path = Path(path)
        self._secret = bytes(secret)
        self.issuer_ref = issuer_ref
        self.now_fn = now_fn
        self.ACTOR.validate()

    @classmethod
    def from_secret_file(cls, path: Path, secret_path: Path, **kwargs: Any):
        return cls(path, load_owner_only_secret(secret_path), **kwargs)

    def _connect(self) -> sqlite3.Connection:
        return _connect(
            self.path,
            ACTOR_TABLES,
            frozenset({"actor_evidence_ref", "actor_evidence_consumption"}),
        )

    def issue(
        self,
        *,
        action: C.FrozenMemoryActionV1,
        request_digest: str,
        nonce: Optional[str] = None,
        ttl_seconds: int = DEFAULT_EVIDENCE_TTL_SECONDS,
    ) -> C.ActorEvidenceRefV1:
        """Issue server-side evidence; no browser/session field can mint authority."""
        action.validate()
        if action.actor_ref_id != self.ACTOR.actor_ref_id:
            raise ActorEvidenceError(C.ACTOR_UNRESOLVED)
        C.require_digest(request_digest, "requestDigest")
        if isinstance(ttl_seconds, bool) or not 1 <= int(ttl_seconds) <= 300:
            raise ValueError("actor evidence TTL is outside the approved bound")
        now = self.now_fn().astimezone(timezone.utc)
        nonce_value = nonce or ("nonce." + uuid.uuid4().hex)
        C.require_id(nonce_value, "nonce")
        ref_id = "ae." + uuid.uuid4().hex
        issued = utc_now(now)
        expires = utc_now(now + timedelta(seconds=int(ttl_seconds)))
        unsigned = C.ActorEvidenceRefV1(
            schema_version=1,
            actor_evidence_ref_id=ref_id,
            actor_ref_id=self.ACTOR.actor_ref_id,
            authority=C.LOCAL_OWNER_AUTHORITY_V1,
            request_digest=request_digest,
            action_digest=action.action_digest,
            nonce=nonce_value,
            issued_at=issued,
            expires_at=expires,
            issuer_ref=self.issuer_ref,
            evidence_fingerprint="0" * 64,
        )
        fingerprint = _hmac_digest(self._secret, unsigned.fingerprint_dict())
        evidence = C.ActorEvidenceRefV1(
            **{**unsigned.__dict__, "evidence_fingerprint": fingerprint}
        )
        evidence.validate_shape()
        conn = self._connect()
        try:
            conn.execute(
                "INSERT INTO actor_evidence_ref VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (
                    evidence.actor_evidence_ref_id,
                    evidence.schema_version,
                    evidence.actor_ref_id,
                    evidence.authority,
                    evidence.request_digest,
                    evidence.action_digest,
                    evidence.nonce,
                    evidence.issued_at,
                    evidence.expires_at,
                    evidence.issuer_ref,
                    evidence.evidence_fingerprint,
                ),
            )
            conn.commit()
        finally:
            conn.close()
        return evidence

    @staticmethod
    def _from_row(row: sqlite3.Row) -> C.ActorEvidenceRefV1:
        return C.ActorEvidenceRefV1(
            schema_version=int(row["schema_version"]),
            actor_evidence_ref_id=str(row["actor_evidence_ref_id"]),
            actor_ref_id=str(row["actor_ref_id"]),
            authority=str(row["authority"]),
            request_digest=str(row["request_digest"]),
            action_digest=str(row["action_digest"]),
            nonce=str(row["nonce"]),
            issued_at=str(row["issued_at"]),
            expires_at=str(row["expires_at"]),
            issuer_ref=str(row["issuer_ref"]),
            evidence_fingerprint=str(row["evidence_fingerprint"]),
        )

    def validate_existing(
        self,
        reference_id: str,
        *,
        action: C.FrozenMemoryActionV1,
        request_digest: Optional[str] = None,
        require_consumed: bool = False,
    ) -> C.ActorEvidenceRefV1:
        action.validate()
        if request_digest is not None:
            C.require_digest(request_digest, "requestDigest")
        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT * FROM actor_evidence_ref WHERE actor_evidence_ref_id=?",
                (reference_id,),
            ).fetchone()
            if row is None:
                raise ActorEvidenceError(C.ACTOR_UNRESOLVED)
            evidence = self._from_row(row)
            evidence.validate_shape()
            expected = _hmac_digest(self._secret, evidence.fingerprint_dict())
            if not hmac.compare_digest(expected, evidence.evidence_fingerprint):
                raise ActorEvidenceError(C.ACTOR_EVIDENCE_INVALID)
            if (
                evidence.actor_ref_id != action.actor_ref_id
                or evidence.action_digest != action.action_digest
                or (request_digest is not None and evidence.request_digest != request_digest)
            ):
                raise ActorEvidenceError(C.ACTOR_EVIDENCE_INVALID)
            now = self.now_fn().astimezone(timezone.utc)
            if now < parse_time(evidence.issued_at) - timedelta(seconds=5):
                raise ActorEvidenceError(C.ACTOR_EVIDENCE_INVALID)
            if now >= parse_time(evidence.expires_at):
                raise ActorEvidenceError(C.ACTOR_EVIDENCE_EXPIRED)
            if require_consumed:
                consumed = conn.execute(
                    "SELECT action_digest FROM actor_evidence_consumption "
                    "WHERE actor_evidence_ref_id=?",
                    (reference_id,),
                ).fetchone()
                if consumed is None or str(consumed[0]) != action.action_digest:
                    raise ActorEvidenceError(C.ACTOR_UNRESOLVED)
            return evidence
        finally:
            conn.close()

    def resolve_and_consume(
        self,
        reference_id: str,
        *,
        action: C.FrozenMemoryActionV1,
        consumer_ref: str,
    ) -> AuthorityResolution:
        C.require_id(consumer_ref, "consumerRef")
        try:
            evidence = self.validate_existing(reference_id, action=action)
            conn = self._connect()
            try:
                conn.execute("BEGIN IMMEDIATE")
                conn.execute(
                    "INSERT INTO actor_evidence_consumption VALUES (?,?,?,?)",
                    (
                        reference_id,
                        action.action_digest,
                        utc_now(self.now_fn()),
                        consumer_ref,
                    ),
                )
                conn.commit()
            except sqlite3.IntegrityError as exc:
                conn.rollback()
                raise ActorEvidenceError(C.ACTOR_EVIDENCE_REPLAYED) from exc
            finally:
                conn.close()
            return AuthorityResolution(CONFIRMED, evidence.actor_evidence_ref_id)
        except ActorEvidenceError as exc:
            return AuthorityResolution(INVALID, reference_id, exc.code)


class ConsentStore:
    """Payload-, purpose-, operation-, actor-, and revision-bound Consent owner."""

    def __init__(
        self,
        path: Path,
        actor_authority: LocalOwnerAuthority,
        *,
        policy_store: Optional[Any] = None,
        now_fn: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
        challenge_ttl_seconds: int = DEFAULT_CHALLENGE_TTL_SECONDS,
    ):
        if not 30 <= int(challenge_ttl_seconds) <= 600:
            raise ValueError("challenge TTL is outside the approved bound")
        self.path = Path(path)
        self.actor_authority = actor_authority
        self.policy_store = policy_store
        self.now_fn = now_fn
        self.challenge_ttl_seconds = int(challenge_ttl_seconds)
        self._challenges: Dict[str, ConsentChallengeV1] = {}

    def _connect(self) -> sqlite3.Connection:
        return _connect(
            self.path,
            CONSENT_TABLES | frozenset({"actor_evidence_ref"}),
            frozenset({"consent_grant", "consent_revocation"}),
        )

    def create_challenge(
        self,
        *,
        action: C.FrozenMemoryActionV1,
        actor_evidence_ref_id: str,
        policy_decision_ref_id: str,
    ) -> ConsentChallengeV1:
        action.validate()
        if action.operation not in C.MEMORY_MUTATIONS:
            raise ConsentError("consent challenge operation is unsupported")
        C.require_id(actor_evidence_ref_id, "actorEvidenceRefId")
        C.require_id(policy_decision_ref_id, "policyDecisionRefId")
        if self.policy_store is None:
            raise ConsentError("Policy decision resolver is unavailable")
        policy = self.policy_store.resolve(
            policy_decision_ref_id,
            action=action,
            capability=C.CANONICAL_MEMORY_PROJECT_CODENAME_MUTATE,
        )
        if policy.status != CONFIRMED:
            raise ConsentError("Policy denied action before confirmation")
        now = self.now_fn().astimezone(timezone.utc)
        challenge = ConsentChallengeV1(
            schema_version=1,
            challenge_id="cc." + uuid.uuid4().hex,
            actor_evidence_ref_id=actor_evidence_ref_id,
            policy_decision_ref_id=policy_decision_ref_id,
            action=action,
            created_at=utc_now(now),
            expires_at=utc_now(now + timedelta(seconds=self.challenge_ttl_seconds)),
        )
        self._challenges[challenge.challenge_id] = challenge
        return challenge

    def cancel_challenge(self, challenge_id: str) -> None:
        self._challenges.pop(challenge_id, None)

    def confirm(
        self,
        challenge_id: str,
        *,
        action: C.FrozenMemoryActionV1,
        issuer_ref: str,
        intent_ref_id: str,
        privacy_notice_version: str,
    ) -> C.ConsentRefV1:
        challenge = self._challenges.pop(challenge_id, None)
        if challenge is None:
            raise ConsentError("consent challenge is unavailable")
        now = self.now_fn().astimezone(timezone.utc)
        if now >= parse_time(challenge.expires_at):
            raise ConsentError("consent challenge expired")
        if challenge.action.action_digest != action.action_digest:
            raise ConsentError("consent challenge action changed")
        if self.policy_store is None or self.policy_store.resolve(
            challenge.policy_decision_ref_id,
            action=action,
            capability=C.CANONICAL_MEMORY_PROJECT_CODENAME_MUTATE,
        ).status != CONFIRMED:
            raise ConsentError("Policy decision is no longer valid")
        self.actor_authority.validate_existing(
            challenge.actor_evidence_ref_id,
            action=action,
            require_consumed=True,
        )
        semantics = C.consent_semantics(
            action,
            actor_evidence_ref_id=challenge.actor_evidence_ref_id,
            issuer_ref=issuer_ref,
            intent_ref_id=intent_ref_id,
            privacy_notice_version=privacy_notice_version,
        )
        consent = C.ConsentRefV1(
            schema_version=1,
            consent_id="consent." + uuid.uuid4().hex,
            authority=C.LOCAL_CONSENT_AUTHORITY_V1,
            actor_ref_id=action.actor_ref_id,
            actor_evidence_ref_id=challenge.actor_evidence_ref_id,
            memory_class=action.memory_class,
            subject_namespace=action.subject_namespace,
            subject_key=action.subject_key,
            operation=action.operation,
            payload_digest=action.payload_digest,
            expected_active_revision_id=action.expected_active_revision_id,
            restore_revision_id=action.restore_revision_id,
            purpose=action.purpose,
            granted_at=utc_now(now),
            issuer_type=C.USER_CONFIRMATION,
            issuer_ref=issuer_ref,
            intent_ref_id=intent_ref_id,
            privacy_notice_version=privacy_notice_version,
            action_digest=action.action_digest,
            consent_fingerprint=C.sha256_digest(semantics),
        )
        consent.validate_shape()
        conn = self._connect()
        try:
            conn.execute(
                "INSERT INTO consent_grant VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    consent.consent_id,
                    consent.schema_version,
                    consent.authority,
                    consent.actor_ref_id,
                    consent.actor_evidence_ref_id,
                    consent.memory_class,
                    consent.subject_namespace,
                    consent.subject_key,
                    consent.operation,
                    consent.payload_digest,
                    consent.expected_active_revision_id,
                    consent.restore_revision_id,
                    consent.purpose,
                    consent.granted_at,
                    consent.issuer_type,
                    consent.issuer_ref,
                    consent.intent_ref_id,
                    consent.privacy_notice_version,
                    consent.action_digest,
                    consent.consent_fingerprint,
                ),
            )
            conn.commit()
        finally:
            conn.close()
        return consent

    @staticmethod
    def _from_row(row: sqlite3.Row) -> C.ConsentRefV1:
        return C.ConsentRefV1(**{
            "schema_version": int(row["schema_version"]),
            "consent_id": str(row["consent_id"]),
            "authority": str(row["authority"]),
            "actor_ref_id": str(row["actor_ref_id"]),
            "actor_evidence_ref_id": str(row["actor_evidence_ref_id"]),
            "memory_class": str(row["memory_class"]),
            "subject_namespace": str(row["subject_namespace"]),
            "subject_key": str(row["subject_key"]),
            "operation": str(row["operation"]),
            "payload_digest": str(row["payload_digest"]),
            "expected_active_revision_id": row["expected_active_revision_id"],
            "restore_revision_id": row["restore_revision_id"],
            "purpose": str(row["purpose"]),
            "granted_at": str(row["granted_at"]),
            "issuer_type": str(row["issuer_type"]),
            "issuer_ref": str(row["issuer_ref"]),
            "intent_ref_id": str(row["intent_ref_id"]),
            "privacy_notice_version": str(row["privacy_notice_version"]),
            "action_digest": str(row["action_digest"]),
            "consent_fingerprint": str(row["consent_fingerprint"]),
        })

    def resolve(
        self,
        reference_id: str,
        *,
        action: C.FrozenMemoryActionV1,
        intent_ref_id: Optional[str] = None,
        actor_evidence_ref_id: Optional[str] = None,
    ) -> AuthorityResolution:
        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT * FROM consent_grant WHERE consent_id=?", (reference_id,)
            ).fetchone()
            if row is None:
                return AuthorityResolution(INVALID, reference_id, "CONSENT_INVALID")
            if conn.execute(
                "SELECT 1 FROM consent_revocation WHERE consent_id=?", (reference_id,)
            ).fetchone():
                return AuthorityResolution(REVOKED, reference_id, "CONSENT_REVOKED")
            consent = self._from_row(row)
            try:
                consent.validate_shape()
            except C.ContractError:
                return AuthorityResolution(INVALID, reference_id, "CONSENT_INVALID")
            semantics = C.consent_semantics(
                action,
                actor_evidence_ref_id=consent.actor_evidence_ref_id,
                issuer_ref=consent.issuer_ref,
                intent_ref_id=consent.intent_ref_id,
                privacy_notice_version=consent.privacy_notice_version,
            )
            exact = (
                consent.action_digest == action.action_digest
                and consent.consent_fingerprint == C.sha256_digest(semantics)
                and (intent_ref_id is None or consent.intent_ref_id == intent_ref_id)
                and (
                    actor_evidence_ref_id is None
                    or consent.actor_evidence_ref_id == actor_evidence_ref_id
                )
            )
            return AuthorityResolution(
                CONFIRMED if exact else INVALID,
                reference_id,
                None if exact else "CONSENT_INVALID",
            )
        finally:
            conn.close()

    def resolve_revision(
        self,
        reference_id: str,
        *,
        memory_class: str,
        subject_namespace: str,
        subject_key: str,
        payload_digest: str,
    ) -> AuthorityResolution:
        """Resolve read authority without reconstructing mutation preconditions."""
        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT memory_class,subject_namespace,subject_key,payload_digest "
                "FROM consent_grant WHERE consent_id=?",
                (reference_id,),
            ).fetchone()
            if row is None:
                return AuthorityResolution(INVALID, reference_id, "CONSENT_INVALID")
            if conn.execute(
                "SELECT 1 FROM consent_revocation WHERE consent_id=?", (reference_id,)
            ).fetchone():
                return AuthorityResolution(REVOKED, reference_id, "CONSENT_REVOKED")
            exact = tuple(row) == (
                memory_class,
                subject_namespace,
                subject_key,
                payload_digest,
            )
            return AuthorityResolution(
                CONFIRMED if exact else INVALID,
                reference_id,
                None if exact else "CONSENT_INVALID",
            )
        finally:
            conn.close()

    def revoke(
        self,
        consent_id: str,
        *,
        actor_evidence_ref_id: str,
        action: C.FrozenMemoryActionV1,
    ) -> str:
        resolved = self.resolve(consent_id, action=action)
        if resolved.status != CONFIRMED:
            raise ConsentError("only an active exact consent may be revoked")
        self.actor_authority.validate_existing(
            actor_evidence_ref_id, action=action, require_consumed=True
        )
        revocation_id = "revoke." + uuid.uuid4().hex
        revoked_at = utc_now(self.now_fn())
        fingerprint = C.sha256_digest({
            "consentId": consent_id,
            "actorRefId": action.actor_ref_id,
            "actorEvidenceRefId": actor_evidence_ref_id,
            "reasonCode": "USER_REVOKED",
        })
        conn = self._connect()
        try:
            conn.execute(
                "INSERT INTO consent_revocation VALUES (?,?,?,?,?,?,?)",
                (
                    revocation_id,
                    consent_id,
                    action.actor_ref_id,
                    actor_evidence_ref_id,
                    "USER_REVOKED",
                    revoked_at,
                    fingerprint,
                ),
            )
            conn.commit()
        finally:
            conn.close()
        return revocation_id


class MemoryPolicyStore:
    """Policy-owned durable decision extension re-exported by ``policy.py``."""

    def __init__(
        self,
        path: Path,
        actor_authority: LocalOwnerAuthority,
        *,
        active_capabilities: FrozenSet[str] = frozenset(),
        now_fn: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
    ):
        unknown = set(active_capabilities) - {
            C.CANONICAL_MEMORY_PROJECT_CODENAME_MUTATE
        }
        if unknown:
            raise ValueError("unknown Policy capability")
        self.path = Path(path)
        self.actor_authority = actor_authority
        self.active_capabilities = frozenset(active_capabilities)
        self.now_fn = now_fn

    def _connect(self) -> sqlite3.Connection:
        return _connect(
            self.path,
            POLICY_TABLES | frozenset({"actor_evidence_ref"}),
            frozenset({"policy_decision"}),
        )

    def decide(
        self,
        *,
        action: C.FrozenMemoryActionV1,
        actor_evidence_ref_id: str,
        capability: str,
    ) -> C.PolicyDecisionRefV1:
        action.validate()
        if action.operation not in C.MEMORY_MUTATIONS:
            raise PolicyError("Policy mutation operation is unsupported")
        if capability != C.CANONICAL_MEMORY_PROJECT_CODENAME_MUTATE:
            raise PolicyError("unknown Policy capability")
        actor = self.actor_authority.resolve_and_consume(
            actor_evidence_ref_id,
            action=action,
            consumer_ref="policy.canonical-memory.v1",
        )
        decision_value = (
            ALLOWED
            if actor.status == CONFIRMED and capability in self.active_capabilities
            else DENIED
        )
        semantic = {
            **action.semantic_dict(),
            "actorEvidenceRefId": actor_evidence_ref_id,
            "capability": capability,
            "policyVersion": POLICY_VERSION,
            "decision": decision_value,
            "actionDigest": action.action_digest,
        }
        decision = C.PolicyDecisionRefV1(
            schema_version=1,
            decision_ref_id="policy." + uuid.uuid4().hex,
            actor_ref_id=action.actor_ref_id,
            actor_evidence_ref_id=actor_evidence_ref_id,
            capability=capability,
            operation=action.operation,
            memory_class=action.memory_class,
            subject_namespace=action.subject_namespace,
            subject_key=action.subject_key,
            payload_digest=action.payload_digest,
            expected_active_revision_id=action.expected_active_revision_id,
            restore_revision_id=action.restore_revision_id,
            purpose=action.purpose,
            policy_version=POLICY_VERSION,
            decision=decision_value,
            action_digest=action.action_digest,
            created_at=utc_now(self.now_fn()),
            decision_fingerprint=C.sha256_digest(semantic),
        )
        decision.validate_shape()
        conn = self._connect()
        try:
            conn.execute(
                "INSERT INTO policy_decision VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    decision.decision_ref_id,
                    decision.schema_version,
                    decision.actor_ref_id,
                    decision.actor_evidence_ref_id,
                    decision.capability,
                    decision.operation,
                    decision.memory_class,
                    decision.subject_namespace,
                    decision.subject_key,
                    decision.payload_digest,
                    decision.expected_active_revision_id,
                    decision.restore_revision_id,
                    decision.purpose,
                    decision.policy_version,
                    decision.decision,
                    decision.action_digest,
                    decision.created_at,
                    decision.decision_fingerprint,
                ),
            )
            conn.commit()
        finally:
            conn.close()
        return decision

    @staticmethod
    def _from_row(row: sqlite3.Row) -> C.PolicyDecisionRefV1:
        values = dict(row)
        values["schema_version"] = int(values["schema_version"])
        return C.PolicyDecisionRefV1(**values)

    def resolve(
        self,
        reference_id: str,
        *,
        action: C.FrozenMemoryActionV1,
        capability: str,
    ) -> AuthorityResolution:
        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT * FROM policy_decision WHERE decision_ref_id=?",
                (reference_id,),
            ).fetchone()
            if row is None:
                return AuthorityResolution(INVALID, reference_id, "POLICY_DECISION_INVALID")
            decision = self._from_row(row)
            try:
                decision.validate_shape()
            except C.ContractError:
                return AuthorityResolution(INVALID, reference_id, "POLICY_DECISION_INVALID")
            semantic = {
                **action.semantic_dict(),
                "actorEvidenceRefId": decision.actor_evidence_ref_id,
                "capability": capability,
                "policyVersion": decision.policy_version,
                "decision": decision.decision,
                "actionDigest": action.action_digest,
            }
            exact = (
                decision.capability == capability
                and decision.action_digest == action.action_digest
                and decision.decision == ALLOWED
                and decision.decision_fingerprint == C.sha256_digest(semantic)
            )
            return AuthorityResolution(
                CONFIRMED if exact else INVALID,
                reference_id,
                None if exact else "POLICY_DECISION_INVALID",
            )
        finally:
            conn.close()


class RollbackAuthority:
    """Separate, single-use RESTORE authorization owner."""

    def __init__(
        self,
        path: Path,
        actor_authority: LocalOwnerAuthority,
        consent_store: ConsentStore,
        *,
        now_fn: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
    ):
        self.path = Path(path)
        self.actor_authority = actor_authority
        self.consent_store = consent_store
        self.now_fn = now_fn

    def _connect(self) -> sqlite3.Connection:
        return _connect(
            self.path,
            ROLLBACK_TABLES | frozenset({"actor_evidence_ref", "consent_grant"}),
            frozenset({"rollback_authorization", "rollback_consumption"}),
        )

    def authorize(
        self,
        *,
        action: C.FrozenMemoryActionV1,
        actor_evidence_ref_id: str,
        consent_ref_id: str,
        memory_item_id: str,
        confirmation_event_ref: str,
    ) -> C.RollbackAuthorizationRefV1:
        action.validate()
        if action.operation != C.RESTORE:
            raise RollbackError("rollback authority is RESTORE-only")
        self.actor_authority.validate_existing(
            actor_evidence_ref_id, action=action, require_consumed=True
        )
        if self.consent_store.resolve(consent_ref_id, action=action).status != CONFIRMED:
            raise RollbackError("rollback requires exact active Consent")
        semantic = {
            **action.semantic_dict(),
            "actorEvidenceRefId": actor_evidence_ref_id,
            "consentRefId": consent_ref_id,
            "memoryItemId": memory_item_id,
            "confirmationEventRef": confirmation_event_ref,
            "authority": C.USER_ROLLBACK_AUTHORITY_V1,
            "actionDigest": action.action_digest,
        }
        authorization = C.RollbackAuthorizationRefV1(
            schema_version=1,
            rollback_authorization_ref_id="rollback." + uuid.uuid4().hex,
            authority=C.USER_ROLLBACK_AUTHORITY_V1,
            actor_ref_id=action.actor_ref_id,
            actor_evidence_ref_id=actor_evidence_ref_id,
            consent_ref_id=consent_ref_id,
            memory_item_id=memory_item_id,
            memory_class=action.memory_class,
            subject_namespace=action.subject_namespace,
            subject_key=action.subject_key,
            expected_active_revision_id=str(action.expected_active_revision_id),
            restore_revision_id=str(action.restore_revision_id),
            target_value_digest=action.payload_digest,
            operation=C.RESTORE,
            purpose=action.purpose,
            confirmation_event_ref=confirmation_event_ref,
            action_digest=action.action_digest,
            authorized_at=utc_now(self.now_fn()),
            authorization_fingerprint=C.sha256_digest(semantic),
        )
        authorization.validate_shape()
        conn = self._connect()
        try:
            conn.execute(
                "INSERT INTO rollback_authorization VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    authorization.rollback_authorization_ref_id,
                    authorization.schema_version,
                    authorization.authority,
                    authorization.actor_ref_id,
                    authorization.actor_evidence_ref_id,
                    authorization.consent_ref_id,
                    authorization.memory_item_id,
                    authorization.memory_class,
                    authorization.subject_namespace,
                    authorization.subject_key,
                    authorization.expected_active_revision_id,
                    authorization.restore_revision_id,
                    authorization.target_value_digest,
                    authorization.operation,
                    authorization.purpose,
                    authorization.confirmation_event_ref,
                    authorization.action_digest,
                    authorization.authorized_at,
                    authorization.authorization_fingerprint,
                ),
            )
            conn.commit()
        finally:
            conn.close()
        return authorization

    @staticmethod
    def _from_row(row: sqlite3.Row) -> C.RollbackAuthorizationRefV1:
        values = dict(row)
        values["schema_version"] = int(values["schema_version"])
        return C.RollbackAuthorizationRefV1(**values)

    def resolve_and_consume(
        self,
        reference_id: str,
        *,
        action: C.FrozenMemoryActionV1,
        memory_item_id: str,
        consumer_ref: str,
    ) -> AuthorityResolution:
        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT * FROM rollback_authorization "
                "WHERE rollback_authorization_ref_id=?",
                (reference_id,),
            ).fetchone()
            if row is None:
                return AuthorityResolution(INVALID, reference_id, "ROLLBACK_NOT_AUTHORIZED")
            authorization = self._from_row(row)
            try:
                authorization.validate_shape()
            except C.ContractError:
                return AuthorityResolution(INVALID, reference_id, "ROLLBACK_NOT_AUTHORIZED")
            semantic = {
                **action.semantic_dict(),
                "actorEvidenceRefId": authorization.actor_evidence_ref_id,
                "consentRefId": authorization.consent_ref_id,
                "memoryItemId": memory_item_id,
                "confirmationEventRef": authorization.confirmation_event_ref,
                "authority": C.USER_ROLLBACK_AUTHORITY_V1,
                "actionDigest": action.action_digest,
            }
            exact = (
                authorization.action_digest == action.action_digest
                and authorization.memory_item_id == memory_item_id
                and authorization.authorization_fingerprint == C.sha256_digest(semantic)
            )
            if not exact:
                return AuthorityResolution(INVALID, reference_id, "ROLLBACK_NOT_AUTHORIZED")
            try:
                conn.execute("BEGIN IMMEDIATE")
                conn.execute(
                    "INSERT INTO rollback_consumption VALUES (?,?,?,?)",
                    (
                        reference_id,
                        action.action_digest,
                        utc_now(self.now_fn()),
                        consumer_ref,
                    ),
                )
                conn.commit()
            except sqlite3.IntegrityError:
                conn.rollback()
                return AuthorityResolution(INVALID, reference_id, "ROLLBACK_REPLAYED")
            return AuthorityResolution(CONFIRMED, reference_id)
        finally:
            conn.close()


class _AuthorityPrivacyErasureOwner:
    """Base for exact Privacy-owned deletion without widening runtime stores."""

    OWNER = ""
    TRIGGERS: Tuple[str, ...] = ()

    def __init__(self, path: Path, privacy_authority: Any):
        self.path = Path(path)
        self.privacy_authority = privacy_authority

    def _authorization(self, authorization_ref_id: str, execution_nonce: str) -> Any:
        authorization = self.privacy_authority.resolve_erasure_authorization(
            authorization_ref_id,
            owner=self.OWNER,
            execution_nonce=execution_nonce,
        )
        if authorization is None:
            raise PermissionError("PRIVACY_ERASURE_NOT_AUTHORIZED")
        return authorization

    @staticmethod
    def _trigger_sql(conn: sqlite3.Connection, names: Tuple[str, ...]) -> Dict[str, str]:
        if not names:
            return {}
        rows = conn.execute(
            "SELECT name,sql FROM sqlite_master WHERE type='trigger' AND name IN (%s)"
            % ",".join("?" for _ in names),
            names,
        )
        values = {str(row[0]): str(row[1]) for row in rows}
        if set(values) != set(names):
            raise RuntimeError(f"{names!r} immutability trigger set is incomplete")
        return values

    def _record(
        self,
        authorization_ref_id: str,
        execution_nonce: str,
        deleted: int,
        **transient: Any,
    ) -> Dict[str, Any]:
        result = {
            "owner": self.OWNER,
            "status": "COMPLETE",
            "deleted": int(deleted),
            **transient,
        }
        self.privacy_authority.record_owner_result(
            authorization_ref_id, execution_nonce, result
        )
        return result


class PolicyPrivacyErasureOwner(_AuthorityPrivacyErasureOwner):
    OWNER = "POLICY"
    TRIGGERS = ("policy_decision_no_delete",)

    def erase_authorized(self, authorization_ref_id: str, execution_nonce: str) -> Dict[str, Any]:
        authorization = self._authorization(authorization_ref_id, execution_nonce)
        conn = sqlite3.connect(str(self.path), timeout=5.0)
        try:
            conn.execute("PRAGMA foreign_keys=ON")
            conn.execute("PRAGMA secure_delete=ON")
            conn.execute("BEGIN EXCLUSIVE")
            rows = conn.execute(
                "SELECT decision_ref_id,actor_evidence_ref_id FROM policy_decision "
                "WHERE memory_class=? AND subject_namespace=? AND subject_key=?",
                authorization.identity,
            ).fetchall()
            triggers = self._trigger_sql(conn, self.TRIGGERS)
            for name in self.TRIGGERS:
                conn.execute(f'DROP TRIGGER "{name}"')
            deleted = conn.execute(
                "DELETE FROM policy_decision WHERE memory_class=? AND subject_namespace=? "
                "AND subject_key=?",
                authorization.identity,
            ).rowcount
            for name in self.TRIGGERS:
                conn.execute(triggers[name])
            conn.commit()
            conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
        return self._record(
            authorization_ref_id,
            execution_nonce,
            deleted,
            actorEvidenceRefIds=tuple(str(row[1]) for row in rows),
        )


class RollbackPrivacyErasureOwner(_AuthorityPrivacyErasureOwner):
    OWNER = "ROLLBACK"
    TRIGGERS = (
        "rollback_authorization_no_delete",
        "rollback_consumption_no_delete",
    )

    def erase_authorized(self, authorization_ref_id: str, execution_nonce: str) -> Dict[str, Any]:
        authorization = self._authorization(authorization_ref_id, execution_nonce)
        conn = sqlite3.connect(str(self.path), timeout=5.0)
        try:
            conn.execute("PRAGMA foreign_keys=ON")
            conn.execute("PRAGMA secure_delete=ON")
            conn.execute("BEGIN EXCLUSIVE")
            rows = conn.execute(
                "SELECT rollback_authorization_ref_id,actor_evidence_ref_id "
                "FROM rollback_authorization WHERE memory_class=? "
                "AND subject_namespace=? AND subject_key=?",
                authorization.identity,
            ).fetchall()
            refs = tuple(str(row[0]) for row in rows)
            triggers = self._trigger_sql(conn, self.TRIGGERS)
            for name in self.TRIGGERS:
                conn.execute(f'DROP TRIGGER "{name}"')
            if refs:
                marks = ",".join("?" for _ in refs)
                conn.execute(
                    f"DELETE FROM rollback_consumption WHERE rollback_authorization_ref_id "
                    f"IN ({marks})",
                    refs,
                )
            deleted = 0
            if refs:
                marks = ",".join("?" for _ in refs)
                deleted = conn.execute(
                    f"DELETE FROM rollback_authorization WHERE "
                    f"rollback_authorization_ref_id IN ({marks})",
                    refs,
                ).rowcount
            for name in self.TRIGGERS:
                conn.execute(triggers[name])
            conn.commit()
            conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
        return self._record(
            authorization_ref_id,
            execution_nonce,
            deleted,
            actorEvidenceRefIds=tuple(str(row[1]) for row in rows),
        )


class ConsentPrivacyErasureOwner(_AuthorityPrivacyErasureOwner):
    OWNER = "CONSENT"
    TRIGGERS = (
        "consent_grant_no_delete",
        "consent_revocation_no_delete",
    )

    def erase_authorized(self, authorization_ref_id: str, execution_nonce: str) -> Dict[str, Any]:
        authorization = self._authorization(authorization_ref_id, execution_nonce)
        conn = sqlite3.connect(str(self.path), timeout=5.0)
        try:
            conn.execute("PRAGMA foreign_keys=ON")
            conn.execute("PRAGMA secure_delete=ON")
            conn.execute("BEGIN EXCLUSIVE")
            rows = conn.execute(
                "SELECT consent_id,actor_evidence_ref_id FROM consent_grant "
                "WHERE memory_class=? AND subject_namespace=? AND subject_key=?",
                authorization.identity,
            ).fetchall()
            refs = tuple(str(row[0]) for row in rows)
            triggers = self._trigger_sql(conn, self.TRIGGERS)
            for name in self.TRIGGERS:
                conn.execute(f'DROP TRIGGER "{name}"')
            if refs:
                marks = ",".join("?" for _ in refs)
                conn.execute(
                    f"DELETE FROM consent_revocation WHERE consent_id IN ({marks})",
                    refs,
                )
            deleted = 0
            if refs:
                marks = ",".join("?" for _ in refs)
                deleted = conn.execute(
                    f"DELETE FROM consent_grant WHERE consent_id IN ({marks})",
                    refs,
                ).rowcount
            for name in self.TRIGGERS:
                conn.execute(triggers[name])
            conn.commit()
            conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
        return self._record(
            authorization_ref_id,
            execution_nonce,
            deleted,
            actorEvidenceRefIds=tuple(str(row[1]) for row in rows),
        )


class ActorPrivacyErasureOwner(_AuthorityPrivacyErasureOwner):
    OWNER = "ACTOR_AUTHORITY"
    TRIGGERS = (
        "actor_evidence_ref_no_delete",
        "actor_evidence_consumption_no_delete",
    )

    def erase_authorized(
        self,
        authorization_ref_id: str,
        execution_nonce: str,
        *,
        actor_evidence_ref_ids: Tuple[str, ...],
    ) -> Dict[str, Any]:
        authorization = self._authorization(authorization_ref_id, execution_nonce)
        refs = tuple(sorted(set(actor_evidence_ref_ids) | {authorization.actor_evidence_ref_id}))
        for ref in refs:
            C.require_id(ref, "actorEvidenceRefId")
        conn = sqlite3.connect(str(self.path), timeout=5.0)
        try:
            conn.execute("PRAGMA foreign_keys=ON")
            conn.execute("PRAGMA secure_delete=ON")
            conn.execute("BEGIN EXCLUSIVE")
            triggers = self._trigger_sql(conn, self.TRIGGERS)
            for name in self.TRIGGERS:
                conn.execute(f'DROP TRIGGER "{name}"')
            marks = ",".join("?" for _ in refs)
            conn.execute(
                f"DELETE FROM actor_evidence_consumption WHERE actor_evidence_ref_id IN ({marks})",
                refs,
            )
            deleted = conn.execute(
                f"DELETE FROM actor_evidence_ref WHERE actor_evidence_ref_id IN ({marks})",
                refs,
            ).rowcount
            for name in self.TRIGGERS:
                conn.execute(triggers[name])
            if conn.execute("PRAGMA foreign_key_check").fetchall():
                raise RuntimeError("actor erasure foreign-key check failed")
            conn.commit()
            conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
        return self._record(authorization_ref_id, execution_nonce, deleted)
