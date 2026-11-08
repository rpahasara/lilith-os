# Current State (AS-IS)

## Current state, updated 2026-11-08

Labels: **SOURCE-VERIFIED** means supported by code, tests and merged pull requests in this repository. **OPERATOR-REPORTED** means observed on the running hosts and recorded in [the PROD work note](../engineering/prod-work-note-2026-11-07.md), but not reproducible from this repository alone.

**There is an active PROD deployment.** One PROD host and one DEV host run LILITH: the Hermes gateway with the LILITH router, plus the LILITH OS Core API.

**SOURCE-VERIFIED:**
- Core API (`services/core-api`): tasks, approval-gated drafts, policy, connectors, World Model, goals, owner memory and the L18 learning-event ledger, with tests.
- PROD router and gateway mirrors (`deploy/prod/`): Router V2, seven cognition lanes (World Model grounding, Goals, Reasoning, Workspace, Motivation, Planning, Ethics), Social Cognition, lean social replies, and the full-agent provider fallback.
- Owner-only memory isolation: the owner channels are the console, the owner's Telegram DM and, once its one-time Telegram-linked challenge is completed and installed, the owner's Discord DM (#355). All other channels are non-owner.
- Delivery: pull-request CI on protected `main`; exact-SHA deployment to DEV; constrained PROD deployment of fixed components (`core-api`, `router`, `hermes-gateway`, `hermes-approval`), with backup, smoke check and automatic rollback (`deploy/prod/lilith-deploy`).
- Canonical-memory governance stack: authority, privacy, witness, FORGET runner and context service sources.

**OPERATOR-REPORTED:**
- **Cutover 1** completed 2026-11-01 and **Cutover 2** (seven lanes on PROD) was accepted 2026-11-04. The remaining exception E-T4 was closed 2026-11-08.
- **Canonical memory is live for owner channels:** two admitted memories are recalled on owner channels (2026-11-06).
- Natural owner learning is approval-gated and LILITH-OS-first.
- **Known gaps:**
  - Google OAuth is broken since 2026-08-31 and deferred to the VM migration.
  - L18 consolidation is shadow only.
  - FORGET covers the relationship-origin memory only.
  - The VM migration is due before the cloud-trial expiry on 2026-11-18.

The sections below are the **historical baseline of 2026-09-13**, kept unchanged.

## Evidence date

Repository foundation created: 2026-09-13.

## Verified in this repository

- Documentation hierarchy and contribution process.
- Initial architectural invariants and accepted runtime-boundary ADR.
- Research-question register and experiment method.
- Initial threat model and trust-boundary inventory.
- Documentation validation script and GitHub Actions CI workflow.
- Deployment workflow is intentionally inactive. *(Historical: superseded. See the current state above.)*

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
