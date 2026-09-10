# Slice 15B2a — Canonical Memory Authority, Privacy, and Containment Foundations

Status: implemented and deployed as foundations on 2026-09-10. This slice does not activate canonical long-term memory.

## Boundary and invariant

Slice 15B2a adds the authority, privacy, containment, and V2 schema boundaries required before one future closed canonical-memory class can be activated. Production remains deliberately inert:

- `canonical_ltm_enabled: false`
- the full-tuple production registry is empty
- the legacy-containment registry is absent, which means empty
- no Home memory-authority transport or confirmation UI exists
- no real actor evidence, consent, policy decision, rollback authorization, learning V2 proposal, privacy request, or canonical memory row exists

The governing order is:

`Actor → exact tuple/schema → Policy → confirmation → Consent → L18 V2 → L04 V2 independent validation → apply`

`RESTORE` additionally requires Rollback Authority after Consent. `FORGET` is owned by Privacy Governance and is never represented as `SUPERSEDE(null)` or `RESTORE`.

The governing separation remains: Learning proposes; LTM admits and stores; provenance explains; memory is not truth.

## Trust and action contracts

`FrozenMemoryActionV1` is the shared semantic identity. Its canonical digest binds the actor, operation, exact `(memoryClass, subjectNamespace, subjectKey)` tuple, value schema and payload digest, expected active revision, restore revision, and closed purpose. Generated IDs and timestamps are excluded.

`LocalOwnerAuthority` issues `ActorEvidenceRefV1` only after receiving a server-side request digest, action digest, nonce, and expiry. Evidence is HMAC-SHA256 authenticated with a 32-byte owner-only key, short-lived, action/request bound, and single-use through `actor_evidence_consumption`. A browser session ID or the string `operator` has no authority. This is truthfully described as `OWNER_CONTROLLED_HOME_CONTEXT`, not generalized human authentication.

The issuer key is stored only at `/home/lilith/.hermes/lilith-os/data/actor_authority.key`, owned by `lilith:lilith`, mode `0600`. It is not stored in a database, contract, log, browser payload, source file, or repository.

## Consent and Policy

`ConsentStore` owns a non-durable confirmation challenge and append-only `ConsentRefV1` grants/revocations. A challenge freezes the exact action, actor evidence, intent, confirmation event, purpose, and privacy-notice version. Cancellation and expiry leave no durable grant or value. Confirmation is not offered until Policy has resolved the same action as allowed.

The consent fingerprint binds actor and evidence identities, exact tuple, operation, payload digest, precondition, restore target, purpose, authority version, privacy notice, intent, and action digest. It excludes timestamps, generated IDs, UI data, transcript, free-form reason, credentials, emotion, and confidence. Revocation affects future resolution and read eligibility but does not itself mutate L04.

`MemoryPolicyStore` is separately owned. Callers request a decision; they cannot submit an `ALLOWED` value. `PolicyDecisionRefV1` durably binds the narrow capability `canonical_memory.project_codename.mutate` to the same frozen action. The capability is registered as `INTERNAL_WRITE` metadata with `productionActive: false`; it does not activate a production memory class.

Generic write approval remains generic approval. It is neither Consent nor Policy.

## Rollback Authority

`RollbackAuthority` issues `RollbackAuthorizationRefV1` only for `RESTORE`. It binds the grounded actor/evidence, memory item, expected current revision, exact historical revision, target value digest, purpose, confirmation event, and frozen action digest. Authorization is one-time and consumption is append-only. A caller string cannot authorize restore.

## Privacy Governance

Privacy Governance has a physically separate database, `/home/lilith/.hermes/lilith-os/data/privacy_governance.db`, and an independent 32-byte HMAC key at `privacy_authority.key`; both are `0600 lilith:lilith`.

`ForgetMemoryRequestV1` identifies exactly one canonical identity and requires grounded actor evidence. Privacy Governance creates an exact hold before erasure authorization. The hold suppresses canonical reads and blocks V2 eligibility/apply until all required owners report completion.

`ErasureAuthorizationRefV1` is HMAC authenticated, owner-scoped, exact-identity bound, nonce bound, short-lived, and separately resolved by each owner. Dedicated erasure adapters exist for L04, L18 V1, L18 V2, Actor Authority, Policy, Consent, Rollback, legacy Memory/User files, skills, and pending records. Ordinary runtime connections retain their immutable-row authorizers; arbitrary SQL is not granted to L04, L18, Consent, or callers.

Completion requires every required owner result. Partial or failed execution keeps the hold active and cannot emit `COMPLETE`. The minimized completion receipt contains opaque identifiers, owner/status summaries, timestamps, and fingerprints; it contains no plaintext value.

Restore suppression uses a keyed opaque selector, never raw `SHA256(value)`. A restored backup must replay suppression and complete verification before availability. Backup retention is configuration-owned, bounded to 1–30 days, never auto-deleted by this foundation, and never permits restoring an old cognitive database over newer privacy state.

## L18 V2 and L04 V2

L18 V1 career semantics and rows are untouched. V2 uses separate typed tables so its candidate/proposal contract cannot reinterpret V1 data. The candidate envelope stores a digest rather than duplicate plaintext; the typed intent and proposal are the only planned normalized-value holders. Each mutation gets a fresh candidate. Actor, Policy, Consent, privacy-hold, and containment readiness are required before `REAL_ELIGIBLE`.

`learning_proposal_ref` provides exact family dispatch between existing `L18_V1_CAREER` and future `OWNER_DIRECTED_PROJECT_CODENAME_V1` proposals. Unknown families fail closed.

L04 V2 owns the closed, full-tuple registry `(memoryClass, subjectNamespace, subjectKey)`. A registry entry also binds value schema, capability, read/write permissions, and Consent requirement. Production has zero entries. The production-path constructor rejects a synthetic non-empty registry. `L04V2Gate` independently resolves proposal family, actor evidence, Policy, Consent, Rollback for restore, privacy hold, kill switch, and exact registry entry. In 15B2a it validates only and has no production mutation bridge.

`CanonicalMemoryReadFacade` requires a grounded actor, exact allowed registry tuple, no privacy hold, and valid Consent for the active revision. A miss or suppression returns a canonical miss. There is no fallback to `MEMORY.md`, `USER.md`, World, chat context, or legacy `/memory/*`.

## Legacy containment

The containment registry stores only exact tuples, keyed value fingerprints, and action digests. The 15B2a production registry is empty. A missing/malformed/weak key, unavailable registry, empty registry, or nonmatching registry all fail closed for a recognized canonical action. Ordinary unmarked legacy writes retain prior behavior.

Containment is enforced at every discovered persistence boundary:

- Memory/User direct add, replace, remove, and batch helpers
- generic pending-write staging
- approved pending Memory replay
- skill create, edit, patch, supporting-file write, and generic skill gate
- approved pending skill replay before approval bypass
- background-review prompt construction

Typed memory-lane messages are removed before background-review prompt construction. If the helper import fails, the local fallback still excludes recognized actions. No cadence, summarization, personality, prompt, or unrelated skill-generation behavior changed.

## Persistence ownership

The cognitive database adds separately authorized tables for:

- Actor: `actor_evidence_ref`, `actor_evidence_consumption`
- Consent: `consent_grant`, `consent_revocation`
- Policy: `policy_decision`
- Rollback: `rollback_authorization`, `rollback_consumption`
- L18 V2: `learning_memory_intent_v2`, `learning_candidate_v2`, `learning_project_codename_candidate_v1`, `learning_candidate_source_v2`, `learning_assessment_v2`, `learning_proposal_ref`, `learning_proposal_v2`
- L04 V2 registry: `memory_registry_entry`

Each owner has its own migration ledger and SQLite authorizer. Runtime stores can write only their owned tables. Append-only triggers reject ordinary update/delete paths. Privacy erasure operates through explicit owner adapters with a valid Privacy authorization, not through the ordinary runtime stores.

The Privacy database owns `privacy_governance_config`, `privacy_forget_request`, `privacy_hold`, `privacy_erasure_authorization`, `privacy_erasure_authorization_owner`, `privacy_erasure_execution`, `privacy_completion_owner_result`, `privacy_completion_receipt`, and `privacy_restore_suppression_manifest`, plus its migration ledger.

## Migration and rollback discipline

Migration is additive, atomic within each database, schema-fingerprinted, count-preserving, idempotent in isolated tests, and gated by a fresh verified SQLite online backup for the production cognitive path. The migration refuses unknown tables, stale backup evidence, fingerprint drift, non-empty new operational tables, integrity failures, and foreign-key failures.

Operational rollback starts with the already-false kill switch and empty registries. Timestamped source copies restore only the authorized code seams. Additive empty tables may remain; they are not dropped automatically. The pre-migration cognitive backup may be restored only after an explicit corruption determination and a Privacy suppression replay-before-availability procedure. The empty Privacy database may remain.

## Explicitly deferred to Slice 15B2b

No production project-codename registry entry, real memory value, live remember/update/restore/forget action, canonical query route, confirmation UI, Home activation, Telegram integration, vector retrieval, graph retrieval, embeddings, scheduler, or autonomous consolidation is part of this slice.
