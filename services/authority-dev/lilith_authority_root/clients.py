"""Root clients of the two root-only owner sockets (PR-1S).

- the authority signer's `/run/lilith-authority-dev/owner.sock`: `HEALTH`
  (B4 for the verifier) and the three C-4 recovery operations, each sent
  with the complete root hold-store snapshot;
- the recovery witness's `/run/lilith-recovery-witness/owner.sock`:
  `HEALTH`, `READ_WITNESS`, `BOOTSTRAP`, and the inert transition
  executions.

One frame, one response, close. The clients add nothing the caller did not
name and never interpret a response as authority.
"""

from __future__ import annotations

import json
import socket
import struct
from typing import Any, Mapping

from lilith_authority_dev import protocol as AP
from lilith_authority_host import paths as P
from lilith_recovery_witness import protocol as WP

TIMEOUT_SECONDS = 10.0


def _exchange(path: str, frame: bytes, *, limit: int, timeout: float = TIMEOUT_SECONDS) -> bytes:
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
        client.settimeout(timeout)
        client.connect(path)
        client.sendall(frame)
        header = b""
        while len(header) < 4:
            chunk = client.recv(4 - len(header))
            if not chunk:
                raise OSError("the service closed the connection without a response")
            header += chunk
        length = struct.unpack(">I", header)[0]
        if not 0 < length <= limit:
            raise ValueError("invalid response length")
        body = b""
        while len(body) < length:
            chunk = client.recv(length - len(body))
            if not chunk:
                raise OSError("truncated response")
            body += chunk
    return header + body


def _authority_response(frame: bytes) -> dict[str, Any]:
    raw = frame[4:]
    value = json.loads(raw)
    if not isinstance(value, dict) or set(value) != {"protocol", "schemaVersion", "payload"} \
            or value["protocol"] != AP.PROTOCOL or value["schemaVersion"] != AP.VERSION:
        raise ValueError("invalid authority response")
    return value["payload"]


def signer_health(*, path: str = P.AUTHORITY_OWNER_SOCKET) -> Mapping[str, Any]:
    """The signer's HEALTH (B4). A signer claim: never authority on its own."""
    payload = _authority_response(_exchange(path, AP.encode_frame(AP.HEALTH, {}), limit=AP.MAX_FRAME_BYTES))
    if payload.get("status") != "OK" or not isinstance(payload.get("health"), dict):
        raise ValueError("signer HEALTH refused")
    return payload["health"]


def signer_recovery(operation: str, *, hold_snapshot: Mapping[str, Any],
                    epoch_authorization: Mapping[str, Any] | None = None,
                    path: str = P.AUTHORITY_OWNER_SOCKET) -> Mapping[str, Any]:
    if operation not in AP.RECOVERY_OPERATIONS:
        raise ValueError("not a recovery operation")
    payload: dict[str, Any] = {"holdStore": dict(hold_snapshot)}
    if operation == AP.RECOVERY_ADVANCE_EPOCH:
        payload["epochAuthorization"] = dict(epoch_authorization or {})
    return _authority_response(_exchange(path, AP.encode_frame(operation, payload), limit=AP.MAX_FRAME_BYTES))


def witness_owner(operation: str, payload: Mapping[str, Any], *,
                  path: str = P.WITNESS_OWNER_SOCKET) -> Mapping[str, Any]:
    if operation not in WP.ROLE_OPERATIONS[WP.OWNER]:
        raise ValueError("not a witness owner operation")
    return WP.parse_response(_exchange(path, WP.encode_frame(operation, dict(payload)), limit=WP.MAX_FRAME_BYTES))
