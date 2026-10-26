"""RR-39: archive layout v3 (`install_authority_dev_v3`) next to the byte-identical V1 and V2 installers.
Repository only: temporary directories and stand-in wheels; nothing is installed."""

from __future__ import annotations

import hashlib
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
for _p in (ROOT / "services/authority-dev/ceremony", ROOT / "services/authority-dev", ROOT / "services/core-api",
           ROOT / "services/owner-memory-control", HERE):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import attest_authority_dev_build as AT  # noqa: E402
import build_authority_dev_release as B  # noqa: E402
import install_authority_dev as V1  # noqa: E402
import install_authority_dev_v2 as V2  # noqa: E402
import install_authority_dev_v3 as V3  # noqa: E402
import installed_layout as IL  # noqa: E402
import pr1s_fixtures as FX  # noqa: E402
import release_file_set as RFS  # noqa: E402
import test_trackb_layout_v2 as L2  # noqa: E402

SHA = "1" * 40
# The exact post-E-23 source change to the signer runtime (RR-39, then the First Memory DEV wiring), against the
# installed E-23 NEW release.
RR39_CHANGED = frozenset({"lilith_authority_dev/core.py", "lilith_authority_dev/credential.py",
                          "lilith_authority_dev/ledger.py", "lilith_authority_dev/protocol.py",
                          # First Memory: the DEV runtime wiring and the evidence-use transport.
                          "lilith_authority_dev/profile.py", "lilith_authority_dev/server.py",
                          "lilith_authority_host/inputs.py", "lilith_authority_host/paths.py",
                          "lilith_authority_root/clients.py",
                          # First Memory privilege fix: the root bridge (`first-memory` form).
                          "lilith_authority_root/cli.py"})


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class LayoutV3Tests(unittest.TestCase):
    def test_v1_and_v2_are_byte_identical_and_v3_adds_exactly_the_issuance_members(self):
        ceremony = ROOT / "services/authority-dev/ceremony"
        self.assertEqual(sha((ceremony / "install_authority_dev.py").read_bytes()),
                         "fe10d9a37c53d4a32ca49d79ee5987c6546866feeebcee3c882087f51ed55487")
        self.assertEqual(sha((ceremony / "install_authority_dev_v2.py").read_bytes()),
                         "cf995dd15beeddae4f6991a62c06d7c3128f8746ba5e497a1a55248aa010e969")
        self.assertEqual(V3.ADDED_RUNTIME_PATHS, {"lilith_authority_dev/issuance.py", "lilith_owner_memory/verifier.py"})
        self.assertEqual(V3.RUNTIME_PATHS - V2.RUNTIME_PATHS, V3.ADDED_RUNTIME_PATHS)
        self.assertEqual(V3.EXPECTED_PATHS - V2.EXPECTED_PATHS, V3.ADDED_RUNTIME_PATHS)
        self.assertEqual(V3.RUNTIME_PATHS, frozenset(RFS.RUNTIME_SOURCE_MAP.values()))
        for name in ("stage_release", "status", "release_tree_failures", "manifest_for", "write_archive", "ROLE",
                     "WHEEL_HASHES", "LOCK"):
            self.assertIs(getattr(V3, name), getattr(V1, name), name)       # everything else IS V1
        self.assertIs(B.I, V3)
        self.assertIs(AT.I, V3)
        self.assertIn("services/authority-dev/ceremony/install_authority_dev_v3.py", AT.RECIPE_FILES)

    def test_each_installer_refuses_the_other_layout(self):
        with FX.stand_in_wheels() as wheels, tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            new = B.build_payloads(ROOT, wheels)                             # the RR-39 (v3) layout
            e23 = IL._build_v2(ROOT, wheels)                                 # the E-23 (v2) layout
            self.assertEqual(set(new) - set(e23), V3.ADDED_RUNTIME_PATHS)
            before = V1.EXPECTED_PATHS
            for installer, payloads in ((V1, new), (V2, new), (V3, e23)):
                with self.subTest(installer=installer.__name__), self.assertRaises(V1.InstallError) as caught:
                    installer.check_payloads(payloads)
                self.assertEqual(str(caught.exception), "RELEASE_FILE_SET_MISMATCH")
            self.assertIs(V1.EXPECTED_PATHS, before)                         # restored, also after a refusal
            new_archive = L2.archive(directory, new, "new")
            e23_archive = L2.archive(directory, e23, "e23")
            _manifest, payloads = V3.verify_archive(*new_archive, SHA)
            self.assertEqual(payloads, new)
            V2.verify_archive(*e23_archive, SHA)
            for installer, pair in ((V1, new_archive), (V2, new_archive), (V3, e23_archive)):
                with self.subTest(installer=installer.__name__), self.assertRaises(V1.InstallError):
                    installer.verify_archive(*pair, SHA)
            self.assertIs(V1.EXPECTED_PATHS, before)

    def test_the_repository_payload_is_e23_moved_by_exactly_the_rr39_delta(self):
        payloads = RFS.runtime_payloads(ROOT)
        source_of = {target: source for source, target in RFS.RUNTIME_SOURCE_MAP.items()}
        e23 = {member: IL.old_source_bytes(source_of[member], IL.E23_RELEASE) for member in V2.RUNTIME_PATHS}
        self.assertEqual(set(payloads) - set(e23), V3.ADDED_RUNTIME_PATHS)
        self.assertEqual({m for m in e23 if payloads[m] != e23[m]}, RR39_CHANGED)
        # The shared verifier is carried at its pinned bytes; the witness, root and host trees are untouched.
        self.assertEqual(sha(payloads["lilith_owner_memory/verifier.py"]),
                         RFS.SHARED_HASHES["services/owner-memory-control/lilith_owner_memory/verifier.py"])
        self.assertFalse({m for m in RR39_CHANGED | V3.ADDED_RUNTIME_PATHS
                          if not m.startswith(("lilith_authority_dev/", "lilith_owner_memory/", "lilith_authority_host/",
                                               "lilith_authority_root/"))})

    def test_the_installed_layout_carries_no_successor_member(self):
        with FX.stand_in_wheels() as wheels:
            old = IL.installed_build_payloads(ROOT, wheels)
        self.assertFalse(set(old) & (V2.ADDED_RUNTIME_PATHS | V3.ADDED_RUNTIME_PATHS))
        self.assertEqual(set(old), V1.EXPECTED_PATHS)


if __name__ == "__main__":
    unittest.main()
