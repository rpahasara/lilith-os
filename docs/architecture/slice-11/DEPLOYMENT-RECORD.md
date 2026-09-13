# Slice 11 — Motivation / Homeostasis V1 · Deployment Record (PASS)

**Date:** 2026-09-08 · **Target:** `lilith-01` backend router only. **No** `app.py` / DB / `run.py` / frontend / Presence / OAuth / connector / Policy change.

## Starting → post hashes (sha256; backups `.bak.20260908-204811`)
| File | pre | post |
|---|---|---|
| `lilith_router/config.py` | `ce2098b3c2428789…` | `76c4604d06ee0499…` |
| `lilith_router/gateway_integration.py` | `c9c028f8b17e90d2…` | `9c667eef0699c1fb…` |
| `lilith_router/world_context.py` | `0c1dc9434e4588b3…` | `7a1533f0027007d9…` |
| `lilith_router/workspace.py` | `ba7513a8e24a9c57…` | `e209440f55c40f3d…` |
| `lilith_router/router.yaml` | `95a54d1bd851c88b…` | `93be0911a5109fe9…` (then `motivation_mode` flipped shadow→live) |
| `lilith_router/motivation.py` | (new) | `f95d4f56cc67d786…` |
| `lilith_router/tests/test_motivation.py` | (new) | — |
| `lilith_router/CURRENT_STATE.md` | — | updated (backup `.bak.20260908-210325`) |

## Files changed (all additive)
- **NEW** `motivation.py` — pure-stdlib ordinal drive core: `DriveSignal`/`MotivationSnapshot`, `classify_coherence`, `classify_goal_completion`, `classify_safety_synthetic`, `build_snapshot` (dedup vs raw refs → `candidateEligible`), `to_attention_candidates`, `bounded_summary`, `build_trace`. Never raises; no network; no floats; no transition claims; no affect keys.
- **EDIT** `world_context.py` (pure append Slice-11 block) — `build_motivation_snapshot` (scoped to ws_cands + user-ref + Executive focus; NO global scan), `motivation_candidates`, `motivation_trace`, `select_reasoning_input_m` (wraps Slice-10 builder, attaches Workspace-bounded `motivationSummary`).
- **EDIT** `workspace.py` — `MOTIVATION_PRESSURE` salience class (rank 11, below every user/blocker/focus/approval/conflict/task-failure class); one `classify_salience` rule; carry `motivationDrive`/`motivationIntensity`; intensity within-class tiebreak.
- **EDIT** `gateway_integration.py` — motivation lane inside the existing reasoning/workspace block (build+log; live merge of eligible candidates; `select_reasoning_input_m`) + `_log_motivation` (lane `"motivation"`).
- **EDIT** `config.py` + `router.yaml` — `motivation_enabled` / `motivation_mode` + `motivation_is_active` / `motivation_is_live`; channels reuse `cognitive_channels`.

## Pre-deploy validation (offline sandbox, local Python 3.13)
Exact patched deploy content: **test_motivation 32/32**, **test_workspace 24/24**, **test_reasoning 18/18**, **test_goal_context 9/9**. Patch dry-run (anchors unique, all `ast.parse` OK).

## Tests (on VM, gateway venv Python 3.12, post-deploy)
motivation **32/32** · workspace **24/24** · reasoning **18/18** · goal_context **9/9** · world_context **ALL PASSED** · classifier **18/18** · social_guard **34/34** · integration_failopen **14/14**.

## Deploy / restart
Patch applied as `lilith` (`ROUTER PATCH OK`). One gateway restart (`hermes-gateway` MainPID 228972 → **233301**, active/running, health OK). **NO `daemon-reload`** (pre-existing benign unit drift). Flags read per-turn; shadow→live flip needed no restart.

## Live acceptance (Home `/os/conversation`, `motivation_mode` shadow then live)
| # | Scenario | Result |
|---|---|---|
| shadow | "what is uncertain about app 14…" | motivation lane logged: COHERENCE=SATISFIED, GOAL_COMPLETION=SIGNIFICANT (`GOAL_USER_REQUESTED_BLOCKED`, `g.2493fb35`), both `candidateEligible=false`; workspace `arbitration_rules_applied` 12→**13** (MOTIVATION_PRESSURE present); primary `USER_REFERENCED_BLOCKER` |
| 1/3 | app14 drive from real state; focus unchanged | GOAL_COMPLETION derived only from the real BLOCKED/USER_REQUESTED goal; answer states "application 17 remains the current executive focus"; `/os/goals/focus` = `g.95cee37` before **and** after |
| 2 | "why does app 14 keep surfacing?" | functional, source-backed ("open lifecycle + no progress + no resolution … unattended item"); **no emotional wording** |
| 5 | dedup / no extra slot | live workspace `candidate_count` 9, `source_type_counts` GOAL:3/DRAFT:2 — **no MOTIVATION_DRIVE merged** (`mot_candidates_merged=0`); goal already a raw candidate → `candidateEligible=false` |
| 7 | action stays on controlled path | app14 `created` drafts 2→2 (`d.os2.14.01caa11f61d6395d`, `…a81a87acd64c2d46`); no writes |
| 4 / 6 | override > pressure; bounded summary | Motivation emits no competing candidate for real app14 turns (deduped), so these are covered by unit tests (`test_user_override_outranks_motivation`, `bounded_summary` T-SUMSEL/T-BYPASS); CRITICAL-cap verified on real data (`blockedBy` = drafts, not a failed task → SIGNIFICANT) |

## Telegram parity (route level; NO transport)
`build_attention_candidates` + `build_motivation_snapshot` + workspace snapshot for the same message, `platform=telegram` vs `lilith_os`: identical drives (COHERENCE SATISFIED, GOAL_COMPLETION SIGNIFICANT `GOAL_USER_REQUESTED_BLOCKED`), identical `candidateEligible=false`, identical `n_cands=9`, identical `ws_primary_class=USER_REFERENCED_BLOCKER`, `mot_candidates_merged=0` — **PARITY_OK: True**. No real Telegram message sent.

## Invariants proven
Executive focus never mutated (`g.95cee37`); no goal/task/draft/belief writes; no tools/connectors; ordinal only (no floats); no ReasoningResult consumed; no global scan (scoped to ws_cands + user-ref + focus); dedup prevents duplicate slot; no affect/emotion output; fail-open (motivation error → Slice-10/9 path unchanged).

## Rollback
`motivation_mode: shadow` (stop merging) or `motivation_enabled: false` (stop the lane) — **no restart**. Full revert: restore `.bak.20260908-204811` (config/gateway/world_context/workspace/router.yaml) + `rm motivation.py tests/test_motivation.py` + one gateway restart. Motivation is ephemeral — no durable state to unwind.

## Known notes
- Trace `sourceAvailability.drafts=false` is cosmetic: drafts are **not** a V1 motivation source (COHERENCE uses beliefs; GOAL_COMPLETION uses goals+tasks), so the field is never set true. Not an error; `partial=false`.
- In realistic scoped turns a drive's source is already a raw Workspace candidate, so `candidateEligible=false` and Motivation contributes **zero** Workspace slots — its V1 effect is the regulatory trace + Workspace-bounded `motivationSummary` for Reasoning. The MOTIVATION_DRIVE candidate path is exercised by unit tests and rare edge cases.

**SLICE 12 (Planning/Replanning): NOT STARTED.**
