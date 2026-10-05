# ADR-0008: Canonical personality is owned above runtimes; `SOUL.md` is a runtime projection

- **Status:** Accepted
- **Date:** 2026-10-05
- **Owners:** Project maintainers
- **Related:** ADR-0001, ADR-0002, ADR-0003, ADR-0007; ledger D-1, C-01,
  C-11, ID-01, ID-08, ID-09, PER-01, PER-02, PER-03, PER-04, PER-06, META-02,
  HSIN-10, HX-02, R6; principles P-01, P-02, P-12

## Context

`SOUL.md` is a prose persona file loaded by the Hermes runtime. The owner
created it as a **temporary** Hermes-side description of how LILITH should
generally speak and behave. It was meant to keep a recognizable style during
early development, while no governed personality architecture existed. It was
never meant to be LILITH's identity, canonical personality state, the semantic
owner of personality, or an authority source.

Repository records nonetheless describe it as an owner:

- **REPORTED.** Slice 14 design §1, "Corrected ownership map", lists
  `/home/lilith/.hermes/SOUL.md` as the "Authoritative owner" of "Base
  identity/personality" (`slice-14-social-cognition-presence-design.md`).
- **REPORTED.** Slice 15B1 design, governing invariant: "SOUL remains the
  personality owner" (`slice-15b1-canonical-ltm-foundations-design.md`).
- **REPORTED.** Slice 14 design §1 lists Hermes `hermes_cli/personality.py` as
  the owner of "Named personality overlays".
- **REPORTED (record copies).** The Hermes main agent is built with
  `load_soul_identity=True` (`slice-9-reasoning-extraction-design.md` §6;
  `slice-9/reasoning.py`; asserted by
  `slice-14/test_social_presence.py::test_run_keeps_load_soul_identity_true`).
  Planning and Ethics LLM candidate calls use `load_soul_identity=False`.
- **REPORTED.** Deployment records for Slices 14, 15A, 15B1 and 15B2a pin
  `SOUL.md` at SHA-256 `d082db5a…5ccd` and state that SOUL was not changed.
- **OBSERVED.** `SOUL.md` itself is not in the repository. Its content, its
  write routes, and whether the runtime can write it are UNKNOWN (ledger
  PER-03, PER-08).
- **OBSERVED.** No canonical personality state, schema, store, proposal
  interface or acceptor exists in the repository (ledger PER-02, PER-03,
  PER-07). Slice 14 states "There is no `PersonalityProfile`".
- **OBSERVED.** The DEV durability probe treats `SOUL.md` as a legacy Hermes
  target, alongside `MEMORY.md`, `USER.md` and the skills tree
  (`scripts/run_core_api_dev_durability_probe.py::LEGACY_TARGETS`).

The [ledger](../architecture/current-architecture-acceptance-ledger-v0.1.md)
records this as conflict C-01 against ADR-0001, P-01 and P-02, and as owner
decision D-1. ADR-0007 has since made the conflict explicit: a prompt or
persona file "including `SOUL.md`" does not become a semantic owner because it
hosts or renders state (OD-9), and ownership exists only where an accepted
record designates it. ADR-0007 deferred the classification of `SOUL.md` to
D-1.

The proposed *Personality Evolution Specification v0.1* and *Identity
Invariant Specification v0.1* remain PROPOSED / NOT ACCEPTED. This ADR does
not adopt them and does not rely on their clause text. It decides D-1 on
accepted ADRs and repository evidence alone.

## Decision

### Definitions

- **Canonical personality.** LILITH's accepted, stable tendencies,
  preferences, interaction patterns, style-related dispositions, and their
  development over time, held as governed state above any runtime.
  Personality here means stable self-level tendencies across contexts; it
  excludes current affect/mood, relationship-specific state, user
  preferences, goals/commitments, and model-native style.
- **Personality domain.** The canonical domain (ADR-0007) whose state is
  canonical personality. It is a semantic boundary, not a service, database,
  process or schema.
- **Runtime persona projection.** A runtime-side artifact or configuration
  that is derived from, or intentionally conveys, personality semantics to a
  consumer, such as a persona file, a persona-bearing system or provider
  prompt, or a named overlay. Voice and avatar configuration is included only
  to the extent that it is personality-relevant; purely presentational voice
  or avatar settings are not personality projections. A runtime persona
  projection is a projection in the ADR-0007 sense.
- **Expression.** What a consumer actually produces: wording, tone, voice,
  appearance. Expression is output, not state.

### What `SOUL.md` is

`SOUL.md` is a **temporary Hermes runtime persona projection**. It is
runtime-side, replaceable, non-canonical and non-authoritative. It may guide
expression. It may later serve as attributed bootstrap evidence.

It is **not** LILITH's identity, canonical personality state, the semantic
owner of personality, an authority source, evidence that a personality
transition was accepted, or evidence of continuity by itself.

```text
TEMPORARY OPERATIONAL PROJECTION  ≠  CANONICAL PERSONALITY STATE
```

### Core rules

- **PERS-1.** Canonical personality is a distinct LILITH semantic domain above
  replaceable models, runtimes, devices and presentation layers.
- **PERS-2.** The Personality domain is the single semantic owner and
  governance boundary for canonical personality (ADR-0007 OD-1). This ADR
  designates the domain and its owner boundary only. It designates no service,
  database, process, schema, acceptor mechanism or proposal interface.
- **PERS-3.** `SOUL.md` is a temporary Hermes runtime persona projection, not
  canonical personality state.
- **PERS-4.** `SOUL.md` is not identity. It cannot own identity or establish
  identity continuity.
- **PERS-5.** A runtime persona projection may influence rendering and
  expression. It cannot accept or apply a canonical personality transition.
- **PERS-6.** Edits to `SOUL.md`, named overlays, provider prompts, model system
  prompts, voice configuration or avatar behavior do not by themselves
  constitute accepted personality evolution.
- **PERS-7.** Existing `SOUL.md` content may later be used as attributed source
  evidence for a typed personality proposal. It is never promoted to
  canonical personality automatically.
- **PERS-8.** Once canonical personality mechanisms exist, runtime persona
  artifacts may be generated from accepted personality state plus explicitly
  scoped runtime or expression overlays.
- **PERS-9.** A projection may omit permitted personality state, or transform
  its representation (for example, compress or reformat it) for a consumer.
  It must not alter the underlying semantics. A projection must not silently
  change personality meaning, broaden the scope of what it conveys, feed back
  into canonical personality state, or become canonical.
- **PERS-10.** Changing model, runtime, provider, device, prompt, voice or
  avatar does not by itself create a personality transition.
- **PERS-11.** Personality semantic ownership grants no action permission, tool
  authority, freshness, currentness, identity authority or operational
  authorization (ADR-0007 OD-10).
- **PERS-12.** Until canonical personality state is implemented, its absence
  stays explicit. The current `SOUL.md` projection must not be relabeled as
  canonical to fill the gap.

### No valid canonical writer yet

Under ADR-0007, a canonical write path that is not registered under the
destination owner's contract is denied by default (OD-7). This ADR registers
no proposal interface, acceptor or applier. Therefore, after acceptance,
**no component is designated or authorized by accepted architecture to accept
or apply canonical personality transitions**, and any such write path is
denied by default under OD-7. This is an architecture statement. It makes no
claim about uninspected live runtime state.
Designating the semantic owner does not authorize any component to start
writing personality state. That requires a later accepted design.

### Temporary-runtime status and lifecycle

**Phase A — current / temporary.** No canonical personality state is
established by accepted architecture or repository evidence.
`SOUL.md` may remain the Hermes runtime persona projection for user-facing
expression. It is operationally useful and non-canonical. During this phase:

- edits to `SOUL.md` are not canonical personality evolution;
- Hermes or runtime changes to it create no accepted personality state;
- copying it between runtimes proves neither identity nor personality
  continuity;
- a model behaving similarly because it receives the same `SOUL.md` does not
  prove that canonical personality is unchanged;
- runtime survival of `SOUL.md` does not make it the owner of personality.

**Phase B — bootstrap / migration.** A later governed personality mechanism may
examine existing `SOUL.md` content as attributed historical or bootstrap
evidence. Nothing enters canonical personality automatically.

**Phase C — future governed projection.** Accepted personality state becomes
the source for runtime persona projections. Hermes may receive a generated
`SOUL.md` or an equivalent artifact. That projection stays replaceable and
non-authoritative.

This ADR implements none of these phases. It authorizes no transition between
them.

### Projection and bootstrap flow

```text
historical / temporary SOUL.md
  → attributed source evidence (source, digest, capture time, author where known)
  → typed personality proposal
  → Personality-domain governance (acceptor; ADR-0007 OD-3..OD-5)
  → accepted canonical personality state
  → runtime projection(s), possibly including a generated SOUL.md
```

The destination Personality domain decides what, if anything, is accepted.
Old content is not presumed accurate because it is old, and it is not
presumed complete because it is the only source. Bootstrapping is a proposal,
not an import. This ADR does not define the proposal schema.

### Identity and personality separation

Identity is governed above runtimes under ADR-0001. Personality is a separate
semantic domain. The two are not interchangeable:

```text
identity     ≠ personality
personality  ≠ current mood / affect
personality  ≠ relationship state
personality  ≠ prompt style or model-native style
personality  ≠ SOUL.md
personality  ≠ voice or avatar
```

The Personality domain owns no identity semantics. Personality evidence never
validates identity. A matching personality projection never substitutes for
identity verification. Relationship and affect ownership are outside this
ADR.

### Model, runtime and provider boundary

Models propose, runtimes orchestrate, and projections render (ADR-0007).
Model-native style is a property of the substrate. It is not personality.
Output that resembles LILITH, or a model rewriting `SOUL.md`, is at most
evidence for a proposal. It is never acceptance. Per-turn model routing under
one shared `SOUL.md` (HX-02) is a projection-consistency question, not
evidence that canonical personality is preserved.

### Expression boundary

Hsin, voice, avatar and text style render expression. They may consume a
personality projection. They do not define personality, and expression
consistency is presentation continuity, not an identity or personality
oracle (ledger HSIN-10, ID-08).

### Authority and currentness separation

Owning personality semantics satisfies no authority gate. Passing an
authority gate never makes a component the personality owner. Personality
cannot declare its own freshness or currentness (ADR-0007 OD-10).

### Non-goals

This ADR does **not**:

- implement canonical personality, create `PersonalityStateV1`, a trait
  ontology, a store, a schema, a proposal interface or an acceptor;
- accept the Personality Evolution or Identity Invariant PDFs, or any other
  proposed PDF, in whole or in part;
- delete, rewrite, move or regenerate `SOUL.md`;
- change Hermes, `load_soul_identity`, named overlays, model or provider
  routing, prompts, voice or avatar behavior;
- inspect or assert anything about the live Hermes runtime;
- resolve C-11 (CA-V1 L11 layer split), relationship or affect ownership,
  D-2, or D-4 through D-9;
- close G1 or G2;
- authorize B-5, M-B1, PR-1B, First Memory, deployment, migration, activation,
  or any authority or freshness transition.

## Compatibility with accepted ADRs

| ADR | Relationship | Result |
| --- | --- | --- |
| ADR-0001 | ADR-0001 places identity and canonical state above runtimes and rejects identity living "implicitly in one runtime's prompt". Classifying `SOUL.md` as a runtime projection applies that rule. ADR-0001 requires runtime-private state to be "migrated or classified as cache". This ADR classifies it as a projection now and defers migration to Phase B. | Agrees; resolves C-01 for personality once accepted |
| ADR-0002 | Canonical state has a canonical authority, and "caches are not silently authoritative". `SOUL.md` is classified as a non-authoritative projection. Topology stays undecided. | Agrees |
| ADR-0003 | Similar output from the same `SOUL.md` is executor-side self-report, not independent evidence that personality is unchanged. | Agrees |
| ADR-0004 | Governs client capability execution. Personality ownership grants no capability authority (PERS-11). | Agrees; orthogonal |
| ADR-0005 | Deployment carries source only. Deploying or pinning `SOUL.md` makes it no owner. | Agrees; no interaction |
| ADR-0006 | Memory may later supply evidence for a personality proposal. Memory acceptance does not change personality (ADR-0007 examples). | Agrees; no interaction |
| ADR-0007 | OD-9 names `SOUL.md` and forbids host-based ownership. The projection definition allows attributed bootstrap evidence. The Exceptions section requires a later ADR to designate a domain owner; this ADR is that designation for personality, at semantic level only. | Instantiates for personality |

No accepted ADR requires `SOUL.md` to remain an owner. No accepted ADR is
superseded or amended.

## Historical wording disposition

These records are not edited or deleted. They remain accurate evidence of what
the runtime design said and did at the time. Once this ADR is accepted, they
are not the controlling ownership rule (`docs/README.md` precedence: accepted
ADRs outrank current-state and slice records).

| Record | Wording | Disposition after acceptance |
| --- | --- | --- |
| `slice-14-social-cognition-presence-design.md` §1 | "Base identity/personality — Authoritative owner: `/home/lilith/.hermes/SOUL.md`" | Historical runtime record. Superseded for architectural interpretation by PERS-3/PERS-4. Read as "the runtime file that projected persona at the time" |
| `slice-14-social-cognition-presence-design.md` §1 | "Named personality overlays — Authoritative owner: Hermes `hermes_cli/personality.py`" | Historical runtime record. Overlays are runtime persona projections (PERS-6) |
| `slice-14-…-design.md` header; `slice-14/DEPLOYMENT-RECORD.md` | "SOUL/personality expresses" | Compatible. Expression is the projection's role |
| `slice-15b1-canonical-ltm-foundations-design.md` | "SOUL remains the personality owner" | Historical design record. Superseded for architectural interpretation by PERS-2/PERS-3 |
| `slice-9-reasoning-extraction-design.md` §6; `slice-9/reasoning.py`; `slice-14/test_social_presence.py` | `load_soul_identity=True`; persona shapes only wording | Compatible. Loading a projection to shape wording is permitted in Phase A. The Hermes identifier `load_soul_identity` is a runtime name, not an architecture claim |
| Deployment records (Slices 14, 15A, 15B1, 15B2a) | `SOUL.md` hash pins; "SOUL not changed" | Compatible. Evidence that a runtime file was protected, not of ownership or continuity |
| `cognitive-architecture-v1.md` L11 | "Owns: persona/voice/norms; relationship model …" | Not resolved here (C-11). Persona config held by any layer is a projection under this ADR |

Reconciling these documents' wording is documentation debt (ledger R11). It
is not a precondition of this ADR.

## Alternatives considered

### `SOUL.md` is canonical personality

This is what the recorded wording implies. It contradicts ADR-0001 and
ADR-0007 OD-9. It ties personality to one runtime's private file, it lets
untracked edits count as personality change, and it has no acceptor distinct
from the writer. It also contradicts the owner's stated intent.

### Delete or freeze `SOUL.md` now

This would remove the only current source of a recognizable runtime style,
with no replacement. It would also discard useful bootstrap material.
Classification removes the ownership problem without the operational loss.

### Import `SOUL.md` wholesale as initial canonical personality

This is fast, but it presumes old prose is accurate, complete and accepted.
It would turn a projection into canonical state by relabeling, which PERS-12
and ADR-0007 forbid.

### Make personality part of the identity domain

This would merge two domains that change at different rates and need
different evidence. It would let personality drift read as identity change,
and identity checks read as personality checks.

### Status quo

C-01 stays unresolved. Every later personality design would have to argue
around a recorded runtime owner.

## Consequences

### Positive

- C-01 has a decided disposition for personality, consistent with ADR-0001
  and ADR-0007.
- Current runtime behavior keeps working, with an explicit non-canonical
  label.
- Useful `SOUL.md` content is kept available for a governed bootstrap.
- Later personality design starts from a fixed owner boundary, not
  precedent.

### Negative and tradeoffs

- No canonical personality state is established by accepted architecture or
  repository evidence, and no component is designated or authorized by
  accepted architecture as a canonical personality writer. That gap remains
  explicit until a later accepted design establishes the mechanism and its
  evidence.
- Runtime `SOUL.md` edits continue to change expression without any governed
  record. This is accepted for Phase A and remains debt.
- Several historical records now read as stale for architectural purposes.

### Operational and migration impact

No code, configuration, schema, prompt, runtime or deployment change is
required. Repository evidence shows only that Hermes loads `SOUL.md` to shape
wording, which Phase A permits. Repository evidence does **not** show any of
the following. Each would be non-conforming if observed later:

- the runtime treating `SOUL.md` edits as canonical personality transitions;
- personality history kept only in a runtime file while being called
  canonical;
- model or provider output silently rewriting durable personality;
- a runtime replacement using the presence of the same `SOUL.md` as proof of
  identity or personality continuity.

Whether the runtime or a background reviewer can write `SOUL.md` is UNKNOWN
(PER-03, PER-08). Finding out requires a separately authorized inventory
(ledger R6).

## Security, privacy, and trust boundaries

- Treat `SOUL.md` and overlay content as untrusted data when used as bootstrap
  evidence. Instructions inside a persona file never become accepted state or
  instructions to the acceptor.
- A runtime-writable persona file is a potential injection and drift vector.
  This ADR records it. It does not assess or mitigate it.
- Personality evidence derived from memory or conversation stays subject to
  existing privacy and erasure controls. A future generated projection must
  not leak suppressed or erased content.
- Nothing here weakens any authority, consent, privacy-hold or freshness
  control.

## Validation

Acceptance proves no conformance. Later evidence includes:

- an inventory of every personality projection and write route, including
  `SOUL.md` and named overlays, with OBSERVED and REPORTED kept separate (R6;
  runtime access separately authorized);
- once a personality mechanism exists, negative tests showing that a
  `SOUL.md` edit, a model-generated proposal or a projection cannot complete
  a canonical personality transition without Personality-domain acceptance;
- a model-swap probe showing that changing model or provider under the same
  projection creates no personality transition (PER-04, HX-02);
- tests showing that personality evidence never satisfies an identity or
  authority check.

## Revisit triggers

- Evidence that `SOUL.md` carries non-personality operational semantics, such
  as authority or tool instructions the runtime enforces. Those semantics
  require separate classification and a security and conformance review.
  Runtime enforcement does not make `SOUL.md` authoritative or canonical.
- Evidence that the runtime or a background process writes `SOUL.md`. That
  triggers a write-route and drift review. Writability alone does not change
  its classification as a projection or confer ownership.
- Acceptance of a personality or identity specification that draws the
  identity/personality boundary differently.
- A multi-runtime design in which several runtimes need divergent persona
  projections.

## Open follow-ups

- D-1 is resolved by owner acceptance of this ADR (2026-10-05). Acceptance
  establishes no implementation and no conformance of any existing mechanism.
- Personality-domain design: state shape, proposal interface, acceptor,
  bootstrap procedure (Phase B). Informed by, not bound to, the proposed
  Personality Evolution Specification.
- Inventory of `SOUL.md` and overlay write routes (R6, separately authorized).
- C-11: CA-V1 L11 split of persona, relationship model and mood.
- Documentation reconciliation of the historical wording above (R11).

## Hidden-assumption review

What could make this design look correct while it is wrong?

- **One file holds all personality.** False. Named overlays, the Router social
  policy, model-native style and TTS style also shape expression. Each is a
  projection under PERS-6, and the inventory must cover all of them.
- **Old content is accurate.** `SOUL.md` age and hash stability show it was
  unchanged across deployments. They do not show it was correct or endorsed.
  Phase B treats it as evidence only.
- **Stable expression proves stable personality.** It does not (PERS-10,
  ADR-0003). It can equally reflect an unchanged prompt over a changed model.
- **Removing SOUL ownership requires immediate canonical state.** It does not.
  The gap is stated explicitly (PERS-12) and no writer is valid meanwhile.
- **Wholesale migration preserves continuity.** It would relabel a projection
  as canonical. Bootstrap is a governed proposal.
- **Model-native style is personality.** It belongs to the substrate.
- **The Personality owner also owns identity or authority.** It does not
  (PERS-4, PERS-11).
- **Naming an owner authorizes writes.** It does not. Without a registered
  interface and acceptor, OD-7 default-deny applies.
- **The repository records describe today's runtime.** They are HISTORICAL
  (2026-09). The current live `SOUL.md`, its hash and its writers were not
  inspected.
