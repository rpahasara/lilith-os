# F8r2: DEV Hermes Phase A installation runbook (lilith-dev-01)

**Status:** PREPARED, LOCALLY VALIDATED, NOT INSTALLED.
- Local build and validation only: WSL Ubuntu 24.04 DEV mirror.
- No PROD contact. No DEV change. No service installed or restarted. No credential, firewall or IAM change. No commit, push or deploy.

**Package:** `hermes-gateway-dev-f293e72-f8r2.tar.gz`, sha256 `269dde950eb024155235b3237a4658c93039975c600fa2f40d638ff02945e327` (deterministic: two builds, identical bytes).
**MANIFEST.sha256:** 14,293 files, sha256 `171af3be77a2fabcf1abda2c95bee57711b5572b7d4fe7c449ed6439ef011412`.
**Supersedes:** f8r1 `4e1167bb…` (NO-GO at the safety gate). Phase B (model provider) becomes a later revision, `f8r3`.

**Phase A boundary:**
- No provider credential, no egress, no tools.
- Router V2 in shadow; every cognitive lane off; `world_context` is the import stub.
- Owner recording and canonical admission inactive.
- Synthetic text only.
- Gateway never enabled at boot.
- No Next.js UI change.

## 1. What changed from f8r1 (C-1 … C-7)

| Fix | Change | Where |
|---|---|---|
| C-1 | Backup tars only HERMES_HOME. Core API DBs are **never opened or copied**: `observe_host.sh` records their sha256 (raw read) and metadata, and reads credential and custody objects as metadata only. | `bin/backup_pre_install.sh`, `bin/observe_host.sh`, `bin/compare_observations.sh` |
| C-2 | No GCE disk snapshot anywhere in the runbook. The single disk holds `/var/lib/systemd/credential.secret` and the authority `.cred`; the default compute SA has `roles/editor`. Rollback is file-level only. | §7 |
| C-3 | Install refuses before any write if any of these hold: any unit has `NeedDaemonReload=yes`, systemd jobs are queued, a dpkg lock is held, an apt unit is active, or apt timers are due within 45 min. The same check runs again immediately before `daemon-reload`, and the 9 existing units' MainPID / InvocationID / NRestarts / start stamp must be identical across the reload. Rollback withholds its reload (`F8_ROLLBACK_HOLD`) under the same conditions. | `bin/install.sh`, `bin/rollback.sh` |
| C-4 | Changed: `IPAddressAllow=127.0.0.1/32` (was `localhost`, which admits the 127.0.0.53/54 resolver stubs and ::1), `RestrictAddressFamilies=AF_UNIX AF_INET`, `InaccessiblePaths=/run/dbus /run/systemd/resolve`. Unchanged: `IPAddressDeny=any`. Unit files are now in the start gate's critical-set pin. An in-sandbox probe proves it (P1–P17). | `systemd/hermes-gateway-dev.service`, `bin/sandbox_probe.sh` |
| C-5 | Pinned DR-5 script `9b569f9b…0f43` and the expected DEV block `7fe21378…68f1c` (155 lines, 142 DENIED, maturity L1c.3 / P1A-9, from DEV deploys 39798993803 and 39781661322) are shipped. `dr5_check.sh` runs the proof as `sa_112096412008414111981` and requires byte equality with the expected block. | `dr5/`, `bin/dr5_check.sh` |
| C-6 | Failure injection at all 8 install stages plus post-install, precondition and rollback-hold cases (§9). The hook is active only with `F8_SIM=1`, which install.sh refuses on lilith-dev-01. | `bin/install.sh` `inject()` |
| C-7 | Complete operation and path allowlist (§4); rollback moves only allowlisted F8 paths. | §4, `bin/rollback.sh` |

## 2. Preconditions for the real run (all must hold, or do not start)

1. Owner authorization **D-0** names package sha `269dde950eb024155235b3237a4658c93039975c600fa2f40d638ff02945e327` and this runbook.
2. Window: no apt run in progress, and neither `apt-daily.timer` nor `apt-daily-upgrade.timer` due within 45 min. Today `apt-daily-upgrade` fires at about 06:17 UTC daily. install.sh enforces this.
3. No other DEV operation, ceremony or deploy is in progress or scheduled during the window. **Owner confirms there is no active freeze.**
4. The latest DEV deploy's DR-5 block still equals `7fe21378…` (`gh run view <id> --log`). If DEV has legitimately changed since b9eb32c, re-derive the expected block first. That is a package change.
5. ≥ 2 GiB free on `/`; memory available ≥ 1 GiB.

## 3. Gates (stop at any FAIL line; on stop: §7)

All SSH goes to **lilith-dev-01 only**: `--zone=asia-southeast1-b --project=lilith-agent-260823-27389 --tunnel-through-iap`. Use gzip+base64 in `--command` (never stdin). Treat rc `0xC0000005` as the known local plink crash: never accept that output, re-read instead. `P=/var/tmp/f8/hermes-gateway-dev-f293e72-f8r2`, `R=/opt/hermes-gateway-dev/current`.

| Gate | Command (root on DEV unless noted) | PASS criterion |
|---|---|---|
| G-0 | Owner records D-0, the package sha and the window. | — |
| G-2 | Laptop: `gcloud compute scp package/hermes-gateway-dev-f293e72-f8r2.tar.gz* lilith-dev-01:/var/tmp/ …`. DEV: `install -d -m 0700 /var/tmp/f8`, move both files in, `sha256sum -c *.sha256`, `tar -xzf`, `cd $P && sha256sum --quiet -c MANIFEST.sha256` | `OK`, then silence |
| G-1 | `bash $P/bin/backup_pre_install.sh` | `F8_BACKUP_DONE /var/backups/hermes-gateway-dev/pre-<ts>` |
| G-1b | `bash $P/bin/dr5_check.sh /var/backups/hermes-gateway-dev/dr5-pre.txt` | `F8_DR5_EQUAL 7fe21378…` (byte-identical; generic PASS insufficient) |
| G-3 | `bash $P/bin/install.sh` | `F8_INSTALL_STAGED f293e72-f8r2`. The only allowed FAIL line is `F8_VERIFY_FAIL MISSING …/.env`. |
| G-3b | `bash $P/bin/dr5_check.sh …/dr5-installed.txt` | `F8_DR5_EQUAL` |
| G-4 | F7 suite as `lilith` (exact block in §7) | `Ran 19 tests … OK` |
| G-5 | `bash $P/bin/provision_console_token.sh`, then `$R/venv/bin/python -I -B $R/bin/verify_release.py --full` | `F8_TOKEN_PROVISIONED sha256_prefix=…` (record only the prefix); `F8_VERIFY_PASS full f293e72-f8r2` |
| G-6 | `systemctl start hermes-gateway-dev` (this also starts the static retention timer through `Wants=`; **never `enable`**: an enable or disable, even with `--no-reload`, marks every unit on the host `NeedDaemonReload=yes`). Poll `ss -Hltn 'sport = :9901'` for up to 90 s, then `systemctl show` ActiveState, SubState, NRestarts and UnitFileState, plus `systemctl show lilith-os-api-dev -p NeedDaemonReload` | `active running 0 static`; exactly `127.0.0.1:9901`; gateway and timer `is-enabled` = `static`; NeedDaemonReload=`no` |
| G-7 | `$R/venv/bin/python -I -B $R/bin/smoke_console.py --phase A --core-api` | `F8_SMOKE_PASS phase=A 22/22`, including S0 (waits for Hermes' "startup restore drained" marker), S10 (real Core API relay) and S11 (capture 403) |
| G-7b | `bash $R/bin/sandbox_probe.sh` | `F8_PROBE_PASS 17/17` |
| G-8 | `systemctl start hermes-gateway-dev-retention.service` | `Result=success` |
| G-9 | `bash $P/bin/observe_host.sh /var/backups/hermes-gateway-dev/post`, then `bash $P/bin/compare_observations.sh <G-1>/observation /var/backups/hermes-gateway-dev/post`, then `bash $P/bin/dr5_check.sh …/dr5-post.txt` | `F8_OBSERVATION_EQUAL` (services, units, sockets, custody, coreapi, accounts) and `F8_DR5_EQUAL` |
| G-9b | Laptop: existing IAP tunnel `start-iap-tunnel lilith-dev-01 8765 --local-host-port=localhost:18765`, then GET `/system/status` | served (tunnel route preserved) |
| G-10 (optional) | Laptop, existing `lilith-os-devui` worktree, **no file changes**: process env `LILITH_API_URL=http://127.0.0.1:18765` with the capture token unset; `npx next dev --hostname 127.0.0.1`. Send the synthetic text `F8-SYNTHETIC UI check`. | The reply shows the provider-failure notice. No UI file is modified. |

Then **STOP for owner acceptance**. A content change in `coreapi` or `custody` during the window is a STOP for owner adjudication, even if it was caused by an existing service.

## 4. Operation and path allowlist (C-7)

### Paths F8 may create or modify (all root-owned unless stated)

| Path | Created by | Mode | Removed/moved by |
|---|---|---|---|
| `/var/tmp/f8/` (package + extraction) | G-2 | 0700 | owner purge after acceptance (D-7) |
| `/var/tmp/f8-g4-*` (F7 suite temp, lilith) | G-4 | 0700 | `rm -rf` at the end of G-4 (this path only) |
| `/var/backups/hermes-gateway-dev/{pre-*,rollback-*,post,dr5-*.txt}` | G-1, G-9, R-2 | 0700 | owner purge (D-7) |
| `/opt/hermes-gateway-dev/` (`releases/f293e72-f8r2/{src,python,venv,bin,dr5,…}` read-only; `current` link) | G-3 | 0755 / a-w | R-2 → quarantine |
| `/etc/hermes-gateway-dev/critical.sha256` | G-3 | dir 0750, file 0600 | R-2 → quarantine |
| `/etc/systemd/system/hermes-gateway-dev.service`, `…-retention.service`, `…-retention.timer` | G-3 | 0644 | R-2 → quarantine |
| `/etc/systemd/journald@hermes-gateway-dev.conf` | G-3 | 0644 | R-2 → quarantine |
| `/var/log/journal/<machine-id>.hermes-gateway-dev/` | systemd (journal namespace) at G-6 | journald | R-2 → quarantine |
| `/home/lilith/.hermes-dev/{config.yaml,.env}` | G-3, G-5 | root:lilith 0640 | R-2 → quarantine |
| `/home/lilith/.hermes-dev/{lilith_router,plugins}/` + 8 empty stubs (`skills optional-skills optional-mcps hooks scripts bin node node_modules`) | G-3 | 0755/0644 | R-2 → quarantine |
| `/home/lilith/.hermes-dev/cron/jobs.json` = `{"jobs": []}` | G-3 | 0644 | R-2 → quarantine |
| `/home/lilith/.hermes-dev/{logs,cache,cron}/` and Hermes runtime state (`state.db*`, `sessions/`, `SOUL.md`, `gateway.*`, …) | G-3, gateway | lilith 0700 / 0600 | R-2 → quarantine |
| Runtime: `/run/systemd/journal.hermes-gateway-dev/`, the gateway's own cgroup and mount namespace | systemd | — | gone at stop |

### Never touched

- **Paths:**
  - `/home/lilith/.hermes-dev/memories/`
  - `/home/lilith/.hermes/**`: the Core API tree, its data and DBs
  - `/etc/lilith-os-dev`
  - every broker, authority and witness path: `/opt/lilith-*`, `/etc/lilith-*`, `/var/lib/lilith-*`, `/run/lilith-*`, `/run/credentials/*`
  - `/etc/credstore.encrypted`, `/var/lib/systemd/credential.secret`
  - `/etc/sudoers*`, `/etc/passwd`, `/etc/group`
  - `/etc/needrestart`, `/etc/tmpfiles.d`, `/usr/local/{sbin,lib}`
  - the host journald config
  - firewall, IAM, GCE metadata, disk snapshots
- **Units:** `lilith-os-api-dev`, `lilith-memory-broker{,.socket}`, `lilith-authority-dev{,.socket}`, `lilith-recovery-witness{,-owner.socket,-signer.socket}`, `lilith-stage3-a2-final`.
- **Packages:** no apt or pip on the host system.

### Operations F8 may run

| Operation | Gate | Notes |
|---|---|---|
| read-only: `stat`, `find -printf`, `sha256sum` (raw), `ss`, `systemctl show / list-units / list-jobs`, `/proc` fd scan, `journalctl --namespace=hermes-gateway-dev` | G-1, G-9, every gate | no DB open, no credential content read |
| `sudo -n -i -u sa_112096412008414111981 bash -s < dr5/deployer_authority_boundary_proof.sh` | G-1b, G-3b, G-9 | proof only: `test` access checks, `sudo -n -l` and `pkcheck` queries |
| `tar`, `cp -a`, `install`, `chown`, `chmod`, `ln -sfn` + `mv -T` | G-2, G-3, G-5 | allowlisted paths only |
| `uv venv` / `uv pip install --offline --no-index --require-hashes` | G-3 | into `$REL/venv` only |
| `systemd-analyze verify` (F8 units) | G-3 | read-only |
| `systemctl daemon-reload` | G-3, R-2 | only after C-3 preconditions + identical-state proof |
| `systemctl start hermes-gateway-dev` (pulls in the static timer); `systemctl start hermes-gateway-dev-retention.service` | G-6, G-8 | F8 units only; **no `enable`/`disable`** of anything |
| synthetic HTTP to `127.0.0.1:9901` and `127.0.0.1:8765/os/conversation{,/evidence}` | G-7 | synthetic text; relay writes nothing for non-capture sessions |
| one probe process in the gateway's cgroup and mount namespace (`nsenter -m`, `setpriv` → lilith) | G-7b | exits by itself |
| `systemctl stop` (F8 units + namespace journald), `mv` to quarantine | R-1, R-2 | never `rm`; `disable --no-reload` only if an F8 unit was found enabled |

## 5. Known behaviour and residual risks

- **Startup race:** console messages sent in the first ~1–2 s after a gateway (re)start get "(LILITH completed the turn without a text reply.)". Hermes queues them during startup restore and the adapter resolves early. Not a safety issue: commands stay gated. The adapter is F7-accepted source and was not changed; a fix belongs to a later reviewed revision.
- **Loopback reach:** the gateway can reach other `127.0.0.1` TCP listeners (e.g. the Core API on 8765). IPAddress filters cannot restrict ports. There are zero tools, so no agent path uses it.
- **Shared uid:** the Core API runs unsandboxed as the same uid `lilith`; it can read `$HH/.env` by design (relay), and could rename RO-bound items on the host side. The start gate re-hashes on every start.
- **Boot:** after a reboot nothing F8 runs until the gateway is started again by hand (not enabled); retention then catches up (`Persistent=true`).
- **Mirror vs DEV:** the mirror is WSL, not GCE. The Core API is real; broker, authority and witness are stand-ins; metadata, NAT and IAP are not reproduced. DR-5 equality on DEV itself is re-proved at G-1b / G-3b / G-9.
- **DR-5 invocation:** the method `sudo -n -i -u <deployer> bash -s` (rather than the CI's OS Login SSH) reproduced the DEV block byte for byte in the mirror. Confirming it is acceptable on DEV is part of D-0.
- **Plink crash:** the known local plink crash can hit the 152 MiB transfer; the G-2 hash check catches it.

## 6. Retention

As in f8r1 §8:
- `state.db` + transcripts: pruned daily, 7 days.
- Logs, including the decisions log: rotated daily, 7 days.
- Journal namespace: 7 days / 200 MB.
- `/var/backups/hermes-gateway-dev` and quarantines: root 0700, purge after acceptance + 14 days (D-7).

The G-1 backup no longer contains any Core API data (C-1).

**Hermes DEV history is not canonical First Memory**, and it is outside L18_V2 FORGET.

## 7. Rollback (validated: §9)

- **R-1** `bash $R/bin/rollback.sh stop` (or `$P/bin/rollback.sh stop`): stops the F8 units and checks that 9901 is closed. The Core API console returns 502, as before F8.
- **R-2** `bash $P/bin/rollback.sh remove`:
  - R-1, then **moves** every §4 F8 path to `/var/backups/hermes-gateway-dev/rollback-<ts>/` (0700). It never deletes.
  - It works on partial installs.
  - It runs `daemon-reload` only under C-3 and an identical-state proof; otherwise it prints `F8_ROLLBACK_HOLD`, and the owner decides the reload.
  - It checks the HERMES_HOME listing against G-1.
- After any rollback, **re-run G-9**: `F8_OBSERVATION_EQUAL` against G-1, and `F8_DR5_EQUAL`.
- Newer DEV state is preserved: nothing is restored from a backup, and no path outside §4 is touched.
- **No disk snapshot** (C-2).

## 8. G-4 command block

```
B=$(mktemp -d /var/tmp/f8-g4-XXXXXX); R=/opt/hermes-gateway-dev/current
ln -s $R/src $B/hermes-agent; mkdir $B/hermes-home-dev $B/tests
cp -a $P/home/lilith_router $P/home/plugins $B/hermes-home-dev/
cp $P/tests/f7-home/config.yaml $B/hermes-home-dev/; cp $P/tests/f7-home/router.yaml $B/hermes-home-dev/lilith_router/
cp $P/tests/test_f7_offline.py $B/tests/; chown -R lilith:lilith $B; chmod 700 $B
runuser -u lilith -- env -i PATH=/usr/bin:/bin HOME=$B PYTHONUNBUFFERED=1 $R/venv/bin/python -B $B/tests/test_f7_offline.py
rm -rf -- "$B"
```

## 9. Local validation evidence (WSL DEV mirror)

Run 4 (final), package `269dde95…e327`, WSL Ubuntu 24.04 DEV mirror, 2026-10-23: **51/51 rows PASS**.
Evidence: `evidence/evidence-run4.tgz` (`1415f0a1…9749`), `evidence/results.tsv`, `evidence/suite.log`. Mirror tooling: `mirror-tools/`.

**Mirror fidelity.** Real Core API at main b9eb32c with the DEV unit text. Stand-in broker, authority and witness services use DEV's exact unit, socket and drop-in definitions (stand-in programs, synthetic non-secret credentials). Every DR-5 ladder, custody and later-state object has DEV's owner and mode. The deployer account `sa_112096412008414111981` (uid 3826947836) has the repo's exact sudoers rule and helper.
**The pinned DR-5 (`9b569f9b…`), run as that deployer, reproduces the current DEV block byte for byte**: `7fe21378…`, 155 lines, 142 DENIED, 0 ALLOWED, 0 FAIL, L1c.3 / P1A-9, including polkit `pkcheck_rc=2`.

| Scenario | Result |
|---|---|
| M0 baseline | DR-5 = DEV block |
| Happy path G-2…G-9 | **G-2:** MANIFEST OK. **G-3:** staged. **DR-5 installed:** EQUAL. **G-4:** F7 19/19 on Linux against the installed release. **G-5:** verify PASS. **G-6:** active/running, 0 restarts, static, listening `127.0.0.1:9901` after about 6 s, 82 MiB, no unit left NeedDaemonReload. **G-7:** smoke 22/22 (real relay S10, capture 403 S11, 9 slash commands not executed). **G-7b:** probe 17/17 (metadata, internet, PROD IP, own NIC IP, DNS stub and public resolution blocked; D-Bus, resolved, Core API tree, broker, credstore hidden or inaccessible; config, jobs and router not writable). **G-8:** retention success. Existing services had identical PID / InvocationID / NRestarts across start, smoke and probe. **G-9:** observation EQUAL to G-1 with F8 running; DR-5 EQUAL. A second install was refused. **R-1, R-2:** CLEAN. |
| Injected failure at `preconditions`, `stage`, `venv`, `home`, `etc`, `units`, `reload`, `verify` | each stopped non-zero at that stage; R-2 → **CLEAN** (observation == G-1 == M0, DR-5 EQUAL, no F8 path, 9901 closed, HERMES_HOME = `memories` only) |
| PF-gate: a lane switched on after install | start refused (`HASH_MISMATCH router.yaml`, `LANE_NOT_OFF cognitive_enabled`); R-2 CLEAN |
| PF-provider: provider key in Phase A | start refused (`FORBIDDEN_KEY`); R-2 CLEAN |
| PF-crash: 4× SIGKILL | the restart loop stops at StartLimitBurst (failed); R-2 CLEAN |
| PF-running: R-2 straight from a running gateway + active timer | CLEAN |
| PG-reload: another unit pending reload | install refused before any write (`NEED_DAEMON_RELOAD_PENDING lilith-authority-dev.service`); CLEAN |
| PG-dpkg: dpkg lock held | install refused before any write (`DPKG_LOCK_HELD`); CLEAN |
| PG-rollback-hold: other unit pending reload during R-2 | files moved, reload withheld (`F8_ROLLBACK_HOLD`), 9901 closed; after the owner-equivalent reload, CLEAN |
| FINAL | observation M0 == FINAL; DR-5 EQUAL |

Found in runs 1–3, and fixed or confirmed:
- **Implicit reload (fixed):** `systemctl enable/disable` performs an implicit daemon-reload, and `--no-reload` flags every unit `NeedDaemonReload=yes`. Fix: the static timer is pulled in via `Wants=`, nothing is ever enabled, and rollback uses `--no-reload`.
- **APT_WINDOW (confirmed):** the guard refused installs while `apt-daily.timer` was 9–10 min away.
- **Startup race (handled):** see §5; G-7 waits for readiness (S0).
- **Rollback journal (fixed):** rollback stops the namespace journald unconditionally before moving its journal.
- **Probe semantics (fixed):** the probe accepts InaccessiblePaths' unreadable mount node as "not accessible".
- **Interrupted install (confirmed):** a kill-interrupted partial install was cleaned by R-2.
