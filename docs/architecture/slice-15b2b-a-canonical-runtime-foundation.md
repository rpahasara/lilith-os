# Slice 15B2b-A — Canonical Runtime Foundation

**Status:** implemented on a feature branch; production activation remains dark.

Slice 15B2b-A establishes deployable and CI-governed V2 canonical-memory apply
foundations. Production canonical writes remain disabled and no real canonical
memory exists.

## Canonical source location

The approved Slice 15A, 15B1, and 15B2a runtime is now a normal deployable
package at `services/core-api/lilith_memory/`. The files in the earlier
`docs/architecture/slice-15*` directories remain immutable implementation and
deployment records; they are no longer the source used to build a Core API
candidate bundle.

Ownership remains separated:

- `learning.py`, `learning_store.py`, and `learning_worker.py`: L18 V1;
- `learning_v2.py`: owner-directed L18 V2 proposals;
- `canonical_authority.py`: Actor, Policy, Consent, and Rollback owners;
- `privacy_governance.py`: Privacy authority;
- `memory_store.py`: retained V1 proof and compatibility implementation;
- `canonical_store.py`: family-neutral L04 V2 apply and exact raw read;
- `memory_v2.py`: tuple contracts, read facade, and Privacy adapters;
- `registry_loader.py`: governed registry and containment readiness;
- `config.py`: server-owned, fail-closed activation snapshot;
- `backup.py` and `canonical_migration.py`: explicit backup and migration
  authorities.

Importing these modules creates no database, runs no migration, and enables no
capability.

## Family-neutral schema

Migration version 2 changes only the proposal foreign-key columns owned by L04:

| Table | V1 column | Family-neutral column |
| --- | --- | --- |
| `memory_revision` | `created_from_proposal_id` | `created_from_proposal_ref_id` |
| `memory_admission` | `proposal_id` | `proposal_ref_id` |
| `memory_apply_audit` | `proposal_id` | `proposal_ref_id` |

Every pre-existing V1 proposal receives a deterministic, immutable
`learning_proposal_ref` with family `L18_V1_CAREER`. Its family-local ID,
fingerprint, timestamp, revision values, item IDs, provenance, admissions,
audits, and active pointer are preserved. V2 proposals already create refs with
family `OWNER_DIRECTED_PROJECT_CODENAME_V1`.

The migration is not an import side effect. It requires a verified backup of
the current cognitive database, validates the version-1 L04 fingerprint,
rebuilds affected tables in one transaction, checks row counts, foreign keys,
and integrity, and records the version-2 fingerprint. Re-running against an
already migrated database requires fresh backup evidence and verifies without
rewriting rows.

The version-2 canonical-runtime schema fingerprint is
`ceadab225a2ef8ecb713f5e0d78a303161713af223b26480775c56ec1544d229`.

## L04 V2 apply

`CanonicalMemoryStoreV2.apply(proposal_ref_id)` accepts no caller-supplied
authority. It resolves the immutable proposal and family and revalidates the
exact action, normalizer/digest, candidate/provenance binding, Actor evidence,
computed Policy decision, Consent, privacy hold, expected revision, registry,
containment readiness, capacity, kill switch, and current server capability.

After validation, one `BEGIN IMMEDIATE` transaction owns the terminal admission
and, for an accepted operation, item, new immutable revision, provenance,
active pointer, and audit. RESTORE also consumes its separate one-time Rollback
Authorization inside that transaction. An accepted replay returns its original
IDs. A terminal rejected/precondition-failed replay returns the same outcome.
A busy database returns retryable state and records nothing.

RESTORE resolves the real canonical item from the exact tuple, verifies the
current active revision and historical revision independently, verifies the
historical digest against the action, and creates a new revision whose
`supersedes_revision_id` is current and `restores_revision_id` is historical.

## Registry, containment, configuration, and reads

The governed registry loader validates the immutable registry schema ledger,
closed memory-class set, exact tuple, schema, capability, read/write bits, and
Consent requirement against a server-reviewed allowlist. Wildcards, aliases,
fuzzy matching, unreviewed rows, and a generic semantic-memory class are not
accepted.

Legacy containment must load from a closed server file and have exact identity
parity with the canonical registry. Missing, malformed, duplicate, extra, or
missing containment entries fail readiness.

The runtime config file has exactly three fields: schema version, Boolean kill
switch, and a closed capability list. Missing or malformed config is disabled.
Callers, browser requests, proposal payloads, and model output are not config
inputs.

`CanonicalMemoryReadFacade` remains the only authorized typed read foundation:
exact actor, exact registry permission, no privacy hold, active revision, and
valid Consent. A miss is `None`; it never consults legacy memory files, World,
Goal, chat history, prompts, or model context.

## Privacy and backup compatibility

L04 Privacy adapters recognize either historical V1 proposal columns or the
family-neutral columns. V2 erasure lineage exposes proposal-ref IDs and
family-local IDs without copying the raw value. Privacy holds block both apply
and read. Restore readiness continues to require Privacy suppression replay,
so a stale cognitive backup cannot outrank a newer erasure.

The governed online-backup utility creates an explicit destination and manifest
for cognitive or Privacy SQLite databases. It records SHA-256, byte size,
source identity, schema fingerprint, table counts, integrity, foreign-key
status, timestamps, mode, and owner/group metadata where supported. Files are
restricted to mode 0600 on POSIX. The tool never restores or deletes a backup.

## CI and delivery

Core API CI compiles the complete package, discovers service tests, and runs a
portable reconstruction of the committed Slice 8–15 regression records. The
reconstruction is temporary and deterministic; it does not contact a model,
connector, DEV, or PROD.

The trusted DEV workflow builds an allowlisted tar archive from the exact
CI-validated candidate SHA. The deterministic manifest hashes every runtime and
test file. A trusted verifier rejects links, traversal, extra members, hash
drift, or candidate-SHA drift. DEV extracts to a SHA-named release, runs
synthetic tests against temporary SQLite only, switches an atomic `current`
symlink, restarts, checks health, reads back the candidate and bundle identity,
and restores the prior symlink on failure.

DEV cognitive and Privacy paths are distinct from PROD and the DEV config is
created disabled with no active capability. No production deployment workflow
was broadened by this stage.

## Explicitly deferred

- trusted owner confirmation UI/transport;
- real REMEMBER and First Memory value;
- production query/explain route;
- full FORGET orchestration;
- production registry and containment tuples;
- production capability or kill-switch activation;
- prompt consumption or autonomous retrieval;
- vectors, embeddings, graphs, relationships, or broad semantic memory.
