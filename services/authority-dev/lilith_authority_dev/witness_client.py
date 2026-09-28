"""The signer's client for the recovery witness signer socket (PR-1S, S-10).

`/run/lilith-recovery-witness/signer.sock` accepts only the signer uid and
only `READ_WITNESS` and `RECORD_LEDGER_ADVANCE` (B1b-3d §10). The client
sends one canonical frame and reads one response. It carries no key and no
witness body: the witness builds and signs its own successor.
"""

from __future__ import annotations

import socket
import struct
import time
from typing import Any, Mapping

from lilith_recovery_witness import protocol as WP

SIGNER_SOCKET = "/run/lilith-recovery-witness/signer.sock"
TIMEOUT_SECONDS = 5.0


def _exchange(frame: bytes, *, path: str = SIGNER_SOCKET, timeout: float = TIMEOUT_SECONDS) -> dict[str, Any]:
    deadline = time.monotonic() + timeout
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
        client.settimeout(timeout)
        client.connect(path)
        client.sendall(frame)
        header = b""
        while len(header) < 4:
            chunk = client.recv(4 - len(header))
            if not chunk:
                raise OSError("witness closed the connection")
            header += chunk
        length = struct.unpack(">I", header)[0]
        if not 0 < length <= WP.MAX_FRAME_BYTES:
            raise ValueError("invalid witness response length")
        body = b""
        while len(body) < length:
            if time.monotonic() > deadline:
                raise OSError("witness response timeout")
            chunk = client.recv(length - len(body))
            if not chunk:
                raise OSError("truncated witness response")
            body += chunk
    return WP.parse_response(header + body)


def record_ledger_advance(previous_witness_digest: str, ledger_sequence: int, ledger_head: str, *,
                          path: str = SIGNER_SOCKET) -> Mapping[str, Any]:
    return _exchange(WP.encode_frame(WP.RECORD_LEDGER_ADVANCE, {
        "previousWitnessDigest": previous_witness_digest, "ledgerSequence": ledger_sequence,
        "ledgerHead": ledger_head}), path=path)


def read_witness(*, path: str = SIGNER_SOCKET) -> Mapping[str, Any]:
    return _exchange(WP.encode_frame(WP.READ_WITNESS, {}), path=path)
