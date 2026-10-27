# Track B B2 (witness K-PAN anchor) + K-PCK DEV_SYNTHETIC keygen: result (2026-10-25)

**Owner approvals (2026-10-25):** Decision 1 (B2: local witness implementation, no install) and Decision 2 (the K-PCK DEV_SYNTHETIC keygen in WSL, as worded in TRACKB-B1-RESULT.md).

**Verdict: `TRACK_B_B2_SOURCE_READY`.**
- B2 source is complete and tested locally.
- K-PCK exists in owner custody.
- The next step (B3 K-PAN ceremony + B4 authority-dev release) is governed and needs separate approval.

**Constraints held:** no DEV, PROD or GCP contact; no install, commit or push.

## Decision 2: K-PCK generated (off-host, owner custody)

**Tool:** run from patch `7483e76a…a387` as approved. Staged in WSL `/root/lilith-privacy-kpck-tool-7483e76a`; hashes verified before use:

| File | sha256 |
|---|---|
| tool | `06f42fda…c88e` |
| contracts | `58e954af…d768` |
| `lilith_memory/__init__` | `2bbebd95…7e21` |

**Command:** `keygen --custody /root/lilith-privacy-kpck-dev-synthetic-01 --environment DEV_SYNTHETIC --key-id kpck.dev-synthetic.01` → `KPCK_GENERATED`, rc 0.

**Custody** (WSL Ubuntu-24.04, root):

| Path | Mode | Notes |
|---|---|---|
| custody dir | `root:root 0700` | |
| `kpck.key` | `0600` | 32 bytes; content never printed or copied |
| `kpck.pin.json` | `0600` | 0600 not 0644, because the run used umask 077; stricter and harmless for a public file |
| `checkpoints.jsonl` | | empty |

`show`: 0 checkpoints, 0 alarms.

**Public pin** (the only thing copied out): `trackb/kpck/kpck.dev-synthetic.01.pin.json`.
- sha256 `1b7b8cfad00ee4671d5576141eee7fd3f2dcbf03f0a8f74e7e966eca335d71f6`;
- public key `a5eba312723b4458edae39cb8a73ffa0ebbd246f3a0b2d0c6a1198b0b72a7b9b`.

**Not done (owner's own step, allowed by the authorization):** one offline backup copy of the custody directory to a separate owner location. Until it is made, the key exists in exactly one place.

## Decision 1: B2 witness source (worktree `lilith-os-trackb`, uncommitted)

**New `lilith_recovery_witness/privacy_anchor.py`:**
- protocol id `LILITH_PRIVACY_ANCHOR_DEV` (RFC 8785 frames, 64 KiB);
- operations `READ_PRIVACY_ANCHOR {fromVersion}`, `GENESIS_PRIVACY_ANCHOR {entries, expectedSetHead}` and `ADVANCE_PRIVACY_ANCHOR {previousAnchorDigest, entries, expectedSetHead}`;
- the witness's own clock;
- pin before signing; strict extension only (the pure contract);
- durable store: `staging/<v>` O_EXCL + fsync → `link` into `chain/<v>` (never overwrites) → dir fsync = commit;
- the whole chain is re-verified on every call; any damage → `ANCHOR_STORE_FAIL_CLOSED`, never repaired.

**`credential.py`:** + `PrivacyAnchorSigningKeyV1`:
- loads only `privacy-anchor-signing-key`, with key id `kpan.dev-synthetic.01` (K-WIT ids refused);
- signs only a `PrivacyAnchorV1` body that re-verifies as the next version of the given stored chain;
- not serializable or copyable;
- `load_privacy_anchor_key` refuses key material equal to K-WIT.

The K-WIT class and loader are unchanged.

**`server.py`:**
- on the OWNER socket only, frames with the anchor protocol id go to `PrivacyAnchorServiceV1`;
- every other frame, and every signer-socket frame, still goes through the unchanged `protocol.py` (which refuses that id);
- an absent or invalid K-PAN gives `ANCHOR_KEY_ABSENT` for anchor operations only, so the V2 service is unaffected.

**Deploy assets (not installed):**
- service unit: `+ LoadCredentialEncrypted=privacy-anchor-signing-key:/etc/lilith-recovery-witness/credentials/lilith-recovery-witness.privacy-anchor.cred`;
- service unit: `ReadWritePaths` adds `/var/lib/lilith-privacy-anchor`;
- tmpfiles: `+ d /var/lib/lilith-privacy-anchor 0700 lilith-recovery-witness lilith-recovery-witness -`.

**Release set:** `witness_release_file_set` gains `privacy_anchor.py` and `test_privacy_anchor.py`. The README text is updated; `__init__.py` is left byte-identical, to keep the release-member delta minimal.

**Existing witness tests:** 4 PR-1S invariants are updated to their new exact values; nothing is relaxed:
- exactly 2 credentials;
- exactly the 2 writable paths;
- the exact 2-line tmpfiles;
- exactly 2 `.sign(` calls, each bound to its own domain.

`privacy_anchor.py` is added to the no-bind / no-generic-signing scan.

### Narrow deviation from Rev 1 §3 (concrete blocker)

**Blocker:** Rev 1 placed the anchor state "under the existing `/var/lib/lilith-recovery-witness`". The pinned `witness_readiness` (SHARED_HASHES `129d4479`, byte-identical by Rev 1's own rule) admits only `chain/`, `authorizations/`, `witness.json`, its scratch file and `witness.lock`. Any other entry → `UNEXPECTED_ENTRY` → `FAIL_CLOSED`, so the witness would refuse to start (`EXIT_STORE_FAIL_CLOSED`). This is proven by `test_anchor_state_must_never_enter_the_recovery_witness_store`.

**Fix:** a separate witness-owned directory `/var/lib/lilith-privacy-anchor` (one `ReadWritePaths` path + one tmpfiles line). Everything else in Rev 1 is unchanged.

### Byte-identity (Rev 1 compatibility check 1)

**UNCHANGED vs origin/main:**
- witness `protocol.py`, `core.py`, `writer.py`, `storage.py`, `profile.py`;
- all of `services/authority-dev` (incl. `release_file_set.py`), `services/memory-broker`, `owner-memory-control/lilith_owner_memory` and `lilith_authority_signer`;
- `canonical_contracts.py`, `owner_proof.py`, `lilith_memory/__init__.py`.

All 15 existing SHARED_HASHES pins still match their files.

## Tests

**Witness suite, Linux (WSL, `PYTHONPATH=/root/l1deps`):** **59/59 OK, 0 skips** (44 existing + 15 new). That includes:
- `systemd-analyze verify` of the changed unit;
- real flock / dir-fd link / fsync seams;
- the crash at every commit seam: uncommitted before the link, committed after it, and the retry succeeds and clears staging;
- refusals that commit nothing: pin mismatch, stale head, re-append, empty advance, second genesis, absent key;
- a damaged, gapped or foreign-key chain → fail closed with the file untouched;
- lock held / state dir missing;
- owner-only routing: signer-socket and wrong-peer anchor frames get no reply, and the V2 path is unchanged;
- end to end: witness genesis → K-PCK checkpoint + unlock → root `apply_unlock` → Core API gate READY; a new suppression row → `ANCHOR_BEHIND`; witness advance + next checkpoint → READY.

**Rev 1 checks 3 and 4:**
- 3: the anchor id is refused (`UNSUPPORTED_VERSION`) by the unchanged `protocol.py` on both sockets, i.e. also by any old witness binary;
- 4: K-WIT cannot sign an anchor body, K-PAN cannot sign a V2 body, and a K-WIT key object is refused as K-PAN.

**Witness suite, Windows:** 59 OK (14 POSIX skips), stable 10/10 after adding `O_BINARY` to the new loader. A Windows-only text-mode read corrupted ~1 in 3 random DER keys; the pre-existing K-WIT loader is unchanged (Linux-only runtime).

**Core API (Windows):** 316 OK (unchanged by B2).

**authority-dev (WSL, with `docs/`):**

| Tree | Result |
|---|---|
| origin/main | **241/241 OK** |
| Track B as is | 2 FAIL + 43 ERROR, ALL one cause: `install_authority_dev.RUNTIME_PATHS` / `RELEASE_FILE_SET_MISMATCH` (the one-release archive path set now includes `lilith_recovery_witness/privacy_anchor.py`) |
| Track B + simulated B4 (WSL copy only) | **241/241 OK**, failure set identical to main |

The simulated B4 adds `privacy_anchor.py` and `lilith_memory/privacy_anchor_contracts.py` to `RUNTIME_PATHS` and `privacy_anchor_contracts.py` (sha `58e954af…`) to `SHARED_HASHES`. So the only remaining delta is exactly the governed B4 pin additions.

**OMC (WSL, with `docs/`):**
- **origin/main:** **2114/2114 OK**.
- **Track B (B1+B2):** 2120 tests (+6 new tool tests, all OK). 142 failures, in exactly three release-pin categories. All are consequences of changing the authority-dev/witness release payload, i.e. B4 release-program work:

  | Count | Category | Fixed in B4 by |
  |---|---|---|
  | 123 | `RELEASE_FILE_SET_MISMATCH`: `install_authority_dev.RUNTIME_PATHS`, used by every M-B operator package fixture | the B4 installer path addition |
  | 14 | `WRB_UNIT_NOT_EXACT`: the E-19 witness-restart-boundary tool pins the exact accepted witness unit bytes | a new unit pin in the restart-boundary install |
  | 5 | release-member pins of the installed release (E-19 maintenance `f46ebfce` → new, E-22 judge transition, M-B6 package / readiness probe) | new release records |

- **Track B + simulated B4 (installer and SHARED_HASHES edit only):** the `RELEASE_FILE_SET_MISMATCH` errors are replaced by `TOOL_PIN_MISMATCH:…install_authority_dev.py`, because the M-B / E-19 / E-22 operator tools pin the installer's own bytes. The WRB unit pin and the release-member pins remain. All of these are release-record re-pins (B4 work) and were NOT simulated. So OMC green requires the full B4 record update, not only the two path additions.

**Merge consequence:** B2 cannot merge on its own. Main CI runs OMC and authority-dev, so B2 must land together with B4 as one governed release change. B1 (Core API + owner tool) has no such coupling and could merge alone.

**Mutations (B2, Linux):** **8/8 caught** (`mutate_b2.py`): anchor served on any socket; stale previous digest; owner pin ignored; signer skips the extension re-verify; stored chain not verified; K-PAN equal to K-WIT; chain gap tolerated; second genesis.
- The gap mutation first survived, because the chain verifier already caught my test's junk file. The test was strengthened with a valid-but-misnamed chain file.
- B1 mutations stay 10/10.

## Artifacts

| Artifact | sha256 |
|---|---|
| `trackb-b2-witness.patch` (9 files) | `5967295551524cd4c74d29e38ed853543bfd79ce6687d16f999f6e0cda2640aa` |
| `trackb-b1b2-cumulative.patch` | `830e650051e2a950057d57c3335602c27cce84839b4fed306ae7f8157669c1eb` |

- The B1 part of the tree is still byte-identical to the approved `7483e76a…`.
- Harnesses: `mutate_b2.py`, `wsl-b4sim.sh`.

## Not done (governed, needs approval)

- **B3 K-PAN ceremony:**
  - generate K-PAN as an Ed25519 PKCS#8 DER on DEV, as an encrypted systemd credential `lilith-recovery-witness.privacy-anchor.cred` under `/etc/lilith-recovery-witness/credentials/`;
  - publish its public pin (`kpan.dev-synthetic.01`);
  - the K-PCK holder pins it.
- **B4 authority-dev release program:**
  - the `RUNTIME_PATHS` + `SHARED_HASHES` additions shown above;
  - a new candidate and build attestation;
  - the install ladder: the K-PAN blob BEFORE the new unit, otherwise `LoadCredentialEncrypted` fails the witness start;
  - DR-5 EQUAL;
  - observation delta: the new blob + the witness unit/tmpfiles hash;
  - a witness restart that preserves the broker and authority (check 6);
  - recorded transcripts byte-identical (check 2).
- **B5 (f9c3 package), B6 genesis + whole-host rollback rehearsal, R-8 K-PAN rotation/compromise:** unchanged from TRACKB-B1-RESULT.md.
