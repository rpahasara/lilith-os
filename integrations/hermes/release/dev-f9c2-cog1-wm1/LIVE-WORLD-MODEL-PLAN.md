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

## Where the grounding text could persist (F1b, 2026-10-28: offline source review)

Sources: pinned upstream Hermes `f293e72`, the DEV patch `integrations/hermes/patches/dev-f9c2.patch`, and the f9c2
release manifest.

- **Hermes `state.db` `system_prompts`: grounding is not persisted.**
  - Hermes stores only `agent._cached_system_prompt` (`agent/conversation_loop.py` 926 and 1021, `run_agent.py:678`).
    That is built by `_build_system_prompt`, which excludes the ephemeral prompt (`agent/system_prompt.py:779`).
  - The gateway passes grounding as `ephemeral_system_prompt` (`gateway/run.py:5764`). Hermes appends it only when
    each API call is built (`conversation_loop.py` 1510 and 2316; `chat_completion_helpers.py` 2931).
  - The DEV patch does not change this.
  - What `system_prompts` holds is the base persona/context prompt Hermes already stores for every session.
- **`sessions/request_dump_*.json`: content-free on DEV.**
  - When written: only when a provider call fails (`non_retryable_client_error` or `max_retries_exhausted`). That is
    at most one per failed turn. The optional preflight dump needs `HERMES_DUMP_REQUESTS`, which is not set.
  - Contents: DEV's patched `agent/agent_runtime_helpers.py` (`bdeecae2…`, F9-B `_content_free_request_dump`) keeps
    only message roles and character counts, tool names, the model and the error type, status and code. It writes no
    user message, system prompt, persona or grounding text. `release/dev-f9c2/tests/test_f9b_offline.py` tests this.
  - There is no setting to turn error dumps off, and none is needed.
- **Retention covers both.** `hermes sessions prune --older-than 7` (the daily DEV retention timer) uses
  `prune_sessions` → `_remove_session_files`. That deletes each pruned session's rows, transcripts and
  `request_dump_{session_id}_*.json`, and then any `system_prompts` row no session still references
  (`hermes_state.py`). FORGET purges all of it.
- **Exceptions:**
  - A dump whose session ID never reached `state.db` (an orphan) is not matched by the prune. It is still purged by
    FORGET.
  - Model replies are stored like any reply (7-day prune and FORGET). A reply that repeats grounding facts keeps them
    for that long.
- **Decision log:** unchanged. The World Model record holds flags only, never grounding text.

**Correction:** an earlier version of this plan said dumps "may contain prompt material" and that the 7-day
retention "probably does not" cover them. The F1b review shows both are wrong for DEV.

## Proposed sequence (each step needs its own approval)

| # | Gate | Step | Notes |
|---|---|---|---|
| F1 | A (read-only) | **DONE 2026-10-28 10:08Z.** DEV `lilith-dev.db` read with `mode=ro&immutable=1` and `query_only`; the file was unchanged. Results: **0** beliefs and **0** tasks; `drafts`, `goal` and every career table **absent** | A pending or draft turn would create an empty `drafts` table (`_drafts_db` DDL). Belief-only turns do not |
| F1b | none (offline) | **DONE 2026-10-28.** See the persistence section above | No extra cleanup engineering is needed |
| F2 | **F** | **DECIDED 2026-10-28: option (a).** Empty DEV World Model data, explicitly authorized synthetic data only, and the static honesty-policy text. The owner acknowledges that a live turn also sends Hermes' existing base system/persona prompt and the synthetic user message to the configured provider through the gate. Not to be sent under this approval: real beliefs, career records, task titles, draft subjects or bodies | Not an authorization to send. The full F2 constraints are listed below |
| B | B | **Release PR** `f293e72-f9c2-cog1-wm2`: router with `cognitive_mode: live`; verifier lane policy World Model **live** on `lilith_os` only, everything else off; installer adapted from `install_wm1.sh` (same guards); offline tests | The tests show: grounding fields and limits; no writes; reads per turn; Core API compatibility with the real `app.py`; draft body excluded if F2 is (c); rollback to wm1 and cog1 |
| G1 | A, D, E, D | Preflight, stop, install, start | As for wm1 |
| G2 | **F** | **Budget reset:** `gate_budget.sh reset --owner-approved "wm2-live-test"` | Gives 5 requests. Daily caps 10 requests / 10,000 tokens; ≤1,024 output tokens per reply |
| G3 | **G** | **Live test**, preceded by an immediate F1 recheck. If real personal data appears, stop and ask for a new F2 decision. Then 2 `TEST_ONLY` console turns in one fresh session: (1) a belief question about synthetic application `999`; (2) a non-matching control. **No pending or draft-request turns**, so the `drafts` table is not created | Expected cost: **2 gate requests** (≤3 with one retry); each reply ≤1,024 tokens |
| G4 | A | **Evidence (aggregates only)** | The belief turn has one `cognitive_mode=live` record with `belief=True`; the control has none. Core API journal: exactly 1 `GET /os/world…`, **0** POSTs, **0** `/os/drafts`, `/os/tasks`, `/os/goals*` or `/career/*`. Gate `budget_used` rises by the number of turns sent, all forwarded with status 200. Replies are not error notices. **Request dumps created: 0.** Gateway stable; protected services unchanged |
| G5 | none | Request dumps or test-session rows need no extra cleanup: they are content-free or session-linked, so the 7-day prune and FORGET cover them | A dump still counts as a stop condition (a failed request) |

**F2 constraints (owner, 2026-10-28):**
- Recheck the DEV grounding tables right before any provider test. Stop on real data.
- No pending or draft turns.
- No `drafts` table creation, database seeding, memory creation or persistent Core API change.
- Every other lane off; draft and goal writes refused.
- `lilith_os` only.

## Stop conditions

Stop before the first turn if any of these hold:
- the immediate F1 recheck finds any belief, task, draft or career row that is not explicitly approved synthetic data;
- the budget reset does not show `available: true`;
- the runtime differs from G1's evidence.

Stop after any turn on any of these:
- a Core API write, or a `/os/goals/focus`, `/os/drafts`, `/os/tasks` or `/career/*` call;
- an unexpected read count;
- a provider error or refusal;
- a request dump created (content-free and pruned, but it signals a failed request);
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
