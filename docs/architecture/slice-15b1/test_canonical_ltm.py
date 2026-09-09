"""Slice 15B1 canonical LTM foundation tests.

Every write uses a disposable SQLite database.  The synthetic registry and
authority fixtures exist only in this test module and cannot be selected by
production construction.
"""

from __future__ import annotations

import ast
import dataclasses
import hashlib
import json
import os
import sqlite3
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

HERE = Path(__file__).resolve().parent
MODULE_ROOT = HERE if (HERE / "memory_store.py").exists() else HERE.parent
if str(MODULE_ROOT) not in sys.path:
    sys.path.insert(0, str(MODULE_ROOT))

import learning
import learning_store
import learning_worker
import memory_contracts as C
import memory_store


SOURCE_SCHEMA = """
CREATE TABLE career_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_type TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    entity_id INTEGER,
    source TEXT,
    confidence REAL NOT NULL DEFAULT 0.0,
    payload_json TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    processed INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX idx_career_events_type ON career_events(event_type);
"""

TEST_CLASS = "SYNTHETIC_ACCEPTANCE"
TEST_NAMESPACE = "test.semantic"
TEST_SCHEMA = "test.assertion.v1"


def stamp(seconds: int = 0) -> str:
    base = datetime(2026, 9, 9, 15, 0, tzinfo=timezone.utc) + timedelta(seconds=seconds)
    return base.isoformat(timespec="microseconds").replace("+00:00", "Z")


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def make_source(path: Path, count: int = 8) -> None:
    conn = sqlite3.connect(path)
    try:
        conn.executescript(SOURCE_SCHEMA)
        stages = ("applied", "interview", "rejected", "offer")
        for index in range(1, count + 1):
            conn.execute(
                "INSERT INTO career_events(id,event_type,entity_type,entity_id,source,confidence,"
                "payload_json,created_at,processed) VALUES (?,?,?,?,?,?,?,?,?)",
                (
                    index, f"career.{stages[(index - 1) % len(stages)]}",
                    "job_application", 500 + index, "gmail", 0.91,
                    json.dumps({"private": "NEVER_COPY"}),
                    f"2026-09-09 15:00:{index:02d}", 0,
                ),
            )
        conn.commit()
    finally:
        conn.close()


def normalize_test(value):
    if not isinstance(value, dict) or set(value) != {"kind", "value"}:
        raise ValueError("closed synthetic value required")
    if value["kind"] != "TEST_ASSERTION":
        raise ValueError("unknown synthetic assertion kind")
    if not isinstance(value["value"], str) or not 1 <= len(value["value"]) <= 32:
        raise ValueError("synthetic value is invalid")
    return {"kind": "TEST_ASSERTION", "value": value["value"]}


def registry(*, consent=False, verification=False):
    return memory_store.MemoryRegistry((memory_store.MemoryClassPolicy(
        memory_class=TEST_CLASS,
        subject_namespace=TEST_NAMESPACE,
        value_schema=TEST_SCHEMA,
        normalize=normalize_test,
        requires_consent=consent,
        requires_verification=verification,
    ),))


class FixtureResolver:
    def __init__(self, values=None):
        self.values = dict(values or {})

    def resolve(self, reference_id, *, proposal, value_digest):
        del proposal, value_digest
        return memory_store.AuthorityResolution(
            self.values.get(reference_id, memory_store.INVALID)
        )


class WorkerConfig:
    memory_consolidation_enabled = True
    memory_consolidation_mode = "shadow"

    def __init__(self, trace):
        self.trace = trace

    def resolved_log_path(self):
        return self.trace


class FoundationCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.source = self.root / "lilith.db"
        self.db = self.root / "cognitive_memory_test.db"
        self.trace = self.root / "learning.log"
        make_source(self.source)
        learning_store.migrate(self.db, applied_at=stamp())
        result = learning_worker.run_once(
            source_db=self.source,
            learning_db=self.db,
            cfg=WorkerConfig(self.trace),
            limit=8,
            now_fn=lambda: stamp(),
        )
        self.assertEqual(result["status"], learning_store.SUCCEEDED)
        memory_store.migrate(
            self.db, applied_at=stamp(1),
            production_path=self.root / "not-production.db",
        )
        self.rollback = FixtureResolver({"rollback.test": memory_store.CONFIRMED})

    def tearDown(self):
        self.tmp.cleanup()

    def candidate(self, source_id):
        row = learning.CareerEventsSource(self.source).read_batch(source_id - 1, 1)[0]
        source_ref, descriptor = learning.build_source_record_ref(row)
        candidate = learning.derive_candidate(source_ref, descriptor, stamp(source_id))
        return source_ref, candidate

    def proposal(
        self,
        source_id,
        operation,
        *,
        key="fixture-one",
        value=None,
        expected=None,
        restore=None,
        memory_class=TEST_CLASS,
        namespace=TEST_NAMESPACE,
        value_schema=TEST_SCHEMA,
        consent_ref=None,
        verification_ref=None,
        rollback_ref=None,
    ):
        source_ref, candidate = self.candidate(source_id)
        proposal = learning.derive_memory_write_proposal(
            candidate,
            source_ref,
            proposal_id=f"lprop.fixture.{source_id}",
            operation=operation,
            target_memory_class=memory_class,
            subject_namespace=namespace,
            subject_key=key,
            proposed_value=value,
            value_schema=value_schema if operation != C.RESTORE else None,
            expected_active_revision_id=expected,
            restore_revision_id=restore,
            consent_ref_id=consent_ref,
            verification_outcome_ref_id=verification_ref,
            rollback_authorization_ref_id=rollback_ref,
            admission_basis="SYNTHETIC_ACCEPTANCE",
            epistemic_basis="CONTROLLED_IMPORT",
            created_at=stamp(10 + source_id),
        )
        learning_store.LearningStore(self.db).insert_proposal(proposal)
        return proposal

    def l04(
        self,
        *,
        enabled=True,
        selected_registry=None,
        consent=None,
        verifier=None,
        rollback=None,
        capacity=100,
        trace=None,
        fault=None,
    ):
        return memory_store.MemoryStore(
            self.db,
            enabled_provider=lambda: enabled,
            registry=selected_registry if selected_registry is not None else registry(),
            consent_resolver=consent,
            verifier_resolver=verifier,
            rollback_resolver=rollback if rollback is not None else self.rollback,
            capacity=capacity,
            trace_sink=trace,
            now_fn=lambda: stamp(30),
            fault_hook=fault,
        )

    def create(self, source_id=1, key="fixture-one", value="alpha", **store_args):
        proposal = self.proposal(
            source_id, C.CREATE, key=key,
            value={"kind": "TEST_ASSERTION", "value": value},
        )
        return proposal, self.l04(**store_args).apply(proposal.proposal_id)


class TestCanonicalDefinitionAndContracts(FoundationCase):
    def test_candidate_proposal_admission_apply_are_distinct(self):
        proposal, result = self.create()
        self.assertIsInstance(proposal, C.MemoryWriteProposal)
        self.assertIsInstance(result, C.MemoryApplyResult)
        conn = sqlite3.connect(self.db)
        try:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM learning_candidate").fetchone()[0], 8)
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM learning_proposal").fetchone()[0], 1)
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM memory_admission").fetchone()[0], 1)
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM memory_apply_audit").fetchone()[0], 1)
        finally:
            conn.close()

    def test_proposal_schema_is_closed_and_has_no_confidence_or_metadata(self):
        proposal = self.proposal(1, C.CREATE, value={"kind": "TEST_ASSERTION", "value": "a"})
        keys = set(proposal.to_dict())
        self.assertNotIn("confidence", {key.lower() for key in keys})
        self.assertNotIn("metadata", {key.lower() for key in keys})
        self.assertNotIn("revisionId", keys)
        self.assertNotIn("activeRevisionId", keys)

    def test_item_and_revision_identifiers_are_distinct(self):
        _, result = self.create()
        self.assertNotEqual(result.memory_item_id, result.revision_id)

    def test_operations_exclude_delete_and_expire(self):
        self.assertEqual(C.MEMORY_OPERATIONS, {"CREATE", "SUPERSEDE", "RESTORE"})

    def test_no_fuzzy_identity_or_dedup(self):
        _, first = self.create(1, key="Exact.Key")
        _, second = self.create(2, key="exact.key")
        self.assertNotEqual(first.memory_item_id, second.memory_item_id)

    def test_value_schema_is_closed(self):
        proposal = self.proposal(
            1, C.CREATE,
            value={"kind": "TEST_ASSERTION", "value": "a", "extra": "blocked"},
        )
        result = self.l04().apply(proposal.proposal_id)
        self.assertEqual((result.outcome, result.failure_code), (memory_store.REJECTED, "INVALID_PROPOSAL"))

    def test_no_raw_source_payload_enters_memory_database(self):
        self.create()
        encoded = self.db.read_bytes().lower()
        self.assertNotIn(b"never_copy", encoded)


class TestCreateSupersedeRestore(FoundationCase):
    def test_create_and_replay_are_idempotent(self):
        proposal, first = self.create()
        second = self.l04().apply(proposal.proposal_id)
        self.assertEqual(first.outcome, memory_store.APPLIED)
        self.assertEqual(second.outcome, memory_store.ALREADY_APPLIED)
        self.assertEqual(first.revision_id, second.revision_id)
        self.assertEqual(self.l04().counts()["memory_revision"], 1)
        self.assertEqual(self.l04().counts()["memory_admission"], 1)

    def test_supersede_preserves_prior_revision(self):
        _, created = self.create()
        proposal = self.proposal(
            2, C.SUPERSEDE, expected=created.revision_id,
            value={"kind": "TEST_ASSERTION", "value": "beta"},
        )
        result = self.l04().apply(proposal.proposal_id)
        lineage = self.l04().get_lineage(created.memory_item_id)
        self.assertEqual(result.outcome, memory_store.APPLIED)
        self.assertEqual(len(lineage), 2)
        self.assertEqual(lineage[1]["supersedes_revision_id"], created.revision_id)
        self.assertEqual(self.l04().get_active(TEST_CLASS, TEST_NAMESPACE, "fixture-one")["revision_id"], result.revision_id)

    def test_stale_expected_revision_fails_without_partial_write(self):
        _, created = self.create()
        second = self.proposal(
            2, C.SUPERSEDE, expected=created.revision_id,
            value={"kind": "TEST_ASSERTION", "value": "beta"},
        )
        applied = self.l04().apply(second.proposal_id)
        stale = self.proposal(
            3, C.SUPERSEDE, expected=created.revision_id,
            value={"kind": "TEST_ASSERTION", "value": "gamma"},
        )
        result = self.l04().apply(stale.proposal_id)
        self.assertEqual((result.outcome, result.failure_code), (memory_store.PRECONDITION_FAILED, "ACTIVE_REVISION_MISMATCH"))
        self.assertEqual(len(self.l04().get_lineage(created.memory_item_id)), 2)
        self.assertEqual(self.l04().get_active(TEST_CLASS, TEST_NAMESPACE, "fixture-one")["revision_id"], applied.revision_id)

    def test_restore_creates_new_revision_and_never_repoints(self):
        _, first = self.create()
        second_p = self.proposal(
            2, C.SUPERSEDE, expected=first.revision_id,
            value={"kind": "TEST_ASSERTION", "value": "beta"},
        )
        second = self.l04().apply(second_p.proposal_id)
        restore_p = self.proposal(
            3, C.RESTORE, expected=second.revision_id, restore=first.revision_id,
            rollback_ref="rollback.test",
        )
        restored = self.l04().apply(restore_p.proposal_id)
        lineage = self.l04().get_lineage(first.memory_item_id)
        self.assertEqual(restored.outcome, memory_store.APPLIED)
        self.assertNotIn(restored.revision_id, {first.revision_id, second.revision_id})
        self.assertEqual(lineage[-1]["supersedes_revision_id"], second.revision_id)
        self.assertEqual(lineage[-1]["restores_revision_id"], first.revision_id)
        self.assertEqual(lineage[-1]["normalized_value_json"], lineage[0]["normalized_value_json"])
        replay = self.l04().apply(restore_p.proposal_id)
        self.assertEqual((replay.outcome, replay.revision_id), (memory_store.ALREADY_APPLIED, restored.revision_id))

    def test_cross_item_restore_fails(self):
        _, first = self.create(1, key="one")
        _, second = self.create(2, key="two")
        proposal = self.proposal(
            3, C.RESTORE, key="two", expected=second.revision_id,
            restore=first.revision_id, rollback_ref="rollback.test",
        )
        result = self.l04().apply(proposal.proposal_id)
        self.assertEqual((result.outcome, result.failure_code), (memory_store.PRECONDITION_FAILED, "RESTORE_ITEM_MISMATCH"))
        self.assertEqual(len(self.l04().get_lineage(second.memory_item_id)), 1)

    def test_restore_requires_authority(self):
        _, first = self.create()
        second_p = self.proposal(
            2, C.SUPERSEDE, expected=first.revision_id,
            value={"kind": "TEST_ASSERTION", "value": "beta"},
        )
        second = self.l04().apply(second_p.proposal_id)
        proposal = self.proposal(
            3, C.RESTORE, expected=second.revision_id,
            restore=first.revision_id, rollback_ref="rollback.missing",
        )
        result = self.l04(rollback=memory_store.UnavailableAuthorityResolver()).apply(proposal.proposal_id)
        self.assertEqual(result.failure_code, "ROLLBACK_AUTHORITY_UNAVAILABLE")
        self.assertEqual(len(self.l04().get_lineage(first.memory_item_id)), 2)

    def test_transaction_failure_rolls_back_every_memory_row(self):
        proposal = self.proposal(
            1, C.CREATE, value={"kind": "TEST_ASSERTION", "value": "alpha"},
        )
        def fail(point):
            if point == "after_revision":
                raise RuntimeError("forced")
        with self.assertRaises(RuntimeError):
            self.l04(fault=fail).apply(proposal.proposal_id)
        counts = self.l04().counts()
        for table in (
            "memory_item", "memory_revision", "memory_revision_source",
            "memory_active_revision", "memory_admission", "memory_apply_audit",
        ):
            self.assertEqual(counts[table], 0)


class TestKillSwitchAndRegistries(FoundationCase):
    def test_disabled_direct_apply_has_zero_mutation(self):
        proposal = self.proposal(
            1, C.CREATE, value={"kind": "TEST_ASSERTION", "value": "alpha"},
        )
        before = self.l04().counts()
        before_hash = file_hash(self.db)
        result = self.l04(enabled=False).apply(proposal.proposal_id)
        self.assertEqual(result.failure_code, "CANONICAL_LTM_DISABLED")
        self.assertEqual(self.l04().counts(), before)
        self.assertEqual(file_hash(self.db), before_hash)

    def test_missing_malformed_and_unknown_enabled_values_fail_closed(self):
        proposal = self.proposal(
            1, C.CREATE, value={"kind": "TEST_ASSERTION", "value": "alpha"},
        )
        for value in (None, "true", 1, {}, object()):
            result = self.l04(enabled=value).apply(proposal.proposal_id)
            self.assertEqual(result.failure_code, "CANONICAL_LTM_DISABLED")
        self.assertEqual(self.l04().counts()["memory_revision"], 0)

    def test_production_registry_is_empty(self):
        store = memory_store.MemoryStore.production(self.db)
        self.assertEqual(store.registry.active_keys(), ())

    def test_empty_registry_rejects_test_class_even_if_enabled(self):
        proposal = self.proposal(
            1, C.CREATE, value={"kind": "TEST_ASSERTION", "value": "alpha"},
        )
        result = self.l04(selected_registry=memory_store.MemoryRegistry()).apply(proposal.proposal_id)
        self.assertEqual(result.failure_code, "UNKNOWN_MEMORY_CLASS")

    def test_nonempty_registry_cannot_target_production_path(self):
        with self.assertRaises(ValueError):
            memory_store.MemoryStore(
                self.db,
                enabled_provider=lambda: True,
                registry=registry(),
                production_path=self.db,
            )

    def test_test_database_guard_rejects_production_path(self):
        with self.assertRaises(ValueError):
            memory_store.assert_isolated_test_database(self.db, self.db)
        memory_store.assert_isolated_test_database(self.db, self.root / "production.db")

    def test_safe_trace_contains_only_allowlisted_metadata(self):
        proposal = self.proposal(
            1, C.CREATE, value={"kind": "TEST_ASSERTION", "value": "secret-value"},
        )
        events = []
        self.l04(trace=events.append).apply(proposal.proposal_id)
        self.assertEqual(set(events[0]), {
            "lane", "proposalId", "operation", "admissionOutcome", "failureCode",
            "memoryClass", "revisionId", "priorRevisionId", "durationMs", "mode",
            "schemaVersion",
        })
        self.assertNotIn("secret-value", json.dumps(events))


class TestExternalAuthorities(FoundationCase):
    def test_missing_consent_fails_closed(self):
        proposal = self.proposal(
            1, C.CREATE, value={"kind": "TEST_ASSERTION", "value": "alpha"},
            consent_ref="consent.missing",
        )
        result = self.l04(selected_registry=registry(consent=True)).apply(proposal.proposal_id)
        self.assertEqual(result.failure_code, "CONSENT_AUTHORITY_UNAVAILABLE")

    def test_invalid_and_revoked_consent_fail_closed(self):
        for source_id, state in ((1, memory_store.INVALID), (2, memory_store.REVOKED)):
            proposal = self.proposal(
                source_id, C.CREATE, key=f"key-{source_id}",
                value={"kind": "TEST_ASSERTION", "value": "alpha"},
                consent_ref=f"consent.{source_id}",
            )
            result = self.l04(
                selected_registry=registry(consent=True),
                consent=FixtureResolver({f"consent.{source_id}": state}),
            ).apply(proposal.proposal_id)
            self.assertEqual(result.failure_code, "CONSENT_INVALID")

    def test_test_consent_fixture_can_confirm_only_explicit_reference(self):
        proposal = self.proposal(
            1, C.CREATE, value={"kind": "TEST_ASSERTION", "value": "alpha"},
            consent_ref="consent.test",
        )
        result = self.l04(
            selected_registry=registry(consent=True),
            consent=FixtureResolver({"consent.test": memory_store.CONFIRMED}),
        ).apply(proposal.proposal_id)
        self.assertEqual(result.outcome, memory_store.APPLIED)

    def test_missing_verifier_fails_procedural_like_policy(self):
        proposal = self.proposal(
            1, C.CREATE, value={"kind": "TEST_ASSERTION", "value": "alpha"},
            verification_ref="verify.command.exit0",
        )
        result = self.l04(selected_registry=registry(verification=True)).apply(proposal.proposal_id)
        self.assertEqual(result.failure_code, "VERIFIER_UNAVAILABLE")

    def test_task_http_and_exit_status_are_not_proof(self):
        for source_id, reference in enumerate(("Task.COMPLETED", "HTTP.200", "exit_code.0"), 1):
            proposal = self.proposal(
                source_id, C.CREATE, key=f"proof-{source_id}",
                value={"kind": "TEST_ASSERTION", "value": "alpha"},
                verification_ref=reference,
            )
            result = self.l04(selected_registry=registry(verification=True)).apply(proposal.proposal_id)
            self.assertEqual(result.failure_code, "VERIFIER_UNAVAILABLE")


class TestProposalBindingAndImmutability(FoundationCase):
    def test_proposal_fingerprint_ignores_generated_id_and_timestamp(self):
        source_ref, candidate = self.candidate(1)
        first = learning.derive_memory_write_proposal(
            candidate, source_ref, proposal_id="lprop.one", operation=C.CREATE,
            target_memory_class=TEST_CLASS, subject_namespace=TEST_NAMESPACE,
            subject_key="key", value_schema=TEST_SCHEMA,
            proposed_value={"kind": "TEST_ASSERTION", "value": "a"},
            admission_basis="SYNTHETIC_ACCEPTANCE", epistemic_basis="CONTROLLED_IMPORT",
            created_at=stamp(1),
        )
        second = dataclasses.replace(first, proposal_id="lprop.two", created_at=stamp(99))
        binding = learning.candidate_provenance_binding(candidate, source_ref)
        timestamp_changed_binding = dataclasses.replace(binding, occurred_at=stamp(88))
        self.assertEqual(
            C.compute_proposal_fingerprint(first, binding),
            C.compute_proposal_fingerprint(second, timestamp_changed_binding),
        )

    def test_each_authority_semantic_changes_fingerprint(self):
        source_ref, candidate = self.candidate(1)
        base = learning.derive_memory_write_proposal(
            candidate, source_ref, proposal_id="lprop.one", operation=C.CREATE,
            target_memory_class=TEST_CLASS, subject_namespace=TEST_NAMESPACE,
            subject_key="key", value_schema=TEST_SCHEMA,
            proposed_value={"kind": "TEST_ASSERTION", "value": "a"},
            admission_basis="SYNTHETIC_ACCEPTANCE", epistemic_basis="CONTROLLED_IMPORT",
            created_at=stamp(1),
        )
        binding = learning.candidate_provenance_binding(candidate, source_ref)
        for field, value in (
            ("consent_ref_id", "consent.x"),
            ("verification_outcome_ref_id", "verify.x"),
        ):
            changed = dataclasses.replace(base, **{field: value})
            self.assertNotEqual(
                C.compute_proposal_fingerprint(base, binding),
                C.compute_proposal_fingerprint(changed, binding),
            )

    def test_proposal_and_candidate_rows_are_immutable(self):
        proposal = self.proposal(
            1, C.CREATE, value={"kind": "TEST_ASSERTION", "value": "alpha"},
        )
        conn = sqlite3.connect(self.db)
        try:
            with self.assertRaises(sqlite3.DatabaseError):
                conn.execute("UPDATE learning_proposal SET subject_key='changed' WHERE proposal_id=?", (proposal.proposal_id,))
            with self.assertRaises(sqlite3.DatabaseError):
                conn.execute("UPDATE learning_candidate SET subject_ref='changed' WHERE candidate_id=?", (proposal.candidate_id,))
            with self.assertRaises(sqlite3.DatabaseError):
                conn.execute("UPDATE learning_candidate_source SET source_digest=? WHERE candidate_id=?", ("0" * 64, proposal.candidate_id))
        finally:
            conn.close()

    def test_rejected_proposal_never_later_applies(self):
        proposal = self.proposal(
            1, C.CREATE, memory_class="UNKNOWN_CLASS",
            value={"kind": "TEST_ASSERTION", "value": "alpha"},
        )
        first = self.l04().apply(proposal.proposal_id)
        second = self.l04(selected_registry=memory_store.MemoryRegistry((memory_store.MemoryClassPolicy(
            "UNKNOWN_CLASS", TEST_NAMESPACE, TEST_SCHEMA, normalize_test,
        ),))).apply(proposal.proposal_id)
        self.assertEqual(first.failure_code, "UNKNOWN_MEMORY_CLASS")
        self.assertEqual((second.outcome, second.failure_code), (memory_store.REJECTED, "UNKNOWN_MEMORY_CLASS"))

    def test_revision_admission_audit_and_provenance_are_immutable(self):
        _, result = self.create()
        conn = sqlite3.connect(self.db)
        try:
            for sql, args in (
                ("UPDATE memory_revision SET value_digest=? WHERE revision_id=?", ("0" * 64, result.revision_id)),
                ("UPDATE memory_admission SET outcome='REJECTED' WHERE proposal_id=?", ("lprop.fixture.1",)),
                ("DELETE FROM memory_apply_audit WHERE proposal_id=?", ("lprop.fixture.1",)),
                ("UPDATE memory_revision_source SET source_owner='OTHER' WHERE revision_id=?", (result.revision_id,)),
            ):
                with self.assertRaises(sqlite3.DatabaseError):
                    conn.execute(sql, args)
        finally:
            conn.close()


class TestScopedSqlOwnership(FoundationCase):
    def test_l18_runtime_cannot_read_or_write_memory_tables(self):
        conn = learning_store.LearningStore(self.db).connect()
        try:
            with self.assertRaises(sqlite3.DatabaseError):
                conn.execute("SELECT * FROM memory_item").fetchall()
            with self.assertRaises(sqlite3.DatabaseError):
                conn.execute(
                    "INSERT INTO memory_item(memory_item_id,memory_class,subject_namespace,subject_key,created_at) "
                    "VALUES ('x','X','x','x','x')"
                )
        finally:
            conn.close()

    def test_l04_runtime_cannot_write_learning_tables(self):
        conn = self.l04()._connect()
        try:
            with self.assertRaises(sqlite3.DatabaseError):
                conn.execute("UPDATE learning_candidate SET subject_ref='x'")
        finally:
            conn.close()

    def test_l04_can_read_only_approved_learning_tables(self):
        conn = self.l04()._connect()
        try:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM learning_proposal").fetchone()[0], 0)
            with self.assertRaises(sqlite3.DatabaseError):
                conn.execute("SELECT * FROM learning_job").fetchall()
        finally:
            conn.close()


class TestMigrationSafety(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_empty_database_migrates_and_repeat_is_idempotent(self):
        db = self.root / "empty.db"
        first = memory_store.migrate(db, applied_at=stamp(), production_path=self.root / "prod.db")
        second = memory_store.migrate(db, applied_at=stamp(1), production_path=self.root / "prod.db")
        self.assertEqual(first, second)
        conn = sqlite3.connect(db)
        try:
            self.assertEqual(conn.execute("PRAGMA integrity_check").fetchone()[0], "ok")
            self.assertEqual(conn.execute("PRAGMA foreign_key_check").fetchall(), [])
        finally:
            conn.close()

    def test_existing_zero_table_database_migrates(self):
        db = self.root / "zero-table.db"
        sqlite3.connect(db).close()
        memory_store.migrate(db, production_path=self.root / "prod.db")
        conn = sqlite3.connect(db)
        try:
            tables = {row[0] for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
            )}
        finally:
            conn.close()
        self.assertEqual(tables, memory_store.ALL_15B1_TABLES)

    def test_slice15a_rows_and_cursor_are_preserved(self):
        source = self.root / "source.db"
        db = self.root / "ledger.db"
        make_source(source, 3)
        learning_store.migrate(db, applied_at=stamp())
        learning_worker.run_once(
            source_db=source, learning_db=db, cfg=WorkerConfig(self.root / "trace.log"),
            limit=3, now_fn=lambda: stamp(),
        )
        before = learning_store.LearningStore(db).counts()
        cursor = learning_store.LearningStore(db).get_cursor()
        memory_store.migrate(db, applied_at=stamp(1), production_path=self.root / "prod.db")
        self.assertEqual(learning_store.LearningStore(db).counts(), before)
        self.assertEqual(learning_store.LearningStore(db).get_cursor(), cursor)

    def test_slice15a_worker_remains_operational_after_l04_migration(self):
        source = self.root / "source-after.db"
        db = self.root / "ledger-after.db"
        make_source(source, 4)
        learning_store.migrate(db, applied_at=stamp())
        learning_worker.run_once(
            source_db=source, learning_db=db, cfg=WorkerConfig(self.root / "trace-after.log"),
            limit=3, now_fn=lambda: stamp(),
        )
        memory_store.migrate(db, applied_at=stamp(1), production_path=self.root / "prod.db")
        result = learning_worker.run_once(
            source_db=source, learning_db=db, cfg=WorkerConfig(self.root / "trace-after.log"),
            limit=3, now_fn=lambda: stamp(2),
        )
        self.assertEqual(result["status"], learning_store.SUCCEEDED)
        self.assertEqual(result["insertedCount"], 1)
        self.assertEqual(learning_store.LearningStore(db).get_cursor(), 4)

    def test_production_path_requires_verified_backup(self):
        db = self.root / "production.db"
        learning_store.migrate(db, applied_at=stamp())
        with self.assertRaises(memory_store.BackupRequired):
            memory_store.migrate(db, production_path=db)
        backup = self.root / "production.backup.db"
        proof = memory_store.create_verified_backup(db, backup)
        fingerprints = memory_store.migrate(db, verified_backup=proof, production_path=db)
        self.assertEqual(len(fingerprints), 2)
        self.assertEqual(proof.backup_integrity, "ok")

    def test_backup_checksum_integrity_and_permissions(self):
        db = self.root / "source.db"
        learning_store.migrate(db, applied_at=stamp())
        proof = memory_store.create_verified_backup(db, self.root / "backup.db")
        self.assertEqual(proof.backup_sha256, file_hash(Path(proof.backup_path)))
        self.assertEqual(proof.backup_integrity, "ok")
        if os.name != "nt":
            self.assertEqual(proof.backup_mode, 0o600)

    def test_malformed_prior_schema_fails_closed(self):
        db = self.root / "bad.db"
        conn = sqlite3.connect(db)
        try:
            conn.execute("CREATE TABLE learning_candidate(candidate_id TEXT)")
            conn.commit()
        finally:
            conn.close()
        with self.assertRaises(memory_store.MemorySchemaError):
            memory_store.migrate(db, production_path=self.root / "prod.db")

    def test_migration_creates_only_approved_tables(self):
        db = self.root / "schema.db"
        memory_store.migrate(db, production_path=self.root / "prod.db")
        conn = sqlite3.connect(db)
        try:
            tables = {row[0] for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
            )}
        finally:
            conn.close()
        self.assertEqual(tables, memory_store.ALL_15B1_TABLES)
        for forbidden in (
            "memory_trace", "memory_embedding", "memory_rank", "memory_summary",
            "memory_confidence", "memory_expiry", "memory_delete_queue",
            "privacy_erasure", "personalization", "procedural_skill",
        ):
            self.assertNotIn(forbidden, tables)


class TestRetrievalCapacityAndPersistence(FoundationCase):
    def test_exact_key_returns_active_revision_only(self):
        _, first = self.create()
        proposal = self.proposal(
            2, C.SUPERSEDE, expected=first.revision_id,
            value={"kind": "TEST_ASSERTION", "value": "beta"},
        )
        second = self.l04().apply(proposal.proposal_id)
        active = self.l04().get_active(TEST_CLASS, TEST_NAMESPACE, "fixture-one")
        self.assertEqual(active["revision_id"], second.revision_id)
        self.assertEqual(json.loads(active["normalized_value_json"])["value"], "beta")
        self.assertIsNone(self.l04().get_active(TEST_CLASS, TEST_NAMESPACE, "missing"))

    def test_lineage_and_explanation_are_complete_and_bounded(self):
        _, result = self.create()
        lineage = self.l04().get_lineage(result.memory_item_id)
        explanation = self.l04().explain(result.revision_id)
        self.assertEqual(len(lineage), 1)
        self.assertEqual(explanation["revision"]["candidate_id"], "lcand." + self.candidate(1)[1].candidate_id.split(".", 1)[1])
        self.assertEqual(set(explanation["sources"][0]), {
            "source_owner", "source_stream", "source_record_id", "source_schema_version",
            "source_digest", "occurred_at", "subject_ref",
        })

    def test_candidates_and_legacy_memory_are_not_retrieval_results(self):
        _, result = self.create()
        active = json.dumps(self.l04().get_active(TEST_CLASS, TEST_NAMESPACE, "fixture-one")).lower()
        self.assertNotIn("candidate_class", active)
        self.assertNotIn("memory.md", active)
        self.assertNotIn("user.md", active)
        self.assertEqual(self.l04().get_revision(result.revision_id)["revision_id"], result.revision_id)

    def test_capacity_pauses_without_deletion(self):
        _, first = self.create(capacity=1)
        proposal = self.proposal(
            2, C.CREATE, key="second",
            value={"kind": "TEST_ASSERTION", "value": "beta"},
        )
        result = self.l04(capacity=1).apply(proposal.proposal_id)
        self.assertEqual(result.failure_code, "CAPACITY_PAUSED")
        self.assertEqual(self.l04().counts()["memory_item"], 1)
        self.assertIsNotNone(self.l04().get_revision(first.revision_id))

    def test_database_reopen_preserves_active_revision(self):
        _, result = self.create()
        reopened = self.l04()
        self.assertEqual(
            reopened.get_active(TEST_CLASS, TEST_NAMESPACE, "fixture-one")["revision_id"],
            result.revision_id,
        )


class TestStaticBoundaries(unittest.TestCase):
    MODULES = (
        "memory_contracts.py", "learning.py", "learning_store.py", "learning_worker.py",
        "memory_store.py",
    )

    def sources(self):
        return {name: (MODULE_ROOT / name).read_text(encoding="utf-8") for name in self.MODULES}

    def test_no_model_network_connector_or_process_imports(self):
        forbidden = {"openai", "anthropic", "requests", "httpx", "socket", "subprocess", "model_tools"}
        for name, source in self.sources().items():
            tree = ast.parse(source)
            imports = set()
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    imports.update(alias.name.split(".")[0] for alias in node.names)
                elif isinstance(node, ast.ImportFrom) and node.module:
                    imports.add(node.module.split(".")[0])
            self.assertTrue(imports.isdisjoint(forbidden), (name, imports & forbidden))

    def test_no_legacy_prompt_world_goal_policy_soul_or_gateway_integration(self):
        lower = "\n".join(self.sources().values()).lower()
        for forbidden in (
            "memory.md", "user.md", "memory_tool", "skill_manage", "background_review",
            "submitobservation", "applyverifieddelta", "create_goal", "enforce_reply",
            "gateway_integration", "systemctl", "daemon-reload",
        ):
            self.assertNotIn(forbidden, lower)

    def test_no_trace_embedding_ranking_expiry_or_delete_contract(self):
        tables = memory_store.ALL_15B1_TABLES
        for forbidden in (
            "memory_trace", "memory_embedding", "memory_rank", "memory_summary",
            "memory_confidence", "memory_expiry", "memory_delete_queue",
        ):
            self.assertNotIn(forbidden, tables)
        self.assertNotIn("DELETE", C.MEMORY_OPERATIONS)
        self.assertNotIn("EXPIRE", C.MEMORY_OPERATIONS)

    def test_l18_has_no_l04_apply_import(self):
        for name in ("learning.py", "learning_store.py", "learning_worker.py"):
            source = self.sources()[name]
            self.assertNotIn("import memory_store", source)
            self.assertNotIn("from . import memory_store", source)

    def test_no_router_api_frontend_or_prompt_entrypoint(self):
        source = self.sources()["memory_store.py"].lower()
        self.assertNotIn("fastapi", source)
        self.assertNotIn("prompt injection", source)
        self.assertNotIn('__name__ == "__main__"', source)


class TestDeployedConfigIfPresent(unittest.TestCase):
    def test_canonical_ltm_defaults_fail_closed(self):
        try:
            from lilith_router import config as deployed_config
        except ImportError:
            self.skipTest("deploy-exact Router package not present")
        cfg = deployed_config.RouterConfig()
        self.assertFalse(cfg.canonical_ltm_enabled)
        self.assertFalse(cfg.canonical_ltm_config_valid)
        self.assertFalse(cfg.canonical_ltm_is_enabled())


if __name__ == "__main__":
    unittest.main()
