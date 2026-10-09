# Slice 15B2b-B1b-3e — Package B Sequence 3: Witness Start and Witness Genesis Completed (2026-10-09)

Status:

- **OWNER ACCEPTANCE RECORD (APPEND-ONLY).** It records Package B sequence 3 on control
  `050e7c5c4c6238eee09eb67b094348127d2953c6`: M-B9a `START_WITNESS` and M-B9b `COMMIT_WITNESS_GENESIS` each ran
  exactly once, each was verified, and the owner accepted the whole package verbatim (B5, §8).
- `PACKAGE_B = COMPLETED / OWNER-ACCEPTED`. The witness is running. **The witness genesis is committed and the
  lineage is irreversible:** no second witness genesis is permitted.
- **The earlier records are unchanged.** The [Package B record](slice-15b2b-b1b3e-mb9-witness-genesis-package.md)
  §21 (`WITNESS_GENESIS = NOT COMMITTED`), the [sequence 1 record](slice-15b2b-b1b3e-mb9-seq1-w9-transport-stop.md)
  and the [sequence 2 record](slice-15b2b-b1b3e-mb9-seq2-stdin-stop-direct-plink.md) were correct when written and
  are not rewritten. This record supersedes them on the Package B outcome only, from 2026-10-09.
- **Documentation and governance only.** Package B completion does not create record 1, the acceptance envelope or
  HELD, does not start the signer, does not make Registry V1 effective and does not activate authority. Record 1,
  the acceptance envelope, HELD, signer start, authority activation, First Memory and PROD stay **NOT AUTHORIZED**.
  `FRESHNESS=UNKNOWN`.
- **Writing this record contacted no live system.** The evidence stays in the owner's local evidence directory,
  sealed as stated in §9.

```text
witness started != witness genesis committed != record 1 != Registry V1 effective != authority active
B5 accepted != this record merged != first post-freeze deploy EQUAL != that deploy owner-accepted
derived running target != accepted global baseline;  completion != First Memory readiness
```

## 1. Identities

| Item | Value |
| --- | --- |
| control | `050e7c5c4c6238eee09eb67b094348127d2953c6` (merge of PR #173, R-B5, 2026-10-08T19:07:32Z; reviewed head `7421f21a4c1c466cd97383d4736b1fc5dc44635f`) |
| control preservation deploy | `37829794035`, "Deploy LILITH Core API to DEV", `workflow_run`, success, `DEPLOY_REQUIRED` from base `103efe50d42ea8f016d671d8ee5f052b9ce961ae`; DR-5 `EQUAL` under `OWNER_INPUTS_INSTALLED_EXACT` (`3640ca01…` / `d05aa017…` / `f5087042…`) |
| preservation acceptance | owner text SHA-256 `f698735a749b6729ff6fcc5f3dec5aed954830156bfa66f6f015623b955f233d`; it selected `050e7c5` as the Package B live control |
| operator | `services/owner-memory-control/tools/mb9_operator.py`, SHA-256 `066fc8213b40c392e3e2bfd609da4a7f2a4e0b6f05da011daee9add3caf13973` (`pins` = `MB9_TOOL_PINS_EXACT`, 17 tools) |
| W9 verifier | `mb9_witness_verifier.py`, SHA-256 `e4aca11dcc925e8ebdb280c2d4a7da1cf4f9a8fcc4e2abb080e22d6917080e78` |
| owner genesis verifier | `mb9_owner_genesis_verify.py`, SHA-256 `30b66fd2be9f29e820041840a75dc87f7623eff44551c025a0141790e7c89a5a` |
| direct plink client | Cloud SDK `plink.exe`, SHA-256 `7308e9d356f14aa1f08cab1af363f71a077bf35dcb49e50b363418044758cd1e`; key public blob `e830598a20880490d8b1644d48a448e600503367d3ab130d051e67d2a6e1a12e` |
| release | `aee323e94412accbe321bc84eae78c5b8cf95afc` |
| candidate | `ac892dc2b14ca7db108400258abfcf2320ff498f2a674058058e16a8a6fb65e4`; `MB7_MB8_UPDATED_AT` `2026-10-08T07:21:43Z` |
| owner pin copies | genesis pin `357477369ab53790245b42cbecbe2a630110477bede5b599696699e4f5c3a590`; register `8d5ab87564d0e531b7d1467c18b6d106f2a468d5d155ce9f2acb64758df85575`; pin record `009a0596ca1d7f2f8d941c949c0671f2091b83668aa9315486dbc7f2a0f1e0ae` |

## 2. The owner acts of sequence 3

Each act is its own verbatim owner text; none implied the next. Every go passed the operator's `check_go` for its
canonical template (record §10).

| Act | Text SHA-256 | Recorded as |
| --- | --- | --- |
| B1: sequence opening (read-only only) | `0fe54c55942dcc2764a611e727a603eb9fa91794df3a5dab719afd5f5605fb8a` | `open-sequence` → `PACKAGE_B_SEQUENCE_OPENED_READ_ONLY`; record `B1_SEQUENCE_AUTHORIZATION.json` `d9381a235f0fb017d0ed562a98c09bc36f7f79a41782a6cd2bf31fddd6189bb1` |
| B2: the M-B9a go | `c9007ba3bd73efeb2b4ea4ac756dbc3fd831a8f7c206345c87505ec3651ffdfe` | markers `mb9a-1`, `mb9a-2` |
| B3: WITNESS_STARTED acceptance | `9e80556cc861187697821ef83b8ffc322c4286391de759fc2db4b02eccb70814` | `accept-9a` → record `WITNESS_STARTED_ACCEPTED-5136ea7af2544450b9370fa412786c98.json` `11ae03ad7d521069edada31089718814c5c488d0b8dfcfb02677296734144f12` |
| B4: the M-B9b lineage go (with the point-of-no-return acknowledgement) | `2e263d1fd96150d5d6568ebd6a6bc39e22613197fba7969a7fc865a4be14a671` | marker `mb9b` |
| B5: Package B acceptance | `1312c01db3d3439ecec7fab22e8141402aa62278e7e7754049d0efd3d6cef6f7` | §8 (verbatim) |

The B1 text also authorized the complete opening evidence from scratch, including the first live use of the R-B5
direct-plink verifier transport through the canonical opening path only, with no fallback.

## 3. Opening evidence and the B2 closing gate (read-only)

Collected fresh for sequence 3; nothing from sequences 1 or 2 was used as eligibility evidence.

- **Cloud:** 13/13 captures returned 0; Admin Activity 306 rows, all `iam.serviceAccounts.actAs` on the DEV VM
  service account, every row after the sequence-2 window mapped to a known session; no compute or IAM change.
- **`host PRE`:** `MB9_HOST_PRE_PASS`, all 10 codes 0, readiness exact, `/tmp` residue `[]`. **The first live use of
  the R-B5 direct-plink verifier transport was exact:** the M-B6, W8 and W9 bundles each exited 0 with empty stderr.
  W9 `W9_0_PRE_WITNESS` (all 7 base checks true; host candidate = pin); W8 `OWNER_INPUTS_INSTALLED_EXACT`; boot id
  `eea461c3-60f0-4b10-8ee9-556dcef19711`; `REBOOT_REQUIRED=absent`; K-WIT blob
  `f87593701ee5e9272363a473a115b87cc06179df3c0b233af4aa62bb5b9b97be`.
- **Denial proofs:** P1B-5 PASS (92 `DENIED`), P1B-6 PASS (20 `DENIED`), P1B-8 PASS (10 `DENIED`); 0 `ALLOWED` each.
- **Candidate reproduction (off-host):** `mb7_genesis_candidate.py derive` over the accepted installables
  (`46b0bfc5…`, `bc5f00a7…`, `be360da2…`) gave `ac892dc2…65e4`, ledger sequence 1, head `19bf9091…1630`.
- **P-A:** `OWNER_COPY_EQUAL`. **Replica A:** `REPLICA_VERIFIED`, 0 records, manifest unchanged.
- **P-B and Replica B** (owner S25 screen-only read of a read-only block, SHA-256
  `7434fc6df32d358b4351c5c389d0b7e2d22bd6f62f5e2404f9f02765e478b6bd`; recorded as `OWNER_SCREEN_TRANSCRIPTION`, not
  machine-captured): Replica B `c068e5331ccd7fa0f69f2b38d25849497b86edea843598784235874080c107c4`, 0 records,
  baseline inodes/modes/sizes/mtime; P-B exactly three files, each `EXACT`. **`OWNER_REGISTER = KNOWN_EMPTY`.**
- **DR-5 targets** derived mechanically (§10) and equal to their pins.
- **B2 closing gate: PASS.** Pins, control, empty queue, B1 record unchanged, no attempt marker; a fresh `host PRE`
  equal to the opening read except clock fields; no reboot.

## 4. M-B9a `START_WITNESS` (B2; one go, two markers)

`mb9a` was invoked once: `MB9A_STARTED`.

- Marker `mb9a-1` at 2026-10-09T04:44:18Z → `witness-state aee323e…` once: `STAGE_PASS`, exit 0, stderr empty → host
  `W9_1_STATE_DIR_ONLY`.
- Marker `mb9a-2` at 2026-10-09T04:44:27Z → the two socket starts and the service start once: `START_RETURNED_OK` →
  host **`W9_2_STARTED_UNINITIALIZED`**; health exact, classification `UNINITIALIZED`.
- **Accepted witness incarnation: InvocationID `5136ea7af2544450b9370fa412786c98`, MainPID `143946`.**

**POST9A:** `MB9A_POST_VERIFIED`, all 13 codes 0; `POST9A_VERIFIED.json` SHA-256
`50a2ef262df099190074dbad1f9358587db76ace10a1e22a077e3c3123f6fcfa`. Store `UNINITIALIZED` (the 2750 state directory
with `witness.lock` only); NRestarts 0; signer units inactive and its paths absent. **P1B-9a PASS: 107 lines, 91
`DENIED`, 5 `ALLOWED_BY_DESIGN`, 0 unexpected `ALLOWED`** (transcript SHA-256
`30c3ebb5d5ec7bae74667eee335271266d173e5001c4113e83bc98f8d0c84d2b`). P1B-5 PASS.

**B3** accepted `WITNESS_STARTED` for exactly that InvocationID, MainPID and POST9A evidence; it authorized nothing.

## 5. The B4 closing gate (read-only)

- A fresh S25 read after `WITNESS_STARTED` (owner transcription, same read-only block): Replica B and P-B identical
  to the opening read; with a fresh Replica A, **`OWNER_REGISTER = KNOWN_EMPTY` after `WITNESS_STARTED`**.
- P-A `OWNER_COPY_EQUAL`; candidate re-derived `ac892dc2…65e4`.
- `host POST9A` byte-equal to the POST9A read except clock fields; **the same incarnation** (InvocationID
  `5136ea7a…`, MainPID `143946`, NRestarts 0); store `UNINITIALIZED`; no chain.
- `classify`: `S9A_ACCEPTED`, routing `SAFE_ADOPT`, bootstrap not invoked. `health`: `MB9_HEALTH_EXACT`,
  `UNINITIALIZED`.
- Control, empty queue, last deploy `37829794035`, no `mb9b` marker, boot id unchanged. **B4 closing gate: PASS.**

## 6. M-B9b `COMMIT_WITNESS_GENESIS` (B4; one attempt)

`mb9b` was invoked once, after the operator re-confirmed `W9_2` and the B3-accepted incarnation and found the
point-of-no-return acknowledgement in the go. Marker `mb9b` at 2026-10-09T04:59:49Z → the ONE
`lilith-recovery-witness-owner-dev bootstrap 1 2026-10-08T07:21:43Z`: exit 0, stderr empty, output
`{"authorityGranted":false,"classification":"CONSISTENT","genesisDigest":"ac892dc2…65e4","pinned":true}`; transcript
`BOOTSTRAP_PASS`; host **`W9_5_GENESIS_COMMITTED_EXACT`**. `MB9B_COMMITTED`.

```text
WITNESS_GENESIS = COMMITTED / IRREVERSIBLE
LINEAGE_REVERSIBLE = NO
SECOND_WITNESS_GENESIS = FORBIDDEN
```

**Committed genesis.** Digest `ac892dc2b14ca7db108400258abfcf2320ff498f2a674058058e16a8a6fb65e4` = the owner pin =
the Package A candidate. `chain/1.json` SHA-256 `252c32204bebf3fa1ca0981d8791115e2abb6cd8ddb0925285c64213317cfb99`;
`witness.json` is byte-identical to it. Fields: registryVersion 1, registryDigest
`fa66272131a3ef076036616b07766a377de4fdc1e4fef4cb8a054726f05c14fc`, ledgerSequence 1, ledgerHead
`19bf9091a96cdc2378a68508feb0c119721f7fcef7b9c3a480a6cd6b72fa1630`, witnessVersion 1, previousWitnessDigest null,
consumedAuthorizationId null, witnessKeyId `test-only.witness.dev-synthetic.b1b3d.1`, updatedAt
`2026-10-08T07:21:43Z`.

**POST9B:** `MB9B_POST_VERIFIED`, all 16 codes 0; `POST9B_VERIFIED.json` SHA-256
`7f41541b4f633187382d9235c07ef1987ffb94bc384f6679623fa5edcbef98af` (no adoption required). W9 `W9_5`, store
`CONSISTENT`, all six genesis checks true, chain = genesis only; the same incarnation, NRestarts 0; signer inactive;
`read` returns head version 1. **P1B-9b PASS: 148 lines, 125 `DENIED`, 11 `ALLOWED_BY_DESIGN`, 0 unexpected
`ALLOWED`** (transcript SHA-256 `1d37a2afd56b82e8f25ec3998bc438478ed2966ea2b5ccc56a8514235dda91c0`). P1B-5 PASS.

P1B-6 and P1B-8 are out of their valid phase once witness state exists (record §11). That is by design, not drift
or failure; their tools are unchanged.

## 7. Owner offline verification

`mb9_owner_genesis_verify.py verify` on the owner workstation (read-only) over P-A, the accepted witness anchor
`be360da2324880d725aea509bb0f41500f51ecfc3c2995dd3057824bb471ab5a` and the exported `chain/1.json` and
`witness.json`: **`MB9B_OWNER_GENESIS_VERIFIED`**. All 15 checks true (including the K-WIT signature, which
verifies) and all 14 genesis-field checks true. The tool reports `record1 = NOT CREATED` and `freshness = UNKNOWN`
by design; P-A was unchanged.

## 8. B5 owner acceptance (verbatim)

Owner acceptance text SHA-256 (the text plus one terminal LF): `1312c01db3d3439ecec7fab22e8141402aa62278e7e7754049d0efd3d6cef6f7`.

> I accept Package B for this sequence: M-B9a / START_WITNESS and M-B9b / COMMIT_WITNESS_GENESIS are COMPLETED.
> Committed witness genesis digest: ac892dc2b14ca7db108400258abfcf2320ff498f2a674058058e16a8a6fb65e4 (= the owner pin
> = the Package A candidate). chain/1.json SHA-256: 252c32204bebf3fa1ca0981d8791115e2abb6cd8ddb0925285c64213317cfb99.
> POST9B_VERIFIED evidence SHA-256: 7f41541b4f633187382d9235c07ef1987ffb94bc384f6679623fa5edcbef98af. Owner offline
> verification: MB9B_OWNER_GENESIS_VERIFIED. This acceptance authorizes nothing further. The Package B deployment
> freeze ends now; the first deploy after it must compare EQUAL to the derived running-witness DR-5 target (separate
> owner record).

B5 ended the Package B deployment freeze and authorized nothing further. The owner separately authorized creating
this record PR (not its merge).

## 9. Evidence seal

- Final sequence-3 evidence seal (`SHA256SUMS`, 360 entries, every evidence file except the checkout copy and the
  seal files): `7e45706f74f8d8faefbd648d0a91329e859ef9ba227f9ed9d546cb57377a6bf6`. It covers the verbatim B5 file.
- Preserved byte-identically beside it: the pre-S25 opening seal
  `8d1f4ace8ae5e7cf1f1c716527e13b44381777f56bc657fd19f5aee98c168b60` (115 entries) and the pre-B5 seal
  `1277299c75d4515cfec319642999cbe1d702b3402849e5a95a226107082af197` (358 entries). Interim working seals taken
  between them were rewritten in place and are not preserved; every file they covered is covered by the final seal.

## 10. The first post-Package-B-freeze deploy (not yet occurred)

`PHASE_BOUND_DR5_BASELINE_WITH_DERIVED_DELTA` (record §12): with the witness running and the genesis committed, the
comparison target is the derived **RUNNING** target. It was derived mechanically from the accepted post-M-B6 texts
and equals its pin; it is **not** a newly accepted global baseline.

| Set | Lines | SHA-256 | Counts |
| --- | --- | --- | --- |
| full result set | 192 | `593c90e1778b0e90326cdf96314b328948c00b2207960d27be2b41874d05ff65` | 167 `DENIED`, 0 `ALLOWED`, 0 `FAIL`, 1 `DEFERRED_UNTIL_OBJECT_EXISTS`, 6 `UNOBSERVABLE_BY_DESIGN` |
| DR-5 block | 153 | `ace51f27ac17a2d719ec19da582d09e21f0c7fb4be7b6ec81e1dd53cb369fd5a` | 139 `DENIED`, 0 `ALLOWED` |
| pre-deploy block | 29 | `f50870420c10149914b8d2a02116708ec89ea5a8f746a847fbe88df058f54cae` | 28 `DENIED` |

Order (none done):

1. this Package B completion-record PR, reviewed;
2. a separate owner merge authorization;
3. its merge-triggered DEV deploy is the **first post-Package-B-freeze deploy**;
4. a fresh read-only W9 read must establish `W9_5_GENESIS_COMMITTED_EXACT`;
5. `mb9_operator.py dr5 <repo> W9_5_GENESIS_COMMITTED_EXACT <deploy-log>` must compare `EQUAL` to the RUNNING target;
6. a separate owner acceptance of that first post-freeze deploy.

```text
PACKAGE_B_COMPLETION_RECORD_MERGE = NOT AUTHORIZED
FIRST_POST_PACKAGE_B_FREEZE_DEPLOY = NOT YET OCCURRED
RUNNING_DR5_TARGET = DERIVED; NOT ACCEPTED AS A GLOBAL BASELINE
```

## 11. Boundaries

| Fact | State |
| --- | --- |
| Package B sequence 3 | COMPLETED / OWNER-ACCEPTED |
| Package B sequence 1 (control `5ce067cf485cafed6ea2487635027955396e7844`) | STOPPED / HISTORICAL / NON-REUSABLE |
| Package B sequence 2 (control `103efe50d42ea8f016d671d8ee5f052b9ce961ae`) | STOPPED BEFORE M-B9a / HISTORICAL / NON-REUSABLE |
| Package B deployment freeze | ENDED by B5 |
| witness | RUNNING (InvocationID `5136ea7a…`, MainPID `143946`) |
| witness genesis | **COMMITTED / IRREVERSIBLE** |
| `REGISTRY_EFFECTIVE` | **NO** |
| `AUTHORITY_ACTIVE` | **NO** |
| `authorityGranted` | false |
| signer | **INACTIVE** |
| record 1 | **ABSENT** |
| acceptance envelope / HELD | **NOT AUTHORIZED** |
| authority activation | **NOT AUTHORIZED** |
| First Memory | **NOT AUTHORIZED** |
| PROD | **NOT AUTHORIZED** |

Record 1, the acceptance envelope, HELD, signer start and authority activation are later stages. Each needs its own
owner authorization; none follows from Package B completion.

The W8 routing field (`MB8_ROUTING_FIELD_ANOMALY = REPORTING_DEFECT_ONLY`) stays an open future remediation and is
not fixed here.

**First Memory boundary.** Tooling must not infer, choose, draft or write LILITH's First Memory merely because later
bootstrap stages become technically ready. If the system eventually reaches `FIRST_MEMORY_READY`, the process
**STOPS** there. Owner discussion is required before any First Memory content is selected or written.

## 12. State

```text
PACKAGE_B = COMPLETED / OWNER-ACCEPTED
PACKAGE_B_SEQUENCE = 3
PACKAGE_B_CONTROL = 050e7c5c4c6238eee09eb67b094348127d2953c6
PACKAGE_B_SEQUENCE_1 = STOPPED / HISTORICAL / NON-REUSABLE
PACKAGE_B_SEQUENCE_2 = STOPPED BEFORE M-B9a / HISTORICAL / NON-REUSABLE
M-B9a = COMPLETED
M-B9b = COMPLETED
WITNESS_STARTED = OWNER-ACCEPTED
WITNESS_INVOCATION_ID = 5136ea7af2544450b9370fa412786c98
WITNESS_MAIN_PID = 143946
POST9A_VERIFIED_SHA256 = 50a2ef262df099190074dbad1f9358587db76ace10a1e22a077e3c3123f6fcfa
WITNESS = RUNNING
WITNESS_GENESIS = COMMITTED / IRREVERSIBLE
WITNESS_GENESIS_DIGEST = ac892dc2b14ca7db108400258abfcf2320ff498f2a674058058e16a8a6fb65e4
CHAIN_1_SHA256 = 252c32204bebf3fa1ca0981d8791115e2abb6cd8ddb0925285c64213317cfb99
POST9B_VERIFIED_SHA256 = 7f41541b4f633187382d9235c07ef1987ffb94bc384f6679623fa5edcbef98af
OWNER_OFFLINE_VERIFICATION = MB9B_OWNER_GENESIS_VERIFIED
P1B-9a = PASS (91 DENIED, 5 ALLOWED_BY_DESIGN, 0 ALLOWED)
P1B-9b = PASS (125 DENIED, 11 ALLOWED_BY_DESIGN, 0 ALLOWED)
B5_ACCEPTANCE_TEXT_SHA256 = 1312c01db3d3439ecec7fab22e8141402aa62278e7e7754049d0efd3d6cef6f7
PACKAGE_B_EVIDENCE_SEAL = 7e45706f74f8d8faefbd648d0a91329e859ef9ba227f9ed9d546cb57377a6bf6
PACKAGE_B_FREEZE = ENDED
RUNNING_DR5_TARGET_FULL_SHA256 = 593c90e1778b0e90326cdf96314b328948c00b2207960d27be2b41874d05ff65
RUNNING_DR5_TARGET_BLOCK_SHA256 = ace51f27ac17a2d719ec19da582d09e21f0c7fb4be7b6ec81e1dd53cb369fd5a
RUNNING_DR5_TARGET_PREDEPLOY_SHA256 = f50870420c10149914b8d2a02116708ec89ea5a8f746a847fbe88df058f54cae
PACKAGE_B_COMPLETION_RECORD_MERGE = NOT AUTHORIZED
FIRST_POST_PACKAGE_B_FREEZE_DEPLOY = NOT YET OCCURRED
LEDGER SEQUENCE = 1
LEDGER HEAD = 19bf9091a96cdc2378a68508feb0c119721f7fcef7b9c3a480a6cd6b72fa1630
REGISTRY_EFFECTIVE = NO
AUTHORITY_ACTIVE = NO
authorityGranted = false
SIGNER = INACTIVE
RECORD 1 = ABSENT
ACCEPTANCE_ENVELOPE = NOT AUTHORIZED
HELD = NOT AUTHORIZED
AUTHORITY ACTIVATION = NOT AUTHORIZED
FIRST_MEMORY = NOT AUTHORIZED
PROD = NOT AUTHORIZED
FRESHNESS=UNKNOWN
```
