# Slice 15B2b-B1b-3e — M-B3 / SIGN_REGISTRY_V1: Final Package Pins (Post-Merge Finalization Record)

Status:

- **`M-B3 PACKAGE STATUS = REVIEWED / MERGED / FINALIZED FOR PREPARATION-SEQUENCE CONSIDERATION`.**
  The [M-B3 registry ceremony package](slice-15b2b-b1b3e-mb3-registry-ceremony-package.md)
  was reviewed and merged (PR #153). This record pins the **final** bundle,
  built from the exact merged control commit, and re-confirms the phone-script
  pin there. It follows the
  [M-B1 finalization precedent](slice-15b2b-b1b3e-mb1-final-package-pins.md).
- These pins are what a future owner M-B3 go must name. The pins are final
  for this control commit; this record itself is reviewed when merged.
- **M-B3 is NOT AUTHORIZED.** No M-B3 preparation sequence, no PREPARE on the
  S25, and no `SIGN_REGISTRY_V1` is authorized. `REGISTRY_SIGNED` is not
  reached.
- Local / repository-only. No DEV, GCP, S25 or replica contact. No K-ROOT or
  K-WIT access. No real K-ACT publication, candidate manifest, `epochRandom`,
  `issuedAt` or registry exists. No simulation ran for this record, so no new
  identity exists to burn.

```text
package reviewed       != package transferred
package finalized      != M-B3 preparation authorized
M-B3 preparation       != signing go
PREPARE                != SIGN
candidate manifest     != authority
SIGN_REGISTRY_V1 execution != owner acceptance
REGISTRY_SIGNED        != registry effective
```

## 1. Control point

| Item | Value |
| --- | --- |
| **control commit** | `1f544e695742fd4a93fcf4fd8dc5d706e24eb452`: the merge of PR #153 into `main` (parent `14fbe03`). It is `SOURCE_COMMIT` inside the bundle |
| historical post-merge repository validation | GitHub Actions run `37452396528` = **SUCCESS** |
| historical post-merge DEV deployment | GitHub Actions run `37452579297` = **SUCCESS** |
| finalized | `2026-10-06T11:09:12Z` (UTC) |

The two runs are **historical post-merge evidence only.** They do **not**
establish M-B3 freshness or currentness, and they do **not** replace the fresh
read-only gates of a future owner-authorized M-B3 preparation sequence
([decision](slice-15b2b-b1b3e-mb3-signing-continuity-owner-decision.md) D-2;
[package](slice-15b2b-b1b3e-mb3-registry-ceremony-package.md) §5). Run
`37452579297` is itself a DEV deployment: a future sequence's K-ACT / host
re-proof happens after it, and any later applicable deployment is
terminator M3-T1.

## 2. Final pins

| Item | Value |
| --- | --- |
| bundle | `lilith-mb3-registry-1f544e6.tar` |
| **bundle SHA-256** | `fce71811073eeb98ce82b5db60dcefb5b7abb12119ed609d35a055bee7360cb0` |
| bundle size | **1454080** bytes |
| top directory | `lilith-mb3-registry-1f544e6/` |
| files | **75** = 17 M-B1 closure sources + `tools/mb3_registry_ceremony.py` + 55 vendor files + `SOURCE_COMMIT` + `SHA256SUMS` (plus 19 directory entries) |
| `SHA256SUMS` (inside the bundle) | `0e3fa7cde854ed08e9826cf175c1d13bdb215bd6a9c664a75390ce6bbad0a18f`; verifies **74 / 74** other members |
| `SOURCE_COMMIT` | `1f544e695742fd4a93fcf4fd8dc5d706e24eb452` plus one newline |
| **phone script** | `mb3_phone_ceremony.py`, **SHA-256 `db02909d8f769f5a0570386aef55c3a472bdbc6c52949830ab94c1b624e6bd54`**, 30931 bytes; re-confirmed from the `1f544e6` blob; outside the bundle |
| bundled library | `services/owner-memory-control/tools/mb3_registry_ceremony.py`, SHA-256 `c77b651ca2ae9d5f6c5526f958469a01c0d42e6ebdf189fc206ac2132af61320` |
| builder | `services/owner-memory-control/tools/build_mb3_registry_bundle.py`, SHA-256 `7f90d3ed05c370735f330805ae2a16b68598b77a8901a9ad492719774bad7293` |
| laptop verifier | `services/owner-memory-control/tools/verify_mb3_registry.py`, SHA-256 `e710cfa623d494e243ab4a1fbaefe28e8d079e58398368f9dcabd645e06b5507` |
| laptop staging | `%USERPROFILE%\lilith-mb3-package\`: the tar, the script, and `STAGING.sha256` (outside every Git tree) |

**Unlike M-B1, the phone script needs no pin substitution.** It takes the
control SHA, bundle SHA-256 and manifest SHA-256 as arguments that the go
names, so its merged bytes are final. The merged script, library, builder and
verifier are byte-identical to the reviewed pre-merge pins.

A future owner M-B3 go (package §8) names **bundle `fce71811…0cb0`** and
**script `db02909d…bd54`**, together with the live-sequence values that do not
exist yet: the K-ACT publication SHA-256, the manifest SHA-256,
`epochRandom`, `issuedAt` and the expected registry digest.

## 3. How the pins were produced

All of it ran locally, offline, with no key material.

1. The control worktree had `HEAD` = `origin/main` = `1f544e6` and an empty
   `git status`. The merge's diff from `14fbe03` is exactly the 11 reviewed
   files (3259 insertions, 1 deletion).
2. **The vendor set** came from the verified M-B1 bundle
   `lilith-mb1-kroot-1e2eae3.tar` (`7f07e158…c2c1`, local staging). Its own
   `SHA256SUMS` (`4816f8c9…6498`) was re-verified for all 73 members first.
   That gives 55 files: `fido2` 2.2.1 and `rfc8785` 0.1.4, with their
   dist-info.
3. **Two independent local clones**, each detached at `1f544e6` with an empty
   `git status`. The merged builder was run once in each:
   `build_mb3_registry_bundle.py --repo . --commit 1f544e6… --vendor-dir … --out …`.
   Both printed the same `tarSha256`, `sha256sumsSha256`, `files=75`,
   `sourceCommit` and `phoneScriptSha256`.
   - The first attempt, from clones under a deep temporary path, was refused
     with `SOURCE_NOT_AT_COMMIT`. This was environmental: Windows `MAX_PATH`
     on git's path check of `<sha>:<path>`. The builder was not changed. The
     clones were recreated under `%USERPROFILE%\lilith-mb3-fin\`.
4. **A third build on Linux** (WSL Ubuntu 24.04, Python 3.12), from a git
   bundle of the same commit, used the same vendor set.
5. **Contents check:**
   - every member is a regular file or a directory, with mtime 0, owner 0:0,
     empty user and group names, and modes 0644 / 0755;
   - `SOURCE_COMMIT` = the control commit;
   - `SHA256SUMS` verifies 74 / 74, and the file set is exactly the listed
     names plus `SHA256SUMS`;
   - all 18 source members equal `git show 1f544e6:<path>`;
   - no member name suggests key material, a public input, a manifest, a
     signed registry or the phone script;
   - no PEM private-key header. Generic substrings (`BEGIN IMMEDIATE`,
     enum constants, `LoadCredentialEncrypted`) occur only in bundled code;
   - the accepted public fingerprints occur only in the library;
   - the tar's own SHA-256 is not inside it.
6. **Against the M-B1 bundle:** the only added member is the library. Of the
   shared members, only `SOURCE_COMMIT` and `SHA256SUMS` differ, so all 17
   M-B1 sources and all 55 vendor files are byte-identical.
7. **Loaded from inside the final bundle** (Linux; only `cryptography` from
   the pinned deps):
   - `burned_identities` and `rfc8785` resolve to the bundle;
   - the canonical burned set is 20;
   - every burned registry and genesis digest (6 / 6) is refused by
     `burned_identity`; the 14 burned public-key fingerprints are present in
     the set (their raw keys are not available, so they were not re-derived);
   - the library's `ACCEPTED` E-21 and K-WIT values, `policyVersion` and
     continuity are as recorded;
   - the bundled owner tool loads with root keyId
     `test-only.registry-root.dev-synthetic.b1b3d.1`.

## 4. Reproducibility

The reviewed design promises archive-level determinism. The builder docstring
specifies sorted names, mtime 0, owner 0:0 and fixed modes; the package test
`test_bundle_is_deterministic_public_only_and_never_self_hashed` checks it.

| Build | Platform | tar SHA-256 | size | `SHA256SUMS` | member list |
| --- | --- | --- | --- | --- | --- |
| A | Windows 11, Python 3.13, clone A | `fce71811…0cb0` | 1454080 | `0e3fa7cd…a18f` | 75 files |
| B | Windows 11, Python 3.13, clone B | `fce71811…0cb0` | 1454080 | `0e3fa7cd…a18f` | 75 files |
| C | WSL Ubuntu 24.04, Python 3.12, git-bundle clone | `fce71811…0cb0` | 1454080 (byte-identical) | `0e3fa7cd…a18f` | 75 files |

**A, B and C are byte-identical** (`cmp`). Result:
`MB3_BUNDLE_REPRODUCIBLE_BYTE_IDENTICAL` (3 / 3, two platforms).

## 5. Validation (from the merged tree; local only)

Run in WSL Ubuntu 24.04 (Python 3.12, pinned deps) on a git clone of
`1f544e6`, with full history:

| Suite | Result |
| --- | --- |
| M-B3 package + signing-continuity tests | 51 OK |
| M-B2 semantic tests | 36 OK |
| M-B1 tests (package, finalization, completion, continuity, carry-forward) | 66 OK |
| P3-5 sequencing; authority registry contracts | 19 OK; 35 OK |
| **full owner-memory-control** | **884 OK, 0 skipped** (the git-dependent tests ran) |
| authority-dev | 241 OK |
| `services/authority-dev/release_file_set.py` | exit 0 |
| `scripts/validate_repository.py` | passed (216 Markdown files) |

## 6. Package boundaries (unchanged)

- **Public-only.** The bundle holds reviewed source, the vendor set,
  `SOURCE_COMMIT` and `SHA256SUMS`. It holds no K-ROOT private material, no
  passphrase material, no K-WIT credential, no real K-ACT publication, no
  candidate manifest, no live `epochRandom` or `issuedAt`, and no signed
  registry.
- The phone script stays outside the bundle and is pinned separately. The
  bundle SHA-256 is recorded here, outside the bundle.
- The `registry-v1` signer, sequencer, keygen, installer, release file set
  and workflows are unchanged.
- The preparation-sequence runbook, PREPARE / SIGN, verification, export
  allowlists, burn handling and owner-acceptance template are those of the
  [package record](slice-15b2b-b1b3e-mb3-registry-ceremony-package.md) §5–§14.
  Its step 1 ("finalization pins recorded") is satisfied when this record is
  merged. Its step 8 ("build or re-verify the bundle against the finalization
  pins") uses §2 here.

## 7. What this record does not do

- It does not authorize an M-B3 preparation sequence, PREPARE, or
  `SIGN_REGISTRY_V1`, and it issues no M-B3 command.
- It does not transfer anything to the S25.
- It does not fetch the K-ACT publication, run DR-5 or PR-2, or contact DEV,
  GCP, the S25 or a replica.
- It creates no candidate, manifest, `epochRandom`, `issuedAt`, signature or
  registry, and records no burn.

## 8. State

```text
M-B3 PACKAGE STATUS = REVIEWED / MERGED / FINALIZED FOR PREPARATION-SEQUENCE CONSIDERATION
CONTROL 1f544e695742fd4a93fcf4fd8dc5d706e24eb452
BUNDLE lilith-mb3-registry-1f544e6.tar fce71811073eeb98ce82b5db60dcefb5b7abb12119ed609d35a055bee7360cb0 (1454080 BYTES, 75 FILES)
SHA256SUMS 0e3fa7cde854ed08e9826cf175c1d13bdb215bd6a9c664a75390ce6bbad0a18f
PHONE SCRIPT db02909d8f769f5a0570386aef55c3a472bdbc6c52949830ab94c1b624e6bd54
MB3_BUNDLE_REPRODUCIBLE_BYTE_IDENTICAL
HISTORICAL RUNS 37452396528 / 37452579297 = SUCCESS; NOT FRESHNESS; NOT CURRENTNESS
M-B1 / GENERATE_K_ROOT = COMPLETED / ACCEPTED
M-B2 / GENERATE_K_WIT = COMPLETED / ACCEPTED
M-B3 PREPARATION SEQUENCE = NOT AUTHORIZED
M-B3 PREPARE ON S25 = NOT AUTHORIZED
M-B3 / SIGN_REGISTRY_V1 = NOT AUTHORIZED
REGISTRY_SIGNED = NOT REACHED
M-B4/M-B5 / INSTALL_TRUST_AND_REGISTRY = NOT AUTHORIZED
REGISTRY EFFECTIVENESS = NOT AUTHORIZED
GENESIS = NOT AUTHORIZED
RECORD 1 = NOT AUTHORIZED
FIRST MEMORY = NOT AUTHORIZED
PROD = NOT AUTHORIZED
FRESHNESS=UNKNOWN
NO LIVE SYSTEM CONTACTED; NO K-ROOT OR K-WIT ACCESS; NOTHING SIGNED
```
