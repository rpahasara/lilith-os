# `dev-planning-hardening` overlay (CANDIDATE, in no release)

Fixes the five blockers in `proposals/planning-shadow-v0.1/DESIGN.md`. **Nothing assembles, installs or references this directory.** Planning stays off on DEV.

Two files: `lilith_router/world_context.py`, which is the w1 adapter plus the changes below, and `lilith_router/planning.py`, which is the deployed module with a counts-only trace.

## Blockers

| # | Before | After | Where |
|---|---|---|---|
| P-1 Over-match | any plan verb | also needs a named piece of work, no negation before the verb, and no quoted or reported speech | adapter |
| P-2 Read load | 14 to 15 reads in a turn | **at most 6**: each route once. Casual plans make 0 | adapter |
| P-3 Goal id | `trace.goal_ref` | `goal_ref_present` | `planning.py` |
| P-4 Application | `trace.subject_target`, `intent.app_id` | `subject_target_type`; `intent.app_id` is null | both |
| P-5 Stable id | `plan_snapshot_id`, same across sessions | `plan_snapshot_present` | `planning.py` |

**P-2:** the adapter keeps a successful read for 1.5 seconds, as parsed-fresh text in process memory, at most 32 paths. It is never written to disk, and failures are not kept. A repeat within a turn no longer reaches the Core API, which also means fewer focus reads.

**P-4:** the intent the gateway logs has no application number. The adapter holds it under a private key and restores it for the three read entries, so the plan still finds its target. `gateway_integration.py` is unchanged.

## Corpus

`tests/planning_corpus.py` was committed (`17b7b4a`) before any rule, and split by hash. The unseen half was scored once, after the rule was frozen. Same author and small, so treat these as better than real traffic will be.

| Unseen half | PROD rule | Candidate |
|---|---|---|
| Work plans matched, of 13 | 12 | **12** |
| Casual plans falsely matched, of 12 | 12 | **0** |
| Negated falsely matched, of 4 | 2 | **0** |
| Other lanes falsely matched, of 2 | 0 | **0** |

**Known misses:** `plan a follow-up for application 3 but do not send it` (unseen), and `plan the next steps on the recruiter`, which the PROD verb list does not cover (tuning half). A miss costs a shadow record.

## Privacy and retention

Records follow the decision log: 7-day retention and the FORGET purge of `logs/`. A plan is ephemeral, and nothing is written. Stored titles and bodies reach only the in-memory plan, never a record. The read memo holds Core API text for at most 1.5 seconds in the gateway process.

## Before a release

| Item | State |
|---|---|
| m1 accepted on DEV | not yet |
| Memo effect on Workspace and Motivation read counts | measured on m1: same records, 8 reads become 5 on a matching turn. A p1 window must pin those totals |
| Installer, verifier pins and simulation | not built |
| The `intent.app_id` choice for the Reasoning and Goal records | owner decision; unchanged here |
| Live mode, and the model candidate path | out of scope |

**Evidence:** `tests/test_planning_hardening.py`, 11/11, on the real gateway, adapter and Core API with the m1 router and counts-only `motivation.py`. It includes compatibility with the four m1 turns.
