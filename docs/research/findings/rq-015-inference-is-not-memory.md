# REPO:RQ-015 — Preventing inference from becoming false memory

> **Namespace (primary-source pass, 2026-09-26).** This finding is filed
> under **REPO:RQ-015** (in-repo register). MASTER equivalent: MASTER:RQ-009 (SEMANTIC MATCH); MASTER:RQ-117 PARTIAL OVERLAP; related MASTER:RQ-036 (malicious content becoming memory).
> See the [crosswalk](../rq-register-crosswalk.md).
>
> **Primary-source evidence added:**
> - The epistemic separation predates Slice 7: S4 (2026-08-24) truth ladder OBSERVED → INFERRED → USER-CONFIRMED → STALE/CONFLICTED, and "personality may color language; it may never color evidence, confidence or permissions".
> - MASTER:RQ-009 proposes OBSERVED, USER_ASSERTED, DERIVED, INFERRED, SPECULATIVE — Slice 7 implemented three of them (OBSERVED, USER_ASSERTED, INFERRED) plus VERIFIED as epistemic states.

## Research question

How is inference prevented from becoming false memory? (In-repo RQ-015;
related RQ-009, RQ-047; threat T-08 memory poisoning. Master topics:
inference becoming false memory; memory immune system.)

## Why it matters to LILITH

A language model's plausible guess, repeated into memory, becomes a durable
"fact" that later reasoning trusts. This is the most direct route from a
hallucination to a persistent false belief about the owner.

## Original hypothesis / problem

Observed, user-asserted, derived, inferred, and speculative claims remain
distinct and have different promotion rules.

## Architecture explored

- **Invariant "memory ≠ truth"** (CA-V1 §12; 15A/15B1 governing sentence
  "Learning proposes · LTM admits and stores · Provenance explains · Memory is
  not truth"; reiterated in B1c and 15B2b-B).
- **Epistemic states** on beliefs: `OBSERVED | USER_ASSERTED | INFERRED |
  VERIFIED`; only the Verification path may set `VERIFIED`; there is no generic
  belief setter and no HTTP mutation route (Slice 7).
- **Candidates are not facts:** `SHADOW_ELIGIBLE` is explicitly not "admitted,
  accepted, learned, true" (15A).
- **Epistemic basis is never promoted** by canonical storage (15B2b-A) or by
  acceptance (B2a returns it unchanged; `truthClaim` always false).
- **Model output is never authority:** B2a lists model output, proposal, row,
  apply result, cached flag, and matching value as forbidden equalities that
  all yield `NOT_ACCEPTED`.

## Experiments / implementation slices

Slice 7 A–R ("VERIFIED > INFERRED", "no generic setter", "no mutation
route"); 15B2b-A DEV probe; B2a forbidden-equality and basis-survival tests.

## Evidence

- TEST: Slice 7 A–R; B2a tests show `USER_ASSERTED` and other bases survive
  acceptance unchanged.
- DEV: the synthetic canonical item's basis remained `USER_ASSERTED`; it was
  **not** promoted to verified truth (15B2b-A).
- OPERATIONAL (pre-DEV live): all 31 live beliefs `OBSERVED`; none fabricated
  (no `follow_up_state` invented without a source column).
- REPORTED: the Slice 7.2 shadow run reproduced an ungrounded model surfacing
  raw storage details; the live grounded lane removed it (N-04).

## Negative findings / failures

- `apply_verified_delta` (the only VERIFIED path) is implemented but unused,
  because no Verification layer feeds beliefs yet.
- There is no path by which LLM inference writes memory — so the defence is
  proven by *absence of a path*, not by resisting an adversarial one.
- N-35: an application-level attacker could currently mint authority
  evidence; the epistemic label would still say `USER_ASSERTED`, but the
  memory could be falsely attributed to the owner.

## Current answer

- **PROVEN (TEST/DEV/pre-DEV live):** epistemic basis is carried end to end
  and never promoted by storage or acceptance; unsourced values are not
  fabricated; model output alone can never produce an accepted memory.
- **DESIGNED:** VERIFIED only through independent verification.
- **INFERRED:** current evidence supports structural separation as the main
  defence. Its strength today comes partly from having no inference write path
  at all.
- **HYPOTHESIS:** the same separation holds once an LLM consolidation path
  exists.
- **UNKNOWN:** resistance to poisoned-but-authorized content; mutation tests
  that try to promote unsupported inferences (register next step).

## Confidence / maturity

Medium: structurally strong, adversarially untested.

## What remains unanswered

An adversarial promotion corpus; how INFERRED claims should ever become
durable; detection of poisoned content that passes authority checks
(the "memory immune system" topic).

## Related RQs

RQ-009, RQ-013, RQ-047, RQ-010.

## Related slices

7, 7.2, 15A, 15B1, 15B2b-A, B2a.

## Publication notes

Strong candidate for an **AI cognition research note** or **architecture
article** ("memory is not truth: carrying epistemic basis end to end"). Must
say the defence has not faced an adversarial inference path yet.
