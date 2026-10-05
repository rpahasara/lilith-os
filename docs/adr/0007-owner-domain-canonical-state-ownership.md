# ADR-0007: Canonical state domains have one controlling semantic owner

- **Status:** Accepted
- **Date:** 2026-10-05
- **Owners:** Project maintainers
- **Related:** ADR-0001, ADR-0002, ADR-0003, ADR-0004, ADR-0006; ledger
  COMP-A, COMP-B, D-3, C-01, C-14, C-21, GOAL-04, LEARN-03; threat-model
  invariants #1, #2, #6, #9; principles P-01, P-02, P-07

## Context

LILITH's accepted ADRs already decide that canonical state sits above
replaceable runtimes (ADR-0001), that durable state has a canonical authority
(ADR-0002), that execution is not verification (ADR-0003), that clients cannot
commit governed effects (ADR-0004), and that for canonical memory L18 may
propose while only L04 may apply (ADR-0006).

None of them states the general rule behind ADR-0006: which component may
*decide* that a given kind of canonical state changes, and what everyone else
may do with that state.

The [Current Architecture & Acceptance Ledger v0.1](../architecture/current-architecture-acceptance-ledger-v0.1.md)
records the effect of that gap (row COMP-A; decision D-3):

- **OBSERVED / DECIDED.** Memory follows the pattern. L18 proposes; L04 alone
  applies (ADR-0006; threat-model invariant #9). The World Model exposes no
  public mutation route.
- **REPORTED.** Personality is recorded as owned by the Hermes runtime file
  `SOUL.md` (Slice 14 §1; Slice 15B1 design), in tension with ADR-0001 (C-01).
- **OBSERVED.** The goal store accepts any `source` from any HTTP caller, with
  no acceptor distinct from the writer (GOAL-04).
- **REPORTED.** The Hermes skills tree and background reviewer are classified
  `LEGACY_EXTERNAL_WRITER`, with no accepted disposition (LEARN-03, C-21).
- **OBSERVED.** Relationship state has no canonical store (REL-01).

The proposed *Integrated Cognitive Architecture & Composition Contract v0.1*
(document 16 of the [contract set](../architecture/cognitive-contracts/v0.1/README.md))
calls this rule the owner-domain principle. That document is PROPOSED / NOT
ACCEPTED, and this ADR does not adopt it. This ADR decides the principle on
repository evidence alone, as the ledger mapped it. It does not rely on the
PDF's clause text.

Without a decision, ownership gets settled case by case, often by whichever
component happens to hold the bytes. That is the failure ADR-0001 rejects for
identity, generalized to every domain.

## Decision

LILITH adopts the **owner-domain principle** as a general architecture rule for
canonical cognitive and durable state.

### Definitions

- **Canonical domain.** A named class of canonical durable state with its own
  meaning and transition rules, such as memory, goals, or authority. A domain
  is a semantic boundary, not a deployment unit.
- **Semantic owner.** The single controlling governance boundary for a
  canonical domain. It defines what the state means, which transitions are
  valid, and what evidence a transition requires. One semantic owner may be
  expressed through several accepted contracts, provided their precedence is
  explicit. Two competing semantic owners for the same domain are forbidden.
- **Proposer.** A component that submits a typed request for a change to a
  domain's canonical state. Proposing grants no change.
- **Acceptor.** The destination domain's governance, which decides whether a
  proposal is admitted.
- **Applier (writer).** The mechanism that commits an accepted transition to
  canonical state, under the owner's contract. It may share code or a process
  with the acceptor.
- **Verifier.** A component that independently checks that an applied
  transition matches its expected state (ADR-0003).
- **Projection / cache.** Any copy, rendering, prompt, index, summary, or
  derived view of canonical state. A projection is never authoritative
  (ADR-0002) and cannot by itself accept or apply canonical state. It may
  serve as attributed evidence or input to a typed proposal to the
  destination domain, which decides under its own governance. A future
  migration or bootstrap from a host file such as `SOUL.md` would take this
  form; whether and how that happens is D-1, which this ADR does not resolve.

### Core rules

- **OD-1.** Every canonical domain has exactly one controlling semantic owner
  (governance boundary). That owner may be represented by multiple accepted
  contracts only if their precedence is explicit. Competing semantic owners
  for one domain are forbidden.
- **OD-2.** A component may read another domain's state only where that
  domain's policy permits.
- **OD-3.** A component may propose a change to another domain only through the
  destination domain's accepted proposal interface.
- **OD-4.** A proposal is never equivalent to acceptance.
- **OD-5.** Only the destination domain's governance determines whether its
  canonical state changes.
- **OD-6.** Cross-reference, retrieval, shared storage, and physical
  co-location do not grant canonical write authority.
- **OD-7.** A cross-domain canonical write path that is not registered under the
  destination owner's contract is denied by default.
- **OD-8.** Acceptance dependencies are acyclic. A domain's acceptance may
  depend one-way on another domain's accepted state or verdict, as L04 apply
  depends on separately governed Policy, Consent, and Rollback authority
  (ADR-0006). No chain of acceptance conditions may lead back to the
  transition it gates, and no domain may accept on another domain's behalf.
- **OD-9.** A model, runtime, provider, prompt or persona file (including
  `SOUL.md`), device, Hsin surface, or database does not become a semantic
  owner because it hosts, renders, transports, caches, or computes over the
  state. Ownership exists only where an accepted record designates it.
- **OD-10.** Semantic ownership grants no action permission, tool authority,
  freshness, currentness, or operational authorization.
- **OD-11.** One process, service, or database may implement several domains,
  provided each domain's semantics, transition rules, and evidence remain
  distinct.
- **OD-12.** A composite operation may coordinate several domains, but each
  domain's accepted transition must remain attributable to that domain's own
  governance.

### Cross-domain proposal flow

```text
source domain / model / runtime
  → typed proposal (destination domain and proposal type bound by the
    interface and/or typed payload; target, provenance, expected head where
    the destination uses revisions)
  → destination proposal interface
  → destination acceptor (destination governance, policy, consent, authority)
  → destination applier (canonical transition)
  → verification / read-back where the consequence warrants (ADR-0003)
```

The destination domain and proposal type must be unambiguously bound, by the
accepted interface itself (for example, an interface that admits only one
domain's proposal type), by typed payload fields, or by both. A redundant
literal destination field is not required where the interface already provides
that binding. The destination must never infer either from ambiguous payload
shape, an identifier prefix, caller identity, or model prose, matching ADR-0006
("family dispatch never infers meaning from an ID prefix"). A request whose
destination or type is not unambiguously bound is not a proposal and is
refused.

Evidence from one domain may *support* a proposal to another. It never
*substitutes* for the destination's acceptance.

### Physical co-location

This ADR does **not** require one service, database, process, schema, or team
per domain. It does not forbid cross-domain reads, cross-domain proposals,
shared storage, coordinated transactions, or composite views.

ADR-0006 is the reference case. In one `BEGIN IMMEDIATE` transaction, L04
commits a canonical memory revision and consumes a separately governed Rollback
authority. Both transitions share a database and a transaction, and each stays
attributable to its own governance. That conforms to OD-11 and OD-12.

### Authority and currentness separation

Authority, freshness, and currentness remain separate governed concerns, owned
by the existing authority records and mechanisms (for example
`owner_freshness`, the recovery admission contracts, and the B1c deployer
boundary). A cognitive domain cannot declare its own authority, freshness, or
currentness (OD-10). Owning a domain's semantics never satisfies an authority
gate, and passing an authority gate never makes a component a semantic owner.

### Runtime, model, and Hsin boundary

This restates ADR-0001 and P-02 for every domain:

- **Models propose.** Model output is proposal or evidence, never acceptance.
- **Hermes and other runtimes orchestrate.** They carry scoped context and may
  submit proposals. They do not own canonical state.
- **Hsin, voice, avatar, and other presence surfaces render.** They may
  implement or render presence and session semantics only under a later
  accepted owner designation for that domain. This ADR designates no owner for
  presence or session state.
- **Prompt and persona files are projections or hosts** unless an accepted
  record designates otherwise (OD-9). Whether `SOUL.md` is canonical or a
  projection is decision D-1, which this ADR does not resolve.

### Failure and default-deny

- An unregistered cross-domain canonical write path is denied by default
  (OD-7). In this ADR "denied" is the design-review outcome. It is not a claim
  that runtime enforcement exists today.
- A domain with no designated owner has no valid canonical writer. A component
  must not assume the role by default.
- If ownership is ambiguous, the transition is refused and the ambiguity is
  recorded for an owner decision. It is never resolved by recency, by the
  writer's convenience, or by model preference.
- An unknown acceptance outcome stays unknown (ADR-0003; P-05). It is never
  read as accepted.

### Examples

| Domain | Allowed | Not allowed |
| --- | --- | --- |
| Memory | L18 proposes memory content. L04 and accepted memory governance decide canonical application (ADR-0006). | A model response becomes accepted memory directly. |
| Personality | Memory supplies evidence for a proposed personality change. | Memory acceptance itself changes personality. A model or prompt-style change is treated as a personality change. |
| Relationship | A remembered interaction is evidence about the relationship. | A remembered interaction directly becomes current consent, trust, or relationship state. |
| Goals | A model or user-intent lane proposes a goal. | A proposal becomes an accepted durable goal without the goal domain accepting it. |
| Learning | Observed success supports a skill or competence proposal. | Success automatically grants capability or tool authority (OD-10). |
| Epistemic | Memory evidence supports a belief update that the World Model's own rules accept. | Memory decides belief or truth state by itself. |
| Hsin | Avatar, voice, and presence render state. | Expression owns identity or changes personality. |
| Authority | Cognitive domains consume authority and freshness verdicts. | A cognitive domain declares its own authority, freshness, or currentness. |

These rows illustrate the rule. For domains other than memory, they do not
designate owners, create stores, or define schemas.

### Exceptions

This rule is general. A domain-specific exception, or a designation of which
component owns a domain, requires a later ADR that names the domain, the
owner, and the reason. An exception may never authorize a host, model,
runtime, or presentation surface to own state merely because it holds that
state (OD-9).

### Non-goals

This ADR does **not**:

- accept any of the 16 proposed PDFs, in whole or in part;
- create schemas, stores, or registries for any domain;
- require microservices, separate databases, or separate processes;
- create personality, relationship, self-model, or skill state;
- designate owners for any domain except by restating ADR-0006 for memory;
- resolve D-1 (`SOUL.md` / personality ownership), D-2 (policy and approval
  boundary), or D-4 through D-9;
- fix or close audit findings G1 or G2;
- authorize B-5, M-B1, PR-1B, First Memory, deployment, migration, activation,
  or any authority or witness transition;
- establish any current live, runtime, host, or authority state;
- disable, migrate, or alter any existing write path.

## Compatibility with accepted ADRs

| ADR | Relationship | Result |
| --- | --- | --- |
| ADR-0001 | ADR-0001 says a runtime "does not become the canonical owner of LILITH identity merely because it performs planning or execution". OD-9 applies the same rule to every domain and to models, devices, prompts, and Hsin. | Agrees; generalizes |
| ADR-0002 | ADR-0002 requires canonical authority per state class. This ADR adds that each class has one *semantic* owner who decides transitions. Its "caches are not silently authoritative" is the projection rule. It leaves topology undecided, as OD-11 does. | Agrees; refines |
| ADR-0003 | Proposer, acceptor, applier, and verifier stay distinct. ADR-0003's "may host both responsibilities only when their contracts remain distinct" is the model for OD-11. | Agrees |
| ADR-0004 | ADR-0004 establishes that client-side policy checks are insufficient as the authoritative boundary for governed capability execution, which must pass through the LILITH control plane. ADR-0007 separately governs semantic ownership and state acceptance; OD-10 keeps the two separate. Neither ADR decides where the authoritative policy and approval boundary sits. | Agrees; orthogonal. D-2 remains unresolved |
| ADR-0005 | Deployment delivers source only and owns no durable state. Under OD-9, a deployment target is not a semantic owner. | Agrees; no interaction |
| ADR-0006 | The instance for memory: L18 proposes, L04 alone applies; typed proposal family; no ID-prefix inference; co-located, single-transaction composite with Rollback authority. | Instantiates; unchanged |

No accepted ADR is superseded or amended. The ADR README rule that changing a
decision requires a superseding ADR is not triggered.

Non-ADR sources:

- `cognitive-architecture-v1.md` (rank 4, target) assigns L19 "authoritative-source
  selection" but also says L19 does not own "the content of any store
  (owners keep it)". The second clause matches this ADR. The first remains
  open as C-07.
- `cognitive-architecture-v1.md` also calls Consolidation the "only writer" to
  Long-Term Memory. That wording was already superseded by ADR-0006 (C-05) and
  does not change here.

## Alternatives considered

### Keep the principle only in the proposed PDFs

The proposed PDFs carry no authority under `docs/README.md`. Each later
decision (D-1, D-5, D-7, D-8) would re-argue ownership from scratch, and
ownership by possession would remain the de facto default.

### Decide ownership domain by domain with no general rule

Each decision would be smaller, but nothing would stop a new domain from
acquiring a host-owner. Reviewers would also have no default to apply when a
cross-domain write appears.

### Physical ownership: one service and database per domain

This gives clear boundaries but contradicts the accepted ADR-0006 composite
transaction. It adds availability and consistency costs with no evidence to
justify them, and it conflates semantic ownership with deployment topology.

### Status quo

Memory stays governed. Personality, goals, skills, and relationships keep
whatever ownership their current host implies. The ledger already records this
as conflict C-01 and C-21 and gap GOAL-04.

## Consequences

### Positive

- One rule explains ADR-0006, the World Model's read-only boundary, and future
  domain decisions.
- D-1, D-5, D-7, and D-8 can be argued against a shared default instead of
  case-by-case precedent.
- Design review gets a clear question: who accepts this transition, and is
  this path registered with that owner?
- Co-location and composite transactions stay explicitly legal.

### Negative and tradeoffs

- Several existing mechanisms are now visibly non-conforming (see below), which
  adds recorded architecture debt without fixing it.
- Every new canonical domain needs an explicit owner designation and proposal
  interface before it can accept writes. That slows ad hoc feature work.
- "Domain" boundaries need judgment. A badly drawn domain can create proposal
  traffic with no benefit.

### Operational and migration impact

No code, configuration, schema, runtime, or deployment change is required to
adopt this ADR. Adopting it creates a conformance yardstick. It does not
change behavior.

Existing mechanisms that would be **non-conforming** once adopted. Each one
stays as-is and is recorded as debt, to be dispositioned by its own decision
or slice:

| Mechanism | Conflict with | Disposition owner |
| --- | --- | --- |
| `SOUL.md` recorded as personality owner (REPORTED; PER-02, C-01) | OD-9 (and ADR-0001) | D-1 |
| Goal create/transition routes accept any caller-asserted `source` with no acceptor distinct from writer (OBSERVED; GOAL-04) | OD-3, OD-4, OD-5 | Ledger R8; D-7 where relevant |
| Hermes skills tree and background reviewer as ungoverned durable writer (REPORTED; LEARN-03, C-21) | OD-7, OD-9 | D-5 |
| One-time device-local → canonical task import (OBSERVED; C-14) | OD-3, OD-5, OD-7 (device-held records enter canonical state without a registered destination proposal interface or a destination acceptance decision); OD-9 secondarily | Later task-store slice |

L18/L04 canonical memory **conforms**: ADR-0006 designates the owner and the
proposal/apply separation.

The World Model is **structurally aligned but partial**. It reconciles
internally and exposes no public mutation route (EPI-02), but no accepted
source explicitly designates its semantic owner. Its rule-based reconciliation
would count as destination governance under OD-5 only once such a designation
exists. Whether its winner rules are correct is D-8, which remains unresolved.

The approval bypass on `/os/drafts` (G2, D-2) is an authority/permission
defect under ADR-0004. Under OD-10 it is outside this ADR.

## Security, privacy, and trust boundaries

- Reduces privilege escalation through state: holding, caching, or rendering
  data never confers the right to change it.
- Makes model and runtime output structurally a proposal. This reinforces
  threat-model invariants #1, #2, and #6.
- Does not weaken any existing authority, consent, privacy-hold, or freshness
  control. Privacy suppression still outranks completeness (ADR-0006).
- Does not by itself enforce anything at runtime. Unenforced paths remain
  exposed until their slices land.

## Validation

Acceptance of this ADR does not prove conformance. Later evidence includes:

- an ownership inventory listing each canonical domain, its designated owner
  (or "undesignated"), its accepted proposal interface, and every known write
  path, with OBSERVED and REPORTED kept separate;
- design-review checks: any new canonical write path names its destination
  owner and proposal type, or is refused;
- for domains given an acceptor, tests showing that a proposal without
  destination acceptance leaves canonical state unchanged. For memory, the
  ADR-0006 tests already cover this;
- negative tests showing that model or runtime output, a projection, or a
  cached copy cannot complete a canonical transition;
- a circularity check showing that no acceptance condition depends,
  directly or transitively, on the acceptance it gates.

## Revisit triggers

- A domain whose semantics cannot be split cleanly enough to name one
  controlling owner.
- Evidence that proposal and acceptance separation imposes unacceptable latency
  on a conversational path (see HX-03), which needs a scoped exception ADR.
  Performance pressure alone never justifies silent cross-domain writes,
  treating a proposal as acceptance, implicit ownership, or authority
  expansion.
- A multi-device or peer-replication model (ADR-0001 and ADR-0002 revisit
  triggers) that changes where acceptance occurs.
- Acceptance of any proposed contract-set clause that defines domain ownership
  differently.

## Open follow-ups

- D-3 is resolved by acceptance of this ADR (2026-10-05). Acceptance does not
  establish conformance of any existing mechanism.
- D-1: classify `SOUL.md` and designate the personality owner.
- D-5: dispose of the Hermes skills tree and background reviewer.
- Goal acceptor and caller authorization (ledger R8), interacting with D-2.
- Relationship-domain owner design under ADR-0001 and ADR-0002 (REL-01).
- Ownership inventory (Validation, first item). This needs no live access for
  repository paths. Runtime-side paths need separate authorization.
