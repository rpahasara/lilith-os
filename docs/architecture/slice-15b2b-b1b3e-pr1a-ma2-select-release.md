# Slice 15B2b-B1b-3e — PR-1A M-A2: Select the Staged Release

Status:

- **M-A2 LIVE MUTATION**
- **CANDIDATE SELECTED** (`current -> releases/aee323e…`)
- **UNITS/CLIS STILL OLD**
- **M-A3 NOT AUTHORIZED**
- **B1b-3e LIVE REHEARSAL NOT AUTHORIZED**
- Result: **`M_A2_PASS`**

This record is on branch `claude/15b2b-b1b3e-pr1a-ma1-stage-release`, after
the [M-A1 record](slice-15b2b-b1b3e-pr1a-ma1-stage-release.md). The
ceremony's merge freeze is still active, so this branch is not merged.

```text
selected release != running release != authority != activation
```

## 1. Identities

| Identity | Value |
| --- | --- |
| `PAYLOAD_SOURCE_SHA` / NEW | `aee323e94412accbe321bc84eae78c5b8cf95afc` |
| `CONTROL_SHA` | `c1eb56842d464f6690b7d55a1f6915d54618e006` |
| `ARTIFACT_SHA256` | `25f1ff03f9915c19ef5835e15ff4be6d90e27d45f23e909b2a1f8bdc81a0250a` |
| `ATTESTATION_SHA256` | `86ed2659a1e8040c43bc560aeb526a5a13842314ce92f917c8868d277f65c683` |
| OLD | `9ac7de22bf977385ceb954624677e33f0bae062b` |

`origin/main` = `d7f9f06`, unchanged since M-A1. It holds only the
docs-only final-gate merge after `CONTROL_SHA`. Nothing was merged during
this step.

## 2. What M-A2 is in reviewed source (confirmed before DEV contact)

The installer at `CONTROL_SHA` (SHA-256 `fe10d9a3…5487`) defines M-A2 as
`upgrade-select <OLD> <NEW> <baseline>`, which is `stage_upgrade_select`.

**Refusals before any mutation.** `_require_upgrade`:

- requires baseline preservation;
- requires state `STAGED_NEW_RELEASE`, or `SELECTED_NEW_RELEASE`, which
  returns `ALREADY_COMPLETE`;
- requires the deferred and custody paths to be absent.

The stage then requires `release_tree_failures(NEW) == []`, and refuses if
`/opt/lilith-authority-dev/.current.tmp` exists.

**The only mutation.** It runs
`symlink("releases/<NEW>", /opt/lilith-authority-dev/.current.tmp)`, then
`lchown(tmp, 0, 0)`, then `rename(tmp, /opt/lilith-authority-dev/current)`,
which is an atomic same-directory replace. Last, it fsyncs
`/opt/lilith-authority-dev`.

**Expected POST.** `SELECTED_NEW_RELEASE`: both releases present,
`current -> releases/<NEW>`, units and CLIs still OLD, and the observed
manager state `reloaded=true`. That is `LoadState=loaded` with
`NeedDaemonReload=no`, read by `systemctl show`. It is not an action.

This is the authorized meaning: only the release selector changes.

## 3. PRE (read-only, 2026-09-28 `14:40:54Z`–`14:42:23Z`)

**Contact.** The same principal and path as M-A1: OS Login
`ravindupahasara2_gmail_com`, `gcloud compute ssh --tunnel-through-iap`,
the existing `sudo`, and tools streamed from `CONTROL_SHA`.

**Observer.** The reviewed observer's `stableSha256` was `8b5ebfdb…`, equal
to M-A1's POST, with no section differing.

| Check | Result |
| --- | --- |
| boot ID | `24d1771d-e1b5-4e5f-816d-da08ad8b367a`, unchanged |
| broker | `BROKER_PRESERVATION=PASS`; `42af2691…`, PID 132976, ticks 108213277, `NRestarts=0` |
| activation | `NOT_ACCEPTED reason=GRANT_ABSENT` |
| CURRENT | inode 1738, SHA-256 `6a61c350…`, unchanged |
| services | authority-dev inactive; witness units `not-found` |
| trees | OLD: manifest `c9f2f76e…`, tree `ac62b1dd…`, 0 mismatched or extra. NEW: manifest `1d578ca7…` (attested), tree `675c9482…` (attested), 0 mismatched or extra |
| selector | `current -> releases/9ac7de2…` |
| `upgrade-status` | `STAGED_NEW_RELEASE`, `PASS`, `failures=[]`. Re-checked as the gate immediately before the stage |
| PR-1 objects | all absent: no K-WIT, ledger, witness, hold, PREPARED, or RETIRED |
| `.current.tmp` | absent |
| staging inputs | archive `25f1ff03…`, stamp `9441c985…`, and baseline `8cc1a58a…` all still hash-valid |

## 4. Mutation

`install_authority_dev.py upgrade-select 9ac7de2… aee323e… /home/ravindupahasara2_gmail_com/b1b3e-pr1a-ma1-stage/owner-baseline.json`

It ran as root, streamed from `CONTROL_SHA`, at `14:42:23Z`–`14:42:29Z`. The
report was `mutation=SELECTED`, `state=SELECTED_NEW_RELEASE`,
`result=PASS`, `failures=[]`.

Every change the observer saw, PRE → POST, besides the volatile host fields:

- `/opt/lilith-authority-dev/current`:
  - target `releases/9ac7de2…` → `releases/aee323e…`;
  - a new inode (574298 → 578158) from the atomic rename;
  - new `mtime`/`ctime`.
- `/opt/lilith-authority-dev`: directory `mtime`/`ctime` updated by the
  rename.

Nothing else changed. `.current.tmp` is absent afterwards, and
`/nonexistent` is still absent.

## 5. POST (`14:42:29Z`–`14:43:02Z`)

| Check | Result |
| --- | --- |
| `upgrade-status` | `SELECTED_NEW_RELEASE`, `PASS`, `failures=[]`. `unitsOld=true`, `unitsNew=false`, `cliOld=true`, `cliNew=false`, `reloaded=true` (an observation of the existing manager state, not a reload; see the [M-A3 record](slice-15b2b-b1b3e-pr1a-ma3-install-units.md) §2), `idle=true` |
| selector | `current -> releases/aee323e94412accbe321bc84eae78c5b8cf95afc` |
| candidate | unchanged and still attested: manifest `1d578ca7…`, tree `675c9482…`, venv `530c1453…`, 0 mismatched or extra |
| old release | `releases/9ac7de2…` present and intact: manifest `c9f2f76e…`, tree `ac62b1dd…`, venv `03bf7233…` |
| installed unit bytes | **OLD** (observer `hostFiles` identical to PRE): service `249f2ec9…`, socket `bff5e927…`, tmpfiles `2a1891ef…`. The witness units are absent |
| installed CLI bytes | **OLD**: keygen `f1e7020b…`. The five new CLIs are absent |
| CURRENT | `currentBlob` identical to PRE: kind, `0:0`, `0600`, device, inode 1738, size, `mtimeNs`, `ctimeNs`, SHA-256 `6a61c350…`. Not decrypted |
| host key | stat identical; never opened |
| services | `units` section identical to PRE. authority-dev inactive, `static`, `NeedDaemonReload=no`, `NRestarts=0`, never started. Witness units `not-found`. No daemon-reload |
| custody / authority | all PR-1 objects absent: no K-WIT, ledger, witness, hold, PREPARED/RETIRED, registry, or owner inputs. No RecoveryEpoch exists |
| accounts | unchanged; no witness account |
| activation | `NOT_ACCEPTED reason=GRANT_ABSENT` |
| broker | `BROKER_PRESERVATION=PASS`, `failures=[]`; `42af2691…`, PID 132976, ticks 108213277, `NRestarts=0`; boot unchanged |
| needrestart | `PASS` |

**Note (M-A2-1).** During PRE, the local `gcloud`/`plink` client for one
read-only call exited with Windows status `0xC0000005` *after* returning its
complete output. This was a workstation-side client crash. Every remote
command in that call had finished. It is not a DEV event.

## 6. Result

```text
M_A2_PASS
```

The attested candidate is now the selected release source. The active unit
files, CLIs, services, credentials, and custody state are unchanged.

## 7. Remaining for the owner

- **M-A3 (`upgrade-units`) needs its own explicit authorization.** Its PRE
  is `upgrade-status … SELECTED_NEW_RELEASE`.
- **The routine-deployment merge freeze stays active until M-A6.**
- **Selector consequence.** A signer start is not authorized. If one were
  attempted, the OLD unit file would run `ExecStart` from `current`, which
  now resolves to the NEW release tree. Nothing starts the signer in PR-1A.
- **Transfer directory.** `~/b1b3e-pr1a-ma1-stage/` remains, pending a
  separately authorized cleanup.

## Explicitly not done

```text
DEV MUTATION LIMITED TO M-A2
ATTESTED CANDIDATE SELECTED
OLD RELEASE RETAINED
UNIT FILES NOT REPLACED
CLI FILES NOT REPLACED
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
M-A3 NOT AUTHORIZED
B1b-3e LIVE REHEARSAL NOT AUTHORIZED
```
