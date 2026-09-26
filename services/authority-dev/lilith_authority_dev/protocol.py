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
"""

from __future__ import annotations

import json
import struct
from dataclasses import dataclass
from typing import Any

import rfc8785
from lilith_memory import canonical_contracts as C
from lilith_memory.owner_proof import OwnerAssertionV1, OwnerCredentialV1, OwnerProofError

PROTOCOL = "LILITH_AUTHORITY_DEV"
VERSION = 1
MAX_FRAME_BYTES = 16 * 1024
HEALTH = "HEALTH"
ISSUE_OWNER_EVIDENCE = "ISSUE_OWNER_EVIDENCE"
OPERATIONS = frozenset({HEALTH, ISSUE_OWNER_EVIDENCE})
_ENVELOPE = frozenset({"protocol", "schemaVersion", "operation", "payload"})
_PAYLOAD_FIELDS = {
    HEALTH: frozenset(),
    ISSUE_OWNER_EVIDENCE: frozenset({"challengeId", "action", "assertion", "ownerCredential"}),
}
_ACTION_FIELDS = frozenset({
    "schemaVersion", "actorRefId", "operation", "memoryClass", "subjectNamespace", "subjectKey",
    "valueSchema", "payloadDigest", "expectedActiveRevisionId", "restoreRevisionId", "purpose",
})


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
    if set(payload) != _PAYLOAD_FIELDS[operation]:
        raise ProtocolError("INVALID_PAYLOAD_FIELDS")
    if operation == ISSUE_OWNER_EVIDENCE:
        parse_issue_request(payload)
    return AuthorityMessageV1(operation, payload)


def parse_issue_request(payload: dict[str, Any]) -> IssueOwnerEvidenceRequestV1:
    if not isinstance(payload, dict) or set(payload) != _PAYLOAD_FIELDS[ISSUE_OWNER_EVIDENCE]:
        raise ProtocolError("INVALID_PAYLOAD_FIELDS")
    challenge_id = payload["challengeId"]
    if not isinstance(challenge_id, str) or not challenge_id.startswith("och.") or len(challenge_id) > 128:
        raise ProtocolError("INVALID_CHALLENGE_ID")
    raw_action = payload["action"]
    if not isinstance(raw_action, dict) or set(raw_action) != _ACTION_FIELDS:
        raise ProtocolError("INVALID_ACTION")
    try:
        action = C.FrozenMemoryActionV1(*(raw_action[key] for key in (
            "schemaVersion", "actorRefId", "operation", "memoryClass", "subjectNamespace", "subjectKey",
            "valueSchema", "payloadDigest", "expectedActiveRevisionId", "restoreRevisionId", "purpose",
        )))
        action.validate()
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
