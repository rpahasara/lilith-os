# Slice 15B2b-B1b-3e — Source Prep A: Witness Durability and Readiness

Status:

- **SOURCE IMPLEMENTED / TEST PROVEN** (TEST-only contracts, a TEST-only
  durable writer over an injected storage port, synthetic keys only)
- **LIVE INSTALL ABSENT**
- **LIVE REHEARSAL NOT AUTHORIZED**
- **WHOLE-HOST ROLLBACK UNRESOLVED**
- **REAL AUTHORITY ABSENT**

Base: protected main `29edc5bb603e45b1a0e3c59f68d4e570e88ef7e7`.

This slice implements the source items SW-3, SW-4, SW-5, SW-6, SW-7, and SW-8
of the accepted [live-rehearsal gate](slice-15b2b-b1b3e-live-rehearsal-gate.md)
("the gate") §14. It builds on the merged
[B1b-3e design](slice-15b2b-b1b3e-rotation-revocation-recovery.md) ("the
design") and [source contracts](slice-15b2b-b1b3e-source-contracts.md)
("B1b-3e-S").

Passing these tests does not authorize a live ceremony. The gate's live
entry matrix (§10) still reads **DO NOT ENTER**: SW-1, SW-2, SW-9, PR-1, PR-2,
and PR-3 remain, and every §14 item must also be reviewed and accepted.

Nothing was contacted or changed: no DEV, PROD, gcloud, SSH, IAP, sudo,
systemctl, or systemd-creds; no real key, credential, registry, witness,
ledger, broker, L04, IAM, WIF, or sudoers. No witness genesis was created
and no authorization was retained outside TEST memory or a temporary
directory.

## 1. Location and delivery impact

| Path | Role |
| --- | --- |
| `services/owner-memory-control/lilith_owner_memory/witness_readiness.py` | **new, pure.** SW-3 binding, SW-4 genesis, SW-8 pin, SW-7 register and history re-verification, SW-5 recovery scan, SW-6 inventory, readiness aggregation. Reads no file, holds no key, never produces a signature |
| `services/owner-memory-control/lilith_authority_signer/synthetic_witness_store.py` | **new, TEST-only.** `DurableWitnessV2WriterV1` (RR-9 commit order over `WitnessStoragePortV1`) and `recover_witness_store` (applies the scan; holds no key). No I/O of its own |
| `services/owner-memory-control/tests/synthetic_b1b3e_prep_a.py` | **new.** `SimulatedDurableStorage` (explicit durability model with `crash()`), `TempDirectoryStorage` (real temp directory, POSIX), `DurableScenario`, owner-input builders, golden generator |
| `services/owner-memory-control/tests/test_b1b3e_source_prep_a.py` | **new.** 134 tests |
| `services/owner-memory-control/tests/b1b3e_prep_a_golden.json` | **new.** Golden vectors, SHA-256 pinned in the test |
| `docs/architecture/README.md` | one index row |

**Unchanged:** `rotation_contracts.py`, `recovery_contracts.py`,
`authority_contracts.py`, `authority_verifier.py`, `synthetic_witness_v2.py`,
`synthetic_recovery_ledger.py`, every earlier golden vector (re-checked by
SHA-256), and all of `services/authority-dev/**`, `services/core-api/**`,
`services/memory-broker/**`, workflows, IAM, WIF, and sudoers.

No runtime package (core API, memory broker, scripts, authority-dev) imports
the new modules; a test enforces this. The existing CI step already runs
`unittest discover -s services/owner-memory-control/tests`.

## 2. Controlling records and their exact requirements

| Item | Source | Requirement taken exactly |
| --- | --- | --- |
| GC-3 / SW-3 | gate §2, §14; design §11.2 | the two §11.2 conditions `verify_loaded_key_binding` lacks (SF-8): "the systemd credential name is the fixed name (the embedded name binding)" and "no other `lilith-authority-dev` credential blob is present in the credential store" (via SW-6). Acceptance: negative tests for a second blob and a wrong name |
| GC-4 / SW-4 | gate §2, §14, RR-18 | the live witness starts at `RecoveryWitnessV2` genesis bound to the exact accepted registry head; no V1 live path; bootstrap refused over an existing chain |
| GC-5 / SW-5 | gate §2, §6, RR-9 | the §6.2 commit order including the `chain/` directory fsync; durable retention of authorization bytes; the §6.3 recovery scan; single writer and lock; fault hooks |
| SW-6 | gate §7.2, §14, RR-19 | a root-observed, no-decryption inventory; phase-dependent PREPARED / RETIRED; ownership, type, mode; unexpected blobs absent; never selects the key |
| SW-7 | gate §6.8, RR-20a | independent K-ROOT re-verification of every transition entry, with the owner register and on-host retained copies |
| SW-8 | gate RR-21 | an owner-pinned genesis-digest input to the verifier and to recovery; a second genesis fails `GENESIS_MISMATCH`; a missing pin fails closed |

No material conflict between those records and current source was found.
Section 13 lists the smaller ambiguities and how each was resolved.

## 3. SW-3 — the GC-3 binding conditions

`verify_current_credential_binding` runs the unchanged RR-14
`verify_loaded_key_binding` (B1–B4) first, then adds:

| Input | What it is | Condition |
| --- | --- | --- |
| B5 `UnitCredentialObservationV1` | root-observed credential directives of the signer unit | the unit is `lilith-authority-dev.service`; exactly **one** reference; directive `LoadCredentialEncrypted`; name `owner-actor-signing-key`; source path the CURRENT slot |
| B3 `custodyEvidence.credentialName` | the ceremony publication | equals the fixed name, so the blob was encrypted under it |
| B6 `CredentialInventoryObservationV1` | the RR-19 inventory (§6) | verifies for the phase; the phase is issuance-ready (`STEADY` or `CUTOVER_INSTALLED`); its single CURRENT blob hash equals B2 |

New closed reasons (appended to `BINDING_REASONS`, whose order is kept):
`UNIT_MISMATCH`, `UNIT_CREDENTIAL_REFERENCES_UNEXPECTED`,
`UNIT_CREDENTIAL_DIRECTIVE_UNEXPECTED`, `CREDENTIAL_NAME_MISMATCH`,
`UNIT_CREDENTIAL_PATH_MISMATCH`, `PUBLICATION_CREDENTIAL_NAME_MISMATCH`,
`CREDENTIAL_INVENTORY_NOT_VERIFIED`, `CREDENTIAL_INVENTORY_PHASE_NOT_READY`,
`INVENTORY_CURRENT_BLOB_MISMATCH`. A missing B5 or B6 is
`BINDING_INPUT_MISSING` naming `B5_UNIT_CREDENTIALS` or
`B6_CREDENTIAL_INVENTORY`.

B5 and B6 are story-4 observations. The positive result still reports
`authorityGranted: false`. `credential loaded != current authority`, and
`inventory result != authority`.

**Limit.** The embedded name is not read (that would need decryption). It is
bound indirectly: systemd decrypts an encrypted credential only under the
name embedded at encryption; the ceremony record says which name was used;
and the unit references only that name at only the CURRENT path.

The fixed values are `DEV_SYNTHETIC_SLOT_CONTRACT`. A test pins them against
the current authority-dev profile, keygen, and unit file. The contract module
does not import authority-dev.

## 4. SW-4 — `RecoveryWitnessV2` genesis

`WitnessV2GenesisExpectationV1` holds the owner-accepted bootstrap inputs,
using the accepted V2 field meanings:

- `environment`;
- `registry_head`: `(registryVersion, registryDigest)`;
- `recovery_epoch` (`currentRecoveryEpoch`);
- `policy_version`;
- `ledger_sequence` / `ledger_head`: the authority recovery ledger position.

**Genesis semantics** follow current source:

- `witnessVersion = 1`;
- `previousWitnessDigest = null`;
- `consumedAuthorizationId = null`.

No transition authorization is invented for genesis, and none is consumed.
`genesis creation != permission for a later head transition`.

- `plan_bound_witness_v2_genesis` reuses the B1b-3e-S
  `plan_witness_v2_genesis`: the registry verifies under K-ROOT at its own
  epoch and has a single current key. It then refuses unless every bound
  field equals the expectation.
- `verify_witness_v2_genesis` checks the genesis shape first, then the K-WIT
  signature, then each expectation field, then that the head registry
  verifies at the genesis head with a single current key. A V1 document is
  refused (`UNSUPPORTED_SCHEMA_VERSION`). There is no V1 operation and no
  V1 → V2 migration.
- Reasons, in order: `GENESIS_INPUT_MALFORMED`, `GENESIS_NOT_GENESIS`,
  `GENESIS_WITNESS_UNVERIFIED`, `GENESIS_ENVIRONMENT_MISMATCH`,
  `GENESIS_EPOCH_MISMATCH`, `GENESIS_REGISTRY_VERSION_MISMATCH`,
  `GENESIS_REGISTRY_DIGEST_MISMATCH`, `GENESIS_POLICY_MISMATCH`,
  `GENESIS_LEDGER_POSITION_MISMATCH`, `GENESIS_REGISTRY_UNVERIFIED`,
  `GENESIS_REGISTRY_NOT_SINGLE_CURRENT`.

The TEST writer's `bootstrap` (the owner `BOOTSTRAP`) proceeds only from
`UNINITIALIZED`. That means no chain, no pointer, no scratch, and no retained
authorization. It verifies the signed genesis against the expectation before
it commits. A bootstrap interrupted before its commit point stays
`UNINITIALIZED`.

## 5. SW-8 — the owner genesis pin

`OwnerGenesisPinV1` has exactly these fields: `{pinType, schemaVersion,
environment, genesisWitnessDigest}`.

It is deliberately **unsigned**. The accepted design defines no
authority-bearing contract for the pin, so none is invented. Its integrity
comes from owner custody off-host.

`genesis_pin_reason` passes only when the verified genesis digest equals the
pin. Its reasons are:

- `GENESIS_PIN_MISSING`;
- `GENESIS_PIN_MALFORMED`;
- `GENESIS_PIN_ENVIRONMENT_MISMATCH`;
- `GENESIS_NOT_GENESIS`;
- `GENESIS_MISMATCH`.

What the pin is **not** (each is tested):

- not K-WIT. The digest excludes the signature, so a forged-signature
  genesis still matches the pin. The scan still rejects it (`CHAIN_CORRUPT`);
- not K-ROOT. A pinned chain whose transition has no retained, registered
  authorization is `AUTHORIZATION_HISTORY_INVALID`;
- not permission for a later witness. A pin of a later entry is
  `GENESIS_NOT_GENESIS`;
- not a registry, not a transition authorization, and not an external
  monotonic head. `genesis pinned != external monotonicity`.

The pin anchors the accepted lineage only. It detects a second genesis over
the same anchor. Whole-host rollback **after** genesis stays unresolved.

## 6. SW-6 — credential-slot inventory

`verify_credential_inventory` is a pure verifier over
`CredentialInventoryObservationV1`. Each location is observed by `lstat`,
with no decryption and no link following.

**Logical roles.**

| Role | Content |
| --- | --- |
| `CREDSTORE` | holds the fixed CURRENT slot, the only unit-loadable one |
| `PREPARED` | at most one successor blob |
| `RETIRED` | the predecessor between cutover and retirement |

PREPARED and RETIRED paths, and the successor's embedded name, stay open
details (RR-11-D1, RR-11-D2, SW-2). They are not fixed here.

**Phases**, as gate §11 → (CURRENT, PREPARED, RETIRED):

| Phase | Gate phases | Counts |
| --- | --- | --- |
| `STEADY` | L3e-0..2, and after L3e-12 | (1, 0, 0) |
| `SUCCESSOR_PREPARED` | L3e-3..7 | (1, 1, 0) |
| `CUTOVER_VACATED` | L3e-8a | (0, 1, 1) |
| `CUTOVER_INSTALLED` | L3e-8b..11 | (1, 0, 1) |

Only `STEADY` and `CUTOVER_INSTALLED` can satisfy readiness.

**Fail closed** (closed ordered reasons, `INVENTORY_REASONS`) on any of:

- a missing credstore;
- a location that is not a directory, is not `root:root`, or is not `0700`;
- a non-regular entry (symlink, directory, special file);
- a blob that is not `root:root 0600`, or has an unobserved hash;
- any credstore name other than the CURRENT slot. This covers `.bak`, the
  superseded B1b-3d `…next.cred`, and a second current-looking name;
- CURRENT, PREPARED, or RETIRED counts the phase does not permit, including
  `MULTIPLE_PREPARED_CANDIDATES`;
- the same blob in two slots (`DUPLICATE_CREDENTIAL_BLOB`);
- an unknown or duplicated location role.

The result reports the CURRENT hash for the binding to compare. Its facts
are `authorityGranted: false` and `selectsAuthoritativeKey: false`. A valid
inventory holding the wrong key still fails readiness at the binding
(tested).

## 7. SW-7 — K-ROOT re-verification and retention

### 7.1 Owner register (off-host model)

`OwnerAuthorizationRegisterV1` has two parts:

- `authorizations`: `authorizationId → (kind, SHA-256 of the exact signed
  bytes)`, for every issued authorization, executed or not. A duplicate ID is
  refused (`REGISTER_AUTHORIZATION_ID_DUPLICATED`), so one ID can never map
  to two digests;
- `headRegistries`: every registry head `(version, digest)` that became
  witness-bound, genesis included. One version maps to one digest.

It is provenance evidence and a readiness input. It is not an authority
root. No real off-host storage is built.

### 7.2 On-host retention (TEST writer)

- The retained bytes are the RFC 8785 JCS form of the signed authorization.
  They are stored at `authorizations/<sha256(authorizationId)>.json`.
- The file is written write-once (`O_EXCL`), then the file is fsynced, then
  the directory is fsynced, **before** the chain entry is created.
- `RETAINED != CONSUMED` (owner-accepted). The exact same authorization
  ID, kind, canonical bytes, and digest presented again, after a fault or a
  planner refusal and before any chain entry consumed it, is
  `ALREADY_RETAINED`. No second copy is made; the copy is fsynced again, and
  execution continues if every other check now passes. This is not a replay.
- The same ID with different bytes is refused
  (`RETAINED_AUTHORIZATION_CONFLICT`), and the same ID with a different
  digest or kind in the register is refused
  (`AUTHORIZATION_REGISTER_MISMATCH`). Both refusals repeat on every attempt.
- Once a chain entry has consumed an ID, any later attempt to execute it is
  refused `AUTHORIZATION_CONSUMED` before retention is touched.
- The scan accepts a retained file only if its bytes are canonical and name
  the same ID as the filename; otherwise the result is `RETENTION_CORRUPT`.
- Retained copies are story 4. They count only when their digest equals the
  owner register.

### 7.3 Re-verification

`verify_authorization_history` runs over a verified chain. First, every head
the chain held must be in the register (`HEAD_NOT_REGISTERED`). Then, for
each entry with a non-null `consumedAuthorizationId`, it checks, in order:

1. no replay of an ID within the history (`AUTHORIZATION_REPLAYED`),
   independently of the chain facts;
2. a retained copy exists; the ID is registered; `sha256(bytes)` equals the
   register; the bytes are canonical;
3. the transition type: an epoch change must be an
   `EpochAdvanceAuthorizationV1` registered as `EPOCH_ADVANCE`; otherwise it
   is a `RegistryHeadAdvanceAuthorizationV1`
   (`TRANSITION_TYPE_MISMATCH`);
4. the K-ROOT signature, environment, root key ID, schema, and the contract
   rules (`AUTHORIZATION_NOT_VERIFIED`, with the B1b-3e-S reason as detail);
5. `authorizationId` equals the entry's (`AUTHORIZATION_ID_MISMATCH`);
6. the binding on **both** sides:
   - head advance: prior head = the predecessor entry's head; target = the
     entry's head; `recoveryEpoch` = both entries' epoch;
   - epoch advance: `expectedPriorWitnessVersion` / `Digest` = the
     predecessor entry; prior / successor epoch = the two entries' epochs;
     target = the entry's head;
7. `issuedAt ≤ entry.updatedAt ≤ notAfter`. This is defence in depth only;
   the chain binding is the replay boundary.

`K-WIT assertion != K-ROOT authorization`. A cryptographically valid K-WIT
chain that promotes a staged candidate under a fake ID fails. A verified
authorization with no witness execution never becomes current.

### 7.4 Order for an authority-changing write (TEST writer)

```text
lock -> recovery scan must be CONSISTENT
  -> verify the K-ROOT authorization
  -> owner register names this ID with this kind and this digest
  -> durable write-once retention (create, file fsync, directory fsync)
  -> planner: target registry, succession, prior head / witness, unconsumed, clock
  -> K-WIT signs the planner output; succession re-checked
  -> durable chain commit (section 8)
  -> derived pointer publication
```

A register mismatch is refused before any write. A fault before the
retention is durable leaves no chain operation at all (tested).

## 8. SW-5 — durability algorithm (RR-9 §6.2)

| Step | Operation | Boundary |
| --- | --- | --- |
| 1 | `create_exclusive(chain, "<v>.json", JCS bytes)` | bytes exist, not durable |
| 2 | `fsync_file(chain, "<v>.json")` | contents durable |
| 3 | `fsync_directory(chain)` | **commit point**: entry durable (GC-5) |
| 4 | `write_scratch(".witness.json.tmp")`, `fsync_file` | pointer scratch durable contents |
| 5 | `replace(tmp → witness.json)` | pointer published (not yet durable) |
| 6 | `fsync_directory(state)` | pointer durable; reply |

- A successor is committed only when its bytes are complete, its K-WIT
  signature verifies, its file is fsynced, and `chain/` is fsynced.
- The pointer is byte-identical to the head entry and is derived state
  only. `witness pointer != witness state`.
- Filenames name a version; they never decide order or authority. An entry
  whose content version differs from its filename is INVALID.
- The writer is the sole writer. It holds the store lock (`flock` in the
  temp-directory adapter) and proceeds only from `CONSISTENT`, so a store left
  mid-sequence is never written again until recovery has run.

## 9. SW-5 — recovery algorithm (RR-9 §6.3)

`classify_witness_store` is pure and deterministic. It never uses mtime,
filename order, or "last file wins". It never produces a witness.

```text
R1 DISCOVER  state names ⊆ {chain/, authorizations/, witness.json, .witness.json.tmp, witness.lock};
             regular files only; chain names [1-9][0-9]*.json; retained names <sha256>.json
             -> otherwise UNEXPECTED_ENTRY. Empty chain: nothing else -> UNINITIALIZED; else CHAIN_MISSING
             owner inputs: pin and register present and well formed -> otherwise RECOVERY_INPUT_INVALID
R2 VERIFY    each entry: canonical JCS, V2 K-WIT signature under the anchor, environment,
             witness key not an authority key, filename number == witnessVersion
R3 LINEAGE   genesis 1.json (absent -> ORPHAN; invalid -> CHAIN_CORRUPT); pin -> GENESIS_MISMATCH;
             follow witness_v2_succession_reason; gap or unlinked -> ORPHAN;
             invalid below the top -> CHAIN_CORRUPT; invalid top with pointer == H -> TORN_TAIL
R4 FACTS     witness_v2_chain_facts (replay -> REPLAY_IN_CHAIN); retained copies well formed
             (else RETENTION_CORRUPT); verify_authorization_history -> AUTHORIZATION_HISTORY_INVALID
R5 HEAD      H = the end of the verified lineage
R6 POINTER   == H: CONSISTENT; == H-1: POINTER_BEHIND_BY_ONE; older chain entry: POINTER_BEHIND_MULTI;
             missing: POINTER_MISSING; invalid, or a re-encoding of H / H-1: POINTER_CORRUPT;
             valid at <= H but not in the chain: FORK; valid beyond H: POINTER_AHEAD
             scratch: a chain copy or invalid -> discard; valid <= H not in chain -> FORK;
             valid beyond H -> SCRATCH_ORDERING_VIOLATION
R7 DECIDE    NO_ACTION | ROLL_FORWARD | OWNER_BOOTSTRAP_REQUIRED | FAIL_CLOSED
```

**Automatic** outcomes are only these:

- `CONSISTENT` → no action;
- `POINTER_BEHIND_BY_ONE`, `POINTER_MISSING`, or `POINTER_CORRUPT` → roll
  forward to H;
- discarding scratch.

Every other classification is `FAIL_CLOSED` for the owner.
`UNINITIALIZED` is `OWNER_BOOTSTRAP_REQUIRED`; it is never automatic.

`recover_witness_store` takes no key. For roll-forward it does the following,
in order:

1. `fsync_file` of H;
2. `fsync_directory(chain)`, so a head that is visible but not yet durable
   reaches the commit point before publication;
3. the pointer, by tmp write, fsync, rename, and state-directory fsync.

It never rolls backward, never picks between candidates, and never changes a
chain byte (tested). It is idempotent: a restart at any recovery seam
re-runs it to the same result.

Readiness readers never repair. A stale pointer is `NOT_READY
(WITNESS_POINTER_STALE)`.

**Fault seams** (a TEST hook raising a synthetic exception):

- writer: `BEFORE_RETENTION_CREATE`, `AFTER_RETENTION_WRITE`,
  `AFTER_RETENTION_FILE_FSYNC`, `AFTER_RETENTION_DIRECTORY_FSYNC`,
  `BEFORE_CHAIN_CREATE`, `AFTER_CHAIN_WRITE`, `AFTER_CHAIN_FILE_FSYNC`,
  `AFTER_CHAIN_DIRECTORY_FSYNC`, `AFTER_POINTER_SCRATCH_WRITE`,
  `AFTER_POINTER_SCRATCH_FSYNC`, `AFTER_POINTER_REPLACE`,
  `AFTER_POINTER_DIRECTORY_FSYNC`;
- recovery: `RECOVERY_AFTER_HEAD_FILE_FSYNC`,
  `RECOVERY_AFTER_CHAIN_DIRECTORY_FSYNC`,
  `RECOVERY_AFTER_POINTER_SCRATCH_WRITE`,
  `RECOVERY_AFTER_POINTER_SCRATCH_FSYNC`, `RECOVERY_AFTER_POINTER_REPLACE`,
  `RECOVERY_AFTER_POINTER_DIRECTORY_FSYNC`, `RECOVERY_AFTER_SCRATCH_REMOVE`.

After a simulated crash (`SimulatedDurableStorage.crash()` keeps only what
was fsynced), every seam up to and including `AFTER_CHAIN_FILE_FSYNC`
recovers to the predecessor, and the authorization stays executable. Every
seam from `AFTER_CHAIN_DIRECTORY_FSYNC` onwards recovers forward to the
successor.

## 10. Readiness aggregation

`evaluate_witness_readiness` reports ten checks, each with its own closed
reason:

1. `WITNESS_CHAIN`;
2. `GENESIS_PIN`;
3. `AUTHORIZATION_HISTORY`;
4. `HEAD_REGISTRY`;
5. `REGISTRY_HISTORY` (every head's registry verifies at its entry, and every
   head change is a `verify_registry_succession` step);
6. `SINGLE_CURRENT_KEY`;
7. `AUTHORITY_LEDGER_POSITION`;
8. `CREDENTIAL_INVENTORY`;
9. `LOADED_KEY_BINDING` (GC-3 included);
10. `CEREMONY_HOLD` (unobserved fails closed).

A check that needs a verified head is `NOT_EVALUATED` without one, and that
is itself `NOT_READY`. Every failing check is listed. Nothing collapses into
one boolean, and no condition is dropped because another looks equivalent.

`all readiness checks passing != live-entry authorization`. The facts always
carry `authorityGranted: false`, `liveEntryAuthorized: false`,
`rollbackDetectionScope: LEDGER_ONLY`, and `wholeHostRollbackProtected:
false`.

## 11. Tests

`test_b1b3e_source_prep_a.py` has **134 tests**. With them the
owner-memory-control suite has 422 tests.

| Area | Coverage |
| --- | --- |
| SW-3 | valid; RR-14 still required; each GC-3 input missing; wrong unit; two or zero references; plaintext directive; wrong name; wrong path; blob minted under another name; second credstore blob (`.bak`, `.next`); prepared blob outside its phase; inventory hash ≠ B2; `CUTOVER_INSTALLED` passes and a retained P never binds; RR-14 taxonomy and signature unchanged |
| SW-4 | valid; each expectation field; wrong environment; non-genesis shapes (previous digest, consumed ID, version 2); invalid and rogue signatures; V1 refused; registry missing or not the head; bound planner refusals incl. two current keys; bootstrap refused over existing state and over a pointer-only store; unbound genesis writes nothing; interrupted bootstrap stays `UNINITIALIZED`; genesis is no transition permission |
| SW-8 | exact pass; one-bit mismatch; wrong environment; missing; malformed; later-witness pin; not a K-ROOT substitute; not a K-WIT substitute; second genesis; minimal unsigned shape |
| SW-7 | head and epoch: valid, wrong root, wrong ID, wrong prior / target head, wrong predecessor and successor witness, wrong epoch, expired, not-yet-valid, replay, tampered bytes, register digest mismatch, missing copy, unregistered, same bytes re-encoded, duplicate ID, head not registered, wrong kind, register environment, register missing; K-WIT-only chain fails readiness; unexecuted authorization never current; unregistered and mismatching copies refused before any write; write-once conflict; exact-byte retry after a planner refusal is `ALREADY_RETAINED` and executes with one retained artifact; same ID with other bytes, digest, or kind refused on every attempt; retry after consumption `AUTHORIZATION_CONSUMED` (head and epoch) |
| SW-5 order | full op-log order (retention → chain → directory fsync → pointer); ledger-only retains nothing; retention not durable ⇒ no chain op; plan refusal after retention leaves an executable unexecuted copy; writer refuses non-`CONSISTENT` stores; single-writer lock |
| SW-5 recovery | clean genesis and linear chain; uninitialized; the ten §6.4 cases; pointer missing, empty, garbage, re-encoded; never backward; torn, empty, and corrupt tails; corruption below the head; file fsynced but directory not; contents lost but entry persisted; visible head made durable before publication; pointer ahead; forks via pointer and scratch; registry unavailable (freshness forward, readiness `REGISTRY_MISSING`); authorization unavailable; replay; gaps, unlinked, and headless orphans; missing and corrupt genesis; missing chain; scratch rules; nine unexpected-entry shapes; retention corruption; swapped filenames; no mtime and no listing-order dependence; idempotence; recovery holds no key |
| Fault seams | all 12 writer seams with and without a crash; every recovery seam with a restart; scratch-discard restart; epoch-advance seams |
| SW-6 | the brief's list, plus a full phase × (0..2)³ count matrix, and pinning of the slot contract to the authority-dev profile, keygen, and unit |
| Readiness | all pass with nothing granted; each check failing independently, with its exact dependent set; readers never repair; `NOT_EVALUATED` dependents; multiple failures all reported; prepared phase never ready; whole-host rollback shown undetected |
| Real directory (POSIX) | bootstrap + rotation with directory fsync; fault then recovery; `O_EXCL`; symlink and FIFO refused; `flock` contention |
| Structure / compatibility | pure contract module; the store module does no I/O of its own; not reachable from runtime code; public-material entry points; writer TEST-only and not copyable; earlier goldens and V2 fields unchanged; compromise still retroactive; honest record status |
| Golden | regenerated equals committed; SHA-256 pinned; golden genesis verifies and matches its pin |

## 12. Compatibility

- **Wire and verifier semantics unchanged:** `AuthorityKeyRecordV1`,
  `AuthorityRegistryV1`, `OwnerEvidenceV2`, `PrivacyAuthorizationV2`,
  `RecoveryEpochV1`, `RecoveryWitnessV1`, and `RecoveryWitnessV2`. All
  existing verifiers are also unchanged, including `verify_loaded_key_binding`.
- **New structures** are additive readiness inputs, never authority:
  `WitnessV2GenesisExpectationV1`, `OwnerGenesisPinV1`,
  `OwnerAuthorizationRegisterV1`, `WitnessStoreObservationV1`, the inventory
  observations, and `UnitCredentialObservationV1`.
- **Goldens:** the B1b-3a, B1b-3b, B1b-3c, and B1b-3e goldens are
  byte-identical (SHA-256 re-checked). The authority-dev `SHARED_HASHES` are
  unchanged. One new golden file is added deliberately.
- **Compromise:** C-1 is unchanged. A COMPROMISED issuing key rejects all of
  its evidence as `KEY_COMPROMISED`, whatever the claimed `issuedAt`.

## 13. Ambiguities found and how they were resolved

U-1, U-2, U-5, and U-9 were **owner-accepted** in the pre-PR audit. U-3 was
audited and its retry semantics are pinned (§7.2).

| # | Point | Resolution |
| --- | --- | --- |
| U-1 | The brief's case "valid successor, required registry unavailable → fail closed" vs gate §6.4 "roll forward freshness; readiness `NOT_READY (REGISTRY_MISSING)`" | **OWNER-ACCEPTED.** Recovery may restore the derived pointer to the valid chain head; readiness then fails closed (`HEAD_REGISTRY` and `REGISTRY_HISTORY` = `REGISTRY_MISSING`). Pointer recovery grants no authority: `freshness != authority` |
| U-2 | A head that is visible but not durable, after an in-process fault with no crash | recovery fsyncs the file and `chain/` **before** publishing the pointer. So the entry is claimed committed only once all four commit conditions hold. The writer never returned it, and re-presenting its authorization then fails `AUTHORIZATION_CONSUMED`. After a real crash, the same state recovers to the predecessor. **OWNER-ACCEPTED** as monotonic roll-forward: only for a candidate that is fully present writer bytes, parses, verifies under K-WIT, has unique valid lineage and valid authorization history, with no fork or ambiguity. Recovery never signs, never invents a successor, never rolls backward, and never chooses among candidates; corrupt, truncated, orphaned, forked, or ambiguous candidates fail closed |
| U-3 | The brief's order puts retention before target-registry verification | implemented as ordered. A planner refusal after retention leaves an unexecuted, still-executable retained copy (reported, not fatal). An unreferenced retained file that is unparseable or misnamed is `RETENTION_CORRUPT` (fail closed; the gate is silent, the stricter reading was chosen). **Audited:** an exact retry is `ALREADY_RETAINED` and executes; see §7.2 |
| U-4 | The retained filename | `sha256(authorizationId).json`, because authorization IDs may contain `:`. The name is never authority; the scan checks the ID inside |
| U-5 | §6.8 lists the pinned genesis digest inside the owner register | the pin is one separate SW-8 input, used by both recovery and readiness, rather than a second copy inside the register that could disagree with it. **OWNER-ACCEPTED:** the pin stays a distinct owner-controlled input for lineage genesis anchoring only. A matching pin and a valid K-WIT signature remain separate checks; the witness wire contract is unchanged |
| U-6 | A torn tail when the pointer is not at H | `CHAIN_CORRUPT`. `TORN_TAIL` is used only for "INVALID at H+1, pointer == H" (both fail closed) |
| U-7 | RETIRED at `S_CURRENT` | allowed only in `CUTOVER_INSTALLED`, per gate L3e-10/11. When P is destroyed is SW-1 (not implemented) |
| U-8 | "two valid successors from one predecessor" inside `chain/` | cannot coexist by name (one entry per version, `O_EXCL`). Forks are detected across chain, pointer, and scratch. A copy under another number is INVALID |
| U-9 | SW-4's "DEV_SYNTHETIC V2 witness writer profile" | not built. The writer here is TEST-only (`environment=test`, `test-only.witness.` keys). The genesis contracts are environment-agnostic. A DEV_SYNTHETIC profile and a live adapter belong to PR-1 (B1b-3d L3a–L4). **OWNER-ACCEPTED** |
| U-10 | A wrong-environment genesis | it surfaces as `GENESIS_WITNESS_UNVERIFIED (WITNESS_ENVIRONMENT_MISMATCH)`, because witness verification is environment-bound first; the parsed-level check `GENESIS_ENVIRONMENT_MISMATCH` also exists |

None of these required stopping.

## 14. Remaining before any live rehearsal

- **SW-1** (GC-1 / RR-11): P retained and non-loadable through cutover; its
  destruction only after an independently verified `S_CURRENT`. Not
  implemented.
- **SW-2** (GC-2 / RR-11): the reviewed successor-capable authority-dev
  release, PREPARED-slot keygen, release-set contract, and installer stages.
  Not implemented. **RR-11-D1** (one release vs one per rotation) and
  **RR-11-D2** (the successor's embedded credential name) stay open. No
  successor path was invented here.
- **SW-9** (RR-6 / RR-16): the current-key compromise recovery path,
  `CeremonyHoldV1`, and `AuthorityKeyTransitionV1`. Not implemented.
- **PR-1**: B1b-3d L3a–L4 designed for V2, implemented, live, and accepted.
  This includes a real witness service and storage adapter at V2 genesis.
- **PR-2**: a complete snapshot inventory (RR-17).
- **PR-3**: the owner's real off-host register and pinned genesis digest,
  before the first live K-ROOT authorization.
- Review and acceptance of this slice.

**Whole-host rollback remains unresolved.** A chain, pointer, registry, and
authority recovery ledger restored together are `CONSISTENT` at an old head
(tested). The same-host witness protects only while it survives.

## 15. Nonclaims

This slice does not claim, create, or authorize any of the following:

- a live witness, witness service, genesis, pin, register, retention, or
  storage adapter;
- a live rotation, revocation, epoch advance, or restore;
- any DEV or PROD contact;
- any real key, credential, registry, witness, or ledger;
- signer activation;
- real-owner-grade custody;
- PROD authority;
- First Memory;
- Privacy custody;
- Stage III;
- zeroization;
- proof-of-possession (RR-14a);
- reading an embedded credential name without decryption;
- external monotonicity from the pin;
- whole-host rollback protection;
- that source tests passing opens the live-entry gate.

## Explicitly not done

- No DEV or PROD contact. No gcloud, SSH, IAP, sudo, systemctl, or
  systemd-creds.
- `/etc/credstore.encrypted` and `/var/lib/lilith-authority-dev` were not
  inspected or changed.
- No key or credential was generated, rotated, or revoked. No live witness,
  epoch, registry, authority ledger, broker ledger, or L04 was touched.
- No IAM, WIF, or sudoers change. No Stage III retry. No First Memory.
- No authority-dev runtime, release, keygen, or unit change. No workflow
  change.
- No PR was opened.
