# Slice 10 — Global Workspace / Attention V1 · Deployment Record (PASS)

**Date:** 2026-09-08 · **Target:** `lilith-01` backend router only. **No** `app.py` / DB / frontend / `run.py` change.

## Starting → post hashes (sha256; backups `.bak.20260908-155803`)
| File | pre | post |
|---|---|---|
| `lilith_router/config.py` | `0572d9add5b3489c…` | `ce2098b3c2428789…` |
| `lilith_router/gateway_integration.py` | `92c01c49252ef2be…` | `c9c028f8b17e90d2…` |
| `lilith_router/world_context.py` | `1a6724daff49916d…` | `0c1dc9434e4588b3…` |
| `lilith_router/router.yaml` | `55a6b39e9d5451b7…` | (appended; then `workspace_mode` flipped shadow→live) |
| `lilith_router/workspace.py` | (new) | `ba7513a8e24a9c57…` |
| `lilith_router/tests/test_workspace.py` | (new) | — |
| `lilith_router/CURRENT_STATE.md` | — | updated (backup `.bak.20260908-162313`) |

## Files changed (all additive)
- **NEW** `workspace.py` — `AttentionCandidate`/`WorkspaceSnapshot` contracts, ordered `SALIENCE_CLASSES`, `classify_salience`, `normalize_candidate`, `deduplicate_candidates` (exact-key + goal↔draft blocker collapse), `rank_candidates`, `build_workspace_snapshot` (1 primary + ≤4 secondary + suppressed/deferred), `build_trace`. Pure stdlib; never raises.
- **EDIT** `world_context.py` (append Slice-10 block) — `detect_attention_override` (USER_REFERENCED vs ATTENTION_OVERRIDE, deterministic), `build_attention_candidates` (READ-ONLY extraction from Goal/Draft/Task/World), `build_reasoning_input_bounded` (Refinement C: bounded support expansion around SELECTED refs), `select_reasoning_input` (bounded when live+primary, else fail-open to existing `build_reasoning_input`).
- **EDIT** `gateway_integration.py` — workspace build + `select_reasoning_input` inside the existing Slice 9 reasoning lane + `_log_workspace` (lane `"workspace"`). Slices 7.2/8 lanes untouched.
- **EDIT** `config.py` + `router.yaml` — `workspace_enabled` / `workspace_mode` / `workspace_capacity` + `workspace_is_active` / `workspace_is_live`; channels reuse `cognitive_channels`.

## Pre-deploy validation (offline sandbox, local Python 3.13)
Real VM `world_context.py` + Slice-10 block + `workspace.py` + tests: **test_workspace 24/24**, **test_reasoning 18/18**. Patch transforms dry-run (anchors unique, all `ast.parse` OK, "ROUTER PATCH OK").

## Tests (on VM, post-deploy)
workspace **24/24** · reasoning **18/18** · goal_context **9/9** · classifier **18/18** · social_guard **34/34** · world_context **all**. Frontend: **untouched** (no frontend change; core suite not runnable in this checkout — no runner/tests present; `git status` shows zero frontend delta).

## Refinements verified
- **A** USER_TURN never auto-consumes a slot (no USER_TURN candidate emitted).
- **B** USER_REFERENCED (entity named) vs ATTENTION_OVERRIDE ("forget…/…instead") distinguished deterministically; override → class `USER_OVERRIDE_TARGET`.
- **C** live snapshot is the REAL ReasoningInput boundary — reasoning trace `correlation_id == w.*` (workspace snapshot id), proving the bounded builder ran; unrelated unselected rows excluded, linked support retained; failure/shadow/no-primary → exact Slice 9 builder.
- **D** no cross-turn novelty; `recentlyChanged` derived only from source timestamps.

## Live acceptance (PASS, Home `/os/conversation`, `workspace_mode: live`; lanes from decisions.log)
| Scenario | Result |
|---|---|
| 1 "why can't you follow up on app 14" | primary `USER_REFERENCED_BLOCKER`; reasoning bounded (corr `w.1e996b599e15850b`); **Executive focus app17 unchanged** |
| 2 "forget app 17 for now, focus on app 14 instead" | primary `USER_OVERRIDE_TARGET`; answer confirms durable focus still app17 |
| 3 "what is uncertain about app 14" | facts vs explicit unknowns; blocker elevated; no fabrication |
| 4 "what could we do next for app 14" | `OPTION_GENERATION`; proposals only; no execution |
| 5 "create a follow-up draft for app 17, do not send it" | lane `cognitive` (Slice 7.3); **workspace NOT engaged**; no 3rd draft; nothing sent (app17 created-drafts 3→3) |

Executive focus before/after all attention turns: `g.95cee3719e3c4a4f9705486b479cb8af` (app17) — **never mutated**.

## Telegram parity (route level; NO transport)
`workspace_is_live` True for both `lilith_os` and `telegram`; identical selection core for the same message + durable state: primary `USER_REFERENCED_BLOCKER` `blocker:g.2493fb35…`, identical secondary refs (`g.2493fb35…`, `d.os2.14.01caa11f61d6395d`, `d.os2.14.a81a87acd64c2d46`, `g.95cee37…`), identical capacity `{1,4}` — `PARITY_OK: True`. No real Telegram message sent.

## Deploy / rollback
One gateway restart (`hermes-gateway` MainPID 228972, NRestarts=0); flags flip per-turn (no restart); **NO `daemon-reload`** (pre-existing benign unit drift). Rollback: `workspace_enabled: false` (no restart) → exact pre-Slice-10 Slice 9 path; or restore `.bak.20260908-155803` (config/gateway/world_context/router.yaml) + one gateway restart. Workspace is ephemeral — no durable state to unwind.

## Known gaps / notes
- SYSTEM_CRITICAL / BACKGROUND_MAINT classes are defined but **synthetic/test-only** — no background health/connector producer wired (Decision 5).
- Workspace consumes the **reasoning lane only**; Slice 7.2 cognitive and Slice 8 goal lanes are unchanged (Decision 3). Goal-query framings (e.g. literal "why is app 14 blocked?") route to the Slice 8 goal lane and correctly do not engage the workspace.

**SLICE 11 (Motivation/Homeostasis): NOT STARTED.**
