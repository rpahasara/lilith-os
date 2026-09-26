# REPO:RQ-033 — Unknown execution state and crash semantics

> **Namespace (primary-source pass, 2026-09-26).** This finding is filed
> under **REPO:RQ-033** (in-repo register). MASTER equivalent: MASTER:RQ-027 (SEMANTIC MATCH); related MASTER:RQ-026, 064.
> See the [crosswalk](../rq-register-crosswalk.md).
>
> **Primary-source evidence added:**
> - RUN evidence: control install 36141310248 succeeded; two `DISPATCH_ONCE` runs (36143716249, 36145190507) failed at the dispatch step (N-25, N-36). No crash experiment ran.

## Research question

What should happen when a call times out after it may have succeeded?
(In-repo RQ-033; related RQ-008 duplicates, RQ-037 false outcomes.)

## Why it matters to LILITH

Blind retries after an ambiguous failure duplicate effects; blind failure
reports abandon effects that happened. For owner authority, a crash between
"proof consumed" and "evidence issued" must never produce two authorities.

## Original hypothesis / problem

Enter UNKNOWN, reconcile by read-back, and retry only when safety is
established.

## Architecture explored

- **Internal writes** (Slice 4): unknown-commit → verify-before-retry;
  approved-not-executed → idempotent auto-resume after reload.
- **Canonical apply** (15B1): one `BEGIN IMMEDIATE` transaction; forced
  failure rolls back admission, revision, source, pointer, and audit together;
  lost acknowledgement → replay returns `ALREADY_APPLIED`.
- **Proof → authority** ([B1b-1](../../architecture/slice-15b2b-b1b1-broker-foundation.md)):
  no transaction spans the owner-control and cognitive databases, so a
  conservative crash table governs five points (A1–A5): consumed-no-claim
  burns the proof; claim-no-evidence becomes terminal; evidence-no-link
  reconciles the same evidence; never reissue.
- **Live experiment design** (Stage III-A A2): a fault seam that self-stops the
  broker after proof consumption and before claim, a reversible state fork, a
  pidfd-bound guard, and a one-shot final controller to SIGKILL, restart,
  recover, and replay.

## Experiments / implementation slices

Slice 4 W-H/W-I (REPORTED); 15B1 P; B1b-1 deterministic fault hooks and
barrier-based concurrency tests; Stage III-A source chain (PRs #38, #53–#59);
isolated real-systemd tests in WSL2; DEV dispatch run 36145190507.

## Evidence

- TEST: fault hooks at A1–A5 produce the conservative outcomes; forced
  transaction failure leaves no partial canonical write.
- TEST (real systemd, synthetic): guard/gate lifecycle, controller SIGKILL
  making both broker units inactive, one-shot restart rejection.
- **DEFERRED (DEV):** the A2 dispatch consumed its one-shot tombstone, but the
  controller failed; the phase journal holds `INTENT` only; no arm, guard, or
  crash occurred; the V2 authorization is preserved and unconsumed
  ([B1c acceptance](../../architecture/slice-15b2b-b1c-acceptance-record.md#broker-and-stage-iii-preservation)).

## Negative findings / failures

- N-25: the live crash experiment did not run. No live evidence exists for
  A1–A5.
- N-24: `systemctl mask --runtime` did not mask units under `/etc`, found
  before DEV use.
- The repository does not record why the controller failed; a read-only
  forensics operation was added (PR #60) but its results are not in the
  repository.

## Current answer

- **PROVEN (TEST):** under deterministic fault injection the recovery rules
  never duplicate authority and never leave partial canonical writes;
  internal draft writes verify before retrying.
- **DESIGNED:** a reversible, contained live A2 experiment.
- **INFERRED:** current evidence supports "unit-proven, live-unproven" crash
  semantics — the wording the 15B2b-B design adopts.
- **UNKNOWN:** behaviour under real process death, WAL recovery, and restart
  on the DEV host; any external-connector UNKNOWN state.

## Confidence / maturity

Medium in unit scope; zero live evidence.

## What remains unanswered

A freshly authorized synthetic A1–A5 rehearsal (proposed as B2c, not an A2
retry); timeouts around an external reversible capability.

## Related RQs

RQ-008, RQ-037, RQ-035, RQ-049.

## Related slices

4, 15B1, B1b-1, B1b-2b, Stage III-A A2, 15B2b-B design.

## Publication notes

The Stage III-A story is valuable for an **engineering blog** on "designing a
one-shot crash experiment and what happens when it fails at step one" — the
failure is the lesson. No claim of proven crash safety.
