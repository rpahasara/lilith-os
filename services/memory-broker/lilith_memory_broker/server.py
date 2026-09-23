"""Inherited-AF_UNIX-only synthetic DEV IPC adapter; never binds a socket."""

from __future__ import annotations

import os
import socket
import struct
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Callable
from pathlib import Path

import rfc8785

from .dev_config import DevConfig
from .dev_core import DevSyntheticBrokerCore
from .dev_state import DevOwnerControlState
from .protocol import MAX_FRAME_BYTES, PROTOCOL, ProtocolError, parse_frame
from .synthetic_evidence import SyntheticEvidenceStore


ALLOWED_IPC_OPERATIONS = frozenset({"HEALTH", "PREPARE_SYNTHETIC", "CONFIRM_SYNTHETIC", "CANCEL"})
SOCKET_PATH = "/run/lilith-memory/owner.sock"
CONNECTION_TIMEOUT_SECONDS = 3.0
MAX_CLIENTS = 8


class ServerError(RuntimeError):
    pass


def kernel_peer_uid(conn: socket.socket) -> int:
    """Linux SO_PEERCRED is the only operational source of local peer UID."""
    if not hasattr(socket, "SO_PEERCRED"):
        raise ServerError("PEER_CREDENTIALS_UNAVAILABLE")
    raw = conn.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, struct.calcsize("3i"))
    _pid, uid, _gid = struct.unpack("3i", raw)
    return uid


def _read_exact(conn: socket.socket, size: int, deadline: float) -> bytes:
    value = bytearray()
    while len(value) < size:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise ServerError("CLIENT_TIMEOUT")
        conn.settimeout(remaining)
        chunk = conn.recv(size - len(value))
        if not chunk:
            raise ServerError("TRUNCATED_FRAME")
        value.extend(chunk)
    return bytes(value)


def _reject_available_trailing_bytes(conn: socket.socket) -> None:
    old_timeout = conn.gettimeout()
    try:
        conn.setblocking(False)
        try:
            if conn.recv(1, socket.MSG_PEEK):
                raise ServerError("PIPELINED_REQUEST_FORBIDDEN")
        except BlockingIOError:
            pass
    finally:
        conn.settimeout(old_timeout)


def _response(value: dict) -> bytes:
    raw = rfc8785.dumps({"protocol": PROTOCOL, "schemaVersion": 1, "payload": value})
    if not 0 < len(raw) <= MAX_FRAME_BYTES:
        raise ServerError("RESPONSE_TOO_LARGE")
    return struct.pack(">I", len(raw)) + raw


def serve_connection(
    conn: socket.socket, broker: DevSyntheticBrokerCore, *, authorized_uid: int,
    peer_uid_reader: Callable[[socket.socket], int] = kernel_peer_uid,
    timeout: float = CONNECTION_TIMEOUT_SECONDS,
) -> None:
    """One frame, one result, close. Only the trusted server supplies peer reader."""
    try:
        peer_uid = peer_uid_reader(conn)
        if type(peer_uid) is not int or peer_uid != authorized_uid:
            raise ServerError("LOCAL_PEER_DENIED")
        deadline = time.monotonic() + timeout
        header = _read_exact(conn, 4, deadline)
        length = struct.unpack(">I", header)[0]
        if not 0 < length <= MAX_FRAME_BYTES:
            raise ServerError("INVALID_FRAME_LENGTH")
        frame = header + _read_exact(conn, length, deadline)
        _reject_available_trailing_bytes(conn)
        message = parse_frame(frame)
        if message.operation not in ALLOWED_IPC_OPERATIONS:
            raise ServerError("IPC_OPERATION_FORBIDDEN")
        result = broker.dispatch(message)
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise ServerError("CLIENT_TIMEOUT")
        conn.settimeout(remaining)
        conn.sendall(_response({"status": "OK", "result": result}))
    except (OSError, ProtocolError, ServerError, ValueError, TypeError):
        # No assertion, payload, or exception text is serialized. A failed
        # connection receives no authority observation and no second frame.
        pass
    finally:
        conn.close()


def inherited_listener() -> socket.socket:
    """Accept exactly one systemd listener FD; no fallback bind."""
    if os.environ.get("LISTEN_PID") != str(os.getpid()) or os.environ.get("LISTEN_FDS") != "1":
        raise ServerError("SYSTEMD_SOCKET_REQUIRED")
    listener = socket.socket(fileno=3)
    if listener.family != socket.AF_UNIX or listener.type & socket.SOCK_STREAM != socket.SOCK_STREAM or listener.getsockname() != SOCKET_PATH:
        listener.close()
        raise ServerError("UNEXPECTED_LISTENER")
    os.environ.pop("LISTEN_PID", None)
    os.environ.pop("LISTEN_FDS", None)
    return listener


def serve_forever(broker: DevSyntheticBrokerCore, *, authorized_uid: int) -> None:
    listener = inherited_listener()
    gate = threading.BoundedSemaphore(MAX_CLIENTS)
    with listener, ThreadPoolExecutor(max_workers=MAX_CLIENTS) as pool:
        while True:
            conn, _ = listener.accept()
            if not gate.acquire(blocking=False):
                conn.close()
                continue
            future = pool.submit(serve_connection, conn, broker, authorized_uid=authorized_uid)
            future.add_done_callback(lambda _finished: gate.release())


def main() -> None:
    """Operational entrypoint for a later, separately authorized DEV install."""
    import json
    import pwd  # Linux-only; deliberately not required to import the module in CI.

    if os.environ.get("LILITH_ENV") != "dev" or any(os.environ.get(key) for key in (
        "PYTHONPATH", "LILITH_COGNITIVE_DB_PATH", "LILITH_PRIVACY_DB_PATH",
        "LILITH_ACTOR_KEY_PATH", "LILITH_PRIVACY_KEY_PATH", "LILITH_CONTAINMENT_KEY_PATH",
    )):
        raise ServerError("DEV_ONLY_NO_LIVE_CUSTODY")
    config = DevConfig.from_file(Path("/etc/lilith-memory-broker/dev.json"))
    manifest_path = Path("/opt/lilith-memory-broker/current/release-manifest.json")
    if manifest_path.is_symlink() or not manifest_path.is_file():
        raise ServerError("RELEASE_MANIFEST_MISSING")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(manifest, dict) or manifest.get("candidateSha") != config.release_sha:
        raise ServerError("RELEASE_MANIFEST_MISMATCH")
    broker_uid = pwd.getpwnam("lilith-memory-broker").pw_uid
    relay_uid = pwd.getpwnam("lilith-memory-relay").pw_uid
    if broker_uid == relay_uid or broker_uid == pwd.getpwnam("lilith").pw_uid:
        raise ServerError("OS_IDENTITY_COLLISION")
    state = DevOwnerControlState(Path("/var/lib/lilith-memory-broker/owner-control/owner_control.db"), config, expected_uid=broker_uid)
    evidence = SyntheticEvidenceStore(Path("/var/lib/lilith-memory-broker/state/synthetic_evidence.db"), release_sha=config.release_sha, expected_uid=broker_uid)
    broker = DevSyntheticBrokerCore(
        config, state, evidence, hostname=socket.gethostname(),
        machine_id=Path("/etc/machine-id").read_text(encoding="ascii").strip(),
        release_sha=manifest["candidateSha"],
    )
    serve_forever(broker, authorized_uid=relay_uid)


if __name__ == "__main__":
    main()
