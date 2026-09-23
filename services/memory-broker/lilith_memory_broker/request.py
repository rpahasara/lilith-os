"""Broker-owned, closed owner request and synthetic action construction."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from typing import Any, Mapping

import rfc8785

from lilith_memory import canonical_contracts as C
from lilith_memory.canonical_authority import LocalOwnerAuthority


PROTOCOL = "LILITH_OWNER_MEMORY_REQUEST"
SCHEMA_VERSION = 1
DOMAIN = b"LILITH_OWNER_MEMORY_REQUEST_V1\x00"
LOGICAL_OWNER_ID = "owner.ravindu.v1"
SYNTHETIC_ACCESS_IDENTITY = "user:synthetic-owner@example.invalid"
SYNTHETIC_FIXTURE_ID = "fixture.b1b1.synthetic-codename.v1"
SYNTHETIC_MEMORY_CLASS = "SYNTHETIC_PROJECT_CODENAME_FACT"
SYNTHETIC_NOTICE = "privacy.synthetic.v1"
SYNTHETIC_INTENT = "intent.synthetic.b1b1"
_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}\Z")
_HEX = re.compile(r"[0-9a-f]{64}\Z")
_FIELDS = frozenset({
    "protocol", "schemaVersion", "challengeId", "logicalOwnerId",
    "accessIdentity", "actorRefId", "action", "actionDigest",
    "memoryItemId", "expectedActiveRevisionId", "restoreTargetRevisionId",
    "restoreTargetDigest", "privacyNoticeVersion", "intentRefId",
    "operation", "purpose", "memoryClass", "subjectNamespace", "subjectKey",
})
_ACTION_FIELDS = frozenset({
    "schemaVersion", "actorRefId", "operation", "memoryClass",
    "subjectNamespace", "subjectKey", "valueSchema", "payloadDigest",
    "expectedActiveRevisionId", "restoreRevisionId", "purpose",
})


class RequestError(ValueError):
    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


def synthetic_action(fixture_id: str) -> C.FrozenMemoryActionV1:
    """Only this governed fixture can create a B1b-1 action."""
    if fixture_id != SYNTHETIC_FIXTURE_ID:
        raise RequestError("UNKNOWN_SYNTHETIC_FIXTURE")
    action = C.FrozenMemoryActionV1(
        schema_version=1,
        actor_ref_id=LocalOwnerAuthority.ACTOR.actor_ref_id,
        operation=C.CREATE,
        memory_class=SYNTHETIC_MEMORY_CLASS,
        subject_namespace="project.synthetic",
        subject_key="codename",
        value_schema="SyntheticCodenameV1",
        payload_digest=hashlib.sha256(b"TEST_ONLY_B1B1_PAYLOAD_BINDING").hexdigest(),
        expected_active_revision_id=None,
        restore_revision_id=None,
        purpose=C.LONG_TERM_PERSONAL_PROJECT_RECALL,
    )
    action.validate()
    return action


def _action_from_dict(value: Any) -> C.FrozenMemoryActionV1:
    if not isinstance(value, dict) or set(value) != _ACTION_FIELDS:
        raise RequestError("INVALID_ACTION_FIELDS")
    action = C.FrozenMemoryActionV1(
        value["schemaVersion"], value["actorRefId"], value["operation"],
        value["memoryClass"], value["subjectNamespace"], value["subjectKey"],
        value["valueSchema"], value["payloadDigest"],
        value["expectedActiveRevisionId"], value["restoreRevisionId"], value["purpose"],
    )
    try:
        action.validate()
    except C.ContractError as exc:
        raise RequestError("INVALID_ACTION") from exc
    return action


@dataclass(frozen=True)
class OwnerRequestV1:
    challenge_id: str
    logical_owner_id: str
    access_identity: str
    action: C.FrozenMemoryActionV1
    memory_item_id: str | None
    restore_target_digest: str | None
    privacy_notice_version: str
    intent_ref_id: str

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> OwnerRequestV1:
        if not isinstance(value, dict) or set(value) != _FIELDS:
            raise RequestError("INVALID_REQUEST_FIELDS")
        if value["protocol"] != PROTOCOL or type(value["schemaVersion"]) is not int or value["schemaVersion"] != SCHEMA_VERSION:
            raise RequestError("UNSUPPORTED_REQUEST_VERSION")
        action = _action_from_dict(value["action"])
        result = cls(
            value["challengeId"], value["logicalOwnerId"],
            value["accessIdentity"], action, value["memoryItemId"],
            value["restoreTargetDigest"], value["privacyNoticeVersion"],
            value["intentRefId"],
        )
        result.validate()
        if value != result.to_dict():
            raise RequestError("REQUEST_BINDING_MISMATCH")
        return result

    def validate(self) -> None:
        if not isinstance(self.challenge_id, str) or not _ID.fullmatch(self.challenge_id):
            raise RequestError("INVALID_CHALLENGE_ID")
        if self.logical_owner_id != LOGICAL_OWNER_ID:
            raise RequestError("UNKNOWN_LOGICAL_OWNER")
        if self.access_identity != SYNTHETIC_ACCESS_IDENTITY:
            raise RequestError("NON_SYNTHETIC_ACCESS_IDENTITY")
        if not isinstance(self.intent_ref_id, str) or not _ID.fullmatch(self.intent_ref_id):
            raise RequestError("INVALID_INTENT_REF")
        if not isinstance(self.privacy_notice_version, str) or not _ID.fullmatch(self.privacy_notice_version):
            raise RequestError("INVALID_PRIVACY_NOTICE")
        if self.memory_item_id is not None and (not isinstance(self.memory_item_id, str) or not _ID.fullmatch(self.memory_item_id)):
            raise RequestError("INVALID_MEMORY_ITEM")
        if self.restore_target_digest is not None and (not isinstance(self.restore_target_digest, str) or not _HEX.fullmatch(self.restore_target_digest)):
            raise RequestError("INVALID_RESTORE_DIGEST")
        self.action.validate()
        if self.action != synthetic_action(SYNTHETIC_FIXTURE_ID):
            raise RequestError("NON_SYNTHETIC_ACTION")
        if self.memory_item_id is not None or self.restore_target_digest is not None:
            raise RequestError("INVALID_SYNTHETIC_SHAPE")
        if self.privacy_notice_version != SYNTHETIC_NOTICE or self.intent_ref_id != SYNTHETIC_INTENT:
            raise RequestError("NON_SYNTHETIC_CONTEXT")

    def to_dict(self) -> dict[str, Any]:
        self.validate()
        action = self.action
        return {
            "protocol": PROTOCOL, "schemaVersion": SCHEMA_VERSION,
            "challengeId": self.challenge_id, "logicalOwnerId": self.logical_owner_id,
            "accessIdentity": self.access_identity, "actorRefId": action.actor_ref_id,
            "action": action.semantic_dict(), "actionDigest": action.action_digest,
            "memoryItemId": self.memory_item_id,
            "expectedActiveRevisionId": action.expected_active_revision_id,
            "restoreTargetRevisionId": action.restore_revision_id,
            "restoreTargetDigest": self.restore_target_digest,
            "privacyNoticeVersion": self.privacy_notice_version,
            "intentRefId": self.intent_ref_id, "operation": action.operation,
            "purpose": action.purpose, "memoryClass": action.memory_class,
            "subjectNamespace": action.subject_namespace, "subjectKey": action.subject_key,
        }

    def canonical_bytes(self) -> bytes:
        return rfc8785.dumps(self.to_dict())

    @property
    def request_digest(self) -> str:
        return hashlib.sha256(DOMAIN + self.canonical_bytes()).hexdigest()


def construct_synthetic_request(challenge_id: str, fixture_id: str = SYNTHETIC_FIXTURE_ID) -> OwnerRequestV1:
    request = OwnerRequestV1(
        challenge_id, LOGICAL_OWNER_ID, SYNTHETIC_ACCESS_IDENTITY,
        synthetic_action(fixture_id), None, None, SYNTHETIC_NOTICE,
        SYNTHETIC_INTENT,
    )
    request.validate()
    return request
