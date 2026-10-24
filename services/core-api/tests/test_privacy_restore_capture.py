"""F9-C restore suppression of the First Interaction capture copy (the relay's separate capture database, F4/F5).

A restored pre-FORGET capture database must not make captured dialogue available again: the L18 V2 owner, given the
capture path the relay uses, erases it (and re-writes the permanent capture block) before the verifier reports ready.
Real capture store (app.ConversationCaptureStore), real Privacy store, synthetic temporary databases only.
"""

from __future__ import annotations

import shutil
import sqlite3
import unittest

from test_privacy_forget_capture import (CAPTURE_TABLES, FAULTED_TEXT, SEALED_TEXT, UNFINISHED_TEXT,  # noqa: F401
                                         CaptureForgetCase)
from test_first_interaction_l04 import fi_value

from lilith_memory import canonical_store
from lilith_memory import memory_action_v2 as MA
from lilith_memory import memory_v2
from lilith_memory import privacy_governance as privacy

FI = MA.FIRST_INTERACTION_IDENTITY


class RestoreCaptureCase(CaptureForgetCase):
    def setUp(self) -> None:
        super().setUp()
        self.populate_capture()
        _action, ref = self.fi_proposal(fi_value(closing="TEST_ONLY capture farewell"), nonce="fi.capture")
        self.assertEqual(self.fi_store().apply(ref.proposal_ref_id).outcome, canonical_store.ACCEPTED)
        self.cognitive_copy, self.capture_copy = self.root / "cognitive.copy.db", self.root / "capture.copy.db"
        shutil.copyfile(self.db, self.cognitive_copy)
        shutil.copyfile(self.capture_db, self.capture_copy)
        auth = self.begin()
        self.l18(auth)
        self.privacy.complete(auth.authorization_ref_id, auth.execution_nonce)
        self.assert_capture_erased(SEALED_TEXT)

    def verify(self, capture_path="default"):
        l18 = memory_v2.L18V2PrivacyErasureOwner(
            self.db, self.privacy, capture_evidence_path=self.capture_db if capture_path == "default" else capture_path)
        return privacy.RestoreSuppressionVerifier(
            self.privacy, memory_v2.L04PrivacyErasureOwner(self.db, self.privacy), l18).verify_and_apply()

    def block_rows(self) -> int:
        conn = sqlite3.connect(self.capture_db)
        try:
            present = {str(r[0]) for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            if "fi_capture_privacy_block" not in present:
                return 0
            return int(conn.execute("SELECT COUNT(*) FROM fi_capture_privacy_block").fetchone()[0])
        finally:
            conn.close()


class RestoreCaptureTests(RestoreCaptureCase):
    def test_restored_cognitive_and_capture_copies_are_both_suppressed(self):
        shutil.copyfile(self.cognitive_copy, self.db)
        shutil.copyfile(self.capture_copy, self.capture_db)
        self.assertEqual((self.capture_counts()["fi_capture_session"], self.block_rows()), (3, 0))
        verification = self.verify()
        self.assertEqual((verification.ready_to_serve, verification.matched_identities), (True, 1), verification)
        self.assert_capture_erased(SEALED_TEXT, UNFINISHED_TEXT, FAULTED_TEXT, "TEST_ONLY sealed reply")
        self.assertEqual(self.block_rows(), 1)                                    # permanent block re-written
        self.assertNotIn(b"TEST_ONLY capture farewell", self.db.read_bytes())

    def test_a_restored_capture_copy_alone_is_detected_and_suppressed(self):
        shutil.copyfile(self.capture_copy, self.capture_db)                       # cognitive database is clean
        verification = self.verify()
        self.assertEqual((verification.ready_to_serve, verification.matched_identities), (True, 1), verification)
        self.assert_capture_erased(SEALED_TEXT, UNFINISHED_TEXT, FAULTED_TEXT)
        self.assertEqual(self.verify().matched_identities, 0)                     # idempotent re-run

    def test_a_restored_capture_copy_without_its_immutability_triggers_stays_refused(self):
        shutil.copyfile(self.capture_copy, self.capture_db)
        conn = sqlite3.connect(self.capture_db)
        conn.execute("DROP TRIGGER fi_capture_turn_no_delete")
        conn.commit()
        conn.close()
        for _ in range(2):
            verification = self.verify()
            self.assertEqual((verification.ready_to_serve, verification.failure_code),
                             (False, "RESTORE_VERIFICATION_FAILED"))
        self.assertGreater(self.capture_counts()["fi_capture_session"], 0)

    def test_a_restored_capture_copy_blocks_gated_memory_serving_until_maintenance(self):
        resolver = memory_v2.restore_gated_hold_resolver(self.privacy, self.db, capture_evidence_path=self.capture_db)
        resolver.require_ready()                                                   # erased: ready
        shutil.copyfile(self.capture_copy, self.capture_db)                       # cognitive database is clean
        with self.assertRaises(privacy.RestoreSuppressionNotReady) as caught:
            resolver.is_held(*FI)
        self.assertEqual(caught.exception.code, "SUPPRESSED_CONTENT_PRESENT")
        self.assertTrue(self.verify().ready_to_serve)                             # maintenance, then serving
        resolver.require_ready()

    def test_an_unreadable_capture_copy_fails_closed(self):
        self.capture_db.write_bytes(b"TEST_ONLY not a database" * 50)
        self.assertFalse(self.verify().ready_to_serve)


if __name__ == "__main__":
    unittest.main()
