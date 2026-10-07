# Slice 15B2b-B1b-3e — M-B4/M-B5 `INSTALL_TRUST_AND_REGISTRY`: Completion and Owner Acceptance (Sequence 2, 2026-10-07)

Status:

- **`INSTALL_TRUST_AND_REGISTRY = COMPLETED / ACCEPTED`.**
  - **M-B4 / install-anchors = COMPLETED / ACCEPTED.** The installer ran
    exactly once and passed P1B-4. The POST passed, and W3 is confirmed. The
    M-B4 go was consumed exactly once.
  - **M-B5 / install-registry = COMPLETED / ACCEPTED.** The installer ran
    exactly once and passed P1B-5. The POST passed, W5 is confirmed and the
    P1B-5 denial proof passed. The M-B5 go was consumed exactly once.
  - Both ran inside owner-authorized preparation **Sequence 2** under the
    accepted
    [`MB4_MB5_CONTINUITY = OWNER_ATTENDED_EVENT_BOUNDED_SINGLE_SEQUENCE_TWO_GO`](slice-15b2b-b1b3e-mb4-mb5-continuity-owner-decision.md),
    using the merged [ceremony package](slice-15b2b-b1b3e-mb4-mb5-ceremony-package.md)
    at control `82b89a32f619ed3e41f0f4d1c642bf5187c74710`.
- **Owner acceptance (§12.3 template, §9):** the trust is installed
  (technical, owner-accepted). The registry is installed but **not
  effective**, and **no authority is active**.
- **The K-WIT burn/regenerate option is CLOSED** (continuity C-9). It does not
  reopen if the installed files are later removed before M-B6.
- **Sequence 1 stays historical** (§2). The first M-B4 POST anomaly is
  recorded as it happened (§6).
- **Nothing later is authorized.** M-B6, genesis, record 1, First Memory and
  PROD remain **NOT AUTHORIZED**. `FRESHNESS=UNKNOWN`.
- **Operational record.**
  - The raw evidence is owner-held outside the repository, in the external
    Sequence-2 evidence set on the laptop (location not published).
  - No K-ROOT private material was read and K-WIT was never decrypted.
  - No repository file changed during the live sequence. This record was
    written afterwards, repository-only, and contacted no live system.

```text
preparation sequence != transfer != closing gate != M-B4 go != one install-anchors invocation
  != M-B4 POST (W3) != continuity check K-1..K-8 != M-B5 go != one install-registry invocation
  != M-B5 POST (W5) != owner acceptance (trust installed, technical)
trust installed + registry installed != registry effective != authority active
M-B4/M-B5 completion != M-B6 / genesis / record 1 / First Memory / PROD authorization
a read-only re-classification after a STOP != a retry of the mutation
```

## 1. Identities

| Item | Value |
| --- | --- |
| repository control | `82b89a32f619ed3e41f0f4d1c642bf5187c74710` (merge of PR #162, the [operator real-load fix](slice-15b2b-b1b3e-mb4-mb5-prep-seq1-operator-loader-incident.md)); unchanged through the sequence |
| post-merge validation / DEV deploy | `37577051261` (success) / `37577178942` (success, at control) |
| operator | `services/owner-memory-control/tools/mb4_mb5_operator.py`, SHA-256 `e380ab1852ba72fe511c650446867c8d229d95776af3c1d4266fa949c0a9de1a` |
| installer | `install_authority_dev.py`, SHA-256 `fe10d9a37c53d4a32ca49d79ee5987c6546866feeebcee3c882087f51ed55487`; release `aee323e94412accbe321bc84eae78c5b8cf95afc` |
| **installed `registry-root.json`** | `/etc/lilith-authority-dev/trust/registry-root.json`, SHA-256 **`bc5f00a76b518c4f11b6804d35844c036db75eaa730d56c35f97f430558ff687`**, 179 bytes, `root:root 0644` |
| **installed `witness-anchor.json`** | `/etc/lilith-authority-dev/trust/witness-anchor.json`, SHA-256 **`be360da2324880d725aea509bb0f41500f51ecfc3c2995dd3057824bb471ab5a`**, 176 bytes, `root:root 0644` |
| **installed `authority-registry.v1.json`** | `/etc/lilith-authority-dev/registry/authority-registry.v1.json`, SHA-256 **`46b0bfc558ec3a19467206ada3dc53c18e8a6a4cd0782711b4800cfe099f8b1e`**, 955 bytes, `root:root 0644` |
| Registry V1 digest | `fa66272131a3ef076036616b07766a377de4fdc1e4fef4cb8a054726f05c14fc` (unchanged identity) |
| signed transport / M-B3 export | `3f0a59c0a104934730184d28bc16e1c9215bdaa6ec1f9d94753722862f486156` / `c4ea3d66fdef3f6b30c63a1f7f4903a3d2d5427f0419c6e1bd7aadd12c9564d8` (export unchanged before and after derivation) |
| E-21 K-ROOT | `publicKeySha256=cb36daf176d813359b8bd0fe6361f549fd3334a52d0cd1f85cc5247cb26592cf` (= the installed root anchor's key) |
| K-WIT | `publicKeySha256=5d778701def439b6c896392750c12685c26b67edfc908bed1a80f02eab0d0bdf` (= the installed witness anchor's key) |
| K-ACT | `publicKeySha256=dd13a1fb302375a4e7ec81131a72920e23e365e06a0b6dc9bb7ab124dadc01ed`; blob `6a61c350e848a833868f4573982fca9c75e2af79ccc9bd3716ae0303c26973f3`, publication `d76479762007afef828f3901591647dc4a2fb2205f4afac527b66d2cc9c6b032` (unchanged throughout) |
| K-WIT blob | `f87593701ee5e9272363a473a115b87cc06179df3c0b233af4aa62bb5b9b97be` (unchanged; never decrypted) |
| M-B4 go file | SHA-256 `f7b1bab66cbf83c10d27cc1fe960bbd7f11c3049ba644e2d7c7b354cf668c10a`; marker `attempts/mb4.json` `startedAt 2026-10-07T07:00:19Z`, `invocationsPermitted 1` |
| M-B5 go file | SHA-256 `d0441a5abae0bb8054c9a74b78c0f8bb0f5ddfe91a562948b96c3e85a9cc0513`; marker `attempts/mb5.json` `startedAt 2026-10-07T07:27:34Z`, `invocationsPermitted 1` |
| staged `SHA256SUMS` | `f262a61a866db22b94b43102f8eaba69d42768505af5aa3657925c89101a299e` |
| external evidence set | owner-held (location not published); `SHA256SUMS` SHA-256 `62f8a2f08fea18bfb6c78787f94c060739a5c7b367ea9133387376af9c1eafdc` |

## 2. Preparation Sequence 1 (historical; unchanged)

Recorded in the [sequence-1 incident record](slice-15b2b-b1b3e-mb4-mb5-prep-seq1-operator-loader-incident.md):

- control `ffa9575`; it **ended at E-21** on the operator real-load defect
  (`2d9835ed…`, the derivation module not registered in `sys.modules`);
- no derivation output, no transfer, no staging, no authority mutation;
- no M-B4 or M-B5 go consumed; no burn;
- its evidence is **HISTORICAL / NON-REUSABLE**, and its freeze was released;
- the fix (operator `e380ab18…`, real-load regression tests) was reviewed and
  merged as PR #162 (`82b89a3`).

Nothing from Sequence 1 was replayed in Sequence 2.

## 3. Owner authorizations in Sequence 2 (each separate, in order)

1. Preparation / fresh re-proof only (E-1 … E-21; E-22 pending).
2. A narrow **E-18 provenance decision**:
   - merged main records the Replica B block by its prefix `72f99d4e…` only;
   - the owner accepted the byte-identical block
     `72f99d4e8dba964e38f59977b3143931eb947220356ce6c461642feaba840d12` from
     two accepted evidence sets (B-5 refresh, M-B2);
   - this applies to Sequence 2 / E-18 only and sets no general rule.
3. E-22 transfer / staging only.
4. The §7.1 M-B4 closing gate (read-only) only.
5. **The M-B4 one-attempt go** (§7.2 template, verbatim, 12 lines):
   - an earlier non-template authorization lacked the binding lines;
   - it reached no operator, wrote no marker and consumed nothing;
   - the verbatim go followed.
6. Exactly one read-only W3 re-classification (§6).
7. The §9.1 continuity check K-1 … K-8 (read-only), with the owner's K-1
   classification (§7).
8. **The M-B5 one-attempt go** (§9.2 template, verbatim, 11 lines, with the
   U+2026 ellipsis preserved).
9. **Acceptance** (§12.3, verbatim; §9).
10. Post-acceptance staging cleanup only.

## 4. Fresh preparation evidence (Sequence 2; all collected fresh)

All times are UTC on 2026-10-07. Every DEV check was on `lilith-dev-01` only.

| Item | Result |
| --- | --- |
| E-1 control | `origin/main` = `ls-remote` = `82b89a3`, clean clone; `MB4_MB5_TOOL_PINS_EXACT`; operator `e380ab18…` (05:44:46Z) |
| E-2 / E-3 deploys | latest DEV deploy `37577178942` (at control, nonmaterial by content); nothing queued or running; **deployment freeze from 05:49:49Z** |
| E-14 DR-5 | the 11 deploys `37445851939` … `37577178942` each byte-identical to the accepted run `36552218231`: result set `f18692342cd62572affa54c83f9d390d21ac183e85dc8496dbadb0d5f3f49f9b`, DR-5 block `a1d98773…`, pre-deploy block `f5087042…`. Each run showed 158 `DENIED`, 0 `ALLOWED`, `P1A-9`, `L1c.3`, `GRANT_ABSENT` |
| E-19 Registry V1 custody | `verify_mb3_registry.py` (`e710cfa6…`) with the M-B3 go pins: `MB3_LAPTOP_VERIFIED`, digest `fa662721…14fc`, transport `3f0a59c0…6156` |
| E-21 derivation | fixed operator `derive`: `MB4_MB5_DERIVED_PINNED`, the three exact pins, independent re-hash, `SHA256SUMS -c` OK; registry = transport minus one LF; root key = E-21, witness key = K-WIT; export unchanged |
| E-20 E-21 confirmation | owner S25 screen-only (06:13:14Z): the public fingerprint `cb36daf1…92cf` and the anchor `300a57dc…` read from the authoritative public copy; no K-ROOT file opened |
| E-17 / E-18 / E-16 | Replica A: 0 records, manifest `fbdd045c…`, inodes unchanged, `REPLICA_VERIFIED`. Replica B (owner, 06:17:25Z): byte-identical to the accepted M-B2 read (manifest `c068e533…`, 0 records, inodes `973613/973617/973618`), settings OFF, custody attested. **`OWNER_REGISTER = KNOWN_EMPTY`** |
| E-4 … E-11 host W0 | `MB4_MB5_HOST_W0_PASS`, `readinessExact=true`: machine `ae929170…`, boot `eea461c3-60f0-4b10-8ee9-556dcef19711`, no reboot pending; broker PASS (`c4b9cb38…` / `a30bd7d6…`); K-ACT CURRENT and K-WIT preserved (inodes and times as accepted); `status --expect P1B-2` PASS; `W0_PRE_INSTALL`; R-1 … R-5 (14 modules exact); observer `94cb28f01571904e277a142e518326dd3930b8ca2f90f364aff6ee24b704c70c`; `GRANT_ABSENT` |
| E-12 cloud | 11 JSON captures + bucket list byte-identical to the last accepted set; Admin Activity only `iam.serviceAccounts.actAs` (reviewed deploys and this sequence's own IAP sessions) |
| E-13 / E-15 | `NO_APPLICABLE_INVALIDATOR` (G-1 … G-9); `NO_B5_STOP` |
| E-22 transfer | after a fresh pre-transfer `host W0` + cloud re-read: the operator `stage` form; exactly four files into `/home/ravindupahasara2_gmail_com/lilith-mb4-mb5-stage` (`0700`), as the operator, no `sudo`; `MB4_MB5_STAGED_FILES_PINNED_ON_HOST`; host `sha256sum -c --strict` OK |
| §7.1 closing gate | control, runs, pins, `staged_check`, `host W0` identical to the E-checks, cloud 12/12 identical, audit fully explained: **PASS** |

## 5. M-B4 (exactly one invocation)

| Fact | Value |
| --- | --- |
| pre-go re-check | 06:58:47Z: control, runs, pins, `staged_check`, `host W0` identical |
| go checks | the operator's `check_go`: all 12 binding lines present |
| go consumed | `attempts/mb4.json` written `O_EXCL` at **07:00:19Z**, after pins, go lines and `staged_check` |
| command | hash-gated `install_authority_dev.py install-anchors aee323e… <stage>/registry-root.json <stage>/witness-anchor.json` |
| invocations | **exactly one**; `install-anchors` was never invoked again |
| installer | exit **0**, `result=PASS`, `stage=P1B-4`, `failures=[]`, stderr empty, no prompt |

## 6. M-B4 POST incident and re-classification (preserved as it happened)

**First POST (`host … W3`, 07:00:55Z–07:02:32Z): formal NOT_PASS.**

- The operator result was `MB4_MB5_HOST_W3_NOT_PASS`.
- One local read-only client, the custody read, exited `3221225477`
  (`0xC0000005`, a Windows access violation in the local Cloud SDK client).
  Every other sub-read was 0.
- The custody output was complete and its stderr empty. The host facts
  showed W3: `status --expect P1B-4` PASS; verifier
  `W3_ANCHORS_INSTALLED_REGISTRY_ABSENT`; both anchors exact.
- Under package §8 this was a STOP. **No mutation was retried.**

**Owner decision.** The owner authorized exactly one package-permitted
read-only `host … W3` re-classification (§15). It did not authorize another
M-B4 attempt.

**Re-classification (07:08:57Z): `MB4_MB5_HOST_W3_PASS`.**

- All seven sub-read exit codes were 0, including custody; stderr was empty.
- Every fact was identical to the first POST.
- One sub-read session was delayed: the verifier's local client opened at
  07:14:17Z. That is explained in the audit (§7).

**Result: M-B4 POST = PASS; W3 CONFIRMED.**

| Required (§8) | Result |
| --- | --- |
| `status --expect P1B-4` | PASS |
| verifier | `W3_ANCHORS_INSTALLED_REGISTRY_ABSENT`, exit 0 |
| `anchorsEqualOwnerCopies` / `witnessAnchorNamesKWit` / `registryVerifiesOnHost` | true / true / false |
| `trustInstalledCandidate` | false |
| registry | absent (`REGISTRY_STORE_MISSING`) |
| E-4 … E-9 | unchanged (same boot, broker PASS, K-ACT / K-WIT identical) |
| observer | differs from W0 only in the trust directory times (the two new files) and the clock; `656d253e231ace4e8d6328007a793e48be4742a89c6118d9ba85889fbcab397a` |

## 7. Inter-stage continuity K-1 … K-8 (§9.1)

- **K-1:** the owner classified the interval from the first POST anomaly to
  the clean re-classification as
  **`ATTENDED_OWNER_ADJUDICATION_WITHOUT_CONTINUITY_BREAK`**. This is for this
  Sequence-2 incident only. It does **not** establish that arbitrary STOPs or
  pauses preserve continuity.
- **K-2 / K-3:** control `82b89a3`, pins exact, latest deploy `37577178942`,
  nothing queued; the freeze was intact.
- **K-4:** `host … W3` `MB4_MB5_HOST_W3_PASS`, all codes 0, facts equal to
  the confirmed W3.
- **K-5:** `staged_check` PASS; the staged files were unchanged (same inodes,
  hashes and `SHA256SUMS`).
- **K-6:** cloud 12/12 identical. The audit held 66 owner
  `iam.serviceAccounts.actAs` entries since the closing gate, each one mapped
  to a Sequence-2 session:
  - pre-go 16;
  - M-B4 4;
  - first POST 14;
  - re-classification 14, including the delayed verifier session at
    07:14:17Z;
  - K-4 14;
  - K-5 4.
- **K-7 / K-8:** no custody event observed or reported; K-ACT / K-WIT
  unchanged; Replica A unchanged; the Registry V1 export unchanged; no
  terminator. **K-1 … K-8 PASS.**

## 8. M-B5 (exactly one invocation), POST and denial proof

| Fact | Value |
| --- | --- |
| pre-go re-check | 07:27:25Z: control, runs, `attempts/mb4.json` present |
| go checks | the operator's `check_go`: all 11 binding lines present |
| go consumed | `attempts/mb5.json` written `O_EXCL` at **07:27:34Z** |
| command | hash-gated `install_authority_dev.py install-registry aee323e… <stage>/authority-registry.v1.json` |
| invocations | **exactly one** |
| installer | exit **0**, `result=PASS`, `stage=P1B-5`, `failures=[]`, stderr empty, no prompt |

**POST (`host … W5`, 07:28:00Z): `MB4_MB5_HOST_W5_PASS`, all codes 0.**

| Required (§10) | Result |
| --- | --- |
| `status --expect P1B-5` | PASS |
| verifier | `W5_INSTALLED_CONTENT_VERIFIED`, exit 0, `failures=[]` |
| `anchorsEqualOwnerCopies` / `witnessAnchorNamesKWit` / `registryVerifiesOnHost` | true / true / true |
| `trustInstalledCandidate` / `registryEffective` / `authorityGranted` | true / false / false |
| `registryDigest` | `fa66272131a3ef076036616b07766a377de4fdc1e4fef4cb8a054726f05c14fc` |
| `hostInputReasons` | exactly `AUTHORIZATION_REGISTER_COPY_MISSING`, `GENESIS_PIN_COPY_MISSING` |
| E-4 … E-9 | unchanged |
| observer | differs from W3 only in the registry directory times and the clock; `76e5039ecb268a6a7f19f1d79a899c52d19eee0ba15280ee6ca0558920975943` |
| denial proof | `AUTHORITY_CUSTODY_DENIAL_PROOF=PASS phase=P1B-5`: **92 `DENIED`, 0 `ALLOWED`, 0 `FAIL`** (15 against the three installed files) |

## 9. Owner acceptance (verbatim, §12.3)

> I accept the verified M-B4/M-B5 INSTALL_TRUST_AND_REGISTRY result of this sequence: P1B-5 PASS; W5_INSTALLED_CONTENT_VERIFIED; anchorsEqualOwnerCopies, witnessAnchorNamesKWit and registryVerifiesOnHost true; denial proof P1B-5 PASS.
> TRUST_INSTALLED = YES (technical, owner-accepted). REGISTRY_EFFECTIVE = NO. AUTHORITY_ACTIVE = NO.
> This acceptance does not authorize M-B6, genesis, record 1, First Memory or PROD. FRESHNESS = UNKNOWN.

## 10. Staging cleanup (§6; separately authorized)

- **Before removal** (07:31:46Z), with nothing removed until all three
  passed:
  - `staged_check` returned `MB4_MB5_STAGED_FILES_PINNED_ON_HOST`;
  - exactly the four entries, with exact pins;
  - `sha256sum -c --strict` OK.
- **Removal:** the operator `cleanup` form ran as the operator account
  **without `sudo`**: `rm -f` of exactly the four named files, then `rmdir`
  of the stage directory. Result `MB4_MB5_STAGE_CLEANED`.
- **After cleanup** (07:32:44Z):
  - `STAGE_DIR_ABSENT`;
  - `host … W5` `MB4_MB5_HOST_W5_PASS`, all codes 0;
  - status and verifier byte-equal to the M-B5 POST, so the installed files
    are unchanged;
  - `status --expect P1B-5` PASS;
  - units inactive, `GRANT_ABSENT`, observer unchanged.
- **The deployment freeze ended at 07:34:02Z**, only after cleanup.

## 11. What remains

- **M-B6** and every later bootstrap step need their own reviewed design or
  preflight, fresh evidence and a separate explicit owner authorization.
  **This completion does not authorize any of them.**
- **The registry is not effective, and no authority is active.** The
  authorization-register copy and the genesis-pin copy are still missing on
  the host (`hostInputReasons`), and no ledger exists.
- **Evidence from Sequence 2 is sequence-bound and not reusable** for a later
  step.
- **Removal before M-B6** stays possible only under its own authorization
  (§12.4). It would never reopen the K-WIT option and never restore a
  consumed go.

## 12. State

```text
INSTALL_TRUST_AND_REGISTRY = COMPLETED / ACCEPTED
M-B4 = COMPLETED / ACCEPTED
M-B4 INSTALLER = PASS / P1B-4
M-B4 POST = PASS (FIRST POST NOT_PASS: LOCAL CUSTODY CLIENT EXIT 3221225477 / 0xC0000005; ONE READ-ONLY RE-CLASSIFICATION MB4_MB5_HOST_W3_PASS, ALL CODES 0)
W3 = W3_ANCHORS_INSTALLED_REGISTRY_ABSENT / CONFIRMED
M-B4 GO = CONSUMED EXACTLY ONCE; INSTALL-ANCHORS INVOCATIONS = 1; NO RETRY
K-WIT_BURN_REGENERATE_OPTION = CLOSED
K1_TO_K8 = PASS (K-1 OWNER CLASSIFICATION: ATTENDED_OWNER_ADJUDICATION_WITHOUT_CONTINUITY_BREAK; THIS SEQUENCE ONLY)
M-B5 = COMPLETED / ACCEPTED
M-B5 INSTALLER = PASS / P1B-5
M-B5 POST = PASS
W5 = W5_INSTALLED_CONTENT_VERIFIED / CONFIRMED
M-B5 GO = CONSUMED EXACTLY ONCE; INSTALL-REGISTRY INVOCATIONS = 1
DENIAL PROOF = PASS / PHASE P1B-5 (92 DENIED, 0 ALLOWED, 0 FAIL)
INSTALLED registry-root.json = bc5f00a76b518c4f11b6804d35844c036db75eaa730d56c35f97f430558ff687
INSTALLED witness-anchor.json = be360da2324880d725aea509bb0f41500f51ecfc3c2995dd3057824bb471ab5a
INSTALLED authority-registry.v1.json = 46b0bfc558ec3a19467206ada3dc53c18e8a6a4cd0782711b4800cfe099f8b1e
REGISTRY_V1_DIGEST = fa66272131a3ef076036616b07766a377de4fdc1e4fef4cb8a054726f05c14fc
E-21 publicKeySha256=cb36daf176d813359b8bd0fe6361f549fd3334a52d0cd1f85cc5247cb26592cf
K-WIT publicKeySha256=5d778701def439b6c896392750c12685c26b67edfc908bed1a80f02eab0d0bdf
TRUST_INSTALLED = YES (TECHNICAL, OWNER-ACCEPTED)
REGISTRY_INSTALLED = YES
REGISTRY_EFFECTIVE = NO
AUTHORITY_ACTIVE = NO
MB4_MB5_PREPARATION_SEQUENCE_1 = ENDED / HISTORICAL / NON-REUSABLE
MB4_MB5_PREPARATION_SEQUENCE_2 = COMPLETE
STAGING = CLEANED (STAGE_DIR_ABSENT)
DEPLOYMENT_FREEZE = ENDED
M-B6 = NOT AUTHORIZED
GENESIS = NOT AUTHORIZED
RECORD_1 = NOT AUTHORIZED
FIRST_MEMORY = NOT AUTHORIZED
PROD = NOT AUTHORIZED
FRESHNESS=UNKNOWN
NO K-ROOT PRIVATE ACCESS; K-WIT NEVER DECRYPTED; THIS RECORD CONTACTED NO LIVE SYSTEM
```
