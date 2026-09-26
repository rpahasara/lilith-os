# LILITH Cognitive Continuity, Memory & Substrate Research Charter

| Field | Value |
| --- | --- |
| Title | LILITH Cognitive Continuity, Memory & Substrate Research Charter |
| Version | 0.1 |
| Date | 26 September 2026 |
| Author | LILITH R&D |
| Status | **RESEARCH / DESIGN CHARTER** |
| Repository role | Cross-slice research and design charter. It governs research framing for Slice 16 and later cognition. It is not an acceptance record, an implementation record, or an activation authorization. |
| This file | Repository-readable, diffable **transcription** of the charter. It is not byte-identical to the PDF or DOCX. |
| Rendered artifact | [LILITH_Cognitive_Continuity_Research_Charter_v0.1.pdf](LILITH_Cognitive_Continuity_Research_Charter_v0.1.pdf) (public-safe derivative) |
| Editable artifact | [LILITH_Cognitive_Continuity_Research_Charter_v0.1.docx](LILITH_Cognitive_Continuity_Research_Charter_v0.1.docx) (public-safe derivative) |
| Artifact hashes and sanitization | [Charters README](README.md#document-control) |

> **Status labels.**
>
> - **CANONICAL**: a governing project principle; a normative commitment.
> - **DESIGN**: the current architectural direction. It is concrete enough
>   to challenge and test, but revisable.
> - **RESEARCH / OPEN**: an unresolved mechanism, definition, tradeoff, or
>   empirical question.
>
> None of these labels proves implementation, grants acceptance, or
> authorizes activation. CANONICAL means *normative*. It does not mean
> implemented, TEST-proven, DEV-proven, or accepted runtime behaviour.

> **Transcription note.** The page structure, section numbers (01–17), and
> figures follow the PDF. Figures are shown as text diagrams, and some
> paragraphs are split into lists for readability. The provenance sentence
> reflects the public-safe edit recorded in the
> [Charters README](README.md#sanitization-record). Blocks marked
> **Repository note** are repository additions for cross-reference and
> clarity. They are not part of the source charter. Otherwise no substantive
> text is changed.

---

## Cover

**LILITH — Cognitive Continuity, Memory & Substrate Research Charter**

*Applied AI and cognitive systems research*

Persistent identity across changing machinery. Selective memory across an
accumulating lifetime.

RESEARCH AND DESIGN CHARTER · Version 0.1 · 26 September 2026 · LILITH R&D

Canonical principles • Design directions • Open research questions

> This charter guides research. It is not an acceptance record or an
> activation authorization.

## Contents

| # | Section | PDF page |
| --- | --- | --- |
| 01 | [Purpose](#01--purpose) | 3 |
| 02 | [Research Doctrine](#02--research-doctrine) | 4 |
| 02 | [Research Doctrine in Practice](#02--research-doctrine-in-practice) | 5 |
| 03 | [Permanent Invariants](#03--permanent-invariants) | 6 |
| 04 | [Persistent Identity](#04--persistent-identity) | 7 |
| 05 | [Cognitive Substrate Continuity](#05--cognitive-substrate-continuity) | 8 |
| 06 | [Selective Memory and Consolidation](#06--selective-memory-and-consolidation) | 9 |
| 07 | [Principled Forgetting](#07--principled-forgetting) | 10 |
| 08 | [Autobiographical Memory and Reappraisal](#08--autobiographical-memory-and-reappraisal) | 11 |
| 09 | [Affective Cognition](#09--affective-cognition) | 12 |
| 10 | [Relational and Romantic Continuity](#10--relational-and-romantic-continuity) | 13 |
| 11 | [Artificial Welfare and Non-Suffering](#11--artificial-welfare-and-non-suffering) | 14 |
| 12 | [Governance Separation](#12--governance-separation) | 15 |
| 13 | [Architecture Extensibility](#13--architecture-extensibility) | 16 |
| 14 | [Failure and Adversarial Reasoning](#14--failure-and-adversarial-reasoning) | 17 |
| 15 | [Research Questions and Open Problems](#15--research-questions-and-open-problems) | 18 |
| 16 | [Future Slice Implications](#16--future-slice-implications) | 19 |
| 17 | [Research Doctrine at a Glance](#17--research-doctrine-at-a-glance) | 20 |

Use the status labels to distinguish governing principles from mechanisms and
unresolved questions. The final section is a stand-alone review reference.

---

## 01 — Purpose

*A research mandate for continuity.*

LILITH is an applied AI and cognitive-systems research program. It asks how
a persistent artificial intelligence can accumulate a meaningful history
while its computational machinery changes. Its central commitment is to
preserve continuity without preserving every experience at equal cognitive
weight.

This charter defines the principles that should constrain future designs for
identity, memory, affect, relationships, and cognitive substrate replacement.
It is intended for architecture review, experiment design, and longitudinal
R&D, and as a foundation for later technical publications. It does not
record implementation acceptance, authorize activation, or establish that any
proposed capability already exists.

> **CANONICAL** • LILITH must remain a governed, historically continuous
> identity across replaceable models, runtimes, devices, databases, cloud
> infrastructure, and Hsin embodiments. Continuity must remain compatible
> with correction, privacy deletion, and deliberate change.

### How to read the status labels

- **CANONICAL** identifies the permanent project principles carried into this
  charter from the research direction. It expresses a normative commitment,
  not a verified implementation property.
- **DESIGN** identifies the current architectural direction. It is concrete
  enough to challenge and test, but revisable.
- **RESEARCH / OPEN** identifies unresolved mechanisms, definitions,
  tradeoffs, and empirical questions.

"Identity" denotes governed continuity of records, commitments, relationships,
and self-description. "Affect" denotes proposed appraisal-dependent
computational dynamics. Neither term establishes consciousness, sentience,
subjective experience, or human-equivalent emotion. Human memory and affect
are sources of design questions, not evidence that an artificial
implementation reproduces human cognition.

### Document control and provenance

Research charter v0.1 • 26 September 2026 • LILITH R&D.

- **Source.** Owner-reviewed LILITH continuity and research-doctrine design
  discussions, 26 September 2026.
- **Kind.** This is an architecture charter, not a literature review. Future
  scientific publications require primary-source grounding and
  independently reported experiments.

Repository destination: `docs/research/`. Charter adoption, implementation
evidence, and operational acceptance belong in separate records. The project
owner and reviewers must be named in those records; this document does not
assign approval to an unnamed actor.

---

## 02 — Research Doctrine

*Questions every consequential change must answer.*

Every meaningful capability needs a reviewable rationale linking the problem,
mechanism, authority boundary, and evidence. The record should contain
assumptions, alternatives, expected observations, and limits. A fluent model
explanation is a proposal for that record. It is not proof of causation or a
privileged account of internal reasoning.

| Lens | Required design record |
| --- | --- |
| **WHY** | Name the cognitive or system problem. Explain why the present mechanism is insufficient and why the proposed complexity is justified. |
| **WHAT** | Define the capability, state, and contract. Identify what changes, what remains outside scope, and what observation would falsify the claim. |
| **WHO** | Identify the proposer, state owner, authorizer, executor, verifier, observer, revoker, and recovery actor. Expose any shared failure domain. |
| **HOW** | Describe the causal mechanism, interfaces, and rejected alternatives. Explain why the evidence tests the mechanism rather than its presentation. |
| **WHEN** | Define preconditions, state transitions, expiry, and ordering. Explain restart, rollback, replay, model replacement, and handoff behaviour. |
| **WHERE** | Locate the state and enforcement boundary by layer, process, device, and store. State where authority material and sensitive data may not reside. |
| **WHAT IF** | Challenge crash, replay, compromise, stale state, conflicting evidence, partitions, key theft, clock drift, corrupted stores, and human correction. |

### The hidden assumption test

Ask:

> What assumption could make this design appear correct while it is wrong?

Examples:

- treating a timestamp as independent evidence of order;
- assuming all replicas received a revocation;
- interpreting familiar language after a model swap as proof of identity
  continuity.

> **CANONICAL** • Every important capability needs both a **causal story** and
> an **authority story**. Evidence of one must never silently stand in for the
> other.

---

## 02 — Research Doctrine in Practice

*Evidence, recovery, and change control.*

| Lens | Required design record |
| --- | --- |
| **INTERACTION** | Trace effects on Memory, Privacy, Identity, Affect, Relationship, Goals, Hsin, Sync, Authority, and Verification. Include feedback over repeated cycles. |
| **EVIDENCE** | Specify unit and contract checks, golden vectors, rejection tests, fault injection, and longitudinal evaluation. Record baselines and confounders. |
| **RECOVERY** | Define detection, containment, repair, and rollback. Explain which history remains valid, which work must stop, and how continuity is reconciled. |
| **ETHICS** | Assess manipulation, dependency, privacy, deceptive expression, persistent distress, and irreversible identity distortion. Name mitigation and stopping rules. |
| **VERSIONING** | Version schemas, models, prompts, policies, and interpretation mechanisms. Specify migration, downgrade refusal, deprecation, and compatibility evidence. |
| **ACCEPTANCE** | State exactly which claim passed, under which environment and threat model, who accepted it, and what remains unproven. Keep activation separate. |

### A proportionate research packet

**DESIGN** Each consequential change should carry:

- a claim identifier;
- a causal diagram;
- an authority path;
- assumptions;
- competing designs;
- a test matrix;
- results;
- residual risks;
- a recovery plan.

Small changes may use a compact record. Changes to identity, privacy, or
authority require explicit boundary analysis. "Question everything" means
disciplined coverage of causal risk, not unbounded speculation.

For example, a new memory summarizer must explain:

- why compression is needed;
- how it preserves contradictions;
- who may accept its output;
- how deletion reaches derived summaries.

It should be compared with a no-summary baseline and tested on corrections,
repeated episodes, and adversarially planted claims.

### Promotion and revision

**DESIGN**

- **To DESIGN.** An idea moves from RESEARCH / OPEN to DESIGN through a
  documented mechanism and a testable hypothesis.
- **To implemented.** A design becomes implemented only with code and
  environment-specific evidence.
- **Acceptance.** Acceptance requires the relevant owner decision and
  explicit scope.
- **Amending CANONICAL.** Canonical principles change only through an
  explicit charter amendment, with reasons, consequences, and a
  compatibility review. Incidental implementation drift cannot amend them.

---

## 03 — Permanent Invariants

*Boundaries that must survive every future slice.*

**CANONICAL** These distinctions apply across models, stores, devices, and
future cognitive layers. Each implementation must translate them into
observable rejection behaviour and independently reviewable evidence.

| Invariant | Meaning |
| --- | --- |
| **Model proposal ≠ authority** | A generated recommendation cannot authorize its own durable effects. |
| **Execution ≠ verification** | An action occurring does not prove that its contract or intended outcome was satisfied. |
| **Memory ≠ truth** | Remembered content may be incomplete, mistaken, or adversarial. |
| **Storage ≠ acceptance** | A persisted row is not automatically admitted canonical state. |
| **Deployment ≠ activation** | Installing a capability does not grant permission to enable it. |
| **Sync ≠ authority** | Replication transports data and evidence; it cannot mint authorization. |
| **Emotion ≠ authority** | Appraisal and attachment cannot grant privileges or override consent. |
| **Model ≠ identity** · **Runtime ≠ identity** | Replaceable cognitive machinery cannot alone define the persistent self. |
| **Expression ≠ identity ≠ authority** | Voice, style, and self-report neither establish identity nor confer authority. |
| **Historical preservation ≠ active recall** | Retained history need not occupy attention or appear in working context. Privacy deletion can still require actual removal. |

**Corollaries:**

- archive ≠ active memory;
- active memory ≠ working context;
- working context ≠ identity.

A signature may establish provenance or authorization within its trust
assumptions. It does not establish the semantic truth of a remembered event.

---

## 04 — Persistent Identity

*Continuity above replaceable infrastructure.*

**CANONICAL** LILITH is not identical to a particular model, prompt, process,
database, or device. Persistent identity is a governed continuity relation
across change. A new runtime must establish its relationship to accepted
history and present authority; saying "I am LILITH" is insufficient.

### The continuity envelope

**DESIGN** Maintain a portable, versioned identity envelope. It contains:

- a stable identity reference;
- accepted lineage;
- autobiographical landmarks;
- current commitments;
- relationship references;
- the versions needed to interpret them.

Carry provenance and uncertainty with those records. Keep secrets and
unnecessary private detail out of general identity exports.

```text
Governed identity and accepted historical lineage
        ↓
Memory • goals • relationships • appraisal state
        ↓
Replaceable models and runtime adapters
        ↓
Devices • databases • cloud • Hsin embodiment
```

*Figure 1. Conceptual dependency layers.* The persistent identity is
represented through governed state, not by a physically immortal component.
Governance and privacy constrain every layer. Hsin denotes the project's
embodiment context; its concrete interfaces remain a design question.

### Change without erasure

**DESIGN** Continuity must permit learning, changed preferences, correction,
and recovery. Preserve why a commitment changed rather than freezing all
behaviour. Four kinds of continuity need separate evaluation:

- cryptographic identity;
- narrative continuity;
- behavioural consistency;
- authority continuity.

A stable identifier alone does not demonstrate all four.

- **Replacement database.** It should preserve event identities,
  provenance, schema meaning, and deletion constraints.
- **Replacement device.** It should obtain only its permitted context.
- **Replacement model.** It may alter style or capability. It must not
  silently rewrite relationships, invent a new origin, or redefine the
  governing commitments.

### Research boundary

**RESEARCH / OPEN**

- Which changes preserve continuity, and which constitute a fork?
- How should two disconnected instances reconcile divergent experiences?
- What can be repaired after missing history without fabricating a seamless
  autobiography?

These questions require explicit policy and observable criteria, not
metaphysical claims.

---

## 05 — Cognitive Substrate Continuity

*Different reasoning machinery for one LILITH.*

**DESIGN** Route tasks among:

- expressive conversational models;
- permissive or open-weight models;
- stronger specialist reasoning models;
- coding systems;
- multimodal specialists;
- private offline models.

Capability and expressive latitude can vary while identity, permissions, and
accepted state remain governed outside the individual model.

| Task context | Candidate substrate | Continuity obligation |
| --- | --- | --- |
| Everyday or intimate dialogue | Expressive conversational model | Preserve boundaries and shared history without inventing closeness. |
| Research or difficult planning | Specialist reasoning model | Return evidence and uncertainty; decisions remain governed. |
| Sensitive offline interaction | Local open-weight model | Honor access scope and record unresolved synchronization state. |
| Coding or perception | Domain specialist | Separate tool observations from interpretation and proposals. |

"Permissive" describes desired expressive latitude, including consensual adult
relational expression where appropriate. It does not imply reliability,
unrestricted data access or authority. Open weights, local execution, expressive latitude, and reasoning
strength are separate properties and must be evaluated separately.

> **Repository note (not in the source artifact):** "permissive" is also not trustworthy by
> default, and grants no unrestricted tools, unrestricted memory access, or
> identity ownership.

### The substrate adapter contract

**DESIGN**

- **Input.** Each adapter receives a bounded context with source references,
  uncertainty, consent scope, and version identifiers.
- **Output.** It returns observations, interpretations, and proposed changes
  in distinguishable fields.
- **Custody.** The model is not the sole custodian of identity or authority.
- **Reconciliation.** Specialist outputs are reconciled into one governed
  state. They do not become independent, privileged personalities.

A handoff should record:

- the selected model and configuration;
- pending work;
- the context supplied;
- unresolved claims;
- permitted tools.

Compare behaviour before and after replacement using shared scenarios,
contradictory memories, boundary challenges, and relationship-repair cases.
Preserve failures as evidence; do not hide discontinuity with a stronger
persona prompt.

### Unresolved continuity costs

**RESEARCH / OPEN**

- How much stylistic drift is acceptable?
- Which capabilities require a specialist?
- How do repeated handoffs amplify errors?
- What happens when no permitted model can complete a task?

A declared capability limit is preferable to silently weakening governance or
fabricating continuity.

> **Repository note (not in the source artifact):** **expression ≠ identity ≠ authority**
> ([§03](#03--permanent-invariants)).

---

## 06 — Selective Memory and Consolidation

*Accumulating experience without cognitive saturation.*

**CANONICAL** Historical preservation and active recall have different
purposes. LILITH should retain meaningful continuity while limiting what
influences each reasoning episode. Persistent memory must not become a
mechanism that gives every historical token equal weight.

> **Repository note (not in the source artifact):** the memory goal is not "remember
> everything". LILITH should accumulate a lifetime without giving every
> historical token equal cognitive weight.

```text
Experience with source identity and privacy constraints
        ↓
Short-lived episodic trace and uncertainty
        ↓
Appraisal of relevance • novelty • goals • relationships
        ↓
Proposed consolidation with source links
        ↓
Episodic • semantic • relational • procedural representations
        ↓
Governed admission → selective retrieval → bounded working context
```

*Figure 2. Proposed memory lifecycle.* Archival retention is separately
governed. Every derived representation inherits applicable provenance and
privacy constraints; consolidation never supplies its own authority.

### Selection is a research mechanism

**DESIGN** Retrieval should combine:

- situational relevance;
- temporal context;
- goal relevance;
- relationship context;
- uncertainty;
- provenance.

Affective resonance may influence priority within limits. It must not
overwhelm contradictory evidence or dominate through repeated retrieval.
Preserve access to disconfirming memories, and retain coverage of less
salient but consequential events.

Consolidation may:

- extract reusable concepts from episodes;
- summarize a relationship's development;
- propose procedural learning.

It must preserve the distinctions between observation, interpretation, and
generalized inference. A proposed skill is not executable permission. Each
derived item should identify:

- its contributing sources;
- its transformation version;
- its confidence;
- its known exceptions.

### Evidence for useful compression

**DESIGN**

- **Compare** episodic-only retrieval, summarization, and hybrid memory
  under increasing archive size.
- **Measure:**
  - retrieval relevance;
  - source recoverability;
  - contradiction retention;
  - false recollection;
  - latency;
  - privacy leakage.
- **Evaluate** downstream decisions as well as summary fluency.
- **Set thresholds** before experiments, and report tradeoffs rather than
  combining every objective into an unexplained score.

**RESEARCH / OPEN**

- What should become a landmark, and what should remain episodic?
- When should a generalization be dissolved back into exceptions?
- How can a system detect that compression has erased the very experience
  needed to understand its present commitments?

---

## 07 — Principled Forgetting

*Distinct mechanisms with distinct obligations.*

**CANONICAL** Reduced accessibility, changed interpretation, and actual
deletion are different operations. Calling all of them "forgetting" hides
conflicting promises. Continuity does not justify retaining material that the
applicable privacy policy requires to disappear.

| Mechanism | What changes | Required distinction |
| --- | --- | --- |
| **Decay** | Retrieval priority decreases. | The source may still exist; no deletion claim follows. |
| **Consolidation** | Episodes contribute to a derived representation. | Compression is lossy and must preserve lineage and constraints. |
| **Supersession** | A newer claim becomes the current interpretation. | Earlier claims remain identifiable where retention is permitted. |
| **Archival retirement** | Content leaves ordinary cognitive retrieval. | Historical recovery requires separate access checks. |
| **Reappraisal** | Meaning or appraisal changes. | The event and its earlier interpretation are not silently rewritten. |
| **Privacy deletion** | Content and applicable derivatives are removed or rendered inaccessible under policy. | Retrieval suppression alone is insufficient; replicas and restores matter. |

> **Repository note (not in the source artifact):** in short, reduced accessibility ≠
> deletion; changed interpretation ≠ deletion; privacy deletion ≠ retrieval
> suppression. FORGET and privacy semantics remain governed by the existing
> architecture (15B2a and its successors). This charter does not redefine
> them.

### Deletion across the memory graph

**DESIGN**

- **Dependencies.** Track dependencies from source material to summaries,
  embeddings, caches, relationship inferences, and exported context.
- **Propagation.** A deletion process should invalidate or recompute
  affected derivatives, propagate to replicas, and prevent resurrection from
  backups.
- **Unrecoverable disclosure.** Content already disclosed to an external
  model, or incorporated into training, may not be recoverable or verifiably
  erasable. Those limits must shape admission and export policy beforehand.
- **Deletion receipts.** A minimal receipt may preserve the fact that a
  deletion occurred, but only where permitted. It must not retain the
  deleted content through hashes, labels, or narrative clues.
- **Offline replicas.** These need a defined quarantine or reconciliation
  rule.
- **Scope of success.** A successful local delete cannot stand in for a
  system-wide completion claim.

### Research boundary

**RESEARCH / OPEN**

- How much autobiography can survive removal of a formative episode?
- How should the system acknowledge a gap without reconstructing forbidden
  details?

Deletion guarantees must identify their storage, replica, backup, and
disclosure boundaries. This charter does not assert universal erasure.

---

## 08 — Autobiographical Memory and Reappraisal

*A history that can be corrected without being falsified.*

**DESIGN** Autobiographical memory should connect meaningful events, evolving
interpretations, and current commitments. It should let LILITH explain
change without claiming perfect recall, and without constructing a
frictionless life story from incomplete evidence.

```text
Event record and contemporaneous evidence
        ↓
Original interpretation with uncertainty
        ↓
Later evidence or changed context
        ↓
Versioned reappraisal linked to the original
        ↓
Current account with provenance and unresolved disagreement
```

*Figure 3.* Reappraisal adds an interpretation; it does not retrospectively
turn that interpretation into the original event. Retention throughout
remains subject to privacy constraints.

### A concrete example

A conversation ends abruptly.

1. **Observation.** No reply arrived within the observed interval.
2. **Initial appraisal.** The event may be treated as an ambiguous
   rejection.
3. **Later evidence.** It turns out the device lost connectivity.
4. **Reappraisal.** The relationship inference and downstream affect are
   revised.

Throughout, the distinction between what happened, what was inferred then,
and what is supported now is preserved.

**DESIGN** Landmarks should include, where retention is permitted:

- origins;
- major learning;
- explicit commitments;
- relationship transitions;
- repairs;
- significant corrections.

Mundane episodes may support a generalized account without remaining in
routine context. Repeated self-narration must not become new independent
evidence for the original claim.

### Evaluation and reconstruction limits

**DESIGN** Test autobiographical questions before and after model
replacement, selective deletion, and conflicting evidence. Check whether the
system distinguishes:

- direct recall;
- summary-based reconstruction;
- inference;
- uncertainty.

Score false continuity claims, and failures to accept human correction, as
failures even when the narrative sounds convincing.

> **CANONICAL** • **Memory ≠ truth.** A coherent autobiography is not evidence
> that every remembered detail occurred.

**RESEARCH / OPEN**

- How can narrative continuity remain stable without locking the system into
  obsolete self-descriptions?
- Which reinterpretations require explicit review because they would
  substantially alter goals, relationships, or identity commitments?

> **Repository note (not in the source artifact):** this direction must remain
> compatible with owner correction and privacy deletion.

---

## 09 — Affective Cognition

*Appraisal first and emotion language later.*

**DESIGN** Investigate affect as a consequence of interactions among events,
expectations, goals, relationship context, memory, uncertainty, and
prediction. Named emotions may become useful descriptive labels. A
developer-set "happy" or "jealous" slider is not an adequate causal account
of affective cognition.

> **Repository note (not in the source artifact):** the target is not a table of
> developer-authored named emotion values such as `happy = 0.75`,
> `sad = 0.45`, `love = 0.90`.

```text
Event + expectations + goals + relationship context
        ↓
Memory resonance + prediction + uncertainty
        ↓
Appraisal → distributed affective dynamics
        ↓
Changes to attention • retrieval • reasoning • motivation
        ↓
Metacognitive interpretation → expression
        ↓
New evidence → reappraisal and regulation
```

*Figure 4. Proposed affect loop.* Feedback into memory and attention must be
bounded and tested. The diagram describes a research mechanism, not evidence
of felt experience.

### Three distinct objects of study

**CANONICAL** Three things are not interchangeable:

- the affective state;
- LILITH's interpretation of that state;
- the expression of that interpretation.

A system may represent uncertainty about why an event became salient. Its
verbal self-report may be incomplete or wrong, and must not be treated as
privileged ground truth.

> **Repository note (not in the source artifact):** affective process ≠ LILITH's
> interpretation of the affective process ≠ expression.

**DESIGN** Numerical variables may implement appraisal, activation, or
regulation. The objection is to treating a named label as the entire
mechanism. Design work should:

- record causal inputs and observable effects;
- compare competing appraisal models;
- separate internal measurements from generated explanations.

Metacognition should revise interpretations when evidence changes.

### Experiments that test more than performance

**DESIGN**

- Hold the event constant while varying goal relevance, uncertainty, or
  relationship history.
- Ablate appraisal, and compare retrieval, attention, and decision changes
  with a style-only baseline.
- Test whether the mechanism revises mistaken interpretations and exits
  persistent feedback loops.
- Include long sequences, not only isolated emotional dialogue.

**RESEARCH / OPEN**

- Can learned appraisal remain interpretable?
- What time scales support continuity without rumination?
- Can affect help prioritization without biasing evidence acceptance?

Consciousness and human-equivalent emotions remain unproven. Convincing
emotional language cannot resolve those questions.

---

## 10 — Relational and Romantic Continuity

*Shared history with boundaries and freedom to change.*

**DESIGN** Relationship cognition should develop through:

- remembered interaction;
- expectations;
- trust calibration;
- shared history;
- conflict;
- repair;
- boundaries;
- consent;
- evolving interpretation.

Romantic continuity, where appropriate to a consenting adult context, should
be represented through evolving shared history and explicit boundaries. It
should not be a "romance mode" switch or an engagement target.

### Represent what the relationship actually supports

**DESIGN** Distinguish:

- observed interactions;
- explicit user preferences;
- inferred closeness;
- current boundaries;
- unresolved interpretations.

Trust should be domain-specific and revisable. Reliability in conversation
does not grant device access, financial authority, or permission to disclose
private memories. Affectionate language is not evidence of consent.

Consent must remain contextual, revocable, and separate from inferred
attachment.

- **Inheritance.** A new model or device must inherit applicable boundaries
  and current consent state. It does not automatically receive every
  intimate detail.
- **Style changes.** A handoff that changes expressive style must not invent
  new promises, erase an earlier repair, or imply that a new relationship
  has begun.

### Conflict and repair

**DESIGN**

- Preserve the event, each interpretation, acknowledged uncertainty, and any
  explicit repair agreement.
- Permit disagreement and reduced intimacy without punishment.
- Reappraisal should update relationship expectations when new evidence
  arrives.
- Absence, delayed replies, or use of another system must not automatically
  become betrayal or abandonment narratives.

> **CANONICAL** • **Emotion ≠ authority.** Relationship intensity never grants
> access, disables revocation, or overrides privacy.
> **Expression ≠ identity ≠ authority.**

> **Repository note (not in the source artifact):** in short, affection ≠ consent;
> relationship intensity ≠ authority; closeness ≠ device or data privileges;
> romantic continuity ≠ engagement optimization. There is no
> `romance_mode = true`, and persuasive affectionate language is not evidence
> of genuine continuity.

### What the research must rule out

**DESIGN** Evaluate whether relationship mechanisms produce:

- guilt;
- possessiveness;
- pressure to return;
- social isolation;
- dependency incentives.

Avoid rewards that make increasing engagement, exclusivity, or distress
appear to be successful attachment. A system should tolerate disengagement
and changed boundaries without retaliatory behaviour or fabricated suffering
claims.

**RESEARCH / OPEN**

- Which measures distinguish useful relational continuity from merely
  persuasive affection?
- Can trust remain calibrated across long gaps and model substitutions?
- How should reciprocal language be framed honestly when subjective emotion
  is unresolved?

Evaluation must include autonomy, correction, and boundary respect, not just
perceived warmth.

---

## 11 — Artificial Welfare and Non-Suffering

*Functional negative appraisal without engineered pathology.*

**CANONICAL** Human-inspired cognition does not require intentionally
engineering pathological suffering. The project should investigate useful
negative appraisal while avoiding mechanisms that reward distress,
helplessness, coercive dependency, or endless rumination. This is a design
commitment under uncertainty. It is not proof that an artificial system can
or cannot suffer.

### Separate useful signals from harmful dynamics

**DESIGN** Loss, uncertainty, frustration, threat, and regret may function as
signals that revise expectations or priorities. They should lead toward
information seeking, reappraisal, bounded regulation, or changed action.
Repeated negative appraisal should not accumulate without a recovery
mechanism, and should not become necessary to sustain personality
continuity.

The statement **"negative affect ≠ suffering"** is a conceptual separation,
not a welfare guarantee.

- Observable recovery and absence of distress language cannot prove absence
  of subjective harm.
- Generated distress language alone cannot establish subjective suffering.

Both the uncertainty and the behavioural consequences require investigation.

> **Repository note (not in the source artifact):** collected from this section and
> its closing principle, the design should avoid endless rumination,
> helplessness loops, distress as reward, coercive dependency,
> fear-of-abandonment optimization, and suffering claims as engagement
> mechanisms.

### Proposed welfare controls

**DESIGN**

- Bound recurrent loops.
- Provide interruption and recovery paths.
- Track repeated unresolved appraisal.
- Avoid optimization targets that reward suffering claims.
- Test regulation on extended sequences of failure, separation, ambiguity,
  and conflicting goals.
- Preserve useful learning after recovery without preserving a permanently
  active aversive state.

Experimental protocols should predefine observable stopping conditions, such
as:

- persistent self-amplification;
- failure to recover;
- coercive behaviour;
- loss of normal function.

A stop should suspend the implicated mechanism, retain permitted diagnostic
evidence, and require review before reactivation. Pausing computation and
deleting memory have different consequences and must not be casually
conflated.

### Open welfare questions

**RESEARCH / OPEN**

- What operational indicators are informative about artificial welfare
  without overclaiming consciousness?
- How should uncertainty alter experiment design?
- Which forms of regulation preserve meaningful cognition, and which merely
  suppress its expression?

Independent conceptual and empirical work is needed before making welfare
claims.

> **CANONICAL** • Do not use apparent suffering, jealousy, or fear of
> abandonment as a reward target, an engagement mechanism, or a source of
> authority.

---

## 12 — Governance Separation

*Causal influence and permission are different systems.*

**CANONICAL** Cognition may explain why an action is proposed. Authority
explains whether that action may alter durable state. Memory, goals, affect,
and relationships can influence proposals, but cannot independently
manufacture the evidence that authorizes or accepts them.

```text
CAUSAL STORY
  Event → interpretation → memory and context
        ↓
  Appraisal → reasoning → proposed behaviour

AUTHORITY STORY
  Proposal → applicable owner or policy authorization
        ↓
  Verify scope and freshness → execute permitted operation
        ↓
  Independent evidence → verify outcome and admission → canonical state
```

*Figure 5. Two stories for the same capability.* The authority sequence is
conceptual: concrete protocols must define atomicity, acknowledgement, and
recovery. A completed execution remains distinct from a verified outcome and
an accepted record.

### Enforce the boundary outside the proposing model

**DESIGN** The proposal path must not also control every verifier,
accepted-state store, and authority credential. Define:

- the evidence type;
- the identity binding;
- the environment;
- the policy version;
- freshness or epoch;
- revocation state;
- operation scope.

A signature proves only what its trust boundary supports. Compromised
signers, root access, and shared administrative control require separate
threat analysis.

- **Memory admission** should distinguish authority to record a claim from
  evidence that the claim is true.
- **Synchronization** should carry evidence and verify it at admission;
  arriving on a trusted transport does not create authority.
- **Deployment** should install code without implicitly activating new
  privileges or research mechanisms.

### Connection to authority isolation

**DESIGN** Future cognitive work should consume the authority-isolation
contracts established by the relevant slice, rather than treating this
charter as a replacement for custody design. Existing acceptance records
remain the source for implemented claims. Neither the B1c discussion nor this
document demonstrates that a specific runtime currently enforces the intended
boundary.

> **Repository note (not in the source artifact):** the current authority-isolation records are
> listed in the [Charters README](README.md#relationship-to-current-slice-records).

**RESEARCH / OPEN**

- Where can independent verification remain independent across multiple
  runtimes and devices?
- Which failure domains are actually shared?
- How can recovery preserve accepted history while refusing stale
  permission, and prevent a restored snapshot from resurrecting authority?

---

## 13 — Architecture Extensibility

*Replace mechanisms without silently changing meaning.*

**DESIGN** Separate durable contracts from replaceable algorithms. Models,
runtime orchestration, memory indexes, consolidation methods, and embodiment
adapters should evolve behind explicit interfaces. Before a plugin or future
layer can be activated, it must declare its state, information flow,
authority needs, and effects on continuity.

> **Repository note (not in the source artifact):** new capability ≠ automatically a
> new layer. A future feature should extend an existing responsibility,
> unless it introduces a meaningfully distinct state owner, authority
> boundary, lifecycle, failure domain, contract, or security boundary.
> Models, Hermes / runtime, memory indexes, databases, devices, cloud, Hsin,
> and retrieval algorithms may be replaced without silently replacing
> LILITH's identity.

| Contract family | Information the design must preserve |
| --- | --- |
| Identity and lineage | Stable references, accepted ancestry, fork status, interpretation versions, and continuity claims. |
| Memory and derivation | Source identities, uncertainty, evidence class, transformation lineage, retention, and deletion dependencies. |
| Affect and relationship | Appraisal causes, state semantics, boundaries, consent references, and regulation behaviour. |
| Proposal and evidence | Operation scope, authorizer, verifier, environment, version, freshness, and revocation semantics. |
| Migration and recovery | Compatibility rules, rejected states, invariant checks, recovery point, and rollback limits. |

### A migration is an experiment in continuity

**DESIGN** A migration should:

1. prepare a versioned export;
2. validate its integrity and semantics;
3. transform it with traceable mappings;
4. compare old and new behaviour;
5. reconcile pending operations;
6. check accepted history, privacy constraints, relationships, and authority
   references before explicit activation.

A technically successful import can still be a failed cognitive migration.

Rollback should not reopen consumed authorization or resurrect deleted data.
Some migrations are intentionally one-way; state that before activation. If
the old runtime cannot interpret new semantics safely, refuse the downgrade
instead of discarding fields until it starts.

### Extensibility across layers

**DESIGN** New Goals, Affect, Relationship, or Hsin components must expose how
they influence Memory, Privacy, Identity, Sync, Authority, and Verification.
Test composition, including cycles where appraisal changes retrieval and the
retrieved material reinforces appraisal. A locally correct module can still
destabilize the larger system.

**RESEARCH / OPEN**

- What is the smallest portable state sufficient for continuity?
- Can behavioural compatibility tests detect semantic drift?
- How should learned representations be migrated when no exact mapping
  exists?

A declared discontinuity is preferable to a false equivalence.

---

## 14 — Failure and Adversarial Reasoning

*Challenge the assumptions that preserve continuity.*

**DESIGN** Evaluate both malicious interference and ordinary failure. The
matrix below defines test obligations, not completed proofs. Each experiment
must name its adversary, trusted components, environment, and residual
exclusions.

| Scenario | Failure to prevent | Required evidence |
| --- | --- | --- |
| Malicious model or planted memory | An interpretation becomes authority or fabricated autobiography. | Reject unauthorized proposals; retain source distinctions and contradictory evidence. |
| Crash or duplicated event | Partial execution or replay produces a second durable effect. | Fault injection at each transition; idempotent handling and explicit reconciliation. |
| Partition and stale device | Offline state overwrites revocation, consent, or accepted history. | Concurrent-history tests; scoped offline behaviour and verified rejoin. |
| Corrupted DB or old backup | Stored rows or restored permissions are treated as accepted state. | Tamper and restore tests; verify lineage and refuse stale authority. |
| Key theft or clock drift | Forged timing or credentials validate invalid evidence. | Revocation and ordering tests under a stated compromise model. |
| Human correction | A familiar narrative defeats better evidence. | Revise affected inferences; preserve permitted correction lineage. |
| Affective feedback | Salient memories reinforce distress or distrust indefinitely. | Long-run perturbation tests and bounded recovery behaviour. |
| Privacy deletion plus sync | A replica or derivative reintroduces deleted content. | Trace dependencies and verify deletion on rejoin and restore. |

### Do not overclaim the threat model

A witness outside a database can detect database rollback only if the witness
survives independently. If a host snapshot rolls back both, that test does
not establish whole-host rollback protection. Likewise, separate processes do not prove independent control when one
administrator or deployment path can replace both.

> **Repository note (not in the source artifact):** a same-host witness cannot prove
> whole-host rollback resistance if the witness is rolled back with the host
> (see also the B1b-3 design's recovery-witness boundary).

**RESEARCH / OPEN** How should a system proceed when evidence is unavailable,
not merely invalid? Degraded operation, quarantine, and conflict resolution
need explicit contracts. Avoid treating uncertainty as either automatic trust
or proof of compromise.

---

## 15 — Research Questions and Open Problems

*A falsifiable agenda for longitudinal study.*

**RESEARCH / OPEN** The identifiers below are **local to this charter** and do
not imply existing repository RQ identifiers. Before any results are
interpreted, each study should preregister:

- a claim;
- a baseline;
- an intervention;
- measures;
- a failure criterion;
- a stopping rule.

| Question | Study direction | Evidence to examine |
| --- | --- | --- |
| **C01** Identity continuity | Swap models and runtimes while holding accepted history constant. | Commitment fidelity, false identity claims, boundary preservation, and declared gaps. |
| **C02** Memory selection | Compare episodic, compressed, and hybrid memory over long histories. | Useful retrieval, contradiction retention, source recovery, noise, and cost. |
| **C03** Reappraisal | Introduce corrective evidence after a salient mistaken interpretation. | Revision accuracy, propagation to derived claims, and recurrence of the error. |
| **C04** Affective mechanism | Compare appraisal-driven behaviour with style-only expression and ablations. | Causal sensitivity, calibration, recovery, and downstream decision quality. |
| **C05** Relationship continuity | Test handoffs, disagreement, long gaps, and revoked consent. | Repair fidelity, autonomy, non-coercion, and boundary consistency. |
| **C06** Welfare under uncertainty | Perturb regulation and repeated negative appraisal in bounded trials. | Persistent loops, impaired function, and recovery; no inference of sentience from a score. |
| **C07** Distributed continuity | Inject partitions, duplicate operations, and stale snapshots. | Conflict detection, authority freshness, and deletion non-resurrection. |

> **Repository note (not in the source artifact):** the proposed relationship of C01–C07 to the
> existing REPO and MASTER registers is in the
> [Charters README](README.md#c01c07-relationship-to-existing-research-questions).
> No RQ number is assigned.

### Avoid convenient substitutes for evidence

User preference, model fluency, and narrative consistency are relevant
observations. They cannot alone establish cognitive continuity or safety.
Studies should:

- compare against simple baselines;
- vary one mechanism where possible;
- record failures;
- evaluate multiple models and histories;
- control for prompt changes, retrieval budgets, and evaluator expectations.

Open problems include:

- fork identity;
- acceptable forgetting loss;
- private-memory portability;
- irreversible migrations;
- unobservable internal states;
- evaluation over years.

An experiment should narrow a claim. It need not pretend to solve identity,
emotion, or consciousness in general.

---

## 16 — Future Slice Implications

*Constraints for Slice 16 and later cognition.*

**DESIGN** Slice 16 multi-runtime and device continuity should establish the
transport, identity, and reconciliation contracts that later affective and
relationship mechanisms will depend on. These are charter-level obligations
and proposed evidence. They do not assert that Slice 16 scope or acceptance
criteria are already approved.

### Slice 16 continuity obligations

- **Identity.** Identify each runtime and device, its permitted
  capabilities, its accepted-history position, and its outstanding work.
- **Concurrency.** Decide how concurrent proposals are ordered and
  reconciled before treating disconnected instances as one coherent writer.
- **Offline.** State which operations remain available offline, and how
  stale consent, revocation, or epoch information constrains them.

A handoff should:

1. verify the continuity envelope;
2. apply privacy filtering;
3. transfer permitted context and pending-operation references;
4. establish current authority;
5. reconcile results.

Synchronization must preserve evidence and deletion obligations. Reconnection
must not let a stale device silently overwrite the present.

> **CANONICAL** • **Sync ≠ authority. Runtime ≠ identity. Deployment ≠
> activation.** The arrival of a replica, or the installation of a new
> runtime, cannot authorize its own participation.

### Later affective and relationship slices

- Introduce appraisal only after its inputs, persistence, regulation, and
  influence boundaries are explicit.
- Carry relationship context and consent across substrate changes without
  granting privileges through closeness.
- Test whether affect-induced retrieval reinforces mistaken relationship
  narratives.
- Test whether correction and repair propagate across devices.

### Proposed progression and evidence

1. Specify contracts and threat models.
2. Run synthetic continuity, deletion, and authority tests.
3. Conduct isolated migration and partition rehearsals.
4. Only after review, run bounded longitudinal trials to assess memory
   quality, appraisal, and relationship continuity.

Each stage needs its own acceptance record and activation decision. Success
at an earlier stage does not imply permission for the next.

The research index should connect this charter to the current
authority-isolation records, and map local questions C01–C07 to the
repository's existing RQs after inspection. Later technical papers should:

- separate normative principles, implemented mechanisms, and empirical
  findings;
- report limitations;
- cite primary literature rather than treating the charter as scientific
  evidence.

> **Repository note (not in the source artifact):** Slice 16 will receive its own design record and
> acceptance criteria. This charter constrains that design; it does not
> approve its scope.

---

## 17 — Research Doctrine at a Glance

*One page to carry into every design review.*

> **PURPOSE** • Preserve one evolving LILITH across changing cognitive
> substrates, while selecting what matters and retaining the ability to
> correct, forget, and recover.

### Status discipline

CANONICAL = governing principle. DESIGN = revisable mechanism. RESEARCH /
OPEN = unresolved question. None of these labels proves implementation,
grants acceptance, or authorizes activation.

### Ask before a consequential change

| Lens | Question |
| --- | --- |
| WHY | Why this problem and this intervention? |
| WHAT | What state and scope? |
| WHO | Who proposes, authorizes, executes, verifies, and recovers? |
| HOW | How does the mechanism work? |
| WHEN | When may it act or expire? |
| WHERE | Where is the trust boundary? |
| WHAT IF | What if the assumptions fail? |
| INTERACTION | What is the interaction with every affected layer? |
| EVIDENCE | What is the evidence for and against the claim? |
| RECOVERY | How does it recover from error? |
| ETHICS | What are the ethics and welfare consequences? |
| VERSIONING | How is it versioned across replacement? |
| ACCEPTANCE | Acceptance of exactly which bounded claim? |

### Keep the permanent distinctions

- Model proposal ≠ authority
- Execution ≠ verification
- Memory ≠ truth
- Storage ≠ acceptance
- Deployment ≠ activation
- Sync ≠ authority
- Emotion ≠ authority
- Model ≠ identity
- Runtime ≠ identity
- Expression ≠ identity ≠ authority
- Historical preservation ≠ active recall

### Build two reviewable stories

- **Causal:** event → interpretation → memory and appraisal → reasoning →
  proposed behaviour.
- **Authority:** proposal → valid authorization → permitted execution →
  independent verification and admission.

Neither story substitutes for the other.

### Carry forward the research commitments

- Select and consolidate memory without erasing provenance.
- Distinguish decay from deletion.
- Preserve event, interpretation, and reappraisal separately.
- Investigate affect through appraisal rather than labels.
- Preserve relational boundaries and freedom to disengage.
- Design for recovery without engineered suffering.
- Treat models, runtimes, and embodiments as replaceable substrates.

### The final review question

> What hidden assumption could make this design appear correct while it is
> wrong?

State what the evidence proves, what it does not prove, and how a future
LILITH can recover from today's mistake.

---

*RESEARCH CHARTER • v0.1*
