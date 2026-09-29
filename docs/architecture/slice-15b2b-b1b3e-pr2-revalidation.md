# Slice 15B2b-B1b-3e — PR-2 Read-Only Revalidation (post-reboot)

Status:

- **`PR2_REVALIDATION_PASS`** (owner-accepted)
- **READ-ONLY**. The only DEV mutation in the window was the routine Core API
  deployment of the merge-triggered run (§2)
- **WHOLE-HOST / WHOLE-DISK ROLLBACK RESISTANCE: NOT ESTABLISHED**
- **PR-1B NOT AUTHORIZED**; **FIRST MEMORY NOT AUTHORIZED**

```text
PR-2 revalidation PASS != rollback resistance
PR-2 revalidation PASS != PR-1B authorization
```

This record revalidates the accepted
[PR-2 snapshot / rollback inventory](slice-15b2b-b1b3e-pr2-snapshot-inventory.md)
([acceptance](slice-15b2b-b1b3e-pr2-acceptance.md)). The revalidation follows
the [pre-PR-1B reboot and rebaseline](slice-15b2b-b1b3e-pre-pr1b-reboot-rebaseline-acceptance.md)
and the [broker preservation re-pin](slice-15b2b-b1b3e-broker-preservation-repin.md),
as the P3-5 sequencing requires
([§12–§13](slice-15b2b-b1b3e-pr3-pr1b-bootstrap-sequencing.md)). It edits no
earlier record.

## 1. Identities

| Item | Value |
| --- | --- |
| merged main (`CONTROL_SHA`) | `c0adb70fe421465ffd13e418eef105cb99776ee9` (merge of PR #107, contains `0d71e33`) |
| broker verifier | `bd7aa35a2e7834a6cc35ba7d1a069a0847a69a03fa7d0d9fe30a5f227703292d` (the reviewed re-pin artifact) |
| other tools | observer `a2f21b45…`; installer `fe10d9a3…`; comparator `6a20c02e…`; PR-2 storage probe, the same bytes as PR-2 (`8cdfdedc…`) |
| window | 2026-09-29 about `09:58Z`–`10:10Z` |
| contact | cloud: describe / list / get-iam-policy / logging read only, as the reviewing principal. Host: OS Login operator over IAP. The storage probe runs without `sudo`; the reviewed tools run as root, read-only |
| evidence | owner workstation `C:\Users\edufo\lilith-b1b3e-pre-pr1b-reboot\pr2rv\`, `SHA256SUMS` `451acdd9…` |

## 2. Preconditions (all PASS)

| Check | Result |
| --- | --- |
| merge-triggered DR-5 | run `36552218231` (`DEPLOY_REQUIRED`, `09:54:48Z`–`10:00:29Z`): `PR1_AUTHORITY_BOUNDARY maturity=P1A-9`, `AUTHORITY_BOUNDARY_PROOF=PASS maturity=L1c.3`. No real `FAIL`, no `ALLOWED(unexpected)`. The six OR-6 `/run` denials are present. The `DENIED` set equals the post-reboot DR-5 |
| broker `preservation` (merged verifier) | `BROKER_PRESERVATION=PASS`, `failures=[]`, `acceptedIdentityMatches=true`, `baselineCandidateMatchesAccepted=true` |
| accepted broker | boot `eea461c3-60f0-4b10-8ee9-556dcef19711`, incarnation `84798e5b74494e1ea362ce90f1cf04ad`, candidate `5000374513f38144c90bd75aefdabb4d000f644e024107bf275da9f80af7dbe2`, PID `2586`, start ticks `69918`, `NRestarts=0`. The Stage III controller is loaded, inactive, and never started |
| `status --expect P1A-9` | PASS |
| activation | `ACTIVATION=NOT_ACCEPTED reason=GRANT_ABSENT` |
| authority / witness units | all five inactive, with no InvocationID |
| host observer | `stableSha256` `c4a654033dac…`, equal to the post-DR-5 observation. The reboot comparison against the accepted PR-2 digest `5eaec23c…` returns `PASS unexpected=0`. Unchanged: accounts, currentBlob, filesystems, hostFiles, hostKey, listings, releases |

## 3. Cloud topology (LILITH project)

Every describe / list / IAM result is **byte-identical** to the accepted PR-2
evidence:

- instance and instance list;
- disk list;
- project, instance, disk, and service-account IAM policies;
- enabled services;
- project metadata keys.

The service-account list shows the same five accounts; only the output
format differed.

| Item | Result |
| --- | --- |
| VM | `lilith-dev-01`, `e2-small`, `automaticRestart=true`, `onHostMaintenance=MIGRATE`, vTPM enabled, Secure Boot off, no resource policies. **Materially unchanged** |
| disks | exactly one: the zonal `pd-balanced` 20 GB boot disk. Google-managed encryption, no replication, no sharing, no resource policies. **Unchanged** |

## 4. Snapshot, image, and backup inventory

| Mechanism | Result |
| --- | --- |
| snapshots | **none** |
| instant snapshots | **none** |
| snapshot schedules / resource policies | **none** |
| machine images | **none** |
| custom images | **none** |
| backup / DR artifacts | **none in the reviewed LILITH scope**. Backup and DR is not enabled, and there are no Cloud Storage buckets |
| Admin Activity since the PR-2 window | only `iam.serviceAccounts.actAs` on the DEV VM service account (206 entries, from the IAP / OS Login sessions). **No compute call.** The in-guest reboot made no GCE call |
| Admin Activity, the project's whole life | the compute method set is identical to PR-2's. There has never been a snapshot, instant snapshot, image, machine image, disk clone, attach / detach, stop / start / reset / suspend, or resource-policy call |
| host (storage probe) | structurally identical to PR-2: same single disk, partitions, `by-id` links, and mount set; no LVM / btrfs / ZFS; no backup software; no `/etc` VCS; no GCE snapshot hooks; same timers, cron, `/var/backups`, journald configuration, and `snap saved`. The only differences are boot artifacts: timestamps, schedules, mount IDs, loop-device order, and a slightly smaller `/run` tmpfs size under the new kernel |

## 5. Persistence domains

- **Single domain, unchanged.** The following are still on ext4 `sda1`
  (`st_dev` 2049) of the single 20 GB `pd-balanced` boot disk, as in PR-2 §5
  (observer `filesystems` section byte-identical; host-key stat unchanged):
  - `credential.secret`;
  - CURRENT (K-ACT);
  - the custody root and slots;
  - the skeleton;
  - every future K-WIT, registry, ledger, witness, hold, and RecoveryEpoch
    path.
- **TPM sealing: not established.** `/dev/tpm0` exists, but no TSS library
  is installed. K-ACT, and future K-WIT, are sealed with the host key.
- **Runtime state.** Runtime-only state (`/run`, `/run/credentials`) is
  tmpfs and re-created empty at boot (OR-6, closed). `/tmp` and `/var/tmp`
  are still on `sda1` (OR-7).

## 6. Freshness

- **Independent freshness consumed by DEV: none.**
- **Owner replicas** (not contacted in this revalidation):

| Replica | State |
| --- | --- |
| A | real, empty |
| B | real, empty |
| accepted records | `0` |
| record 1 | absent |
| real freshness | **`FRESHNESS_UNKNOWN`** |

P3-3 completion does not make DEV rollback-resistant.

## 7. Central question

> Can whole-host / whole-disk rollback still present a self-consistent old
> authority world?

**Yes.** K-ACT, the host key, and every current and future custody object
share one disk and one snapshot domain. No freshness state consumed by any
verifier exists outside it.

- A restore of that disk, by any principal able to create a snapshot, image,
  or clone (OR-3), rolls all of them back together and cannot be detected
  on the host.
- This does not follow from service separation, and service separation
  does not change it.
- No artifact capable of such a restore exists today (§4).

**Whole-host / whole-disk rollback resistance: NOT ESTABLISHED.**

## 8. Open risks

| ID | Risk | Status |
| --- | --- | --- |
| OR-1 | whole-disk / whole-host rollback presents a self-consistent old authority world | **OPEN** |
| OR-2 | root-equivalent principals and host-local copies (DR-3) | **OPEN** |
| OR-3 | cloud principals able to create a future snapshot, image, or clone | **OPEN / bounded**: IAM unchanged; no artifact exists |
| OR-4 | no external freshness state consumed by DEV | **OPEN**: replicas exist, but they are empty and freshness is `FRESHNESS_UNKNOWN` |
| OR-5 | pending kernel reboot | **CLOSED**: kernel `7.0.0-1013-gcp`; `reboot-required` absent; no process maps a deleted libc |
| OR-6 | tmpfiles post-boot runtime directories | **CLOSED**: exact tmpfiles spec, empty, `P1A-9` PASS, DR-5 denies |
| OR-7 | `PrivateTmp=` / `/tmp` backed by the disk | **OPEN / applicable**: `/tmp` and `/var/tmp` remain on `sda1`; inert while the services do not run |
| OR-8 | future snapshot activity can make this inventory stale | **OPEN**: valid as of this window |
| OR-9 | visibility scope | **LIMIT / visibility-scope limitation only** (below) |

**OR-9 wording.** PR-2 conclusions are limited to the LILITH project and
other cloud projects visible to the reviewing principal. Unrelated visible
projects are not LILITH components and create no architectural dependency
or authority relationship. They were observed only to bound the
reviewer-visible search space for snapshot, image, and backup artifacts; no
such artifact was found there. They are not LILITH infrastructure,
dependencies, recovery domains, authority domains, custody domains, or
freshness domains.

## 9. Result

```text
PR2_REVALIDATION_PASS
PR-2 materially equivalent to the accepted inventory (OR-5, OR-6 closed)
WHOLE-HOST / WHOLE-DISK ROLLBACK RESISTANCE: NOT ESTABLISHED
```

This result satisfies the P3-5 §13 revalidation rule for the current window
only. P3-5 requires it again, read-only, immediately before
`CHECK_ELIGIBILITY` and immediately before `GENERATE_K_WIT`. Any change
yields `PR2_REVALIDATION_REQUIRED`.

## 10. Nonclaims

This record does not claim:

- rollback resistance of any kind;
- that DR-3 is closed;
- any change to owner freshness;
- PR-1B eligibility or authorization;
- K-ROOT, K-WIT, a registry, a ledger, witness state, a hold,
  RecoveryEpoch, INITIAL_CUSTODY, or real record 1;
- First Memory.

## Explicitly not done

```text
NO DEV CONTACT BEYOND READ-ONLY OBSERVATION
NO DEV MUTATION (except the routine merge-triggered Core API deployment)
NO SNAPSHOT / IMAGE / BACKUP CREATED
NO AUTHORITY START
NO WITNESS START
NO K-ROOT
NO K-WIT
NO REGISTRY
NO LEDGER
NO REAL RECORD 1
REAL FRESHNESS REMAINS UNKNOWN
PR-1B NOT AUTHORIZED
FIRST MEMORY NOT AUTHORIZED
```
