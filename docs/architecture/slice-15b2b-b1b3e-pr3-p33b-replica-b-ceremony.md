# Slice 15B2b-B1b-3e PR-3 P3-3B: S25 Ultra Real Replica B Initialization Ceremony

**Status: P3-3B PREPARED FOR OWNER EXECUTION. Not executed.**

- Real Replica B is **not yet created**.
- Real Replica A is untouched. There is no real record 1, and real freshness
  remains `FRESHNESS_UNKNOWN`.
- P3-3 remains `P3_3_STORAGE_INCOMPLETE` until this ceremony runs **and**
  the independence evidence (§7) is accepted.
- No phone, DEV, or cloud contact was made to prepare it.

| Field | Value |
| --- | --- |
| Source | merged `main` `44a53f2d0fde605f9b2ae46589febee806405575` (PR #101 + #102: PR-3, P3-2 … P3-6, P3-3A and the probe fix) |
| Target | Samsung S25 Ultra, Termux app-private storage, `~/lilith-owner-freshness/owner-offline-dev-synthetic-01` |
| Replica | `replicaId = owner-offline-dev-synthetic-01`, `environment = dev`, `authorityProfile = DEV_SYNTHETIC` |
| Only mutation | `init-real-replica`, creating `REPLICA.json` plus an empty `records/` |
| Never run | `propose-genesis`, `propose-accept`, `propose-reject`, `append`, `build-review-package`, `propose-envelope`, `append-envelope`, `init-acceptance-store` |

## 1. Accepted S25 evidence (owner-reported)

- Termux private storage, on a physical device separate from Replica A.
- Probe results:
  - `directory_fsync=PASS`
  - `hardlink=UNAVAILABLE`
  - `rename_noreplace=PASS`
  - `direct_o_excl=PASS`
  - `symlink_detection=PASS`
  - `canonical_reread=PASS`
  - `cleanup=PASS`
  - `admitted_backend=RENAME_NOREPLACE_V1`
- Developer options OFF. Termux `sshd` not running.
- Google "Other device data" backup OFF. Samsung automatic backup observed
  OFF.
- No real Replica B exists.

## 2. The bundle

`lilith-p3-3b-44a53f2.tar` is 1 331 200 bytes, built deterministically
(sorted names, fixed mtime, owner 0:0).

```text
SHA-256(lilith-p3-3b-44a53f2.tar)      = ce163b632c0186e5a3268ea32342ecadfb8aed65fe0931a4bd1458d45a1c70dd
SHA-256(bundle SHA256SUMS, 74 files)   = 9bf11b2b67d3f905f14088fdc114ec107af14e5b5d4597f641c85aaf57feee2c
SHA-256(expected Replica B REPLICA.json) = c068e5331ccd7fa0f69f2b38d25849497b86edea843598784235874080c107c4
SHA-256(p33b_phone_commands.sh)        = d7b2f7a385806936c2089bbb7014b933455232c07aa8c11f50eed431f6bb160a
```

**Contents: only the import closure of the tool, plus the probe.**

| Part | Files | Origin |
| --- | --- | --- |
| `src/core-api/lilith_memory/` | `__init__.py`, `canonical_contracts.py`, `owner_proof.py` | `git archive 44a53f2` |
| `src/owner-memory-control/lilith_owner_memory/` | `__init__.py`, `authority_contracts.py`, `authority_verifier.py`, `contracts.py`, `create_only_publish.py`, `owner_acceptance.py`, `owner_freshness.py`, `owner_freshness_tool.py`, `recovery_contracts.py`, `rotation_contracts.py`, `witness_readiness.py` | `git archive 44a53f2` |
| `src/tools/android_p3_probe.py` | the standalone P3-3A probe | `git archive 44a53f2` |
| `vendor/fido2/` + `fido2-2.2.1.dist-info/` | pure Python, pinned in `services/core-api/requirements.txt` | the pinned test wheel set; every file verified against its wheel `RECORD` SHA-256 (47 files) |
| `vendor/rfc8785/` + `rfc8785-0.1.4.dist-info/` | pure Python, pinned | the same (6 files) |
| `EXPECTED_REPLICA_B_MANIFEST.json` | the exact expected `REPLICA.json` bytes (RFC 8785) | computed |
| `SOURCE_COMMIT` | `44a53f2d0fde605f9b2ae46589febee806405575` | — |
| `SHA256SUMS` | a SHA-256 for every other file | — |

`init-real-replica` never executes any cryptography. But the merged
tool's import graph imports `cryptography` (through `fido2` and the
authority contracts). That is a **native** package: it cannot be vendored
into a portable bundle, so it must already be installed in Termux. **Gate
G0 stops the ceremony if it is not.** Installing it would be a separate
owner decision taken before P3-3B, since it needs network access; it is not
part of this ceremony.

**Laptop staging** (outside the repository, OneDrive, and every Git tree):
`%USERPROFILE%\lilith-p3-3b\`. It holds the tar,
`SHA256SUMS.inside-bundle`, `p33b_phone_commands.sh`, and `STAGING.sha256`.

## 3. Transport: laptop to phone

`Download` is transport only.

1. On the laptop, verify the staged tarball:
   `certutil -hashfile %USERPROFILE%\lilith-p3-3b\lilith-p3-3b-44a53f2.tar SHA256`,
   which must print `ce163b63…70dd`.
2. Connect the S25 by USB cable **only for this copy**. Choose **File
   transfer (MTP)**.
   - Do not enable Developer options or USB debugging.
   - Do not open Smart Switch, and dismiss any backup prompt.
3. In Explorer, copy `lilith-p3-3b-44a53f2.tar` to the phone's **Internal
   storage › Download**.
4. Disconnect the cable.
5. In Termux, if `~/storage/downloads` does not exist, run
   `termux-setup-storage` once and grant the storage prompt. This is needed
   only to read Download. The permission can be revoked afterwards.

No ADB, no SSH, no network, and no cloud transfer (Quick Share or similar)
is used.

## 4. Phone commands (Termux, bash): exact

Run them step by step. **Every `STOP` marker is a hard stop.** They are
identical to `p33b_phone_commands.sh` (SHA-256 `d7b2f7a3…160a`), and they
were dry-run verbatim in a simulated Termux home directory (§6).

```bash
# ===================== P3-3B phone commands (Termux, bash) =====================
# Run step by step. Every "STOP if" is a hard stop: do not continue past it.

# ---- G0 preconditions (read-only) ----
cd "$HOME"
python -c 'import sys; print("PYTHON", sys.version.split()[0])'
python -c 'import sys, cryptography as c; v = c.__version__; m = int(v.split(".")[0]); print("CRYPTOGRAPHY", v); sys.exit(0 if 2 <= m < 52 and m != 35 else 1)' || echo "STOP: cryptography missing or unsupported"
test ! -e "$HOME/lilith-owner-freshness/owner-offline-dev-synthetic-01" && echo TARGET_ABSENT       # STOP if not printed
test ! -e "$HOME/lilith-p3-3b" && echo STAGING_ABSENT                                                # STOP if not printed

# ---- T1 transport: Download is transport only ----
mkdir -m 700 "$HOME/lilith-p3-3b" "$HOME/lilith-p3-3b/evidence"
cp "$HOME/storage/downloads/lilith-p3-3b-44a53f2.tar" "$HOME/lilith-p3-3b/"
cd "$HOME/lilith-p3-3b"
echo "ce163b632c0186e5a3268ea32342ecadfb8aed65fe0931a4bd1458d45a1c70dd  lilith-p3-3b-44a53f2.tar" | sha256sum -c -   # STOP unless OK
tar -xf lilith-p3-3b-44a53f2.tar
cd lilith-p3-3b-44a53f2
echo "9bf11b2b67d3f905f14088fdc114ec107af14e5b5d4597f641c85aaf57feee2c  SHA256SUMS" | sha256sum -c -                # STOP unless OK
sha256sum -c --quiet SHA256SUMS && echo BUNDLE_VERIFIED                                            # STOP if not printed
cat SOURCE_COMMIT                                                                                   # 44a53f2d0fde605f9b2ae46589febee806405575

# ---- environment (Termux private storage only) ----
B="$HOME/lilith-p3-3b/lilith-p3-3b-44a53f2"
E="$HOME/lilith-p3-3b/evidence"
P="$HOME/lilith-owner-freshness"
R="$P/owner-offline-dev-synthetic-01"
export PYTHONPATH="$B/vendor:$B/src/core-api:$B/src/owner-memory-control"
export PYTHONDONTWRITEBYTECODE=1
T() { python -B -m lilith_owner_memory.owner_freshness_tool "$@"; }

# ---- G1 standalone Android probe (temporary files only) ----
python -B "$B/src/tools/android_p3_probe.py" | tee "$E/android-probe.txt"
grep -qx "admitted_backend=RENAME_NOREPLACE_V1" "$E/android-probe.txt" && echo ANDROID_PROBE_GATE_PASS   # STOP if not printed

# ---- G2 parent, location policy, tool probe immediately before initialization ----
test -e "$P" || mkdir -m 700 "$P"
T location-check --path "$R" | tee "$E/location-check.json"
T probe-storage --probe-parent "$P" > "$E/probe-storage.json"; cat "$E/probe-storage.json"
python -c 'import json, sys; d = json.load(open(sys.argv[1])); sys.exit(0 if d["result"] == "P3_STORAGE_CAPABLE" and d["admittedBackend"] == "RENAME_NOREPLACE_V1" and d["checks"]["directoryFsync"] is True else 1)' "$E/probe-storage.json" && echo PROBE_GATE_PASS   # STOP if not printed
test ! -e "$R" && echo TARGET_STILL_ABSENT                                                          # STOP if not printed

# ---- M1 the ONLY mutation: initialize the empty Replica B ----
T init-real-replica --replica "$R" --replica-id owner-offline-dev-synthetic-01 --environment dev --profile DEV_SYNTHETIC | tee "$E/init-real-replica.json"

# ---- V strict verification ----
T verify-replica --replica "$R" | tee "$E/verify-replica.json"                                     # records 0, headDigest null
cmp "$R/REPLICA.json" "$B/EXPECTED_REPLICA_B_MANIFEST.json" && echo MANIFEST_EXACT
sha256sum "$R/REPLICA.json"                                                                         # c068e5331ccd7fa0f69f2b38d25849497b86edea843598784235874080c107c4
test -z "$(ls -A "$R/records")" && echo RECORDS_EMPTY
test "$(ls -A "$R" | LC_ALL=C sort | tr '\n' ' ')" = "REPLICA.json records " && echo NO_UNEXPECTED_ENTRIES
test "$(ls -A "$P")" = "owner-offline-dev-synthetic-01" && echo PARENT_CLEAN
stat -c '%n %a %F' "$P" "$R" "$R/REPLICA.json" "$R/records" | sed "s#$HOME#~#" | tee "$E/stat.txt"   # 700 dir, 700 dir, 600 file, 700 dir
python -c 'import json, sys; d = json.load(open(sys.argv[1])); sys.exit(0 if d["records"] == 0 and d["headDigest"] is None and d["replicaId"] == "owner-offline-dev-synthetic-01" else 1)' "$E/verify-replica.json" && echo ACCEPTED_FRESHNESS_RECORDS=0
sha256sum "$E"/* > "$HOME/lilith-p3-3b/evidence.sha256"; cat "$HOME/lilith-p3-3b/evidence.sha256"
# ============================== end of P3-3B ==============================
```

**Expected verification output:**

- `MANIFEST_EXACT`
- `REPLICA.json` SHA-256 `c068e533…07c4`
- `RECORDS_EMPTY`
- `NO_UNEXPECTED_ENTRIES`
- `PARENT_CLEAN`
- modes `700 / 700 / 600 / 700`
- `ACCEPTED_FRESHNESS_RECORDS=0`
- `verify-replica` returns `REPLICA_VERIFIED`, `records = 0`,
  `headDigest = null`

**Afterwards:**

- Delete the transport copy with
  `rm "$HOME/storage/downloads/lilith-p3-3b-44a53f2.tar"`, and optionally
  revoke Termux's storage permission.
- Keep `~/lilith-p3-3b/` (bundle and evidence) in Termux private storage.

**If any STOP fires:**

- Do not retry by deleting anything.
- Record the output, and leave every directory as it is.
- A partially created `~/lilith-owner-freshness/` parent with no replica is
  harmless.
- An existing Replica B directory makes `init-real-replica` refuse
  (`REPLICA_PATH_EXISTS`).

## 5. What the ceremony deliberately does not do

- **Cross-device independence check.** It does not run `check-independence`
  across devices, because the tool needs both replicas on one filesystem
  tree. Cross-device independence is owner evidence (§7). Replica A is
  never present on the phone.
- **The `--other-replica` guard.** `init-real-replica` runs without
  `--other-replica`, because Replica A is not on the phone. Distinctness is
  established by the fixed, different replica IDs
  (`owner-primary-dev-synthetic-01` vs `owner-offline-dev-synthetic-01`)
  and separate physical devices.
- **Laptop side.** It does not touch Replica A, the laptop replica set, or
  any acceptance store.

## 6. Dry run (WSL, simulated Termux home, temporary)

The exact command file was executed in a temporary home directory with a
fake `storage/downloads`. The Android probe was driven directly, because
its Termux-path guard refuses non-Termux paths by design.

Result: every gate passed.

- `BUNDLE_VERIFIED`, and `admitted_backend=RENAME_NOREPLACE_V1`.
- `PROBE_GATE_PASS`, then `REAL_REPLICA_INITIALIZED_EMPTY`.
- `REPLICA_VERIFIED` with `records = 0`.
- `MANIFEST_EXACT` (`c068e533…`), `RECORDS_EMPTY`, `NO_UNEXPECTED_ENTRIES`,
  `PARENT_CLEAN`.
- Modes `700 700 600 700`, and `ACCEPTED_FRESHNESS_RECORDS=0`.
- A second `init-real-replica` was refused with `REPLICA_PATH_EXISTS`.
- The simulation directory was removed.

## 7. Evidence

### 7.1 Public-safe evidence template (fill after execution)

```text
P3-3B RESULT: <P3_3B_REPLICA_B_INITIALIZED_EMPTY | P3_3B_STOPPED_AT_<gate>>
date (UTC): <YYYY-MM-DD>
source commit: 44a53f2d0fde605f9b2ae46589febee806405575
bundle tar SHA-256: ce163b632c0186e5a3268ea32342ecadfb8aed65fe0931a4bd1458d45a1c70dd  (verified on phone: <yes/no>)
bundle SHA256SUMS verified: <BUNDLE_VERIFIED>
storage class: Android phone, Termux app-private storage (separate physical device from Replica A)
android probe: directory_fsync=<>, hardlink=<>, rename_noreplace=<>, direct_o_excl=<>, symlink_detection=<>,
               canonical_reread=<>, cleanup=<>, admitted_backend=<>
tool probe: result=<P3_STORAGE_CAPABLE>, admittedBackend=<RENAME_NOREPLACE_V1>, directoryFsync=<true>
replicaId: owner-offline-dev-synthetic-01   environment/profile: dev / DEV_SYNTHETIC
REPLICA.json SHA-256: <c068e5331ccd7fa0f69f2b38d25849497b86edea843598784235874080c107c4>   MANIFEST_EXACT: <>
records/: <RECORDS_EMPTY>   unexpected entries: <NO_UNEXPECTED_ENTRIES>   modes: <700/700/600/700>
accepted freshness records: <0>
evidence.sha256 digest (private files): <sha256 of ~/lilith-p3-3b/evidence.sha256>
not run: propose-*, append, build-review-package, propose-envelope, append-envelope, init-acceptance-store
Replica A: untouched   record 1: absent   real freshness: FRESHNESS_UNKNOWN
```

### 7.2 Private evidence checklist (keep off-repository)

| # | Item | Where |
| --- | --- | --- |
| PV-1 | the full terminal output of every step, including every STOP gate | phone, copied to owner notes |
| PV-2 | `~/lilith-p3-3b/evidence/*` (the Android probe, location check, tool probe, init output, verify output, stat) and `evidence.sha256` | phone (Termux private) |
| PV-3 | absolute paths and the device number from `init-real-replica` (never published) | PV-2 |
| PV-4 | `python` and `cryptography` versions from G0 | PV-1 |
| PV-5 | the phone's model and Android and Termux versions | owner notes |
| PV-6 | **backup posture**, at the time of initialization: Google backup (including "Other device data") OFF; Samsung Cloud / automatic backup OFF; no Smart Switch archive containing Termux data on any PC or medium; whether the Termux manifest allows app-data backup | owner observation, with screenshots kept private |
| PV-7 | **agent boundary**: Developer options OFF, USB debugging OFF, Termux `sshd` not running, no automation apps with Termux access | owner observation |
| PV-8 | **independence**: the laptop (Replica A: WSL VHDX on the internal NVMe) and the phone (Replica B) share no sync or backup path; no laptop backup holds a phone archive, and no phone backup holds the laptop disk | owner statement |
| PV-9 | the transport copy was deleted from Download, and whether the storage permission was revoked | PV-1 |
| PV-10 | a laptop-side read-only `verify-replica` of Replica A after the ceremony, still showing 0 records | laptop |

## 8. After execution

P3-3 can be recorded complete only after the owner reviews:

- the §7.1 result;
- PV-6 … PV-8, with "Can one ordinary rollback restore both replicas?"
  answered **NO** with evidence;
- the open custody item (PR-3 §25.5): the phone copy is the
  agent-unreachable one, so it must stay disconnected and without ADB or
  SSH;
- a separate acceptance record.

**PR-1B stays not eligible until then, and also after it until
authorized.**

## 9. Nonclaims

Preparing P3-3B does **not** establish any of the following:

- Replica B;
- P3-3 completion;
- independence;
- backup safety;
- real freshness;
- any owner record or envelope;
- any K-WIT, registry, ledger, witness, hold, RecoveryEpoch, or
  INITIAL_CUSTODY state;
- PR-1B, A1–A7, or First Memory progress.

## Appendix: bundle `SHA256SUMS` (74 files)

```text
c068e5331ccd7fa0f69f2b38d25849497b86edea843598784235874080c107c4  EXPECTED_REPLICA_B_MANIFEST.json
d0730c0c6f36a83e0213912cd9db8b3550f83e097c243edd6124573c8e53dc9c  SOURCE_COMMIT
2bbebd95846f1073a0b4e2ec3a2aa24378c56be4ecbb5470e5c1f1d359037e21  src/core-api/lilith_memory/__init__.py
f93d26d8a7e01d78d25f1f1d9540577cf2a55dfd4d52c4b64c87bef93ad887e0  src/core-api/lilith_memory/canonical_contracts.py
3a3eb7147d1e276ac261457a2340e045a0c43f6bc63eeb1a78bfc9864f80ac08  src/core-api/lilith_memory/owner_proof.py
d1f1bf65a24315005ca4b597971dec6efa0212d4ab5836832e2a5a80fb9e62b4  src/owner-memory-control/lilith_owner_memory/__init__.py
fabd8fd24f45febe83f8fd67c3fc39f277278e9145df9c55d5e03e5e8598e74f  src/owner-memory-control/lilith_owner_memory/authority_contracts.py
3c808267e56e9abc1ea1e848881cefd20a56fde51d9e803ac90f7f0c7517e83a  src/owner-memory-control/lilith_owner_memory/authority_verifier.py
ff5075f1131f84348bdbc5d3fbd3410e53c7da39e265476a0b57ace6ff8ef5c7  src/owner-memory-control/lilith_owner_memory/contracts.py
58b22c6d2a8dbb2b907348b806c0df32e2290ea6d6f590ccb8151a067ea232a5  src/owner-memory-control/lilith_owner_memory/create_only_publish.py
1e4ffe11b69963b2998ad3c342e2d482268ff74d8c69c510a90743aac61ee31d  src/owner-memory-control/lilith_owner_memory/owner_acceptance.py
9eab25b892010f1de966fb5c23357bf93a60ea472d02bbaf7a16fc1336b76689  src/owner-memory-control/lilith_owner_memory/owner_freshness.py
1ef8534412e39cdea2b5cdaef9a8c269a5a50aefbefd91672a1ecbf04595e8d9  src/owner-memory-control/lilith_owner_memory/owner_freshness_tool.py
f4a14cff094d167a2a7925622031352955291c18244545e95c0003fb9231b95e  src/owner-memory-control/lilith_owner_memory/recovery_contracts.py
8f9df8dcd3e8a1b0cd8f03169bf7a51d4b6726cbb708cadfb3025586211996b0  src/owner-memory-control/lilith_owner_memory/rotation_contracts.py
129d4479a7c86a6ef33acfb27da4f5cd6c6a6947b89184863a50117091fe3cbd  src/owner-memory-control/lilith_owner_memory/witness_readiness.py
9b1b69a028629cc8df2d1b4f7a2bf1f6540c9e5b130d2a4afd689f91d0277678  src/tools/android_p3_probe.py
65afb1ae6cd9a954aa39dc9deb7c36b7b4bc26a6c10db475fed71eff8caedbd2  vendor/fido2-2.2.1.dist-info/METADATA
d9a7adf846821366a3c03bff1ad9d26c5a4807c482ba4ac9b4dcaa6eb3f79501  vendor/fido2-2.2.1.dist-info/RECORD
798ee776ec33bfe95d531a736d1971c2f0baf771e0e8f5fc6d60e31078d9fdd9  vendor/fido2-2.2.1.dist-info/WHEEL
3f32bbc57de1cb9c191b1898d8e47f866f206604e08ff1b39a3ea7a2c98452de  vendor/fido2-2.2.1.dist-info/licenses/COPYING
cfc7749b96f63bd31c3c42b5c471bf756814053e847c10f3eb003417bc523d30  vendor/fido2-2.2.1.dist-info/licenses/COPYING.APLv2
fab3dd6bdab226f1c08630b1dd917e11fcb4ec5e1e020e2c16f83a0a13863e85  vendor/fido2-2.2.1.dist-info/licenses/COPYING.MPLv2
0ee1bb3e529d81ef438db7f9671d5ad720efa52b81e951dd2fea1f9b49b41399  vendor/fido2/__init__.py
f177fc3ab69d26e8ad08242943fd1d6243fd37eabd14297fef7c38e6065ebe24  vendor/fido2/arkg.py
ffa97f2aca1a1fa3941e4fbfa6c656b31efe49388c73f9eb581986be7ab56c0b  vendor/fido2/attestation/__init__.py
dd4c73c329bd409335f113879e92cb340a6af9e8a95a75b98b5f16f642547352  vendor/fido2/attestation/android.py
8511ea01d0fa55af06d2c7ea7bfffd3b5246503fb1dc66eaadf024361f47853a  vendor/fido2/attestation/apple.py
13de140a8344b3d46909c186b2c303a2352a79b2308020dff0243ac6e0a98b2f  vendor/fido2/attestation/base.py
1cbaa12c510918ea2b747b80bbd5c90ab4aa415196187aa2aa85028e9d0eb43b  vendor/fido2/attestation/packed.py
bdbbac95c439a6aa89fd42f82e1e107afe78f1e4490ba89dd18a3347ed60c7b7  vendor/fido2/attestation/tpm.py
969627f4eacb4bf79377ae2bd33fcc31e54fd406c325f25c29acb530d46e6723  vendor/fido2/attestation/u2f.py
e4956054e3519aded35592aa48da5db43645faa0c4c018dd56fe28051a9ce780  vendor/fido2/cbor.py
832878a5636f7e9a90826f1be856677a0a504925ca95ebaf77482bbd1237f099  vendor/fido2/client/__init__.py
59cfe51d23cbaf80068223560f4d97ddde049a02274f475bc46200cb0f4e8967  vendor/fido2/client/win_api.py
0dc7aa0a5cc7031836591c32f711d56fe020be182dfc0a89114a425b91e48fdd  vendor/fido2/client/windows.py
b9023f6b1143d940d3815d87d2656652c385f4359edb4dd93d31e7c9cf44f444  vendor/fido2/cose.py
82a35f22a6c93138f70e1bfd910d676d2ff6b98e419afe97595acb1bda89ce4b  vendor/fido2/ctap.py
a69b13011e627eee723e1a1503f5c02a8fa02e8e787e0870f4d1dac5a7173c3b  vendor/fido2/ctap1.py
72ff13a0d64c4eee46fb46c5b3c51306422af42721d10bf0a2b735c97de841dc  vendor/fido2/ctap2/__init__.py
d7b8c266f547828da22f5a0406fa1770b13abd41b5d709221ffa6d02db80bf36  vendor/fido2/ctap2/base.py
b356c3fcc6a68cf052b399aa1f3a3c5a817a5af55eaf73eacdfa86d3324a278f  vendor/fido2/ctap2/bio.py
823eb9a19e1354b3c6812c4b898af6626d37cbc962a51aba0c706868463d2c59  vendor/fido2/ctap2/blob.py
2e6e1505e9ad74f2fb094f9e146a0a9aa22dd198a4a607c00a9290d53d967d6d  vendor/fido2/ctap2/config.py
5e416f468785948d739e8a56cb1476a02cbb887f976b483e2f080caf0fc247b0  vendor/fido2/ctap2/credman.py
dec5d2e071dcb9308164f73018f41ba214aed31c299f7fcfac5d331b655dcbc0  vendor/fido2/ctap2/extensions.py
27adb86944e077f04cdc1693208ef754f044e5a1f7abf150e46457808f1861b1  vendor/fido2/ctap2/pin.py
e02b12f7b7ce38c7a3cfa09207b02da7e7aa8402338a28483adf01363427c24b  vendor/fido2/features.py
55ea60139170f82a119c7f36802d3ff3ec3bb7cd034a3f4f8a30475961635b39  vendor/fido2/hid/__init__.py
6090b2f37fe82c3e11ec3b70db202fa51bdb11c86ec1e37a3e098faddde9ebf6  vendor/fido2/hid/base.py
791458fbc970b67afe92dbe5f067fd55262f92a05ca18a5a112dcdd315456b3c  vendor/fido2/hid/freebsd.py
b23b109a229a2622503f232c61e3288462c00cc01c0416dd5338c6ff69fbf823  vendor/fido2/hid/linux.py
bb19c6a4f1d652d69c8d4a76f916d1d7c181dab71787743e969129330cab2fca  vendor/fido2/hid/macos.py
73aed0120688c855896602990627ddbade3723b19d453de133ce6d8a04071da5  vendor/fido2/hid/netbsd.py
c32374760d5c115949dbb00703bfe48c33f966400e3127ef88d7408c402a96c6  vendor/fido2/hid/openbsd.py
0456c072fb235b84796c9a46c3afb955ed07f7248a3459737185af0e6fb270e7  vendor/fido2/hid/windows.py
b157401d44b3787d37342940c8eb1ed9db6efd987ad63159a9a1ebc72df8bb65  vendor/fido2/mds3.py
ec7c556fa6a7d6e62e23cb4f6e3b965ae6a54e6457e375e3dfe8a52444005f7d  vendor/fido2/payment.py
fc3a0df236699a9f5033c6d34e17b8891cc74227cf8ca603e39c2eab07e4280c  vendor/fido2/pcsc.py
8208f0c918c6cb3ab77b484635fc8683c94cbfff818be81950908e881a5f8be2  vendor/fido2/public_suffix_list.dat
e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855  vendor/fido2/py.typed
8226d4c0329f6fc77f5508307940daef9fdad240ead02c1ca4286d4a8c0a084b  vendor/fido2/rpid.py
5333c4fbf041e90b4e2e19a949d6b101b44fa5805e0a87a4c8a1f1c459993cbc  vendor/fido2/server.py
eb2b5afc4e44127bd0eb35f997ed8a330cc3fb8fc0bfc0276a04540f0d54c018  vendor/fido2/utils.py
c3651f6ffee564c18207e65c7858cc1e4d17e83a70b0bb46e3a999b046112d99  vendor/fido2/webauthn.py
0d542e0c8804e39aa7f37eb00da5a762149dc682d7829451287e11b938e94594  vendor/rfc8785-0.1.4.dist-info/LICENSE
9dfbf420c8c18077dd7697ec12fe2838b5901683573ae128df2d3403330f7aa9  vendor/rfc8785-0.1.4.dist-info/METADATA
a6a9131be557aa3e3764604df469eb92d457289548885c7085e58943e7ce8e87  vendor/rfc8785-0.1.4.dist-info/RECORD
1196c6921ec87b83e865f450f08d19b8ff5592537f4ef719e83484e546abe33e  vendor/rfc8785-0.1.4.dist-info/WHEEL
fa44927afd547caf7547247078bcf28863d1e69caf116d258c532b3f20ffd154  vendor/rfc8785/__init__.py
80aea74efb380f714b5153efa0103d7b6b41c25b6e9cac2150d15d8c47f129b1  vendor/rfc8785/__pycache__/__init__.cpython-312.pyc
8ad0e2155badc785ea9750cf35a9eb45410d40c61df648b8c8fbac0048628599  vendor/rfc8785/__pycache__/_impl.cpython-312.pyc
c25bc3a046528482d53bee3487b837f31dd9c05f33e8f13288c7aab320932cec  vendor/rfc8785/_impl.py
e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855  vendor/rfc8785/py.typed
```

```text
REAL REPLICA B NOT YET CREATED   REAL REPLICA A UNTOUCHED   NO REAL RECORD 1   REAL FRESHNESS REMAINS UNKNOWN
NO DEV CONTACT   NO CLOUD CONTACT   NO K-WIT   NO REGISTRY   NO LEDGER   NO WITNESS STATE   NO INITIAL_CUSTODY
PR-1B NOT AUTHORIZED   FIRST MEMORY NOT AUTHORIZED
```
