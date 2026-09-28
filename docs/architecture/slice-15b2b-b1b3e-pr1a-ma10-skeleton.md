# Slice 15B2b-B1b-3e — PR-1A M-A10: Empty PR-1 Skeleton

Status:

- **M-A10 LIVE MUTATION**
- **EMPTY PR-1 SKELETON INSTALLED**
- **NO AUTHORITY MATERIAL**
- **NO WITNESS MATERIAL**
- **P1A-8c SATISFIED WITHOUT EXPLICIT DAEMON-RELOAD** (owner-skipped)
- **PR-1B NOT AUTHORIZED**; **B1b-3e LIVE REHEARSAL NOT AUTHORIZED**
- Result: **`M_A10_PASS`**

This record is on branch `claude/15b2b-b1b3e-pr1a-ma1-stage-release`, after
[M-A9](slice-15b2b-b1b3e-pr1a-ma9-witness-units.md). It is not merged.

```text
directory skeleton != authority data != registry != witness state != hold != authority
```

## 1. Source drift and the accepted post-M-A9 boundary

- **Source drift.** `origin/main` = `96fed73` (the merge of PR #97, the M-A9
  record). Only `docs/` differs from `CONTROL_SHA` `c1eb568`. The streamed
  installer is `fe10d9a3…5487`.
- **Post-M-A9 DR-5.** It was observed read-only from run `36453920293`
  (`96fed73`, `16:50:33Z`–`16:56:10Z`):
  - `PR1_AUTHORITY_BOUNDARY maturity=P1A-8b`,
    `AUTHORITY_BOUNDARY_PROOF=PASS maturity=L1c.3`.
  - The deployer is non-vacuously denied `test -w` on all four witness unit
    files.

  This closes the M-A9 record's pending item.
- **P1A-8c.** The owner skipped P1A-8c: it is satisfied without an explicit
  daemon-reload. Its reviewed contract requires the witness units
  `LoadState=loaded` and `NeedDaemonReload=no`, and they already are. The
  `P1A-8c` status passed as this stage's guard (§3). No daemon-reload was
  run.

## 2. What M-A10 is in reviewed source (confirmed before DEV contact)

M-A10 is installer stage `skeleton <SHA>`, which is `stage_skeleton`. Its
status contract is `P1A-9`.

- **Guard.** `require_dev_root`, then `status --expect P1A-8c <SHA>` must
  PASS.
- **Creates exactly `SKELETON_DIRS`, in order.** Each is created with
  `mkdir(mode)`, then `chown 0:0`, then `chmod`. An existing path is a
  collision:

  | Path | Mode |
  | --- | --- |
  | `/etc/lilith-authority-dev` | `0755` |
  | `/etc/lilith-authority-dev/trust` | `0755` |
  | `/etc/lilith-authority-dev/registry` | `0755` |
  | `/etc/lilith-authority-dev/owner` | `0755` |
  | `/etc/lilith-recovery-witness` | `0700` |
  | `/etc/lilith-recovery-witness/credentials` | `0700` |
  | `/var/lib/lilith-authority-custody` | `0700` |
  | `/var/lib/lilith-authority-custody/holds` | `0700` |

- **Then** it fsyncs `/etc`, `/etc/lilith-authority-dev`,
  `/etc/lilith-recovery-witness`, `/var/lib`, and
  `/var/lib/lilith-authority-custody`, and returns
  `status --expect P1A-9 <SHA>`.
- **The P1A-9 contract (`PR1_LISTINGS`)** requires exact listings:
  - `/etc/lilith-authority-dev` = `{owner, registry, trust}`;
  - `trust/`, `owner/`, and `registry/` each empty;
  - `/etc/lilith-recovery-witness` = `{credentials}`;
  - `credentials/` empty;
  - `/var/lib/lilith-authority-custody` = `{holds}`;
  - `holds/` empty.
- **It creates no file.** It invokes no `systemctl` beyond the read-only
  `show`, and no tmpfiles. It creates no runtime directory, registry,
  register, K-WIT, witness state, ledger, hold record, or genesis.

This is empty-skeleton-only, as authorized.

## 3. PRE (read-only, 2026-09-28 `17:09:05Z`–`17:09:39Z`)

The contact was the same as before: OS Login `ravindupahasara2_gmail_com`,
IAP, the existing `sudo`, and tools from `CONTROL_SHA`. The gate required
16 checks, and all were `OK`:

- **Host observation.** The observer `stableSha256` equals the M-A9 POST.
- **Guard status.** `status --expect P1A-8c aee323e…` = `PASS`.
- **Custody.** The custody root is exact, with `prepared/` and `retired/`
  empty.
- **Target paths.** All eight skeleton paths are absent. Every other PR-1
  object is absent too.
- **Witness account.** Exact: 994/984, groups `[984]`, `nologin`,
  `/nonexistent`.
- **Witness units.** The four files have the attested hashes. The units
  are `loaded`, `inactive`, `static`, `NeedDaemonReload=no`.
- **Services.** The authority service and socket are inactive.
- **CURRENT.** `6a61c350…`, inode 1738.
- **Broker.** `PASS`: `42af2691…`, PID 132976, ticks 108213277,
  `NRestarts=0`.
- **Activation and boot.** Activation `GRANT_ABSENT`. Boot `24d1771d…`.
- **Runtime.** No witness process. `/run/lilith-recovery-witness` and
  `/run/lilith-authority-dev` are absent. 0 PID 1 reloads since `14:00Z`.

## 4. Mutation

`install_authority_dev.py skeleton aee323e94412accbe321bc84eae78c5b8cf95afc`

It ran as root, streamed from `CONTROL_SHA`, at `17:09:39Z`–`17:09:46Z`.
The returned `status P1A-9` was `result=PASS`, `failures=[]`.

| Created path | Type | Owner:group | Mode | `st_dev` | inode | Contents |
| --- | --- | --- | --- | --- | --- | --- |
| `/etc/lilith-authority-dev` | directory | `root:root` | `0755` | 2049 | 266829 | `owner registry trust` |
| `/etc/lilith-authority-dev/trust` | directory | `root:root` | `0755` | 2049 | 267290 | empty |
| `/etc/lilith-authority-dev/registry` | directory | `root:root` | `0755` | 2049 | 267291 | empty |
| `/etc/lilith-authority-dev/owner` | directory | `root:root` | `0755` | 2049 | 267294 | empty |
| `/etc/lilith-recovery-witness` | directory | `root:root` | `0700` | 2049 | 267295 | `credentials` |
| `/etc/lilith-recovery-witness/credentials` | directory | `root:root` | `0700` | 2049 | 267296 | empty |
| `/var/lib/lilith-authority-custody` | directory | `root:root` | `0700` | 2049 | 267297 | `holds` |
| `/var/lib/lilith-authority-custody/holds` | directory | `root:root` | `0700` | 2049 | 267298 | empty |

- All eight are real directories, not symlinks. No file was created.
- The only children are the reviewed child directories.
- All lie on the credstore filesystem (`st_dev 2049`).

The observer's changed sections, PRE → POST, are exactly `pr1Objects`,
`listings`, `filesystems` (the future paths now resolve to themselves), and
`namespaceInventory`. All come from these eight directories.

## 5. POST (`17:09:46Z`–`17:10:20Z`)

| Check | Result |
| --- | --- |
| `status --expect P1A-9 aee323e…` | **`PASS`**, `failures=[]` |
| skeleton | exact (§4) |
| witness account | unchanged (`accounts` section identical) |
| witness units | unchanged (`hostFiles`, `units` identical): attested bytes; `loaded`, `inactive`, `static`, `NeedDaemonReload=no` |
| authority release / units / CLIs | unchanged (`releases`, `hostFiles` identical): single release `aee323e…`, attested tree, units, six CLIs |
| CURRENT | `currentBlob` identical: inode 1738, `0:0 0600`, `mtimeNs`, `ctimeNs`, SHA-256 `6a61c350…`. Not decrypted |
| authority service / socket | inactive, `NRestarts=0` |
| witness service / sockets | inactive, not enabled; no witness process |
| daemon-reload | **not executed**: 0 PID 1 `Reloading` since `14:00Z`; `UnitsLoadTimestamp` still `2026-09-27 06:25:33 UTC` |
| tmpfiles | **not executed**: `/run/lilith-recovery-witness` and `/run/lilith-authority-dev` absent |
| K-WIT | absent: `credentials/` empty, and the superseded credstore name is absent |
| witness state | `/var/lib/lilith-recovery-witness` absent |
| authority ledger | `/var/lib/lilith-authority-dev` and `authority_ledger.db` absent |
| hold record | `holds/` empty |
| registry content | `registry/` and `trust/` empty |
| owner register content | `owner/` empty |
| RecoveryEpoch | none |
| `prepared/`, `retired/` | still empty |
| activation | `ACTIVATION=NOT_ACCEPTED reason=GRANT_ABSENT` |
| broker | `BROKER_PRESERVATION=PASS`, `failures=[]`. Candidate `35495854…` = accepted; `42af2691…`, PID 132976, ticks 108213277, `NRestarts=0`. needrestart `PASS` |

The transcripts are in `…\lilith-b1b3e-pr1a-aee323e…\ma10\` with
`SHA256SUMS`.

## 6. DR-5 after M-A10

```text
POST_M_A10_DR5_PENDING
```

The routine proof runs only on the next push to `main`, and no manual
substitute was run.

With the skeleton present, that run should prove the new root-only roots
non-vacuously: `/etc/lilith-recovery-witness` and
`/var/lib/lilith-authority-custody`. It should prove the
`/etc/lilith-authority-dev` skeleton `-w`-denied. Everything beneath the
root-only roots should be `UNOBSERVABLE_BY_DESIGN`. Its exact maturity string
will be recorded. A FAIL is a STOP, and it must not be rerun.

## 7. Result

```text
M_A10_PASS
```

The reviewed empty authority and witness namespace skeleton exists. It holds
no authority material, witness material, registry, register, hold, ledger,
or credential.

## 8. PR-1A position

| Phase | Stage | Result |
| --- | --- | --- |
| M-A1 | `upgrade-stage` | `M_A1_PASS` |
| M-A2 | `upgrade-select` | `M_A2_PASS` |
| M-A3 | `upgrade-units` | `M_A3_PASS` |
| M-A4 | daemon-reload | owner-skipped, not required |
| M-A5 | `upgrade-cli` | `M_A5_PASS` |
| M-A6 | `upgrade-retire-old` | `M_A6_PASS` |
| transport cleanup | — | `PR1A_TRANSPORT_CLEANUP_PASS` |
| M-A7 | `custody` (L2c / P1A-7) | `M_A7_PASS`; DR-5 `P1A-7` |
| M-A8 | `witness-account` (P1A-8a) | `M_A8_PASS`; DR-5 `P1A-8a` |
| M-A9 | `witness-units` (P1A-8b) | `M_A9_PASS`; DR-5 `P1A-8b` |
| P1A-8c | daemon-reload | owner-skipped, satisfied without reload |
| M-A10 | `skeleton` (P1A-9) | `M_A10_PASS`; DR-5 **pending** |

Every PR-1A mutation stage in preflight §27 (M-A1…M-A10) is now complete.
Two things remain before an owner PR-1A completion or acceptance record:

1. **The post-M-A10 routine proof gate.** This is the preflight §27 row
   "proof gate": a real routine deployment with DR-5 PASS non-vacuous at
   the final PR-1 ladder step, and broker preservation PASS.
2. **The owner's PR-1A acceptance record.** It covers the inert install and
   makes no custody claim.

**Nonclaim.** PR-1A completion is not custody readiness. PR-1B (K-WIT,
registry, ledger, genesis, INITIAL_CUSTODY) also stays blocked on PR-2 and
PR-3.

## Explicitly not done

```text
P1A-8c SATISFIED WITHOUT EXPLICIT DAEMON-RELOAD
DEV MUTATION LIMITED TO M-A10
EMPTY PR-1 SKELETON ONLY
NO REGISTRY CONTENT
NO OWNER REGISTER CONTENT
NO K-WIT
NO WITNESS STATE
NO LEDGER
NO HOLD RECORD
PREPARED/RETIRED STILL EMPTY
CURRENT CREDENTIAL UNCHANGED
AUTHORITY SERVICE INACTIVE
WITNESS SERVICES/SOCKETS INACTIVE
NO DAEMON-RELOAD
NO TMPFILES EXECUTION
NO SERVICE START/STOP/RESTART
NO RECOVERY EPOCH
NO KEY ROTATION
ACTIVATION STILL DARK
PR-1B NOT AUTHORIZED
B1b-3e LIVE REHEARSAL NOT AUTHORIZED
```
