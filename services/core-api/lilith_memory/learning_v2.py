"""Additive Slice 15B2a L18 V2 candidate/proposal foundations.

Slice 15A career V1 tables and meanings are not changed.  V2 uses a stable
candidate envelope plus a closed source-family descriptor; candidates keep a
digest only, while the typed intent and proposal are the only planned holders
of normalized value JSON.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import unicodedata
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, Mapping, Optional, Tuple

try:
    from . import canonical_contracts as C
except ImportError:  # deploy-exact flat-directory tests
    import canonical_contracts as C


SCHEMA_VERSION = 1
V2_PROPOSAL_FAMILY = "OWNER_DIRECTED_PROJECT_CODENAME_V1"
V1_PROPOSAL_FAMILY = "L18_V1_CAREER"
CANDIDATE_CLASS = "OWNER_DIRECTED_MEMORY_CANDIDATE"
SOURCE_STREAM = "home_owner_memory_intents"
VALUE_SCHEMA = "HomelabCodenameV1"

REAL_ELIGIBLE = "REAL_ELIGIBLE"
REJECTED = "REJECTED"
DEFERRED = "DEFERRED"

LEARNING_V2_TABLES = frozenset({
    "learning_v2_schema_migration",
    "learning_memory_intent_v2",
    "learning_candidate_v2",
    "learning_project_codename_candidate_v1",
    "learning_candidate_source_v2",
    "learning_assessment_v2",
    "learning_proposal_ref",
    "learning_proposal_v2",
})

LEARNING_V2_SCHEMA_OBJECTS = frozenset({
    *LEARNING_V2_TABLES,
    "learning_memory_intent_v2_action",
    "learning_candidate_v2_idempotency",
    "learning_candidate_v2_action",
    "learning_proposal_ref_family",
    "learning_proposal_v2_candidate",
    "learning_proposal_v2_fingerprint",
    "learning_memory_intent_v2_no_update",
    "learning_memory_intent_v2_no_delete",
    "learning_candidate_v2_no_update",
    "learning_candidate_v2_no_delete",
    "learning_project_codename_candidate_v1_no_update",
    "learning_project_codename_candidate_v1_no_delete",
    "learning_candidate_source_v2_no_update",
    "learning_candidate_source_v2_no_delete",
    "learning_assessment_v2_no_update",
    "learning_assessment_v2_no_delete",
    "learning_proposal_ref_no_update",
    "learning_proposal_ref_no_delete",
    "learning_proposal_v2_no_update",
    "learning_proposal_v2_no_delete",
})

LEARNING_V2_MIGRATION_STATEMENTS = (
    """
    CREATE TABLE IF NOT EXISTS learning_v2_schema_migration (
        version INTEGER PRIMARY KEY,
        schema_fingerprint TEXT NOT NULL,
        applied_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS learning_memory_intent_v2 (
        intent_ref_id TEXT PRIMARY KEY,
        schema_version INTEGER NOT NULL CHECK(schema_version=1),
        source_owner TEXT NOT NULL CHECK(source_owner='MEMORY_INTERACTION_AUTHORITY'),
        source_stream TEXT NOT NULL CHECK(source_stream='home_owner_memory_intents'),
        actor_ref_id TEXT NOT NULL,
        actor_evidence_ref_id TEXT NOT NULL,
        operation TEXT NOT NULL CHECK(operation IN ('CREATE','SUPERSEDE','RESTORE')),
        memory_class TEXT NOT NULL,
        subject_namespace TEXT NOT NULL,
        subject_key TEXT NOT NULL,
        value_schema TEXT,
        normalized_value_json TEXT,
        payload_digest TEXT NOT NULL CHECK(length(payload_digest)=64),
        expected_active_revision_id TEXT,
        restore_revision_id TEXT,
        purpose TEXT NOT NULL CHECK(purpose='LONG_TERM_PERSONAL_PROJECT_RECALL'),
        action_digest TEXT NOT NULL CHECK(length(action_digest)=64),
        created_at TEXT NOT NULL,
        CHECK(
            (operation IN ('CREATE','SUPERSEDE') AND value_schema IS NOT NULL AND normalized_value_json IS NOT NULL)
            OR (operation='RESTORE' AND value_schema IS NULL AND normalized_value_json IS NULL)
        )
    )
    """,
    """CREATE UNIQUE INDEX IF NOT EXISTS learning_memory_intent_v2_action
        ON learning_memory_intent_v2(actor_evidence_ref_id,action_digest)""",
    """
    CREATE TABLE IF NOT EXISTS learning_candidate_v2 (
        candidate_id TEXT PRIMARY KEY,
        schema_version INTEGER NOT NULL CHECK(schema_version=1),
        candidate_class TEXT NOT NULL CHECK(candidate_class='OWNER_DIRECTED_MEMORY_CANDIDATE'),
        descriptor_family TEXT NOT NULL CHECK(descriptor_family='PROJECT_CODENAME_V1'),
        actor_ref_id TEXT NOT NULL,
        actor_evidence_ref_id TEXT NOT NULL,
        intent_ref_id TEXT NOT NULL REFERENCES learning_memory_intent_v2(intent_ref_id),
        policy_decision_ref_id TEXT NOT NULL,
        consent_ref_id TEXT NOT NULL,
        action_digest TEXT NOT NULL CHECK(length(action_digest)=64),
        admission_basis TEXT NOT NULL CHECK(admission_basis='OWNER_DIRECTED_EXACT_ACTION'),
        epistemic_basis TEXT NOT NULL CHECK(epistemic_basis='USER_ASSERTED'),
        validation_state TEXT NOT NULL CHECK(validation_state IN ('VALID','INVALID')),
        idempotency_key TEXT NOT NULL,
        created_at TEXT NOT NULL
    )
    """,
    """CREATE UNIQUE INDEX IF NOT EXISTS learning_candidate_v2_idempotency
        ON learning_candidate_v2(idempotency_key)""",
    """CREATE UNIQUE INDEX IF NOT EXISTS learning_candidate_v2_action
        ON learning_candidate_v2(action_digest)""",
    """
    CREATE TABLE IF NOT EXISTS learning_project_codename_candidate_v1 (
        candidate_id TEXT PRIMARY KEY REFERENCES learning_candidate_v2(candidate_id),
        operation TEXT NOT NULL CHECK(operation IN ('CREATE','SUPERSEDE','RESTORE')),
        memory_class TEXT NOT NULL,
        subject_namespace TEXT NOT NULL,
        subject_key TEXT NOT NULL,
        value_schema TEXT,
        payload_digest TEXT NOT NULL CHECK(length(payload_digest)=64),
        expected_active_revision_id TEXT,
        restore_revision_id TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS learning_candidate_source_v2 (
        candidate_id TEXT PRIMARY KEY REFERENCES learning_candidate_v2(candidate_id),
        source_owner TEXT NOT NULL CHECK(source_owner='MEMORY_INTERACTION_AUTHORITY'),
        source_stream TEXT NOT NULL CHECK(source_stream='home_owner_memory_intents'),
        source_ref_id TEXT NOT NULL REFERENCES learning_memory_intent_v2(intent_ref_id),
        source_digest TEXT NOT NULL CHECK(length(source_digest)=64),
        UNIQUE(source_owner,source_stream,source_ref_id,source_digest)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS learning_assessment_v2 (
        candidate_id TEXT PRIMARY KEY REFERENCES learning_candidate_v2(candidate_id),
        schema_version INTEGER NOT NULL CHECK(schema_version=1),
        outcome TEXT NOT NULL CHECK(outcome IN ('REAL_ELIGIBLE','REJECTED','DEFERRED')),
        reason_code TEXT NOT NULL,
        assessed_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS learning_proposal_ref (
        proposal_ref_id TEXT PRIMARY KEY,
        proposal_family TEXT NOT NULL CHECK(proposal_family IN ('L18_V1_CAREER','OWNER_DIRECTED_PROJECT_CODENAME_V1')),
        proposal_schema_version INTEGER NOT NULL CHECK(proposal_schema_version=1),
        family_proposal_id TEXT NOT NULL,
        immutable_fingerprint TEXT NOT NULL CHECK(length(immutable_fingerprint)=64),
        created_at TEXT NOT NULL,
        UNIQUE(proposal_family,family_proposal_id)
    )
    """,
    """CREATE INDEX IF NOT EXISTS learning_proposal_ref_family
        ON learning_proposal_ref(proposal_family,family_proposal_id)""",
    """
    CREATE TABLE IF NOT EXISTS learning_proposal_v2 (
        proposal_id TEXT PRIMARY KEY,
        schema_version INTEGER NOT NULL CHECK(schema_version=1),
        candidate_id TEXT NOT NULL REFERENCES learning_candidate_v2(candidate_id),
        intent_ref_id TEXT NOT NULL REFERENCES learning_memory_intent_v2(intent_ref_id),
        actor_ref_id TEXT NOT NULL,
        actor_evidence_ref_id TEXT NOT NULL,
        policy_decision_ref_id TEXT NOT NULL,
        consent_ref_id TEXT NOT NULL,
        rollback_authorization_ref_id TEXT,
        operation TEXT NOT NULL CHECK(operation IN ('CREATE','SUPERSEDE','RESTORE')),
        memory_class TEXT NOT NULL,
        subject_namespace TEXT NOT NULL,
        subject_key TEXT NOT NULL,
        value_schema TEXT,
        proposed_value_json TEXT,
        payload_digest TEXT NOT NULL CHECK(length(payload_digest)=64),
        expected_active_revision_id TEXT,
        restore_revision_id TEXT,
        purpose TEXT NOT NULL CHECK(purpose='LONG_TERM_PERSONAL_PROJECT_RECALL'),
        action_digest TEXT NOT NULL CHECK(length(action_digest)=64),
        proposal_fingerprint TEXT NOT NULL CHECK(length(proposal_fingerprint)=64),
        created_at TEXT NOT NULL,
        CHECK(
            (operation IN ('CREATE','SUPERSEDE') AND value_schema IS NOT NULL AND proposed_value_json IS NOT NULL AND rollback_authorization_ref_id IS NULL)
            OR (operation='RESTORE' AND value_schema IS NULL AND proposed_value_json IS NULL AND rollback_authorization_ref_id IS NOT NULL)
        )
    )
    """,
    """CREATE UNIQUE INDEX IF NOT EXISTS learning_proposal_v2_candidate
        ON learning_proposal_v2(candidate_id)""",
    """CREATE UNIQUE INDEX IF NOT EXISTS learning_proposal_v2_fingerprint
        ON learning_proposal_v2(proposal_fingerprint)""",
    """CREATE TRIGGER IF NOT EXISTS learning_memory_intent_v2_no_update
        BEFORE UPDATE ON learning_memory_intent_v2 BEGIN SELECT RAISE(ABORT,'memory intent is immutable'); END""",
    """CREATE TRIGGER IF NOT EXISTS learning_memory_intent_v2_no_delete
        BEFORE DELETE ON learning_memory_intent_v2 BEGIN SELECT RAISE(ABORT,'memory intent deletion requires Privacy authority'); END""",
    """CREATE TRIGGER IF NOT EXISTS learning_candidate_v2_no_update
        BEFORE UPDATE ON learning_candidate_v2 BEGIN SELECT RAISE(ABORT,'V2 candidate is immutable'); END""",
    """CREATE TRIGGER IF NOT EXISTS learning_candidate_v2_no_delete
        BEFORE DELETE ON learning_candidate_v2 BEGIN SELECT RAISE(ABORT,'V2 candidate deletion requires Privacy authority'); END""",
    """CREATE TRIGGER IF NOT EXISTS learning_project_codename_candidate_v1_no_update
        BEFORE UPDATE ON learning_project_codename_candidate_v1 BEGIN SELECT RAISE(ABORT,'typed descriptor is immutable'); END""",
    """CREATE TRIGGER IF NOT EXISTS learning_project_codename_candidate_v1_no_delete
        BEFORE DELETE ON learning_project_codename_candidate_v1 BEGIN SELECT RAISE(ABORT,'typed descriptor deletion requires Privacy authority'); END""",
    """CREATE TRIGGER IF NOT EXISTS learning_candidate_source_v2_no_update
        BEFORE UPDATE ON learning_candidate_source_v2 BEGIN SELECT RAISE(ABORT,'V2 provenance is immutable'); END""",
    """CREATE TRIGGER IF NOT EXISTS learning_candidate_source_v2_no_delete
        BEFORE DELETE ON learning_candidate_source_v2 BEGIN SELECT RAISE(ABORT,'V2 provenance deletion requires Privacy authority'); END""",
    """CREATE TRIGGER IF NOT EXISTS learning_assessment_v2_no_update
        BEFORE UPDATE ON learning_assessment_v2 BEGIN SELECT RAISE(ABORT,'V2 assessment is immutable'); END""",
    """CREATE TRIGGER IF NOT EXISTS learning_assessment_v2_no_delete
        BEFORE DELETE ON learning_assessment_v2 BEGIN SELECT RAISE(ABORT,'V2 assessment deletion requires Privacy authority'); END""",
    """CREATE TRIGGER IF NOT EXISTS learning_proposal_ref_no_update
        BEFORE UPDATE ON learning_proposal_ref BEGIN SELECT RAISE(ABORT,'proposal ref is immutable'); END""",
    """CREATE TRIGGER IF NOT EXISTS learning_proposal_ref_no_delete
        BEFORE DELETE ON learning_proposal_ref BEGIN SELECT RAISE(ABORT,'proposal ref deletion requires Privacy authority'); END""",
    """CREATE TRIGGER IF NOT EXISTS learning_proposal_v2_no_update
        BEFORE UPDATE ON learning_proposal_v2 BEGIN SELECT RAISE(ABORT,'V2 proposal is immutable'); END""",
    """CREATE TRIGGER IF NOT EXISTS learning_proposal_v2_no_delete
        BEFORE DELETE ON learning_proposal_v2 BEGIN SELECT RAISE(ABORT,'V2 proposal deletion requires Privacy authority'); END""",
)


class LearningV2Error(RuntimeError):
    pass


def utc_now(value: Optional[datetime] = None) -> str:
    stamp = value or datetime.now(timezone.utc)
    if stamp.tzinfo is None:
        stamp = stamp.replace(tzinfo=timezone.utc)
    return stamp.astimezone(timezone.utc).isoformat(timespec="microseconds").replace(
        "+00:00", "Z"
    )


def normalize_project_codename(value: Mapping[str, Any]) -> Tuple[str, str]:
    """Closed test/future contract; this function does not activate a class."""
    if not isinstance(value, Mapping) or set(value) != {"codename"}:
        raise LearningV2Error("HomelabCodenameV1 requires exactly codename")
    raw = value.get("codename")
    if not isinstance(raw, str):
        raise LearningV2Error("codename must be text")
    normalized = unicodedata.normalize("NFC", raw.strip())
    if not 1 <= len(normalized) <= 64:
        raise LearningV2Error("codename length is invalid")
    if any(
        unicodedata.category(ch) in {"Cc", "Cf", "Co", "Cs"}
        or ch in "\r\n\t"
        for ch in normalized
    ):
        raise LearningV2Error("codename contains prohibited characters")
    allowed_punctuation = {".", "_", "-", " "}
    for ch in normalized:
        if not (unicodedata.category(ch)[0] in {"L", "M", "N"} or ch in allowed_punctuation):
            raise LearningV2Error("codename character is unsupported")
    if not (
        unicodedata.category(normalized[0])[0] in {"L", "N"}
        and unicodedata.category(normalized[-1])[0] in {"L", "N"}
    ):
        raise LearningV2Error("codename endpoints must be letters or numbers")
    lowered = normalized.lower()
    if "://" in lowered or "@" in normalized or "{" in normalized or "}" in normalized:
        raise LearningV2Error("codename resembles an unsupported structured value")
    encoded = json.dumps(
        {"codename": normalized},
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    )
    return encoded, hashlib.sha256(encoded.encode("ascii")).hexdigest()


@dataclass(frozen=True)
class MemoryIntentV1:
    intent_ref_id: str
    action: C.FrozenMemoryActionV1
    actor_evidence_ref_id: str
    normalized_value_json: Optional[str]
    created_at: str


@dataclass(frozen=True)
class LearningCandidateV2:
    candidate_id: str
    action: C.FrozenMemoryActionV1
    actor_evidence_ref_id: str
    intent_ref_id: str
    policy_decision_ref_id: str
    consent_ref_id: str
    validation_state: str
    idempotency_key: str
    created_at: str


@dataclass(frozen=True)
class MemoryWriteProposalV2:
    proposal_id: str
    candidate_id: str
    intent_ref_id: str
    action: C.FrozenMemoryActionV1
    actor_evidence_ref_id: str
    policy_decision_ref_id: str
    consent_ref_id: str
    rollback_authorization_ref_id: Optional[str]
    proposed_value_json: Optional[str]
    proposal_fingerprint: str
    created_at: str


@dataclass(frozen=True)
class ProposalRefV1:
    proposal_ref_id: str
    proposal_family: str
    proposal_schema_version: int
    family_proposal_id: str
    immutable_fingerprint: str
    created_at: str


def _authorizer(
    action: int,
    arg1: Optional[str],
    arg2: Optional[str],
    database: Optional[str],
    trigger: Optional[str],
) -> int:
    del arg2, database, trigger
    table = str(arg1 or "")
    readable = LEARNING_V2_TABLES | {"learning_proposal", "sqlite_master"}
    writable = LEARNING_V2_TABLES - {"learning_v2_schema_migration"}
    if action == sqlite3.SQLITE_READ:
        return sqlite3.SQLITE_OK if table in readable else sqlite3.SQLITE_DENY
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


class LearningV2Store:
    def __init__(
        self,
        path: Path,
        *,
        privacy_hold_resolver: Optional[Any] = None,
        containment_ready: Callable[[], bool] = lambda: False,
        actor_authority: Optional[Any] = None,
        policy_store: Optional[Any] = None,
        consent_store: Optional[Any] = None,
        now_fn: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
    ):
        self.path = Path(path)
        self.privacy_hold_resolver = privacy_hold_resolver
        self.containment_ready = containment_ready
        self.actor_authority = actor_authority
        self.policy_store = policy_store
        self.consent_store = consent_store
        self.now_fn = now_fn

    def connect(self) -> sqlite3.Connection:
        if not self.path.is_file():
            raise LearningV2Error("L18 V2 database is unavailable")
        conn = sqlite3.connect(str(self.path), timeout=5.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        existing = {
            str(row[0])
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
            )
        }
        if not LEARNING_V2_TABLES.issubset(existing):
            conn.close()
            raise LearningV2Error("L18 V2 schema is unavailable")
        conn.set_authorizer(_authorizer)
        return conn

    def create_intent(
        self,
        *,
        action: C.FrozenMemoryActionV1,
        actor_evidence_ref_id: str,
        normalized_value_json: Optional[str],
        intent_ref_id: Optional[str] = None,
    ) -> MemoryIntentV1:
        action.validate()
        C.require_id(actor_evidence_ref_id, "actorEvidenceRefId")
        if intent_ref_id is not None:
            C.require_id(intent_ref_id, "intentRefId")
        if action.operation in {C.CREATE, C.SUPERSEDE}:
            if normalized_value_json is None:
                raise LearningV2Error("value-bearing intent requires normalized value")
            try:
                value = json.loads(normalized_value_json)
            except (TypeError, ValueError) as exc:
                raise LearningV2Error("intent value is invalid JSON") from exc
            canonical, digest = normalize_project_codename(value)
            if canonical != normalized_value_json or digest != action.payload_digest:
                raise LearningV2Error("intent payload/action digest mismatch")
        elif normalized_value_json is not None:
            raise LearningV2Error("RESTORE intent cannot carry plaintext")
        intent = MemoryIntentV1(
            intent_ref_id=intent_ref_id or ("intent." + uuid.uuid4().hex),
            action=action,
            actor_evidence_ref_id=actor_evidence_ref_id,
            normalized_value_json=normalized_value_json,
            created_at=utc_now(self.now_fn()),
        )
        conn = self.connect()
        try:
            conn.execute(
                "INSERT INTO learning_memory_intent_v2 VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    intent.intent_ref_id,
                    1,
                    C.MEMORY_INTERACTION_AUTHORITY,
                    SOURCE_STREAM,
                    action.actor_ref_id,
                    actor_evidence_ref_id,
                    action.operation,
                    action.memory_class,
                    action.subject_namespace,
                    action.subject_key,
                    action.value_schema,
                    normalized_value_json,
                    action.payload_digest,
                    action.expected_active_revision_id,
                    action.restore_revision_id,
                    action.purpose,
                    action.action_digest,
                    intent.created_at,
                ),
            )
            conn.commit()
        finally:
            conn.close()
        return intent

    def create_candidate(
        self,
        *,
        action: C.FrozenMemoryActionV1,
        actor_evidence_ref_id: str,
        intent_ref_id: str,
        policy_decision_ref_id: str,
        consent_ref_id: str,
        validation_state: str = "VALID",
    ) -> LearningCandidateV2:
        action.validate()
        for field, value in (
            ("actorEvidenceRefId", actor_evidence_ref_id),
            ("intentRefId", intent_ref_id),
            ("policyDecisionRefId", policy_decision_ref_id),
            ("consentRefId", consent_ref_id),
        ):
            C.require_id(value, field)
        if validation_state not in {"VALID", "INVALID"}:
            raise LearningV2Error("candidate validation state is unsupported")
        conn = self.connect()
        try:
            intent = conn.execute(
                "SELECT * FROM learning_memory_intent_v2 WHERE intent_ref_id=?",
                (intent_ref_id,),
            ).fetchone()
            exact_intent = (
                intent is not None
                and str(intent["actor_ref_id"]) == action.actor_ref_id
                and str(intent["actor_evidence_ref_id"]) == actor_evidence_ref_id
                and str(intent["operation"]) == action.operation
                and str(intent["memory_class"]) == action.memory_class
                and str(intent["subject_namespace"]) == action.subject_namespace
                and str(intent["subject_key"]) == action.subject_key
                and intent["value_schema"] == action.value_schema
                and str(intent["payload_digest"]) == action.payload_digest
                and intent["expected_active_revision_id"] == action.expected_active_revision_id
                and intent["restore_revision_id"] == action.restore_revision_id
                and str(intent["purpose"]) == action.purpose
                and str(intent["action_digest"]) == action.action_digest
            )
            if not exact_intent:
                raise LearningV2Error("candidate intent/action mismatch")
            if self.actor_authority is None or self.policy_store is None or self.consent_store is None:
                raise LearningV2Error("L18 V2 authority resolvers are unavailable")
            try:
                self.actor_authority.validate_existing(
                    actor_evidence_ref_id, action=action, require_consumed=True
                )
            except Exception as exc:
                raise LearningV2Error("candidate actor binding is invalid") from exc
            policy = self.policy_store.resolve(
                policy_decision_ref_id,
                action=action,
                capability=C.CANONICAL_MEMORY_PROJECT_CODENAME_MUTATE,
            )
            if getattr(policy, "status", None) != "CONFIRMED":
                raise LearningV2Error("candidate Policy binding is invalid")
            consent = self.consent_store.resolve(
                consent_ref_id,
                action=action,
                intent_ref_id=intent_ref_id,
                actor_evidence_ref_id=actor_evidence_ref_id,
            )
            if getattr(consent, "status", None) != "CONFIRMED":
                raise LearningV2Error("candidate Consent binding is invalid")
            candidate = LearningCandidateV2(
                candidate_id="candidate.v2." + uuid.uuid4().hex,
                action=action,
                actor_evidence_ref_id=actor_evidence_ref_id,
                intent_ref_id=intent_ref_id,
                policy_decision_ref_id=policy_decision_ref_id,
                consent_ref_id=consent_ref_id,
                validation_state=validation_state,
                idempotency_key="action." + action.action_digest,
                created_at=utc_now(self.now_fn()),
            )
            conn.execute("BEGIN IMMEDIATE")
            conn.execute(
                "INSERT INTO learning_candidate_v2 VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    candidate.candidate_id,
                    1,
                    CANDIDATE_CLASS,
                    "PROJECT_CODENAME_V1",
                    action.actor_ref_id,
                    actor_evidence_ref_id,
                    intent_ref_id,
                    policy_decision_ref_id,
                    consent_ref_id,
                    action.action_digest,
                    "OWNER_DIRECTED_EXACT_ACTION",
                    "USER_ASSERTED",
                    validation_state,
                    candidate.idempotency_key,
                    candidate.created_at,
                ),
            )
            conn.execute(
                "INSERT INTO learning_project_codename_candidate_v1 VALUES (?,?,?,?,?,?,?,?,?)",
                (
                    candidate.candidate_id,
                    action.operation,
                    action.memory_class,
                    action.subject_namespace,
                    action.subject_key,
                    action.value_schema,
                    action.payload_digest,
                    action.expected_active_revision_id,
                    action.restore_revision_id,
                ),
            )
            conn.execute(
                "INSERT INTO learning_candidate_source_v2 VALUES (?,?,?,?,?)",
                (
                    candidate.candidate_id,
                    C.MEMORY_INTERACTION_AUTHORITY,
                    SOURCE_STREAM,
                    intent_ref_id,
                    action.action_digest,
                ),
            )
            conn.commit()
            return candidate
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
    def assess(
        self,
        candidate_id: str,
        *,
        requested_outcome: str = REAL_ELIGIBLE,
    ) -> str:
        if requested_outcome not in {REAL_ELIGIBLE, REJECTED, DEFERRED}:
            raise LearningV2Error("assessment outcome is unsupported")
        conn = self.connect()
        try:
            candidate = conn.execute(
                "SELECT c.*,d.memory_class,d.subject_namespace,d.subject_key "
                "FROM learning_candidate_v2 c JOIN learning_project_codename_candidate_v1 d "
                "ON d.candidate_id=c.candidate_id WHERE c.candidate_id=?",
                (candidate_id,),
            ).fetchone()
            if candidate is None:
                raise LearningV2Error("candidate not found")
            held = False
            if self.privacy_hold_resolver is not None:
                held = bool(self.privacy_hold_resolver.is_held(
                    str(candidate["memory_class"]),
                    str(candidate["subject_namespace"]),
                    str(candidate["subject_key"]),
                ))
            if str(candidate["validation_state"]) != "VALID":
                outcome, reason = REJECTED, "CANDIDATE_INVALID"
            elif held:
                outcome, reason = REJECTED, "PRIVACY_HOLD_ACTIVE"
            elif not self.containment_ready():
                outcome, reason = DEFERRED, "LEGACY_CONTAINMENT_NOT_READY"
            else:
                outcome, reason = requested_outcome, "AUTHORITY_FOUNDATIONS_READY"
            conn.execute(
                "INSERT INTO learning_assessment_v2 VALUES (?,?,?,?,?)",
                (candidate_id, 1, outcome, reason, utc_now(self.now_fn())),
            )
            conn.commit()
            return outcome
        finally:
            conn.close()

    def create_proposal(
        self,
        *,
        candidate_id: str,
        action: C.FrozenMemoryActionV1,
        rollback_authorization_ref_id: Optional[str] = None,
    ) -> Tuple[MemoryWriteProposalV2, ProposalRefV1]:
        action.validate()
        conn = self.connect()
        try:
            row = conn.execute(
                "SELECT c.*,d.operation,d.memory_class,d.subject_namespace,d.subject_key,"
                "d.value_schema,d.payload_digest,d.expected_active_revision_id,d.restore_revision_id,"
                "i.normalized_value_json,a.outcome FROM learning_candidate_v2 c "
                "JOIN learning_project_codename_candidate_v1 d ON d.candidate_id=c.candidate_id "
                "JOIN learning_memory_intent_v2 i ON i.intent_ref_id=c.intent_ref_id "
                "JOIN learning_assessment_v2 a ON a.candidate_id=c.candidate_id "
                "WHERE c.candidate_id=?",
                (candidate_id,),
            ).fetchone()
            if row is None or str(row["outcome"]) != REAL_ELIGIBLE:
                raise LearningV2Error("candidate is not REAL_ELIGIBLE")
            descriptor_exact = (
                str(row["action_digest"]) == action.action_digest
                and str(row["actor_ref_id"]) == action.actor_ref_id
                and str(row["operation"]) == action.operation
                and str(row["memory_class"]) == action.memory_class
                and str(row["subject_namespace"]) == action.subject_namespace
                and str(row["subject_key"]) == action.subject_key
                and row["value_schema"] == action.value_schema
                and str(row["payload_digest"]) == action.payload_digest
                and row["expected_active_revision_id"] == action.expected_active_revision_id
                and row["restore_revision_id"] == action.restore_revision_id
            )
            if not descriptor_exact:
                raise LearningV2Error("candidate action changed")
            if action.operation == C.RESTORE and not rollback_authorization_ref_id:
                raise LearningV2Error("RESTORE proposal requires rollback authority")
            if action.operation != C.RESTORE and rollback_authorization_ref_id is not None:
                raise LearningV2Error("non-RESTORE proposal cannot carry rollback authority")
            proposal_id = "proposal.v2." + uuid.uuid4().hex
            created_at = utc_now(self.now_fn())
            semantic = {
                "proposalSchemaVersion": 1,
                "candidateId": candidate_id,
                "intentRefId": str(row["intent_ref_id"]),
                "actorRefId": action.actor_ref_id,
                "actorEvidenceRefId": str(row["actor_evidence_ref_id"]),
                "policyDecisionRefId": str(row["policy_decision_ref_id"]),
                "consentRefId": str(row["consent_ref_id"]),
                "rollbackAuthorizationRefId": rollback_authorization_ref_id,
                "action": action.semantic_dict(),
                "actionDigest": action.action_digest,
            }
            proposal = MemoryWriteProposalV2(
                proposal_id=proposal_id,
                candidate_id=candidate_id,
                intent_ref_id=str(row["intent_ref_id"]),
                action=action,
                actor_evidence_ref_id=str(row["actor_evidence_ref_id"]),
                policy_decision_ref_id=str(row["policy_decision_ref_id"]),
                consent_ref_id=str(row["consent_ref_id"]),
                rollback_authorization_ref_id=rollback_authorization_ref_id,
                proposed_value_json=row["normalized_value_json"],
                proposal_fingerprint=C.sha256_digest(semantic),
                created_at=created_at,
            )
            proposal_ref = ProposalRefV1(
                proposal_ref_id="proposal-ref." + uuid.uuid4().hex,
                proposal_family=V2_PROPOSAL_FAMILY,
                proposal_schema_version=1,
                family_proposal_id=proposal_id,
                immutable_fingerprint=proposal.proposal_fingerprint,
                created_at=created_at,
            )
            conn.execute("BEGIN IMMEDIATE")
            conn.execute(
                "INSERT INTO learning_proposal_v2 VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    proposal.proposal_id,
                    1,
                    proposal.candidate_id,
                    proposal.intent_ref_id,
                    action.actor_ref_id,
                    proposal.actor_evidence_ref_id,
                    proposal.policy_decision_ref_id,
                    proposal.consent_ref_id,
                    proposal.rollback_authorization_ref_id,
                    action.operation,
                    action.memory_class,
                    action.subject_namespace,
                    action.subject_key,
                    action.value_schema,
                    proposal.proposed_value_json,
                    action.payload_digest,
                    action.expected_active_revision_id,
                    action.restore_revision_id,
                    action.purpose,
                    action.action_digest,
                    proposal.proposal_fingerprint,
                    created_at,
                ),
            )
            conn.execute(
                "INSERT INTO learning_proposal_ref VALUES (?,?,?,?,?,?)",
                tuple(proposal_ref.__dict__.values()),
            )
            conn.commit()
            return proposal, proposal_ref
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def reference_v1_proposal(self, proposal_id: str) -> ProposalRefV1:
        """Reference an existing V1 proposal without changing its row or meaning."""
        conn = self.connect()
        try:
            row = conn.execute(
                "SELECT proposal_fingerprint,created_at FROM learning_proposal WHERE proposal_id=?",
                (proposal_id,),
            ).fetchone()
            if row is None:
                raise LearningV2Error("V1 proposal not found")
            ref = ProposalRefV1(
                proposal_ref_id="proposal-ref." + uuid.uuid4().hex,
                proposal_family=V1_PROPOSAL_FAMILY,
                proposal_schema_version=1,
                family_proposal_id=proposal_id,
                immutable_fingerprint=str(row["proposal_fingerprint"]),
                created_at=str(row["created_at"]),
            )
            conn.execute(
                "INSERT INTO learning_proposal_ref VALUES (?,?,?,?,?,?)",
                tuple(ref.__dict__.values()),
            )
            conn.commit()
            return ref
        finally:
            conn.close()

    def resolve_proposal_ref(self, proposal_ref_id: str) -> Tuple[ProposalRefV1, sqlite3.Row]:
        conn = self.connect()
        try:
            row = conn.execute(
                "SELECT * FROM learning_proposal_ref WHERE proposal_ref_id=?",
                (proposal_ref_id,),
            ).fetchone()
            if row is None:
                raise LearningV2Error("proposal ref not found")
            ref = ProposalRefV1(
                proposal_ref_id=str(row["proposal_ref_id"]),
                proposal_family=str(row["proposal_family"]),
                proposal_schema_version=int(row["proposal_schema_version"]),
                family_proposal_id=str(row["family_proposal_id"]),
                immutable_fingerprint=str(row["immutable_fingerprint"]),
                created_at=str(row["created_at"]),
            )
            if ref.proposal_family == V2_PROPOSAL_FAMILY:
                proposal = conn.execute(
                    "SELECT * FROM learning_proposal_v2 WHERE proposal_id=?",
                    (ref.family_proposal_id,),
                ).fetchone()
            elif ref.proposal_family == V1_PROPOSAL_FAMILY:
                proposal = conn.execute(
                    "SELECT * FROM learning_proposal WHERE proposal_id=?",
                    (ref.family_proposal_id,),
                ).fetchone()
            else:
                raise LearningV2Error("unknown proposal family")
            if proposal is None or str(proposal["proposal_fingerprint"]) != ref.immutable_fingerprint:
                raise LearningV2Error("proposal ref fingerprint mismatch")
            return ref, proposal
        finally:
            conn.close()
