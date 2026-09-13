# LILITH–Runtime Boundary

## Decision summary

Hermes is a replaceable runtime substrate used by LILITH. It is not the identity, policy authority, canonical memory, or canonical task store. See [ADR-0001](../adr/0001-lilith-identity-above-runtimes.md).

## Responsibilities supplied to a runtime

A runtime may receive:

- a bounded task and expected outcome;
- policy-filtered context;
- a capability allowlist and scoped credentials or references;
- time, cost, model, and retry budgets;
- a delegation envelope;
- required evidence and return schema.

## Responsibilities retained by LILITH

LILITH retains:

- identity and relationship continuity;
- canonical durable state and revisions;
- policy, risk classification, and approvals;
- memory admission and retention;
- cross-runtime coordination;
- final task-state transitions;
- evidence retention and user-facing accountability.

## Proposed runtime request envelope

```yaml
task_id: stable-id
task_revision: 7
operation_id: idempotency-id
runtime_request_id: attempt-id
objective: bounded desired outcome
context_refs: []
capability_allowlist: []
delegation:
  expires_at: timestamp
  risk_ceiling: R1
  resources: []
budgets:
  wall_time_seconds: 60
  model_cost_units: 10
verification_contract_ref: contract-version
```

This is illustrative, not yet a versioned implementation contract.

## Failure semantics to specify

- Runtime unavailable before accepting work.
- Runtime crashes after accepting work.
- Capability succeeds but runtime response is lost.
- Runtime returns malformed or adversarial output.
- Runtime uses a disallowed capability.
- Two runtimes receive overlapping work.
- An offline runtime returns a stale mutation.
- Model change causes behavioral regression.

The safe default is to preserve uncertainty, reconcile against external evidence, and refuse an unsafe retry or state mutation.
