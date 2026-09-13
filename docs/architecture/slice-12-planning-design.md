# LILITH Slice 12 — Planning / Replanning System V1 · Design (corrected & approved)

> **Status:** Phase 1 APPROVED WITH REQUIRED REFINEMENTS (1–31). This record supersedes the Phase-1 report where they conflict, and reflects the implemented + tested design.
> **Layer:** `L10 · Planning / Replanning` (Tier 5) of `cognitive-architecture-v1.md`.
> **Governing rule:** the planner *proposes* · Policy *governs* · connectors *perform I/O* · the verifier *proves*. Planning answers **HOW**, never WHAT/WHETHER/execution/proof.
> **Target:** `lilith-01` backend router only (`~/.hermes/lilith_router/`). Reuses the Slice-9 `run.py` short-circuit — **no `run.py`/`app.py`/DB/frontend change.**

---

## 0. Two load-bearing findings (why V1 is shaped as it is)

1. **The authoritative Policy engine / capability registry / connector fabric / verifier live only in the frontend `RealCommandCore`** (browser-only, separate branch, regression guard). The live Home+Telegram path is Router V2 → `/os/*`. On that path there is **no** live Policy service, capability registry, connector-health API, or independent Verifier — only read-only `/os/{world,goals,goals/focus,tasks,drafts}` and static constraint strings. Slices 8–11 integrate there; Slice 12 must too.
2. **There is no executor on the Router path.** The only real state change reachable is `POST /os/drafts` (reversible, idempotent, dedup-guarded internal write). No send capability (`mail.send_email` PROHIBITED), no task materialization, no Verifier. Therefore **post-execution replanning cannot be honestly exercised live** — it is design + fixture-tested only.

## 1. Operational definitions

- **Plan (V1 = PlanSnapshot):** a bounded, typed, ephemeral, revisable **proposal** — a DAG of typed steps, each naming preconditions, required capabilities, expected effects, and a verification requirement — that *if executed by the authorized layers* could move current World State toward the subject's outcome. Never truth, permission, execution, or proof.
- **Replanning:** deterministic construction of a **successor** plan **from an explicit prior plan** when evidence invalidates a prerequisite, a step fails, Policy prohibits, or a goal/constraint changes, preserving verified effects. **Without an explicit `priorPlan` it is Planning, not Replanning** (refinement 1/25).
- **Re-derivation (live V1):** a fresh `PlanSnapshot` produced under changed source state. This is **not** cross-turn replanning and never claims a prior-plan transition (refinements 1/2/18) — same principle as Slice-10 no-fake-novelty / Slice-11 no-fake-transition.

## 2. Ownership boundary

**Owns:** the `PlanSnapshot`/`PlanStep` DAG; step ordering/dependencies; the grounder + validator; the non-authoritative planning capability *view*; replan schema (fixture); the safe non-CoT trace. **Reads (GET only):** Goal+focus, World beliefs, tasks, drafts, Workspace snapshot, Motivation summary, (optional) ReasoningResult, the capability view. **Never:** mutates goals/beliefs/tasks/drafts; POSTs; executes tools/connectors; approves; decides Policy; claims verification; materializes tasks; invents capabilities/arguments; runs autonomous/proactive loops. Enforced by tests + symbol-absence.

## 3. Persistence & lifecycle

**Ephemeral per-turn, no DB, no `/os/plans`** (avoids the DB-redesign + Task-duplication stop-conditions; nothing to preserve without an executor). The live object is a `PlanSnapshot` with a `planSnapshotId` and **no** `revision`/`supersedesPlanId`/`derivedFromPlanId`/cross-turn `replanReasonCodes` (refinement 2/23). Lineage fields live **only** in the fixture-only Replanning model (refinement 25). `planStatus` ∈ `PROPOSED | BLOCKED | NEEDS_INFORMATION | USER_DECISION_REQUIRED` (computed this turn; no cross-turn FSM). `IN_PROGRESS/COMPLETED/FAILED` are intentionally absent (would impersonate Runtime/Verifier).

## 4. Single PlanningSubject (refinement 3/4)

Planning **never arbitrates goals**. Exactly one `PlanningSubject { kind: GOAL|USER_INTENT, goalRef?, targetRef?, targetAppId?, userIntentRef? }`. With an explicit target → the durable goal owning that target if one exists, else USER_INTENT for that target. With no target → the **Executive-derived focus** goal (Executive selected it), else USER_INTENT. No `goalCandidates[]` in `PlanningInput`.

## 5. Structure & step taxonomy

Bounded **DAG** (`dependencyStepIds`), acyclic, ≤ `planning_max_steps` (default 6, clamp [1,8]). Step `kind` ∈ `INFORMATION_GATHERING | STATE_CHANGE | POLICY_GATE | VERIFICATION | USER_DECISION`. Step planning `state` ∈ `PENDING | READY | BLOCKED | UNEXECUTABLE | INFO_NEEDED | ALREADY_SATISFIED` — **distinct** from Task/execution lifecycle (refinements 13/14). `ALREADY_SATISFIED` derives **only** from externally-owned source evidence read *before* planning; it never means executed/verified (refinement 13/16).

## 6. Preconditions vs execution requirements (refinement 9)

- **SourcePrecondition** — backed by a real readable owner only (`world|goals|tasks|drafts`): `{kind, sourceOwner, sourceRef, expectedState, satisfiedBySource, required}`. No fabricated owners.
- **ExecutionRequirement** — future-execution declarations whose owners are unavailable on the Router path: `CAPABILITY_REQUIRED · POLICY_EVALUATION_REQUIRED · APPROVAL_MAY_BE_REQUIRED · CONNECTOR_AVAILABILITY_REQUIRED · VERIFICATION_REQUIRED`. Approval is never "satisfied by request" (refinement 8).

## 7. Expected effect / verification (refinements 14/15/18/19)

Each `STATE_CHANGE` declares an `ExpectedEffect` (claim, never truth — refinement 49) and a `VerificationRequirement { expectedPredicate, targetRef, evidenceSourceOwner, observationMethod, status:"DECLARED_ONLY" }` — a specification, **not** an endpoint-as-proof and **not** performed. Task status (`completed`/`verifying`) is never treated as verification proof (refinement 14).

## 8. Capability view (refinements 4/5/6/7) — `planning_capabilities.py`

A **non-authoritative** `PlanningCapabilityDescriptor` view owned by planning (not `world_context`): `supportStatus ∈ ROUTER_PATH_SUPPORTED|KNOWN_UNAVAILABLE|NOT_DECLARED`; `policyCompatibility ∈ KNOWN_PROHIBITED|NO_KNOWN_STATIC_CONFLICT|NOT_EVALUATED`; `runtimeAvailability` **always `UNKNOWN`** (no real owner). `career.create_followup_draft`/`career.add_note` = ROUTER_PATH_SUPPORTED + NO_KNOWN_STATIC_CONFLICT + REVERSIBLE + IDEMPOTENT; `mail.send_email` = KNOWN_UNAVAILABLE + KNOWN_PROHIBITED; unknown → NOT_DECLARED → `UNEXECUTABLE`. `NO_KNOWN_STATIC_CONFLICT ≠ Policy ALLOW`; validation never emits `POLICY_ELIGIBLE`/`CAPABILITY_RUNTIME_AVAILABLE`.

## 9. Mechanism — hybrid, grounder ≠ validator (refinements 10/11/48)

Pipeline: **candidate graph** (deterministic template *or* bounded no-tool LLM) → **deterministic Grounder** (resolve refs, map declared caps, attach source-preconditions + execution-requirements + expected-effects + verification-requirements, derive dependencies, insert mandatory `USER_DECISION`/`VERIFICATION` structure, canonicalize ids/order, dependency-resolution pass) → **deterministic Validator** (schema/reference/capability-reference/dependency-cycle/boundedness/policy-compat/source-precondition verdicts; drops invalid; **never synthesizes steps**) → `PlanSnapshot` or typed failure. The bounded LLM call reuses the Slice-9 no-tool construction (`enabled_toolsets=[]`, `skip_memory`, `skip_context_files`, `max_iterations=1`). **No determinism is claimed for raw LLM output**; tests assert *same candidate graph + same sources → identical grounded/validated result* (refinement 11). The natural `answer` is composed **deterministically** from the validated plan (no overclaim, no persona-fabricated action claims).

**Live posture (V1):** the gateway calls `run_planning` with **no `model_call`** → **deterministic template only live** (refinement 19: template is not merely to force success; general/unsupported subjects honestly return `NO_VIABLE_PLAN`/`INSUFFICIENT_INFORMATION`). The LLM candidate path is implemented + unit-tested and can be enabled later behind a flag.

## 10. Validity & failure (refinements 16/32/36)

Named verdicts (never `plan.valid=true`): `STRUCTURAL_STATUS · REFERENCE_STATUS · CAPABILITY_REFERENCE_STATUS · SOURCE_PRECONDITION_STATUS · POLICY_COMPATIBILITY_STATUS (STATIC_ONLY|KNOWN_PROHIBITED_PRESENT) · EXECUTION_REQUIREMENT_STATUS (DECLARED)`. Typed no-viable reasons: `MISSING_CAPABILITY · BLOCKED_BY_POLICY · INSUFFICIENT_INFORMATION · UNRESOLVED_CONFLICT · USER_DECISION_REQUIRED · DEPENDENCY_UNSATISFIED`. **No confidence floats, no fake durations.**

## 11. Relationships

- **Reasoning (20):** `candidateNextSteps` are raw material only, grounded/validated identically to the LLM candidate graph — never copied verbatim. (V1 standalone lane has no ReasoningResult; the LLM candidate graph is the raw material.)
- **Workspace/Motivation (21):** consumes Workspace-bounded context (via `select_reasoning_input_m`); Motivation may only explain attention — no steps, no reordering, no correctness/capability/policy influence.
- **World Model (19):** typed epistemics preserved; CONFLICTED precondition → step BLOCKED; STALE → refresh/re-check; `INFERRED` never satisfies an irreversible prerequisite (none reachable in V1).
- **Ethics (22):** L09 not implemented — **no ethical verdict is fabricated**; no `ethicalReview` field on the plan.
- **Executive (43/AL):** goal focus/priority never changed by Planning.

## 12. Router integration

New `planning.py` + `planning_capabilities.py` + `tests/test_planning.py`; **append** a Slice-12 block to `world_context.py` (`detect_planning_intent`, `build_planning_subject`, `build_planning_input`, `planning_trace`); a **planning lane** in `gateway_integration.py` (before the reasoning lane) + `_log_planning`; `config.py` + `router.yaml` flags. `detect_planning_intent` fires only on **explicit plan verbs** and **yields** to 7.2 draft / 8 goal_create+goal_query / 7.2 pending (refinement 27). Generic "what could we do next?" stays with Reasoning. Live short-circuit returns `{"final_response", "mode":"planning"}` (reuses the Slice-9 `run.py` hook) only for `PLAN_PROPOSED`/`USER_DECISION_REQUIRED`; else falls through fail-open.

## 13. Config / flags

`planning_enabled:false`, `planning_mode:"shadow"`, `planning_max_steps:6`; channels reuse `cognitive_channels` (`lilith_os`, `telegram`; Discord excluded). Read per-turn (no restart to flip). Shadow = build+validate+log a snapshot, **no** user-facing answer. Live = proposal answer becomes the turn reply.

## 14. Tests (offline, injected fakes) — `test_planning.py` (39 cases)

Template path (app14 dup → USER_DECISION; 0 → PROPOSED/READY; 1 → ALREADY_SATISFIED; lookup-None → INFO). Grounder≠validator; validator adds no steps; deterministic same-candidate-same-plan. Capability view non-authoritative; static≠runtime; unknown→NO_VIABLE (MISSING_CAPABILITY); prohibited→NO_VIABLE (BLOCKED_BY_POLICY) + no Policy-eval/ALLOW claim; exec-requirements complete; source-preconditions real owners only. Verification DECLARED_ONLY; ALREADY_SATISFIED≠executed/verified; expected-effect≠precondition-truth. LLM candidate grounded-not-copied + hallucinated cap rejected; semantic (not byte) determinism; unparseable→fail-open. Cycle rejected; dangling dep dropped; bounded steps. Replanning: no-priorPlan→NOT_REPLANNING; priorPlan→preserve verified + invalidate downstream + no dup. No fake lineage; no confidence/durations. No-tool kwargs; no-CoT keys; symbol absence; never raises. Detectors: yields to draft/goal/pending; matches plan verbs; generic-next-steps not planning; single subject never a list; no goalCandidates in input. **Regression guards (offline):** motivation 32, workspace 24, reasoning 18, goal_context 9. **On VM (post-deploy):** + world_context, classifier 18, social_guard 34, integration_failopen 14.

## 15. Rollout / rollback / acceptance

Design record → backups `.bak.<TS>` → offline tests green (deploy-exact) → deploy + **one** gateway restart → `planning_mode:shadow` (log only) → inspect trace → `planning_mode:live` (per-turn, no restart) → Home acceptance (A app14 USER_DECISION, B app17 PROPOSED, C explicit action yields, D unsupported→NO_VIABLE, E prohibited→blocked-not-evaluated, F changed-state re-derivation not replan, G explicit priorPlan replan fixture) → Telegram route parity → regressions → `CURRENT_STATE.md` after PASS. **No `daemon-reload`.** Rollback: `planning_mode:shadow`/`planning_enabled:false` (no restart), or restore `.bak.<TS>` of 4 files + remove `planning*.py` + one restart. Ephemeral — no durable state to unwind.

## 16. Deferred (not V1)

Durable plan store + `/os/plans` + persisted lineage + subgraph replanning; task materialization / execution handoff; live post-execution replanning; independent Verifier; hierarchical decomposition; branching; live LLM candidate path; Ethics edge; cross-goal optimization; plan-template learning; worker assignment; proactive planning; frontend visualizer.
