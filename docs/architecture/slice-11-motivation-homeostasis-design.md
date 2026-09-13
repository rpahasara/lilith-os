# LILITH Slice 11 — Motivation / Homeostasis System V1 · Design (corrected & approved)

> **Status:** Phase 1 APPROVED WITH REQUIRED REFINEMENTS (decisions 1–18). This record supersedes the Phase-1 report where they conflict.
> **Layer:** `L06 · Motivational / Homeostatic System` (Tier 4) of `cognitive-architecture-v1.md`.
> **Governing rule:** Motivation is a *functional regulatory read* — it names how far a functional condition is from resolved and biases attention. It owns no source truth, persists nothing, mutates nothing, calls no tools, and (deliberately narrower than the full L06 spec) does **not** influence the Executive in V1.

---

## 1. Ownership boundary

| Owns | References only (GET, never mutates) | Produces (never stores) |
|---|---|---|
| ordinal drive classification; per-drive resolution semantics; the ephemeral `MotivationSnapshot`; `DriveSignal` construction; drive→candidate mapping + dedup; the bounded motivation summary; the safe non-CoT motivation trace | World beliefs (`/os/world`), goals + Executive focus (`/os/goals*`), tasks (`/os/tasks`), drafts (`/os/drafts`) | `MOTIVATION_DRIVE` AttentionCandidates (into the Workspace pool); read-only `motivationSummary` on the bounded ReasoningInput |

**Hard non-ownership (enforced by tests):** no POST/write; no tools/connectors/shell/DB; no goal create/activate/reprioritize/complete/block/unblock/suspend/resume; no belief reconcile; no task/draft mutation; no execution; no autonomous/background loop; no Presence control; **no Executive influence in V1** (no `drive_weight` in Slice-8 arbitration); no numeric utility score; **never consumes ReasoningResult**; never raises into the caller.

## 2. Operational definitions

- **Homeostatic variable** — a named, externally-owned *functional condition* whose preferred operating state is **resolved**; deviation = the presence/severity of an unresolved condition in a real source; recovery is **event-driven** (the source clears), never timer-driven. Baseline = `SATISFIED`.
- **Drive** — a bounded **ordinal** signal `= f(condition present, severity)` computed deterministically from source-owned conditions of one class; an *attend-to* error signal per the L06 hard invariant, never a want/feeling/reward.
- **Motivational influence** — the drive becomes a low-tier Workspace candidate (bias) and a bounded read-only summary for Reasoning. It never selects, never acts.

## 3. V1 drives (decision 1) — canonical L06 names

| Drive | Status | Owner |
|---|---|---|
| **COHERENCE** | REAL | World Model |
| **GOAL_COMPLETION** | REAL | Goal store (+ Task store) |
| **SAFETY** | SYNTHETIC / TEST-ONLY (no real producer; schema-supported) | — |

Not implemented (decision 1): CURIOSITY, SOCIAL_ENGAGEMENT / loneliness / deprivation, RESOURCE_EFFICIENCY, Competence, Trust, Self-consistency, affect/emotions.

## 4. World-Model semantics (decision 2 — orthogonal dimensions)

Two independent dimensions; COHERENCE consumes both correctly and never conflates them:

- **Lifecycle:** `ACTIVE · SUPERSEDED · CONFLICTED · STALE`
- **Epistemic:** `OBSERVED · USER_ASSERTED · INFERRED · VERIFIED`
- **UNKNOWN** = honest absence; **not** a stored lifecycle and **not** a stored epistemic value; never fabricated into a belief to create pressure.

`VERIFIED`/`OBSERVED` are **epistemic** and are never treated as lifecycle values. COHERENCE keys only off **lifecycle ∈ {CONFLICTED, STALE}** (plus `contradicted_by`); epistemic is carried as evidence only. Tests prove the orthogonality (§10, T-ORTH).

## 5. Source scope (decision 3 — NO broad global scan)

Drive derivation is scoped strictly to, and only to:
- the **current turn's Workspace candidate pool** (`ws_cands`, pre-arbitration — the objects the Workspace will consider this turn),
- the **explicit user-referenced target**, and
- the **current durable Executive focus goal**.

**COHERENCE** derives only from the CONFLICTED/STALE `WORLD_BELIEF` candidates already present in `ws_cands` (Slice-10 already scopes belief extraction to referenced entities / bounded set) — no new global belief scan. **GOAL_COMPLETION** derives only from goals that are (a) the Executive focus, (b) explicitly user-referenced, or (c) present as a GOAL/BLOCKER candidate in `ws_cands`. Unrelated open/USER_REQUESTED goals are **not** scanned to manufacture standing pressure. Broader/global motivational surveillance is deferred until proactive cognition is intentionally designed.

## 6. Severity rules — deterministic & provable only

### COHERENCE (decision 4)
| Class | Condition (typed, provable) |
|---|---|
| `SATISFIED` | no relevant STALE/CONFLICTED belief in scope |
| `MILD` | relevant **STALE** source only |
| `SIGNIFICANT` | relevant **CONFLICTED** source (lifecycle) |
| `CRITICAL` | **only if** the conflicting belief key is a demonstrable prerequisite/blocker of the current requested action / a selected Workspace blocker / the Executive-focus goal **through an existing typed reference** (belief `key` ∈ that blocker's `relatedBeliefRefs` or the focus goal's `blockedBy`). If the data model cannot prove the dependency → **cap at SIGNIFICANT.** No LLM criticality. |

### GOAL_COMPLETION (decision 5)
| Class | Condition (typed, provable) |
|---|---|
| `SATISFIED` | no relevant unresolved blocker in scope |
| `MILD` | relevant **non-focus** goal `BLOCKED` |
| `SIGNIFICANT` | **Executive-focus** goal `BLOCKED`, **or** explicitly user-referenced `USER_REQUESTED` goal `BLOCKED` |
| `CRITICAL` | **only if** a typed hard blocker is provably unresolved — i.e. `goal.blockedBy` explicitly references a task whose status is `failed`/`error` (or an equivalent existing typed dependency). A merely-failed *linked* task that is **not** referenced by `blockedBy` never yields CRITICAL. If the schema cannot prove the required dependency → **cap at SIGNIFICANT.** No inference of "no path forward." |

## 7. Schemas

### DriveSignal (decision 6 — no transition claims; decision 7 — single ordinal field)
```
DriveSignal = {
  schemaVersion: 1,
  driveId,                       # "drive:<TYPE>"  (class-level)
  driveType,                     # COHERENCE | GOAL_COMPLETION | SAFETY
  intensityClass,                # SATISFIED | MILD | SIGNIFICANT | CRITICAL
                                 #   (the deterministic evaluated deviation class for THIS turn)
  sourceRefs: [str],             # REAL refs (belief keys / goalIds / taskIds)
  causeCodes: [str],             # WORLD_CONFLICTED | WORLD_STALE | GOAL_BLOCKED_FOCUS
                                 #   | GOAL_USER_REQUESTED_BLOCKED | GOAL_BLOCKED_NONFOCUS
                                 #   | HARD_BLOCKER_FAILED_TASK | SAFETY_SYNTHETIC
  relatedGoalIds: [str], relatedBeliefRefs: [str], relatedTaskIds: [str], targetApps: [str],
  evidenceCounts: {conflicted, stale, blocked, ...},   # metadata only, never decides
  resolutionConditions: [str],
  candidateEligible: bool,       # emit a Workspace candidate? (dedup vs raw pool, §8)
  persistenceClass: "reconstructed",
  provenance                     # "motivation@<channel>"
}
```
- **No** `homeostaticState` (removed — was a duplicate of `intensityClass`).
- **No** `priorIntensity` / `newIntensity` / "resolved since previous turn" — V1 has no previous-snapshot owner, so no transition is claimed. The ordinal is an *evaluated* class, not a delta.
- **No** `intensity: float`; no `thinking`/`scratchpad`/CoT fields.

### MotivationSnapshot (ephemeral)
```
MotivationSnapshot = {
  schemaVersion: 1, correlationId, timestamp, channel,
  drives: [DriveSignal],                 # all evaluated (incl. SATISFIED)
  activeDrives: [driveType],             # intensity > SATISFIED
  satisfiedDrives: [driveType],          # evaluated SATISFIED this turn  (renamed from resolvedDrives)
  highestIntensityClass,                 # trace only — NOT an aggregate utility
  sourceAvailability: {world, goals, tasks, drafts},
  partial: bool, fallbackReason
}
```
Ephemeral, reconstructible; no `/os/motivation`, no DB, no persistent rows.

## 8. Numeric vs ordinal → **ORDINAL** (`SATISFIED · MILD · SIGNIFICANT · CRITICAL`)
The only numeric reused is Slice-10 `recency`, as a within-class tiebreak only. Intensity is a within-`MOTIVATION_PRESSURE` tiebreak (`CRITICAL > SIGNIFICANT > MILD`). No equations, no decaying tanks, no LLM scores.

## 9. Workspace integration + dedup (decisions 9, 12)

Flow: `ws_cands (raw)` → `build_motivation_snapshot(ws_cands, focus, user-ref)` → for each drive decide `candidateEligible` → `motivation_candidates()` merges eligible `MOTIVATION_DRIVE` candidates into the pool → **Workspace arbitrates** (sole authority).

- New salience class **`MOTIVATION_PRESSURE`**, inserted between `RECENT_UNRESOLVED` (10) and `BACKGROUND_MAINT` (11) — **below every user/blocker/focus/approval/conflict/task-failure class by construction.** A `MOTIVATION_DRIVE` candidate sets `motivationDrive=True` and **no** raw flag, so it can never masquerade as a higher class.
- **Dedup (exact refs only, no fuzzy):** a drive's `MOTIVATION_DRIVE` candidate is emitted **only if** the drive's causal source refs are **not already represented** by a raw candidate in `ws_cands` (exact match on `relatedGoalId` / `relatedBeliefRefs` / `sourceRef` / `targetApps`). Its unique value is aggregate/standing pressure **when the condition would otherwise be unrepresented**. One real condition is never listed as both a raw blocker/conflict and a motivation candidate in the same bounded Workspace.
- Consequence: `MOTIVATION_PRESSURE` candidates never seize the primary from a user/blocker/focus signal, never change Executive focus/priority, never write a goal.

## 10. Reasoning integration — bounded by Workspace (decisions 8, 10)

- **Order is `Motivation → Workspace → Reasoning`**, so the current-turn `ReasoningResult` **cannot** feed Motivation. Enforced: Motivation reads only the approved externally-owned source state; it never imports/receives a ReasoningResult.
- After arbitration, `select_reasoning_input_m` attaches a read-only `motivationSummary` to the **bounded** ReasoningInput containing **only** drives that either (a) had a `MOTIVATION_DRIVE` candidate selected (primary/secondary), or (b) directly support a selected raw candidate through **exact** shared refs. Unselected/unrelated drive state cannot bypass the Workspace attention boundary into Reasoning.
- **V1 boundary:** `motivationSummary` is carried on the ReasoningInput **contract** (like `workspaceFocus` today, which Slice-9 `render_input_prompt` also carries without rendering). Rendering the drive framing into the reasoning prompt is a deliberate future one-line `reasoning.py` change and is **out of scope** here (reasoning.py is not edited). The source facts needed to explain "why X keeps surfacing" are already present as bounded beliefs/goals/drafts.

## 11. No self-amplification / suffering (decision 11)
Drive inputs are exclusively external source rows; a `DriveSignal` is never an input to any drive; no timers, no cross-turn accumulator; bounded at CRITICAL; source unavailable → omitted + `partial`, never assumed; source resolved → `SATISFIED` on reconstruction; no emotion labels, no loneliness, no distress narrative, no nagging/proactive messages.

## 12. Motivation / Workspace / Executive separation (decision 12)
Executive priority (durable, Executive-owned) ≠ Drive intensity (ephemeral functional deviation, Motivation-owned) ≠ Workspace salience (temporary attentional selection, Workspace-owned). Motivation may only *emit candidates*; it may not seize Workspace focus, change Executive focus/priority, create goals/tasks, act, invoke tools/connectors, or mutate beliefs.

## 13. SAFETY (decision 13)
Defined, schema-supported, **synthetic/test-only**: `build_motivation_snapshot` never derives SAFETY from live GETs (no producer). Tests inject a synthetic SAFETY source to exercise the schema/candidate path. No real health/connector producer, no background loop, no proactive perception, no interruption system in Slice 11.

## 14. Durability / timing (decision 14)
Per-turn reconstruction only; full `MotivationSnapshot` ephemeral; safe non-CoT trace metadata only; no DB, no `/os/motivation`, no `app.py`, no `run.py`, no persistent drive rows. Same durable source state after restart → identical deterministic evaluation.

## 15. Files (decision 15)
- **NEW** `lilith_router/motivation.py` (pure stdlib, never raises)
- **NEW** `lilith_router/tests/test_motivation.py`
- **EDIT** `lilith_router/world_context.py` — **pure append** of a Slice-11 block (`build_motivation_snapshot`, `motivation_candidates`, `motivation_trace`, `select_reasoning_input_m`); no in-place edits to existing functions.
- **EDIT** `lilith_router/workspace.py` — add `MOTIVATION_PRESSURE` class; one `classify_salience` rule; carry `motivationDrive`/`motivationIntensity` in `normalize_candidate`; intensity tiebreak in `_sort_key`.
- **EDIT** `lilith_router/gateway_integration.py` — motivation lane inside the existing Slice-9/10 reasoning block (build+log, live merge, `select_reasoning_input_m`) + `_log_motivation`.
- **EDIT** `lilith_router/config.py` + `router.yaml` — `motivation_enabled`/`motivation_mode` + `motivation_is_active`/`motivation_is_live` (reuse `cognitive_channels`).
- **NO** `app.py` / DB / schema / `run.py` / frontend / Presence / OAuth / connector / Policy change; no external action; no Slice 12.

## 16. Test plan (offline; injected fakes)
Core (pure `motivation.py`) + boundary (synthetic `ws_cands`/snapshot dicts). Includes the base suite **plus the decision-16 additions**:
A source always real · B no floats · C deterministic transitions·classes · D same input→identical snapshot · E CONFLICTED→SIGNIFICANT / provable typed dep→CRITICAL · F lone irrelevant STALE ≤ MILD · G blocked relevant goal→drive · H ordinary/COMPLETED goal→SATISFIED, no candidate · I resolved source removes drive · J no self-amplification · K source-unavailable→omitted+partial, never fabricated · L two drives coexist independently · M no aggregate utility decides · N/O/P no world/executive/task/draft mutation · Q no tool/connector call · R no goal creation · S no action · T `MOTIVATION_DRIVE`→deterministic `MOTIVATION_PRESSURE` candidate · U Workspace remains arbiter · V user override outranks motivation · W Executive priority unchanged · X Workspace focus may differ with zero goal write · Y Reasoning reads summary without mutating · Z no emotion booleans · AA no social drive · AB no curiosity drive · AC no suffering loop · AD restart-identical · AE Home/Telegram parity · AF 7.2 / AG 8 / AH 9 / AI 10 regressions green · AJ draft-action precedence intact · AK classifier/social_guard green · AL frontend core 67/67.
**Decision-16 additions:** T-ORTH VERIFIED/OBSERVED are epistemic not lifecycle · T-UNK UNKNOWN is absence, never fabricated · T-NOPATH non-blocking failed linked task cannot create CRITICAL GOAL_COMPLETION · T-CRIT CRITICAL requires a provable typed blocker/dependency · T-NOTRANS no prior/new transition claim exists · T-SAT `satisfiedDrives` replaces `resolvedDrives` · T-NODUP no `homeostaticState==intensityClass` field · T-NORES Motivation consumes no ReasoningResult · T-SLOT raw selected source suppresses the equivalent motivation candidate from Workspace capacity · T-SUMSEL `motivationSummary` contains only selected/supporting drives · T-BYPASS unselected drive cannot bypass Workspace into Reasoning · T-NOGSCAN-G no broad global unresolved-goal scan · T-NOGSCAN-B no broad global belief-pressure scan.

## 17. Rollout (decision 17)
design record → starting hashes + `.bak.<TS>` backups → offline tests green → deploy code + one `hermes-gateway` restart (max) → `motivation_enabled:true, motivation_mode:shadow` (build+log only) → inspect traces → `motivation_mode:live` (candidate merge; flags read per-turn, no restart) → Home acceptance → Telegram route-level parity → full regressions → `CURRENT_STATE.md` only after PASS. Leave `live` only if all checks pass; else shadow/disable and report FAIL. **No `daemon-reload`.**

## 18. Live acceptance (decision 18; existing safe state; no external action)
1. app14 real blocker derives GOAL_COMPLETION only from actual goal state. 2. "Why does application 14 keep surfacing?" → source-backed functional explanation, no emotional wording. 3. Executive focus app17 unchanged while a drive temporarily influences Workspace selection. 4. User attention override beats `MOTIVATION_PRESSURE`. 5. An equivalent raw blocker/conflict selected in Workspace prevents a duplicate motivation candidate from consuming a slot. 6. Reasoning sees only selected/supporting motivational context. 7. Action request stays on the existing controlled action path. No proactive messages, no external sends.

## 19. Rollback
Per-turn flags: `motivation_mode:shadow` (stop merging) or `motivation_enabled:false` (stop the lane), **no restart** → exact Slice-10 behaviour. Full revert: restore `.bak.<TS>` of the 4 edited files + remove `motivation.py`/tests + one gateway restart. The `MOTIVATION_PRESSURE` class addition is additive and inert while disabled (no producer emits `MOTIVATION_DRIVE`).

## 20. Failure / fallback
World/Goal/Task/Draft unavailable → omit that drive, mark `partial`, never infer. Malformed source row → dropped. Motivation module error → `_mot_snapshot=None`, `ws_cands` untouched, Slice-10/9 proceed unchanged. Motivation failure never breaks a turn.
