"""Separate Slice 15B2a Privacy/Data Governance authority.

Privacy orchestrates exact erasure but does not directly mutate cognitive or
legacy stores.  Each resource owner receives and independently validates the
same HMAC-bound authorization.  A hold and opaque restore-suppression selector
exist before any destructive owner call.
"""

from __future__ import annotations

import hashlib
import hmac
import os
import sqlite3
import stat
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, Optional, Sequence, Tuple

try:
    from . import canonical_contracts as C
    from . import canonical_authority as A
except ImportError:  # deploy-exact flat-directory tests
    import canonical_contracts as C
    import canonical_authority as A


SCHEMA_VERSION = 1
DEFAULT_MAX_BACKUP_RETENTION_DAYS = 30
SCOPE = "CANONICAL_AND_KNOWN_DERIVED_COPIES"
OWNER_SET_V1 = frozenset({
    "L04",
    "L18_V1",
    "L18_V2",
    "ACTOR_AUTHORITY",
    "POLICY",
    "CONSENT",
    "ROLLBACK",
    "LEGACY_MEMORY",
    "LEGACY_SKILLS",
    "PENDING",
})
# F9-C: the Hermes DEV conversation store is a peer erasure owner under this authority (never part of L18_V2). It is
# scope-bound: an authorization may name it only where the governed required-owner floor (schema v2) names it for the
# identity's memory class and namespace, and there it is mandatory. Schema v1 databases accept only OWNER_SET_V1.
HERMES_DEV_CONVERSATION = "HERMES_DEV_CONVERSATION"
SCOPED_OWNERS = frozenset({HERMES_DEV_CONVERSATION})
OWNER_SET = OWNER_SET_V1 | SCOPED_OWNERS
PRIVACY_SCHEMA_V1 = 1
PRIVACY_SCHEMA_V2 = 2
REQUIRED_OWNER_FLOOR_TABLE = "privacy_required_owner_floor"
# Database-level enforcement created and dropped together with the floor row (privacy_schema_v2), so code that
# predates the floor (a rolled-back release) can neither authorize nor complete a floor-scoped FORGET without it.
FLOOR_ENFORCEMENT_TRIGGERS = (
    "privacy_floor_hermes_fi_authorization",
    "privacy_floor_hermes_fi_completion",
)

PRIVACY_TABLES = frozenset({
    "privacy_schema_migration",
    "privacy_governance_config",
    "privacy_forget_request",
    "privacy_hold",
    "privacy_erasure_authorization",
    "privacy_erasure_authorization_owner",
    "privacy_erasure_execution",
    "privacy_restore_suppression_manifest",
    "privacy_completion_receipt",
    "privacy_completion_owner_result",
})

PRIVACY_SCHEMA_OBJECTS = frozenset({
    *PRIVACY_TABLES,
    "privacy_hold_identity",
    "privacy_erasure_authorization_fingerprint",
    "privacy_erasure_execution_owner",
    "privacy_restore_suppression_selector",
    "privacy_forget_request_no_update",
    "privacy_hold_no_update",
    "privacy_erasure_authorization_no_update",
    "privacy_erasure_authorization_owner_no_update",
    "privacy_restore_suppression_no_update",
    "privacy_restore_suppression_no_delete",
    "privacy_completion_receipt_no_update",
    "privacy_completion_receipt_no_delete",
    "privacy_completion_owner_result_no_update",
    "privacy_completion_owner_result_no_delete",
})

PRIVACY_MIGRATION_STATEMENTS = (
    """
    CREATE TABLE IF NOT EXISTS privacy_schema_migration (
        version INTEGER PRIMARY KEY,
        schema_fingerprint TEXT NOT NULL,
        applied_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS privacy_governance_config (
        config_id TEXT PRIMARY KEY CHECK(config_id='production'),
        authority_version TEXT NOT NULL CHECK(authority_version='PRIVACY_GOVERNANCE_AUTHORITY_V1'),
        max_backup_retention_days INTEGER NOT NULL CHECK(max_backup_retention_days BETWEEN 1 AND 30),
        restore_suppression_required INTEGER NOT NULL CHECK(restore_suppression_required=1),
        configured_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS privacy_forget_request (
        request_id TEXT PRIMARY KEY,
        schema_version INTEGER NOT NULL CHECK(schema_version=1),
        actor_ref_id TEXT NOT NULL,
        actor_evidence_ref_id TEXT NOT NULL,
        memory_class TEXT NOT NULL,
        subject_namespace TEXT NOT NULL,
        subject_key TEXT NOT NULL,
        memory_item_id TEXT,
        operation TEXT NOT NULL CHECK(operation='FORGET'),
        scope TEXT NOT NULL CHECK(scope='CANONICAL_AND_KNOWN_DERIVED_COPIES'),
        intent_ref_id TEXT NOT NULL,
        action_digest TEXT NOT NULL CHECK(length(action_digest)=64),
        requested_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS privacy_hold (
        hold_id TEXT PRIMARY KEY,
        request_id TEXT NOT NULL UNIQUE REFERENCES privacy_forget_request(request_id),
        memory_class TEXT NOT NULL,
        subject_namespace TEXT NOT NULL,
        subject_key TEXT NOT NULL,
        action_digest TEXT NOT NULL CHECK(length(action_digest)=64),
        state TEXT NOT NULL CHECK(state='ACTIVE'),
        created_at TEXT NOT NULL
    )
    """,
    """CREATE UNIQUE INDEX IF NOT EXISTS privacy_hold_identity
        ON privacy_hold(memory_class,subject_namespace,subject_key)""",
    """
    CREATE TABLE IF NOT EXISTS privacy_erasure_authorization (
        authorization_ref_id TEXT PRIMARY KEY,
        request_id TEXT NOT NULL UNIQUE REFERENCES privacy_forget_request(request_id),
        authority TEXT NOT NULL CHECK(authority='PRIVACY_GOVERNANCE_AUTHORITY_V1'),
        actor_ref_id TEXT NOT NULL,
        actor_evidence_ref_id TEXT NOT NULL,
        memory_class TEXT NOT NULL,
        subject_namespace TEXT NOT NULL,
        subject_key TEXT NOT NULL,
        memory_item_id TEXT,
        hold_id TEXT NOT NULL REFERENCES privacy_hold(hold_id),
        action_digest TEXT NOT NULL CHECK(length(action_digest)=64),
        authorization_version TEXT NOT NULL CHECK(authorization_version='V1'),
        confirmation_event_ref TEXT NOT NULL,
        execution_nonce TEXT NOT NULL UNIQUE,
        authorized_at TEXT NOT NULL,
        authorization_fingerprint TEXT NOT NULL CHECK(length(authorization_fingerprint)=64)
    )
    """,
    """CREATE UNIQUE INDEX IF NOT EXISTS privacy_erasure_authorization_fingerprint
        ON privacy_erasure_authorization(authorization_fingerprint)""",
    """
    CREATE TABLE IF NOT EXISTS privacy_erasure_authorization_owner (
        authorization_ref_id TEXT NOT NULL REFERENCES privacy_erasure_authorization(authorization_ref_id),
        resource_owner TEXT NOT NULL CHECK(resource_owner IN (
            'L04','L18_V1','L18_V2','ACTOR_AUTHORITY','POLICY','CONSENT','ROLLBACK',
            'LEGACY_MEMORY','LEGACY_SKILLS','PENDING'
        )),
        PRIMARY KEY(authorization_ref_id,resource_owner)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS privacy_erasure_execution (
        execution_id TEXT PRIMARY KEY,
        authorization_ref_id TEXT NOT NULL REFERENCES privacy_erasure_authorization(authorization_ref_id),
        resource_owner TEXT NOT NULL,
        status TEXT NOT NULL CHECK(status IN ('COMPLETE','FAILED')),
        completed_at TEXT NOT NULL,
        result_fingerprint TEXT NOT NULL CHECK(length(result_fingerprint)=64)
    )
    """,
    """CREATE UNIQUE INDEX IF NOT EXISTS privacy_erasure_execution_owner
        ON privacy_erasure_execution(authorization_ref_id,resource_owner)""",
    """
    CREATE TABLE IF NOT EXISTS privacy_restore_suppression_manifest (
        suppression_ref_id TEXT PRIMARY KEY,
        authority TEXT NOT NULL CHECK(authority='PRIVACY_GOVERNANCE_AUTHORITY_V1'),
        identity_selector TEXT NOT NULL CHECK(length(identity_selector)=64),
        state TEXT NOT NULL CHECK(state IN ('ACTIVE','COMPLETE')),
        created_at TEXT NOT NULL,
        completed_at TEXT
    )
    """,
    """CREATE UNIQUE INDEX IF NOT EXISTS privacy_restore_suppression_selector
        ON privacy_restore_suppression_manifest(identity_selector)""",
    """
    CREATE TABLE IF NOT EXISTS privacy_completion_receipt (
        receipt_id TEXT PRIMARY KEY,
        authority_version TEXT NOT NULL CHECK(authority_version='PRIVACY_GOVERNANCE_AUTHORITY_V1'),
        completed_at TEXT NOT NULL,
        restore_suppression_ref TEXT NOT NULL REFERENCES privacy_restore_suppression_manifest(suppression_ref_id),
        verification_status TEXT NOT NULL CHECK(verification_status='COMPLETE'),
        receipt_fingerprint TEXT NOT NULL UNIQUE CHECK(length(receipt_fingerprint)=64)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS privacy_completion_owner_result (
        receipt_id TEXT NOT NULL REFERENCES privacy_completion_receipt(receipt_id),
        resource_owner TEXT NOT NULL,
        status TEXT NOT NULL CHECK(status='COMPLETE'),
        result_fingerprint TEXT NOT NULL CHECK(length(result_fingerprint)=64),
        PRIMARY KEY(receipt_id,resource_owner)
    )
    """,
    """CREATE TRIGGER IF NOT EXISTS privacy_forget_request_no_update
        BEFORE UPDATE ON privacy_forget_request BEGIN SELECT RAISE(ABORT,'forget request is immutable'); END""",
    """CREATE TRIGGER IF NOT EXISTS privacy_hold_no_update
        BEFORE UPDATE ON privacy_hold BEGIN SELECT RAISE(ABORT,'privacy hold is immutable'); END""",
    """CREATE TRIGGER IF NOT EXISTS privacy_erasure_authorization_no_update
        BEFORE UPDATE ON privacy_erasure_authorization BEGIN SELECT RAISE(ABORT,'erasure authorization is immutable'); END""",
    """CREATE TRIGGER IF NOT EXISTS privacy_erasure_authorization_owner_no_update
        BEFORE UPDATE ON privacy_erasure_authorization_owner BEGIN SELECT RAISE(ABORT,'erasure owner set is immutable'); END""",
    """CREATE TRIGGER IF NOT EXISTS privacy_restore_suppression_no_update
        BEFORE UPDATE ON privacy_restore_suppression_manifest BEGIN SELECT RAISE(ABORT,'suppression manifest is immutable'); END""",
    """CREATE TRIGGER IF NOT EXISTS privacy_restore_suppression_no_delete
        BEFORE DELETE ON privacy_restore_suppression_manifest BEGIN SELECT RAISE(ABORT,'suppression manifest is monotonic'); END""",
    """CREATE TRIGGER IF NOT EXISTS privacy_completion_receipt_no_update
        BEFORE UPDATE ON privacy_completion_receipt BEGIN SELECT RAISE(ABORT,'privacy receipt is immutable'); END""",
    """CREATE TRIGGER IF NOT EXISTS privacy_completion_receipt_no_delete
        BEFORE DELETE ON privacy_completion_receipt BEGIN SELECT RAISE(ABORT,'privacy receipt is immutable'); END""",
    """CREATE TRIGGER IF NOT EXISTS privacy_completion_owner_result_no_update
        BEFORE UPDATE ON privacy_completion_owner_result BEGIN SELECT RAISE(ABORT,'privacy result is immutable'); END""",
    """CREATE TRIGGER IF NOT EXISTS privacy_completion_owner_result_no_delete
        BEFORE DELETE ON privacy_completion_owner_result BEGIN SELECT RAISE(ABORT,'privacy result is immutable'); END""",
)


class PrivacyError(RuntimeError):
    pass


def utc_now(value: Optional[datetime] = None) -> str:
    stamp = value or datetime.now(timezone.utc)
    if stamp.tzinfo is None:
        stamp = stamp.replace(tzinfo=timezone.utc)
    return stamp.astimezone(timezone.utc).isoformat(timespec="microseconds").replace(
        "+00:00", "Z"
    )


def _hmac(secret: bytes, value: Dict[str, Any]) -> str:
    return hmac.new(
        secret, C.canonical_json(value).encode("ascii"), hashlib.sha256
    ).hexdigest()


def create_owner_only_secret(path: Path) -> None:
    A.create_owner_only_secret(path)


def load_owner_only_secret(path: Path) -> bytes:
    return A.load_owner_only_secret(path)


@dataclass(frozen=True)
class ForgetMemoryRequestV1:
    request_id: str
    actor_ref_id: str
    actor_evidence_ref_id: str
    memory_class: str
    subject_namespace: str
    subject_key: str
    memory_item_id: Optional[str]
    operation: str
    scope: str
    intent_ref_id: str
    action_digest: str
    requested_at: str

    @property
    def identity(self) -> Tuple[str, str, str]:
        return (self.memory_class, self.subject_namespace, self.subject_key)


@dataclass(frozen=True)
class ErasureAuthorizationV1:
    authorization_ref_id: str
    actor_ref_id: str
    actor_evidence_ref_id: str
    memory_class: str
    subject_namespace: str
    subject_key: str
    memory_item_id: Optional[str]
    hold_id: str
    action_digest: str
    confirmation_event_ref: str
    execution_nonce: str
    resource_owners: Tuple[str, ...]
    authorized_at: str
    authorization_fingerprint: str

    @property
    def identity(self) -> Tuple[str, str, str]:
        return (self.memory_class, self.subject_namespace, self.subject_key)


@dataclass(frozen=True)
class PrivacyCompletionReceiptV1:
    receipt_id: str
    completed_at: str
    restore_suppression_ref: str
    verification_status: str
    receipt_fingerprint: str


def _authorizer(
    action: int,
    arg1: Optional[str],
    arg2: Optional[str],
    database: Optional[str],
    trigger: Optional[str],
) -> int:
    del arg2, database, trigger
    table = str(arg1 or "")
    if action == sqlite3.SQLITE_READ:
        # The v2 required-owner floor is readable but never writable here; only the governed tool provisions it.
        readable = PRIVACY_TABLES | {"sqlite_master", REQUIRED_OWNER_FLOOR_TABLE}
        return sqlite3.SQLITE_OK if table in readable else sqlite3.SQLITE_DENY
    if action in {sqlite3.SQLITE_INSERT, sqlite3.SQLITE_UPDATE, sqlite3.SQLITE_DELETE}:
        writable = PRIVACY_TABLES - {
            "privacy_schema_migration",
            "privacy_governance_config",
        }
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


class PrivacyGovernanceStore:
    def __init__(
        self,
        path: Path,
        secret: bytes,
        actor_authority: A.LocalOwnerAuthority,
        *,
        now_fn: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
    ):
        if len(secret) < 32:
            raise ValueError("privacy authority secret must be at least 32 bytes")
        self.path = Path(path)
        self._secret = bytes(secret)
        self.actor_authority = actor_authority
        self.now_fn = now_fn

    @classmethod
    def from_secret_file(
        cls,
        path: Path,
        secret_path: Path,
        actor_authority: A.LocalOwnerAuthority,
        **kwargs: Any,
    ):
        return cls(path, load_owner_only_secret(secret_path), actor_authority, **kwargs)

    def _connect(self) -> sqlite3.Connection:
        if not self.path.is_file():
            raise PrivacyError("privacy governance database is unavailable")
        if os.name != "nt" and stat.S_IMODE(self.path.stat().st_mode) != 0o600:
            raise PrivacyError("privacy governance database must be mode 0600")
        conn = sqlite3.connect(str(self.path), timeout=5.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA secure_delete=ON")
        existing = {
            str(row[0])
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
            )
        }
        if not PRIVACY_TABLES.issubset(existing):
            conn.close()
            raise PrivacyError("privacy governance schema is unavailable")
        conn.set_authorizer(_authorizer)
        return conn

    def identity_selector(self, identity: Tuple[str, str, str]) -> str:
        return _hmac(self._secret, {
            "authority": C.PRIVACY_GOVERNANCE_AUTHORITY_V1,
            "selectorVersion": 1,
            "memoryClass": identity[0],
            "subjectNamespace": identity[1],
            "subjectKey": identity[2],
        })

    def is_held(self, memory_class: str, subject_namespace: str, subject_key: str) -> bool:
        identity = (memory_class, subject_namespace, subject_key)
        selector = self.identity_selector(identity)
        conn = self._connect()
        try:
            if conn.execute(
                "SELECT 1 FROM privacy_hold WHERE memory_class=? AND subject_namespace=? "
                "AND subject_key=? AND state='ACTIVE'",
                identity,
            ).fetchone():
                return True
            return conn.execute(
                "SELECT 1 FROM privacy_restore_suppression_manifest "
                "WHERE identity_selector=? AND state IN ('ACTIVE','COMPLETE')",
                (selector,),
            ).fetchone() is not None
        finally:
            conn.close()

    @staticmethod
    def _owner_floor(conn: sqlite3.Connection, memory_class: str, subject_namespace: str) -> Tuple[int, frozenset]:
        """Schema version and the governed required-owner floor for one identity scope (always empty on v1)."""
        try:
            version = int(conn.execute("SELECT MAX(version) FROM privacy_schema_migration").fetchone()[0] or 0)
            if version == PRIVACY_SCHEMA_V1:
                return version, frozenset()
            if version != PRIVACY_SCHEMA_V2:
                raise PrivacyError("privacy governance schema version is unsupported")
            rows = conn.execute(
                f"SELECT resource_owner FROM {REQUIRED_OWNER_FLOOR_TABLE} "
                "WHERE memory_class=? AND subject_namespace=?",
                (memory_class, subject_namespace),
            ).fetchall()
            if rows:
                marks = ",".join("?" for _ in FLOOR_ENFORCEMENT_TRIGGERS)
                present = conn.execute(
                    f"SELECT COUNT(*) FROM sqlite_master WHERE type='trigger' AND name IN ({marks})",
                    FLOOR_ENFORCEMENT_TRIGGERS,
                ).fetchone()[0]
                if int(present) != len(FLOOR_ENFORCEMENT_TRIGGERS):
                    raise PrivacyError("required erasure owner floor enforcement is missing")
        except sqlite3.Error as exc:
            raise PrivacyError("privacy governance owner floor is unavailable") from exc
        return version, frozenset(str(row[0]) for row in rows)

    @staticmethod
    def _check_owner_scope(version: int, floor: frozenset, owners: Sequence[str]) -> None:
        if version == PRIVACY_SCHEMA_V1 and not set(owners).issubset(OWNER_SET_V1):
            raise PrivacyError("erasure resource owner requires privacy schema v2")
        if not floor.issubset(owners):
            raise PrivacyError("required erasure resource owner is missing")
        if (set(owners) & SCOPED_OWNERS) - floor:
            raise PrivacyError("erasure resource owner is not provisioned for this scope")

    def begin_forget(
        self,
        *,
        action: C.FrozenMemoryActionV1,
        actor_evidence_ref_id: str,
        intent_ref_id: str,
        memory_item_id: Optional[str],
        resource_owners: Iterable[str],
        confirmation_event_ref: str,
    ) -> Tuple[ForgetMemoryRequestV1, ErasureAuthorizationV1, str]:
        action.validate()
        if action.operation != C.FORGET:
            raise PrivacyError("Privacy authority accepts only FORGET")
        owners = tuple(sorted(set(resource_owners)))
        if not owners or not set(owners).issubset(OWNER_SET):
            raise PrivacyError("erasure resource owner set is invalid")
        # Checked before the actor evidence is consumed, and again inside the write transaction below.
        conn = self._connect()
        try:
            scope = self._owner_floor(conn, action.memory_class, action.subject_namespace)
        finally:
            conn.close()
        self._check_owner_scope(*scope, owners)
        actor = self.actor_authority.resolve_and_consume(
            actor_evidence_ref_id,
            action=action,
            consumer_ref="privacy.forget.v1",
        )
        if actor.status != A.CONFIRMED:
            raise PrivacyError(actor.failure_code or "ACTOR_UNRESOLVED")
        now = utc_now(self.now_fn())
        request = ForgetMemoryRequestV1(
            request_id="forget." + uuid.uuid4().hex,
            actor_ref_id=action.actor_ref_id,
            actor_evidence_ref_id=actor_evidence_ref_id,
            memory_class=action.memory_class,
            subject_namespace=action.subject_namespace,
            subject_key=action.subject_key,
            memory_item_id=memory_item_id,
            operation=C.FORGET,
            scope=SCOPE,
            intent_ref_id=intent_ref_id,
            action_digest=action.action_digest,
            requested_at=now,
        )
        hold_id = "hold." + uuid.uuid4().hex
        authorization_ref_id = "erase." + uuid.uuid4().hex
        execution_nonce = "execution." + uuid.uuid4().hex
        auth_semantic = {
            "authority": C.PRIVACY_GOVERNANCE_AUTHORITY_V1,
            "actorRefId": action.actor_ref_id,
            "actorEvidenceRefId": actor_evidence_ref_id,
            "memoryClass": action.memory_class,
            "subjectNamespace": action.subject_namespace,
            "subjectKey": action.subject_key,
            "memoryItemId": memory_item_id,
            "resourceOwners": list(owners),
            "privacyHoldId": hold_id,
            "actionDigest": action.action_digest,
            "authorizationVersion": "V1",
            "confirmationEventRef": confirmation_event_ref,
            "executionNonce": execution_nonce,
        }
        authorization = ErasureAuthorizationV1(
            authorization_ref_id=authorization_ref_id,
            actor_ref_id=action.actor_ref_id,
            actor_evidence_ref_id=actor_evidence_ref_id,
            memory_class=action.memory_class,
            subject_namespace=action.subject_namespace,
            subject_key=action.subject_key,
            memory_item_id=memory_item_id,
            hold_id=hold_id,
            action_digest=action.action_digest,
            confirmation_event_ref=confirmation_event_ref,
            execution_nonce=execution_nonce,
            resource_owners=owners,
            authorized_at=now,
            authorization_fingerprint=_hmac(self._secret, auth_semantic),
        )
        suppression_ref = "suppress." + uuid.uuid4().hex
        conn = self._connect()
        try:
            conn.execute("BEGIN IMMEDIATE")
            if self._owner_floor(conn, action.memory_class, action.subject_namespace) != scope:
                raise PrivacyError("required erasure owner floor changed during FORGET")
            conn.execute(
                "INSERT INTO privacy_forget_request VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    request.request_id,
                    1,
                    request.actor_ref_id,
                    request.actor_evidence_ref_id,
                    request.memory_class,
                    request.subject_namespace,
                    request.subject_key,
                    request.memory_item_id,
                    request.operation,
                    request.scope,
                    request.intent_ref_id,
                    request.action_digest,
                    request.requested_at,
                ),
            )
            conn.execute(
                "INSERT INTO privacy_hold VALUES (?,?,?,?,?,?,?,?)",
                (
                    hold_id,
                    request.request_id,
                    *request.identity,
                    request.action_digest,
                    "ACTIVE",
                    now,
                ),
            )
            conn.execute(
                "INSERT INTO privacy_erasure_authorization VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    authorization.authorization_ref_id,
                    request.request_id,
                    C.PRIVACY_GOVERNANCE_AUTHORITY_V1,
                    authorization.actor_ref_id,
                    authorization.actor_evidence_ref_id,
                    *authorization.identity,
                    authorization.memory_item_id,
                    authorization.hold_id,
                    authorization.action_digest,
                    "V1",
                    authorization.confirmation_event_ref,
                    authorization.execution_nonce,
                    authorization.authorized_at,
                    authorization.authorization_fingerprint,
                ),
            )
            conn.executemany(
                "INSERT INTO privacy_erasure_authorization_owner VALUES (?,?)",
                [(authorization_ref_id, owner) for owner in owners],
            )
            conn.execute(
                "INSERT INTO privacy_restore_suppression_manifest VALUES (?,?,?,?,?,?)",
                (
                    suppression_ref,
                    C.PRIVACY_GOVERNANCE_AUTHORITY_V1,
                    self.identity_selector(request.identity),
                    "ACTIVE",
                    now,
                    None,
                ),
            )
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
        return request, authorization, suppression_ref

    def _authorization_from_row(
        self, row: sqlite3.Row, owners: Sequence[str]
    ) -> ErasureAuthorizationV1:
        return ErasureAuthorizationV1(
            authorization_ref_id=str(row["authorization_ref_id"]),
            actor_ref_id=str(row["actor_ref_id"]),
            actor_evidence_ref_id=str(row["actor_evidence_ref_id"]),
            memory_class=str(row["memory_class"]),
            subject_namespace=str(row["subject_namespace"]),
            subject_key=str(row["subject_key"]),
            memory_item_id=row["memory_item_id"],
            hold_id=str(row["hold_id"]),
            action_digest=str(row["action_digest"]),
            confirmation_event_ref=str(row["confirmation_event_ref"]),
            execution_nonce=str(row["execution_nonce"]),
            resource_owners=tuple(sorted(owners)),
            authorized_at=str(row["authorized_at"]),
            authorization_fingerprint=str(row["authorization_fingerprint"]),
        )

    def resolve_erasure_authorization(
        self,
        authorization_ref_id: str,
        *,
        owner: str,
        execution_nonce: str,
    ) -> Optional[ErasureAuthorizationV1]:
        if owner not in OWNER_SET:
            return None
        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT * FROM privacy_erasure_authorization WHERE authorization_ref_id=?",
                (authorization_ref_id,),
            ).fetchone()
            if row is None or str(row["execution_nonce"]) != execution_nonce:
                return None
            owners = [
                str(r[0])
                for r in conn.execute(
                    "SELECT resource_owner FROM privacy_erasure_authorization_owner "
                    "WHERE authorization_ref_id=? ORDER BY resource_owner",
                    (authorization_ref_id,),
                )
            ]
            if owner not in owners:
                return None
            authorization = self._authorization_from_row(row, owners)
            semantic = {
                "authority": C.PRIVACY_GOVERNANCE_AUTHORITY_V1,
                "actorRefId": authorization.actor_ref_id,
                "actorEvidenceRefId": authorization.actor_evidence_ref_id,
                "memoryClass": authorization.memory_class,
                "subjectNamespace": authorization.subject_namespace,
                "subjectKey": authorization.subject_key,
                "memoryItemId": authorization.memory_item_id,
                "resourceOwners": list(authorization.resource_owners),
                "privacyHoldId": authorization.hold_id,
                "actionDigest": authorization.action_digest,
                "authorizationVersion": "V1",
                "confirmationEventRef": authorization.confirmation_event_ref,
                "executionNonce": authorization.execution_nonce,
            }
            if not hmac.compare_digest(
                authorization.authorization_fingerprint,
                _hmac(self._secret, semantic),
            ):
                return None
            hold = conn.execute(
                "SELECT 1 FROM privacy_hold WHERE hold_id=? AND state='ACTIVE'",
                (authorization.hold_id,),
            ).fetchone()
            return authorization if hold else None
        finally:
            conn.close()

    def record_owner_result(
        self,
        authorization_ref_id: str,
        execution_nonce: str,
        result: Dict[str, Any],
    ) -> None:
        owner = str(result.get("owner") or "")
        status = str(result.get("status") or "")
        authorization = self.resolve_erasure_authorization(
            authorization_ref_id, owner=owner, execution_nonce=execution_nonce
        )
        if authorization is None or status not in {"COMPLETE", "FAILED"}:
            raise PrivacyError("invalid owner erasure result")
        fingerprint = _hmac(self._secret, {
            "authorizationRefId": authorization_ref_id,
            "resourceOwner": owner,
            "status": status,
        })
        conn = self._connect()
        try:
            conn.execute(
                "INSERT INTO privacy_erasure_execution VALUES (?,?,?,?,?,?)",
                (
                    "erase-result." + uuid.uuid4().hex,
                    authorization_ref_id,
                    owner,
                    status,
                    utc_now(self.now_fn()),
                    fingerprint,
                ),
            )
            conn.commit()
        finally:
            conn.close()

    def owner_result(
        self, authorization_ref_id: str, execution_nonce: str, owner: str
    ) -> Optional[str]:
        """Read-only: the recorded status of one owner for one live authorization (exact nonce), else None.

        Lets an owner make a retry idempotent instead of colliding with its own earlier result.
        """
        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT e.status FROM privacy_erasure_execution e "
                "JOIN privacy_erasure_authorization a ON a.authorization_ref_id=e.authorization_ref_id "
                "WHERE e.authorization_ref_id=? AND e.resource_owner=? AND a.execution_nonce=?",
                (authorization_ref_id, owner, execution_nonce),
            ).fetchone()
            return None if row is None else str(row[0])
        finally:
            conn.close()

    def owner_completion_recorded(self, authorization_ref_id: str, owner: str) -> bool:
        """Read-only: Privacy has COMPLETED exactly this authorization with this owner COMPLETE.

        Proven by the immutable completion rows (the owner result fingerprint is HMAC-bound to the reference, owner
        and status under this secret) and by the authorization no longer being in flight."""
        fingerprint = _hmac(self._secret, {
            "authorizationRefId": authorization_ref_id,
            "resourceOwner": owner,
            "status": "COMPLETE",
        })
        conn = self._connect()
        try:
            in_flight = conn.execute(
                "SELECT 1 FROM privacy_erasure_authorization WHERE authorization_ref_id=?", (authorization_ref_id,)
            ).fetchone()
            recorded = conn.execute(
                "SELECT 1 FROM privacy_completion_owner_result WHERE resource_owner=? AND status='COMPLETE' "
                "AND result_fingerprint=?", (owner, fingerprint)
            ).fetchone()
            return in_flight is None and recorded is not None
        finally:
            conn.close()

    def identity_forget_completed(self, identity: Tuple[str, str, str], required_owner: str) -> bool:
        """Read-only: a FORGET of exactly this identity has COMPLETED with ``required_owner`` among its owners.

        Proven by no ACTIVE hold on the identity, its suppression selector, and a completion receipt for that selector
        whose HMAC verifies under this secret and whose owner results include ``required_owner`` COMPLETE. Lets the
        root hold-first release (F9-C Track A) clear a durable FORGET intent without the intent naming an
        authorization."""
        selector = self.identity_selector(identity)
        conn = self._connect()
        try:
            if conn.execute(
                "SELECT 1 FROM privacy_hold WHERE memory_class=? AND subject_namespace=? AND subject_key=? "
                "AND state='ACTIVE'", tuple(identity)
            ).fetchone() is not None:
                return False
            suppression = conn.execute(
                "SELECT suppression_ref_id FROM privacy_restore_suppression_manifest WHERE identity_selector=?",
                (selector,)).fetchone()
            if suppression is None:
                return False
            for receipt in conn.execute(
                    "SELECT * FROM privacy_completion_receipt WHERE restore_suppression_ref=?",
                    (str(suppression[0]),)).fetchall():
                results = conn.execute(
                    "SELECT resource_owner,status,result_fingerprint FROM privacy_completion_owner_result "
                    "WHERE receipt_id=? ORDER BY resource_owner", (receipt["receipt_id"],)).fetchall()
                semantic = {
                    "authorityVersion": C.PRIVACY_GOVERNANCE_AUTHORITY_V1,
                    "resourceOwnerResults": [
                        {"owner": str(r[0]), "status": str(r[1]), "fingerprint": str(r[2])} for r in results
                    ],
                    "restoreSuppressionRef": str(receipt["restore_suppression_ref"]),
                    "verificationStatus": "COMPLETE",
                }
                if hmac.compare_digest(str(receipt["receipt_fingerprint"]), _hmac(self._secret, semantic)) \
                        and any(str(r[0]) == required_owner and str(r[1]) == "COMPLETE" for r in results):
                    return True
            return False
        finally:
            conn.close()

    def required_owners(self, memory_class: str, subject_namespace: str) -> frozenset:
        """Read-only: the governed required-owner floor for one identity scope (empty on v1; fails closed)."""
        conn = self._connect()
        try:
            return self._owner_floor(conn, memory_class, subject_namespace)[1]
        finally:
            conn.close()

    def in_flight_authorization(self, identity: Tuple[str, str, str]) -> Optional[Tuple[str, str]]:
        """Read-only: (authorization_ref_id, execution_nonce) of the ACTIVE hold on exactly this identity, else None.

        Lets the governed runner resume an interrupted FORGET without the caller naming an authorization.
        """
        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT a.authorization_ref_id,a.execution_nonce FROM privacy_hold h "
                "JOIN privacy_erasure_authorization a ON a.hold_id=h.hold_id "
                "WHERE h.memory_class=? AND h.subject_namespace=? AND h.subject_key=? AND h.state='ACTIVE'",
                tuple(identity),
            ).fetchone()
            return None if row is None else (str(row[0]), str(row[1]))
        finally:
            conn.close()

    def complete(
        self, authorization_ref_id: str, execution_nonce: str
    ) -> PrivacyCompletionReceiptV1:
        conn = self._connect()
        try:
            auth_row = conn.execute(
                "SELECT * FROM privacy_erasure_authorization WHERE authorization_ref_id=?",
                (authorization_ref_id,),
            ).fetchone()
            if auth_row is None or str(auth_row["execution_nonce"]) != execution_nonce:
                raise PrivacyError("erasure authorization is unavailable")
            required = tuple(
                str(r[0])
                for r in conn.execute(
                    "SELECT resource_owner FROM privacy_erasure_authorization_owner "
                    "WHERE authorization_ref_id=? ORDER BY resource_owner",
                    (authorization_ref_id,),
                )
            )
            results = {
                str(r[0]): (str(r[1]), str(r[2]))
                for r in conn.execute(
                    "SELECT resource_owner,status,result_fingerprint "
                    "FROM privacy_erasure_execution WHERE authorization_ref_id=?",
                    (authorization_ref_id,),
                )
            }
            if any(owner not in results or results[owner][0] != "COMPLETE" for owner in required):
                raise PrivacyError("erasure is incomplete; privacy hold remains active")
            selector = self.identity_selector((
                str(auth_row["memory_class"]),
                str(auth_row["subject_namespace"]),
                str(auth_row["subject_key"]),
            ))
            suppression = conn.execute(
                "SELECT suppression_ref_id FROM privacy_restore_suppression_manifest "
                "WHERE identity_selector=?",
                (selector,),
            ).fetchone()
            if suppression is None:
                raise PrivacyError("restore suppression is unavailable")
            suppression_ref = str(suppression[0])
            completed_at = utc_now(self.now_fn())
            receipt_id = "privacy-receipt." + uuid.uuid4().hex
            receipt_semantic = {
                "authorityVersion": C.PRIVACY_GOVERNANCE_AUTHORITY_V1,
                "resourceOwnerResults": [
                    {"owner": owner, "status": results[owner][0], "fingerprint": results[owner][1]}
                    for owner in required
                ],
                "restoreSuppressionRef": suppression_ref,
                "verificationStatus": "COMPLETE",
            }
            receipt = PrivacyCompletionReceiptV1(
                receipt_id=receipt_id,
                completed_at=completed_at,
                restore_suppression_ref=suppression_ref,
                verification_status="COMPLETE",
                receipt_fingerprint=_hmac(self._secret, receipt_semantic),
            )
            conn.execute("BEGIN IMMEDIATE")
            # The suppression row is immutable; completion is represented by the
            # receipt, while its ACTIVE selector remains monotonic and effective.
            conn.execute(
                "INSERT INTO privacy_completion_receipt VALUES (?,?,?,?,?,?)",
                (
                    receipt.receipt_id,
                    C.PRIVACY_GOVERNANCE_AUTHORITY_V1,
                    receipt.completed_at,
                    receipt.restore_suppression_ref,
                    receipt.verification_status,
                    receipt.receipt_fingerprint,
                ),
            )
            conn.executemany(
                "INSERT INTO privacy_completion_owner_result VALUES (?,?,?,?)",
                [
                    (receipt_id, owner, "COMPLETE", results[owner][1])
                    for owner in required
                ],
            )
            # Remove exact/linkable in-flight state.  The minimized receipt and
            # opaque keyed selector are the only durable completion artifacts.
            conn.execute(
                "DELETE FROM privacy_erasure_execution WHERE authorization_ref_id=?",
                (authorization_ref_id,),
            )
            conn.execute(
                "DELETE FROM privacy_erasure_authorization_owner WHERE authorization_ref_id=?",
                (authorization_ref_id,),
            )
            request_id = str(auth_row["request_id"])
            hold_id = str(auth_row["hold_id"])
            conn.execute(
                "DELETE FROM privacy_erasure_authorization WHERE authorization_ref_id=?",
                (authorization_ref_id,),
            )
            conn.execute("DELETE FROM privacy_hold WHERE hold_id=?", (hold_id,))
            conn.execute("DELETE FROM privacy_forget_request WHERE request_id=?", (request_id,))
            conn.commit()
            conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            return receipt
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def verify_suppression_integrity(self) -> int:
        """Read-only pre-serve check that this store and its secret really are the Privacy authority's records.

        Every completion receipt's HMAC must verify under this secret and still name an existing suppression selector,
        and every in-flight authorization's HMAC must verify. A wrong or rotated secret (whose selectors would match
        nothing, silently disabling suppression) or tampered records raise. Returns the number of selectors."""
        conn = self._connect()
        try:
            for receipt in conn.execute("SELECT * FROM privacy_completion_receipt ORDER BY receipt_id").fetchall():
                results = conn.execute(
                    "SELECT resource_owner,status,result_fingerprint FROM privacy_completion_owner_result "
                    "WHERE receipt_id=? ORDER BY resource_owner", (receipt["receipt_id"],)).fetchall()
                semantic = {
                    "authorityVersion": C.PRIVACY_GOVERNANCE_AUTHORITY_V1,
                    "resourceOwnerResults": [
                        {"owner": str(r[0]), "status": str(r[1]), "fingerprint": str(r[2])} for r in results
                    ],
                    "restoreSuppressionRef": str(receipt["restore_suppression_ref"]),
                    "verificationStatus": "COMPLETE",
                }
                if not results or not hmac.compare_digest(str(receipt["receipt_fingerprint"]),
                                                          _hmac(self._secret, semantic)):
                    raise PrivacyError("privacy completion receipt does not verify")
                if conn.execute("SELECT 1 FROM privacy_restore_suppression_manifest WHERE suppression_ref_id=?",
                                (receipt["restore_suppression_ref"],)).fetchone() is None:
                    raise PrivacyError("privacy restore suppression selector is missing")
            for row in conn.execute("SELECT authorization_ref_id,execution_nonce FROM privacy_erasure_authorization"):
                owners = [str(r[0]) for r in conn.execute(
                    "SELECT resource_owner FROM privacy_erasure_authorization_owner WHERE authorization_ref_id=?",
                    (row[0],))]
                if not owners or self.resolve_erasure_authorization(
                        str(row[0]), owner=owners[0], execution_nonce=str(row[1])) is None:
                    raise PrivacyError("in-flight erasure authorization does not verify")
            return int(conn.execute("SELECT COUNT(*) FROM privacy_restore_suppression_manifest").fetchone()[0])
        finally:
            conn.close()

    def suppression_matches(self, identity: Tuple[str, str, str]) -> bool:
        selector = self.identity_selector(identity)
        conn = self._connect()
        try:
            return conn.execute(
                "SELECT 1 FROM privacy_restore_suppression_manifest "
                "WHERE identity_selector=?",
                (selector,),
            ).fetchone() is not None
        finally:
            conn.close()


def validate_backup_retention(
    backup_paths: Iterable[Path],
    *,
    now: Optional[datetime] = None,
    max_days: int = DEFAULT_MAX_BACKUP_RETENTION_DAYS,
) -> Tuple[Path, ...]:
    """Return backups beyond the configured ceiling; deletion is never automatic."""
    if isinstance(max_days, bool) or not 1 <= int(max_days) <= 30:
        raise PrivacyError("backup retention ceiling is invalid")
    current = (now or datetime.now(timezone.utc)).timestamp()
    limit_seconds = int(max_days) * 86400
    expired = []
    for path in backup_paths:
        target = Path(path)
        if not target.is_file() or current - target.stat().st_mtime > limit_seconds:
            expired.append(target)
    return tuple(expired)


@dataclass(frozen=True)
class RestoreSuppressionVerification:
    ready_to_serve: bool
    matched_identities: int
    suppressed_identities: int
    failure_code: Optional[str]


class RestoreSuppressionVerifier:
    """Explicit pre-serve utility; it is not a startup hook or scheduler.

    Privacy's suppression selectors are the authority: whatever a restored cognitive database contains, every identity
    this Privacy store has suppressed is erased from L04 and then L18 V2 (L04 admissions reference L18 proposal rows)
    through their governed restore paths. Ready only when, re-read afterwards, no suppressed identity has any L04 or
    L18 V2 row left (for First Interaction: the whole family and the capture copy). Any error fails closed; a re-run
    after a crash or partial cleanup is safe."""

    def __init__(self, privacy_store: PrivacyGovernanceStore, l04_owner: Any, l18_owner: Any):
        if l04_owner is None or l18_owner is None:
            raise PrivacyError("restore suppression needs both the L04 and L18 V2 owners")
        self.privacy_store = privacy_store
        self.l04_owner = l04_owner
        self.l18_owner = l18_owner

    def _identities(self) -> Tuple[Tuple[str, str, str], ...]:
        return tuple(sorted(
            {tuple(i) for i in self.l04_owner.list_identities()} | {tuple(i) for i in self.l18_owner.list_identities()}
        ))

    def verify_and_apply(self) -> RestoreSuppressionVerification:
        owners = (self.l04_owner, self.l18_owner)
        try:
            self.privacy_store.verify_suppression_integrity()
        except Exception:
            return RestoreSuppressionVerification(False, 0, 0, "PRIVACY_RECORDS_UNVERIFIED")
        try:
            matched = [i for i in self._identities() if self.privacy_store.suppression_matches(i)]
            suppressed = 0
            for identity in matched:
                for owner in owners:
                    owner.erase_restore_suppressed(identity, self.privacy_store)
                suppressed += 1
            remaining = [i for i in self._identities() if self.privacy_store.suppression_matches(i)]
            if remaining or any(owner.restore_residue(i) for i in matched for owner in owners):
                return RestoreSuppressionVerification(False, len(matched), suppressed, "SUPPRESSION_INCOMPLETE")
            return RestoreSuppressionVerification(True, len(matched), suppressed, None)
        except Exception:
            return RestoreSuppressionVerification(False, 0, 0, "RESTORE_VERIFICATION_FAILED")


class RestoreSuppressionNotReady(PermissionError):
    """Memory serving refused: the restore-suppression gate is not ready (an explicit refusal, never a miss)."""

    def __init__(self, code: str):
        super().__init__("RESTORE_SUPPRESSION_NOT_READY:" + code)
        self.code = code


class RestoreSuppressionGate:
    """Read-only pre-serve gate over this Privacy authority and the L04 / L18 V2 restore probes.

    There is no readiness flag: every check re-reads the current Privacy and cognitive (and capture) stores, so a
    restore, a database replacement or a new suppression takes effect at the next memory-serving call. Ready requires
    the Privacy records to verify under this secret, and no suppressed identity to have content that no ACTIVE hold
    covers (content under an in-flight FORGET is expected and already refused per identity by ``is_held``). It only
    lists and counts (read-only connections); erasure stays with ``RestoreSuppressionVerifier.verify_and_apply``, a
    separate maintenance step that request handlers are never given."""

    def __init__(self, privacy_store: PrivacyGovernanceStore, l04_owner: Any, l18_owner: Any):
        if l04_owner is None or l18_owner is None:
            raise PrivacyError("the restore-suppression gate needs both the L04 and L18 V2 owners")
        self._privacy = privacy_store
        # Only the read-only probes are kept; the gate has no erasure operation.
        self._probes = tuple((owner.list_identities, owner.restore_residue) for owner in (l04_owner, l18_owner))

    def check(self) -> RestoreSuppressionVerification:
        try:
            self._privacy.verify_suppression_integrity()
        except Exception:
            return RestoreSuppressionVerification(False, 0, 0, "PRIVACY_RECORDS_UNVERIFIED")
        try:
            identities = sorted({tuple(i) for listing, _ in self._probes for i in listing()})
            matched = [i for i in identities if self._privacy.suppression_matches(i)]
            exposed = [
                i for i in matched
                if self._privacy.in_flight_authorization(i) is None and any(residue(i) for _, residue in self._probes)
            ]
        except Exception:
            return RestoreSuppressionVerification(False, 0, 0, "RESTORE_CHECK_FAILED")
        if exposed:
            return RestoreSuppressionVerification(False, len(matched), 0, "SUPPRESSED_CONTENT_PRESENT")
        return RestoreSuppressionVerification(True, len(matched), 0, None)

    def require_ready(self) -> None:
        verification = self.check()
        if not verification.ready_to_serve:
            raise RestoreSuppressionNotReady(str(verification.failure_code))


class GatedPrivacyHoldResolver:
    """The ``privacy_hold_resolver`` given to memory-serving components (read facade, canonical store, learning
    store). Every call first requires the restore-suppression gate, then answers from the Privacy authority exactly
    as before; a gate failure raises (it is never reported as a hold, which would write REJECTED admissions)."""

    def __init__(self, privacy_store: PrivacyGovernanceStore, gate: RestoreSuppressionGate):
        if not isinstance(gate, RestoreSuppressionGate):
            raise TypeError("a RestoreSuppressionGate is required")
        self._privacy = privacy_store
        self._gate = gate

    def require_ready(self) -> None:
        self._gate.require_ready()

    def is_held(self, memory_class: str, subject_namespace: str, subject_key: str) -> bool:
        self._gate.require_ready()
        return self._privacy.is_held(memory_class, subject_namespace, subject_key)
