# Track B E-23 — Transition Completion (E0 … E8) and Post-E8 Re-pin

Status:

- **REPOSITORY RECORD + RE-PIN SLICE.** `LIVE_MUTATION = NONE`, `DEV_CONTACT = NONE` in this change. Base: main
  `571eb46bacc3135e2f2165e332e75343d700c803` (PR #254), the control commit of E5 recovery … E8.
- It records the owner-authorized live transition `UPGRADE_E23_PRIVACY_ANCHOR_DEV_SYNTHETIC`. References:
  [transition tooling](trackb-e23-transition.md), [pin](trackb-e23-new-release-pin.md),
  [E5 adjudication](trackb-e23-e5-adjudication.md).
- It re-pins the installed-release bindings that must name the new release, and derives the post-E8 DR-5 target.
- No E-19 / E-22 historical record, pin or authorization changes. The M-B11 operator record gets only its append-only
  re-pin addendum §25, as E-22 added §23.
- **Not claimed:** a DR-5 EQUAL, Privacy activation, or any M-B milestone.

## 1. The live transition (2026-10-25 / 26, DEV_SYNTHETIC)

Evidence: `C:\Users\edufo\lilith-e23-preflight-7684666\`. The workdir is `workdir\`; seals run from
`SHA256SUMS.seal-2-kpan` to `seal-9-e8`. Every mutation followed the same sequence:

1. the owner's verbatim go, byte-identical to the operator's render;
2. every earlier step reached;
3. a fresh read-only gate;
4. one `O_EXCL` marker;
5. one invocation;
6. a read-only post-status.

There was no retry.

| Step | Control | Owner go SHA-256 | Result |
| --- | --- | --- | --- |
| Preflight | `7684666` | — | `E23_PREFLIGHT_EXACT`. E0: OLD `129f2be` only; signer `efbc0784…`/128648 and witness `8cbfbed2…`/127192 (the E-22 accepted pair); K-PAN absent |
| K-PAN keygen | `7684666` | owner chat go | one `trackb_kpan_keygen.py` run (`aec2d7c4…`). `kpan.dev-synthetic.01`, public key SHA-256 `a9a4dfdc…`; blob 219 B, root 0600; K-WIT unchanged |
| STAGE | `7684666` | `99aa0e93…` | `E1_NEW_STAGED` (archive `a8cadbfa…` transferred and verified first) |
| SIGNER_STOP | `7684666` | `31266733…` | `E2_SIGNER_STOPPED` |
| WITNESS_STOP | `7684666` | `b4aacb13…` | `E3_WITNESS_STOPPED` |
| SELECT | `7684666` | `1df56409…` | `E4_NEW_SELECTED` |
| WITNESS_UNITS | `7684666` | `0a956584…` | Host effect complete, but the post-check STOPped on the anchor-group classifier defect. Fixed and owner-adjudicated by PR #254 (`STEP.json` `c331e1e4…`); never re-run |
| E5 recovery read | `571eb46` | — | `E5_WITNESS_UNITS_NEW` under the fixed classifier; #254 merge classified `CONTROL_ONLY_NO_DEPLOY` |
| WITNESS_START | `571eb46` | `18942072…` | `E6_WITNESS_RUNNING`: replacement witness `86ba4cc2d0864119bba502f5f4ccd14e` / 281470, K-WIT and K-PAN loaded. `verify` VERIFIED (`81e321e8…`); owner acceptance `8a3dcce2…` |
| SIGNER_START | `571eb46` | `824e3a74…` | `E7_SIGNER_RUNNING`: replacement signer `639a814da4dc4d338cef37565e14e2c0` / 281830, **K-ACT load 3**. `verify` VERIFIED (`8ee0ab36…`); owner acceptance `4a27467e…` |
| RETIRE | `571eb46` | `7ce476ef…` | `E8_OLD_RETIRED`: only `releases/57bff671…`; both accepted replacements run from it |

**Throughout:** Core API, Hermes gateway, provider gate and broker kept their preflight incarnations; K-WIT and K-PAN
metadata were unchanged; the anchor directory (`lilith-recovery-witness:lilith-recovery-witness 0700`) holds no chain.

## 2. Re-pins in this change

The installed release is now `57bff671fbfe5df4e59248d5d69338dc0ba05846`, with manifest
`fc29a23cbb411704f2799b418f8c7fd7fadf215489174e9ac9d370db2e78368c`.

| Tool | Change |
| --- | --- |
| `mb12_readiness_inputs.py` | `DEV_PINS` releaseSha / attestedManifestSha256 → E-23 |
| `mb12_pr3_material.py` | `DEV_EXPECTED` releaseSha / releaseManifestSha256 → E-23 |
| `e19_witness_restart_boundary_install.py` | `FRAGMENTS[lilith-recovery-witness.service]` `9f78130c…` → `b3e2c753c6facea0691752c4894f28ce3f2fe3738f31cf3baa75a25af1d011c1` (the E-23 unit). The sockets are unchanged |
| `mb11_operator.py` → `e22_operator.py` → `e23_operator.py` | `TOOL_PINS` cascade only (M-B11 record §25) |
| `mb14_operator.py` → `mb15_operator.py` | `TOOL_PINS` cascade only. Both build on the E-22 operator's transport; no behaviour change |

**Deliberately unchanged:**

- `mb6_operator.RELEASE_MODULES` and the other closed-ceremony module pins. The M-B6 ceremony is historical, and every
  operator's transport chain pins `mb6_operator.py`.
- The W11 verifier and restart-boundary release pins (the E-22 decision, §3 of its completion record).
- The E-23 contract: OLD / NEW / delta stay as merged.

## 3. K-PAN credential-directory listing

Since K-PAN exists, the frozen installer V1 `status` reports `LISTING:/etc/lilith-recovery-witness/credentials`. Only
the three release-stage tools consume installer `status`. The current reads (W9 / W10 / W11, readiness, PR-3) judge no
listing of that directory.

`e23_release_stages` admits exactly that one finding, and only when the listing is exactly the K-WIT and K-PAN names
with K-PAN `PRESENT_EXACT`. Any other name, or an unsafe K-PAN, stays a STOP; a test proves it. No other check is
widened, and nothing else needs admitting.

## 4. Post-E8 DR-5 target (`e23_dr5_target.py`)

The target is the accepted E-22 procedure moved one release on. The E-22 post-V7 texts are re-derived and must equal
their merged pin. `derive_release_swap(OLD = 129f2be…, NEW = 57bff671…)` then moves exactly the release lines.

| Target | result-set | dr5-block | predeploy-block |
| --- | --- | --- | --- |
| `SIGNER_RUNNING_WITNESS_RUNNING_HELD_E23` | 194 / `94d38f47f25004e409ac4a7a717c6cd751ed44aa20f249548821054999c913ac` | 155 / `402633cde5be1c660613c1a6f64a57ca4f9116ecafa59571d043feb4d16404b0` | 29 / `f50870420c10149914b8d2a02116708ec89ea5a8f746a847fbe88df058f54cae` (no release line; equal to E-22) |

The target is `DERIVED_PINNED_NOT_ACCEPTED`, and **no real deploy proof has been compared with it**.

`compare <e23-workdir> <deploy-log>` reads EQUAL only when all of these hold:

- the workdir has the consumed RETIRE that reached E8;
- the VERIFIED signer is on NEW;
- both owner acceptances are recorded;
- all three DR-5 sets are byte-equal to the target, with no `ALLOWED` line and no line naming a retired release.

The E-22 text is DRIFT.

**Caveat.** The derivation assumes the deployer-boundary proof's text changes only in its release lines. If the first
post-E8 deploy proof differs elsewhere (for example a line that reflects the new witness unit), `compare` reads DRIFT.
That is an owner adjudication, never an automatic re-pin.

## 5. Validation

- `tests/test_trackb_e23_completion.py` (new):
  - the pins;
  - the target re-derivation (only release lines move);
  - EQUAL only for the E-23 text on an E8 workdir;
  - the fail-closed cases;
  - this record.
- `tests/test_trackb_e23_release_stages.py`: the K-PAN listing admission is exactly two names.
- Current-pin assertions are adapted: the E-19 / E-22 completion, maintenance, judge and PR-3 tests now name the E-23
  installed release, and the E-22 NEW is asserted to be the E-23 OLD.
- The WRB fixture host carries the installed (E-23) unit.

## 6. Remaining (not done here)

1. **Review and merge this change.** The merge is `DEPLOY_REQUIRED`: these tools are not on the control-only
   allowlist. That deploy is the first post-E8 routine deploy and ends the E-23 deploy freeze.
2. **Run `e23_dr5_target.py compare <workdir> <deploy log>` on that deploy's log.** EQUAL is required. DRIFT is an
   owner adjudication.
3. **Then the owner decides Privacy activation (B5 / B6) separately.** K-PAN is loaded; there is no genesis yet.

## 7. State

```text
E-23 TRANSITION = E8 REACHED (owner-accepted replacements: witness 86ba4cc2…/281470, signer 639a814d…/281830)
K-ACT LOAD COUNT = 3;  K-PAN = LOADED BY THE WITNESS, NO ANCHOR CHAIN;  INSTALLED = 57bff671 (only)
E-23 DR-5 = DERIVED, NOT YET COMPARED;  DEPLOY FREEZE = UNTIL THIS CHANGE'S REVIEW;  PRIVACY ACTIVATION = NOT STARTED
```
