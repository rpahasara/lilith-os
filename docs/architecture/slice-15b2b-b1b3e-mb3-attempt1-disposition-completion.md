# Slice 15B2b-B1b-3e — M-B3 Attempt-1 Phone Incident Disposition: Completion Record (2026-10-06)

Status:

- **`PHONE_INCIDENT_DISPOSITION = PASS`.** One owner-authorized,
  owner-attended S25 operation archived the M-B3 SIGN attempt-1 phone state
  by rename and move. It followed the reviewed procedure in the
  [attempt-1 incident record](slice-15b2b-b1b3e-mb3-sign-attempt1-incident.md)
  §8. Nothing was deleted, and K-ROOT custody is preserved.
- **This record authorizes nothing.** It authorizes no live S25 action, no
  replacement-file transfer, no replacement M-B3 preparation sequence, no
  PREPARE, no `SIGN_REGISTRY_V1` and no K-ROOT use. M-B4/M-B5, registry
  installation and effectiveness, genesis, record 1, First Memory and PROD
  remain **NOT AUTHORIZED**. `FRESHNESS=UNKNOWN`.
- Append-only, repository-only. The raw evidence is owner-held outside the
  repository: the S25 archive, its manifest, the S25 transcript, and the
  laptop preparation folder.

```text
disposition authorized != disposition executed != disposition accepted
disposition PASS != replacement package transferred != replacement preparation authorized != PREPARE != SIGN
archived attempt-1 evidence != reusable attempt-1 candidate
```

## 1. Identities

| Item | Value |
| --- | --- |
| governance / control commit | `cb07608b3bcc8b8b04834a174383bc28461994f8` (merge of PR #156, the replacement package finalization) |
| reviewed procedure | [incident record](slice-15b2b-b1b3e-mb3-sign-attempt1-incident.md) §8. Its block is unchanged at `cb07608`: the record gained only an appended pointer since review |
| disposition script | `mb3_attempt1_disposition.sh`, SHA-256 `73f7135549322bd939fd7f3c743e564715e708402388d61d51a86e46c30154e1` (4013 bytes), extracted from the record at `cb07608` and byte-identical to the block the tests execute; the 5 disposition tests passed at `cb07608` before transfer |
| incident record at control | SHA-256 `9f476217334b8c1432e29d1ba87566346aa7f6a491affdfeeba222ee873fb37c` |
| **archive** | `~/lilith-mb3-incident-attempt1` (S25 Termux private storage) |
| **archive manifest SHA-256** | `94483e8b95adecea163dad9d0622877f21328f9d580ebee68201bf36c955181d` (`~/lilith-mb3-incident-attempt1.sha256`) |

## 2. Owner authorization (verbatim)

> I authorize one owner-attended S25 M-B3 attempt-1 incident disposition operation, and nothing beyond it.
> Current governance/control commit:
> cb07608b3bcc8b8b04834a174383bc28461994f8
> The operation must follow the reviewed incident-disposition procedure recorded for M-B3 SIGN attempt 1.
> It may verify the exact attempt-1 before-state, verify all required attempt-1 hashes, archive/rename the existing attempt-1 M-B3 state and public incident evidence exactly as reviewed, remove the reviewed attempt-1 files from the Download staging area only after their expected hashes match, write and verify the reviewed archive SHA-256 manifest, and verify before and after that the K-ROOT directory metadata/name set remains unchanged.
> The preferred disposition is archival by rename/move, not deletion of incident evidence.
> This authorization does not permit opening, reading, decrypting, moving, copying, renaming or modifying k-root.der or any K-ROOT private material.
> It does not authorize copying the replacement M-B3 package or corrected script to the phone.
> It does not authorize a replacement M-B3 preparation sequence, PREPARE, SIGN_REGISTRY_V1, K-ROOT passphrase entry, M-B4/M-B5, registry installation/effectiveness, genesis, record 1, First Memory, PROD, or any later bootstrap step.
> If the actual S25 before-state or any required attempt-1 hash differs from the reviewed incident procedure, STOP without moving or deleting anything.
> After successful disposition and verification, STOP and report the resulting phone state for owner review.
> FRESHNESS=UNKNOWN remains unchanged.

## 3. Execution

1. **Laptop preparation (repository / local only).**
   - The control commit was confirmed (`origin/main = cb07608`).
   - The reviewed block was extracted from the record at that commit, then
     re-tested at that commit: 5 / 5 PASS. The extracted file equals the
     tested block.
   - Only the disposition script was transferred to the S25. The replacement
     package and corrected script were **not** transferred.
2. **Read-only pre-check on the S25** (before running the script).
   - **Why it was added:** the reviewed block checks the home-directory
     before-state before any move, but checks the Download file hashes only
     inside its move loop. A Download mismatch could therefore stop after
     archiving had begun, which would breach the authorization's "STOP
     without moving anything" condition.
   - The owner therefore first verified every present attempt-1 Download file
     and both home-directory hashes against the procedure's pins, read-only.
   - **The reviewed script was not changed.**
3. **The disposition run.** It ran in a local Termux session, without SSH,
   ADB or automation. Its output was `DISPOSITION_BEFORE_STATE_OK`,
   `ARCHIVE_SHA256 …`, then `MB3_ATTEMPT1_DISPOSITION_COMPLETE`. The
   transcript is `~/lilith-mb3-attempt1-disposition.transcript.txt`.
4. **The archive manifest hash.**
   - The owner's first transcription had 65 hexadecimal characters, so it was
     not a valid SHA-256. It was flagged before recording.
   - The owner then re-read the value read-only, from both
     `sha256sum ~/lilith-mb3-incident-attempt1.sha256` and the transcript's
     `ARCHIVE_SHA256` line. Both gave the same 64-character value (§1). The
     earlier value had one extra `e`.

## 4. Resulting phone state (owner-verified)

| Check | Result |
| --- | --- |
| `~/lilith-mb3` | absent |
| `~/lilith-mb3-failure-export.tar` | absent |
| `~/lilith-mb3-registry-public` | absent |
| `~/lilith-mb3-export.tar` | absent |
| `~/storage/downloads/mb3_phone_ceremony.py` (attempt-1 script `db02909d…`) | absent (archived) |
| archive contents | the attempt-1 `lilith-mb3/` state, including the `sign/` attempt marker, the manifest `52478f46…`, the candidate and the PREPARE evidence; the failure export `658f4af6…`; the PREPARE transcript; and `downloads/` (the archived attempt-1 Download files) |
| archive manifest | its SHA-256 equals `ARCHIVE_SHA256` on the phone |
| K-ROOT directory | still contains only `k-root.der`. The procedure's before / after metadata comparison (`stat`, name listing, public-anchor hashes) passed. K-ROOT was never opened, read, moved, copied or modified |
| replacement files on the phone | none transferred |

**Consequence.** The four paths that a replacement PREPARE refuses are clear,
and the attempt-1 script no longer sits in Download under the replacement
script's filename. That precondition for a future transfer
([replacement final pins](slice-15b2b-b1b3e-mb3-replacement-final-package-pins.md)
§7) is met. **It authorizes nothing.**

## 5. Attempt-1 history (unchanged)

- M-B3 SIGN attempt 1 is `CLOSED / INCIDENT / A_NO_SIGNATURE`, with
  `NO_REAL_REGISTRY_BURN`. Its sequence is ENDED and its go is CONSUMED.
- Candidate `b7e24530a21757a5bef996ec9adb13ed5932ab04edb1943321f529e3206c0e53`
  = `HISTORICAL_ABANDONED_UNSIGNED_CANDIDATE`: not burned and not reusable.
  It is retained, archived on the S25, as historical incident evidence only.
- The attempt-1 bundle `fce71811…` and script `db02909d…` are historical and
  superseded. The replacement pins are bundle `ad37758e…a736` and script
  `b58b9321…ecc7` (source `f9fb9e1`).

## 6. What remains for any future replacement attempt

Each item needs its own explicit owner authorization. None is given here.

1. A replacement M-B3 preparation sequence, with all fresh read-only gates
   ([decision](slice-15b2b-b1b3e-mb3-signing-continuity-owner-decision.md)
   D-2). That includes a new K-ACT publication pin: DEV has been deployed
   since the attempt-1 re-proof, so no attempt-1 evidence carries forward.
2. A fresh transfer set built from the replacement pins. The attempt-1
   transfer folder `%USERPROFILE%\lilith-mb3-transfer\` must never be reused.
3. A new PREPARE, which produces a new `epochRandom`, `issuedAt`, manifest and
   expected digest.
4. A separate one-attempt SIGN go.

## 7. State

```text
PHONE_INCIDENT_DISPOSITION = PASS
ATTEMPT1_ARCHIVE = ~/lilith-mb3-incident-attempt1
ARCHIVE_MANIFEST_SHA256 = 94483e8b95adecea163dad9d0622877f21328f9d580ebee68201bf36c955181d
DISPOSITION_SCRIPT 73f7135549322bd939fd7f3c743e564715e708402388d61d51a86e46c30154e1 (REVIEWED BLOCK AT cb07608, UNCHANGED)
ACTIVE_MB3_STATE = ABSENT
ATTEMPT1_DOWNLOAD_FILES = ARCHIVED
KROOT_CUSTODY_PRESERVED = YES
NOTHING DELETED; ARCHIVE BY RENAME / MOVE
REPLACEMENT_FILES_TRANSFERRED = NO
M-B3 SIGN ATTEMPT 1 = CLOSED / INCIDENT / A_NO_SIGNATURE
ATTEMPT-1 CANDIDATE = HISTORICAL_ABANDONED_UNSIGNED_CANDIDATE; NOT BURNED; NOT REUSABLE
REPLACEMENT M-B3 PREPARATION SEQUENCE = NOT AUTHORIZED
PREPARE = NOT AUTHORIZED
SIGN_REGISTRY_V1 = NOT AUTHORIZED
REGISTRY_SIGNED = NOT REACHED
M-B4/M-B5 = NOT AUTHORIZED
REGISTRY EFFECTIVENESS = NOT AUTHORIZED
GENESIS = NOT AUTHORIZED
RECORD 1 = NOT AUTHORIZED
FIRST MEMORY = NOT AUTHORIZED
PROD = NOT AUTHORIZED
FRESHNESS=UNKNOWN
THIS RECORD: REPOSITORY-ONLY; NO LIVE SYSTEM CONTACTED; NO K-ROOT OR K-WIT ACCESS; NOTHING SIGNED
```

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
