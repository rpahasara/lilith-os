# Slice 15B2b-B1b-3e — B-4 Termux K-ROOT Capability Rehearsal (prepared, not executed)

Status:

- **PREPARED FOR REVIEW. NOT EXECUTED.** The bundle is built only after
  this record's source is merged (§3)
- **TEST ONLY**: a throwaway TEST key and synthetic inputs. **No real
  K-ROOT**, no real passphrase, no genesis pin, no replica touched
- Authorized by the [B-4 decision](slice-15b2b-b1b3e-b4-kroot-custody-decision.md):
  "preparation and review", separately reviewed before the real M-B1
- **Real M-B1 NOT AUTHORIZED**; **PR-1B NOT AUTHORIZED**

```text
rehearsal key != K-ROOT;  rehearsal PASS != M-B1 authorization
capability on Termux != custody established
```

## 1. Why

K-ROOT custody Option A1 puts `root-keygen`, `registry-v1`, and `reproduce`
of `services/authority-dev/ceremony/lilith_authority_owner_dev.py` on the
S25 in Termux.

- The Termux Replica B bundle (P3-3B) proved that the owner-freshness
  import graph runs there.
- The K-ROOT paths have **never** run there:
  - encrypted PKCS#8 generation (`BestAvailableEncryption`);
  - Ed25519 registry signing;
  - genesis-candidate reproduction.

This rehearsal proves they work on the phone before a real key exists.

## 2. What the rehearsal does

`services/owner-memory-control/tools/termux_kroot_rehearsal.py rehearse`
runs only when `$TMPDIR` resolves into Termux private app storage
(`/data/data/com.termux/…` or `/data/user/0/com.termux/…`). It uses one
fresh `mkdtemp` directory, `.lilith-b4-kroot-rehearsal-TEST-*`, which it
removes at the end.

| Check | What it proves |
| --- | --- |
| `rootKeygen`, `keyFileRegular0600`, `keyFileOnlyEntry` | the tool function writes exactly one regular `0600` file, and no temporary or second copy |
| `keyNotLoadableWithoutPassphrase`, `keyNotLoadableWithWrongPassphrase` | the file is encrypted at rest |
| `anchorMatchesKeyAndFingerprint` | the anchor public key equals the decrypted key, `publicKeySha256` = SHA-256 of the raw public key, and `rootKeyId` / `environment` are as the tool pins them |
| `existingKeyNeverOverwritten`, `shortPassphraseRefused` | `O_EXCL`, and the 12-byte minimum with nothing written |
| `rootKeygenCli` | the tool's own `main` entry point writes a `0600` key; a second run produces a **different** key |
| `syntheticInputs` | throwaway K-ACT / K-WIT publications built with the **production** constructors (`lilith_authority_keygen_dev.publication`, `pr1_bootstrap.witness_publication`). The synthetic machine ID is never the DEV machine ID |
| `registryV1`, `registryV1CliEqualsFunction` | Ed25519 registry v1 signing; the CLI output is byte-identical to the function (deterministic signature) |
| `registryV1WrongPassphraseRefused` | a wrong passphrase refuses with no output |
| `witnessAnchor` | CLI = function |
| `reproduceDeterministicAndVerified` | function ×2 = CLI; `registryVerified=true`; `authorityGranted=false`; pin = candidate digest; environment `dev` |
| `cleanup` | the directory and every file are removed |

**Transcript.** It holds public values only:

- every check;
- the removed entries;
- Python and `cryptography` versions and the architecture;
- `realAuthorityMaterial=NONE`;
- **`burnedTestIdentities`**: both rehearsal root-key fingerprints, the
  synthetic K-ACT and K-WIT fingerprints, the rehearsal registry digest,
  and the rehearsal genesis-candidate digest. None of them may ever appear
  in a real anchor, registry, pin, or record.

**Not exercised** (residual, for the real M-B1 preparation):

- interactive `getpass` on Termux (the TEST passphrase is injected);
- the real K-ROOT directory in Termux private `$HOME`;
- directory fsync for the key file. The tool fsyncs the file only.

## 3. Source, tests, bundle

| File | Role |
| --- | --- |
| `services/owner-memory-control/tools/termux_kroot_rehearsal.py` | the rehearsal. Offline: no socket, HTTP, subprocess, or `getpass`. It writes only inside its temporary directory |
| `services/owner-memory-control/tools/build_termux_kroot_rehearsal_bundle.py` | the deterministic laptop-side bundle builder (sorted, mtime 0, 0:0, 0644 / 0755). Files come from `git show <commit>:<path>` |
| `services/owner-memory-control/tests/test_b1b3e_b4_termux_kroot_rehearsal.py` | 11 offline tests (§5) |

**Bundle contents** (`CLOSURE`, pinned by a test to the exact AST import
closure of the two ceremony tools):

- `lilith_authority_owner_dev.py` and `lilith_authority_keygen_dev.py`;
- three `lilith_memory` modules;
- twelve `lilith_owner_memory` modules;
- the rehearsal script;
- `vendor/` (`fido2` 2.2.1 and `rfc8785` 0.1.4, pure Python);
- `SOURCE_COMMIT`;
- `SHA256SUMS`.

The files keep repository paths (`services/…`) because the owner tool
resolves its imports from them. `cryptography` is native and must already
be installed in Termux (the P3-3B G0 gate).

**Vendor source.** The vendor files are the `vendor/` directory of the
accepted P3-3B bundle, taken only after both hashes verify:

- `lilith-p3-3b-44a53f2.tar`: SHA-256 `ce163b63…70dd`;
- its `SHA256SUMS`: `9bf11b2b…ee2c`.

Every file was verified against its wheel `RECORD` at P3-3B.

**Build procedure (after merge, on the laptop, offline).**

1. Use a clean checkout at the merged `main` SHA.
2. Verify the P3-3B tar and its `SHA256SUMS`, then extract `vendor/` into a
   staging directory.
3. Run the builder:

   ```bash
   python services/owner-memory-control/tools/build_termux_kroot_rehearsal_bundle.py \
     --repo . --commit <merged SHA> --vendor-dir <staging>/vendor --out <staging>/lilith-b4-kroot-rehearsal-<sha7>.tar
   ```

4. Record the printed `tarSha256` and `sha256sumsSha256`, then stage them
   in `%USERPROFILE%\lilith-b4-rehearsal\`, outside every Git tree and
   OneDrive.

The bundle identity is therefore recorded in the staging step, not here.

## 4. Phone commands (owner-executed, Termux)

The transport is the same as P3-3B: one manual MTP copy into `Download`,
which is transport only. The phone stays disconnected otherwise: no ADB,
no SSH.

```bash
# ================= B-4 Termux K-ROOT capability rehearsal (TEST ONLY) =================
# Every "STOP if" is a hard stop. Nothing here creates a real K-ROOT or touches a replica.
TAR=lilith-b4-kroot-rehearsal-<sha7>.tar          # from the staging record
TAR_SHA=<tarSha256>                                # from the staging record
SUMS_SHA=<sha256sumsSha256>                        # from the staging record

# ---- G0 preconditions (read-only) ----
cd "$HOME"
python -c 'import sys; print("PYTHON", sys.version.split()[0])'
python -c 'import sys, cryptography as c; v = c.__version__; m = int(v.split(".")[0]); print("CRYPTOGRAPHY", v); sys.exit(0 if 2 <= m < 52 and m != 35 else 1)' || echo "STOP: cryptography missing or unsupported"
test ! -e "$HOME/lilith-b4-rehearsal" && echo STAGING_ABSENT                                     # STOP if not printed
R="$HOME/lilith-owner-offline-dev-synthetic-01"                                                  # the real Replica B (staging record §0)
sha256sum "$R/REPLICA.json"; ls -A "$R/records" | wc -l                                        # c068e533…07c4 / 0 (record before)

# ---- T1 transport + bundle verification ----
mkdir -m 700 "$HOME/lilith-b4-rehearsal" "$HOME/lilith-b4-rehearsal/evidence"
cp "$HOME/storage/downloads/$TAR" "$HOME/lilith-b4-rehearsal/"
cd "$HOME/lilith-b4-rehearsal"
echo "$TAR_SHA  $TAR" | sha256sum -c -                                                           # STOP unless OK
tar -xf "$TAR"
B="$HOME/lilith-b4-rehearsal/${TAR%.tar}"
E="$HOME/lilith-b4-rehearsal/evidence"
cd "$B"
echo "$SUMS_SHA  SHA256SUMS" | sha256sum -c -                                                     # STOP unless OK
sha256sum -c --quiet SHA256SUMS && echo BUNDLE_VERIFIED                                          # STOP if not printed
cat SOURCE_COMMIT                                                                                 # = the merged SHA

# ---- R1 the rehearsal (temporary TEST files only, removed by the script) ----
export PYTHONPATH="$B/vendor"
export PYTHONDONTWRITEBYTECODE=1
python -B "$B/services/owner-memory-control/tools/termux_kroot_rehearsal.py" rehearse | tee "$E/rehearsal.json"
tail -1 "$E/rehearsal.json"                                                                       # B4_KROOT_REHEARSAL=PASS

# ---- V verification (read-only) ----
ls -A "${TMPDIR:-$PREFIX/tmp}" | grep -q lilith-b4-kroot-rehearsal && echo "STOP: TEST dir left" || echo TMP_CLEAN
sha256sum "$R/REPLICA.json"; ls -A "$R/records" | wc -l                                        # unchanged: c068e533…07c4 / 0
find "$HOME" -name 'k-root*' 2>/dev/null | grep -v "^$B/" || echo NO_KEY_FILE_OUTSIDE_BUNDLE
sha256sum "$E"/* > "$HOME/lilith-b4-rehearsal/evidence.sha256"; cat "$HOME/lilith-b4-rehearsal/evidence.sha256"
# ============================== end of B-4 rehearsal ==============================
```

**Afterwards:**

- Remove the `Download` transport copy.
- Keep `~/lilith-b4-rehearsal/` (bundle and evidence) for review.
- It holds no key: the script removed every TEST key.

**Owner-reported evidence for the review:**

- `rehearsal.json`;
- the G0 versions;
- `BUNDLE_VERIFIED`;
- `TMP_CLEAN`;
- `NO_KEY_FILE_OUTSIDE_BUNDLE`;
- the Replica B before and after lines;
- `evidence.sha256`.

**If any STOP fires or the result is `FAIL`:**

- Do not retry by editing anything.
- Report the transcript.
- The TEST key was throwaway, so no custody consequence arises.

## 5. Offline tests

`test_b1b3e_b4_termux_kroot_rehearsal.py` (11 tests):

- the full rehearsal PASSes on POSIX with every named check, and leaves the
  base directory empty;
- every created identity is reported as burned, distinct, and 64-hex; two
  runs never share a root key;
- the transcript contains no passphrase, private key, or PEM/DER marker;
- nothing is written outside the temporary directory: `HOME` is
  unchanged;
- a failing step is contained, and cleanup still runs;
- the Termux gate refuses non-Termux storage;
- usage refusals;
- the source is offline and TEST-marked, and its synthetic machine ID is
  not the DEV machine ID;
- `CLOSURE` equals the exact AST import closure;
- the bundle is deterministic and exact: member set, `SHA256SUMS`,
  modes, owner, mtime, `SOURCE_COMMIT`;
- builder refusals: non-40-hex commit, missing commit, vendor-set
  mismatch, existing output.

## 6. Review gate before the real M-B1

The real M-B1 may be prepared only after:

1. this source is merged and the bundle is built and staged from the
   merged SHA;
2. the owner runs §4 and reports the evidence;
3. a separate review accepts `B4_KROOT_REHEARSAL=PASS`, `TMP_CLEAN`,
   `NO_KEY_FILE_OUTSIDE_BUNDLE`, and Replica B unchanged, and records the
   burned identities;
4. B-3 and B-5 are resolved, and PR-2 is revalidated immediately before
   `CHECK_ELIGIBILITY`.

## 7. Nonclaims

This preparation does **not**:

- generate, test, or custody a real K-ROOT;
- use or define the real passphrase;
- create a genesis pin, K-WIT, registry, record 1, or envelope;
- touch either owner replica;
- establish phone-compromise resistance;
- lift `REAL_ACCEPTANCE_ENABLED`;
- authorize M-B1 or PR-1B.

## Explicitly not done

```text
REHEARSAL NOT EXECUTED
NO K-ROOT GENERATED
NO K-WIT GENERATED
NO GENESIS PIN CREATED
NO DEV / PHONE / REPLICA CONTACT
NO REAL_ACCEPTANCE_ENABLED CHANGE
NO REAL RECORD 1
REAL FRESHNESS REMAINS UNKNOWN
PR-1B NOT AUTHORIZED
FIRST MEMORY NOT AUTHORIZED
```
