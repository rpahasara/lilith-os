# Slice 15B2b-B1b-3e — Source Prep B: Successor Custody and Compromise Recovery

Status:

- **SOURCE IMPLEMENTED / TEST PROVEN** (SW-1, SW-2, SW-9; pure contracts,
  TEST-only fixtures, synthetic keys only)
- **NEW AUTHORITY-DEV SOURCE RELEASE PREPARED** (successor-capable; not
  built, not installed, not active)
- **LIVE INSTALL ABSENT**
- **LIVE REHEARSAL NOT AUTHORIZED**
- **WHOLE-HOST ROLLBACK UNRESOLVED**
- **REAL AUTHORITY ABSENT**

Base: protected main `3453f0d28f4d84aa3388647b9354a5d201014f74`.

This slice implements the accepted
[Source Prep B design](slice-15b2b-b1b3e-source-prep-b-design.md) ("the
design"), §15 items 1–12, for the [live-rehearsal gate](slice-15b2b-b1b3e-live-rehearsal-gate.md)
("the gate") §14 items SW-1, SW-2, and SW-9. It builds on the
[B1b-3e design](slice-15b2b-b1b3e-rotation-revocation-recovery.md), the
[source contracts](slice-15b2b-b1b3e-source-contracts.md), and
[Source Prep A](slice-15b2b-b1b3e-source-prep-a-witness-readiness.md).

Passing these tests does not authorize any live step. The gate's live entry
matrix still reads **DO NOT ENTER** until PR-1, PR-2, and PR-3 exist and every
§14 item is reviewed and accepted.

Nothing was contacted or changed. No DEV, PROD, gcloud, SSH, IAP, sudo,
systemctl, systemd-creds, or installer run against any host. No credential
was generated, moved, rotated, revoked, or deleted. No registry, witness,
RecoveryEpoch, authority ledger, broker ledger, L04, IAM, WIF, or sudoers was
touched. `/etc/credstore.encrypted`, `/etc/lilith-authority-custody`, and
`/var/lib/lilith-authority-dev` were not created or read on any real host.
Every custody test runs on a temporary directory or on pure observations.

```text
source release prepared != installed release
credential exists       != authority
PREPARED successor      != current successor
same-filesystem proof   != authority
hold / hold release     != authority;  hold release != S_CURRENT
missing hold            != released
S_ACTIVATED             != S_CURRENT
destruction             != revocation;  destruction failure != authority rollback
logical destruction     != media zeroization
```

## 1. Location and delivery impact

| Path | Role |
| --- | --- |
| `services/owner-memory-control/lilith_owner_memory/successor_custody.py` | **new, pure.** Successor identity and bounds; `SuccessorCeremonyRecordV1`; the burned-ordinal register; custody observation, A/B/C states, same-filesystem proof, forward-only transitions; `CeremonyHoldV1` and its lifecycle; predecessor destruction evidence |
| `services/owner-memory-control/lilith_owner_memory/successor_readiness.py` | **new, pure.** Verified history; compromise-epoch rule; SW-9 evaluator; derived `AuthorityKeyTransitionV1`; hold binding; `HOLD_RELEASE_ELIGIBILITY` / `FULL_READINESS`; narrow C-4 gate; custody-step authorization; destruction order |
| `services/owner-memory-control/tests/synthetic_b1b3e_prep_b.py` | **new, TEST-only.** `PrepBScenario` (durable TEST witness, rotation and SW-9 ladders, error paths), custody observations, `TempCustody` (real temp directory, POSIX) |
| `services/owner-memory-control/tests/test_b1b3e_source_prep_b.py` | **new.** 55 tests |
| `services/authority-dev/ceremony/lilith_authority_keygen_dev.py` | **changed (release member `cli/`).** Closed `successor <N>` form; `actor` unchanged |
| `services/authority-dev/deploy/lilith-authority-dev.service` | **changed (release member `assets/`).** `InaccessiblePaths` adds `/etc/lilith-authority-custody` |
| `services/authority-dev/ceremony/install_authority_dev.py` | **changed (control tooling, never payload).** Stage `custody` (L2c); RR-25 `RELEASE_SET` wording |
| `services/authority-dev/release_file_set.py` | new test file listed |
| `services/authority-dev/tests/test_successor_custody.py` | **new.** 23 tests |
| `docs/architecture/README.md` | one index row |

**Unchanged:** `rotation_contracts.py`, `witness_readiness.py`,
`recovery_contracts.py`, `authority_contracts.py`, `authority_verifier.py`,
every `lilith_authority_signer` module, every runtime module of
`lilith_authority_dev` (`profile`, `credential`, `core`, `server`,
`protocol`, `evidence_minter`), and every golden vector. `services/core-api/**`,
`services/memory-broker/**`, workflows, IAM, WIF, and sudoers are unchanged.
No runtime package imports the new modules (a test enforces it for
authority-dev).

## 2. Controlling records

| Item | Controlling text | Taken exactly |
| --- | --- | --- |
| RR-11-D1 | design §5 | closed `successor <N>`; N decimal, no leading zero, four digits, N ≥ 2; `keyId = test-only.dev-synthetic.actor.b1b3e.<N>`; `ceremonyId = dev-synthetic.owner-actor.successor.<N>`; burned ordinals |
| RR-11-D2 | design §6 | runtime name `owner-actor-signing-key` for every rotation; five identifiers never aliases |
| §7.2–§7.4 | design | successor preconditions, one run, refusal matrix |
| RR-26 | design §8 | CURRENT / PREPARED / RETIRED paths, `root:root 0700` directories, `0600` blobs, `st_dev` proof, `InaccessiblePaths` |
| RR-27 | design §9 | publication unchanged; separate non-authority ceremony record |
| RR-22, §10.2 | design §10 | marking head advance first, then the `KEY_COMPROMISE` epoch advance |
| §10.3 | design | compromise-epoch rule; no latch |
| RR-28 | design §10.4 | narrow C-4 gate, pure; closed set {`ADVANCE_EPOCH`, `VOID_CHALLENGE`, `QUARANTINE_USE`}; no credential-less mode |
| RR-23 | design §10.5 | derived non-authority `AuthorityKeyTransitionV1` only |
| RR-24, RR-30 | design §10.6 | `CeremonyHoldV1`, `INITIAL_CUSTODY`, eligibility vs full readiness |
| SW-1, RR-29 | design §4, §13 | forward-only cutover; destruction only after `S_CURRENT`; required evidence; failure rule |
| RR-25 | design §7.1 | one installed executable release |
| §11 | design | SW-9 crash matrix rows 1–12 |

Where this prompt and the merged design differ, the merged design governs:

- **transition kind name.** The design's closed set is `INITIAL_CUSTODY`,
  `ROTATION`, `KEY_COMPROMISE_RECOVERY` (§10.6). The source uses `ROTATION`,
  not `ROUTINE_ROTATION`. A hold naming `ROUTINE_ROTATION` fails closed as
  `HOLD_TRANSITION_KIND_UNKNOWN` (tested).
- **ceremonyId encoding.** The design pins
  `dev-synthetic.owner-actor.successor.<N>`. The environment and profile are
  carried by the fixed `dev-synthetic` label, and the keyId is a bijective
  function of N, so the fixed context (environment, ordinal, keyId) is fully
  determined by N. The record verifier re-derives and checks all three.

No accepted owner decision was contradicted by current source.

## 3. SW-2 — the successor-capable keygen (RR-11-D1, RR-11-D2)

Forms: exactly `actor` (unchanged) and `successor <N>`.

| Input | Rule |
| --- | --- |
| `N` | ASCII decimal, `[0-9]{1,16}`, no leading zero, `2 ≤ N ≤ 9999` (**SOURCE DETAIL bound**, design §5 "four digits") |
| everything else | fixed: environment `dev`, profile `DEV_SYNTHETIC`, `OWNER_ACTOR`, `OWNER_MEMORY_OPERATION`, Ed25519, credential name, PREPARED path, `--with-key=host`, DEV machine ID and hostname, publication schema |

Refusals: `USAGE_SUCCESSOR_ORDINAL` (wrong arity, any extra argument or flag),
`SUCCESSOR_ORDINAL_INVALID` (non-decimal, sign, space, fullwidth digit,
leading zero, `0`, over 16 digits), `SUCCESSOR_ORDINAL_OUT_OF_RANGE` (`1`,
`10000`). There is no path, keyId, name, environment, algorithm, domain,
evidence type, schema, role, output, force, seed, or export option.

**Derivation.** `successor_key_id(N)`, `successor_ceremony_id(N)`, and the
inverse `successor_ordinal(keyId)` in the keygen; `successor_identity(N)`
owner-side. A test proves both sides agree for every N in 2..9999 and that the
9998 keyIds and ceremonyIds are distinct and never the initial K-ACT.

**Preflight (read-only, nothing generated).** The common host checks (root,
isolated interpreter, DEV machine ID and hostname, no swap, host key
`root:root 0400`, `systemd-creds` `0755`, credstore `root:root 0700`), then:
credstore holds exactly the CURRENT slot (`CREDSTORE_NOT_EXACTLY_CURRENT`);
CURRENT is a `root:root 0600` regular file, not a symlink (`CURRENT_CUSTODY`);
custody root `root:root 0700` with exactly `prepared` and `retired`
(`CUSTODY_ROOT_ABSENT`, `CUSTODY_ROOT_CUSTODY`,
`CUSTODY_ROOT_UNEXPECTED_ENTRY`); `prepared/` and `retired/` `root:root 0700`,
not symlinks (`PREPARED_CUSTODY`, `RETIRED_CUSTODY`), both empty
(`PREPARED_NOT_EMPTY`, `RETIRED_NOT_EMPTY`); credstore, `prepared/`, and
`retired/` on one `st_dev` (`CUSTODY_FILESYSTEM_MISMATCH`); CURRENT observed
"before" (device, inode, mode, uid, gid, size, SHA-256).

**One run.** Generate one Ed25519 key in memory; PKCS#8 DER only to the
`systemd-creds encrypt --with-key=host --name=owner-actor-signing-key` pipe;
refuse ciphertext containing the plaintext; re-observe CURRENT; open
`prepared/` with `O_DIRECTORY|O_NOFOLLOW` and re-check it on the descriptor
(root 0700, same device, empty); create the blob `O_EXCL|O_NOFOLLOW` `0600`
through `dir_fd`; fsync the file; fsync the directory; re-observe CURRENT.
Any change is `FAILED CURRENT_CHANGED` with nothing printed; the PREPARED blob
it may leave is an abandoned successor (burned ordinal, destroyed, never
reused). stdout carries only the canonical v1 publication; stderr carries only
`REFUSED <reason>` or `FAILED <reason>`.

The keygen never writes CURRENT or RETIRED, never mutates an existing
PREPARED blob, never reads the host key, and never consults registry,
witness, or ledger state. Live privilege (`euid == 0`) is enforced by the
keygen; source tests pass `euid=0` explicitly and run as an ordinary user on
temporary trees (`Host.owner_uid/gid`, `Host.device_of` model root ownership
and a mount boundary).

**Publication stays v1.** Same fields as `actor`. A successor differs only in
the derived `keyId` and in `custodyEvidence.credentialPath`, which keeps its
existing meaning ("where the ciphertext was written") and is the PREPARED path.
`publication()` refuses any identity outside the two closed forms. No
`KeyPublicationV2`.

## 4. Burned ordinals (anti-reuse)

`SuccessorCeremonyRegisterV1` (`LILITH_SUCCESSOR_CEREMONY_REGISTER` v1) is the
owner's burned-ordinal model (the successor part of PR-3). It is not
authority and not a cryptographic root. Each row is `{successorOrdinal, keyId,
ceremonyId, publicationDigest, credentialBlobSha256}`; keyId and ceremonyId
must be the derivation of the ordinal (`REGISTER_ENTRY_NOT_DERIVED`).

| Operation | Refuses |
| --- | --- |
| parse | duplicate ordinal, keyId, or ceremonyId; the same blob or publication under two ordinals; wrong environment |
| `check_ordinal_unburned` (before PREPARE) | `ORDINAL_BURNED`, `KEY_ID_BURNED`, `CEREMONY_ID_BURNED` |
| `register_successor_ceremony` (after PREPARE) | a burned ordinal (also after abandonment), `MATERIAL_ALREADY_REGISTERED` |
| `verify_registered_ceremony` (readiness) | `ORDINAL_MATERIAL_MISMATCH` (same ordinal, other material), `KEY_ID_ORDINAL_CONFLICT`, `CEREMONY_ID_ORDINAL_CONFLICT`, `CEREMONY_NOT_REGISTERED` |

Registry history stays the authority boundary for key identity (K-ROOT never
publishes a second record under one keyId).

## 5. `SuccessorCeremonyRecordV1` (RR-27)

`LILITH_SUCCESSOR_CEREMONY_RECORD` v1, fields `ceremonyId`,
`successorOrdinal`, `keyId`, `publicationDigest` (SHA-256 of the exact
canonical publication bytes), `credentialBlobSha256`, `reviewedReleaseSha`
(40-hex), `createdForRole = PREPARED` (historical creation provenance only).
No environment, domain, or type is duplicated: they are verified from the
bound publication. `authority_granted = False`.

`verify_successor_ceremony_record` checks, in order: shape and version;
`createdForRole`; ordinal bounds; ceremonyId and keyId are the derivation of
the ordinal; the publication is exact canonical bytes with that digest; it is
the DEV_SYNTHETIC PREPARED-form publication of that keyId (profile,
environment, domain, types, credential name, `withKey`, credential path,
fingerprint); its `blobSha256` equals the record; the reviewed release equals
the installer evidence; and, when given, the observed PREPARED blob hash.
Anti-substitution cases (old publication + new blob, new publication + old
blob, right keyId + wrong record, right ceremonyId + wrong ordinal, right
blob from another release, right release + wrong digest, other environment,
stale abandoned blob, reused ordinal with a new blob) all fail closed.

`reviewedReleaseSha` is provenance: meaningful only with the installer's
release directory, selector, and `CLI_BYTES` evidence. It is never authority.

## 6. Custody paths and observation (RR-26)

| Role | Path | Custody |
| --- | --- | --- |
| CURRENT | `/etc/credstore.encrypted/lilith-authority-dev.owner-actor.cred` | the only `LoadCredentialEncrypted=` source |
| PREPARED | `/etc/lilith-authority-custody/prepared/lilith-authority-dev.owner-actor.cred` | referenced by no unit |
| RETIRED | `/etc/lilith-authority-custody/retired/lilith-authority-dev.owner-actor.cred` | referenced by no unit |

Directories `root:root 0700`; blobs `root:root 0600` regular files; no
symlinks; no extra names. These are SOURCE CONTRACT paths; none was created
on any host.

`CustodyObservationV1` = the Prep A slot inventory + `st_dev` of the three
slot directories + the custody root's facts + CURRENT's `(st_dev, st_ino)`.
`observe_custody` fails closed on a missing or wrongly owned custody root,
unexpected root entries, a missing slot directory, any slot name other than
the fixed one, an unproven or mismatched filesystem, and everything the Prep A
inventory refuses. `custody_state` names the state by exact P / S hashes:

| State | CURRENT | PREPARED | RETIRED | Prep A phase |
| --- | --- | --- | --- | --- |
| `PREDECESSOR_STEADY` | P | — | — | `STEADY` |
| `A_PREPARED` | P | S | — | `SUCCESSOR_PREPARED` |
| `B_VACATED` | — | S | P | `CUTOVER_VACATED` |
| `C_INSTALLED` | S | — | P | `CUTOVER_INSTALLED` |
| `SUCCESSOR_STEADY` | S | — | — | `STEADY` |

No new inventory phase exists.

**Same filesystem.** `same_filesystem_reason` requires three integer `st_dev`
values that are equal (`SAME_FILESYSTEM_UNPROVEN`,
`CUSTODY_FILESYSTEM_MISMATCH`). The keygen proves it before PREPARE; every
planned rename proves it again; the installer's L2c POST checks it.

**CURRENT preserved during PREPARE.** The keygen's own before/after CURRENT
facts, and `verify_preparation` over the before/after observations
(`PREDECESSOR_STEADY` → `A_PREPARED`, same CURRENT identity and hash, nothing
in RETIRED). Tamper tests change CURRENT before and after the write.

## 7. SW-1 — forward-only custody transitions

| Step | From → to | Allowed |
| --- | --- | --- |
| `PREPARE` | steady(P) → A | before the authority PONR only |
| `ABANDON` | A → steady(P) (destroy PREPARED S) | before the authority PONR only |
| `VACATE` | A → B (rename CURRENT → RETIRED) | after the authority PONR only |
| `INSTALL` | B → C (rename PREPARED → CURRENT) | after the authority PONR only |
| `DESTROY` | C → steady(S) (unlink RETIRED P) | after `S_CURRENT` only (§9) |

`custody_transition_reason` refuses everything else: B → A and C → A are
`PREDECESSOR_RESTORE_FORBIDDEN`; ABANDON after the PONR is
`PREDECESSOR_RESTORE_FORBIDDEN`; VACATE / INSTALL before it are
`AUTHORITY_PONR_NOT_REACHED`; C → B and A → C are undefined.

`authorize_custody_step` is the only entry point for PREPARE, ABANDON,
VACATE, and INSTALL. It requires, together:

- a CONSISTENT verified history (owner-pinned genesis, K-WIT chain,
  re-verified K-ROOT authorizations, K-ROOT registry at every head);
- the authority PONR fact: the witnessed head names the successor current
  (VACATE, INSTALL) or not (PREPARE, ABANDON);
- a bound `HELD` primary hold of the same ceremony, predecessor, and
  successor;
- the exact from-state with exact hashes, same-filesystem proof, and every
  RR-26 fact (`plan_custody_filesystem_step`);
- for PREPARE: P current at the head (ROTATION), or P `COMPROMISED` at the
  head with no current key (KEY_COMPROMISE_RECOVERY, after the marking); and
  an unburned ordinal.

Filesystem contents alone never produce a plan. A plan moves nothing; the
TEST `TempCustody` executor performs exactly the named rename or unlink and
fsyncs each touched directory.

Crash states: a crash in B leaves CURRENT empty; the unit cannot load a
credential and the signer cannot start (fail-safe availability loss).
Recovery is INSTALL (PREPARED → CURRENT) after verifying the expected
successor hash; P is never restored.

## 8. `CeremonyHoldV1` (RR-24, RR-30)

`LILITH_CEREMONY_HOLD` v1. Fields: `protocol`, `schemaVersion`,
`environment`, `ceremonyId`, `transitionKind`, `state`, `reason`,
`expectedPredecessorKeyId`, `expectedSuccessorKeyId`,
`observedWitnessDigest`. No `createdAt`. `authority_granted = False`.

| Closed set | Values |
| --- | --- |
| `state` | `HELD`, `RELEASED` |
| `transitionKind` | `INITIAL_CUSTODY`, `ROTATION`, `KEY_COMPROMISE_RECOVERY` |
| `reason` (SOURCE DETAIL) | `INITIAL_CUSTODY_BOOTSTRAP`, `ROTATION_IN_PROGRESS`, `KEY_COMPROMISE_RECOVERY_IN_PROGRESS` (HELD, by kind); `PREDECESSOR_DESTRUCTION_INCOMPLETE` (HELD, custody debt); `OWNER_RELEASE_AFTER_ELIGIBILITY` (RELEASED) |

Structure (all fail closed; unknown values and versions never parse):
`INITIAL_CUSTODY` is the only kind with `expectedPredecessorKeyId = null`, its
successor is the initial K-ACT, and its ceremony is the deterministic initial
ID. `ROTATION` / `KEY_COMPROMISE_RECOVERY` need a predecessor, a successor
ceremony (or its custody-debt derivative), and a successor equal to the
ordinal's derived keyId (null only while HELD before preparation).

**Lifecycle** (`hold_transition_reason`): missing → HELD → RELEASED only.
Refused: missing → RELEASED, RELEASED → HELD, RELEASED → RELEASED with other
bindings (an identical re-assertion is a no-op), and any HELD rebinding
except filling a null successor once. A new ceremony starts again from HELD.
`missing hold != released`.

**Initial ceremony ID** (SOURCE DETAIL encoding):
`<environment>.initial-custody.<initialKeyId>`, for DEV
`dev.initial-custody.test-only.dev-synthetic.actor.b1b3d.1`.

**Custody-debt ceremony** (SOURCE DETAIL). The design's destruction-failure
rule engages an availability hold after `S_CURRENT`, when the ceremony's own
hold is already RELEASED; RELEASED → HELD is refused for a ceremony. The
availability hold is therefore the one deterministic derivative
`<successorCeremonyId>.custody-debt`, HELD with reason
`PREDECESSOR_DESTRUCTION_INCOMPLETE`. It is still non-authority. Its RELEASED
form passes only once the inventory is STEADY (destruction complete).

## 9. Hold-release eligibility, full readiness, `S_CURRENT`

`evaluate_successor_readiness(inputs, mode)` runs the unchanged Prep A
evaluator with its boolean `hold_present` forced and ignored, keeps every
Prep A check except `CEREMONY_HOLD`, and adds:

| Check | Meaning |
| --- | --- |
| `PUBLICATION_BYTES` | the exact publication bytes the ceremony record binds are the publication the Prep A binding (B3) used |
| `KEY_TRANSITION` | the ladder the verified history shows for the head's current key (§11) |
| `COMPROMISE_EPOCH` | §10 |
| `CEREMONY_PROVENANCE` | INITIAL: the initial publication (CURRENT path), no record. Otherwise: the verified record, naming the head successor, registered once |
| `CEREMONY_HOLD` | a parsed hold bound to exactly this verified state |

| Mode | Hold required | Means |
| --- | --- | --- |
| `HOLD_RELEASE_ELIGIBILITY` | bound `HELD` | every other condition passes; the owner may release. Not readiness |
| `FULL_READINESS` | bound `RELEASED` | issuance readiness; READY here is the independently reproduced `S_CURRENT` |

Hold binding: kind, primary ceremony, predecessor, and successor equal the
derived transition. `observedWitnessDigest` names a verified chain entry:
for a primary HELD hold, an entry before the ceremony's first authority step
(INITIAL: the pinned genesis itself); for RELEASED and for the custody-debt
HELD hold, an entry with the head's exact registry head (later ledger-only
entries allowed). A release record for witness A never passes readiness for
witness B. Order: HELD → eligibility → owner release → RELEASED → full
readiness re-run; full readiness never implies a release.

`S_ACTIVATED != S_CURRENT`: with the successor loaded and reporting its
fingerprint, full readiness still fails while the hold is HELD.

The Prep A `evaluate_witness_readiness` and its boolean input are unchanged
for compatibility; `evaluate_successor_readiness` is the Source Prep B
issuance-readiness entry point and supersedes that boolean (absence never
releases).

## 10. Compromise-epoch rule (§10.3)

`compromise_epoch_reason(history)` returns `COMPROMISE_EPOCH_ADVANCE_REQUIRED`
when the verified history contains an in-epoch head transition that turns the
then-current OWNER_ACTOR issuance key `COMPROMISED`, and the epoch advance
immediately out of that epoch is absent or not a re-verified
`KEY_COMPROMISE` advance. It is recomputed from chain entries, head
registries, and re-verified authorizations on every call; no latch, flag
file, or state owner exists.

Source details that only make the rule stricter:

- it keys on the lifecycle fact, not the reason label, so a K-ROOT registry
  that marks the current key under any reason also triggers it;
- an advance out of that epoch under another reason (for example
  `OPERATOR_RECOVERY`) never clears it.

Proven: a K-ROOT-signed, witness-executed same-epoch successor after the
marking passes every Prep A check and still fails here (`owner signing error
!= valid readiness`). A non-current key's marking is in-epoch only and does
not trigger the rule.

## 11. SW-9 — current-key compromise recovery (RR-22)

`evaluate_compromise_recovery(history, predecessor)` checks the accepted order:
P current at a witnessed head in epoch E → an in-epoch head advance authorized
`COMPROMISE_MARKING` that marks P `COMPROMISED` and names no current key → no
same-epoch head advance naming a successor → the epoch advance out of E
authorized `KEY_COMPROMISE`, naming the successor in E+1.

| Phase | Meaning |
| --- | --- |
| `RECOVERY_NOT_STARTED` | no marking of P (or `WRONG_MARKING_KEY`) |
| `RECOVERY_MARKED` | marking committed; the only C-4 adoption window |
| `RECOVERY_EPOCH_ADVANCED` | `KEY_COMPROMISE` advance committed; the only C-4 quarantine window. Not `S_CURRENT` |
| `RECOVERY_INVALID` | `PREDECESSOR_NEVER_CURRENT`, `MARKING_NOT_CURRENT_KEY`, `SUCCESSOR_BEFORE_MARKING`, `EPOCH_ADVANCE_WITHOUT_MARKING`, `MARKING_REASON_INVALID`, `MARKING_INCLUDES_SUCCESSOR`, `SAME_EPOCH_SUCCESSOR_AFTER_MARKING`, `WRONG_EPOCH_ADVANCE_REASON`, `RECOVERY_SUCCESSOR_INVALID` |

Stale witness heads, skipped or unregistered authorizations, and replays fail
earlier in `verify_history` (`HISTORY_WITNESS_NOT_CONSISTENT` with the Prep A
classification). The two steps are never collapsed: the combined option-B
registry fails `EPOCH_ADVANCE_WITHOUT_MARKING` in the evaluator and in
readiness. Every piece of P evidence stays `KEY_COMPROMISED` under the
unchanged verifier at both the marking and the recovered head (tested).

**`AuthorityKeyTransitionV1` (RR-23).** Implemented only as a derived
readiness output (`LILITH_AUTHORITY_KEY_TRANSITION` v1): kind, predecessor,
successor, ceremony, from/to heads, epochs, and witness digests, the readiness
digest, and `predecessorMaterial` (`NONE`, `RETAINED`,
`DESTROYED_FROM_ACTIVE_CUSTODY`). `authorityGranted: false`,
`authorityProof: false`, no signature root, reproducible from the
authoritative inputs, consumed by nothing that decides authority. Kept because
it gives the crash-matrix and destruction tests one deterministic summary.

## 12. Narrow C-4 recovery gate (RR-28)

`evaluate_recovery_gate` is a pure evaluator for a future signer that still
loads the COMPROMISED P. It is not wired into authority-dev (a test proves no
authority-dev module imports it; the signer still exits without its one
credential). Permitted only if all hold:

- DEV_SYNTHETIC profile (`prod` and any altered profile refused);
- operation in the closed allowlist {`ADVANCE_EPOCH`, `VOID_CHALLENGE`,
  `QUARANTINE_USE`}, the three signer-owned authority-ledger operations of
  C-4 (`synthetic_recovery_ledger`, design PB-13). Everything else is
  `OPERATION_NOT_ALLOWLISTED`: `ISSUE`, `PREPARE`, `CONSUME`, `RESERVE`,
  `CONFIRM`, `ABANDON`, `REGISTRY_VIEW`, every signing request (OwnerEvidence,
  registry, Privacy, generic), admin, and any unknown value;
- a bound HELD `KEY_COMPROMISE_RECOVERY` primary hold naming P;
- a CONSISTENT verified history in which the SW-9 sequence is valid, P is
  `COMPROMISED` at the head, and the head's current key is not P (issuance
  disabled);
- `ADVANCE_EPOCH` only in `RECOVERY_MARKED`, with an EAA that verifies under
  K-ROOT, is `KEY_COMPROMISE`, binds the current head (witness digest,
  version, epoch), is not consumed, and is not already journalled
  (`ADOPTION_ALREADY_JOURNALLED`);
- `VOID_CHALLENGE` / `QUARANTINE_USE` only in `RECOVERY_EPOCH_ADVANCED`.

A permitted result grants nothing: `authorityGranted`, `signingPermitted`,
`issuancePermitted`, `evidenceReservationPermitted` are all false. No
credential-less signer mode was added.

## 13. Predecessor destruction (RR-29, §13)

`verify_destruction_order` permits the one `UNLINK RETIRED` only when:

- `FULL_READINESS` is READY with the RELEASED primary hold, the loaded-key
  binding names S, the head's current key is S, and the derived transition is
  this ceremony; or, for an owner retry after a failure,
  `HOLD_RELEASE_ELIGIBILITY` is READY under the custody-debt HELD hold and the
  ceremony's own RELEASED hold binds the same keys;
- custody is exactly state C with RETIRED = P's hash, and every §6 fact holds.

Otherwise `DESTRUCTION_BEFORE_S_CURRENT`, `DESTRUCTION_CEREMONY_MISMATCH`,
`PREDECESSOR_STILL_CURRENT`, `RELEASED_HOLD_NOT_BOUND`, or
`PREDECESSOR_NOT_RETIRED`. Rollback to P is never permitted.

`evaluate_destruction_evidence` (`LILITH_PREDECESSOR_DESTRUCTION_RECORD` v1,
non-authority) decides `DESTROYED_FROM_ACTIVE_CUSTODY` only with all of: the
RETIRED blob observed before as a `root 0600` regular file with P's hash; the
unlink succeeded; the RETIRED directory fsynced; `lstat` absent afterwards;
inventory STEADY with CURRENT = S. The record binds the `S_CURRENT` readiness
digest and states `mediaZeroization: NOT_CLAIMED`.

**Failure after `S_CURRENT`.** Anything less is `DESTRUCTION_INCOMPLETE`:
`KNOWN_CUSTODY_DEBT`, availability hold required, owner retry required,
`authorityRollbackPermitted: false`, `predecessorRestorePermitted: false`.
`destruction_failure_outcome` returns the custody-debt HELD hold; with it,
full readiness fails closed while the head and S stay authority-current.

Not claimed: media zeroization, journal / filesystem / SSD remanence, page
cache, earlier signer process memory, snapshot or backup copies.

## 14. Unit, single loadable slot, installer (RR-25, RR-26)

Unit: exactly one `LoadCredentialEncrypted=owner-actor-signing-key:<CURRENT>`;
no `LoadCredential`, `SetCredential*`, or `ImportCredential`; no directory or
wildcard source; exactly one `InaccessiblePaths=` line, now also denying
`/etc/lilith-authority-custody` (which covers PREPARED and RETIRED); the
custody root appears in no read or bind path. `systemd-analyze verify` of the
changed unit passes (CI step unchanged). The unit was not started, reloaded,
or installed.

Installer (control tooling, never release payload): new stage `custody`
(ladder `L2c`, after `L2b.2`). It requires the exact L2b.2 POST, creates the
custody root, `prepared/`, and `retired/` `root:root 0700`, fsyncs the custody
root and `/etc`, and never writes, moves, or deletes a blob. Its POST
requires owner and mode, exactly two entries, empty slot directories, and one
filesystem with the credstore. Earlier stages require all three absent. The
`RELEASE_SET` check keeps "exactly one installed release" (RR-25, now the
successor-capable one; no retained executable release for rollback;
`release rollback != authority rollback`). The installer was not executed
against any host.

## 15. New source release identity

| Member | Live `9ac7de2` (installed) | Source Prep B (prepared, not installed) |
| --- | --- | --- |
| `cli/lilith-authority-keygen-dev` | `f1e7020b…d81232` | `f6b21367…3ccd6d2` |
| `assets/lilith-authority-dev.service` | `249f2ec9…b62b1bc` | `192fc3a9…b3bdc88` |
| runtime Python modules and shared contracts | unchanged | unchanged |

The runtime file manifest of this source (SHA-256 of the sorted-key JSON of
`release_file_set.runtime_manifest`, as the new test computes it) is
`f49187c0…4f68c`. By the existing N-45 convention the release
identity `RELEASE_SHA` is the protected-main commit the archive is built from;
it exists only after merge and a separate reviewed build. The live installed
release remains `9ac7de2…` until a separately authorized PR-1 install.

```text
source release prepared != installed release
```

## 16. Crash and failure matrix (tests)

| # | State | Proven outcome |
| --- | --- | --- |
| 1 | hold engaged, nothing prepared | not ready; custody steady; no move |
| 2 | successor prepared, marking/registry absent | S unknown to the head; VACATE refused |
| 3 | candidate registry signed, authorization absent | staged registry is not the head; C-4 adoption refused |
| 4 | EAA exists, ledger adopted, witness not advanced | `LEDGER_EPOCH_AHEAD_OF_WITNESS`; re-adoption refused; the witness executes the same EAA |
| 5 | witness committed new head, custody still P | binding refuses P; P restore forbidden |
| 6 | P → RETIRED, CURRENT empty | nothing loadable; forward INSTALL only; B → A forbidden |
| 7 | S installed, signer not started | no HEALTH → not ready |
| 8 | signer reports P's fingerprint | `HEALTH_FINGERPRINT_MISMATCH` |
| 9 | signer reports S, independent binding fails | `BLOB_HASH_MISMATCH` |
| 10 | `S_CURRENT`, P retained | full readiness READY; destruction permitted |
| 11 | crash during destruction | `KNOWN_CUSTODY_DEBT`; debt hold; head unchanged; no rollback |
| 12 | old snapshot after `S_CURRENT` | credential-only restore: binding refuses. Whole-host restore (chain, pointer, registries, ledger together): **NOT DETECTED** — the restored genesis state reads READY; the nonclaim is pinned by a test |

Rows 6–12 run for both the routine rotation and the SW-9 ladder. The §7.4
keygen refusal matrix, §6 custody refusals, and the design §14 hidden-
assumption cases are covered in the same suites.

## 17. Compatibility

Unchanged: `AuthorityKeyRecordV1`, `AuthorityRegistryV1`, `OwnerEvidenceV2`,
`PrivacyAuthorizationV2`, `RecoveryEpochV1`, `RecoveryWitnessV1`,
`RecoveryWitnessV2`, `EpochAdvanceAuthorizationV1`,
`RegistryHeadAdvanceAuthorizationV1`, the key publication v1, and every
B1b-3a / 3b / 3c / 3e / Prep A golden. No new golden was introduced. Existing
COMPROMISED behaviour is unchanged: all evidence under a COMPROMISED key
rejects `KEY_COMPROMISED`. The durable TEST witness writers still accept only
environment `test`; Source Prep B profiles admit `test` solely as that TEST
stand-in, and every other profile value must equal DEV_SYNTHETIC.

## 18. Tests

| Suite | Result |
| --- | --- |
| `test_b1b3e_source_prep_b.py` (new) | 55 passed |
| `test_successor_custody.py` (new) | 23 passed |
| owner-memory-control, complete | 477 passed (422 before) |
| authority-dev, complete | 108 passed (85 before) |
| both new suites as a non-root user | passed |
| `compileall`, `release_file_set.py`, `systemd-analyze verify`, `validate_repository.py`, `git diff --check` | passed |

Run in WSL from a copy of the tree with the pinned wheels on `PYTHONPATH`;
no dependency was installed into the repository.

## 19. Remaining before any live rehearsal

- **PR-1:** B1b-3d L3a–L4 designed for V2, installed, and accepted, including
  the signer's authority ledger, the runtime wiring of the §12 gate, the live
  `INITIAL_CUSTODY` bootstrap, the reviewed replacement of the installed
  `9ac7de2` release by the successor-capable release under RR-25 (the
  installer's `release` stage still assumes a fresh L1a; the swap is PR-1
  design), the `custody` stage, and adding the custody root to the broker
  preservation verifier's custody path list.
- **PR-2:** the snapshot inventory.
- **PR-3:** the owner's real off-host register and material, including the
  burned-ordinal ceremony register.
- Whole-host rollback remains unresolved. No PROD authority, no Privacy
  custody (B1b-3f), no Stage III, no First Memory.

## 20. Unresolved SOURCE DETAIL (fail closed today)

- Epoch advances for reasons other than `KEY_COMPROMISE`
  (`LEDGER_RESTORE_DETECTED`, `WITNESS_LEDGER_MISMATCH`, `OPERATOR_RECOVERY`)
  have no accepted hold kind: readiness reports
  `TRANSITION_KIND_NOT_SUPPORTED`.
- An in-epoch head advance after `S_CURRENT` that does not change the current
  key (administrative revocation, a non-current marking) moves the registry
  head; the RELEASED hold then no longer binds and cannot be re-released for
  the same ceremony. No accepted ceremony form exists for it yet.
- `PREPARED_ABSENT` is reachable only by a race: the custody-root entry check
  refuses first.

## 21. Nonclaims

This slice does not claim or authorize: a live step; a key; a rotation; a
revocation; an epoch advance; a custody move; an installed or active release;
media zeroization; whole-host rollback protection; real-owner-grade custody;
PROD authority; Privacy custody; Stage III; First Memory; or that any test
result authorizes live entry.

## Explicitly not done

- No DEV or PROD contact; no gcloud, SSH, IAP, sudo, systemctl, or
  systemd-creds against any host; no installer execution against any host.
- No real credential generated; no custody path created on a real host.
- No live registry, witness chain, RecoveryEpoch, authority ledger, broker
  ledger, or L04 touched; no IAM, WIF, or sudoers change.
- No PR opened; nothing merged.
