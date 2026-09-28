# Slice 15B2b-B1b-3e — PR-1A M-A8: Recovery-Witness System Account

Status:

- **M-A8 LIVE MUTATION**
- **RECOVERY-WITNESS ACCOUNT CREATED** (`lilith-recovery-witness`, uid 994 / gid 984)
- **NO WITNESS UNITS**
- **NO K-WIT**
- **M-A9 NOT AUTHORIZED**; **PR-1B NOT AUTHORIZED**; **B1b-3e LIVE REHEARSAL NOT AUTHORIZED**
- Result: **`M_A8_PASS`**

This record is on branch `claude/15b2b-b1b3e-pr1a-ma1-stage-release`, after
[M-A7](slice-15b2b-b1b3e-pr1a-ma7-custody-root.md). It is not merged.

```text
account existence != witness installation != witness credential != witness authority != activation
```

## 1. Source drift and the accepted post-M-A7 boundary

- **Source drift.** `origin/main` = `38c5adf` (the merge of PR #95: M-A7,
  transport cleanup, the DR-5 note). Only `docs/` differs from
  `CONTROL_SHA` `c1eb568`. The streamed installer is `fe10d9a3…5487`.
- **Post-M-A7 DR-5.** It was observed read-only in GitHub from run
  `36447743322` (candidate `38c5adf`, `15:59:35Z`–`16:02:58Z`):
  - `PR1_AUTHORITY_BOUNDARY maturity=P1A-7`,
    `AUTHORITY_BOUNDARY_PROOF=PASS maturity=L1c.3`.
  - The custody root now gets a non-vacuous `DENIED` for `test -r`, `-w`,
    and `-x`.
  - `prepared/` and `retired/` are `UNOBSERVABLE_BY_DESIGN`.
  - `sudo -u lilith-recovery-witness` is still
    `DEFERRED_UNTIL_OBJECT_EXISTS`, as is everything else still absent.

  This closes the M-A7 record's pending item.

## 2. What M-A8 is in reviewed source (confirmed before DEV contact)

M-A8 is installer stage `witness-account <SHA>`, which is
`stage_witness_account`. Its status contract is `P1A-8a`, and the rationale
is PR-1S S-4.

- **Guard.** `require_dev_root`, then `status --expect L2c <SHA>` must PASS.
- **One command:**

  ```text
  useradd --system --user-group --no-create-home --home-dir /nonexistent --shell /usr/sbin/nologin lilith-recovery-witness
  ```

  - The group is created by that same call (`--user-group`), not
    separately.
  - The uid and gid are assigned by useradd from the system range; none is
    requested.
  - No home is created, and no password is set, so it is locked.
- **Returns `status --expect P1A-8a`,** which includes the witness account
  contract (`verify_witness_account_contract`):
  - a system uid below 1000 and not 0;
  - primary gid = the group's gid, and **no supplementary groups**;
  - a group with no members;
  - home `/nonexistent`, which must not exist;
  - shell `/usr/sbin/nologin`;
  - shadow password locked (`!` or `*`);
  - `sudo -n -l -U` says "not allowed";
  - no uid or gid shared with `lilith`, `lilith-memory-broker`,
    `lilith-memory-relay`, or `lilith-authority-dev`;
  - not a member of the signer group.
- **It does not** create any directory, install units, invoke `systemctl`
  beyond the read-only `show`, or create K-WIT, witness state, a ledger,
  holds, a registry, or a RecoveryEpoch.

This is account-only, as authorized. It uses the same form as the accepted
B1b-3d L1a signer account.

## 3. PRE (read-only, 2026-09-28 `16:09:07Z`–`16:09:33Z`)

The contact was the same as before: OS Login `ravindupahasara2_gmail_com`,
IAP, the existing `sudo`, and tools from `CONTROL_SHA`. The gate required
15 checks, and all were `OK`:

- **Host observation.** The observer `stableSha256` equals the M-A7 POST.
- **Status.** `status --expect L2c aee323e…` = `PASS`.
- **Custody.** The root, `prepared/`, and `retired/` are exactly the P1A-7
  structure: root `0700`, and the root holds only `prepared` and
  `retired`. Both slots are empty. Every other PR-1 object is absent.
- **CURRENT.** `6a61c350…`, inode 1738.
- **Services.** The signer is inactive, and witness units are `not-found`.
- **Account.** `getent passwd` and `getent group lilith-recovery-witness`
  are both absent. There is no pre-existing group, and no witness process.
- **Broker.** `PASS`: `42af2691…`, PID 132976, ticks 108213277,
  `NRestarts=0`.
- **Activation and boot.** Activation `GRANT_ABSENT`. Boot `24d1771d…`.

## 4. Mutation

`install_authority_dev.py witness-account aee323e94412accbe321bc84eae78c5b8cf95afc`

It ran as root, streamed from `CONTROL_SHA`, at `16:09:33Z`–`16:09:40Z`.
The returned `status P1A-8a` was `result=PASS`, `failures=[]`.

| Property | Observed |
| --- | --- |
| user | `lilith-recovery-witness:x:994:984::/nonexistent:/usr/sbin/nologin` |
| group | `lilith-recovery-witness:x:984:`, with no members |
| uid / gid | **994 / 984**, system range, distinct from the signer 995/985, the broker group 987, and every other named principal |
| supplementary groups | none: `id` = `groups=984(lilith-recovery-witness)` |
| shell | `/usr/sbin/nologin` |
| home | `/nonexistent`, which does not exist. Nothing was added to `/home` |
| password / login | `passwd -S`: `L` (locked). No usable password. `nologin` shell, and no `authorized_keys` possible (no home) |
| sudo | `sudo -n -l -U lilith-recovery-witness`: "User lilith-recovery-witness is not allowed to run sudo on lilith-dev-01." No sudoers file names it |
| sensitive groups | unchanged. `sudo:27:ubuntu`, `adm:4:syslog,ubuntu`, `systemd-journal:999:` (empty), `lilith-memory-broker:987:` (empty), `lilith-authority-dev:985:` (empty), `lxd:105:ubuntu`. The witness is in none of them |
| subuid / subgid | no entry (a `--system` account) |
| mail spool | none created (`/var/mail` unchanged) |

**Every file the mutation touched** (useradd's standard account-database
updates):

| File | Change |
| --- | --- |
| `/etc/passwd`, `/etc/group` | rewritten with one new line each |
| `/etc/shadow`, `/etc/gshadow` | rewritten with one new line each; modes and owners unchanged (`0644 root:root`, `0640 root:shadow`) |
| `/etc/passwd-`, `/etc/group-`, `/etc/shadow-`, `/etc/gshadow-` | refreshed as backups of the previous contents |
| `/var/log/lastlog` | mtime updated; useradd resets the new uid's lastlog record |

Nothing else changed. There is no directory, unit, or tmpfiles file. The
observer's only changed section, PRE → POST, is `accounts`, which now holds
the witness facts. The signer account's facts are identical.

## 5. POST (`16:09:40Z`–`16:10:10Z`)

| Check | Result |
| --- | --- |
| `status --expect P1A-8a aee323e…` | **`PASS`**, `failures=[]` |
| account / group | exactly as §4 |
| unexpected directories / files | none. No home, `/nonexistent` absent, no `/etc/lilith-recovery-witness`, no `/var/lib/lilith-recovery-witness` |
| witness units | absent (`not-found`); no witness tmpfiles file |
| witness process | none (`WITNESS_PROCS=0`) |
| K-WIT / witness state / ledger / hold record / registry / RecoveryEpoch | all absent |
| `prepared/`, `retired/` | still empty |
| CURRENT | `currentBlob` identical: inode 1738, `0:0 0600`, `mtimeNs`, `ctimeNs`, SHA-256 `6a61c350…`. Not decrypted |
| release / units / CLIs | the observer's `releases`, `hostFiles`, and `units` sections are identical to PRE. Single release `aee323e…`, units and six CLIs attested |
| authority service | inactive, `NRestarts=0`, never started |
| activation | `ACTIVATION=NOT_ACCEPTED reason=GRANT_ABSENT` |
| broker | `BROKER_PRESERVATION=PASS`, `failures=[]`, `identityBoundaryEquivalent=true`. Candidate `35495854…` = accepted; `42af2691…`, PID 132976, ticks 108213277, `NRestarts=0` |
| daemon-reload / lifecycle | none: 0 PID 1 `Reloading` since `14:00Z`; no start, stop, or restart |
| needrestart | `PASS` |

The transcripts are in `…\lilith-b1b3e-pr1a-aee323e…\ma8\` with
`SHA256SUMS`.

## 6. DR-5 after M-A8

```text
POST_M_A8_DR5_PENDING
```

The accepted boundary proof runs only as the routine deployer on the next
push to `main`. No manual substitute was run.

That run must now prove `sudo -u lilith-recovery-witness` **non-vacuously
denied**, instead of `DEFERRED_UNTIL_OBJECT_EXISTS`. Its exact maturity
string will be recorded from the run. A FAIL is a STOP, and it must not be
rerun.

## 7. Result

```text
M_A8_PASS
```

The inert recovery-witness OS security principal exists with the reviewed
identity and privilege constraints. No witness unit, credential, state, or
authority exists.

## 8. For owner review before M-A9

- **Pending DR-5.** The post-M-A8 DR-5 happens on the next routine run
  (owner merge).
- **M-A9.** M-A9 is installer stage `witness-units` (P1A-8b): it installs
  the witness service, the two sockets, and the tmpfiles file. Its daemon-reload
  (P1A-8c) is a further step. Both need their own authorization.
- **Reboot / broker restart.** Either one requires a fresh baseline.

## Explicitly not done

```text
DEV MUTATION LIMITED TO M-A8
RECOVERY-WITNESS SYSTEM PRINCIPAL ONLY
NO WITNESS UNITS
NO WITNESS PROCESS
NO K-WIT
NO WITNESS STATE
NO LEDGER
NO HOLD RECORD
PREPARED/RETIRED STILL EMPTY
CURRENT CREDENTIAL UNCHANGED
ATTESTED RELEASE/UNITS/CLIS UNCHANGED
AUTHORITY SERVICE INACTIVE
NO DAEMON-RELOAD
NO SERVICE START/STOP/RESTART
NO REGISTRY
NO RECOVERY EPOCH
NO KEY ROTATION
ACTIVATION STILL DARK
M-A9 NOT AUTHORIZED
PR-1B NOT AUTHORIZED
B1b-3e LIVE REHEARSAL NOT AUTHORIZED
```
