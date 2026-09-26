# Research Question Register

This register captures the hard questions that shape LILITH as autonomy, persistence, and runtime diversity increase. Rows are intentionally concise; an issue or experiment note should hold detailed protocols and results.

Status meanings are defined in the [research method](method.md). “Designed” means a proposed answer exists—not that it is implemented or correct.

## Register provenance and numbering (added 2026-09-26)

- **Origin.** All fifty rows below were created in commit `1eee09b`
  (2026-09-13, "chore: establish LILITH repository foundation") and were not
  modified until this note. The wording and **Status** column below are the
  original historical record and must not be rewritten; later evidence is
  recorded separately.
- **Current evidence.** Per-question evidence, a proposed evidence-assessed
  maturity, and what remains unknown are in the [RQ evidence map](rq-evidence-map.md).
  Proposed changes there take effect only when accepted in a pull request.
- **Numbering.** This register's numbers are **not** the numbering of the
  out-of-repo Architecture & Research Master v1.1 (RQ-001–RQ-121). The same
  number can name a different question in the two registers. See the
  [numbering reconciliation](rq-numbering-reconciliation.md). ADRs cite this
  register's numbers. Do not assign RQ-051 or later until the owner decides
  how the two registers relate.
- **Master archived (2026-09-26).** Both Master editions are now archived
  under [source-material/originals](source-material/originals/). Cite this
  register as `REPO:RQ-NNN` and the Master as `MASTER:RQ-NNN`; the
  [REPO ↔ MASTER crosswalk](rq-register-crosswalk.md) classifies every pair.
  Only RQ-001 means the same question in both.

## Priority questions

The first evaluation wave should focus on the questions with the highest architectural leverage:

1. **RQ-001 identity invariant** — defines what must survive all replacements.
2. **RQ-004 canonical multi-runtime state** — prevents split identity and duplicated action.
3. **RQ-009 memory admission** and **RQ-010 consolidation** — govern what becomes durable belief.
4. **RQ-026 risk calibration** and **RQ-030 emergency authority** — bound consequential autonomy.
5. **RQ-033 unknown execution state** and **RQ-035 verification independence** — prevent unsafe retries and false success.
6. **RQ-044 evaluation suite** — determines whether LILITH is improving rather than merely changing.

## Identity and continuity

| ID | Research question | Current hypothesis / architectural direction | Status | Next evidence-producing step |
| --- | --- | --- | --- | --- |
| RQ-001 | What fundamentally makes LILITH the same LILITH after components are replaced? | A versioned identity charter, relationship history, governed durable state, commitments, policy, and provenance form the invariant—not a model or runtime. | RESEARCH | Define continuity scenarios and a minimum-state restoration test. |
| RQ-002 | How much identity change is evolution versus replacement? | Identity changes need explicit versioning, migration rationale, and user-visible continuity boundaries. | UNKNOWN | Build a rubric for gradual drift, intentional change, corruption, fork, and restoration. |
| RQ-003 | Can an old state be restored without creating a competing identity? | Restore should preserve lineage and record a branch/rollback event rather than pretend intervening history never existed. | RESEARCH | Model restore, fork, merge, and revocation semantics. |

## Runtime independence and synchronization

| ID | Research question | Current hypothesis / architectural direction | Status | Next evidence-producing step |
| --- | --- | --- | --- | --- |
| RQ-004 | How can one identity operate across Hermes, local, and cloud runtimes? | Runtimes are clients of a canonical LILITH state plane using revisions, operation IDs, and explicit conflicts. | DESIGNED | Prototype two runtime adapters against a synthetic canonical store. |
| RQ-005 | Does multi-runtime execution require a leader, leases, or capability-level ownership? | Coordination may vary by state class and side-effect risk; one universal consistency rule is unlikely. | RESEARCH | Simulate partitions and overlapping task claims under three coordination models. |
| RQ-006 | What should an offline runtime be allowed to do? | Offline work should be limited by cached policy, expiry, risk ceiling, and reconciliation requirements. | UNKNOWN | Specify an offline delegation envelope and adversarial test matrix. |
| RQ-007 | How are model and runtime behavioral differences normalized? | Versioned contracts and compatibility evaluations should constrain behavior without forcing identical reasoning. | RESEARCH | Run the same scenario suite across two materially different runtimes. |
| RQ-008 | How are duplicated cross-runtime external actions prevented? | Action fingerprints, global operation IDs, leases where needed, and external idempotency keys form layered protection. | DESIGNED | Fault-inject duplicate delivery before, during, and after connector timeouts. |

## Memory, context, and provenance

| ID | Research question | Current hypothesis / architectural direction | Status | Next evidence-producing step |
| --- | --- | --- | --- | --- |
| RQ-009 | What deserves to become durable memory? | Admission should score importance, durability, sensitivity, novelty, consent, provenance, and contradiction. | DESIGNED | Label a synthetic conversation corpus and compare rules, model judgment, and hybrid admission. |
| RQ-010 | When should episodic observations consolidate into semantic knowledge? | Consolidation should depend on source authority and repeated independent support, not count alone. | RESEARCH | Test consolidation against changing preferences and unequal-authority sources. |
| RQ-011 | How should memory decay, archive, or be forgotten? | Lifecycle combines time, usage, confidence, validity, importance, and explicit user intent; important history may be archived rather than active. | RESEARCH | Compare retrieval quality and trust after several decay policies. |
| RQ-012 | How should contradictory memories coexist and resolve? | Preserve temporal validity and provenance; never blindly overwrite history. | DESIGNED | Create contradiction cases for preference change, correction, fraud, and uncertain evidence. |
| RQ-013 | How does LILITH know why it believes a claim? | Durable claims retain source, observation time, transformation lineage, confidence, freshness, and verification. | PARTIAL | Define a provenance schema and trace three multi-source conclusions end to end. |
| RQ-014 | Which memories should enter cognition for a task? | Retrieval combines relevance, recency, importance, active goal, source quality, contradictions, privacy, and contamination controls. | RESEARCH | Benchmark task outcomes and privacy leakage under competing rankers. |
| RQ-015 | How is inference prevented from becoming false memory? | Observed, user-asserted, derived, inferred, and speculative claims remain distinct and have different promotion rules. | DESIGNED | Add mutation tests that attempt to promote unsupported inferences. |
| RQ-016 | What does complete deletion require across derived data and backups? | Deletion must propagate through indexes, embeddings, summaries, caches, replicas, exports, and defined backup expiry. | UNKNOWN | Produce a data lineage map and deletion-verification protocol. |
| RQ-017 | How is sensitive memory routed across models and runtimes? | Data classification constrains context assembly, runtime selection, retention, and logging. | RESEARCH | Threat-model three sensitivity tiers and measure utility loss under redaction. |

## Goals, planning, delegation, and self-evaluation

| ID | Research question | Current hypothesis / architectural direction | Status | Next evidence-producing step |
| --- | --- | --- | --- | --- |
| RQ-018 | What distinguishes a conversation, task, workflow, project, goal, routine, and automation? | They require separate lifecycle and completion semantics connected by typed relationships. | DESIGNED | Specify examples and counterexamples as a domain model. |
| RQ-019 | How should conflicting goals be prioritized? | Explicit user priorities dominate; inferred tradeoffs require uncertainty and escalation thresholds. | RESEARCH | Test a preference-elicitation protocol on synthetic conflicting goals. |
| RQ-020 | How does LILITH detect stale or abandoned goals? | Inactivity, changed dependencies, repeated deferral, and explicit signals may trigger review, never silent abandonment. | DESIGNED | Evaluate reminder precision and user annoyance in a simulated backlog. |
| RQ-021 | When should deterministic playbooks replace model planning? | Known high-confidence operations use versioned playbooks; novelty and complexity trigger bounded planning. | PARTIAL | Compare reliability, cost, and recovery across a task taxonomy. |
| RQ-022 | When should a plan continue, replan, pause, or stop? | Explicit expectation-versus-observation checks and risk changes drive state transitions. | DESIGNED | Build failure-injection scenarios for lost capabilities, stale assumptions, and partial success. |
| RQ-023 | How does LILITH recognize unreliable reasoning? | Evidence completeness, uncertainty calibration, verifier disagreement, and historical task-class performance should drive escalation. | RESEARCH | Measure calibration and selective-abstention curves. |
| RQ-024 | Which runtime/model should handle a task? | Routing considers privacy, capability, risk, cost, latency, context size, and measured performance. | DESIGNED | Create a routing benchmark with explicit utility and privacy budgets. |
| RQ-025 | How is worker delegation bounded and supervised? | A worker receives a narrow objective, capability allowlist, state scope, budget, expiry, and evidence contract. | RESEARCH | Test nested delegation for authority amplification and lost cancellation. |

## Governance, authority, and risk

| ID | Research question | Current hypothesis / architectural direction | Status | Next evidence-producing step |
| --- | --- | --- | --- | --- |
| RQ-026 | How should contextual action risk be calculated? | Effective risk combines intrinsic class, environment, blast radius, timing, reversibility, uncertainty, system health, and policy. | RESEARCH | Build a labeled scenario set and compare human/system classification agreement. |
| RQ-027 | Can experience safely reduce friction for repeatedly approved actions? | Learning may propose a policy change but must never silently lower restrictions. | DESIGNED | Simulate policy suggestions and measure unsafe-generalization rate. |
| RQ-028 | How is approval bound to exactly what executes? | Canonical serialization plus proposal fingerprint, conditions, approver, and execution-time equality checks. | DESIGNED | Attempt parameter substitution, encoding ambiguity, and replay attacks. |
| RQ-029 | How long should approval remain valid when reality changes? | Expiry, state bindings, and precondition revalidation vary by capability and risk. | RESEARCH | Test approval validity against changing commits, recipients, prices, and policy. |
| RQ-030 | What happens when a high-urgency event requires authority and the user is unavailable? | Wait, wake, escalate, or execute only a predelegated reversible action; urgency alone never creates authority. | RESEARCH | Develop a 3 a.m. incident matrix with harm/cost and interruption outcomes. |
| RQ-031 | What future actions can be safely predelegated? | Delegation requires scope, conditions, expiry, resource, risk ceiling, rate limit, and verification. | RESEARCH | Pilot a synthetic health-check/restart policy in simulation. |
| RQ-032 | Which actions must remain nondelegable? | Some destructive, identity, credential, legal, or financial actions may require contemporaneous human authorization or prohibition. | UNKNOWN | Facilitate a values and threat-model review; record the result in policy ADRs. |

## Execution, verification, and evidence

| ID | Research question | Current hypothesis / architectural direction | Status | Next evidence-producing step |
| --- | --- | --- | --- | --- |
| RQ-033 | What should happen when a call times out after it may have succeeded? | Enter UNKNOWN, reconcile by read-back, and retry only when safety is established. | DESIGNED | Fault-inject timeouts around a reversible draft-creation capability. |
| RQ-034 | How is goal success distinguished from execution success? | Each task class needs an expected-state and evidence contract beyond transport success. | PARTIAL | Define contracts for read, internal mutation, draft creation, and deployment. |
| RQ-035 | When must verification be independent from execution? | Consequence and false-pass harm determine whether separate API, identity, worker, or observation is required. | RESEARCH | Compare correlated failure rates across verification topologies. |
| RQ-036 | How much evidence is sufficient? | Evidence thresholds are task-specific and include source diversity, freshness, expected state, and stability windows. | DESIGNED | Specify graded evidence profiles for R0–R4 examples. |
| RQ-037 | How are false PASS, false FAIL, partial, and unknown outcomes measured? | Confusion matrices must include partial and unknown classes, weighted by consequence. | RESEARCH | Create a verifier benchmark with injected ambiguous outcomes. |
| RQ-038 | How is a conclusion traced back through derived facts to observations? | Evidence forms a typed lineage graph with immutable source references and transformation metadata. | DESIGNED | Trace a multi-source morning brief and detect unsupported conclusions. |
| RQ-039 | What compensating strategies work when an external system lacks idempotency? | Read-before-write, unique markers, reconciliation, rate limits, and compensating actions may reduce—not remove—risk. | RESEARCH | Compare strategies on a fake connector with lossy responses. |

## Proactivity, attention, and human factors

| ID | Research question | Current hypothesis / architectural direction | Status | Next evidence-producing step |
| --- | --- | --- | --- | --- |
| RQ-040 | When should LILITH interrupt rather than wait? | Expected harm, urgency, actionability, confidence, user context, and interruption cost determine attention level. | RESEARCH | Label scenarios and measure precision, regret, and missed-critical-event rate. |
| RQ-041 | How can proactivity avoid becoming surveillance or manipulation? | Proactivity must be purpose-limited, inspectable, quiet by default, and user-configurable with clear data boundaries. | RESEARCH | Conduct abuse-case review and preference interviews using synthetic scenarios. |
| RQ-042 | How should correction change future behavior without overgeneralizing? | Corrections attach to scoped policy/preferences with confidence and confirmation for broad changes. | UNKNOWN | Test local versus generalized learning across ambiguous feedback cases. |
| RQ-043 | What makes continuity feel trustworthy to the user? | Accurate recall, visible uncertainty, respectful forgetting, stable commitments, and repair after error matter more than surface personality alone. | RESEARCH | Define a longitudinal human-evaluation protocol and repair scenarios. |

## Evaluation, observability, security, and operations

| ID | Research question | Current hypothesis / architectural direction | Status | Next evidence-producing step |
| --- | --- | --- | --- | --- |
| RQ-044 | How do we measure continuity, identity consistency, verification quality, and interruption appropriateness? | A versioned compatibility suite combines scenario tests, calibration, behavioral invariants, and longitudinal human ratings. | RESEARCH | Define the first 20 golden scenarios and scoring rubric. |
| RQ-045 | How are model upgrades prevented from silently changing identity or judgment? | Shadow evaluation and invariant regression gates precede rollout; rollback preserves state compatibility. | DESIGNED | Run two model versions through identity, policy, and tone cases. |
| RQ-046 | What observability supports accountability without leaking personal data? | Structured event metadata, redaction, selective content capture, access control, and retention tiers are required. | RESEARCH | Threat-model a trace schema and test debugging utility after redaction. |
| RQ-047 | How resilient is policy to direct and indirect prompt injection? | Untrusted content remains data, capabilities are least-privileged, and policy is enforced outside model instructions. | RESEARCH | Build adversarial connector-content cases across read and write flows. |
| RQ-048 | How are secrets isolated from models, logs, workers, and clients? | Capabilities use scoped credential handles; raw secrets stay in a dedicated store and are never placed in model context. | DESIGNED | Trace credential exposure paths and add canary-secret tests. |
| RQ-049 | How are backups, migrations, and disaster recovery reconciled with identity continuity? | Recovery requires lineage, integrity checks, monotonic state rules, and explicit handling of post-backup actions. | UNKNOWN | Run a tabletop recovery with concurrent writes and revoked authority. |
| RQ-050 | When is LILITH safe enough to advance an autonomy level? | A release gate combines task success, false-pass limits, unknown-state handling, security tests, override behavior, and incident-free exposure. | RESEARCH | Define quantitative gates for the first approval-bound write. |

## Review cadence

- Review priority questions at each architecture milestone.
- Review all active questions quarterly or after a material incident, model change, runtime change, or autonomy increase.
- Promote status only in a pull request that links evidence.
- Keep disproven hypotheses and superseded questions visible for research integrity.
