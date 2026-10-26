"""Track B B4: archive layout v2 (`install_authority_dev_v2`) next to the byte-identical V1 installer.
Repository only: temporary directories and stand-in wheels; nothing is installed.

RR-39 moved the tree on to archive layout v3 (`test_rr39_layout_v3`); v2 is judged on the E-23 NEW payload
(`installed_layout._build_v2`, the 57bff671 bytes) and V2 itself stays byte-identical."""

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

import build_authority_dev_release as B  # noqa: E402
import install_authority_dev as V1  # noqa: E402
import install_authority_dev_v2 as V2  # noqa: E402
import install_authority_dev_v3 as V3  # noqa: E402
import installed_layout as IL  # noqa: E402
import pr1s_fixtures as FX  # noqa: E402
import release_file_set as RFS  # noqa: E402

SHA = "1" * 40


def archive(directory: Path, payloads: dict, name: str) -> tuple[Path, Path]:
    manifest = V1.manifest_for(SHA, payloads)
    raw = V1.write_archive(payloads, manifest)
    path, stamp = directory / f"{name}.tar.gz", directory / f"{name}.json"
    path.write_bytes(raw)
    stamp.write_bytes(V1.canonical({"schemaVersion": 1, "artifactRole": V1.ROLE, "candidateSha": SHA,
                                    "archiveByteSize": len(raw), "archiveSha256": V1.digest(raw),
                                    "manifestSha256": V1.digest(V1.canonical(manifest))}))
    return path, stamp


class LayoutTests(unittest.TestCase):
    def test_v1_is_byte_identical_and_v2_adds_exactly_two_members(self):
        self.assertEqual(hashlib.sha256((ROOT / "services/authority-dev/ceremony/install_authority_dev.py").read_bytes())
                         .hexdigest(), "fe10d9a37c53d4a32ca49d79ee5987c6546866feeebcee3c882087f51ed55487")
        self.assertEqual(V2.ADDED_RUNTIME_PATHS, {"lilith_recovery_witness/privacy_anchor.py",
                                                  "lilith_memory/privacy_anchor_contracts.py"})
        self.assertEqual(V2.RUNTIME_PATHS - V1.RUNTIME_PATHS, V2.ADDED_RUNTIME_PATHS)
        self.assertEqual(V2.EXPECTED_PATHS - V1.EXPECTED_PATHS, V2.ADDED_RUNTIME_PATHS)
        self.assertEqual(V2.RUNTIME_PATHS, frozenset(RFS.RUNTIME_SOURCE_MAP.values()) - V3.ADDED_RUNTIME_PATHS)
        for name in ("stage_release", "status", "release_tree_failures", "manifest_for", "write_archive", "ROLE"):
            self.assertIs(getattr(V2, name), getattr(V1, name), name)       # everything else IS V1
        # RR-39: V2 is the E-23 (57bff671) bytes; the builder moved on to the v3 successor.
        self.assertEqual(hashlib.sha256((ROOT / "services/authority-dev/ceremony/install_authority_dev_v2.py")
                                        .read_bytes()).hexdigest(),
                         "cf995dd15beeddae4f6991a62c06d7c3128f8746ba5e497a1a55248aa010e969")
        self.assertIs(B.I, V3)

    def test_each_installer_refuses_the_other_layout(self):
        with FX.stand_in_wheels() as wheels, tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            new = IL._build_v2(ROOT, wheels)                                 # the E-23 (v2) layout
            old = IL.installed_build_payloads(ROOT, wheels)                  # the installed (v1) layout
            self.assertEqual(set(new) - set(old), V2.ADDED_RUNTIME_PATHS)
            before = V1.EXPECTED_PATHS
            with self.assertRaises(V1.InstallError) as caught:
                V1.check_payloads(new)
            self.assertEqual(caught.exception.args[0] if caught.exception.args else str(caught.exception),
                             "RELEASE_FILE_SET_MISMATCH")
            with self.assertRaises(V1.InstallError):
                V2.check_payloads(old)
            self.assertIs(V1.EXPECTED_PATHS, before)                         # restored, also after a refusal
            new_archive = archive(directory, new, "new")
            old_archive = archive(directory, old, "old")
            manifest, payloads = V2.verify_archive(*new_archive, SHA)
            self.assertEqual(payloads, new)
            V1.verify_archive(*old_archive, SHA)
            with self.assertRaises(V1.InstallError):
                V1.verify_archive(*new_archive, SHA)
            with self.assertRaises(V1.InstallError):
                V2.verify_archive(*old_archive, SHA)
            self.assertIs(V1.EXPECTED_PATHS, before)

    def test_installed_layout_is_the_129f2be_bytes(self):
        with FX.stand_in_wheels() as wheels:
            old = IL.installed_build_payloads(ROOT, wheels)
        for member in ("lilith_recovery_witness/credential.py", "lilith_recovery_witness/server.py",
                       "assets/lilith-recovery-witness.service"):
            source = next(s for s, t in RFS.RUNTIME_SOURCE_MAP.items() if t == member)
            self.assertEqual(old[member], IL.old_source_bytes(source))
            self.assertNotEqual(old[member], (ROOT / source).read_bytes())


if __name__ == "__main__":
    unittest.main()
