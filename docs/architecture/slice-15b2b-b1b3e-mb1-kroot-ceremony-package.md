# Slice 15B2b-B1b-3e — M-B1: Real K-ROOT Ceremony Package (S25 Termux)

Status:

- **`MB1_PACKAGE_PREPARED_READY_FOR_REVIEW`**. The package is prepared.
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

| Stage | Meaning | State |
| --- | --- | --- |
| **package prepared** | the bundle is built deterministically from merged `main`; the operator script, record, and tests exist | **YES** (this record) |
| **package reviewed** | an owner / reviewer accepts this record, and the branch is merged | no |
| **M-B1 authorized** | all five B-5 grant conditions are met, including the owner's separate M-B1 go statement naming the script and bundle SHA-256 below | no |
| **M-B1 executed** | the script ran on the S25 with `RUN_EXIT=0`, and its evidence is reviewed | no |

## 1. Identities

| Item | Value |
| --- | --- |
| source commit (merged `main`) | `c6940615875fd13df1636d7c105ad5b65c39d112` (`SOURCE_COMMIT` in the bundle) |
| bundle | `lilith-mb1-kroot-c694061.tar`, 1 413 120 bytes |
| **bundle SHA-256** | `a42083c6ea85300ffbf550e2e6e09a9822c9b69b236f0c69c1f53ef218b9eb24` |
| `SHA256SUMS` (inside the bundle) | `92880077323536c8f756f5384ce83dffd11533cb05b990f30df3f20e5b564739` |
| files | **74**: 17 source files + 55 vendor files + `SOURCE_COMMIT` + `SHA256SUMS` |
| top directory | `lilith-mb1-kroot-c694061/` |
| **operator script** | `mb1_phone_commands.sh`, 14 799 bytes, **SHA-256 `c2efe0fd9bcaaebb47f5e57b4ef8fce862265af0ced67b9130055ad0a1fefba5`**; exactly the §4 block |
| builder | `services/owner-memory-control/tools/build_mb1_kroot_bundle.py` (this change) |
| determinism | two independent builds are byte-identical |
| laptop staging | `%USERPROFILE%\lilith-mb1-package\` (outside every Git tree): the tar and the operator script |

**Contents.**

- The 16-file import closure of
  `services/authority-dev/ceremony/lilith_authority_owner_dev.py`, computed
  and pinned by a test.
- `lilith_owner_memory/burned_identities.py`.
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

## 3. Operator flow

**Preconditions** (none of them is met yet):

1. this package reviewed and merged;
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
6. Confirm by eye that the fingerprint is none of the 12 burned identities.
   The script has already refused them mechanically.

**Export:**

1. Write down the `PHONE_SIDE_EXPORT_SHA256` line.
2. Copy **only** `~/lilith-mb1-export.tar` and `~/lilith-mb1.transcript.txt`
   into Download.
3. Transfer them by MTP.

**Never** copy `~/lilith-kroot-dev-synthetic/`.

## 4. Operator script

`mb1_phone_commands.sh` (SHA-256 `c2efe0fd9bcaaebb47f5e57b4ef8fce862265af0ced67b9130055ad0a1fefba5`) is exactly this block:

```bash
# ===== M-B1: real K-ROOT generation (DEV_SYNTHETIC), S25 Termux ONLY (bundle lilith-mb1-kroot-c694061) =====
# Run ONLY after the owner's separate, explicit M-B1 go statement; ONLY on the S25; ONLY as a file; in a LOCAL
# Termux session (never SSH); with airplane mode ON and USB unplugged BEFORE starting:
#   bash "$HOME/storage/downloads/mb1_phone_commands.sh" 2>&1 | tee "$HOME/lilith-mb1.transcript.txt"; echo "RUN_EXIT=${PIPESTATUS[0]}" | tee -a "$HOME/lilith-mb1.transcript.txt"
# The ONLY private write is $KEY (root-keygen: O_EXCL, O_NOFOLLOW, 0600). The passphrase is typed ONLY into this
# phone's terminal (getpass on /dev/tty); it is never an argument, a variable, or a file. Only public files leave.
# stop() is the only STOP path: it prints "STOP: ..." on stderr and exits 1. After a STOP: do not retry, delete, or edit.
set -u
stop() { builtin echo "STOP: $*" >&2; exit 1; }
vpass() { builtin echo "$1"; builtin echo "$1" >> "$E/verify.txt" || stop "cannot write verify.txt"; }
TAR=lilith-mb1-kroot-c694061.tar
TAR_SHA=a42083c6ea85300ffbf550e2e6e09a9822c9b69b236f0c69c1f53ef218b9eb24
SUMS_SHA=92880077323536c8f756f5384ce83dffd11533cb05b990f30df3f20e5b564739
SRC=c6940615875fd13df1636d7c105ad5b65c39d112
NFILES=74
DL="$HOME/storage/downloads"
W="$HOME/lilith-mb1"                                   # staging and PUBLIC evidence
E="$W/evidence"
B="$W/lilith-mb1-kroot-c694061"
K="$HOME/lilith-kroot-dev-synthetic"                   # the ONLY place private K-ROOT material may exist
KEY="$K/k-root.der"
PUB="$HOME/lilith-kroot-dev-synthetic-public"          # the authoritative S25 copy of the PUBLIC anchor and fingerprint
X="$HOME/lilith-mb1-export.tar"                         # public-only export for the laptop
R="$HOME/lilith-owner-offline-dev-synthetic-01"         # Replica B: read only
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
assert len(every) == 12, "burned set is not the 12 accepted identities"
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
cat "$E/anchor-check.txt" || stop "cannot read anchor-check.txt"
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
- This is test-enforced, following the reviewed B-4 run-2 pattern.

**Pre-run (G0 / G1 / T1).** Any failure stops **before any write**:

- `HOME` or TMPDIR is not Termux private storage;
- an SSH session (`SSH_CONNECTION` / `SSH_CLIENT` / `SSH_TTY`), or `sshd`
  running;
- no interactive phone terminal (`-t 0`, `/dev/tty`);
- Python or `cryptography` missing or unsupported;
- `~/lilith-mb1`, `~/lilith-kroot-dev-synthetic`,
  `~/lilith-kroot-dev-synthetic-public`, or the export already exists
  (rerun safety);
- a stale TMPDIR directory;
- **any existing `k-root*` or `*REHEARSAL-TEST*` file** under `$HOME`;
- Replica B missing, not the accepted empty replica (`c068e533…`, 0
  records, `parent` line), or a nested Replica B;
- the bundle is not in Download, or its tar hash, `SHA256SUMS` digest,
  source commit, 74-file count, or `sha256sum -c` differs;
- the bundle is not in private storage;
- the owner does not type `GENERATE` on the phone terminal.

**Generation and checks (K1 / K2):**

- `root-keygen` exits non-zero: passphrase mismatch, too short, or an
  existing file;
- the key file is not regular, not `0600`, or not the only entry in a `0700`
  dir;
- `root-keygen` wrote to stderr;
- the output is not exactly `{registryRoot, publicKeySha256}` with a valid
  `TrustedRegistryRootV1`, the expected root key ID, and the `dev`
  environment;
- the fingerprint is not the SHA-256 of the raw 32-byte key;
- **the fingerprint equals any of the 12 burned identities** (checked
  against all three burned sets);
- the key loads without a passphrase;
- the passphrase does not unlock it, or the unlocked key does not match the
  anchor.

**Verification (V):**

- TMPDIR is not clean;
- any `k-root*` or rehearsal key file exists outside `$KEY`;
- a key-like file is in shared Download;
- any evidence file equals the key;
- the bundle changed;
- **Replica B changed**.

**Public copy and export (P / S / X):**

- the public copy is not exactly the anchor and the fingerprint;
- the seal does not verify;
- the export names the key directory, `k-root.der`, or a tar, or is not
  **exactly** the 14-file public allowlist.

**Cleanup.** The transport copy is removed only after everything above
passes, and only with explicit existence, `cmp`, `rm`, and absence checks.

**Acceptance requires `RUN_EXIT=0`, zero transcript lines beginning
`STOP`, and `MB1_KROOT_GENERATED` as the last token before `RUN_EXIT`.**

## 6. Partial failure and recovery

The script never deletes or retries anything. The only removal is the
transport copy, at the very end.

| STOP point | State left | Rule (P3-5 crash matrix) |
| --- | --- | --- |
| G0 / G1 / T1 or the `GENERATE` refusal | no key. At most `~/lilith-mb1/` exists | nothing private was written. Report; a rerun needs the staging directory removed after review |
| `root-keygen` refused (passphrase mismatch / too short) | **empty** `~/lilith-kroot-dev-synthetic/` and staging | no key exists (C-1). Report; the empty directory is removed only after review |
| after `root-keygen` succeeded (any K2 / V / P / X gate) | **a key file exists; no fingerprint was presented as recordable** | **C-2:** the fingerprint was **not** recorded (`MB1_KROOT_GENERATED` never printed). **Do not record or use it.** Report; the reviewed recovery is discard and regenerate, never reuse |
| burned-identity STOP | the key exists | as C-2, and the key must never be used |

**A failed ceremony cannot look successful:**

- `MB1_KROOT_GENERATED` and the recordable `MB1_KROOT_FINGERPRINT` are
  printed only after every gate;
- `RUN_EXIT` is the script's true exit status (the reviewed
  `PIPESTATUS[0]` invocation);
- any STOP leaves a `STOP:` line in the transcript.

## 7. Custody proofs

**No K-ROOT private material can be copied to the laptop by this package.**

- The script contains no network, MTP, `adb`, `ssh`, `scp`, `curl`, or `nc`
  command (test-enforced). The phone is in airplane mode.
- `$KEY` is used only as the `root-keygen` output path and in read-only
  checks: `test`, `stat`, `ls`, the at-rest and unlock checks, and `cmp`.
  It never appears in `cp`, `mv`, `tar`, `cat`, or `echo` (test-enforced).
- The only artifact meant for the laptop, `~/lilith-mb1-export.tar`, is
  built from an **explicit allowlist** that never names
  `lilith-kroot-dev-synthetic/`. It is then checked to be exactly the
  14-file public list, and every evidence and public file is
  `cmp`-compared against the key.
- The transcript holds only public output: `root-keygen` writes its JSON to
  a file, and the key bytes are never printed.
- **Simulation:** the key's bytes appear in neither the export nor the
  transcript.

**The passphrase is entered only on the S25.**

- It is read only by `getpass`, from the controlling terminal
  (`/dev/tty`), and nowhere else: twice by `root-keygen`, once by the
  unlock check.
- The package has **no** passphrase argument, environment variable, file,
  or `read` (the `read` reads only the word `GENERATE`). The owner tool's
  test hook (`main(passphrase=…)`) is not reachable from the CLI.
- G0 refuses SSH sessions and a running `sshd`, and requires the local
  terminal. So the terminal is the phone's own Termux session.
- **Simulation:** the passphrase never appears in the transcript.
- Airplane mode and the absence of screen mirroring or remote-input tools
  are **owner attestations**.

**Replica B:** read-only snapshots before and after, which must be
byte-identical.

**No other authority action.** The package cannot generate K-WIT, create
registry v1, create a genesis pin, append record 1, start any service, touch
activation, contact DEV or PROD, or authorize First Memory. None of those
tools or commands is in the script (test-enforced).

## 8. Evidence outputs

**Public** (in the export):

- `evidence/`:
  - `g0.txt`;
  - `replica-b-before.txt`, `replica-b-after.txt`;
  - `root-keygen.json` (the anchor and fingerprint);
  - `root-keygen.exit`, `root-keygen.stderr` (empty);
  - `anchor-check.txt`, `burned-check.txt`, `at-rest-check.txt`,
    `unlock-check.txt`;
  - `verify.txt`;
- `evidence.sha256`;
- `lilith-kroot-dev-synthetic-public/k-root-anchor.json` and
  `k-root.publicKeySha256`.

Also public: the transcript, and the `PHONE_SIDE_EXPORT_SHA256` written
down before transfer.

**Allowed on the laptop:** only the export tar, the transcript, and their
hashes. That is a **public working copy** of the anchor and fingerprint,
never the authoritative copy (B-4 decision).

**Never on the laptop:** `k-root.der`, anything from
`~/lilith-kroot-dev-synthetic/`, and the passphrase.

## 9. Validation

**Tests** (`test_b1b3e_mb1_kroot_package.py`):

- **Builder:** the closure equals the computed import closure, plus
  `burned_identities.py`. The build is deterministic and exact, with the
  B-4 tar format. It refuses forbidden member names and a bad commit or
  vendor set, and contains no rehearsal script.
- **Record and pins:** the §4 block digest equals the recorded digest, and
  the bundle pins match.
- **Structure:**
  - STOP only through `stop()`;
  - only `root-keygen` is invoked, exactly once;
  - no passphrase channel other than `getpass`;
  - `$KEY` only in allowed commands;
  - the export allowlist never names the key directory;
  - Replica B is read only;
  - none of the forbidden tools or commands appears.
- **The embedded checks, run directly:**
  - the anchor check accepts a real `root-keygen` output and refuses a
    tampered one;
  - the burned-identity check refuses each of the 12, and passes a fresh
    fingerprint;
  - the at-rest check refuses an unencrypted key.
- **A real-pty run of the pinned script** against a bundle of the working
  tree closure. Only the pins and the Termux prefix are substituted. It
  covers a clean run, a passphrase mismatch, a wrong unlock passphrase, an
  SSH session, and an owner decline.

**Full-fidelity WSL simulation** of the real bundle `a42083c6…` and the
real `root-keygen`, under a pseudo-terminal:

| Case | `RUN_EXIT` | Result |
| --- | --- | --- |
| clean | 0 | every token; key `0600`, the only entry; public copy; export exactly the 14-file allowlist; **key bytes in neither the export nor the transcript; passphrase not in the transcript**; Replica B unchanged; transport copy removed |
| passphrase mismatch / too short | 1 | `root-keygen` refused; **no key file** |
| owner types anything but `GENERATE` | 1 | STOP before the key directory exists |
| wrong unlock passphrase | 1 | STOP after generation; **no fingerprint presented, no public copy, no export** (C-2) |
| SSH session | 1 | STOP in G0 |
| existing key directory / stale `k-root` file / nested Replica B / bad bundle hash | 1 | STOP before any write |
| Replica B touched mid-run | 1 | `STOP: Replica B changed`; no export |

Every simulation key was deleted with its simulated home. The clean case
printed a throwaway TEST fingerprint, `ae5d8275dfcb39e7…c6c`, which is
**burned** like the rehearsal identities.

## 10. Review points addressed

| Review point | How it is addressed |
| --- | --- |
| accidental write paths | exactly five, all new and refused if present: `~/lilith-mb1/`, the key directory, the public directory, the export, and the transcript |
| path mistakes | canonical Replica B path; private and public directories distinct; the key directory must hold only `k-root.der` |
| shell quoting hazards | `set -u`; every path quoted; the Python checks passed as `-c "$VAR"` from quoted heredocs; no `eval` |
| rerun safety | every target must be absent; `O_EXCL` in `root-keygen` |
| partial-failure behaviour | §6 |
| evidence contamination | `cmp` against the key; the export allowlist; the transcript holds no secrets |
| accidental key export | §7 |
| a failed ceremony appearing successful | §6: the completion tokens come last, and the true `RUN_EXIT` |

## 11. State

```text
MB1_PACKAGE_PREPARED_READY_FOR_REVIEW
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
