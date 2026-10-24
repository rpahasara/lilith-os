"""F9-C restore-suppression pre-serve gate, exercised through the real memory read path.

Every memory-serving component (CanonicalMemoryReadFacade, CanonicalMemoryStoreV2, LearningV2Store) is given the
gated privacy_hold_resolver built by ``memory_v2.restore_gated_hold_resolver``. The gate re-reads Privacy and the
cognitive database on every call (no readiness flag), refuses explicitly (RestoreSuppressionNotReady) and never
erases; cleanup stays in the separate maintenance step ``RestoreSuppressionVerifier.verify_and_apply``.
Synthetic temporary databases only.
"""

from __future__ import annotations

import inspect
import shutil
import sqlite3
import unittest
from unittest import mock

from test_canonical_runtime import TEST_CLASS, TEST_KEY, TEST_NAMESPACE, stamp_text  # noqa: F401
from test_first_interaction_l04 import FirstInteractionCase
from test_privacy_forget_runner import FAREWELL, FI, HERMES, CountingOwner
from test_privacy_hermes_owner_v2 import SECRET
from test_privacy_restore_suppression import CODENAME, RestoreCase, SkippingOwner

from lilith_memory import canonical_contracts as contracts
from lilith_memory import learning_v2
from lilith_memory import memory_v2
from lilith_memory import privacy_forget_runner as R
from lilith_memory import privacy_governance as privacy
from lilith_memory import privacy_schema_v2 as V2
from lilith_memory import slice15b2a_migration

NOT_READY = privacy.RestoreSuppressionNotReady


class GatedPathMixin:
    """The DEV memory read path, assembled exactly as a serving runtime must: one gated resolver for every component."""

    def gated(self, store=None):
        return memory_v2.restore_gated_hold_resolver(store or self.privacy, self.db)

    def serving(self, resolver=None):
        resolver = resolver or self.gated()
        self.learning.privacy_hold_resolver = resolver
        store = self.fi_store(privacy_hold_resolver=resolver)
        facade = memory_v2.CanonicalMemoryReadFacade(
            store, registry=self.registry, consent_store=self.consent, privacy_hold_resolver=resolver,
            actor_resolver=lambda actor: actor == self.actor.ACTOR)
        return store, facade

    def read(self, identity, facade=None):
        memory_class, namespace, key = identity
        return (facade or self.serving()[1]).read_exact(actor=self.actor.ACTOR, memory_class=memory_class,
                                                        subject_namespace=namespace, subject_key=key)

    def assert_not_ready(self, code, identity=CODENAME, facade=None):
        with self.assertRaises(NOT_READY) as caught:
            self.read(identity, facade)
        self.assertEqual(caught.exception.code, code)


class CleanStartupTests(GatedPathMixin, FirstInteractionCase):
    def setUp(self) -> None:
        super().setUp()
        self.migrate_fi()
        self.enable_fi()
        self.privacy_db = self.root / "privacy.test.db"
        slice15b2a_migration.migrate_privacy(self.privacy_db, applied_at=stamp_text(3))
        V2.upgrade_privacy_v1_to_v2(self.privacy_db, applied_at=stamp_text(4))
        V2.provision_hermes_owner_floor(self.privacy_db, deployment_environment=V2.DEV_SYNTHETIC)
        self.privacy = privacy.PrivacyGovernanceStore(self.privacy_db, SECRET, self.actor, now_fn=lambda: self.now)

    def test_a_clean_database_is_ready_and_serves(self):
        self.assertTrue(self.gated()._gate.check().ready_to_serve)
        self.assertIsNone(self.read(CODENAME))
        self.assertIsNone(self.read(FI))
        self.create()                                                             # a codename written ...
        self.assertIn("SYNTH-ALPHA", self.read(CODENAME)["normalized_value_json"])  # ... and served, gated


class GateTests(GatedPathMixin, RestoreCase):
    def test_serving_before_any_forget(self):
        self.assertIn(FAREWELL.decode(), self.read(FI)["normalized_value_json"])
        self.assertIn("SYNTH-ALPHA", self.read(CODENAME)["normalized_value_json"])

    def test_after_a_completed_forget_reads_resume_without_maintenance(self):
        self.forget_fi()
        self.assertIsNone(self.read(FI))
        self.assertIn("SYNTH-ALPHA", self.read(CODENAME)["normalized_value_json"])

    def test_an_in_flight_forget_is_held_per_identity_not_a_global_refusal(self):
        self.assert_incomplete(self.forget(self.runner(self.owners(**{HERMES: self.hermes(None)}))))
        self.assertIsNone(self.read(FI))                                         # held
        self.assertIn("SYNTH-ALPHA", self.read(CODENAME)["normalized_value_json"])

    def test_content_still_under_an_active_hold_does_not_block_other_memories(self):
        """The FORGET stalls before any owner erased anything: the First Interaction rows still exist, but the ACTIVE
        hold covers them, so the gate stays ready and only that identity is refused (held)."""
        stalled = CountingOwner(self.owners()["L04"], fail_times=1)
        result = self.forget(self.runner(self.owners(L04=stalled)))
        self.assert_incomplete(result, "RuntimeError")
        self.assertTrue(self.fi_present())
        self.assertTrue(self.gated()._gate.check().ready_to_serve)
        self.assertIsNone(self.read(FI))
        self.assertIn("SYNTH-ALPHA", self.read(CODENAME)["normalized_value_json"])

    def test_restored_suppressed_data_blocks_all_memory_serving_until_maintenance(self):
        self.forget_fi()
        self.restore()
        store, facade = self.serving()
        for identity in (FI, CODENAME):
            self.assert_not_ready("SUPPRESSED_CONTENT_PRESENT", identity, facade)
        self.assert_ready(self.verify(), matched=1)                              # the separate maintenance step
        self.assertIsNone(self.read(FI))
        self.assertIn("SYNTH-ALPHA", self.read(CODENAME)["normalized_value_json"])
        self.assert_fi_suppressed()

    def test_a_blocked_write_leaves_no_durable_trace(self):
        self.forget_fi()
        self.restore()
        admissions = self.count("SELECT COUNT(*) FROM memory_admission")
        assessments = self.count("SELECT COUNT(*) FROM learning_assessment_v2")
        store, _facade = self.serving()
        action, encoded = self.action("SYNTH-BETA", operation=contracts.SUPERSEDE,
                                      expected=self.fi_store().get_active(*CODENAME)["revision_id"])
        with self.assertRaises(NOT_READY):
            self.proposal(action, encoded, nonce="gate.blocked")                 # the learning assess is gated
        self.assertEqual((self.count("SELECT COUNT(*) FROM memory_admission"),
                          self.count("SELECT COUNT(*) FROM learning_assessment_v2")), (admissions, assessments))

    def test_database_replacement_after_verification_is_refused_at_the_next_read(self):
        self.forget_fi()
        self.restore()
        self.assert_ready(self.verify(), matched=1)
        _store, facade = self.serving()
        self.assertIsNone(self.read(FI, facade))                                 # verified and serving ...
        self.restore()                                                           # ... then the file is replaced
        self.assert_not_ready("SUPPRESSED_CONTENT_PRESENT", CODENAME, facade)    # same facade: no stale flag
        self.assert_ready(self.verify(), matched=1)
        self.assertIsNotNone(self.read(CODENAME, facade))

    def test_a_replacement_between_the_check_and_the_read_is_not_served(self):
        self.forget_fi()
        store, facade = self.serving()
        real = store.get_active

        def swapped(*identity):
            row = real(*identity)
            self.restore()                                                       # replaced mid-read
            return row

        with mock.patch.object(store, "get_active", side_effect=swapped):
            with self.assertRaises(NOT_READY):
                self.read(CODENAME, facade)

    def test_missing_privacy_state_blocks_and_recovers(self):
        moved = self.privacy_db.with_suffix(".moved")
        self.privacy_db.rename(moved)
        _store, facade = self.serving()
        for identity in (FI, CODENAME):
            self.assert_not_ready("PRIVACY_RECORDS_UNVERIFIED", identity, facade)
        moved.rename(self.privacy_db)
        self.assertIsNotNone(self.read(CODENAME, facade))

    def test_a_wrong_secret_blocks_serving(self):
        self.forget_fi()
        other = privacy.PrivacyGovernanceStore(self.privacy_db, b"TEST_ONLY a different 32+ byte secret!!",
                                               self.actor)
        self.assertFalse(other.is_held(*FI))                                     # it would have served FI
        self.assert_not_ready("PRIVACY_RECORDS_UNVERIFIED", FI, self.serving(self.gated(other))[1])

    def test_tampered_suppression_blocks_serving(self):
        self.forget_fi()
        self.restore()
        conn = sqlite3.connect(self.privacy_db)
        try:
            conn.execute("PRAGMA foreign_keys=OFF")
            for (name,) in conn.execute("SELECT name FROM sqlite_master WHERE type='trigger' AND "
                                        "tbl_name='privacy_restore_suppression_manifest'").fetchall():
                conn.execute(f'DROP TRIGGER "{name}"')
            conn.execute("DELETE FROM privacy_restore_suppression_manifest")
            conn.commit()
        finally:
            conn.close()
        self.assertFalse(self.privacy.is_held(*FI))                              # Privacy alone would now serve FI
        self.assert_not_ready("PRIVACY_RECORDS_UNVERIFIED", FI)

    def test_interrupted_cleanup_keeps_serving_blocked_until_a_rerun_finishes(self):
        self.forget_fi()
        self.restore()
        l18 = SkippingOwner(self.l18(), fail_times=1)
        self.assert_refused(self.verify(l18=l18), "RESTORE_VERIFICATION_FAILED")
        self.assert_not_ready("SUPPRESSED_CONTENT_PRESENT")                      # L04 cleaned, L18 not
        self.assert_ready(self.verify(l18=l18), matched=1)
        self.assertIsNotNone(self.read(CODENAME))

    def test_an_unavailable_cognitive_database_blocks_serving(self):
        self.db.unlink()
        with self.assertRaises(NOT_READY) as caught:
            self.gated().require_ready()
        self.assertEqual(caught.exception.code, "RESTORE_CHECK_FAILED")


class SeparationTests(GatedPathMixin, RestoreCase):
    def test_the_gate_reads_only_and_never_erases(self):
        self.forget_fi()
        self.restore()
        before = (self.db.read_bytes(), self.privacy_db.read_bytes())
        with mock.patch.object(memory_v2.L04PrivacyErasureOwner, "erase_restore_suppressed") as l04_erase, \
                mock.patch.object(memory_v2.L18V2PrivacyErasureOwner, "erase_restore_suppressed") as l18_erase:
            for _ in range(3):
                self.assert_not_ready("SUPPRESSED_CONTENT_PRESENT")
        self.assertEqual((l04_erase.call_count, l18_erase.call_count), (0, 0))
        self.assertEqual((self.db.read_bytes(), self.privacy_db.read_bytes()), before)
        self.assertTrue(self.fi_present())

    def test_the_serving_objects_expose_no_erasure(self):
        resolver = self.gated()
        for obj in (resolver, resolver._gate):
            public = {name for name in dir(obj) if not name.startswith("_")}
            self.assertFalse({n for n in public if "erase" in n or "apply" in n or "forget" in n}, public)
        self.assertEqual({fn.__name__ for pair in resolver._gate._probes for fn in pair},
                         {"list_identities", "restore_residue"})
        source = inspect.getsource(privacy.RestoreSuppressionGate) + inspect.getsource(privacy.GatedPrivacyHoldResolver)
        self.assertNotIn("erase_restore_suppressed(", source)

    def test_a_resolver_without_a_gate_is_refused(self):
        with self.assertRaises(TypeError):
            privacy.GatedPrivacyHoldResolver(self.privacy, object())
        with self.assertRaises(privacy.PrivacyError):
            privacy.RestoreSuppressionGate(self.privacy, self.l04(), None)


if __name__ == "__main__":
    unittest.main()
