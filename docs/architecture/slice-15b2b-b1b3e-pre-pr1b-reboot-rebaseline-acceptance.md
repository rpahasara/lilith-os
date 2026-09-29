# Slice 15B2b-B1b-3e — Pre-PR-1B Reboot: Evidence and Broker Rebaseline Acceptance

Status:

- **M-R1 (reboot) DONE**: `POST_MR1_REBOOT_STATE_PASS`
- **M-R2 (one broker start) DONE**: `M_R2_BROKER_REBASELINE_PASS`
- **NEW BROKER CONTINUITY BASELINE ACCEPTED** by the owner, broker runtime scope only (§5)
- **§10 DR-5 PENDING**: the merge of this record is its trigger (§6)
- **PR-1B NOT AUTHORIZED**; **FIRST MEMORY NOT AUTHORIZED**
- `LIVE_MUTATION` (this record) = NONE

```text
healthy broker service != accepted broker baseline
accepted broker baseline != authority readiness != PR-1B eligibility
```

This record carries the live evidence of the
[pre-PR-1B reboot and rebaseline ceremony](slice-15b2b-b1b3e-pre-pr1b-reboot-rebaseline.md)
and the owner's acceptance of the new broker baseline. It edits no earlier
record. It supersedes, for broker continuity only, the 2026-09-26 acceptance
of incarnation `42af2691…` in the
[current runtime baseline record](slice15b2b-b1b3d-current-runtime-baseline.md) §3.
That record's rule applies: any process replacement ends an acceptance, and
a new one needs a new record.

## 1. Identities

| Identity | Value |
| --- | --- |
| `CONTROL_SHA` | `afe5286b12f85703f0ac2c2e3c9ecb3307fa3544` (merge of PR #105, correction C-1) |
| tools (SHA-256) | observer `a2f21b45…08bf`; installer `fe10d9a3…5487`; broker verifier `72d0a99d…8a43`; needrestart probe `edd23ac7…b2db`; comparator `6a20c02e…e6f4` |
| host | `lilith-dev-01`, instance `7687007163730582258`, machine-id `ae929170e6fa4c8ab9cc7b9547238d9d` |
| `OLD_BOOT` | `24d1771d-e1b5-4e5f-816d-da08ad8b367a` |
| `NEW_BOOT` | `eea461c3-60f0-4b10-8ee9-556dcef19711` |
| kernel | `6.17.0-1022-gcp` → `7.0.0-1013-gcp` (= `EXPECTED_KERNEL`) |
| operator | owner OS Login session over IAP; tools embedded gzip+base64 in `--command` |
| evidence | owner workstation `C:\Users\edufo\lilith-b1b3e-pre-pr1b-reboot\`: `pre3/` `SHA256SUMS` `13d242f6…`, `post/` `1c7b1798…`, `mr2/` `55b34009…` |

## 2. Pre-reboot gate (G0–G16): `PRE_REBOOT_GATE_PASS`

The passing gate ran 2026-09-29 `08:44:28Z`–`08:46:59Z` at `CONTROL_SHA`.

- **G2 DR-5:** run `36543920477` (`afe5286`, `DEPLOY_REQUIRED`,
  `08:37:42Z`–`08:43:20Z`):
  - `SUDO_EFFECTIVE_PROOF=PASS user=sa_112096412008414111981 mode=self`;
  - `PR1_AUTHORITY_BOUNDARY maturity=P1A-9`;
  - `AUTHORITY_BOUNDARY_PROOF=PASS maturity=L1c.3`.
- **G5:** observer `5eaec23cef9c8f53db8e6f27e84b270ad6b8567d4f21287a1ffd543550fe2778`
  twice, equal to the accepted value.
- **G6–G9:** `status --expect P1A-9` PASS; broker preservation PASS (§3 of
  the baseline record, candidate `35495854…`); activation `GRANT_ABSENT`;
  needrestart probe PASS.
- **G10:** `EXPECTED_KERNEL=7.0.0-1013-gcp`. It is the newest installed
  kernel; GRUB default is 0, there is no saved entry, and the first entry
  boots it. The fallback is `6.17.0-1022-gcp`.
- **G11:** idle. No apt timer was due inside the window.
- **G12–G15:** matched the reviewed ceremony.

**Gate history (findings).**

| # | Finding | Handling |
| --- | --- | --- |
| RB-2 | The first gate (`05:17Z`) found `apt-daily-upgrade` due in 43 minutes (G11). The run at `06:04Z` installed `linux-image-7.0.0-1013-gcp` and **autoremoved `7.0.0-1011-gcp`**, the kernel that gate had expected. It also upgraded `libevent-core`, `python3-requests`, `python3-jwt`, and `dracut-install` | The gate was repeated in full. `EXPECTED_KERNEL` was re-derived. Broker libraries, observer digest, and custody were unchanged |
| RB-3 | The routine deploy lock `/run/lilith-dev-deploy.lock` would make the §10 raw-digest check fail with no real drift | Correction C-1 (PR #105): the structural `routine-deploy` comparison |
| RB-4 | The ceremony §9 Q2 command runs `journalctl` without `sudo -n`, so it returns "insufficient permissions" | The same read-only queries were re-run with `sudo -n`. A record fix is carried as a documentation item |

## 3. M-R1 and post-reboot state: `POST_MR1_REBOOT_STATE_PASS`

- **M-R1:** issued once by the owner with the reviewed guarded command.
  Previous boot: orderly `systemd-reboot`, journal stopped at `09:00:49Z`.
  New boot at `09:01:01Z`. The first poll (`09:02:22Z`) saw `RUNNING` and the
  new boot ID, within the 15-minute bound.
- **Q1:** identity unchanged; kernel `7.0.0-1013-gcp`.
- **Q2 (with `sudo -n`, RB-4):** no LILITH error. The only errors are a
  `piix4_smbus` BIOS notice and OS Login `pam_group` messages.
  `systemctl --failed` is empty.
- **§11:** `reboot-required` absent; `libc6` `2.39-0ubuntu8.9` unchanged;
  no process maps a deleted `libc.so.6`.
- **Q3:** post observer
  `5c8037477e73f60cbfecbd4bef004b8623a7dab5ab1a9fef89e87d038215533f`. The
  comparator (pre = gate observation, accepted digest checked) returned
  `REBOOT_OBSERVATION_COMPARISON=PASS unexpected=0`. These sections are
  unchanged: accounts, currentBlob, filesystems, hostFiles, hostKey,
  listings, releases. The expected deltas were:
  - boot ID and kernel;
  - `reboot-required` cleared;
  - broker lifetime;
  - both OR-6 directories created;
  - `lilith-dev-deploy.lock` not recreated.
- **OR-6 (§7): `OR6_EXPECTED_TMPFILES_EFFECT`.**
  - `/run/lilith-authority-dev` is `root:root 0700`.
  - `/run/lilith-recovery-witness` is `root:lilith-authority-dev(985) 0710`.
  - Both were created at `09:01` by `systemd-tmpfiles-setup` (no error),
    from unchanged definitions (`2a1891ef…`, `c3491d51…`).
  - Both are empty. `/run/credentials` is empty.
  - `P1A-9` still PASSes. **OR-6 is closed.**
- **Q5–Q7:** `P1A-9` PASS. Activation `GRANT_ABSENT`. The five authority
  and witness units are inactive, `static`, and have no InvocationID. The
  Stage III controller shows exactly `CONTROLLER_POST_REBOOT_EXPECTED`.
- **RB-1 confirmed live:** the broker came back **down**. The service was
  `inactive/dead`, the socket `inactive`/`disabled`, there was no uid-999
  process, and no `owner.sock` listener.
- **Q9:** the only service difference is the broker. The Core API's
  recurring `no such table: career_events` log line is pre-existing
  (11 280 occurrences in the previous boot, since 2026-09-13) and unrelated.

**OR-5 is closed.** The running kernel is the newest installed kernel,
`reboot-required` is gone, and no process maps stale libc.

## 4. M-R2 and fresh broker rebaseline: `M_R2_BROKER_REBASELINE_PASS`

**Pre-M-R2 guard (`09:11:26Z`).** All required values held:

- boot and kernel as pinned;
- observer `5c803747…`, the same as post-M-R1;
- `P1A-9` PASS;
- `GRANT_ABSENT`;
- broker down, 0 listeners;
- units inert;
- no apt or dpkg activity.

**M-R2.** Issued once, `09:12:30Z`, rc 0:

```bash
dev "test \"\$(cat /proc/sys/kernel/random/boot_id)\" = eea461c3-60f0-4b10-8ee9-556dcef19711 || exit 96; sudo -n /usr/bin/systemctl start lilith-memory-broker.service"
```

- The journal shows only the socket starting (`Requires=`) and the service
  starting, both at `09:12:38Z`.
- There was no enable, no restart, and no `daemon-reload`.
- The service stays `static` and the socket stays `disabled`.

**Rebaseline (`rebaseline`, verifier `72d0a99d…`).**

| Run | Time | Result | Candidate |
| --- | --- | --- | --- |
| 1 | `09:13:02Z` | `BROKER_REBASELINE=PASS`, `failures=[]` | `5000374513f38144c90bd75aefdabb4d000f644e024107bf275da9f80af7dbe2` |
| 2 | `09:18:12Z` (≥ 5 min later) | `BROKER_REBASELINE=PASS`, `failures=[]` | identical digest; full candidate identical |

The digest was recomputed locally from `baselineCandidate`.

**After M-R2.**

- The observer returned
  `45fb0555cdeaab3e13d1127ce429b79b445a30b18f1a161fa0735bccb4a1a9ac`. This
  is `mr2/obs.txt`, the §10 D-4 baseline.
- Comparison with the pre-reboot observation: PASS, `unexpected=0`.
- `P1A-9` PASS. `GRANT_ABSENT`. The authority, witness, and Stage III units
  are unchanged and inert.

## 5. Owner acceptance

The owner's statement (2026-09-29), recorded verbatim:

> I explicitly accept broker rebaseline candidate
> 5000374513f38144c90bd75aefdabb4d000f644e024107bf275da9f80af7dbe2
> for LILITH DEV on boot
> eea461c3-60f0-4b10-8ee9-556dcef19711
> as the new accepted broker continuity baseline.
>
> This acceptance applies only to the broker runtime baseline.

**Accepted baseline.**

| Field | Value |
| --- | --- |
| `baselineCandidateSha256` | `5000374513f38144c90bd75aefdabb4d000f644e024107bf275da9f80af7dbe2` |
| boot ID | `eea461c3-60f0-4b10-8ee9-556dcef19711` |
| InvocationID (incarnation) | `84798e5b74494e1ea362ce90f1cf04ad` |
| PID / start ticks / start time | `2586` (ppid 1) / `69918` / `2026-09-29T09:12:38Z` |
| `NRestarts` | `0` |
| release / manifest | `817a83e44cec8965479fd97fc30b7a0b3ae49ab2` / `7a46ac83001411a29b1bc4be7e0f91f09c5879967386c452b2620e23d16e4614` |
| shared-library set | `40e68a1c27328c27b811da19bb17a1262cbacff18dcd7ab397e06bebb17a87bd` (25 mappings, none deleted; the same `libc6`/`libexpat` bytes as the old baseline) |
| equivalence facts | release, config, state, identity boundary, socket boundary, Stage III untouched, deployer policy text, incarnation healthy: all `true` |
| superseded | `42af2691b8d24ee5a92a286197c5444c` / boot `24d1771d…` / candidate `35495854…` (ended by M-R1) |

**Scope.** Broker runtime continuity only. The owner stated explicitly that
the acceptance does **not** authorize any of:

- PR-1B;
- K-ROOT;
- K-WIT;
- registry;
- ledger;
- witness state;
- INITIAL_CUSTODY;
- real owner freshness record 1;
- First Memory.

Any process replacement ends this acceptance: a restart, needrestart,
`Restart=on-failure`, a reboot, or a fault reset. A new acceptance then
needs a new record.

**Verifier pins.** `preservation` in the merged verifier still pins
`42af2691…`, so it now fails by design. Until a separate reviewed source
change re-pins these to §5:

- `ACCEPTED_CURRENT_INCARNATION`;
- `ACCEPTED_CURRENT_BASELINE_SHA256`;
- `ACCEPTED_CURRENT_BOOT_ID`;

every broker gate uses `rebaseline` and requires exactly the accepted
digest and incarnation. This record does not change them.

## 6. Remaining steps (none authorized by this record)

1. **§10 DR-5.** The merge of this record is `DEPLOY_REQUIRED`, which gives
   the post-reboot routine DR-5 run. It must start after `NEW_BOOT`'s boot
   time and show:
   - `PR1_AUTHORITY_BOUNDARY maturity=P1A-9` and
     `AUTHORITY_BOUNDARY_PROOF=PASS maturity=L1c.3`;
   - the new `DENIED: test -w/-r/-x` lines on `/run/lilith-authority-dev`
     and `/run/lilith-recovery-witness`.

   Then D-1..D-4 (read-only):
   - `rebaseline` = `50003745…` with incarnation `84798e5b…`;
   - `P1A-9` PASS;
   - `GRANT_ABSENT`;
   - `routine-deploy` comparison of `mr2/obs.txt` against the post-DR-5
     observation plus the lock `stat` line.

   A FAIL is a STOP. Do not rerun.
2. **Verifier re-pin** to §5 (reviewed source change).
3. **PR-2 read-only revalidation**
   ([P3-5 §13](slice-15b2b-b1b3e-pr3-pr1b-bootstrap-sequencing.md)).
4. **Documentation item (RB-4):** add `sudo -n` to the ceremony's Q2
   `journalctl` commands.

## 7. Nonclaims

This record does not claim:

- behavioural equivalence of the new kernel, the new process, or the broker
  runtime. Observation proves artifact equivalence only;
- the §10 DR-5 result, which is pending;
- that whole-host rollback resistance is established (OR-1 stays open);
- that DR-3 is closed;
- any change to real owner freshness. Neither owner replica was contacted.
  Both remain empty, freshness records = 0.

Carried open: OR-1..OR-4, OR-7..OR-9, DR-3.

## Explicitly not done

```text
NO SECOND REBOOT
NO BROKER RESTART
NO SERVICE ENABLEMENT
NO AUTHORITY START
NO WITNESS START
NO VERIFIER PIN CHANGE
NO OWNER REPLICA CONTACT
NO K-ROOT
NO K-WIT
NO REGISTRY
NO LEDGER
NO WITNESS STATE
NO HOLD
NO RECOVERY EPOCH
NO INITIAL_CUSTODY
NO REAL RECORD 1
REAL FRESHNESS REMAINS UNKNOWN
PR-1B NOT AUTHORIZED
FIRST MEMORY NOT AUTHORIZED
```
