# REPO:RQ-040 — Attention, motivation, and the affect boundary

> **Namespace (primary-source pass, 2026-09-26).** This finding is filed
> under **REPO:RQ-040** (in-repo register). MASTER equivalent: MASTER:RQ-048 (SEMANTIC MATCH); MASTER:RQ-047, 050 PARTIAL OVERLAP; related MASTER:RQ-044, 049; affect: MASTER:RQ-121 and MASTER:RQ-060 (no REPO question).
> See the [crosswalk](../rq-register-crosswalk.md).
>
> **Primary-source evidence added:**
> - S4 (2026-08-24): presence states "are presentation, not simulated feelings"; attention levels 0–5 by urgency, confidence, user state, reversibility and time-to-impact.
> - S1 (2026-09-07) §10: no-simulated-suffering invariant for drives.
> - Master v1.0/v1.1 (2026-09-14) §08 DESIGNED a functional affect architecture (drives → appraisal → fast affect → slow mood → expression), an epistemic boundary ("subjective experience is not thereby proven"), "affect never outranks governance", and anti-manipulation / anti-suffering constraints; MASTER:RQ-121 registers affective continuity as research. Slices 11 and 14 (2026-09-08/09) deliberately implemented none of it.

## Research question

When should LILITH interrupt rather than wait? (In-repo RQ-040; related
RQ-041 proactivity without surveillance and RQ-014 what enters cognition.)
This record also documents the project's current constraints on affect,
because attention and motivation are where affect would first touch
cognition.

## Why it matters to LILITH

Attention decides what LILITH thinks about; motivation biases it. Getting
this wrong produces either a nagging assistant or one that ignores what
matters — and, if affect is modelled carelessly, either manipulation or
engineered distress.

## Original hypothesis / problem

Expected harm, urgency, actionability, confidence, user context, and
interruption cost determine attention level.

## Architecture explored

- **Global Workspace** ([Slice 10](../../architecture/slice-10-global-workspace-design.md)):
  deterministic, ordered salience classes; one primary and up to four
  secondary candidates; bounds the reasoning input; never mutates executive
  focus; USER_TURN never auto-consumes a slot.
- **Motivation** ([Slice 11](../../architecture/slice-11-motivation-homeostasis-design.md)):
  ordinal drives (COHERENCE from belief conflicts, GOAL_COMPLETION from
  blocked goals; SAFETY synthetic); a lowest-rank `MOTIVATION_PRESSURE` class;
  **no floats, no affect keys, no emotional wording**; scoped (no global scan).
- **No-suffering invariant** (CA-V1 §10): drives are bounded, decaying error
  signals for prioritization; the system never represents, rewards, or
  reports subjective pain; no drive may be maximised by inducing its own
  deficit.
- **Social cognition** (Slice 14): TURN-only cues (difficulty, support,
  humor) with explicit prohibitions on affect, emotion inference, and
  relationship state.

## Experiments / implementation slices

Slice 10 24/24 and acceptance 1–5; Slice 11 32/32 and shadow → live
acceptance; Slice 14 49/49 (shadow).

## Evidence

- OPERATIONAL (pre-DEV live): workspace primary `USER_REFERENCED_BLOCKER` and
  `USER_OVERRIDE_TARGET` selected deterministically; reasoning input bounded
  to the snapshot (Slice 10).
- OPERATIONAL: GOAL_COMPLETION = SIGNIFICANT derived only from the real blocked
  goal; the answer to "why does app 14 keep surfacing?" was functional and
  source-backed, "no emotional wording" (Slice 11).

## Negative findings / failures

- N-07: in realistic turns motivation contributed **zero** workspace slots
  (its sources were already candidates). Its live effect is a trace and a
  bounded summary to reasoning.
- No interruption has ever been delivered; SYSTEM_CRITICAL and
  BACKGROUND_MAINT producers are synthetic.
- Slice 14 is shadow-only; Presence hints have no consumer.

## Current answer

- **PROVEN (pre-DEV live):** attention and drives can be deterministic,
  scoped, explainable, and kept from overriding commitments or producing
  affect language.
- **DESIGNED:** interruption thresholds and delivery via Presence.
- **INFERRED:** current evidence supports that V1 motivation is *correct but
  behaviourally inert*; any claim that drives shape behaviour needs new
  measurement.
- **Explicit non-claim:** nothing built so far is an emotion or affect model.
  *(Corrected.)* The affect research target was first canonicalized on
  2026-09-14 as MASTER:RQ-121, with a designed functional-affect architecture
  in Master §08; the un-numbered candidates in the RQ candidates record extend
  it. None of it is implemented.
- **UNKNOWN:** interruption precision/regret; how affect-like dynamics could
  influence attention without granting authority.

## Confidence / maturity

Medium for mechanics; low for the behavioural question.

## What remains unanswered

Interruption scenarios with missed-critical and false-interrupt rates;
proactivity abuse review (RQ-041); whether a richer appraisal signal should
feed the workspace.

## Related RQs

RQ-041, RQ-014, RQ-019, RQ-043.

## Related slices

10, 11, 14; CA-V1 §9–§10.

## Publication notes

Suitable for an **AI cognition research note** on "a drive system that was
correct and did nothing" — a useful negative result. Must not describe
Slice 11 as emotions.
