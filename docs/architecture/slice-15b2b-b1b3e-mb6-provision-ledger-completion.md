# Slice 15B2b-B1b-3e — M-B6 `PROVISION_LEDGER`: Completion and Owner Acceptance (2026-10-07)

Status:

- **COMPLETION AND OWNER-ACCEPTANCE RECORD.** M-B6 / `PROVISION_LEDGER` ran in one owner-attended DEV_SYNTHETIC
  preparation sequence on control `5752bc8e2ee267ae47db04b37c50cbdfa3a0a361` (the merge of PR #165), under the
  [M-B6 ceremony package](slice-15b2b-b1b3e-mb6-ceremony-package.md).
- **Exactly one** `/usr/local/sbin/lilith-authority-ledger-dev provision 1` ran. The go was consumed. The owner then
  issued the §12 acceptance verbatim.
- `M-B6 = COMPLETED / OWNER-ACCEPTED`. `LEDGER_PROVISIONED = OWNER-ACCEPTED`.
- **Nothing later is authorized.** M-B7, M-B8, witness genesis, record 1, First Memory, authority activation and
  PROD are **NOT AUTHORIZED**. `FRESHNESS=UNKNOWN`.
- The post-M-B6 DR-5 target stays **DERIVED, NOT ACCEPTED** (§8).
- This record is written repository-only. Writing it contacted no live system.

```text
ledger provisioned != Registry V1 effective != authority active != memory write authorized
ledger GENESIS op (M-B6, a journal row) != witness genesis candidate (M-B7) != OwnerGenesisPinV1 (M-B8)
  != committed witness genesis (M-B9b)
LEDGER_PROVISIONED accepted != M-B7 authorized
```

## 1. Identities

| Item | Value |
| --- | --- |
| control | `5752bc8e2ee267ae47db04b37c50cbdfa3a0a361` |
| release on DEV | `aee323e94412accbe321bc84eae78c5b8cf95afc` |
| operator | `services/owner-memory-control/tools/mb6_operator.py`, SHA-256 `4a91d98421e38326858e141152180c127f5a67306eebe51a8ca8762f0504dcc5` |
| verifier | `mb6_ledger_verifier.py`, SHA-256 `6449d6ac88313da177665ab9ae7ee9beb86a3a03a22e2a02c2aecf99a79767b5` |
| P1B-6 proof | `mb6_ledger_denial_proof.py`, SHA-256 `470cb27231a0acc3cc5e0ffedb691c1e0a72c313ae80205aa928cff248b9f3c0` |
| ledger sequence | `1` |
| ledger head | `19bf9091a96cdc2378a68508feb0c119721f7fcef7b9c3a480a6cd6b72fa1630` (equal to the [owner-accepted expected head](slice-15b2b-b1b3e-mb6-owner-ledger-head-acceptance.md)) |
| GENESIS op JCS SHA-256 | `8e3bdbdf3f3730de5ad031d36eb390888fc6e0f65307d947522b0138ffcd7b60` |
| schema fingerprint | `65127a68c61d4dba390e01c61d01a76fdc54e830c374cb05069b0ab0c50d9cb7` |
| Registry V1 digest | `fa66272131a3ef076036616b07766a377de4fdc1e4fef4cb8a054726f05c14fc` |
| attempt marker SHA-256 | `75e7307983b3b14150856ad6a953ba9eeaffa2d2e816a4cccaf9980362417f87` |
| POST_VERIFIED evidence SHA-256 | `733377bc62fc908aa8a46d2df05ba59078bb68e2ec9f2b8830706d06048bf93b` |
| P1B-6 transcript SHA-256 | `f8722cb7e2cb2ee91b73e4722715ee790c6eb564692ad5cf4d3de38094b92e2b` |

## 2. Owner authorizations (each separate, in order)

1. **The preparation sequence** (package §14.1): fresh E-1 … E-25 and the closing gate G-1 … G-9; read-only.
2. **The E-18 owner submission:** the Replica B screen-only read on the S25, the settings, and the custody
   attestation.
3. **The M-B6 go** (package §8, verbatim, 18 lines; equal to `mb6_operator.MB6_GO_LINES`).
4. **The owner determination** that the P1B-6 line-count discrepancy is a documentation erratum only (§7).
5. **The §12 owner acceptance** (verbatim; §6).
6. **This repository-only completion record.**

## 3. Fresh preparation evidence (all collected fresh; all PASS)

All times are UTC on 2026-10-07. Every DEV check was on `lilith-dev-01` only.

| Item | Result |
| --- | --- |
| E-1 control | `origin/main` = `ls-remote` = `5752bc8`, clean clone; `MB6_TOOL_PINS_EXACT`; the merged package's tests pass on the clone |
| E-2 / E-3 deploys and freeze | latest DEV deploy `37666101351` (at control), nothing queued or running; **deployment freeze from 18:31:53Z** |
| E-4 DR-5 | deploys `37590712214`, `37657074989`, `37666101351` each `EQUAL` to the pre-M-B6 baseline (`f1869234…`, `a1d98773…`, `f5087042…`): 158 `DENIED`, 0 `ALLOWED`, `P1A-9`, `L1c.3`, `GRANT_ABSENT` |
| E-5 … E-8 | broker PASS (`c4b9cb38…` / `a30bd7d6…`); machine `ae929170…`, boot `eea461c3…`, no reboot pending; K-ACT (`6a61c350…`) and K-WIT (`f8759370…`) preserved, never decrypted |
| E-9 … E-13 | installed root anchor `bc5f00a7…`, witness anchor and Registry V1 `46b0bfc5…` exact; `status --expect P1B-5` PASS; `W5_INSTALLED_CONTENT_VERIFIED` |
| E-14 | `readinessExact`: all 38 release modules of the `provision` path and the CLI wrapper `fda779cd…` exact on DEV |
| E-15 | observer `76e5039e…`, equal to the accepted post-W5 value except the clock |
| E-16 | cloud: 12/12 captures identical to the last accepted set; Admin Activity only `iam.serviceAccounts.actAs`, every entry mapped |
| E-17 … E-19 | Replica A and Replica B (owner, S25, 18:39:49Z) byte-continuous with their accepted baselines, 0 records: `OWNER_REGISTER = KNOWN_EMPTY` (the owner freshness register) |
| E-20 / E-21 | `MB3_LAPTOP_VERIFIED` (`fa662721…`); the operator `expected` form reproduced sequence 1, head `19bf9091…1630`, op `8e3bdbdf…` |
| E-22 | P1B-5 denial proof PASS: 92 `DENIED`, 0 `ALLOWED` |
| E-23 … E-25 | no later state; `GRANT_ABSENT`; the M-B6 verifier `W6_0_NO_MB6_MUTATION` (state directory absent; no ledger, WAL, SHM or journal) |
| closing gate | G-1 … G-9 PASS at 18:55Z; `MB6_CONTINUITY = INTACT_AT_GO_BOUNDARY` |

## 4. M-B6 (exactly one invocation)

| Fact | Value |
| --- | --- |
| pre-go re-check | 18:57Z: control unchanged, clean, no new deploy, nothing pending, no marker |
| go checks | the go equals the 18 template lines; the operator's `check_go` passed; the operator equals its own bytes at `HEAD` |
| pre-state | read-only M-B6 verifier `W6_0_NO_MB6_MUTATION`, before the marker |
| go consumed | `attempts/mb6.json` written `O_EXCL` at **18:57:49Z** (`invocationsPermitted: 1`) |
| command | `sudo -n /usr/local/sbin/lilith-authority-ledger-dev provision 1` |
| invocations | **exactly one**; `provision` was never invoked again |
| CLI result | exit 0, empty stderr, **`CLI_SUCCESS_EXACT`**: sequence 1, head `19bf9091…1630`, `stateDirectory=CREATED` |

## 5. POST, denial proofs and the acceptance-time check

**POST (read-only).** The operator `post` form, 18:58–18:59Z:

- **Result:** `MB6_POST_VERIFIED`, sequence phase **`W6_6_POST_VERIFIED_ACCEPTANCE_PENDING`** before owner acceptance.
  All 8 codes were 0 and `readinessExact` was true.
- **Ledger content:** the independent verifier reports `LEDGER_COMMITTED_EXACT`, failures `[]`. There is exactly
  one journal row (sequence 1, `GENESIS`, the accepted JCS op). `prev_head` = `0^64`, and the head equals the
  owner-accepted head.
- **Database:** schema fingerprint `65127a68…9cb7`; `integrity_check` ok; WAL header; meta and epoch rows exact; no
  other rows.
- **Files:** the state directory is signer-owned `0700`; the ledger is `0600`. **The database is the only
  state-directory entry**: no WAL, SHM or journal.
- **Host state:** `status --expect P1B-6` PASS. W5 is `OUT_OF_SCOPE_POST_LEDGER` with all three trust booleans true.
  `AUTHORIZATION_REGISTER_COPY_MISSING` and `GENESIS_PIN_COPY_MISSING` remain. No later state.
- **Boundaries held:** `registryEffective=false`, `authorityActive=false`, `authorityGranted=false`. Broker PASS,
  unchanged.
- **Observer:** it differs from PRE only in the new state directory and ledger, the clock, and the section digests
  derived from them.

**Denial proofs (read-only):**

- **P1B-6:** `MB6_LEDGER_DENIAL_PROOF=PASS phase=P1B-6 denied=20 allowed=0`, with `GRANT_ABSENT`. The transcript is
  27 lines (§7), SHA-256 `f8722cb7…2e2b`.
- **P1B-5:** PASS, 92 `DENIED`, 0 `ALLOWED`. The transcript is byte-identical to the pre-M-B6 proof.

**Acceptance-time verification (read-only, 19:07–19:08Z).** One `classify` showed:

- host `LEDGER_COMMITTED_EXACT`, head `19bf9091…1630`, the database the only entry, failures `[]`;
- the committed-image digest equal to POST (`fae62c87…`);
- no new deploy and nothing pending.

## 6. Owner acceptance (verbatim, package §12)

The owner issued the §12 acceptance. It equals the package template with only the four placeholders filled
(`<CONTROL>`, `<MARKER_SHA256>`, `<POST_SHA256>`, `<P1B6_SHA256>`):

> I accept M-B6 / PROVISION_LEDGER as technically completed for DEV_SYNTHETIC in the M-B6 sequence on control
> 5752bc8e2ee267ae47db04b37c50cbdfa3a0a361, release aee323e94412accbe321bc84eae78c5b8cf95afc. Provision: exactly
> one /usr/local/sbin/lilith-authority-ledger-dev provision 1; transcript CLI_SUCCESS_EXACT; attempt marker SHA-256
> 75e7307983b3b14150856ad6a953ba9eeaffa2d2e816a4cccaf9980362417f87. Verifier:
> services/owner-memory-control/tools/mb6_ledger_verifier.py SHA-256
> 6449d6ac88313da177665ab9ae7ee9beb86a3a03a22e2a02c2aecf99a79767b5 reports LEDGER_COMMITTED_EXACT; POST_VERIFIED
> (W6-6), POST evidence SHA-256 733377bc62fc908aa8a46d2df05ba59078bb68e2ec9f2b8830706d06048bf93b. Ledger: sequence
> 1; head 19bf9091a96cdc2378a68508feb0c119721f7fcef7b9c3a480a6cd6b72fa1630, equal to the owner-accepted expected
> head; GENESIS op JCS SHA-256 8e3bdbdf3f3730de5ad031d36eb390888fc6e0f65307d947522b0138ffcd7b60; schema
> fingerprint 65127a68c61d4dba390e01c61d01a76fdc54e830c374cb05069b0ab0c50d9cb7; the database is the only entry.
> Denial: MB6_LEDGER_DENIAL_PROOF=PASS phase=P1B-6 denied=20 allowed=0 (transcript SHA-256
> f8722cb7e2cb2ee91b73e4722715ee790c6eb564692ad5cf4d3de38094b92e2b); AUTHORITY_CUSTODY_DENIAL_PROOF=PASS
> phase=P1B-5; GRANT_ABSENT. DR-5: PHASE_BOUND_DR5_BASELINE_WITH_DERIVED_DELTA applies. The post-M-B6 target
> 3640ca0136e5740835f7047480e472e737b2556c14b48db66ff1c1983350f494 (188 lines, 161 DENIED, 0 ALLOWED) remains
> DERIVED and NOT ACCEPTED; its acceptance is separate, after the first post-freeze deploy compares EQUAL.
> LEDGER_PROVISIONED = OWNER-ACCEPTED. REGISTRY_EFFECTIVE = NO. AUTHORITY_ACTIVE = NO.
> AUTHORIZATION_REGISTER_COPY_MISSING and GENESIS_PIN_COPY_MISSING remain. This acceptance does not authorize M-B7,
> M-B8, witness genesis, record 1, First Memory, authority activation or PROD. The M-B6 deployment freeze ends with
> this acceptance (package §13).

**The deployment freeze ended at 19:08:52Z** (package §13). It ended only after both the owner's §12 acceptance and
the read-only acceptance-time host verification of `LEDGER_COMMITTED_EXACT`. It did not end at technical success.

## 7. P1B-6 line-count erratum (owner determination)

```text
P1B6_LINE_COUNT_DISCREPANCY = DOCUMENTATION_ERRATUM_ONLY
correct deterministic transcript line count = 27
  = 2 state + 2 unit + 1 GRANT_ABSENT + 20 DENIED probes + 1 scope + 1 PASS
```

**The mistake.** The [remediation record](slice-15b2b-b1b3e-mb6-ledger-remediation.md) §13 ("Expected PASS
transcript: 28 lines") and the [ceremony package](slice-15b2b-b1b3e-mb6-ceremony-package.md) §9 ("the exact
28-line transcript") miscount. Their own breakdown tables sum to 27.

**The evidence.** The live transcript is byte-equal to the 27-line PASS transcript bound by the merged tests
(`test_b1b3e_mb6_ledger_denial_proof.PASS_TRANSCRIPT`).

**How it is recorded.** As an append-only erratum block after each of those two statements; the original text is
unchanged.

**It does not alter:**

- P1B-6 PASS;
- M-B6 technical success;
- W6-6;
- the owner acceptance;
- the ledger sequence, head, op or schema fingerprint;
- the denial semantics;
- the deployment-freeze history;
- any previous evidence result.

## 8. DR-5 state

| Item | State |
| --- | --- |
| `PHASE_BOUND_DR5_BASELINE_WITH_DERIVED_DELTA` | **APPLIES** |
| pre-M-B6 baseline (`f1869234…`, `a1d98773…`, `f5087042…`) | historical accepted baseline (DR6-1) |
| post-M-B6 target | **DERIVED**: `3640ca0136e5740835f7047480e472e737b2556c14b48db66ff1c1983350f494`, 188 lines, 161 `DENIED`, 0 `ALLOWED`, 0 `FAIL` |
| `POST_MB6_DR5_TARGET_ACCEPTED` | **NO** |

**Not pre-accepted.** The target is accepted only after two steps:

1. the first post-freeze DEV deployment is captured;
2. it compares `EQUAL` under `mb6_dr5_target.py compare LEDGER_COMMITTED_EXACT <log>`, the merged canonical tool,
   after a fresh verifier read confirms `LEDGER_COMMITTED_EXACT`.

Then the owner decides separately (DR6-12). A `DRIFT` result is unexpected, and the owner adjudicates it.

## 9. Boundaries

| Fact | State |
| --- | --- |
| `LEDGER_PROVISIONED` | **OWNER-ACCEPTED** |
| `GRANT_ABSENT` | remains |
| `REGISTRY_EFFECTIVE` | **NO**: ledger provision does not make Registry V1 effective |
| `AUTHORITY_ACTIVE` | **NO**: ledger provision does not activate authority |
| memory writes | not authorized: ledger provision does not authorize any memory write |
| `AUTHORIZATION_REGISTER_COPY_MISSING`, `GENESIS_PIN_COPY_MISSING` | remain (M-B8 work) |
| ledger GENESIS | a journal row of the authority ledger; **not** witness genesis |
| M-B7 | **NOT AUTHORIZED**: M-B6 acceptance granted no M-B7 authority |
| M-B8 | **NOT AUTHORIZED** |
| witness genesis | **NOT AUTHORIZED** |
| record 1 | **NOT AUTHORIZED** |
| First Memory | **NOT AUTHORIZED** |
| authority activation | **NOT AUTHORIZED** |
| PROD | **NOT AUTHORIZED** |

**First Memory boundary.** First Memory must **not** be auto-generated, inferred or chosen by tooling. If technical
bootstrap eventually reaches `FIRST_MEMORY_READY`, the process **STOPS** there. Owner discussion and a separate
explicit owner authorization are required before any First Memory content is created or written. This record
chooses no First Memory content.

## 10. What remains

- The first post-freeze DEV deployment's DR-5 comparison against the derived target, then the owner's separate
  decision on the post-M-B6 baseline (§8).
- M-B7 and every later bootstrap step: each needs its own reviewed design, evidence and explicit owner
  authorization. None is implied here.

## 11. State

```text
M-B6 = COMPLETED / OWNER-ACCEPTED
M-B6 GO = CONSUMED
PROVISION INVOCATIONS = EXACTLY ONE
CLI RESULT = CLI_SUCCESS_EXACT
POST PHASE BEFORE ACCEPTANCE = W6_6_POST_VERIFIED_ACCEPTANCE_PENDING
LEDGER_PROVISIONED = OWNER-ACCEPTED
LEDGER SEQUENCE = 1
LEDGER HEAD = 19bf9091a96cdc2378a68508feb0c119721f7fcef7b9c3a480a6cd6b72fa1630
P1B-6 = PASS (20 DENIED, 0 ALLOWED; 27-line transcript)
P1B-5 = PASS (92 DENIED, 0 ALLOWED)
P1B6_LINE_COUNT_DISCREPANCY = DOCUMENTATION_ERRATUM_ONLY
GRANT_ABSENT = TRUE
TRUST_INSTALLED = YES
REGISTRY_INSTALLED = YES
REGISTRY_EFFECTIVE = NO
AUTHORITY_ACTIVE = NO
AUTHORIZATION_REGISTER_COPY_MISSING = TRUE
GENESIS_PIN_COPY_MISSING = TRUE
DEPLOYMENT_FREEZE = ENDED (after owner §12 acceptance and acceptance-time host verification)
POST_MB6_DR5_TARGET_ACCEPTED = NO
M-B7 = NOT AUTHORIZED
M-B8 = NOT AUTHORIZED
M-B9a / M-B9b = NOT AUTHORIZED
WITNESS GENESIS = NOT AUTHORIZED
RECORD_1 = NOT AUTHORIZED
FIRST_MEMORY = NOT AUTHORIZED
AUTHORITY ACTIVATION = NOT AUTHORIZED
PROD = NOT AUTHORIZED
FRESHNESS=UNKNOWN
```
