# Plan: live World Model grounding on DEV (Gate F/G) (PROPOSAL, nothing approved)

**Scope:** the Slice 7.2 World Model lane only, on `lilith_os` only. Every other lane stays off. Durable draft and
goal writes stay refused by the adapter. PROD is out of scope.

## What changes when the lane goes from shadow to live

On a matching turn, the DEV gateway calls the recovered PROD `build_grounding(do_write=True)` through the governed
adapter. It appends the result to the turn's ephemeral system prompt (`combined_ephemeral`), which is sent to the
normal turn model. The turn model and route are unchanged:
- Hermes `openai/gpt-oss-120b`;
- through the local provider gate to Groq;
- at most 1,024 output tokens.

The global router `mode` stays `shadow`, so social routing to the Groq social model stays off.

## Exactly what can enter the provider prompt (new, compared with today)

| Turn type | Core API reads (adapter allowlist) | Text added to the prompt |
|---|---|---|
| any matching turn | none | the static `FALLBACK_POLICY` text (World-Model-first honesty rules) |
| belief question | `GET /os/world` (filtered by application when the message names one) | up to **12 beliefs**: `entity_type:entity_id`, `predicate`, `value` (cut to 120 chars), lifecycle, epistemic state, confidence value/tier/basis, provenance `source_class:source_id (freshness)`; plus counts of conflicted and stale beliefs and the last reconcile time |
| pending question | `GET /os/tasks?limit=200`, `GET /os/drafts?limit=200` | up to **20 tasks**: `taskId`, `title`, `status`, `approvalState`. Up to **20 unsent drafts**: `draftId`, `kind`, target application id, `subject` (cut to 120 chars) |
| draft request, one unsent draft already exists for that application (reuse path) | `GET /os/drafts?target_id=…` (+ `/os/world`) | that draft's id, status, **full subject and full body** |
| draft request, none exists | `GET /os/drafts?target_id=…`, `GET /career/applications` (+ `/os/world`) | "could not save" notice only; the write is refused by the adapter. Application role and company are read but not added |
| unavailable Core API | (breaker) | "temporarily unavailable, do not guess" notice |

**Never added:** recruiter name or contact, `/memory/*`, canonical or owner memory, Privacy records, and the content
of any goal (the goal lane stays off). As with every turn, the user's own message is sent too.

**Riskiest field:** the draft reuse path sends a full draft body. Option F2-c below excludes it.

## Writes and Core API side effects

- **Drafts and goals:** `POST /os/drafts` and `POST /os/goals` are never sent (adapter refusal, tested).
- **No goal trace:** the World Model lane does not call `/os/goals/focus`, so no `goal_trace` row.
- **Schema creation:** `GET /os/world` runs `_world_ensure_once()` (idempotent `CREATE TABLE IF NOT EXISTS`). On DEV
  the maintenance thread has already done this, but a schema change on first use is possible.
- **Read bounds:** at most 16 reads per adapter call; a worst-case World Model turn makes about 3 reads. A transport
  failure opens a 30 s breaker.

## Where the grounding text could persist (must be measured, not assumed)

- **Hermes `state.db` `system_prompts` table.** FORGET purges it (`hermes_forget_executor.py` `PURGE_ORDER`). It is
  unverified whether ephemeral grounding is stored there, and whether `hermes sessions prune --older-than 7` removes
  it.
- **`sessions/request_dump_*.json`.** Observed on 2026-10-28 when the gate refused a request: 2 files of about 750
  bytes, contents not read. A dump is expected whenever a provider request fails (refusal, rate limit, timeout).
  FORGET purges `sessions/`; the 7-day retention probably does not. The DEV config has no setting for dumps.
- **Decision log:** unchanged. The World Model record holds flags only, never grounding text.

## Proposed sequence (each step needs its own approval)

| # | Gate | Step | Notes |
|---|---|---|---|
| F1 | A (read-only) | **Data-exposure inventory on DEV.** Counts and field presence only: beliefs (total and per entity type), tasks, unsent drafts, whether drafts have bodies, whether career tables exist. Uses Core API's own read-only SQLite access, as earlier audits did. No values shown | The 2026-10-27 audit saw 0 beliefs and no career tables. If DEV holds only synthetic or no World Model data, live grounding sends no new personal data |
| F1b | none (offline) | **Request-dump and `system_prompts` behaviour.** Read the pinned upstream Hermes `f293e72` source offline: what triggers `request_dump_*`, what it contains, any switch to turn it off, and whether ephemeral prompts reach `system_prompts` and get pruned | Decides whether F4's cleanup is needed and how much |
| F2 | **F** | **Owner provider-data decision**, choosing one of: **(a)** synthetic or empty DEV data only, all fields above; **(b)** real DEV data, all fields above; **(c)** as (a) or (b) but **excluding draft bodies**. Option (c) needs a small adapter or verifier change (reviewed PR) to drop the reuse-path body | Recommendation: **(a)**, verified by F1. Add (c) before any real data |
| B | B | **Release PR** `f293e72-f9c2-cog1-wm2`: router with `cognitive_mode: live`; verifier lane policy World Model **live** on `lilith_os` only, everything else off; installer adapted from `install_wm1.sh` (same guards); offline tests | The tests show: grounding fields and limits; no writes; reads per turn; Core API compatibility with the real `app.py`; draft body excluded if F2 is (c); rollback to wm1 and cog1 |
| G1 | A, D, E, D | Preflight, stop, install, start | As for wm1 |
| G2 | **F** | **Budget reset:** `gate_budget.sh reset --owner-approved "wm2-live-test"` | Gives 5 requests. Daily caps 10 requests / 10,000 tokens; ≤1,024 output tokens per reply |
| G3 | **G** | **Live test:** 3 `TEST_ONLY` console turns in one dedicated session: (1) belief question about synthetic application `999`; (2) pending question; (3) a non-matching control | Expected cost: **3 gate requests** (≤4 with one retry); each reply ≤1,024 tokens |
| G4 | A | **Evidence (aggregates only)** | Per-turn records `cognitive_mode=live` with the expected flags. Core API journal: exactly the expected GETs, **0** POSTs, **0** `/os/goals/focus`. Gate `budget_used` equals the turns sent and every request was forwarded with status 200. Replies are not error notices. **Request dumps created: 0.** `system_prompts` row-count change reported (count only). Gateway stable; protected services unchanged |
| G5 | conditional | **Cleanup** of any request dump created by the test: pre-approved as part of G3. Same pinned, targeted deletion as 2026-10-28; never a general FORGET | Any `system_prompts` row from the test is handled per F1b (retention, or an owner-approved targeted removal) |

## Stop conditions

Stop before the first turn if any of these hold:
- F1 shows real personal data while F2 chose (a);
- the budget reset does not show `available: true`;
- the runtime differs from G1's evidence.

Stop after any turn on any of these:
- a Core API write, or a `/os/goals/focus` call;
- an unexpected read count;
- a provider error or refusal;
- a request dump created (clean up under G5, then stop);
- a gateway restart, or any lane other than World Model;
- prompt material appearing in decision logs.

## Rollback

`install_wm2.sh revert` returns to wm1 (World Model shadow); `install_wm1.sh revert` returns further to cog1 (every
lane off). Each is preceded by a gateway stop and followed by `reset-failed` + start, and each needs its own approval.

Nothing in canonical memory, Privacy, authority or Core API data needs reverting, because the lane never writes.
Budget `RESET` lines are append-only history and stay.

## Not covered by this plan

Goals, reasoning, workspace, motivation, planning and ethics lanes; durable draft and goal writes (these need an
authenticated, approval-gated Core API write path first); channels other than `lilith_os`; PROD.
