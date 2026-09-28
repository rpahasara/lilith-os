# Slice 15B2b-B1b-3e — PR-1A Read-Only Live Preflight (Pass 1)

Status:

- **READ-ONLY LIVE PREFLIGHT**
- **NO LIVE MUTATION**
- **PR-1A INSTALL NOT YET AUTHORIZED** (Pass 2 needs a separate owner
  authorization)
- **B1b-3e LIVE REHEARSAL NOT AUTHORIZED**
- **WHOLE-HOST ROLLBACK UNRESOLVED**; **REAL AUTHORITY ABSENT**
- Result: **`PR1A_PREFLIGHT_PASS`**

Branch `claude/15b2b-b1b3e-pr1a-inert-install`, base protected main
`3848ab0e0641438c78d53eee26e5b20db7e612d4` (the merge of PR-1S, PR #90).
The streamed control tools come from that same commit
(`CONTROL_SHA=3848ab0e0641438c78d53eee26e5b20db7e612d4`).

This record observes the live DEV_SYNTHETIC host against the accepted
baseline that the
[PR-1 preflight](slice-15b2b-b1b3e-pr1-live-install-preflight.md) (§4, §6.2,
§24) and [PR-1S](slice-15b2b-b1b3e-pr1s-runtime-wiring.md) (§4) require
before `UPGRADE_EXISTING_DEV_SYNTHETIC`. It also resolves the values the
preflight classifies as **UNKNOWN_UNTIL_LIVE_PREFLIGHT**. It installs,
repairs, and normalizes nothing.

```text
preflight PASS          != PR-1A authorized
preflight PASS          != custody readiness
baseline recorded       != baseline accepted by the owner
DR-5 PASS               != owner authority
broker preservation     != authority proof
```

## 1. Live contact

| Item | Value |
| --- | --- |
| Observation window | 2026-09-28 `10:38:21Z` (first contact) to `10:47:11Z` (final probe) |
| Target | `lilith-dev-01`, `asia-southeast1-b`, project `lilith-agent-260823-27389` (GCE instance id `7687007163730582258`). DEV only |
| PROD (`lilith-01`) | **not contacted** |
| Mechanism | `gcloud compute ssh lilith-dev-01 --tunnel-through-iap` (the owner IAP / OS Login session, L2 runbook §9). Each tool was streamed as gzip+base64 inside `--command` into `sudo /usr/bin/python3 -I -B - <args>`. Nothing was copied to the host and no bytecode was written |
| Principal | OS Login user `ravindupahasara2_gmail_com`, with `sudo` to root (euid 0), the existing accepted operator path. No new principal. No IAM, WIF, or sudoers change |
| Privilege boundary | operator → root through the existing `sudo`, as in every earlier B1b-3d read-only step. No `sudo -u` to any service or deployer identity |
| Unavoidable side effects | IAP / OS Login session and `sudo` accounting records (journal, lastlog), as in every earlier inspection. The installer's `status` read the CURRENT ciphertext, the unit files, and `/etc/shadow` (for the lock flag) with ordinary reads on a `relatime` mount, so their **atime** may have advanced. The ad-hoc probe used `O_NOATIME`. No mtime, ctime, inode, size, owner, or mode changed (§6 re-probe) |

Tools run, all read-only:

| Tool (SHA-256 at `CONTROL_SHA`) | Operation | Result |
| --- | --- | --- |
| `services/authority-dev/ceremony/install_authority_dev.py` (`fe10d9a3…5487`) | `upgrade-baseline 9ac7de22…062b` (P1A-0) | `result=PASS` |
| same | `status --expect L2b.2 9ac7de22…062b` | `result=PASS`, `failures=[]` |
| `scripts/verify_broker_dev_current_incarnation.py` (`bbca69bc…b85b0b`) | `preservation` | `BROKER_PRESERVATION=PASS` |
| `scripts/probe_needrestart_lilith_override.py` (`edd23ac7…b2db`) | `probe` | `NEEDRESTART_LILITH_OVERRIDE=PASS` |
| `/usr/local/sbin/lilith-activation-verify` (installed; bytes = `scripts/dev_deployer/lilith_activation_verify.py`, `44046cae…a32`) | no arguments | `ACTIVATION=NOT_ACCEPTED reason=GRANT_ABSENT advisoryConfigEnabled=false` |
| ad-hoc stat probe (session scratch, **not** repository source; SHA-256 `163b206b…38ab`) | run twice, 6 min apart | `lstat`, directory listings, `O_NOATIME` ciphertext hashing, `systemctl show`, GCE metadata. Never opens `credential.secret` (hard refusal in code) |

DR-5 was **not** executed from the operator session. The accepted DR-5
evidence is a real routine run as the deployer (§11).

## 2. Host identity (§4)

| Fact | Observed | Pinned value | Match |
| --- | --- | --- | --- |
| hostname | `lilith-dev-01` | installer `DEV_HOSTNAME` | yes |
| machine-id | `ae929170e6fa4c8ab9cc7b9547238d9d` | installer `DEV_MACHINE_ID`; custody design §host | yes |
| GCE metadata | name `lilith-dev-01`, zone `asia-southeast1-b` | same | yes |
| boot ID | `24d1771d-e1b5-4e5f-816d-da08ad8b367a` | custody design; broker baseline boot | yes (no reboot since 2026-09-13) |
| uptime | 1 269 739 s (≈ 14.7 days) | consistent with the 2026-09-13 boot | yes |
| OS / kernel | Ubuntu 24.04.4 LTS, `6.17.0-1022-gcp` | custody design | yes |
| timezone | `/etc/localtime -> /usr/share/zoneinfo/Etc/UTC` | — | informational |
| swap | none active (`/proc/swaps` has only its header) | ceremony requirement D-S | yes |
| `/var/run/reboot-required` | present | known pending since 2026-09-14 (runtime baseline §10) | known; see D-6 |
| root filesystem | ext4 `/dev/root`, `8:1`, `st_dev=2049`, `rw,relatime` | — | recorded |

## 3. Installed authority-dev release (§5)

| Fact | Observed |
| --- | --- |
| `/opt/lilith-authority-dev` | dir `root:root 0755`, entries exactly `current`, `releases` |
| `releases/` | exactly one entry, `9ac7de22bf977385ceb954624677e33f0bae062b` (dir `root:root 0755`); no staging or temporary name |
| selector | `current -> releases/9ac7de22bf977385ceb954624677e33f0bae062b` (symlink) |
| manifest | `release-manifest.json` SHA-256 `c9f2f76e6f498be8e6b6deda56f216294935fa7bdc7a4f14bfe812daa670370d`; role `lilith-authority-dev-synthetic-owner-actor-release-v1`, `candidateSha=9ac7de2…`, expected host and machine-id = DEV |
| manifest / tree | 23 manifest files. Every file matches by bytes and size. No extra file outside `venv/`, no symlink or special file outside `venv/`, all `root:root`, modes `0644`/`0755`. Non-venv tree digest `ac62b1dd…a991` |
| venv | 1391 entries; file-set digest `03bf7233a08423b2a7418d84792e596e8d88c1acba381036b9871f174d5f9165` (drift reference for PR-1A, preflight §23) |
| installed unit | `/etc/systemd/system/lilith-authority-dev.service` `root:root 0644`, SHA-256 `249f2ec9568d32848fbd9535940d37bdbbe5db78146cf3708cb067116b62b1bc` = release asset = `git show 9ac7de2` = preflight B-1 |
| installed socket | `…/lilith-authority-dev.socket` `bff5e9275ad1478dd068855465d65542ceb338e5e9236e43d1bd43d7c50c194f` = release asset |
| installed tmpfiles | `/etc/tmpfiles.d/lilith-authority-dev.conf` `2a1891ef3c4e3e0c2916eece828c37f98f6edace9bb5bf27846c4eb28944a51e` = release asset |
| installed CLI | `/usr/local/sbin/lilith-authority-keygen-dev` `root:root 0755`, `f1e7020b8ef7dd5610945abbc79b1fb716e75bf15daccd42ec3febaac2d81232` = release `cli/` member = preflight B-1 |

Installed release = **`9ac7de22bf977385ceb954624677e33f0bae062b`**, as
accepted. No later record supersedes it.

## 4. Authority service state (§6)

| Unit | LoadState | Active / Sub | UnitFileState | NeedDaemonReload | NRestarts | MainPID | Start timestamps |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `lilith-authority-dev.service` | loaded | inactive / dead | `static` | no | 0 | 0 | `ExecMainStart`, `InactiveExit`, `ActiveEnter`, `InvocationID` all empty |
| `lilith-authority-dev.socket` | loaded | inactive / dead | `static` | no | — | — | all empty; `Listen=/run/lilith-authority-dev/owner.sock` |

- There are no enablement links for any authority or witness unit under
  `/etc/systemd/system/*/`. There are no drop-ins.
- `WorkingDirectory=/opt/lilith-authority-dev/current`,
  `User=Group=lilith-authority-dev`, `StateDirectory=lilith-authority-dev`.
- The unit file has exactly one credential directive:
  `LoadCredentialEncrypted=owner-actor-signing-key:/etc/credstore.encrypted/lilith-authority-dev.owner-actor.cred`.
- `InaccessiblePaths=/etc/credstore.encrypted /etc/lilith-memory-broker /var/lib/lilith-memory-broker /etc/lilith-os-dev`.
  This is the `9ac7de2` form, without the custody root (PF-4, expected; D-4).
- **Never started:**
  - no start timestamp in this boot, the only boot since creation;
  - no `/var/lib/lilith-authority-dev` (the `StateDirectory=`);
  - no `/run/lilith-authority-dev`;
  - `/run/credentials/` is empty.
- No signer process exists. Nothing was stopped or changed.

## 5. Signer account (§7)

| Fact | Observed |
| --- | --- |
| name | `lilith-authority-dev` (user and group) |
| uid / gid | **995 / 985**. These resolve preflight B-11, `UNKNOWN_UNTIL_LIVE_PREFLIGHT`. They agree with the owner-reported L1a value |
| supplementary groups | none (`getgrouplist` = `[985]` only); group has no members |
| shell / home | `/usr/sbin/nologin` / `/nonexistent` (absent) |
| collisions | no other account holds uid 995 or gid 985 |
| contract | installer L1a contract PASS inside `status --expect L2b.2`: system uid < 1000, primary group only, password locked, `sudo -n -l -U` "not allowed". No sudoers file names an authority or witness account |

## 6. CURRENT K-ACT credential (§8)

| Fact | Observed |
| --- | --- |
| path | `/etc/credstore.encrypted/lilith-authority-dev.owner-actor.cred` |
| type | regular file (`lstat`), not a symlink, `nlink=1` |
| owner / mode | `root:root` (0:0), `0600` |
| `st_dev` | `2049` (`8:1`) |
| inode | `1738` |
| size | `219` |
| `mtime_ns` | `1790493331258019177` |
| `ctime_ns` | `1790493331258019177` |
| SHA-256 (ciphertext) | `6a61c350e848a833868f4573982fca9c75e2af79ccc9bd3716ae0303c26973f3` = accepted (B-5) |

The blob was never decrypted or copied, and the signer was not run. Every
field was identical in both probe runs (`10:40:55Z`, `10:47:11Z`) and in the
installer's `upgrade-baseline` output between them.

## 7. Credential-store inventory (§9)

- **`/etc/credstore.encrypted`:**
  - the directory: `root:root 0700`, inode 526, `st_dev 2049`, `nlink 2`;
  - its entries: **exactly one**, the CURRENT blob above;
  - no other blob, symlink, subdirectory, or special file.
  - Invariant holds: *K-ACT credstore == one CURRENT blob*.
- **`/etc/credstore`** (plaintext store, outside the judged namespace):
  `root:root 0700`, mtime 2024-04 (the distribution package default), and
  empty (D-5).
- **Not present:**
  - `/run/credstore` and `/run/credstore.encrypted`;
  - `/usr/lib/credstore` and `/usr/lib/credstore.encrypted`;
  - `/usr/local/lib/credstore` and `/usr/local/lib/credstore.encrypted`.

## 8. Host credential secret (§10), stat only

`/var/lib/systemd/credential.secret` was `lstat`ed and never opened, read,
or hashed:

- type: regular file, `nlink 1`;
- owner and mode: `root:root 0400`;
- `st_dev 2049`, inode `5768`, size `4112`;
- `mtime_ns 1790490701237702273`, `ctime_ns 1790490701241702264`.

Its parent `/var/lib/systemd` is `root:root 0755`. This matches B-10:
PRESENT_SECURE, in both the installer's prerequisites and DR-5.

## 9. PR-1 object absence (§11, §20)

Every object below was `lstat`ed and is **absent**
(`EXPECTED_ABSENT`). None is `UNEXPECTED_PRESENT`.

| Group | Paths |
| --- | --- |
| custody root / slots | `/etc/lilith-authority-custody`, `…/prepared` (PREPARED), `…/retired` (RETIRED) |
| hold store | `/var/lib/lilith-authority-custody`, `…/holds`; superseded single-file hold `/etc/lilith-authority-dev/hold` |
| K-WIT | `/etc/lilith-recovery-witness`, `…/credentials`, `…/credentials/lilith-recovery-witness.witness.cred`; superseded `/etc/credstore.encrypted/lilith-recovery-witness.witness.cred` |
| witness state / runtime | `/var/lib/lilith-recovery-witness` (no chain, pointer, or V2 genesis), `/run/lilith-recovery-witness`, `/run/credentials/lilith-recovery-witness.service` |
| authority config / registry / owner inputs | `/etc/lilith-authority-dev` and `…/{trust,registry,owner}` (no anchors, registry, genesis pin copy, or owner register copy) |
| ledger / signer state | `/var/lib/lilith-authority-dev`, `…/authority_ledger.db`, `/run/lilith-authority-dev`, `/run/credentials/lilith-authority-dev.service` |
| witness account | `lilith-recovery-witness`: no user, no group |
| witness units | the three files `lilith-recovery-witness{.service,-owner.socket,-signer.socket}` are absent, and systemd reports `LoadState=not-found`; `/etc/tmpfiles.d/lilith-recovery-witness.conf` is absent |
| PR-1 root CLIs | `/usr/local/sbin/lilith-authority-{ledger,hold,verify,recovery}-dev`, `/usr/local/sbin/lilith-recovery-witness-owner-dev` |

These are `EXPECTED_EXISTING` (B1b-3d L1a…L2b.2): the signer account, the
`9ac7de2` release tree and selector, the two authority unit files and the
tmpfiles file, the keygen CLI, the credstore and CURRENT, and the host key.

The LILITH namespace inventory has nothing beyond the accepted baseline:

- `/etc`: `lilith-memory-broker`, `lilith-os-dev`;
- `/opt`: `lilith-authority-dev`, `lilith-memory-broker`,
  `lilith-stage3-a2-final-v1`, `lilith-trusted-controls`;
- `/var/lib`: `lilith-memory-broker` plus the Stage III attempt markers;
- `/usr/local/sbin`: `lilith-activation-verify`,
  `lilith-authority-keygen-dev`, `lilith-dev-deploy`;
- `/etc/tmpfiles.d`: the authority and broker files;
- `/run`: `lilith-dev-deploy.lock`, `lilith-memory`.

## 10. Authority state directory (§12)

`/var/lib/lilith-authority-dev` is **absent**. That means there is no
authority ledger or state database of any kind, which matches the pre-PR-1
baseline (B-17, closure §6).

## 11. Activation, DR-5, broker, needrestart (§13–§16)

**Activation.**
- Result: `ACTIVATION=NOT_ACCEPTED reason=GRANT_ABSENT advisoryConfigEnabled=false` (exit 1).
- `/etc/lilith-os-dev/activation/` is empty.
- The installed verifier's bytes equal the reviewed source.

**DR-5 routine-deployer boundary.** The evidence comes from the post-merge
routine run for `3848ab0` itself:

| Item | Value |
| --- | --- |
| Run | workflow run `36408531112` |
| Classification | `DEPLOY_REQUIRED` |
| DR-5 step window | `10:15:24Z`–`10:17:34Z` |
| Job end | `10:20:15Z` |
| Deployer identity | `sa_112096412008414111981` |
| Effective-sudo proof | `SUDO_EFFECTIVE_PROOF=PASS mode=self` |
| Base ladder line | `AUTHORITY_BOUNDARY_PROOF=PASS maturity=L1c.3` |
| PR-1 ladder line | `PR1_AUTHORITY_BOUNDARY maturity=PR1_ABSENT` |

- **Non-vacuous denials:**
  - `sudo -u` to `lilith`, `lilith-memory-broker`, and `lilith-authority-dev`;
  - every authority and witness unit verb (query-only);
  - write on the release tree, the unit files, the tmpfiles file, and the
    keygen;
  - the keygen, with and without `actor`;
  - `-r` and `-w` on `credential.secret`;
  - `-r`, `-w`, and `-x` on `/etc/credstore.encrypted`.
- **CURRENT:** `UNOBSERVABLE_BY_DESIGN`.
- **Absent PR-1 objects are `DEFERRED_UNTIL_OBJECT_EXISTS`, never
  "denied":** the five CLIs, the custody root, the witness units, the
  skeleton, `/var/lib/lilith-authority-custody`, the K-WIT blob, the holds,
  and the ledger. The witness `sudo -u` is deferred (proxy probe only).
- **Polkit:** `DEFERRED_NOT_IN_GATE` (`pkcheck_rc=2`), by design.
- The run's routine core-api deployment happened before this preflight,
  and it is the routine path that DR-5 exists to prove harmless (D-2).

**Broker preservation.**

| Fact | Value |
| --- | --- |
| Result | `BROKER_PRESERVATION=PASS`, `failures=[]` |
| Incarnation | `42af2691b8d24ee5a92a286197c5444c` (`InvocationID`) |
| Process | PID `132976`, start `2026-09-26T06:34:08Z`, ticks `108213277`, `NRestarts=0` |
| Boot | `24d1771d…` |
| Release | `817a83e44cec8965479fd97fc30b7a0b3ae49ab2`; manifest `7a46ac83…4614` |
| Shared libraries digest | `40e68a1c27328c27b811da19bb17a1262cbacff18dcd7ab397e06bebb17a87bd` |
| `baselineCandidateSha256` | `3549585487ad46ead96a0cb1af30a15be0c4ac17575663816e8e11dc80a7eee5` = accepted |

- Equivalent: release, config, state, identity boundary, socket boundary,
  and deployer policy text. Stage III is untouched.
- `processContinuity=false` is expected. It compares against the
  historical Stage II process (DR-1), not against the accepted incarnation.
- `authorityCustodyJudgment=NOT_PERFORMED`,
  `authorityMaturity=NOT_ESTABLISHED_BY_PRESERVATION`.
- Of the PR-1 `CUSTODY_PATHS`, only the accepted B1b-3d objects are
  present. Every PR-1 path is reported absent.
- The broker was not restarted.

**needrestart.**
- Result: `NEEDRESTART_LILITH_OVERRIDE=PASS`, `failures=[]`.
- The snippet: `/etc/needrestart/conf.d/lilith-authority-sensitive.conf`,
  `root:root 0644`, SHA-256
  `503279315ccc884d8a68505c86b51dfd09387b393c9becba684b1fa1c28068d2`. That
  is the accepted artifact and the installer's `NEEDRESTART_SHA256`.
- `EXCLUDED`: `lilith-memory-broker.service`,
  `lilith-authority-dev.service`, and `lilith-recovery-witness.service`.
  Every control unit is `DEFAULT`. `restart=DEFAULT`.
- The main `needrestart.conf` SHA-256 is `baacdd68…f7ee` (recorded, not
  pinned).

## 12. Filesystem relationships (§17)

The `st_dev` is `2049`: ext4 `/dev/root`, `8:1`, mounted at `/`. It is the
same for the following:

- CURRENT and `/etc/credstore.encrypted`;
- `/etc`: the nearest existing parent of `/etc/lilith-authority-custody`
  and its `prepared/` and `retired/`, and of `/etc/lilith-recovery-witness`
  and `/etc/lilith-authority-dev`;
- `/var/lib`: the parent of `/var/lib/lilith-authority-custody/holds`,
  `/var/lib/lilith-recovery-witness`, and `/var/lib/lilith-authority-dev`;
- `/var/lib/systemd` and the host key;
- `/opt/lilith-authority-dev`, `/usr/local/sbin`, and `/etc/systemd/system`.

No separate `/etc`, `/var`, `/var/lib`, or `/opt` mount exists. The other
mounts are `/boot` (`259:0`), `/boot/efi` (`8:15`), and `/run` (tmpfs
`0:27`, runtime only). The future CURRENT / PREPARED / RETIRED layout would
**not** cross filesystems: `st_dev(credstore) == st_dev(/etc) == 2049`.
Nothing was created to establish this.

## 13. Snapshot inventory and owner register (§18, §22)

```text
SNAPSHOT_INVENTORY=NOT_COMPLETED_PR2
OWNER_OFF_HOST_REGISTER=NOT_COMPLETED_PR3
```

Only the mount and filesystem facts in §12 were collected. There was no
provider listing of disks, snapshots, machine images, or schedules. No
snapshot-safety claim is made. PR-1A may precede PR-2 under an explicit
nonclaim (preflight §21). No owner pin, register, or K-ROOT exists on the
host (§9), and nothing about off-host material is claimed.

## 14. Candidate PR-1S release (local, not transferred)

Computed on the workstation from clean merged main `3848ab0`
(`python services/authority-dev/release_file_set.py`). No archive was
built, no attestation was produced, and nothing was copied to DEV.

| Field | Value |
| --- | --- |
| merged main (candidate NEW `RELEASE_SHA`) | `3848ab0e0641438c78d53eee26e5b20db7e612d4` |
| role | `lilith-authority-dev-synthetic-release-source-v2`, `SOURCE_PREPARED_NOT_INSTALLED` |
| runtime payload | 53 files plus 6 `cli/` members |
| `runtimeDigests.authority` | `4b32f169fb5d83873d574845fb8a38bbae31a904be941fc2411b0d4202a9671b` |
| `runtimeDigests.rootTooling` | `28e9d6cbdb0d2642074d10c4d8dc9e83c9c7b19f90c6676248b920cd6c47b903` |
| `runtimeDigests.witness` = `witnessManifestSha256` | `5137ddb03c3c1b17fceb400cee70a5e0b057c02f1c9138722f1260db1564d3c3` (role `lilith-recovery-witness-dev-synthetic-source-v1`) |
| `assets/lilith-authority-dev.service` | `11b6d00f04d998caa156875fb587dd642cb7d78dd9b6d1866616cc0b9bc1b254` (changes from `249f2ec9…`) |
| `assets/lilith-authority-dev.socket` | `bff5e927…194f` (unchanged) |
| `assets/lilith-authority-dev.tmpfiles.conf` | `2a1891ef…a51e` (unchanged) |
| `assets/lilith-recovery-witness.service` | `9f78130c06491d184aff7066de99f804bf3816e171c63d6f70b734b1c6e85d7d` |
| `assets/lilith-recovery-witness-owner.socket` | `d260917fb31e9c76341fba131bafdc2802b80c0cf2fdcffb8cecc6e176440beb` |
| `assets/lilith-recovery-witness-signer.socket` | `ad345d18747c30a7c2a93cb18d5be310dc091f5efe07fc6e1606efbc099bb9c7` |
| `assets/lilith-recovery-witness.tmpfiles.conf` | `c3491d517aa70ff960e1dba4410378efcecc134737282136aad77a5a9d200be0` |
| `cli/lilith-authority-keygen-dev` | `1fa50327bb9cb402dc38f6e8a3742362901ba4dbd5c48f8474dc7c6c4e134472` (changes from `f1e7020b…`) |
| `cli/lilith-authority-ledger-dev` | `fda779cd0dcecdc26e371082078306978f97e4f7097acae780fa6f38180fc45b` |
| `cli/lilith-authority-hold-dev` | `ad3fbc9442db715595683f4602e8b2fd62d22697703e888eda2ef30c0121da1b` |
| `cli/lilith-authority-verify-dev` | `bc331636eedbbae22a53667aa230ba0672fb1e22b8a5bd4975ac9f8557a400a4` |
| `cli/lilith-authority-recovery-dev` | `ad928f8d56062763da156084f5375c23dabfdcced396a065ba4cc2719e01cc74` |
| `cli/lilith-recovery-witness-owner-dev` | `9fce2e460a9c279f99b59c6e251b813375a1be404ae611d379fed5cd812f16ab` |
| archive / attestation / release manifest SHA-256 | **not yet produced**. They come from the owner's two independent workstation builds (preflight §23, RR-38) before Pass 2 |

The authority, witness, and root-tooling digests equal the PR-1S record §3.

## 15. Observed baseline for the owner (P1A-0)

The `upgrade-baseline` output, for the owner to record off-host as the
`UPGRADE_EXISTING_DEV_SYNTHETIC` baseline input (it is not accepted by this
record):

```json
{
  "baselineType": "LILITH_AUTHORITY_DEV_UPGRADE_BASELINE", "schemaVersion": 1,
  "oldRelease": "9ac7de22bf977385ceb954624677e33f0bae062b",
  "currentBlob": {"kind": "file", "device": 2049, "inode": 1738, "size": 219, "uid": 0, "gid": 0,
                  "mode": "0600", "mtimeNs": 1790493331258019177, "ctimeNs": 1790493331258019177,
                  "sha256": "6a61c350e848a833868f4573982fca9c75e2af79ccc9bd3716ae0303c26973f3"},
  "hostKey": {"kind": "file", "device": 2049, "inode": 5768, "size": 4112, "uid": 0, "gid": 0,
              "mode": "0400", "mtimeNs": 1790490701237702273, "ctimeNs": 1790490701241702264},
  "signerAccount": {"uid": 995, "gid": 985},
  "statusL2b2Old": "PASS", "statusFailures": [],
  "acceptedOldRelease": true, "acceptedCurrentSha256": true, "result": "PASS"
}
```

## 16. Discrepancies and notes

None is a material drift from the accepted baseline.

| # | Observation | Classification |
| --- | --- | --- |
| D-1 | The installer `status` read CURRENT, the unit files, and `/etc/shadow` without `O_NOATIME` on a `relatime` mount, so their atime may have advanced | inherent in the accepted `status` tooling, as in every earlier B1b-3d status run. atime is outside every preservation contract (§6.2, §24). mtime, ctime, inode, size, owner, mode, and SHA-256 are unchanged |
| D-2 | DR-5 evidence comes from routine run `36408531112` (`10:15`–`10:17Z`), not from this session | the accepted DR-5 mechanism runs as the deployer in CI. The operator session never assumes the deployer identity. The run's core-api deployment completed at `10:20Z`, before first contact (`10:38Z`). Broker preservation passes after it |
| D-3 | systemd reports `UnitFilePreset=enabled` for both authority units | the distribution default preset policy for a `static` unit. `UnitFileState=static`, with no `[Install]` enablement and no links. Not enabled |
| D-4 | The installed `9ac7de2` unit's `InaccessiblePaths` lacks `/etc/lilith-authority-custody`, the hold root, and the K-WIT root | expected OLD-release form (PF-4). PR-1A M-A3 replaces it with `11b6d00f…` |
| D-5 | `/etc/credstore` (plaintext) exists, `root:root 0700`, empty | the distribution default, outside `/etc/credstore.encrypted`. No credential |
| D-6 | `/var/run/reboot-required` is pending (kernel `7.0.0-1011-gcp`, since 2026-09-14) | known (runtime baseline §10). A reboot before or during PR-1A changes the boot ID and the broker incarnation, and ends this baseline. Pass 2 must re-run this preflight after any reboot |
| D-7 | `/root/b1b3d-l2b-publication.json` exists (name only; not read) | the owner-retained L2b.2 publication (public material only) is still on the host. This resolves preflight B-8's "where the owner copy lives" only partly. Its bytes are not in the repository |
| D-8 | The ad-hoc stat probe is session scratch, not reviewed source | it made only the stat, list, and hash observations the accepted tools do not cover. Its SHA-256 is recorded. If the owner wants a reproducible Pass-2 PRE, it needs review |

## 17. Result

```text
PR1A_PREFLIGHT_PASS
```

Every required baseline property matches:

- host identity;
- installed release `9ac7de2`, its tree, and its selector;
- unit, socket, tmpfiles, and CLI bytes;
- units loaded, inactive, `static`, never started, `NeedDaemonReload=no`;
- the signer account contract (uid 995, gid 985);
- CURRENT identity and SHA-256;
- credstore = exactly CURRENT;
- host key PRESENT_SECURE (stat only);
- every PR-1 object absent;
- no authority state directory;
- activation `GRANT_ABSENT`;
- DR-5 `L1c.3` + `PR1_ABSENT`;
- broker preservation PASS at the accepted incarnation and candidate;
- needrestart control intact;
- one filesystem for every current and future custody path.

The only previously unknown values (signer uid and gid, CURRENT and host-key
inode and times) were observed and satisfy the structural contract.

**Do not continue into installation.** Pass 2 (PR-1A inert install) needs a
separate explicit owner authorization. It must also have:

- the owner's reproducible archive and attestation for the candidate
  release;
- a fresh repeat of this preflight immediately before M-A1;
- the merge freeze between `upgrade-stage` and `upgrade-retire-old`
  (preflight §9).

## 18. Nonclaims

- No PR-1A install, PR-1B bootstrap, K-WIT, ledger, witness, V2 genesis,
  hold, owner pin, register, K-ROOT, registry, or activation grant.
- No authority, custody readiness, `FULL_READINESS`, or issuance.
- No snapshot safety (PR-2), no off-host register (PR-3), and no
  whole-host rollback protection.
- No zeroization or remanence claim.
- L2 U5 is still open, because the signer has never loaded K-ACT.
- DR-3 (`ubuntu` root-equivalent through `sudo`/`lxd`) remains OPEN,
  unchanged.

## Explicitly not done

```text
READ-ONLY DEV CONTACT ONLY
NO PROD CONTACT
NO FILE MUTATION ON DEV
NO PERMISSION CHANGE
NO SERVICE START/STOP/RESTART
NO DAEMON-RELOAD
NO INSTALL
NO K-WIT GENERATION
NO LEDGER
NO WITNESS
NO HOLD
NO REGISTRY CHANGE
NO KEY ROTATION
PR-1A INSTALL PASS 2 NOT AUTHORIZED
B1b-3e LIVE REHEARSAL NOT AUTHORIZED
```
