# Planning shadow: readiness and design (PROPOSAL, nothing wired)

Slice 12 on DEV after m1. **Not ready for a release.** The defects below come from measurements on the real gateway, adapter and Core API. `test_planning_shadow_findings.py` pins each one, so a fix shows up as a test change.

`planning.py` (`e74f7f7e...`) and `planning_capabilities.py` (`742b01c9...`) are already in the DEV release, and `docs/architecture/slice-12/` holds the same bytes.

## How the lane behaves

| Property | Measured |
|---|---|
| Position | before Workspace and Reasoning, and it yields to draft, goal and pending paths |
| Provider | none in shadow: the candidate-model path is implemented but not wired |
| Writes | none on an empty store. With a goal present, the first focus read writes one `goal_trace` row, so the empty-store rule stays |
| Reply | unchanged in shadow; live mode would replace the reply |
| Records | `planning`, `routing`; no `workspace` or `reasoning` record on that turn |
| Dependencies | Workspace and Motivation for bounded context; drafts for follow-up evidence; Goals for focus |

## Blockers

| # | Finding | Effect | Proposed fix |
|---|---|---|---|
| P-1 | **Over-match:** `make a plan for dinner` is a planning turn | 14 Core API reads for a casual message | Harden `detect_planning_intent` in the adapter: a plan verb and a work subject |
| P-2 | **14 to 15 reads per turn**, 7 of them goal routes on a follow-up turn | Load, and repeated focus reads | Share one read set per turn, or cap the turn. The adapter already has a per-entry budget, but each entry gets a fresh one |
| P-3 | **Goal id in the record:** `trace.goal_ref` | Real goal ids in the decision log once goals exist | Log `goal_ref_present: true` |
| P-4 | **Target in the record:** `trace.subject_target`, `intent.app_id` | Links a record to one application | Log the target type only; review `app_id` with the Reasoning record, which already carries it |
| P-5 | **Stable identifier:** `plan_snapshot_id` is the same across turns and sessions for the same plan | Links turns, the reason ids were removed from Workspace | Drop it from the trace, as w1 did |

P-3 and P-5 sit in `planning.py`, so the fix replaces a code member, like the w1 `workspace.py`. P-1 and P-2 sit in the adapter.

## Proposed release, after m1 is accepted

| Member | Change |
|---|---|
| `home/router.yaml` | `planning_enabled: true`, `planning_mode: shadow` |
| `bin/verify_release.py` | Planning shadow; pins `planning.py` and `planning_capabilities.py` |
| `lilith_router/world_context.py` | hardened detector, bounded reads |
| `lilith_router/planning.py` | counts-only trace |

**Rollback:** the installer's revert to m1, restoring the adapter, `planning.py`, router and verifier. The verifier keeps the empty-goal-store rule.

**Privacy and FORGET:** no new store. Records follow the decision log's 7-day retention and FORGET purge. A plan is ephemeral, and proposals are never written.

## Not for this lane

Planning Live, the model candidate path, and any execution. Each needs its own design: live mode would replace a reply on a detector with no real-traffic evidence.
