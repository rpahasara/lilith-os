# Minimum safe PROD migration (PROPOSAL, nothing approved)

**This supersedes the lane table in `MINIMUM-FOUNDATION.md` and the "one governed cutover" in `EXECUTION-ROADMAP.md` section 10.** PROD was not accessed. Evidence: the read-only audit of 2026-10-27, recovered source, and source comparison.

## The recommendation: preserve first, then promote

**Cutover 1 changes what's around LILITH, not LILITH herself.** Every lane stays live on PROD's own code. Hardened lanes then arrive one at a time.

| | Cutover 1 | Afterwards, one lane per window |
|---|---|---|
| Persona, `USER.md`, `state.db`, all databases | **untouched** | untouched |
| `lilith_router`, Hermes, plugins, `config.yaml`, `router.yaml` | **untouched** | adapter added beside PROD's own |
| Live lanes | **all stay live, same code** | hardened detector, per lane, after a model test |
| Core API | `app.py` to main plus #289 and #306 | |
| New | off-host backups, credentials, restore proof | FORGET, then OAuth, each its own decision |

**Why this replaces my earlier table,** which proposed Motivation, Planning and Ethics in shadow:

- It meets the rule that live functionality is never downgraded. That table was a downgrade.
- The audit's rule 2 forbids deploying a DEV bundle over the router, Hermes or plugins: those are the only copies of several modules.
- The DEV stack has never run live with a model, and PROD's stack has, for weeks.
- DEV's adapter already wraps PROD's `world_context.py` byte for byte as `_prod_world_context.py`, so hardened lanes can be added later, without replacing it.

**The cost, stated plainly:** Cutover 1 brings **none** of the seven-lane work to PROD. PROD keeps its over-matching detectors and the Ethics suppression bug until promotion. PROD has been idle since 09-13, so that costs little in the meantime.

## PROD compatibility risks

| Area | What could break | Evidence | Handling |
|---|---|---|---|
| Identity, persona | Replacing `SOUL.md`, `USER.md`, `config.yaml` | Audit rank 2; only copies | Not touched. Hashes checked before and after |
| Canonical memory | L04 can't be enabled: no signer or witness on PROD | Audit rule 5 | `canonical_ltm_enabled` stays false; 3 L18 candidates kept |
| World Model, goals, tasks, drafts | Schema change, or a test writing to real data | 10 table definitions byte-identical; no `ALTER`; audit rule 3 | No migration needed. Never run tests on the installed tree |
| Conversation history | `state.db` lost or mangled | Audit rank 1, unread | Not touched; stays unread until a Privacy decision |
| **Live router writes** | **Enforced auth would refuse `POST /os/drafts` and `/os/goals`, and every read, from the router.** It sends no credential | PROD `world_context.py` lines 127, 139, 558 | **Fixed without touching the router:** `LILITH_OS_TRUST_LOOPBACK=1`, #306 |
| Core API start | A missing module crashes it: PROD's deploy copies only `app.py` | New import is stdlib `hmac` only. `fido2`, `rfc8785` and `lilith_memory` aren't used by `app.py` | Rehearsal starts it for real |
| **Unset settings** | Every protected route refuses | #289 | Drop-in first, code second |
| Command Center | Reaches PROD by IAP tunnel, so it's a remote caller. **Its `direct` mode can't send a credential** | `src/lib/api.ts` | Proxy mode only; tokens set on the Next server |
| IAP route | A loopback bind cuts it off | IAP forwards to the NIC address | Keep the bind; rely on credentials |
| Automations | Watchers write `lilith.db` directly, not over HTTP, so auth can't break them | `career_watcher.py` | None. They're broken by OAuth regardless |
| **OAuth repair** | Would ingest everything since 08-31 at once, including anything erased | extractor source | Not part of migration. Audit rule 7 |
| Provider configuration | `gpt-5.6-sol` by Codex OAuth, Groq social; **untested since 09-13** | Audit | Baseline proves it first |
| Keys | Regenerating 15B2a keys breaks verification | Audit rule 6 | Not touched |
| Single disk | Any mistake is unrecoverable | One 20 GB disk; one manual snapshot | First step |
| Empty DEV database | Would erase her | | **Never in any step.** `app.py` is the only file deployed |

## Must fix before cutover

| # | Item | Threatens | Evidence | Checklist |
|---|---|---|---|---|
| 1 | Fresh snapshot, schedule, one proven restore | Recoverability | single disk, no schedule | A32, A31 |
| 2 | Core API credentials on, with the router unaffected | Owner data: every accessor gets all data and a trusted turn | `519b309` has no owner check | A19, A20 |
| 3 | Re-read reachability, tag the firewall rule, narrow the deployer's tunnel | Owner data | the deployer can tunnel to all ports on PROD | A21, A22 |
| 4 | Today's reply path proven, before any change | Attribution of any failure | idle 7 weeks; proposed A41 | R-7 |
| 5 | Identity baseline, then comparison on the copy | Identity | A8 can't be judged without it | A8, A11 |
| 6 | Row-level comparison on the copy | Data integrity | | A30 |
| 7 | Rollback proven and timed | Recoverability | no rollback has run live | A31, A34, A35 |
| 8 | Capability inventory passed; acceptance criteria signed first | Functioning capabilities | | A7, A36 to A38 |
| 9 | One real file digest check that PROD is still `bb0a4139` | Compatibility | audit is days old | A10 |
| 10 | Owner decisions below | | | |

## Can wait until after cutover

| Item | Why it can wait | Checklist |
|---|---|---|
| Hardened detectors, Ethics fixes | Live lanes keep working | A5 for live, A23 |
| Full model evaluation, 10 requests | Nothing about cognition changes at Cutover 1. **Required before each lane's promotion** | A3 |
| Populated DEV window | Rehearsal is stricter | A2, R-1 |
| Seven lanes on PROD, multi-intent | New cognition | A1 on PROD |
| L04, owner-memory authority on PROD | Stays off, as today | A12, A13 |
| Motivation drives, goal creation changes, G3 | Unchanged behaviour | A6 |
| Per-caller tokens, removing `open-acknowledged`, SSH forwarding | Refinements | |
| CI scans, DEV refusal tests, monitoring tools beyond the checks here | Not demonstrated threats to this cutover | A26, A27 |
| Hermes tools on Telegram and Discord | Kept exactly as is, so no regression. **Still worth an owner decision later** | parity row |
| WhatsApp, OAuth, retention ages, `state.db` review | Separate owner tasks; audit rule 7 | A18, A39 |

**FORGET needs a decision, not a silent deferral.** The checklist calls A14 to A17 mandatory before promotion. Under preserve-first, cutover changes no data flow, adds no store, and removes no protection PROD has today: its Privacy V1 has never run. **Proposal R-13:** FORGET becomes mandatory before OAuth repair and before any new real-data capture, rather than before Cutover 1. The ingest guard ships inside #306 anyway. **Trade-off:** until then an erasure request on PROD can't be honoured across the Core API, which is already true today. If you refuse R-13, wiring it comes before step 8.

## Remaining DEV work

| Test | Size | Answers | Reuses | Approval |
|---|---|---|---|---|
| **Auth rollout on DEV** | one window: drop-in, merge #289 then #306, enforce | callers survive; settings survive deploy and rollback | #306 tests | DEV op, then **DEPLOY_REQUIRED merges** |
| **Core API rollback** | one return to the previous `app.py`, and forward | the rollback Cutover 1 would use | deploy scripts | same window |
| **Bounded model test** | **2 requests, no reset:** the budget has 2 left | a real reply still comes back with auth on | S6 method | DEV op |
| Populated store | **no new test:** source tests stand, then the copy | | seven-lane suite | none |
| Critical cross-lane | **no new test:** e1 accepted | | | none |

**Dropped, compared with earlier plans:** a 10-request window before cutover, an e1 to p1 return before cutover, and any further cognition release. The e1 return moves to the first lane promotion, where it matters.

## Sequence

| # | Step | Gate | Proves | Stop if |
|---|---|---|---|---|
| 1 | DEV validation above | owner, per window | auth and rollback work | any caller fails |
| 2 | Merge #289, #306 to main, DEV only | same | code on main; PROD unaffected: its workflow is dispatch-only | |
| 3 | PROD baseline: cloud preflight, fresh snapshot, file digests, one owner-sent turn | owner, read-only plus snapshot | PROD is what we think | any drift |
| 4 | Rehearsal, on a copy that's never booted, R0 to R9 | owner, Privacy | migration on real rows | unexplained difference |
| 5 | Compare identity, memory, database, capabilities | automatic, then owner judgment | nothing lost | |
| 6 | Rollback timed on the copy | automatic | | over the limit |
| 7 | Owner authorizes the live upgrade, with signed criteria | **owner** | | |
| 8 | Upgrade: snapshot, drop-in, dispatch `deploy.yml` at the exact SHA, set Next server tokens | owner window | | any trigger |
| 9 | Acceptance per `ROLLOUT-PLAN.md`; 48-hour return window | automatic, owner | | any trigger |
| 10 | Lane promotions, DEV-first | one approval each | | |

**The rollout runbook for step 8:**

1. Confirm no FORGET, no running deploy, and the snapshot READY.
2. Write the drop-in with `open-acknowledged`, daemon-reload. Don't restart yet.
3. Dispatch `deploy.yml`. It backs up `app.py`, installs, restarts, and rolls back on a failed health check.
4. Set `LILITH_OS_TRUST_LOOPBACK=1`, then write enforcement, then write `LILITH_OS_FOCUS_READ_ONLY=1`, with one restart.
5. Router turn: grounded. Stranger with no credential: refused.
6. Same for reads.

**Rollback:** at step 4 or 5, set `open-acknowledged` and restart. At step 3, the deploy's own backup. Beyond that, the snapshot. `app.py` at `519b309` ignores the new settings, so the drop-in is harmless after a return.

## Decisions needed from the owner

| Decision | Recommendation |
|---|---|
| Preserve-first, instead of the earlier lane table | **Yes** |
| R-13, FORGET's timing | Yes |
| `LILITH_OS_TRUST_LOOPBACK` | Yes: a token can't protect against the same user |
| Focus read-only on PROD | Yes: answers are identical and it stops audit writes during reads |
| Snapshot retention | Keep 2026-10-27's; schedule daily, 30 days |
| Rollback window | 48 hours |
| Rehearsal Privacy decision; whether R10 runs | Needed to judge replies |

Accepting this plan also accepts R-1, R-5, R-6, R-7 and R-8 **only if you say so.** Merging it accepts nothing.
