"""Slice 15B2a authority, privacy, containment, L18 V2, and L04 V2 tests.

Every mutable fixture is created below a TemporaryDirectory.  No test uses the
production path, production registry, production secrets, or a real memory
value.  Synthetic codenames are intentionally unrelated to the future human
acceptance sequence.
"""

from __future__ import annotations

import dataclasses
import hashlib
import inspect
import json
import os
import sqlite3
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

HERE = Path(__file__).resolve().parent
ARCH = HERE.parent
B1 = ARCH / "slice-15b1"
A = ARCH / "slice-15a"
for module_root in reversed((HERE, B1, A)):
    if str(module_root) not in sys.path:
        sys.path.insert(0, str(module_root))

import canonical_authority as authority
import canonical_contracts as contracts
import learning_v2
import legacy_canonical_containment as containment
import memory_store
import memory_v2
import privacy_governance
import slice15b2a_migration as migration


TEST_CLASS = "SYNTHETIC_PROJECT_CODENAME_FACT"
TEST_NAMESPACE = "project.synthetic"
TEST_KEY = "codename"
TEST_SCHEMA = learning_v2.VALUE_SCHEMA
TEST_CAPABILITY = contracts.CANONICAL_MEMORY_PROJECT_CODENAME_MUTATE


def stamp(seconds: int = 0) -> datetime:
    return datetime(2026, 9, 10, 1, 0, tzinfo=timezone.utc) + timedelta(seconds=seconds)


def stamp_text(seconds: int = 0) -> str:
    return authority.utc_now(stamp(seconds))


def digest(label: str) -> str:
    return hashlib.sha256(label.encode("utf-8")).hexdigest()


class HoldFixture:
    def __init__(self, held: bool = False):
        self.held = held

    def is_held(self, *_identity: str) -> bool:
        return self.held


class RawReadFixture:
    def __init__(self, row=None):
        self.row = row
        self.calls = 0

    def get_active(self, *_identity: str):
        self.calls += 1
        return self.row


class ConsentReadFixture:
    def __init__(self, status: str):
        self.status = status

    def resolve_revision(self, *_args, **_kwargs):
        return authority.AuthorityResolution(self.status)


class Slice15B2aCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.db = self.root / "cognitive.db"
        self.privacy_db = self.root / "privacy.db"
        self.now = stamp()
        memory_store.migrate(
            self.db,
            applied_at=stamp_text(),
            production_path=self.root / "not-production.db",
        )
        self.v1_counts = self._counts(self.db)
        self.backup = self.root / "cognitive.pre15b2a.db"
        proof = memory_store.create_verified_backup(self.db, self.backup)
        self.owner_fingerprints, self.complete_fingerprint = migration.migrate_cognitive(
            self.db,
            verified_backup=proof,
            production_path=self.db,
            applied_at=stamp_text(1),
        )
        self.privacy_fingerprint, self.privacy_complete_fingerprint = (
            migration.migrate_privacy(self.privacy_db, applied_at=stamp_text(1))
        )
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
        self.privacy = privacy_governance.PrivacyGovernanceStore(
            self.privacy_db, b"p" * 32, self.actor, now_fn=lambda: self.now
        )

    def tearDown(self):
        self.tmp.cleanup()

    @staticmethod
    def _counts(path: Path):
        conn = sqlite3.connect(path)
        try:
            tables = [
                str(row[0])
                for row in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' "
                    "AND name NOT LIKE 'sqlite_%' ORDER BY name"
                )
            ]
            return {
                table: int(conn.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0])
                for table in tables
            }
        finally:
            conn.close()

    def action(
        self,
        value: str = "ORION",
        *,
        operation: str = contracts.CREATE,
        key: str = TEST_KEY,
        expected: str | None = None,
        restore: str | None = None,
    ) -> tuple[contracts.FrozenMemoryActionV1, str | None]:
        if operation in {contracts.CREATE, contracts.SUPERSEDE}:
            encoded, payload_digest = learning_v2.normalize_project_codename(
                {"codename": value}
            )
            value_schema = TEST_SCHEMA
        else:
            encoded = None
            payload_digest = digest("historical:" + value)
            value_schema = None
        return contracts.FrozenMemoryActionV1(
            schema_version=1,
            actor_ref_id=self.actor.ACTOR.actor_ref_id,
            operation=operation,
            memory_class=TEST_CLASS,
            subject_namespace=TEST_NAMESPACE,
            subject_key=key,
            value_schema=value_schema,
            payload_digest=payload_digest,
            expected_active_revision_id=expected,
            restore_revision_id=restore,
            purpose=contracts.LONG_TERM_PERSONAL_PROJECT_RECALL,
        ), encoded

    def issue(self, action, *, nonce="nonce.fixture", ttl=90):
        return self.actor.issue(
            action=action,
            request_digest=digest("request:" + action.action_digest),
            nonce=nonce,
            ttl_seconds=ttl,
        )

    def authorized_action(
        self,
        *,
        value="ORION",
        operation=contracts.CREATE,
        key=TEST_KEY,
        expected=None,
        restore=None,
        nonce="nonce.authorized",
    ):
        action, encoded = self.action(
            value, operation=operation, key=key, expected=expected, restore=restore
        )
        evidence = self.issue(action, nonce=nonce)
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
        consent = self.consent.confirm(
            challenge.challenge_id,
            action=action,
            issuer_ref="home-confirmation",
            intent_ref_id="intent." + nonce,
            privacy_notice_version="privacy-v1",
        )
        return action, encoded, evidence, decision, consent

    def v2_proposal(
        self,
        *,
        value="ORION",
        key=TEST_KEY,
        nonce="nonce.v2",
        operation=contracts.CREATE,
        expected=None,
        restore=None,
    ):
        action, encoded, evidence, decision, consent = self.authorized_action(
            value=value,
            key=key,
            nonce=nonce,
            operation=operation,
            expected=expected,
            restore=restore,
        )
        store = learning_v2.LearningV2Store(
            self.db,
            privacy_hold_resolver=HoldFixture(False),
            containment_ready=lambda: True,
            actor_authority=self.actor,
            policy_store=self.policy,
            consent_store=self.consent,
            now_fn=lambda: self.now,
        )
        intent = store.create_intent(
            action=action,
            actor_evidence_ref_id=evidence.actor_evidence_ref_id,
            normalized_value_json=encoded,
            intent_ref_id=consent.intent_ref_id,
        )
        candidate = store.create_candidate(
            action=action,
            actor_evidence_ref_id=evidence.actor_evidence_ref_id,
            intent_ref_id=intent.intent_ref_id,
            policy_decision_ref_id=decision.decision_ref_id,
            consent_ref_id=consent.consent_id,
        )
        self.assertEqual(store.assess(candidate.candidate_id), learning_v2.REAL_ELIGIBLE)
        rollback_ref_id = None
        if operation == contracts.RESTORE:
            rollback_ref_id = self.rollback.authorize(
                action=action,
                actor_evidence_ref_id=evidence.actor_evidence_ref_id,
                consent_ref_id=consent.consent_id,
                memory_item_id="item." + key,
                confirmation_event_ref="confirm." + nonce,
            ).rollback_authorization_ref_id
        proposal, ref = store.create_proposal(
            candidate_id=candidate.candidate_id,
            action=action,
            rollback_authorization_ref_id=rollback_ref_id,
        )
        return store, action, evidence, decision, consent, proposal, ref

    def synthetic_registry(self, *keys: str):
        return memory_v2.CanonicalTupleRegistry(
            tuple(
                memory_v2.MemoryTuplePolicyV1(
                    memory_class=TEST_CLASS,
                    subject_namespace=TEST_NAMESPACE,
                    subject_key=key,
                    value_schema=TEST_SCHEMA,
                    capability=TEST_CAPABILITY,
                    read_allowed=True,
                    write_allowed=True,
                )
                for key in keys
            ),
            database_path=self.db,
            production_path=self.root / "not-production.db",
        )

    def forget(self, owners, *, key: str = TEST_KEY, memory_item_id=None):
        action, _ = self.action(operation=contracts.FORGET, key=key)
        evidence = self.issue(action, nonce="nonce.forget." + key)
        return self.privacy.begin_forget(
            action=action,
            actor_evidence_ref_id=evidence.actor_evidence_ref_id,
            intent_ref_id="intent.forget." + key,
            memory_item_id=memory_item_id,
            resource_owners=owners,
            confirmation_event_ref="confirm.forget." + key,
        )

    def insert_v1_proposal(self, *, key: str, value: str, ordinal: int):
        """Create one isolated V1 graph without invoking or changing V1 semantics."""
        candidate_id = f"candidate.v1.{key}.{ordinal}"
        proposal_id = f"proposal.v1.{key}.{ordinal}"
        subject_ref = f"job_application:{1000 + ordinal}"
        source_digest = digest(f"source:{key}:{ordinal}")
        value_json = json.dumps(
            {"kind": "TEST_ASSERTION", "value": value},
            sort_keys=True,
            separators=(",", ":"),
        )
        value_digest = hashlib.sha256(value_json.encode("ascii")).hexdigest()
        proposal_fingerprint = digest(f"proposal:{key}:{ordinal}")
        conn = sqlite3.connect(self.db)
        try:
            conn.execute("PRAGMA foreign_keys=ON")
            conn.execute(
                "INSERT INTO learning_candidate VALUES (?,?,?,?,?,?,?,?,?,?)",
                (
                    candidate_id,
                    1,
                    "SOURCE_EVENT_CONSOLIDATION_CANDIDATE",
                    "SOURCE_EVENT_SHADOW_EVALUATION",
                    "SOURCE_EVENT",
                    "VALID",
                    f"v1:{key}:{ordinal}",
                    "career.applied",
                    subject_ref,
                    stamp_text(10 + ordinal),
                ),
            )
            conn.execute(
                "INSERT INTO learning_candidate_source VALUES (?,?,?,?,?,?,?,?)",
                (
                    candidate_id,
                    "CAREER_WATCHER",
                    "career_events",
                    1000 + ordinal,
                    1,
                    source_digest,
                    stamp_text(10 + ordinal),
                    subject_ref,
                ),
            )
            conn.execute(
                "INSERT INTO learning_assessment VALUES (?,?,?,?,?)",
                (
                    candidate_id,
                    1,
                    "SHADOW_ELIGIBLE",
                    "SOURCE_EVENT_INFRASTRUCTURE_PROOF",
                    stamp_text(11 + ordinal),
                ),
            )
            conn.execute(
                "INSERT INTO learning_proposal VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    proposal_id,
                    candidate_id,
                    1,
                    contracts.CREATE,
                    TEST_CLASS,
                    TEST_NAMESPACE,
                    key,
                    None,
                    None,
                    "test.assertion.v1",
                    value_json,
                    value_digest,
                    "SYNTHETIC_ACCEPTANCE",
                    "CONTROLLED_IMPORT",
                    None,
                    None,
                    None,
                    proposal_fingerprint,
                    stamp_text(12 + ordinal),
                ),
            )
            conn.commit()
        finally:
            conn.close()
        return candidate_id, proposal_id, value_json, value_digest

    def insert_l04_item(self, *, key: str, values: tuple[str, ...], ordinal: int):
        """Create an isolated L04 lineage plus its V1 proposal/provenance graph."""
        item_id = f"item.{key}.{ordinal}"
        proposals = []
        revisions = []
        fixtures = []
        for offset, value in enumerate(values):
            fixtures.append(
                self.insert_v1_proposal(
                    key=key,
                    value=value,
                    ordinal=ordinal * 10 + offset,
                )
            )
        conn = sqlite3.connect(self.db)
        try:
            conn.execute("PRAGMA foreign_keys=ON")
            conn.execute("BEGIN IMMEDIATE")
            conn.execute(
                "INSERT INTO memory_item VALUES (?,?,?,?,?)",
                (item_id, TEST_CLASS, TEST_NAMESPACE, key, stamp_text(40 + ordinal)),
            )
            prior = None
            for offset, (candidate_id, proposal_id, value_json, value_digest) in enumerate(fixtures):
                del candidate_id
                revision_id = f"revision.{key}.{ordinal}.{offset}"
                admission_id = f"admission.{key}.{ordinal}.{offset}"
                operation_id = f"operation.{key}.{ordinal}.{offset}"
                operation = contracts.CREATE if offset == 0 else contracts.SUPERSEDE
                conn.execute(
                    "INSERT INTO memory_revision VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (
                        revision_id,
                        item_id,
                        1,
                        "test.assertion.v1",
                        value_json,
                        value_digest,
                        proposal_id,
                        prior,
                        None,
                        "CONTROLLED_IMPORT",
                        "SYNTHETIC_ACCEPTANCE",
                        None,
                        None,
                        None,
                        stamp_text(50 + ordinal + offset),
                    ),
                )
                conn.execute(
                    "INSERT INTO memory_revision_source VALUES (?,?,?,?,?,?,?,?,?)",
                    (
                        revision_id,
                        0,
                        "CAREER_WATCHER",
                        "career_events",
                        1000 + ordinal * 10 + offset,
                        1,
                        digest(f"source:{key}:{ordinal * 10 + offset}"),
                        stamp_text(10 + ordinal * 10 + offset),
                        f"job_application:{1000 + ordinal * 10 + offset}",
                    ),
                )
                conn.execute(
                    "INSERT INTO memory_admission VALUES (?,?,?,?,?,?)",
                    (admission_id, proposal_id, 1, "ACCEPTED", None, stamp_text(60 + ordinal + offset)),
                )
                conn.execute(
                    "INSERT INTO memory_apply_audit VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                    (
                        operation_id,
                        proposal_id,
                        admission_id,
                        1,
                        operation,
                        item_id,
                        prior,
                        revision_id,
                        revision_id,
                        None,
                        stamp_text(70 + ordinal + offset),
                    ),
                )
                proposals.append(proposal_id)
                revisions.append(revision_id)
                prior = revision_id
            conn.execute(
                "INSERT INTO memory_active_revision VALUES (?,?,?,?)",
                (item_id, revisions[-1], stamp_text(80 + ordinal), f"operation.{key}.{ordinal}.{len(values) - 1}"),
            )
            conn.commit()
        finally:
            conn.close()
        return item_id, tuple(proposals), tuple(revisions)


class TestMigrationAndSchema(Slice15B2aCase):
    def test_migration_is_additive_empty_and_fingerprinted(self):
        after = self._counts(self.db)
        for table, count in self.v1_counts.items():
            self.assertEqual(after[table], count)
        for table in migration.COGNITIVE_15B2A_TABLES:
            self.assertEqual(after[table], 1 if table.endswith("_schema_migration") else 0)
        self.assertTrue(all(len(value) == 64 for value in self.owner_fingerprints.values()))
        self.assertEqual(len(self.complete_fingerprint), 64)

    def test_migrations_are_idempotent(self):
        before = self._counts(self.db)
        owner, complete = migration.migrate_cognitive(
            self.db, production_path=self.root / "not-production.db"
        )
        privacy_owner, privacy_complete = migration.migrate_privacy(self.privacy_db)
        self.assertEqual(before, self._counts(self.db))
        self.assertEqual(owner, self.owner_fingerprints)
        self.assertEqual(complete, self.complete_fingerprint)
        self.assertEqual(privacy_owner, self.privacy_fingerprint)
        self.assertEqual(privacy_complete, self.privacy_complete_fingerprint)

    def test_production_migration_requires_fresh_verified_backup(self):
        with self.assertRaises(migration.MigrationError):
            migration.migrate_cognitive(self.db, production_path=self.db)

    def test_privacy_store_starts_with_configuration_only(self):
        counts = self._counts(self.privacy_db)
        self.assertEqual(counts["privacy_schema_migration"], 1)
        self.assertEqual(counts["privacy_governance_config"], 1)
        for table, count in counts.items():
            if table not in {"privacy_schema_migration", "privacy_governance_config"}:
                self.assertEqual(count, 0)

    def test_runtime_sql_authorizers_preserve_owner_boundaries(self):
        _, _, _, decision, _ = self.authorized_action(nonce="nonce.authorizer")
        l18 = learning_v2.LearningV2Store(self.db)
        conn = l18.connect()
        try:
            with self.assertRaises(sqlite3.DatabaseError):
                conn.execute("SELECT * FROM memory_item")
            with self.assertRaises(sqlite3.DatabaseError):
                conn.execute("DELETE FROM learning_candidate")
        finally:
            conn.close()

        conn = self.policy._connect()
        try:
            with self.assertRaises(sqlite3.DatabaseError):
                conn.execute("SELECT * FROM consent_grant")
            with self.assertRaises(sqlite3.DatabaseError):
                conn.execute(
                    "DELETE FROM policy_decision WHERE decision_ref_id=?",
                    (decision.decision_ref_id,),
                )
        finally:
            conn.close()

        conn = self.privacy._connect()
        try:
            with self.assertRaises(sqlite3.DatabaseError):
                conn.execute("SELECT * FROM memory_item")
            with self.assertRaises(sqlite3.DatabaseError):
                conn.execute("DROP TABLE privacy_hold")
        finally:
            conn.close()


class TestActorConsentPolicyRollback(Slice15B2aCase):
    def test_browser_session_and_operator_strings_have_zero_actor_authority(self):
        action, _ = self.action()
        for caller_value in ("browser-session.synthetic", "operator"):
            resolved = self.actor.resolve_and_consume(
                caller_value,
                action=action,
                consumer_ref="test.untrusted-caller",
            )
            self.assertEqual(resolved.status, authority.INVALID)
            self.assertEqual(resolved.failure_code, contracts.ACTOR_UNRESOLVED)

    def test_actor_evidence_is_hmac_action_request_nonce_and_expiry_bound(self):
        action, _ = self.action()
        evidence = self.issue(action)
        self.assertEqual(evidence.action_digest, action.action_digest)
        self.assertEqual(evidence.request_digest, digest("request:" + action.action_digest))
        self.assertEqual(evidence.nonce, "nonce.fixture")
        self.assertNotEqual(
            evidence.evidence_fingerprint,
            contracts.sha256_digest(evidence.fingerprint_dict()),
        )
        self.assertNotIn("session", json.dumps(evidence.__dict__).lower())

    def test_actor_evidence_replay_is_rejected(self):
        action, _ = self.action()
        evidence = self.issue(action)
        first = self.actor.resolve_and_consume(
            evidence.actor_evidence_ref_id, action=action, consumer_ref="test.one"
        )
        second = self.actor.resolve_and_consume(
            evidence.actor_evidence_ref_id, action=action, consumer_ref="test.two"
        )
        self.assertEqual(first.status, authority.CONFIRMED)
        self.assertEqual(second.failure_code, contracts.ACTOR_EVIDENCE_REPLAYED)

    def test_wrong_action_and_expired_evidence_are_rejected(self):
        action, _ = self.action()
        evidence = self.issue(action, ttl=1)
        changed, _ = self.action("VEGA")
        with self.assertRaises(authority.ActorEvidenceError) as wrong:
            self.actor.validate_existing(evidence.actor_evidence_ref_id, action=changed)
        self.assertEqual(wrong.exception.code, contracts.ACTOR_EVIDENCE_INVALID)
        self.now = stamp(2)
        with self.assertRaises(authority.ActorEvidenceError) as expired:
            self.actor.validate_existing(evidence.actor_evidence_ref_id, action=action)
        self.assertEqual(expired.exception.code, contracts.ACTOR_EVIDENCE_EXPIRED)

    def test_modified_request_and_wrong_actor_are_rejected(self):
        action, _ = self.action()
        evidence = self.issue(action)
        with self.assertRaises(authority.ActorEvidenceError) as modified:
            self.actor.validate_existing(
                evidence.actor_evidence_ref_id,
                action=action,
                request_digest=digest("different-request"),
            )
        self.assertEqual(modified.exception.code, contracts.ACTOR_EVIDENCE_INVALID)
        wrong_actor = dataclasses.replace(action, actor_ref_id="actor.other")
        with self.assertRaises(authority.ActorEvidenceError) as wrong:
            self.actor.validate_existing(
                evidence.actor_evidence_ref_id, action=wrong_actor
            )
        self.assertEqual(wrong.exception.code, contracts.ACTOR_EVIDENCE_INVALID)

    def test_issuer_secret_is_absent_from_contract_and_database(self):
        action, _ = self.action()
        evidence = self.issue(action)
        encoded = json.dumps(evidence.__dict__, sort_keys=True).encode()
        self.assertNotIn(b"a" * 32, encoded)
        self.assertNotIn(b"a" * 32, self.db.read_bytes())

    def test_policy_decision_is_computed_not_caller_declared(self):
        action, _ = self.action()
        evidence = self.issue(action)
        disabled = authority.MemoryPolicyStore(
            self.db, self.actor, active_capabilities=frozenset(), now_fn=lambda: self.now
        )
        decision = disabled.decide(
            action=action,
            actor_evidence_ref_id=evidence.actor_evidence_ref_id,
            capability=TEST_CAPABILITY,
        )
        self.assertEqual(decision.decision, authority.DENIED)
        self.assertEqual(
            disabled.resolve(
                decision.decision_ref_id, action=action, capability=TEST_CAPABILITY
            ).status,
            authority.INVALID,
        )

    def test_consent_is_separate_payload_purpose_operation_and_actor_bound(self):
        action, _, evidence, decision, consent = self.authorized_action()
        self.assertEqual(decision.action_digest, action.action_digest)
        self.assertEqual(consent.action_digest, action.action_digest)
        self.assertEqual(consent.actor_evidence_ref_id, evidence.actor_evidence_ref_id)
        self.assertEqual(consent.purpose, contracts.LONG_TERM_PERSONAL_PROJECT_RECALL)
        changed, _ = self.action("VEGA")
        self.assertEqual(
            self.consent.resolve(consent.consent_id, action=changed).status,
            authority.INVALID,
        )
        variants = (
            dataclasses.replace(action, actor_ref_id="actor.other"),
            self.action(
                "ORION",
                operation=contracts.SUPERSEDE,
                expected="revision.current",
            )[0],
        )
        for variant in variants:
            self.assertEqual(
                self.consent.resolve(consent.consent_id, action=variant).status,
                authority.INVALID,
            )
        with self.assertRaises(contracts.ContractError):
            self.consent.resolve(
                consent.consent_id,
                action=dataclasses.replace(action, purpose="training"),
            )

    def test_cancelled_and_expired_challenges_leave_no_grant(self):
        action, _ = self.action()
        evidence = self.issue(action)
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
        self.consent.cancel_challenge(challenge.challenge_id)
        with self.assertRaises(authority.ConsentError):
            self.consent.confirm(
                challenge.challenge_id,
                action=action,
                issuer_ref="home-confirmation",
                intent_ref_id="intent.cancelled",
                privacy_notice_version="privacy-v1",
            )
        self.assertEqual(self._counts(self.db)["consent_grant"], 0)
        self.assertNotIn(b"ORION", self.db.read_bytes())

        expiring = self.consent.create_challenge(
            action=action,
            actor_evidence_ref_id=evidence.actor_evidence_ref_id,
            policy_decision_ref_id=decision.decision_ref_id,
        )
        self.now = stamp(301)
        with self.assertRaises(authority.ConsentError):
            self.consent.confirm(
                expiring.challenge_id,
                action=action,
                issuer_ref="home-confirmation",
                intent_ref_id="intent.expired",
                privacy_notice_version="privacy-v1",
            )
        self.assertEqual(self._counts(self.db)["consent_grant"], 0)
        counts = self._counts(self.db)
        self.assertEqual(counts["learning_candidate_v2"], 0)
        self.assertEqual(counts["learning_proposal_v2"], 0)

    def test_policy_deny_blocks_consent_challenge_and_grant(self):
        action, _ = self.action()
        evidence = self.issue(action)
        disabled = authority.MemoryPolicyStore(
            self.db, self.actor, active_capabilities=frozenset(), now_fn=lambda: self.now
        )
        denied = disabled.decide(
            action=action,
            actor_evidence_ref_id=evidence.actor_evidence_ref_id,
            capability=TEST_CAPABILITY,
        )
        consent = authority.ConsentStore(
            self.db, self.actor, policy_store=disabled, now_fn=lambda: self.now
        )
        with self.assertRaises(authority.ConsentError):
            consent.create_challenge(
                action=action,
                actor_evidence_ref_id=evidence.actor_evidence_ref_id,
                policy_decision_ref_id=denied.decision_ref_id,
            )
        self.assertEqual(self._counts(self.db)["consent_grant"], 0)

    def test_consent_grant_is_immutable_and_legacy_approval_is_not_consent(self):
        action, _, _, _, consent = self.authorized_action()
        conn = sqlite3.connect(self.db)
        try:
            with self.assertRaises(sqlite3.DatabaseError):
                conn.execute(
                    "UPDATE consent_grant SET purpose=purpose WHERE consent_id=?",
                    (consent.consent_id,),
                )
            with self.assertRaises(sqlite3.DatabaseError):
                conn.execute("DELETE FROM consent_grant WHERE consent_id=?", (consent.consent_id,))
        finally:
            conn.close()
        self.assertEqual(
            self.consent.resolve("pending.approval", action=action).status,
            authority.INVALID,
        )

    def test_consent_and_policy_reject_revision_operation_and_restore_drift(self):
        action, _, _, decision, consent = self.authorized_action(
            value="ORION",
            operation=contracts.SUPERSEDE,
            expected="revision.one",
        )
        variants = (
            dataclasses.replace(action, expected_active_revision_id="revision.other"),
            self.action("ORION", operation=contracts.CREATE)[0],
        )
        for changed in variants:
            self.assertEqual(
                self.consent.resolve(consent.consent_id, action=changed).status,
                authority.INVALID,
            )
            self.assertEqual(
                self.policy.resolve(
                    decision.decision_ref_id,
                    action=changed,
                    capability=TEST_CAPABILITY,
                ).status,
                authority.INVALID,
            )

        restore_action, _, _, restore_decision, restore_consent = self.authorized_action(
            value="ORION",
            operation=contracts.RESTORE,
            expected="revision.current",
            restore="revision.original",
            nonce="nonce.restore.drift",
        )
        changed_restore = dataclasses.replace(
            restore_action, restore_revision_id="revision.other"
        )
        self.assertEqual(
            self.consent.resolve(restore_consent.consent_id, action=changed_restore).status,
            authority.INVALID,
        )
        self.assertEqual(
            self.policy.resolve(
                restore_decision.decision_ref_id,
                action=changed_restore,
                capability=TEST_CAPABILITY,
            ).status,
            authority.INVALID,
        )

    def test_consent_revocation_is_append_only_and_suppresses_resolution(self):
        action, _, evidence, _, consent = self.authorized_action()
        self.consent.revoke(
            consent.consent_id,
            actor_evidence_ref_id=evidence.actor_evidence_ref_id,
            action=action,
        )
        self.assertEqual(
            self.consent.resolve(consent.consent_id, action=action).status,
            authority.REVOKED,
        )
        conn = sqlite3.connect(self.db)
        try:
            with self.assertRaises(sqlite3.DatabaseError):
                conn.execute("DELETE FROM consent_revocation")
        finally:
            conn.close()

    def test_rollback_is_restore_only_exact_and_single_use(self):
        action, _, evidence, _, consent = self.authorized_action(
            operation=contracts.RESTORE,
            expected="revision.current",
            restore="revision.historical",
        )
        rollback_ref = self.rollback.authorize(
            action=action,
            actor_evidence_ref_id=evidence.actor_evidence_ref_id,
            consent_ref_id=consent.consent_id,
            memory_item_id="item.codename",
            confirmation_event_ref="confirm.restore",
        )
        first = self.rollback.resolve_and_consume(
            rollback_ref.rollback_authorization_ref_id,
            action=action,
            memory_item_id="item.codename",
            consumer_ref="l04.test",
        )
        second = self.rollback.resolve_and_consume(
            rollback_ref.rollback_authorization_ref_id,
            action=action,
            memory_item_id="item.codename",
            consumer_ref="l04.test",
        )
        self.assertEqual(first.status, authority.CONFIRMED)
        self.assertEqual(second.failure_code, "ROLLBACK_REPLAYED")

    def test_rollback_rejects_caller_string_and_revision_drift(self):
        action, _, evidence, _, consent = self.authorized_action(
            operation=contracts.RESTORE,
            expected="revision.current",
            restore="revision.historical",
        )
        rollback_ref = self.rollback.authorize(
            action=action,
            actor_evidence_ref_id=evidence.actor_evidence_ref_id,
            consent_ref_id=consent.consent_id,
            memory_item_id="item.codename",
            confirmation_event_ref="confirm.restore",
        )
        self.assertEqual(
            self.rollback.resolve_and_consume(
                "operator",
                action=action,
                memory_item_id="item.codename",
                consumer_ref="l04.test",
            ).status,
            authority.INVALID,
        )
        for changed in (
            dataclasses.replace(action, expected_active_revision_id="revision.other"),
            dataclasses.replace(action, restore_revision_id="revision.other"),
        ):
            self.assertEqual(
                self.rollback.resolve_and_consume(
                    rollback_ref.rollback_authorization_ref_id,
                    action=changed,
                    memory_item_id="item.codename",
                    consumer_ref="l04.test",
                ).status,
                authority.INVALID,
            )


class TestLearningAndL04V2(Slice15B2aCase):
    def test_v2_candidate_is_digest_only_and_proposal_is_closed(self):
        _, action, _, _, _, proposal, _ = self.v2_proposal()
        conn = sqlite3.connect(self.db)
        conn.row_factory = sqlite3.Row
        try:
            candidate = conn.execute("SELECT * FROM learning_candidate_v2").fetchone()
            descriptor = conn.execute(
                "SELECT * FROM learning_project_codename_candidate_v1"
            ).fetchone()
            self.assertNotIn("ORION", json.dumps(dict(candidate)))
            self.assertEqual(descriptor["payload_digest"], action.payload_digest)
            self.assertEqual(
                set(dict(conn.execute("SELECT * FROM learning_proposal_v2").fetchone())),
                {
                    "proposal_id", "schema_version", "candidate_id", "intent_ref_id",
                    "actor_ref_id", "actor_evidence_ref_id", "policy_decision_ref_id",
                    "consent_ref_id", "rollback_authorization_ref_id", "operation",
                    "memory_class", "subject_namespace", "subject_key", "value_schema",
                    "proposed_value_json", "payload_digest", "expected_active_revision_id",
                    "restore_revision_id", "purpose", "action_digest",
                    "proposal_fingerprint", "created_at",
                },
            )
            self.assertEqual(proposal.action.action_digest, action.action_digest)
        finally:
            conn.close()

    def test_normalizer_rejects_arbitrary_payload(self):
        with self.assertRaises(learning_v2.LearningV2Error):
            learning_v2.normalize_project_codename({"codename": "ORION", "extra": True})

    def test_v1_proposal_reference_does_not_reinterpret_v1_rows(self):
        candidate_id, proposal_id, _, _ = self.insert_v1_proposal(
            key="v1-reference", value="ORION", ordinal=1
        )
        conn = sqlite3.connect(self.db)
        conn.row_factory = sqlite3.Row
        try:
            before = {
                table: dict(
                    conn.execute(
                        f"SELECT * FROM {table} WHERE candidate_id=?",
                        (candidate_id,),
                    ).fetchone()
                )
                for table in (
                    "learning_candidate",
                    "learning_candidate_source",
                    "learning_assessment",
                )
            }
            before["learning_proposal"] = dict(
                conn.execute(
                    "SELECT * FROM learning_proposal WHERE proposal_id=?",
                    (proposal_id,),
                ).fetchone()
            )
        finally:
            conn.close()
        store = learning_v2.LearningV2Store(self.db)
        ref = store.reference_v1_proposal(proposal_id)
        resolved_ref, resolved = store.resolve_proposal_ref(ref.proposal_ref_id)
        self.assertEqual(resolved_ref.proposal_family, learning_v2.V1_PROPOSAL_FAMILY)
        self.assertEqual(str(resolved["proposal_id"]), proposal_id)
        conn = sqlite3.connect(self.db)
        conn.row_factory = sqlite3.Row
        try:
            after = {
                table: dict(
                    conn.execute(
                        f"SELECT * FROM {table} WHERE candidate_id=?",
                        (candidate_id,),
                    ).fetchone()
                )
                for table in (
                    "learning_candidate",
                    "learning_candidate_source",
                    "learning_assessment",
                )
            }
            after["learning_proposal"] = dict(
                conn.execute(
                    "SELECT * FROM learning_proposal WHERE proposal_id=?",
                    (proposal_id,),
                ).fetchone()
            )
        finally:
            conn.close()
        self.assertEqual(after, before)

    def test_l18_requires_authoritative_refs_and_fresh_semantics(self):
        action, encoded, evidence, decision, consent = self.authorized_action(
            nonce="nonce.authoritative"
        )
        unavailable = learning_v2.LearningV2Store(
            self.db,
            privacy_hold_resolver=HoldFixture(False),
            containment_ready=lambda: True,
            now_fn=lambda: self.now,
        )
        intent = unavailable.create_intent(
            action=action,
            actor_evidence_ref_id=evidence.actor_evidence_ref_id,
            normalized_value_json=encoded,
            intent_ref_id=consent.intent_ref_id,
        )
        with self.assertRaises(learning_v2.LearningV2Error):
            unavailable.create_candidate(
                action=action,
                actor_evidence_ref_id=evidence.actor_evidence_ref_id,
                intent_ref_id=intent.intent_ref_id,
                policy_decision_ref_id=decision.decision_ref_id,
                consent_ref_id=consent.consent_id,
            )

        store = learning_v2.LearningV2Store(
            self.db,
            privacy_hold_resolver=HoldFixture(False),
            containment_ready=lambda: True,
            actor_authority=self.actor,
            policy_store=self.policy,
            consent_store=self.consent,
            now_fn=lambda: self.now,
        )
        for policy_ref, consent_ref in (
            ("pending.approval", consent.consent_id),
            (decision.decision_ref_id, "pending.approval"),
        ):
            with self.assertRaises(learning_v2.LearningV2Error):
                store.create_candidate(
                    action=action,
                    actor_evidence_ref_id=evidence.actor_evidence_ref_id,
                    intent_ref_id=intent.intent_ref_id,
                    policy_decision_ref_id=policy_ref,
                    consent_ref_id=consent_ref,
                )

    def test_each_new_mutation_gets_fresh_candidate_and_candidate_cannot_drift(self):
        first = self.v2_proposal(value="ORION", nonce="nonce.fresh.one")
        second = self.v2_proposal(
            value="VEGA", key="neighbor", nonce="nonce.fresh.two"
        )
        first_proposal = first[5]
        second_proposal = second[5]
        self.assertNotEqual(first_proposal.candidate_id, second_proposal.candidate_id)
        changed, _ = self.action("VEGA")
        with self.assertRaises(learning_v2.LearningV2Error):
            first[0].create_proposal(
                candidate_id=first_proposal.candidate_id,
                action=changed,
            )

    def test_containment_not_ready_defers_candidate(self):
        action, encoded, evidence, decision, consent = self.authorized_action(
            nonce="nonce.containment.defer"
        )
        store = learning_v2.LearningV2Store(
            self.db,
            privacy_hold_resolver=HoldFixture(False),
            containment_ready=lambda: False,
            actor_authority=self.actor,
            policy_store=self.policy,
            consent_store=self.consent,
            now_fn=lambda: self.now,
        )
        intent = store.create_intent(
            action=action,
            actor_evidence_ref_id=evidence.actor_evidence_ref_id,
            normalized_value_json=encoded,
            intent_ref_id=consent.intent_ref_id,
        )
        candidate = store.create_candidate(
            action=action,
            actor_evidence_ref_id=evidence.actor_evidence_ref_id,
            intent_ref_id=intent.intent_ref_id,
            policy_decision_ref_id=decision.decision_ref_id,
            consent_ref_id=consent.consent_id,
        )
        self.assertEqual(store.assess(candidate.candidate_id), learning_v2.DEFERRED)

    def test_v2_proposal_and_ref_are_immutable_and_fingerprint_bound(self):
        _, _, _, _, _, proposal, ref = self.v2_proposal(
            nonce="nonce.fingerprint"
        )
        conn = sqlite3.connect(self.db)
        try:
            for statement, values in (
                (
                    "UPDATE learning_proposal_v2 SET action_digest=? WHERE proposal_id=?",
                    (digest("tamper"), proposal.proposal_id),
                ),
                (
                    "UPDATE learning_proposal_ref SET immutable_fingerprint=? WHERE proposal_ref_id=?",
                    (digest("tamper"), ref.proposal_ref_id),
                ),
            ):
                with self.assertRaises(sqlite3.DatabaseError):
                    conn.execute(statement, values)
        finally:
            conn.close()

    def test_privacy_hold_and_containment_readiness_block_real_eligibility(self):
        action, encoded, evidence, decision, consent = self.authorized_action()
        held_store = learning_v2.LearningV2Store(
            self.db,
            privacy_hold_resolver=HoldFixture(True),
            containment_ready=lambda: True,
            actor_authority=self.actor,
            policy_store=self.policy,
            consent_store=self.consent,
            now_fn=lambda: self.now,
        )
        intent = held_store.create_intent(
            action=action,
            actor_evidence_ref_id=evidence.actor_evidence_ref_id,
            normalized_value_json=encoded,
            intent_ref_id=consent.intent_ref_id,
        )
        candidate = held_store.create_candidate(
            action=action,
            actor_evidence_ref_id=evidence.actor_evidence_ref_id,
            intent_ref_id=intent.intent_ref_id,
            policy_decision_ref_id=decision.decision_ref_id,
            consent_ref_id=consent.consent_id,
        )
        self.assertEqual(held_store.assess(candidate.candidate_id), learning_v2.REJECTED)

    def test_proposal_family_dispatch_and_l04_independent_validation(self):
        store, action, _, _, _, _, ref = self.v2_proposal()
        before = {
            table: self._counts(self.db)[table]
            for table in memory_store.MEMORY_TABLES
        }
        gate = memory_v2.L04V2AdmissionGate(
            store,
            enabled_provider=lambda: True,
            family_registry=memory_v2.ProposalFamilyRegistry(
                (learning_v2.V2_PROPOSAL_FAMILY,)
            ),
            memory_registry=self.synthetic_registry(TEST_KEY),
            actor_authority=self.actor,
            policy_store=self.policy,
            consent_store=self.consent,
            rollback_authority=self.rollback,
            privacy_hold_resolver=HoldFixture(False),
        )
        result = gate.evaluate(ref.proposal_ref_id)
        self.assertEqual((result.outcome, result.failure_code), (memory_v2.ACCEPTED, None))
        self.assertEqual(result.action_digest, action.action_digest)
        self.assertEqual(
            before,
            {
                table: self._counts(self.db)[table]
                for table in memory_store.MEMORY_TABLES
            },
        )

    def test_l04_privacy_hold_revocation_and_actor_failure_are_independent(self):
        store, action, _, _, consent, _, ref = self.v2_proposal(
            nonce="nonce.l04.independent"
        )
        common = dict(
            learning_store=store,
            enabled_provider=lambda: True,
            family_registry=memory_v2.ProposalFamilyRegistry(
                (learning_v2.V2_PROPOSAL_FAMILY,)
            ),
            memory_registry=self.synthetic_registry(TEST_KEY),
            policy_store=self.policy,
            consent_store=self.consent,
            rollback_authority=self.rollback,
        )
        held = memory_v2.L04V2AdmissionGate(
            actor_authority=self.actor,
            privacy_hold_resolver=HoldFixture(True),
            **common,
        )
        self.assertEqual(held.evaluate(ref.proposal_ref_id).failure_code, "PRIVACY_HOLD_ACTIVE")

        class RejectActor:
            def validate_existing(self, *_args, **_kwargs):
                raise authority.ActorEvidenceError(contracts.ACTOR_UNRESOLVED)

        rejected_actor = memory_v2.L04V2AdmissionGate(
            actor_authority=RejectActor(),
            privacy_hold_resolver=HoldFixture(False),
            **common,
        )
        self.assertEqual(
            rejected_actor.evaluate(ref.proposal_ref_id).failure_code,
            "ACTOR_UNRESOLVED",
        )
        self.consent.revoke(
            consent.consent_id,
            actor_evidence_ref_id=consent.actor_evidence_ref_id,
            action=action,
        )
        revoked = memory_v2.L04V2AdmissionGate(
            actor_authority=self.actor,
            privacy_hold_resolver=HoldFixture(False),
            **common,
        )
        self.assertEqual(revoked.evaluate(ref.proposal_ref_id).failure_code, "CONSENT_REVOKED")

    def test_l04_restore_requires_exact_one_time_rollback_authority(self):
        store, _, _, _, _, _, ref = self.v2_proposal(
            operation=contracts.RESTORE,
            expected="revision.current",
            restore="revision.historical",
            nonce="nonce.l04.restore",
        )
        gate = memory_v2.L04V2AdmissionGate(
            store,
            enabled_provider=lambda: True,
            family_registry=memory_v2.ProposalFamilyRegistry(
                (learning_v2.V2_PROPOSAL_FAMILY,)
            ),
            memory_registry=self.synthetic_registry(TEST_KEY),
            actor_authority=self.actor,
            policy_store=self.policy,
            consent_store=self.consent,
            rollback_authority=self.rollback,
            privacy_hold_resolver=HoldFixture(False),
        )
        self.assertEqual(gate.evaluate(ref.proposal_ref_id).outcome, memory_v2.ACCEPTED)
        self.assertEqual(
            gate.evaluate(ref.proposal_ref_id).failure_code,
            "ROLLBACK_NOT_AUTHORIZED",
        )

    def test_l04_kill_switch_and_empty_family_fail_closed(self):
        store, _, _, _, _, _, ref = self.v2_proposal()
        common = dict(
            learning_store=store,
            memory_registry=self.synthetic_registry(TEST_KEY),
            actor_authority=self.actor,
            policy_store=self.policy,
            consent_store=self.consent,
            rollback_authority=self.rollback,
            privacy_hold_resolver=HoldFixture(False),
        )
        for provided in (False, None, "true"):
            gate = memory_v2.L04V2AdmissionGate(
                enabled_provider=lambda value=provided: value,
                family_registry=memory_v2.ProposalFamilyRegistry(
                    (learning_v2.V2_PROPOSAL_FAMILY,)
                ),
                **common,
            )
            self.assertEqual(gate.evaluate(ref.proposal_ref_id).failure_code, "CANONICAL_LTM_DISABLED")
        inactive = memory_v2.L04V2AdmissionGate(
            enabled_provider=lambda: True,
            family_registry=memory_v2.ProposalFamilyRegistry(),
            **common,
        )
        self.assertEqual(inactive.evaluate(ref.proposal_ref_id).failure_code, "UNKNOWN_PROPOSAL_FAMILY")

    def test_production_registry_guard_and_empty_registry(self):
        production = self.root / "production.db"
        policy = memory_v2.MemoryTuplePolicyV1(
            TEST_CLASS, TEST_NAMESPACE, TEST_KEY, TEST_SCHEMA, TEST_CAPABILITY, True, True
        )
        with self.assertRaises(ValueError):
            memory_v2.CanonicalTupleRegistry(
                (policy,), database_path=production, production_path=production
            )
        self.assertEqual(memory_v2.CanonicalTupleRegistry().active_keys(), ())

        store, _, _, _, _, _, ref = self.v2_proposal(nonce="nonce.empty.registry")
        gate = memory_v2.L04V2AdmissionGate(
            store,
            enabled_provider=lambda: True,
            family_registry=memory_v2.ProposalFamilyRegistry(
                (learning_v2.V2_PROPOSAL_FAMILY,)
            ),
            memory_registry=memory_v2.CanonicalTupleRegistry(),
            actor_authority=self.actor,
            policy_store=self.policy,
            consent_store=self.consent,
            rollback_authority=self.rollback,
            privacy_hold_resolver=HoldFixture(False),
        )
        self.assertEqual(gate.evaluate(ref.proposal_ref_id).failure_code, "UNKNOWN_MEMORY_TUPLE")

    def test_unknown_proposal_family_is_rejected_at_registry_boundary(self):
        with self.assertRaises(ValueError):
            memory_v2.ProposalFamilyRegistry(("UNKNOWN_PROPOSAL_FAMILY",))


class TestReadFacade(Slice15B2aCase):
    def row(self):
        return {
            "consent_ref_id": "consent.synthetic",
            "value_digest": digest("ORION"),
            "value": {"codename": "ORION"},
        }

    def test_requires_actor_and_exact_registry(self):
        raw = RawReadFixture(self.row())
        facade = memory_v2.CanonicalMemoryReadFacade(
            raw,
            registry=self.synthetic_registry(TEST_KEY),
            consent_store=ConsentReadFixture(authority.CONFIRMED),
            privacy_hold_resolver=HoldFixture(False),
            actor_resolver=lambda actor: actor == self.actor.ACTOR,
        )
        with self.assertRaises(PermissionError):
            facade.read_exact(
                actor=None,
                memory_class=TEST_CLASS,
                subject_namespace=TEST_NAMESPACE,
                subject_key=TEST_KEY,
            )
        self.assertEqual(raw.calls, 0)
        with self.assertRaises(PermissionError):
            facade.read_exact(
                actor=dataclasses.replace(self.actor.ACTOR, actor_ref_id="actor.other"),
                memory_class=TEST_CLASS,
                subject_namespace=TEST_NAMESPACE,
                subject_key=TEST_KEY,
            )
        with self.assertRaises(PermissionError):
            facade.read_exact(
                actor=self.actor.ACTOR,
                memory_class=TEST_CLASS,
                subject_namespace=TEST_NAMESPACE,
                subject_key="unknown",
            )
        self.assertEqual(raw.calls, 0)

    def test_hold_revocation_and_miss_return_no_fallback(self):
        for held, status, row in (
            (True, authority.CONFIRMED, self.row()),
            (False, authority.REVOKED, self.row()),
            (False, authority.CONFIRMED, None),
        ):
            raw = RawReadFixture(row)
            facade = memory_v2.CanonicalMemoryReadFacade(
                raw,
                registry=self.synthetic_registry(TEST_KEY),
                consent_store=ConsentReadFixture(status),
                privacy_hold_resolver=HoldFixture(held),
                actor_resolver=lambda actor: actor == self.actor.ACTOR,
            )
            self.assertIsNone(
                facade.read_exact(
                    actor=self.actor.ACTOR,
                    memory_class=TEST_CLASS,
                    subject_namespace=TEST_NAMESPACE,
                    subject_key=TEST_KEY,
                )
            )

    def test_valid_exact_read_returns_only_l04_row(self):
        row = self.row()
        facade = memory_v2.CanonicalMemoryReadFacade(
            RawReadFixture(row),
            registry=self.synthetic_registry(TEST_KEY),
            consent_store=ConsentReadFixture(authority.CONFIRMED),
            privacy_hold_resolver=HoldFixture(False),
            actor_resolver=lambda actor: actor == self.actor.ACTOR,
        )
        self.assertIs(
            facade.read_exact(
                actor=self.actor.ACTOR,
                memory_class=TEST_CLASS,
                subject_namespace=TEST_NAMESPACE,
                subject_key=TEST_KEY,
            ),
            row,
        )

    def test_read_facade_has_no_legacy_or_context_fallback(self):
        source = inspect.getsource(memory_v2.CanonicalMemoryReadFacade.read_exact).lower()
        self.assertIn("_raw_l04_store.get_active", source)
        for forbidden in (
            "memory.md",
            "user.md",
            "world",
            "chat",
            "context",
            "/memory/",
            "legacy",
        ):
            self.assertNotIn(forbidden, source)


class TestContainment(Slice15B2aCase):
    def gate(self):
        secret = b"c" * 32
        entry = containment.make_protected_tuple(
            secret=secret,
            memory_class=TEST_CLASS,
            subject_namespace=TEST_NAMESPACE,
            subject_key=TEST_KEY,
            protected_values=("VEGA", "ORION PRIME"),
            action_digests=(digest("historical-action"),),
        )
        return containment.LegacyCanonicalContainmentGate(
            secret=secret, registry_provider=lambda: (entry,)
        )

    def marker(self, *, action_digest=None):
        return containment.LegacyContainmentMarkerV1(
            1, True, True, TEST_CLASS, TEST_NAMESPACE, TEST_KEY, action_digest
        )

    def test_value_tuple_batch_and_historical_action_are_blocked(self):
        gate = self.gate()
        for payload, marker in (
            ({"content": "remember VEGA please"}, None),
            ({"operations": [{"content": "ORION PRIME"}]}, None),
            ({"content": "unrelated"}, self.marker()),
            ({"content": "unrelated"}, self.marker(action_digest=digest("historical-action"))),
        ):
            decision = gate.evaluate(payload, marker=marker)
            self.assertFalse(decision.allowed)
            self.assertEqual(decision.matched_identity, (TEST_CLASS, TEST_NAMESPACE, TEST_KEY))

    def test_unrelated_legacy_write_is_unchanged(self):
        self.assertTrue(self.gate().evaluate({"content": "ordinary note"}).allowed)

    def test_unavailable_registry_fails_closed_for_recognized_action(self):
        gate = containment.LegacyCanonicalContainmentGate(
            secret=b"c" * 32,
            registry_provider=lambda: (_ for _ in ()).throw(RuntimeError("unavailable")),
        )
        decision = gate.evaluate({"content": "anything"}, marker=self.marker())
        self.assertEqual(decision.failure_code, containment.LEGACY_CONTAINMENT_NOT_READY)

    def test_empty_or_nonmatching_registry_never_falls_through_recognized_action(self):
        empty = containment.LegacyCanonicalContainmentGate(
            secret=b"c" * 32, registry_provider=lambda: ()
        )
        decision = empty.evaluate({"content": "anything"}, marker=self.marker())
        self.assertFalse(decision.allowed)
        self.assertEqual(decision.failure_code, containment.LEGACY_CONTAINMENT_NOT_READY)

        unrelated = containment.make_protected_tuple(
            secret=b"c" * 32,
            memory_class="SYNTHETIC_OTHER_CLASS",
            subject_namespace="project.other",
            subject_key="other-key",
            protected_values=("ALTAIR",),
        )
        nonmatching = containment.LegacyCanonicalContainmentGate(
            secret=b"c" * 32, registry_provider=lambda: (unrelated,)
        )
        decision = nonmatching.evaluate(
            {"content": "anything"}, marker=self.marker()
        )
        self.assertFalse(decision.allowed)
        self.assertEqual(decision.failure_code, containment.LEGACY_CONTAINMENT_NOT_READY)

    def test_background_review_excludes_typed_memory_lane(self):
        marker = {
            "legacyContainment": {
                "schemaVersion": 1,
                "excludeFromLegacyBackgroundReview": True,
                "recognizedCanonicalAction": True,
                "memoryClass": TEST_CLASS,
                "subjectNamespace": TEST_NAMESPACE,
                "subjectKey": TEST_KEY,
                "actionDigest": digest("action"),
            }
        }
        messages = [{"content": "ordinary"}, {"content": "secret", "metadata": marker}]
        self.assertEqual(
            containment.filter_background_review_messages(messages),
            [{"content": "ordinary"}],
        )

    def test_legacy_memory_skill_and_pending_erasure_are_exact(self):
        memory_path = self.root / "MEMORY.md"
        user_path = self.root / "USER.md"
        skill_root = self.root / "skills"
        pending_root = self.root / "pending"
        skill_root.mkdir()
        pending_root.mkdir()
        memory_path.write_text("ordinary memory\nORION PRIME\n", encoding="utf-8")
        user_path.write_text("ordinary user\nVEGA\n", encoding="utf-8")
        (skill_root / "SKILL.md").write_text(
            "ordinary skill\nORION PRIME\n", encoding="utf-8"
        )
        pending = pending_root / "pending.json"
        pending.write_text(json.dumps({"content": "VEGA"}), encoding="utf-8")
        request, authorization, _ = self.forget(
            ("LEGACY_MEMORY", "LEGACY_SKILLS", "PENDING")
        )
        del request
        gate = self.gate()
        results = (
            containment.LegacyMemoryErasureOwner(
                memory_path, user_path, gate, self.privacy
            ).erase_authorized(
                authorization.authorization_ref_id,
                authorization.execution_nonce,
            ),
            containment.LegacySkillErasureOwner(
                skill_root, gate, self.privacy
            ).erase_authorized(
                authorization.authorization_ref_id,
                authorization.execution_nonce,
            ),
            containment.PendingErasureOwner(
                pending_root, gate, self.privacy
            ).erase_authorized(
                authorization.authorization_ref_id,
                authorization.execution_nonce,
            ),
        )
        self.privacy.complete(
            authorization.authorization_ref_id,
            authorization.execution_nonce,
        )
        self.assertTrue(all(result["status"] == "COMPLETE" for result in results))
        self.assertEqual(memory_path.read_text(encoding="utf-8"), "ordinary memory\n")
        self.assertEqual(user_path.read_text(encoding="utf-8"), "ordinary user\n")
        self.assertEqual(
            (skill_root / "SKILL.md").read_text(encoding="utf-8"),
            "ordinary skill\n",
        )
        self.assertFalse(pending.exists())

    def test_production_gate_rejects_missing_or_weak_server_secret_for_typed_lane(self):
        key = self.root / "containment.key"
        key.write_bytes(b"weak")
        marker = {
            "legacyContainment": {
                "schemaVersion": 1,
                "excludeFromLegacyBackgroundReview": True,
                "recognizedCanonicalAction": True,
                "memoryClass": TEST_CLASS,
                "subjectNamespace": TEST_NAMESPACE,
                "subjectKey": TEST_KEY,
                "actionDigest": digest("action"),
            }
        }
        containment._production_gate = None
        self.addCleanup(setattr, containment, "_production_gate", None)
        with mock.patch.dict(
            os.environ,
            {"LILITH_LEGACY_CONTAINMENT_KEY_FILE": str(key)},
            clear=False,
        ):
            decision = containment.check_legacy_payload(marker)
        self.assertFalse(decision.allowed)
        self.assertEqual(decision.failure_code, containment.LEGACY_CONTAINMENT_NOT_READY)


class TestStaticBoundaries(unittest.TestCase):
    PRODUCTION_MODULES = (
        "canonical_contracts.py",
        "canonical_authority.py",
        "learning_v2.py",
        "memory_v2.py",
        "privacy_governance.py",
        "legacy_canonical_containment.py",
        "slice15b2a_migration.py",
    )

    def sources(self):
        return {
            name: (HERE / name).read_text(encoding="utf-8")
            for name in self.PRODUCTION_MODULES
        }

    def test_no_real_acceptance_values_or_expansion_subsystems_in_production_code(self):
        combined = "\n".join(self.sources().values()).lower()
        for forbidden in (
            "blackstar",
            "nightfall",
            "eclipse",
            "qdrant",
            "chroma",
            "weaviate",
            "faiss",
            "neo4j",
            "telegram",
            "embedding column",
            "embedding job",
            "semantic index",
            "vector search",
            "graph edge",
        ):
            self.assertNotIn(forbidden, combined)

    def test_installer_scope_excludes_gateway_app_frontend_config_and_systemd(self):
        source = (HERE / "patch_slice15b2a.py").read_text(encoding="utf-8")
        main_body = source[source.index("def main()") :]
        for forbidden in (
            "gateway/run.py",
            "gateway_integration.py",
            "app.py",
            "router.yaml",
            "config.py",
            "src/",
            "systemd",
            "daemon-reload",
        ):
            self.assertNotIn(forbidden, main_body)
        self.assertIn(
            "refusal = _legacy_containment_guard(payload)",
            source[source.index("def patch_skill_manager") :],
        )

    def test_home_conversation_transport_has_no_memory_authority_lane(self):
        repo = HERE.parents[2]
        sources = (
            repo / "src" / "app" / "api" / "lilith" / "conversation" / "route.ts",
            repo / "src" / "lib" / "conversation" / "client.ts",
        )
        if not all(path.is_file() for path in sources):
            self.skipTest("repository Home transport source is unavailable")
        combined = "\n".join(path.read_text(encoding="utf-8") for path in sources)
        for forbidden in (
            "LOCAL_OWNER_AUTHORITY_V1",
            "ActorEvidenceRef",
            "canonical_memory.project_codename.mutate",
            "learning_memory_intent_v2",
            "learning_proposal_v2",
        ):
            self.assertNotIn(forbidden, combined)


class TestPrivacyGovernance(Slice15B2aCase):
    def test_forget_requires_grounded_actor_and_forget_operation(self):
        action, _ = self.action(operation=contracts.FORGET)
        with self.assertRaises(privacy_governance.PrivacyError):
            self.privacy.begin_forget(
                action=action,
                actor_evidence_ref_id="browser-session.synthetic",
                intent_ref_id="intent.untrusted",
                memory_item_id=None,
                resource_owners=("L04",),
                confirmation_event_ref="confirm.untrusted",
            )
        for operation, expected, restore in (
            (contracts.SUPERSEDE, "revision.current", None),
            (contracts.RESTORE, "revision.current", "revision.historical"),
        ):
            wrong, _ = self.action(
                operation=operation,
                expected=expected,
                restore=restore,
            )
            evidence = self.issue(wrong, nonce="nonce.wrong." + operation.lower())
            with self.assertRaises(privacy_governance.PrivacyError):
                self.privacy.begin_forget(
                    action=wrong,
                    actor_evidence_ref_id=evidence.actor_evidence_ref_id,
                    intent_ref_id="intent.wrong." + operation.lower(),
                    memory_item_id=None,
                    resource_owners=("L04",),
                    confirmation_event_ref="confirm.wrong",
                )
        counts = self._counts(self.privacy_db)
        self.assertEqual(counts["privacy_forget_request"], 0)
        self.assertEqual(counts["privacy_hold"], 0)

    def test_forget_creates_exact_hold_keyed_suppression_and_hmac_authorization(self):
        request, authorization, suppression = self.forget(("L18_V2",))
        self.assertEqual(request.identity, (TEST_CLASS, TEST_NAMESPACE, TEST_KEY))
        self.assertTrue(self.privacy.is_held(*request.identity))
        self.assertNotEqual(
            self.privacy.identity_selector(request.identity),
            hashlib.sha256("|".join(request.identity).encode()).hexdigest(),
        )
        self.assertTrue(suppression.startswith("suppress."))
        self.assertIsNone(
            self.privacy.resolve_erasure_authorization(
                authorization.authorization_ref_id,
                owner="L18_V2",
                execution_nonce="wrong",
            )
        )

    def test_partial_or_failed_erasure_cannot_complete_and_hold_remains(self):
        request, authorization, _ = self.forget(("L18_V2", "POLICY"))
        self.privacy.record_owner_result(
            authorization.authorization_ref_id,
            authorization.execution_nonce,
            {"owner": "L18_V2", "status": "COMPLETE"},
        )
        self.privacy.record_owner_result(
            authorization.authorization_ref_id,
            authorization.execution_nonce,
            {"owner": "POLICY", "status": "FAILED"},
        )
        with self.assertRaises(privacy_governance.PrivacyError):
            self.privacy.complete(
                authorization.authorization_ref_id, authorization.execution_nonce
            )
        self.assertTrue(self.privacy.is_held(*request.identity))

    def test_l04_and_l18_v1_privileged_erasure_removes_exact_lineage_only(self):
        item_id, proposal_ids, revision_ids = self.insert_l04_item(
            key=TEST_KEY,
            values=("ORION", "VEGA"),
            ordinal=1,
        )
        neighbor_id, neighbor_proposals, neighbor_revisions = self.insert_l04_item(
            key="neighbor",
            values=("ORION",),
            ordinal=2,
        )
        conn = sqlite3.connect(self.db)
        try:
            for statement, values in (
                ("DELETE FROM memory_item WHERE memory_item_id=?", (item_id,)),
                ("DELETE FROM memory_revision WHERE revision_id=?", (revision_ids[0],)),
                ("DELETE FROM learning_proposal WHERE proposal_id=?", (proposal_ids[0],)),
            ):
                with self.assertRaises(sqlite3.DatabaseError):
                    conn.execute(statement, values)
                conn.rollback()
        finally:
            conn.close()

        request, authorization, _ = self.forget(
            ("L04", "L18_V1"), memory_item_id=item_id
        )
        l04_result = memory_v2.L04PrivacyErasureOwner(
            self.db, self.privacy
        ).erase_authorized(
            authorization.authorization_ref_id,
            authorization.execution_nonce,
        )
        self.assertEqual(set(l04_result["proposalIds"]), set(proposal_ids))
        l18_result = memory_v2.L18V1PrivacyErasureOwner(
            self.db, self.privacy
        ).erase_authorized(
            authorization.authorization_ref_id,
            authorization.execution_nonce,
            proposal_ids=tuple(l04_result["proposalIds"]),
        )
        receipt = self.privacy.complete(
            authorization.authorization_ref_id,
            authorization.execution_nonce,
        )
        self.assertEqual(l18_result["deleted"], 2)
        self.assertEqual(receipt.verification_status, "COMPLETE")
        self.assertTrue(self.privacy.is_held(*request.identity))
        conn = sqlite3.connect(self.db)
        try:
            self.assertEqual(
                conn.execute(
                    "SELECT COUNT(*) FROM memory_item WHERE memory_item_id=?", (item_id,)
                ).fetchone()[0],
                0,
            )
            self.assertEqual(
                conn.execute(
                    "SELECT COUNT(*) FROM memory_revision WHERE revision_id IN (?,?)",
                    revision_ids,
                ).fetchone()[0],
                0,
            )
            self.assertEqual(
                conn.execute(
                    "SELECT COUNT(*) FROM learning_proposal WHERE proposal_id IN (?,?)",
                    proposal_ids,
                ).fetchone()[0],
                0,
            )
            self.assertEqual(
                conn.execute(
                    "SELECT COUNT(*) FROM learning_candidate WHERE idempotency_key LIKE ?",
                    (f"v1:{TEST_KEY}:%",),
                ).fetchone()[0],
                0,
            )
            self.assertEqual(
                conn.execute(
                    "SELECT COUNT(*) FROM memory_item WHERE memory_item_id=?",
                    (neighbor_id,),
                ).fetchone()[0],
                1,
            )
            self.assertEqual(
                conn.execute(
                    "SELECT COUNT(*) FROM memory_revision WHERE revision_id=?",
                    (neighbor_revisions[0],),
                ).fetchone()[0],
                1,
            )
            self.assertEqual(
                conn.execute(
                    "SELECT COUNT(*) FROM learning_proposal WHERE proposal_id=?",
                    (neighbor_proposals[0],),
                ).fetchone()[0],
                1,
            )
            self.assertEqual(conn.execute("PRAGMA integrity_check").fetchone()[0], "ok")
            self.assertEqual(conn.execute("PRAGMA foreign_key_check").fetchall(), [])
        finally:
            conn.close()

    def test_l18_v2_and_authority_owner_erasure_is_exact_and_minimized(self):
        self.v2_proposal(value="ORION", key=TEST_KEY, nonce="nonce.first")
        self.v2_proposal(value="VEGA", key="neighbor", nonce="nonce.neighbor")
        request, authorization, _ = self.forget(
            ("L18_V2", "POLICY", "CONSENT", "ACTOR_AUTHORITY")
        )
        results = []
        results.append(
            memory_v2.L18V2PrivacyErasureOwner(self.db, self.privacy).erase_authorized(
                authorization.authorization_ref_id, authorization.execution_nonce
            )
        )
        policy_result = authority.PolicyPrivacyErasureOwner(
            self.db, self.privacy
        ).erase_authorized(authorization.authorization_ref_id, authorization.execution_nonce)
        results.append(policy_result)
        consent_result = authority.ConsentPrivacyErasureOwner(
            self.db, self.privacy
        ).erase_authorized(authorization.authorization_ref_id, authorization.execution_nonce)
        results.append(consent_result)
        evidence_ids = tuple(
            sorted(
                set(policy_result["actorEvidenceRefIds"])
                | set(consent_result["actorEvidenceRefIds"])
            )
        )
        results.append(
            authority.ActorPrivacyErasureOwner(self.db, self.privacy).erase_authorized(
                authorization.authorization_ref_id,
                authorization.execution_nonce,
                actor_evidence_ref_ids=evidence_ids,
            )
        )
        receipt = self.privacy.complete(
            authorization.authorization_ref_id, authorization.execution_nonce
        )
        self.assertTrue(all(result["status"] == "COMPLETE" for result in results))
        self.assertEqual(receipt.verification_status, "COMPLETE")
        self.assertTrue(self.privacy.is_held(*request.identity))
        conn = sqlite3.connect(self.db)
        try:
            for table in (
                "learning_memory_intent_v2",
                "learning_project_codename_candidate_v1",
                "learning_proposal_v2",
                "policy_decision",
                "consent_grant",
            ):
                self.assertEqual(
                    conn.execute(
                        f"SELECT COUNT(*) FROM {table} WHERE subject_key=?",
                        (TEST_KEY,),
                    ).fetchone()[0],
                    0,
                )
                self.assertEqual(
                    conn.execute(
                        f"SELECT COUNT(*) FROM {table} WHERE subject_key='neighbor'"
                    ).fetchone()[0],
                    1,
                )
            self.assertEqual(
                conn.execute("SELECT COUNT(*) FROM learning_candidate_v2").fetchone()[0],
                1,
            )
            self.assertEqual(
                conn.execute("SELECT COUNT(*) FROM learning_candidate_source_v2").fetchone()[0],
                1,
            )
            self.assertEqual(
                conn.execute("SELECT COUNT(*) FROM learning_assessment_v2").fetchone()[0],
                1,
            )
            self.assertEqual(
                conn.execute("SELECT COUNT(*) FROM learning_proposal_ref").fetchone()[0],
                1,
            )
            self.assertEqual(conn.execute("PRAGMA integrity_check").fetchone()[0], "ok")
            self.assertEqual(conn.execute("PRAGMA foreign_key_check").fetchall(), [])
        finally:
            conn.close()
        conn = sqlite3.connect(self.privacy_db)
        conn.row_factory = sqlite3.Row
        try:
            receipt_row = conn.execute(
                "SELECT * FROM privacy_completion_receipt WHERE receipt_id=?",
                (receipt.receipt_id,),
            ).fetchone()
            self.assertEqual(
                set(dict(receipt_row)),
                {
                    "receipt_id",
                    "authority_version",
                    "completed_at",
                    "restore_suppression_ref",
                    "verification_status",
                    "receipt_fingerprint",
                },
            )
        finally:
            conn.close()
        encoded_privacy = self.privacy_db.read_bytes()
        self.assertNotIn(b"ORION", encoded_privacy)
        self.assertNotIn(TEST_KEY.encode(), encoded_privacy)

    def test_restore_suppression_verifier_erases_restored_identity_before_ready(self):
        request, authorization, _ = self.forget(("L18_V2",))
        self.privacy.record_owner_result(
            authorization.authorization_ref_id,
            authorization.execution_nonce,
            {"owner": "L18_V2", "status": "COMPLETE"},
        )
        self.privacy.complete(
            authorization.authorization_ref_id, authorization.execution_nonce
        )

        class RestoredOwner:
            def __init__(self, identity):
                self.identities = [identity]

            def list_identities(self):
                return tuple(self.identities)

            def erase_restore_suppressed(self, identity, privacy_store):
                if not privacy_store.suppression_matches(identity):
                    raise PermissionError
                self.identities.remove(identity)

        restored = RestoredOwner(request.identity)
        outcome = privacy_governance.RestoreSuppressionVerifier(
            self.privacy, restored
        ).verify_and_apply()
        self.assertTrue(outcome.ready_to_serve)
        self.assertEqual((outcome.matched_identities, outcome.suppressed_identities), (1, 1))

    def test_backup_retention_is_bounded_and_never_auto_deletes(self):
        backup = self.root / "old.db"
        backup.write_bytes(b"fixture")
        old = stamp() - timedelta(days=31)
        os.utime(backup, (old.timestamp(), old.timestamp()))
        expired = privacy_governance.validate_backup_retention(
            (backup,), now=stamp(), max_days=30
        )
        self.assertEqual(expired, (backup,))
        self.assertTrue(backup.exists())


if __name__ == "__main__":
    unittest.main(verbosity=2)
