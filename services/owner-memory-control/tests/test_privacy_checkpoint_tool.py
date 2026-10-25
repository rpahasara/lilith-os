"""Track B owner-device K-PCK tool: keygen custody, extension-only checkpoints with fork alarms, and boot unlocks
that are signed only when the tool's own comparison is FRESH. The host side is the real Core API
``privacy_freshness`` step over a TEST_ONLY simulated witness. Temporary directories only."""

from __future__ import annotations

import json
import os
import secrets
import sqlite3
import tempfile
import unittest
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

import synthetic_authority  # noqa: F401  (puts services/core-api and owner-memory-control on sys.path)
import sys

TOOLS = Path(__file__).resolve().parents[1] / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import privacy_checkpoint_tool as T  # noqa: E402
from lilith_memory import privacy_anchor_contracts as A  # noqa: E402
from lilith_memory import privacy_freshness as F  # noqa: E402

ENV = "DEV_SYNTHETIC"
KPAN_ID = "kpan.test-only.dev-synthetic.01"
KPCK_ID = "kpck.test-only.dev-synthetic.01"


def stamp(n: int) -> str:
    return f"2026-10-25T11:{n // 60:02d}:{n % 60:02d}.000000Z"


class ToolTests(unittest.TestCase):
    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.custody = self.root / "owner-kpck"
        self.privacy_db = self.root / "privacy.db"
        conn = sqlite3.connect(self.privacy_db)
        conn.execute("CREATE TABLE privacy_restore_suppression_manifest (suppression_ref_id TEXT PRIMARY KEY, "
                     "identity_selector TEXT NOT NULL)")
        conn.commit()
        conn.close()
        self.kpan = Ed25519PrivateKey.generate()               # TEST_ONLY simulated witness key
        self.anchor_pin = self.root / "kpan.pin.json"
        self.anchor_pin.write_text(json.dumps(T.public_pin(self.kpan.public_key(), environment=ENV, key_id=KPAN_ID,
                                                           family="K-PAN")))
        self.anchors = []
        self.t = 0
        self.result = T.keygen(self.custody, environment=ENV, key_id=KPCK_ID)

    def now(self) -> str:
        self.t += 1
        return stamp(self.t)

    def suppress(self, n: int) -> None:
        conn = sqlite3.connect(self.privacy_db)
        conn.execute("INSERT INTO privacy_restore_suppression_manifest VALUES (?, ?)",
                     (f"suppress.{n:032x}", f"{n:064x}"))
        conn.commit()
        conn.close()

    def advance(self) -> Path:
        chain = A.verify_anchor_chain(self.anchors, self.kpan.public_key(), environment=ENV, key_id=KPAN_ID) \
            if self.anchors else None
        local = set(F.local_suppression_entries(self.privacy_db))
        body = A.unsigned_anchor_advance(chain, sorted(local - (chain.entries if chain else set())),
                                         environment=ENV, updated_at=self.now(), key_id=KPAN_ID)
        self.anchors.append({**body, "signature": self.kpan.sign(A.signing_bytes("anchor", body)).hex()})
        return self.write_chain(self.anchors)

    def write_chain(self, docs) -> Path:
        path = self.root / f"anchor-chain-{secrets.token_hex(4)}.json"
        path.write_text(json.dumps(docs))
        return path

    def keys(self):
        pin, _ = T.load_pin(self.custody / T.PIN_FILE, family="K-PCK", prefix=A.KPCK_KEY_PREFIX)
        return F.FreshnessKeys(ENV, self.kpan.public_key(), KPAN_ID, pin, KPCK_ID)

    def test_keygen_creates_private_custody_and_refuses_reuse_or_other_families(self):
        self.assertEqual(self.result["status"], "KPCK_GENERATED")
        if os.name == "posix":
            self.assertEqual(os.stat(self.custody).st_mode & 0o777, 0o700)
            self.assertEqual(os.stat(self.custody / T.KEY_FILE).st_mode & 0o777, 0o600)
        self.assertEqual(len((self.custody / T.KEY_FILE).read_bytes()), 32)
        self.assertEqual(self.result["pin"]["family"], "K-PCK")
        self.assertNotIn((self.custody / T.KEY_FILE).read_bytes().hex(), json.dumps(self.result))
        with self.assertRaises(T.ToolRefusal):
            T.keygen(self.custody, environment=ENV, key_id=KPCK_ID)
        with self.assertRaises(T.ToolRefusal):
            T.keygen(self.root / "other", environment=ENV, key_id="kroot.dev-synthetic.01")

    def test_checkpoints_extend_only_and_a_rolled_back_host_raises_a_fork_alarm(self):
        chain1 = self.advance()
        first = T.checkpoint(self.custody, anchor_chain=chain1, anchor_pin=self.anchor_pin, at=self.now())
        self.suppress(1)
        chain2 = self.advance()
        T.checkpoint(self.custody, anchor_chain=chain2, anchor_pin=self.anchor_pin, at=self.now())
        self.assertEqual(T.show(self.custody)["checkpoints"], 2)
        # a host presenting its OLD chain (rolled back) cannot obtain a checkpoint: fork alarm recorded
        with self.assertRaises(T.ToolRefusal) as c:
            T.checkpoint(self.custody, anchor_chain=chain1, anchor_pin=self.anchor_pin, at=self.now())
        self.assertEqual(c.exception.code, "CHECKPOINT_FORK_ALARM")
        self.assertEqual(T.show(self.custody)["alarms"], 1)
        self.assertEqual(first["checkpointSeq"], 1)

    def test_a_forked_host_chain_is_refused(self):
        T.checkpoint(self.custody, anchor_chain=self.advance(), anchor_pin=self.anchor_pin, at=self.now())
        self.suppress(1)
        T.checkpoint(self.custody, anchor_chain=self.advance(), anchor_pin=self.anchor_pin, at=self.now())
        fork = list(self.anchors[:1])
        chain1 = A.verify_anchor_chain(fork, self.kpan.public_key(), environment=ENV, key_id=KPAN_ID)
        body = A.unsigned_anchor_advance(chain1, [(f"suppress.{9:032x}", f"{9:064x}"), (f"suppress.{8:032x}",
                                                  f"{8:064x}")], environment=ENV, updated_at=self.now(),
                                         key_id=KPAN_ID)
        fork.append({**body, "signature": self.kpan.sign(A.signing_bytes("anchor", body)).hex()})
        with self.assertRaises(T.ToolRefusal):
            T.checkpoint(self.custody, anchor_chain=self.write_chain(fork), anchor_pin=self.anchor_pin, at=self.now())

    def test_unlock_end_to_end_with_the_real_host_step(self):
        chain = self.advance()
        T.checkpoint(self.custody, anchor_chain=chain, anchor_pin=self.anchor_pin, at=self.now())
        boot, nonce = "boot-" + secrets.token_hex(6), secrets.token_hex(32)
        challenge = F.issue_challenge(self.keys(), self.anchors, self.privacy_db, boot_id=boot, nonce=nonce,
                                      issued_at=self.now())
        cpath = self.root / "challenge.json"
        cpath.write_text(json.dumps(challenge))
        unlock = T.unlock(self.custody, challenge=cpath, anchor_chain=chain, anchor_pin=self.anchor_pin,
                          at=self.now())
        marker_path = self.root / "run" / "verified"
        marker = F.apply_unlock(self.keys(), self.anchors, self.privacy_db, challenge, unlock,
                                T.Custody(self.custody).latest(), boot_id=boot, nonce=nonce,
                                verified_at=self.now(), marker_path=marker_path)
        self.assertEqual(marker["anchorVersion"], 1)
        gate = F.PrivacyFreshnessGate(self.privacy_db, environment=ENV, marker_path=marker_path,
                                      intent_dir=self.root / "intent", boot_id=lambda: boot,
                                      require_root_marker=False)
        self.assertTrue(gate.check().ready)

    def test_unlock_is_refused_for_a_host_behind_the_latest_checkpoint(self):
        chain1 = self.advance()
        T.checkpoint(self.custody, anchor_chain=chain1, anchor_pin=self.anchor_pin, at=self.now())
        self.suppress(1)
        T.checkpoint(self.custody, anchor_chain=self.advance(), anchor_pin=self.anchor_pin, at=self.now())
        old = self.anchors[:1]
        old_chain = A.verify_anchor_chain(old, self.kpan.public_key(), environment=ENV, key_id=KPAN_ID)
        challenge = A.make_challenge(old_chain, environment=ENV, boot_id="boot-x", nonce="3" * 64,
                                     issued_at=self.now())
        cpath = self.root / "challenge-old.json"
        cpath.write_text(json.dumps(challenge))
        with self.assertRaises(T.ToolRefusal) as c:
            T.unlock(self.custody, challenge=cpath, anchor_chain=chain1, anchor_pin=self.anchor_pin, at=self.now())
        self.assertEqual(c.exception.code, "UNLOCK_REFUSED:" + A.OLDER_THAN_CHECKPOINT)

    def test_a_wrong_family_pin_or_tampered_key_file_is_refused(self):
        bad_pin = self.root / "bad.pin.json"
        bad_pin.write_text(json.dumps(T.public_pin(self.kpan.public_key(), environment=ENV, key_id=KPCK_ID,
                                                   family="K-PCK")))
        chain = self.advance()
        with self.assertRaises(T.ToolRefusal):
            T.checkpoint(self.custody, anchor_chain=chain, anchor_pin=bad_pin, at=self.now())
        (self.custody / T.KEY_FILE).chmod(0o600)
        os.replace(self.custody / T.KEY_FILE, self.custody / "moved")
        (self.custody / T.KEY_FILE).write_bytes(Ed25519PrivateKey.generate().private_bytes_raw())
        if os.name == "posix":
            os.chmod(self.custody / T.KEY_FILE, 0o600)
        with self.assertRaises(T.ToolRefusal) as c:
            T.checkpoint(self.custody, anchor_chain=chain, anchor_pin=self.anchor_pin, at=self.now())
        self.assertEqual(c.exception.code, "KEY_PIN_MISMATCH")


if __name__ == "__main__":
    unittest.main()
