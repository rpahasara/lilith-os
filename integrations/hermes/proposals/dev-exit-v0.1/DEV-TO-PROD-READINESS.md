# DEV-to-PROD readiness checklist

**Status: DEV is not ready for production promotion.** Shadow tests on every lane would not change that. They prove plumbing on empty stores with no model behind them.

**The first fact to hold on to:** PROD is not behind DEV in a simple way. PROD runs an older stack with its cognition lanes **live**, on the original detectors, and with real data. DEV runs newer, hardened code in shadow on synthetic data. Promotion is a migration, not an upgrade, and it can lose capability as easily as gain it.

PROD facts below come from the read-only audit of 2026-10-27, and are that old. Status values: **OPEN**, **PARTIAL** or **DONE**.

## A. Mandatory before production promotion

### Cognition compatibility

| # | Requirement | Evidence required | Status |
|---|---|---|---|
| A1 | Cross-lane regression across all lanes together, with detector ownership decided per message class | One suite on one assembled home, including Ethics and Reasoning overlap | OPEN |
| A2 | A populated-store test of every lane, on a synthetic copy of PROD's shape | Selection, ranking, drives and plans exercised with non-empty data | OPEN: every DEV window ran on empty stores |
| A3 | A model-in-the-loop test: what each lane does to a real reply | Bounded, budgeted, synthetic | OPEN: shadow replies were failures by design |
| A4 | Each lane's PROD mode decided: keep live, move to shadow, or turn off | A signed table. Hardened detectors will fire less often than PROD's | OPEN |
| A5 | Planning and Ethics blockers fixed | P-1 to P-5, E-1 to E-5 closed | PARTIAL: Planning candidate #300, Ethics analysis only |
| A6 | G3's title criterion and the populated negative control | A live pass, or an owner decision to waive | OPEN |

### Existing PROD capability and identity

| # | Requirement | Evidence required | Status |
|---|---|---|---|
| A7 | Inventory of what PROD does today, and a pass or a named, accepted loss for each | Conversation, Router V2, career ingestion, automation, Command Center relay | OPEN |
| A8 | Persona and identity preserved | Before-and-after comparison on a fixed prompt set, in an isolated copy | OPEN |
| A9 | Hermes runtime reproducible from reviewed source | Build equals the recorded digests. One file was withheld from recovery | PARTIAL: 175 of 176 verified |
| A10 | The Core API gap closed: PROD `app.py` is far behind main, and the PROD deploy workflow is disabled | A reviewed path from `519b309`, schema changes listed | OPEN |

### Canonical memory

| # | Requirement | Evidence required | Status |
|---|---|---|---|
| A11 | Canonical memory integrity across migration | Digests of every canonical store before and after, in rehearsal | OPEN |
| A12 | L04 and L18 states decided: PROD has L04 empty and 3 L18 shadow candidates | Owner decision | OPEN |
| A13 | Owner-memory authority on PROD: signer, broker and witness are DEV-only today | A design, or a decision that PROD stays without it at first | OPEN |

### Privacy, FORGET and retention

| # | Requirement | Evidence required | Status |
|---|---|---|---|
| A14 | **FORGET reaches the Core API database.** Today it does not | Goals, tasks, drafts and World Model covered, with a DEV drill using canaries | OPEN: candidates in #296, not wired |
| A15 | Deleted data cannot return | Source decision for `career_events`, cursor rule, restore gate | OPEN |
| A16 | Retention set for each store | Ages decided and running | OPEN |
| A17 | FORGET exists on PROD at all, with Privacy anchoring | Equivalent of the DEV activation | OPEN |
| A18 | Records carry no identifying data the owner hasn't accepted | `app_id` decided; `state.db` on PROD reviewed: it was unread in the audit | PARTIAL |

### Authentication and authorization

| # | Requirement | Evidence required | Status |
|---|---|---|---|
| A19 | Write authentication enforced | #289 stages 1 to 5 | OPEN |
| A20 | Read authentication for owner-content routes | Design and tests | OPEN |
| A21 | Core API not reachable off-host without credentials | Bound to loopback, or an accepted reason | OPEN |
| A22 | Deployer least privilege: the deployer identity had broad project-wide roles when reviewed | A current review and a PROD-scoped identity | OPEN |

### Provider exposure

| # | Requirement | Evidence required | Status |
|---|---|---|---|
| A23 | PROD provider exposure measured and bounded per lane | What each live lane sends, with limits | OPEN |
| A24 | A PROD budget and failure mode: DEV's 5-request gate is a test tool, not a production control | Designed and tested | OPEN |
| A25 | No fallback provider surprise | Verified in PROD configuration | OPEN |

### DEV and PROD isolation

| # | Requirement | Evidence required | Status |
|---|---|---|---|
| A26 | Configuration separated: no DEV pin, host, token or path in PROD artifacts | A scan, in CI | OPEN |
| A27 | DEV-only tools cannot run on PROD | Refusal tests. Scripts already check the hostname | PARTIAL |
| A28 | Separate credentials for every service | Inventory | OPEN |

### Migration rehearsal

| # | Requirement | Evidence required | Status |
|---|---|---|---|
| A29 | **Full rehearsal on an isolated copy of a PROD snapshot**, with no network path to PROD and provider access off | A rehearsal record | OPEN |
| A30 | Schema migration with row-level checks: 31 beliefs, 93 evidence rows, 3 goals, 11 traces, 7 tasks and 10 drafts when audited | Counts and digests before and after | OPEN |
| A31 | Rehearsed rollback, timed | A record | OPEN |

### Backup, rollback and recovery

| # | Requirement | Evidence required | Status |
|---|---|---|---|
| A32 | Scheduled off-host backups. PROD had one disk and no schedule; a manual snapshot was taken on 2026-10-27 | Schedule running, restore tested | OPEN |
| A33 | A backup policy that respects FORGET | Restore gate | OPEN |
| A34 | Rollback tested live at least once. No live rollback has been exercised on DEV for w1 | A DEV exercise, then the rehearsal | OPEN |
| A35 | A recovery runbook for a failed cutover | Reviewed | OPEN |

### Post-deployment acceptance

| # | Requirement | Evidence required | Status |
|---|---|---|---|
| A36 | Criteria fixed before the cutover | Written and signed | OPEN |
| A37 | Minimum set: identity prompts, one memory recall, one real career read, one FORGET drill on canaries, a provider-budget check, no failed units, and fingerprints unchanged except as planned | Run once, recorded | OPEN |
| A38 | A monitoring window with named rollback triggers | Defined | OPEN |

### Broken PROD integrations

| # | Requirement | Evidence required | Status |
|---|---|---|---|
| A39 | Decide on Google OAuth (`invalid_grant` since 08-31) and WhatsApp (broken since 09-12): repair, or an accepted loss | Owner decision | OPEN |

## B. Safe to stay disabled or shadow-only until after migration

| Feature | Condition |
|---|---|
| Reasoning, Workspace and Motivation Live on the new stack | A4 decides how PROD's live lanes map to this. Shadow here means the old behaviour is not silently lost |
| Planning and Ethics shadow on the hardened stack | Same condition |
| Motivation drives in Workspace | Off: needs real records |
| Model candidate paths for Planning and Ethics | Not wired. Stay off |
| Goal creation through conversation | Refused today. Stays off until A14 to A16 |
| L04 owner memory expansion | After A11 to A13 |
| Social cognition, memory consolidation, canonical LTM lanes | Off |
| `open-acknowledged` removal (#289 stage 6) | May follow, if enforcement is on |
| Per-caller credentials | One principal is acceptable at first |
| Detector tuning on real shadow records | Needs real traffic, so it can only follow |

## What does not count as exit

- All seven lanes passing shadow tests.
- CI being green.
- Simulations passing without a real-host preflight. Two generator bugs here were caught only by the real host.
- Offline detector scores, which all come from one author's synthetic pools.

## Recommended order

1. Close Planning and Ethics on DEV, in shadow.
2. Cross-lane and populated-store tests on DEV, A1 and A2.
3. FORGET and retention, A14 to A16, with a DEV drill.
4. Authentication stages on DEV.
5. A model-in-the-loop window, A3.
6. Owner decisions: A4, A7, A12, A15, A39.
7. Rehearsal on an isolated snapshot, A29 to A31.
8. Backups and rollback, A32 to A35.
9. Cutover under A36 to A38.
