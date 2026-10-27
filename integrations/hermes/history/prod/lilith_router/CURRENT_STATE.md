# LILITH Conversation Router V2 — COMPLETE / STABLE V1  (+ Slice 7.2 cognitive lane)

Status: **COMPLETE — Stable V1, in production use** (closed out 2026-08-27).
Final Discord + Telegram live validation: **PASS**.

**Slice 7.2 (World-Model-first cognitive lane): DEPLOYED + ACCEPTED 2026-09-08.**
Home (`lilith_os`) live acceptance 5/5 PASS; Telegram shared-seam parity proven;
**Telegram live end-to-end acceptance PASS (2026-09-08)**. Slice 7.2 is CLOSED.

**Slice 7.3 (semantic draft de-duplication hardening): DEPLOYED + ACCEPTED 2026-09-08.**
Deterministic cross-channel de-dup of career follow-up drafts (reuse one / refuse +
reconcile many / create none-existing). Home + Telegram parity proven. The prior
Slice 7.2 "semantic draft dedup" follow-up is now RESOLVED. See the Slice 7.3 section.

## Live production state

- Router enabled: yes
- Mode: live
- Live scope: **Discord** (`discord:__LILITH_DISCORD_CHANNEL_ID__`) + **Telegram** (all chats)
- WhatsApp: intentionally **out of scope / not live** (do not touch)
- Social provider: **Groq qwen/qwen3.8-27b**
- Technical/work provider: **Hermes GPT-5.6 Sol** (`gpt-5.6-sol`, provider `openai-codex`)
- Social response guard: **active**
- Fail-open / fallback behavior: **active** (Groq social-turn failure/rate-limit/timeout →
  native fallback chain retries on gpt-5.6-sol carrying the same social ephemeral prompt)
- Discord memory notifications: **off**
- Discord tool-progress: **off**

## Social response guard — enforced post-generation (live social turns)

- No unsolicited AI/feelings/identity disclaimers on relational prompts
  (allowed only when the user explicitly asks about consciousness / sentience /
  human-biological status / subjective emotional experience / AI nature)
- No pet name repeated in back-to-back social replies (pet names kept sparse)
- No menu-style / branching emotional replies
- Reasoning / provider / model leakage stripped; never user-visible

## Final validation (Router V2 V1)

- Discord live routing: PASS
- Telegram live routing: PASS
- Social → technical → social transitions: PASS
- Social guard (disclaimer / pet-name / menu): PASS
- Technical-history bleed-through suppression: PASS
- Explicit consciousness exception: PASS
- Classifier regression: 18/18 · Social-guard tests: 34/34

# Slice 7.2 — World-Model-first cognitive lane (DEPLOYED + ACCEPTED 2026-09-08)

## Purpose

Give LILITH's free-chat conversation runtime **World-Model-first** read semantics
and **durable action** semantics, shared identically by Home and Telegram, so the
assistant reasons from its reconciled beliefs and durable records instead of
rummaging raw sessions / files / SQLite, and so "create a draft" produces a real
durable object rather than prose. Frontend-only cognition (RealCommandCore) could
not serve Telegram; the authoritative path is the shared backend seam.

## Authoritative backend path

Home (`lilith_os` adapter :9901) and Telegram both converge at
`BasePlatformAdapter.handle_message → _message_handler → run_sync (gateway/run.py)
→ Router V2`. The cognitive lane is an **additive branch inside
`lilith_router/gateway_integration.route_turn`** (the existing hook at run.py
~5764 — NO new run.py patch). It runs BEFORE the social/technical/work decision,
governs ONLY belief / pending / durable-draft turns, records mode `WORK` (so the
social-reply guard skips it), and returns an override that injects a
World-Model grounding into `combined_ephemeral` and runs on the WORK brain
(`gpt-5.6-sol`, `force_rebuild=true`). Fully fail-open: any error → native path.

## World-Model-first read semantics

Context Builder `lilith_router/world_context.py` (READ-ONLY): reads `GET /os/world`
(bounded **top-k = 12**, entity-focused when an application id is present) and
renders a belief block preserving **lifecycleState, epistemicState, confidence +
basis, provenance / source class, freshness, conflicted / stale**. It never
mutates the World Model and never duplicates raw private payloads where a
summary/ref suffices.

## Fallback rules (injected policy)

- **Sufficient** → answer from beliefs; do NOT search files / sessions / SQLite.
- **UNKNOWN** → say plainly it is not known / not tracked; no fabricated value or
  formal status; raw sources only if genuinely helpful and not already answered.
- **STALE** → say it is stale; offer to refresh rather than presenting as current.
- **CONFLICTED** → expose the conflict and the competing evidence; never silently
  pick a winner.
- Raw file / session / SQLite retrieval only when a fact is absent / stale /
  conflicted, or when the user explicitly asks for raw sources. Generic tools are
  governed by the injected policy, not globally suppressed.

## Durable draft semantics (reuses existing /os/drafts — NO second store)

Create/save/prepare/queue + follow-up verb (excluding "example") with an app id →
deterministic compose → idempotent `POST /os/drafts`
(`draftId d.os2.<appid>.<hash>`, `idempotencyKey os2.<appid>.<hash>`, kind
`career_followup`, status `created` = **UNSENT**, reversible/soft-discardable).
The real draft record is injected as ground truth so the reply is accurate; on a
non-confirming write the model is told to say it could NOT save. Persistence is
never claimed unless `/os/drafts` confirms it. No email is ever sent (no send
capability exists). "Write me an example email" → prose only, no durable object.

## Pending state (durable only)

Answered from `GET /os/tasks` + `GET /os/drafts` (pending/non-terminal tasks +
`created` drafts). Never inferred from prior conversational prose.

## Live channels currently enabled (cognitive lane)

- `lilith_os`  (Home free-chat) — live
- `telegram`   — live
- **Discord: EXCLUDED** (not in `cognitive_channels`; the lane does not touch it)

## Feature flags (`router.yaml`, read per-turn — NO restart to flip)

    cognitive_enabled: true
    cognitive_mode: live
    cognitive_channels: ["lilith_os", "telegram"]

Ladder used: shadow(lilith_os) → live(lilith_os) → live(lilith_os, telegram).

## Acceptance / tests

- **Home live acceptance: 5/5 PASS** — (1) beliefs split into confirmed /
  observations / conflicts / unknowns with confidence + sources; (2) app-14 belief
  + provenance; (3) follow-up status honest UNKNOWN; (4) real durable draft
  `d.os2.14.a81a87acd64c2d46` created + verified in `/os/drafts`; (5) pending read
  from durable state incl. that draft. Pre-enable shadow reproduced the original
  bug (raw sqlite/gmail rummaging); the live lane fixes it.
- **Telegram shared-seam parity: PROVEN** — the real `route_turn` returns identical
  cognitive grounding for `platform=telegram` vs `lilith_os` (same WORK brain).
- **Telegram live end-to-end acceptance: PASS (2026-09-08)** — World-Model-first read
  prompts passed; app-14 provenance/unknown semantics passed; "create a follow-up
  draft for application 14, but do not send it" returned a real durable UNSENT draft
  `d.os2.14.01caa11f61d6395d`; "what tasks or approvals are pending" correctly read
  durable state (no active tasks + four unsent drafts).
- Tests: **test_world_context PASS · classifier 18/18 · social_guard 34/34 ·
  frontend core 67/67**.

## Change surface (what Slice 7.2 did and did NOT touch)

- Changed (backend, `~/.hermes/lilith_router/`): NEW `world_context.py`,
  NEW `tests/test_world_context.py`, EDITED `config.py`, `gateway_integration.py`,
  `router.yaml`. Installed backups TS **20260908-051429**
  (`config.py.bak`, `gateway_integration.py.bak`, `router.yaml.bak`) plus
  `router.yaml.bak.20260908-052432 / -052734 / -053143` (flag-flip snapshots).
- One gateway restart to load the (cognitive-OFF) code; flag flips needed no
  restart. Post-restart healthy: PID active, NRestarts=0, no router/world_context
  traceback, Telegram+Discord sockets up, `:9901` listening.
- **NOT changed: `app.py`, DB schema, World-Model schema, `gateway/run.py`,
  Hsin/Presence, OAuth, connectors, external-write policy, frontend code.**

## Rollback procedure (Slice 7.2)

- Fast disable (NO restart): set `cognitive_enabled: false` in `router.yaml`
  (leaves social routing fully intact).
- Full code revert: restore the three `.bak.20260908-051429` files
  (`config.py`, `gateway_integration.py`, `router.yaml`), remove `world_context.py`
  (and `tests/test_world_context.py`), then `sudo systemctl restart hermes-gateway`.

## Remaining gap

- None blocking. Home and Telegram live end-to-end acceptance both PASS. See
  "Known follow-ups" below.

## Known follow-ups (non-blocking)

- **Semantic draft de-duplication — RESOLVED by Slice 7.3 (2026-09-08).** See the
  Slice 7.3 section below.
- **Reconcile the two historical Application 14 duplicate drafts (manual, user).**
  `d.os2.14.a81a87acd64c2d46` + `d.os2.14.01caa11f61d6395d` remain intact (NOT
  deleted/modified by 7.3). A new "create a follow-up draft for application 14"
  request now REFUSES and asks the user to reconcile them (keep one / merge /
  discard) before any send. 7.3 never auto-resolves or deletes them — this is a
  user decision.

# Slice 7.3 — Semantic draft de-duplication hardening (DEPLOYED + ACCEPTED 2026-09-08)

## Purpose

Prevent future semantically duplicate career follow-up drafts **deterministically
across channels** (Home + Telegram), without deleting or mutating existing drafts.
Root cause (from 7.2): the create idempotency key was per
(session + exact message + app), so the same logical request from a different
channel/wording created a second durable row.

## Deterministic de-dup rule (no LLM, no fuzzy matching)

On a create/save/prepare/queue follow-up request WITH an application id, BEFORE
creating, query durable `GET /os/drafts?target_id=<id>` and match exactly:
`target.type == application` AND `target.id == <id>` AND `kind == career_followup`
AND `status == created` (unsent/unresolved; `discarded` is resolved). Then:

- **exactly one** match  → reuse it; create nothing; report the existing draft id.
- **more than one** match → create nothing; report that duplicates exist, list
  their ids, and require reconciliation before any send.
- **none**                → create normally via the existing Slice-4 `/os/drafts`.

Fail-open: if the lookup errors, it proceeds to create (no worse than pre-7.3).

## Feature flag

`router.yaml` `cognitive_draft_dedup: true` (default true; read per-turn — set false
to restore pre-7.3 always-create without reverting code).

## Change surface

- Changed (backend, `~/.hermes/lilith_router/`): `world_context.py`
  (+`find_unresolved_followups`, de-dup branch in `build_grounding`),
  `config.py` (+`cognitive_draft_dedup`), `gateway_integration.py` (passes the
  flag), `tests/test_world_context.py` (+8 de-dup cases). `router.yaml` gained one
  line (`cognitive_draft_dedup: true`) — live cognitive/social flags preserved.
  Installed backups TS **20260908-091656**.
- One gateway restart to load the code (done; PID active, NRestarts=0, healthy).
- **NOT changed: `app.py`, DB schema, World-Model schema, `run.py`, external-send
  path, Hsin/Presence, OAuth, connectors, external-write policy, frontend.**

## Tests / results

- `test_world_context` incl. 8 new de-dup cases: reuse-single, Home→Telegram
  no-second-draft, repeated-identical, different-app→new, different-kind→new,
  discarded-ignored→new, multiple→reconcile, dedup-disabled→create. **All PASS.**
- Regressions green: classifier 18/18 · social_guard 34/34 · frontend core 67/67.

## Live acceptance

- **Rule 7 (App 14, real state):** "create a follow-up draft for application 14" →
  refused, surfaced both duplicate ids + reconciliation requirement, **nothing
  sent**, App 14 still exactly its 2 original drafts (unchanged).
- **Rules 1/2/3 (synthetic app 999999):** first request created one draft; a second
  request from a different session/wording **reused** it (count stayed 1).
- **Rule 6 (live):** discarding that draft then re-requesting created a NEW draft
  (discarded does not block). Synthetic test drafts cleaned up (999999 → 0).
- **Home + Telegram parity:** the real `route_turn` returns identical de-dup
  grounding for `platform=telegram` vs `lilith_os` (App 14 duplicates case), no
  write.

## Rollback (Slice 7.3)

- Fast disable (NO restart): set `cognitive_draft_dedup: false` in `router.yaml`
  (keeps the rest of the cognitive lane live).
- Full code revert: restore the `.bak.20260908-091656` files
  (`world_context.py`, `config.py`, `gateway_integration.py`,
  `tests/test_world_context.py`, `router.yaml`), then
  `sudo systemctl restart hermes-gateway`.

## Key references (backups / config)

- Router package: `~/.hermes/lilith_router/` (config `router.yaml`, read per-turn — no
  restart needed for scope / cognitive-flag changes)
- run.py integration seam: `~/.hermes/hermes-agent/gateway/run.py`
  (route_turn ~5764, enforce_reply ~6527); backups
  `run.py.bak.20260826-104319`, `run.py.bak.20260826-113403`  (UNCHANGED by Slice 7.2)
- Groq provider plugin: `~/.hermes/plugins/model-providers/groq/`
- Notable backups:
  - Slice 7.2: `config.py.bak.20260908-051429`,
    `gateway_integration.py.bak.20260908-051429`, `router.yaml.bak.20260908-051429`
  - `router.yaml.bak.20260827-101658` (pre-Telegram-enable, V1)
  - `policy.py.bak.20260827-082317`, `social_guard.py.bak.20260827-082317`
  - `social_guard.py.bak.20260827-085515`, `state.py.bak.20260827-085515`,
    `gateway_integration.py.bak.20260827-085515`, `tests/test_social_guard.py.bak.20260827-085515`
  - Full checkpoint set: `~/.hermes/lilith_router/checkpoints/*.20260826-122342`
- Rollback (router scope): restore a `router.yaml.bak.*` (no restart).
  Rollback (code): restore the relevant `.bak.*` + `sudo systemctl restart hermes-gateway`.

## Not started yet (explicitly deferred)

- **Slice 8 (Goal / Executive): NOT STARTED.**
- Avatar, voice, System, and other LILITH OS work — not begun.

================================================================================
SLICE 8 — GOAL / EXECUTIVE SYSTEM V1  (CLOSED / PASSED 2026-09-08)
================================================================================

WHAT: A durable Goal/Executive layer answering "what is LILITH trying to
accomplish now?". Executive decides WHAT to pursue; Planning (HOW) stays out of
scope. Goal != Task — the tasks table is untouched; a Goal links tasks/drafts and
owns lifecycle + focus. Focus is DERIVED (never stored). Arbitration is
deterministic (typed ranks; no LLM).

BACKEND (api/app.py, additive `# BEGIN/END SLICE 8` block; backup
app.py.bak.20260908-100133; DB snapshot lilith.before-goals.db):
  - Tables: goal, goal_trace (inline CREATE IF NOT EXISTS; schema_version=1;
    revision + last_operation_id idempotency; user_version stays 0).
  - Lifecycle FSM PENDING/ACTIVE/BLOCKED/SUSPENDED/COMPLETED/CANCELLED/FAILED;
    illegal transition -> 409 illegal_transition; terminal->active only via
    explicit `reopen` -> PENDING (traced). Completion is evidence-based
    (career.followup can never be system-completed = honest, no send capability;
    career.prepare_followup needs a real draft).
  - Deterministic USER_REQUESTED de-dup on (type, target_key, owner): exactly one
    non-terminal -> reuse; multiple -> 409 reconciliation_required; none -> create.
  - Arbitration rules (ordered): lifecycle > priority > deadline > source >
    recency > id. GET /os/goals/focus recomputes focus + explainable trace.
  - World Model READ-ONLY (via _world_ro_conn); block contains NO belief-mutation
    symbol (conformance test). No connector/tool/send.
  - Routes: GET /os/goals, /os/goals/{id}, /os/goals/focus; POST /os/goals,
    /os/goals/{id}/transition, /os/goals/{id}/link_task. NO generic setter.

ROUTER LANE (~/.hermes/lilith_router/, additive; backups .bak.20260908-100618):
  - world_context.py: detect_goal_intent + build_goal_grounding (+GOAL_POLICY);
    goal-state questions grounded from /os/goals + /os/goals/focus; explicit
    "track as a goal" creates via POST /os/goals (server-side dedup, evaluateBlock).
  - gateway_integration.py: goal lane in _route_turn_impl (mirrors cognitive lane;
    fail-open; records WORK mode) + _log_goal.
  - config.py + router.yaml: goals_enabled:true, goals_mode:live (shadow->live),
    channels reuse cognitive_channels ["lilith_os","telegram"]. Read per-turn.

TESTS: backend 22/22 (tests/test_goal_executive.py, temp DB); router
goal_context 9/9; regressions classifier 18/18, social_guard 34/34, world_context
all pass; frontend core 67/67.

LIVE ACCEPTANCE (PASS): Home free-chat "track application 14 as a goal" -> durable
USER_REQUESTED career.followup goal auto-BLOCKED (two real unsent drafts
d.os2.14.a81a87acd64c2d46 + d.os2.14.01caa11f61d6395d require reconciliation;
drafts UNTOUCHED, nothing sent). Grounded Q&A ("what are you trying to do", "what
is blocked and why", "which goal has priority") answered from durable Goal state.
Demonstrated ACTIVE (g.95cee37 prepare app17, HIGH, task-linked), PENDING
(g.5585f6c follow-up app8), BLOCKED (g.2493fb3 app14), SUSPEND->RESUME (focus moved
to g2 then back to g1), deterministic arbitration (winner g1 by lifecycle rule).
Telegram route-level parity proven (identical durable grounding; goals_is_live
telegram=True). Restart persistence proven (lilith-os-api restarted; goals/traces
persist, focus reconstructed). Two gateway/api restarts total; NO daemon-reload.

ROLLBACK: goals_enabled:false (no restart) disables the lane; or restore
app.py.bak.20260908-100133 + router .bak.20260908-100618 + restart both services
(goal tables go inert).

SLICE 9 (Reasoning extraction): NOT STARTED.

================================================================================
SLICE 9 — REASONING EXTRACTION V1  (CLOSED / PASSED 2026-09-08)
================================================================================

WHAT: Extracted "reasoning" into a bounded, TOOL-LESS cognitive component. It
receives a bounded ReasoningInput (durable World + Goal + pending state), runs ONE
side-effect-free model call, and returns a typed ReasoningResult whose natural
`answer` is the user reply; typed fields (assumptions/uncertainties/conflicts/
blockers/candidateNextSteps) are persona-neutral and evidence-grounded. It never
acts: no tools, no memory/context files, no World/Goal/task/draft mutation, no
connector/send, no approval decision, no verified-completion claim, no CoT output.

FILES (additive; backups .bak.20260908-141508):
  - NEW ~/.hermes/lilith_router/reasoning.py  (schemas + stdlib validator +
    REASONING_SYSTEM prompt + tool-less model call; Hermes internals lazy-imported;
    resolvers/constructor injectable for offline tests).
  - EDIT world_context.py: detect_reasoning_intent (analytic framings only; YIELDS
    to 7.2 draft/pending, 8 goal_create/goal_query) + build_reasoning_input (bounded,
    provenance-by-ref, epistemic preserved).
  - EDIT gateway_integration.py: reasoning lane in _route_turn_impl (runs before
    7.2/8 but yields to them; records WORK; returns {"final_response": answer}) +
    _log_reasoning (safe non-CoT trace).
  - EDIT config.py + router.yaml: reasoning_enabled:true, reasoning_mode:live
    (shadow->live), channels reuse cognitive_channels ["lilith_os","telegram"].
  - EDIT gateway/run.py (backup .bak.20260908-141508): ONE minimal additive
    fail-open short-circuit — when route_turn returns a final_response, use it as
    `result` (with messages so the turn persists) INSTEAD of running the tool-
    exposed agent; it STILL flows through enforce_reply (hook at run_conversation
    ~6457, enforce_reply ~6527). Normal turns untouched; fail-open to the agent.

NO-TOOL BOUNDARY: primary = enabled_toolsets=[] (live proof: constructed agent has
tools=0, valid_tool_names=0, enabled_toolsets=0). Secondary = max_iterations=1,
skip_memory, skip_context_files.

INTENT PRECEDENCE: explicit action (draft) and Slice-8 goal-state stay on their
existing paths; Reasoning owns only NEW analytic framings (uncertainty/blocker/
options/info/analyze). Verified live: "create a follow-up draft for app 17" ->
lane=cognitive (no 3rd draft, nothing sent); "which goal deserves attention" ->
lane=goal; plain "what do you know about app 14" -> lane=cognitive.

TESTS: reasoning 18/18 (tests/test_reasoning.py: detection precedence, no-tool
construction, schema validation, CoT-drop, fail-safe) + classifier 18/18 +
social_guard 34/34 + world_context all + goal_context 9/9 + frontend core 67/67.

LIVE ACCEPTANCE (PASS, Home /os/conversation): uncertainty (facts vs explicit
unknowns), blocker (app-14 two unsent drafts + approval/connector/prohibited
constraints, no send), options (approval-gated proposals, reconcile drafts). #4
goal via Slice 8. Telegram parity: reasoning_is_live=True both channels; identical
bounded durable input home==telegram. Ephemeral result; safe non-CoT trace to
decisions.log; no DB/schema change. One gateway restart; NO daemon-reload.

ROLLBACK: reasoning_enabled:false (no restart); or restore .bak.20260908-141508
(incl. run.py) + one gateway restart.

KNOWN GAP: if turn-history reconstruction fails in the run.py short-circuit, a
reasoning turn is answered but not persisted (fail-safe branch); low impact
(reasoning reads durable state).

SLICE 10 (Global Workspace / Attention V1): DEPLOYED + ACCEPTED 2026-09-08 — see section below.


## Slice 10 — Global Workspace / Attention System V1 — DEPLOYED + ACCEPTED 2026-09-08

Bounded, ephemeral, DETERMINISTIC per-turn attention layer (L02). New `workspace.py`
(pure stdlib, never raises) owns arbitration: normalize AttentionCandidate refs ->
dedup -> rank by typed ordered salience CLASSES -> 1 primary + <=4 secondary +
suppressed/deferred + safe non-CoT trace. `world_context.build_attention_candidates`
extracts candidates from durable Goal/Draft/Task/World refs (READ-ONLY). In
`workspace_mode=live` a snapshot with a primary is the REAL boundary for the Slice 9
ReasoningInput (`build_reasoning_input_bounded`: bounded support expansion around the
SELECTED refs only); shadow / failure / no-primary falls open to the exact existing
`build_reasoning_input`. Reuses `cognitive_channels` (lilith_os + telegram; Discord
excluded). Slices 7.2/8 lanes UNCHANGED. Workspace performs NO writes/tools/connectors
and NEVER mutates goals/beliefs/tasks/drafts.

FLAGS (router.yaml, read per-turn): `workspace_enabled: true`, `workspace_mode: live`,
`workspace_capacity: 4` (secondary; hard-bounded [0,8]).

SALIENCE (ordered classes; the named class is the deciding reason; no LLM/probability):
SYSTEM_CRITICAL(synthetic/test-only) > USER_OVERRIDE_TARGET > USER_REFERENCED_BLOCKER >
USER_REFERENCED_OBJECT > BLOCKER_ON_FOCUS > FOCUS_CONTINUITY > UNRESOLVED_APPROVAL >
DEADLINE_URGENCY > WORLD_CONFLICT > TASK_FAILURE > RECENT_UNRESOLVED >
BACKGROUND_MAINT(synthetic/test-only). USER_TURN is arbitration context only (never
auto-consumes a slot). No cross-turn novelty claimed (source-timestamp `recentlyChanged`
only). Attention override != Executive priority.

EXEC vs WORKSPACE FOCUS: independent. Verified live — Executive focus stayed
`g.95cee3719e3c4a4f9705486b479cb8af` (app17) across every attention turn; zero goal write.

TESTS: workspace 24/24 + reasoning 18/18 + goal_context 9/9 + classifier 18/18 +
social_guard 34/34 + world_context all. (frontend untouched — no frontend change.)

LIVE ACCEPTANCE (PASS, Home /os/conversation, workspace_mode:live):
- "why can't you follow up on application 14" -> primary USER_REFERENCED_BLOCKER;
  reasoning consumed the bounded snapshot (reasoning trace correlation_id == workspace
  snapshot id `w.*`); Executive focus app17 unchanged.
- "forget application 17 for now, focus on application 14 instead" -> primary
  USER_OVERRIDE_TARGET; answer confirms durable executive focus still app17 (unchanged).
- "what is uncertain about application 14" -> facts vs explicit unknowns; blocker
  elevated; nothing fabricated.
- "what could we do next for application 14" -> OPTION_GENERATION; proposals only; no
  execution.
- action precedence "create a follow-up draft for application 17, do not send it" ->
  lane=cognitive (Slice 7.3), workspace NOT engaged, no 3rd draft, nothing sent.
Telegram route-level parity: workspace_is_live True both channels; identical selection
core (primary class/ref, secondary refs, capacity) home == telegram. No Telegram transport.

DEPLOY: additive router-lane patch (config.py / gateway_integration.py / world_context.py
append / router.yaml + new workspace.py + tests/test_workspace.py); backups
`.bak.20260908-155803`; NO app.py/DB/frontend/run.py change; one gateway restart
(PID 228972, NRestarts=0); NO daemon-reload.

ROLLBACK: `workspace_enabled: false` (no restart) -> exact pre-Slice-10 Slice 9 path; or
restore `.bak.20260908-155803` + one gateway restart. Ephemeral (no durable workspace state).

SLICE 11 (Motivation/Homeostasis): NOT STARTED.

## Slice 11 — Motivation / Homeostasis V1 (CLOSED, PASS 2026-09-08)
Additive router lane: NEW `motivation.py` (pure ordinal drive core) + world_context Slice-11 block
(`build_motivation_snapshot`/`motivation_candidates`/`motivation_trace`/`select_reasoning_input_m`) +
workspace.py `MOTIVATION_PRESSURE` class (rank 11) + gateway motivation lane + `_log_motivation` +
config `motivation_enabled`/`motivation_mode`. Backups `.bak.20260908-204811`. One gateway restart
(PID 233301). Flags: motivation_enabled: true, motivation_mode: live (per-turn, no restart to flip).
V1 drives: COHERENCE (World-Model CONFLICTED/STALE) + GOAL_COMPLETION (BLOCKED scoped goal);
SAFETY schema-only/synthetic. Ordinal SATISFIED/MILD/SIGNIFICANT/CRITICAL; NO floats; NO Executive
influence; NO ReasoningResult input; dedup vs raw ws_cands (candidateEligible); scoped to
ws_cands+user-ref+focus (no global scan). Tests: motivation 32/32, workspace 24/24, reasoning 18/18,
goal_context 9/9, world_context ALL, classifier 18/18, social_guard 34/34, integration_failopen 14/14.
Live (Home): app14 -> GOAL_COMPLETION SIGNIFICANT (GOAL_USER_REQUESTED_BLOCKED) from real blocked
USER_REQUESTED goal g.2493fb35, candidateEligible=false (deduped, 0 slots consumed), COHERENCE
SATISFIED; Executive focus g.95cee37 (app17) UNCHANGED; app14 drafts 2->2 (no writes); "why keep
surfacing" = functional source-backed explanation, no emotional wording. Telegram parity PARITY_OK.
Rollback: motivation_mode: shadow / motivation_enabled: false (no restart), or restore
.bak.20260908-204811 + rm motivation.py + one restart. Cosmetic: trace sourceAvailability.drafts=false
(drafts are not a V1 motivation source; not an error). SLICE 12: NOT STARTED.


## Slice 12 — Planning / Replanning V1 (CLOSED 20260909-041202)
- Additive Router-lane; proposal-only HOW layer. NEW planning.py + planning_capabilities.py + tests/test_planning.py; world_context.py Slice-12 block (detect_planning_intent / build_planning_subject / build_planning_input); gateway_integration.py planning lane + _log_planning; config.py + router.yaml flags. Reuses the Slice-9 run.py short-circuit; NO run.py/app.py/DB/frontend change.
- Ephemeral PlanSnapshot (no /os/plans, no DB). Single PlanningSubject (no goal arbitration). Bounded DAG; grounder != validator; deterministic template live (bounded no-tool LLM candidate path implemented + unit-tested, not wired live). Non-authoritative capability view (runtime availability UNKNOWN; NO_KNOWN_STATIC_CONFLICT != Policy ALLOW). VerificationRequirement DECLARED_ONLY. Post-execution replanning design+fixture-only (no executor).
- Flags: planning_enabled: true, planning_mode: live, planning_max_steps: 6 (cognitive_channels: lilith_os + telegram; Discord excluded). Per-turn; flip needs no restart.
- Tests: planning 40/40; regressions motivation 32, workspace 24, reasoning 18, goal_context 9, world_context ALL, classifier 18, social_guard 34, integration_failopen 14. Route-level + live-lane acceptance PASS (app14/app17 USER_DECISION_REQUIRED from real duplicate drafts; Home/Telegram parity; action precedence; zero writes). Rollback: planning_mode:shadow / planning_enabled:false (no restart), or restore .bak.20260909-035048 + .bak.s12fix.* + one restart.

## Slice 13 — Ethical Deliberation V1 (CLOSED 20260909-055359)
- Additive Router-lane; advisory-only L09. NEW ethics.py + ethics_principles.py + tests/test_ethics.py; world_context.py Slice-13 block (detect_ethics_intent / build_turn_evidence / build_ethical_subject / build_ethical_input); gateway_integration.py ethics lane (after planning, before reasoning) + _log_ethics; config.py + router.yaml flags. Reuses the Slice-9 run.py short-circuit; NO run.py/app.py/DB/frontend/Policy/Verifier/executor change.
- Ethics may deliberate; Policy governs. NO ALLOW/DENY, no execution/approval/verification, no goal/plan/belief/draft mutation, no Policy impersonation. Ephemeral EthicalResult (no /os/ethics, no DB); content-seeded ethicalSnapshotId (channel/corr-independent). Single USER_INTENT subject live; PLAN_SNAPSHOT shadow-only; ACTION_PROPOSAL non-live. Four fixed principles (USER_AUTONOMY, PRIVACY_MINIMIZATION, NON_MALEFICENCE, PROPORTIONALITY; principleSetVersion 1). Ephemeral TURN evidence is a real source owner (sourceOwner=TURN); concerns cite TURN/world/goals/tasks/drafts refs only, never raw text, never a fabricated preference / third-party identity / sensitivity label. Deterministic live path (grounder != validator); bounded no-tool LLM candidate path implemented + unit-tested, NOT wired live. Hard known prohibition -> SKIPPED_KNOWN_PROHIBITION (prohibitionBasis=STATIC_POLICY_MIRROR, authoritativePolicyEvaluation=false; no moral balancing). No importanceClass/uncertaintyClass/score; humanReviewRecommended from typed conditions only.
- Flags: ethics_enabled: true, ethics_mode: live, ethics_max_concerns: 4, ethics_max_tensions: 3 (cognitive_channels: lilith_os + telegram; Discord excluded). Per-turn; flip needs no restart.
- Tests: ethics 54/54; regressions planning 40, motivation 32, workspace 24, reasoning 18, goal_context 9, world_context ALL, classifier 18, social_guard 34, integration_failopen 14. Route-level + lane-level (_route_turn_impl) acceptance PASS (A EXECUTION_CONSENT_UNCLEAR, B PRIVACY_EXPOSURE, C SKIPPED_KNOWN_PROHIBITION, E IRREVERSIBILITY_UNDER_UNCERTAINTY/HUMAN_REVIEW, F UNNECESSARY_SCOPE, G INSUFFICIENT_CONTEXT; Home/Telegram outcome+snapshot parity; action precedence preserved; zero writes). Rollback: ethics_mode:shadow / ethics_enabled:false (no restart), or restore .bak.20260909-055359 (config/gateway/world_context/router.yaml) + remove ethics*.py + tests/test_ethics.py + one restart.
- One gateway restart total (MainPID 239056 -> 242686). NO daemon-reload (pre-existing benign unit drift). Final hashes: config df944b19; gateway 7d98f158; world_context 46b8187e; router.yaml a7e2f25f; ethics b6e3ce49; ethics_principles 178990e5.

**SLICE 14: NOT STARTED.**
