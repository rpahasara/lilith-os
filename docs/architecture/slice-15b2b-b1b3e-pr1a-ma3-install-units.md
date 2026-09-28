# Slice 15B2b-B1b-3e — PR-1A M-A3: Install the Reviewed Unit Bytes

Status:

- **M-A3 LIVE MUTATION**
- **UNIT ASSETS INSTALLED** (authority-dev service, socket, tmpfiles)
- **SERVICES INERT**
- **DAEMON-RELOAD NOT AUTHORIZED** (none executed)
- **M-A4 NOT AUTHORIZED**
- **B1b-3e LIVE REHEARSAL NOT AUTHORIZED**
- Result: **`M_A3_PASS`**

This record is on branch `claude/15b2b-b1b3e-pr1a-ma1-stage-release`, after
[M-A2](slice-15b2b-b1b3e-pr1a-ma2-select-release.md). The ceremony's merge
freeze is still active, so nothing was merged. `origin/main` = `d7f9f06`,
unchanged.

```text
unit bytes on disk != systemd manager loaded definition != service execution
```

## 1. Identities

| Identity | Value |
| --- | --- |
| `PAYLOAD_SOURCE_SHA` / selected NEW | `aee323e94412accbe321bc84eae78c5b8cf95afc` |
| `CONTROL_SHA` | `c1eb56842d464f6690b7d55a1f6915d54618e006` |
| `ARTIFACT_SHA256` | `25f1ff03f9915c19ef5835e15ff4be6d90e27d45f23e909b2a1f8bdc81a0250a` |
| `ATTESTATION_SHA256` | `86ed2659a1e8040c43bc560aeb526a5a13842314ce92f917c8868d277f65c683` |
| retained OLD | `9ac7de22bf977385ceb954624677e33f0bae062b` |

## 2. Resolution of the M-A2 "systemd is reloaded" wording

**No `systemctl daemon-reload` ran in M-A2** (or M-A1, or M-A3). The M-A2
"reloaded" wording was `upgrade-status`'s *observed* field
`reloaded=true`. That field is computed read-only from `systemctl show`
(`LoadState=loaded` and `NeedDaemonReload=no`).

The evidence:

- The installer at `CONTROL_SHA` has no daemon-reload capability. Its only
  `systemctl` call is `systemctl show`, and its other subprocesses are
  `sudo -n -l -U`, `useradd`, `venv`/`pip`, and `runuser`.
- No M-A2 transcript contains `daemon-reload`.
- PID 1's journal: the last `Reloading…` on this boot is
  `2026-09-27T06:25:33Z` (client `systemctl`, session-3784). That is the
  accepted B1b-3d L1c.2 owner reload.
- The manager's `UnitsLoadTimestamp` is still `Sun 2026-09-27 06:25:33
  UTC`, read at the M-A3 POST.

The M-A2 record now says this explicitly.

## 3. What M-A3 is in reviewed source (confirmed before DEV contact)

The installer is `fe10d9a3…5487`, identical to `git show c1eb568`. M-A3 is
`upgrade-units <OLD> <NEW> <baseline>`, which is `stage_upgrade_units`:

- **Guard.** `_require_upgrade` checks baseline preservation, the state
  `SELECTED_NEW_RELEASE`, and that the deferred and custody paths are
  absent. `UNITS_UPDATED` or `UNITS_RELOADED` returns `ALREADY_COMPLETE`.
- **Replaces exactly `UNIT_TARGETS`**, each from `releases/<NEW>/assets/…`:
  - `/etc/systemd/system/lilith-authority-dev.service`;
  - `/etc/systemd/system/lilith-authority-dev.socket`;
  - `/etc/tmpfiles.d/lilith-authority-dev.conf`.
- **How each file is replaced (`_replace_file`).** An `O_EXCL` temp file
  `.<name>.lilith-upgrade.tmp` is written and fsynced. It is set to root
  `0644`, renamed over the target, and the directory is fsynced.
- **It does not** daemon-reload, run `systemd-tmpfiles`, start, stop,
  enable, or disable anything, create directories, or touch CLIs.
- **Expected POST.** `UNITS_UPDATED`, or `UNITS_RELOADED` when systemd
  reports no reload is needed. The source accepts either.

**Deviation from the instruction's expected meaning.** The reviewed M-A3 does
**not** install the recovery-witness units or tmpfiles file. Those belong to
the separate `witness-units` stage (P1A-8b / M-A9). M-A3 does less than
expected, never more, so the instruction's "if M-A3 installs them" case
applies. They are still absent.

## 4. PRE (read-only, 2026-09-28 `14:52:41Z`–`14:53:41Z`)

A local gate (`gate.py`) required all 13 checks, and all were `OK`:

1. `upgrade-status` = `SELECTED_NEW_RELEASE` / `PASS` / `[]`, with
   `current -> releases/aee323e…`;
2. observer `stableSha256` = M-A2 POST;
3. both release trees verify (0 mismatched, 0 extra, no unexpected entry);
4. NEW tree = attested `675c9482…`;
5. host service unit = OLD `249f2ec9…`;
6. keygen = OLD `f1e7020b…`;
7. no PR-1 object;
8. CURRENT `6a61c350…`, inode 1738;
9. signer inactive;
10. broker `PASS`: PID 132976, `NRestarts=0`, `42af2691…`;
11. activation `GRANT_ABSENT`;
12. boot `24d1771d…`;
13. no `.lilith-upgrade.tmp` file.

The principal and path are unchanged: OS Login `ravindupahasara2_gmail_com`,
IAP, the existing `sudo`, and tools streamed from `CONTROL_SHA`.

## 5. Mutation

`install_authority_dev.py upgrade-units 9ac7de2… aee323e… /home/ravindupahasara2_gmail_com/b1b3e-pr1a-ma1-stage/owner-baseline.json`

It ran as root, streamed from `CONTROL_SHA`, at `14:53:41Z`–`14:53:47Z`.
The report was `mutation=REPLACED`, `state=UNITS_RELOADED`, `result=PASS`,
`failures=[]`.

| Host file | Before (SHA-256 / inode) | After (SHA-256 / inode) | Attested |
| --- | --- | --- | --- |
| `/etc/systemd/system/lilith-authority-dev.service` | `249f2ec9…` (OLD) / 411 | `11b6d00f04d998caa156875fb587dd642cb7d78dd9b6d1866616cc0b9bc1b254` / 1772 | equal |
| `/etc/systemd/system/lilith-authority-dev.socket` | `bff5e927…` / 5647 | `bff5e9275ad1478dd068855465d65542ceb338e5e9236e43d1bd43d7c50c194f` / 411 (same bytes, rewritten) | equal |
| `/etc/tmpfiles.d/lilith-authority-dev.conf` | `2a1891ef…` / 5652 | `2a1891ef3c4e3e0c2916eece828c37f98f6edace9bb5bf27846c4eb28944a51e` / 5647 (same bytes, rewritten) | equal |

- All three are `root:root 0644` with new mtimes (`1790607228…`). No
  temp file remains.
- Only the service unit's content changed. It adds the hold root, the
  custody root, and the K-WIT root to `InaccessiblePaths` (PF-4, RR-34,
  RR-36).

The observer's changed sections were exactly two:

- `hostFiles`: the three files above;
- `units`: the loaded `InaccessiblePaths` of the service (§6).

Nothing else changed.

## 6. systemd manager state after M-A3

| Unit | `NeedDaemonReload` before → after | Loaded `InaccessiblePaths` after |
| --- | --- | --- |
| `lilith-authority-dev.service` | `no` → `no` | `/etc/credstore.encrypted /etc/lilith-authority-custody /var/lib/lilith-authority-custody /etc/lilith-recovery-witness /etc/lilith-memory-broker /var/lib/lilith-memory-broker /etc/lilith-os-dev`, which is the **NEW** definition |
| `lilith-authority-dev.socket` | `no` → `no` | — |

The systemd manager already reports the **new** unit definition, and no
daemon-reload ran (§2).

**Why.** Both units are inactive, not enabled, have no dependents, and
nothing references them. systemd garbage-collects such units from memory.
The next query (`systemctl show`) loads the current fragment fresh from
disk, so the manager's view equals the new bytes and `NeedDaemonReload`
stays `no`. This is ordinary systemd behaviour for unreferenced units, not
a manager reload.

Consequences:

- `upgrade-status` classifies the POST as `UNITS_RELOADED`. The reviewed
  source accepts that state (§3), and it is also what M-A5 (`upgrade-cli`)
  requires as PRE.
- The owner's M-A4 daemon-reload would find nothing pending for these two
  units. Whether M-A4 still runs as a formal step is an **owner decision**.
- **Nonclaim.** The loaded definition says nothing about execution. The
  service remains inactive, never started (`InvocationID` empty), and
  `NRestarts=0`.

## 7. POST (`14:53:47Z`–`14:54:21Z`)

| Check | Result |
| --- | --- |
| `upgrade-status` | `UNITS_RELOADED`, `PASS`, `failures=[]`. `unitsNew=true`, `unitsOld=false`, `cliOld=true`, `cliNew=false`, `reloaded=true` (observed, §6), `idle=true` |
| selector | `current -> releases/aee323e…`, unchanged |
| candidate | still attested: manifest `1d578ca7…`, tree `675c9482…`, venv `530c1453…`, 0 mismatched or extra |
| predecessor | `releases/9ac7de2…` intact: manifest `c9f2f76e…`, tree `ac62b1dd…`, venv `03bf7233…` |
| authority-dev unit assets | NEW attested bytes (§5) |
| recovery-witness unit assets | **absent**: not part of M-A3 in reviewed source (§3) |
| fixed CLIs | **OLD**: keygen `f1e7020b…`; the five new CLIs absent |
| services | authority-dev service and socket `inactive`, `loaded`, `static`, `NRestarts=0`, `MainPID=0`. Witness units `not-found`, and no witness process: the only `pgrep` match was the probe's own shell. No enablement or drop-in entries. `/run/lilith-authority-dev` absent, so tmpfiles did not run. No start, stop, or restart |
| CURRENT | `currentBlob` identical to PRE: kind, `0:0`, `0600`, device, inode 1738, size, `mtimeNs`, `ctimeNs`, SHA-256 `6a61c350…`. Not decrypted |
| host key | stat identical; never opened |
| authority / custody | all PR-1 objects absent: no K-WIT, ledger, witness, hold, PREPARED/RETIRED, registry, or owner inputs. No RecoveryEpoch |
| accounts / listings | identical to PRE |
| activation | `ACTIVATION=NOT_ACCEPTED reason=GRANT_ABSENT` |
| broker | `BROKER_PRESERVATION=PASS`, `failures=[]`; `42af2691…`, PID 132976, ticks 108213277, `NRestarts=0`; boot `24d1771d…` |

The transcripts are in `…\lilith-b1b3e-pr1a-aee323e…\ma3\` with
`SHA256SUMS`. They include the read-only reload check (`reloadcheck.out`).

## 8. Result

```text
M_A3_PASS
```

The reviewed unit and tmpfiles bytes are installed on disk. The services
are inert, and no daemon-reload or authority/custody mutation occurred.

## 9. For owner review before M-A4

- **M-A4 is the owner's `daemon-reload`.** systemd already shows the new
  definition (§6), so the reload has nothing pending for these units. The
  owner decides whether to run it as a formal no-op step or to skip it.
  M-A5's PRE is already satisfied (`UNITS_RELOADED`). Either way, M-A4 needs
  its own authorization.
- **M-A9 installs the witness units later.** They are not part of
  M-A3–M-A5.
- The merge freeze stays active until M-A6. The transfer directory
  `~/b1b3e-pr1a-ma1-stage/` still awaits cleanup authorization. A reboot or
  broker restart requires a fresh owner review.

## Explicitly not done

```text
DEV MUTATION LIMITED TO M-A3
ATTESTED UNIT ASSETS INSTALLED
ATTESTED CANDIDATE STILL SELECTED
OLD RELEASE RETAINED
FIXED CLIS NOT REPLACED
CURRENT CREDENTIAL UNCHANGED
NO DAEMON-RELOAD
NO SERVICE START/STOP/RESTART
NO K-WIT
NO LEDGER
NO WITNESS
NO HOLD
NO REGISTRY CHANGE
NO KEY ROTATION
ACTIVATION STILL DARK
M-A4 NOT AUTHORIZED
B1b-3e LIVE REHEARSAL NOT AUTHORIZED
```
