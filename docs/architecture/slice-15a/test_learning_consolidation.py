"""Slice 15A Learning/Consolidation Foundations tests.

All source state is synthetic and local.  Tests use only SQLite files in a
temporary directory and never contact production, a model, or a connector.
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
MODULE_ROOT = HERE if (HERE / "learning.py").exists() else HERE.parent
if str(MODULE_ROOT) not in sys.path:
    sys.path.insert(0, str(MODULE_ROOT))

import learning
import learning_store as store_module
import learning_worker
import memory_contracts as C


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


def stamp(seconds: int = 0) -> str:
    base = datetime(2026, 9, 9, 12, 0, tzinfo=timezone.utc) + timedelta(seconds=seconds)
    return store_module.utc_now(base)


def make_source(path: Path, count: int = 3, *, schema: str = SOURCE_SCHEMA) -> None:
    conn = sqlite3.connect(path)
    try:
        conn.executescript(schema)
        if schema != SOURCE_SCHEMA:
            conn.commit()
            return
        stages = ("applied", "interview", "rejected", "offer")
        for index in range(1, count + 1):
            conn.execute(
                "INSERT INTO career_events(id,event_type,entity_type,entity_id,source,confidence,"
                "payload_json,created_at,processed) VALUES (?,?,?,?,?,?,?,?,?)",
                (
                    index, f"career.{stages[(index - 1) % len(stages)]}", "job_application",
                    100 + index, "gmail", 0.99,
                    json.dumps({"private_note": "DO_NOT_COPY", "email": "private@example.test"}),
                    f"2026-09-09 12:00:{index:02d}", 0,
                ),
            )
        conn.commit()
    finally:
        conn.close()


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def source_snapshot(path: Path):
    conn = sqlite3.connect(path)
    try:
        schema = conn.execute(
            "SELECT type,name,sql FROM sqlite_master ORDER BY type,name"
        ).fetchall()
        rows = conn.execute("SELECT * FROM career_events ORDER BY id").fetchall()
        return schema, rows
    finally:
        conn.close()


class ConfigFixture:
    def __init__(self, trace_path: Path, enabled: bool = True, mode: str = "shadow"):
        self.memory_consolidation_enabled = enabled
        self.memory_consolidation_mode = mode
        self._trace_path = trace_path

    def resolved_log_path(self):
        return self._trace_path


class TempCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.source = self.root / "lilith.db"
        self.ledger = self.root / "cognitive_memory.db"
        self.trace = self.root / "decisions.log"
        make_source(self.source)
        self.cfg = ConfigFixture(self.trace)

    def tearDown(self):
        self.tmp.cleanup()

    def migrate(self):
        return store_module.migrate(self.ledger, applied_at=stamp())

    def run_worker(self, **values):
        args = {
            "source_db": self.source,
            "learning_db": self.ledger,
            "cfg": self.cfg,
            "now_fn": lambda: stamp(),
        }
        args.update(values)
        return learning_worker.run_once(**args)


class TestContracts(TempCase):
    def source_and_candidate(self):
        row = learning.CareerEventsSource(self.source).read_batch(0, 1)[0]
        ref, descriptor = learning.build_source_record_ref(row)
        return ref, learning.derive_candidate(ref, descriptor, stamp())

    def test_input_contract_is_learning_source_record_ref(self):
        ref, _ = self.source_and_candidate()
        self.assertIsInstance(ref, C.LearningSourceRecordRef)
        self.assertFalse(hasattr(C, "EpisodicRecordRef"))

    def test_source_ref_schema_is_closed(self):
        ref, _ = self.source_and_candidate()
        self.assertEqual(set(ref.to_dict()), {
            "schemaVersion", "sourceOwner", "sourceStream", "sourceRecordId",
            "sourceSchemaVersion", "sourceDigest", "occurredAt", "subjectRefs",
            "evidenceRefs",
        })
        self.assertEqual(ref.evidence_refs, ())

    def test_candidate_schema_is_closed_structured_metadata(self):
        _, candidate = self.source_and_candidate()
        self.assertEqual(set(candidate.to_dict()), {
            "candidateId", "schemaVersion", "candidateClass", "sourceRefs",
            "sourceDigests", "subjectRefs", "admissionBasis", "epistemicBasis",
            "validationState", "idempotencyKey", "createdAt", "descriptor",
        })
        self.assertEqual(set(candidate.descriptor.to_dict()), {"eventType", "subjectRef"})

    def test_candidate_has_no_free_form_payload_or_summary(self):
        _, candidate = self.source_and_candidate()
        encoded = json.dumps(candidate.to_dict()).lower()
        self.assertNotIn("normalizedpayload", encoded)
        self.assertNotIn("summary", encoded)
        self.assertNotIn("do_not_copy", encoded)

    def test_contracts_have_no_confidence_fields(self):
        ref, candidate = self.source_and_candidate()
        keys = json.dumps({"ref": ref.to_dict(), "candidate": candidate.to_dict()}).lower()
        self.assertNotIn("confidence", keys)

    def test_only_real_v1_bases_exist(self):
        _, candidate = self.source_and_candidate()
        self.assertEqual(candidate.admission_basis, "SOURCE_EVENT_SHADOW_EVALUATION")
        self.assertEqual(candidate.epistemic_basis, "SOURCE_EVENT")
        module_values = vars(C).values()
        encoded = " ".join(str(value) for value in module_values if isinstance(value, str))
        for future in ("USER_ASSERTED", "VERIFIED_OUTCOME", "DERIVED_SUMMARY", "LEGACY_UNVALIDATED"):
            self.assertNotIn(future, encoded)

    def test_validation_is_distinct_from_assessment(self):
        _, candidate = self.source_and_candidate()
        validation = learning.validate_candidate(candidate)
        assessment = learning.assess_candidate(candidate, validation, stamp())
        self.assertIsInstance(validation, C.CandidateValidationResult)
        self.assertIsInstance(assessment, C.LearningAssessment)
        self.assertEqual(validation.state, C.VALID)
        self.assertEqual(assessment.outcome, C.SHADOW_ELIGIBLE)

    def test_valid_candidate_may_be_shadow_deferred(self):
        _, candidate = self.source_and_candidate()
        validation = learning.validate_candidate(candidate)
        assessment = learning.assess_candidate(
            candidate, validation, stamp(), defer_reason=C.NO_CANONICAL_LTM_APPLY_PATH,
        )
        self.assertEqual(assessment.outcome, C.SHADOW_DEFERRED)

    def test_invalid_candidate_is_shadow_rejected(self):
        _, candidate = self.source_and_candidate()
        broken = dataclasses.replace(candidate, subject_refs=("career.application:999",))
        validation = learning.validate_candidate(broken)
        assessment = learning.assess_candidate(broken, validation, stamp())
        self.assertEqual(validation.state, C.INVALID)
        self.assertEqual(assessment.outcome, C.SHADOW_REJECTED)

    def test_shadow_eligible_is_not_admission_or_memory(self):
        _, candidate = self.source_and_candidate()
        assessment = learning.assess_candidate(candidate, learning.validate_candidate(candidate), stamp())
        encoded = json.dumps(dataclasses.asdict(assessment))
        self.assertIn("SHADOW_ELIGIBLE", encoded)
        for forbidden in ("ADMITTED", "ACCEPTED", "LEARNED"):
            self.assertNotIn(forbidden, encoded)


class TestSourceAdapter(TempCase):
    def test_read_is_ordered_and_bounded(self):
        rows = learning.CareerEventsSource(self.source).read_batch(0, 2)
        self.assertEqual([row["id"] for row in rows], [1, 2])
        rows = learning.CareerEventsSource(self.source).read_batch(1, 2)
        self.assertEqual([row["id"] for row in rows], [2, 3])

    def test_projection_contains_only_allowlisted_fields(self):
        row = learning.CareerEventsSource(self.source).read_batch(0, 1)[0]
        self.assertEqual(tuple(row), learning.SOURCE_FIELD_ALLOWLIST)
        self.assertNotIn("payload_json", row)
        self.assertNotIn("confidence", row)
        self.assertNotIn("processed", row)

    def test_query_is_select_only(self):
        sql = learning.SOURCE_SELECT_SQL.upper()
        self.assertTrue(sql.startswith("SELECT "))
        for mutator in ("INSERT ", "UPDATE ", "DELETE ", "REPLACE ", "CREATE ", "DROP "):
            self.assertNotIn(mutator, sql)

    def test_source_database_bytes_and_rows_do_not_change(self):
        before_hash = file_hash(self.source)
        before = source_snapshot(self.source)
        learning.CareerEventsSource(self.source).read_batch(0, 3)
        self.assertEqual(file_hash(self.source), before_hash)
        self.assertEqual(source_snapshot(self.source), before)

    def test_digest_is_stable_and_uses_approved_representation(self):
        row = learning.CareerEventsSource(self.source).read_batch(0, 1)[0]
        first, _ = learning.build_source_record_ref(row)
        second, _ = learning.build_source_record_ref(dict(row))
        self.assertEqual(first.source_digest, second.source_digest)
        self.assertEqual(len(first.source_digest), 64)

    def test_source_descriptor_is_closed(self):
        row = learning.CareerEventsSource(self.source).read_batch(0, 1)[0]
        ref, descriptor = learning.build_source_record_ref(row)
        self.assertEqual(descriptor.event_type, "career.applied")
        self.assertEqual(descriptor.subject_ref, "career.application:101")
        self.assertEqual(ref.subject_refs, (descriptor.subject_ref,))

    def test_source_schema_mismatch_fails_closed(self):
        other = self.root / "bad.db"
        make_source(other, schema="CREATE TABLE career_events(id INTEGER PRIMARY KEY, event_type TEXT)")
        with self.assertRaises(learning.SourceSchemaMismatch):
            learning.CareerEventsSource(other).read_batch(0, 1)

    def test_missing_source_is_retryable(self):
        with self.assertRaises(learning.SourceUnavailable) as caught:
            learning.CareerEventsSource(self.root / "missing.db").read_batch(0, 1)
        self.assertTrue(caught.exception.retryable)

    def test_unknown_event_type_is_invalid(self):
        row = learning.CareerEventsSource(self.source).read_batch(0, 1)[0]
        row["event_type"] = "career.unreviewed"
        with self.assertRaises(learning.InvalidSourceRecord):
            learning.build_source_record_ref(row)

    def test_wrong_entity_or_source_is_invalid(self):
        row = learning.CareerEventsSource(self.source).read_batch(0, 1)[0]
        for key, value in (("entity_type", "person"), ("source", "private_mail"), ("entity_id", None)):
            changed = dict(row)
            changed[key] = value
            with self.assertRaises(learning.InvalidSourceRecord):
                learning.build_source_record_ref(changed)

    def test_oversized_field_rejects_before_candidate(self):
        row = learning.CareerEventsSource(self.source).read_batch(0, 1)[0]
        row["event_type"] = "x" * 65
        with self.assertRaises(learning.SourceTooLarge):
            learning.build_source_record_ref(row)

    def test_batch_limit_is_hard_bounded(self):
        with self.assertRaises(learning.SourceTooLarge):
            learning.CareerEventsSource(self.source).read_batch(0, 26)
        with self.assertRaises(learning.SourceTooLarge):
            learning.CareerEventsSource(self.source).read_batch(0, 0)


class TestLearningStore(TempCase):
    def test_migration_is_explicit_and_idempotent(self):
        first = self.migrate()
        second = store_module.migrate(self.ledger, applied_at=stamp(1))
        self.assertEqual(first, second)
        conn = sqlite3.connect(self.ledger)
        try:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM learning_schema_migration").fetchone()[0], 1)
        finally:
            conn.close()

    def test_schema_fingerprint_survives_reopen(self):
        expected = self.migrate()
        conn = store_module.LearningStore(self.ledger).connect()
        try:
            self.assertEqual(store_module.schema_fingerprint(conn), expected)
        finally:
            conn.close()

    def test_database_contains_only_l18_tables(self):
        self.migrate()
        conn = sqlite3.connect(self.ledger)
        try:
            tables = {row[0] for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
            )}
        finally:
            conn.close()
        self.assertEqual(tables, store_module.ALLOWED_TABLES)
        for forbidden in ("memory_item", "memory_revision", "memory_active_revision", "memory_admission", "memory_apply_audit"):
            self.assertNotIn(forbidden, tables)

    @unittest.skipIf(os.name == "nt", "POSIX permission assertion")
    def test_database_permissions_are_owner_only(self):
        self.migrate()
        self.assertEqual(self.ledger.stat().st_mode & 0o777, 0o600)

    def test_worker_open_does_not_create_unmigrated_database(self):
        with self.assertRaises(store_module.SchemaError):
            store_module.LearningStore(self.ledger).connect()
        self.assertFalse(self.ledger.exists())

    def test_job_leases_and_attempt_count_are_operational(self):
        self.migrate()
        ledger = store_module.LearningStore(self.ledger)
        job = ledger.lease_job("worker.one", stamp())
        self.assertEqual(job["status"], store_module.LEASED)
        self.assertEqual(job["attempt_count"], 1)
        self.assertEqual(job["cursor_from"], 0)

    def test_stale_lease_cannot_commit_after_reclaim(self):
        self.migrate()
        ledger = store_module.LearningStore(self.ledger)
        first = ledger.lease_job("worker.old", stamp(), lease_seconds=1)
        second = ledger.lease_job("worker.new", stamp(2), lease_seconds=60)
        self.assertEqual(first["job_id"], second["job_id"])
        with self.assertRaises(store_module.LeaseLost):
            ledger.commit_batch(first["job_id"], first["lease_token"], [], 0, stamp(2))

    def test_expired_lease_is_reclaimable(self):
        self.migrate()
        ledger = store_module.LearningStore(self.ledger)
        first = ledger.lease_job("worker.old", stamp(), lease_seconds=1)
        second = ledger.lease_job("worker.new", stamp(2), lease_seconds=60)
        self.assertNotEqual(first["lease_token"], second["lease_token"])
        self.assertEqual(second["attempt_count"], 2)

    def test_job_candidate_assessment_lifecycles_are_separate(self):
        self.migrate()
        result = self.run_worker(limit=1)
        conn = sqlite3.connect(self.ledger)
        try:
            job_status = conn.execute("SELECT status FROM learning_job").fetchone()[0]
            validation = conn.execute("SELECT validation_state FROM learning_candidate").fetchone()[0]
            assessment = conn.execute("SELECT outcome FROM learning_assessment").fetchone()[0]
        finally:
            conn.close()
        self.assertEqual((job_status, validation, assessment), ("SUCCEEDED", "VALID", "SHADOW_ELIGIBLE"))
        self.assertEqual(result["canonicalMemoryMutation"], False)

    def test_capacity_pauses_without_deleting(self):
        self.migrate()
        result = self.run_worker(limit=2, capacity=1)
        self.assertEqual(result["failureCode"], "CAPACITY_PAUSED")
        self.assertEqual(store_module.LearningStore(self.ledger).counts()["learning_candidate"], 0)


class TestOneShotWorker(TempCase):
    def test_feature_disabled_creates_no_database_or_trace(self):
        cfg = ConfigFixture(self.trace, enabled=False)
        result = learning_worker.run_once(source_db=self.source, learning_db=self.ledger, cfg=cfg)
        self.assertEqual(result["status"], "DISABLED")
        self.assertFalse(self.ledger.exists())
        self.assertFalse(self.trace.exists())

    def test_unknown_mode_fails_closed_without_mutation(self):
        cfg = ConfigFixture(self.trace, enabled=True, mode="live")
        result = learning_worker.run_once(source_db=self.source, learning_db=self.ledger, cfg=cfg)
        self.assertEqual(result["status"], "DISABLED_UNSUPPORTED_MODE")
        self.assertFalse(self.ledger.exists())

    def test_fresh_bounded_batch(self):
        self.migrate()
        result = self.run_worker(limit=2)
        self.assertEqual(result["status"], "SUCCEEDED")
        self.assertEqual(result["sourceCount"], 2)
        self.assertEqual(result["candidateCount"], 2)
        self.assertEqual(result["cursorThrough"], 2)
        self.assertFalse(result["canonicalMemoryMutation"])

    def test_same_batch_replay_is_idempotent(self):
        self.migrate()
        first = self.run_worker(limit=3)
        conn = sqlite3.connect(self.ledger)
        try:
            conn.execute("UPDATE learning_cursor SET committed_value=0")
            conn.commit()
        finally:
            conn.close()
        second = self.run_worker(limit=3)
        counts = store_module.LearningStore(self.ledger).counts()
        self.assertEqual(first["insertedCount"], 3)
        self.assertEqual(second["insertedCount"], 0)
        self.assertEqual(second["idempotentReplayCount"], 3)
        self.assertEqual(counts["learning_candidate"], 3)
        self.assertEqual(counts["learning_candidate_source"], 3)

    def test_crash_before_commit_replays_safely_after_lease_expiry(self):
        self.migrate()
        with self.assertRaises(RuntimeError):
            self.run_worker(
                limit=2,
                lease_seconds=1,
                fault_hook=lambda point: (_ for _ in ()).throw(RuntimeError("crash"))
                if point == "before_ledger_commit" else None,
            )
        self.assertEqual(store_module.LearningStore(self.ledger).get_cursor(), 0)
        result = self.run_worker(limit=2, now_fn=lambda: stamp(2))
        self.assertEqual(result["status"], "SUCCEEDED")
        self.assertEqual(result["insertedCount"], 2)
        self.assertEqual(store_module.LearningStore(self.ledger).get_cursor(), 2)

    def test_restart_after_commit_does_not_duplicate(self):
        self.migrate()
        with self.assertRaises(RuntimeError):
            self.run_worker(
                limit=2,
                fault_hook=lambda point: (_ for _ in ()).throw(RuntimeError("crash"))
                if point == "after_ledger_commit" else None,
            )
        self.assertEqual(store_module.LearningStore(self.ledger).get_cursor(), 2)
        result = self.run_worker(limit=2, now_fn=lambda: stamp(2))
        self.assertEqual(result["cursorFrom"], 2)
        self.assertEqual(result["insertedCount"], 1)
        self.assertEqual(store_module.LearningStore(self.ledger).counts()["learning_candidate"], 3)

    def test_source_schema_mismatch_is_terminal(self):
        bad = self.root / "bad.db"
        make_source(bad, schema="CREATE TABLE career_events(id INTEGER PRIMARY KEY, event_type TEXT)")
        self.migrate()
        result = self.run_worker(source_db=bad)
        self.assertEqual(result["status"], store_module.FAILED_TERMINAL)
        self.assertEqual(result["failureCode"], "SOURCE_SCHEMA_MISMATCH")
        self.assertEqual(store_module.LearningStore(self.ledger).get_cursor(), 0)

    def test_source_unavailable_retries_three_times_then_stops(self):
        self.migrate()
        missing = self.root / "missing.db"
        results = [self.run_worker(source_db=missing, now_fn=lambda i=i: stamp(i)) for i in range(3)]
        self.assertEqual([r["status"] for r in results[:2]], ["QUEUED", "QUEUED"])
        self.assertEqual(results[2]["status"], store_module.FAILED_TERMINAL)
        job = store_module.LearningStore(self.ledger).job(results[2]["jobId"])
        self.assertEqual(job["attempt_count"], 3)

    def test_invalid_source_record_does_not_advance_cursor(self):
        conn = sqlite3.connect(self.source)
        try:
            conn.execute("UPDATE career_events SET event_type='career.unknown' WHERE id=1")
            conn.commit()
        finally:
            conn.close()
        self.migrate()
        result = self.run_worker(limit=1)
        self.assertEqual(result["failureCode"], "INVALID_SOURCE_RECORD")
        self.assertEqual(store_module.LearningStore(self.ledger).get_cursor(), 0)

    def test_oversized_source_rejects_without_candidate_content(self):
        conn = sqlite3.connect(self.source)
        try:
            conn.execute("UPDATE career_events SET event_type=? WHERE id=1", ("x" * 65,))
            conn.commit()
        finally:
            conn.close()
        self.migrate()
        result = self.run_worker(limit=1)
        self.assertEqual(result["failureCode"], "SOURCE_TOO_LARGE")
        self.assertEqual(store_module.LearningStore(self.ledger).counts()["learning_candidate"], 0)

    def test_trace_is_metadata_only(self):
        self.migrate()
        self.run_worker(limit=2)
        trace = json.loads(self.trace.read_text(encoding="ascii").splitlines()[-1])
        self.assertEqual(set(trace), {
            "lane", "jobId", "sourceOwner", "sourceStream", "sourceCount",
            "candidateCount", "validationCounts", "assessmentCounts", "cursorFrom",
            "cursorThrough", "idempotentReplayCount", "failureCode", "durationMs",
            "mode", "schemaVersion", "timestamp",
        })
        encoded = json.dumps(trace).lower()
        for private in ("do_not_copy", "private@example.test", "private_note", "payload_json"):
            self.assertNotIn(private, encoded)

    def test_ledger_contains_no_source_payload_or_private_email(self):
        self.migrate()
        self.run_worker(limit=3)
        data = self.ledger.read_bytes().lower()
        self.assertNotIn(b"do_not_copy", data)
        self.assertNotIn(b"private@example.test", data)

    def test_source_state_unchanged_by_worker(self):
        self.migrate()
        before = source_snapshot(self.source)
        self.run_worker(limit=3)
        self.assertEqual(source_snapshot(self.source), before)

    def test_cursor_is_integer_event_id_not_timestamp(self):
        self.migrate()
        self.run_worker(limit=2)
        conn = sqlite3.connect(self.ledger)
        try:
            row = conn.execute("SELECT cursor_kind,committed_value FROM learning_cursor").fetchone()
        finally:
            conn.close()
        self.assertEqual(row, ("INTEGER_EVENT_ID", 2))

    def test_one_invocation_processes_at_most_hard_batch(self):
        many = self.root / "many.db"
        make_source(many, count=30)
        self.migrate()
        result = self.run_worker(source_db=many, limit=25)
        self.assertEqual(result["sourceCount"], 25)
        self.assertEqual(result["cursorThrough"], 25)


class TestStaticBoundaries(unittest.TestCase):
    MODULES = ("memory_contracts.py", "learning.py", "learning_store.py", "learning_worker.py")

    def sources(self):
        return {name: (MODULE_ROOT / name).read_text(encoding="utf-8") for name in self.MODULES}

    def test_no_model_or_network_imports(self):
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

    def test_no_world_goal_policy_soul_or_verifier_calls(self):
        operational = "\n".join(self.sources().values()).lower()
        for forbidden in (
            "applyverifieddelta", "submitobservation", "userassertion",
            "inferencecandidate", "create_goal", "policy.py", "soul.md",
            "verification_evidence.db", "verificationoutcomeref",
        ):
            self.assertNotIn(forbidden, operational)

    def test_no_legacy_memory_or_skills_access(self):
        operational = "\n".join(self.sources().values()).lower()
        for forbidden in ("memory.md", "user.md", "memory_tool", "skill_manage", "background_review"):
            self.assertNotIn(forbidden, operational)

    def test_no_l04_runtime_types_or_apply_operations(self):
        operational = "\n".join(self.sources().values())
        for forbidden in (
            "MemoryItem", "MemoryRevision", "memory_active_revision",
            "memory_admission", "memory_apply_audit", "SUPERSEDE", "RESTORE",
        ):
            self.assertNotIn(forbidden, operational)

    def test_no_daemon_or_systemd_surface(self):
        operational = "\n".join(self.sources().values()).lower()
        self.assertNotIn("while true", operational)
        self.assertNotIn("systemctl", operational)
        self.assertNotIn("daemon-reload", operational)
        self.assertNotIn("threading", operational)

    def test_no_learning_trace_table(self):
        self.assertNotIn("learning_trace", (MODULE_ROOT / "learning_store.py").read_text(encoding="utf-8"))

    def test_only_worker_main_is_an_execution_entrypoint(self):
        for name in self.MODULES[:-1]:
            self.assertNotIn('__name__ == "__main__"', (MODULE_ROOT / name).read_text(encoding="utf-8"))
        self.assertIn('__name__ == "__main__"', (MODULE_ROOT / "learning_worker.py").read_text(encoding="utf-8"))

    def test_source_query_never_selects_free_form_or_score_fields(self):
        sql = learning.SOURCE_SELECT_SQL.lower()
        self.assertNotIn("payload_json", sql)
        self.assertNotIn("confidence", sql)
        self.assertNotIn("processed", sql)


class TestDeployedConfigIfPresent(unittest.TestCase):
    def test_config_defaults_and_shadow_gate(self):
        try:
            from lilith_router import config as deployed_config
        except ImportError:
            self.skipTest("deploy-exact Router package not present")
        cfg = deployed_config.RouterConfig()
        self.assertFalse(cfg.memory_consolidation_enabled)
        self.assertEqual(cfg.memory_consolidation_mode, "shadow")
        self.assertFalse(cfg.memory_consolidation_is_active())
        cfg.memory_consolidation_enabled = True
        self.assertTrue(cfg.memory_consolidation_is_active())
        cfg.memory_consolidation_mode = "live"
        self.assertFalse(cfg.memory_consolidation_is_active())


if __name__ == "__main__":
    unittest.main()
