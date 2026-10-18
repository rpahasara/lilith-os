# Slice 15B2b-B1b-3e M-B12 — OD-M12-11 and the One-Member Judge Transition Contract (`UPGRADE_E22_JUDGE_DEV_SYNTHETIC`)

Status: OD-M12-11 PROPOSED (decision only) until the owner confirms it by merging this record; transition contract
PROPOSED, REPOSITORY ONLY
Environment: DEV_SYNTHETIC
Date: 2026-10-18
Base: main `6a06ed3bacb2cfced5427d8e3e0795a2f802bbef` (PR #215, OD-M12-10 merged)

Nothing in this record builds, attests, stages, selects or retires a release, stops or starts a unit, loads K-ACT or
K-WIT, changes custody, HELD or the ledger, writes a replica or First Memory, or activates authority.

## 1. Where this stands

- PR #215 merged the OD-M12-10 E-22 adjudication (record `slice-15b2b-b1b3e-mb12-prb2-proof-producers.md` §17). The
  repository judge `pr1_acceptance.py` is `d3df4cfc…`. It is not built or installed. DEV runs the E-19 release
  `ba943e1`, whose judge is `0d2e6cca…`.
- Deploy `39117829501` (main `6a06ed3`) compared W11 DR-5 `W11_1_SIGNER_STARTED_EXACT` **EQUAL** (194 / 155 / 29,
  fail 0, old-release lines 0). The deployer-visible release set is exactly `releases/ba943e1…`. Evidence
  `lilith-mb11-pr215-dr5-6a06ed3`, `SHA256SUMS` `4cf04454a3fd9507400672e7c625dff083a0b2b32c38a5d08bb04c8ceb46d02c`. DR-5
  does not observe the contents of the release tree.
- Repository: the release payload sources differ from `ba943e1` only in `lilith_owner_memory/pr1_acceptance.py`.
  `lilith_authority_root/verifier.py` is unchanged.

## 2. OD-M12-11: transition-time credential loads

**Owner decision (2026-10-18):** "I accept OD-M12-11 as recommended (decision only). Prepare the one-member transition
contract slice for review; no build, swap or live step."

Disclosure: the written recommendation did not reach the owner before that answer. It is stated in full here for the
first time. **Status: PROPOSED, decision only, until the owner confirms it by merging this record.** The merge
confirms the decision only; it authorizes no build, stage, select, restart, credential load or custody change.

The rule (`e22_judge_upgrade.OD_M12_11_RULE`):

1. Each transition-time private-material event is its own event, never covered by OD-M12-10. There are two: the
   K-WIT load of the replacement witness (V5) and the K-ACT load of the replacement signer (V6). Each records its own
   window (operator markers) and retains its transcript.
2. The post-transition `journal` and `attribute` reads are taken after the last of those loads, in the same boot as
   its window. They must show exactly the historical 12 attributed matches and no new marker. The OD-M12-10 admission
   (§17.3 of the PR-B2 record) already refuses anything else.
3. The two loads do **not** become rows of the E-22 `CEREMONIES` table. That keeps the OD-M12-10 adjudication valid
   without re-issuing it: its producer pin and approved body stay the same.
4. After V6 the K-ACT load count is **2**, counted from the journal (never inferred from a start command).

## 3. The contract (`services/owner-memory-control/tools/e22_judge_upgrade.py`)

It reuses the accepted E-19 contract (`e19_p1b10_upgrade`) and changes nothing in it:

| Item | Value |
| --- | --- |
| mode | `UPGRADE_E22_JUDGE_DEV_SYNTHETIC`, `PROPOSED_NOT_ACCEPTED` |
| OLD (installed) | `E19.NEW_RELEASE` `ba943e1…`, manifest `E19.NEW_MANIFEST_SHA256` `b8393015…` |
| NEW | `None` until a merged owner record pins an independently attested build of the merged source (E-19 `new-release-pin` pattern) |
| payload delta | exactly `lilith_owner_memory/pr1_acceptance.py`: `0d2e6ccabf916425a1dfa7dc587bfcb3d7a232eb6c52c5cd938d573199715cff` → `d3df4cfca975b31cbe526805d6573e7d4760ef376ad02f3cb8e0ac7cece4049b`; units and CLIs byte-identical |
| exact edits | `E22_EDITS` (5 anchored edits); `reverse_e22` proves the repository judge is those edits over the installed bytes and nothing else |
| build-time gate | `check_payload(payloads, installed_pins)`: a candidate NEW payload equals the installed module map except that one member, with exactly the pinned bytes |

**Difference from E-19:** E-19 ran while the signer was dark, and its contract halts on a running signer. Now both the
signer (`lilith_authority_dev.recovery`) and the witness (`lilith_recovery_witness.core`) import the judge and run from
`current`. Neither may run across a selector change or from a retired tree:

| Phase | Releases | `current` | Signer | Witness |
| --- | --- | --- | --- | --- |
| V0 W11 exact | OLD | OLD | OLD (accepted W11 / POST11) | OLD |
| V1 NEW staged | OLD, NEW | OLD | OLD | OLD |
| V2 signer stopped | OLD, NEW | OLD | stopped | OLD |
| V3 witness stopped | OLD, NEW | OLD | stopped | stopped |
| V4 NEW selected | OLD, NEW | NEW | stopped | stopped |
| V5 witness running | OLD, NEW | NEW | stopped | NEW (one K-WIT load) |
| V6 signer running | OLD, NEW | NEW | NEW (one K-ACT load, the second) | NEW |
| V7 OLD retired | NEW | NEW | NEW | NEW |

The stop commands name exactly the reviewed units (`pr1_acceptance.SIGNER_UNITS`, `WITNESS_UNITS`). The restart
boundary drop-ins (signer: M-B11; witness: E-19) stay required in every phase.

## 4. Not in this slice (each needs its own owner authorization)

1. A release build of the merged tree, its independent attestation, and an owner pin record setting `NEW_RELEASE` /
   `NEW_MANIFEST_SHA256` (`check_payload` must pass on the built payload).
2. The live tooling for V1 … V7. This reuses the E-19 stage / select / retire installer forms and the E-19 observer
   pattern, extended with the signer stop / start. That needs a reviewed source slice; the accepted E-19 tools are
   not edited.
3. The re-pin cascade from the built release: readiness `DEV_PINS`, PR-3 `DEV_EXPECTED` and E-21 re-confirmation, the
   W11 DR-5 targets, and tool and operator pins.
4. The owner-authorized V1 … V7 run, W11 / POST11 acceptance of the replacement signer, DR-5 EQUAL, the OD-M12-11
   reads, then the M-B12 recollection and the M-B13 acceptance.

Retention note: the OD-M12-10 admission needs boot `24d1771d` (and `eea461c3` for coverage) still retained at the
post-transition read. Journald rotation removes the oldest boot first, so delay works against this path.

```text
OD-M12-11 = PROPOSED (DECISION ONLY) UNTIL CONFIRMED BY OWNER MERGE;  UPGRADE_E22_JUDGE_DEV_SYNTHETIC = PROPOSED, SOURCE ONLY
NEW RELEASE = NOT BUILT / NOT ATTESTED / NOT PINNED;  BUILD / STAGE / SELECT / RESTART / KEY LOAD = NOT AUTHORIZED
E-22 = BLOCKED;  M-B12 = NOT PASSED;  CUSTODY = HELD;  K-ACT LOAD COUNT = 1
```

## 5. Addendum (2026-10-18): transition tooling slice and owner execution plan (source only)

**Evidence.** Deploy `39123673552` (main `76653d5`, PR #217) compared W11 DR-5 `W11_1_SIGNER_STARTED_EXACT` **EQUAL**
(194 / 155 / 29, fail 0, old-release lines 0). The only authority release the deployer sees is `releases/ba943e1…`.
Evidence `lilith-mb11-pr217-dr5-76653d5`, `SHA256SUMS` `9c66a8933e4e9d2ab58923b882125200f17d57c5be4d0bf335c5039362d990fe`.

**Added (no build, no DEV contact, no unit or credential action):**

| Piece | What it does | Reuses |
| --- | --- | --- |
| `e22_judge_upgrade.check_inspection_delta` / `check-build` | build-time gate: a NEW build inspection against the installed E-19 build inspection (bound to archive `a4ad24e8…`, manifest `b8393015…`, source `ba943e1`). It admits exactly the judge (`0d2e6cca` → `d3df4cfc`, same install mode) and refuses any other payload, file-set, unit, CLI, host-target, dependency, root-tooling, witness-runtime or tar-member change. A local run against the real E-19 inspection binds it as installed and refuses an unchanged payload | the unchanged `attest_authority_dev_build.py` inspection format |
| `ENDING_SIGNER_INCARNATION` / `ENDING_WITNESS_INCARNATION` | `c7ba0fb7…`/84806 (M-B11 start acceptance §2) and `90b28f9d…`/69238 (E-19 completion record) | accepted records |
| `e22_release_stages.py` | root on DEV, each form behind its own go: `e22-status` (read-only: layout state, both units, both working trees, the V-phase or a STOP), `e22-stage` (V0 → V1), `e22-select` (V3 → V4, signer **and** witness stopped), `e22-retire-old` (V6 → V7, both named replacements running from NEW). STOPs: a unit on OLD after select, on a retired tree, transitional, an ending incarnation restarted or a new one on OLD, an inconsistent layout | `e19_release_stages` host reads (unchanged), installer `install_authority_dev.py` (unchanged) |

The stop / start of units stays with the operator and the contract's reviewed commands, as in E-19. The tool never
starts, stops or reloads a unit.

**Still missing before a live swap (one more source-only slice):** the laptop operator for V0 … V7. That means the
rendered go texts, the `O_EXCL` go markers and the pinned remote route (`e19_operator` / `mb10_operator` pattern),
the OD-M12-11 window markers, and the replacement-signer POST and acceptance with K-ACT load count 2. The last reuses
the M-B11 start path and W11 verifier.

### Owner execution plan (nothing below is authorized)

**Authorization 1 — BUILD (local only; no DEV).** After the operator slice merges, pick source commit `S` (that merge):

1. Build twice with the unchanged tool, from clean checkouts of `S` with the pinned wheelhouse:
   `build_authority_dev_release.py --candidate-sha S …` (BUILD_A Windows; BUILD_B WSL `env -i … -I -B`).
2. `attest_authority_dev_build.py inspect` both, then `attest` (must be `REPRODUCED`), then `check`.
3. `e22_judge_upgrade.py check-build <new inspection> <E-19 build-a/inspection-a.json>` must print `PASS`.
4. A repository-only pin PR: `NEW_RELEASE = S`, `NEW_MANIFEST_SHA256`, the attestation record, and the derived DR-5
   targets for the swap phases.

**Authorization 2 — LIVE SWAP (DEV; one owner go per mutation, in order, each consumed once):** V0 read-only status
and observe → STAGE → SIGNER STOP → WITNESS STOP → SELECT → WITNESS START (one K-WIT load) → witness POST and owner
acceptance → SIGNER START (K-ACT load 2) → signer POST and owner acceptance → RETIRE. Then:

- DR-5 EQUAL against the derived post-swap target;
- the OD-M12-11 `journal` and `attribute` reads (same boot, exactly 12 attributed matches);
- the re-pin cascade, the M-B12 recollection and the SECRET_HYGIENE pin only if the OD-M12-10 admission passes;
- M-B13.

```text
TRANSITION TOOLING (GATE + STAGES + STATUS) = SOURCE ONLY;  OPERATOR = NOT YET;  NEW RELEASE = NOT BUILT
BUILD / STAGE / SELECT / RETIRE / UNIT STOP-START / KEY LOAD = NOT AUTHORIZED
E-22 = BLOCKED;  M-B12 = NOT PASSED;  CUSTODY = HELD;  K-ACT LOAD COUNT = 1
```

## 6. Addendum (2026-10-18): the V0 … V7 operator (source only) and the execution instructions

Base: main `db106487b75846674e93770b1472014385dfb763` (PR #218). Nothing below is authorized by this record.

**Added.**

| Piece | What it does | Reuses (unchanged) |
| --- | --- | --- |
| `tools/e22_operator.py` | the laptop operator: `pins`, `bind`, `status`, `v0`, `render`, the seven mutation forms `stage`, `stop-signer`, `stop-witness`, `select`, `start-witness`, `start-signer`, `retire`, the read-only `post-witness` / `post-signer`, the local `accept-witness` / `accept-signer` and `windows` | `mb11_operator.Operator` (E-19 transport: pinned `gcloud compute ssh` route, direct-plink BOOT stdin route, go check, `O_EXCL` marker, records; owner-inputs reader; accepted-start reader; POST11 judgement), the E-19 denial proofs and `denial_result`, the installer, `e19_release_stages`, `e22_release_stages`, the contract |
| `tools/e22_transition_remote.py` | read-only host tail after the M-B11 W11 bundle: `window` (journal tail cursor, boot id, UTC) and `post` (the M-B11 `post` form with the W11 release binding set to the phase's release, plus the journal-counted K-ACT invocations after the M-B11 gate cursor and K-WIT invocations after the V5 window cursor) | `mb11_start_remote.run_form`, `mb11_signer_verifier` (journal parser and reader, `evaluate`) |
| `e22_judge_upgrade.py` (fix) | no longer puts the remote cwd on `sys.path` when run under the mb6 BOOT loader (the operator bundles it to DEV). Same guard as `e19_maintenance_observer` | |

**Rules the operator enforces.**

- Each mutation needs: an exact `render`ed go (verbatim), the latest recorded `status` in exactly the step's pre-phase,
  and a fresh read-only `e22-status` in that pre-phase. Only then is the `O_EXCL` marker written, followed by ONE
  invocation and one read-only post-status. There is no retry, automatic stop, rollback or repair. A consumed or
  tampered go is refused, and so is a host that changed since the go.
- The V-phase is re-judged locally from the retained `e22-status` bytes with the pure `e22_release_stages.phase`.
  Every `VS_*` outcome is a STOP: a unit running from OLD after the select, a unit on a retired tree, a transitional
  unit, a changed ending incarnation, or an inconsistent layout.
- `v0` requires status V0 and the identical M-B11 POST11 document (`judge_observe` against the accepted POST11). The
  journal must show exactly one K-ACT invocation since the M-B11 gate cursor, the ending signer `c7ba0fb7…`.
- **OD-M12-11.** `start-witness` (V5, K-WIT) and `start-signer` (V6, K-ACT) each read a `window` before the marker
  and again after the invocation. Each writes `WINDOW.json`: event, phase, marker, go digest, open and close (cursor,
  boot id, UTC), `sameBoot`, the SHA-256 of every retained transcript file, and `joinsCeremoniesTable: false`. A
  reboot inside the window is a STOP. `windows` prints both windows, the boot and the cursor after which the
  post-transition `journal` / `attribute` reads must be taken.
- `post-witness` (V5) requires: W11 `W11_1S` with the signer stopped after exactly the one M-B11 load; W10_1 on the
  replacement witness (not `90b28f9d…`); exactly one K-WIT invocation in the V5 window (the running one); the three
  denial proofs PASS (P1B-9b, P1B-10, P1B-5); the boundary effective; authority dark.
- `post-signer` (V6) requires:
  - W11 `W11_1` with exactly one load in the V6 window, HEALTH bound to the running replacement (NRestarts 0, not
    `c7ba0fb7…`), the accepted M-B11 key, and the accepted replacement witness;
  - **K-ACT load count 2**, counted from the journal after the M-B11 gate cursor: exactly the invocations
    `[c7ba0fb7…, <replacement>]`, both LOADED. Any other count is a STOP.
- Acceptance (`render ACCEPT_WITNESS|ACCEPT_SIGNER`, then `accept-*` with the owner's verbatim text) needs the latest
  POST to be VERIFIED. The text is bound to that POST record and its window record. `start-signer` needs the witness
  acceptance. `retire` needs both acceptances, and both accepted incarnations must still be the ones running.
- Every DEV form refuses until `J.NEW_RELEASE` / `J.NEW_MANIFEST_SHA256` are pinned (`NEW_RELEASE_NOT_ESTABLISHED`).

Tests: `tests/test_b1b3e_e22_operator.py` (15). They use a synthetic DEV that runs the real E-22 and M-B11 host tails,
the W11 verifier and the V-phase judge. They cover: V0 → V7 with each mutation exactly once in order and K-ACT count
2; out-of-order, replayed or tampered gos and a changed host refused before any marker; the select-across-running
STOP; NEW unpinned; a missing witness acceptance; a reboot inside a window; an extra K-ACT load (count 3) and a
non-exact V0; two K-WIT loads; a failed denial proof; closed remote evidence; tool pins; the BOOT `sys.path` guard.

### Authorization 1: BUILD (owner workstation only; no DEV)

`S` = the merge commit of this slice. All paths are from a clean control checkout.

1. Build twice from clean checkouts of `S` with the pinned wheelhouse, using the unchanged builder:
   `python services/authority-dev/ceremony/build_authority_dev_release.py --candidate-sha S --wheelhouse <wh> --archive release-S.tar.gz --attestation release-S.json`.
   BUILD_A on Windows; BUILD_B on WSL (`env -i … python3 -I -B …`), as for E-19.
2. `attest_authority_dev_build.py inspect --sha S --source-root <checkout> --archive … --stamp … --out inspection-{a,b}.json`,
   then `attest --a … --b … --out attestation.json` (must print `REPRODUCED`), then `check` on both archives.
3. `python services/owner-memory-control/tools/e22_judge_upgrade.py check-build inspection-a.json <E-19 build-a/inspection-a.json>`
   must print `PASS`.
4. One repository-only pin PR:
   - `J.NEW_RELEASE = S` and `J.NEW_MANIFEST_SHA256`;
   - the attestation record;
   - the derived W11 DR-5 targets for the swap phases;
   - re-pins `e22_operator.TOOL_PINS` for the changed contract bytes;
   - if the release-module pins in the readiness inputs move, the re-pinned readiness envelope used by `post-signer`.

### Authorization 2: LIVE SWAP (DEV; one owner go per mutation, in order, each consumed once)

`OP="python services/owner-memory-control/tools/e22_operator.py"`, `R=.` (clean control checkout at the pin merge),
`WD` = a new E-22 workdir, `MB11` = the accepted M-B11 workdir. The owner first copies `release-S.tar.gz` and
`release-S.json` to `/home/<oslogin>/lilith-e22-transfer/` (`gcloud compute scp`, a separate owner act).

| # | Command | Expect |
| --- | --- | --- |
| 0 | `$OP pins $R`; `$OP bind $R $WD $MB11`; `$OP v0 $R $WD` | `E22_TOOL_PINS_EXACT`; bound; `E22_V0_EXACT` |
| 1 | `$OP status $R $WD STAGE`; `$OP render $R $WD STAGE`; owner go; `$OP stage $R $WD go.txt` | `REACHED_V1_NEW_STAGED` |
| 2 | same pattern, `SIGNER_STOP` / `stop-signer` | `REACHED_V2_SIGNER_STOPPED` |
| 3 | `WITNESS_STOP` / `stop-witness` | `REACHED_V3_WITNESS_STOPPED` |
| 4 | `SELECT` / `select` | `REACHED_V4_NEW_SELECTED` |
| 5 | `WITNESS_START` / `start-witness` (one K-WIT load; window) | `REACHED_V5_WITNESS_RUNNING` |
| 6 | `$OP post-witness $R $WD <envelope>`; `render ACCEPT_WITNESS`; owner statement; `accept-witness` | `E22_WITNESS_POST_VERIFIED`; recorded |
| 7 | `SIGNER_START` / `start-signer` (K-ACT load 2; window) | `REACHED_V6_SIGNER_RUNNING` |
| 8 | `$OP post-signer $R $WD <envelope>`; `render ACCEPT_SIGNER`; owner statement; `accept-signer` | `E22_SIGNER_POST_VERIFIED`, `kActLoadCount` 2; recorded |
| 9 | `RETIRE` / `retire` | `REACHED_V7_OLD_RETIRED` |
| 10 | `$OP windows $R $WD` | both windows; the boot for the reads |

Any other result is a STOP: no retry, no stop or restart by the operator, a read-only `status` only, then owner
adjudication. After V7:

1. DR-5 EQUAL against the derived post-swap target.
2. The OD-M12-11 `journal` and `attribute` reads, in the printed boot: exactly the historical 12 attributed matches.
3. The re-pin cascade, the M-B12 recollection and the SECRET_HYGIENE pin, only if the OD-M12-10 admission passes.
4. M-B13.

```text
E-22 OPERATOR (V0 … V7, OD-M12-11 WINDOWS, POSTS, ACCEPTANCES) = SOURCE ONLY;  NEW RELEASE = NOT BUILT / NOT PINNED
BUILD / STAGE / SELECT / RETIRE / UNIT STOP-START / KEY LOAD = NOT AUTHORIZED
E-22 = BLOCKED;  M-B12 = NOT PASSED;  CUSTODY = HELD;  K-ACT LOAD COUNT = 1
```
