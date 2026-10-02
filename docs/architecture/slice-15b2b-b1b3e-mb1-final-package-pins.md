# Slice 15B2b-B1b-3e — M-B1: Final Package Pins (Finalization Record)

Status:

- **`MB1_FINAL_PACKAGE_PINNED_READY_FOR_REVIEW`.** This record pins the
  **final** M-B1 bundle and operator script. Both are rebuilt from the exact
  merged `main` that landed the
  [M-B1 source and design](slice-15b2b-b1b3e-mb1-kroot-ceremony-package.md)
  (PR #123).
- **Condition 1 closes only when this record is reviewed and merged.** On
  merge, Condition 1 becomes `MB1_PACKAGE_REVIEWED_AND_MERGED`. Before then
  it stays **NOT CLOSED**.
- The provisional design pins in the source-and-design record (bundle
  `08cfe650…` from `3ec71c1`, script `a63bf5aa…`) are **superseded and must
  not be used**. Their `SOURCE_COMMIT` is not merged `main`.
- **M-B1 is NOT AUTHORIZED.** Conditions 2–5 of the
  [B-5 grant](slice-15b2b-b1b3e-b5-pr1b-authorization-granted.md) §2 are
  untouched.
- There was no phone contact, no DEV contact, no Replica B contact, and no
  key generation of any kind. No simulation was run for this record, so no
  new identity exists to burn.

```text
package finalized != package reviewed and merged != M-B1 authorized != M-B1 executed
```

## 1. Final pins

| Item | Value |
| --- | --- |
| **source commit** | `1e2eae30fb7023a44776d1f8d25e2bb958955e6a`: the merge of PR #123 into `main` (parent `c694061`). It is `SOURCE_COMMIT` inside the bundle |
| bundle | `lilith-mb1-kroot-1e2eae3.tar` |
| **bundle SHA-256** | `7f07e158aa5a0b3c31ee63e25ae25116c92f26a402bc6924422d7c95e2edc2c1` |
| `SHA256SUMS` (inside the bundle) | `4816f8c93de7a2088fd3570edbdf141a2a1db12bedd330da46d83fd9336c6498` |
| files | **74**: 17 source files + 55 vendor files + `SOURCE_COMMIT` + `SHA256SUMS` |
| top directory | `lilith-mb1-kroot-1e2eae3/` |
| **operator script** | `mb1_phone_commands.sh`, **SHA-256 `4e463796ced5c8375fd45bbf318cee9c7222ab9e5d9b9e20190ab451a470c091`**, 20128 bytes; exactly the §3 block |
| builder | `services/owner-memory-control/tools/build_mb1_kroot_bundle.py`, unchanged at `1e2eae3` |
| laptop staging | `%USERPROFILE%\lilith-mb1-package\`: the final tar, the final script, and `STAGING.sha256`. The provisional `3ec71c1` tar and `a63bf5aa` script are under `superseded/` |

The owner's M-B1 go statement (Condition 5) must name **these two
values**: bundle `7f07e158…c2c1` and script `4e463796…c091`.

## 2. How the pins were produced

All of it ran on the laptop, offline, with no key material.

1. PR #123 was merged with `--match-head-commit 26773b6` after all four
   checks passed (Repository contracts, Frontend build and command core,
   Core API tests, LILITH DEV deployment). The new `origin/main` is
   `1e2eae3`.
2. **Two independent clean worktrees** were created, both detached at
   `1e2eae3`, with an empty `git status`.
3. **The vendor set:**
   - It was taken from the verified B-4 bundle `659c50a4…` (its own
     `SHA256SUMS` was re-verified).
   - It was cross-checked to be byte-identical to the vendor set of the
     provisional bundle `08cfe650…` (whose `SHA256SUMS` was also
     re-verified).
   - 55 files: `fido2` 2.2.1 and `rfc8785` 0.1.4, with their dist-info.
4. The builder ran once in each worktree:
   `build_mb1_kroot_bundle.py --repo . --commit 1e2eae30… --vendor-dir … --out …`.
   - Both runs printed the same `tarSha256`, `sha256sumsSha256`,
     `files=74`, and `sourceCommit=1e2eae30…`.
   - **The two tars are byte-identical** (`cmp`).
5. **Contents check:**
   - `SOURCE_COMMIT` equals `1e2eae30fb7023a44776d1f8d25e2bb958955e6a`.
   - `SHA256SUMS` verifies all 73 other members.
   - Every member is regular or a directory, with mtime 0 and owner 0:0.
   - No member name suggests key material.
   - **Against the provisional bundle**, the member set is identical. Only
     `SOURCE_COMMIT` and `SHA256SUMS` differ, so all 17 source files and all
     55 vendor files are byte-identical. (No closure file changed between
     `3ec71c1` and `1e2eae3`.)
6. **Burned-identity refusal, from inside the final bundle.**
   - The bundle was extracted, with `PYTHONPATH` set to the bundle only. It
     was confirmed that `burned_identities` loads from the bundle.
   - The merged script's `BURNED_CHECK` snippet **refused all 20 canonical
     identities (20/20)**, and accepted a fresh random value.
   - No identity was printed.

## 3. Final operator script

The final script is the reviewed v3 block (§4 of the source-and-design
record, `a63bf5aa…`) with **exactly six lines changed**, and nothing else:

| Line | Provisional (`a63bf5aa…`) | Final |
| --- | --- | --- |
| header | `(bundle lilith-mb1-kroot-3ec71c1)` | `(bundle lilith-mb1-kroot-1e2eae3)` |
| `TAR=` | `lilith-mb1-kroot-3ec71c1.tar` | `lilith-mb1-kroot-1e2eae3.tar` |
| `TAR_SHA=` | `08cfe650…cb8ec78` | `7f07e158…edc2c1` |
| `SUMS_SHA=` | `44e453ac…b7a619` | `4816f8c9…6c6498` |
| `SRC=` | `3ec71c176963…d555` | `1e2eae30fb70…955e6a` |
| `B=` | `"$W/lilith-mb1-kroot-3ec71c1"` | `"$W/lilith-mb1-kroot-1e2eae3"` |

`NFILES=74`, every path, every gate, the custody code, and every Python
snippet are unchanged. A test re-derives this block from the merged v3 block
by these six substitutions and requires byte equality.

**Known cosmetic note, left unchanged on purpose:** the comment above
`BURNED_CHECK` still says "the 12 permanently burned rehearsal identities".
The check itself asserts `len(every) == BI.CANONICAL_COUNT == 20`, and
refused 20/20 (§2). The comment is kept as reviewed so that the final script
differs from the reviewed v3 only in the pins.

`mb1_phone_commands.sh` (SHA-256 `4e463796ced5c8375fd45bbf318cee9c7222ab9e5d9b9e20190ab451a470c091`) is exactly this block:

```bash
# ===== M-B1: real K-ROOT generation (DEV_SYNTHETIC), S25 Termux ONLY (bundle lilith-mb1-kroot-1e2eae3) =====
# Run ONLY after the owner's separate, explicit M-B1 go statement; ONLY on the S25; ONLY as a file; in a LOCAL
# Termux session (never SSH); with airplane mode ON and USB unplugged BEFORE starting:
#   bash "$HOME/storage/downloads/mb1_phone_commands.sh" 2>&1 | tee "$HOME/lilith-mb1.transcript.txt"; echo "RUN_EXIT=${PIPESTATUS[0]}" | tee -a "$HOME/lilith-mb1.transcript.txt"
# The ONLY private write is $KEY (root-keygen: O_EXCL, O_NOFOLLOW, 0600). The passphrase is typed ONLY into this
# phone's terminal (getpass on /dev/tty); it is never an argument, a variable, or a file. Only public files leave.
# stop() is the only STOP path: it prints "STOP: ..." on stderr and exits 1. After a STOP: do not retry, delete, or edit.
# Any STOP (or signal) after root-keygen starts runs fail_custody(): a generated candidate becomes a permanently burned
# FAILED_GENERATED_CANDIDATE (quarantined on the phone, public identity recorded and exported); it is NEVER K-ROOT.
set -u
KEYGEN_STARTED=0
CUSTODY_RUNNING=0
stop() { builtin echo "STOP: $*" >&2; [ "$KEYGEN_STARTED" = 1 ] && fail_custody "$*"; exit 1; }
trap '' PIPE
trap 'stop "interrupted by a signal"' INT TERM HUP
vpass() { builtin echo "$1"; builtin echo "$1" >> "$E/verify.txt" || stop "cannot write verify.txt"; }
TAR=lilith-mb1-kroot-1e2eae3.tar
TAR_SHA=7f07e158aa5a0b3c31ee63e25ae25116c92f26a402bc6924422d7c95e2edc2c1
SUMS_SHA=4816f8c93de7a2088fd3570edbdf141a2a1db12bedd330da46d83fd9336c6498
SRC=1e2eae30fb7023a44776d1f8d25e2bb958955e6a
NFILES=74
DL="$HOME/storage/downloads"
W="$HOME/lilith-mb1"                                   # staging and PUBLIC evidence
E="$W/evidence"
B="$W/lilith-mb1-kroot-1e2eae3"
K="$HOME/lilith-kroot-dev-synthetic"                   # the ONLY place private K-ROOT material may exist
KEY="$K/k-root.der"
PUB="$HOME/lilith-kroot-dev-synthetic-public"          # the authoritative S25 copy of the PUBLIC anchor and fingerprint
X="$HOME/lilith-mb1-export.tar"                         # public-only export for the laptop
R="$HOME/lilith-owner-offline-dev-synthetic-01"         # Replica B: read only
FC="$HOME/lilith-mb1-failed-candidate"                 # PUBLIC burn record of a failed generated candidate
QK="$HOME/lilith-kroot-dev-synthetic.FAILED-CANDIDATE"  # quarantined private candidate: stays on the S25, never K-ROOT
FX="$HOME/lilith-mb1-failed-candidate-export.tar"       # public-only failure export for the laptop
TMP="${TMPDIR:-$PREFIX/tmp}"
priv() { case "$(realpath "$1")/" in /data/data/com.termux/*|/data/user/0/com.termux/*) return 0;; *) return 1;; esac; }
snap() { echo "sha $(sha256sum "$R/REPLICA.json" | cut -d' ' -f1)"; echo "records $(ls -A "$R/records" | wc -l)"
         echo "entries $(ls -A "$R" | LC_ALL=C sort | tr '\n' ' ')"; echo "parent $(ls -A "$HOME" | grep '^lilith-owner' | LC_ALL=C sort | tr '\n' ' ')"
         stat -c '%n %i %a %s %Y' "$R" "$R/REPLICA.json" "$R/records" | sed "s#$HOME#~#"; }
# Validates the root-keygen output: exactly the public anchor and its fingerprint (argv[1] = root-keygen.json).
ANCHOR_CHECK=$(cat <<'PYEOF'
import base64, hashlib, json, sys
from lilith_owner_memory import authority_contracts as A
d = json.load(open(sys.argv[1]))
assert isinstance(d, dict) and set(d) == {"registryRoot", "publicKeySha256"}, "unexpected root-keygen output"
root = A.TrustedRegistryRootV1.from_dict(d["registryRoot"])
raw = base64.urlsafe_b64decode(d["registryRoot"]["publicKey"] + "==")
assert len(raw) == 32 and raw == root.public_key, "anchor key is not a raw 32-byte Ed25519 key"
assert root.environment == "dev" and root.root_key_id == "test-only.registry-root.dev-synthetic.b1b3d.1", "anchor scope"
assert hashlib.sha256(raw).hexdigest() == d["publicKeySha256"], "fingerprint differs from the anchor key"
print("ANCHOR_VALID")
print("FINGERPRINT " + d["publicKeySha256"])
PYEOF
)
# Refuses a real identity that equals ANY of the 12 permanently burned rehearsal identities (argv[1] = fingerprint).
BURNED_CHECK=$(cat <<'PYEOF'
import sys
from lilith_owner_memory import burned_identities as BI
fp = sys.argv[1]
every = BI.BURNED_PUBLIC_KEY_SHA256 | BI.BURNED_REGISTRY_DIGESTS | BI.BURNED_GENESIS_WITNESS_DIGESTS
assert len(every) == BI.CANONICAL_COUNT == 20, "burned set is not the 20 canonical identities"
if fp in every:
    sys.exit("real K-ROOT fingerprint equals a burned rehearsal identity")
print("NOT_A_BURNED_IDENTITY")
PYEOF
)
# The key file is encrypted at rest: it must not load without a passphrase (argv[1] = key path).
AT_REST_CHECK=$(cat <<'PYEOF'
import sys
from cryptography.hazmat.primitives.serialization import load_der_private_key
try:
    load_der_private_key(open(sys.argv[1], "rb").read(), password=None)
except TypeError:
    print("KEY_ENCRYPTED_AT_REST")
else:
    sys.exit("the key file loads without a passphrase")
PYEOF
)
# The owner proves the passphrase unlocks the key and the key matches the anchor. The passphrase is read by
# getpass from this phone's terminal only; nothing is printed but the result (argv[1] = key, argv[2] = anchor json).
UNLOCK_CHECK=$(cat <<'PYEOF'
import base64, getpass, importlib.util, json, sys
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
spec = importlib.util.spec_from_file_location("owner_tool", sys.argv[3])
tool = importlib.util.module_from_spec(spec); spec.loader.exec_module(tool)
anchor = json.load(open(sys.argv[2]))["registryRoot"]
key = tool._root_key(sys.argv[1], getpass.getpass("K-ROOT passphrase (unlock check): ").encode("utf-8"))
if key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw) != base64.urlsafe_b64decode(anchor["publicKey"] + "=="):
    sys.exit("the unlocked key does not match the anchor")
del key
print("KEY_UNLOCKS_AND_MATCHES_ANCHOR")
PYEOF
)
# Reads the candidate fingerprint for the burn record, tolerating a damaged file (argv[1] = root-keygen.json).
FP_EXTRACT=$(cat <<'PYEOF'
import json, re, sys
try:
    fp = json.load(open(sys.argv[1]))["publicKeySha256"]
    print(fp if re.fullmatch(r"[0-9a-f]{64}", fp) else "UNKNOWN")
except Exception:
    print("UNKNOWN")
PYEOF
)
# Failure custody: never calls stop() and never exits. EVERY step is checked. Any failure leaves custody INCOMPLETE:
# nothing is ever deleted, the candidate stays exactly where it is, and the result is a hard incident that needs
# manual, reviewed recovery. "custody complete" is printed only when every step succeeded.
fail_custody() {
  [ "$CUSTODY_RUNNING" = 1 ] && return 0
  CUSTODY_RUNNING=1
  trap '' INT TERM HUP                                   # custody runs to the end; a second signal cannot cut it short
  if ! test -e "$KEY" && ! test -L "$KEY"; then
    builtin echo "NO_CANDIDATE_GENERATED: root-keygen wrote no key file"
    builtin echo "MB1_INCIDENT: generation was attempted. MANUAL, REVIEWED RECOVERY IS REQUIRED before any deletion or rerun."
    return 0
  fi
  ok=1
  cfp=UNKNOWN
  builtin echo "FAILED_GENERATED_CANDIDATE: recording, withdrawing, quarantining, and exporting the failed candidate"
  if mkdir -m 700 "$FC"; then
    printf '%s\n' "$1" > "$FC/reason.txt" || miss "cannot write reason.txt"
    if test -f "$E/root-keygen.json"; then
      cp "$E/root-keygen.json" "$FC/candidate-anchor.json" || miss "cannot copy the candidate anchor"
      cfp=$(python -B -c "$FP_EXTRACT" "$E/root-keygen.json") || cfp=UNKNOWN
    else miss "root-keygen.json is missing: the candidate's public anchor is unknown"; fi
    printf '%s\n' "$cfp" | grep -qE '^[0-9a-f]{64}$' || { cfp=UNKNOWN; miss "the candidate fingerprint could not be derived"; }
    printf '%s\n' "$cfp" > "$FC/candidate.publicKeySha256" || miss "cannot write candidate.publicKeySha256"
    ksha=$(sha256sum "$KEY" | cut -d' ' -f1)
    printf '%s\n' "$ksha" | grep -qE '^[0-9a-f]{64}$' && printf '%s\n' "$ksha" > "$FC/candidate-key-file.sha256" || miss "cannot capture the encrypted key file hash"
    printf 'FAILED_GENERATED_CANDIDATE\npublicKeySha256=%s\nstatus=PERMANENTLY_BURNED; NEVER K-ROOT; never regenerate, reuse, or reclassify\nutc=%s\n' "$cfp" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" > "$FC/FAILED_GENERATED_CANDIDATE" || miss "cannot write the burn marker"
  else miss "cannot create $FC: no burn record exists"; fi
  if test -e "$PUB"; then
    test -d "$FC" && mv "$PUB" "$FC/withdrawn-public" && builtin echo PUBLIC_COPY_WITHDRAWN || miss "an accepted-looking public copy REMAINS at $PUB (it is NOT K-ROOT)"
  fi
  if test -e "$X"; then
    test -d "$FC" && mv "$X" "$FC/withdrawn-export.tar" && builtin echo SUCCESS_FORMAT_EXPORT_WITHDRAWN || miss "a success-format export REMAINS at $X (it is NOT K-ROOT)"
  fi
  if test -e "$QK"; then miss "$QK already exists; the candidate stays at $KEY"
  else mv "$K" "$QK" && builtin echo "CANDIDATE_QUARANTINED (private, on this phone only)" || miss "quarantine failed; the candidate REMAINS at $KEY"; fi
  if test -d "$FC" && tar -cf "$FX" -C "$HOME" lilith-mb1-failed-candidate $(test -d "$E" && builtin echo lilith-mb1/evidence) \
     && ! tar -tf "$FX" | grep -q -e 'k-root\.der' -e 'lilith-kroot-dev-synthetic/' -e 'FAILED-CANDIDATE'; then
    fxsha=$(sha256sum "$FX" | cut -d' ' -f1)
    printf '%s\n' "$fxsha" | grep -qE '^[0-9a-f]{64}$' && builtin echo "PHONE_SIDE_FAILURE_EXPORT_SHA256 $fxsha" || miss "cannot hash the failure export"
  else miss "the failure export could not be built, or it names private material"; fi
  if [ "$ok" = 1 ]; then
    builtin echo "MB1_FAILED_GENERATED_CANDIDATE publicKeySha256=$cfp (PERMANENTLY BURNED; NEVER K-ROOT; custody complete)"
  else
    builtin echo "MB1_FAILURE_CUSTODY_INCOMPLETE: MANUAL CUSTODY RECOVERY REQUIRED. The candidate is NOT K-ROOT and is burned, but custody did not complete. Do not delete anything and do not rerun: report for review."
  fi
  builtin echo "MB1_INCIDENT: a candidate was generated. MANUAL, REVIEWED RECOVERY IS REQUIRED before any deletion or rerun."
  return 0
}
miss() { ok=0; builtin echo "FAILURE_CUSTODY_STEP_FAILED: $*"; }

# ---- G0 phone state (read-only) ----
cd "$HOME" || stop "cannot enter HOME"
priv "$HOME" && echo HOME_TERMUX_PRIVATE || stop "HOME is not Termux private storage"
priv "$TMP" && echo TMP_TERMUX_PRIVATE || stop "TMPDIR is not Termux private storage"
[ -z "${SSH_CONNECTION-}${SSH_CLIENT-}${SSH_TTY-}" ] && echo NOT_AN_SSH_SESSION || stop "SSH session: the passphrase must be typed on the S25 itself"
for c in /proc/[0-9]*/comm; do [ "$(cat "$c" 2>/dev/null)" = sshd ] && stop "sshd is running"; done
echo NO_SSHD_RUNNING
[ -t 0 ] && [ -r /dev/tty ] && [ -w /dev/tty ] && echo PHONE_TERMINAL_OK || stop "no interactive phone terminal"
python -c 'import sys; print("PYTHON", sys.version.split()[0])' || stop "python missing"
python -c 'import sys, cryptography as c; v = c.__version__; m = int(v.split(".")[0]); print("CRYPTOGRAPHY", v); sys.exit(0 if 2 <= m < 52 and m != 35 else 1)' && echo CRYPTOGRAPHY_OK || stop "cryptography missing or unsupported"
test ! -e "$W" && echo STAGING_ABSENT || stop "$W already exists"
test ! -e "$K" && echo KROOT_DIR_ABSENT || stop "$K already exists: a K-ROOT may already exist"
test ! -e "$PUB" && echo PUBLIC_DIR_ABSENT || stop "$PUB already exists"
test ! -e "$X" && echo EXPORT_ABSENT || stop "$X already exists"
test ! -e "$FC" && test ! -e "$QK" && test ! -e "$FX" && echo NO_FAILED_CANDIDATE_PENDING || stop "a failed generated candidate exists: it must be burned and disposed of by a reviewed step first"
ls -A "$TMP" | grep -q -e lilith-mb1 -e lilith-b4-kroot-rehearsal && stop "stale directory in TMPDIR" || echo TMP_NO_STALE
find "$HOME" \( -name 'k-root*' -o -name '*REHEARSAL-TEST*' \) 2>/dev/null | grep -q . && stop "a k-root or rehearsal key file already exists" || echo NO_KROOT_FILES_BEFORE
test -f "$R/REPLICA.json" && echo REPLICA_B_PRESENT || stop "Replica B missing"
test ! -e "$HOME/lilith-owner-freshness/owner-offline-dev-synthetic-01" && echo NESTED_REPLICA_ABSENT || stop "a second Replica B exists at the old nested path"
test -f "$DL/$TAR" && echo TRANSPORT_COPY_PRESENT || stop "bundle not in Download"

# ---- G1 Replica B baseline (read-only) ----
mkdir -m 700 "$W" "$E" || stop "cannot create $W"
{ echo "HOME_PRIVATE yes"; echo "TMP_PRIVATE yes"
  python -c 'import sys, platform, cryptography as c; print("PYTHON", sys.version.split()[0], "CRYPTOGRAPHY", c.__version__, "MACHINE", platform.machine())'; } > "$E/g0.txt" || stop "cannot write g0.txt"
snap > "$E/replica-b-before.txt" || stop "cannot write Replica B baseline"; cat "$E/replica-b-before.txt" || stop "cannot read Replica B baseline"
grep -qx "sha c068e5331ccd7fa0f69f2b38d25849497b86edea843598784235874080c107c4" "$E/replica-b-before.txt" && grep -qx "records 0" "$E/replica-b-before.txt" && grep -qE "^parent (.* )?lilith-owner-offline-dev-synthetic-01 " "$E/replica-b-before.txt" && echo REPLICA_B_BASELINE_OK || stop "Replica B is not the accepted empty replica"

# ---- T1 transport copy -> private staging, then verify ----
cp "$DL/$TAR" "$W/" || stop "transport copy missing or unreadable"
cd "$W" || stop "cannot enter $W"
echo "$TAR_SHA  $TAR" | sha256sum -c - || stop "bundle hash differs"
tar -xf "$TAR" || stop "cannot extract the bundle"
cd "$B" || stop "cannot enter the bundle"
echo "$SUMS_SHA  SHA256SUMS" | sha256sum -c - || stop "SHA256SUMS digest differs"
sha256sum -c --quiet SHA256SUMS && echo BUNDLE_VERIFIED || stop "SHA256SUMS verification failed"
test "$(cat SOURCE_COMMIT)" = "$SRC" && echo SOURCE_COMMIT_OK || stop "source commit differs"
test "$(find "$B" -type f | wc -l)" = "$NFILES" && echo FILE_COUNT_OK || stop "unexpected file count"
priv "$B" && echo BUNDLE_IN_TERMUX_PRIVATE || stop "bundle is not in Termux private storage"
cd "$HOME" || stop "cannot enter HOME"
export PYTHONPATH="$B/vendor:$B/services/core-api:$B/services/owner-memory-control"
export PYTHONDONTWRITEBYTECODE=1
TOOL="$B/services/authority-dev/ceremony/lilith_authority_owner_dev.py"

# ---- C0 last owner confirmation on the phone terminal ----
printf '\nAll pre-run gates passed. The next step creates the REAL K-ROOT on this phone.\nType GENERATE to continue: ' > /dev/tty
read -r answer < /dev/tty || stop "no confirmation"
[ "$answer" = GENERATE ] && echo OWNER_CONFIRMED_ON_PHONE || stop "owner did not confirm"

# ---- K1 the ONLY private write: root-keygen (the passphrase is asked twice by getpass on this terminal) ----
mkdir -m 700 "$K" || stop "cannot create $K"
KEYGEN_STARTED=1
python -B "$TOOL" root-keygen "$KEY" > "$E/root-keygen.json" 2> "$E/root-keygen.stderr"
rc=$?
echo "exit=$rc" | tee "$E/root-keygen.exit" || stop "cannot write root-keygen.exit"
test "$rc" -eq 0 || stop "root-keygen refused or failed ($rc); see root-keygen.stderr; do NOT record any fingerprint"

# ---- K2 key and anchor checks (nothing secret is printed) ----
test -f "$KEY" && ! test -L "$KEY" && echo KEY_FILE_REGULAR || stop "key file missing or not regular"
test "$(stat -c %a "$KEY")" = 600 && echo KEY_FILE_0600 || stop "key file mode is not 0600"
test "$(stat -c %a "$K")" = 700 && echo KROOT_DIR_0700 || stop "key directory mode is not 0700"
test "$(ls -A "$K")" = k-root.der && echo KEY_FILE_ONLY_ENTRY || stop "unexpected entry beside the key"
test -f "$E/root-keygen.stderr" && ! test -s "$E/root-keygen.stderr" && echo KEYGEN_STDERR_EMPTY || stop "root-keygen wrote to stderr"
python -B -c "$ANCHOR_CHECK" "$E/root-keygen.json" > "$E/anchor-check.txt" || stop "root-keygen output is not a valid K-ROOT anchor"
grep -qx ANCHOR_VALID "$E/anchor-check.txt" && echo ANCHOR_VALID || stop "cannot read anchor-check.txt"   # the fingerprint is shown only at the end
FP=$(sed -n 's/^FINGERPRINT \([0-9a-f]\{64\}\)$/\1/p' "$E/anchor-check.txt")
test "${#FP}" = 64 || stop "no fingerprint"
python -B -c "$BURNED_CHECK" "$FP" > "$E/burned-check.txt" || stop "the real K-ROOT equals a burned identity: do NOT record or use it"
cat "$E/burned-check.txt" || stop "cannot read burned-check.txt"
python -B -c "$AT_REST_CHECK" "$KEY" > "$E/at-rest-check.txt" || stop "key file is not encrypted at rest"
cat "$E/at-rest-check.txt" || stop "cannot read at-rest-check.txt"
python -B -c "$UNLOCK_CHECK" "$KEY" "$E/root-keygen.json" "$TOOL" > "$E/unlock-check.txt" || stop "the passphrase does not unlock the key, or the key does not match the anchor"
cat "$E/unlock-check.txt" || stop "cannot read unlock-check.txt"

# ---- V verification (read-only) ----
ls -A "$TMP" | grep -q -e lilith-mb1 -e lilith-b4-kroot-rehearsal && stop "stale directory in TMPDIR"; vpass TMP_CLEAN
find "$HOME" \( -name 'k-root*' -o -name '*REHEARSAL-TEST*' \) ! -path "$KEY" 2>/dev/null | grep -q . && stop "a key file exists outside $KEY"; vpass NO_OTHER_KEY_FILE
find "$DL/" \( -name 'k-root*' -o -name '*.der' \) 2>/dev/null | grep -q . && stop "a key-like file is in shared Download"; vpass NO_KEY_IN_SHARED_STORAGE
for f in "$E"/*; do cmp -s "$f" "$KEY" && stop "evidence file $f equals the private key"; done; vpass EVIDENCE_HOLDS_NO_KEY
test "$(find "$B" -type f | wc -l)" = "$NFILES" && (cd "$B" && sha256sum -c --quiet SHA256SUMS) || stop "unexpected file in bundle"; vpass BUNDLE_UNCHANGED
snap > "$E/replica-b-after.txt" || stop "cannot write Replica B post-run snapshot"
cmp "$E/replica-b-before.txt" "$E/replica-b-after.txt" || stop "Replica B changed"; vpass REPLICA_B_UNCHANGED

# ---- P authoritative S25 public copy (E-21): the anchor and the fingerprint only ----
mkdir -m 700 "$PUB" || stop "cannot create $PUB"
cp "$E/root-keygen.json" "$PUB/k-root-anchor.json" || stop "cannot write the public anchor copy"
echo "$FP" > "$PUB/k-root.publicKeySha256" || stop "cannot write the fingerprint copy"
for f in "$PUB"/*; do cmp -s "$f" "$KEY" && stop "public file $f equals the private key"; done
test "$(ls -A "$PUB" | LC_ALL=C sort | tr '\n' ' ')" = "k-root-anchor.json k-root.publicKeySha256 " && echo PUBLIC_COPY_WRITTEN || stop "unexpected public copy"

# ---- S seal the evidence ----
sha256sum "$E"/* > "$W/evidence.sha256" || stop "cannot write evidence.sha256"; cat "$W/evidence.sha256" || stop "cannot read evidence.sha256"
sha256sum -c --quiet "$W/evidence.sha256" || stop "evidence.sha256 does not verify"

# ---- X public-only export for the laptop (explicit allowlist; the key directory is never named) ----
tar -cf "$X" -C "$HOME" lilith-mb1/evidence lilith-mb1/evidence.sha256 lilith-kroot-dev-synthetic-public || stop "cannot build the export"
tar -tf "$X" | grep -q -e 'lilith-kroot-dev-synthetic/' -e 'k-root\.der' -e '\.tar$' && stop "export names private key material"
test "$(tar -tf "$X" | grep -v '/$' | LC_ALL=C sort | tr '\n' ' ')" = "lilith-kroot-dev-synthetic-public/k-root-anchor.json lilith-kroot-dev-synthetic-public/k-root.publicKeySha256 lilith-mb1/evidence.sha256 lilith-mb1/evidence/anchor-check.txt lilith-mb1/evidence/at-rest-check.txt lilith-mb1/evidence/burned-check.txt lilith-mb1/evidence/g0.txt lilith-mb1/evidence/replica-b-after.txt lilith-mb1/evidence/replica-b-before.txt lilith-mb1/evidence/root-keygen.exit lilith-mb1/evidence/root-keygen.json lilith-mb1/evidence/root-keygen.stderr lilith-mb1/evidence/unlock-check.txt lilith-mb1/evidence/verify.txt " && echo EXPORT_PUBLIC_ONLY || stop "export is not exactly the public allowlist"

# ---- cleanup of the transport copy only (after every line above passed) ----
test -f "$DL/$TAR" || stop "transport copy missing in Download"
test -f "$W/$TAR" || stop "staged tar missing"
cmp "$DL/$TAR" "$W/$TAR" || stop "transport copy differs from the staged tar"
rm "$DL/$TAR" || stop "cannot remove the transport copy"
test ! -e "$DL/$TAR" || stop "transport copy still present"
echo TRANSPORT_COPY_REMOVED

# ---- result: record the fingerprint now (E-21) ----
echo "PHONE_SIDE_EXPORT_SHA256 $(sha256sum "$X" | cut -d' ' -f1)"
KEYGEN_STARTED=0                                        # accepted: every gate passed; no STOP path remains
echo "MB1_KROOT_FINGERPRINT publicKeySha256=$FP"
echo MB1_KROOT_GENERATED
# Write the fingerprint down now; the authoritative copy is in $PUB. Copy ONLY $X (and the transcript) to Download.
# ============================== end of M-B1 ==============================
```

## 4. Operator-flow preconditions (replacing the provisional ones)

The source-and-design record §3 still governs the flow. Its precondition 1
now reads:

1. **this record reviewed and merged.** On the laptop:
   - `git merge-base --is-ancestor 1e2eae30fb7023a44776d1f8d25e2bb958955e6a origin/main`
     must hold;
   - the 17 bundled source files must equal `origin/main`'s;
   - the staged tar and script must hash to the §1 values.

Preconditions 2–5 are unchanged: the `cfa0b3e` DEV deploy boundary review,
a fresh PR-2 revalidation, `PR1B_ELIGIBLE`, and the owner's separate M-B1
go statement naming the §1 hashes.

## 5. Validation

- `test_b1b3e_mb1_finalization.py`:
  - the record pins equal the block;
  - the block is the six-line derivation of the merged v3 block;
  - the merged v3 block itself is still `a63bf5aa…`;
  - with git available, the source commit is an ancestor of `HEAD`, and the
    17 bundled source files are unchanged since it;
  - a fake-vendor build at the source commit has `SOURCE_COMMIT` equal to
    it, and source members equal to `git show`;
  - the burned set is the canonical 20.
- In a git checkout, the 7 finalization tests pass (all 7 ran).
- **The full owner-memory-control suite (WSL, Python 3.12, pinned deps):
  722 OK, 4 skipped.** That is 715 plus the 7 new tests. The run used a
  `git archive` copy with no `.git`, so the 4 skips are git-dependent: the
  2 known ones, plus the 2 finalization git tests above.
- `scripts/validate_repository.py` passes, and `git diff --check` is clean.

## 6. What this record does not do

- It does not authorize M-B1, and it issues no M-B1 command.
- It does not change the builder, the bundled source, the vendor set, the
  burned set, or any gate or custody step.
- It does not contact the S25, Replica A, Replica B, or DEV.
- It creates no K-ROOT, K-WIT, registry v1, genesis pin, or record 1.

## 7. State

```text
MB1_FINAL_PACKAGE_PINNED_READY_FOR_REVIEW
CONDITION 1 NOT YET CLOSED (closes as MB1_PACKAGE_REVIEWED_AND_MERGED when this record merges)
M-B1 NOT AUTHORIZED
NO M-B1 COMMAND ISSUED
NO REAL K-ROOT
NO K-WIT
NO REGISTRY V1
NO GENESIS PIN
NO REAL RECORD 1
NO PHONE / REPLICA B CONTACT
FRESHNESS=UNKNOWN
FIRST MEMORY NOT AUTHORIZED
```
