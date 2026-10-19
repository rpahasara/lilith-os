# Slice 15B2b-B1b-3e — M-B14 / WRITE_RELEASED: INITIAL_CUSTODY RELEASED Completed (2026-10-19)

Status:

- **OWNER ACCEPTANCE RECORD (APPEND-ONLY).** It records the one M-B14 `release-initial` on control
  `a5197d04c72a65cd3d595d81b6c5623a6ac598b4` (merge of PR #229, the M-B14 ceremony package). The INITIAL_CUSTODY
  record moved HELD → RELEASED in exactly one invocation of the reviewed release writer. An independent read-back
  verified it, and the owner then accepted M-B14 verbatim (§4).
- `M-B14 = COMPLETED / OWNER-ACCEPTED`. `CUSTODY = RELEASED`. The release marker `mb14` is consumed. M-B14 is never
  retried, and `unstage` is not run (the staging document was absent).
- **The earlier records are unchanged.** The [M-B14 package record](slice-15b2b-b1b3e-mb14-release-initial-package.md)
  (`PACKAGE PREPARED FOR OWNER REVIEW`, `CUSTODY = HELD`) was correct when written and is not rewritten. This record
  supersedes it on the M-B14 outcome only, from 2026-10-19.
- **RELEASED grants no authority.** `authorityGranted` stays false. FULL_READINESS (M-B15), authority activation,
  Registry V1 effectiveness, First Memory and PROD stay **NOT AUTHORIZED**.
- **The first post-M-B14 deploy has NOT yet occurred.** Its DR-5 comparison is **PENDING** (§6).
- **Writing this record contacted no live system.** The evidence stays in the owner's local evidence directories
  (§7), with one independently verified encrypted backup (§8).

```text
RELEASED = custody state only;  RELEASED != FULL_READINESS (M-B15) != activation != Registry V1 effective
MB14_RELEASED_EXACT technical result != owner acceptance
owner acceptance != this record merged != first post-M-B14 deploy EQUAL
```

## 1. Identities

| Item | Value |
| --- | --- |
| control | `a5197d04c72a65cd3d595d81b6c5623a6ac598b4` (clean clone; `MB14_TOOL_PINS_EXACT`) |
| control deploy | `39277135210`, success at the control; the only deploy since `39254293493` and the last before the release |
| operator | `services/owner-memory-control/tools/mb14_operator.py`, SHA-256 `37db0b0308673ac709fe3229772d7cba230e9917fe108db96e03aa39a9222028` |
| envelope | `3128a0a857cae8a0121c2febf97f2e6e0e9a3f0e92f9fa6bec843dba13c875fb` (the M-B12 envelope) |
| input document | `inputs.json` `261b437084e2b38ef968385b61d46ea8580b4685c2439a4781080f2772caec43` |
| expected records | `EXPECTED.json` `d090209daa829b16db8bba2710c37c506b1b9128f901dc2880faa84b09a6bdef` |
| approved package digest | `eab79d56e58f0d7ce88217c43acdba1d31dec30743d79245dca6a893b49a1a86` (M-B12 / M-B13) |

## 2. Sequence

| Step | Time (UTC) | Result |
| --- | --- | --- |
| DR-5 on deploy `39277135210` | before `pre` | `EQUAL` 194 / 155 / 29, `unequal []`; comparison `c9ba3e9898e6c1c4669fdcd17fc6ab9836feddfc60c0c990611bec93c468ad0d`; E-08 `7fe21378…` |
| `prepare` | before `pre` | `MB14_PREPARED` |
| `pre` (read-only) | 15:35:34 – 15:36:24 | `MB14_PRE_EXACT`, reasons `[]`: HELD `c713ea1d…` (421 B), listing `ee7aaa61…`; staging absent; signer `efbc0784…` / 128648; ONE package re-run `READY`, `HOLD_RELEASE_ELIGIBILITY`, digest `eab79d56…`. `PRE.json` `392dc05c13b5a2daf27d0f2ba9d5f51eace647984e34b66d9151eac3e19a705c` |
| owner GO | rendered 15:47 | `8bc9a612c52dddbf3fdfe15470fb23ac38ca080b5d7884682c2f261724741cbf` (2305 B, LF); the owner's go bytes equal the fresh render |
| `release` | 15:54:33 – 15:55:36 | gate exact (HELD, staging absent, signer, witness); marker `mb14` (`940e4c79…`) at 15:55:02; ONE remote invocation, rc 0, stderr empty; CLI rc 0, `cliExact` true; `MB14_UNSTAGED=0`. `ATTEMPT.json` `73deead07d1df51c766b0f04bf110b2119c59f004d893898b6782317d4cd4afb`; `RELEASE.json` `09c7752cce889b489ddb70879ca63df173d8cb1076c13dbb0331dc6daa2e1d2e` |
| read-back (`post`) | 15:55:36 | `MB14_READBACK_RELEASED_EXACT` (§3). `POST.json` `2beea0f2da65d5d22bad0bc79f24ea6e9999c88222fb80d79be3cec2bf92c55e` |

Result: **`MB14_RELEASED_EXACT`**. There was one marker and one invocation. Nothing was retried.

## 3. Custody after M-B14

| | Before (HELD, now historical) | After (RELEASED) |
| --- | --- | --- |
| name | `1ee1b7d5797b9c39b941befbbe4a5917b7fe510fa48a0f487f801246f80071d6.json` | the same (replaced in place) |
| bytes / SHA-256 | 421 B, `c713ea1d2e0b016e59eb55ddc1a125561495ed4cc0a2c24764f36c8355d0216d` | 431 B, `bb7576f4437fb61dd31adafe50ac56eba467c7f98b329b7149942e630f1ef003` |
| hold listing digest | `ee7aaa61c2e52d1aa8bb2c2a5c086e1d85a4b432df20cbb78a60f88495df6a82` | `c4cb131983b450d1e931d1121e5b125a98c2dc1625934db0ff0a5f3f661e195c` |
| bound witness | genesis `ac892dc2b14ca7db108400258abfcf2320ff498f2a674058058e16a8a6fb65e4` | the same (chain length 1) |

The read-back found exactly one entry with the expected RELEASED bytes, the staging path absent, all three
observations at exit 0, and both services unchanged: signer `efbc0784…` / 128648 and witness `8cbfbed2…` / 127192,
`NRestarts` 0. `authorityGranted` is false. Both values equal the package derivation
(`EXPECTED_RELEASED_SHA256`, `EXPECTED_RELEASED_LISTING`).

The HELD bytes now exist on no host. They are retained off-host only (package record §5–§6): in `EXPECTED.json`, the
`pre` and release-gate observations, and the M-B10 evidence.

## 4. Owner acceptance

**Owner decision (verbatim, 2026-10-19):**

> I accept M-B14 / WRITE_RELEASED for DEV_SYNTHETIC: INITIAL_CUSTODY RELEASED is COMPLETED.
> RELEASED record: 1ee1b7d5797b9c39b941befbbe4a5917b7fe510fa48a0f487f801246f80071d6.json, SHA-256 bb7576f4437fb61dd31adafe50ac56eba467c7f98b329b7149942e630f1ef003, bound to witness genesis ac892dc2b14ca7db108400258abfcf2320ff498f2a674058058e16a8a6fb65e4. Read-back SHA-256: 2beea0f2da65d5d22bad0bc79f24ea6e9999c88222fb80d79be3cec2bf92c55e. Approved and re-run package digest: eab79d56e58f0d7ce88217c43acdba1d31dec30743d79245dca6a893b49a1a86.
> The HELD record SHA-256 c713ea1d2e0b016e59eb55ddc1a125561495ed4cc0a2c24764f36c8355d0216d is retained off-host only. authorityGranted remains false.
> This acceptance authorizes nothing further: not FULL_READINESS (M-B15), authority activation, Registry V1 effectiveness, First Memory or PROD.

| Item | Value |
| --- | --- |
| statement | `ACCEPT.txt`, 821 B, LF, SHA-256 `62dd0b3c47151d0ec7092dc8227ea7243cfc8db5f51590adf77c70b41a9b1fdc`, rendered from the workdir; no adoption line (the CLI response was received exactly) |
| `accept` | `MB14_ACCEPTED`, `authorityGranted` false, stderr empty |
| acceptance record | `MB14_ACCEPTANCE.json` `72ccfb049935a9ad14181ba35a9ef7f8821377513f01f8f098ea473356acdcb2` |

## 5. Expected HALTs (not drift)

As the package record §7 says, every judge that requires HELD now reports HALT or a mismatch. This is expected and
is not drift:

- the W10 (`mb10_held_verifier`, `W10_HOLD_SET_UNEXPECTED`) and W11 verifiers;
- the M-B11 and E-22 `status` / `v0` / `post` forms;
- E-19 `PRESERVED_PINS` (`heldSha256`);
- `HOLD_RELEASE_ELIGIBILITY` (the package digest `eab79d56…` and HOLD listing `ee7aaa61…` are consumed).

These judges are historical HELD evidence, valid for the period before 2026-10-19 15:55Z. They are not re-pinned, and
a HALT from them is not read as a RELEASED pass. The RELEASED state is established only by the M-B14 read-back
(§3) and the owner's acceptance (§4).

The pins that do not observe the hold store stay valid (package record §7). A post-RELEASED read-only host judge
(W14) and moving the HELD-based pins to RELEASED are deferred to M-B15 preparation. Neither is in this record.
M-B15 (FULL_READINESS) and the W14 judge are separate, not prepared and not authorized.

## 6. First post-M-B14 deploy (PENDING)

The merge of this record deploys. Its DR-5 comparison must be `EQUAL` to the unchanged E-22 target
(194 / 155 / 29). Anything other than `EQUAL` is a STOP for owner review. The target is not rebaselined, and no
gate is relaxed to admit it. DR-5 cannot read the hold store, so EQUAL is deployment-boundary evidence only. It is
not evidence about RELEASED.

## 7. Off-host evidence

The evidence folders are identified by name. They live in the owner's private evidence root, outside Git; paths
inside a folder are relative to it.

| Evidence folder | Contents | Seal |
| --- | --- | --- |
| `lilith-mb14-seq-a5197d0` | control clone `ctl/` (not sealed), DR-5, GO, `workdir/` (prepare, pre, marker, release, post, acceptance), `acceptance/` (a byte-identical copy of `lilith-mb14-accept-a5197d0`), status notes | `SHA256SUMS` `34e88fa3…` (read-only stage); `SHA256SUMS.seal-2-release` `883ba32e…` (70 files); `SHA256SUMS.seal-3-accept` `59321791a09de893a9198589ee46b06d6ac44e4d1859ca98f3db2ce17fab166a` (79 files: seal-2's set, both earlier seals, `workdir/MB14_ACCEPTANCE.json`, `acceptance/`, `STATUS-accept.md`) |
| `lilith-mb14-accept-a5197d0` | the original `ACCEPT.txt`, render and `accept` transcripts | covered by seal-3 through the copy |
| `lilith-mb14-step1-0457b03`, `lilith-mb14-package-0457b03`, `lilith-mb14-stop-0457b03` | earlier M-B14 evidence: DR-5 Step 1, the package re-run, the STOP record | their own `SHA256SUMS` |

## 8. Independent encrypted backup (2026-10-19 / 20)

After M-B14 the HELD bytes exist only off-host (§3), so the five evidence folders were backed up once, encrypted, to
a second device. Each phase had its own owner authorization. No seal and no evidence file changed.

| Item | Value |
| --- | --- |
| archive | one tar of the five folders in §7, without the rebuildable `ctl/` clones: 121 files, 28 directories, 1,771,520 bytes, SHA-256 `59833ee1687728b91b9077d59b65d051b998ae867aca4c2bdfc29905ac47e305` |
| encryption | GnuPG symmetric, AES-256, iterated and salted S2K with SHA-512, integrity-protected (MDC). The passphrase is held by the owner only and is recorded nowhere |
| encrypted archive | `lilith-mb14-evidence-20261019.tar.gpg`, 282,255 bytes, SHA-256 `2394b7b3c2d38abe85b5af3530261c7d996dec4bb6ec33c8f406e0f046821835` |
| copies | laptop backup folder `lilith-mb14-backup-20261019` (owner-only access; it also still holds the plaintext tar); the owner's S25 Ultra, internal storage `Download` (encrypted archive and its `.sha256` only) |

| Phase | Where / by whom | Result |
| --- | --- | --- |
| B1 build | laptop, agent | the six seals verified first; every archived file byte-equal to its source |
| B2 encrypt | laptop; the owner entered the passphrase in GnuPG's own prompt | `END_ENCRYPTION` |
| B3 test restore | laptop, agent; passphrase entered by the owner | `DECRYPTION_OKAY`, `GOODMDC`, no warnings; tar SHA-256 equal; members safe (no links, absolute or `..` paths); 121 files byte-equal; six seals OK; acceptance copy OK |
| T1 transfer | laptop → S25 by USB (MTP), agent | two files, nothing overwritten; read back from the phone, both hashes equal |
| S1 independent restore | S25 Ultra, Termux, **owner-run** | see below |

**S1 (owner-reported results, evidence class `OWNER_SCREEN_TRANSCRIPTION`).** The owner ran these checks in Termux
and reported the results. The agent did not run or observe them.

- The encrypted archive SHA-256 on the phone was `2394b7b3…1835`.
- It decrypted with the owner's passphrase, and the decrypted tar SHA-256 was `59833ee1…e305`.
- The archive audit found 121 files, 28 directories and the five expected folders. It was extracted inside Termux's
  private app storage, never in `Download`.
- Five seals passed directly. The sixth (`lilith-mb14-stop-0457b03/SHA256SUMS`) names its one file, `STOP.md`, by
  an absolute laptop path, so it cannot be checked in place on another device. It was verified by comparing
  `STOP.md` with the digest in that unchanged manifest.
- The acceptance copy was OK, and the `MB14_ACCEPTANCE.json` SHA-256 was verified.

The restored test copies (laptop and Termux) are retained. No cleanup is authorized. The backup grants nothing and
changes no custody or authority state.

## 9. State

```text
M-B12 = COMPLETED;  M-B13 = OWNER-ACCEPTED;  M-B14 = COMPLETED / OWNER-ACCEPTED 2026-10-19 (RELEASED bb7576f4…f003)
CUSTODY = RELEASED;  AUTHORITY = DARK;  REGISTRY V1 = NOT EFFECTIVE;  FIRST MEMORY = NONE
EVIDENCE = seal-3 59321791…166a;  ENCRYPTED BACKUP = VERIFIED (laptop + S25; S1 owner-reported)
first post-M-B14 deploy DR-5 = PENDING (must be EQUAL 194 / 155 / 29; no rebaseline)
M-B15 (FULL_READINESS) and the W14 post-RELEASED judge = NOT PREPARED, NOT AUTHORIZED
```
