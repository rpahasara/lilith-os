# LILITH Roadmap

This roadmap is evidence-gated, not date-driven. A phase advances when its exit criteria are met. Research, security, documentation, and public learning artifacts run alongside implementation.

## Maturity model

| Level | Operating mode | Authority |
| --- | --- | --- |
| A0 | Architecture and offline research | No real-world action |
| A1 | Read-only assistance | Observe and summarize with provenance |
| A2 | Simulated and shadow operation | Propose actions but do not execute |
| A3 | Approval-gated reversible writes | Execute an exact approved proposal and verify |
| A4 | Bounded predelegation | Low-risk action classes under explicit envelopes |
| A5 | Multi-runtime and proactive operation | Coordinated autonomy with measured attention policy |

No schedule alone promotes an autonomy level.

## Phase 0 — Repository and architecture foundation

**Status:** IN PROGRESS

Deliverables:

- professional repository structure and contribution workflow;
- AS-IS evidence policy and target architecture;
- initial ADRs and research register;
- threat model, trust boundaries, and security policy;
- documentation CI and deployment placeholder;
- engineering-journal workflow.

Exit criteria:

- required documents pass automated validation;
- placeholder URLs are replaced when the GitHub repository exists;
- maintainers review and accept the identity/runtime boundary.

## Phase 1 — Current-system audit and import

**Status:** PLANNED

- Import existing LILITH implementation intentionally, preserving history where possible.
- Map every reported component to code, tests, state, data flows, and deployment evidence.
- Document GCP or other infrastructure, runtime topology, connector freshness, and secrets boundaries.
- Create a technical-debt and dependency-risk register.
- Replace reported claims in AS-IS documentation with verified claims or corrections.

Exit criteria:

- component ownership and dependency diagrams match code;
- repeatable local development and test commands exist;
- no unexplained direct capability path bypasses policy/state;
- state schemas and migrations are recoverable.

## Phase 2 — Engineering quality and CI/CD foundation

**Status:** PLANNED

- Select language-specific formatting, linting, type, test, and security checks.
- Add contract, integration, concurrency, failure-injection, and migration tests.
- Produce immutable artifacts with provenance and dependency inventory.
- Define environment separation, protected deployment approvals, secrets, rollback, and post-deployment verification.
- Keep production deployment disabled until an ADR and readiness review are accepted.

Exit criteria:

- pull requests enforce relevant quality gates;
- a sandbox deployment can be reproduced and rolled back;
- deployed artifact identity is verifiable;
- secrets do not enter source, logs, or model context.

## Phase 3 — Architecture V2 and Slice 4 design

**Status:** PLANNED

- Review every proposed layer for a real invariant, state, trust, or failure boundary.
- Version core task, capability, policy, approval, and evidence contracts.
- Threat-model the first real write.
- Design a reversible operation such as creating an unsent draft.
- Specify proposal fingerprint, approval expiry, precondition binding, idempotency, cancellation, denial, reconciliation, read-back, and evidence.

Exit criteria:

- accepted ADRs cover contested boundaries;
- failure branches are modeled and tested in simulation;
- RQ-028, RQ-033, RQ-034, and RQ-036 have explicit test protocols;
- security review approves an A3 sandbox pilot.

## Phase 4 — First approval-gated reversible write

**Status:** FUTURE

- Implement one vertical slice through intent, task, plan, policy, approval, execution, read-back, verification, evidence, and presence.
- Run sandbox, fault-injection, and replay tests.
- Start in shadow mode before approval-gated real use.

Exit criteria:

- changed proposals invalidate approval;
- duplicates do not create duplicate effects under tested faults;
- ambiguous timeouts enter UNKNOWN and reconcile safely;
- verification meets declared false-PASS threshold;
- denial, cancellation, expiry, and rollback work end to end.

## Phase 5 — Memory and resumable goals

**Status:** FUTURE / RESEARCH-DEPENDENT

- Separate conversation, task, goal, memory, evidence, preference, and operational state.
- Implement candidate-memory admission with provenance and sensitivity.
- Prototype contradiction, temporal validity, retrieval, consolidation, decay, export, and deletion.
- Add long-running goal lifecycle, dependencies, staleness, and resumption.

Exit criteria:

- no inference silently becomes user fact;
- deletion verification covers derived artifacts;
- retrieval evaluation measures task benefit and privacy leakage;
- goal staleness interventions meet interruption-quality thresholds.

## Phase 6 — Workers and automation

**Status:** FUTURE

- Add specialized workers with bounded delegation envelopes.
- Add resumable workflows, schedules, event triggers, budgets, cancellation, and compensation.
- Preserve canonical state, authority, and evidence across delegation.

Exit criteria:

- nested workers cannot amplify authority;
- crash recovery and duplicate delivery are tested;
- automations remain inspectable, pausable, and revocable.

## Phase 7 — Proactive intelligence and bounded authority

**Status:** FUTURE / RESEARCH-DEPENDENT

- Implement attention and interruption policy.
- Pilot predelegated low-risk actions only after shadow evaluation.
- Define emergency decision matrix without treating urgency as authority.

Exit criteria:

- missed-critical-event, false-interruption, regret, and override metrics meet thresholds;
- every autonomous action stays within an inspectable envelope;
- break-glass behavior, if any, has a dedicated accepted ADR and exercises.

## Phase 8 — Multi-runtime and cross-device continuity

**Status:** FUTURE / RESEARCH-DEPENDENT

- Add another conforming runtime beside Hermes.
- Introduce sync authority, leases or other selected coordination mechanism, and offline constraints.
- Add native clients without moving governance into the client.
- Run identity compatibility and partition-recovery evaluations.

Exit criteria:

- runtime replacement preserves declared identity invariants;
- overlapping execution cannot duplicate consequential effects under tested partitions;
- conflicts are visible, auditable, and safely resolved.

## Continuous portfolio and learning track

Each phase should produce:

- one architecture or research artifact;
- one journal entry describing hardship, evidence, and changed understanding;
- one reusable diagram or experiment result;
- optional public material derived from real work, with sensitive details removed.

The operating loop is: **learn → apply to LILITH → verify → document → extract a public lesson**.
