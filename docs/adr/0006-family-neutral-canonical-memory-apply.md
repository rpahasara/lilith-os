# ADR-0006: Canonical memory apply uses family-neutral proposal identity

- **Status:** Accepted
- **Date:** 2026-09-22
- **Owners:** Project maintainers
- **Related:** ADR-0002, ADR-0003, ADR-0004, ADR-0005

## Context

Slice 15B1 proved immutable canonical-memory revisions, but its L04 tables
referenced the Slice 15A `learning_proposal` table directly. Slice 15B2a added
an owner-directed project-codename proposal family and an immutable
`learning_proposal_ref` anchor, plus separate Actor, Policy, Consent, Rollback,
Privacy, registry, and containment authorities. It intentionally did not add a
canonical write bridge.

Directly placing a V2 proposal ID into a V1 foreign key would silently
reinterpret identity. Letting L18 mutate `memory_*` would collapse the learning
and canonical-state authorities. Consuming Rollback authority in a separate
transaction would also allow authority consumption to survive a failed
canonical write.

## Decision

L04 canonical rows reference the immutable, family-neutral
`learning_proposal_ref.proposal_ref_id`. The anchor records the closed proposal
family, family-local proposal ID, schema version, and immutable fingerprint.
Existing V1 proposals map explicitly to `L18_V1_CAREER`; V2 proposals remain
`OWNER_DIRECTED_PROJECT_CODENAME_V1`. Family dispatch never infers meaning from
an ID prefix.

Only L04 owns canonical application. Its public V2 boundary accepts a proposal
reference ID, independently resolves every authority and precondition, and
commits the admission, item, revision, provenance, active pointer, audit, and
RESTORE authorization consumption in one `BEGIN IMMEDIATE` transaction.
RESTORE always resolves the real `mitem.*` identity, the current revision, and
the historical target digest, then creates a new revision. It never repoints to
history.

Activation requires all of the following independently:

- the server-owned canonical kill switch is valid and true;
- the exact Policy capability is server-configured and active;
- the immutable DB registry exactly matches a reviewed server allowlist;
- the closed legacy-containment registry has exact tuple parity;
- Actor, Policy, Consent, privacy hold, proposal, candidate, and operation
  bindings all validate.

Missing or malformed configuration, registry, containment, schema, or authority
state fails closed. Callers and model payloads cannot activate these controls.

Migration is an explicit operator command. It requires freshly verified online
SQLite backup evidence for the source image, recognizes only the approved
Slice 15B2a schema, preserves V1 rows, writes a versioned fingerprint, and is
idempotent. Importing the runtime never migrates or activates anything.

## Consequences

### Positive

- V1 and V2 proposal identity is explicit and collision-free.
- L18 can propose but cannot mutate canonical state.
- accepted and rejected proposal replay is deterministic.
- stale expected revisions and transaction faults leave no partial canonical
  state.
- Rollback consumption and RESTORE revision creation succeed or fail together.
- Privacy owners can locate both the proposal reference and its family-local
  lineage.
- Git now contains the deployable Slice 15 runtime instead of treating VM-only
  source as authority.

### Tradeoffs

- The schema migration rebuilds the affected SQLite tables transactionally to
  change their foreign keys; it therefore requires explicit backup evidence and
  exclusive migration authority.
- Existing V1 runtime objects are compatibility evidence, not a second write
  authority after migration. Family-specific dispatch must remain explicit.
- A trusted deployment-control change cannot validate itself through the
  default-branch `workflow_run` until that control is present on the trusted
  branch.

## Privacy and recovery

Canonical revision values remain in L04 and are linked to an erasable exact
identity and proposal lineage. No value is added to logs, bundle manifests, or
backup manifests. Privacy holds suppress apply and read. A cognitive backup may
not outrank newer Privacy suppression; restore procedures must replay and verify
Privacy suppression before readiness.

The backup utility records source identity, SHA-256, size, schema fingerprint,
row counts, integrity and foreign-key results, ownership metadata where
available, restrictive mode evidence, and a timestamp. It never restores a
database automatically.

## Dark-state guarantee

Acceptance of this ADR does not activate canonical memory. Slice 15B2b-A must
end with the production kill switch false, the production registry empty, the
project-codename capability inactive, no production tuple or containment entry,
and zero real canonical rows. First Memory remains a later owner-controlled
stage.

## Validation

- migration from populated V1 fixtures and idempotent repeat;
- exact registry and containment loaders, including malformed input;
- inactive capability and missing/malformed kill-switch configuration;
- synthetic CREATE, SUPERSEDE, RESTORE, accepted and rejected replay;
- stale expected revision, DB busy, and injected transaction failure;
- exact authorized read, miss-without-fallback, and privacy-hold suppression;
- deterministic bundle construction, tamper rejection, atomic DEV release
  switching, identity read-back, health check, and rollback behavior.

## Revisit triggers

Revisit this ADR before adding another proposal family, a new canonical memory
class, cross-database transactions, a full FORGET orchestrator, production
activation, or a different durable-store technology.
