# Slice 15B2b-B1b-3e — E-A18: First Post-Package-A-Freeze DR-5 Preservation (2026-10-08)

Status:

- **OWNER ACCEPTANCE RECORD (APPEND-ONLY).** It records E-A18: the first DEV deployment after the Package A
  deployment freeze ended compared `EQUAL` to the accepted post-M-B6 DR-5 baseline under the W8-verified host phase
  `OWNER_INPUTS_INSTALLED_EXACT`. The owner then accepted it verbatim (§6).
- `E-A18 = COMPLETED / OWNER-ACCEPTED`. `POST_MB6_ACCEPTED_DR5_BASELINE_PRESERVED = YES`. **No new baseline was
  created.**
- **The earlier records are unchanged.** The [Package A completion record](slice-15b2b-b1b3e-mb7-mb8-package-a-completion.md)
  §9 and the [Package B record](slice-15b2b-b1b3e-mb9-witness-genesis-package.md) state `E-A18 = NOT YET PERFORMED`.
  That was correct when they were written, and they are not rewritten. This record supersedes them on this one point
  only, from 2026-10-08.
- **Documentation and governance only.** This record does not open Package B. B1, M-B9a, M-B9b, witness start,
  witness genesis, record 1, signer start, authority activation, First Memory and PROD stay **NOT AUTHORIZED**.
  `FRESHNESS=UNKNOWN`.
- **No live mutation.** Every E-A18 evidence read was read-only. Writing this record contacted no live system. The
  evidence stays in the owner's local evidence directory, sealed as stated in §7.

```text
E-A18 owner-accepted != this record merged != preservation deploy EQUAL != Package B control != B1 != M-B9a authorized
EQUAL != new baseline;  W8-verified phase != phase argument;  E-A18 accepted != Package B open
```

## 1. Identities

| Item | Value |
| --- | --- |
| control | `36b21c90dfe8e5e4243b56f24de503ea0a4f8b91` (merge of PR #170, 2026-10-08T14:18:08Z; source head `39481f2772635c6d3a04af163d9c376231167814`) |
| source validation | `37791336364` (`push`), success |
| `E-A18_DEPLOY_RUN` | `37791575032`, "Deploy LILITH Core API to DEV", `workflow_run`, branch `main`, success, 2026-10-08T14:19:57Z–14:25:31Z |
| mode / base | `DEPLOY_REQUIRED`; base `29c2b824cae187037e4434a1ad7f9466f4eb2ab6` |
| previous DEV deploy | `37741374796` (`29c2b82`, 2026-10-08T07:06Z), before the Package A freeze ended; none in between |
| deploy log | 1841 lines, SHA-256 `b374aefae68a52856faa742b8977e328d7a678b9a038a148f2c1f2863fb48554` |
| operator | `services/owner-memory-control/tools/mb7_mb8_operator.py`, SHA-256 `9f13411f363dc956795ce4832d1948e7e6a9a7f7c8d1057291de852e9e2a20cd` (`pins` = `MB7_MB8_TOOL_PINS_EXACT` at the control) |
| DR-5 extractor | `mb6_dr5_target.py`, SHA-256 `9978e3a791a829d6beace81ca0e4c6db9b1c154fbc56091f6312385d02632656` |
| W8 verifier | `mb8_owner_input_verifier.py`, SHA-256 `b190c255c88a1bdca0ff8d9cb050443ad24d42f269d49947d47b87775351e341` |

## 2. The first post-Package-A-freeze deploy

```text
FIRST_POST_PACKAGE_A_FREEZE_DEPLOY = YES (37791575032)
PREVIOUS_DEV_DEPLOY = 37741374796
```

- The Package A freeze ended with the owner's §16 acceptance (Package A completion record §6). No deploy ran between
  `37741374796` and `37791575032`.
- The run's own log names `MODE=DEPLOY_REQUIRED BASE_SHA=29c2b824… CANDIDATE_SHA=36b21c90…`; the base is the commit
  that `37741374796` deployed.
- At the check no workflow run was queued, in progress, waiting, pending or requested, and `origin/main` was the
  control.
- The route is the canonical one: package §12 row E-A18, `dr5 <repo> OWNER_INPUTS_INSTALLED_EXACT <log>` (package
  §7, OD-4). No new procedure was used, and no historical PASS was replayed.

## 3. Phase gate (W8-verified, read-only)

The operator's read-only `host <repo> <workdir> <evidence> POST` ran at 2026-10-08T14:36:18Z–14:48:59Z:
**`MB7_MB8_HOST_POST_PASS`**, all 9 codes 0, readiness exact, `/tmp` residue `[]`.

- Custody, readiness, installer status (P1B-8), broker preservation, W5, M-B6 and W8 output is byte-identical to the
  accepted E-A17 post-cleanup reads. The identity and observer reads differ only in clock fields. The boot id is
  unchanged and `REBOOT_REQUIRED=absent`.
- **W8 phase: `OWNER_INPUTS_INSTALLED_EXACT`.** `genesis-pin.json` SHA-256
  `357477369ab53790245b42cbecbe2a630110477bede5b599696699e4f5c3a590` and `authorization-register.json` SHA-256
  `8d5ab87564d0e531b7d1467c18b6d106f2a468d5d155ce9f2acb64758df85575`, both `root:root 0644`, one link; candidate
  `ac892dc2…65e4` on host equals the owner candidate.
- **Ledger:** exact, sequence 1, head `19bf9091a96cdc2378a68508feb0c119721f7fcef7b9c3a480a6cd6b72fa1630`.
- **Registry and authority:** `registryEffective = false`, `authorityActive = false`, `authorityGranted = false`;
  `ACTIVATION=NOT_ACCEPTED reason=GRANT_ABSENT`.
- **No later state:** the signer and witness services and sockets are inactive; `/var/lib/lilith-recovery-witness`
  is absent; every W8 later-state path is absent; `witnessGenesisPresent = false`; the hold store is empty. There is
  no record 1 and no M-B9a or M-B9b state.

## 4. DR-5 comparison

Fresh, from run `37791575032`'s own log:

| Set | Lines | SHA-256 | Counts |
| --- | --- | --- | --- |
| full result set | 188 | `3640ca0136e5740835f7047480e472e737b2556c14b48db66ff1c1983350f494` | 161 `DENIED`, 0 `ALLOWED`, 0 `FAIL`, 3 `DEFERRED_UNTIL_OBJECT_EXISTS`, 6 `UNOBSERVABLE_BY_DESIGN` |
| DR-5 block | 149 | `d05aa017672c370b49518297c98709c0381765b9c98a7e29ac9a1edf094e7801` | 133 `DENIED`, 0 `ALLOWED` |
| pre-deploy block | 29 | `f50870420c10149914b8d2a02116708ec89ea5a8f746a847fbe88df058f54cae` | 28 `DENIED` |

`PR1_AUTHORITY_BOUNDARY maturity=P1A-9`, `AUTHORITY_BOUNDARY_PROOF=PASS maturity=L1c.3` and
`ACTIVATION=NOT_ACCEPTED reason=GRANT_ABSENT` were all present.

**Comparison.** `mb7_mb8_operator.py dr5 <repo> OWNER_INPUTS_INSTALLED_EXACT <log>` returned **`EQUAL`**, target
`POST_MB6_ACCEPTED_BASELINE_UNCHANGED_BY_PACKAGE_A`, with `unequal = []`, `allowed = 0` and `fail = 0`.

```text
POST_MB6_DR5_COMPARISON = EQUAL
NEW_DR5_BASELINE = NONE
```

## 5. Observations (none is drift)

- The word `ALLOWED` occurs twice in the log, both in the printed source of the `deny()` helper; the same two occur
  in the `37741374796` log. No result line is `ALLOWED`.
- The W8 `routing` field reads `STOP_OWNER_ADJUDICATION`: the known `MB8_ROUTING_FIELD_ANOMALY =
  REPORTING_DEFECT_ONLY` (Package A completion record §10), byte-identical to E-A17. It stays an open future
  remediation and is not fixed here.
- The M-B6 verifier reports `OUT_OF_SCOPE_LATER_STATE`, as expected after M-B8 (package §7), byte-identical to E-A17.
- Two registry values are distinct, not in conflict: `46b0bfc5…` is the owner-accepted installable-representation
  file pin; `fa662721…14fc` is the Registry V1 digest the host verifies (W8 `trustRegistryExact`,
  `registryVerifiesOnHost`).

## 6. Owner acceptance (verbatim)

Owner acceptance text SHA-256 (the text plus one terminal LF): `df80425edcc3d3f29b527345f227f944667f9bddd7b0c71d48207453daa4a4c2`.

> I accept E-A18 for DEV_SYNTHETIC: the first DEV deployment after the Package A deployment freeze ended preserved
> the accepted post-M-B6 DR-5 baseline. Deployment run 37791575032 ("Deploy LILITH Core API to DEV", workflow_run,
> success) deployed control 36b21c90dfe8e5e4243b56f24de503ea0a4f8b91 (PR #170 merge) in MODE=DEPLOY_REQUIRED from
> base 29c2b824cae187037e4434a1ad7f9466f4eb2ab6. It is the first deployment after 37741374796. The host phase,
> independently verified by the W8 verifier at this control, is OWNER_INPUTS_INSTALLED_EXACT: the installed genesis
> pin has SHA-256 357477369ab53790245b42cbecbe2a630110477bede5b599696699e4f5c3a590 and the installed authorization
> register has SHA-256 8d5ab87564d0e531b7d1467c18b6d106f2a468d5d155ce9f2acb64758df85575. The ledger remains sequence
> 1 with head 19bf9091a96cdc2378a68508feb0c119721f7fcef7b9c3a480a6cd6b72fa1630. The canonical mb7_mb8_operator.py
> dr5 comparison for OWNER_INPUTS_INSTALLED_EXACT returned EQUAL with no unequal fields, allowed=0 and fail=0. The
> full result set is 188 lines with SHA-256 3640ca0136e5740835f7047480e472e737b2556c14b48db66ff1c1983350f494: 161
> DENIED, 0 ALLOWED, 0 FAIL, 3 DEFERRED_UNTIL_OBJECT_EXISTS and 6 UNOBSERVABLE_BY_DESIGN. The DR-5 block is 149
> lines with SHA-256 d05aa017672c370b49518297c98709c0381765b9c98a7e29ac9a1edf094e7801 and 133 DENIED. The pre-deploy
> block is 29 lines with SHA-256 f50870420c10149914b8d2a02116708ec89ea5a8f746a847fbe88df058f54cae and 28 DENIED. No
> new baseline is created. REGISTRY_EFFECTIVE remains NO. AUTHORITY_ACTIVE remains NO. authorityGranted remains
> false and GRANT_ABSENT remains true. The signer and witness remain inactive, /var/lib/lilith-recovery-witness is
> absent, witness genesis is not committed and Record 1 is absent. No Package B state exists. Therefore E-A18 =
> COMPLETED / OWNER-ACCEPTED and POST_MB6_ACCEPTED_DR5_BASELINE_PRESERVED = YES. This acceptance does not open
> Package B and does not authorize B1, M-B9a, M-B9b, witness start, witness genesis, Record 1, signer start,
> authority activation, First Memory or PROD. It does not authorize creating or merging the E-A18 record PR; that
> needs its own owner authorization.

The owner separately authorized creating this record PR (not its merge).

## 7. Evidence seal

- Final E-A18 evidence seal (`SHA256SUMS`, 43 entries, every evidence file except the checkout copy and the seal
  files): `997fd9049ba1dac7ab0676c9c7638efca854dada61483207dcfd8b4ca8c18e9b`. It covers the verbatim acceptance file.
- The prior seal (taken before the acceptance was recorded) is preserved byte-identically beside it:
  `93921edaafff3f2f32dec143d387e612011c943508d37c9a45e1b49de949baf2`.

## 8. Ordering after E-A18 (Package B record §13; none done)

1. this E-A18 record PR, reviewed;
2. a separate owner merge authorization;
3. its merge-triggered DEV deploy is a **preservation deploy**: it must succeed and compare `EQUAL` under the
   W8-verified `OWNER_INPUTS_INSTALLED_EXACT`;
4. a separate owner acceptance of that preservation result;
5. only then may that merge commit become the Package B live control;
6. B1 opens Package B (a separate owner act).

```text
EA18_RECORD_MERGE = NOT AUTHORIZED
EA18_RECORD_PRESERVATION_DEPLOY = NOT YET OCCURRED
PACKAGE_B_CONTROL = NOT SELECTED
```

## 9. Boundaries

| Fact | State |
| --- | --- |
| E-A18 | COMPLETED / OWNER-ACCEPTED |
| post-M-B6 accepted DR-5 baseline | PRESERVED (`3640ca01…`); no new baseline |
| host phase | `OWNER_INPUTS_INSTALLED_EXACT` |
| `REGISTRY_EFFECTIVE` | **NO** |
| `AUTHORITY_ACTIVE` | **NO** |
| `GRANT_ABSENT` | TRUE |
| signer / witness | INACTIVE |
| witness genesis | **NOT COMMITTED** |
| record 1 | **ABSENT** |
| Package B | **NOT OPEN** |
| B1 / M-B9a / M-B9b | **NOT AUTHORIZED** |
| First Memory | **NOT AUTHORIZED** |
| authority activation | **NOT AUTHORIZED** |
| PROD | **NOT AUTHORIZED** |

**First Memory boundary.** Tooling must not infer, choose, draft or write LILITH's First Memory merely because later
bootstrap stages become technically ready. If the system eventually reaches `FIRST_MEMORY_READY`, the process
**STOPS** there. Owner discussion is required before any First Memory content is selected or written.

## 10. State

```text
E-A18 = COMPLETED / OWNER-ACCEPTED
E-A18_DEPLOY_RUN = 37791575032
E-A18_CONTROL = 36b21c90dfe8e5e4243b56f24de503ea0a4f8b91
E-A18_PHASE = OWNER_INPUTS_INSTALLED_EXACT
FIRST_POST_PACKAGE_A_FREEZE_DEPLOY = YES
PREVIOUS_DEV_DEPLOY = 37741374796
POST_MB6_DR5_COMPARISON = EQUAL
POST_MB6_ACCEPTED_DR5_BASELINE_PRESERVED = YES
NEW_DR5_BASELINE = NONE
DR5_FULL_SHA256 = 3640ca0136e5740835f7047480e472e737b2556c14b48db66ff1c1983350f494
DR5_BLOCK_SHA256 = d05aa017672c370b49518297c98709c0381765b9c98a7e29ac9a1edf094e7801
DR5_PREDEPLOY_SHA256 = f50870420c10149914b8d2a02116708ec89ea5a8f746a847fbe88df058f54cae
OWNER_ACCEPTANCE_TEXT_SHA256 = df80425edcc3d3f29b527345f227f944667f9bddd7b0c71d48207453daa4a4c2
EA18_EVIDENCE_SEAL = 997fd9049ba1dac7ab0676c9c7638efca854dada61483207dcfd8b4ca8c18e9b
EA18_PRIOR_SEAL_PRESERVED = 93921edaafff3f2f32dec143d387e612011c943508d37c9a45e1b49de949baf2
MB8_ROUTING_FIELD_ANOMALY = REPORTING_DEFECT_ONLY (OPEN FUTURE REMEDIATION)
LEDGER SEQUENCE = 1
LEDGER HEAD = 19bf9091a96cdc2378a68508feb0c119721f7fcef7b9c3a480a6cd6b72fa1630
REGISTRY_EFFECTIVE = NO
AUTHORITY_ACTIVE = NO
GRANT_ABSENT = TRUE
SIGNER = INACTIVE
WITNESS = INACTIVE
WITNESS_GENESIS = NOT COMMITTED
RECORD 1 = ABSENT
EA18_RECORD_MERGE = NOT AUTHORIZED
EA18_RECORD_PRESERVATION_DEPLOY = NOT YET OCCURRED
PACKAGE_B_CONTROL = NOT SELECTED
PACKAGE_B = NOT OPEN
B1 = NOT AUTHORIZED
M-B9a = NOT AUTHORIZED
M-B9b = NOT AUTHORIZED
FIRST_MEMORY = NOT AUTHORIZED
AUTHORITY ACTIVATION = NOT AUTHORIZED
PROD = NOT AUTHORIZED
FRESHNESS=UNKNOWN
```
