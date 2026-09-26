# REPO:RQ-021 — Deterministic playbooks, model planning, and replanning

> **Namespace (primary-source pass, 2026-09-26).** This finding is filed
> under **REPO:RQ-021** (in-repo register). MASTER equivalent: MASTER:RQ-013 (SEMANTIC MATCH); related MASTER:RQ-014.
> See the [crosswalk](../rq-register-crosswalk.md).
>
> **Primary-source evidence added:**
> - J1 Entries 9–10 (PRIMARY): Slice 1 self-tests 7/7 and Slice 2 16/16; Slice 1 deliberately used "a bounded planner rather than immediately building unrestricted autonomy" (also quoted in MASTER:RQ-013).
> - MASTER:RQ-013 proposes the hierarchy playbook → single capability → dynamic planner → hierarchical planner → worker delegation.

## Research question

When should deterministic playbooks replace model planning? (In-repo RQ-021,
historical status PARTIAL; related RQ-022 replanning, RQ-023 unreliable
reasoning, RQ-025 delegation.)

## Why it matters to LILITH

Model planning is flexible but can invent capabilities, skip preconditions,
or quietly change what the user asked for. Deterministic playbooks are
reliable but narrow. Where the boundary sits decides how much of LILITH's
behaviour is predictable.

## Original hypothesis / problem

Known high-confidence operations use versioned playbooks; novelty and
complexity trigger bounded planning.

## Architecture explored

- **Playbook engine** (Slices 1–2): one executor/retry/cancel/verify/persist
  path shared by every read task; later write playbooks (Slices 4–5) reuse it.
- **Proposal-only planner** ([Slice 12](../../architecture/slice-12-planning-design.md)):
  ephemeral `PlanSnapshot`, single planning subject, a *grounder* that maps
  candidate steps to real state and a separate *validator* that may drop but
  never add steps, a non-authoritative capability view whose runtime
  availability is always `UNKNOWN`, and verification declared but not
  performed.
- **Tool-less reasoning** (Slice 9) as the only model component on the path.

## Experiments / implementation slices

Slices 1–2 self-tests (7/7 and 16/16, PRIMARY, J1); Slice 12 40/40 and acceptance A–G.

## Evidence

- OPERATIONAL (pre-DEV live): deterministic template plans for applications 14
  and 17 returned `USER_DECISION_REQUIRED` because of real duplicate drafts;
  no writes; plan-only requests created nothing (Slice 12 A, B).
- TEST (fixture): unsupported capability → `NO_VIABLE_PLAN /
  MISSING_CAPABILITY`; prohibited send → `BLOCKED_BY_POLICY` with no ALLOW
  claim; replanning only with an explicit prior plan (Slice 12 D, E, G).

## Negative findings / failures

- N-09: the LLM candidate planner is built and unit-tested but **not wired
  live**; every live plan is the deterministic template.
- Post-execution replanning exists only as fixtures; there is no executor on
  the Router path.
- N-08: a detector-precedence defect surfaced during acceptance.
- No reliability or cost comparison between playbooks and model planning has
  been run.

## Current answer

- **PROVEN (pre-DEV live, fixtures):** a planner can be made proposal-only,
  unable to invent capabilities or claim policy approval, and still useful for
  surfacing real blockers.
- **DESIGNED:** bounded LLM candidate planning behind grounder ≠ validator.
- **INFERRED:** current evidence supports "deterministic first, model as
  candidate generator" as a safe default; it does not show when the model
  path becomes necessary.
- **UNKNOWN:** the reliability/cost crossover; live replanning behaviour.

## Confidence / maturity

Medium for the safety envelope; low for the comparative question itself.

## What remains unanswered

Live LLM candidate planning under the validator; replanning after partial
execution; delegation to workers (RQ-025, no evidence).

## Related RQs

RQ-022, RQ-023, RQ-025, RQ-026.

## Related slices

1, 2, 4, 5, 9, 12.

## Publication notes

Suitable for an **architecture article** on "grounder ≠ validator" and
proposal-only planning. Must state that model planning is not live.
