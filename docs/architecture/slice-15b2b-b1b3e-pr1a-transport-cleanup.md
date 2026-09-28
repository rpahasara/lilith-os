# Slice 15B2b-B1b-3e — PR-1A Transport Cleanup (M-A1 inputs)

Status:

- **TRANSPORT CLEANUP ONLY** (one owner-authorized removal)
- **NO RELEASE, UNIT, CLI, CREDENTIAL, CUSTODY, OR SERVICE CHANGE**
- **M-A7 NOT AUTHORIZED**; **PR-1B NOT AUTHORIZED**; **B1b-3e LIVE REHEARSAL NOT AUTHORIZED**
- Result: **`PR1A_TRANSPORT_CLEANUP_PASS`**

This record is on branch `claude/15b2b-b1b3e-pr1a-ma1-stage-release`, after
[M-A6](slice-15b2b-b1b3e-pr1a-ma6-retire-predecessor.md). The merge freeze
is `MERGE_FREEZE_ELIGIBLE_TO_LIFT` but not lifted, so nothing was merged.

## 1. What was removed

The owner authorized removing exactly
`/home/ravindupahasara2_gmail_com/b1b3e-pr1a-ma1-stage/`. That is the
transient M-A1 transfer directory, created by the operator (`0700`, inode
262572). It held only the three M-A1 transport inputs.

## 2. PRE (read-only, 2026-09-28 `15:40:20Z`–`15:40:56Z`)

The contact was the same as M-A1…M-A6: OS Login
`ravindupahasara2_gmail_com`, IAP, the existing `sudo` for the streamed
tools, and tools from `CONTROL_SHA` `c1eb568`. The local gate required 10
checks, and all were `OK`:

- **Target.** `$HOME` = `/home/ravindupahasara2_gmail_com`. The target is
  a real directory (not a symlink), `0700`, operator-owned. It lies
  outside every authority, release, custody, witness, and ledger path.
- **Contents.** Exactly three regular, non-symlink entries whose SHA-256
  equal the M-A1 record:

  | File | SHA-256 |
  | --- | --- |
  | `lilith-authority-dev-release.tar.gz` | `25f1ff03…250a` |
  | `lilith-authority-dev-release.attestation.json` | `9441c985…1b42` |
  | `owner-baseline.json` | `8cc1a58a…b73e` |

- **Host.**
  - The observer `stableSha256` equals the M-A6 POST.
  - `status --expect L2b.2 aee323e…` = `PASS`, `failures=[]`.
  - Broker `PASS`: `42af2691…`, PID 132976, ticks 108213277,
    `NRestarts=0`.
  - Boot `24d1771d…`.
  - `ACTIVATION=NOT_ACCEPTED reason=GRANT_ABSENT`.

## 3. Mutation (`15:40:56Z`–`15:41:02Z`)

It ran as the operator, without sudo, in one command that first repeated
the path, type, exact-entry, and `sha256sum -c --strict` checks. Then it
ran `rm -f` on the three named files only, followed by `rmdir` of the
directory. `rmdir` fails if anything else is present, so nothing
unverified could be removed. Result: `CLEANUP_DONE`, then
`STAGE_DIR_ABSENT`.

No wildcard, no `rm -r`, and no sudo were used for the removal.

## 4. POST (`15:41:02Z`–`15:41:26Z`)

| Check | Result |
| --- | --- |
| staging directory | absent (checked twice) |
| host observation | `stableSha256` `d92a6f1c…` **identical to PRE**, so `/opt/lilith-authority-dev`, the units, CLIs, CURRENT, host key, services, accounts, listings, PR-1 objects, and filesystems are all unchanged |
| selector / release | `current -> releases/aee323e…`; releases = `[aee323e…]`; manifest `1d578ca7…`, tree `675c9482…`, venv `530c1453…`, 0 mismatched or extra |
| units | service `11b6d00f…`, socket `bff5e927…`, tmpfiles `2a1891ef…` |
| six CLIs | keygen `1fa50327…`, ledger `fda779cd…`, hold `ad3fbc94…`, verify `bc331636…`, recovery `ad928f8d…`, witness-owner `9fce2e46…` |
| `status --expect L2b.2 aee323e…` | `PASS`, `failures=[]` |
| CURRENT | SHA-256 `6a61c350…`, inode 1738, unchanged |
| authority service | inactive, `NRestarts=0`. 0 PID 1 `Reloading` since `14:00Z` |
| authority / custody | no K-WIT, ledger, witness, hold, registry, or RecoveryEpoch state |
| broker | `PASS`: `42af2691…`, PID 132976, ticks 108213277, `NRestarts=0` |
| activation | `NOT_ACCEPTED reason=GRANT_ABSENT` |

**Observation, not a change.** The operator home also holds a pre-existing
file `NUL` (38 bytes, dated 2026-09-23). It is an old Windows-redirect
artifact from an earlier session, unrelated to this ceremony, and it was
left untouched.

The transcripts are in `…\lilith-b1b3e-pr1a-aee323e…\cleanup\` with
`SHA256SUMS`.

## 5. Routine deployments around the ceremony (observed from GitHub, read-only)

The owner merged PR #94 (the M-A1…M-A6 evidence) as main `0621f26`. That
lifted the freeze after M-A6 and before this cleanup.

| Run | Candidate | Window (UTC) | DR-5 |
| --- | --- | --- | --- |
| `36432097677` | `d7f9f06` (final-gate record) | `13:55:26Z`–`14:01:01Z`, **before** M-A1 PRE (`14:09:40Z`) | `AUTHORITY_BOUNDARY_PROOF=PASS maturity=L1c.3`, `PR1_AUTHORITY_BOUNDARY maturity=PR1_ABSENT` |
| `36443835331` | `0621f26` (merge of PR #94) | `15:28:26Z`–`15:34:05Z`, **after** M-A6 (`15:16:27Z`), before this cleanup | `SUDO_EFFECTIVE_PROOF=PASS`; `AUTHORITY_BOUNDARY_PROOF=PASS maturity=L1c.3`; **`PR1_AUTHORITY_BOUNDARY maturity=P1A-5`** |

What the two runs show:

- No routine deployment ran between `upgrade-stage` and
  `upgrade-retire-old`, so the preflight §9 freeze held.
- Run `36443835331` is the first DR-5 proof over the installed PR-1 CLIs,
  and it returned exactly the expected ladder step. For example,
  `DENIED: sudo /usr/local/sbin/lilith-recovery-witness-owner-dev` and
  `DENIED: test -w` on it.
- The cleanup PRE observer equalled the M-A6 POST observer. The routine
  deployment therefore changed no authority state.

## 6. Result

```text
PR1A_TRANSPORT_CLEANUP_PASS
```

The owner workstation still holds the candidate artifact, and this
removal does not change it.

## Explicitly not done

```text
TRANSPORT DIRECTORY ONLY REMOVED
NO RELEASE / UNIT / CLI CHANGE
CURRENT CREDENTIAL UNCHANGED
NO DAEMON-RELOAD
NO SERVICE START/STOP/RESTART
NO K-WIT
NO LEDGER
NO WITNESS
NO HOLD
NO REGISTRY CHANGE
ACTIVATION STILL DARK
M-A7 NOT AUTHORIZED
PR-1B NOT AUTHORIZED
B1b-3e LIVE REHEARSAL NOT AUTHORIZED
```
