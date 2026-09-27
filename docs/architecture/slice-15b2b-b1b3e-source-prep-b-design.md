# Slice 15B2b-B1b-3e — Source Prep B Design: Successor Custody and Compromise Recovery

Status:

- **DESIGN CLOSURE** (SW-1, SW-2, SW-9; RR-11-D1, RR-11-D2)
- **SOURCE NOT IMPLEMENTED**
- **LIVE REHEARSAL NOT AUTHORIZED**
- **OWNER DECISIONS ACCEPTED:** RR-11-D1, RR-11-D2, RR-22 … RR-30, and the
  derived compromise-epoch readiness rule (§18). First draft `8e3643c`;
  owner-decision closure `7411a53`; this revision closes RR-30
- **NO PENDING OWNER DECISION** remains for Source Prep B. What is left is
  SOURCE DETAIL only (§18)
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
| **OWNER-ACCEPTED** | accepted in the owner-decision closure pass (§18). Binding for Source Prep B source; exact schemas stay source work |
| **PENDING_OWNER_DECISION** | a new choice. A recommendation is given; nothing is accepted. None remains in this record |
| **SOURCE DETAIL** | an implementation choice that does not alter authority, state ownership, the custody boundary, or failure semantics. It is fixed and reviewed in the Source Prep B source slice |

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

Pinned by the owner-decision closure pass:

```text
owner signing error                        != valid readiness
private key loaded                         != issuance authority
COMPROMISED key loaded for recovery        != valid evidence issuer
hold                                       != authority
hold release                               != authority
hold release                               != S_CURRENT
missing hold                               != released
destruction failure                        != authority rollback
release rollback                           != authority rollback
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
| **PREPARED** | at most one successor blob | the successor keygen only | root only | **no**: referenced by no unit | **no**: must be `InaccessiblePaths` in the successor release (§8) | no | no. The key is `KEY_UNKNOWN` until a head names it | yes | yes, while `NOT_IN_HEAD` (abandon); otherwise it is emptied by the cutover install | `root:root 0600` regular file in a `root:root 0700` directory, on the credstore's filesystem |
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
  verifier reproduced `S_CURRENT`: every readiness check `PASS` at head vN+1,
  with the binding naming S. **OWNER-ACCEPTED (RR-29):** destruction is then
  the **mandatory next custody-cleanup step**. It is not part of authority
  establishment.
- **When logical destruction fails after `S_CURRENT`.** Do not roll back the
  authority head, and do not restore P to CURRENT. S stays the
  authority-current key. Fail closed by engaging a local availability hold
  (`CeremonyHoldV1` state `HELD`), which stops issuance. Report
  `KNOWN_CUSTODY_DEBT`. Completing the destruction needs owner intervention or
  a retry. `destruction failure != authority rollback`.
- **Evidence and zeroization.** See §13.

```text
retention   != authority      (a retained P is custody debt, not a fallback)
destruction != revocation     (P was made non-current by K-ROOT at L3e-6, not by deletion)
revocation  != destruction    (P's K-ROOT SUPERSEDED marking deletes nothing)
S_CURRENT independently verified -> then, and only then, predecessor destruction
```

**SW-1 source requirement.** A pure destruction-ordering verifier refuses
destruction unless it is given all of:

- a readiness result that is `READY` at the same head, with a binding naming
  the successor;
- an inventory in `CUTOVER_INSTALLED` whose RETIRED hash equals P's
  publication.

The destruction evidence of §13 decides `DESTROYED`. Anything short of it
decides `DESTRUCTION_INCOMPLETE`, which requires the availability hold. The rotation
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

**OWNER-ACCEPTED: C.** One reusable, reviewed, **closed** successor-capable
release. Its only successor form is `successor <N>`.

Varies per ceremony: **one** argument, the bounded positive successor
ordinal `N`, with `N ≥ 2`. N is decimal, no leading zero, bounded to four digits, and parsed
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

**Ordinals are burned (OWNER-ACCEPTED).** Once an ordinal has produced
credential material or a publication, that ordinal, its `keyId`, and its
`ceremonyId` are permanently burned. They must never be reused, even if the
ceremony is later abandoned. Enforcement is layered, and none of it is
authority:

- **Registry history** stays the authority boundary for key identity: K-ROOT
  cannot publish a second record under an existing `keyId` (§9.3).
- The **owner ceremony register** (PR-3) records every burned ordinal. It
  prevents reuse before any registry publication.
- The Source Prep B **ceremony-record verifier** refuses a second
  `SuccessorCeremonyRecordV1` for an ordinal, `keyId`, or `ceremonyId` it has
  already seen.

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

**OWNER-ACCEPTED: A.** The runtime systemd credential name stays
`owner-actor-signing-key` across all rotations. No successor gets a new
runtime credential ID. The signer keeps requesting exactly one runtime
credential, `owner-actor-signing-key`. Only the CURRENT encrypted source slot
may back it.

The consequence is that systemd name binding no longer distinguishes P from
S. It still distinguishes K-ACT from K-WIT. What distinguishes P from S is
the binding: B2 (CURRENT blob hash) = B3 (the head key's publication) and
B4 = the head key's fingerprint.

**Five identifiers, never synonyms:**

| Identifier | Meaning | Where it lives | Changes on rotation? | Authority? |
| --- | --- | --- | --- | --- |
| `credentialName` | the systemd runtime credential ID: the file name inside `$CREDENTIALS_DIRECTORY`, and the name embedded in the ciphertext by `--name` | profile constant; unit directive; publication `custodyEvidence` | **no** (A) | no |
| `keyId` | the registry identity of one key | the `AuthorityKeyRecordV1` and the publication's `publicVerificationMaterial` | **yes**: one per key, derived from N | the K-ROOT registry record is authority. The ID alone is not |
| `ceremonyId` | the identity of one successor ceremony | `SuccessorCeremonyRecordV1` and the owner ceremony register (RR-27); **not** the key publication | yes; burned once used | no (provenance) |
| logical slot role | CURRENT / PREPARED / RETIRED | inventory observation | the blob moves between roles | no |
| filesystem path | where the bytes of a role sit | fixed per role (RR-26) | no; the blob moves | no |

A blob is identified by `blobSha256`, never by name or path. These five
identifiers are not aliases (OWNER-ACCEPTED).

## 7. SW-2 — the successor-capable release

### 7.1 Scope of the release

The release contains:

- the unchanged runtime payload;
- the unchanged initial `actor` form;
- a new closed form, `successor <N>`;
- an installer stage that creates the PREPARED and RETIRED directories;
- the unit change `InaccessiblePaths += <custody root>`;
- the new release-set contract (RR-25): this release becomes the **single**
  installed authority-dev release.

`actor` stays exactly as PB-4 describes: initial custody only, refused if the
credstore is non-empty. The successor form never writes CURRENT.

**Release set (OWNER-ACCEPTED, RR-25).**

- Only **one** executable authority-dev release is installed on the host. No
  second executable release is retained merely for operational rollback.
- The prior reviewed release (`9ac7de2`) is preserved by immutable
  repository history, by its release SHA and provenance record, and by the
  existing reviewed-artifact process.
- Before any authority point of no return, reinstalling a prior reviewed
  release may be a separately reviewed operational recovery.
- After an authority point of no return, a release rollback never implies an
  authority rollback. `release rollback != authority rollback`.
- The installer's `RELEASE_SET` check therefore keeps "exactly one entry",
  now naming the successor-capable release.

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
   the only local check of identity. Ordinal burning is enforced by the owner
   ceremony register and the ceremony-record verifier (§5), not by keygen
   state.
6. PREPARED, RETIRED, and the credstore report the same `st_dev`. This proves
   that every later cutover rename is a same-filesystem rename (RR-26).

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
- PREPARED, RETIRED, and the credstore on different filesystems (`st_dev`);
- CURRENT changed during the run;
- not root, not DEV, swap active, or host key custody wrong;
- the ciphertext containing the plaintext;
- an existing target (`O_EXCL`).

## 8. Side-by-side slot paths (RR-26, OWNER-ACCEPTED)

| Role | Path |
| --- | --- |
| CURRENT | `/etc/credstore.encrypted/lilith-authority-dev.owner-actor.cred` (unchanged, PB-3) |
| PREPARED | `/etc/lilith-authority-custody/prepared/lilith-authority-dev.owner-actor.cred` |
| RETIRED | `/etc/lilith-authority-custody/retired/lilith-authority-dev.owner-actor.cred` |

Requirements:

- CURRENT stays the **only** `LoadCredentialEncrypted=` source.
- `/etc/lilith-authority-custody`, `prepared/`, and `retired/` are all
  `root:root 0700` directories.
- Blobs are `root:root` regular `0600` files.
- No symlinks anywhere on these paths, and no extra blobs.
- Same filesystem (`st_dev`) must be proven before any rename-based cutover.
  The keygen proves it at preparation (§7.2); the cutover proves it again
  before each rename.
- PREPARED and RETIRED are inaccessible to the authority service: the unit
  adds `InaccessiblePaths=/etc/lilith-authority-custody`.
- Root ceremony tooling alone performs the custody moves.

**Not inside `/etc/credstore.encrypted`**, because:

- systemd searches credstore directories for credentials by name;
- the B1b-3d §13 `…next.cred` placement is superseded (GC-2);
- Prep A treats any second credstore name as `UNEXPECTED_CREDENTIAL_BLOB`.

Filesystem role and path never determine authority.

## 9. Provenance: release, ceremony, key (RR-27)

### 9.1 What must be bound

The produced blob and its publication must be bound to four things:

- **the ceremony:** `ceremonyId`;
- **the intended key:** `keyId`;
- **the release:** the reviewed `RELEASE_SHA`;
- **the profile:** environment, domain, and type.

### 9.2 Where each binding lives (RR-27, OWNER-ACCEPTED with minimality)

The existing key publication contract stays **unchanged**. No
`KeyPublicationV2` is created merely to carry ceremony or release
provenance, unless implementation proves the existing publication cannot
remain stable.

| Binding | Carried by | Verified by |
| --- | --- | --- |
| keyId, domain, type, environment, publicKey | publication `publicVerificationMaterial` (unchanged) | Prep A binding (B3 = B1) |
| blob, credential name | publication `custodyEvidence.blobSha256`, `credentialName` (unchanged) | Prep A binding and inventory (B2 = B3) |
| ceremony, ordinal, release | a separate non-authority `SuccessorCeremonyRecordV1` | the ceremony-record verifier + the owner ceremony register |

`SuccessorCeremonyRecordV1` binds only the successor-ceremony provenance:

| Field | Meaning |
| --- | --- |
| `ceremonyId` | derived from the ordinal |
| `successorOrdinal` | N |
| `keyId` | derived from the ordinal; must equal the publication's |
| `publicationDigest` | SHA-256 of the exact canonical publication bytes |
| `credentialBlobSha256` | must equal the publication's `blobSha256` |
| `reviewedReleaseSha` | the reviewed release that produced it |
| `createdForRole = PREPARED` | **historical creation provenance only.** It records where the keygen wrote the blob. It is not the credential's current dynamic slot role, which only the inventory observes |

- It does not duplicate other publication fields.
- `reviewedReleaseSha` is meaningful only together with the existing
  installer evidence: the release directory, the selector, and the
  `CLI_BYTES` check (PB-7).
- The record is **not** registry authority, **not** a K-ROOT authorization,
  **not** witness freshness, and it **cannot make a key current**.
- That CURRENT was not overwritten during PREPARE is proven by the keygen's
  own before/after re-hash (§7.3) and the before/after inventory. The record
  does not prove it.

A correct blob from an unreviewed release shows up as a mismatch between the
installed CLI bytes and the reviewed release member. That blocks the
ceremony record. It is not authority either way.

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
   and the keygen must not judge authority.
5. Burned ordinals (§5) are refused by the owner ceremony register and the
   ceremony-record verifier. If a burned ordinal is misused anyway, it yields
   a new key under an existing ID. K-ROOT will refuse to publish it, and the
   blob is `NOT_IN_HEAD` custody debt, destroyed as an abandoned successor.

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

**OWNER-ACCEPTED: A.** Current-key compromise uses two authority
transitions:

1. **A separate in-epoch `COMPROMISE_MARKING` registry-head advance.** It
   marks P `COMPROMISED` as early as possible, so all of P's evidence stays
   `KEY_COMPROMISED` under existing semantics. It creates no successor. The
   compromise-epoch rule (§10.3) stops any other same-epoch successor from
   becoming ready.
2. **A `KEY_COMPROMISE` RecoveryEpoch advance** into the recovery-successor
   path.

The marking is **not** collapsed into the target epoch registry. Option B is
not used.

### 10.2 The accepted SW-9 order (OWNER-ACCEPTED)

```text
engage hold (CeremonyHoldV1 HELD, transitionKind KEY_COMPROMISE_RECOVERY)
 -> stop normal signer activity
 -> K-ROOT registry vN+1 marks P COMPROMISED (no current Actor key)
 -> RegistryHeadAdvanceAuthorizationV1 vN -> vN+1, reason COMPROMISE_MARKING
 -> witness commits the COMPROMISE_MARKING head          [first authority PONR]
 -> compromise-epoch readiness rule becomes active       (derived, §10.3)
 -> prepare the recovery successor: successor <N> -> PREPARED (§7)
 -> K-ROOT registry vN+2 at E(n+1) (S current; P stays COMPROMISED)
    + EpochAdvanceAuthorizationV1, reason KEY_COMPROMISE
 -> C-4: authority-ledger ADVANCE_EPOCH through the narrow recovery gate (§10.4)
 -> witness commits the authorized new epoch/registry head [second authority PONR]
 -> C-4 continues unchanged: quarantine, then the witness records the ledger advance
 -> serve and verify the new registry
 -> forward-only credential cutover: P CURRENT -> RETIRED, then S PREPARED -> CURRENT
 -> S_ACTIVATED
 -> independent S_CURRENT (all readiness checks, incl. §10.3 and a RELEASED hold)
 -> predecessor logical destruction (mandatory, RR-29)
 -> destruction evidence (§13)
```

The B1b-3c / C-4 quarantine and witness ordering is preserved exactly
wherever extra witness updates are needed. C-4 is not rewritten.

Classification comes first, under RR-6: S9, S10, and S11 mean STOP, and this
path applies only to S3 and S12. P is destroyed from active custody as class
`COMPROMISED` (RR-7).

### 10.3 Compromise-epoch readiness rule (DERIVED from RR-6; OWNER-ACCEPTED; required Source Prep B source)

**Condition.** The rule applies when the **verified** witness, registry, and
authorization history (Prep A chain, registry history, and authorization
re-verification) proves all three of:

1. a key K was the current `OWNER_ACTOR` issuance key at a witnessed head
   in epoch E;
2. a subsequent `COMPROMISE_MARKING` head transition, whose
   `RegistryHeadAdvanceAuthorizationV1` re-verifies, marks K `COMPROMISED`;
3. `RecoveryEpoch` has not yet advanced beyond E through a re-verified
   `EpochAdvanceAuthorizationV1` with reason `KEY_COMPROMISE`.

**Effect.** No successor in epoch E may reach issuance readiness or
`S_CURRENT`. Readiness fails with `COMPROMISE_EPOCH_ADVANCE_REQUIRED`. This
holds even if K-ROOT mistakenly signs another same-epoch registry that names
a new current successor, and the witness executes it: the planner does not
know policy, and Prep A readiness alone would pass.

`owner signing error != valid readiness`.

**Clearing.** The condition clears only when the witnessed chain contains the
accepted `KEY_COMPROMISE` epoch advance out of E, with its authorization
re-verified. The ready key must then be current at the newer epoch.

**Not a latch.** No mutable compromise latch, flag file, or new state owner is
created. The condition is recomputed from the verified history on every
evaluation: it is a pure function of chain entries, head registries, and
retained authorizations. There is no new authority state.

**Scope.**

- It applies only when K was **current** at the marking. A non-current key's
  compromise is in-epoch marking only (RR-6 rule 4).
- It is independent of `evaluate_rotation`. That function already refuses
  this path (`PREDECESSOR_NOT_SINGLE_CURRENT` /
  `CANDIDATE_PREDECESSOR_NOT_SUPERSEDED`), but readiness must refuse it on
  its own.
- It implements the gate's SW-9 test: "current-key compromise without an
  epoch advance never reaches `S_CURRENT`".

### 10.4 Containment vs C-4 (RR-28, OWNER-ACCEPTED with strict containment)

C-4 requires the signer-owned authority ledger to journal `ADVANCE_EPOCH`
(PB-13), and the signer refuses to start without a credential (PB-6). So the
compromised P **may remain physically in CURRENT temporarily**. That does
**not** mean it remains issuance-authorized.

Sequence requirements:

1. The compromise hold is engaged (`HELD`, `KEY_COMPROMISE_RECOVERY`).
2. The signer is normally stopped.
3. The `COMPROMISE_MARKING` head transition is already committed before any
   recovery start.
4. P stays in CURRENT only for the narrow C-4 recovery step.
5. A narrowly gated recovery execution may start the signer, but only
   enough to perform the destroy/narrow-only authority-ledger operations
   C-4 requires: the `ADVANCE_EPOCH` adoption, then quarantine.
6. OwnerEvidence issuance and signing stay denied. No generic signer
   operation becomes available merely because the private key is loaded.
7. After the required ledger operations, the ladder proceeds forward through
   the epoch and witness recovery (§10.2).

```text
private key loaded                  != issuance authority
COMPROMISED key loaded for recovery != valid evidence issuer
```

**Current source cannot enforce this yet.** L1 has no authority ledger and
refuses every signing request (`NOT_READY`, PB-6), so there is nothing to
gate today. The ledger and its operations arrive with PR-1 (B1b-3d L3a–L4).
The gate is therefore **required Source Prep B implementation work** in two
parts:

- **A pure evaluator.** It permits an operation only under all of:
  - a valid `HELD` hold of kind `KEY_COMPROMISE_RECOVERY` naming P as
    `expectedPredecessorKeyId`;
  - a verified committed `COMPROMISE_MARKING` head that marks P;
  - the operation is in the closed set {`ADVANCE_EPOCH` adoption bound to the
    re-verified `KEY_COMPROMISE` authorization, `VOID_CHALLENGE`,
    `QUARANTINE_USE`}.

  It refuses everything else, including `ISSUE`, every signing operation, and
  `REGISTRY_VIEW` naming a current key.
- **The runtime wiring into the future signer.** It is designed and tested
  here as a pure contract, and wired with the ledger in PR-1.

No credential-less signer mode is invented.

Issuance is also impossible independently of the gate, because of each of:

- the hold;
- after the marking head, `NO_CURRENT_ISSUANCE_KEY`;
- the binding (B1 has no current key);
- the compromise-epoch rule;
- P's evidence is `KEY_COMPROMISED`.

If the owner judges the signer process itself untrustworthy, that is RR-6
S9, which means STOP, not SW-9.

### 10.5 `AuthorityKeyTransitionV1` (RR-23)

| Option | Assessment |
| --- | --- |
| **A. No new contract** | the authority is fully represented by existing objects: the K-ROOT registry (who is current, P's lifecycle), the RHAA / EAA (permission for one exact transition), the witness (execution and freshness), and the Prep A readiness result (verification) |
| **B. Non-authority record only** | an evidence summary emitted by the verifier after `S_CURRENT`. It is what design §7.7 already defines (story 4) |
| C. Authority-bearing | **rejected.** No property is missing. It would be a second authority story, able to disagree with the registry |

**OWNER-ACCEPTED.** No new authority-bearing `AuthorityKeyTransitionV1` is
introduced. Existing authority stays `AuthorityRegistryV1`,
`RegistryHeadAdvanceAuthorizationV1`, and `EpochAdvanceAuthorizationV1`.
`RecoveryWitnessV2` stays freshness and execution evidence.

If Source Prep B implements `AuthorityKeyTransitionV1`, it is only:

- a pure, derived ceremony / readiness record;
- non-authority, with `authorityGranted = false`;
- reproducible from the authoritative inputs.

It must never become required cryptographic authority for acceptance.

It is the §7.7 record as a verifier **output** that grants nothing. Its fields: `authorityGranted: false`;
`kind ROTATION | KEY_COMPROMISE_RECOVERY`; predecessor and successor keyIds;
from and to heads; epoch(s); witness digests; the `ceremonyId`; the
readiness result digest; and `predecessorMaterial`. It is consumed by nothing
that decides authority.

### 10.6 `CeremonyHoldV1` (RR-24, OWNER-ACCEPTED with state refinement)

It is a versioned, **pure, non-authority** data contract, implemented in
Source Prep B. Every field is unauthenticated (design §9.1).

| Field | Purpose |
| --- | --- |
| `protocol`, `schemaVersion` | parse strictly; an unknown version fails closed |
| `environment` | refuse a hold from another environment |
| `ceremonyId` | a ceremony step refuses unless the hold names its own ceremony |
| `transitionKind` | closed: `INITIAL_CUSTODY`, `ROTATION`, `KEY_COMPROMISE_RECOVERY` (selects the ladder) |
| `state` | **closed: `HELD`, `RELEASED`** |
| `reason` | closed set, informational |
| `expectedPredecessorKeyId` | refuse a ceremony run against another P. `null` is valid **only** for `INITIAL_CUSTODY` |
| `expectedSuccessorKeyId` | null only in phases where it is not yet known (before preparation); fixed after |
| `observedWitnessDigest` | `HELD`: the head observed when the hold was engaged. `RELEASED`: the independently verified head at which `S_CURRENT` was established |

There is no `createdAt`: nothing uses it, and timestamps are not authority.
`observedRegistryVersion` is implied by the witness digest.

**Semantics.**

```text
valid HELD                                  -> issuance NOT_READY; ceremony steps may run (if bound)
valid RELEASED, every phase binding holds   -> the hold check passes (still not authority, not S_CURRENT)
missing / malformed / unknown-version       -> fail closed; NEVER interpreted as RELEASED
file absence                                != proof of release
hold != authority;  hold release != authority;  hold release != S_CURRENT;  missing hold != released
```

**`RELEASED` bindings.** For a valid `RELEASED` hold, the Source Prep B
verifier requires every phase-specific binding that proves the hold
corresponds to the independently verified state:

- `environment` equals the store environment;
- `ceremonyId` equals the verified `SuccessorCeremonyRecordV1` for the
  successor, or, for `INITIAL_CUSTODY`, the deterministic initial ceremony ID
  (below);
- `transitionKind` equals the ladder the chain history shows:
  - `INITIAL_CUSTODY` when the head registry is the genesis registry;
  - `ROTATION` after a rotation;
  - `KEY_COMPROMISE_RECOVERY` when §10.3 applied;
- `expectedPredecessorKeyId` equals the predecessor of the verified
  transition;
- `expectedSuccessorKeyId` equals the authority-current key at the head, and
  the key the loaded-key binding names;
- `observedWitnessDigest` names a verified chain entry with the **same
  registry head** as the current head. Later ledger-only entries are
  allowed; a different head is not.

**Consequence for readiness.** Prep A's boolean `hold_present` input
(`False` → `PASS`) is superseded in Source Prep B. The `CEREMONY_HOLD` check
requires a valid, bound `RELEASED` hold, and absence fails closed. The Prep A
source is not changed by this design pass.

**Hold-release eligibility vs full readiness (no circularity).** Two logical
evaluations exist. Both are pure, over the same verified inputs, with no new
authority owner.

- **A. `HOLD_RELEASE_ELIGIBILITY`.** Every applicable readiness condition
  **except** "the hold is already `RELEASED`". It still requires a valid,
  bound `HELD` hold of the same ceremony. It includes every Source Prep A
  condition:
  - the verified K-ROOT registry and its current key;
  - the exact `RecoveryWitnessV2` genesis and head, with a valid witness
    signature;
  - the owner genesis pin;
  - the single-current-key rule;
  - the loaded-key / current-key binding;
  - the credential inventory;
  - authority-ledger consistency;
  - the compromise-epoch rule, where it applies.
- **B. `FULL_READINESS`.** Every applicable condition **plus** a valid,
  bound `RELEASED` hold of the same ceremony, matching the same verified
  custody, witness, and key state.

The order is always:

```text
HELD -> HOLD_RELEASE_ELIGIBILITY passes -> explicit owner release -> RELEASED -> FULL_READINESS re-run
```

It is never "release because full readiness passed": full readiness itself
requires the release. This applies to every transition kind. For a rotation,
gate L3e-10 is eligibility, L3e-11 is the release, and `S_CURRENT` needs the
re-run full readiness.

```text
hold-release eligibility != readiness
hold release             != authority
hold release             != S_CURRENT
missing hold             != released
```

**`INITIAL_CUSTODY` (RR-30, OWNER-ACCEPTED).** The initial B1b-3d custody
key takes part in the same fail-closed hold model as later rotations. No
separate bootstrap authority object is introduced.

| Field | Rule for `INITIAL_CUSTODY` |
| --- | --- |
| `transitionKind` | `INITIAL_CUSTODY`: the **only** kind for which `expectedPredecessorKeyId = null` is valid |
| `expectedPredecessorKeyId` | `null` (required) |
| `expectedSuccessorKeyId` | the initial / current custody key: for the DEV_SYNTHETIC baseline, the existing initial OWNER_ACTOR K-ACT `test-only.dev-synthetic.actor.b1b3d.1` (PB-9), not new successor material. It must be the authority-current key at the genesis registry head and the key the loaded-key binding names |
| `ceremonyId` | closed and deterministic, derived only from fixed context: the environment plus the initial key identity. Not operator text, a timestamp, or a random name. The exact canonical encoding is SOURCE DETAIL; the input space is closed |
| `observedWitnessDigest` | `HELD`: the accepted `RecoveryWitnessV2` genesis digest, equal to the owner genesis pin (SW-8). `RELEASED`: a verified chain entry rooted at that pinned genesis, with the **genesis registry head** (genesis itself, or a later ledger-only entry) |
| `environment`, `state`, `reason`, `protocol`, `schemaVersion` | as for every hold |

**Initial lifecycle.** Absence never becomes `RELEASED` directly:

```text
missing -> INITIAL_CUSTODY / HELD -> HOLD_RELEASE_ELIGIBILITY -> INITIAL_CUSTODY / RELEASED -> FULL_READINESS
```

- A missing, malformed, or unknown hold always fails closed.
- The existence of the older B1b-3d credential does **not** grandfather it
  into a released state.

**Still non-authority.** An `INITIAL_CUSTODY` hold, in either state, does
not:

- create registry authority;
- substitute for K-ROOT or K-WIT;
- make a credential current;
- grant issuance authority.

**Responsibility.**

- **Source Prep B source may implement:**
  - `INITIAL_CUSTODY` parsing and validation;
  - the `HELD` / `RELEASED` state rules;
  - `HOLD_RELEASE_ELIGIBILITY`;
  - full-readiness hold validation;
  - the deterministic initial ceremony-ID derivation;
  - synthetic tests.

  It **must not** create any live hold record.
- **PR-1 (B1b-3d L3a–L4) owns the future live bootstrap:**
  1. establish and verify the V2 genesis;
  2. create `INITIAL_CUSTODY / HELD`;
  3. prove hold-release eligibility;
  4. perform the explicit owner acceptance step;
  5. persist `RELEASED`;
  6. re-run full readiness.

  This record does not authorize PR-1.

## 11. SW-9 crash matrix

The head is the witnessed head. "Issue?" means may the signer issue. The
composition is the accepted RR-22 A.

| # | State | Head (authority) | Loadable (CURRENT) | Issue? | Rollback to P? | Recovery | Destroy P? |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | hold engaged, nothing prepared | vN (P current) | P | no (hold) | P was never moved. But P is compromised, so it never resumes | owner: continue to marking | no |
| 2 | successor prepared, marking not yet done | vN | P | no | as 1 | owner: marking, or destroy S (`NOT_IN_HEAD`) and restart | no |
| 3 | vN+1 marking signed, RHAA absent | vN | P | no | as 1 | owner: sign the RHAA; vN+1 stays staged | no |
| 4 | marking committed; EAA exists, witness not advanced | vN+1 (no current key; P `COMPROMISED`) | P | no (no current key; §10.3) | **no**: P is compromised at the head | owner: C-4 through the narrow recovery gate (§10.4). If the adoption is already journalled: `LEDGER_EPOCH_AHEAD_OF_WITNESS` → the witness executes **the same** EAA | no |
| 5 | epoch advance committed; custody still P | vN+2 (E(n+1), S current) | P | no (binding: B1 = S) | no | forward: quarantine, witness, cutover | no |
| 6 | P → RETIRED, S not installed | vN+2 | — (the unit cannot start) | no | **no** | forward: install S (automatic within the owner's ceremony; no authority step) | no |
| 7 | S installed, signer not started | vN+2 | S | no (no `HEALTH`, hold) | no | start under the hold | no |
| 8 | `HEALTH` reports the wrong key | vN+2 | wrong blob | no (binding) | no | stop; diagnose the inventory; restore **S** from PREPARED / RETIRED knowledge. P never | no |
| 9 | `HEALTH` = S, binding fails | vN+2 | S? | no | no | the hold stays; diagnose B2 / B3 (F20) | no |
| 10 | `S_CURRENT`, P retained | vN+2 | S | yes (per-operation readiness) | no | destroy P: the **mandatory next step** (RR-29) | **yes, required** |
| 11 | crash or failure during destruction | vN+2 (unchanged) | S | **no**: the availability hold is engaged (`HELD`) | **no**, and the head is never rolled back | owner: retry the destruction idempotently. A file that reappears after a crash (unlink not yet fsynced) has the same hash and is deleted again. Report `KNOWN_CUSTODY_DEBT` until the §13 evidence is complete, then release the hold (a bound `RELEASED` record) | yes (complete it) |
| 12 | old snapshot restored after `S_CURRENT` | as restored | as restored | if witness, registry, and ledger are all restored: **undetected** (whole-host rollback). If only the credential is restored: the binding fails (`STALE_CREDENTIAL_PRESENT`) | no | if detected: STOP, classify the snapshot (RR-17). A snapshot with both halves outside the accepted boundary → RR-20b | n/a |

The rotation (RR-6 S1) uses the same rows 6–12 after its single head
advance. Row 11 applies identically to a rotation.

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
4. **After:** `lstat` is absent, and the credential inventory is `STEADY`
   with CURRENT(S).
5. A `PredecessorDestructionRecordV1` (non-authority) holds these facts plus
   the `S_CURRENT` readiness result it depended on. It is reported as
   `predecessorMaterialDestroyedFromActiveCustody: true`.

This list is the **required** destruction evidence (OWNER-ACCEPTED, RR-29).
If any item is missing, the destruction is incomplete, and §4.1's
failure rule applies:

- the availability hold;
- `KNOWN_CUSTODY_DEBT`;
- owner retry;
- no authority rollback;
- no restore of P.

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

## 15. Source Prep B source implementation boundary (per the accepted decisions)

Source Prep B source contains only what is needed to prove the following,
TEST-only first and with no DEV contact:

| # | Responsibility | Where |
| --- | --- | --- |
| 1 | the reusable closed successor keygen form `successor <N>` (§7); `actor` unchanged | `services/authority-dev` ceremony tooling (a reviewed release change) |
| 2 | ordinal → `keyId` / `ceremonyId` derivation and anti-reuse (burned ordinals, §5) | keygen (derivation) + a pure ceremony-record verifier |
| 3 | PREPARED / CURRENT / RETIRED custody observation and transition verification (§3, §4.1) | a pure verifier over the Prep A inventory; the installer stage for the custody directories; the unit's `InaccessiblePaths`; a single-release `RELEASE_SET` (RR-25) |
| 4 | same-filesystem (`st_dev`) cutover precondition (RR-26) | keygen preflight + the custody transition verifier |
| 5 | current credential never overwritten during PREPARE (§7.3) | keygen before/after re-hash + a before/after inventory check |
| 6 | non-authority `SuccessorCeremonyRecordV1` (§9.2) | a pure parser and verifier |
| 7 | `CeremonyHoldV1` with `HELD` / `RELEASED`, the `RELEASED` bindings, `INITIAL_CUSTODY` (null predecessor only there; deterministic initial ceremony ID), and the `HOLD_RELEASE_ELIGIBILITY` / `FULL_READINESS` split (§10.6). It replaces the Prep A boolean in readiness. No live hold record is created | a pure parser and verifier + synthetic tests |
| 8 | the compromise-epoch derived readiness rule `COMPROMISE_EPOCH_ADVANCE_REQUIRED` (§10.3) | pure readiness |
| 9 | the current-key compromise recovery evaluator for the §10.2 order | pure evaluator |
| 10 | the narrow C-4 compromised-key recovery gate (§10.4) | pure evaluator; runtime wiring with the ledger in PR-1 |
| 11 | the predecessor destruction-order verifier and the destruction evidence (§4.1, §13) | pure verifier + non-authority `PredecessorDestructionRecordV1` |
| 12 | crash and failure matrices: every §4.1 row, every §11 row, the §7.4 refusal matrix, every §14 case | tests |

Optional, and only if implemented as a derived non-authority output:
`AuthorityKeyTransitionV1` (RR-23).

**Not added:**

- a new authority contract;
- a witness or registry schema change;
- a `KeyPublicationV2` (RR-27);
- a new inventory phase;
- a credential-less signer mode;
- a DEV_SYNTHETIC witness profile (PR-1);
- any live execution.

**Outside Source Prep B:**

- PR-1: B1b-3d L3a–L4 designed for V2, installed, and accepted, including
  the signer's authority ledger, the runtime wiring of the §10.4 gate, and
  the live `INITIAL_CUSTODY` bootstrap (§10.6);
- PR-2: the snapshot inventory;
- PR-3: the owner's real off-host register and material (including the
  ceremony register of burned ordinals);
- any actual DEV_SYNTHETIC rotation or recovery rehearsal;
- PROD authority;
- B1b-3f Privacy custody;
- Stage III;
- First Memory.

**Whole-host rollback remains unresolved.**

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
- that accepting these decisions authorizes any source, release, or live
  step beyond the Source Prep B source boundary of §15.

## 17. Destruction and custody evidence summary

| Evidence | Proves | Does not prove |
| --- | --- | --- |
| inventory per phase (Prep A) | which roles hold which blob hashes | authority |
| ceremony record (RR-27) | which reviewed release and CLI produced which publication and blob | authority; key secrecy |
| binding (Prep A) | the loaded blob = the head key's blob, and the signer reports that key | the signer's memory; authority |
| destruction record | a logical unlink plus a directory fsync of a known blob | media erasure; the absence of copies |

## 18. Owner decisions

| # | Question | Accepted outcome | Classification |
| --- | --- | --- | --- |
| RR-11-D1 | one successor-capable release for many rotations, or one per rotation? | one reusable, reviewed, **closed** release with form `successor <N>`. N (a bounded positive ordinal) derives `keyId` and `ceremonyId`. No other input. A used ordinal, `keyId`, or `ceremonyId` is burned forever, even if abandoned. Registry history stays the authority boundary for key identity; the owner ceremony register prevents reuse but is not authority (§5) | **OWNER-ACCEPTED** |
| RR-11-D2 | fixed runtime credential name? | `owner-actor-signing-key`, fixed across rotations. The signer requests exactly that one credential; only the CURRENT source slot backs it. The five identifiers are not aliases (§6) | **OWNER-ACCEPTED** |
| — | compromise-epoch readiness rule | after a verified `COMPROMISE_MARKING` of the current key, no same-epoch successor is ever ready: `COMPROMISE_EPOCH_ADVANCE_REQUIRED`. Derived from verified history; no latch; clears only on the verified `KEY_COMPROMISE` epoch advance (§10.3) | **DERIVED (RR-6), OWNER-ACCEPTED** |
| RR-22 | SW-9 marking composition | two transitions: a separate in-epoch `COMPROMISE_MARKING` head advance first, then the `KEY_COMPROMISE` epoch advance. Not combined (§10.1) | **OWNER-ACCEPTED** |
| RR-23 | `AuthorityKeyTransitionV1` | no new authority-bearing contract. If implemented: a pure, derived, reproducible, non-authority record, `authorityGranted = false`, never required for acceptance (§10.5) | **OWNER-ACCEPTED** |
| RR-24 | `CeremonyHoldV1` | a versioned pure non-authority contract with explicit `HELD` / `RELEASED`; missing, malformed, or unknown-version fails closed and is never `RELEASED`; `RELEASED` must be bound to the verified state (§10.6) | **OWNER-ACCEPTED** (with state refinement) |
| RR-25 | release set | exactly one installed executable authority-dev release (the successor-capable one). No retained executable release for rollback. The prior release is preserved by history and provenance. Release rollback never implies authority rollback (§7.1) | **OWNER-ACCEPTED** |
| RR-26 | custody paths | CURRENT `/etc/credstore.encrypted/…owner-actor.cred`; PREPARED `/etc/lilith-authority-custody/prepared/…`; RETIRED `/etc/lilith-authority-custody/retired/…`; `root:root 0700` directories, `0600` regular blobs, no symlinks, no extra blobs, `st_dev` proven before renames, inaccessible to the service, root tooling only (§8) | **OWNER-ACCEPTED** |
| RR-27 | provenance | the existing publication is unchanged (no v2 unless proven necessary). A separate non-authority `SuccessorCeremonyRecordV1` carries `ceremonyId`, `successorOrdinal`, `keyId`, `publicationDigest`, `credentialBlobSha256`, `reviewedReleaseSha`, `createdForRole = PREPARED` (historical) (§9.2) | **OWNER-ACCEPTED** (with minimality refinement) |
| RR-28 | SW-9 containment vs C-4 | P may stay physically in CURRENT, only for the narrow C-4 step, after the marking head, under the hold. A narrow recovery gate permits only the destroy/narrow-only ledger ops; issuance and signing are denied. Required Source Prep B work; no credential-less mode (§10.4) | **OWNER-ACCEPTED** (strict containment) |
| RR-29 | predecessor destruction | the mandatory next custody-cleanup step after verified `S_CURRENT`, with the §13 evidence. On failure: no authority rollback, no restore of P, availability hold, `KNOWN_CUSTODY_DEBT`, owner retry (§4.1, §13) | **OWNER-ACCEPTED** |
| RR-30 | initial-custody hold record | `transitionKind INITIAL_CUSTODY`, the only kind with `expectedPredecessorKeyId = null`. `expectedSuccessorKeyId` = the existing initial K-ACT. It binds the pinned V2 genesis. It has a deterministic closed ceremony ID and a lifecycle of missing → `HELD` → eligibility → `RELEASED` → full readiness; no grandfathering; no bootstrap authority object. It stays non-authority. PR-1 owns the live bootstrap (§10.6) | **OWNER-ACCEPTED** |

**No PENDING_OWNER_DECISION remains for Source Prep B.**

**SOURCE DETAIL** (does not alter authority, state ownership, the custody
boundary, or failure semantics):

- the exact canonical encoding of the initial and successor ceremony IDs;
- the exact closed `reason` values for `CeremonyHoldV1`;
- the file locations of hold and ceremony records;
- the refusal-reason names.

**ALREADY_DETERMINED (not reopened):**

- no restore of P after the authority PONR (§4.2, gate §11);
- P not destroyed before `S_CURRENT` (RR-11);
- `AuthorityKeyTransitionV1` and `CeremonyHoldV1` are non-authority;
- C-4 unchanged;
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
