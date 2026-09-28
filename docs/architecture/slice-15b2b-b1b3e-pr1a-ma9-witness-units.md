# Slice 15B2b-B1b-3e — PR-1A M-A9: Recovery-Witness Unit Assets

Status:

- **M-A9 LIVE MUTATION**
- **WITNESS UNIT ASSETS INSTALLED** (service, owner socket, signer socket, tmpfiles file)
- **NO DAEMON-RELOAD**
- **NO WITNESS STATE**
- **NO K-WIT**
- **M-A10 NOT AUTHORIZED**; **PR-1B NOT AUTHORIZED**; **B1b-3e LIVE REHEARSAL NOT AUTHORIZED**
- Result: **`M_A9_PASS`**

This record is on branch `claude/15b2b-b1b3e-pr1a-ma1-stage-release`, after
[M-A8](slice-15b2b-b1b3e-pr1a-ma8-witness-account.md). It is not merged.

```text
unit files exist != units loaded for execution != service started != witness state != K-WIT != witness authority
```

## 1. Source drift and the accepted post-M-A8 boundary

- **Source drift.** `origin/main` = `a9737d9` (the merge of PR #96, the M-A8
  record). Only `docs/` differs from `CONTROL_SHA` `c1eb568`. The streamed
  installer is `fe10d9a3…5487`.
- **Post-M-A8 DR-5.** It was observed read-only from run `36450019253`
  (`a9737d9`, `16:18:05Z`–`16:23:41Z`):
  - `PR1_AUTHORITY_BOUNDARY maturity=P1A-8a`,
    `AUTHORITY_BOUNDARY_PROOF=PASS maturity=L1c.3`.
  - `DENIED: sudo -u lilith-recovery-witness /usr/bin/true`, which is now
    non-vacuous. Every witness unit verb (start, stop, restart, enable, mask,
    edit, …) was also `DENIED`.

  This closes the M-A8 record's pending item.

## 2. What M-A9 is in reviewed source (confirmed before DEV contact)

M-A9 is installer stage `witness-units <SHA>`, which is `stage_witness_units`.
Its status contract is `P1A-8b`, and the rationale is PR-1S S-8.

- **Guard.** `require_dev_root`, then `status --expect P1A-8a <SHA>` must
  PASS.
- **Creates exactly four new files** (`WITNESS_UNIT_TARGETS`), each from
  `releases/<SHA>/assets/…`. Each is written by `_write_new`:
  `O_WRONLY|O_CREAT|O_EXCL|O_NOFOLLOW`, fsync, `chown root:root`,
  `chmod 0644`. An existing file is **never** replaced:
  - `/etc/systemd/system/lilith-recovery-witness.service`;
  - `/etc/systemd/system/lilith-recovery-witness-owner.socket`;
  - `/etc/systemd/system/lilith-recovery-witness-signer.socket`;
  - `/etc/tmpfiles.d/lilith-recovery-witness.conf`.
- **Returns `status --expect P1A-8b`.** That checks the four files at
  root `0644`, bytes equal to the release copies (`UNIT_BYTES`), every unit
  `UnitFileState` in `{none, "", static}`, and nothing active.
- **It does not** invoke `systemctl` beyond the read-only `show` inside
  `status`, daemon-reload, run `systemd-tmpfiles`, start, stop, or enable
  anything. It creates no `/etc/lilith-recovery-witness`,
  `/var/lib/lilith-recovery-witness`, K-WIT, witness state, ledger, or hold.
- **No `[Install]` section.** None of the four assets has one, so systemd
  classifies the units as `static`.

This is unit-assets-only, as authorized.

## 3. PRE (read-only, 2026-09-28 `16:28:12Z`–`16:35:42Z`; IAP slow)

The contact was the same as before: OS Login `ravindupahasara2_gmail_com`,
IAP, the existing `sudo`, and tools from `CONTROL_SHA`. The gate required
14 checks, and all were `OK`:

- **Host observation.** The observer `stableSha256` equals the M-A8 POST.
- **Status.** `status --expect P1A-8a aee323e…` = `PASS`.
- **Custody.** The root is exactly the P1A-7 structure, with `prepared/`
  and `retired/` empty. Every other PR-1 object is absent.
- **Witness account.** `994/984`, groups `[984]`, `nologin`, home
  `/nonexistent` (absent), no group members.
- **CURRENT.** `6a61c350…`, inode 1738.
- **Services.** The signer is inactive.
- **Witness units.** The four target files are absent. All three witness
  units are `not-found`.
- **Broker.** `PASS`: `42af2691…`, PID 132976, ticks 108213277,
  `NRestarts=0`.
- **Activation and boot.** Activation `GRANT_ABSENT`. Boot `24d1771d…`.
- **Runtime.** No witness process. `/run/lilith-recovery-witness` absent.

## 4. Mutation

`install_authority_dev.py witness-units aee323e94412accbe321bc84eae78c5b8cf95afc`

It ran as root, streamed from `CONTROL_SHA`, at `16:35:42Z`–`16:37:16Z`.
The files are stamped `16:37:09Z`. The returned `status P1A-8b` was
`result=PASS`, `failures=[]`.

| Created file | Owner:group | Mode | Size | inode | SHA-256 | Attested |
| --- | --- | --- | --- | --- | --- | --- |
| `/etc/systemd/system/lilith-recovery-witness.service` | `root:root` | `0644` | 1587 | 2522 | `9f78130c06491d184aff7066de99f804bf3816e171c63d6f70b734b1c6e85d7d` | equal |
| `/etc/systemd/system/lilith-recovery-witness-owner.socket` | `root:root` | `0644` | 518 | 5652 | `d260917fb31e9c76341fba131bafdc2802b80c0cf2fdcffb8cecc6e176440beb` | equal |
| `/etc/systemd/system/lilith-recovery-witness-signer.socket` | `root:root` | `0644` | 573 | 5901 | `ad345d18747c30a7c2a93cb18d5be310dc091f5efe07fc6e1606efbc099bb9c7` | equal |
| `/etc/tmpfiles.d/lilith-recovery-witness.conf` | `root:root` | `0644` | 64 | 5902 | `c3491d517aa70ff960e1dba4410378efcecc134737282136aad77a5a9d200be0` | equal |

All four are regular files, not symlinks. No other file was created.

The observer's changed sections, PRE → POST, are exactly:

- `hostFiles`: these four files; every other host file is unchanged;
- `namespaceInventory`: the four names;
- `units`: the systemd state in §5.

## 5. systemd state (recorded, never reloaded)

| Unit | LoadState before → after | ActiveState | UnitFileState before → after | NeedDaemonReload | FragmentPath after |
| --- | --- | --- | --- | --- | --- |
| `lilith-recovery-witness.service` | `not-found` → `loaded` | `inactive` / `dead` | `""` → `static` | `no` | `/etc/systemd/system/lilith-recovery-witness.service` |
| `lilith-recovery-witness-owner.socket` | `not-found` → `loaded` | `inactive` / `dead` | `""` → `static` | `no` | `/etc/systemd/system/lilith-recovery-witness-owner.socket` |
| `lilith-recovery-witness-signer.socket` | `not-found` → `loaded` | `inactive` / `dead` | `""` → `static` | `no` | `/etc/systemd/system/lilith-recovery-witness-signer.socket` |

**systemd sees the new files, but no daemon-reload occurred.**

- **Evidence of no reload.** PID 1 logged 0 `Reloading` entries since
  `14:00Z`, and `UnitsLoadTimestamp` is still `Sun 2026-09-27 06:25:33 UTC`.
- **Why the units show `loaded`.** It is the same on-demand behaviour
  recorded for M-A3 §6. An unreferenced, not-found unit is not kept in
  memory, so the next `systemctl show` loads the fragment fresh from disk.
- **Execution.** `InvocationID` is empty and every unit is `inactive`.
  There are no enablement or drop-in entries. Nothing is started, enabled,
  or listening.

The authority-dev units are unchanged: `loaded`, `inactive`, `static`,
`NeedDaemonReload=no`.

## 6. POST (`16:37:16Z`–`16:42:32Z`)

| Check | Result |
| --- | --- |
| `status --expect P1A-8b aee323e…` | **`PASS`**, `failures=[]` |
| witness files | exist; bytes attested; `root:root 0644`; no extra file (§4) |
| witness account | unchanged (`accounts` section identical): 994/984, `nologin`, `/nonexistent`, no supplementary groups |
| witness units | `inactive`, `static`, not enabled, no start (§5) |
| daemon-reload | **not executed** |
| tmpfiles | **not executed**: `/run/lilith-recovery-witness` still absent |
| `/etc/lilith-recovery-witness` | absent (the new files are under `/etc/systemd/system` and `/etc/tmpfiles.d` only) |
| `/var/lib/lilith-recovery-witness` | absent |
| K-WIT / witness chain or state / ledger / hold record / registry / RecoveryEpoch | all absent (`pr1Objects` section identical to PRE) |
| `prepared/`, `retired/` | still empty |
| CURRENT | `currentBlob` identical: inode 1738, `0:0 0600`, `mtimeNs`, `ctimeNs`, SHA-256 `6a61c350…`. Not decrypted |
| authority service | inactive, `NRestarts=0`, `NeedDaemonReload=no` |
| release / units / CLIs | `releases` identical: single release `aee323e…`, attested tree. Authority units and the six CLIs unchanged (every other host file identical) |
| activation | `ACTIVATION=NOT_ACCEPTED reason=GRANT_ABSENT` |
| broker | `BROKER_PRESERVATION=PASS`, `failures=[]`. Candidate `35495854…` = accepted; `42af2691…`, PID 132976, ticks 108213277, `NRestarts=0`. needrestart `PASS` |

The transcripts are in `…\lilith-b1b3e-pr1a-aee323e…\ma9\` with
`SHA256SUMS`.

## 7. DR-5 after M-A9

```text
POST_M_A9_DR5_PENDING
```

The routine deployer's boundary proof runs only on the next push to `main`.
No manual substitute was run. Its exact maturity string will be recorded
from that run. A FAIL is a STOP, and it must not be rerun.

## 8. Notes

- **Transport.** The local gcloud client for the POST observer call exited
  `0xC0000005` after writing its complete output (the transcript ends
  `PR1A_HOST_OBSERVATION=COMPLETE stableSha256=a783f86f…`). This is the
  known workstation-side crash, not a DEV event. IAP was slow: the PRE took
  about 7.5 minutes.
- **Tmpfiles consequence.** From now on, the next boot (or any
  `systemd-tmpfiles --create`) creates `/run/lilith-recovery-witness`
  `0710 root:lilith-authority-dev`. The reviewed contract accepts exactly
  that runtime directory from P1A-8b (`PR1_RUNTIME_DIRECTORIES`), so it is
  runtime scaffolding, not witness state.

## 9. Result

```text
M_A9_PASS
```

The reviewed witness unit assets exist on disk, byte-identical to the
attested release. Nothing is running, enabled, reloaded, or stateful.

## 10. For owner review before M-A10

- **Pending DR-5.** The post-M-A9 DR-5 happens on the next routine run.
- **P1A-8c** is the owner daemon-reload step after `witness-units`. Its
  status contract requires the witness units `loaded` with
  `NeedDaemonReload=no`, which systemd already reports without a reload
  (§5), the same as the M-A4 situation. Whether to skip it is an owner
  decision.
- **M-A10.** M-A10 is installer stage `skeleton` (P1A-9). Its guard is
  `status --expect P1A-8c`, which is already met by the observed state in
  §5. It creates eight empty `root:root` directories, in this order:
  - `/etc/lilith-authority-dev`, `…/trust`, `…/registry`, `…/owner`,
    each `0755`;
  - `/etc/lilith-recovery-witness`, `…/credentials`, each `0700`;
  - `/var/lib/lilith-authority-custody`, `…/holds`, each `0700`.

  It needs its own authorization.
- **Reboot / broker restart.** Either one requires a fresh baseline.

## Explicitly not done

```text
DEV MUTATION LIMITED TO M-A9
WITNESS UNIT ASSETS INSTALLED
WITNESS ACCOUNT UNCHANGED
NO DAEMON-RELOAD
NO TMPFILES EXECUTION
NO SERVICE START/STOP/RESTART
NO SOCKET START/STOP/RESTART
NO ENABLEMENT
NO K-WIT
NO WITNESS STATE
NO LEDGER
NO HOLD RECORD
PREPARED/RETIRED STILL EMPTY
CURRENT CREDENTIAL UNCHANGED
AUTHORITY SERVICE INACTIVE
NO REGISTRY
NO RECOVERY EPOCH
NO KEY ROTATION
ACTIVATION STILL DARK
M-A10 NOT AUTHORIZED
PR-1B NOT AUTHORIZED
B1b-3e LIVE REHEARSAL NOT AUTHORIZED
```
