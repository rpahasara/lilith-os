# Slice 15B2b-B1b-3e — DEV_SYNTHETIC Fresh Read-Only Rebaseline (2026-10-05)

Status:

- **`DEV_SYNTHETIC_FRESH_READONLY_REBASELINE=ACCEPTED_AS_OBSERVATIONAL_EVIDENCE`**
  (owner review, 2026-10-05). The owner accepted the collected package as
  valid read-only observational evidence **for its recorded collection
  window only**.
- It is **not** accepted as:
  - current Condition 3;
  - a Condition 3 PASS;
  - a B-5 grant;
  - B-5 packet readiness;
  - `CHECK_ELIGIBILITY`;
  - M-B1 authorization;
  - First Memory authorization.
- **READ-ONLY.** Cloud: describe / list / get-iam-policy / logging read.
  GitHub: run list and run-log reads. Host (`lilith-dev-01` only): the
  reviewed read-only tools plus read-only queries. Owner side: a read-only
  Replica A check. **No DEV, cloud, package, runtime or replica mutation.**
  Replica B, the custody device and PROD were not contacted.
- Governed by
  [ADR-0015](../adr/0015-operational-evidence-invalidated-by-material-substrate-drift.md)
  and the
  [Substrate Drift and Evidence Revalidation Policy v0.1](substrate-drift-and-evidence-revalidation-policy-v0.1.md).
  The Condition 3 validity model decided at review time is recorded
  separately in the
  [Condition 3 validity-window owner decision](slice-15b2b-b1b3e-condition3-validity-window-owner-decision.md).

```text
observational evidence accepted != Condition 3 current != B-5 granted != eligible != M-B1 authorized
```

## 1. Identities

| Item | Value |
| --- | --- |
| operation | fresh read-only DEV_SYNTHETIC rebaseline |
| date | 2026-10-05 |
| authorization | owner, read-only observation only |
| control `main` (`CONTROL_SHA`) | `a73fa5e9e9cee68e026981fbee80a9aadd594191` |
| **collection window** | **`2026-10-05T16:12:17Z`–`16:31:27Z`**: cloud `16:12:21Z`–`16:20:54Z`; DR-5 log reads after that; host `16:25:05Z`–`16:28:14Z`; package risk `16:30:08Z`–`16:30:41Z`; Replica A `16:31:28Z` (WSL clock). Timestamps are provenance only; no trusted clock is established |
| reviewed tools | the same git blobs as the [Condition 3 PASS](slice-15b2b-b1b3e-condition3-fresh-pr2-pass.md) window (`fbaad55`): observer blob `7d1e3e89…`, installer blob `c265433e…`, broker verifier file SHA-256 `2e68160971a3b0dd05ffcb6cdc464fc612afb2b522a57fb534b25c6af83c10ba`, needrestart probe blob `6d8e281b…`. Storage probe file SHA-256 `8cdfdedc…`. Installed activation verifier file SHA-256 `44046cae…`, equal to the repository source. `git diff 0fa5e21..a73fa5e` over `scripts`, `services` and `.github` is empty |
| collectors | the PASS window's cloud and host collectors, changing only the output location, the audit-since timestamp (`2026-10-02T12:18:36Z`, the end of the PASS cloud collection) and `CONTROL_SHA`; plus read-only identity, systemd, package-risk and needrestart-config queries |
| pre-flight | every tool was classified READ_ONLY_CONFIRMED from its source before use. The needrestart probe ran only after `dpkg -V needrestart` was clean and the LILITH conf equalled the repository artifact |
| baseline compared | the Condition 3 PASS evidence (`6afa4659…`); for DR-5, the accepted run `36552218231` |
| **raw evidence** | operator-held external evidence bundle (164 files), **not canonical repository content**. `SHA256SUMS` SHA-256 **`e7bc0df5e3a32d6bf63d1dcc51bf3d54157b557b2dae0a47695d2782d46aa429`**. Its location is not published |

## 2. Fresh observations

**No global invalidator G-1 … G-9 was observed.** G-6 was observed for
Replica A only; G-9 (custody device) was not collected.

| # | Item | Observed | vs accepted |
| --- | --- | --- | --- |
| 1 | host identity | `lilith-dev-01`; hostname, FQDN, machine-id and instance description unchanged | equivalent |
| 2 | boot / kernel / OS | boot **`eea461c3-60f0-4b10-8ee9-556dcef19711`** (same boot); kernel `7.0.0-1013-gcp`; Ubuntu 24.04.4 LTS; `REBOOT_REQUIRED=absent` | equivalent |
| 3 | **broker preservation** | **`BROKER_PRESERVATION=PASS`, `failures=[]`**; output byte-identical to the PASS window (`a6a6a79a…`) | equivalent |
| 4 | broker identity | incarnation **`c4b9cb38d7a041dc91db0d8ada7e8d04`**, candidate **`a30bd7d6e26a75e4eba863c08622aebbbaf72928bc9dc7737fc1f7aa6473069d`**, PID `35622`, start ticks `26369693`, **`NRestarts=0`** | no process replacement |
| 5 | mapped files | **25 mapped, 0 deleted**; every on-disk inode equals the mapped inode | equivalent |
| 6 | mapped packages | the same 12 packages at **unchanged versions** (`libssl3t64` `3.0.13-0ubuntu3.16`); **no pending upgrade for any of them**; no hold; package manager idle. No dpkg install / upgrade since `2026-10-02 06:56:37` (`libxpm4`) | equivalent |
| 7 | needrestart | `NEEDRESTART_LILITH_OVERRIDE=PASS`, byte-identical to the accepted post-recovery probe; conf equals the repository artifact; main conf distro-pristine | equivalent |
| 8 | systemd / trusted process | broker unit, socket and tmpfiles bytes equal the repository deploy artifacts; no drop-ins; account, sandbox, `Restart=on-failure`, `IPAddressDeny=any`, `AF_UNIX` only, `NeedDaemonReload=no` | equivalent |
| 9 | activation | **`ACTIVATION=NOT_ACCEPTED reason=GRANT_ABSENT`** (rc 1), byte-identical | equivalent |
| 10 | authority observer | `stableSha256` `c54f21ba09bdc3b3fb0434ec35875fb280d2042716d4e0111b124d8faf386f33`, equal; all 11 sections equal; only the volatile `utcNow` / `uptimeSeconds` differ | equivalent |
| 11 | P1A-9 | `status --expect P1A-9` **PASS**, byte-identical, in the same boot. Observational only; not re-accepted | current in boot `eea461c3…` |
| 12 | **DR-5** | **14 of 14** deploy runs since the PASS window (`cc02819` … `a73fa5e`, §3) have full result set, DR-5 block and pre-deploy block equal to accepted run `36552218231` (`f1869234…`, `a1d98773…`, `f5087042…`); `P1A-9`, `L1c.3`, `GRANT_ABSENT`, no `ALLOWED` | equal |
| 13 | IAM | project, instance and disk policies, the service-account list and all five service-account policies byte-identical. Admin Activity since the PASS: 80 entries, all `iam.serviceAccounts.actAs` | equivalent |
| 14 | rollback domain / topology | instance, the one boot disk, snapshots, instant snapshots, resource policies, machine images, custom images (all `[]`), enabled services (`backupdr` off), buckets (none), project metadata: byte-identical. Whole-life compute Admin Activity byte-identical: **no compute call ever** | equivalent |
| 15 | storage / custody | probe sections equal except the accepted volatile classes in §4 | equivalent |
| 16 | Replica A | records `0`; entries `REPLICA.json records`; manifest `fbdd045c…978b`; inodes `59905 / 59906 / 59907`; mtime `1790643451` | byte-identical |
| 17 | Replica B | **NOT CONTACTED** (last evidence: B-4 run 2, historical) | UNKNOWN |
| 18 | owner `FRESHNESS` | **UNKNOWN** (not observed; not inferable from this evidence) | — |

**No material substrate drift was identified.** The rollback conclusions are
unchanged:

```text
WHOLE-HOST / WHOLE-DISK ROLLBACK CAN PRESENT A SELF-CONSISTENT OLD AUTHORITY WORLD.
WHOLE-HOST ROLLBACK RESISTANCE = NOT ESTABLISHED.
INDEPENDENTLY PERSISTED FRESHNESS STATE = NONE.
```

## 3. DEV deployments since the PASS window

All `DEPLOY_REQUIRED`, success. Each equals the accepted DR-5 sets. The
extraction rule (Condition 2 §2) was first checked to reproduce the
accepted run's three digests exactly.

| Run | SHA | Run | SHA |
| --- | --- | --- | --- |
| `37054183214` | `cc02819` | `37289915900` | `e53fbb2` |
| `37225913804` | `b92fe88` | `37296376712` | `5ed4a4b` |
| `37232542361` | `c3f8d72` | `37300923592` | `16e6554` |
| `37263554917` | `aca5357` | `37306436398` | `7e4ab6b` |
| `37266907412` | `ff393cb` | `37323663339` | `28a4b2d` |
| `37273258573` | `4f29172` | `37331846174` | `e127800` |
| `37277814526` | `a940978` | `37337601444` | `a73fa5e` (latest at collection) |

The 56 deployer `actAs` entries equal 4 × 14 deployments.

## 4. Non-material observations

Listed separately. Each is outside the relevant dependency sets of
policy §3, or in a volatile class the repository already treats as
non-material (policy §4). One is owner-confirmed (§4.1); the rest stay
candidates. None is a universal exemption.

| Observation | Classification |
| --- | --- |
| `google-cloud-cli` snap refresh (loop device `499` → `503`); not broker-mapped | candidate NON_MATERIAL (precedent: `snapd` loop device) |
| timer schedules and runtime volatility (`utcNow`, uptime, user tmpfs) | candidate NON_MATERIAL (accepted volatile) |
| `/etc` mtime from the OS Login cache timer | candidate NON_MATERIAL (precedent: cron parent-directory mtimes) |
| `/var/backups` apt-state rotation | candidate NON_MATERIAL (accepted volatile) |
| 8 owner `actAs` entries at `2026-10-02T19:34:57Z`–`19:36:25Z`: an owner session with no repository record, explained by operator-held output of a read-only package / preservation check | candidate NON_MATERIAL (unrecorded but explained) |
| a new visible cloud project `au4labs-web-rp-2026` (created `2026-10-03T10:09Z`), compute API not enabled; LILITH project IAM unchanged | **OWNER_CONFIRMED_UNRELATED / NON_MATERIAL** (§4.1) |

### 4.1 Owner confirmation: `au4labs-web-rp-2026`

> The owner confirms that `au4labs-web-rp-2026` is an unrelated
> startup / official-website project. It is not part of the LILITH
> DEV_SYNTHETIC operational trust / rollback domain represented by this
> evidence window.

- Disposition: **`OWNER_CONFIRMED_UNRELATED / NON_MATERIAL`**, owner
  follow-up review, 2026-10-05.
- It applies to the **observed 2026-10-05 state only**. It is **not** a
  permanent exemption.
- If future evidence shows a shared or changed dependency with LILITH
  (IAM, service accounts, disks, snapshots / images, backup relationships,
  authority material, trusted runtime dependencies, network / trust-boundary
  dependencies, or any other ADR-0015 evidence dependency), it is evaluated
  normally under
  [ADR-0015](../adr/0015-operational-evidence-invalidated-by-material-substrate-drift.md).
- No live re-check was made for this confirmation.

## 5. Mapped-package risk at collection time

| Item | Value |
| --- | --- |
| pending upgrades | 36, all from `noble-updates`, none for a mapped package; `noble-updates` is outside the unattended origins (`noble`, `noble-security`, ESM) |
| package lists | `noble-security` `2026-10-05T10:34:39`; `noble-updates` `2026-10-04T11:14:57` |
| next list refresh | `apt-daily` at `2026-10-06T01:45:07Z` |
| next unattended install opportunity | `apt-daily-upgrade` at `2026-10-06T06:48:30Z` |

These are observed facts of this window, not a validity bound for any gate.

## 6. What this evidence does not establish

**Condition 3 current satisfaction = NOT ESTABLISHED.** Reasons at
collection and review time:

- this was a rebaseline, not the final Condition 3 window collected
  immediately before `CHECK_ELIGIBILITY`;
- B-5 remains WITHHELD;
- `CHECK_ELIGIBILITY` was not authorized;
- no owner Condition 3 acceptance was made;
- B-5 packet prerequisites remain incomplete (§7).

A future final Condition 3 window is governed by the event- and
sequence-bounded model in the
[owner decision](slice-15b2b-b1b3e-condition3-validity-window-owner-decision.md).
This evidence cannot be carried into that window as current.

## 7. B-5 packet status

```text
B5_EVIDENCE_PACKET_READINESS = NOT_READY
```

Blockers:

- repository merge / acceptance of this record, as applicable;
- Replica B / `ownerRegisterKnownEmpty` needs separately authorized fresh
  read-only evidence;
- the custody device (G-9) needs separately authorized fresh read-only
  evidence;
- Condition 1 needs a fresh check;
- OR-1 … OR-9 need fresh owner review.

The `au4labs-web-rp-2026` owner-confirmation blocker is closed (§4.1).

> **Later current state (2026-10-05, pointer only; the status above is
> preserved as written).** The remaining blockers were addressed by the
> [B-5 packet refresh and owner risk review](slice-15b2b-b1b3e-b5-packet-refresh-owner-risk-review.md):
> `TECHNICAL_PACKET_COMPONENTS_COMPLETE = YES` and
> `B5_PACKET_READY_FOR_SEPARATE_OWNER_DECISION`. B-5 remains WITHHELD.

## 8. Incidental notes

- Contact effects inherent to authorized read-only access: 14 OS Login / IAP
  SSH sessions (each with `actAs` audit entries, session logs and a user
  tmpfs) and sudo log lines.
- A first Replica A command lost its variables to shell quoting. It ran only
  failed read-only `ls` / `stat` / `sha256sum` on nonexistent paths, and
  was re-run correctly. A transient GitHub 502 on one log read was retried.
- Not run: the verifier's `rebaseline` operation, non-repository recovery
  tools, `dpkg --audit`, anything that refreshes package lists, and any
  eligibility evaluation.

## 9. State

```text
DEV_SYNTHETIC_FRESH_READONLY_REBASELINE=ACCEPTED_AS_OBSERVATIONAL_EVIDENCE (window 2026-10-05T16:12:17Z–16:31:27Z only)
NO GLOBAL INVALIDATOR G-1..G-9 OBSERVED
NO MATERIAL SUBSTRATE DRIFT IDENTIFIED
AU4LABS-WEB-RP-2026 = OWNER_CONFIRMED_UNRELATED / NON_MATERIAL (OBSERVED 2026-10-05 STATE ONLY)
B-5 = WITHHELD
FRESHNESS=UNKNOWN
CONDITION 3 = NOT CURRENTLY ESTABLISHED
CHECK_ELIGIBILITY = NOT RUN / NOT AUTHORIZED
M-B1 NOT AUTHORIZED
FIRST MEMORY NOT AUTHORIZED
B5_EVIDENCE_PACKET_READINESS = NOT_READY
REPLICA B NOT CONTACTED
NO DEV, CLOUD, PACKAGE, RUNTIME OR REPLICA MUTATION
NO RESTART, REBOOT OR RE-PIN
NO REAL K-ROOT / K-WIT / REGISTRY V1 / GENESIS PIN / RECORD 1
```
