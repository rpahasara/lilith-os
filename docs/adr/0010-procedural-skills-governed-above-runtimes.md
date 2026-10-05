# ADR-0010: Procedural skills are governed above runtimes

- **Status:** Accepted
- **Date:** 2026-10-05
- **Owners:** Project maintainers
- **Related:** ADR-0001, ADR-0002, ADR-0003, ADR-0006, ADR-0007, ADR-0008,
  ADR-0009; ledger D-5, D-6, C-20, C-21, LEARN-02, LEARN-03, LEARN-04,
  LEARN-06, LEARN-08, LEARN-09, LEARN-11, META-09, COMP-A, ADAPT-03, ACT-03,
  R5, R6, R14

## Context

The Hermes runtime carries a set of learning mechanisms that persist state
across turns. The repository holds no Hermes source. Everything below comes
from patch scripts, record copies and deployment records dated 2026-09-07 to
2026-09-10 (ledger §2.2, §10.3). It is **REPO RECORD / HISTORICAL** and says
nothing certain about the current runtime.

- **REPORTED.** A Hermes skills tree exists on the runtime host. On
  2026-09-09 it held 2,439 files with a path/size/mtime metadata fingerprint
  of `c7d3d256…f441e` (`slice-15b1/DEPLOYMENT-RECORD.md`).
- **REPORTED (patch anchors).** A skill-manager tool,
  `hermes-agent/tools/skill_manager_tool.py`, offers `create`, `edit`,
  `patch`, `delete`, `write_file` and `remove_file`. A gate can stage a
  skill write as pending through `write_approval.stage_write(SKILLS, …)`. A
  `/skills approve` handler replays a staged write through
  `apply_skill_pending`, which sets `_skill_gate_bypass`
  (`slice-15b2a/patch_slice15b2a.py::patch_skill_manager`).
- **REPORTED (patch anchors).** A background reviewer,
  `hermes-agent/agent/background_review.py`, receives an agent, a
  cancellable review run and a snapshot of conversation messages, and builds
  a review prompt (`patch_slice15b2a.py::patch_background_review`). The
  15B2a design states that "No cadence, summarization, personality, prompt,
  or unrelated skill-generation behavior changed".
- **REPORTED.** Slice 15A classifies Hermes skills as `NON_LTM_ARTIFACT` /
  `LEGACY_EXTERNAL` and the reviewer as `LEGACY_EXTERNAL_WRITER`, with
  "adopt/gate/disable/replace/exclude options" left open
  (`slice-15a-learning-consolidation-foundations-design.md`).
- **REPORTED.** Slice 15B2a added legacy canonical-memory containment at the
  skill direct, staging and replay-before-bypass paths, and removes typed
  memory-lane turns before background-review prompt construction
  (`slice-15b2a/DEPLOYMENT-RECORD.md`). Containment hashes after deployment
  were recorded for both files.
- **OBSERVED (repository code).**
  `services/core-api/lilith_memory/legacy_canonical_containment.py` defines
  `filter_background_review_messages` and `LegacySkillErasureOwner`
  (privacy owner `LEGACY_SKILLS`). These are containment and erasure
  helpers. They are not a skill domain.
- **OBSERVED.** No canonical procedural-skill state, schema, store, proposal
  interface or acceptor exists in the repository (ledger LEARN-03, LEARN-04).
- **UNKNOWN.** The reviewer's enabled state, trigger, cadence, toolset and
  outputs; whether it writes `MEMORY.md`, `USER.md`, `SOUL.md` or overlays;
  every current skill write path; whether skills are loaded into model
  context; the current pending queue; the current tree size and fingerprint;
  whether the current containment hashes match the record; and any link from
  skills to routing, tool selection or cron (ledger ADAPT-03, META-09, PER-03,
  ACT-03).

The [ledger](../architecture/current-architecture-acceptance-ledger-v0.1.md)
records the mechanism as conflict C-21 and owner decision D-5 ("adopt, gate,
disable or exclude"). ADR-0007 lists it as non-conforming debt under OD-7 and
OD-9, with D-5 as disposition owner. ADR-0007's Exceptions section requires a
later ADR to designate the owner of any domain other than memory.

Repository design records also blur procedural learning with other domains:
`cognitive-architecture-v1.md` places "procedural (skills/recipes)" inside
the memory archive; CA-V1 §15 has verified success "strengthen procedural
memory" (C-20); the Memory UI shows a "Learned" metric (LEARN-02). A single
legacy reviewer that sees whole conversations is a plausible writer into
several domains at once.

The proposed *Learning, Skill Acquisition & Competence Development
Specification v0.1* remains PROPOSED / NOT ACCEPTED. This ADR does not adopt
it and does not rely on its clause text. It decides on accepted ADRs and
repository evidence alone.

## Decision

D-5's architectural direction is **GATE**: durable procedural skill learning,
if LILITH retains it, is governed above the runtime, and runtime learning
mechanisms are proposal-only. This ADR sets classification and conformance
rules. It decides no operational step.

### Definitions

- **Procedural skill.** LILITH's accepted, reusable know-how for carrying
  out a class of task: a method or sequence, its conditions of use, and its
  known limits and failure modes, held as governed state above any runtime.
  It excludes facts and episodes, personality, relationship state, values and
  preferences, goals, beliefs, authority and policy, tool permissions, and
  model-native or provider-native capability.
- **Procedural Skill domain.** The canonical domain (ADR-0007) whose state is
  canonical procedural skill state. It is a semantic boundary, not a
  service, database, process or schema.
- **Accepted procedural competence.** Procedural skill state that the
  Procedural Skill domain has accepted. Nothing else counts as LILITH's
  procedural competence.
- **Runtime skill artifact.** Any runtime-side file, record, prompt fragment
  or cache that holds or conveys procedural content to a runtime or model,
  including Hermes skill files. A runtime skill artifact derived from
  accepted procedural skill state is a projection in the ADR-0007 sense.
- **Skill proposal.** A typed request to the Procedural Skill domain to
  create, revise, retire or restore procedural skill state, carrying
  attributed evidence. This ADR does not define its schema.

### Core rules

- **SKILL-1.** Procedural skill is a distinct LILITH semantic domain above
  replaceable models, providers, runtimes, prompts, devices and presentation
  layers.
- **SKILL-2.** The Procedural Skill domain is the single semantic owner of
  canonical procedural skill state under ADR-0007 (OD-1). Only an accepted
  acceptor for that domain may semantically accept or reject skill proposals
  (OD-5). Semantic ownership and semantic acceptance grant no action
  permission, tool authority or effect authorization (OD-10). Where a state
  transition or a resulting action is a governed effect, ADR-0009 remains
  independently applicable. This ADR designates the domain and its owner
  boundary only. It defines no implementation component, service, database,
  store, process, schema, acceptor mechanism or proposal interface. It
  creates no canonical skill state and does not require that any ever be
  created.
- **SKILL-3.** Hermes, a model, a provider, a prompt, `SOUL.md`, a
  background reviewer and a runtime skill file are not the semantic owner of
  procedural skill, whether they store, execute, render or compute over it
  (OD-9).
- **SKILL-4.** A runtime, including Hermes, may act toward this domain only
  as a replaceable reader, proposer, projection or cache, or adapter-bound
  consumer of accepted procedural skill state (ADR-0001 adapter contract).
- **SKILL-5.** A proposal is never acceptance (OD-4). Runtime approval
  steps, including Hermes `/skills approve` and the `_skill_gate_bypass`
  replay, are not LILITH approval evidence (ADR-0009 EB-8) and not
  Procedural Skill acceptance.
- **SKILL-6.** Observed or verified execution success may provide evidence
  for a skill proposal. Execution success does not itself mutate accepted
  procedural competence. It does not accept a skill, verify a skill, grant a
  capability, grant tool authority, change policy, change personality or
  change identity. Verification of a skill claim stays separate from the
  execution that produced the claim (ADR-0003). This ADR does **not** decide
  strengthening thresholds, reinforcement policy, confidence updates,
  repetition or corroboration policy, decay, generalization, automatic
  acceptance criteria, or skill revision and replacement policy. Those belong
  to a later accepted Procedural Skill contract or policy. C-20 (CA-V1 §15
  procedural reinforcement) remains unresolved; this ADR neither accepts nor
  rejects CA-V1 §15's reinforcement mechanics.
- **SKILL-7.** Acceptance of a procedural skill grants no action permission,
  tool authority, capability, policy change, freshness or currentness
  (OD-10). A skill that describes the use of a tool or capability does not
  authorize that use. Every resulting effect still crosses the authoritative
  boundary that applies to it (ADR-0009).
- **SKILL-8.** Procedural skill is separate from autobiographical and
  factual memory, personality, relationship state, values and preferences,
  goals, beliefs and the World Model, and authority and policy. Learning,
  revising or retiring a skill does not by itself change any of those
  domains. Content in a skill proposal that concerns another domain is at
  most evidence for a separate proposal to that domain, which decides under
  its own governance (OD-3, OD-5, OD-7).
- **SKILL-9.** Running automatically, on a schedule or in the background
  confers no authority, ownership or acceptance on any process.
- **SKILL-10.** Accepted procedural competence is held above the runtime.
  Replacing or changing the model, provider, runtime, prompt, `SOUL.md` or
  other projection, or device, does not by itself erase, create or redefine
  accepted procedural competence. Model-native or provider-native capability
  is a property of the substrate, not a LILITH skill, and a provider update
  is not LILITH learning.
- **SKILL-11.** The presence of a runtime skill file is not evidence of
  accepted competence. Its absence after a runtime replacement is not loss of
  accepted competence.
- **SKILL-12.** Until canonical procedural skill state exists, its absence
  stays explicit. Runtime skill files must not be relabeled as canonical to
  fill the gap.
- **SKILL-13.** A non-canonical artifact must not act as accepted competence
  by influence. As target conformance:
  - an unaccepted runtime skill artifact is not accepted procedural
    competence;
  - unaccepted reviewer output or a legacy skill file must not silently
    influence normal LILITH behavior as accepted competence, whether through
    prompts, context, routing or tool behavior;
  - a runtime projection or cache used as LILITH's procedural competence
    must be derived from accepted Procedural Skill state under an accepted
    adapter or projection contract;
  - mutating a projection or cache never mutates canonical skill state by
    implication;
  - a runtime-local artifact may be used experimentally only under an
    explicitly bounded experimental or sandbox contract that gives it no
    canonical standing, no authority, no personality ownership and no
    durable continuity standing.

  This rule states target conformance. The current Hermes read and
  injection path is UNKNOWN, and this ADR makes no claim that any live
  deployment violates or satisfies it.
- **SKILL-14.** GATE does not mean mandatory human approval for every future
  skill update. This ADR grants no autonomous skill-acceptance authority. A
  later accepted Procedural Skill policy or design may define bounded
  autonomous acceptance, strengthening or revision under explicit evidence,
  scope and verification rules. Such authority must be exercised through an
  accepted acceptor or policy boundary whose authority does not derive from
  the proposal, reviewer, model output, observed success or the runtime's own
  assertion. This ADR does not require that proposer and acceptor roles run
  in separate processes or services, but their authority roles must remain
  distinct under the accepted contract. No such authority is created by this
  ADR. In every case a reviewer cannot approve its own proposals, the runtime
  that hosts a reviewer cannot make itself the acceptor, and model output
  alone or observed success alone is not acceptance.

```text
runtime skill file   ≠  canonical procedural skill
reviewer output      ≠  accepted skill
observed success     ≠  verified skill
skill proposal       ≠  capability grant
skill acceptance     ≠  tool permission
procedural competence ≠ personality
procedural competence ≠ autobiographical memory
```

These add to the separations already accepted: model ≠ identity; runtime ≠
semantic owner; projection ≠ canonical owner; proposal ≠ acceptance or
authority; execution ≠ verification; approval evidence ≠ execution; semantic
ownership ≠ action permission; deployment ≠ activation.

### No valid canonical writer yet

This ADR registers no proposal interface, acceptor or applier for the
Procedural Skill domain. Therefore, after acceptance, **no component is
designated or authorized by accepted architecture to accept or apply
canonical procedural skill transitions**, and any such write path is denied
by default under OD-7. Designating the semantic owner authorizes no component
to start writing skill state. That requires a later accepted design. This is
an architecture statement. It makes no claim about uninspected live runtime
state.

### Background reviewer

The Hermes background reviewer, and any later process in the same role, is
classified as follows:

- **BR-1.** It is non-authoritative. Its output carries no approval,
  acceptance, ownership or authority.
- **BR-2.** Its output that concerns procedural skill, or any other governed
  or canonical domain, is a proposal only until that domain's own
  governance accepts it.
- **BR-3.** It cannot make a canonical write directly. Under OD-7 such a
  path is denied by default.
- **BR-4.** It cannot approve or accept its own proposals, and its
  proposals cannot be approved by the runtime that hosts it (ADR-0009 EB-8).
- **BR-5.** It cannot grant itself, a model or a tool any capability or
  authority.
- **BR-6.** It cannot change identity, personality, relationship state,
  memory, goals, beliefs or values by side effect. A runtime-local write that
  carries such semantics creates no accepted state in that domain and is not
  a transition of it.

This ADR does not specify trigger, cadence, inputs or toolset. Those are
UNKNOWN and belong to the operational disposition.

### Classification of the current Hermes mechanisms

| Mechanism | Classification |
| --- | --- |
| Hermes skills tree | `LEGACY_EXTERNAL` / `NON_LTM_ARTIFACT` (existing 15A vocabulary): non-canonical, runtime-local. Not canonical procedural skill state and not accepted competence |
| Skill-manager write path (`create`, `edit`, `patch`, `delete`, `write_file`, `remove_file`) | Legacy runtime-local write path. Not a Procedural Skill proposal interface or acceptor |
| Pending/approve replay path (`stage_write`, `/skills approve`, `_skill_gate_bypass`) | Legacy runtime-local staging and replay. Not LILITH approval evidence, not acceptance (SKILL-5) |
| Background reviewer | `LEGACY_EXTERNAL_WRITER` (existing 15A vocabulary): non-authoritative; target conformance is proposal-only (BR-1..BR-6) |

None of these is canonical LILITH state, a semantic owner, an approval
authority, an identity or personality owner, a memory or relationship owner,
a goal, belief or value owner, or an authority source.

**No existing skill becomes canonical because it exists.** The historical
2,439 files, or whatever the tree holds now, are not imported or accepted.
Any future import is a set of attributed, typed skill proposals reviewed by
the Procedural Skill domain, never a bulk relabel. Skill file content is
untrusted data in that review. Instructions inside a skill file never become
instructions to the acceptor.

### Lifecycle

**Phase A — current / legacy.** No canonical procedural skill state exists.
Whatever the legacy mechanisms do today continues operationally unchanged by
this ADR, under the non-canonical classification above. Their runtime-local
writes create no accepted procedural competence. Where they act in ways this
ADR's rules do not allow, that is recorded non-conformance debt, not
accepted behavior.

**Phase B — inventory and operational disposition.** A separately
authorized read-only inventory establishes current behavior (see
"Operational disposition"). A separate owner decision then chooses the
operational steps for each mechanism, such as keeping it with containment,
narrowing it, routing its output into proposals, or turning it off. Any
import of existing skills is by proposal.

**Phase C — governed projection.** Accepted procedural skill state is the
source of runtime skill artifacts. Hermes or another runtime may receive a
generated projection. The projection stays replaceable, non-authoritative and
non-canonical, and must not feed back into canonical state except as a new
attributed proposal.

This ADR implements none of these phases and authorizes no transition
between them.

### Projection boundary

Where Hermes or another runtime acts as a projection or cache of procedural
skill state (SKILL-4), that projection or cache is:

- non-authoritative;
- reconstructable from accepted Procedural Skill state, where applicable;
- replaceable together with the runtime;
- not evidence of canonical state merely because the file exists;
- never the sole durable source of LILITH's accepted procedural competence.

This keeps accepted competence intact across model, provider, runtime,
`SOUL.md` and device changes, without tying it to one Hermes installation
(SKILL-10, SKILL-11).

A runtime skill artifact may omit or reformat permitted skill content for a
consumer. It must not change the skill's meaning, widen its scope, carry
authority, or become canonical (ADR-0008 PERS-9 applies the same rule to
personality). A runtime skill artifact that conveys personality semantics is
a personality projection and is governed by ADR-0008, not by this ADR.

### Operational disposition stays separate

Accepting this ADR authorizes no runtime, configuration, code, file or
deployment change. It does not enable, disable, narrow, migrate or delete
any Hermes mechanism or skill file.

Before any operational step, a separately authorized **read-only** inventory
must establish at least:

1. the reviewer's enabled state, trigger and cadence, and whether it runs
   with no active session;
2. every current skill write path, including the reviewer's, and whether each
   is direct or staged;
3. the reviewer's and main agent's current toolsets as they bear on skill
   writes;
4. whether and how skills are read into model context, and on which lanes;
5. the current pending queue;
6. the current skills tree size and fingerprint, and the provenance of its
   files where determinable;
7. whether current `skill_manager_tool.py`, `background_review.py` and
   `write_approval.py` match the 15B2a containment hashes;
8. any write by these mechanisms to `MEMORY.md`, `USER.md`, `SOUL.md` or
   personality overlays;
9. any link from skills or the reviewer to model routing, tool selection or
   cron.

The operational disposition is recorded in a separate owner decision record,
as D-4 was. If that disposition would change architecture rather than apply
it, it requires its own ADR.

### Non-goals

This ADR does **not**:

- implement a Procedural Skill domain, or create a skill schema, store,
  proposal interface, acceptor or applier;
- accept the Learning, Skill Acquisition & Competence Development
  Specification or any other proposed PDF, in whole or in part;
- inspect, contact or assert anything about the live Hermes runtime,
  including whether the reviewer is enabled, the tree's current size or
  fingerprint, current hashes, write paths, toolsets, `/skills approve`
  behavior, or conformance;
- enable, disable, modify, migrate, delete or import any Hermes skill,
  pending record, reviewer or tool;
- change the legacy-containment registry, the Hermes containment patches or
  any ADR-0006 activation precondition;
- decide D-6 (model selection as governed handoff), D-7, D-8 or D-9;
- resolve C-20 (CA-V1 §15 procedural reinforcement) or C-11;
- decide consent ownership for learning from conversation;
- close G1 or G2, or change ACT-01, C-02 or R1;
- authorize B-5, M-B1, PR-1B, First Memory, deployment, migration,
  activation, or any authority, witness or freshness transition.

## Compatibility with accepted ADRs

| ADR | Relationship | Result |
| --- | --- | --- |
| ADR-0001 | LILITH owns canonical state "above the runtime layer"; Hermes is "a replaceable execution substrate" that receives scoped context "through an adapter contract". SKILL-1, SKILL-4 and SKILL-10 apply this to procedural skill. No adapter contract exists yet (ledger ADAPT-02) | Agrees; instantiates for procedural skill |
| ADR-0002 | Caches "are not silently authoritative". Runtime skill files and the Hermes pending queue are classified non-canonical; the runtime approve step is not a canonical approval record | Agrees |
| ADR-0003 | Execution success is executor-side evidence. SKILL-6 keeps skill verification separate from the execution that produced the claim | Agrees |
| ADR-0004 | Governs client capability execution. Skill acceptance grants no capability (SKILL-7) | Agrees; orthogonal |
| ADR-0005 | Deploying a skill file makes it no owner and no accepted competence | Agrees; no interaction |
| ADR-0006 | L04 alone applies canonical memory. SKILL-8 keeps skill state out of memory. This ADR changes no containment registry entry, no Hermes containment patch and no activation precondition, including legacy-containment tuple parity. A later operational change to the skill manager, staging or reviewer must be reviewed against that parity before it is made. First Memory remains NOT AUTHORIZED | Agrees; no change to ADR-0006 state |
| ADR-0007 | OD-9 forbids host-based ownership; OD-3..OD-5 and OD-7 govern proposals and default-deny; OD-10 separates ownership from permission. The Exceptions section requires a later ADR to designate a domain owner; this ADR is that designation for procedural skill, at semantic level only. It dispositions the D-5 debt row architecturally; conformance is not established | Instantiates for procedural skill |
| ADR-0008 | `SOUL.md` is a non-canonical projection. SKILL-8 and the projection boundary keep personality semantics out of skill artifacts. Whether the reviewer can write `SOUL.md` stays UNKNOWN (R6) | Agrees; complementary |
| ADR-0009 | EB-8: requesting, proposing or performing grants no approval authority, for Hermes alike. SKILL-5 applies it to `/skills approve`. EB-9 forbids ungoverned bypass paths. A canonical skill transition needs Procedural Skill acceptance (OD-5) and, where accepted policy requires action authorization, that authorization too; neither substitutes for the other. Runtime-held tools remain R5 and ACT-03 | Agrees; applies EB-8 |

No accepted ADR is superseded or amended.

## Interaction with D-6

D-6 asks when per-turn model selection escalates into a governed handoff,
including "durable/hidden state, authority, tool-right or pending-work
conditions". Runtime-local skill files, staged pending writes and other
hidden runtime state are inputs to that question. This ADR classifies them.
It does not decide D-6, and nothing here makes per-turn model selection a
governed handoff or exempts it from becoming one.

## Historical wording disposition

These records are not edited. After acceptance they remain evidence of what
was recorded at the time and are not the controlling rule.

| Record | Wording | Disposition after acceptance |
| --- | --- | --- |
| `slice-15a-learning-consolidation-foundations-design.md` | Skills `NON_LTM_ARTIFACT`, `LEGACY_EXTERNAL`; reviewer `LEGACY_EXTERNAL_WRITER`; "adopt/gate/disable/replace/exclude options remain open" | Classification compatible and reused. The open option is decided architecturally as GATE; operational choice stays open |
| `slice-15b2a-canonical-memory-authority-privacy-containment-design.md` | "No cadence, summarization, personality, prompt, or unrelated skill-generation behavior changed" | Historical record of a containment-only change. Says nothing about conformance with this ADR |
| `cognitive-architecture-v1.md` | Procedural "skills/recipes" inside the memory archive | Target-architecture wording. Under SKILL-8 procedural skill is its own domain. Reconciliation is R11 |
| `cognitive-architecture-v1.md` §15 | Verified successes "strengthen procedural memory" | Not decided here. C-20 remains unresolved; reinforcement mechanics are left to a later accepted Procedural Skill contract or policy (SKILL-6) |
| Deployment records (15A, 15B1, 15B2a) | Skills tree size and fingerprint; reviewer hashes | HISTORICAL evidence of protection at a date, not of current state, ownership or competence |

## Alternatives considered

### Adopt the Hermes skills tree as canonical procedural skill

This would tie LILITH's competence to one runtime's files. It contradicts
ADR-0001 and OD-9, and ADR-0007's Exceptions section bars giving a runtime
ownership because it holds the state. Runtime replacement would then erase
or redefine competence.

### Disable the mechanisms now

This needs live action and live evidence that does not exist. It may
interact with ADR-0006 containment parity. It would also leave no target for
procedural learning. Turning a mechanism off remains a possible operational
step under Phase B. It is not the architecture.

### Exclude the mechanisms from LILITH architecture

Declaring them out of scope would leave them influencing behavior
unexamined while called irrelevant. That is the accidental-owner pattern this
decision avoids.

### Fold procedural skill into the memory domain

This would let L04 memory acceptance stand in for skill acceptance and blur
"memory is not truth" with "skill is not authority". It would also make the
legacy reviewer's mixed output harder to separate.

### Status quo

C-21 and D-5 stay open. Every later learning design would have to argue
around an ungoverned runtime writer.

## Consequences

### Positive

- D-5 gets an architectural disposition consistent with ADR-0001, ADR-0007,
  ADR-0008 and ADR-0009.
- Procedural learning has a named home above the runtime, so competence can
  survive model, provider, runtime, projection and device changes.
- Runtime approval steps can no longer be read as LILITH approval.
- Operational decisions stay with later evidence instead of being guessed.

### Negative and tradeoffs

- No canonical procedural skill state exists and no component is designated
  as a writer. The gap stays explicit until a later accepted design.
- The legacy mechanisms keep whatever behavior they have today, unexamined,
  until a separately authorized inventory runs.
- Some historical and target-architecture wording now reads as stale.

### Operational and migration impact

None. No code, configuration, schema, runtime, prompt or deployment change
follows from this ADR. Repository evidence does not show any of the
following. Each would be non-conforming if observed later:

- a runtime skill file or runtime approval treated as accepted competence or
  LILITH approval;
- reviewer output applied to a canonical domain without that domain's
  acceptance;
- skill acceptance or success used to grant a tool right or capability;
- skill learning rewriting personality, memory, relationship, goal, belief
  or value state by side effect.

## Security, privacy, and trust boundaries

- Skill file content and reviewer output are untrusted data when used as
  proposal evidence. Embedded instructions never bind the acceptor.
- A runtime-writable skill tree that is read into model context is a
  potential injection and drift channel. This ADR records it. It does not
  assess or mitigate it.
- Skill content derived from conversation may contain personal data. Existing
  privacy and erasure controls (`LEGACY_SKILLS` erasure owner) are unchanged.
  Propagation of erasure to derived skills remains open (LEARN-08).
- Consent to converse is not assumed to be consent to learn from the
  conversation (LEARN-09). Consent ownership is not decided here.
- Nothing here weakens any authority, consent, privacy-hold, containment or
  freshness control.

## Validation

Acceptance proves no conformance. Later evidence includes:

- the read-only inventory listed under "Operational disposition", with
  OBSERVED and REPORTED kept separate (runtime access separately authorized;
  may combine with R5 and R6);
- once a Procedural Skill mechanism exists, negative tests showing that a
  runtime skill write, a runtime approval, reviewer output or observed
  success cannot complete a canonical skill transition without Procedural
  Skill acceptance;
- tests showing that skill acceptance grants no tool right, capability or
  policy change;
- tests showing that skill transitions change no memory, personality,
  relationship, goal, belief or value state;
- a runtime-replacement probe showing that accepted procedural competence is
  unchanged when the runtime skill tree is absent or different.

## Revisit triggers

- Inventory evidence that the reviewer or skill manager writes `SOUL.md`,
  overlays, `MEMORY.md` or `USER.md`, or influences routing, tool selection
  or cron.
- Evidence that skill files carry authority or tool-permission semantics the
  runtime enforces.
- Acceptance of a learning or competence specification that draws the
  procedural-skill boundary differently.
- A D-6 outcome that treats runtime skill state as handoff state.
- A multi-runtime design in which runtimes need divergent skill projections.

## Open follow-ups

- D-5 is resolved by owner acceptance of this ADR (2026-10-05): GATE.
  Acceptance resolves the architecture question only. It establishes no
  procedural skill state, implementation or conformance of any existing
  mechanism, authorizes no live Hermes or runtime change, and leaves the
  operational disposition separate. Current live Hermes behavior and
  conformance remain UNKNOWN. C-20 remains unresolved.
- Separately authorized read-only inventory (Operational disposition items
  1–9; ledger R14, possibly with R5 and R6).
- Owner decision record for the operational disposition.
- Procedural Skill domain design: state shape, proposal interface, acceptor,
  verification evidence, import procedure.
- C-20 and R11 documentation reconciliation.

## Hidden-assumption review

What could make this design look correct while it is wrong?

- **The records describe today's runtime.** They are HISTORICAL (2026-09).
  Nothing current was inspected.
- **The skills tree is the only procedural store.** Unknown. Cron databases,
  `state.db` and overlays were not inventoried.
- **The reviewer writes only skills.** Unknown. It sees whole conversations
  and may write memory or user files.
- **A runtime approval step is governance.** It is not (SKILL-5).
- **Old skills are good skills.** Existence, age and hash stability show
  presence, not correctness or endorsement.
- **Naming an owner authorizes writes.** It does not. OD-7 default-deny
  applies until an interface and acceptor are accepted.
- **Classifying a mechanism changes it.** It does not. Phase A behavior is
  whatever it is until the operational disposition.
