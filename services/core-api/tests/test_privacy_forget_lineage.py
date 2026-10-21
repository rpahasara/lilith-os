"""Privacy FORGET over L04 V2: rejected and precondition-failed admissions are erased with their identity.

Before this fix the L04 owner erased admissions only along the accepted revision lineage. A rejected or
precondition-failed admission of the same identity kept its foreign key to learning_proposal_ref, so the L18 V2 owner
failed ("FOREIGN KEY constraint failed"), Privacy completion was refused, and the plaintext intent/proposal values
stayed behind a held identity. Synthetic temporary databases only; the real Privacy Governance store and both erasure
owners run unchanged apart from the L04 fix.
"""

from __future__ import annotations

import sqlite3
import unittest

from test_canonical_runtime import (  # noqa: F401  (also puts the Core API on sys.path)
    TEST_CAPABILITY,
    TEST_CLASS,
    TEST_KEY,
    TEST_NAMESPACE,
    TEST_SCHEMA,
    CanonicalRuntimeCase,
    digest,
    stamp_text,
)

from lilith_memory import canonical_contracts as contracts
from lilith_memory import canonical_store
from lilith_memory import learning_v2
from lilith_memory import memory_v2
from lilith_memory import privacy_governance as privacy
from lilith_memory import slice15b2a_migration

OTHER_KEY = "codename-other"
TEST_ONLY_PRIVACY_SECRET = b"TEST_ONLY forget-lineage privacy secret (32+ bytes)"


class ForgetLineageCase(CanonicalRuntimeCase):
    def setUp(self) -> None:
        super().setUp()
        path = self.root / "privacy.test.db"
        slice15b2a_migration.migrate_privacy(path, applied_at=stamp_text(3))
        self.privacy = privacy.PrivacyGovernanceStore(path, TEST_ONLY_PRIVACY_SECRET, self.actor,
                                                      now_fn=lambda: self.now)
        self.registry = memory_v2.CanonicalTupleRegistry((
            self.registry_policy,
            memory_v2.MemoryTuplePolicyV1(TEST_CLASS, TEST_NAMESPACE, OTHER_KEY, TEST_SCHEMA, TEST_CAPABILITY,
                                          read_allowed=True, write_allowed=True),
        ))

    def keyed_action(self, value: str, key: str):
        encoded, payload = learning_v2.normalize_project_codename({"codename": value})
        return contracts.FrozenMemoryActionV1(
            schema_version=1, actor_ref_id=self.actor.ACTOR.actor_ref_id, operation=contracts.CREATE,
            memory_class=TEST_CLASS, subject_namespace=TEST_NAMESPACE, subject_key=key, value_schema=TEST_SCHEMA,
            payload_digest=payload, expected_active_revision_id=None, restore_revision_id=None,
            purpose=contracts.LONG_TERM_PERSONAL_PROJECT_RECALL), encoded

    def apply(self, value: str, *, key: str = TEST_KEY, nonce: str, **store_overrides):
        action, encoded = self.keyed_action(value, key)
        _proposal, ref, _consent = self.proposal(action, encoded, nonce=nonce)
        store = self.store(memory_registry=self.registry, containment_ready=lambda identity: True,
                           **store_overrides)
        return store.apply(ref.proposal_ref_id), ref

    def forget(self, key: str = TEST_KEY):
        identity = (TEST_CLASS, TEST_NAMESPACE, key)
        active = self.store(memory_registry=self.registry).get_active(*identity)
        action = contracts.FrozenMemoryActionV1(
            schema_version=1, actor_ref_id=self.actor.ACTOR.actor_ref_id, operation=contracts.FORGET,
            memory_class=TEST_CLASS, subject_namespace=TEST_NAMESPACE, subject_key=key, value_schema=None,
            payload_digest="0" * 64, expected_active_revision_id=None, restore_revision_id=None,
            purpose=contracts.LONG_TERM_PERSONAL_PROJECT_RECALL)
        evidence = self.actor.issue(action=action, request_digest=digest("forget:" + key), nonce="forget." + key)
        _request, auth, _suppression = self.privacy.begin_forget(
            action=action, actor_evidence_ref_id=evidence.actor_evidence_ref_id, intent_ref_id="intent.forget." + key,
            memory_item_id=None if active is None else active["memory_item_id"],
            resource_owners=("L04", "L18_V2"), confirmation_event_ref="confirm.forget." + key)
        l04 = memory_v2.L04PrivacyErasureOwner(self.db, self.privacy).erase_authorized(
            auth.authorization_ref_id, auth.execution_nonce)
        l18 = memory_v2.L18V2PrivacyErasureOwner(self.db, self.privacy).erase_authorized(
            auth.authorization_ref_id, auth.execution_nonce)
        receipt = self.privacy.complete(auth.authorization_ref_id, auth.execution_nonce)
        return l04, l18, receipt

    def rows(self, sql: str, *params):
        conn = sqlite3.connect(self.db)
        try:
            return conn.execute(sql, params).fetchall()
        finally:
            conn.close()

    def identity_rows(self, key: str = TEST_KEY) -> dict:
        params = (TEST_CLASS, TEST_NAMESPACE, key)
        return {
            "memory_item": self.rows("SELECT COUNT(*) FROM memory_item WHERE memory_class=? AND "
                                     "subject_namespace=? AND subject_key=?", *params)[0][0],
            "learning_memory_intent_v2": self.rows("SELECT COUNT(*) FROM learning_memory_intent_v2 WHERE "
                                                   "memory_class=? AND subject_namespace=? AND subject_key=?",
                                                   *params)[0][0],
            "learning_proposal_v2": self.rows("SELECT COUNT(*) FROM learning_proposal_v2 WHERE memory_class=? AND "
                                              "subject_namespace=? AND subject_key=?", *params)[0][0],
        }

    def assert_clean(self):
        self.assertEqual(self.rows("PRAGMA foreign_key_check"), [])
        self.assertEqual(self.rows("PRAGMA integrity_check"), [("ok",)])


class ForgetLineageTests(ForgetLineageCase):
    def test_precondition_failed_duplicate_is_erased_and_forget_completes(self):
        first, _ref1 = self.apply("TEST-ONLY-FIRST", nonce="first")
        duplicate, ref2 = self.apply("TEST-ONLY-DUPLICATE", nonce="duplicate")
        self.assertEqual(first.outcome, canonical_store.ACCEPTED)
        self.assertEqual((duplicate.outcome, duplicate.failure_code),
                         (canonical_store.PRECONDITION_FAILED, "MEMORY_ALREADY_EXISTS"))
        l04, l18, receipt = self.forget()
        self.assertEqual((l04["status"], l04["deleted"], l18["status"]), ("COMPLETE", 1, "COMPLETE"))
        self.assertEqual(receipt.verification_status, "COMPLETE")
        self.assertEqual(self.identity_rows(), {"memory_item": 0, "learning_memory_intent_v2": 0,
                                                "learning_proposal_v2": 0})
        self.assertEqual(self.rows("SELECT COUNT(*) FROM memory_admission"), [(0,)])
        self.assertEqual(self.rows("SELECT COUNT(*) FROM learning_proposal_ref WHERE proposal_ref_id=?",
                                   ref2.proposal_ref_id), [(0,)])
        self.assert_clean()
        raw = self.db.read_bytes()
        for value in (b"TEST-ONLY-FIRST", b"TEST-ONLY-DUPLICATE"):
            self.assertNotIn(value, raw)
        self.assertTrue(self.privacy.is_held(TEST_CLASS, TEST_NAMESPACE, TEST_KEY))   # monotonic suppression

    def test_rejected_only_identity_is_erased(self):
        rejected, _ref = self.apply("TEST-ONLY-REJECTED", nonce="rejected",
                                    capability_provider=lambda capability: False)
        self.assertEqual((rejected.outcome, rejected.failure_code), (canonical_store.REJECTED, "CAPABILITY_INACTIVE"))
        self.assertEqual(self.identity_rows()["memory_item"], 0)
        l04, l18, receipt = self.forget()
        self.assertEqual((l04["status"], l04["deleted"], l18["status"]), ("COMPLETE", 0, "COMPLETE"))
        self.assertEqual(receipt.verification_status, "COMPLETE")
        self.assertEqual(self.rows("SELECT COUNT(*) FROM memory_admission"), [(0,)])
        self.assertEqual(self.identity_rows(), {"memory_item": 0, "learning_memory_intent_v2": 0,
                                                "learning_proposal_v2": 0})
        self.assert_clean()
        self.assertNotIn(b"TEST-ONLY-REJECTED", self.db.read_bytes())

    def test_other_identities_are_untouched(self):
        self.apply("TEST-ONLY-MINE", nonce="mine")
        self.apply("TEST-ONLY-MINE-DUP", nonce="mine-dup")
        other, other_ref = self.apply("TEST-ONLY-OTHER", key=OTHER_KEY, nonce="other",
                                      capability_provider=lambda capability: False)
        other_ok, _ = self.apply("TEST-ONLY-OTHER-OK", key=OTHER_KEY, nonce="other-ok")
        self.assertEqual((other.outcome, other_ok.outcome), (canonical_store.REJECTED, canonical_store.ACCEPTED))
        before = self.identity_rows(OTHER_KEY)
        self.forget()
        self.assertEqual(self.identity_rows(OTHER_KEY), before)
        self.assertEqual(self.rows("SELECT outcome FROM memory_admission WHERE proposal_ref_id=?",
                                   other_ref.proposal_ref_id), [("REJECTED",)])
        self.assertEqual(self.rows("SELECT COUNT(*) FROM memory_admission"), [(2,)])   # the other identity's two
        self.assert_clean()

    def test_identity_with_nothing_stored_keeps_the_unchanged_result(self):
        l04, l18, receipt = self.forget()
        self.assertEqual(l04, {"owner": "L04", "status": "COMPLETE", "deleted": 0, "proposalIds": ()})
        self.assertEqual((l18["status"], receipt.verification_status), ("COMPLETE", "COMPLETE"))


if __name__ == "__main__":
    unittest.main()
