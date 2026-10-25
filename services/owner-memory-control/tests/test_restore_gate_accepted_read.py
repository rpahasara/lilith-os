"""F9-C restore-suppression gate on the owner-controlled accepted-memory read path.

The V2 accepted-memory read (AcceptedMemoryReadFacadeV2.read_accepted) reads through the existing L04 read facade.
Given the gated privacy_hold_resolver (core-api ``memory_v2.restore_gated_hold_resolver``) that facade refuses
explicitly while the restore-suppression gate is not ready, so no accepted memory is served from unverified state,
and resumes once the separate maintenance step has made the database safe. Synthetic temporary databases only.
"""

from __future__ import annotations

import shutil
import unittest

import synthetic_b1b3b as T
from lilith_memory import canonical_contracts as C
from lilith_memory import memory_v2
from lilith_memory import privacy_governance as P
from lilith_memory import slice15b2a_migration
from lilith_owner_memory import accepted_read_v2 as AR
from lilith_owner_memory import admission_v2 as V2
from lilith_owner_memory import l04_v2_adapter as AD

import synthetic_authority as SA

TEST_ONLY_PRIVACY_SECRET = b"TEST_ONLY restore-gate accepted-read privacy secret"
IDENTITY = (T.L04_CLASS, T.L04_NAMESPACE, T.L04_KEY)


class GatedAcceptedReadTests(unittest.TestCase):
    def setUp(self) -> None:
        self.flow = T.Flow()
        self.addCleanup(self.flow.l04.close)
        l04 = self.flow.l04
        self.privacy_db = l04.root / "privacy.test.db"
        slice15b2a_migration.migrate_privacy(self.privacy_db, applied_at="2026-10-24T00:00:00.000000Z")
        self.privacy = P.PrivacyGovernanceStore(self.privacy_db, TEST_ONLY_PRIVACY_SECRET, l04.actor)
        _, proposal, proof, evidence = self.flow.create("SYNTH-GATED", "gated.read")
        admitted = self.flow.adapter.admit(self.flow.request(proposal, proof, evidence))
        self.assertEqual(admitted.status, AD.L04_ADMITTED)

    def reader(self):
        l04 = self.flow.l04
        resolver = memory_v2.restore_gated_hold_resolver(self.privacy, l04.db)
        facade = memory_v2.CanonicalMemoryReadFacade(
            l04.store(privacy_hold_resolver=resolver), registry=l04.tuple_registry, consent_store=l04.consent,
            privacy_hold_resolver=resolver, actor_resolver=lambda actor: actor == l04.actor.ACTOR)
        return AR.AcceptedMemoryReadFacadeV2(
            facade, l04.store(), owner_context=T.owner_context(), authority_context=SA.historical_context(),
            registry_provider=lambda: self.flow.registry_doc, challenge_record_provider=self.flow.challenge_record,
            link_store=self.flow.links, evidence_use_ledger=self.flow.ledger)

    def read(self, reader=None):
        return self.flow.read(reader or self.reader())

    def forget(self):
        l04 = self.flow.l04
        action = C.FrozenMemoryActionV1(
            schema_version=1, actor_ref_id=l04.actor.ACTOR.actor_ref_id, operation=C.FORGET,
            memory_class=T.L04_CLASS, subject_namespace=T.L04_NAMESPACE, subject_key=T.L04_KEY, value_schema=None,
            payload_digest="0" * 64, expected_active_revision_id=None, restore_revision_id=None,
            purpose=C.LONG_TERM_PERSONAL_PROJECT_RECALL)
        evidence = l04.actor.issue(action=action, request_digest="1" * 64, nonce="gated.forget")
        _r, auth, _s = self.privacy.begin_forget(
            action=action, actor_evidence_ref_id=evidence.actor_evidence_ref_id, intent_ref_id="intent.gated",
            memory_item_id=None, resource_owners=("L04", "L18_V2"), confirmation_event_ref="confirm.gated")
        for owner in (memory_v2.L04PrivacyErasureOwner(l04.db, self.privacy),
                      memory_v2.L18V2PrivacyErasureOwner(l04.db, self.privacy)):
            owner.erase_authorized(auth.authorization_ref_id, auth.execution_nonce)
        self.privacy.complete(auth.authorization_ref_id, auth.execution_nonce)

    def test_accepted_memory_is_served_when_ready(self):
        result = self.read()
        self.assertEqual(result.status, V2.ACCEPTED_MEMORY, result)
        self.assertIn("SYNTH-GATED", result.row["normalized_value_json"])

    def test_missing_privacy_state_refuses_the_accepted_read(self):
        reader = self.reader()
        moved = self.privacy_db.with_suffix(".moved")
        self.privacy_db.rename(moved)
        with self.assertRaises(P.RestoreSuppressionNotReady) as caught:
            self.read(reader)
        self.assertEqual(caught.exception.code, "PRIVACY_RECORDS_UNVERIFIED")
        moved.rename(self.privacy_db)
        self.assertEqual(self.read(reader).status, V2.ACCEPTED_MEMORY)

    def test_a_restored_forgotten_memory_is_refused_until_maintenance_then_not_readable(self):
        copy = self.flow.l04.root / "cognitive.pre-forget.copy.db"
        shutil.copyfile(self.flow.l04.db, copy)
        self.forget()
        self.assertEqual(self.read().reason, "NOT_READABLE")                     # forgotten, gate ready
        shutil.copyfile(copy, self.flow.l04.db)                                   # restore the old copy
        reader = self.reader()
        with self.assertRaises(P.RestoreSuppressionNotReady) as caught:
            self.read(reader)
        self.assertEqual(caught.exception.code, "SUPPRESSED_CONTENT_PRESENT")
        l04 = self.flow.l04
        verification = P.RestoreSuppressionVerifier(
            self.privacy, memory_v2.L04PrivacyErasureOwner(l04.db, self.privacy),
            memory_v2.L18V2PrivacyErasureOwner(l04.db, self.privacy)).verify_and_apply()
        self.assertEqual((verification.ready_to_serve, verification.matched_identities), (True, 1), verification)
        result = self.read(reader)
        self.assertEqual((result.status, result.reason), (V2.NOT_ACCEPTED, "NOT_READABLE"))
        self.assertNotIn(b"SYNTH-GATED", l04.db.read_bytes())


if __name__ == "__main__":
    unittest.main()
