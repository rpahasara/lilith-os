"""Family-neutral, atomic L04 V2 canonical-memory apply boundary."""

from __future__ import annotations

import json
import sqlite3
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, Optional, Tuple

from . import canonical_authority as A
from . import canonical_contracts as C
from . import canonical_migration
from . import learning_v2 as L
from . import memory_v2 as M


ACCEPTED = "ACCEPTED"
REJECTED = "REJECTED"
PRECONDITION_FAILED = "PRECONDITION_FAILED"
ALREADY_APPLIED = "ALREADY_APPLIED"
RETRYABLE_FAILURE = "RETRYABLE_FAILURE"


@dataclass(frozen=True)
class CanonicalApplyResult:
    proposal_ref_id: str
    outcome: str
    failure_code: Optional[str] = None
    memory_item_id: Optional[str] = None
    revision_id: Optional[str] = None
    active_revision_id: Optional[str] = None
    operation_id: Optional[str] = None


class CanonicalStoreError(RuntimeError):
    pass


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds").replace(
        "+00:00", "Z"
    )


_MEMORY_TABLES = frozenset(
    {
        "memory_item",
        "memory_revision",
        "memory_revision_source",
        "memory_admission",
        "memory_apply_audit",
        "memory_active_revision",
        "rollback_consumption",
    }
)
_READ_TABLES = _MEMORY_TABLES | frozenset(
    {
        "canonical_runtime_schema_migration",
        "learning_proposal_ref",
        "learning_proposal_v2",
        "learning_candidate_v2",
        "learning_project_codename_candidate_v1",
        "learning_candidate_source_v2",
        "learning_assessment_v2",
        "learning_memory_intent_v2",
        "rollback_authorization",
        "sqlite_master",
    }
)


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
        return sqlite3.SQLITE_OK if table in _READ_TABLES else sqlite3.SQLITE_DENY
    if action in {sqlite3.SQLITE_INSERT, sqlite3.SQLITE_UPDATE, sqlite3.SQLITE_DELETE}:
        return sqlite3.SQLITE_OK if table in _MEMORY_TABLES else sqlite3.SQLITE_DENY
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


class CanonicalMemoryStoreV2:
    """Apply one immutable V2 proposal reference as one SQLite transaction."""

    def __init__(
        self,
        path: Path,
        learning_store: L.LearningV2Store,
        *,
        enabled_provider: Callable[[], Optional[bool]],
        capability_provider: Callable[[str], bool],
        family_registry: M.ProposalFamilyRegistry,
        memory_registry: M.CanonicalTupleRegistry,
        containment_ready: Callable[[Tuple[str, str, str]], bool],
        actor_authority: A.LocalOwnerAuthority,
        policy_store: A.MemoryPolicyStore,
        consent_store: A.ConsentStore,
        rollback_authority: A.RollbackAuthority,
        privacy_hold_resolver: Any,
        capacity: int = 10_000,
        now_fn: Callable[[], str] = _utc_now,
        fault_hook: Optional[Callable[[str], None]] = None,
        busy_timeout_ms: int = 5_000,
    ):
        if isinstance(capacity, bool) or not isinstance(capacity, int) or capacity < 1:
            raise ValueError("capacity must be positive")
        if isinstance(busy_timeout_ms, bool) or int(busy_timeout_ms) < 0:
            raise ValueError("busy timeout is invalid")
        self.path = Path(path)
        self.learning_store = learning_store
        self.enabled_provider = enabled_provider
        self.capability_provider = capability_provider
        self.family_registry = family_registry
        self.memory_registry = memory_registry
        self.containment_ready = containment_ready
        self.actor_authority = actor_authority
        self.policy_store = policy_store
        self.consent_store = consent_store
        self.rollback_authority = rollback_authority
        self.privacy_hold_resolver = privacy_hold_resolver
        self.capacity = capacity
        self.now_fn = now_fn
        self.fault_hook = fault_hook
        self.busy_timeout_ms = int(busy_timeout_ms)

    def _connect(self) -> sqlite3.Connection:
        if not self.path.is_file():
            raise CanonicalStoreError("canonical database is unavailable")
        conn = sqlite3.connect(
            str(self.path), timeout=self.busy_timeout_ms / 1000.0
        )
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute(f"PRAGMA busy_timeout={self.busy_timeout_ms}")
        try:
            canonical_migration._verify_current_schema(conn)
        except Exception as exc:
            conn.close()
            raise CanonicalStoreError("canonical schema is unavailable") from exc
        conn.set_authorizer(_authorizer)
        return conn

    @staticmethod
    def _action(row: sqlite3.Row) -> C.FrozenMemoryActionV1:
        return C.FrozenMemoryActionV1(
            schema_version=1,
            actor_ref_id=str(row["actor_ref_id"]),
            operation=str(row["operation"]),
            memory_class=str(row["memory_class"]),
            subject_namespace=str(row["subject_namespace"]),
            subject_key=str(row["subject_key"]),
            value_schema=row["value_schema"],
            payload_digest=str(row["payload_digest"]),
            expected_active_revision_id=row["expected_active_revision_id"],
            restore_revision_id=row["restore_revision_id"],
            purpose=str(row["purpose"]),
        )

    @staticmethod
    def _result(
        proposal_ref_id: str,
        outcome: str,
        failure_code: Optional[str] = None,
        **values: Optional[str],
    ) -> CanonicalApplyResult:
        return CanonicalApplyResult(
            proposal_ref_id=proposal_ref_id,
            outcome=outcome,
            failure_code=failure_code,
            **values,
        )

    @staticmethod
    def _replay(conn: sqlite3.Connection, proposal_ref_id: str) -> Optional[CanonicalApplyResult]:
        row = conn.execute(
            "SELECT operation_id,memory_item_id,created_revision_id,"
            "resulting_active_revision_id FROM memory_apply_audit WHERE proposal_ref_id=?",
            (proposal_ref_id,),
        ).fetchone()
        if row is not None:
            return CanonicalApplyResult(
                proposal_ref_id=proposal_ref_id,
                outcome=ALREADY_APPLIED,
                memory_item_id=str(row["memory_item_id"]),
                revision_id=str(row["created_revision_id"]),
                active_revision_id=str(row["resulting_active_revision_id"]),
                operation_id=str(row["operation_id"]),
            )
        row = conn.execute(
            "SELECT outcome,failure_code FROM memory_admission WHERE proposal_ref_id=?",
            (proposal_ref_id,),
        ).fetchone()
        if row is not None and str(row["outcome"]) != ACCEPTED:
            return CanonicalApplyResult(
                proposal_ref_id=proposal_ref_id,
                outcome=str(row["outcome"]),
                failure_code=str(row["failure_code"]),
            )
        return None

    def _initial_replay(self, proposal_ref_id: str) -> Optional[CanonicalApplyResult]:
        try:
            conn = self._connect()
        except sqlite3.OperationalError:
            return self._result(proposal_ref_id, RETRYABLE_FAILURE, "DB_BUSY")
        try:
            return self._replay(conn, proposal_ref_id)
        finally:
            conn.close()

    @staticmethod
    def _proposal_fingerprint(row: sqlite3.Row, action: C.FrozenMemoryActionV1) -> str:
        return C.sha256_digest(
            {
                "proposalSchemaVersion": 1,
                "candidateId": str(row["candidate_id"]),
                "intentRefId": str(row["intent_ref_id"]),
                "actorRefId": action.actor_ref_id,
                "actorEvidenceRefId": str(row["actor_evidence_ref_id"]),
                "policyDecisionRefId": str(row["policy_decision_ref_id"]),
                "consentRefId": str(row["consent_ref_id"]),
                "rollbackAuthorizationRefId": row["rollback_authorization_ref_id"],
                "action": action.semantic_dict(),
                "actionDigest": action.action_digest,
            }
        )

    def _candidate_binding_exact(
        self, proposal: sqlite3.Row, action: C.FrozenMemoryActionV1
    ) -> bool:
        conn = self.learning_store.connect()
        try:
            row = conn.execute(
                "SELECT c.action_digest,c.actor_ref_id,c.actor_evidence_ref_id,"
                "c.policy_decision_ref_id,c.consent_ref_id,a.outcome,s.source_digest,"
                "s.source_owner,s.source_stream,s.source_ref_id,d.operation,d.memory_class,"
                "d.subject_namespace,d.subject_key,d.value_schema,d.payload_digest,"
                "d.expected_active_revision_id,d.restore_revision_id "
                "FROM learning_candidate_v2 c "
                "JOIN learning_project_codename_candidate_v1 d ON d.candidate_id=c.candidate_id "
                "JOIN learning_assessment_v2 a ON a.candidate_id=c.candidate_id "
                "JOIN learning_candidate_source_v2 s ON s.candidate_id=c.candidate_id "
                "WHERE c.candidate_id=?",
                (str(proposal["candidate_id"]),),
            ).fetchone()
            return bool(
                row is not None
                and str(row["action_digest"]) == action.action_digest
                and str(row["actor_ref_id"]) == action.actor_ref_id
                and str(row["actor_evidence_ref_id"])
                == str(proposal["actor_evidence_ref_id"])
                and str(row["policy_decision_ref_id"])
                == str(proposal["policy_decision_ref_id"])
                and str(row["consent_ref_id"]) == str(proposal["consent_ref_id"])
                and str(row["outcome"]) == L.REAL_ELIGIBLE
                and str(row["source_digest"]) == action.action_digest
                and str(row["operation"]) == action.operation
                and str(row["memory_class"]) == action.memory_class
                and str(row["subject_namespace"]) == action.subject_namespace
                and str(row["subject_key"]) == action.subject_key
                and row["value_schema"] == action.value_schema
                and str(row["payload_digest"]) == action.payload_digest
                and row["expected_active_revision_id"]
                == action.expected_active_revision_id
                and row["restore_revision_id"] == action.restore_revision_id
            )
        finally:
            conn.close()

    def _prevalidate(
        self, proposal_ref_id: str
    ) -> Tuple[sqlite3.Row, C.FrozenMemoryActionV1, M.MemoryTuplePolicyV1]:
        ref, proposal = self.learning_store.resolve_proposal_ref(proposal_ref_id)
        if not self.family_registry.permits(ref.proposal_family):
            raise CanonicalStoreError("UNKNOWN_PROPOSAL_FAMILY")
        if ref.proposal_family != L.V2_PROPOSAL_FAMILY:
            raise CanonicalStoreError("V1_DISPATCH_UNAVAILABLE")
        action = self._action(proposal)
        action.validate()
        if (
            ref.immutable_fingerprint != str(proposal["proposal_fingerprint"])
            or str(proposal["action_digest"]) != action.action_digest
            or str(proposal["proposal_fingerprint"])
            != self._proposal_fingerprint(proposal, action)
        ):
            raise CanonicalStoreError("PROPOSAL_FINGERPRINT_MISMATCH")
        policy = self.memory_registry.resolve(*action.identity)
        if policy is None or not policy.write_allowed:
            raise CanonicalStoreError("UNKNOWN_MEMORY_TUPLE")
        if policy.value_schema != (action.value_schema or policy.value_schema):
            raise CanonicalStoreError("UNKNOWN_VALUE_SCHEMA")
        try:
            capability_active = self.capability_provider(policy.capability)
        except Exception:
            capability_active = False
        if capability_active is not True:
            raise CanonicalStoreError("CAPABILITY_INACTIVE")
        try:
            containment_ready = self.containment_ready(action.identity)
        except Exception:
            containment_ready = False
        if containment_ready is not True:
            raise CanonicalStoreError("LEGACY_CONTAINMENT_NOT_READY")
        if self.privacy_hold_resolver.is_held(*action.identity):
            raise CanonicalStoreError("PRIVACY_HOLD_ACTIVE")
        if action.operation in {C.CREATE, C.SUPERSEDE}:
            try:
                canonical, digest = L.normalize_project_codename(
                    json.loads(str(proposal["proposed_value_json"]))
                )
            except Exception as exc:
                raise CanonicalStoreError("INVALID_PROPOSAL_VALUE") from exc
            if canonical != str(proposal["proposed_value_json"]) or digest != action.payload_digest:
                raise CanonicalStoreError("PROPOSAL_VALUE_DIGEST_MISMATCH")
        try:
            self.actor_authority.validate_existing(
                str(proposal["actor_evidence_ref_id"]),
                action=action,
                require_consumed=True,
            )
        except Exception as exc:
            raise CanonicalStoreError("ACTOR_UNRESOLVED") from exc
        if self.policy_store.resolve(
            str(proposal["policy_decision_ref_id"]),
            action=action,
            capability=policy.capability,
        ).status != A.CONFIRMED:
            raise CanonicalStoreError("POLICY_DECISION_INVALID")
        consent = self.consent_store.resolve(
            str(proposal["consent_ref_id"]),
            action=action,
            intent_ref_id=str(proposal["intent_ref_id"]),
            actor_evidence_ref_id=str(proposal["actor_evidence_ref_id"]),
        )
        if consent.status != A.CONFIRMED:
            raise CanonicalStoreError(
                "CONSENT_REVOKED" if consent.status == A.REVOKED else "CONSENT_INVALID"
            )
        if not self._candidate_binding_exact(proposal, action):
            raise CanonicalStoreError("CANDIDATE_BINDING_INVALID")
        return proposal, action, policy

    def apply(self, proposal_ref_id: str) -> CanonicalApplyResult:
        """Apply a V2 proposal reference; no caller-controlled authority inputs."""
        try:
            enabled = self.enabled_provider()
        except Exception:
            enabled = None
        if enabled is not True:
            return self._result(proposal_ref_id, REJECTED, "CANONICAL_LTM_DISABLED")
        replay = self._initial_replay(proposal_ref_id)
        if replay is not None:
            return replay
        try:
            conn = self._connect()
            conn.execute("BEGIN IMMEDIATE")
        except sqlite3.OperationalError:
            try:
                conn.close()
            except UnboundLocalError:
                pass
            return self._result(proposal_ref_id, RETRYABLE_FAILURE, "DB_BUSY")
        try:
            replay = self._replay(conn, proposal_ref_id)
            if replay is not None:
                conn.rollback()
                return replay
            try:
                proposal, action, policy = self._prevalidate(proposal_ref_id)
            except (
                CanonicalStoreError,
                L.LearningV2Error,
                C.ContractError,
                ValueError,
            ) as exc:
                code = str(exc) if str(exc) else "PROPOSAL_REF_INVALID"
                if code not in {
                    "UNKNOWN_PROPOSAL_FAMILY",
                    "V1_DISPATCH_UNAVAILABLE",
                    "PROPOSAL_FINGERPRINT_MISMATCH",
                    "UNKNOWN_MEMORY_TUPLE",
                    "UNKNOWN_VALUE_SCHEMA",
                    "CAPABILITY_INACTIVE",
                    "LEGACY_CONTAINMENT_NOT_READY",
                    "PRIVACY_HOLD_ACTIVE",
                    "INVALID_PROPOSAL_VALUE",
                    "PROPOSAL_VALUE_DIGEST_MISMATCH",
                    "ACTOR_UNRESOLVED",
                    "POLICY_DECISION_INVALID",
                    "CONSENT_REVOKED",
                    "CONSENT_INVALID",
                    "CANDIDATE_BINDING_INVALID",
                }:
                    conn.rollback()
                    return self._result(
                        proposal_ref_id, REJECTED, "PROPOSAL_REF_INVALID"
                    )
                conn.execute(
                    "INSERT INTO memory_admission VALUES (?,?,?,?,?,?)",
                    (
                        "madm." + uuid.uuid4().hex,
                        proposal_ref_id,
                        1,
                        REJECTED,
                        code,
                        self.now_fn(),
                    ),
                )
                conn.commit()
                return self._result(proposal_ref_id, REJECTED, code)
            item = conn.execute(
                "SELECT memory_item_id FROM memory_item WHERE memory_class=? "
                "AND subject_namespace=? AND subject_key=?",
                action.identity,
            ).fetchone()
            item_id = str(item[0]) if item is not None else None
            active = None
            if item_id is not None:
                active = conn.execute(
                    "SELECT revision_id FROM memory_active_revision WHERE memory_item_id=?",
                    (item_id,),
                ).fetchone()
            current_revision_id = str(active[0]) if active is not None else None
            failure = None
            if action.operation == C.CREATE:
                if item_id is not None or current_revision_id is not None:
                    failure = "MEMORY_ALREADY_EXISTS"
                elif int(conn.execute("SELECT COUNT(*) FROM memory_item").fetchone()[0]) >= self.capacity:
                    failure = "CAPACITY_EXCEEDED"
            elif item_id is None or current_revision_id is None:
                failure = "MEMORY_NOT_FOUND"
            elif current_revision_id != action.expected_active_revision_id:
                failure = "STALE_EXPECTED_REVISION"

            historical = None
            if failure is None and action.operation == C.RESTORE:
                historical = conn.execute(
                    "SELECT * FROM memory_revision WHERE revision_id=?",
                    (action.restore_revision_id,),
                ).fetchone()
                if historical is None or str(historical["memory_item_id"]) != item_id:
                    failure = "RESTORE_REVISION_NOT_FOUND"
                elif str(historical["value_digest"]) != action.payload_digest:
                    failure = "RESTORE_DIGEST_MISMATCH"
                elif not proposal["rollback_authorization_ref_id"]:
                    failure = "ROLLBACK_NOT_AUTHORIZED"
                else:
                    rollback = self.rollback_authority.resolve_and_consume_in_transaction(
                        conn,
                        str(proposal["rollback_authorization_ref_id"]),
                        action=action,
                        memory_item_id=str(item_id),
                        consumer_ref="l04.v2.apply",
                    )
                    if rollback.status != A.CONFIRMED:
                        failure = rollback.failure_code or "ROLLBACK_NOT_AUTHORIZED"
            if failure is not None:
                conn.execute(
                    "INSERT INTO memory_admission VALUES (?,?,?,?,?,?)",
                    (
                        "madm." + uuid.uuid4().hex,
                        proposal_ref_id,
                        1,
                        PRECONDITION_FAILED,
                        failure,
                        self.now_fn(),
                    ),
                )
                conn.commit()
                return self._result(proposal_ref_id, PRECONDITION_FAILED, failure)

            if self.privacy_hold_resolver.is_held(*action.identity):
                conn.execute(
                    "INSERT INTO memory_admission VALUES (?,?,?,?,?,?)",
                    (
                        "madm." + uuid.uuid4().hex,
                        proposal_ref_id,
                        1,
                        REJECTED,
                        "PRIVACY_HOLD_ACTIVE",
                        self.now_fn(),
                    ),
                )
                conn.commit()
                return self._result(proposal_ref_id, REJECTED, "PRIVACY_HOLD_ACTIVE")

            now = self.now_fn()
            item_id = item_id or ("mitem." + uuid.uuid4().hex)
            revision_id = "mrev." + uuid.uuid4().hex
            admission_id = "madm." + uuid.uuid4().hex
            operation_id = "mop." + uuid.uuid4().hex
            if action.operation == C.CREATE:
                conn.execute(
                    "INSERT INTO memory_item VALUES (?,?,?,?,?)",
                    (item_id, *action.identity, now),
                )
            if historical is not None:
                value_schema = str(historical["value_schema"])
                normalized_value_json = str(historical["normalized_value_json"])
                value_digest = str(historical["value_digest"])
            else:
                value_schema = str(action.value_schema)
                normalized_value_json = str(proposal["proposed_value_json"])
                value_digest = action.payload_digest
            conn.execute(
                "INSERT INTO memory_admission VALUES (?,?,?,?,?,?)",
                (admission_id, proposal_ref_id, 1, ACCEPTED, None, now),
            )
            conn.execute(
                "INSERT INTO memory_revision VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    revision_id,
                    item_id,
                    1,
                    value_schema,
                    normalized_value_json,
                    value_digest,
                    proposal_ref_id,
                    current_revision_id,
                    action.restore_revision_id if action.operation == C.RESTORE else None,
                    "USER_ASSERTED",
                    "OWNER_DIRECTED_EXACT_ACTION",
                    str(proposal["consent_ref_id"]),
                    str(proposal["policy_decision_ref_id"]),
                    proposal["rollback_authorization_ref_id"],
                    now,
                ),
            )
            source = conn.execute(
                "SELECT source_owner,source_stream,source_ref_id,source_digest "
                "FROM learning_candidate_source_v2 WHERE candidate_id=?",
                (str(proposal["candidate_id"]),),
            ).fetchone()
            source_record_id = int(str(source["source_digest"])[:15], 16) + 1
            intent = conn.execute(
                "SELECT created_at FROM learning_memory_intent_v2 WHERE intent_ref_id=?",
                (str(source["source_ref_id"]),),
            ).fetchone()
            conn.execute(
                "INSERT INTO memory_revision_source VALUES (?,?,?,?,?,?,?,?,?)",
                (
                    revision_id,
                    0,
                    str(source["source_owner"]),
                    str(source["source_stream"]),
                    source_record_id,
                    1,
                    str(source["source_digest"]),
                    str(intent["created_at"]),
                    f"{action.subject_namespace}:{action.subject_key}",
                ),
            )
            if self.fault_hook:
                self.fault_hook("after_revision")
            conn.execute(
                "INSERT INTO memory_apply_audit VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (
                    operation_id,
                    proposal_ref_id,
                    admission_id,
                    1,
                    action.operation,
                    item_id,
                    current_revision_id,
                    revision_id,
                    revision_id,
                    proposal["rollback_authorization_ref_id"],
                    now,
                ),
            )
            if action.operation == C.CREATE:
                conn.execute(
                    "INSERT INTO memory_active_revision VALUES (?,?,?,?)",
                    (item_id, revision_id, now, operation_id),
                )
            else:
                conn.execute(
                    "UPDATE memory_active_revision SET revision_id=?,updated_at=?,"
                    "last_operation_id=? WHERE memory_item_id=?",
                    (revision_id, now, operation_id, item_id),
                )
            if self.fault_hook:
                self.fault_hook("before_commit")
            if self.privacy_hold_resolver.is_held(*action.identity):
                raise CanonicalStoreError("PRIVACY_HOLD_ACTIVE")
            conn.commit()
            return CanonicalApplyResult(
                proposal_ref_id=proposal_ref_id,
                outcome=ACCEPTED,
                memory_item_id=item_id,
                revision_id=revision_id,
                active_revision_id=revision_id,
                operation_id=operation_id,
            )
        except sqlite3.OperationalError as exc:
            conn.rollback()
            if "locked" in str(exc).lower() or "busy" in str(exc).lower():
                return self._result(proposal_ref_id, RETRYABLE_FAILURE, "DB_BUSY")
            raise
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def get_active(
        self, memory_class: str, subject_namespace: str, subject_key: str
    ) -> Optional[Dict[str, Any]]:
        """Internal exact-key read only; there is deliberately no fallback."""
        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT i.memory_item_id,i.memory_class,i.subject_namespace,i.subject_key,"
                "r.revision_id,r.value_schema,r.normalized_value_json,r.value_digest,"
                "r.consent_ref_id,r.created_at FROM memory_item i "
                "JOIN memory_active_revision a ON a.memory_item_id=i.memory_item_id "
                "JOIN memory_revision r ON r.revision_id=a.revision_id "
                "WHERE i.memory_class=? AND i.subject_namespace=? AND i.subject_key=?",
                (memory_class, subject_namespace, subject_key),
            ).fetchone()
            return dict(row) if row is not None else None
        finally:
            conn.close()

    def resolve_restore_state(
        self, action: C.FrozenMemoryActionV1
    ) -> Optional[Dict[str, str]]:
        """Resolve exact current and historical state without consuming authority."""
        if action.operation != C.RESTORE:
            raise ValueError("restore state resolver is RESTORE-only")
        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT i.memory_item_id,a.revision_id AS current_revision_id,"
                "h.revision_id AS restore_revision_id,h.value_digest AS target_value_digest "
                "FROM memory_item i "
                "JOIN memory_active_revision a ON a.memory_item_id=i.memory_item_id "
                "JOIN memory_revision h ON h.memory_item_id=i.memory_item_id "
                "WHERE i.memory_class=? AND i.subject_namespace=? AND i.subject_key=? "
                "AND h.revision_id=?",
                (*action.identity, action.restore_revision_id),
            ).fetchone()
            return dict(row) if row is not None else None
        finally:
            conn.close()
