# Slice 15B2b-B1b-3e — M-B3 / SIGN_REGISTRY_V1 Attempt 1: Incident Record, Fix and Disposition Procedure (2026-10-06)

Status:

- **`MB3_SIGN_ATTEMPT_1 = CLOSED / INCIDENT / A_NO_SIGNATURE`.** The first
  owner-authorized DEV_SYNTHETIC M-B3 SIGN attempt stopped inside the phone
  script **before the signer was invoked**. No signature exists. No Registry
  V1 identity was burned.
- **The attempt-1 sequence is ENDED / NON-REUSABLE; the attempt-1 go is
  CONSUMED.** The attempt must never be retried.
- **The attempt-1 candidate is `HISTORICAL_ABANDONED_UNSIGNED_CANDIDATE`**
  (owner decision, §4). It is not burned and not eligible for reuse.
- **The fix is repository-only and pre-merge (§5).** It changes only the real
  terminal confirmation I/O. No signing, canonicalization, signer, K-ROOT,
  K-WIT, manifest or authority semantics change.
- **Nothing is authorized by this record:** no replacement preparation
  sequence, no PREPARE, no SIGN go, and no phone cleanup. The disposition
  procedure (§8) is reviewed here and needs its own owner authorization.
- Append-only. Earlier records are not edited except for later-state pointers.

```text
attempt-1 SIGN STOP           != signature
A_NO_SIGNATURE                != burn
HISTORICAL_ABANDONED_UNSIGNED_CANDIDATE != BURNED_REGISTRY_DIGEST
historical retention          != permission to reuse it
fix merged                    != package re-finalized != replacement sequence authorized != SIGN go
reviewed disposition procedure != phone cleanup authorized
```

## 1. Identities

| Item | Value |
| --- | --- |
| governance / control commit of the attempt | `a86d032211ebb421e3777aa43cc2da31b0093c28` |
| package source commit | `1f544e695742fd4a93fcf4fd8dc5d706e24eb452` |
| bundle | `lilith-mb3-registry-1f544e6.tar`, `fce71811073eeb98ce82b5db60dcefb5b7abb12119ed609d35a055bee7360cb0` |
| **attempt-1 phone script** | `db02909d8f769f5a0570386aef55c3a472bdbc6c52949830ab94c1b624e6bd54` (now superseded) |
| candidate manifest | `52478f462509cb7904791a80cd0e0dfa70316ae48b6fc4d7830dd64e5de2aa2e` |
| candidate digest | `b7e24530a21757a5bef996ec9adb13ed5932ab04edb1943321f529e3206c0e53` |
| `epochRandom` / `issuedAt` | `141428faf6afa19c3525e7b6c2e6b1aa` / `2026-10-06T12:00:18Z` |
| PREPARE readback | `27dfb73ce42746eeb8effb0338dae5146bbc69a0e7411745eb0c7457c6da45e4` |
| **failed attempt start** | `2026-10-06T12:11:49Z` (`sign/attempt.json`) |
| **failure export** | `lilith-mb3-failure-export.tar`, `658f4af661f7933c258acc8ba18fae5fcd60696ed0d2a4d20dcc1157e92e2de3` |
| transcript | none: the command was not piped through `tee`. The phone screen output plus the structured failure export are the accepted evidence |

## 2. What happened

The owner ran the authorized `sign` command once. The phone printed:

```text
STOP: unexpected UnsupportedOperation: File or stream is not seekable.
MB3_ATTEMPT_CONSUMED outcome=A_NO_SIGNATURE burn=no
MB3_INCIDENT: the go is consumed. NO RETRY.
```

**Failure export contents.**

- It holds 11 public files: the manifest, the unsigned registry, the signing
  bytes, PREPARE evidence, the four public inputs, `sign/attempt.json`,
  `evidence/sign-outcome.json` and `evidence.sha256`. It has no private
  markers.
- `evidence/sign-outcome.json` records
  `{"burnRecorded": false, "invoked": false, "outcome": "A_NO_SIGNATURE", "stop": "unexpected UnsupportedOperation: File or stream is not seekable."}`.
- **Absent, because they were never created:**
  - `sign/registry-v1.stdout`, `sign/registry-v1.stderr` and
    `sign/registry-v1.exit`. The script creates the first two
    (`O_EXCL`) immediately before the single signer call;
  - `burn/`;
  - `evidence/verify-s25.txt`.
- Every frozen file in it is byte-identical to the PREPARE readback.

## 3. Root cause (traced and reproduced)

`mb3_phone_ceremony.py` (`db02909d…`), `_tty_confirm`:

```python
with open("/dev/tty", "r+", encoding="utf-8") as tty:
```

- Text mode `"r+"` builds a `BufferedRandom`, which requires a seekable raw
  stream.
- A terminal is not seekable.
- So `open` raises `io.UnsupportedOperation: File or stream is not seekable.`
  before the prompt is written.

`sign()` order in the attempt-1 script:

1. K-ROOT file custody shape: `lstat` of the file and its directory, `listdir`
   of the directory, `realpath`. This is metadata only, by design.
2. `phone.show(...)`, using `_tty_show` (`"w"`): it worked.
3. **`phone.confirm(...)` → `_tty_confirm` → the exception.**
4. Never reached:
   - the creation of the signer stdout / stderr files;
   - `invoked = True`;
   - the single `run_signer` call.

**Established:**

- `"r+"` in `_tty_confirm` is the only read/write or seek stream on the SIGN
  path. This was checked across the script, the library, the owner tool,
  `lilith_owner_memory` and `lilith_memory`.
- The exception was reproduced exactly under a real pseudo-terminal with the
  pinned `db02909d…` bytes. The stop string is byte-identical to the phone's.
- **The cause is not** `tee`, stdout / stderr handling, `getpass`, the
  subprocess invocation, transcript capture, or the signer. PREPARE never
  prompts, which is why it succeeded.

**Why review missed it.** The package tests replaced `confirm`, `show` and
`run_signer` with stand-ins. The real terminal functions and the real signer
subprocess were never exercised.

## 4. Accepted incident state and owner decisions

```text
SIGNER_INVOKED = NO
KROOT_ACCESSED = NO (metadata stat/listdir only, by design; never opened, read, loaded or decrypted)
PASSPHRASE_PROMPT_REACHED = NO
SIGNATURE_POSSIBLE = NO
BURN_STATUS = NO_REAL_REGISTRY_BURN
CURRENT_SEQUENCE = ENDED / NON-REUSABLE
CURRENT_GO = CONSUMED
```

**Candidate `b7e24530a21757a5bef996ec9adb13ed5932ab04edb1943321f529e3206c0e53`:
`HISTORICAL_ABANDONED_UNSIGNED_CANDIDATE`** (owner decision).

- **Never signed. Not burned.** It is not a burned Registry V1 identity and is
  **not** added to any real-registry burn set. Burn case A: no signature, so
  no burn.
- **Not eligible for reuse** as the replacement live candidate. It may be
  retained only as historical incident evidence.
- It also cannot be reused mechanically:
  - its manifest binds the attempt-1 script SHA-256, which the fixed script no
    longer matches;
  - `~/lilith-mb3/sign/` exists, so `sign` refuses
    (`ATTEMPT_ALREADY_CONSUMED`);
  - `prepare` refuses while `~/lilith-mb3` or the failure export exists.
- **A replacement requires a completely new PREPARE**, with a new
  `epochRandom`, `issuedAt`, candidate manifest and expected registry digest.

## 5. The fix (repository-only; pre-merge)

Only `_tty_confirm` changes. It now uses separate write-only and read-only
terminal handles:

```python
def _tty_confirm(prompt: str) -> str:
    # Separate write-only and read-only handles: a terminal is not seekable, and text-mode "r+"
    # (BufferedRandom) refuses it with UnsupportedOperation (M-B3 attempt-1 incident).
    with open("/dev/tty", "w", encoding="utf-8") as out, open("/dev/tty", "r", encoding="utf-8") as tty:
        out.write(prompt)
        out.flush()
        return tty.readline().strip()
```

- **Unchanged:** Registry V1 cryptographic semantics, canonicalization, the
  `registry-v1` signer, the signing bytes, K-ROOT loading and signing, K-WIT,
  the candidate manifest, the authority contracts, and runtime authority
  behaviour.
- **Not changed:** the library (`c77b651c…`), builder, verifier and owner tool
  are byte-unchanged. The bundle members are unchanged; the phone script is
  outside the bundle.
- Reverting exactly this function reproduces the attempt-1 script
  `db02909d…` byte for byte (test-enforced).
- **Pre-merge fixed phone-script SHA-256:
  `b58b93215dc5c1e724846c7fc16acc2c29d81725a2ba13badcdccfd7b9eaecc7`.** It
  becomes a live pin only after merge and post-merge re-finalization (§7).

## 6. Test-gap closure

`services/owner-memory-control/tests/test_b1b3e_mb3_sign_incident.py` runs the
**real** terminal path under a real pseudo-terminal. `pty.fork` makes it the
child's controlling terminal, so `/dev/tty` is the pty. Only TEST keys and
TEST passphrases are used.

| Test | Proves |
| --- | --- |
| `test_reconstructed_script_is_the_attempt1_pin` | the current script with only the fix reverted is exactly `db02909d…` |
| `test_only_tty_confirm_changed` | no other line changed; no `open("/dev/tty", "r+"` remains |
| `test_the_terminal_is_not_seekable` | `/dev/tty` on a real pty is not seekable |
| `test_fixed_confirm_shows_prompt_and_reads_answer_on_a_real_terminal` | the fixed `_tty_confirm` displays the prompt and reads the typed answer |
| `test_attempt1_confirm_fails_exactly_as_on_the_s25` | the attempt-1 `_tty_confirm` raises `UnsupportedOperation: File or stream is not seekable.` before showing the prompt (**the regression**) |
| `test_end_to_end_sign_through_a_real_terminal` | PREPARE, then SIGN with the real `_tty_show`, `_tty_confirm` and `_signer_subprocess`. The confirmation is typed through the pty, and the TEST passphrase through the real `getpass` prompt (shown once, never echoed). Exactly one signer invocation, exit 0, empty stderr, `REGISTRY_SIGNED`; the laptop verifier passes; a retry is `ATTEMPT_ALREADY_CONSUMED` |
| `test_attempt1_script_reproduces_the_incident_end_to_end` | the attempt-1 script under a real terminal ends exactly as on the S25: `A_NO_SIGNATURE`, `invoked: false`, no burn, no signer files, the same stop string, the prompt never shown, no passphrase prompt; a retry is refused |
| `test_wrong_confirmation_on_the_real_terminal_consumes_without_signer` | a wrong answer consumes the attempt with no signer invocation and no burn; a retry is refused |

In the test environment only, a user-site `.pth` under the temporary HOME lets
the real signer subprocess import `cryptography`. On the S25, `cryptography`
is system-installed.

## 7. Package and pin consequences

```text
PACKAGE_REFINALIZATION_REQUIRED = YES
```

- The fixed phone script has a new SHA-256. The repository references and
  tests that pinned `db02909d…` now treat it as the attempt-1 / superseded pin,
  and check the current file against the pre-merge fixed pin. History is not
  rewritten: the package and final-pins records carry later-state pointers.
- **After this fix merges**, a separate post-merge finalization phase:
  1. fixes the new package source commit;
  2. rebuilds the bundle from that exact commit;
  3. records the new bundle SHA-256, `SHA256SUMS` SHA-256 and phone-script
     SHA-256;
  4. re-runs the reproducibility checks;
  5. records the final replacement pins.

  The M-B1 precedent is followed: the members are unchanged, but
  `SOURCE_COMMIT` and `SHA256SUMS` change.
- No replacement live transfer set is created now. The previously finalized
  bundle `fce71811…` and script `db02909d…` must not be used for a replacement
  attempt.

## 8. Phone incident disposition procedure (reviewed; NOT AUTHORIZED)

**Purpose.** Before any replacement PREPARE, the S25 must not hold
`~/lilith-mb3`, `~/lilith-mb3-registry-public`, `~/lilith-mb3-export.tar` or
`~/lilith-mb3-failure-export.tar`, because PREPARE refuses all four. The
attempt-1 phone script and inputs must also leave Download, so that they
cannot be run or picked up by mistake.

**Disposition: archive by rename, never delete.**

| Path | Disposition |
| --- | --- |
| `~/lilith-mb3/` (staging, `sign/` attempt marker, evidence, inputs, bundle copy) | renamed into `~/lilith-mb3-incident-attempt1/lilith-mb3/` |
| `~/lilith-mb3-failure-export.tar` | moved into `~/lilith-mb3-incident-attempt1/` |
| `~/lilith-mb3-prepare.transcript.txt` (if present) | moved into `~/lilith-mb3-incident-attempt1/` |
| Download: `mb3_phone_ceremony.py` (`db02909d…`), `lilith-mb3-registry-1f544e6.tar`, `mb3-kact-publication.json`, `mb3-kwit-publication.json`, `lilith-mb3-prepare-readback.tar`, `lilith-mb3-failure-export.tar` (each if present, and only if its SHA-256 is the attempt-1 value) | moved into `~/lilith-mb3-incident-attempt1/downloads/` |
| `~/lilith-mb3-incident-attempt1.sha256` | new: a SHA-256 manifest of every archived file |
| **never touched** | `~/lilith-kroot-dev-synthetic/`, `k-root.der`, `~/lilith-kroot-dev-synthetic-public/` (the K-ROOT anchor), the Replica B and M-B1 paths, and every unrelated Termux file. K-ROOT is only `stat`-ed and listed by name, before and after, to prove it is unchanged |

**Run** only after a separate owner authorization, only on the S25, in a local
Termux session (no SSH, ADB or automation). Save the block as a file and run:

```text
bash mb3_attempt1_disposition.sh 2>&1 | tee "$HOME/lilith-mb3-attempt1-disposition.transcript.txt"
```

The block is exactly this. It is pinned by a test that executes it against a
temporary fixture HOME:

```bash
# ===== M-B3 attempt-1 incident disposition (S25 local Termux ONLY; requires a separate owner authorization) =====
# Archives by rename; deletes nothing. Never opens, reads, moves or changes K-ROOT. Any STOP: do not retry; report.
set -eu
MANIFEST_SHA=52478f462509cb7904791a80cd0e0dfa70316ae48b6fc4d7830dd64e5de2aa2e
FAILURE_SHA=658f4af661f7933c258acc8ba18fae5fcd60696ed0d2a4d20dcc1157e92e2de3
SCRIPT_SHA=db02909d8f769f5a0570386aef55c3a472bdbc6c52949830ab94c1b624e6bd54
BUNDLE_SHA=fce71811073eeb98ce82b5db60dcefb5b7abb12119ed609d35a055bee7360cb0
KACT_SHA=d76479762007afef828f3901591647dc4a2fb2205f4afac527b66d2cc9c6b032
KWIT_SHA=9e9dd0787b3d6df8d40730c6abab728cacbe5136269ca4421160da830bb23472
READBACK_SHA=27dfb73ce42746eeb8effb0338dae5146bbc69a0e7411745eb0c7457c6da45e4
A="$HOME/lilith-mb3-incident-attempt1"
S="$HOME/lilith-mb3-incident-attempt1.sha256"
DL="$HOME/storage/downloads"
K="$HOME/lilith-kroot-dev-synthetic"
P="$HOME/lilith-kroot-dev-synthetic-public"
stop() { echo "STOP: $*" >&2; exit 1; }
sha_is() { [ "$(sha256sum "$1" | cut -d' ' -f1)" = "$2" ]; }
kroot_meta() { stat -c '%n %a %s %i %Y' "$K" "$K/k-root.der"; ls -A "$K"; sha256sum "$P"/*; }
# ---- B: before-state (read-only) ----
[ -z "${SSH_CONNECTION-}${SSH_CLIENT-}${SSH_TTY-}" ] || stop "SSH session"
test ! -e "$A" && test ! -e "$S" || stop "an archive already exists"
test -d "$HOME/lilith-mb3/sign" && test -f "$HOME/lilith-mb3/sign/attempt.json" || stop "not the attempt-1 staging"
test ! -e "$HOME/lilith-mb3/sign/registry-v1.stdout" && test ! -e "$HOME/lilith-mb3/burn" || stop "signer output or burn present"
test ! -e "$HOME/lilith-mb3-registry-public" && test ! -e "$HOME/lilith-mb3-export.tar" || stop "success-format output present"
sha_is "$HOME/lilith-mb3/mb3-inputs.json" "$MANIFEST_SHA" || stop "manifest is not the attempt-1 manifest"
sha_is "$HOME/lilith-mb3-failure-export.tar" "$FAILURE_SHA" || stop "failure export differs"
grep -q '"invoked": false' "$HOME/lilith-mb3/evidence/sign-outcome.json" || stop "outcome is not invoked=false"
grep -q '"outcome": "A_NO_SIGNATURE"' "$HOME/lilith-mb3/evidence/sign-outcome.json" || stop "outcome is not A_NO_SIGNATURE"
test "$(ls -A "$K")" = k-root.der || stop "K-ROOT directory is not exactly k-root.der"
BEFORE=$(kroot_meta) || stop "cannot read K-ROOT metadata"
echo DISPOSITION_BEFORE_STATE_OK
# ---- M: archive by rename (no deletion) ----
mkdir -m 700 "$A" "$A/downloads"
mv "$HOME/lilith-mb3" "$A/lilith-mb3"
mv "$HOME/lilith-mb3-failure-export.tar" "$A/"
if [ -e "$HOME/lilith-mb3-prepare.transcript.txt" ]; then mv "$HOME/lilith-mb3-prepare.transcript.txt" "$A/"; fi
for pair in "mb3_phone_ceremony.py $SCRIPT_SHA" "lilith-mb3-registry-1f544e6.tar $BUNDLE_SHA" \
            "mb3-kact-publication.json $KACT_SHA" "mb3-kwit-publication.json $KWIT_SHA" \
            "lilith-mb3-prepare-readback.tar $READBACK_SHA" "lilith-mb3-failure-export.tar $FAILURE_SHA"; do
  set -- $pair
  if [ -e "$DL/$1" ]; then
    sha_is "$DL/$1" "$2" || stop "Download/$1 is not the attempt-1 file; left in place"
    mv "$DL/$1" "$A/downloads/$1"
  fi
done
# ---- V: after-state ----
(cd "$A" && find . -type f | LC_ALL=C sort | while read -r f; do sha256sum "$f"; done) > "$S"
test ! -e "$HOME/lilith-mb3" && test ! -e "$HOME/lilith-mb3-failure-export.tar" || stop "staging still present"
test ! -e "$HOME/lilith-mb3-registry-public" && test ! -e "$HOME/lilith-mb3-export.tar" || stop "unexpected output"
test ! -e "$DL/mb3_phone_ceremony.py" || stop "attempt-1 script still in Download"
sha_is "$A/lilith-mb3/mb3-inputs.json" "$MANIFEST_SHA" || stop "archived manifest differs"
sha_is "$A/lilith-mb3-failure-export.tar" "$FAILURE_SHA" || stop "archived failure export differs"
test -f "$A/lilith-mb3/sign/attempt.json" || stop "attempt marker not archived"
AFTER=$(kroot_meta) || stop "cannot read K-ROOT metadata"
[ "$BEFORE" = "$AFTER" ] || stop "K-ROOT metadata or public anchor changed"
echo "ARCHIVE_SHA256 $(sha256sum "$S" | cut -d' ' -f1)"
echo MB3_ATTEMPT1_DISPOSITION_COMPLETE
```

**Expected result:**

- `DISPOSITION_BEFORE_STATE_OK`, then `ARCHIVE_SHA256 <hex>`, then
  `MB3_ATTEMPT1_DISPOSITION_COMPLETE`. The owner records the archive hash.
- **After:** the four PREPARE-blocking paths are absent; the attempt-1 script
  is no longer in Download; the archive holds the attempt marker, manifest,
  candidate, PREPARE evidence, failure export and public inputs.
- **K-ROOT:** directory and file metadata, the name listing and the public
  anchor hashes are identical before and after.

**On any STOP:** do not retry or delete. Report the transcript for review.

## 9. Authorization posture

```text
M-B1 / GENERATE_K_ROOT = COMPLETED / ACCEPTED
M-B2 / GENERATE_K_WIT = COMPLETED / ACCEPTED
FIRST M-B3 PREPARE CANDIDATE = HISTORICAL / ABANDONED / UNSIGNED / NOT BURNED
FIRST M-B3 SIGN GO = CONSUMED
FIRST M-B3 SEQUENCE = ENDED
M-B3 / REGISTRY_SIGNED = NOT REACHED
REPLACEMENT M-B3 PREPARATION SEQUENCE = NOT AUTHORIZED
PHONE INCIDENT CLEANUP = NOT AUTHORIZED
NEW PREPARE = NOT AUTHORIZED
NEW SIGN GO = NOT AUTHORIZED
M-B4/M-B5 = NOT AUTHORIZED
REGISTRY EFFECTIVENESS = NOT AUTHORIZED
GENESIS = NOT AUTHORIZED
RECORD 1 = NOT AUTHORIZED
FIRST MEMORY = NOT AUTHORIZED
PROD = NOT AUTHORIZED
FRESHNESS=UNKNOWN
```

## 10. State

```text
MB3_SIGN_ATTEMPT_1 = CLOSED / INCIDENT / A_NO_SIGNATURE
INCIDENT_ROOT_CAUSE = _tty_confirm open("/dev/tty", "r+"): text r+ requires seekability; a terminal is not seekable
SIGNER_INVOKED = NO
KROOT_ACCESSED = NO
PASSPHRASE_PROMPT_REACHED = NO
SIGNATURE_POSSIBLE = NO
BURN_STATUS = NO_REAL_REGISTRY_BURN
CANDIDATE b7e24530a21757a5bef996ec9adb13ed5932ab04edb1943321f529e3206c0e53 = HISTORICAL_ABANDONED_UNSIGNED_CANDIDATE
HISTORICAL_ABANDONED_UNSIGNED_CANDIDATE != BURNED_REGISTRY_DIGEST
HISTORICAL RETENTION != PERMISSION TO REUSE
ATTEMPT-1 PHONE SCRIPT db02909d8f769f5a0570386aef55c3a472bdbc6c52949830ab94c1b624e6bd54 = SUPERSEDED
PRE-MERGE FIXED PHONE SCRIPT b58b93215dc5c1e724846c7fc16acc2c29d81725a2ba13badcdccfd7b9eaecc7
PACKAGE_REFINALIZATION_REQUIRED = YES
PHONE DISPOSITION PROCEDURE = REVIEWED HERE; NOT AUTHORIZED
NO LIVE SYSTEM CONTACTED BY THIS RECORD; NO K-ROOT OR K-WIT ACCESS; NOTHING SIGNED
```
