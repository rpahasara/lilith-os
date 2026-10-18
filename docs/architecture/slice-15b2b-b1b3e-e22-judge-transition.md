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
