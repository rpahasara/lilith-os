# Slice 15B2b-B1b-3e — E-19 NEW Release Pin and Derived DR-5 Targets

Status:

- **REPOSITORY-ONLY PIN SLICE.** `LIVE_MUTATION = NONE`, `DEV_CONTACT = NONE`. Base: main
  `ba943e1a188d98f4108c9eec7149c0cf1a8f68bb` (the PR #193 merge, deploy `38426037134`; post-#193 preservation PASS).
- **Owner authorization:** one focused repository-only PR. It pins the independently attested NEW authority release
  and derives its E-19 release-swap DR-5 targets. No live DEV operation is authorized.
- It follows owner sequence step 3 of the
  [E-19 transition implementation](slice-15b2b-b1b3e-e19-transition-implementation.md) §2, under E19-D4
  ([E-19 release maintenance](slice-15b2b-b1b3e-e19-release-maintenance.md) §10).

```text
NEW attested != NEW pinned != NEW staged != NEW selected (installed) != replacement accepted != any go
DR-5 targets derived + pinned != accepted != effective (post-U5 only)
```

## 1. Two identities: the release source and the pin commit

| Identity | Value | Meaning |
| --- | --- | --- |
| **NEW release** (`NEW_RELEASE`) | `ba943e1a188d98f4108c9eec7149c0cf1a8f68bb` | The **source** commit the archive was built from. It is the archive's `candidateSha`, its manifest's `candidateSha`, and the future `releases/<NEW>` directory name. |
| **Pin commit** (this PR's head, and later its merge) | not a release | It carries the pins and becomes the **control commit** of later E-19 operator runs. It is never built, staged or installed. A later main commit does not rebuild NEW. |

The pin commit changes no payload source. A local check found that every non-wheel member of the attested archive is
byte-identical to the corresponding source file on this branch (§4).

## 2. The pins (`services/owner-memory-control/tools/e19_p1b10_upgrade.py`)

| Constant | Value |
| --- | --- |
| `NEW_RELEASE` | `ba943e1a188d98f4108c9eec7149c0cf1a8f68bb` |
| `NEW_MANIFEST_SHA256` | `b8393015e505495a81629411a4ecd33c0c372c7b16d2761094eb4e018bc300a2` |
| `OLD_RELEASE` (unchanged; still installed) | `aee323e94412accbe321bc84eae78c5b8cf95afc` |
| `OLD_MANIFEST_SHA256` (unchanged) | `1d578ca707a95134dab218c826408b4380e7af0b5839160f47ede37232b94e8f` |

`NEW_RELEASE_ATTESTATION` holds the build provenance. It is a record only: `e19-stage` verifies the archive against its
builder stamp (installer `verify_archive`) and against `NEW_MANIFEST_SHA256`.

| Field | Value |
| --- | --- |
| `archiveSha256` | `a4ad24e8c261c6e5858c559f4102ac8d6cc6923cfc19a9a7ffe5720408ae3faf` |
| `archiveByteSize` | `5355042` |
| `builderStampSha256` | `cc1695184453c99bd0d0ffd3c18fca8eaf2b979e9f33a4c2a6fbd1b236837211` |
| `attestationDigest` (`LILITH_PR1A_BUILD_ATTESTATION_V1\0`) | `d6f7f709d3b40dc42d6fb9c936137bb6c6871c36917c9d27f8f2faa634ff51d2` |
| `buildRecipeSha256` | `aa1c5200db931553271897f18a53306bd7c5ab6726d3b484b74d0b1e134ce092` |
| `authorityReleaseDigest` | `5a7c990318e74fd3c8a5e39259a9382cbc7f3971ce38efad0fdc425c61a45f58` |
| `evidenceManifestSha256` | `b502b8dab36fa72349c5f386e02522b1a9b0325a4072c6a4189265979a7c21a7` |

**Builds.** BUILD_A ran on Windows 11 (CPython 3.13.5, zlib 1.3.1, fresh clone). BUILD_B ran on WSL Ubuntu 24.04.5
(CPython 3.12.3, zlib 1.3, git bundle, `env -i … -I -B`).

- The two builds are byte-identical, with identity `5fe150147ae7bc0712e52640a5a24a086b8b5c57a02983ee5e93c0fb7fe15ebe`.
- `attest` returned `REPRODUCED`. `check` returned PASS on Windows, and independently in WSL against BUILD_B's own
  archive.
- The attestation tool is byte-identical to the PR-1A gate (`709cd552…`).

**OLD → NEW payload.** The only change is `lilith_owner_memory/pr1_acceptance.py`:

- from `e0928854e1fcf4107458939ba9ebf1903cf7a4d0ab6808f7e89108db1444bbff`
- to `0d2e6ccabf916425a1dfa7dc587bfcb3d7a232eb6c52c5cd938d573199715cff`

This is `PAYLOAD_DELTA`, and it reverses exactly by `E19_EDITS`.

The following are byte-identical: units, sockets, tmpfiles, CLIs, host targets, install modes, wheels and lock, the
witness runtime digest and the root-tooling digest.

Approved non-executable metadata changes:

- the manifest `candidateSha`;
- the recipe file `release_file_set.py`: its TEST and CEREMONY lists, and the `SHARED_HASHES` re-pin of
  `pr1_acceptance`.

The archive and evidence stay on the owner workstation, outside git (the PR-1A storage precedent):
`C:\Users\edufo\lilith-e19-new-build-ba943e1a188d98f4108c9eec7149c0cf1a8f68bb\`.

## 3. Derived E-19 DR-5 targets (`NEW_DR5_TARGETS`)

**Procedure.** The canonical `derive_release_swap(texts, old=OLD_RELEASE, new=NEW_RELEASE)` is applied to the
accepted W10_1 texts.

- The W10_1 texts come from `mb10_dr5_target.derive`. That derivation re-checks every pinned W9 and W10 target over
  the accepted post-M-B6 fixture `b1b3e_mb9_post_mb6_dr5_baseline.json`
  (`6620aa9e14bfa7467ce9df0a82217813e22d0110e5a949897ed199a6bf4ff168`) and the pinned DR-5 script
  (`9b569f9bee8f07f0bf13ec1d20e2607d9e01c601a2e94a2988320e5bc4160f43`).
- In each target exactly two lines move in the result set and two in the DR-5 block. Each moved line is
  `DENIED: test -w /opt/lilith-authority-dev/releases/aee323e…` becoming the same line for `ba943e1…`.
- The pre-deploy block is unchanged, and every W9 invariant still holds.

| Target (source) | Set | Lines | SHA-256 |
| --- | --- | --- | --- |
| `WITNESS_RUNNING_HELD_E19` (`WITNESS_RUNNING_HELD`) | result-set | 192 | `91c91ec7d5001d8c13f8438cb3d653ea3ee9b6bc1e41087ec154fec834def13d` |
| | dr5-block | 153 | `0692dc6df9dfbba2e6d81d985d56090025c11d2756a6397966346bb5f9e5fd16` |
| | predeploy-block | 29 | `f50870420c10149914b8d2a02116708ec89ea5a8f746a847fbe88df058f54cae` |
| `WITNESS_STATE_PRESENT_SERVICE_STOPPED_HELD_E19` (`WITNESS_STATE_PRESENT_SERVICE_STOPPED_HELD`) | result-set | 190 | `a3d07a4342296dfdf424bc2f6f74e9add141e373d2822420ff15768abb74dc9e` |
| | dr5-block | 151 | `8d25c6766b61b23517db870d5ddb5887af0e3b8fefe9b2011ced3de09ce2452f` |
| | predeploy-block | 29 | `f50870420c10149914b8d2a02116708ec89ea5a8f746a847fbe88df058f54cae` |

**Status.** The status is `NEW_DR5_TARGETS_STATUS = "DERIVED_PINNED_NOT_ACCEPTED"`.

- The targets apply only to the first deploy after U5, and only the owner accepts them.
- U1–U4 have no DR-5 target. Routine deploys stay frozen from U0.
- **No comparison maps a phase to an E-19 target yet.** `mb10_dr5_target.PHASE_TARGETS` is unchanged, so the
  routine deploy still compares against the historical W10_1 targets: `593c90e1…` / `ace51f27…` / `f5087042…`. They
  stay pinned and unchanged while `aee323e` is installed.

**Reproducibility.** The tests re-derive both targets twice and require them equal to the pins. A local run of the
same derivation over the same inputs gave the identical values (§4).

## 4. Validation

`verify_pin.py` is a local, read-only check over the attested evidence directory and this branch. Its result is
**PASS** on all 16 checks:

- `NEW_RELEASE` / `NEW_MANIFEST_SHA256` equal the attestation's `sourceCommit` / `manifestSha256`;
- the attestation digest recomputes;
- the archive, stamp and evidence-manifest digests and the archive size equal the files;
- the installer `verify_archive` accepts the archive for `NEW_RELEASE`, and its manifest digest is the pin;
- every non-wheel payload member equals this branch's source, and the wheels equal `WHEEL_HASHES`;
- the delta member is `0d2e6cca…`;
- the re-derived `NEW_DR5_TARGETS` equal the pins, with exactly 2/2/0 moved lines;
- the W10 targets are unchanged.

Tests (`services/owner-memory-control/tests`):

- `test_b1b3e_e19_release_maintenance.py`:
  - **exact pins**: NEW, the manifest, the attestation provenance and the target status;
  - **mismatch refusal**: evidence for any other NEW is refused (`OBSERVATION_RELEASES`), a missing NEW is refused
    (`NEW_RELEASE_NOT_ESTABLISHED`), and OLD, malformed or uppercase values are refused;
  - **U0–U4 under the merged pins**: `current` stays OLD through U0–U2, NEW is selected only at U3, and an early
    select under the running OLD is `STOP_MIXED`;
  - **binding guard**: no tool other than the contract names the NEW release or manifest, so no current read path
    reads NEW before the select;
  - **targets and comparison**: the pinned E-19 targets re-derive deterministically from the accepted W10 texts; the
    historical W10 targets and the `mb10_dr5_target.py` pin (`29c35961…`) are unchanged; no routine phase selects
    an E-19 target.
- `test_b1b3e_e19_maintenance_observer.py`: the pinned default refuses inputs that are not for the pinned NEW.
- `test_b1b3e_e19_transition.py`:
  - the operator defaults to the merged pins;
  - an explicitly unpinned operator is refused;
  - the pinned operator refuses a host whose evidence is for another NEW;
  - this record holds every current tool pin and target digest.
- Unchanged and passing: the stage, select and retire synthetic sequence (`PAYLOAD_DELTA` consumption) and the
  preserved custody and DR-5 contracts (`PRESERVED_PINS`).

**Updated tool pins.** The contract change moves the observer's `E19_CONTRACT_SHA256`, and the observer change moves
the operator's `TOOL_PINS[OBSERVER]`.

| Tool | SHA-256 |
| --- | --- |
| `services/owner-memory-control/tools/e19_p1b10_upgrade.py` (was `152022ee…`) | `e8c8f6037ef51d4e2f7de7ac546f034bdf4893a717ef3bcb450d9fe52cb12cc2` |
| `services/owner-memory-control/tools/e19_maintenance_observer.py` (was `1689b6ba…`; contract pin only) | `bc3017d13a222db7af7aa590a8efeaf8959f8840ffbbf9e14c69b3de1ac4a38e` |
| `services/owner-memory-control/tools/e19_operator.py` (was `4a9c4206…`; observer pin only) | `a49ed4f54b0173dd7afb9a3d2ea1836631c2dcfc1019417dcbc1209284dc5c0f` |
| `services/owner-memory-control/tools/e19_release_stages.py` (unchanged) | `77279d4546db1da85dac489ccbcbf477adc9a3f1a9fcea274fc487ff0ab0396d` |
| `services/authority-dev/ceremony/install_authority_dev.py` (unchanged) | `fe10d9a37c53d4a32ca49d79ee5987c6546866feeebcee3c882087f51ed55487` |
| `services/owner-memory-control/tools/mb10_operator.py` (unchanged, reused) | `74e1611fd067b67841029b6d2ae0189e2b2d417bc88122811bde11f3bea5042b` |

## 5. What stays OLD, and why

`CURRENT_RELEASE_BINDINGS` keep `aee323e` and its manifest `1d578ca7…`. These are `mb6_operator`, `mb9_operator`,
`mb11_*`, `mb12_pr3_material` and `mb12_readiness_inputs`.

- They describe the **installed** release.
- Re-pinning them before the U2 → U3 select would make the live host read as NEW and break routine preservation.
- They are re-pinned with the post-U5 completion record.

The E-19 operator judges each phase by its own selected release: OLD at U0, U1 and U2, NEW from U3
(`HOST_PHASES`, `release_modules`).

Also unchanged:

- the historical ceremonies (`mb4_mb5_operator`, `mb6_ledger_verifier`, `mb7_mb8_operator`);
- the M-B10 W10_1 DR-5 targets;
- HELD `c713ea1d…`, the custody pins and the ledger head.

## 6. Remaining before U0, and after

- **Before U0 (owner acts, none authorized here):**
  - merge this PR;
  - routine preservation of the merge deploy: DR-5 W10_1 EQUAL on `aee323e`, plus the focused WRB_2 / custody
    host read as after #193;
  - then the separate read-only U0 preparation (`observe`, then `render U0`).
- **Before the first post-U5 deploy (not a U0 blocker):**
  - no tool yet compares a deploy log against `NEW_DR5_TARGETS`, because `mb10_dr5_target.compare` maps only W10
    phases;
  - the completion record must add that comparison (an E-19 phase → target map) and re-pin
    `CURRENT_RELEASE_BINDINGS`.
- **Before STAGE (U1):** the owner transfers the attested archive and stamp to the fixed transfer directory, then
  runs `check` against this attestation.

## 7. State

```text
NEW_RELEASE = PINNED ba943e1 (attested; manifest b8393015…);  INSTALLED = aee323e (unchanged)
NEW_DR5_TARGETS = DERIVED_PINNED_NOT_ACCEPTED (post-U5 only);  W10_1 targets = UNCHANGED
U0 BASELINE = NOT ACCEPTED;  REPLACEMENT = NONE
LIVE_MUTATION = NONE;  DEV_CONTACT = NONE;  authorityGranted = false
```
