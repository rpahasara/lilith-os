# Slice 15B2b-B1b-3e — Rotation, Revocation, Restore, and Recovery Semantics

Status:

- **DESIGN RECORD** (second review pass)
- **OWNER DECISIONS C-1 AND C-4 ACCEPTED** (§17)
- **NOT IMPLEMENTED**
- **NOT LIVE**
- **NO LIVE MUTATION AUTHORIZED**
- **WHOLE-HOST ROLLBACK UNRESOLVED**
- **REAL AUTHORITY ABSENT**

Base: protected main `069f6d1861b79d817f8b959e36b53f017bfbac32`.

This record defines the fifth sub-slice of the
[B1b-3 custody isolation design](slice-15b2b-b1b3-custody-isolation-design.md).
It follows the [B1b-3d live closure](slice-15b2b-b1b3d-live-closure.md) and
builds on three earlier records:

- [B1b-3a](slice-15b2b-b1b3a-authority-registry-contracts.md): registry,
  key-record, and evidence contracts;
- [B1b-3c](slice-15b2b-b1b3c-recovery-epoch-witness.md): recovery epoch,
  witness, ledger, and readiness;
- the [B1b-3d design](slice-15b2b-b1b3d-dev-synthetic-custody-design.md):
  DEV_SYNTHETIC custody, the witness service, the ceremony, and the ledger
  schema.

This is a design and source-review record only. It is not any of the
following:

- an acceptance record;
- an implementation authorization;
- a ceremony runbook;
- an activation instruction.

It does **not** mark any of the following as complete:

- B1b-3;
- Level 2 isolation;
- real owner authority;
- First Memory;
- Privacy custody;
- Stage III.

No DEV, PROD, IAM, WIF, systemd, key, credential, registry, witness, ledger,
broker, or Stage III state was contacted or changed. No source, test, vector,
workflow, or contract was changed.

Labels are used as in the B1b-3 records.

| Label | Meaning |
| --- | --- |
| **CANONICAL** | defined by accepted records or by protected-main source |
| **IMPLEMENTED** | present in source (TEST) or in installed state |
| **LIVE** | installed on DEV, per the B1b-3d live closure |
| **PROPOSED** | recommended by this record. It still needs review and a separately authorized source slice |
| **OWNER-ACCEPTED** | a conflict decision the owner accepted in this review pass (§17) |
| **SUPERSEDED FOR B1b-3e** | a part of an earlier design record that this record replaces for all future implementation. The earlier record itself is not edited |

## 1. Scope and current live baseline

B1b-3e defines what four words mean for LILITH authority:

- **rotation:** an authority key is replaced by a successor;
- **revocation:** a key stops being usable for new evidence;
- **restore:** bytes come back from an older state;
- **recovery:** authority resumes after a restore or a fault.

The **authority story** is kept separate from the **freshness story** and the
**causal/storage story**:

| Story | Question | Owner |
| --- | --- | --- |
| Authority | which keys does the owner's registry root authorize? | the owner, offline, through K-ROOT-signed `AuthorityRegistryV1` |
| Freshness | is this registry state recent enough to trust, or is it stale or rolled back? | the recovery witness (`RecoveryWitnessV1`) |
| Local issuance readiness | may this signer, with this ledger and this loaded credential, issue now? | the signer ledger + the readiness gate + independent verification |
| Storage / causal | which bytes exist, were restored, or were installed? | the filesystem, root, and credential custody |

The existence, restoration, or installation of bytes never decides by
itself whether authority exists.

**Current live DEV state** (from the
[live closure](slice-15b2b-b1b3d-live-closure.md) §4 and §6):

| Artifact | Live? |
| --- | --- |
| K-ACT `test-only.dev-synthetic.actor.b1b3d.1` host-bound encrypted blob | **yes** (custody only) |
| `/var/lib/systemd/credential.secret` | yes |
| `lilith-authority-dev` account, release `9ac7de2…`, units (inactive, not enabled) | yes |
| `AuthorityRegistryV1`, `TrustedRegistryRootV1`, `/etc/lilith-authority-dev` | **no** |
| K-WIT, `lilith-recovery-witness`, `RecoveryWitnessV1` | **no** |
| `authority_ledger.db` | **no** |
| Activation | `NOT_ACCEPTED reason=GRANT_ABSENT` |

K-ACT is **not an authority key yet**. It appears in no registry, and it has
no `AuthorityKeyRecordV1`. No witness or ledger exists.

- Replacing K-ACT today would be a custody change with **no authority
  effect**.
- Every rotation, revocation, and epoch semantic in this record becomes live
  only after B1b-3d L3a–L4 exist: the registry, the anchors, the witness,
  the ledger, and signer readiness. None of these is authorized.

## 2. Inherited and pinned invariants

These are inherited unchanged:

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

B1b-3e pins these as well:

```text
rotation                   != silent replacement
prepared                   != active
published                  != activated
credential exists          != accepted authority

witness freshness          != authority grant
witness floor              != key activation
registry publication       != signer issuance readiness

REGISTRY_VIEW              != authority
REGISTRY_VIEW              != registry-root authorization
REGISTRY_VIEW              != witness execution

hold file                  != owner request
root custody               != owner authorization

signed authorization       != executed transition
witness receipt            != independent verification
evidence.issuedAt          != authority cutover
```

Two B1b-3c rules are inherited unchanged. They are listed under "Two rules
carry the whole slice" in the B1b-3c record:

1. **Removing authority never needs readiness. Creating it always does.**
2. **Recovery can only destroy pending authority, never create any.**

## 3. Existing contracts reused

B1b-3e reuses the following as they are. It adds no duplicate concept.

| Contract / mechanism | Source | Role in B1b-3e |
| --- | --- | --- |
| `AuthorityKeyRecordV1`: `createdAt`, `notBefore`, `retiredAt`, `revokedAt`, `revocationReason ∈ {ROUTINE, COMPROMISED, SUPERSEDED}`, `compromisedSince`, `recoveryEpoch`, `policyVersion`, and the immutable first-publication `registryVersion` | `authority_contracts.py` | the only representation of key lifecycle |
| `AuthorityRegistryV1`, `TrustedRegistryRootV1` | `authority_contracts.py` | the **authority** state; the registry root signs every key transition and every epoch advance |
| `verify_authority_registry`, `verify_owner_evidence` (44-reason taxonomy) | `authority_verifier.py` | forward rejection and historical verification |
| `RecoveryEpochV1 {counter, random}`, `epoch_digest`, `compare_epochs` (`EQUAL` / `OLDER` / `NEWER` / `FORKED`), `ledger_epoch_id` | `authority_contracts.py`, `recovery_contracts.py` | epoch identity, ordering, and fork detection |
| `RecoveryWitnessV1`, `TrustedWitnessAnchorV1`, `witness_succession_reason` (`SUCCESSION_REASONS`) | `recovery_contracts.py` | the **freshness** state and its monotonic succession |
| `witness_authority_context` | `recovery_contracts.py` | combines the registry-root anchor with witness freshness (floor, epoch, policy) into the verification context. Its docstring says the "trusted monotonic inputs [are] taken from the verified witness and nowhere else" |
| `AuthorityLedgerStateV1` journal ops: `PREPARE`, `CONSUME`, `ISSUE`, `RESERVE`, `CONFIRM`, `EXPIRE` / `CANCEL` / `FAIL`, `ABANDON`, `REGISTRY_VIEW`, `ADVANCE_EPOCH`, `VOID_CHALLENGE`, `QUARANTINE_USE` | `synthetic_recovery_ledger.py` | the ledger state machine |
| `begin_recovery`, `quarantine_pre_recovery`, `RECOVERY_REASONS` | `synthetic_recovery_ledger.py` | the governing epoch-advance ledger steps (C-4) |
| `evaluate_restore_readiness` → `RESTORE_READY` / `NOT_READY(reason)` | `synthetic_recovery_ledger.py` | the only gate for authority-creating operations |
| `RecoveryEpochTransitionV1` | `synthetic_recovery_ledger.py` | the acknowledgement after an epoch advance. It is a record, not an authority |
| `RecoveryBoundAdmissionGateV1`, `verify_historical_accepted_memory` | `recovery_admission.py` | NEW_ADMISSION_AUTHORITY vs HISTORICAL_VALIDITY |
| Witness owner-socket ops `BOOTSTRAP`, `RAISE_REGISTRY_FLOOR`, `ADVANCE_EPOCH`; signer op `RECORD_LEDGER_ADVANCE`; ceremony hold; verifier CLI | B1b-3d design §10, §11, §13 | the execution and verification boundaries. They are designed, not live, and C-4 applies (§9.2) |
| DEV_SYNTHETIC backup policy: no K-ACT or K-WIT backup; loss means re-key | B1b-3d design §16 | the credential-restore policy |

## 4. State owners

Every state object has exactly one owner. **No new service, identity,
socket, or layer is introduced.** Every B1b-3e object is either a refinement
of an existing owner's state or a record that the existing verifier produces.

| State | Owner | Where | Mutated by | Is authority? | Live? |
| --- | --- | --- | --- | --- | --- |
| Owner transition request | the owner (a person) | the owner's workstation ceremony transcript. **No authenticated contract exists** (§9.1, RR-13) | the owner | no: intent only | no |
| Local ceremony hold | host root | the root-owned hold file (B1b-3d §13 step 1) | host root | no: storage and gating only | no |
| Authority registry state | the owner, **offline**, through K-ROOT | signed `AuthorityRegistryV1` documents (all versions retained) | owner workstation only | **yes**: the only authority state | no (no K-ROOT anchor is installed) |
| Registry freshness: floor, epoch, policy; a head binding is proposed (§10.3) | the recovery witness | `witness.json` + append-only `chain/` | the witness service only, on request | **no**: freshness and rollback evidence | no |
| Served registry file / pointer | host root | `/etc/lilith-authority-dev/registry/` | host root | no: storage | no |
| Challenge, evidence, and evidence-use ledger; the observed registry view; the journalled signing key set | `lilith-authority-dev` | `authority_ledger.db` journal (authoritative over rows) | the signer only | no: local state, gated by readiness | no |
| Private key material (K-ACT; later K-WIT) | root credential store + systemd | `/etc/credstore.encrypted/*.cred`, the host key | root ceremony CLIs | no | K-ACT **yes** |
| Verification / read model | nobody (stateless) | output of the independent root-run verifier CLI | — | no | no |
| Legacy `owner_control.db` `authority_epoch` | none: retired, non-authoritative history (B1b-3d T-12) | the legacy broker DB | — | no | yes, inert |
| Application databases | not an authority owner; never consulted (B1b-3c §14) | — | — | no | — |

**Verification is the combination.** A verifier trusts two things together:

1. a registry that verifies under the pinned `TrustedRegistryRootV1`
   (authority);
2. the verified witness's freshness inputs, taken through
   `witness_authority_context` (freshness).

Neither input alone is enough:

- A K-ROOT-signed registry that is not fresh enough is stale authority, and
  it is refused (`REGISTRY_DOWNGRADE`).
- A witness names no key and grants nothing.

**Infrastructure depth is proportional to cognitive relevance.** B1b-3e adds
none of these:

- a witness replica;
- a rotation daemon;
- a scheduler;
- an off-host service.

The only property being protected is this: owner-approved memory is never
accepted on authority that is not current and fresh.

## 5. Timestamp and interval semantics (CANONICAL, from source)

These are enforced by `authority_verifier._verify_evidence`,
`AuthorityKeyRecordV1.from_dict`, and `AuthorityRegistryV1.from_verified_dict`.

| Field | Record constraint | Verification effect |
| --- | --- | --- |
| `createdAt` | `notBefore ≥ createdAt`; `revokedAt ≥ createdAt`; `createdAt ≤ registry.issuedAt` | ordering only; no rule on evidence |
| `notBefore` | `notBefore ≥ createdAt`; **not** bounded by `registry.issuedAt` | `issuedAt < notBefore` → `KEY_NOT_YET_VALID` |
| `retiredAt` | `retiredAt ≥ notBefore`; `retiredAt ≤ registry.issuedAt` | `issuedAt ≥ retiredAt` → `KEY_RETIRED`, **both purposes** |
| `revokedAt` + `revocationReason` | set together; `revokedAt ≥ createdAt`; `revokedAt ≤ registry.issuedAt` | ROUTINE or SUPERSEDED: `issuedAt ≥ revokedAt` → `KEY_REVOKED`, both purposes |
| `compromisedSince` | set **if and only if** `COMPROMISED`; `compromisedSince ≤ revokedAt` | **not consulted.** Every piece of evidence from the key → `KEY_COMPROMISED`, both purposes (C-1, §6.3) |
| evidence `issuedAt` | signer-controlled | the only time the evidence carries. **Not trustworthy after key exposure** |
| `signedAt`, accepted-at | **do not exist** in any B1b-3a or B1b-3c contract | — |
| key "current" | `retiredAt == null and revokedAt == null` (independent of `notBefore`) | registry invariant: a current key is in the registry's epoch and policy |

The only trusted ordering of authority events is the **ledger journal
sequence**, and it is anchored by the witness's
`ledgerSequence`/`ledgerHead`. It is ledger-only and holds only while the
witness survives (B1b-3c §16). No trusted wall-clock acceptance time exists.

## 6. Revocation semantics

### 6.1 Four distinct transitions

| Transition | Record expression (CANONICAL fields) | Meaning | Evidence already issued |
| --- | --- | --- | --- |
| **Retirement** | `retiredAt = t` | planned end of validity; the key is not suspected. Used by every epoch advance: "every current E1 key is retired at the recovery instant" (B1b-3c §10). Proposed for rotation (RR-10) | valid if `notBefore ≤ issuedAt < t` (`RETIRED_AFTER_ISSUANCE`) |
| **Routine revocation** | `revokedAt = t`, `ROUTINE` | stopped for a non-security reason: lost, decommissioned, or never activated | valid if `issuedAt < t` (`REVOKED_AFTER_ISSUANCE`) |
| **Supersession** | `revokedAt = t`, `SUPERSEDED` | replaced by a successor before its planned retirement. It verifies the same as ROUTINE. **No successor-link field exists**, and none is invented; the link lives in the transition record (§7.7) | as ROUTINE |
| **Compromise** | `revokedAt = t`, `COMPROMISED`, `compromisedSince ≤ t` | private material may be outside custody | **all rejected**, `KEY_COMPROMISED`, both purposes |

### 6.2 Historical-validity invariant

> Evidence that was valid under the registry/key state that applied to its
> issuance is not retroactively invalidated merely because its key is later
> retired, routinely revoked, or superseded.

This holds in source for retirement, ROUTINE, and SUPERSEDED. The B1b-3a
golden vectors freeze it: "retirement accepted as history" and "in-flight
evidence surviving a registry update".

It holds **only while the key record is kept unchanged** in every later
registry, because verification uses only the current registry. The B1b-3a
record puts it this way: "a key record removed from a later registry makes
its evidence `KEY_UNKNOWN`". A rewritten `recoveryEpoch` or `policyVersion`
would give `RECOVERY_EPOCH_MISMATCH` or `POLICY_VERSION_MISMATCH`.

Today no source compares one registry version with the next. §10 closes this
in design.

### 6.3 Compromise: decision C-1 (OWNER-ACCEPTED)

**Accepted: the current B1b-3a source semantics.** The source says it
verbatim, in the `authority_verifier.py` module docstring:

> compromise is retroactive: every piece of evidence the key signed is
> rejected, whatever its signer-controlled `issuedAt`, because
> re-attestation does not exist yet;

This means:

- `COMPROMISED` → `KEY_COMPROMISED` for **all** evidence from that key. This
  holds for both purposes, including evidence whose `issuedAt` claims a time
  before `compromisedSince`.
- **Reason.** `issuedAt` is signer-controlled. After a compromise, whoever
  holds the key can backdate newly forged evidence. `compromisedSince` must
  **not** be used as evidence that earlier-looking evidence is still
  trustworthy.
- `compromisedSince` is recorded forensic information. It is not a
  verification boundary.
- Routine retirement and non-compromise revocation keep valid historical
  evidence under their existing interval rules (§6.2). Compromise is the one
  deliberate exception.
- **Deferred:** pre-compromise evidence of a compromised key surviving. This
  needs an independent timestamp, an admission-time attestation, or a
  re-attestation contract that the compromised signing key cannot forge.
  - A candidate basis is the witness-anchored ledger position of the
    evidence's `ISSUE` and `CONFIRM` operations. That is ledger-only.
  - Another is an owner-signed checkpoint over accepted evidence digests.

  Neither exists, and neither is designed here.
- The B1b-3a source is unchanged.

**Friction, recorded only (RR-8).** The contract enforces
`compromisedSince ≤ revokedAt`. Suppose a key was routinely revoked at
`t_r`, and its material leaks after `t_r`. It can be escalated to
compromised only by setting `compromisedSince ≤ t_r`. The verdict is the same,
because compromise is retroactive. The forensic field is then knowingly
imprecise.

### 6.4 Forward rejection, stale registries, and registry-version effects

- **Forward rejection at the verifier.** After retirement or revocation at
  `t`, evidence with `issuedAt ≥ t` is refused for both purposes.
- **Forward rejection at the ledger.** Issuance is refused before evidence
  exists:
  - readiness requires every journalled signing key to be current and not
    compromised in the verified, fresh registry (`REQUIRED_KEY_UNAVAILABLE`);
  - it requires the ledger's observed view to equal that registry
    (`BROKER_REGISTRY_VIEW_STALE`).
- **Why `issuedAt` alone is not the protection.** A retired key whose
  material survived could still produce backdated evidence.
  - For NEW_ADMISSION the protection is the ledger. `RESERVE` requires an
    `ISSUE` record in this ledger (`EVIDENCE_NOT_ISSUED_HERE`), so forged
    evidence cannot be reserved.
  - For history the protection is the full acceptance chain: owner
    assertion, L04 link, and consumed use.
  - Retirement also requires the predecessor's material to leave active
    custody (§8.4).
- **Registry-version effects** (CANONICAL, B1b-3a).
  - `key.registryVersion ≤ evidence.registryVersion ≤ registry.registryVersion`.
  - Registry evolution alone never invalidates evidence.
  - A key is judged by its record in the verified registry.
- **Stale registry rejection:**
  - a registry below the witness floor → `REGISTRY_DOWNGRADE`, which blocks
    issuance **and** historical reads;
  - a ledger view above the installed registry → `REGISTRY_DOWNGRADE`
    (`BELOW_BROKER_VIEW`);
  - an installed registry above the ledger view → `BROKER_REGISTRY_VIEW_STALE`.
- **There is no "delete the bad key from history" mechanism.** A compromised
  key is marked, never removed (§10).

## 7. Rotation

### 7.1 Two kinds of rotation

| Kind | Epoch | In-flight owner proofs | Triggered by |
| --- | --- | --- | --- |
| **In-epoch rotation** | unchanged | **preserved.** Predecessor evidence that was already `ISSUE`d in the ledger stays reservable and admissible in the same epoch, if it lies inside the predecessor's interval. B1b-3c §7: "a routine key rotation during an in-flight approval must not burn the owner's proof" | routine policy; a key lost without suspected exposure |
| **Epoch-advance rotation** | `counter + 1` | **burned by design.** PREPARED → `VOIDED_BY_RECOVERY`; RESERVED → `QUARANTINED_BY_RECOVERY`; E(n) evidence can never be reserved in E(n+1) | recovery (`RECOVERY_REASONS`); compromise (RR-6) |

Epoch-advance rotation is forced by B1b-3a: a key belongs to one epoch, and a
current key must be in the registry's epoch. It is specified in §9. This
section defines the shared state machine and the in-epoch path.

### 7.2 Single-current-key scope (PROPOSED profile rule, RR-3)

**Why the scope is not `(environment, authorityDomain)`.** Under the current
contracts, `authorityDomain` is the **logical** context field. It appears on
evidence only, and **never on key records**. B1b-3a's
`AuthorityKeyRecordV1` carries `signingDomain` instead. That is the field
the earlier B1b-3 design table called `authorityDomain` for keys.

A rule keyed on the logical `authorityDomain` cannot be expressed. One key
serves every logical authority context in its environment and signing
domain.

**Scope.** In one verified registry (one `environment`, one
`recoveryEpoch`), for each `(signingDomain, evidenceType)`:

> at most one current key whose `evidenceTypes` contains that
> `evidenceType`; and, in the DEV_SYNTHETIC profile, exactly one for
> `(OWNER_ACTOR, OWNER_MEMORY_OPERATION)` and none for
> `(PRIVACY, PRIVACY_ERASURE_AUTHORIZATION)` (B1b-3f not started).

Why the evidence type is included: the verifier accepts a key when its
`signingDomain` matches **and** `evidenceType ∈ key.evidenceTypes`, so
ambiguity is per evidence type. Today each signing domain has exactly one
evidence type (`EVIDENCE_TYPES_BY_DOMAIN`). The rule is therefore
equivalent to "one current key per `(environment, signingDomain)`". It is
stated per evidence type so that it stays correct if a domain gains a second
type. A key covering several types counts toward each.

This rule is a publication-time profile check (§10). The B1b-3a verifier
still structurally accepts several current keys, and B1b-3e does not change
it.

### 7.3 Cut-over is version and state based, not time based

**The authority cut-over is not `evidence.issuedAt`**, and no signer-chosen
time is used. Issuance authority moves from P to S in this sequence:

1. the K-ROOT-signed registry generation vN+1 names S as the single current
   key in scope and P as non-current;
2. witness freshness excludes vN;
3. independent verification confirms the signer's local issuance readiness
   for S (§7.5, `S_CURRENT`).

After that, the ledger's `ISSUE` operations (witness-anchored sequence)
decide what is issued. Before it, the hold blocks issuance.

**`t_cut` remains only as a record field value.** It is the `retiredAt` of P
and the `notBefore` of S in vN+1.

| Aspect | Answer |
| --- | --- |
| Owner | the owner, who chooses it when signing vN+1 with K-ROOT. It is part of the signed authority state |
| Used for | **historical interval verification only**: which P evidence lies inside `[notBefore, retiredAt)` |
| Not used for | issuance authority, readiness, or ordering. Those are version and state based |
| Selection rule (PROPOSED, RR-10) | `t_cut` is chosen after the hold is in force and the signer has stopped. It must be greater than the `issuedAt` of every P evidence recorded by an `ISSUE` in the witness-consistent ledger (read-only verifier). It must satisfy `t_cut ≤ vN+1.issuedAt` |
| Why that rule is safe | the values compared are ledger-recorded evidence that P legitimately issued while trusted. A forged P evidence carrying `issuedAt < t_cut` has no `ISSUE` record, so it can never be reserved. If P's material was exposed, P is `COMPROMISED` (C-1), and `t_cut` is then irrelevant |

Historical verification timing (`t_cut`) and current issuance authority (the
registry generation plus freshness plus readiness) are therefore never
conflated.

### 7.4 State machine

States are named for the successor **S**. The predecessor **P**'s state is
implied at each step.

```text
 P_ACTIVE ──(1)──▶ S_PROPOSED ──(2)──▶ S_PREPARED ──(3)──▶ S_AUTHORIZED ──(4)──▶ S_PUBLISHED ──(5)──▶ S_ACTIVATED ──(6)──▶ S_CURRENT
                       │ abort            │ abort             │ abort                  │ forward only                         (P_RETIRED)
                       ▼                  ▼                   ▼                        ▼
                   P_ACTIVE          destroy blob        never installed;       replace S by a
                                     (no history)        signed history only    later generation
```

| # | Transition | Caused by (state owner) | Precondition | Postcondition | Not implied |
| --- | --- | --- | --- | --- | --- |
| 1 | P_ACTIVE → S_PROPOSED | the **owner** decides (a transcript record, not authenticated, RR-13). **Host root** writes the local ceremony hold | `RESTORE_READY` under vN | the hold is present, so the signer refuses creating ops. P is still current, but not issuing | no authority change. The hold is not the owner's request (§9.1) |
| 2 | S_PROPOSED → S_PREPARED | **credential custody** (host root runs the reviewed successor-keygen CLI) | the hold is present; the successor slot is empty | the successor blob is in a slot **distinct from** the unit's (B1b-3d §13 "`.next.cred`"). Public material is recorded | **S cannot sign accepted authority.** It is in no registry (`KEY_UNKNOWN`), no unit loads it, and it is not journalled |
| 3 | S_PREPARED → S_AUTHORIZED | **the owner, offline, K-ROOT** signs vN+1. vN+1 names S current (`notBefore = t_cut`) and P `retiredAt = t_cut`. It passes the single-current-key rule and `verify_registry_succession(vN → vN+1)` | the public material from step 2 | **the authority registry state vN+1 exists** | **not witness execution.** vN is still fresh enough (the floor is still N), so both vN and vN+1 pass freshness. Nothing issues (hold). The ledger still names P |
| 4 | S_AUTHORIZED → S_PUBLISHED | **the recovery witness** accepts vN+1 as the new freshness state on host-root request: `RAISE_REGISTRY_FLOOR{vN+1}`, plus the head binding once it exists (§10.3). **Host root** then serves vN+1 | vN+1 verifies under K-ROOT at the current epoch and is a valid successor | vN is **stale** (`REGISTRY_DOWNGRADE`). vN+1 is the freshest registry the witness allows | **not an authority grant.** The authority came from step 3. The witness excludes staleness. **Not issuance readiness**: the ledger view is still N and names P → `BROKER_REGISTRY_VIEW_STALE` / `REQUIRED_KEY_UNAVAILABLE` |
| 5 | S_PUBLISHED → S_ACTIVATED | **credential custody** (host root) atomically moves S into the unit slot and destroys P's blob. **The signer** starts under the hold, runs the startup key-binding check (MC-1), journals `REGISTRY_VIEW{N+1,[S]}` as an observation, and asks the witness to record the ledger advance | step 4 is complete | **exact meaning:** *the signer has locally observed the fresh authorized state and reports itself ready to issue with S; this is not yet independently verified.* The hold is still in force | nothing is issued. `S_ACTIVATED` confers no authority and no permission |
| 6 | S_ACTIVATED → S_CURRENT | **the independent verifier** (stateless, root-run, read-only) confirms `RESTORE_READY`, the loaded-key binding, and the successor facts, and emits `AuthorityKeyTransitionV1`. **Host root** removes the hold on the owner's decision | step 5 is complete | issuance is **permitted**, and still one readiness-gated ledger op at a time | no dual-current issuance: the scope has one current key, one unit slot, and one journalled key |
| — | P_ACTIVE → P_RETIRED | **authority:** K-ROOT at step 3 (`retiredAt`). **Freshness:** effective for every verifier at step 4. **Custody:** material destroyed at step 5 | — | P evidence inside `[notBefore, t_cut)` stays valid | P is never current again: succession forbids reopening, and vN is stale |

**Are `S_ACTIVATED` and `S_CURRENT` redundant?** No. They differ by exactly
one boundary, `execution != verification`:

- `S_ACTIVATED` is the signer's own claim;
- `S_CURRENT` is that claim, independently verified, plus the release of the
  hold.

`S_ACTIVATED` is **not** an authority state. If the ceremony had no hold and
no independent verifier, the two would collapse into one. B1b-3e keeps the
verifier boundary, so both names stay, and only `S_CURRENT` permits
issuance.

### 7.5 What makes a key "current"

| Sense | Established by | Verified by |
| --- | --- | --- |
| **Authorized** | the K-ROOT-signed registry generation (step 3) | `verify_authority_registry` under the pinned root |
| **Fresh** | the witness freshness state (step 4). This is freshness of the registry state, not authority over the key | `witness_authority_context` → `REGISTRY_DOWNGRADE`, or `REGISTRY_HEAD_MISMATCH` once the head binding exists |
| **Current for verification** | a *verification result* only: the key is current in a registry that is both authorized and fresh | the B1b-3a verifier with the witness-derived context |
| **Issuance-ready** | the signer's local observation (step 5), independently verified (step 6) | readiness + the verifier CLI + MC-1 |

### 7.6 Rotation crash and failure handling

| Point | State left | Authority change | Allowed action |
| --- | --- | --- | --- |
| crash before successor preparation | `S_PROPOSED` | none | remove the hold, or continue |
| keygen succeeds; authorization never happens | `S_PREPARED` | none | destroy the successor blob. It was never in any registry, so it has no history |
| crash after signing vN+1, before the witness accepts it | `S_AUTHORIZED` | vN+1 exists as authority; freshness has not moved | have the witness accept it later, or abandon it. **Never sign a different vN+1** (§10.3) |
| crash after the witness accepts vN+1, before local observation | `S_PUBLISHED` | none further | forward only: complete step 5. If S's blob is lost, vN+2 revokes S (`ROUTINE`, zero S evidence proven) and names S′. Never return to P |
| crash after `REGISTRY_VIEW` is journalled, before the witness records the ledger advance | `LEDGER_AHEAD_OF_WITNESS` | none | fail closed. B1b-3c/3d resolve this **only by an epoch advance** (§9). The signer must not re-submit after restart, because that is indistinguishable from a restored witness |
| the verifier does not return `RESTORE_READY` | `S_ACTIVATED` | none | the hold stays; diagnose |

### 7.7 `AuthorityKeyTransitionV1` (PROPOSED record, not an authority)

This is the in-epoch sibling of `RecoveryEpochTransitionV1`. The verifier
produces it at step 6.

Fields:

- `schemaVersion`, `kind`, `environment`;
- `signingDomain`, `evidenceType`;
- `predecessorKeyId`, `successorKeyId`;
- `fromRegistry {version, digest}`, `toRegistry {version, digest}`;
- `recoveryEpoch` (unchanged);
- `witnessVersionBefore`, `witnessVersionAfter`, `ledgerSequence`;
- `tCut` (labelled `historicalIntervalOnly`);
- `predecessorIssuedEvidenceCount`, `maxPredecessorIssuedAt`;
- `inFlightEvidencePreserved: true`, `historicalEvidenceRetained: true`;
- `predecessorMaterialDestroyedFromActiveCustody` (limit in §8.4);
- `rollbackDetectionScope: LEDGER_ONLY`, `wholeHostRollbackProtected: false`.

## 8. Restore semantics

```text
RESTORE != AUTHORITY RESTORATION
```

**Restoring bytes never restores authority.** Authority exists only in a
K-ROOT-signed registry that current freshness accepts. Issuance exists only
when readiness passes against a surviving witness.

Restored bytes may be **adopted as state** only when a surviving freshness
owner already attests exactly those bytes. Even then they carry no authority
beyond what the witness attests.

### 8.1 Five kinds of restore

| Kind | Bytes | What they can do | What they can never do |
| --- | --- | --- | --- |
| **Data restore** | application DBs, L04 rows, memory files | serve as history, subject to the B2a/B1b-3c acceptance chain | be consulted by readiness; revive authority; block authority (B1b-3c §14) |
| **Broker / signer-state restore** | `authority_ledger.db`; the legacy `owner_control.db` is non-authoritative | be adopted if and only if its journal `sequence/head` equals the surviving witness's values; otherwise it is evidence only | reopen a terminal row (`TERMINAL_STATE_REOPENED`); revive a PREPARED challenge after an epoch advance (`LEDGER_EPOCH_STALE`); issue while behind the witness (`LEDGER_BEHIND_WITNESS`); turn a restored `REGISTRY_VIEW` into authority |
| **Registry restore** | an older signed `AuthorityRegistryV1` | nothing, if it is below freshness. Reinstating the retained **current** head is harmless: its authority came from K-ROOT, and its acceptance from freshness, not from the file | lift a retirement, revocation, or compromise (`REGISTRY_DOWNGRADE`); bring back a deleted record (§10) |
| **Credential restore** | an older `.cred` blob | nothing. DEV_SYNTHETIC forbids K-ACT and K-WIT backup and restore; loss means re-key (B1b-3d §16) | turn a retired key into an issuing key: the loaded-key binding fails (MC-1, `REQUIRED_KEY_UNAVAILABLE`) |
| **Authority restoration** | — | only through §9: an owner decision, a K-ROOT-authorized registry at a new epoch, witness execution, and independent verification | be performed by any restore of bytes, alone or combined |

### 8.2 Specific restore cases

| Case | Detected as | Outcome |
| --- | --- | --- |
| An old VM snapshot holds a once-valid K-ACT blob, and only the blob is extracted onto the current host | loaded-key binding ≠ the single current key → `REQUIRED_KEY_UNAVAILABLE`. The blob is not in the unit slot | no issuance. The blob decrypts (same host key), so the retired key's material is exposed again. See §8.4 and RR-7 |
| The whole VM boots from an old snapshot | **not detected.** Witness, ledger, registry, blob, and host key all come from the same time (B1b-3c §16, test-proven) | **unresolved** (§13) |
| The registry rolls back; the witness is current | `REGISTRY_DOWNGRADE` | issuance and historical reads are blocked. Reinstate the retained current head |
| The broker ledger rolls back; the witness is current | `LEDGER_BEHIND_WITNESS` (or `LEDGER_EPOCH_STALE` / `LEDGER_HEAD_MISMATCH`) | issuance is blocked; historical reads are allowed. Recovery: reinstate a preserved ledger equal to the witness (as in B1b-3d L7), or else advance the epoch |
| Ledger **and** registry roll back together; the witness is newer | `REGISTRY_DOWNGRADE` first, then `LEDGER_BEHIND_WITNESS` | blocked. Reinstate the current head, then advance the epoch from the **witness**, never from the stale ledger (`begin_recovery`) |
| Ledger and registry roll back to a **same-version fork** head; the witness is newer | V1: **not detected** by the floor. With the head binding: `REGISTRY_HEAD_MISMATCH` | §10.3 |
| The witness rolls back alone | `LEDGER_AHEAD_OF_WITNESS` | blocked, and historical reads are too (`_WITNESS_SUSPECT`). Advance the epoch. The witness's own history is its append-only chain (RR-9) |
| Every relevant owner rolls back together | not detected | **unresolved** |

### 8.3 Stale-epoch owner proof after a restore

A restored database flag is never authority:

- a `CONSUMED` challenge restored as `PREPARED` → `TERMINAL_STATE_REOPENED`
  (the journal is authoritative);
- a pre-advance `PREPARED` challenge is voided. Its owner assertion binds the
  old `ledgerEpoch`, so it can never be consumed or signed in the new epoch
  (`STALE_EPOCH_CHALLENGE`, `CHALLENGE_EPOCH_NOT_CURRENT`);
- old-epoch evidence can never be reserved (`STALE_EPOCH_EVIDENCE`), even
  when relabelled.

### 8.4 Host-bound credentials do not solve snapshot rollback

The live closure already records this: "Host-bound systemd credentials do
not, by themselves, solve whole-host or snapshot rollback." Any disk snapshot
of `lilith-dev-01` taken after L2a/L2b.2 holds both the K-ACT blob and
`credential.secret`. This record does **not** know whether any such snapshot
exists, because it made no live contact.

Therefore `predecessorMaterialDestroyedFromActiveCustody` means only that the
material was destroyed from the live credential store. It never means that
the key no longer exists.

**PROPOSED (RR-7).** Where retained material sits decides how it is treated:

- **Inside the owner/root boundary** — for example, a same-project snapshot
  that was never exported, which root could read anyway. This is the known
  Level 3 and whole-host debt.
- **Outside that boundary** — for example, exported, copied off the project,
  loaded by a unit that is not an authority unit, or seen by `lilith` or the
  deployer. This is **compromise**, and the key is marked `COMPROMISED`.

## 9. Recovery-epoch advancement protocol

```text
Owner Request  ->  Registry-root Authorize  ->  Recovery Witness Execute  ->  Independent Verify
   (intent)          (offline K-ROOT)            (freshness transition)          (verifier CLI)
```

| Boundary | Object | Owner | Is authority? |
| --- | --- | --- | --- |
| **Owner request** (intent) | **no authenticated contract exists.** The owner's decision is recorded in the owner's workstation ceremony transcript (§9.1, RR-13) | the owner | **no** |
| **Local ceremony hold** | the root-owned hold file. Its content, `CeremonyHoldV1` (PROPOSED), is a *local gating container*: `{kind, reason ∈ RECOVERY_REASONS, environment, observedWitnessDigest, observedRegistryVersion, createdAt}`. Every field is an unauthenticated description | host root | **no.** It only blocks creating ops |
| **Registry-root authorization** | the K-ROOT-signed `AuthorityRegistryV1` at `newEpoch = (witness.counter + 1, fresh random)`, with all of: `registryVersion > floor`; every E(n) key non-current; the §7.2 scope rule met; a valid successor under §10. This reuses the B1b-3d T-8 proposal, which the owner has not decided (RR-2) | the owner, offline | **yes: it is the first owner-authenticated object.** It permits one transition. It mutates nothing and does not advance the witness |
| **Witness execution** | witness `ADVANCE_EPOCH` → a successor `RecoveryWitnessV1` plus `chain/<v>.json` | the witness | **no.** It executes the freshness transition that step 2 authorized. The signed witness is a freshness receipt |
| **Resulting RecoveryEpoch** | `witness.currentRecoveryEpoch: RecoveryEpochV1`; `ledgerEpoch = "lep1." + epoch_digest(epoch, env)` | the witness (freshness) | no: it is the epoch the fresh authority must match |
| **Verification evidence** | `ReadinessResultV1 == RESTORE_READY`, `RecoveryEpochTransitionV1`, and the MC-1 key binding, from the root-run read-only verifier CLI | nobody (stateless) | no. It gates resumption (`execution != verification`) |

### 9.1 Owner request vs. local ceremony hold

- **The hold file is storage and ceremony gating.** Being root-owned does not
  make it owner intent. Host root, whether the owner's break-glass session or
  any root-equivalent principal (DR-3), can write it.
- **Its only effect fails safe.** While the hold is present, the signer
  refuses every creating op. That is destroy-only.
  - A forged hold costs availability only.
  - A removed hold grants nothing, because every creating op still needs
    `RESTORE_READY` against a fresh K-ROOT registry.
- **The owner's request has no cryptographic provenance today.** Two
  owner-held signing mechanisms exist, and both are deliberately **not**
  reused here:
  - K-ROOT has one signed artifact type, the registry.
  - The B1c activation SSH key serves activation.

  This pass creates no owner-signature scheme.
- The first owner-authenticated object in every transition is therefore the
  **K-ROOT-signed registry** itself.
- Whether an authenticated `OwnerTransitionRequest` is ever needed is RR-13.
  Candidates:
  - a new K-ROOT artifact type with its own separator;
  - owner WebAuthn;
  - no request object at all, because the registry already authorizes.

The previous draft's `AuthorityTransitionHoldV1`, described as the owner's
request, is withdrawn. It is renamed `CeremonyHoldV1` and is only a gating
container.

### 9.2 Ordering: decision C-4 (OWNER-ACCEPTED)

**Accepted:** the B1b-3c source succession semantics govern. The governing
order for all future implementation is the B1b-3c source order.

The B1b-3c source order (`begin_recovery`, then witness, then
`quarantine_pre_recovery`, then witness again, as tested in
`synthetic_b1b3c.py` `recover`):

1. **Ledger adoption record.** The signer journals `ADVANCE_EPOCH`. This is
   destroy-only (`creates_authority=False`). The new epoch is computed from
   the **pre-advance witness** (`witness.counter + 1`), and the op carries
   `fromWitnessDigest`. It is admitted only with a K-ROOT registry that
   verifies at the new epoch and is above the floor.
2. **Witness execution.** The witness records the new epoch together with the
   **post-journal** `ledgerSequence/ledgerHead`, and it must satisfy
   `witness_succession_reason`. This is the point of no return.
3. **Quarantine.** `VOID_CHALLENGE` / `QUARANTINE_USE` for older-epoch work
   (destroy-only).
4. **Witness again**, over the post-quarantine ledger.
5. **Independent verification** → `RESTORE_READY`. The hold is removed.

**SUPERSEDED FOR B1b-3e:** a part of the B1b-3d design. The B1b-3d design
§13 steps 7 and 9, and the §10 `ADVANCE_EPOCH {…restoredLedgerSequence,
restoredLedgerHead…}` operation, describe the reverse order:

- first, the witness advances with the *restored* sequence and head;
- then the signer "adopts" and calls `RECORD_LEDGER_ADVANCE`.

That order would violate the implemented B1b-3c checks:

- **Head check.** On an advance, `witness_succession_reason` requires a head
  that differs from the previous witness head (`WITNESS_LEDGER_REGRESSION`).
  An advance over an unrestored ledger would therefore be refused. Cases:
  compromise, rotation, and `LEDGER_AHEAD_OF_WITNESS` recovery.
- **Counter.** A post-advance `begin_recovery` would compute `counter + 2`.

**Status of that portion:** it is superseded for B1b-3e and for every future
implementation. The B1b-3d record is **not edited** and stays as history.
The witness owner operation is re-specified in B1b-3e-S (§15). It binds the
post-journal sequence and head that the ledger adoption record produced.

The ledger `ADVANCE_EPOCH` record is **not** authority and **not** witness
execution. A compromised or restored signer that journals it arbitrarily
causes a readiness failure only (`LEDGER_EPOCH_AHEAD_OF_WITNESS`), which means
availability loss.

**No live epoch advance is authorized.**

### 9.3 Epoch rules (CANONICAL)

| Rule | Source behaviour |
| --- | --- |
| Current epoch | `witness.currentRecoveryEpoch` |
| Requested next epoch | `(witness.counter + 1, fresh random)`, taken from the witness, never from a stale ledger |
| Monotonic counter | equal or `+1` (`WITNESS_EPOCH_NOT_SUCCESSOR`); never older (`WITNESS_EPOCH_REGRESSION`); the floor is strictly higher on an advance (`WITNESS_REGISTRY_MINIMUM_REGRESSION`) |
| Random / fork component | same counter with a different random = `FORKED` → `WITNESS_EPOCH_REGRESSION`, `LEDGER_EPOCH_FORKED`. The new random must differ from the current one (`RECOVERY_EPOCH_NOT_ADVANCING`). B1b-3d adds "never seen before", against the chain |
| Stale-epoch rejection | `LEDGER_EPOCH_STALE`, `STALE_EPOCH_CHALLENGE`, `STALE_EPOCH_EVIDENCE`, `CHALLENGE_EPOCH_NOT_CURRENT`; for NEW_ADMISSION, `RECOVERY_EPOCH_MISMATCH` |
| Replay rejection | an executed authorization cannot execute again: the counter is no longer `+1`, and the floor is not strictly higher. An older registry is stale |
| Authorization expiry | **none exists.** The registry has `issuedAt` but no `notAfter` (RR-2) |
| At most once | the witness chain is linear: `previousWitnessDigest`, `witnessVersion + 1`, `O_EXCL` chain files, one service instance plus `flock`. After a crash, the owner **reads** the witness instead of retrying blind |

### 9.4 Epoch-advance crash handling (under C-4)

| Crash after | Readiness | Allowed action | Authority change |
| --- | --- | --- | --- |
| the hold is written | issuance is held | remove the hold, or continue | none |
| the authorization is signed, not used | unchanged | use it later, or abandon it (no expiry, RR-2) | the authority state exists; freshness has not moved |
| the ledger `ADVANCE_EPOCH` is journalled; the witness has not executed | `LEDGER_EPOCH_AHEAD_OF_WITNESS` | witness execution with **the same** authorization. The journalled epoch equals the registry epoch, so this is completion, not a retry | none until the witness executes |
| the witness has executed (**point of no return**) | `NONTERMINAL_PRE_RECOVERY_WORK` until quarantine | finish the quarantine (destroy-only), then swap the credential | E(n) is stale. E(n+1) is not issuing yet |
| quarantine is journalled; the witness record is lost | `LEDGER_AHEAD_OF_WITNESS` | **another** epoch advance. This is safe by rule 2 and is the T-4 cost | none |
| `chain/<v>.json` is written; `witness.json` has not been renamed | the witness refuses writes (B1b-3d §18) | RR-9 | none |

## 10. Registry succession and freshness anchoring

### 10.1 `verify_registry_succession(previous, following)` (PROPOSED)

This is a pure function with a closed reason set. It adds **no** change to the
B1b-3a verifier and **no** signed field.

| Rule | Reason when violated |
| --- | --- |
| same `environment`; same `registryRootKeyId` (a root change needs a new anchor ceremony) | `SUCCESSION_ROOT_OR_ENVIRONMENT_CHANGED` |
| `following.registryVersion < previous.registryVersion` | `SUCCESSION_VERSION_REGRESSION` |
| `following.registryVersion == previous.registryVersion` with a different digest | `SUCCESSION_SAME_VERSION_FORK` (only meaningful when `previous` is the **trusted** prior head, §10.3) |
| `following.registryVersion != previous.registryVersion + 1`, when not equal (RR-4: whether gaps are allowed) | `SUCCESSION_VERSION_GAP` |
| `following.issuedAt ≥ previous.issuedAt` | `SUCCESSION_TIME_REGRESSION` |
| epoch equal, or `NEWER` with `counter + 1` | `SUCCESSION_EPOCH_INVALID` |
| every previous `keyId` is present | `SUCCESSION_RECORD_REMOVED` |
| per record, immutable: `signingDomain`, `evidenceTypes`, `environment`, `algorithm`, `publicKey`, `createdAt`, `notBefore`, `recoveryEpoch`, `policyVersion`, `registryVersion` | `SUCCESSION_RECORD_MUTATED` |
| `retiredAt`: `null → t` only | `SUCCESSION_LIFECYCLE_REOPENED` |
| `revokedAt`/`revocationReason`: `null → (t, reason)` only. The only permitted later change is `ROUTINE`/`SUPERSEDED` → `COMPROMISED` with `revokedAt` unchanged and `compromisedSince ≤ revokedAt` (RR-8) | `SUCCESSION_LIFECYCLE_REOPENED` |
| `COMPROMISED` never changes back | `SUCCESSION_COMPROMISE_CLEARED` |
| a non-current record never becomes current | `SUCCESSION_LIFECYCLE_REOPENED` |
| new records carry `registryVersion == following.registryVersion` | `SUCCESSION_NEW_RECORD_VERSION` |
| profile: the §7.2 single-current-key scope | `SUCCESSION_CURRENT_KEY_SCOPE` |

**Limit.** The function verifies only the two inputs it is given. It proves
additive history *between those inputs*. It does **not** establish durable
fork protection or rollback protection. Those depend entirely on who
supplies `previous` (§10.2).

### 10.2 Who owns the trusted prior registry head

| Source of `previous` | Trusted? | What succession then proves |
| --- | --- | --- |
| the retained registry directory (root-owned files) | **no**: it can be restored or rolled back with the registry | internal consistency of the retained chain only |
| the signer ledger journal (a `registryDigest` in `REGISTRY_VIEW` / `ADVANCE_EPOCH`) | **no**: it can be restored, and **no verifier consults it**. `witness_authority_context` takes its trusted inputs "from the verified witness and nowhere else". Historical reads continue under `LEDGER_BEHIND_WITNESS` without any ledger check | local consistency while the ledger survives. It is kept only as a local cross-check |
| **the recovery witness** (proposed head binding, §10.3) | **yes**, in the ledger-only threat model, while the witness survives | fork and rollback detection across registry + ledger rollback |
| an off-host / owner-held anchor | not designed (RR-12) | whole-host |

The trusted prior head is therefore owned by the **recovery witness
boundary**, which is the existing freshness owner. No new service is
proposed.

### 10.3 Same-version fork anchoring (PROPOSED; exact schema is RR-4)

**Problem.** `RecoveryWitnessV1` carries only `minimumRegistryVersion`. Floor
semantics (`registryVersion ≥ floor`) cannot tell these two apart:

- `(vN, digest A)`;
- `(vN, digest B)`.

Nor can they exclude any `vN+k` that K-ROOT signed but that was never
accepted as fresh. The previous draft proposed a `registryDigest` only in
the restorable broker journal. That is **withdrawn as a fork-detection
claim**, for the reasons in §10.2.

**Minimum required property:**

> The canonical registry head `(registryVersion, registryDigest)` is bound
> in the surviving freshness state owner. Every verification context derived
> from it requires the verified registry's digest to equal the bound head
> digest, and not merely its version to be at or above the floor.

Until this exists, B1b-3e **does not claim** same-version fork detection
across a registry or ledger rollback.

**`RecoveryWitnessV1` is not silently mutated.** Adding a field would change
its signed bytes, its separator semantics, and the B1b-3c vectors. Two
proposals, with the choice left to the source slice:

| Option | Shape | Pros | Cons |
| --- | --- | --- | --- |
| **A. `RecoveryWitnessV2`** (recommended) | a new schema version, with `registryHead {version, digest}` added (or replacing `minimumRegistryVersion`), a new separator, `witness_authority_context_v2` requiring the head digest, and V2 succession rules: the head changes only by a valid `verify_registry_succession` step, and the same version never has a different digest | one chain and one succession function. Freshness stays in exactly one signed object | V1 → V2 migration at bootstrap (nothing is live, so this is a bootstrap choice). New vectors |
| B. `RegistryHeadBindingV1` | a separately versioned artifact signed by K-WIT with its own separator, chained to the witness digest `{witnessDigest, registryHead}` | V1 is untouched | two artifacts that must stay mutually consistent; more crash states; the same key and boundary anyway |

Either option keeps the witness in the same boundary and key, K-WIT. Neither
makes the witness an authority, because the head is a **freshness pointer** to
a K-ROOT-signed registry. The witness cannot author registry content.

Whole-host rollback of witness + registry + ledger together stays
**unresolved** under both options.

## 11. Ledger state machine

These transitions are enforced by `synthetic_recovery_ledger._step`
(IMPLEMENTED, TEST). They are made durable with triggers by the B1b-3d schema
(designed, not provisioned).

**Challenge:**

```text
 (absent) ── PREPARE (ready; current ledgerEpoch) ──▶ PREPARED
 PREPARED ── CONSUME (ready; current epoch) ────────▶ CONSUMED ── ISSUE (ready; once) ──▶ CONSUMED + evidence
 PREPARED ── EXPIRE / CANCEL / FAIL ────────────────▶ EXPIRED | CANCELLED | FAILED
 PREPARED ── VOID_CHALLENGE (older epoch only) ─────▶ VOIDED_BY_RECOVERY
```

**Evidence use:**

```text
 (absent) ── RESERVE (ready; issued here; digest; issuing == claimed == current epoch; unused) ──▶ RESERVED
 RESERVED ── CONFIRM (ready; current epoch) ──────────────▶ CONSUMED
 RESERVED ── ABANDON ─────────────────────────────────────▶ ABANDONED
 RESERVED ── QUARANTINE_USE (older epoch only) ───────────▶ QUARANTINED_BY_RECOVERY
 QUARANTINED_BY_RECOVERY ── RECONCILE_DECISION ───────────▶ ABANDONED   (B1b-3d §14; designed)
```

**Ledger-global** (local observations, never authority):

```text
 GENESIS (seq 0 only)
 REGISTRY_VIEW   (version strictly up; sets the observed signingKeyIds)  — local observation
 ADVANCE_EPOCH   (counter strictly up; registry strictly up)             — local adoption record (C-4 step 1)
```

### 11.1 `REGISTRY_VIEW` classification

`REGISTRY_VIEW` is **broker/ledger state**. It records which fresh,
authorized registry the signer has observed, and which journalled signing
key set it intends to use from it.

```text
REGISTRY_VIEW != authority
REGISTRY_VIEW != registry-root authorization
REGISTRY_VIEW != witness execution
```

- It is classified only as a **local issuance-readiness observation**,
  recorded **after** the authoritative state has been verified
  independently: K-ROOT signature plus witness freshness.
- It is non-creating in source (`record_registry`,
  `creates_authority=False`).
- It can only **narrow** issuance. Readiness re-derives everything from the
  authoritative inputs:
  - `journal.registry_view == verified registry version`, where the registry
    is verified under K-ROOT and fresh under the witness;
  - `journalled signingKeyIds ⊆ current, uncompromised keys` in *that*
    registry.

A compromised or restored broker that writes `REGISTRY_VIEW` naming a key
that the fresh K-ROOT registry does not authorize gets
`REQUIRED_KEY_UNAVAILABLE`, `BROKER_REGISTRY_VIEW_STALE`, or
`REGISTRY_DOWNGRADE`. It **cannot make a successor authoritative**. The worst
case is availability loss.

**Missing contract (MC-1, RR-14).** Readiness checks the *journalled* key IDs
against the registry. **No contract binds the key actually loaded by the
signer.** B1b-3d §18 designs a startup fingerprint check, but it has no
input or result contract, and `evaluate_restore_readiness` has no
loaded-key input.

Issuance readiness therefore needs one more input, a
`SignerKeyBindingObservation {loadedPublicKeySha256, keyId}`. It must be
checked equal to the single current key in scope (§7.2). The independent
verifier must reproduce it, for example from the `HEALTH` `publicKeySha256`
(L2 U5).

The schema is left to the source slice. `REGISTRY_VIEW` is **not** given any
authority semantics to fill this gap.

### 11.2 Required rules

| Rule | Mechanism |
| --- | --- |
| PREPARED may be voided | `VOID_CHALLENGE`, older `ledgerEpoch` only, destroy-only. In-epoch: `CANCEL` / `EXPIRE` / `FAIL` |
| CONSUMED never reopens | no transition leaves `CONSUMED`; rows showing otherwise → `TERMINAL_STATE_REOPENED`; triggers forbid terminal edits |
| CONSUMED is never reusable | a second `ISSUE` → `EVIDENCE_ALREADY_ISSUED`; a second `RESERVE` → `EVIDENCE_ALREADY_USED` |
| A stale epoch is rejected | `CHALLENGE_EPOCH_NOT_CURRENT`, `STALE_EPOCH_CHALLENGE`, `STALE_EPOCH_EVIDENCE`, `STALE_EPOCH_RESERVATION` |
| An old epoch never becomes current | `ADVANCE_EPOCH` requires `counter > current`; witness succession forbids regression and forks |
| History is additive | append-only, hash-chained journal; terminal rows kept; nothing deleted by recovery or reconciliation |
| Restore → replayable owner proof | impossible (§8.3) |

**Forbidden:**

- `CONSUMED → PREPARED`;
- `CONSUMED → reusable`;
- any transition out of a terminal state;
- `QUARANTINED_BY_RECOVERY → RESERVED / CONSUMED`;
- `ADVANCE_EPOCH` to an older or forked epoch;
- `REGISTRY_VIEW` to a version that is lower or equal;
- any journal op that grants authority.

## 12. Failure matrix

Every row reports `rollbackDetectionScope: LEDGER_ONLY` and
`wholeHostRollbackProtected: false`. None of it is live until B1b-3d L3a–L4
exist.

| # | Failure | Authoritative state owner | Allowed recovery action | Authority changes? | Historical evidence changes? | Fail-closed behaviour |
| --- | --- | --- | --- | --- | --- | --- |
| F1 | crash before successor preparation | the owner decides; the hold is local gating | remove the hold, or continue | no | no | creating ops refused while the hold is present |
| F2 | crash after successor preparation | credential custody | destroy the unpublished successor blob, or continue | no | no | S is in no registry, not loadable, and not journalled |
| F3 | crash after registry authorization (vN+1 signed; the witness has not accepted it) | registry root (authority); witness (freshness still N) | have the witness accept it later, or abandon it. Never sign a second vN+1 | the vN+1 authority state exists; nothing issues | no | the hold is present; the ledger names P |
| F4 | crash after the witness accepts vN+1 (or executes an epoch advance) | witness (freshness) | forward only: step 5 (in-epoch), or quarantine and swap (epoch) | P is no longer fresh / E(n) is stale | no (retirement preserves intervals) | `BROKER_REGISTRY_VIEW_STALE`, `REQUIRED_KEY_UNAVAILABLE`, or `NONTERMINAL_PRE_RECOVERY_WORK` |
| F5 | crash after registry publication, before local observation | witness + ledger | complete step 5 | no | no | no issuance: the ledger view is stale |
| F6 | stale authorization replay | witness | none needed | no | no | `REGISTRY_DOWNGRADE`; floor not strictly higher; counter not `+1` |
| F7 | old credential restored (blob only) | registry + loaded-key binding (MC-1) | leave it unloaded. RR-7 decides whether this is a compromise | no | no, unless RR-7 → `COMPROMISED` (then retroactive for that key, C-1) | `REQUIRED_KEY_UNAVAILABLE` |
| F8 | old registry restored | witness | reinstate the retained current head | no | no | `REGISTRY_DOWNGRADE`: issuance **and** historical reads blocked |
| F9 | old broker ledger restored | witness | reinstate a preserved ledger equal to the witness, or else advance the epoch | only through an epoch advance | no | `LEDGER_BEHIND_WITNESS` / `LEDGER_EPOCH_STALE` / `LEDGER_HEAD_MISMATCH` |
| F10 | old registry + old ledger restored, witness survives | witness | reinstate the current head, then advance the epoch from the witness | only through an epoch advance | no | `REGISTRY_DOWNGRADE`, then `LEDGER_BEHIND_WITNESS` |
| F11 | whole-host rollback | **no owner survives** | none. The owner must distrust the host from out-of-band knowledge | **undetected**: stale authority may revive | undetected | **not fail-closed**: `RESTORE_READY` on the old state (B1b-3c §16) |
| F12 | compromised old key | registry root | vN+1 marks it `COMPROMISED`. If it was the issuing key, advance the epoch (RR-6) | yes: the key is dead | **yes**: all of its evidence → `KEY_COMPROMISED` (C-1) | `REQUIRED_KEY_UNAVAILABLE` if it was journalled |
| F13 | routine retirement | registry root → witness → ledger → verifier | in-epoch rotation (§7) | S replaces P after `S_CURRENT` | no (`RETIRED_AFTER_ISSUANCE`) | no issuance from step 1 to step 6 |
| F14 | successor key lost before activation | registry root | vN+2 revokes S (`ROUTINE`, zero S evidence proven) and names S′ | no | no | S cannot issue |
| F15 | successor key lost after activation | registry root + ledger | destroyed without exposure → retire S and rotate to S′. Exposure unknown or confirmed → `COMPROMISED` plus an epoch advance | S is replaced | retirement: no. Compromise: yes, for S's evidence | the unit fails on a missing credential |
| F16 | same-version registry fork (two K-ROOT-signed vN) | witness head binding (§10.3, proposed) | refuse the fork; treat it as a K-ROOT operational incident | no, if detected | no | **V1: not detected** by floor semantics. With the head binding: `REGISTRY_HEAD_MISMATCH` |
| F17 | crash between a ledger commit and the witness record | witness | advance the epoch | only through an epoch advance | no | `LEDGER_AHEAD_OF_WITNESS` |
| F18 | compromised or restored broker writes `REGISTRY_VIEW` / `ADVANCE_EPOCH` | registry root + witness | ignore it; re-derive readiness from the authoritative inputs | **no** | no | `REQUIRED_KEY_UNAVAILABLE` / `BROKER_REGISTRY_VIEW_STALE` / `LEDGER_EPOCH_AHEAD_OF_WITNESS` |
| F19 | root-equivalent principal forges or removes the hold | readiness | treat as a ceremony incident | no | no | a forged hold → availability loss. A removed hold → creating ops still need `RESTORE_READY` |

## 13. Security boundaries and unresolved risks

### Security boundaries

| Actor | Can | Cannot |
| --- | --- | --- |
| Owner with K-ROOT (workstation) | authorize registry generations and epoch advances | execute anything on the host without a host-root session |
| Host root (owner break-glass, or root-equivalent under DR-3) | request witness freshness ops; install files; run ceremonies; write or remove the hold. At Level 3: read runtime credentials and forge the witness with K-WIT | authorize a registry generation or an epoch advance (that needs K-ROOT). Root custody is not owner authorization |
| `lilith-authority-dev` (signer uid) | journal ledger ops, including observations; submit `RECORD_LEDGER_ADVANCE` | change the epoch, the floor, or the head; rewrite the witness; make any key authoritative. Worst case: availability loss |
| `lilith-recovery-witness` | sign witness successors (freshness) | sign evidence or registries (`WITNESS_KEY_IS_AUTHORITY_KEY`); author registry content; read the ledger or K-ACT |
| `lilith`, Hermes, the model, the routine deployer | nothing in this record | request, authorize, execute, or verify any transition |

### Unresolved risks

1. **Whole-host or whole-snapshot rollback (OPEN).** No independent
   surviving state owner is introduced. The anchors listed in B1b-3c §16 are
   all still unselected (RR-12).
2. **Compromise is retroactive (C-1, accepted).** A leaked key erases the
   historical validity of all of its evidence until re-attestation exists.
3. **Retained key material in snapshots** (§8.4, RR-7).
4. **Same-version registry fork** (F16) until the head binding exists
   (RR-4).
5. **No authorization expiry** (RR-2).
6. **Per-transition witnessing cost** (T-4). Some crashes escalate to an
   epoch advance.
7. **No binding contract for the loaded key** (MC-1, RR-14).
8. **No authenticated owner request** (RR-13). The hold is only gating.
9. **DR-3** (`ubuntu` is root-equivalent) and Level 3 remain OPEN.

## 14. Explicit non-claims and out of scope

B1b-3e does **not** claim, design, or authorize any of the following:

- PROD authority, or closure of `CROSS_ENVIRONMENT_PROD_AUTHORITY_DEBT`;
- real-owner-grade key custody, or a real registry root;
- First Memory, or any accepted-memory transition;
- signer activation, an activation grant, or witness installation;
- Privacy key custody, or a Privacy boundary source (B1b-3f);
- WebAuthn ceremony, RP, or authenticator changes;
- a Stage III retry or arm;
- a whole-host rollback solution;
- memory zeroization, or remanence elimination;
- consciousness, personhood, or identity claims about LILITH;
- automatic authority recovery from backups (none exists);
- a new owner-signature scheme;
- any live mutation, key generation, rotation, revocation, restore, epoch
  advance, or ceremony.

## 15. Proposed follow-on source slice (B1b-3e-S, TEST-only)

This slice is not authorized by this record. It lives under
`services/owner-memory-control/` and `services/authority-dev/`, and nothing
goes under `services/core-api/**` or `services/memory-broker/`.

It depends on these decisions: RR-3, RR-4, RR-5a, RR-10, and RR-14
(`BLOCKING_BEFORE_3E_SOURCE`, §16).

1. `verify_registry_succession` (§10.1), with golden vectors and a negative
   matrix covering:
   - a removed record;
   - a rewritten record;
   - a version regression;
   - a same-version fork against a trusted head;
   - a version gap;
   - an epoch that is not a successor;
   - a reopened lifecycle;
   - a cleared compromise;
   - the `ROUTINE → COMPROMISED` escalation;
   - two current keys in scope.
2. The freshness head binding, as `RecoveryWitnessV2` or
   `RegistryHeadBindingV1` (RR-4), with its own vectors. The V1 vectors and
   SHA-256 pins stay unchanged.
3. The single-current-key scope check (§7.2), as a profile rule. The B1b-3a
   verifier is unchanged.
4. In-epoch rotation in the TEST ledger model, with `REGISTRY_VIEW` as an
   observation only. It needs a test for every §7.6 crash point, and for
   F18.
5. The MC-1 loaded-key binding input to profile readiness (RR-14).
6. The C-4 governing order, tested against `witness_succession_reason`,
   including an advance over a **current**, unrestored ledger. The witness
   owner op is re-specified to bind the post-journal sequence and head.
7. The `CeremonyHoldV1` schema (a gating container) and
   `AuthorityKeyTransitionV1`.
8. Pins: the B2a, B1b-3a, B1b-3b, and B1b-3c golden files and their SHA-256
   pins stay unchanged.

A **live** rehearsal (B1b-3e-L) has three prerequisites:

- B1b-3d L3a–L4 are live and accepted;
- the `BLOCKING_BEFORE_LIVE_3E` decisions are resolved;
- a separately authorized ladder with one mutation per step exists.

It is not designed here.

## 16. RR-2 through RR-14 (owner decisions; recommendations are not decisions)

Classification:

- `BLOCKING_BEFORE_3E_SOURCE`: needed before the B1b-3e-S tests can be
  written without rework.
- `BLOCKING_BEFORE_LIVE_3E`: needed before any live rehearsal.
- `DEFERABLE`: neither.

| # | Exact question | Current proposed / default | Alternatives | Consequences | Class | Recommendation (why) |
| --- | --- | --- | --- | --- | --- | --- |
| RR-2 | Is the K-ROOT-signed registry at the new epoch sufficient epoch-advance authorization, or is a separate owner-signed `EpochAdvanceAuthorization` needed, binding the predecessor witness digest, the reason, and a `notAfter`? | the registry is the authorization (B1b-3d T-8 proposal; not an owner decision) | (a) registry only; (b) a new K-ROOT artifact type with its own separator; (c) registry plus a `notAfter` convention outside the signed bytes | (a) no expiry; not bound to the predecessor random; replay bounded by witness succession. (b) exact binding and expiry, but a new signed contract and a second K-ROOT artifact type. (c) not enforceable | `BLOCKING_BEFORE_LIVE_3E` | (a) for DEV_SYNTHETIC, because witness succession already rejects replay and forks. Revisit (b) before any real authority |
| RR-3 | Must a registry have exactly one current key per `(environment, signingDomain, evidenceType)` (§7.2)? | exactly one for OWNER_ACTOR in the profile | (a) exactly one; (b) at most two during a bounded overlap; (c) no rule (B1b-3a as is) | (a) no dual-current ambiguity, but a hold-based cut-over. (b) issuance-free rotation, but an ambiguous "which key issues" and a more complex state machine. (c) ambiguity is left to signer configuration | `BLOCKING_BEFORE_3E_SOURCE` | (a): it makes S_CURRENT unambiguous. In-flight proofs are still preserved by interval semantics |
| RR-4 | Where, and in which schema, is the canonical registry head `(version, digest)` bound? Are version gaps allowed? | the witness boundary, in a new schema version; no gaps | (a) `RecoveryWitnessV2`; (b) `RegistryHeadBindingV1` under K-WIT; (c) journal digest only; (d) owner discipline only | (a) one chain, fork detection while the witness survives, new vectors. (b) same detection, two artifacts to keep consistent. (c)/(d) **no** fork detection across ledger rollback | `BLOCKING_BEFORE_3E_SOURCE` | (a), with no gaps: freshness stays in one signed object, and a complete retained chain is checkable |
| RR-5 | Epoch-advance ordering | **resolved by owner decision C-4**: the B1b-3c order governs | — | — | resolved | — |
| RR-5a (residual of C-4) | Which actor journals the ledger `ADVANCE_EPOCH` before witness execution, and with which credential loaded? | the signer, under the hold, with the old credential still loaded (destroy-only op) | (a) the signer under the hold; (b) a root offline tool on the stopped DB; (c) the signer started with no credential slot | (a) keeps the ledger single-writer. The old key is loaded but refused by the hold. (b) breaks the ledger's owner. (c) needs a unit variant without `LoadCredentialEncrypted` | `BLOCKING_BEFORE_3E_SOURCE` | (a): no new writer. Creating ops are refused by the hold and by readiness |
| RR-6 | Does compromise of the issuing key force an epoch advance (`KEY_COMPROMISE`)? | yes | (a) always; (b) only if ledger tampering is suspected; (c) never; rotate in-epoch | (a) in-flight proofs are burned, and any work the attacker touched is voided. (b) needs a judgement the system cannot make. (c) PREPARED work touched by the attacker survives | `BLOCKING_BEFORE_LIVE_3E` | (a): fail closed. A compromise usually implies the signer uid |
| RR-7 | Is retained or restored key material a compromise? | inside the owner/root boundary: known debt. Outside it: compromise | (a) the boundary rule; (b) any retained copy is a compromise; (c) never | (a) matches the Level 3 debt already carried. (b) every snapshot kills all history (C-1). (c) leaked keys stay trusted | `BLOCKING_BEFORE_LIVE_3E` | (a): honest about the existing trust boundary |
| RR-8 | `compromisedSince ≤ revokedAt` when compromise follows a routine revocation | accept an imprecise forensic field in V1 | (a) accept; (b) a new key-record version | (a) the verdict is correct and the forensics imprecise. (b) contract churn | `DEFERABLE` | (a): the verdict is unaffected (C-1) |
| RR-9 | Witness crash between the `chain/<v>` write and the `witness.json` rename | roll forward only to a verified signed chain successor; otherwise break-glass | (a) roll forward; (b) always refuse (break-glass); (c) roll back to `witness.json` | (a) automatic, bounded completion. (b) availability cost. (c) **unsafe**: it discards a signed successor | `BLOCKING_BEFORE_LIVE_3E` | (a): the chain is the append-only record |
| RR-10 | Which lifecycle fields and reasons does rotation use, and how is `t_cut` chosen? | `retiredAt` for rotation; `ROUTINE` for lost or unused keys; `SUPERSEDED` unused. `t_cut` from the witness-consistent ledger's `ISSUE` records (§7.3), historical use only | (a) as proposed; (b) `SUPERSEDED` for rotation; (c) `t_cut` = hold time | (a) matches the B1b-3c recovery ceremony. (b) the verifier treats it the same, but the audit narrative differs. (c) relies on clocks | `BLOCKING_BEFORE_3E_SOURCE` | (a) |
| RR-11 | Release-set and keygen contract for a successor credential slot | a new reviewed release; defined with B1b-3e-L | (a) a new release plus a successor keygen form; (b) reuse the L2b keygen | (a) reviewable. (b) impossible: it refuses a non-empty credstore, and `RELEASE_SET` is initial-custody only | `BLOCKING_BEFORE_LIVE_3E` | (a) |
| RR-12 | An owner-held checkpoint as the first whole-host anchor | not selected | (a) an owner-held last-witness digest; (b) an off-host witness; (c) a hardware counter; (d) none yet | (a) detection only at the next owner check. (b) a new trust dependency. (c) vTPM coupling | `DEFERABLE` | (d) for now; (a) first when whole-host protection becomes required |
| RR-13 (new) | Does an owner transition request need authenticated provenance? | none; the K-ROOT registry is the first authenticated object | (a) none; (b) a new K-ROOT artifact type; (c) owner WebAuthn over the request | (a) intent lives only in transcripts. (b)/(c) are new signature schemes, out of scope for this pass | `DEFERABLE` (DEV_SYNTHETIC) | (a) for DEV_SYNTHETIC. Revisit with RR-2 before real authority |
| RR-14 (new) | Contract for binding the signer's loaded key to the single current key (MC-1) | missing; required | (a) a profile readiness input plus verifier reproduction; (b) keep the startup check without a contract | (a) testable and independently verifiable. (b) the loaded key is unverified by any contract | `BLOCKING_BEFORE_3E_SOURCE` | (a) |

Carried forward unchanged:

- B1b-3c open decision 3: the off-host anchor;
- B1b-3c open decision 5: witness write frequency (T-4 kept);
- B1b-3c open decision 6: reconciliation;
- B1b-3c open decision 7: the Privacy boundary (B1b-3f);
- B1b-3d T-6 (the reboot test) and T-9 (`ubuntu`).

## 17. Owner-accepted decisions and review history

| Decision | Result |
| --- | --- |
| **C-1: compromise** (was RR-1) | **ACCEPTED: the current B1b-3a source semantics.** `COMPROMISED` → `KEY_COMPROMISED` for all evidence from that key, including evidence that claims `issuedAt < compromisedSince`. Routine retirement and non-compromise revocation keep their interval rules. Pre-compromise survival is deferred until an unforgeable timestamp, admission-time attestation, or re-attestation contract exists. The B1b-3a source is unchanged |
| **C-4: epoch-advance order** (was RR-5) | **ACCEPTED: the B1b-3c source succession semantics govern.** The B1b-3d §13 steps 7 and 9 and the §10 `ADVANCE_EPOCH` shape are **superseded for B1b-3e** (§9.2). The B1b-3d record is not edited. No live epoch advance is authorized |

**Second review pass: corrections to the first draft (`fff4ea2`):**

- **Witness vs. authority.** "Verification-current = floor raise" and "the
  witness owns the effective registry" are withdrawn. The witness owns
  freshness only, and "current for verification" is a combined verification
  result (§4, §7.5).
- **`REGISTRY_VIEW` vs. authority.** "Issuance-current = witnessed
  `REGISTRY_VIEW`" is withdrawn. `REGISTRY_VIEW` is a local observation, and
  the missing loaded-key contract MC-1 is identified (§11.1).
- **Fork detection via the journal.** The claim that a journal
  `registryDigest` detects same-version forks is withdrawn. Detection needs a
  head binding at the freshness owner (§10.3).
- **Hold vs. owner request.** `AuthorityTransitionHoldV1` "as the owner's
  request" is withdrawn. It is now `CeremonyHoldV1`, a gating container only
  (§9.1).
- **Cut-over.** The cut-over is now version and state based. `t_cut` is
  restricted to historical interval use (§7.3). The single-current-key scope
  is defined (§7.2).
- **State machine.** Every transition names its causing owner.
  `S_ACTIVATED` and `S_CURRENT` are distinguished only by independent
  verification (§7.4).

## 18. Acceptance criteria for design closure

1. §1 is correct: K-ACT is custody only, and no registry, witness, or ledger
   is live.
2. The authority / freshness / readiness / storage separation (§1, §4) is
   accepted.
3. C-1 and C-4 are recorded as accepted (§17).
4. The §7.2 scope and the §7.3 cut-over rule are accepted, and RR-3 and
   RR-10 are decided.
5. The §7.4 state machine and its owners are accepted.
6. The §10 succession function, its stated limit, and the witness-boundary
   ownership of the trusted head are accepted, and RR-4 is decided.
7. The §11.1 `REGISTRY_VIEW` classification is accepted, and RR-14 is
   decided.
8. The §9.1 hold vs. request separation is accepted.
9. The §8 restore taxonomy is accepted without exception.
10. The §12 matrix is accepted, with F11 and F16 acknowledged as not
    fail-closed (F16 until the head binding exists).
11. The §14 non-claims are unchanged.
12. All remaining `BLOCKING_BEFORE_3E_SOURCE` items are decided before
    B1b-3e-S begins.

## Explicitly not done

- No DEV or PROD contact. No gcloud, SSH, IAP, systemctl, systemd-creds, or
  sudo.
- No key, credential, registry, witness, ledger, or blob was generated,
  rotated, revoked, restored, encrypted, decrypted, installed, or activated.
- No change to source, tests, golden vectors, workflows, IAM, WIF, sudoers,
  the broker runtime, Stage III, or activation.
- No edit of the B1b-3a, B1b-3c, or B1b-3d records. The superseded B1b-3d
  portion is recorded here only (§9.2).
- No claim of real authority, real-owner custody, First Memory, same-version
  fork detection, or whole-host rollback protection.
