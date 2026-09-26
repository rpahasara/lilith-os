# DR-1 — DEV Memory Broker Restart Forensics

Status:

- **FORENSIC EVIDENCE RECORD**
- **NOT AN ACCEPTANCE RECORD**
- **NO LIVE CHANGE**
- **B1b-3d LIVE ENTRY STILL BLOCKED** (see [§11](#11-b1b-3d-live-entry-gates))

Base: protected main `a7d2b957a2a3197a49909a627ffefe118d82b538`.
Investigation: 2026-09-26, 14:03–14:12 UTC, owner break-glass session, read-only.

This record resolves the cause of drift **DR-1** in the
[B1b-3d DEV_SYNTHETIC custody design](slice-15b2b-b1b3d-dev-synthetic-custody-design.md#3-live-and-docs-drift).
It does **not** rewrite the
[accepted Stage II lifecycle](slice15b2b-accepted-stage2-lifecycle.md) or the
[trusted snapshot acceptance contract](slice15b2b-trusted-snapshot-install-acceptance-contract.md).
Those remain the historical acceptance of the Stage II process instance and
artifacts.

Labels:

- **OBSERVED** — read live on `lilith-dev-01` during this investigation.
- **RUN** — a GitHub Actions record.
- **CANONICAL** — defined by an accepted repository record.
- **INFERRED** — a conclusion drawn from the observations; the reasoning is given.

## 1. Classification

```text
DR1-EXPLAINED_UNRECORDED
  STATE_EQUIVALENT
  PROCESS_ONLY_CHANGE
  EVIDENCE_INCOMPLETE
```

- **Cause (OBSERVED):** Ubuntu `unattended-upgrades` installed a `libexpat1`
  security update. `needrestart` then ran
  `systemctl restart lilith-memory-broker.service lilith-os-api-dev.service polkit.service`.
- **Unrecorded:** no repository record captured it, and no project control
  anticipated OS maintenance restarting an authority-sensitive service.
- **State-equivalent:** every accepted Stage II file, config, and state hash
  still matches (§6).
- **Process-only:** the process instance changed; nothing observed shows an
  authority or state mutation.
- **Evidence incomplete:** hashes match *today*. Nothing observed continuously
  between 2026-09-24 and 2026-09-26, so a temporary change that was later
  reverted cannot be excluded (§9).

## 2. Broker incarnation timeline

All times UTC. Boot `24d1771d-e1b5-4e5f-816d-da08ad8b367a` (2026-09-13 17:58)
covers the whole period; there was no reboot.

| Time | Event | Invocation / PID | Initiator | Label |
| --- | --- | --- | --- | --- |
| 09-24 06:51:22 | Accepted Stage II broker starts (run 35965971283) | `5c1eb955e2dc44e78139c416f0c9469a` / 96650, start ticks 91036598 | Stage II control | CANONICAL |
| 09-25 14:06:15 | Stage III A2 controller stops the broker, then the socket; the controller fails at 14:06:16 (run 36145190507, [N-25](../research/negative-results-register.md)) | end of `5c1eb955` | Stage III controller | OBSERVED (journal) |
| 09-25 14:54:06 | Owner runs `sudo systemctl start lilith-memory-broker.service` (tty session). systemd job 575603 starts the service; the socket (job 575606) is pulled in by `Requires=` | `42a0608f29a54fba8c52614396cb9f74` / not recorded; socket `1434eda774ed4d8296bc4e266191bc67` | owner `ravindupahasara2_gmail_com` | OBSERVED (sudo + journal) |
| 09-26 06:33:47 | `apt-daily-upgrade.service` starts `unattended-upgrade` | — | systemd timer | OBSERVED |
| 09-26 06:33:55–59 | Upgrade: `curl`, `libcurl4t64`, `libcurl3t64-gnutls` 8.5.0-2ubuntu10.13 → 10.15; needrestart restarts nothing LILITH | — | unattended-upgrades | OBSERVED (dpkg, apt history) |
| 09-26 06:34:06–08 | Upgrade: `libexpat1`, `libexpat1-dev` 2.6.1-2ubuntu0.5 → 0.6 | — | unattended-upgrades | OBSERVED (dpkg, apt history) |
| 09-26 06:34:09.346 | systemd job 605255 (`JOB_TYPE=restart`) stops the broker, which deactivates cleanly; `lilith-os-api-dev` and `polkit` restart in the same 30 ms | end of `42a0608f` | needrestart (root) | OBSERVED |
| 09-26 06:34:09.377 | The broker starts again under the same job | `42af2691b8d24ee5a92a286197c5444c` / 132976 | needrestart (root) | OBSERVED |
| 09-26 06:34:13 | `apt-daily-upgrade.service` finishes | — | — | OBSERVED |

The socket was **not** cycled at 06:34. It has been continuously active since
09-25 14:54:06.

### needrestart evidence

`/var/log/unattended-upgrades/unattended-upgrades-dpkg.log`, block
`Log started: 2026-09-26 06:34:06`:

```text
Setting up libexpat1:amd64 (2.6.1-2ubuntu0.6) ...
Restarting services...
 systemctl restart lilith-memory-broker.service lilith-os-api-dev.service polkit.service
Service restarts being deferred:
 systemctl restart apt-daily-upgrade.service
 ...
```

- `needrestart` 3.6-7ubuntu4.5 is installed.
- `$nrconf{restart}` is left at its commented default. Under unattended
  upgrades that default restarts services automatically.
- No `override_rc` / `blacklist_rc` entry names a LILITH service.
- `APT::Periodic::Unattended-Upgrade "1"`.
- The python interpreter (`/usr/bin/python3.12`) was not upgraded. The trigger
  was the libexpat shared object mapped by the broker process (INFERRED; the
  replacement process now maps `/usr/lib/x86_64-linux-gnu/libexpat.so.1.9.1`
  from the patched package).
- Earlier needrestart runs (09-22, 09-23, 09-24) never named the broker.

## 3. What was ruled out

| Candidate | Result | Evidence |
| --- | --- | --- |
| VM reboot / OS reboot / kernel restart | **excluded** | one boot ID since 09-13; `last` shows no reboot |
| GCE reset, stop, or maintenance | **no evidence** | `gcloud compute operations list` for `lilith-dev-01` since 09-25 returned none |
| `Restart=on-failure` policy | **excluded** | `NRestarts=0`; the old process deactivated successfully; the job type is `restart`, not an auto-restart |
| Socket activation | **excluded** | the socket was not cycled; the service start belongs to job 605255 |
| OOM, watchdog, crash, signal | **excluded** | no such journal entries; `WatchdogUSec=0`; clean deactivation |
| Owner session | **no evidence** | no `sshd`, `sudo`, or `systemd-logind` entries 06:00–07:00 |
| B1c routine deployer | **no evidence** | first session 07:55:16 (`lilith-dev-deploy deploy 99edaaa…`); its sudoers allows only the fixed helper |
| `ubuntu` account | **no evidence** | no session; `authorized_keys` empty; password locked |
| GitHub Actions | **no evidence** | no run of any workflow between 09-25 20:58 and 09-26 07:51 (RUN list); no scheduled workflow exists |
| Deployment | **excluded** | the selector link mtime is still 2026-09-23 15:28; no deploy in the window |

Temporal overlap was not taken as causation. The attribution rests on the
dpkg log line naming the broker together with the matching systemd restart
job.

## 4. Current incarnation (OBSERVED 2026-09-26 ~14:06 UTC)

| Fact | Value |
| --- | --- |
| Host | `lilith-dev-01`, boot `24d1771d-e1b5-4e5f-816d-da08ad8b367a` |
| Service | active/running since `Sat 2026-09-26 06:34:09 UTC`; `static`; no drop-ins; `Restart=on-failure`, `RestartUSec=5s`, `NRestarts=0` |
| InvocationID / PID | `42af2691b8d24ee5a92a286197c5444c` / 132976, ppid 1 |
| Process identity | UID/GID 999/987 (all four), groups [987], `NoNewPrivs=1`, CapPrm/CapEff/CapBnd 0, seccomp mode 2 |
| Process cwd | `/opt/lilith-memory-broker/releases/817a83e44cec8965479fd97fc30b7a0b3ae49ab2` |
| Socket | active since 09-25 14:54:06, `disabled`, invocation `1434eda774ed4d8296bc4e266191bc67`, `lilith-memory-broker:lilith-memory-ipc` 0660 |
| Runtime | `/run/lilith-memory` `root:lilith-memory-ipc 0710`; `owner.sock` `lilith-memory-broker:lilith-memory-ipc 0660` |
| Sandbox | identical to the accepted unit (`ProtectSystem=strict`, `RestrictAddressFamilies=AF_UNIX`, `IPAddressDeny=any`, empty capability sets, …) |

## 5. Stage III preservation (OBSERVED)

| Item | State |
| --- | --- |
| Phase journal `/var/lib/.lilith-memory-broker-stage3-a2/` | `root 0700`, single file `000-INTENT.json` (`1ef684467f40d25731edb4e871ad7d5f7fd238821a2484b371fe664fea555bd7`), mtime 09-25 14:06:15; **INTENT only** |
| Dispatch tombstone | `d4f75cb5a7b40d142695ee8f3627394031597714a613ca4258a87f6ac5e71b4d`, mtime 09-25 14:06:13 |
| Final-attempt record | `b389f62e74bf0c0e9476d2d6d321a5f0719a13125942e7d85cb41aef1cdb4374`, mtime 09-25 14:06:13 |
| Authorization `b1b2b-stage3-a2-authorization.json` | present, `84049b4b97b7d262efa1a5e5ccd5dc279e25d9f51dec685e7b64933ba171805c` |
| `…authorization.used.json` | **absent** (not consumed) |
| A2 arm `/run/lilith-memory-stage3/a2-arm.json` | **absent** |
| Guard `/run/lilith-stage3-a2/{guard.json,activation.ready}`, `guard.claim.json` | **absent** |
| `lilith-stage3-a2-final.service` | failed / exit-code 1 / `Restart=no`, inactive since 09-25 14:06:16 |
| Broker gate drop-in | none |

No earlier record pinned the tombstone or INTENT hashes. The values above are
first observations, pinned from now on by the revalidation script (§10).

## 6. Artifact, config, and state equivalence (OBSERVED)

Every value equals `verify_broker_dev_lifecycle.ACCEPTED_FILES`:

| Path | SHA-256 | Owner / mode |
| --- | --- | --- |
| `/etc/systemd/system/lilith-memory-broker.service` | `6a9dca54b9051cc7788587a0f37601f67e16fc07de043cbc5d64e7123ed35689` | 0:0 0644 |
| `/etc/systemd/system/lilith-memory-broker.socket` | `d9f21223b837fd4be98d3c67eb95625b00c8a0ee6922d06eb79605edb382e793` | 0:0 0644 |
| `/etc/tmpfiles.d/lilith-memory-broker.conf` | `e6139f16b001a3c36e9ff3db733f19a3a7ce06b1d0fbc923591bc17b2d4df86e` | 0:0 0644 |
| `/etc/lilith-memory-broker/dev.json` | `c1787b34e5f1969fe98a0d3499c7913fde01a6eba7f2ee04f427a39cd02f27fb` | 0:987 0640 |
| `/etc/lilith-memory-broker/identities.json` | `e1c808901bea374d7a0d16d49140125d8572012497905a690d634373a2070d23` | 0:0 0600 |
| `…/b1b2b-authorization.used.json` | `2c9975086f7bc41aec872ae0bdeb9e5f9da7d312495ab193e46879de5302274b` | 0:0 0600 |
| `…/b1b2b-stage2-authorization.used.json` | `d75394b18906546095650851b0c18aac3208ac3fb04bde43655c80482602ef51` | 0:0 0600 |
| `…/b1b2b-stage2-retry2-authorization.used.json` | `ad43a9e3b822390b227d4e72d4a29a9f2915773f646b192015d98f7f9e720249` | 0:0 0600 |
| `owner_control.db` | `939b5a0e4c5471bac5843f9c17de9548494ab49bfa54a062994f57900de2b7bb` | 999:987 0600, mtime 09-24 06:52:33 |
| `synthetic_evidence.db` | `a4ff3d076a51019a6287c2a492a44e755dae5e9a7da55c9d9e942d9b9362c785` | 999:987 0600, mtime 09-24 06:51:25 |

- The selector `current` points to `releases/817a83e44cec8965479fd97fc30b7a0b3ae49ab2`
  (link mtime 09-23 15:28). The Stage III candidate `releases/4a04f2d…` is
  still present and not selected.
- Differences, both INFERRED as benign consequences of clean stops and starts:
  - the SQLite `-wal` / `-shm` sidecars the accepted contract recorded are now
    absent;
  - the state directories' mtime is 09-26 06:34:10, from the new process
    opening and closing the databases.
- The single runtime-substrate difference is the patched `libexpat`.

## 7. Four separate equivalence questions

| Question | Answer | Why |
| --- | --- | --- |
| **ARTIFACT_EQUIVALENCE** | **Holds (today)** | Release, selector, units, tmpfiles, config, used markers, state DBs, ownership and modes all equal the accepted contract (§6) |
| **PROCESS_CONTINUITY** | **Lost, permanently** | `5c1eb955` / PID 96650 ended 09-25 14:06. Two incarnations followed (`42a0608f`, then `42af2691`). No evidence can restore it, and the trusted snapshot validator correctly rejects the current incarnation |
| **RUNTIME_BEHAVIORAL_EQUIVALENCE** | **Not proven** | Same code, units, config, and state, but a different shared-library substrate (libexpat), and no request has been observed through the new process. Observation alone cannot prove behaviour |
| **ACCEPTANCE** | **Stage II acceptance unchanged, not extended** | The Stage II record remains the valid historical acceptance of release `817a83e` and PID 96650. It does **not** cover `42af2691`. Matching hashes do **not** make the current process Stage-II accepted. Only a separate, owner-accepted current-incarnation baseline can |

Two rules follow from the table:

- automatic restart ≠ unauthorized authority mutation;
- process replacement still requires revalidation evidence.

## 8. Control gap: OS maintenance restarts authority-sensitive services

**Finding.** The repository assumes that only owner break-glass root can
start or stop the broker (B1b-3d §6/§18, B1c). In fact, root-level OS
maintenance automation (`unattended-upgrades` → `needrestart`) can restart it
at any time, with no owner ceremony and no project record. The same applies
to the future `lilith-authority-dev` and `lilith-recovery-witness` services.

This did not mutate authority. It did replace the process instance, and the
project's trust evidence is bound to the process instance. Requirement:
**every authority-sensitive service needs a deliberate update and restart
policy.**

Owner decisions (2026-09-26): unattended security updates stay on globally;
needrestart is not modified in this task.

### Options (DESIGN ONLY)

| Option | Mechanism | For | Against |
| --- | --- | --- | --- |
| **A. Service-specific needrestart exclusion** | `$nrconf{override_rc}{qr(^lilith-(memory-broker\|authority-dev\|recovery-witness)\.service$)} = 0;` in a root-owned `/etc/needrestart/conf.d/` file | Small; host-native; security updates still install; other services still restart | The service keeps running the old library until someone acts; staleness must be surfaced, not hidden |
| **B. Controlled maintenance window** | Move `apt-daily-upgrade.timer` to a fixed window with owner presence | Predictable | Still restarts without ceremony, only on a schedule; delays security fixes |
| **C. Quiesce, then owner restart** | Stop issuance (the B1b-3d `hold` marker) before package maintenance; the owner restarts and revalidates afterwards | Strongest ceremony | Needs tooling that does not exist yet; manual burden |
| **D. Other host-native** | `Unattended-Upgrade::Package-Blacklist` for specific libraries; a systemd `RefuseManualStop=` / `RefuseManualStart=` drop-in | — | The blacklist blocks security fixes; `RefuseManual*` also blocks the owner's own break-glass restart |

### Recommended B1b-3d policy (PROPOSED; implementation separate)

**A + C-lite.**

1. Install a service-specific `override_rc` exclusion for the three
   authority-sensitive services as its own separately authorized,
   owner-installed step before B1b-3d L1. Security updates keep installing.
2. The current-incarnation verifier treats a process that maps a deleted or
   replaced library as `RUNTIME_SUBSTRATE_STALE_OR_UNREADABLE`, so a pending
   restart is visible, never silent.
3. When a restart is needed: the owner places the `hold` marker (no new
   issuance), restarts, runs the read-only revalidation (§10), and accepts
   the new incarnation baseline explicitly.
4. The broker and authority services stay `static` / not enabled (design
   T-5); a reboot still brings them down, which is fail closed.

## 9. Evidence limitations

- The journal and dpkg logs are local, and root can alter them. They agree
  with each other and with the systemd job IDs, but there is no independent
  off-host log.
- Hash equality is a point-in-time observation. No file-integrity monitoring
  ran between 2026-09-24 and 2026-09-26, so a temporary change that was later
  reverted is not excluded.
- The GCE operations list came back empty, which was read as "no operations";
  it was not cross-checked with Cloud Audit Logs.
- The Stage III tombstone and INTENT hashes had no earlier recorded value;
  their preservation rests on mtimes and content structure.
- The PID of incarnation `42a0608f` was not recorded.

## 10. Current-incarnation read-only revalidation

[`scripts/verify_broker_dev_current_incarnation.py`](../../scripts/verify_broker_dev_current_incarnation.py)
(tests: [`scripts/test_verify_broker_dev_current_incarnation.py`](../../scripts/test_verify_broker_dev_current_incarnation.py)).

- **Entry:** it may later be streamed as `sudo python3 -I -B - baseline` on
  `lilith-dev-01`, **only after a separate owner authorization**. It was
  **not** run live in the task that created it.
- **Read only:**
  - it refuses to run unless `hostname == lilith-dev-01`, before any other read;
  - the only subprocess is `systemctl show`;
  - SQLite files are hashed as bytes, never opened;
  - it makes no socket connection and runs no `sudo -u`;
  - it creates no path.
- **Output:** `CURRENT_RUNTIME_BASELINE=PASS|FAIL`, with:
  - `releaseEquivalent`, `configEquivalent`, `stateEquivalent`,
    `identityBoundaryEquivalent`, `socketBoundaryEquivalent`,
    `stageIIIUntouched`, `deployerPolicyTextEquivalent`, `incarnationHealthy`;
  - `processContinuity` (reported against the Stage II identity, never
    required);
  - `runtimeBehavioralEquivalence=NOT_PROVEN_BY_OBSERVATION`;
  - `runtimeIncarnation`, `bootId`, `startTime`;
  - a `baselineCandidate` (invocation, PID, start ticks and time, `NRestarts`,
    release and manifest, and every mapped shared library with its SHA-256 and
    inode match) plus its digest.
- **Never output:** `STAGE_II_ACCEPTED`. The candidate is a separate artifact,
  and `ownerAcceptance` stays `PENDING_SEPARATE_EXPLICIT_OWNER_DECISION`.
- **No false denials (DR-5):** planned B1b-3d custody paths are reported as
  `NOT_YET_PRESENT`, never `DENIED`. A path that is present before B1b-3d
  fails the baseline.
- **Deployer boundary:** only policy text and the helper hash are observed,
  labelled `POLICY_TEXT_ONLY_NOT_A_DENIAL_PROOF`. The `sudo -u
  lilith-memory-broker` denial is reported `NOT_TESTED_DR5_OPEN`. Final
  B1b-3d acceptance still needs the live denial proof in design §7/L5; the
  sudoers text alone is not sufficient.

## 11. B1b-3d live-entry gates

Owner decision (2026-09-26): **LIVE_ENTRY_CLEAR_AFTER_READ_ONLY_REVALIDATION**.
DR-1 is acknowledged, and a new incarnation baseline is permitted after
read-only revalidation.

B1b-3d remains **blocked** until all of these hold:

1. this forensic record is merged;
2. the current-incarnation read-only revalidation (§10) runs under separate
   owner authorization and returns `CURRENT_RUNTIME_BASELINE=PASS`;
3. the owner explicitly accepts the resulting runtime baseline as a separate
   record (the Stage II record is not edited);
4. needrestart handling for the custody window is decided (§8).

## 12. Related drift (not changed here)

- **DR-3 (host-root debt).** `ubuntu` (uid 1000) is in `sudo`, `adm`, and
  `lxd`.
  - Membership in `lxd` is independently root-equivalent on a stock host, so
    there are **two** root-equivalent memberships.
  - `authorized_keys` is empty (0 bytes), the password is locked, and no login
    path is known. This record does not claim the account is remotely
    exploitable.
  - A root-equivalent principal nonetheless exists. It is explicit host-root
    debt; it was not mutated.
- **DR-5 (vacuous denials).** Still open. A missing path must never count as
  `DENIED`: proofs require `PATH_EXISTS`, then `ACCESS_DENIED`. Future custody
  proof must test `sudo -n -u lilith-memory-broker` explicitly.

## 13. Process deviation: read-only PROD contact

During this investigation the first SSH connection went to **`lilith-01`,
which is PROD**. The DEV host `lilith-dev-01` was identified only afterwards.

- **Commands:** `hostname`, the boot ID, `uptime`, `sudo journalctl
  --list-boots`, `last -x`, and `systemctl status|show|cat` for the broker
  units, which do not exist on PROD. All read-only.
- **Footprint:** the SSH session and the sudo journal queries are logged in
  PROD's journal (about 14:04:57 UTC).
- **No PROD mutation** occurred.
- This **violated** the task's explicit "do not contact PROD" instruction.
- **Cause:** the investigator reused a stale note that named `lilith-01` as
  "the backend", without first resolving the DEV instance name from
  `deploy-dev.yml` (`GCP_INSTANCE: lilith-dev-01`).
- **Correction:**
  - future runbooks and scripts must name the DEV host explicitly before any
    SSH;
  - the revalidation script refuses to run on any host except
    `lilith-dev-01`, and a test proves it rejects `lilith-01`.

This is recorded as process evidence ([N-43](../research/negative-results-register.md)),
not hidden.

## Explicitly not done

- No restart, stop, start, reload, or `daemon-reload`.
- No change to needrestart, unattended-upgrades, `ubuntu`, sudoers, IAM, WIF,
  systemd, workflows, keys, the broker, or Stage III.
- No authorization consumed; no Stage III retry or arm.
- The new revalidation script was not run against DEV.
- B1b-3d was not started.
