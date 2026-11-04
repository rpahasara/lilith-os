"""Track B B4: the PROPOSED E-23 release contract (`e23_privacy_anchor_upgrade`). Repository only: nothing is built,
staged, selected, stopped, started or loaded."""

from __future__ import annotations

import hashlib
import subprocess
import unittest

import e23_installed as H
from e23_installed import E23, RFS, ROOT

import e22_judge_upgrade as E22  # noqa: E402
import install_authority_dev_v2 as I  # noqa: E402  (archive layout v2; V1 byte-identical)


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class ContractTests(unittest.TestCase):
    def test_old_is_the_installed_e22_release_and_new_is_the_attested_build(self):
        # OLD stays the installed E-22 release (record trackb-e23-new-release-pin §4).
        self.assertEqual(E23.OLD_RELEASE, "129f2bed617334be61dcac5204cd409946a7a566")
        self.assertEqual(E23.OLD_RELEASE, E22.NEW_RELEASE)
        self.assertEqual(E23.OLD_MANIFEST_SHA256, "fc7dbf08bb5b8260716a762fd2fbccdb44fbf0e438e2e21d0cfddcd6f1a3348a")
        self.assertEqual(E23.NEW_RELEASE, "57bff671fbfe5df4e59248d5d69338dc0ba05846")       # the PR #251 merge
        self.assertEqual(E23.NEW_MANIFEST_SHA256, "fc29a23cbb411704f2799b418f8c7fd7fadf215489174e9ac9d370db2e78368c")
        self.assertEqual(E23.NEW_RELEASE_ATTESTATION["archiveSha256"],
                         "a8cadbfa75023ed19c6939b17841e56f1ad9d0b83a6f854755621e32ed174486")
        self.assertEqual(E23.STATUS, "PROPOSED_NOT_ACCEPTED")

    def test_the_pinned_new_source_is_the_installed_payload_moved_by_exactly_the_delta(self):
        installed = {member: sha(data) for member, data in H.installed_payloads().items()}
        pinned = {target: subprocess.run(["git", "show", f"{E23.NEW_RELEASE}:{source}"], cwd=ROOT,
                                         capture_output=True, check=True).stdout
                  for source, target in RFS.RUNTIME_SOURCE_MAP.items()
                  if target not in H.V3.ADDED_RUNTIME_PATHS}            # RR-39 (layout v3) members postdate E-23
        E23.check_payload(pinned, installed)

    def test_the_pin_record_names_every_pin_and_is_not_approved(self):
        record = (ROOT / "docs/architecture/trackb-e23-new-release-pin.md").read_text(encoding="utf-8")
        self.assertIn("PROPOSED — NOT APPROVED", record)
        for value in (E23.NEW_RELEASE, E23.NEW_MANIFEST_SHA256, E23.OLD_RELEASE, E23.OLD_MANIFEST_SHA256,
                      *E23.NEW_RELEASE_ATTESTATION.values()):
            self.assertIn(str(value), record)

    def test_the_repository_payload_is_the_installed_payload_moved_by_exactly_the_delta(self):
        # RR-39 moved the repository on (archive layout v3, pinned by authority-dev `test_rr39_layout_v3`); its E-23
        # part is the repository payload with that change reverted.
        installed = {member: sha(data) for member, data in H.installed_payloads().items()}
        E23.check_payload(H.e23_new_payloads(), installed)
        for member, (before, after) in E23.PAYLOAD_DELTA.items():
            self.assertEqual(sha(H.old_bytes(member)), before, member)          # proven against Git history
            now = H.e23_new_bytes(member) if member in H.OWNER_PROD_INSTALLED else RFS.runtime_payloads(ROOT)[member]
            self.assertEqual(sha(now), after, member)                  # OWNER_PROD (P2) later moved some on

    def test_any_other_difference_is_refused(self):
        installed = {member: sha(data) for member, data in H.installed_payloads().items()}
        payloads = H.e23_new_payloads()
        other = next(m for m in sorted(payloads) if m not in E23.PAYLOAD_DELTA and m not in E23.PAYLOAD_ADDED)
        for mutate, reason in ((lambda p: p.__setitem__(other, p[other] + b"\n"), "PAYLOAD_DELTA_NOT_EXACT"),
                               (lambda p: p.__setitem__("lilith_x/extra.py", b""), "PAYLOAD_MEMBER_UNEXPECTED"),
                               (lambda p: p.pop("lilith_memory/privacy_anchor_contracts.py"), "PAYLOAD_MEMBER_MISSING")):
            tampered = dict(payloads)
            mutate(tampered)
            with self.subTest(reason=reason), self.assertRaises(E23.Refused) as caught:
                E23.check_payload(tampered, installed)
            self.assertEqual(caught.exception.reason, reason)

    def test_the_signer_payload_is_untouched(self):
        changed = set(E23.PAYLOAD_DELTA) | set(E23.PAYLOAD_ADDED)
        self.assertFalse({m for m in changed if m.startswith(("lilith_authority_dev/", "lilith_authority_root/",
                                                               "lilith_authority_host/", "lilith_owner_memory/"))})
        self.assertEqual({m.split("/")[0] for m in changed}, {"lilith_recovery_witness", "assets", "lilith_memory"})

    def test_the_installer_and_shared_hashes_carry_exactly_the_two_additions(self):
        self.assertTrue(set(E23.PAYLOAD_ADDED) <= I.RUNTIME_PATHS)
        self.assertEqual(RFS.SHARED_HASHES["services/core-api/lilith_memory/privacy_anchor_contracts.py"],
                         E23.PAYLOAD_ADDED["lilith_memory/privacy_anchor_contracts.py"])
        # RR-39 moved the tree on to archive layout v3: exactly its two members on top of the E-23 layout.
        import install_authority_dev_v3 as V3
        self.assertEqual(I.RUNTIME_PATHS | V3.ADDED_RUNTIME_PATHS, frozenset(RFS.RUNTIME_SOURCE_MAP.values()))
        self.assertEqual(V3.RUNTIME_PATHS - V3.ADDED_RUNTIME_PATHS, I.RUNTIME_PATHS)

    def test_unit_carries_the_k_pan_credential_and_anchor_state(self):
        unit = RFS.runtime_payloads(ROOT)[E23.WITNESS_UNIT].decode()
        self.assertIn(f"LoadCredentialEncrypted={E23.KPAN_CREDENTIAL_NAME}:{E23.KPAN_CREDENTIAL_BLOB}\n", unit)
        self.assertIn(E23.ANCHOR_STATE_DIR, unit)


if __name__ == "__main__":
    unittest.main()
