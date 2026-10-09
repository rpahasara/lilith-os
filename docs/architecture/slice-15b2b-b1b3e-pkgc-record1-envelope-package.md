# Slice 15B2b-B1b-3e — Package C: Record 1 (Replica A, Replica B) + Acceptance Envelope 1 (Copies A, B) (Design, Tooling and Runbook)

Status:

- **REPOSITORY ONLY: DESIGN, DOCUMENTATION, A THIN OPERATOR, A PHONE SCRIPT AND TESTS.** The owner authorized the
  Package C design slice only (2026-10-09), and the owner's review of PR #176 revised it (v2, §18). Writing this slice
  contacted no live system: no DEV, no S25, no replica, no acceptance store and no owner key. **No live Package C
  step has run.**
- Packages the four owner-record steps of the accepted bootstrap (P3-5 steps 10, 11, 11a and 11b) into one
  owner-attended sequence of **six owner acts**: **C1 → C2 → C3 → C4A → C4B → C5** (§2). Each of the four
  owner-record acts (C2, C3, C4A, C4B) is a canonical owner-state write with its own go, attempt marker and point of
  no return.
- **Nothing is authorized by this record.** `APPEND_RECORD_1_REPLICA_A`, `APPEND_RECORD_1_REPLICA_B`,
  `APPEND_ENVELOPE_1_COPY_A`, `APPEND_ENVELOPE_1_COPY_B`, every owner-record write, every S25 mutation, every live
  DEV mutation, M-B10 HELD, signer start, authority activation, First Memory and PROD remain **NOT AUTHORIZED**.
  `FRESHNESS=UNKNOWN`.
- Predecessors: [Package B completion](slice-15b2b-b1b3e-mb9-package-b-completion.md) (`WITNESS_GENESIS = COMMITTED
  / IRREVERSIBLE`, genesis `ac892dc2…65e4`) and the [first post-Package-B-freeze deploy](slice-15b2b-b1b3e-mb9-first-post-package-b-deploy.md)
  (`EQUAL / OWNER-ACCEPTED`, host phase `W9_5_GENESIS_COMMITTED_EXACT`).

```text
binding != record 1;  record 1 on Replica A != freshness CURRENT;  AUTHENTIC + CURRENT != acceptance evidence
fresh acquisition = a receipt-bound read in this sequence != a new directory != identical bytes
peer view = NON-CUSTODY read-only comparison input != replica != acceptance store
envelope copy A (C4A) != envelope copy B (C4B);  acceptance envelope complete != HELD != signer != authority
operator != writer: only owner_freshness_tool append / append-envelope / init-acceptance-store write, run by the owner
```

## 1. Canonical sources (unchanged by this slice)

| Source | Governs |
| --- | --- |
| [P3-5 bootstrap sequencing](slice-15b2b-b1b3e-pr3-pr1b-bootstrap-sequencing.md) §2–§11 | the order (steps 10, 11, 11a, 11b), evidence per step, PONRs, crash windows C-13 … C-16b, freshness gates (10/11 `BOOTSTRAP_SPECIAL_CASE`, 11a/11b `REQUIRED_CURRENT`), the R1 package, D12 |
| [P3-6 acceptance envelope](slice-15b2b-b1b3e-pr3-owner-acceptance-envelope.md) §1–§10 | the envelope contract, the review package, chaining, the storage layout, the 13-step ceremony, acceptance states |
| [Owner ceremony runbook](slice-15b2b-b1b3e-pr3-owner-ceremony-runbook.md) | the ten owner-freshness ceremony steps, the "Never" list |
| [B-3 real acceptance](slice-15b2b-b1b3e-b3-real-acceptance.md) | `REAL_ACCEPTANCE_ENABLED = True`; burned rehearsal identities refused |
| [P3-3B Replica B ceremony](slice-15b2b-b1b3e-pr3-p33b-replica-b-ceremony.md) (with its erratum) | the S25 transport (MTP only), the G0 `cryptography` gate, the canonical Replica B path `$HOME/lilith-owner-offline-dev-synthetic-01` |
| [Package B](slice-15b2b-b1b3e-mb9-witness-genesis-package.md) §6.1, §8, §9, OD-B10 | the W9 phases, the read-only `host` and `chain-export` forms, the owner offline verification |
| code: `owner_freshness_tool.py` (SHA-256 `fd7abe2a…7c27`), `owner_freshness.py`, `owner_acceptance.py`, `pr1b_sequencing.py`, `mb9_operator.py` (`066fc821…3973`) | **unchanged**: what writes, classifies and reads DEV |

Accepted identities Package C binds (Package A and Package B records), re-proven fresh in every sequence:

| Item | Value |
| --- | --- |
| committed witness genesis | `ac892dc2b14ca7db108400258abfcf2320ff498f2a674058058e16a8a6fb65e4` (= pin = Package A candidate) |
| `chain/1.json` = `witness.json` | SHA-256 `252c32204bebf3fa1ca0981d8791115e2abb6cd8ddb0925285c64213317cfb99` |
| owner installables | Registry V1 `46b0bfc5…8b1e`, registry root `bc5f00a7…f687`, witness anchor `be360da2…ab5a` |
| P-A / P-B owner pin record | `genesis-pin.json` `35747736…a590`, `authorization-register.json` `8d5ab875…5575`, `pin-record.json` `009a0596…e0ae` |
| accepted witness incarnation | InvocationID `5136ea7af2544450b9370fa412786c98`, MainPID `143946`, NRestarts 0 |
| Replica A | `owner-primary-dev-synthetic-01` (laptop WSL) |
| Replica B | `owner-offline-dev-synthetic-01` at `$HOME/lilith-owner-offline-dev-synthetic-01` (S25 Termux), `REPLICA.json` `c068e533…07c4` |
| environment / profile | `dev` / `DEV_SYNTHETIC` |

## 2. Package C state machine: C1 → C2 → C3 → C4A → C4B → C5

`pkgc_operator.PackageCSequenceV1` (pure, forward only). Freshness and acceptance enter only as the real
`FreshnessResultV1` / `AcceptanceResultV1`, never a boolean (tested).

```text
PC0_NOT_OPENED
 --C1 (verbatim, read-only)------------------------------------------------> PC1_OPENED_READ_ONLY
 --fresh acquisition + binding + S25 C1 transcription + KNOWN_EMPTY--------> PC1_BOUND_KNOWN_EMPTY
 --gate C2 + C2 go (marker C2)---------------------------------------------> PC2_ARMED
 --observe: A = [record 1], B = [], FRESHNESS_UNKNOWN----------------------> PC2_RECORD1_A_PARTIAL      step 10
 --gate C3 + C3 go (marker C3)---------------------------------------------> PC3_ARMED
 --observe: S25 transcription exact, A = B, AUTHENTIC + CURRENT------------> PC3_RECORD1_CURRENT        step 11
 --gate C4A + C4A go (marker C4A; CURRENT re-checked)----------------------> PC4A_ARMED
 --observe copy A: CURRENT + ACCEPTANCE_PARTIAL----------------------------> PC4A_ENVELOPE_A_PARTIAL    step 11a
 --gate C4B; fresh C4B read (copy A exact, copy B absent, exactly PARTIAL);
   C4B go (marker C4B)-----------------------------------------------------> PC4B_ARMED
 --observe copy B: transcription exact + CURRENT + ACCEPTANCE_COMPLETE-----> PC4B_ENVELOPE_COMPLETE     step 11b
 --gate C5 + C5 (verbatim)-------------------------------------------------> PC5_PACKAGE_C_ACCEPTED (terminal)
any state:  HALT event      --> PC_HALT_MANUAL_RECOVERY (terminal)
            REVALIDATE event --> the SAME state; a fresh gate (and, after a consumed marker, a new go) is required
PC1*:       owner pre-C2 stop --> PC_STOPPED_BEFORE_OWNER_RECORD
```

The accepted bootstrap mapping is preserved exactly (`BOOTSTRAP_STEP`, tested). C2 is step 10
`APPEND_RECORD_1_REPLICA_A`, C3 is step 11 `APPEND_RECORD_1_REPLICA_B`, **C4A is step 11a
`APPEND_ENVELOPE_1_COPY_A`** and **C4B is step 11b `APPEND_ENVELOPE_1_COPY_B`**. The next P3-5 step after C4B,
`WRITE_HELD`, is **not** Package C.

| Act | Boundary | Writes | Requires | Ends at |
| --- | --- | --- | --- | --- |
| **C1** open (read-only only) | opens the sequence (a fresh `sequenceId`) and the Package C freeze | the operator work directory; the S25 staging/evidence directory | pins exact at the control; opening facts (control, last DEV deploy run) | `PC1_BOUND_KNOWN_EMPTY` after one fresh acquisition (§3.1), the binding (§3), the bundle transfer and the S25 C1 transcription |
| **C2** go | step 10, one attempt | **Replica A record 1** (canonical `append`, owner-typed digest) | fresh gate C2 (§7); candidate re-derived; review package built *before* the append; peer = the proven empty B view | `PC2_RECORD1_A_PARTIAL`, `FRESHNESS_UNKNOWN` |
| **C3** go | step 11 on the S25, one attempt, owner-run in Termux | **Replica B record 1** (canonical `append`) | fresh gate C3; T2 (Replica A view) verified on the phone; the phone re-derives the same candidate digest | `PC3_RECORD1_CURRENT`: AUTHENTIC + CURRENT, acceptance `NOT_PRESENT` |
| **C4A** go | step 11a on the laptop, one attempt | store A initialization, then **envelope 1 in store A** (canonical `append-envelope`) | fresh gate C4A; AUTHENTIC + CURRENT; the envelope digest bound in the go; peer = the proven empty store-B view | `PC4A_ENVELOPE_A_PARTIAL`: `ACCEPTANCE_PARTIAL` |
| **C4B** go | step 11b on the S25, one attempt, owner-run in Termux | store B initialization, then **envelope 1 in store B** | fresh gate C4B, then the **C4B eligibility read after that gate** (§2.1); the same envelope digest; T3 (store-A view) verified on the phone | `PC4B_ENVELOPE_COMPLETE`: `ACCEPTANCE_COMPLETE` |
| **C5** acceptance | Package C acceptance; ends the freeze | the C5 record in the work directory only | fresh gate C5; CURRENT + `ACCEPTANCE_COMPLETE` | `PC5_PACKAGE_C_ACCEPTED`; authorizes nothing |

No act implies the next. Every arm requires its own fresh gate, and a gate never carries over to the next act
(tested). C4A's go explicitly does not authorize C4B.

### 2.1 C4B eligibility (`pkgc_operator.py c4b-eligibility`)

C4B is eligible only after a **fresh read** proves **exactly `ACCEPTANCE_PARTIAL`, with copy A exact and copy B
absent**. That read happens **after** the last exact C4B gate, and it is voided by a new gate or by any drift
(tested):

1. **The S25 `C4B_PRE` read** (`pkgc_c4b_pre`, read-only, no marker, no write). Its transcription is recorded bound to
   the C4B gate it follows (`afterGateSha256`). It shows Replica B = exactly record 1, AUTHENTIC + CURRENT on the
   phone, and **`ACCEPTANCE_STORE_B=ABSENT`**. `PRESENT` is never exact, so the C4B go is never issued over an
   existing copy B (tested).
2. **Copy A exact:** store A holds exactly envelope 1, whose digest is the one the C4A go bound.
3. **Exactly `ACCEPTANCE_PARTIAL` and CURRENT** on the laptop, computed through **proven** peer views only (§5).

`C4B_ELIGIBILITY.json` binds the gate hash, the envelope digest, store A's tree digest and the states. The C4B go
binds the eligibility hash. If store A changes after eligibility, the C4B arm refuses
(`STORE_A_CHANGED_SINCE_ELIGIBILITY`). In the state machine, `c4b_eligibility` with copy B present, or with any
state other than exactly PARTIAL, is a HALT (`ACCEPTANCE_CONFLICTING`): a second copy-B write is never attempted.

## 3. Canonical chain-export binding (`pkgc_operator.py bind`)

**Why it exists.** The canonical tool needs a trust-input document (`LILITH_OWNER_FRESHNESS_TRUST_INPUTS`) and a
chain-export JSON array. Neither exists as an accepted artifact. Package B exported only the raw `chain/1.json` /
`witness.json` bytes (evidence only, OD-B10), and `mb9_owner_genesis_verify.py` deliberately did not use the tool's
input format. A hand-assembled trust document would be an unreviewed authority input. `bind` makes both inputs a
deterministic function of accepted bytes plus one fresh acquisition.

**Inputs (all read-only):** one **fresh acquisition** (§3.1); the owner-held installables
(`authority-registry.v1.json`, `registry-root.json`, `witness-anchor.json`), exactly those three, each hashing to its
accepted pin; P-A, exactly the three Package A files, each hashing to its pin, with the pin parsing as
`OwnerGenesisPinV1` (`dev`, `ac892dc2…`); Replica A (read-only, at an explicit path outside the work directory); and
the SHA-256 of the two owner-held R1 evidence documents (`PR2_REVALIDATION`, the fresh C1 read-only cloud capture;
`P3_3_INDEPENDENCE`, the accepted P3-3 evidence).

**Exactness of the acquisition (`check_export`):** host and chain-export W9 phase **`W9_5_GENESIS_COMMITTED_EXACT`**,
`w9verifier` exit 0 with empty stderr and no failures, every `evidence9b` item true, committed digest = the accepted
genesis, `chain-1.json` SHA-256 = `252c3220…`, pointer = genesis bytes, the accepted incarnation, `NRestarts` exactly
`"0"` (unknown is not zero), a known boot id, `REBOOT_REQUIRED=absent`, hold store `[]`, no signer later state,
`registryEffective = false`, `authorityActive = authorityGranted = false`.

**Outputs (create-only, `<workdir>/binding/`):**

| File | Content | Rule |
| --- | --- | --- |
| `trust-inputs.json` | RFC 8785 `{trustType, schemaVersion 1, environment dev, witnessAnchor, registryRoot, registries: [Registry V1]}` | the installable documents verbatim as parsed; nothing invented |
| `chain-export.json` | RFC 8785 `[<chain/1.json document>]` | genesis only |
| `genesis-pin.json` | the P-A pin bytes, unchanged | `35747736…` |
| `BINDING.json` | the sequence id, every input hash, the acquisition and its receipt hash, every output hash, the W9/host snapshot (including the boot id), Replica A's listing and manifest hash, the R1 evidence digests, the canonical tool's own view | `load_binding` re-hashes every output on every use (`BINDING_OUTPUT_CHANGED`) |

Before writing `BINDING.json`, the operator runs the **canonical tool's own read** (`load_trust`, `inspect_chain`) on
the outputs. It requires AUTHENTIC, one entry, genesis = head = the pin, and no consumed authorization. The binding is
deterministic: two bindings over the same accepted bytes are byte-identical (tested).

### 3.1 Export-acquisition freshness rule (OD-C6, revised)

The genesis is immutable, so the exported bytes of two fresh reads are **legitimately identical**. Freshness is
therefore **never** "a new directory" and never "the right bytes". A fresh acquisition is **one read of the
presented DEV world performed by `pkgc_operator.py acquire` in this Package C sequence**, evidenced by a per-read
acquisition receipt:

1. `acquire` writes `acquisitions/<NN>-<acquisitionId>.started.json` create-only. It contains the sequence id, a new
   random `acquisitionId`, the index and the `startedAt` time.
2. It runs exactly the two **pinned read-only** `mb9_operator.py` forms (SHA-256 checked before launch):
   `host <repo> <mb9-workdir> <export>/host POST9B` and `chain-export <repo> <mb9-workdir> <export>/chain`, into the NEW
   directory `exports/<NN>-<acquisitionId>/`. No other form can be reached (tested).
3. It writes `exports/<NN>-<acquisitionId>/ACQUISITION.json` create-only, binding at minimum:

   | Receipt field | Content |
   | --- | --- |
   | `sequenceId`, `acquisitionId`, `index` | this Package C sequence (the C1 record) and this read |
   | `startedAt`, `completedAt` | the acquisition timestamps (owner workstation UTC); the host's own `date -u` is also recorded (`devDate`) |
   | `control`, `operatorSha256`, `toolPins` | the control commit and the relevant tool pins (`owner_freshness_tool`, `mb9_operator`, the W9 verifier, the owner genesis verifier) |
   | `commands` | each form, its arguments, its exit code, the SHA-256 of its stdout and its parsed result (`MB9_HOST_POST9B_PASS`, `MB9_CHAIN_EXPORTED`): the deterministic receipt of the acquisition command and result |
   | `facts` | W9 phase (chain export and host) `W9_5_GENESIS_COMMITTED_EXACT`; witness `InvocationID`, `MainPID`, `NRestarts`; boot id and `REBOOT_REQUIRED` state; committed genesis digest; `chain/1.json` SHA-256 |
   | `artifacts` | the SHA-256 of every exported file |
4. It writes `acquisitions/<NN>-<acquisitionId>.completed.json`, binding the receipt's SHA-256.

`verify_acquisition` accepts an export only if **every** clause holds (tested clause by clause):

- the directory is directly under this sequence's `exports/`;
- the receipt names this sequence, and both log entries exist, name this sequence and this acquisition, and
  `completed.receiptSha256` = SHA-256(receipt);
- the timestamps are well-formed, no earlier than the C1 opening, and in order (`startedAt` ≤ `completedAt`, not
  before any earlier acquisition);
- the control and the tool pins are the current ones;
- both commands exited 0 with the exact expected results;
- the artifacts listing equals the files exactly;
- the facts re-derived from the artifact bytes equal the receipt's facts.

Each acquisition is consumed by exactly one binding or gate (`EXPORT_REUSED`).

```text
an old export copied into a newly created directory   -> ACQUISITION_NOT_FRESH:NOT_IN_SEQUENCE_LOG
a bare historical export (e.g. Package B POST9B)      -> ACQUISITION_NOT_FRESH:NO_RECEIPT
another sequence's export, even with its log entries  -> ACQUISITION_NOT_FRESH:sequenceBound
any artifact or receipt edited after the read         -> ACQUISITION_NOT_FRESH:artifactsExact / receiptLogged
a failed or inexact read                              -> ACQUISITION_NOT_FRESH:commandsExact
```

At a gate, a non-fresh acquisition is `ACQUISITION_NOT_FRESH`, a REVALIDATE that never passes (tested). As for every
owner-side record, this protects against mistakes and stale inputs, not against a hostile process running as the
owner. That protection is custody (D6).

## 4. Points of no return

| PONR | Before | After | Recovery if interrupted |
| --- | --- | --- | --- |
| a C2 / C3 / C4A / C4B attempt marker (operator `arm`; phone `set -C` marker) | the go is unused | that go is consumed; whether the write happened is decided only by reading the copies | read-only classification (§7.3); never a second run under the same go |
| **record 1 in Replica A** (C2, step 10) | the register is KNOWN_EMPTY | owner history exists: never overwritten, removed or re-proposed | C-14: the same candidate to B (new C3 go); a pending file is C-15 manual |
| **record 1 in Replica B** (C3, step 11) | the partial state | AUTHENTIC + CURRENT for genesis | — (forward only) |
| **envelope 1 in store A** (C4A, step 11a) | `ACCEPTANCE_NOT_PRESENT` | acceptance history exists | C-16a: the same envelope to store B (new C4B gate, eligibility, go) |
| **envelope 1 in store B** (C4B, step 11b) | `ACCEPTANCE_PARTIAL` | `ACCEPTANCE_COMPLETE` | — |

`reset()` is refused from `PC2_ARMED` onward (`OWNER_RECORD_PONR_PASSED`, tested). An armed state already counts,
because the marker exists before the write.

## 5. Peer views (OD-C2): explicit, tested invariants

The canonical `append` and `append-envelope` read the target **and** the peer copy on one machine, and
`classify` / `compare-replicas` / `propose-envelope` read both replicas. Replica A never leaves the laptop, Replica B
never leaves the S25, and no SSH, ADB or sync exists between them (D6). Package C therefore uses **peer views**:

| View | Where | Built from | Stands for | Bound to (provenance) |
| --- | --- | --- | --- | --- |
| `replica-b-0` | `<workdir>/views/` (laptop) | the pinned Replica B manifest bytes, empty `records/` | Replica B before C3 | the exact S25 **C1** transcription (manifest `c068e533…`, `REPLICA_B_RECORDS=0`) |
| `replica-b-1` | `<workdir>/views/` | the pinned manifest + Replica A's record-1 bytes, which must equal the C2 go's record | Replica B after C3 | the exact S25 **C3** transcription (`REPLICA_B_FILE`, `REPLICA_B_HEAD`, `REPLICATION=REPLICAS_IDENTICAL`) + Replica A's tree |
| `store-b-0` | `<workdir>/views/` | the store-B manifest (`custodyCopyId = owner-offline-dev-synthetic-01`), empty | store B before C4B | the exact S25 **C3** transcription (`ACCEPTANCE_STORE_B=ABSENT`) |
| `store-b-1` | `<workdir>/views/` | the store-B manifest + store A's bundle bytes, which must equal the C4A go's envelope | store B after C4B | the exact S25 **C4B** transcription (`STORE_B_MANIFEST_SHA256`, `ENVELOPE_DIGEST`, `COPIES_IDENTICAL`) + store A's tree |
| A view (T2) | S25 `$HOME/lilith-pkgc/views/a/…` | a byte copy of Replica A after C2 | Replica A | transfer record (tar SHA-256, tree digest, the C2 record digest); typed tar hash, `SHA256SUMS`, transcribed `A_VIEW_TREE_SHA256` |
| store-A view (T3) | S25 `$HOME/lilith-pkgc/views/s/…` | a byte copy of store A after C4A, plus the review package | store A | transfer record (tar SHA-256, tree digest, the C4A envelope digest); `A_STORE_VIEW_TREE_SHA256` |

**Invariants (each tested):**

1. **NON-CUSTODY.** Every view and transfer record is labelled `NON_CUSTODY_PEER_VIEW`. A view is a read-only
   comparison input only, never a replica or acceptance store of custody, and is never copied into one. Copying
   between replicas by any means other than `append` stays forbidden.
2. **Never under a canonical root.** Laptop views live only at `<workdir>/views/<kind>`, at a fixed path with no free
   output argument. The work directory is refused if it is at or under a replica or acceptance-store root
   (`WORKDIR_UNDER_CUSTODY_ROOT`). Every canonical path is refused if it is inside the work directory
   (`CANONICAL_COPY_INSIDE_WORKDIR`). Phone views live only under `$HOME/lilith-pkgc/views`.
3. **Never discovered or counted.** The operator never enumerates directories to find replicas or stores. Canonical
   copies come only from explicit paths, and directory enumeration is limited to operator-owned directories and
   copies being hashed (AST-tested). The register is read (`load_register`, `classify_acceptance_state`) only in
   `laptop_freshness` and `laptop_acceptance`, and only with a proven view.
4. **A view never makes anything current by existing.** `laptop_freshness` / `laptop_acceptance` count a view only
   when its provenance verifies: the view's tree digest is unchanged, and the bound S25 transcription record is
   unchanged and exact. Otherwise the result is `FRESHNESS_UNKNOWN` / `ACCEPTANCE_UNKNOWN`
   (`PEER_VIEW_NOT_PROVEN`). Tested: a hand-made "Replica B" view holding record 1 while the real B is empty makes the
   bare tool say CURRENT, but the operator says UNKNOWN.
5. **Read-only.** View files are made read-only (`0400` / `0500`). The canonical tool writes only its `--replica` /
   `--store` target, and no view changes across an append (asserted).
6. **Provenance-bound to the actual opposite-side canonical owner record.** Each view has a provenance record beside
   it, not inside it. The record binds the view tree digest, the S25 transcription that proves the real opposite-side
   copy, and, for `-1` views, the canonical source tree and the record or envelope digest the go bound.

A wrong view cannot create a wrong record. The record is re-derived from the binding's chain, trust and pin, and an
inconsistent peer is refused with nothing written (tested).

## 6. Owner acts (DRAFT TEMPLATES; NOT ISSUED)

No template authorizes the next act. The operator binds every placeholder `<...>` at runtime from the files
themselves (§12), so none is typed. `<binding>`, `<gate>` and `<eligibility>` are the SHA-256 of `BINDING.json`, of
the last exact gate record for that act, and of `C4B_ELIGIBILITY.json`.

### 6.1 C1: open Package C (read-only only)

> I authorize opening the Package C (record 1 + acceptance envelope 1) live sequence now, for this current DEV_SYNTHETIC sequence only.
> Continuity: PACKAGE_C_CONTINUITY = OWNER_ATTENDED_EVENT_BOUNDED_SINGLE_SEQUENCE_FOUR_OWNER_RECORD_BOUNDARIES.
> From this successful opening through C5, no intentional merge, deploy, reboot or witness restart is permitted. An unexpected external drift does not advance the sequence: it enters the reviewed revalidation path, and continuing requires the relevant fresh gate.
> Control commit: <control>.
> Operator: services/owner-memory-control/tools/pkgc_operator.py SHA-256 <operator>.
> Owner freshness tool: services/owner-memory-control/lilith_owner_memory/owner_freshness_tool.py SHA-256 <freshness_tool>.
> Committed witness genesis digest: <genesis>. chain/1.json SHA-256: <chain1>.
> This authorizes opening the sequence, read-only evidence (including receipt-bound acquisitions through the pinned read-only mb9_operator.py forms host POST9B and chain-export), the S25 read-only gate and the transfer of the reviewed bundle only. It does not authorize any owner-record write, record 1, either acceptance envelope copy, HELD, the signer, authority activation, First Memory or PROD.

### 6.2 C2: the APPEND_RECORD_1_REPLICA_A go (step 10)

> I authorize APPEND_RECORD_1_REPLICA_A now for exactly one attempt within this current Package C sequence.
> Continuity: PACKAGE_C_CONTINUITY = OWNER_ATTENDED_EVENT_BOUNDED_SINGLE_SEQUENCE_FOUR_OWNER_RECORD_BOUNDARIES.
> Control commit: <control>. Binding SHA-256: <binding>. Gate C2 SHA-256: <gate>.
> Target: Replica A <replica_a>. Peer: the non-custody, provenance-bound empty Replica B view (SHA-256 <view>).
> Record 1 candidate digest: <record>. Review package digest: <package>.
> Committed witness genesis digest: <genesis> (= the owner pin).
> I have reviewed the candidate and repeat its digest by hand to owner_freshness_tool append.
> I understand that this is an owner-record write: record 1 on Replica A is never overwritten or removed, and freshness remains FRESHNESS_UNKNOWN until Replica B holds the identical record.
> This go does not authorize record 1 on Replica B, either acceptance envelope copy, HELD, the signer, authority activation, First Memory or PROD.
> Any REFUSED, FAILED, traceback, pending file or other STOP after the attempt marker consumes this go. There is no automatic retry.

### 6.3 C3: the APPEND_RECORD_1_REPLICA_B go (step 11, S25)

> I authorize APPEND_RECORD_1_REPLICA_B on the S25 now for exactly one attempt within this current Package C sequence.
> Continuity: PACKAGE_C_CONTINUITY = OWNER_ATTENDED_EVENT_BOUNDED_SINGLE_SEQUENCE_FOUR_OWNER_RECORD_BOUNDARIES.
> Control commit: <control>. Binding SHA-256: <binding>. Gate C3 SHA-256: <gate>.
> Target: Replica B <replica_b>, run by me locally in Termux, with no SSH and no ADB. Peer: the non-custody Replica A view (SHA-256 <view>).
> S25 bundle SHA-256: <bundle>. Record 1 digest: <record> (the same record as Replica A).
> I understand that this is an owner-record write and that AUTHENTIC + CURRENT becomes possible only when Replica B holds exactly this record.
> This go does not authorize either acceptance envelope copy, HELD, the signer, authority activation, First Memory or PROD.
> Any REFUSED, FAILED, traceback, pending file or other STOP after the attempt marker consumes this go. There is no automatic retry.

### 6.4 C4A: the APPEND_ENVELOPE_1_COPY_A go (step 11a, laptop)

> I authorize APPEND_ENVELOPE_1_COPY_A now for exactly one attempt within this current Package C sequence: initialization of acceptance store A, then the one envelope append to store A on the laptop.
> Continuity: PACKAGE_C_CONTINUITY = OWNER_ATTENDED_EVENT_BOUNDED_SINGLE_SEQUENCE_FOUR_OWNER_RECORD_BOUNDARIES.
> Control commit: <control>. Binding SHA-256: <binding>. Gate C4A SHA-256: <gate>.
> Freshness: AUTHENTIC + CURRENT for record 1 <record>, observed in this sequence.
> Target: acceptance store A <store_a>. Peer: the non-custody, provenance-bound empty store B view (SHA-256 <view>).
> Envelope digest: <envelope>. Review package digest: <package>.
> I understand that the envelope is owner-acceptance evidence only: it does not make freshness current, does not make Registry V1 effective, does not start the signer, does not write HELD and grants no authority.
> This go does not authorize APPEND_ENVELOPE_1_COPY_B, HELD, the signer, authority activation, First Memory or PROD.
> Any REFUSED, FAILED, traceback, pending file or other STOP after the attempt marker consumes this go. There is no automatic retry.

### 6.5 C4B: the APPEND_ENVELOPE_1_COPY_B go (step 11b, S25)

> I authorize APPEND_ENVELOPE_1_COPY_B on the S25 now for exactly one attempt within this current Package C sequence: initialization of acceptance store B, then the one envelope append to store B, run by me locally in Termux, with no SSH and no ADB.
> Continuity: PACKAGE_C_CONTINUITY = OWNER_ATTENDED_EVENT_BOUNDED_SINGLE_SEQUENCE_FOUR_OWNER_RECORD_BOUNDARIES.
> Control commit: <control>. Binding SHA-256: <binding>. Gate C4B SHA-256: <gate>.
> C4B eligibility SHA-256: <eligibility>: a fresh read proved exactly ACCEPTANCE_PARTIAL, with copy A exact and copy B absent.
> Envelope digest: <envelope> (the same envelope as copy A). Record 1 digest: <record>.
> S25 bundle SHA-256: <bundle>. Peer: the non-custody store A view (SHA-256 <store_view>).
> I understand that the envelope is owner-acceptance evidence only: it does not make freshness current, does not make Registry V1 effective, does not start the signer, does not write HELD and grants no authority.
> This go does not authorize HELD, the signer, authority activation, First Memory or PROD.
> Any REFUSED, FAILED, traceback, pending file or other STOP after the attempt marker consumes this go. There is no automatic retry.

### 6.6 C5: Package C acceptance (authorizes nothing)

> I accept Package C for this sequence: record 1 on Replica A and Replica B and acceptance envelope 1 on copies A and B are COMPLETED.
> Record 1 digest: <record>. Envelope digest: <envelope>. Binding SHA-256: <binding>.
> Freshness: AUTHENTIC + CURRENT. Acceptance: ACCEPTANCE_COMPLETE.
> REGISTRY_EFFECTIVE remains NO. AUTHORITY_ACTIVE remains NO. authorityGranted remains false. The signer remains inactive.
> This acceptance authorizes nothing further: not HELD, the signer, authority activation, First Memory or PROD. The Package C freeze ends now.

### 6.7 Owner pre-C2 stop

> I stop this Package C sequence now, before any owner-record write, for this current DEV_SYNTHETIC sequence only.
> Control commit: <control>. C1 record SHA-256: <c1>.
> No C2 attempt marker exists and no owner record was written by this sequence.
> This sequence is STOPPED / HISTORICAL / NON-REUSABLE. Its freeze is released; the release authorizes nothing.

## 7. Continuity, freeze and invalidation

`PACKAGE_C_CONTINUITY = OWNER_ATTENDED_EVENT_BOUNDED_SINGLE_SEQUENCE_FOUR_OWNER_RECORD_BOUNDARIES` (proposed,
OD-C1): one fresh evidence sequence; one freeze; no wall-clock TTL; material uncertainty or drift ⇒ REVALIDATE / STOP
(ADR-0015); a technical PASS never implies the next go.

**Freeze (clarified).** From the **successful C1 opening through C5**, no **intentional** merge, deploy, reboot or
witness restart is permitted. This also covers merge-triggered deploys, manual DEV changes, package upgrades and
signer actions. The pre-C2 stop releases the freeze instead.

**External drift.** An unexpected external drift, for example an unplanned restart or an unattended upgrade, **does
not silently advance the sequence**. The state machine keeps its state (tested in every non-terminal state). The
event enters the reviewed revalidation path (§7.2): REVALIDATE drops the last gate and any C4B eligibility, and
continuing requires **the relevant fresh gate**. After a consumed marker it also requires a new go. A HALT event ends
the sequence.

The first deploy after C5 must again show `W9_5_GENESIS_COMMITTED_EXACT` and compare `EQUAL` to the accepted
running-witness phase-bound DR-5 target. Record 1 and the envelopes are not host-observable, so Package C adds no DR-5
line.

### 7.1 What must remain unchanged (binding → C5, in particular between record 1 on A and on B)

| Fact | Source at each gate |
| --- | --- |
| control commit; operator, `owner_freshness_tool` and the pinned Package B read tools | `pins`; the C1 record; every acquisition receipt |
| the binding (`BINDING.json` and its three outputs) | `load_binding` re-hash |
| the candidate record-1 digest and bytes (A, the phone's re-derivation, B) | the C2 marker values; the phone's `propose-genesis`; the transcription |
| the envelope digest (A, the phone's re-derivation, B) | the C4A marker values; C4B eligibility; the phone's `propose-envelope` |
| W9 phase `W9_5_GENESIS_COMMITTED_EXACT`; committed digest `ac892dc2…`; `chain/1.json` = `witness.json` `252c3220…`; chain = genesis only | a fresh acquisition (§3.1) |
| witness incarnation (InvocationID `5136ea7a…`, MainPID `143946`) and `NRestarts = 0` | the same acquisition |
| boot id (= the binding's); `REBOOT_REQUIRED = absent` | the same acquisition (`host` identity) |
| the last DEV deploy run id; an empty workflow queue | `gh run list` (read-only facts file) |
| hold store empty; signer inactive with no runtime path; `registryEffective = false`; `authorityGranted = false` | the acquisition |
| Replica A and store A = exactly the expected entries; Replica B and store B = exactly the expected entries; no pending file | `verify-replica` (laptop); the transcriptions (S25) |
| P-A and P-B = the three accepted files | `bind`; the phone's `cmp` / hashes |
| the S25 bundle tar SHA-256 | the `S25_BUNDLE.json` record; the phone's `sha256sum -c` |

### 7.2 Invalidators

| Event | Route | Meaning |
| --- | --- | --- |
| `DEPLOY_OCCURRED`, `WORKFLOW_QUEUE_NOT_EMPTY`, `CONTROL_CHANGED`, `TOOL_PIN_CHANGED` | REVALIDATE | freeze breach or drift: STOP the act; a fresh gate, and after a consumed marker a new go |
| `WITNESS_INCARNATION_CHANGED`, `WITNESS_RESTARTED` | REVALIDATE | the witness is not the accepted incarnation: STOP; separately reviewed re-acceptance first |
| `BOOT_ID_CHANGED`, `REBOOT_REQUIRED_PRESENT` | REVALIDATE (global invalidator) | STOP; the P3-5 §12 re-baseline before anything else |
| `ACQUISITION_NOT_FRESH`, `W9_PHASE_NOT_EXACT`, `S25_BUNDLE_MISMATCH`, `TRANSCRIPTION_MISMATCH` | REVALIDATE | STOP; read again (a new acquisition); never act on a stale or partial read |
| `EVIDENCE_UNKNOWN` (a missing, unparseable or unexpected fact) | REVALIDATE | **UNKNOWN is never equality and never success** |
| `GENESIS_MISMATCH`, `CHAIN_ADVANCED`, `CHAIN_BYTES_CHANGED` | **HALT** | lineage drift: never accept; manual recovery |
| `OWNER_RECORD_INCONSISTENT`, `REPLICA_PENDING_WRITE`, `ACCEPTANCE_PENDING_WRITE`, `ACCEPTANCE_CONFLICTING`, `PIN_BYTES_CHANGED` | **HALT** | owner-record inconsistency: STOP; the owner inspects; nothing is deleted, repaired or rewritten |
| `HOLD_STORE_NOT_EMPTY`, `SIGNER_ACTIVE`, `AUTHORITY_GRANTED`, `REGISTRY_EFFECTIVE` | **HALT** | an authority boundary moved outside Package C |

The following are also HALT, because they cannot happen in a correct sequence (tested): CURRENT after Replica A
alone; anything other than `[record 1]` / `[]` after C2; anything other than exactly PARTIAL after C4A; copy B present
or not exactly PARTIAL at the C4B eligibility read. Any event not in the tables is treated as `EVIDENCE_UNKNOWN`.

### 7.3 Retry and recovery after an attempt marker

There is **no automatic retry**, ever. After a marker, the outcome is classified read-only:

| Observed copy after the attempt | Classification | Next |
| --- | --- | --- |
| exactly the expected new record / envelope, no pending file | the write happened (also when the tool's reply was lost) | continue to the next observation; never run the same append again (the tool would refuse anyway: `RECORD_EXISTS` / `REPLICAS_NOT_APPENDABLE` / `ENVELOPE_EXISTS`) |
| unchanged, no pending file | no write; that go is consumed | STOP; a new sequence (new C1, fresh evidence) may resume (below); a new go is required |
| a `.pending-*` file | C-15 / `ACCEPTANCE_PENDING_WRITE` | HALT, manual; never auto-deleted |
| anything else | inconsistency | HALT |

**Resumption.** A STOP never undoes an owner record. A new sequence opens with a fresh C1, a fresh acquisition and a
fresh binding, and its read-only opening observation decides where it starts. Only the canonical recoverable states
are accepted:

- `EMPTY` → `PC1_BOUND_KNOWN_EMPTY`;
- `A_ONLY` (C-14) → `PC2_RECORD1_A_PARTIAL`;
- `AB_NO_ENVELOPE` (C-16) → `PC3_RECORD1_CURRENT`;
- `ENVELOPE_A_ONLY` (C-16a) → `PC4A_ENVELOPE_A_PARTIAL`, after which C4B still needs its own gate, eligibility and
  go.

Anything else is HALT (tested). The canonical tool's own semantics permit these continuations: `append` accepts
"peer = target + candidate", and `append-envelope` accepts "peer = target + envelope".

## 8. S25 procedure

### 8.1 Rules

- **Owner-run, locally, in Termux.** No SSH, no ADB, no USB debugging, no Developer options, no network transfer, no
  cloud share. `sshd` is not running.
- **Transport:** a USB cable in **File transfer (MTP)** mode, **only for the copy**, then disconnected (P3-3B §3).
  Files land in `Download`, which is transport only. `termux-setup-storage` is a prerequisite and is not part of the
  script.
- **Only the reviewed artifacts travel:** T1 the bundle (§8.2), T2 the Replica A view, and T3 the store-A view plus
  the review package. Nothing else. Nothing travels from the phone to the laptop except the owner's transcription.
- **G0 `cryptography` preinstall check:** major version within the P3-3B range **and** a live Ed25519
  sign/verify self-test. Missing or failing means STOP; installing it is a separate owner decision (OD-C8).
- **Exact checksums before execution:** the tar SHA-256 is typed by the owner and checked with `sha256sum -c`, then
  every member is checked against the bundle's `SHA256SUMS`, at the start of **every** stage.
- **Bundle source:** the canonical tool's import closure **at the Package C control** (15 files, pinned by a test to
  the computed import closure). **The P3-3B bundle (`44a53f2`) must not be used** (OD-C9).
- **Paths:** Replica B `$HOME/lilith-owner-offline-dev-synthetic-01` (canonical, not nested); P-B
  `$HOME/lilith-genesis-pin-dev-synthetic`; store B `$HOME/lilith-owner-acceptance-offline-dev-synthetic-01`
  (sibling, never inside the replica); staging and views `$HOME/lilith-pkgc`.

### 8.2 Bundle and transfers (laptop, deterministic)

| Transfer | Form | Content | When |
| --- | --- | --- | --- |
| T1 `lilith-pkgc-bundle.tar` | `pkgc_operator.py s25-bundle <repo> <workdir> <vendor-dir> <out>` | `src/` closure at the control, `vendor/` (fido2 2.2.1, rfc8785 0.1.4, pure Python), `binding/` (the four binding files), `pkgc_s25_phone.sh`, `SOURCE_COMMIT`, `SHA256SUMS` | after `bind`, inside C1 |
| T2 `lilith-pkgc-replica-a.tar` | `transfer <workdir> replica-a <paths> <out>` | `replica-a/REPLICA.json`, `replica-a/records/000001-<d>.json` (must be the C2 record) | after C2 is observed, before gate C3 |
| T3 `lilith-pkgc-store-a.tar` | `transfer <workdir> store-a <paths> <out>` | `store-a/…` (must be the C4A envelope), `package.json` | after C4A is observed `ACCEPTANCE_PARTIAL`, before gate C4B |

Every tar: sorted names, mtime 0, owner 0:0, modes 0644/0755, a top-level `SHA256SUMS`. The tar SHA-256 and tree
digest are recorded create-only in the work directory (`custody = NON_CUSTODY_PEER_VIEW`).

### 8.3 Phone commands

[`pkgc_s25_phone.sh`](../../services/owner-memory-control/tools/pkgc_s25_phone.sh) (in the bundle). The owner sources
it and runs **one** stage function per step, typing the laptop-shown values by hand:

| Function | Act | Mutation | Gates before any write |
| --- | --- | --- | --- |
| `pkgc_c1` | C1 | none (staging and evidence directories only) | G0, bundle, P-B exact and = bound pin, `inspect-chain` AUTHENTIC, Replica B verifies |
| `pkgc_c3` | C3 | `append` to Replica B, once | everything in C1, plus: A view verified; Replica B has 0 records; the phone's own `propose-genesis` digest equals the typed record digest; noclobber marker `attempt-C3` |
| `pkgc_c4b_pre` | after gate C4B (eligibility) | **none**: read-only, no marker | everything in C1, plus: A view verified; prints Replica B, the phone's freshness and `ACCEPTANCE_STORE_B` |
| `pkgc_c4b` | C4B | `init-acceptance-store` (store B), then `append-envelope`, once | everything in C1, plus: both views verified; the phone classifies AUTHENTIC + CURRENT; store B absent; noclobber marker `attempt-C4B`; the phone's own `propose-envelope` digest equals the typed envelope digest |

The digest passed to `--confirm-digest` is the owner-typed value, so the owner repeats it by hand (PR3-D2). It is
never generated on the phone.

### 8.4 Evidence class: `OWNER_SCREEN_TRANSCRIPTION`

Each stage (`C1`, `C3`, `C4B_PRE`, `C4B`) prints a fixed, ordered result block and then
`RESULT_BLOCK_SHA256=<sha256 of the block>`. The owner transcribes the block from the screen. `s25-check` requires
**exact ordered equality** with the expectation the laptop derives from its own evidence (the bundle record, Replica
A's record 1, the tree digests, store A's envelope), **plus** the block hash. A missing, extra, reordered or altered
line, or a wrong hash, is `PKGC_S25_TRANSCRIPTION_MISMATCH` (tested). The block hash catches transcription errors; it
authenticates nothing. The phone result is owner-observed, not machine-captured. No stronger mechanism is designed or
authorized here (OD-C3).

## 9. Freshness semantics (canonical tool, unchanged; enforced by tests)

| Point | Register | Freshness | Gated operations | Acceptance |
| --- | --- | --- | --- | --- |
| before C2 | `OWNER_REGISTER_EMPTY` (A + the proven empty B view) | `FRESHNESS_UNKNOWN` | all blocked | — |
| after C2 (A only) | `REPLICAS_DIVERGENT … PREFIX` | **`FRESHNESS_UNKNOWN`** (CURRENT here is a HALT) | **all `FRESHNESS_BLOCKED`** | `propose-envelope` refuses (`OWNER_REGISTER_NOT_VERIFIED`) |
| after C3 (A = B) | `OWNER_REGISTER_VERIFIED` | **AUTHENTIC + CURRENT** (first possible here) | met (meeting a gate authorizes nothing) | `ACCEPTANCE_NOT_PRESENT` |
| after C4A | unchanged | CURRENT (unchanged) | unchanged | `ACCEPTANCE_PARTIAL` |
| after C4B | unchanged | CURRENT (unchanged) | unchanged | `ACCEPTANCE_COMPLETE` |

- **AUTHENTIC + CURRENT is impossible until Replica B holds the identical record 1.** On the laptop it is also
  impossible through an unproven view (§5 invariant 4).
- **The envelope never makes freshness current.** An out-of-band envelope written while only A holds record 1 leaves
  freshness `FRESHNESS_UNKNOWN` and acceptance not `COMPLETE` (tested). The sequencer refuses any envelope step from
  `OWNER_RECORD_PARTIAL` (tested).
- **The tests drive the accepted P3-5 sequencer** (`BootstrapSequencerV1`) from `WITNESS_GENESIS_COMMITTED` through
  steps 10, 11, 11a (C4A) and 11b (C4B), using the real classification results. It ends at
  `OWNER_ACCEPTANCE_EVIDENCED`, and `WRITE_HELD` is never invoked.

## 10. Acceptance envelope 1

- **Binds** (P3-6 §1, unchanged): `freshnessRecordVersion = 1`, `freshnessRecordDigest` = record 1,
  `decision = ACCEPT_CURRENT`, `previousAcceptanceEnvelopeDigest = null`, `genesisPinDigest` (the bound pin),
  `ownerReviewPackageDigest` (the R1 package built **before** C2, with the `PR2_REVALIDATION` and `P3_3_INDEPENDENCE`
  digests from the binding), `replicaSetDigest` (the two replica IDs), `ceremonyVersion`, and
  `acceptanceMethod = EXPLICIT_OWNER_DIGEST_CONFIRMATION`. It has no timestamp, no signature and no path.
- **Copy A (C4A) and copy B (C4B) are separate acts** with separate gates, markers and points of no return. Both bind
  the **same** envelope digest. The C4A go binds it from the laptop's envelope candidate. The C4B go binds it from
  the eligibility record (= store A's envelope). The phone re-derives it with `propose-envelope` from Replica B, the A
  view, store B and the transferred package, and refuses any difference. The **bundle files** in stores A and B are
  **byte-identical** (tested). The stores' `ACCEPTANCE.json` manifests differ by design (`custodyCopyId`).
- **Partial vs complete:** `ACCEPTANCE_PARTIAL` after C4A, `ACCEPTANCE_COMPLETE` after C4B. Any other state after a
  copy is HALT (tested). C4B requires exactly PARTIAL with copy B absent (§2.1). C5 requires COMPLETE + CURRENT.
- **No widening:** the envelope is evidence of one past owner decision. It does not make freshness current, does not
  make Registry V1 effective, does not start the signer, does not write HELD, and grants no authority. Both the C4A
  and C4B gos state this verbatim.

## 11. State boundaries after Package C

Package C completion leaves exactly (`AUTHORITY_BOUNDARY`, tested):

```text
REGISTRY_EFFECTIVE = NO
AUTHORITY_ACTIVE = NO
authorityGranted = false
signer = inactive
HELD = not authorized
First Memory = not authorized
PROD = not authorized
```

The P3-5 sequencer stands at `OWNER_ACCEPTANCE_EVIDENCED`. `authority_changing_permitted` is false, and
`first_memory_gate` returns `FIRST_MEMORY_BLOCKED` (`FULL_READINESS_REQUIRED`). `PackageCSequenceV1` has no HELD,
signer, activation, release or First Memory transition (tested by name). After `PC5` the only next action is "none":
HELD (M-B10), the signer, activation, First Memory and PROD each need their own later authorization.

**First Memory boundary.** Tooling must not infer, choose, draft or write LILITH's First Memory merely because later
bootstrap stages become technically ready. If the system eventually reaches `FIRST_MEMORY_READY`, the process
**STOPS** there. Owner discussion is required before any First Memory content is selected or written.

## 12. Tooling

**Reused unchanged:** `owner_freshness_tool` (`propose-genesis`, `build-review-package`, `append`, `classify`,
`compare-replicas`, `verify-replica`, `init-acceptance-store`, `propose-envelope`, `append-envelope`,
`classify-acceptance`, `inspect-chain`), `pr1b_sequencing`, `owner_acceptance`, and the pinned `mb9_operator.py`
(only its read-only `host … POST9B` and `chain-export` forms) with `mb9_witness_verifier.py` and
`mb9_owner_genesis_verify.py`. No accepted semantics change.

**Added (thin, justified):** `services/owner-memory-control/tools/pkgc_operator.py`. It closes exactly three
binding gaps that the existing tools cannot:

1. deterministic trust-input and chain-export documents from accepted bytes (§3);
2. a receipt-bound fresh acquisition (§3.1);
3. provenance-bound non-custody peer views (§5).

Everything else is sequencing discipline: gates, the C4B eligibility read, markers, derived go values and the
transcription check. Forms: `pins`, `open`, `acquire`, `acquire-windows` (§12.2), `bind`, `gate`, `peer-view`, `transfer`, `s25-bundle`,
`s25-expect`, `s25-check`, `c4b-eligibility`, `arm`, `record`.

- **It writes no owner record.** It never calls `append`, `append-envelope`, `init-acceptance-store` or any replica
  writer (AST-tested). It writes only its work directory, the binding, views, transfer tars, receipts and markers.
- **Go values are derived from files, never typed:**
  - the record digest from the candidate file (checked as record 1 of this genesis);
  - the package digest from the package (checked: `RECORD_1`, this record, the bound evidence);
  - the view digests from proven views;
  - the envelope digest from the envelope candidate (checked against this record and package) for C4A, and from the
    eligibility record for C4B.

  A go with any other value is `GO_LINE_MISSING` (tested).
- **Its only DEV contact** is `acquire`, which runs the two pinned read-only `mb9_operator.py` forms and nothing else
  (tested). It never contacts the S25, and has no `gcloud`, `ssh`, `plink`, `systemctl`, socket or mutating
  `mb9_operator` form (tested).
- `services/owner-memory-control/tools/pkgc_s25_phone.sh`: the only S25 commands. Static tests check: no
  SSH/ADB/network/package install/deletion; exactly three write commands (`append`, `init-acceptance-store`,
  `append-envelope`), each behind a noclobber marker; `pkgc_c4b_pre` read-only; and emitted keys equal to the
  expectation.

### 12.1 Runbook (laptop; WSL; outside every Git tree and every replica or store root)

1. **C1** (owner text). `pkgc_operator.py pins <repo>`, then `open <repo> <workdir> <C1.txt> <facts.json>`. Every `acquire` in steps 1 to 6 runs on Windows as `acquire-windows` (§12.2). Read-only
   evidence: cloud captures (the `PR2_REVALIDATION` digest) and `gh run list`. Then `acquire <repo> <workdir>
   <mb9-workdir>`, `bind <workdir> … <workdir>/exports/<01-…> <replica-a> <pr2> <p33>`, `s25-bundle`, and T1 (MTP). On
   the phone: `pkgc_c1`. On the laptop: `s25-check <workdir> C1 …`. Replica A is verified empty, so the register is
   `KNOWN_EMPTY`.
2. **C2.** `peer-view <workdir> replica-b-0`, `propose-genesis`, `build-review-package` (Replica A + the B view;
   `--evidence PR2_REVALIDATION=… P3_3_INDEPENDENCE=…`), then `acquire` and `gate C2`. Owner go: `arm <workdir> C2
   <go> <paths>`. The owner runs the one `append --replica <A> --peer <B view>`, typing the digest. Then
   `verify-replica`; laptop freshness is `FRESHNESS_UNKNOWN` and every gate is blocked.
3. **C3.** `transfer replica-a` (T2, MTP), `acquire`, `gate C3`. Owner go: `arm C3`. On the phone: `pkgc_c3`. On the
   laptop: `s25-check C3`, `peer-view replica-b-1 <replica-a>`; laptop freshness is AUTHENTIC + CURRENT.
4. **C4A.** `peer-view store-b-0`, `propose-envelope` (A + the B view; a throwaway empty store-A' + the store-B view;
   the candidate is a proposal only), `acquire`, `gate C4A`. Owner go: `arm C4A`. The owner runs
   `init-acceptance-store` (store A), then the one `append-envelope --store <A> --peer-store <store-B view>`. Laptop
   acceptance is `ACCEPTANCE_PARTIAL`.
5. **C4B.** `transfer store-a` (T3, MTP), `acquire`, `gate C4B`. On the phone: `pkgc_c4b_pre` (read-only). On the
   laptop: `s25-check C4B_PRE`, then `c4b-eligibility`. Owner go: `arm C4B`. On the phone: `pkgc_c4b`. On the laptop:
   `s25-check C4B`, `peer-view store-b-1 <store-a>`; laptop acceptance is `ACCEPTANCE_COMPLETE`.
6. **C5** (owner text). `acquire`, `gate C5`, `record <workdir> C5 <C5.txt> <paths>`. The freeze ends.

Before C2 only, the owner may instead stop the sequence (§6.7, `record … STOP`). The operator refuses the stop once
any attempt marker exists.

### 12.2 Two-environment procedure (C1 environment fix)

On the owner laptop the two halves of every acquisition live in different environments:

- `pkgc_operator` and the canonical tool need the pinned `rfc8785`, `fido2` and `cryptography` packages. Those are
  installed only in WSL (`/root/l1deps`).
- The pinned read-only `mb9_operator.py` forms need the reviewed Windows DEV transport: the Windows Cloud SDK, the
  pinned direct-plink client (R-B4 / R-B5) and the owner key. WSL has none of them and is not given any.

So the procedure is split, without changing any Package C semantics:

| Where | Forms |
| --- | --- |
| **WSL** (`PYTHONPATH=/root/l1deps`) | `pins`, `open`, `bind`, `gate`, `peer-view`, `transfer`, `s25-bundle`, `s25-expect`, `s25-check`, `c4b-eligibility`, `arm`, `record`, and every canonical-tool command |
| **Windows** (standard library only) | `acquire-windows <repo> <wsl-distro> <wsl-workdir> <sequence-id> <mb9-workdir>`, with the reviewed `LILITH_MB6_GCLOUD` / `LILITH_MB9_PLINK` environment |

**What changed in `pkgc_operator.py`:**

- The four `lilith_owner_memory` modules are imported **on first use** (`_OnDemand`). Every other form imports
  them, and through them the pinned packages, exactly as before.
- `_read` and `_json` use the standard library: the same 8 MiB limit (`MAX_INPUT_BYTES` = the tool's) and the same
  strict parser (UTF-8, duplicate keys refused) as `witness_readiness._json`. Their equality is tested.
- `acquire-windows` validates the path and the sequence, then calls the **unchanged** `acquire`. The same two
  pinned read-only forms run, into the same `exports/` and `acquisitions/` entries, with the same receipt. The WSL
  side verifies it with the unchanged `verify_acquisition`, `check_export` and `bind`.

**Path contract (deterministic, validated before anything is written):**

- `<wsl-workdir>` is the absolute WSL path given to `open`, for example `/root/lilith-pkgc-seq1`. Only plain
  components are accepted: no `.`, `..`, empty component, trailing `/` or `/mnt`.
- The Windows path is exactly `\\wsl$\<wsl-distro>` followed by that path with `\` separators, for example
  `\\wsl$\Ubuntu-24.04\root\lilith-pkgc-seq1`. No other spelling is derived or accepted.
- It must be an existing directory (`WSL_WORKDIR_NOT_FOUND`) holding the C1 opening (`SEQUENCE_NOT_OPENED`). Its
  `sequenceId` must equal `<sequence-id>`, the value `open` printed (`SEQUENCE_MISMATCH`). The form never opens or
  creates a sequence or work directory.
- The Windows clock must not be behind the WSL opening time (`CLOCK_BEFORE_OPENING`). Otherwise the receipt's
  timestamp rule would refuse the read after the fact. This check runs before any DEV contact.
- `<repo>` is a clean Windows checkout at the control. `pins` exactness is checked as in `acquire`.

**Not changed:** the receipt schema; the freshness rule (§3.1); the single use of each acquisition; the two pinned
forms; `TOOL_PINS` (the `mb9_operator.py` pin and transport are unchanged); every gate, template and refusal; and
the fact that the operator writes no owner record.

## 13. Tests

`services/owner-memory-control/tests/test_b1b3e_pkgc_record1_envelope.py` (TEST_ONLY, temporary directories, real
K-WIT-signed TEST chains, the canonical tool via `owner_freshness_tool.run`, a fake runner in place of the two pinned
read-only `mb9_operator` forms):

| Class | Covers |
| --- | --- |
| `StateMachineTests` | the full C1→C2→C3→C4A→C4B→C5 path; the bootstrap mapping (10, 11, 11a, 11b, then `WRITE_HELD` outside); C4A and C4B as separate acts; C4B eligibility only after its gate, voided by a new gate or drift, HALT on copy B present or not exactly PARTIAL; order; a fresh gate per arm; A-only UNKNOWN; CURRENT only after B; partial vs complete; drift never advances (every non-terminal state, every REVALIDATE event); HALT events; PONRs; stop; resumption |
| `AcquisitionTests` | the receipt binds sequence, time, control, pins, commands and results, phase, incarnation, boot, genesis and artifacts; identical bytes are fine; an old export in a new directory, a bare export, another sequence's export (even with its log entries), tampering, and a failed read are all `ACQUISITION_NOT_FRESH`; only the two read-only forms run; control drift is refused |
| `BindingTests` | exact, deterministic binding the canonical tool reads AUTHENTIC; every acquisition exactness check; accepted installable and pin bytes; single-use acquisitions; tamper evidence |
| `ContinuityTests` | fresh gates; each invalidator and its route; a stale export is REVALIDATE, never PASS; the last gate must be exact and for this stage |
| `PeerViewTests` | NON-CUSTODY label, provenance beside the view, read-only modes; never under a canonical root and no canonical copy inside the work directory; bound to the opposite-side transcription; **a view never makes anything current by existing**; a changed view loses its provenance; no discovery (AST) |
| `CeremonyTests` | **end to end** on two simulated machines, C1 → C5, with the P3-5 sequencer driven in step: `PEER_PENDING` and UNKNOWN after C2; `REPLICAS_IDENTICAL` and CURRENT after C3; PARTIAL after C4A; the C4B gate, `C4B_PRE` and eligibility; `COPIES_IDENTICAL`, byte-identical bundles and COMPLETE after C4B; C5 with the boundary unchanged; copy B present never eligible; an envelope never makes freshness current; a wrong peer writes nothing |
| `S25Tests` | exact ordered transcription plus the block hash; per-stage expectations (`C4B_PRE` read-only); the phone script's keys and boundary; the S25 closure = the computed import closure; deterministic tars |
| `BoundaryTests` | no owner-record write and no authority or mutating form; the operator forms; tool pins = merged bytes; the templates (freeze line, C4A ≠ C4B, step names); the accepted pins = the Package A/B records; this record's boundary lines and verbatim templates |

## 14. Owner decisions requested (proposed; none accepted)

| # | Decision |
| --- | --- |
| OD-C1 | `PACKAGE_C_CONTINUITY = OWNER_ATTENDED_EVENT_BOUNDED_SINGLE_SEQUENCE_FOUR_OWNER_RECORD_BOUNDARIES`, with the clarified freeze (§7) |
| OD-C2 | peer views as NON-CUSTODY, read-only, provenance-bound comparison inputs with the six invariants of §5. The S25 views stay in staging as evidence after Package C, never at a replica or store path |
| OD-C3 | the S25 evidence class is `OWNER_SCREEN_TRANSCRIPTION` with the result-block hash. No MTP copy-back is designed |
| OD-C4 | C4 split into **C4A** (step 11a, laptop) and **C4B** (step 11b, S25), each with its own go, marker and PONR, and C4B eligibility per §2.1. Store paths as in §8.1 and the laptop sibling `/root/lilith-owner-acceptance-primary-dev-synthetic-01` |
| OD-C5 | resumption by a new sequence at the canonical recoverable points only (§7.3) |
| OD-C6 | **export freshness = a per-read acquisition receipt bound to this sequence and the presented DEV world (§3.1)**, never a new directory or identical content |
| OD-C7 | the `PR2_REVALIDATION` evidence is the C1 fresh read-only cloud capture; `P3_3_INDEPENDENCE` is the accepted P3-3 evidence digest |
| OD-C8 | `cryptography` must already be installed in Termux; G0 STOPs otherwise; installing it is a separate owner decision |
| OD-C9 | the S25 runs only the Package C bundle at the control. The P3-3B `44a53f2` bundle is retired for writes |

## 15. Hidden assumption

> What assumption could make Package C appear safe while it is wrong?

1. **"The phone and the laptop each see their own replica, so the tool's two-replica checks still hold."** Not by
   themselves: each machine sees one real copy and one view. Safety rests on (a) the record being re-derived from the
   bound chain, trust and pin, not from the view; (b) the view counting only when its provenance binds it to the
   transcribed real copy; and (c) a wrong view being refused before any write.
2. **"An export is fresh if it is in a new directory or has the right bytes."** Rejected (OD-C6, revised): right
   bytes are expected forever. Freshness is the logged, receipt-bound read itself.
3. **"Copy A succeeded, so copy B is a formality."** Rejected: copy B is a separate owner-record write, against a
   separate copy, on a separate device. It needs its own fresh evidence that copy B is still absent and copy A still
   exact.
4. **"The envelope completes acceptance, so the world is current."** Rejected: CURRENT comes only from the two
   identical records (P3-6 §14).
5. **"The phone printed CURRENT, so it is CURRENT."** The phone's output reaches the laptop only as owner
   transcription. The laptop independently classifies through a proven view. Both must agree.

## 16. Nonclaims

This slice does **not** establish record 1, any envelope, an acceptance store, CURRENT freshness, owner acceptance of
anything, HELD, signer readiness, Registry V1 effectiveness, authority activation, A1–A7, First Memory readiness, PROD
readiness or whole-host rollback resistance. The operator is not a verifier of DEV state: it trusts the pinned W9
verifier's and host forms' reports as read-only evidence and refuses anything inexact.

## 17. State

```text
PACKAGE_C = DESIGN / REPOSITORY ONLY (DOCS + OPERATOR + PHONE SCRIPT + TESTS); NOT MERGED; NOT RUN
PACKAGE_C_SEQUENCE_ORDER = C1 → C2 → C3 → C4A → C4B → C5
PACKAGE_C_CONTINUITY = PROPOSED (OD-C1); NOT ACCEPTED
OWNER_DECISIONS OD-C1..OD-C9 = PROPOSED; NOT ACCEPTED
PACKAGE_B = COMPLETED / OWNER-ACCEPTED
W9_PHASE = W9_5_GENESIS_COMMITTED_EXACT (last accepted read)
WITNESS_GENESIS_DIGEST = ac892dc2b14ca7db108400258abfcf2320ff498f2a674058058e16a8a6fb65e4
OWNER_FRESHNESS_TOOL_SHA256 = fd7abe2aa5e5efae41b87553efe8fe8058b437748accf866c2fa5ee71c8a7c27 (unchanged)
PACKAGE_C_SEQUENCE = NOT AUTHORIZED
APPEND_RECORD_1_REPLICA_A = NOT AUTHORIZED
APPEND_RECORD_1_REPLICA_B = NOT AUTHORIZED
APPEND_ENVELOPE_1_COPY_A = NOT AUTHORIZED
APPEND_ENVELOPE_1_COPY_B = NOT AUTHORIZED
S25_MUTATION = NOT AUTHORIZED
LIVE_DEV_MUTATION = NOT AUTHORIZED
RECORD 1 = ABSENT
ACCEPTANCE_ENVELOPE = ABSENT
REGISTRY_EFFECTIVE = NO
AUTHORITY_ACTIVE = NO
authorityGranted = false
SIGNER = INACTIVE
HELD = NOT AUTHORIZED
AUTHORITY ACTIVATION = NOT AUTHORIZED
FIRST_MEMORY = NOT AUTHORIZED
FIRST_MEMORY_READY = NOT REACHED
PROD = NOT AUTHORIZED
FRESHNESS=UNKNOWN
```

## 18. Revision history

| Version | Commit | Change |
| --- | --- | --- |
| v1 | `d84eecb` | initial design (C1 → C2 → C3 → C4 → C5) |
| v2 | `013c9cf` | owner review of PR #176: C4 split into C4A / C4B, with the C4B eligibility read (§2.1); OD-C6 tightened to the per-read acquisition receipt (§3.1); peer-view invariants made explicit and tested (§5); the freeze clarified (§7); state machine, templates, runbook and tests updated |
| v3 | this revision | C1 environment fix: the acquisition runs on Windows with the standard library only (`acquire-windows`, on-demand imports, stdlib `_read` / `_json`); everything else stays in WSL (§12.2) |
