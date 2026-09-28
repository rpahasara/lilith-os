# Slice 15B2b-B1b-3e PR-2: DEV Snapshot / Rollback Inventory

**Status: PR-2 SNAPSHOT / ROLLBACK INVENTORY.** READ-ONLY RESEARCH AND
EVIDENCE ONLY. No DEV mutation, no cloud-resource mutation. Whole-host
rollback resistance is **NOT ESTABLISHED**. This record is not an acceptance
record. PR-1B is not authorized. First Memory is not authorized.

| Field | Value |
| --- | --- |
| Gate | live-rehearsal gate §14 row PR-2 (RR-17, [gate §5.6](slice-15b2b-b1b3e-live-rehearsal-gate.md)); PR-1 preflight §20 ([preflight](slice-15b2b-b1b3e-pr1-live-install-preflight.md)) |
| Accepted pre-state | PR-1A ACCEPTED ([acceptance](slice-15b2b-b1b3e-pr1a-acceptance.md)): FINAL_MATURITY `P1A-9`, AUTHORITY_BOUNDARY PASS `L1c.3`, release `aee323e94412accbe321bc84eae78c5b8cf95afc` |
| Starting main | `db22f09a66a91f2fe05cad3b1f11815a856c1367` |
| Cloud window | 2026-09-28 from `23:31:14Z`, same session (describe / list / get-iam-policy / logging read only) |
| Host window | 2026-09-28 `23:42:58Z`–`23:44:17Z` (storage probe as the operator; reviewed observer as root) |
| Private evidence | outside the repository; `SHA256SUMS` digest `f967e5db574a8ec1db16aad68bcb0d7a1fbfa68091f9ef67f1c8ce2c5b07b666` |
| Result | `PR2_INVENTORY_COMPLETE` (§15) |

```text
storage separation       != snapshot-domain separation
service separation       != failure-domain separation
cryptographic separation != rollback separation
```

## 1. Question

If the DEV machine or disk were restored from a snapshot, image, machine
image, clone, provider backup, filesystem backup, or host-local copy, which
current and future authority and custody objects would roll back
**together**? This record states what rollback can capture today. It does
not prove rollback resistance and does not remediate anything.

## 2. Method and contact

**Cloud (read-only).** From the owner workstation, as the project-owner user
account (active gcloud account; identity recorded privately):

- `compute instances describe | list`, `disks list`, `snapshots list`,
  `instant-snapshots list`, `resource-policies list`, `machine-images list`,
  `images list --no-standard-images`;
- `projects get-iam-policy`, `iam service-accounts get-iam-policy` (five
  project service accounts), `compute instances|disks get-iam-policy`,
  `iam roles describe` (the project custom role and `roles/compute.viewer`);
- `services list --enabled`, `storage buckets list`,
  `compute project-info describe` (metadata keys only);
- `logging read` over the Admin Activity audit log (400-day freshness, which
  covers the project's whole life since 2026-08-23);
- the same snapshot / image / machine-image lists in the three other projects
  visible to the owner account (§9.3).

**Host (read-only).** OS Login operator over IAP, the transport already used
for PR-1A. Two contacts:

1. **Storage probe** (operator, no `sudo`, 3 307 bytes, private evidence):
   `lsblk`, `/dev/disk/by-id`, `/proc/self/mountinfo`, `/etc/fstab`,
   `/proc/swaps`, device-mapper / md / NVMe presence, TPM device nodes,
   `/sys/power`, `dpkg-query` for backup and TPM packages, `/etc` VCS
   presence, GCE snapshot-hook directories, `systemctl list-timers`, cron
   directory listings, `/var/backups` listing, journald configuration,
   `snap list` / `snap saved`, `findmnt -T` for runtime paths, the two
   installed lilith tmpfiles files, `systemctl show` for unit runtime
   properties, a grep of the installed unit files, and `stat` of
   `/var/lib/systemd` and `credential.secret` (metadata only).
2. **Reviewed observer** `observe_authority_dev_host.py observe` (SHA-256
   `a2f21b45…`, unchanged since `bf866b2`), streamed and run as root, exactly
   as in M-A1..M-A10.

Neither contact reads the host key or any credential plaintext, runs
`systemd-creds`, decrypts, writes, chmods, changes a mount, or touches a unit
lifecycle. No child of a root-only custody slot was opened. The observer's
directory listing of the empty slots is the same reviewed observation used
throughout PR-1A.

**Host unchanged.** The observer returned
`stableSha256=5eaec23cef9c8f53db8e6f27e84b270ad6b8567d4f21287a1ffd543550fe2778`.
That is **identical** to the M-A10 POST. Every non-volatile observed fact
(release, units, CLIs, accounts, CURRENT, host-key stat, listings, PR-1
objects, filesystems, namespace inventory) is unchanged since PR-1A
acceptance. Boot `24d1771d…` continues; `reboot-required` is still present.

## 3. Cloud topology

| Item | Observed |
| --- | --- |
| Project | `lilith-agent-260823-27389` (created 2026-08-23) |
| DEV instance | `lilith-dev-01`, id `7687…2258`, `e2-small`, `RUNNING`, created 2026-09-13 17:57Z |
| Zone / region | `asia-southeast1-b` / `asia-southeast1` |
| Scheduling | `automaticRestart=true`, `onHostMaintenance=MIGRATE`, `STANDARD` (not preemptible / spot) |
| Shielded VM | `enableVtpm=true`, `enableIntegrityMonitoring=true`, `enableSecureBoot=false` |
| Confidential VM | not enabled |
| `deletionProtection` | `false` |
| Instance resource policies | none |
| Instance metadata | no items. Project metadata: `enable-oslogin` only |
| `sourceMachineImage` | none |
| Network | one NIC on `lilith-vpc`, no external address |
| Attached service account | `lilith-dev-vm@…`, scope `cloud-platform`; project roles only `logging.logWriter` and `monitoring.metricWriter` |
| Attached disks | **exactly one**: boot, `PERSISTENT`, `READ_WRITE`, `autoDelete=true`, device `persistent-disk-0` |
| Boot disk | `lilith-dev-01`, id `8559…4802`, zonal `asia-southeast1-b`, `pd-balanced`, 20 GB, 4096-byte blocks |
| Disk source | public image `ubuntu-2404-noble-amd64-v20260820`; `sourceSnapshot` none |
| Disk replication | zonal. No `replicaZones` (not regional), no `asyncPrimaryDisk` (no async replication) |
| Disk sharing | `users` = only `lilith-dev-01`; `accessMode` unset (single-writer). Not shared |
| Disk encryption | `diskEncryptionKey` absent: **Google-managed default encryption** (no CMEK, no CSEK). Any principal with the project compute rights can snapshot or restore it; there is no operator-held key to revoke |
| Disk resource policies | none |
| Local SSD | none (no `SCRATCH` disk; no `/dev/nvme*` block device) |
| PROD | `lilith-01` has its own zonal disk `lilith-01`, attached only to `lilith-01`. No DEV disk is shared with PROD |

The host confirms the single disk:
`/dev/sda` = `PersistentDisk` serial `persistent-disk-0`, with partitions
`sda1` (ext4 `/`, `8:1`), `sda15` (vfat `/boot/efi`), `sda16`
(ext4 `/boot`), and `sda14` (unmounted BIOS boot). No device-mapper
volumes, no md arrays, no LVM volumes (`lvm2` is installed but unused), no
swap, no NVMe or local SSD. The only other block devices are read-only snap
squashfs loop images.

## 4. Snapshot, image, and backup inventory

| Mechanism | Observed | Evidence |
| --- | --- | --- |
| Standard / archive snapshots | **none** in the project | `snapshots list` = `[]` |
| Instant snapshots | **none** | `instant-snapshots list` = `[]` |
| Snapshot schedules / resource policies | **none** in the project; none attached to the disk or the instance | `resource-policies list` = `[]`; `resourcePolicies` absent |
| Machine images | **none** | `machine-images list` = `[]` |
| Custom images / image families | **none** | `images list --no-standard-images` = `[]` |
| Disk clones | **none**: no `disks.insert` other than instance creation | audit log (below) |
| Backup and DR service | **not enabled** (`backupdr.googleapis.com` absent from the enabled services) | `services list --enabled` |
| Cloud Storage buckets | **none** in the project (so no exported disk image) | `storage buckets list` = empty |
| GCE application-consistent snapshot hooks | absent (`/etc/google`, `/etc/google/snapshots` do not exist) | probe |
| On-host backup software | absent: restic, borgbackup, duplicity, rsnapshot, timeshift, etckeeper, rdiff-backup, bacula, bareos, amanda. Only `rsync` exists, and no job uses it | `dpkg-query` |
| `/etc` in version control | absent (`/etc/.git`, `.etckeeper`, `.hg`, `.bzr` do not exist) | probe |
| Scheduled copy jobs | none. Timers are stock Ubuntu/GCE (apt, dpkg-db-backup, logrotate, sysstat, man-db, fstrim, e2scrub, tmpfiles-clean, oslogin cache, workload-cert refresh, motd/notifier). Cron holds only the stock `e2scrub_all`, `sysstat`, and daily apport/apt-compat/dpkg/logrotate/man-db/sysstat | `list-timers`, cron listings |
| `/var/backups` | stock dpkg/apt/alternatives rotations only (`dpkg-db-backup`). No lilith, credstore, custody, or systemd-credential file | listing |
| snapd snapshots | `No snapshots found.` | `snap saved` |
| Filesystem snapshots | not possible on the layout: ext4 on a raw partition; no LVM, btrfs, or ZFS volume | lsblk / mountinfo |

**Audit history (Admin Activity, entire project life).** The complete
compute method set ever called is: `firewalls.insert` (5),
`instances.insert` (4: two operations each for `lilith-01` on 2026-08-23 and
`lilith-dev-01` on 2026-09-13), `subnetworks.insert`, `routers.insert|patch`,
`networks.insert`, `projects.setCommonInstanceMetadata`, and
`instances.setIamPolicy`. There has **never** been a `createSnapshot`,
`snapshots.insert`, `instantSnapshots.insert`, `images.insert`,
`machineImages.insert`, a `disks.insert` from a source disk, an
`attachDisk`/`detachDisk`, `stop`/`start`/`reset`/`suspend`, or any
resource-policy call. (Admin Activity is written for every such call and
cannot be disabled; retention is 400 days, which exceeds the project's age.)

**Consequence for historical K-ACT material.** The host key was written at
2026-09-27 `06:31:41Z` and the CURRENT K-ACT blob at `07:15:31Z`. No
provider snapshot, image, machine image, or clone of the DEV disk has ever
existed, before or after PR-1A, so **no provider-held historical copy of
K-ACT or of the host key exists**. No snapshot artifact therefore needs an
RR-17 class.

## 5. Host storage map

Every persistent authority and custody path sits on the same filesystem:
ext4 `/dev/root` = `/dev/sda1`, `maj:min 8:1`, `st_dev 2049`, mounted at
`/`, on the one boot PD. `/proc/self/mountinfo` has 30 entries, and none is
mounted at or below `/etc`, `/var`, `/var/lib`, or `/opt`.

| Path | Now | Resolves to | Filesystem / device | Persistent | On boot disk | Captured by a disk snapshot | Rolls back with the others on whole-host restore |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `/var/lib/systemd/credential.secret` | exists (`0400`, inode 5768, 4112 B) | itself | ext4 `sda1` / 2049 | yes | yes | yes | yes |
| `/etc/credstore.encrypted` | exists | itself | same | yes | yes | yes | yes |
| `…/lilith-authority-dev.owner-actor.cred` (K-ACT) | exists (inode 1738, 219 B, `6a61c350…`) | itself | same | yes | yes | yes | yes |
| `/etc/lilith-authority-custody` (+`prepared/`, `retired/`) | exist, empty | themselves | same | yes | yes | yes | yes |
| `/etc/lilith-authority-dev` (+`trust/`, `registry/`, `owner/`) | exist, empty | themselves | same | yes | yes | yes | yes |
| `/etc/lilith-recovery-witness` (+`credentials/`) | exist, empty | themselves | same | yes | yes | yes | yes |
| `/var/lib/lilith-authority-custody` (+`holds/`) | exist, empty | themselves | same | yes | yes | yes | yes |
| `…/credentials/lilith-recovery-witness.witness.cred` (K-WIT) | future (PR-1B) | parent `credentials/` | same | yes | yes | yes | yes |
| `/etc/lilith-authority-dev/{trust,registry,owner}` content | future (PR-1B) | themselves | same | yes | yes | yes | yes |
| `/var/lib/lilith-authority-dev/authority_ledger.db` | future (PR-1B; `StateDirectory=`) | parent `/var/lib` | same | yes | yes | yes | yes |
| `/var/lib/lilith-recovery-witness` (`chain/`, `authorizations/`, `witness.json`, lock) | future (PR-1B; `ReadWritePaths=`) | parent `/var/lib` | same | yes | yes | yes | yes |
| `/var/lib/lilith-authority-custody/holds` records | future (PR-1B) | itself | same | yes | yes | yes | yes |
| `/opt/lilith-authority-dev` release, units, `/usr/local/sbin` CLIs | exist | themselves | same | yes | yes | yes | yes |

Future paths resolve through their nearest existing parent. No mount exists
beneath any of them, so they land on `sda1` unless a mount is added. Adding
one would be a change and is not authorized.

## 6. Runtime-only state

`/run` is `tmpfs` (RAM, `size=401820k`, `0:27`); `/run/credentials` is
inside it. `/tmp` and `/var/tmp` are **not** tmpfs: they are on `sda1`.
There is no swap, so RAM is never paged to the disk.

| Runtime object | Source | Now | Survives service restart | Survives VM reboot | Captured by a disk snapshot |
| --- | --- | --- | --- | --- | --- |
| `/run/lilith-authority-dev` (`0700 root`) | tmpfiles `d` line (installed) | absent | yes (the directory; `RuntimeDirectory=` is not used) | **no**: re-created **empty** at boot by `systemd-tmpfiles-setup` | no |
| `/run/lilith-recovery-witness` (`0710 root:lilith-authority-dev`) | tmpfiles `d` line (installed) | absent | yes (the directory) | **no**: re-created **empty** at boot | no |
| `/run/lilith-authority-dev/owner.sock` | socket unit, `RemoveOnStop=yes` | absent | depends on the socket unit, not the service | no | no |
| `/run/lilith-recovery-witness/{owner,signer}.sock` | socket units, `RemoveOnStop=yes` | absent | as above | no | no |
| `/run/credentials/lilith-authority-dev.service` | `LoadCredentialEncrypted=` decrypt at service start | absent | **no**: torn down at stop, decrypted again from the blob at the next start | no | no; its **source** blob and host key are |
| `/run/credentials/lilith-recovery-witness.service` | same, from the K-WIT blob | absent | no | no | no; its source is |
| service `PrivateTmp=` (both services) | `/tmp/systemd-private-*` | absent | no (removed at stop) | no | **yes while the service runs**, because `/tmp` is on `sda1` |
| process memory (loaded keys, in-memory witness head) | running services | none running | no | no | no; preserved across GCE live migration and would be preserved across a GCE suspend/resume, neither of which is a rollback. No suspend has ever been issued |

Runtime state has **no freshness role**. Everything a restarted service
knows it re-reads from `sda1`. A rollback of `sda1` is therefore invisible
to runtime state after the restore boot.

**Observation (not a PR-2 action).** The installed tmpfiles files mean the
pending kernel reboot will create empty `/run/lilith-authority-dev` and
`/run/lilith-recovery-witness`. The reviewed observer records both paths
under PR-1 objects. Whether `status --expect P1A-9` treats their
post-reboot presence as expected has not been checked (§13, OR-6).

## 7. Credential-secret coupling

| Fact | Evidence |
| --- | --- |
| K-ACT is sealed `--with-key=host` | keygen source `ENCRYPT_ARGV`; the attested CLI `1fa50327…` |
| future K-WIT is sealed `--with-key=host` | keygen source `WITNESS_ENCRYPT_ARGV` |
| no TPM binding is possible today | `/dev/tpm0` and `/dev/tpmrm0` exist (vTPM enabled), but no TSS library is installed (`tpm2-tss` / `libtss2-esys` absent), as the B1b-3d design recorded (`has-tpm2 = partial`). TPM sealing was deferred (T-2) |
| host key and K-ACT share a filesystem, disk, and snapshot domain | both `st_dev 2049` on `sda1` on the one PD |
| future K-WIT would share them | its directory is `st_dev 2049` on `sda1` |

**Conclusion.** Any disk snapshot, image, machine image, or clone of the DEV
boot disk taken at a time `T` would hold `credential.secret` and every blob
it seals as **one historical pair**: K-ACT at `T`, and K-WIT once it exists.
Host-key mode binds to no vTPM, instance, or external key. By systemd's
documented design, the pair therefore decrypts on **any** machine that
boots the restored disk or can read both files. This was not tested: nothing
was decrypted. Google-managed disk encryption does not change this, because
it is transparent to anyone with the project compute rights.

This is the case the owner accepted under T-2 (DEV_SYNTHETIC only; "not
whole-host or snapshot rollback protection"). Under RR-17, any such
snapshot is at least `KNOWN_CUSTODY_DEBT` inside an accepted, inventoried
environment. Outside that environment it is `EXPOSED_PRIVATE_MATERIAL`,
which means the RR-20b STOP. **Today no such snapshot exists (§4).**

**Who can create one.** Only principals with `compute.disks.createSnapshot`
(or the image, machine-image, or clone equivalents) on the DEV disk:

- the project-owner user;
- the default compute service account, which holds `roles/editor`. It is
  attached to no VM, and nobody holds actAs on it except through project
  ownership;
- Google's compute service agent.

The DEV VM's own service account cannot. The routine and PROD deployers hold
only `compute.viewer`, OS Login, IAP, and the `compute.projects.get` custom
role, and none of those holds a snapshot permission. Disk and instance IAM
policies add only `compute.osLogin` for the DEV deployer.

**Host-local copies are a separate path.** Root-equivalent principals on
DEV can copy both halves with ordinary file operations, which no cloud log
records. That set is the open DR-3 `ubuntu` account plus the PROD deployer's
project-level `osAdminLogin` (the known cross-environment debt,
[B1c acceptance](slice-15b2b-b1c-acceptance-record.md)). PR-2 cannot exclude
such copies (§13, OR-2).

## 8. Rollback-coherence matrix

"Disk-snapshot rollback" means restoring only the DEV boot disk from a
snapshot, image, or clone. "Whole-host rollback" means restoring the machine
(machine image or disk swap), which here is the same single disk. The GCE
restore paths all need a stop/start or a new instance, so a restore always
begins a new boot.

| # | Object | Location | Current / future | Persistent / runtime | Boot-disk captured | Disk-snapshot rollback | Whole-host rollback | Independently fresh after host rollback? | Authority meaning | Notes / limitations |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| A | K-ACT encrypted blob | `/etc/credstore.encrypted/lilith-authority-dev.owner-actor.cred` | current | persistent | yes | rolled back | rolled back | **no** | OWNER_ACTOR signing custody (`NOT_IN_HEAD`; grant absent) | a rolled-back slot presents an old credential as CURRENT (RR-17 `STALE_CREDENTIAL_PRESENT` after succession) |
| B | systemd host credential secret | `/var/lib/systemd/credential.secret` | current | persistent | yes | rolled back | rolled back | **no** | decrypts A and C | same disk as A and C: one historical pair (§7) |
| C | K-WIT encrypted blob | `/etc/lilith-recovery-witness/credentials/lilith-recovery-witness.witness.cred` | future | persistent | yes | rolled back | rolled back | **no** | witness signing custody | same host key as A |
| D | signed registry | `/etc/lilith-authority-dev/registry` (+ `trust/` anchors) | future | persistent | yes | rolled back | rolled back | **no** | K-ROOT-signed key registry | a K-ROOT signature authenticates an old version; it does not prove it is the latest |
| E | registry-head view | witness `chain/` head binding + ledger copy of the head (`authority_ledger.db`) | future | persistent | yes | rolled back | rolled back | **no** | which registry head is current | no out-of-snapshot copy of the head exists or is planned before PR-3 |
| F | authority ledger | `/var/lib/lilith-authority-dev/authority_ledger.db` | future | persistent | yes | rolled back | rolled back | **no** | RecoveryEpoch binding, consumed authorizations | a ledger-only rollback is detectable by a surviving witness (§10) |
| G | witness authoritative chain / state | `/var/lib/lilith-recovery-witness/chain/`, `authorizations/` | future | persistent | yes | rolled back | rolled back | **no** | monotonic head, K-WIT-signed | K-WIT signatures verify the old chain equally well |
| H | witness derived pointer | `/var/lib/lilith-recovery-witness/witness.json` | future | persistent | yes | rolled back | rolled back | **no** | derived; chain is authoritative (RR-9) | rolls back in step with G, so it stays self-consistent |
| I | custody holds | `/var/lib/lilith-authority-custody/holds` | future | persistent | yes | rolled back | rolled back | **no** | HELD/RELEASED ceremony state | a restored `HELD` or `RELEASED` record is indistinguishable from a live one on the host |
| J | prepared successor credential | `/etc/lilith-authority-custody/prepared` | future (rotation) | persistent | yes | rolled back | rolled back | **no** | successor custody before `S_CURRENT` | a rollback can remove a successor or revive an earlier one |
| K | retired credential | `/etc/lilith-authority-custody/retired` | future (rotation) | persistent | yes | rolled back | rolled back | **no** | predecessor evidence, logically destroyed | a rollback can restore a pre-retirement slot state; "logical destruction" is not rollback-proof |
| L | runtime-loaded service credential | `/run/credentials/<unit>.service` | future | runtime (tmpfs) | no | lost; re-derived from A/C + B at the next start | same | n/a: always re-derived from rolled-back A/C | loaded signing key | fresh RAM, stale source |
| M | runtime sockets / directories / process state | `/run/lilith-authority-dev`, `/run/lilith-recovery-witness`, sockets, memory | future | runtime (tmpfs / RAM) | no | lost; re-created empty at boot | same | n/a: holds no freshness | request channels only | recreated by tmpfiles/socket units |
| — | owner register / genesis pin (PR-3) | owner off-host (planned); on-host pin copy under `/etc/lilith-authority-dev/owner` | future | persistent (off-host part) | on-host copy only | on-host copy rolled back | on-host copy rolled back | **off-host part only, once it exists** | owner genesis pin, register | **does not exist** (PR-3 not done) |
| — | K-ROOT | owner off-host (existence UNKNOWN, preflight B-26) | future | off-host | no | no | no | not freshness state | signs registry and epoch transitions | authenticates but does not order |
| — | cloud Admin Activity audit log | Google Cloud Logging | current | external | no | no | no | yes, but **consumed by no verifier** | none | records cloud snapshot/restore/stop/start calls; does **not** record host-local file copy or restore by root |

Separate directories, owners, services, and keys do not appear as
independence anywhere in the matrix. The evidence shows one filesystem and
one disk.

## 9. Central architectural test

> If the DEV boot disk is snapshotted at time `T` and restored later, can
> the restore simultaneously roll back K-ACT custody, K-WIT custody,
> registry, authority ledger, witness state, and custody holds?

**YES.** A, B, C, D, E, F, G, H, I, J, and K all live on `/dev/sda1`
(`st_dev 2049`) on the single zonal PD `lilith-dev-01`. There are no other
disks, no mounts below the authority paths, no local SSD, and no off-host
state that any verifier consumes.

**WHOLE-HOST / WHOLE-DISK ROLLBACK CAN PRESENT A SELF-CONSISTENT OLD
AUTHORITY WORLD.**

After such a restore, every on-host verifier would see all of these at `T`,
mutually consistent:

- a K-ACT blob and its host key;
- a K-WIT blob;
- a K-ROOT-signed registry;
- a ledger whose epoch binding matches;
- a K-WIT-signed witness chain whose head matches that registry and ledger;
- matching holds.

No independently preserved component exists (§11).

### 9.1 Coverage by restore path

| Restore path | Exists now | Scope | Rolls back all of A–K together |
| --- | --- | --- | --- |
| disk snapshot → new disk → boot-disk swap or new VM | no snapshot exists; creatable by §7 principals | whole disk | yes |
| machine image → new VM | none exists; creatable by the same principals | whole disk + instance config | yes; the vTPM state is irrelevant because nothing is TPM-sealed |
| disk clone (`disks.insert --source-disk`) | none ever | whole disk | yes |
| provider backup (Backup and DR) | service not enabled | — | would be whole disk if enabled |
| filesystem-level backup on host | none (§4) | — | — |
| host-local manual copy by root | cannot be excluded (DR-3, cross-environment `osAdminLogin`) | any subset, chosen by the copier | **any subset**, including a ledger-only or witness-only rollback |

## 10. Witness interpretation

The existing rule is preserved: **a same-host witness can detect a
ledger-only rollback if the witness state survives it.** That holds here,
narrowly. If only `authority_ledger.db` is restored (for example, a
root-local file restore of F), then G stays ahead of F, and the witness
refuses the stale ledger.

```text
ledger-only rollback  != whole-host rollback
```

- **Ledger-only rollback.** It is detectable, provided G survives. On this
  host, G survives only because nobody restored it too. Nothing structural
  preserves G separately from F: same filesystem, same disk, same root.
- **Witness-only rollback.** G (and H) are restored while F is not. The
  ledger is then ahead of the witness. Detection depends on the ledger
  cross-check. Nothing out of band protects it.
- **Whole-host / whole-disk rollback.** F and G roll back **together** and
  remain consistent with each other, with D, and with I. The witness cannot
  detect it, because its only reference for "latest" is itself.

**Independent persistence for witness freshness outside the snapshot
domain: NONE.** There is no second disk, regional or async replica, off-host
witness, remote monotonic counter, TPM NV counter (the vTPM is present but
unused, and its instance-bound state would survive a disk restore on the
same instance), or out-of-band head register. The only planned candidate is
the PR-3 owner off-host register (genesis pin / register material). It does
not exist, and nothing today defines it as a monotonic freshness source.

**WHOLE-HOST ROLLBACK RESISTANCE = NOT ESTABLISHED.** That is acceptable
for PR-2, and it is the same status every prior B1b-3 record carries.

## 11. Security-model result

Each property is classified separately. No single "rollback protected"
boolean exists.

| Property | Result | Basis |
| --- | --- | --- |
| `ROLLBACK_LEDGER_ONLY` | **DETECTABLE, conditional**, once PR-1B exists: requires the witness state to survive (same host, same disk, no structural separation) | §10 |
| `ROLLBACK_WITNESS_ONLY` | **CONDITIONAL**: relies only on the ledger/witness cross-check; no out-of-band reference | §10 |
| `ROLLBACK_CREDENTIAL_ONLY` | **NOT PREVENTED on host**: a restored slot is caught only by the registry/witness binding (RR-19 inventory, loaded-key binding) while those are not rolled back too | §8 rows A, C, J, K |
| `ROLLBACK_BOOT_DISK` | **NOT DETECTABLE on host**: all of A–K roll back coherently | §9 |
| `ROLLBACK_WHOLE_HOST` | **NOT DETECTABLE on host; NOT ESTABLISHED**: equivalent to boot-disk rollback here (single disk; nothing TPM- or instance-bound) | §9.1 |
| `ROLLBACK_EXTERNAL_STATE` | **NO EXTERNAL FRESHNESS STATE EXISTS.** The cloud Admin Activity log would record provider snapshot and restore calls, but no verifier consumes it, and it does not see host-local file restores | §4, §8 |

## 12. Hidden-assumption check

> What assumption could make this design appear correct while it is wrong?

**"Because the authority signer and recovery witness are separate services,
their persistence is independent."** The storage topology does **not**
support this. The signer and the witness have:

- separate users (995 / 994);
- separate units, sockets, and signing keys (K-ACT / K-WIT);
- separate state directories (`/var/lib/lilith-authority-dev`,
  `/var/lib/lilith-recovery-witness`).

Every one of those lives on the same ext4 filesystem on the same zonal PD,
under one root, sealed by one host key, and inside one snapshot domain. The
separation defends against a compromised **service** or **application
principal**, which is what it was designed for. It does not defend against
a rollback of the **disk**. Service separation is not failure-domain
separation.

Related assumptions that fail the same way:

1. **"Signed state is fresh state."** K-WIT, K-ROOT, and registry
   signatures verify an old chain, head, or registry exactly as well as the
   latest one. Signatures give authenticity, not recency. Cryptographic
   separation is not rollback separation.
2. **"Encrypted credentials are safe in a snapshot."** False for
   host-key mode: the snapshot carries the decryption secret beside the
   blob (§7).
3. **"The vTPM makes this host-bound."** The vTPM is present but seals
   nothing: TSS is absent and T-2 chose host-key mode.
4. **"No snapshot schedule means no snapshot risk."** No snapshot exists
   today, but the owner, the editor-role default compute SA, or the service
   agent could create one without any host-side trace. A root-local copy
   needs no cloud call at all.
5. **"Logical destruction / retirement is final."** A rollback restores
   pre-retirement slot and hold state (rows J, K, I).
6. **"The genesis pin makes the chain monotonic."** The Source Prep A
   record already states that a pinned genesis is not external
   monotonicity. The on-host pin copy rolls back too.

## 13. Open risks (carried; none remediated)

| ID | Risk | Status |
| --- | --- | --- |
| OR-1 | whole-host / whole-disk rollback presents a self-consistent old authority world (§9) | **OPEN**; not established |
| OR-2 | host-local copies of blob + host key by root-equivalent principals (DR-3 `ubuntu`; PROD deployer project-level `osAdminLogin`) cannot be excluded by inventory | **OPEN** (DR-3, cross-environment debt) |
| OR-3 | project-level principals able to snapshot, image, or clone the DEV disk (owner user; default compute SA via `roles/editor`; compute service agent); Google-managed encryption offers no revocable operator key | **OPEN**, bounded; no such artifact exists today |
| OR-4 | no independent freshness source for the witness or registry head (PR-3 not done; no monotonic external store defined) | **OPEN** |
| OR-5 | kernel reboot pending (`reboot-required` present; boot `24d1771d…` continues) | **OPEN**, carried |
| OR-6 | the next boot will create empty `/run/lilith-authority-dev` and `/run/lilith-recovery-witness` from the installed tmpfiles files; whether `status --expect P1A-9` and the observer expect that is unverified | **NEW**, observation only |
| OR-7 | `PrivateTmp=` scratch space for both services is on `sda1` (not tmpfs), so anything a running service writes to `/tmp` is on the snapshot domain while it runs | **NEW**, observation only |
| OR-8 | a future snapshot, image, or clone of the DEV disk would need RR-17 classification before any entry; no control prevents one from being created | **OPEN**; any future artifact makes this inventory stale |
| OR-9 | inventory of other owner projects: `au4-vault` holds no snapshot, image, or machine image; the other two have the Compute API disabled. Cross-organization projects invisible to this account are not covered | **LIMIT** |

## 14. Explicit nonclaims

PR-2 does **not** claim:

- rollback resistance of any kind (ledger-only detection is conditional and
  exists only after PR-1B);
- independent witness freshness;
- real authority readiness, or any `FULL_READINESS`;
- K-WIT custody (no K-WIT exists);
- registry authority (no registry exists);
- owner acceptance of this inventory, or of any RR-17 environment bound;
- `INITIAL_CUSTODY`;
- PR-1B readiness, or satisfaction of the PR-2 precondition, until the
  owner accepts this record (§20 of the preflight);
- First Memory readiness;
- that K-ACT is free of host-local copies (OR-2), or that it is exposed.
  The only finding is that **no provider-level copy exists**.

## 15. Result

| Item | Result |
| --- | --- |
| Cloud topology | complete (§3) |
| Snapshot / image / backup inventory | complete: **none exist, none ever existed** (§4) |
| Host storage map | complete: **one filesystem, one disk** (§5) |
| Runtime-state analysis | complete (§6) |
| Credential-secret coupling | same snapshot domain (§7) |
| Central test | **YES**: self-consistent old authority world possible (§9) |
| Independent freshness state | **none** (§10) |
| Whole-host rollback resistance | **NOT ESTABLISHED** |
| Required observations blocked by a stop condition | none |
| DEV / cloud mutation | **none**. Host `stableSha256` equals the M-A10 POST. The gcloud prompt to enable the Compute API in the two other projects was declined automatically (non-interactive stdin), and the API remains disabled there (verified) |

**Classification: `PR2_INVENTORY_COMPLETE`.**

The owner accepts or rejects this record separately. PR-3 foundation is
next in the accepted order (§20). Neither PR-3 nor PR-1B is authorized by
this record.

```text
READ-ONLY ONLY            NO SNAPSHOT CREATED        NO SNAPSHOT DELETED
NO CLOUD RESOURCE CHANGED NO DEV STATE CHANGED       NO SERVICE LIFECYCLE CHANGE
NO CREDENTIAL GENERATED   NO CREDENTIAL DECRYPTED    NO K-WIT
NO REGISTRY               NO LEDGER                  NO WITNESS STATE
NO HOLD RECORD            NO RECOVERY EPOCH
PR-1B NOT AUTHORIZED      FIRST MEMORY NOT AUTHORIZED
```
