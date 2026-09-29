# Slice 15B2b-B1b-3e — PR-2 Read-Only Revalidation (pre-B-3/B-5 landing window)

Status:

- **`PR2_PRE_B5_REVALIDATION_PASS`**. This is a fresh read-only PR-2
  revalidation. The topology is **unchanged** from the accepted PR-2 model
  and from the [previous revalidation](slice-15b2b-b1b3e-pr2-revalidation.md).
- **READ-ONLY.** Cloud: describe / list / get-iam-policy / logging read.
  Host (`lilith-dev-01` only; PROD not contacted): the reviewed read-only
  tools, plus one read-only package-log check.
- **B-3 is HELD and unmerged** (`claude/15b2b-b1b3e-b3-real-acceptance-held`,
  `729e2a3`). B-5 is unchanged.
- **WHOLE-HOST / WHOLE-DISK ROLLBACK RESISTANCE: NOT ESTABLISHED.**
- **PR-1B NOT AUTHORIZED**; **FIRST MEMORY NOT AUTHORIZED**.
- **Classification: `PR2_PRE_B5_REVALIDATION_READY`**.

```text
PR-2 revalidation PASS != rollback resistance != PR-1B authorization
```

## 1. Identities

| Item | Value |
| --- | --- |
| control `main` (`CONTROL_SHA`) | `cf3a8291003ac55fd1e030caadd3895662f8e669` |
| reviewed tools | byte-identical to the previous revalidation (`c0adb70` → `cf3a829`, the same git blobs): observer `a2f21b45…`, installer `fe10d9a3…`, broker verifier `bd7aa35a…`. The storage probe is the same script bytes |
| window | cloud `2026-09-29T18:51:53Z`–`18:55:14Z`; host `18:56:31Z`–`18:57:17Z`, plus a package-log check just after |
| evidence | owner workstation `C:\Users\edufo\lilith-b1b3e-pr2-preb5\` (68 files), `SHA256SUMS` `67eb9a16048314dd04ddf50aa228eb5a104764c6be173c8c5f342cbd4d436b0a` |
| baseline compared | the previous revalidation's evidence `…\lilith-b1b3e-pre-pr1b-reboot\pr2rv\` (`451acdd9…`) |

## 2. Changes since the previous revalidation

**Code.**

- 12 merges to `main` (`28daf7b` … `cf3a829`), each followed by a
  merge-triggered DEV deployment run.
- None of them changed `services/core-api`, `services/authority-dev`,
  `scripts`, or `.github` (empty `git diff` over those paths,
  `c0adb70..cf3a829`). They changed docs, owner-memory-control tests, and
  B-4 tooling only.

**Latest DEV deployment** (run `36597637454`, `cf3a829`).

- `MODE=DEPLOY_REQUIRED`: the routine Core API deployment, the only DEV
  mutation class in the window. I made none.
- Its DR-5 boundary results equal the accepted run `36552218231`
  **exactly**: 156 result lines, including 154 `DENIED` lines,
  `PR1_AUTHORITY_BOUNDARY maturity=P1A-9`, and
  `AUTHORITY_BOUNDARY_PROOF=PASS maturity=L1c.3`.
- There is no real `ALLOWED(unexpected)`: the only matches are the script's
  own function text, as in the accepted run.

**Package activity.**

- The last dpkg install/upgrade/remove was `2026-09-29 06:06:43` (routine
  unattended upgrades and old `7.0.0-1011` kernel removal). That is
  **before** the previous window and before the current boot.
- There has been no package change since, and `REBOOT_REQUIRED=absent`.

## 3. Live observations

**Cloud** (LILITH project). Byte-identical to the previous revalidation:

- instance and instance list;
- disk list;
- snapshots, instant snapshots, resource policies, machine images, and
  custom images;
- project, instance, disk, and all five service-account IAM policies;
- the service-account list;
- enabled services;
- buckets;
- project metadata keys;
- the visible-project list.

The other visible projects give the same content (only the listing order
differs).

| # | Item | Observed |
| --- | --- | --- |
| 1 | DEV VM identity / zone | `lilith-dev-01`, `asia-southeast1-b`, `e2-small`, `automaticRestart=true`, `onHostMaintenance=MIGRATE`; unchanged |
| 2 | boot disk | exactly one zonal `pd-balanced` 20 GB boot disk (`persistent-disk-0`), attached only to `lilith-dev-01`. Google-managed encryption, no replication, no sharing, no resource policies |
| 4 | snapshots | **none** (`[]`) |
| 5 | instant snapshots | **none** (`[]`) |
| 6 | snapshot schedules / resource policies | **none** (`[]`) |
| 7 | machine images | **none** (`[]`) |
| 8 | custom images / clones | **none** (`[]`). The whole-life compute Admin Activity set is byte-identical: no clone, snapshot, image, attach / detach, or stop / start / reset has ever been made |
| 9 | Backup and DR / backup products | `backupdr.googleapis.com` is not enabled (the enabled services are identical). No backup product is present |
| 10 | object storage / external persistence | **no buckets** |
| — | Admin Activity since the previous window | 60 entries, all `iam.serviceAccounts.actAs` (OS Login / IAP sessions of the deploy runs). **No compute call** |

**Host** (`lilith-dev-01`).

| # | Item | Observed |
| --- | --- | --- |
| — | boot / kernel | boot `eea461c3-60f0-4b10-8ee9-556dcef19711`, the same boot as the previous window. Kernel `7.0.0-1013-gcp` |
| 3 | block devices / filesystems | the storage probe is structurally identical: the same `lsblk` set, `by-id` names and targets, mount set, `fstab`, swaps, dm / md / NVMe, power, and packages. The only diffs are timer schedules, cron parent-directory mtimes, and `/var/backups` apt-state rotation (from the 06:06 upgrade, copied by the 12:21 daily job) |
| 11 | TPM / vTPM | the vTPM is enabled on the VM (Secure Boot off). `/dev/tpm0` and `/dev/tpmrm0` exist, but no TSS library is installed. **No authority material is bound to TPM state**: K-ACT (and future K-WIT) are host-key sealed |
| 12 | authority / witness / registry / custody locations | observer `stableSha256` `c4a654033dac292b176aacd114e15b8b998a30f4c27cb05615f68bd7b1af5734`, **equal** to the previous revalidation, so accounts, currentBlob, filesystems, hostFiles, hostKey, listings, and releases are unchanged. All current and future custody paths remain on ext4 `sda1` (`st_dev` 2049) |
| — | units | byte-identical: broker PID `2586`, incarnation `84798e5b74494e1ea362ce90f1cf04ad`, `NRestarts=0`. The authority and witness units and sockets are inactive, with no InvocationID. The Stage III controller is never started |
| — | installer status | `status --expect P1A-9` **PASS**, `failures=[]`, byte-identical |
| — | broker preservation | `BROKER_PRESERVATION=PASS`, `acceptedIdentityMatches=true`, `baselineCandidateMatchesAccepted=true`, byte-identical |
| — | activation | `ACTIVATION=NOT_ACCEPTED reason=GRANT_ABSENT` (rc 1) |

**Owner side.**

- **Replica A** (read-only, laptop WSL, `/root/lilith-owner-freshness/owner-primary-dev-synthetic-01`):
  - records `0`;
  - entries exactly `REPLICA.json records`;
  - the parent holds only the replica;
  - manifest `fbdd045c…978b`;
  - inodes `59905 / 59906 / 59907` and mtime `1790643451`, unchanged.
- **Replica B** was not contacted. Its last evidence is the accepted B-4
  run 2 (same day): 0 records, manifest `c068e533…07c4`, byte-identical
  before and after.

## 4. Freshness and rollback

| # | Question | Answer |
| --- | --- | --- |
| 13 | independently persisted freshness state consumed by DEV | **NONE**. Replicas A and B exist, but they are empty; there is no record 1 |
| 14 | can a whole-host / whole-disk rollback present a self-consistent old authority world? | **YES.** K-ACT, the host key, and every current and future custody object share one disk and one snapshot domain, and no freshness state consumed by a verifier exists outside it. No restore artifact exists today (§3), but any principal able to create a snapshot, image, or clone (OR-3) could create one |
| 15 | a topology change that invalidates the analysis | **none.** No new rollback domain, disk, attachment, snapshot mechanism, backup product, bucket, or TPM binding |

```text
WHOLE-HOST / WHOLE-DISK ROLLBACK CAN PRESENT A SELF-CONSISTENT OLD AUTHORITY WORLD.
WHOLE-HOST ROLLBACK RESISTANCE = NOT ESTABLISHED.
INDEPENDENTLY PERSISTED FRESHNESS STATE = NONE.
```

Owner freshness remains the intended off-host protection once record 1
exists.

## 5. Authority state (item 17)

- There is no real K-ROOT. Under custody Option A1 it would live only on the
  phone, and M-B1 has not run.
- There is no K-WIT, registry v1, genesis pin, or real record 1.
- The observer and installer status are unchanged from `P1A-9`.
- Real freshness is `FRESHNESS_UNKNOWN`.

## 6. Open risks

OR-1..OR-9 are unchanged from the
[previous revalidation](slice-15b2b-b1b3e-pr2-revalidation.md) §8:

- **Open:** OR-1, OR-2, OR-4, OR-7, OR-8.
- **Bounded:** OR-3.
- **Visibility limit:** OR-9.
- **Closed:** OR-5, OR-6.

## 7. Result and validity

```text
PR2_PRE_B5_REVALIDATION_PASS
PR-2 materially equivalent to the accepted inventory and the previous revalidation
WHOLE-HOST / WHOLE-DISK ROLLBACK RESISTANCE: NOT ESTABLISHED
```

This result covers the current window only. P3-5 §13 still requires PR-2 to
be revalidated read-only **immediately before** `CHECK_ELIGIBILITY` and
immediately before `GENERATE_K_WIT`.

- If the B-3 merge and the B-5 decision follow this window without any
  intervening topology change (a routine deployment that equals this
  record's DR-5 result set is not one), this record may serve as that input.
- Otherwise, any change yields `PR2_REVALIDATION_REQUIRED`.

## Explicitly not done

```text
NO DEV MUTATION BY THIS REVALIDATION
NO PROD CONTACT
NO SNAPSHOT / IMAGE / BACKUP CREATED
B-3 NOT MERGED
B-5 UNCHANGED
NO M-B1
NO REAL K-ROOT
NO K-WIT
NO REGISTRY V1
NO GENESIS PIN
NO REAL RECORD 1
NO REPLICA A / B CHANGE
FRESHNESS=UNKNOWN
PR-1B NOT AUTHORIZED
FIRST MEMORY NOT AUTHORIZED
```
