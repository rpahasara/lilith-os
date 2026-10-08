# Slice 15B2b-B1b-3e — Package A (M-B7 + M-B8): Completion and Owner Acceptance (2026-10-08)

Status:

- **COMPLETION AND OWNER-ACCEPTANCE RECORD.** Package A (M-B7 / `PREPARE_GENESIS_CANDIDATE` + M-B8 / `PIN_GENESIS`)
  ran in one owner-attended DEV_SYNTHETIC sequence on control `29c2b824cae187037e4434a1ad7f9466f4eb2ab6` (the merge
  of PR #169), under the [Package A record](slice-15b2b-b1b3e-mb7-mb8-genesis-prep-package.md).
- Continuity: `MB7_MB8_CONTINUITY = OWNER_ATTENDED_EVENT_BOUNDED_SINGLE_SEQUENCE_TWO_STAGE` (OD-1).
- M-B7 ran exactly once (read-only). M-B8 ran exactly once (one `install-owner-inputs`). The owner then issued the
  canonical §16 acceptance verbatim (§6).
- `PACKAGE_A = COMPLETED / OWNER-ACCEPTED`. `GENESIS_PREPARED = YES`. `GENESIS_PINNED = YES`.
- **E-A18 is NOT YET PERFORMED** (§9). The Package A deployment freeze ended with the §16 acceptance.
- **Nothing later is authorized.** M-B9a, M-B9b, witness genesis, record 1, the signer, authority activation, First
  Memory and PROD are **NOT AUTHORIZED**. `FRESHNESS=UNKNOWN`.
- This record is written repository-only. Writing it contacted no live system. The sequence evidence stays in the
  owner's local evidence directory, sealed as stated in §8.

```text
candidate (M-B7) != OwnerGenesisPinV1 / genesis-pin.json (M-B8) != committed witness genesis (M-B9b) != record 1
GENESIS_PINNED != witness genesis committed != Registry V1 effective != authority active
Package A accepted != E-A18 performed != M-B9a authorized
```

## 1. Identities

| Item | Value |
| --- | --- |
| control | `29c2b824cae187037e4434a1ad7f9466f4eb2ab6` |
| release on DEV | `aee323e94412accbe321bc84eae78c5b8cf95afc` |
| operator | `services/owner-memory-control/tools/mb7_mb8_operator.py`, SHA-256 `9f13411f363dc956795ce4832d1948e7e6a9a7f7c8d1057291de852e9e2a20cd` |
| owner candidate tool | `mb7_genesis_candidate.py`, SHA-256 `d50fcb36afab51a79c7918a7a43c86f97338241f62144c780d8b342c68b3c8b2` |
| W8 verifier | `mb8_owner_input_verifier.py`, SHA-256 `b190c255c88a1bdca0ff8d9cb050443ad24d42f269d49947d47b87775351e341` |
| removal | `mb8_owner_input_removal.py`, SHA-256 `d9a6e0d5dcfb07558ca7533e8144b7f2b7c29b1b4db28400571aede55b99f7f5` |
| P1B-8 proof | `mb8_owner_input_denial_proof.py`, SHA-256 `5d63137a2c6e43f12f663febdd4e22fd7b2b519a6c0cfa544dad12f0bc958517` |
| installer | `install_authority_dev.py`, SHA-256 `fe10d9a37c53d4a32ca49d79ee5987c6546866feeebcee3c882087f51ed55487` |
| `MB7_MB8_UPDATED_AT` | `2026-10-08T07:21:43Z` |
| candidate digest | `ac892dc2b14ca7db108400258abfcf2320ff498f2a674058058e16a8a6fb65e4` |
| M-B7 host stdout SHA-256 | `40b1a6008319cf66e541bf4cd8df9ed90c77cea1433a570b5785b00bd3a28984` |
| `genesis-pin.json` SHA-256 | `357477369ab53790245b42cbecbe2a630110477bede5b599696699e4f5c3a590` |
| `authorization-register.json` SHA-256 | `8d5ab87564d0e531b7d1467c18b6d106f2a468d5d155ce9f2acb64758df85575` |
| `pin-record.json` SHA-256 | `009a0596ca1d7f2f8d941c949c0671f2091b83668aa9315486dbc7f2a0f1e0ae` |
| M-B8 go SHA-256 | `a0d6e8b2fd8468a4599c198855e4d6ac4efb874be3769aae128495d957c42e7b` |
| `POST_VERIFIED.json` SHA-256 (owner-selected POST evidence artifact) | `e5441b5a260a314925c8393d7afa69adc7a6ed031a6608d077d25ffa19c6e2e6` |
| P1B-8 transcript SHA-256 | `271d2f0b7e5484d6f4856a48bfe6c76c2f0696a9bba05e03253d6e1c4d6a01aa` |
| ledger | sequence 1, head `19bf9091a96cdc2378a68508feb0c119721f7fcef7b9c3a480a6cd6b72fa1630` |
| Registry V1 | digest `fa66272131a3ef076036616b07766a377de4fdc1e4fef4cb8a054726f05c14fc`; installable SHA-256 `46b0bfc558ec3a19467206ada3dc53c18e8a6a4cd0782711b4800cfe099f8b1e` |
| latest DEV deploy | `37741374796` (`29c2b82`, success); no deploy since |

The candidate, pin, register and pin-record digests re-derive from the accepted identities and `updatedAt` alone
(the pinned owner restatement; tested in `test_b1b3e_mb9_package.py`).

## 2. Owner acts (each separate, in order)

1. **ACT 1** (package §14.1, verbatim): the sequence and the read-only M-B7.
2. **ACT 2** (§14.2, verbatim): `GENESIS_PREPARED` accepted for exactly this candidate; P-A and P-B recording authorized.
3. **ACT 3** (§14.3, verbatim): exactly one M-B8 host install.
4. **E-A16 decision** (owner): run E-A16 before acceptance; then one authorized read-only rerun after a local client
   launch failure (§5).
5. **§16 acceptance** (verbatim, §6), which ended the deployment freeze.
6. **E-A17 authorization** (owner): the stage cleanup only.

## 3. M-B7 and the owner records

- E-A7 (laptop) and E-A8 (S25, owner-run, attested) reproduced the same candidate. The DEV in-memory candidate and
  the one DEV `genesis-candidate` invocation (E-A9, `MB7_TECHNICAL_PASS`, stdout byte-equal) are the same. W8-0
  before and after; no scratch residue.
- **P-A** `/root/lilith-genesis-pin-dev-synthetic` (laptop WSL Ubuntu-24.04) and **P-B**
  `$HOME/lilith-genesis-pin-dev-synthetic` (S25 Termux) each hold exactly the three files above, separately
  hash-verified and byte-equal. The first P-B attempt stopped `PRE_WRITE_TRANSFER_SOURCE_MISSING` with no write;
  the second recorded it.
- `OWNER_REGISTER = KNOWN_EMPTY` (the owner freshness register; not `OwnerAuthorizationRegisterV1`) was freshly
  established from Replica A and Replica B after P-A / P-B were recorded.

## 4. M-B8 (exactly one invocation) and POST

- The closing gate (E-A13) first stopped on one read-only W5 verifier SSH timeout (no marker, no mutation; preserved
  as evidence). One owner-authorized read-only rerun (E-A13b) passed every gate.
- Marker at `2026-10-08T10:30:49Z`; exactly one `install-owner-inputs aee323e… <stage>/genesis-pin.json
  <stage>/authorization-register.json`: exit 0, stderr empty, transcript `INSTALL_PASS`, `status P1B-8` PASS.
- POST (E-A15): `MB8_POST_VERIFIED`, sequence phase `S8_6_POST_VERIFIED_ACCEPTANCE_PENDING`; W8
  `OWNER_INPUTS_INSTALLED_EXACT`; both copies `root:root 0644`, one link; all three evidence items true;
  `hostInputReasons = []`; `candidate_pin_reason = None`; P1B-8 PASS (18 lines, `denied=10 allowed=0`); W5
  `OUT_OF_SCOPE_POST_LEDGER` with all evidence true; M-B6 verifier `OUT_OF_SCOPE_LATER_STATE` (expected: its scope
  ends at the first owner copy); ledger exact; preservation and readiness byte-identical to PRE.

## 5. E-A16 (post-M-B8 P1B-5 and P1B-6)

- The first attempt (`E-A16a`) failed before any transport: the local gcloud launcher was not configured
  (`LOCAL_CLIENT_LAUNCH_FAILURE_BEFORE_TRANSPORT`; no DEV contact; preserved as evidence).
- The owner-authorized rerun passed, byte-identical to the accepted E-A6 transcripts:
  - P1B-5 `AUTHORITY_CUSTODY_DENIAL_PROOF=PASS`, 92 `DENIED`, 0 `ALLOWED`, 0 `FAIL`, SHA-256
    `e87db14d0e03ee3da162863a72ee9326b087f1973d2e027ea67680064e899a8d`;
  - P1B-6 `MB6_LEDGER_DENIAL_PROOF=PASS`, 20 `DENIED`, 0 `ALLOWED`, SHA-256
    `f8722cb7e2cb2ee91b73e4722715ee790c6eb564692ad5cf4d3de38094b92e2b`.
- An acceptance-boundary recheck then passed (control, no deploy, empty queue, host POST reads byte-equal to M-B8
  POST except time fields, staged files exact, P-A exact). Its first P-A read used the default WSL distribution and
  found nothing; the read in Ubuntu-24.04 was exact (a misdirected read-only probe; preserved).

## 6. Owner acceptance (verbatim, package §16)

> I accept Package A for this sequence: M-B7 / PREPARE_GENESIS_CANDIDATE and M-B8 / PIN_GENESIS are COMPLETED. Candidate digest: ac892dc2b14ca7db108400258abfcf2320ff498f2a674058058e16a8a6fb65e4. MB7_MB8_UPDATED_AT: 2026-10-08T07:21:43Z. Genesis-pin copy SHA-256: 357477369ab53790245b42cbecbe2a630110477bede5b599696699e4f5c3a590. Authorization-register copy SHA-256: 8d5ab87564d0e531b7d1467c18b6d106f2a468d5d155ce9f2acb64758df85575. Pin-record SHA-256: 009a0596ca1d7f2f8d941c949c0671f2091b83668aa9315486dbc7f2a0f1e0ae. POST_VERIFIED evidence: e5441b5a260a314925c8393d7afa69adc7a6ed031a6608d077d25ffa19c6e2e6.
>
> ```text
> M-B7 = OWNER-ACCEPTED
> M-B8 = OWNER-ACCEPTED
> GENESIS_PREPARED = YES
> GENESIS_PINNED = YES
> OWNER P-A PIN = RECORDED
> OWNER P-B PIN = RECORDED
> OFF-HOST AUTHORIZATION REGISTER P-A = RECORDED / EXACT
> OFF-HOST AUTHORIZATION REGISTER P-B = RECORDED / EXACT
> HOST OWNER INPUTS = OWNER_INPUTS_INSTALLED_EXACT
> LEDGER = SEQUENCE 1 / HEAD 19bf9091a96cdc2378a68508feb0c119721f7fcef7b9c3a480a6cd6b72fa1630
> REGISTRY_EFFECTIVE = NO
> AUTHORITY_ACTIVE = NO
> authorityGranted = false
> GRANT_ABSENT = TRUE
> WITNESS = INACTIVE; SIGNER = INACTIVE
> M-B9a = NOT AUTHORIZED
> M-B9b = NOT AUTHORIZED
> WITNESS_GENESIS = NOT COMMITTED
> RECORD 1 = ABSENT
> FIRST MEMORY = NOT AUTHORIZED
> PROD = NOT AUTHORIZED
> FRESHNESS = UNKNOWN
> ```
>
> This acceptance authorizes nothing further. The deployment freeze ends now; the first post-freeze deploy must compare EQUAL to the accepted post-M-B6 DR-5 baseline (separate owner record).

## 7. E-A17 (closing cleanup)

- Pre-cleanup gate PASS (control, no deploy since `37741374796`, empty queue, host reads byte-equal to M-B8 POST
  except time fields, staged files exact).
- Exactly one operator `cleanup`: the two staged transport copies removed, the stage directory removed,
  `STAGE_DIR_ABSENT` confirmed (`MB8_STAGE_CLEANED`). The installed owner-input copies, the ledger, trust, registry,
  P-A, P-B and the replicas were not touched.
- Post-cleanup host read: `OWNER_INPUTS_INSTALLED_EXACT`, all three evidence items true, ledger exact, both copies
  `root:root 0644` one link with the hashes above, `GRANT_ABSENT`, witness and signer units inactive, no witness
  state, empty hold store.
- `E-A17 = COMPLETE`.

## 8. Evidence seal

- Final Package A evidence seal (`SHA256SUMS`, 322 entries, every evidence file except the checkout copy):
  `71a503d8b99240bfff61e8da23cf95aa225868b31a23ad507614c2f358b1551d`.
- The prior seal is preserved byte-identically beside it: `50e8804c066420b0c15f89ce6a5d8d7672b31251640900162139f8b7db348e0a`
  (it differs from the final set only in the appended state log).
- Every failed or anomalous read above is inside the final seal; none was deleted.

## 9. E-A18 (not yet performed)

The freeze ended with §6, but no deploy has run since `37741374796`. The first post-freeze deploy must compare
`EQUAL` to the accepted post-M-B6 DR-5 baseline (`3640ca01…`) under `OWNER_INPUTS_INSTALLED_EXACT` (package §7,
OD-4), and the owner records that separately. **`E-A18 = NOT YET PERFORMED`.** Package B must not open before it
(Package B record §13).

## 10. Open remediation item (recorded, not fixed)

`MB8_ROUTING_FIELD_ANOMALY = REPORTING_DEFECT_ONLY` (owner determination). The W8 verifier's `ROUTING` table is keyed
by sequence phases plus the stop phases and has no entry for the host phase `OWNER_INPUTS_INSTALLED_EXACT`, so its
`routing` field falls through to `STOP_OWNER_ADJUDICATION` for that host phase, while package §6.1 routes it
`SAFE_ADOPT`. The operator routes by sequence phase and never reads that field, so no Package A result is affected.
**OPEN FUTURE REMEDIATION:** a later independent slice may add the missing `OWNER_INPUTS_INSTALLED_EXACT ->
SAFE_ADOPT` entry and its regression test. The pinned Package A tool is not changed by this record or by Package B.

## 11. Boundaries

- No witness state exists; witness and signer are inactive; `GRANT_ABSENT`; no hold record; record 1 is absent.
- `REGISTRY_EFFECTIVE = NO`; `AUTHORITY_ACTIVE = NO`; `authorityGranted = false`.
- First Memory is **NOT AUTHORIZED**. No tool or model may choose, draft or write it. When bootstrap reaches
  `FIRST_MEMORY_READY`, execution stops for owner discussion.

## 12. State

```text
PACKAGE_A = COMPLETED / OWNER-ACCEPTED
M-B7 = OWNER-ACCEPTED
M-B8 = OWNER-ACCEPTED
GENESIS_PREPARED = YES
GENESIS_PINNED = YES
HOST OWNER INPUTS = OWNER_INPUTS_INSTALLED_EXACT
STAGED TRANSPORT FILES = REMOVED / E-A17 COMPLETE
E-A17 = COMPLETE
LEDGER_SEQUENCE = 1
LEDGER_HEAD = 19bf9091a96cdc2378a68508feb0c119721f7fcef7b9c3a480a6cd6b72fa1630
registryEffective = false
authorityActive = false
authorityGranted = false
GRANT_ABSENT = TRUE
WITNESS = INACTIVE
SIGNER = INACTIVE
WITNESS_GENESIS = NOT COMMITTED
RECORD 1 = ABSENT
PACKAGE_A_FINAL_EVIDENCE_SEAL = 71a503d8b99240bfff61e8da23cf95aa225868b31a23ad507614c2f358b1551d
PACKAGE_A_PRIOR_SEAL_PRESERVED = 50e8804c066420b0c15f89ce6a5d8d7672b31251640900162139f8b7db348e0a
DEPLOYMENT_FREEZE = ENDED_BY_§16_OWNER_ACCEPTANCE
E-A18 = NOT YET PERFORMED
MB8_ROUTING_FIELD_ANOMALY = REPORTING_DEFECT_ONLY (OPEN FUTURE REMEDIATION)
M-B9a = NOT AUTHORIZED
M-B9b = NOT AUTHORIZED
FIRST MEMORY = NOT AUTHORIZED
PROD = NOT AUTHORIZED
FRESHNESS = UNKNOWN
```
