# Slice 8 — Goal / Executive System V1 (Design Record)

> **Status:** Approved (Phase 1) · Phase 2 implementation record.
> **Target:** `lilith-01` · backend only. `api/app.py` (service `lilith-os-api.service`, :8765) + `~/.hermes/lilith_router/` (service `hermes-gateway`). No frontend change.
> **Scope rule:** Executive decides **WHAT** should be pursued now. Planning (**HOW**) is out of scope. Goal ≠ Task. Slice 9 **NOT STARTED**.

---

## 0. Governing principles

- **Goal ≠ Task.** Tasks (Slice 3, `tasks` table + `/os/tasks`) remain the execution substrate and are **not modified**. A Goal is a durable, higher-level continuity object that *links* tasks/drafts and owns lifecycle, blocking, and arbitration.
- **Executive owns goals; World Model owns beliefs.** The Executive **reads** belief state read-only and **never** mutates it.
- **Planner proposes · policy governs · connectors perform I/O · verifier proves.** The Executive does none of those: no plans, no connector/tool calls, no external sends, no policy bypass.
- **Focus is derived, not stored.** Current focus is computed deterministically from durable goal rows on demand and reconstructed after any restart.
- **Deterministic arbitration only.** Typed, ordered rules. No LLM priority, no opaque scores.
- **Additive, reversible, restart-only.** Inline `CREATE TABLE IF NOT EXISTS` bootstrap; timestamped backups; **never `daemon-reload`**.

## 1. Architecture placement

Two services share one SQLite DB (`lilith.db`):

- `lilith-os-api` (FastAPI single-file `app.py`) owns the durable substrate. The **Goal store + Executive layer + controlled routes live here**.
- `hermes-gateway` runs the Router V2 cognitive lane (`~/.hermes/lilith_router/`). It reaches the substrate **over HTTP** and already creates drafts via `POST /os/drafts`. It reads/creates goals over HTTP the same way.

Home free-chat (`/os/conversation` → `lilith_os` adapter) and Telegram both converge at `run_sync` → Router V2 → `world_context.py`. That shared seam is the **only** place goal semantics are identical across channels, so the authoritative Goal read/create integration lives there. The browser `RealCommandCore` (frontend, 67/67) cannot serve Telegram and is left untouched — it is a regression guard for Slice 8.

## 2. Goal model (durable, additive)

Table `goal`:

| column | notes |
|---|---|
| `goal_id` TEXT PK | `g.<uuid>` |
| `schema_version` INTEGER | `GOAL_SCHEMA_VERSION = 1` |
| `type` TEXT | e.g. `career.followup` |
| `title` TEXT | |
| `description` TEXT | nullable |
| `source` TEXT | `USER_REQUESTED \| TASK_DERIVED \| SYSTEM_MAINTENANCE \| SCHEDULED` |
| `owner` TEXT | e.g. `user`, `system` |
| `lifecycle_state` TEXT | see §3 |
| `priority` TEXT | `URGENT \| HIGH \| NORMAL \| LOW` (default `NORMAL`) |
| `parent_goal_id` TEXT | nullable |
| `linked_task_ids` TEXT | JSON array of `tasks.task_id` |
| `target_json` TEXT | typed target, e.g. `{"type":"career.application","id":"14"}` |
| `target_key` TEXT | canonical dedup key derived from `target_json` |
| `deadline` TEXT | nullable — **only if genuinely known; never fabricated** |
| `blocked_reason` TEXT | nullable |
| `blocked_by_json` TEXT | JSON array of typed refs, e.g. `["draft:d.os2.14.a81a87acd64c2d46", ...]` |
| `resume_conditions` TEXT | nullable |
| `created_at`/`updated_at` | ISO |
| `started_at`/`blocked_at`/`suspended_at`/`completed_at`/`cancelled_at`/`failed_at` | ISO, nullable |
| `provenance_json` TEXT | `{source_channel, correlation_id, created_via}` |
| `revision` INTEGER | monotonic, 1 on create |
| `last_operation_id` TEXT | idempotency |

Indexes: `lifecycle_state`, `parent_goal_id`, `type`, `(type, owner, target_key)`.

Table `goal_trace`:

`id` PK · `correlation_id` · `goal_id` · `at` · `kind` (`transition` | `arbitration`) · `prior_state` · `new_state` · `action` · `reason` · `source` · `arbitration_winner` · `arbitration_alternatives_json` · `priority_inputs_json`. Indexes: `(goal_id, at)`, `correlation_id`.

Task linkage lives **on the goal** (`linked_task_ids`) → the `tasks` table is untouched; no task state duplicated.

## 3. Lifecycle FSM (explicit, validated)

States: `PENDING, ACTIVE, BLOCKED, SUSPENDED, COMPLETED, CANCELLED, FAILED`.
Terminal: `COMPLETED, CANCELLED, FAILED`.

| action | allowed from | to | timestamp |
|---|---|---|---|
| `activate` | PENDING | ACTIVE | started_at |
| `block` | PENDING, ACTIVE | BLOCKED | blocked_at |
| `unblock` | BLOCKED | ACTIVE | started_at |
| `suspend` | ACTIVE | SUSPENDED | suspended_at |
| `resume` | SUSPENDED | ACTIVE | started_at |
| `complete` | ACTIVE | COMPLETED | completed_at |
| `fail` | ACTIVE, BLOCKED | FAILED | failed_at |
| `cancel` | PENDING, ACTIVE, BLOCKED, SUSPENDED | CANCELLED | cancelled_at |
| `reopen` | COMPLETED, CANCELLED, FAILED | PENDING | — |

- Illegal transition → **HTTP 409 `illegal_transition`** (zero mutation).
- `BLOCKED → ACTIVE` only via explicit `unblock`; `SUSPENDED → ACTIVE` only via explicit `resume`. No implicit terminal → active. `reopen` is the only terminal exit and lands in **PENDING** (never directly ACTIVE), always traced.
- No parent/child cascade in V1 (conservative). Parent/child is a stored, queryable relationship only.
- **Completion is evidence-based.** For `career.followup`, `complete` requires a matching `created` follow-up draft for the target; otherwise **409 `evidence_required`**. No send capability exists, so "send" goals can never be system-completed.

## 4. Semantic goal de-duplication (deterministic, V1)

Before creating a **`USER_REQUESTED`** goal, match existing **non-terminal** goals on exact `(type, target_key, owner)`:

- **exactly one** → reuse/return it, create no row (`created:false`, `reason:"reused_existing"`).
- **more than one** → create nothing, return **409 `reconciliation_required`** with the equivalent `goalIds`.
- **none** → create normally.

No LLM/fuzzy matching. `target_key` is the canonical JSON of `target_json` (sorted keys), `""` when no target. Exact `operation_id` replay is separately idempotent (returns the same created goal).

## 5. Deterministic arbitration & derived focus

Candidates = goals with `lifecycle_state ∈ {ACTIVE, PENDING}` (BLOCKED/SUSPENDED/terminal excluded). Ordered comparator (ascending):

1. **lifecycle** — ACTIVE (0) before PENDING (1) — continuity with running work.
2. **priority** — URGENT < HIGH < NORMAL < LOW.
3. **deadline** — known deadline earlier first; **no deadline sorts last** (never invented).
4. **source** — USER_REQUESTED < TASK_DERIVED < SCHEDULED < SYSTEM_MAINTENANCE.
5. **recency** — `updated_at` descending.
6. **id** — `goal_id` ascending (stable total order).

`GET /os/goals/focus` recomputes the winner from durable rows (so it survives any restart), returns `{focus, candidates, arbitration:{winner, ruleFired, alternatives:[{goalId, eliminatedBy}], priorityInputs}}`, and writes an `arbitration` trace when the winner changes. **Focus is a single derived selection**; a future Global Workspace replaces the deterministic arbiter without schema change.

## 6. World Model read-only relationship (strict)

The Executive may **read** beliefs (via the read-only connection `_world_ro_conn()` — `mode=ro`, structurally write-incapable) to inform decisions: application stage, connector availability, system health, task result, stale/conflicted beliefs. Rules:

- UNKNOWN required evidence → goal may stay PENDING/BLOCKED.
- STALE → decision marked stale-informed in the trace.
- CONFLICTED → block/escalate, never silently pick a side.

**Ownership boundary is structural:** the Slice 8 block never imports or calls `submit_observation`, `submit_user_assertion`, `submit_inference_candidate`, `apply_verified_delta`, or `_world_reconcile`. A conformance test asserts the block's source text contains none of those symbols.

## 7. Controlled contract (no generic mutator)

Reads (GET): `/os/goals?state=&type=&owner=&limit=`, `/os/goals/{id}` (404 = honest unknown), `/os/goals/focus`.

Controlled writes (typed; idempotent by `operation_id`; `expected_revision` 409-guarded; FSM-validated; each emits a trace):

- `POST /os/goals` — create (with §4 dedup for USER_REQUESTED).
- `POST /os/goals/{id}/transition` — `{action ∈ activate|block|unblock|suspend|resume|complete|fail|cancel|reopen, expected_revision?, operation_id, reason?, blocked_reason?, blocked_by?, resume_conditions?, evidence?}`.
- `POST /os/goals/{id}/link_task` — `{task_id, operation_id}` (validates the task exists; appends idempotently).

No `setGoal`/`setState`/`mutateGoal`. Every mutation is typed, validated, idempotent, revision-guarded, traced.

## 8. Policy boundary

Goal state is **internal cognitive state**. Creating/transitioning a goal grants **no** external permission: no connector invocation, no external send, no draft-approval bypass. `mail.send_email` stays PROHIBITED. A goal linking a draft does not weaken that draft's existing approval/audit path. Goal creation ≠ draft creation (an explicit "track as a goal" makes a Goal; "draft a follow-up" makes a draft through the existing approval-gated path; casual prose makes neither).

## 9. Router V2 / conversation integration

Additive lane in `~/.hermes/lilith_router/` (mirrors the Slice 7.2/7.3 pattern; per-turn config read, fail-open):

- **Goal-state questions** ("what are you trying to do / what's active / what's blocked / why is goal X blocked / which goal has priority") → inject a durable **Goal grounding block** (from `/os/goals` + `/os/goals/focus`) into `combined_ephemeral`, routed to the WORK brain. Answers come from durable state, never inferred from prose.
- **Goal-tracking creation** — only on an explicit track/pursue intent with a resolvable type+target → `POST /os/goals` (server-side dedup applies). Prose requests create nothing.
- Flags `goals_enabled`, `goals_mode` (shadow→live), channels reuse `cognitive_channels` (`lilith_os`, `telegram`). Discord excluded. Home and Telegram share identical semantics because they share this seam.

## 10. Tests

Backend `api/tests/test_goal_executive.py` (stdlib `unittest`, throwaway temp DB, injected clock):

A durable create · B survives reopen · C valid transitions · D invalid transitions 409 · E parent/subgoal · F task link · G tasks table unchanged · H arbitration winner deterministic · I blocked cannot silently activate · J explicit unblock · K suspend→resume · L terminal no silent reactivate (reopen explicit) · M world read informs Executive · N conflicted belief blocks silent progression · O Executive cannot mutate World Model (symbol-absence + no-write) · P Executive invokes no connector/tool · Q trace per transition · R arbitration trace explainable · S dedup reuse (exactly one) · T dedup reconciliation-required (multiple) · U real career.followup goal (app 14) blocked on duplicate drafts.

Router: goal-intent detector unit tests. Regressions run as guards (not edited): classifier 18/18, social_guard 34/34, frontend core 67/67.

## 11. Rollout / rollback

- **Deploy:** append `# BEGIN/END SLICE 8` block to `app.py`; add the four router edits. Backups `app.py.bak.<ts>`, `lilith.before-goals.db`, `.bak.<ts>` for each router file. `ast.parse` gate before restart. **Exactly two restarts** (`lilith-os-api`, `hermes-gateway`); flag flips need none. **No `daemon-reload`.**
- **Rollout ladder:** `goals_mode: shadow` → live `lilith_os` → + `telegram`.
- **Rollback:** restore `app.py.bak.<ts>` + router `.bak` files, restart both services (goal tables go inert). Or `goals_enabled: false` (no restart) to disable the lane while keeping the store.

## 12. Live acceptance (Application 14)

Real career goal `career.followup` for `career.application:14`, using the **existing** duplicate-draft state (`d.os2.14.a81a87acd64c2d46`, `d.os2.14.01caa11f61d6395d`) — neither modified nor deleted. The goal is BLOCKED with an explicit reason: two unresolved unsent follow-up drafts require reconciliation. Demonstrate one ACTIVE/PENDING, one BLOCKED, one SUSPENDED→RESUMED, deterministic arbitration between ≥2 goals, Home + Telegram parity, and restart persistence (states/traces persist; focus reconstructed). No external email sent.

## 13. Out of scope / not started

Slice 9 (Reasoning extraction) **NOT STARTED**. No Global Workspace, Motivation/Homeostasis, autonomous goal generation, planning/replanning, Ethical Deliberation, Social Cognition changes, Hsin/Presence changes, Device/Session Sync, OAuth work, new connectors, external sending, or autonomous execution.
