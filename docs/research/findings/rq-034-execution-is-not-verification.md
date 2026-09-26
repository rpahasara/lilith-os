# REPO:RQ-034 — Execution is not verification

> **Namespace (primary-source pass, 2026-09-26).** This finding is filed
> under **REPO:RQ-034** (in-repo register). MASTER equivalent: MASTER:RQ-028 (SEMANTIC MATCH); related MASTER:RQ-029, 030, 031, 092.
> See the [crosswalk](../rq-register-crosswalk.md).
>
> **Primary-source evidence added:**
> - J1 Entry 9 (PRIMARY) replaces the earlier REPORTED claim: the live Slice 1 result reported "4 of 6 services healthy with evidence and an overview-vs-detail discrepancy"; J1's proposed article title was "Why My AI Agent Refuses to Trust HTTP 200".
> - RUN evidence for the B1c `curl -f` failure: run 36172947091 attempt 3, step "Prove routine DEV federation cannot obtain PROD or the legacy privileged identity".

## Research question

How is goal success distinguished from execution success? (In-repo RQ-034,
historical status PARTIAL; related RQ-035 independence, RQ-036 sufficiency,
RQ-037 measuring false outcomes.)

## Why it matters to LILITH

"The API returned 200" is the most common false success in agent systems.
LILITH's governing rule makes the verifier the only authority on "done".

## Original hypothesis / problem

Each task class needs an expected-state and evidence contract beyond
transport success. [ADR-0003](../../adr/0003-separate-execution-from-verification.md)
separates execution from verification.

## Architecture explored

The invariant recurs at every layer, each time in a new form:

| Form | Where |
| --- | --- |
| Typed PASS/PARTIAL/FAIL verifier over content, not HTTP status | Slice 1 |
| Read-back after write; "attempted" ≠ "done" | Slices 4, 6 |
| Only Verification sets VERIFIED | Slice 7 |
| `SHADOW_ELIGIBLE` ≠ accepted; task/HTTP/exit status are not proof | 15A, 15B1 J |
| Trusted pre/post snapshots compare complete state around a candidate | B1b-2b, DEV validation |
| Deployment ≠ activation | B1c |
| Apply succeeded ≠ accepted memory | B2a |

## Experiments / implementation slices

Slice 1 verifier; Slice 4 read-back; B1c federation proof; B2a forbidden
equalities.

## Evidence

- PRIMARY (J1 Entry 9): the Slice 1 verifier reported "4 of 6 services
  healthy" with an overview-vs-detail discrepancy instead of passing on
  HTTP 200 (N-01).
- DEV: every B1c deployment asserts `ACTIVATION=NOT_ACCEPTED
  reason=GRANT_ABSENT`; a successful deploy never implies activation.
- TEST: B2a returns `NOT_ACCEPTED` for apply-succeeded-without-chain.

## Negative findings / failures — the invariant also failed in our own tooling

- N-30: the B1c federation proof used `curl -f`; a *correct* 403 denial
  aborted the step as a transport failure. Fix: explicit status classification
  with transport error as a separate state.
- N-19: Stage II compared a display string, so a bookkeeping change looked
  like an API restart (false FAIL).
- N-21/N-22: SSH stdout and transfer stalls were at first treated as
  meaningful results.
- N-26: an unresolvable identity needed a third state (`DEFERRED`) distinct
  from PASS and FAIL.

## Current answer

- **PROVEN (pre-DEV live, DEV, TEST):** separating execution from verification
  catches real inconsistencies, and every authority boundary built so far
  treats execution success as one input, never as acceptance.
- **INFERRED:** current evidence supports a stronger statement than the
  register: *transport signals are not semantic results, even inside the
  verification tooling itself* — the invariant must apply recursively.
- **UNKNOWN:** expected-state contracts for external actions; false-PASS rates.

## Confidence / maturity

High for the principle within scope; no quantitative measurement (RQ-037).

## What remains unanswered

A verifier benchmark with injected ambiguous outcomes (RQ-037); independence
topologies compared by correlated-failure rate (RQ-035).

## Related RQs

RQ-035, RQ-036, RQ-037, RQ-033.

## Related slices

1, 4, 6, 7, 15A, 15B1, B1b-2b, B1c, B2a.

## Publication notes

Strong **engineering blog** material, especially the self-inflicted failures
(`curl -f` on a denial; display-string comparison). Mature enough for a
practitioner talk.
