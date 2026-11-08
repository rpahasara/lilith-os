"""Relationship-origin correction (owner-approved SUPERSEDE) on L04/L18, schema v4 (TEST_ONLY; synthetic statements).

- MigrationTests: v3 -> v4 is row-preserving (the admitted original stays byte-identical), deterministic, idempotent,
  rolls back at every fault point, refuses a stale backup or a non-v3 database, and the v3 / FM-02 tooling refuses v4.
  The v4 CHECKs admit SUPERSEDE of the origin tuple only when bound to a prior revision; First Interaction stays
  CREATE-only and RESTORE stays refused.
- CorrectionStoreTests: a consented SUPERSEDE makes a NEW revision of the SAME item active; the original revision, its
  admission and audit stay as history, linked by `supersedes_revision_id` / `prior_revision_id`; a stale correction is
  refused; CREATE of a second origin memory is still refused; codename is untouched; Privacy FORGET still erases every
  revision.
"""

from __future__ import annotations

import sqlite3
import unittest

from test_canonical_runtime import digest, stamp_text  # noqa: F401  (Core API on sys.path)
from test_relationship_origin_l04 import OriginCase, RO_CLASS, RO_KEY, RO_NAMESPACE, RO_PURPOSE, ro_action

from lilith_memory import backup
from lilith_memory import canonical_contracts as C
from lilith_memory import canonical_store
from lilith_memory import first_interaction_migration as FIM
from lilith_memory import learning_v2
from lilith_memory import memory_action_v2 as MA
from lilith_memory import memory_v2
from lilith_memory import privacy_governance as PG
from lilith_memory import relationship_origin_correction_migration as RCM
from lilith_memory import relationship_origin_migration as ROM
from lilith_memory import slice15b2a_migration

ORIGINAL = "TEST_ONLY I'm saving this. Not because it is profound, a synthetic line."
CORRECTED = "TEST_ONLY I'm saying this. Not because it is profound, a synthetic line."
TEST_ONLY_PRIVACY_SECRET = b"TEST_ONLY relationship-origin correction privacy secret"


class CorrectionCase(OriginCase):
    def migrate_v4(self, tag: str = "v4", **kwargs):
        manifest = backup.create_backup(self.db, self.root / f"pre-{tag}.db", self.root / f"pre-{tag}.manifest.json",
                                        role="cognitive")
        return RCM.migrate(self.db, backup_manifest=manifest, applied_at=stamp_text(7), **kwargs)

    def origin_revisions(self):
        return self.rows("SELECT r.revision_id,r.memory_item_id,r.normalized_value_json,r.value_digest,"
                         "r.supersedes_revision_id FROM memory_revision r "
                         "JOIN memory_item i ON i.memory_item_id=r.memory_item_id WHERE i.memory_class=? "
                         "ORDER BY r.supersedes_revision_id IS NOT NULL,r.revision_id", RO_CLASS)

    def admit_original(self):
        _action, ref = self.ro_proposal(ORIGINAL, nonce="ro.original")
        result = self.ro_store().apply(ref.proposal_ref_id)
        self.assertEqual(result.outcome, canonical_store.ACCEPTED)
        return result

    def correction(self, expected: str, statement: str = CORRECTED, nonce: str = "ro.correct"):
        action, encoded = ro_action(statement, operation=C.SUPERSEDE, expected_active_revision_id=expected)
        _proposal, ref, _consent = self.proposal_with(action, encoded, nonce=nonce)
        return action, ref


class MigrationTests(CorrectionCase):
    def setUp(self):
        super().setUp()
        self.create()                                                     # codename memory
        self.migrate_ro()                                                 # v3
        self.enable_ro()
        self.original = self.admit_original()
        self.before = self.origin_revisions()
        self.codename_before = self.codename_snapshot()

    def test_v4_is_row_preserving_idempotent_and_older_tooling_refuses_it(self):
        self.assertEqual(RCM.schema_state(self.db), 3)
        first = self.migrate_v4()
        self.assertEqual(RCM.schema_state(self.db), 4)
        self.assertEqual(self.origin_revisions(), self.before)             # the admitted original, unchanged
        self.assertEqual(self.codename_snapshot(), self.codename_before)
        self.assertEqual(self.rows("PRAGMA foreign_key_check"), [])
        settled = self.complete_fingerprint()
        self.assertEqual(self.migrate_v4(tag="again"), first)              # idempotent: nothing written
        self.assertEqual(self.complete_fingerprint(), settled)
        with self.assertRaises(ROM.RelationshipOriginMigrationError):      # v3 tooling refuses v4
            ROM.schema_state(self.db)
        with self.assertRaises(FIM.FirstInteractionMigrationError):
            self.migrate_fi(tag="fm02-on-v4")
        self.assertEqual(self.complete_fingerprint(), settled)

    def test_every_fault_point_rolls_back_completely(self):
        before = self.complete_fingerprint()
        for point in RCM.FAULT_POINTS:
            def fault(stage, point=point):
                if stage == point:
                    raise RuntimeError("injected " + stage)
            with self.subTest(point=point):
                with self.assertRaises(RuntimeError):
                    self.migrate_v4(tag=point, fault_hook=fault)
                self.assertEqual(self.complete_fingerprint(), before)
                self.assertEqual(RCM.schema_state(self.db), 3)
        self.migrate_v4(tag="recovered")
        self.assertEqual(RCM.schema_state(self.db), 4)

    def test_stale_backup_is_refused(self):
        stale = backup.create_backup(self.db, self.root / "stale.db", self.root / "stale.manifest.json",
                                     role="cognitive")
        _a, ref = self.ro_proposal("TEST_ONLY changes the database after the backup.", nonce="ro.after")
        self.ro_store().apply(ref.proposal_ref_id)                          # refused (exists) but rows were written
        with self.assertRaises(Exception):
            RCM.migrate(self.db, backup_manifest=stale, applied_at=stamp_text(7))
        self.assertEqual(RCM.schema_state(self.db), 3)

    def test_v4_checks_admit_only_a_bound_origin_supersede(self):
        self.migrate_v4()
        conn = self.raw()
        try:
            row = ["p.1", 1, "actor.local-owner.v1", "ev.1", MA.CANONICAL_MEMORY_RELATIONSHIP_ORIGIN_CREATE, "SUPERSEDE",
                   RO_CLASS, RO_NAMESPACE, RO_KEY, "0" * 64, "mrev.1", None, RO_PURPOSE, "v", "ALLOWED", "0" * 64,
                   "t", "0" * 64]

            def policy(n, **change):
                values = list(row)
                values[0] = f"p.{n}"
                for index, value in change.items():
                    values[int(index[1:])] = value
                conn.execute("INSERT INTO policy_decision VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", values)
            policy(1)                                                      # bound origin correction: admitted
            for n, change in enumerate(({"i10": None},                     # SUPERSEDE without a prior revision
                                        {"i5": "RESTORE", "i11": "mrev.0"},
                                        {"i8": "other-key"}), start=2):
                with self.subTest(change=change), self.assertRaises(sqlite3.IntegrityError):
                    policy(n, **change)
            fi = list(row)
            fi[0], fi[4], fi[6], fi[7], fi[8], fi[12] = ("p.fi", MA.CANONICAL_MEMORY_FIRST_INTERACTION_CREATE,
                                                         *MA.FIRST_INTERACTION_IDENTITY, MA.OWNER_AUTOBIOGRAPHICAL_EPISODE_ADMISSION)
            with self.assertRaises(sqlite3.IntegrityError):                # First Interaction stays CREATE-only
                conn.execute("INSERT INTO policy_decision VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", fi)
            intent = ["i.1", 1, "MEMORY_INTERACTION_AUTHORITY", "home_owner_memory_intents", "actor.local-owner.v1",
                      "ev", "SUPERSEDE", RO_CLASS, RO_NAMESPACE, RO_KEY, MA.RELATIONSHIP_ORIGIN_VALUE_SCHEMA, "{}",
                      "0" * 64, None, None, RO_PURPOSE, "0" * 64, "t"]
            with self.assertRaises(sqlite3.IntegrityError):                # L18: SUPERSEDE needs the prior revision
                conn.execute("INSERT INTO learning_ro_intent_v1 VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", intent)
            intent[13] = "mrev.1"
            conn.execute("INSERT INTO learning_ro_intent_v1 VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", intent)
            conn.rollback()
        finally:
            conn.close()


class CorrectionStoreTests(CorrectionCase):
    def setUp(self):
        super().setUp()
        self.create()
        self.codename_before = self.codename_snapshot()
        self.migrate_ro()
        self.enable_ro()
        self.original = self.admit_original()

    def test_v3_refuses_a_correction_before_any_row(self):
        self.assertFalse(self.learning.supports_family_operation(MA.RELATIONSHIP_ORIGIN, C.SUPERSEDE))
        self.assertTrue(self.learning.supports_family_operation(MA.RELATIONSHIP_ORIGIN, C.CREATE))
        with self.assertRaises(Exception):
            self.correction(self.original.revision_id)
        self.assertEqual(len(self.origin_revisions()), 1)

    def test_a_consented_correction_is_a_new_active_revision_and_the_original_is_kept(self):
        before = self.origin_revisions()
        self.migrate_v4()
        self.enable_ro()
        self.assertTrue(self.learning.supports_family_operation(MA.RELATIONSHIP_ORIGIN, C.SUPERSEDE))
        self.assertFalse(self.learning.supports_family_operation(MA.FIRST_INTERACTION, C.SUPERSEDE))
        _action, ref = self.correction(self.original.revision_id)
        result = self.ro_store().apply(ref.proposal_ref_id)
        self.assertEqual(result.outcome, canonical_store.ACCEPTED, result)
        rows = self.origin_revisions()
        self.assertEqual(rows[0], before[0])                               # original revision byte-identical
        new = rows[1]
        self.assertEqual((new[0], new[1], new[4]), (result.revision_id, before[0][1], before[0][0]))
        self.assertEqual(new[2], learning_v2.normalize_relationship_origin({"statement": CORRECTED})[0])
        active = self.ro_store().get_active(RO_CLASS, RO_NAMESPACE, RO_KEY)
        self.assertEqual(active["revision_id"], result.revision_id)
        self.assertEqual(self.rows("SELECT operation,prior_revision_id,created_revision_id FROM memory_apply_audit "
                                   "WHERE memory_item_id=? ORDER BY rowid", before[0][1]),
                         [("CREATE", None, before[0][0]), ("SUPERSEDE", before[0][0], result.revision_id)])
        self.assertEqual(self.rows("SELECT COUNT(*) FROM memory_admission a JOIN memory_revision r "
                                   "ON a.proposal_ref_id=r.created_from_proposal_ref_id "
                                   "JOIN memory_item i ON i.memory_item_id=r.memory_item_id WHERE i.memory_class=?",
                                   RO_CLASS), [(2,)])
        self.assertEqual(self.rows("SELECT epistemic_basis FROM memory_revision WHERE revision_id=?",
                                   result.revision_id), [("USER_ASSERTED",)])
        self.assertEqual(self.codename_snapshot(), self.codename_before)
        replay = self.ro_store().apply(ref.proposal_ref_id)
        self.assertEqual((replay.outcome, replay.revision_id), (canonical_store.ALREADY_APPLIED, result.revision_id))

    def test_a_stale_correction_and_a_second_create_are_refused(self):
        self.migrate_v4()
        self.enable_ro()
        _a, first = self.correction(self.original.revision_id, nonce="ro.first")
        self.assertEqual(self.ro_store().apply(first.proposal_ref_id).outcome, canonical_store.ACCEPTED)
        _a, stale = self.correction(self.original.revision_id, statement=CORRECTED + " Again.", nonce="ro.stale")
        refused = self.ro_store().apply(stale.proposal_ref_id)
        self.assertEqual(refused.outcome, canonical_store.PRECONDITION_FAILED)
        _a, again = self.ro_proposal("TEST_ONLY a second origin memory.", nonce="ro.create-again")
        duplicate = self.ro_store().apply(again.proposal_ref_id)
        self.assertEqual((duplicate.outcome, duplicate.failure_code),
                         (canonical_store.PRECONDITION_FAILED, "MEMORY_ALREADY_EXISTS"))
        self.assertEqual(len(self.origin_revisions()), 2)

    def test_forget_still_erases_every_revision(self):
        self.migrate_v4()
        self.enable_ro()
        _a, ref = self.correction(self.original.revision_id)
        self.assertEqual(self.ro_store().apply(ref.proposal_ref_id).outcome, canonical_store.ACCEPTED)
        privacy_db = self.root / "privacy.test.db"
        slice15b2a_migration.migrate_privacy(privacy_db, applied_at=stamp_text(8))
        privacy = PG.PrivacyGovernanceStore(privacy_db, TEST_ONLY_PRIVACY_SECRET, self.actor)
        l18 = memory_v2.L18V2PrivacyErasureOwner(self.db, privacy)
        forget, _encoded = ro_action(operation=C.FORGET, value_schema=None, payload_digest="0" * 64,
                                     actor_ref_id=self.actor.ACTOR.actor_ref_id)
        evidence = self.actor.issue(action=forget, request_digest=digest("request:forget"), nonce="ro.forget")
        _r, auth, _s = privacy.begin_forget(
            action=forget, actor_evidence_ref_id=evidence.actor_evidence_ref_id, intent_ref_id="intent.ro.forget",
            memory_item_id=None, resource_owners=("L04", "L18_V2"), confirmation_event_ref="confirm.ro.forget")
        for owner in (memory_v2.L04PrivacyErasureOwner(self.db, privacy), l18):
            owner.erase_authorized(auth.authorization_ref_id, auth.execution_nonce)
        privacy.complete(auth.authorization_ref_id, auth.execution_nonce)
        self.assertEqual(self.origin_revisions(), [])
        for table in learning_v2.RELATIONSHIP_ORIGIN_TABLES:
            self.assertEqual(self.rows(f"SELECT COUNT(*) FROM {table}"), [(0,)], table)
        self.assertEqual(self.codename_snapshot(), self.codename_before)


if __name__ == "__main__":
    unittest.main()
