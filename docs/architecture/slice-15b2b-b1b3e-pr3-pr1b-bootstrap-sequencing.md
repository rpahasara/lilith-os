# Slice 15B2b-B1b-3e PR-3 P3-5: PR-1B Bootstrap Sequencing

**Status: P3-5 SEQUENCING DESIGN + PURE SOURCE.** This is design only.

- PR-1B eligibility is **FALSE** while P3-3 is `P3_3_STORAGE_INCOMPLETE`.
- Real owner freshness remains `FRESHNESS_UNKNOWN`. No real record 1
  exists.
- There was no DEV contact, no cloud contact, and no K-ROOT, K-WIT,
  registry, ledger, witness, hold, RecoveryEpoch, or INITIAL_CUSTODY
  activity. No reboot happened.
- PR-1B, A1–A7, and First Memory are **not authorized**.

| Field | Value |
| --- | --- |
| Refines | the [PR-1 live-install preflight](slice-15b2b-b1b3e-pr1-live-install-preflight.md) §12–§20, §27 (M-B1 … M-B15), §29, §30 |
| Depends on | [PR-3 owner freshness foundation](slice-15b2b-b1b3e-pr3-owner-offhost-foundation.md) (D1–D12, §24 tooling, §25 P3-3, §26 P3-4); [PR-2 acceptance](slice-15b2b-b1b3e-pr2-acceptance.md) |
| Source | `services/owner-memory-control/lilith_owner_memory/pr1b_sequencing.py`: a pure checklist state machine. `sequencer != verifier` |
| Tests | `…/tests/test_b1b3e_pr3_p35_pr1b_sequencing.py` |

The accepted order was broadly correct. This record makes it exact and
places the one step the preflight did not have: **owner freshness record
1**, accepted in two replicas. It does this without creating circular
trust.

```text
PREPARED != SIGNED != PINNED != COMMITTED != ACCEPTED != CURRENT
SIGNED_REGISTRY != EFFECTIVE_CURRENT_REGISTRY
ledger storage exists != GENESIS row exists != authority state accepted
key exists != key custodied != key authoritative
K-ROOT authorization != owner freshness acceptance
propose record 1 != accept record 1
RELEASED != freshness
```

## 1. Preconditions: `PR1B_ELIGIBLE` or `PR1B_NOT_ELIGIBLE`

`evaluate_eligibility` returns `PR1B_ELIGIBLE` only if **every** item
below is literally `True`. Any other value fails, and unknown keys, such
as a synthetic rehearsal result, are reported, never counted.

| Precondition | Failure reason | Today |
| --- | --- | --- |
| P3-3 complete | `P3_3_INCOMPLETE` | **false** |
| two real owner replicas exist | `OWNER_REPLICAS_MISSING` | **false** (only A) |
| both admitted by `init-real-replica` | `OWNER_REPLICAS_NOT_ADMITTED` | A only |
| independence (distinct rollback paths) established | `OWNER_REPLICA_INDEPENDENCE_NOT_ESTABLISHED` | **false** |
| at least one agent-unreachable copy (§25.5 of the PR-3 record) | `OWNER_REPLICA_CUSTODY_NOT_AGENT_EXCLUSIVE` | **false** |
| owner register KNOWN_EMPTY: two replicas, identical, zero records, no divergence | `OWNER_REGISTER_NOT_KNOWN_EMPTY` | not evaluable (one replica) |
| PR-3 source/tooling accepted (reviewed, merged) | `PR3_TOOLING_NOT_ACCEPTED` | owner decision |
| PR-1A `P1A-9` still valid, or freshly re-baselined after any reboot/restart (§12) | `PR1A_BASELINE_NOT_VALID` | valid until a reboot |
| PR-2 inventory revalidated (§13) | `PR2_REVALIDATION_REQUIRED` | must be re-run |
| no unreviewed snapshot/backup/topology change | `PR2_REVALIDATION_REQUIRED` | must be re-run |
| open risks (OR-1…OR-9, DR-3, cross-environment `osAdminLogin`, whole-host rollback) explicitly acknowledged | `OPEN_RISKS_NOT_ACKNOWLEDGED` | owner decision |
| PR-1B explicitly authorized by the owner | `PR1B_NOT_AUTHORIZED` | **false** |

**P3-3 dependency.** P3-5 can complete while P3-3 is incomplete. PR-1B
eligibility stays **FALSE** until P3-3 is complete, and no synthetic
rehearsal overrides that (tested).

## 2. Dependency DAG

Each arrow means "must be complete and verified before". Owner-side steps
are marked ◆. Host writes are marked ▲.

```text
P3-3 COMPLETE ─┐
PR-2 revalidated ─┤
P1A-9 valid ─────┼─► CHECK_ELIGIBILITY (P1B-0)
owner authorization ┘         │
                              ▼
            ◆ GENERATE_K_ROOT (M-B1) ── fingerprint → owner record (E-21)
                              │
                              ▼   (PR-2 revalidated immediately before)
            ▲ GENERATE_K_WIT (M-B2) ── publication → owner fingerprint
                              │
                              ▼
            ◆ SIGN_REGISTRY_V1 (M-B3): E0, K-ACT single current, K-WIT absent
                              │
                              ▼
            ▲ INSTALL_TRUST_AND_REGISTRY (M-B4 + M-B5): root anchor, witness anchor, registry v1
                              │
                              ▼
            ▲ PROVISION_LEDGER (M-B6): sequence 1, owner-computed head
                              │
                              ▼
          ◆▲ PREPARE_GENESIS_CANDIDATE (M-B7): host digest = owner digest (read-only)
                              │
                              ▼
          ◆▲ PIN_GENESIS (M-B8): owner pin off-host (two copies) + on-host copy
                              │
                              ▼
            ▲ START_WITNESS (M-B9a): UNINITIALIZED
                              │
                              ▼
            ▲ COMMIT_WITNESS_GENESIS (M-B9b): exact pinned candidate; committed = pin
                              │
                              ▼
            ◆ APPEND_RECORD_1_REPLICA_A ── FRESHNESS_UNKNOWN (intended)
                              │
                              ▼
            ◆ APPEND_RECORD_1_REPLICA_B ── AUTHENTIC + CURRENT
                              │
                              ▼
            ▲ WRITE_HELD (M-B10) ─► ▲ START_SIGNER (M-B11) ─► EVALUATE_ELIGIBILITY (M-B12)
                                                                  │
                         PR-2 E-20, PR-3 full material ───────────┤
                                                                  ▼
                              ◆ OWNER_ACCEPTANCE (M-B13) ─► ▲ WRITE_RELEASED (M-B14)
                                                                  │
                                                                  ▼
                                                   EVALUATE_FULL_READINESS (M-B15)
                                                                  │
                                         fresh A1–A7 ─► owner acceptance ─► First Memory review
```

**The one-way dependency that removes circularity.**

1. Pre-genesis artifacts (K-ROOT, K-WIT, registry v1, anchors, ledger
   genesis position) never depend on owner freshness. There is no lineage
   yet, and the owner's own off-host records anchor each one.
2. The genesis candidate is a deterministic function of those artifacts.
   The owner pins its digest off-host **before** commit (RR-35).
3. The witness commits exactly the pinned candidate.
4. Record 1 accepts the committed genesis, which must equal the pin.
   Record 1 depends on genesis; genesis never depends on record 1.
5. Everything after record 1 requires `AUTHENTIC` + `CURRENT`.
   `INITIAL_CUSTODY` RELEASED requires CURRENT and creates no freshness.

## 3. Bootstrap state machine

These are `pr1b_sequencing.STEPS`, in order. Every transition requires its
evidence items to be literally `True`, and every one is forward only. The
table's gate column is §10. For crash semantics, see §9.

| # | Action | From → to | Mutation | Required evidence | Writes | Authority meaning | PONR |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 0 | `CHECK_ELIGIBILITY` | PR1B_INELIGIBLE → PR1B_ELIGIBLE | P1B-0 | `EligibilityResultV1` = `PR1B_ELIGIBLE` | none | none | — |
| 1 | `GENERATE_K_ROOT` | → K_ROOT_GENERATED | M-B1 | off-host workstation; fingerprint recorded off-host | owner workstation only | defines the future registry root; authorizes nothing yet | — (discardable before use) |
| 2 | `GENERATE_K_WIT` | → K_WIT_CUSTODIED | M-B2 | PR-2 revalidated immediately before; publication captured; fingerprint recorded off-host; secret scans clean; K-ACT unchanged; K-WIT distinct from K-ACT and K-ROOT | K-WIT blob (RR-36 path) | none | **CUSTODY** |
| 3 | `SIGN_REGISTRY_V1` | → REGISTRY_SIGNED | M-B3 | single-current-key; K-ACT record = publication; K-WIT not in registry; digest recorded off-host | owner workstation only | an authority object exists off-host; not effective | — |
| 4 | `INSTALL_TRUST_AND_REGISTRY` | → TRUST_INSTALLED | M-B4+M-B5 | anchors equal owner copies; witness anchor names K-WIT; registry verifies on-host | anchors, registry bytes | none on host (story 4) | — |
| 5 | `PROVISION_LEDGER` | → LEDGER_PROVISIONED | M-B6 | sequence 1; head = owner-computed; schema fingerprint | `authority_ledger.db` + GENESIS op | a recorded position, not accepted state | — (until genesis) |
| 6 | `PREPARE_GENESIS_CANDIDATE` | → GENESIS_PREPARED | M-B7 | host candidate digest = owner digest | none | none | — |
| 7 | `PIN_GENESIS` | → GENESIS_PINNED | M-B8 | pin stored off-host in two owner copies; on-host copy = off-host; pin = candidate | pin (off-host + on-host copy) | owner anchor for one genesis | **RECORD** |
| 8 | `START_WITNESS` | → WITNESS_STARTED | M-B9a | store UNINITIALIZED; not enabled | the empty state dir | none | — |
| 9 | `COMMIT_WITNESS_GENESIS` | → WITNESS_GENESIS_COMMITTED | M-B9b | pin = candidate; committed = pin; chain = genesis only; recovery CONSISTENT | `chain/1.json`, pointer | lineage anchored (not accepted) | **LINEAGE** |
| 10 | `APPEND_RECORD_1_REPLICA_A` | → OWNER_RECORD_PARTIAL | P3 | chain authentic, genesis only; record 1 binds pin; record 1 witness = committed genesis; owner reviewed; owner confirmed digest; `PEER_PENDING` | record 1 in Replica A | none yet: FRESHNESS_UNKNOWN | **OWNER_RECORD** |
| 11 | `APPEND_RECORD_1_REPLICA_B` | → OWNER_FRESHNESS_CURRENT | P3 | same candidate and digest; `REPLICAS_IDENTICAL`; replicas verified; **classify = AUTHENTIC + CURRENT** | record 1 in Replica B | owner-accepted latest world = genesis | **OWNER_RECORD** |
| 12 | `WRITE_HELD` | → INITIAL_CUSTODY_HELD | M-B10 | hold store empty before; HELD bound to genesis digest | one HELD record | restricts: no issuance | **HOLD** |
| 13 | `START_SIGNER` | → SIGNER_STARTED | M-B11 | HEALTH B4 = B3; NOT_READY with only the hold reason; not enabled | K-ACT loaded (first time) | none | — |
| 14 | `EVALUATE_ELIGIBILITY` | → ELIGIBILITY_READY | M-B12 | eligibility READY; package digest; denial proofs | none | none | — |
| 15 | `OWNER_ACCEPTANCE` | → OWNER_ACCEPTANCE_COMPLETE | M-B13 | owner off-host reproduction equal; decision recorded off-host; PR-2 E-20 accepted; PR-3 full material | owner records | the owner's decision about the package | — |
| 16 | `WRITE_RELEASED` | → INITIAL_CUSTODY_RELEASED | M-B14 | re-run package digest = approved; RELEASED bound to the genesis head | RELEASED record | enables readiness evaluation; creates no freshness | **READINESS** |
| 17 | `EVALUATE_FULL_READINESS` | → FULL_READINESS | M-B15 | FULL_READINESS READY; activation dark; DR-5 + preservation | none | readiness only; issuance stays unwired (RR-39) | — |

**Other sequencer rules.**

- **Out of order.** Any action whose source is not the current state is
  `TRANSITION_OUT_OF_ORDER`.
- **No repeats.** Repeating an action is `REPEATED_IRREVERSIBLE_TRANSITION`
  if it has a PONR, and `REPEATED_TRANSITION` otherwise.
- **Reset.** `reset()` is allowed only while no PONR has been passed.
  Otherwise it returns `REBOOTSTRAP_FORBIDDEN` (RR-40).
- **Halt.** `halt()` enters `BOOTSTRAP_HALTED_MANUAL_RECOVERY`, which is
  terminal. It is used, for example, when the committed genesis ≠ the pin.
- **Authority-changing operations.** They are permitted only at
  `FULL_READINESS` with `AUTHENTIC` + `CURRENT`, and then only through their
  own gates (`authority_changing_permitted`). They are never permitted in
  `OWNER_RECORD_PARTIAL`.

## 4. Key and artifact lifecycles

### 4.1 K-ROOT

| Stage | Where | When | May be effective before record 1? |
| --- | --- | --- | --- |
| ABSENT | — | until step 1 | — |
| GENERATED_OFF_HOST | owner workstation | step 1 | yes (it only exists) |
| FINGERPRINT_RECORDED | owner off-host records (E-21) | step 1 | yes |
| REGISTRY_V1_SIGNED | off-host | step 3 | yes: signed, **not effective** |
| ROOT_ANCHOR_INSTALLED | host `trust/` | step 4 | yes: verification input only |
| GENESIS_BOUND | through the registry head in the witness genesis | step 9 | yes: bound, not accepted |
| TRANSITION_AUTHORIZER | signs registry-head / epoch advances | **only after FULL_READINESS, and only when the presented prior head is CURRENT** | **no** |

K-ROOT signatures authenticate. They never establish which world is
current: `K-ROOT authorization != owner freshness acceptance`.

**Artifacts that may be created before record 1:** K-ROOT, K-WIT, registry
v1, the anchors, the ledger genesis position, the pin, and the witness
genesis.

**Artifacts that may not become effective before record 1:** the registry
as the current registry, the witness head as the latest world, any K-ROOT
transition authorization, HELD, RELEASED, and signer start.

### 4.2 K-WIT

| Stage | Meaning | Step | Before record 1? |
| --- | --- | --- | --- |
| ABSENT | no key | — | — |
| GENERATED | fixed keygen `witness` form created the key on-host | 2 | permitted |
| CUSTODIED | blob `root:root 0600` at the RR-36 path, host-key encrypted | 2 | permitted |
| IDENTITY_PUBLISHED | publication captured; fingerprint in the owner's off-host records | 2 | permitted |
| AVAILABLE_TO_WITNESS | witness anchor installed (step 4) and witness started (step 8) | 4, 8 | permitted |
| GENESIS_SIGNED | signed the pinned genesis candidate | 9 | permitted (the last pre-record stage) |
| ACTIVE_FOR_FRESHNESS | its chain is the owner-accepted lineage | 11 | **only through record 1** |

Key existence is not authority. K-WIT signs only `RecoveryWitnessV2`, and
K-WIT validity is not freshness.

### 4.3 Initial registry

| Stage | Meaning | Step |
| --- | --- | --- |
| DRAFT | built by the owner, off-host | 3 |
| K-ROOT_SIGNED | signature verifies offline | 3 |
| OWNER_REVIEWABLE | bytes installed on-host; digest equal to the owner record | 4 |
| GENESIS_BOUND | `registryVersion` / `registryDigest` in the committed genesis | 9 |
| OWNER_ACCEPTED | record 1 accepts the genesis that binds it | 11 |
| EFFECTIVE_CURRENT | usable for readiness, only at FULL_READINESS with CURRENT freshness | 17 |

A K-ROOT-signed registry **may** exist before owner acceptance (steps 3–10).
It is inert until then:

```text
SIGNED_REGISTRY != EFFECTIVE_CURRENT_REGISTRY
```

### 4.4 Authority ledger

| Stage | Meaning | Step |
| --- | --- | --- |
| ABSENT | no file (`AUTHORITY_STATE_MISSING`) | — |
| STORAGE_AND_GENESIS_ROW | one provisioning transaction creates the directory, the DB, and exactly one `GENESIS` op; there is no state with storage but no genesis row | 5 |
| GENESIS_BOUND | the witness genesis binds `(ledgerSequence = 1, ledgerHead)` | 9 |
| OWNER_ACCEPTED | through record 1 | 11 |
| AUTHORITY_STATE_EFFECTIVE | only at FULL_READINESS | 17 |

Allowed before record 1: exactly sequence 1, the GENESIS op, nothing else.
The first signer start (step 13) journals nothing.

If provisioning is interrupted and leaves a DB without exactly one GENESIS
op, the DB is never adopted (crash C-7).

```text
ledger storage exists != GENESIS row exists != authority state accepted
```

### 4.5 Witness genesis sequence and immutability

| Point | What becomes immutable |
| --- | --- |
| candidate constructed (step 6) | nothing. It is a deterministic function of the registry, epoch E0, policy, ledger head, K-WIT key ID, and the owner-chosen `updatedAt` |
| pin stored (step 7) | the candidate **digest**: any different candidate is a STOP, never a second pin |
| genesis committed (step 9; commit point = the fsync of `chain/`) | the lineage root, the witness head identity (version 1, digest), and the ledger and registry bound into it |
| record 1 accepted (step 11) | the owner's statement that this head is the latest world |

## 5. Genesis pin (PR3-D12)

```text
genesis pin != OwnerAuthorizationRegisterV1 != OwnerFreshnessRecordV1
```

| Question | Answer |
| --- | --- |
| who creates it | the owner, off-host, by independently recomputing the candidate digest from owner-held inputs (registry v1, ledger genesis head, E0, K-WIT key ID, `updatedAt`) |
| what it commits to | `environment` + the genesis `witness_v2_digest` (the signing bytes; the signature is excluded) |
| when it is owner-accepted | when the owner stores it in their two off-host copies, before commit. The copies are kept beside the freshness replicas, never inside them, because a replica admits only `REPLICA.json` and `records/` |
| mutability | immutable. A new pin is an owner re-bootstrap decision, possible only **before** step 9. After step 9 it is forbidden (RR-40) |
| record-1 binding | record 1's `genesisWitnessDigest` and `witnessDigest` must equal the pin. P3-2 `propose-genesis` and `append` re-check this (`GENESIS_PIN_MISMATCH`) |
| candidate differs after pinning | before commit: STOP, and never pin again silently. After commit (committed ≠ pin): `REBOOTSTRAP_FORBIDDEN` → halt, manual recovery design (C-12) |

## 6. Owner freshness record 1

**Exact moment:** immediately after `COMMIT_WITNESS_GENESIS` (step 9), and
before HELD.

**Prerequisites:**

- an authentic K-WIT chain that is exactly genesis, available as a chain
  export;
- the pin matches exactly;
- two real replicas are healthy, admitted, independent, **empty, and
  identical** (KNOWN_EMPTY);
- environment and profile match (`dev` / `DEV_SYNTHETIC`);
- no conflicting bootstrap artifact exists: one genesis, one pin, empty
  hold store, ledger at sequence 1.

`propose record 1 != accept record 1`. Acceptance is the P3-4 ten-step
ceremony (runbook), inside steps 10–11:

1. inspect the authentic bootstrap material (`inspect-chain`);
2. verify the genesis pin against `genesisWitnessDigest`;
3. classify the pre-record state: `FRESHNESS_UNKNOWN`
   (`OWNER_REGISTER_EMPTY`);
4. `propose-genesis`;
5. the owner reviews the exact digest;
6. append Replica A (step 10, `PEER_PENDING`);
7. the system is intentionally `FRESHNESS_UNKNOWN`
   (`REPLICAS_DIVERGENT … PREFIX`), and **no authority-changing operation
   may proceed**;
8. append Replica B (step 11, `REPLICAS_IDENTICAL`);
9. `compare-replicas` returns `OWNER_REGISTER_VERIFIED`;
10. classify: `AUTHENTIC` + `CURRENT`.

**P3-5 source fix.** `load_register` used to report `OWNER_REGISTER_EMPTY`
whenever *any* replica was empty. It now reports:

- `REPLICA_QUORUM_UNMET` below two replicas;
- `OWNER_REGISTER_EMPTY` only when *all* replicas are empty;
- `REPLICAS_DIVERGENT … PREFIX` when some are empty and others are not.

Without this fix, the first-append state could be mistaken for KNOWN_EMPTY.

## 7. INITIAL_CUSTODY

**HELD is placed after record 1 (step 12) and before the signer's first
start (step 13).** This keeps the preflight rule ("after the genesis commit
and pin re-verification, before the signer's first start"). It also:

- makes HELD an ordinary `REQUIRED_CURRENT` write, not a third special case;
- avoids any cycle. Record 1 needs only the committed genesis and the pin;
  HELD needs CURRENT; RELEASED needs HELD, CURRENT, and owner acceptance.
  None of them needs a later one;
- leaves one harmless window, between the genesis commit and HELD. There is
  no hold, freshness is UNKNOWN, and the signer is not started, so
  `missing hold != released` keeps readiness failing (C-13, C-16).

Once HELD exists it is never deleted, recreated, or re-bound (RR-40). A
failed eligibility is a retry of the same HELD ceremony.

**RELEASED prerequisites (step 16):**

- `AUTHENTIC` + `CURRENT` owner freshness, re-classified at write time;
- K-WIT custody verified (E-10);
- registry binding verified (E-13);
- ledger genesis verified (E-15);
- witness genesis verified (E-11) and pin equality (E-12);
- the complete hold set: exactly one HELD, bound to genesis (E-16);
- eligibility READY (E-17);
- the independent owner review package with off-host reproduction (§11);
- no custody debt beyond explicitly bounded, documented
  `KNOWN_CUSTODY_DEBT` (E-20);
- a re-run package digest equal to the approved one.

RELEASED does not create freshness. If the witness has advanced since
record 1, the world is `AHEAD_UNACCEPTED` and RELEASED is blocked until the
owner accepts a new record (D11).

## 8. Points of no return

| PONR | Reversible before | Irreversible after | Recovery if interrupted | Evidence to preserve |
| --- | --- | --- | --- | --- |
| real K-WIT generated (step 2) | nothing exists | private material existed. Destroying the blob burns the key; it never deletes the fact | before M-B4: burn and regenerate (C-3). After: forward only | publication, blob SHA-256, scan results, the burned-key record if any |
| K-ROOT-signed registry v1 (step 3) | draft | the signed object exists (it stays inert until genesis) | install the same bytes (C-5) | registry bytes and digest in owner records |
| owner genesis pin (step 7) | candidate only | the pinned digest: no silent re-pin | re-run the witness commit of the same candidate (C-11) | the pin copies, candidate digest, both reproductions |
| witness genesis committed (step 9) | UNINITIALIZED | the lineage: no second genesis | none: committed ≠ pin → halt (C-12) | `chain/1.json` bytes, digest, pointer, recovery classification |
| owner record 1 accepted (steps 10–11) | an empty register | owner history: no overwrite, and rejection is terminal | append the same candidate to B (C-14); a pending file means manual (C-15) | the candidate file, record bytes, both replica listings, compare result |
| INITIAL_CUSTODY HELD (step 12) | an empty hold store | HELD is never deleted or recreated | retry the same HELD (C-17) | hold listing digest, HELD bytes |
| INITIAL_CUSTODY RELEASED (step 16) | HELD | never returns to HELD | the root observer decides; ambiguous = STOP (C-19) | the approved package digest, re-run digest, RELEASED bytes |
| predecessor destruction (later rotations) | out of scope here | Source Prep B rules | — | — |

## 9. Crash matrix

These are the rows of `pr1b_sequencing.CRASH_MATRIX`, classified as
`SAFE_RETRY`, `RECOVERABLE_INCOMPLETE`, `KNOWN_CUSTODY_DEBT`,
`REBOOTSTRAP_FORBIDDEN`, or `MANUAL_RECOVERY_REQUIRED`.

| Window | Class | Action |
| --- | --- | --- |
| C-1 eligibility checked / K-ROOT absent | SAFE_RETRY | re-check; nothing was written |
| C-2 K-ROOT generated / fingerprint not recorded | SAFE_RETRY | off-host only: discard and regenerate before use |
| C-3 K-WIT generated / publication not captured | MANUAL_RECOVERY_REQUIRED | the identity is unknown: burn the blob, record it, generate a new K-WIT (before M-B4 only) |
| C-4 K-WIT custodied / registry not signed | KNOWN_CUSTODY_DEBT | continue forward; the blob and the host key share the PR-2 snapshot domain (bounded, documented) |
| C-5 registry signed / not installed | RECOVERABLE_INCOMPLETE | install the same bytes |
| C-6 trust installed / ledger absent | RECOVERABLE_INCOMPLETE | provision the ledger |
| C-7 ledger provisioning interrupted | MANUAL_RECOVERY_REQUIRED | a DB without exactly one GENESIS op is never adopted; inspect it, remove the partial DB (before M-B9b only), re-run |
| C-8 ledger provisioned / candidate not prepared | SAFE_RETRY | read-only step |
| C-9 candidate prepared / pin absent | SAFE_RETRY | the owner reproduces and pins |
| C-10 pin stored / witness not started | SAFE_RETRY | start the witness |
| C-11 genesis pinned / witness commit absent | SAFE_RETRY | witness recovery reads UNINITIALIZED; BOOTSTRAP the same candidate |
| C-12 committed genesis ≠ pin | REBOOTSTRAP_FORBIDDEN | STOP; no second genesis (RR-35, RR-40) |
| C-13 witness genesis committed / record 1 absent | RECOVERABLE_INCOMPLETE | propose record 1 against the same genesis; nothing is effective |
| C-14 record 1 in Replica A / Replica B absent | RECOVERABLE_INCOMPLETE | append the same candidate to B; FRESHNESS_UNKNOWN until then |
| C-15 append interrupted (pending file left) | MANUAL_RECOVERY_REQUIRED | `REPLICA_PENDING_WRITE`; the owner inspects; never auto-deleted |
| C-16 record 1 CURRENT / HELD not written | SAFE_RETRY | write HELD (the store is still empty) |
| C-17 HELD / owner package incomplete | RECOVERABLE_INCOMPLETE | correct the condition; re-evaluate the SAME HELD |
| C-18 owner acceptance complete / RELEASED absent | SAFE_RETRY | re-run the package; the digest must match, else the owner reviews again |
| C-19 RELEASED write interrupted | MANUAL_RECOVERY_REQUIRED | the root observer decides HELD vs RELEASED; never re-create; ambiguous = STOP |
| C-20 RELEASED / FULL_READINESS fails | RECOVERABLE_INCOMPLETE | diagnose; RELEASED never returns to HELD |

A whole-host rollback after genesis remains **undetectable on-host** (PR-2;
preflight F-13). The owner register detects it only while at least one
owner copy is newer (P3-4 joint-rollback limitation).

## 10. Freshness-gate placement

| Step | Category | Justification |
| --- | --- | --- |
| 0 `CHECK_ELIGIBILITY`, 1 `GENERATE_K_ROOT`, 3 `SIGN_REGISTRY_V1`, 6 `PREPARE_GENESIS_CANDIDATE` | `NOT_APPLICABLE_PRE_GENESIS` | no lineage exists; off-host or read-only |
| 2 `GENERATE_K_WIT`, 4 `INSTALL_TRUST_AND_REGISTRY`, 5 `PROVISION_LEDGER`, 7 `PIN_GENESIS`, 8 `START_WITNESS` | `REQUIRED_UNKNOWN_BLOCK` | pre-genesis host writes. The register must be KNOWN_EMPTY; any unknown state (missing, divergent, non-empty) blocks |
| 9 `COMMIT_WITNESS_GENESIS` | `BOOTSTRAP_SPECIAL_CASE` | creates the lineage that freshness later accepts, so no record can precede it. Compensating controls: the owner's pre-commit pin, a KNOWN_EMPTY register, committed = pin |
| 10 `APPEND_RECORD_1_REPLICA_A`, 11 `APPEND_RECORD_1_REPLICA_B` | `BOOTSTRAP_SPECIAL_CASE` | the act that creates owner freshness cannot require CURRENT. Compensating controls: P3-2 re-derivation, pin binding, owner digest confirmation, a KNOWN_EMPTY register before A, and step 11 must itself classify CURRENT |
| 12–17 (HELD … FULL_READINESS) | `REQUIRED_CURRENT` | every post-record step, re-classified per step |

There is **no blanket bootstrap bypass**. There are exactly three special
cases, each tested and each justified, and all of them sit in the
genesis/record-1 window. Every later step is `REQUIRED_CURRENT`, and the
sequencer accepts only a real `FreshnessResultV1`, never a boolean
(tested).

## 11. Owner acceptance packages

Both packages are offline and reproducible from owner-held material. Where
possible they do not depend on DEV's claims.

**R1: before accepting record 1 (steps 10–11).**

| # | Evidence | Owner reproduction |
| --- | --- | --- |
| R1-1 | chain export: exactly one entry; K-WIT signature verifies under the owner-held witness anchor | `inspect-chain` with the owner's pinned trust inputs |
| R1-2 | K-WIT fingerprint = the off-host record from step 2; K-WIT not in registry v1 | owner record comparison |
| R1-3 | K-ROOT fingerprint and registry v1 digest = the owner records from steps 1 and 3; `registryDigest` in genesis equals them | recompute `registry_digest` from the owner's bytes |
| R1-4 | ledger genesis head = the owner-computed `H(0^32, genesis op)`; `ledgerSequence = 1` | recompute |
| R1-5 | `witness_v2_digest(genesis)` = the pin = the candidate digest from step 6 | recompute from the owner's inputs |
| R1-6 | environment `dev`, profile `DEV_SYNTHETIC`, E0 | read |
| R1-7 | both replicas: admitted, independent, identical, zero records (`compare-replicas`, `check-independence`, the P3-3 evidence) | run the tool |
| R1-8 | the candidate record: every field equals R1-1…R1-6 | read, then confirm the digest |
| R1-9 | the PR-2 revalidation result from immediately before step 2 is unchanged | owner record |

**RELEASED package (step 15).** It keeps preflight §19 E-1…E-24 unchanged,
and adds:

| # | Evidence |
| --- | --- |
| E-25 | owner freshness classification at package time: `AUTHENTIC` + `CURRENT`, with the register head digest and latest accepted record version |
| E-26 | record 1 bytes and digest; `compare-replicas` = verified; the R1 package digest |
| E-27 | P3-3 storage and independence evidence (public-safe class plus a private evidence digest) |

The canonical package digest covers E-25…E-27. Step 16 re-runs the whole
package and refuses unless the digest is identical.

## 12. Reboot interaction (not authorized)

The pending kernel reboot must happen **before PR-1B**, or not until after
FULL_READINESS. It must never happen inside it. **Recommended: before PR-1B**,
as its own owner-authorized maintenance step, followed by a fresh
read-only re-baseline.

A reboot:

- restarts the memory broker, which ends the accepted broker incarnation
  baseline (`42af2691`), so re-acceptance is required;
- creates the empty `/run/lilith-*` directories (OR-6);
- changes `boot_id`, which PR-1A and PR-2 evidence reference.

The re-baseline after it must re-prove:

- installer `status --expect P1A-9`, including whether OR-6 runtime
  directories are expected;
- CURRENT identity and host-key stat;
- the observer `stableSha256`, with a new expected value;
- broker incarnation re-acceptance and preservation;
- a routine DR-5 proof;
- the needrestart snippet state;
- units inactive and not enabled;
- activation `GRANT_ABSENT`.

A reboot **inside** PR-1B stops at the next gate. Before continuing:
re-prove the above, restart the witness and signer, and re-classify
freshness. Persistent state (genesis, hold, records) is unaffected; the
baseline evidence is not.

## 13. PR-2 revalidation rule

The check is run read-only immediately before `CHECK_ELIGIBILITY`, and
again immediately before `GENERATE_K_WIT`. It covers the same scope as PR-2:

- snapshots and instant snapshots;
- machine images and custom images;
- resource policies and schedules;
- the Backup and DR service state;
- disk list, attachment, and replication;
- the Admin Activity audit method set since the PR-2 window;
- the owner freshness storage topology: replica devices, and any new sync
  or backup relationship.

Any change yields `PR2_REVALIDATION_REQUIRED`, and therefore
`PR1B_NOT_ELIGIBLE`, until a new inventory is accepted.

A snapshot created **after** K-WIT generation holds K-WIT and the host key
together (RR-17). It must be classified before RELEASED (E-20).

P3-5 performed no cloud contact.

## 14. First Memory dependency

```text
PR-1B FULL_READINESS -> fresh A1–A7 design + rehearsal -> owner acceptance of those proofs
                     -> First Memory eligibility review
```

`first_memory_gate` returns `FIRST_MEMORY_BLOCKED` in each of these cases:

- anything before FULL_READINESS (`FULL_READINESS_REQUIRED`);
- freshness not CURRENT;
- A1–A7 not accepted;
- owner acceptance of the A1–A7 proofs missing.

At most it returns `FIRST_MEMORY_REVIEW_ELIGIBLE`. **It never returns an
authorization**, and P3-5 authorizes no First Memory.

## 15. Hidden assumption

> What assumption could make the bootstrap sequence appear safe while it is wrong?

**"If every final artifact is valid, their creation order does not
matter."** Rejected. The order decides authority and recoverability:

1. **Pin after commit:** the pin would be copied from the host it is meant
   to anchor. RR-35 exists because order *is* the security property.
2. **K-WIT before PR-2 revalidation:** a K-WIT created under a host key
   that an unknown snapshot already exposed is contaminated. Every final
   artifact would still verify.
3. **Record 1 before genesis:** impossible without inventing a digest. And
   if the genesis could be created after an owner record, "latest" would be
   defined before the thing it names.
4. **HELD after the signer's first start:** a window in which K-ACT is
   loaded with no hold. The same artifacts, in the wrong order.
5. **RELEASED before CURRENT:** a valid RELEASED record bound to a world the
   owner never accepted as latest.
6. **Ledger after genesis:** the genesis would bind a ledger head that did
   not exist yet (`plan_witness_v2_genesis` requires `ledgerSequence ≥ 1`).
7. **Rejection or recovery by re-creation:** the same final bytes, but a
   destroyed history.

The sequencer therefore enforces order rather than artifact validity
alone. Artifact validity remains the verifiers' job.

## 16. Nonclaims

P3-5 does **not** establish:

- P3-3 completion (**`P3_3_STORAGE_INCOMPLETE`** remains);
- real owner freshness;
- K-ROOT custody;
- K-WIT custody;
- a registry;
- a ledger;
- witness genesis;
- INITIAL_CUSTODY;
- PR-1B eligibility or completion;
- A1–A7 completion;
- First Memory readiness;
- whole-host rollback resistance.

The sequencer is not a verifier. Passing it proves only that
caller-supplied evidence was presented in the required order.

```text
P3-5 SEQUENCING DESIGN ONLY    P3-3 REMAINS STORAGE_INCOMPLETE   REAL FRESHNESS REMAINS UNKNOWN
NO REAL RECORD 1   NO DEV CONTACT   NO CLOUD CONTACT   NO K-ROOT ACTIVITY   NO K-WIT
NO REGISTRY   NO LEDGER   NO WITNESS STATE   NO HOLD   NO RECOVERY EPOCH   NO INITIAL_CUSTODY
NO REBOOT   PR-1B NOT AUTHORIZED   A1-A7 NOT AUTHORIZED   FIRST MEMORY NOT AUTHORIZED
```
