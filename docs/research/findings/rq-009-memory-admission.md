# REPO:RQ-009 — What deserves to become durable memory?

> **Namespace (primary-source pass, 2026-09-26).** This finding is filed
> under **REPO:RQ-009** (in-repo register). MASTER equivalent: MASTER:RQ-003 (SEMANTIC MATCH); related MASTER:RQ-101 (memory economics), MASTER:RQ-117 (immune system).
> See the [crosswalk](../rq-register-crosswalk.md).
>
> **Primary-source evidence added:**
> - The REPO hypothesis (score importance, durability, sensitivity, novelty, conflict) largely follows MASTER:RQ-003's original pipeline (observation → candidate → importance → durability → sensitivity → novelty → conflict check → store/reject), carried from the missing Problem Register.
> - S4 (2026-08-24) memory lifecycle: ingest → redact → classify → consent/policy → store → retrieve minimally → expire/delete. Master §04 lifecycle: event → candidate → classify → validate → admit → retrieve → consolidate → revise/forget.
> - Master v1.1 (§R) supersedes S1's "L18 is the sole LTM writer": L18 proposes; L04 owns admission under consent, policy and privacy authority — the model 15A–15B2a implemented.

## Research question

What deserves to become durable memory? (In-repo RQ-009; Master topic
"what deserves to become memory". Related RQ-010 consolidation, RQ-014
retrieval, RQ-017 sensitivity routing.)

## Why it matters to LILITH

Durable memory shapes every later answer. Admitting too much creates
surveillance and poisoning risk; admitting the wrong thing turns noise or
inference into persistent "fact".

## Original hypothesis / problem

Register hypothesis (2026-09-13): admission should **score** importance,
durability, sensitivity, novelty, consent, provenance, and contradiction.

## Architecture explored

The project did not build a scorer. It built an **authority path** that any
admission must pass, and deferred the selection question:

1. **Learning proposes** (L18, [15A](../../architecture/slice-15a-learning-consolidation-foundations-design.md)):
   source events become bounded candidates; `SHADOW_ELIGIBLE` explicitly means
   only "meets infrastructure-proof rules".
2. **LTM admits and stores** (L04, [15B1](../../architecture/slice-15b1-canonical-ltm-foundations-design.md)):
   atomic CREATE/SUPERSEDE/RESTORE with immutable revisions and audit.
3. **Authority gates** ([15B2a](../../architecture/slice-15b2a-canonical-memory-authority-privacy-containment-design.md)):
   actor evidence, payload-bound consent, computed policy, privacy hold,
   closed registry of admissible classes.
4. **Family-neutral apply** ([ADR-0006](../../adr/0006-family-neutral-canonical-memory-apply.md),
   15B2b-A): V1 career proposals and V2 owner-directed proposals share one
   apply bridge.
5. **Owner control** ([15B2b-B design](../../architecture/slice-15b2b-b-owner-memory-control-design.md)):
   the first real class is intended to be owner-directed
   (`OWNER_DIRECTED_PROJECT_CODENAME_V1`, INFERRED), requiring a per-action
   owner WebAuthn proof.
6. **Acceptance is a verifier result** ([B2a](../../architecture/slice-15b2b-b2a-accepted-memory-verifier.md)).

## Experiments / implementation slices

15A (shadow, 3 real source-event candidates), 15B1 (A–P mechanics), 15B2a
(A–DL authority matrix), 15B2b-A (DEV durability probe), B2a (89-case tamper
matrix).

## Evidence

- OPERATIONAL (pre-DEV shadow): 3 `career_events` → 3 valid candidates, 3
  `SHADOW_ELIGIBLE` assessments, `canonicalMemoryMutation=false` (15A).
- TEST: 15B1 CREATE/SUPERSEDE/RESTORE and missing Consent/Verifier/Rollback
  fail closed; 15B2a consent binding, revocation, policy-deny tests.
- DEV: one synthetic item persisted across a service restart, `USER_ASSERTED`
  not promoted, privacy hold suppressed read (15B2b-A).
- PROD DARK: zero canonical rows in 21 tables (15B2b-A); zero production
  classes (15B2a).

## Negative findings / failures

- Zero real admissions have ever happened — by design.
- The scoring hypothesis was **never tested**; the architecture moved instead
  toward owner-directed admission.
- N-35: the application user can currently mint the evidence that authorizes
  admission, so the authority path is not yet isolated.

## Current answer

- **PROVEN (TEST/DEV-synthetic):** admission can be made impossible without
  actor evidence, payload-bound consent, computed policy, registry membership,
  and privacy clearance; replay and partial writes do not create memory.
- **DESIGNED:** the first real memory will be explicitly owner-chosen, one
  closed class, with acceptance decided by a verifier over the full chain.
- **INFERRED:** current evidence supports reframing RQ-009 into two
  questions: *who may authorize* admission (substantially designed and
  test-proven) and *what should be proposed* (untested).
- **HYPOTHESIS:** multi-factor scoring (register) or owner-directed selection
  (current design) — neither evaluated against a labelled corpus.
- **UNKNOWN:** criteria for autonomous consolidation of career or conversation
  data; effect on trust and retrieval quality.

## Confidence / maturity

Mechanics: medium-high (TEST/DEV). Selection criteria: none.

## What remains unanswered

Labelled-corpus comparison of rule, model, and hybrid admission; consent UX;
the 15B1 prerequisites 1–3 and 7 (class, namespace, admissible semantics,
retention).

## Related RQs

RQ-010, RQ-014, RQ-015, RQ-017, RQ-028.

## Related slices

15A, 15B1, 15B2a, 15B2b-A, 15B2b-B design, B2a.

## Publication notes

Mature for a **security/architecture case study**: "separating who may admit
memory from what memory is". Must state that no real memory exists and that
selection criteria are untested.
