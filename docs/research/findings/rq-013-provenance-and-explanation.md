# REPO:RQ-013 — How LILITH knows why it believes a claim

> **Namespace (primary-source pass, 2026-09-26).** This finding is filed
> under **REPO:RQ-013** (in-repo register). MASTER equivalent: MASTER:RQ-007 (SEMANTIC MATCH); related MASTER:RQ-114 (explanation contract), 032, 033, 034, 075.
> See the [crosswalk](../rq-register-crosswalk.md).
>
> **Primary-source evidence added:**
> - MASTER:RQ-007 cites the Gmail failure as the demonstration of why provenance matters; J1 Entry 12 (PRIMARY) records that LILITH marked sources unavailable/stale instead of treating empty data as truth, and proposed provenance classes LIVE, CACHED_LIVE, STALE, SIMULATED, TEST, USER_ENTERED.
> - S4 (2026-08-24) "Audit explainer: records what happened, why and from which evidence".

## Research question

How does LILITH know why it believes a claim? (In-repo RQ-013, historical
status PARTIAL; related RQ-038 lineage and RQ-036 evidence sufficiency.
Master topics: belief/provenance; explanation contract.)

## Why it matters to LILITH

Without provenance, LILITH cannot explain an answer, retract a poisoned
source, or honour a deletion. Provenance is also the only thing that separates
"LILITH was told X" from "X is true".

## Original hypothesis / problem

Durable claims retain source, observation time, transformation lineage,
confidence, freshness, and verification.

## Architecture explored

Three generations of provenance:

1. **Beliefs** (Slice 7): `world_belief_evidence` rows per observation
   (`source_class`, `origin_ref`, `content_hash`, epistemic state,
   confidence) and a `world_belief_trace` row per mutation with reconciliation
   reason.
2. **Canonical memory** (15B1/15B2a/15B2b-A): immutable revision, source
   binding, proposal fingerprint, admission and apply audit, Consent and
   Policy references; provenance explanation bounded, no raw payload.
3. **Acceptance chain** (15B2b-B design, B2a): a verifier re-derives owner
   proof → broker evidence → L04 admission and returns either
   `ACCEPTED_MEMORY` or one reason from a closed, ordered 43-reason taxonomy.

## Experiments / implementation slices

Slice 7 A–R (provenance persistence, trace per mutation); 7.1 event-sourced
provenance; 15B1 N (provenance explanation) and M (lineage); B2a tamper
matrix.

## Evidence

- OPERATIONAL (pre-DEV live): `career.application:14:status` carried origins
  `career_events/14` and `job_applications/14`, three evidence rows, and a
  trace; evidence and trace counts persisted across restart (Slices 7, 7.1).
- TEST: ordered revision lineage and bounded provenance explanation (15B1);
  every signed field mutated after signing is rejected with an exact reason
  (B2a).

## Negative findings / failures

- The register's next step ("trace three multi-source conclusions end to end")
  has not been done.
- Provenance explains **what was recorded and authorized**, not whether it is
  true; B2a sets `truthClaim=false` deliberately.
- Reasoning and planning outputs are ephemeral; their provenance is by
  reference only and not stored (Slices 9, 12).

## Current answer

- **PROVEN (pre-DEV live, TEST):** beliefs can carry a complete, persistent
  evidence and mutation trail; canonical memory can carry an immutable,
  explainable lineage; an acceptance verifier can explain rejection with a
  specific reason.
- **DESIGNED:** a hash-chained provenance record per accepted revision
  (previous revision digest, owner-proof reference, broker evidence ID).
- **INFERRED:** current evidence supports provenance as an explanation of
  *authorization and origin*, which is necessary for, but not the same as, an
  explanation of *belief*.
- **UNKNOWN:** user-facing explanation quality; multi-source derivation chains.

## Confidence / maturity

Medium-high for mechanics; low for explanation to a human.

## What remains unanswered

An explanation contract a user can read; multi-hop derived conclusions;
provenance for reasoning outputs.

## Related RQs

RQ-038, RQ-036, RQ-012, RQ-015.

## Related slices

7, 7.1, 15B1, 15B2a, 15B2b-A, 15B2b-B design, B2a.

## Publication notes

Mature for an **architecture article** on "provenance explains authorization,
not truth". Good pairing with the RQ-015 finding.
