"""Track B B3: the K-PAN ceremony (`tools/trackb_kpan_keygen.py`) over a temporary host tree with a stand-in encryptor.
Nothing runs on a host; no real key leaves the temporary directory."""

from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
TOOLS = ROOT / "services/owner-memory-control/tools"
for _p in (TOOLS, ROOT / "services/core-api"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import privacy_checkpoint_tool as PCT  # noqa: E402
import trackb_kpan_keygen as K  # noqa: E402
from lilith_memory import privacy_anchor_contracts as A  # noqa: E402

POSIX = os.name == "posix"


@unittest.skipUnless(POSIX, "dir-fd O_EXCL and owner/mode semantics are POSIX")
class KeygenTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.host = self.make_host()

    def make_host(self, encrypt=None):
        def fake_encrypt(der: bytes) -> bytes:
            self.der = der
            return b"TEST ciphertext " + der[-8:]
        return K.Host(root=self.root, owner_uid=os.getuid(), owner_gid=os.getgid(), encrypt=encrypt or fake_encrypt)

    def p(self, absolute):
        return self.root / absolute.lstrip("/")

    def build(self):
        for path, mode, data in (("/etc/machine-id", 0o644, K.DEV_MACHINE_ID + "\n"),
                                 # simulated, rewritten by the swap cases below; keygen reads it and never checks its mode
                                 ("/proc/swaps", 0o644, "Filename Type Size Used Priority\n"),
                                 (K.HOST_KEY, 0o400, "k"), (K.SYSTEMD_CREDS, 0o755, "#!")):
            self.p(path).parent.mkdir(parents=True, exist_ok=True)
            self.p(path).write_text(data)
            os.chmod(self.p(path), mode)
        self.p(K.CREDENTIAL_DIR).mkdir(parents=True)
        os.chmod(self.p(K.WITNESS_PARENT), 0o700)
        os.chmod(self.p(K.CREDENTIAL_DIR), 0o700)
        kwit = self.p(K.CREDENTIAL_DIR + "/" + K.KWIT_BLOB_NAME)
        kwit.write_bytes(b"KWIT ciphertext")
        os.chmod(kwit, 0o600)

    def run_keygen(self, **kw):
        args = {"euid": 0, "isolated": True, "hostname": "lilith-dev-01"} | kw
        return K.keygen(self.host, **args)

    def test_one_run_writes_one_blob_and_prints_only_the_public_pin(self):
        self.build()
        out = self.run_keygen()
        blob = self.p(K.KPAN_BLOB_PATH)
        self.assertEqual(os.stat(blob).st_mode & 0o777, 0o600)
        self.assertEqual(out["custodyEvidence"]["blobSha256"], K.blob_facts(blob).sha256)
        self.assertEqual(out["pin"]["keyId"], "kpan.dev-synthetic.01")
        text = json.dumps(out)
        self.assertNotIn(self.der.hex(), text)                                # no private material in the output
        self.assertEqual(sorted(os.listdir(self.p(K.CREDENTIAL_DIR))), [K.KPAN_BLOB_NAME, K.KWIT_BLOB_NAME])
        pin_file = self.root / "kpan.pin.json"
        pin_file.write_text(json.dumps(out["pin"]))
        key, pin = PCT.load_pin(pin_file, family="K-PAN", prefix=A.KPAN_KEY_PREFIX)   # the owner tool reads it
        self.assertEqual(pin["keyId"], K.KEY_ID)
        self.assertEqual(K.ENCRYPT_ARGV, ("/usr/bin/systemd-creds", "encrypt", "--with-key=host",
                                          "--name=privacy-anchor-signing-key", "-", "-"))

    def test_preconditions_refuse_before_anything_is_generated(self):
        self.build()
        cases = {"NOT_ROOT": {"euid": 1000}, "INTERPRETER_NOT_ISOLATED": {"isolated": False},
                 "NOT_DEV_HOST": {"hostname": "lilith-01"}}
        for reason, kw in cases.items():
            with self.subTest(reason=reason), self.assertRaises(K.Refused) as caught:
                self.run_keygen(**kw)
            self.assertEqual(caught.exception.reason, reason)
        self.p("/proc/swaps").write_text("Filename Type\n/swapfile file 1 0 -2\n")
        with self.assertRaises(K.Refused) as caught:
            self.run_keygen()
        self.assertEqual(caught.exception.reason, "SWAP_ACTIVE")
        self.p("/proc/swaps").write_text("Filename Type\n")
        (self.p(K.CREDENTIAL_DIR) / "extra").write_bytes(b"")
        with self.assertRaises(K.Refused) as caught:
            self.run_keygen()
        self.assertEqual(caught.exception.reason, "CREDENTIAL_DIR_NOT_EXACTLY_KWIT")
        os.unlink(self.p(K.CREDENTIAL_DIR) / "extra")
        os.chmod(self.p(K.CREDENTIAL_DIR), 0o750)
        with self.assertRaises(K.Refused) as caught:
            self.run_keygen()
        self.assertEqual(caught.exception.reason, "CREDENTIAL_DIR_CUSTODY")
        os.chmod(self.p(K.CREDENTIAL_DIR), 0o700)
        self.assertFalse(hasattr(self, "der"))                                # nothing was generated

    def test_one_time_and_kwit_must_not_change(self):
        self.build()
        self.run_keygen()
        with self.assertRaises(K.Refused) as caught:
            self.run_keygen()
        self.assertEqual(caught.exception.reason, "KPAN_ALREADY_PRESENT")
        os.unlink(self.p(K.KPAN_BLOB_PATH))

        def tamper(der):
            kwit = self.p(K.CREDENTIAL_DIR + "/" + K.KWIT_BLOB_NAME)
            kwit.write_bytes(b"KWIT ciphertext changed")
            return b"TEST ciphertext"
        self.host = self.make_host(tamper)
        with self.assertRaises(K.Failed) as caught:
            self.run_keygen()
        self.assertEqual(caught.exception.reason, "KWIT_CHANGED")

    def test_encryption_failure_writes_nothing(self):
        self.build()

        def broken(_der):
            raise K.Failed("ENCRYPT_FAILED")
        self.host = self.make_host(broken)
        with self.assertRaises(K.Failed):
            self.run_keygen()
        self.assertFalse(self.p(K.KPAN_BLOB_PATH).exists())


class StaticTests(unittest.TestCase):
    def test_closed_form_and_no_release_or_signer_reach(self):
        source = (TOOLS / "trackb_kpan_keygen.py").read_text(encoding="utf-8")
        for needle in ("lilith_authority_signer", "credstore.encrypted/", "from_private_bytes", "argparse",
                       "socket.socket(", "urllib", "requests"):
            self.assertNotIn(needle, source)
        self.assertEqual(K.main(["keygen", "--force"]), K.EXIT_REFUSED)
        self.assertEqual(K.main([]), K.EXIT_REFUSED)


if __name__ == "__main__":
    unittest.main()
