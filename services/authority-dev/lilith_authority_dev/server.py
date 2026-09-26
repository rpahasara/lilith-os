"""Inherited-AF_UNIX-only authority owner-socket adapter (B1b-3d L1).

The adapter never binds a socket. It accepts exactly one listener FD from
`lilith-authority-dev.socket` (`/run/lilith-authority-dev/owner.sock`,
`root:root 0600` in a `root:root 0700` directory, design §15), and it serves
only a kernel `SO_PEERCRED` uid of 0: the authority owner socket is root-only
(design §8). There is no application-facing, broker-facing, or network
listener.

`main()` is the operational entrypoint for a later, separately authorized
DEV install. It refuses to start unless it runs as `lilith-authority-dev`
(never root, never sharing a uid with another LILITH principal, no
supplementary groups), in `LILITH_ENV=dev`, with no other `LILITH_*`
variable and no `PYTHONPATH`. It never reads a key from the environment.

A missing credential exits with `EXIT_CREDENTIAL_ABSENT` before any socket is
served; an unusable one exits with `EXIT_CREDENTIAL_INVALID`. In a live unit,
systemd itself fails the start earlier when the encrypted blob is missing
(design §18). Neither is a signer failure.
"""

from __future__ import annotations

import os
import socket
import struct
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Callable

from . import protocol as W
from .core import DevAuthoritySignerCoreV1
from .credential import CREDENTIAL_ABSENT, CREDENTIAL_INVALID, inspect_owner_actor_credential
from .profile import DISTINCT_PRINCIPALS, OWNER_SOCKET_PATH, SERVICE_GROUP, SERVICE_USER

AUTHORIZED_PEER_UID = 0
CONNECTION_TIMEOUT_SECONDS = 3.0
MAX_CLIENTS = 4
ALLOWED_ENVIRONMENT = frozenset({"LILITH_ENV"})

EXIT_STARTUP_REFUSED = 2
EXIT_CREDENTIAL_ABSENT = 3
EXIT_CREDENTIAL_INVALID = 4


class ServerError(RuntimeError):
    pass


def kernel_peer_uid(conn: socket.socket) -> int:
    """Linux SO_PEERCRED is the only operational source of local peer uid."""
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


def serve_connection(conn: socket.socket, core: DevAuthoritySignerCoreV1, *,
                     authorized_uid: int = AUTHORIZED_PEER_UID,
                     peer_uid_reader: Callable[[socket.socket], int] = kernel_peer_uid,
                     timeout: float = CONNECTION_TIMEOUT_SECONDS) -> None:
    """One frame, one result, close. A denied or malformed peer gets nothing."""
    try:
        peer_uid = peer_uid_reader(conn)
        if type(peer_uid) is not int or peer_uid != authorized_uid:
            raise ServerError("LOCAL_PEER_DENIED")
        deadline = time.monotonic() + timeout
        header = _read_exact(conn, 4, deadline)
        length = struct.unpack(">I", header)[0]
        if not 0 < length <= W.MAX_FRAME_BYTES:
            raise ServerError("INVALID_FRAME_LENGTH")
        frame = header + _read_exact(conn, length, deadline)
        _reject_available_trailing_bytes(conn)
        result = core.dispatch(W.parse_frame(frame))
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise ServerError("CLIENT_TIMEOUT")
        conn.settimeout(remaining)
        conn.sendall(W.encode_response(result))
    except (OSError, W.ProtocolError, ServerError, ValueError, TypeError):
        # No request, payload, or exception text is serialized back.
        pass
    finally:
        conn.close()


def inherited_listener() -> socket.socket:
    """Accept exactly one systemd listener FD; no fallback bind."""
    if os.environ.get("LISTEN_PID") != str(os.getpid()) or os.environ.get("LISTEN_FDS") != "1":
        raise ServerError("SYSTEMD_SOCKET_REQUIRED")
    listener = socket.socket(fileno=3)
    if listener.family != socket.AF_UNIX or listener.type & socket.SOCK_STREAM != socket.SOCK_STREAM \
            or listener.getsockname() != OWNER_SOCKET_PATH:
        listener.close()
        raise ServerError("UNEXPECTED_LISTENER")
    for key in ("LISTEN_PID", "LISTEN_FDS", "LISTEN_FDNAMES"):
        os.environ.pop(key, None)
    return listener


def serve_forever(core: DevAuthoritySignerCoreV1) -> None:
    listener = inherited_listener()
    gate = threading.BoundedSemaphore(MAX_CLIENTS)
    with listener, ThreadPoolExecutor(max_workers=MAX_CLIENTS) as pool:
        while True:
            conn, _ = listener.accept()
            if not gate.acquire(blocking=False):
                conn.close()
                continue
            future = pool.submit(serve_connection, conn, core)
            future.add_done_callback(lambda _finished: gate.release())


def check_environment(environ: dict[str, str]) -> None:
    if environ.get("LILITH_ENV") != "dev":
        raise ServerError("DEV_ONLY")
    if environ.get("PYTHONPATH"):
        raise ServerError("PYTHONPATH_FORBIDDEN")
    extra = sorted(key for key in environ if key.startswith("LILITH_") and key not in ALLOWED_ENVIRONMENT)
    if extra:
        # No key, key path, DB path, or custody hint is accepted from the environment.
        raise ServerError("LILITH_ENVIRONMENT_FORBIDDEN")


def check_identity(uid: int, gid: int, groups: list[int], *,
                   user_lookup: Callable[[str], tuple[int, int] | None],
                   group_lookup: Callable[[str], int | None]) -> None:
    """Run only as the dedicated signer identity, with no extra group."""
    own = user_lookup(SERVICE_USER)
    own_group = group_lookup(SERVICE_GROUP)
    if own is None or own_group is None:
        raise ServerError("SERVICE_IDENTITY_MISSING")
    if uid == 0 or (uid, gid) != own or gid != own_group:
        raise ServerError("SERVICE_IDENTITY_MISMATCH")
    if set(groups) - {gid}:
        raise ServerError("SUPPLEMENTARY_GROUPS_FORBIDDEN")
    for name in DISTINCT_PRINCIPALS:
        other = user_lookup(name)
        if other is not None and other[0] == uid:
            raise ServerError("OS_IDENTITY_COLLISION")


def _user(name: str) -> tuple[int, int] | None:
    import pwd  # Linux-only; deliberately not required to import the module in CI.

    try:
        entry = pwd.getpwnam(name)
    except KeyError:
        return None
    return (entry.pw_uid, entry.pw_gid)


def _group(name: str) -> int | None:
    import grp  # Linux-only.

    try:
        return grp.getgrnam(name).gr_gid
    except KeyError:
        return None


def _process_identity() -> tuple[int, int, list[int]]:
    return os.getuid(), os.getgid(), os.getgroups()  # Linux-only


def main() -> int:
    """Operational entrypoint for a later, separately authorized DEV install."""
    try:
        check_environment(dict(os.environ))
        uid, gid, groups = _process_identity()
        check_identity(uid, gid, groups, user_lookup=_user, group_lookup=_group)
    except ServerError as exc:
        print(f"lilith-authority-dev: STARTUP_REFUSED {exc}", file=sys.stderr)
        return EXIT_STARTUP_REFUSED
    credential = inspect_owner_actor_credential(os.environ.get("CREDENTIALS_DIRECTORY"))
    if credential.state == CREDENTIAL_ABSENT:
        print("lilith-authority-dev: CREDENTIAL_ABSENT", file=sys.stderr)
        return EXIT_CREDENTIAL_ABSENT
    if credential.state == CREDENTIAL_INVALID:
        print("lilith-authority-dev: CREDENTIAL_INVALID", file=sys.stderr)
        return EXIT_CREDENTIAL_INVALID
    try:
        serve_forever(DevAuthoritySignerCoreV1(credential))
    except ServerError as exc:
        print(f"lilith-authority-dev: STARTUP_REFUSED {exc}", file=sys.stderr)
        return EXIT_STARTUP_REFUSED
    return 0


if __name__ == "__main__":
    sys.exit(main())
