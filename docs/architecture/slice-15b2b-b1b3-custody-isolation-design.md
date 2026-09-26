# Slice 15B2b-B1b-3 — Authority and Key Custody Isolation Design

Status: **DESIGN RECORD** at protected main
`99edaaa8585cf1a6122c76abb760bc1cfb882de0`. This is not an acceptance record,
an implementation authorization, an activation instruction, or a claim of real
memory or real owner authority.

This record freezes the design produced by the completed B1b-3 custody review,
with the review corrections incorporated. It does **not** mark any of the
following as complete, achieved, or ready:

- B1b-3;
- Level 2 isolation;
- real owner authority;
- real memory;
- Privacy custody;
- Stage III.

No key, registry, signer, grant, credential, memory value, or authority is
created, installed, or rotated by this record. No DEV, PROD, IAM, WIF, or
systemd state is changed.

Labels:

- **CANONICAL** — the repository's accepted architecture records already
  define it.
- **IMPLEMENTED** — current source or installed state, as evidenced in the
  repository and its acceptance records. Implemented is not the same as
  accepted target architecture; several implemented facts below are debt.
- **INFERRED** — an architectural inference from canonical or implemented
  facts.
- **PROPOSED** — a design recommendation that needs separate review and
  authorization. All sub-slice names in this record are PROPOSED.

## Canonical name and position

**CANONICAL** ([threat model](../security/threat-model.md) T-24): "B1b-2/B1b-3
isolation review before live authority."

**CANONICAL** ([15B2b-B design](slice-15b2b-b-owner-memory-control-design.md)):
B1b-3 is the custody-isolation gate. It moves issuance keys out of the
application, defines the restored-ledger epoch policy, and closes T-24.

**INFERRED:** B1b-3 sits after [B1c](slice-15b2b-b1c-acceptance-record.md),
which moved *activation* authority out of the application, and after
[B2a](slice-15b2b-b2a-accepted-memory-verifier.md), which defined a TEST-only
accepted-memory verifier. B1b-3 does for *memory evidence* authority what B1c
did for activation.

## Invariants

**CANONICAL:**

- model proposal ≠ authority;
- execution ≠ verification;
- memory ≠ truth;
- deployment ≠ activation;
- emotion ≠ authority.

**CANONICAL** (15B2b-B): authoritative acceptance is a verifier result over the
complete authority and provenance chain. No mutable database flag is
authority.

**PROPOSED** (this record): no private authority-signing key is ever in
application custody.

## Current implemented debt

**IMPLEMENTED.** These facts describe the system as it stands. They are the
reason B1b-3 exists, and none of them is resolved by this record.

| # | Fact | Source |
| --- | --- | --- |
| D1 | The PROD application user `lilith` owns the Actor HMAC private material (`actor_authority.key`, `lilith:lilith 0600`). | [15B2a](slice-15b2a-canonical-memory-authority-privacy-containment-design.md) |
| D2 | The PROD application user `lilith` owns the Privacy authority and restore-selector private material (`privacy_authority.key` and the keyed selector input). | 15B2a |
| D3 | Policy (`PolicyDecisionRefV1`), Consent (`ConsentRefV1`), and Rollback (`RollbackAuthorizationRefV1`) authority inputs are durable rows in the application-owned cognitive DB. A direct application DB writer can forge them. | 15B2a; INFERRED from custody |
| D4 | The Privacy DB (`privacy_governance.db`) is owned by `lilith`. | 15B2a |
| D5 | The containment key is a **detection PRF** over legacy tuples and values. It is not an authority-signing key, and it must not be promoted to one. | 15B2a |
| D6 | The B2a accepted-memory verifier is TEST-only. It refuses any non-`test` context and is not wired to L04. | [B2a](slice-15b2b-b2a-accepted-memory-verifier.md) |
| D7 | No live broker-held asymmetric signing key exists. B2a uses in-process test keys only. | B2a |
| D8 | The broker ledger's `authority_epoch` is a static text value in `broker_schema_v1`. It has no restore-advancement semantics. | `services/memory-broker/lilith_memory_broker/state.py` |

**INFERRED:** by D1–D4, a compromised `lilith` can mint owner-looking Actor
evidence and Privacy erasure authorization, and can write Policy, Consent, and
Rollback rows that current readiness checks accept.

## Target security property

**PROPOSED:**

> A compromised `lilith` application identity, Hermes instance, model-driven
> tool path, routine deployer, or direct cognitive-DB writer may propose or
> corrupt untrusted state, but cannot independently manufacture the
> cryptographic authority chain that the authoritative memory verifier
> accepts.

Accepted authority requires all of the following:

1. valid owner authorization, where the operation requires it;
2. broker or authority-domain evidence signed by a private key outside
   application custody;
3. correct environment, authority-domain, epoch, and registry bindings;
4. canonical L04 admission linked to that evidence;
5. verification of the complete chain.

**Not claimed** by this property:

- broker compromise is solved;
- host root is solved;
- the legacy PROD root debt (`CROSS_ENVIRONMENT_PROD_AUTHORITY_DEBT`) is
  solved;
- owner credential compromise is solved;
- Level 3 isolation.

**Honest limit (CANONICAL, 15B2b-B):** the L04 read facade runs in the
application. B1b-3 prevents minting and forging acceptance; it does not
prevent a compromised `lilith` from reading memory it serves.

## Target architecture

**PROPOSED:**

- **Asymmetric evidence signing.** Authority evidence is signed with Ed25519.
  The application holds only public verification material. HMAC authority keys
  are retired from the authority path.
- **Separate cryptographic domains.** The Owner/Actor authority domain and the
  Privacy authority domain have separate signing keys, separate registry
  entries, separate domain separators, and separate evidence types. Evidence
  from one domain never verifies in the other.
- **Public verification registry.** Verification keys are published through an
  owner-signed registry (see *Key registry*). The application can read it and
  cannot write it.
- **Application custody.** The cognitive DB may remain owned by `lilith`.
  Forged or tampered rows remain possible but are non-authoritative: they fail
  verification.
- **Privacy migrates separately.** Privacy state and custody move in their own
  gate (B1b-3f), not in the first contracts slice.
- **Containment remains detection.** The containment PRF key keeps its
  detection role and is never used to sign or authorize.
- **B2a reuse without promotion.** B2a verifier patterns (canonical bytes,
  domain separators, closed reason taxonomy, trusted context) may be reused.
  B2a TEST contracts are not silently promoted to production; production use
  requires new versioned contracts and their own vectors.
- **Dedicated authority service.** A separate authority service, distinct from
  the memory broker, is a possible later hardening. It is not a B1b-3
  prerequisite.

## Distinct authority roots

**PROPOSED, review correction 1.** Three conceptual roots stay distinct in the
design:

```text
activation authority  ≠  authority-registry root  ≠  owner WebAuthn credential
```

| Root | Purpose | Mechanism (current or proposed) |
| --- | --- | --- |
| Activation authority | standing capability activation | CANONICAL (B1c): owner-signed grant, `ssh-keygen -Y`, namespace `lilith-canonical-activation` |
| Authority-registry root | signs the public key registry | PROPOSED: distinct signer; production custody **unresolved** |
| Owner WebAuthn credential | per-action, single-use memory authorization | CANONICAL (B1a): ES256 with user presence and verification, off-host |

- The design does **not** canonize reuse of the B1c activation SSH private key
  as the registry root.
- B1b-3a TEST fixtures use a **separate synthetic registry signer**.
- The production registry-root choice is an **unresolved owner decision**. A
  later owner decision may evaluate operational reuse of an existing owner key.
  The design must not require it, and verifiers must treat the registry root
  as its own trust anchor with its own namespace and domain separator.

## Key registry

**PROPOSED.** The registry is an owner-signed, versioned document of
`AuthorityKeyRecordV1` entries.

`AuthorityKeyRecordV1` fields:

| Field | Meaning |
| --- | --- |
| `keyId` | stable opaque identifier, carried in every evidence envelope |
| `authorityDomain` | e.g. Owner/Actor or Privacy; exactly one per key |
| `evidenceTypes` | closed list of evidence types this key may sign |
| `environment` | `test` \| `dev` \| `prod`; exactly one per key |
| `algorithm` | `Ed25519` only in V1 |
| `publicKey` | public verification material |
| `notBefore` | start of the valid interval |
| `retiredAt` | end of routine validity, or null |
| `revokedAt` | revocation time, or null |
| `revocationReason` | closed enum, e.g. `ROUTINE`, `COMPROMISED`, `SUPERSEDED` |
| `compromisedSince` | earliest suspected compromise time, or null |
| `recoveryEpoch` | the recovery epoch the key belongs to |
| `policyVersion` | policy version the key is bound to |

The signed registry document additionally carries a monotonic
`registryVersion`, the environment, and the registry-root key identifier.

**Verification rules (PROPOSED):**

- the registry signature verifies under the registry root for that
  environment;
- `registryVersion` never decreases relative to the last accepted version;
- a key verifies evidence only for its own domain, evidence types,
  environment, and recovery epoch;
- cross-domain, cross-environment, and cross-epoch use is rejected.

### Retirement versus compromise

- **ROUTINE RETIREMENT.** Historical evidence remains valid if it was signed
  inside the key's valid interval `[notBefore, retiredAt)`. New evidence
  signed after `retiredAt` is rejected.
- **COMPROMISE.** Evidence signed by a compromised key is distrusted
  **retroactively**, unless it has been independently re-attested.

**Honest limit:** `issuedAt` is signer-controlled. An attacker holding a
compromised key can backdate evidence to before `compromisedSince`, so
`compromisedSince` alone cannot separate genuine historical evidence from
forged backdated evidence. Timestamps alone do not solve compromise.

**PROPOSED, unresolved:** owner-supplied or independently trusted time and
ordering evidence (for example, owner-signed checkpoints over accepted
evidence digests, or an independent monotonic anchor) must eventually allow
pre-compromise evidence to be re-attested. Until then, compromise means
retroactive distrust of every piece of evidence the key signed.

## Recovery epoch

**PROPOSED.** The recovery epoch is a pair:

```text
recoveryEpoch = (counter, random)
```

- `counter` is monotonic and advances on every recognized restore or recovery.
- `random` is fresh high-entropy material chosen at advancement, so that two
  divergent restores from the same snapshot that both advance to the same
  counter still produce distinguishable epochs.

**Rules:**

- prepared or otherwise nonterminal work from a prior epoch can never become
  new authority;
- consumed authorization never reopens, in any epoch;
- accepted evidence from an old epoch may remain valid **historical**
  evidence;
- old-epoch evidence can never authorize a **new** admission under the new
  epoch.

**IMPLEMENTED today:** `authority_epoch` is static (D8). These semantics do
not exist yet.

### Recovery witness threat boundary

**PROPOSED, review correction 2.** Detecting a rollback requires a witness
that the rollback did not also roll back.

| Property | What it detects | Achievable by |
| --- | --- | --- |
| **LEDGER-ONLY RESTORE DETECTION** | the broker ledger or store was restored to an older state while the rest of the host survived | a root-owned or owner-signed local witness stored outside the broker ledger, on the same host |
| **WHOLE-HOST / WHOLE-DISK ROLLBACK DETECTION** | the entire host or disk, witness included, was restored to an older state | only an off-host or independently monotonic anchor |

- A same-host witness proves rollback detection **only when the witness itself
  survives**.
- B1b-3c may prove LEDGER-ONLY RESTORE DETECTION with a root-owned or
  owner-signed local witness.
- B1b-3c must **not** claim WHOLE-HOST / WHOLE-DISK ROLLBACK DETECTION.
- **Whole-host rollback detection is an unresolved later requirement.**

## OS and process boundary

**PROPOSED:**

- private authority-signing keys live outside `lilith` custody, readable only
  by the authority-domain service identity;
- the routine DEV deployer is denied read access to private keys and write
  access to the registry, the verifier, and the witness, extending B1c's
  per-deploy `DENIED` list;
- the public registry is readable by the application and not writable by it;
- application deployment cannot replace the registry, the registry-root trust
  anchor, or the verifier;
- the application reaches authority state only through a **read-only**
  app-facing query path;
- the mutating owner socket remains inaccessible to `lilith`;
- root remains out of scope (Level 3).

**Key storage mechanism:** systemd `LoadCredentialEncrypted` is **preferred**
if the DEV host supports it, with a protected root-owned file (service
identity only, no `lilith` access) as the fallback. It is **not** frozen as
mandatory by this record.

## Privacy custody — separate migration gate

**PROPOSED, review correction 3.** The following must eventually leave
application custody:

- Privacy authorization (erasure authorization issuance);
- the Privacy restore-selector PRF;
- Privacy DB custody.

This work is **not** merged into B1b-3a. It is the separate rehearsal
**B1b-3f**. Until B1b-3f passes, D2 and D4 remain open debt, and Privacy
custody is not complete.

## Relationship to Stage III A2

**CANONICAL:** the old Stage III A2 controller stopped at INTENT, is
deferred and unproven, and must not be retried. A1, A3, A4, and A5 remain
open. Stage III is **not** completed.

**PROPOSED, review correction 4.** The broker-signed sequence changes crash
semantics, so the old A2 path is **superseded** for future rehearsal:

| Point | Old meaning | Status under the proposed sequence |
| --- | --- | --- |
| A1 | challenge/request gap | may survive conceptually |
| A2 | proof consumed, before claim | may survive conceptually |
| A3 | claim, before evidence | obsolete if evidence is committed atomically with the claim |
| A4 | evidence, before link | obsolete as a separate split under atomic claim+evidence; replaced by A6 |
| A5 | committed result, lost response | may survive conceptually |
| A6 (new) | signed evidence durable, L04 admission not committed | new |
| A7 (new) | L04 admission committed and linked, acknowledgement to the authority domain or owner not delivered | new |

- The new points sit around **signed evidence → L04 admission →
  acknowledgement**.
- A future crash rehearsal must be **redesigned** once the B1b-3 contracts and
  signing semantics are fixed. It is a fresh A1–A7 design, not a retry.

## Proposed sub-slices

**PROPOSED** names; they remain proposed until this design is reviewed.

1. **15B2b-B1b-3a — Authority Evidence & Key Registry Contracts** (TEST-only).
2. **15B2b-B1b-3b — Broker-only signing + L04 V2 verification adapter**
   (TEST-only).
3. **15B2b-B1b-3c — Recovery epoch / registry witness semantics** (TEST
   first; LEDGER-ONLY restore detection only).
4. **15B2b-B1b-3d — DEV_SYNTHETIC custody install + OS denial proof.**
5. **15B2b-B1b-3e — Rotation / revocation / restore rehearsals.**
6. **15B2b-B1b-3f — Privacy authority + Privacy DB custody separation
   rehearsal.**
7. **Owner acceptance gate.**
8. Then: **fresh A1–A7 crash-model design and rehearsal.**

## First implementation slice

**PROPOSED: 15B2b-B1b-3a — Authority Evidence & Key Registry Contracts.**
TEST-only. It is not implemented or authorized by this record.

**Future scope:**

- `AuthorityKeyRecordV1`;
- the owner-signed registry contract;
- a separate synthetic registry signer (not the B1c activation key);
- `OwnerEvidenceV2`;
- `PrivacyAuthorizationV2`;
- domain-separated Ed25519 signatures;
- rotation, retirement, and compromise semantics;
- environment, domain, and epoch rules;
- cross-domain rejection;
- golden vectors;
- a full negative matrix.

**Explicitly excluded:**

- keys on disk;
- broker runtime changes;
- L04 runtime changes;
- any DEV contact;
- IAM;
- systemd;
- a real registry signer;
- real credentials;
- Privacy DB movement;
- Stage III.

**INFERRED placement:** like B2a, it should sit outside `services/core-api/**`
(whose changes trigger the PROD workflow) and outside
`services/memory-broker/` (whose file set is enforced by broker validation).

## Unresolved owner decisions

1. Production authority-registry root: custody and mechanism, and whether any
   operational reuse of an existing owner key is acceptable.
2. The off-host or independently monotonic anchor for whole-host rollback
   detection, and when it becomes required.
3. Trusted time and ordering evidence for re-attesting pre-compromise evidence.
4. Service-identity layout: the memory broker holds both domains, or a
   separate Privacy authority identity, or a dedicated authority service.
5. `LoadCredentialEncrypted` versus protected-file fallback on the DEV host.
6. Who may advance the recovery epoch, and whether advancement requires an
   owner signature.
7. Retention of retired public keys and registry versions.
8. Whether B1b-3 closes T-24 alone, or only together with B1d.
9. Ordering against `CROSS_ENVIRONMENT_PROD_AUTHORITY_DEBT` before any real
   owner authority.
10. Carried from 15B2b-B: RP domain, origins, authenticators, and the
    recovery/revocation ceremony.

## Explicitly not done

- No implementation of B1b-3a or any other sub-slice.
- No key created, installed, or rotated; no registry or signer created.
- No DEV or PROD mutation; no IAM, WIF, or systemd change.
- No Stage III retry.
- No real memory or authority created.
