"""Closed, canonical, length-prefixed broker protocol; no transport listener."""

from __future__ import annotations

import json
import struct
from dataclasses import dataclass
from typing import Any

import rfc8785

from lilith_memory.owner_proof import OwnerAssertionV1, OwnerProofError
from .request import SYNTHETIC_FIXTURE_ID


PROTOCOL = "LILITH_MEMORY_BROKER"
VERSION = 1
MAX_FRAME_BYTES = 16 * 1024
OPERATIONS = frozenset({"HEALTH", "ACCESS_CONTEXT", "PREPARE_SYNTHETIC", "CONFIRM_SYNTHETIC", "CANCEL"})
_ENVELOPE = frozenset({"protocol", "schemaVersion", "operation", "payload"})


class ProtocolError(ValueError):
    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


@dataclass(frozen=True)
class BrokerMessageV1:
    operation: str
    payload: dict[str, Any]


def _unique_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ProtocolError("DUPLICATE_FIELD")
        result[key] = value
    return result


def _reject_constant(_value: str) -> None:
    raise ProtocolError("INVALID_JSON_CONSTANT")


def parse_frame(frame: bytes) -> BrokerMessageV1:
    if not isinstance(frame, bytes) or len(frame) < 4:
        raise ProtocolError("TRUNCATED_FRAME")
    length = struct.unpack(">I", frame[:4])[0]
    if length == 0 or length > MAX_FRAME_BYTES:
        raise ProtocolError("INVALID_FRAME_LENGTH")
    if len(frame) != length + 4:
        raise ProtocolError("FRAME_LENGTH_MISMATCH")
    raw = frame[4:]
    try:
        value = json.loads(
            raw.decode("utf-8"), object_pairs_hook=_unique_pairs,
            parse_constant=_reject_constant,
        )
    except (UnicodeError, ValueError, TypeError) as exc:
        raise ProtocolError("INVALID_JSON") from exc
    if not isinstance(value, dict) or set(value) != _ENVELOPE:
        raise ProtocolError("INVALID_ENVELOPE")
    try:
        if raw != rfc8785.dumps(value):
            raise ProtocolError("NONCANONICAL_JSON")
    except (rfc8785.CanonicalizationError, OverflowError) as exc:
        raise ProtocolError("INVALID_CANONICAL_JSON") from exc
    if value["protocol"] != PROTOCOL or type(value["schemaVersion"]) is not int or value["schemaVersion"] != VERSION:
        raise ProtocolError("UNSUPPORTED_VERSION")
    operation = value["operation"]
    if not isinstance(operation, str) or operation not in OPERATIONS:
        raise ProtocolError("UNSUPPORTED_OPERATION")
    payload = value["payload"]
    if not isinstance(payload, dict):
        raise ProtocolError("INVALID_PAYLOAD")
    expected = {
        "HEALTH": frozenset(),
        "ACCESS_CONTEXT": frozenset(),
        "PREPARE_SYNTHETIC": frozenset({"fixtureId"}),
        "CONFIRM_SYNTHETIC": frozenset({"challengeId", "assertion"}),
        "CANCEL": frozenset({"challengeId"}),
    }[operation]
    if set(payload) != expected:
        raise ProtocolError("INVALID_PAYLOAD_FIELDS")
    if operation == "PREPARE_SYNTHETIC" and payload["fixtureId"] != SYNTHETIC_FIXTURE_ID:
        raise ProtocolError("UNKNOWN_FIXTURE")
    if operation in {"CONFIRM_SYNTHETIC", "CANCEL"}:
        challenge_id = payload["challengeId"]
        if not isinstance(challenge_id, str) or not challenge_id.startswith("och.") or len(challenge_id) > 128:
            raise ProtocolError("INVALID_CHALLENGE_ID")
    if operation == "CONFIRM_SYNTHETIC":
        try:
            OwnerAssertionV1.from_dict(payload["assertion"])
        except (OwnerProofError, TypeError, KeyError) as exc:
            raise ProtocolError("INVALID_ASSERTION") from exc
    return BrokerMessageV1(operation, payload)


def encode_frame(operation: str, payload: dict[str, Any]) -> bytes:
    raw = rfc8785.dumps({
        "protocol": PROTOCOL, "schemaVersion": VERSION,
        "operation": operation, "payload": payload,
    })
    if not 0 < len(raw) <= MAX_FRAME_BYTES:
        raise ProtocolError("INVALID_FRAME_LENGTH")
    frame = struct.pack(">I", len(raw)) + raw
    parse_frame(frame)
    return frame
