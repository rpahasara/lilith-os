# ADR-0013: World Model preserves claims and separates epistemic projection

- **Status:** Accepted
- **Date:** 2026-10-05
- **Owners:** Project maintainers
- **Related:** ADR-0001, ADR-0002, ADR-0003, ADR-0007, ADR-0011, ADR-0012;
  ledger D-8, D-9, EPI-03, EPI-06, EPI-07, EPI-11, META-07, MEM-10, C-08,
  C-22, C-23, R4; principles P-04, P-05, P-07, P-12;
  `docs/architecture/slice-7-world-model-backend-spec.md`

## Context

The [Current Architecture & Acceptance Ledger v0.1](../architecture/current-architecture-acceptance-ledger-v0.1.md)
records owner decision **D-8**: "World Model R2/R3 winner rules: keep, or
replace with preserved conflict?". Row EPI-07 records a CONFLICT over
whether incompatible claims are preserved or resolved by a recency or
authority winner. Conflict C-23 records "Recency/authority winner rules;
repeat clears CONFLICTED", with "Tested repo behavior until decided".

R2 and R3 are repository design. Their only source is §9 of the
[Slice 7 World Model backend spec](../architecture/slice-7-world-model-backend-spec.md),
a design record that is not an ADR:

> R2 New evidence higher authority than current (e.g. VERIFIED over
> OBSERVED/INFERRED): new value wins -> ACTIVE with new epistemic; mark
> prior evidence superseded; set supersedes.
>
> R3 New evidence equal authority, newer observed_at, comparable source:
> newer value supersedes older -> ACTIVE; prior evidence superseded.

The proposed *Epistemic Integrity, Belief State & Uncertainty Governance
Specification v0.1* (source 15) remains PROPOSED / NOT ACCEPTED. Its clause
text is not in this repository; the
[contract index](../architecture/cognitive-contracts/v0.1/README.md) holds
only its metadata and hash, and the ledger holds paraphrases of E-25 and
E-26. This ADR does not adopt that source or rely on its wording.

### Repository evidence

All items are repository code in `services/core-api/app.py`, Slice 7 and
7.1 blocks, at the baseline commit, unless marked otherwise. None is a
statement about live deployment state.

- **REPO CODE.** `world_belief` has one row per semantic key
  (`entity_type:entity_id:predicate`) and one mutable `value_json`.
- **REPO CODE.** R2 (higher epistemic rank) and R3 (equal rank, newer
  `observed_at`) overwrite `value_json` in place. No prior value is kept on
  the belief row, and `world_belief_trace` records reason codes and
  lifecycle changes but no values.
- **REPO CODE.** R4 (equal rank, disagreeing, not newer) keeps the incumbent
  value, sets `CONFLICTED` and writes a conflict row whose reference is a
  timestamp string, not an evidence identity. The competing value exists only
  in a `world_belief_evidence` row.
- **REPO CODE.** `/os/world` and `/os/world/{key}` return evidence metadata
  without the value each evidence row asserted, return `supersedes` as an
  empty list, and omit evidence flagged `superseded`. Alternatives are not
  normally visible to any consumer.
- **REPO CODE.** R1 runs before any rank check. A repeat of the current
  value from any source, including `INFERRED`, moves `CONFLICTED` to `ACTIVE`
  and marks the open conflict rows resolved.
- **REPO CODE / INFERENCE.** R3 does not mark the earlier evidence
  superseded and does not resolve open conflict rows, contrary to the spec.
  The outcome of a sequence of evidence depends on arrival order: an older
  observation that arrives late with a different value becomes `CONFLICTED`.
- **REPO CODE.** The evidence `superseded` flag means both "was current and
  was replaced" (R2) and "lower rank, never adopted" (R5). Lifecycle state
  `SUPERSEDED` is declared and filtered by readers but never assigned.
- **REPO CODE.** Confidence is rule-derived and compared by no rule. Repeated
  same-value evidence raises it, including dependent repeats (C-22).
- **REPO CODE.** Only `submit_observation` has callers. User assertion,
  inference and verified-delta ingestion have none, so R2 and R5 are latent;
  R1, R3 and R4 are the rules the current pipeline exercises.
- **REPO CODE.** Every consumer reads one value per key: Working Memory
  reconstruction, the Slice 9 reasoning input and the Slice 10 Workspace
  (record copies), and the `/world` page. Conflict is visible as a lifecycle
  flag only.
- **REPO RECORD.** Slice 7 and 7.1 recorded 18/18 and 9/9 tests passing and
  a controlled live conflict (2026-09-07). Those records are HISTORICAL;
  REVALIDATE. The tests are record copies, not part of
  `services/core-api/tests`.

### What the evidence shows

The rules rank evidence correctly within their own terms, but the result of
the ranking is written as the single stored belief. Storage, preference and
something that reads like truth are the same field. The repository cannot
directly answer "What did I believe before, and why did it change?", cannot
show a consumer what the competing claim says, and cannot tell a changed
world from a corrected mistake. Evidence is not deleted, but the belief's
history is not first-class.

## Decision

The canonical World Model preserves materially competing epistemic claims,
their provenance and their conflicts as first-class state. Any single
"current" or "preferred" value is a separately derived, non-authoritative
**Epistemic Projection**. Winning a reconciliation comparison does not make
a claim true, does not erase its competitor and does not resolve a conflict.

```text
evidence  ≠  claim  ≠  epistemic projection  ≠  accepted truth  ≠  working assumption
preferred projection  ≠  accepted truth
projection choice     ≠  conflict resolution
reconciliation computation  ≠  semantic acceptance
world change  ≠  correction
superseded    ≠  erased,  superseded  ≠  necessarily false
```

### Definitions

These terms are used only as far as needed to keep evidence ranking separate
from truth-like storage. They define no global truth ontology.

- **Evidence.** A recorded observation, assertion, inference or verification
  result, with its provenance, that bears on a claim.
- **Epistemic claim.** A proposition about a semantic subject (today, a
  semantic key) and its value, supported by evidence.
- **Materially competing claims.** Claims that the World Model treats as
  incompatible for the same subject. Today the repository detects this only
  as a same-key value disagreement. The later World Model contract defines
  incompatibility, including scope and time.
- **Epistemic conflict.** The recorded state that materially competing
  claims exist and are unresolved.
- **Epistemic resolution.** A disposition of competing claims made under a
  later accepted epistemic resolution rule.
- **Epistemic Projection.** A derived, non-authoritative view that selects
  or summarizes epistemic state for a bounded consumer, context or purpose.
- **Accepted truth.** World Model state accepted under a designated owner's
  governance (ADR-0007). No such acceptance exists today.
- **Decision-time working assumption.** A bounded assumption a planner or
  reasoner adopts to act under uncertainty.

### Core rules

- **EP-1. Competing claims stay first-class.** Materially competing claims
  and their provenance remain first-class and queryable while unresolved. A
  later accepted epistemic resolution rule may end the unresolved-conflict
  state and change a claim's status or disposition (for example, superseded
  or rejected, in vocabulary the later contract defines). Resolution must not
  erase the historical claim, its provenance or its historical
  queryability. Where an accepted privacy-erasure policy applies, that
  separate policy remains controlling.
- **EP-2. Arrival does not erase.** A new claim or evidence item must not
  make an incompatible earlier claim disappear, or stop it being
  epistemically queryable, merely because it:
  - arrived later;
  - has a higher current rule rank;
  - repeats the incumbent value;
  - is preferred by a model;
  - is selected for an Epistemic Projection or a working assumption.
- **EP-3. R2 and R3 do not select truth.** The Slice 7 R2 and R3 rules are
  not accepted as canonical truth-selection rules. Winning an R2 rank
  comparison or an R3 recency comparison does not by itself:
  - erase an incompatible claim;
  - make the losing claim cease to be epistemically queryable;
  - establish canonical or accepted truth;
  - resolve a conflict.

  R2 and R3 are not accepted as projection policy either. Their future role
  stays undecided until the projection or resolution contract exists.
- **EP-4. Ranking inputs are not banned.** A later accepted projection or
  resolution contract may use epistemic authority, recency, verification,
  source properties or other evidence characteristics as inputs. This ADR
  defines no ranking rule, order or weight.
- **EP-5. The Epistemic Projection is derived and non-authoritative.** An
  Epistemic Projection:
  - is derived from canonical epistemic state;
  - is recomputable from that state where applicable, and can be revised
    when the state changes;
  - may select or summarize a bounded view, omitting detail for a bounded
    consumer or purpose under a later contract;
  - does not mutate, delete, overwrite or suppress the underlying canonical
    claims, evidence or conflicts because they are not selected;
  - must keep the existence of an unresolved conflict discoverable where
    that conflict is materially relevant, so that omitting alternatives cannot
    be mistaken for settled truth;
  - does not make itself authoritative, and does not become accepted truth
    by being selected, cached, rendered or consumed;
  - carries the unresolved-conflict status of what it summarizes;
  - must not present a preference as settled truth;
  - may vary by scope, consumer or purpose under a later accepted contract.

  The projection algorithm, its owner and its acceptor are not decided here.
- **EP-6. Projection choice is not resolution.** Selecting one claim for a
  projection does not resolve the conflict, mark the other claim false or
  change canonical epistemic state.
- **EP-7. Working assumptions are not World Model resolution.** A planner or
  reasoner may later be permitted to adopt a bounded decision-time working
  assumption when action requires one. Adopting it must not, by that fact:
  - change canonical epistemic state;
  - mark a competing claim false;
  - clear an epistemic conflict;
  - become an accepted belief.

  A later planning or execution contract decides how working assumptions are
  selected, scoped and disclosed.
- **EP-8. Unresolved conflict is first-class state.** An unresolved
  conflict must not be cleared solely because:
  - the incumbent value is repeated;
  - a lower-authority source repeats a value;
  - a model asserts a value again;
  - a projection selects one value;
  - a consumer needs a single value.

  Qualifying resolution evidence and its acceptance are defined by the later
  World Model contract.
- **EP-9. World change is not correction.** Two different values for one
  semantic predicate at different valid times may both have been correct.
  The architecture must not infer that an earlier claim was wrong merely
  because a newer observation differs. Equally, a correction (an earlier
  claim found erroneous, or set aside under an accepted epistemic rule) is
  not a change in the world. The later contract must represent enough
  temporal and context information to tell these cases apart. Until it can,
  neither case may be settled by discarding the earlier claim.
- **EP-10. Historical epistemic integrity.** Through the later World Model
  contract, the canonical record must be able to answer:
  - what evidence was known at time T;
  - which claim was preferred at time T, and for which projection;
  - which incompatible claims existed;
  - when a preference changed, and why;
  - whether a later value was a correction, a changed world or an unresolved
    disagreement.

  This requires no particular mechanism, such as event sourcing. It requires
  that historical epistemic facts and provenance are not lost by later
  writes.
- **EP-11. Supersession preserves standing.** If the World Model uses
  supersession, a superseded item is not erased and is not thereby false.
  It keeps historical and provenance standing appropriate to the World Model
  domain. World Model supersession semantics are defined by the later
  contract. They are not copied from ADR-0006 memory revisions or ADR-0012
  goal lineage.
- **EP-12. Confidence is not authority.** Confidence alone does not accept a
  claim, resolve a conflict or select canonical truth. Repeated evidence
  must not gain authority merely through replay or repetition. Calibration
  and corroboration policy are not decided here (C-22 stays open).
- **EP-13. Provenance is kept; source trust is not decided.** Provenance is
  preserved as input to later epistemic reasoning. This ADR creates no
  source-reliability weights and does not make any source class (user,
  connector, tool, verification, model or inference) more trustworthy than
  accepted architecture already provides. A source-trust-weighted projection
  or resolution rule needs its own accepted contract or policy.
- **EP-14. Model output is proposal.** A model cannot make a claim true by
  producing it, cannot resolve a conflict by repeating a claim, does not
  become a World Model owner, and does not determine canonical epistemic
  state because it was selected as the cognitive engine (ADR-0007 OD-9;
  ADR-0011). A model or provider substitution alone must not change
  LILITH's epistemic history.
- **EP-15. Consumers can see unresolved competition.** A consumer that
  receives an Epistemic Projection must be able to determine that unresolved
  competing claims exist. Not every consumer needs every evidence row, and no
  wire format is mandated. A projection must not hide an unresolved conflict
  so that a preference cannot be told apart from settled truth. The later
  consumer contract defines the payloads.
- **EP-16. Semantics, not authority.** These rules define epistemic
  semantics. They do not designate a World Model owner, acceptor or
  source-trust authority, accept any World Model state or authorize any
  write.

### Authority and acceptance

```text
proposal  ≠  acceptance
reconciliation computation  ≠  semantic acceptance
Epistemic Projection        ≠  semantic acceptance
```

- ADR-0007 still requires a designated World Model semantic owner before
  reconciliation counts as destination governance. None exists today.
- Current reconciliation output is not accepted truth because code wrote
  it. Whether world beliefs need governed acceptance stays open (EPI-11).
- Semantic ownership and this ADR grant no action permission (ADR-0007
  OD-10). A belief or projection still grants no permission to act (Slice 7
  §17).

### Historical continuity

With claims, conflicts and history preserved, the canonical record can
eventually support statements such as:

- I used to believe X.
- I later found evidence for Y.
- X and Y are still unresolved.
- I currently lean toward Y, for this purpose.
- I changed my mind because of evidence Z.
- I was wrong before, or the world changed since.
- I am uncertain.

This is continuity and provenance architecture. It makes no claim about
experience or consciousness.

### Independence from D-9

This ADR decides D-8 on repository evidence and accepted ADRs alone. R2 and
R3 come from repository design. E-25 and E-26 exist in this repository only
as ledger paraphrases of an unaccepted source. This ADR does not accept PDF
15, E-25, E-26, any source-trust clause or any other D-9 source or clause.
D-9 is unchanged.

### Historical implementation disposition

The Slice 7 spec, deployment records, Slice 7.1 record and test copies are
not edited. They remain accurate history of what was built (rank 3,
HISTORICAL; REVALIDATE for live claims). With this ADR accepted, the
following current repository behavior is **non-conforming implementation
debt**, not accepted semantics:

- one mutable `world_belief.value_json` per semantic key acts as the stored
  belief (EP-1, EP-5);
- R2 and R3 overwrite that value, and the earlier value is not kept as a
  first-class claim (EP-2, EP-3);
- R4 keeps one incumbent value and exposes only a conflict marker; the
  competing value lives only in an evidence row that reads do not return
  (EP-1, EP-15);
- R1 clears `CONFLICTED` when the current value is repeated, from any
  source (EP-8);
- consumers normally receive one value per key with no access to
  alternatives (EP-15);
- belief history is not directly reconstructable or queryable (EP-10);
- the evidence `superseded` flag conflates replacement with
  never-adopted, and conflict references are not evidence identities
  (EP-10, EP-11);
- repeated and dependent evidence raises confidence (EP-12; C-22).

This ADR does not decide whether the existing single-value row could later
serve as an Epistemic Projection. That is for the later contract, and would
require EP-5 and EP-15 to hold.

Current live World Model contents and behavior are UNKNOWN. This ADR claims
no live state.

### Non-goals

This ADR does **not**:

- implement or name claim, evidence, conflict-set or projection schema,
  tables, fields or endpoints;
- define valid-time or context representation;
- define source reliability or source-trust policy;
- define a confidence formula, calibration or corroboration policy, or
  resolve C-22;
- define full conflict-resolution criteria or a projection algorithm;
- designate a World Model owner or acceptor, or resolve EPI-11;
- accept D-9 or any proposed source or clause, in whole or in part;
- redesign planning, the Workspace or the Executive;
- define semantic contradiction detection;
- define TTL or freshness policy (EPI-08);
- change memory supersession (ADR-0006) or goal history (ADR-0012);
- define a global truth ontology;
- resolve C-20, or change goal or personality semantics;
- make preserved claims undeletable where privacy rules require removal;
- perform or authorize any live write, migration, reconciliation,
  deployment or contact with a live system;
- fix or close G1 or G2;
- change B-5 (WITHHELD), FRESHNESS (UNKNOWN), M-B1 or First Memory (NOT
  AUTHORIZED), or the substrate-drift policy (OPEN).

## Compatibility with accepted ADRs

| ADR | Relationship | Result |
| --- | --- | --- |
| ADR-0001 | LILITH owns canonical state and provenance above runtimes. Epistemic history is canonical state, not a property of a runtime or model | Agrees |
| ADR-0002 | Requires explicit conflict outcomes, auditable provenance and no naïve last-write-wins. EP-1, EP-2 and EP-8 stop a later or higher-ranked write from silently replacing a competing claim | Agrees; applies |
| ADR-0003 | Unknown and partial outcomes are first-class, and execution is not verification. EP-8 keeps unresolved conflict as a state; EP-12 stops confidence standing in for verification | Agrees; applies |
| ADR-0007 | Proposal is not acceptance, a projection is never authoritative, and hosting or computing over state confers no ownership (OD-4, OD-5, OD-9). EP-5, EP-14 and EP-16 apply this to the World Model; no owner is designated | Agrees; orthogonal to ownership |
| ADR-0011 | Model and runtime output is proposal and context, and engine change is not an ownership transition. EP-14 applies this to epistemic state | Agrees; applies |
| ADR-0012 | History is not rewritten because a later record exists. Analogy only: ADR-0012 states that D-8 is not affected, and EP-11 imports none of its goal rules | Consistent; not imported |

ADR-0004, ADR-0005, ADR-0006, ADR-0008, ADR-0009 and ADR-0010 are not
materially affected. ADR-0006's revision pattern for memory is a precedent
only.

No conflict with an accepted ADR was found. No accepted ADR is amended or
superseded.

## Interaction with unresolved items

| Item | Relationship |
| --- | --- |
| D-8 | Resolved by owner acceptance of this ADR (2026-10-05) |
| D-9 | Independent; no proposed source accepted |
| C-23, EPI-07 | C-23 resolved architecturally; the EPI-07 implementation divergence remains |
| META-07 | The R1 counterexample would become non-conforming (EP-8) |
| C-08, MEM-10 | "Prefer higher-confidence" (CA-V1) is not accepted as a winner rule (EP-3, EP-12) |
| C-22, EPI-06 | Unchanged; EP-12 only bars replay from gaining authority |
| EPI-08 | Unchanged (freshness) |
| EPI-11 | Unchanged (acceptance) |
| R4 | Architecture input for the "repeat must not clear CONFLICTED" item |
| G1, G2, C-20 | Unchanged |

## Alternatives considered

### Keep R2/R3 as winner rules (Option A)

Keeps one value per key and needs no consumer change. Safe only if every
replaced value stays immutable and queryable, R3 marks what it replaced and
R1 cannot clear a conflict. Even then, storage and preference are one field,
correction and world change look the same, and the stored value reads as
truth.

### Preserved conflict without a projection (Option B)

Keeps every competing claim and declares none current until resolved.
Strong on integrity, but every consumer must handle several values or none,
and the record cannot say "I currently lean toward Y". Not selected.

### Status quo

Tested repository behavior continues. EPI-07 and C-23 stay in conflict, a
repeat can clear a conflict, and belief history stays implicit in evidence
rows.

## Consequences

### Positive

- Competing claims and their provenance stay visible and queryable.
- Preference is explicit and separate from truth, so it can change without
  rewriting history.
- Change over time and correction become distinguishable.
- Model or provider substitution cannot rewrite epistemic history.

### Negative and tradeoffs

- The store needs claim-level representation and a migration from
  single-value rows.
- Every consumer needs a projection contract, including conflict status.
- Projection, resolution and working-assumption rules each need their own
  contract before the target is reachable.
- Valid-time and context need a representation before EP-9 is enforceable.

### Operational and migration impact

None from this ADR. No code, schema, data, route or deployment changes.

## Security, privacy, and trust boundaries

- Reduces silent belief replacement by a later or higher-ranked source, and
  stops a replayed or model-repeated claim from clearing a conflict, once
  implemented.
- Adds no new personal data class. Preserved claims are World Model state
  and stay subject to privacy deletion and suppression; "first-class" does
  not mean undeletable (C-06).
- A projection that hides alternatives is a presentation-honesty risk (§8 of
  the ledger); EP-15 addresses the World Model part only.

## Validation

Acceptance proves no conformance. Later evidence includes tests
that:

- a higher-rank or newer claim leaves the earlier incompatible claim
  queryable with its provenance;
- repeating the incumbent value, from any source, does not clear an
  unresolved conflict;
- a projection selection or working assumption changes no canonical
  epistemic state;
- a consumer receiving a projection can see that a conflict is unresolved;
- the state at time T (evidence, preferred claim, competing claims) can be
  reconstructed after later writes;
- a changed world and a correction are recorded differently;
- replayed evidence does not raise authority.

## Revisit triggers

- A World Model contract that needs single-value canonical storage for a
  reason this ADR does not address.
- Evidence that claim-level storage is infeasible at the required scale.
- Acceptance of a proposed epistemic clause that draws the boundary
  differently.
- A privacy or correction mechanism that conflicts with EP-1 or EP-10.

## Open follow-ups

- D-8 is resolved by owner acceptance of this ADR (2026-10-05). The
  canonical World Model preserves materially competing claims, evidence,
  provenance and unresolved conflict as first-class state, and any
  preferred or current view is a separate, non-authoritative Epistemic
  Projection. Acceptance resolves the architectural semantics only. It does
  not make the current repository implementation conforming: the
  single-value, R2/R3-overwrite and repeat-clears-conflict behavior is
  implementation debt (Historical implementation disposition). Current
  repository and live conformance are not established, and live World Model
  state is UNKNOWN. Acceptance performs no World Model schema, code, API,
  consumer or data migration, runs no reconciliation and mutates no live
  World Model state. It designates no World Model owner, acceptor or
  source-trust authority, and creates no source-trust, confidence,
  corroboration, projection or conflict-resolution policy. It does not
  accept PDF 15, E-25, E-26 or any D-9 source or clause. D-9, EPI-11,
  EPI-08, C-22, C-20, G1, G2, ACT-01, C-02 and R1 are unchanged.

Not implemented by this ADR; each requires separate design and
authorization:

1. canonical representation of claims, evidence and conflicts (EP-1, EP-8);
2. the Epistemic Projection contract (EP-5, EP-6);
3. valid-time and context representation (EP-9);
4. explicit conflict-resolution criteria and their acceptance (EP-8);
5. source and provenance policy, where appropriate (EP-13);
6. confidence and corroboration policy (EP-12; C-22);
7. the consumer projection and wire contract (EP-15);
8. migration from mutable single-value rows;
9. tests for conflict persistence and historical reconstruction
   (Validation);
10. a World Model owner and acceptor decision under ADR-0007 (EPI-11).

## Hidden-assumption review

What could make this design look correct while it is wrong?

- **Evidence rows already preserve the claims.** They keep values, but
  reads do not return them, conflict references are not evidence
  identities, and the `superseded` flag is overloaded.
- **Every disagreement is a conflict.** For time-varying predicates most
  differing values are a changed world (EP-9); without valid-time they are
  indistinguishable.
- **A projection is harmless because it is only a view.** It is how every
  consumer sees the World Model; if it hides conflict, preserved storage
  does not preserve epistemic behavior (EP-15).
- **Rule-derived confidence is evidence strength.** It counts dependent
  repeats (C-22) and is compared by no rule.
- **Defining semantics makes reconciliation output accepted.** It does not
  (EP-16; EPI-11).
