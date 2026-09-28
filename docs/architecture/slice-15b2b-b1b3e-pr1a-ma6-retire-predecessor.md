# Slice 15B2b-B1b-3e — PR-1A M-A6: Retire the Predecessor Release

Status:

- **M-A6 LIVE MUTATION**
- **PREDECESSOR RELEASE RETIRED** (`releases/9ac7de2…` removed)
- **SINGLE-RELEASE STATE RESTORED** (`status --expect L2b.2 aee323e…` PASS)
- **SERVICES INERT**
- **MERGE FREEZE SUBJECT TO OWNER LIFT** (`MERGE_FREEZE_ELIGIBLE_TO_LIFT`; not lifted)
- **M-A7 NOT AUTHORIZED**; **PR-1B NOT AUTHORIZED**; **B1b-3e LIVE REHEARSAL NOT AUTHORIZED**
- Result: **`M_A6_PASS`**

This record is on branch `claude/15b2b-b1b3e-pr1a-ma1-stage-release`, after
[M-A5](slice-15b2b-b1b3e-pr1a-ma5-install-clis.md). `origin/main` =
`d7f9f06`, unchanged. Nothing was merged, and no routine deployment was
triggered.

```text
M_A6_PASS != authority accepted != service activated != PR-1B authorized
```

## 1. Identities

| Identity | Value |
| --- | --- |
| `PAYLOAD_SOURCE_SHA` / selected release | `aee323e94412accbe321bc84eae78c5b8cf95afc` |
| `CONTROL_SHA` | `c1eb56842d464f6690b7d55a1f6915d54618e006` |
| `ARTIFACT_SHA256` | `25f1ff03f9915c19ef5835e15ff4be6d90e27d45f23e909b2a1f8bdc81a0250a` |
| `ATTESTATION_SHA256` | `86ed2659a1e8040c43bc560aeb526a5a13842314ce92f917c8868d277f65c683` |
| retired predecessor | `9ac7de22bf977385ceb954624677e33f0bae062b` |

## 2. What M-A6 is in reviewed source (confirmed before DEV contact)

The installer at `CONTROL_SHA` (`fe10d9a3…`) defines M-A6 as
`upgrade-retire-old <OLD> <NEW> <baseline>`, which is
`stage_upgrade_retire_old` (RR-25).

Preconditions, all checked before removal:

1. **`_require_upgrade`:**
   - DEV root guard (machine-id, hostname, euid 0);
   - `preservation_failures` against the owner baseline:
     - CURRENT identity and SHA-256;
     - credstore = exactly CURRENT;
     - host-key stat identity;
     - signer uid/gid;
     - custody slots not non-empty;
     - no K-WIT blob;
   - state `CLI_UPDATED`. That implies `current -> releases/<NEW>`, the NEW
     unit bytes, the NEW CLI set, `reloaded`, and `idle`. The state
     `COMPLETE_NEW_RELEASE` returns `ALREADY_COMPLETE`;
   - every deferred and custody path absent.
2. **`release_tree_failures(NEW) == []`.** NEW is independently verified
   first: every manifest file's bytes, root ownership, dirs `0755`, files
   `0644`/`0755`, no symlink, nothing extra outside `venv/`.
3. **Target check.** `releases/<OLD>` must be a real directory (not a
   symlink), and `readlink(current)` must equal `releases/<NEW>`.

Mutations: `shutil.rmtree(/opt/lilith-authority-dev/releases/<OLD>)` (it
never follows symlinks), then an fsync of `releases/`. Nothing else.

Afterwards it requires `upgrade-status` = `COMPLETE_NEW_RELEASE` and runs
`status --expect L2b.2 <NEW>`. The stage FAILs unless that passes.

This matches the authorized meaning, and it is not broader.

**Rollback acknowledgement (recorded before mutation).** M-A6 removes the
predecessor release tree. After it, the host has no release tree to roll
back to `9ac7de2`. A future rollback needs a separately reviewed
re-staging of the attested `9ac7de2` artifact. This is **release** rollback
semantics only. It is not authority, credential, registry, witness, or
RecoveryEpoch rollback.

## 3. PRE (read-only, 2026-09-28 `15:15:43Z`–`15:16:21Z`)

The principal and path are unchanged: OS Login
`ravindupahasara2_gmail_com`, IAP, the existing `sudo`, and tools streamed
from `CONTROL_SHA`. The local gate required all 25 checks, and all were
`OK`.

- **State.** `upgrade-status` = `CLI_UPDATED` / `PASS` / `[]`. Observer
  `stableSha256` = M-A5 POST.
- **Releases.** Release entries were exactly `{9ac7de2…, aee323e…}`, with
  no staging entry.
  - NEW verifies: manifest = attested `1d578ca7…`, tree `675c9482…`, 0
    mismatched or extra.
  - OLD verifies: manifest `c9f2f76e…`, tree `ac62b1dd…`, 0 mismatched or
    extra.
  - The selector pointed to `releases/aee323e…`.
- **Installed bytes.** Service, socket, and tmpfiles = attested. All six
  fixed CLIs = attested.
- **systemd.** `NeedDaemonReload=no`. There were 0 PID 1 `Reloading`
  entries since `14:00Z`, and `UnitsLoadTimestamp` was still
  `2026-09-27 06:25:33 UTC`.
- **State absent.** No PR-1 object: no K-WIT, ledger, witness, hold,
  PREPARED, RETIRED, registry, or owner inputs.
- **CURRENT.** SHA-256 `6a61c350…`, inode 1738.
- **Services.** Signer inactive; witness units `not-found`; no witness
  process.
- **Broker, activation, boot.** Broker `PASS`: `42af2691…`, PID 132976,
  `NRestarts=0`. Activation `GRANT_ABSENT`. Boot `24d1771d…`.

## 4. Mutation

`install_authority_dev.py upgrade-retire-old 9ac7de2… aee323e… /home/ravindupahasara2_gmail_com/b1b3e-pr1a-ma1-stage/owner-baseline.json`

It ran as root, streamed from `CONTROL_SHA`, at `15:16:21Z`–`15:16:27Z`.
The report was `mutation=RETIRED`, `state=COMPLETE_NEW_RELEASE`,
`statusL2b2New=PASS`, `result=PASS`, `failures=[]`.

**Removed.** Exactly the tree `/opt/lilith-authority-dev/releases/9ac7de22bf977385ceb954624677e33f0bae062b`
(inode 531025): its 24 non-venv files, including its manifest, and its
1391-entry venv.

Every change the observer saw, PRE → POST, apart from the volatile host
fields and the removed tree's own facts:

- `/opt/lilith-authority-dev/releases`: `nlink` 4 → 3 and new
  `mtime`/`ctime`;
- `releaseEntries` → `[aee323e…]`.

The observer's changed sections are exactly `releases` and `listings`.

## 5. POST (`15:16:27Z`–`15:17:06Z`)

| Check | Result |
| --- | --- |
| predecessor | `releases/9ac7de2…` **absent** |
| release inventory | exactly `[aee323e94412accbe321bc84eae78c5b8cf95afc]`. No `.staging`, no `.current.tmp`: `/opt/lilith-authority-dev` holds only `current` and `releases` |
| selector | `current -> releases/aee323e…`, unchanged (same symlink as after M-A2) |
| final status | `status --expect L2b.2 aee323e…` = **`PASS`**, `failures=[]`. `releaseSha=aee323e…`, `releaseEntries=[aee323e…]`, CURRENT `6a61c350…`, both host prerequisites `PRESENT_SECURE` |
| `upgrade-status` | `COMPLETE_NEW_RELEASE`, `PASS`, `failures=[]` |
| NEW release | tree facts identical to PRE: manifest `1d578ca7…` (attested), tree `675c9482…`, venv `530c1453…`, 0 mismatched or extra |
| installed units | unchanged and attested: service `11b6d00f…`, socket `bff5e927…`, tmpfiles `2a1891ef…` |
| installed CLIs | unchanged and attested: keygen `1fa50327…`, ledger `fda779cd…`, hold `ad3fbc94…`, verify `bc331636…`, recovery `ad928f8d…`, witness-owner `9fce2e46…` |
| CURRENT | `currentBlob` identical: kind, `0:0`, `0600`, device, inode 1738, size, `mtimeNs`, `ctimeNs`, SHA-256 `6a61c350…`. Not decrypted |
| host key | stat identical; never opened |
| authority service | `units` identical to PRE: inactive, loaded, `NRestarts=0`, never started. No lifecycle action |
| recovery witness | units `not-found`; no process; no account |
| `NeedDaemonReload` | `no` |
| daemon-reload | **not executed**: 0 PID 1 `Reloading` since `14:00Z`; `UnitsLoadTimestamp` unchanged |
| authority / custody | all absent: no K-WIT, ledger, witness, hold, PREPARED/RETIRED, registry, owner inputs, or RecoveryEpoch state |
| activation | `ACTIVATION=NOT_ACCEPTED reason=GRANT_ABSENT` |
| broker | `BROKER_PRESERVATION=PASS`, `failures=[]`. Candidate `35495854…` = accepted; `42af2691…`, PID 132976, ticks 108213277, `NRestarts=0`. needrestart `PASS` |

The transcripts are in `…\lilith-b1b3e-pr1a-aee323e…\ma6\` with
`SHA256SUMS`.

## 6. Result

```text
M_A6_PASS
```

The predecessor release is retired. DEV has returned to a coherent,
single-release, inert installation of the attested `aee323e` release.

## 7. Merge-freeze assessment

```text
MERGE_FREEZE_ELIGIBLE_TO_LIFT
```

Every condition holds:

- M-A6 PASS;
- single-release L2b.2 PASS;
- the selected release verifies;
- the units and all six CLIs verify;
- CURRENT is unchanged;
- the services are inert;
- activation is dark;
- broker preservation PASS;
- no installer temporary state remains (no `.staging`, `.current.tmp`, or
  `.lilith-upgrade.tmp`).

The freeze has **not** been lifted. The owner lifts it separately.

Notes for that decision:

- **First routine deployment.** It will also be the first DR-5 proof over
  the installed PR-1 CLIs. The expected report is
  `AUTHORITY_BOUNDARY_PROOF=PASS maturity=L1c.3` with
  `PR1_AUTHORITY_BOUNDARY maturity=P1A-5`. That is not yet proven: a FAIL
  would be a STOP, and it must not be rerun.
- **Branch order.** This evidence branch is docs-only. Merging it is what
  triggers that routine deployment.
- **Transfer directory.** `~/b1b3e-pr1a-ma1-stage/` (archive, stamp,
  baseline; `0700`, operator-owned) is transient ceremony transfer state
  outside every release, unit, CLI, and custody path. It is still present
  and awaits a separately authorized cleanup. It is not installer state and
  does not bear on the freeze.

## 8. PR-1A position after M-A6

| Phase | State |
| --- | --- |
| M-A1 stage | done (`M_A1_PASS`) |
| M-A2 select | done (`M_A2_PASS`) |
| M-A3 units | done (`M_A3_PASS`) |
| M-A4 daemon-reload | owner-skipped, not required |
| M-A5 CLIs | done (`M_A5_PASS`) |
| M-A6 retire old | done (`M_A6_PASS`) |
| M-A7 custody root | **not authorized** |
| M-A8 witness identity | **not authorized** |
| M-A9 witness units | **not authorized** |
| M-A10 skeleton | **not authorized** |
| proof gate (routine DR-5 + preservation) | pending the owner freeze lift |

## Explicitly not done

```text
DEV MUTATION LIMITED TO M-A6
PREDECESSOR RELEASE RETIRED
ATTESTED NEW RELEASE RETAINED
SINGLE-RELEASE STATE RESTORED
SELECTOR STILL POINTS TO ATTESTED RELEASE
ATTESTED UNIT FILES UNCHANGED
ATTESTED FIXED CLIS UNCHANGED
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
M-A7 NOT AUTHORIZED
PR-1B NOT AUTHORIZED
B1b-3e LIVE REHEARSAL NOT AUTHORIZED
```
