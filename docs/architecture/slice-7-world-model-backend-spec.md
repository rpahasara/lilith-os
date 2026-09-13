# Slice 7 — World Model + Working Memory: Backend Build Spec

> **Status:** Implementation-ready specification for **Slice 7 Phase B** (backend/VM).
> **Authority:** [Cognitive Architecture V1](./cognitive-architecture-v1.md) §5, §7a, §12–13.
> **Prerequisite:** backend/VM source + tunnel access (absent from the frontend repo).
> **Frontend Phase A** (contracts, client, proxy allow-list, Working-Memory selection, Context Builder, inspector) is already implemented in this repo under `src/lib/world/*`, `src/app/world/`, and the `/os/world` proxy allow-list entry. The wire shapes below are the contract that frontend already normalises.
> **Reconciled to production (recon 2026-09-07):** verified against the live VM — single-file `app.py`, inline `CREATE TABLE IF NOT EXISTS` bootstrap (no migration framework, `user_version=0`), `journal_mode=delete`, real Career schema (`job_applications`/`companies`/`career_events`). Sections 1, 11, 12, 14 below reflect that reality.

This document is written so a backend engineer with VM access can implement Slice 7 end-to-end without further design. Field names, DDL, endpoints and reconciliation rules are concrete. Where a detail must match an existing backend convention (migration runner, DI, auth middleware), it is flagged **[adapt]**.

---

## 0. Scope & non-negotiables

**Build:** a durable, provenance-stamped **belief store** with controlled ingestion, deterministic reconciliation, a read-only `/os/world` API, a meta-cognition trace, and Career as the first live source. Working Memory is **reconstructed**, not durably stored.

**Do not:** expose a generic `setBelief`; use an LLM to resolve conflicts; let a belief grant permission to act; let World Model confidence bypass Policy; add external writes or new connectors; touch Hsin, Google OAuth, Presence, or the Slices 1–6 stores/behaviour. A connector's output is **candidate observation/evidence**, never truth — only Verification produces `VERIFIED`.

**Three separate abstractions (never merge):**
| | Question | Persistence |
|---|---|---|
| World Model | "What does LILITH believe is true now?" | Durable current-state checkpoint |
| Working Memory | "What is cognitively active right now?" | Ephemeral, reconstructible |
| Long-Term Memory | "What was recorded/learned historically?" | Durable, written only by consolidation |

Per architecture §7a: World-Model current-state persistence **is** allowed online; the "no durable writes during online cognition" rule refers to **LTM consolidation**, not World-Model checkpointing.

---

## 1. SQLite schema (inline bootstrap — matches production)

**Production reality (recon 2026-09-07):** the backend has **no migration framework** — no migrations directory, `PRAGMA user_version = 0`, no startup hook. Tables `tasks`/`drafts` are created lazily inline via `CREATE TABLE IF NOT EXISTS` inside their write paths, using the shared `db()` helper, with per-row `schema_version` + module constants (`TASK_SCHEMA_VERSION = 1`). Slice 7 follows the **same** pattern: an idempotent `_ensure_world_schema(conn)` guarded by a module-level `WORLD_SCHEMA_VERSION = 1`, called at the top of every World-Model read/ingest path. **Do not add a migration file or runner.** The DDL below is unchanged in content — only its delivery is inline. New tables only; no change to `tasks`, `drafts`, `os_audit_log`, `career_events`, `job_applications`, `companies`, or any Slice 1–6 table.

```python
# _ensure_world_schema(conn) executes exactly the statements below, once per
# connection, idempotently. NOT a migration file — production uses inline
# bootstrap. Mirrors the existing inline tasks/drafts table creation.
```

```sql
-- Current-state belief store. One row per canonical belief key (its latest
-- reconciled state). Superseded history is preserved in belief_evidence + trace.
CREATE TABLE IF NOT EXISTS world_belief (
  key             TEXT PRIMARY KEY,          -- '<entity_type>:<entity_id>:<predicate>'
  entity_type     TEXT NOT NULL,
  entity_id       TEXT NOT NULL,
  predicate       TEXT NOT NULL,
  value_json      TEXT NOT NULL,             -- JSON-encoded believed value
  lifecycle_state TEXT NOT NULL,             -- ACTIVE|SUPERSEDED|CONFLICTED|STALE
  epistemic_state TEXT NOT NULL,             -- OBSERVED|USER_ASSERTED|INFERRED|VERIFIED
  confidence      REAL NOT NULL,             -- 0..1, rule-derived
  confidence_tier TEXT NOT NULL,             -- high|medium|low|unknown
  confidence_basis TEXT NOT NULL,            -- machine reason code
  observed_at     TEXT,                      -- ISO-8601, when the fact was observed
  created_at      TEXT NOT NULL,             -- ISO-8601
  updated_at      TEXT NOT NULL,             -- ISO-8601
  expires_at      TEXT,                      -- ISO-8601 freshness horizon
  revision        INTEGER NOT NULL DEFAULT 1,
  CHECK (lifecycle_state IN ('ACTIVE','SUPERSEDED','CONFLICTED','STALE')),
  CHECK (epistemic_state IN ('OBSERVED','USER_ASSERTED','INFERRED','VERIFIED')),
  CHECK (confidence >= 0.0 AND confidence <= 1.0)
);
CREATE INDEX IF NOT EXISTS ix_world_belief_entity
  ON world_belief (entity_type, entity_id);
CREATE INDEX IF NOT EXISTS ix_world_belief_lifecycle
  ON world_belief (lifecycle_state);

-- Evidence chain. Append-only; every ingested observation/assertion/inference/
-- verification that touched a belief key is retained here (this is where
-- superseded and conflicting evidence lives — beliefs supersede, never delete).
CREATE TABLE IF NOT EXISTS world_belief_evidence (
  id              INTEGER PRIMARY KEY AUTOINCREMENT,
  belief_key      TEXT NOT NULL REFERENCES world_belief(key),
  source_class    TEXT NOT NULL,             -- USER|LIVE_CONNECTOR|TASK_RESULT|VERIFICATION|MEMORY|INFERENCE|SYSTEM
  source_id       TEXT,
  source_type     TEXT,                      -- e.g. 'career.application'
  correlation_id  TEXT,
  value_json      TEXT NOT NULL,             -- the value this evidence asserted
  epistemic_state TEXT NOT NULL,             -- epistemic status of THIS evidence
  confidence      REAL NOT NULL,
  observed_at     TEXT,
  ingested_at     TEXT NOT NULL,
  origin_ref      TEXT,                      -- opaque ref to origin record (no payload)
  content_hash    TEXT,                      -- hash of full content when not inlined
  note            TEXT,                      -- short safe summary
  superseded      INTEGER NOT NULL DEFAULT 0,-- 1 once outranked by later evidence
  CHECK (source_class IN
    ('USER','LIVE_CONNECTOR','TASK_RESULT','VERIFICATION','MEMORY','INFERENCE','SYSTEM'))
);
CREATE INDEX IF NOT EXISTS ix_world_evidence_key
  ON world_belief_evidence (belief_key, ingested_at);

-- Conflict edges (retained; a CONFLICTED belief points at the evidence/keys it
-- disagrees with). One row per unresolved conflict pair.
CREATE TABLE IF NOT EXISTS world_belief_conflict (
  belief_key      TEXT NOT NULL REFERENCES world_belief(key),
  conflict_ref    TEXT NOT NULL,             -- evidence id or belief key in conflict
  detected_at     TEXT NOT NULL,
  reason          TEXT NOT NULL,             -- e.g. 'equal_authority_disagree'
  resolved_at     TEXT,
  PRIMARY KEY (belief_key, conflict_ref)
);

-- Meta-cognition trace. Append-only, observable decision metadata (NEVER LLM
-- chain-of-thought). One row per belief mutation.
CREATE TABLE IF NOT EXISTS world_belief_trace (
  id                 INTEGER PRIMARY KEY AUTOINCREMENT,
  correlation_id     TEXT NOT NULL,
  belief_key         TEXT NOT NULL,
  at                 TEXT NOT NULL,
  prev_lifecycle     TEXT,
  new_lifecycle      TEXT NOT NULL,
  prev_epistemic     TEXT,
  new_epistemic      TEXT NOT NULL,
  confidence         REAL NOT NULL,
  confidence_basis   TEXT NOT NULL,
  source_class       TEXT NOT NULL,
  reconciliation_reason TEXT NOT NULL,       -- deterministic code (see §9)
  superseded_keys    TEXT,                   -- JSON array
  conflict_keys      TEXT                    -- JSON array
);
CREATE INDEX IF NOT EXISTS ix_world_trace_key
  ON world_belief_trace (belief_key, at);
CREATE INDEX IF NOT EXISTS ix_world_trace_corr
  ON world_belief_trace (correlation_id);

-- OPTIONAL minimal working-set reconstruction metadata. Working Memory is NOT
-- durably stored; only the seed needed to rebuild it deterministically is kept.
CREATE TABLE IF NOT EXISTS world_working_seed (
  session_id      TEXT PRIMARY KEY,
  task_id         TEXT,
  focus_json      TEXT,                      -- {entities:[...], predicates:[...]}
  capacity        INTEGER NOT NULL DEFAULT 12,
  updated_at      TEXT NOT NULL
);
```

**Bootstrap safety:** all statements are `CREATE TABLE/INDEX IF NOT EXISTS` — idempotent, re-runnable, no data backfill. Deliver them from a single `_ensure_world_schema(conn)` (mirroring the existing inline task/draft creation), gated by a module-level `WORLD_SCHEMA_VERSION = 1`. No migration ledger and **no `PRAGMA user_version` change** (production keeps it at 0). The schema write is the only mutation Slice 7 performs at bootstrap; it briefly locks the DB under `journal_mode=delete` (see §11), so run it once on first world-path access and guard with a process-level "already ensured" flag to avoid redundant writes.

---

## 2. Belief schema (field reference)

| Field | Type | Notes |
|---|---|---|
| `key` | string | canonical identity — §4 |
| `entity_type` / `entity_id` / `predicate` | string | the (entity, attribute) the belief is about |
| `value` | any (JSON) | the believed value |
| `lifecycle_state` | enum | `ACTIVE` \| `SUPERSEDED` \| `CONFLICTED` \| `STALE` — §5 |
| `epistemic_state` | enum | `OBSERVED` \| `USER_ASSERTED` \| `INFERRED` \| `VERIFIED` — §5 |
| `confidence` | `{value, tier, basis}` | rule-derived & explainable — §7 |
| `provenance` | evidence[] | ordered chain, newest first — §6 |
| `observed_at` | ISO? | when the underlying fact was observed |
| `created_at` / `updated_at` | ISO | first-seen / last reconciliation |
| `expires_at` | ISO? | freshness horizon → `STALE` after |
| `revision` | int | bumped on every state-changing reconciliation |
| `supersedes` / `contradicted_by` | string[]? | evidence ids / belief keys |

`UNKNOWN` is **not a stored value** — it is the honest absence of an `ACTIVE` belief for a key, or a belief below the confidence floor. The API represents this by returning no belief (or `lifecycle_state != ACTIVE`), never a fabricated `value`.

---

## 3. (reserved — see §2)

---

## 4. Canonical belief identity

```
key = "<entity_type>:<entity_id>:<predicate>"
# example
career.application:17:status
```

Rules:
- Identity is deterministic and stable. The same proposition **always** resolves to the same key.
- Repeated observations of the same key **update/reconcile** the existing row (append evidence, bump revision) — they never create a second row.
- `entity_type` is a namespaced domain path (`career.application`, `user.profile`, `device.session`). `predicate` is a single attribute name (`status`, `last_activity`, `follow_up_state`).
- Values that are themselves entities should be modelled as separate beliefs, not embedded, so they get their own provenance.

---

## 5. Lifecycle vs epistemic states

Two orthogonal axes. A belief has exactly one of each.

**Epistemic (how we know it):**
```
OBSERVED       seen via a live connector / real observation
USER_ASSERTED  the user stated it directly
INFERRED       derived by reasoning — may be wrong; never outranks evidence
VERIFIED       independently proven by the Verification layer ONLY
```
`VERIFIED` may originate solely from `applyVerifiedDelta` (§8). Ingress from any other path may never set `VERIFIED`.

**Lifecycle (its status in the store):**
```
ACTIVE       current best-estimate truth
SUPERSEDED   replaced by newer/stronger evidence (row retained as history)
CONFLICTED   trusted evidence disagrees; rules cannot safely resolve
STALE        past freshness/TTL — still known, explicitly old
```

Legal lifecycle transitions (all logged to the trace):
```
(new)      -> ACTIVE | CONFLICTED
ACTIVE     -> SUPERSEDED | CONFLICTED | STALE
STALE      -> ACTIVE (fresh evidence) | SUPERSEDED | CONFLICTED
CONFLICTED -> ACTIVE (resolving evidence arrives) | SUPERSEDED
SUPERSEDED -> (terminal for that evidence; key may become ACTIVE again on new evidence)
```

---

## 6. Provenance schema

Every belief carries an ordered evidence chain. Source classes:
```
USER | LIVE_CONNECTOR | TASK_RESULT | VERIFICATION | MEMORY | INFERENCE | SYSTEM
```
Per-evidence fields: `source_class`, `source_id?`, `source_type?`, `correlation_id?`, `value_json`, `epistemic_state`, `confidence`, `observed_at?`, `ingested_at`, `origin_ref?`, `content_hash?`, `note?`.

**Privacy:** store `origin_ref` + a short `note` + optional `content_hash`; do **not** inline full private payloads. An `INFERRED` belief must remain visibly distinct from `OBSERVED`/`VERIFIED` (its evidence's `epistemic_state` says so). Never store hidden chain-of-thought — `note` is a short, safe, human-readable summary only.

---

## 7. Confidence model

Confidence is **explainable and rule-derived** — never a free-form LLM number.

**Base confidence by epistemic state of the strongest current evidence:**
| Epistemic | Base |
|---|---|
| VERIFIED | 0.98 |
| OBSERVED | 0.80 |
| USER_ASSERTED | 0.80 |
| INFERRED | 0.45 |

**Adjustments (bounded, additive, then clamp to [0,1]):**
- `+0.05` per corroborating independent evidence of equal-or-higher authority (max `+0.15`).
- `−0.20` while `lifecycle_state = CONFLICTED`.
- `−0.15` while `STALE`.
- `−0.10` if the sole evidence is older than its freshness horizon but not yet expired.

**Tier mapping:** `value ≥ 0.80 → high`, `≥ 0.55 → medium`, `≥ 0.15 → low`, `< 0.15 → unknown` (belief not admitted as ACTIVE).

**`basis`** is a machine code recording the derivation, e.g. `verified`, `single_observation`, `observed+2corroborations`, `inferred_no_corroboration`, `conflicted_penalty`, `stale_penalty`. The system must be able to answer "why is confidence 0.65?" from `basis` + the evidence chain alone.

> Prefer emitting the **tier** to reasoning prompts; keep the raw float for reconciliation and audit. Do not ask an LLM to produce the number.

---

## 8. Controlled ingestion API (internal only)

No generic `setBelief`. Only these four internal entry points may submit candidates; each is called by an **authorized cognitive source** and performs reconciliation (§9), never a blind write. **[adapt]** to the backend's internal service/DI style; these are not HTTP-exposed for mutation.

```
submitObservation(entity, predicate, value, source: LIVE_CONNECTOR|TASK_RESULT|SYSTEM,
                  { sourceId, sourceType, correlationId, observedAt, originRef, note }) -> ReconcileResult
    # epistemic = OBSERVED

submitUserAssertion(entity, predicate, value, { correlationId, note }) -> ReconcileResult
    # epistemic = USER_ASSERTED, source_class = USER

submitInferenceCandidate(entity, predicate, value, { basis, correlationId, note }) -> ReconcileResult
    # epistemic = INFERRED, source_class = INFERENCE; never outranks evidence

applyVerifiedDelta(entity, predicate, value, { correlationId, verificationRef }) -> ReconcileResult
    # epistemic = VERIFIED — the ONLY path that may set VERIFIED. Comes from the
    # Verification layer after a real-world action is proven. No connector output
    # may call this directly.
```

**Authorization boundary (must be enforced & tested — test J/K):** Planner, Reasoning, Connectors, Personality and Presence **cannot** call these paths directly. Ingestion is invoked only by: the observation pipeline (Slice 1 watchers/connector results), the conversation/turn handler for user assertions, and the Verification layer for verified deltas. A direct mutation attempt from an unauthorized caller is rejected and logged.

`ReconcileResult = { key, action: 'created'|'updated'|'superseded'|'conflicted'|'stale'|'noop', revision, traceId }`.

---

## 9. Reconciliation V1 (deterministic, no LLM)

On each ingestion, load the current belief for `key` (if any), append the new evidence row, then apply the first matching rule. **No LLM is used to resolve conflicts.**

**Authority ordering:** `VERIFIED > OBSERVED = USER_ASSERTED > INFERRED`.

```
R0  No current belief:
      create ACTIVE (or CONFLICTED if two equal-authority disagreeing evidences arrive together).
      reason = 'first_evidence'

R1  Identical value, any source (idempotent repeat):
      no state change; add corroboration; recompute confidence (+corroboration).
      revision unchanged unless confidence tier changes. reason = 'idempotent_corroboration'

R2  New evidence higher authority than current (e.g. VERIFIED over OBSERVED/INFERRED):
      new value wins -> ACTIVE with new epistemic; mark prior evidence superseded;
      set supersedes. reason = 'higher_authority_supersedes'
      (special: 'verified_outranks_inferred', 'verified_outranks_observed')

R3  New evidence equal authority, newer observed_at, comparable source:
      newer value supersedes older -> ACTIVE; prior evidence superseded.
      reason = 'newer_comparable_supersedes'
      NB: recency applies ONLY at equal authority. Never let a newer INFERRED
      override an older OBSERVED/VERIFIED.

R4  New evidence equal authority, disagreeing value, NOT clearly newer/stronger:
      cannot safely resolve -> lifecycle = CONFLICTED; retain BOTH evidence chains;
      write world_belief_conflict rows; lower confidence (conflicted penalty).
      reason = 'equal_authority_disagree'

R5  New evidence lower authority than current, disagreeing:
      current belief stands (ACTIVE); new evidence retained but marked superseded
      (kept for provenance). reason = 'lower_authority_ignored_kept'

R6  Freshness sweep (scheduled, not on write):
      belief.updated_at past expires_at -> lifecycle = STALE (value retained).
      reason = 'freshness_expired'. Fresh comparable evidence returns it to ACTIVE (R2/R3).

R7  Source-failure / empty result (CRITICAL — test I):
      an unavailable/failed source (e.g. connector 502, empty fetch) must NOT be
      ingested as a value. It is NOT evidence of absence. Do not overwrite a valid
      belief with null/empty. At most, if a freshness contract exists, let the
      existing belief age toward STALE via R6. reason = 'source_unavailable_noop'

R8  Unknown remains unknown (test H):
      if no ACTIVE belief exists and no admissible evidence arrives, the key stays
      absent. Never synthesize a value to fill a gap.
```

Every rule application writes a `world_belief_trace` row and returns a `ReconcileResult`. Reconciliation is a **pure function of (current belief, current evidence chain, new evidence, clock)** — same inputs, same outcome.

---

## 10. Conflict & supersession behaviour

- **Supersession retains history:** superseded evidence rows stay in `world_belief_evidence` with `superseded=1`; the belief's `supersedes` lists what it replaced. Nothing is destructively deleted.
- **Conflict retains both chains:** a `CONFLICTED` belief keeps every disagreeing evidence chain and one `world_belief_conflict` row per pair. Confidence is lowered, and the conflict surfaces to Meta-Cognition (trace) and, per architecture Flow E, may drive a disambiguation request to the user via Presence — but resolution comes from **new evidence or explicit user assertion**, never an LLM guess in Slice 7.
- **Resolution:** when qualifying evidence arrives (higher authority, or user assertion, or a clearly-newer equal-authority observation), the belief returns to `ACTIVE`, conflict rows get `resolved_at`, and confidence recovers.

---

## 11. `/os/world` read contracts

Read-only. **[adapt]** to the backend's router/auth. Already allow-listed in the frontend proxy (`os/world`).

**Concurrency & read-safety (production `journal_mode=delete`).** The production DB uses a rollback journal, not WAL, so a writer takes a brief exclusive lock. World-Model reads must therefore:
- open the DB **read-only** — `sqlite3.connect("file:" + str(DB) + "?mode=ro", uri=True)` — so a read can never create/modify a journal or block a writer, and
- set a bounded busy timeout — `PRAGMA busy_timeout = 2000` (or `connect(..., timeout=2.0)`) — so a read waits briefly under a concurrent write rather than erroring, then returns `503`/empty honestly if still locked.

Reads must never fabricate a belief on `SQLITE_BUSY`; they surface an honest unavailable state (the frontend already renders it). Ingestion/reconciliation (write paths) use the normal read-write `db()` connection.

### `GET /os/world`
Query params: `entity_type?`, `entity_id?`, `include_superseded?` (default `0`), `limit?` (default 200).

```jsonc
// 200 OK
{
  "beliefs": [
    {
      "key": "career.application:17:status",
      "entity_type": "career.application",
      "entity_id": "17",
      "predicate": "status",
      "value": "interviewing",
      "lifecycle_state": "ACTIVE",
      "epistemic_state": "OBSERVED",
      "confidence": { "value": 0.8, "tier": "high", "basis": "single_observation" },
      "provenance": [
        {
          "source_class": "LIVE_CONNECTOR",
          "source_id": "career-store",
          "source_type": "career.application",
          "correlation_id": "obs_9f2c",
          "observed_at": "2026-09-06T14:20:00Z",
          "freshness": "fresh",
          "confidence": 0.8,
          "origin_ref": "career_events/1042",
          "note": "status field from career pipeline"
        }
      ],
      "observed_at": "2026-09-06T14:20:00Z",
      "created_at": "2026-09-06T14:20:00Z",
      "updated_at": "2026-09-06T14:20:00Z",
      "revision": 1,
      "supersedes": [],
      "contradicted_by": []
    }
  ],
  "meta": {
    "total": 1,
    "by_lifecycle": { "ACTIVE": 1 },
    "by_epistemic": { "OBSERVED": 1 },
    "conflicted": 0,
    "stale": 0,
    "last_reconciled_at": "2026-09-06T14:20:00Z"
  }
}
```

### `GET /os/world/{key}`
Returns a single belief object (same shape as an element above), or `404` if no belief exists for the key (honest UNKNOWN — the frontend renders "not yet known", never a fake value).

**No mutation endpoints are HTTP-exposed.** Ingestion is internal only (§8).

---

## 12. Meta-cognition trace schema

Every belief mutation emits one `world_belief_trace` row (§1). Read projection (for a future `/os/world/trace` or the inspector; not required for Phase A acceptance):
```jsonc
{
  "id": "…", "correlation_id": "obs_9f2c", "belief_key": "career.application:17:status",
  "at": "2026-09-06T14:20:00Z",
  "prev_lifecycle": null, "new_lifecycle": "ACTIVE",
  "prev_epistemic": null, "new_epistemic": "OBSERVED",
  "confidence": { "value": 0.8, "basis": "single_observation" },
  "source_class": "LIVE_CONNECTOR",
  "reconciliation_reason": "first_evidence",
  "superseded_keys": [], "conflict_keys": []
}
```
Trace rows are observable metadata only — **no hidden chain-of-thought**, no full private payloads (refs/hashes/summaries only, mirroring §6/§13).

**`world_belief_trace` is authoritative for cognitive belief changes.** It is a dedicated store, separate from `os_audit_log` (which stays authoritative for *actions/writes*, Slice 4). A `VERIFIED` delta (from `applyVerifiedDelta`) **may optionally** also write a mirror row into `os_audit_log` — using the existing columns: `app='world-model'`, `action='belief.verified'`, `entity_type`/`entity_id` from the belief, `actor` = the verification source, `confidence`, `reason` = `reconciliation_reason`, `before_json`/`after_json` = prior/new belief value, `reversible=0` — so belief-affecting verified outcomes appear in the current audit view. This mirror is convenience only; the world trace remains the source of truth for belief lifecycle/epistemic transitions. Non-verified reconciliations (`OBSERVED`/`INFERRED`/`USER_ASSERTED`) write **only** to `world_belief_trace`, never to `os_audit_log`, to keep the action audit clean.

---

## 13. Working Memory reconstruction semantics

Working Memory is **not** a durable store. The backend's only durable involvement is the optional `world_working_seed` row (session_id, task_id?, focus, capacity). Reconstruction is deterministic and already implemented in the frontend (`src/lib/world/working-memory.ts`, `buildWorkingSet`) as the reference algorithm; the backend (or a future server-side context assembler) must reproduce the **same** selection given the same beliefs + focus + capacity:

1. Read current beliefs (via the store) for the focus entities (+ related).
2. Exclude `SUPERSEDED`; exclude `confidence < 0.15`.
3. Score = `3·focusRelevance + 1.5·epistemicAuthority + 1.2·confidence + 0.8·recency + 0.5·lifecycleWeight`.
4. Sort `(score desc, key asc)`; take top `capacity` (default 12).

After a reload/restart, the working set is **rebuilt** from durable beliefs — proving it was never treated as durable truth (test N).

---

## 14. First live domain — Career/Application

Map only fields that exist in the **real production schema** (recon 2026-09-07). `entity_id` is the stringified `job_applications.id` (INTEGER in the DB → e.g. `career.application:8:status`). Do **not** fabricate absent fields.

**Production source columns:** `job_applications(id, company_id, role_title, stage DEFAULT 'discovered', status DEFAULT 'active', source, source_account, confidence, first_seen, last_activity, recruiter_id, notes)`; `companies(id, name)`; `career_events(event_type, entity_type, entity_id, source, confidence, payload_json, processed)`; `career_activities(application_id, activity_type, occurred_at, confidence, source)`.

| Belief key | Value from | epistemic | source_class | note |
|---|---|---|---|---|
| `career.application:<id>:status` | `job_applications.stage` (the real status field) | OBSERVED | LIVE_CONNECTOR | e.g. `discovered`, `interviewing` |
| `career.application:<id>:role` | `job_applications.role_title` | OBSERVED | LIVE_CONNECTOR | |
| `career.application:<id>:company` | `companies.name` via `company_id` | OBSERVED | LIVE_CONNECTOR | join; skip if `company_id` NULL |
| `career.application:<id>:last_activity` | `job_applications.last_activity` | OBSERVED | LIVE_CONNECTOR | ISO ts → also `observed_at` |
| `career.application:<id>:lifecycle` | `job_applications.status` (active/…) | OBSERVED | LIVE_CONNECTOR | optional |

- **`source_account`** (`job_applications.source_account`) is carried as evidence **provenance** (`provenance.source_id`/`note`), not its own belief.
- **No `follow_up_state` column exists.** Do **not** emit a `follow_up_state` belief from `job_applications`. It may be **derived** only if a valid signal exists in `career_activities` (e.g. an `activity_type` denoting a follow-up sent/received) — and then it is an **`INFERRED`** belief (`career.application:<id>:follow_up`, `source_class=INFERENCE`, `basis='derived_from_career_activity'`), never `OBSERVED`. If no such activity exists, the belief stays **UNKNOWN** (absent).
- **Evidence confidence:** use `career_events.confidence` / `career_activities.confidence` when the observation originates from an event/activity row; otherwise the epistemic base (§7).

**Ingestion path:** a read-only projection reads `job_applications` (LEFT JOIN `companies`) and, where relevant, `career_events`/`career_activities`, and calls `submitObservation(entity={career.application, str(id)}, predicate, value, LIVE_CONNECTOR, {source_type='career.application', origin_ref='job_applications/<id>' or 'career_events/<id>', observed_at=<last_activity|occurred_at>})`. At least one real Career observation must become a durable `ACTIVE` belief and enter a reconstructed Working Set (acceptance §16).

---

## 15. Tests A–R (backend)

Deterministic unit/integration tests. Each maps to a reconciliation rule or invariant above.

| # | Assertion | Anchored in |
|---|---|---|
| A | Real observation creates a provenance-stamped belief | §8 submitObservation, R0 |
| B | Canonical key prevents uncontrolled duplicates (two obs of same key → one row) | §4, R1 |
| C | Identical repeated observation is idempotent (corroboration, no dup, no spurious revision) | R1 |
| D | Newer comparable trusted observation supersedes older state | R3 |
| E | VERIFIED outranks INFERRED (verified value wins; inferred retained superseded) | R2 |
| F | Stale info stays explicitly STALE (freshness sweep), value retained | R6 |
| G | Unresolved equal-authority conflict → CONFLICTED, both chains retained, conflict row written | R4, §10 |
| H | UNKNOWN stays unknown (no belief synthesized for a missing key) | R8, §2 |
| I | Unavailable source does NOT convert prior belief into false empty truth | **R7** |
| J | Only authorized ingestion boundaries mutate the store (unauthorized rejected + logged) | §8 |
| K | Planner/Reasoner cannot directly mutate beliefs (no code path; attempt rejected) | §8 |
| L | Working Memory contains a selected subset only (not all beliefs) | §13 |
| M | Working Memory respects capacity bound (≤ capacity) | §13 |
| N | Working Memory reconstructs after reload from durable sources | §13 |
| O | A trace row exists for every belief mutation | §1, §12 |
| P | Provenance + correlation survive a World-Model reload | §1 persistence |
| Q | Career reasoning remains functional (no regression to Slice 2 flows) | §14, governance |
| R | Slices 1–6 regressions remain green | §0 governance |

Frontend Phase A already exercises the pure Working-Memory selection (L/M) and reconstruction (N) semantics via `buildWorkingSet`; the backend must re-prove them server-side plus A–K, O–R.

---

## 16. Production acceptance (executable)

Assumes the tunnel is up (`LILITH_API_URL` → `localhost:8000`). Demonstrate the full path:

```bash
# 1. Ingest a real Career observation (internal path; shown via a one-off admin
#    task or the observation pipeline — NOT an HTTP mutation endpoint).
#    -> submitObservation(career.application/17, status="interviewing", LIVE_CONNECTOR)

# 2. Read it back through the read API (via the frontend proxy or direct).
curl -s localhost:8000/os/world?entity_type=career.application | jq '.beliefs[0]'
#    expect: key career.application:17:status, lifecycle ACTIVE, epistemic OBSERVED,
#            confidence.tier high, provenance[0].origin_ref career_events/...

curl -s localhost:8000/os/world/career.application:17:status | jq '.revision, .confidence'

# 3. Reconstruct Working Memory (server-side context build or the frontend
#    Context Builder) with focus=career.application/17, capacity=12
#    -> active set contains the belief; count <= capacity.

# 4. RESTART the backend service, then re-read:
curl -s localhost:8000/os/world/career.application:17:status | jq '.provenance, .revision'
#    expect: belief + provenance + correlation PERSIST (durable checkpoint);
#            Working Memory is REBUILT (not read from a durable WM table).

# 5. Conflict/stale honesty (zero external mutation):
#    a) submit a disagreeing equal-authority observation -> lifecycle CONFLICTED,
#       both evidence chains present, confidence lowered.
curl -s localhost:8000/os/world/career.application:17:status | jq '.lifecycle_state, .contradicted_by'
#    b) simulate the source going unavailable -> belief NOT overwritten with empty.
```

**Acceptance = all of:** real observation → typed provenance → controlled ingestion → deterministic reconciliation → durable belief → bounded Working-Memory selection → Context Builder → existing reasoning path; belief + provenance persist across restart while Working Memory is reconstructed; one controlled stale/conflict scenario shows honest state with **zero external mutation**; tests A–R green; Slices 1–6 green.

---

## 17. Governance invariants (must hold)

- A belief **never** grants permission to act. World-Model confidence **never** bypasses Policy (Slice 5). Actions still flow Planner → Ethics → Policy → Runtime → Connector → Verification.
- Connector output is **candidate observation/evidence**, not truth. Only `applyVerifiedDelta` (from Verification) sets `VERIFIED`.
- No external writes, no new connectors, no Google OAuth/Gmail/Calendar writes, no Hsin changes, no Presence cognition.
- Slices 1–6 stores, endpoints and behaviour unchanged; migration `0007` is additive only.

---

## 18. Phase B handoff checklist

When backend/VM access is available, implement in this order:
1. `0007_world_model.sql` migration (§1); register in the ledger.
2. Belief store + evidence/conflict/trace repositories (§1–2).
3. Confidence deriver (§7) and reconciliation engine (§9–10) as a pure module with unit tests A–I, O.
4. Internal ingestion service with the authorization boundary (§8) + tests J, K.
5. `GET /os/world` and `GET /os/world/{key}` read handlers (§11).
6. Career observation wiring (§14) + test Q.
7. Freshness sweep job (R6) + test F.
8. Server-side Working-Memory reconstruction mirroring `buildWorkingSet` (§13) + tests L, M, N.
9. Restart-persistence + provenance/correlation durability (§16 step 4) + test P.
10. Full regression (§0) + test R; run production acceptance (§16).

On completion, the frontend Phase A surfaces (`/world`, `src/lib/world/*`) go live automatically — no frontend change required.

---

*Design/spec only. No production backend code is included here; implementation is Slice 7 Phase B, pending backend/VM access.*
