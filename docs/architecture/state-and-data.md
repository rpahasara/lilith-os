# State and Data Architecture

## State taxonomy

| State class | Purpose | Expected authority |
| --- | --- | --- |
| Conversation context | Immediate interaction continuity | Ephemeral/session store |
| Task state | Current bounded work and lifecycle | Canonical task service |
| Goal state | Long-running outcomes and dependencies | Canonical goal service |
| Episodic memory | What happened, with time and source | Memory service |
| Semantic memory | Consolidated claims with confidence and validity | Memory service |
| User preferences | Explicit or carefully inferred preferences | Identity/memory policy |
| Relationship state | Durable interaction commitments and boundaries | Identity service |
| Policy and delegation | Allowed actions and conditions | Policy authority |
| Evidence/provenance | Why the system believes a claim or outcome | Evidence store |
| Operational state | Health, credentials, connector freshness | Operational control plane |

## Provenance classes

At minimum, records should distinguish `LIVE`, `CACHED_LIVE`, `STALE`, `USER_ASSERTED`, `OBSERVED`, `DERIVED`, `INFERRED`, `SPECULATIVE`, `SIMULATED`, and `TEST`. These axes may become separate fields rather than a single enum as the model matures.

## Memory lifecycle under research

```text
observation
  → candidate
  → importance / durability / sensitivity / novelty assessment
  → contradiction and consent checks
  → store or reject
  → retrieve with relevance and policy filters
  → reinforce, consolidate, supersede, archive, or forget
```

Deletion must consider indexes, embeddings, derived facts, caches, replicas, logs, exports, and backups. “Forgotten” cannot merely mean hidden from the primary query path.

## Consistency direction

Canonical state should use monotonic revisions and explicit expected-revision checks. Multi-runtime work will require operation identities, action fingerprints, conflict records, offline reconciliation, and rules for leases or leadership. The exact consistency model remains a research question; the target is not naïve last-write-wins for identity or authority state.

## Retention placeholder

Before personal data is stored, define:

- purpose and lawful/consensual basis;
- sensitivity and permitted model/runtime routes;
- default retention and expiry;
- access, export, correction, and deletion behavior;
- derived-data and backup deletion semantics;
- encryption and key ownership;
- observability redaction.
