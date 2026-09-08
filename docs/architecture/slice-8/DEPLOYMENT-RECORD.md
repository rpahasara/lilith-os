# Slice 8 — Goal / Executive System V1 · Deployment Record (PASS)

**Date:** 2026-09-08 · **Target:** `lilith-01` (backend only; frontend untouched).

## Baseline / hashes
- `app.py` before: sha256 `f44396c58e2f34dc9e1820ce69bebf217eb088ecf9ea3b5853c878843dd48d45` (post-Slice-7.1).
- `app.py` after Slice 8 append: sha256 `743a804aa7e3cbb8edf7ff8e3a698a74d4bc17cce2cfefe24c353b52c214d6e2`.
- Backups: `app.py.bak.20260908-100133`, DB snapshot `lilith.before-goals.db`, router `*.bak.20260908-100618`, `CURRENT_STATE.md.bak.<ts>`.

## Files changed (all additive)
| File | Change |
|---|---|
| `api/app.py` | Appended `# BEGIN/END SLICE 8` block (see `app.py.slice8-block.py`): `goal`+`goal_trace` tables, FSM, arbitration, controlled internal fns, 6 routes. |
| `~/.hermes/lilith_router/world_context.py` | Appended goal lane (`world_context.goal-block.py`): `detect_goal_intent`, `build_goal_grounding`, `GOAL_POLICY`, create/read helpers. |
| `~/.hermes/lilith_router/gateway_integration.py` | Goal lane in `_route_turn_impl` + `_log_goal` (via `patch_router.py`). |
| `~/.hermes/lilith_router/config.py` | `goals_enabled` / `goals_mode` + `goals_is_active` / `goals_is_live`. |
| `~/.hermes/lilith_router/router.yaml` | `goals_enabled: true`, `goals_mode: live` (rolled shadow→live). |
| `api/tests/test_goal_executive.py` | Backend suite (22 tests). |
| `~/.hermes/lilith_router/tests/test_goal_context.py` | Goal-lane detection/format (9 tests). |

## Contract
- **Reads:** `GET /os/goals`, `GET /os/goals/{id}`, `GET /os/goals/focus`.
- **Controlled writes:** `POST /os/goals` (create + USER_REQUESTED dedup + optional `evaluateBlock`), `POST /os/goals/{id}/transition` (activate/block/unblock/suspend/resume/complete/fail/cancel/reopen), `POST /os/goals/{id}/link_task`. Idempotent (`operationId`), revision-guarded (`expectedRevision`→409), FSM-validated (→409 illegal_transition). No generic setter.

## Lifecycle FSM
PENDING→ACTIVE|BLOCKED|CANCELLED · ACTIVE→BLOCKED|SUSPENDED|COMPLETED|FAILED|CANCELLED · BLOCKED→ACTIVE(unblock)|CANCELLED|FAILED · SUSPENDED→ACTIVE(resume)|CANCELLED · {COMPLETED,CANCELLED,FAILED}→PENDING (explicit `reopen`, traced). Completion evidence-gated.

## Arbitration (deterministic)
Candidates = ACTIVE|PENDING. Ordered rules: lifecycle > priority > deadline > source > recency > id. Focus is derived (recomputed from durable rows; reconstructed after restart); arbitration trace written when the winner changes.

## Tests
- Backend `test_goal_executive.py`: **22/22** (A–U + dedup reuse/reconciliation + completion evidence + idempotency/revision).
- Router `test_goal_context.py`: **9/9**. Regressions: classifier 18/18, social_guard 34/34, world_context all pass, frontend core **67/67**.

## Live acceptance (PASS)
- Home: "I want to follow up on application 14. Track that as a goal." → durable USER_REQUESTED `career.followup` goal `g.2493fb35…`, auto-**BLOCKED** on the two real unsent drafts `d.os2.14.a81a87acd64c2d46` + `d.os2.14.01caa11f61d6395d` (untouched; nothing sent).
- Grounded Q&A from durable state: focus, "what is blocked and why", "which goal has priority".
- States demonstrated: ACTIVE `g.95cee37…` (prepare app17, HIGH, task-linked), PENDING `g.5585f6c…` (app8), BLOCKED `g.2493fb3…` (app14); SUSPEND→RESUME moved focus g1→g2→g1; arbitration winner g1 (lifecycle rule).
- **Telegram route-level parity** proven (identical grounding; `goals_is_live(telegram)`=True).
- **Restart persistence** proven (lilith-os-api restarted; 3 goals + 11 traces persist; focus reconstructed).

## Deploy notes
Two restarts total (`lilith-os-api`, `hermes-gateway`); router.yaml flips are per-turn (no restart). **No `daemon-reload`** (pre-existing benign drift). WhatsApp session stays disconnected (out of scope).

## Rollback
`goals_enabled: false` (no restart) disables the lane; or restore `app.py.bak.20260908-100133` + router `*.bak.20260908-100618` + restart both services (goal tables inert).

## Remaining gaps
- Goals demonstrated for arbitration/suspend (`g1` app17, `g2` app8) were created during acceptance via the controlled API; they are real, reversible USER_REQUESTED goals and can be cancelled if undesired.
- No Goals UI (frontend intentionally untouched; acceptance authority is Home + Telegram).
- Parent/child cascade not implemented (V1 conservative; relationship stored + queryable only).

**Slice 9 (Reasoning extraction): NOT STARTED.**
