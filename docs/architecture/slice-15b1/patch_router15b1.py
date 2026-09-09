"""Apply the narrow, hash-pinned Slice 15B1 runtime patch.

This is a deployment/build utility, not a runtime entry point. It updates only
the approved Router files and installs the two new L04 files. Optional backups
are byte-for-byte copies made before replacement.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path


EXPECTED_START = {
    "memory_contracts.py": "943ff813564fa667fae6a376a6396c9bd53be254b8f1762391a8a29f652fd273",
    "learning.py": "20f7ee3fa2af5e6b789937dfb96b39ee32253c76dd051068dd82e8329315abdf",
    "learning_store.py": "9b8c54e9e4b4aa3638fe661f7d47f3e053f8f55b92ec224ec0f447f5bf691c5d",
    "learning_worker.py": "9b52d1fd4fa658cd1685c298acfcfd74ace97493ad4fa43217d38fb98be03b5c",
    "config.py": "bb04943f4b51b7b4a7f1ecad531d7cf9f3305a8ed90a1a8fe96f0bbcfefdffb5",
    "router.yaml": "df37c6c3c5403835872e457c539a049c2c7e592507e56d6749647adee54a7201",
    "tests/test_learning_consolidation.py": "49ba1bd1f1b6be61a2ab8a9e2e6e84d0179f42e715b328d70cdcbbeb0450c29c",
}


LEARNING_ADDITION = r'''


def candidate_provenance_binding(
    candidate: C.LearningCandidate,
    source_ref: C.LearningSourceRecordRef,
) -> C.CandidateProvenanceBinding:
    """Build the exact candidate/source meaning bound by an L18 proposal."""
    if validate_candidate(candidate).state != C.VALID:
        raise C.LearningContractError("cannot propose from an invalid candidate")
    expected_ref = f"{source_ref.source_stream}:{source_ref.source_record_id}"
    if (
        candidate.source_refs != (expected_ref,)
        or candidate.source_digests != (source_ref.source_digest,)
        or candidate.subject_refs != source_ref.subject_refs
        or len(source_ref.subject_refs) != 1
        or candidate.descriptor.subject_ref != source_ref.subject_refs[0]
    ):
        raise C.LearningContractError("candidate provenance does not match its source")
    return C.CandidateProvenanceBinding(
        candidate_id=candidate.candidate_id,
        candidate_schema_version=candidate.schema_version,
        candidate_class=candidate.candidate_class,
        candidate_idempotency_key=candidate.idempotency_key,
        candidate_admission_basis=candidate.admission_basis,
        candidate_epistemic_basis=candidate.epistemic_basis,
        validation_state=candidate.validation_state,
        event_type=candidate.descriptor.event_type,
        subject_ref=candidate.descriptor.subject_ref,
        source_owner=source_ref.source_owner,
        source_stream=source_ref.source_stream,
        source_record_id=source_ref.source_record_id,
        source_schema_version=source_ref.source_schema_version,
        source_digest=source_ref.source_digest,
        occurred_at=source_ref.occurred_at,
        source_subject_ref=source_ref.subject_refs[0],
    )


def derive_memory_write_proposal(
    candidate: C.LearningCandidate,
    source_ref: C.LearningSourceRecordRef,
    *,
    proposal_id: str,
    operation: str,
    target_memory_class: str,
    subject_namespace: str,
    subject_key: str,
    admission_basis: str,
    epistemic_basis: str,
    created_at: str,
    value_schema: Optional[str] = None,
    proposed_value: Optional[Mapping[str, Any]] = None,
    expected_active_revision_id: Optional[str] = None,
    restore_revision_id: Optional[str] = None,
    consent_ref_id: Optional[str] = None,
    verification_outcome_ref_id: Optional[str] = None,
    rollback_authorization_ref_id: Optional[str] = None,
) -> C.MemoryWriteProposal:
    """Create an immutable proposal; this function has no L04 capability."""
    binding = candidate_provenance_binding(candidate, source_ref)
    if proposed_value is None:
        value_json = None
        value_digest = None
    else:
        value_json, value_digest = C.normalize_proposed_value(proposed_value)
    draft = C.MemoryWriteProposal(
        proposal_id=proposal_id,
        candidate_id=candidate.candidate_id,
        schema_version=C.SCHEMA_VERSION,
        operation=operation,
        target_memory_class=target_memory_class,
        subject_namespace=subject_namespace,
        subject_key=subject_key,
        expected_active_revision_id=expected_active_revision_id,
        restore_revision_id=restore_revision_id,
        value_schema=value_schema,
        proposed_value_json=value_json,
        proposed_value_digest=value_digest,
        admission_basis=admission_basis,
        epistemic_basis=epistemic_basis,
        consent_ref_id=consent_ref_id,
        verification_outcome_ref_id=verification_outcome_ref_id,
        rollback_authorization_ref_id=rollback_authorization_ref_id,
        proposal_fingerprint="0" * 64,
        created_at=created_at,
    )
    draft.validate()
    fingerprint = C.compute_proposal_fingerprint(draft, binding)
    return C.MemoryWriteProposal(
        **{**draft.__dict__, "proposal_fingerprint": fingerprint}
    )
'''


STORE_CONSTANTS = r'''

# Slice 15B1 adds a durable L18 proposal handoff and L04-owned tables.  The
# original Slice 15A migration fingerprint remains scoped to its exact V1
# objects; the new migration authority fingerprints every 15B1 object.
PROPOSAL_TABLES = frozenset({"learning_proposal"})
SHARED_L04_TABLES = frozenset({
    "memory_schema_migration", "memory_item", "memory_revision",
    "memory_revision_source", "memory_active_revision", "memory_admission",
    "memory_apply_audit",
})
KNOWN_COGNITIVE_TABLES = ALLOWED_TABLES | PROPOSAL_TABLES | SHARED_L04_TABLES
L18_V1_SCHEMA_OBJECTS = ALLOWED_TABLES | frozenset({
    "learning_job_one_open_stream", "learning_candidate_source_record",
})
'''


STORE_AUTHORIZER = r'''


def _l18_authorizer(
    action: int,
    arg1: Optional[str],
    arg2: Optional[str],
    database: Optional[str],
    trigger: Optional[str],
) -> int:
    """Deny L18 runtime access outside its learning-owned SQL scope."""
    del arg2, database, trigger
    table = str(arg1 or "")
    if action == sqlite3.SQLITE_READ:
        return sqlite3.SQLITE_OK if table.startswith("learning_") or table in {
            "sqlite_master", "sqlite_schema",
        } else sqlite3.SQLITE_DENY
    if action in {sqlite3.SQLITE_INSERT, sqlite3.SQLITE_UPDATE, sqlite3.SQLITE_DELETE}:
        return sqlite3.SQLITE_OK if table.startswith("learning_") else sqlite3.SQLITE_DENY
    schema_actions = {
        sqlite3.SQLITE_CREATE_INDEX, sqlite3.SQLITE_CREATE_TABLE,
        sqlite3.SQLITE_CREATE_TRIGGER, sqlite3.SQLITE_CREATE_VIEW,
        sqlite3.SQLITE_DROP_INDEX, sqlite3.SQLITE_DROP_TABLE,
        sqlite3.SQLITE_DROP_TRIGGER, sqlite3.SQLITE_DROP_VIEW,
        sqlite3.SQLITE_ALTER_TABLE, sqlite3.SQLITE_REINDEX,
    }
    if action in schema_actions:
        return sqlite3.SQLITE_DENY
    return sqlite3.SQLITE_OK
'''


STORE_METHODS = r'''

    @staticmethod
    def _proposal_from_row(row: sqlite3.Row) -> C.MemoryWriteProposal:
        return C.MemoryWriteProposal(
            proposal_id=str(row["proposal_id"]),
            candidate_id=str(row["candidate_id"]),
            schema_version=int(row["schema_version"]),
            operation=str(row["operation"]),
            target_memory_class=str(row["target_memory_class"]),
            subject_namespace=str(row["subject_namespace"]),
            subject_key=str(row["subject_key"]),
            expected_active_revision_id=row["expected_active_revision_id"],
            restore_revision_id=row["restore_revision_id"],
            value_schema=row["value_schema"],
            proposed_value_json=row["proposed_value_json"],
            proposed_value_digest=row["proposed_value_digest"],
            admission_basis=str(row["admission_basis"]),
            epistemic_basis=str(row["epistemic_basis"]),
            consent_ref_id=row["consent_ref_id"],
            verification_outcome_ref_id=row["verification_outcome_ref_id"],
            rollback_authorization_ref_id=row["rollback_authorization_ref_id"],
            proposal_fingerprint=str(row["proposal_fingerprint"]),
            created_at=str(row["created_at"]),
        )

    @staticmethod
    def _candidate_binding(conn: sqlite3.Connection, candidate_id: str) -> C.CandidateProvenanceBinding:
        row = conn.execute(
            "SELECT c.candidate_id,c.schema_version,c.candidate_class,c.idempotency_key,"
            "c.admission_basis,c.epistemic_basis,c.validation_state,c.event_type,"
            "c.subject_ref,s.source_owner,s.source_stream,s.source_record_id,"
            "s.source_schema_version,s.source_digest,s.occurred_at,"
            "s.subject_ref AS source_subject_ref,a.outcome AS assessment_outcome "
            "FROM learning_candidate c "
            "JOIN learning_candidate_source s ON s.candidate_id=c.candidate_id "
            "JOIN learning_assessment a ON a.candidate_id=c.candidate_id "
            "WHERE c.candidate_id=?",
            (candidate_id,),
        ).fetchone()
        if row is None:
            raise LearningStoreError("candidate provenance is unavailable")
        if row["validation_state"] != C.VALID or row["assessment_outcome"] != C.SHADOW_ELIGIBLE:
            raise LearningStoreError("candidate is not proposal-eligible")
        return C.CandidateProvenanceBinding(
            candidate_id=str(row["candidate_id"]),
            candidate_schema_version=int(row["schema_version"]),
            candidate_class=str(row["candidate_class"]),
            candidate_idempotency_key=str(row["idempotency_key"]),
            candidate_admission_basis=str(row["admission_basis"]),
            candidate_epistemic_basis=str(row["epistemic_basis"]),
            validation_state=str(row["validation_state"]),
            event_type=str(row["event_type"]),
            subject_ref=str(row["subject_ref"]),
            source_owner=str(row["source_owner"]),
            source_stream=str(row["source_stream"]),
            source_record_id=int(row["source_record_id"]),
            source_schema_version=int(row["source_schema_version"]),
            source_digest=str(row["source_digest"]),
            occurred_at=str(row["occurred_at"]),
            source_subject_ref=str(row["source_subject_ref"]),
        )

    def insert_proposal(self, proposal: C.MemoryWriteProposal) -> C.MemoryWriteProposal:
        """Commit one immutable L18 proposal after rebinding persisted provenance."""
        proposal.validate()
        conn = self.connect()
        try:
            conn.execute("BEGIN IMMEDIATE")
            binding = self._candidate_binding(conn, proposal.candidate_id)
            expected = C.compute_proposal_fingerprint(proposal, binding)
            if expected != proposal.proposal_fingerprint:
                raise LearningStoreError("proposal fingerprint does not bind persisted provenance")
            existing = conn.execute(
                "SELECT * FROM learning_proposal WHERE proposal_fingerprint=?",
                (proposal.proposal_fingerprint,),
            ).fetchone()
            if existing is not None:
                stored = self._proposal_from_row(existing)
                conn.rollback()
                return stored
            conn.execute(
                "INSERT INTO learning_proposal(proposal_id,candidate_id,schema_version,operation,"
                "target_memory_class,subject_namespace,subject_key,expected_active_revision_id,"
                "restore_revision_id,value_schema,proposed_value_json,proposed_value_digest,"
                "admission_basis,epistemic_basis,consent_ref_id,verification_outcome_ref_id,"
                "rollback_authorization_ref_id,proposal_fingerprint,created_at) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    proposal.proposal_id, proposal.candidate_id, proposal.schema_version,
                    proposal.operation, proposal.target_memory_class, proposal.subject_namespace,
                    proposal.subject_key, proposal.expected_active_revision_id,
                    proposal.restore_revision_id, proposal.value_schema,
                    proposal.proposed_value_json, proposal.proposed_value_digest,
                    proposal.admission_basis, proposal.epistemic_basis,
                    proposal.consent_ref_id, proposal.verification_outcome_ref_id,
                    proposal.rollback_authorization_ref_id, proposal.proposal_fingerprint,
                    proposal.created_at,
                ),
            )
            conn.commit()
            return proposal
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def proposal(self, proposal_id: str) -> Optional[C.MemoryWriteProposal]:
        conn = self.connect()
        try:
            row = conn.execute(
                "SELECT * FROM learning_proposal WHERE proposal_id=?", (proposal_id,),
            ).fetchone()
            return self._proposal_from_row(row) if row else None
        finally:
            conn.close()
'''


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path: Path) -> str:
    return path.read_bytes().decode("utf-8")


def write(path: Path, text: str) -> None:
    path.write_bytes(text.replace("\r\n", "\n").encode("utf-8"))


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if text.count(old) != 1:
        raise RuntimeError(f"{label}: expected exactly one patch anchor")
    return text.replace(old, new, 1)


def backup(path: Path, tag: str | None) -> None:
    if not tag:
        return
    target = path.with_name(path.name + f".bak.slice15b1.{tag}")
    if target.exists():
        raise RuntimeError(f"backup already exists: {target}")
    shutil.copy2(path, target)


def patch_learning(path: Path) -> None:
    text = read(path)
    if "def derive_memory_write_proposal(" in text:
        return
    write(path, text.rstrip() + LEARNING_ADDITION + "\n")


def patch_learning_store(path: Path) -> None:
    text = read(path)
    if "def insert_proposal(" in text:
        return
    marker = "ALLOWED_TABLES = frozenset({\n    \"learning_schema_migration\",\n    \"learning_job\",\n    \"learning_cursor\",\n    \"learning_candidate\",\n    \"learning_candidate_source\",\n    \"learning_assessment\",\n})\n"
    text = replace_once(text, marker, marker + STORE_CONSTANTS, "learning table ownership")
    old_fp = '''def schema_fingerprint(conn: sqlite3.Connection) -> str:
    rows = conn.execute(
        "SELECT type, name, sql FROM sqlite_master "
        "WHERE name LIKE 'learning_%' AND sql IS NOT NULL "
        "ORDER BY type, name"
    ).fetchall()
    payload = "\\n".join(f"{row[0]}:{row[1]}:{_normal_sql(row[2])}" for row in rows)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
'''
    new_fp = '''def schema_fingerprint(conn: sqlite3.Connection) -> str:
    rows = conn.execute(
        "SELECT type,name,sql FROM sqlite_master WHERE sql IS NOT NULL ORDER BY type,name"
    ).fetchall()
    selected = [row for row in rows if str(row[1]) in L18_V1_SCHEMA_OBJECTS]
    if {str(row[1]) for row in selected} != L18_V1_SCHEMA_OBJECTS:
        raise SchemaError("Slice 15A schema object set is incomplete")
    payload = "\\n".join(f"{row[0]}:{row[1]}:{_normal_sql(row[2])}" for row in selected)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
'''
    text = replace_once(text, old_fp, new_fp, "L18 fingerprint scope")
    text = replace_once(
        text,
        "    if not tables.issubset(ALLOWED_TABLES):\n        raise SchemaError(\"database contains a non-L18 table\")",
        "    if not tables.issubset(KNOWN_COGNITIVE_TABLES):\n        raise SchemaError(\"database contains an unrecognized cognitive table\")",
        "shared table allowlist",
    )
    anchor = "\ndef migrate(path: Path, applied_at: Optional[str] = None) -> str:\n"
    text = replace_once(text, anchor, STORE_AUTHORIZER + anchor, "L18 authorizer")
    text = replace_once(
        text,
        "            if row[\"schema_fingerprint\"] != schema_fingerprint(conn):\n                raise SchemaError(\"Learning schema fingerprint mismatch\")\n            return conn",
        "            if row[\"schema_fingerprint\"] != schema_fingerprint(conn):\n                raise SchemaError(\"Learning schema fingerprint mismatch\")\n            conn.set_authorizer(_l18_authorizer)\n            return conn",
        "runtime authorizer install",
    )
    text = replace_once(text, "\n    def counts(self) -> Dict[str, int]:\n", STORE_METHODS + "\n    def counts(self) -> Dict[str, int]:\n", "proposal methods")
    write(path, text)


def patch_config(path: Path) -> None:
    text = read(path)
    if "canonical_ltm_config_valid" in text:
        return
    field_anchor = '''    memory_consolidation_enabled: bool = False
    memory_consolidation_mode: str = "shadow"
'''
    field_new = field_anchor + '''
    # -- Slice 15B1: canonical LTM apply kill switch. --
    # Missing or non-boolean configuration is invalid and therefore disabled.
    canonical_ltm_enabled: bool = False
    canonical_ltm_config_valid: bool = False
'''
    text = replace_once(text, field_anchor, field_new, "canonical config fields")
    method_anchor = '''    def resolved_log_path(self) -> Path:
'''
    method_new = '''    def canonical_ltm_is_enabled(self) -> bool:
        """True only for an explicitly present, strictly boolean true setting."""
        return self.canonical_ltm_config_valid and self.canonical_ltm_enabled is True

''' + method_anchor
    text = replace_once(text, method_anchor, method_new, "canonical config method")
    load_anchor = '''        cfg.memory_consolidation_mode = str(
            raw.get("memory_consolidation_mode", cfg.memory_consolidation_mode)
        ).strip().lower() or "shadow"
        return cfg
'''
    load_new = '''        cfg.memory_consolidation_mode = str(
            raw.get("memory_consolidation_mode", cfg.memory_consolidation_mode)
        ).strip().lower() or "shadow"
        canonical_value = raw.get("canonical_ltm_enabled")
        if isinstance(canonical_value, bool):
            cfg.canonical_ltm_enabled = canonical_value
            cfg.canonical_ltm_config_valid = True
        else:
            cfg.canonical_ltm_enabled = False
            cfg.canonical_ltm_config_valid = False
        return cfg
'''
    text = replace_once(text, load_anchor, load_new, "strict canonical config load")
    write(path, text)


def patch_yaml(path: Path) -> None:
    text = read(path)
    if "canonical_ltm_enabled:" in text:
        return
    addition = '''

# -- Slice 15B1: canonical Long-Term Memory foundation --
# Production apply remains impossible. This switch is checked inside L04.
# It is independent from the Slice 15A shadow Learning worker above.
canonical_ltm_enabled: false
'''
    write(path, text.rstrip() + addition)


def patch_learning_test(path: Path) -> None:
    text = read(path)
    old = '''    def test_no_l04_runtime_types_or_apply_operations(self):
        operational = "\\n".join(self.sources().values())
        for forbidden in (
            "MemoryItem", "MemoryRevision", "memory_active_revision",
            "memory_admission", "memory_apply_audit", "SUPERSEDE", "RESTORE",
        ):
            self.assertNotIn(forbidden, operational)
'''
    new = '''    def test_l18_has_no_l04_apply_or_mutator_import(self):
        for name in ("learning.py", "learning_store.py", "learning_worker.py"):
            source = (MODULE_ROOT / name).read_text(encoding="utf-8")
            self.assertNotIn("import memory_store", source)
            self.assertNotIn("from . import memory_store", source)
            self.assertNotIn(".apply(proposal", source)
'''
    text = replace_once(text, old, new, "Slice 15A L04 boundary regression")
    old_verifier = '''        operational = "\\n".join(self.sources().values()).lower()
        for forbidden in (
            "applyverifieddelta", "submitobservation", "userassertion",
            "inferencecandidate", "create_goal", "policy.py", "soul.md",
            "verification_evidence.db", "verificationoutcomeref",
        ):
            self.assertNotIn(forbidden, operational)
'''
    new_verifier = '''        operational = "\\n".join(
            (MODULE_ROOT / name).read_text(encoding="utf-8")
            for name in ("learning.py", "learning_store.py", "learning_worker.py")
        ).lower()
        for forbidden in (
            "applyverifieddelta", "submitobservation", "userassertion",
            "inferencecandidate", "create_goal", "policy.py", "soul.md",
            "verification_evidence.db",
        ):
            self.assertNotIn(forbidden, operational)
'''
    text = replace_once(text, old_verifier, new_verifier, "Verifier boundary regression")
    write(path, text)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--router-root", type=Path, required=True)
    parser.add_argument("--artifact-root", type=Path, required=True)
    parser.add_argument("--backup-tag")
    args = parser.parse_args()

    root = args.router_root.resolve()
    artifacts = args.artifact_root.resolve()
    targets = {name: root / name for name in EXPECTED_START}
    for name, path in targets.items():
        if not path.is_file() or digest(path) != EXPECTED_START[name]:
            raise RuntimeError(f"starting hash mismatch: {name}")
    for path in targets.values():
        backup(path, args.backup_tag)

    final_contracts = artifacts / "memory_contracts.py"
    memory_store = artifacts / "memory_store.py"
    canonical_test = artifacts / "test_canonical_ltm.py"
    if not all(path.is_file() for path in (final_contracts, memory_store, canonical_test)):
        raise RuntimeError("Slice 15B1 artifacts are incomplete")

    write(root / "memory_contracts.py", read(final_contracts))
    patch_learning(root / "learning.py")
    patch_learning_store(root / "learning_store.py")
    patch_config(root / "config.py")
    patch_yaml(root / "router.yaml")
    patch_learning_test(root / "tests" / "test_learning_consolidation.py")

    for new_path in (root / "memory_store.py", root / "tests" / "test_canonical_ltm.py"):
        if new_path.exists():
            raise RuntimeError(f"new Slice 15B1 target already exists: {new_path}")
    write(root / "memory_store.py", read(memory_store))
    write(root / "tests" / "test_canonical_ltm.py", read(canonical_test))

    changed = {
        str(path.relative_to(root)): digest(path)
        for path in (
            root / "memory_contracts.py", root / "learning.py",
            root / "learning_store.py", root / "config.py", root / "router.yaml",
            root / "memory_store.py", root / "tests" / "test_learning_consolidation.py",
            root / "tests" / "test_canonical_ltm.py",
        )
    }
    print(json.dumps(changed, sort_keys=True))


if __name__ == "__main__":
    main()
