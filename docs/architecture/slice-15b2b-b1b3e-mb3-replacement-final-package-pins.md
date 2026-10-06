# Slice 15B2b-B1b-3e — M-B3 / SIGN_REGISTRY_V1: Replacement Package Final Pins (Post-Incident Finalization Record)

Status:

- **`M-B3 REPLACEMENT PACKAGE STATUS = REVIEWED FIX / MERGED / FINALIZED FOR NEW PREPARATION-SEQUENCE CONSIDERATION`.**
  - The [attempt-1 incident fix](slice-15b2b-b1b3e-mb3-sign-attempt1-incident.md)
    was reviewed and merged (PR #155).
  - This record pins the **replacement** bundle, built from the exact merged
    commit, and the corrected phone script.
  - It follows the
    [first finalization](slice-15b2b-b1b3e-mb3-final-package-pins.md) and the
    [M-B1 precedent](slice-15b2b-b1b3e-mb1-final-package-pins.md).
- **Finalized, not transferred.** Nothing was sent to the S25.
- **Nothing is authorized.** This record authorizes no:
  - phone incident disposition;
  - replacement M-B3 preparation sequence;
  - PREPARE;
  - `SIGN_REGISTRY_V1`.

  `REGISTRY_SIGNED` is not reached.
- Local / repository-only:
  - no DEV, GCP, S25 or replica contact;
  - no K-ROOT or private K-WIT access;
  - no real K-ACT publication, candidate, `epochRandom`, `issuedAt` or
    signature.

  No live simulation ran. The real-terminal tests use throwaway TEST keys
  only.

```text
package reviewed       != package transferred
package finalized      != M-B3 preparation authorized
M-B3 preparation       != signing go
PREPARE                != SIGN
candidate manifest     != authority
SIGN_REGISTRY_V1 execution != owner acceptance
REGISTRY_SIGNED        != registry effective
```

## 1. History (preserved; not rewritten)

| Item | State |
| --- | --- |
| attempt-1 package: bundle `lilith-mb3-registry-1f544e6.tar` `fce71811073eeb98ce82b5db60dcefb5b7abb12119ed609d35a055bee7360cb0`, source `1f544e6` | **historical / superseded for future attempts** |
| attempt-1 phone script `db02909d8f769f5a0570386aef55c3a472bdbc6c52949830ab94c1b624e6bd54` | **historical / superseded** (the `_tty_confirm` "r+" defect) |
| attempt-1 candidate `b7e24530a21757a5bef996ec9adb13ed5932ab04edb1943321f529e3206c0e53` | **`HISTORICAL_ABANDONED_UNSIGNED_CANDIDATE`**: not burned, not reusable |
| M-B3 SIGN attempt 1 | `CLOSED / INCIDENT / A_NO_SIGNATURE`: signer not invoked, `NO_REAL_REGISTRY_BURN`, sequence ENDED, go CONSUMED |

## 2. Control point

| Item | Value |
| --- | --- |
| **package source commit** | `f9fb9e14dc6a14ac796379938d3092f6214194cb`: the merge of PR #155 into `main` (parents `a86d032`, `304ee9d`). It is `SOURCE_COMMIT` inside the bundle |
| historical post-merge repository validation | GitHub Actions run `37466905265` = **SUCCESS** |
| historical post-merge DEV deployment | GitHub Actions run `37467113188` = **SUCCESS** |
| finalized | `2026-10-06T13:08:53Z` (UTC) |

**The two runs are historical evidence only.**

- They do **not** establish freshness or currentness for any future M-B3
  sequence.
- They do **not** replace that sequence's fresh read-only gates
  ([decision](slice-15b2b-b1b3e-mb3-signing-continuity-owner-decision.md) D-2,
  [package](slice-15b2b-b1b3e-mb3-registry-ceremony-package.md) §5).
- Run `37467113188` is a DEV deployment, so a future sequence's K-ACT / host
  re-proof must follow it.

**Drift check, from `1f544e6` to `f9fb9e1`:**

- **The only code change** is the reviewed `_tty_confirm` correction in
  `mb3_phone_ceremony.py`: separate write-only and read-only `/dev/tty`
  handles. Everything else in the diff is documentation and tests.
- **Unchanged**, by `git diff` of 0 files:
  - the `registry-v1` signer and owner tool, canonicalization, the authority
    contracts, and K-ROOT / K-WIT semantics;
  - `mb3_registry_ceremony.py`;
  - the builders (`build_mb3_registry_bundle.py`, plus the M-B1 and B-4
    primitives they load);
  - the laptop verifier;
  - all of `services/authority-dev`, `services/core-api` and
    `lilith_owner_memory`.
- The merged script, incident test and incident record are byte-identical to
  the reviewed versions.

## 3. Final replacement pins

| Item | Value |
| --- | --- |
| bundle | `lilith-mb3-registry-f9fb9e1.tar` |
| **bundle SHA-256** | `ad37758ebf892e773a7019cb2c084d4d30920e34fb5318ba9f82999f48ffa736` |
| bundle size | **1454080** bytes |
| top directory | `lilith-mb3-registry-f9fb9e1/` |
| files / directories | **75** files (17 M-B1 closure sources + `tools/mb3_registry_ceremony.py` + 55 vendor files + `SOURCE_COMMIT` + `SHA256SUMS`) / **19** directories |
| `SHA256SUMS` (inside the bundle) | `58eb1b8269f8a54dd4153d1bde68f1bf1440cb7d52459081f81884599240f683`; verifies **74 / 74** other members |
| `SOURCE_COMMIT` | `f9fb9e14dc6a14ac796379938d3092f6214194cb` plus one newline |
| **corrected phone script** | `mb3_phone_ceremony.py`, **SHA-256 `b58b93215dc5c1e724846c7fc16acc2c29d81725a2ba13badcdccfd7b9eaecc7`**, 31161 bytes. Recomputed from the `f9fb9e1` blob; equal to the pre-merge value; **differs from `db02909d…`**; outside the bundle |
| bundled library | `services/owner-memory-control/tools/mb3_registry_ceremony.py`, SHA-256 `c77b651ca2ae9d5f6c5526f958469a01c0d42e6ebdf189fc206ac2132af61320` (unchanged) |
| builder | `services/owner-memory-control/tools/build_mb3_registry_bundle.py`, SHA-256 `7f90d3ed05c370735f330805ae2a16b68598b77a8901a9ad492719774bad7293` (unchanged) |
| laptop verifier | `services/owner-memory-control/tools/verify_mb3_registry.py`, SHA-256 `e710cfa623d494e243ab4a1fbaefe28e8d079e58398368f9dcabd645e06b5507` (unchanged) |
| laptop staging (not a transfer set) | `%USERPROFILE%\lilith-mb3r-package\`: the tar, the script and `STAGING.sha256`, outside every Git tree |

**Against the attempt-1 bundle `fce71811…`:**

- The member set is identical.
- Only `SOURCE_COMMIT` and `SHA256SUMS` differ.
- All 17 sources, the library and all 55 vendor files are byte-identical.

**A future owner M-B3 go must name:**

- **bundle `ad37758e…a736`**;
- **script `b58b9321…ecc7`**;
- package source `f9fb9e1`;
- the live values of the new sequence, none of which exists yet:
  - the K-ACT publication SHA-256;
  - the new manifest SHA-256;
  - `epochRandom`;
  - `issuedAt`;
  - the expected digest.

**Do not use** for any future attempt:

- the attempt-1 transfer folder `%USERPROFILE%\lilith-mb3-transfer\`. It holds
  the attempt-1 script `db02909d…` under the **same filename**;
- the attempt-1 staging `%USERPROFILE%\lilith-mb3-package\`.

A new sequence builds a fresh transfer set from §3.

## 4. How the pins were produced

All of it ran locally and offline, with no key material.

1. **Vendor set.**
   - Taken from the verified M-B1 bundle `lilith-mb1-kroot-1e2eae3.tar`
     (`7f07e158…c2c1`).
   - Its `SHA256SUMS` (`4816f8c9…6498`) was re-verified for all 73 members
     first.
   - That gives the same 55 files (`fido2` 2.2.1, `rfc8785` 0.1.4) as both
     earlier bundles.
2. **Two independent local Windows clones** were made, each detached at
   `f9fb9e1` with an empty `git status`, under the short path
   `%USERPROFILE%\lilith-mb3r-fin\`, which avoids the `MAX_PATH` issue in the
   first finalization.
3. The merged builder ran once in each clone:
   `build_mb3_registry_bundle.py --repo . --commit f9fb9e14… --vendor-dir … --out …`.
4. **A third build on Linux** (WSL Ubuntu 24.04, Python 3.12) used a
   full-history git bundle of `f9fb9e1` and the same vendor set.
5. **Contents check:**
   - every member is a regular file or a directory, with mtime 0, owner 0:0,
     empty names and modes 0644 / 0755;
   - `SOURCE_COMMIT` = the control commit;
   - `SHA256SUMS` verifies 74 / 74, and the file set is exact;
   - all 18 source members equal `git show f9fb9e1:<path>`;
   - there is no key-like, input-like, manifest, signed-registry or
     phone-script member;
   - there is no PEM private-key header;
   - the attempt-1 candidate digest is not present;
   - the tar's own SHA-256 is not inside it.
6. **Loaded from inside the bundle** (Linux; only `cryptography` from the
   pinned deps):
   - `burned_identities` and `rfc8785` resolve to the bundle;
   - the canonical burned set is 20;
   - every burned registry and genesis digest (6 / 6) is refused;
   - the attempt-1 candidate is **not** a burned identity;
   - `ACCEPTED` (E-21 `cb36daf1…`, K-WIT `5d778701…`), `policyVersion` and the
     continuity are as recorded.

## 5. Reproducibility

The reviewed design promises archive-level determinism (builder docstring;
package test).

| Build | Platform | tar SHA-256 | size | `SHA256SUMS` | members |
| --- | --- | --- | --- | --- | --- |
| A | Windows 11, Python 3.13, clone A | `ad37758e…a736` | 1454080 | `58eb1b82…f683` | 75 files |
| B | Windows 11, Python 3.13, clone B | `ad37758e…a736` | 1454080 | `58eb1b82…f683` | 75 files |
| C | WSL Ubuntu 24.04, Python 3.12, git-bundle clone | `ad37758e…a736` | 1454080 | `58eb1b82…f683` | 75 files |

**A, B and C are byte-identical** (`cmp`). Result:
**`MB3_REPLACEMENT_BUNDLE_REPRODUCIBLE_BYTE_IDENTICAL`** (3 / 3, two platforms).

## 6. Validation (from the merged tree; local only)

WSL Ubuntu 24.04 (Python 3.12, pinned deps), on a full-history clone of
`f9fb9e1`:

| Suite | Result |
| --- | --- |
| M-B3 incident tests, including real-pseudo-terminal `_tty_confirm` (fixed: works; attempt-1: `UnsupportedOperation`), TEST-key end-to-end real-terminal PREPARE + SIGN, attempt-1 reproduction, wrong confirmation, disposition procedure | 17 OK |
| all M-B3 tests | 75 OK |
| M-B2 / M-B1 tests | 36 OK / 66 OK |
| P3-5 sequencing; authority registry contracts | 19 OK; 35 OK |
| **full owner-memory-control** | **908 OK, 0 skipped** |
| authority-dev | 241 OK |
| `services/authority-dev/release_file_set.py` | exit 0 |
| `scripts/validate_repository.py` | passed |

## 7. Phone incident disposition (pointer; NOT AUTHORIZED)

The reviewed procedure in the
[incident record](slice-15b2b-b1b3e-mb3-sign-attempt1-incident.md) §8 still
applies to the actual attempt-1 phone state. It expects:

- `~/lilith-mb3/` with the `sign/` attempt marker and no signer output or burn;
- the attempt-1 manifest `52478f46…`;
- the failure export `658f4af6…`;
- `invoked: false` / `A_NO_SIGNATURE`;
- the attempt-1 Download files, each identified by its hash.

None of these is changed by this finalization.

**Ordering consequence.**

- The replacement script has the **same filename**, `mb3_phone_ceremony.py`.
  The K-ACT and K-WIT inputs also keep the names `mb3-kact-publication.json`
  and `mb3-kwit-publication.json`.
- So the attempt-1 Download copies **must be archived by the reviewed
  disposition procedure before any replacement file is transferred.**
- A replacement copy placed first would overwrite an attempt-1 file. The
  procedure would then STOP ("not the attempt-1 file; left in place"),
  possibly after archiving earlier files.
- The replacement bundle name `lilith-mb3-registry-f9fb9e1.tar` does not
  collide.
- A replacement PREPARE also refuses while `~/lilith-mb3` or the failure
  export exists.

```text
PHONE INCIDENT DISPOSITION = NOT AUTHORIZED
```

## 8. State

```text
M-B3 REPLACEMENT PACKAGE STATUS = REVIEWED FIX / MERGED / FINALIZED FOR NEW PREPARATION-SEQUENCE CONSIDERATION
PACKAGE SOURCE f9fb9e14dc6a14ac796379938d3092f6214194cb
REPLACEMENT BUNDLE lilith-mb3-registry-f9fb9e1.tar ad37758ebf892e773a7019cb2c084d4d30920e34fb5318ba9f82999f48ffa736 (1454080 BYTES, 75 FILES, 19 DIRECTORIES)
SHA256SUMS 58eb1b8269f8a54dd4153d1bde68f1bf1440cb7d52459081f81884599240f683
CORRECTED PHONE SCRIPT b58b93215dc5c1e724846c7fc16acc2c29d81725a2ba13badcdccfd7b9eaecc7
MB3_REPLACEMENT_BUNDLE_REPRODUCIBLE_BYTE_IDENTICAL
HISTORICAL RUNS 37466905265 / 37467113188 = SUCCESS; NOT FRESHNESS; NOT CURRENTNESS
ATTEMPT-1 PACKAGE fce71811073eeb98ce82b5db60dcefb5b7abb12119ed609d35a055bee7360cb0 = HISTORICAL / SUPERSEDED
ATTEMPT-1 SCRIPT db02909d8f769f5a0570386aef55c3a472bdbc6c52949830ab94c1b624e6bd54 = HISTORICAL / SUPERSEDED
ATTEMPT-1 CANDIDATE b7e24530a21757a5bef996ec9adb13ed5932ab04edb1943321f529e3206c0e53 = HISTORICAL_ABANDONED_UNSIGNED_CANDIDATE; NOT BURNED; NOT REUSABLE
M-B3 SIGN ATTEMPT 1 = CLOSED / INCIDENT / A_NO_SIGNATURE
NO_REAL_REGISTRY_BURN
REPLACEMENT PACKAGE FINALIZED; NOT TRANSFERRED
M-B1 / GENERATE_K_ROOT = COMPLETED / ACCEPTED
M-B2 / GENERATE_K_WIT = COMPLETED / ACCEPTED
PHONE INCIDENT DISPOSITION = NOT AUTHORIZED
REPLACEMENT M-B3 PREPARATION = NOT AUTHORIZED
REPLACEMENT PREPARE = NOT AUTHORIZED
REPLACEMENT SIGN_REGISTRY_V1 = NOT AUTHORIZED
REGISTRY_SIGNED = NOT REACHED
M-B4/M-B5 = NOT AUTHORIZED
GENESIS = NOT AUTHORIZED
RECORD 1 = NOT AUTHORIZED
FIRST MEMORY = NOT AUTHORIZED
PROD = NOT AUTHORIZED
FRESHNESS=UNKNOWN
NO LIVE SYSTEM CONTACTED; NO K-ROOT OR K-WIT ACCESS; NOTHING SIGNED
```

> **Later current state (2026-10-06, pointer only; the text above is
> preserved as written).** The owner-authorized phone incident disposition ran
> once with the reviewed block (`73f71355…54e1`) and passed:
> [disposition completion record](slice-15b2b-b1b3e-mb3-attempt1-disposition-completion.md). The attempt-1 state is archived in
> `~/lilith-mb3-incident-attempt1` (manifest `94483e8b…181d`), the active M-B3
> paths are clear, K-ROOT custody is preserved, and no replacement file was
> transferred. A replacement preparation sequence, PREPARE and SIGN remain NOT
> AUTHORIZED, and FRESHNESS is UNKNOWN.

> **Later current state (2026-10-06, pointer only; the text above is
> preserved as written).** Attempt 2 ran under its own owner-authorized
> preparation, transfer, PREPARE and one-attempt SIGN steps, with fresh gates
> and a new candidate. The owner accepted the result:
> [M-B3 completion record](slice-15b2b-b1b3e-mb3-registry-sign-completion.md).
> M-B3 / `SIGN_REGISTRY_V1` COMPLETED / ACCEPTED; Registry V1 `fa662721…14fc`
> (signed file `3f0a59c0…6156`) is signed and owner-accepted, not installed
> and not effective. The attempt-1 candidate stays historical, not burned and
> not reusable. M-B4/M-B5, genesis, record 1, First Memory and PROD remain
> NOT AUTHORIZED, and FRESHNESS is UNKNOWN.
