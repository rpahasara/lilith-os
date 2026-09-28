# Slice 15B2b-B1b-3e — PR-1A M-A7: Inert Custody Root

Status:

- **M-A7 LIVE MUTATION**
- **INERT CUSTODY ROOT INSTALLED** (`/etc/lilith-authority-custody`, `prepared/`, `retired/`; empty)
- **NO CUSTODY RECORDS**
- **NO K-WIT**
- **M-A8 NOT AUTHORIZED**; **PR-1B NOT AUTHORIZED**; **B1b-3e LIVE REHEARSAL NOT AUTHORIZED**
- Result: **`M_A7_PASS`**

This record is on branch `claude/15b2b-b1b3e-pr1a-ma1-stage-release`, after
the [transport cleanup](slice-15b2b-b1b3e-pr1a-transport-cleanup.md). It is
not merged.

```text
directory existence != custody acceptance != hold state != authority != activation
```

## 1. Identities and source drift

| Identity | Value |
| --- | --- |
| installed release / `PAYLOAD_SOURCE_SHA` | `aee323e94412accbe321bc84eae78c5b8cf95afc` |
| `CONTROL_SHA` | `c1eb56842d464f6690b7d55a1f6915d54618e006` |
| `ARTIFACT_SHA256` | `25f1ff03…250a` |
| `ATTESTATION_SHA256` | `86ed2659…c683` |

`origin/main` = `0621f26`. Between `c1eb568` and `0621f26` only `docs/`
changed: the final-gate record, the M-A1…M-A6 records, and README rows.
There is no installer, custody, host-path, unit, CLI, or boundary-logic
change. The streamed installer is `git show c1eb568` (`fe10d9a3…5487`).

## 2. What M-A7 is in reviewed source (confirmed before DEV contact)

M-A7 is installer stage `custody <SHA>`, which is `stage_custody`. Its status
contract is `L2c`, the DR-5 ladder calls it `P1A-7`, and the rationale is
RR-26.

- **Guard.** `require_dev_root`, then `status --expect L2b.2 <SHA>` must
  PASS (the L2b.2 contract requires all three custody paths absent).
- **Creates exactly three directories, in order**, each with
  `mkdir(mode=0700)`, then `chown 0:0`, then `chmod 0700`. An existing path
  is a collision and aborts:
  - `/etc/lilith-authority-custody`;
  - `/etc/lilith-authority-custody/prepared`;
  - `/etc/lilith-authority-custody/retired`.
- **Then** it fsyncs the custody root and `/etc`, and returns
  `status --expect L2c <SHA>`. That is the full L2b.2 contract plus:
  - the three directories root `0700`;
  - the root holding exactly `prepared` and `retired`;
  - both slots empty;
  - `st_dev(credstore) == st_dev(prepared) == st_dev(retired)`
    (`custody_failures`).
- **It creates no file or content.** PREPARED and RETIRED are empty slot
  *directories*; no credential is written or moved.
- **It does not invoke** tmpfiles, a daemon-reload, or any `systemctl`
  beyond the read-only `show` inside `status`.
- **It does not create** a hold store, anything under `/var/lib`, an
  account, a ledger, witness state, a registry, owner inputs, or a
  RecoveryEpoch.

This is custody-root scaffolding only, as authorized.

## 3. PRE (read-only, 2026-09-28 `15:50:23Z`–`15:50:51Z`)

The contact was the same as before: OS Login `ravindupahasara2_gmail_com`,
IAP, the existing `sudo`, and tools from `CONTROL_SHA`. The gate required
13 checks, and all were `OK`:

- **Host observation.** The observer `stableSha256` equals the
  transport-cleanup POST.
- **Status.** `status --expect L2b.2 aee323e…` = `PASS`.
- **Custody.** The three custody paths are absent. Every other PR-1 object
  is absent too: no K-WIT, ledger, witness state, hold, registry, owner
  inputs, or RecoveryEpoch.
- **CURRENT.** `6a61c350…73f3`, inode 1738.
- **Services.** The signer is inactive. Witness units are `not-found`, there
  is no witness account, and no witness process.
- **Filesystem.** `/etc` (the nearest existing parent of the future root)
  shares `st_dev` with the credstore.
- **Broker.** `PASS`: `42af2691…`, PID 132976, ticks 108213277,
  `NRestarts=0`.
- **Activation and boot.** Activation `GRANT_ABSENT`. Boot `24d1771d…`, no
  reboot.
- **Transport.** The transfer staging directory is still absent.

**DR-5 compatibility.** The latest routine run is `36443835331` (main
`0621f26`), with `PR1_AUTHORITY_BOUNDARY maturity=P1A-5` and
`AUTHORITY_BOUNDARY_PROOF=PASS maturity=L1c.3`. No routine run has happened
since.

## 4. Mutation

`install_authority_dev.py custody aee323e94412accbe321bc84eae78c5b8cf95afc`

It ran as root, streamed from `CONTROL_SHA`, at `15:50:51Z`–`15:50:58Z`.
The returned `status L2c` was `result=PASS`, `failures=[]`.

| Created path | Type | Owner:group | Mode | `st_dev` | inode | Entries |
| --- | --- | --- | --- | --- | --- | --- |
| `/etc/lilith-authority-custody` | directory (not symlink) | `root:root` | `0700` | 2049 | 262572 | exactly `prepared`, `retired` |
| `/etc/lilith-authority-custody/prepared` | directory (not symlink) | `root:root` | `0700` | 2049 | 262575 | **empty** |
| `/etc/lilith-authority-custody/retired` | directory (not symlink) | `root:root` | `0700` | 2049 | 262576 | **empty** |

`/etc/credstore.encrypted` is `root:root 0700`, `st_dev 2049`, inode 526:
the same filesystem as both slots, which is what future custody renames
need.

The observer's changed sections, PRE → POST, are exactly `pr1Objects`,
`listings`, `filesystems`, and `namespaceInventory`, all from these three
directories. `filesystems` changed only because the future-root entry now
resolves to itself instead of `/etc`. The `/etc` directory's own
`mtime`/`ctime` changed because of the new entry.

## 5. POST (`15:50:58Z`–`15:52:02Z`)

| Check | Result |
| --- | --- |
| `status --expect L2c aee323e…` | **`PASS`**, `failures=[]` |
| `status --expect L2b.2 aee323e…` | `FAIL` with exactly `UNEXPECTED_PRESENT` for the three custody paths. This is expected: L2b.2 is now the superseded ladder step |
| created paths | exist; types, owners, and modes exactly as reviewed (§4); no file inside; no symlink |
| CURRENT | `currentBlob` identical: kind, `0:0`, `0600`, device, inode 1738, size, `mtimeNs`, `ctimeNs`, SHA-256 `6a61c350…`. Credstore still exactly CURRENT |
| release / units / CLIs | the observer's `releases`, `hostFiles`, and `units` sections are identical to PRE: `current -> releases/aee323e…`, single release, manifest `1d578ca7…`, tree `675c9482…`. Units `11b6d00f…`/`bff5e927…`/`2a1891ef…`. Six CLIs `1fa50327…`, `fda779cd…`, `ad3fbc94…`, `bc331636…`, `ad928f8d…`, `9fce2e46…` |
| authority service | inactive, `NRestarts=0`, never started |
| recovery witness | units `not-found`, no account, no process |
| daemon-reload | not executed: 0 PID 1 `Reloading` since `14:00Z` |
| K-WIT / ledger / witness state / hold record / registry / RecoveryEpoch | all absent. `/var/lib/lilith-authority-custody` and `holds/` are absent. No K-WIT root. No `/var/lib/lilith-authority-dev`. No `/etc/lilith-authority-dev` |
| activation | `ACTIVATION=NOT_ACCEPTED reason=GRANT_ABSENT` |
| broker | `BROKER_PRESERVATION=PASS`, `failures=[]`. Candidate `35495854…` = accepted; `42af2691…`, PID 132976, ticks 108213277, `NRestarts=0`. Its *reported* custody paths now include the three directories. It reports them, not judges them |
| needrestart | `PASS` |

The transcripts are in `…\lilith-b1b3e-pr1a-aee323e…\ma7\` with
`SHA256SUMS`.

## 6. DR-5 after M-A7

**PENDING. Not observable under this authorization.**

- The accepted authority-boundary proof runs only as the routine deployer
  inside `deploy-dev.yml`, on a push to `main`. The workflow's
  `workflow_dispatch` path exists only for broker-candidate PR observation.
- This instruction forbids merging, and the operator session never assumes
  the deployer identity. So no post-M-A7 DR-5 value exists yet, and none is
  predicted here.
- The first routine run after the owner merges this evidence is the
  post-M-A7 proof. At that point `/etc/lilith-authority-custody` must be
  proven non-vacuously: it now exists, so it is no longer
  `DEFERRED_UNTIL_OBJECT_EXISTS`. `prepared/` and `retired/` must be
  `UNOBSERVABLE_BY_DESIGN`, never "denied".
- The exact maturity string will be recorded from that run. A FAIL is a
  STOP, and it must not be rerun.

## 7. Notes

- **Inode reuse.** The custody root's inode 262572 is the same number the
  removed transfer directory had. That is ordinary ext4 inode reuse after
  the cleanup, and it carries no meaning.
- **PRE exit code.** One read-only PRE call exited `1` because the `ls` of
  the still-absent custody paths failed. The output was complete. No
  state was involved.

## 8. Result

```text
M_A7_PASS
```

The reviewed inert custody filesystem structure exists with exactly the
reviewed ownership and permissions. It holds no custody record, credential,
or authority.

## 9. For owner review before M-A8

- **Pending DR-5.** The post-M-A7 DR-5 proof is still outstanding (§6). It
  happens on the next routine run, which the owner triggers by merging.
- **M-A8.** M-A8 (the witness identity, installer `witness-account`,
  P1A-8a) needs its own authorization. It creates an **account**, which is a
  different kind of change from directories.
- **Reboot / broker restart.** Either one requires a fresh baseline first.

## Explicitly not done

```text
DEV MUTATION LIMITED TO M-A7
INERT CUSTODY ROOT STRUCTURE ONLY
CURRENT CREDENTIAL UNCHANGED
ATTESTED RELEASE/UNITS/CLIS UNCHANGED
AUTHORITY SERVICE INACTIVE
NO DAEMON-RELOAD
NO SERVICE START/STOP/RESTART
NO K-WIT
NO LEDGER
NO WITNESS STATE
NO HOLD RECORD
NO REGISTRY
NO RECOVERY EPOCH
NO KEY ROTATION
ACTIVATION STILL DARK
M-A8 NOT AUTHORIZED
PR-1B NOT AUTHORIZED
B1b-3e LIVE REHEARSAL NOT AUTHORIZED
```
