# Slice 15B2b-B1b-3e — Source Prep B Design: Successor Custody and Compromise Recovery

Status:

- **DESIGN CLOSURE** (SW-1, SW-2, SW-9; RR-11-D1, RR-11-D2)
- **SOURCE NOT IMPLEMENTED**
- **LIVE REHEARSAL NOT AUTHORIZED**
- **OWNER DECISIONS PENDING:** RR-11-D1, RR-11-D2, RR-22 … RR-29 (§18).
  Recommendations here are not owner decisions
- **WHOLE-HOST ROLLBACK UNRESOLVED**
- **REAL AUTHORITY ABSENT**

Base: protected main `75f8946e8bff71abc426a6a728c8ee9ead3ecbef`.

This record closes the design questions that block the Source Prep B
implementation of the [live-rehearsal gate](slice-15b2b-b1b3e-live-rehearsal-gate.md)
("the gate") §14:

| Item | What it covers |
| --- | --- |
| SW-1 | predecessor retention and destruction ordering |
| SW-2 | the successor-capable release, and side-by-side preparation and cutover |
| SW-9 | the accepted current-key compromise recovery path |

It builds on:

- the [B1b-3e design](slice-15b2b-b1b3e-rotation-revocation-recovery.md) ("the
  design");
- the [source contracts](slice-15b2b-b1b3e-source-contracts.md) ("B1b-3e-S");
- [Source Prep A](slice-15b2b-b1b3e-source-prep-a-witness-readiness.md)
  ("Prep A");
- the B1b-3d [custody design](slice-15b2b-b1b3d-dev-synthetic-custody-design.md),
  [L2 custody preparation](slice-15b2b-b1b3d-l2-custody-preparation.md), and
  [live closure](slice-15b2b-b1b3d-live-closure.md) records.

It contains no commands.

Nothing was contacted or changed. No DEV, PROD, gcloud, SSH, IAP, sudo,
systemctl, or systemd-creds was used. No key, credential, registry, witness,
epoch, ledger, broker, L04, IAM, WIF, sudoers, Python source, unit file,
workflow, or runtime configuration was touched.

Labels:

| Label | Meaning |
| --- | --- |
| **SOURCE FACT** | read from current source at the base |
| **ALREADY_DETERMINED** | fixed by an accepted record or by current source; not reopened |
| **DERIVED** | follows necessarily from accepted decisions and current source; not a new choice |
| **PENDING_OWNER_DECISION** | a new choice. A recommendation is given; nothing is accepted here |

## 1. Controlling source facts

Current source is the authority for current behaviour.

| # | Fact | Location |
| --- | --- | --- |
| PB-1 | Service account and group `lilith-authority-dev`; unit `lilith-authority-dev.service` | `profile.py` (`SERVICE_USER`, `SERVICE_GROUP`, `SERVICE_UNIT`) |
| PB-2 | Runtime credential name `owner-actor-signing-key` (`CREDENTIAL_NAME`). The only private-material source is `$CREDENTIALS_DIRECTORY/owner-actor-signing-key`, and the directory must equal `/run/credentials/lilith-authority-dev.service` | `profile.py`; `credential.py` `inspect_owner_actor_credential` |
| PB-3 | The encrypted source is `/etc/credstore.encrypted/lilith-authority-dev.owner-actor.cred` (`CREDENTIAL_SOURCE`). The unit's only credential directive is `LoadCredentialEncrypted=owner-actor-signing-key:/etc/credstore.encrypted/lilith-authority-dev.owner-actor.cred`. It also has `InaccessiblePaths=/etc/credstore.encrypted …` | `profile.py`; `deploy/lilith-authority-dev.service` |
| PB-4 | The keygen accepts exactly `actor`; `witness` is refused. It has a fixed `KEY_ID = test-only.dev-synthetic.actor.b1b3d.1`, a fixed path, and encryption via `systemd-creds encrypt --with-key=host --name=owner-actor-signing-key`. It requires root, an isolated interpreter, the DEV machine ID and hostname, no swap, and the host key `0400`. It refuses `CREDENTIAL_ALREADY_PRESENT` and `CREDSTORE_NOT_EMPTY`. The blob is written `O_WRONLY|O_CREAT|O_EXCL|O_NOFOLLOW` `0600`, then file fsync, then credstore-directory fsync. stdout carries only the canonical publication | `ceremony/lilith_authority_keygen_dev.py` |
| PB-5 | Publication `LILITH_AUTHORITY_KEY_PUBLICATION` v1, with two parts. `publicVerificationMaterial` = `{keyId, signingDomain, evidenceTypes, environment, algorithm, publicKey, publicKeySha256}`. `custodyEvidence` = `{credentialName, credentialPath, withKey, machineId, blobByteSize, blobSha256}`. Prep A parses `publicVerificationMaterial` exactly, but reads only `blobSha256` and `credentialName` from `custodyEvidence` | keygen `publication()`; `rotation_contracts.KeyPublicationV1`; `witness_readiness.verify_current_credential_binding` |
| PB-6 | `HEALTH.publicKeySha256` is derived at startup from the loaded PKCS#8 key: `sha256(raw public key)`. The server exits `CREDENTIAL_ABSENT` or `CREDENTIAL_INVALID` before serving, so a signer without a credential never runs. L1 readiness is always `NOT_READY` | `credential.py` `_classify`; `server.py` `main`; `core.py` |
| PB-7 | The installer's `RELEASE_SET` requires exactly one entry under `/opt/lilith-authority-dev/releases`. Its own comment says B1b-3e may define another set. The keygen CLI `/usr/local/sbin/lilith-authority-keygen-dev` must equal the release member `cli/lilith-authority-keygen-dev` | `ceremony/install_authority_dev.py` `status`, `stage_cli` |
| PB-8 | The file set is explicit. `SOURCE_FILES` lists every file under `services/authority-dev/`. `SHARED_HASHES` pins three shared contract modules. The runtime payload refuses key-generation markers (`.generate()`, `Ed25519PrivateKey.generate`). The keygen is ceremony tooling, shipped as a separate CLI member | `release_file_set.py` |
| PB-9 | Live baseline: `RELEASE_SHA 9ac7de2…`. K-ACT `test-only.dev-synthetic.actor.b1b3d.1`; blob hash `6a61c350…`; units inactive; `ACTIVATION=NOT_ACCEPTED reason=GRANT_ABSENT`. No registry, witness, K-WIT, or authority ledger exists live | live closure §3, §4, §6 |
| PB-10 | `evaluate_rotation` requires the predecessor to become `SUPERSEDED` in the candidate. The head-advance planner does not require the target to have a current key. The epoch planner does (`TARGET_HAS_NO_ISSUANCE_KEY`). `verify_registry_succession` allows `null → COMPROMISED` and `ROUTINE`/`SUPERSEDED → COMPROMISED`; `HEAD_ADVANCE_REASONS` includes `COMPROMISE_MARKING` | `rotation_contracts.py` |
| PB-11 | Prep A binding: the unit has exactly one `LoadCredentialEncrypted` reference, under the fixed name and at the CURRENT path. The publication's `credentialName` is the fixed name. The inventory verifies with its CURRENT hash equal to B2. Inventory phases are `STEADY`, `SUCCESSOR_PREPARED`, `CUTOVER_VACATED`, `CUTOVER_INSTALLED`; only `STEADY` and `CUTOVER_INSTALLED` can be ready | `witness_readiness.py` |
| PB-12 | Design §7.7 already defines `AuthorityKeyTransitionV1` as a **PROPOSED record, story 4**, emitted by the verifier. Design §9.1 defines `CeremonyHoldV1` as a **PROPOSED gating container, story 4**, with every field unauthenticated. Neither is authority | design §7.7, §9.1 |
| PB-13 | C-4 order (accepted) for an epoch advance: hold, then the signer journals `ADVANCE_EPOCH`, then the witness executes, then quarantine, then the witness again, then credential swap and verification. The adoption is journalled by the **running signer** with the old credential loaded, and it needs no signing | design §9.3, §9.4 |

## 2. Inherited decisions (not reopened)

These are ALREADY_DETERMINED:

- **Current issuing key compromised:** `COMPROMISED` marking → `KEY_COMPROMISE`
  epoch advance → recovery successor path (RR-6).
- **Non-current key compromised:** in-epoch marking only, unless another
  domain is suspect.
- **Root, host custody, K-ROOT, or K-WIT compromise:** STOP.
- **No in-epoch compromised-current + successor contract** (RR-16 closed).
- **The witness starts at V2 genesis** (RR-18).
- **Side-by-side successor preparation.** The current blob is never
  overwritten, and P is not destroyed before an independently verified
  `S_CURRENT` (RR-11).

```text
credential existence   != authority
credential loaded      != current authority
service restart order  != authority
filesystem name/path   != authority
S_ACTIVATED            != S_CURRENT
retention              != authority
destruction            != revocation
revocation             != destruction
cryptographic ability to sign != authorization to issue
logical destruction    != media zeroization
```

## 3. Logical custody roles

The minimum set is three roles plus absence. Prep A already uses the names
`CREDSTORE`/CURRENT, `PREPARED`, and `RETIRED`. This record keeps them.
`RETIRED` is the gate's "RETIRED holding", which the brief calls
RETAINED_PREDECESSOR.

**No `ABANDONED` role is introduced.** An abandoned successor is simply a
`PREPARED` blob that is destroyed (gate §7.1). A distinct role would add a
fourth loadable-looking location without adding a property.

| Role | Holds | Created by | Readable by | systemd may load? | Signer may observe? | Deployer may observe? | Authority? | Survives restart? | May be destroyed? | Contract |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| **CURRENT** | exactly one blob: the one the unit loads | the initial keygen (B1b-3d L2b); later, only the cutover install (a same-filesystem rename of PREPARED) | root only | **yes, the only one** (PB-3) | no (`InaccessiblePaths`). It sees only the decrypted `$CREDENTIALS_DIRECTORY` copy | no | **no**. Its blob is current only if its hash equals the head key's publication (B2 = B3) | yes | only by the cutover vacate. Never overwritten | `root:root 0600` regular file in `root:root 0700` `/etc/credstore.encrypted` |
| **PREPARED** | at most one successor blob | the successor keygen only | root only | **no**: referenced by no unit | **no**: must be `InaccessiblePaths` in the successor release (§9) | no | no. The key is `KEY_UNKNOWN` until a head names it | yes | yes, while `NOT_IN_HEAD` (abandon); otherwise it is emptied by the cutover install | `root:root 0600` regular file in a `root:root 0700` directory, on the credstore's filesystem |
| **RETIRED** | at most one predecessor blob | the cutover vacate only (a same-filesystem rename of CURRENT) | root only | **no** | **no** (`InaccessiblePaths`) | no | no. The key is non-current at the head. Class `KNOWN_CUSTODY_DEBT`, or `COMPROMISED` in SW-9 | yes | **only after independently verified `S_CURRENT`** (§4) | as PREPARED |
| **ABSENT** | nothing | — | — | a unit whose CURRENT is absent fails to start (fail safe) | — | — | — | — | — | Prep A `ABSENT` |

No application, deployer, broker, or witness identity reads any role. The
successor keygen is the only writer of PREPARED. The cutover step is the
only mover between roles. The destruction step is the only unlinker of
RETIRED.

## 4. SW-1 — predecessor lifecycle and destruction ordering

### 4.1 Routine rotation, in-epoch (gate §11 phases)

| Gate phase | Head (authority) | CURRENT | PREPARED | RETIRED | Inventory phase | P usable if aborted? | May P return to CURRENT? | P destroyable? |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| L3e-0..2 preflight, hold, quiesce | vN (P current) | P | — | — | `STEADY` | yes | n/a (already there) | **no** |
| L3e-3 prepare | vN | P (unchanged, re-hashed) | S | — | `SUCCESSOR_PREPARED` | yes | n/a | no |
| L3e-4/5 candidate + authorization signed | vN | P | S | — | `SUCCESSOR_PREPARED` | yes (let (B) expire) | n/a | no |
| **L3e-6 witness executes (B)** | **vN+1 (S current, P `SUPERSEDED`)** | P | S | — | `SUCCESSOR_PREPARED` | **no, never again** | **no** | no |
| L3e-7 serve vN+1 | vN+1 | P | S | — | `SUCCESSOR_PREPARED` | no | no | no |
| L3e-8a vacate | vN+1 | — | S | P | `CUTOVER_VACATED` | no | **no** | no |
| L3e-8b install | vN+1 | S | — | P | `CUTOVER_INSTALLED` | no | no | no |
| L3e-9 activate (`S_ACTIVATED`) | vN+1 | S (loaded) | — | P | `CUTOVER_INSTALLED` | no | no | no |
| L3e-10/11 verify, release (`S_CURRENT`) | vN+1 | S | — | P | `CUTOVER_INSTALLED` | no | no | **permissible after this row's POST** |
| L3e-12 retire P | vN+1 | S | — | — | `STEADY` | no | no | done |

**Answers (DERIVED from RR-11, the gate §11 rollback column, and PB-10):**

- **When CURRENT may be vacated.** Only after the authority PONR (L3e-6) and
  after the head registry bytes are served (L3e-7). Before L3e-6, P must
  remain in CURRENT untouched, because an abort must leave P usable.
- **When P becomes non-loadable.** At L3e-8a, by a same-filesystem rename
  CURRENT → RETIRED. It is a rename, not a copy, so no second copy appears.
- **When S may occupy CURRENT.** At L3e-8b, only after 8a's POST shows CURRENT
  empty and RETIRED = P. It is a same-filesystem rename PREPARED → CURRENT.
  S is never loaded before the head names it.
- **Crash between 8a and 8b** (CURRENT empty). The unit cannot start, and
  systemd fails closed on the missing source. Nothing issues. Recovery is
  forward only: complete 8b. `CUTOVER_VACATED` is a recognized inventory
  phase, so the state is classifiable. It is never "put P back".
- **S installed, signer not started** (`CUTOVER_INSTALLED`, no `HEALTH`).
  Nothing issues. Start under the hold (L3e-9).
- **Signer starts but `HEALTH` reports P.** This is only possible if CURRENT
  holds P's blob. The Prep A binding fails (`BLOB_HASH_MISMATCH` against S's
  publication), and so does the inventory (duplicate or unexpected). Stop the
  signer, keep the hold, and diagnose. Forward only.
- **`HEALTH` reports S but the binding fails** (F20). The hold stays and P
  stays retained. Diagnose. No destruction, no `S_CURRENT`.
- **When P may be restored to CURRENT.** Only **before** L3e-6, and then
  there is nothing to restore, because P never left.
- **When rollback to P is forbidden.** From L3e-6 onwards, permanently. P is
  `SUPERSEDED` at the witnessed head and can never be current again (gate SF-10).
  A loaded P can only fail the binding.
- **When destruction becomes permissible.** Only after the independent
  verifier reproduced `S_CURRENT`, i.e. every Prep A readiness check `PASS`
  at head vN+1 with the binding naming S. The hold may be released or still
  in place. Destruction is permitted, not required, at that point.
  RR-29 asks how long P may remain.
- **Evidence and zeroization.** See §13.

```text
retention   != authority      (a retained P is custody debt, not a fallback)
destruction != revocation     (P was made non-current by K-ROOT at L3e-6, not by deletion)
revocation  != destruction    (P's K-ROOT SUPERSEDED marking deletes nothing)
S_CURRENT independently verified -> then, and only then, predecessor destruction
```

**SW-1 source requirement.** A pure destruction-ordering verifier refuses
destruction unless it is given a Prep A readiness result that is `READY` at
the same head, with a binding naming the successor, and an inventory in
`CUTOVER_INSTALLED` whose RETIRED hash equals P's publication. The rotation
assessment and `AuthorityKeyTransitionV1` report `predecessorMaterial:
RETAINED | DESTROYED_FROM_ACTIVE_CUSTODY`. A retained P never satisfies
readiness: that is already proven by Prep A (the CURRENT hash must equal the
head key's publication).

### 4.2 Points of no return

They are distinct and ordered. None is collapsed into another.

| PONR | Event | Reversible? |
| --- | --- | --- |
| **Authority** | `RecoveryWitnessV2` commits the chain entry that consumes (B) or the `EpochAdvanceAuthorizationV1` (Prep A commit point). P is no longer the witnessed-head current key | **never**. Forward only: a new K-ROOT generation (for example vN+2 revoking S `ROUTINE` and naming S′, design §7.6) |
| **Custody** | L3e-8a: P is made non-loadable (CURRENT → RETIRED). L3e-8b: S installed | the moves are physically reversible renames. They are **forbidden** to reverse, because the authority PONR already happened. They are only ever completed forward |
| **Currentness** | the independent verifier passes `S_CURRENT` (and the hold is released for issuance) | readiness is re-derived per operation. Losing it (binding, inventory, ledger, hold) returns to `NOT_READY` without any authority change. The predecessor is never re-admitted |
| **Material** | L3e-12: P's blob unlinked and the directory fsynced | irreversible for active custody. It is not a media-level guarantee (§13) |

**Critical answer: can P be restored to the loadable slot after the witness
committed the successor head but before `S_CURRENT`?** **No.**

The fail-closed path instead:

- If S's blob is missing or unloadable, the signer does not start. Nothing
  issues, and the hold stays.
- The owner recovers forward: a new successor S′ through a new rotation
  (vN+1 → vN+2, S `ROUTINE`-revoked with zero issued evidence, S′ current).
- P stays retained until an `S′_CURRENT` and is then destroyed.

Even if root copied P back into CURRENT, the signer could load and sign, but
it could not issue. The head names S, so B1 ≠ P's publication → binding
fails → `NOT_READY`. P's signatures dated at or after `t_cut` are
`KEY_REVOKED`. This is why the answer is "forbidden" and not merely
"useless": restoring P turns a `KNOWN_CUSTODY_DEBT` blob into
`STALE_CREDENTIAL_PRESENT` in the unit slot (RR-7).

This answer is DERIVED from the gate §11 ("forward only" from L3e-6) and
RR-7. It is not a new decision.

## 5. RR-11-D1 — release reuse

**Question.** Does one reviewed successor-capable release serve multiple
rotations, or does every rotation need its own reviewed release?

| Criterion | A. reusable, free inputs (keyId, path as arguments) | B. one reviewed release per rotation (keyId compiled in) | C. reusable closed form: one bounded ordinal; everything else fixed |
| --- | --- | --- | --- |
| Auditability | weak: the output depends on arbitrary arguments | strong per release | strong: the whole input space is a pattern; each ceremony is recorded |
| Attack surface | a generic key generator | smallest per artifact, but a new runtime release each time | small and closed |
| Release immutability | preserved, but the behaviour is open | preserved | preserved |
| Code-to-ceremony coupling | none | total: code change per rotation | moderate: the code fixes the form, the ceremony fixes N |
| keyId uniqueness | caller-chosen (collisions possible) | reviewed per release | derived from N by one fixed rule; uniqueness enforced where authority is (§9.3) |
| Output-path flexibility | arbitrary (unacceptable) | fixed | **none**: the PREPARED path is fixed |
| Operator error | high | low per ceremony; high release churn | low: one argument, validated |
| Reproducibility | poor | good | good: same release + same N ⇒ same public shape (fresh key material) |
| Future PROD suitability | no | burdensome | reasonable template (a PROD profile is its own review) |
| Operational burden | low | **high**: review, build, attest, install, and select before every rotation, and the gate forbids a selector switch inside a custody ceremony | low |

**Recommendation: C** (PENDING_OWNER_DECISION).

Varies per ceremony: **one** argument, the successor ordinal `N`, with
`N ≥ 2`. N is decimal, no leading zero, bounded to four digits, and parsed
strictly. From N the tool derives:

- `keyId = test-only.dev-synthetic.actor.b1b3e.<N>`. It keeps the profile's
  `test-only.` prefix and `.dev-synthetic.` label (PB-4), and is distinct
  from the initial `…b1b3d.1`;
- `ceremonyId = dev-synthetic.owner-actor.successor.<N>`.

Fixed at compile time or by profile, never arguments:

- environment `dev` / profile `DEV_SYNTHETIC`;
- `signingDomain OWNER_ACTOR`;
- `evidenceTypes [OWNER_MEMORY_OPERATION]`;
- algorithm Ed25519;
- `credentialName owner-actor-signing-key` (RR-11-D2);
- the PREPARED path;
- `--with-key=host`;
- the DEV machine ID and hostname;
- the publication schema.

There are no flags, and no domain, type, path, output, force, export, or seed
option.

Not an input: timestamps, random filenames, and anything read from the
registry. The keygen never reads or judges authority state.

## 6. RR-11-D2 — credential name vs slot

**Question.** Does the systemd runtime credential name stay fixed across
rotations?

| Criterion | A. fixed name `owner-actor-signing-key` forever; only the blob and its slot rotate | B. new runtime name per successor | C. fixed name, but the successor encrypted under a PREPARED-specific name and re-encrypted at cutover |
| --- | --- | --- | --- |
| Signer source | unchanged (PB-2) | `CREDENTIAL_NAME` changes each rotation, so it is a runtime release | unchanged |
| Unit file | unchanged: one directive, one path | the directive changes each rotation (unit edit inside the ceremony) | unchanged |
| Publication binding | `credentialName` constant; Prep A binding unchanged | Prep A contract must become per-key | the name recorded at keygen ≠ the name at load |
| Loaded-key verifier | unchanged | changed | changed |
| Release compatibility | one release (§5 C) | forces §5 B | one release |
| Cutover safety | a rename; no plaintext; `blobSha256` survives the rename | needs a unit reload plus a rename | **re-exposes plaintext** at cutover (forbidden by RR-11-D2's constraint) |
| Restart semantics | a restart loads whatever is in CURRENT, and the binding decides | ditto, plus a unit-generation mismatch risk | ditto |
| Accidental dual loading | impossible: the unit references one path (Prep A inventory + binding) | two directives possible during transition | as A |

**Recommendation: A** (PENDING_OWNER_DECISION). It is the option the gate
itself noted as meeting both RR-11-D2 constraints.

The consequence is that systemd name binding no longer distinguishes P from
S. It still distinguishes K-ACT from K-WIT. What distinguishes P from S is
the binding: B2 (CURRENT blob hash) = B3 (the head key's publication) and
B4 = the head key's fingerprint.

**Five identifiers, never synonyms:**

| Identifier | Meaning | Where it lives | Changes on rotation? | Authority? |
| --- | --- | --- | --- | --- |
| `credentialName` | the systemd runtime credential ID: the file name inside `$CREDENTIALS_DIRECTORY`, and the name embedded in the ciphertext by `--name` | profile constant; unit directive; publication `custodyEvidence` | **no** (A) | no |
| `keyId` | the registry identity of one key | the `AuthorityKeyRecordV1` and the publication's `publicVerificationMaterial` | **yes**: one per key, derived from N | the K-ROOT registry record is authority. The ID alone is not |
| `ceremonyId` | the identity of one successor ceremony | the ceremony record, owner register, and publication (RR-27) | yes | no (provenance) |
| logical slot role | CURRENT / PREPARED / RETIRED | inventory observation | the blob moves between roles | no |
| filesystem path | where the bytes of a role sit | fixed per role (RR-26) | no; the blob moves | no |

A blob is identified by `blobSha256`, never by name or path.

## 7. SW-2 — the successor-capable release

### 7.1 Scope of the release

The release contains:

- the unchanged runtime payload;
- the unchanged initial `actor` form;
- a new closed form, `successor <N>`;
- an installer stage that creates the PREPARED and RETIRED directories;
- the unit change `InaccessiblePaths += <custody root>`;
- the new release-set contract (RR-25).

`actor` stays exactly as PB-4 describes: initial custody only, refused if the
credstore is non-empty. The successor form never writes CURRENT.

### 7.2 `successor <N>` preconditions (all refuse closed, and none generate anything)

1. root; isolated interpreter; the DEV machine ID and hostname; no swap; the
   host key `root:root 0400`. These are all as PB-4.
2. N parses under §5 C.
3. The credstore is `root:root 0700`. It contains exactly the CURRENT slot
   name, and that entry is a regular `root:root 0600` file, not a symlink.
   Its SHA-256 is recorded (before).
4. The PREPARED directory exists, is `root:root 0700`, is not a symlink, and
   is **empty**. The RETIRED directory is empty.
5. The derived `keyId` is not the initial K-ACT ID. See §9.3 for why this is
   the only local uniqueness check.

### 7.3 One run

1. Generate one Ed25519 key in memory.
2. PKCS#8 DER → `systemd-creds encrypt --with-key=host
   --name=owner-actor-signing-key` over a pipe (PB-4).
3. Refuse ciphertext that contains the plaintext.
4. Write the blob `O_EXCL|O_NOFOLLOW` `0600` into the PREPARED directory, then
   fsync the file, then fsync the directory.
5. Re-hash CURRENT. It must equal the "before" hash, otherwise `FAILED
   CURRENT_CHANGED`.
6. Print one canonical publication on stdout.

There is no private material on stdout, stderr, logs, arguments, or the
environment (PB-4 rules). Zeroization is NOT_PROVEN.

**Preparation alone changes no authority.** The key is `KEY_UNKNOWN` until a
witnessed head names it.

### 7.4 Refusal matrix (source tests later)

The keygen refuses on each of:

- wrong argv or N;
- a PREPARED directory that is non-empty, missing, a symlink, or wrongly
  owned or moded;
- RETIRED non-empty;
- the credstore not exactly CURRENT;
- CURRENT not regular or wrongly moded;
- CURRENT changed during the run;
- not root, not DEV, swap active, or host key custody wrong;
- the ciphertext containing the plaintext;
- an existing target (`O_EXCL`).

## 8. Side-by-side slot paths (RR-26)

Exact paths are an open detail (gate §7.2).

**Recommendation** (PENDING_OWNER_DECISION): one root-only custody root on
the same filesystem as `/etc/credstore.encrypted`, so that renames are
atomic:

| Path | Role |
| --- | --- |
| `/etc/lilith-authority-custody/` | `root:root 0700` |
| `/etc/lilith-authority-custody/prepared/` | PREPARED |
| `/etc/lilith-authority-custody/retired/` | RETIRED |

The blob keeps a fixed name, `lilith-authority-dev.owner-actor.cred`, in
every role. The successor unit adds `InaccessiblePaths=/etc/lilith-authority-custody`.

**Not inside `/etc/credstore.encrypted`**, because:

- systemd searches credstore directories for credentials by name;
- the B1b-3d §13 `…next.cred` placement is superseded (GC-2);
- Prep A treats any second credstore name as `UNEXPECTED_CREDENTIAL_BLOB`.

## 9. Provenance: release, ceremony, key (RR-27)

### 9.1 What must be bound

The produced blob and its publication must be bound to four things:

- **the ceremony:** `ceremonyId`;
- **the intended key:** `keyId`;
- **the release:** the reviewed `RELEASE_SHA`;
- **the profile:** environment, domain, and type.

### 9.2 Where each binding lives

| Binding | Carried by | Verified by |
| --- | --- | --- |
| keyId, domain, type, environment, publicKey | publication `publicVerificationMaterial` (unchanged) | Prep A binding (B3 = B1) |
| blob | publication `custodyEvidence.blobSha256` (unchanged) | Prep A binding and inventory (B2 = B3) |
| ceremony | **proposed:** publication `custodyEvidence.ceremonyId` and `custodyEvidence.slotRole = PREPARED`, under a publication `schemaVersion` 2. **Source design change**, not implemented | ceremony record + owner register |
| release | **not in the publication.** The keygen cannot know its own reviewed git SHA without a self-reference. Instead, the non-authority `SuccessorCeremonyRecordV1` (owner transcript) binds the items listed below | the owner / verifier reproduces each hash |

`SuccessorCeremonyRecordV1` binds:

- `ceremonyId` and `keyId`;
- `releaseSha` (from installer `status`: the release directory and selector);
- `keygenCliSha256` (installer `CLI_BYTES` check, PB-7);
- `publicationSha256`, `preparedBlobSha256`, and `currentBlobSha256Before` /
  `After`.

The release hash is **provenance / readiness evidence, not authority**. A
correct blob from an unreviewed release is detected as a mismatch between
the installed CLI bytes and the reviewed release member. That is not
authority either, but it blocks the ceremony record.

No cryptographic authority contract (registry, authorization, witness) is
enlarged.

### 9.3 keyId uniqueness without timestamps or random names

1. Derivation: `keyId` is a fixed function of N.
2. **Authority-side uniqueness:** a registry cannot add a record whose
   `keyId` exists. It would be `SUCCESSION_RECORD_MUTATED` (the immutable
   public key differs) or a duplicate. So K-ROOT signing is the uniqueness
   boundary.
3. Owner side: the register records each issued `ceremonyId` and `keyId`
   (PR-3).
4. The keygen does not consult the registry: `REGISTRY_VIEW != authority`,
   and the keygen must not judge authority. A reused N yields a new key with
   an existing ID, which K-ROOT will refuse to publish. The blob is then
   `NOT_IN_HEAD` custody debt, destroyed as an abandoned successor.

## 10. SW-9 — current-key compromise recovery

### 10.1 Marking composition (RR-22)

**Question.** Is P's `COMPROMISED` marking a separate head advance first, or
does it live inside the `KEY_COMPROMISE` epoch-advance target?

| Criterion | A. separate in-epoch head advance first (`COMPROMISE_MARKING`, vN → vN+1, no current key in scope), then the epoch advance (vN+1 → vN+2 at E(n+1), S current) | B. combined: the epoch-advance target vN+1 at E(n+1) marks P `COMPROMISED` and names S current | C. other compositions |
| --- | --- | --- | --- |
| Mutation under the compromised state | the marking head needs **no signer involvement** (no ledger adoption, no successor) | marking waits for successor preparation, candidate signing, and C-4 adoption by the signer | — |
| Witness steps | 2 transition entries (plus ledger-only) | 1 | — |
| K-ROOT authorizations | 2 (RHAA + EAA) | 1 (EAA) | — |
| Evidence invalidation | **as soon as the marking head commits**: every P evidence → `KEY_COMPROMISED` (C-1); readiness → `NO_CURRENT_ISSUANCE_KEY` | only when the epoch advance commits | — |
| Crash points | more, but each is simple and independently classifiable | fewer, but marking is hostage to the whole recovery ladder | — |
| Source complexity | existing planners unchanged; the head planner already allows a target with no current key (PB-10) | existing planners unchanged | a combined in-epoch compromise + successor is forbidden (RR-16) |
| Recovery clarity | two single-purpose steps: *reject P*, then *re-anchor state and name S* | one step with two purposes | — |
| Hold | blocks issuance throughout, and after the marking the registry itself also blocks it | blocks issuance throughout; the registry does not until the advance | — |

**Recommendation: A** (PENDING_OWNER_DECISION). It minimizes the time during
which P's evidence still verifies. It needs nothing from the suspect state
domain. Both of its steps use existing contracts unchanged. Current source
supports both A and B (gate §4.4), so B stays a valid alternative if the
owner prefers fewer steps.

### 10.2 The accepted path, in order (with A)

1. **Containment.** Write the hold (`kind KEY_COMPROMISE_RECOVERY`). Stop the
   signer. Classify under RR-6. S9, S10, and S11 mean STOP; SW-9 applies only
   to S3 / S12.
2. **Marking (authority).** K-ROOT signs vN+1: P `revokedAt`, `COMPROMISED`,
   `compromisedSince`, and no current Actor key. It also signs an RHAA vN → vN+1
   with reason `COMPROMISE_MARKING`. The witness executes it: the **first
   authority PONR**. P's evidence is rejected from here.
3. **Successor preparation (custody).** `successor <N>` → PREPARED (§7). P
   stays in CURRENT, not running (§10.4).
4. **Epoch authority.** K-ROOT signs vN+2 at E(n+1) with S current. P stays
   `COMPROMISED`, and every other E(n) key is non-current. It also signs an
   `EpochAdvanceAuthorizationV1` (`KEY_COMPROMISE`) bound to the current
   witness.
5. **C-4.** Start the signer under the hold. It journals `ADVANCE_EPOCH` (no
   signing). The witness executes: the **second authority PONR**. Quarantine
   follows, and the witness records the ledger advance. Stop the signer.
6. **Cutover.** P CURRENT → RETIRED, then S PREPARED → CURRENT (as 8a/8b).
7. **Activation and verification.** Start under the hold. `HEALTH` = S. Prep A
   readiness at vN+2 passes, plus the compromise-epoch rule (§10.3). Release
   the hold: `S_CURRENT`.
8. **P destruction** (§4.1 rule; class `COMPROMISED`, RR-7 action "yes, from
   active custody").

### 10.3 Compromise-epoch rule (DERIVED from RR-6; SW-9 source requirement)

Readiness must refuse any successor reached **in-epoch** after a
current-key compromise.

**The rule.** Suppose the witnessed chain contains a head change where a key
K that was the single current key in scope at the predecessor head becomes
`COMPROMISED`. Then:

1. no key may be issuance-ready at any head whose `recoveryEpoch` equals the
   epoch in which K was current;
2. the current head must lie at a strictly newer epoch;
3. that epoch must have been reached by an `EpochAdvanceAuthorizationV1` with
   reason `KEY_COMPROMISE`, whose retained copy re-verifies (Prep A history).

Under B, the marking head is itself the epoch advance, so the rule holds by
construction.

Without this rule, K-ROOT could (by owner error) sign an in-epoch head
advance adding S after the marking. The witness planner would execute it,
because it does not know policy, and Prep A readiness would pass. The rule
closes that gap.

It also implements the gate's SW-9 test: "current-key compromise without an
epoch advance never reaches `S_CURRENT`". The existing `evaluate_rotation`
already refuses such a path (`PREDECESSOR_NOT_SINGLE_CURRENT` /
`CANDIDATE_PREDECESSOR_NOT_SUPERSEDED`). Readiness must refuse it
independently.

It applies only when K was current at the marking. A non-current key's
compromise is in-epoch marking only (RR-6 rule 4).

### 10.4 Containment vs C-4 (RR-28)

C-4 needs the running signer to journal `ADVANCE_EPOCH` and the quarantine
(PB-13). The signer refuses to start without a credential (PB-6). So the
compromised P cannot be vacated from CURRENT at containment unless the runtime
gains a credential-less recovery mode, which is a runtime change.

**Recommendation** (PENDING_OWNER_DECISION): keep P in CURRENT, with the
signer stopped except during step 5. Keeping P loaded in the signer adds no
exposure: in S3/S12 the private key is already outside. Issuance is
impossible for several reasons:

- the hold;
- after the marking head, `NO_CURRENT_ISSUANCE_KEY`;
- the binding (B1 has no current key);
- P's evidence is `KEY_COMPROMISED`.

If the owner judges the signer process itself untrustworthy, that is S9, which
means STOP, not SW-9.

The alternative, a credential-less signer mode for ledger-only operations, is
a runtime and release change and is not recommended.

### 10.5 `AuthorityKeyTransitionV1` (RR-23)

| Option | Assessment |
| --- | --- |
| **A. No new contract** | the authority is fully represented by existing objects: the K-ROOT registry (who is current, P's lifecycle), the RHAA / EAA (permission for one exact transition), the witness (execution and freshness), and the Prep A readiness result (verification) |
| **B. Non-authority record only** | an evidence summary emitted by the verifier after `S_CURRENT`. It is what design §7.7 already defines (story 4) |
| C. Authority-bearing | **rejected.** No property is missing. It would be a second authority story, able to disagree with the registry |

The non-authority status is ALREADY_DETERMINED (PB-12). Only whether to
implement it is open.

**Recommendation: B, minimal.** Implement the §7.7 record as a verifier
**output** that grants nothing. Its fields: `authorityGranted: false`;
`kind ROTATION | KEY_COMPROMISE_RECOVERY`; predecessor and successor keyIds;
from and to heads; epoch(s); witness digests; the `ceremonyId`; the
readiness result digest; and `predecessorMaterial`. It is consumed by nothing
that decides authority.

### 10.6 `CeremonyHoldV1` (RR-24)

Design §9.1 proposed these fields: `{kind, reason, environment,
observedWitnessDigest, observedRegistryVersion, createdAt}`. Every field is
unauthenticated, and the object is non-authority (ALREADY_DETERMINED).

**Recommendation** (PENDING_OWNER_DECISION): **A. a versioned, pure,
non-authority data contract**, with the fields trimmed to those that have a
purpose:

| Field | Purpose |
| --- | --- |
| `schemaVersion`, `holdType` | parse strictly |
| `environment` | refuse a hold from another environment |
| `ceremonyId` | a ceremony step refuses unless the hold names its own ceremony |
| `kind` | `ROTATION`, or `KEY_COMPROMISE_RECOVERY` (selects the ladder) |
| `reason` | closed set, informational |
| `expectedPredecessorKeyId` | refuse a ceremony run against another P |
| `expectedSuccessorKeyId` | null until preparation, then fixed |
| `observedWitnessDigest` | the head at hold time; a ceremony step refuses if the chain does not descend from it |

**Dropped:** `createdAt` (timestamps are not authority, and it has no
consumer) and `observedRegistryVersion` (it is implied by the witness
digest).

Semantics:

```text
hold present (valid or unparseable)     -> issuance NOT_READY (fail safe)
hold absent where a ceremony step needs it -> that step refuses
hold unparseable                          -> treated as present; ceremony steps refuse
hold release != authority
hold release != S_CURRENT                  (S_CURRENT additionally needs every readiness check)
```

Prep A's boolean `hold_present` stays the readiness input. `CeremonyHoldV1`
adds the ceremony-step preconditions only.

## 11. SW-9 crash matrix

The head is the witnessed head. "Issue?" means may the signer issue. Rows 1–9
assume composition A.

| # | State | Head (authority) | Loadable (CURRENT) | Issue? | Rollback to P? | Recovery | Destroy P? |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | hold engaged, nothing prepared | vN (P current) | P | no (hold) | P was never moved. But P is compromised, so it never resumes | owner: continue to marking | no |
| 2 | successor prepared, marking not yet done | vN | P | no | as 1 | owner: marking, or destroy S (`NOT_IN_HEAD`) and restart | no |
| 3 | vN+1 marking signed, RHAA absent | vN | P | no | as 1 | owner: sign the RHAA; vN+1 stays staged | no |
| 4 | marking committed; EAA exists, witness not advanced | vN+1 (no current key; P `COMPROMISED`) | P | no (no current key) | **no**: P is compromised at the head | owner: C-4 step 5. If the adoption is already journalled: `LEDGER_EPOCH_AHEAD_OF_WITNESS` → the witness executes **the same** EAA | no |
| 5 | epoch advance committed; custody still P | vN+2 (E(n+1), S current) | P | no (binding: B1 = S) | no | forward: quarantine, witness, cutover | no |
| 6 | P → RETIRED, S not installed | vN+2 | — (the unit cannot start) | no | **no** | forward: install S (automatic within the owner's ceremony; no authority step) | no |
| 7 | S installed, signer not started | vN+2 | S | no (no `HEALTH`, hold) | no | start under the hold | no |
| 8 | `HEALTH` reports the wrong key | vN+2 | wrong blob | no (binding) | no | stop; diagnose the inventory; restore **S** from PREPARED / RETIRED knowledge. P never | no |
| 9 | `HEALTH` = S, binding fails | vN+2 | S? | no | no | the hold stays; diagnose B2 / B3 (F20) | no |
| 10 | `S_CURRENT`, P retained | vN+2 | S | yes (per-operation readiness) | no | destroy P (§4.1) | **yes, permitted** |
| 11 | crash during destruction | vN+2 | S | yes | no | re-run destruction idempotently. A file that reappears after a crash (unlink not yet fsynced) has the same hash and is deleted again. Inventory `CUTOVER_INSTALLED` stays a readiness phase | yes (continue) |
| 12 | old snapshot restored after `S_CURRENT` | as restored | as restored | if witness, registry, and ledger are all restored: **undetected** (whole-host rollback). If only the credential is restored: the binding fails (`STALE_CREDENTIAL_PRESENT`) | no | if detected: STOP, classify the snapshot (RR-17). A snapshot with both halves outside the accepted boundary → RR-20b | n/a |

Under composition B, rows 3–4 merge into the single epoch advance. Until it
commits, the head is still vN with P current, and only the hold and a stopped
signer contain.

## 12. Dual-current / dual-load prevention

The four senses:

| Sense | Established by |
| --- | --- |
| authority-current | the single current key at the witnessed K-ROOT head |
| loaded | whatever blob sits in CURRENT, as delivered by systemd |
| issuance-ready | every Prep A check passes, including the binding |
| `S_CURRENT` | issuance-ready plus the hold released, independently verified |

**Claim.** At most one key is issuance-ready, and it is the authority-current
one.

1. Issuance-readiness requires the binding. The binding requires that the
   **loaded** blob's hash (B2) and the signer's fingerprint (B4) equal the
   publication of the **authority-current** key (B1 = B3). So a loaded key is
   ready only if it is the authority-current key.
2. The witnessed head has at most one authority-current key in scope
   (single-current rule, enforced at genesis, succession, and readiness).
3. Exactly one blob is loadable: one unit directive (Prep A B5) and one
   CURRENT blob (Prep A inventory; `DUPLICATE_CREDENTIAL_BLOB`,
   `MULTIPLE_PREPARED_CANDIDATES`).

Hence the combination "authorized S + loadable P + both current" is
impossible:

- **P loaded after the witness advanced:** B1 = S ≠ P → `BLOB_HASH_MISMATCH`
  / `HEALTH_FINGERPRINT_MISMATCH` → `NOT_READY`.
- **S loaded before the witness advanced:** B1 = P (or no current key after
  a marking) → `NOT_READY`. S is also `KEY_UNKNOWN` to verifiers.
- **Both reachable:** the unit and inventory refuse.

```text
cryptographic ability to sign != authorization to issue
```

A loaded P can still sign. Verifiers then reject its output:

- `KEY_REVOKED` at or after `t_cut`;
- `KEY_COMPROMISED` always, in SW-9.

The acceptance chain also refuses it: `RESERVE` needs an `ISSUE` record,
which readiness blocks.

The one residual is a rotation only. A **backdated** P signature inside
`[notBefore, t_cut)` still verifies historically. That is exactly why a
retained P is `KNOWN_CUSTODY_DEBT` (RR-7) and must be destroyed after
`S_CURRENT`, and why a disclosed P escalates to `COMPROMISED` (gate SF-10).

## 13. Destruction evidence and zeroization

What Source Prep B may honestly prove for P's blob in RETIRED:

1. **Before:** the path existed, as a regular `root:root 0600` file, and its
   SHA-256 equalled P's publication `blobSha256`.
2. The unlink succeeded.
3. The RETIRED directory was fsynced.
4. **After:** `lstat` is absent, and the inventory is `STEADY` with
   CURRENT(S).
5. A `PredecessorDestructionRecordV1` (non-authority) holds these facts plus
   the `S_CURRENT` readiness result it depended on. It is reported as
   `predecessorMaterialDestroyedFromActiveCustody: true`.

**Not proven:**

- media zeroization;
- journal, filesystem, or SSD remanence;
- page cache;
- process memory of earlier signer runs;
- copies in snapshots or backups.

```text
logical destruction != media zeroization
destruction         != revocation
```

The host key `credential.secret` still decrypts any copy of P's blob that
survives elsewhere. A snapshot holding both halves stays classified under
RR-17 and RR-20b. Destruction does not change P's authority state; K-ROOT
already did (`SUPERSEDED` or `COMPROMISED`).

## 14. Hidden assumption

**"What assumption could make the custody cutover look correct while the
authority state is wrong?"**

The assumption is that **custody state and authority state move together**:
that "the blob in CURRENT" and "the key the head names" are the same thing
because a ceremony moved them in the same session. They are joined only by
the binding at verification time.

| Case | Why it can look right | Why it fails closed |
| --- | --- | --- |
| P still loadable after the witness advanced | the service starts and signs | binding B1 = S ≠ P |
| S loaded before the witness advanced | `HEALTH` shows the new fingerprint | B1 = P (or none); S is `KEY_UNKNOWN` |
| two preparation slots | "a spare" | the inventory has one PREPARED role, and a second candidate is refused |
| the unit references both | "fallback" | Prep A B5 requires exactly one reference |
| stale publication + new blob | the publication verifies | B2 ≠ B3 `blobSha256` |
| correct blob from an unreviewed release | the key is fine | the ceremony record's CLI hash ≠ the reviewed release member (provenance; blocks the ceremony record) |
| the CURRENT path changes while the key identity does not | same keyId | B5 path ≠ the fixed CURRENT path; the inventory refuses other credstore names |
| deletion mistaken for revocation | "P is gone" | revocation exists only as a K-ROOT registry state at a witnessed head |
| in-epoch successor after a current-key compromise | K-ROOT signed it; the witness executed it | the compromise-epoch rule (§10.3) |
| re-encryption at cutover | "just rename the credential" | forbidden (plaintext); RR-11-D2 A keeps a rename |

## 15. Future Source Prep B implementation boundary

Minimized to what the accepted semantics require.

**`services/authority-dev` (a reviewed successor-capable release; a release
change):**

1. keygen `successor <N>` (§7). The `actor` form is unchanged.
2. Installer: a stage that creates the custody root, `prepared/`, and
   `retired/` (`root:root 0700`). A status contract for them. The new
   release-set contract (RR-25). CLI byte checks unchanged.
3. Unit: `InaccessiblePaths += /etc/lilith-authority-custody` (RR-26). No
   credential directive change (RR-11-D2 A).
4. `release_file_set.py`: file-set and hash updates only.

**`services/owner-memory-control` (pure verifiers; TEST-proven):**

5. A custody transition verifier: the allowed inventory-phase sequence
   (§4.1) and the destruction-ordering rule (SW-1).
6. The compromise-epoch rule in readiness (§10.3), and
   `evaluate_compromise_recovery` for the §10.2 ladder, including an explicit
   check that the marking precedes or accompanies the advance.
7. A `CeremonyHoldV1` parser plus the ceremony-step preconditions (§10.6).
8. Non-authority outputs: `AuthorityKeyTransitionV1`,
   `PredecessorDestructionRecordV1`, and `SuccessorCeremonyRecordV1`
   verification (§9). The publication v2 parser if RR-27 is accepted.
9. Tests: every §4.1 row, every §11 row, the §7.4 refusal matrix, and every
   §14 case.

**Explicitly not needed:**

- a new authority contract;
- a witness change;
- a registry schema change;
- a new inventory phase (the compromise path reuses the rotation phases,
  given RR-28's recommendation);
- a DEV_SYNTHETIC witness profile (PR-1);
- a credential-less signer mode.

**Outside Source Prep B:**

- PR-1: B1b-3d L3a–L4 designed for V2, installed, and accepted;
- PR-2: the snapshot inventory;
- PR-3: the owner's real off-host register and material;
- any actual DEV_SYNTHETIC rotation or compromise rehearsal;
- PROD authority;
- Privacy (B1b-3f);
- Stage III;
- First Memory.

## 16. Nonclaims

This record does not claim, create, or authorize any of the following:

- source;
- a release;
- a key;
- a rotation;
- a revocation;
- an epoch advance;
- a live step;
- zeroization;
- whole-host rollback protection;
- real-owner-grade custody;
- PROD authority;
- that any recommendation here is accepted.

## 17. Destruction and custody evidence summary

| Evidence | Proves | Does not prove |
| --- | --- | --- |
| inventory per phase (Prep A) | which roles hold which blob hashes | authority |
| ceremony record (RR-27) | which reviewed release and CLI produced which publication and blob | authority; key secrecy |
| binding (Prep A) | the loaded blob = the head key's blob, and the signer reports that key | the signer's memory; authority |
| destruction record | a logical unlink plus a directory fsync of a known blob | media erasure; the absence of copies |

## 18. Owner decision table

Every row below is **PENDING_OWNER_DECISION** unless stated.

| # | Question | Options | Security consequence | Operational consequence | Recommendation |
| --- | --- | --- | --- | --- | --- |
| RR-11-D1 | one successor-capable release for many rotations, or one per rotation? | A free inputs / B per-rotation release / C closed reusable form `successor <N>` | A is a generic keygen (reject); B and C are closed | B needs review + install + selector switch per rotation; C needs one reviewed install | **C** |
| RR-11-D2 | fixed runtime credential name? | A fixed `owner-actor-signing-key` / B per-successor name / C re-encrypt at cutover | A: P vs S distinguished by the binding; C re-exposes plaintext (reject) | A: no unit or signer change; B: unit + release per rotation | **A** |
| RR-22 | SW-9 marking: a separate head advance, or inside the epoch target? | A separate `COMPROMISE_MARKING` first / B combined | A rejects P's evidence earliest, without the suspect domain | A: 2 authorizations, 2 witness steps; B: 1 | **A** |
| RR-23 | is `AuthorityKeyTransitionV1` needed? | A none / B non-authority record / C authority contract | C creates a second authority story (reject) | B: one verifier output | **B** (its non-authority status is ALREADY_DETERMINED, design §7.7) |
| RR-24 | `CeremonyHoldV1` representation? | A versioned pure non-authority contract / B untyped local file / C none | A lets ceremony steps bind to one ceremony; every option fails safe | A: small parser | **A**, trimmed (§10.6) (non-authority status ALREADY_DETERMINED, design §9.1) |
| RR-25 | the successor release-set contract replacing PB-7 `RELEASE_SET` | exactly {successor release}; or {successor release + retained 9ac7de2 as inert history}; selector → successor | extra entries are inert only if the selector and CLI bytes pin the reviewed one | retention aids forensics | {successor} + at most the previous accepted release, inert; selector and CLI pinned to the successor |
| RR-26 | exact PREPARED / RETIRED paths | inside the credstore (reject, GC-2) / a separate root-only custody root on the same filesystem | outside the credstore, systemd name search and the Prep A inventory stay unambiguous | one installer stage + one unit line | `/etc/lilith-authority-custody/{prepared,retired}` |
| RR-27 | where ceremony and release provenance live | publication v2 (`ceremonyId`, `slotRole`) + a separate ceremony record for the release / everything in the publication / everything in the record | the release hash is never authority in either | v2 needs a parser update | publication v2 for `ceremonyId` / `slotRole`; release SHA in `SuccessorCeremonyRecordV1` |
| RR-28 | SW-9 containment: vacate P at containment, or keep it in CURRENT until the post-witness cutover? | vacate early (needs a credential-less signer mode) / keep P, signer stopped except for C-4 | no added exposure: P is already outside; issuance is impossible | early vacate is a runtime change | **keep P in CURRENT**, signer stopped except C-4 step 5 |
| RR-29 | how long may P stay RETIRED after `S_CURRENT`? | immediately in the same ceremony (L3e-12) / an owner-chosen bounded window | a longer window = longer custody debt (the backdating residual, §12) | immediate is simplest | **immediately after the `S_CURRENT` POST, in the same ceremony** |

**ALREADY_DETERMINED (not reopened):**

- no restore of P after the authority PONR (§4.2, gate §11);
- P not destroyed before `S_CURRENT` (RR-11);
- `AuthorityKeyTransitionV1` and `CeremonyHoldV1` are non-authority;
- the compromise-epoch rule (§10.3), which is DERIVED from RR-6;
- no ABANDONED role.

## Explicitly not done

- No DEV or PROD contact. No gcloud, SSH, IAP, sudo, systemctl, or
  systemd-creds.
- No credential generated. No successor key. `/etc/credstore.encrypted` and
  `/var/lib/lilith-authority-dev` untouched.
- No key rotated, revoked, or deleted. No registry, witness, epoch, authority
  ledger, broker ledger, or L04 touched.
- No IAM, WIF, or sudoers change. No Stage III retry. No First Memory.
- No Python source, unit, workflow, or runtime configuration changed.
- No PR was opened.
