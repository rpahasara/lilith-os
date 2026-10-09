# Slice 15B2b-B1b-3e — Post-Reboot Re-pin: Witness and Broker Identities

Status:

- **SOURCE / DOCUMENTATION CHANGE ONLY.** `LIVE_MUTATION = NONE`, and no DEV contact.
- Base (control) `25d1397af9dd6489814cd0a4546610d139827e4f` (PR #176, the Package C design, merged).
- It re-pins the repository to two runtime identities the owner has already accepted after the
  2026-10-09 M-R1 reboot (§2). It changes no check, refusal, phase, sequence or authority semantics.
- **PACKAGE C NOT OPENED. C1 NOT STARTED. RECORD 1 ABSENT. FIRST MEMORY NOT AUTHORIZED.**

```text
re-pinned != deployed != preservation PASS != C1 authorized
```

## 1. Why

A scheduled unattended kernel upgrade (`linux-image-7.0.0-1014-gcp`) set `REBOOT_REQUIRED`. The owner
authorized one controlled reboot (M-R1). After it:

- the witness was restarted once through the reviewed restart procedure (plan `bb765760…`);
- the broker was started once (M-R2) and re-baselined twice, at least five minutes apart.

The owner accepted both new incarnations (§2). The repository still pinned the pre-reboot identities:

- `scripts/verify_broker_dev_current_incarnation.py` `preservation` pinned the 2026-10-02 broker baseline,
  so it fails by design on the new broker;
- `pkgc_operator.ACCEPTED_PINS` pinned the Package B witness incarnation, so every Package C acquisition
  would fail `incarnationAccepted`.

## 2. Owner acceptances (verbatim)

Both texts were issued identical to the rendered drafts. Evidence: `C:\Users\edufo\lilith-reboot-1014-25d1397`
(`SHA256SUMS.seal-3-60ad4359` = SHA-256 `60ad435997704d88a2bf28a7ef72df467dbfa5dc34a08267cb4ab744cf2cd912`).

**Witness incarnation** (`restart/witness-incarnation-acceptance.txt`, SHA-256
`f7f95e6525263cd88abe166cdef518bb6254a04816d0998c465f8ca33dd16be5`):

> I accept the post-reboot witness runtime incarnation for DEV_SYNTHETIC: lilith-recovery-witness.service InvocationID 8af12bd64d024d0eba56bbcedbc534a6, MainPID 1580, NRestarts 0, started 2026-10-09T09:42:02Z by the one reviewed restart of plan bb7657607bc23700048c6aa46713e696e4f49cbf819b0bdb222424db2743b233 (W9_5S_GENESIS_COMMITTED_STOPPED -> W9_5_GENESIS_COMMITTED_EXACT), on boot cb0d71da-32a7-402b-b85e-5748da012bff, kernel 7.0.0-1014-gcp, REBOOT_REQUIRED absent, control 25d1397af9dd6489814cd0a4546610d139827e4f.
> The committed witness lineage is unchanged: genesis ac892dc2b14ca7db108400258abfcf2320ff498f2a674058058e16a8a6fb65e4; chain/1.json and witness.json SHA-256 252c32204bebf3fa1ca0981d8791115e2abb6cd8ddb0925285c64213317cfb99; store and health CONSISTENT; P1B-9b and P1B-5 PASS. The earlier incarnation 5136ea7af2544450b9370fa412786c98 / 143946 is historical.
> The signer remains inactive, the hold store is empty, REGISTRY_EFFECTIVE remains NO, AUTHORITY_ACTIVE remains NO, authorityGranted remains false and Record 1 remains absent. The memory broker remains stopped and its post-reboot baseline is not established.
> This acceptance authorizes nothing further: not M-R2, the broker baseline or re-pin, a Package C pin change, any deploy, C1, Record 1, the acceptance envelope, HELD, the signer, authority activation, First Memory or PROD.

**Broker baseline** (`mr2/broker-baseline-acceptance.txt`, SHA-256
`bd715a373843ed1bd193d84ce506e967badf4c4f5bc18ae73f14d5c60cfed9a0`):

> I accept the post-reboot memory broker baseline candidate ff3a432d9d8e5c23718be41898be9568dd8914f0e2e28bb4c27f8e0bccaa3ef1 for DEV_SYNTHETIC (broker scope only): lilith-memory-broker.service runtime incarnation ed35e343bc9f4ec687f753ed7b3a53b2, PID 3411, start ticks 125335, started 2026-10-09T09:52:33Z, NRestarts 0, release 817a83e44cec8965479fd97fc30b7a0b3ae49ab2, manifest 7a46ac83001411a29b1bc4be7e0f91f09c5879967386c452b2620e23d16e4614, shared libraries 818994544397da37d5a97e3799afff314608a7aa00cad50c968a90b86f41ce60, on boot cb0d71da-32a7-402b-b85e-5748da012bff, kernel 7.0.0-1014-gcp, REBOOT_REQUIRED absent, control 25d1397af9dd6489814cd0a4546610d139827e4f.
> It was produced by the one reviewed M-R2 start and two reviewed rebaseline reads (BROKER_REBASELINE=PASS twice, at least 5 minutes apart, identical candidate and incarnation). The earlier broker incarnation c4b9cb38d7a041dc91db0d8ada7e8d04 and baseline a30bd7d6e26a75e4eba863c08622aebbbaf72928bc9dc7737fc1f7aa6473069d are historical.
> The accepted witness incarnation remains 8af12bd64d024d0eba56bbcedbc534a6 / 1580 / NRestarts 0 at W9_5_GENESIS_COMMITTED_EXACT with genesis ac892dc2b14ca7db108400258abfcf2320ff498f2a674058058e16a8a6fb65e4 and chain/1.json 252c32204bebf3fa1ca0981d8791115e2abb6cd8ddb0925285c64213317cfb99. The signer remains inactive, the hold store is empty, REGISTRY_EFFECTIVE remains NO, AUTHORITY_ACTIVE remains NO, authorityGranted remains false and Record 1 remains absent.
> This acceptance authorizes nothing further: not the verifier re-pin, a Package C pin change, any repository change, merge or deploy, C1, Record 1, the acceptance envelope, HELD, the signer, authority activation, First Memory or PROD.

This record is the reviewed re-pin those acceptances left open. It is authorized separately by the owner's
post-reboot re-pin instruction (preparation, commit, push and PR only).

## 3. Broker preservation verifier pins

In `scripts/verify_broker_dev_current_incarnation.py`:

| Constant | Old (now retired) | New (accepted in §2) |
| --- | --- | --- |
| `ACCEPTED_CURRENT_INCARNATION` | `c4b9cb38d7a041dc91db0d8ada7e8d04` | `ed35e343bc9f4ec687f753ed7b3a53b2` |
| `ACCEPTED_CURRENT_BASELINE_SHA256` | `a30bd7d6e26a75e4eba863c08622aebbbaf72928bc9dc7737fc1f7aa6473069d` | `ff3a432d9d8e5c23718be41898be9568dd8914f0e2e28bb4c27f8e0bccaa3ef1` |
| `ACCEPTED_CURRENT_BOOT_ID` | `eea461c3-60f0-4b10-8ee9-556dcef19711` | `cb0d71da-32a7-402b-b85e-5748da012bff` |
| `ACCEPTED_CURRENT_IDENTITY` | PID `35622`, start ticks `26369693`, boot `eea461c3…` | PID `3411`, start ticks `125335`, boot `cb0d71da…`. `nRestarts` `"0"`, release `817a83e44cec8965479fd97fc30b7a0b3ae49ab2`, manifest `7a46ac83001411a29b1bc4be7e0f91f09c5879967386c452b2620e23d16e4614` and shared libraries `818994544397da37d5a97e3799afff314608a7aa00cad50c968a90b86f41ce60` are unchanged |
| `ACCEPTED_CURRENT_CONTROLLER_EXPECTED` | `CONTROLLER_POST_REBOOT_EXPECTED` | unchanged: the Stage III controller has never run in the new boot |
| `RETIRED_BROKER_BASELINES` | `42af2691…`, `84798e5b…` | plus **`c4b9cb38…`** (candidate `a30bd7d6…`, boot `eea461c3…`; ended by the 2026-10-09 M-R1 reboot; record: [broker restart recovery](slice-15b2b-b1b3e-broker-restart-recovery.md)) |

Nothing else changes: no check, no operation, no `rebaseline` supersession semantics, no controller contract.
`rebaseline` now supersedes `ed35e343…` and still requires a boot other than `cb0d71da…`.

Verifier SHA-256: `2e68160971a3b0dd05ffcb6cdc464fc612afb2b522a57fb534b25c6af83c10ba` →
**`b90ed6efa203f7aade5519120e1658b866aa9f0d4f559e6ac39fcc51573ebfcf`**.

### 3.1 Proof against the accepted evidence

- The accepted candidate preimage (Appendix A, copied from `mr2/B4-rebaseline2.out`; both rebaseline reads
  carry byte-identical output, SHA-256 `1edf7a59…6b2e`) hashes with the verifier's own `canonical_sha256` to
  exactly `ff3a432d…`. Its identity fields are exactly the new `ACCEPTED_CURRENT_IDENTITY` (tested).
- The live post-M-R2 `preservation` read (`mr2/host-POST9B/preservation.out`, SHA-256
  `774dedd972ed11ec7fc5a68ff7e3c16d0b517e3673db31e929edcaab717614fe`) failed with exactly
  `RUNTIME_INCARNATION_NOT_ACCEPTED_BASELINE`, `ACCEPTED_IDENTITY_CHANGED:bootId`,
  `ACCEPTED_IDENTITY_CHANGED:pid`, `ACCEPTED_IDENTITY_CHANGED:startTicks` and `BASELINE_CANDIDATE_CHANGED`:
  only the pinned fields this re-pin moves. No raw `collect()` dump was captured, so no offline replay of the
  re-pinned verifier was run; the first live proof is the post-merge preservation read (§6).

## 4. The verifier hash cascade

The verifier is streamed to DEV hash-gated. Every tool-pin list that pins it:

| Pin list | Role now | Change |
| --- | --- | --- |
| `mb9_operator.TOOL_PINS` | **current**: the Package B read-only forms (`host POST9B`, `chain-export`) that Package C `acquire` runs, and post-merge preservation | `BROKER` pinned explicitly to `b90ed6ef…` (it was derived from `mb6_operator.TOOL_PINS`) |
| `pkgc_operator.TOOL_PINS[mb9_operator.py]` | **current**: hash-checked before every acquisition | `066fc8213b40c392e3e2bfd609da4a7f2a4e0b6f05da011daee9add3caf13973` → `2312e26a9cc8c2076539ae8bdde98cc5d79c2bbeb5138d66d07863ec3303c928` |
| `mb6_operator.TOOL_PINS` (M-B6), `mb7_mb8_operator.TOOL_PINS` (Package A, derived from M-B6), `mb4_mb5_operator.TOOL_PINS` (M-B4/M-B5) | **historical**: completed, owner-accepted ceremonies, never re-run | **none**: byte-unchanged; they keep `2e681609…` and refuse the current tree with `TOOL_PIN_MISMATCH` (fail closed, tested) |

The completed operators stay byte-identical because `mb9_operator` checks their bytes at run time
(`mb6_operator.py` `4a91d984…`, `mb7_mb8_operator.py` `9f13411f…`), and because their accepted completion
records bind those hashes. Their tests check the historical pin exactly and exercise their logic against
the current verifier bytes (`tests/post_reboot_repin.py`).

Final SHA-256 values:

| File | Before | After |
| --- | --- | --- |
| `scripts/verify_broker_dev_current_incarnation.py` | `2e68160971a3b0dd05ffcb6cdc464fc612afb2b522a57fb534b25c6af83c10ba` | `b90ed6efa203f7aade5519120e1658b866aa9f0d4f559e6ac39fcc51573ebfcf` |
| `services/owner-memory-control/tools/mb9_operator.py` | `066fc8213b40c392e3e2bfd609da4a7f2a4e0b6f05da011daee9add3caf13973` | `2312e26a9cc8c2076539ae8bdde98cc5d79c2bbeb5138d66d07863ec3303c928` |
| `services/owner-memory-control/tools/pkgc_operator.py` | `d7aaf9022982edecf5ff21d53faa1e34e04cf9ef9501a8622b1e3f327b9df298` | `7577c10bfe1e612bf11b81ac069e90cd47b4abc2c77e388c040bdd52bd1803fa` |

`pkgc_operator.py` is not pinned by any other file. A test reverses exactly this re-pin's edits in each of
the three files and gets back the "Before" hash, so each diff is the re-pin and nothing else.

## 5. Package C witness pins

In `pkgc_operator.ACCEPTED_PINS`:

| Field | Old (historical) | New (accepted in §2) |
| --- | --- | --- |
| `witness_invocation_id` | `5136ea7af2544450b9370fa412786c98` | `8af12bd64d024d0eba56bbcedbc534a6` |
| `witness_main_pid` | `143946` | `1580` |

`NRestarts = 0` stays a separate check (`noRestart`). Package C does not pin a boot id: the binding takes it
from the verified acquisition, and any later change is `BOOT_ID_CHANGED` (HALT). Unchanged: genesis
`ac892dc2b14ca7db108400258abfcf2320ff498f2a674058058e16a8a6fb65e4`, `chain/1.json` `252c32204bebf3fa1ca0981d8791115e2abb6cd8ddb0925285c64213317cfb99`,
the installables, the P-A / P-B pin record, both replicas, every state, gate, template and refusal. The
historical incarnation now fails `incarnationAccepted` (tested). The incarnation row of the
[Package C design record](slice-15b2b-b1b3e-pkgc-record1-envelope-package.md) §1 is superseded by this table.

## 6. After merge (not authorized by this record)

1. The merge's routine deployment runs DR-5.
2. A read-only post-merge preservation through `mb9_operator host POST9B` must show
   `BROKER_PRESERVATION=PASS` on `ed35e343…` / `ff3a432d…`, W9_5 exact on `8af12bd6…` / 1580, and DR-5
   equal to the accepted baseline.
3. Only then can the owner consider C1.

## 7. Validation

- `scripts/test_verify_broker_dev_current_incarnation.py`, `scripts/test_compare_reboot_host_observations.py`,
  `scripts/test_needrestart_lilith_override.py`.
- `services/owner-memory-control/tests` (full), including `test_b1b3e_post_reboot_witness_broker_repin.py`.
- `services/authority-dev/tests` (full).
- `scripts/validate_repository.py`, `compileall`, `git diff --check`.

## 8. State

```text
POST_REBOOT_REPIN = PREPARED (PR, NOT MERGED)
LIVE_MUTATION = NONE
DEV_CONTACT = NONE
BROKER_ACCEPTED = ed35e343bc9f4ec687f753ed7b3a53b2 / ff3a432d9d8e5c23718be41898be9568dd8914f0e2e28bb4c27f8e0bccaa3ef1
WITNESS_ACCEPTED = 8af12bd64d024d0eba56bbcedbc534a6 / 1580 / NRestarts 0
WITNESS_GENESIS = ac892dc2b14ca7db108400258abfcf2320ff498f2a674058058e16a8a6fb65e4 (UNCHANGED)
REGISTRY_EFFECTIVE = NO
AUTHORITY_ACTIVE = NO
authorityGranted = false
SIGNER = INACTIVE
HOLD_STORE = EMPTY
RECORD_1 = ABSENT
PACKAGE_C = NOT OPENED
C1 = NOT STARTED
C2 / C3 / C4A / C4B = NOT AUTHORIZED
FIRST_MEMORY = NOT AUTHORIZED
PROD = NOT AUTHORIZED
```

## Appendix A. Accepted broker baseline candidate (preimage of `ff3a432d…`)

```json
{
 "bootId": "cb0d71da-32a7-402b-b85e-5748da012bff",
 "execMainStartTimestamp": "Fri 2026-10-09 09:52:34 UTC",
 "manifestSha256": "7a46ac83001411a29b1bc4be7e0f91f09c5879967386c452b2620e23d16e4614",
 "nRestarts": "0",
 "pid": 3411,
 "releaseSha": "817a83e44cec8965479fd97fc30b7a0b3ae49ab2",
 "runtimeIncarnation": "ed35e343bc9f4ec687f753ed7b3a53b2",
 "schema": "BrokerDevCurrentIncarnationBaselineCandidateV1",
 "sharedLibraries": [
  {"deleted": false, "diskInode": 265208, "inode": 265208, "path": "/opt/lilith-memory-broker/releases/817a83e44cec8965479fd97fc30b7a0b3ae49ab2/venv/lib/python3.12/site-packages/_cffi_backend.cpython-312-x86_64-linux-gnu.so", "sha256": "9bc1d08072255a5ec2db10fc75df1dd9e73097a75cd9150cfe875ebd6712f17c"},
  {"deleted": false, "diskInode": 265298, "inode": 265298, "path": "/opt/lilith-memory-broker/releases/817a83e44cec8965479fd97fc30b7a0b3ae49ab2/venv/lib/python3.12/site-packages/cryptography/hazmat/bindings/_rust.abi3.so", "sha256": "d256d770983ec651ec1e48f5fdf8cf82dc17366064d83d651fb724814907dc12"},
  {"deleted": false, "diskInode": 8192, "inode": 8192, "path": "/usr/bin/python3.12", "sha256": "e50d468e8b0adfb05733f5b87b3cff34829c4a8c1aea50c865aa8bdfe4bb150f"},
  {"deleted": false, "diskInode": 5137, "inode": 5137, "path": "/usr/lib/locale/C.utf8/LC_CTYPE", "sha256": "59015993b1b671273461ef1167d7a9ad76dc090d521c91102e962217ed6b6dba"},
  {"deleted": false, "diskInode": 82968, "inode": 82968, "path": "/usr/lib/locale/locale-archive", "sha256": "7a31de159ded19d74c73126489d3f714c1684d5b9262cddae10bbe4fd8581a2b"},
  {"deleted": false, "diskInode": 5292, "inode": 5292, "path": "/usr/lib/python3.12/lib-dynload/_bz2.cpython-312-x86_64-linux-gnu.so", "sha256": "eff8df23cdc54d38ce9ca600d07c21ccfd7f22bd52a0720e599e6828d3e2eb76"},
  {"deleted": false, "diskInode": 8261, "inode": 8261, "path": "/usr/lib/python3.12/lib-dynload/_hashlib.cpython-312-x86_64-linux-gnu.so", "sha256": "8dc6cda6dd9495b95a2bfb5b26e8cf06b72f36dc0213d958b9277a958287f0fe"},
  {"deleted": false, "diskInode": 5307, "inode": 5307, "path": "/usr/lib/python3.12/lib-dynload/_json.cpython-312-x86_64-linux-gnu.so", "sha256": "ca8e35c58f7bc8e27258c4af43651c941413bc6318903621253485b0395758a3"},
  {"deleted": false, "diskInode": 5309, "inode": 5309, "path": "/usr/lib/python3.12/lib-dynload/_lzma.cpython-312-x86_64-linux-gnu.so", "sha256": "cb298120e40f064dc047e638d911f8b3b0abf625bf1d6bd07902b46efd820fd7"},
  {"deleted": false, "diskInode": 5313, "inode": 5313, "path": "/usr/lib/python3.12/lib-dynload/_queue.cpython-312-x86_64-linux-gnu.so", "sha256": "6e253343c58e3d83d5aca52e85dcad640d6e332d48dc4ff9bd55fcfd8be55d2b"},
  {"deleted": false, "diskInode": 5314, "inode": 5314, "path": "/usr/lib/python3.12/lib-dynload/_sqlite3.cpython-312-x86_64-linux-gnu.so", "sha256": "ecf54958b24c533f5c8dc67ca82cdce236aeb322864140bfe93eb8a69b729f4d"},
  {"deleted": false, "diskInode": 33202, "inode": 33202, "path": "/usr/lib/x86_64-linux-gnu/gconv/gconv-modules.cache", "sha256": "52c227df9d53248238602c1ddaccd2c8ddc4cc6a61aa45d7c425af590b8806a5"},
  {"deleted": false, "diskInode": 33210, "inode": 33210, "path": "/usr/lib/x86_64-linux-gnu/ld-linux-x86-64.so.2", "sha256": "c20a2dc8917c755f02b94049356320fe1f62ac7d9f8994731f807d9df39302da"},
  {"deleted": false, "diskInode": 7825, "inode": 7825, "path": "/usr/lib/x86_64-linux-gnu/libbz2.so.1.0.4", "sha256": "cc08c9f50a8009ffd6391e0116a100369b11ca9238fa52392c019e6645b122a1"},
  {"deleted": false, "diskInode": 33213, "inode": 33213, "path": "/usr/lib/x86_64-linux-gnu/libc.so.6", "sha256": "3a15d66867d83762c7f2f1e37359cb8f6c5743edb369c65285cb0b1c4f7498bf"},
  {"deleted": false, "diskInode": 5987, "inode": 5987, "path": "/usr/lib/x86_64-linux-gnu/libcrypto.so.3", "sha256": "6866ed711dab8927e1bf82bf1cd30e828bdfc34f3cc1e83b1c9eb01ce6c37d9a"},
  {"deleted": false, "diskInode": 33215, "inode": 33215, "path": "/usr/lib/x86_64-linux-gnu/libdl.so.2", "sha256": "c2994527172cc23b7fb0f7d611b71e00a37da27af12c2e5e9e0dc1a742886c96"},
  {"deleted": false, "diskInode": 5905, "inode": 5905, "path": "/usr/lib/x86_64-linux-gnu/libexpat.so.1.9.1", "sha256": "286682ecbc5e59a638963b1a4e6351e65eb32fcf4bdcb9cb7569b6a61fe06a8d"},
  {"deleted": false, "diskInode": 6451, "inode": 6451, "path": "/usr/lib/x86_64-linux-gnu/libgcc_s.so.1", "sha256": "d93224d2b0dab4247598be683adca02f5cf00586f99c187579cd7e92058fb7cb"},
  {"deleted": false, "diskInode": 5098, "inode": 5098, "path": "/usr/lib/x86_64-linux-gnu/liblzma.so.5.4.5", "sha256": "696e868dd0700a19a6d65fc01608ec2d70d3cb91f65710e89180cd2e688f30cb"},
  {"deleted": false, "diskInode": 33216, "inode": 33216, "path": "/usr/lib/x86_64-linux-gnu/libm.so.6", "sha256": "fce00b6f25f459cf4ae0b7fae4257909a1a8a86f9149e7c029a5d617baf1ccd0"},
  {"deleted": false, "diskInode": 33225, "inode": 33225, "path": "/usr/lib/x86_64-linux-gnu/libpthread.so.0", "sha256": "90491a21ce44efcf3bd4b65ec82501c091d7ebe7f8d9b341dd01d721001d9ecd"},
  {"deleted": false, "diskInode": 33227, "inode": 33227, "path": "/usr/lib/x86_64-linux-gnu/librt.so.1", "sha256": "6d072187d88e092e81561a44c03a4a41397319022c6d43519757cc051c576d82"},
  {"deleted": false, "diskInode": 2213, "inode": 2213, "path": "/usr/lib/x86_64-linux-gnu/libsqlite3.so.0.8.6", "sha256": "85265a9d4afca6f4b325ceb078b669c754fb881abed4cafe91ccebe9d625d975"},
  {"deleted": false, "diskInode": 1876, "inode": 1876, "path": "/usr/lib/x86_64-linux-gnu/libz.so.1.3", "sha256": "86200da370f20476a2507e9097a789b5ef97269b4ca8d5e164ad82dab9d99892"}
 ],
 "sharedLibrariesSha256": "818994544397da37d5a97e3799afff314608a7aa00cad50c968a90b86f41ce60",
 "startTicks": 125335,
 "startTime": "2026-10-09T09:52:33Z"
}
```
