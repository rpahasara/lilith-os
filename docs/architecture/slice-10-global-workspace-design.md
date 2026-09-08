# LILITH Slice 10 — Global Workspace / Attention System V1 · Design

> **Status:** Approved (Phase 1) with refinements A–D + Decisions 1–5. Implementation record below.
> **Layer:** `L02 · Attention / Global Workspace` (Tier 2) of `cognitive-architecture-v1.md`.
> **Governing rule:** the Workspace decides *what deserves attention this turn*; it owns selection, never source truth.

The Workspace is a **bounded, ephemeral, deterministic per-turn attention mechanism**. It normalizes candidate signals from durable sources, arbitrates them by typed ordered salience classes, and produces a small `WorkspaceSnapshot` (one primary + a bounded secondary set) that, in live mode, becomes the **real selection boundary** for the Slice 9 tool-less ReasoningInput. It performs no writes, invokes no tools/connectors, and never mutates goals/beliefs/tasks/drafts.

---

## 1. Ownership boundary

| Owns | References only (never mutates) | Seeds (never stores) |
|---|---|---|
| candidate normalization; deterministic salience arbitration; suppression/defer decisions; the ephemeral `WorkspaceSnapshot`; the safe attention trace | beliefs (`/os/world`), goals + Executive focus (`/os/goals*`), tasks (`/os/tasks`), drafts (`/os/drafts`) | the Slice 9 ReasoningInput |

Hard non-ownership: no POST/write, no tools, no connectors, no goal create/activate/reprioritize/complete, no belief reconcile, no task/draft mutation, no execution, no autonomous loop, no Presence bone/pose control.

## 2. Chosen architecture (Option C, additive Router-lane pattern)

New standalone `lilith_router/workspace.py` (pure stdlib, never raises) owns arbitration. `world_context.py` gains a Slice-10 block that extracts candidates from durable sources and assembles the bounded ReasoningInput. The router's **existing Slice 9 reasoning lane** builds the snapshot and, in live mode, feeds it to a bounded ReasoningInput builder. Fully fail-open to the exact current Slice 9 path.

```
reasoning-intent turn (rintent.any)
  → world_context.build_attention_candidates(...)     # normalize durable refs (read-only)
  → workspace.build_workspace_snapshot(candidates, capacity)   # dedup → rank → 1 primary + ≤N secondary + suppressed/deferred + trace
  → _log_workspace(...)                                # decisions.log (shadow or live)
  → if workspace live & snapshot has a primary:
        world_context.build_reasoning_input_bounded(..., snapshot)   # bounded support expansion around SELECTED refs only
     else / on any failure:
        world_context.build_reasoning_input(...)        # exact existing Slice 9 builder (fail-open)
  → reasoning.run_reasoning(ri)                         # unchanged: enabled_toolsets=[], skip_memory, skip_context_files
```

## 3. AttentionCandidate (schema)

Reference/summary only — never a copied source object.
```
AttentionCandidate = {
  schemaVersion:1, candidateId, correlationId,
  sourceType, sourceRef, category, summary,
  # deterministic flags (arbitration inputs — no LLM, no probability):
  systemCritical:bool, userReferenced:bool, userOverrideTarget:bool,
  isFocusGoal:bool, blockingImpact:bool, approvalPending:bool,
  deadline:bool, conflict:bool, taskFailure:bool,
  recentlyChanged:bool,            # derived ONLY from real source timestamps (no cross-turn novelty)
  recency:float|None,              # deterministic [0,1] from source updatedAt (tiebreak)
  relatedGoalId, relatedBeliefRefs[], relatedTaskIds[], relatedDraftIds[], targetApps[],
  salienceClass,                   # assigned by workspace.classify_salience (the deciding reason)
  lifecycle, createdAt, expiresAt?, suppressionReason?, provenance
}
```
`novelty` is deliberately absent (Refinement D): V1 has no previous-snapshot state owner, so no cross-turn "unseen" is claimed. `recentlyChanged` is source-timestamp-derived only.

## 4. Source types (V1)

Emitting: `GOAL, BLOCKER, TASK, DRAFT, WORLD_BELIEF`. Defined but **synthetic/test-only** (no real producer wired — Decision 5): `SYSTEM_HEALTH`/`CONNECTOR_STATE` (→ `SYSTEM_CRITICAL`/`BACKGROUND_MAINT`), `SCHEDULED_SIGNAL`. **`USER_TURN` is arbitration context, not an auto-candidate** (Refinement A): the incoming turn sets `userReferenced`/`userOverrideTarget` flags on real cognitive-object candidates but never itself consumes a capacity slot. `REASONING_RESULT` = consumer only. `MOTIVATION_DRIVE`/`WORKER_RESULT` = future-seam names only.

## 5. WorkspaceSnapshot (schema)

```
WorkspaceSnapshot = {
  schemaVersion:1, correlationId, timestamp, channel,
  primaryFocus: AttentionCandidate|None,
  secondaryItems: [AttentionCandidate],            # bounded, §6
  suppressedItems: [{candidateId, sourceType, suppressionReason}],
  deferredItems:   [{candidateId, sourceType, suppressionReason, expiresAt}],
  capacity: {primary:1, secondary:int},
  selectionReason: str,                             # named deciding class for the primary
  arbitrationTrace: [str],                          # ordered rules applied + per-candidate outcome
  expiresAt                                         # turn-bound
}
```
Ephemeral. No persistence, no `/os/workspace` endpoint (Decision 2). Reconstructible from source state.

## 6. Capacity (Decision 1)

**1 primary + up to 4 secondary.** `workspace_capacity` controls the secondary bound, hard-clamped `[0, 8]`. Deliberately smaller than the per-source lists it selects from.

## 7. Salience / arbitration (deterministic, explainable)

Ordered typed classes (rank = index; first match wins). No LLM scoring, no probabilities.
```
 1 SYSTEM_CRITICAL          (synthetic/test-only in V1)
 2 USER_OVERRIDE_TARGET     target of an explicit attention-override this turn
 3 USER_REFERENCED_BLOCKER  blocker on a user-referenced object
 4 USER_REFERENCED_OBJECT   cognitive object explicitly named by the user this turn
 5 BLOCKER_ON_FOCUS         blocker affecting the current Executive focus goal
 6 FOCUS_CONTINUITY         the current Executive focus goal
 7 UNRESOLVED_APPROVAL      approval-pending draft/task
 8 DEADLINE_URGENCY
 9 WORLD_CONFLICT           CONFLICTED/STALE belief on a relevant entity
10 TASK_FAILURE
11 RECENT_UNRESOLVED
12 BACKGROUND_MAINT         (connector/health; synthetic/test-only in V1)
```
Primary = rank-1 candidate. Secondary = next `capacity` distinct-sourceRef candidates. Tiebreak within a class: `(recency desc, sourceRef asc)`; `_wm_score`-style relevance is reserved as a lower-level tiebreak among `WORLD_BELIEF` candidates only. The **named class is always the deciding reason** in the trace.

## 8. USER_REFERENCED vs ATTENTION_OVERRIDE (Refinement B)

Deterministic phrase/entity detection only (`detect_attention_override`):
- **USER_REFERENCED** — the turn names/targets an entity (e.g. "Why is application 14 blocked?"). Candidates for that entity get `userReferenced=True` → classes 3/4.
- **ATTENTION_OVERRIDE** — the turn explicitly switches attention away ("Forget app17 for now, focus on app14"; "ignore that and look at 14 instead"). The new target's candidates get `userOverrideTarget=True` → class 2. Override target = the app id nearest a focus/switch cue (last id heuristic); reference target = first id.

Neither ever mutates Executive priority, Executive focus, or goal lifecycle.

## 9. Executive focus vs Workspace focus (critical separation)

Executive focus (`/os/goals/focus`) is durable, deterministic, owned by the Goal store. Workspace `primaryFocus` is ephemeral and per-turn. A higher-class candidate (USER_OVERRIDE_TARGET / USER_REFERENCED_*) can outrank the FOCUS_CONTINUITY candidate **without any goal write**. Canonical: Executive=app17; "why is app14 blocked?" → Workspace primary = app14 blocker; Executive focus stays app17. Enforced by tests G/H and live Scenario 1/2.

## 10. Reasoning boundary (Refinement C)

In `workspace_mode=live` a successful snapshot is the **real** ReasoningInput boundary: `build_reasoning_input_bounded` performs **bounded support expansion around the selected refs only** — the selected primary/secondary candidates, their linked goal(s), linked draft/task refs, and target-entity beliefs — and **excludes unrelated rows** that merely existed in the old per-source lists. Executive focus is still reported (read-only) as `currentFocus`; the attentional pick is reported as `workspaceFocus`/`workspaceSelectionReason`. Fail-open: no primary, or any failure, or shadow mode → the exact existing `build_reasoning_input`. Slice 9 no-tool guarantees are untouched.

## 11. Suppression / dedup / expiry

Suppression reasons (recorded, never delete source): `LOWER_SALIENCE, CAPACITY_LIMIT, STALE, DUPLICATE, IRRELEVANT_TO_CURRENT_TURN, SUPERSEDED, EXPIRED`. Dedup by exact `(sourceType, sourceRef)`; a blocker surfaced via both a goal and a draft collapses into one `BLOCKER` candidate carrying both `relatedGoalId` and `relatedDraftIds`. Expiry: candidates are turn-bound; recomputed each turn (no stored TTL), so "until source changes" is a free consequence of reconstruction.

## 12. Trace / durability / failure

Trace: one JSONL line to `decisions.log`, `lane:"workspace"`, no chain-of-thought: `correlation_id, candidate_count, source_type_counts, selected_primary_id, selected_secondary_ids, suppressed_ids, arbitration_rules_applied, deciding_rule, capacity, duration_ms, fallback_reason, timestamp`. Durability: **none** (Decision 2) — snapshot ephemeral, only trace logged, no DB/schema/`app.py` change. Failure: any source down → excluded, partial; malformed candidate → dropped; arbitration error/timeout → snapshot None → router falls to existing Slice 9 path. Workspace failure never blocks conversation.

## 13. Rollout / channel scope

Channels reuse `cognitive_channels` = `["lilith_os","telegram"]` (Discord excluded — Decision 4). Ladder: `workspace_enabled:true` + `workspace_mode:shadow` (build+log only) → inspect traces → `workspace_mode:live` (reasoning-lane consumption only). Slices 7.2/8 lanes are **not** migrated (Decision 3). Flags read per-turn (no restart to flip). One gateway restart to load code.

## 14. Files (Phase 2)

NEW `lilith_router/workspace.py`, `lilith_router/tests/test_workspace.py`. EDIT `lilith_router/world_context.py` (append Slice-10 block), `lilith_router/gateway_integration.py` (workspace build + bounded RI selection + `_log_workspace`), `lilith_router/config.py` (`workspace_enabled`/`workspace_mode`/`workspace_capacity` + `workspace_is_active`/`workspace_is_live`), `router.yaml`. **No** `app.py`/DB/frontend/`run.py`/Presence/OAuth/connector change.

## 15. Test plan

Offline unit suite (`test_workspace.py`, injected fakes): bounded construction; exact-ref preservation; dedup collapse (incl. goal+draft blocker); one primary; capacity clamp; USER_OVERRIDE beats FOCUS_CONTINUITY; USER_REFERENCED marks target without an override phrase; override vs reference distinguishable; workspace focus ≠ Executive focus + zero goal writes; belief conflict → high candidate; stale belief suppressed; blocker on focus elevated; unrelated draft not selected; task failure candidate; connector only-if-relevant; expired excluded; suppression reasons recorded; determinism; explainability; malformed rejected; partial-source failure; **live bounded RI excludes unrelated unselected rows**; **support expansion retains linked objects**; **workspace failure restores exact Slice 9 builder**; no cross-turn novelty claimed; no app.py/DB mutation; no tool/connector invocation. Regressions: reasoning 18/18, goal_context 9/9, classifier, social_guard, world_context, frontend core 67/67.

## 16. Deployment record

See `docs/architecture/slice-10/DEPLOYMENT-RECORD.md` (hashes, backups, test counts, shadow/live traces, acceptance, rollback).
