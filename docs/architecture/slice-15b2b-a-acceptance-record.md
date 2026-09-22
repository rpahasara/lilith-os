# Slice 15B2b-A — Canonical Runtime Foundation Acceptance Record

**Evidence date:** 2026-09-22 UTC. **Scope:** a historical acceptance record,
not an activation instruction or a claim of live canonical memory.

## Three distinct states

| State | Acceptance finding |
| --- | --- |
| **SOURCE ACCEPTED** | PR [#13](https://github.com/rpahasara/lilith-os/pull/13) merged the canonical runtime foundation at `1e6419be90f9d85ec0fb798941224cf82e122db8`. |
| **DEV PROVEN** | An exact-SHA, synthetic, isolated DEV probe showed durable canonical state across a real service restart and a new process, then cleaned up its synthetic state. |
| **PROD DARK** | The production audit found canonical LTM disabled, capability inactive, empty registry and zero canonical authority/memory rows. The production workflow installed only the unchanged legacy `app.py`, not the canonical package. |

These findings do not establish an owner-control interface, production canonical
read/write capability, real personal memory, autonomous consolidation, prompt
retrieval, or semantic/vector retrieval. **No real canonical memory exists.**

## Purpose and starting architecture

Slice 15B2b-A turns the earlier Slice 15A/15B1/15B2a proof modules into a
governed, deployable source package while preserving authority boundaries.
Before it, L18 V1 learning proposals and an owner-directed L18 V2 proposal
family existed, but L04's canonical foreign keys were tied to V1's local
proposal table. Slice 15B2a had Actor, Policy, Consent, Rollback, Privacy,
registry and containment foundations without an enabled production V2 apply
bridge. A V2 local ID could not safely be treated as a V1 proposal ID.

The accepted [ADR-0006](../adr/0006-family-neutral-canonical-memory-apply.md)
uses the immutable `learning_proposal_ref` as L04's family-neutral identity.
The explicit, backup-gated V2 migration remaps existing V1 proposals to
`L18_V1_CAREER` refs without changing their identity, values, provenance or
active revisions; V2 refs use `OWNER_DIRECTED_PROJECT_CODENAME_V1`. It
rebuilds only the three affected L04 proposal-reference foreign-key columns
transactionally, checks integrity and row counts, records the schema
fingerprint, and verifies an already-migrated image without rewriting it.
Importing Python modules never runs the migration.

## Accepted runtime contracts

`CanonicalMemoryStoreV2.apply(proposal_ref_id)` accepts no caller-provided
authority. It resolves the proposal family and rechecks the frozen action,
candidate/provenance binding, Actor evidence, computed Policy decision,
Consent, Privacy hold, expected active revision, exact registry entry,
containment parity, capacity, server kill switch and capability. One
`BEGIN IMMEDIATE` transaction owns terminal admission and, when accepted,
the item, immutable revision, provenance, active pointer and audit. RESTORE's
one-time Rollback Authorization is consumed in that same transaction.
Accepted and terminal rejected replays retain their outcome; busy or failed
transactions cannot leave a partial canonical write.

CREATE creates a new item/revision; SUPERSEDE creates a new revision against
the exact expected active revision. RESTORE independently resolves the real
item, current active revision, selected historical revision and historical
digest, then creates a **new** revision linking both current and restored
history. It never repoints directly to an old revision. The corrected
item/digest checks reject a historical revision from another item or a wrong
historical digest.

The server-reviewed registry loader admits only the closed exact tuple,
value schema, capability, permissions and Consent requirement. The closed
legacy-containment loader requires exact identity parity; missing, malformed,
extra or duplicate entries fail readiness. Server-owned runtime configuration
has only schema version, Boolean `canonical_ltm_enabled` and closed active
capabilities. Missing or malformed configuration disables canonical use; a
browser, proposal or model cannot enable it. The kill switch is checked on
both mutation and exact reads. `CanonicalMemoryReadFacade` additionally
requires actor authorization, registry read permission, no Privacy hold,
active revision and valid Consent. A canonical miss remains a miss: there is
no fallback to legacy files, World, chat history or prompts.

The L04 Privacy adapter understands historical V1 and family-neutral V2
lineage. Privacy holds suppress apply and read. Governed cognitive and Privacy
SQLite online-backup tooling records source identity, checksums, schema/table
evidence, integrity, foreign keys, ownership and restrictive mode; migration
requires fresh verified evidence. The utility neither restores nor deletes a
backup. A stale cognitive backup may not outrank newer Privacy suppression:
replay and verification of Privacy state precede restore readiness.

## Governed validation and trusted-control bootstrap

The accepted head `dd410b20ae2bbe08f9fda3eb5ed30baabf96bea6` passed
[repository validation](https://github.com/rpahasara/lilith-os/actions/runs/35774918580):
Repository contracts, Frontend build and command core, and Core API tests.
Core API CI compiles the complete package, runs service tests, and reconstructs
Slice 8–15 architecture regressions deterministically without a paid model
call. The fourth required check, LILITH DEV deployment, passed in
[run 35775007405](https://github.com/rpahasara/lilith-os/actions/runs/35775007405).

The default-branch `workflow_run` trust boundary could not validate its own
new deployment controls. The narrowly scoped bootstrap controls were merged
before final PR #13 acceptance: [PR #14](https://github.com/rpahasara/lilith-os/pull/14)
installed the trusted bundle path, [PR #15](https://github.com/rpahasara/lilith-os/pull/15)
added the persistent durability probe, and
[PR #16](https://github.com/rpahasara/lilith-os/pull/16) separated the final
production read-only audit and hardened idempotent synthetic cleanup. Branch
protection was restored before PR #13's final green run and normal merge.

Trusted DEV controls checked out their own default-branch version and built an
allowlisted archive from the exact CI-validated candidate SHA. The manifest
bound every included path and hash; the verifier rejected links, traversal,
extras, hash drift and candidate-SHA drift. The release was installed under
the SHA-named isolated DEV directory and atomically selected. The final
archive SHA-256 was
`92664944efafd3c09abd313cbc5eb6bfd41f64f91061968b4da63bf1189bab5e`;
the unchanged `app.py` SHA-256 was
`bb0a4139641c0a81607263b07fa854deb34241b5fcfcdcab965c6a82dd8826d3`.

The persistent DEV probe used separate DEV cognitive and Privacy databases,
not PROD paths. It prepared one synthetic exact-key item, verified the same
item ID, active revision ID, value digest, proposal/admission/Consent/Policy
and source provenance after the service changed from PID `57019` to `58285`,
and independently reconciled the read facade with SQLite lineage. The
epistemic basis remained `USER_ASSERTED`; it was **not** promoted to verified
truth. Legacy stores remained unchanged. A Privacy hold suppressed the read,
blocked a new mutation, and did not fall back to legacy memory. The probe
then reported `CLEANUP_COMPLETE`: its cognitive DB, Privacy DB and probe
directory were absent. This was idempotent **DEV environment teardown**, not
a production FORGET or Privacy erasure proof.

## Production darkness and merge impact

The pinned production VM was `lilith-01` in project
`lilith-agent-260823-27389`, zone `asia-southeast1-b`, instance ID
`1332996232081478576`. The trusted DEV run audited PROD read-only; the
post-merge check repeated the dark-state audit. SQLite was opened read-only
with query-only mode. Both audits found `canonical_ltm_enabled=false`,
canonical capability inactive, no runtime activation file, no containment
file, empty canonical registry, zero rows in every checked canonical
authority/memory table (21 checked tables) and zero rows in all eight checked
Privacy operational tables. Both database integrity checks were `ok` with
zero foreign-key violations. No real canonical item or revision was present.

The production config SHA-256 stayed
`7d14b571abc73766782fbe2d534e85a4fb1fef628592b478b9747f7c76639586`;
the cognitive DB SHA-256 stayed
`43d40848c35aae5134a60b7467ecedbf35229947a003335d9b64a130deffb544`;
the Privacy DB SHA-256 stayed
`7605ab7bc5a8a1d87c5f7fbe39b7b1ce8307496c6327e41eae90aa54a7bb83f5`.
These comparisons do **not** assert byte equality for the separate legacy
`lilith.db`, for which no pre/post hash was collected.

Merging PR #13 triggered the existing
[production workflow run 35778073209](https://github.com/rpahasara/lilith-os/actions/runs/35778073209)
because `services/core-api/**` changed. The run succeeded, restarted
`lilith-os-api.service` (PID `427970` to `437152`, `NRestarts=0`), and passed
its final `/health` check. The deploy script backed up `app.py` at
`/home/lilith/.hermes/lilith-os/api/app.py.bak.gitdeploy.20260922T200903Z`;
its automatic rollback was not invoked. `app.py` was byte-identical before
and after this deployment. The workflow transfers only `app.py` and its
deploy script: it does **not** install `lilith_memory`, registry/containment
configuration, keys, migrations or databases. The installed legacy app does
not import the canonical package. Thus governed Git source contains the
canonical runtime, but current PROD does not. The app's separate legacy
world-maintenance startup path is outside the canonical DB equality claim;
the observed maintenance report had zero new events, touched beliefs and
staled beliefs.

## Recovery and next boundary

For source or DEV release failure, preserve the accepted SHA and manifest,
use the existing DEV atomic previous-release rollback, and reverify health
and identity; a code rollback is not a Privacy erasure. PROD's current
app-only deployment has its own timestamped `app.py` backup and health-gated
rollback, but it cannot roll forward or back canonical package files that it
never installed. Any future cognitive DB restore requires explicit operator
authority and newer Privacy suppression replay before canonical availability.
Do not activate a class, registry tuple, capability or kill switch as a
recovery shortcut.

The next boundary is **Slice 15B2b-B — Owner Memory Control**: design and,
only after separate implementation authorization, build trusted owner
confirmation, exact query/explain/correct/restore/forget, complete Privacy
owner orchestration, and a production multi-file dark-deployment path. It
must remain inactive with no real value. A later Slice 15B2b-C may consider
an explicitly owner-chosen First Memory only after those gates pass.
