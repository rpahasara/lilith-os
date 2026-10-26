"""Relationship-origin family on L04/L18 (TEST_ONLY; every statement is synthetic, never owner content).

- ContractTests: the closed family (purpose, capability, tuple, USER_ASSERTED, OWNER_PERSONAL), purpose/tuple/operation
  binding, the governed canonical_contracts still refusing the purpose, and the statement normalizer.
- MigrationTests: schema v3 from v1 and from v2, row-preserving, deterministic, idempotent, fault rollback, paired CHECKs,
  and older tooling failing closed on v3.
- StoreTests: one CREATE-only USER_ASSERTED admission, the codename memory unchanged, no consent / wrong purpose /
  inactive capability / hold refusing, and a Privacy FORGET erasing every relationship-origin row.
"""

from __future__ import annotations

import sqlite3
import unittest

from test_canonical_runtime import TEST_CAPABILITY, digest, stamp_text  # noqa: F401  (Core API on sys.path)
from test_first_interaction_l04 import FirstInteractionCase, V2_FINGERPRINTS

from lilith_memory import backup
from lilith_memory import canonical_authority as authority
from lilith_memory import canonical_contracts as C
from lilith_memory import canonical_store
from lilith_memory import first_interaction_migration as FIM
from lilith_memory import learning_v2
from lilith_memory import memory_action_v2 as MA
from lilith_memory import memory_v2
from lilith_memory import privacy_governance as PG
from lilith_memory import relationship_origin_migration as ROM
from lilith_memory import slice15b2a_migration

RO_CLASS, RO_NAMESPACE, RO_KEY = MA.RELATIONSHIP_ORIGIN_IDENTITY
RO_PURPOSE = MA.LONG_TERM_OWNER_RELATIONSHIP_ORIGIN_RECALL
RO_CAPABILITY = MA.CANONICAL_MEMORY_RELATIONSHIP_ORIGIN_CREATE
STATEMENT = "TEST_ONLY synthetic origin statement, with a comma; not a real memory."
TEST_ONLY_PRIVACY_SECRET = b"TEST_ONLY relationship-origin privacy secret"


def ro_action(statement: str = STATEMENT, **fields) -> tuple[C.FrozenMemoryActionV1, str]:
    encoded, payload = learning_v2.normalize_relationship_origin({"statement": statement})
    spec = dict(schema_version=1, actor_ref_id="actor.local-owner.v1", operation=C.CREATE, memory_class=RO_CLASS,
                subject_namespace=RO_NAMESPACE, subject_key=RO_KEY, value_schema=MA.RELATIONSHIP_ORIGIN_VALUE_SCHEMA,
                payload_digest=payload, expected_active_revision_id=None, restore_revision_id=None, purpose=RO_PURPOSE)
    spec.update(fields)
    return MA.action_from_fields(**spec), encoded


class ContractTests(unittest.TestCase):
    def test_the_family_is_closed_and_distinct(self):
        family = MA.family_for_purpose(RO_PURPOSE)
        self.assertIs(family, MA.RELATIONSHIP_ORIGIN)
        self.assertEqual((family.capability, family.epistemic_basis, family.sensitivity, family.value_schema),
                         (RO_CAPABILITY, MA.USER_ASSERTED, MA.OWNER_PERSONAL, "OwnerRelationshipOriginV1"))
        self.assertEqual(MA.RELATIONSHIP_ORIGIN_IDENTITY, ("OWNER_PROVIDED_RELATIONSHIP_ORIGIN",
                                                           "lilith.core.relationship", "origin.owner-statement"))
        self.assertNotEqual(MA.RELATIONSHIP_ORIGIN_IDENTITY, MA.FIRST_INTERACTION_IDENTITY)
        self.assertNotEqual(MA.RELATIONSHIP_ORIGIN_IDENTITY[0], "SYNTHETIC_PROJECT_CODENAME_FACT")
        self.assertIs(MA.family_for_identity(MA.RELATIONSHIP_ORIGIN_IDENTITY), family)
        self.assertIs(MA.family_for_proposal_family(learning_v2.RELATIONSHIP_ORIGIN_PROPOSAL_FAMILY), family)
        self.assertEqual(learning_v2.L04_V2_FAMILIES, frozenset({learning_v2.V2_PROPOSAL_FAMILY,
                                                                 learning_v2.FIRST_INTERACTION_PROPOSAL_FAMILY,
                                                                 learning_v2.RELATIONSHIP_ORIGIN_PROPOSAL_FAMILY}))

    def test_the_governed_contract_still_refuses_the_purpose(self):
        action, _encoded = ro_action()
        self.assertIsInstance(action, MA.RelationshipOriginActionV1)
        action.validate()
        base = C.FrozenMemoryActionV1(**{n: getattr(action, n) for n in C.FrozenMemoryActionV1.__dataclass_fields__})
        with self.assertRaisesRegex(C.ContractError, "purpose is unsupported"):
            base.validate()
        self.assertEqual(base.semantic_dict.__func__, action.semantic_dict.__func__)  # inherited encoding

    def test_purpose_tuple_and_operation_are_bound(self):
        with self.assertRaises(C.ContractError):                                 # origin tuple, codename purpose
            ro_action(purpose=C.LONG_TERM_PERSONAL_PROJECT_RECALL)[0].validate()
        with self.assertRaises(C.ContractError):                                 # origin purpose, codename tuple
            ro_action(memory_class="SYNTHETIC_PROJECT_CODENAME_FACT", subject_namespace="project.synthetic",
                      subject_key="codename")[0].validate()
        with self.assertRaises(C.ContractError):                                 # origin purpose, FI tuple
            ro_action(memory_class=MA.FIRST_INTERACTION_IDENTITY[0], subject_namespace=MA.FIRST_INTERACTION_IDENTITY[1],
                      subject_key=MA.FIRST_INTERACTION_IDENTITY[2])[0].validate()
        with self.assertRaises(C.ContractError):
            ro_action(value_schema=learning_v2.VALUE_SCHEMA)[0].validate()
        with self.assertRaisesRegex(C.ContractError, "CREATE-only"):
            ro_action(operation=C.SUPERSEDE, expected_active_revision_id="mrev.1")[0].validate()
        ro_action(operation=C.FORGET, value_schema=None)[0].validate()           # Privacy-owned FORGET
        with self.assertRaises(C.ContractError):
            MA.capability_for_purpose("LONG_TERM_OWNER_RELATIONSHIP_ORIGIN")
        with self.assertRaises(ValueError):                                      # tuple under the codename capability
            memory_v2.CanonicalTupleRegistry((memory_v2.MemoryTuplePolicyV1(
                RO_CLASS, RO_NAMESPACE, RO_KEY, MA.RELATIONSHIP_ORIGIN_VALUE_SCHEMA,
                C.CANONICAL_MEMORY_PROJECT_CODENAME_MUTATE, True, True),))

    def test_the_statement_is_kept_exactly_as_written(self):
        encoded, payload = learning_v2.normalize_relationship_origin({"statement": "  TEST_ONLY, é x.  "})
        self.assertEqual(encoded, '{"statement":"TEST_ONLY, \\u00e9 x."}')     # NFC + trim, nothing rewritten
        self.assertEqual(learning_v2.normalize_for_schema(MA.RELATIONSHIP_ORIGIN_VALUE_SCHEMA,
                                                          {"statement": "TEST_ONLY, é x."}), (encoded, payload))
        self.assertEqual(learning_v2.normalize_for_purpose(RO_PURPOSE, {"statement": "TEST_ONLY, é x."}),
                         (encoded, payload))
        for bad in ({"statement": ""}, {"statement": "   "}, {"statement": "a\nb"}, {"statement": "a​b"},
                    {"statement": "a b"}, {"statement": "x" * 601}, {"statement": 1}, {"statement": None},
                    {"statement": "ok", "extra": 1}, {"codename": "SYNTH"}, ["statement"], "statement"):
            with self.subTest(bad=bad), self.assertRaises(learning_v2.LearningV2Error):
                learning_v2.normalize_relationship_origin(bad)
        learning_v2.normalize_relationship_origin({"statement": "x" * 600})


class OriginCase(FirstInteractionCase):
    def migrate_ro(self, tag: str = "ro", **kwargs):
        manifest = backup.create_backup(self.db, self.root / f"pre-{tag}.db", self.root / f"pre-{tag}.manifest.json",
                                        role="cognitive")
        return ROM.migrate(self.db, backup_manifest=manifest, applied_at=stamp_text(4), **kwargs)

    def enable_ro(self, capabilities=frozenset({TEST_CAPABILITY, RO_CAPABILITY})):
        self.policy = authority.MemoryPolicyStore(self.db, self.actor, active_capabilities=capabilities,
                                                  now_fn=lambda: self.now)
        self.consent = authority.ConsentStore(self.db, self.actor, policy_store=self.policy, now_fn=lambda: self.now)
        self.rollback = authority.RollbackAuthority(self.db, self.actor, self.consent, now_fn=lambda: self.now)
        self.learning = learning_v2.LearningV2Store(
            self.db, privacy_hold_resolver=self.hold, containment_ready=lambda: True, actor_authority=self.actor,
            policy_store=self.policy, consent_store=self.consent, now_fn=lambda: self.now)
        self.registry = memory_v2.CanonicalTupleRegistry((self.registry_policy, memory_v2.MemoryTuplePolicyV1(
            RO_CLASS, RO_NAMESPACE, RO_KEY, MA.RELATIONSHIP_ORIGIN_VALUE_SCHEMA, RO_CAPABILITY, True, True)))

    def ro_store(self, **overrides):
        values = {
            "capability_provider": lambda capability: capability in {TEST_CAPABILITY, RO_CAPABILITY},
            "family_registry": memory_v2.ProposalFamilyRegistry(
                (learning_v2.V2_PROPOSAL_FAMILY, learning_v2.V1_PROPOSAL_FAMILY,
                 learning_v2.RELATIONSHIP_ORIGIN_PROPOSAL_FAMILY)),
            "containment_ready": lambda identity: True,
        }
        values.update(overrides)
        return self.store(**values)

    def ro_proposal(self, statement: str = STATEMENT, nonce: str = "ro.one"):
        action, encoded = ro_action(statement)
        _proposal, ref, _consent = self.proposal_with(action, encoded, nonce=nonce)
        return action, ref

    def rows(self, sql, *args):
        conn = sqlite3.connect(self.db)
        try:
            return conn.execute(sql, args).fetchall()
        finally:
            conn.close()

    def codename_snapshot(self):
        return self.rows("SELECT r.revision_id,r.normalized_value_json,r.value_digest,r.epistemic_basis,a.admission_id "
                         "FROM memory_revision r JOIN memory_item i ON i.memory_item_id=r.memory_item_id "
                         "LEFT JOIN memory_admission a ON a.proposal_ref_id=r.created_from_proposal_ref_id "
                         "WHERE i.memory_class='SYNTHETIC_PROJECT_CODENAME_FACT' ORDER BY r.revision_id")


class MigrationTests(OriginCase):
    def test_v3_from_v1_is_row_preserving_deterministic_and_idempotent(self):
        self.create()
        self.assertEqual(ROM.schema_state(self.db), 1)
        before = self.codename_snapshot()
        first = self.migrate_ro()
        self.assertEqual(ROM.schema_state(self.db), 3)
        self.assertEqual(self.codename_snapshot(), before)
        for family in (MA.FIRST_INTERACTION, MA.RELATIONSHIP_ORIGIN):        # v3 contains v2; both stay empty
            for table in learning_v2.family_tables(family):
                self.assertEqual(self.rows(f"SELECT COUNT(*) FROM {table}"), [(0,)])
        self.assertEqual(self.rows("PRAGMA foreign_key_check"), [])
        settled = self.complete_fingerprint()
        self.assertEqual(self.migrate_ro(tag="again"), first)                # idempotent: nothing written
        self.assertEqual(self.complete_fingerprint(), settled)
        via_v2 = OriginCase("run")                                           # v1 -> v2 -> v3 ends identically
        via_v2.setUp()
        try:
            self.assertEqual(via_v2.migrate_fi(), V2_FINGERPRINTS)
            self.assertEqual(via_v2.migrate_ro(), first)
            self.assertEqual(ROM.schema_state(via_v2.db), 3)
        finally:
            via_v2.tearDown()

    def test_every_fault_point_rolls_back_completely(self):
        self.create()
        before = self.complete_fingerprint()
        for point in ROM.FAULT_POINTS:
            def fault(stage, point=point):
                if stage == point:
                    raise RuntimeError("injected " + stage)
            with self.subTest(point=point):
                with self.assertRaises(RuntimeError):
                    self.migrate_ro(tag=point, fault_hook=fault)
                self.assertEqual(self.complete_fingerprint(), before)
                self.assertEqual(ROM.schema_state(self.db), 1)
        self.migrate_ro(tag="recovered")
        self.assertEqual(ROM.schema_state(self.db), 3)

    def test_stale_backup_and_older_tooling_fail_closed(self):
        stale = backup.create_backup(self.db, self.root / "stale.db", self.root / "stale.manifest.json",
                                     role="cognitive")
        self.create()
        with self.assertRaises(Exception):
            ROM.migrate(self.db, backup_manifest=stale, applied_at=stamp_text(4))
        self.assertEqual(ROM.schema_state(self.db), 1)
        self.migrate_ro()
        before = self.complete_fingerprint()
        with self.assertRaises(FIM.FirstInteractionMigrationError):          # FM-02 tooling refuses v3
            self.migrate_fi(tag="fm02-on-v3")
        with self.assertRaises(slice15b2a_migration.MigrationError):
            slice15b2a_migration.migrate_cognitive(self.db, applied_at=stamp_text(5))
        self.assertEqual(self.complete_fingerprint(), before)

    def test_rebuilt_checks_are_paired_and_closed(self):
        self.migrate_ro()
        conn = self.raw()
        try:
            row = ["p.1", 1, "actor.local-owner.v1", "ev.1", None, "CREATE", RO_CLASS, RO_NAMESPACE, RO_KEY,
                   "0" * 64, None, None, None, "v", "ALLOWED", "0" * 64, "t", "0" * 64]

            def policy(capability, purpose, operation="CREATE", key=RO_KEY, n=[0]):
                n[0] += 1
                values = list(row)
                values[0], values[4], values[12], values[5], values[8] = f"p.{n[0]}", capability, purpose, operation, key
                conn.execute("INSERT INTO policy_decision VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", values)
            for capability, purpose, operation, key in (
                    (C.CANONICAL_MEMORY_PROJECT_CODENAME_MUTATE, C.LONG_TERM_PERSONAL_PROJECT_RECALL, "CREATE", RO_KEY),
                    (RO_CAPABILITY, C.LONG_TERM_PERSONAL_PROJECT_RECALL, "CREATE", RO_KEY),
                    (C.CANONICAL_MEMORY_PROJECT_CODENAME_MUTATE, RO_PURPOSE, "CREATE", RO_KEY),
                    (MA.CANONICAL_MEMORY_FIRST_INTERACTION_CREATE, RO_PURPOSE, "CREATE", RO_KEY),
                    (RO_CAPABILITY, RO_PURPOSE, "SUPERSEDE", RO_KEY),
                    (RO_CAPABILITY, RO_PURPOSE, "CREATE", "other-key")):
                with self.subTest(policy=(capability, purpose, operation, key)):
                    with self.assertRaises(sqlite3.IntegrityError):
                        policy(capability, purpose, operation, key)
            policy(RO_CAPABILITY, RO_PURPOSE)                                 # the one paired form
            conn.execute("INSERT INTO learning_proposal_ref VALUES (?,?,?,?,?,?)",
                         ("pr.ro", learning_v2.RELATIONSHIP_ORIGIN_PROPOSAL_FAMILY, 1, "p.ro", "0" * 64, "t"))
            with self.assertRaises(sqlite3.IntegrityError):
                conn.execute("INSERT INTO learning_proposal_ref VALUES (?,?,?,?,?,?)",
                             ("pr.x", "UNKNOWN_FAMILY", 1, "p.x", "0" * 64, "t"))
            conn.rollback()
        finally:
            conn.close()

    def test_an_unmigrated_database_refuses_the_family_and_codename_still_works(self):
        self.enable_ro()
        action, encoded = ro_action()
        with self.assertRaisesRegex(learning_v2.LearningV2Error, "Relationship origin schema is unavailable"):
            self.learning.create_intent(action=action, actor_evidence_ref_id="ev.1", normalized_value_json=encoded,
                                        intent_ref_id="intent.ro.v1db")
        result, _ref, _consent = self.create()
        self.assertEqual(result.outcome, canonical_store.ACCEPTED)


class StoreTests(OriginCase):
    def setUp(self):
        super().setUp()
        self.create()                                                     # the existing codename memory
        self.codename_before = self.codename_snapshot()
        self.migrate_ro()
        self.enable_ro()

    def test_one_consented_origin_memory_is_admitted_user_asserted(self):
        _action, ref = self.ro_proposal()
        applied = self.ro_store().apply(ref.proposal_ref_id)
        self.assertEqual(applied.outcome, canonical_store.ACCEPTED)
        self.assertEqual(self.rows("SELECT epistemic_basis,admission_basis,value_schema,normalized_value_json FROM memory_revision "
                                   "WHERE revision_id=?", applied.revision_id),
                         [("USER_ASSERTED", "OWNER_DIRECTED_EXACT_ACTION", MA.RELATIONSHIP_ORIGIN_VALUE_SCHEMA,
                           learning_v2.normalize_relationship_origin({"statement": STATEMENT})[0])])
        self.assertEqual(self.rows("SELECT COUNT(*) FROM learning_ro_candidate_v1 WHERE epistemic_basis=?",
                                   "USER_ASSERTED"), [(1,)])
        self.assertEqual(self.codename_snapshot(), self.codename_before)  # the codename memory is unchanged
        replay = self.ro_store().apply(ref.proposal_ref_id)
        self.assertEqual((replay.outcome, replay.revision_id), (canonical_store.ALREADY_APPLIED, applied.revision_id))
        _a2, ref2 = self.ro_proposal("TEST_ONLY a different synthetic statement.", nonce="ro.two")
        duplicate = self.ro_store().apply(ref2.proposal_ref_id)
        self.assertEqual((duplicate.outcome, duplicate.failure_code),
                         (canonical_store.PRECONDITION_FAILED, "MEMORY_ALREADY_EXISTS"))

    def test_no_consent_wrong_purpose_or_inactive_capability_writes_no_memory(self):
        before = self.counts()
        action, encoded = ro_action()
        evidence = self.actor.issue(action=action, request_digest=digest("request:w"), nonce="w")
        with self.assertRaises(authority.PolicyError):                    # the codename capability for this purpose
            self.policy.decide(action=action, actor_evidence_ref_id=evidence.actor_evidence_ref_id,
                               capability=C.CANONICAL_MEMORY_PROJECT_CODENAME_MUTATE)
        intent = self.learning.create_intent(action=action, actor_evidence_ref_id="ev.nc",
                                             normalized_value_json=encoded, intent_ref_id="intent.no-consent")
        with self.assertRaises(learning_v2.LearningV2Error):              # an intent alone is never a candidate
            self.learning.create_candidate(action=action, actor_evidence_ref_id="ev.nc",
                                           intent_ref_id=intent.intent_ref_id, policy_decision_ref_id="pd.none",
                                           consent_ref_id="consent.none")
        _a, ref = self.ro_proposal()
        inactive = self.ro_store(capability_provider=lambda capability: capability == TEST_CAPABILITY).apply(
            ref.proposal_ref_id)
        self.assertEqual((inactive.outcome, inactive.failure_code), (canonical_store.REJECTED, "CAPABILITY_INACTIVE"))
        codename_only = self.store().apply(ref.proposal_ref_id)           # a codename-only registry/family set
        self.assertEqual(codename_only.outcome, canonical_store.REJECTED)
        self.assertEqual(self.counts()["memory_item"], before["memory_item"])

    def test_a_privacy_hold_refuses(self):
        _a, ref = self.ro_proposal()
        self.hold.held = True
        held = self.ro_store().apply(ref.proposal_ref_id)
        self.assertEqual((held.outcome, held.failure_code), (canonical_store.REJECTED, "PRIVACY_HOLD_ACTIVE"))

    def test_forget_erases_every_origin_row_and_keeps_the_codename(self):
        _action, ref = self.ro_proposal()
        self.assertEqual(self.ro_store().apply(ref.proposal_ref_id).outcome, canonical_store.ACCEPTED)
        privacy_db = self.root / "privacy.test.db"
        slice15b2a_migration.migrate_privacy(privacy_db, applied_at=stamp_text(6))
        privacy = PG.PrivacyGovernanceStore(privacy_db, TEST_ONLY_PRIVACY_SECRET, self.actor)
        l18 = memory_v2.L18V2PrivacyErasureOwner(self.db, privacy)
        self.assertIn(MA.RELATIONSHIP_ORIGIN_IDENTITY, l18.list_identities())
        forget, _encoded = ro_action(operation=C.FORGET, value_schema=None, payload_digest="0" * 64,
                                     actor_ref_id=self.actor.ACTOR.actor_ref_id)
        evidence = self.actor.issue(action=forget, request_digest=digest("request:forget"), nonce="ro.forget")
        _r, auth, _s = privacy.begin_forget(
            action=forget, actor_evidence_ref_id=evidence.actor_evidence_ref_id, intent_ref_id="intent.ro.forget",
            memory_item_id=None, resource_owners=("L04", "L18_V2"), confirmation_event_ref="confirm.ro.forget")
        for owner in (memory_v2.L04PrivacyErasureOwner(self.db, privacy), l18):
            owner.erase_authorized(auth.authorization_ref_id, auth.execution_nonce)
        privacy.complete(auth.authorization_ref_id, auth.execution_nonce)
        for table in learning_v2.RELATIONSHIP_ORIGIN_TABLES:
            self.assertEqual(self.rows(f"SELECT COUNT(*) FROM {table}"), [(0,)], table)
        self.assertEqual(self.rows("SELECT COUNT(*) FROM learning_proposal_ref WHERE proposal_family=?",
                                   learning_v2.RELATIONSHIP_ORIGIN_PROPOSAL_FAMILY), [(0,)])
        self.assertEqual(self.rows("SELECT COUNT(*) FROM memory_item WHERE memory_class=?", RO_CLASS), [(0,)])
        self.assertEqual(l18.restore_residue(MA.RELATIONSHIP_ORIGIN_IDENTITY), 0)
        self.assertNotIn(MA.RELATIONSHIP_ORIGIN_IDENTITY, l18.list_identities())
        self.assertEqual(self.codename_snapshot(), self.codename_before)
        self.assertTrue(privacy.is_held(*MA.RELATIONSHIP_ORIGIN_IDENTITY))   # suppressed: never re-admitted silently


if __name__ == "__main__":
    unittest.main()
