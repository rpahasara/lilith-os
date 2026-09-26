# REPO:RQ-019 — Goal arbitration and executive focus

> **Namespace (primary-source pass, 2026-09-26).** This finding is filed
> under **REPO:RQ-019** (in-repo register). MASTER equivalent: MASTER:RQ-011 (SEMANTIC MATCH); related MASTER:RQ-010, 012.
> See the [crosswalk](../rq-register-crosswalk.md).
>
> **Primary-source evidence added:**
> - Master §05: "Executive focus and conversational attention remain distinct" (2026-09-14), matching the Slice 10 invariant.

## Research question

How should conflicting goals be prioritized? (In-repo RQ-019; related RQ-018
object distinctions and RQ-020 stale goals.)

## Why it matters to LILITH

A persistent assistant accumulates goals. If "what matters now" is decided
by whichever prompt arrived last, or by an LLM's mood, LILITH's behaviour is
neither predictable nor explainable.

## Original hypothesis / problem

Explicit user priorities dominate; inferred trade-offs require uncertainty
and escalation thresholds.

## Architecture explored

- [Slice 8 Goal/Executive](../../architecture/slice-8-goal-executive-design.md):
  durable goals with an FSM (PENDING/ACTIVE/BLOCKED/SUSPENDED/COMPLETED/FAILED/
  CANCELLED, explicit reopen), evidence-gated completion, and deterministic
  arbitration: lifecycle > priority > deadline > source > recency > id. Focus
  is **derived** from durable rows and reconstructed after restart.
- Slice 10: **Workspace focus ≠ Executive focus.** Attention may select what
  to reason about this turn but never mutates the executive's durable focus.
- Slice 11: motivation may add ordinal pressure to attention; it has no edge
  to the executive.

## Experiments / implementation slices

Slice 8 22/22 + 9/9; Slices 10/11 invariant checks on real focus.

## Evidence

- OPERATIONAL (pre-DEV live): goals for applications 17 (ACTIVE, HIGH), 8
  (PENDING), 14 (BLOCKED on two unsent drafts); SUSPEND → RESUME moved focus
  and back; winner by lifecycle rule; focus reconstructed after restart
  (Slice 8).
- OPERATIONAL: executive focus `g.95cee37…` unchanged before and after all
  attention and motivation turns, including an explicit "forget app 17, focus
  on app 14 instead" override (Slices 10, 11).

## Negative findings / failures

- No preference elicitation; priorities are explicit fields only.
- No parent/child cascade.
- The app-14 goal stayed BLOCKED because of historical duplicate drafts
  (N-05) — arbitration was correct, but the world state was stuck.

## Current answer

- **PROVEN (pre-DEV live):** deterministic, restart-safe arbitration over
  durable goals is workable and explainable; per-turn attention can be kept
  from overriding durable focus.
- **DESIGNED:** evidence-gated completion.
- **INFERRED:** current evidence supports separating *salience this turn*
  from *commitment over time* as an architectural rule.
- **HYPOTHESIS:** explicit user priority should dominate inferred trade-offs.
- **UNKNOWN:** how to infer priorities safely; staleness interventions
  (RQ-020).

## Confidence / maturity

Medium for the deterministic mechanism; untested for inference.

## What remains unanswered

Preference elicitation; stale-goal review precision; how an explicit user
override should become durable (it currently does not).

## Related RQs

RQ-018, RQ-020, RQ-040.

## Related slices

8, 10, 11.

## Publication notes

Suitable for an **engineering blog** ("why attention must not rewrite
commitments") with real but small-scale evidence.
