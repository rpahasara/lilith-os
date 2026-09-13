# Architectural Principles

## P-01 — Identity is substrate-independent

LILITH is not a model, prompt, process, device, UI, database, or Hermes deployment. Its continuity depends on a versioned identity charter, governed durable state, relationship history, memory, goals, policy, delegated authority, and provenance.

## P-02 — Runtimes are clients of identity

Hermes and future runtimes receive scoped context and authority. They do not own canonical identity or silently persist competing identity state.

## P-03 — Governance precedes capability execution

Every executable capability is explicit, typed, scoped, risk-classified, and policy-evaluated. Approval is bound to the exact proposed action; changed parameters invalidate it.

## P-04 — External reality beats internal confidence

Plans and model judgments are hypotheses. Goal completion depends on evidence from the relevant environment, with independent read-back for consequential actions.

## P-05 — Unknown is a valid state

Timeouts and partial failures must not be collapsed into success or failure when the external state is genuinely unknown. Reconciliation comes before unsafe retries.

## P-06 — Durable state is revisioned and idempotent

Concurrent mutation is protected through version checks, operation identities, and explicit conflict handling. External idempotency is used where available; otherwise compensating strategies are documented.

## P-07 — Memory is governed data, not a transcript dump

Memory admission, sensitivity, provenance, consolidation, contradiction, retention, deletion, and retrieval are explicit lifecycle concerns. Inferences never silently become facts.

## P-08 — Autonomy expands through evidence

New capability classes move from design to simulation, shadow operation, approval gating, bounded delegation, and broader autonomy only when evaluation supports the transition.

## P-09 — Least privilege is continuous

Authority is limited by user, capability, resource, environment, conditions, time, and rate. Workers and runtimes receive the minimum authority required for the current task.

## P-10 — Presence reflects semantic state

User-facing presence communicates states such as listening, planning, awaiting approval, acting, verifying, degraded, or blocked. It does not expose private reasoning or become an alternative control plane.

## P-11 — Privacy and reversibility are design inputs

Personal data collection, retention, model routing, logging, and deletion behavior are decided before integration. Prefer reversible actions and recovery paths.

## P-12 — Documentation distinguishes fact from intention

Current-state claims require repository or operational evidence. Target designs, historical reports, and research hypotheses are labeled as such.
