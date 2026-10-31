# Core API fail-closed auth: deployment design (PROPOSAL, activated nowhere)

Covers #289 and #306. **Nothing here is merged or deployed, and auth is active on neither host.** Each stage below is its own approved window.

## What the code does

| Setting | State | Effect |
|---|---|---|
| `LILITH_OS_WRITE_AUTH`, `LILITH_OS_READ_AUTH` unset, or any unknown value | **refused** | 503 on every protected route, before any database access |
| `open-acknowledged` | open, by a written choice | as today |
| `enforced` with a token under 32 characters | **refused** | 503 |
| `enforced` with a token | enforced | 401 on a missing or wrong credential, compared in constant time |

**What the setting doesn't cover:** `POST /os/conversation` always needs the credential, whatever the address, because a turn spends provider budget and nothing on the host calls it. An unconfigured server still refuses loopback. A forged forwarded header changes nothing. **It relies on nothing reverse-proxying to Core API on the host,** which the PROD baseline must confirm: anything that did would look local.

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
| **Enforcing auth breaks the on-host router** | **The Hermes adapter sends no credential, and on PROD it also posts drafts and goals.** Reads would get 401, and every lane fails open by design, so turns would still work, with nothing grounded and no error shown | `LILITH_OS_TRUST_LOOPBACK=1`: credentials are required from everything off the host, and the router stays unchanged |
| **Command Center breaks** | Its proxy routes send no read header | Same: header first |
| **PROD's Core API is far behind** | `519b309`, with no auth code | Auth reaches PROD only through the migration |
| **Unknown callers on PROD** | Automation scripts haven't been traced end to end | The rehearsal inventories them before enforcement |

## Callers

| Caller | Sends today | Needs |
|---|---|---|
| Hermes adapter `world_context.py`, including its `POST /os/drafts` and `/os/goals` | nothing, from loopback | **nothing changes.** Trusted by address when the setting is on. PROD's router is an only copy, and Hermes runs as the same user as Core API, so it can read the database directly: a token would protect nothing there |
| Command Center proxies under `src/app/api/lilith/` | **all 7 now send it from server-only variables, when set** (`core-api-credentials.ts`, on this branch) | tokens set at stage 1 |
| `src/lib/world/client.ts` and `src/lib/api.ts` | through the proxies | no secret in the browser: `test_caller_credentials.py` proves it from source. **`direct` mode can't send a credential, so it stops working under enforcement** |
| Deploy health check | `/health` | nothing |
| PROD automation | not traced | rehearsal |

## Stages

| Stage | Change | Pass needs | Rollback |
|---|---|---|---|
| **0** | Merge #289 and #306 with DEV's unit already carrying `open-acknowledged` for both, set **before** the deploy | DEV serves as before; `FOCUS_READ_ONLY` unset | revert the commit |
| **1** | Tokens created on the host, root-owned, 0600, never printed. Still `open-acknowledged` | Core API restarts clean | remove them |
| **2** | Command Center sends headers; `LILITH_OS_TRUST_LOOPBACK=1`. Still open | Command Center's header is seen present, by count only | unset |
| **3** | `WRITE_AUTH=enforced` | No caller gets 401 in a window; a wrong token does | env back to `open-acknowledged`, one restart |
| **4** | `READ_AUTH=enforced` | The router's reads stay 200, and **a turn is still grounded**, not only "still working" | same |
| **5** | `FOCUS_READ_ONLY=1` | No trace on a changed focus; same answer | unset |
| **6** | Narrow the route in, per `PROD-API-EXPOSURE.md`. **Not a loopback bind while the IAP tunnel is in use:** IAP forwards to the NIC address, so loopback would cut Command Center off | named accessors only; rule tagged per VM | previous firewall and IAM |
| **7** | Remove `open-acknowledged` from the code | After a settled period; optional for cutover | revert the commit |

**One switch per window, DEV first.** Rollback is a setting and one restart, so there's never a reason to loosen the code in a hurry. **A rollback may go only as far as `open-acknowledged`, never to unset:** unset refuses everything.

## Combined order with FORGET

Each step depends on the ones above it. **FORGET isn't complete until steps 5 to 9 are verified,** and only step 2's code exists on any branch in full.

| # | Step | Depends on | State |
|---|---|---|---|
| 1 | Owner decisions: source scope, snapshots, key location, FORGET authority | | open |
| 2 | Callers carry credentials: Command Center | | **done on #306, unmerged** |
| 3 | The on-host router keeps working: `LILITH_OS_TRUST_LOOPBACK` | | **done on #306, 9 tests, unmerged** |
| 4 | Stages 0 to 4 above: fail-closed writes, then reads | 2, 3 | designed |
| 5 | Focus read-only on populated goals, before any new code reads PROD goals | 4 | flag tested on #306 |
| 6 | Ingest guard and ledger configured, with no erasure yet | 1 | guard on #306 |
| 7 | World Model and Core API erasure wired into the executor | 1, 6, Privacy approval | candidate on #296 |
| 8 | Persistent message tombstones in the extractor, before OAuth repair | 7 | candidate on #296; extractor unpatched |
| 9 | Backup and snapshot policy, and the restore gate in the procedure | 1, 7 | gate tested, policy open |
| 10 | DEV drill: canaries, every route, restore, replay, bytes checked | 2 to 9 | not run |

## PROD

PROD takes stages 0 to 6 inside the migration, on the rehearsal first. Exposure as recorded is in `PROD-API-EXPOSURE.md`: **not public on the last read, but every accessor gets an unauthenticated trusted-operator turn.**

## Tests that exist

`test_populated_reads.py` on a PROD-shaped synthetic store: no route answers without configuration except `/health`, none answers a stranger, the docs are covered, and only the owner's conversation relays. 380 Core API tests in both env modes.

## Tests still needed

- Grounding after enforcement, by a real turn: stage 4's pass above.
- No token in a built browser bundle. Source is tested; a scan of the build output isn't.
- A pre-start check that refuses to start Core API with neither variable set.

## Decisions needed from the owner

| # | Decision | Recommendation |
|---|---|---|
| 1 | One token per class, or per caller? | Per class at first: one principal |
| 2 | May stage 7 follow cutover? | Yes |
| 3 | Does R-4, read auth up to 30 days after cutover if loopback is proven, stand? | **Withdraw it.** Loopback can't be proven while the tunnel is the route, and the header work has to happen anyway |
| 4 | Keep the IAP tunnel to 8765, or move to SSH forwarding over IAP and close it? | Decide from `PROD-API-EXPOSURE.md` |

## What's needed from #296 for the first migration

| Part | Needed for Cutover 1? |
|---|---|
| `write-auth-stage1.conf` and its test | **Yes:** the drop-in pattern for setting values before the code |
| `SECURITY-PLAN.md` | Superseded by this design where they differ |
| `core_erasure.py`, `goal_erasure.py`, restore gate, tombstones | **Not for Cutover 1 under R-13.** Needed before OAuth repair and new real-data capture |
| `ERASURE-ARCHITECTURE.md`, `PROD-DATA-MIGRATION.md` | Reference for the FORGET decisions |
| `COGNITION-DEPENDENCIES.md`, `METADATA-AND-RUNTIME-REVIEW.md` | Lane promotions, later |
