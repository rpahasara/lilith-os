# Track B E-23 — E5 WITNESS_UNITS STOP: Classifier Fix and Owner Adjudication

Status:

- **PROPOSED — NOT APPROVED.** This record and the adjudication pin it adds take effect only when the owner reviews and
  merges it.
- **REPOSITORY-ONLY.** `LIVE_MUTATION = NONE`, `DEV_CONTACT = NONE` in this change. Base: main
  `76846661ecf98cd2fc54d5ccf80029204ffd8beb` (PR #253 merge; the control commit of E0 … E5).
- It relates to [E-23 transition](trackb-e23-transition.md).

```text
adjudicated STOP != reached step;  chain continuation != any go;  the next step still needs its own fresh gate and go
```

## 1. What happened (2026-10-25, DEV_SYNTHETIC)

E0 → E4 completed under owner gos, one attempt each (evidence `C:\Users\edufo\lilith-e23-preflight-7684666\`, seals
2 … 6). E23-GO-WITNESS-UNITS (canonical go `0a956584…`, bound to observation 14) ran **once**:

| Item | Value |
| --- | --- |
| Gate | observation 15: `E4_NEW_SELECTED`, K-PAN `PRESENT_EXACT` (inode 262565, 219 B) |
| Marker | `attempts/e23-witness-units.json`, consumed |
| Remote | one `e23-witness-units`, mutation `WITNESS_UNITS_REPLACED_RELOADED`, rc 1 (its post-check failed) |
| Post | observation 16: `ES_WITNESS_UNITS_NOT_EXACT` (`witnessUnits = MIXED`) |
| Step record | `steps/05-WITNESS_UNITS/STEP.json`, result `E23_WITNESS_UNITS_STOP`, SHA-256 `c331e1e48e83d6a2885134ccb2347347eb771e5bda5f99cfd1df245170816f10` |
| Seal | `SHA256SUMS.seal-7-witness-units-stop` `2a041511…` |

The same post-status showed every intended effect:

- `current` → NEW `57bff671…`, and both releases present;
- all five authority and witness units inactive;
- the E4 `UNIT_BYTES` installer findings gone (the host unit and tmpfiles equal the NEW assets);
- `NeedDaemonReload=no`;
- the anchor directory present and empty, with no chain;
- K-PAN and K-WIT unchanged;
- the foreign services unchanged.

No retry and no repair.

## 2. Root cause (confirmed by one owner-approved read-only stat)

| Path | Owner : group | Mode |
| --- | --- | --- |
| `/var/lib/lilith-privacy-anchor` | `lilith-recovery-witness` (994) : `lilith-recovery-witness` (984) | 0700 |
| `/var/lib/lilith-recovery-witness` | `lilith-recovery-witness` (994) : `lilith-authority-dev` (985) | 2750 |

Evidence: `AB-stat.out`, seal `SHA256SUMS.seal-8-anchor-stat` `29bfc855…`.

The anchor directory is exactly the new tmpfiles line (`d … 0700 lilith-recovery-witness lilith-recovery-witness`).
`e23_release_stages.witness_units_state` wrongly required the anchor's owner and group to equal the witness **state**
directory's. That directory is `wit:svc 2750` by the installer contract, so its group is the signer group. A correctly
created anchor therefore read `MIXED`.

The fake-systemd tests missed it because every fixture directory had the same group. **The host was exactly E5. The
STOP was a tooling defect.**

## 3. The fix (this change)

- **`e23_release_stages.py`.** The anchor must be `("dir", wit uid, wit gid, "0700")`. Here `wit` is the installer's
  witness principal (`install_authority_dev._principal(system, "wit", …)`: the witness user and its primary group).
  An unknown witness account fails closed.
- **Tests.** The fixture now carries the DEV shape: the state directory is in another group (as root, in WSL). New
  tests:
  - the DEV anchor next to that state directory is E5;
  - a wrong owner, group or mode, or no witness account, is a STOP.
- **`e23_operator.py`.**
  - It re-pins `TOOL_PINS[STAGES]`.
  - It adds `ADJUDICATED_STEPS = {"WITNESS_UNITS": "c331e1e4…"}` (§4).
  - Nothing else changes: same phases, gates, commands and go texts. The operator SHA in each go changes with its bytes.

## 4. The adjudication (what merging this record decides)

The consumed WITNESS_UNITS step whose `STEP.json` is **exactly** SHA-256
`c331e1e48e83d6a2885134ccb2347347eb771e5bda5f99cfd1df245170816f10` counts as reached, **for the step chain only**.

**What it does not do:**

- It does not re-run WITNESS_UNITS. Its marker stays consumed; a second attempt is refused.
- It does not admit any other record or any other step. A different digest or a non-STOP result is refused.
- It does not skip a gate. The next step, WITNESS_START, still needs:
  - a fresh read-only status that the **fixed** classifier judges exactly `E5_WITNESS_UNITS_NEW`;
  - its own canonical owner go, consumed once.

If the fresh status is anything else, that is a new STOP.

## 5. Recovery after merge (each line its own owner decision)

1. The merge commit becomes the new control. Run `e23_operator pins` (exact).
2. Take one read-only `e23_operator status` in the same workdir. It must be `E5_WITNESS_UNITS_NEW` with K-PAN
   `PRESENT_EXACT` (inode 262565) and everything else as in observation 16. Otherwise STOP.
3. Run `render WITNESS_START`. That is the E6 go, for the owner to approve.

## 6. Open owner decision: the merge deploy versus the deploy freeze

`scripts/classify_dev_deployment.py` admits only an explicit `CONTROL_ONLY_PATHS` allowlist, and these files are not on
it. So merging this change is `DEPLOY_REQUIRED`: the DEV Core API deploy runs mid-transition.

**Consequences:**

- It restarts `lilith-os-api-dev`. The #253 deploy did (PID 274541 → 276946).
- `verify` would then report `FOREIGN_UNIT_INCARNATION_CHANGED`, because its baseline is the preflight.
- Its DR-5 comparison would run while the signer and witness are stopped.

**Options:**

| Option | Effect |
| --- | --- |
| A | Use the reviewed fix commit as the operator control **before** merging. This departs from E-19/E-22 practice, which merged first |
| B | Merge and accept that deploy. A further owner record then admits exactly that Core API incarnation change before `verify`. That needs one more small operator change |
| C | Add these paths to the deploy classifier's control-only allowlist first. That is its own reviewed change |

No option is chosen here.
