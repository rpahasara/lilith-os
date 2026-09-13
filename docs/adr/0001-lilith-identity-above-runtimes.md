# ADR-0001: LILITH identity exists above replaceable runtimes

- **Status:** Accepted
- **Date:** 2026-09-13
- **Owners:** Project maintainers
- **Related:** RQ-001, RQ-004, RQ-007

## Context

LILITH may use Hermes today and local, cloud, or specialized runtimes in the future. Models and runtimes change availability, behavior, cost, privacy properties, and implementation details. If identity lives implicitly in one runtime's prompt, process, or private storage, changing that runtime can fragment identity, lose commitments, or create competing sources of truth.

## Decision

LILITH owns persistent identity, relationship history, goals, memory policy, delegated authority, canonical state, and provenance above the runtime layer.

Hermes is a replaceable execution substrate. A runtime receives scoped task context and authority through an adapter contract. It does not become the canonical owner of LILITH identity merely because it performs planning or execution.

This ADR does not claim that the identity invariant or multi-runtime synchronization mechanism is fully implemented.

## Alternatives considered

### Hermes is LILITH

This is initially simple, but couples identity to one runtime, makes migration ambiguous, and permits runtime-private state to become invisible authority.

### Reconstruct identity from conversation history

Transcripts are incomplete, noisy, sensitive, and lack typed policy, state, and provenance. Reconstruction can produce drift and contradictions.

### Each runtime owns an identity replica

Peer replicas may eventually be viable, but unresolved conflicts in policy, memory, or external action create unacceptable ambiguity without a canonical coordination model.

## Consequences

### Positive

- Models and runtimes can be replaced or compared without redefining the project.
- Governance and continuity remain reviewable outside probabilistic execution.
- Multi-runtime work has an explicit coordination boundary.

### Negative and tradeoffs

- Requires versioned contracts and a durable control plane.
- Adds synchronization, migration, and availability concerns.
- “Identity” must be formally specified rather than left as branding.

### Operational and migration impact

Runtime adapters must not persist canonical identity state. Existing runtime-private memory must be audited and migrated or classified as cache.

## Security, privacy, and trust boundaries

The runtime boundary is a trust boundary. LILITH should minimize context, constrain capabilities, avoid raw secret exposure, validate outputs, and retain final authority for governed state transitions.

## Validation

- Restore LILITH state through a different runtime and measure invariant behavior.
- Run equivalent scenarios through Hermes and another adapter.
- Demonstrate that disabling Hermes does not erase canonical goals, policy, or identity lineage.

## Revisit triggers

- Evidence that central state creates unacceptable availability or privacy risk.
- A formally verified peer-replication model that preserves authority and identity semantics.
- A revised identity-invariant specification.
