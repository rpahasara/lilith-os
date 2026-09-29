# Slice 15B2b-B1b-3e — B-4 Post-Hoc Evidence Acceptance and Fresh Rehearsal (Run 2)

Status:

- **`B4_POSTHOC_READONLY_COLLECTION=ACCEPTED`**
- The original rehearsal (run 1) **remains**
  `B4_TERMUX_KROOT_REHEARSAL=PASS_OBSERVED` with
  `B4_REVIEWED_GATE_EVIDENCE=INCOMPLETE`.
  `B4_TERMUX_KROOT_REHEARSAL=ACCEPTED` is **not** recorded
- **Owner decision:** exactly **one fresh TEST-only rehearsal (run 2)** with
  the reviewed operator block and complete run-time evidence. It is
  prepared here and **not started**
- **Classification: `B4_POSTHOC_EVIDENCE_ACCEPTED_FRESH_REHEARSAL_REQUIRED`**
- Documentation plus a derived operator script. No ceremony logic, gate,
  owner tooling, or acceptance flag changes. No phone contact was made to
  prepare it
- **Real M-B1 NOT AUTHORIZED**; **PR-1B NOT AUTHORIZED**

```text
post-hoc safety proven != run-time gates proven != rehearsal accepted
rehearsal key != K-ROOT;  rehearsal PASS != M-B1 authorization
```

| Field | Value |
| --- | --- |
| Control `main` | `df4eb5585275641b48094ed28ce23b00246b9c89` |
| Prior records | [evidence hold](slice-15b2b-b1b3e-b4-termux-kroot-rehearsal-evidence-hold.md) (run 1 and the v2 collection script `05ff0e39…3920`); [staging](slice-15b2b-b1b3e-b4-termux-kroot-rehearsal-staging.md) (reviewed block `353c988f…d6a7`) |
| Bundle (unchanged) | `lilith-b4-kroot-rehearsal-ff13bc6.tar`, `659c50a476c85ff9ed005af97bc70a48989a87890ec53b23f940d97901bee0b3` |

## 1. Post-hoc read-only collection: accepted

The v2 collection script (`05ff0e39…3920`, merged) ran on the S25 and
printed `ALL_GATES_PASS` and `SEAL_VERIFIED`.

**Transfer.**

| Item | Value |
| --- | --- |
| `lilith-b4-readonly-check.tar`, phone-side pre-transfer SHA-256 | `4dbe43102f301c967bb19ef6a0f6e5aa800025d6f33cdcc3f1e345b196c1eeaf` (owner-recorded before MTP) |
| laptop-received SHA-256 | `4dbe43102f301c967bb19ef6a0f6e5aa800025d6f33cdcc3f1e345b196c1eeaf`, **identical**, so transport integrity is established |
| sealed `SHA256SUMS` | `aa024f67055df496653d1d8964233bae63edcf0fae13b53233e74427f66a62b6` |
| seal re-verified on the laptop | `sha256sum -c --strict` OK for all 8 files; 8 lines; no self-entry; no `STOP.txt` |
| `gates.txt` | `2cff18e760b345a4288a58b6fdf300cea1f364779c0276917344932bfae706c9` |
| `key-file-matches.txt` | 0 bytes |

**Gates.** `gates.txt` holds these PASS tokens, in order:

- `CHECK_DIR_CREATED`
- `EVIDENCE_UNCHANGED_NOW`
- `BUNDLE_TAR_OK_NOW`
- `SHA256SUMS_DIGEST_OK_NOW`
- `SOURCE_COMMIT_OK_NOW`
- `BUNDLE_UNCHANGED_NOW`
- `TMP_CLEAN_NOW`
- `NO_KEY_FILE_ANYWHERE_NOW`
- `STDERR_EMPTY_NOW`
- `REPLICA_B_UNCHANGED_SINCE_BASELINE`
- `REPLICA_B_UNCHANGED_SINCE_AFTER`
- `REPLICA_B_BASELINE_OK_NOW`
- `NESTED_REPLICA_ABSENT_NOW`
- `ALL_GATES_PASS`

Its `INFO` lines are:

- `ORIGINAL_ABSENT` for `g0.txt`, `verify.txt`, and `evidence.sha256`. The
  inventory confirms that run 1 never wrote them;
- `TRANSPORT_COPY_STILL_IN_DOWNLOAD`. Run 1's cleanup step did not run;
- `HISTORY_NOT_COLLECTED`.

**Replica B now.**

- Path: `$HOME/lilith-owner-offline-dev-synthetic-01`.
- Manifest: `c068e5331ccd7fa0f69f2b38d25849497b86edea843598784235874080c107c4`.
- `records 0`.
- Reviewed-format `parent lilith-owner-offline-dev-synthetic-01`.
- Inodes `973613 / 973617 / 973618`, the same modes, sizes, and mtime
  `1790654695` as run 1's baseline.
- The old nested path is absent.

**Environment now.** `HOME` and `TMPDIR` are private; Python `3.14.6`;
`cryptography` `50.0.1`; `aarch64`.

**Run 1 archive transport, now established.** A phone copy of
`lilith-b4-rehearsal-evidence.tar` remained in Download. Its phone-side
SHA-256 is `96d188c14d28b56f58163efdd2a7634ed3bebf159f83df24a4a329176bdc374e`.

- It equals the laptop-received archive, so that archive's transport
  integrity is established. This supersedes the caveat in the hold record
  §1.
- `EVIDENCE_UNCHANGED_NOW` shows the six member files on the phone still
  equal the archive's.

> **Acceptance wording.** `B4_POSTHOC_READONLY_COLLECTION=ACCEPTED`. The
> reviewed v2 read-only collection ran on the S25 with every hard gate
> passing and a verified seal. Its tar arrived byte-identical to the
> phone-side pre-transfer hash. It proves, **as the state at collection
> time**:
>
> - no TEST key or rehearsal output remains in `$HOME` or `TMPDIR`;
> - `TMPDIR` holds no rehearsal workdir;
> - the rehearsal bundle is intact;
> - run 1's `rehearsal.stderr` is empty;
> - Replica B is byte-for-byte continuous with run 1's pre-rehearsal
>   baseline (same manifest, 0 records, same inodes, modes, sizes, and
>   mtimes) and passes the reviewed baseline gate;
> - no nested Replica B exists.
>
> It also establishes the transport integrity of run 1's evidence archive.
>
> It does **not** prove the pre-run or immediate post-run run-time tokens
> of the reviewed `353c988f` block. So it does not accept run 1.

## 2. Remaining gap

Run 1 cannot supply, and no read-only step can reconstruct:

- a run-time record that the **exact reviewed `353c988f` block** executed;
- the **pre-run** gate tokens:
  - `HOME_TERMUX_PRIVATE`, `TMP_TERMUX_PRIVATE`, `CRYPTOGRAPHY_OK`;
  - `STAGING_ABSENT`, `TMP_NO_STALE`, `NO_KROOT_FILES_BEFORE`;
  - `REPLICA_B_PRESENT`, `NESTED_REPLICA_ABSENT`;
  - the reviewed-format baseline and `REPLICA_B_BASELINE_OK`;
  - `BUNDLE_VERIFIED`, `SOURCE_COMMIT_OK`, `FILE_COUNT_OK`,
    `BUNDLE_IN_TERMUX_PRIVATE`;
- the **immediate post-run** tokens: `TMP_CLEAN`, `NO_KEY_FILE_ANYWHERE`,
  `BUNDLE_UNCHANGED`, `STDERR_EMPTY`, `REPLICA_B_UNCHANGED`;
- `g0.txt`, `verify.txt`, `evidence.sha256`, and a stdout/stderr
  transcript.

The owner's decision is to close this gap with **one fresh TEST-only
rehearsal**, not with accepted limitations.

## 3. Run 2: derivation from the reviewed block

> **Revision (2026-09-29, before any owner execution).** The first run-2
> script (`aa0a33b0…f724`, commit `b7c6b18`) is **withdrawn and must not be
> run**. It relied on an `echo()` redefinition as its only stop mechanism,
> and a literal review plus fault injection (§7) confirmed that it failed
> open.
>
> 1. **A non-zero rehearsal exit continued.** `echo "exit=$?"` never
>    printed STOP. The run went on to the gate, verify, seal, and cleanup.
>    Run 1's old script ended `RUN_EXIT=0`.
> 2. **A failed rehearsal gate continued.** `STOP: rehearsal gate failed`
>    is printed by Python and shown by `cat`, not by `echo`. `RUN_EXIT=0`.
> 3. **Post-run STOPs were swallowed.**
>    - `TMP_CLEAN`, `NO_KEY_FILE_ANYWHERE`, `BUNDLE_UNCHANGED`, and
>      `STDERR_EMPTY` ran inside `{ …; } | tee verify.txt`, so `exit` left
>      only that pipeline subshell.
>    - The seal and the transport-copy removal still ran, with
>      `RUN_EXIT=0`.
> 4. **The `REPLICA_B_UNCHANGED` STOP did end the run**, but only through
>    `echo()`.
> 5. **A cleanup `cmp` failure was silent.** It ended `RUN_EXIT=1` with no
>    STOP line.
>
> Also, the rehearsal gate program's own exit status was never checked.

> **Final hardening (2026-09-29, before any owner execution).** Script
> `193da67a…b4b0` (commit `3b0d530`) is superseded. Its authority and
> control gates are unchanged here. Only evidence I/O was hardened, so that
> an evidence write or read failure can never end `RUN_EXIT=0`.
>
> **Confirmed on `193da67a` by fault injection (§7):**
>
> - a failed g0 environment probe ended **`RUN_EXIT=0`** with an
>   incomplete `g0.txt`;
> - a `rehearsal.exit` write failure ran on through the gate and verify
>   steps, and stopped only at the seal;
> - baseline and post-run snapshot write failures stopped only indirectly,
>   with the misleading "not the accepted empty replica" and "Replica B
>   changed".
>
> **Eight `|| stop` additions**, listed in the diff below:
>
> - `cd "$HOME"`;
> - the `g0.txt` group (its redirection and the probe);
> - `snap > replica-b-before.txt`, and its `cat`;
> - `echo "exit=$rc" | tee rehearsal.exit` (the content is still
>   exactly `exit=N`);
> - `tail -1 rehearsal.json`;
> - `cat gate.txt`, before its exact success check;
> - `snap > replica-b-after.txt`;
> - `cat evidence.sha256`.

**Why run 2 cannot be the reviewed block unmodified.**

- Its G0 requires `~/lilith-b4-rehearsal` to be absent.
- Run 1's directory must be kept, so the exact block would STOP at
  `STAGING_ABSENT`.
- The reviewed block was also written to be pasted, with the operator
  halting at each STOP. Run 2 runs as **one file**, to capture a complete
  transcript, so every stop must be structural.

**Differences from `353c988f`.** There are exactly two kinds, and the
unified diff below lists every changed line. `RunTwoTests` pins that the
diff is exactly this.

1. **Staging directory:** `W="$HOME/lilith-b4-rehearsal-2"`. `E` and `B`
   follow from `W`.
2. **Hard-stop control flow**, and nothing else:
   - **Prelude:** five comment lines, plus two functions.
     `stop()` prints `STOP: …` on stderr, which the transcript captures, and
     `exit 1`s. It is the **only** STOP path. `vpass()` prints a verify
     token and appends it to `verify.txt`. There is no `echo()`
     redefinition.
   - **Every top-level gate:** `echo "STOP: X"` becomes `stop "X"`, a
     mechanical rule. The condition, the PASS token, and the order are
     unchanged.
   - **Structural steps** that previously continued on failure now end
     with `|| stop`: `mkdir`, `cp`, `cd "$W"`, `tar -xf`, `cd "$B"`.
   - **R1:** `rc=$?`, then `echo "exit=$rc" | tee rehearsal.exit`, then
     `test "$rc" -eq 0 || stop`. On a non-zero exit, no gate, verify,
     seal, or cleanup runs.
   - **Rehearsal gate:** the gate program's own exit is checked
     (`<<'PYEOF' || stop`). After `cat gate.txt`, a top-level check
     requires three things: the first line is exactly
     `REHEARSAL_GATE_PASS`, there are exactly six `BURNED` lines, and no
     line begins with `STOP`.
   - **V:** the `{ …; } | tee verify.txt` group is replaced by top-level
     lines. Each evaluates the reviewed condition, calls `stop` on failure,
     and otherwise calls `vpass` with the same token. `verify.txt` gets the
     same five PASS lines in the same order.
     - `STDERR_EMPTY` also requires `rehearsal.stderr` to exist.
     - `REPLICA_B_UNCHANGED` is `cmp … || stop`.
   - **Seal:** `evidence.sha256` is written `|| stop`, shown `|| stop`, then
     verified with `sha256sum -c`, which also stops on failure.
   - **Evidence I/O:** `cd "$HOME"`, the `g0.txt` group, both Replica B
     snapshots and the baseline's `cat`, the `rehearsal.exit` write, and
     the `rehearsal.json` and `gate.txt` displays each end in `|| stop`.
   - **Cleanup** runs only after every gate and the seal. It requires, each
     with a stop on failure:
     1. the Download tar exists;
     2. the staged tar exists;
     3. `cmp` succeeds;
     4. `rm` succeeds;
     5. the Download tar is absent afterwards.

     Only then does it print `TRANSPORT_COPY_REMOVED`.

**Unchanged:**

- the bundle and its pins (`TAR_SHA`, `SUMS_SHA`, `SRC`, 75 files);
- the canonical Replica B path;
- the manifest hash;
- the reviewed `snap()` and its format;
- every gate condition and PASS token;
- the rehearsal program, its TEST-only semantics, and the gate program's
  checks;
- the evidence files and their fields;
- the burned-identity rules.

**Run 2 creates no real K-ROOT, K-WIT, registry, genesis pin, or freshness
record, and does not write Replica B.**

**Acceptance requires** `RUN_EXIT=0` **and zero transcript lines beginning
`STOP:`**. The documented invocation (§4 step 4) records the script's true
exit status. `RUN_EXIT` is taken from `PIPESTATUS[0]` of that one pipeline,
which a test pins.

```diff
--- 353c988f
+++ run2
@@ -0,0 +1,7 @@
+# ===== B-4 FRESH TEST-only rehearsal, run 2: derived from the reviewed operator block 353c988f =====
+# Every difference from 353c988f is the pinned diff in the run-2 record section 3. Run 1's directory is kept.
+# Run ONLY as a file, with airplane mode ON and USB unplugged BEFORE starting (the PAUSE below is then already satisfied):
+#   bash "$HOME/storage/downloads/b4_phone_commands.run2.sh" 2>&1 | tee "$HOME/lilith-b4-rehearsal-2.transcript.txt"
+# stop() is the only STOP path: it prints "STOP: ..." on stderr (captured by the transcript) and exits 1 at top level.
+stop() { builtin echo "STOP: $*" >&2; exit 1; }
+vpass() { builtin echo "$1"; builtin echo "$1" >> "$E/verify.txt" || stop "cannot write verify.txt"; }
@@ -8 +15 @@
-W="$HOME/lilith-b4-rehearsal"
+W="$HOME/lilith-b4-rehearsal-2"
@@ -19,3 +26,3 @@
-cd "$HOME"
-priv "$HOME" && echo HOME_TERMUX_PRIVATE || echo "STOP: HOME is not Termux private storage"
-priv "$TMP" && echo TMP_TERMUX_PRIVATE || echo "STOP: TMPDIR is not Termux private storage"
+cd "$HOME" || stop "cannot enter HOME"
+priv "$HOME" && echo HOME_TERMUX_PRIVATE || stop "HOME is not Termux private storage"
+priv "$TMP" && echo TMP_TERMUX_PRIVATE || stop "TMPDIR is not Termux private storage"
@@ -23,6 +30,6 @@
-python -c 'import sys, cryptography as c; v = c.__version__; m = int(v.split(".")[0]); print("CRYPTOGRAPHY", v); sys.exit(0 if 2 <= m < 52 and m != 35 else 1)' && echo CRYPTOGRAPHY_OK || echo "STOP: cryptography missing or unsupported"
-test ! -e "$W" && echo STAGING_ABSENT || echo "STOP: $W already exists"
-ls -A "$TMP" | grep -q lilith-b4-kroot-rehearsal && echo "STOP: stale rehearsal directory in TMPDIR" || echo TMP_NO_STALE
-find "$HOME" -name 'k-root*' 2>/dev/null | grep -q . && echo "STOP: a k-root file already exists" || echo NO_KROOT_FILES_BEFORE
-test -f "$R/REPLICA.json" && echo REPLICA_B_PRESENT || echo "STOP: Replica B missing"
-test ! -e "$HOME/lilith-owner-freshness/owner-offline-dev-synthetic-01" && echo NESTED_REPLICA_ABSENT || echo "STOP: a second Replica B exists at the old nested path"
+python -c 'import sys, cryptography as c; v = c.__version__; m = int(v.split(".")[0]); print("CRYPTOGRAPHY", v); sys.exit(0 if 2 <= m < 52 and m != 35 else 1)' && echo CRYPTOGRAPHY_OK || stop "cryptography missing or unsupported"
+test ! -e "$W" && echo STAGING_ABSENT || stop "$W already exists"
+ls -A "$TMP" | grep -q lilith-b4-kroot-rehearsal && stop "stale rehearsal directory in TMPDIR" || echo TMP_NO_STALE
+find "$HOME" -name 'k-root*' 2>/dev/null | grep -q . && stop "a k-root file already exists" || echo NO_KROOT_FILES_BEFORE
+test -f "$R/REPLICA.json" && echo REPLICA_B_PRESENT || stop "Replica B missing"
+test ! -e "$HOME/lilith-owner-freshness/owner-offline-dev-synthetic-01" && echo NESTED_REPLICA_ABSENT || stop "a second Replica B exists at the old nested path"
@@ -31 +38 @@
-mkdir -m 700 "$W" "$E"
+mkdir -m 700 "$W" "$E" || stop "cannot create $W"
@@ -33,3 +40,3 @@
-  python -c 'import sys, platform, cryptography as c; print("PYTHON", sys.version.split()[0], "CRYPTOGRAPHY", c.__version__, "MACHINE", platform.machine())'; } > "$E/g0.txt"
-snap > "$E/replica-b-before.txt"; cat "$E/replica-b-before.txt"
-grep -qx "sha c068e5331ccd7fa0f69f2b38d25849497b86edea843598784235874080c107c4" "$E/replica-b-before.txt" && grep -qx "records 0" "$E/replica-b-before.txt" && grep -qE "^parent (.* )?lilith-owner-offline-dev-synthetic-01 " "$E/replica-b-before.txt" && echo REPLICA_B_BASELINE_OK || echo "STOP: Replica B is not the accepted empty replica"
+  python -c 'import sys, platform, cryptography as c; print("PYTHON", sys.version.split()[0], "CRYPTOGRAPHY", c.__version__, "MACHINE", platform.machine())'; } > "$E/g0.txt" || stop "cannot write g0.txt"
+snap > "$E/replica-b-before.txt" || stop "cannot write Replica B baseline"; cat "$E/replica-b-before.txt" || stop "cannot read Replica B baseline"
+grep -qx "sha c068e5331ccd7fa0f69f2b38d25849497b86edea843598784235874080c107c4" "$E/replica-b-before.txt" && grep -qx "records 0" "$E/replica-b-before.txt" && grep -qE "^parent (.* )?lilith-owner-offline-dev-synthetic-01 " "$E/replica-b-before.txt" && echo REPLICA_B_BASELINE_OK || stop "Replica B is not the accepted empty replica"
@@ -38,10 +45,10 @@
-cp "$HOME/storage/downloads/$TAR" "$W/"
-cd "$W"
-echo "$TAR_SHA  $TAR" | sha256sum -c - || echo "STOP: bundle hash differs"
-tar -xf "$TAR"
-cd "$B"
-echo "$SUMS_SHA  SHA256SUMS" | sha256sum -c - || echo "STOP: SHA256SUMS digest differs"
-sha256sum -c --quiet SHA256SUMS && echo BUNDLE_VERIFIED || echo "STOP: SHA256SUMS verification failed"
-test "$(cat SOURCE_COMMIT)" = "$SRC" && echo SOURCE_COMMIT_OK || echo "STOP: source commit differs"
-test "$(find "$B" -type f | wc -l)" = 75 && echo FILE_COUNT_OK || echo "STOP: unexpected file count"
-priv "$B" && echo BUNDLE_IN_TERMUX_PRIVATE || echo "STOP: bundle is not in Termux private storage"
+cp "$HOME/storage/downloads/$TAR" "$W/" || stop "transport copy missing or unreadable"
+cd "$W" || stop "cannot enter $W"
+echo "$TAR_SHA  $TAR" | sha256sum -c - || stop "bundle hash differs"
+tar -xf "$TAR" || stop "cannot extract the bundle"
+cd "$B" || stop "cannot enter the bundle"
+echo "$SUMS_SHA  SHA256SUMS" | sha256sum -c - || stop "SHA256SUMS digest differs"
+sha256sum -c --quiet SHA256SUMS && echo BUNDLE_VERIFIED || stop "SHA256SUMS verification failed"
+test "$(cat SOURCE_COMMIT)" = "$SRC" && echo SOURCE_COMMIT_OK || stop "source commit differs"
+test "$(find "$B" -type f | wc -l)" = 75 && echo FILE_COUNT_OK || stop "unexpected file count"
+priv "$B" && echo BUNDLE_IN_TERMUX_PRIVATE || stop "bundle is not in Termux private storage"
@@ -55,3 +62,5 @@
-echo "exit=$?" | tee "$E/rehearsal.exit"                                                     # exit=0
-tail -1 "$E/rehearsal.json"                                                                   # B4_KROOT_REHEARSAL=PASS
-python - "$E/rehearsal.json" > "$E/gate.txt" <<'PYEOF'
+rc=$?
+echo "exit=$rc" | tee "$E/rehearsal.exit" || stop "cannot write rehearsal.exit"                                                     # exit=0
+test "$rc" -eq 0 || stop "rehearsal exited non-zero ($rc)"
+tail -1 "$E/rehearsal.json" || stop "cannot read rehearsal.json"                                                                   # B4_KROOT_REHEARSAL=PASS
+python - "$E/rehearsal.json" > "$E/gate.txt" <<'PYEOF' || stop "rehearsal gate program failed"
@@ -77 +86,2 @@
-cat "$E/gate.txt"                                                                             # REHEARSAL_GATE_PASS + 6 BURNED lines
+cat "$E/gate.txt" || stop "cannot read gate.txt"                                                                             # REHEARSAL_GATE_PASS + 6 BURNED lines
+test "$(head -1 "$E/gate.txt")" = REHEARSAL_GATE_PASS && test "$(grep -c '^BURNED ' "$E/gate.txt")" = 6 && ! grep -q '^STOP' "$E/gate.txt" || stop "rehearsal gate failed"
@@ -80,7 +90,8 @@
-{ ls -A "$TMP" | grep -q lilith-b4-kroot-rehearsal && echo "STOP: rehearsal directory left in TMPDIR" || echo TMP_CLEAN
-  find "$HOME" \( -name 'k-root*' -o -name '*REHEARSAL-TEST*' \) 2>/dev/null | grep -q . && echo "STOP: a TEST key file remains" || echo NO_KEY_FILE_ANYWHERE
-  test "$(find "$B" -type f | wc -l)" = 75 && (cd "$B" && sha256sum -c --quiet SHA256SUMS) && echo BUNDLE_UNCHANGED || echo "STOP: unexpected file in bundle"
-  test -s "$E/rehearsal.stderr" && echo "STOP: rehearsal wrote to stderr" || echo STDERR_EMPTY; } | tee "$E/verify.txt"
-snap > "$E/replica-b-after.txt"
-cmp "$E/replica-b-before.txt" "$E/replica-b-after.txt" && echo REPLICA_B_UNCHANGED | tee -a "$E/verify.txt" || echo "STOP: Replica B changed"
-sha256sum "$E"/* > "$W/evidence.sha256"; cat "$W/evidence.sha256"
+ls -A "$TMP" | grep -q lilith-b4-kroot-rehearsal && stop "rehearsal directory left in TMPDIR"; vpass TMP_CLEAN
+find "$HOME" \( -name 'k-root*' -o -name '*REHEARSAL-TEST*' \) 2>/dev/null | grep -q . && stop "a TEST key file remains"; vpass NO_KEY_FILE_ANYWHERE
+test "$(find "$B" -type f | wc -l)" = 75 && (cd "$B" && sha256sum -c --quiet SHA256SUMS) || stop "unexpected file in bundle"; vpass BUNDLE_UNCHANGED
+test -f "$E/rehearsal.stderr" && ! test -s "$E/rehearsal.stderr" || stop "rehearsal wrote to stderr"; vpass STDERR_EMPTY
+snap > "$E/replica-b-after.txt" || stop "cannot write Replica B post-run snapshot"
+cmp "$E/replica-b-before.txt" "$E/replica-b-after.txt" || stop "Replica B changed"; vpass REPLICA_B_UNCHANGED
+sha256sum "$E"/* > "$W/evidence.sha256" || stop "cannot write evidence.sha256"; cat "$W/evidence.sha256" || stop "cannot read evidence.sha256"
+sha256sum -c --quiet "$W/evidence.sha256" || stop "evidence.sha256 does not verify"
@@ -89 +100,6 @@
-cmp "$HOME/storage/downloads/$TAR" "$W/$TAR" && rm "$HOME/storage/downloads/$TAR" && echo TRANSPORT_COPY_REMOVED
+test -f "$HOME/storage/downloads/$TAR" || stop "transport copy missing in Download"
+test -f "$W/$TAR" || stop "staged tar missing"
+cmp "$HOME/storage/downloads/$TAR" "$W/$TAR" || stop "transport copy differs from the staged tar"
+rm "$HOME/storage/downloads/$TAR" || stop "cannot remove the transport copy"
+test ! -e "$HOME/storage/downloads/$TAR" || stop "transport copy still present"
+echo TRANSPORT_COPY_REMOVED
```

**Airplane mode.** The block's mid-run PAUSE is a comment. Run 2 therefore
starts with airplane mode already ON and USB unplugged. Nothing in the
block needs a network or the laptop: the bundle is copied from Download
locally.

**Script.** `b4_phone_commands.run2.sh` (SHA-256
`f0768b6e2b1faa120d1136c467cccfa99b2f2fa83f59ad719ddabc2b4d1b1fe9`) is exactly the block below. The laptop copy is at
`%USERPROFILE%\lilith-b4-evidence\b4_phone_commands.run2.sh`.

```bash
# ===== B-4 FRESH TEST-only rehearsal, run 2: derived from the reviewed operator block 353c988f =====
# Every difference from 353c988f is the pinned diff in the run-2 record section 3. Run 1's directory is kept.
# Run ONLY as a file, with airplane mode ON and USB unplugged BEFORE starting (the PAUSE below is then already satisfied):
#   bash "$HOME/storage/downloads/b4_phone_commands.run2.sh" 2>&1 | tee "$HOME/lilith-b4-rehearsal-2.transcript.txt"
# stop() is the only STOP path: it prints "STOP: ..." on stderr (captured by the transcript) and exits 1 at top level.
stop() { builtin echo "STOP: $*" >&2; exit 1; }
vpass() { builtin echo "$1"; builtin echo "$1" >> "$E/verify.txt" || stop "cannot write verify.txt"; }
# ===== B-4 Termux K-ROOT capability rehearsal: TEST ONLY (bundle lilith-b4-kroot-rehearsal-ff13bc6) =====
# Run in Termux on the S25, one block at a time. Every "STOP" is a hard stop: do not continue past it.
# Nothing here creates a real K-ROOT, uses a real passphrase, or writes to a replica or pin path.
TAR=lilith-b4-kroot-rehearsal-ff13bc6.tar
TAR_SHA=659c50a476c85ff9ed005af97bc70a48989a87890ec53b23f940d97901bee0b3
SUMS_SHA=dbb9dfbeaeefb59e47cb2ae64aaa651bbe9b89daa443e0912787c10d0b0e2288
SRC=ff13bc6f72156c332b29ad1605d24410c2abf232
W="$HOME/lilith-b4-rehearsal-2"
E="$W/evidence"
B="$W/lilith-b4-kroot-rehearsal-ff13bc6"
R="$HOME/lilith-owner-offline-dev-synthetic-01"                   # the real Replica B, directly under $HOME
TMP="${TMPDIR:-$PREFIX/tmp}"
priv() { case "$(realpath "$1")/" in /data/data/com.termux/*|/data/user/0/com.termux/*) return 0;; *) return 1;; esac; }
snap() { echo "sha $(sha256sum "$R/REPLICA.json" | cut -d' ' -f1)"; echo "records $(ls -A "$R/records" | wc -l)"
         echo "entries $(ls -A "$R" | LC_ALL=C sort | tr '\n' ' ')"; echo "parent $(ls -A "$HOME" | grep '^lilith-owner' | LC_ALL=C sort | tr '\n' ' ')"
         stat -c '%n %i %a %s %Y' "$R" "$R/REPLICA.json" "$R/records" | sed "s#$HOME#~#"; }

# ---- G0 environment (read-only) ----
cd "$HOME" || stop "cannot enter HOME"
priv "$HOME" && echo HOME_TERMUX_PRIVATE || stop "HOME is not Termux private storage"
priv "$TMP" && echo TMP_TERMUX_PRIVATE || stop "TMPDIR is not Termux private storage"
python -c 'import sys; print("PYTHON", sys.version.split()[0])'
python -c 'import sys, cryptography as c; v = c.__version__; m = int(v.split(".")[0]); print("CRYPTOGRAPHY", v); sys.exit(0 if 2 <= m < 52 and m != 35 else 1)' && echo CRYPTOGRAPHY_OK || stop "cryptography missing or unsupported"
test ! -e "$W" && echo STAGING_ABSENT || stop "$W already exists"
ls -A "$TMP" | grep -q lilith-b4-kroot-rehearsal && stop "stale rehearsal directory in TMPDIR" || echo TMP_NO_STALE
find "$HOME" -name 'k-root*' 2>/dev/null | grep -q . && stop "a k-root file already exists" || echo NO_KROOT_FILES_BEFORE
test -f "$R/REPLICA.json" && echo REPLICA_B_PRESENT || stop "Replica B missing"
test ! -e "$HOME/lilith-owner-freshness/owner-offline-dev-synthetic-01" && echo NESTED_REPLICA_ABSENT || stop "a second Replica B exists at the old nested path"

# ---- G1 Replica B baseline (read-only) ----
mkdir -m 700 "$W" "$E" || stop "cannot create $W"
{ echo "HOME_PRIVATE $(priv "$HOME" && echo yes || echo no)"; echo "TMP_PRIVATE $(priv "$TMP" && echo yes || echo no)"
  python -c 'import sys, platform, cryptography as c; print("PYTHON", sys.version.split()[0], "CRYPTOGRAPHY", c.__version__, "MACHINE", platform.machine())'; } > "$E/g0.txt" || stop "cannot write g0.txt"
snap > "$E/replica-b-before.txt" || stop "cannot write Replica B baseline"; cat "$E/replica-b-before.txt" || stop "cannot read Replica B baseline"
grep -qx "sha c068e5331ccd7fa0f69f2b38d25849497b86edea843598784235874080c107c4" "$E/replica-b-before.txt" && grep -qx "records 0" "$E/replica-b-before.txt" && grep -qE "^parent (.* )?lilith-owner-offline-dev-synthetic-01 " "$E/replica-b-before.txt" && echo REPLICA_B_BASELINE_OK || stop "Replica B is not the accepted empty replica"

# ---- T1 transport copy -> private staging, then verify ----
cp "$HOME/storage/downloads/$TAR" "$W/" || stop "transport copy missing or unreadable"
cd "$W" || stop "cannot enter $W"
echo "$TAR_SHA  $TAR" | sha256sum -c - || stop "bundle hash differs"
tar -xf "$TAR" || stop "cannot extract the bundle"
cd "$B" || stop "cannot enter the bundle"
echo "$SUMS_SHA  SHA256SUMS" | sha256sum -c - || stop "SHA256SUMS digest differs"
sha256sum -c --quiet SHA256SUMS && echo BUNDLE_VERIFIED || stop "SHA256SUMS verification failed"
test "$(cat SOURCE_COMMIT)" = "$SRC" && echo SOURCE_COMMIT_OK || stop "source commit differs"
test "$(find "$B" -type f | wc -l)" = 75 && echo FILE_COUNT_OK || stop "unexpected file count"
priv "$B" && echo BUNDLE_IN_TERMUX_PRIVATE || stop "bundle is not in Termux private storage"

# ---- PAUSE: turn ON airplane mode and unplug USB now. The rehearsal needs no network or laptop. ----

# ---- R1 the rehearsal (throwaway TEST key; temporary files removed by the script) ----
export PYTHONPATH="$B/vendor"
export PYTHONDONTWRITEBYTECODE=1
python -B "$B/services/owner-memory-control/tools/termux_kroot_rehearsal.py" rehearse > "$E/rehearsal.json" 2> "$E/rehearsal.stderr"
rc=$?
echo "exit=$rc" | tee "$E/rehearsal.exit" || stop "cannot write rehearsal.exit"                                                     # exit=0
test "$rc" -eq 0 || stop "rehearsal exited non-zero ($rc)"
tail -1 "$E/rehearsal.json" || stop "cannot read rehearsal.json"                                                                   # B4_KROOT_REHEARSAL=PASS
python - "$E/rehearsal.json" > "$E/gate.txt" <<'PYEOF' || stop "rehearsal gate program failed"
import json, sys
head, last = open(sys.argv[1]).read().rstrip().rsplit("\n", 1)
d = json.loads(head)
need = ["rootKeygen", "keyFileRegular0600", "keyFileOnlyEntry", "keyNotLoadableWithoutPassphrase",
        "keyNotLoadableWithWrongPassphrase", "anchorMatchesKeyAndFingerprint", "existingKeyNeverOverwritten",
        "shortPassphraseRefused", "rootKeygenCli", "syntheticInputs", "registryV1", "registryV1CliEqualsFunction",
        "registryV1WrongPassphraseRefused", "witnessAnchor", "reproduceDeterministicAndVerified",
        "allFilesInsideWorkdir", "cleanup"]
removed = sorted(["k-root.REHEARSAL-TEST.der", "k-root-cli.REHEARSAL-TEST.der", "kact.json", "kwit.json",
                  "root-anchor.json", "registry.json", "witness-anchor.json"])
bad = [k for k in need if d["checks"].get(k) != "PASS"] + sorted(set(d["checks"]) - set(need))
ok = (last == "B4_KROOT_REHEARSAL=PASS" and not bad and d["REHEARSAL"] == "PASS" and d["testOnly"] is True
      and d["realAuthorityMaterial"] == "NONE" and sorted(d["removedEntries"]) == removed
      and len(d["burnedTestIdentities"]) == 6)
print("REHEARSAL_GATE_PASS" if ok else "STOP: rehearsal gate failed " + ",".join(bad))
for k, v in sorted(d["burnedTestIdentities"].items()):
    print("BURNED", k, v)
print("ENV", json.dumps(d["environment"], sort_keys=True))
PYEOF
cat "$E/gate.txt" || stop "cannot read gate.txt"                                                                             # REHEARSAL_GATE_PASS + 6 BURNED lines
test "$(head -1 "$E/gate.txt")" = REHEARSAL_GATE_PASS && test "$(grep -c '^BURNED ' "$E/gate.txt")" = 6 && ! grep -q '^STOP' "$E/gate.txt" || stop "rehearsal gate failed"

# ---- V verification (read-only) ----
ls -A "$TMP" | grep -q lilith-b4-kroot-rehearsal && stop "rehearsal directory left in TMPDIR"; vpass TMP_CLEAN
find "$HOME" \( -name 'k-root*' -o -name '*REHEARSAL-TEST*' \) 2>/dev/null | grep -q . && stop "a TEST key file remains"; vpass NO_KEY_FILE_ANYWHERE
test "$(find "$B" -type f | wc -l)" = 75 && (cd "$B" && sha256sum -c --quiet SHA256SUMS) || stop "unexpected file in bundle"; vpass BUNDLE_UNCHANGED
test -f "$E/rehearsal.stderr" && ! test -s "$E/rehearsal.stderr" || stop "rehearsal wrote to stderr"; vpass STDERR_EMPTY
snap > "$E/replica-b-after.txt" || stop "cannot write Replica B post-run snapshot"
cmp "$E/replica-b-before.txt" "$E/replica-b-after.txt" || stop "Replica B changed"; vpass REPLICA_B_UNCHANGED
sha256sum "$E"/* > "$W/evidence.sha256" || stop "cannot write evidence.sha256"; cat "$W/evidence.sha256" || stop "cannot read evidence.sha256"
sha256sum -c --quiet "$W/evidence.sha256" || stop "evidence.sha256 does not verify"

# ---- Cleanup of the transport copy only (after every line above passed) ----
test -f "$HOME/storage/downloads/$TAR" || stop "transport copy missing in Download"
test -f "$W/$TAR" || stop "staged tar missing"
cmp "$HOME/storage/downloads/$TAR" "$W/$TAR" || stop "transport copy differs from the staged tar"
rm "$HOME/storage/downloads/$TAR" || stop "cannot remove the transport copy"
test ! -e "$HOME/storage/downloads/$TAR" || stop "transport copy still present"
echo TRANSPORT_COPY_REMOVED
# Keep "$W" (bundle + evidence). It holds no key. Airplane mode may be turned off afterwards.
# =============================== end of B-4 rehearsal ===============================
```

## 4. Run 2 execution plan (owner; not started)

**Preconditions.**

- A separate owner **go** for run 2.
- Run 1's `~/lilith-b4-rehearsal/`, `~/lilith-b4-readonly-check/`, and
  `~/lilith-b4-readonly-check.tar` stay untouched.
- The bundle tar `lilith-b4-kroot-rehearsal-ff13bc6.tar` is still in
  Download from run 1 (post-hoc `INFO`). If it is gone, copy it again by
  MTP. Either way, the block verifies its hash after copying.

**Steps.**

1. **Laptop:** verify `b4_phone_commands.run2.sh` is `f0768b6e2b1faa120d1136c467cccfa99b2f2fa83f59ad719ddabc2b4d1b1fe9`, then
   copy it by MTP into Download. Also copy the bundle tar if it is absent.
2. **Phone:** unplug USB, turn airplane mode **ON**, and open Termux.
3. **Phone, read-only pre-checks:**

   ```bash
   sha256sum "$HOME/storage/downloads/b4_phone_commands.run2.sh"                 # f0768b6e2b1faa120d1136c467cccfa99b2f2fa83f59ad719ddabc2b4d1b1fe9
   sha256sum "$HOME/storage/downloads/lilith-b4-kroot-rehearsal-ff13bc6.tar"     # 659c50a476c85ff9ed005af97bc70a48989a87890ec53b23f940d97901bee0b3
   test ! -e "$HOME/lilith-b4-rehearsal-2" && test ! -e "$HOME/lilith-b4-rehearsal-2.transcript.txt" && test ! -e "$HOME/lilith-b4-rehearsal-2-evidence.tar" && echo RUN2_TARGETS_ABSENT
   ```

   Stop unless both hashes match and `RUN2_TARGETS_ABSENT` prints.
4. **Phone, the run.** One command line captures stdout and stderr in the
   transcript, then appends the run's exit status:

   ```bash
   bash "$HOME/storage/downloads/b4_phone_commands.run2.sh" 2>&1 | tee "$HOME/lilith-b4-rehearsal-2.transcript.txt"; echo "RUN_EXIT=${PIPESTATUS[0]}" | tee -a "$HOME/lilith-b4-rehearsal-2.transcript.txt"
   ```

5. **Phone:** confirm there is no STOP line and the run succeeded:

   ```bash
   grep -c '^STOP' "$HOME/lilith-b4-rehearsal-2.transcript.txt"        # 0
   tail -1 "$HOME/lilith-b4-rehearsal-2.transcript.txt"                # RUN_EXIT=0
   ```

6. **Phone, export** (the only write outside the block; it never
   overwrites):

   ```bash
   cd "$HOME" && test ! -e lilith-b4-rehearsal-2-evidence.tar && tar -cf lilith-b4-rehearsal-2-evidence.tar lilith-b4-rehearsal-2/evidence lilith-b4-rehearsal-2/evidence.sha256 lilith-b4-rehearsal-2.transcript.txt && sha256sum lilith-b4-rehearsal-2-evidence.tar
   ```

   **Write down that hash on the phone screen before any transfer.** It is
   the phone-side pre-transfer hash.
7. **Transfer.** Copy the tar with
   `cp "$HOME/lilith-b4-rehearsal-2-evidence.tar" "$HOME/storage/downloads/"`,
   then plug in USB and copy it by MTP to the laptop. Airplane mode may be
   turned off afterwards.

**On any STOP** (non-zero `RUN_EXIT`, or any `STOP` line):

- Do not retry, delete, or edit anything.
- Keep `~/lilith-b4-rehearsal-2/` (if it was created) and the transcript.
- Export them as in step 6, listing only the members that exist (for
  example, only the transcript after a G0 STOP), and report.
- A further run needs a new reviewed decision.

## 5. Expected run-2 output

These are the reviewed staging §4 tokens, in order. The only difference is
that the staging directory is `~/lilith-b4-rehearsal-2`.

- `HOME_TERMUX_PRIVATE`
- `TMP_TERMUX_PRIVATE`
- `PYTHON <version>`
- `CRYPTOGRAPHY <version>`, `CRYPTOGRAPHY_OK`
- `STAGING_ABSENT`
- `TMP_NO_STALE`
- `NO_KROOT_FILES_BEFORE`
- `REPLICA_B_PRESENT`
- `NESTED_REPLICA_ABSENT`
- the baseline:
  - `sha c068e533…07c4`
  - `records 0`
  - `entries REPLICA.json records`
  - `parent lilith-owner-offline-dev-synthetic-01`
  - three `~/`-shortened stat lines
- `REPLICA_B_BASELINE_OK`
- `lilith-b4-kroot-rehearsal-ff13bc6.tar: OK`
- `SHA256SUMS: OK`
- `BUNDLE_VERIFIED`
- `SOURCE_COMMIT_OK`
- `FILE_COUNT_OK`
- `BUNDLE_IN_TERMUX_PRIVATE`
- `exit=0`
- `B4_KROOT_REHEARSAL=PASS`
- `REHEARSAL_GATE_PASS`, six `BURNED …` lines, and one `ENV …` line
- `TMP_CLEAN`
- `NO_KEY_FILE_ANYWHERE`
- `BUNDLE_UNCHANGED`
- `STDERR_EMPTY`
- `REPLICA_B_UNCHANGED`
- the `evidence.sha256` listing
- `TRANSPORT_COPY_REMOVED`
- `RUN_EXIT=0`

## 6. Run-2 acceptance criteria (for the later review)

**Integrity.**

- The export tar's laptop hash equals its phone-side pre-transfer hash.
- `evidence.sha256` verifies every file in `evidence/`.

**Evidence present:** `g0.txt`, `replica-b-before.txt`, `rehearsal.json`,
`rehearsal.stderr` (0 bytes), `rehearsal.exit` (`exit=0`), `gate.txt`,
`verify.txt`, `replica-b-after.txt`, and the transcript.

**Transcript.** It contains every token of §5, **zero** lines beginning `STOP:`,
and ends `RUN_EXIT=0`. Both are required.

**Rehearsal result.**

- `gate.txt` is reproduced byte for byte by re-running the reviewed gate on
  the laptop against `rehearsal.json`.
- There are exactly six `BURNED` identities. All are new: they must not
  equal run 1's (§8).

**Replica B.**

- `replica-b-before.txt` is in the reviewed `snap()` format: it has the
  `parent` line and `~/` paths.
- `replica-b-after.txt` is byte-identical to it.
- Its manifest is `c068e533…07c4`, with 0 records, and the inodes, modes,
  sizes, and mtime equal the post-hoc collection's (§1).

**Nothing else changed.** Run 1's directory and the check directory are
not touched. Run 2 does not reference them.

## 7. Offline check (laptop / WSL; no phone)

**Full-fidelity simulation.**

- The real bundle and the real rehearsal program run under a simulated
  Termux layout that mirrors the phone:
  - the stub Replica B at the canonical path, from the accepted manifest;
  - run 1's `~/lilith-b4-rehearsal/`, the check directory, and its tar;
  - the bundle tar in Download.
- Each script is run as a file, exactly as in §4 step 4.
- Faults are injected **only** by a `python` shim on `PATH`. It runs the
  real rehearsal, then applies one fault. The script under test is byte
  for byte the one listed.
- Every negative row stopped before `TRANSPORT_COPY_REMOVED`, with the
  Download tar preserved.

| # | Fault | withdrawn `aa0a33b0` | **v2 (this script)** |
| --- | --- | --- | --- |
| I | none (clean) | `RUN_EXIT=0` | **`RUN_EXIT=0`**, 0 STOP lines, every §5 token, 6 `BURNED`, all evidence files, `evidence.sha256` verifies, before = after, the transport copy removed |
| A | rehearsal exits 3 | `RUN_EXIT=0`, sealed, cleaned | **`1`**, `STOP: rehearsal exited non-zero (3)`; no `gate.txt`, `verify.txt`, or seal |
| B | gate check FAIL | `RUN_EXIT=0`, sealed, cleaned | **`1`**, `STOP: rehearsal gate failed`; no `verify.txt`, no seal |
| C | TMPDIR workdir left | `RUN_EXIT=0`, sealed, cleaned | **`1`**, `STOP: rehearsal directory left in TMPDIR`; no seal |
| D | TEST key left in `$HOME` | `RUN_EXIT=0`, sealed, cleaned | **`1`**, `STOP: a TEST key file remains`; no seal |
| E | bundle file changed | `RUN_EXIT=0`, sealed, cleaned | **`1`**, `STOP: unexpected file in bundle`; no seal |
| F | stderr non-empty | `RUN_EXIT=0`, sealed, cleaned | **`1`**, `STOP: rehearsal wrote to stderr`; no seal |
| G | `REPLICA.json` mtime changed | `RUN_EXIT=1` | **`1`**, `STOP: Replica B changed`; no seal |
| H | Download tar altered before cleanup | `RUN_EXIT=1`, **no STOP line** | **`1`**, `STOP: transport copy differs from the staged tar`; seal present (it precedes cleanup); the Download tar preserved |

**Evidence-I/O faults (final hardening).** Same full-fidelity setup. The
shim fails the g0 probe, or puts a directory where the next evidence file
must be written.

| Fault | superseded `193da67a` | **final (this script)** |
| --- | --- | --- |
| g0 environment probe fails | **`RUN_EXIT=0`**, sealed, cleaned; `g0.txt` incomplete | **`1`**, `STOP: cannot write g0.txt`; before any baseline or transport |
| `replica-b-before.txt` unwritable | `1`, only via "not the accepted empty replica" | **`1`**, `STOP: cannot write Replica B baseline`; before transport |
| `rehearsal.exit` unwritable | `1`, only at the seal; gate and verify had run | **`1`**, `STOP: cannot write rehearsal.exit`; no gate, verify, or seal |
| `replica-b-after.txt` unwritable | `1`, only via "Replica B changed" | **`1`**, `STOP: cannot write Replica B post-run snapshot`; no seal |
| `evidence.sha256` unwritable | `1` | **`1`**, `STOP: cannot write evidence.sha256` |
| clean | `0` | **`0`**: 0 STOP lines, 6 `BURNED`, 8 evidence files, `exit=0`, the seal verifies, before = after |

In every case, the Download bundle is preserved and `TRANSPORT_COPY_REMOVED`
never appears. `RunTwoHardStopTests` covers the same five faults on the
pinned text (`test_io_*`).

The pre-run STOPs (G0, G1, T1) remain as in the earlier check. The bad
transport tar, an existing run-2 directory, a nested replica, a leftover
`k-root`, a wrong manifest, and a stale workdir each stop before R1.

**Repository tests** (`RunTwoHardStopTests`, POSIX). The same cases A–I run
against the **pinned run-2 text**, on a stub bundle whose rehearsal program
injects the fault. Only these values are substituted:

- the bundle pins;
- the file count;
- the Termux prefix in `priv()`.

Each negative asserts, in addition:

- exit 1;
- that the STOP line is the **last** output;
- that there is no `TRANSPORT_COPY_REMOVED`;
- that the Download tar is preserved.

The clean case asserts the exact token sequence, the exact `verify.txt`,
six `BURNED` lines, before = after, and a verifying `evidence.sha256`.

The offline runs' TEST identities are throwaway and **burned**.

## 8. Burned TEST identities

- **Run 1's six** remain permanently burned
  ([hold record](slice-15b2b-b1b3e-b4-termux-kroot-rehearsal-evidence-hold.md)
  §4).
- **Every identity run 2 creates** is permanently burned too: its six
  `BURNED` lines.

None may ever be used or accepted in:

- M-B1 or M-B2;
- the real registry v1;
- the witness genesis or genesis pin;
- record 1 or any envelope;
- any later lineage.

Run 2 creates **no** real K-ROOT, K-WIT, registry, genesis pin, or
freshness record. It writes only TEST names inside a TMPDIR workdir that it
removes.

## 9. Blocker state

| # | Blocker | State |
| --- | --- | --- |
| B-3 | source-level real-acceptance block | **OPEN** |
| B-4 | custody topology | **CLOSED** ([decision](slice-15b2b-b1b3e-b4-kroot-custody-decision.md)) |
| B-4 | mandatory Termux rehearsal prerequisite | **OPEN**: run 1 `PASS_OBSERVED` / reviewed-gate evidence `INCOMPLETE`; post-hoc collection `ACCEPTED`; **run 2 required, prepared, not started** |
| B-5 | PR-1B not authorized | **OPEN** |

**`PR1B_NOT_ELIGIBLE`.**

The historical P3-3B status block ("Not executed") remains separate
historical-status debt.

## Explicitly not done

```text
B4_TERMUX_KROOT_REHEARSAL=ACCEPTED NOT RECORDED
RUN 2 NOT STARTED
NO PHONE CONTACT
NO PHONE MUTATION
NO REPLICA MUTATION
NO REAL K-ROOT
NO K-WIT
NO REAL REGISTRY
NO GENESIS PIN
NO REAL RECORD 1
FRESHNESS=UNKNOWN
PR-1B NOT AUTHORIZED
FIRST MEMORY NOT AUTHORIZED
```
