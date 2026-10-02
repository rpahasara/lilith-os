# Slice 15B2b-B1b-3e — Broker Preservation Recovery: Controlled Broker Restart (evidence and acceptance request)

Status:

- **`BROKER_PRESERVATION_RECOVERY_READY_FOR_OWNER_REVIEW`.** This record
  answers the
  [Condition 3 STOP](slice-15b2b-b1b3e-condition3-fresh-pr2-stop.md). It
  records one owner-authorized live mutation: a restart of the memory broker
  only. It holds the evidence for the new broker candidate, and it asks the
  owner to accept that candidate (§6).
- **Broker preservation is NOT restored yet.** As in the accepted reboot flow:
  - `preservation` fails by design until the owner accepts the candidate
    here (step 1);
  - and until a separate reviewed re-pin pins it (step 2,
    `claude/15b2b-b1b3e-broker-restart-repin`).

  An offline replay of the real post-restart observation shows that the
  re-pinned `preservation` PASSES (§4).
- **Not authorization of anything else.** The B-5 grant stays void.
  Condition 3 has not been re-run. Condition 4 has not been evaluated. M-B1
  is NOT AUTHORIZED.

```text
broker restarted != candidate accepted != re-pinned != preservation PASS != PR-2 PASS != eligible
```

## 1. Why a broker restart, not a reboot

- **The STOP cause.** The running broker (PID 2586) mapped a `libcrypto.so.3`
  that the 2026-10-01 `libssl3t64` upgrade had deleted. The verifier's
  structural rule is that every mapped library must be non-deleted, with the
  on-disk inode equal to the mapped one. Any new broker process satisfies
  it. A reboot is not needed, and the owner preferred the restart.
- **Same accepted tools and pattern.** The recovery uses the reviewed tools
  at control `main` `094b914`, and the accepted ceremony pattern of the
  [pre-PR-1B reboot](slice-15b2b-b1b3e-pre-pr1b-reboot-rebaseline.md):
  - the read-only gate §3.2;
  - the broker start §6 (M-R2), here as `restart`;
  - the baseline procedure §8;
  - owner acceptance, then a separate re-pin
    ([re-pin record](slice-15b2b-b1b3e-broker-preservation-repin.md)).
- **One gap, recorded rather than invented around.** `rebaseline` was written
  for the post-reboot case. It requires a boot different from the accepted
  boot, and otherwise adds `REBOOT_NOT_OBSERVED`. After a same-boot restart
  that is its **only** failure (§3). It therefore emits the candidate but not
  its digest.
  - The digest was computed with the verifier's own `canonical_sha256` over
    that candidate.
  - It was confirmed by an exact offline replay (§4).
  - No new operation was added. Whether to add a same-boot
    `restart-rebaseline` operation for future recoveries is a separate,
    optional source change.
- **What `preservation` checks.** `preservation` requires the **same** boot
  as the accepted one. The accepted boot ID `eea461c3…` therefore stays
  pinned, and only the process identity changes.

## 2. Pre-recovery gate (read-only), `2026-10-02T10:10:35Z`–`10:14:30Z`

| # | Check | Observed |
| --- | --- | --- |
| G0 | control source | `origin/main` = `094b91481940ec5529cae14ef787a77a372a7259`. Observer `7d1e3e89…`, installer `c265433e…`, broker verifier `451f418a…` and needrestart probe `6d8e281b…` are the same git blobs as at `b4def65` |
| G1 | no run in flight | the `094b914` deploy (run `36993433277`) finished at `10:10:05Z` with success. Its 186-line boundary result set and DR-5 block equal the accepted run `36552218231` |
| G3 | GCE identity | id `7687007163730582258`, `RUNNING`, `automaticRestart=True`, `MIGRATE` |
| G4 | host / boot | boot `eea461c3-60f0-4b10-8ee9-556dcef19711`, kernel `7.0.0-1013-gcp` |
| G5 | observer | `stableSha256` `c4a65403…`, equal to the STOP window |
| G6 | installer | `status --expect P1A-9` PASS, `failures=[]` |
| G7 | broker | PID `2586`, incarnation `84798e5b…`, `NRestarts=0`. **5 deleted mapping lines** (one file: `libcrypto.so.3`). `preservation` FAIL, byte-identical to the STOP record (`a7caaf68…`): `RUNTIME_SUBSTRATE_STALE_OR_UNREADABLE`, `ACCEPTED_IDENTITY_CHANGED:sharedLibrariesSha256`, `BASELINE_CANDIDATE_CHANGED` |
| G8 | activation | `ACTIVATION=NOT_ACCEPTED reason=GRANT_ABSENT`, rc 1 |
| G9 | needrestart | `NEEDRESTART_LILITH_OVERRIDE=PASS`; the broker, authority and witness services are `EXCLUDED` |
| G11 | package manager | idle (only the unattended-upgrades shutdown waiter), `dpkg --audit` clean, `REBOOT_REQUIRED=absent`. Next `apt-daily-upgrade` is `2026-10-03 06:39Z` |
| G12 | enablement | only `lilith-os-api-dev.service` is enabled. No authority, witness, broker or Stage III unit is enabled; no LILITH timer |
| — | authority / witness units | inactive, `static`, no InvocationID, `NRestarts=0` |

## 3. The mutation and the new candidate

**M-BR1 (the only mutation), `2026-10-02T10:15:56Z`.** It is guarded on the
exact boot, PID and incarnation:

```bash
dev 'test "$(cat /proc/sys/kernel/random/boot_id)" = eea461c3-60f0-4b10-8ee9-556dcef19711 || exit 96;
     test "$(systemctl show -p MainPID --value lilith-memory-broker.service)" = 2586 || exit 95;
     test "$(systemctl show -p InvocationID --value lilith-memory-broker.service)" = 84798e5b74494e1ea362ce90f1cf04ad || exit 94;
     sudo -n /usr/bin/systemctl restart lilith-memory-broker.service'
```

- It returned `restart-rc=0`.
- There was no `enable`, no `daemon-reload`, no other unit, and no retry.
- The socket was not restarted: its InvocationID `c2b1e4db…` is unchanged.

**Post-restart gates.** Two read-only gates, `10:16:24Z`–`10:17:42Z` and,
after five minutes or more, `10:23:06Z`–`10:24:22Z`:

| Item | Value |
| --- | --- |
| service | `active/running`, `static`, `NRestarts=0`, `Result=success` |
| **new incarnation** | **`c4b9cb38d7a041dc91db0d8ada7e8d04`** |
| **new PID / start ticks** | **`35622`** / **`26369693`** (start `2026-10-02T10:15:55Z`) |
| boot | `eea461c3-60f0-4b10-8ee9-556dcef19711` (unchanged) |
| release / manifest | `817a83e44cec8965479fd97fc30b7a0b3ae49ab2` / `7a46ac83…` (unchanged) |
| **deleted mappings** | **0**: both `map_files` and `maps` count 0. All 25 mapped files are non-deleted and inode-equal to disk |
| `sharedLibrariesSha256` | `818994544397da37d5a97e3799afff314608a7aa00cad50c968a90b86f41ce60` |
| `rebaseline` (both gates) | `FAIL`, **only `REBOOT_NOT_OBSERVED`** (§1). Every fact is `true`: `releaseEquivalent`, `configEquivalent`, `stateEquivalent`, `identityBoundaryEquivalent`, `socketBoundaryEquivalent`, `deployerPolicyTextEquivalent`, `stageIIIUntouched`, `incarnationHealthy`. `RUNTIME_SUBSTRATE_STALE_OR_UNREADABLE` is gone |
| **candidate digest** | **`a30bd7d6e26a75e4eba863c08622aebbbaf72928bc9dc7737fc1f7aa6473069d`** (`canonical_sha256` of the candidate) |
| stability | both gates give a byte-identical `rebaseline` output (`f61fb63d…`) and raw observation (`20456431…`): no restart, no library replacement |
| `preservation` (current pins) | `FAIL` by design: `RUNTIME_INCARNATION_NOT_ACCEPTED_BASELINE`, and `ACCEPTED_IDENTITY_CHANGED` for `pid`, `startTicks` and `sharedLibrariesSha256`, and `BASELINE_CANDIDATE_CHANGED`. Nothing else |

## 4. Offline proof that the re-pin restores `preservation`

To make the re-pin checkable against real data, the gates also captured the
verifier's own `collect()` observation. This is the same read-only
collection that `preservation` performs, from the `094b914` verifier source
with only its `main()` call replaced by a JSON dump. It was replayed in WSL
(Linux, so the verifier's path constants are exact) by
`tools/offline_eval.py`:

| Replay | Result |
| --- | --- |
| pre-restart observation, current pins | `preservation` and `rebaseline` failures **identical** to the host runs (a faithful replay) |
| post-restart observations (both), current pins | identical to the host runs |
| **post-restart observations (both), pins = the §3 candidate** | **`BROKER_PRESERVATION=PASS`, `failures=[]`** |

The re-pin values are exactly those of the step-2 source change:
- incarnation `c4b9cb38…`;
- baseline `a30bd7d6…`;
- boot `eea461c3…`;
- identity: PID `35622`, start ticks `26369693`, `nRestarts` `"0"`, release
  `817a83e4…`, manifest `7a46ac83…`, libraries `81899454…`.

## 5. Authority state after the restart

- **Observer.** `stableSha256` changed from `c4a65403…` to
  `c54f21ba09bdc3b3fb0434ec35875fb280d2042716d4e0111b124d8faf386f33`.
  **Only the `units` section changed:** the broker's MainPID, InvocationID and
  timestamps. These sections are identical:
  - `accounts`, `currentBlob`, `filesystems`, `host`;
  - `hostFiles`, `hostKey`, `listings`;
  - `namespaceInventory`, `pr1Objects`, `releases`.

  `c54f21ba…` is the new observer baseline. No source pins the observer
  digest.
- **`status --expect P1A-9`** PASS. No K-WIT, registry, ledger, witness
  state or hold exists.
- **Activation** stays `GRANT_ABSENT`.
- **Authority and witness units** are inactive, with no InvocationID.
- **No authority material was created.**
- **Replica A** is byte-identical (0 records, manifest `fbdd045c…`).
  Replica B was not contacted.

## 6. Owner acceptance (step 1 of 2)

The owner accepts, or declines, the candidate below as the new broker
continuity baseline, for **broker runtime scope only**:

| Field | Value |
| --- | --- |
| candidate digest | `a30bd7d6e26a75e4eba863c08622aebbbaf72928bc9dc7737fc1f7aa6473069d` |
| incarnation | `c4b9cb38d7a041dc91db0d8ada7e8d04` |
| boot | `eea461c3-60f0-4b10-8ee9-556dcef19711` |
| PID / start ticks | `35622` / `26369693` |
| shared libraries | `818994544397da37d5a97e3799afff314608a7aa00cad50c968a90b86f41ce60` |
| `nRestarts` | `0` |
| release | `817a83e44cec8965479fd97fc30b7a0b3ae49ab2` |
| manifest | `7a46ac83001411a29b1bc4be7e0f91f09c5879967386c452b2620e23d16e4614` |
| supersedes (retired on acceptance) | incarnation `84798e5b74494e1ea362ce90f1cf04ad`, candidate `5000374513f38144c90bd75aefdabb4d000f644e024107bf275da9f80af7dbe2`, PID `2586` |

**Owner statement** (verbatim, given 2026-10-02 after this record merged in
#127 with the placeholder still in place; recorded here by a one-purpose
follow-up change):

```text
I accept the recovered broker candidate:

a30bd7d6e26a75e4eba863c08622aebbbaf72928bc9dc7737fc1f7aa6473069d

with broker incarnation:

c4b9cb38d7a041dc91db0d8ada7e8d04

as the accepted recovered DEV broker runtime candidate following the controlled broker-only restart.

I accept that:
- the boot remains eea461c3-60f0-4b10-8ee9-556dcef19711;
- the broker has no deleted shared-library mappings;
- the post-restart candidate is stable across both accepted observation gates;
- activation remains NOT_ACCEPTED / GRANT_ABSENT;
- authority and witness material remain absent;
- Replica A remains empty;
- freshness remains UNKNOWN.

This acceptance authorizes only the reviewed broker re-pin in PR #128.

It does not re-grant B-5.
It does not authorize Condition 3.
It does not authorize PR-1B eligibility.
It does not authorize M-B1.
It does not authorize K-ROOT generation.
It does not authorize First Memory.
```

- Acceptance does not re-grant B-5, and does not authorize PR-1B, M-B1,
  First Memory, or activation.
- Step 2 (the re-pin) is a separate reviewed change.
- After step 2 merges, the routine deploy's DR-5 and a **new fresh PR-2
  revalidation** (Condition 3) are required. Then the owner re-decides B-5.

## 7. Recurrence for the immediate PR-1B window

**Exposure.** The broker maps 25 files from 11 packages:
- `libc6` and `libc-bin`;
- `libssl3t64` (`libcrypto.so.3`);
- `libexpat1`, `libsqlite3-0`, `zlib1g`, `libbz2-1.0`, `liblzma5`,
  `libgcc-s1`;
- `libpython3.12-minimal`, `libpython3.12-stdlib`, `python3.12-minimal`.

**At `10:20Z` none of them has a pending upgrade.** The 36 pending upgrades
are all `noble-updates` (apparmor, krb5, kernel, netplan, …). The host's
`50unattended-upgrades` was read on the host: it allows only `${distro_codename}`,
`-security`, and ESM. `-updates` is commented out, and the package blacklist is
empty. So unattended-upgrades does not apply `noble-updates`. No package is on
hold. The next `apt-daily-upgrade` run is **2026-10-03 06:39Z** (randomized
delay), and `apt-daily` (list refresh) is at 17:49Z.

**Recommendation: no package hold yet.**
- A security update to one of those 11 packages can land only on an
  unattended run.
- Plan the window so that these complete before the next run that follows a
  list refresh carrying such an update:
  - the acceptance;
  - the re-pin;
  - its deploy DR-5;
  - the fresh PR-2;
  - eligibility;
  - the owner's M-B1 go.
- Re-check `apt list --upgradable` for the 11 packages at the start of the
  fresh PR-2. If one is pending, either finish before 06:39Z or stop.

**A hold is warranted only if the window must span an unattended run.** It
would be narrowly scoped: `apt-mark hold` on exactly the 11 packages, until
the end of M-B2 (which needs its own fresh PR-2). That is a separate host
mutation, needing explicit owner approval and a fresh PR-2 afterwards. It
is not proposed for execution here.

**Background.** The DR-1 forensics option D records that a blacklist delays
security fixes. A hold has the same cost, so it should stay temporary.

## 8. Evidence

All evidence is on the owner workstation, outside Git, at
`C:\Users\edufo\lilith-b1b3e-broker-recovery\` (87 files). `SHA256SUMS` is
`4df22e74fc616136970707fd039bc72d06811cadf68177343bf0f5b3376ff42d`.
- `pre/`, `post/`, `post2/`: the gates, with raw observations (not committed:
  they carry host details);
- `restart.txt`;
- `tools/`: `lib.sh`, `gate.sh`, `obs_dump.py`, `offline_eval.py`, and the
  `094b914` verifier;
- the recurrence data.

The pre-state seal before the mutation is `6a0cc242…`.

## 9. State

```text
BROKER_PRESERVATION_RECOVERY_READY_FOR_OWNER_REVIEW
BROKER RESTARTED (one mutation, M-BR1); NEW CANDIDATE a30bd7d6… OWNER ACCEPTED (§6, broker runtime scope only)
BROKER PRESERVATION NOT YET RESTORED (needs acceptance + re-pin)
B-5 GRANT REMAINS VOID
CONDITION 3 NOT YET RE-RUN
CONDITION 4 NOT EVALUATED
CONDITION 5 OPEN
M-B1 NOT AUTHORIZED
NO REBOOT
NO PACKAGE HOLD
NO REAL K-ROOT
NO K-WIT
NO REGISTRY V1
NO GENESIS PIN
NO REAL RECORD 1
FRESHNESS=UNKNOWN
FIRST MEMORY NOT AUTHORIZED
```
