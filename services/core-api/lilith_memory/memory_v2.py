"""L04 Slice 15B2a full-tuple registry, V2 gate, read facade, and erasure owner.

The V2 gate performs independent authority resolution but deliberately has no
production mutation bridge in 15B2a.  Existing Slice 15B1 CREATE/SUPERSEDE/
RESTORE mechanics remain the isolated storage proof while the production kill
switch and both production registries remain empty/false.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, FrozenSet, Iterable, Mapping, Optional, Tuple

try:
    from . import canonical_contracts as C
    from . import canonical_authority as A
    from . import learning_v2 as L
except ImportError:  # deploy-exact flat-directory tests
    import canonical_contracts as C
    import canonical_authority as A
    import learning_v2 as L


SCHEMA_VERSION = 1
ACCEPTED = "ACCEPTED"
REJECTED = "REJECTED"

REGISTRY_TABLES = frozenset({
    "memory_registry_schema_migration",
    "memory_registry_entry",
})
REGISTRY_SCHEMA_OBJECTS = frozenset({
    *REGISTRY_TABLES,
    "memory_registry_exact_tuple",
    "memory_registry_entry_no_update",
    "memory_registry_entry_no_delete",
})
REGISTRY_MIGRATION_STATEMENTS = (
    """
    CREATE TABLE IF NOT EXISTS memory_registry_schema_migration (
        version INTEGER PRIMARY KEY,
        schema_fingerprint TEXT NOT NULL,
        applied_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS memory_registry_entry (
        registry_entry_id TEXT PRIMARY KEY,
        schema_version INTEGER NOT NULL CHECK(schema_version=1),
        memory_class TEXT NOT NULL,
        subject_namespace TEXT NOT NULL,
        subject_key TEXT NOT NULL,
        value_schema TEXT NOT NULL,
        capability TEXT NOT NULL,
        read_allowed INTEGER NOT NULL CHECK(read_allowed IN (0,1)),
        write_allowed INTEGER NOT NULL CHECK(write_allowed IN (0,1)),
        requires_consent INTEGER NOT NULL CHECK(requires_consent IN (0,1)),
        created_at TEXT NOT NULL
    )
    """,
    """CREATE UNIQUE INDEX IF NOT EXISTS memory_registry_exact_tuple
        ON memory_registry_entry(memory_class,subject_namespace,subject_key)""",
    """CREATE TRIGGER IF NOT EXISTS memory_registry_entry_no_update
        BEFORE UPDATE ON memory_registry_entry BEGIN
        SELECT RAISE(ABORT,'registry entry is immutable'); END""",
    """CREATE TRIGGER IF NOT EXISTS memory_registry_entry_no_delete
        BEFORE DELETE ON memory_registry_entry BEGIN
        SELECT RAISE(ABORT,'registry entry removal requires migration authority'); END""",
)


@dataclass(frozen=True)
class MemoryTuplePolicyV1:
    memory_class: str
    subject_namespace: str
    subject_key: str
    value_schema: str
    capability: str
    read_allowed: bool
    write_allowed: bool
    requires_consent: bool = True

    @property
    def identity(self) -> Tuple[str, str, str]:
        return (self.memory_class, self.subject_namespace, self.subject_key)


class CanonicalTupleRegistry:
    """Exact `(class, namespace, key)` registry; aliases and fuzzy lookup do not exist."""

    def __init__(
        self,
        entries: Iterable[MemoryTuplePolicyV1] = (),
        *,
        database_path: Optional[Path] = None,
        production_path: Optional[Path] = None,
    ):
        mapped: Dict[Tuple[str, str, str], MemoryTuplePolicyV1] = {}
        for entry in entries:
            C.FrozenMemoryActionV1(
                schema_version=1,
                actor_ref_id="actor.local-owner.v1",
                operation=C.CREATE,
                memory_class=entry.memory_class,
                subject_namespace=entry.subject_namespace,
                subject_key=entry.subject_key,
                value_schema=entry.value_schema,
                payload_digest="0" * 64,
                expected_active_revision_id=None,
                restore_revision_id=None,
                purpose=C.LONG_TERM_PERSONAL_PROJECT_RECALL,
            ).validate()
            if entry.identity in mapped:
                raise ValueError("duplicate exact memory tuple")
            if entry.capability != C.CANONICAL_MEMORY_PROJECT_CODENAME_MUTATE:
                raise ValueError("unsupported memory capability")
            if not all(
                isinstance(value, bool)
                for value in (entry.read_allowed, entry.write_allowed, entry.requires_consent)
            ) or entry.requires_consent is not True:
                raise ValueError("memory tuple policy is unsupported")
            mapped[entry.identity] = entry
        if (
            database_path is not None
            and production_path is not None
            and Path(database_path).resolve() == Path(production_path).resolve()
            and mapped
        ):
            raise ValueError("Slice 15B2a production tuple registry must remain empty")
        self._entries = mapped

    def resolve(
        self, memory_class: str, subject_namespace: str, subject_key: str
    ) -> Optional[MemoryTuplePolicyV1]:
        return self._entries.get((memory_class, subject_namespace, subject_key))

    def active_keys(self) -> Tuple[Tuple[str, str, str], ...]:
        return tuple(sorted(self._entries))


@dataclass(frozen=True)
class L04V2Decision:
    proposal_ref_id: str
    outcome: str
    failure_code: Optional[str]
    action_digest: Optional[str]


class ProposalFamilyRegistry:
    def __init__(self, families: Iterable[str] = ()):
        allowed = {L.V1_PROPOSAL_FAMILY, L.V2_PROPOSAL_FAMILY}
        values = frozenset(families)
        if not values.issubset(allowed):
            raise ValueError("unknown proposal family")
        self._families = values

    def permits(self, family: str) -> bool:
        return family in self._families

    def active_families(self) -> Tuple[str, ...]:
        return tuple(sorted(self._families))


class L04V2AdmissionGate:
    """Independent V2 validation/admission foundation; never mutates memory rows."""

    def __init__(
        self,
        learning_store: L.LearningV2Store,
        *,
        enabled_provider: Callable[[], Optional[bool]],
        family_registry: ProposalFamilyRegistry,
        memory_registry: CanonicalTupleRegistry,
        actor_authority: A.LocalOwnerAuthority,
        policy_store: A.MemoryPolicyStore,
        consent_store: A.ConsentStore,
        rollback_authority: A.RollbackAuthority,
        privacy_hold_resolver: Any,
        canonical_state_resolver: Optional[
            Callable[[C.FrozenMemoryActionV1], Optional[Mapping[str, str]]]
        ] = None,
    ):
        self.learning_store = learning_store
        self.enabled_provider = enabled_provider
        self.family_registry = family_registry
        self.memory_registry = memory_registry
        self.actor_authority = actor_authority
        self.policy_store = policy_store
        self.consent_store = consent_store
        self.rollback_authority = rollback_authority
        self.privacy_hold_resolver = privacy_hold_resolver
        self.canonical_state_resolver = canonical_state_resolver

    @staticmethod
    def _action_from_row(row: sqlite3.Row) -> C.FrozenMemoryActionV1:
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

    def evaluate(self, proposal_ref_id: str) -> L04V2Decision:
        enabled = self.enabled_provider()
        if enabled is not True:
            return L04V2Decision(
                proposal_ref_id, REJECTED, "CANONICAL_LTM_DISABLED", None
            )
        try:
            ref, proposal = self.learning_store.resolve_proposal_ref(proposal_ref_id)
        except Exception:
            return L04V2Decision(proposal_ref_id, REJECTED, "PROPOSAL_REF_INVALID", None)
        if not self.family_registry.permits(ref.proposal_family):
            return L04V2Decision(proposal_ref_id, REJECTED, "UNKNOWN_PROPOSAL_FAMILY", None)
        if ref.proposal_family != L.V2_PROPOSAL_FAMILY:
            return L04V2Decision(proposal_ref_id, REJECTED, "V1_DISPATCH_UNCHANGED", None)
        try:
            action = self._action_from_row(proposal)
            action.validate()
        except Exception:
            return L04V2Decision(proposal_ref_id, REJECTED, "INVALID_PROPOSAL", None)
        if str(proposal["action_digest"]) != action.action_digest:
            return L04V2Decision(
                proposal_ref_id, REJECTED, "PROPOSAL_ACTION_DIGEST_MISMATCH", action.action_digest
            )
        proposal_semantic = {
            "proposalSchemaVersion": 1,
            "candidateId": str(proposal["candidate_id"]),
            "intentRefId": str(proposal["intent_ref_id"]),
            "actorRefId": action.actor_ref_id,
            "actorEvidenceRefId": str(proposal["actor_evidence_ref_id"]),
            "policyDecisionRefId": str(proposal["policy_decision_ref_id"]),
            "consentRefId": str(proposal["consent_ref_id"]),
            "rollbackAuthorizationRefId": proposal["rollback_authorization_ref_id"],
            "action": action.semantic_dict(),
            "actionDigest": action.action_digest,
        }
        if str(proposal["proposal_fingerprint"]) != C.sha256_digest(proposal_semantic):
            return L04V2Decision(
                proposal_ref_id, REJECTED, "PROPOSAL_FINGERPRINT_MISMATCH", action.action_digest
            )
        policy = self.memory_registry.resolve(*action.identity)
        if policy is None or not policy.write_allowed:
            return L04V2Decision(
                proposal_ref_id, REJECTED, "UNKNOWN_MEMORY_TUPLE", action.action_digest
            )
        if policy.value_schema != (action.value_schema or policy.value_schema):
            return L04V2Decision(
                proposal_ref_id, REJECTED, "UNKNOWN_VALUE_SCHEMA", action.action_digest
            )
        if action.operation in {C.CREATE, C.SUPERSEDE}:
            try:
                canonical_value, value_digest = L.normalize_project_codename(
                    json.loads(str(proposal["proposed_value_json"]))
                )
            except Exception:
                return L04V2Decision(
                    proposal_ref_id, REJECTED, "INVALID_PROPOSAL_VALUE", action.action_digest
                )
            if (
                canonical_value != str(proposal["proposed_value_json"])
                or value_digest != action.payload_digest
            ):
                return L04V2Decision(
                    proposal_ref_id, REJECTED, "PROPOSAL_VALUE_DIGEST_MISMATCH", action.action_digest
                )
        if self.privacy_hold_resolver.is_held(*action.identity):
            return L04V2Decision(
                proposal_ref_id, REJECTED, "PRIVACY_HOLD_ACTIVE", action.action_digest
            )
        try:
            self.actor_authority.validate_existing(
                str(proposal["actor_evidence_ref_id"]),
                action=action,
                require_consumed=True,
            )
        except Exception:
            return L04V2Decision(
                proposal_ref_id, REJECTED, "ACTOR_UNRESOLVED", action.action_digest
            )
        policy_result = self.policy_store.resolve(
            str(proposal["policy_decision_ref_id"]),
            action=action,
            capability=policy.capability,
        )
        if policy_result.status != A.CONFIRMED:
            return L04V2Decision(
                proposal_ref_id, REJECTED, "POLICY_DECISION_INVALID", action.action_digest
            )
        consent_result = self.consent_store.resolve(
            str(proposal["consent_ref_id"]),
            action=action,
            intent_ref_id=str(proposal["intent_ref_id"]),
            actor_evidence_ref_id=str(proposal["actor_evidence_ref_id"]),
        )
        if consent_result.status != A.CONFIRMED:
            return L04V2Decision(
                proposal_ref_id,
                REJECTED,
                "CONSENT_REVOKED" if consent_result.status == A.REVOKED else "CONSENT_INVALID",
                action.action_digest,
            )
        if action.operation == C.RESTORE:
            rollback_ref = proposal["rollback_authorization_ref_id"]
            if not rollback_ref:
                return L04V2Decision(
                    proposal_ref_id, REJECTED, "ROLLBACK_NOT_AUTHORIZED", action.action_digest
                )
            if self.canonical_state_resolver is None:
                return L04V2Decision(
                    proposal_ref_id, REJECTED, "CANONICAL_STATE_UNAVAILABLE", action.action_digest
                )
            try:
                state = self.canonical_state_resolver(action)
            except Exception:
                state = None
            if (
                state is None
                or state.get("current_revision_id") != action.expected_active_revision_id
                or state.get("restore_revision_id") != action.restore_revision_id
                or state.get("target_value_digest") != action.payload_digest
                or not state.get("memory_item_id")
            ):
                return L04V2Decision(
                    proposal_ref_id, REJECTED, "RESTORE_STATE_MISMATCH", action.action_digest
                )
            rollback = self.rollback_authority.resolve_and_consume(
                str(rollback_ref),
                action=action,
                memory_item_id=str(state["memory_item_id"]),
                consumer_ref="l04.v2.admission",
            )
            if rollback.status != A.CONFIRMED:
                return L04V2Decision(
                    proposal_ref_id, REJECTED, "ROLLBACK_NOT_AUTHORIZED", action.action_digest
                )
        conn = self.learning_store.connect()
        try:
            binding = conn.execute(
                "SELECT c.action_digest,c.actor_ref_id,c.actor_evidence_ref_id,"
                "c.policy_decision_ref_id,c.consent_ref_id,a.outcome,s.source_digest,"
                "d.operation,d.memory_class,d.subject_namespace,d.subject_key,"
                "d.value_schema,d.payload_digest,d.expected_active_revision_id,"
                "d.restore_revision_id "
                "FROM learning_candidate_v2 c "
                "JOIN learning_project_codename_candidate_v1 d ON d.candidate_id=c.candidate_id "
                "JOIN learning_assessment_v2 a ON a.candidate_id=c.candidate_id "
                "JOIN learning_candidate_source_v2 s ON s.candidate_id=c.candidate_id "
                "WHERE c.candidate_id=?",
                (str(proposal["candidate_id"]),),
            ).fetchone()
            exact = (
                binding is not None
                and str(binding["action_digest"]) == action.action_digest
                and str(binding["actor_ref_id"]) == action.actor_ref_id
                and str(binding["actor_evidence_ref_id"]) == str(proposal["actor_evidence_ref_id"])
                and str(binding["policy_decision_ref_id"]) == str(proposal["policy_decision_ref_id"])
                and str(binding["consent_ref_id"]) == str(proposal["consent_ref_id"])
                and str(binding["source_digest"]) == action.action_digest
                and str(binding["outcome"]) == L.REAL_ELIGIBLE
                and str(binding["operation"]) == action.operation
                and str(binding["memory_class"]) == action.memory_class
                and str(binding["subject_namespace"]) == action.subject_namespace
                and str(binding["subject_key"]) == action.subject_key
                and binding["value_schema"] == action.value_schema
                and str(binding["payload_digest"]) == action.payload_digest
                and binding["expected_active_revision_id"] == action.expected_active_revision_id
                and binding["restore_revision_id"] == action.restore_revision_id
            )
        finally:
            conn.close()
        if not exact:
            return L04V2Decision(
                proposal_ref_id, REJECTED, "CANDIDATE_BINDING_INVALID", action.action_digest
            )
        return L04V2Decision(proposal_ref_id, ACCEPTED, None, action.action_digest)


class CanonicalMemoryReadFacade:
    """Future exact read boundary; it has no legacy fallback of any kind."""

    def __init__(
        self,
        raw_l04_store: Any,
        *,
        registry: CanonicalTupleRegistry,
        consent_store: Any,
        privacy_hold_resolver: Any,
        actor_resolver: Callable[[C.ActorRefV1], bool],
    ):
        self._raw_l04_store = raw_l04_store
        self._registry = registry
        self._consent_store = consent_store
        self._privacy_hold_resolver = privacy_hold_resolver
        self._actor_resolver = actor_resolver

    def read_exact(
        self,
        *,
        actor: Optional[C.ActorRefV1],
        memory_class: str,
        subject_namespace: str,
        subject_key: str,
    ) -> Optional[Dict[str, Any]]:
        if actor is None:
            raise PermissionError("ACTOR_UNRESOLVED")
        actor.validate()
        if self._actor_resolver(actor) is not True:
            raise PermissionError("ACTOR_UNRESOLVED")
        policy = self._registry.resolve(memory_class, subject_namespace, subject_key)
        if policy is None or not policy.read_allowed:
            raise PermissionError("UNKNOWN_MEMORY_TUPLE")
        if self._privacy_hold_resolver.is_held(
            memory_class, subject_namespace, subject_key
        ):
            return None
        row = self._raw_l04_store.get_active(
            memory_class, subject_namespace, subject_key
        )
        if row is None:
            return None
        consent_ref = row.get("consent_ref_id")
        if not consent_ref or self._consent_store.resolve_revision(
            consent_ref,
            memory_class=memory_class,
            subject_namespace=subject_namespace,
            subject_key=subject_key,
            payload_digest=str(row.get("value_digest") or ""),
        ).status != A.CONFIRMED:
            return None
        return row


_L04_DELETE_TRIGGERS = (
    "memory_item_no_delete",
    "memory_revision_no_delete",
    "memory_revision_source_no_delete",
    "memory_admission_no_delete",
    "memory_apply_audit_no_delete",
    "memory_active_revision_no_delete",
)


class L04PrivacyErasureOwner:
    """Tightly-scoped privileged L04 erasure path, callable only with exact auth."""

    OWNER = "L04"

    def __init__(self, path: Path, privacy_authority: Any):
        self.path = Path(path)
        self.privacy_authority = privacy_authority

    @staticmethod
    def _lineage_schema(conn: sqlite3.Connection) -> Tuple[str, str]:
        revision_columns = {
            str(row[1]) for row in conn.execute("PRAGMA table_info(memory_revision)")
        }
        admission_columns = {
            str(row[1]) for row in conn.execute("PRAGMA table_info(memory_admission)")
        }
        if (
            "created_from_proposal_ref_id" in revision_columns
            and "proposal_ref_id" in admission_columns
        ):
            return "created_from_proposal_ref_id", "proposal_ref_id"
        if "created_from_proposal_id" in revision_columns and "proposal_id" in admission_columns:
            return "created_from_proposal_id", "proposal_id"
        raise RuntimeError("L04 proposal lineage schema is unsupported")

    @staticmethod
    def _family_lineage(
        conn: sqlite3.Connection, identifiers: Tuple[str, ...], revision_column: str
    ) -> Tuple[Tuple[str, ...], Tuple[str, ...], Tuple[str, ...]]:
        if revision_column == "created_from_proposal_id":
            return identifiers, (), ()
        if not identifiers:
            return (), (), ()
        marks = ",".join("?" for _ in identifiers)
        rows = conn.execute(
            "SELECT proposal_ref_id,proposal_family,family_proposal_id "
            f"FROM learning_proposal_ref WHERE proposal_ref_id IN ({marks})",
            identifiers,
        ).fetchall()
        if len(rows) != len(set(identifiers)):
            raise RuntimeError("L04 proposal lineage is incomplete")
        v1 = tuple(
            str(row[2]) for row in rows if str(row[1]) == L.V1_PROPOSAL_FAMILY
        )
        v2 = tuple(
            str(row[2]) for row in rows if str(row[1]) == L.V2_PROPOSAL_FAMILY
        )
        return v1, v2, tuple(str(row[0]) for row in rows)

    def erase_authorized(self, authorization_ref_id: str, execution_nonce: str) -> Dict[str, Any]:
        authorization = self.privacy_authority.resolve_erasure_authorization(
            authorization_ref_id,
            owner=self.OWNER,
            execution_nonce=execution_nonce,
        )
        if authorization is None:
            raise PermissionError("PRIVACY_ERASURE_NOT_AUTHORIZED")
        conn = sqlite3.connect(str(self.path), timeout=5.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA secure_delete=ON")
        try:
            conn.execute("BEGIN EXCLUSIVE")
            item = conn.execute(
                "SELECT memory_item_id FROM memory_item WHERE memory_class=? "
                "AND subject_namespace=? AND subject_key=?",
                authorization.identity,
            ).fetchone()
            if item is None:
                conn.rollback()
                result = {
                    "owner": self.OWNER,
                    "status": "COMPLETE",
                    "deleted": 0,
                    "proposalIds": (),
                }
                self.privacy_authority.record_owner_result(
                    authorization_ref_id, execution_nonce, result
                )
                return result
            item_id = str(item[0])
            if authorization.memory_item_id and authorization.memory_item_id != item_id:
                raise PermissionError("PRIVACY_ERASURE_IDENTITY_MISMATCH")
            trigger_sql = {
                str(row[0]): str(row[1])
                for row in conn.execute(
                    "SELECT name,sql FROM sqlite_master WHERE type='trigger' AND name IN (%s)"
                    % ",".join("?" for _ in _L04_DELETE_TRIGGERS),
                    _L04_DELETE_TRIGGERS,
                )
            }
            if set(trigger_sql) != set(_L04_DELETE_TRIGGERS):
                raise RuntimeError("L04 immutability trigger set is incomplete")
            for name in _L04_DELETE_TRIGGERS:
                conn.execute(f'DROP TRIGGER "{name}"')
            revision_column, admission_column = self._lineage_schema(conn)
            revision_rows = conn.execute(
                f"SELECT revision_id,{revision_column} FROM memory_revision "
                "WHERE memory_item_id=?",
                (item_id,),
            ).fetchall()
            revision_ids = tuple(str(row[0]) for row in revision_rows)
            identifiers = tuple(str(row[1]) for row in revision_rows)
            proposal_ids, v2_proposal_ids, proposal_ref_ids = self._family_lineage(
                conn, identifiers, revision_column
            )
            if revision_ids:
                marks = ",".join("?" for _ in revision_ids)
                conn.execute(
                    f"DELETE FROM memory_revision_source WHERE revision_id IN ({marks})",
                    revision_ids,
                )
            conn.execute("DELETE FROM memory_apply_audit WHERE memory_item_id=?", (item_id,))
            if identifiers:
                marks = ",".join("?" for _ in identifiers)
                conn.execute(
                    f"DELETE FROM memory_admission WHERE {admission_column} IN ({marks})",
                    identifiers,
                )
            conn.execute("DELETE FROM memory_active_revision WHERE memory_item_id=?", (item_id,))
            conn.execute("DELETE FROM memory_revision WHERE memory_item_id=?", (item_id,))
            deleted = conn.execute(
                "DELETE FROM memory_item WHERE memory_item_id=?", (item_id,)
            ).rowcount
            for name in _L04_DELETE_TRIGGERS:
                conn.execute(trigger_sql[name])
            if conn.execute("PRAGMA foreign_key_check").fetchall():
                raise RuntimeError("L04 erasure foreign-key check failed")
            if str(conn.execute("PRAGMA integrity_check").fetchone()[0]) != "ok":
                raise RuntimeError("L04 erasure integrity check failed")
            conn.commit()
            conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            result = {
                "owner": self.OWNER,
                "status": "COMPLETE",
                "deleted": int(deleted),
                "proposalIds": proposal_ids,
                "v2ProposalIds": v2_proposal_ids,
                "proposalRefIds": proposal_ref_ids,
            }
            self.privacy_authority.record_owner_result(
                authorization_ref_id, execution_nonce, result
            )
            return result
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def list_identities(self) -> Tuple[Tuple[str, str, str], ...]:
        conn = sqlite3.connect(f"file:{self.path.resolve()}?mode=ro", uri=True)
        try:
            return tuple(
                (str(row[0]), str(row[1]), str(row[2]))
                for row in conn.execute(
                    "SELECT memory_class,subject_namespace,subject_key FROM memory_item "
                    "ORDER BY memory_class,subject_namespace,subject_key"
                )
            )
        finally:
            conn.close()

    def erase_restore_suppressed(self, identity: Tuple[str, str, str], privacy_store: Any) -> None:
        """Maintenance-only restore gate; Privacy proves the opaque selector first."""
        if not privacy_store.suppression_matches(identity):
            raise PermissionError("RESTORE_SUPPRESSION_NOT_AUTHORIZED")
        conn = sqlite3.connect(str(self.path), timeout=5.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA secure_delete=ON")
        try:
            conn.execute("BEGIN EXCLUSIVE")
            item = conn.execute(
                "SELECT memory_item_id FROM memory_item WHERE memory_class=? "
                "AND subject_namespace=? AND subject_key=?",
                identity,
            ).fetchone()
            if item is None:
                conn.rollback()
                return
            item_id = str(item[0])
            trigger_sql = {
                str(row[0]): str(row[1])
                for row in conn.execute(
                    "SELECT name,sql FROM sqlite_master WHERE type='trigger' AND name IN (%s)"
                    % ",".join("?" for _ in _L04_DELETE_TRIGGERS),
                    _L04_DELETE_TRIGGERS,
                )
            }
            if set(trigger_sql) != set(_L04_DELETE_TRIGGERS):
                raise RuntimeError("L04 immutability trigger set is incomplete")
            for name in _L04_DELETE_TRIGGERS:
                conn.execute(f'DROP TRIGGER "{name}"')
            revision_column, admission_column = self._lineage_schema(conn)
            revision_rows = tuple(
                (str(row[0]), str(row[1]))
                for row in conn.execute(
                    f"SELECT revision_id,{revision_column} FROM memory_revision "
                    "WHERE memory_item_id=?",
                    (item_id,),
                )
            )
            revisions = tuple(row[0] for row in revision_rows)
            identifiers = tuple(row[1] for row in revision_rows)
            if revisions:
                marks = ",".join("?" for _ in revisions)
                conn.execute(
                    f"DELETE FROM memory_revision_source WHERE revision_id IN ({marks})",
                    revisions,
                )
            conn.execute("DELETE FROM memory_apply_audit WHERE memory_item_id=?", (item_id,))
            if identifiers:
                marks = ",".join("?" for _ in identifiers)
                conn.execute(
                    f"DELETE FROM memory_admission WHERE {admission_column} IN ({marks})",
                    identifiers,
                )
            conn.execute("DELETE FROM memory_active_revision WHERE memory_item_id=?", (item_id,))
            conn.execute("DELETE FROM memory_revision WHERE memory_item_id=?", (item_id,))
            conn.execute("DELETE FROM memory_item WHERE memory_item_id=?", (item_id,))
            for name in _L04_DELETE_TRIGGERS:
                conn.execute(trigger_sql[name])
            if conn.execute("PRAGMA foreign_key_check").fetchall():
                raise RuntimeError("restore suppression foreign-key check failed")
            if str(conn.execute("PRAGMA integrity_check").fetchone()[0]) != "ok":
                raise RuntimeError("restore suppression integrity check failed")
            conn.commit()
            conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()


class L18V1PrivacyErasureOwner:
    """L18 V1 deletes only proposal/candidate/provenance IDs returned by L04."""

    OWNER = "L18_V1"
    _TRIGGERS = (
        "learning_proposal_no_delete",
        "learning_candidate_no_delete",
        "learning_candidate_source_no_delete",
        "learning_assessment_no_delete",
    )

    def __init__(self, path: Path, privacy_authority: Any):
        self.path = Path(path)
        self.privacy_authority = privacy_authority

    def erase_authorized(
        self,
        authorization_ref_id: str,
        execution_nonce: str,
        *,
        proposal_ids: Tuple[str, ...],
    ) -> Dict[str, Any]:
        authorization = self.privacy_authority.resolve_erasure_authorization(
            authorization_ref_id, owner=self.OWNER, execution_nonce=execution_nonce
        )
        if authorization is None:
            raise PermissionError("PRIVACY_ERASURE_NOT_AUTHORIZED")
        conn = sqlite3.connect(str(self.path), timeout=5.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA secure_delete=ON")
        try:
            conn.execute("BEGIN EXCLUSIVE")
            trigger_sql = {
                str(row[0]): str(row[1])
                for row in conn.execute(
                    "SELECT name,sql FROM sqlite_master WHERE type='trigger' AND name IN (%s)"
                    % ",".join("?" for _ in self._TRIGGERS),
                    self._TRIGGERS,
                )
            }
            if set(trigger_sql) != set(self._TRIGGERS):
                raise RuntimeError("L18 V1 immutability trigger set is incomplete")
            for name in self._TRIGGERS:
                conn.execute(f'DROP TRIGGER "{name}"')
            candidate_ids = []
            for proposal_id in proposal_ids:
                row = conn.execute(
                    "SELECT candidate_id FROM learning_proposal WHERE proposal_id=?",
                    (proposal_id,),
                ).fetchone()
                if row is not None:
                    candidate_ids.append(str(row[0]))
                conn.execute("DELETE FROM learning_proposal WHERE proposal_id=?", (proposal_id,))
            for candidate_id in candidate_ids:
                conn.execute("DELETE FROM learning_assessment WHERE candidate_id=?", (candidate_id,))
                conn.execute("DELETE FROM learning_candidate_source WHERE candidate_id=?", (candidate_id,))
                conn.execute("DELETE FROM learning_candidate WHERE candidate_id=?", (candidate_id,))
            for name in self._TRIGGERS:
                conn.execute(trigger_sql[name])
            if conn.execute("PRAGMA foreign_key_check").fetchall():
                raise RuntimeError("L18 V1 erasure foreign-key check failed")
            conn.commit()
            conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            result = {"owner": self.OWNER, "status": "COMPLETE", "deleted": len(candidate_ids)}
            self.privacy_authority.record_owner_result(
                authorization_ref_id, execution_nonce, result
            )
            return result
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()


class L18V2PrivacyErasureOwner:
    """Exact-identity erasure owned by L18 V2, independent of L04 storage."""

    OWNER = "L18_V2"
    _TRIGGERS = (
        "learning_memory_intent_v2_no_delete",
        "learning_candidate_v2_no_delete",
        "learning_project_codename_candidate_v1_no_delete",
        "learning_candidate_source_v2_no_delete",
        "learning_assessment_v2_no_delete",
        "learning_proposal_ref_no_delete",
        "learning_proposal_v2_no_delete",
    )

    def __init__(self, path: Path, privacy_authority: Any):
        self.path = Path(path)
        self.privacy_authority = privacy_authority

    def erase_authorized(self, authorization_ref_id: str, execution_nonce: str) -> Dict[str, Any]:
        authorization = self.privacy_authority.resolve_erasure_authorization(
            authorization_ref_id, owner=self.OWNER, execution_nonce=execution_nonce
        )
        if authorization is None:
            raise PermissionError("PRIVACY_ERASURE_NOT_AUTHORIZED")
        conn = sqlite3.connect(str(self.path), timeout=5.0)
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA secure_delete=ON")
        try:
            conn.execute("BEGIN EXCLUSIVE")
            trigger_sql = {
                str(row[0]): str(row[1])
                for row in conn.execute(
                    "SELECT name,sql FROM sqlite_master WHERE type='trigger' AND name IN (%s)"
                    % ",".join("?" for _ in self._TRIGGERS),
                    self._TRIGGERS,
                )
            }
            if set(trigger_sql) != set(self._TRIGGERS):
                raise RuntimeError("L18 V2 immutability trigger set is incomplete")
            candidate_ids = tuple(
                str(row[0])
                for row in conn.execute(
                    "SELECT candidate_id FROM learning_project_codename_candidate_v1 "
                    "WHERE memory_class=? AND subject_namespace=? AND subject_key=?",
                    authorization.identity,
                )
            )
            intent_ids: Tuple[str, ...] = ()
            proposal_ids: Tuple[str, ...] = ()
            if candidate_ids:
                marks = ",".join("?" for _ in candidate_ids)
                intent_ids = tuple(
                    str(row[0])
                    for row in conn.execute(
                        f"SELECT intent_ref_id FROM learning_candidate_v2 "
                        f"WHERE candidate_id IN ({marks})",
                        candidate_ids,
                    )
                )
                proposal_ids = tuple(
                    str(row[0])
                    for row in conn.execute(
                        f"SELECT proposal_id FROM learning_proposal_v2 "
                        f"WHERE candidate_id IN ({marks})",
                        candidate_ids,
                    )
                )
            for name in self._TRIGGERS:
                conn.execute(f'DROP TRIGGER "{name}"')
            if proposal_ids:
                marks = ",".join("?" for _ in proposal_ids)
                conn.execute(
                    f"DELETE FROM learning_proposal_ref WHERE proposal_family=? "
                    f"AND family_proposal_id IN ({marks})",
                    (L.V2_PROPOSAL_FAMILY, *proposal_ids),
                )
                conn.execute(
                    f"DELETE FROM learning_proposal_v2 WHERE proposal_id IN ({marks})",
                    proposal_ids,
                )
            if candidate_ids:
                marks = ",".join("?" for _ in candidate_ids)
                conn.execute(
                    f"DELETE FROM learning_assessment_v2 WHERE candidate_id IN ({marks})",
                    candidate_ids,
                )
                conn.execute(
                    f"DELETE FROM learning_candidate_source_v2 WHERE candidate_id IN ({marks})",
                    candidate_ids,
                )
                conn.execute(
                    f"DELETE FROM learning_project_codename_candidate_v1 "
                    f"WHERE candidate_id IN ({marks})",
                    candidate_ids,
                )
                deleted = conn.execute(
                    f"DELETE FROM learning_candidate_v2 WHERE candidate_id IN ({marks})",
                    candidate_ids,
                ).rowcount
            else:
                deleted = 0
            if intent_ids:
                marks = ",".join("?" for _ in intent_ids)
                conn.execute(
                    f"DELETE FROM learning_memory_intent_v2 WHERE intent_ref_id IN ({marks})",
                    intent_ids,
                )
            for name in self._TRIGGERS:
                conn.execute(trigger_sql[name])
            if conn.execute("PRAGMA foreign_key_check").fetchall():
                raise RuntimeError("L18 V2 erasure foreign-key check failed")
            conn.commit()
            conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
        result = {"owner": self.OWNER, "status": "COMPLETE", "deleted": int(deleted)}
        self.privacy_authority.record_owner_result(
            authorization_ref_id, execution_nonce, result
        )
        return result
