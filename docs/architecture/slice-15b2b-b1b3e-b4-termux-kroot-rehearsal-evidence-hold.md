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

**Boundaries:**

- It generates no key. It does not run the rehearsal, `root-keygen`,
  `registry-v1`, `witness-anchor`, or any LILITH tool.
- It reads Replica B, `~/lilith-b4-rehearsal/`, and TMPDIR, and changes
  nothing in them. It deletes nothing: a leftover file is reported, not
  removed.
- **The only writes** are a new directory `~/lilith-b4-readonly-check/`
  with new text files, and its tar `~/lilith-b4-readonly-check.tar`. Neither
  name matches `lilith-owner*`, so neither affects the `parent` line.
- It changes no authority state.

**Airplane mode:** keep it ON and USB unplugged until C8 has printed its
last hash. Write that hash down on the phone screen **before** the MTP copy.
It is the phone-side pre-transfer hash that the first archive lacked.

**Offline check (laptop / WSL; no phone).** Under a simulated Termux layout
that mirrors the received evidence, the block below printed every PASS
token and no STOP. Nothing outside the new directory changed except
`$HOME`'s own mtime. Seeded faults each produced the intended STOP:

- a leftover `k-root*` file in TMPDIR;
- a touched `REPLICA.json`;
- a nested replica.

Block SHA-256:
`99e4d95d999e4b3130d5bfff5f0fb1bdccd58ce074a535ca98287da668d838a5`.

```bash
# ===== B-4 post-hoc READ-ONLY evidence collection (Termux, S25) =====
# Generates NO key. Does NOT run the rehearsal, root-keygen, registry-v1, witness-anchor, or any LILITH tool.
# Reads Replica B, the rehearsal staging directory, and TMPDIR only. Deletes nothing and changes nothing there.
# The ONLY write is the new directory $X, holding new text files. Every "STOP" is a hard stop.
W="$HOME/lilith-b4-rehearsal"
E="$W/evidence"
B="$W/lilith-b4-kroot-rehearsal-ff13bc6"
TAR=lilith-b4-kroot-rehearsal-ff13bc6.tar
R="$HOME/lilith-owner-offline-dev-synthetic-01"
TMP="${TMPDIR:-$PREFIX/tmp}"
X="$HOME/lilith-b4-readonly-check"
priv() { case "$(realpath "$1")/" in /data/data/com.termux/*|/data/user/0/com.termux/*) return 0;; *) return 1;; esac; }
# snap: byte-for-byte the reviewed snapshot of operator script 353c988f
snap() { echo "sha $(sha256sum "$R/REPLICA.json" | cut -d' ' -f1)"; echo "records $(ls -A "$R/records" | wc -l)"
         echo "entries $(ls -A "$R" | LC_ALL=C sort | tr '\n' ' ')"; echo "parent $(ls -A "$HOME" | grep '^lilith-owner' | LC_ALL=C sort | tr '\n' ' ')"
         stat -c '%n %i %a %s %Y' "$R" "$R/REPLICA.json" "$R/records" | sed "s#$HOME#~#"; }
# snap_raw: the format actually captured in replica-b-before.txt (no parent line, full stat paths)
snap_raw() { echo "sha $(sha256sum "$R/REPLICA.json" | cut -d' ' -f1)"; echo "records $(ls -A "$R/records" | wc -l)"
             echo "entries $(ls -A "$R" | LC_ALL=C sort | tr '\n' ' ')"
             stat -c '%n %i %a %s %Y' "$R" "$R/REPLICA.json" "$R/records"; }

# ---- C0 preconditions and the one new directory ----
cd "$HOME"
test -d "$E" && echo EVIDENCE_DIR_PRESENT || echo "STOP: $E missing"
test ! -e "$X" && mkdir -m 700 "$X" && echo CHECK_DIR_CREATED || echo "STOP: $X already exists"

# ---- C1 inventory: which original evidence files exist on the phone (read-only; copies go to $X only) ----
{ date -u +%Y-%m-%dT%H:%M:%SZ; ls -la "$W" "$E"; } > "$X/inventory.txt"; cat "$X/inventory.txt"
sha256sum "$E"/* > "$X/evidence-now.sha256"; cat "$X/evidence-now.sha256"
for f in g0.txt verify.txt; do test -f "$E/$f" && cp "$E/$f" "$X/original-$f" && echo "ORIGINAL_PRESENT $f" || echo "ORIGINAL_ABSENT $f"; done
test -f "$W/evidence.sha256" && cp "$W/evidence.sha256" "$X/original-evidence.sha256" && echo "ORIGINAL_PRESENT evidence.sha256" || echo "ORIGINAL_ABSENT evidence.sha256"

# ---- C2 environment now (post-hoc equivalent of g0.txt) ----
{ echo "HOME_PRIVATE $(priv "$HOME" && echo yes || echo no)"; echo "TMP_PRIVATE $(priv "$TMP" && echo yes || echo no)"
  python -c 'import sys, platform, cryptography as c; print("PYTHON", sys.version.split()[0], "CRYPTOGRAPHY", c.__version__, "MACHINE", platform.machine())'; } > "$X/g0-now.txt"; cat "$X/g0-now.txt"

# ---- C3 bundle integrity now ----
{ echo "$(sha256sum "$W/$TAR" | cut -d' ' -f1)" | grep -qx 659c50a476c85ff9ed005af97bc70a48989a87890ec53b23f940d97901bee0b3 && echo BUNDLE_TAR_OK_NOW || echo "STOP: bundle tar hash differs or tar missing"
  echo "$(sha256sum "$B/SHA256SUMS" | cut -d' ' -f1)" | grep -qx dbb9dfbeaeefb59e47cb2ae64aaa651bbe9b89daa443e0912787c10d0b0e2288 && echo SHA256SUMS_DIGEST_OK_NOW || echo "STOP: SHA256SUMS digest differs"
  test "$(cat "$B/SOURCE_COMMIT")" = ff13bc6f72156c332b29ad1605d24410c2abf232 && echo SOURCE_COMMIT_OK_NOW || echo "STOP: source commit differs"
  test "$(find "$B" -type f | wc -l)" = 75 && (cd "$B" && sha256sum -c --quiet SHA256SUMS) && echo BUNDLE_UNCHANGED_NOW || echo "STOP: bundle files differ"; } | tee "$X/bundle-now.txt"

# ---- C4 no TEST key left, TMPDIR clean, stderr empty (read-only; any match is reported, NOT deleted) ----
{ ls -A "$TMP" | grep -q lilith-b4-kroot-rehearsal && echo "STOP: rehearsal directory present in TMPDIR" || echo TMP_CLEAN_NOW
  find "$HOME" "$TMP" \( -name 'k-root*' -o -name '*REHEARSAL-TEST*' -o -name 'kact.json' -o -name 'kwit.json' -o -name 'root-anchor.json' -o -name 'witness-anchor.json' \) 2>/dev/null > "$X/key-file-matches.txt"
  test -s "$X/key-file-matches.txt" && echo "STOP: a TEST key or rehearsal output file remains (see key-file-matches.txt)" || echo NO_KEY_FILE_ANYWHERE_NOW
  test -s "$E/rehearsal.stderr" && echo "STOP: rehearsal.stderr is not empty" || echo STDERR_EMPTY_NOW
  test ! -e "$HOME/storage/downloads/$TAR" && echo TRANSPORT_COPY_ABSENT_NOW || echo "NOTE: transport tar still in Download (not removed here)"; } | tee "$X/verify-now.txt"

# ---- C5 Replica B now (read-only) ----
snap_raw > "$X/replica-b-now.raw.txt"; cat "$X/replica-b-now.raw.txt"
snap > "$X/replica-b-now.reviewed.txt"; cat "$X/replica-b-now.reviewed.txt"
{ cmp "$E/replica-b-before.txt" "$X/replica-b-now.raw.txt" && echo REPLICA_B_UNCHANGED_SINCE_BASELINE || echo "STOP: Replica B differs from the pre-rehearsal baseline"
  cmp "$E/replica-b-after.txt" "$X/replica-b-now.raw.txt" && echo REPLICA_B_UNCHANGED_SINCE_AFTER || echo "STOP: Replica B differs from the post-rehearsal snapshot"
  grep -qx "sha c068e5331ccd7fa0f69f2b38d25849497b86edea843598784235874080c107c4" "$X/replica-b-now.reviewed.txt" && grep -qx "records 0" "$X/replica-b-now.reviewed.txt" && grep -qE "^parent (.* )?lilith-owner-offline-dev-synthetic-01 " "$X/replica-b-now.reviewed.txt" && echo REPLICA_B_BASELINE_OK_NOW || echo "STOP: reviewed baseline gate fails now"
  test ! -e "$HOME/lilith-owner-freshness/owner-offline-dev-synthetic-01" && echo NESTED_REPLICA_ABSENT_NOW || echo "STOP: a second Replica B exists at the old nested path"; } | tee "$X/replica-b-now-gates.txt"

# ---- C6 phone-side hash of the earlier evidence archive, if a copy is still on the phone ----
for t in "$HOME/lilith-b4-rehearsal-evidence.tar" "$W/lilith-b4-rehearsal-evidence.tar" "$HOME/storage/downloads/lilith-b4-rehearsal-evidence.tar"; do
  test -f "$t" && sha256sum "$t" | sed "s#$HOME#~#"; done > "$X/earlier-archive-phone-side.sha256"; cat "$X/earlier-archive-phone-side.sha256"

# ---- C7 optional, PRIVATE: what was actually typed (review before exporting; it may hold unrelated commands) ----
test -f "$HOME/.bash_history" && grep -n -E 'lilith|snap|REPLICA|rehears|replica-b|g0\.txt|verify\.txt|evidence' "$HOME/.bash_history" > "$X/history-excerpt.txt"; wc -l < "$X/history-excerpt.txt" 2>/dev/null || echo "NO_HISTORY_FILE"

# ---- C8 seal the check directory and hash the export BEFORE any transfer ----
(cd "$X" && sha256sum -- $(ls | LC_ALL=C sort) > SHA256SUMS && cat SHA256SUMS)
tar -cf "$HOME/lilith-b4-readonly-check.tar" -C "$HOME" lilith-b4-readonly-check && sha256sum "$HOME/lilith-b4-readonly-check.tar" | sed "s#$HOME#~#"
# Write down this last hash on the phone screen BEFORE the MTP copy; it is the phone-side pre-transfer hash.
# Transfer (owner choice): cp "$HOME/lilith-b4-readonly-check.tar" "$HOME/storage/downloads/" then MTP to the laptop.
# ============================== end of read-only collection ==============================
```

**Expected PASS output, in order:**

- `EVIDENCE_DIR_PRESENT`, `CHECK_DIR_CREATED`;
- the inventory and `evidence-now.sha256`. The six hashes must equal §1;
- one `ORIGINAL_PRESENT` or `ORIGINAL_ABSENT` line each for `g0.txt`,
  `verify.txt`, and `evidence.sha256`. Either answer is reportable;
- the `g0-now.txt` lines;
- `BUNDLE_TAR_OK_NOW`, `SHA256SUMS_DIGEST_OK_NOW`, `SOURCE_COMMIT_OK_NOW`,
  `BUNDLE_UNCHANGED_NOW`;
- `TMP_CLEAN_NOW`, `NO_KEY_FILE_ANYWHERE_NOW`, `STDERR_EMPTY_NOW`,
  `TRANSPORT_COPY_ABSENT_NOW`;
- `REPLICA_B_UNCHANGED_SINCE_BASELINE`, `REPLICA_B_UNCHANGED_SINCE_AFTER`,
  `REPLICA_B_BASELINE_OK_NOW`, `NESTED_REPLICA_ABSENT_NOW`, with
  `parent lilith-owner-offline-dev-synthetic-01` in the reviewed snapshot;
- the earlier-archive hash lines (possibly none), the history line count
  (or `NO_HISTORY_FILE`), `SHA256SUMS`, and the check-archive hash.

**On any STOP:**

- Do not retry, delete, move, or edit anything.
- Keep both directories and report the output.

**For the review, the owner reports:**

- `lilith-b4-readonly-check.tar`;
- its phone-side hash, written down before transfer;
- the laptop-side hash after transfer.

C7 is optional. To keep shell history private, skip that one line: C8 then
seals the directory without it. If C7 runs, review `history-excerpt.txt`
on the phone before the transfer.

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
