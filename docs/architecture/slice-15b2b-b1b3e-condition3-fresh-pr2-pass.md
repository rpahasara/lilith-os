# Slice 15B2b-B1b-3e — M-B1 Condition 3: Fresh PR-2 Revalidation (re-run, PASS)

Status:

- **`CONDITION_3_FRESH_PR2=PASS`.** This is a **new** read-only PR-2
  observation window. It does not reuse the
  [failed Condition 3 window](slice-15b2b-b1b3e-condition3-fresh-pr2-stop.md).
- The difference from that STOP is broker preservation, now restored: the
  owner accepted
  [the recovery](slice-15b2b-b1b3e-broker-restart-recovery.md) §6, and the
  [re-pin](slice-15b2b-b1b3e-broker-restart-repin.md) merged. Everything
  else is equal to the accepted
  [pre-B-5 revalidation](slice-15b2b-b1b3e-pr2-pre-b5-revalidation.md),
  apart from the reviewed broker restart.
- **READ-ONLY.** Cloud: describe / list / get-iam-policy / logging read.
  Host (`lilith-dev-01` only): the reviewed read-only tools at `main`
  `fbaad55`. **No DEV or cloud mutation**, no `apt update`, no hold, and no
  PROD contact. Replica B was not contacted.
- **Condition 3 is OPEN until owner review.** On merge it is CLOSED.
  **Condition 4 is NOT EVALUATED. B-5 GRANT REMAINS VOID. M-B1 NOT
  AUTHORIZED.**

```text
fresh PR-2 PASS != B-5 re-granted != eligible != M-B1 authorized
```

## 1. Identities

| Item | Value |
| --- | --- |
| control `main` (`CONTROL_SHA`) | `fbaad554fd53fb3c31ca75159f53fdf24c333ca3` (unchanged through the window) |
| reviewed tools | observer `7d1e3e89…`, installer `c265433e…` (the same git blobs as every accepted window). Broker verifier: the merged re-pin, file SHA-256 `2e68160971a3b0dd05ffcb6cdc464fc612afb2b522a57fb534b25c6af83c10ba`. Storage probe `8cdfdedc…` |
| collectors | the accepted ones, with the service-account CRLF defect fixed (`tr -d '\015'`; all five policies were read on the first pass). Audit window from `2026-09-29T18:57:17Z`, the end of the last accepted window |
| **window** | **`2026-10-02T12:08:38Z`–`12:24:19Z`**: cloud `12:08:38Z`–`12:18:36Z`; host `12:19:29Z`–`12:21:23Z`; package risk, then Replica A |
| evidence | owner workstation `C:\Users\edufo\lilith-b1b3e-c3-rerun\` (73 files), `SHA256SUMS` `6afa46597ffeb5c9faf4c5e13552a3c50730ce219d8d63c85a04194bf5ad6d0c` |
| baseline compared | the pre-B-5 evidence `C:\Users\edufo\lilith-b1b3e-pr2-preb5\` (`67eb9a16…`); for the broker, the accepted recovery evidence (`4df22e74…`, post-merge `6b1b1d2e…`) |

## 2. Cloud and rollback domain

**Byte-identical** to the accepted pre-B-5 window (23 artifacts):

- the instance, and the instance list: `lilith-dev-01`, `asia-southeast1-b`,
  `RUNNING`;
- the disks: exactly one zonal `pd-balanced` 20 GB boot disk, attached only
  to `lilith-dev-01`;
- snapshots, instant snapshots, resource policies / snapshot schedules,
  machine images, and custom images: **all `[]`**;
- the enabled services: **`backupdr` not enabled**;
- buckets: **none**;
- project metadata keys, the projects list, and other-project artifacts;
- IAM: the project, instance and disk policies, the service-account list,
  and **all five service-account policies**.

**Admin Activity since the last accepted window: 142 entries, all
`iam.serviceAccounts.actAs` on `lilith-dev-vm`.**
- 36 are `github-lilith-dev-deployer`: 4 for each of the 9 routine deploys
  `11c47dc` … `fbaad55`.
- 106 are the owner's OS Login / IAP sessions, 2 per SSH session. They cover
  the tail of the pre-B-5 collection, the STOP window, the recovery gates
  (including M-BR1 at `10:15:56Z`), and the post-merge check.

**No compute call.** The whole-life compute Admin Activity set is
byte-identical (20 entries). No snapshot, image, clone, attach / detach, or
stop / start / reset has ever been made.

**Rollback conclusions (re-established):**

```text
WHOLE-HOST / WHOLE-DISK ROLLBACK CAN PRESENT A SELF-CONSISTENT OLD AUTHORITY WORLD.
WHOLE-HOST ROLLBACK RESISTANCE = NOT ESTABLISHED.
INDEPENDENTLY PERSISTED FRESHNESS STATE = NONE.
```

## 3. Host, broker, authority

| # | Item | Observed |
| --- | --- | --- |
| 1 | boot | `eea461c3-60f0-4b10-8ee9-556dcef19711` (same boot). Kernel `7.0.0-1013-gcp` |
| 2 | disk / filesystem layout | every storage-probe section is identical to pre-B-5, except `lsblk`, whose only difference is the `snapd` loop device (snap refresh 2.76.3 → 2.77.1). All custody paths remain on ext4 `sda1` |
| 3 | TPM / vTPM | identical: devices present, no TSS library, nothing bound |
| 4 | **broker preservation** | **`BROKER_PRESERVATION=PASS`, `failures=[]`**. `acceptedIdentityMatches=true`, `baselineCandidateMatchesAccepted=true`. The output is byte-identical to the post-merge check (`a6a6a79a…`) |
| 5 | broker identity | incarnation **`c4b9cb38d7a041dc91db0d8ada7e8d04`**, candidate **`a30bd7d6e26a75e4eba863c08622aebbbaf72928bc9dc7737fc1f7aa6473069d`**, PID `35622`, start ticks `26369693`, `NRestarts=0` |
| 6 | deleted mappings | **0** of 25 mapped files |
| 7 | P1A-9 | **`status --expect P1A-9` PASS**, byte-identical to pre-B-5 |
| 8 | authority observer | `stableSha256` `c54f21ba09bdc3b3fb0434ec35875fb280d2042716d4e0111b124d8faf386f33`. Against pre-B-5, **only the `units` section differs**, and only in the broker's MainPID, InvocationID and start timestamps (the reviewed restart). Unchanged: accounts, currentBlob, filesystems, host, hostFiles, hostKey, listings, namespaceInventory, pr1Objects, releases |
| 9 | activation | **`ACTIVATION=NOT_ACCEPTED reason=GRANT_ABSENT`** (rc 1), byte-identical |
| 10 | units | authority-dev service and socket, recovery-witness service and both sockets, and the Stage III controller: all `inactive/dead`, `static`, no InvocationID, `NRestarts=0`. Only `lilith-os-api-dev` is enabled |
| 11 | unexpected authority material | none: the observer and status are unchanged |
| 12 | latest DR-5 | run `36998230353` (`fbaad55`, the latest deploy). The 186-line boundary result set and the 147-line DR-5 block equal the accepted run `36552218231`: `P1A-9`, `L1c.3`, `GRANT_ABSENT`, no `ALLOWED(unexpected)` |
| — | packages | no package change since `2026-10-02 06:56:37` (`libxpm4`). The last broker-relevant change is the `libssl3t64` upgrade of 10-01, resolved by the restart. `REBOOT_REQUIRED=absent` |

## 4. Package-update risk (read-only; no `apt update`, no hold)

| Item | Value |
| --- | --- |
| **mapped package set** | `libbz2-1.0`, `libc-bin`, `libc6`, `libexpat1`, `libgcc-s1`, `liblzma5`, `libpython3.12-minimal`, `libpython3.12-stdlib`, `libsqlite3-0`, `libssl3t64`, `python3.12-minimal`, `zlib1g` (12) |
| **pending upgrade for any of them** | **none**. 36 upgrades are pending, all for other packages |
| package lists refreshed since the post-merge check (`11:05Z`)? | **no**. `apt-daily` last ran at `03:22Z`. The list files are unchanged: `noble-security` `2026-10-01T17:54:14`, `noble-updates` `2026-10-02T02:01:52` |
| next automatic refresh | `apt-daily` at **`2026-10-02T17:49:59Z`** |
| next unattended upgrade | `apt-daily-upgrade` at **`2026-10-03T06:39:01Z`** (origins: release, `-security`, ESM only) |
| holds | none. Package manager idle |

The no-pending result holds only as of the host's last list refresh. A
security update published after `2026-10-01T17:54Z` would appear only after
`17:49:59Z` today. Before that it cannot install, because the next unattended
run is `2026-10-03T06:39Z`. **This PASS is valid for eligibility and the M-B1
window only if that window completes before `2026-10-03T06:39Z`.** If it
cannot, re-check the 12 packages after the `17:49Z` refresh, and stop if any
is pending.

## 5. Replica A (read-only)

**Byte-identical** to the accepted pre-B-5 observation:
- records `0`;
- entries `REPLICA.json records`;
- the parent holds only the replica;
- manifest `fbdd045c390506f8174192dbea6a6444e6f3e819c9a24e90c61155ec9238978b`;
- inodes `59905 / 59906 / 59907`, mtime `1790643451`.

Freshness remains `FRESHNESS_UNKNOWN`. Replica B was not contacted (last
evidence: B-4 run 2, 0 records).

## 6. Result

```text
CONDITION_3_FRESH_PR2=PASS
PR-2 materially equivalent to the accepted boundary (only the reviewed broker restart differs)
WHOLE-HOST / WHOLE-DISK ROLLBACK RESISTANCE: NOT ESTABLISHED
```

This result covers this window only (P3-5 §13).
- It is the input to Condition 4 (`CHECK_ELIGIBILITY`) only if no topology
  change happens before that check. A routine deployment whose DR-5 equals
  the accepted result set is not one.
- It is also valid only if the eligibility-to-M-B1 window ends before the
  next unattended run (§4).
- Otherwise `PR2_REVALIDATION_REQUIRED`. `GENERATE_K_WIT` (M-B2) needs its
  own fresh PR-2.

## 7. Validation

- `test_b1b3e_condition3_fresh_pr2_pass.py` (5) pins the window, the broker
  identity, the rollback conclusions, and the non-claims.
- In WSL: the owner-memory-control suite gives 741 OK (4 git-dependent
  skips), and the broker verifier tests give 59 OK.
- `scripts/validate_repository.py` passes, and `git diff --check` is clean.

## 8. State

```text
CONDITION_3_FRESH_PR2=PASS
CONDITION 1 CLOSED
CONDITION 2 CLOSED
CONDITION 3 OPEN UNTIL OWNER REVIEW
CONDITION 4 NOT EVALUATED
CONDITION 5 OPEN
B-5 GRANT REMAINS VOID
M-B1 NOT AUTHORIZED
NO M-B1 COMMAND ISSUED
NO DEV OR CLOUD MUTATION BY THIS REVALIDATION
NO REAL K-ROOT
NO K-WIT
NO REGISTRY V1
NO GENESIS PIN
NO REAL RECORD 1
NO REPLICA A / B CHANGE
FRESHNESS=UNKNOWN
FIRST MEMORY NOT AUTHORIZED
```
