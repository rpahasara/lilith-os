# Slice 15B2b-B1b-3e — Rotation, Revocation, Restore, and Recovery Semantics

Status:

- **DESIGN RECORD** (closure pass: every source-blocking decision resolved)
- **OWNER DECISIONS ACCEPTED:** C-1, C-4, RR-2, RR-3, RR-4, RR-5a
  (conditional), RR-10, RR-14, RR-15 (§17)
- **DESIGN READY FOR PR REVIEW** (§18). Source is not implemented, and no
  live rehearsal is authorized
- **NOT IMPLEMENTED**
- **NOT LIVE**
- **NO LIVE MUTATION AUTHORIZED**
- **WHOLE-HOST ROLLBACK UNRESOLVED**
- **REAL AUTHORITY ABSENT**

Base: protected main `069f6d1861b79d817f8b959e36b53f017bfbac32`.

This record defines the fifth sub-slice of the
[B1b-3 custody isolation design](slice-15b2b-b1b3-custody-isolation-design.md).
It follows the [B1b-3d live closure](slice-15b2b-b1b3d-live-closure.md) and
builds on three records:

- [B1b-3a](slice-15b2b-b1b3a-authority-registry-contracts.md): registry,
  key-record, and evidence contracts;
- [B1b-3c](slice-15b2b-b1b3c-recovery-epoch-witness.md): recovery epoch,
  witness, recovery ledger, and readiness;
- the [B1b-3d design](slice-15b2b-b1b3d-dev-synthetic-custody-design.md):
  DEV_SYNTHETIC custody, the witness service, the ceremony, and the ledger
  schema.

This is a design and source-review record only. It is not any of the
following:

- an acceptance record;
- an implementation authorization;
- a ceremony runbook;
- an activation instruction.

It does **not** mark any of these complete: B1b-3, Level 2 isolation, real
owner authority, First Memory, Privacy custody, or Stage III.

Nothing was contacted or changed in any of these:

- DEV, PROD, IAM, WIF, or systemd;
- any key, credential, registry, witness, ledger, or broker;
- Stage III.

No source, test, vector, workflow, contract, or earlier record was changed.

Labels:

| Label | Meaning |
| --- | --- |
| **CANONICAL** | defined by accepted records or by protected-main source |
| **IMPLEMENTED** | present in source (TEST), or in installed state |
| **LIVE** | installed on DEV, per the B1b-3d live closure |
| **PROPOSED** | recommended here; it still needs review and a separately authorized source slice |
| **OWNER-ACCEPTED** | an owner decision recorded for B1b-3e (§17). The accepted design property is binding for B1b-3e-S. The exact schemas stay follow-on source work |
| **SUPERSEDED FOR B1b-3e** | a part of an earlier design record that this record replaces for all future implementation. The earlier record is not edited |

## 1. Scope, the four stories, and the live baseline

B1b-3e defines four terms:

- **rotation:** an authority key is replaced by a successor;
- **revocation:** a key stops being usable for new evidence;
- **restore:** bytes come back from an older state;
- **recovery:** authority resumes after a restore or a fault.

Four separate stories are kept apart throughout this record. **None of them
may take over another's role.**

| # | Story | Question | Objects | Owner |
| --- | --- | --- | --- | --- |
| 1 | **Authority** | which keys, and which transitions, does the owner authorize? | the K-ROOT-signed `AuthorityRegistryV1`; the K-ROOT-signed `EpochAdvanceAuthorizationV1` (§9) and `RegistryHeadAdvanceAuthorizationV1` (§10.4) | the owner, offline, K-ROOT |
| 2 | **Freshness** | is this registry state the trusted current head, or is it stale, rolled back, or forked? | `RecoveryWitnessV1`, and the accepted `RecoveryWitnessV2` registry-head binding (§10) | the recovery witness |
| 3 | **Issuance readiness** | may this signer, with this loaded key, issue now? | `RESTORE_READY`; the independently verified loaded-key binding (§11.2); release of the local hold | the readiness gate + the independent verifier; hold release by host root on the owner's decision |
| 4 | **Storage / observation** | which bytes exist, and what did a component record or observe? | `REGISTRY_VIEW` and other journal records; ceremony hold files; installed registry files; credential blobs; read models; transcripts | the filesystem, root, credential custody, and the recovery-ledger writer |

Each story is limited to its own role:

- Story 2 never authorizes.
- Story 3 never authorizes and never refreshes.
- Story 4 is never authority, freshness, or readiness. It is only an input
  that stories 1–3 evaluate.

**Current live DEV state** (from the
[live closure](slice-15b2b-b1b3d-live-closure.md) §4 and §6):

| Artifact | Live? |
| --- | --- |
| K-ACT `test-only.dev-synthetic.actor.b1b3d.1` host-bound encrypted blob | **yes** (custody only) |
| `/var/lib/systemd/credential.secret` | yes |
| `lilith-authority-dev` account; release `9ac7de2…`; units (inactive, not enabled) | yes |
| `AuthorityRegistryV1`, `TrustedRegistryRootV1`, `/etc/lilith-authority-dev` | **no** |
| K-WIT, `lilith-recovery-witness`, any witness | **no** |
| `authority_ledger.db` | **no** |
| Activation | `NOT_ACCEPTED reason=GRANT_ABSENT` |

K-ACT is **not an authority key yet**. It is in no registry, and no witness or
recovery ledger exists. Replacing K-ACT today would be a custody change with
no authority effect.

Everything in this record becomes live only after B1b-3d L3a–L4 exist. None
of that is authorized.

## 2. Inherited and pinned invariants

Inherited unchanged:

```text
model proposal             != authority
execution                  != verification
memory                     != truth
storage                    != acceptance
deployment                 != activation
archive                    != active memory
runtime                    != identity
credential custody         != accepted authority
restore                    != authority restoration
historical preservation    != current authorization
```

Pinned by B1b-3e:

```text
rotation                          != silent replacement
prepared                          != active
registry publication              != activation
registry publication              != signer issuance readiness
registry publication              != witness execution authorization
credential exists                 != accepted authority
credential loaded                 != current authority

owner request                     != authorization
authorization                     != execution
execution                         != verification
signed authorization              != executed transition

witness freshness                 != authority grant
witness freshness                 != key activation
witness floor                     != key activation
witness head binding              != registry authority
witness receipt                   != independent verification

REGISTRY_VIEW                     != authority
REGISTRY_VIEW                     != registry-root authorization
REGISTRY_VIEW                     != witness execution

hold file                         != owner request
root custody                      != owner authorization

signer claim                      != verification
S_ACTIVATED                       != S_CURRENT

ledger evidence                   != registry authority
historical interval cutoff        != current issuance authority
evidence.issuedAt                 != authority cutover

signed registry                   != effective current registry head
registry existence                != head-advance permission
K-ROOT authorization              != witness execution
witness execution                 != independent verification
registry-head advance             != key issuance readiness
```

Two B1b-3c rules are inherited unchanged:

1. **Removing authority never needs readiness; creating it always does.**
2. **Recovery can only destroy pending authority, never create any.**

The ledger rules are also inherited (§12): **PREPARED may be voided.
CONSUMED never reopens.**

## 3. Existing contracts reused

| Contract / mechanism | Source | Role in B1b-3e | Story |
| --- | --- | --- | --- |
| `AuthorityKeyRecordV1`, exact current fields in §7.2 | `authority_contracts.py` | the only representation of a key's lifecycle | 1 |
| `AuthorityRegistryV1`, `TrustedRegistryRootV1` | `authority_contracts.py` | the authoritative registry state | 1 |
| `verify_authority_registry`, `verify_owner_evidence` (44-reason taxonomy) | `authority_verifier.py` | forward rejection and historical verification | 1 + 2 |
| `RecoveryEpochV1 {counter, random}`, `epoch_digest`, `compare_epochs`, `ledger_epoch_id` | `authority_contracts.py`, `recovery_contracts.py` | epoch identity, ordering, and forks | 2 |
| `RecoveryWitnessV1`, `TrustedWitnessAnchorV1`, `witness_succession_reason` | `recovery_contracts.py` | the freshness state. V1 is unchanged; V2 is accepted (§10) | 2 |
| `witness_authority_context` | `recovery_contracts.py` | combines story 1 (root anchor) with story 2 (freshness inputs), taken "from the verified witness and nowhere else" | 1 + 2 |
| `AuthorityLedgerStateV1` ("authority-side recovery ledger model") and its journal ops | `synthetic_recovery_ledger.py` | the recovery ledger's state machine (§12) | 4, evaluated by 3 |
| `begin_recovery`, `quarantine_pre_recovery`, `RECOVERY_REASONS` | `synthetic_recovery_ledger.py` | the governing epoch-advance steps (C-4) | 4 |
| `evaluate_restore_readiness` | `synthetic_recovery_ledger.py` | the gate on every authority-creating operation | 3 |
| `RecoveryEpochTransitionV1` | `synthetic_recovery_ledger.py` | the acknowledgement after an advance; a record | 4 |
| `RecoveryBoundAdmissionGateV1`, `verify_historical_accepted_memory` | `recovery_admission.py` | new admission vs history | 1 + 2 + 3 |
| Signer `HEALTH` `publicKeySha256`; the keygen publication `{publicKey, publicKeySha256, blobSha256}` | B1b-3d L1 service; L2 §7 and U5 | inputs to the loaded-key binding (§11.2) | 4, evaluated by 3 |
| Witness owner ops, ceremony hold, verifier CLI | B1b-3d design §10, §11, §13 | execution and verification boundaries, designed only. C-4 applies | 2 / 3 / 4 |
| DEV_SYNTHETIC no-backup policy | B1b-3d design §16 | credential restore | 4 |

## 4. State owners and ledger names

"The ledger" is never used without qualification in this record. There are
three distinct ledgers.

| Name used here | Physical | Owner (sole writer) | Contents | Role |
| --- | --- | --- | --- | --- |
| **Authority recovery ledger** | `/var/lib/lilith-authority-dev/authority_ledger.db` (B1b-3d §12; not provisioned) | `lilith-authority-dev`, the authority signer boundary | the hash-chained journal plus `authority_challenge_v2`, `authority_evidence_v2`, `authority_evidence_use_v1`, and `authority_epoch_v1`. It is the durable form of `AuthorityLedgerStateV1` | the only ledger any B1b-3e operation mutates. It is authoritative over its own rows |
| **Legacy memory-broker ledgers** | `/var/lib/lilith-memory-broker/…/owner_control.db`, `synthetic_evidence.db` | `lilith-memory-broker` | B1b-1/B1b-2 synthetic challenge and evidence rows. Pinned Stage II evidence. `authority_epoch` is retired as non-authoritative (T-12) | **never** read or mutated by B1b-3e. The signer unit has them in `InaccessiblePaths` (B1b-3d §9) |
| **Application / L04 databases** | application-owned | `lilith` / the application | L04 rows, admission links | never consulted by readiness (B1b-3c §14) |

**A terminology note.** The B1b-3b and B1b-3c records and module docstrings
use "broker challenge ledger" and "evidence-use ledger" for the
**authority-side** role, the "broker / authority signer". The B1b-3d design
(§6) assigns that role to the new `lilith-authority-dev` identity, **not** to
`lilith-memory-broker`. In B1b-3e those B1b-3b/3c terms mean the tables of
the **authority recovery ledger**.

The signer therefore gains **no** mutation authority over any ledger it does
not already solely own.

### State owners

| State | Story | Owner | Is authority? |
| --- | --- | --- | --- |
| Owner transition request (intent) | 4 | the owner (a person); recorded in the workstation transcript; unauthenticated (RR-13) | no |
| Ceremony hold file | 4 | host root | no: gating only |
| Authority registry generations | 1 | the owner, offline, K-ROOT | **yes** |
| `EpochAdvanceAuthorizationV1` | 1 | the owner, offline, K-ROOT | **yes**, for exactly one epoch transition |
| `RegistryHeadAdvanceAuthorizationV1` | 1 | the owner, offline, K-ROOT | **yes**, for exactly one in-epoch head advance |
| Staged / abandoned registry (signed, never executed as head) | 4 | host root (bytes) | no: it can never become the head without an executed authorization |
| Freshness: epoch, floor, head, ledger position | 2 | the recovery witness | no |
| Served registry file / pointer | 4 | host root | no |
| Authority recovery ledger | 4 (evaluated by 3) | `lilith-authority-dev` | no |
| Private key material | 4 | root credential store + systemd | no |
| Readiness result, loaded-key binding result, transition records | 3 | the independent verifier (stateless) | no |

**Infrastructure depth is proportional to cognitive relevance.** B1b-3e adds
no service, identity, socket, replica, daemon, scheduler, or off-host
component.

The only thing it adds to the witness is a registry-head binding (V2). That
lives inside the existing freshness boundary and uses the existing K-WIT
key.

## 5. Timestamp and interval semantics (CANONICAL, from source)

| Field | Record constraint | Verification effect |
| --- | --- | --- |
| `createdAt` | `notBefore ≥ createdAt`; `revokedAt ≥ createdAt`; `≤ registry.issuedAt` | ordering only |
| `notBefore` | `≥ createdAt`; **not** bounded by `registry.issuedAt` | `issuedAt < notBefore` → `KEY_NOT_YET_VALID` |
| `retiredAt` | `≥ notBefore`; `≤ registry.issuedAt` | `issuedAt ≥ retiredAt` → `KEY_RETIRED`, both purposes |
| `revokedAt` + `revocationReason` | set together; `≥ createdAt`; `≤ registry.issuedAt` | ROUTINE or SUPERSEDED: `issuedAt ≥ revokedAt` → `KEY_REVOKED`, both purposes. **The two are verification-identical**: `compromised` is `revocationReason == COMPROMISED` only |
| `compromisedSince` | set **if and only if** `COMPROMISED`; `≤ revokedAt` | not consulted. All of the key's evidence → `KEY_COMPROMISED` (C-1) |
| evidence `issuedAt` | signer-controlled | the evidence's only time. Untrustworthy after key exposure |
| `signedAt`, accepted-at | **do not exist** | — |
| key "current" | `retiredAt == null and revokedAt == null` | registry invariant: current keys are in the registry's epoch and policy |

The only trusted ordering of authority events is the **authority recovery
ledger** journal sequence, anchored by the witness's
`ledgerSequence`/`ledgerHead`. It is ledger-only and holds only while the
witness survives. No trusted wall-clock acceptance time exists.

## 6. Revocation semantics

### 6.1 Four transitions and their use (RR-10, OWNER-ACCEPTED)

| Transition | Record expression | Used for | Evidence already issued |
| --- | --- | --- | --- |
| **Supersession** | `revokedAt = t_cut`, `SUPERSEDED` | **ordinary predecessor → successor rotation** (accepted) | valid if `notBefore ≤ issuedAt < t_cut` (`REVOKED_AFTER_ISSUANCE`) |
| **Routine revocation** | `revokedAt = t`, `ROUTINE` | **administrative end of use that does not express successor replacement** (accepted): decommissioned, lost without exposure, published but never activated | valid if `issuedAt < t` |
| **Retirement** | `retiredAt = t` (no reason field) | the existing B1b-3c recovery ceremony ("every current E1 key is retired at the recovery instant"). This is unchanged; see RR-10a | valid if `issuedAt < t` (`RETIRED_AFTER_ISSUANCE`) |
| **Compromise** | `revokedAt = t`, `COMPROMISED`, `compromisedSince ≤ t` | private material may be outside custody | **all rejected**, `KEY_COMPROMISED` |

`ROUTINE` and `SUPERSEDED` verify identically in current source. The
distinction is recorded meaning only, and the verifier is unchanged.

**No successor-link field exists** in `AuthorityKeyRecordV1`, and none is
invented. The predecessor → successor link is carried by
`AuthorityKeyTransitionV1` (§7.7) and by the registry generation that holds
both records.

### 6.2 Historical-validity invariant

> Evidence valid under the registry/key state applicable to its issuance is
> not retroactively invalidated merely because its key is later retired,
> routinely revoked, or superseded.

This holds in source, pinned by the B1b-3a golden vectors "retirement accepted
as history" and "in-flight evidence surviving a registry update". It holds
only while every later registry keeps the record unchanged: a removed record
gives `KEY_UNKNOWN`, and a rewritten one gives an epoch or policy mismatch.
§10 enforces this.

### 6.3 Compromise: decision C-1 (OWNER-ACCEPTED)

The current B1b-3a source semantics are accepted. The verifier docstring says:

> compromise is retroactive: every piece of evidence the key signed is
> rejected, whatever its signer-controlled `issuedAt`, because
> re-attestation does not exist yet;

What follows from it:

- `COMPROMISED` → `KEY_COMPROMISED` for **all** evidence from the key. This
  includes evidence that claims `issuedAt < compromisedSince`.
- **Why.** `issuedAt` is signer-controlled. A key thief can backdate newly
  forged evidence. `compromisedSince` is forensic only.
- **Unchanged.** Routine retirement and non-compromise revocation keep their
  interval rules.
- **Deferred.** Pre-compromise survival needs an independent timestamp, an
  admission-time attestation, or a re-attestation contract that the key
  cannot forge. B1b-3a source is unchanged.

**Friction (RR-8).** `compromisedSince ≤ revokedAt` means that a compromise
found after a `ROUTINE` or `SUPERSEDED` revocation must be recorded with a
`compromisedSince` that is knowingly imprecise. The verdict is the same.

### 6.4 Forward rejection and stale registries

- **Verifier.** After revocation or retirement at `t`, evidence with
  `issuedAt ≥ t` is refused for both purposes.
- **Authority recovery ledger + readiness (story 3).** Readiness requires
  every journalled signing key to be current and uncompromised in the
  **fresh, K-ROOT-verified** registry (`REQUIRED_KEY_UNAVAILABLE`). It also
  requires the journal's observed view to equal that registry
  (`BROKER_REGISTRY_VIEW_STALE`).
- **Protection against backdating.**
  - For NEW_ADMISSION, `RESERVE` requires an `ISSUE` record in the authority
    recovery ledger (`EVIDENCE_NOT_ISSUED_HERE`).
  - For history, the full acceptance chain applies.
- **Stale registry.** A registry below freshness → `REGISTRY_DOWNGRADE`,
  which blocks issuance **and** historical reads. With V2, a registry off the
  witnessed head is refused as well (§10).
- **No "delete the bad key from history".** A compromised key is marked,
  never removed.

## 7. Rotation

### 7.1 Two kinds

| Kind | Epoch | In-flight owner proofs | Authorized by |
| --- | --- | --- | --- |
| **In-epoch rotation** | unchanged | **preserved** for predecessor evidence already `ISSUE`d in the authority recovery ledger inside the predecessor's interval | K-ROOT registry generation vN+1 **and** `RegistryHeadAdvanceAuthorizationV1` (vN → vN+1) (§10.4) |
| **Epoch-advance rotation** | `counter + 1` | **burned by design**: PREPARED voided, RESERVED quarantined | K-ROOT registry at the new epoch **and** `EpochAdvanceAuthorizationV1` (§9) |

### 7.2 Single-current-key scope (RR-3, OWNER-ACCEPTED)

**Field truth in current source.** At protected main `069f6d1`,
`authority_contracts.py` has:

```text
KEY_RECORD_FIELDS = {
  schemaVersion, keyId, signingDomain, evidenceTypes, environment,
  algorithm, publicKey, createdAt, notBefore, retiredAt, revokedAt,
  revocationReason, compromisedSince, recoveryEpoch, policyVersion,
  registryVersion }
SIGNING_DOMAINS = { OWNER_ACTOR, PRIVACY }
EVIDENCE_TYPES_BY_DOMAIN = { OWNER_ACTOR: {OWNER_MEMORY_OPERATION},
                             PRIVACY:     {PRIVACY_ERASURE_AUTHORIZATION} }
```

- **The key record's cryptographic authority domain field is `signingDomain`.**
  `AuthorityKeyRecordV1` has **no** `authorityDomain` field. Its docstring
  says the "record carries no logical `authorityDomain`".
- `authorityDomain` exists only on `OwnerEvidenceV2` and
  `PrivacyAuthorizationV2`, as the **logical** context with its B2a meaning.
  Signing-domain names are rejected there.
- **History.** The first B1b-3a commit `a26be42` named this key-record field
  `authorityDomain`, and the earlier B1b-3 design table did too. Commit
  `cd92d08` ("Separate signing domain from logical authority domain")
  renamed it to `signingDomain`.
- **Current state.** The current B1b-3a record (Contracts, "Two different
  domain fields") and the golden `fieldSemantics` both freeze the current
  meaning. Any description of the key record as carrying
  `authorityDomain = OWNER_ACTOR | PRIVACY` reflects the pre-`cd92d08` shape,
  not current source.
- **Not the same field.** The L2 keygen publication's
  `publicVerificationMaterial.signingDomain` is a separate custody
  publication. It is not the registry contract, and this rule does not rely
  on it.

No alias is created.

**Accepted invariant:**

> At most one current issuance key per
> `(environment, recoveryEpoch, signingDomain, evidenceType)`.

A verified registry fixes `environment` and `recoveryEpoch` (registry
invariants). So the rule, local to a registry, is:

> in one verified registry, for each `(signingDomain, evidenceType)`, at most
> one current key whose `evidenceTypes` contains `evidenceType`.

- **Why `evidenceType` is part of the scope.** The verifier accepts a key when
  its `signingDomain` matches **and** `evidenceType ∈ key.evidenceTypes`.
  Today each domain has exactly one type, so this equals one key per
  `signingDomain`. Stating it per type keeps it correct if a domain gains a
  type. A multi-type key counts toward each type it lists.
- **DEV_SYNTHETIC profile.** Exactly one current key for
  `(OWNER_ACTOR, OWNER_MEMORY_OPERATION)`. None for
  `(PRIVACY, PRIVACY_ERASURE_AUTHORIZATION)`, because B1b-3f has not started.
- **Enforcement.** A publication-time profile check in
  `verify_registry_succession` (§10.1) and in the verifier CLI. The B1b-3a
  verifier is unchanged and still structurally accepts several current keys.

### 7.3 Cut-over: version and state, not time (RR-10, OWNER-ACCEPTED)

**Current issuance cut-over** (story 3) is state and version based, not
wall-clock based. Issuance moves from P to S only when all of these hold:

1. K-ROOT registry generation vN+1 names S as the single current key in scope,
   and P as `SUPERSEDED` (story 1);
2. the witness head is vN+1 (story 2);
3. the independent verifier has confirmed readiness and the loaded-key
   binding, and the hold is released (story 3; `S_CURRENT`).

No signer-controlled time takes part.

**Historical interval cut-off.** `t_cut` is the value of P's `revokedAt` and
S's `notBefore` in vN+1.

| Aspect | Answer |
| --- | --- |
| Authoritative owner | **the K-ROOT-signed lifecycle state in the registry** (`revokedAt` / `notBefore`). The owner chooses it when signing |
| Used for | historical interval verification only: which P evidence lies in `[notBefore, revokedAt)` |
| Not used for | current issuance authority, readiness, or ordering |
| Role of recovery-ledger `ISSUE` records | **evidence the owner may use** to choose a safe value. For example, take a value above the maximum `issuedAt` of P evidence recorded by `ISSUE` in the witness-consistent authority recovery ledger, read by the verifier. **They neither own nor authorize `t_cut`.** `ledger evidence != registry authority` |
| Constraint | `t_cut ≤ vN+1.issuedAt` (contract). Chosen while the hold is in force and the signer is stopped |

```text
historical interval cutoff (registry lifecycle fields)  !=  current issuance authority (state/version)
```

### 7.4 State machine

```text
 P_ACTIVE ─(1)▶ S_PROPOSED ─(2)▶ S_PREPARED ─(3)▶ S_AUTHORIZED ─(4)▶ S_PUBLISHED ─(5)▶ S_ACTIVATED ─(6)▶ S_CURRENT
                                                                                                        (P_SUPERSEDED)
```

| # | Transition | Caused by | Story | Postcondition | Explicitly not implied |
| --- | --- | --- | --- | --- | --- |
| 1 | P_ACTIVE → S_PROPOSED | the owner decides (unauthenticated intent, RR-13). Host root writes the ceremony hold | 4 | the signer refuses creating ops. P is current, not issuing | no authority change. `hold file != owner request` |
| 2 | → S_PREPARED | credential custody (host root runs the successor-keygen CLI, RR-11) | 4 | the S blob sits in a slot **distinct from** the unit's. The publication `{publicKey, publicKeySha256, blobSha256}` is recorded | **S cannot sign accepted authority**: it is in no registry (`KEY_UNKNOWN`), not loadable, and not journalled |
| 3 | → S_AUTHORIZED | the owner, offline, with K-ROOT, signs **both** of the following. **(A) Successor / key authorization:** the candidate registry vN+1 names S current (`notBefore = t_cut`) and P `revokedAt = t_cut`, `SUPERSEDED`, and satisfies §7.2 and `verify_registry_succession(vN → vN+1)`. **(B) Head-advance execution authorization:** a `RegistryHeadAdvanceAuthorizationV1` from the exact prior head `(vN, digest_N)` to the exact candidate `(vN+1, digest_N+1)` in the current epoch (§10.4). If only (A) exists, vN+1 is a **staged candidate**, still in `S_PREPARED` for head purposes | 1 | the candidate authority state exists, and permission to execute exactly one head advance to it exists | **not** witness execution or freshness. The head is still vN. Nothing issues. `signed registry != effective current registry head`; `registry existence != head-advance permission` |
| 4 | → S_PUBLISHED | the recovery witness (V2) **executes** the `RegistryHeadAdvanceAuthorizationV1` on host-root request, after the §10.4 checks. Host root then serves vN+1 | 2 | the witness head is `(vN+1, digest_N+1)`, and the authorization ID is recorded as consumed. vN is stale | **not** an authority grant: authority came from step 3. **Not** key activation. **Not** issuance readiness: the recovery ledger's view is still vN → `BROKER_REGISTRY_VIEW_STALE` / `REQUIRED_KEY_UNAVAILABLE`. `K-ROOT authorization != witness execution`; `registry-head advance != key issuance readiness` |
| 5 | → S_ACTIVATED | credential custody moves S into the unit slot and destroys P's blob. The signer starts under the hold, reports `HEALTH` `publicKeySha256`, and journals `REGISTRY_VIEW{vN+1,[S]}` (an observation). The witness records the recovery-ledger advance | 4 | **one meaning:** *S's credential is loaded in the unit slot, and the signer has recorded its observation of the fresh head. Nothing about this is verified yet.* The hold stays | no authority, and no permission to issue. `credential loaded != current authority`; `signer claim != verification` |
| 6 | → S_CURRENT | the independent verifier reproduces readiness **and** the loaded-key binding (§11.2), then emits `AuthorityKeyTransitionV1`. Host root releases the hold on the owner's decision | 3 | issuance is permitted, still gated by readiness per operation | **no dual-current issuance**: one current key in scope, one unit slot, one journalled key, and a binding verified equal to that key |
| — | P → P_SUPERSEDED | authority: K-ROOT (step 3). Freshness: effective at step 4. Custody: material destroyed at step 5 | 1 / 2 / 4 | P evidence in `[notBefore, t_cut)` stays valid | P is never current again (§10.1; vN is stale) |

**`S_CURRENT` requires all of these:**

- a valid K-ROOT registry vN+1;
- a fresh `RecoveryWitnessV2` whose head is exactly `(vN+1, digest_N+1)`,
  reached by an executed `RegistryHeadAdvanceAuthorizationV1`;
- the loaded-key binding (§11.2);
- independent verification;
- the local hold released.

`S_ACTIVATED` and `S_CURRENT` are **not redundant**. They differ by exactly
`execution != verification` plus the release of the hold:

- `S_ACTIVATED` is the signer's own claim.
- `S_CURRENT` is independently verified.

Only `S_CURRENT` permits issuance.

### 7.5 What "current" means

| Sense | Established by | Story |
| --- | --- | --- |
| Authorized | the K-ROOT registry generation (step 3) | 1 |
| Fresh | the witness head (step 4). Freshness of the registry state, not authority over a key | 2 |
| Current for verification | a verification **result** combining 1 and 2 | 1 + 2 |
| Issuance-ready | independently verified readiness + loaded-key binding + hold release (step 6) | 3 |

### 7.6 Rotation crash handling

| Point | State | Authority change | Allowed action |
| --- | --- | --- | --- |
| before successor preparation | `S_PROPOSED` | none | release the hold, or continue |
| keygen done; authorization never comes | `S_PREPARED` | none | destroy the successor blob (it has no history) |
| vN+1 signed; no head-advance authorization | `S_PREPARED` + staged candidate | none: a staged candidate can never become the head | sign (B) later, or abandon: the bytes stay story-4 history |
| vN+1 and (B) signed; not executed | `S_AUTHORIZED` | none until executed | execute later, or abandon. (B) stays executable until `notAfter`, or until the head moves away from its bound prior head. Executing it yields only K-ROOT-authorized content. **Owner rule:** do not sign a competing (B) from the same prior head until the earlier one has expired. Otherwise whichever executes first wins, and the other becomes unusable (its prior-head binding fails) |
| head advanced; not activated | `S_PUBLISHED` | none further | forward only. If S's blob is lost: vN+2 revokes S `ROUTINE` (zero S evidence proven) and names S′ |
| `REGISTRY_VIEW` journalled; ledger advance not witnessed | `LEDGER_AHEAD_OF_WITNESS` | none | fail closed. Resolved only by an epoch advance (B1b-3c/3d) |
| verifier not ready, or binding mismatch | `S_ACTIVATED` | none | the hold stays; diagnose |

### 7.7 `AuthorityKeyTransitionV1` (PROPOSED record, story 4)

The verifier emits it at step 6. Its fields:

- `schemaVersion`, `kind`, `environment`;
- `signingDomain`, `evidenceType`;
- `predecessorKeyId`, `successorKeyId`, `predecessorRevocationReason: SUPERSEDED`;
- `fromRegistry {version, digest}`, `toRegistry {version, digest}`;
- `recoveryEpoch`;
- `witnessDigestBefore`, `witnessDigestAfter`;
- `authorityRecoveryLedgerSequence`;
- `tCut` (`historicalIntervalOnly: true`);
- `loadedKeyBinding` (§11.2 result);
- `predecessorIssuedEvidenceCount`;
- `inFlightEvidencePreserved: true`, `historicalEvidenceRetained: true`;
- `predecessorMaterialDestroyedFromActiveCustody` (§8.4);
- `rollbackDetectionScope: LEDGER_ONLY`, `wholeHostRollbackProtected: false`.

## 8. Restore semantics

```text
RESTORE != AUTHORITY RESTORATION
```

Authority exists only in K-ROOT-signed objects (story 1) that current
freshness accepts (story 2). Issuance exists only after story 3.

Restored bytes are story 4. They may be **adopted as state** only when the
surviving freshness owner attests exactly those bytes, and even then they
gain no authority.

### 8.1 Five kinds of restore

| Kind | Bytes | Can | Can never |
| --- | --- | --- | --- |
| **Data restore** | application / L04 DBs, memory files | serve as history under the acceptance chain | be consulted by readiness; revive or block authority |
| **Signer-state restore** | the authority recovery ledger | be adopted only if its journal equals the witnessed `sequence/head` | reopen a terminal row (`TERMINAL_STATE_REOPENED`); revive PREPARED after an advance (`LEDGER_EPOCH_STALE`); issue while behind the witness; turn a restored `REGISTRY_VIEW` into authority |
| **Registry restore** | an older signed registry | nothing below or off the witnessed head. Reinstating the retained current head bytes is harmless | lift a revocation, retirement, or compromise; restore a deleted record |
| **Credential restore** | an older `.cred` blob | nothing. Backup and restore are forbidden in DEV_SYNTHETIC | pass the loaded-key binding (§11.2) |
| **Authority restoration** | — | only through §9 | be performed by any restore of bytes |

The legacy memory-broker ledgers are outside all five rows. Restoring them
has no B1b-3e authority meaning.

### 8.2 Specific restore cases

| Case | Detected as | Outcome |
| --- | --- | --- |
| old snapshot's K-ACT blob extracted onto the current host | slot blob hash ≠ current key publication, or binding mismatch → `REQUIRED_KEY_UNAVAILABLE` | no issuance. The material is exposed again (§8.4, RR-7) |
| whole VM boots from an old snapshot | **not detected** | **unresolved** |
| registry rolls back; witness current | `REGISTRY_DOWNGRADE` (V2: off-head) | blocked; reinstate the current head bytes |
| authority recovery ledger rolls back; witness current | `LEDGER_BEHIND_WITNESS` / `LEDGER_EPOCH_STALE` / `LEDGER_HEAD_MISMATCH` | issuance blocked; history allowed. Reinstate a witnessed ledger, or advance the epoch |
| registry + recovery ledger roll back; witness newer | `REGISTRY_DOWNGRADE`, then `LEDGER_BEHIND_WITNESS` | reinstate the head, then advance the epoch from the witness |
| registry + recovery ledger roll back to a same-version fork; witness newer | V1: **not detected**. V2: head-digest mismatch | §10.3 |
| witness rolls back alone | `LEDGER_AHEAD_OF_WITNESS` | blocked (history too); advance the epoch; RR-9 |
| witness + registry + recovery ledger roll back together | not detected | **unresolved** |

### 8.3 Stale owner proof

- A restored `PREPARED` flag over a `CONSUMED` journal entry →
  `TERMINAL_STATE_REOPENED`.
- Pre-advance `PREPARED` challenges are voided.
- Old-epoch assertions and evidence can never be consumed, signed, or
  reserved (`STALE_EPOCH_*`).

### 8.4 Host-bound credentials and snapshots

Host-bound systemd credentials do not solve snapshot rollback (live closure
§11). Any post-L2b.2 disk snapshot holds both the K-ACT blob and
`credential.secret`. No live contact was made, so whether such snapshots
exist is unknown.

`predecessorMaterialDestroyedFromActiveCustody` means destruction from the
live credential store only.

RR-7 is still an open owner decision. The proposal: material retained inside
the owner/root boundary counts as known debt; material outside it counts as
compromise.

## 9. Recovery-epoch advancement protocol (RR-2, OWNER-ACCEPTED)

```text
Owner Request ─▶ Registry-root Authorize ─▶ Recovery Witness Execute ─▶ Independent Verify
 (intent, S4)    (EpochAdvanceAuthorizationV1   (freshness transition, S2)   (readiness + binding, S3)
                  + registry at new epoch, S1)
```

### 9.1 Objects

| Boundary | Object | Story | Is authority? |
| --- | --- | --- | --- |
| Owner request | unauthenticated local intent for DEV_SYNTHETIC. It is recorded in the owner transcript and may be mirrored in `CeremonyHoldV1` (RR-13) | 4 | **no**. `owner request != authorization` |
| Ceremony hold | `CeremonyHoldV1` (PROPOSED gating container) `{kind, reason, environment, observedWitnessDigest, observedRegistryVersion, createdAt}`. Every field is unauthenticated | 4 | **no**. It only blocks creating ops (fails safe). `hold file != owner request`; `root custody != owner authorization` |
| Registry state at the new epoch | a K-ROOT-signed `AuthorityRegistryV1` at `(counter + 1, fresh random)`: `registryVersion = head + 1` (contiguous); every E(n) key non-current; §7.2 holds; succession holds | 1 | **yes**: the authoritative registry state. It is **not** permission to execute the advance: `registry publication != witness execution authorization` |
| **Execution authorization** | **`EpochAdvanceAuthorizationV1`**, signed by K-ROOT (§9.2) | 1 | **yes**: the first authority-bearing *transition* object, and usable for exactly one transition. `authorization != execution` |
| Recovery-ledger adoption record | the authority recovery ledger's `ADVANCE_EPOCH` journal op, written by the signer before the witness executes (§9.4, RR-5a) | 4 | **no**: destroy/narrow-only |
| Witness execution | witness `ADVANCE_EPOCH` → successor witness (V2) plus a chain entry | 2 | **no**: it executes the authorized freshness transition. The signed witness is a receipt |
| Resulting epoch | `witness.currentRecoveryEpoch`; `ledgerEpoch = "lep1." + epoch_digest(…)` | 2 | no |
| Verification | the independent verifier: `RESTORE_READY` + loaded-key binding + `RecoveryEpochTransitionV1` | 3 | no. `execution != verification` |

No new service is created: K-ROOT stays the only authorizer, the witness the
only executor, and the verifier the only verifier.

**Relationship to RR-15.** `EpochAdvanceAuthorizationV1` and
`RegistryHeadAdvanceAuthorizationV1` (§10.4) are **distinct contracts**,
with distinct separators and distinct semantics:

- `EpochAdvanceAuthorizationV1` authorizes changing `RecoveryEpochV1` and the
  associated recovery state. The registry head changes with it, to the
  target it binds.
- `RegistryHeadAdvanceAuthorizationV1` authorizes changing **only** the
  registry head, inside the current epoch.

Neither is valid in place of the other. Implementation helpers may later be
shared. **No generic optional-field "transition authorization" envelope is
introduced.**

### 9.2 `EpochAdvanceAuthorizationV1` (PROPOSED contract; accepted property)

The design shape follows. The exact schema, vectors, and reason names belong
to B1b-3e-S.

**Signing.** Ed25519 with K-ROOT over
`"LILITH_EPOCH_ADVANCE_AUTHORIZATION_V1\x00" ‖ JCS(all fields except
signature)`. It is verified with the pinned `TrustedRegistryRootV1`.

The separator must be distinct from every existing separator: the B1a, B2a,
and B1b-3a separators, and B1b-3c's `LILITH_RECOVERY_WITNESS_V1` and
`LILITH_RECOVERY_EPOCH_V1`. B1b-3e-S must add a pinning test for this. So a registry
signature and an authorization signature can never be confused, even though
K-ROOT now signs two artifact types. The `test-only.` root prefix rule still
applies.

| Field | Binds |
| --- | --- |
| `protocol`, `schemaVersion` | `LILITH_EPOCH_ADVANCE_AUTHORIZATION`, `1` |
| `authorizationId` | a unique ID with ≥ 128-bit random nonce material; recorded by the witness on execution |
| `environment` | exactly one environment |
| `reason` | one of `RECOVERY_REASONS` |
| `priorRecoveryEpoch` | `RecoveryEpochV1`; must equal the witness's current epoch |
| `successorRecoveryEpoch` | `RecoveryEpochV1`; `counter = prior.counter + 1`; `random` fresh and never seen in the chain |
| `targetRegistryVersion`, `targetRegistryDigest` | the exact registry generation at the successor epoch; `version = witness head version + 1` |
| `expectedPriorWitnessDigest` (+ `expectedPriorWitnessVersion`) | the exact witness state the transition starts from |
| `registryRootKeyId` | the signing root |
| `issuedAt`, `notAfter` | a validity window (see the limit below) |
| `signature` | K-ROOT |

**Witness execution checks** (all must hold; any failure → refuse, no state
change):

1. the signature verifies under the pinned root;
2. the environment matches;
3. the current witness digest and version equal the expected values;
4. `priorRecoveryEpoch == current epoch`;
5. the successor epoch is a valid successor (counter `+1`, fresh random,
   `compare_epochs` `NEWER`);
6. the supplied registry verifies under K-ROOT at `successorRecoveryEpoch`;
   its digest equals `targetRegistryDigest`; its version equals
   `targetRegistryVersion` = head + 1; `verify_registry_succession(head →
   target)` passes;
7. the authority recovery ledger's journalled `ADVANCE_EPOCH` names the same
   `authorizationId` and successor epoch (C-4 order);
8. `authorizationId` does not appear in the witness chain;
9. the witness's `updatedAt ≤ notAfter`.

**Replay safety.** The authorization is usable only for the exact
transition:

- it binds the prior witness digest, and the chain is linear, so after
  execution the witness can never again be at that digest;
- the chain records `authorizationId`;
- it binds the exact target registry digest and successor epoch.

**Honest limits:**

- A witness restored alone to the prior digest could meet a replayed
  authorization. The recovery ledger, which is ahead, then shows
  `LEDGER_AHEAD_OF_WITNESS` / `LEDGER_EPOCH_AHEAD_OF_WITNESS`, and the
  result is fail-closed.
- A whole-host rollback that includes the witness is **not** protected.
- **Expiry** uses the host clock through the witness's monotonic `updatedAt`.
  It is defence in depth, not a security boundary:
  - a fast clock can only cause refusal;
  - a slow clock can only extend a window that the prior-witness binding
    already limits.
- The contract's `_instant` timestamps support this safely.

### 9.3 Decision C-4: ordering (OWNER-ACCEPTED)

**The B1b-3c source succession semantics govern.** The governing order for
future implementation is:

1. The owner writes the hold. K-ROOT has signed the registry at the new epoch
   and `EpochAdvanceAuthorizationV1`.
2. **Recovery-ledger adoption (pre-witness).** The signer journals
   `ADVANCE_EPOCH` in the authority recovery ledger. This is `begin_recovery`,
   with the new epoch taken from the **pre-advance** witness, plus
   `fromWitnessDigest` and, proposed, `authorizationId`.
3. **Witness execution** of the authorization, binding the **post-journal**
   `ledgerSequence/ledgerHead`. This is the point of no return.
4. Quarantine (`VOID_CHALLENGE`, `QUARANTINE_USE`), then the witness records
   the recovery-ledger advance.
5. Credential swap. The independent verifier confirms readiness and the
   loaded-key binding. The hold is released.

**SUPERSEDED FOR B1b-3e:** the B1b-3d design §13 steps 7 and 9, and the §10
`ADVANCE_EPOCH {…restoredLedgerSequence, restoredLedgerHead…}` operation
shape. They put the witness first, with the restored sequence and head. The
implemented B1b-3c checks would refuse that:

- `WITNESS_LEDGER_REGRESSION` for an unrestored ledger;
- `counter + 2` from a post-advance `begin_recovery`.

The B1b-3d record is not edited. **No live epoch advance is authorized.**

### 9.4 Pre-witness `ADVANCE_EPOCH`: who and what (RR-5a, OWNER-ACCEPTED conditionally)

- **Ledger.** The **authority recovery ledger**
  (`/var/lib/lilith-authority-dev/authority_ledger.db`, the durable
  `AuthorityLedgerStateV1`). Its sole writer is `lilith-authority-dev`, the
  authority signer boundary.
- **The acceptance condition is met.** This is the ledger the signer already
  solely owns for every challenge, issue, reserve, and confirm operation
  (B1b-3d §12). Performing recovery gives the signer **no new** mutation
  authority.
- **Not the legacy ledgers.** The signer **does not** and **cannot** mutate
  the legacy memory-broker ledgers (`owner_control.db`,
  `synthetic_evidence.db`, owner `lilith-memory-broker`, `InaccessiblePaths`
  for the signer) or any application or L04 database.
- **Who runs it.** The signer runs it under the hold. The old credential may
  still be loaded, but the op needs no signing, and creating ops are refused
  by the hold and by readiness.

**The op is destroy/narrow-only.** It:

- **may** record adoption of the K-ROOT-authorized successor epoch, and so
  make every old-epoch artifact unusable for creation;
- **may not** create or issue evidence;
- **may not** reopen `CONSUMED` or any terminal state;
- **may not** grant authority;
- **may not** make any key current.

The `signingKeyIds` field it records (as `REGISTRY_VIEW` also does) is a
**story-4 observation** of the authorized registry. Readiness re-derives it
from stories 1–3.

A signer that journals a bogus `ADVANCE_EPOCH` causes only
`LEDGER_EPOCH_AHEAD_OF_WITNESS`, which is availability loss.

### 9.5 Epoch rules and crash handling

| Rule | Behaviour |
| --- | --- |
| Next epoch | `(witness.counter + 1, fresh random)`, from the witness; bound in the authorization |
| Monotonic / fork | counter equal or `+1`; `FORKED` rejected; the random never repeats |
| Stale epoch | `LEDGER_EPOCH_STALE`, `STALE_EPOCH_*`, `CHALLENGE_EPOCH_NOT_CURRENT`, `RECOVERY_EPOCH_MISMATCH` |
| Replay | §9.2 |
| At most once | linear chain, `O_EXCL`, single instance + `flock`; after a crash, read the witness first |

| Crash after | Readiness | Allowed action |
| --- | --- | --- |
| hold written / authorization signed | issuance held | continue, or abandon (the authorization expires at `notAfter`) |
| ledger `ADVANCE_EPOCH` journalled | `LEDGER_EPOCH_AHEAD_OF_WITNESS` | witness executes **the same** authorization (completion) |
| witness executed | `NONTERMINAL_PRE_RECOVERY_WORK` | finish the quarantine and the swap |
| quarantine journalled; the witness record lost | `LEDGER_AHEAD_OF_WITNESS` | another epoch advance (with a new authorization) |
| chain file written; `witness.json` not renamed | witness refuses writes | RR-9 |

## 10. Registry succession and freshness head (RR-4, OWNER-ACCEPTED)

### 10.1 `verify_registry_succession(previous, following)` (PROPOSED)

A pure function with a closed reason set.

| Rule | Reason |
| --- | --- |
| same `environment` and `registryRootKeyId` | `SUCCESSION_ROOT_OR_ENVIRONMENT_CHANGED` |
| version decreased | `SUCCESSION_VERSION_REGRESSION` |
| same version, different digest (against a **trusted** prior head) | `SUCCESSION_SAME_VERSION_FORK` |
| `following.version ≠ previous.version + 1` (**no gaps**, accepted) | `SUCCESSION_VERSION_GAP` |
| `issuedAt` not decreasing | `SUCCESSION_TIME_REGRESSION` |
| epoch equal, or `NEWER` with counter `+1` | `SUCCESSION_EPOCH_INVALID` |
| every prior `keyId` present | `SUCCESSION_RECORD_REMOVED` |
| immutable per record: `signingDomain`, `evidenceTypes`, `environment`, `algorithm`, `publicKey`, `createdAt`, `notBefore`, `recoveryEpoch`, `policyVersion`, `registryVersion` | `SUCCESSION_RECORD_MUTATED` |
| `retiredAt`: `null → t` only. `revokedAt`/reason: `null → (t, reason)` only; the only later change allowed is `ROUTINE`/`SUPERSEDED` → `COMPROMISED`, with `revokedAt` fixed and `compromisedSince ≤ revokedAt` | `SUCCESSION_LIFECYCLE_REOPENED` |
| `COMPROMISED` is never cleared | `SUCCESSION_COMPROMISE_CLEARED` |
| a non-current record never becomes current | `SUCCESSION_LIFECYCLE_REOPENED` |
| new records carry `registryVersion == following.version` | `SUCCESSION_NEW_RECORD_VERSION` |
| the §7.2 single-current-key scope | `SUCCESSION_CURRENT_KEY_SCOPE` |

**Limit.** The function verifies only its inputs. It does **not** establish
durable fork or rollback protection. That depends on who supplies
`previous`.

### 10.2 Owner of the trusted prior head

| Source of `previous` | Trusted? |
| --- | --- |
| the retained registry directory (story 4, root files) | no: it can be restored |
| a `registryDigest` in the authority recovery ledger journal (story 4) | no: it can be restored, and no verification context consults it (`witness_authority_context` reads only the witness). It is kept at most as a local cross-check |
| **`RecoveryWitnessV2` registry head** (story 2) | **yes**, ledger-only threat model, while the witness survives |
| off-host / owner-held anchor | not designed (RR-12) |

### 10.3 `RecoveryWitnessV2` (accepted property; exact schema follow-on)

**Accepted.** `RecoveryWitnessV2` extends the witness freshness boundary.
Its signed monotonic state binds the trusted authority-registry head:

```text
registryHead = (registryVersion, registryDigest)
```

It uses the same witness identity and K-WIT. It creates no new service.
`RecoveryWitnessV1` is **not** mutated. V2 has its own schema version,
separator, vectors, and succession rules.

Required V2 properties (the exact field names come from the source slice):

1. **Head succession.** The head changes only to `(v + 1, digest)`
   (contiguous, no gaps), where
   `verify_registry_succession(head, candidate)` passes against the
   witnessed head. A same version with a different digest is refused.
2. **Head change operations.** The head changes **only** by executing one
   of the two K-ROOT authorizations:
   - an epoch advance, under an `EpochAdvanceAuthorizationV1` that names the
     target digest (§9.2);
   - an in-epoch head advance, under a `RegistryHeadAdvanceAuthorizationV1`
     (§10.4).

   No V2 operation advances the head from registry bytes alone. This replaces
   the V1-era `RAISE_REGISTRY_FLOOR {registry}` idea for V2.
3. **Verification context.** A V2 verification context requires
   `registry.digest == head.digest` and `registry.version == head.version`
   for NEW_ADMISSION and readiness. The historical-verification context uses
   the same head, because history is verified against the current head
   registry (B1b-3a).
4. **Existing V1 rules are kept:** epoch succession, ledger position, time
   monotonicity, and chain digest.
5. **Freshness state:** the witness chain records the executed
   `authorizationId`s of both contracts. An ID executed once is never
   executable again in that chain.

```text
witness head binding  != registry authority    (the head points at K-ROOT-signed content; the witness cannot author it)
witness freshness     != key activation
```

- Same-version fork detection is claimed **only** once V2 is implemented,
  and only while the witness survives.
- Whole-host rollback (witness + registry + recovery ledger together) stays
  **unresolved**.

### 10.4 `RegistryHeadAdvanceAuthorizationV1` (RR-15, OWNER-ACCEPTED; PROPOSED contract)

It authorizes `RecoveryWitnessV2` to advance from **one exact** authority-registry
head to **another exact** head, **inside the same `RecoveryEpochV1`**. It creates
no new service or state owner:

- K-ROOT stays the authorizer;
- `RecoveryWitnessV2` stays the freshness and execution boundary.

**Signing.** Ed25519 with K-ROOT over
`"LILITH_REGISTRY_HEAD_ADVANCE_AUTHORIZATION_V1\x00" ‖ JCS(all fields except
signature)`, verified with the pinned `TrustedRegistryRootV1`. The separator
must be distinct from every existing separator and from
`EpochAdvanceAuthorizationV1`'s. A pinning test is required in B1b-3e-S.

| Field | Binds |
| --- | --- |
| `protocol`, `schemaVersion` | `LILITH_REGISTRY_HEAD_ADVANCE_AUTHORIZATION`, `1` |
| `authorizationId` | a unique ID, recorded as consumed in the witness chain on execution |
| `nonce` | ≥ 128-bit fresh random |
| `environment` | exactly one environment |
| `recoveryEpoch` | `RecoveryEpochV1`; must equal the witness's current epoch **and** the target registry's epoch |
| `priorRegistryVersion`, `priorRegistryDigest` | the exact current head |
| `targetRegistryVersion`, `targetRegistryDigest` | the exact candidate; `targetRegistryVersion == priorRegistryVersion + 1` (DEV_SYNTHETIC: no gaps, no same-version advance) |
| `reason` | a closed transition-reason set, defined in source (for example successor rotation, administrative revocation, compromise marking) |
| `registryRootKeyId` | the signing root |
| `issuedAt`, `notAfter` | a validity window |
| `signature` | K-ROOT |

**Witness execution requires every one of these.** Any failure means
refusal, with no state change:

1. the witness's current head equals exactly `(priorRegistryVersion,
   priorRegistryDigest)`;
2. the target `AuthorityRegistryV1` verifies under K-ROOT;
3. the target's version and digest equal exactly `targetRegistryVersion` /
   `targetRegistryDigest`;
4. the target's `recoveryEpoch` equals the witness's current
   `RecoveryEpochV1`, and equals the authorization's `recoveryEpoch`;
5. `targetRegistryVersion == priorRegistryVersion + 1`, and
   `verify_registry_succession(prior head registry → target)` passes;
6. `authorizationId` has not been consumed in the witness chain;
7. `issuedAt ≤ witness updatedAt ≤ notAfter`. **This clock check is defence
   in depth only.** It is not the replay boundary.

Also checked: the signature, the environment, and the `registryRootKeyId`
match.

**The successor witness binds:**

- the target `registryVersion`;
- the target `registryDigest`;
- the consumed `authorizationId`.

The epoch and the V1 ledger-position, time, and chain rules are unchanged.
Any policy change arrives only with the new registry.

**Replay prevention** comes from three things together:

- the prior-head binding (after execution the head never equals the prior
  head again, because the chain is linear and contiguous);
- the linear witness chain;
- the recorded `authorizationId`.

`notAfter` only narrows the window.

**Staged / abandoned registries.** A K-ROOT-signed registry for which no
matching `RegistryHeadAdvanceAuthorizationV1` (or, across epochs,
`EpochAdvanceAuthorizationV1`) was executed stays a **staged or abandoned
registry**. It is story-4 bytes. It **cannot** become the trusted fresh head
merely because its bytes exist. V2 verification refuses it, because its
digest is not the head digest.

```text
signed registry        != effective current registry head
registry existence     != head-advance permission
K-ROOT authorization   != witness execution
witness execution      != independent verification
registry-head advance  != key issuance readiness
```

**Honest limits** (the same as §9.2):

- a witness restored alone could meet a replayed authorization, and this
  fails closed through the recovery-ledger position checks;
- whole-host rollback is not protected.

## 11. Issuance readiness

### 11.1 `REGISTRY_VIEW` is observation (story 4)

`REGISTRY_VIEW` is a journal record in the **authority recovery ledger**:

```text
REGISTRY_VIEW != authority
REGISTRY_VIEW != registry-root authorization
REGISTRY_VIEW != witness execution
```

- It is recorded only **after** the authoritative state has been
  independently verified: K-ROOT signature plus witness head.
- It is non-creating (`creates_authority=False`).
- It can only narrow issuance. Readiness re-derives the view and the key set
  from story 1 and story 2.
- A compromised or restored signer that writes `REGISTRY_VIEW` naming an
  unauthorized key gets `REQUIRED_KEY_UNAVAILABLE`,
  `BROKER_REGISTRY_VIEW_STALE`, or `REGISTRY_DOWNGRADE`. It can **never**
  make a successor current.

### 11.2 Loaded-key binding (RR-14, OWNER-ACCEPTED)

**Required before `S_CURRENT`:**

> the key actually loaded by the signer ==
> the single current key selected by the K-ROOT-verified registry at the
> fresh witness head.

**A signer self-claim is not sufficient.** The **independent verifier**
reproduces the comparison from inputs it obtains itself. Existing evidence is
reused, and no new service is added.

| # | Input | Source | Independent of the signer? |
| --- | --- | --- | --- |
| B1 | the selected key: the single in-scope current key of the registry that verifies under K-ROOT and equals the witness head | registry + witness (stories 1 + 2) | yes |
| B2 | the unit-slot credential blob's SHA-256 | root `stat`/hash of `/etc/credstore.encrypted/lilith-authority-dev.owner-actor.cred`. **No decryption** | yes (root-observed) |
| B3 | the keygen publication for B1's key: `{publicKey, publicKeySha256, blobSha256}` | the owner-retained transcript of the ceremony (L2 §7) | yes (ceremony record) |
| B4 | `HEALTH` `publicKeySha256` | the running signer (L1 service; L2 U5) | **no**: a self-claim |

**Binding holds** only if all of these are true:

- `B3.publicKey == B1.publicKey`;
- `B2 == B3.blobSha256`;
- `B4 == B3.publicKeySha256 == sha256(B1.publicKey)`;
- the systemd credential name is the fixed name (the embedded name binding,
  B1b-3d §5);
- no other `lilith-authority-dev` credential blob is present in the
  credential store.

B2 and B3 carry the independent part of the evidence. B4 alone would be a
signer claim.

**Limits:**

- The binding proves that the unit slot holds exactly the blob minted for
  the selected key, and that the signer reports that key.
- It does not prove what a *compromised* signer process holds in memory.
  That is outside this check: signer compromise means compromise (RR-6).
- The exact readiness input and result schema is B1b-3e-S work.

**Where B4 comes from (RR-14a; current source, inspected at `2e273a7` /
main `069f6d1`).** `HEALTH.publicKeySha256` is **derived cryptographically
at runtime from the private key loaded from the systemd credential**:

1. `services/authority-dev/lilith_authority_dev/server.py:206`, startup:
   `credential = inspect_owner_actor_credential(os.environ.get("CREDENTIALS_DIRECTORY"))`.
2. `services/authority-dev/lilith_authority_dev/credential.py`,
   `inspect_owner_actor_credential` (lines 57–85), checks three things:
   - the directory equals the fixed
     `CREDENTIALS_DIRECTORY = "/run/credentials/lilith-authority-dev.service"`,
     else `CREDENTIAL_INVALID` (`profile.py:49`);
   - it opens `<dir>/owner-actor-signing-key` (`CREDENTIAL_NAME`,
     `profile.py:46`) with `O_NOFOLLOW`;
   - the file is a regular file of ≤ 256 bytes.
3. `credential.py` `_classify` (lines 88–99):
   - `load_der_private_key(raw)`, which must be `Ed25519PrivateKey`;
   - `public = key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)`;
   - `del key`;
   - `CredentialStatusV1(CREDENTIAL_PRESENT_UNVERIFIED, hashlib.sha256(public).hexdigest())`.
4. `core.py:61`: `health()` returns
   `"publicKeySha256": self._credential.public_key_sha256`. It is that stored
   derived value, not configuration or cached publication metadata.

**Outcome A.** B4 shows that the running signer derived the expected public
key from the private material systemd actually delivered to the unit. B2
and B3 independently bind that key to the unchanged encrypted credential
artifact of the ceremony:

- the slot blob hash equals the publication's `blobSha256`;
- the publication's `publicKey` equals the registry's.

**RR-14a (proof-of-possession) therefore stays `DEFERABLE`.**

Two residuals remain:

- **B4 is still reported by the signer.** A compromised signer process could
  misreport it. B2 and B3 carry the independent part.
- **Source requirement for B1b-3e-S; not a new decision.** L1 derives the
  fingerprint and then releases the key object, and it never signs. When
  signing is implemented, the signing key object **must** come from the
  same credential load that produced `publicKeySha256`. A second, divergent
  load path is not allowed. Otherwise the reported fingerprint and the
  signing key could differ.

```text
credential loaded != current authority
signer claim      != verification
S_ACTIVATED       != S_CURRENT
```

## 12. Authority recovery ledger state machine

These transitions are enforced by `synthetic_recovery_ledger._step` (TEST). They
are made durable in `authority_ledger.db` by the B1b-3d schema (designed).

```text
Challenge
 (absent)  ── PREPARE (ready; current ledgerEpoch) ──▶ PREPARED
 PREPARED  ── CONSUME (ready; current epoch) ────────▶ CONSUMED ── ISSUE (ready; once) ──▶ CONSUMED + evidence
 PREPARED  ── EXPIRE / CANCEL / FAIL ────────────────▶ EXPIRED | CANCELLED | FAILED
 PREPARED  ── VOID_CHALLENGE (older epoch only) ─────▶ VOIDED_BY_RECOVERY

Evidence use
 (absent)  ── RESERVE (ready; issued here; epochs equal; unused) ──▶ RESERVED
 RESERVED  ── CONFIRM (ready; current epoch) ──▶ CONSUMED
 RESERVED  ── ABANDON ──▶ ABANDONED
 RESERVED  ── QUARANTINE_USE (older epoch only) ──▶ QUARANTINED_BY_RECOVERY ── RECONCILE_DECISION ──▶ ABANDONED (designed)

Journal-global (story-4 observations and destroy/narrow-only records)
 GENESIS (seq 0) · REGISTRY_VIEW (version strictly up) · ADVANCE_EPOCH (counter strictly up; destroy/narrow-only)
```

| Rule | Mechanism |
| --- | --- |
| **PREPARED may be voided** | `VOID_CHALLENGE` (older epoch; destroy-only); in-epoch `CANCEL` / `EXPIRE` / `FAIL` |
| **CONSUMED never reopens** | no transition leaves it; rows showing otherwise → `TERMINAL_STATE_REOPENED`; triggers forbid terminal edits |
| CONSUMED is never reusable | `EVIDENCE_ALREADY_ISSUED`, `EVIDENCE_ALREADY_USED` |
| Stale epoch rejected | `CHALLENGE_EPOCH_NOT_CURRENT`, `STALE_EPOCH_CHALLENGE`, `STALE_EPOCH_EVIDENCE`, `STALE_EPOCH_RESERVATION` |
| An old epoch never becomes current | `ADVANCE_EPOCH` counter strictly up; witness succession |
| History is additive | an append-only hash-chained journal; terminal rows kept |
| No journal op grants authority | readiness evaluates the journal against stories 1–2 |

Forbidden:

- `CONSUMED → PREPARED`;
- `CONSUMED → reusable`;
- any transition out of a terminal state;
- `QUARANTINED_BY_RECOVERY → RESERVED/CONSUMED`;
- `ADVANCE_EPOCH` to an older or forked epoch;
- `REGISTRY_VIEW` to a version that is lower or equal;
- restore → a replayable owner proof.

## 13. Failure matrix

Every row reports `rollbackDetectionScope: LEDGER_ONLY` and
`wholeHostRollbackProtected: false`. None of this is live until B1b-3d
L3a–L4 exist.

| # | Failure | Authoritative owner | Allowed recovery | Authority changes? | Historical evidence changes? | Fail-closed behaviour |
| --- | --- | --- | --- | --- | --- | --- |
| F1 | crash before successor preparation | owner (intent); hold = gating | release or continue | no | no | hold blocks creation |
| F2 | crash after successor preparation | credential custody | destroy the unpublished blob, or continue | no | no | S is in no registry and not loadable |
| F3 | crash after registry authorization (candidate signed, with or without `RegistryHeadAdvanceAuthorizationV1`) | K-ROOT (authority); witness head still vN | execute the head advance later, or abandon it (let (B) expire before signing a competing (B)) | none effective: a staged candidate is not the head | no | hold; ledger view vN; the staged digest is not the head |
| F4 | crash after witness execution (head advance or epoch advance) | witness | forward only | P not fresh / E(n) stale | no | `BROKER_REGISTRY_VIEW_STALE`, `REQUIRED_KEY_UNAVAILABLE`, `NONTERMINAL_PRE_RECOVERY_WORK` |
| F5 | crash after registry publication, before activation | witness + authority recovery ledger | complete step 5 | no | no | ledger view stale |
| F6 | stale authorization replay (epoch or head advance) | witness | none | no | no | V2: prior-witness / prior-head mismatch, `authorizationId` already consumed, `notAfter` (defence in depth); V1: counter / floor |
| F7 | old credential restored | K-ROOT registry + witness head + verifier binding | leave it unloaded; RR-7 | no | no, unless → `COMPROMISED` | binding mismatch, `REQUIRED_KEY_UNAVAILABLE` |
| F8 | old registry restored | witness | reinstate the head bytes | no | no | `REGISTRY_DOWNGRADE` / off-head; history blocked |
| F9 | old authority recovery ledger restored | witness | reinstate a witnessed ledger, or advance the epoch | only via an advance | no | `LEDGER_BEHIND_WITNESS` etc. |
| F10 | old registry + old recovery ledger, witness survives | witness | reinstate the head, then advance the epoch | only via an advance | no | `REGISTRY_DOWNGRADE`, then `LEDGER_BEHIND_WITNESS` |
| F11 | whole-host rollback | **none survives** | none; out-of-band distrust | **undetected** | undetected | **not fail-closed** |
| F12 | compromised old key | K-ROOT | mark it `COMPROMISED`; advance the epoch if it was the issuing key (RR-6) | yes | **yes**: all of its evidence (C-1) | `REQUIRED_KEY_UNAVAILABLE` |
| F13 | ordinary rotation | K-ROOT → witness → verifier | §7 (`SUPERSEDED`) | S after `S_CURRENT` | no | no issuance, steps 1–6 |
| F14 | successor lost before activation | K-ROOT | vN+2 revokes S `ROUTINE`; name S′ | no | no | S cannot issue |
| F15 | successor lost after activation | K-ROOT | no exposure → `ROUTINE` + rotate; exposure → `COMPROMISED` + advance | S replaced | only on compromise | missing credential fails the unit |
| F16 | same-version registry fork | witness V2 head | refuse; K-ROOT incident | no | no | V1: **undetected**; V2: head-digest mismatch |
| F17 | crash between a recovery-ledger commit and its witness record | witness | epoch advance | only via an advance | no | `LEDGER_AHEAD_OF_WITNESS` |
| F18 | compromised or restored signer writes `REGISTRY_VIEW` / `ADVANCE_EPOCH` | K-ROOT + witness | re-derive from stories 1–2 | **no** | no | `REQUIRED_KEY_UNAVAILABLE` / `BROKER_REGISTRY_VIEW_STALE` / `LEDGER_EPOCH_AHEAD_OF_WITNESS` |
| F19 | root-equivalent principal forges or removes the hold | readiness + verifier | ceremony incident | no | no | a forged hold → availability; a removed hold → still needs readiness + binding |
| F20 | signer reports the S fingerprint, but the slot holds another blob | verifier (B2/B3) | stop; investigate | no | no | binding fails; no `S_CURRENT` |
| F21 | a staged or abandoned K-ROOT registry is served, or presented, as current | witness V2 head | serve the head bytes | no | no | V2: digest ≠ head digest → refused; without an executed authorization it never becomes the head |
| F22 | a head-advance authorization is presented for a different epoch, a non-contiguous target, or the same version | witness V2 | none | no | no | refused (§10.4 checks 3–5) |

## 14. Security boundaries, risks, and non-claims

| Actor | Can | Cannot |
| --- | --- | --- |
| Owner + K-ROOT (workstation) | sign registry generations, `EpochAdvanceAuthorizationV1`, and `RegistryHeadAdvanceAuthorizationV1` | execute on the host without a host-root session |
| Host root (break-glass; root-equivalent under DR-3) | request witness ops; install; write or remove the hold; hash blobs. At Level 3: read credentials and forge the witness | authorize anything |
| `lilith-authority-dev` | write the authority recovery ledger, including observations and destroy/narrow records; report `HEALTH` | mutate the legacy broker ledgers or L04; advance freshness; make a key current; pass the verifier binding on a claim alone |
| `lilith-recovery-witness` | sign freshness successors after verifying authorizations | sign evidence, registries, or authorizations; author registry content; read the recovery ledger or K-ACT |
| `lilith`, Hermes, the model, the routine deployer | nothing here | anything here |

**Unresolved risks:**

1. Whole-host rollback (RR-12).
2. Retroactive compromise (C-1).
3. Snapshot-retained key material (RR-7).
4. Same-version forks remain undetected until V2 is implemented.
5. Expiry depends on the host clock (defence in depth only).
6. The per-transition witnessing cost (T-4).
7. The binding does not inspect signer memory (RR-14a).
8. The unauthenticated owner request (RR-13).
9. DR-3 and Level 3.

**Non-claims.** None of the following is claimed:

- PROD authority, or closure of the cross-environment debt;
- real-owner-grade custody or a real registry root;
- First Memory;
- signer activation or witness installation;
- Privacy custody (B1b-3f);
- WebAuthn changes;
- Stage III;
- a whole-host solution;
- zeroization;
- consciousness or personhood;
- automatic recovery from backups;
- any new owner-signature scheme beyond the reuse of K-ROOT for
  `EpochAdvanceAuthorizationV1` and `RegistryHeadAdvanceAuthorizationV1`;
- any live mutation.

## 15. Follow-on source slice (B1b-3e-S, TEST-only; not authorized here)

It lives under `services/owner-memory-control/` and `services/authority-dev/`,
and touches neither `services/core-api/**` nor `services/memory-broker/`.
All of its source-blocking decisions are resolved (§16).

1. `verify_registry_succession` (§10.1), with golden vectors and a full
   negative matrix.
2. `RecoveryWitnessV2` with the registry head, head succession, recorded
   `authorizationId`s, and the V2 verification context. V1 vectors and pins
   are unchanged.
3. `EpochAdvanceAuthorizationV1` (§9.2), with a new separator, vectors, and
   the witness execution checks 1–9.
   `RegistryHeadAdvanceAuthorizationV1` (§10.4), as a **separate** contract
   with its own separator, vectors, and the witness execution checks 1–7.
   Negative cases:
   - wrong prior head;
   - a target digest or version mismatch;
   - a cross-epoch target;
   - a gap or same-version target;
   - a consumed ID;
   - expired;
   - a staged registry with no executed authorization;
   - cross-use of one authorization type as the other.

   The signing-key object must come from the same credential load as the
   `HEALTH` fingerprint (§11.2).
4. The §7.2 scope check, using `signingDomain` and `evidenceTypes` as the
   exact source fields.
5. In-epoch rotation in the TEST recovery-ledger model: `SUPERSEDED`
   predecessor; `REGISTRY_VIEW` as observation only; each §7.6 crash point;
   F18 and F20.
6. The loaded-key binding (§11.2) as readiness input plus verifier result.
7. The C-4 order, with the recovery-ledger adoption record carrying
   `authorizationId`, tested against `witness_succession_reason` on an
   unrestored ledger.
8. `CeremonyHoldV1` and `AuthorityKeyTransitionV1`.
9. The B2a, B1b-3a, B1b-3b, and B1b-3c golden files and SHA-256 pins stay
   unchanged.

A live rehearsal (B1b-3e-L) needs B1b-3d L3a–L4 live and accepted, the
`BLOCKING_BEFORE_LIVE_3E` decisions resolved, and its own ladder.

## 16. Owner decisions (RR-2 … RR-15)

| # | Question | Status | Class | Result / recommendation |
| --- | --- | --- | --- | --- |
| RR-2 | Epoch-advance execution authorization | **OWNER-ACCEPTED** | `BLOCKING_BEFORE_3E_SOURCE` (satisfied) | a distinct K-ROOT-signed `EpochAdvanceAuthorizationV1` (§9.2) |
| RR-3 | Single current key | **OWNER-ACCEPTED** | `BLOCKING_BEFORE_3E_SOURCE` (satisfied) | at most one current key per `(environment, recoveryEpoch, signingDomain, evidenceType)` (§7.2) |
| RR-4 | Registry head anchor; version gaps | **OWNER-ACCEPTED** | `BLOCKING_BEFORE_3E_SOURCE` (satisfied) | `RecoveryWitnessV2` binds `(registryVersion, registryDigest)`; contiguous versions. The schema is follow-on work |
| RR-5 | Epoch-advance ordering | resolved by **C-4** | — | the B1b-3c order |
| RR-5a | Owner of the pre-witness `ADVANCE_EPOCH` | **OWNER-ACCEPTED (conditional; condition met, §9.4)** | `BLOCKING_BEFORE_3E_SOURCE` (satisfied) | the signer, on the **authority recovery ledger** only; destroy/narrow-only |
| RR-6 | Does issuing-key compromise force an epoch advance? | open | `BLOCKING_BEFORE_LIVE_3E` | recommend always (fail closed) |
| RR-7 | Is retained or restored key material a compromise? | open | `BLOCKING_BEFORE_LIVE_3E` | recommend the boundary rule (§8.4) |
| RR-8 | `compromisedSince ≤ revokedAt` friction | deferred | `DEFERABLE` | accept imprecise forensics in V1; the verdict is unaffected |
| RR-9 | Witness crash between the chain write and the rename | open | `BLOCKING_BEFORE_LIVE_3E` | recommend roll-forward to a verified signed successor only |
| RR-10 | Rotation lifecycle and `t_cut` | **OWNER-ACCEPTED** | `BLOCKING_BEFORE_3E_SOURCE` (satisfied) | `SUPERSEDED` for rotation; `ROUTINE` for administrative ends; `t_cut` owned by the K-ROOT lifecycle fields; ledger records are evidence only (§6.1, §7.3) |
| RR-10a (residual) | Should B1b-3c epoch-advance predecessors keep `retiredAt`, or use `SUPERSEDED`? | open | `DEFERABLE` | verifier-identical. Recommend keeping the B1b-3c `retiredAt` until the source slice revisits the ceremony |
| RR-11 | Successor keygen slot and release set | open | `BLOCKING_BEFORE_LIVE_3E` | recommend a new reviewed release plus a successor keygen form |
| RR-12 | First whole-host anchor | deferred | `DEFERABLE` | none yet |
| RR-13 | Authenticated owner request | deferred | `DEFERABLE` | unauthenticated intent for DEV_SYNTHETIC; K-ROOT objects are the first authority |
| RR-14 | Loaded-key binding | **OWNER-ACCEPTED** | `BLOCKING_BEFORE_3E_SOURCE` (satisfied) | the independent verifier reproduces B1–B4 (§11.2) |
| RR-14a | Proof-of-possession op for K-ACT | **classified from source: outcome A** (§11.2) | `DEFERABLE` | `HEALTH.publicKeySha256` is derived at runtime from the loaded private key (`credential.py` `_classify`). Not required now: it would add a K-ACT artifact type, and B2/B3 already give independent evidence |
| RR-15 | Does an in-epoch registry-head advance need an explicit K-ROOT execution authorization? | **OWNER-ACCEPTED** | `BLOCKING_BEFORE_3E_SOURCE` (satisfied) | yes: a distinct `RegistryHeadAdvanceAuthorizationV1` (§10.4). Single use; exact prior and target head; same epoch; `target = prior + 1`. A staged or abandoned registry never becomes the head. It is kept distinct from `EpochAdvanceAuthorizationV1`, with no generic envelope |

Carried forward unchanged:

- B1b-3c open decisions 3, 5 (T-4), 6, and 7;
- B1b-3d T-6 and T-9.

## 17. Owner-accepted decisions and review history

| Decision | Result |
| --- | --- |
| C-1 | B1b-3a retroactive compromise is kept. Pre-compromise survival is deferred |
| C-4 | The B1b-3c succession order governs. The B1b-3d §13 steps 7 and 9, and its §10 `ADVANCE_EPOCH` shape, are superseded for B1b-3e |
| RR-2 | A distinct K-ROOT `EpochAdvanceAuthorizationV1`. The owner request stays unauthenticated intent |
| RR-3 | At most one current issuance key per cryptographic authority scope. In source that is `(signingDomain, evidenceType)` within one registry |
| RR-4 | `RecoveryWitnessV2` binds the registry head `(registryVersion, registryDigest)`; no gaps |
| RR-5a | The signer's pre-witness `ADVANCE_EPOCH` runs only on the authority recovery ledger it already solely owns. It is destroy/narrow-only |
| RR-10 | `SUPERSEDED` for rotation and `ROUTINE` for administrative ends. `t_cut` is owned by K-ROOT lifecycle fields |
| RR-14 | Independently verified loaded-key binding before `S_CURRENT` |
| RR-15 | A distinct K-ROOT `RegistryHeadAdvanceAuthorizationV1` for every in-epoch head advance. A staged or abandoned registry never becomes the head |

**Review passes:**

- **`fff4ea2` — first draft.**
- **`2d9d57b` — authority story separated from freshness and observation.**
  - The witness is freshness only.
  - `REGISTRY_VIEW` is observation.
  - The hold is gating.
  - Forks need a witness-bound head.
- **This pass — source-blocking decisions resolved.**
  - RR-2, RR-3, RR-4, RR-5a, RR-10, and RR-14 are recorded as accepted.
  - The ledgers are named unambiguously.
  - The key-record field truth is established from source.
  - RR-10a, RR-14a, and RR-15 are raised as residual or new open items.
- **Closure pass — RR-15 accepted; RR-14a classified from source.**
  - RR-15 is accepted, and `RegistryHeadAdvanceAuthorizationV1` is added.
  - `S_AUTHORIZED` now separates key authorization (A) from head-advance
    authorization (B).
  - RR-14a is classified `DEFERABLE` from the current `HEALTH` source.

## 18. Acceptance criteria for design closure

1. The four stories (§1) are kept distinct throughout. No story takes over
   another's role.
2. The accepted decisions in §17 are reflected exactly.
3. No `BLOCKING_BEFORE_3E_SOURCE` item remains open: RR-2, RR-3, RR-4,
   RR-5a, RR-10, RR-14, and RR-15 are accepted, and RR-14a is `DEFERABLE`
   from source.
4. The pinned invariants in §2 hold everywhere:
   - PREPARED may be voided;
   - CONSUMED never reopens;
   - `restore != authority restoration`;
   - `registry publication != activation`;
   - `witness freshness != authority`;
   - `REGISTRY_VIEW != authority`;
   - `loaded credential != accepted/current authority`.
5. F11 is acknowledged as not fail-closed. F16 is acknowledged as not
   fail-closed until V2 is implemented.
6. The non-claims in §14 are unchanged.
7. The `BLOCKING_BEFORE_LIVE_3E` decisions (RR-6, RR-7, RR-9, RR-11) are
   decided before any live B1b-3e step is designed.

**Design status.** Criteria 1–6 are met by this record. Criterion 7 governs
only live work.

**B1b-3e DESIGN is READY FOR PR REVIEW.** This does **not** mean any of the
following:

- B1b-3e source is implemented. It is not; B1b-3e-S is a separate,
  unauthorized slice.
- A live rehearsal is authorized. It is not.
- RR-6, RR-7, RR-9, or RR-11 are closed. They stay `BLOCKING_BEFORE_LIVE_3E`.
- Whole-host rollback is resolved. It stays **unresolved**.

## Explicitly not done

- No DEV or PROD contact. No gcloud, SSH, IAP, systemctl, systemd-creds, or
  sudo.
- No key, credential, registry, witness, ledger, or blob was touched.
- No change to source, tests, vectors, workflows, IAM, WIF, sudoers, the
  broker, Stage III, or activation.
- No edit of the B1b-3a, B1b-3c, or B1b-3d records.
- No claim of real authority, real-owner custody, First Memory, same-version
  fork detection before V2, or whole-host rollback protection.
