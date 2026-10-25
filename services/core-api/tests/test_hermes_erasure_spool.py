"""F9-C: the Core API spool client for the privileged Hermes erasure executor (unprivileged; temporary directories).

It queues only the Slice 2 request, never overwrites, never leaves a hard-linked or partial request, and accepts a
receipt only from the executor's uid, as a regular, bounded, non-writable-by-others file opened without following
links. The executor-side matrix (root, WSL) exercises it end to end against the real executor."""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path

from test_canonical_runtime import CanonicalRuntimeCase  # noqa: F401  (puts the Core API on sys.path)

from lilith_memory import hermes_erasure_owner as H
from lilith_memory import hermes_erasure_spool as S

REF, NONCE = "erase." + "a" * 32, "execution." + "b" * 32


@unittest.skipUnless(os.name == "posix", "POSIX file semantics")
class SpoolClientTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        self.spool, self.receipts = root / "spool", root / "receipts"
        self.spool.mkdir()
        self.receipts.mkdir()
        self.client = S.SpoolHermesErasureExecutor(self.spool, self.receipts, executor_uid=os.getuid())

    def test_submit_writes_exactly_the_request_once_per_attempt(self):
        for _ in range(2):
            self.client.submit(H.erasure_request(REF, NONCE))
        requests = sorted(self.spool.glob("*.req"))
        self.assertEqual(len(requests), 2)                                   # a retry queues a new request
        for request in requests:
            self.assertEqual(json.loads(request.read_text()), H.erasure_request(REF, NONCE))
            self.assertEqual(request.stat().st_nlink, 1)
            self.assertEqual(request.stat().st_mode & 0o777, 0o640)
        self.assertEqual(sorted(p.name for p in self.spool.iterdir() if not p.name.endswith(".req")), [])

    def test_submit_refuses_anything_but_the_contract(self):
        for bad in ({"v": 1}, {**H.erasure_request(REF, NONCE), "sessionIds": ["s"]},
                    {**H.erasure_request(REF, NONCE), "owner": "L04"}, H.erasure_request("../../etc/x", NONCE)):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                self.client.submit(bad)
        self.assertEqual(list(self.spool.iterdir()), [])

    def test_read_receipt_trust_rules(self):
        self.assertIsNone(self.client.read_receipt(REF))
        path = self.receipts / f"{REF}.receipt.json"
        path.write_text(json.dumps({"status": "COMPLETE"}))
        os.chmod(path, 0o640)
        self.assertEqual(self.client.read_receipt(REF), {"status": "COMPLETE"})
        os.chmod(path, 0o666)
        with self.assertRaises(PermissionError):                             # writable by others
            self.client.read_receipt(REF)
        os.chmod(path, 0o640)
        other = S.SpoolHermesErasureExecutor(self.spool, self.receipts, executor_uid=os.getuid() + 1)
        with self.assertRaises(PermissionError):                             # not the executor's file
            other.read_receipt(REF)
        path.unlink()
        target = self.receipts / "elsewhere.json"
        target.write_text("{}")
        path.symlink_to(target)
        with self.assertRaises(OSError):                                     # never follows a link
            self.client.read_receipt(REF)
        path.unlink()
        path.write_bytes(b"{" + b" " * (S.MAX_RECEIPT_BYTES + 1) + b"}")
        with self.assertRaises(PermissionError):                             # bounded size
            self.client.read_receipt(REF)
        for bad in ("../x", "erase.short", REF + "/../y"):
            with self.subTest(ref=bad), self.assertRaises(ValueError):
                self.client.read_receipt(bad)


if __name__ == "__main__":
    unittest.main()
