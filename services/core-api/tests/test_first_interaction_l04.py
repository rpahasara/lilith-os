"""FM-02 First Interaction L04 family (synthetic, Core API level), versioned `memory_action_v2` design.

- ContractTests: canonical_contracts is byte-identical (governed sha f93d26d8) and still refuses the new purpose (as
  the released signer does); closed purpose/capability/basis maps in memory_action_v2; family scope; codename encoding
  goldens (computed on unmodified main 3d5ac64); the single normalizer; no live activation.
- MigrationTests: schema v2 is explicit, backup-gated, deterministic, row-preserving and idempotent; every fault point
  rolls back; mixed or stale state fails closed; the rebuilt CHECKs are paired; v1 tooling refuses a v2 database.
- StoreTests: CREATE-only apply with RECORDED_INTERACTION, replay, duplicate, hold, inactive capability; the codename
  path keeps working on the rebuilt tables.
"""

from __future__ import annotations

import hashlib
import inspect
import json
import sqlite3
import unittest

from test_canonical_runtime import (  # noqa: F401  (also puts the Core API on sys.path)
    CORE_API as CORE_API_ROOT,
    TEST_CAPABILITY,
    CanonicalRuntimeCase,
    digest,
    stamp_text,
)

from lilith_memory import backup
from lilith_memory import canonical_authority as authority
from lilith_memory import canonical_contracts as C
from lilith_memory import canonical_store
from lilith_memory import config
from lilith_memory import conversation_evidence as CE
from lilith_memory import first_interaction_migration as FIM
from lilith_memory import first_interaction_v1 as FI
from lilith_memory import learning_v2
from lilith_memory import memory_action_v2 as MA
from lilith_memory import memory_v2
from lilith_memory import slice15b2a_migration

GOVERNED_CANONICAL_CONTRACTS_SHA256 = "f93d26d8a7e01d78d25f1f1d9540577cf2a55dfd4d52c4b64c87bef93ad887e0"
# Owner-ledger schema v2 (FM-02): consent/policy/learning_v2 ledgers 1 -> 2. Distinct from canonical runtime v2.
V2_FINGERPRINTS = {
    "consent_schema_migration": "51f6ad42d6bbad5cbb52cfb68dda506c44538714015278886d7d435e7f9fffee",
    "policy_schema_migration": "70e38b78e82a3c29fafbbbeb9546d84aa5032b9699c07fe3b24c15fe42f2aac5",
    "learning_v2_schema_migration": "8da282cb421d98c9cfc0584ee74cbeea0426f6f4072d2de61f2db9ee85f5d5d4",
}
FI_CLASS, FI_NAMESPACE, FI_KEY = MA.FIRST_INTERACTION_IDENTITY
FI_PURPOSE = MA.OWNER_AUTOBIOGRAPHICAL_EPISODE_ADMISSION
FI_CAPABILITY = MA.CANONICAL_MEMORY_FIRST_INTERACTION_CREATE

# Computed on unmodified main 3d5ac64 for the CanonicalRuntimeCase codename action "SYNTH-ALPHA".
CODENAME_VALUE = '{"codename":"SYNTH-ALPHA"}'
CODENAME_PAYLOAD = "8cb9cbb19515b959059e72fa955adf05127074c96f0a97444369ac1b11f1d1dc"
CODENAME_ACTION_DIGEST = "29039e0cb5950815eb7904ec9723210eca7529f3531f56c596ccad70a5161f7a"
CODENAME_CONSENT_SEMANTICS = "bc49e416c981105a85f0d29694ed8f294be81251beb862726f8c82b4d6730319"

SYNTHETIC_BINDING = {  # TEST_ONLY shape-valid binding; never a real identity
    "lilithIdentityId": "lid1." + "ab" * 16, "charterVersion": "1.0.0-test",
    "charterDigest": "c" * 64, "identityProfileDigest": "d" * 64,
}


class SyntheticEvidenceSource:
    """TEST-ONLY stand-in for sealed captured evidence: exact transcript bytes by evidence reference."""

    def __init__(self) -> None:
        self.transcripts: dict[str, bytes] = {}

    def sealed_transcript(self, evidence_ref: str) -> bytes | None:
        return self.transcripts.get(evidence_ref)


SYNTHETIC_EVIDENCE = SyntheticEvidenceSource()


def fi_value(closing: str = "TEST_ONLY good night") -> dict:
    turns = [("OWNER", "2026-11-01T18:00:00Z", "TEST_ONLY hi"), ("LILITH", "2026-11-01T18:00:05Z", closing)]
    evidence = json.dumps({"schema": FI.TRANSCRIPT_SCHEMA, "conversationRef": "conv.test-only.core",
                           "turns": [{"index": i, "speaker": s, "at": at, "text": t}
                                     for i, (s, at, t) in enumerate(turns)]}).encode("utf-8")
    evidence_ref = "evidence.test-only.core." + hashlib.sha256(evidence).hexdigest()[:16]
    SYNTHETIC_EVIDENCE.transcripts[evidence_ref] = evidence
    return {
        "schemaVersion": 1, "valueSchema": FI.VALUE_SCHEMA, "identityBinding": dict(SYNTHETIC_BINDING),
        "truthBasis": FI.RECORDED_INTERACTION,
        "eventTime": {"startedAt": turns[0][1], "endedAt": turns[1][1]},
        "transcript": {"schema": FI.TRANSCRIPT_SCHEMA, "evidenceRef": evidence_ref,
                       "sha256": hashlib.sha256(evidence).hexdigest(), "turnCount": 2},
        "quotations": [{"position": FI.OPENING, "turnIndex": 0, "speaker": "OWNER", "start": 0,
                        "end": len(turns[0][2]), "text": turns[0][2]},
                       {"position": FI.CLOSING, "turnIndex": 1, "speaker": "LILITH", "start": 0,
                        "end": len(closing), "text": closing}],
        "access": dict(FI.ACCESS), "retention": dict(FI.RETENTION),
    }


def fi_action(value=None, **fields) -> tuple[C.FrozenMemoryActionV1, str]:
    encoded, payload = learning_v2.normalize_for_purpose(FI_PURPOSE, fi_value() if value is None else value)
    spec = dict(schema_version=1, actor_ref_id="actor.local-owner.v1", operation=C.CREATE, memory_class=FI_CLASS,
                subject_namespace=FI_NAMESPACE, subject_key=FI_KEY, value_schema=FI.VALUE_SCHEMA,
                payload_digest=payload, expected_active_revision_id=None, restore_revision_id=None,
                purpose=FI_PURPOSE)
    spec.update(fields)
    return MA.action_from_fields(**spec), encoded


class ContractTests(unittest.TestCase):
    def test_codename_encoding_is_byte_identical_to_main(self):
        encoded, payload = learning_v2.normalize_project_codename({"codename": "SYNTH-ALPHA"})
        self.assertEqual((encoded, payload), (CODENAME_VALUE, CODENAME_PAYLOAD))
        self.assertEqual(learning_v2.normalize_for_purpose(C.LONG_TERM_PERSONAL_PROJECT_RECALL,
                                                           {"codename": "SYNTH-ALPHA"}), (encoded, payload))
        action = C.FrozenMemoryActionV1(
            schema_version=1, actor_ref_id="actor.local-owner.v1", operation=C.CREATE,
            memory_class="SYNTHETIC_PROJECT_CODENAME_FACT", subject_namespace="project.synthetic",
            subject_key="codename", value_schema=learning_v2.VALUE_SCHEMA, payload_digest=payload,
            expected_active_revision_id=None, restore_revision_id=None, purpose=C.LONG_TERM_PERSONAL_PROJECT_RECALL)
        self.assertEqual(action.action_digest, CODENAME_ACTION_DIGEST)
        self.assertEqual(C.sha256_digest(C.consent_semantics(
            action, actor_evidence_ref_id="ev.1", issuer_ref="iss", intent_ref_id="intent.1",
            privacy_notice_version="privacy-v1")), CODENAME_CONSENT_SEMANTICS)

    def test_governed_contract_is_unchanged_and_still_refuses_the_new_purpose(self):
        source = (CORE_API_ROOT / "lilith_memory" / "canonical_contracts.py").read_bytes()
        self.assertEqual(hashlib.sha256(source).hexdigest(), GOVERNED_CANONICAL_CONTRACTS_SHA256)
        self.assertEqual(C.VALID_PURPOSES, frozenset({C.LONG_TERM_PERSONAL_PROJECT_RECALL}))
        action, _encoded = fi_action()
        self.assertIsInstance(action, MA.FirstInteractionActionV1)
        self.assertIsInstance(action, C.FrozenMemoryActionV1)
        base = C.FrozenMemoryActionV1(**{name: getattr(action, name) for name in C.FrozenMemoryActionV1.__dataclass_fields__})
        with self.assertRaisesRegex(C.ContractError, "purpose is unsupported"):
            base.validate()                    # what the released signer (canonical_contracts only) does today
        self.assertEqual(base.semantic_dict.__func__, action.semantic_dict.__func__)  # inherited encoding

    def test_maps_are_closed_and_paired(self):
        self.assertEqual(MA.PURPOSES, frozenset({C.LONG_TERM_PERSONAL_PROJECT_RECALL, FI_PURPOSE}))
        self.assertEqual(MA.CAPABILITY_BY_PURPOSE, {
            C.LONG_TERM_PERSONAL_PROJECT_RECALL: C.CANONICAL_MEMORY_PROJECT_CODENAME_MUTATE,
            FI_PURPOSE: FI_CAPABILITY})
        self.assertEqual(MA.EPISTEMIC_BASIS_BY_PURPOSE, {
            C.LONG_TERM_PERSONAL_PROJECT_RECALL: "USER_ASSERTED", FI_PURPOSE: "RECORDED_INTERACTION"})
        self.assertEqual(learning_v2.FIRST_INTERACTION_PROPOSAL_FAMILY, "OWNER_DIRECTED_FIRST_INTERACTION_V1")
        self.assertEqual(MA.FIRST_INTERACTION_IDENTITY, ("OWNER_DIRECTED_FIRST_INTERACTION",
                                                        "lilith.core.autobiographical", "episode.first-interaction"))
        for bad in ("", "OWNER_AUTOBIOGRAPHICAL_EPISODE", None):
            with self.assertRaises(C.ContractError):
                MA.capability_for_purpose(bad)

    def test_family_is_not_live_activatable(self):
        # The live capability configuration stays codename-only; the production tuple registry must stay empty.
        self.assertEqual(config.ALLOWED_CAPABILITIES, frozenset({C.CANONICAL_MEMORY_PROJECT_CODENAME_MUTATE}))
        entry = memory_v2.MemoryTuplePolicyV1(FI_CLASS, FI_NAMESPACE, FI_KEY, FI.VALUE_SCHEMA, FI_CAPABILITY,
                                              True, True)
        with self.assertRaises(ValueError):
            memory_v2.CanonicalTupleRegistry((entry,), database_path="x.db", production_path="x.db")

    def test_purpose_tuple_and_operation_are_bound(self):
        fi_action()[0].validate()
        with self.assertRaises(C.ContractError):                                    # FI tuple, codename purpose:
            fi_action(purpose=C.LONG_TERM_PERSONAL_PROJECT_RECALL)[0].validate()    # refused at construction
        with self.assertRaises(C.ContractError):
            fi_action(memory_class="SYNTHETIC_PROJECT_CODENAME_FACT")[0].validate()  # FI purpose, other tuple
        with self.assertRaises(C.ContractError):
            fi_action(value_schema=learning_v2.VALUE_SCHEMA)[0].validate()
        for operation, extra in ((C.SUPERSEDE, {"expected_active_revision_id": "mrev.1"}),
                                 (C.RESTORE, {"expected_active_revision_id": "mrev.1", "restore_revision_id": "mrev.0",
                                              "value_schema": None})):
            with self.subTest(operation=operation), self.assertRaises(C.ContractError):
                fi_action(operation=operation, **extra)[0].validate()
        fi_action(operation=C.FORGET, value_schema=None)[0].validate()                # Privacy-owned FORGET
        with self.assertRaises(ValueError):                                         # tuple under the wrong capability
            memory_v2.CanonicalTupleRegistry((memory_v2.MemoryTuplePolicyV1(
                FI_CLASS, FI_NAMESPACE, FI_KEY, FI.VALUE_SCHEMA, C.CANONICAL_MEMORY_PROJECT_CODENAME_MUTATE,
                True, True),))

    def test_one_authoritative_normalizer(self):
        value = fi_value()
        self.assertEqual(learning_v2.normalize_for_purpose(FI_PURPOSE, value),
                         FI.normalize_first_interaction_episode(value))
        self.assertEqual(learning_v2.normalize_for_schema(FI.VALUE_SCHEMA, value),
                         FI.normalize_first_interaction_episode(value))
        with self.assertRaises(learning_v2.LearningV2Error):
            learning_v2.normalize_for_schema("UnknownSchemaV1", value)
        with self.assertRaises(learning_v2.LearningV2Error):
            learning_v2.normalize_for_purpose(FI_PURPOSE, {"codename": "SYNTH"})
        source = inspect.getsource(FI)
        for forbidden in ("sqlite3", "open(", "socket", "subprocess", "os.environ", "canonical_store", "sign("):
            self.assertNotIn(forbidden, source, forbidden)

    def test_apply_bases_agree_with_the_contract_map(self):
        source = inspect.getsource(canonical_store.CanonicalMemoryStoreV2.apply)
        self.assertIn('"RECORDED_INTERACTION" if L.is_first_interaction(action.purpose) else "USER_ASSERTED"', source)
        self.assertEqual(MA.epistemic_basis_for_purpose(FI_PURPOSE), "RECORDED_INTERACTION")
        self.assertEqual(MA.epistemic_basis_for_purpose(C.LONG_TERM_PERSONAL_PROJECT_RECALL), "USER_ASSERTED")


# Inappropriate types for any field: unhashable (list, dict, set), wrong scalar, bytes, and a JSON-shaped tuple.
WRONG_TYPES = (["OPENING"], {"x": 1}, {"OPENING"}, ("OPENING",), 1, 1.5, True, None, b"OPENING")


class NormalizerTypeConfusionTests(unittest.TestCase):
    """F4: malformed field types must fail with the contract error, never TypeError or another exception."""

    def assert_contract_error(self, fn, value, expected=None):
        try:
            fn(value)
        except FI.FirstMemoryContractViolation as exc:
            if expected is not None:
                self.assertEqual(str(exc), expected)
            return
        except Exception as exc:  # noqa: BLE001 - any other exception type is the failure under test
            self.fail(f"{type(exc).__name__} escaped instead of FirstMemoryContractViolation: {exc}")
        self.fail("malformed value was accepted")

    def test_quotation_position_and_speaker(self):
        for field in ("position", "speaker"):
            for bad in WRONG_TYPES:
                with self.subTest(field=field, bad=repr(bad)):
                    value = fi_value()
                    value["quotations"][0] = dict(value["quotations"][0], **{field: bad})
                    self.assert_contract_error(FI.normalize_first_interaction_episode, value, "QUOTATION_MALFORMED")
                    with self.assertRaises(learning_v2.LearningV2Error):      # the L04 entry point stays typed
                        learning_v2.normalize_for_purpose(FI_PURPOSE, value)

    def test_every_value_field_and_nested_field(self):
        base = fi_value()
        paths = [(key,) for key in base] + [
            ("eventTime", "startedAt"), ("transcript", "schema"), ("transcript", "evidenceRef"),
            ("transcript", "sha256"), ("transcript", "turnCount"), ("access", "consumerScope"),
            ("retention", "mode"), ("identityBinding", "lilithIdentityId"), ("identityBinding", "charterVersion"),
            *[("quotations", 0, field) for field in ("position", "turnIndex", "speaker", "start", "end", "text")],
        ]
        for path in paths:
            for bad in WRONG_TYPES:
                value = json.loads(json.dumps(base))
                target = value
                for step in path[:-1]:
                    target = target[step]
                if type(bad) is type(target[path[-1]]):
                    continue                     # same type as the valid value: not a type-confusion input
                with self.subTest(path=path, bad=repr(bad)):
                    target[path[-1]] = bad
                    self.assert_contract_error(FI.normalize_first_interaction_episode, value)

    def test_transcript_turn_fields(self):
        for field in ("speaker", "index", "at", "text"):
            for bad in WRONG_TYPES:
                if isinstance(bad, (bytes, set, tuple)):
                    continue                                    # not representable in transcript JSON
                with self.subTest(field=field, bad=repr(bad)):
                    turns = [{"index": 0, "speaker": "OWNER", "at": "2026-11-01T18:00:00Z", "text": "TEST_ONLY hi"},
                             {"index": 1, "speaker": "LILITH", "at": "2026-11-01T18:00:05Z", "text": "TEST_ONLY ok"}]
                    turns[0][field] = bad
                    raw = json.dumps({"schema": FI.TRANSCRIPT_SCHEMA, "conversationRef": "conv.t", "turns": turns})
                    self.assert_contract_error(FI.parse_transcript, raw.encode("utf-8"), "TRANSCRIPT_MALFORMED")


class FirstInteractionCase(CanonicalRuntimeCase):
    def migrate_fi(self, tag: str = "fm02", **kwargs):
        manifest = backup.create_backup(self.db, self.root / f"pre-{tag}.db", self.root / f"pre-{tag}.manifest.json",
                                        role="cognitive")
        return FIM.migrate(self.db, backup_manifest=manifest, applied_at=stamp_text(3), **kwargs)

    def enable_fi(self):
        both = frozenset({TEST_CAPABILITY, FI_CAPABILITY})
        self.policy = authority.MemoryPolicyStore(self.db, self.actor, active_capabilities=both,
                                                  now_fn=lambda: self.now)
        self.consent = authority.ConsentStore(self.db, self.actor, policy_store=self.policy, now_fn=lambda: self.now)
        self.rollback = authority.RollbackAuthority(self.db, self.actor, self.consent, now_fn=lambda: self.now)
        self.learning = learning_v2.LearningV2Store(
            self.db, privacy_hold_resolver=self.hold, containment_ready=lambda: True, actor_authority=self.actor,
            policy_store=self.policy, consent_store=self.consent, now_fn=lambda: self.now,
            first_interaction_evidence_gate=CE.FirstInteractionEvidenceGate(
                SYNTHETIC_EVIDENCE, trusted_identity=CE.TrustedIdentityBindingV1("test", SYNTHETIC_BINDING),
                deployment_environment="test"))
        self.registry = memory_v2.CanonicalTupleRegistry((self.registry_policy, memory_v2.MemoryTuplePolicyV1(
            FI_CLASS, FI_NAMESPACE, FI_KEY, FI.VALUE_SCHEMA, FI_CAPABILITY, True, True)))

    def fi_store(self, **overrides):
        values = {
            "capability_provider": lambda capability: capability in {TEST_CAPABILITY, FI_CAPABILITY},
            "family_registry": memory_v2.ProposalFamilyRegistry(
                (learning_v2.V2_PROPOSAL_FAMILY, learning_v2.V1_PROPOSAL_FAMILY,
                 learning_v2.FIRST_INTERACTION_PROPOSAL_FAMILY)),
            "containment_ready": lambda identity: True,
        }
        values.update(overrides)
        return self.store(**values)

    def fi_proposal(self, value=None, nonce: str = "fi.one"):
        action, encoded = fi_action(value)
        _proposal, ref, consent = self.proposal_with(action, encoded, nonce=nonce)
        return action, ref

    def proposal_with(self, action, encoded, *, nonce):
        evidence = self.actor.issue(action=action, request_digest=digest("request:" + nonce), nonce=nonce)
        decision = self.policy.decide(action=action, actor_evidence_ref_id=evidence.actor_evidence_ref_id,
                                      capability=MA.capability_for_purpose(action.purpose))
        challenge = self.consent.create_challenge(action=action, actor_evidence_ref_id=evidence.actor_evidence_ref_id,
                                                  policy_decision_ref_id=decision.decision_ref_id)
        consent = self.consent.confirm(challenge.challenge_id, action=action, issuer_ref="synthetic-home-confirmation",
                                       intent_ref_id="intent." + nonce, privacy_notice_version="privacy-v1")
        intent = self.learning.create_intent(action=action, actor_evidence_ref_id=evidence.actor_evidence_ref_id,
                                             normalized_value_json=encoded, intent_ref_id="intent." + nonce)
        candidate = self.learning.create_candidate(
            action=action, actor_evidence_ref_id=evidence.actor_evidence_ref_id, intent_ref_id=intent.intent_ref_id,
            policy_decision_ref_id=decision.decision_ref_id, consent_ref_id=consent.consent_id)
        self.assertEqual(self.learning.assess(candidate.candidate_id), learning_v2.REAL_ELIGIBLE)
        proposal, ref = self.learning.create_proposal(candidate_id=candidate.candidate_id, action=action)
        return proposal, ref, consent

    def raw(self):
        conn = sqlite3.connect(self.db)
        conn.execute("PRAGMA foreign_keys=OFF")
        return conn

    def complete_fingerprint(self):
        conn = sqlite3.connect(self.db)
        try:
            return slice15b2a_migration.complete_schema_fingerprint(conn), slice15b2a_migration.table_counts(conn)
        finally:
            conn.close()


class MigrationTests(FirstInteractionCase):
    def test_v2_is_deterministic_row_preserving_and_idempotent(self):
        self.create()                                      # codename rows in consent, policy and proposal refs
        self.assertEqual(FIM.schema_state(self.db), "V1")
        conn = sqlite3.connect(self.db)
        try:
            rows = {t: FIM._rows_digest(conn, t) for t in ("consent_grant", "policy_decision", "learning_proposal_ref")}
            others = FIM._other_objects(conn, rows)
        finally:
            conn.close()
        first = self.migrate_fi()
        self.assertEqual(first, V2_FINGERPRINTS)            # pinned owner-ledger schema v2 (FM-02)
        self.assertEqual(FIM.schema_state(self.db), "V2")
        conn = sqlite3.connect(self.db)
        try:
            self.assertEqual({t: FIM._rows_digest(conn, t) for t in rows}, rows)
            after = FIM._other_objects(conn, rows)
            self.assertEqual({k: v for k, v in after.items() if k in others}, others)
            self.assertEqual(set(after) - set(others),
                             {f"{kind}:{name}" for kind, name in conn.execute(
                                 "SELECT type,name FROM sqlite_master WHERE name LIKE 'learning_fi_%'")})
            self.assertEqual(conn.execute("PRAGMA foreign_key_check").fetchall(), [])
        finally:
            conn.close()
        # Fresh v1 database, same steps: identical v2 fingerprints (deterministic).
        other = FirstInteractionCase("run")
        other.setUp()
        try:
            self.assertEqual(other.migrate_fi(), first)
        finally:
            other.tearDown()
        before = self.complete_fingerprint()
        self.assertEqual(self.migrate_fi(tag="again"), first)     # idempotent: nothing written
        self.assertEqual(self.complete_fingerprint(), before)

    def test_every_fault_point_rolls_back_completely(self):
        self.create()
        before = self.complete_fingerprint()
        for point in FIM.FAULT_POINTS:
            def fault(stage, point=point):
                if stage == point:
                    raise RuntimeError("injected " + stage)
            with self.subTest(point=point):
                with self.assertRaises(RuntimeError):
                    self.migrate_fi(tag=point, fault_hook=fault)
                self.assertEqual(self.complete_fingerprint(), before)
                self.assertEqual(FIM.schema_state(self.db), "V1")
        self.migrate_fi(tag="recovered")                      # recovery: a clean rerun succeeds
        self.assertEqual(FIM.schema_state(self.db), "V2")

    def test_stale_backup_mixed_ledgers_and_v1_tooling_fail_closed(self):
        stale = backup.create_backup(self.db, self.root / "stale.db", self.root / "stale.manifest.json",
                                     role="cognitive")
        self.create()                                         # the database changes after the backup
        with self.assertRaises(Exception):
            FIM.migrate(self.db, backup_manifest=stale, applied_at=stamp_text(3))
        self.assertEqual(FIM.schema_state(self.db), "V1")
        conn = self.raw()
        try:
            conn.execute("INSERT INTO policy_schema_migration VALUES (2,?,?)", ("0" * 64, stamp_text(3)))
            conn.commit()
        finally:
            conn.close()
        with self.assertRaises(FIM.FirstInteractionMigrationError):
            FIM.schema_state(self.db)
        before = self.complete_fingerprint()
        with self.assertRaises(FIM.FirstInteractionMigrationError):
            self.migrate_fi(tag="mixed")
        self.assertEqual(self.complete_fingerprint(), before)

    def test_v1_cognitive_migration_refuses_a_v2_database(self):
        self.migrate_fi()
        before = self.complete_fingerprint()
        with self.assertRaisesRegex(slice15b2a_migration.MigrationError, "consent_schema_migration fingerprint"):
            slice15b2a_migration.migrate_cognitive(self.db, applied_at=stamp_text(5))
        self.assertEqual(self.complete_fingerprint(), before)
        self.assertEqual(FIM.schema_state(self.db), "V2")

    def test_rebuilt_checks_are_paired_and_closed(self):
        self.migrate_fi()
        conn = self.raw()
        try:
            policy_row = ("p.1", 1, "actor.local-owner.v1", "ev.1", None, "CREATE", FI_CLASS, FI_NAMESPACE, FI_KEY,
                          "0" * 64, None, None, None, "v", "ALLOWED", "0" * 64, "t", "0" * 64)

            def policy(capability, purpose, operation="CREATE", key=FI_KEY):
                row = list(policy_row)
                row[4], row[12], row[5], row[8] = capability, purpose, operation, key
                conn.execute("INSERT INTO policy_decision VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", row)
            for capability, purpose, operation, key in (
                    (C.CANONICAL_MEMORY_PROJECT_CODENAME_MUTATE, FI_PURPOSE, "CREATE", FI_KEY),
                    (FI_CAPABILITY, C.LONG_TERM_PERSONAL_PROJECT_RECALL, "CREATE", FI_KEY),
                    (C.CANONICAL_MEMORY_PROJECT_CODENAME_MUTATE, C.LONG_TERM_PERSONAL_PROJECT_RECALL, "CREATE", FI_KEY),
                    (FI_CAPABILITY, FI_PURPOSE, "SUPERSEDE", FI_KEY),
                    (FI_CAPABILITY, FI_PURPOSE, "CREATE", "other-key"),
                    ("canonical_memory.unknown", FI_PURPOSE, "CREATE", FI_KEY)):
                with self.subTest(policy=(capability, purpose, operation, key)):
                    with self.assertRaises(sqlite3.IntegrityError):
                        policy(capability, purpose, operation, key)
            with self.assertRaises(sqlite3.IntegrityError):
                conn.execute("INSERT INTO learning_proposal_ref VALUES (?,?,?,?,?,?)",
                             ("pr.x", "UNKNOWN_FAMILY", 1, "p.x", "0" * 64, "t"))
            conn.execute("INSERT INTO learning_proposal_ref VALUES (?,?,?,?,?,?)",
                         ("pr.fi", learning_v2.FIRST_INTERACTION_PROPOSAL_FAMILY, 1, "p.fi", "0" * 64, "t"))
            conn.rollback()
        finally:
            conn.close()

    def test_unmigrated_database_refuses_the_family_and_codename_still_works(self):
        action, encoded = fi_action()
        with self.assertRaises(learning_v2.LearningV2Error):
            self.learning.create_intent(action=action, actor_evidence_ref_id="ev.1", normalized_value_json=encoded,
                                        intent_ref_id="intent.fi.v1db")
        result, _ref, _consent = self.create()
        self.assertEqual(result.outcome, canonical_store.ACCEPTED)


class StoreTests(FirstInteractionCase):
    def setUp(self):
        super().setUp()
        self.create()                                         # a codename memory exists before the migration
        self.migrate_fi()
        self.enable_fi()

    def basis(self, revision_id):
        conn = sqlite3.connect(self.db)
        try:
            return conn.execute("SELECT epistemic_basis,admission_basis,value_schema FROM memory_revision "
                                "WHERE revision_id=?", (revision_id,)).fetchone()
        finally:
            conn.close()

    def test_create_only_admission_with_recorded_interaction(self):
        action, ref = self.fi_proposal()
        before = self.counts()
        applied = self.fi_store().apply(ref.proposal_ref_id)
        self.assertEqual(applied.outcome, canonical_store.ACCEPTED)
        self.assertEqual(self.basis(applied.revision_id),
                         ("RECORDED_INTERACTION", "OWNER_DIRECTED_EXACT_ACTION", FI.VALUE_SCHEMA))
        self.assertEqual(self.counts()["memory_item"], before["memory_item"] + 1)
        replay = self.fi_store().apply(ref.proposal_ref_id)                     # idempotent replay
        self.assertEqual((replay.outcome, replay.revision_id), (canonical_store.ALREADY_APPLIED, applied.revision_id))
        _action2, ref2 = self.fi_proposal(fi_value(closing="TEST_ONLY see you"), nonce="fi.two")
        duplicate = self.fi_store().apply(ref2.proposal_ref_id)                 # a second "first" episode
        self.assertEqual((duplicate.outcome, duplicate.failure_code),
                         (canonical_store.PRECONDITION_FAILED, "MEMORY_ALREADY_EXISTS"))
        with self.assertRaisesRegex(sqlite3.IntegrityError, r"learning_fi_candidate_v1\.action_digest"):
            self.fi_proposal(nonce="fi.three")                                  # identical action: one candidate

    def test_hold_inactive_capability_and_unregistered_family_refuse(self):
        _action, ref = self.fi_proposal()
        cases = (
            ({"capability_provider": lambda capability: capability == TEST_CAPABILITY}, "CAPABILITY_INACTIVE"),
            ({"family_registry": memory_v2.ProposalFamilyRegistry(
                (learning_v2.V2_PROPOSAL_FAMILY,))}, "UNKNOWN_PROPOSAL_FAMILY"),
            ({"memory_registry": memory_v2.CanonicalTupleRegistry((self.registry_policy,))}, "UNKNOWN_MEMORY_TUPLE"),
        )
        for overrides, code in cases:
            with self.subTest(code=code):
                other = FirstInteractionCase("run")
                other.setUp()
                try:
                    other.migrate_fi()
                    other.enable_fi()
                    _a, other_ref = other.fi_proposal()
                    result = other.fi_store(**overrides).apply(other_ref.proposal_ref_id)
                    self.assertEqual((result.outcome, result.failure_code), (canonical_store.REJECTED, code))
                finally:
                    other.tearDown()
        self.hold.held = True
        held = self.fi_store().apply(ref.proposal_ref_id)
        self.assertEqual((held.outcome, held.failure_code), (canonical_store.REJECTED, "PRIVACY_HOLD_ACTIVE"))

    def test_policy_and_l18_refuse_a_mismatched_capability_or_operation(self):
        action, encoded = fi_action()
        evidence = self.actor.issue(action=action, request_digest=digest("request:x"), nonce="x")
        with self.assertRaises(authority.PolicyError):
            self.policy.decide(action=action, actor_evidence_ref_id=evidence.actor_evidence_ref_id,
                               capability=C.CANONICAL_MEMORY_PROJECT_CODENAME_MUTATE)
        inactive = authority.MemoryPolicyStore(self.db, self.actor, active_capabilities=frozenset({TEST_CAPABILITY}),
                                               now_fn=lambda: self.now)
        evidence = self.actor.issue(action=action, request_digest=digest("request:y"), nonce="y")
        decision = inactive.decide(action=action, actor_evidence_ref_id=evidence.actor_evidence_ref_id,
                                   capability=FI_CAPABILITY)
        self.assertEqual(decision.decision, authority.DENIED)                   # not activated: denied
        conn = self.raw()
        try:
            with self.assertRaises(sqlite3.IntegrityError):
                conn.execute("INSERT INTO learning_fi_intent_v1 VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                             ("intent.bad", 1, "MEMORY_INTERACTION_AUTHORITY", "home_owner_memory_intents",
                              "actor.local-owner.v1", "ev", "SUPERSEDE", FI_CLASS, FI_NAMESPACE, FI_KEY,
                              FI.VALUE_SCHEMA, "{}", "0" * 64, "mrev.1", None, FI_PURPOSE, "0" * 64, "t"))
        finally:
            conn.close()

    def test_codename_path_keeps_working_on_the_rebuilt_tables(self):
        active = self.store().get_active("SYNTHETIC_PROJECT_CODENAME_FACT", "project.synthetic", "codename")
        self.assertEqual(self.basis(active["revision_id"])[0], "USER_ASSERTED")
        action, encoded = self.action("SYNTH-BETA", operation=C.SUPERSEDE, expected=active["revision_id"])
        _proposal, ref, _consent = self.proposal(action, encoded, nonce="codename.supersede")
        result = self.store().apply(ref.proposal_ref_id)
        self.assertEqual(result.outcome, canonical_store.ACCEPTED)
        self.assertEqual(self.basis(result.revision_id)[0], "USER_ASSERTED")


if __name__ == "__main__":
    unittest.main()
