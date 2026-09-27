# Slice 15B2b-B1b-3e — Live-Rehearsal Entry Gate

Status:

- **DESIGN / LIVE GATE ONLY**
- **NOT SOURCE IMPLEMENTATION**
- **NOT LIVE AUTHORIZATION**
- **OWNER DECISIONS ACCEPTED:** RR-6, RR-7, RR-9, RR-11, RR-17, RR-18, RR-19,
  RR-20a, RR-20b, RR-21. **RR-16 CLOSED** by RR-6 (§13)
- **DO NOT ENTER LIVE REHEARSAL** until the source and preparation work of §14
  is implemented, test-proven, reviewed, and accepted
- **WHOLE-HOST ROLLBACK UNRESOLVED**
- **REAL AUTHORITY ABSENT**

Base: protected main `918a7b1bde9d7dcbd9036a55ffe408e643192805`. First draft
`0a66b12`; this revision is the owner-decision closure pass.

This record defines the conditions under which a future DEV_SYNTHETIC live
rehearsal of B1b-3e **may be designed**. It builds on:

- the merged [B1b-3e design record](slice-15b2b-b1b3e-rotation-revocation-recovery.md)
  ("the design"), which left RR-6, RR-7, RR-9, and RR-11 as
  `BLOCKING_BEFORE_LIVE_3E`;
- the merged [B1b-3e source contracts](slice-15b2b-b1b3e-source-contracts.md)
  ("B1b-3e-S"), TEST-only;
- the [B1b-3c recovery epoch and witness](slice-15b2b-b1b3c-recovery-epoch-witness.md)
  record;
- the B1b-3d [custody design](slice-15b2b-b1b3d-dev-synthetic-custody-design.md),
  [L2 custody preparation](slice-15b2b-b1b3d-l2-custody-preparation.md),
  [live closure](slice-15b2b-b1b3d-live-closure.md), and
  [deployer boundary](slice-15b2b-b1b3d-deployer-authority-boundary.md)
  records.

It is not an acceptance of any live state, a ceremony runbook, an activation
instruction, or an implementation authorization. It contains no commands.

Nothing was contacted or changed: no DEV, PROD, gcloud, SSH, IAP, sudo,
systemctl, or systemd-creds; no key, credential, registry, witness, ledger,
broker, L04, IAM, WIF, or sudoers; no Stage III; no First Memory. No source,
test, vector, workflow, or earlier record was changed.

Labels:

| Label | Meaning |
| --- | --- |
| **CANONICAL** | defined by accepted records or protected-main source |
| **SOURCE FACT** | read from current source at the base above |
| **OWNER-ACCEPTED** | an owner decision recorded in this closure pass (§13). The accepted property is binding for the follow-on work of §14; exact schemas and layouts stay source work |
| **SOURCE WORK REQUIRED** | implied by an accepted decision; not implemented; blocks live entry (§14) |
| **OPEN DETAIL** | a choice the accepted decisions do not fix. It must be fixed and reviewed in the named source slice. It is not accepted here |

## 1. Controlling source facts

Current source is the authority for current behaviour.

| # | Source fact | Location |
| --- | --- | --- |
| SF-1 | The keygen has exactly one form (`actor`), a fixed key ID `test-only.dev-synthetic.actor.b1b3d.1`, a fixed blob path in `/etc/credstore.encrypted`, and refuses `CREDSTORE_NOT_EMPTY` | `services/authority-dev/ceremony/lilith_authority_keygen_dev.py:65`, `:70-71`, `:161-166`, `:206-207` |
| SF-2 | The installer's `RELEASE_SET` check requires exactly one installed release; its own comment says B1b-3e may define a different release-set contract. The keygen CLI is written once (collision refused) | `services/authority-dev/ceremony/install_authority_dev.py:437-445`, `:589-594` |
| SF-3 | The signer unit loads exactly one credential, `owner-actor-signing-key`, from exactly one path, and has `/etc/credstore.encrypted` in `InaccessiblePaths` | `services/authority-dev/deploy/lilith-authority-dev.service` |
| SF-4 | The signer reads only `$CREDENTIALS_DIRECTORY/owner-actor-signing-key`; `HEALTH.publicKeySha256` is derived from the loaded key. L1 has no signing, no ledger, no witness client; readiness is always `NOT_READY` | `services/authority-dev/lilith_authority_dev/credential.py`, `core.py` |
| SF-5 | `evaluate_rotation` requires the candidate's predecessor to be `SUPERSEDED` (`CANDIDATE_PREDECESSOR_NOT_SUPERSEDED`). It evaluates in-epoch rotation only. Aborts are allowed only up to `S_AUTHORIZED` | `services/owner-memory-control/lilith_owner_memory/rotation_contracts.py:1345`, `:1553` |
| SF-6 | `HEAD_ADVANCE_REASONS` includes `COMPROMISE_MARKING`; `EPOCH_ADVANCE_REASONS` includes `KEY_COMPROMISE`. The head-advance planner does not require the target to have a current key; the epoch planner does (`TARGET_HAS_NO_ISSUANCE_KEY`) | `rotation_contracts.py:79-83`, `:975-1018`, `:1055` |
| SF-7 | `witness_v2_succession_reason` requires a transition entry to **name** a consumed authorization; it does **not** verify that authorization ("the executor's check"). Chain facts establish linearity and single use only | `rotation_contracts.py:687-738`, `:775-792` |
| SF-8 | `verify_loaded_key_binding` takes B1–B4 only. It has no input for the systemd credential name or for a credential-store inventory | `rotation_contracts.py:1265-1327` |
| SF-9 | The only `RecoveryWitnessV2` writer is TEST-only and keeps its chain in memory. No durable chain/pointer writer, witness service, or K-WIT custody code exists in the repository | `services/owner-memory-control/lilith_authority_signer/synthetic_witness_v2.py:69` |
| SF-10 | `verify_registry_succession` allows `null → (t, COMPROMISED)` and the escalation `ROUTINE`/`SUPERSEDED` → `COMPROMISED`; a compromise is never cleared | `rotation_contracts.py:249-273` |
| SF-11 | No source contract exists for `CeremonyHoldV1` or `AuthorityKeyTransitionV1` (design §15 item 8), and no evaluator takes an epoch-advance successor path to `S_CURRENT`. `plan_epoch_advance`, `adopt_authorized_epoch`, and `verify_loaded_key_binding` exist as separate pure pieces | `rotation_contracts.py`, `synthetic_witness_v2.py` |

**Live baseline (CANONICAL, live closure §4, §6).** Only the K-ACT
host-bound blob, `credential.secret`, the `lilith-authority-dev` account, the
release, and inactive units exist on DEV. No registry, anchor, K-WIT,
witness, or authority recovery ledger exists. K-ACT is not an authority key.
Activation is `NOT_ACCEPTED reason=GRANT_ABSENT`. B1b-3d L3a–L4 are neither
implemented as a service (SF-9) nor live.

## 2. Design/source conflicts and their resolution

| # | Conflict | Resolution |
| --- | --- | --- |
| GC-1 | The design §7.4 step 5 destroys P's blob at `S_ACTIVATED`, before `S_CURRENT` | **RR-11 accepted:** P stays retained and non-loadable through cutover and is destroyed only after independently verified `S_CURRENT`. For future implementation this supersedes the destruction timing of the design §7.4 step 5 (the design record is not edited). **SOURCE WORK REQUIRED** (§14 SW-1) |
| GC-2 | The B1b-3d §13 step 5a puts the successor blob `…owner-actor.next.cred` inside `/etc/credstore.encrypted`; the keygen refuses a non-empty credstore (SF-1); the design §11.2 binding requires no other authority blob there | **RR-11 accepted:** a separate root-only preparation directory on the same filesystem. Supersedes the B1b-3d §13 step 5a location for B1b-3e (not edited). **SOURCE WORK REQUIRED** (SW-2) |
| GC-3 | The design §11.2 conditions "fixed credential name" and "no other authority blob" are not implemented by `verify_loaded_key_binding` (SF-8) | **RR-19 accepted:** a credential-slot inventory is a fail-closed readiness condition. **SOURCE WORK REQUIRED** (SW-3, SW-6) |
| GC-4 | The B1b-3d §10 witness is V1 (`RAISE_REGISTRY_FLOOR`, V1 `ADVANCE_EPOCH`); no record fixed the live bootstrap schema | **RR-18 accepted:** the live witness begins at `RecoveryWitnessV2` genesis. Resolved; SW-4 implements it |
| GC-5 | The B1b-3d §10 update order has no fsync of the `chain/` directory before the pointer rename | **RR-9 accepted:** the directory fsync is part of the commit point. **SOURCE WORK REQUIRED** (SW-5) |
| GC-6 | The design §16 recommended RR-6 "always (fail closed)" | **Superseded by accepted RR-6** (option C, §4.4) for B1b-3e live work. The design record is not edited |
| GC-7 | `evaluate_rotation` cannot evaluate an in-epoch compromise-plus-successor transition (SF-5) | **RR-16 closed by RR-6:** no such transition contract is introduced. The accepted current-key path is marking + `KEY_COMPROMISE` epoch advance; its source gaps are implementation work (SW-9) |

## 3. Invariants

Inherited and preserved without change:

```text
model proposal              != authority
execution                   != verification
credential exists           != accepted authority
credential loaded           != current authority
signer claim                != independent verification
registry publication        != activation
witness freshness           != authority
K-ROOT authorization        != witness execution
REGISTRY_VIEW               != authority
storage                     != acceptance
restore                     != authority restoration
historical validity         != current authority
routine deployment          != authority mutation
PREPARED may be voided
CONSUMED never reopens
authority history is additive
whole-host rollback remains unresolved
same-host witness protects only while it survives
```

The B1b-3a rule is preserved: **a COMPROMISED issuing key ⇒ all evidence
under that key is `KEY_COMPROMISED`** (C-1). Nothing here weakens it.

Pinned by this gate:

```text
epoch advancement            != custody repair
epoch advancement            != key-compromise repair
K-WIT assertion              != K-ROOT authorization
freshness                    != authority
source tests pass            != live entry
retained ciphertext          != automatically safe
restored credential          != restored authority
private material exposure    != ordinary retirement
witness pointer              != witness state
chain entry exists           != committed transition
file exists / newest mtime   != current
successor slot filled        != successor authorized
inventory result             != authority
genesis pinned               != external monotonicity
```

## 4. RR-6 — compromise and epoch advance (OWNER-ACCEPTED)

### 4.1 What a RecoveryEpoch advance actually does

From B1b-3c §10, the design §9, and SF-6, an epoch advance does exactly four
things:

| # | Effect | Mechanism |
| --- | --- | --- |
| E1 | voids old-epoch `PREPARED` challenges and quarantines `RESERVED` uses, so in-flight work needs owner re-authorization | `VOID_CHALLENGE`, `QUARANTINE_USE` |
| E2 | makes every old-epoch challenge, evidence, and reservation unusable for creation | `STALE_EPOCH_*`, `CHALLENGE_EPOCH_NOT_CURRENT` |
| E3 | makes every E(n) key non-current; the target registry must name a current key at E(n+1) | registry invariants; `TARGET_HAS_NO_ISSUANCE_KEY` |
| E4 | re-anchors the authority recovery ledger. A ledger ahead of the witness is resolvable only by an advance | `LEDGER_AHEAD_OF_WITNESS` |

It does **not**:

- **repair a compromised key.** Evidence rejection comes from the K-ROOT
  `COMPROMISED` marking (C-1);
- **repair custody.** The advance is journalled by the signer and executed by
  the witness, both inside the host-root boundary, and the successor key is
  generated there too;
- change historical evidence (history is retained);
- detect or repair whole-host rollback.

**Does advancing RecoveryEpoch provide any protection if the same compromised
custody boundary can also mint the next key? No.** Only K-ROOT (offline)
stays outside that boundary. Custody must be re-established by a separately
reviewed recovery path.

### 4.2 Suspect-state sets

| Set | Suspect state | Remedy |
| --- | --- | --- |
| K | issuing-key private material | K-ROOT `COMPROMISED` marking |
| L | in-flight authority recovery ledger state from an unknown exposure window | epoch advance (E1–E4) |
| B | the custody boundary: host root, `credential.secret` outside the accepted boundary, K-WIT, the witness chain | **STOP**; re-establish custody (separately reviewed) |
| R | K-ROOT | **STOP**; re-establish trust root (separately reviewed) |

### 4.3 Scenario analysis

"Rejected now?" means rejected by the verifier. That happens only when a
registry marking the key `COMPROMISED` is the witnessed head. Until then
containment is operational: the hold, a stopped signer, and the acceptance
chain (`RESERVE` needs an `ISSUE` record in the authority recovery ledger).

| # | Scenario | Compromised state | Rejected now? | Rotation sufficient? | Epoch advance | Owner re-auth? | Historical evidence | Witness trustworthy? | Rehearsal |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| S1 | routine successor rotation | none | no | yes (in-epoch, `SUPERSEDED`) | **not** for rotation | no (in-flight preserved) | unchanged | yes | this is the rehearsal |
| S2 | administrative revocation | none | forward only: `issuedAt ≥ revokedAt` | yes (`ROUTINE` head advance; a successor if issuance must continue) | **not** for administrative revocation | only for work needing a signature before a successor exists | unchanged | yes | may continue |
| S3 | confirmed private-key disclosure of the **current** key outside custody | K + L | after the marking head | **no** (`SUPERSEDED` would keep backdated forgeries in `[notBefore, t_cut)` valid) | **REQUIRED**, `KEY_COMPROMISE` | yes (E1) | **all** of the key's evidence → `KEY_COMPROMISED`, including accepted history | yes, only if the vector is shown key-only; otherwise S8/S9 | **stop** the rotation rehearsal; compromise recovery is its own ladder |
| S4 | suspected disclosure without proof | unknown | no | not until classified | not until classified | not until classified | unchanged until classified | provisionally | **hold / fail closed** until classification is resolved |
| S5 | stale retired credential restored inside the same host/root boundary | none new (`KNOWN_CUSTODY_DEBT`, or `STALE_CREDENTIAL_PRESENT` if in the unit slot) | P already non-current; a loaded P fails the binding | n/a | no. Yes only if the restore also rewound the ledger (B1b-3c) | no | unchanged | yes, if the witness was not restored | stop the phase; remove it; re-verify binding and inventory; establish the copy's source |
| S6 | stale retired credential observed outside the custody boundary | K for a **non-current** key | after the marking head | n/a | **no**: in-epoch `COMPROMISED` marking is sufficient, unless another state domain is independently suspect (then S8 or S9) | no | **all** of P's evidence → `KEY_COMPROMISED` (`SUPERSEDED` → `COMPROMISED`, SF-10); accepted history from P is lost | yes | stop; marking head advance; resume after |
| S7 | snapshot with the encrypted blob only | none, while `credential.secret` has never left the accepted boundary | no | n/a | no | no | unchanged | yes | per the RR-17 inventory (§5.6) |
| S8 | snapshot with the blob **and** `credential.secret` | inside an explicitly accepted, inventoried environment: `KNOWN_CUSTODY_DEBT` (RR-17). **Outside** it: every key under that host key (K-ACT; K-WIT if present) and the host key itself | after the marking head | **no** | **no remedy**: rotating the host key alone is **not** sufficient (RR-20b) | yes | all evidence of the exposed keys → `KEY_COMPROMISED` | **no**, if K-WIT was in the snapshot | outside the accepted environment: **STOP**; re-establish custody with fresh custody material |
| S9 | root compromise while the host runs | B | after the marking head (K-ROOT is offline) | no | **no remedy** (§4.1) | yes | all K-ACT evidence → `KEY_COMPROMISED` | **no** | **STOP**; re-establish custody |
| S10 | compromise of K-ROOT | R | not by any current mechanism | no | **no remedy** (K-ROOT authorizes it) | yes | post-onset registries are unverifiable | **no** (it executes attacker-signed authorizations) | **STOP**; re-establish trust root |
| S11 | compromise of K-WIT | B for freshness: forks from any past entry; promotion of staged candidates with a fake ID (SF-7) unless RR-20a is enforced | K-ACT evidence not `KEY_COMPROMISED` unless K-ACT also exposed | n/a | **no remedy** (the witness executes it) | yes | unchanged cryptographically; freshness history untrusted | **no** | **STOP**; re-establish witness custody |
| S12 | compromise of only the OWNER_ACTOR issuing key (current), with K-WIT, K-ROOT, `credential.secret`, and the ledger shown unaffected | K + L | after the marking head | no | **REQUIRED**, `KEY_COMPROMISE` | yes (E1) | all K-ACT evidence → `KEY_COMPROMISED` | yes | stop the rotation rehearsal; compromise recovery is its own ladder |

### 4.4 Accepted rule

**OWNER-ACCEPTED: option C.**

1. **Routine rotation:** no RecoveryEpoch advance solely because of rotation.
2. **Administrative non-compromise revocation:** no RecoveryEpoch advance
   solely because of it.
3. **Compromise of the CURRENT issuing key:** a RecoveryEpoch advance is
   **REQUIRED**, reason `KEY_COMPROMISE`. The advance burns and quarantines
   stale in-flight authority state. It does **not** repair the key. The key
   must still be marked `COMPROMISED`, and its evidence stays
   `KEY_COMPROMISED` under B1b-3a.
4. **Compromise of a NON-CURRENT key:** in-epoch `COMPROMISED` marking is
   sufficient, unless another state domain is independently suspect.
5. **Root, host custody boundary, K-ROOT, or K-WIT compromise:** **STOP.**
   Neither ordinary rotation nor epoch advancement is remediation. Custody is
   re-established only under a separately reviewed recovery path.
6. **Suspected compromise:** hold and fail closed until classification is
   resolved.

The accepted current-key path (from RR-16's closure):

```text
current issuing key compromised
    -> COMPROMISED marking
    -> KEY_COMPROMISE RecoveryEpoch advance
    -> recovery successor path

non-current key compromised
    -> in-epoch COMPROMISED marking
```

The marking must precede or accompany the epoch advance. Current source
supports both a separate `COMPROMISE_MARKING` head advance followed by the
epoch advance, and an epoch-advance target registry that itself carries the
marking (SF-6, SF-10). Which form the recovery path uses is an **OPEN DETAIL**
of SW-9. It is not a new authority path.

## 5. RR-7 — retained and restored key material (OWNER-ACCEPTED)

### 5.1 Custody boundary

For DEV_SYNTHETIC, the **custody boundary** of K-ACT (and later K-WIT) is the
running DEV VM's root principal and its local disk, which holds
`/var/lib/systemd/credential.secret`: the same boundary that holds the current
key.

Outside it: any other host; the owner workstation; GitHub and CI; logs and
transcripts; and cloud or disk snapshots. Under RR-17, snapshots are **not**
automatically inside the boundary. An owner may accept a specific,
inventoried snapshot environment as bounded (§5.6).

Host-key encryption means: **a blob is exactly as secret as the
`credential.secret` it can be combined with.** systemd encrypted credentials
do not protect against a whole-disk snapshot containing both halves.

### 5.2 Closed classification

Classes apply per artifact. They are evaluated most severe first; the first
match wins. A key's action follows its worst artifact.

| # | Class | Definition (every condition must hold) |
| --- | --- | --- |
| 1 | `COMPROMISED` | an authority outcome: the K-ROOT registry at the witnessed head records `revocationReason = COMPROMISED`. Also used, per RR-17, for an uncontrolled copy known to be decryptable by an unaccepted party. Terminal (SF-10) |
| 2 | `EXPOSED_PRIVATE_MATERIAL` | plaintext private material (PKCS#8 DER, seed, raw private bytes) was observable outside the L2 §6 transient path (keygen and `systemd-creds` process memory, the kernel pipe, the running unit's `$CREDENTIALS_DIRECTORY`); **or** ciphertext and its decrypting `credential.secret` exist together, or could be combined, outside both the custody boundary and any explicitly accepted, inventoried environment |
| 3 | `UNKNOWN_PROVENANCE` | existence, copy history, location, access history, or co-location with the host key cannot be established from records. Includes a blob matching no publication and any snapshot not in the inventory. **Fails closed; treated as exposure until proved otherwise** |
| 4 | `STALE_CREDENTIAL_PRESENT` | a blob of a key that is not the single current key at the witnessed head is in the CURRENT slot, or in any path a unit's `LoadCredentialEncrypted=` references |
| 5 | `KNOWN_CUSTODY_DEBT` | known provenance (hash matches a publication, or the snapshot is inventoried); decryptable only inside the custody boundary or an explicitly accepted, inventoried environment; never observable elsewhere; in no unit slot. **Must be explicitly bounded and documented** |
| 6 | `SAFE_RETAINED_CIPHERTEXT` | known provenance; ciphertext only; its decrypting host key is not with it and cannot be obtained by the copy's holder; `credential.secret` has never left the accepted boundary; owner-controlled. **Conditional:** any later exposure of `credential.secret` reclassifies every such copy |

No class exists for "probably safe". Plaintext is never below class 2.

Authority action also depends on the key's status at the witnessed head:
`CURRENT`; `NON_CURRENT` (`SUPERSEDED`, `ROUTINE`, retired); or
`NOT_IN_HEAD` (never named by an executed head; evidence `KEY_UNKNOWN`).

### 5.3 Action per class

| Class | Authority impact | Destroy? | Destruction sufficient? | Permanent `COMPROMISED`? | Epoch advance? | Live entry (current key) | Evidence to resume |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `COMPROMISED` | all of the key's evidence rejected | yes, from active custody | irrelevant to authority | already | current key: **required** (RR-6) | **blocked** | marking head; RR-6 path completed |
| `EXPOSED_PRIVATE_MATERIAL` | `CURRENT`/`NON_CURRENT` → must become `COMPROMISED`. `NOT_IN_HEAD` → must never be published | yes | **no** | yes (not for `NOT_IN_HEAD`) | current key: required. Otherwise no | **blocked** | marking head; for a host-key exposure, RR-20b re-custody |
| `UNKNOWN_PROVENANCE` | treated as exposure | yes, once preserved as evidence | no | as exposure, unless proved lower | as exposure | **blocked** | an owner-accepted record proving a lower class |
| `STALE_CREDENTIAL_PRESENT` | none; binding and inventory fail → `NOT_READY` | remove from the slot; classify the source copy | yes, for the slot | no (unless the source copy is class 2 or 3) | no | **blocked** | slot holds exactly the current publication's blob; binding + inventory re-verified |
| `KNOWN_CUSTODY_DEBT` | none now; a later disclosure could forge backdated evidence inside a `SUPERSEDED` interval | yes, at predecessor retirement (after `S_CURRENT`) | reduces exposure; not proof (no zeroization) | no | no | **allowed, if explicitly bounded and documented** | debt named in the transition record and the entry nonclaims |
| `SAFE_RETAINED_CIPHERTEXT` | none, conditionally | recommended (it breaks the no-backup policy) | n/a | no | no | **allowed** | owner record of location, holder, and non-export of `credential.secret` |

### 5.4 Cases

| Case | Class | Notes |
| --- | --- | --- |
| encrypted blob copied inside root-only same-host custody | `KNOWN_CUSTODY_DEBT` if deliberate and recorded; `UNKNOWN_PROVENANCE` if unexplained | breaks the B1b-3d §16 no-backup policy |
| encrypted blob copied off-host | `SAFE_RETAINED_CIPHERTEXT` only if owner-controlled, recorded, and without `credential.secret`; otherwise `UNKNOWN_PROVENANCE` | |
| blob + matching `credential.secret` together | inside an accepted, inventoried environment: at least `KNOWN_CUSTODY_DEBT`. Otherwise `EXPOSED_PRIVATE_MATERIAL` for every key under that host key | RR-17, RR-20b |
| plaintext ever observable | `EXPOSED_PRIVATE_MATERIAL` | |
| backup made before rotation, restored after the successor is current | backup: by location. Restore into the slot: `STALE_CREDENTIAL_PRESENT` | `restored credential != restored authority` |
| old encrypted credential left on disk after rotation | `KNOWN_CUSTODY_DEBT` | destroyed only after `S_CURRENT` (RR-11) |
| old credential reintroduced into the CURRENT slot | `STALE_CREDENTIAL_PRESENT`, plus the source copy's class | binding and inventory fail |
| old credential available but not loadable | `KNOWN_CUSTODY_DEBT` if root can still decrypt it; never `SAFE` by assertion | "not loadable" ≠ "not decryptable" |
| successor generated but never authorized | `KNOWN_CUSTODY_DEBT`, `NOT_IN_HEAD` | destroy only after confirming no unexpired head authorization targets a candidate naming it |
| abandoned successor after a failed ceremony | as above if `NOT_IN_HEAD`; a partial blob with no publication is `UNKNOWN_PROVENANCE` (no authority effect, the key is unregistered). If `S_PUBLISHED` was reached, S is `CURRENT` and cannot be abandoned by deletion (F14/F15) | |
| owner-controlled offline archival copy | ciphertext only: `SAFE_RETAINED_CIPHERTEXT` (conditional). With `credential.secret`: class 2, unless the owner accepts that environment under RR-17, then at least class 5 | recommend no archival copies |
| hypervisor / disk snapshot | per the RR-17 inventory (§5.6) | |
| full-machine snapshot restored with the witness also rolled back | not classifiable from inside the host | whole-host rollback; **unresolved** |

### 5.5 Accepted entry rule

**OWNER-ACCEPTED.** Live rehearsal entry for **CURRENT** key material is
allowed only when every artifact is `SAFE_RETAINED_CIPHERTEXT`, or
`KNOWN_CUSTODY_DEBT` that is explicitly bounded and documented. Every more
severe class blocks entry. `UNKNOWN_PROVENANCE` fails closed and is treated as
exposure until proved otherwise.

### 5.6 RR-17 — snapshot classification (OWNER-ACCEPTED)

Snapshots are not automatically inside the same-host custody boundary. **A
complete snapshot inventory is REQUIRED before live entry** (§14 PR-2). It is
a separately authorized, read-only preparation step.

| Snapshot kind | Minimum class |
| --- | --- |
| encrypted credential blob only | `SAFE_RETAINED_CIPHERTEXT` if the §5.2 class-6 conditions hold; otherwise `UNKNOWN_PROVENANCE` |
| credential blob + `credential.secret` | **at least `KNOWN_CUSTODY_DEBT`**, and only if it lies within an explicitly accepted, inventoried environment. Outside it: `EXPOSED_PRIVATE_MATERIAL` → RR-20b STOP |
| unknown access history | `UNKNOWN_PROVENANCE` (fails closed) |
| restored after key succession | the restored slot content is `STALE_CREDENTIAL_PRESENT`; the snapshot itself is classified by its contents and location. If it also restored the witness: whole-host rollback, unresolved |
| accessible by principals outside the accepted custody boundary | with both halves: `EXPOSED_PRIVATE_MATERIAL`, or `COMPROMISED` once marked. With ciphertext only: `UNKNOWN_PROVENANCE` |

**RR-20b (OWNER-ACCEPTED).** If a snapshot exposure includes both protected
credential material and the host credential secret outside the accepted
custody boundary, rotating the host key alone is **not** claimed sufficient.
The rehearsal **STOPs**, and custody is re-established through a reviewed
recovery procedure with fresh custody material as required. A bounded, known
snapshot within an explicitly accepted environment may remain
`KNOWN_CUSTODY_DEBT`, but it must be inventoried.

## 6. RR-9 — witness crash and torn publication (OWNER-ACCEPTED)

### 6.1 State owner and artifacts

The sole writer is the witness service identity `lilith-recovery-witness`:
single instance, serialized requests, `flock` (B1b-3d §10).

| Artifact | Role |
| --- | --- |
| `chain/<v>.json` | **authoritative** durable freshness state. Append-only, created `O_EXCL`, never overwritten or deleted. One entry per version |
| retained authorization bytes for each transition entry | the exact signed K-ROOT authorization the witness verified before signing that entry (RR-20a retention, §6.8). Written durably before the chain entry. Story-4 bytes: evidence for re-verification, never authority |
| `witness.json` | the **active pointer**: derived state only. `witness pointer != witness state` |
| `.witness.json.tmp` | scratch. Never authoritative |
| `witness.lock` | serialization only |

Readers (the signer and the independent verifier) never trust the pointer
alone. They verify the chain from genesis and compare. Pointer ≠ chain head
⇒ `NOT_READY (WITNESS_POINTER_STALE)`. Readers never repair.

### 6.2 Commit point

A witness successor is **committed** only when all of these hold:

1. the successor bytes are complete;
2. its K-WIT signature verifies;
3. the file contents are durably fsynced;
4. the containing `chain/` directory entry is durably fsynced (GC-5).

The write order: verify succession → sign → durably retain the authorization
bytes → create `chain/<v+1>.json` (`O_EXCL`), write, `fsync` the file →
`fsync` the `chain/` directory → write tmp, `fsync` → `rename` to
`witness.json` → `fsync` the state directory → reply.

Replacing the pointer is publication, not commit. A signed successor that did
not reach the commit point is not committed and was never returned.

### 6.3 Recovery algorithm

The witness service runs it at start, holding the lock, before serving any
operation. **Recovery never signs and never uses K-WIT.** It writes only the
pointer, by the tmp/fsync/rename/fsync steps, to a value derived from the
chain. It is idempotent; a restart during recovery re-runs it to the same
result.

```text
R1 DISCOVER   every entry in chain/ (O_NOFOLLOW; regular files only; unexpected names -> fail closed),
              the retained authorization bytes, witness.json, .witness.json.tmp
R2 VERIFY     each chain entry alone: V2 schema, K-WIT signature under the pinned anchor, environment,
              witness key not an authority key, filename number == witnessVersion -> VALID | INVALID
R3 LINEAGE    from the genesis entry, whose digest must equal the owner-pinned genesis digest (RR-21),
              follow previousWitnessDigest: version k's candidates are VALID entries whose predecessor is
              the unique entry at k-1 and whose witness_v2_succession_reason is None
R4 FACTS      witness_v2_chain_facts (linear; no CHAIN_AUTHORIZATION_REPLAYED), and the authorization
              history: every transition entry's retained authorization re-verifies (RR-20a, §6.8)
R5 HEAD       H = the last version with exactly one valid candidate; classify anomalies (table below)
R6 POINTER    compare the derived active pointer with H
R7 DECIDE     roll forward (pointer := H) | CONSISTENT | FAIL_CLOSED(reason)
```

Never mtime. Never filename order. Never last file wins. **Never roll
backward automatically.**

| Observation | Classification | Outcome |
| --- | --- | --- |
| pointer byte-equal to entry H | `CONSISTENT` | none |
| pointer byte-equal to entry H−1; H committed, unique, linked, succession OK, authorization re-verifies, ID not consumed earlier | `POINTER_BEHIND_BY_ONE` | **roll forward (automatic)** |
| pointer missing or unparseable; chain healthy | `POINTER_MISSING` / `POINTER_CORRUPT` | roll forward from H (automatic) |
| pointer older than H−1 | `POINTER_BEHIND_MULTI` | fail closed; owner |
| pointer is a VALID witness at H+1, not in the chain | `POINTER_AHEAD` (ordering violation) | **fail closed; no rollback**; owner. A possible owner-authorized repair is re-appending the byte-identical document, with no new signature |
| two VALID linked entries at one version (chain, pointer, or tmp) | `FORK` | fail closed; OWNER + K-ROOT (§8) |
| INVALID entry at a version ≤ H | `CHAIN_CORRUPT` | fail closed; owner |
| INVALID entry at H+1, pointer == H | `TORN_TAIL` (not committed) | refuse writes; owner sets the bytes aside, preserved outside the lineage. The same authorization stays executable (prior head unchanged) |
| VALID entries unlinked or beyond a gap | `ORPHAN` | fail closed; owner |
| `CHAIN_AUTHORIZATION_REPLAYED` | `REPLAY_IN_CHAIN` | fail closed; owner |
| a transition entry's retained authorization missing or failing re-verification | `AUTHORIZATION_HISTORY_INVALID` | fail closed; owner (RR-6 S11 if unexplained) |
| genesis digest ≠ owner-pinned digest | `GENESIS_MISMATCH` | fail closed; owner |
| chain empty, pointer present | `CHAIN_MISSING` | fail closed. History is never rebuilt from a pointer; no auto-bootstrap |
| chain and pointer both absent | `UNINITIALIZED` | only the owner `BOOTSTRAP` operation at V2 genesis (RR-18). Never automatic |
| tmp byte-equal to a chain entry, or unparseable with no H+1 candidate | scratch | discard (automatic) |
| tmp is a VALID witness not in the chain | ordering violation | fail closed; preserve |

### 6.4 The ten required cases

| Case | Result |
| --- | --- |
| predecessor active, successor absent | `CONSISTENT` at v. Nothing committed; the authorization is unconsumed and may be re-presented |
| successor committed, pointer still predecessor | `POINTER_BEHIND_BY_ONE` → roll forward. Re-presenting the authorization then gives `AUTHORIZATION_CONSUMED` / `PRIOR_HEAD_MISMATCH` (expected POST evidence) |
| successor written but corrupt or truncated | `TORN_TAIL` → writes refused; owner; no committed state lost |
| pointer replaced, directory fsync lost | after reboot, `CONSISTENT` or `POINTER_BEHIND_BY_ONE` → roll forward; same final state |
| pointer names the successor, chain file missing | `POINTER_AHEAD` → fail closed, no rollback, owner |
| two candidate successors from one predecessor | `FORK` → fail closed; OWNER + K-ROOT |
| successor committed, target registry bytes unavailable | roll forward freshness (the retained authorization binds the target digest). Readiness stays `NOT_READY (REGISTRY_MISSING)` until the owner reinstates head registry bytes that verify at the head |
| target registry available, authorization missing | `AUTHORIZATION_HISTORY_INVALID` → fail closed; owner. A K-WIT entry alone never proves K-ROOT authorization (RR-20a) |
| chain holds a successor whose authorization was already consumed | `REPLAY_IN_CHAIN` → fail closed |
| restart during recovery | idempotent (§6.3) |

### 6.5 Automatic vs owner

- **Automatic:** deriving the pointer from a unique, committed, fully
  verified chain head (roll forward; missing or corrupt pointer);
  discarding scratch.
- **Owner intervention:** fork, corruption, ambiguity, missing authoritative
  chain, invalid lineage, invalid authorization history, and any case that
  moves bytes in the append-only chain directory.

The witness never picks between candidates.

### 6.6 Evidence a future rehearsal must collect

- per chain entry: version, digest, signature result, lineage position,
  authorization re-verification result;
- the pinned genesis digest and the observed one;
- pointer digest; tmp presence;
- the recovery classification before and after;
- proof that recovery changed neither chain length nor any signature;
- for each injected fault (a source-provided fault hook, TEST-proven first):
  the injection point, the observed classification, and the final head;
- `rollbackDetectionScope: LEDGER_ONLY`, `wholeHostRollbackProtected: false`.

**Limit.** No whole-host rollback protection is claimed. A snapshot that
restores chain and pointer together is `CONSISTENT` at an old head.

### 6.7 Source dependency

GC-5 and this algorithm require source work before live entry: a durable
witness writer with the chain-directory fsync, the recovery scan, and fault
tests (§14 SW-5).

### 6.8 RR-20a — authorization-chain re-verification (OWNER-ACCEPTED)

Readiness must independently verify the K-ROOT artifact behind every
authority-changing `RecoveryWitnessV2` transition. A valid K-WIT chain by
itself never proves that a transition was K-ROOT-authorized (SF-7).

```text
K-WIT assertion  != K-ROOT authorization
freshness        != authority
```

For each chain entry with a non-null `consumedAuthorizationId`:

| Transition | Re-verify | Must also equal |
| --- | --- | --- |
| registry-head change (same epoch) | `RegistryHeadAdvanceAuthorizationV1` signature under the pinned `TrustedRegistryRootV1`; environment; root key ID | `authorizationId` = the entry's ID; prior head = the predecessor entry's `(registryVersion, registryDigest)`; target = the entry's head; `recoveryEpoch` = both entries' epoch |
| epoch change | `EpochAdvanceAuthorizationV1` signature under the pinned root; environment; root key ID | `authorizationId` = the entry's ID; `expectedPriorWitnessVersion`/`Digest` = the predecessor entry; `priorRecoveryEpoch` = the predecessor's epoch; `successorRecoveryEpoch` = the entry's epoch; target = the entry's head |

The target registry bytes must verify under K-ROOT at the entry's epoch and
satisfy `verify_registry_succession` from the predecessor head's registry.
Readiness needs them anyway.

**Minimum durable retention**, so the verification is reproducible:

1. **Owner, off-host:** the full signed bytes of every executed
   authorization; every registry generation that ever became head (genesis
   included); and a register recording each item's SHA-256, each issued
   authorization ID (executed or not), and the pinned genesis digest (RR-21).
2. **On-host, witness-owned:** the exact signed authorization bytes for
   every transition entry, retained write-once and made durable before the
   entry commits (§6.2).
3. **On-host, root-owned:** every registry generation that became head
   (B1b-3d §15 already retains all versions).
4. The verifier accepts an on-host copy only if its SHA-256 equals the
   owner register. A mismatch or an absence fails closed. The retained copies
   are story 4: they are evidence, not authority.

The witness records and commits the consumed authorization identity. It
remains freshness and execution evidence, not authority. **SOURCE WORK
REQUIRED** (§14 SW-7).

## 7. RR-11 — successor credential slot and release (OWNER-ACCEPTED)

### 7.1 Accepted rule

A successor requires a **new reviewed, successor-capable authority-dev
release**. The installed release (`9ac7de2`) cannot safely generate a
successor: its key ID and path are fixed, and the keygen refuses a non-empty
store (SF-1). A successor needs a distinct key ID, because a record's public
key is immutable (`SUCCESSION_RECORD_MUTATED`).

Preparation is **side by side**:

- the current credential blob is never overwritten during successor
  preparation;
- the successor sits in a separate root-only preparation slot/directory on
  the same filesystem;
- successor existence does not make it current;
- the current service cannot silently load the successor;
- filenames do not establish authority;
- service restart ordering does not establish authority;
- the old credential stays retained but non-loadable through cutover;
- the old credential is **not** destroyed before the successor reaches
  independently verified `S_CURRENT`;
- only after `S_CURRENT` may predecessor destruction or retirement proceed,
  under the accepted lifecycle rules;
- an abandoned successor may be destroyed without affecting the predecessor.

GC-1 and GC-2 are explicit source blockers (§14 SW-1, SW-2).

### 7.2 Logical roles

| Role | Meaning | Loadable by the signer unit? |
| --- | --- | --- |
| **CURRENT slot** | the single path the unit's `LoadCredentialEncrypted=` references (SF-3), inside `/etc/credstore.encrypted` | yes: it is the only one |
| **PREPARED slot** | one root-only directory outside the credstore, on the same filesystem, for at most one successor blob; referenced by no unit | no |
| **RETIRED holding** | a root-only, non-loadable location for the predecessor blob from cutover until destruction after `S_CURRENT`; plus the predecessor's publication and transcript as records | no |

Exact paths are **OPEN DETAIL** for the successor-capable release (SW-2).

### 7.3 How the properties hold

| Property | Mechanism |
| --- | --- |
| preparation leaves current authority unchanged | the successor keygen writes only the PREPARED slot and never opens the CURRENT slot for writing. Authority comes from the witnessed head, which preparation does not touch |
| existence never makes the successor current | current = `select_current_issuance_key` at the verified head. A blob is the current credential only if its hash equals the head key's publication `blobSha256` (B2 = B3) |
| no silent early load | the unit references only the CURRENT slot. An early move there is a root act that the binding (the successor is not current at the head) and the RR-19 inventory both catch |
| restart order never decides authority | readiness is a pure function of the head registry, the chain, the ledger, the binding inputs, the inventory, and the hold |
| filenames never decide authority | filenames are never inputs; the head digest and publications are |
| rollback identifies the authoritative current credential | before `S_PUBLISHED`: P. From `S_PUBLISHED` on: S, forward only (SF-5). No matching blob ⇒ none, fail closed |
| abandoned successor destroyed safely | the PREPARED slot is disjoint from CURRENT and RETIRED |
| no predecessor destruction before `S_CURRENT` | P moves CURRENT → RETIRED at cutover; destruction is a separate phase after `S_CURRENT` (§11 L3e-12) |

After `S_PUBLISHED`, P is non-current at the witnessed head and can never be
current again (SF-10). The retained P blob is therefore
`KNOWN_CUSTODY_DEBT`: a forensic continuity item, not a rollback resource.

### 7.4 Artifact relationships

| Artifact | Establishes | Does not establish |
| --- | --- | --- |
| reviewed successor-capable release | which code runs; which keygen bytes exist (hash-pinned) | any key, authority, or freshness |
| keygen CLI | that one blob was minted into one slot, plus its public publication | registry membership; current status |
| credential slot | where bytes sit | authority |
| key publication `{publicKey, publicKeySha256, blobSha256}` | the ceremony link from public key to blob (B3) | authority; freshness |
| K-ROOT candidate registry (A) | the authorized key state, if it ever becomes head | head status |
| `RegistryHeadAdvanceAuthorizationV1` (B) | permission for exactly one head advance from an exact prior head | execution |
| `RecoveryWitnessV2` entry | that (B) was executed; the head is now the candidate | K-ROOT authorization (RR-20a); readiness; activation |
| `HEALTH` fingerprint | the signer's claim about the key it loaded (B4) | independent verification |
| loaded-key binding verifier | B1 = B3 = B2, with B4 consistent, at a named head | authority (`authorityGranted: false`) |
| credential-slot inventory (RR-19) | no unexpected slot or blob exists | which key is authoritative |
| local ceremony hold | issuance is blocked | owner authorization |
| `S_ACTIVATED` | S is loaded and observed, by the signer's own account | anything verified |
| `S_CURRENT` | independently verified readiness + binding + inventory + authorization history + hold released | authority (that came from K-ROOT) |

### 7.5 Open details (not decided by RR-11)

| # | Detail | Constraint the accepted rule imposes |
| --- | --- | --- |
| RR-11-D1 | whether one successor-capable release serves several rotations (a closed successor form) or each rotation gets its own release | the release must be immutable and reviewed; no free-form key ID, path, or domain argument; the keygen writes only the PREPARED slot and refuses if it is non-empty; switching the signer's `current` selector must not be part of a custody ceremony |
| RR-11-D2 | the successor's embedded credential name | whatever is chosen, the successor must not load in the current unit before cutover, and cutover must not re-expose plaintext. Keeping the fixed name `owner-actor-signing-key` with a distinct path meets both (the unit references only the CURRENT path, and `blobSha256` survives a rename) |

Both are fixed in the successor-capable release slice (SW-2) and reviewed
there.

## 8. The dual-current hidden assumption (rule retained)

**"What assumption could make every individual artifact look valid while the
overall system is wrong?"**

The assumption is: **there is exactly one witness chain per environment,
every consumer evaluates that same chain, and at most one executable
authorization is outstanding per prior head.**

**Rule (retained):** two individually valid successors from one predecessor
must never both become accepted current. The resolution comes only from:

1. **exact prior-head binding.** After one execution the head never returns
   to the prior head, so a competing authorization fails `PRIOR_HEAD_MISMATCH`
   forever;
2. **contiguous registry versions.** `target = prior + 1`; the same version
   with another digest is `WITNESS_REGISTRY_FORK`;
3. **single-use authorization.** `CHAIN_AUTHORIZATION_REPLAYED` /
   `AUTHORIZATION_CONSUMED`;
4. **unique verified witness lineage.** From the owner-pinned genesis (RR-21),
   one `O_EXCL` entry per version, one writer, and re-verified authorization
   history (RR-20a);
5. **single-current-key validation.** At most one current key per scope in the
   head registry, and one loadable blob (RR-19).

Never timestamps. Never filename order. Never service restart order. Never
last writer wins.

| Artifact | Why it cannot make a second current |
| --- | --- |
| two signed candidate registries | only a witness entry with a re-verified authorization makes one the head |
| two `RegistryHeadAdvanceAuthorizationV1` from one prior head | the first executed wins; the second fails its prior-head binding |
| two prepared credential slots | the PREPARED slot holds one blob; the inventory refuses a second; only the blob matching the head key's publication is current |
| two valid witness successors | `FORK` → fail closed |
| two `HEALTH` fingerprints at different times | `HEALTH` is a claim at an instant; a binding result is valid only for the head it names |

**Where the assumption can still break:**

- inside one chain, only through K-WIT misuse. It is detected as a fork,
  replay, ordering violation, or invalid authorization history;
- a second genesis over the same anchor is detected by the pinned genesis
  digest (RR-21);
- **a cloned VM shares the genesis and is not detected.** That is whole-host
  rollback, which stays unresolved;
- the owner keeps the register of issued authorization IDs (§6.8), with at
  most one unexpired authorization per prior head. This is the only defence
  spanning chains.

**A detected fork fails closed and requires OWNER + K-ROOT recovery.** The
witness never chooses. The verifier only reports. Host root may preserve
evidence but decides nothing.

## 9. State owners

| State | Owner | May request | May mutate | May verify | Restorable? | Rollback-sensitive? | Authority-bearing? | Freshness-bearing? |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| K-ROOT registry authority | the owner, offline, K-ROOT | the owner | the owner (signs a new generation; never edits one) | anyone, with the pinned root | bytes yes; authority only at the witnessed head | yes | **yes** | no |
| `RegistryHeadAdvanceAuthorizationV1` | the owner, K-ROOT (object); the witness chain (consumption) | the owner | K-ROOT signs; the witness consumes | the witness planner; the verifier (RR-20a) | the object, yes (harmless once consumed or off its prior head) | a witness restored alone could meet a replay; fails closed via the ledger position | **yes**, for one transition | no |
| `EpochAdvanceAuthorizationV1` | as above | the owner | as above, plus the signer's pre-witness adoption record (C-4) | as above | as above | as above | **yes**, for one transition | no |
| retained authorization bytes + owner register | the owner (off-host register); the witness (on-host copies) | — | written once | the verifier | the owner copy is the reference | a missing or mismatching copy fails closed | no (evidence) | no |
| owner-pinned genesis digest (RR-21) | the owner, off-host | — | written once at V2 genesis | the verifier; witness recovery | n/a | anchors lineage only | no | no |
| `RecoveryWitnessV2` (chain authoritative; pointer derived) | `lilith-recovery-witness` | host root (owner socket); the signer (ledger advance only) | the witness service only | the independent verifier (full chain) | a chain restored alone → fail closed; restored with everything → undetected | **yes** | no | **yes** |
| authority recovery ledger | `lilith-authority-dev` | the signer's own operations | the signer only (recovery records are destroy/narrow-only) | the verifier (read-only copy) | adopted only if equal to the witnessed position | **yes** | no | position only |
| credential custody (CURRENT / PREPARED / RETIRED) | host root + systemd | the owner | host root via the fixed CLIs | root-observed hashes (B2); publications (B3); inventory (RR-19) | forbidden in DEV_SYNTHETIC; a restore is class 4 or worse | yes | no | no |
| key publication (B3) | the owner transcript | — | written once by the keygen output | the verifier | yes (a public record) | no | no | no |
| signer loaded key | the running signer process | — | systemd at unit start, from the CURRENT slot | B4 is a claim, bound via B1–B3 | n/a | yes | no | no |
| ceremony hold | host root | the owner (unauthenticated intent, RR-13) | host root | anyone (presence only) | a restored hold is availability loss; a removed hold still needs readiness | fails safe | no | no |
| verification / readiness / inventory result | the independent verifier (stateless) | the owner | none (re-derived) | reproducible by anyone with the inputs | n/a | bound to the head it names | no | no |

No new service, identity, socket, or state owner is introduced.

## 10. Live entry matrix

**Current verdict: DO NOT ENTER LIVE REHEARSAL.**

`ENTER` means only "this row does not block". Entry needs every row to be
`ENTER` or `ENTER WITH EXPLICIT NONCLAIM`, every §14 item accepted, and a
separate owner authorization of the rehearsal design. **Passing source tests
never authorizes a live ceremony.**

| Condition | Verdict |
| --- | --- |
| B1b-3d L3a–L4 not live and accepted | **DO NOT ENTER** |
| any §14 item not implemented, test-proven, reviewed, and accepted | **DO NOT ENTER** |
| RR-6 rule not reflected in the recovery tooling (SW-9) | **DO NOT ENTER** a compromise-recovery rehearsal. For a routine rotation rehearsal: ENTER WITH EXPLICIT NONCLAIM (no compromise-recovery claim) |
| any current-key artifact in class 1–4 (§5.2) | **DO NOT ENTER** |
| current-key artifacts only `SAFE_RETAINED_CIPHERTEXT` or bounded, documented `KNOWN_CUSTODY_DEBT` | ENTER WITH EXPLICIT NONCLAIM (named debt) |
| snapshot inventory incomplete (RR-17) | **DO NOT ENTER** |
| RR-9 durable writer, chain-directory fsync, recovery scan, and fault tests absent | **DO NOT ENTER** |
| `RecoveryWitnessV2` pure contracts only (today, SF-9) | **DO NOT ENTER** |
| live witness not at V2 genesis (RR-18) | **DO NOT ENTER** |
| genesis digest not pinned off-host, or mismatching (RR-21) | **DO NOT ENTER** |
| chain verifies from the pinned genesis; pointer = head; authorization history re-verifies (RR-20a) | ENTER |
| no reviewed successor-capable release installed (RR-11) | **DO NOT ENTER** |
| successor credential present at preflight | **DO NOT ENTER** until classified and destroyed |
| current credential binding unverified, or inventory unexpected (RR-19) | **DO NOT ENTER** |
| binding (B1–B4) and inventory verified at the current head | ENTER |
| K-ROOT authorization absent at preflight | ENTER (it is created inside the ceremony) |
| an unexpired K-ROOT authorization from the current head already exists | **DO NOT ENTER** |
| an active hold at preflight | **DO NOT ENTER** |
| the hold released at preflight | ENTER |
| authority recovery ledger position equals the witness | ENTER |
| authority recovery ledger stale, ahead, or unverifiable | **DO NOT ENTER** |
| whole-host rollback protection absent | ENTER WITH EXPLICIT NONCLAIM (`wholeHostRollbackProtected: false`) |
| preservation set (B1b-3d §23) changed | **DO NOT ENTER** |

## 11. Future rehearsal phases (routine rotation; no commands)

This is the minimum sequence for an in-epoch routine rotation P → S (RR-6 S1).
A compromise-recovery or epoch-advance rehearsal is a separate later ladder.
Every phase starts by re-hashing the preservation set, re-verifying the chain
from the pinned genesis with its authorization history, and re-running the
inventory for the phase. **"Usable" means P may resume issuance if the owner
aborts and releases the hold.**

| Phase | PRE | The one authority-relevant mutation | POST evidence | STOP if | Rollback boundary | P usable? | S may issue? | `S_CURRENT`? |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| L3e-0 preflight | §10 all green | none | inventory (CURRENT only); snapshot inventory reference; chain + authorization history; ledger = witness; binding at head; RR-7 classes | any §10 row blocks | — | yes | no | no |
| L3e-1 hold | L3e-0 PASS | write the ceremony hold (`S_PROPOSED`) | hold hash; signer refuses creating ops | hold not observed | remove the hold | yes (after release) | no | no |
| L3e-2 quiesce | hold present | stop the signer (runtime, kept separate by the one-mutation rule) | no signer-uid process | signer still running | start again (hold still blocks) | yes | no | no |
| L3e-3 successor preparation | PREPARED slot empty | successor keygen → PREPARED slot (`S_PREPARED`) | publication; slot hash = `blobSha256`; CURRENT hash unchanged; inventory = CURRENT + one PREPARED; output scan clean | any private pattern; CURRENT changed | destroy the PREPARED blob | yes | no (`KEY_UNKNOWN`) | no |
| L3e-4 registry candidate | publication recorded | offline: K-ROOT signs candidate vN+1 (S current, P `SUPERSEDED`, `t_cut`) (A) | candidate digest in the owner register; succession passes offline | succession or single-current fails | discard (stays story 4) | yes | no | no |
| L3e-5 head authorization | (A) verified; no other unexpired (B) from vN | offline: K-ROOT signs (B) vN → vN+1 (`S_AUTHORIZED`) | authorization ID and digest in the owner register | a competing (B) exists | let (B) expire; abort | yes | no | no |
| L3e-6 witness head advance | chain head = vN; (A), (B) verify | the witness executes (B) (`S_PUBLISHED`). **Point of no return** | committed entry; retained authorization copy digest = register; pointer = head; recovery `CONSISTENT` | refusal (state unchanged) | **none: forward only** | **no, never again** | no | no |
| L3e-7 serve head registry | head = vN+1 | install vN+1 bytes as the served registry (story 4) | served digest = head digest | mismatch | reinstate the head bytes | no | no | no |
| L3e-8a vacate | served = head | P: CURRENT → RETIRED holding | CURRENT empty (the unit cannot start: fail safe); RETIRED = P | anything else changed | forward only | no | no | no |
| L3e-8b install | L3e-8a POST | S: PREPARED → CURRENT (same-filesystem rename) | inventory = CURRENT(S) + RETIRED(P); PREPARED empty | any other blob | forward only | no | no | no |
| L3e-9 activation | S in CURRENT; hold present | start the signer: `REGISTRY_VIEW{vN+1,[S]}` journalled; the witness records the ledger advance (one protocol step; a crash → `LEDGER_AHEAD_OF_WITNESS`, fail closed) (`S_ACTIVATED`) | `HEALTH` = S; ledger view; witness position | `HEALTH` ≠ S; ledger ahead | stop the signer; diagnose | no | no | no |
| L3e-10 independent verification | `S_ACTIVATED` | none (the verifier emits the transition record) | `RESTORE_READY`; binding B1–B4; inventory expected for this phase; authorization history re-verified | anything else | the hold stays | no | no | eligible only |
| L3e-11 hold release | L3e-10 PASS; owner decision | remove the hold (`S_CURRENT`) | hold absent; readiness still READY | readiness changes | recreate the hold | no | **yes**, per-operation readiness | **yes** |
| L3e-12 predecessor retirement | `S_CURRENT` independently verified | destroy P's blob from RETIRED holding | RETIRED empty; inventory = CURRENT(S) only; `predecessorMaterialDestroyedFromActiveCustody: true` (active custody only, no zeroization claim) | any copy remains | none needed | no | yes | yes |
| L3e-13 crash/restore proofs | `S_CURRENT`; fault hooks TEST-proven | one injected fault per sub-step (§6.4 cases; stale credential into CURRENT (F7/F20); stale registry served (F21); competing authorization (F6)), each preserve → inject → observe → restore | classification and readiness per case | any `RESTORE_READY` on a stale, torn, or forked state | restore the preserved state (hash-verified) | no | only when READY | yes, after each restore |

## 12. Nonclaims

This record does not claim, create, or authorize any of the following:

- PROD authority, or closure of the cross-environment debt;
- real-owner-grade custody or a real registry root;
- First Memory;
- a Stage III retry;
- Privacy live custody;
- any WebAuthn change;
- consciousness or personhood;
- a whole-host rollback solution;
- external monotonicity because the genesis is pinned;
- that systemd encrypted credentials protect against a whole-disk snapshot
  containing both halves;
- zeroization;
- automatic trust in restored backups;
- **any live rotation**;
- **any live epoch advance**;
- any live ceremony, runbook, or command;
- that source tests passing authorizes live entry.

## 13. Owner decisions

| # | Question | Accepted outcome | Classification |
| --- | --- | --- | --- |
| RR-6 | When does compromise require an epoch advance? | option C (§4.4): none for rotation or administrative revocation; **required** (`KEY_COMPROMISE`) for current issuing-key compromise, with the key still marked `COMPROMISED`; in-epoch marking for a non-current key unless another domain is suspect; STOP for root, host boundary, K-ROOT, or K-WIT compromise; hold on suspicion. `epoch advancement != custody repair`; `!= key-compromise repair` | **OWNER-ACCEPTED** |
| RR-7 | How is retained or restored material classified, and when may a rehearsal enter? | the six-class closed model (§5.2). Unknown provenance fails closed as exposure. Current-key entry only at `SAFE_RETAINED_CIPHERTEXT` or bounded, documented `KNOWN_CUSTODY_DEBT` | **OWNER-ACCEPTED** |
| RR-9 | How does the witness recover from a torn publication? | the signed chain is authoritative; the pointer is derived; commit needs complete bytes, a verifying signature, a file fsync, and a directory fsync; roll forward only a unique valid durable successor; never roll back automatically; fork, corruption, ambiguity, missing chain, or invalid lineage fail closed to the owner (§6) | **OWNER-ACCEPTED** |
| RR-11 | How is a successor prepared, from which release? | a new reviewed successor-capable release; side-by-side preparation in a separate root-only directory on the same filesystem; the old credential retained and non-loadable through cutover and destroyed only after `S_CURRENT` (§7.1). RR-11-D1 and D2 are open details (§7.5) | **OWNER-ACCEPTED** ("the current release cannot generate a successor" is also SOURCE-DETERMINED, SF-1) |
| RR-16 | A separate in-epoch compromised-current-key + successor contract? | **not introduced.** Closed by RR-6. Source gaps of the accepted path are implementation work (SW-9) | **CLOSED** |
| RR-17 | Are snapshots inside the custody boundary? | not automatically; a complete inventory is required before entry; both halves together is at least `KNOWN_CUSTODY_DEBT` inside an accepted, inventoried environment; unknown or uncontrolled copies are `UNKNOWN_PROVENANCE` or `COMPROMISED` (§5.6) | **OWNER-ACCEPTED** |
| RR-18 | Which witness schema does the live witness start with? | `RecoveryWitnessV2` genesis, binding the exact accepted registry head. No live V1 and later migration. V1 stays historical and source-compatible | **OWNER-ACCEPTED** |
| RR-19 | Must readiness verify the credential-slot inventory? | yes, as a fail-closed readiness condition, not authority. Unexpected inventory blocks `S_CURRENT` (§14 SW-6) | **OWNER-ACCEPTED** |
| RR-20a | Must readiness re-verify the K-ROOT authorization behind each witness transition? | yes, for both head and epoch changes, with minimum retention per §6.8 | **OWNER-ACCEPTED** |
| RR-20b | Is host-key rotation enough after a both-halves snapshot exposure outside the boundary? | no. STOP and re-establish custody with fresh custody material; a bounded, accepted, inventoried snapshot may stay `KNOWN_CUSTODY_DEBT` (§5.6) | **OWNER-ACCEPTED** |
| RR-21 | Pin the V2 genesis digest? | yes, off-host by the owner before entry. It anchors the accepted lineage; it does not solve post-genesis whole-host rollback. Head checkpoints and off-host monotonic anchoring stay separate work | **OWNER-ACCEPTED** |

Carried forward unchanged from the design: RR-8, RR-10a, RR-12, RR-13, RR-14a
(`DEFERABLE`); the B1b-3c open decisions 3, 5 (T-4), 6, 7; B1b-3d T-6, T-9.
Open details RR-11-D1 and RR-11-D2 (§7.5) and the marking form of SW-9 are
not decisions accepted here.

## 14. Source and preparation work required before live entry

None of this is implemented here. Every item must be implemented,
test-proven (TEST-only first, with no DEV contact), reviewed, and accepted
before a live rehearsal may be designed.

| # | Origin | Requirement | Minimum acceptance evidence |
| --- | --- | --- | --- |
| SW-1 | GC-1 / RR-11 | correct old-key destruction ordering: P moves CURRENT → RETIRED (non-loadable) at cutover and is destroyed only after independently verified `S_CURRENT`; the rotation assessment and transition record report retention until then | tests that destruction before `S_CURRENT` is refused, and that a retained P can never satisfy readiness |
| SW-2 | GC-2 / RR-11 | a reviewed successor-capable authority-dev release: side-by-side successor keygen writing only the PREPARED slot (separate root-only directory, same filesystem), refusing if it is non-empty, never writing CURRENT; a distinct successor key ID; a B1b-3e release-set contract replacing the initial-custody `RELEASE_SET` rule (SF-2); installer stages for the successor CLI; RR-11-D1 and D2 fixed | release file-set pins; keygen refusal matrix; installer status contract; no plaintext in output |
| SW-3 | GC-3 | the missing loaded-key/readiness binding conditions of the design §11.2: fixed embedded credential name and "no other authority blob" (via SW-6) | binding negative tests for a second blob and a wrong name |
| SW-4 | GC-4 / RR-18 | live V2 genesis semantics: a DEV_SYNTHETIC V2 witness writer profile whose owner `BOOTSTRAP` produces `RecoveryWitnessV2` genesis bound to the exact accepted registry head; no V1 live path; the V1 `RAISE_REGISTRY_FLOOR` and V1 `ADVANCE_EPOCH` shapes not offered | genesis vectors; refusal of bootstrap over an existing chain; V1 refused as the live start |
| SW-5 | GC-5 / RR-9 | a durable witness writer and service: the §6.2 commit order, including the `chain/` directory fsync; durable retention of authorization bytes; the §6.3 recovery scan; single instance and `flock`; a fault-injection hook for TEST | every §6.3 row and every §6.4 case as a test; recovery never signs; idempotent across repeated runs |
| SW-6 | RR-19 | a credential-slot inventory verifier (root-observed, no decryption): CURRENT exists; PREPARED exists only in phases that permit it; RETIRED only between cutover and retirement; ownership, type, and mode match the contract; unexpected blobs and slots absent; no second candidate can satisfy loaded-key readiness; the result never selects the authoritative key | a phase × inventory matrix of tests; unexpected inventory blocks `S_CURRENT` |
| SW-7 | RR-20a | independent K-ROOT authorization-chain re-verification in readiness and witness recovery, per §6.8, plus the retention inputs (owner register digests, on-host copies) | tests: a K-WIT chain that promotes a staged candidate with a fake ID fails; a missing or mismatching retained authorization fails; valid head and epoch transitions pass |
| SW-8 | RR-21 | an owner-pinned genesis-digest input to the verifier and to witness recovery | tests: a second genesis over the same anchor fails `GENESIS_MISMATCH`; a missing pin fails closed |
| SW-9 | RR-6 / RR-16 | the current-key compromise recovery path, without a new authority path: an end-to-end evaluator from marking through the `KEY_COMPROMISE` epoch advance (ledger adoption, quarantine, successor, binding, inventory) to `S_CURRENT`, because `evaluate_rotation` is in-epoch only (SF-5, SF-11); the choice of separate vs combined marking; `CeremonyHoldV1` and `AuthorityKeyTransitionV1` contracts (SF-11); in-epoch `COMPROMISE_MARKING` for a non-current key | tests: current-key compromise without an epoch advance never reaches `S_CURRENT`; the marking is present at or before the advance; all old-key evidence stays `KEY_COMPROMISED` |
| PR-1 | B1b-3d | B1b-3d L3a–L4 designed for V2, implemented, live, and accepted (registry, anchors, witness at V2 genesis, authority recovery ledger, `RESTORE_READY` signer) | the B1b-3d acceptance record |
| PR-2 | RR-17 | a complete snapshot inventory, classified per §5.6. It is a separately authorized read-only preparation step | an owner-accepted inventory record |
| PR-3 | RR-20a / §8 | the owner's off-host register: authorization IDs, digests of authorizations and head registries, and the pinned genesis digest | the register exists before the first live K-ROOT authorization |

**DO NOT ENTER LIVE REHEARSAL** until every item above is implemented,
test-proven, reviewed, and accepted.

## Explicitly not done

- No DEV or PROD contact. No gcloud, SSH, IAP, sudo, systemctl, or
  systemd-creds.
- No key generated, rotated, revoked, deleted, or restored. No registry,
  witness, epoch, authority recovery ledger, broker ledger, or L04 touched.
- No IAM, WIF, or sudoers change. No Stage III retry. No First Memory.
- No live ceremony script, runbook, deployment, or mutation command.
- No source, test, vector, workflow, or earlier record changed.
- No live entry authorized.
