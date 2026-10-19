# Slice 15B2b-B1b-3e M-B12 — E-22 Judge Transition Completion (V0 … V7) and Post-V7 Re-pin

Status:

- **REPOSITORY RECORD + RE-PIN SLICE.** This change performs no live mutation and no DEV contact. Base: main
  `04a0cdd4870788b196be99cfc4e5580ca0867092` (PR #221), the control commit of every live step below.
- It records the owner-authorized live transition `UPGRADE_E22_JUDGE_DEV_SYNTHETIC`
  ([judge transition](slice-15b2b-b1b3e-e22-judge-transition.md) §6, [pin](slice-15b2b-b1b3e-e22-new-release-pin.md)).
  It re-pins the installed-release bindings that must name the new release, and adds the post-V7 DR-5 comparison.
- It does **not** claim M-B12. The package recollection and the E-01 … E-24 verification come after this merges (§5).

## 1. The live transition (2026-10-18 / 19, DEV_SYNTHETIC)

Evidence: `C:\Users\edufo\lilith-e22-v0-04a0cdd\`. The operator workdir is `workdir/`, and the transcript and seals
are `SHA256SUMS.seal-2-stage` … `SHA256SUMS.seal-11-od-m12-11`. Every mutation followed the same sequence: the
owner's verbatim go (byte-identical to the operator's render), a fresh read-only gate, one `O_EXCL` marker, one
invocation, and a read-only post-status. There was no retry.

| Step | Owner go SHA-256 | Result |
| --- | --- | --- |
| V0 (read-only) | — | `E22_V0_EXACT`: OLD `ba943e1` only; signer `c7ba0fb7…` / 84806 and witness `90b28f9d…` / 69238; W11_1; one K-ACT load |
| STAGE | `82d757a9…` | `V1_NEW_STAGED` |
| SIGNER_STOP | `85777384…` | `V2_SIGNER_STOPPED` |
| WITNESS_STOP | `89ffb273…` | `V3_WITNESS_STOPPED` |
| SELECT | `2385b7d7…` | `V4_NEW_SELECTED` (`current -> releases/129f2be…`) |
| WITNESS_START | `c83c921c…` | `V5_WITNESS_RUNNING`: replacement witness `8cbfbed20c954c478425c7233084ce17` / 127192 |
| witness POST | — | `E22_WITNESS_POST_VERIFIED` (`d4f65baa…`): W11_1S, one K-WIT load in the window, denials P1B-9b / P1B-10 / P1B-5 PASS |
| witness acceptance | owner statement | recorded `c5e2d29c…` |
| SIGNER_START | `d567c55e…` | `V6_SIGNER_RUNNING`: replacement signer `efbc078492634b0280565d8990dab3d3` / 128648 |
| signer POST | — | `E22_SIGNER_POST_VERIFIED` (`691ffd9f…`): W11_1, one load in the window, HEALTH key `dd13a1fb…`; **K-ACT load count 2** (journal: `c7ba0fb7…`, `efbc0784…`) |
| signer acceptance | owner statement | recorded `8edddc0c…` |
| RETIRE | `01951755…` | `V7_OLD_RETIRED`: only `releases/129f2be…`; both accepted replacements run from it |

One local deviation is retained. The transfer `mkdir` (control `4873a9f`) printed exact output, but the Windows
client exited `0xC0000005`. The owner accepted it, and the independent verification read confirmed the directory and
files.

## 2. OD-M12-11 windows and reads

| Event | Window (UTC, boot `cb0d71da…`) | Record SHA-256 |
| --- | --- | --- |
| K-WIT (V5) | 2026-10-18T19:20:59Z → 19:21:15Z | `ddd2c01ac0fc2ab29845f5af9c661b9bf2f38ff7212c664c6cfa86f7fdf36f88` |
| K-ACT (V6) | 2026-10-18T19:29:29Z → 19:29:42Z | `183f3edd9ef78c2979cb43879326b67fc9939f7fd1acd14625a1b2116160f406` |

Both post-transition reads ran after the last load, in the same boot, with producer
`mb12_secret_hygiene_proof.py` `83b275b4…`:

- **`journal`:** `JOURNAL_SECRET_SCAN=FAIL`, `PRIVATE_MATERIAL_MARKER class=PEM_PRIVATE_KEY count=12`. Three retained
  boots. Transcript `959bb0b2…`.
- **`attribute`:** `JOURNAL_MARKER_ATTRIBUTION=COMPLETE matches=12`. The match list is byte-identical to the historical
  attribution: all 12 are in boot `24d1771d…`, in the three 2026-09-27 sudo sessions. Transcript `e65d5b1d…`.

So the reads show exactly the historical 12 attributed matches and no new marker, which is what the OD-M12-10
admission requires. The scan FAIL stands; it is adjudicated, never a clean scan.

## 3. Re-pins in this change

The installed release is now `129f2bed617334be61dcac5204cd409946a7a566`, manifest
`fc7dbf08bb5b8260716a762fd2fbccdb44fbf0e438e2e21d0cfddcd6f1a3348a`.

| Tool | Change | New SHA-256 |
| --- | --- | --- |
| `mb12_readiness_inputs.py` | `DEV_PINS` releaseSha / attestedManifestSha256 → E-22 | `229c75af41f705e62c61a0d1f3e34475879e33da6e32b666ebaeafa917e1e538` |
| `mb12_pr3_material.py` | `DEV_EXPECTED` releaseSha / releaseManifestSha256 → E-22 | `12c40b58c96f2025d0bbb97015d01eea3483f3c454b8f750e51dea95475f20c7` |
| `mb11_operator.py` | pin cascade (`TOOL_PINS[READINESS_INPUTS]`) | `9ba4a096cf69200ca9b6ab52dc182d41c7693871049aa88453ebd1b3f721df3d` |
| `e22_operator.py` | pin cascade (`TOOL_PINS[MB11_OPERATOR]`, readiness) | `717b08ea3e0030209c426a44bc7d50f585dbe4bfaa0980be16041758d1238978` |
| `e22_dr5_target.py` (new) | post-V7 DR-5 `derive` / `compare` | `430f4b53b47f06627a7278f86df518a5f2428f20ef01bc8c004d3dbe1ed67836` |

**Deliberately not re-pinned:**

- `mb11_signer_verifier.RELEASE_SHA` and `mb11_restart_boundary_install.RELEASE_SHA` stay `ba943e1`. W11 reads after
  V7 go through `e22_transition_remote`, which binds the W11 release to the phase. The restart-boundary value only
  feeds the accepted P1B-10R plan digest `2a004a41…`, and the fragment bytes are unchanged.
- Re-pinning these would rewrite the immutable E-19 completion record and its exact M-B11 pins for no M-B12 benefit.
- The bound M-B11 readiness envelope was not re-pinned for the V5 / V6 POSTs: W11 E / F do not read its `releaseSha`.

## 4. Post-V7 DR-5 (`e22_dr5_target.py`)

The target is the merged `NEW_DR5_TARGETS["SIGNER_RUNNING_WITNESS_RUNNING_HELD_E22"]`:

- result-set `194` / `a0ebd54d75f3f453970957454b00baf6767e64a8bb910f02344fbc72b46104ed`
- dr5-block `155` / `7fe21378bb97f57aed3a6c60f6fc216e08d646f9da42d9c35feb7509f5468f1c`
- predeploy-block `29` / `f50870420c10149914b8d2a02116708ec89ea5a8f746a847fbe88df058f54cae`

`derive` reproduces it from the accepted texts.

`compare <e22-workdir> <deploy-log>` gives EQUAL only when all of the following hold:

- the workdir has the consumed RETIRE that reached V7;
- the VERIFIED signer POST is present (W11_1, K-ACT count 2, release NEW);
- both owner acceptances are recorded;
- all three DR-5 sets are byte-equal to the target, with no `ALLOWED` line and no line naming `ba943e1`.

The pre-swap text is DRIFT. No deploy has run since V7, so this comparison has not run yet. The routine deploy of
this change's merge is its first input.

## 5. Remaining for M-B12 (not done here)

1. Merge this PR. Its deploy is the first post-V7 deploy. Run `e22_dr5_target.py compare <workdir> <deploy log>`,
   which must be EQUAL.
2. Run the M-B12 readiness recollection on the re-pinned control (read-only DEV, existing tools). Then check the
   canonical E-01 … E-24 package: E-22 is admissible only as the OD-M12-10 `OWNER_RISK_ADJUDICATED` outcome, and every
   other check stays PASS-only.
3. M-B12 is accepted only by the owner, on that package. Then M-B13.

## 6. State

```text
E-22 TRANSITION = V7 REACHED (owner-accepted replacements: witness 8cbfbed2…/127192, signer efbc0784…/128648)
K-ACT LOAD COUNT = 2;  K-WIT LOADS IN E-22 = 1;  OD-M12-11 READS = 12 HISTORICAL ATTRIBUTED MATCHES, NO NEW MARKER
INSTALLED = 129f2be (only);  POST-V7 DR-5 = NOT YET RUN;  M-B12 = NOT PASSED;  CUSTODY = HELD;  AUTHORITY = DARK
```
