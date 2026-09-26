# REPO:RQ-044 — Measuring whether LILITH improves rather than merely changes

> **Namespace (primary-source pass, 2026-09-26).** This finding is filed
> under **REPO:RQ-044** (in-repo register). MASTER equivalent: MASTER:RQ-068 (SEMANTIC MATCH); related MASTER:RQ-017, 069, 072, 083.
> See the [crosswalk](../rq-register-crosswalk.md).
>
> **Primary-source evidence added:**
> - MASTER:RQ-068 lists metric families (technical, cognitive, memory, proactivity, identity, governance); MASTER:RQ-083 proposes about 50 canonical conversations/tasks as a drift benchmark.
> - S4 (2026-08-24) project-tracking metrics: event health, attention quality, truth quality, autonomy safety, memory quality, app value.

## Research question

How do we measure continuity, identity consistency, verification quality,
and interruption appropriateness? (In-repo RQ-044; related RQ-045 model
upgrades and RQ-050 autonomy advancement.)

## Why it matters to LILITH

A layered architecture can pass every unit test while the assistant becomes
less trustworthy. Without cognition-level evaluation, "slice accepted" means
"did not break", not "got better".

## Original hypothesis / problem

A versioned compatibility suite combining scenario tests, calibration,
behavioural invariants, and longitudinal human ratings.

## Architecture explored

What exists is an **engineering regression discipline**:

- per-slice suites with a growing cumulative Router regression (226 tests at
  Slice 14, 282 at 15A, 335 from 15B1), plus standalone classifier (18),
  social guard (34), fail-open (14), world-context checks, and the frontend
  core self-test (67);
- deploy-exact isolated trees, hash-pinned protected owners, and database
  schema fingerprints before/after every pre-DEV deployment (Slices 14–15B2a);
- acceptance matrices (15B1 A–P, 15B2a A–DL, B2a 89-case tamper matrix);
- three-state acceptance records (SOURCE / DEV / PROD) from 15B2b-A onward;
- repository CI and exact-SHA DEV deployment gates.

## Evidence

All counts above are OBSERVED in the cited deployment and acceptance records.

## Negative findings / failures

- No golden scenarios, calibration curves, identity-consistency measures, or
  human ratings exist.
- N-12: several "live" acceptances were route-level harness runs.
- N-16: the roadmap's autonomy gates were never updated after A3-level
  internal writes were reached (Slices 4–5).
- Some installed-tree test discovery was deliberately **not** run because
  legacy tests could write production state (Slice 14 record) — a sign that
  the test estate and production were not cleanly separated before DEV
  existed.

## Current answer

- **PROVEN:** regression discipline catches breakage and protects invariants
  across 15+ additive slices.
- **INFERRED:** current evidence supports "no regression" claims only. It
  cannot support "LILITH improved", "identity preserved across model change",
  or "interruptions are appropriate".
- **UNKNOWN:** every cognition-level metric in the question.

## Confidence / maturity

High for regression; none for the question as posed.

## What remains unanswered

The first 20 golden scenarios and rubric; shadow comparison of two model
versions (RQ-045); quantitative autonomy gates (RQ-050).

## Related RQs

RQ-045, RQ-050, RQ-043, RQ-037.

## Related slices

8–15B2a, 15B2b-A, B2a.

## Publication notes

Suitable for an **engineering blog** on regression discipline for layered
agents, explicitly distinguishing it from cognitive evaluation.
