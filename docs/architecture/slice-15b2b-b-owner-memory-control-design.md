# Slice 15B2b-B — Owner Memory Control Design

Status: **DESIGN RECORD** at protected main
`7d0b149a24f7cb5cdf3a9d744171ac3587ff0093`. This is not an acceptance record,
an implementation authorization, an activation instruction, or a claim of real
memory. 15B2b-B is **not** complete or accepted. No key, grant, credential,
memory value, or authority is created by this record.

Labels: **CANONICAL** means the repository already defines it. **INFERRED** is
an architectural inference from canonical text. **PROPOSED** is a design
recommendation that needs separate review and authorization.

## Canonical name and scope

**CANONICAL** ([15B2b-A acceptance record](slice-15b2b-a-acceptance-record.md)):

> The next boundary is **Slice 15B2b-B — Owner Memory Control**: design and,
> only after separate implementation authorization, build trusted owner
> confirmation, exact query/explain/correct/restore/forget, complete Privacy
> owner orchestration, and a production multi-file dark-deployment path. It
> must remain inactive with no real value. A later Slice 15B2b-C may consider
> an explicitly owner-chosen First Memory only after those gates pass.

**INFERRED:** the `15B2b-B1…` records are the foundation track of this slice:

- [B1a owner-proof contracts](slice-15b2b-b1a-owner-proof-contracts.md);
- [B1b-1 broker foundation](slice-15b2b-b1b1-broker-foundation.md);
- [B1b-2a synthetic DEV boundary](slice-15b2b-b1b2a-synthetic-dev-boundary.md);
- B1b-2b first install and Stage II (accepted);
- [B1c deployer authority](slice-15b2b-b1c-acceptance-record.md) (accepted).

**Out of scope (CANONICAL):** real value, First Memory (15B2b-C), activation,
prompt or retrieval consumption, and vectors or embeddings.

## Invariants

**CANONICAL:**

- model proposal ≠ authority;
- execution ≠ verification;
- memory ≠ truth;
- deployment ≠ activation.

**CANONICAL**, from the
[15B1 design](slice-15b1-canonical-ltm-foundations-design.md): "Learning
proposes · LTM admits and stores · Provenance explains · Memory is not truth."

**CANONICAL** security invariants from the
[threat model](../security/threat-model.md):

- #2: a model's decision cannot replace deterministic authorization;
- #6: clients and runtimes cannot directly commit canonical consequential state;
- #9: only L04 may apply;
- #10: cognitive recovery cannot outrank newer Privacy suppression.

**PROPOSED** acceptance invariant: *authoritative acceptance is a verifier
result over the complete authority and provenance chain. No mutable database
flag is authority.* A derived acceptance cache may exist only if it is
explicitly non-authoritative, invalidatable, and recomputable from that chain.

LILITH remains the governed continuity layer. Hermes remains a replaceable
runtime, and models remain replaceable reasoning engines. Neither is an
identity, authority, or truth owner.

## Canonical requirements already in force

- **15B1 prerequisites before the first real admission:**
  1. a real class and closed schema;
  2. the namespace owner and normalization;
  3. admissible source/candidate semantics;
  4. real Consent;
  5. real Verifier where required;
  6. real Rollback Authority;
  7. Privacy retention and true erasure;
  8. capacity policy;
  9. a reviewed retrieval consumer;
  10. explicit production enablement and an acceptance plan.
- **B1a owner proof:**
  - the private credential stays off-host;
  - ES256 WebAuthn with user presence and user verification;
  - a challenge lifetime of at most 60 seconds;
  - the durable challenge state is the replay authority;
  - `VERIFIED_PROOF_ONLY` is not ActorEvidence.
- **B1a owner decision:** "Before live enrollment, Ravindu must choose the
  real RP domain, permitted origins, authenticator(s), and recovery/revocation
  ceremony."
- **B1b-1 broker:**
  - the broker alone constructs requests;
  - it commits a one-time claim keyed by `challengeId` before evidence;
  - it never reissues;
  - it never initializes a missing production ledger;
  - its ledger records a recovery epoch.
- **15B2a Privacy:**
  - Privacy is the only FORGET owner;
  - a hold precedes erasure;
  - FORGET is never `SUPERSEDE(null)`;
  - restore replays suppression.
- **ADR-0006:** "First Memory remains a later owner-controlled stage."
- **Threat model T-24:** "B1b-2/B1b-3 isolation review before live authority."

## The central authority gap

**CANONICAL**
([15B2a design](slice-15b2a-canonical-memory-authority-privacy-containment-design.md)):

- `LocalOwnerAuthority` issues HMAC-authenticated `ActorEvidenceRefV1` with a
  key stored at `/home/lilith/.hermes/lilith-os/data/actor_authority.key`,
  `lilith:lilith 0600`.
- The Privacy authority key is held the same way.
- The broker installer records custody of `cognitiveDb`, `privacyDb`,
  `actorKey`, `privacyKey`, and `containmentKey` as `ABSENT`.
- B1a states that "current `lilith` can still read keys and write databases."

**INFERRED:** a compromised application user can therefore mint owner-looking
evidence and write rows that pass as admitted memory. Owner Memory Control must
move authority out of the application, as B1c moved activation out of it.

## Threat model

Assets: owner authorization, the canonical value and its identity, the evidence
chain, activation, and Privacy state.

| Threat | Forbidden outcome | Required control | Evidence |
| --- | --- | --- | --- |
| Compromised `lilith` (runs app code, reads its 0600 keys, writes cognitive and Privacy DBs) | Mints evidence or erasure authorization; rows pass as accepted | **PROPOSED:** issuance keys leave `lilith` (B1b-3); acceptance is a verifier result | `lilith`-authored rows without broker-signed evidence are `NOT_ACCEPTED`; OS test shows no key read |
| Compromised Hermes, or a malicious or hallucinating model | Self-authorized or substituted memory | **CANONICAL:** broker-only request construction (T-21); owner signs digest-bound bytes; model output is never config (T-17) | Golden vectors; mutated-field tests; static path scan |
| Compromised CI/CD or routine DEV deployer | Gains key or authority custody; replaces the verifier | **CANONICAL:** B1c fixed helper with no root. **PROPOSED:** keys, registry, and verifier outside the helper's reach | Extend B1c's per-deploy `DENIED` list |
| Legacy PROD deployer (project-wide `osAdminLogin`, root on DEV) | Root on the memory host | See "Relationship to existing debt" | Cloud gate |
| Direct database writer | A row becomes authority | **PROPOSED:** verifier result bound to broker-signed evidence and the owner-proof reference | Inserted and tampered row tests |
| Compromised broker | Forged owner consent | **CANONICAL:** owner key off-host. **PROPOSED:** the chain carries a re-verifiable owner-assertion reference | Offline re-verification test |
| Stale authorization | Late use | **CANONICAL:** ≤60 s; expiry re-checked under lock after cryptography | Expiry-crossing tests |
| Replayed authorization | Second use | **CANONICAL:** durable `CONSUMED`; unique claim and evidence nonce (T-22) | Restart-replay tests |
| Substituted content or metadata | Owner approves X, Y is stored | **CANONICAL:** `payloadDigest` and `actionDigest`; L04 revalidates | Digest-drift tests |
| Signing-key compromise (authenticator or broker key) | Forged authority | **CANONICAL:** credential `REVOKED`. **PROPOSED:** broker key IDs in the evidence envelope; revoked keys fail acceptance after revocation | Revocation tests |
| Authorization copied DEV↔PROD | Cross-environment acceptance | **PROPOSED:** `deploymentEnvironment` and `authorityDomain` in the challenge; per-environment credentials and broker keys | Cross-environment replay test |
| Rollback or snapshot restore | Revived revoked or forgotten state | **CANONICAL:** suppression replay; ledger recovery epoch; B1b-3 restored-ledger policy | FORGET→restore drill |
| Partial write or crash | Half-accepted memory | **CANONICAL:** one L04 `BEGIN IMMEDIATE`; no cross-DB transaction; conservative crash table | A1–A5 synthetic matrix |
| Execution/verification confusion | Apply success treated as acceptance | **PROPOSED:** separate verifier result | Apply-succeeded, verifier-fails test |
| Accepted before durable commit | Acknowledgement without state | **CANONICAL:** acknowledge after commit; replay gives `ALREADY_APPLIED` | Lost-ack test (A5) |
| Durable without authority evidence | Orphan treated as memory | **PROPOSED:** `NOT_ACCEPTED(EVIDENCE_ABSENT)`, quarantined, never backfilled | Orphan-row test |
| Wrong identity context | Memory bound to a different owner or LILITH | **CANONICAL:** `logicalOwnerId`. **PROPOSED (deferred):** LILITH identity and charter binding | Owner-mismatch test |
| Conflicting owner grants | Race on one item | **CANONICAL:** `expectedActiveRevisionId` gives `PRECONDITION_FAILED` | Barrier concurrency test |
| Deletion or revocation ambiguity | "Forgotten" still readable or restorable | **CANONICAL:** hold → erasure → all-owner `COMPLETE`. **PROPOSED:** crypto-erasure | FORGET + backup + restore drill |

## State model

**PROPOSED.** The model composes the existing canonical state vocabularies
rather than introducing a new generic ladder.

| Layer (owner) | States | Source |
| --- | --- | --- |
| Proposal (L18 V2) | immutable `learning_proposal` and ref, family `OWNER_DIRECTED_PROJECT_CODENAME_V1` | CANONICAL |
| Owner proof (broker ledger) | `PREPARED` → `CONSUMED` \| `CANCELLED` \| `EXPIRED` | CANONICAL (B1a) |
| Broker claim | `CLAIMED` → `EVIDENCE_COMMITTED` \| `ABANDONED` | CANONICAL (B1b-1) |
| Authority (Actor, Consent, Policy) | evidence issued, then resolved | CANONICAL (15B2a); issuer custody PROPOSED to move |
| Storage (L04) | `ACCEPTED` \| `REJECTED` \| `PRECONDITION_FAILED` admission; immutable revision, audit, active pointer | CANONICAL (15B1) |
| Acceptance | `ACCEPTED_MEMORY` \| `NOT_ACCEPTED(reason)` as verifier output | PROPOSED |
| Retirement | SUPERSEDE or RESTORE (new revision); FORGET: hold → erasure → `COMPLETE` | CANONICAL |

**Owner authority** is required for consuming a proof for CREATE, SUPERSEDE,
RESTORE, or FORGET, and separately for the class capability's activation grant
(B1c). **Broker verification** covers proof verification and consumption, the
claim, and (PROPOSED) evidence issuance. **Storage state** covers proposal,
admission, revision, audit, and active-pointer rows.

A write, a model output, or a successful execution each supply at most one
input to the verifier. None of them is acceptance.

## Owner authorization contract

**INFERRED:** `OwnerMemoryChallengeV1` (B1a) is the right basis. It already
binds:

- `protocol`, `schemaVersion`, `ownerPrincipal`, `challengeId`;
- `actionDigest`, `requestDigest`, `payloadDigest`;
- `operation`, `memoryClass`, `subjectNamespace`, `subjectKey`, `purpose`;
- the revision and restore targets;
- `privacyNoticeVersion`, `nonce`, `issuedAt`, `expiresAt` (≤60 s), `rpId`;
- the domain separator `LILITH_OWNER_MEMORY_CHALLENGE_V1`.

It is signed by the ES256 credential record.

**PROPOSED `OwnerMemoryChallengeV2`** adds only logical authority context:

- `deploymentEnvironment`, the canonical broker configuration field name;
- `authorityDomain`, the logical authority scope within the environment;
- `logicalOwnerId`, where canonical `owner.ravindu.v1` is the stable logical owner ID;
- `policyVersion` and the registry tuple version;
- `ledgerEpoch`, bound to the canonical broker recovery epoch, so that an
  authorization prepared before a ledger restore cannot be consumed after it.

V1 golden vectors remain immutable. V2 uses a new domain separator and its own
vectors.

**Explicitly excluded from the owner-signed challenge:**

- **Any VM, machine, cloud instance, or physical broker-host binding.** LILITH
  continuity must survive VM, cloud, device, and runtime replacement. Host and
  instance facts may appear in provenance only.
- **Any broker issuance key identifier.** The owner authorizes the memory
  operation, not a particular broker key. The broker evidence envelope carries
  `brokerKeyId`, the broker release/version, and the evidence
  signature/digest, so broker keys can rotate without invalidating an owner
  authorization.

**Deferred schema extension:** the repository has no versioned identity-charter
artifact and no canonical LILITH-system identity identifier. `principles.md`
and `component-boundaries.md` refer to a versioned identity charter, but none
exists. A charter or LILITH-identity binding therefore is not a mandatory V2
field and does not appear in the first V2 golden vectors. It will be added as
a versioned extension once a canonical artifact exists. No placeholder charter
may be invented to fill the field.

**Separate mechanisms (PROPOSED):** memory authorization does not reuse the B1c
activation grant.

| | Activation (B1c) | Memory authorization |
| --- | --- | --- |
| Purpose | standing capability | per action, single use, ≤60 s |
| Mechanism | `ssh-keygen -Y`, namespace `lilith-canonical-activation` | WebAuthn ES256 with user verification |
| Key | owner SSH key | owner authenticator |

Separate keys, namespaces, and verifiers mean that compromising one never
yields the other.

## Cognitive and Privacy storage boundary

**CANONICAL today:**

- **Cognitive DB:** L18 proposals; L04 items, revisions, sources, admissions,
  and audits; Actor, Consent, Policy, and Rollback tables.
- **Privacy DB:** separate, holding forget requests, holds, erasure
  authorizations, per-owner results, and receipts.
- **Keys:** the Actor, Privacy, and containment HMAC keys are all `lilith 0600`.
- **Broker:** `owner_control.db` (challenges, requests, public credentials,
  claims) and a synthetic evidence DB, with no cognitive, Privacy, or key
  custody.
- **Application-visible:** the advisory `canonical-runtime.json`.

**PROPOSED:**

- The plaintext value lives only in the L04 revision. The broker ledger,
  Privacy DB, evidence, provenance, and logs hold digests and opaque IDs,
  consistent with the canonical rule that no value is added to logs.
- The broker holds issuance keys; the application holds only public
  verification material.
- A future per-item data key under Privacy/broker custody would make FORGET a
  cryptographic retirement that also covers backups (T-09, T-14). This is
  design only; no encryption is implemented.

**Honest limit:** the L04 read facade runs in the application, so a compromised
`lilith` can read memory it serves. This design prevents minting and forging
acceptance, not reading.

## Key custody

| Material | Custody | Label |
| --- | --- | --- |
| Owner memory credential (WebAuthn private key) | Owner authenticator, off-host, never exported | CANONICAL |
| Owner activation key (SSH) | Owner, off-host | CANONICAL (B1c) |
| Public credential registry | Broker `owner_control.db` | CANONICAL |
| Actor, Privacy, and containment issuance keys | `lilith 0600` today; move to broker custody or broker-private asymmetric keys in B1b-3 | CANONICAL today / PROPOSED move |
| Future data keys | Privacy/broker custody | PROPOSED |

- **DEV/PROD separation (PROPOSED):** separate RP IDs, origins, credentials,
  broker keys, and ledgers; the challenge binds `deploymentEnvironment`.
- **Rotation (PROPOSED):** broker key IDs travel in evidence envelopes with
  overlapping validity.
- **Revocation:** credential `REVOKED` is CANONICAL; broker-key revocation is
  PROPOSED.
- **Recovery and loss:** CANONICAL owner decision (B1a). PROPOSED: at least two
  enrolled authenticators; losing all of them stops new authority but not
  retention.
- **Never available to:** the model, Hermes, the routine deployer, `lilith`,
  the repository, or CI logs. B1c's denial proofs extend to the new paths.

## Provenance contract

**CANONICAL:** proposal fingerprint and candidate/source binding;
`epistemicBasis`, never promoted; revision lineage (`supersedes`/`restores`);
admission and apply audit; Consent and Policy references.

**PROPOSED additions**, immutable per accepted revision:

- memory digest;
- owner-proof reference: `challengeId`, credential record ID, verified request
  digest, assertion digest;
- broker claim and evidence IDs, `brokerKeyId`, and broker release;
- policy, registry, and environment context, plus `logicalOwnerId`;
- L04 transaction and audit ID, and timestamps;
- previous accepted revision digest (hash chain);
- Privacy lineage reference;
- host and instance facts, as provenance only.

The record asserts "the owner authorized LILITH to retain X". It never asserts
that X is true.

## Failure and recovery

| Case | Behavior | Label |
| --- | --- | --- |
| Crash before owner verification | `PREPARED`, then `EXPIRED` | CANONICAL |
| Consumed, no claim (A2) | Proof burned; new confirmation | CANONICAL |
| Claim, no evidence (A3) | `ABANDONED`; never reissued | CANONICAL |
| Evidence, no link (A4) | Reconcile the same evidence by its unique nonce | CANONICAL |
| Crash during L04 commit | Single transaction, nothing partial, retryable | CANONICAL |
| Commit succeeded, acknowledgement lost (A5) | `ALREADY_APPLIED`, same IDs | CANONICAL |
| Authorization consumed, memory absent | Terminal; owner re-confirms | CANONICAL / INFERRED |
| Memory present, evidence absent | `NOT_ACCEPTED(EVIDENCE_ABSENT)`, quarantined, never backfilled from a consumed proof | PROPOSED |
| Replay after restart | Rejected by durable challenge state | CANONICAL |
| DB rollback | Suppression replay, then full chain re-verification before readiness | CANONICAL / PROPOSED |
| Broker ledger rollback | Recovery epoch advances; challenges bound to an older `ledgerEpoch` are void | CANONICAL field / PROPOSED rule |
| Owner revocation after acceptance | Blocks new authority; retirement only by explicit FORGET or SUPERSEDE; verifier reports revoked-key status | PROPOSED |

## Synthetic test ladder

**PROPOSED.** The ladder mirrors the repository's TEST → DEV_SYNTHETIC →
owner-marker pattern. No phase uses a real memory. Every phase stops by failing
closed and preserving evidence.

| Phase | Mutation | Authority | Pass criteria |
| --- | --- | --- | --- |
| A — Contracts | None (temp SQLite, `LILITH_ENV=test`) | Normal PR | V2 vectors; verifier rejects every reachable forgery |
| B — Signed synthetic chain | None | Normal PR | End-to-end `.invalid` chain; tampered rows give `NOT_ACCEPTED` |
| C — DEV_SYNTHETIC broker integration | Broker release via owner installer | Owner decision | Broker-issued synthetic evidence; OS proof that `lilith` cannot mint |
| D — Crash/replay | DEV synthetic state | Separate owner decision and harness | A1–A5 matrix |
| E — Privacy and key custody (B1b-3) | Custody moves, DEV only | Owner decision | T-24 closed; epoch drill; FORGET→restore suppression |
| F — Owner acceptance gate | None | Owner review | Enrollment ceremony, RP, and recovery decided; gates extended; cross-environment debt resolved |
| G — 15B2b-C First Memory | One real memory | Separate slice | Outside 15B2b-B |

## Relationship to Stage III A2

**CANONICAL:** A2 (`A2_AFTER_PROOF_CONSUME_BEFORE_CLAIM`) is one of five crash
points, and A1, A3, A4, and A5 also remain open. A2 is deferred and unproven;
its controller stopped at INTENT and must not be retried.

**INFERRED:** the proof-to-authority crash model is proven by deterministic
fault hooks but not live under systemd.

**PROPOSED:** 15B2b-B does not retry the A2 controller. Phase D is a freshly
authorized, synthetic A1–A5 rehearsal against the post-B1c boundary. Until it
passes, crash semantics for real memory are "unit-proven, live-unproven".

## Relationship to existing debt

**INFERRED:** `CROSS_ENVIRONMENT_PROD_AUTHORITY_DEBT` can violate Owner Memory
Control. The legacy PROD identity's project-wide `osAdminLogin` is root on DEV
and is exercised automatically by `deploy.yml`. Root on a memory-authority host
can read broker keys and replace the verifier or public registry. B1a classes
host-root as Level 3, beyond what an off-host key protects against.

**Classification:**

- **Not blocking:** this design and synthetic phases A–E.
- **Required before PROD memory.**
- **PROPOSED:** also required before any real owner authority on a host it can
  root (phase F).

## B1d

**CANONICAL:** B1d appears once, in B1a ("remains root-capable until
B1b/B1c/B1d"). It is otherwise undefined and is **not** accepted architecture.

**PROPOSED** candidate scope, for owner decision only: retire the remaining
routine root-capable identities over any memory-authority host, together with
the PROD multi-file dark-deployment path.

It is not required for this design or for phases A–E. It is required before
phase F and before PROD memory. It is the point at which Level 2 could be
claimed.

## Unresolved owner decisions

1. Real RP domain, origins, authenticator models, and the recovery/revocation
   ceremony (CANONICAL owner decision).
2. Whether, and how, to create a versioned identity charter and a stable
   LILITH-system identity identifier.
3. **First Memory class.** INFERRED intended class: project codename
   (`OWNER_DIRECTED_PROJECT_CODENAME_V1`,
   `canonical_memory.project_codename.mutate`). Confirm it and answer 15B1
   prerequisites 1–3.
4. The environment of the first real memory: DEV or PROD.
5. Custody design: broker-signed evidence with `lilith` keeping the cognitive
   DB, or full broker custody of the cognitive DB.
6. The retrieval consumer and its non-authoritative semantics (15B1 #9).
7. The retention policy for the class (15B1 #7).
8. Whether live crash evidence (phase D) is required before real authority.
9. B1d scope.
10. Level 3 posture: accepted residual risk, or mitigation.

## Proposed sub-slices

**PROPOSED** names; B1b-3 is the canonical gate name.

1. **15B2b-B2a — Accepted-memory contract and verifier** (TEST only).
2. **15B2b-B1b-3 — Custody isolation review** (issuance keys; restored-ledger
   epoch policy; closes T-24).
3. **15B2b-B2b — Broker-mediated synthetic CREATE, end to end**
   (DEV_SYNTHETIC).
4. **15B2b-B2c — A1–A5 synthetic crash/replay rehearsal** (fresh
   authorization; not an A2 retry).
5. **15B2b-B2d — Privacy FORGET orchestration and crypto-erasure design**
   (synthetic).
6. **15B2b-B2e — Owner enrollment ceremony design** (owner decisions; no
   enrollment).
7. **15B2b-B1d** (if the owner defines it) — retire remaining root-capable
   identities and the PROD multi-file dark path.
8. **Owner acceptance gate**, then 15B2b-C.

## First implementation recommendation

**PROPOSED: 15B2b-B2a — Accepted-memory contract and verifier**, TEST only. It
is not implemented by this record. It should eventually define:

- `OwnerMemoryChallengeV2` with logical authority context only, and golden
  vectors;
- a synthetic broker evidence envelope carrying `brokerKeyId`, broker
  release/version, and signature/digest;
- the acceptance-verifier result taxonomy with `ACCEPTED_MEMORY` and
  `NOT_ACCEPTED(reason)` semantics;
- tamper, substitution, and replay tests.

Pass criterion: every forgery reachable as `lilith`, a model, or a database
writer yields `NOT_ACCEPTED`.

It must use no infrastructure, no real keys, no DEV change, and no activation.
It should stay outside `services/core-api/**`, or explicitly accept that
merging would trigger the PROD workflow, as B1a warned.
