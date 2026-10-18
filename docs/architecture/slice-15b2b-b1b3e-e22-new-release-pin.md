# Slice 15B2b-B1b-3e M-B12 — E-22 NEW Release Pin and Derived DR-5 Target

Status:

- **REPOSITORY-ONLY PIN SLICE.** `LIVE_MUTATION = NONE`, `DEV_CONTACT = NONE`. Base: main
  `129f2bed617334be61dcac5204cd409946a7a566` (the PR #219 merge; repository validation and DEV deployment passed).
- **Owner authorization (2026-10-18): LOCAL BUILD ONLY.** Build the E-22 replacement release locally, verify that it
  reproduces, attest it, and prepare one release-pin PR. No DEV contact, upload, stage, select, unit stop or start,
  K-ACT / K-WIT load, custody change, merge or First Memory write is authorized.
- It is step 4 of Authorization 1 in the
  [E-22 judge transition](slice-15b2b-b1b3e-e22-judge-transition.md) §6.

```text
NEW attested != NEW pinned != NEW staged != NEW selected != replacements accepted != any go
DR-5 target derived + pinned != accepted != effective (post-V7 only)
```

## 1. Two identities: the release source and the pin commit

| Identity | Value | Meaning |
| --- | --- | --- |
| **NEW release** (`NEW_RELEASE`) | `129f2bed617334be61dcac5204cd409946a7a566` | The **source** commit the archive was built from. It is the archive's and manifest's `candidateSha` and the future `releases/<NEW>` directory. |
| **Pin commit** (this PR's head, later its merge) | not a release | It carries the pins and becomes the control commit of the E-22 operator runs. It is never built or installed. |

This PR changes no release payload source. It edits only control tooling, tests and documents. None of these is a
member of `release_file_set.py`'s payload.

## 2. The pins (`services/owner-memory-control/tools/e22_judge_upgrade.py`)

| Constant | Value |
| --- | --- |
| `NEW_RELEASE` | `129f2bed617334be61dcac5204cd409946a7a566` |
| `NEW_MANIFEST_SHA256` | `fc7dbf08bb5b8260716a762fd2fbccdb44fbf0e438e2e21d0cfddcd6f1a3348a` |
| `OLD_RELEASE` (unchanged; still installed) | `ba943e1a188d98f4108c9eec7149c0cf1a8f68bb` |
| `OLD_MANIFEST_SHA256` (unchanged) | `b8393015e505495a81629411a4ecd33c0c372c7b16d2761094eb4e018bc300a2` |

`NEW_RELEASE_ATTESTATION` holds the build provenance. It is a record only. `e22-stage` verifies the archive against
its builder stamp (installer `verify_archive`), against `NEW_MANIFEST_SHA256`, and against the one-member delta.

| Field | Value |
| --- | --- |
| `archiveSha256` | `baa317262896061626e6bf17151c95eea990beb01b707ffbabb7f68f3465daab` |
| `archiveByteSize` | `5356341` |
| `builderStampSha256` | `2c6f36ec13df2a8781821671d1ede5db9af2f1a709e8b57c6ab93565789efaaa` |
| `attestationDigest` (`LILITH_PR1A_BUILD_ATTESTATION_V1\0`) | `bc7ca22f820ed8684c74fb0333a161f64e91ebbf1d18e56524294c3afa9d7fde` |
| `buildRecipeSha256` | `3ff8ce72da5fba99db4546ff66ac238c042abe784fbe949aaef7ac9394e75b54` |
| `authorityReleaseDigest` | `cfb6db8f8461f68f903141acdd4729d232dfb528d13d8bddcf9683dc8ded9d8d` |
| `identitySha256` (BUILD_A = BUILD_B) | `aaf183ac4cf7ce28ae1354fc4428e2152f1de9bf1482784f6778f8bf871c9b17` |
| `evidenceManifestSha256` | `caa63c9bc63d3990f2dee81288e1db56f56e757fcb95f083c1c336cd863e1670` |

The recipe digest differs from E-19 (`aa1c5200…`) only through `release_file_set.py` (`bcb5e02f…`). Its
`SHARED_HASHES` pins the OD-M12-10 judge. The builder (`4b1ebff8…`), the installer (`fe10d9a3…`) and the witness file
set (`cd831bf0…`) are byte-identical to E-19.

**Pin chain.** The contract bytes moved, so the operator re-pins it: `e22_operator.TOOL_PINS[CONTRACT]` =
`505966d4c065a07ab53d7b9a16875b301a04525032ac5b553f8f216f20d21ec9`. Every other tool pin is unchanged.
`e22_release_stages.py` reads the pins at call time, so it now refuses any other NEW release or manifest.

## 3. Build, reproduction and attestation (the E-19 process, unchanged tools)

Evidence: `C:\Users\edufo\lilith-e22-new-build-129f2bed617334be61dcac5204cd409946a7a566\` (`EVIDENCE-SHA256SUMS`
`caa63c9b…`, 69 files; `candidate/PROVENANCE.txt`). BUILD_B's tree is also kept in WSL at
`/root/lilith-e22-new-build-<SHA>/build-b`.

| Step | Result |
| --- | --- |
| BUILD_A | Windows 11, CPython 3.13.5, zlib 1.3.1. Fresh `git clone --no-hardlinks`, detached at the source, `core.autocrlf=false`. rc 0 |
| BUILD_B | WSL Ubuntu 24.04.5, CPython 3.12.3, zlib 1.3. Fresh repo fetched from a git bundle of `origin/main`. `env -i PATH=/usr/bin:/bin LANG=C.UTF-8 python3 -I -B`. rc 0 |
| Wheelhouse | the 5 pinned wheels from the E-19 build, each OK against `install_authority_dev.WHEEL_HASHES`, in both builds |
| Archives | byte-identical: `baa31726…`, 5,356,341 B, manifest `fc7dbf08…` |
| `inspect` A / B | rc 0 / 0, identity `aaf183ac…` both |
| `attest` | `REPRODUCED`, digest `bc7ca22f…` |
| `check` | PASS for the A and B archives on Windows; PASS independently in WSL against BUILD_B's own source and archive |
| `e22_judge_upgrade.py check-build` (vs the E-19 `build-a/inspection-a.json`) | PASS for A and B. The delta is exactly `lilith_owner_memory/pr1_acceptance.py` `0d2e6cca…` → `d3df4cfc…` |

Two transcript-only incidents are retained in the evidence. Neither produced a build:

1. The first BUILD_B clone from the bundle was empty (the bundle carries `refs/remotes/origin/main`). It is kept
   under `attempts/`; the ref was then fetched explicitly.
2. The first Windows `check` omitted the required `--source-root` (a usage error, rc 2). It is kept as
   `check-*-attempt1-*`.

## 4. Derived W11 DR-5 target (`NEW_DR5_TARGETS`)

There is exactly one target, for the post-V7 state: signer and witness running from NEW, HELD unchanged. It is the
M-B11 `SIGNER_RUNNING_WITNESS_RUNNING_HELD` texts (`mb11_dr5_target.py`, pinned, unchanged) moved from OLD to NEW by
the E-19 contract's `derive_release_swap` (2 / 2 / 0 release lines). V1 … V6 have two releases or a stopped unit, so
they have **no** target.

| Target | result-set | dr5-block | predeploy-block |
| --- | --- | --- | --- |
| `SIGNER_RUNNING_WITNESS_RUNNING_HELD_E22` | 194 / `a0ebd54d75f3f453970957454b00baf6767e64a8bb910f02344fbc72b46104ed` | 155 / `7fe21378bb97f57aed3a6c60f6fc216e08d646f9da42d9c35feb7509f5468f1c` | 29 / `f50870420c10149914b8d2a02116708ec89ea5a8f746a847fbe88df058f54cae` |

The target is `DERIVED_PINNED_NOT_ACCEPTED`. No routine compare selects it yet: `mb11_dr5_target.PHASE_TARGETS` is
unchanged. Wiring it in is part of the post-V7 re-pin, with the completion record (the E-19 precedent).

## 5. What stays OLD, and why (readiness and the `post-signer` envelope)

The installed-release bindings describe the release that is **installed**. These are readiness `DEV_PINS`, PR-3
`DEV_EXPECTED`, `mb11_signer_verifier.RELEASE_SHA` / `RELEASE_CWD`, `mb11_restart_boundary_install.RELEASE_SHA`, and
the `mb11_dr5_target` phase map. They stay on `ba943e1` while it is installed. Pinning NEW now would make the live
host read as NEW before the select. They are re-pinned after V7 with the completion record, as for E-19
(`e19_p1b10_upgrade.CURRENT_RELEASE_BINDINGS`).

The `post-signer` envelope does **not** need a re-pin:

- At V6 the W11 readiness judgement needs E READY and F to be exactly the hold reason. Neither depends on the
  envelope's `releaseSha`: the verifier passes it only to the successor-ceremony check, which is not on this path.
  The PR-1 package's installed-release reasons are recorded, never judged in W11.
- The W11 release working directory is set to the phase's release by `e22_transition_remote`.

So `post-witness` and `post-signer` use the bound M-B11 readiness envelope. A re-pinned envelope belongs to the post-V7
M-B12 recollection.

## 6. Validation

- `tests/test_b1b3e_e22_judge_transition.py` asserts the pins and attestation values, re-derives the DR-5 target from
  the accepted texts, and checks this record. The build gate runs with the pinned NEW source.
- `tests/test_b1b3e_e22_release_stages.py`: the synthetic stage runs use synthetic pins, and `PinnedReleaseTests`
  shows the merged pins refuse any other release or manifest.
- `tests/test_b1b3e_e22_operator.py`: the default operator carries the merged pins; `None` still refuses every DEV
  form.

## 7. State

```text
LIVE_MUTATION = NONE;  DEV_CONTACT = NONE;  INSTALLED = ba943e1 (E-19 U5);  NEW = 129f2be ATTESTED + PINNED (not staged)
NEW_DR5_TARGETS = DERIVED_PINNED_NOT_ACCEPTED (post-V7 only)
LIVE SWAP (Authorization 2) = NOT AUTHORIZED;  E-22 = BLOCKED;  M-B12 = NOT PASSED;  CUSTODY = HELD;  K-ACT LOAD COUNT = 1
```
