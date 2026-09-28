# Slice 15B2b-B1b-3e — PR-1A M-A5: Install the Reviewed Fixed CLIs

Status:

- **M-A5 LIVE MUTATION**
- **FIXED CLIS INSTALLED**
- **SERVICES INERT**
- **M-A4 SKIPPED / NOT REQUIRED** (owner decision). `NeedDaemonReload=no`,
  and no daemon-reload was executed
- **M-A6 NOT AUTHORIZED**
- **B1b-3e LIVE REHEARSAL NOT AUTHORIZED**
- Result: **`M_A5_PASS`**

This record is on branch `claude/15b2b-b1b3e-pr1a-ma1-stage-release`, after
[M-A3](slice-15b2b-b1b3e-pr1a-ma3-install-units.md). The merge freeze is
still active, so nothing was merged. `origin/main` = `d7f9f06`, unchanged.

```text
CLI installation != service activation != authority acceptance
```

## 1. Identities

| Identity | Value |
| --- | --- |
| `PAYLOAD_SOURCE_SHA` / selected NEW | `aee323e94412accbe321bc84eae78c5b8cf95afc` |
| `CONTROL_SHA` | `c1eb56842d464f6690b7d55a1f6915d54618e006` |
| `ARTIFACT_SHA256` | `25f1ff03f9915c19ef5835e15ff4be6d90e27d45f23e909b2a1f8bdc81a0250a` |
| `ATTESTATION_SHA256` | `86ed2659a1e8040c43bc560aeb526a5a13842314ce92f917c8868d277f65c683` |
| retained OLD | `9ac7de22bf977385ceb954624677e33f0bae062b` |

## 2. M-A4 skipped, and why that is source-consistent

The owner skipped M-A4 (the owner `daemon-reload`) as not required. In the
installer at `CONTROL_SHA` (`fe10d9a3…`):

- `stage_upgrade_cli` accepts `UNITS_RELOADED` as its entry state, or
  `CLI_UPDATED` for `ALREADY_COMPLETE`.
- The classification table defines `UNITS_RELOADED` and `CLI_UPDATED` with
  `reloaded=true`.
- No stage requires a reload event, only the observed manager state
  (`LoadState=loaded`, `NeedDaemonReload=no`).

The post-M-A3 state was already `UNITS_RELOADED` with `NeedDaemonReload=no`,
explained in the M-A3 record §6. No daemon-reload was executed to preserve
ceremony numbering, and none has been executed since the L1c.2 reload of
2026-09-27 (§6).

## 3. What M-A5 is in reviewed source (confirmed before DEV contact)

M-A5 is `upgrade-cli <OLD> <NEW> <baseline>`, which is `stage_upgrade_cli`.

- **Guard.** `_require_upgrade` checks baseline preservation, the state
  `UNITS_RELOADED`, and that the deferred and custody paths are absent.
- **Keygen.** It **replaces** `/usr/local/sbin/lilith-authority-keygen-dev`
  from `releases/<NEW>/cli/…`: an `O_EXCL` temp file, fsync, root `0755`,
  rename, directory fsync.
- **New CLIs.** It **creates** `/usr/local/sbin/lilith-authority-ledger-dev`,
  `…-hold-dev`, `…-verify-dev`, `…-recovery-dev`, and
  `…/lilith-recovery-witness-owner-dev`. Each is created `O_EXCL`, root
  `0755`, fsynced. An existing file with other bytes raises
  `CLI_COLLISION`.
- **Directory.** Then it fsyncs `/usr/local/sbin`.
- **It does not** run `systemctl` (beyond the read-only `show` inside
  `upgrade-status`), daemon-reload, start/stop/restart/enable anything,
  touch units or the selector, or create custody, witness, ledger, or hold
  state.
- **Expected POST.** `CLI_UPDATED`.

## 4. PRE (read-only, 2026-09-28 `15:03:31Z`–`15:03:59Z`)

The principal and path are unchanged: OS Login
`ravindupahasara2_gmail_com`, IAP, the existing `sudo`, and tools streamed
from `CONTROL_SHA`. The local gate required all 17 checks, and all were
`OK`:

1. `upgrade-status` = `UNITS_RELOADED` / `PASS` / `[]`, with
   `current -> releases/aee323e…`;
2. observer `stableSha256` = M-A3 POST;
3. both trees verify, and the NEW tree is the attested `675c9482…`;
4. installed service unit = NEW attested;
5. installed socket = NEW attested;
6. installed tmpfiles = NEW attested;
7. keygen = OLD `f1e7020b…`;
8. the five new CLIs absent;
9. `NeedDaemonReload=no` for both authority units;
10. no PR-1 object;
11. CURRENT `6a61c350…`, inode 1738;
12. signer inactive;
13. broker `PASS`: PID 132976, `NRestarts=0`, `42af2691…`;
14. activation `GRANT_ABSENT`;
15. boot `24d1771d…`;
16. no temp file;
17. no recovery-witness process.

## 5. Mutation

`install_authority_dev.py upgrade-cli 9ac7de2… aee323e… /home/ravindupahasara2_gmail_com/b1b3e-pr1a-ma1-stage/owner-baseline.json`

It ran as root, streamed from `CONTROL_SHA`, at `15:03:59Z`–`15:06:06Z`.
The report was `mutation=REPLACED`, `state=CLI_UPDATED`, `result=PASS`,
`failures=[]`.

| CLI | Before | After (SHA-256) | Owner / mode | Attested |
| --- | --- | --- | --- | --- |
| `/usr/local/sbin/lilith-authority-keygen-dev` | `f1e7020b…` (OLD) | `1fa50327bb9cb402dc38f6e8a3742362901ba4dbd5c48f8474dc7c6c4e134472` | `root:root 0755` | equal |
| `/usr/local/sbin/lilith-authority-ledger-dev` | absent | `fda779cd0dcecdc26e371082078306978f97e4f7097acae780fa6f38180fc45b` | `root:root 0755` | equal |
| `/usr/local/sbin/lilith-authority-hold-dev` | absent | `ad3fbc9442db715595683f4602e8b2fd62d22697703e888eda2ef30c0121da1b` | `root:root 0755` | equal |
| `/usr/local/sbin/lilith-authority-verify-dev` | absent | `bc331636eedbbae22a53667aa230ba0672fb1e22b8a5bd4975ac9f8557a400a4` | `root:root 0755` | equal |
| `/usr/local/sbin/lilith-authority-recovery-dev` | absent | `ad928f8d56062763da156084f5375c23dabfdcced396a065ba4cc2719e01cc74` | `root:root 0755` | equal |
| `/usr/local/sbin/lilith-recovery-witness-owner-dev` | absent | `9fce2e460a9c279f99b59c6e251b813375a1be404ae611d379fed5cd812f16ab` | `root:root 0755` | equal |

`/usr/local/sbin` now holds exactly:

- `lilith-activation-verify` and `lilith-dev-deploy`, both unchanged;
- the six fixed CLIs above.

No extra CLI and no temp file.

The observer's changed sections, PRE → POST, are exactly `hostFiles` (the
six CLIs) and `namespaceInventory` (the five new names). Nothing else
changed.

## 6. POST (`15:06:06Z`–`15:06:31Z`)

| Check | Result |
| --- | --- |
| `upgrade-status` | `CLI_UPDATED`, `PASS`, `failures=[]`. `cliNew=true`, `cliOld=false`, `unitsNew=true`, `reloaded=true` (observed), `idle=true` |
| selector | `current -> releases/aee323e…`, unchanged |
| candidate | release section identical to PRE: manifest `1d578ca7…`, tree `675c9482…`, venv `530c1453…`, 0 mismatched or extra |
| predecessor | `releases/9ac7de2…` intact: manifest `c9f2f76e…`, tree `ac62b1dd…`, venv `03bf7233…` |
| installed units | NEW attested, unchanged: service `11b6d00f…`, socket `bff5e927…`, tmpfiles `2a1891ef…`. Witness units absent (M-A9) |
| fixed CLIs | all six = NEW attested bytes (§5) |
| CURRENT | `currentBlob` identical to PRE: kind, `0:0`, `0600`, device, inode 1738, size, `mtimeNs`, `ctimeNs`, SHA-256 `6a61c350…`. Not decrypted |
| host key | stat identical; never opened |
| services | `units` section identical to PRE. authority-dev service and socket `inactive`, `loaded`, `NRestarts=0`, never started. Recovery-witness `not-found`, and no witness process (`WITNESS_PROCS=0`). No lifecycle operation |
| daemon-reload | **not executed**. `NeedDaemonReload=no`, `UnitsLoadTimestamp` still `Sun 2026-09-27 06:25:33 UTC`, and 0 PID 1 `Reloading` journal entries since `14:00Z` |
| authority / custody | all PR-1 objects absent: no K-WIT, ledger, witness, hold, PREPARED/RETIRED, registry, or owner inputs. No RecoveryEpoch |
| accounts / listings | identical to PRE |
| activation | `ACTIVATION=NOT_ACCEPTED reason=GRANT_ABSENT` |
| broker | `BROKER_PRESERVATION=PASS`, `failures=[]`. Candidate `35495854…` = accepted; `42af2691…`, PID 132976, ticks 108213277, `NRestarts=0`; boot `24d1771d…`. The report now lists the five new CLIs among its *reported* custody paths. That is reporting, not judgment, and it is why the transcript grew |

**Note (M-A5-1).** The local gcloud/plink client for the final read-only
POST call exited `0xC0000005` after returning its complete output. It was
a workstation-side crash, as seen in M-A2. It is not a DEV event.

The transcripts are in `…\lilith-b1b3e-pr1a-aee323e…\ma5\` with
`SHA256SUMS`.

## 7. Result

```text
M_A5_PASS
```

The reviewed fixed CLI set is installed, byte-identical to the attested
candidate, and coherent with the selected release. The services are inert.

## 8. For owner review before M-A6

- **M-A6 (`upgrade-retire-old`) needs its own authorization.** It removes
  `releases/9ac7de2…` only if NEW verifies, and its POST is
  `status --expect L2b.2 aee323e…`.
  - It is the last point with the OLD tree on host. After it, release
    rollback means re-staging the reviewed `9ac7de2` archive (RR-25).
  - Release rollback is not authority rollback.
- **Merge freeze.** It stays until M-A6 completes. After M-A6, the next
  routine deployment is also the first DR-5 proof over the new CLIs. Expect
  `PR1_AUTHORITY_BOUNDARY maturity=P1A-5`, if the ladder objects are present
  as designed.
- **Cleanup.** The transfer directory `~/b1b3e-pr1a-ma1-stage/` still awaits
  cleanup authorization.
- **Reboot / broker restart.** Either one requires a fresh review.

## Explicitly not done

```text
M-A4 SKIPPED AS NOT REQUIRED
DEV MUTATION LIMITED TO M-A5
ATTESTED FIXED CLIS INSTALLED
ATTESTED CANDIDATE STILL SELECTED
OLD RELEASE RETAINED
ATTESTED UNIT FILES REMAIN INSTALLED
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
M-A6 NOT AUTHORIZED
B1b-3e LIVE REHEARSAL NOT AUTHORIZED
```
