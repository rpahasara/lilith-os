# Slice 15B2b-B1b-3e — Rotation, Revocation, Restore, and Recovery Semantics

Status:

- **DESIGN RECORD**
- **NOT IMPLEMENTED**
- **NOT LIVE**
- **NO LIVE MUTATION AUTHORIZED**
- **WHOLE-HOST ROLLBACK UNRESOLVED**
- **REAL AUTHORITY ABSENT**

Base: protected main `069f6d1861b79d817f8b959e36b53f017bfbac32`.

This is the fifth sub-slice of the
[B1b-3 custody isolation design](slice-15b2b-b1b3-custody-isolation-design.md).
It follows the [B1b-3d live closure](slice-15b2b-b1b3d-live-closure.md). It
builds on these records:

- [B1b-3a](slice-15b2b-b1b3a-authority-registry-contracts.md): registry, key
  record, and evidence contracts;
- [B1b-3c](slice-15b2b-b1b3c-recovery-epoch-witness.md): recovery epoch,
  witness, ledger, and readiness;
- the [B1b-3d design](slice-15b2b-b1b3d-dev-synthetic-custody-design.md):
  DEV_SYNTHETIC custody, witness service, ceremony, and ledger schema.

It is a design and source-review record only. It is not an acceptance record,
an implementation authorization, a ceremony runbook, or an activation
instruction. It does **not** mark any of the following as complete:

- B1b-3;
- Level 2 isolation;
- real owner authority;
- First Memory;
- Privacy custody;
- Stage III.

No DEV, PROD, IAM, WIF, systemd, key, credential, registry, witness, ledger,
broker, or Stage III state was contacted or changed. No source, test, vector,
workflow, or contract was changed.

Labels are used as in the B1b-3 records:

- **CANONICAL**: defined by accepted records or protected-main source.
- **IMPLEMENTED**: present in source (TEST) or in installed state.
- **LIVE**: installed on DEV per the B1b-3d live closure.
- **PROPOSED**: a recommendation of this record. It still needs review and a
  separately authorized source slice.
- **CONFLICT**: this task's brief and the repository differ. The repository
  contract is kept, and the difference is left as an explicit decision (§16).

## 1. Scope and current live baseline

B1b-3e defines what these words mean for LILITH authority:

- **rotation**: an authority key is replaced by a successor;
- **revocation**: a key stops being usable for new evidence;
- **restore**: bytes return from an older state;
- **recovery**: authority resumes after a restore or fault.

The authority story is kept separate from the causal and storage story. That
bytes exist, were restored, or were published never by itself decides
whether authority exists.

**Current live DEV state** (from the
[live closure](slice-15b2b-b1b3d-live-closure.md) §4 and §6), relevant here:

| Artifact | Live? |
| --- | --- |
| K-ACT `test-only.dev-synthetic.actor.b1b3d.1` host-bound encrypted blob | **yes** (custody only) |
| `/var/lib/systemd/credential.secret` | yes |
| `lilith-authority-dev` account, release `9ac7de2…`, units (inactive, not enabled) | yes |
| `AuthorityRegistryV1`, `TrustedRegistryRootV1`, `/etc/lilith-authority-dev` | **no** |
| K-WIT, `lilith-recovery-witness`, `RecoveryWitnessV1` | **no** |
| `authority_ledger.db` | **no** |
| Activation | `NOT_ACCEPTED reason=GRANT_ABSENT` |

K-ACT is therefore **not an authority key yet**. It appears in no registry.
It has no `AuthorityKeyRecordV1`, and no witness or ledger exists.

- Replacing K-ACT today would be a custody change with **no authority
  effect**, because nothing current would be retired.
- Every rotation, revocation, and epoch semantic in this record becomes live
  only after the B1b-3d L3a–L4 steps exist: registry, anchors, witness,
  ledger, and signer readiness. Those steps are not authorized.

```text
credential custody != accepted authority      (live closure §1)
```

## 2. Inherited invariants

These invariants are fixed. B1b-3e adds none that weakens them.

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

B1b-3e adds these separations, and they are used throughout this record:

```text
rotation                   != silent replacement
prepared                   != active
published                  != activated
credential exists          != accepted authority
activation                 != issuance        (issuance still needs RESTORE_READY)
signed authorization       != executed transition
witness receipt            != independent verification
```

It also inherits two B1b-3c rules unchanged
([B1b-3c](slice-15b2b-b1b3c-recovery-epoch-witness.md), "Two rules carry the
whole slice"):

1. **Removing authority never needs readiness; creating it always does.**
2. **Recovery can only destroy pending authority, never create any.**

## 3. Existing contracts reused

B1b-3e reuses these as they are. It adds no duplicate concept.

| Contract / mechanism | Source | Role in B1b-3e |
| --- | --- | --- |
| `AuthorityKeyRecordV1` (`createdAt`, `notBefore`, `retiredAt`, `revokedAt`, `revocationReason ∈ {ROUTINE, COMPROMISED, SUPERSEDED}`, `compromisedSince`, `recoveryEpoch`, `policyVersion`, immutable first-publication `registryVersion`) | `authority_contracts.py` | the only key-lifecycle representation; rotation and revocation are expressed only through it |
| `AuthorityRegistryV1` + `TrustedRegistryRootV1` | `authority_contracts.py` | registry-root authorization of every key transition and every epoch advance |
| `verify_authority_registry`, `verify_owner_evidence` (44-reason taxonomy) | `authority_verifier.py` | forward rejection and historical verification |
| `RecoveryEpochV1 {counter, random}`, `epoch_digest`, `compare_epochs` (`EQUAL`/`OLDER`/`NEWER`/`FORKED`), `ledger_epoch_id` | `authority_contracts.py`, `recovery_contracts.py` | epoch identity, ordering, and fork detection |
| `RecoveryWitnessV1`, `TrustedWitnessAnchorV1`, `witness_succession_reason` (`SUCCESSION_REASONS`) | `recovery_contracts.py` | witness execution and receipt; monotonic succession |
| `witness_authority_context` | `recovery_contracts.py` | trusted epoch and registry floor for verification |
| `AuthorityLedgerStateV1` journal ops (`PREPARE`, `CONSUME`, `ISSUE`, `RESERVE`, `CONFIRM`, `EXPIRE`/`CANCEL`/`FAIL`, `ABANDON`, `REGISTRY_VIEW`, `ADVANCE_EPOCH`, `VOID_CHALLENGE`, `QUARANTINE_USE`) | `synthetic_recovery_ledger.py` | the ledger state machine; `REGISTRY_VIEW` is the in-epoch activation event |
| `begin_recovery`, `quarantine_pre_recovery`, `RECOVERY_REASONS` | `synthetic_recovery_ledger.py` | the epoch-advance ledger steps |
| `evaluate_restore_readiness` → `RESTORE_READY` / `NOT_READY(reason)` | `synthetic_recovery_ledger.py` | the only gate for authority-creating operations |
| `RecoveryEpochTransitionV1` | `synthetic_recovery_ledger.py` | the post-advance acknowledgement record (not an authority) |
| `RecoveryBoundAdmissionGateV1`, `verify_historical_accepted_memory` | `recovery_admission.py` | NEW_ADMISSION_AUTHORITY vs HISTORICAL_VALIDITY |
| Witness owner-socket ops `BOOTSTRAP`, `RAISE_REGISTRY_FLOOR`, `ADVANCE_EPOCH`; signer op `RECORD_LEDGER_ADVANCE`; ceremony hold file; verifier CLI | B1b-3d design §10, §11, §13 | execution and verification boundaries (designed, not live) |
| DEV_SYNTHETIC backup policy: no K-ACT/K-WIT backup; loss means re-key | B1b-3d design §16 | credential-restore policy |

## 4. State owners

Every state object below has exactly one owner. **No new service, identity,
socket, or layer is introduced.** Each B1b-3e object in the last three rows is
either a refinement of an existing owner's state or a record produced by the
existing verifier.

| State | Owner | Where | Mutated by | Live? |
| --- | --- | --- | --- | --- |
| Owner intent / transition request | owner, via host root | the root-owned ceremony hold (B1b-3d §13 step 1), refined as `AuthorityTransitionHoldV1` (§8.1) | owner only | no |
| Registry-root authorization | owner, **offline**, K-ROOT | a signed `AuthorityRegistryV1` (all versions retained) | owner workstation only | no (no K-ROOT anchor installed) |
| Effective registry ("which registry counts") | recovery witness (`minimumRegistryVersion`), via the verified registry at or above it | witness chain + `…/registry/` | witness `RAISE_REGISTRY_FLOOR` / `ADVANCE_EPOCH` | no |
| Recovery epoch, ledger position | recovery witness | `witness.json` + append-only `chain/` | witness service only | no |
| Challenge / evidence / evidence-use ledger, active signing key set | `lilith-authority-dev` | `authority_ledger.db` journal (authoritative over rows) | signer only | no |
| Private key material (K-ACT; later K-WIT) | root credential store + systemd | `/etc/credstore.encrypted/*.cred`, host key | owner (root) ceremony CLIs | K-ACT **yes** |
| Verification / read model | nobody (stateless) | independent root-run verifier CLI output | — | no |
| Legacy `owner_control.db` `authority_epoch` | none (retired, non-authoritative history; B1b-3d T-12) | legacy broker DB | — | yes, inert |
| Application databases | not an authority owner (never consulted; B1b-3c §14) | — | — | — |

**Infrastructure depth proportional to cognitive relevance.** B1b-3e adds:

- no witness replica;
- no rotation daemon;
- no scheduler;
- no off-host service.

The property protected is narrow. Owner-approved memory must never be
accepted on authority that is not current. Every mechanism below is the
smallest one that keeps that property across key change and restore.

## 5. Timestamp and interval semantics (CANONICAL, quoted from source)

The verifier in `authority_verifier.py` (`_verify_evidence`) and the record
validator in `authority_contracts.py` (`AuthorityKeyRecordV1.from_dict`,
`AuthorityRegistryV1.from_verified_dict`) currently enforce:

| Field | Record constraint | Verification effect |
| --- | --- | --- |
| `createdAt` | `notBefore ≥ createdAt`; `revokedAt ≥ createdAt`; `≤ registry.issuedAt` | ordering only; no evidence rule |
| `notBefore` | `≥ createdAt`; **not** bounded by `registry.issuedAt` (may be in the future) | `issuedAt < notBefore` → `KEY_NOT_YET_VALID` |
| `retiredAt` | `≥ notBefore`; `≤ registry.issuedAt` (cannot be scheduled in the future) | `issuedAt ≥ retiredAt` → `KEY_RETIRED`, **both purposes** |
| `revokedAt` + `revocationReason` | set together; `≥ createdAt`; `≤ registry.issuedAt` | ROUTINE / SUPERSEDED: `issuedAt ≥ revokedAt` → `KEY_REVOKED`, both purposes |
| `compromisedSince` | set **iff** `revocationReason == COMPROMISED`; `≤ revokedAt`; `≤ registry.issuedAt` | **not consulted.** Every piece of evidence the key signed → `KEY_COMPROMISED`, both purposes, whatever its `issuedAt` |
| evidence `issuedAt` | signer-controlled | the only evidence time |
| `signedAt`, accepted-at | **do not exist** in `OwnerEvidenceV2` or any B1b-3a/3c contract | — |
| key "current" | `retiredAt == null and revokedAt == null` (independent of `notBefore`) | registry invariant: a current key is in the registry's epoch and policy |

The only trusted ordering of authority events is the **ledger journal
sequence**. It is anchored by the witness's `ledgerSequence`/`ledgerHead`.
This is ledger-only: it holds only while the witness survives (B1b-3c §16).
No trusted wall-clock acceptance time exists.

## 6. Revocation semantics

### 6.1 Four distinct transitions

| Transition | Record expression (CANONICAL fields) | Meaning | Evidence already issued |
| --- | --- | --- | --- |
| **Retirement** | `retiredAt = t` | planned end of validity. The key is not suspected. Used by rotation (§7) and by every epoch advance ("every current E1 key is retired at the recovery instant", B1b-3c §10) | valid if `notBefore ≤ issuedAt < t` (`RETIRED_AFTER_ISSUANCE`) |
| **Routine revocation** | `revokedAt = t`, `ROUTINE` | the key stops for a non-security reason (lost, decommissioned, never activated) | valid if `issuedAt < t` (`REVOKED_AFTER_ISSUANCE`) |
| **Supersession** | `revokedAt = t`, `SUPERSEDED` | replaced by a successor before its planned retirement. It verifies the same way as ROUTINE. **No successor-link field exists**, and B1b-3e invents none. The successor relation lives in the transition record (§7.6) | as ROUTINE |
| **Compromise** | `revokedAt = t`, `COMPROMISED`, `compromisedSince ≤ t` | private material may be outside custody | **all** rejected, `KEY_COMPROMISED`, both purposes |

**PROPOSED usage rule (DEV_SYNTHETIC profile).** Use each expression for one
case only:

- **Rotation** retires the predecessor with `retiredAt`. It does not use
  `SUPERSEDED`. This matches the existing B1b-3c ceremony.
- **`ROUTINE`** is for a published key that was lost or never activated.
- **`SUPERSEDED`** is reserved and unused by DEV_SYNTHETIC rotation.

The verifier gives all three the same result. The rule only keeps the audit
trail unambiguous. Decision RR-10.

### 6.2 Historical-validity invariant

> Evidence that was valid under the registry/key state applicable to its
> issuance is not retroactively invalidated merely because its key is later
> retired, routinely revoked, or superseded.

This already holds in source for retirement, ROUTINE, and SUPERSEDED. The B1b-3a
golden vectors freeze these outcomes: "retirement accepted as history" and
"in-flight evidence surviving a registry update". It holds **only while the
key record is retained unchanged** in every later registry. Verification is
against the current registry only. As B1b-3a says, "a key record removed
from a later registry makes its evidence `KEY_UNKNOWN`", and a mutated
`recoveryEpoch` or `policyVersion` would make its evidence
`RECOVERY_EPOCH_MISMATCH` or `POLICY_VERSION_MISMATCH`.

**Gap (found by this review):** no source today checks one registry version
against the next. A K-ROOT-signed registry that deletes or rewrites a record
would verify, and it would silently invalidate history. §6.5 closes this in
design.

### 6.3 Compromise: CONFLICT C-1

**The brief says:** evidence whose relevant time lies in the compromised
interval may become invalid, while evidence demonstrably before
`compromisedSince` is not automatically invalidated.

**The repository says** (verbatim, `authority_verifier.py` module docstring):

> compromise is retroactive: every piece of evidence the key signed is
> rejected, whatever its signer-controlled `issuedAt`, because
> re-attestation does not exist yet;

The B1b-3a record says: "**Compromise** is retroactive: `KEY_COMPROMISED` for
every piece of evidence the key signed, in every purpose, whatever its
signer-controlled `issuedAt`. Re-attestation is not implemented."

The B1b-3 design ("Retirement versus compromise") gives the reason. An
attacker holding the key can backdate `issuedAt`, so "`compromisedSince`
alone cannot separate genuine historical evidence from forged backdated
evidence."

**B1b-3e keeps the repository rule.** It does not adopt the brief's interval
rule. The consequence is spelled out, not hidden:

- A compromise **does** retroactively invalidate every piece of historical
  evidence signed by that key. This is the one deliberate exception to §6.2.
  It is not an accident of registry evolution.
- `compromisedSince` is recorded forensic information. It is not a
  verification boundary.
- The **only** way evidence "demonstrably before `compromisedSince`" could
  survive is **re-attestation**. Re-attestation needs a trusted ordering that
  the key holder cannot forge. Two candidates:
  1. the witness-anchored ledger position of the evidence's `ISSUE` and
     `CONFIRM` operations;
  2. an owner-signed checkpoint over accepted evidence digests.

  Neither exists as a contract, and (1) is ledger-only. Adopting interval
  compromise before one exists would let a key thief mint "historical"
  evidence by backdating. Decision RR-1.

**Friction (RR-8).** `compromisedSince ≤ revokedAt` is enforced. Take a key
that was routinely revoked at `t_r`, whose material leaks later: its true
compromise time is after `t_r`. It can only be escalated by setting
`compromisedSince ≤ t_r`. The verdict is the same, because compromise is
retroactive, but the forensic field is then knowingly imprecise. The
escalation rule is defined in §6.5. Changing the constraint needs a new
contract version.

### 6.4 Forward rejection, stale registries, and registry-version effects

- **Forward rejection.** After retirement or revocation at `t`, evidence with
  `issuedAt ≥ t` is refused for both purposes. Issuance is also refused
  earlier, at the ledger. Readiness requires every journalled signing key to
  be current in the verified registry and not compromised
  (`REQUIRED_KEY_UNAVAILABLE`). Readiness also requires the ledger's
  registry view to equal the verified registry (`BROKER_REGISTRY_VIEW_STALE`).
- **Signer-controlled time.** A retired key could still produce evidence with
  a backdated `issuedAt` if its private material survived. Retirement is
  therefore complete only when the predecessor's private material has left
  active custody (B1b-3d §13 step 8: "remove the old private blob"). See §8.4
  for what a snapshot means here.
- **Registry-version effects** (CANONICAL, B1b-3a):
  `key.registryVersion ≤ evidence.registryVersion ≤ registry.registryVersion`.
  Registry evolution alone never invalidates evidence. The key is judged by
  its record in the current registry.
- **Stale registry rejection.** Below the witness floor →
  `REGISTRY_DOWNGRADE`, which blocks issuance **and** historical reads. The
  ledger's view above the installed registry → `REGISTRY_DOWNGRADE`
  (`BELOW_BROKER_VIEW`). The installed registry above the ledger's view →
  `BROKER_REGISTRY_VIEW_STALE`.

### 6.5 Additive authority history (PROPOSED contract)

There is no "delete the bad key from history" mechanism, and B1b-3e forbids
one. A compromised key is marked, never removed.

**PROPOSED `verify_registry_succession(previous, following)`** is a pure
function with a closed reason set. It adds **no** B1b-3a verifier change and
**no** signed field. It is required wherever a registry version is raised: at
witness `RAISE_REGISTRY_FLOOR` and `ADVANCE_EPOCH`, and in the verifier CLI
over the retained chain v1…vN.

| Rule | Reason if violated |
| --- | --- |
| same `environment`, same `registryRootKeyId` (root change needs a new anchor ceremony) | `SUCCESSION_ROOT_OR_ENVIRONMENT_CHANGED` |
| `following.registryVersion == previous.registryVersion + 1` | `SUCCESSION_VERSION_GAP` |
| `following.issuedAt ≥ previous.issuedAt` | `SUCCESSION_TIME_REGRESSION` |
| epoch equal, or `compare_epochs` `NEWER` with `counter + 1` | `SUCCESSION_EPOCH_INVALID` |
| every previous `keyId` is present | `SUCCESSION_RECORD_REMOVED` |
| immutable per record: `signingDomain`, `evidenceTypes`, `environment`, `algorithm`, `publicKey`, `createdAt`, `notBefore`, `recoveryEpoch`, `policyVersion`, `registryVersion` | `SUCCESSION_RECORD_MUTATED` |
| `retiredAt`: `null → t` only; once set, unchanged | `SUCCESSION_LIFECYCLE_REOPENED` |
| `revokedAt`/`revocationReason`: `null → (t, reason)` only; once set, `revokedAt` unchanged. The only permitted reason change is `ROUTINE`/`SUPERSEDED` → `COMPROMISED`, with `compromisedSince` added and `≤ revokedAt` (RR-8) | `SUCCESSION_LIFECYCLE_REOPENED` |
| `COMPROMISED` never changes back | `SUCCESSION_COMPROMISE_CLEARED` |
| a non-current record never becomes current | `SUCCESSION_LIFECYCLE_REOPENED` |
| new records carry `registryVersion == following.registryVersion` | `SUCCESSION_NEW_RECORD_VERSION` |
| DEV_SYNTHETIC profile: exactly one current OWNER_ACTOR key (RR-3) | `SUCCESSION_CURRENT_KEY_COUNT` |

A version gap is refused so that the retained chain is complete and every
step is checkable. Whether gaps may be allowed is part of RR-4.

## 7. Rotation

### 7.1 Two kinds of rotation

| Kind | Epoch | In-flight owner proofs | Triggered by |
| --- | --- | --- | --- |
| **In-epoch rotation** | unchanged | **preserved**: predecessor evidence with `issuedAt < retiredAt` stays reservable and admissible in the same epoch (B1b-3c §7: "a routine key rotation during an in-flight approval must not burn the owner's proof") | routine key age or policy, a key lost with no suspected exposure |
| **Epoch-advance rotation** | `counter + 1` | **burned by design**: PREPARED → `VOIDED_BY_RECOVERY`, RESERVED → `QUARANTINED_BY_RECOVERY`, E(n) evidence never reservable in E(n+1) | recovery (`RECOVERY_REASONS`), compromise (RR-6) |

Epoch-advance rotation is forced by B1b-3a: a key belongs to one epoch, and a
current key must be in the registry's epoch (B1b-3c open decision 9;
B1b-3d §13). It is specified in §9. This section specifies the shared state
machine and the in-epoch path.

### 7.2 State machine

States are named for the **successor** S. The predecessor P's state is
implied at each step. **Each state is owned by exactly one of the §4 owners.**

```text
            owner hold                keygen              K-ROOT signs vN+1        witness floor N+1
 P_ACTIVE ───────────▶ S_PROPOSED ───────────▶ S_PREPARED ───────────▶ S_AUTHORIZED ───────────▶ S_PUBLISHED
    ▲                      │                        │                       │                        │
    │                      │ abort                  │ abort: destroy blob   │ abort: discard,        │ forward only
    └──────────────────────┴────────────────────────┴───────────────────────┘ never install          ▼
                                                                                    ledger REGISTRY_VIEW + witness
                                                                                                     │
                                                                              S_ACTIVATED ◀──────────┘
                                                                                   │ verifier RESTORE_READY, hold removed
                                                                                   ▼
                                                                              S_CURRENT  (P = P_RETIRED)
```

| State | Owner | Exact representation | P is | S can sign accepted evidence? |
| --- | --- | --- | --- | --- |
| `P_ACTIVE` | registry + ledger | vN: P current; ledger `signingKeyIds == [P]`; witness floor N; `RESTORE_READY` | issuing | — |
| `S_PROPOSED` | owner | `AuthorityTransitionHoldV1{kind: KEY_ROTATION}` present, so the signer refuses every creating op | current, **not issuing** (held) | no key exists |
| `S_PREPARED` | credential custody | successor blob in a **distinct** slot (B1b-3d §13 "`.next.cred`", not referenced by any unit); public publication JSON | current, held | **no**: not in any verified registry (`KEY_UNKNOWN`), not loadable by the unit, and not a journalled signing key |
| `S_AUTHORIZED` | owner (K-ROOT) | signed vN+1: S current with `notBefore = t_cut`; P `retiredAt = t_cut`; exactly one current OWNER_ACTOR key; `verify_registry_succession(vN, vN+1)` passes. Held on the workstation, or installed as a file with the floor still N | current in vN, which still counts | no: vN+1 does not count until the floor is raised; the ledger still names P |
| `S_PUBLISHED` | witness | witness `RAISE_REGISTRY_FLOOR{vN+1}` succeeded: floor N+1. **Point of no return for P**: vN is now a downgrade | retired (registry fact) | **no**: the ledger view is N and its signing key is P, so readiness fails with `BROKER_REGISTRY_VIEW_STALE` / `REQUIRED_KEY_UNAVAILABLE`. Nothing issues |
| `S_ACTIVATED` | ledger | successor blob atomically moved into the fixed unit slot; P's blob destroyed; signer started under hold; startup fingerprint check (B1b-3d §18) passes; journal `REGISTRY_VIEW{registryVersion: N+1, signingKeyIds: [S]}` committed; `RECORD_LEDGER_ADVANCE` witnessed | retired, material destroyed | not yet: the hold still blocks creating ops |
| `S_CURRENT` | verifier → owner | the independent verifier prints `RESTORE_READY` and emits `AuthorityKeyTransitionV1` (§7.6); owner removes the hold | `P_RETIRED` | **yes**, through the normal ledger path only |

**The exact event that changes which key is current**, in two senses:

- **Verification-current:** the witness raises the floor to vN+1
  (`S_PUBLISHED`). From then on only vN+1 counts.
- **Issuance-current:** the ledger journal entry
  `REGISTRY_VIEW{signingKeyIds:[S]}`, once witnessed. It is non-creating in
  source (`record_registry`, `creates_authority=False`).

That second event is safe without readiness. It creates nothing:
issuance still needs `RESTORE_READY`, which checks the journalled key against
the verified registry.

```text
published (S_PUBLISHED) != activated (S_ACTIVATED) != issuing (S_CURRENT)
```

### 7.3 Cut-over time `t_cut` (PROPOSED)

- `t_cut` is chosen **after** the hold is in force and the signer is stopped.
- `t_cut` must be strictly greater than the `issuedAt` of every piece of P
  evidence recorded in the ledger. The verifier CLI proves this from
  `authority_evidence_v2` signed bytes, which are opened read-only.
- `t_cut ≤ vN+1.issuedAt` is required by the contract.

This guarantees that every legitimately issued P evidence falls inside
`[notBefore, retiredAt)`. P evidence can be reserved and confirmed after
rotation, in the same epoch. Decision RR-10.

### 7.4 Overlap

| Overlap | Permitted? | Purpose |
| --- | --- | --- |
| **Verification overlap**: P evidence issued before `t_cut` verifies after S is current | **yes**, indefinitely as history; for NEW_ADMISSION within the same epoch | in-flight owner proofs survive routine rotation |
| **Registry dual-current**: P and S both current in one registry | **no** in the DEV_SYNTHETIC profile (RR-3). B1b-3a structurally permits several current keys per signing domain. B1b-3e does not change the B1b-3a verifier; it forbids this at publication (`SUCCESSION_CURRENT_KEY_COUNT`) | — |
| **Issuance overlap**: two keys able to issue | **never**. The ledger journals exactly one signing key; the unit loads exactly one credential slot | — |
| **S valid before publication** | no: `notBefore = t_cut`, and S is absent from earlier registries | — |

**How ambiguous dual-current authority is prevented.** Evidence is authority
only in combination with a single-use owner challenge. The ledger allows
exactly one `ISSUE` per consumed challenge (`EVIDENCE_ALREADY_ISSUED`), and
one `RESERVE` per evidence (`EVIDENCE_ALREADY_USED`), whichever key signed.
Two current keys would therefore never double an owner's approval. The
single-current profile rule removes the remaining audit ambiguity about which
key was meant to issue.

### 7.5 Rotation crash and failure handling

| Point | State left | Authority change | Allowed action |
| --- | --- | --- | --- |
| crash before successor preparation | `S_PROPOSED` (hold) | none (P current, held) | remove the hold, or continue |
| keygen succeeds, authorization never happens | `S_PREPARED` | none | destroy the successor blob. It was never published, so it has no history |
| crash after signing vN+1, before install | `S_AUTHORIZED` (workstation) | none | install later, or discard. Never sign a *different* vN+1 (RR-4) |
| crash after the vN+1 file is installed, floor still N | `S_AUTHORIZED` | none: vN counts, the ledger view is N | raise the floor, or revert the pointer |
| crash after the floor is raised, before local activation | `S_PUBLISHED` | P retired; nothing issues | forward only: activate S. If S's blob is lost → vN+2 revokes S (`ROUTINE`, zero evidence proven) and names S′. Never return to P |
| crash after `REGISTRY_VIEW` is journalled, before `RECORD_LEDGER_ADVANCE` | `LEDGER_AHEAD_OF_WITNESS` | none | fail closed. As B1b-3c/3d define, this is resolved **only by an epoch advance** (§9). The signer must not re-submit after restart, because that is indistinguishable from a restored witness |
| verifier not `RESTORE_READY` | `S_ACTIVATED` with the hold | none | the hold stays; diagnose |

A partially prepared successor **can never mint accepted evidence**. Before
`S_PUBLISHED` it is not in a counting registry (`KEY_UNKNOWN`). Before
`S_CURRENT` the ledger refuses creating ops. A signature is never acceptance
in any state (B2a/B1b-3c acceptance chain).

### 7.6 `AuthorityKeyTransitionV1` (PROPOSED record, not an authority)

This is the in-epoch sibling of `RecoveryEpochTransitionV1`. The verifier CLI
produces it at `S_CURRENT`. Fields:

- `schemaVersion`, `kind`, `environment`;
- `predecessorKeyId`, `successorKeyId`, `tCut`;
- `fromRegistryVersion`, `toRegistryVersion`, both registry digests;
- `recoveryEpoch` (unchanged);
- `witnessVersionBefore`, `witnessVersionAfter`, `ledgerSequence`;
- `predecessorEvidenceCount`, `maxPredecessorIssuedAt`;
- `inFlightEvidencePreserved: true`, `historicalEvidenceRetained: true`;
- `predecessorMaterialDestroyedFromActiveCustody` (see §8.4 for its limit);
- `rollbackDetectionScope: LEDGER_ONLY`, `wholeHostRollbackProtected: false`.

## 8. Restore semantics

```text
RESTORE != AUTHORITY RESTORATION
```

**Restoring bytes never restores authority.** Authority is established only
by current state owners evaluating current semantics:

- the registry verified at or above the witness floor;
- the witness verified under its anchor;
- the ledger journal matching the witness;
- `RESTORE_READY`.

Restored bytes may be **adopted as state** only when a surviving current
state owner already attests exactly those bytes. Even then they never carry
authority beyond what that owner attests.

### 8.1 Five kinds of restore

| Kind | Bytes | What they can do | What they can never do |
| --- | --- | --- | --- |
| **Data restore** | application DBs, L04 rows, memory files | serve as history, subject to the B2a/B1b-3c acceptance chain | be consulted by readiness; revive or block authority (B1b-3c §14) |
| **Broker / signer-state restore** | `authority_ledger.db` (legacy `owner_control.db` is non-authoritative) | be adopted if and only if its journal `sequence/head` equals the surviving witness's (`RESTORE_READY`); otherwise it is evidence only | reopen a terminal row (`TERMINAL_STATE_REOPENED`); revive a PREPARED challenge after an epoch advance (`LEDGER_EPOCH_STALE`); issue when behind the witness (`LEDGER_BEHIND_WITNESS`) |
| **Registry restore** | an older signed `AuthorityRegistryV1` | none below the floor. Reinstating the retained **current** version is harmless, because its authority came from K-ROOT plus the floor, not from the file | lift a retirement, revocation, or compromise (`REGISTRY_DOWNGRADE`); make a deleted record reappear (§6.5) |
| **Credential restore** | an older `.cred` blob | none. DEV_SYNTHETIC forbids K-ACT/K-WIT backup and restore: loss means re-key (B1b-3d §16). A loaded key must match the single current registry key (fingerprint check, `REQUIRED_KEY_UNAVAILABLE`) | turn a retired key back into an issuing key; count as custody of a current key |
| **Authority restoration** | — | **only** through §9: an owner request, a K-ROOT-authorized registry at a new epoch, witness execution, and independent verification | be performed by any restore of bytes, alone or combined |

### 8.2 Specific restore cases

| Case | Detected as | Outcome |
| --- | --- | --- |
| Old VM snapshot contains a once-valid K-ACT blob. Only the blob is extracted onto the current host | fingerprint ≠ current registry key → `REQUIRED_KEY_UNAVAILABLE`; the blob is not in the unit slot | no issuance. The blob decrypts (same host key), so the retired key's material is exposed again. See RR-7 and §8.4 |
| The whole VM boots from an old snapshot | **not detected**: the witness, ledger, registry, blob, and host key all come from one time (B1b-3c §16, test-proven) | **unresolved** (§12) |
| Registry rolls back (witness current) | `REGISTRY_DOWNGRADE` | issuance and historical reads blocked. Reinstate the retained current version |
| Broker ledger rolls back (witness current) | `LEDGER_BEHIND_WITNESS` (or `LEDGER_EPOCH_STALE` / `LEDGER_HEAD_MISMATCH`) | issuance blocked; historical reads allowed. Recovery: reinstate a preserved ledger whose journal equals the witness (as in B1b-3d L7), or else epoch advance |
| Ledger **and** registry roll back together, witness newer | `REGISTRY_DOWNGRADE` first, then `LEDGER_BEHIND_WITNESS` | blocked. Reinstate the current registry, then epoch advance from the **witness** (never from the stale ledger; `begin_recovery`) |
| Witness rolls back alone | `LEDGER_AHEAD_OF_WITNESS` | blocked, and historical reads too (`_WITNESS_SUSPECT`). Epoch advance. The append-only chain is the witness's own history (RR-9) |
| Every relevant owner rolls back together | not detected | **unresolved** |

### 8.3 Stale-epoch owner proof after restore

A restored database flag is never authority:

- A `CONSUMED` challenge restored as `PREPARED` is detected
  (`TERMINAL_STATE_REOPENED`), because the journal is authoritative.
- A pre-advance `PREPARED` challenge is voided.
- Its owner assertion binds the old `ledgerEpoch`, so it can never be
  consumed or signed in the new epoch (`STALE_EPOCH_CHALLENGE`,
  `CHALLENGE_EPOCH_NOT_CURRENT`).
- Old-epoch evidence can never be reserved (`STALE_EPOCH_EVIDENCE`), even if
  relabelled.

```text
restore -> replayable owner proof          : impossible after an epoch advance
restore -> replayable owner proof, no advance: blocked by LEDGER_BEHIND_WITNESS
```

### 8.4 Host-bound credentials do not solve snapshot rollback

The live closure already records it: "Host-bound systemd credentials do not,
by themselves, solve whole-host or snapshot rollback." Any disk snapshot of
`lilith-dev-01` taken after L2a/L2b.2 contains both:

- the K-ACT blob;
- `credential.secret`.

This record does **not** know whether any such snapshot exists. It made no
live contact. Consequences:

- `predecessorMaterialDestroyedFromActiveCustody` means **only** that the
  material was destroyed from the live credential store. It is never "the
  key no longer exists".
- **PROPOSED (RR-7).** Retained material inside the owner/root boundary is
  the known Level-3 / whole-host debt, not a compromise. Examples: a GCE
  snapshot in the same project that was never exported, and that root could
  read anyway. Material found **outside** that boundary is a compromise.
  Examples: exported, copied off-project, loaded by a non-authority unit, or
  seen by `lilith` or the deployer. Such a key is marked `COMPROMISED`
  (retroactive, §6.3), and RR-6 then applies.

## 9. Recovery-epoch advancement protocol

The sequence is the brief's. It already matches B1b-3d §11. No stricter
canonical version exists.

```text
Owner Request  ->  Registry-root Authorize  ->  Recovery Witness Execute  ->  Independent Verify
   (intent)          (offline K-ROOT)              (witness service)            (verifier CLI)
```

| Boundary | Object (reused unless marked) | Owner | Is authority? |
| --- | --- | --- | --- |
| **EpochAdvanceRequest** | `AuthorityTransitionHoldV1{kind: EPOCH_ADVANCE, reason ∈ RECOVERY_REASONS, environment, observedWitnessDigest, observedRegistryVersion, createdAt}`, the content of the existing B1b-3d hold (**PROPOSED refinement**) | owner | **no**. It only blocks creating ops (destroy-only). The signer may only *report* `NOT_READY` (B1b-3d §11). The application has no path |
| **EpochAdvanceAuthorization** | the K-ROOT-signed `AuthorityRegistryV1` at `newEpoch = (witness.counter + 1, fresh random)`, with `registryVersion > witness.minimumRegistryVersion`, every E(n) key non-current, exactly one current OWNER_ACTOR key at E(n+1), and passing `verify_registry_succession` (reused; B1b-3d T-8: no additional ceremony signature for DEV_SYNTHETIC) | owner, offline | it **permits** one transition. It mutates nothing. It does not advance the witness |
| **Witness execution** | witness owner-socket `ADVANCE_EPOCH{registry, ledgerSequence, ledgerHead, reason}` → successor `RecoveryWitnessV1` plus `chain/<v>.json` (reused) | witness | executes the only epoch change. The signed witness is the receipt |
| **Resulting RecoveryEpoch** | `witness.currentRecoveryEpoch: RecoveryEpochV1`; `ledgerEpoch = "lep1." + epoch_digest(epoch, env)` (reused) | witness | the only epoch in which authority may issue |
| **Verification evidence** | `ReadinessResultV1 == RESTORE_READY` + `RecoveryEpochTransitionV1` from the root-run read-only verifier CLI (reused) | nobody (stateless) | no. `execution != verification`; resumption requires it |

### 9.1 Epoch rules (CANONICAL)

| Rule | Source behaviour |
| --- | --- |
| Current epoch | `witness.currentRecoveryEpoch` |
| Requested next epoch | `(witness.counter + 1, fresh random)`, from the witness, never from a stale ledger (`begin_recovery`) |
| Monotonic counter | succession: counter equal, or `+1` (`WITNESS_EPOCH_NOT_SUCCESSOR`); never older (`WITNESS_EPOCH_REGRESSION`); floor strictly higher on advance (`WITNESS_REGISTRY_MINIMUM_REGRESSION`) |
| Random / fork component | same counter + different random = `FORKED` (`compare_epochs`) → `WITNESS_EPOCH_REGRESSION`, `LEDGER_EPOCH_FORKED`. The new random must differ from the current one (`RECOVERY_EPOCH_NOT_ADVANCING`). B1b-3d adds "never seen before", checked against the chain |
| Stale epoch rejection | `LEDGER_EPOCH_STALE`, `STALE_EPOCH_CHALLENGE`, `STALE_EPOCH_EVIDENCE`, `CHALLENGE_EPOCH_NOT_CURRENT`, `RECOVERY_EPOCH_MISMATCH` for NEW_ADMISSION |
| Replay rejection | an executed authorization cannot re-execute: the counter is no longer `+1`, and the floor is not strictly higher. An older registry is below the floor |
| Authorization expiry | **none exists**. The registry has `issuedAt` but no `notAfter` (RR-2) |
| At-most-once | the witness chain is linear (`previousWitnessDigest`, `witnessVersion + 1`, `O_EXCL` chain files, single-instance service with `flock`). One authorization executes at most once. After a crash the owner **reads** the witness (`READ_WITNESS`) instead of retrying blind. Seeing the authorized epoch as current means it executed |

### 9.2 Ordering: CONFLICT C-4 (B1b-3c source vs B1b-3d design text)

| | Order |
| --- | --- |
| **B1b-3c (source, tested)** | the ledger journals `ADVANCE_EPOCH` first (`begin_recovery`: destroy-only, carries `fromWitnessDigest`, new epoch computed from the **pre-advance** witness). **Then** the witness records the new epoch with the **post-journal** `sequence/head`. Then quarantine, then witness again |
| **B1b-3d §10/§13 (design, not implemented)** | the witness `ADVANCE_EPOCH` first, with the *restored* `sequence/head`. Then the signer "adopts" E(n+1) and calls `RECORD_LEDGER_ADVANCE` |

The consequences of the B1b-3d order:

- **Head check.** It fails `witness_succession_reason` whenever the ledger was
  not actually restored. On advance, the head must differ from the previous
  witness head (`WITNESS_LEDGER_REGRESSION`). An epoch advance on a current
  ledger (compromise, rotation, `LEDGER_AHEAD_OF_WITNESS` recovery) would
  therefore be refused.
- **Counter.** A post-advance `begin_recovery` would compute `counter + 2`.

**PROPOSED (RR-5):** the B1b-3c order is canonical. The B1b-3d ceremony
steps 6–9 are re-sequenced in the follow-on source slice:

1. Install the vN+1 file.
2. Signer, running under the hold with the old credential, journals
   `ADVANCE_EPOCH`. This is a destroy-only op and needs no signing.
3. Witness `ADVANCE_EPOCH` binding that post-journal `sequence/head` (point of
   no return).
4. Stop the signer; swap the credential; start it.
5. Quarantine ops, then `RECORD_LEDGER_ADVANCE`.
6. The verifier prints `RESTORE_READY`; remove the hold.

B1b-3e does not edit the B1b-3d record. It records the conflict here.

### 9.3 Epoch-advance crash handling

| Crash after | Readiness | Allowed action | Authority change |
| --- | --- | --- | --- |
| the hold is written | issuance held | remove the hold, or continue | none |
| authorization signed, not executed | unchanged | execute later, or discard (no expiry, RR-2) | none |
| ledger `ADVANCE_EPOCH` journalled, witness not advanced | `LEDGER_EPOCH_AHEAD_OF_WITNESS` | witness `ADVANCE_EPOCH` with **the same** authorization (its epoch equals the journalled epoch). This is completion, not retry | none until the witness executes |
| witness advanced (**point of no return**) | `NONTERMINAL_PRE_RECOVERY_WORK` until quarantine | finish the quarantine (destroy-only); swap the credential | E(n) authority is gone; E(n+1) issuing is still blocked |
| quarantine journalled, `RECORD_LEDGER_ADVANCE` lost | `LEDGER_AHEAD_OF_WITNESS` | **another** epoch advance (B1b-3c/3d; it is safe by rule 2). This is the per-transition witnessing cost (T-4) | none |
| witness `chain/<v>.json` written, `witness.json` not renamed | witness refuses writes (B1b-3d §18) | RR-9: roll forward if the chain head is a valid signed successor of `witness.json`; otherwise break-glass | none |

## 10. Ledger state machine

The transitions below are the ones `synthetic_recovery_ledger._step` enforces
(IMPLEMENTED, TEST). The B1b-3d schema makes them durable with triggers
(designed, not provisioned).

**Challenge**

```text
            PREPARE (ready, current ledgerEpoch)
 (absent) ─────────────────────────────────────▶ PREPARED
                                                 │  CONSUME (ready, current epoch) ──▶ CONSUMED ── ISSUE (ready, once) ──▶ CONSUMED+evidence
                                                 │  EXPIRE / CANCEL / FAIL ───────────▶ EXPIRED | CANCELLED | FAILED
                                                 │  VOID_CHALLENGE (older epoch only) ─▶ VOIDED_BY_RECOVERY
```

**Evidence use**

```text
 (absent) ── RESERVE (ready; issued here; digest; issuing epoch == claimed == current; unused) ──▶ RESERVED
 RESERVED ── CONFIRM (ready; current epoch) ─────────────────────────────────────────────────────▶ CONSUMED
 RESERVED ── ABANDON ────────────────────────────────────────────────────────────────────────────▶ ABANDONED
 RESERVED ── QUARANTINE_USE (older epoch only) ──────────────────────────────────────────────────▶ QUARANTINED_BY_RECOVERY
 QUARANTINED_BY_RECOVERY ── RECONCILE_DECISION {ABANDON | REQUIRE_OWNER_REAUTHORIZATION} ─────────▶ ABANDONED   (B1b-3d §14; designed)
```

**Ledger-global**

```text
 GENESIS (seq 0 only) ─▶ … ─ REGISTRY_VIEW (version strictly up; sets signingKeyIds)   [in-epoch activation]
                         … ─ ADVANCE_EPOCH (counter strictly up; registry strictly up) [epoch activation]
```

Required rules, all already enforced or designed:

| Rule | Mechanism |
| --- | --- |
| PREPARED may be voided | `VOID_CHALLENGE` only for an older `ledgerEpoch`, and destroy-only. In-epoch: `CANCEL`/`EXPIRE`/`FAIL` |
| CONSUMED never reopens | there is no transition out of `CONSUMED`. Rows showing otherwise → `TERMINAL_STATE_REOPENED`. B1b-3d triggers forbid terminal edits |
| CONSUMED is never reusable | a second `ISSUE` → `EVIDENCE_ALREADY_ISSUED`; a second `RESERVE` → `EVIDENCE_ALREADY_USED` |
| A stale epoch is rejected | `CHALLENGE_EPOCH_NOT_CURRENT`, `STALE_EPOCH_CHALLENGE`, `STALE_EPOCH_EVIDENCE`, `STALE_EPOCH_RESERVATION` |
| An old epoch never becomes current | `ADVANCE_EPOCH` requires `counter > current`; witness succession forbids regression and fork |
| History is additive | an append-only journal with a hash-chained `head`. Terminal rows are retained unchanged. Nothing is deleted by recovery or reconciliation |
| Restore → replayable owner proof | impossible (§8.3) |

Forbidden transitions: `CONSUMED → PREPARED`, `CONSUMED → reusable`, any
terminal state → any state, `VOIDED_BY_RECOVERY → *`,
`QUARANTINED_BY_RECOVERY → RESERVED/CONSUMED`, `ADVANCE_EPOCH` to an older or
forked epoch, and `REGISTRY_VIEW` to a lower or equal version.

**PROPOSED (RR-4): registry digest in the journal.** Add `registryDigest` to
the `REGISTRY_VIEW` and `ADVANCE_EPOCH` payloads. The DEV_SYNTHETIC profile
readiness would then require the installed registry's digest to equal the
journalled one (`REGISTRY_DIGEST_MISMATCH`, in the profile's own reason set,
as B1b-3d did for `CUSTODY_PREFLIGHT_FAILED`). The B1b-3c taxonomy does not
change.

The witness already binds the ledger head. The head chains over the payload.
So the registry digest becomes **transitively witnessed**, without changing
`RecoveryWitnessV1`. This closes the same-version registry fork (§12).

## 11. Failure matrix

Every row reports `rollbackDetectionScope: LEDGER_ONLY` and
`wholeHostRollbackProtected: false`. None of these semantics is live until
B1b-3d L3a–L4 exist (§1).

| # | Failure | Authoritative state owner | Allowed recovery action | Authority changes? | Historical evidence changes? | Fail-closed behaviour |
| --- | --- | --- | --- | --- | --- | --- |
| F1 | crash before successor preparation | owner (hold) | remove the hold, or continue | no | no | creating ops refused while the hold exists |
| F2 | crash after successor preparation | credential custody | destroy the unpublished successor blob, or continue | no | no | the successor is not in the registry (`KEY_UNKNOWN`), not loadable, not journalled |
| F3 | crash after registry authorization (signed vN+1 not installed, or installed below the floor) | owner (K-ROOT) / witness floor N | install and raise the floor, or discard. Never sign a second vN+1 | no | no | vN still counts; the ledger names P under the hold |
| F4 | crash after witness execution (floor raised or epoch advanced) | witness | forward only: activate the successor (in-epoch), or quarantine and swap (epoch) | P retired / E(n) gone (point of no return) | no (retirement is interval-preserving) | `BROKER_REGISTRY_VIEW_STALE`, `REQUIRED_KEY_UNAVAILABLE`, or `NONTERMINAL_PRE_RECOVERY_WORK` |
| F5 | crash after registry publication, before local activation | witness + ledger | journal `REGISTRY_VIEW{[S]}`, then witness it | no further change | no | no issuance: the ledger view is stale |
| F6 | stale authorization replay (old registry, re-submitted raise or advance) | witness | none needed | no | no | `REGISTRY_DOWNGRADE`, floor not strictly higher, counter not `+1` |
| F7 | old credential restored (blob only) | registry + ledger | leave the blob unloaded. Apply RR-7 to decide whether this is a compromise | no | no, unless RR-7 → `COMPROMISED` (then retroactive for that key) | fingerprint mismatch → `REQUIRED_KEY_UNAVAILABLE` |
| F8 | old registry restored | witness floor | reinstate the retained current registry | no | no | `REGISTRY_DOWNGRADE`: issuance **and** historical reads blocked |
| F9 | old broker ledger restored | witness | reinstate a preserved ledger equal to the witness, else epoch advance | only through an epoch advance | no | `LEDGER_BEHIND_WITNESS` / `LEDGER_EPOCH_STALE` / `LEDGER_HEAD_MISMATCH` |
| F10 | old registry + old ledger restored, witness survives | witness | reinstate the current registry, then epoch advance from the witness | only through an epoch advance | no | `REGISTRY_DOWNGRADE`, then `LEDGER_BEHIND_WITNESS` |
| F11 | whole-host rollback | **none survives** | none. The owner must treat the host as untrusted by out-of-band knowledge (§12) | **undetected**: stale authority may revive | undetected | **not fail-closed**: `RESTORE_READY` on the old state (B1b-3c §16, test-proven) |
| F12 | compromised old key | registry (K-ROOT) | publish `COMPROMISED` (and `compromisedSince`) in vN+1. If it was the issuing key, epoch advance (RR-6) | yes: the key is dead | **yes**: every piece of evidence it signed → `KEY_COMPROMISED` (C-1, deliberate) | readiness `REQUIRED_KEY_UNAVAILABLE` if it was journalled |
| F13 | routine retirement | registry + ledger | in-epoch rotation (§7) | the successor becomes current | no: `RETIRED_AFTER_ISSUANCE` stays valid | no issuance between `S_PUBLISHED` and `S_CURRENT` |
| F14 | successor key lost before activation | registry | vN+2: revoke S `ROUTINE` (zero S evidence, proven by the verifier), publish S′ | no | no | S cannot issue: not journalled, no blob |
| F15 | successor key lost after activation | registry + ledger | destroyed with no exposure → retire S and rotate to S′. Whereabouts unknown or exposed → `COMPROMISED` + epoch advance | the successor is replaced | retire: no. Compromise: yes (S's evidence) | `REQUIRED_KEY_UNAVAILABLE` (unit fails on a missing credential) |
| F16 | same-version registry fork (two K-ROOT-signed vN+1) | owner discipline today; journalled digest if RR-4 is adopted | refuse the second; treat as a K-ROOT operational incident | no, if detected | no | **today: not detected** by floor semantics; with RR-4, `REGISTRY_DIGEST_MISMATCH` |
| F17 | crash between ledger commit and witness record (any creating or activating op) | witness | epoch advance | only through an epoch advance | no | `LEDGER_AHEAD_OF_WITNESS` |

## 12. Security boundaries and unresolved risks

### Boundaries

| Actor | Can | Cannot |
| --- | --- | --- |
| Owner with K-ROOT (workstation) | authorize any registry transition and epoch advance | execute on the host without a host-root session |
| Host root (owner break-glass) | execute witness owner ops, install files, run ceremonies. Level 3: can read runtime credentials and forge the witness with K-WIT | authorize a registry transition or an epoch advance (needs K-ROOT) |
| `lilith-authority-dev` (signer uid) | journal ledger ops; submit `RECORD_LEDGER_ADVANCE` | change the epoch or the floor; rewrite the witness; load a key other than its one slot. Worst case: availability loss (B1b-3d §9) |
| `lilith-recovery-witness` | sign witness successors | sign evidence or registries (`WITNESS_KEY_IS_AUTHORITY_KEY`); read the ledger or K-ACT |
| `lilith`, Hermes, the model, the routine deployer | nothing in this record | request, authorize, execute, or verify any transition (B1b-3d §7, §8; DR-5 closed for the deployer) |

### Unresolved risks

1. **Whole-host / whole-snapshot rollback (OPEN).** B1b-3e introduces no
   independent surviving state owner, so it claims no protection. Every
   candidate anchor from B1b-3c §16 remains unselected:
   - an off-host monotonic witness;
   - an owner-held checkpoint;
   - an external monotonic service;
   - a hardware counter.

   An owner-held "last witness digest I saw" is the cheapest candidate
   (RR-12). It would need its own design, and it would still detect only at
   the next owner check.
2. **Compromise is retroactive** (C-1). One leaked key erases the historical
   validity of all its evidence until re-attestation exists.
3. **Retained key material in snapshots** (§8.4, RR-7). Destruction from
   active custody is not destruction of the key.
4. **Same-version registry fork** (F16) until RR-4 is adopted.
5. **No authorization expiry** (RR-2). A signed, unexecuted
   authorization stays executable until superseded.
6. **Per-transition witnessing cost** (T-4). Some crashes escalate to an
   epoch advance, which burns in-flight owner proofs.
7. **DR-3** (`ubuntu` root-equivalent) and Level 3 remain OPEN.
8. **Signer-controlled time.** `issuedAt` is untrusted, so `t_cut` relies on
   the ledger's recorded evidence plus the hold, not on clocks.

## 13. Explicit non-claims and out of scope

B1b-3e does **not** claim, design, or authorize any of the following:

- PROD authority, or closure of `CROSS_ENVIRONMENT_PROD_AUTHORITY_DEBT`;
- real-owner-grade key custody, or a real registry root;
- First Memory or any accepted-memory transition;
- signer activation, an activation grant, or witness installation;
- Privacy key custody or a Privacy boundary source (B1b-3f);
- WebAuthn ceremony, RP, or authenticator changes;
- a Stage III retry or arm;
- a whole-host rollback solution;
- memory zeroization or remanence elimination;
- consciousness, personhood, or identity claims about LILITH;
- automatic authority recovery from backups. There is none: every recovery
  is an owner ceremony with K-ROOT authorization;
- any live mutation, key generation, rotation, revocation, restore, or
  ceremony.

## 14. Proposed follow-on source slice (B1b-3e-S, TEST-only)

This slice is not authorized by this record. It needs its own review and PR.
It would live under `services/owner-memory-control/` and
`services/authority-dev/`. Nothing would go under `services/core-api/**` or
`services/memory-broker/`.

1. `verify_registry_succession` (§6.5): a closed reason set, golden vectors,
   and a negative matrix (deleted record, mutated immutable field, reopened
   lifecycle, cleared compromise, `ROUTINE → COMPROMISED` escalation, version
   gap, two current keys).
2. A DEV_SYNTHETIC profile check: exactly one current OWNER_ACTOR key (RR-3).
   This tightens B1b-3c's "at least one" for the profile only. The B1b-3a
   verifier is not changed.
3. In-epoch rotation through the existing `REGISTRY_VIEW` op in the TEST
   ledger model, with a test for every §7.5 crash point. It must show that
   predecessor evidence with `issuedAt < t_cut` is reservable and confirmable
   after rotation, and that a successor in `S_PREPARED`/`S_AUTHORIZED`/
   `S_PUBLISHED` can never pass readiness.
4. `AuthorityKeyTransitionV1` (§7.6) as a verifier-side record builder.
5. `registryDigest` in the journal payloads plus the profile readiness reason
   (RR-4). The B1b-3c taxonomy and vectors are unchanged.
6. The re-sequenced epoch-advance ceremony (RR-5), tested against the B1b-3c
   `witness_succession_reason`, including an advance on a **current**
   (unrestored) ledger.
7. The `AuthorityTransitionHoldV1` schema (§9).
8. Pins: the B2a, B1b-3a, B1b-3b, and B1b-3c golden files and their SHA-256
   pins stay unchanged. The authority-dev `release_file_set.py` shared-contract
   pins change only if a shared contract module changes (it should not).

A **live** rotation or epoch-advance rehearsal (B1b-3e-L) needs all of:

- the B1b-3d L3a–L4 prerequisites, live and accepted;
- a successor-slot keygen form. The L2b keygen refuses a non-empty credstore,
  and the L2 `RELEASE_SET` rule is initial-custody only (RR-11);
- its own one-mutation-per-step owner ladder.

It is not designed here.

## 15. Acceptance criteria for design closure

This design record is closed (as a design) when the owner confirms each item:

1. §1 is correct: K-ACT is custody-only, and no registry, witness, or ledger
   is live.
2. The §6.1 transition vocabulary and the RR-10 usage rule are accepted.
3. C-1 is resolved: compromise stays retroactive (recommended), or a
   re-attestation design is commissioned first.
4. The §6.5 additive-history rule is accepted as a required source contract.
5. The §7.2 rotation state machine is accepted, with its two
   "current" events: verification-current (floor raise) and issuance-current
   (witnessed `REGISTRY_VIEW`).
6. RR-3 (single current key) is decided.
7. The §8 restore taxonomy and `RESTORE != AUTHORITY RESTORATION` are
   accepted without exception.
8. The §9 object mapping is accepted (hold as request, registry as
   authorization, witness as executor, verifier as verification). RR-2 is
   decided.
9. C-4 / RR-5 ordering is decided.
10. The §10 forbidden-transition list is accepted.
11. The §11 failure matrix is accepted. F11 and F16 are acknowledged as
    **not fail-closed** (F16 only until RR-4).
12. The §13 non-claims are unchanged.
13. The §14 follow-on slice is authorized separately, or deferred.

## 16. Unresolved decisions

| # | Decision | Recommendation |
| --- | --- | --- |
| **C-1 / RR-1** | Compromise interval semantics (brief) vs retroactive compromise (B1b-3a source) | keep retroactive. Interval semantics only after a trusted-ordering re-attestation contract exists |
| RR-2 | A separate owner-signed `EpochAdvanceAuthorization` binding the predecessor witness digest, the reason, and `notAfter`, vs the T-8 registry-as-authorization | keep T-8 for DEV_SYNTHETIC; the witness succession rules bound replay. Revisit before any real authority. Residual: no expiry, and no binding to the predecessor's random |
| RR-3 | Exactly one current OWNER_ACTOR key per registry (profile rule) | yes, for DEV_SYNTHETIC |
| RR-4 | Same-version registry fork detection: `registryDigest` in journal ops (transitively witnessed) vs a `RecoveryWitnessV2` field vs owner discipline only | journal digest. Also: forbid version gaps |
| **C-4 / RR-5** | Epoch-advance ordering: B1b-3c source order vs B1b-3d §13 text | B1b-3c order; re-sequence B1b-3d steps 6–9 in B1b-3e-S |
| RR-6 | Compromise of the issuing key ⇒ mandatory epoch advance (reason `KEY_COMPROMISE`) | yes: in-flight work may have been touched by the key holder |
| RR-7 | Retained or restored key material: inside the owner/root boundary (known debt) vs outside (compromise) | as §8.4 |
| RR-8 | `revokedAt` fixed + `compromisedSince ≤ revokedAt` when compromise is found after a routine revocation | accept the imprecise forensic field in V1; fix only in a new contract version |
| RR-9 | Witness crash between the chain write and the `witness.json` rename | roll forward only to a verified signed chain successor; otherwise break-glass |
| RR-10 | `t_cut` rule; `retiredAt` for rotation; `ROUTINE` for lost or unused keys; `SUPERSEDED` unused | as §6.1 and §7.3 |
| RR-11 | Release-set and keygen contract for a successor credential slot | new reviewed release; defined with B1b-3e-L |
| RR-12 | An owner-held checkpoint as the first whole-host anchor | not selected; needs its own design |

Carried forward unchanged: B1b-3c open decisions 3 (the off-host anchor), 5
(witness write frequency; T-4 kept), 6 (reconciliation), and 7 (the Privacy
boundary, B1b-3f); B1b-3d T-6 (reboot test) and T-9 (`ubuntu`).

## Explicitly not done

- No DEV or PROD contact. No gcloud, SSH, IAP, systemctl, systemd-creds, or
  sudo.
- No key, credential, registry, witness, ledger, or blob generated, rotated,
  revoked, restored, encrypted, decrypted, installed, or activated.
- No change to source, tests, golden vectors, workflows, IAM, WIF, sudoers,
  the broker runtime, Stage III, or activation.
- No change to the B1b-3a, B1b-3c, or B1b-3d records or semantics. Conflicts
  are recorded in §6.3 and §9.2 only.
- No claim of real authority, real-owner custody, First Memory, or
  whole-host rollback protection.
