"""Slice 15B2b-A deterministic synthetic canonical-runtime tests."""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path


CORE_API = Path(__file__).resolve().parents[1]
if str(CORE_API) not in sys.path:
    sys.path.insert(0, str(CORE_API))

from lilith_memory import backup
from lilith_memory import canonical_authority as authority
from lilith_memory import canonical_contracts as contracts
from lilith_memory import canonical_migration
from lilith_memory import canonical_store
from lilith_memory import config
from lilith_memory import learning_v2
from lilith_memory import memory_store
from lilith_memory import memory_v2
from lilith_memory import registry_loader
from lilith_memory import slice15b2a_migration


TEST_CLASS = "SYNTHETIC_PROJECT_CODENAME_FACT"
TEST_NAMESPACE = "project.synthetic"
TEST_KEY = "codename"
TEST_SCHEMA = learning_v2.VALUE_SCHEMA
TEST_CAPABILITY = contracts.CANONICAL_MEMORY_PROJECT_CODENAME_MUTATE


def stamp(seconds: int = 0) -> datetime:
    return datetime(2026, 9, 22, 1, 0, tzinfo=timezone.utc) + timedelta(seconds=seconds)


def stamp_text(seconds: int = 0) -> str:
    return authority.utc_now(stamp(seconds))


def digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


class Hold:
    def __init__(self) -> None:
        self.held = False

    def is_held(self, *_identity: str) -> bool:
        return self.held


class CanonicalRuntimeCase(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.db = self.root / "cognitive.test.db"
        self.now = stamp()
        memory_store.migrate(
            self.db,
            production_path=self.root / "not-production.db",
            applied_at=stamp_text(),
        )
        old_backup = self.root / "pre-15b2a.db"
        old_proof = memory_store.create_verified_backup(self.db, old_backup)
        slice15b2a_migration.migrate_cognitive(
            self.db,
            verified_backup=old_proof,
            production_path=self.db,
            applied_at=stamp_text(1),
        )
        self.backup_file = self.root / "pre-15b2b.db"
        self.backup_manifest_file = self.root / "pre-15b2b.manifest.json"
        self.backup_manifest = backup.create_backup(
            self.db,
            self.backup_file,
            self.backup_manifest_file,
            role="cognitive",
        )
        self.migration_version, self.migration_fingerprint = canonical_migration.migrate(
            self.db,
            backup_manifest=self.backup_manifest,
            applied_at=stamp_text(2),
        )
        self.hold = Hold()
        self.actor = authority.LocalOwnerAuthority(
            self.db, b"a" * 32, now_fn=lambda: self.now
        )
        self.policy = authority.MemoryPolicyStore(
            self.db,
            self.actor,
            active_capabilities=frozenset({TEST_CAPABILITY}),
            now_fn=lambda: self.now,
        )
        self.consent = authority.ConsentStore(
            self.db, self.actor, policy_store=self.policy, now_fn=lambda: self.now
        )
        self.rollback = authority.RollbackAuthority(
            self.db, self.actor, self.consent, now_fn=lambda: self.now
        )
        self.learning = learning_v2.LearningV2Store(
            self.db,
            privacy_hold_resolver=self.hold,
            containment_ready=lambda: True,
            actor_authority=self.actor,
            policy_store=self.policy,
            consent_store=self.consent,
            now_fn=lambda: self.now,
        )
        self.registry_policy = memory_v2.MemoryTuplePolicyV1(
            memory_class=TEST_CLASS,
            subject_namespace=TEST_NAMESPACE,
            subject_key=TEST_KEY,
            value_schema=TEST_SCHEMA,
            capability=TEST_CAPABILITY,
            read_allowed=True,
            write_allowed=True,
        )
        self.registry = memory_v2.CanonicalTupleRegistry((self.registry_policy,))

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def store(self, **overrides):
        values = {
            "enabled_provider": lambda: True,
            "capability_provider": lambda capability: capability == TEST_CAPABILITY,
            "family_registry": memory_v2.ProposalFamilyRegistry(
                (learning_v2.V2_PROPOSAL_FAMILY, learning_v2.V1_PROPOSAL_FAMILY)
            ),
            "memory_registry": self.registry,
            "containment_ready": lambda identity: identity
            == (TEST_CLASS, TEST_NAMESPACE, TEST_KEY),
            "actor_authority": self.actor,
            "policy_store": self.policy,
            "consent_store": self.consent,
            "rollback_authority": self.rollback,
            "privacy_hold_resolver": self.hold,
            "now_fn": lambda: stamp_text(20),
        }
        values.update(overrides)
        return canonical_store.CanonicalMemoryStoreV2(
            self.db, self.learning, **values
        )

    def action(
        self,
        value: str,
        *,
        operation: str = contracts.CREATE,
        expected: str | None = None,
        restore: str | None = None,
        restore_digest: str | None = None,
    ):
        if operation in {contracts.CREATE, contracts.SUPERSEDE}:
            encoded, payload_digest = learning_v2.normalize_project_codename(
                {"codename": value}
            )
            value_schema = TEST_SCHEMA
        else:
            encoded = None
            payload_digest = str(restore_digest)
            value_schema = None
        return (
            contracts.FrozenMemoryActionV1(
                schema_version=1,
                actor_ref_id=self.actor.ACTOR.actor_ref_id,
                operation=operation,
                memory_class=TEST_CLASS,
                subject_namespace=TEST_NAMESPACE,
                subject_key=TEST_KEY,
                value_schema=value_schema,
                payload_digest=payload_digest,
                expected_active_revision_id=expected,
                restore_revision_id=restore,
                purpose=contracts.LONG_TERM_PERSONAL_PROJECT_RECALL,
            ),
            encoded,
        )

    def proposal(
        self,
        action: contracts.FrozenMemoryActionV1,
        encoded: str | None,
        *,
        nonce: str,
        memory_item_id: str | None = None,
    ):
        evidence = self.actor.issue(
            action=action,
            request_digest=digest("request:" + nonce),
            nonce=nonce,
        )
        decision = self.policy.decide(
            action=action,
            actor_evidence_ref_id=evidence.actor_evidence_ref_id,
            capability=TEST_CAPABILITY,
        )
        challenge = self.consent.create_challenge(
            action=action,
            actor_evidence_ref_id=evidence.actor_evidence_ref_id,
            policy_decision_ref_id=decision.decision_ref_id,
        )
        intent_ref_id = "intent." + nonce
        consent = self.consent.confirm(
            challenge.challenge_id,
            action=action,
            issuer_ref="synthetic-home-confirmation",
            intent_ref_id=intent_ref_id,
            privacy_notice_version="privacy-v1",
        )
        intent = self.learning.create_intent(
            action=action,
            actor_evidence_ref_id=evidence.actor_evidence_ref_id,
            normalized_value_json=encoded,
            intent_ref_id=intent_ref_id,
        )
        candidate = self.learning.create_candidate(
            action=action,
            actor_evidence_ref_id=evidence.actor_evidence_ref_id,
            intent_ref_id=intent.intent_ref_id,
            policy_decision_ref_id=decision.decision_ref_id,
            consent_ref_id=consent.consent_id,
        )
        self.assertEqual(
            self.learning.assess(candidate.candidate_id), learning_v2.REAL_ELIGIBLE
        )
        rollback_id = None
        if action.operation == contracts.RESTORE:
            rollback_id = self.rollback.authorize(
                action=action,
                actor_evidence_ref_id=evidence.actor_evidence_ref_id,
                consent_ref_id=consent.consent_id,
                memory_item_id=str(memory_item_id),
                confirmation_event_ref="confirm." + nonce,
            ).rollback_authorization_ref_id
        proposal, ref = self.learning.create_proposal(
            candidate_id=candidate.candidate_id,
            action=action,
            rollback_authorization_ref_id=rollback_id,
        )
        return proposal, ref, consent

    def create(self, value: str = "SYNTH-ALPHA", nonce: str = "create.one"):
        action, encoded = self.action(value)
        _, ref, consent = self.proposal(action, encoded, nonce=nonce)
        result = self.store().apply(ref.proposal_ref_id)
        self.assertEqual(result.outcome, canonical_store.ACCEPTED)
        return result, ref, consent

    def counts(self):
        conn = sqlite3.connect(self.db)
        try:
            return {
                table: int(conn.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0])
                for table in (
                    "memory_item",
                    "memory_revision",
                    "memory_revision_source",
                    "memory_admission",
                    "memory_apply_audit",
                    "memory_active_revision",
                    "rollback_consumption",
                )
            }
        finally:
            conn.close()


class TestMigrationBackupAndConfig(CanonicalRuntimeCase):
    def test_migration_is_versioned_fingerprinted_and_backup_gated(self):
        self.assertEqual(self.migration_version, 2)
        self.assertEqual(len(self.migration_fingerprint), 64)
        self.assertEqual(self.backup_manifest.integrity_check, "ok")
        self.assertEqual(self.backup_manifest.foreign_key_violations, 0)
        self.assertTrue(self.backup_manifest.privacy_precedence_required)
        with self.assertRaises(backup.BackupError):
            backup.verify_backup(
                self.root / "not-the-source.db",
                self.backup_manifest,
                expected_role="cognitive",
            )

    def test_privacy_database_online_backup_has_independent_evidence(self):
        privacy_db = self.root / "privacy.test.db"
        slice15b2a_migration.migrate_privacy(privacy_db, applied_at=stamp_text(2))
        evidence = backup.create_backup(
            privacy_db,
            self.root / "privacy.backup.db",
            self.root / "privacy.backup.manifest.json",
            role="privacy",
        )
        self.assertEqual(evidence.role, "privacy")
        self.assertEqual(evidence.integrity_check, "ok")
        self.assertEqual(evidence.foreign_key_violations, 0)
        self.assertEqual(
            backup.verify_backup(privacy_db, evidence, expected_role="privacy"),
            evidence,
        )

    def test_migration_repeat_is_idempotent_with_fresh_backup(self):
        second = backup.create_backup(
            self.db,
            self.root / "repeat.db",
            self.root / "repeat.manifest.json",
            role="cognitive",
        )
        before = self.counts()
        self.assertEqual(
            canonical_migration.migrate(self.db, backup_manifest=second),
            (2, self.migration_fingerprint),
        )
        self.assertEqual(self.counts(), before)

    def test_current_v1_rows_migrate_without_identity_or_semantic_reinterpretation(self):
        path = self.root / "v1-populated.db"
        memory_store.migrate(
            path,
            production_path=self.root / "never-production.db",
            applied_at=stamp_text(),
        )
        proof = memory_store.create_verified_backup(path, self.root / "v1-pre-b2a.db")
        slice15b2a_migration.migrate_cognitive(
            path,
            verified_backup=proof,
            production_path=path,
            applied_at=stamp_text(1),
        )
        proposal_id = "proposal.v1.migration-fixture"
        candidate_id = "candidate.v1.migration-fixture"
        proposal_fingerprint = digest("v1-migration-proposal")
        conn = sqlite3.connect(path)
        try:
            conn.execute("PRAGMA foreign_keys=ON")
            conn.execute(
                "INSERT INTO learning_candidate VALUES (?,?,?,?,?,?,?,?,?,?)",
                (
                    candidate_id, 1, "SOURCE_EVENT_CONSOLIDATION_CANDIDATE",
                    "SOURCE_EVENT_SHADOW_EVALUATION", "SOURCE_EVENT", "VALID",
                    "v1:migration", "career.applied", "job_application:7", stamp_text(3),
                ),
            )
            conn.execute(
                "INSERT INTO learning_candidate_source VALUES (?,?,?,?,?,?,?,?)",
                (
                    candidate_id, "CAREER_WATCHER", "career_events", 7, 1,
                    digest("v1-source"), stamp_text(3), "job_application:7",
                ),
            )
            conn.execute(
                "INSERT INTO learning_assessment VALUES (?,?,?,?,?)",
                (candidate_id, 1, "SHADOW_ELIGIBLE", "SOURCE_EVENT_INFRASTRUCTURE_PROOF", stamp_text(3)),
            )
            value_json = '{"kind":"TEST_ASSERTION","value":"SYNTH-V1"}'
            value_digest = digest(value_json)
            conn.execute(
                "INSERT INTO learning_proposal VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    proposal_id, candidate_id, 1, contracts.CREATE, TEST_CLASS,
                    TEST_NAMESPACE, "v1-migration", None, None, "test.assertion.v1",
                    value_json, value_digest, "SYNTHETIC_ACCEPTANCE", "CONTROLLED_IMPORT",
                    None, None, None, proposal_fingerprint, stamp_text(4),
                ),
            )
            conn.execute(
                "INSERT INTO memory_item VALUES (?,?,?,?,?)",
                ("mitem.v1.fixture", TEST_CLASS, TEST_NAMESPACE, "v1-migration", stamp_text(5)),
            )
            conn.execute(
                "INSERT INTO memory_revision VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    "mrev.v1.fixture", "mitem.v1.fixture", 1, "test.assertion.v1",
                    value_json, value_digest, proposal_id, None, None, "CONTROLLED_IMPORT",
                    "SYNTHETIC_ACCEPTANCE", None, None, None, stamp_text(6),
                ),
            )
            conn.execute(
                "INSERT INTO memory_revision_source VALUES (?,?,?,?,?,?,?,?,?)",
                (
                    "mrev.v1.fixture", 0, "CAREER_WATCHER", "career_events", 7, 1,
                    digest("v1-source"), stamp_text(3), "job_application:7",
                ),
            )
            conn.execute(
                "INSERT INTO memory_admission VALUES (?,?,?,?,?,?)",
                ("madm.v1.fixture", proposal_id, 1, "ACCEPTED", None, stamp_text(6)),
            )
            conn.execute(
                "INSERT INTO memory_apply_audit VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (
                    "mop.v1.fixture", proposal_id, "madm.v1.fixture", 1, contracts.CREATE,
                    "mitem.v1.fixture", None, "mrev.v1.fixture", "mrev.v1.fixture", None,
                    stamp_text(6),
                ),
            )
            conn.execute(
                "INSERT INTO memory_active_revision VALUES (?,?,?,?)",
                ("mitem.v1.fixture", "mrev.v1.fixture", stamp_text(6), "mop.v1.fixture"),
            )
            conn.commit()
        finally:
            conn.close()
        evidence = backup.create_backup(
            path,
            self.root / "v1-pre-b2b.db",
            self.root / "v1-pre-b2b.manifest.json",
            role="cognitive",
        )
        canonical_migration.migrate(path, backup_manifest=evidence)
        conn = sqlite3.connect(path)
        try:
            row = conn.execute(
                "SELECT r.revision_id,r.normalized_value_json,p.proposal_family,"
                "p.family_proposal_id,p.immutable_fingerprint FROM memory_revision r "
                "JOIN learning_proposal_ref p "
                "ON p.proposal_ref_id=r.created_from_proposal_ref_id"
            ).fetchone()
            self.assertEqual(
                row,
                (
                    "mrev.v1.fixture",
                    value_json,
                    learning_v2.V1_PROPOSAL_FAMILY,
                    proposal_id,
                    proposal_fingerprint,
                ),
            )
            self.assertEqual(conn.execute("PRAGMA foreign_key_check").fetchall(), [])
        finally:
            conn.close()

    def test_missing_malformed_and_inactive_config_fail_closed(self):
        missing = config.load(self.root / "missing.json")
        self.assertFalse(missing.canonical_ltm_enabled)
        self.assertFalse(missing.canonical_ltm_config_valid)
        malformed = self.root / "malformed.json"
        malformed.write_text('{"canonicalLtmEnabled":"yes"}', encoding="utf-8")
        self.assertFalse(config.load(malformed).canonical_ltm_config_valid)
        inactive = self.root / "inactive.json"
        inactive.write_text(
            json.dumps(
                {
                    "schemaVersion": 1,
                    "canonicalLtmEnabled": False,
                    "activeCapabilities": [],
                }
            ),
            encoding="utf-8",
        )
        loaded = config.load(inactive)
        self.assertTrue(loaded.canonical_ltm_config_valid)
        self.assertFalse(loaded.canonical_ltm_enabled)
        self.assertFalse(loaded.capability_active(TEST_CAPABILITY))
        synthetic_active = self.root / "synthetic-active.json"
        synthetic_active.write_text(
            json.dumps(
                {
                    "schemaVersion": 1,
                    "canonicalLtmEnabled": True,
                    "activeCapabilities": [TEST_CAPABILITY],
                }
            ),
            encoding="utf-8",
        )
        active = config.load(synthetic_active)
        self.assertTrue(active.canonical_ltm_config_valid)
        self.assertTrue(active.canonical_ltm_enabled)
        self.assertTrue(active.capability_active(TEST_CAPABILITY))

    def test_nonproduction_path_guard_rejects_production_path(self):
        with self.assertRaises(ValueError):
            config.assert_nonproduction_database(
                self.db, production_path=self.db, environment="dev"
            )


class TestRegistryAndContainment(CanonicalRuntimeCase):
    def install_registry_row(self):
        conn = sqlite3.connect(self.db)
        try:
            conn.execute(
                "INSERT INTO memory_registry_entry VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (
                    "registry.synthetic.1",
                    1,
                    TEST_CLASS,
                    TEST_NAMESPACE,
                    TEST_KEY,
                    TEST_SCHEMA,
                    TEST_CAPABILITY,
                    1,
                    1,
                    1,
                    stamp_text(3),
                ),
            )
            conn.commit()
        finally:
            conn.close()

    def test_registry_loader_requires_exact_server_approval(self):
        self.install_registry_row()
        loaded = registry_loader.GovernedRegistryLoader(
            self.db,
            approved_policies=(self.registry_policy,),
            allowed_memory_classes=frozenset({TEST_CLASS}),
        ).load()
        self.assertEqual(loaded.active_keys(), (self.registry_policy.identity,))
        with self.assertRaises(registry_loader.RegistryLoadError):
            registry_loader.GovernedRegistryLoader(
                self.db,
                approved_policies=(),
                allowed_memory_classes=frozenset({TEST_CLASS}),
            ).load()

    def test_registry_loader_rejects_unclosed_memory_class(self):
        self.install_registry_row()
        with self.assertRaises(registry_loader.RegistryLoadError):
            registry_loader.GovernedRegistryLoader(
                self.db,
                approved_policies=(self.registry_policy,),
                allowed_memory_classes=frozenset(),
            )

    def test_containment_loader_missing_and_malformed_fail_closed(self):
        with self.assertRaises(registry_loader.RegistryLoadError):
            registry_loader.load_containment(
                self.root / "missing.json",
                secret=b"c" * 32,
                canonical_registry=self.registry,
            )
        malformed = self.root / "containment.json"
        malformed.write_text("{}", encoding="utf-8")
        with self.assertRaises(registry_loader.RegistryLoadError):
            registry_loader.load_containment(
                malformed, secret=b"c" * 32, canonical_registry=self.registry
            )

    def test_containment_loader_requires_exact_registry_parity(self):
        path = self.root / "containment.json"
        path.write_text(
            json.dumps(
                {
                    "schemaVersion": 1,
                    "protectedTuples": [
                        {
                            "schemaVersion": 1,
                            "memoryClass": TEST_CLASS,
                            "subjectNamespace": TEST_NAMESPACE,
                            "subjectKey": TEST_KEY,
                            "valueFingerprints": [digest("synthetic-value")],
                            "actionDigests": [],
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )
        readiness = registry_loader.load_containment(
            path, secret=b"c" * 32, canonical_registry=self.registry
        )
        self.assertTrue(readiness.ready_for(self.registry_policy.identity))


class TestCanonicalLifecycle(CanonicalRuntimeCase):
    def test_kill_switch_and_inactive_capability_deny_without_rows(self):
        action, encoded = self.action("SYNTH-DARK")
        _, ref, _ = self.proposal(action, encoded, nonce="dark.one")
        baseline = self.counts()
        disabled = self.store(enabled_provider=lambda: False).apply(ref.proposal_ref_id)
        self.assertEqual(disabled.failure_code, "CANONICAL_LTM_DISABLED")
        self.assertEqual(self.counts(), baseline)
        inactive = self.store(capability_provider=lambda _cap: False).apply(
            ref.proposal_ref_id
        )
        self.assertEqual(inactive.failure_code, "CAPABILITY_INACTIVE")
        expected = dict(baseline)
        expected["memory_admission"] += 1
        self.assertEqual(self.counts(), expected)

    def test_create_is_atomic_and_successful_replay_is_idempotent(self):
        result, ref, _ = self.create()
        after = self.counts()
        replay = self.store().apply(ref.proposal_ref_id)
        self.assertEqual(replay.outcome, canonical_store.ALREADY_APPLIED)
        self.assertEqual(replay.revision_id, result.revision_id)
        self.assertEqual(self.counts(), after)

    def test_supersede_advances_pointer_and_stale_replay_is_terminal(self):
        created, _, _ = self.create()
        action, encoded = self.action(
            "SYNTH-BETA",
            operation=contracts.SUPERSEDE,
            expected=created.revision_id,
        )
        _, ref, _ = self.proposal(action, encoded, nonce="supersede.one")
        superseded = self.store().apply(ref.proposal_ref_id)
        self.assertEqual(superseded.outcome, canonical_store.ACCEPTED)
        self.assertNotEqual(superseded.revision_id, created.revision_id)

        stale_action, stale_value = self.action(
            "SYNTH-GAMMA",
            operation=contracts.SUPERSEDE,
            expected=created.revision_id,
        )
        _, stale_ref, _ = self.proposal(
            stale_action, stale_value, nonce="supersede.stale"
        )
        before = self.counts()
        first = self.store().apply(stale_ref.proposal_ref_id)
        second = self.store().apply(stale_ref.proposal_ref_id)
        self.assertEqual(first.failure_code, "STALE_EXPECTED_REVISION")
        self.assertEqual(second, first)
        expected = dict(before)
        expected["memory_admission"] += 1
        self.assertEqual(self.counts(), expected)

    def test_restore_resolves_exact_item_and_historical_digest_then_creates_revision(self):
        created, _, _ = self.create()
        first_row = self.store().get_active(TEST_CLASS, TEST_NAMESPACE, TEST_KEY)
        action2, encoded2 = self.action(
            "SYNTH-BETA",
            operation=contracts.SUPERSEDE,
            expected=created.revision_id,
        )
        _, ref2, _ = self.proposal(action2, encoded2, nonce="restore.supersede")
        second = self.store().apply(ref2.proposal_ref_id)
        restore_action, _ = self.action(
            "ignored",
            operation=contracts.RESTORE,
            expected=second.revision_id,
            restore=created.revision_id,
            restore_digest=str(first_row["value_digest"]),
        )
        _, restore_ref, _ = self.proposal(
            restore_action,
            None,
            nonce="restore.one",
            memory_item_id=created.memory_item_id,
        )
        restored = self.store().apply(restore_ref.proposal_ref_id)
        self.assertEqual(restored.outcome, canonical_store.ACCEPTED)
        self.assertNotIn(restored.revision_id, {created.revision_id, second.revision_id})
        conn = sqlite3.connect(self.db)
        try:
            row = conn.execute(
                "SELECT supersedes_revision_id,restores_revision_id,value_digest "
                "FROM memory_revision WHERE revision_id=?",
                (restored.revision_id,),
            ).fetchone()
            self.assertEqual(row[0], second.revision_id)
            self.assertEqual(row[1], created.revision_id)
            self.assertEqual(row[2], first_row["value_digest"])
        finally:
            conn.close()

    def test_restore_wrong_historical_digest_is_terminal_without_consuming_rollback(self):
        created, _, _ = self.create()
        action2, encoded2 = self.action(
            "SYNTH-BETA", operation=contracts.SUPERSEDE, expected=created.revision_id
        )
        _, ref2, _ = self.proposal(action2, encoded2, nonce="wrong.supersede")
        second = self.store().apply(ref2.proposal_ref_id)
        restore_action, _ = self.action(
            "ignored",
            operation=contracts.RESTORE,
            expected=second.revision_id,
            restore=created.revision_id,
            restore_digest=digest("wrong-target"),
        )
        _, restore_ref, _ = self.proposal(
            restore_action,
            None,
            nonce="wrong.restore",
            memory_item_id=created.memory_item_id,
        )
        before = self.counts()
        result = self.store().apply(restore_ref.proposal_ref_id)
        self.assertEqual(result.failure_code, "RESTORE_DIGEST_MISMATCH")
        self.assertEqual(self.counts()["rollback_consumption"], before["rollback_consumption"])

    def test_fault_injection_rolls_back_every_canonical_row(self):
        action, encoded = self.action("SYNTH-FAULT")
        _, ref, _ = self.proposal(action, encoded, nonce="fault.create")
        before = self.counts()

        def fail(stage):
            if stage == "after_revision":
                raise RuntimeError("synthetic fault")

        with self.assertRaisesRegex(RuntimeError, "synthetic fault"):
            self.store(fault_hook=fail).apply(ref.proposal_ref_id)
        self.assertEqual(self.counts(), before)
        self.assertEqual(
            self.store().apply(ref.proposal_ref_id).outcome,
            canonical_store.ACCEPTED,
        )

    def test_database_busy_returns_retryable_without_partial_state(self):
        action, encoded = self.action("SYNTH-BUSY")
        _, ref, _ = self.proposal(action, encoded, nonce="busy.create")
        lock = sqlite3.connect(self.db, timeout=0.1)
        try:
            lock.execute("BEGIN IMMEDIATE")
            before = self.counts()
            result = self.store(busy_timeout_ms=1).apply(ref.proposal_ref_id)
            self.assertEqual(result.outcome, canonical_store.RETRYABLE_FAILURE)
            self.assertEqual(result.failure_code, "DB_BUSY")
            self.assertEqual(self.counts(), before)
        finally:
            lock.rollback()
            lock.close()

    def test_privacy_hold_blocks_apply_and_read(self):
        action, encoded = self.action("SYNTH-HOLD")
        _, ref, _ = self.proposal(action, encoded, nonce="hold.create")
        self.hold.held = True
        result = self.store().apply(ref.proposal_ref_id)
        self.assertEqual(result.failure_code, "PRIVACY_HOLD_ACTIVE")
        self.hold.held = False
        created, _, consent = self.create("SYNTH-READ", nonce="hold.read")
        facade = memory_v2.CanonicalMemoryReadFacade(
            self.store(),
            registry=self.registry,
            consent_store=self.consent,
            privacy_hold_resolver=self.hold,
            actor_resolver=lambda actor: actor == self.actor.ACTOR,
        )
        self.assertEqual(
            facade.read_exact(
                actor=self.actor.ACTOR,
                memory_class=TEST_CLASS,
                subject_namespace=TEST_NAMESPACE,
                subject_key=TEST_KEY,
            )["revision_id"],
            created.revision_id,
        )
        self.hold.held = True
        self.assertIsNone(
            facade.read_exact(
                actor=self.actor.ACTOR,
                memory_class=TEST_CLASS,
                subject_namespace=TEST_NAMESPACE,
                subject_key=TEST_KEY,
            )
        )
        self.assertTrue(consent.consent_id)

    def test_read_requires_actor_exact_tuple_and_never_falls_back(self):
        facade = memory_v2.CanonicalMemoryReadFacade(
            self.store(),
            registry=self.registry,
            consent_store=self.consent,
            privacy_hold_resolver=self.hold,
            actor_resolver=lambda actor: actor == self.actor.ACTOR,
        )
        with self.assertRaises(PermissionError):
            facade.read_exact(
                actor=None,
                memory_class=TEST_CLASS,
                subject_namespace=TEST_NAMESPACE,
                subject_key=TEST_KEY,
            )
        self.assertIsNone(
            facade.read_exact(
                actor=self.actor.ACTOR,
                memory_class=TEST_CLASS,
                subject_namespace=TEST_NAMESPACE,
                subject_key=TEST_KEY,
            )
        )

    def test_family_neutral_lineage_is_locatable_for_privacy(self):
        created, ref, _ = self.create()
        conn = sqlite3.connect(self.db)
        try:
            row = conn.execute(
                "SELECT r.created_from_proposal_ref_id,p.proposal_family,p.family_proposal_id "
                "FROM memory_revision r JOIN learning_proposal_ref p "
                "ON p.proposal_ref_id=r.created_from_proposal_ref_id "
                "WHERE r.revision_id=?",
                (created.revision_id,),
            ).fetchone()
            self.assertEqual(row[0], ref.proposal_ref_id)
            self.assertEqual(row[1], learning_v2.V2_PROPOSAL_FAMILY)
            self.assertTrue(str(row[2]).startswith("proposal.v2."))
        finally:
            conn.close()


class TestV1CompatibilityAndStaticInvariants(CanonicalRuntimeCase):
    def test_v1_proposal_reference_preserves_family_and_fingerprint(self):
        conn = sqlite3.connect(self.db)
        try:
            conn.execute("PRAGMA foreign_keys=ON")
            candidate = "candidate.synthetic.v1"
            proposal = "proposal.synthetic.v1"
            conn.execute(
                "INSERT INTO learning_candidate VALUES (?,?,?,?,?,?,?,?,?,?)",
                (
                    candidate,
                    1,
                    "SOURCE_EVENT_CONSOLIDATION_CANDIDATE",
                    "SOURCE_EVENT_SHADOW_EVALUATION",
                    "SOURCE_EVENT",
                    "VALID",
                    "v1.synthetic",
                    "career.applied",
                    "job_application:1",
                    stamp_text(4),
                ),
            )
            conn.execute(
                "INSERT INTO learning_candidate_source VALUES (?,?,?,?,?,?,?,?)",
                (
                    candidate,
                    "CAREER_WATCHER",
                    "career_events",
                    1,
                    1,
                    digest("source-v1"),
                    stamp_text(4),
                    "job_application:1",
                ),
            )
            conn.execute(
                "INSERT INTO learning_assessment VALUES (?,?,?,?,?)",
                (candidate, 1, "SHADOW_ELIGIBLE", "SOURCE_EVENT_INFRASTRUCTURE_PROOF", stamp_text(4)),
            )
            conn.execute(
                "INSERT INTO learning_proposal VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    proposal,
                    candidate,
                    1,
                    contracts.CREATE,
                    TEST_CLASS,
                    TEST_NAMESPACE,
                    "v1-key",
                    None,
                    None,
                    "test.assertion.v1",
                    '{"kind":"TEST_ASSERTION","value":"SYNTH"}',
                    digest("v1-value"),
                    "SYNTHETIC_ACCEPTANCE",
                    "CONTROLLED_IMPORT",
                    None,
                    None,
                    None,
                    digest("v1-proposal"),
                    stamp_text(4),
                ),
            )
            conn.commit()
        finally:
            conn.close()
        ref = self.learning.reference_v1_proposal(proposal)
        resolved, row = self.learning.resolve_proposal_ref(ref.proposal_ref_id)
        self.assertEqual(resolved.proposal_family, learning_v2.V1_PROPOSAL_FAMILY)
        self.assertEqual(str(row["proposal_id"]), proposal)
        self.assertEqual(str(row["proposal_fingerprint"]), digest("v1-proposal"))

    def test_runtime_has_no_expansion_or_legacy_fallback_surface(self):
        source = (CORE_API / "lilith_memory" / "canonical_store.py").read_text(
            encoding="utf-8"
        ).lower()
        forbidden = (
            "memory.md",
            "user.md",
            "telegram",
            "embedding",
            "vector",
            "graph retrieval",
            "relationship memory",
            "personalization memory",
            "world mutation",
            "goal mutation",
            "soul mutation",
            "scheduler",
            "prompt consumer",
        )
        for token in forbidden:
            self.assertNotIn(token, source)

    def test_import_does_not_migrate_or_create_database(self):
        unopened = self.root / "must-not-exist.db"
        self.assertFalse(unopened.exists())
        __import__("lilith_memory.canonical_migration")
        __import__("lilith_memory.canonical_store")
        self.assertFalse(unopened.exists())


if __name__ == "__main__":
    unittest.main()
