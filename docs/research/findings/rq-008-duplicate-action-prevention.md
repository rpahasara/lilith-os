# REPO:RQ-008 — Preventing duplicated actions

> **Namespace (primary-source pass, 2026-09-26).** This finding is filed
> under **REPO:RQ-008** (in-repo register). MASTER equivalent: MASTER:RQ-026 (SEMANTIC MATCH); MASTER:RQ-002 PARTIAL OVERLAP (duplicate-action subquestion).
> See the [crosswalk](../rq-register-crosswalk.md).
>
> **Primary-source evidence added:**
> - J1 Entry 11 (PRIMARY): Slice 3 operation idempotency and stale-revision 409 verified live.
> - S4 (2026-08-24) OS Core v0.1 checklist already required an event log "with replay/idempotency".

## Research question

How are duplicated cross-runtime external actions prevented? (In-repo RQ-008;
related RQ-033, RQ-039.)

## Why it matters to LILITH

Retries, reloads, crashes, and two channels asking for the same thing can each
cause an action to happen twice. For drafts that is clutter; for email,
deployment, or memory authority it is harm.

## Original hypothesis / problem

Action fingerprints, global operation IDs, leases where needed, and external
idempotency keys form layered protection.

## Architecture explored

Layered idempotency at every write boundary built so far:

| Layer | Mechanism | Slice |
| --- | --- | --- |
| Task store | `operationId` replay no-op; `expectedRevision` → 409 | 3 |
| Draft write | idempotency key `taskId:stepId`; deterministic draft ID; `created:false` on replay | 4 |
| World Model ingest | persistent cursor + identical-evidence skip | 7.1 |
| Conversational drafts | deterministic dedup: 1 → reuse, >1 → refuse, 0 → create | 7.3 (REPORTED) |
| Goals | `operationId`, revision guard, USER_REQUESTED dedup | 8 |
| Learning ledger | idempotent job/lease/cursor; stale lease cannot commit | 15A |
| Canonical apply | replay returns `ALREADY_APPLIED` with the same identities | 15B1, 15B2b-A |
| Owner authority | unique claim keyed by `challengeId` before evidence; challenge ID as unique evidence nonce; never reissue | B1b-1 |

## Evidence

- TEST: Slice 7 A–R (idempotency, canonical-key dedup); Slice 7.1 9/9
  (idempotent reprocess, restart-no-duplicate); 15A B/C (replay, crash before
  cursor); 15B1 B/F (CREATE/RESTORE replay); B1b-1 deterministic fault hooks and
  concurrent-confirmation tests.
- OPERATIONAL (pre-DEV live): 8 applications → 31 beliefs, second run
  idempotent (Slice 7); second tick `new_events: 0` after restart (7.1); app 17
  drafts stayed 3 → 3 when a create was requested again (Slice 10 record).

## Negative findings / failures

- N-05: dedup did not exist when application 14 received two drafts; the
  duplicates persist and block the goal until the user reconciles them.
- No external connector exists, so no external idempotency has been tested
  (RQ-039).

## Current answer

- **PROVEN (TEST + pre-DEV live):** for internal writes, layered operation IDs,
  deterministic keys, cursors, and replay-returning-same-result prevent
  duplicates under tested retries, restarts, and crash points.
- **DESIGNED:** owner-authority issuance is protected by claim-before-evidence
  and a unique nonce.
- **INFERRED:** current evidence supports "every write boundary needs its own
  idempotency identity"; a single global mechanism was never needed.
- **UNKNOWN:** external systems without idempotency; cross-runtime duplicates.

## Confidence / maturity

High for internal writes; none for external effects.

## What remains unanswered

External connector duplication under lossy responses; leases across runtimes;
repairing pre-existing duplicates without deleting evidence.

## Related RQs

RQ-033, RQ-039, RQ-005.

## Related slices

3, 4, 7.1, 7.3, 8, 15A, 15B1, 15B2b-A, B1b-1.

## Publication notes

Mature for an **engineering blog** ("idempotency at every boundary of a
personal agent"), including the honest note that dedup does not repair
history (N-05).
