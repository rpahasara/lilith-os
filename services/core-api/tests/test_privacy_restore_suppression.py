"""F9-C restore suppression over L04 + L18 V2: a restored pre-FORGET cognitive database must not make suppressed First
Interaction rows or plaintext available again, and the verifier must never report ready while any remain.

Privacy (an external store) is the authority: its suppression selectors, not the restored cognitive database, decide
what is erased. Cleanup is identity-scoped (the First Interaction family CHECKs its single identity); unrelated
identities and codename memories stay. Synthetic temporary databases only; the Hermes owner uses a mock executor.
"""

from __future__ import annotations

import shutil
import sqlite3
import tempfile
import unittest
from pathlib import Path

from test_canonical_runtime import TEST_CLASS, TEST_KEY, TEST_NAMESPACE, digest  # noqa: F401  (Core API on path)
from test_first_interaction_l04 import fi_value
from test_privacy_forget_runner import FAREWELL, FI, HERMES, RunnerCase
from test_privacy_hermes_owner_v2 import SECRET, HermesOwnerCase

from lilith_memory import canonical_contracts as contracts
from lilith_memory import canonical_store
from lilith_memory import memory_v2
from lilith_memory import privacy_forget_runner as R
from lilith_memory import privacy_governance as privacy

CODENAME = (TEST_CLASS, TEST_NAMESPACE, TEST_KEY)


class SkippingOwner:
    """Wraps an owner; its restore erasure can raise (a crash) or silently do nothing (a defective owner)."""

    def __init__(self, owner, *, fail_times: int = 0, skip: bool = False):
        self.inner, self.fail_times, self.skip, self.calls = owner, fail_times, skip, 0

    def __getattr__(self, name):
        return getattr(self.inner, name)

    def erase_restore_suppressed(self, identity, privacy_store):
        self.calls += 1
        if self.calls <= self.fail_times:
            raise RuntimeError("TEST_ONLY crash during restore cleanup")
        if not self.skip:
            self.inner.erase_restore_suppressed(identity, privacy_store)


class RestoreCase(RunnerCase):
    def setUp(self) -> None:
        super().setUp()
        self.pre_forget = self.root / "cognitive.pre-forget.copy.db"
        shutil.copyfile(self.db, self.pre_forget)

    def l04(self, store=None):
        return memory_v2.L04PrivacyErasureOwner(self.db, store or self.privacy)

    def l18(self, store=None):
        return memory_v2.L18V2PrivacyErasureOwner(self.db, store or self.privacy)

    def verify(self, l04=None, l18=None, store=None):
        store = store or self.privacy
        return privacy.RestoreSuppressionVerifier(store, l04 or self.l04(store), l18 or self.l18(store)).verify_and_apply()

    def restore(self, copy=None):
        shutil.copyfile(copy or self.pre_forget, self.db)

    def forget_fi(self):
        self.assertEqual(self.forget().status, R.COMPLETE)

    def codename_state(self):
        return (self.count("SELECT COUNT(*) FROM memory_item WHERE memory_class=?", TEST_CLASS),
                self.l18().restore_residue(CODENAME), self.l04().restore_residue(CODENAME))

    def fi_present(self) -> bool:
        return self.fi_rows()["learning_fi_proposal_v1"] > 0 or FAREWELL in self.db.read_bytes()

    def assert_ready(self, verification, matched=None):
        self.assertEqual((verification.ready_to_serve, verification.failure_code), (True, None), verification)
        if matched is not None:
            self.assertEqual(verification.matched_identities, matched)

    def assert_refused(self, verification, code=None):
        self.assertFalse(verification.ready_to_serve, verification)
        if code is not None:
            self.assertEqual(verification.failure_code, code)

    def assert_fi_suppressed(self):
        self.assertEqual(set(self.fi_rows().values()), {0})
        self.assertNotIn(FAREWELL, self.db.read_bytes())
        self.assertEqual((self.l04().restore_residue(FI), self.l18().restore_residue(FI)), (0, 0))


class GapReproductionTests(RestoreCase):
    def test_b9eb32c_verifier_reported_ready_with_l18_plaintext_and_the_fix_does_not(self):
        self.forget_fi()
        self.restore()
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        old_module, old_store = HermesOwnerCase.frozen_store(self, Path(tmp.name))
        old = old_module.RestoreSuppressionVerifier(old_store, self.l04(old_store)).verify_and_apply()
        self.assertTrue(old.ready_to_serve)                                       # the reproduced defect ...
        self.assertTrue(self.fi_present())                                        # ... with plaintext still there
        self.assertEqual(self.fi_rows()["memory_item"], 0)
        self.assert_ready(self.verify(), matched=1)
        self.assert_fi_suppressed()

    def test_the_verifier_cannot_be_built_without_the_l18_owner(self):
        with self.assertRaises(TypeError):
            privacy.RestoreSuppressionVerifier(self.privacy, self.l04())
        with self.assertRaises(privacy.PrivacyError):
            privacy.RestoreSuppressionVerifier(self.privacy, self.l04(), None)


class ReadinessTests(RestoreCase):
    def test_ready_only_after_every_row_of_the_suppressed_identity_is_gone(self):
        codename = self.codename_state()
        self.forget_fi()
        self.restore()
        self.assertTrue(self.fi_present())
        self.assertGreater(self.l18().restore_residue(FI), 0)
        self.assert_ready(self.verify(), matched=1)
        self.assert_fi_suppressed()
        self.assertEqual(self.codename_state(), codename)
        self.assertTrue(self.privacy.is_held(*FI))

    def test_nothing_suppressed_means_nothing_erased(self):
        before = (self.fi_rows(), self.codename_state())
        self.restore()
        self.assert_ready(self.verify(), matched=0)
        self.assertEqual((self.fi_rows(), self.codename_state()), before)
        self.assertIn(FAREWELL, self.db.read_bytes())

    def test_a_codename_forget_suppresses_only_that_identity(self):
        fi_before = self.fi_rows()
        action = contracts.FrozenMemoryActionV1(
            schema_version=1, actor_ref_id=self.actor.ACTOR.actor_ref_id, operation=contracts.FORGET,
            memory_class=TEST_CLASS, subject_namespace=TEST_NAMESPACE, subject_key=TEST_KEY, value_schema=None,
            payload_digest="0" * 64, expected_active_revision_id=None, restore_revision_id=None,
            purpose=contracts.LONG_TERM_PERSONAL_PROJECT_RECALL)
        evidence = self.actor.issue(action=action, request_digest=digest("forget:codename"), nonce="forget.codename")
        _r, auth, _s = self.privacy.begin_forget(action=action, actor_evidence_ref_id=evidence.actor_evidence_ref_id,
                                                 intent_ref_id="intent.codename", memory_item_id=None,
                                                 resource_owners=("L04", "L18_V2"), confirmation_event_ref="c.code")
        for owner in (self.l04(), self.l18()):
            owner.erase_authorized(auth.authorization_ref_id, auth.execution_nonce)
        self.privacy.complete(auth.authorization_ref_id, auth.execution_nonce)
        self.restore()
        self.assertEqual(self.codename_state()[0], 1)
        self.assert_ready(self.verify(), matched=1)
        self.assertEqual(self.codename_state(), (0, 0, 0))
        self.assertEqual(self.fi_rows(), fi_before)                               # First Interaction untouched
        self.assertIn(FAREWELL, self.db.read_bytes())

    def test_repeat_restores_and_reruns_are_idempotent(self):
        self.forget_fi()
        for _ in range(2):
            self.restore()
            self.assert_ready(self.verify(), matched=1)
            self.assert_fi_suppressed()
            self.assert_ready(self.verify(), matched=0)                          # nothing left to match
        self.assertEqual(self.codename_state()[0], 1)

    def test_a_restore_during_an_in_flight_forget(self):
        self.assert_incomplete(self.forget(self.runner(self.owners(**{HERMES: self.hermes(None)}))))
        self.restore()                                                           # copy predates the FORGET
        self.assert_ready(self.verify(), matched=1)
        self.assert_fi_suppressed()
        self.assertEqual(self.runner().resume().status, R.COMPLETE)
        self.assert_ready(self.verify(), matched=0)

    def test_a_rejected_admission_in_the_restored_copy_is_erased_too(self):
        _action, ref = self.fi_proposal(fi_value(closing="TEST_ONLY second first"), nonce="fi.dup")
        duplicate = self.fi_store().apply(ref.proposal_ref_id)
        self.assertEqual(duplicate.failure_code, "MEMORY_ALREADY_EXISTS")       # an admission with no revision
        shutil.copyfile(self.db, self.pre_forget)
        self.forget_fi()
        self.restore()
        self.assertEqual(self.l04().restore_residue(FI), 3)                      # item + 2 identity admissions
        self.assert_ready(self.verify(), matched=1)
        self.assert_fi_suppressed()
        self.assertNotIn(b"TEST_ONLY second first", self.db.read_bytes())

    def test_listing_and_residue_are_read_only_and_exact(self):
        before = self.db.read_bytes()
        self.assertIn(FI, self.l18().list_identities())
        self.assertIn(CODENAME, self.l18().list_identities())
        counts = self.fi_rows()
        family = sum(v for k, v in counts.items() if k != "memory_item") + 1          # + its proposal reference
        keyed = counts["learning_fi_intent_v1"] + counts["learning_fi_candidate_v1"] + counts["learning_fi_proposal_v1"]
        self.assertEqual(self.l18().restore_residue(FI), keyed + family)
        self.assertEqual(self.l04().restore_residue(FI), 2)                      # item + its admission
        self.assertEqual(self.db.read_bytes(), before)

    def test_owner_restore_paths_refuse_an_unsuppressed_identity(self):
        for owner in (self.l04(), self.l18()):
            with self.subTest(owner=owner.OWNER), self.assertRaisesRegex(PermissionError, "NOT_AUTHORIZED"):
                owner.erase_restore_suppressed(FI, self.privacy)
        self.assertTrue(self.fi_present())


class CrashAndPartialCleanupTests(RestoreCase):
    def setUp(self) -> None:
        super().setUp()
        self.forget_fi()
        self.restore()

    def test_crash_between_l04_and_l18_then_rerun(self):
        l18 = SkippingOwner(self.l18(), fail_times=1)
        self.assert_refused(self.verify(l18=l18), "RESTORE_VERIFICATION_FAILED")
        self.assertEqual(self.fi_rows()["memory_item"], 0)                       # L04 done, L18 not
        self.assertTrue(self.fi_present())
        self.assert_ready(self.verify(l18=l18), matched=1)
        self.assert_fi_suppressed()

    def test_crash_before_any_cleanup_then_rerun(self):
        l04 = SkippingOwner(self.l04(), fail_times=1)
        self.assert_refused(self.verify(l04=l04), "RESTORE_VERIFICATION_FAILED")
        self.assertEqual(self.fi_rows()["memory_item"], 1)
        self.assert_ready(self.verify(l04=l04), matched=1)
        self.assert_fi_suppressed()

    def test_an_l18_owner_that_silently_skips_cleanup_is_not_ready(self):
        self.assert_refused(self.verify(l18=SkippingOwner(self.l18(), skip=True)), "SUPPRESSION_INCOMPLETE")
        self.assertTrue(self.fi_present())

    def test_the_independent_residue_count_catches_a_listing_defect(self):
        """An L18 owner whose listing misses the identity and whose erase does nothing: re-listing finds nothing, so
        only the verifier's per-identity residue count stands between this and a false ready."""
        blind = SkippingOwner(self.l18(), skip=True)
        blind.list_identities = lambda: ()
        self.assert_refused(self.verify(l18=blind), "SUPPRESSION_INCOMPLETE")
        self.assertTrue(self.fi_present())

    def test_the_re_list_catches_a_residue_defect(self):
        """The mirror case: residue reports 0 and the erase does nothing; only re-listing catches it."""
        lying = SkippingOwner(self.l18(), skip=True)
        lying.restore_residue = lambda identity: 0
        self.assert_refused(self.verify(l18=lying), "SUPPRESSION_INCOMPLETE")
        self.assertTrue(self.fi_present())

    def test_an_l04_owner_that_silently_skips_cleanup_is_not_ready(self):
        self.assert_refused(self.verify(l04=SkippingOwner(self.l04(), skip=True)))
        self.assertEqual(self.fi_rows()["memory_item"], 1)


class CorruptedRestoreTests(RestoreCase):
    def setUp(self) -> None:
        super().setUp()
        self.forget_fi()

    def corrupt_copy(self, sql_statements):
        copy = self.root / "cognitive.corrupt.copy.db"
        shutil.copyfile(self.pre_forget, copy)
        conn = sqlite3.connect(copy)
        try:
            conn.execute("PRAGMA foreign_keys=OFF")
            for statement in sql_statements:
                conn.execute(statement)
            conn.commit()
        finally:
            conn.close()
        return copy

    def test_garbage_truncated_and_missing_files_fail_closed(self):
        data = self.pre_forget.read_bytes()
        for label, content in (("garbage", b"TEST_ONLY not a database" * 100), ("truncated", data[: len(data) // 3])):
            with self.subTest(label):
                self.db.write_bytes(content)
                self.assert_refused(self.verify(), "RESTORE_VERIFICATION_FAILED")
        self.db.unlink()
        self.assert_refused(self.verify(), "RESTORE_VERIFICATION_FAILED")

    def test_a_copy_with_a_missing_immutability_trigger_stays_refused(self):
        self.restore(self.corrupt_copy(["DROP TRIGGER learning_fi_proposal_v1_no_delete"]))
        for _ in range(2):
            self.assert_refused(self.verify(), "RESTORE_VERIFICATION_FAILED")
        self.assertTrue(self.fi_present())

    def test_a_copy_with_broken_lineage_stays_refused(self):
        self.restore(self.corrupt_copy(["DROP TRIGGER learning_fi_candidate_v1_no_delete",
                                        "DELETE FROM learning_fi_candidate_v1",
                                        "CREATE TRIGGER learning_fi_candidate_v1_no_delete BEFORE DELETE ON "
                                        "learning_fi_candidate_v1 BEGIN SELECT RAISE(ABORT,'First Interaction L18 "
                                        "deletion requires Privacy authority'); END"]))
        self.assert_refused(self.verify())
        self.assertTrue(self.fi_present())

    def test_a_pre_first_interaction_schema_copy_is_ready_and_keeps_the_codename(self):
        older = self.root / "pre-fm02.db"                                         # the migration's own backup
        self.assertTrue(older.is_file())
        self.restore(older)
        self.assert_ready(self.verify(), matched=0)
        self.assertEqual(self.codename_state()[0], 1)
        self.assertNotIn(FAREWELL, self.db.read_bytes())


class PrivacyRecordTests(RestoreCase):
    def setUp(self) -> None:
        super().setUp()
        self.forget_fi()
        self.restore()

    def tamper_privacy(self, *statements):
        conn = sqlite3.connect(self.privacy_db)
        try:
            conn.execute("PRAGMA foreign_keys=OFF")
            for statement in statements:
                conn.execute(statement)
            conn.commit()
        finally:
            conn.close()

    def drop_triggers(self, table):
        conn = sqlite3.connect(self.privacy_db)
        try:
            return [str(r[0]) for r in conn.execute(
                "SELECT 'DROP TRIGGER \"' || name || '\"' FROM sqlite_master WHERE type='trigger' AND tbl_name=?",
                (table,))]
        finally:
            conn.close()

    def test_missing_or_unprovisioned_privacy_store_fails_closed(self):
        moved = self.privacy_db.with_suffix(".moved")
        self.privacy_db.rename(moved)
        self.assert_refused(self.verify(), "PRIVACY_RECORDS_UNVERIFIED")
        sqlite3.connect(self.privacy_db).close()                                  # an empty database in its place
        self.assert_refused(self.verify(), "PRIVACY_RECORDS_UNVERIFIED")
        self.privacy_db.unlink()
        moved.rename(self.privacy_db)
        self.assertTrue(self.fi_present())
        self.assert_ready(self.verify(), matched=1)

    def test_a_wrong_privacy_secret_cannot_make_suppression_disappear(self):
        other = privacy.PrivacyGovernanceStore(self.privacy_db, b"TEST_ONLY a different 32+ byte secret!!",
                                               self.actor)
        self.assertFalse(other.suppression_matches(FI))                           # its selectors match nothing
        self.assert_refused(self.verify(store=other), "PRIVACY_RECORDS_UNVERIFIED")
        self.assertTrue(self.fi_present())

    def test_tampered_receipt_or_deleted_selector_fails_closed(self):
        for table, statement in (
                ("privacy_completion_receipt", "UPDATE privacy_completion_receipt SET receipt_fingerprint='"
                 + "0" * 64 + "'"),
                ("privacy_restore_suppression_manifest", "DELETE FROM privacy_restore_suppression_manifest")):
            with self.subTest(table):
                backup = self.privacy_db.read_bytes()
                self.tamper_privacy(*self.drop_triggers(table), statement)
                self.assert_refused(self.verify(), "PRIVACY_RECORDS_UNVERIFIED")
                self.privacy_db.write_bytes(backup)
        self.assertTrue(self.fi_present())
        self.assert_ready(self.verify(), matched=1)


class InFlightPrivacyRecordTests(RestoreCase):
    def test_in_flight_authorizations_must_verify_too(self):
        self.assert_incomplete(self.forget(self.runner(self.owners(**{HERMES: self.hermes(None)}))))
        self.assertEqual(self.prows("SELECT COUNT(*) FROM privacy_completion_receipt"), [(0,)])   # no receipt yet
        self.assertEqual(self.privacy.verify_suppression_integrity(), 1)
        other = privacy.PrivacyGovernanceStore(self.privacy_db, b"TEST_ONLY a different 32+ byte secret!!",
                                               self.actor)
        with self.assertRaisesRegex(privacy.PrivacyError, "in-flight erasure authorization does not verify"):
            other.verify_suppression_integrity()
        self.restore()
        self.assert_refused(self.verify(store=other), "PRIVACY_RECORDS_UNVERIFIED")
        self.assert_ready(self.verify(), matched=1)


if __name__ == "__main__":
    unittest.main()
