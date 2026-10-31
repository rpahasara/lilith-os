# DEV exit: execution roadmap

Turns `DEV-TO-PROD-READINESS.md` (A1 to A39) into a dependency order. That checklist stays the source of truth: **nothing here waives an item.** Section 6 proposes revisions, for the owner to accept or refuse.

**As of 2026-10-31:** DEV runs e1, seven lanes in shadow, accepted by the owner for that scope only. **The state column in section 3 was written before e1: `MINIMUM-FOUNDATION.md` is current.** Current per-item state, classes and lane modes are in `MINIMUM-FOUNDATION.md`; stages and acceptance in `ROLLOUT-PLAN.md`; real-data concerns in `PROD-POPULATED-REVIEW.md`; later work in `ADVANCED-ROADMAP.md`. PROD facts date from the 2026-10-27 read-only audit. Capability by capability, see `PROD-PARITY-MATRIX.md`. For Phase 4, see `SNAPSHOT-REHEARSAL-DESIGN.md`.

## 1. The real constraint: PROD parity

Every lane is **live** in PROD's `router.yaml`, on the original detectors, with real data. The DEV stack runs them in shadow on empty stores. Three things follow.

- **Installing the DEV stack as it stands would silently replace live cognition with shadow lanes.** The reply path would keep working, while the lanes stop affecting it. That is the failure this roadmap exists to prevent.
- **The hardened detectors fire far less than PROD's.** That's the goal, but any Live lane on the new stack behaves differently from today, and this has never been measured with a model.
- **PROD has been idle since 2026-09-13.** Its last turn or decision is seven weeks old, Google OAuth has failed since 08-31 and WhatsApp since 09-12. There's no live traffic to protect during a window, and no recent proof that today's PROD works end to end.

**So the identity baseline must be captured before anything changes:** a fixed prompt set run on an isolated copy of PROD as it is. Without it, A8 can't be judged.

## 2. Dependency order

| Phase | Goal | Items | Kind | Depends on |
|---|---|---|---|---|
| **0** | Owner decisions | A4 (draft), A12, A15, A16, A18, A39, snapshot policy | **Owner** | none |
| **1** | Finish shadow on DEV | A5, A1 on a host | DEV op | p1, then e1 |
| **2** | Close the Core API gaps | A14, A15, A16, A19, A20, A21 on DEV | DEV op, Privacy approval | 0 |
| **3** | Prove behaviour | A3 model window, A34 live rollback | DEV op, budget approval | 1 |
| **4** | Rehearse | A2, A7, A8, A9, A10, A11, A29, A30, A31, A25, A26 | **Snapshot rehearsal** | 2, 3 |
| **5** | PROD foundations | A17, A22, A24, A28, A32, A33, A13 | PROD op | 4 |
| **6** | Cut over | A35, A36, A37, A38, A23 | PROD op | 5 |

Phases 1 and 2 can run in parallel. Keep them in separate windows, as the security stages restart Core API.

## 3. Every item

**Class:** **M** mandatory for a safe first migration; **C** mandatory only on the stated condition. **Next:** where the next piece of work happens.

| # | Item | Class | State now | Next | Next action |
|---|---|---|---|---|---|
| A1 | Cross-lane regression | M | **Source: 18/18, 7 lanes.** Host: 5 | DEV op | e1 window |
| A2 | Populated-store test | M | **Source: all lanes reached.** Host: none | Rehearsal | see section 7 |
| A3 | Model in the loop | M | not run | DEV op | see section 8 |
| A4 | Each lane's PROD mode | M | no decision | **Owner** | section 5 proposes a table |
| A5 | Planning, Ethics blockers | M | **Candidates built.** p1 sealed; Ethics #304 | DEV op | p1, then e1 |
| A6 | G3 title, negative control | C | open | see section 6 | |
| A7 | Capability inventory | M | partial | Offline, then rehearsal | list from recovered source; prove on the copy |
| A8 | Persona and identity | M | not run | Rehearsal | baseline on the unchanged copy first |
| A9 | Hermes reproducible | M | 175 of 176 | Offline | decide on the withheld checkpoint file; merge #272 to #275 |
| A10 | `app.py` gap | M | `519b309` to main not reviewed | Offline, then rehearsal | list schema and route changes |
| A11 | Canonical memory | M | not run | Rehearsal | digests before and after |
| A12 | L04, L18 states | M | no decision | **Owner** | |
| A13 | Owner-memory authority | C | DEV only | **Owner** | decide "stays off at first" or a design |
| A14 | FORGET reaches Core API | M | **Candidate, 18 tests.** Not wired | DEV op, Privacy | wire and drill |
| A15 | Data can't return | M | **Guard and restore gate on branches** | **Owner**, then DEV op | source decision |
| A16 | Retention per store | M | candidates; ages undecided | **Owner**, then DEV op | |
| A17 | FORGET on PROD | M | absent | PROD op | after 14 to 16 |
| A18 | No unaccepted identifiers | M | **`app_id` removed in p1.** `state.db` unread | DEV op, then rehearsal | read `state.db` on the copy |
| A19 | Write auth | M | #289 ready | DEV op | stages 1 to 5 |
| A20 | Read auth | M | **Implemented on a branch** | DEV op | see section 6 |
| A21 | Not reachable off-host | M | `0.0.0.0:8765` when reviewed | DEV op, then PROD op | bind, or accept in writing |
| A22 | Deployer least privilege | M | broad roles when reviewed | Offline, then PROD op | current review |
| A23 | Provider exposure per lane | M | not measured | Rehearsal | with A3's numbers |
| A24 | PROD budget, failure mode | M | none | Offline, then PROD op | design |
| A25 | No fallback surprise | M | not verified | Rehearsal | |
| A26 | Config separated | M | not scanned | Offline | CI scan |
| A27 | DEV tools refuse on PROD | M | partial | Offline | refusal tests |
| A28 | Separate credentials | M | not listed | Offline | inventory |
| A29 | Full rehearsal | M | not run | Rehearsal | |
| A30 | Row-level migration | M | not run | Rehearsal | 31, 93, 3, 11, 7, 10, re-read first |
| A31 | Timed rollback | M | not run | Rehearsal | |
| A32 | Off-host backups | M | none | **Owner**, then PROD op | needs the snapshot policy first |
| A33 | Backups respect FORGET | M | **Gate tested** | **Owner** | same policy |
| A34 | Rollback tested live | M | **Never on any release** | DEV op | see section 6 |
| A35 | Failed-cutover runbook | M | none | Offline | after the rehearsal |
| A36 | Criteria fixed first | M | none | Offline, owner signs | |
| A37 | Minimum acceptance set | M | none | PROD op | |
| A38 | Monitoring, rollback triggers | M | none | Offline | |
| A39 | OAuth, WhatsApp | M | no decision | **Owner** | repair, or an accepted loss |

### Can stay disabled or shadow-only, if the owner says so

Planning and Ethics may stay in shadow **only if A4 records it,** because both are live on PROD today. Off until after migration: Motivation drives in Workspace, model candidate paths, conversational goal creation, L04 expansion, Social cognition, memory consolidation, canonical LTM, per-caller credentials, and tuning on real traffic.

## 4. What can move now

| Offline now, no approval needed | |
|---|---|
| A7 | Capability inventory from recovered source |
| A9 | Recovery PR review |
| A10 | `519b309` to main: every schema and route change |
| A22, A28 | Written reviews from what's already known |
| A24, A36, A38, A35 | Drafts |
| A26, A27 | CI scan and refusal tests |
| Rehearsal runbook | Written and simulated before any snapshot is touched |

## 5. Proposed lane modes for the first migration (A4)

**Superseded by `MIGRATION-PLAN.md`:** preserve first, every lane live.

**Principle: no silent loss.** Every PROD-live lane is either kept live, or moved to shadow by a signed decision naming what's lost.

| Lane | PROD today | Proposed first-migration mode | Why |
|---|---|---|---|
| World Model | live | **live** | Grounding is the core reply path; its detector ran in shadow on DEV; needs A3 |
| Goals | live | **live, read paths only** | Goal creation stays refused until A14 to A16 |
| Reasoning | live | **live**, after A3 | Otherwise replies lose analysis on matching turns |
| Workspace | live | **live with Reasoning** | Reasoning uses it when live |
| Motivation | live | **shadow** | Drive quality has never been shown; loses a weak input, not a reply path |
| Planning | live | **shadow** | Live replaces the reply; never tested with a model on the new stack |
| Ethics | live | **shadow** | Same, and the third-party fix changes what it would say |

**Named loss if accepted:** Planning and Ethics stop answering directly on PROD. Given PROD's Ethics could never raise a third-party concern, the loss there is smaller than it looks.

**The alternative, a parity-first migration,** keeps PROD's own detectors live on the new infrastructure, then moves lanes one at a time. It's safer for identity but carries the over-matching forward, including casual messages reaching a provider. **Recommendation: the table above,** decided after A3 and the A8 baseline, because those two can overturn it.

## 6. Proposed checklist revisions, for owner review

**None of these is applied.** Each needs a yes.

| # | Proposal | Why | Risk |
|---|---|---|---|
| R-1 | A2 is met by source tests plus the rehearsal; no populated DEV window | A DEV window needs real writes and a verifier variant, and proves less than PROD-shaped data on the copy | none: the rehearsal is stricter |
| R-2 | A6 becomes conditional: required only if conversational goal creation stays on | With creation off at first, the title criterion can't apply | re-opens if creation is enabled |
| R-3 | A34 is met by one deliberate live return e1 to p1, then forward again, in its own window | Waiting for a real failure may never test it. It's the cheapest real rollback proof | one more restart; budget untouched |
| R-4 | **Withdrawn.** A20 may not follow cutover. Loopback can't be shown while the IAP tunnel is the route in, and the header work is needed anyway | see `MINIMUM-FOUNDATION.md` | none |
| R-5 | A13 is met by a signed "owner-memory authority stays off at first" | The item already allows it; this states the expected outcome | none |
| R-6 | Add A40: identity baseline on the **unchanged** copy before any migration step | A8 can't be judged without it, and the checklist doesn't say when it's taken | none |
| R-7 | Add A41: recent end-to-end proof of today's PROD reply path | PROD has been idle since 09-13. A failure found after cutover couldn't be attributed | none |
| R-8 | Add A42: snapshot retention policy, as its own item | A15, A32 and A33 all rest on it, and two preservation snapshots exist today with no decision | none |

**Refused as a revision:** dropping A29, or merging A14 with A17. Both look like time savers, and both remove the only proof that erasure works on real data.

## 7. Populated-store plan (A2)

| Level | What | Data | State |
|---|---|---|---|
| Source | all lanes on goals, a blocked goal, a task, a draft and a belief | synthetic | **done, 18/18** |
| Source, next | PROD's **shape**: 31 beliefs with evidence, 3 goals with 11 traces, 7 tasks, 10 drafts, conflicted and stale beliefs | synthetic generator, canary-tagged, no real text | offline, can start now |
| Rehearsal | the real rows on the isolated copy | real, never leaves the copy; provider off | Phase 4 |

**Pass:** selection, ranking, drives and plans change with the data; reads stay at or under 6; records stay private; only the expected tables change.

## 8. Model-in-the-loop plan (A3)

**Question:** what does each lane do to a real reply, compared with no lane?

| Parameter | Proposal |
|---|---|
| Data | synthetic, `TEST_ONLY`, canary-tagged, on DEV, never real goals |
| Requests | **10 at most**, a new owner-approved budget. Today's gate is 3 of 5 used, and this needs a reset the owner must approve |
| Shape | 5 fixed prompts, each with its lane off and on: grounded belief, goal focus, analysis, a false match, and a casual message |
| Measures | request and response size, whether the expected fact appears, whether a title or id leaks, persona markers, latency, tokens |
| Stop rules | the gate's hard budget; any forwarded request beyond the plan; any canary in a dump; any write |
| Order | after p1 and e1 |

**Not proven by it:** real wording, or long sessions. It gives a first number for A23.

## 9. Isolated snapshot rehearsal (Phase 4)

**Rules:** a new VM with no route to PROD, provider access off, credentials absent, destroyed afterwards under an approved procedure. The copy holds real data, so it needs its own Privacy decision.

1. Attach a copy of the 2026-10-27 snapshot. Re-read every count.
2. **Baseline:** run the identity prompts on the unchanged copy, with provider off and then, only if approved, with a bounded budget.
3. Migrate: Core API schema, Hermes, lanes.
4. Row-level digests, and the capability inventory.
5. Erase canaries, restore, replay, and show nothing returns.
6. Roll back, timed.
7. Record. **Any unexplained difference stops the plan.**

## 10. Recommended migration approach

**Superseded by `MIGRATION-PLAN.md`.**

**Rehearse, then one governed cutover.** PROD is idle, which removes the usual reason for a gradual move, and a long dual-running period adds risk without traffic to compare. But the first change on PROD should be backups, not code.

1. **DEV:** finish p1 and e1. Then security, FORGET, model window and rollback proof.
2. **Rehearsal:** on the copy, until it passes without surprises.
3. **PROD foundations, no cognition change:** snapshot schedule, least privilege, credentials, budget.
4. **Cutover:** one window. Lanes per the signed A4 table. FORGET, auth and acceptance checks in that window. Rollback is the snapshot taken minutes before.
5. **Monitor,** then move shadow lanes to Live one at a time, each a separate approval.

**Exit test for DEV:** when phases 1 to 3 are complete, DEV stops growing. New cognition work waits for the migration.
