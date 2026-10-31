# Minimum production-ready foundation

Classifies A1 to A39 from `DEV-TO-PROD-READINESS.md`, which stays the source of truth. **Nothing is waived:** "defer" appears only where the checklist already allows it, and each needs a signature. PROD facts date from the audit of 2026-10-27.

**As of 2026-10-31, later in the day:** p1 owner-accepted and #304 merged; e1 sealed, not installed. **0 of 39 are fully done: 11 are partial, 2 are proposed and awaiting signature, and 26 are open.**

## Classes

| Code | Meaning |
|---|---|
| **CUT** | Mandatory before the initial cutover |
| **LANE** | Mandatory before enabling a particular live lane |
| **DEFER** | Safe to defer behind an explicit disabled or shadow setting |
| **OWNER** | Needs an owner policy decision |
| **SNAP** | Needs the isolated snapshot rehearsal |
| **WIN** | Needs a live PROD maintenance window |

An item can have more than one. The first is what blocks it now.

## Items

| # | Item | Classes | Exact state | Blocker |
|---|---|---|---|---|
| A1 | Cross-lane regression | CUT | **PARTIAL.** Source 24/24, seven lanes; host six | e1 window |
| A2 | Populated-store test | CUT, SNAP | **PARTIAL.** Source only | rehearsal |
| A3 | Model in the loop | CUT, LANE | OPEN | budget approval |
| A4 | Lane modes | OWNER, CUT | OPEN; table proposed | signature, after A3 and A8 |
| A5 | Planning, Ethics blockers | CUT | **PARTIAL.** Planning shadow accepted; Ethics E-1 to E-5 fixed in source | e1 window |
| A6 | G3 title, negative control | LANE, DEFER | OPEN | only needed for goal creation, R-2 |
| A7 | Capability inventory | CUT, SNAP | PARTIAL: matrix | signed DISABLE rows, rehearsal |
| A8 | Persona and identity | CUT, SNAP | OPEN | baseline on the unchanged copy |
| A9 | Hermes reproducible | CUT | PARTIAL: 175 of 176 | withheld file, recovery PRs |
| A10 | `app.py` gap | CUT, SNAP | OPEN | `519b309` to main review |
| A11 | Canonical memory | CUT, SNAP | OPEN | rehearsal |
| A12 | L04, L18 states | OWNER | OPEN | decision |
| A13 | Owner-memory authority | OWNER, DEFER | OPEN | signed "off at first", R-5 |
| A14 | FORGET reaches Core API | CUT | PARTIAL: candidate, 33 tests | decisions, Privacy approval, DEV drill |
| A15 | Data can't return | OWNER, CUT | PARTIAL: **redelivery route now closed in the candidate** | decisions 1 to 3 of `ERASURE-ARCHITECTURE.md`; extractor patch |
| A16 | Retention per store | OWNER, CUT | PARTIAL: candidates | task ages |
| A17 | FORGET on PROD | CUT, WIN | OPEN | 14 to 16 |
| A18 | No unaccepted identifiers | CUT, SNAP | PARTIAL: `app_id` gone; `state.db` unread | read on the copy |
| A19 | Write auth | CUT | OPEN: code on #289 | stages in `AUTH-DEPLOYMENT-DESIGN.md` |
| A20 | Read auth | CUT | OPEN: code on #306 | **adapter header first** |
| A21 | Not reachable off-host | CUT, WIN | OPEN | port check approval, bind |
| A22 | Deployer least privilege | CUT, WIN | OPEN | current review |
| A23 | Provider exposure | CUT, SNAP | OPEN | needs A3 |
| A24 | PROD budget | CUT, WIN | OPEN | design |
| A25 | No fallback surprise | CUT, SNAP | OPEN | rehearsal |
| A26 | Config separated | CUT | OPEN | CI scan |
| A27 | DEV tools refuse on PROD | CUT | PARTIAL | refusal tests |
| A28 | Separate credentials | CUT | OPEN | inventory |
| A29 | Full rehearsal | CUT, SNAP | OPEN | prerequisites below |
| A30 | Row-level migration | CUT, SNAP | OPEN | rehearsal |
| A31 | Timed rollback | CUT, SNAP | OPEN | rehearsal |
| A32 | Off-host backups | OWNER, WIN, CUT | OPEN | snapshot policy |
| A33 | Backups respect FORGET | OWNER, CUT | PARTIAL: gate tested | snapshot policy |
| A34 | Rollback tested live | CUT | OPEN: **never run on any release** | a deliberate return, R-3 |
| A35 | Failed-cutover runbook | CUT | OPEN | after rehearsal |
| A36 | Criteria fixed first | OWNER, CUT | PROPOSED in `ROLLOUT-PLAN.md` | signature |
| A37 | Minimum acceptance | CUT, WIN | OPEN | cutover |
| A38 | Monitoring, triggers | CUT | PROPOSED in `ROLLOUT-PLAN.md` | signature |
| A39 | OAuth, WhatsApp | OWNER | OPEN | decision. **Repairing OAuth before message tombstones would re-deliver erased mail** |

## Safe to defer, and what stays off

Conversational goal creation, Motivation drives in Workspace, model paths for Planning and Ethics, L04 expansion, Social Cognition, Memory Consolidation lanes, per-caller credentials, removing `open-acknowledged`, and tuning on real traffic. Motivation, Planning and Ethics may run in shadow on PROD **only with the signed table below**, because all three are live there today.

## Proposed changes to the criteria

R-1 to R-8 from `EXECUTION-ROADMAP.md` section 6 stand, with these updates. **None is applied without a yes.**

| # | Change | Evidence | Trade-off |
|---|---|---|---|
| R-4 | **Withdrawn.** Don't let read auth follow cutover | The adapter sends no header, so the work can't be avoided | none |
| R-9 | New: A43, verifier treats a lane read that gets 401 as a failure | Otherwise enforcing auth silently removes grounding | one more release change |
| R-10 | New: A44, message tombstones wired before OAuth repair | Redelivery test | ties A39 to A15 |
| R-11 | A1 met on a host by e1 **plus** source tests for the rest | Seven lanes on one host is one window; a host can't reach every message class | a host pass stays narrow; the matrix says so |

## PROD lane modes, first migration

**Rule: no silent loss.** A shadow lane on PROD is a named, signed loss. Evidence levels are from `cross-lane-v0.1/COVERAGE-MATRIX.md`.

| Lane | PROD today | Proposed | Evidence for it | What could overturn it |
|---|---|---|---|---|
| World Model, Working Memory | live | **live** | HOST shadow; one synthetic belief live | A3, A8 |
| Goals, reads | live | **live** | Goals Live on one synthetic goal | focus flag on the populated copy |
| Goals, creation | live | **off** | no FORGET coverage until wired | A14 to A16 |
| Reasoning | live | **live, after A3** | HOST shadow, no model | A3: if it's worse, shadow, signed |
| Workspace | live | **live with Reasoning** | HOST shadow, `NO_CANDIDATE` only | same |
| Motivation | live | **shadow** | weak input, never shown useful | A3 |
| Planning | live, can replace the reply | **shadow** | Live never tested on this stack | A3 |
| Ethics | live, advisory | **shadow** | no host evidence yet | e1, A3 |
| Social Cognition, L18 | shadow | **unchanged, rows preserved** | no DEV release carries them | **must be proven not lost: DEV has no such lanes** |
| Legacy containment | live | **live** | unchanged | |

**Do not assume a DEV shadow equivalent can replace a PROD live lane.** They're different detectors. And `PROD-PARITY-MATRIX.md` remains the list of capabilities, including those with no lane at all.

## Identity and state preservation

**Never copy DEV's empty database over PROD's.** The migration keeps PROD's files and changes code around them. **What must survive:** `SOUL.md`, `USER.md`, `state.db`, World Model rows, goals, tasks, drafts, career history, L18 candidates, authority keys and working automations. Rows are compared by digest, per `SNAPSHOT-REHEARSAL-DESIGN.md`.

**Could regress, by name:** full Hermes tools on Telegram and Discord; Telegram cognition, as every DEV lane is `lilith_os` only; Social Cognition and L18 shadow; Planning and Ethics answering directly; fallback routing; goal creation; provider exposure on casual messages, which falls, and that's a behaviour change too; PROD's Privacy V1 config.
