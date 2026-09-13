# Slice 15A — Learning / Memory Consolidation Foundations

**Status:** Implemented and deployed in bounded `SHADOW` mode on 2026-09-09.

## Governing invariant

> Learning proposes · LTM admits and stores · Provenance explains · Memory is not truth.

Slice 15A proves governed Learning machinery. It does not create canonical Long-Term Memory, make source events true, admit a memory, or affect a reply.

```text
career_events (read-only infrastructure-proof source)
  → LearningSourceRecordRef
  → deterministic candidate derivation
  → structural/source validation
  → durable L18 Learning ledger
  → shadow assessment
  → atomic cursor commit
```

There is no L04 apply step.

## Authority and ownership

- `career_events` remains owned by the Career Watcher. Slice 15A reads it as `READ_ONLY_INFRASTRUCTURE_PROOF_SOURCE` only.
- L18 Learning owns the job, cursor, candidate, provenance, and shadow-assessment records in `cognitive_memory.db`.
- Verification is an independent authority. The Verifier owns proof semantics and a future qualifying `VerificationOutcomeRef`; Task Runtime and Slice 15 Learning do not.
- L04 remains the future canonical admission/storage owner. No L04 runtime class, table, apply operation, or active-revision pointer exists here.
- A future Consent Authority may produce a `ConsentRef`. Consent ownership is unresolved in V1 and is not assigned to Learning or L04.
- World, Goal/Executive, Meta-Cognition, personality, Policy, Social Guard, connectors, and prompts remain separate and unchanged.

## Source adapter

The adapter opens `/home/lilith/.hermes/lilith-os/data/lilith.db` with SQLite `mode=ro`, applies `PRAGMA query_only=ON`, validates the complete nine-column `career_events` schema as source schema version 1, and executes one fixed query:

```sql
SELECT id, event_type, entity_type, entity_id, source, created_at
FROM career_events
WHERE id > ?
ORDER BY id ASC
LIMIT ?
```

The allowlist is exactly:

- `id`
- `event_type`
- `entity_type`
- `entity_id`
- `source`
- `created_at`

The existing source columns `confidence`, `payload_json`, and `processed` are deliberately excluded from row reads, digests, candidates, provenance, assessments, and trace. In particular, arbitrary JSON/email content is never loaded by this adapter.

Accepted V1 source semantics are closed to `source=gmail`, `entity_type=job_application`, positive integer IDs, strict SQLite timestamps, and these source-owner stages:

`discovered`, `applied`, `recruiter_contact`, `screening`, `assessment`, `interview`, `final_interview`, `offer`, `rejected`, `withdrawn`, and `closed` (each stored as `career.<stage>`).

The ordered cursor is the last committed integer event ID. Timestamp is metadata, never cursor authority.

## Closed contracts

`LearningSourceRecordRef` contains only:

```text
schemaVersion
sourceOwner
sourceStream
sourceRecordId
sourceSchemaVersion
sourceDigest
occurredAt
subjectRefs[]
evidenceRefs[]
```

For V1, the owner/stream are `CAREER_WATCHER` / `career_events`; one subject reference is derived as `career.application:<entity_id>` and `evidenceRefs` is empty. `sourceDigest` is SHA-256 over canonical JSON containing only the six approved source fields plus the fixed owner, stream, and source-schema version.

`LearningCandidate` contains only:

```text
candidateId
schemaVersion
candidateClass
sourceRefs[]
sourceDigests[]
subjectRefs[]
admissionBasis
epistemicBasis
validationState
idempotencyKey
createdAt
descriptor { eventType, subjectRef }
```

Exact V1 values are:

- `candidateClass=SOURCE_EVENT_CONSOLIDATION_CANDIDATE`
- `admissionBasis=SOURCE_EVENT_SHADOW_EVALUATION`
- `epistemicBasis=SOURCE_EVENT`

There is no normalized payload, summary paragraph, transcript, chain of thought, score, or confidence field. Candidate ID and idempotency key are derived from the same SHA-256 fingerprint of schema version, class, closed descriptor, source owner/stream/record ID/schema version, and source digest.

## Validation and assessment

`CandidateValidationResult` answers only whether the candidate is structurally and source-valid. Its states are `VALID` and `INVALID`, with closed reason codes.

`LearningAssessment` separately describes shadow eligibility:

- `SHADOW_ELIGIBLE / SOURCE_EVENT_INFRASTRUCTURE_PROOF`
- `SHADOW_REJECTED / CANDIDATE_VALIDATION_FAILED`
- `SHADOW_DEFERRED / NO_CANONICAL_LTM_APPLY_PATH`

`SHADOW_ELIGIBLE` means the candidate meets Slice 15A's infrastructure-proof rules. It does not mean admitted, accepted, learned, true, or likely to be accepted by a future L04 owner. A valid candidate may be deferred.

## Durable ledger

Path: `/home/lilith/.hermes/lilith-os/data/cognitive_memory.db`

The file is owned by `lilith:lilith` with mode `0600`. Its existence does not mean canonical LTM is active. Schema version 1 contains only:

- `learning_schema_migration` — explicit version and schema fingerprint
- `learning_job` — execution and lease lifecycle
- `learning_cursor` — source-specific committed progress
- `learning_candidate` — closed shadow candidate metadata
- `learning_candidate_source` — bounded source provenance
- `learning_assessment` — shadow outcome and reason

There is no `learning_trace` table and no `memory_item`, `memory_revision`, `memory_active_revision`, `memory_admission`, or `memory_apply_audit` table.

Schema creation is explicit, versioned, idempotent, and fingerprint-checked. Normal worker opens do not create or migrate the database. SQLite uses WAL, `synchronous=FULL`, foreign keys, a 5-second busy timeout, and `BEGIN IMMEDIATE` for job/commit transitions.

The initial migration created a new database, so there was no pre-existing ledger to back up. Any future schema migration must first disable manual processing, capture a timestamped filesystem backup of `cognitive_memory.db` (including a consistent WAL checkpoint or SQLite backup), verify that backup, and preserve it through acceptance. Destructive migration is not authorized.

Two indexes enforce the key operational invariants:

- a partial unique index permits at most one `QUEUED` or `LEASED` job for the source stream;
- a provenance index supports exact owner/stream/source-record lookup.

Primary keys, a unique idempotency key, a unique source-version/digest tuple, foreign keys, and closed `CHECK` constraints enforce the rest of the contract.

## Jobs, leases, retries, and transaction boundary

The lifecycle is `QUEUED → LEASED → SUCCEEDED`, with retryable failure/expiry returning to `QUEUED`, permanent failure reaching `FAILED_TERMINAL`, and an explicitly modeled but unused `CANCELLED` terminal state. Attempt count is operational only.

The default lease is 60 seconds and the hard range is 1–300 seconds. The maximum is three attempts total. Expired leases are reclaimable; a stale token cannot commit. Source unavailability is retryable. Source-schema mismatch, invalid records, oversize, cursor conflict, and capacity pause fail closed without advancing the cursor. The capacity ceiling is 10,000 candidates; reaching it pauses admission and never prunes or deletes.

Candidate rows, source links, assessments, cursor advancement, and successful job completion commit in one Learning-database transaction. Because the source and Learning databases are separate, delivery is at least once; deterministic idempotency converts replay into a no-duplicate result.

## Bounds and observability

- Default one-shot batch: 10 records
- Hard batch maximum: 25 records
- Approved canonical representation: at most 512 bytes per record
- Approved batch representation: at most 12,800 bytes
- Exactly one source reference, digest, and subject reference per candidate

The existing Router `decisions.log` receives one bounded ASCII JSON record, at most 4,096 bytes, with job/source/count/cursor/replay/failure/duration/mode/schema metadata. It excludes source text, payloads, names, emails, notes, prompts, legacy memory, SOUL, and chain of thought. Durable audit is already provided by the ledger; no second trace table is justified.

## Configuration and execution

The additive config keys are:

```yaml
memory_consolidation_enabled: true
memory_consolidation_mode: SHADOW
```

Dataclass defaults remain disabled. Only case-normalized `shadow` activates the worker; `live`, empty, and unknown modes disable it. The worker is manual, bounded, and one-shot. It has no daemon loop, systemd unit/timer, gateway hook, conversation correlation, model/tool call, connector access, prompt injection, retrieval consumer, or write-back consumer.

## Legacy and privacy boundary

- `MEMORY.md`: `LEGACY_EXTERNAL`, `LEGACY_UNVALIDATED`; not accessed.
- `USER.md`: `LEGACY_EXTERNAL`, `LEGACY_UNVALIDATED`, `SENSITIVE`; not accessed.
- Hermes skills: `NON_LTM_ARTIFACT`, `LEGACY_EXTERNAL`; not accessed.
- `state.db` sessions/FTS: `NON_LTM_INFRASTRUCTURE`.
- Existing `/memory/*`: `LEGACY_PROJECTION`; unchanged and not used.
- Hermes background reviewer: unchanged `LEGACY_EXTERNAL_WRITER`; future adopt/gate/disable/replace/exclude options remain open.

There is no preference learning, procedural reinforcement, privacy-erasure lifecycle, automatic retention, or automatic pruning. Correctness rollback and future privacy erasure remain different concerns.

## Rollback and deferred work

Fast rollback is to set `memory_consolidation_enabled: false` and stop manual invocations; config is read by each invocation, so no gateway restart is required. Full deployment rollback restores the timestamped config backups and removes only the five additive Python/test files. The Learning ledger is preserved for audit unless deletion is separately approved.

Slice 15B remains deferred. Prerequisites include reviewed canonical L04 admission/storage contracts, proposal/apply boundaries, consent ownership and `ConsentRef`, qualifying Verifier semantics and `VerificationOutcomeRef`, privacy-erasure governance, retention policy, rollback/revision semantics, and separately reviewed prompt/retrieval consumers. No part of those prerequisites is activated by Slice 15A.
