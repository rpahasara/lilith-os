"""Relationship-origin correction offer through the real conversation chain (TEST_ONLY; synthetic statements).

Source-only stage (owner decision 2026-11-08): the L04/L18 side and schema v4 are in place, the authority signer is NOT
yet upgraded. These proofs therefore cover the offer and the fail-closed boundary:

1. "correct our origin: <full statement>" on a v4 database offers ONE owner-approved SUPERSEDE of the SAME item, bound
   to the ACCEPTED active revision (challenge memoryItemId / expectedActiveRevisionId); an offer writes nothing;
2. a v3 database, nothing admitted yet, or an unchanged statement refuse at the offer;
3. until the signer release that admits the correction is installed, the signer refuses it: nothing is written and the
   original memory is still recalled unchanged.
"""

from __future__ import annotations

import json
import sqlite3
import unittest

import test_relationship_origin_conversation as ROC

from lilith_memory import backup  # noqa: E402
from lilith_memory import canonical_contracts as C  # noqa: E402
from lilith_memory import relationship_origin_correction_migration as RCM  # noqa: E402
from lilith_owner_memory import first_memory_conversation as FMC  # noqa: E402

ORIGINAL = "TEST_ONLY I'm saving this. Not because it is profound, a synthetic line."
CORRECTED = "TEST_ONLY I'm saying this. Not because it is profound, a synthetic line."
BASE = ROC.RelationshipOriginConversationTests


class RelationshipOriginCorrectionOfferTests(unittest.TestCase):
    copy_db = staticmethod(BASE.copy_db)
    forget_first_interaction = BASE.forget_first_interaction
    bind = BASE.bind
    reader = BASE.reader
    owner_consents = BASE.owner_consents
    conversation = BASE.conversation
    remember = BASE.remember
    table_rows = BASE.table_rows

    def setUp(self) -> None:
        BASE.setUp(self)
        _offer, created = self.remember("Remember our origin: " + ORIGINAL)
        self.assertEqual(created.status, FMC.ADMITTED, created)

    def migrate_v4(self):
        l04 = self.flow.l04
        manifest = backup.create_backup(l04.db, self.root / "pre-v4.db", self.root / "pre-v4.manifest.json",
                                        role="cognitive")
        RCM.migrate(l04.db, backup_manifest=manifest, applied_at="2026-11-08T00:00:01.000000Z")

    def active(self):
        conn = sqlite3.connect(self.flow.l04.db)
        try:
            return conn.execute(
                "SELECT i.memory_item_id,a.revision_id FROM memory_item i JOIN memory_active_revision a "
                "ON a.memory_item_id=i.memory_item_id WHERE i.memory_class=?",
                ("OWNER_PROVIDED_RELATIONSHIP_ORIGIN",)).fetchone()
        finally:
            conn.close()

    def test_a_v4_correction_offer_is_one_bound_supersede_and_writes_nothing(self):
        self.migrate_v4()
        item_id, revision_id = self.active()
        before = self.table_rows()
        offer = self.fm.offer("sess.c", "Correct our origin: " + CORRECTED)
        self.assertEqual((offer.status, offer.kind, offer.operation, offer.value, offer.replaces_revision_id),
                         (FMC.OFFERED, "relationship-origin", C.SUPERSEDE, CORRECTED, revision_id))
        challenge = json.loads(offer.challenge_json)
        self.assertEqual((challenge["operation"], challenge["memoryItemId"], challenge["expectedActiveRevisionId"]),
                         (C.SUPERSEDE, item_id, revision_id))
        action = self.fm._pending[offer.offer_id].action
        self.assertEqual((action.operation, action.expected_active_revision_id), (C.SUPERSEDE, revision_id))
        action.validate()
        self.assertEqual(self.table_rows(), before)                           # an offer is not memory

    def test_v3_nothing_to_correct_and_unchanged_refuse_at_the_offer(self):
        with self.assertRaises(FMC.FirstMemoryRefused) as caught:            # schema v3: no correction path
            self.fm.offer("sess.c", "Correct our origin: " + CORRECTED)
        self.assertEqual(caught.exception.code, "CORRECTION_SCHEMA_UNAVAILABLE")
        self.migrate_v4()
        with self.assertRaises(FMC.FirstMemoryRefused) as caught:
            self.fm.offer("sess.c", "Correct our origin: " + ORIGINAL)
        self.assertEqual(caught.exception.code, "CORRECTION_UNCHANGED")
        for text in ("correct our origin", "correct our origin:   ", "Correct my origin: x"):
            self.assertEqual(self.fm.offer("sess.c", text).status, FMC.NOT_A_MEMORY_REQUEST, text)

    def test_the_installed_signer_wire_still_refuses_a_correction(self):
        """Until the signer release with the correction rule is installed, the real signer refuses the action."""
        self.migrate_v4()
        offer = self.fm.offer("sess.c", "Correct our origin: " + CORRECTED)
        action = self.fm._pending[offer.offer_id].action
        fields = {"schemaVersion": 1, "actorRefId": action.actor_ref_id, "operation": action.operation,
                  "memoryClass": action.memory_class, "subjectNamespace": action.subject_namespace,
                  "subjectKey": action.subject_key, "valueSchema": action.value_schema,
                  "payloadDigest": action.payload_digest, "expectedActiveRevisionId": action.expected_active_revision_id,
                  "restoreRevisionId": None, "purpose": action.purpose}
        assertion, credential = self.owner_consents(offer)
        with self.assertRaises(ROC.SIGNER_WIRE.ProtocolError) as caught:
            ROC.SIGNER_WIRE.parse_issue_request({"challengeId": offer.offer_id, "assertion": dict(assertion),
                                                 "ownerCredential": dict(credential), "action": fields})
        self.assertEqual(caught.exception.code, "INVALID_ACTION")

    def test_with_an_admitting_signer_the_correction_is_the_accepted_memory_and_history_is_kept(self):
        """The full chain with the test broker standing in for the upgraded signer (owner proof, evidence, L04 V2
        adapter, accepted read): a new session recalls the corrected statement; the original revision stays."""
        self.migrate_v4()
        item_id, original_revision = self.active()
        offer = self.fm.offer("sess.c", "Correct our origin: " + CORRECTED)
        assertion, credential = self.owner_consents(offer)
        result = self.fm.consent(offer.offer_id, "sess.c", assertion, credential)
        self.assertEqual(result.status, FMC.ADMITTED, result)
        new_item, new_revision = self.active()
        self.assertEqual(new_item, item_id)
        self.assertNotEqual(new_revision, original_revision)
        conn = sqlite3.connect(self.flow.l04.db)
        try:
            rows = dict(conn.execute("SELECT revision_id,supersedes_revision_id FROM memory_revision "
                                     "WHERE memory_item_id=?", (item_id,)).fetchall())
        finally:
            conn.close()
        self.assertEqual(rows, {original_revision: None, new_revision: original_revision})
        recalled = self.conversation(ROC.FMT.TestBrokerIssuer(self.flow)).recall("sess.d-new", ROC.ASK_ORIGIN)
        self.assertEqual((recalled.status, recalled.value), (FMC.RECALLED, CORRECTED))
        context = self.conversation(ROC.FMT.TestBrokerIssuer(self.flow)).recall_authorized("sess.e-new")
        self.assertEqual([(m.kind, m.value, m.revision_id) for m in context],
                         [("relationship-origin", CORRECTED, new_revision)])


if __name__ == "__main__":
    unittest.main()
