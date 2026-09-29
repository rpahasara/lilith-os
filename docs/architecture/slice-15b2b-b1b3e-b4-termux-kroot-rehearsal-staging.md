# Slice 15B2b-B1b-3e — B-4 Termux K-ROOT Rehearsal: Final Bundle and Operator Package

Status:

- **`TERMUX_KROOT_REHEARSAL_READY_FOR_OWNER_EXECUTION`**, after the
  **Replica B path correction** (§0,
  `TERMUX_KROOT_REHEARSAL_PATH_CORRECTION_READY`). Use only the corrected
  operator script `353c988f…d6a7`
- **TEST ONLY. NOT EXECUTED ON THE PHONE.** No phone or DEV contact was
  made to prepare it
- Built from merged `main` per the
  [rehearsal preparation](slice-15b2b-b1b3e-b4-termux-kroot-rehearsal.md) §3
- **Real K-ROOT / M-B1 NOT AUTHORIZED**; **PR-1B NOT AUTHORIZED**

```text
rehearsal key != K-ROOT;  rehearsal PASS != M-B1 authorization
```

## 0. Replica B path correction (before any execution)

The first version of this record pointed the operator block at
`$HOME/lilith-owner-freshness/owner-offline-dev-synthetic-01` and listed
`$HOME/lilith-owner-freshness` as its parent. It was stopped before the
phone ran it.

**Owner read-only phone evidence** (the phone was not contacted by this
correction):

```text
REAL_REPLICA_B_DIRECT=FOUND
NESTED_PATH=ABSENT
```

**Canonical real Replica B:** `$HOME/lilith-owner-offline-dev-synthetic-01`,
directly under the Termux `$HOME`. Its parent is `$HOME` itself.

**Root cause.** The rehearsal copied the path from the P3-3B ceremony
design ([P3-3B](slice-15b2b-b1b3e-pr3-p33b-replica-b-ceremony.md) §1 and its
`p33b_phone_commands.sh`, `d7b2f7a3…160a`), which planned the nested
`~/lilith-owner-freshness/` parent. The replica that was actually created
and accepted is not nested. The [P3-3 acceptance](slice-15b2b-b1b3e-pr3-p33-storage-acceptance.md)
§2 records its identity (ID, `REPLICA.json` `c068e533…07c4`, 0 records) but
never restated its path, so the difference was not caught. Those two
records are left unchanged by this correction.

**Correction (operator block only; the bundle is unchanged):**

- `R="$HOME/lilith-owner-offline-dev-synthetic-01"`;
- the snapshot `parent` line lists the `lilith-owner*` entries of `$HOME`,
  the real parent. `$HOME` also holds unrelated entries (`storage`,
  `lilith-p3-3b`, this staging directory), so the full listing is not an
  invariant;
- a new G0 gate, `NESTED_REPLICA_ABSENT`, stops if a replica also exists at
  the old nested path;
- `REPLICA_B_BASELINE_OK` now also requires the canonical name in that
  `parent` line.

No file in the bundle names a replica path (all 75 files checked), so the
bundle was **not rebuilt**. Its tar, `SHA256SUMS`, and source commit
`ff13bc6` stand. Only the operator script changes (§2):
`23f49b50…e227` (withdrawn) → `353c988f…d6a7`.

The canonical path is pinned by
`tests/test_b1b3e_b4_termux_kroot_rehearsal.py` (`OperatorBlockTests`).

## 1. Control source

- **Merged `main`:** `ff13bc6f72156c332b29ad1605d24410c2abf232` (merge of
  PR #112).
- **Tree:** identical to the reviewed `3c05eba`.
- **Contains:**
  - the [B-4 decision](slice-15b2b-b1b3e-b4-kroot-custody-decision.md);
  - `tools/termux_kroot_rehearsal.py`;
  - `tools/build_termux_kroot_rehearsal_bundle.py`;
  - `tests/test_b1b3e_b4_termux_kroot_rehearsal.py`.
- **Build method:** a clean detached worktree at that SHA, using the builder
  from that SHA. The feature branch was not used.

## 2. Final bundle

| Item | Value |
| --- | --- |
| source commit | `ff13bc6f72156c332b29ad1605d24410c2abf232` |
| filename | `lilith-b4-kroot-rehearsal-ff13bc6.tar` |
| size | **1 464 320 bytes** |
| SHA-256 (tar) | `659c50a476c85ff9ed005af97bc70a48989a87890ec53b23f940d97901bee0b3` |
| SHA-256 (`SHA256SUMS` inside the bundle) | `dbb9dfbeaeefb59e47cb2ae64aaa651bbe9b89daa443e0912787c10d0b0e2288` |
| file count | **75** (every file except `SHA256SUMS` itself is listed in it) |
| rehearsal-script SHA-256 | `bb3cef4df621caa17d40ed579fb2bb1f429c0ed469a014532985e0911e687d2f` (equal to `main`) |
| extracted top-level directory | `lilith-b4-kroot-rehearsal-ff13bc6/` |
| determinism | an independent second build is **byte-identical** |
| phone dependency | Termux Python with native `cryptography`, **2 ≤ major < 52, and not 35** (the P3-3B G0 gate) |

**Contents.**

- the 17 import-closure files (the two ceremony tools, three
  `lilith_memory` modules, twelve `lilith_owner_memory` modules);
- the rehearsal script;
- 55 vendor files (`fido2` 2.2.1, `rfc8785` 0.1.4);
- `SOURCE_COMMIT`;
- `SHA256SUMS`.

**Vendor provenance.**

- The vendor files come from the accepted P3-3B bundle, taken after
  verifying its tar (`ce163b63…70dd`) and its `SHA256SUMS`
  (`9bf11b2b…ee2c`).
- All 55 source files are byte-identical to P3-3B's.
- The builder excludes compiled caches by design. So the two stale
  `vendor/rfc8785/__pycache__/*.cpython-312.pyc` files present in the P3-3B
  bundle are **not** included. The phone runs with bytecode writing
  disabled (`-B`, `PYTHONDONTWRITEBYTECODE`).

**No authority material.**

- Scanned for private-key markers (`BEGIN … PRIVATE KEY`), `.der`,
  `.cred`, and `.pem` files, and `k-root`, `secret`, `genesis-pin`, and
  `REPLICA` names: **none**.

**Offline pre-checks (laptop / WSL; no phone).**

1. The extracted final bundle was run in WSL with only its own `vendor/`
   plus `cryptography`. Result: `REHEARSAL=PASS`, all 17 checks PASS,
   nothing left behind. Every LILITH, `fido2`, and `rfc8785` module loaded
   from inside the bundle.
2. The exact §3 command block was run in WSL under a simulated Termux
   layout: a fake `/data/data/com.termux` home, a stub Replica B built from
   the accepted expected manifest `c068e533…07c4`, and the bundle in a fake
   `storage/downloads`. **Every gate printed its PASS token, and no STOP
   line appeared.**
3. After the §0 path correction, the corrected §3 block
   (`353c988f…d6a7`) was run the same way, with the stub Replica B at
   `~/lilith-owner-offline-dev-synthetic-01` and unrelated `~/storage` and
   `~/lilith-p3-3b` entries beside it. Every gate, including the new
   `NESTED_REPLICA_ABSENT`, printed its PASS token; the baseline read
   `parent lilith-owner-offline-dev-synthetic-01`; stderr was empty; no
   STOP line appeared. The simulated layout was then deleted.

The TEST identities of both offline runs are throwaway too, and are burned
like the phone's.

**Laptop staging.** `%USERPROFILE%\lilith-b4-rehearsal\`, outside every Git
tree and OneDrive. It holds:

- the tar;
- `b4_phone_commands.sh` (SHA-256
  `353c988f67cd855372c7037f0b55d8655af63d52bb4ac26a44f1d43a7c98d6a7`,
  exactly the §3 block; it replaces the withdrawn path-wrong
  `23f49b50…e227`, which must not be run);
- `SHA256SUMS.inside-bundle`;
- `BUILD.txt`;
- `STAGING.sha256`.

## 3. Transport and the exact Termux command block

**Transport.**

1. Verify the tar's SHA-256 on the laptop (`certutil -hashfile … SHA256`).
2. Copy **only the tar** by manual MTP into the phone's `Download`. That
   copy is transport only.
3. Unplug the phone.
4. Type the command block below in Termux, or copy it there. The laptop is
   not needed during execution.
5. Turn on airplane mode at the marked PAUSE, before R1.

```bash
# ===== B-4 Termux K-ROOT capability rehearsal: TEST ONLY (bundle lilith-b4-kroot-rehearsal-ff13bc6) =====
# Run in Termux on the S25, one block at a time. Every "STOP" is a hard stop: do not continue past it.
# Nothing here creates a real K-ROOT, uses a real passphrase, or writes to a replica or pin path.
TAR=lilith-b4-kroot-rehearsal-ff13bc6.tar
TAR_SHA=659c50a476c85ff9ed005af97bc70a48989a87890ec53b23f940d97901bee0b3
SUMS_SHA=dbb9dfbeaeefb59e47cb2ae64aaa651bbe9b89daa443e0912787c10d0b0e2288
SRC=ff13bc6f72156c332b29ad1605d24410c2abf232
W="$HOME/lilith-b4-rehearsal"
E="$W/evidence"
B="$W/lilith-b4-kroot-rehearsal-ff13bc6"
R="$HOME/lilith-owner-offline-dev-synthetic-01"                   # the real Replica B, directly under $HOME
TMP="${TMPDIR:-$PREFIX/tmp}"
priv() { case "$(realpath "$1")/" in /data/data/com.termux/*|/data/user/0/com.termux/*) return 0;; *) return 1;; esac; }
snap() { echo "sha $(sha256sum "$R/REPLICA.json" | cut -d' ' -f1)"; echo "records $(ls -A "$R/records" | wc -l)"
         echo "entries $(ls -A "$R" | LC_ALL=C sort | tr '\n' ' ')"; echo "parent $(ls -A "$HOME" | grep '^lilith-owner' | LC_ALL=C sort | tr '\n' ' ')"
         stat -c '%n %i %a %s %Y' "$R" "$R/REPLICA.json" "$R/records" | sed "s#$HOME#~#"; }

# ---- G0 environment (read-only) ----
cd "$HOME"
priv "$HOME" && echo HOME_TERMUX_PRIVATE || echo "STOP: HOME is not Termux private storage"
priv "$TMP" && echo TMP_TERMUX_PRIVATE || echo "STOP: TMPDIR is not Termux private storage"
python -c 'import sys; print("PYTHON", sys.version.split()[0])'
python -c 'import sys, cryptography as c; v = c.__version__; m = int(v.split(".")[0]); print("CRYPTOGRAPHY", v); sys.exit(0 if 2 <= m < 52 and m != 35 else 1)' && echo CRYPTOGRAPHY_OK || echo "STOP: cryptography missing or unsupported"
test ! -e "$W" && echo STAGING_ABSENT || echo "STOP: $W already exists"
ls -A "$TMP" | grep -q lilith-b4-kroot-rehearsal && echo "STOP: stale rehearsal directory in TMPDIR" || echo TMP_NO_STALE
find "$HOME" -name 'k-root*' 2>/dev/null | grep -q . && echo "STOP: a k-root file already exists" || echo NO_KROOT_FILES_BEFORE
test -f "$R/REPLICA.json" && echo REPLICA_B_PRESENT || echo "STOP: Replica B missing"
test ! -e "$HOME/lilith-owner-freshness/owner-offline-dev-synthetic-01" && echo NESTED_REPLICA_ABSENT || echo "STOP: a second Replica B exists at the old nested path"

# ---- G1 Replica B baseline (read-only) ----
mkdir -m 700 "$W" "$E"
{ echo "HOME_PRIVATE $(priv "$HOME" && echo yes || echo no)"; echo "TMP_PRIVATE $(priv "$TMP" && echo yes || echo no)"
  python -c 'import sys, platform, cryptography as c; print("PYTHON", sys.version.split()[0], "CRYPTOGRAPHY", c.__version__, "MACHINE", platform.machine())'; } > "$E/g0.txt"
snap > "$E/replica-b-before.txt"; cat "$E/replica-b-before.txt"
grep -qx "sha c068e5331ccd7fa0f69f2b38d25849497b86edea843598784235874080c107c4" "$E/replica-b-before.txt" && grep -qx "records 0" "$E/replica-b-before.txt" && grep -qE "^parent (.* )?lilith-owner-offline-dev-synthetic-01 " "$E/replica-b-before.txt" && echo REPLICA_B_BASELINE_OK || echo "STOP: Replica B is not the accepted empty replica"

# ---- T1 transport copy -> private staging, then verify ----
cp "$HOME/storage/downloads/$TAR" "$W/"
cd "$W"
echo "$TAR_SHA  $TAR" | sha256sum -c - || echo "STOP: bundle hash differs"
tar -xf "$TAR"
cd "$B"
echo "$SUMS_SHA  SHA256SUMS" | sha256sum -c - || echo "STOP: SHA256SUMS digest differs"
sha256sum -c --quiet SHA256SUMS && echo BUNDLE_VERIFIED || echo "STOP: SHA256SUMS verification failed"
test "$(cat SOURCE_COMMIT)" = "$SRC" && echo SOURCE_COMMIT_OK || echo "STOP: source commit differs"
test "$(find "$B" -type f | wc -l)" = 75 && echo FILE_COUNT_OK || echo "STOP: unexpected file count"
priv "$B" && echo BUNDLE_IN_TERMUX_PRIVATE || echo "STOP: bundle is not in Termux private storage"

# ---- PAUSE: turn ON airplane mode and unplug USB now. The rehearsal needs no network or laptop. ----

# ---- R1 the rehearsal (throwaway TEST key; temporary files removed by the script) ----
export PYTHONPATH="$B/vendor"
export PYTHONDONTWRITEBYTECODE=1
python -B "$B/services/owner-memory-control/tools/termux_kroot_rehearsal.py" rehearse > "$E/rehearsal.json" 2> "$E/rehearsal.stderr"
echo "exit=$?" | tee "$E/rehearsal.exit"                                                     # exit=0
tail -1 "$E/rehearsal.json"                                                                   # B4_KROOT_REHEARSAL=PASS
python - "$E/rehearsal.json" > "$E/gate.txt" <<'PYEOF'
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
cat "$E/gate.txt"                                                                             # REHEARSAL_GATE_PASS + 6 BURNED lines

# ---- V verification (read-only) ----
{ ls -A "$TMP" | grep -q lilith-b4-kroot-rehearsal && echo "STOP: rehearsal directory left in TMPDIR" || echo TMP_CLEAN
  find "$HOME" \( -name 'k-root*' -o -name '*REHEARSAL-TEST*' \) 2>/dev/null | grep -q . && echo "STOP: a TEST key file remains" || echo NO_KEY_FILE_ANYWHERE
  test "$(find "$B" -type f | wc -l)" = 75 && (cd "$B" && sha256sum -c --quiet SHA256SUMS) && echo BUNDLE_UNCHANGED || echo "STOP: unexpected file in bundle"
  test -s "$E/rehearsal.stderr" && echo "STOP: rehearsal wrote to stderr" || echo STDERR_EMPTY; } | tee "$E/verify.txt"
snap > "$E/replica-b-after.txt"
cmp "$E/replica-b-before.txt" "$E/replica-b-after.txt" && echo REPLICA_B_UNCHANGED | tee -a "$E/verify.txt" || echo "STOP: Replica B changed"
sha256sum "$E"/* > "$W/evidence.sha256"; cat "$W/evidence.sha256"

# ---- Cleanup of the transport copy only (after every line above passed) ----
cmp "$HOME/storage/downloads/$TAR" "$W/$TAR" && rm "$HOME/storage/downloads/$TAR" && echo TRANSPORT_COPY_REMOVED
# Keep "$W" (bundle + evidence). It holds no key. Airplane mode may be turned off afterwards.
# =============================== end of B-4 rehearsal ===============================
```

## 4. Expected PASS output

In order:

- `HOME_TERMUX_PRIVATE`
- `TMP_TERMUX_PRIVATE`
- `CRYPTOGRAPHY <version>`, `CRYPTOGRAPHY_OK`
- `STAGING_ABSENT`
- `TMP_NO_STALE`
- `NO_KROOT_FILES_BEFORE`
- `REPLICA_B_PRESENT`
- `NESTED_REPLICA_ABSENT`
- the Replica B baseline:
  - `sha c068e5331ccd7fa0f69f2b38d25849497b86edea843598784235874080c107c4`
  - `records 0`
  - `entries REPLICA.json records`
  - `parent lilith-owner-offline-dev-synthetic-01` (the `lilith-owner*`
    entries of `$HOME`; an empty leftover `lilith-owner-freshness` may also
    appear and is not a STOP, since `NESTED_REPLICA_ABSENT` already passed)
  - three stat lines, for `~/lilith-owner-offline-dev-synthetic-01`, its
    `REPLICA.json`, and its `records`
- `REPLICA_B_BASELINE_OK`
- `lilith-b4-kroot-rehearsal-ff13bc6.tar: OK`
- `SHA256SUMS: OK`
- `BUNDLE_VERIFIED`
- `SOURCE_COMMIT_OK`
- `FILE_COUNT_OK`
- `BUNDLE_IN_TERMUX_PRIVATE`
- `exit=0`
- `B4_KROOT_REHEARSAL=PASS`
- `REHEARSAL_GATE_PASS`, followed by six `BURNED …` lines and one `ENV …`
  line
- `TMP_CLEAN`
- `NO_KEY_FILE_ANYWHERE`
- `BUNDLE_UNCHANGED`
- `STDERR_EMPTY`
- `REPLICA_B_UNCHANGED`
- the `evidence.sha256` listing
- `TRANSPORT_COPY_REMOVED`

## 5. STOP conditions

Any line beginning `STOP`, or any missing PASS token, is a hard stop. Covered
explicitly:

- the bundle hash differs;
- the `SHA256SUMS` digest or verification fails;
- the source commit differs;
- the file count differs;
- HOME, TMPDIR, or the bundle is not in Termux private storage;
- the staging directory already exists;
- a stale rehearsal directory or an existing `k-root*` file is present
  before the run;
- `cryptography` is missing or unsupported;
- Replica B is missing at `~/lilith-owner-offline-dev-synthetic-01`, is not
  the accepted empty replica, or is not listed under `$HOME`;
- a second Replica B exists at the old nested
  `~/lilith-owner-freshness/owner-offline-dev-synthetic-01`;
- the rehearsal exits non-zero, its final line is not
  `B4_KROOT_REHEARSAL=PASS`, or `REHEARSAL_GATE_PASS` is not printed. This
  covers key mode ≠ `0600`, a second file, encryption at rest, overwrite
  refusal, wrong-passphrase refusal, function-vs-CLI mismatch,
  non-deterministic `reproduce`, `registryVerified` false, and a cleanup
  failure;
- anything is left in TMPDIR, any `k-root*` or `*REHEARSAL-TEST*` file
  remains, the bundle changed, or the rehearsal wrote to stderr;
- **Replica B changed**: hash, record count, entries, the `lilith-owner*`
  listing of `$HOME`, or inode, mode, size, or mtime;
- any network or DEV / cloud attempt. The source has no network import
  (test-enforced), and airplane mode during R1 makes any attempt fail
  visibly.

**After a STOP:**

- Do not retry and do not edit anything.
- Keep `~/lilith-b4-rehearsal/`.
- Report the evidence.

The TEST key is throwaway, so there is no custody consequence.

## 6. Burned identities

Every identity the rehearsal creates is **permanently burned**:

- both rehearsal root-key fingerprints;
- the synthetic K-ACT and K-WIT fingerprints;
- the rehearsal registry digest;
- the rehearsal genesis-candidate digest.

This applies to the phone run's six `BURNED` lines and to the offline
pre-check runs. None may ever be used or accepted in:

- M-B1 (K-ROOT);
- M-B2 (K-WIT);
- the real registry v1;
- the witness genesis or genesis pin;
- record 1 or any acceptance envelope;
- any later lineage.

The real M-B1 review must check that the real K-ROOT fingerprint is not
among them.

## 7. Evidence (kept privately on the phone)

Directory `~/lilith-b4-rehearsal/`:

- the extracted bundle;
- the tar;
- `evidence/`:
  - `g0.txt`;
  - `replica-b-before.txt`;
  - `rehearsal.json`, `rehearsal.stderr`, `rehearsal.exit`;
  - `gate.txt`;
  - `verify.txt`;
  - `replica-b-after.txt`;
- `evidence.sha256`.

**For the review, the owner reports:**

- `gate.txt`, including the `BURNED` lines;
- `verify.txt`;
- the G0 versions;
- the before and after Replica B lines;
- `evidence.sha256`.

No private material exists to report: the TEST key files were deleted by
the script. The phone need not reconnect to the laptop to run the
rehearsal. Reporting may be done by transcription or a later owner-chosen
transfer.

## 8. Next (not authorized here)

A separate review of the owner-reported evidence
([preparation](slice-15b2b-b1b3e-b4-termux-kroot-rehearsal.md) §6). Only after
that review, with B-3 and B-5 resolved, may the real M-B1 be prepared.

## Explicitly not done

```text
NO PHONE CONTACT
NO DEV CONTACT
NO REAL K-ROOT
NO K-WIT
NO GENESIS PIN
NO REAL_ACCEPTANCE_ENABLED CHANGE
NO REAL RECORD 1
REAL FRESHNESS REMAINS UNKNOWN
PR-1B NOT AUTHORIZED
FIRST MEMORY NOT AUTHORIZED
```
