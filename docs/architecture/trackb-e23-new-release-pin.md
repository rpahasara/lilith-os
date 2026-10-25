# Track B E-23 — NEW Release Pin (owner decision record)

Status:

- **PROPOSED — NOT APPROVED.** This record and the pins it names take effect only when the owner reviews and merges
  it. Until then the E-23 contract's NEW pin is a proposal, not an authorization.
- **REPOSITORY-ONLY PIN SLICE.** `LIVE_MUTATION = NONE`, `DEV_CONTACT = NONE`. Base: main
  `57bff671fbfe5df4e59248d5d69338dc0ba05846` (the PR #251 merge; DEV Core API deployment `40195829050` passed;
  post-deploy F9c2 preservation check PASS).
- **Owner authorization (2026-10-25): OFFLINE RELEASE PREPARATION ONLY.** Build the real E-23 authority release from
  the merged commit with the existing builder and attestation tooling, verify it against the E-23 contract, and
  prepare one local pin proposal. No push, PR, merge, DEV/PROD contact, K-PAN/K-PCK operation, witness or authority
  service operation, stage, select or retire is authorized.

```text
NEW attested != NEW pinned (this record, once merged) != NEW staged != NEW selected != OLD retired != any go
```

## 1. Two identities: the release source and the pin commit

| Identity | Value | Meaning |
| --- | --- | --- |
| **NEW release** (`NEW_RELEASE`) | `57bff671fbfe5df4e59248d5d69338dc0ba05846` | The **source** commit the archive was built from. It is the archive's and manifest's `candidateSha`. |
| **Pin commit** (this change, later its merge) | not a release | It carries the pins. It is never built or installed. |

This change edits only the E-23 contract module, its test and this record. None is a member of
`release_file_set.py`'s payload, and `e23_privacy_anchor_upgrade.py` is not pinned by any tool, so nothing cascades.

## 2. The pins (`services/owner-memory-control/tools/e23_privacy_anchor_upgrade.py`)

| Constant | Value |
| --- | --- |
| `NEW_RELEASE` | `57bff671fbfe5df4e59248d5d69338dc0ba05846` |
| `NEW_MANIFEST_SHA256` | `fc29a23cbb411704f2799b418f8c7fd7fadf215489174e9ac9d370db2e78368c` |
| `OLD_RELEASE` (unchanged; still installed on DEV) | `129f2bed617334be61dcac5204cd409946a7a566` |
| `OLD_MANIFEST_SHA256` (unchanged) | `fc7dbf08bb5b8260716a762fd2fbccdb44fbf0e438e2e21d0cfddcd6f1a3348a` |

`NEW_RELEASE_ATTESTATION` holds the build provenance. It is a record only.

| Field | Value |
| --- | --- |
| `archiveSha256` | `a8cadbfa75023ed19c6939b17841e56f1ad9d0b83a6f854755621e32ed174486` |
| `archiveByteSize` | `5367662` |
| `builderStampSha256` | `3972c9a7f899df0e7c1d0cad2d52d267cb2e4decefd876ea17c3f63b05fed32e` |
| `attestationDigest` | `3f18fd50f0269c1e72e537e996b2a38de8369b0ed4da6150ee597cd5299f4b90` |
| `buildRecipeSha256` | `5e687a8e06d6c937a6ac088c055d603d581000cf413fe8d2a42a4c813a580130` |
| `authorityReleaseDigest` | `4475c3c408571a7cba0a0f705c360ae1a6df02486a7d32c710531a8fd2ed16b7` |
| `recoveryWitnessReleaseDigest` | `c911b7334d97dfe3b9246832d5301a830771e3f41c3b2d6d86867519de16c2be` |
| `identitySha256` (BUILD_A = BUILD_B) | `409874ff7c5e216b613f0bf649ea66443c1ec81f52b8f69277c8e0f1ef45f40e` |
| `evidenceManifestSha256` | `3ca5bbe1a2e24a5d24fd29fde4c297e26c7438869760ac53052206ba2d15ff68` |

The build recipe includes the versioned installer `install_authority_dev_v2.py` (`cf995dd1…`). The original
`install_authority_dev.py` is byte-identical (`fe10d9a3…`, unchanged since `129f2be`).

## 3. Build, reproduction, attestation and delta (existing tools, unchanged)

Evidence: `C:\Users\edufo\lilith-e23-new-build-57bff671fbfe5df4e59248d5d69338dc0ba05846\` (`EVIDENCE-SHA256SUMS`
`3ca5bbe1…`; `candidate/PROVENANCE.txt`). BUILD_B's tree is also kept in WSL at
`/root/lilith-e23-new-build-<SHA>/build-b`.

| Step | Result |
| --- | --- |
| BUILD_A | Windows 11, CPython 3.13.5. Fresh `git clone --no-hardlinks`, detached at the source, `core.autocrlf=false`. rc 0 |
| BUILD_B | WSL Ubuntu 24.04, CPython 3.12.3. Fresh repo fetched from a git bundle of `origin/main` (= the source). `env -i PATH=/usr/bin:/bin LANG=C.UTF-8 python3 -I -B`. rc 0 |
| Wheelhouse | the 5 pinned wheels from the E-22 build, each OK against `install_authority_dev.WHEEL_HASHES` |
| Archives | byte-identical: `a8cadbfa…`, 5,367,662 B, manifest `fc29a23c…`, builder stamp `3972c9a7…` |
| `inspect` A / B | rc 0 / 0, identity `409874ff…` both |
| `attest` | `REPRODUCED`, digest `3f18fd50…` |
| `check` | PASS for the A and B archives on Windows; PASS independently in WSL against BUILD_B's own source and archive |
| `install_authority_dev_v2.verify_archive` | PASS |
| E-23 `check_payload` (vs the installed E-22 archive `baa31726…` / manifest `fc7dbf08…`) | PASS |

**Delta from the installed E-22 archive** (66 → 68 members):

| Member | Change |
| --- | --- |
| `lilith_recovery_witness/credential.py` | `7a394b56…` → `68da7a17…` |
| `lilith_recovery_witness/server.py` | `1d709a17…` → `6bb19ffb…` |
| `assets/lilith-recovery-witness.service` | `9f78130c…` → `b3e2c753…` |
| `assets/lilith-recovery-witness.tmpfiles.conf` | `c3491d51…` → `9fd8a2ec…` |
| `lilith_recovery_witness/privacy_anchor.py` | added `9d7d7c37…` |
| `lilith_memory/privacy_anchor_contracts.py` | added `58e954af…` |
| `release-manifest.json` | `fc7dbf08…` → `fc29a23c…` (its only non-`files` change is `candidateSha`) |

Nothing was removed. The other 61 pre-existing members are byte-identical, including the 11 authority signer modules,
the 6 CLIs, the 5 wheels, `requirements.lock` and the 5 other units/tmpfiles.

The earlier rehearsal build (local commit `4d8e0806…`, archive `6692bb5e…`) differs from this archive only in
`release-manifest.json`, and there only in `candidateSha`. The rehearsal is not the release.

## 4. What stays OLD

The installed-release bindings describe the release that is **installed**: the M-B6 module pins, the E-19
restart-boundary unit fragment `9f78130c`, and `OLD_RELEASE` / `OLD_MANIFEST_SHA256`. They stay on `129f2be` until the
transition completes (the E-22 practice). No E-19 / E-22 historical record, pin, go text or past authorization is
changed.

## 5. Validation

`services/owner-memory-control/tests/test_trackb_e23_contract.py` asserts the pins and attestation values, proves that
the pinned NEW source (`git show NEW_RELEASE:…`) is the installed payload moved by exactly the contract delta, and
checks that this record names every pin and is marked PROPOSED — NOT APPROVED.

## 6. State

```text
LIVE_MUTATION = NONE;  DEV_CONTACT = NONE;  INSTALLED = 129f2be (E-22 V7);  NEW = 57bff67 ATTESTED, pin PROPOSED (not merged, not staged)
K-PAN = NOT GENERATED / NOT INSTALLED;  E-23 LIVE LADDER = NOT WRITTEN / NOT AUTHORIZED
```
