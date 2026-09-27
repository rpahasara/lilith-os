# Slice 15B2b-B1b-3e — Live-Rehearsal Entry Gate

Status:

- **DESIGN / LIVE GATE ONLY**
- **NOT SOURCE IMPLEMENTATION**
- **NOT LIVE AUTHORIZATION**
- **RR-6, RR-7, RR-9, RR-11: PENDING_OWNER_DECISION** (§13). Nothing in this
  record is owner-accepted.
- **WHOLE-HOST ROLLBACK UNRESOLVED**
- **REAL AUTHORITY ABSENT**

Base: protected main `918a7b1bde9d7dcbd9036a55ffe408e643192805`.

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

It is not an acceptance record, a ceremony runbook, an activation
instruction, or an implementation authorization. It contains no commands.

Nothing was contacted or changed: no DEV, PROD, gcloud, SSH, IAP, sudo,
systemctl, or systemd-creds; no key, credential, registry, witness, ledger,
broker, L04, IAM, WIF, or sudoers; no Stage III; no First Memory. No source,
test, vector, workflow, or earlier record was changed.

Labels follow the design: **CANONICAL** (accepted record or protected-main
source), **SOURCE FACT** (read from current source at the base above),
**PROPOSED** (recommended here, needs owner decision and a separate source
slice), **PENDING_OWNER_DECISION**.

## 1. Controlling source facts

Current source is the authority for current behaviour. These facts constrain
every section below.

| # | Source fact | Location |
| --- | --- | --- |
| SF-1 | The keygen has exactly one form (`actor`), a fixed key ID `test-only.dev-synthetic.actor.b1b3d.1`, a fixed blob path in `/etc/credstore.encrypted`, and refuses `CREDSTORE_NOT_EMPTY` | `services/authority-dev/ceremony/lilith_authority_keygen_dev.py:65`, `:70-71`, `:161-166`, `:206-207` |
| SF-2 | The installer's `RELEASE_SET` check requires exactly one installed release; its own comment says B1b-3e may define a different release-set contract. The keygen CLI is written once (collision refused) | `services/authority-dev/ceremony/install_authority_dev.py:437-445`, `:589-594` |
| SF-3 | The signer unit loads exactly one credential, `owner-actor-signing-key`, from exactly one path, and has `/etc/credstore.encrypted` in `InaccessiblePaths` | `services/authority-dev/deploy/lilith-authority-dev.service` |
| SF-4 | The signer reads only `$CREDENTIALS_DIRECTORY/owner-actor-signing-key`; `HEALTH.publicKeySha256` is derived from the loaded key. L1 has no signing, no ledger, no witness client; readiness is always `NOT_READY` | `services/authority-dev/lilith_authority_dev/credential.py`, `core.py` |
| SF-5 | `evaluate_rotation` requires the candidate's predecessor to be `SUPERSEDED` (`CANDIDATE_PREDECESSOR_NOT_SUPERSEDED`). Aborts are allowed only up to `S_AUTHORIZED` | `services/owner-memory-control/lilith_owner_memory/rotation_contracts.py:1345`, `:1553` |
| SF-6 | `HEAD_ADVANCE_REASONS` includes `COMPROMISE_MARKING`; `EPOCH_ADVANCE_REASONS` includes `KEY_COMPROMISE`. The head-advance planner does not require the target to have a current key; the epoch planner does (`TARGET_HAS_NO_ISSUANCE_KEY`) | `rotation_contracts.py:79-83`, `:975-1018`, `:1055` |
| SF-7 | `witness_v2_succession_reason` requires a transition entry to **name** a consumed authorization; it does **not** verify that authorization ("the executor's check"). Chain facts establish linearity and single use only | `rotation_contracts.py:687-738`, `:775-792` |
| SF-8 | `verify_loaded_key_binding` takes B1–B4 only. It has no input for the systemd credential name or for a credential-store inventory | `rotation_contracts.py:1265-1327` |
| SF-9 | The only `RecoveryWitnessV2` writer is TEST-only and keeps its chain in memory. No durable chain/pointer writer, witness service, or K-WIT custody code exists in the repository | `services/owner-memory-control/lilith_authority_signer/synthetic_witness_v2.py:69` |
| SF-10 | `verify_registry_succession` allows `null → (t, COMPROMISED)` and the escalation `ROUTINE`/`SUPERSEDED` → `COMPROMISED`; a compromise is never cleared | `rotation_contracts.py:249-273` |

**Live baseline (CANONICAL, live closure §4, §6).** Only the K-ACT
host-bound blob, `credential.secret`, the `lilith-authority-dev` account, the
release, and inactive units exist on DEV. No registry, anchor, K-WIT,
witness, or authority recovery ledger exists. K-ACT is not an authority key.
Activation is `NOT_ACCEPTED reason=GRANT_ABSENT`. B1b-3d L3a–L4 are neither
implemented as a service (SF-9) nor live.

## 2. Design/source conflicts found (not silently resolved)

| # | Conflict | Handling |
| --- | --- | --- |
| GC-1 | The design §7.4 step 5 has credential custody "move S into the unit slot and destroy P's blob" at `S_ACTIVATED`, **before** `S_CURRENT`. This gate's brief requires that the current credential is not destroyed before `S_CURRENT` is independently established | Analysed in §7.5. After `S_PUBLISHED`, P is non-current at the witnessed head and can never be current again (SF-10), so P's blob is not a rollback resource. The timing is left to the owner: **RR-11b** |
| GC-2 | The B1b-3d design §13 step 5a names the successor blob `…owner-actor.next.cred` inside `/etc/credstore.encrypted`. The implemented keygen refuses a non-empty credstore (SF-1), and the design §11.2 binding requires "no other `lilith-authority-dev` credential blob" in the credential store | **RR-11c**. Not chosen here |
| GC-3 | The design §11.2 binding conditions "fixed systemd credential name" and "no other authority blob present" are not implemented by `verify_loaded_key_binding` (SF-8) | The design requirement stands. New question **RR-19** |
| GC-4 | The B1b-3d §10 witness is V1 with `RAISE_REGISTRY_FLOOR` and a V1 `ADVANCE_EPOCH` shape. The design §10.3 replaces the floor raise for V2, and §9.3 supersedes that `ADVANCE_EPOCH` shape. No record states the schema the live witness bootstraps with | New question **RR-18** |
| GC-5 | The B1b-3d §10 update order fsyncs the chain file but specifies no fsync of the `chain/` directory before the pointer rename. Without it, a crash can leave the pointer naming v+1 while the chain entry's directory entry is lost | §6.2 proposes the directory fsync. PENDING with RR-9 |
| GC-6 | The design §16 recommends RR-6 "always (fail closed)". This record's analysis (§4) refines that recommendation | The design is not edited. Both recommendations are presented; neither is accepted |
| GC-7 | Registry succession (SF-10) and the B1b-3c §9 narrative ("v11: K `COMPROMISED`, next key published") allow an in-epoch compromise-plus-successor registry, but `evaluate_rotation` cannot evaluate it (SF-5) | New question **RR-16** |

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
source tests pass            != live entry
epoch advance                != key-disclosure protection
retained ciphertext          != automatically safe
restored credential          != restored authority
private material exposure    != ordinary retirement
witness pointer              != witness state
chain entry exists           != committed transition   (a valid K-WIT signature and a durable entry are both required)
file exists / newest mtime   != current
successor slot filled        != successor authorized
```

## 4. RR-6 — compromise and epoch advance

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

- **reject evidence of a disclosed key.** That is the K-ROOT `COMPROMISED`
  marking at the witnessed head (C-1), which works with or without an epoch
  change;
- **protect against an adversary inside the custody boundary.** The advance
  is journalled by the signer and executed by the witness. Both are inside
  the host-root boundary. The successor key is generated inside it;
- change historical evidence (history is retained);
- detect or repair whole-host rollback.

So an epoch advance protects against **stale or suspect authority recovery
ledger state being used for creation**. It does not protect against key
disclosure as such.

**Does advancing RecoveryEpoch provide any protection if the same compromised
custody boundary can also mint the next key? No.** An adversary who holds
host root while the successor is generated can read the successor from the
running unit, sign witness successors with K-WIT, and write the ledger. The
advance then only records that an attacker-observable key is current. Only
K-ROOT (offline) remains outside that boundary. Recovery from a boundary
compromise requires re-establishing the boundary itself (§4.3, S9).

### 4.2 Suspect-state sets

The right question is not "was there a compromise?" but "which state is now
suspect?":

| Set | Suspect state | Remedy owner | Remedy |
| --- | --- | --- | --- |
| K | issuing-key private material only | K-ROOT | `COMPROMISED` marking at the next head; a successor |
| L | in-flight authority recovery ledger state from an unknown exposure window | K-ROOT + witness | epoch advance (E1–E4) |
| B | the custody boundary: host root, `credential.secret`, K-WIT, the witness chain | owner | re-custody / re-bootstrap. Outside B1b-3e live scope |
| R | K-ROOT | owner | a new trust root. Outside B1b-3e live scope |

### 4.3 Scenario analysis

"Rejected now?" means rejected by the verifier. Rejection happens only when a
registry that marks the key `COMPROMISED` is the witnessed head. Until then
containment is operational: the hold, a stopped signer, and the acceptance
chain (`RESERVE` needs an `ISSUE` record in the authority recovery ledger).

| # | Scenario | Compromised state | Rejected now? | Rotation sufficient? | Epoch advance? | Owner re-auth? | Historical evidence | Witness trustworthy? | Rehearsal |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| S1 | routine successor rotation | none | no | yes (in-epoch, `SUPERSEDED`) | no | no (in-flight preserved) | unchanged | yes | this is the rehearsal |
| S2 | administrative revocation | none | forward only: `issuedAt ≥ revokedAt` | yes (`ROUTINE` head advance; a successor if issuance must continue) | no | only for work needing a new signature before a successor exists | unchanged | yes | may continue |
| S3 | confirmed private-key disclosure outside custody | K; L because the window is unknown | after the marking head | **no**: `SUPERSEDED` would keep backdated forgeries in `[notBefore, t_cut)` historically valid | recommended (§4.4) | yes (E1) | **all** of the key's evidence → `KEY_COMPROMISED`, including accepted history | yes, if the vector is shown to be key-only. Otherwise treat as S8/S9 | **stop**; resume only as a separately designed compromise rehearsal |
| S4 | suspected disclosure without proof | unknown | no | not until classified | not until classified | not until classified | unchanged until classified | yes, provisionally | **stop** under the hold. Resolve to S3, or to a lower RR-7 class with owner-accepted evidence. An unresolved suspicion never releases the hold |
| S5 | stale retired credential restored inside the same host/root boundary | none new. The bytes were already inside the boundary (RR-7 `KNOWN_CUSTODY_DEBT`, or `STALE_CREDENTIAL_PRESENT` if in the unit slot) | P already non-current; a loaded P fails the binding | n/a | no. **Yes** only if the restore also rewound the ledger (B1b-3c) | no | unchanged | yes, if the witness was not restored | stop the phase; remove it; re-verify the binding; establish the source of the copy (a same-host copy breaks the DEV_SYNTHETIC no-backup policy) |
| S6 | stale retired credential observed outside the custody boundary | K for the **non-current** key | after the marking head | n/a: the key is not issuing | **no**: the current key and in-flight state are unaffected, unless the same artifact carried the current key or `credential.secret` (then S8) | no | **all** of P's evidence → `KEY_COMPROMISED` via `SUPERSEDED` → `COMPROMISED` escalation (SF-10); accepted history from P is lost (no re-attestation, C-1) | yes | stop; an in-epoch `COMPROMISE_MARKING` head advance; resume after |
| S7 | host snapshot with the encrypted blob only | none, while `credential.secret` has never left the host | no | n/a | no | no | unchanged | yes | ENTER WITH EXPLICIT NONCLAIM only if the snapshot is classified `SAFE_RETAINED_CIPHERTEXT` (§5). Otherwise stop |
| S8 | host snapshot with the blob **and** `credential.secret` | every key encrypted under that host key when the snapshot was taken (K-ACT; K-WIT if present), **and the host key itself** | after the marking head | **no**: a successor encrypted under the same host key is protected only by host access; every later ciphertext copy becomes decryptable | not sufficient. It needs host credential-key rotation and K-ACT/K-WIT regeneration (**RR-17**, **RR-20**) | yes | all evidence of the exposed keys → `KEY_COMPROMISED` | **no**, if K-WIT was in the snapshot. The snapshot also enables whole-host rollback | **stop**; re-custody |
| S9 | root compromise while the host runs | B: K-ACT, K-WIT, witness chain, ledger, hold, served registry | after the marking head (K-ROOT is offline, so marking stays possible) | no | **no protection** (§4.1) | yes | all K-ACT evidence → `KEY_COMPROMISED` | **no**: every entry since the unknown onset is untrusted | **stop**; rebuild the host, new host key, new K-ACT, new K-WIT, new witness genesis and anchor |
| S10 | compromise of K-ROOT | R: every registry and authorization the attacker could sign | not by any current mechanism: the verifier trusts K-ROOT | no | **no protection**: an advance is K-ROOT-authorized | yes | anything whose validity rests on post-onset registries is unverifiable. No contract re-signs history under a new root | **no**: it faithfully executes attacker-signed authorizations | **stop**; a new trust root; re-bootstrap DEV_SYNTHETIC trust (B1b-3d T-10) |
| S11 | compromise of K-WIT | B for freshness. The holder can sign forks from any past entry and, by SF-7, promote any K-ROOT-signed staged candidate with a fake authorization ID | K-ACT evidence is **not** `KEY_COMPROMISED` unless K-ACT was also exposed | n/a | **no protection**: the witness executes it | yes, if a new chain is started | unchanged cryptographically. Freshness history is untrusted | **no** | **stop**; new K-WIT, new anchor, new genesis. Establish the vector (usually S9) |
| S12 | compromise of only the OWNER_ACTOR issuing key (K-ACT). K-WIT, K-ROOT, `credential.secret`, and the ledger are shown unaffected | K (and L for the unknown window) | after the marking head | no (`SUPERSEDED` is wrong for exposure) | recommended (§4.4) | yes (E1) | all K-ACT evidence → `KEY_COMPROMISED` | yes | **stop** the rotation rehearsal. A compromise-replacement rehearsal is a separate later ladder |

### 4.4 Options and recommendation

| Option | Rule | Security consequence | Operational consequence |
| --- | --- | --- | --- |
| A | in-epoch replacement only; never advance the epoch for compromise | in-flight ledger state from the exposure window stays usable with the successor key. It also relies on a path `evaluate_rotation` cannot evaluate (GC-7) | cheapest; needs RR-16 source work first |
| B | always advance the epoch on any compromise (the design §16's recommendation) | burns in-flight state (good), but gives false assurance for S8–S11, where the advance is executed inside the compromised boundary or authorized by the compromised root | also burns in-flight work for non-issuing-key cases (S6) with no security gain |
| **C (recommended)** | scope by suspect-state set (§4.2) | the remedy matches the suspect state. S8–S11 are named as re-custody or re-root, never "fixed" by an epoch | needs a correct classification (RR-7); the suspicion rule for S4 makes that fail-closed |

**Recommendation (PENDING_OWNER_DECISION): C, with this DEV_SYNTHETIC V1
operational rule:**

1. A confirmed, or unresolved suspected, compromise of the **current issuing
   key** (S3, S12, S4 unresolved) ⇒ an epoch advance with reason
   `KEY_COMPROMISE`. The target registry marks the key `COMPROMISED` and names
   a successor at E(n+1). Justification:
   - the exposure window is unknown (`compromisedSince` is forensic only), so
     in-flight ledger state from that window is set L;
   - it is the only compromise-replacement path current source models end to
     end (SF-5, SF-6; RR-16);
   - DEV_SYNTHETIC has little in-flight work, so the burn cost is low.

   It is **not** justified by "the epoch protects the key". It does not.
2. Compromise of a **non-current** key (S6) ⇒ an in-epoch
   `COMPROMISE_MARKING` head advance. No epoch advance.
3. Boundary or root compromise (S8–S11) ⇒ stop. Re-custody or re-root is out
   of B1b-3e live scope.
4. A suspicion is resolved only by owner-accepted evidence of a lower RR-7
   class. The hold is never released on an unresolved suspicion.

## 5. RR-7 — retained and restored key material

### 5.1 Custody boundary for classification

For DEV_SYNTHETIC, the **custody boundary** of K-ACT (and later K-WIT) is:
the running DEV VM's root principal and its local disk, which holds
`/var/lib/systemd/credential.secret`. This is the same boundary that holds
the current key.

Outside it: any other host; the owner workstation (K-ACT is designed never
to leave the host); GitHub and CI; logs and transcripts; and, **until RR-17
decides otherwise**, cloud-level disk snapshots.

Host-key encryption means: **a blob is exactly as secret as the
`credential.secret` it can be combined with.**

### 5.2 Closed classification

Classes apply per artifact. They are evaluated most severe first; the first
matching class wins. A key's action follows its worst artifact.

| # | Class | Definition (every condition must hold) |
| --- | --- | --- |
| 1 | `COMPROMISED` | an **authority outcome**, not a storage class: the K-ROOT registry at the witnessed head records `revocationReason = COMPROMISED`. Terminal (SF-10) |
| 2 | `EXPOSED_PRIVATE_MATERIAL` | plaintext private material (PKCS#8 DER, seed, raw private bytes) was observable anywhere outside the L2 §6 transient path (keygen and `systemd-creds` process memory, the kernel pipe, the running unit's `$CREDENTIALS_DIRECTORY`); **or** ciphertext and its decrypting `credential.secret` exist together, or could be combined, outside the custody boundary |
| 3 | `UNKNOWN_PROVENANCE` | its existence, copy history, location, or co-location with the host key cannot be established from records (key publication, owner transcripts, a root-observed inventory). This includes a blob whose SHA-256 matches no publication, and a snapshot whose existence is unknown |
| 4 | `STALE_CREDENTIAL_PRESENT` | a blob of a key that is not the single current key at the witnessed head is in the unit slot, or in any path a unit's `LoadCredentialEncrypted=` references |
| 5 | `KNOWN_CUSTODY_DEBT` | known provenance (the hash matches a publication); decryptable inside the custody boundary; never observable outside it; in no unit slot |
| 6 | `SAFE_RETAINED_CIPHERTEXT` | known provenance; ciphertext only; its decrypting host key is not with it and cannot be obtained by the copy's holder; `credential.secret` has never been exported; the copy is owner-controlled. **Conditional:** any later exposure of `credential.secret`, or of a snapshot containing it, reclassifies every such copy as `EXPOSED_PRIVATE_MATERIAL` |

No class exists for "probably safe". Plaintext is never below class 2.

**Key status matters.** A class's authority action depends on the key's
status at the witnessed head:

- `CURRENT`: the single current key;
- `NON_CURRENT`: `SUPERSEDED`, `ROUTINE`, or retired;
- `NOT_IN_HEAD`: never named by an executed head (a prepared or abandoned
  successor, including one named only by a staged candidate). Its evidence is
  `KEY_UNKNOWN`.

### 5.3 Action per class

| Class | Authority impact | Destroy? | Destruction sufficient? | Permanent `COMPROMISED`? | Epoch advance? | Rehearsal | Evidence to resume |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `COMPROMISED` | all of the key's evidence rejected | yes, from active custody | irrelevant to authority | already | per RR-6 (current key: recommended) | stop | a K-ROOT marking head; the RR-6 remedy completed |
| `EXPOSED_PRIVATE_MATERIAL` | `CURRENT`/`NON_CURRENT`: must become `COMPROMISED`. `NOT_IN_HEAD`: none, but it must never be named current | yes | **no** | yes (not for `NOT_IN_HEAD`, which must instead never be published) | `CURRENT`: per RR-6. Otherwise no | **fail closed** | the marking head executed; for a host-key exposure, RR-20 |
| `UNKNOWN_PROVENANCE` | treated as `EXPOSED` for authority until resolved | yes, once preserved as evidence | no | as `EXPOSED`, unless resolved to a lower class | as `EXPOSED` | **fail closed** | an owner-accepted inventory or record that establishes a lower class |
| `STALE_CREDENTIAL_PRESENT` | none: the binding fails (B2/B3/B4) → `NOT_READY` | remove from the slot; then classify the source copy | yes, for the slot | no (unless the source copy is class 2 or 3) | no | stop the phase | the slot holds exactly the current publication's blob; the binding re-verified |
| `KNOWN_CUSTODY_DEBT` | none now. A later disclosure could forge backdated evidence inside a `SUPERSEDED` interval, so the debt is real | yes, at the predecessor retirement phase | reduces exposure; not proof (no zeroization, snapshots) | no | no | ENTER WITH EXPLICIT NONCLAIM | the debt is named in `AuthorityKeyTransitionV1`; the destruction step recorded |
| `SAFE_RETAINED_CIPHERTEXT` | none, conditionally | recommended (it breaks the no-backup policy) | n/a | no | no | ENTER WITH EXPLICIT NONCLAIM | the owner record of location, holder, and non-export of `credential.secret` |

### 5.4 Cases

| Case | Class | Notes |
| --- | --- | --- |
| encrypted blob copied inside root-only same-host custody | `KNOWN_CUSTODY_DEBT` if deliberate and recorded; `UNKNOWN_PROVENANCE` if found unexplained | breaks the B1b-3d §16 no-backup policy. Destroy the copy |
| encrypted blob copied off-host | `SAFE_RETAINED_CIPHERTEXT` only if owner-controlled, recorded, and without `credential.secret`; otherwise `UNKNOWN_PROVENANCE` | ciphertext is safe only while the host key stays put |
| blob + matching `credential.secret` copied together | `EXPOSED_PRIVATE_MATERIAL` for every key under that host key; the host key is burnt | RR-6 S8 |
| plaintext DER, seed, or private bytes ever observable | `EXPOSED_PRIVATE_MATERIAL` | the keygen's own output scan exists to prevent this (L2 §6) |
| backup made before rotation, restored after the successor is current | the backup: by its location (rows above). The restore into the slot: `STALE_CREDENTIAL_PRESENT` | `restored credential != restored authority`: P is non-current at the head and can never be current again (SF-10) |
| old encrypted credential left on disk after rotation | `KNOWN_CUSTODY_DEBT` | `predecessorMaterialDestroyedFromActiveCustody = false` until destroyed |
| old credential reintroduced into the active unit slot | `STALE_CREDENTIAL_PRESENT`, plus the class of wherever it came from | the signer loads it and reports P's fingerprint; the binding fails |
| old credential available but not loadable | `KNOWN_CUSTODY_DEBT` if root can still decrypt it on this host ("not loadable by the unit" is not "not decryptable"). Truly undecryptable cannot be proven while any snapshot might hold the old host key | never `SAFE` by assertion |
| successor generated but never authorized | `KNOWN_CUSTODY_DEBT`, key `NOT_IN_HEAD` | destroy. Before destroying, confirm no unexpired `RegistryHeadAdvanceAuthorizationV1` targets a candidate naming it; otherwise a later execution names a key with no blob (F14, availability only) |
| abandoned successor after a failed ceremony | as above if `NOT_IN_HEAD`. A partial blob with no publication (keygen exit 3) is `UNKNOWN_PROVENANCE` by definition, with no authority effect because the key is unregistered. If the ceremony had reached `S_PUBLISHED`, S is `CURRENT` and cannot be abandoned by deletion: F14/F15 | destroy after preserving the failure transcript |
| owner-controlled offline archival copy | ciphertext only: `SAFE_RETAINED_CIPHERTEXT` (conditional). With `credential.secret`: `EXPOSED_PRIVATE_MATERIAL` | owner control is not the custody boundary. Recommend no archival copies |
| hypervisor / disk snapshot | `UNKNOWN_PROVENANCE` until RR-17 decides whether the cloud snapshot store is inside the boundary, and a read-only inventory (separately authorized) establishes which snapshots exist | holds the blob, `credential.secret`, and later K-WIT, the chain, and the ledger |
| full-machine snapshot restored with the witness also rolled back | **not classifiable from inside the host**: whole-host rollback | undetected (F11). If known out of band: stop, and treat every post-snapshot transition as unknown. **Unresolved** |

### 5.5 Recommendation

**PENDING_OWNER_DECISION:** adopt the closed model of §5.2–§5.3, including:

- `UNKNOWN_PROVENANCE` is treated as exposure until resolved;
- `SAFE_RETAINED_CIPHERTEXT` is conditional on the host key;
- a live rehearsal enters only when every artifact of the current key is
  class 5 or 6, with the class-5/6 debt named as a nonclaim.

This replaces the design's two-way "inside = debt / outside = compromise"
proposal with a closed six-way model. The two agree where both apply.

## 6. RR-9 — witness crash and torn publication

### 6.1 State owner and artifacts

The sole writer is the witness service identity `lilith-recovery-witness`:
single instance, serialized requests, `flock` (B1b-3d §10).

| Artifact | Role (PROPOSED) |
| --- | --- |
| `chain/<v>.json` | **authoritative** durable freshness state. Append-only, created `O_EXCL`, never overwritten or deleted. One entry per version, so the filesystem refuses a second entry at the same version |
| `witness.json` | the **active pointer**: a derived copy of the chain head. `witness pointer != witness state` |
| `.witness.json.tmp` | scratch. Never authoritative |
| `witness.lock` | serialization only |

Readers (the signer and the independent verifier) never trust the pointer
alone. They verify the chain from genesis (`verify_witness_v2_chain`) and
compare. Pointer ≠ chain head ⇒ `NOT_READY (WITNESS_POINTER_STALE)`. Readers
never repair.

### 6.2 Atomicity boundary and fsync

**Commit point:** a K-WIT-signed `chain/<v+1>.json` whose bytes **and**
directory entry are durable. Replacing the pointer is publication, not
commit.

The write order (B1b-3d §10, plus GC-5):

1. verify succession (planner);
2. sign;
3. create `chain/<v+1>.json` with `O_EXCL`; write; `fsync` the file;
4. **`fsync` the `chain/` directory** (PROPOSED addition);
5. write the tmp file; `fsync` it;
6. `rename` it to `witness.json`;
7. `fsync` the state directory;
8. only then reply.

A signed successor that never reached step 4 is not committed and was never
returned.

### 6.3 Recovery algorithm (PROPOSED)

The witness service runs it at start, holding the lock, before serving any
operation. **Recovery never signs and never uses K-WIT.** It writes only the
pointer, through steps 5–7, to a value derived from the chain. It is
therefore idempotent, and a restart during recovery re-runs it to the same
result.

```text
R1 DISCOVER   every entry in chain/ (O_NOFOLLOW; regular files only; unexpected names -> fail closed),
              plus witness.json and .witness.json.tmp
R2 VERIFY     each chain entry alone: V2 schema, K-WIT signature under the pinned anchor, environment,
              witness key not an authority key, filename number == witnessVersion  -> VALID | INVALID
R3 LINEAGE    from the genesis entry (version 1, previousWitnessDigest null; genesis digest equal to the
              owner-pinned value if RR-21 is accepted), follow previousWitnessDigest:
              version k's candidates = VALID entries whose predecessor is the unique entry at k-1 and whose
              witness_v2_succession_reason is None. Never filename order. Never mtime
R4 FACTS      witness_v2_chain_facts: linear; no CHAIN_AUTHORIZATION_REPLAYED
R5 HEAD       H = the last version with exactly one valid candidate; classify anomalies (table below)
R6 POINTER    compare witness.json with H
R7 DECIDE     roll forward (pointer := H) | CONSISTENT | FAIL_CLOSED(reason)
```

| Observation | Classification | Outcome |
| --- | --- | --- |
| pointer byte-equal to chain entry H | `CONSISTENT` | none |
| pointer byte-equal to entry H−1; H VALID, unique, linked, succession OK, its consumed ID not consumed earlier | `POINTER_BEHIND_BY_ONE` | **roll forward (automatic)**. Never roll back to H−1 |
| pointer missing or unparseable; chain healthy | `POINTER_MISSING` / `POINTER_CORRUPT` | roll forward from H (automatic). The pointer is derived |
| pointer equal to an entry older than H−1 | `POINTER_BEHIND_MULTI` | fail closed. One crash cannot cause it, because each operation publishes before replying and recovery precedes service |
| pointer is a VALID witness at H+1 linking to H, not in the chain | `POINTER_AHEAD` (an ordering violation, given steps 3–6) | **fail closed. No rollback.** Owner intervention. A possible owner-authorized repair is re-appending the byte-identical document: no new signature |
| two VALID linked entries at one version (chain, pointer, or tmp) | `FORK` | fail closed. This is K-WIT misuse or tampering (RR-6 S11). Owner |
| an INVALID entry at a version ≤ H | `CHAIN_CORRUPT` | fail closed. Owner |
| an INVALID entry at H+1, pointer == H | `TORN_TAIL` (not committed: no valid signature on durable bytes; no reply was sent) | refuse writes (the `O_EXCL` slot is occupied). The owner sets the bytes aside, preserved outside the lineage. The requester may later re-present the same authorization: the prior head is unchanged, so it is still executable |
| VALID entries not linked to the lineage, or beyond a gap | `ORPHAN` | fail closed. Owner |
| `CHAIN_AUTHORIZATION_REPLAYED` | `REPLAY_IN_CHAIN` | fail closed. K-WIT misuse. Owner |
| chain empty, pointer present | `CHAIN_MISSING` | fail closed. History is never rebuilt from a pointer, and there is no auto-bootstrap |
| chain and pointer both absent | `UNINITIALIZED` | only the owner `BOOTSTRAP` operation (B1b-3d §10). Never automatic |
| tmp byte-equal to a chain entry, or unparseable with no H+1 candidate | scratch | discard (automatic) |
| tmp is a VALID witness not in the chain | ordering violation | fail closed; preserve |

### 6.4 The ten required cases

| Case | Result |
| --- | --- |
| predecessor active, successor absent | `CONSISTENT` at v. Nothing was committed; the authorization is unconsumed and may be re-presented |
| successor fully written and fsynced, pointer still predecessor | `POINTER_BEHIND_BY_ONE` → roll forward. The authorization is now consumed; re-presenting it gives `AUTHORIZATION_CONSUMED` / `PRIOR_HEAD_MISMATCH`, which is expected POST evidence |
| successor written but corrupt or truncated | `TORN_TAIL` → writes refused; owner sets it aside; no committed state is lost |
| pointer replaced, directory fsync lost | after reboot, either `CONSISTENT` (v+1) or `POINTER_BEHIND_BY_ONE` → roll forward. Same final state |
| pointer names the successor, chain file missing | `POINTER_AHEAD` → fail closed, no rollback, owner |
| two candidate successors from one predecessor | `FORK` → fail closed; K-WIT integrity incident |
| successor signature valid, target registry unavailable | roll forward freshness: registry bytes are story 4 and not needed for freshness. Readiness stays `NOT_READY (REGISTRY_MISSING)` until the owner reinstates the head registry bytes and they verify at the head. Nothing is fetched automatically |
| successor registry available, authorization missing | roll forward freshness. `S_AUTHORIZED`/`S_PUBLISHED` evaluation still needs the verified authorization (`HEAD_AUTHORIZATION_MISSING`). Under **RR-20**, readiness is blocked until the owner supplies it. If it cannot be produced, treat as RR-6 S11 |
| chain holds a successor whose authorization was already consumed | `REPLAY_IN_CHAIN` → fail closed |
| restart during recovery | recovery is idempotent (§6.3) |

### 6.5 Automatic vs owner

- **Automatic:** deriving the pointer from a healthy, unique chain head
  (roll forward, missing or corrupt pointer); discarding scratch.
- **Owner intervention:** everything else. In particular every case that
  moves bytes in the append-only chain directory, and every case with more
  than one valid candidate.

The witness never picks between candidates. Only the owner, with K-ROOT, can
author a resolution (a new head or a new epoch). The owner may also decide
to re-bootstrap.

### 6.6 Evidence a future rehearsal must collect

- per chain entry: version, digest, signature result, lineage position;
- pointer digest; tmp presence;
- the recovery classification, before and after;
- proof that recovery did not change the chain length or create a
  signature;
- for each injected fault (a source-provided fault hook, TEST-proven first):
  the injection point, the observed classification, and the final head;
- the explicit statement `rollbackDetectionScope: LEDGER_ONLY`,
  `wholeHostRollbackProtected: false`.

**Limit.** This does not address whole-host rollback. A snapshot that
restores chain and pointer together is `CONSISTENT` at an old head.

### 6.7 Recommendation

**PENDING_OWNER_DECISION:** accept §6.1–§6.5. That is: chain authoritative,
pointer derived, the `chain/` directory fsync added, roll-forward only to a
unique verified successor, and fail closed otherwise. RR-9 is live-blocking
until a durable witness writer implementing this exists in source with fault
tests (SF-9).

## 7. RR-11 — successor credential slot and release

### 7.1 Logical roles

| Role | Meaning | Loadable by the signer unit? |
| --- | --- | --- |
| **CURRENT slot** | the single path the unit's `LoadCredentialEncrypted=` references (SF-3) | yes: it is the only one |
| **PREPARED slot** | one side-by-side location for exactly one successor blob; referenced by no unit | no |
| **RETIRED reference** | the predecessor's publication and transcript. If RR-11b option D-2 is chosen, also a non-loadable holding location for the predecessor blob until retirement | no |

Paths are not chosen here, except where source already fixes them (the
CURRENT slot, SF-1/SF-3).

### 7.2 Required properties and how they hold

| Property | Mechanism |
| --- | --- |
| side-by-side generation; preparation leaves current issuance authority unchanged | the successor keygen writes only the PREPARED slot and never opens the CURRENT slot for writing. Authority comes from the witnessed head, which preparation does not touch |
| a file's existence never makes the successor current | current = `select_current_issuance_key` at the verified head. A blob is the current credential only if its hash equals the head key's publication `blobSha256` (B2 = B3) |
| the signer cannot silently load the successor before authorization | the unit references only the CURRENT slot. Moving the successor there early is a root act that the binding catches (the successor is not current at the head → `PUBLICATION_SCOPE_MISMATCH`/`KEY_MISMATCH` → `NOT_READY`) |
| service restart order never decides authority | readiness is a pure function of the head registry, the chain, the ledger, the binding inputs, and the hold. A restart only changes which bytes are loaded, which the binding re-checks |
| registry state is never inferred from filenames | filenames are never inputs. The head digest and publications are |
| rollback identifies the authoritative current credential | before `S_PUBLISHED`: P, whose blob matches P's publication. From `S_PUBLISHED` on: S, forward only (SF-5). No matching blob ⇒ none, fail closed |
| an abandoned successor can be destroyed without affecting the predecessor | the PREPARED slot is disjoint from the CURRENT slot; destruction touches only the PREPARED slot |
| the current credential is not destroyed before `S_CURRENT` | RR-11b (GC-1) |
| predecessor destruction only when the cutover rules permit | the retirement phase follows `S_CURRENT` (§11) under D-2; at the swap under D-1 |

### 7.3 Artifact relationships

| Artifact | Establishes | Does not establish |
| --- | --- | --- |
| immutable reviewed authority-dev release | which code runs; which keygen bytes exist (hash-pinned) | any key, authority, or freshness |
| keygen CLI | that one blob was minted into one slot, plus its public publication | registry membership; current status |
| credential slot | where bytes sit | authority (`credential exists != accepted authority`) |
| key publication `{publicKey, publicKeySha256, blobSha256}` | the ceremony link from public key to blob (B3) | authority; freshness |
| K-ROOT candidate registry (A) | the authorized key state, if it ever becomes head | head status (`signed registry != effective current registry head`) |
| `RegistryHeadAdvanceAuthorizationV1` (B) | permission for exactly one head advance from an exact prior head | execution |
| `RecoveryWitnessV2` entry | that (B) was executed; the head is now the candidate | readiness; key activation |
| `HEALTH` fingerprint | the signer's claim about the key it derived from what it loaded (B4) | independent verification |
| loaded-key binding verifier | B1 = B3 = B2, with B4 consistent, **at a specific head** | authority (`authorityGranted: false`) |
| local ceremony hold | issuance is blocked | owner authorization |
| `S_ACTIVATED` | S is loaded and observed, by the signer's own account | anything verified |
| `S_CURRENT` | independently verified readiness + binding + hold released | authority (that came from K-ROOT) |

### 7.4 Options

**Release (RR-11a).** Source already excludes one option: **R-C, reusing
the installed release `9ac7de2` keygen, is impossible.** It refuses a
non-empty credstore, has a fixed key ID equal to the predecessor's, and a
fixed path equal to the CURRENT slot (SF-1). A successor needs a distinct key
ID, because a record's public key is immutable (`SUCCESSION_RECORD_MUTATED`).

| Option | Shape | Security consequence | Operational consequence |
| --- | --- | --- | --- |
| R-A | a new reviewed release for each rotation, with the successor key ID and slot fixed in it | the most auditable per rotation; no argument surface | a release and installer cycle per rotation. Switching `current` would change the running signer's code during a custody ceremony, so the keygen install must not switch it |
| **R-B (recommended)** | one new reviewed B1b-3e release adding a closed successor form (for example a fixed grammar with an ordinal that maps to a key ID pattern), writing only the PREPARED slot, refusing if it is non-empty, and never touching the CURRENT slot | multiple slot-specific credentials from one immutable release. Key ID uniqueness is enforced where authority lives: K-ROOT registry building and `verify_registry_succession` | one release cycle. Needs a B1b-3e release-set contract replacing the initial-custody `RELEASE_SET` rule (SF-2) |

**Credential name (RR-11c-1).**

| Option | Shape | Consequence |
| --- | --- | --- |
| **N1 (recommended)** | the same embedded name `owner-actor-signing-key`, at a distinct path | cutover is an atomic same-filesystem rename into the CURRENT slot; `blobSha256` is unchanged, so B2 still matches the publication |
| N2 | a distinct embedded name | the blob can never load in the unit, even if moved. Cutover needs re-encryption (a new plaintext exposure and a new publication) or a unit change (a new release per rotation) |
| N3 | a per-key unit path | every cutover is a unit change, which is a release change |

**Location (RR-11c-2, GC-2).**

| Option | Shape | Consequence |
| --- | --- | --- |
| L-a | the PREPARED slot inside `/etc/credstore.encrypted` (B1b-3d §13 5a) | conflicts with the keygen precondition (SF-1) and the design §11.2 "no other blob" condition during `S_PREPARED`…`S_ACTIVATED` |
| **L-b (recommended)** | a separate root-only directory on the same filesystem | the credstore keeps the invariant "exactly one authority blob = the CURRENT slot" at every moment except the atomic rename |

**Predecessor destruction timing (RR-11b, GC-1).**

| Option | Shape | Consequence |
| --- | --- | --- |
| D-1 | the design §7.4 step 5: rename S over P at the swap; P's bytes leave active custody at `S_ACTIVATED` | one mutation; no debt window. It contradicts this brief's non-destruction-before-`S_CURRENT` requirement. P has no authority value after `S_PUBLISHED`, so nothing security-relevant is lost |
| **D-2 (recommended)** | move P to the non-loadable RETIRED holding location at the swap; destroy it only after `S_CURRENT` (§11 retirement phase) | satisfies the brief. The credstore invariant holds. It adds a bounded `KNOWN_CUSTODY_DEBT` window and one extra mutation. It gives forensic continuity, not a rollback path |

### 7.5 Recommendation

**PENDING_OWNER_DECISION:** R-B + N1 + L-b + D-2.

The one SOURCE-DETERMINED part: the current reviewed release cannot generate
a successor (R-C excluded).

Every other part needs source work first:

- the successor keygen form;
- a B1b-3e release-set rule;
- an installer stage;
- the binding completeness check (RR-19).

## 8. The dual-current hidden assumption

**"What assumption could make every individual artifact look valid while the
overall system is wrong?"**

The assumption is: **there is exactly one witness chain per environment,
every consumer evaluates that same chain, and the owner has at most one
executable authorization outstanding per prior head.** Every artifact check
is local. Only the lineage makes the checks jointly consistent.

**The single authoritative lineage is the `RecoveryWitnessV2` chain,
verified from genesis.** It prevents `A → B` and `A → C` from both becoming
current through five mechanisms together:

1. **Exact prior-head binding.** (B) names `(vA, digestA)`. After one
   execution the head is `(vA+1, digestB)` and never returns to `vA`, because
   the chain is linear and contiguous. The other authorization fails
   `PRIOR_HEAD_MISMATCH` forever.
2. **Contiguous head.** `target = prior + 1`; the same version with another
   digest is `WITNESS_REGISTRY_FORK`.
3. **Single-use authorization.** Consumed IDs are recorded; a replay is
   `CHAIN_AUTHORIZATION_REPLAYED` / `AUTHORIZATION_CONSUMED`.
4. **One entry per version.** `chain/<v>.json` is created `O_EXCL`; a second
   successor at the same version cannot be written into the same chain by
   the service.
5. **One writer.** A single instance, serialized requests, and `flock`.

Every other artifact is subordinate and never selects current state:

| Artifact | Why it cannot make a second current |
| --- | --- |
| two signed candidate registries | only a witness entry makes one the head; the other stays story 4 (F21) |
| two `RegistryHeadAdvanceAuthorizationV1` from one prior head | the first executed wins; the second fails its prior-head binding |
| two prepared credential slots | the PREPARED slot holds one blob (refusal if non-empty); only the blob matching the head key's publication is the current credential |
| two valid witness successors | a `FORK`. It fails closed (§6.3); it is never resolved by choice |
| two `HEALTH` fingerprints at different times | `HEALTH` is B4, a claim at an instant. A binding result is valid only for the head it names (`registryHead` in its facts). Any head change voids earlier binding results |

Timestamps, mtimes, "last file wins", and filename order are never used.

**Where the assumption breaks, and who decides:**

- **Inside one chain:** only with K-WIT misuse (RR-6 S11). It is detected as
  a fork, replay, or ordering violation, and fails closed.
- **Across chains:** a second genesis (re-bootstrap over the same anchor) or
  a cloned VM gives two individually valid chains. A pinned genesis digest
  (**RR-21**) would detect a second genesis. **A clone shares the genesis and
  is not detected: whole-host rollback, unresolved.**
- **The owner rule** of the design §7.6 ("do not sign a competing (B) from
  the same prior head until the earlier one has expired") is the only
  defence that spans chains. This gate makes it a live-entry requirement:
  the owner keeps a register of issued authorization IDs, and at most one
  unexpired authorization exists per prior head.
- **Deciding a detected fork:** only the owner, with K-ROOT, authors the
  resolution: a new contiguous head or an epoch advance from the chosen
  lineage, or a re-bootstrap. The witness never chooses. The verifier only
  reports. Host root may preserve evidence but decides nothing.

## 9. State owners

| State | Owner | May request | May mutate | May verify | Restorable? | Rollback-sensitive? | Authority-bearing? | Freshness-bearing? |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| K-ROOT registry authority (registry generations) | the owner, offline, K-ROOT | the owner | the owner (signs a new generation; never edits one) | anyone, with the pinned root | the bytes, yes; authority only at the witnessed head | yes (old bytes → `REGISTRY_DOWNGRADE` / off-head) | **yes** | no |
| registry-head execution authorization (`RegistryHeadAdvanceAuthorizationV1`) | the owner, K-ROOT (object); the witness chain (consumption) | the owner | K-ROOT signs; the witness consumes | the witness planner; the verifier | the object, yes (harmless once consumed or off its prior head) | a witness restored alone could meet a replay; fails closed via the ledger position | **yes**, for one transition | no |
| recovery-epoch execution authorization (`EpochAdvanceAuthorizationV1`) | as above | the owner | as above; plus the signer's pre-witness adoption record (C-4) | as above | as above | as above | **yes**, for one transition | no |
| `RecoveryWitnessV2` (chain authoritative; pointer derived) | `lilith-recovery-witness` | host root (owner socket), the signer (ledger advance only) | the witness service only | the independent verifier (full chain) | a chain restored alone → `LEDGER_AHEAD_OF_WITNESS` (fail closed). Restored with everything → undetected | **yes** | no | **yes** |
| authority recovery ledger | `lilith-authority-dev` | the signer's own operations | the signer only (destroy/narrow-only for recovery records) | the verifier (read-only copy) | adopted only if equal to the witnessed position | **yes** | no | position only (bound by the witness) |
| credential custody (CURRENT / PREPARED / RETIRED) | host root + systemd | the owner | host root via the fixed CLIs | root-observed hashes (B2); publications (B3) | forbidden in DEV_SYNTHETIC; a restore is `STALE_CREDENTIAL_PRESENT` or worse (§5) | yes (a stale blob fails the binding) | no | no |
| key publication (B3) | the owner transcript | — | written once, by the keygen output | the verifier | yes (public, a record) | no | no | no |
| signer loaded key | the running signer process | — | systemd at unit start (from the CURRENT slot) | B4 is a claim; the verifier binds it via B1–B3 | n/a (runtime) | yes (it reloads whatever sits in the slot) | no | no |
| ceremony hold | host root | the owner (unauthenticated intent, RR-13) | host root | anyone (presence only) | a restored hold is only availability loss; a removed hold still needs readiness | fails safe | no | no |
| verification / readiness result | the independent verifier (stateless) | the owner | none (re-derived every time) | reproducible by anyone with the inputs | n/a | results are bound to the head they name | no | no |

No new service, identity, socket, or state owner is introduced.

## 10. Live entry matrix (future DEV_SYNTHETIC rehearsal)

`ENTER` means only "this row does not block". Entry needs every row to be
`ENTER` or `ENTER WITH EXPLICIT NONCLAIM`, **and** a separate owner
authorization of the rehearsal design. **Passing source tests never
authorizes a live ceremony.**

| Condition | Verdict |
| --- | --- |
| B1b-3d L3a–L4 not live and accepted (no registry, anchors, witness, ledger, or `RESTORE_READY` signer) | **DO NOT ENTER** |
| RR-6 unresolved | **DO NOT ENTER** |
| RR-7 classification ambiguous, or any current-key artifact in class 2–4 | **DO NOT ENTER** |
| RR-7 resolved; current-key artifacts only in class 5 or 6 | ENTER WITH EXPLICIT NONCLAIM (named debt) |
| RR-9 recovery algorithm not implemented and fault-tested in source | **DO NOT ENTER** |
| RR-11 successor slot/release unresolved, or no reviewed successor keygen | **DO NOT ENTER** |
| `RecoveryWitnessV2` source absent | **DO NOT ENTER** |
| `RecoveryWitnessV2` pure contracts present only (today, SF-9) | **DO NOT ENTER** |
| `RecoveryWitnessV2` durable writer + service + RR-9 recovery present and tested | ENTER |
| live witness custody (K-WIT, service, V2 genesis, chain) absent | **DO NOT ENTER** |
| live witness custody present; chain verifies from genesis; pointer = head | ENTER |
| successor credential absent at preflight | ENTER (required) |
| successor credential present at preflight | **DO NOT ENTER** until classified (§5) and destroyed |
| current credential binding unverified | **DO NOT ENTER** |
| current credential binding verified at the current head (B1–B4 plus RR-19) | ENTER |
| K-ROOT authorization absent at preflight | ENTER (it is created inside the ceremony) |
| an unexpired K-ROOT authorization from the current head already exists | **DO NOT ENTER** (competing-authorization risk, §8) |
| an active hold present at preflight | **DO NOT ENTER** (unexplained ceremony state) |
| the hold released at preflight | ENTER |
| authority recovery ledger position equals the witness | ENTER |
| authority recovery ledger stale, ahead, or unverifiable | **DO NOT ENTER** |
| whole-host rollback protection absent | ENTER WITH EXPLICIT NONCLAIM (`wholeHostRollbackProtected: false`) |
| snapshot inventory unknown, RR-17 undecided | **DO NOT ENTER** |
| RR-16 undecided | ENTER WITH EXPLICIT NONCLAIM, for a routine rotation rehearsal only (no compromise-replacement claim) |
| RR-18 undecided | **DO NOT ENTER** (the witness schema is undefined) |
| RR-19 undecided | **DO NOT ENTER** (`S_CURRENT` would rest on an incomplete binding) |
| RR-20 undecided | **DO NOT ENTER** |
| RR-21 undecided | ENTER WITH EXPLICIT NONCLAIM (a second genesis would not be detected) |
| preservation set (B1b-3d §23) changed | **DO NOT ENTER** |

## 11. Future rehearsal phases (routine rotation; no commands)

This is the minimum sequence for an in-epoch routine rotation P → S (RR-6 S1).
A compromise-replacement or epoch-advance rehearsal is a separate, later
ladder. Every phase starts by re-hashing the preservation set and
re-verifying the chain. **"Usable" means P may resume issuance if the owner
aborts and releases the hold.**

| Phase | PRE | The one authority-relevant mutation | POST evidence | STOP if | Rollback boundary | P usable? | S may issue? | `S_CURRENT`? |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| L3e-0 preflight | §10 all green | none | the inventory; chain verification; ledger = witness; binding at head; credential inventory (CURRENT only); RR-7 classes | any §10 row blocks | — | yes | no | no |
| L3e-1 hold | L3e-0 PASS | write the ceremony hold (`S_PROPOSED`) | hold hash; signer refuses creating ops | hold not observed | remove the hold | yes (after release) | no | no |
| L3e-2 quiesce | hold present | stop the signer (a runtime, not an authority, mutation; kept separate by the one-mutation rule) | no signer-uid process | signer still running | start again (hold still blocks) | yes | no | no |
| L3e-3 successor preparation | PREPARED slot empty | successor keygen → PREPARED slot (`S_PREPARED`) | publication; slot hash = `blobSha256`; CURRENT slot hash unchanged; output scan clean | any private pattern; CURRENT slot changed | destroy the PREPARED blob | yes | no (`KEY_UNKNOWN`) | no |
| L3e-4 registry candidate | publication recorded | offline: K-ROOT signs candidate vN+1 (S current, P `SUPERSEDED`, `t_cut`) (A) | candidate digest; `verify_registry_succession(vN → vN+1)` passes offline | succession or single-current fails | discard (stays story 4) | yes | no | no |
| L3e-5 head authorization | (A) verified; no other unexpired (B) from vN | offline: K-ROOT signs (B) vN → vN+1 (`S_AUTHORIZED`) | authorization ID recorded in the owner register | a competing (B) exists | let (B) expire; abort | yes | no | no |
| L3e-6 witness head advance | chain head = vN; (A), (B) verify | the witness executes (B) (`S_PUBLISHED`). **Point of no return** | new chain entry; pointer = head; consumed ID; recovery classification `CONSISTENT` | refusal (state unchanged) | **none: forward only** | **no, never again** | no | no |
| L3e-7 serve head registry | head = vN+1 | install vN+1 bytes as the served registry (story 4) | served digest = head digest | mismatch | reinstate the head bytes | no | no | no |
| L3e-8 credential cutover | served = head | P: CURRENT → RETIRED holding (D-2), then S: PREPARED → CURRENT (two renames, each its own step, 8a/8b) | credstore holds exactly S's blob; RETIRED holds P | any other blob present | forward only (P cannot be current) | no | no | no |
| L3e-9 activation | S in CURRENT; hold present | start the signer: `REGISTRY_VIEW{vN+1,[S]}` journalled; witness records the ledger advance (one protocol step; crash → `LEDGER_AHEAD_OF_WITNESS`, fail closed) (`S_ACTIVATED`) | `HEALTH` = S; ledger view; witness ledger position | `HEALTH` ≠ S; ledger ahead | stop the signer; diagnose | no | no | no |
| L3e-10 independent verification | `S_ACTIVATED` | none (the verifier emits `AuthorityKeyTransitionV1` as a record) | readiness `RESTORE_READY`; binding B1–B4 plus RR-19; transition record | anything except READY + binding | the hold stays | no | no | eligible only |
| L3e-11 hold release | L3e-10 PASS; owner decision | remove the hold (`S_CURRENT`) | hold absent; readiness still READY | readiness changes | recreate the hold | no | **yes**, per-operation readiness | **yes** |
| L3e-12 predecessor retirement | `S_CURRENT` | destroy P's blob from the RETIRED holding (D-2) | RETIRED empty; `predecessorMaterialDestroyedFromActiveCustody: true` (active custody only) | any copy remains | none needed | no | yes | yes |
| L3e-13 crash/restore proofs | `S_CURRENT`; fault hooks TEST-proven | one injected fault per sub-step (RR-9 cases §6.4; stale credential into CURRENT (F7/F20); stale registry served (F21); competing authorization (F6)), each preserve → inject → observe → restore | classification and readiness per case | any `RESTORE_READY` on a stale, torn, or forked state | restore the preserved state (hash-verified) | no | only when READY | yes, after each restore |

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
- zeroization;
- automatic trust in restored backups;
- **any live rotation**;
- **any live epoch advance**;
- any live ceremony, runbook, or command;
- that source tests passing authorizes live entry.

## 13. Owner decisions

| # | Exact question | Options | Security consequence | Operational consequence | Recommendation | Classification |
| --- | --- | --- | --- | --- | --- | --- |
| RR-6 | When does key compromise require in-epoch replacement only, and when a RecoveryEpoch advance? | A: never epoch; B: always epoch; C: by suspect-state set (§4.2) | A keeps suspect in-flight state. B implies protection it cannot give for S8–S11. C matches remedy to state; an epoch never protects against a boundary that mints the next key | C needs RR-7 classification and the S4 suspicion rule | **C**, with the DEV_SYNTHETIC V1 rule: current issuing-key compromise → `KEY_COMPROMISE` epoch advance; non-current key → in-epoch marking; boundary/root → stop and re-custody (§4.4) | **PENDING_OWNER_DECISION** |
| RR-7 | How are retained or restored key materials classified, and what does each class require? | the design's two-way boundary rule, or the closed six-class model (§5.2) | the six-class model closes "probably safe", treats unknown provenance as exposure, and makes ciphertext safety conditional on the host key | needs an inventory per artifact; snapshots need RR-17 | **the closed model**; entry only with class 5/6 as named debt | **PENDING_OWNER_DECISION** |
| RR-9 | How does the witness recover from a crash between the chain append and the pointer replacement? | roll-forward-only on a unique verified successor (§6.3); or fail closed on any mismatch | roll-forward never loses a committed transition; failing closed on every mismatch strands committed transitions (availability) but never rolls back | needs a durable writer, the `chain/` directory fsync, and fault tests (SF-9) | **§6.3**: chain authoritative, pointer derived, automatic roll-forward only for a unique verified head, owner for everything else | **PENDING_OWNER_DECISION** |
| RR-11 | How is a successor credential prepared side by side, from which release? | release R-A / R-B (R-C excluded by source); name N1/N2/N3; location L-a/L-b; destruction D-1/D-2 (§7.4) | N1 + L-b keep a single loadable slot and a clean credstore; D-2 avoids destroying P before `S_CURRENT` at the cost of a bounded debt window | R-B is one release cycle; R-A is one per rotation | **R-B + N1 + L-b + D-2** | **PENDING_OWNER_DECISION** (except "the current release cannot generate a successor": **SOURCE/DESIGN_ALREADY_DETERMINED**, SF-1) |
| RR-16 | Should an in-epoch compromise-plus-successor transition get an evaluable contract, or is the epoch advance the only compromise-replacement path for DEV_SYNTHETIC V1? | accept the epoch path only; or add a source contract (GC-7) | none, if the epoch path is used | adding it is source work | accept the epoch path only, for V1 | **PENDING_OWNER_DECISION** |
| RR-17 | Are cloud-level disk snapshots (and the principals able to read them) inside the K-ACT custody boundary, and is a read-only snapshot inventory a live-entry prerequisite? | inside, with an inventory; outside (every snapshot → `EXPOSED`); undecided (`UNKNOWN_PROVENANCE`) | decides whether every post-L2b.2 snapshot exposes K-ACT | an inventory is a separately authorized read-only cloud contact | outside by default; entry after an owner-authorized inventory shows none, or after the owner accepts named ones as debt | **PENDING_OWNER_DECISION** |
| RR-18 | Does the live witness bootstrap `RecoveryWitnessV2` at genesis, superseding the B1b-3d §10 V1 operation set (GC-4)? | V2 genesis; or V1 then a migration | a V1→V2 migration is not designed; V2 genesis avoids a migration seam | the B1b-3d L3b step must name V2 | **V2 genesis** (`plan_witness_v2_genesis` exists) | **PENDING_OWNER_DECISION** |
| RR-19 | Must the readiness binding include a root-observed credential inventory (fixed embedded name; exactly one authority blob in the credstore), as the design §11.2 requires but source lacks (GC-3)? | add the input; or drop the design condition | without it, an extra loadable blob or a renamed credential is not detected by the verifier | verifier source work | **add it** before any live `S_CURRENT` | **PENDING_OWNER_DECISION** |
| RR-20 | Must readiness re-verify, from owner-retained objects, the K-ROOT authorization for every consumed ID in the chain, closing the K-WIT-only head promotion that SF-7 allows? And after a decryptable-snapshot exposure (S8), is host credential-key rotation required? | yes / no for each | re-verification binds freshness back to K-ROOT; host-key rotation invalidates every blob under the burnt key | the owner keeps authorization objects; host-key rotation forces K-ACT and K-WIT re-keying | **yes** to both | **PENDING_OWNER_DECISION** |
| RR-21 | Should the owner pin the witness genesis digest in the verifier trust inputs? | pin; do not pin | detects a second genesis over the same anchor; does **not** detect a clone | one owner record at bootstrap | **pin** | **PENDING_OWNER_DECISION** |

Carried forward unchanged from the design: RR-8, RR-10a, RR-12, RR-13, RR-14a
(`DEFERABLE`); the B1b-3c open decisions 3, 5 (T-4), 6, 7; B1b-3d T-6, T-9.

## Explicitly not done

- No DEV or PROD contact. No gcloud, SSH, IAP, sudo, systemctl, or
  systemd-creds.
- No key generated, rotated, revoked, deleted, or restored. No registry,
  witness, epoch, authority recovery ledger, broker ledger, or L04 touched.
- No IAM, WIF, or sudoers change. No Stage III retry. No First Memory.
- No live ceremony script, runbook, deployment, or mutation command.
- No source, test, vector, workflow, or earlier record changed.
- No PENDING item marked accepted.
