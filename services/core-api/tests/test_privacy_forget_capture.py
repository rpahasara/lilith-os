"""F4: an authorized First Interaction FORGET erases the relay's captured conversation evidence.

The L18 V2 Privacy erasure owner, given the capture database path, erases every capture session (sealed, unfinished,
faulted, never admitted) for the single First Interaction identity, after its own L18 commit and before it records
COMPLETE. A capture-erasure failure therefore leaves Privacy incomplete with the hold active, and a retry finishes.
Other identities and the ordinary relay are untouched; no capture database is created to perform erasure.

Synthetic temporary databases, the real capture store (app.ConversationCaptureStore) and the real Privacy Governance
store only. Capture stays disabled; nothing here relays a conversation.
"""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

from test_canonical_runtime import TEST_CLASS, TEST_KEY, TEST_NAMESPACE, digest, stamp_text  # noqa: F401
from test_first_interaction_l04 import FI_CLASS, FI_KEY, FI_NAMESPACE, FI_PURPOSE, FirstInteractionCase, fi_value

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import app  # noqa: E402

from lilith_memory import canonical_contracts as contracts  # noqa: E402
from lilith_memory import canonical_store  # noqa: E402
from lilith_memory import memory_action_v2 as MA  # noqa: E402
from lilith_memory import memory_v2  # noqa: E402
from lilith_memory import privacy_governance as privacy  # noqa: E402
from lilith_memory import slice15b2a_migration  # noqa: E402

TEST_ONLY_PRIVACY_SECRET = b"TEST_ONLY F4 capture-forget privacy secret (32+ bytes)"
CAPTURE_TABLES = ("fi_capture_session", "fi_capture_turn", "fi_capture_fault", "fi_conversation_evidence")
SEALED_TEXT = "TEST_ONLY sealed hello"
UNFINISHED_TEXT = "TEST_ONLY unfinished hello"
FAULTED_TEXT = "TEST_ONLY faulted hello"


class CaptureForgetCase(FirstInteractionCase):
    def setUp(self) -> None:
        super().setUp()
        self.create()                                                         # codename "SYNTH-ALPHA" survives
        self.migrate_fi()
        self.enable_fi()
        path = self.root / "privacy.test.db"
        slice15b2a_migration.migrate_privacy(path, applied_at=stamp_text(3))
        self.privacy = privacy.PrivacyGovernanceStore(path, TEST_ONLY_PRIVACY_SECRET, self.actor,
                                                      now_fn=lambda: self.now)
        self.capture_db = self.root / "conversation-evidence.test.db"
        self.capture = app.ConversationCaptureStore(self.capture_db)

    def stamp(self, seconds: int) -> str:
        return f"2026-11-01T18:00:{seconds:02d}.000000Z"

    def populate_capture(self) -> dict:
        """One sealed, one unfinished and one faulted session; none ever reaches a memory candidate."""
        sealed = self.capture.open_session()
        self.capture.record_exchange(sealed, owner_text=SEALED_TEXT, owner_at=self.stamp(0),
                                     lilith_text="TEST_ONLY sealed reply", lilith_at=self.stamp(1))
        self.capture.seal(sealed)
        unfinished = self.capture.open_session()
        self.capture.record_exchange(unfinished, owner_text=UNFINISHED_TEXT, owner_at=self.stamp(2),
                                     lilith_text="TEST_ONLY unfinished reply", lilith_at=self.stamp(3))
        faulted = self.capture.open_session()
        self.capture.record_exchange(faulted, owner_text=FAULTED_TEXT, owner_at=self.stamp(4),
                                     lilith_text="TEST_ONLY faulted reply", lilith_at=self.stamp(5))
        self.capture.record_fault(faulted, "RELAY_504")
        return {"sealed": sealed, "unfinished": unfinished, "faulted": faulted}

    def capture_counts(self) -> dict:
        conn = sqlite3.connect(self.capture_db)
        try:
            return {t: int(conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]) for t in CAPTURE_TABLES}
        finally:
            conn.close()

    def capture_triggers(self) -> set:
        conn = sqlite3.connect(self.capture_db)
        try:
            return {str(r[0]) for r in conn.execute("SELECT name FROM sqlite_master WHERE type='trigger'")}
        finally:
            conn.close()

    def begin(self, identity=MA.FIRST_INTERACTION_IDENTITY):
        memory_class, namespace, key = identity
        fields = dict(schema_version=1, actor_ref_id=self.actor.ACTOR.actor_ref_id, operation=contracts.FORGET,
                      memory_class=memory_class, subject_namespace=namespace, subject_key=key, value_schema=None,
                      payload_digest="0" * 64, expected_active_revision_id=None, restore_revision_id=None)
        if identity == MA.FIRST_INTERACTION_IDENTITY:
            action, store = MA.action_from_fields(**fields, purpose=FI_PURPOSE), self.fi_store()
        else:
            action = contracts.FrozenMemoryActionV1(**fields, purpose=contracts.LONG_TERM_PERSONAL_PROJECT_RECALL)
            store = self.fi_store()
        active = store.get_active(*identity)
        evidence = self.actor.issue(action=action, request_digest=digest("forget:" + key), nonce="forget." + key)
        _request, auth, _suppression = self.privacy.begin_forget(
            action=action, actor_evidence_ref_id=evidence.actor_evidence_ref_id, intent_ref_id="intent.forget." + key,
            memory_item_id=None if active is None else active["memory_item_id"],
            resource_owners=("L04", "L18_V2"), confirmation_event_ref="confirm.forget." + key)
        memory_v2.L04PrivacyErasureOwner(self.db, self.privacy).erase_authorized(
            auth.authorization_ref_id, auth.execution_nonce)
        return auth

    def l18(self, auth, capture_path="default"):
        owner = memory_v2.L18V2PrivacyErasureOwner(
            self.db, self.privacy, capture_evidence_path=self.capture_db if capture_path == "default" else capture_path)
        return owner.erase_authorized(auth.authorization_ref_id, auth.execution_nonce)

    def assert_capture_erased(self, *gone: str):
        self.assertEqual(self.capture_counts(), {t: 0 for t in CAPTURE_TABLES})
        self.assertTrue({f"{t}_no_delete" for t in CAPTURE_TABLES} <= self.capture_triggers())   # restored
        raw = self.capture_db.read_bytes()
        for text in gone:
            self.assertNotIn(text.encode("utf-8"), raw)
        self.assertFalse(Path(str(self.capture_db) + "-journal").exists())


class CaptureForgetTests(CaptureForgetCase):
    def test_forget_erases_sealed_unfinished_faulted_and_never_admitted_captures(self):
        self.populate_capture()
        _action, ref = self.fi_proposal(fi_value(closing="TEST_ONLY admitted farewell"), nonce="fi.admitted")
        self.assertEqual(self.fi_store().apply(ref.proposal_ref_id).outcome, canonical_store.ACCEPTED)
        self.assertEqual(self.capture_counts(), {"fi_capture_session": 3, "fi_capture_turn": 6,
                                                 "fi_capture_fault": 1, "fi_conversation_evidence": 1})
        result = self.l18(auth := self.begin())
        self.assertEqual((result["status"], result["deleted"], result["captureSessionsErased"]), ("COMPLETE", 1, 3))
        self.assertEqual(self.privacy.complete(auth.authorization_ref_id, auth.execution_nonce).verification_status,
                         "COMPLETE")
        self.assert_capture_erased(SEALED_TEXT, UNFINISHED_TEXT, FAULTED_TEXT, "TEST_ONLY sealed reply")
        self.assertIsNone(self.fi_store().get_active(*MA.FIRST_INTERACTION_IDENTITY))
        self.assertIsNotNone(self.store().get_active(TEST_CLASS, TEST_NAMESPACE, TEST_KEY))   # codename kept
        self.assertTrue(self.privacy.is_held(*MA.FIRST_INTERACTION_IDENTITY))

    def test_missing_capture_database_is_not_created(self):
        result = self.l18(auth := self.begin())
        self.assertEqual((result["status"], result["captureSessionsErased"]), ("COMPLETE", 0))
        self.assertFalse(self.capture_db.exists())
        self.assertEqual(self.privacy.complete(auth.authorization_ref_id, auth.execution_nonce).verification_status,
                         "COMPLETE")

    def test_unauthorized_erasure_is_refused_and_capture_kept(self):
        sessions = self.populate_capture()
        before = self.capture_counts()
        owner = memory_v2.L18V2PrivacyErasureOwner(self.db, self.privacy, capture_evidence_path=self.capture_db)
        with self.assertRaisesRegex(PermissionError, "PRIVACY_ERASURE_NOT_AUTHORIZED"):
            owner.erase_authorized("auth.missing", "nonce.missing")
        auth = self.begin()
        with self.assertRaisesRegex(PermissionError, "PRIVACY_ERASURE_NOT_AUTHORIZED"):
            owner.erase_authorized(auth.authorization_ref_id, "nonce.wrong")
        self.assertEqual(self.capture_counts(), before)
        self.assertIsNotNone(self.capture.sealed_transcript(sessions["sealed"]))

    def test_other_identity_forget_leaves_capture_untouched(self):
        sessions = self.populate_capture()
        before = self.capture_counts()
        result = self.l18(auth := self.begin((TEST_CLASS, TEST_NAMESPACE, TEST_KEY)))
        self.assertEqual(result["status"], "COMPLETE")
        self.assertNotIn("captureSessionsErased", result)
        self.assertEqual(self.privacy.complete(auth.authorization_ref_id, auth.execution_nonce).verification_status,
                         "COMPLETE")
        self.assertEqual(self.capture_counts(), before)
        self.assertIsNotNone(self.capture.sealed_transcript(sessions["sealed"]))
        self.assertIsNone(self.store().get_active(TEST_CLASS, TEST_NAMESPACE, TEST_KEY))

    def test_without_capture_path_the_existing_result_is_unchanged(self):
        self.populate_capture()
        result = self.l18(self.begin(), capture_path=None)
        self.assertEqual(set(result), {"owner", "status", "deleted"})
        self.assertEqual(self.capture_counts()["fi_capture_session"], 3)        # not configured: not touched

    def test_capture_erasure_failure_blocks_completion_and_retry_finishes(self):
        self.populate_capture()
        before = self.capture_counts()
        conn = sqlite3.connect(self.capture_db)
        try:   # a TEST-only obstacle that fails the last DELETE, after the others already ran in the transaction
            conn.execute("CREATE TRIGGER test_only_block_session_delete BEFORE DELETE ON fi_capture_session "
                         "BEGIN SELECT RAISE(ABORT,'TEST_ONLY injected capture erasure failure'); END")
            conn.commit()
        finally:
            conn.close()
        auth = self.begin()
        with self.assertRaisesRegex(sqlite3.DatabaseError, "TEST_ONLY injected"):
            self.l18(auth)
        self.assertEqual(self.capture_counts(), before)                          # rolled back, nothing half-erased
        with self.assertRaisesRegex(privacy.PrivacyError, "erasure is incomplete"):
            self.privacy.complete(auth.authorization_ref_id, auth.execution_nonce)
        self.assertTrue(self.privacy.is_held(*MA.FIRST_INTERACTION_IDENTITY))
        conn = sqlite3.connect(self.capture_db)
        try:
            conn.execute("DROP TRIGGER test_only_block_session_delete")
            conn.commit()
        finally:
            conn.close()
        result = self.l18(auth)                                                  # retry, same authorization
        self.assertEqual((result["status"], result["captureSessionsErased"]), ("COMPLETE", 3))
        self.assertEqual(self.privacy.complete(auth.authorization_ref_id, auth.execution_nonce).verification_status,
                         "COMPLETE")
        self.assert_capture_erased(SEALED_TEXT, UNFINISHED_TEXT, FAULTED_TEXT)

    def test_incomplete_capture_trigger_set_fails_closed(self):
        self.populate_capture()
        conn = sqlite3.connect(self.capture_db)
        try:
            conn.execute("DROP TRIGGER fi_capture_turn_no_delete")
            conn.commit()
        finally:
            conn.close()
        auth = self.begin()
        with self.assertRaisesRegex(RuntimeError, "trigger set is incomplete"):
            self.l18(auth)
        self.assertEqual(self.capture_counts()["fi_capture_turn"], 6)
        with self.assertRaises(privacy.PrivacyError):
            self.privacy.complete(auth.authorization_ref_id, auth.execution_nonce)

    def test_capture_after_forget_is_still_append_only(self):
        self.populate_capture()
        self.l18(self.begin())
        session = self.capture.open_session()                                   # the store keeps working
        self.capture.record_exchange(session, owner_text="TEST_ONLY later", owner_at=self.stamp(10),
                                     lilith_text="TEST_ONLY later reply", lilith_at=self.stamp(11))
        conn = sqlite3.connect(self.capture_db)
        try:
            with self.assertRaises(sqlite3.DatabaseError):
                conn.execute("DELETE FROM fi_capture_turn")
        finally:
            conn.close()


if __name__ == "__main__":
    import unittest

    unittest.main()
