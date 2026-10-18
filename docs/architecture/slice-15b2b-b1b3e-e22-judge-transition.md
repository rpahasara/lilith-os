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
