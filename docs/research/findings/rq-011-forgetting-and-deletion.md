# REPO:RQ-011 — Forgetting, decay, and deletion

> **Namespace (primary-source pass, 2026-09-26).** This finding is filed
> under **REPO:RQ-011** (in-repo register). MASTER equivalent: MASTER:RQ-005 (SEMANTIC MATCH); MASTER:RQ-115 and MASTER:RQ-101 PARTIAL OVERLAP.
> See the [crosswalk](../rq-register-crosswalk.md).
>
> **Primary-source evidence added:**
> - MASTER:RQ-005 proposes lifecycle states ACTIVE, AGING, STALE, SUPERSEDED, ARCHIVED, FORGOTTEN and asks whether forgotten data can return through embeddings or backups.
> - Master v1.1 §R reconciles S1's "supersede, never delete": lineage is retained where permitted, but privacy deletion and retention expiry take precedence, and tombstones must not retain erased content — the principle 15B2a later implemented as Privacy-owned FORGET.
> - PRIVATE HISTORICAL SOURCE — Infrastructure, CI/CD & Operations v1.1 — SHA-256 `d38d6b5ad53485f4631a76f42e3bb3cc50c3201e1d43a2be2b7808755df4ce49` — recovery rules: restoration must not resurrect revoked permissions or deleted memories; derived indexes rebuild only from authorized surviving records.

## Research question

How should memory decay, archive, or be forgotten? (In-repo RQ-011; related
RQ-016 complete deletion and RQ-049 backup/restore. Master topics:
forgetting; forgetfulness contract.)

## Why it matters to LILITH

A persistent personal system that cannot forget is a liability. A system that
"forgets" only in the UI while copies survive in derived stores or backups
misleads its owner.

## Original hypothesis / problem

Register: lifecycle combines time, usage, confidence, validity, importance,
and explicit user intent; important history may be archived rather than
active. RQ-016: deletion must propagate through indexes, embeddings,
summaries, caches, replicas, exports, and backups.

## Architecture explored

- **Belief freshness** (Slice 7/7.1): `STALE` lifecycle and a scheduled sweep;
  stale beliefs keep their value and history.
- **FORGET is a Privacy operation, not a memory edit**
  ([15B2a](../../architecture/slice-15b2a-canonical-memory-authority-privacy-containment-design.md)):
  Privacy is the only FORGET owner; a hold precedes erasure; FORGET is never
  `SUPERSEDE(null)`; every owner must report `COMPLETE`.
- **Restore cannot outrank suppression** (threat-model invariant #10;
  15B2b-A): privacy suppression replay precedes any cognitive restore.
- **Crypto-erasure** (15B2b-B design, PROPOSED): per-item data keys under
  Privacy/broker custody so FORGET also covers backups.

## Experiments / implementation slices

Slice 7.1 sweep; 15B2a acceptance cases AE–AO (forget authorization,
hold-keyed suppression, exact-lineage erasure preserving neighbours);
15B2b-A DEV probe (hold suppressed read and blocked mutation, no legacy
fallback).

## Evidence

- OPERATIONAL (pre-DEV live): a seeded expired belief was marked `STALE` by the
  scheduled tick (7.1).
- TEST: exact-lineage privileged erasure for L04 and L18 V1/V2 (15B2a AL–AO).
- DEV: privacy hold suppressed read and blocked mutation (15B2b-A). The DEV
  cleanup was environment teardown, explicitly **not** a FORGET proof.

## Negative findings / failures

- Career beliefs carry no `expires_at`, so the sweep never stales them (7.1
  known gap); combined with the failing watcher (N-15), stale data can look
  current.
- No decay policy exists for any memory class.
- Backups and derived artifacts are not covered by any implemented erasure.

## Current answer

- **PROVEN (TEST/DEV-synthetic):** a hold can suppress read and mutation
  immediately; erasure can remove exactly one lineage without collateral
  damage; restore order can be forced to replay suppression first.
- **DESIGNED:** FORGET as hold → erasure → all-owner `COMPLETE`; crypto-erasure
  for backups.
- **INFERRED:** current evidence supports "forgetting is an authority
  operation owned outside memory", not a decay heuristic.
- **HYPOTHESIS:** the register's multi-factor decay lifecycle.
- **UNKNOWN:** decay effects on retrieval quality and trust; complete deletion
  across backups and any future embeddings.

## Confidence / maturity

Forget mechanics: medium (TEST/DEV). Decay: none. Complete deletion: low.

## What remains unanswered

A data-lineage map and deletion-verification protocol (RQ-016); TTL policy
for beliefs; a FORGET → backup → restore drill.

## Related RQs

RQ-016, RQ-049, RQ-012, RQ-009.

## Related slices

7, 7.1, 15B2a, 15B2b-A, 15B2b-B design.

## Publication notes

Suitable for a **security case study** on "forgetting as a privacy authority,
not a delete button", provided it states that decay and backup erasure are
unimplemented.
