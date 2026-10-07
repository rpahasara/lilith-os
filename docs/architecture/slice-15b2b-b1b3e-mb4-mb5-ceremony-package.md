# Slice 15B2b-B1b-3e — M-B4/M-B5 `INSTALL_TRUST_AND_REGISTRY`: Ceremony Package and Runbook

Status:

- **REVIEWED CEREMONY PACKAGE (SOURCE AND DESIGN), 2026-10-07.** It
  implements the accepted
  [continuity decision](slice-15b2b-b1b3e-mb4-mb5-continuity-owner-decision.md)
  (`MB4_MB5_CONTINUITY = OWNER_ATTENDED_EVENT_BOUNDED_SINGLE_SEQUENCE_TWO_GO`)
  and the [installable-representation decision](slice-15b2b-b1b3e-mb4-mb5-installable-representation-owner-decision.md).
  It uses the [remediation](slice-15b2b-b1b3e-mb4-mb5-trust-install-remediation.md)
  tooling.
- `MB4_MB5_PACKAGE_SOURCE_AND_DESIGN_READY_FOR_REVIEW`.
- **Nothing here authorizes anything.** Each of these needs its own explicit
  owner authorization: the preparation sequence (§4), the transfer (§6), the
  M-B4 go (§7), the M-B5 go (§9), the removal (§11), and acceptance (§10).
  - M-B4, M-B5 and `INSTALL_TRUST_AND_REGISTRY` remain **NOT AUTHORIZED**.
  - Genesis, record 1, First Memory and PROD remain **NOT AUTHORIZED**.
  - `FRESHNESS=UNKNOWN`.
- Repository-only: no DEV, S25 or GCP contact; no K-ROOT or K-WIT private
  material accessed.

```text
package reviewed != sequence authorized != evidence fresh != M-B4 go != M-B4 != W3 != HARD STOP
  != continuity check != M-B5 go != M-B5 != W5 VERIFIED != TRUST_INSTALLED accepted
tool / flag / marker / go-file check != authorization
one go = exactly one installer invocation; no retry
```

## 1. Control and pinned tools

**Control rule.** The ceremony runs from a clean checkout of a merged
`main` commit that contains this record. Every tool below must hash to its
pin there. `mb4_mb5_operator.py pins <repo>` checks this, and the operator
re-checks each tool before streaming it (`git show HEAD:<path>`). Any
mismatch is `STOP TOOL_PIN_MISMATCH`. There is no bundle: the pins are the
exact file bytes, so they do not change on merge.

| Tool (repository path) | Where it runs | SHA-256 |
| --- | --- | --- |
| `services/owner-memory-control/tools/mb4_mb5_operator.py` | owner laptop (the operator; it builds every remote command) | `e380ab1852ba72fe511c650446867c8d229d95776af3c1d4266fa949c0a9de1a` |
| `services/owner-memory-control/tools/mb4_mb5_installable_inputs.py` | owner laptop, WSL (pinned wheels) | `dbe94a2d3a38fa838d4fd7eeb9016274c85c684221ddb770e8e993cc15b18d61` |
| `services/owner-memory-control/tools/mb3_registry_ceremony.py` (library of the derivation) | owner laptop, WSL | `c77b651ca2ae9d5f6c5526f958469a01c0d42e6ebdf189fc206ac2132af61320` |
| `services/owner-memory-control/tools/verify_mb3_registry.py` | owner laptop, WSL (export re-verification) | `e710cfa623d494e243ab4a1fbaefe28e8d079e58398368f9dcabd645e06b5507` |
| `services/authority-dev/ceremony/install_authority_dev.py` | DEV, root, `/usr/bin/python3 -I -B -` (streamed) | `fe10d9a37c53d4a32ca49d79ee5987c6546866feeebcee3c882087f51ed55487` |
| `services/owner-memory-control/tools/mb4_mb5_trust_install_verifier.py` | DEV, root, `/opt/lilith-authority-dev/current/venv/bin/python -I -B -` (streamed) | `78f57c01811e20a03ebb06bc114847bad440c7435e85ceb0249a488c659b2361` |
| `services/owner-memory-control/tools/mb4_mb5_remove_before_mb6.py` | DEV, root, `/usr/bin/python3 -I -B -` (streamed; §11 only) | `db0629a6a5f39ca65e23010aeeccc565978b7d8990f38d6b8bb6c361046ee104` |
| `services/authority-dev/ceremony/observe_authority_dev_host.py` | DEV, root (streamed) | `a2f21b45e57a153f099c79a734ab05a575ac5c50f7cbc0527e562e94dd6908bf` |
| `scripts/verify_broker_dev_current_incarnation.py` | DEV, root (streamed) | `2e68160971a3b0dd05ffcb6cdc464fc612afb2b522a57fb534b25c6af83c10ba` |
| `scripts/authority_custody_denial_proof.py` (with the new `P1B-5` phase, §14) | DEV, root (streamed) | `f4e39c81c24a01be5702f6a65a581fcd08f97e1c5ad4a07326883b605fef1455` |
| `services/owner-memory-control/lilith_owner_memory/owner_freshness_tool.py` (Replica A read) | owner laptop | `fd7abe2aa5e5efae41b87553efe8fe8058b437748accf866c2fa5ee71c8a7c27` |
| `scripts/deployer_authority_boundary_proof.sh` (DR-5; runs in the deploy workflow, not by the owner) | DEV, routine deployer | `9b569f9bee8f07f0bf13ec1d20e2607d9e01c601a2e94a2988320e5bc4160f43` (unchanged; §14) |

The authority release on DEV stays `aee323e94412accbe321bc84eae78c5b8cf95afc`.
Its modules are pinned in §5.3.

**Hash-gated streaming.** Every DEV tool is sent gzip + base64 inside the
`gcloud compute ssh --command`, exactly as the PR-1A / M-B2 / M-B3 ceremonies
did, with one added gate. The host decodes the blob, hashes it, and runs it
only on an exact pin match:

```text
B=<blob>; printf %s "$B" | base64 -d | gunzip | sha256sum | cut -c1-64 | grep -qx '<pin>' || exit 96; printf %s "$B" | base64 -d | gunzip | sudo -n <interpreter> -I -B - <args>
```

Every remote command is also prefixed with
`test "$(hostname)" = lilith-dev-01 || exit 97;`. Exit 96 or 97 is a STOP.
Nothing is copied to the host except the four staged files (§6), and no
bytecode is written.

## 2. Roles

| Role | Principal / place |
| --- | --- |
| owner | attends every step; gives each go and decision verbatim |
| operator | owner laptop. Windows Git Bash for `gcloud` (bundled-python recipe via `LILITH_MB4_MB5_GCLOUD`); WSL Ubuntu with the pinned wheels for `derive` |
| DEV contact | OS Login `ravindupahasara2_gmail_com` over `gcloud compute ssh lilith-dev-01 --tunnel-through-iap`, with the existing `sudo` for the streamed tools |
| S25 | owner-run only, local Termux, screen-only; no SSH, `sshd`, ADB or automation. Used for the Replica B read and the E-21 confirmation |

## 3. Validity (continuity C-8, C-13, C-14, C-15)

- **Events and the sequence bound validity, not a clock.** No TTL exists.
- **No replay.** Evidence from any earlier sequence counts for nothing. That
  includes M-B2, M-B3, the preflight and this package's derivation
  transcript.
- **Terminators.** Each of the following ends the sequence's usability
  (REVALIDATE). A new sequence and a fresh re-proof are then required:
  - **T-1** a new DEV deployment run starts or queues after the DR-5 freeze;
  - **T-2** the boot ID or hostname / machine-id changes, or a reboot
    becomes pending;
  - **T-3** broker preservation is other than PASS;
  - **T-4** K-ACT CURRENT or K-WIT custody facts change;
  - **T-5** the installer status or the verifier phase differs from the
    expected checkpoint;
  - **T-6** a cloud / IAM / topology difference from the accepted capture
    set, or an Admin Activity entry other than `iam.serviceAccounts.actAs`;
  - **T-7** `origin/main` moves, or any tool pin mismatches;
  - **T-8** a replica changes, or the owner register is not `KNOWN_EMPTY`;
  - **T-9** any custody-device event (G-9): phone or laptop compromise or
    rollback, ADB / SSH / automation on Termux;
  - **T-10** the sequence is paused, interrupted or uncertain (C-8);
  - **T-11** any B-5 §9 stop condition or G-1 … G-9 invalidator.
- **Unknown fails closed.** If it is unknown whether an event is a
  terminator, the sequence is unusable until the owner records a
  determination.

## 4. Fresh preparation and re-proof (one owner-authorized sequence)

The preparation sequence needs a **separate explicit owner authorization**
(template in §12.1). It writes nothing to DEV except the staging directory
in the operator home (§6). Every item below is collected **inside** the
sequence.

| # | Evidence | How (operator form or command) | PASS means |
| --- | --- | --- | --- |
| E-1 | exact repository control | `pins <repo>` on a clean checkout | `origin/main` = HEAD = the control commit; every §1 pin exact |
| E-2 | DEV deployment relationship | GitHub run list (read-only) | the latest DEV deploy run is the control commit or an ancestor classified in §13; nothing later |
| E-3 | no pending / running deploy | GitHub run list (read-only) | no deploy run queued or in progress; **deployment freeze declared** from the E-14 DR-5 point until §10 / §11 ends |
| E-4 | machine-id and hostname | `host … W0` → `identity.out` | `ae929170e6fa4c8ab9cc7b9547238d9d`, `lilith-dev-01` |
| E-5 | boot identity | `identity.out` | equal to the last accepted boot (`eea461c3…` at M-B3). A different boot is T-2: the existing reboot re-baseline procedure and an owner acceptance are required first, outside this sequence |
| E-6 | no reboot pending | `identity.out` | `REBOOT_REQUIRED=absent` |
| E-7 | broker incarnation preservation | `host` → `preservation.*` | `verify_broker_dev_current_incarnation.py preservation` PASS against the pinned accepted incarnation (`c4b9cb38…` / `a30bd7d6…` at M-B3, or a later owner-accepted re-pin) |
| E-8 | K-ACT CURRENT | `host` → `custody.out` | credstore has exactly one entry; the blob is `root:root 0600`, SHA-256 `6a61c350e848a833868f4573982fca9c75e2af79ccc9bd3716ae0303c26973f3`, inode and times as last accepted; the K-ACT publication `/root/b1b3d-l2b-publication.json` hashes to `d76479762007afef828f3901591647dc4a2fb2205f4afac527b66d2cc9c6b032` (re-read now, not reused) |
| E-9 | K-WIT preservation | `custody.out` | `credentials/` lists only the K-WIT blob, `root:root 0600`, SHA-256 `f87593701ee5e9272363a473a115b87cc06179df3c0b233af4aa62bb5b9b97be` (ciphertext; never decrypted), inode and times as last accepted |
| E-10 | P1B-2 starting state | `host … W0` → `status.*`, `verifier.*` | `install_authority_dev.py status --expect P1B-2 aee323e…` PASS; verifier `expect W0_PRE_INSTALL` exit 0; trust / registry / owner directories empty; `LATER_STATE … ABSENT` ×2; units inactive, not enabled; activation `GRANT_ABSENT` |
| E-11 | release / DEV readiness | `readiness.*` (§5.3) | `MB4_MB5_HOST_W0_PASS` with `readinessExact=true` |
| E-12 | exposure / network / IAM / topology | `cloud <dir> <since>` | the 11 JSON captures and the bucket list are byte-identical to the last accepted capture set; the Admin Activity since `<since>` holds only `iam.serviceAccounts.actAs` (owner IAP sessions; the deployer during reviewed deploys). `<since>` is the end of the last accepted window |
| E-13 | no G-1 … G-9 invalidator | owner review of E-1 … E-12, E-16 … E-18 | none observed; unknown classification = REVALIDATE |
| E-14 | fresh non-vacuous DR-5 | §14.1 | every DEV deploy run since the last accepted comparison is equal to the accepted run on all three digests |
| E-15 | B-5 stop conditions absent | owner review against the [current grant](slice-15b2b-b1b3e-b5-pr1b-authorization-current-grant.md) §7 | no §9 stop; grant not void |
| E-16 | owner register `KNOWN_EMPTY` | the owner's determination from E-17 + E-18, as at M-B2 (Replica B stays on the S25; it is never copied to the laptop) | both replicas at their canonical paths, byte-continuous with the accepted baselines, zero records: `KNOWN_EMPTY` (the sequencer's `OWNER_REGISTER_EMPTY`); anything else blocks (`REQUIRED_UNKNOWN_BLOCK`) |
| E-17 | Replica A read | `owner_freshness_tool verify-replica` on Replica A (laptop) | 0 records; manifest `fbdd045c…`, entries and inodes equal to the accepted baseline |
| E-18 | owner-run S25 Replica B read | owner, local Termux, screen-only block | canonical path, not nested; manifest `c068e533…`; 0 records; inodes as accepted; settings OFF; owner custody attestation |
| E-19 | accepted Registry V1 custody | owner laptop, WSL: re-hash the export; `verify_mb3_registry.py` with the M-B3 go pins | export `c4ea3d66…64d8`; `MB3_LAPTOP_VERIFIED`; signed transport `3f0a59c0…6156` inside it |
| E-20 | accepted E-21 confirmation | owner, S25 screen (B-4 §2) and laptop | the public fingerprint read on the phone equals `cb36daf176d813359b8bd0fe6361f549fd3334a52d0cd1f85cc5247cb26592cf`, equals the derived root anchor's key hash (§5); no K-ROOT file is opened |
| E-21 | derived installable artifact pins | `derive <repo> <export.tar> <workdir>` (§5) | `MB4_MB5_DERIVED_PINNED`, exactly the three pins of §5.1 |
| E-22 | staged copies on DEV | `stage <workdir>` (§6) | `MB4_MB5_STAGED_FILES_PINNED_ON_HOST` |

**Order inside the sequence:**

1. E-1 … E-3 and the DR-5 freeze (E-14).
2. E-19 … E-21 (off-host).
3. E-16 … E-18.
4. `host … W0` (E-4 … E-11).
5. `cloud` (E-12).
6. E-13, E-15.
7. Transfer (§6, its own authorization).
8. A final closing gate (§7.1).
9. **STOP and wait for the owner.**

The sequence authorization is not the M-B4 go.

## 5. Off-host derivation and independent re-hash

### 5.1 The three installable artifacts (owner-accepted pins)

| File | SHA-256 | Install target |
| --- | --- | --- |
| `registry-root.json` | `bc5f00a76b518c4f11b6804d35844c036db75eaa730d56c35f97f430558ff687` | `/etc/lilith-authority-dev/trust/registry-root.json` (M-B4) |
| `witness-anchor.json` | `be360da2324880d725aea509bb0f41500f51ecfc3c2995dd3057824bb471ab5a` | `/etc/lilith-authority-dev/trust/witness-anchor.json` (M-B4) |
| `authority-registry.v1.json` | `46b0bfc558ec3a19467206ada3dc53c18e8a6a4cd0782711b4800cfe099f8b1e` | `/etc/lilith-authority-dev/registry/authority-registry.v1.json` (M-B5) |

Identities unchanged:
- Registry V1 digest `fa66272131a3ef076036616b07766a377de4fdc1e4fef4cb8a054726f05c14fc`;
- signed transport `3f0a59c0a104934730184d28bc16e1c9215bdaa6ec1f9d94753722862f486156`;
- export `c4ea3d66fdef3f6b30c63a1f7f4903a3d2d5427f0419c6e1bd7aadd12c9564d8`;
- E-21 `cb36daf1…92cf`;
- K-WIT `5d778701…0bdf`.

### 5.2 Transformation (export never modified)

`mb4_mb5_operator.py derive <repo> <export.tar> <workdir>` runs in WSL with
the pinned wheels. It does the following:

1. Checks that `mb4_mb5_installable_inputs.py` and `mb3_registry_ceremony.py`
   in `<repo>` hash to their pins.
2. Checks that the export hashes to `c4ea3d66…64d8`.
3. Runs the governed derivation **twice** from the export's five pinned
   members (`read_export` → `derive_from_members`), without extracting the
   tar, and requires byte-equal results.
4. Requires the result to equal the three accepted pins (`check_pins`).
5. Writes the files with `O_EXCL` into a **new** `<workdir>/derived/files`
   (`0700`).
6. **Independently re-hashes** them by reading the written files back.
7. Writes `SHA256SUMS`. It contains exactly the three lines
   `<pin>  <name>`, in the §5.1 order.
8. Re-hashes the export and requires it to be unchanged.

The owner-held export is only read. The operator's own copy for this step
is a separate file copied from the owner's evidence set; the original is
never opened for writing.

### 5.3 Release / DEV readiness check (read-only; inside `host`)

| Check | Exact command (DEV) | Expected |
| --- | --- | --- |
| R-1 selected release | `readlink /opt/lilith-authority-dev/current` | `releases/aee323e94412accbe321bc84eae78c5b8cf95afc` |
| R-2 release interpreter | `sudo -n test -x /opt/lilith-authority-dev/current/venv/bin/python` | `RELEASE_PYTHON=executable` |
| R-3 modules | `sudo -n …/venv/bin/python -I -B -c "<READINESS_PROBE>"` (the fixed string in `mb4_mb5_operator.py`) | it imports exactly what the verifier imports, plus `rfc8785` and `cryptography`. Every loaded `lilith_*` file is inside the release tree and hashes to the table below; nothing else is loaded. It reads files only |
| R-4 tool hashes | the hash gate (§1) on every streamed tool | each streamed tool is decoded on the host and equals its pin before it runs |
| R-5 release tree | `status --expect P1B-2 aee323e…` | PASS (the installer's own tree, unit and CLI contract) |

**R-3 module pins** (equal to `aee323e` and to `release_file_set.SHARED_HASHES`):

| Release file | SHA-256 |
| --- | --- |
| `lilith_authority_host/__init__.py` | `27a314ec79fc0083f18eb70be215de10b9dc6c39119be505c5cfa690cbb7ac3a` |
| `lilith_authority_host/inputs.py` | `775d521a197372f252cd718877f74e7902b8e9f7fee79bdd843115131a0ea299` |
| `lilith_authority_host/paths.py` | `d95171b91c126da983a3ec2cc864b1875dd333b0b0d638eacf8645e93d52c55e` |
| `lilith_authority_host/store_observer.py` | `e22414fa594c5eddc139f62e2bdabe379f9e78cc78adf339ad60276990d1c27a` |
| `lilith_memory/__init__.py` | `2bbebd95846f1073a0b4e2ec3a2aa24378c56be4ecbb5470e5c1f1d359037e21` |
| `lilith_memory/canonical_contracts.py` | `f93d26d8a7e01d78d25f1f1d9540577cf2a55dfd4d52c4b64c87bef93ad887e0` |
| `lilith_memory/owner_proof.py` | `3a3eb7147d1e276ac261457a2340e045a0c43f6bc63eeb1a78bfc9864f80ac08` |
| `lilith_owner_memory/__init__.py` | `d1f1bf65a24315005ca4b597971dec6efa0212d4ab5836832e2a5a80fb9e62b4` |
| `lilith_owner_memory/contracts.py` | `ff5075f1131f84348bdbc5d3fbd3410e53c7da39e265476a0b57ace6ff8ef5c7` |
| `lilith_owner_memory/authority_contracts.py` | `fabd8fd24f45febe83f8fd67c3fc39f277278e9145df9c55d5e03e5e8598e74f` |
| `lilith_owner_memory/authority_verifier.py` | `3c808267e56e9abc1ea1e848881cefd20a56fde51d9e803ac90f7f0c7517e83a` |
| `lilith_owner_memory/recovery_contracts.py` | `f4a14cff094d167a2a7925622031352955291c18244545e95c0003fb9231b95e` |
| `lilith_owner_memory/rotation_contracts.py` | `8f9df8dcd3e8a1b0cd8f03169bf7a51d4b6726cbb708cadfb3025586211996b0` |
| `lilith_owner_memory/witness_readiness.py` | `129d4479a7c86a6ef33acfb27da4f5cd6c6a6947b89184863a50117091fe3cbd` |

The set comes from the static import closure of the verifier's imports. The
first live R-3 run is itself the check: an extra or missing module fails it.

## 6. Transport, staging and cleanup (operator home only)

The transfer needs its own explicit owner authorization (§12.2).

- **Stage.** `stage <workdir>`:
  - re-hashes the three local files against the pins;
  - on DEV, as the operator without `sudo`, creates
    `/home/ravindupahasara2_gmail_com/lilith-mb4-mb5-stage` with
    `mkdir -m 0700`. It refuses if the path exists;
  - copies exactly four files (the three artifacts and `SHA256SUMS`) with
    `gcloud compute scp --tunnel-through-iap`;
  - runs `staged_check`.
- **Host re-hash** (`staged_check`; repeated immediately before each
  installer stage):
  - `cd <stage>`;
  - the `LC_ALL=C`-sorted listing is exactly
    `SHA256SUMS authority-registry.v1.json registry-root.json witness-anchor.json`;
  - every entry is a regular file;
  - `sha256sum -c --strict SHA256SUMS` passes.

  So all three staged files are re-hashed on the host, independently of the
  laptop, before any installation.
- **The installer reads the staged files by path.** Its `_canonical_document`
  refuses a symlink, a non-regular file, a file over 64 KiB, non-ASCII,
  non-canonical bytes or `environment != dev`.
- **Cleanup.** `cleanup <workdir>`, after §10 acceptance or after any STOP
  that ends the sequence:
  - repeats `staged_check`;
  - then `rm -f` of exactly the four named files and `rmdir` of the stage
    directory, as the operator without `sudo`. No wildcard, no `rm -r`;
  - requires `STAGE_DIR_ABSENT`.

  Cleanup is not authority and changes no authority path.

## 7. M-B4 (one attempt)

### 7.1 Closing gate (immediately before the M-B4 go)

Read-only:
- `origin/main` unchanged (T-7);
- no new deploy run (T-1);
- `staged_check` PASS;
- `host … W0` re-run, with E-4 … E-11 unchanged (same boot, broker, K-ACT,
  K-WIT, P1B-2, `W0_PRE_INSTALL`, readiness);
- no terminator.

Then **STOP and wait for the owner's M-B4 go.**

### 7.2 M-B4 owner go template (exact; one attempt)

The owner gives it verbatim, in the same sequence, after §7.1. `<CONTROL>`
is the full control commit.

> I authorize M-B4 / install-anchors now for exactly one attempt within this current DEV_SYNTHETIC M-B4/M-B5 sequence.
> Continuity: MB4_MB5_CONTINUITY = OWNER_ATTENDED_EVENT_BOUNDED_SINGLE_SEQUENCE_TWO_GO.
> Control commit: `<CONTROL>`.
> Release: aee323e94412accbe321bc84eae78c5b8cf95afc.
> Installer SHA-256: fe10d9a37c53d4a32ca49d79ee5987c6546866feeebcee3c882087f51ed55487.
> registry-root.json SHA-256: bc5f00a76b518c4f11b6804d35844c036db75eaa730d56c35f97f430558ff687.
> witness-anchor.json SHA-256: be360da2324880d725aea509bb0f41500f51ecfc3c2995dd3057824bb471ab5a.
> E-21 K-ROOT fingerprint: publicKeySha256=cb36daf176d813359b8bd0fe6361f549fd3334a52d0cd1f85cc5247cb26592cf.
> K-WIT fingerprint: publicKeySha256=5d778701def439b6c896392750c12685c26b67edfc908bed1a80f02eab0d0bdf.
> I acknowledge: M-B4 closes the K-WIT burn/regenerate option. That option does not reopen merely because installed files are later removed before M-B6.
> This go does not authorize M-B5, and M-B4 success does not mean TRUST_INSTALLED.
> Any REFUSED, FAILED, unexpected output, or other STOP consumes this go and ends the sequence. There is no retry.

The operator (`mb4 <repo> <workdir> <go-file>`) does the following:

1. Refuses unless the go file holds every line above, with this control
   commit.
2. Repeats `staged_check`.
3. Writes the local one-attempt marker `attempts/mb4.json` with `O_EXCL`
   **before** invoking.
4. Runs exactly one hash-gated
   `install_authority_dev.py install-anchors aee323e… <stage>/registry-root.json <stage>/witness-anchor.json`.

A second `mb4` in the same workdir is `STOP ATTEMPT_ALREADY_CONSUMED`,
whatever the first outcome was.

## 8. M-B4 POST and content-verification checkpoint, then HARD STOP

**Run immediately:** `host <repo> <dir> W3`. It is read-only.

**Required, all of them:**

- installer exit 0, with its JSON `result=PASS` for P1B-4;
- `status --expect P1B-4 aee323e…` PASS;
- verifier `expect W3_ANCHORS_INSTALLED_REGISTRY_ABSENT`, exit 0, and its
  report has:
  - `anchorsEqualOwnerCopies=true`;
  - `witnessAnchorNamesKWit=true`;
  - `registryVerifiesOnHost=false` (no registry yet);
  - `trustInstalledCandidate=false`;
- `hostInputReasons` ⊇ `REGISTRY_STORE_MISSING`;
- E-4 … E-9 unchanged: same boot, broker PASS, K-ACT and K-WIT facts
  identical;
- the observer differs from W0 only in the trust listing / pr1Objects
  sections that the two new files explain (recorded, not compared).

**Then HARD STOP (C-5).**
- M-B4 success is **not** `TRUST_INSTALLED` (C-11) and does **not**
  authorize M-B5 (C-7).
- Any other result is a STOP. Classify the window with the verifier phase
  (§11). There is no retry.

## 9. Inter-stage continuity and the M-B5 go

### 9.1 Continuity check K-1 … K-8 (immediately before the M-B5 go; read-only)

- **K-1** the sequence was not paused, interrupted or uncertain since §8
  (C-8). If it was, M-B5 cannot continue: a fresh re-proof (all of §4)
  under a new sequence authorization is required.
- **K-2** `origin/main` and every tool pin unchanged.
- **K-3** no deploy run started or queued since the freeze.
- **K-4** `host … W3` re-run: same boot; `REBOOT_REQUIRED=absent`; broker
  preservation PASS; K-ACT and K-WIT facts identical; P1B-4 PASS; verifier
  `W3_ANCHORS_INSTALLED_REGISTRY_ABSENT`.
- **K-5** `staged_check` PASS.
- **K-6** no Admin Activity entry other than `iam.serviceAccounts.actAs`
  since E-12. That is a `cloud` re-read of the audit only; topology
  re-capture is required if anything else appears.
- **K-7** no custody-device event (T-9).
- **K-8** no other terminator.

Then **STOP and wait for the owner's M-B5 go.**

### 9.2 M-B5 owner go template (exact; one attempt)

> I authorize M-B5 / install-registry now for exactly one attempt within this current DEV_SYNTHETIC M-B4/M-B5 sequence.
> Continuity: MB4_MB5_CONTINUITY = OWNER_ATTENDED_EVENT_BOUNDED_SINGLE_SEQUENCE_TWO_GO.
> Control commit: `<CONTROL>`.
> Release: aee323e94412accbe321bc84eae78c5b8cf95afc.
> Installer SHA-256: fe10d9a37c53d4a32ca49d79ee5987c6546866feeebcee3c882087f51ed55487.
> authority-registry.v1.json SHA-256: 46b0bfc558ec3a19467206ada3dc53c18e8a6a4cd0782711b4800cfe099f8b1e.
> Registry V1 digest: fa66272131a3ef076036616b07766a377de4fdc1e4fef4cb8a054726f05c14fc.
> M-B4 POST verifier phase: W3_ANCHORS_INSTALLED_REGISTRY_ABSENT, with anchorsEqualOwnerCopies and witnessAnchorNamesKWit true.
> The inter-stage continuity check K-1 … K-8 passed in this sequence after the M-B4 POST.
> This go does not accept TRUST_INSTALLED, and does not authorize M-B6, genesis, record 1, First Memory or PROD.
> Any REFUSED, FAILED, unexpected output, or other STOP consumes this go and ends the sequence. There is no retry.

The operator (`mb5 <repo> <workdir> <go-file>`) does the following:

1. Refuses unless `attempts/mb4.json` exists in the same workdir (same
   sequence) and the go file holds every line above.
2. Repeats `staged_check`.
3. Writes `attempts/mb5.json` with `O_EXCL`.
4. Runs exactly one hash-gated
   `install_authority_dev.py install-registry aee323e… <stage>/authority-registry.v1.json`.

## 10. M-B5 POST, content verification and acceptance checkpoint

**Run immediately:** `host <repo> <dir> W5`, then `denial <repo> <dir>`.
Both are read-only.

**Required, all of them:**

- installer exit 0, with `result=PASS` for P1B-5;
- `status --expect P1B-5 aee323e…` PASS;
- verifier `expect W5_INSTALLED_CONTENT_VERIFIED`, exit 0, with
  `trustInstalledCandidate=true`, `registryEffective=false`,
  `authorityGranted=false`;
- `registryDigest = fa662721…14fc`;
- `hostInputReasons` exactly `AUTHORIZATION_REGISTER_COPY_MISSING`,
  `GENESIS_PIN_COPY_MISSING`;
- E-4 … E-9 unchanged;
- denial proof `AUTHORITY_CUSTODY_DENIAL_PROOF=PASS phase=P1B-5`.

**The three sequencer evidence items, and what proves each** (the verifier
report is the evidence; [remediation](slice-15b2b-b1b3e-mb4-mb5-trust-install-remediation.md)
§5 defines the rules):

| Evidence (`pr1b_sequencing`) | Proven by |
| --- | --- |
| `anchorsEqualOwnerCopies` | `evidence.anchorsEqualOwnerCopies=true`, plus the report's `files` SHA-256 values equal `bc5f00a7…f687` / `be360da2…ab5a`, `metadataExact=true`, and the trust listing of exactly two names. The owner compares these SHA-256 values with the §5.1 pins in the owner's own derivation transcript (E-21) |
| `witnessAnchorNamesKWit` | `evidence.witnessAnchorNamesKWit=true`: the runtime-parsed anchor has keyId `test-only.witness.dev-synthetic.b1b3d.1`, key hash `5d778701…0bdf`, environment `dev`, and is none of the authority keys |
| `registryVerifiesOnHost` | `evidence.registryVerifiesOnHost=true`: the installed bytes `46b0bfc5…8b1e`, read by the release runtime reader, have digest `fa662721…14fc` and pass `verify_authority_registry` under the **installed** E-21 anchor; the single key is K-ACT `dd13a1fb…01ed` |

**Then STOP for owner acceptance.**
- `TRUST_INSTALLED` is established only by a **separate explicit owner
  acceptance** (C-12; template §12.3) of these results.
- Acceptance does not make the registry effective, activate authority, or
  authorize M-B6, genesis, record 1, First Memory or PROD.
- After acceptance (or after any STOP that ends the sequence): `cleanup`,
  and the freeze ends.

## 11. Crash windows W0–W5 and bounded removal before M-B6

The verifier phase is the classifier. `host … W<n>` records it, and
`expect` fails on any other phase.

| Window | Phase | Handling |
| --- | --- | --- |
| W0 | `W0_PRE_INSTALL` | before M-B4. If the M-B4 go was given but the installer never started (operator STOP before invocation), the go is still consumed: a new sequence |
| W1 | `W1_ROOT_ANCHOR_INCOMPLETE` | STOP. Bounded removal only (below), then `status --expect P1B-2` and `W0`. A new attempt needs a new sequence and a new M-B4 go |
| W2 | `W2_WITNESS_ANCHOR_INCOMPLETE` | as W1 |
| W3 | `W3_ANCHORS_INSTALLED_REGISTRY_ABSENT` | M-B4 POST state. M-B5 only under §9 in the same unbroken sequence. Otherwise: leave it (M-B5 in a later sequence after a full fresh re-proof and a new M-B5 go), or bounded removal |
| W4 | `W4_REGISTRY_INCOMPLETE` | STOP. Bounded removal (all present files, back to W0). New sequence; both gos anew |
| W5 | `W5_INSTALLED_CONTENT_VERIFIED` / `…_NOT_VERIFIED` | verified: §10 acceptance. Not verified: STOP and investigate; removal only under its own authorization |
| — | `UNEXPECTED_STATE` / `OUT_OF_SCOPE_POST_LEDGER` | STOP; owner investigation. The removal tool refuses post-ledger |

**Bounded removal procedure** (needs its own explicit owner authorization,
§12.4):

1. `removal-plan <repo> <dir>` (read-only) prints the exact files (SHA-256,
   size, mode, inode) and the `planDigest`.
2. The owner reviews the plan and authorizes that digest.
3. `removal <repo> <workdir> <planDigest> <authorization-file>`:
   - refuses unless the authorization holds the §12.4 lines with that
     digest;
   - writes a one-attempt marker;
   - runs exactly one hash-gated
     `mb4_mb5_remove_before_mb6.py remove <planDigest>`, which refuses
     `PLAN_CHANGED` on any difference.
4. POST: `host … W0`, which requires `status --expect P1B-2` PASS and
   `W0_PRE_INSTALL`.

**What removal does not do:**
- it touches only the three fixed files, only pre-ledger;
- it never reopens the K-WIT burn/regenerate option (C-9);
- it never restores a consumed go.

## 12. Authorization templates (each separate; none implied by another)

**12.1 Preparation sequence.**

> I authorize one DEV_SYNTHETIC M-B4/M-B5 preparation sequence under MB4_MB5_CONTINUITY = OWNER_ATTENDED_EVENT_BOUNDED_SINGLE_SEQUENCE_TWO_GO, on control `<CONTROL>`, to establish the fresh evidence E-1 … E-21 of the ceremony package §4 (including the DR-5 comparison and freeze, Replica A and my S25 Replica B read, and my E-21 confirmation), read-only, and to stop and wait for me. It does not authorize the transfer, M-B4, M-B5, removal, or anything later.

**12.2 Transfer.**

> I authorize the transfer of exactly the three pinned installable files and SHA256SUMS into /home/ravindupahasara2_gmail_com/lilith-mb4-mb5-stage on lilith-dev-01, as the operator without sudo, with the host re-hash. It does not authorize M-B4 or M-B5.

**12.3 Acceptance after W5 (TRUST_INSTALLED).**

> I accept the verified M-B4/M-B5 INSTALL_TRUST_AND_REGISTRY result of this sequence: P1B-5 PASS; W5_INSTALLED_CONTENT_VERIFIED; anchorsEqualOwnerCopies, witnessAnchorNamesKWit and registryVerifiesOnHost true; denial proof P1B-5 PASS.
> TRUST_INSTALLED = YES (technical, owner-accepted). REGISTRY_EFFECTIVE = NO. AUTHORITY_ACTIVE = NO.
> This acceptance does not authorize M-B6, genesis, record 1, First Memory or PROD. FRESHNESS = UNKNOWN.

**12.4 Bounded removal.** The binding lines are `REMOVAL_LINES` in the
operator:

> I authorize the bounded M-B4/M-B5 removal before M-B6 for exactly one invocation.
> Plan digest: `<planDigest>`.
> I acknowledge: this removal does not reopen the K-WIT burn/regenerate option, and any consumed M-B4/M-B5 go stays consumed.

## 13. Post-M-B3 deploy classification (ADR-0015)

The last accepted DR-5 comparison is M-B2's (deploy `37435321602`, `4d16d76`;
[M-B2 completion](slice-15b2b-b1b3e-mb2-kwit-completion.md) §3). M-B3 took no
fresh DR-5 by decision. These were read from GitHub run metadata only. No
DR-5 log was read, and none is inferred PASS.

| Deploy run | SHA | Change since the previous deploy | Content classification | Evidence consequence |
| --- | --- | --- | --- | --- |
| `37445851939` | `14fbe03` | M-B2 completion records (docs, tests) | unrelated / nonmaterial (docs-only) | DR-5 MUST_RECOLLECT (routine deploy) |
| `37452579297` | `1f544e6` | M-B3 package tooling + tests (owner-control, not deployed payload) | nonmaterial to every §3 class | DR-5 MUST_RECOLLECT |
| `37455735513` | `a86d032` | M-B3 final pins (docs, tests) | nonmaterial | DR-5 MUST_RECOLLECT |
| `37467113188` | `f9fb9e1` | M-B3 phone-script fix + incident record | nonmaterial (owner-control tooling) | DR-5 MUST_RECOLLECT |
| `37470507011` | `cb07608` | M-B3 replacement pins (docs, tests) | nonmaterial | DR-5 MUST_RECOLLECT |
| `37475815074` | `ea74e1b` | attempt-1 disposition record (docs, tests) | nonmaterial | DR-5 MUST_RECOLLECT |
| `37506016808` | `1fb73e0` | **`sharp` 0.35.5**: `package.json` / `package-lock.json` only | frontend dependency outside every §3 dependency set and outside the Core API bundle (`build_core_api_bundle.py` packs `services/core-api` only): **unrelated / nonmaterial** by content | DR-5 MUST_RECOLLECT |
| `37507920435` | `69dc837` | M-B3 completion record (docs, tests) | nonmaterial | DR-5 MUST_RECOLLECT |
| `37517400764` | `b0299f3` | M-B4/M-B5 remediation: docs, owner-control tools and tests, one existing test | nonmaterial to every §3 class; the new tools are provenance, pinned here (§1), not subject drift | DR-5 MUST_RECOLLECT |
| (future) | the merge of this package | docs, owner-control tools and tests, `scripts/authority_custody_denial_proof.py` (owner-run, not a deploy or DR-5 dependency) | nonmaterial | DR-5 MUST_RECOLLECT |

**Summary:**
- **Materially invalidating: none** by content. Nothing changed in the Core
  API bundle, the broker, the deploy workflow or helper, DR-5, the
  authority release, the installer, the sequencer, the owner-freshness
  tool, `burned_identities` or `REAL_ACCEPTANCE_ENABLED`
  (`git diff 4d16d76 b0299f3` touches only `docs/`, `package.json`,
  `package-lock.json`, and `services/owner-memory-control/{tests,tools}`).
- **Dependency-bound revalidation:** every one of these deploys is a routine
  Core API deployment. So DR-5 is MUST_RECOLLECT for each and must equal
  the accepted run, and broker preservation is PORTABLE only if DR-5 is
  equal (policy §4/§5). Their DR-5 results are **UNKNOWN** here.
- **Consequence for B-5:** a different DR-5 result set after a deployment is
  a B-5 §9 stop and **voids** the grant (current grant §7).
- **Unrelated / nonmaterial:** the content of all nine.

## 14. DR-5 design and the extension result

### 14.1 Required fresh non-vacuous DR-5 (E-14; not run here)

For **every** DEV deploy run after `37435321602` up to the latest (the nine
above, plus the merge of this package and any later one), read the run log
(read-only, GitHub). Extract with the
[Condition 2](slice-15b2b-b1b3e-condition2-dev-deploy-boundary.md) §2 rules,
and require each run to be **byte-identical** to the accepted run
`36552218231` on:

- the full result set: 186 lines, 158 `DENIED…`,
  SHA-256 `f18692342cd62572affa54c83f9d390d21ac183e85dc8496dbadb0d5f3f49f9b`;
- the DR-5 block `a1d98773…`;
- the pre-deploy block `f5087042…`.

It must also show:
- `PR1_AUTHORITY_BOUNDARY maturity=P1A-9`;
- `AUTHORITY_BOUNDARY_PROOF=PASS maturity=L1c.3`;
- `ACTIVATION=NOT_ACCEPTED reason=GRANT_ABSENT`;
- no `ALLOWED`.

**Non-vacuous:** 158 `DENIED` lines, with each denial against an existing
object. **Then declare the deployment freeze** (T-1). A run that is not
equal is a B-5 §9 stop: grant VOID, owner re-decision.

**Why the DR-5 result set does not change at M-B4/M-B5.** DR-5 only `stat`s
`/etc/lilith-authority-dev/{trust,registry}` as P1A-9 directories (`0755`).
It does not list them and has no ladder entry for the new files. So
installing the three files leaves the routine DR-5 result set byte-identical.

### 14.2 Extension of DR-5 to the three files: NOT IMPLEMENTED (by design)

**Designed:** two more PR-1 ladder steps in
`scripts/deployer_authority_boundary_proof.sh`:

```text
P1B-4|/etc/lilith-authority-dev/trust/registry-root.json|regular file|644|
P1B-4|/etc/lilith-authority-dev/trust/witness-anchor.json|regular file|644|
P1B-5|/etc/lilith-authority-dev/registry/authority-registry.v1.json|regular file|644|
```

and `AB_PR1_STEPS` += `P1B-4 P1B-5`. The cumulative rule would require both
anchors once either exists, and the deployer would be denied `-w` on each.

**Why not now.** Precedent does not support it safely:
- it changes the DR-5 result set **before** installation, with three new
  `DEFERRED_UNTIL_OBJECT_EXISTS` lines;
- it changes it again **after** installation (`PR1_AUTHORITY_BOUNDARY
  maturity=P1B-5`, new `DENIED` lines);
- DR-5 currentness is defined as byte equality with the accepted run, and a
  different result set after a deployment is a **B-5 §9 stop (grant
  VOID)**;
- the PR-1S precedent extended DR-5 before any B-5 grant existed.

**Precondition for a future extension:** a separate owner decision that
accepts a new DR-5 baseline and its relation to the B-5 grant.

The routine deployer cannot write the files anyway: they are
`root:root 0644` in `root` `0755` directories that DR-5 already proves
unwritable.

### 14.3 Root denial proof extension: IMPLEMENTED

`scripts/authority_custody_denial_proof.py` gains the closed phase **`P1B-5`**:
- `-w` is denied to the application, the deployer, the broker, the signer
  and the witness on each of the three files;
- the existing P1A-10 rows also run;
- P1B-12 rows stay deferred.

It is owner-run, root, streamed, and not part of any deployment, DR-5 or
B-5 §9 condition. The `P1A-10` / `P1B-12` behaviour is unchanged: in
`P1B-12` the new rows also run, because the files exist by then.

## 15. STOP rules (any one ends the sequence; no retry)

- **S-1** any tool pin mismatch, exit 96 (hash gate) or 97 (wrong host).
- **S-2** any terminator T-1 … T-11.
- **S-3** any E-1 … E-22 not PASS, or unknown.
- **S-4** the go file is missing a binding line, or names another control
  commit (operator `GO_LINE_MISSING`).
- **S-5** a one-attempt marker already exists (`ATTEMPT_ALREADY_CONSUMED`).
- **S-6** installer `REFUSED` / non-zero / unexpected output, or its
  `status` other than PASS.
- **S-7** verifier exit not 0 at a checkpoint, a phase other than the
  expected one, or any evidence boolean other than expected.
- **S-8** a staged file re-hash mismatch, an extra or missing staged entry,
  or a non-regular entry.
- **S-9** any K-ACT / K-WIT custody change. Any prompt for a passphrase, or
  any keygen or `systemd-creds` invocation, is never part of this ceremony.
- **S-10** any `ALLOWED` in the denial proof, or a DR-5 result set other
  than the accepted one.
- **S-11** the owner declines or is unsure.

After a STOP: classify the window with `host … W<n>` (read-only). Recover
only per §11, under separate authorization. Cleanup is per §6.

## 16. Remaining blockers before an M-B4/M-B5 preparation decision

1. **This package must be reviewed and merged.** The pinned files must equal
   §1 on merged `main`. The `mb4_mb5_operator.py` and denial-proof pins are
   pre-merge values of unchanged bytes.
2. **E-14 DR-5** for the nine deploys above (and this merge) must be
   compared, inside the sequence. If any one differs, B-5 is void.
3. **The release R-3 module set** is confirmed live by the first `host W0`
   run (inside the authorized sequence).
4. **Broker baseline:** E-7 needs the currently accepted incarnation pin.
   M-B3 recorded `c4b9cb38…` / `a30bd7d6…`; a different running incarnation
   is a T-3 STOP.
5. **The owner's preparation-sequence authorization (§12.1)** is not given.

## 17. State

```text
MB4_MB5_PACKAGE_SOURCE_AND_DESIGN_READY_FOR_REVIEW
MB4_MB5_CONTINUITY = OWNER_ATTENDED_EVENT_BOUNDED_SINGLE_SEQUENCE_TWO_GO (ACCEPTED; SEE CONTINUITY OWNER DECISION)
G-5 CLOSED IN GOVERNANCE; PACKAGE SOURCE READY (PINS FROM MERGED MAIN ON MERGE)
VERIFIER CHECKPOINTS: BEFORE M-B4 = W0_PRE_INSTALL; AFTER M-B4 = W3_ANCHORS_INSTALLED_REGISTRY_ABSENT; AFTER M-B5 = W5_INSTALLED_CONTENT_VERIFIED
REGISTRY_V1_INSTALLABLE_SHA256 = 46b0bfc558ec3a19467206ada3dc53c18e8a6a4cd0782711b4800cfe099f8b1e
ROOT_ANCHOR_INSTALLABLE_SHA256 = bc5f00a76b518c4f11b6804d35844c036db75eaa730d56c35f97f430558ff687
WITNESS_ANCHOR_INSTALLABLE_SHA256 = be360da2324880d725aea509bb0f41500f51ecfc3c2995dd3057824bb471ab5a
POST-M-B3 DEPLOYS: NONE MATERIALLY INVALIDATING BY CONTENT; DR-5 MUST_RECOLLECT FOR EACH; DR-5 RESULTS UNKNOWN
DR-5 EXTENSION = DESIGNED, NOT IMPLEMENTED (B-5 §9 RESULT-SET RULE); DENIAL PROOF P1B-5 = IMPLEMENTED
PREPARATION SEQUENCE = NOT AUTHORIZED
TRANSFER = NOT AUTHORIZED
M-B4 = NOT AUTHORIZED
M-B5 = NOT AUTHORIZED
INSTALL_TRUST_AND_REGISTRY = NOT AUTHORIZED
REMOVAL = NOT AUTHORIZED
TRUST_INSTALLED = NO
REGISTRY_INSTALLED = NO
REGISTRY_EFFECTIVE = NO
AUTHORITY_ACTIVE = NO
GENESIS = NOT AUTHORIZED
RECORD_1 = NOT AUTHORIZED
FIRST_MEMORY = NOT AUTHORIZED
PROD = NOT AUTHORIZED
FRESHNESS=UNKNOWN
NO LIVE SYSTEM CONTACTED; NO K-ROOT OR K-WIT PRIVATE MATERIAL ACCESSED
```

> **Later current state (2026-10-07, pointer only; the text above is
> preserved as written except the operator pin in the §1 table, which must
> equal the code).** The first preparation sequence (control `ffa9575`)
> stopped at E-21: the operator `2d9835ed…` loaded the derivation module
> without registering it in `sys.modules`, and the module's dataclasses failed
> to initialize. Nothing was derived, staged or installed; no go was consumed;
> no burn. See the [sequence-1 incident record](slice-15b2b-b1b3e-mb4-mb5-prep-seq1-operator-loader-incident.md).
> The operator pin `2d9835ed…` is **superseded and must not be used**; the
> fixed operator (pre-merge `e380ab18…`) is pinned in §1. Sequence-1 evidence is
> historical and non-reusable. A new preparation sequence needs its own owner
> authorization after the fix is merged and deployed, and its DR-5 comparison
> must include that deploy. FRESHNESS is UNKNOWN.

> **Later current state (2026-10-07, pointer only; the text above is
> preserved as written).** M-B4/M-B5 `INSTALL_TRUST_AND_REGISTRY` completed in
> preparation Sequence 2 (control `82b89a3`) and was owner-accepted
> ([completion record](slice-15b2b-b1b3e-mb4-mb5-install-trust-registry-completion.md)).
> Exactly one `install-anchors` ran: P1B-4 PASS, and W3 was confirmed after one
> read-only re-classification of a local-client POST anomaly. Exactly one
> `install-registry` ran: P1B-5 PASS, `W5_INSTALLED_CONTENT_VERIFIED`, denial
> proof P1B-5 PASS. The trust anchors and Registry V1 are installed (technical,
> owner-accepted); the registry is not effective and no authority is active.
> The K-WIT burn/regenerate option is closed. M-B6, genesis, record 1, First
> Memory and PROD remain NOT AUTHORIZED, and FRESHNESS is UNKNOWN.
