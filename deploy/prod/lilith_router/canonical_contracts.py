"""Closed Slice 15B2a authority and canonical-memory action contracts.

These objects carry identifiers and digests, never browser session material,
raw transcripts, prompts, confidence, emotion state, or arbitrary metadata.
Generated identifiers and timestamps are deliberately excluded from the
semantic action digest.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple


SCHEMA_VERSION = 1

LOCAL_OWNER_AUTHORITY_V1 = "LOCAL_OWNER_AUTHORITY_V1"
LOCAL_CONSENT_AUTHORITY_V1 = "LOCAL_CONSENT_AUTHORITY_V1"
USER_ROLLBACK_AUTHORITY_V1 = "USER_ROLLBACK_AUTHORITY_V1"
PRIVACY_GOVERNANCE_AUTHORITY_V1 = "PRIVACY_GOVERNANCE_AUTHORITY_V1"
MEMORY_INTERACTION_AUTHORITY = "MEMORY_INTERACTION_AUTHORITY"

OWNER_CONTROLLED_HOME_CONTEXT = "OWNER_CONTROLLED_HOME_CONTEXT"
LOCAL_OWNER_ACTOR_ID = "local-owner"
USER_CONFIRMATION = "USER_CONFIRMATION"

CREATE = "CREATE"
SUPERSEDE = "SUPERSEDE"
RESTORE = "RESTORE"
FORGET = "FORGET"
MEMORY_MUTATIONS = frozenset({CREATE, SUPERSEDE, RESTORE})
ACTION_OPERATIONS = frozenset({CREATE, SUPERSEDE, RESTORE, FORGET})

LONG_TERM_PERSONAL_PROJECT_RECALL = "LONG_TERM_PERSONAL_PROJECT_RECALL"
VALID_PURPOSES = frozenset({LONG_TERM_PERSONAL_PROJECT_RECALL})

CANONICAL_MEMORY_PROJECT_CODENAME_MUTATE = (
    "canonical_memory.project_codename.mutate"
)

ACTOR_EVIDENCE_EXPIRED = "ACTOR_EVIDENCE_EXPIRED"
ACTOR_EVIDENCE_REPLAYED = "ACTOR_EVIDENCE_REPLAYED"
ACTOR_EVIDENCE_INVALID = "ACTOR_EVIDENCE_INVALID"
ACTOR_UNRESOLVED = "ACTOR_UNRESOLVED"

_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_CLASS_RE = re.compile(r"^[A-Z][A-Z0-9_]{0,63}$")
_NAMESPACE_RE = re.compile(r"^[a-z][a-z0-9_.-]{0,63}$")
_SCHEMA_RE = re.compile(r"^[A-Za-z][A-Za-z0-9._:-]{0,127}$")
_HEX64_RE = re.compile(r"^[0-9a-f]{64}$")


class ContractError(ValueError):
    """A closed Slice 15B2a contract was malformed."""


def canonical_json(value: Dict[str, Any]) -> str:
    """Return the one canonical JSON representation used by all authorities."""
    try:
        return json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        )
    except (TypeError, ValueError) as exc:
        raise ContractError("value is not canonical JSON") from exc


def sha256_digest(value: Dict[str, Any]) -> str:
    return hashlib.sha256(canonical_json(value).encode("ascii")).hexdigest()


def require_id(value: str, field: str) -> None:
    if not isinstance(value, str) or not _ID_RE.fullmatch(value):
        raise ContractError(f"{field} is invalid")


def require_optional_id(value: Optional[str], field: str) -> None:
    if value is not None:
        require_id(value, field)


def require_digest(value: str, field: str) -> None:
    if not isinstance(value, str) or not _HEX64_RE.fullmatch(value):
        raise ContractError(f"{field} is invalid")


@dataclass(frozen=True)
class ActorRefV1:
    schema_version: int
    actor_ref_id: str
    actor_id: str
    authority: str
    assurance: str

    def validate(self) -> None:
        if self.schema_version != SCHEMA_VERSION:
            raise ContractError("actor schema version is unsupported")
        require_id(self.actor_ref_id, "actorRefId")
        if self.actor_id != LOCAL_OWNER_ACTOR_ID:
            raise ContractError("actorId is unsupported")
        if self.authority != LOCAL_OWNER_AUTHORITY_V1:
            raise ContractError("actor authority is unsupported")
        if self.assurance != OWNER_CONTROLLED_HOME_CONTEXT:
            raise ContractError("actor assurance is unsupported")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schemaVersion": self.schema_version,
            "actorRefId": self.actor_ref_id,
            "actorId": self.actor_id,
            "authority": self.authority,
            "assurance": self.assurance,
        }


@dataclass(frozen=True)
class FrozenMemoryActionV1:
    """The semantic identity shared by every Slice 15B2a authority."""

    schema_version: int
    actor_ref_id: str
    operation: str
    memory_class: str
    subject_namespace: str
    subject_key: str
    value_schema: Optional[str]
    payload_digest: str
    expected_active_revision_id: Optional[str]
    restore_revision_id: Optional[str]
    purpose: str

    def validate(self) -> None:
        if self.schema_version != SCHEMA_VERSION:
            raise ContractError("action schema version is unsupported")
        require_id(self.actor_ref_id, "actorRefId")
        if self.operation not in ACTION_OPERATIONS:
            raise ContractError("operation is unsupported")
        if not isinstance(self.memory_class, str) or not _CLASS_RE.fullmatch(
            self.memory_class
        ):
            raise ContractError("memoryClass is invalid")
        if not isinstance(self.subject_namespace, str) or not _NAMESPACE_RE.fullmatch(
            self.subject_namespace
        ):
            raise ContractError("subjectNamespace is invalid")
        require_id(self.subject_key, "subjectKey")
        if self.value_schema is not None and not _SCHEMA_RE.fullmatch(self.value_schema):
            raise ContractError("valueSchema is invalid")
        require_digest(self.payload_digest, "payloadDigest")
        require_optional_id(self.expected_active_revision_id, "expectedActiveRevisionId")
        require_optional_id(self.restore_revision_id, "restoreRevisionId")
        if self.purpose not in VALID_PURPOSES:
            raise ContractError("purpose is unsupported")
        if self.operation == CREATE and (
            self.expected_active_revision_id is not None
            or self.restore_revision_id is not None
            or self.value_schema is None
        ):
            raise ContractError("CREATE action shape is invalid")
        if self.operation == SUPERSEDE and (
            self.expected_active_revision_id is None
            or self.restore_revision_id is not None
            or self.value_schema is None
        ):
            raise ContractError("SUPERSEDE action shape is invalid")
        if self.operation == RESTORE and (
            self.expected_active_revision_id is None
            or self.restore_revision_id is None
            or self.value_schema is not None
        ):
            raise ContractError("RESTORE action shape is invalid")
        if self.operation == FORGET and (
            self.expected_active_revision_id is not None
            or self.restore_revision_id is not None
            or self.value_schema is not None
        ):
            raise ContractError("FORGET action shape is invalid")

    def semantic_dict(self) -> Dict[str, Any]:
        self.validate()
        return {
            "schemaVersion": self.schema_version,
            "actorRefId": self.actor_ref_id,
            "operation": self.operation,
            "memoryClass": self.memory_class,
            "subjectNamespace": self.subject_namespace,
            "subjectKey": self.subject_key,
            "valueSchema": self.value_schema,
            "payloadDigest": self.payload_digest,
            "expectedActiveRevisionId": self.expected_active_revision_id,
            "restoreRevisionId": self.restore_revision_id,
            "purpose": self.purpose,
        }

    @property
    def action_digest(self) -> str:
        return sha256_digest(self.semantic_dict())

    @property
    def identity(self) -> Tuple[str, str, str]:
        return (self.memory_class, self.subject_namespace, self.subject_key)


@dataclass(frozen=True)
class ActorEvidenceRefV1:
    schema_version: int
    actor_evidence_ref_id: str
    actor_ref_id: str
    authority: str
    request_digest: str
    action_digest: str
    nonce: str
    issued_at: str
    expires_at: str
    issuer_ref: str
    evidence_fingerprint: str

    def validate_shape(self) -> None:
        if self.schema_version != SCHEMA_VERSION:
            raise ContractError("actor evidence schema version is unsupported")
        require_id(self.actor_evidence_ref_id, "actorEvidenceRefId")
        require_id(self.actor_ref_id, "actorRefId")
        if self.authority != LOCAL_OWNER_AUTHORITY_V1:
            raise ContractError("actor evidence authority is unsupported")
        require_digest(self.request_digest, "requestDigest")
        require_digest(self.action_digest, "actionDigest")
        require_id(self.nonce, "nonce")
        require_id(self.issuer_ref, "issuerRef")
        require_digest(self.evidence_fingerprint, "evidenceFingerprint")
        if not self.issued_at or not self.expires_at:
            raise ContractError("actor evidence timestamps are required")

    def fingerprint_dict(self) -> Dict[str, Any]:
        return {
            "schemaVersion": self.schema_version,
            "actorRefId": self.actor_ref_id,
            "authority": self.authority,
            "requestDigest": self.request_digest,
            "actionDigest": self.action_digest,
            "nonce": self.nonce,
            "issuedAt": self.issued_at,
            "expiresAt": self.expires_at,
            "issuerRef": self.issuer_ref,
        }


@dataclass(frozen=True)
class ConsentRefV1:
    schema_version: int
    consent_id: str
    authority: str
    actor_ref_id: str
    actor_evidence_ref_id: str
    memory_class: str
    subject_namespace: str
    subject_key: str
    operation: str
    payload_digest: str
    expected_active_revision_id: Optional[str]
    restore_revision_id: Optional[str]
    purpose: str
    granted_at: str
    issuer_type: str
    issuer_ref: str
    intent_ref_id: str
    privacy_notice_version: str
    action_digest: str
    consent_fingerprint: str

    def validate_shape(self) -> None:
        if self.schema_version != SCHEMA_VERSION:
            raise ContractError("consent schema version is unsupported")
        for field, value in (
            ("consentId", self.consent_id),
            ("actorRefId", self.actor_ref_id),
            ("actorEvidenceRefId", self.actor_evidence_ref_id),
            ("subjectKey", self.subject_key),
            ("issuerRef", self.issuer_ref),
            ("intentRefId", self.intent_ref_id),
            ("privacyNoticeVersion", self.privacy_notice_version),
        ):
            require_id(value, field)
        if self.authority != LOCAL_CONSENT_AUTHORITY_V1:
            raise ContractError("consent authority is unsupported")
        if self.issuer_type != USER_CONFIRMATION:
            raise ContractError("consent issuer type is unsupported")
        if self.operation not in MEMORY_MUTATIONS:
            raise ContractError("consent operation is unsupported")
        if not _CLASS_RE.fullmatch(self.memory_class):
            raise ContractError("consent memoryClass is invalid")
        if not _NAMESPACE_RE.fullmatch(self.subject_namespace):
            raise ContractError("consent namespace is invalid")
        require_digest(self.payload_digest, "payloadDigest")
        require_digest(self.action_digest, "actionDigest")
        require_digest(self.consent_fingerprint, "consentFingerprint")
        require_optional_id(self.expected_active_revision_id, "expectedActiveRevisionId")
        require_optional_id(self.restore_revision_id, "restoreRevisionId")
        if self.purpose not in VALID_PURPOSES:
            raise ContractError("consent purpose is unsupported")


@dataclass(frozen=True)
class PolicyDecisionRefV1:
    schema_version: int
    decision_ref_id: str
    actor_ref_id: str
    actor_evidence_ref_id: str
    capability: str
    operation: str
    memory_class: str
    subject_namespace: str
    subject_key: str
    payload_digest: str
    expected_active_revision_id: Optional[str]
    restore_revision_id: Optional[str]
    purpose: str
    policy_version: str
    decision: str
    action_digest: str
    created_at: str
    decision_fingerprint: str

    def validate_shape(self) -> None:
        if self.schema_version != SCHEMA_VERSION:
            raise ContractError("policy decision schema version is unsupported")
        for field, value in (
            ("decisionRefId", self.decision_ref_id),
            ("actorRefId", self.actor_ref_id),
            ("actorEvidenceRefId", self.actor_evidence_ref_id),
            ("subjectKey", self.subject_key),
            ("policyVersion", self.policy_version),
        ):
            require_id(value, field)
        if self.capability != CANONICAL_MEMORY_PROJECT_CODENAME_MUTATE:
            raise ContractError("policy capability is unsupported")
        if self.decision not in {"ALLOWED", "DENIED"}:
            raise ContractError("policy decision is unsupported")
        require_digest(self.payload_digest, "payloadDigest")
        require_digest(self.action_digest, "actionDigest")
        require_digest(self.decision_fingerprint, "decisionFingerprint")


@dataclass(frozen=True)
class RollbackAuthorizationRefV1:
    schema_version: int
    rollback_authorization_ref_id: str
    authority: str
    actor_ref_id: str
    actor_evidence_ref_id: str
    consent_ref_id: str
    memory_item_id: str
    memory_class: str
    subject_namespace: str
    subject_key: str
    expected_active_revision_id: str
    restore_revision_id: str
    target_value_digest: str
    operation: str
    purpose: str
    confirmation_event_ref: str
    action_digest: str
    authorized_at: str
    authorization_fingerprint: str

    def validate_shape(self) -> None:
        if self.schema_version != SCHEMA_VERSION:
            raise ContractError("rollback schema version is unsupported")
        for field, value in (
            ("rollbackAuthorizationRefId", self.rollback_authorization_ref_id),
            ("actorRefId", self.actor_ref_id),
            ("actorEvidenceRefId", self.actor_evidence_ref_id),
            ("consentRefId", self.consent_ref_id),
            ("memoryItemId", self.memory_item_id),
            ("subjectKey", self.subject_key),
            ("expectedActiveRevisionId", self.expected_active_revision_id),
            ("restoreRevisionId", self.restore_revision_id),
            ("confirmationEventRef", self.confirmation_event_ref),
        ):
            require_id(value, field)
        if self.authority != USER_ROLLBACK_AUTHORITY_V1:
            raise ContractError("rollback authority is unsupported")
        if self.operation != RESTORE:
            raise ContractError("rollback authorization is RESTORE-only")
        require_digest(self.target_value_digest, "targetValueDigest")
        require_digest(self.action_digest, "actionDigest")
        require_digest(self.authorization_fingerprint, "authorizationFingerprint")


def consent_semantics(action: FrozenMemoryActionV1, **values: str) -> Dict[str, Any]:
    """Canonical semantic fields for a consent fingerprint."""
    return {
        "schemaVersion": SCHEMA_VERSION,
        "authority": LOCAL_CONSENT_AUTHORITY_V1,
        "actorRefId": action.actor_ref_id,
        "actorEvidenceRefId": values["actor_evidence_ref_id"],
        "memoryClass": action.memory_class,
        "subjectNamespace": action.subject_namespace,
        "subjectKey": action.subject_key,
        "operation": action.operation,
        "payloadDigest": action.payload_digest,
        "expectedActiveRevisionId": action.expected_active_revision_id,
        "restoreRevisionId": action.restore_revision_id,
        "purpose": action.purpose,
        "issuerType": USER_CONFIRMATION,
        "issuerRef": values["issuer_ref"],
        "intentRefId": values["intent_ref_id"],
        "privacyNoticeVersion": values["privacy_notice_version"],
        "actionDigest": action.action_digest,
    }
