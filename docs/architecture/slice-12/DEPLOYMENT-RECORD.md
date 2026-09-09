# Slice 12 — Planning / Replanning V1 · Deployment Record (PASS)

**Date:** 2026-09-09 · **Target:** `lilith-01` backend router only (`~/.hermes/lilith_router/`). **No** `run.py` / `app.py` / DB / frontend / Presence / OAuth / connector / Policy-engine change. Reuses the Slice-9 `run.py` `final_response` short-circuit.

## Starting → final hashes (sha256)
| File | pre | post |
|---|---|---|
| `config.py` | `76c4604d06ee0499…` | `0a9949ba312c30d6…` |
| `gateway_integration.py` | `9c667eef0699c1fb…` | `9feac66ce1cc7b7f…` |
| `world_context.py` | `7a1533f0027007d9…` | `149abf2660bd8f2b…` |
| `router.yaml` | `0978502d9e8b7e69…` | `50d5f65145a3ebb3…` (planning_mode flipped shadow→live) |
| `planning.py` | (new) | `e74f7f7e9c59b7b1…` |
| `planning_capabilities.py` | (new) | `742b01c938f56a4c…` |
| `tests/test_planning.py` | (new) | — |
| `CURRENT_STATE.md` | — | updated (`.bak.s12.20260909-041202`) |

Backups: patch `.bak.20260909-035048` (config/gateway/world_context/router.yaml); world_context precedence-fix `.bak.s12fix.20260909-040645`; router.yaml go-live `.bak.golive12.20260909-041202`.

## Files changed (all additive)
- **NEW** `planning.py` — proposal-only planner: schemas (`PlanSnapshot`/`PlanStep`, no cross-turn lineage), `deterministic_template` (career follow-up), bounded no-tool LLM candidate path (`planning_agent_kwargs` `enabled_toolsets=[]`), **separate** `ground_candidate_graph` (resolve/map/attach/insert/canonicalize + dep-resolution) and `validate_plan` (verdicts + drops; no new steps), `run_planning`, fixture-only `run_replanning` (requires explicit `priorPlan`). Never raises; no writes/tools/execution.
- **NEW** `planning_capabilities.py` — non-authoritative `PLANNING_CAPABILITY_VIEW` (`ROUTER_PATH_SUPPORTED|KNOWN_UNAVAILABLE|NOT_DECLARED`; `policyCompatibility KNOWN_PROHIBITED|NO_KNOWN_STATIC_CONFLICT|NOT_EVALUATED`; `runtimeAvailability` always `UNKNOWN`).
- **EDIT** `world_context.py` (pure append Slice-12 block) — `detect_planning_intent` (explicit plan verbs; yields to draft/goal/pending; plan-only carve-out), `build_planning_subject` (single subject, no arbitration), `build_planning_input` (bounded, no `goalCandidates`, real subject evidence via `find_unresolved_followups`), `planning_trace`.
- **EDIT** `gateway_integration.py` — planning lane before the reasoning lane (deterministic template live; LLM path not wired live) + `_log_planning`.
- **EDIT** `config.py` + `router.yaml` — `planning_enabled`/`planning_mode`/`planning_max_steps` + `planning_is_active`/`planning_is_live` (reuse `cognitive_channels`).

## Pre-deploy validation (offline sandbox, local Python 3.13)
Deploy-exact patched tree (patch dry-run byte-identical to the hand-validated sandbox; VM `_patched` hashes matched local): **test_planning 40/40**, test_motivation 32/32, test_workspace 24/24, test_reasoning 18/18, test_goal_context 9/9. All `ast.parse` OK; anchors unique.

## Tests on VM (post-deploy, gateway venv Python 3.12 / system python3)
planning **40/40** · motivation **32/32** · workspace **24/24** · reasoning **18/18** · goal_context **9/9** · world_context **ALL PASSED** · classifier **18/18** · social_guard **34/34** · integration_failopen **14/14**.

## Deploy / restart
Patch applied as `lilith` (`ROUTER PATCH OK`, backups `.bak.20260909-035048`). Detector-precedence fix (acceptance B) installed via `fix12.py` (world_context.py → `149abf26…`, backup `.bak.s12fix.20260909-040645`). **Two** `hermes-gateway` restarts total (MainPID 233301 → 238423 → **239056**, active/running, health `/os/tasks`=200). **NO `daemon-reload`** (pre-existing benign unit drift). Go-live flag flip (`golive12.py` + `flip2.py`) read per-turn, **no restart**.

## Live acceptance (route-level against DEPLOYED code + REAL `/os` state; + live-lane harness)
| # | Scenario | Result |
|---|---|---|
| A | "What would we need to do to resolve application 14?" | OWNS; subject GOAL `g.2493fb35…` (career.followup); template; **USER_DECISION_REQUIRED** — 2 real duplicate unsent drafts → reconcile blocks the create step; VERIFICATION declared; **no third draft, no writes** |
| B | "Plan how to create a follow-up draft for application 17, but do not do it." | OWNS (plan-only carve-out); subject GOAL `g.95cee37…`; constraint captured; USER_DECISION_REQUIRED (app17 also has 2 unsent drafts); **no draft created** |
| B-live | live-lane harness `_route_turn_impl` | returns `{"mode":"planning","final_response": "…proposal only. Nothing has been created…"}`; **shadow → falls through (None)** |
| C | "Create a follow-up draft for application 17." | Planning **YIELDS** (bare draft action → existing 7.2 path) |
| D | unsupported capability (fixture) | `NO_VIABLE_PLAN` / `MISSING_CAPABILITY`; step `UNEXECUTABLE`; no invented capability |
| E | prohibited `mail.send_email` (fixture) | `NO_VIABLE_PLAN` / `BLOCKED_BY_POLICY`; `POLICY_COMPATIBILITY_STATUS=KNOWN_PROHIBITED_PRESENT`; **no ALLOW / no full Policy eval claim** |
| F | changed source state | fresh deterministic `PlanSnapshot` (same candidate+sources → identical `planSnapshotId`); reported as re-derivation, **not** cross-turn replanning |
| G | explicit `priorPlan` (fixture) | only here does `run_replanning` yield `REPLAN_PROPOSED` (preserve verified, invalidate downstream, no dup); no priorPlan → `NOT_REPLANNING_WITHOUT_PRIOR_PLAN` |

## Home / Telegram parity (route + lane level; NO transport)
Identical `PlanSnapshot` (`ps.4bd0a3c2…`) and identical `final_response` for `platform=telegram` vs `lilith_os`. **PARITY_OK**. Discord excluded (`planning_is_live(discord)=False`).

## Invariants proven
No goal/task/draft/belief writes (app14=2, app17=2 unchanged throughout); no tools/connectors (symbol-absence + `enabled_toolsets=[]`); no Policy ALLOW / no `POLICY_ELIGIBLE` / `runtimeAvailability=UNKNOWN`; VerificationRequirement `DECLARED_ONLY`; `ALREADY_SATISFIED` ≠ executed/verified; expected effect never satisfies its own precondition; grounder ≠ validator (validator adds no steps); no cross-turn lineage on live snapshot; no confidence floats / fake durations; no CoT; single PlanningSubject (no goal arbitration); Executive focus untouched; action precedence intact; fully fail-open.

## Final config
`planning_enabled: true`, `planning_mode: live`, `planning_max_steps: 6`, `cognitive_channels: [lilith_os, telegram]`.

## Rollback
`planning_mode: shadow` (stop returning plan answers) or `planning_enabled: false` (stop the lane) — **no restart**. Full revert: restore `.bak.20260909-035048` (config/gateway/world_context/router.yaml) + remove `planning.py`/`planning_capabilities.py`/`tests/test_planning.py` + one gateway restart. Ephemeral — no durable state to unwind.

## Remaining limitations (V1)
Deterministic-template-only live (LLM candidate path implemented + unit-tested, not wired live). Post-execution / partial-execution replanning is design + fixture-only (no executor on the Router path). No durable plan store / `/os/plans`. No task materialization. Capability view is a curated static subset (authoritative registry is the frontend RealCommandCore). No Ethics edge (L09 unbuilt; no verdict fabricated). No live full-conversation LLM turn exercised (route-level + lane-level harness used, per Slice-10/11 methodology).

**SLICE 13 (Ethical Deliberation): NOT STARTED.**
