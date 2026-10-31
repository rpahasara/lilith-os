# Core API fail-closed auth: deployment design (PROPOSAL, activated nowhere)

Covers #289 and #306. **Nothing here is merged or deployed, and auth is active on neither host.** Each stage below is its own approved window.

## What the code does

| Setting | State | Effect |
|---|---|---|
| `LILITH_OS_WRITE_AUTH`, `LILITH_OS_READ_AUTH` unset, or any unknown value | **refused** | 503 on every protected route, before any database access |
| `open-acknowledged` | open, by a written choice | as today |
| `enforced` with a token under 32 characters | **refused** | 503 |
| `enforced` with a token | enforced | 401 on a missing or wrong credential, compared in constant time |

**Deny by default:** every GET needs the read credential unless it's listed in `_PUBLIC_READS`, which holds only `/health`. A new route can't be left open by forgetting it. The docs routes are covered too.

| Routes | Credential |
|---|---|
| Goals, Tasks, Drafts writes (8 checks) | write |
| Goals, Tasks, Drafts, World Model, Career, Memory, Meetings, Audit, System reads | read |
| `GET /os/goals/focus` | read, plus `LILITH_OS_FOCUS_READ_ONLY=1` to stop its trace write |
| `POST /os/conversation` | read, **new in #306:** it had no owner check at all |
| `/health` | none |

## The hazards this ordering exists for

| Hazard | Why | Control |
|---|---|---|
| **Deploying the code breaks every route** | Unset means refused, and neither host sets the variables | Environment first, code second, and a pre-start check |
| **Enforcing reads silently removes grounding** | **The Hermes adapter sends no credential.** Its reads would get 401, and every lane fails open by design, so turns would still work, with nothing grounded and no error shown | The adapter's new header ships in a release before enforcement, and a check proves it |
| **Command Center breaks** | Its proxy routes send no read header | Same: header first |
| **PROD's Core API is far behind** | `519b309`, with no auth code | Auth reaches PROD only through the migration |
| **Unknown callers on PROD** | Automation scripts haven't been traced end to end | The rehearsal inventories them before enforcement |

## Callers

| Caller | Sends today | Needs |
|---|---|---|
| Hermes adapter `world_context.py` | nothing | read header, from a root-owned env; a **new release** with a new pin |
| Command Center proxies under `src/app/api/lilith/` | write header on some | read header on all, server-side only |
| `src/lib/world/client.ts` and `src/lib/api.ts` | through the proxies | no secret in the browser: **a test must prove it** |
| Deploy health check | `/health` | nothing |
| PROD automation | not traced | rehearsal |

## Stages

| Stage | Change | Pass needs | Rollback |
|---|---|---|---|
| **0** | Merge #289 and #306 with DEV's unit already carrying `open-acknowledged` for both, set **before** the deploy | DEV serves as before; `FOCUS_READ_ONLY` unset | revert the commit |
| **1** | Tokens created on the host, root-owned, 0600, never printed. Still `open-acknowledged` | Core API restarts clean | remove them |
| **2** | Callers send headers: a new Hermes release, and Command Center. Still open | Every caller's header is seen present, by count only | previous release |
| **3** | `WRITE_AUTH=enforced` | No caller gets 401 in a window; a wrong token does | env back to `open-acknowledged`, one restart |
| **4** | `READ_AUTH=enforced` | The adapter's reads stay 200, and **a turn is still grounded**, not only "still working" | same |
| **5** | `FOCUS_READ_ONLY=1` | No trace on a changed focus; same answer | unset |
| **6** | Bind to `127.0.0.1`, A21 | `ss` shows loopback only; nothing off-host connects | previous unit |
| **7** | Remove `open-acknowledged` from the code | After a settled period; optional for cutover | revert the commit |

**One switch per window, DEV first.** Rollback is a setting and one restart, so there's never a reason to loosen the code in a hurry. **A rollback may go only as far as `open-acknowledged`, never to unset:** unset refuses everything.

## PROD

PROD takes stages 0 to 6 inside the migration, on the rehearsal first. Stage 6 matters most there: the recovered unit binds `0.0.0.0:8765`, and whether a firewall covers it is unconfirmed. **Confirming that port from outside needs a read-only approval of its own, and it decides how urgent this is:** until #306 reaches PROD, an open port there would relay a stranger's conversation.

## Tests that exist

`test_populated_reads.py` on a PROD-shaped synthetic store: no route answers without configuration except `/health`, none answers a stranger, the docs are covered, and only the owner's conversation relays. 380 Core API tests in both env modes.

## Tests still needed

- The adapter sending the header, and a 401 being visible rather than silent. **A lane failing open on 401 should count as a failure in the verifier, not a quiet empty read.**
- No token in any browser bundle.
- A pre-start check that refuses to start Core API with neither variable set.

## Decisions needed from the owner

| # | Decision | Recommendation |
|---|---|---|
| 1 | One token per class, or per caller? | Per class at first: one principal |
| 2 | May stage 7 follow cutover? | Yes |
| 3 | Does R-4, read auth up to 30 days after cutover if loopback is proven, stand? | **Withdraw it.** The adapter finding means the header work has to happen anyway |
