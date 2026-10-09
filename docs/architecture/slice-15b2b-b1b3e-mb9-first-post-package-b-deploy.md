# Slice 15B2b-B1b-3e — First Post-Package-B-Freeze Deploy: Running-Witness DR-5 Comparison (2026-10-09)

Status:

- **OWNER ACCEPTANCE RECORD (APPEND-ONLY).** It records the first DEV deployment after the Package B deployment
  freeze ended: run `37888892605` compared `EQUAL` to the derived running-witness DR-5 target under the W9-verified
  host phase `W9_5_GENESIS_COMMITTED_EXACT`. The owner then accepted it (§6, verbatim).
- `FIRST_POST_PACKAGE_B_FREEZE_DEPLOY = EQUAL / OWNER-ACCEPTED`. The running-witness target is accepted **only** as
  the phase-bound comparison target for `W9_5_GENESIS_COMMITTED_EXACT`. **It is not a new global baseline.**
- **Package B was already completed and owner-accepted before this deploy**
  ([Package B completion record](slice-15b2b-b1b3e-mb9-package-b-completion.md), B5). That record states
  `FIRST_POST_PACKAGE_B_FREEZE_DEPLOY = NOT YET OCCURRED`; it was correct when written and is not rewritten. This
  record supersedes it on this one point only, from 2026-10-09.
- **Documentation and governance only.** This acceptance authorizes nothing further. Record 1, the acceptance
  envelope, HELD, signer start, authority activation, First Memory and PROD stay **NOT AUTHORIZED**.
  `FRESHNESS=UNKNOWN`.
- **No live mutation.** Every evidence read was read-only. Writing this record contacted no live system. The
  evidence stays in the owner's local evidence directory, sealed as stated in §7.

```text
deploy EQUAL != owner-accepted != this record merged != the next deploy EQUAL
running target accepted for W9_5 != new global baseline;  W9-verified phase != phase argument
witness genesis committed != record 1 != Registry V1 effective != authority active
```

## 1. Identities

| Item | Value |
| --- | --- |
| control | `2532176d5faeff0d9b1fe73bd193297d591fee2e` (merge of PR #174, the Package B completion record, 2026-10-09T05:28:41Z; reviewed head `c15005cdb5d580a0c729efac3d337b69b544564e`) |
| source validation | `37888756220` (`push`), success |
| `FIRST_POST_PACKAGE_B_FREEZE_DEPLOY_RUN` | `37888892605`, "Deploy LILITH Core API to DEV", `workflow_run`, branch `main`, success, attempt 1, 2026-10-09T05:30:24Z–05:35:56Z |
| mode / base | `DEPLOY_REQUIRED`; base `050e7c5c4c6238eee09eb67b094348127d2953c6` |
| previous DEV deploy | `37829794035` (`050e7c5`, the Package B control preservation deploy, 2026-10-08T19:09Z); none in between |
| deploy log | 1853 lines, SHA-256 `d124395b05e5a577332fdd4de3dd10cb69ad1fb0975666165ded113fb673ded7` |
| operator | `services/owner-memory-control/tools/mb9_operator.py`, SHA-256 `066fc8213b40c392e3e2bfd609da4a7f2a4e0b6f05da011daee9add3caf13973` (`pins` = `MB9_TOOL_PINS_EXACT` at the control, the same 17 pins as Package B sequence 3) |
| DR-5 target tool | `mb9_dr5_target.py` (pinned by the operator); the comparison is `mb9_operator.py dr5 <repo> W9_5_GENESIS_COMMITTED_EXACT <deploy-log>` (Package B record §12) |

## 2. The first post-Package-B-freeze deploy

```text
FIRST_POST_PACKAGE_B_FREEZE_DEPLOY = YES (37888892605)
PREVIOUS_DEV_DEPLOY = 37829794035
```

- The Package B freeze ended with the owner's B5 acceptance. No deploy ran between `37829794035` and `37888892605`.
- The run's own log names `MODE=DEPLOY_REQUIRED BASE_SHA=050e7c5c… CANDIDATE_SHA=2532176d…`; the base is the commit
  that `37829794035` deployed.
- At the start and at the end of the check no workflow run was queued, in progress, waiting, pending or requested,
  and `origin/main` was the control.
- The route is the canonical one (Package B record §12; Package B completion record §10). No historical PASS was
  replayed.

## 3. Phase gate (W9-verified, read-only)

The operator's read-only `host <repo> <workdir> <evidence> POST9B` ran at 2026-10-09T05:39:53Z:
**`MB9_HOST_POST9B_PASS`**, all 10 codes 0, readiness exact, `/tmp` residue `[]`; the M-B6, W8 and W9 verifier
bundles travelled over the R-B5 direct-plink route with empty stderr. The read-only `health` returned
`MB9_HEALTH_EXACT`.

- Custody, readiness, installer status, broker preservation, W5, M-B6, W8 and W9 output is byte-identical to the
  accepted Package B POST9B read. Only clock fields differ (the uptime advance equals the elapsed time). The boot id
  is unchanged and `REBOOT_REQUIRED=absent`.
- **W9 phase: `W9_5_GENESIS_COMMITTED_EXACT`.** Committed genesis digest
  `ac892dc2b14ca7db108400258abfcf2320ff498f2a674058058e16a8a6fb65e4` (fields equal to the candidate); `chain/1.json`
  and `witness.json` SHA-256 `252c32204bebf3fa1ca0981d8791115e2abb6cd8ddb0925285c64213317cfb99`; store `CONSISTENT`;
  all six genesis checks true; no failures. **The witness genesis is unchanged.**
- **The accepted incarnation:** InvocationID `5136ea7af2544450b9370fa412786c98`, MainPID `143946`, NRestarts 0.
- **Witness health:** `CONSISTENT`.
- **Registry and authority:** `registryEffective = false`, `authorityActive = false`, `authorityGranted = false`;
  the deploy log shows `ACTIVATION=NOT_ACCEPTED reason=GRANT_ABSENT`.
- **Signer:** units inactive; its runtime paths absent.
- **Record 1:** absent. Replica A of the owner register verified with 0 records and an unchanged manifest; the host
  cannot observe record 1.

## 4. DR-5 comparison

Fresh, from run `37888892605`'s own log:

| Set | Lines | SHA-256 | Counts |
| --- | --- | --- | --- |
| full result set | 192 | `593c90e1778b0e90326cdf96314b328948c00b2207960d27be2b41874d05ff65` | 167 `DENIED`, 0 `ALLOWED`, 0 `FAIL`, 1 `DEFERRED_UNTIL_OBJECT_EXISTS`, 6 `UNOBSERVABLE_BY_DESIGN` |
| DR-5 block | 153 | `ace51f27ac17a2d719ec19da582d09e21f0c7fb4be7b6ec81e1dd53cb369fd5a` | 139 `DENIED`, 0 `ALLOWED` |
| pre-deploy block | 29 | `f50870420c10149914b8d2a02116708ec89ea5a8f746a847fbe88df058f54cae` | 28 `DENIED` |

`PR1_AUTHORITY_BOUNDARY maturity=P1A-9`, `AUTHORITY_BOUNDARY_PROOF=PASS maturity=L1c.3` and
`ACTIVATION=NOT_ACCEPTED reason=GRANT_ABSENT` were all present.

**Comparison.** `mb9_operator.py dr5 <repo> W9_5_GENESIS_COMMITTED_EXACT <log>` returned **`EQUAL`**, target
`WITNESS_RUNNING`, with `unequal = []`, `allowed = 0` and `fail = 0`.

```text
RUNNING_WITNESS_DR5_COMPARISON = EQUAL
NEW_GLOBAL_DR5_BASELINE = NONE
```

## 5. What is accepted

- The deploy: `FIRST_POST_PACKAGE_B_FREEZE_DEPLOY = EQUAL / OWNER-ACCEPTED`.
- The derived running-witness target (Package B record §12; until now `PROPOSED`) is accepted **only** as the
  phase-bound comparison target for `W9_5_GENESIS_COMMITTED_EXACT`
  (`PHASE_BOUND_DR5_BASELINE_WITH_DERIVED_DELTA`). It is not a new global baseline. The stopped-witness target
  (`7f70aa3b…`) stays PROPOSED / NOT ACCEPTED. The accepted post-M-B6 baseline (`3640ca01…`) is unchanged and
  remains the target for `W9_0_PRE_WITNESS` only.

## 6. Owner acceptance (verbatim)

Owner acceptance text SHA-256 (the text plus one terminal LF): `ff9ecac4dc8a6f1d87fdb74620530a9eea04fd29446d255f462ee52a948ab353`.

> accept deployment run 37888892605 (“Deploy LILITH Core API to DEV”, workflow_run, success) as the first DEV
> deployment after the Package B deployment freeze ended, for DEV_SYNTHETIC. It deployed commit
> 2532176d5faeff0d9b1fe73bd193297d591fee2e, the merge of PR rpahasara/lilith-os#174 (Package B completion record,
> reviewed head c15005cdb5d580a0c729efac3d337b69b544564e), in MODE=DEPLOY_REQUIRED from base
> 050e7c5c4c6238eee09eb67b094348127d2953c6, after repository validation run 37888756220 succeeded, and it is the only
> deployment since 37829794035. At this commit the Package B operator
> services/owner-memory-control/tools/mb9_operator.py has SHA-256
> 066fc8213b40c392e3e2bfd609da4a7f2a4e0b6f05da011daee9add3caf13973 and all Package B tool pins are exact. The host
> phase, independently verified by the W9 verifier at this commit, is W9_5_GENESIS_COMMITTED_EXACT: the committed
> witness genesis digest remains ac892dc2b14ca7db108400258abfcf2320ff498f2a674058058e16a8a6fb65e4 (= the owner pin =
> the Package A candidate), chain/1.json and witness.json remain SHA-256
> 252c32204bebf3fa1ca0981d8791115e2abb6cd8ddb0925285c64213317cfb99, the store is CONSISTENT, and the witness is the
> accepted incarnation InvocationID 5136ea7af2544450b9370fa412786c98, MainPID 143946, NRestarts 0. Witness health is
> CONSISTENT. The boot id is unchanged and REBOOT_REQUIRED is absent. The canonical mb9_operator.py dr5 comparison for
> W9_5_GENESIS_COMMITTED_EXACT returned EQUAL to the derived running-witness target WITNESS_RUNNING with no unequal
> fields, allowed=0 and fail=0. The full result set is 192 lines with SHA-256
> 593c90e1778b0e90326cdf96314b328948c00b2207960d27be2b41874d05ff65: 167 DENIED, 0 ALLOWED, 0 FAIL, 1
> DEFERRED_UNTIL_OBJECT_EXISTS and 6 UNOBSERVABLE_BY_DESIGN. The DR-5 block is 153 lines with SHA-256
> ace51f27ac17a2d719ec19da582d09e21f0c7fb4be7b6ec81e1dd53cb369fd5a and 139 DENIED. The pre-deploy block is 29 lines
> with SHA-256 f50870420c10149914b8d2a02116708ec89ea5a8f746a847fbe88df058f54cae and 28 DENIED. Therefore
> FIRST_POST_PACKAGE_B_FREEZE_DEPLOY = EQUAL and is ACCEPTED, and the derived running-witness DR-5 target is accepted
> as the phase-bound comparison target for W9_5_GENESIS_COMMITTED_EXACT; it is not a new global baseline.
> REGISTRY_EFFECTIVE remains NO. AUTHORITY_ACTIVE remains NO. authorityGranted remains false and GRANT_ABSENT remains
> true. The signer remains inactive and Record 1 remains absent. This acceptance authorizes nothing further: it does
> not authorize Record 1, the acceptance envelope, HELD, signer start, authority activation, First Memory or PROD, and
> it does not authorize any further merge or deployment record.

The text is preserved exactly as issued. Against the rendered draft (`528da7f08b89ab7ba241f5b61146c97f6c3fe867087bfc006890045f17d5eae1`)
it differs only in: the leading "I" is absent; "PR #174" reads "PR rpahasara/lilith-os#174" (the same PR); and the
workflow name is in typographic quotes. Every identifier, hash, count and clause is otherwise identical. The owner
separately authorized creating this record PR (not its merge).

## 7. Evidence seal

- Final evidence seal (`SHA256SUMS`, 58 entries, every evidence file except the checkout copy and the seal files):
  `4582edfd348a25f6d49119e54b6228936556f2e0e0d00a330cfcaf52af1cf453`. It covers the verbatim acceptance file.
- The prior seal (taken before the acceptance was recorded) is preserved byte-identically beside it as
  `SHA256SUMS.seal-1-95d13af5`: `95d13af50409c2a88a64f6951a07f1278a0d94bd762907f210c37d2024728677` (56 entries).

## 8. Ordering after this acceptance (none done)

1. this record PR, reviewed;
2. a separate owner merge authorization;
3. its merge-triggered DEV deploy must again succeed, a fresh read-only W9 read must establish
   `W9_5_GENESIS_COMMITTED_EXACT`, and `mb9_operator.py dr5` must compare `EQUAL` to the accepted running-witness
   phase-bound target;
4. a separate owner acceptance of that deploy.

```text
FIRST_POSTB_DEPLOY_RECORD_MERGE = NOT AUTHORIZED
NEXT_DEPLOY = NOT YET OCCURRED; NOT AUTHORIZED
```

## 9. Boundaries

| Fact | State |
| --- | --- |
| Package B | COMPLETED / OWNER-ACCEPTED (before this deploy) |
| first post-Package-B-freeze deploy | EQUAL / OWNER-ACCEPTED (`37888892605`) |
| running-witness DR-5 target | ACCEPTED for `W9_5_GENESIS_COMMITTED_EXACT` only; not a global baseline |
| host phase | `W9_5_GENESIS_COMMITTED_EXACT` |
| witness genesis | unchanged (`ac892dc2…`; `chain/1.json` `252c3220…`) |
| `REGISTRY_EFFECTIVE` | **NO** |
| `AUTHORITY_ACTIVE` | **NO** |
| `authorityGranted` | false |
| `GRANT_ABSENT` | TRUE |
| signer | **INACTIVE** |
| record 1 | **ABSENT** |
| acceptance envelope / HELD | **NOT AUTHORIZED** |
| authority activation | **NOT AUTHORIZED** |
| First Memory | **NOT AUTHORIZED** |
| PROD | **NOT AUTHORIZED** |

**First Memory boundary.** Tooling must not infer, choose, draft or write LILITH's First Memory merely because later
bootstrap stages become technically ready. If the system eventually reaches `FIRST_MEMORY_READY`, the process
**STOPS** there. Owner discussion is required before any First Memory content is selected or written.

## 10. State

```text
FIRST_POST_PACKAGE_B_FREEZE_DEPLOY = EQUAL / OWNER-ACCEPTED
FIRST_POST_PACKAGE_B_FREEZE_DEPLOY_RUN = 37888892605
FIRST_POST_PACKAGE_B_FREEZE_DEPLOY_CONTROL = 2532176d5faeff0d9b1fe73bd193297d591fee2e
SOURCE_VALIDATION_RUN = 37888756220
PREVIOUS_DEV_DEPLOY = 37829794035
PACKAGE_B = COMPLETED / OWNER-ACCEPTED
W9_PHASE = W9_5_GENESIS_COMMITTED_EXACT
RUNNING_WITNESS_DR5_COMPARISON = EQUAL
RUNNING_WITNESS_DR5_TARGET = ACCEPTED (PHASE-BOUND: W9_5_GENESIS_COMMITTED_EXACT ONLY)
NEW_GLOBAL_DR5_BASELINE = NONE
RUNNING_DR5_FULL_SHA256 = 593c90e1778b0e90326cdf96314b328948c00b2207960d27be2b41874d05ff65
RUNNING_DR5_BLOCK_SHA256 = ace51f27ac17a2d719ec19da582d09e21f0c7fb4be7b6ec81e1dd53cb369fd5a
RUNNING_DR5_PREDEPLOY_SHA256 = f50870420c10149914b8d2a02116708ec89ea5a8f746a847fbe88df058f54cae
WITNESS_GENESIS_DIGEST = ac892dc2b14ca7db108400258abfcf2320ff498f2a674058058e16a8a6fb65e4
CHAIN_1_SHA256 = 252c32204bebf3fa1ca0981d8791115e2abb6cd8ddb0925285c64213317cfb99
WITNESS_INVOCATION_ID = 5136ea7af2544450b9370fa412786c98
WITNESS_MAIN_PID = 143946
WITNESS_NRESTARTS = 0
WITNESS_HEALTH = CONSISTENT
OWNER_ACCEPTANCE_TEXT_SHA256 = ff9ecac4dc8a6f1d87fdb74620530a9eea04fd29446d255f462ee52a948ab353
EVIDENCE_SEAL = 4582edfd348a25f6d49119e54b6228936556f2e0e0d00a330cfcaf52af1cf453
PRIOR_SEAL_PRESERVED = 95d13af50409c2a88a64f6951a07f1278a0d94bd762907f210c37d2024728677
REGISTRY_EFFECTIVE = NO
AUTHORITY_ACTIVE = NO
authorityGranted = false
GRANT_ABSENT = TRUE
SIGNER = INACTIVE
RECORD 1 = ABSENT
ACCEPTANCE_ENVELOPE = NOT AUTHORIZED
HELD = NOT AUTHORIZED
AUTHORITY ACTIVATION = NOT AUTHORIZED
FIRST_POSTB_DEPLOY_RECORD_MERGE = NOT AUTHORIZED
FIRST_MEMORY = NOT AUTHORIZED
PROD = NOT AUTHORIZED
FRESHNESS=UNKNOWN
```
