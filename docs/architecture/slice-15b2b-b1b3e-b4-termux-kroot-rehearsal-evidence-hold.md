# Slice 15B2b-B1b-3e — B-4 Termux K-ROOT Rehearsal: Evidence Received (Hold)

Status:

- **`B4_TERMUX_KROOT_REHEARSAL=PASS_OBSERVED`**
- **`B4_REVIEWED_GATE_EVIDENCE=INCOMPLETE`**
- **Classification: `B4_REHEARSAL_EVIDENCE_HOLD`**
- **The B-4 rehearsal is NOT accepted.** `B4_TERMUX_KROOT_REHEARSAL=ACCEPTED`
  is **not** recorded. The owner chose to hold and collect the missing
  evidence first
- This record is documentation only. It changes no ceremony logic, gate,
  owner tooling, phone tooling, or acceptance flag. No phone contact was
  made to prepare it
- **Real M-B1 NOT AUTHORIZED**; **PR-1B NOT AUTHORIZED**

```text
PASS observed != reviewed gate proven != rehearsal accepted
rehearsal key != K-ROOT;  rehearsal PASS != M-B1 authorization
```

| Field | Value |
| --- | --- |
| Control `main` | `9d83f5c9c58112f57cb15e927a69158d46e415cf` |
| Reviewed operator script | `353c988f67cd855372c7037f0b55d8655af63d52bb4ac26a44f1d43a7c98d6a7` ([staging](slice-15b2b-b1b3e-b4-termux-kroot-rehearsal-staging.md) §3) |
| Bundle | `lilith-b4-kroot-rehearsal-ff13bc6.tar`, `659c50a4…0b3` |
| Evidence received | `lilith-b4-rehearsal-evidence.tar`, laptop-received |
| Review gate | [rehearsal preparation](slice-15b2b-b1b3e-b4-termux-kroot-rehearsal.md) §6.3 |

## 1. Evidence received

**Laptop-received archive:** `lilith-b4-rehearsal-evidence.tar`, SHA-256
`96d188c14d28b56f58163efdd2a7634ed3bebf159f83df24a4a329176bdc374e`.

- This hash was computed on the **laptop, after** the MTP copy. No
  phone-side pre-transfer hash is available. It is **not** proof of MTP
  transport integrity.
- Members are owned by the Termux uid (`u0_a492`), mode `0600`, under a
  single `evidence/` directory.

| Member | Size | SHA-256 |
| --- | --- | --- |
| `gate.txt` | 721 | `425377f848fb959aa6ad81eabceddaf7d6ae6184bee16b643d41732674ce64a7` |
| `rehearsal.exit` | 7 | `19eaf43821a7660ec323a87c8457bf74823beb296c39f5e01aa8a683aa50f061` |
| `rehearsal.json` | 1851 | `557176d7b6fe9e05e1adcde86a8fff2a7cca775d3a8ab3b2e77ee9a39cc0a0e8` |
| `rehearsal.stderr` | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| `replica-b-before.txt` | 423 | `e4587f324a6ec346aa8fa295a9d46a4204d453f1ea3bff8ae1f1f7007a136a61` |
| `replica-b-after.txt` | 423 | `e4587f324a6ec346aa8fa295a9d46a4204d453f1ea3bff8ae1f1f7007a136a61` |

Every member hash was recomputed on the laptop and equals the
owner-reported value.

## 2. Observed facts (valid)

| Fact | Source |
| --- | --- |
| `rehearsal.exit` = `exit=0` | file |
| `B4_KROOT_REHEARSAL=PASS` (final line of `rehearsal.json`), `REHEARSAL=PASS`, all 17 checks `PASS`, `testOnly: true`, `realAuthorityMaterial: NONE`, the seven expected `removedEntries` | file |
| `REHEARSAL_GATE_PASS` | `gate.txt`. The reviewed gate program (staging §3), re-run on the laptop against the received `rehearsal.json`, reproduces `gate.txt` **byte for byte** |
| exactly **6** TEST identities burned (§4) | file |
| environment: Python `3.14.6`, `cryptography` `50.0.1`, `aarch64`, `Android` | `rehearsal.json`, `gate.txt` |
| `rehearsal.stderr` is 0 bytes | file |
| Replica B manifest `c068e5331ccd7fa0f69f2b38d25849497b86edea843598784235874080c107c4`, before and after | file |
| Replica B record count `0`, before and after; entries `REPLICA.json records` | file |
| before and after snapshots are **byte-identical**, including inode, mode, size, and mtime of the replica, `REPLICA.json`, and `records/` | file |
| Replica B at the canonical `$HOME/lilith-owner-offline-dev-synthetic-01` | stat paths in the file |
| the nested non-canonical path remained absent | **owner-reported**; no transferred file shows it |
| USB disconnected and Airplane Mode ON for the rehearsal and every gate, cleanup, and Replica B check; USB connected later only for MTP export | **owner attestation** |
| no real K-ROOT was intentionally created | owner attestation; the rehearsal writes only TEST names |

## 3. Gaps against the reviewed gate

1. **The Replica B snapshots were not produced by the reviewed
   `353c988f` `snap()`.**
   - There is no `parent` line.
   - The stat paths are full paths, not `~`-shortened.
   - So the exact `REPLICA_B_BASELINE_OK` gate is **not evidenced**. That
     gate requires the `parent` line, so the reviewed block would have
     printed `STOP` on this file.
2. **The transferred archive lacks:**
   - `verify.txt`;
   - `g0.txt`;
   - `evidence.sha256` (the reviewed block writes it to
     `~/lilith-b4-rehearsal/`, outside `evidence/`);
   - a reviewed stdout transcript, or any equivalent proof that the exact
     operator gates ran.
3. **Therefore this record does NOT claim, as §6.3 reviewed-gate proof:**
   - `TMP_CLEAN`;
   - `NO_KEY_FILE_ANYWHERE`;
   - `BUNDLE_UNCHANGED`;
   - `REPLICA_B_UNCHANGED`.

   The byte-identical before and after files are valid observations, but
   they are not the reviewed gate's output.

## 4. Burned TEST identities

These are permanently burned, whatever the outcome of this hold. None may
ever be used or accepted in M-B1, M-B2, the real registry v1, the witness
genesis or genesis pin, record 1, any acceptance envelope, or any later
lineage.

| Identity | Value |
| --- | --- |
| `rehearsalCliRootPublicKeySha256` | `1273ab2ef653dab08042a278729bb70812086a46ee2d5ad79272d044f5ba3d95` |
| `rehearsalGenesisCandidateDigest` | `c4c095d8b0bcb918555c291362bbcba84a8fe221f7d9de8717c629c1c4733e04` |
| `rehearsalRegistryDigest` | `c97a689bf9b0c928fc5764b4d1cdff187009bc3464d82da43d4955e1c8a74034` |
| `rehearsalRootPublicKeySha256` | `d68033f06e49b3de6ea6f30b7cbd9c8c2fefd266ff961f4a7d4819e9c99a3def` |
| `syntheticKActPublicKeySha256` | `a20368b64e6168c0cb77f054e63edb3b705f7c1053536a88a92c957579dd7ce0` |
| `syntheticKWitPublicKeySha256` | `e1320162d98565e1f946cf287bb3b5fa0e162301e29dd60bae5596f7dfb03654` |

The real M-B1 review must check that the real K-ROOT fingerprint is none of
these, nor any identity burned by the offline pre-checks.

## 5. What can and cannot be reconstructed read-only

**Can be established now, read-only (post-hoc, as the state at collection
time):**

- whether the original `g0.txt`, `verify.txt`, and `evidence.sha256` exist
  on the phone after all. If they do, they are copied unchanged. They are
  run-time evidence, not reconstructions;
- the environment (`g0.txt` equivalent): `HOME` and `TMPDIR` in Termux
  private storage, plus the Python / `cryptography` / machine versions;
- bundle integrity now: tar `659c50a4…`, `SHA256SUMS` `dbb9dfbe…`, source
  commit `ff13bc6`, 75 files, `sha256sum -c`;
- `TMP_CLEAN`, `NO_KEY_FILE_ANYWHERE` (also over `TMPDIR` and the rehearsal
  output names), `STDERR_EMPTY`, and the transport copy's absence;
- **Replica B unchanged across the whole interval.** A snapshot in the
  exact captured format is compared byte for byte with
  `replica-b-before.txt`. Equality means the same inode, mode, size, and
  mtime as the pre-rehearsal baseline, which is stronger than a post-run
  check alone;
- the exact reviewed `snap()` and `REPLICA_B_BASELINE_OK` gate, including
  the `parent` line, evaluated now;
- `NESTED_REPLICA_ABSENT`, now;
- a phone-side hash of the earlier archive, if a copy is still on the
  phone. That is a phone-side hash taken now, not a pre-transfer hash;
- the owner's typed commands, from `~/.bash_history` if present. They are
  commands only, not their output.

**Cannot be reconstructed after the fact:**

- proof that the **exact reviewed `353c988f` block** ran at the time;
- the **run-time** G0 tokens: `STAGING_ABSENT`, `TMP_NO_STALE`,
  `NO_KROOT_FILES_BEFORE`, and `NESTED_REPLICA_ABSENT` before R1;
- the **pre-R1** bundle verification: `BUNDLE_VERIFIED`,
  `SOURCE_COMMIT_OK`, `FILE_COUNT_OK`, `BUNDLE_IN_TERMUX_PRIVATE`. It can be
  shown now only;
- the `parent` listing at baseline time;
- the **immediate post-run** `verify.txt` tokens. They can be shown now
  only;
- the run-time stdout transcript;
- a true pre-transfer hash of the earlier archive;
- airplane mode and USB state during R1. These are owner attestation
  either way, as the reviewed block always intended.

## 6. Read-only collection commands (phone, owner-executed)

> **Revision v2 (2026-09-29, before any owner execution).** The first
> version (`99e4d95d…38a5`) is **withdrawn and must not be run**. The review
> found three defects:
>
> 1. Its `cond && echo PASS || echo "STOP: …"` gates printed STOP and
>    **kept going**.
> 2. Several gates sat inside `{ …; } | tee`. There, even an `exit` leaves
>    only the pipeline subshell, so the script still continued.
> 3. Its seal `sha256sum -- $(ls) > SHA256SUMS` hashed the partly written
>    `SHA256SUMS` itself on any rerun. It also word-split file names and
>    never verified the seal.
>
> v2 below corrects all three.

**Boundaries:**

- It generates no key. It does not run the rehearsal, `root-keygen`,
  `registry-v1`, `witness-anchor`, or any LILITH tool.
- It reads Replica B, `~/lilith-b4-rehearsal/`, and TMPDIR, and writes or
  deletes nothing in them. A leftover file is reported, never removed.
- **The only writes:**
  - a new directory `~/lilith-b4-readonly-check/` of new text files,
    including `gates.txt` and, on a STOP, `STOP.txt`;
  - its tar `~/lilith-b4-readonly-check.tar`.

  The script refuses to start if either already exists. Neither name
  matches `lilith-owner*`, so neither affects the `parent` line.
- It changes no authority state.

**Hard stops.** Every safety failure calls `stop`. That prints
`STOP: …` on stderr, appends it to `STOP.txt` once the check directory
exists, and **exits 1 at once**. No gate runs inside a pipeline or a
subshell whose exit could be swallowed. On a STOP, nothing later runs: no
further gate, no seal, no tar. The hard-stop gates are:

- the preconditions: `HOME` and `TMPDIR` in Termux private storage; the
  evidence directory and Replica B present; the check directory and tar
  absent;
- the six received evidence files unchanged (hashes of §1);
- the bundle tar hash, the `SHA256SUMS` digest, the source commit, the
  75-file count, and `sha256sum -c --strict`;
- TMPDIR holding no rehearsal workdir;
- the leftover TEST key or output search;
- `rehearsal.stderr` empty;
- Replica B equal to the baseline and to the after-snapshot;
- the reviewed `REPLICA_B_BASELINE_OK` gate;
- the nested Replica B absent;
- the seal.

**Informational only (prefixed `INFO`, deliberately non-fatal):**

- `ORIGINAL_PRESENT` or `ORIGINAL_ABSENT` for `g0.txt`, `verify.txt`, and
  `evidence.sha256`;
- the transport tar still in Download;
- no earlier archive on the phone;
- whether history was collected.

**Leftover search scope.**

- The rehearsal writes only inside
  `$TMPDIR/.lilith-b4-kroot-rehearsal-TEST-*`. The search also covers all
  of `$HOME`, as the reviewed gate did.
- It matches `k-root*`, `*REHEARSAL-TEST*`, and the rehearsal's output
  names (`kact.json`, `kwit.json`, `root-anchor.json`,
  `witness-anchor.json`, `registry.json`).
- It **cannot falsely match the bundle**: none of its 75 names match (checked
  against the tar listing, and pinned by C3). The P3-3B bundle has no match
  either.
- The check directory is pruned. Its fixed names never match anyway.
- Any match elsewhere in `$HOME` is a hard STOP. That fails safe.

**Seal (C8).**

- `SHA256SUMS` covers every regular file in the check directory **except
  itself**. It is written as `SHA256SUMS.partial` from a NUL-separated,
  `LC_ALL=C`-sorted `find`, which excludes both names, then renamed.
- The seal is verified before the tar with `sha256sum -c --strict`, plus
  two checks: the file count equals the line count, and there is no
  self-entry.
- A subdirectory in the check directory fails the seal.
- Nothing is written into the check directory after the seal.

**How to run.**

1. Copy `b4_readonly_collect.sh` by MTP into Download. The laptop copy is at
   `%USERPROFILE%\lilith-b4-evidence\`.
2. Check its hash in Termux:
   `sha256sum "$HOME/storage/downloads/b4_readonly_collect.sh"`. It must be
   the SHA-256 below.
3. Unplug, and turn airplane mode ON.
4. Run `bash "$HOME/storage/downloads/b4_readonly_collect.sh"`.

**Do not paste it** into an interactive shell: `exit 1` would close the
Termux session. `INCLUDE_HISTORY=1 bash …` also collects matching
`~/.bash_history` lines. That is off by default; review them on the phone
before export.

**The phone-side pre-transfer hash.** The last line is
`PHONE_SIDE_PRE_TRANSFER_SHA256 <hash>`. Write it down **before** the MTP
copy.

**Offline check (laptop / WSL; no phone).** Simulated Termux layout that
mirrors the received evidence. For the simulation only, the two expected
Replica B evidence hashes are replaced by the simulated files' hashes;
nothing else differs.

| Case | Exit | Result |
| --- | --- | --- |
| clean | **0** | every PASS token, `ALL_GATES_PASS`, `SEAL_VERIFIED`. The seal re-verifies (8 files, 8 lines, no self-entry). The printed tar hash equals the actual one. Nothing outside the check directory and tar changed (apart from `$HOME`'s own mtime) |
| leftover `k-root.REHEARSAL-TEST.der` in TMPDIR | **1** | `STOP: a TEST key or rehearsal output file remains`; no seal, no tar |
| modified `REPLICA.json` (mtime) | **1** | `STOP: Replica B differs from the pre-rehearsal baseline`; no seal, no tar |
| nested Replica B | **1** | `STOP: a second Replica B exists at the old nested path`; no seal, no tar |
| existing check directory | **1** | `STOP: … already exists`; the existing content is untouched |
| existing check tar | **1** | `STOP: … already exists`; the existing tar is untouched |
| bad bundle hash | **1** | `STOP: bundle tar hash differs or tar missing`; no seal, no tar |
| stale TMPDIR rehearsal workdir | **1** | `STOP: rehearsal directory present in TMPDIR` |
| unpatched script vs. the simulated evidence | **1** | `STOP: evidence/replica-b-before.txt differs from the received archive` |

Script SHA-256 (v2):
`05ff0e3916373ea7f47cd08a07cdf01a4271b1f2612c794b6e112735b5003920`.

```bash
# ===== B-4 post-hoc READ-ONLY evidence collection (Termux, S25) — v2 =====
# Run ONLY as a file:  bash "$HOME/storage/downloads/b4_readonly_collect.sh"   (never paste it line by line)
# Generates NO key. Does NOT run the rehearsal, root-keygen, registry-v1, witness-anchor, or any LILITH tool.
# Reads Replica B, the rehearsal staging directory, and TMPDIR only; writes and deletes nothing there.
# The ONLY writes: the new directory $X (new text files) and the new tar $XT.
# Every STOP is a hard stop: it prints "STOP: ..." on stderr and exits 1 at once; nothing after it runs.
# Optional: INCLUDE_HISTORY=1 bash <file> also copies matching ~/.bash_history lines (review before export).
set -u
W="$HOME/lilith-b4-rehearsal"
E="$W/evidence"
B="$W/lilith-b4-kroot-rehearsal-ff13bc6"
TAR=lilith-b4-kroot-rehearsal-ff13bc6.tar
R="$HOME/lilith-owner-offline-dev-synthetic-01"
TMP="${TMPDIR:-$PREFIX/tmp}"
X="$HOME/lilith-b4-readonly-check"
XT="$HOME/lilith-b4-readonly-check.tar"
XMADE=0
stop() { echo "STOP: $*" >&2; [ "$XMADE" = 1 ] && echo "STOP: $*" >> "$X/STOP.txt"; exit 1; }
pass() { echo "$1"; [ "$XMADE" = 1 ] && echo "$1" >> "$X/gates.txt"; return 0; }
info() { echo "INFO $1"; [ "$XMADE" = 1 ] && echo "INFO $1" >> "$X/gates.txt"; return 0; }
priv() { case "$(realpath "$1")/" in /data/data/com.termux/*|/data/user/0/com.termux/*) return 0;; *) return 1;; esac; }
sha_of() { test -f "$1" || return 1; sha256sum "$1" | cut -d' ' -f1; }
# snap: byte-for-byte the reviewed snapshot of operator script 353c988f
snap() { echo "sha $(sha256sum "$R/REPLICA.json" | cut -d' ' -f1)"; echo "records $(ls -A "$R/records" | wc -l)"
         echo "entries $(ls -A "$R" | LC_ALL=C sort | tr '\n' ' ')"; echo "parent $(ls -A "$HOME" | grep '^lilith-owner' | LC_ALL=C sort | tr '\n' ' ')"
         stat -c '%n %i %a %s %Y' "$R" "$R/REPLICA.json" "$R/records" | sed "s#$HOME#~#"; }
# snap_raw: the format actually captured in replica-b-before.txt (no parent line, full stat paths)
snap_raw() { echo "sha $(sha256sum "$R/REPLICA.json" | cut -d' ' -f1)"; echo "records $(ls -A "$R/records" | wc -l)"
             echo "entries $(ls -A "$R" | LC_ALL=C sort | tr '\n' ' ')"
             stat -c '%n %i %a %s %Y' "$R" "$R/REPLICA.json" "$R/records"; }

# ---- C0 preconditions (read-only), then the one new directory ----
cd "$HOME" || stop "cannot cd to HOME"
priv "$HOME" || stop "HOME is not Termux private storage"
test -d "$TMP" && priv "$TMP" || stop "TMPDIR missing or not Termux private storage"
test -d "$E" || stop "$E missing"
test -f "$R/REPLICA.json" && test -d "$R/records" || stop "Replica B missing at $R"
test ! -e "$X" || stop "$X already exists"
test ! -e "$XT" || stop "$XT already exists"
mkdir -m 700 "$X" || stop "cannot create $X"
XMADE=1
pass CHECK_DIR_CREATED

# ---- C1 received evidence unchanged; inventory; originals copied into $X if present ----
while read -r want name; do
  test "$(sha_of "$E/$name")" = "$want" || stop "evidence/$name differs from the received archive"
done <<'SUMS'
425377f848fb959aa6ad81eabceddaf7d6ae6184bee16b643d41732674ce64a7 gate.txt
19eaf43821a7660ec323a87c8457bf74823beb296c39f5e01aa8a683aa50f061 rehearsal.exit
557176d7b6fe9e05e1adcde86a8fff2a7cca775d3a8ab3b2e77ee9a39cc0a0e8 rehearsal.json
e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855 rehearsal.stderr
e4587f324a6ec346aa8fa295a9d46a4204d453f1ea3bff8ae1f1f7007a136a61 replica-b-before.txt
e4587f324a6ec346aa8fa295a9d46a4204d453f1ea3bff8ae1f1f7007a136a61 replica-b-after.txt
SUMS
pass EVIDENCE_UNCHANGED_NOW
{ date -u +%Y-%m-%dT%H:%M:%SZ; ls -la "$W" "$E"; } > "$X/inventory.txt" || stop "inventory failed"
sha256sum "$E"/* > "$X/evidence-now.sha256" || stop "evidence hashing failed"
for f in g0.txt verify.txt; do
  if test -f "$E/$f"; then cp "$E/$f" "$X/original-$f" || stop "copy of $f failed"; info "ORIGINAL_PRESENT $f"; else info "ORIGINAL_ABSENT $f"; fi
done
if test -f "$W/evidence.sha256"; then cp "$W/evidence.sha256" "$X/original-evidence.sha256" || stop "copy of evidence.sha256 failed"; info "ORIGINAL_PRESENT evidence.sha256"
else info "ORIGINAL_ABSENT evidence.sha256"; fi

# ---- C2 environment now (post-hoc equivalent of g0.txt) ----
{ echo "HOME_PRIVATE yes"; echo "TMP_PRIVATE yes"
  python -c 'import sys, platform, cryptography as c; print("PYTHON", sys.version.split()[0], "CRYPTOGRAPHY", c.__version__, "MACHINE", platform.machine())'; } > "$X/g0-now.txt" || stop "environment probe failed"
cat "$X/g0-now.txt"

# ---- C3 bundle integrity now ----
test "$(sha_of "$W/$TAR")" = 659c50a476c85ff9ed005af97bc70a48989a87890ec53b23f940d97901bee0b3 || stop "bundle tar hash differs or tar missing"
pass BUNDLE_TAR_OK_NOW
test "$(sha_of "$B/SHA256SUMS")" = dbb9dfbeaeefb59e47cb2ae64aaa651bbe9b89daa443e0912787c10d0b0e2288 || stop "SHA256SUMS digest differs"
pass SHA256SUMS_DIGEST_OK_NOW
test "$(cat "$B/SOURCE_COMMIT" 2>/dev/null)" = ff13bc6f72156c332b29ad1605d24410c2abf232 || stop "source commit differs"
pass SOURCE_COMMIT_OK_NOW
test "$(find "$B" -type f | wc -l)" = 75 || stop "bundle file count is not 75"
(cd "$B" && sha256sum -c --quiet --strict SHA256SUMS) || stop "bundle files fail sha256sum -c"
pass BUNDLE_UNCHANGED_NOW

# ---- C4 no TEST key or rehearsal output left; TMPDIR clean; stderr empty (matches are reported, NOT deleted) ----
# The rehearsal writes only inside "$TMP"/.lilith-b4-kroot-rehearsal-TEST-*; $HOME is searched too, as in the reviewed gate.
# $X is pruned (its fixed names never match); the bundle is not pruned (none of its 75 names match, and C3 pins it).
ls -A "$TMP" | grep -q lilith-b4-kroot-rehearsal && stop "rehearsal directory present in TMPDIR"
pass TMP_CLEAN_NOW
find "$HOME" "$TMP" -path "$X" -prune -o \( -name 'k-root*' -o -name '*REHEARSAL-TEST*' -o -name 'kact.json' -o -name 'kwit.json' \
     -o -name 'root-anchor.json' -o -name 'witness-anchor.json' -o -name 'registry.json' \) -print 2>/dev/null > "$X/key-file-matches.txt"
test -s "$X/key-file-matches.txt" && stop "a TEST key or rehearsal output file remains (see $X/key-file-matches.txt)"
pass NO_KEY_FILE_ANYWHERE_NOW
test -f "$E/rehearsal.stderr" && ! test -s "$E/rehearsal.stderr" || stop "rehearsal.stderr missing or not empty"
pass STDERR_EMPTY_NOW
if test -e "$HOME/storage/downloads/$TAR"; then info "TRANSPORT_COPY_STILL_IN_DOWNLOAD (not removed here)"; else info TRANSPORT_COPY_ABSENT_NOW; fi

# ---- C5 Replica B now (read-only) ----
snap_raw > "$X/replica-b-now.raw.txt" || stop "raw Replica B snapshot failed"
snap > "$X/replica-b-now.reviewed.txt" || stop "reviewed Replica B snapshot failed"
cat "$X/replica-b-now.raw.txt" "$X/replica-b-now.reviewed.txt"
cmp -s "$E/replica-b-before.txt" "$X/replica-b-now.raw.txt" || stop "Replica B differs from the pre-rehearsal baseline"
pass REPLICA_B_UNCHANGED_SINCE_BASELINE
cmp -s "$E/replica-b-after.txt" "$X/replica-b-now.raw.txt" || stop "Replica B differs from the post-rehearsal snapshot"
pass REPLICA_B_UNCHANGED_SINCE_AFTER
grep -qx "sha c068e5331ccd7fa0f69f2b38d25849497b86edea843598784235874080c107c4" "$X/replica-b-now.reviewed.txt" \
  && grep -qx "records 0" "$X/replica-b-now.reviewed.txt" \
  && grep -qE "^parent (.* )?lilith-owner-offline-dev-synthetic-01 " "$X/replica-b-now.reviewed.txt" || stop "reviewed baseline gate fails now"
pass REPLICA_B_BASELINE_OK_NOW
test ! -e "$HOME/lilith-owner-freshness/owner-offline-dev-synthetic-01" || stop "a second Replica B exists at the old nested path"
pass NESTED_REPLICA_ABSENT_NOW

# ---- C6 phone-side hash of the earlier evidence archive, if a copy is still on the phone (informational) ----
for t in "$HOME/lilith-b4-rehearsal-evidence.tar" "$W/lilith-b4-rehearsal-evidence.tar" "$HOME/storage/downloads/lilith-b4-rehearsal-evidence.tar"; do
  test -f "$t" && sha256sum "$t" | sed "s#$HOME#~#"; done > "$X/earlier-archive-phone-side.sha256"
if test -s "$X/earlier-archive-phone-side.sha256"; then cat "$X/earlier-archive-phone-side.sha256"; else info NO_EARLIER_ARCHIVE_ON_PHONE; fi

# ---- C7 optional, PRIVATE (INCLUDE_HISTORY=1 only): typed commands, not their output ----
if [ "${INCLUDE_HISTORY:-0}" = 1 ] && test -f "$HOME/.bash_history"; then
  grep -n -E 'lilith|snap|REPLICA|rehears|replica-b|g0\.txt|verify\.txt|evidence' "$HOME/.bash_history" > "$X/history-excerpt.txt"
  info "HISTORY_EXCERPT_LINES $(wc -l < "$X/history-excerpt.txt")"
else info HISTORY_NOT_COLLECTED; fi

# ---- C8 seal: hash every file in $X except SHA256SUMS itself, verify the seal, then tar ----
pass ALL_GATES_PASS
( cd "$X" || exit 1
  find . -maxdepth 1 -type d ! -name . | grep -q . && exit 1
  find . -maxdepth 1 -type f ! -name SHA256SUMS ! -name SHA256SUMS.partial -print0 | LC_ALL=C sort -z | xargs -0 sha256sum -- > SHA256SUMS.partial || exit 1
  mv SHA256SUMS.partial SHA256SUMS || exit 1
  sha256sum -c --quiet --strict SHA256SUMS || exit 1
  test "$(find . -maxdepth 1 -type f ! -name SHA256SUMS | wc -l)" = "$(wc -l < SHA256SUMS)" || exit 1
  ! grep -q ' \./SHA256SUMS$' SHA256SUMS ) || stop "seal failed"
XMADE=2                                            # sealed: nothing more is written into $X
echo SEAL_VERIFIED
cat "$X/SHA256SUMS"
tar -cf "$XT" -C "$HOME" lilith-b4-readonly-check || stop "tar failed"
echo "PHONE_SIDE_PRE_TRANSFER_SHA256 $(sha256sum "$XT" | cut -d' ' -f1)"
# Write down this last hash on the phone screen BEFORE the MTP copy; it is the phone-side pre-transfer hash.
# Transfer (owner choice): cp "$XT" "$HOME/storage/downloads/" then MTP to the laptop.
# ============================== end of read-only collection ==============================
```

**Expected PASS output, in order:**

- `CHECK_DIR_CREATED`, `EVIDENCE_UNCHANGED_NOW`;
- three `INFO ORIGINAL_PRESENT|ORIGINAL_ABSENT …` lines;
- the `g0-now.txt` lines;
- `BUNDLE_TAR_OK_NOW`, `SHA256SUMS_DIGEST_OK_NOW`, `SOURCE_COMMIT_OK_NOW`,
  `BUNDLE_UNCHANGED_NOW`;
- `TMP_CLEAN_NOW`, `NO_KEY_FILE_ANYWHERE_NOW`, `STDERR_EMPTY_NOW`;
- `INFO TRANSPORT_COPY_…`;
- the raw and reviewed Replica B snapshots. The reviewed one includes
  `parent lilith-owner-offline-dev-synthetic-01`;
- `REPLICA_B_UNCHANGED_SINCE_BASELINE`, `REPLICA_B_UNCHANGED_SINCE_AFTER`,
  `REPLICA_B_BASELINE_OK_NOW`, `NESTED_REPLICA_ABSENT_NOW`;
- the earlier-archive hash lines or `INFO NO_EARLIER_ARCHIVE_ON_PHONE`;
- `INFO HISTORY_…`;
- `ALL_GATES_PASS`, `SEAL_VERIFIED`, the `SHA256SUMS` listing;
- `PHONE_SIDE_PRE_TRANSFER_SHA256 <hash>`.

Exit status `0`.

**On any STOP (exit 1):**

- Do not retry, delete, move, or edit anything. That includes the partial
  check directory: it is evidence of where the run stopped.
- Report the STOP line.

**For the review, the owner reports:**

- `lilith-b4-readonly-check.tar`;
- the `PHONE_SIDE_PRE_TRANSFER_SHA256` written down before transfer;
- the laptop-side hash after transfer.

## 7. Is a fresh TEST rehearsal required?

**Not for capability, and not if §6 passes.**

- The capability that B-4 needed proven is shown by `rehearsal.json`, whose
  gate is reproduced byte for byte on the laptop: `root-keygen`,
  `registry-v1`, and `reproduce` under Termux on the S25.
- A clean §6 establishes the safety properties §6.3 guards:
  - no TEST key or output anywhere;
  - TMPDIR clean;
  - the bundle intact;
  - Replica B byte-for-byte at its pre-rehearsal inode, mode, size, and
    mtime;
  - no nested replica.

What would remain unproven is **procedural fidelity at run time**: that the
exact `353c988f` gates printed their tokens during the run. No read-only
step can recover that, unless §6 finds the original `verify.txt` / `g0.txt`
/ `evidence.sha256` on the phone.

The acceptance review decides:

- **(a)** A clean §6 plus the observed facts satisfies §6.3. The run-time
  gaps are recorded as accepted limitations. No new rehearsal is needed.
- **(b)** §6.3 demands the run-time transcript of the exact block. Then a
  **fresh TEST-only rehearsal** with the unchanged `353c988f` block and
  bundle is required, exported in full with a phone-side pre-transfer hash.
  It burns six more TEST identities.

**A fresh rehearsal is required regardless if §6 shows:**

- the bundle changed (the PASS would then be untrusted);
- the rehearsal output is missing or differs.

**If §6 shows a leftover TEST file:** a separately reviewed deletion is
needed. The rehearsal result itself stands, because the file is burned.

**If §6 shows Replica B changed or a nested replica:** that is a P3-3
replica-integrity incident, not a rehearsal question. Stop everything.

## 8. Blocker state (unchanged by this record)

| # | Blocker | State |
| --- | --- | --- |
| B-3 | source-level real-acceptance block | **OPEN** |
| B-4 | custody topology | **CLOSED** ([decision](slice-15b2b-b1b3e-b4-kroot-custody-decision.md)) |
| B-4 | mandatory Termux rehearsal prerequisite | **HOLD**: `PASS_OBSERVED`, reviewed-gate evidence `INCOMPLETE`; not accepted |
| B-5 | PR-1B not authorized | **OPEN** |

**`PR1B_NOT_ELIGIBLE`.**

The historical P3-3B status block ("Not executed") is stale. That is
separate historical-status debt, not addressed here.

## Explicitly not done

```text
B4_TERMUX_KROOT_REHEARSAL=ACCEPTED NOT RECORDED
NO PHONE CONTACT
NO PHONE MUTATION
NO REPLICA MUTATION
NO REAL K-ROOT
NO K-WIT
NO REGISTRY V1
NO GENESIS PIN
NO REAL RECORD 1
FRESHNESS=UNKNOWN
PR-1B NOT AUTHORIZED
FIRST MEMORY NOT AUTHORIZED
```
