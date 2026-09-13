# Current State (AS-IS)

## Evidence date

Repository foundation created: 2026-09-13.

## Verified in this repository

- Documentation hierarchy and contribution process.
- Initial architectural invariants and accepted runtime-boundary ADR.
- Research-question register and experiment method.
- Initial threat model and trust-boundary inventory.
- Documentation validation script and GitHub Actions CI workflow.
- Deployment workflow is intentionally inactive.

## Reported by earlier engineering-journal material

Prior project context reports work on:

- UI and Presence foundations;
- Command System V1;
- a bounded cognitive core covering early read-oriented slices;
- playbook/context/planner and capability-registry concepts;
- Hermes/router integration;
- evidence-backed verification;
- authoritative backend task records with monotonic revisions, optimistic conflict protection, and operation idempotency;
- degraded-source handling that distinguishes unavailable or stale data from an empty result.

These are **REPORTED**, not independently verified in this repository. When implementation is imported, each claim must be mapped to source paths, tests, schemas, traces, and deployment evidence before its status changes.

## Known gap before implementation resumes

The first consequential write slice requires a reviewable lifecycle for proposal fingerprinting, approval persistence and expiry, exact execution binding, denial/cancellation, idempotency, unknown-state reconciliation, independent read-back, verification, and durable audit evidence.

## Audit checklist for imported code

For each component, record:

- owner and explicit non-responsibilities;
- inputs, outputs, schemas, and versioning;
- state read and state mutated;
- caller/callee rules and bypass paths;
- deterministic versus probabilistic behavior;
- trust-boundary crossings and credentials;
- timeouts, retries, cancellation, and crash recovery;
- evidence emitted and verification performed;
- unit, contract, integration, failure-injection, and end-to-end tests;
- deployed revision and operational dashboards.

The completed audit should update this page, not overwrite the historical distinction between reported and verified work.
