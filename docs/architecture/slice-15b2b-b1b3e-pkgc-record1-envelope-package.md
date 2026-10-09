# Slice 15B2b-B1b-3e — Package C: Record 1 (Replica A, Replica B) + Acceptance Envelope 1 (Copies A, B) (Design, Tooling and Runbook)

Status:

- **REPOSITORY ONLY: DESIGN, DOCUMENTATION, A THIN OPERATOR, A PHONE SCRIPT AND TESTS.** Owner authorization of
  2026-10-09 covered the Package C design slice only. Writing this slice contacted no live system: no DEV, no S25, no
  replica, no acceptance store and no owner key. **No live Package C step has run.**
- Packages the four owner-record steps of the accepted bootstrap (P3-5 steps 10, 11, 11a and 11b) into one
  owner-attended sequence with **five owner acts** (C1 … C5, §2). Three of them (C2, C3, C4) are canonical owner-state
  writes, and each needs its own explicit go.
- **Nothing is authorized by this record.** `APPEND_RECORD_1_REPLICA_A`, `APPEND_RECORD_1_REPLICA_B`,
  `APPEND_ENVELOPE_1_COPY_A`, `APPEND_ENVELOPE_1_COPY_B`, every owner-record write, every S25 mutation, every live
  DEV mutation, M-B10 HELD, signer start, authority activation, First Memory and PROD remain **NOT AUTHORIZED**.
  `FRESHNESS=UNKNOWN`.
- Predecessors: [Package B completion](slice-15b2b-b1b3e-mb9-package-b-completion.md) (`WITNESS_GENESIS = COMMITTED
  / IRREVERSIBLE`, genesis `ac892dc2…65e4`) and the [first post-Package-B-freeze deploy](slice-15b2b-b1b3e-mb9-first-post-package-b-deploy.md)
  (`EQUAL / OWNER-ACCEPTED`, host phase `W9_5_GENESIS_COMMITTED_EXACT`).

```text
binding != record 1;  record 1 on Replica A != freshness CURRENT;  AUTHENTIC + CURRENT != acceptance evidence
acceptance envelope complete != HELD != signer started != Registry V1 effective != authority active != First Memory
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
| [Package B](slice-15b2b-b1b3e-mb9-witness-genesis-package.md) §6.1, §8, §9, OD-B10 | the W9 phases, the read-only `chain-export` form, the owner offline verification |
| code: `owner_freshness_tool.py` (SHA-256 `fd7abe2a…7c27`), `owner_freshness.py`, `owner_acceptance.py`, `pr1b_sequencing.py` | **unchanged**: what writes and classifies |

Accepted identities Package C binds (Package A and Package B records, re-proven fresh in every sequence):

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

## 2. Package C state machine and the C1–C5 boundaries

`pkgc_operator.PackageCSequenceV1` (pure, forward only). Freshness and acceptance enter only as the real
`FreshnessResultV1` / `AcceptanceResultV1`, never a boolean (tested).

```text
PC0_NOT_OPENED
  --C1 (verbatim, read-only)--> PC1_OPENED_READ_ONLY
  --fresh export + binding + S25 C1 transcription + KNOWN_EMPTY--> PC1_BOUND_KNOWN_EMPTY
  --gate C2 + C2 go (marker)--> PC2_ARMED
  --observe: A = [record 1], B = [], FRESHNESS_UNKNOWN--> PC2_RECORD1_A_PARTIAL            (P3-5 OWNER_RECORD_PARTIAL)
  --gate C3 + C3 go (marker)--> PC3_ARMED
  --observe: S25 transcription exact, A = B, AUTHENTIC + CURRENT--> PC3_RECORD1_CURRENT   (P3-5 OWNER_FRESHNESS_CURRENT)
  --gate C4 + C4 go (marker; CURRENT re-checked)--> PC4_ARMED
  --observe copy A: CURRENT + ACCEPTANCE_PARTIAL--> PC4_ENVELOPE_A_PARTIAL               (P3-5 OWNER_ACCEPTANCE_EVIDENCE_PARTIAL)
  --observe copy B: transcription exact + CURRENT + ACCEPTANCE_COMPLETE--> PC4_ENVELOPE_COMPLETE (P3-5 OWNER_ACCEPTANCE_EVIDENCED)
  --gate C5 + C5 (verbatim)--> PC5_PACKAGE_C_ACCEPTED                                    (terminal; next P3-5 step WRITE_HELD is NOT Package C)
any state: HALT event --> PC_HALT_MANUAL_RECOVERY (terminal);  REVALIDATE event --> same state, fresh gate required
PC1*: owner pre-C2 stop --> PC_STOPPED_BEFORE_OWNER_RECORD
```

| Act | Boundary | Writes | Requires | Ends at |
| --- | --- | --- | --- | --- |
| **C1** open (read-only only) | opens the sequence and the Package C freeze | the operator work directory; the S25 staging/evidence directory | pins exact at the control; opening facts (control, last DEV deploy, boot id) | `PC1_BOUND_KNOWN_EMPTY` after the binding (§3), the bundle transfer and the S25 C1 transcription |
| **C2** go | `APPEND_RECORD_1_REPLICA_A`, exactly one attempt | **Replica A record 1** (canonical `append`, owner-typed digest) | fresh gate C2 (§7); candidate re-derived; review package built *before* the append; peer = reviewed empty B view | `PC2_RECORD1_A_PARTIAL`, `FRESHNESS_UNKNOWN` |
| **C3** go | `APPEND_RECORD_1_REPLICA_B` on the S25, exactly one attempt, owner-run in Termux | **Replica B record 1** (canonical `append`) | fresh gate C3; T2 (Replica A view) verified on the phone; the phone re-derives the same candidate digest | `PC3_RECORD1_CURRENT`: AUTHENTIC + CURRENT, acceptance `NOT_PRESENT` |
| **C4** go | acceptance envelope 1: store A init, copy A (laptop), then store B init, copy B (S25); one attempt per copy | **envelope 1 in store A, then store B** (canonical `append-envelope`) | fresh gate C4; AUTHENTIC + CURRENT; envelope candidate digest bound in the go; copy B only after copy A is exactly `ACCEPTANCE_PARTIAL` | `PC4_ENVELOPE_COMPLETE` |
| **C5** acceptance | Package C acceptance; ends the freeze | the C5 record in the work directory only | fresh gate C5; CURRENT + `ACCEPTANCE_COMPLETE` | `PC5_PACKAGE_C_ACCEPTED`; authorizes nothing |

No act implies the next. Every arm requires its own fresh gate; a gate never carries over to the next act (tested).

## 3. Canonical chain-export binding (`pkgc_operator.py bind`)

**Why it exists.** The canonical tool needs a trust-input document (`LILITH_OWNER_FRESHNESS_TRUST_INPUTS`) and a
chain-export JSON array. Neither exists as an accepted artifact: Package B exported only the raw `chain/1.json` /
`witness.json` bytes (evidence only, OD-B10), and `mb9_owner_genesis_verify.py` deliberately did not use the tool's
input format. A hand-assembled trust document would be an unreviewed authority input. `bind` makes both inputs a
deterministic function of accepted bytes.

**Inputs (all read-only):**

1. **One fresh export** produced in *this* sequence: `mb9_operator.py chain-export <repo> <mb9-workdir>
   <pkgc-workdir>/exports/<new>` (the pinned Package B read-only form; R-B5 transport). It must be a NEW directory
   directly under the sequence's `exports/`; anything else is `EXPORT_NOT_IN_SEQUENCE` (so no historical Package B
   POST9B export or other stale copy is ever an input). Each export directory is consumed by exactly one binding or
   gate (`EXPORT_REUSED`). Freshness is per read, not per content: the genesis is immutable, so fresh exports are
   normally byte-identical.
2. The export must be exact (`check_export`): `w9verifier` exit 0, empty stderr, phase
   **`W9_5_GENESIS_COMMITTED_EXACT`**, no failures, every `evidence9b` item true, committed digest = the accepted
   genesis, `chain-1.json` SHA-256 = `252c3220…`, pointer = genesis bytes, the accepted incarnation, `NRestarts`
   exactly `"0"` (unknown is not zero), hold store `[]`, no signer later state, `registryEffective = false`,
   `authorityActive = authorityGranted = false`.
3. The owner-held installables (`authority-registry.v1.json`, `registry-root.json`, `witness-anchor.json`), exactly
   those three files, each hashing to its accepted pin.
4. P-A, exactly the three Package A files, each hashing to its accepted pin; the pin parses as `OwnerGenesisPinV1`
   (`dev`, `ac892dc2…`).
5. Replica A (read-only): the replica ID and record listing are bound.
6. The SHA-256 of two owner-held evidence documents the R1 package requires: `PR2_REVALIDATION` (the fresh C1
   read-only cloud capture) and `P3_3_INDEPENDENCE` (the accepted P3-3 storage/independence evidence).

**Outputs (create-only, `<workdir>/binding/`):**

| File | Content | Rule |
| --- | --- | --- |
| `trust-inputs.json` | RFC 8785 `{trustType, schemaVersion 1, environment dev, witnessAnchor, registryRoot, registries: [Registry V1]}` | the installable documents verbatim as parsed; nothing invented |
| `chain-export.json` | RFC 8785 `[<chain/1.json document>]` | genesis only |
| `genesis-pin.json` | the P-A pin bytes, unchanged | `35747736…` |
| `BINDING.json` | every input hash, every output hash, the W9 snapshot, Replica A's listing and manifest hash, the R1 evidence digests, the canonical tool's own view | `load_binding` re-hashes every output on every use (`BINDING_OUTPUT_CHANGED`) |

Before writing `BINDING.json` the operator runs the **canonical tool's own read** (`load_trust`, `inspect_chain`) on
the outputs and requires AUTHENTIC, one entry, genesis = head = the pin, no consumed authorization. The binding is
deterministic: two bindings over the same accepted bytes are byte-identical (tested).

```text
the binding is the only source of --trust, --chain and --pin for every Package C tool run (laptop and S25)
binding exact != record 1;  binding exact != CURRENT;  BINDING.json says freshness UNKNOWN
```

## 4. Points of no return

| PONR | Before | After | Recovery if interrupted |
| --- | --- | --- | --- |
| a C2 / C3 / C4 attempt marker (operator `arm`; phone `set -C` marker) | the go is unused | that go is consumed; whether the write happened is decided only by reading the copies | read-only classification (§7.3); never a second run under the same go |
| **record 1 in Replica A** (C2, P3-5 step 10) | the register is KNOWN_EMPTY | owner history exists: never overwritten, removed or re-proposed; a rejection would be terminal | C-14: append the same candidate to B (new C3 go); a pending file is C-15 manual |
| **record 1 in Replica B** (C3, step 11) | the partial state | AUTHENTIC + CURRENT for genesis; the owner has accepted the latest world | — (forward only) |
| **envelope 1 in store A** (C4 copy A, step 11a) | `ACCEPTANCE_NOT_PRESENT` | acceptance history exists | C-16a: the same envelope to store B |
| **envelope 1 in store B** (C4 copy B, step 11b) | `ACCEPTANCE_PARTIAL` | `ACCEPTANCE_COMPLETE` | — |

`reset()` is refused from `PC2_ARMED` onward (`OWNER_RECORD_PONR_PASSED`, tested): an armed state already counts,
because the marker exists before the write.

## 5. Peer views (why two machines can run one ceremony)

The canonical `append` and `append-envelope` read the target **and** the peer copy on one machine, and
`classify` / `compare-replicas` / `propose-envelope` read both replicas. Replica A never leaves the laptop and Replica
B never leaves the S25, and no SSH, ADB or sync exists between them (D6). Package C therefore uses **peer views**:

| View | Where | Built from | Stands for | Equality evidence |
| --- | --- | --- | --- | --- |
| `replica-b-0` | laptop work directory | the pinned Replica B manifest bytes, empty `records/` | Replica B before C3 | manifest SHA-256 `c068e533…` = the S25 C1 transcription; `records = 0` |
| A-view (T2) | S25 staging `~/lilith-pkgc/views/a/…/replica-a` | a byte copy of Replica A after C2 (deterministic tar) | Replica A | tar SHA-256 typed by the owner; `SHA256SUMS`; tree digest transcribed (`A_VIEW_TREE_SHA256`) |
| `replica-b-1` | laptop | the pinned manifest + Replica A's record-1 bytes | Replica B after C3 | the C3 transcription (`REPLICA_B_FILE`, `REPLICA_B_HEAD`, manifest hash); identical bytes by construction (tested) |
| `store-b-0` | laptop | the store-B manifest (`custodyCopyId = owner-offline-dev-synthetic-01`), empty | store B before copy B | — (store B does not exist yet; the S25 C1/C3 lines say `ABSENT`) |
| store-A view (T3) | S25 staging | a byte copy of store A after copy A, plus the review package | store A | tar SHA-256; `A_STORE_VIEW_TREE_SHA256` |
| `store-b-1` | laptop | the store-B manifest + store A's bundle bytes | store B after copy B | the C4 transcription (`STORE_B_MANIFEST_SHA256`, `ENVELOPE_DIGEST`, `COPIES_IDENTICAL`) |

Rules (tested): a view is a **read-only tool input**, never a replica or store of custody. It lives only in the
sequence work directory or the S25 staging directory, never at or under a replica or store path. The canonical tool
writes only its `--replica` / `--store` target, so no append ever writes a view (asserted after every append). A
view is never copied into a replica: copying between replicas by any means other than `append` stays forbidden (runbook
"Never"). A wrong view cannot create a wrong record. The record is re-derived from the binding's chain, trust and
pin, and a view only decides the replication class (`PEER_PENDING` / `REPLICAS_IDENTICAL`). An inconsistent view is
refused (`REPLICAS_NOT_APPENDABLE`, tested) and nothing is written.

## 6. Owner acts (DRAFT TEMPLATES; NOT ISSUED)

No template authorizes the next act. Placeholders `<...>` are bound at runtime by the operator from the files themselves (§12); none is typed. `<binding>` and `<gate>` are the SHA-256 of `BINDING.json` and of the last exact gate record for that act.

### 6.1 C1: open Package C (read-only only)

> I authorize opening the Package C (record 1 + acceptance envelope 1) live sequence now, for this current DEV_SYNTHETIC sequence only.
> Continuity: PACKAGE_C_CONTINUITY = OWNER_ATTENDED_EVENT_BOUNDED_SINGLE_SEQUENCE_THREE_OWNER_RECORD_BOUNDARIES.
> The Package C freeze begins now and holds through C2, C3, C4 and C5; no deploy, merge-triggered deploy, DEV change, witness restart or reboot is permitted inside this sequence.
> Control commit: <control>.
> Operator: services/owner-memory-control/tools/pkgc_operator.py SHA-256 <operator>.
> Owner freshness tool: services/owner-memory-control/lilith_owner_memory/owner_freshness_tool.py SHA-256 <freshness_tool>.
> Committed witness genesis digest: <genesis>. chain/1.json SHA-256: <chain1>.
> This authorizes opening the sequence, read-only evidence, the S25 read-only gate and the transfer of the reviewed bundle only. It does not authorize any owner-record write, record 1, the acceptance envelope, HELD, the signer, authority activation, First Memory or PROD.

### 6.2 C2: the APPEND_RECORD_1_REPLICA_A go

> I authorize APPEND_RECORD_1_REPLICA_A now for exactly one attempt within this current Package C sequence.
> Continuity: PACKAGE_C_CONTINUITY = OWNER_ATTENDED_EVENT_BOUNDED_SINGLE_SEQUENCE_THREE_OWNER_RECORD_BOUNDARIES.
> Control commit: <control>. Binding SHA-256: <binding>. Gate C2 SHA-256: <gate>.
> Target: Replica A <replica_a>. Peer: the reviewed empty Replica B view (SHA-256 <view>).
> Record 1 candidate digest: <record>. Review package digest: <package>.
> Committed witness genesis digest: <genesis> (= the owner pin).
> I have reviewed the candidate and repeat its digest by hand to owner_freshness_tool append.
> I understand that this is an owner-record write: record 1 on Replica A is never overwritten or removed, and freshness remains FRESHNESS_UNKNOWN until Replica B holds the identical record.
> This go does not authorize record 1 on Replica B, the acceptance envelope, HELD, the signer, authority activation, First Memory or PROD.
> Any REFUSED, FAILED, traceback, pending file or other STOP after the attempt marker consumes this go. There is no automatic retry.

### 6.3 C3: the APPEND_RECORD_1_REPLICA_B go (S25)

> I authorize APPEND_RECORD_1_REPLICA_B on the S25 now for exactly one attempt within this current Package C sequence.
> Continuity: PACKAGE_C_CONTINUITY = OWNER_ATTENDED_EVENT_BOUNDED_SINGLE_SEQUENCE_THREE_OWNER_RECORD_BOUNDARIES.
> Control commit: <control>. Binding SHA-256: <binding>. Gate C3 SHA-256: <gate>.
> Target: Replica B <replica_b>, run by me locally in Termux, with no SSH and no ADB. Peer: the reviewed Replica A view (SHA-256 <view>).
> S25 bundle SHA-256: <bundle>. Record 1 digest: <record> (the same record as Replica A).
> I understand that this is an owner-record write and that AUTHENTIC + CURRENT becomes possible only when Replica B holds exactly this record.
> This go does not authorize the acceptance envelope, HELD, the signer, authority activation, First Memory or PROD.
> Any REFUSED, FAILED, traceback, pending file or other STOP after the attempt marker consumes this go. There is no automatic retry.

### 6.4 C4: the acceptance envelope 1 go (copies A and B)

> I authorize acceptance envelope 1 now for exactly one attempt per copy within this current Package C sequence: store initialization, then APPEND_ENVELOPE_1_COPY_A on the laptop, then APPEND_ENVELOPE_1_COPY_B on the S25.
> Continuity: PACKAGE_C_CONTINUITY = OWNER_ATTENDED_EVENT_BOUNDED_SINGLE_SEQUENCE_THREE_OWNER_RECORD_BOUNDARIES.
> Control commit: <control>. Binding SHA-256: <binding>. Gate C4 SHA-256: <gate>.
> Freshness: AUTHENTIC + CURRENT for record 1 <record>, observed in this sequence.
> Envelope digest: <envelope>. Review package digest: <package>.
> Copy B runs only after copy A is exactly ACCEPTANCE_PARTIAL with this envelope.
> I understand that the envelope is owner-acceptance evidence only: it does not make freshness current, does not make Registry V1 effective, does not start the signer, does not write HELD and grants no authority.
> This go does not authorize HELD, the signer, authority activation, First Memory or PROD.
> Any REFUSED, FAILED, traceback, pending file or other STOP after a copy marker consumes that copy. There is no automatic retry.

### 6.5 C5: Package C acceptance (authorizes nothing)

> I accept Package C for this sequence: record 1 on Replica A and Replica B and acceptance envelope 1 on copies A and B are COMPLETED.
> Record 1 digest: <record>. Envelope digest: <envelope>. Binding SHA-256: <binding>.
> Freshness: AUTHENTIC + CURRENT. Acceptance: ACCEPTANCE_COMPLETE.
> REGISTRY_EFFECTIVE remains NO. AUTHORITY_ACTIVE remains NO. authorityGranted remains false. The signer remains inactive.
> This acceptance authorizes nothing further: not HELD, the signer, authority activation, First Memory or PROD. The Package C freeze ends now.

### 6.6 Owner pre-C2 stop

> I stop this Package C sequence now, before any owner-record write, for this current DEV_SYNTHETIC sequence only.
> Control commit: <control>. C1 record SHA-256: <c1>.
> No C2 attempt marker exists and no owner record was written by this sequence.
> This sequence is STOPPED / HISTORICAL / NON-REUSABLE. Its freeze is released; the release authorizes nothing.

## 7. Continuity, freeze and invalidation

`PACKAGE_C_CONTINUITY = OWNER_ATTENDED_EVENT_BOUNDED_SINGLE_SEQUENCE_THREE_OWNER_RECORD_BOUNDARIES` (proposed,
OD-C1): one fresh evidence sequence; one freeze from C1 to C5; no wall-clock TTL; material uncertainty or drift ⇒
REVALIDATE / STOP (ADR-0015); a technical PASS never implies the next go.

**Freeze.** From C1 until C5 (or the pre-C2 stop): no deploy, no merge-triggered deploy, no manual DEV change, no
package upgrade, no witness stop/start/restart, no reboot, no signer action. The first deploy after C5 must again show
`W9_5_GENESIS_COMMITTED_EXACT` and compare `EQUAL` to the accepted running-witness phase-bound DR-5 target. Record 1
and the envelopes are not host-observable, so Package C adds no DR-5 line.

### 7.1 What must remain unchanged (binding → C5, in particular between record 1 on A and on B)

| Fact | Source at each gate |
| --- | --- |
| control commit; operator, `owner_freshness_tool` and the pinned Package B read tools | `pins`; the C1 record |
| the binding (`BINDING.json` and its three outputs) | `load_binding` re-hash |
| the candidate record-1 digest and bytes (A, the phone's re-derivation, B) | the C2 marker values; the phone's `propose-genesis`; the transcription |
| W9 phase `W9_5_GENESIS_COMMITTED_EXACT`; committed digest `ac892dc2…`; `chain/1.json` = `witness.json` `252c3220…`; chain = genesis only | a fresh in-sequence export |
| witness incarnation (InvocationID `5136ea7a…`, MainPID `143946`) and `NRestarts = 0` | the same export |
| boot id; `REBOOT_REQUIRED = absent` | the read-only `host` form |
| the last DEV deploy run id; an empty workflow queue | `gh run list` (read-only) |
| hold store empty; signer inactive with no runtime path; `registryEffective = false`; `authorityGranted = false` | the export |
| Replica A = exactly the expected records; Replica B = exactly the expected records; no pending file | `verify-replica` (laptop); the transcription (S25) |
| P-A and P-B = the three accepted files | `bind`; the phone's `cmp` / hashes |
| the S25 bundle tar SHA-256 | the `S25_BUNDLE.json` record; the phone's `sha256sum -c` |

### 7.2 Invalidators

| Event | Route | Meaning |
| --- | --- | --- |
| `DEPLOY_OCCURRED`, `WORKFLOW_QUEUE_NOT_EMPTY`, `CONTROL_CHANGED`, `TOOL_PIN_CHANGED` | REVALIDATE | freeze breach or drift: STOP the act; a fresh gate, and after a consumed marker a new go |
| `WITNESS_INCARNATION_CHANGED`, `WITNESS_RESTARTED` | REVALIDATE | the witness is not the accepted incarnation: STOP; separately reviewed re-acceptance first |
| `BOOT_ID_CHANGED`, `REBOOT_REQUIRED_PRESENT` | REVALIDATE (global invalidator) | STOP; the P3-5 §12 re-baseline before anything else |
| `W9_PHASE_NOT_EXACT`, `S25_BUNDLE_MISMATCH`, `TRANSCRIPTION_MISMATCH` | REVALIDATE | STOP; read again; never act on a partial read |
| `EVIDENCE_UNKNOWN` (a missing, unparseable or unexpected fact) | REVALIDATE | **UNKNOWN is never equality and never success** |
| `GENESIS_MISMATCH`, `CHAIN_ADVANCED`, `CHAIN_BYTES_CHANGED` | **HALT** | lineage drift: never accept; manual recovery (`REBOOTSTRAP_FORBIDDEN` / `AHEAD_UNACCEPTED` are outside Package C) |
| `OWNER_RECORD_INCONSISTENT`, `REPLICA_PENDING_WRITE`, `ACCEPTANCE_PENDING_WRITE`, `ACCEPTANCE_CONFLICTING`, `PIN_BYTES_CHANGED` | **HALT** | owner-record inconsistency: STOP; the owner inspects; nothing is deleted, repaired or rewritten |
| `HOLD_STORE_NOT_EMPTY`, `SIGNER_ACTIVE`, `AUTHORITY_GRANTED`, `REGISTRY_EFFECTIVE` | **HALT** | an authority boundary moved outside Package C |

Two observations are also HALT, because they cannot happen in a correct sequence: CURRENT after Replica A alone, and
anything other than `[record 1]` / `[]` after C2 (tested). Any event not in the tables is treated as
`EVIDENCE_UNKNOWN` (tested).

### 7.3 Retry and recovery after an attempt marker

There is **no automatic retry**, ever. After a marker, the outcome is classified read-only:

| Observed copy after the attempt | Classification | Next |
| --- | --- | --- |
| exactly the expected new record / envelope, no pending file | the write happened (also when the tool's reply was lost) | continue to the next observation; never run the same append again (the tool would refuse anyway: `RECORD_EXISTS` / `REPLICAS_NOT_APPENDABLE` / `ENVELOPE_EXISTS`) |
| unchanged, no pending file | no write; that go is consumed | STOP; a new sequence (new C1, fresh evidence) may resume (below); a new go is required |
| a `.pending-*` file | C-15 / `ACCEPTANCE_PENDING_WRITE` | HALT, manual; never auto-deleted |
| anything else | inconsistency | HALT |

**Resumption.** A STOP never undoes an owner record. A new sequence opens with a fresh C1 and a fresh binding, and its
read-only opening observation decides where it starts. Only the canonical recoverable states are accepted:
`EMPTY` → `PC1_BOUND_KNOWN_EMPTY`; `A_ONLY` (C-14) → `PC2_RECORD1_A_PARTIAL`; `AB_NO_ENVELOPE` (C-16) →
`PC3_RECORD1_CURRENT`; `ENVELOPE_A_ONLY` (C-16a) → `PC4_ENVELOPE_A_PARTIAL`. Anything else (for example B ahead
of A) is HALT (tested). The canonical tool's own semantics are what permit these continuations: `append` accepts
"peer = target + candidate", and `append-envelope` accepts "peer = target + envelope".

## 8. S25 procedure

### 8.1 Rules

- **Owner-run, locally, in Termux.** No SSH, no ADB, no USB debugging, no Developer options, no network transfer, no
  cloud share. `sshd` is not running.
- **Transport:** a USB cable in **File transfer (MTP)** mode, **only for the copy**, then disconnected
  (P3-3B §3). Files land in `Download`, which is transport only. `termux-setup-storage` is a prerequisite and is not
  part of the script.
- **Only the reviewed artifacts travel:** T1 the bundle (§8.2), T2 the Replica A view, T3 the store-A view plus the
  review package. Nothing else. Nothing travels from the phone to the laptop except the owner's transcription.
- **G0 `cryptography` preinstall check:** major version within the P3-3B range **and** a live Ed25519
  sign/verify self-test. This slice, unlike P3-3B, executes signature verification on the phone. Missing or failing
  means STOP; installing it is a separate owner decision (OD-C8).
- **Exact checksums before execution:** the tar SHA-256 is typed by the owner and checked with `sha256sum -c`, then
  every member is checked against the bundle's `SHA256SUMS`, at the start of **every** stage.
- **Bundle source:** the canonical tool's import closure **at the Package C control** (15 files, pinned by a test
  to the computed import closure). **The P3-3B bundle (`44a53f2`) must not be used**: it predates B-3 and the
  burned-identity refusal (OD-C9).
- **Paths:** Replica B `$HOME/lilith-owner-offline-dev-synthetic-01` (canonical, not nested); P-B
  `$HOME/lilith-genesis-pin-dev-synthetic`; store B `$HOME/lilith-owner-acceptance-offline-dev-synthetic-01`
  (sibling, never inside the replica); staging `$HOME/lilith-pkgc`.

### 8.2 Bundle and transfers (laptop, deterministic)

| Transfer | Form | Content | When |
| --- | --- | --- | --- |
| T1 `lilith-pkgc-bundle.tar` | `pkgc_operator.py s25-bundle <repo> <workdir> <vendor-dir> <out>` | `src/` closure at the control, `vendor/` (fido2 2.2.1, rfc8785 0.1.4, pure Python), `binding/` (the four binding files), `pkgc_s25_phone.sh`, `SOURCE_COMMIT`, `SHA256SUMS` | after `bind`, inside C1 |
| T2 `lilith-pkgc-replica-a.tar` | `transfer <workdir> replica-a <paths> <out>` | `replica-a/REPLICA.json`, `replica-a/records/000001-<d>.json` | after C2 is observed, before gate C3 |
| T3 `lilith-pkgc-store-a.tar` | `transfer <workdir> store-a <paths> <out>` | `store-a/…`, `package.json` | after copy A is observed `ACCEPTANCE_PARTIAL` |

Every tar: sorted names, mtime 0, owner 0:0, modes 0644/0755, a top-level `SHA256SUMS`. Its SHA-256 and tree digest
are recorded create-only in the work directory.

### 8.3 Phone commands

[`pkgc_s25_phone.sh`](../../services/owner-memory-control/tools/pkgc_s25_phone.sh) (in the bundle). The owner sources
it and runs **one** stage function per owner act, typing the laptop-shown values by hand:

| Function | Act | Mutation | Gates before any write |
| --- | --- | --- | --- |
| `pkgc_c1` | C1 | none (staging and evidence directories only) | G0, bundle, P-B exact and = bound pin, `inspect-chain` AUTHENTIC, Replica B verifies |
| `pkgc_c3` | C3 | `append` to Replica B, once | everything in C1, plus: A-view verified; Replica B has 0 records; the phone's own `propose-genesis` digest equals the typed record digest; noclobber marker `attempt-C3` |
| `pkgc_c4` | C4 copy B | `init-acceptance-store` (store B), then `append-envelope`, once | everything in C3, plus: the store view verified; the phone classifies AUTHENTIC + CURRENT; store B absent; noclobber marker `attempt-C4-B`; the phone's own `propose-envelope` digest equals the typed envelope digest |

The digest passed to `--confirm-digest` is the owner-typed value, so the owner repeats it by hand (PR3-D2). It is
never generated on the phone.

### 8.4 Evidence class: `OWNER_SCREEN_TRANSCRIPTION`

Each stage prints a fixed, ordered result block and then `RESULT_BLOCK_SHA256=<sha256 of the block>`. The owner
transcribes the block from the screen. `s25-check` requires **exact ordered equality** with the expectation the
laptop derives from its own evidence (the bundle record, Replica A's record 1, the tree digests, store A's envelope),
**plus** the block hash. A missing, extra, reordered or altered line, or a wrong hash, is
`PKGC_S25_TRANSCRIPTION_MISMATCH` (tested). The block hash catches transcription errors; it authenticates nothing.
The phone result is owner-observed, not machine-captured. No stronger mechanism (for example an MTP copy-back of
the phone evidence) is designed or authorized here (OD-C3).

## 9. Freshness semantics (canonical tool, unchanged; enforced by tests)

| Point | Register | Freshness | Gated operations | Acceptance |
| --- | --- | --- | --- | --- |
| before C2 | `OWNER_REGISTER_EMPTY` (two empty replicas: A + the transcription-backed B) | `FRESHNESS_UNKNOWN` | all blocked | — |
| after C2 (A only) | `REPLICAS_DIVERGENT … PREFIX` | **`FRESHNESS_UNKNOWN`** (CURRENT here is a HALT) | **all `FRESHNESS_BLOCKED`** | `propose-envelope` refuses (`OWNER_REGISTER_NOT_VERIFIED`) |
| after C3 (A = B) | `OWNER_REGISTER_VERIFIED` | **AUTHENTIC + CURRENT** (first possible here) | met (meeting a gate authorizes nothing) | `ACCEPTANCE_NOT_PRESENT` |
| after C4 copy A | unchanged | CURRENT (unchanged) | unchanged | `ACCEPTANCE_PARTIAL` |
| after C4 copy B | unchanged | CURRENT (unchanged) | unchanged | `ACCEPTANCE_COMPLETE` |

- **AUTHENTIC + CURRENT is impossible until Replica B holds the identical record 1.** The P3-5 `load_register`
  prefix rule makes the one-replica state UNKNOWN (tested end to end with the canonical tool).
- **The envelope never makes freshness current.** CURRENT depends only on the freshness records. An out-of-band
  envelope written while only A holds record 1 leaves freshness `FRESHNESS_UNKNOWN` and acceptance not `COMPLETE`
  (tested). The sequencer refuses any envelope step from `OWNER_RECORD_PARTIAL` (tested).
- **The tests drive the accepted P3-5 sequencer** (`BootstrapSequencerV1`) from `WITNESS_GENESIS_COMMITTED` through
  steps 10, 11, 11a and 11b, using the real classification results. It ends at `OWNER_ACCEPTANCE_EVIDENCED`, and
  `WRITE_HELD` is never invoked.

## 10. Acceptance envelope 1

- **Binds** (P3-6 §1, unchanged): `freshnessRecordVersion = 1`, `freshnessRecordDigest` = record 1,
  `decision = ACCEPT_CURRENT`, `previousAcceptanceEnvelopeDigest = null`, `genesisPinDigest` (the bound pin),
  `ownerReviewPackageDigest` (the R1 package built **before** C2 from Replica A and the empty B view, with the
  `PR2_REVALIDATION` and `P3_3_INDEPENDENCE` digests from the binding), `replicaSetDigest` (the two replica IDs),
  `ceremonyVersion`, and `acceptanceMethod = EXPLICIT_OWNER_DIGEST_CONFIRMATION`. It has no timestamp, no signature
  and no path.
- **The same envelope digest on both copies.** The laptop's `propose-envelope` and the phone's `propose-envelope`
  (from Replica B, the A-view, store B and the transferred package) must yield the C4-go digest. The phone refuses
  otherwise. The **bundle files** on copies A and B are **byte-identical** (tested). The stores' `ACCEPTANCE.json`
  manifests differ by design (`custodyCopyId`).
- **Partial vs complete:** `ACCEPTANCE_PARTIAL` after copy A, `ACCEPTANCE_COMPLETE` after copy B. Any other state
  after a copy is HALT (tested). C5 requires COMPLETE + CURRENT.
- **No widening:** the envelope is evidence of one past owner decision. It does not make freshness current, does
  not make Registry V1 effective, does not start the signer, does not write HELD, and grants no authority. The C4 go
  states this verbatim.

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
signer, activation, release or First Memory transition (tested by name). After `PC5` the only next action is
"none": HELD (M-B10), the signer, activation, First Memory and PROD each need their own later authorization.

**First Memory boundary.** Tooling must not infer, choose, draft or write LILITH's First Memory merely because later
bootstrap stages become technically ready. If the system eventually reaches `FIRST_MEMORY_READY`, the process
**STOPS** there. Owner discussion is required before any First Memory content is selected or written.

## 12. Tooling

**Reused unchanged:** `owner_freshness_tool` (`propose-genesis`, `build-review-package`, `append`, `classify`,
`compare-replicas`, `verify-replica`, `init-acceptance-store`, `propose-envelope`, `append-envelope`,
`classify-acceptance`, `inspect-chain`), `pr1b_sequencing`, `owner_acceptance`, and the pinned `mb9_operator.py`
(`chain-export`, `host`, `health`; read-only forms only) with `mb9_witness_verifier.py` and
`mb9_owner_genesis_verify.py`. No accepted semantics change.

**Added (thin, justified):** `services/owner-memory-control/tools/pkgc_operator.py`. It exists only because two
binding gaps cannot be closed with the existing tools: (1) the trust-input and chain-export documents must be
derived deterministically from accepted bytes and a fresh export (§3); (2) the canonical tool needs both copies on
one machine (§5). Everything else in it is sequencing discipline: gates, markers, derived go values, and the
transcription check. Forms: `pins`, `open`, `bind`, `gate`, `peer-view`, `transfer`, `s25-bundle`, `s25-expect`,
`s25-check`, `arm`, `record`.

- **It writes no owner record.** It never calls `append`, `append-envelope`, `init-acceptance-store` or any
  replica writer (AST-tested). It writes only its work directory, the binding, views, transfer tars and markers.
- **Go values are derived from files, never typed:** the record digest from the candidate file (checked as record 1
  of this genesis), the package digest from the package (checked: `RECORD_1`, this record, the bound evidence), the
  view digests from the trees, and the envelope digest from the envelope candidate (checked against this record and
  package). A go with any other value is `GO_LINE_MISSING` (tested).
- **It contacts nothing:** no DEV, S25, network, `gcloud`, `ssh`, `plink`, `systemctl` or socket (tested). DEV
  reads stay in the pinned `mb9_operator.py`.
- `services/owner-memory-control/tools/pkgc_s25_phone.sh`: the only S25 commands. It is static-tested for no
  SSH/ADB/network/package install/deletion, exactly three write commands (`append`, `init-acceptance-store`,
  `append-envelope`), noclobber markers before them, and its emitted keys equal the expectation.

### 12.1 Runbook (laptop; WSL; outside every Git tree and replica parent)

1. **C1** (owner text). `pkgc_operator.py pins <repo>`, then `open <repo> <workdir> <C1.txt> <facts.json>`. Fresh
   read-only evidence: cloud captures (the `PR2_REVALIDATION` digest), `mb9_operator.py host … POST9B`, `health`,
   `gh run list`, then `mb9_operator.py chain-export … <workdir>/exports/e1`. Then `bind … <workdir>/exports/e1
   <replica-a> <pr2> <p33>`, `s25-bundle`, and T1 (MTP). On the phone: `pkgc_c1`. Then `s25-check <workdir> C1 …`.
   With Replica A verified empty, the result is `KNOWN_EMPTY`.
2. **C2 preparation** (read-only plus candidate files). `peer-view replica-b-0`, `propose-genesis`, and
   `build-review-package` (Replica A + the B view; `--evidence PR2_REVALIDATION=… P3_3_INDEPENDENCE=…`). Then a fresh
   export `e2` and `gate C2`.
3. **C2 go** (owner text). `arm <workdir> C2 <go> <paths>`. The owner runs the one `append --replica <A> --peer
   <B view>`, typing the digest. Then `verify-replica`, `classify` (A + B view): `FRESHNESS_UNKNOWN`, every gate
   blocked.
4. **C3 preparation.** `transfer replica-a` (T2, MTP), a fresh export `e3`, `gate C3`.
5. **C3 go** (owner text). `arm C3`. On the phone: `pkgc_c3`. On the laptop: `s25-check C3`, `peer-view replica-b-1`,
   then `compare-replicas` and `classify` (A + B view): AUTHENTIC + CURRENT.
6. **C4 preparation.** `init-acceptance-store` for store A (laptop), `peer-view store-b-0`, `propose-envelope`
   (A + B view; store A + store-B view), a fresh export `e4`, `gate C4`.
7. **C4 go** (owner text). `arm C4`. The owner runs `append-envelope --store <A> --peer-store <store-B view>`, then
   `classify-acceptance`: `ACCEPTANCE_PARTIAL`. Then `transfer store-a` (T3, MTP). On the phone: `pkgc_c4`. On the
   laptop: `s25-check C4`, `peer-view store-b-1`, `classify-acceptance`: `ACCEPTANCE_COMPLETE`.
8. **C5** (owner text). A fresh export `e5`, `gate C5`, then `record <workdir> C5 <C5.txt> <paths>`. The freeze
   ends.

Before C2 only, the owner may instead stop the sequence (§6.6, `record … STOP`). The operator refuses the stop once
any attempt marker exists.

## 13. Tests

`services/owner-memory-control/tests/test_b1b3e_pkgc_record1_envelope.py` (TEST_ONLY, temporary directories, real
K-WIT-signed TEST chains, the canonical tool via `owner_freshness_tool.run`):

| Class | Covers |
| --- | --- |
| `StateMachineTests` | full C1→C5 path; order; a fresh gate per arm; one attempt per go; A-only partial and UNKNOWN (CURRENT after A = HALT; a boolean is never freshness); CURRENT only after B; the envelope needs CURRENT; partial vs complete; every REVALIDATE and HALT event; unknown events ⇒ revalidate; PONRs and reset; the pre-C2 stop; resumption only at canonical points; mapping onto P3-5 steps 10–11b, with `WRITE_HELD` next and outside |
| `BindingTests` | exact, deterministic binding the canonical tool reads AUTHENTIC; no stale or foreign export; every export check; accepted installable and pin bytes; tamper evidence; no partial write on refusal |
| `ContinuityTests` | fresh gates; no export reuse; each invalidator and its route; the last gate must be exact and for this stage |
| `CeremonyTests` | **end to end** on two simulated machines: binding → S25 C1 → C2 (`PEER_PENDING`, UNKNOWN, all gates blocked, envelope refused) → T2 → C3 on the "S25" (`REPLICAS_IDENTICAL`, CURRENT) → transcription → B view → CURRENT on the laptop → C4 copy A (`PARTIAL`, freshness unchanged) → T3 → copy B (`COPIES_IDENTICAL`, byte-identical bundles, `COMPLETE`) → C5, with the P3-5 sequencer driven in step; an envelope never makes freshness current; a wrong peer view is refused and writes nothing |
| `S25Tests` | exact ordered transcription plus the block hash; per-stage expectations; the phone script's emitted keys; the phone script's boundary; the S25 closure = the computed import closure; deterministic tars |
| `BoundaryTests` | the operator writes no owner record and has no authority form; tool pins = merged bytes; the go templates never authorize more; the accepted pins = the Package A/B records; this record's boundary lines and verbatim templates |

## 14. Owner decisions requested (proposed; none accepted)

| # | Decision |
| --- | --- |
| OD-C1 | `PACKAGE_C_CONTINUITY = OWNER_ATTENDED_EVENT_BOUNDED_SINGLE_SEQUENCE_THREE_OWNER_RECORD_BOUNDARIES`, with the C1–C5 freeze (§7) |
| OD-C2 | peer views (§5) as read-only tool inputs. The A-view and store-A view stay in S25 staging as evidence after Package C, never at a replica or store path. This places a byte copy of record 1 (public-safe owner data) in phone staging, which is not a custody copy |
| OD-C3 | the S25 evidence class is `OWNER_SCREEN_TRANSCRIPTION` with the result-block hash. No MTP copy-back is designed |
| OD-C4 | C4 = one go, with store initialization and one attempt per copy, ordered A then B. Store paths as in §8.1 and the laptop sibling `/root/lilith-owner-acceptance-primary-dev-synthetic-01` |
| OD-C5 | resumption by a new sequence at the canonical recoverable points only (§7.3) |
| OD-C6 | export freshness by a new in-sequence directory per read, plus the incarnation, phase and boot facts, not by content |
| OD-C7 | the `PR2_REVALIDATION` evidence is the C1 fresh read-only cloud capture; `P3_3_INDEPENDENCE` is the accepted P3-3 evidence digest |
| OD-C8 | `cryptography` must already be installed in Termux; G0 STOPs otherwise; installing it is a separate owner decision |
| OD-C9 | the S25 runs only the Package C bundle at the control. The P3-3B `44a53f2` bundle is retired for writes |

## 15. Hidden assumption

> What assumption could make Package C appear safe while it is wrong?

1. **"The phone and the laptop each see their own replica, so the tool's two-replica checks still hold."** Not by
   themselves: each machine sees one real copy and one view. Safety rests on (a) the record being re-derived from
   the bound chain, trust and pin, not from the view; (b) the view being hash-equal to the real copy, with the
   evidence named per view (§5); and (c) a wrong view being refused before any write. A view is evidence of
   equality, never custody.
2. **"An export is fresh if its bytes are right."** Rejected: right bytes are expected forever, since the genesis is
   immutable. Freshness is the read itself: a new directory under this sequence, bound to the incarnation, phase,
   boot and deploy facts.
3. **"The envelope completes acceptance, so the world is current."** Rejected: CURRENT comes only from the two
   identical records. The envelope is evidence of a past decision (P3-6 §14).
4. **"The phone printed CURRENT, so it is CURRENT."** The phone's output reaches the laptop only as owner
   transcription. The laptop independently reconstructs B from the transcription-checked hashes and classifies
   CURRENT itself. Both must agree.

## 16. Nonclaims

This slice does **not** establish record 1, any envelope, an acceptance store, CURRENT freshness, owner acceptance
of anything, HELD, signer readiness, Registry V1 effectiveness, authority activation, A1–A7, First Memory readiness,
PROD readiness or whole-host rollback resistance. The operator is not a verifier of DEV state: it trusts the pinned
W9 verifier's report as read-only evidence and refuses anything inexact.

## 17. State

```text
PACKAGE_C = DESIGN / REPOSITORY ONLY (DOCS + OPERATOR + PHONE SCRIPT + TESTS); NOT MERGED; NOT RUN
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
