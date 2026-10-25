"""Track B B4: the PROPOSED E-23 release contract (`e23_privacy_anchor_upgrade`). Repository only: nothing is built,
staged, selected, stopped, started or loaded."""

from __future__ import annotations

import hashlib
import unittest

import e23_installed as H
from e23_installed import E23, RFS, ROOT

import e22_judge_upgrade as E22  # noqa: E402
import install_authority_dev_v2 as I  # noqa: E402  (archive layout v2; V1 byte-identical)


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class ContractTests(unittest.TestCase):
    def test_old_is_the_installed_e22_release_and_new_is_unpinned(self):
        self.assertEqual(E23.OLD_RELEASE, "129f2bed617334be61dcac5204cd409946a7a566")
        self.assertEqual(E23.OLD_RELEASE, E22.NEW_RELEASE)
        self.assertIsNone(E23.NEW_RELEASE)
        self.assertIsNone(E23.NEW_MANIFEST_SHA256)
        self.assertEqual(E23.STATUS, "PROPOSED_NOT_ACCEPTED")

    def test_the_repository_payload_is_the_installed_payload_moved_by_exactly_the_delta(self):
        installed = {member: sha(data) for member, data in H.installed_payloads().items()}
        E23.check_payload(RFS.runtime_payloads(ROOT), installed)
        for member, (before, after) in E23.PAYLOAD_DELTA.items():
            self.assertEqual(sha(H.old_bytes(member)), before, member)          # proven against Git history
            self.assertEqual(sha(RFS.runtime_payloads(ROOT)[member]), after, member)

    def test_any_other_difference_is_refused(self):
        installed = {member: sha(data) for member, data in H.installed_payloads().items()}
        payloads = dict(RFS.runtime_payloads(ROOT))
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
        self.assertEqual(I.RUNTIME_PATHS, frozenset(RFS.RUNTIME_SOURCE_MAP.values()))

    def test_unit_carries_the_k_pan_credential_and_anchor_state(self):
        unit = RFS.runtime_payloads(ROOT)[E23.WITNESS_UNIT].decode()
        self.assertIn(f"LoadCredentialEncrypted={E23.KPAN_CREDENTIAL_NAME}:{E23.KPAN_CREDENTIAL_BLOB}\n", unit)
        self.assertIn(E23.ANCHOR_STATE_DIR, unit)


if __name__ == "__main__":
    unittest.main()
