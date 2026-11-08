"""P3 contract: the OWNER_PROD DEV transition delta is exactly the git bytes of d82f7da against this source (offline)."""

import hashlib
import subprocess
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
for _p in (ROOT / "services/owner-memory-control/tools", ROOT / "services/authority-dev", HERE):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import owner_prod_signer_upgrade as C  # noqa: E402
import release_file_set as RFS  # noqa: E402
import e23_installed as H  # noqa: E402


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class ContractTests(unittest.TestCase):
    def test_new_is_the_attested_merge_build_and_ready(self):
        self.assertEqual(C.NEW_RELEASE, "88a1168bd41797109772ffce7df7352c1ae40e4c")
        self.assertEqual(C.NEW_MANIFEST_SHA256, "072001af671feca6564906d3d685f89bfc608f9d595aed58bae0f72a25777684")
        self.assertEqual(C.NEW_RELEASE_ATTESTATION["archiveSha256"],
                         "53ae457b8b907e12282ed468da0387620b7a376a46ab1c450709b67540b43c07")
        self.assertTrue(C.ready_to_transition())
        self.assertEqual(C.OLD_RELEASE, "d82f7dac669f37c494beebf9bbb99dffdb6c23f5")
        self.assertNotEqual(C.NEW_RELEASE_ATTESTATION["archiveSha256"], C.REHEARSAL["archiveSha256"])
        # NEW's payload is the rehearsal's: only the release manifest (it names the candidate) differs.
        self.assertEqual(C.NEW_RELEASE_ATTESTATION["archiveByteSize"], C.REHEARSAL["archiveByteSize"] + 1)

    def test_the_pinned_new_is_main_history_and_its_runtime_equals_this_tree(self):
        merged = subprocess.run(["git", "-C", str(ROOT), "merge-base", "--is-ancestor", C.NEW_RELEASE, "HEAD"])
        if merged.returncode == 128:
            self.skipTest("shallow clone without the merge commit")
        self.assertEqual(merged.returncode, 0)
        source_of = {target: source for source, target in RFS.RUNTIME_SOURCE_MAP.items()}
        for member, data in RFS.runtime_payloads(ROOT).items():
            if member not in source_of:
                continue
            new = subprocess.run(["git", "-C", str(ROOT), "show", f"{C.NEW_RELEASE}:{source_of[member]}"],
                                 capture_output=True, check=True).stdout
            self.assertEqual(new, data, member)

    def test_the_delta_is_the_git_bytes_of_d82f7da_against_this_tree(self):
        source_of = {target: source for source, target in RFS.RUNTIME_SOURCE_MAP.items()}
        current = RFS.runtime_payloads(ROOT)
        self.assertEqual(set(C.PAYLOAD_DELTA), set(H.OWNER_PROD_TREE_DELTA))
        for member, (before, after) in C.PAYLOAD_DELTA.items():
            old = subprocess.run(["git", "-C", str(ROOT), "show", f"{C.OLD_RELEASE}:{source_of[member]}"],
                                 capture_output=True, check=True).stdout
            self.assertEqual(sha(old), before, member)
            self.assertEqual(sha(current[member]), after, member)
        for member, data in current.items():                     # every other member is unchanged since OLD
            if member in C.PAYLOAD_DELTA or member not in source_of:
                continue
            old = subprocess.run(["git", "-C", str(ROOT), "show", f"{C.OLD_RELEASE}:{source_of[member]}"],
                                 capture_output=True)
            if old.returncode == 0:
                self.assertEqual(old.stdout, data, member)
        self.assertEqual(C.WITNESS_MEMBERS, frozenset({"lilith_recovery_witness/credential.py",
                                                      "lilith_recovery_witness/server.py"}))
        self.assertEqual(C.PAYLOAD_ADDED, {})

    def test_check_payload_refuses_any_other_difference(self):
        installed = {m: b for m, (b, _a) in C.PAYLOAD_DELTA.items()}
        with self.assertRaises(C.Refused):
            C.new_payload_pins({**installed, next(iter(installed)): "0" * 64})
        with self.assertRaises(C.Refused):
            C.check_payload({}, installed)


if __name__ == "__main__":
    unittest.main()
