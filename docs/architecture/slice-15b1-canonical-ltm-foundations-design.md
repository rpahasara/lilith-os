# Slice 15B1 — Canonical Long-Term Memory Foundations

Status: implemented and deployed with production apply disabled.

This slice establishes L04 canonical Long-Term Memory storage infrastructure and proves its mechanics only in isolated synthetic databases. It does not admit real memory and does not integrate canonical retrieval into prompts, conversations, World, Goals, Planning, Policy, SOUL, or legacy memory.

The strongest valid claim is:

> LILITH has canonical Long-Term Memory infrastructure with proven isolated CREATE/SUPERSEDE/RESTORE mechanics.

## Governing invariant

Learning proposes · LTM admits and stores · Provenance explains · Memory is not truth.

- L18 Learning owns candidates, assessments, and durable `MemoryWriteProposal` creation.
- L04 Long-Term Memory owns storage admission, exact memory identity, immutable revisions, active-revision selection, apply audit, lineage, and internal exact-key retrieval.
- Consent Authority, Verifier, and Rollback Authority remain separate owners. L04 resolves their references but cannot create their authority.
- Privacy/Data Governance remains the future true-erasure owner.
- World remains the current-belief owner; a canonical revision is not a World truth claim.
- Executive remains the goal owner, Policy remains the authorization owner, and SOUL remains the personality owner.

## L18 → L04 handoff

The durable sequence is deliberately four-part:

1. `LearningCandidate` describes a bounded, validated learning candidate.
2. `LearningAssessment` records the L18 shadow assessment.
3. `MemoryWriteProposal` makes a specific immutable request across the L18/L04 boundary.
4. L04 records a terminal `AdmissionDecision` and, only for an accepted proposal, atomically creates the revision, provenance snapshot, active pointer, and apply audit represented by `MemoryApplyResult`.

A candidate is not a proposal. A proposal is not an admission. An admission is not an apply audit. Neither a candidate nor a prompt-visible or legacy-memory record is canonical memory.

## `MemoryWriteProposal` V1

The closed proposal contains:

- `proposalId`, `candidateId`, and `schemaVersion`
- `operation`: `CREATE`, `SUPERSEDE`, or `RESTORE`
- exact `targetMemoryClass`, `subjectNamespace`, and `subjectKey`
- optional `expectedActiveRevisionId` and `restoreRevisionId`, as required by the operation
- `valueSchema`, normalized `proposedValue`, and `proposedValueDigest` for CREATE/SUPERSEDE
- `admissionBasis` and `epistemicBasis`
- optional `consentRefId`, `verificationOutcomeRefId`, and `rollbackAuthorizationRefId`
- `proposalFingerprint` and `createdAt`

CREATE requires a value and forbids expected-active and restore references. SUPERSEDE requires a value and exact expected-active revision. RESTORE requires exact expected-active and historical restore references, forbids caller-supplied replacement value, and requires rollback authorization. DELETE and EXPIRE do not exist in the operation contract.

The proposal contains no confidence score, unrestricted metadata, caller-selected revision ID, caller-selected active pointer, raw source record, transcript, prompt, or chain of thought.

## Candidate and provenance binding

`proposalFingerprint` is SHA-256 over canonical JSON containing the proposal's authority-bearing meaning and the persisted candidate binding:

- candidate ID, candidate schema version, candidate class, idempotency key, validation state, admission basis, and epistemic basis
- each ordered source owner, stream, record ID, schema version, source digest, and bounded subject reference
- proposal schema version, operation, target class, exact namespace/key identity, expected active revision, restore target, normalized value digest, admission basis, epistemic basis, and authority reference IDs

Generated proposal IDs and all timestamps, including source occurrence time, are excluded. L18 recomputes the binding from committed candidate/source rows before inserting an immutable proposal. L04 recomputes the same binding from persisted rows before admission. Candidate, source, assessment, and proposal rows are protected against update and deletion by SQLite triggers; the proposal does not rely on `candidateId` alone.

## Exact identity and immutable revisions

`memory_item` owns exact identity through:

`UNIQUE(memory_class, subject_namespace, subject_key)`

There is no fuzzy identity, semantic search, embedding, case folding, or LLM-selected identity.

`memory_revision` stores one immutable normalized value with its digest, proposal, lineage references, epistemic/admission bases, authority references, and creation time. The item ID and revision ID are distinct. Semantic revision content cannot be updated or deleted.

`memory_revision_source` stores only the bounded provenance needed for explanation: source owner, stream, record ID, schema version, digest, occurrence time, and optional subject reference. It never copies raw career payload, email, transcript, notes, MEMORY.md, USER.md, prompts, or arbitrary JSON.

## Active pointer and lineage

`memory_active_revision` has one row per item. A composite foreign key ensures that its revision belongs to the same item. Identity-changing updates and deletion are denied.

- CREATE makes a new item/revision and points active to it.
- SUPERSEDE requires the current pointer to equal `expectedActiveRevisionId`, creates a new revision whose `supersedesRevisionId` is the prior active revision, and advances the pointer.
- RESTORE requires the same exact-current precondition and a historical target from the same item. It creates a new revision whose normalized value is copied from the validated target, whose `supersedesRevisionId` is the current active revision, and whose `restoresRevisionId` names the historical target. It never repoints directly to an old revision.

A stale expected revision produces terminal `PRECONDITION_FAILED / ACTIVE_REVISION_MISMATCH` and no revision or pointer change. A cross-item restore is rejected.

## Admission and apply idempotency

`memory_admission` permits only terminal `ACCEPTED`, `REJECTED`, and `PRECONDITION_FAILED`, with at most one row per proposal. Retryable storage failure creates no terminal admission.

`memory_apply_audit` immutably binds the proposal, admission, operation, item, prior revision, created revision, resulting active revision, apply time, and restore authorization reference when applicable. A successful proposal has one audit and one created revision.

Replaying a successfully applied proposal derives `ALREADY_APPLIED` from the existing audit and returns the same identities; it does not insert another admission or revision. Replaying a rejected or precondition-failed proposal returns its terminal result and cannot later apply. A corrected attempt requires a new proposal and fingerprint.

## Authority resolver model

Production uses unavailable resolvers for Consent, Verification, and Rollback Authority. Strings supplied by a caller do not self-authenticate. Consent-required, procedural-like, and restore operations therefore fail closed when their real authority is unavailable.

The synthetic registry, value schema, consent resolver, verifier resolver, and rollback resolver live only in `test_canonical_ltm.py`. `MemoryStore.production()` constructs an empty registry, and construction rejects any non-empty registry aimed at the production database path. No test authority or synthetic memory class is production-accessible.

## Production kill switch

Production configuration is explicit and unambiguous:

```yaml
memory_consolidation_enabled: true
memory_consolidation_mode: shadow
canonical_ltm_enabled: false
```

`MemoryStore.apply()` evaluates the strict boolean provider before opening the database. Missing, malformed, unknown, or false configuration fails closed as `CANONICAL_LTM_DISABLED`. The check is inside L04, so direct invocation cannot bypass it. The production registry is also empty. These are independent defenses.

## Tables and ownership

L18 adds one table:

- `learning_proposal`: immutable proposal ledger, unique by candidate and proposal fingerprint.

L04 adds seven tables:

- `memory_schema_migration`: L04 schema version and L04-only schema fingerprint.
- `memory_item`: exact canonical identity.
- `memory_revision`: immutable values and lineage.
- `memory_revision_source`: bounded immutable provenance snapshot.
- `memory_active_revision`: one exact active pointer per item.
- `memory_admission`: immutable terminal admission.
- `memory_apply_audit`: immutable successful-apply audit.

There is no trace, embedding, rank, summary, confidence, expiry, deletion, privacy-erasure, personalization, or procedural-skill table. Runtime trace is allowlisted, bounded metadata only.

## SQL and migration authority

The L18 runtime SQLite authorizer can operate only on the six Slice 15A `learning_*` tables plus its own `learning_proposal`; it cannot read or write `memory_*`.

The L04 runtime authorizer can read only `learning_proposal`, `learning_candidate`, `learning_candidate_source`, and `learning_assessment`, plus L04-owned memory tables. It cannot mutate `learning_*`. It may mutate only L04 data tables and cannot perform schema operations.

`memory_store.migrate()` is the separate, explicit schema authority. On the production database path it requires a verified, still-current SQLite backup. It creates only the approved additive schema, preserves every L18 row and cursor, checks the L04 fingerprint, foreign keys, and `integrity_check`, and is idempotent. Isolated empty databases receive the existing L18 schema first solely to support self-contained tests.

The L18 internal migration fingerprint and the complete database schema fingerprint remain separate terms. Slice 15B1 also adds a distinct L04 internal migration fingerprint.

## Internal reads and capacity

L04 exposes exact-key retrieval of only the active canonical revision, direct revision reads, ordered lineage, and bounded provenance/audit explanation. It does not search Learning candidates or legacy memory. There is no prompt or conversation consumer.

Capacity exhaustion pauses admission without deletion, expiry, pruning, or eviction. True privacy/legal erasure is intentionally outside this slice.

## Implementation footprint

The runtime footprint is limited to:

- expanded `memory_contracts.py`
- narrow proposal helpers in `learning.py`
- proposal persistence and L18 SQL ownership in `learning_store.py`
- new `memory_store.py`
- strict `canonical_ltm_enabled` parsing in `config.py` and an explicit false value in `router.yaml`
- `test_canonical_ltm.py` and narrow Slice 15A static-boundary test updates

There is no gateway hook, scheduler, model/LLM call, connector, process execution, prompt mutation, retrieval integration, frontend change, app.py change, systemd unit, timer, restart, or daemon reload.

## Remaining Slice 15B2 prerequisites

Before the first real canonical admission, a later authorized slice must define and approve all of the following without weakening 15B1:

1. a real memory class and closed value schema;
2. its exact subject namespace owner and normalization rules;
3. its admissible L18 source/candidate semantics;
4. real Consent Authority integration where required;
5. real Verifier integration for procedural-like memory where required;
6. real Rollback Authority for restore;
7. Privacy/Data Governance retention and true-erasure behavior;
8. capacity and operational policy for that class;
9. a separately reviewed retrieval consumer and non-authoritative use semantics;
10. explicit production enablement and an acceptance plan proving the first real write.

Until then, `canonical_ltm_enabled` stays false, the production registry stays empty, and all production canonical memory data tables stay empty.
