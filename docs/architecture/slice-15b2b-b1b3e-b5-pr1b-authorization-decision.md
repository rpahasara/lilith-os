# Slice 15B2b-B1b-3e — B-5: PR-1B Owner Authorization Decision Packet

Status:

- **`B5_OWNER_AUTHORIZATION_DECISION_READY`**. The packet is prepared for
  the owner's decision. **No decision is recorded.**
- **B-5 is OPEN. PR-1B is NOT AUTHORIZED.** `pr1bAuthorized` is not set
  anywhere. It is an owner-asserted eligibility input, not a source flag,
  and nothing here persists it.
- There is no M-B1, no real K-ROOT, K-WIT, registry v1, genesis pin, or
  record 1. Real freshness is `FRESHNESS_UNKNOWN`. First Memory is not
  authorized.
- There was no DEV mutation, no phone contact, and no replica change. This
  packet is read-only evaluation plus documentation.

```text
B-5 GRANTED != M-B1 go != K-ROOT exists != freshness CURRENT != First Memory
```

| Field | Value |
| --- | --- |
| Control `main` | `cfa0b3e542e821ae2d4a3bb4ba0f198ee9e6fb58` (merge of PR #121: B-3) |
| Governing records | [PR-1B eligibility review](slice-15b2b-b1b3e-pr1b-eligibility-review.md) §8; [P3-5 sequencing](slice-15b2b-b1b3e-pr3-pr1b-bootstrap-sequencing.md); [B-4 custody decision](slice-15b2b-b1b3e-b4-kroot-custody-decision.md) |

## 1. Eligibility inputs (current state)

| Precondition | Blocker | State | Evidence |
| --- | --- | --- | --- |
| `p33Complete` | — | TRUE | [P3-3 acceptance](slice-15b2b-b1b3e-pr3-p33-storage-acceptance.md) (`P3_3_COMPLETE`), with the Replica B path [erratum](slice-15b2b-b1b3e-pr3-p33-storage-acceptance.md) |
| `twoRealReplicasExist` | — | TRUE | P3-3 acceptance §1–§2 |
| `replicasCapabilityAdmitted` | — | TRUE | P3-3 acceptance (Replica B `RENAME_NOREPLACE_V1`) |
| `replicaIndependenceEstablished` | — | TRUE | P3-3 acceptance §3 |
| `replicasAgentUnreachableCopy` | — | TRUE | P3-3 acceptance §4. Replica B has no routine agent write path while the phone stays disconnected |
| `ownerRegisterKnownEmpty` | — | TRUE | **Replica A**: checked read-only for this packet: 0 records, manifest `fbdd045c…`. **Replica B**: 0 records, manifest `c068e533…`, byte-identical across the accepted [B-4 run 2](slice-15b2b-b1b3e-b4-termux-kroot-rehearsal-acceptance.md). It was not contacted here |
| `pr3ToolingAccepted` | B-1 | TRUE | [PR-3 tooling acceptance](slice-15b2b-b1b3e-pr3-tooling-acceptance.md) |
| `pr1aBaselineValid` | — | TRUE | PR-1A accepted; `status --expect P1A-9` PASS in the [pre-B5 PR-2 revalidation](slice-15b2b-b1b3e-pr2-pre-b5-revalidation.md) |
| `pr2InventoryRevalidated` | — | TRUE **for its window** | pre-B5 PR-2 revalidation PASS (`18:51–18:57Z`). P3-5 §13 requires another read-only revalidation **immediately before `CHECK_ELIGIBILITY`** (§11) |
| `noUnreviewedTopologyChange` | — | TRUE **as of this packet** | since that window: the `11c47dc` DEV deployment (run `36617360613`), whose DR-5 result set equals the accepted run exactly (156 lines). The `cfa0b3e` deployment has **not yet run**, and its result must be checked (§11) |
| `openRisksAcknowledged` | B-2 | TRUE | [open-risk acknowledgement](slice-15b2b-b1b3e-open-risk-acknowledgement.md) |
| `pr1bAuthorized` | **B-5** | **FALSE** | this decision |

**Review blockers outside the function** (all CLOSED):

- **B-3:** the real-acceptance gate, merged at `cfa0b3e`
  ([record](slice-15b2b-b1b3e-b3-real-acceptance.md)).
- **B-4:** custody topology and the Termux rehearsal
  ([decision](slice-15b2b-b1b3e-b4-kroot-custody-decision.md),
  [acceptance](slice-15b2b-b1b3e-b4-termux-kroot-rehearsal-acceptance.md)).

`REAL_ACCEPTANCE_ENABLED = True`, and burned identities are refused on the
real path.

## 2. Eligibility evaluation (in memory, `main` source)

This is `evaluate_eligibility` from `cfa0b3e`, run in WSL. The inputs are
every precondition above set True, with only `pr1bAuthorized` varied.
Nothing is persisted.

```text
REAL_ACCEPTANCE_ENABLED = True | block(DEV_SYNTHETIC) = None
pr1bAuthorized=False: PR1B_NOT_ELIGIBLE reasons=('PR1B_NOT_AUTHORIZED',) | CHECK_ELIGIBILITY -> REFUSED PR1B_NOT_ELIGIBLE, state=PR1B_INELIGIBLE
pr1bAuthorized=True:  PR1B_ELIGIBLE     reasons=()                         | CHECK_ELIGIBILITY -> ADVANCED, state=PR1B_ELIGIBLE
   GENERATE_K_ROOT (M-B1) without evidence -> REFUSED EVIDENCE_MISSING offHostWorkstation,kRootFingerprintRecordedOffHost
```

**The only unmet precondition is `PR1B_NOT_AUTHORIZED`.**

**No technical blocker remains besides B-5** for the authorization
decision itself. Execution still needs the §5 prerequisites.

## 3. Exact effect of `pr1bAuthorized = True`

**In code**, it is the last input that turns `evaluate_eligibility` to
`PR1B_ELIGIBLE`. That lets the sequencer's `CHECK_ELIGIBILITY` (P1B-0)
advance to `PR1B_ELIGIBLE`. **Nothing else reads it.**

- It sets no source flag.
- It starts no service.
- It creates no key.
- It changes no replica.
- It does not satisfy any later step's evidence. Each of M-B1..M-B15 keeps
  its own evidence and gates.

**In governance**, the owner authorizes PR-1B, the DEV_SYNTHETIC bootstrap
M-B1 … M-B15, to proceed in the accepted order. Every step is still
individually reviewed and owner-driven.

## 4. What becomes permitted, and what does not

**Permitted after `B5_OWNER_AUTHORIZATION=GRANTED`:**

1. preparing and reviewing the **real M-B1 ceremony package**: a bundle
   built from merged `main`, a phone operator script, stop conditions, and
   an evidence plan. This is not execution;
2. the fresh read-only PR-2 revalidation and the P1B-0
   `CHECK_ELIGIBILITY` evaluation;
3. **only after a separate, explicit owner M-B1 go statement (§12):**
   M-B1 on the S25, and then each later step in order, each under its own
   reviewed procedure.

**Still NOT permitted after B-5:**

- M-B1 without the reviewed package and the separate owner go statement;
- skipping, reordering, or repeating any PR-1B step;
- running M-B2 without a PR-2 revalidation immediately before it;
- any real `append` / `append-envelope` before the sequence reaches
  `APPEND_RECORD_1_REPLICA_A` (after M-B9b);
- claiming freshness `CURRENT` before record 1 is on both replicas;
- First Memory, A1–A7, activation, or memory issuance (RR-39: issuance
  stays unwired);
- anything in PROD;
- K-ROOT on the laptop or on DEV;
- any reuse of a burned identity.

## 5. Post-B-5 sequence (beginning with M-B1)

Order (P3-5): `CHECK_ELIGIBILITY` (P1B-0) → **M-B1 `GENERATE_K_ROOT`** →
M-B2 `GENERATE_K_WIT` → M-B3 `SIGN_REGISTRY_V1` → M-B4+M-B5 → M-B6 → M-B7 →
**M-B8 `PIN_GENESIS`** → M-B9a → **M-B9b `COMMIT_WITNESS_GENESIS`** →
record 1 (Replica A, then B) → envelope → M-B10 … M-B15.

**Before M-B1 (prerequisites, none started):**

1. The real M-B1 package is prepared, reviewed, and merged:
   - `root-keygen` from a merged SHA;
   - the output path in Termux private storage, outside the replicas and
     the rehearsal directories;
   - a transcript;
   - a phone-side pre-transfer hash;
   - the burned-identity comparison of the new `publicKeySha256`.
2. The `cfa0b3e` DEV deployment has run, and its DR-5 result set equals
   the accepted run.
3. A fresh read-only PR-2 revalidation immediately before
   `CHECK_ELIGIBILITY` returns PASS.
4. `CHECK_ELIGIBILITY` is evaluated with the owner's `pr1bAuthorized =
   True`.
5. The owner gives the separate M-B1 go statement (§12).

**M-B1 itself** (evidence `offHostWorkstation`,
`kRootFingerprintRecordedOffHost`):

- `root-keygen` runs **on the S25 in Termux**.
- The passphrase is typed only on the phone.
- It writes exactly one encrypted PKCS#8 K-ROOT file (`O_EXCL`, `0600`).
- It prints the `TrustedRegistryRootV1` anchor and `publicKeySha256`.
- The owner records the fingerprint on the phone. That is the
  authoritative copy (E-21).
- The laptop gets a public working copy only.

## 6. Irreversible consequences beginning at M-B1

| Point | Consequence |
| --- | --- |
| during M-B1, before the fingerprint is recorded | C-2 `SAFE_RETRY`: discard and regenerate off-host, before any use |
| **end of M-B1** (fingerprint recorded off-host, E-21) | **K-ROOT becomes a custody commitment.** A second `root-keygen` makes a different key, which the M-B4 anchor equality catches. Losing K-ROOT before M-B3 means regenerating; after binding, there are no transitions and a re-bootstrap (R-1) |
| M-B2 | `PONR_CUSTODY`: private K-WIT material exists |
| M-B3 | K-ROOT signs registry v1: the first real K-ROOT signature |
| M-B8 | the genesis pin is immutable (`PONR_RECORD`) |
| M-B9b | the lineage is committed (`PONR_LINEAGE`). A mismatch with the pin is C-12 `REBOOTSTRAP_FORBIDDEN`: STOP |
| record 1 | `PONR_OWNER_RECORD`: create-only on both replicas |

**Any time:** phone compromise is K-ROOT compromise and requires **STOP**.
Phone loss after lineage binding may require a re-bootstrap.

## 7. Owner custody obligations (binding if granted)

1. **K-ROOT exists only in S25 Termux private storage.** There is no laptop
   copy, no DEV copy, and no backup (Option A1). Any copy the owner makes
   must be recorded; an unrecorded copy is custody debt or a suspected
   compromise.
2. **The K-ROOT passphrase is entered only on the S25.** It is never typed,
   stored, or pasted on the agent-reachable laptop.
3. **All 12 rehearsal identities stay permanently burned:**
   - [hold record](slice-15b2b-b1b3e-b4-termux-kroot-rehearsal-evidence-hold.md)
     §4;
   - [acceptance](slice-15b2b-b1b3e-b4-termux-kroot-rehearsal-acceptance.md)
     §4.
4. **No real identity may match a burned identity.** That covers K-ROOT,
   K-WIT, registry v1, and the genesis digest. The tool refuses them
   mechanically on the owner-freshness path (B-3), and the M-B1 and later
   reviews also compare by hand.
5. **Replica B stays independent and offline**, except for deliberate
   ceremony steps. The phone stays disconnected except for reviewed manual
   transfers: no ADB, no SSH, no automation access to Termux.
6. **Pin copies P-A and P-B** (M-B8) are kept outside both replicas and
   their parents. The public `reproduce` inputs are retained on both
   devices.

## 8. Accepted debt during DEV_SYNTHETIC

```text
WHOLE-HOST / WHOLE-DISK ROLLBACK CAN PRESENT A SELF-CONSISTENT OLD AUTHORITY WORLD.
WHOLE-HOST ROLLBACK RESISTANCE = NOT ESTABLISHED.
INDEPENDENTLY PERSISTED FRESHNESS STATE = NONE.
```

**Acknowledged under B-2:**

- OR-1: whole-disk rollback;
- OR-2 / DR-3: root-equivalent principals;
- cross-environment `osAdminLogin`;
- OR-3: principals able to snapshot or clone (bounded);
- OR-4: no external freshness before record 1;
- OR-7: `/tmp` on the disk;
- OR-8: point-in-time inventory.

**Limitations:**

- owner freshness does not protect against simultaneous rollback or
  compromise of both owner replicas;
- the phone concentration (K-ROOT, Replica B, pin B) is accepted
  availability coupling, not compromise resistance;
- owner freshness is the intended off-host protection **once record 1
  exists**.

## 9. Stop conditions that invalidate an authorization before M-B1

Any one of these voids a GRANTED authorization. The owner must then
re-decide.

- any cloud or host topology change: disk, attachment, snapshot, image,
  clone, backup product, bucket, resource policy, or IAM;
- a PR-2 revalidation other than PASS;
- a DR-5 result set other than the accepted one after any deployment;
- `status --expect P1A-9` failing;
- broker preservation other than PASS;
- activation other than `GRANT_ABSENT`;
- either replica not empty, or not byte-continuous (A: manifest `fbdd045c…`
  and its inodes; B: manifest `c068e533…`);
- a nested Replica B;
- any real authority material appearing before M-B1 (K-ROOT, K-WIT,
  registry, genesis pin, or record);
- any change to `REAL_ACCEPTANCE_ENABLED`, `burned_identities`, the
  owner-freshness tool, or the sequencer without review;
- a suspected phone compromise, phone loss, or loss of Termux private
  storage;
- the laptop compromised or rolled back;
- ADB, SSH, or automation access enabled to Termux;
- the owner cannot run M-B1 entirely on the S25, with the passphrase only
  on the phone;
- any unreviewed change to the M-B1 package, or a bundle that does not
  come from a merged SHA.

## 10. Remaining risks

- The §8 debt, unchanged.
- **Time:** the PR-2 result is point-in-time (OR-8). It must be re-run
  immediately before `CHECK_ELIGIBILITY` and before M-B2.
- **The pending `cfa0b3e` routine deployment:** it must be checked.
- **The M-B1 package does not exist yet.** It is the first post-B-5 work
  item.

## 11. Preconditions to check at the moment of `CHECK_ELIGIBILITY` (P1B-0)

1. The fresh read-only PR-2 revalidation is PASS, with the same scope as
   the pre-B5 revalidation.
2. The latest DEV deployment's DR-5 result set equals the accepted run.
3. Replica A has 0 records (read-only), and Replica B is unchanged since
   its last evidence.
4. `evaluate_eligibility` returns `PR1B_ELIGIBLE` with the owner's
   authorization input.

## 12. Decision record

**The owner selects exactly one outcome.** It is recorded later, in a
separate owner-signed-off change. This packet does not choose.

### Outcome A: `B5_OWNER_AUTHORIZATION=GRANTED`

> I, the owner, authorize PR-1B (the DEV_SYNTHETIC bootstrap M-B1 … M-B15)
> to proceed in the accepted P3-5 order, under the custody obligations of §7
> and the accepted debt of §8.
>
> This sets the eligibility input `pr1bAuthorized = True` for the P1B-0
> `CHECK_ELIGIBILITY` evaluation only.
>
> It does **not** authorize any M-B1 command. **No M-B1 command may be
> issued until I give a separate, explicit M-B1 go statement.** That
> statement comes after the real M-B1 package has been reviewed, the
> `cfa0b3e` deployment's DR-5 result verified, and a fresh PR-2 revalidation
> has passed.
>
> It does not authorize First Memory, A1–A7, activation, issuance, or any
> PROD action. Any §9 stop condition voids it.
>
> Date: `<YYYY-MM-DD>`. Control `main`: `<SHA>`.

**Required separate M-B1 go statement.** This is a separate owner
statement, given later, after the §5 prerequisites:

> I authorize M-B1 now: real K-ROOT generation on the S25 in Termux private
> storage, with the passphrase entered only on the phone, using the
> reviewed M-B1 package `<script SHA-256>` / bundle `<tar SHA-256>` from
> merged `main` `<SHA>`. I will record the fingerprint on the phone, and I
> will confirm it is none of the 12 burned identities.

### Outcome B: `B5_OWNER_AUTHORIZATION=WITHHELD`

> I, the owner, withhold PR-1B authorization. `pr1bAuthorized` stays
> False, and `CHECK_ELIGIBILITY` stays `PR1B_NOT_ELIGIBLE`
> (`PR1B_NOT_AUTHORIZED`).
>
> No M-B1 package is executed. No K-ROOT, K-WIT, registry, genesis pin, or
> record is created. Both replicas stay empty. Freshness stays UNKNOWN.
>
> B-1..B-4 stay closed, but any later grant requires a fresh PR-2
> revalidation and a fresh check of every §1 input.
>
> Reason (optional): `<…>`. Date: `<YYYY-MM-DD>`.

## 13. Blocker state

| # | Blocker | State |
| --- | --- | --- |
| B-1 | PR-3 tooling not accepted | **CLOSED** |
| B-2 | open risks not acknowledged | **CLOSED** |
| B-3 | real-acceptance gate | **CLOSED** (merged `cfa0b3e`) |
| B-4 | K-ROOT custody and the Termux rehearsal | **CLOSED** |
| B-5 | PR-1B not authorized | **OPEN**: this decision |

**`PR1B_NOT_ELIGIBLE` (`PR1B_NOT_AUTHORIZED` only).**

## Explicitly not done

```text
NO DECISION RECORDED
B-5 OPEN
PR-1B NOT AUTHORIZED
NO M-B1
NO REAL K-ROOT
NO K-WIT
NO REGISTRY V1
NO GENESIS PIN
NO REAL RECORD 1
NO REPLICA B CONTACT
NO DEV MUTATION
FRESHNESS=UNKNOWN
FIRST MEMORY NOT AUTHORIZED
```
