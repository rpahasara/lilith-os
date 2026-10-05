# ADR-0012: Terminal goal history is preserved through linked successors

- **Status:** Accepted
- **Date:** 2026-10-05
- **Owners:** Project maintainers
- **Related:** ADR-0001, ADR-0002, ADR-0003, ADR-0007, ADR-0009, ADR-0011;
  ledger D-7, GOAL-03, GOAL-04, GOAL-05, GOAL-06, GOAL-11, C-19, ACT-06,
  COMP-J, G2, R1, R8; principles P-04, P-06, P-12;
  `docs/architecture/slice-8-goal-executive-design.md`

## Context

The [Current Architecture & Acceptance Ledger v0.1](../architecture/current-architecture-acceptance-ledger-v0.1.md)
records owner decision **D-7**: "Goal `reopen`: in place, or linked
successor?". Row GOAL-06 records a CONFLICT between the repository goal
state machine, which lets a terminal goal resume on the same record, and a
proposed requirement that terminal records never resume in place. Conflict
C-19 records the same tension, with disposition "Owner decision D-7 if PDF
adopted".

The proposed *Goal, Commitment & Intention Continuity Specification v0.1*
(source 11) remains PROPOSED / NOT ACCEPTED. Its clause text is not in this
repository; the [contract index](../architecture/cognitive-contracts/v0.1/README.md)
holds only its metadata and hash, and the ledger holds a paraphrase of
GC-16. This ADR does not adopt that source or rely on its wording. It
decides on accepted ADRs and repository evidence alone.

### Repository evidence

All items below are repository code in `services/core-api/app.py`, Slice 8
block, at the baseline commit, unless marked otherwise. None is a statement
about live deployment state.

- **REPO CODE.** `_GOAL_ACTIONS["reopen"]` moves a goal from `COMPLETED`,
  `CANCELLED` or `FAILED` to `PENDING` on the **same `goal_id`**. It writes
  no lifecycle timestamp. It is the only exit from a terminal state.
- **REPO CODE.** The goal row has one column per lifecycle timestamp
  (`started_at`, `completed_at`, `cancelled_at`, `failed_at`, …). Reopen does
  not clear them, so a reopened `PENDING` goal still carries its earlier
  terminal timestamp. A later `activate` or `complete` overwrites the single
  slot (reading of `_transition_goal_impl`; not covered by a test).
- **REPO CODE.** There is no closure-reason or outcome column. A transition
  reason is stored only in `goal_trace.reason` and defaults to
  `"action:<action>"`. Reopen requires no reason.
- **REPO CODE.** `goal_trace` is written by `INSERT` only. The database does
  not enforce that, and a trace row records no revision, operation identity
  or caller.
- **REPO CODE.** `linked_task_ids` is a JSON array on the goal row. Reopen
  leaves it unchanged, so the predecessor's task links carry silently into
  the renewed pursuit. `post_goal_link_task` accepts links in any lifecycle
  state, including terminal states.
- **REPO CODE / INFERENCE.** The `USER_REQUESTED` duplicate check in
  `_create_goal_impl` considers only non-terminal goals, and reopen does not
  apply it. A goal completed, recreated as a new row, and then reopened can
  leave two equivalent non-terminal goals. Later creates for that target then
  return `409 reconciliation_required`. No test covers this path.
- **REPO CODE.** No predecessor, successor, lineage, episode or attempt field
  exists. `parent_goal_id` records a parent/subgoal relation only (design
  §3: "Parent/child is a stored, queryable relationship only").
- **REPO CODE.** Transition replay is detected only against the single
  `last_operation_id`, and `operationId` and `expectedRevision` are optional
  (GOAL-05).
- **REPO RECORD.** Slice 8 design §3 and the deployment record (2026-09-08)
  document `reopen` as explicit and traced. No repository record shows reopen
  being exercised live. Slice 8 records are HISTORICAL; REVALIDATE.
- **REPO CODE / G2.** `POST /os/goals`, `POST /os/goals/{id}/transition` and
  `POST /os/goals/{id}/link_task` have no authorization dependency, and no
  goal-domain acceptor exists (GOAL-04).

### What the evidence shows

The current goal row is a mutable projection with a convention-only
append log. Under in-place reopen, the row can present contradictory state
(`PENDING` with a completion time), later lifecycle writes can overwrite the
only stored time of an earlier outcome, and the earlier outcome survives only
as trace text that nothing protects. Task links lose the boundary between
the original pursuit and the renewed one. The repository can therefore not
reliably answer "Did I complete this before, and is that still true?" for a
reopened goal.

## Decision

A terminal goal record does not resume in place. A later resumption creates
a new goal record that is explicitly linked to its terminal predecessor. The
predecessor remains historical truth; the successor represents the renewed
pursuit.

```text
terminal goal record   ≠  renewed pursuit
renewed pursuit        =  new goal record + explicit lineage to predecessor
```

### Definitions

- **Goal record.** One concrete goal with its own identity (`goal_id` today)
  and its own lifecycle from creation to a terminal state.
- **Terminal predecessor.** A goal record in a terminal lifecycle state
  (`COMPLETED`, `CANCELLED` or `FAILED` in the current state machine).
- **Resumption.** A later decision to pursue again what a terminal
  predecessor pursued.
- **Successor.** The new goal record created by an accepted resumption.
- **Predecessor/successor lineage.** An explicit, typed relation from a
  successor to its predecessor.
- **Terminal lifecycle facts.** A record's terminal state, the time it was
  reached, and the recorded outcome, reason and evidence for it.

### Core rules

- **GL-1. Terminal history is not rewritten by resumption.** Resumption must
  not rewrite the predecessor's terminal lifecycle facts. In particular it
  must not:
  - change the predecessor from `COMPLETED`, `CANCELLED` or `FAILED` back to
    `PENDING`, `ACTIVE` or any other non-terminal state;
  - overwrite the predecessor's terminal timestamp;
  - erase or replace the predecessor's recorded outcome or reason;
  - make the predecessor's completion, failure or cancellation cease to be
    historically true.
- **GL-2. Resumption creates a new goal record.** The successor has a new
  goal identity, distinct from the predecessor's.
- **GL-3. Lineage is explicit and typed.** The successor carries an explicit
  relation to its predecessor. At minimum the canonical record must be able
  to answer:
  1. which prior goal record this pursuit continues from;
  2. what type of lineage relation exists;
  3. why the renewed pursuit was created (provenance of the resumption).

  An untyped or implied link is not sufficient. A match on `(type, owner,
  target_key)` or any other equivalence key is not lineage. The relation
  vocabulary, field names and storage belong to the later goal contract.
- **GL-4. Parent/subgoal lineage is not predecessor/successor lineage.**
  `parent_goal_id` must not be repurposed to represent resumption. The two
  relations are separate and must remain distinguishable.
- **GL-5. The successor has its own lifecycle.** It starts its own lifecycle
  at creation. It does not inherit the predecessor's lifecycle state,
  timestamps, outcome, completion evidence or task links. The predecessor's
  terminal outcome, verification or evidence must not be inherited or
  reused as proof that the successor is complete. Any eventual successor
  completion must be established independently under the goal-domain
  contract applicable to that successor. The predecessor's outcome does not
  complete, fail or cancel the successor, and the successor's outcome does
  not change the predecessor's. Which descriptive values a successor starts with is left to
  the later contract.
- **GL-6. `reopen` is intent vocabulary.** The word or action `reopen` may
  remain as user and API intent vocabulary. Its accepted semantic meaning is
  "request a linked successor to a terminal predecessor". It no longer means
  "mutate the terminal predecessor back to `PENDING`". The endpoint and
  request shape are not decided here.
- **GL-7. Task provenance stays with the predecessor.** A predecessor's task
  links remain associated with the predecessor. Resumption must not
  automatically move, copy or reinterpret those links as the successor's,
  and must not reactivate any task. A successor receives task links only
  through an explicit, accepted goal/task linking action under the
  applicable contract.
- **GL-8. No accidental duplicate successors.** One accepted resumption must
  produce at most one successor, under retry, replay, timeout or concurrent
  submission. Successor creation requires a stable operation identity bound
  to its payload, with explicit conflict outcomes (ADR-0002; ADR-0009
  EB-10). Lineage forks must not arise from retries or races.
- **GL-9. Intentional branching is not decided.** An accidental duplicate
  successor is distinct from an intentionally accepted parallel or
  alternative successor. GL-8 prohibits the former. Whether a predecessor
  may intentionally have more than one successor, whether a successor may
  have more than one predecessor, and whether lineage is a chain or a DAG
  are left to the later goal contract.
- **GL-10. Equivalence checks must not be defeated by resumption.**
  Successor creation must not create duplicate equivalent non-terminal goals
  by bypassing the goal domain's duplicate controls. How an equivalence key
  treats predecessors and successors is left to the later contract.
- **GL-11. Correction is not resumption.** If an erroneous historical record
  ever needs correction, that uses separate, provenance-preserving
  correction semantics. Resumption is never a correction path. This ADR
  does not define the correction mechanism.
- **GL-12. Semantics, not authority.** These rules define goal-history
  semantics. They do not accept any goal transition, designate a goal
  acceptor or authorize any write.

### Goal identity

This ADR introduces no new canonical "semantic goal" or ambition identity.
The repository's `goal_id` is the concrete goal-record identity, and
`(type, owner, target_key)` remains a de facto equivalence and
de-duplication key. This ADR does not elevate that key into an identity,
owner or lineage concept. A future architecture may introduce a stable
concept identity above goal records if evidence justifies it; D-7 does not
require one.

### Historical continuity

The rule exists so that LILITH can keep truthful goal history across renewed
pursuits. With predecessor records intact and explicit lineage, the
canonical record can support statements such as:

- I pursued this before.
- I completed, failed or cancelled it before.
- I resumed it later.
- This later pursuit came from that earlier one.
- The earlier result remains historically true.

This is historical continuity and provenance architecture. It makes no claim
about experience or consciousness.

### Metrics and learning

Successor lineage keeps each pursuit's outcome as a separate, unaltered
fact, so later metrics or learning can tell separate pursuits apart without
retroactively changing an earlier terminal outcome. This ADR defines no
success rate, completion metric, learning rule or reinforcement. Any
aggregation across a lineage is separate, later policy. C-20 and D-8 are
not affected.

### Authority and acceptance

```text
goal transition semantics  ≠  goal-domain acceptance  ≠  effect authorization
```

- ADR-0007 still requires a goal-domain semantic acceptor. None exists today
  (GOAL-04). A request to resume is a proposal to the goal domain (OD-4),
  not an accepted transition.
- ADR-0009 applies independently to any governed effect. Defining successor
  semantics grants no write or action authority.
- Current unauthenticated goal API writes do not become authoritative
  because this ADR defines what a resumption means. G2 and GOAL-04 stay
  open.
- Transcript text such as "I want this again" remains context and proposal
  only (ADR-0011 CX-9). It is not a resumption, a successor or pending goal
  work.

### Independence from D-9

This ADR resolves the goal-history question on its own architectural
merits. It does not adopt source 11, GC-16 or any other proposed clause, and
it does not route any proposed source to acceptance. D-9 is unchanged. C-19
was framed as needing a decision "if PDF adopted"; this ADR decides the
question whether or not that source is ever adopted.

### Historical implementation disposition

The Slice 8 design record, deployment record and tests are not edited. They
remain accurate history of what was built (rank 3, HISTORICAL; REVALIDATE
for live claims). With this ADR accepted, the current repository behavior
is **non-conforming implementation debt**, not accepted semantics:

- `reopen` mutates the same `goal_id` from a terminal state to `PENDING`
  (GL-1, GL-2);
- earlier lifecycle timestamps can later be overwritten, and terminal
  timestamps can coexist with a reopened non-terminal state (GL-1);
- no closure reason or outcome is stored on the record (GL-1, GL-3);
- task links persist across reopen (GL-7);
- duplicate equivalent non-terminal goals can arise through reopen (GL-10);
- no successor or lineage fields exist (GL-2, GL-3);
- transition and create replay is not bound to payload, and operation
  identity is optional (GL-8; GOAL-05, ACT-06).

Separately, `post_goal_link_task` does not check that its revision-guarded
update changed a row, so a concurrent revision change can drop a link while
the trace records it and the response reports `applied: true` (INFERENCE
from code). That is task-link implementation and conformance debt. This ADR
records it and does not fix it.

Whether any live goal was ever reopened is UNKNOWN. This ADR claims no live
state.

### Non-goals

This ADR does **not**:

- implement successor or lineage schema, or define field, column, table or
  endpoint names;
- migrate, backfill or reclassify existing goals;
- perform or authorize any live write, migration, deployment or contact with
  a live system;
- designate the goal-domain acceptor or any goal writer;
- fix G2, close GOAL-04 or GOAL-05, or resolve ACT-01, ACT-06, C-02 or R1;
- redesign the task domain or fix the `link_task` concurrency defect;
- define parent/subgoal behavior or cascade;
- define metrics, learning or reinforcement, or resolve C-20;
- decide D-8 World Model winner semantics;
- accept D-9 or any proposed source, in whole or in part;
- define goal expiry or review (GOAL-03), or commitment, obligation or
  intention types (GOAL-02);
- define relationship or consent semantics;
- define the correction mechanism for erroneous history;
- decide intentional successor cardinality (GL-9);
- change B-5 (WITHHELD), FRESHNESS (UNKNOWN), M-B1 or First Memory (NOT
  AUTHORIZED), or the substrate-drift policy (OPEN).

## Compatibility with accepted ADRs

| ADR | Relationship | Result |
| --- | --- | --- |
| ADR-0001 | LILITH owns goals and provenance above the runtime, and disabling Hermes must not erase "canonical goals … or identity lineage". Goal lineage is canonical state above any runtime | Agrees |
| ADR-0002 | Requires stable operation identities, explicit conflict outcomes, auditable provenance and no naïve last-write-wins. GL-1 stops a resumption from overwriting terminal facts; GL-3 and GL-8 apply provenance and operation identity to successor creation | Agrees; applies |
| ADR-0003 | Completion is a verification outcome. GL-1 and GL-5 stop a later pursuit from erasing an earlier completion or failure, and stop the predecessor's outcome or evidence from being reused as proof of the successor's completion. This ADR adds no completion-evidence requirement | Agrees; applies |
| ADR-0007 | Proposal is not acceptance (OD-4); the destination domain accepts its own transitions. GL-12 keeps semantics separate from acceptance; no acceptor is designated | Agrees; orthogonal |
| ADR-0009 | Semantic ownership does not authorize effects, and retries must not duplicate effects (EB-10). GL-8 mirrors EB-10 for successor creation; GL-12 grants no authority | Agrees |
| ADR-0011 | Transcript context is not authoritative pending work (CX-9). A conversational wish to resume creates nothing | Agrees; applies |

ADR-0004, ADR-0005, ADR-0006, ADR-0008 and ADR-0010 are not materially
affected. ADR-0006's restore-as-new-revision pattern for memory is a
precedent only, not a constraint on goals.

No conflict with an accepted ADR was found. No accepted ADR is amended or
superseded.

## Interaction with unresolved items

| Item | Relationship |
| --- | --- |
| D-7 | Resolved by owner acceptance of this ADR (2026-10-05) |
| D-8 | Independent |
| D-9 | Independent; no proposed source accepted (see Independence from D-9) |
| G1 | Independent |
| G2, R1, ACT-01, C-02 | Unchanged. Successor semantics cannot protect unauthenticated write routes |
| GOAL-04 | Unchanged. Conformance needs a designated goal acceptor |
| GOAL-05, ACT-06, COMP-J | Implementation of GL-8 depends on payload-bound idempotency |
| GOAL-06, C-19 | C-19 resolved architecturally; the GOAL-06 implementation divergence remains |
| R8 | Architecture input for the `reopen` part of goal API hardening |
| C-20 | Unchanged |

## Alternatives considered

### In-place reopen (current behavior)

Keeps one identity and needs no lineage field. As implemented, it presents
contradictory row state, overwrites single-slot timestamps and carries task
links across pursuits, so earlier outcomes stay true only in unprotected
trace text. A safe form would need immutable per-episode records inside one
goal, which turns terminal states into episode boundaries and leaves the
row, focus and task links ambiguous about which pursuit they describe.

### Stable goal concept with attempt records

Separates a durable concept identity from per-pursuit records. It answers
"same ambition or new attempt" directly, but introduces a new canonical
identity layer that current evidence does not require, and would elevate an
equivalence key into identity. Not selected; left open for a future ADR.

### Unlinked new goal

Already possible today: after completion, the same `(type, owner, target)`
can be created again under a new identity. Nothing records that it follows
the earlier goal, so "I tried this before" depends on matching keys.

### Status quo

The tested repository behavior continues to reopen in place, GOAL-06 and
C-19 stay in conflict, and goal history stays rewriteable by any caller of
the transition route.

## Consequences

### Positive

- Terminal outcomes stay historically true and independently queryable.
- Each pursuit has its own lifecycle, evidence and task links.
- Lineage makes "pursued before", "resumed later" and "came from" explicit.
- Later metrics can distinguish pursuits without retroactive change.

### Negative and tradeoffs

- Consumers that follow a goal over time must follow lineage, not one ID.
- Arbitration, de-duplication and target lookups need lineage-aware rules
  (the Slice 12 record copy looks up "the single non-terminal durable goal"
  for a target).
- Successor creation needs stronger idempotency than the current routes
  provide.
- Unfinished work from a predecessor needs an explicit linking step.

### Operational and migration impact

None from this ADR. No code, schema, data, route or deployment changes. Any
historically reopened goals need a separately designed and authorized
migration or classification; whether any exist is UNKNOWN.

## Security, privacy, and trust boundaries

- Prevents an unauthenticated or stale caller from silently rewriting goal
  history through resumption, once implemented. It does not itself protect
  any route (G2).
- Adds no new personal data class. Lineage and resumption provenance are
  goal state and are handled like other goal state. The GOAL-12 gaps (no
  privacy scope, no deletion or suppression path) are unchanged.
- Correction and privacy deletion remain separate concerns (GL-11). This ADR
  does not make history undeletable where privacy rules require removal.

## Validation

Acceptance proves no conformance. Later evidence includes tests that:

- a resumption leaves the predecessor's terminal state, timestamp, outcome
  and reason unchanged;
- a resumption creates a new goal identity with typed lineage and recorded
  provenance;
- `parent_goal_id` is not used for resumption;
- resumption moves, copies or reactivates no task link or task;
- retry, replay and concurrent submission of one resumption create exactly
  one successor, and a reused operation identity with a different payload is
  rejected;
- resumption cannot leave duplicate equivalent non-terminal goals;
- transcript text alone creates no successor;
- an unauthorized or unaccepted request leaves goal state unchanged, once a
  goal acceptor and trusted boundary exist.

## Revisit triggers

- Evidence that a stable concept identity above goal records is needed.
- A goal contract that needs resumption to share identity with the
  predecessor for a reason this ADR does not address.
- Acceptance of a proposed goal clause that draws the boundary differently.
- A correction or privacy mechanism that conflicts with GL-1.

## Open follow-ups

- D-7 is resolved by owner acceptance of this ADR (2026-10-05). A terminal
  goal record does not resume in place; a later resumption creates a new
  goal record with explicit typed lineage to its terminal predecessor, and
  the predecessor's terminal history is preserved. Acceptance resolves the
  architectural semantics only. It does not make the current in-place
  `reopen` implementation conforming: that behavior is implementation debt
  (Historical implementation disposition). Acceptance performs no schema,
  API, runtime or data migration, changes no live goal or task state,
  creates no successor, designates no goal acceptor and grants no authority.
  It creates no general goal completion-evidence requirement (GOAL-03 is
  unchanged). Current live deployment and conformance are not established.
  It does not accept source 11, GC-16 or any D-9 source or clause. D-8, D-9,
  C-20, G1, G2, ACT-01, C-02 and R1 are unchanged.

Not implemented by this ADR; each requires separate design and
authorization:

1. successor and lineage schema and API contract, including the lineage
   relation vocabulary and intentional cardinality (GL-3, GL-9);
2. migration or backfill of any historically reopened goals;
3. task-link handling in successor creation (GL-7), and the separate
   `link_task` concurrency defect;
4. de-duplication, idempotency and concurrency hardening (GL-8, GL-10;
   GOAL-05, ACT-06; R8);
5. goal-domain acceptor and trusted-boundary enforcement (GOAL-04; G2; R1);
6. tests for immutable predecessor history and successor lineage
   (Validation).

## Hidden-assumption review

What could make this design look correct while it is wrong?

- **The trace already preserves history.** It records transitions by code
  convention only, with no revision, operation identity or caller, and
  nothing protects it.
- **Same type and target means same goal.** That is an equivalence key for
  de-duplication, not identity or lineage.
- **A link is enough.** An untyped link cannot say why the pursuit resumed
  or what relation it has (GL-3).
- **Retries are rare.** Optional operation identities and single-slot replay
  detection make duplicate successors a real risk (GL-8).
- **Reopen is unused, so nothing needs migrating.** Live use is UNKNOWN.
- **Defining semantics makes current writes legitimate.** It does not
  (GL-12; G2; GOAL-04).
