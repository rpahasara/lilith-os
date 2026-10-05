# ADR-0011: Replaceable cognitive execution and governed handoffs

- **Status:** Accepted
- **Date:** 2026-10-05
- **Owners:** Project maintainers
- **Related:** ADR-0001, ADR-0002, ADR-0003, ADR-0004, ADR-0006, ADR-0007,
  ADR-0008, ADR-0009, ADR-0010; ledger D-6, C-09, ADAPT-01..ADAPT-09,
  EVAL-03, EVAL-07, HX-02, PER-04, ACT-03, ACT-05, ACT-06, REC-09, COMP-I,
  COMP-J, R5, R7, R14; principles P-01, P-02, P-05, P-06, P-09, P-11;
  threat-model invariants #2, #5, #6; threats T-10, T-11;
  `docs/architecture/runtime-boundary.md`

## Context

ADR-0001 makes Hermes "a replaceable execution substrate" and says a runtime
"receives scoped task context and authority through an adapter contract".
ADR-0007, ADR-0008 and ADR-0010 then establish that a model, provider or
runtime owns no canonical domain, that changing the model or provider is not
by itself a personality transition, and that accepted procedural competence
survives model, provider and runtime changes. ADR-0009 establishes that
holding or calling a tool confers no authority.

None of them says when choosing a different model, provider or runtime for a
unit of work is only a replaceable read-and-propose choice, and when it
carries something that needs governance. The
[ledger](../architecture/current-architecture-acceptance-ledger-v0.1.md)
records that gap as owner decision **D-6**, conflict **C-09** ("Per-turn
model switching, fail-open, without guarded handoff") and row **ADAPT-06**
(no handoff mechanism; per-turn model switching recorded as "an unguarded
A→B transition").

### Repository evidence

The Router V2 source, the Hermes `gateway/run.py`, the Groq provider plugin,
`SOUL.md`, `social_guard.py` and Hermes named overlays are **not in this
repository** (ledger §2.2, §10.3). Every runtime statement below comes from
patch scripts, module copies and deployment records dated 2026-09-07 to
2026-09-10. It is **REPO RECORD / HISTORICAL / REVALIDATE** and says nothing
certain about the current runtime.

- **REPORTED (patch).** A router lane returns `turn_route`,
  `combined_ephemeral`, `force_rebuild: True` and a `mode`, and evicts the
  per-session cached agent when `getattr(cached_agent, "model", None) ==
  cfg.groq_model` (`slice-8/patch_router.py`). The `run.py` hook discards the
  agent on `force_rebuild` (`slice-9/patch_run.py`).
- **REPORTED (module copies).** Lane agents are built with
  `model=_resolve_gateway_model()` plus per-lane flags:
  `enabled_toolsets=[]`, `max_iterations=1`, `skip_memory=True`,
  `skip_context_files=True`, and `load_soul_identity=True` (Slice 9) or
  `False` (Slice 12 and 13 candidate paths)
  (`slice-9/reasoning.py::reasoning_agent_kwargs`,
  `slice-12/planning.py::planning_agent_kwargs`,
  `slice-13/ethics.py`).
- **REPORTED (design).** The main turn agent is built with
  `enabled_toolsets=ctx.enabled_toolsets`, so "platform tools exposed"
  (`slice-9-reasoning-extraction-design.md` §1). The repository proxy notes
  that "technical turns run tools on the VM"
  (`src/app/api/lilith/conversation/route.ts`).
- **REPORTED (design).** Lanes are fail-open. A lane failure falls through to
  the normal path, which is the tool-exposed main agent
  (`slice-9-reasoning-extraction-design.md` §2; `slice-8/patch_router.py`
  "fully fail-open").
- **REPORTED (design).** A Slice 9 reasoning answer is appended to session
  history "so the turn persists like a normal turn", where any later turn,
  on any route, reads it (`slice-9-reasoning-extraction-design.md` §2).
  Slice 12 plans are ephemeral with no cross-turn lineage
  (`slice-12-planning-design.md` §1); outside a trace they survive only as
  reply text in that history.
- **REPORTED.** Router state is recorded per session
  (`STATE.record(session_key, message, WORK)`) and read by the Social Guard
  (`slice-9/patch_router9.py`, `slice-12/patch_router12.py`,
  `slice-13/patch_router13.py`). Its persistence is UNKNOWN.
- **OBSERVED (repository code).** The browser keeps a stable session id
  (`lilith-os:session-id`) and a transcript in localStorage, and `retry`
  resends the last message on the same session with no operation identity
  (`src/components/conversation/conversation-provider.tsx`). The backend
  relay waits 175 s (`services/core-api/app.py::os_conversation`); the
  Next.js proxy waits 178 s.
- **REPORTED.** Hermes `state.db` sessions and full-text search are
  classified `NON_LTM_INFRASTRUCTURE`
  (`slice-15a-learning-consolidation-foundations-design.md`) and are not
  exposed by the backend (`app.py`, Memory section).
- **REPORTED only; no in-repo source located.** The ledger (§9.2) lists "a
  fallback model" among reply sources.
- **NOT FOUND.** Provider conversation or thread identifiers, server-side
  conversation state, model-native memory, prompt or KV caches, learned
  model-selection preferences, routing scores read back into routing, and
  rate-limit state.
- **UNKNOWN.** The current lane → model → toolset → context map; the
  toolset of the agent on the `groq_model` route; whether a fallback model
  exists and when it fires; whether a timed-out turn keeps running; whether
  the cached agent holds tool-loop state; whether the main agent loads
  `MEMORY.md`, `USER.md`, `state.db` or skills (ADAPT-03); runtime tool
  enforcement (ACT-03, R5).

### What the evidence shows

As recorded, a route never selects only a model. One construction step binds
the model, the effective toolset, the persona flag, the memory and
context-file flags and session handling together. The same step decides
whether the turn may run tools. Treating "which model" as the unit would
miss the dimension that matters most for authority: what the invocation can
actually do. The recorded fail-open path also shows a failure moving a turn
from a zero-tool envelope into a tool-exposed one.

The current agent construction is evidence that an abstraction is needed. It
is not the architecture this ADR adopts.

The proposed *Model / Runtime Adapter & Handoff Specification v0.1* (document
04 of the [contract set](../architecture/cognitive-contracts/v0.1/README.md))
remains PROPOSED / NOT ACCEPTED. This ADR does not adopt it and does not
rely on its clause text. It decides on accepted ADRs and repository evidence
alone. The research charter's handoff notes are RESEARCH / DESIGN and are not
relied on as accepted architecture either.

## Decision

D-6 is answered by classifying every selection of a cognitive engine for a
unit of work against its **cognitive execution envelope**. A selection is
one of:

- a **replaceable reader/proposer substitution**;
- a **governed execution-envelope transition**;
- a **governed handoff**.

Each selection takes exactly one overall classification, the strongest one
that applies, under the classification precedence below. This ADR fixes the
boundary between them. It does not define the routing policy, the capability
policy, the adapter or handoff contract, or any wire format.

### Definitions

- **Cognitive engine.** The model that computes over supplied inputs, with
  the provider that serves it and the runtime that hosts the invocation.
- **Cognitive execution envelope (envelope).** The complete, effective set of
  conditions under which a cognitive engine is invoked for a unit of work.
  An envelope has at least these dimensions:
  1. **Engine:** model, provider, model build or version where known, and
     hosting runtime.
  2. **Effective capability set:** the tools, tool schemas, network, file,
     code-execution, write and external-effect capabilities, and any
     background or autonomous ability, that are actually reachable from the
     invocation.
  3. **Authority context:** any approval evidence, authorization,
     delegation, lease, token or temporary capability the invocation
     carries or relies on.
  4. **Projection inputs:** persona and personality projections, procedural
     skill projections, and policy or system instructions supplied to the
     engine.
  5. **Context inputs:** memory, context files, transcript, grounding,
     working set and other supplied context, with their classification.
  6. **Session handling:** session binding, cached executor state and
     transcript persistence.
  7. **Continuation state:** in-flight or unresolved tool calls, effects
     whose outcome is not yet known, pending operations, and any runtime- or
     provider-held state needed to continue the work correctly.
  8. **Trust route:** the processor or provider that receives the data, its
     destination, and the credential scope, as far as an accepted policy
     makes these relevant.

  "Effective" means what is actually reachable or applied, not what is
  declared. An envelope is a semantic description. It is not a component,
  class, object, process or wire format, and it is not the current
  `AIAgent` construction.
- **Executor.** A cognitive engine running under an envelope.
- **Envelope selection.** Choosing the envelope for a unit of work: per
  turn, per step, on retry or on fallback.
- **Continuity-bearing state.** State whose presence, absence or content
  changes what a continuation means or what LILITH is obliged to do next.
- **Reconstructable.** Obtainable by the next executor from accepted
  canonical state, or from an explicitly classified projection, cache or
  read-only context, without depending on the prior executor.
- **Execution responsibility.** The obligation to complete, reconcile or
  safely abandon work already started, including an effect that may already
  have occurred.

### Core rules

- **CX-1. The envelope is the unit.** D-6 classification applies to the
  envelope, not to the model alone. Two selections with the same model and
  different envelopes are different selections. Two selections with
  different models and otherwise equivalent envelopes may be ordinary
  substitution.
- **CX-2. Engine change is not a self change.** Changing model, provider or
  runtime does not by itself create an identity transition, a personality
  transition (ADR-0008 PERS-10), a procedural-competence transition
  (ADR-0010 SKILL-10), a semantic-ownership transition (ADR-0007 OD-9) or an
  authority transfer (ADR-0009 EB-8).
- **CX-3. Replaceable reader/proposer substitution.** A selection is an
  ordinary substitution only if all of the following hold:
  - no semantic owner changes, and no accepted identity, personality,
    memory, skill or other canonical state changes ownership;
  - no action authority, approval evidence, lease or temporary capability
    transfers to or from the executor;
  - the effective envelope does not differ materially under CX-4; in
    particular, effective tool and capability rights are unchanged;
  - no execution responsibility transfers, including for an effect whose
    outcome is unknown;
  - the next executor needs no non-reconstructable model-, provider- or
    runtime-specific state;
  - every continuity-bearing input the next executor needs is
    reconstructable from accepted state or from an explicitly classified
    read-only projection, cache or context;
  - no hidden provider or runtime state is treated as canonical because it
    exists.

  This is the normal case of dynamic routing. It needs no human approval per
  substitution. A later accepted routing policy may choose automatically
  among envelopes that satisfy CX-3. Satisfying CX-3 grants no capability and
  does not make a route permitted (CX-13).
- **CX-4. Governed execution-envelope transition.** A selection is a governed
  envelope transition when the effective envelope differs materially from
  the envelope otherwise applicable to that unit of work. A material
  difference includes:
  - different effective tool or capability rights;
  - different network, file, code-execution, write or external-effect
    capability;
  - a different trust route where an accepted policy treats the difference
    as relevant;
  - a different projection or context contract where an accepted contract
    places that dimension under governance.

  A governed envelope transition is not by itself a handoff. A fresh unit of
  work with nothing pending may validly start in a different capability
  envelope. The validity of the effective capability set must be
  established by an accepted capability policy or trusted boundary
  (ADR-0009). The selected engine, the runtime, a routing heuristic or the
  envelope description itself cannot establish it:

  ```text
  envelope selected  ≠  tool permission granted  ≠  effect authorized
  ```

  Even within a validly selected envelope, every governed effect still
  crosses its authoritative boundary (ADR-0009 EB-1).
- **CX-5. Governed handoff.** A selection is a governed handoff when
  execution responsibility or continuity-bearing execution state must cross
  from one executor or envelope to another. Triggers include:
  - an active or unresolved tool call;
  - an effect whose outcome is UNKNOWN;
  - a pending action or transaction;
  - an authorization context, lease or temporary capability in use;
  - pending work whose responsibility moves to the next executor;
  - non-reconstructable runtime or provider state needed to continue
    correctly;
  - model- or runtime-local continuation state;
  - durable hidden state on which later semantics depend;
  - in-flight delegated responsibility;
  - any state whose loss would materially change what the continuation
    means.

  A governed handoff requires explicit identification, transfer, fencing and
  reconciliation semantics under a later accepted handoff contract. This ADR
  does not define the protocol.

  Responsibility for an unresolved operation must not be dropped or
  ambiguously duplicated. By default, exactly one executor or envelope is
  accountable for continuing or reconciling it. Concurrent or shared
  responsibility is permitted only under a later accepted coordination
  contract that explicitly defines responsibility, fencing, idempotency,
  effect ownership and reconciliation. This ADR creates no such
  coordination contract and authorizes no multi-executor or ensemble
  execution. Without one, an accidental duplicate retry, or two executors
  each independently treating the same unresolved effect as theirs, is
  forbidden. CX-8 applies unchanged to any effect whose outcome is UNKNOWN.

  CX-5 concerns transferred responsibility and state. A different engine
  alone is not a handoff.
- **CX-6. Fail closed.** If the state a handoff needs cannot be identified,
  transferred, reconstructed or safely abandoned, the continuation is
  refused or the discontinuity is represented explicitly, under the later
  contract. A selection whose class cannot be established is not assumed to
  be CX-3 substitution. Unavailable or unknown classification inputs are
  never read as "nothing to hand off" (P-05; ADR-0007 "Failure and
  default-deny"; ADR-0009 EB-11).
- **CX-7. Fallback never silently widens capability or authority.** Fallback
  from one envelope to another must preserve or reduce effective rights,
  unless a separately valid capability decision under CX-4 authorizes the
  wider envelope. Failure grants no capability. Model or provider
  unavailability grants no capability. Retry or fallback never expands
  authority merely to obtain an answer. Where no envelope within the
  permitted rights can serve the work, the correct outcome is a declared
  limit or refusal, not a wider envelope.
- **CX-8. Unknown effects are not retried by switching engines.** Where an
  executor may already have caused an effect and the outcome is UNKNOWN:
  - another model, provider or runtime is not a clean retry;
  - the request is not replayed because the cognitive engine changed;
  - where a governed operation exists, its stable operation identity is
    preserved (ADR-0002, P-06);
  - the prior outcome is reconciled or verified (ADR-0003), or the work is
    refused, as the applicable effect contract requires.

  Changing the cognitive engine must never be used to bypass UNKNOWN-effect
  semantics or ADR-0009 EB-10.
- **CX-9. Transcript context is not authoritative pending work.**
  Natural-language transcript, including plans, asks and conversational
  commitments, may be supplied to another cognitive engine as continuity
  context. By itself it creates no action permission, delegated authority,
  canonical task, canonical goal, accepted obligation or tool right. A later
  executor reading prior plan text gains no authority to carry it out. If a
  pending operational obligation must survive executor replacement, it
  should be externalized into appropriate typed, governed state under that
  state's owner. This ADR creates no such state and decides no goal
  semantics.
- **CX-10. Held state is not canonical state.** A model, provider or runtime
  may hold ephemeral or non-canonical state. Holding it makes it neither
  canonical nor semantically authoritative (ADR-0002, ADR-0007 OD-9). For a
  selection to remain CX-3 substitution, every piece of state required for
  correct continuation must be one of:
  - reconstructable from accepted or canonical state;
  - an explicitly classified projection or cache;
  - explicitly transferred under an accepted handoff contract.

  Unknown hidden state that is needed to preserve semantics disqualifies a
  selection from being assumed CX-3 substitution. ADR-0010 SKILL-13 applies
  this to procedural skill; CX-10 states it for every envelope dimension.
- **CX-11. Projections stay projections.** Different projection inputs or
  model-native styles across envelopes do not create personality ownership
  or a personality transition (ADR-0008 PERS-5, PERS-6, PERS-10). A later
  accepted envelope contract should state which projections and context a
  route requires. This ADR does not define that contract and makes no claim
  that the recorded `load_soul_identity` differences conform.
- **CX-12. Skills stay above the runtime.** Runtime skill artifacts confer
  no handoff authority and are not handoff state by default. If a future
  handoff needs a procedural-skill projection or cache, it must derive from
  accepted Procedural Skill state under ADR-0010.
- **CX-13. Equivalence does not permit a route.** Reader/proposer equivalence
  under CX-3 does not imply that a route is permitted. A provider change does
  not by itself create an identity or personality transition or imply a
  handoff. It may independently fall under a privacy, security or
  model-route policy, because processor, retention, residency, logging,
  credentials or trust boundary may differ. A separate accepted policy may
  forbid or constrain a route that satisfies CX-3. This ADR defines no such
  policy.
- **CX-14. Discontinuity is represented, not masked.** Canonical continuity
  is determined by governed state and ownership boundaries, not by model
  sameness. A cognitive-engine change may change wording, reasoning style,
  latency, creativity and model-specific strengths without a personality or
  identity transition. A material loss of required continuity state must
  not be hidden behind a stronger persona prompt or other projection. Where
  required state cannot be reconstructed or carried safely, the system
  represents the discontinuity or refuses the continuation, under a later
  contract.
- **CX-15. No owner designation.** Classifying a selection designates no
  semantic owner. In particular this ADR designates no owner for session or
  presence state, which ADR-0007 left undesignated, and no owner for
  routing.
- **CX-16. Conformance rule only.** Acceptance of this ADR creates a
  classification and conformance rule. It does not establish that any
  current route, fallback, toolset, session mechanism or deployment
  conforms, and it grants no tool, capability or action authority.

### Classification precedence

Each selection is classified once, by the strongest applicable class, in
this order:

1. If execution responsibility or continuity-bearing execution state must
   cross executors and CX-5 applies, the selection is a **governed
   handoff**.
2. Otherwise, if the effective cognitive execution envelope changes
   materially under CX-4, it is a **governed execution-envelope
   transition**.
3. Otherwise, it is a **replaceable reader/proposer substitution** under
   CX-3.

This is classification precedence, not implementation code. A
cognitive-engine change may occur within any of the three classes, and the
overall transition takes the strongest classification that applies. A
governed handoff into a materially different envelope must also meet CX-4's
requirement that the destination envelope be established as valid by an
accepted capability policy or trusted boundary. A capability or authority
difference cannot be reclassified as ordinary model selection. A model,
provider or runtime change alone does not make a selection a handoff, and a
selection that reaches step 3 needs no human approval per turn. Where the
inputs to steps 1 or 2 cannot be established, CX-6 applies and the selection
is not assumed to reach step 3.

### Summary

```text
(strongest applicable class wins: CX-5, then CX-4, then CX-3)

same governed state + equivalent effective envelope + nothing in flight
    → replaceable reader/proposer substitution (CX-3; no per-turn approval)

materially different effective envelope (capability, authority, governed
trust route or governed projection/context)
    → governed execution-envelope transition (CX-4; validity from accepted
      capability policy or boundary, never from the engine)

execution responsibility or continuity-bearing execution state must cross
    → governed handoff (CX-5; explicit transfer/fencing/reconciliation under
      a later contract; fail closed per CX-6)
```

### Historical implementation disposition

The Router V2, Groq-route, fail-open and toolset records cited in Context
remain **REPO RECORD / HISTORICAL / REVALIDATE**. They are not edited. Read
against this ADR, they describe:

- per-turn agent eviction and rebuild across engines, which this ADR
  classifies by envelope rather than by model;
- lane envelopes with zero tools and a main envelope with platform tools,
  which are materially different effective capability sets (CX-4);
- a fail-open path from the zero-tool envelope to the tool-exposed one,
  which would be a capability-widening fallback under CX-7 unless a valid
  capability decision covered it;
- shared session history carrying plan and reply text across routes, which
  is continuity context under CX-9, not authoritative pending work.

This ADR does not claim that any of these behaviours occurs live today.
Current live conformance is UNKNOWN.

### Non-goals

This ADR does **not**:

- grant any tool, capability, approval or bounded autonomous authority;
- authorize any live routing, model, provider, toolset, fallback or session
  change, or any contact with a live provider, runtime or router;
- define the routing policy, the capability policy or effective-right
  manifest, the privacy or model-route policy, the adapter contract or the
  handoff protocol or wire format;
- designate an owner for session, presence or routing state;
- create task, goal, relationship, consent, obligation or skill state;
- decide D-7 (goal reopen), D-8 (World Model winner rules) or D-9 (proposed
  source acceptance);
- accept the Model / Runtime Adapter & Handoff Specification or any other
  proposed PDF, in whole or in part;
- reopen D-5 or change ADR-0010's classification of runtime skill state;
- close G1 or G2, or resolve ACT-01, ACT-06, C-02 or R1;
- authorize R5, R6, R14 or the RQ-045 shadow evaluation;
- change B-5 (WITHHELD), FRESHNESS (UNKNOWN), M-B1 or First Memory (NOT
  AUTHORIZED), or the substrate-drift policy (OPEN);
- establish any current live, runtime, host, routing or authority state.

## Compatibility with accepted ADRs

| ADR | Relationship | Result |
| --- | --- | --- |
| ADR-0001 | Hermes is "a replaceable execution substrate" receiving scoped context and authority "through an adapter contract". CX-1..CX-3 say when replacement stays ordinary. The adapter contract is still missing (ADAPT-02); CX-5 and CX-11 name what it must later cover | Agrees; refines |
| ADR-0002 | "Caches are not silently authoritative" is CX-10. Stable operation identities carry into CX-8 | Agrees |
| ADR-0003 | UNKNOWN and partial outcomes are first-class and blind retry is unsafe. CX-8 applies this to engine changes | Agrees; applies |
| ADR-0004 | Governs clients. CX rules address runtimes and executors. No overlap | Orthogonal |
| ADR-0005 | Deploying a router or model configuration is not activation and confers no envelope validity | No interaction |
| ADR-0006 | Model payloads cannot activate canonical memory. Memory is model-independent, so a CX-3 substitution never transfers it | Agrees |
| ADR-0007 | OD-9 (no host ownership), OD-4 (proposal ≠ acceptance) and OD-10 (ownership ≠ permission) underlie CX-2, CX-9 and CX-10. Session and presence owners stay undesignated (CX-15) | Agrees; applies |
| ADR-0008 | PERS-10 is CX-2 for personality; PERS-5, PERS-6 and PERS-9 underlie CX-11. The HX-02 projection-consistency framing is unchanged | Agrees |
| ADR-0009 | EB-8 (tool possession confers no authority), EB-9 (no bypass), EB-10 (retry and replay cannot widen authorization or duplicate effects) and EB-11 (unknown fails closed) underlie CX-4, CX-7 and CX-8 | Agrees; applies |
| ADR-0010 | SKILL-10 and SKILL-11 (competence survives runtime change) and SKILL-13 (non-canonical artifacts do not act as competence) underlie CX-10 and CX-12. Its revisit trigger "A D-6 outcome that treats runtime skill state as handoff state" is not met: CX-12 keeps runtime skill state out of handoff authority | Agrees; does not trigger revisit |

No conflict with an accepted ADR was found. No accepted ADR is amended or
superseded.

Non-ADR sources:

- `cognitive-architecture-v1.md` (rank 4, target) gives L08 Reasoning "model
  selection" and L19 "session handoff" and "authoritative-source
  selection". This ADR assigns neither to a layer. C-07 is unchanged.
- `runtime-boundary.md` lists "time, cost, model, and retry budgets", a
  "capability allowlist" and a "delegation envelope" among what a runtime
  receives, as an illustrative envelope. The cognitive execution envelope is
  consistent with it and does not make it a contract.

## Interaction with unresolved items

| Item | Relationship |
| --- | --- |
| D-7, D-8 | Independent. Not decided here |
| D-9 | Independent. This ADR does not route PDF 04 clauses to acceptance |
| G1 | Independent |
| G2, ACT-01, C-02, R1 | Unchanged. A route rule cannot fix bypassable write routes |
| ACT-03, ADAPT-05, R5 | Conformance depends on a separately authorized runtime tool inventory |
| ACT-05, ACT-06, REC-09, COMP-J | Conformance debt for CX-8 (no UNKNOWN effect state; idempotency replay without payload binding) |
| ADAPT-02, ADAPT-07, ADAPT-08 | The later envelope and handoff contract |
| R6, R14 | Input: projection and skill inventories may reveal envelope dimensions |
| EVAL-03, RQ-045, PER-04 | Validation |

## Alternatives considered

### Treat the model as the unit

This matches the D-6 wording but not the evidence. As recorded, the
toolset, persona flag and context flags change with the route. A model-only
rule would call a switch from a tool-less lane to a tool-exposed agent
"the same kind of change" as two equivalent models.

### Treat every route change as a handoff

Safe on paper, but it would make ordinary dynamic routing a governed event
on every turn, invite approval fatigue, and blur the case that needs
transfer semantics (responsibility in flight) with the many that do not.

### Treat every capability difference as a handoff

A fresh unit of work with nothing in flight has nothing to hand off. Its
risk is capability, which ADR-0009 already places under policy and
boundaries. Calling it a handoff would build transfer machinery for a
problem that is about permission.

### Adopt the proposed handoff state machine

PDF 04 is not accepted, and D-9 has not routed it to acceptance. Adopting
its clause text here would accept a proposed source by side effect.

### Status quo

Per-turn routing stays fail-open and unclassified (C-09). Fallback can widen
capability without any rule saying it should not, and transcript text
remains the only carrier of cross-model obligations.

## Consequences

### Positive

- Dynamic routing among equivalent envelopes stays cheap and needs no
  per-turn approval.
- Capability differences and responsibility transfers get named, separate
  treatments.
- Fallback and retry have a rule that stops them from becoming silent
  privilege escalation or duplicate effects.
- Accepted personality, skill and memory continuity rules extend cleanly to
  engine changes.

### Negative and tradeoffs

- Classification needs envelope information the repository does not have
  today (Context, UNKNOWN). Until it exists, CX-6 makes many selections
  "not assumed substitution".
- A fail-closed fallback can produce refusals where a wider envelope would
  have answered.
- Three later artifacts are needed before the rule can be enforced.

### Operational and migration impact

None. No code, configuration, router, runtime, provider, prompt or
deployment change follows from this ADR. Repository evidence does not show
whether the following occur today. Each would be non-conforming if observed
later:

- a fallback that moves work into a wider capability envelope without a
  separate valid capability decision;
- a retry on another engine after a possibly effectful turn, without
  reconciliation;
- transcript text acted on as authorization or accepted obligation;
- hidden runtime state treated as canonical to preserve continuity.

## Security, privacy, and trust boundaries

- Treats the effective capability set, not the model name, as the
  security-relevant fact about a route (P-09).
- Closes failure-driven privilege escalation at the architectural level
  (CX-7). It does not enforce anything at runtime.
- Keeps transcript content as untrusted context. Embedded plans or
  instructions bind no later executor (CX-9; threat-model invariant #1).
- Leaves provider privacy, retention, residency, logging and credential
  scope to a separate policy (CX-13; P-11; threat-model data-flow
  placeholders). Satisfying CX-3 never answers those questions.
- Weakens no existing authority, consent, privacy-hold, containment or
  freshness control.

## Validation

Acceptance proves no conformance. Later evidence includes:

- a separately authorized read-only envelope inventory answering at least:
  1. the current route → engine → effective toolset → context and projection
     map, including the `groq_model` route;
  2. whether a fallback engine exists, its triggers, and whether it can fire
     mid-turn or after a tool call;
  3. whether router session state persists and what reads it;
  4. whether cached executor state can hold tool-loop or continuation state;
  5. what the main agent loads into context (ADAPT-03);
  6. whether any provider holds server-side conversation state or caches;
  7. whether a timed-out turn keeps running, and what a client retry does;
  8. whether the route or envelope is recorded with resulting effects;
- tests that a fallback cannot reach a wider capability set without a valid
  capability decision;
- tests that a turn with a possibly applied effect is not replayed on another
  engine without reconciliation;
- negative tests that transcript text cannot create a task, goal, approval or
  tool right;
- the RQ-045 two-model shadow evaluation and a model-swap no-change probe
  (EVAL-03, PER-04), under separate authorization.

## Revisit triggers

- Evidence that a provider holds durable server-side state that later
  semantics depend on.
- A capability policy that binds rights to engines rather than to envelopes.
- A multi-runtime or multi-device design that runs executors concurrently on
  one unit of work.
- Acceptance of any proposed adapter or handoff clause that draws the
  boundary differently.
- Evidence that the three classes cannot be distinguished in practice.

## Open follow-ups

- D-6 is resolved by owner acceptance of this ADR (2026-10-05).
  Replaceable reader/proposer substitution, governed execution-envelope
  transition and governed handoff are distinct classes, and the strongest
  applicable classification wins (CX-5, then CX-4, then CX-3). Acceptance
  resolves the architectural boundary only. It establishes no implementation
  and no conformance of any existing route, fallback, toolset, session
  mechanism or deployment. The Router V2, Hermes and Groq-route records stay
  HISTORICAL / REVALIDATE, and current live conformance is UNKNOWN.
  Acceptance authorizes no live model or provider switch, router, runtime,
  capability or toolset change, failover experiment, deployment or
  activation, and no R5, R14 or RQ-045 execution. It creates no coordination
  contract and no multi-executor authority.
- Execution-envelope and handoff adapter contract (ADAPT-02, ADAPT-07,
  ADAPT-08).
- Capability policy and effective-right manifest (with R5 and ACT-03).
- Privacy and model-route policy (P-11; threat-model data-flow review).
- Conformance inventory and validation (Validation above; R7, RQ-045).

## Hidden-assumption review

What could make this design look correct while it is wrong?

- **The records describe today's router.** They are HISTORICAL (2026-09).
  Nothing current was inspected.
- **Equal model names mean equal envelopes.** They do not (CX-1).
- **A tool-less engine is harmless wherever it runs.** Its output can still
  be persisted as context that a tool-exposed executor later acts on (CX-9).
- **Shared transcript is continuity.** It is context. It is not canonical
  state, and it exists only inside one runtime.
- **Providers hold no state.** Not found is not absent. Provider-side state
  is UNKNOWN.
- **Fallback is always safer.** Only if it does not widen rights (CX-7).
- **A stable voice shows a stable self.** It does not (CX-14; ADR-0008).
