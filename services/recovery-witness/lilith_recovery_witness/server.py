"""Inherited-AF_UNIX-only recovery-witness adapter and entrypoint (PR-1S).

The adapter never binds a socket. It accepts exactly the two listener FDs
systemd passes (`LISTEN_FDNAMES=owner:signer`, from
`lilith-recovery-witness-owner.socket` and `-signer.socket`) and serves:

- `owner.sock`: only a kernel `SO_PEERCRED` uid of 0 (host root; uid 0 is
  host-root execution, not human-owner authentication);
- `signer.sock`: only the uid of `lilith-authority-dev`.

One request per connection, one instance, served sequentially: the store
lock is the single-writer boundary and requests never interleave.

`main()` refuses to start unless it runs as `lilith-recovery-witness` (never
root; no supplementary group; no uid or gid shared with any other LILITH
principal), in `LILITH_ENV=dev`, with no other `LILITH_*` variable and no
`PYTHONPATH`, with exactly its one systemd credential. Before serving it
runs only the Prep A recovery scan. It never auto-bootstraps: an
UNINITIALIZED store stays UNINITIALIZED until an owner `BOOTSTRAP`.
Installing the unit files and starting the service create no transition.
"""

from __future__ import annotations

import os
import selectors
import socket
import struct
import sys
import time
from datetime import datetime, timezone
from typing import Callable

from lilith_authority_host import inputs as HI

from . import protocol as W
from .core import RecoveryWitnessCoreV1, authority_public_keys
from .credential import CREDENTIAL_ABSENT, WitnessCredentialError, load_witness_signing_key
from .profile import (DISTINCT_PRINCIPALS, ENVIRONMENT, OWNER_SOCKET_PATH, SERVICE_GROUP, SERVICE_USER,
                      SIGNER_PEER_USER, SIGNER_SOCKET_PATH, STATE_DIR)
from .storage import FilesystemWitnessStorageV1
from .writer import DevSyntheticWitnessWriterV1, recover

CONNECTION_TIMEOUT_SECONDS = 3.0
ALLOWED_ENVIRONMENT = frozenset({"LILITH_ENV"})
LISTENER_NAMES = ("owner", "signer")
ROLE_BY_NAME = {"owner": W.OWNER, "signer": W.SIGNER}
PATH_BY_NAME = {"owner": OWNER_SOCKET_PATH, "signer": SIGNER_SOCKET_PATH}

EXIT_STARTUP_REFUSED = 2
EXIT_CREDENTIAL_ABSENT = 3
EXIT_CREDENTIAL_INVALID = 4
EXIT_STORE_FAIL_CLOSED = 5


class ServerError(RuntimeError):
    pass


def kernel_peer_uid(conn: socket.socket) -> int:
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


def serve_connection(conn: socket.socket, core: RecoveryWitnessCoreV1, *, role: str, authorized_uid: int,
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
        result = core.dispatch(role, W.parse_frame(frame, role=role))
        conn.settimeout(max(deadline - time.monotonic(), 0.1))
        conn.sendall(W.encode_response(result))
    except (OSError, W.ProtocolError, ServerError, ValueError, TypeError):
        pass  # no request, payload, or exception text is serialized back
    finally:
        conn.close()


def inherited_listeners() -> dict[str, socket.socket]:
    """Exactly the two named systemd listeners; no fallback bind."""
    if os.environ.get("LISTEN_PID") != str(os.getpid()) or os.environ.get("LISTEN_FDS") != "2":
        raise ServerError("SYSTEMD_SOCKETS_REQUIRED")
    names = os.environ.get("LISTEN_FDNAMES", "").split(":")
    if sorted(names) != sorted(LISTENER_NAMES):
        raise ServerError("UNEXPECTED_LISTENER_NAMES")
    listeners: dict[str, socket.socket] = {}
    for index, name in enumerate(names):
        listener = socket.socket(fileno=3 + index)
        if listener.family != socket.AF_UNIX or listener.type & socket.SOCK_STREAM != socket.SOCK_STREAM \
                or listener.getsockname() != PATH_BY_NAME[name]:
            listener.close()
            raise ServerError("UNEXPECTED_LISTENER")
        listeners[name] = listener
    for key in ("LISTEN_PID", "LISTEN_FDS", "LISTEN_FDNAMES"):
        os.environ.pop(key, None)
    return listeners


def serve_forever(core: RecoveryWitnessCoreV1, listeners: dict[str, socket.socket], *, signer_uid: int) -> None:
    selector = selectors.DefaultSelector()
    uids = {"owner": 0, "signer": signer_uid}
    for name, listener in listeners.items():
        selector.register(listener, selectors.EVENT_READ, name)
    while True:
        for key, _ in selector.select():
            conn, _ = key.fileobj.accept()
            serve_connection(conn, core, role=ROLE_BY_NAME[key.data], authorized_uid=uids[key.data])


def check_environment(environ: dict[str, str]) -> None:
    if environ.get("LILITH_ENV") != ENVIRONMENT:
        raise ServerError("DEV_ONLY")
    if environ.get("PYTHONPATH"):
        raise ServerError("PYTHONPATH_FORBIDDEN")
    extra = sorted(key for key in environ if key.startswith("LILITH_") and key not in ALLOWED_ENVIRONMENT)
    if extra:
        raise ServerError("LILITH_ENVIRONMENT_FORBIDDEN")


def check_identity(uid: int, gid: int, groups: list[int], *, user_lookup: Callable[[str], tuple[int, int] | None],
                   group_lookup: Callable[[str], int | None]) -> int:
    """Run only as the dedicated witness identity. Returns the signer uid."""
    own, own_group = user_lookup(SERVICE_USER), group_lookup(SERVICE_GROUP)
    if own is None or own_group is None:
        raise ServerError("SERVICE_IDENTITY_MISSING")
    if uid == 0 or (uid, gid) != own or gid != own_group:
        raise ServerError("SERVICE_IDENTITY_MISMATCH")
    if set(groups) - {gid}:
        raise ServerError("SUPPLEMENTARY_GROUPS_FORBIDDEN")
    for name in DISTINCT_PRINCIPALS:
        other = user_lookup(name)
        if other is not None and (other[0] == uid or other[1] == gid):
            raise ServerError("OS_IDENTITY_COLLISION")
    signer = user_lookup(SIGNER_PEER_USER)
    if signer is None or signer[0] in (0, uid):
        raise ServerError("SIGNER_PEER_IDENTITY_INVALID")
    return signer[0]


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _user(name: str) -> tuple[int, int] | None:
    import pwd

    try:
        entry = pwd.getpwnam(name)
    except KeyError:
        return None
    return (entry.pw_uid, entry.pw_gid)


def _group(name: str) -> int | None:
    import grp

    try:
        return grp.getgrnam(name).gr_gid
    except KeyError:
        return None


def build_core(signing_key, *, state_dir: str = STATE_DIR, read_inputs=None, clock=utc_now) -> RecoveryWitnessCoreV1:
    storage = FilesystemWitnessStorageV1(state_dir)
    writer = DevSyntheticWitnessWriterV1(signing_key=signing_key, storage=storage)
    reader = read_inputs or (lambda: HI.read_host_inputs(environment=ENVIRONMENT))
    return RecoveryWitnessCoreV1(writer=writer, storage=storage, inputs=reader, clock=clock)


def startup_recovery(core: RecoveryWitnessCoreV1, storage: FilesystemWitnessStorageV1, inputs: HI.HostInputsV1):
    """Prep A recovery at start. UNINITIALIZED is left alone (no auto-bootstrap);
    every non-automatic classification fails the start closed."""
    if inputs.registry_root is None or inputs.witness_anchor is None:
        return None
    return recover(storage, context=inputs.store_context(authority_public_keys=authority_public_keys(inputs)))


def main() -> int:
    try:
        check_environment(dict(os.environ))
        signer_uid = check_identity(os.getuid(), os.getgid(), os.getgroups(), user_lookup=_user, group_lookup=_group)
    except ServerError as exc:
        print(f"lilith-recovery-witness: STARTUP_REFUSED {exc}", file=sys.stderr)
        return EXIT_STARTUP_REFUSED
    try:
        key = load_witness_signing_key(os.environ.get("CREDENTIALS_DIRECTORY"))
    except WitnessCredentialError as exc:
        print(f"lilith-recovery-witness: {exc.state}", file=sys.stderr)
        return EXIT_CREDENTIAL_ABSENT if exc.state == CREDENTIAL_ABSENT else EXIT_CREDENTIAL_INVALID
    core = build_core(key)
    storage = core._storage
    run = startup_recovery(core, storage, HI.read_host_inputs(environment=ENVIRONMENT))
    if run is not None and run.after.fail_closed:
        print(f"lilith-recovery-witness: STORE_FAIL_CLOSED {run.after.classification}", file=sys.stderr)
        return EXIT_STORE_FAIL_CLOSED
    try:
        serve_forever(core, inherited_listeners(), signer_uid=signer_uid)
    except ServerError as exc:
        print(f"lilith-recovery-witness: STARTUP_REFUSED {exc}", file=sys.stderr)
        return EXIT_STARTUP_REFUSED
    return 0


if __name__ == "__main__":
    sys.exit(main())
