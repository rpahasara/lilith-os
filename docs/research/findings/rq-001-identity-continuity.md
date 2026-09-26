# REPO:RQ-001 — Identity continuity across component replacement

> **Namespace (primary-source pass, 2026-09-26).** This finding is filed
> under **REPO:RQ-001** (in-repo register). MASTER equivalent: MASTER:RQ-001 (SEMANTIC MATCH; REPO:RQ-002 and REPO:RQ-003 are MASTER:RQ-001 subquestions); related MASTER:RQ-097, 104, 119.
> See the [crosswalk](../rq-register-crosswalk.md).
>
> **Primary-source evidence added:**
> - S4 (2026-08-24) already stated "LILITH survives any single model, runtime, channel or cloud. Hermes is a reasoning runtime today — not the identity" — two weeks before CA-V1 and three before ADR-0001.
> - Master v1.0/v1.1 (2026-09-14) define the identity invariant (charter, relationship state, autobiographical history, commitments, goals, policy, delegated authority, provenance) and an "identity-critical" state class; MASTER:RQ-001 lists "Create a formal LILITH Identity Invariant Specification" as future work.
> - Master §03 designs identity versioning and narrative identity (derived, revisable, never overwriting primary evidence).
> - Still no charter or invariant-specification artifact exists in any archived source; N-34 stands.

## Research question

What fundamentally makes LILITH the same LILITH after components (model,
runtime, cloud, device, database) are replaced? (In-repo RQ-001; related to
RQ-002 evolution vs replacement and RQ-003 restoration. Master topics:
identity continuity, identity versioning, narrative identity — see the
[numbering reconciliation](../rq-numbering-reconciliation.md).)

## Why it matters to LILITH

LILITH is designed as a persistent governed system above replaceable
substrates. If identity silently lives in a prompt, a runtime process, or a
host, replacing that component forks or erases LILITH without anyone deciding
to.

## Original hypothesis / problem

Register hypothesis (2026-09-13): a versioned identity charter, relationship
history, governed durable state, commitments, policy, and provenance form the
invariant — not a model or runtime. [ADR-0001](../../adr/0001-lilith-identity-above-runtimes.md)
accepted that identity lives above runtimes, while stating it does not claim
the invariant is implemented.

## Architecture explored

- [Cognitive Architecture V1](../../architecture/cognitive-architecture-v1.md):
  the LLM is one replaceable component (L08); identity frame belongs to a
  future Device/Session Sync layer (L19, Slice 16, not started).
- [Principles](../../architecture/principles.md) P-01/P-02.
- [15B2b-B Owner Memory Control design](../../architecture/slice-15b2b-b-owner-memory-control-design.md):
  owner authorization binds only **logical** authority context
  (`deploymentEnvironment`, `authorityDomain`, `logicalOwnerId`
  `owner.ravindu.v1`, `policyVersion`, `ledgerEpoch`) and explicitly excludes
  any VM, machine, instance, broker host, or broker key, so that continuity of
  owner authority survives runtime and cloud replacement.

## Experiments / implementation slices

- Slice 9: reasoning as a tool-less, replaceable component.
- B1b-1: stable logical owner ID `owner.ravindu.v1`, distinct from any OS Login
  access identity.
- B2a: `OwnerMemoryChallengeV2` implements the logical-only field set (TEST).

## Evidence

- DESIGN: ADR-0001, CA-V1, P-01, 15B2b-B design.
- TEST: B2a golden vectors and tamper matrix show the V2 challenge has no host,
  VM, process, broker-key, or charter field, and that V1 and V2 never
  interchange ([B2a record](../../architecture/slice-15b2b-b2a-accepted-memory-verifier.md)).
- OBSERVED absence: 15B2b-B states the repository has **no versioned identity
  charter and no canonical LILITH-system identity identifier**.

## Negative findings / failures

- N-34: P-01 and ADR-0001 depend on a charter that does not exist. The
  identity invariant is currently undefined as an artifact.
- No restoration or replacement test has been run.

## Current answer

- **PROVEN (TEST):** owner-authority context can be bound without any host or
  runtime identifier, and a V2 authorization is rejected if its logical
  context is altered.
- **DESIGNED:** LILITH's identity is intended to be the governed durable state
  and policy above runtimes; owner authority is logical, host facts go to
  provenance only.
- **INFERRED:** current evidence supports *authority continuity* design, not
  *identity continuity*. Owner authority continuity is a necessary but not
  sufficient part of LILITH's identity.
- **HYPOTHESIS:** a versioned charter plus canonical state and provenance is
  sufficient for identity continuity.
- **UNKNOWN:** what the invariant contains; how drift, fork, and restore are
  distinguished (RQ-002, RQ-003).

## Confidence / maturity

Low. Design-level only for the question as posed.

## What remains unanswered

The charter's content and versioning; a minimum-state restoration test;
whether relationship history and affective history are part of the invariant.

## Related RQs

RQ-002, RQ-003, RQ-004, RQ-007, RQ-045.

## Related slices

CA-V1, Slice 9, B1b-1, 15B2b-B design, B2a.

## Publication notes

Mature enough for an **architecture article** on "authority context without
host binding" if framed as design plus TEST evidence. **Not** mature for any
claim that LILITH's identity continuity is solved.
