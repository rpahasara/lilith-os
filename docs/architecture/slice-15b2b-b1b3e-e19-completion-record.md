# Slice 15B2b-B1b-3e — E-19 Completion Record

Status:

- **REPOSITORY-ONLY COMPLETION RECORD.** `LIVE_MUTATION = NONE`, `DEV_CONTACT = NONE` in this change. Base: main
  `3cdee90ea4c10b18b81f5d4b9c4c268657ce0ded` (the PR #194 merge, deploy `38504051046`, the transition's control
  commit).
- **E-19 transition: COMPLETE to U5.** Every one-time go was consumed once and reached its phase.
- **E-19 owner completion: NOT ACCEPTED.** The deployment freeze stays **ACTIVE**.
- **Contract route.** The contract's U5 route is `FINAL_POST_AND_FIRST_DEPLOY_DR5_THEN_OWNER_COMPLETION`. This PR is
  the "completion record PR that pins the replacement" named by the
  [transition implementation](slice-15b2b-b1b3e-e19-transition-implementation.md) §2 step 12.
- **The merge is the first deploy.** Merging this PR is the separately authorized first post-transition deploy. It is
  not authorized here.

```text
transition complete (U5) != DR-5 EQUAL on NEW != owner completion accepted != freeze lifted
derived target != accepted target;  a local test is never DR-5 EQUAL evidence
```

## 1. The completion record (`services/owner-memory-control/tools/e19_completion_record.json`)

The record is machine-readable: canonical sorted JSON, LF line endings. Its SHA-256,
**`31bc707ebc9b58b376d233a30594eaa0e1f4d3b32444b172c741dbaeec66b3b8`**, is pinned by `e19_dr5_target.py`. It is
validated against the merged contract by `e19_completion.load_record`.

Status: `TRANSITION_COMPLETE_U5_OWNER_COMPLETION_NOT_ACCEPTED`. `ownerCompletionAcceptance = null`.
`deploymentFreeze = ACTIVE`.

| Binding | Value |
| --- | --- |
| U0 baseline | acceptance `8c0c30fc806c32b229e47c0318ab1c10eec43574c566ca5261d3d56dea030052`; statement `02d952f9…`; observation `6263ebea…`; cursor `s=4704cb6f…;i=a4b72;…;x=5e0d7dc3d1086261`; ending incarnation `8af12bd6…` / 1580 |
| STAGE (U0 → U1) | go `2264de72…`; marker `c22dfac9…`; post `2ea5d644…` |
| STOP (U1 → U2) | go `a958e13a…`; marker `aedb35ed…`; post `33045398…` |
| SELECT (U2 → U3) | go `57151f43…`; marker `fc6bca46…`; post `1a869804…` |
| START (U3 → U4) | go `2034b887…`; marker `1c70b921…`; post `0149ce36…` |
| RETIRE (U4 → U5) | go `594aa7a9…`; marker `e3e0c63d…`; post `cb22dd2607755ff0822c12287a89e4c7117a487e74d3ac88373eeee4ce2d9256` |
| POST9A-R | `POST9A_R_VERIFIED`; evidence `d44d1c4bcf767b90471da83f86a19c15f0c77c5fdffd209b41018500e7fb08b8`; P1B-9b / P1B-10 / P1B-5 PASS |
| Replacement acceptance | record `90e81b284eb87078fcc0495a961cd995fd8d3aaf8478a88536b24bb6ecaf9f3e`; statement `6a784747…` |
| Accepted replacement | InvocationID `90b28f9d06fd48a1a1bdc3ae39474fb1`, MainPID `69238`; journal ids after the U0 cursor = [ending, replacement]: **one K-WIT load** |
| NEW release | `ba943e1a188d98f4108c9eec7149c0cf1a8f68bb`, manifest `b8393015e505495a81629411a4ecd33c0c372c7b16d2761094eb4e018bc300a2`, archive `a4ad24e8…`, attestation `d6f7f709…`; **sole installed, selected** |
| OLD release | `aee323e…`, manifest `1d578ca7…`; **RETIRED** |
| Final host U5 | `E19_HOST_U5_OLD_RETIRED_REPLACEMENT_ACCEPTED_PASS`; HOST_RESULT `aac2b926…`; W10 output `314ca426…` |
| Evidence manifests (owner workstation) | U5 `60bcaf4cf0500c7f6d4162258e86cefe396b624e255ff89a7209bb8510f77168`; host U5 `bc2dc210c35832869e01b9768d6e9bfc45281db966a857394ce1ea6a81a1722e`; plus the ten earlier E-19 directories (full values in the record) |

The evidence stays on the owner workstation. Only digests are committed, following the repository practice.

## 2. Post-U5 release bindings

Four current bindings now name NEW. Each one only describes the installed release.

| File | Change | Was → now |
| --- | --- | --- |
| `services/owner-memory-control/tools/mb11_signer_verifier.py` | `RELEASE_SHA` → NEW; `RELEASE_CWD` follows | `020ab5b1…` → `e21fd26fd68bcdea3d645a12ff53b647ef3aa8f62824e9c89712b8fcb85d4e1d` |
| `services/owner-memory-control/tools/mb11_restart_boundary_install.py` | `RELEASE_SHA` → NEW; signer fragments unchanged | `44ab3f04…` → `428d93b4b36bdb8d7783e2c1f22d3961fd5cf3623ce0ee0d419ab3b81c53c8af` |
| `services/owner-memory-control/tools/mb12_pr3_material.py` | `DEV_EXPECTED` releaseSha / releaseManifestSha256 → NEW | `cc63183a…` → `cac0634bd15fff548822cead4a1bc1e587b015f0f668230365886f1200cc0774` |
| `services/owner-memory-control/tools/mb12_readiness_inputs.py` | `DEV_PINS` releaseSha / attestedManifestSha256 → NEW | `3483020e…` → `d325d07f9e2ba23b1c5d98e295d415275c8aab88d0d9c50ea8081f99eb19ce2b` |
| `services/owner-memory-control/tools/e19_operator.py` | `TOOL_PINS[RESTART_BOUNDARY_INSTALL]` follows | `a49ed4f5…` → `b98328162b72795de0579d5e7abb58ff55f1bd7498e53b8699d91af5d453c1dd` |

The signer fragment bytes are identical in OLD and NEW, because the payload delta is `pr1_acceptance.py` only.

**Unchanged, byte-identical.**

- `mb6_operator` (`4a91d984…`), `mb9_operator` (`2312e26a…`) and `mb12_os_denial_proof` (`e6754228…`).
- The contract (`e8c8f603…`) and the observer (`bc3017d1…`).
- The historical ceremonies.
- The M-B10 W10_1 DR-5 targets and their phase map.

The retired release's SHA remains only where it is history or provenance (`e19_completion.OLD_RELEASE_MENTIONS`). A
test fails on any unclassified mention.

**Routine successor read.** The M-B10 host POST reads OLD through the `mb6` / `mb9` readiness pins, so it cannot
judge the installed release any more. The routine post-U5 preservation read is now `e19_operator host <main>
<workdir> U5_OLD_RETIRED_REPLACEMENT_ACCEPTED`.

- It judges readiness by NEW's module pins (`PAYLOAD_DELTA` moved) and the installer state `E19_OLD_RETIRED`.
- It never requires OLD.
- It was proven live by the final host U5 PASS.

## 3. E-19 DR-5 comparison (`services/owner-memory-control/tools/e19_dr5_target.py`)

The targets are the merged `e19_p1b10_upgrade.NEW_DR5_TARGETS` (PR #194). `derive` re-derives them as
`derive_release_swap(OLD → NEW)` over the accepted W10_1 texts (`mb10_dr5_target.derive`, pinned `29c35961…`), and
requires equality with the pins.

| Target | result-set | dr5-block | predeploy-block |
| --- | --- | --- | --- |
| `WITNESS_RUNNING_HELD_E19` (first post-transition deploy) | 192 / `91c91ec7d5001d8c13f8438cb3d653ea3ee9b6bc1e41087ec154fec834def13d` | 153 / `0692dc6df9dfbba2e6d81d985d56090025c11d2756a6397966346bb5f9e5fd16` | 29 / `f50870420c10149914b8d2a02116708ec89ea5a8f746a847fbe88df058f54cae` |
| `WITNESS_STATE_PRESENT_SERVICE_STOPPED_HELD_E19` | 190 / `a3d07a43…` | 151 / `8d25c676…` | 29 / `f5087042…` |

**`compare <host-u5-dir> <deploy-log>`** maps a verified `host U5` result to a target. It requires all of:

- `HOST_RESULT.json` = `E19_HOST_U5_OLD_RETIRED_REPLACEMENT_ACCEPTED_PASS` for NEW, with all 11 reads rc 0,
  `E19_OLD_RETIRED`, readiness exact and no residue;
- `w10verifier.rc` = 0;
- a W10 phase in `{W10_1_HELD_EXACT → RUNNING_HELD_E19, W10_1S_HELD_EXACT_WITNESS_STOPPED → STOPPED_HELD_E19}`;
- for RUNNING, the W10 identity equal to the completion record's accepted replacement with 0 restarts;
- authority inactive.

**EQUAL** needs byte equality of all three sets, zero `ALLOWED` lines and zero lines naming OLD. Anything missing is
refused (`NO_BASELINE_STOP` / `DR5_SETS_MISSING`). Any other difference is DRIFT. The output always says
`targetStatus = DERIVED_PINNED_NOT_ACCEPTED` and `accepted = false`.

**Local check against real artifacts (no DEV contact).**

- The real host U5 evidence binds to `WITNESS_RUNNING_HELD_E19`.
- The pre-transition deploy log `38504051046` compares **DRIFT** with 4 OLD lines, as it must.
- No EQUAL is claimed. EQUAL can only come from the post-merge deploy.

## 4. The freeze gate (`services/owner-memory-control/tools/e19_completion.py`)

`freeze_lift_admissible(host_u5_dir, deploy_run_id, acceptance)` judges and writes nothing.

**Security correction.** It takes **no** comparison document and no run metadata from the caller. This fixes the
review findings B1 and B2 on `af668a15`: the gate re-establishes everything itself.

**Deploy provenance (B2).** It is read only from the GitHub Actions REST API through the owner's authenticated `gh`
(`GitHubSource`). The gate requires all of:

- PR #195 `merged`, into `main`, giving its `merge_commit_sha` and `merged_at`;
- run `<id>`:
  - `name` = `Deploy LILITH Core API to DEV`, `path` = `.github/workflows/deploy-dev.yml`;
  - repository `rpahasara/lilith-os`, `event` = `workflow_run`, `head_branch` = `main`;
  - `completed` / `success`;
  - `head_sha` = the merge commit;
  - created after the merge;
  - the **first** `workflow_run` deploy-dev run created after the merge.

  The PR-only "LILITH DEV deployment" CI stub (`ci.yml`, `pull_request`) can never qualify.
- the run log, fetched from GitHub by the gate (`gh run view <id> --log`) and hashed.

**Host binding.** The canonical `e19_operator host U5` directory's own identity read (`identity.out`, rc 0) must name
`lilith-dev-01`, the DEV machine-id and the accepted boot. Its DEV-clock UTC instant must be **strictly after** the
run's completion (`updated_at`). The pre-merge host U5 read (`2026-10-14T07:31:33Z`) therefore can never qualify.

**Recomputation (B1).** The gate runs `e19_dr5_target.compare(host dir, fetched log)` itself. The result must be EQUAL
to `WITNESS_RUNNING_HELD_E19` at `W10_1_HELD_EXACT`, and its host evidence must equal the host digests above. A
handcrafted EQUAL has no input path.

**Owner binding.** The owner's verbatim statement (`render`) names:

- the completion record, NEW, OLD and the replacement;
- PR #195's merge commit, the run id and its completion instant, and the log SHA-256;
- the host read instant and the HOST_RESULT SHA-256;
- the comparison SHA-256 and the evidence SHA-256.

The local acceptance record must bind the same evidence and statement digests.

**Before the sanctioned deploy exists** (PR not merged, or no qualifying run), the result is `FREEZE_ACTIVE:…`.

**What can never lift the freeze:**

- missing, unparseable or other-repository provenance;
- a wrong workflow, trigger, conclusion, commit, order or run id;
- an empty or different log;
- a pre-deploy, stale, other-host or other-boot host read;
- DRIFT, the STOPPED target, or a witness other than the accepted replacement;
- a reworded statement or a mismatched record.

**Trust boundary.** GitHub's API and the owner's `gh` authentication are trusted for deploy facts. The `host U5`
directory is the operator's own local record, as is every E-19 evidence directory, and its digests are bound into the
owner's statement. Ordering relies on the DEV host clock and GitHub's clock both being UTC, NTP-synchronised.

**New tool pins.**

| File | SHA-256 |
| --- | --- |
| `services/owner-memory-control/tools/e19_completion_record.json` | `31bc707ebc9b58b376d233a30594eaa0e1f4d3b32444b172c741dbaeec66b3b8` |
| `services/owner-memory-control/tools/e19_dr5_target.py` | `c7b99e446ecb107ad074ba14aff96238fb7bca8312ca5827c1396bec928b76be` |
| `services/owner-memory-control/tools/e19_completion.py` | `aee80c9c0413326b0dcd339883e149a7c3c67df6aba2b644b07944f55b05db10` |

## 5. Validation

- **WSL, Ubuntu 24.04:**
  - the new `test_b1b3e_e19_completion.py`: record, bindings, derive, compare (fail-closed matrix) and freeze gate;
  - the updated E-19, M-B11 and M-B12 suites;
  - the full owner-memory-control, authority-dev and recovery-witness suites; `validate_repository.py`.
- **Test changes:**
  - the M-B11 record-pin tests accept a tool pin from the M-B11 record (unchanged check) **or** exactly
    `e19_completion.MB11_REPINNED_SHA256[<that file>]`. This is a structured file → SHA-256 map holding only the two
    re-pinned M-B11 tools; it has no substring match, no concatenation and no other field (C1). The M-B11 design
    records are not rewritten;
  - the M-B12 E-19 defect test now names the retired release explicitly.

## 6. Owner sequence (each step its own act; none authorized here)

1. Review this PR. Do not merge until the owner authorizes the first post-transition deploy.
2. Merge. That triggers the first post-transition deploy (`Repository validation` → `Deploy LILITH Core API to DEV`).
3. Read-only, after the deploy completes: `e19_operator host U5`. That gives a fresh host directory whose identity
   instant is later than the run's completion.
4. `e19_completion render <host-u5-dir> <run-id>`. It fetches the provenance from GitHub, recomputes the DR-5 EQUAL
   and renders the statement. Then the owner's verbatim statement and the local acceptance record follow.
   `e19_completion gate <host-u5-dir> <run-id> <acceptance.json>` must return `FREEZE_LIFT_ADMISSIBLE`.
5. The owner's E-19 completion acceptance, which lifts the freeze. Package READY, M-B11 and authority remain separate
   milestones.

## 7. State

```text
E19 TRANSITION = COMPLETE (U5);  E19 OWNER COMPLETION = NOT ACCEPTED
NEW = ba943e1 (sole installed);  OLD = aee323e (retired);  replacement = 90b28f9d / 69238
NEW_DR5_TARGETS = DERIVED_PINNED_NOT_ACCEPTED;  first post-transition DR-5 = NOT OBSERVED
FREEZE = ACTIVE;  LIVE_MUTATION = NONE;  DEV_CONTACT = NONE;  authorityGranted = false
```
