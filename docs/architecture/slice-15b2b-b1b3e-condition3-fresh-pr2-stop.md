# Slice 15B2b-B1b-3e — M-B1 Condition 3: Fresh PR-2 Revalidation (STOP)

Status:

- **`CONDITION_3_FRESH_PR2=FAIL`. STOP.** The fresh read-only PR-2
  revalidation found **`BROKER_PRESERVATION=FAIL`**. Every other observation
  is equal to the accepted pre-B-5 revalidation.
- **Condition 4 was NOT evaluated.** `CHECK_ELIGIBILITY` was not run, as
  the owner's instruction requires on any material difference.
- **The B-5 grant is void under its own terms.** The
  [B-5 decision packet](slice-15b2b-b1b3e-b5-pr1b-authorization-decision.md)
  §9 lists "broker preservation other than PASS" among the conditions that
  void a GRANTED authorization: "The owner must then re-decide."
- **READ-ONLY.** Cloud: describe / list / get-iam-policy / logging read.
  Host (`lilith-dev-01` only): the reviewed read-only tools. **No DEV
  mutation, no broker restart, no re-pin.** PROD was not contacted, and
  Replica B was not contacted.
- **M-B1 NOT AUTHORIZED.** Conditions 1 and 2 stay CLOSED. Condition 3
  FAILED. Conditions 4 and 5 are OPEN.

```text
fresh PR-2 FAIL -> no eligibility -> B-5 grant void (§9) -> owner re-decision required
```

## 1. Identities

| Item | Value |
| --- | --- |
| control `main` (`CONTROL_SHA`) | `b4def65b05e52e5140824b094705e355061e855e` |
| reviewed tools | **byte-identical** to the pre-B-5 revalidation (the same git blobs at `cf3a829` and `b4def65`): observer `7d1e3e89…`, installer `c265433e…`, broker verifier `451f418a…`. The storage probe is the same bytes (`8cdfdedc…`). No change under `services/core-api`, `services/authority-dev`, `scripts`, or `.github` since `cf3a829` |
| collectors | the pre-B-5 `cloud_collect.sh` / `host_collect.sh`, changing only the output directory, the audit-since timestamp (`2026-09-29T18:57:17Z`, the end of the pre-B-5 window), and `CONTROL_SHA`. A read-only `dpkg.log` / reboot-required check was added |
| **window** | cloud `2026-10-02T09:49:56Z`–`09:53:04Z` (service-account IAM re-read just after); host `09:54:31Z`–`09:55:25Z`; Replica A just after; window closed `09:56:41Z` |
| evidence | owner workstation `C:\Users\edufo\lilith-b1b3e-c3c4\` (73 files), `SHA256SUMS` `b4e83101a277f4d0c98f77bfc3eaaafc7ae29a59a87f57d51af9e9846c8df6cb` |
| baseline compared | the pre-B-5 evidence `C:\Users\edufo\lilith-b1b3e-pr2-preb5\` (`67eb9a16…`, its `SHA256SUMS` re-verified) |

## 2. The failure

`preservation` (`scripts/verify_broker_dev_current_incarnation.py`),
output SHA-256 `a7caaf68…`:

```text
BROKER_PRESERVATION=FAIL
failures:
  RUNTIME_SUBSTRATE_STALE_OR_UNREADABLE
  ACCEPTED_IDENTITY_CHANGED:sharedLibrariesSha256
  BASELINE_CANDIDATE_CHANGED
acceptedIdentityMatches=false   baselineCandidateMatchesAccepted=false
sharedLibrariesSha256: 40e68a1c… (accepted) -> 80130f7d…
baselineCandidateSha256: 50003745… (accepted) -> ddee1c15…
```

**The single changed input is:**

```text
/usr/lib/x86_64-linux-gnu/libcrypto.so.3
  mapped inode 12510, deleted=true, sha256=null   (accepted: deleted=false, sha256 6a66c3ba…)
  on-disk inode 5987
```

**Cause.** The host's `dpkg.log` records a routine unattended upgrade:

```text
2026-10-01 06:53:42 upgrade libssl3t64:amd64 3.0.13-0ubuntu3.15 3.0.13-0ubuntu3.16
2026-10-01 06:53:42 upgrade openssl:amd64 3.0.13-0ubuntu3.15 3.0.13-0ubuntu3.16
```

1. The upgrade replaced `libcrypto.so.3` on disk.
2. The broker was **not** restarted (the authority-sensitive restart control
   held). It is still the accepted process: PID `2586`, incarnation
   `84798e5b…`, `NRestarts=0`, boot `eea461c3…`.
3. So the process still maps the old, now-deleted library file.
4. The verifier's structural rule requires every mapped library to be
   non-deleted, with the on-disk inode equal to the mapped inode.

**No re-pin can make this PASS while this process runs.** Only a new
broker process that maps the new library can satisfy the rule: a broker
restart or a reboot. Either is a live mutation and needs a new owner
re-baseline. Neither is authorized.

Other packages changed in the same period (not mapped by the broker in the
accepted library set):
- `libheif*` (10-01);
- `libxpm4` (10-02);
- the `snapd` snap auto-refresh (2.76.3 → 2.77.1, a read-only squashfs loop).

`REBOOT_REQUIRED=absent`.

## 3. Everything else (equal to the accepted boundary)

**Cloud** (LILITH project). Byte-identical to the pre-B-5 revalidation:

- the instance, and the instance list;
- the disks: one zonal `pd-balanced` 20 GB boot disk, attached only to
  `lilith-dev-01`;
- snapshots, instant snapshots, resource policies / snapshot schedules,
  machine images, and custom images: all `[]`;
- the enabled services (`backupdr` not enabled);
- buckets (none);
- project metadata keys, and the visible-project list;
- the project, instance and disk IAM policies;
- **all five service-account IAM policies.**

The first read of the service-account policies came back empty. That was a
collector defect, not an IAM change: CRLF in `sa-list.txt` made four calls
fail silently. They were re-read immediately, and all five are
byte-identical.

**Admin Activity since the pre-B-5 window: 24 entries, all
`iam.serviceAccounts.actAs` on `lilith-dev-vm`.**
- 20 are `github-lilith-dev-deployer`: 4 for each of the 5 routine deploys
  `11c47dc`, `cfa0b3e`, `c694061`, `92ab356`, `b4def65`.
- 4 are the owner at `2026-09-29T18:57`–`18:58Z`: the tail of the pre-B-5
  host collection.
- **No compute call.** The whole-life compute Admin Activity set is
  byte-identical (20 entries): no snapshot, image, clone, attach / detach,
  or stop / start / reset has ever been made.

**Latest DEV deployment.** Run `36991330853` (`b4def65`), and every deploy
since the pre-B-5 window. Its 186-line boundary result set and 147-line
DR-5 block equal the accepted run `36552218231` exactly
([Condition 2 record](slice-15b2b-b1b3e-condition2-dev-deploy-boundary.md)).

**Host** (`lilith-dev-01`):

| # | Item | Observed |
| --- | --- | --- |
| 1 | VM identity / boot | `lilith-dev-01`. Boot `eea461c3-60f0-4b10-8ee9-556dcef19711`, the same boot. Kernel `7.0.0-1013-gcp` |
| 2–3 | disk / filesystem placement | probe sections identical: `by-id`, `fstab`, swaps, dm / md / NVMe, power, packages of interest, `/etc` VCS, Google snapshot hooks, runtime-fs, `lilith` tmpfiles, unit runtime properties, socket listen, unit files, host-key parent stat, journald. The only `lsblk` and mount difference is the `snapd` loop device (and user tmpfs sessions). All custody paths remain on ext4 `sda1` |
| 12 | TPM / vTPM | identical: `/dev/tpm0` and `/dev/tpmrm0` are present, with no TSS library, and nothing is bound to TPM state |
| 13 | authority observer | **`stableSha256` `c4a654033dac292b176aacd114e15b8b998a30f4c27cb05615f68bd7b1af5734`, equal**. Accounts, currentBlob, filesystems, hostFiles, hostKey, listings, and releases are unchanged |
| 14 | P1A-9 | **`status --expect P1A-9` PASS, byte-identical** to the pre-B-5 output |
| 15 | broker preservation | **FAIL** (§2) |
| 16 | activation | **`ACTIVATION=NOT_ACCEPTED reason=GRANT_ABSENT`** (rc 1), byte-identical |
| 17 | units | byte-identical: broker PID `2586`, incarnation `84798e5b…`, `NRestarts=0`. The authority and witness units and sockets are inactive, with no InvocationID. The Stage III controller is never started |
| 18 | unexpected authority material | none: the observer and status outputs are unchanged |

**Owner side.** Replica A (read-only, WSL) is **byte-identical** to the
pre-B-5 observation:
- records `0`;
- entries `REPLICA.json records`;
- manifest `fbdd045c…978b`;
- inodes `59905 / 59906 / 59907`, mtime `1790643451`.

Replica B was not contacted (last evidence: B-4 run 2, 0 records).

## 4. Rollback conclusions (re-established)

The topology is unchanged, so the canonical conclusions stand:

```text
WHOLE-HOST / WHOLE-DISK ROLLBACK CAN PRESENT A SELF-CONSISTENT OLD AUTHORITY WORLD.
WHOLE-HOST ROLLBACK RESISTANCE = NOT ESTABLISHED.
INDEPENDENTLY PERSISTED FRESHNESS STATE = NONE.
```

## 5. What the owner must decide (not decided here)

1. **Re-decide B-5.** Under §9 the existing grant is void.
2. **How to restore broker preservation.** This needs a live, owner-authorized
   step. Two routes:
   - a controlled broker restart: a new incarnation, then the
     re-baseline acceptance and re-pin flow of the
     [broker preservation re-pin](slice-15b2b-b1b3e-broker-preservation-repin.md);
   - a controlled reboot ceremony, as for the pre-PR-1B reboot.

   Either is followed by a new DR-5, and then a **new** fresh PR-2
   revalidation immediately before eligibility.
3. **Substrate drift policy.** Unattended upgrades replace libraries under
   a broker that, by design, is not restarted. This will recur whenever a
   mapped library is upgraded. Options include:
   - holding the broker's mapped packages (for example `libssl3t64`)
     during the PR-1B window;
   - scheduling the window right after a deliberate re-baseline.

   The owner chooses; this record does not.

Until then: no eligibility, and no M-B1.

## 6. State

```text
CONDITION_3_FRESH_PR2=FAIL
CONDITION 4 NOT EVALUATED
B5 GRANT VOID UNDER §9 (broker preservation other than PASS) — OWNER RE-DECISION REQUIRED
CONDITION 1 CLOSED
CONDITION 2 CLOSED
CONDITION 3 FAILED (STOP)
CONDITION 4 OPEN
CONDITION 5 OPEN
M-B1 NOT AUTHORIZED
NO M-B1 COMMAND ISSUED
NO DEV MUTATION BY THIS REVALIDATION
NO BROKER RESTART
NO REAL K-ROOT
NO K-WIT
NO REGISTRY V1
NO GENESIS PIN
NO REAL RECORD 1
NO REPLICA A / B CHANGE
FRESHNESS=UNKNOWN
FIRST MEMORY NOT AUTHORIZED
```
