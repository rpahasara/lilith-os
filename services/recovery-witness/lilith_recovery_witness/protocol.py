"""Closed, canonical, length-prefixed recovery-witness protocol (PR-1S).

Framing is the authority signer's (B1b-3d §10): a 4-byte big-endian length,
RFC 8785 JSON, unique keys, no JSON constants, an exact envelope. Frames are
at most 64 KiB because owner operations carry one authorization and one
complete hold-store snapshot.

Two sockets, two closed operation sets (B1b-3d §10; preflight §10):

- owner socket (`root:root 0600`, peer uid 0): `HEALTH`, `READ_WITNESS`,
  `BOOTSTRAP`, `EXECUTE_REGISTRY_HEAD_ADVANCE`, `EXECUTE_EPOCH_ADVANCE`;
- signer socket (peer uid = `lilith-authority-dev`): `READ_WITNESS`,
  `RECORD_LEDGER_ADVANCE`.

No operation carries a witness body to sign, a digest, a key, a path, an
environment, or a signing domain: every witness is reconstructed by the
witness from fixed on-host inputs and planner rules. There is no generic
signing operation.
"""

from __future__ import annotations

import json
import re
import struct
from dataclasses import dataclass
from typing import Any

import rfc8785

PROTOCOL = "LILITH_RECOVERY_WITNESS_DEV"
VERSION = 1
MAX_FRAME_BYTES = 64 * 1024

HEALTH = "HEALTH"
READ_WITNESS = "READ_WITNESS"
BOOTSTRAP = "BOOTSTRAP"
EXECUTE_REGISTRY_HEAD_ADVANCE = "EXECUTE_REGISTRY_HEAD_ADVANCE"
EXECUTE_EPOCH_ADVANCE = "EXECUTE_EPOCH_ADVANCE"
RECORD_LEDGER_ADVANCE = "RECORD_LEDGER_ADVANCE"

OWNER = "OWNER"
SIGNER = "SIGNER"
ROLE_OPERATIONS = {
    OWNER: frozenset({HEALTH, READ_WITNESS, BOOTSTRAP, EXECUTE_REGISTRY_HEAD_ADVANCE, EXECUTE_EPOCH_ADVANCE}),
    SIGNER: frozenset({READ_WITNESS, RECORD_LEDGER_ADVANCE}),
}
OPERATIONS = frozenset().union(*ROLE_OPERATIONS.values())
MUTATING_OPERATIONS = frozenset({BOOTSTRAP, EXECUTE_REGISTRY_HEAD_ADVANCE, EXECUTE_EPOCH_ADVANCE,
                                 RECORD_LEDGER_ADVANCE})

_ENVELOPE = frozenset({"protocol", "schemaVersion", "operation", "payload"})
LEDGER_OBSERVATION_FIELDS = frozenset({"environment", "recoveryEpoch", "sequence", "head", "registryView",
                                       "signingKeyIds", "rowsConsistent", "terminalReopened"})
PAYLOAD_FIELDS = {
    HEALTH: frozenset(),
    READ_WITNESS: frozenset(),
    BOOTSTRAP: frozenset({"registryVersion", "ledgerObservation", "updatedAt"}),
    RECORD_LEDGER_ADVANCE: frozenset({"previousWitnessDigest", "ledgerSequence", "ledgerHead"}),
    EXECUTE_REGISTRY_HEAD_ADVANCE: frozenset({"authorization", "targetRegistryVersion", "holdStore"}),
    EXECUTE_EPOCH_ADVANCE: frozenset({"authorization", "targetRegistryVersion", "adoptionRecord",
                                      "ledgerSequence", "ledgerHead", "holdStore"}),
}
_HEX64 = re.compile(r"[0-9a-f]{64}\Z")


class ProtocolError(ValueError):
    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


@dataclass(frozen=True)
class WitnessMessageV1:
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


def _int(value: Any, minimum: int) -> None:
    if type(value) is not int or value < minimum:
        raise ProtocolError("INVALID_PAYLOAD_VALUE")


def _hex64(value: Any) -> None:
    if not isinstance(value, str) or _HEX64.fullmatch(value) is None:
        raise ProtocolError("INVALID_PAYLOAD_VALUE")


def _validate_payload(operation: str, payload: dict[str, Any]) -> None:
    if set(payload) != PAYLOAD_FIELDS[operation]:
        raise ProtocolError("INVALID_PAYLOAD_FIELDS")
    if operation == BOOTSTRAP:
        _int(payload["registryVersion"], 1)
        observation = payload["ledgerObservation"]
        if not isinstance(observation, dict) or set(observation) != LEDGER_OBSERVATION_FIELDS:
            raise ProtocolError("INVALID_PAYLOAD_VALUE")
        if not isinstance(payload["updatedAt"], str) or len(payload["updatedAt"]) > 32:
            raise ProtocolError("INVALID_PAYLOAD_VALUE")
    elif operation == RECORD_LEDGER_ADVANCE:
        _hex64(payload["previousWitnessDigest"])
        _int(payload["ledgerSequence"], 1)
        _hex64(payload["ledgerHead"])
    elif operation in (EXECUTE_REGISTRY_HEAD_ADVANCE, EXECUTE_EPOCH_ADVANCE):
        if not isinstance(payload["authorization"], dict) or not isinstance(payload["holdStore"], dict):
            raise ProtocolError("INVALID_PAYLOAD_VALUE")
        _int(payload["targetRegistryVersion"], 2)
        if operation == EXECUTE_EPOCH_ADVANCE:
            if not isinstance(payload["adoptionRecord"], dict):
                raise ProtocolError("INVALID_PAYLOAD_VALUE")
            _int(payload["ledgerSequence"], 1)
            _hex64(payload["ledgerHead"])


def parse_frame(frame: bytes, *, role: str) -> WitnessMessageV1:
    """Parse one frame for one socket role. Unknown or wrong-socket operations
    are refused before any payload is interpreted."""
    if role not in ROLE_OPERATIONS:
        raise ProtocolError("UNKNOWN_ROLE")
    if not isinstance(frame, bytes) or len(frame) < 4:
        raise ProtocolError("TRUNCATED_FRAME")
    length = struct.unpack(">I", frame[:4])[0]
    if length == 0 or length > MAX_FRAME_BYTES:
        raise ProtocolError("INVALID_FRAME_LENGTH")
    if len(frame) != length + 4:
        raise ProtocolError("FRAME_LENGTH_MISMATCH")
    raw = frame[4:]
    try:
        value = json.loads(raw.decode("utf-8"), object_pairs_hook=_unique_pairs, parse_constant=_reject_constant)
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
    if value["protocol"] != PROTOCOL or type(value["schemaVersion"]) is not int or value["schemaVersion"] != VERSION:
        raise ProtocolError("UNSUPPORTED_VERSION")
    operation = value["operation"]
    if not isinstance(operation, str) or operation not in OPERATIONS:
        raise ProtocolError("UNSUPPORTED_OPERATION")
    if operation not in ROLE_OPERATIONS[role]:
        raise ProtocolError("OPERATION_NOT_ON_THIS_SOCKET")
    payload = value["payload"]
    if not isinstance(payload, dict):
        raise ProtocolError("INVALID_PAYLOAD")
    _validate_payload(operation, payload)
    return WitnessMessageV1(operation, payload)


def encode_frame(operation: str, payload: dict[str, Any]) -> bytes:
    raw = rfc8785.dumps({"protocol": PROTOCOL, "schemaVersion": VERSION, "operation": operation, "payload": payload})
    if not 0 < len(raw) <= MAX_FRAME_BYTES:
        raise ProtocolError("INVALID_FRAME_LENGTH")
    return struct.pack(">I", len(raw)) + raw


def encode_response(payload: dict[str, Any]) -> bytes:
    raw = rfc8785.dumps({"protocol": PROTOCOL, "schemaVersion": VERSION, "payload": payload})
    if not 0 < len(raw) <= MAX_FRAME_BYTES:
        raise ProtocolError("RESPONSE_TOO_LARGE")
    return struct.pack(">I", len(raw)) + raw


def parse_response(frame: bytes) -> dict[str, Any]:
    """Client side: one response frame -> its payload (strict)."""
    if not isinstance(frame, bytes) or len(frame) < 4:
        raise ProtocolError("TRUNCATED_FRAME")
    length = struct.unpack(">I", frame[:4])[0]
    if length == 0 or length > MAX_FRAME_BYTES or len(frame) != length + 4:
        raise ProtocolError("INVALID_FRAME_LENGTH")
    raw = frame[4:]
    try:
        value = json.loads(raw.decode("utf-8"), object_pairs_hook=_unique_pairs, parse_constant=_reject_constant)
    except (UnicodeError, ValueError, TypeError) as exc:
        if isinstance(exc, ProtocolError):
            raise
        raise ProtocolError("INVALID_JSON") from exc
    if not isinstance(value, dict) or set(value) != {"protocol", "schemaVersion", "payload"} \
            or value["protocol"] != PROTOCOL or value["schemaVersion"] != VERSION or raw != rfc8785.dumps(value) \
            or not isinstance(value["payload"], dict):
        raise ProtocolError("INVALID_RESPONSE")
    return value["payload"]
