"""Closed, canonical, length-prefixed authority owner-socket protocol (B1b-3d L1).

Framing follows the memory broker V1 framing (design §10): a 4-byte
big-endian length, RFC 8785 JSON, at most 16 KiB, unique keys, no JSON
constants, exact envelope, and a closed operation set.

There is no operation that signs caller-supplied bytes, text, or digests, and
none that names a signing domain, separator, key, epoch, or registry version.
The only signing-related operation, `ISSUE_OWNER_EVIDENCE`, carries the
B1b-3b `OwnerEvidenceRequestV1` shape: a challenge reference plus the owner's
assertion and public credential over a frozen action. Every signed value is
derived by the signer, never taken from the request.

RR-39 adds a governed form of `ISSUE_OWNER_EVIDENCE` that also carries the exact owner challenge and the
complete root hold-store snapshot; the legacy form stays parseable and is always refused.

B1b-3e PR-1S adds exactly three recovery operations (preflight §15), each a
ledger journal write gated by the pure C-4 recovery gate, never a signature:
`RECOVERY_ADVANCE_EPOCH` (the exact K-ROOT epoch-advance authorization plus
the complete root hold-store snapshot), `RECOVERY_VOID_CHALLENGE` and
`RECOVERY_QUARANTINE_USE` (the snapshot only). Frames are at most 64 KiB so
one complete snapshot fits.

First Memory adds the authority-side evidence-use transport the L04 V2 adapter needs (B1b-3b lifecycle, now on the
signer's durable ledger): `RESERVE_EVIDENCE_USE`, `CONFIRM_EVIDENCE_USE`, `ABANDON_EVIDENCE_USE` (each with the
complete root hold-store snapshot, like recovery) and the read-only `LOOKUP_EVIDENCE_USE`. None of them signs.

Relationship origin: besides the project codename, the signer attests exactly one more purpose, the owner-provided
relationship origin, and only as CREATE of its one tuple (`RelationshipOriginActionV1`). The rule is stated here, in
the signer's own payload, rather than imported: the Core API module that defines the family
(`lilith_memory.memory_action_v2`) is not release payload, and a test pins the two definitions equal. The First
Interaction purpose stays refused: its identity is permanently suppressed (F9c2 FORGET).
"""

from __future__ import annotations

import dataclasses
import json
import struct
from dataclasses import dataclass
from typing import Any

import rfc8785
from lilith_memory import canonical_contracts as C
from lilith_memory.owner_proof import OwnerAssertionV1, OwnerCredentialV1, OwnerProofError

PROTOCOL = "LILITH_AUTHORITY_DEV"
VERSION = 1
MAX_FRAME_BYTES = 64 * 1024
HEALTH = "HEALTH"
ISSUE_OWNER_EVIDENCE = "ISSUE_OWNER_EVIDENCE"
RECOVERY_ADVANCE_EPOCH = "RECOVERY_ADVANCE_EPOCH"
RECOVERY_VOID_CHALLENGE = "RECOVERY_VOID_CHALLENGE"
RECOVERY_QUARANTINE_USE = "RECOVERY_QUARANTINE_USE"
RECOVERY_OPERATIONS = frozenset({RECOVERY_ADVANCE_EPOCH, RECOVERY_VOID_CHALLENGE, RECOVERY_QUARANTINE_USE})
RESERVE_EVIDENCE_USE = "RESERVE_EVIDENCE_USE"
CONFIRM_EVIDENCE_USE = "CONFIRM_EVIDENCE_USE"
ABANDON_EVIDENCE_USE = "ABANDON_EVIDENCE_USE"
LOOKUP_EVIDENCE_USE = "LOOKUP_EVIDENCE_USE"
USE_WRITE_OPERATIONS = frozenset({RESERVE_EVIDENCE_USE, CONFIRM_EVIDENCE_USE, ABANDON_EVIDENCE_USE})
USE_OPERATIONS = USE_WRITE_OPERATIONS | {LOOKUP_EVIDENCE_USE}
OPERATIONS = frozenset({HEALTH, ISSUE_OWNER_EVIDENCE}) | RECOVERY_OPERATIONS | USE_OPERATIONS
_ENVELOPE = frozenset({"protocol", "schemaVersion", "operation", "payload"})
_PAYLOAD_FIELDS = {
    HEALTH: frozenset(),
    ISSUE_OWNER_EVIDENCE: frozenset({"challengeId", "action", "assertion", "ownerCredential"}),
    RECOVERY_ADVANCE_EPOCH: frozenset({"epochAuthorization", "holdStore"}),
    RECOVERY_VOID_CHALLENGE: frozenset({"holdStore"}),
    RECOVERY_QUARANTINE_USE: frozenset({"holdStore"}),
    RESERVE_EVIDENCE_USE: frozenset({"holdStore", "evidenceId", "evidenceDigest", "challengeId", "proposalRefId",
                                     "actionDigest"}),
    CONFIRM_EVIDENCE_USE: frozenset({"holdStore", "evidenceId", "proposalRefId", "admissionId", "revisionId"}),
    ABANDON_EVIDENCE_USE: frozenset({"holdStore", "evidenceId", "proposalRefId"}),
    LOOKUP_EVIDENCE_USE: frozenset({"evidenceId"}),
}
_USE_DIGEST_FIELDS = frozenset({"evidenceDigest", "actionDigest"})
# RR-39: the governed issuance form adds the exact owner challenge and the complete root hold-store snapshot (the
# recovery-handler pattern). The legacy form above stays parseable and is always refused (no challenge to verify).
GOVERNED_ISSUE_FIELDS = _PAYLOAD_FIELDS[ISSUE_OWNER_EVIDENCE] | {"challenge", "holdStore"}
# The relationship-origin family as the signer attests it (equal to memory_action_v2.RELATIONSHIP_ORIGIN).
RELATIONSHIP_ORIGIN_PURPOSE = "LONG_TERM_OWNER_RELATIONSHIP_ORIGIN_RECALL"
RELATIONSHIP_ORIGIN_IDENTITY = ("OWNER_PROVIDED_RELATIONSHIP_ORIGIN", "lilith.core.relationship",
                                "origin.owner-statement")
RELATIONSHIP_ORIGIN_VALUE_SCHEMA = "OwnerRelationshipOriginV1"
# CREATE, and the owner-approved correction (SUPERSEDE) of the active revision; never RESTORE or FORGET.
RELATIONSHIP_ORIGIN_OPERATIONS = frozenset({C.CREATE, C.SUPERSEDE})
# The only purposes this signer attests. Each is also gated by L04's canonical config and tuple registry.
SIGNER_PURPOSES = frozenset({C.LONG_TERM_PERSONAL_PROJECT_RECALL, RELATIONSHIP_ORIGIN_PURPOSE})
_ACTION_FIELDS = frozenset({
    "schemaVersion", "actorRefId", "operation", "memoryClass", "subjectNamespace", "subjectKey",
    "valueSchema", "payloadDigest", "expectedActiveRevisionId", "restoreRevisionId", "purpose",
})


@dataclass(frozen=True)
class RelationshipOriginActionV1(C.FrozenMemoryActionV1):
    """A relationship-origin action: the unchanged `FrozenMemoryActionV1` fields and digest encoding; valid only as
    CREATE, or an owner-approved SUPERSEDE (correction) bound to the active revision it replaces, of the one tuple with
    its value schema (the SUPERSEDE shape and every other field checked by the unchanged base validator)."""

    def validate(self) -> None:
        if self.purpose != RELATIONSHIP_ORIGIN_PURPOSE:
            raise C.ContractError("purpose is unsupported")
        fields = {f.name: getattr(self, f.name) for f in dataclasses.fields(self)}
        C.FrozenMemoryActionV1(**{**fields, "purpose": C.LONG_TERM_PERSONAL_PROJECT_RECALL}).validate()
        if self.operation not in RELATIONSHIP_ORIGIN_OPERATIONS or (tuple(self.identity), self.value_schema) != (
                RELATIONSHIP_ORIGIN_IDENTITY, RELATIONSHIP_ORIGIN_VALUE_SCHEMA):
            raise C.ContractError("relationship origin is CREATE or SUPERSEDE of its one tuple only")


class ProtocolError(ValueError):
    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


@dataclass(frozen=True)
class AuthorityMessageV1:
    operation: str
    payload: dict[str, Any]


@dataclass(frozen=True)
class IssueOwnerEvidenceRequestV1:
    """Wire form of B1b-3b `OwnerEvidenceRequestV1`. No signed value inside."""

    challenge_id: str
    action: C.FrozenMemoryActionV1
    assertion: OwnerAssertionV1
    owner_credential: OwnerCredentialV1
    challenge: dict[str, Any] | None = None       # governed form only (RR-39)
    hold_store: dict[str, Any] | None = None      # governed form only (RR-39)
    raw_assertion: dict[str, Any] | None = None

    @property
    def governed(self) -> bool:
        return self.challenge is not None and self.hold_store is not None


def _unique_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ProtocolError("DUPLICATE_FIELD")
        result[key] = value
    return result


def _reject_constant(_value: str) -> None:
    raise ProtocolError("INVALID_JSON_CONSTANT")


def parse_frame(frame: bytes) -> AuthorityMessageV1:
    if not isinstance(frame, bytes) or len(frame) < 4:
        raise ProtocolError("TRUNCATED_FRAME")
    length = struct.unpack(">I", frame[:4])[0]
    if length == 0 or length > MAX_FRAME_BYTES:
        raise ProtocolError("INVALID_FRAME_LENGTH")
    if len(frame) != length + 4:
        raise ProtocolError("FRAME_LENGTH_MISMATCH")
    raw = frame[4:]
    try:
        value = json.loads(raw.decode("utf-8"), object_pairs_hook=_unique_pairs,
                           parse_constant=_reject_constant)
    except (UnicodeError, ValueError, TypeError) as exc:
        if isinstance(exc, ProtocolError):
            raise
        raise ProtocolError("INVALID_JSON") from exc
    if not isinstance(value, dict) or set(value) != _ENVELOPE:
        raise ProtocolError("INVALID_ENVELOPE")
    try:
        if raw != rfc8785.dumps(value):
            raise ProtocolError("NONCANONICAL_JSON")
    except (rfc8785.CanonicalizationError, OverflowError) as exc:
        raise ProtocolError("INVALID_CANONICAL_JSON") from exc
    if value["protocol"] != PROTOCOL or type(value["schemaVersion"]) is not int \
            or value["schemaVersion"] != VERSION:
        raise ProtocolError("UNSUPPORTED_VERSION")
    operation = value["operation"]
    if not isinstance(operation, str) or operation not in OPERATIONS:
        raise ProtocolError("UNSUPPORTED_OPERATION")
    payload = value["payload"]
    if not isinstance(payload, dict):
        raise ProtocolError("INVALID_PAYLOAD")
    if set(payload) != _PAYLOAD_FIELDS[operation] and not (
            operation == ISSUE_OWNER_EVIDENCE and set(payload) == GOVERNED_ISSUE_FIELDS):
        raise ProtocolError("INVALID_PAYLOAD_FIELDS")
    if operation == ISSUE_OWNER_EVIDENCE:
        parse_issue_request(payload)
    elif operation in RECOVERY_OPERATIONS:
        if not isinstance(payload["holdStore"], dict):
            raise ProtocolError("INVALID_HOLD_STORE")
        if operation == RECOVERY_ADVANCE_EPOCH and not isinstance(payload["epochAuthorization"], dict):
            raise ProtocolError("INVALID_EPOCH_AUTHORIZATION")
    elif operation in USE_OPERATIONS:
        parse_use_request(payload, operation)
    return AuthorityMessageV1(operation, payload)


def parse_use_request(payload: dict[str, Any], operation: str) -> dict[str, Any]:
    """Shape-only validation of an evidence-use request; every rule is the handler's and the journal's."""
    if operation not in USE_OPERATIONS or not isinstance(payload, dict) or set(payload) != _PAYLOAD_FIELDS[operation]:
        raise ProtocolError("INVALID_PAYLOAD_FIELDS")
    for name, value in payload.items():
        if name == "holdStore":
            if not isinstance(value, dict):
                raise ProtocolError("INVALID_HOLD_STORE")
        elif name in _USE_DIGEST_FIELDS:
            if not (isinstance(value, str) and len(value) == 64 and all(c in "0123456789abcdef" for c in value)):
                raise ProtocolError("INVALID_USE_DIGEST")
        elif not (isinstance(value, str) and 0 < len(value) <= 128 and value.isascii() and value.isprintable()):
            raise ProtocolError("INVALID_USE_IDENTIFIER")
    return dict(payload)


def parse_issue_request(payload: dict[str, Any]) -> IssueOwnerEvidenceRequestV1:
    if not isinstance(payload, dict) or set(payload) not in (_PAYLOAD_FIELDS[ISSUE_OWNER_EVIDENCE],
                                                             GOVERNED_ISSUE_FIELDS):
        raise ProtocolError("INVALID_PAYLOAD_FIELDS")
    challenge_id = payload["challengeId"]
    if not isinstance(challenge_id, str) or not challenge_id.startswith("och.") or len(challenge_id) > 128:
        raise ProtocolError("INVALID_CHALLENGE_ID")
    raw_action = payload["action"]
    if not isinstance(raw_action, dict) or set(raw_action) != _ACTION_FIELDS:
        raise ProtocolError("INVALID_ACTION")
    purpose = raw_action["purpose"]
    if not isinstance(purpose, str) or purpose not in SIGNER_PURPOSES:
        raise ProtocolError("INVALID_ACTION")
    action_type = RelationshipOriginActionV1 if purpose == RELATIONSHIP_ORIGIN_PURPOSE else C.FrozenMemoryActionV1
    try:
        action = action_type(*(raw_action[key] for key in (
            "schemaVersion", "actorRefId", "operation", "memoryClass", "subjectNamespace", "subjectKey",
            "valueSchema", "payloadDigest", "expectedActiveRevisionId", "restoreRevisionId", "purpose",
        )))
        action.validate()
        if action_type is C.FrozenMemoryActionV1 and tuple(action.identity) == RELATIONSHIP_ORIGIN_IDENTITY:
            raise C.ContractError("purpose and memory tuple do not match")
    except (C.ContractError, TypeError, ValueError) as exc:
        raise ProtocolError("INVALID_ACTION") from exc
    if action.operation == C.FORGET:
        # Erasure is Privacy-owned (B1b-3b); the OWNER_ACTOR signer never attests it.
        raise ProtocolError("PRIVACY_OWNED_OPERATION")
    try:
        assertion = OwnerAssertionV1.from_dict(payload["assertion"])
    except (OwnerProofError, TypeError, KeyError) as exc:
        raise ProtocolError("INVALID_ASSERTION") from exc
    try:
        credential = OwnerCredentialV1.from_dict(payload["ownerCredential"])
    except (OwnerProofError, TypeError, KeyError) as exc:
        raise ProtocolError("INVALID_OWNER_CREDENTIAL") from exc
    if set(payload) == GOVERNED_ISSUE_FIELDS:
        if not isinstance(payload["challenge"], dict):
            raise ProtocolError("INVALID_CHALLENGE")
        if not isinstance(payload["holdStore"], dict):
            raise ProtocolError("INVALID_HOLD_STORE")
        return IssueOwnerEvidenceRequestV1(challenge_id, action, assertion, credential, dict(payload["challenge"]),
                                           dict(payload["holdStore"]), dict(payload["assertion"]))
    return IssueOwnerEvidenceRequestV1(challenge_id, action, assertion, credential)


def encode_frame(operation: str, payload: dict[str, Any]) -> bytes:
    raw = rfc8785.dumps({"protocol": PROTOCOL, "schemaVersion": VERSION,
                         "operation": operation, "payload": payload})
    if not 0 < len(raw) <= MAX_FRAME_BYTES:
        raise ProtocolError("INVALID_FRAME_LENGTH")
    frame = struct.pack(">I", len(raw)) + raw
    parse_frame(frame)
    return frame


def encode_response(payload: dict[str, Any]) -> bytes:
    raw = rfc8785.dumps({"protocol": PROTOCOL, "schemaVersion": VERSION, "payload": payload})
    if not 0 < len(raw) <= MAX_FRAME_BYTES:
        raise ProtocolError("RESPONSE_TOO_LARGE")
    return struct.pack(">I", len(raw)) + raw
