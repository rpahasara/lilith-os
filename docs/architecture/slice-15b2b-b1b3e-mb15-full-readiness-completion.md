# Slice 15B2b-B1b-3e — M-B15 / EVALUATE_FULL_READINESS: FULL_READINESS READY Accepted (2026-10-20)

Status:

- **OWNER ACCEPTANCE RECORD (APPEND-ONLY).** It records M-B15 (`EVALUATE_FULL_READINESS`, DEV_SYNTHETIC) on control
  `627ad67d377f6b2af65bec50952d2f1fc78a4b3d` (merge of PR #231, the W14 read-only tooling). The root verifier judged
  FULL_READINESS **READY** over the RELEASED custody record in one read-only DEV session. The result was reproduced
  off-host, the owner confirmed freshness on S25 Replica B, and the owner then accepted M-B15 verbatim (§5).
- `M-B15 = COMPLETED / OWNER-ACCEPTED` (2026-10-20). `CUSTODY = RELEASED`. Nothing on DEV was written.
- **The earlier record is unchanged.** The [W14 package record](slice-15b2b-b1b3e-mb15-w14-full-readiness-package.md)
  (`PACKAGE PREPARED FOR OWNER REVIEW`, M-B15 `NOT AUTHORIZED`) was correct when written and is historical. It is not
  rewritten. This record supersedes it on the M-B15 outcome only, from 2026-10-20.
- **FULL_READINESS READY grants no authority.** Authority stays **DARK**, issuance stays **UNWIRED** (RR-39),
  `authorityGranted` stays false, Registry V1 is **NOT EFFECTIVE**, First Memory is **NONE**, and no PROD authorization
  exists. This document grants no new authority.
- **The first post-M-B15-record deploy has NOT yet occurred.** Its DR-5 comparison is **PENDING** (§7).

```text
W14_1 technical observation != M-B15 owner acceptance != this record merged != post-merge deploy EQUAL
FULL_READINESS READY = local readiness facts only;  READY != activation != issuance != Registry V1 effective
```

## 1. Identities

| Item | Value |
| --- | --- |
| control | `627ad67d377f6b2af65bec50952d2f1fc78a4b3d` (clean clone; the W14 tooling of PR #231) |
| control deploy | `39369390461`; DR-5 `EQUAL` 194 / 155 / 29 against the unchanged E-22 target (comparison `c9ba3e98…`) |
| RELEASED record | `bb7576f4437fb61dd31adafe50ac56eba467c7f98b329b7149942e630f1ef003`, listing `c4cb1319…` (M-B14) |
| owner-input envelope | `3128a0a857cae8a0121c2febf97f2e6e0e9a3f0e92f9fa6bec843dba13c875fb` (**historical** M-B12 owner input; §3) |
| prep tools manifest | `5054690f1b28aa1784e4f82c6ef90086008518feeaddd40fd5976aa1e743ac7c` |

## 2. Result

| Gate | Provenance | Result |
| --- | --- | --- |
| freeze PRE_SESSION / POST_DEV / PRE_DECISION | GitHub reads | exact ×3 (PRE_DECISION seal `8d1cf1ba2edaec0db2f3fd6bdca72354439be1fa53883772c3e6579f3d0cdc41`) |
| currency OPEN / CLOSE | live DEV, read-only | exact; boot `cb0d71da-32a7-402b-b85e-5748da012bff` unchanged; no pending reboot; activation line exact (rc 1); signer `efbc0784…` / 128648, witness `8cbfbed2…` / 127192, broker `ed35e343…` / 3411; custody output `abcc26fb…` at both |
| E-09 broker preservation | live DEV, read-only | PASS (transcript `79387fe7…` = the pinned accepted transcript) |
| E-23 preservation set | live observation + off-host compare | §4 |
| witness export / chain relation | live read + off-host | chain-1 = witness = `252c3220…`; derived export = sealed bundle member `d542e616…` |
| **W14 `observe`** | live DEV, read-only | **`W14_1_RELEASED_FULL_READY_OBSERVED`**, reasons `[]`; record SHA-256 `0b4b727ac7798b40ed9c72cb9433e2c5a2b59c417d1d84a2ccfab97a17cf62c3` |
| **FULL package** | root verifier | **READY**, `issuanceWired` false; digest `1509133ccb06ed15c2eb3c76e2cf02fdc244dd388e7de17ad5a3893b278503dc` |

W14 also reports eligibility `NOT_READY` (`CEREMONY_HOLD:HOLD_NOT_HELD`). This is expected under RELEASED and is not a
FULL_READINESS failure. W14 itself does not judge envelope currency (`NOT_JUDGED`) or owner freshness
(`NOT_EVALUATED`), and it does not establish M-B15 (`mb15Established` false). Those were settled by §3, §5 and the
owner decision.

**E-22 is `OWNER_RISK_ADJUDICATED`, not PASS.** Inside the FULL package, E-22 (SECRET_HYGIENE) is carried as the
OD-M12-10 owner risk adjudication, exactly as in the [E-22 completion record](slice-15b2b-b1b3e-e22-completion.md).
FULL_READINESS READY does not turn that adjudication into a pass.

**Independent off-host reproduction** (clean control, owner material):

- W14 `classify` re-judged the retained transcripts and produced the identical record (`0b4b727a…`, `W14_1`, reasons `[]`).
- RR-38 B `offhost_reproduction` on the FULL package: `REPRODUCED`, mismatches `[]`.
- Replica A (WSL): `REPLICA_VERIFIED`, `AUTHENTIC:CURRENT`, head `77752db1…`, version 1 (`REPLICA.json` `fbdd045c…`).

## 3. Envelope provenance

The owner-input envelope `3128a0a8…` is the accepted M-B12 owner input. It is **historical** evidence, reused by owner
decision for M-B15. The E-19 activation line and the owner proofs come from it, so W14 records
`activationObservedLive` false. Its currency is supplied separately by the fresh currency OPEN / CLOSE reads of §2
(same boot, same signer, witness and broker identities, same custody output). The envelope was not re-created or
re-signed.

## 4. E-23 preservation

| Item | Value |
| --- | --- |
| observation | 22 members, refused `[]`, rc 0, `2026-10-20T07:00:41Z`; SHA-256 `3999200c51647b1c20cfe7c5d9cfb10a3bc46caa0944fd7d2ab712acd4280747` |
| expected absences | `STAGE3_ACTIVATION_READY`, `STAGE3_ARM`, `STAGE3_AUTHORIZATION_USED`, `STAGE3_GUARD` absent, as expected |
| off-host compare | pinned producer, WSL: `PRESERVATION_SET_PROOF=PASS` against baseline `019e0117…` (`2026-10-17T10:38:08Z`); `compare.out` `63b9e8ae…` |

## 5. Owner freshness (S25) and acceptance

**S25 Replica B (evidence class `OWNER_SCREEN_TRANSCRIPTION`).** The owner ran the read-only
`E25-S25-READONLY-MB15.sh` (SHA-256 `5d7fc13cebf56280bbe2a19e6627ea39df260e10ed748b8d4db1ba15ca79ae0f`) once on the
S25 Ultra (Termux) and transcribed the result from their own screen. The agent did not run or observe it. The reported
result-block SHA-256 `623db45000094f73e1b6b8b49046b36e93d32b0f095547a693d0dc2ba71e86b6` equals the SHA-256 of the
expected 14-line block, so every line matched exactly: `FRESHNESS=AUTHENTIC:CURRENT`,
`ACCEPTANCE=ACCEPTANCE_COMPLETE`, `STORE_B=ACCEPTANCE_STORE_VERIFIED:1`, Replica B head `77752db1…` version 1, and
`MB15_E25_RESULT=EXACT`. The S25 check is not repeated.

**Accepted statement (verbatim, `ACCEPT-PROPOSED.txt`, SHA-256
`0e6fa79574e96ccab759bc5c691ff94c9899fc26f46eaafec0976cef1b683a65`):**

> I accept M-B15 / EVALUATE_FULL_READINESS for DEV_SYNTHETIC: FULL_READINESS is READY for INITIAL_CUSTODY RELEASED bb7576f4437fb61dd31adafe50ac56eba467c7f98b329b7149942e630f1ef003.
> W14 record SHA-256 0b4b727ac7798b40ed9c72cb9433e2c5a2b59c417d1d84a2ccfab97a17cf62c3, FULL package digest 1509133ccb06ed15c2eb3c76e2cf02fdc244dd388e7de17ad5a3893b278503dc, evidence digest 1febbd244958a22d807a8201a84946c7f66a7f388bc83871733ebcd98726287e.
> Owner freshness AUTHENTIC + CURRENT with ACCEPTANCE_COMPLETE (S25 result block 623db45000094f73e1b6b8b49046b36e93d32b0f095547a693d0dc2ba71e86b6, owner-transcribed).
> Issuance remains unwired and authorityGranted remains false.
> This acceptance authorizes nothing further: not authority activation, issuance, Registry V1 effectiveness, First Memory or PROD.

**Owner decision (verbatim, 2026-10-20, `OWNER-MESSAGE.txt`, SHA-256
`eeb8f2e8f0531919ec8c09c60286cbe0b9826935e2bb8fd1a1a0d00d3bbe60c7`):**

> I accept M-B15 with the proposed statement verbatim (ACCEPT-PROPOSED.txt, SHA-256 0e6fa79574e96ccab759bc5c691ff94c9899fc26f46eaafec0976cef1b683a65). Record it off-host; nothing further is authorized.
>
> I explicitly accept M-B15 / EVALUATE_FULL_READINESS for DEV_SYNTHETIC.
>
> FULL_READINESS is READY for INITIAL_CUSTODY RELEASED `bb7576f4437fb61dd31adafe50ac56eba467c7f98b329b7149942e630f1ef003`.
>
> W14 record SHA-256: `0b4b727ac7798b40ed9c72cb9433e2c5a2b59c417d1d84a2ccfab97a17cf62c3`
>
> FULL package digest: `1509133ccb06ed15c2eb3c76e2cf02fdc244dd388e7de17ad5a3893b278503dc`
>
> Final evidence digest: `1febbd244958a22d807a8201a84946c7f66a7f388bc83871733ebcd98726287e`
>
> Owner freshness is AUTHENTIC + CURRENT with ACCEPTANCE_COMPLETE, supported by the owner-transcribed S25 result-block SHA-256 `623db45000094f73e1b6b8b49046b36e93d32b0f095547a693d0dc2ba71e86b6`.
>
> Issuance remains unwired and authorityGranted remains false.
>
> This acceptance authorizes nothing further: no authority activation, issuance, Registry V1 effectiveness, First Memory or PROD.
>
> Record this explicit owner acceptance against the accepted evidence. Do not create a PR, merge, deploy or perform further live operations without separate authorization.

This docs-only record was opened under a separate owner authorization (one completion PR, 2026-10-20). That
authorization covers no merge, deploy or live operation.

| Item | Value |
| --- | --- |
| acceptance record | `MB15_ACCEPTANCE.json` `02cd6b1ae10ebb830475970993167053f8777fcdd100f8f50ea49646c39245d7` (`acceptedOn` 2026-10-20, `verbatim` true, `authorityGranted` false, `issuanceWired` false, `s25Provenance` `OWNER_SCREEN_TRANSCRIPTION`) |
| acceptance seal | `SHA256SUMS` `6774283fe6b733c59cb78b413a1c1e83f82749b04f796bc53374dd627d986734` (statement, owner message, acceptance record) |

## 6. Off-host evidence

The evidence folders are identified by name. They live in the owner's private evidence root, outside Git.

| Evidence folder | Contents | Seal |
| --- | --- | --- |
| `lilith-mb15-seq3-627ad67` | the read-only DEV session: freezes, currency, E-09, E-23, chain, W14, off-host reproduction (control clone `ctl/` not sealed) | `SHA256SUMS` `bfc8ed91aee2866c5d308f496d6a75064b36430a5dc13064189fe930406f06e0`; `freeze-pre_decision/SHA256SUMS` `8d1cf1ba…` (sealed separately) |
| `lilith-mb15-final-627ad67` | final summary, owner S25 transcription, expected result block, references | `SHA256SUMS` = final evidence digest `1febbd244958a22d807a8201a84946c7f66a7f388bc83871733ebcd98726287e` |
| `lilith-mb15-accept-627ad67` | accepted statement, owner message, `MB15_ACCEPTANCE.json` | `SHA256SUMS` `6774283f…6734` |
| `lilith-mb15-prep-627ad67` | the reviewed v3 drivers | `SHA256SUMS` `5054690f…7c` |

The two stopped sessions are retained unchanged and are not part of the accepted result: seq1 `a85af776…` (a preflight
false positive) and seq2 `25b776e2…` (a local transport-configuration error). Neither wrote anything to DEV.

## 7. Post-merge deploy (PENDING)

If merging this record triggers a DEV deployment, its DR-5 comparison must be `EQUAL` to the unchanged E-22 target
(194 / 155 / 29). Anything other than `EQUAL` is a STOP for owner review. The target is not rebaselined, and no gate is
relaxed to admit it. This verification has **not** been performed.

## 8. State

```text
M-B14 = COMPLETED / OWNER-ACCEPTED 2026-10-19 (RELEASED bb7576f4…f003)
M-B15 = COMPLETED / OWNER-ACCEPTED 2026-10-20 (FULL_READINESS READY; package 1509133c…03dc; evidence 1febbd24…287e)
CUSTODY = RELEASED;  AUTHORITY = DARK;  ISSUANCE = UNWIRED (RR-39);  REGISTRY V1 = NOT EFFECTIVE
FIRST MEMORY = NONE;  PROD = NOT AUTHORIZED;  E-22 = OWNER_RISK_ADJUDICATED (OD-M12-10), not PASS
post-merge deploy DR-5 = PENDING (must be EQUAL 194 / 155 / 29; no rebaseline)
```
