# Slice 15B2b-B1b-3e — M-B1: Real K-ROOT Ceremony Package (S25 Termux)

Status:

- **`MB1_SOURCE_AND_DESIGN_READY_TO_LAND`.** This record lands the reviewed
  **source and design**. **It is NOT the final runnable package.** The
  bundle and script pins below are **provisional design pins**: bundle from
  `3ec71c1`, script v3.
  - After merge, the real bundle is rebuilt from the merged `main` SHA, so
    `SOURCE_COMMIT` equals that SHA.
  - The final pins go in a separate finalization record.
  - **Condition 1 stays NOT CLOSED** until that finalization record is
    reviewed and merged.
- The canonical burned set is now **20**
  ([expansion record](slice-15b2b-b1b3e-burned-identities-expansion.md) §3). A
  failing v2 pty test printed one candidate.
- History: **`MB1_PACKAGE_REVISED_READY_FOR_REVIEW`** (v2). The package is prepared.
  **It is not reviewed yet, M-B1 is NOT AUTHORIZED, and M-B1 has not been
  executed.**
- It satisfies only condition 1 of the owner's
  [B-5 grant](slice-15b2b-b1b3e-b5-pr1b-authorization-granted.md) §2 (the
  bundle and operator script are prepared), and only once reviewed.
  Conditions 2–5 are untouched.
- There was no phone contact, no DEV contact, no K-ROOT, and no Replica B
  contact. The simulation (§9) ran only in WSL, with a throwaway TEST
  passphrase.

```text
package prepared != package reviewed != M-B1 authorized != M-B1 executed
```

> **Revision v2 (2026-09-30, before any review or execution).** The v1
> package (bundle `a42083c6…eb24` from `c694061`, script `c2efe0fd…fba5`,
> commit `1b17a25`) is **superseded and must not be used**. The review found
> two issues:
>
> 1. **The burned set was incomplete.** Seven real-format TEST identities
>    had been printed in full and declared burned, but were not enforced:
>    six from the B-4 path-correction simulation, and v1's own simulation
>    candidate `ae5d8275…`. The
>    [expansion record](slice-15b2b-b1b3e-burned-identities-expansion.md)
>    makes the canonical set **19**. `burned_identities.py` changed, so the
>    bundle was rebuilt from that commit (`ce5e10d`).
> 2. **A STOP after generation could leave an untracked candidate:**
>    - the key in place;
>    - its fingerprint only in staging;
>    - no burn record or export;
>    - a public copy that looked accepted, and no signal handling.
>
>    v2 adds failed-candidate custody (§6).

| Stage | Meaning | State |
| --- | --- | --- |
| **package prepared** | the bundle is built deterministically from merged `main`; the operator script, record, and tests exist | **YES** (this record) |
| **package reviewed** | an owner / reviewer accepts this record, and the branch is merged | no |
| **M-B1 authorized** | all five B-5 grant conditions are met, including the owner's separate M-B1 go statement naming the script and bundle SHA-256 below | no |
| **M-B1 executed** | the script ran on the S25 with `RUN_EXIT=0`, and its evidence is reviewed | no |

## 1. Identities

| Item | Value |
| --- | --- |
| source commit | `3ec71c176963a26b1b7d14333130bd7aebd2d555`: the burned-set expansion (20), on this branch, child of merged `main` `c694061`. It is `SOURCE_COMMIT` in the bundle. At run time it must be an ancestor of merged `main`, with the 17 bundled source files unchanged there (§3) |
| bundle | `lilith-mb1-kroot-3ec71c1.tar` |
| **bundle SHA-256** | `08cfe650024c1440c0fc56ebef226ad936d728bf3141e33d8e98aa361cb8ec78` |
| `SHA256SUMS` (inside the bundle) | `44e453acd0209177cc964a741447c2701345628e73c87d11884cf20edbb7a619` |
| files | **74**: 17 source files + 55 vendor files + `SOURCE_COMMIT` + `SHA256SUMS` |
| top directory | `lilith-mb1-kroot-3ec71c1/` |
| **operator script** | `mb1_phone_commands.sh`, **SHA-256 `a63bf5aa97d6a098923afc52fb9f71ebc0939c8526de28a1afb4271c4a84599e`**; exactly the §4 block |
| builder | `services/owner-memory-control/tools/build_mb1_kroot_bundle.py` (this change) |
| determinism | two independent builds are byte-identical |
| laptop staging | `%USERPROFILE%\lilith-mb1-package\` (outside every Git tree): the v2 tar, the operator script, and `STAGING.sha256`. v1 is under `superseded/` |

**Contents.**

- The 16-file import closure of
  `services/authority-dev/ceremony/lilith_authority_owner_dev.py`, computed
  and pinned by a test.
- `lilith_owner_memory/burned_identities.py`, with the canonical **20**
  (`CANONICAL_COUNT = 20`).
- The 55 vendor files (`fido2` 2.2.1, `rfc8785` 0.1.4). They are
  byte-identical to the verified B-4 bundle `659c50a4…`, whose own
  `SHA256SUMS` was re-verified before copying.
- `SOURCE_COMMIT` and `SHA256SUMS`.

**What it does not contain:**

- the rehearsal script;
- a key, a passphrase, or any `.der` / `.pem` / `.cred` file;
- any real authority material.

The builder refuses a member whose name suggests key material.
`cryptography` is native and preinstalled in Termux (50.0.1 observed in
B-4).

**What is run from it:** only `root-keygen`. The script never invokes
`registry-v1`, `witness-anchor`, `reproduce`, `package-digest`, or the
K-WIT key-generation tool (`lilith_authority_keygen_dev.py` is not in the
bundle). This is test-enforced.

## 2. Paths on the S25

| Path | Role | Written by |
| --- | --- | --- |
| `~/lilith-kroot-dev-synthetic/k-root.der` | **the only private K-ROOT material** (encrypted PKCS#8, `0600`, in a `0700` dir that must hold nothing else) | `root-keygen` only (`O_EXCL`, `O_NOFOLLOW`) |
| `~/lilith-kroot-dev-synthetic-public/` | the **authoritative S25 copy** of the public anchor and `publicKeySha256` (B-4 decision §2, E-21) | the script, public only |
| `~/lilith-mb1/` | staging: the bundle and public evidence | the script |
| `~/lilith-mb1-export.tar` | the **public-only** export for the laptop | the script |
| `~/lilith-mb1.transcript.txt` | the stdout / stderr transcript (public) | `tee` |
| `~/lilith-owner-offline-dev-synthetic-01` | Replica B: **read only** (snapshot before and after) | nothing |
| `~/lilith-mb1-failed-candidate/` | **only after a post-generation STOP:** the public burn record of a `FAILED_GENERATED_CANDIDATE` | `fail_custody()` |
| `~/lilith-kroot-dev-synthetic.FAILED-CANDIDATE/` | **only after a post-generation STOP:** the quarantined private candidate. It stays on the S25, and is never K-ROOT | `fail_custody()` (`mv` of the key directory) |
| `~/lilith-mb1-failed-candidate-export.tar` | **only after a post-generation STOP:** the public-only failure export | `fail_custody()` |

## 3. Operator flow

**Preconditions** (none of them is met yet):

1. this package reviewed and merged. On the laptop, `git merge-base
   --is-ancestor 3ec71c1 origin/main` must hold, and the 17 bundled source files
   must equal `origin/main`'s;
2. the `cfa0b3e` DEV deployment boundary results reviewed and accepted;
3. a fresh PR-2 revalidation PASS immediately before eligibility;
4. `CHECK_ELIGIBILITY` returns `PR1B_ELIGIBLE`;
5. **the owner's separate M-B1 go statement**, naming the script and
   bundle SHA-256 above.

**Transport** (laptop to phone, public files only):

1. Verify both SHA-256 values on the laptop.
2. Copy the tar and `mb1_phone_commands.sh` by MTP into the phone's
   Download folder.
3. Unplug USB, and turn airplane mode **ON**.

**Run on the S25**, in a local Termux session (never SSH):

1. `sha256sum "$HOME/storage/downloads/mb1_phone_commands.sh"` must equal
   the operator-script SHA-256 above.
2. Run the one command line in the script header. It captures the
   transcript and `RUN_EXIT`.
3. At the phone prompt, type **`GENERATE`**.
4. Type the passphrase twice (`root-keygen`), then once more for the unlock
   check. It is typed only into the phone.
5. On `RUN_EXIT=0`, write down the fingerprint (`MB1_KROOT_FINGERPRINT`).
   That is the E-21 owner record. The authoritative copy is also in
   `~/lilith-kroot-dev-synthetic-public/`.
6. Confirm by eye that the fingerprint is none of the **20** burned
   identities. The script has already refused them mechanically.

**Export:**

1. Write down the `PHONE_SIDE_EXPORT_SHA256` line.
2. Copy **only** `~/lilith-mb1-export.tar` and `~/lilith-mb1.transcript.txt`
   into Download.
3. Transfer them by MTP.

**Never** copy `~/lilith-kroot-dev-synthetic/`.

## 4. Operator script

`mb1_phone_commands.sh` (SHA-256 `a63bf5aa97d6a098923afc52fb9f71ebc0939c8526de28a1afb4271c4a84599e`) is exactly this block:

```bash
# ===== M-B1: real K-ROOT generation (DEV_SYNTHETIC), S25 Termux ONLY (bundle lilith-mb1-kroot-3ec71c1) =====
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
TAR=lilith-mb1-kroot-3ec71c1.tar
TAR_SHA=08cfe650024c1440c0fc56ebef226ad936d728bf3141e33d8e98aa361cb8ec78
SUMS_SHA=44e453acd0209177cc964a741447c2701345628e73c87d11884cf20edbb7a619
SRC=3ec71c176963a26b1b7d14333130bd7aebd2d555
NFILES=74
DL="$HOME/storage/downloads"
W="$HOME/lilith-mb1"                                   # staging and PUBLIC evidence
E="$W/evidence"
B="$W/lilith-mb1-kroot-3ec71c1"
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

## 5. Gates and hard STOP conditions

**Every STOP is `stop()`:** it prints `STOP: …` on stderr, which the
transcript captures, and exits 1 at top level.

- No gate runs inside a pipeline or a subshell whose exit could be
  swallowed.
- There is no `echo()` redefinition.
- `INT`, `TERM`, and `HUP` are trapped into `stop`.
- `SIGPIPE` is ignored, so a dead `tee` cannot kill the custody step.

**Once `root-keygen` has started, every STOP first runs failed-candidate
custody (§6).**

**Pre-run (G0 / G1 / T1).** Any failure stops **before any write**:

- `HOME` or TMPDIR is not Termux private storage;
- an SSH session (`SSH_CONNECTION` / `SSH_CLIENT` / `SSH_TTY`), or `sshd`
  running;
- no interactive phone terminal (`-t 0`, `/dev/tty`);
- Python or `cryptography` missing or unsupported;
- `~/lilith-mb1`, `~/lilith-kroot-dev-synthetic`,
  `~/lilith-kroot-dev-synthetic-public`, or the export already exists
  (rerun safety);
- **a pending failed candidate** (`~/lilith-mb1-failed-candidate`, the
  quarantine directory, or the failure export);
- a stale TMPDIR directory;
- **any existing `k-root*` or `*REHEARSAL-TEST*` file** under `$HOME`,
  including a quarantined candidate;
- Replica B missing, not the accepted empty replica (`c068e533…`, 0
  records, `parent` line), or a nested Replica B;
- the bundle is not in Download, or its tar hash, `SHA256SUMS` digest,
  source commit, 74-file count, or `sha256sum -c` differs;
- the bundle is not in private storage;
- the owner does not type `GENERATE` on the phone terminal.

**Generation and checks (K1 / K2):**

- `root-keygen` exits non-zero;
- the key file is not regular, not `0600`, or not the only entry in a `0700`
  dir;
- `root-keygen` wrote to stderr;
- the output is not exactly `{registryRoot, publicKeySha256}`: a valid
  `TrustedRegistryRootV1`, the expected root key ID, `dev`, and a fingerprint
  equal to the SHA-256 of the raw key;
- **the fingerprint equals any of the 20 canonical burned identities**
  (`len(every) == CANONICAL_COUNT == 20` is itself asserted);
- the key loads without a passphrase;
- the passphrase does not unlock it, or the unlocked key does not match the
  anchor.

**Verification (V):**

- TMPDIR is not clean;
- any key file exists outside `$KEY`;
- a key-like file is in shared Download;
- any evidence file equals the key;
- the bundle changed;
- **Replica B changed**.

**Public copy and export (P / S / X):**

- the public copy is not exactly the anchor and the fingerprint;
- the seal does not verify;
- the export names the key directory, `k-root.der`, or a tar, or is not
  **exactly** the 14-file public allowlist.

**Cleanup.** The transport copy is removed only after everything above,
with explicit existence, `cmp`, `rm`, and absence checks.

**Acceptance requires `RUN_EXIT=0`, zero transcript lines beginning
`STOP`, and `MB1_KROOT_GENERATED` as the last token before `RUN_EXIT`.**

## 6. Failed-candidate custody (every STOP after generation)

**States.**

| State | Meaning | Marker |
| --- | --- | --- |
| **successful M-B1** | every gate passed. `KEYGEN_STARTED` is cleared **only then**, immediately before the success lines | `MB1_KROOT_FINGERPRINT` and `MB1_KROOT_GENERATED`, then `RUN_EXIT=0` |
| **`FAILED_GENERATED_CANDIDATE`** | a key file was written, and a STOP or signal followed | `MB1_FAILED_GENERATED_CANDIDATE publicKeySha256=<fp> (PERMANENTLY BURNED; NEVER K-ROOT)`, then `RUN_EXIT=1`. **`MB1_KROOT_GENERATED` is never printed** |
| **no candidate** | STOP before or during `root-keygen`, with no key file written (a passphrase mismatch or too short) | `NO_CANDIDATE_GENERATED`; nothing to burn |

**`fail_custody()`.** It runs inside `stop()`, once. It never calls `stop()`
and never exits, so it cannot recurse or be cut short by a gate. It never
deletes anything, and it contacts nothing. In order:

1. **Burn record:** it creates `~/lilith-mb1-failed-candidate/` (`0700`),
   public only, holding:
   - `FAILED_GENERATED_CANDIDATE`: the fingerprint, `PERMANENTLY_BURNED`,
     "never K-ROOT; never regenerate, reuse, or reclassify", and the UTC
     time;
   - `candidate.publicKeySha256`: the fingerprint, from `root-keygen.json`.
     It is `UNKNOWN` only if that file is missing or damaged; the ciphertext
     hash then still identifies the file;
   - `candidate-anchor.json`: the public anchor;
   - `candidate-key-file.sha256`: the SHA-256 of the **encrypted** key
     file, which identifies the quarantined file and reveals nothing;
   - `reason.txt`: the STOP message.
2. **Withdraw anything that looks accepted:** the public copy moves to
   `withdrawn-public/`, and a success-format export, if already built, moves
   to `withdrawn-export.tar`, both inside the burn record.
3. **Quarantine:** the key directory is renamed
   `~/lilith-kroot-dev-synthetic.FAILED-CANDIDATE/`. It stays in Termux
   private storage on the S25, is never read again, and no path treats it
   as K-ROOT.
4. **Failure export:** `~/lilith-mb1-failed-candidate-export.tar` holds the
   burn record and the public evidence. It is refused if any member names
   `k-root.der`, the key directory, or the quarantine directory. It prints
   `PHONE_SIDE_FAILURE_EXPORT_SHA256`.

**Why the candidate can never become K-ROOT:**

- There is no success marker, public copy, or success export.
- A rerun stops in G0, on the burn record, the quarantine directory, and
  the quarantined `k-root.der` (`NO_KROOT_FILES_BEFORE`), until a reviewed
  disposal.
- The burned fingerprint joins `burned_identities.py` through a reviewed
  change. Every later bundle then refuses it mechanically.

**Reviewed recovery** (not scripted, and not authorized here):

1. Transfer the failure export and transcript (phone-side hash), and review
   them.
2. A reviewed change adds the candidate fingerprint to
   `burned_identities.py`, which raises `CANONICAL_COUNT`. The bundle is
   rebuilt and the script re-pinned.
3. A separately reviewed phone disposal step deletes the quarantined key
   file, and archives or removes `~/lilith-mb1/` and the burn record.
4. A fresh owner M-B1 go statement is given for a new candidate.

**Replica B and freshness are never touched** by custody.

**Custody self-failure (v3).** `fail_custody()` never claims more than it
achieved:

- Every step is checked:
  - the burn-directory creation;
  - each burn-record write;
  - the anchor copy;
  - the fingerprint derivation (it must be 64-hex, otherwise `UNKNOWN`);
  - the encrypted-key hash (64-hex);
  - both withdrawals;
  - the quarantine rename;
  - the failure-export build, its private-name check, and its hash.
- Any failure prints `FAILURE_CUSTODY_STEP_FAILED: <what>`, and ends with
  **`MB1_FAILURE_CUSTODY_INCOMPLETE: MANUAL CUSTODY RECOVERY REQUIRED`**.
  Only a fully successful custody prints `… custody complete)`.
- Both outcomes end with `MB1_INCIDENT: … MANUAL, REVIEWED RECOVERY IS
  REQUIRED before any deletion or rerun`.
- **Nothing is ever deleted**, and the candidate stays where it is: at
  `$KEY` if the quarantine failed. A withdrawal that fails leaves the
  accepted-looking file in place and names it.
- Custody ignores `INT` / `TERM` / `HUP` once it starts, so a second
  signal cannot cut it short.
- The main trap is armed at the top of the script, before
  `KEYGEN_STARTED=1` and `root-keygen` (test-enforced).
- If generation was attempted but no key file exists (for example Ctrl-C at
  the passphrase prompt), the state is `NO_CANDIDATE_GENERATED`. It still
  prints `MB1_INCIDENT`, and the staging directory remains.
- **No rerun is possible from any incident state:** G0 refuses the staging
  directory, the key, public, or quarantine directories, the burn record,
  either export, and any `k-root*` file. Power loss or `SIGKILL` (no trap
  possible) leaves the same blocking state.

Each of the ten custody steps is forced to fail in turn by the pty tests
(§9), which then prove:

- `INCOMPLETE` plus `MB1_INCIDENT`;
- no `custody complete`;
- no `MB1_KROOT_GENERATED`;
- exactly one `k-root.der` still under `$HOME`;
- the named leftover still present;
- a blocked rerun.

## 7. Custody proofs

**No K-ROOT private material can be copied to the laptop by this package.**

- The script has no network, MTP, `adb`, `ssh`, `scp`, `curl`, or `nc`
  command (test-enforced). The phone is in airplane mode.
- `$KEY` is used only as the `root-keygen` output path, in read-only
  checks, and in the ciphertext hash of the burn record. It never appears
  in `cp`, `tar`, `cat`, or `echo`. The only `mv` commands are the custody
  withdrawals and the quarantine, all inside `$HOME` (test-enforced).
- **Both exports are built from explicit lists that never name the key or
  quarantine directory**, and both are checked after building:
  - the success export must be exactly the 14-file public allowlist;
  - the failure export must name no `k-root.der`, key directory, or
    quarantine directory.
- Every evidence and public file is `cmp`-compared against the key.
- The transcript holds only public output.
- **Simulation:** the key bytes appear in neither export nor the
  transcript, in every case.

**The passphrase is entered only on the S25.**

- It is read only by `getpass`, from the controlling terminal: twice by
  `root-keygen`, once by the unlock check.
- There is no passphrase argument, environment variable, file, or `read`
  (the `read` reads only `GENERATE`).
- SSH sessions and a running `sshd` are refused, and a local terminal is
  required.
- Airplane mode and the absence of remote-input tools are owner
  attestations.

**No other authority action.** No K-WIT, registry v1, genesis pin, record 1,
service, activation, DEV, PROD, or First Memory action is possible from the
script (test-enforced).

## 8. Evidence outputs

**Success export** (the 14-file public allowlist):

- `evidence/`:
  - `g0.txt`;
  - `replica-b-before.txt`, `replica-b-after.txt`;
  - `root-keygen.json`, `root-keygen.exit`, `root-keygen.stderr`;
  - `anchor-check.txt`, `burned-check.txt`, `at-rest-check.txt`,
    `unlock-check.txt`;
  - `verify.txt`;
- `evidence.sha256`;
- the public anchor and fingerprint copy.

Also public: the transcript and `PHONE_SIDE_EXPORT_SHA256`.

**Failure export:** the burn record (§6) and the public evidence, plus
`PHONE_SIDE_FAILURE_EXPORT_SHA256`.

**Allowed on the laptop:** only these exports, the transcript, and their
hashes. **Never on the laptop:** `k-root.der`, the key or quarantine
directory, or the passphrase.

## 9. Validation

**Tests** (`test_b1b3e_mb1_kroot_package.py`, and the B-3 module for the
set of 20):

- **Builder:** the closure, determinism, exactness, and refusals.
- **Pins:** the recorded script digest, the bundle pins, and source commit
  `3ec71c1`.
- **Structure:**
  - the STOP discipline, and the traps;
  - only `root-keygen`;
  - the passphrase channel;
  - `$KEY` usage;
  - the only `mv` commands are custody's;
  - neither export names private directories;
  - Replica B is read only.
- **Embedded checks:**
  - the anchor check;
  - the burned-identity check, which refuses each of the 20 and asserts the
    count;
  - the at-rest check.
- **Real-pty runs of the pinned script:**
  - a clean run;
  - a passphrase mismatch (no candidate);
  - a wrong unlock passphrase (`FAILED_GENERATED_CANDIDATE`: the burn record
    equals the candidate, the key is quarantined, no public copy, no
    success marker, the failure export has no key);
  - a rerun after a failure (G0 STOP);
  - **custody self-failure**: each of burn-directory creation, burn-record
    write, anchor copy, fingerprint derivation, encrypted-key hash, public
    copy withdrawal, success-export withdrawal, quarantine, failure-export
    build, and failure-export hash is forced to fail by a command shim.
    Each gives `INCOMPLETE`, the candidate never deleted, no success, and a
    blocked rerun;
  - Ctrl-C during `root-keygen` (no candidate; an incident; a blocked
    rerun);
  - SSH, `sshd`, and an owner decline.

**Full-fidelity WSL simulation** of the real bundle `08cfe650…` and the real
`root-keygen` under a pty. Every generated identity is **redacted**, and
destroyed with the simulated home.

| Case | `RUN_EXIT` | Result |
| --- | --- | --- |
| clean | 0 | every token; key `0600`; export is the 14-file allowlist; no key bytes in the export or transcript; no passphrase in the transcript; Replica B unchanged; transport copy removed |
| passphrase mismatch / too short | 1 | no key file; no candidate |
| owner declines | 1 | STOP before the key directory |
| wrong unlock passphrase | 1 | `FAILED_GENERATED_CANDIDATE`: the burn record equals the candidate; quarantined; no key or public directory; failure export public only; the marker says burned |
| rerun after that failure | 1 | G0 STOP; no generation |
| **Ctrl-C at the unlock prompt** | 1 | the same custody state on disk. The transcript loses its tail (`tee` is also interrupted), so the on-disk burn record is authoritative |
| Replica B touched mid-run | 1 | `STOP: Replica B changed`, then custody |
| **failure after the public copy and export** (transport copy removed mid-run) | 1 | custody **withdraws both** into the burn record |
| SSH / existing key dir / stale `k-root` / nested Replica B / bad bundle | 1 | STOP before any write |

## 10. Burned identities

The canonical, mechanically enforced set is **20**
([expansion record](slice-15b2b-b1b3e-burned-identities-expansion.md)):

- the 12 phone-rehearsal identities;
- the 6 B-4 path-correction simulation identities;
- the v1 M-B1 simulation candidate `ae5d8275…`;
- the M-B1 v2 pty-test candidate `d1719045…` (printed by a failing test).

**No real identity may match any of them.** v2's simulation identities
were redacted and destroyed (the unrecorded ephemeral class).

## 11. State

```text
MB1_SOURCE_AND_DESIGN_READY_TO_LAND
CONDITION 1 NOT YET CLOSED
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
