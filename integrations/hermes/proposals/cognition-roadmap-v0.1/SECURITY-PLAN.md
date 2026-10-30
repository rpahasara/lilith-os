# Write authentication: staged plan for Goals, Tasks and Drafts (PROPOSAL, nothing deployed)

Replaces section 1 of [`../goals-privacy-v0.2/PLAN.md`](../goals-privacy-v0.2/PLAN.md) where they differ.

## Status

PR #289 is reworked to this design (`LILITH_OS_WRITE_AUTH`, `LILITH_OS_WRITE_TOKEN`, header `X-LILITH-OS-Write`), with tests. Not merged or deployed.

**Merging it without stage 1 would stop every Core API write on DEV and PROD,** because unset now refuses. That is deliberate, and it is why the
setting has to be in place first. It also deploys: `DEPLOY_REQUIRED`.

## Target rule

One explicit setting, `LILITH_OS_WRITE_AUTH`, read at start:

| Value | Behaviour |
|---|---|
| unset or unknown | **writes refused with 503**, reads work |
| `enforced` | a token of 32+ characters is required, or writes return 503; the right header is needed on every write route |
| `open-acknowledged` | writes open, logged at start. Temporary, for migration only, and refused when `LILITH_ENV=prod` after stage 4 |

`/health` reports `writeAuth` as `enforced`, `open-acknowledged` or `refused`, with no secret, so preflights can see the state.

**Routes covered:** `POST /os/goals`, `POST /os/goals/{id}/transition`, `POST /os/goals/{id}/link_task`, `POST /os/tasks`,
`PATCH /os/tasks/{id}`, `POST /os/drafts`, `DELETE /os/drafts/{id}`, through one dependency, with a test that fails if a new write route
lacks it. `/os/conversation` keeps its existing fail-closed owner check.

## Stages

Each is a separate approval. Every stage that changes `app.py` is `DEPLOY_REQUIRED`: merging it restarts Core API and invalidates
packages pinning `a9fc562f…` or PID 304463. **Run each with no gate open, after G3 and the `drafts` gate.**

| Stage | Change | State after | Proof |
|---|---|---|---|
| 1 | Drop-in outside the unit, which the bootstrap does not rewrite, holding `LILITH_OS_WRITE_AUTH=open-acknowledged`, on DEV and PROD, and a preflight for it | No code change | Bootstrap re-run keeps it |
| 2 | Merge #289 after stage 1 is verified on both hosts | Same behaviour, now explicit; `/health` shows `writeAuth` | `/health` reads `open-acknowledged`; unset refuses, in tests |
| 3 | Callers send the header: PROD `_post_goal_json`, task and draft writers, and the Command Center path | Harmless while open | Caller tests |
| 4 | DEV to `enforced` | **Protected on DEV** | No header 401, wrong 401, right 200, on every route |
| 5 | PROD to `enforced` in its own approved window | **Protected on PROD** | Same probe |
| 6 | Remove `open-acknowledged`. Review binding Core API to `127.0.0.1` | No open mode exists | |

**Rollback:** set `open-acknowledged` and restart. Never by unsetting, which refuses writes.

## Proving it without writing

Refusal happens before any DB access. So a preflight POST with no header is a safe probe on a protected service: 401 or 503 means
protected. **A 200 would mean it wrote,** so the probe sends a body that fails validation, where an unprotected route returns 400.

## Other open items

| Item | State |
|---|---|
| `GET /os/goals/focus` writes a trace | Authentication cannot cover it. Move the trace to the first read after a change in a write path, or accept it |
| Core API on `0.0.0.0:8765` | Reachable off-host through IAP. Stage 6 |
| Shared single token | Acceptable for one principal. Per-caller credentials are a later step |
| DB mode 0644 | Plan in `goals-privacy-v0.2`, not done |

## Goal data before any real goal

**Code candidate:** [`../goal-forget-v0.1/goal_erasure.py`](../goal-forget-v0.1/goal_erasure.py), not wired. Its tests run on the real schema: a canary is
gone from the file bytes after erasure, no activity counter remains, a re-run is harmless, an unknown table or held lock refuses
with nothing changed, and retention removes only old terminal goals.

**Still needed:** owner decisions 1 to 8 in `goals-privacy-v0.2/PLAN.md`; wiring into the FORGET executor, which is a Privacy change needing
its own approval; hold handling; backup rules; and a DEV drill.
