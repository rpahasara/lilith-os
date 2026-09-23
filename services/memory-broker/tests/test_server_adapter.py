"""Local socketpair protocol tests; never creates a host pathname socket."""

from __future__ import annotations

import socket
import struct
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT / "services" / "core-api"), str(ROOT / "services" / "memory-broker")]

from lilith_memory_broker import protocol, server


class StubBroker:
    def __init__(self):
        self.calls = []

    def dispatch(self, message):
        self.calls.append(message.operation)
        return {"status": "SYNTHETIC_ONLY"}


class ServerAdapterCase(unittest.TestCase):
    def exchange(self, data: bytes, *, peer: int = 1001, authorized: int = 1001, close_write: bool = False, timeout: float = 0.1):
        client, broker_side = socket.socketpair()
        self.addCleanup(client.close)
        stub = StubBroker()
        client.sendall(data)
        if close_write:
            client.shutdown(socket.SHUT_WR)
        server.serve_connection(broker_side, stub, authorized_uid=authorized, peer_uid_reader=lambda _sock: peer, timeout=timeout)
        client.settimeout(0.1)
        chunks = []
        while True:
            try:
                item = client.recv(1024)
            except (socket.timeout, ConnectionResetError):
                break
            if not item:
                break
            chunks.append(item)
        return b"".join(chunks), stub.calls

    def test_authorized_one_request_one_response(self):
        response, calls = self.exchange(protocol.encode_frame("HEALTH", {}))
        self.assertEqual(calls, ["HEALTH"])
        length = struct.unpack(">I", response[:4])[0]
        self.assertEqual(length, len(response) - 4)
        self.assertIn(b"SYNTHETIC_ONLY", response)

    def test_peer_identity_and_no_access_context(self):
        good = protocol.encode_frame("HEALTH", {})
        self.assertEqual(self.exchange(good, peer=1002)[1], [])
        self.assertEqual(self.exchange(good, peer="1001")[1], [])
        self.assertEqual(self.exchange(protocol.encode_frame("ACCESS_CONTEXT", {}))[1], [])
        forged = b'{"operation":"HEALTH","payload":{"uid":1001},"protocol":"LILITH_MEMORY_BROKER","schemaVersion":1}'
        self.assertEqual(self.exchange(struct.pack(">I", len(forged)) + forged)[1], [])

    def test_bad_frames_never_dispatch(self):
        good = protocol.encode_frame("HEALTH", {})
        for data in (
            b"", b"\x00\x00", struct.pack(">I", 0), struct.pack(">I", 16385),
            good[:-1], good + good, struct.pack(">I", 2) + b"{}",
            struct.pack(">I", 4) + b"nope",
        ):
            with self.subTest(data=data[:10]):
                self.assertEqual(self.exchange(data, close_write=True)[1], [])

    def test_timeout_and_response_limit(self):
        self.assertEqual(self.exchange(b"", timeout=0.01)[1], [])
        with self.assertRaises(server.ServerError):
            server._response({"large": "x" * 20000})

    def test_requires_inherited_systemd_fd(self):
        with self.assertRaises(server.ServerError):
            server.inherited_listener()


if __name__ == "__main__":
    unittest.main()
