# ADR-0002: Durable task and identity state has a canonical authority

- **Status:** Accepted
- **Date:** 2026-09-13
- **Owners:** Project maintainers
- **Related:** RQ-004, RQ-005, RQ-008, RQ-049

## Context

Clients and runtimes may operate concurrently, retry requests, become disconnected, or return after holding stale state. Browser-local or runtime-private records cannot safely determine whether a consequential task is approved, executed, cancelled, or complete.

Earlier journal context reports an authoritative backend task-store foundation with revisions, expected-revision conflict protection, and operation idempotency. That implementation still requires audit when imported.

## Decision

Durable identity, policy, approval, task, goal, memory, and evidence records have a canonical authority. Mutations use monotonic versioning or equivalent concurrency protection, stable operation identities, explicit conflict outcomes, and auditable provenance.

Clients and runtimes may cache state, but caches are not silently authoritative. High-consequence conflicts must not use naïve last-write-wins resolution.

The physical database and deployment topology remain undecided.

## Alternatives considered

### Client-local authority

Works for a prototype but fails across devices, processes, recovery, and concurrent operation.

### Runtime-owned authority

Couples continuity to an execution substrate and conflicts with ADR-0001.

### Uncoordinated peer state

Improves availability but makes approvals, cancellations, and external side effects ambiguous during partitions.

## Consequences

### Positive

- Clear conflict and recovery semantics.
- Auditable state transitions.
- Supports multiple clients and future runtimes.

### Negative and tradeoffs

- The authority can become a latency or availability dependency.
- Requires migrations, backups, integrity checks, and disaster-recovery design.
- Offline operation must be deliberately constrained.

## Security, privacy, and trust boundaries

The canonical state plane contains highly sensitive relationship, memory, authority, and audit data. It requires strict access control, encryption, retention policy, redaction, and tamper-evident operational evidence.

## Validation

- Concurrent mutation and stale-revision tests.
- Duplicate operation and retry tests.
- Crash recovery around each lifecycle transition.
- Backup restoration with identity lineage and post-backup writes.

## Revisit triggers

- Multi-region or offline requirements that cannot meet objectives under a single logical authority.
- Evidence supporting a safe per-state consistency model.
