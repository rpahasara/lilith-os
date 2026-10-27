# F8: DEV Hermes installation readiness (lilith-dev-01), 2026-10-23

**Status:** PREPARED. Nothing is installed on DEV. The read-only DEV preflight is done; the full runbook ran
end-to-end in a local WSL Ubuntu 24.04 simulation of the DEV layout. No PROD contact; no service, firewall, secret or
model call on any real host; no commit or push.

**Scope:** Phase A only. This is an infrastructure install of the F7 runtime: lilith_os console on 127.0.0.1:9901, zero
tools, every cognitive lane off, Router V2 in shadow, `world_context` an import stub, owner recording and canonical
memory admission inactive, no model provider and no egress. Phase B (model provider) is a separate, owner-authorized
package revision (see D-1).

## 1. Artifacts (`C:\Users\edufo\lilith-hermes-staging\f8-dev-install-20261023\`)

| Item | sha256 |
|---|---|
| `package/hermes-gateway-dev-f293e72-f8r1.tar.gz` (152 MiB, deterministic: two builds, same bytes) | `4e1167bb5aa64043d6803ddf83cffd05671e061289ec626850b71fb172b5cac7` |
| `MANIFEST.sha256` inside it (14,287 files) | `8765ba0cff02dee06e6b9c888ed74019895769e72d7d16168a09c4167fa59244` |
| `RELEASE_ID` = `f293e72-f8r1` | `36c05c74…` |

Package contents, with provenance:

| Component | Provenance / check | Hash |
|---|---|---|
| `src/`: upstream NousResearch/hermes-agent `f293e7206b4ddd66042329442c6afebc19a8808d` + 6 F7 files | 10,091 files verified blob by blob against the upstream git tree (10 `.ps1` are CRLF by upstream `.gitattributes eol=crlf`, LF blob matches). The 6 overlay files equal the F7/PROD hashes (`run.py` `2774eee5…`, containment `c1667e62…`, etc.) | tree `df3e987a…` (10,092 files) |
| `python/`: CPython 3.11.16 (python-build-standalone, `linux-x86_64-gnu`) | installed by uv 0.12.5, which verifies its pinned download hash. = F7/PROD interpreter version | tree `8beefa7c…` (4,079 files) |
| `uv/uv` 0.12.5 `x86_64-unknown-linux-gnu` | GitHub release tarball `68a509da…` matched the published `.sha256` | `b65f23a4…` |
| `wheelhouse/`: 60 manylinux/py3 wheels | `pip download --require-hashes` against `uv export --frozen --no-dev` of `uv.lock` `64a66f8a…` | list `9d9ad9d9…` |
| `buildbackend/setuptools-83.0.0` | `pyproject [build-system]` pin (not in uv.lock) | `29b23c36…` |
| `requirements.locked.txt` (from uv.lock, all hashes) | used with `--require-hashes` on the host too | `c78877af…` |
| `EXPECTED-DISTS.txt`: 61 dists | install fails unless `uv pip list` matches exactly | `2908dd43…` |
| `home/lilith_router/*`, `home/plugins/*` | byte-identical to F7 `hermes-home-dev` (hardened adapter `76948218…`, stub `world_context` `5c1fbf98…`) | per-file in MANIFEST |
| `home/config.yaml`, `home/router.yaml` | F7 + F8 deltas (section 5) | `7e6a74dc…`, `14fcb90f…` |
| `systemd/*`, `bin/*` | F8 (reviewable copies in `review/`) | MANIFEST |
| `tests/test_f7_offline.py` + `tests/f7-home/` | unchanged F7 suite and F7 config for the Linux re-run | `fd1610cb…` |

Reproduce: `build-tools/build-stage1.sh` and `build-stage2.sh` (WSL Ubuntu 24.04, root). Simulation:
`build-tools/sim.sh`. Evidence: `evidence/`.

## 2. DEV infrastructure preflight (read-only, 2026-10-23 05:05Z, `evidence/dev-preflight-pass*.txt`)

| Area | Finding |
|---|---|
| VM | e2-small (2 shared vCPU), 1,960 MiB RAM (1,443 available), **no swap**, 19 GB ext4 (13 GB free, 7% inodes). Ubuntu 24.04.4, kernel 7.0.0-1014-gcp, systemd 255. Boot `cb0d71da…`, up 13 d. No reboot pending. |
| Python | System has only 3.12.3, no 3.11, no uv, so the package brings its own CPython 3.11.16 + uv. **No apt install is needed**, which avoids the needrestart/libcrypto class of incident that hit the broker before. |
| Services | Running: `lilith-os-api-dev` (uvicorn, PID 176771, NRestarts 0), `lilith-memory-broker`, `lilith-authority-dev`, `lilith-recovery-witness`. `hermes-gateway`/`hermes-gateway-dev`: not-found. Hermes is not installed anywhere. |
| Sockets | TCP `0.0.0.0:8765` (Core API), `:22` (sshd); 9901 free. Unix: broker `/run/lilith-memory/owner.sock` (`lilith-memory-ipc` 0660); authority/witness owner sockets root 0600; witness signer `lilith-authority-dev` group. |
| User `lilith` | uid 1001, groups = `lilith` only. **Cannot reach** the broker, authority or witness sockets/state (verified with `sudo -u lilith test`). No linger, no crontab, no sudoers entry. |
| HERMES_HOME | `/home/lilith/.hermes-dev` lilith 0700 holding only an empty `memories/` (read by the Core API). `/home/lilith/.hermes` is root 0755 containing the Core API tree `lilith-os-dev/` (lilith 0700), which is also Hermes' **fallback home**. The unit hides it (`ProtectHome=tmpfs`). |
| Core API → console | `services/core-api/app.py` reads `LILITH_OS_PORT`/`LILITH_OS_TOKEN` from `$HERMES_HOME/.env`, then its own env. Its unit has no `LILITH_FI_EVIDENCE_CAPTURE`, so owner capture stays inactive. |
| Host firewall | ufw inactive, iptables ACCEPT, nft empty. |
| Journald | default config, 533.6 MB used, no time-based retention (host-wide; F8 does not change it). |
| AppArmor | loaded; unprivileged userns allowed (the unit sets `RestrictNamespaces=yes`). |
| Deployer | The routine `lilith-dev-deploy` touches only `lilith-os-api-dev` under `/home/lilith/.hermes/lilith-os-dev`, so it never interferes with the gateway. |
| Egress | No external IP. Egress goes through Cloud NAT `lilith-router/lilith-nat` (all subnets). Private Google Access is off. **The VM service account `lilith-dev-vm@` has the `cloud-platform` scope**, so the gateway must not reach the metadata server (blocked by the unit). |

## 3. Port 8765 exposure (read-only; nothing changed)

- **Not publicly reachable.** Neither `lilith-01` nor `lilith-dev-01` has an access config/external IP. Cloud NAT is
  egress-only.
- **lilith-vpc ingress rules:** `lilith-allow-iap-ssh` (tcp:22 from `35.235.240.0/20`, tag `lilith-vm`) and
  `lilith-api-iap` (tcp:8765 from `35.235.240.0/20`, **no target tag, so it applies to every instance in the VPC**). There is no
  allow-internal rule and there are no network firewall policies. So PROD→DEV (10.20.0.2→10.20.0.3:8765) and any other
  in-VPC source is dropped by the implied deny. The permissive `default-allow-*` rules (ssh/rdp/icmp from 0.0.0.0/0) are on the
  **`default`** network, which has no instances.
- **IAP tunnel access:** project `roles/owner` (owner account) and `roles/iap.tunnelResourceAccessor` +
  `osAdminLogin` for `github-lilith-deployer@` (project-wide, all ports, both VMs). This is the existing posture.
- **The working IAP tunnel route is preserved:** F8 changes no firewall rule, no bind and no IAM.
- **New 9901:** bound to 127.0.0.1 by the adapter, and `IPAddressAllow=localhost` in the unit. No firewall rule exists for it,
  and IAP forwards to the NIC IP, never to loopback, so it is unreachable from IAP or the VPC.
- Observations for later (not part of F8): `lilith-api-iap` could be scoped by target tag per VM; the deployer SA's
  tunnel grant could be conditioned to port 22 and the DEV VM. The Core API must stay on a non-loopback bind
  for the IAP tunnel to work.

## 4. Install layout

| Path | Owner / mode | Purpose |
|---|---|---|
| `/opt/hermes-gateway-dev/releases/f293e72-f8r1/{src,python,venv,bin}` | root, read-only (`a-w`) | code; venv built on the host, offline |
| `/opt/hermes-gateway-dev/current` → `releases/f293e72-f8r1` | root | atomic switch |
| `/etc/hermes-gateway-dev/` (`critical.sha256`, later `provider.env`) | root 0750/0600 | start gate pins + Phase B credential; hidden from the service |
| `$HH=/home/lilith/.hermes-dev` | lilith 0700 (unchanged) | writable DEV state |
| `$HH/lilith_router/`, `$HH/plugins/` | root 0755/0644 + RO bind | Router V2 + lilith_os + groq plugin code |
| `$HH/config.yaml`, `$HH/lilith_router/router.yaml`, `$HH/.env` | root:lilith 0640 + RO bind | config; `.env` = port + DEV token only |
| `$HH/{skills,optional-skills,optional-mcps,hooks,scripts,bin,node,node_modules}` | root, empty, RO bind | block lazy downloads / skill / hook / node installs |
| `$HH/cron/jobs.json` = `{"jobs": []}` | root 0644 + RO bind | the cron ticker cannot be disabled; this pins it to no jobs |
| `$HH/{logs,cache,state.db,sessions,…}` | lilith (created at run) | Hermes runtime state |
| units `hermes-gateway-dev.service`, `…-retention.{service,timer}`, `/etc/systemd/journald@hermes-gateway-dev.conf` | root 0644 | |

Names deliberately avoid the `lilith`/`recovery-witness` markers used by the authority host observer's namespace
inventory, so F8 does not change the authority observation sections (`releases`, `hostFiles`, `accounts`, `listings`,
`filesystems`). DR-5 checks root ownership of `/opt`, `/etc`, `/etc/systemd/system`, and every F8 object is root-owned.

## 5. Systemd and security configuration (`review/systemd/hermes-gateway-dev.service`)

- `User=lilith`, `UMask=0077`. The `ExecStartPre=+verify_release.py --pre-start` runs as root and checks:
  - the critical-set hashes;
  - root ownership of code;
  - the config pins, every lane off, `.env` keys and token format;
  - the cron pin;
  - that the stub is recognised.

  If any check fails, the gateway does not start.
- `ExecStart=…/venv/bin/python -I -B -m hermes_cli.main gateway run`. No `[Install]` section, so the unit is not enabled at boot (D-6).
- Filesystem:
  - `ProtectSystem=strict` and `ProtectHome=tmpfs`, with `BindPaths=` granting HERMES_HOME only. The `ReadOnlyPaths=` binds above make rename fail with EBUSY.
  - `InaccessiblePaths=` for `/etc/hermes-gateway-dev`, `/etc/lilith-os-dev`, credstore/custody, broker/authority/witness `etc`/`var/lib`/`opt`/`run`, the stage3/trusted-controls trees, the deployer lib and `sudoers.d`.
- Kernel/privilege: `NoNewPrivileges`, empty `CapabilityBoundingSet`, `PrivateTmp/Devices/IPC`, `Protect{KernelTunables,KernelModules,KernelLogs,ControlGroups,Clock,Hostname}`, `ProtectProc=invisible`, `RestrictNamespaces`, `RestrictSUIDSGID`, `LockPersonality`, `SystemCallFilter=@system-service` minus privileged/mount/debug/module/…
- Network (Phase A): `RestrictAddressFamilies=AF_UNIX AF_INET AF_INET6`, `IPAddressDeny=any`, `IPAddressAllow=localhost`, `IPAccounting=yes`.
- Resources: `MemoryHigh=450M`, `MemoryMax=640M`, `MemorySwapMax=0`, `TasksMax=128`, `CPUWeight=50`, `IOWeight=50`, `OOMScoreAdjust=500`. The kernel OOM killer picks the gateway before the broker, authority or Core API. Simulated peak was 126 MB; PROD runs at about 245 MB.
- `LogNamespace=hermes-gateway-dev` with its own retention: console previews stay out of the main journal that other DEV evidence relies on.
- `systemd-analyze security`: **1.2 OK**.
- No interference with the existing DEV services:
  - different user from the broker, authority and witness;
  - no access to their sockets or state;
  - no shared unit, socket, port or dependency;
  - not in needrestart's override list (an unattended library upgrade may restart only this unit);
  - the Core API is untouched. Its relay starts answering instead of returning 502 once 9901 is up.

## 6. Tool-isolation strategy (Linux-verified)

| Threat | Layers (all verified in the WSL run) |
|---|---|
| Terminal / file write / browser / code exec / MCP tools | `platform_toolsets.lilith_os: []` + `agent.disabled_toolsets` deny-list (0 tools even with every toolset enabled: F7 suite 19/19 **on Linux**). No `mcp_servers`, and `optional-mcps/` is an RO stub. FS: everything RO except HERMES_HOME state. |
| Operator slash commands (the console is `role_authorized`) | **New F8 finding**: `/update`, `/skills install`, `/model --global`, `/restart`, `/yolo`, `/sethome` were reachable. Fixed by Hermes' own gate (`lilith_os.allow_admin_from: [f8-no-console-admin]`, `user_allowed_commands: []`); smoke S6 shows all are refused as "admin-only" or "unknown command". Plain chat is unaffected. |
| Autonomous commands | The cron ticker always runs in the gateway; `cron/jobs.json` is pinned empty and RO. `cron.allow_agent_scheduling: false`, the `cronjob` toolset is denied, the curator, background review, kanban dispatch and nudges are off, and `hooks/` is an RO stub. |
| Lazy package / binary installs | `security.allow_lazy_installs: false` + `HERMES_DISABLE_LAZY_INSTALLS=1` + root RO venv + `PIP_NO_INDEX`/`UV_OFFLINE` + no egress. **New Linux-only finding**: at start Hermes downloads the **tirith** scanner from GitHub in a background thread (F7 never saw it because Windows is unsupported). The first simulation run proved the sandbox blocked it (`.tirith-install-failed`). Now `security.tirith_enabled: false` + `TIRITH_ENABLED=0`. |
| Unauthorised memory writes | Hermes `memory.memory_enabled/user_profile_enabled: false` and the `memory` toolset is denied. `memories/` is RO in the unit. The broker/authority sockets are unreachable (different group + `InaccessiblePaths`). `canonical_ltm_enabled: false`; no `lilith_memory` import path. |
| Egress / credential theft | Phase A has no egress at all. In the simulation, metadata `169.254.169.254`, `1.1.1.1:443` and PROD `10.20.0.2:8765` were all blocked from the service cgroup. The Phase B drop-in keeps metadata, the VPC, RFC1918, CGNAT and link-local denied. |
| Code/config tampering by the agent | RO binds (`touch` gives EROFS/EACCES; `mv plugins` gives EBUSY), `/opt` RO, `/etc/hermes-gateway-dev` hidden. Residual: the unsandboxed Core API runs as the same uid and could rename RO-bound items on the host side. The pre-start hash gate catches that on the next start. |

## 7. Model provider credential (Phase B; not provisioned)

- `EnvironmentFile=-/etc/hermes-gateway-dev/provider.env`, root 0600. PID 1 reads it before dropping privileges, and the file is
  `InaccessiblePaths` to the service. Unlike `$HH/.env`, the Core API, `lilith` and the agent cannot read it.
- Template (one line, filled on the host by the owner at the Phase B gate, never copied from PROD):
  `<PROVIDER>_API_KEY=<new DEV-only key with a provider-side spend cap>`
- Phase B is a new package revision `f8r2`, because three hashed items change:
  - `config.yaml model.default/provider` (and `router.yaml hermes_model/hermes_provider`);
  - `verify_release.PROVIDER_ALLOWED = {"<PROVIDER>_API_KEY"}`;
  - `systemd/20-provider-egress.conf` gets installed.

  Router V2 stays in **shadow**, so only one provider is needed; the Groq social lane would need its own key.
- Never used: PROD `auth.json` (openai-codex OAuth), any PROD `.env` value or a shared key.

## 8. Retention (DEV Hermes history is NOT canonical First Memory)

| Data | Contains | Rule |
|---|---|---|
| `state.db` (+ `sessions/` transcripts) | console turns | `session_reset idle 24h`, then pruned after 7 days. **F8 finding**: Hermes prunes only when the gateway starts, so the daily `hermes-gateway-dev-retention.timer` runs `sessions prune --older-than 7 --include-archived --include-pinned`. |
| `logs/lilith-router-decisions.log` | one JSON line per turn with a message preview of 60 characters or less | moved out of the RO code directory. Rotated daily (logrotate, copytruncate) and deleted after 7 days. |
| `logs/*.log` (Hermes, 5 MB × 3) | warnings and errors, possible previews | the same daily rotation and 7-day age-out |
| journald namespace `hermes-gateway-dev` | gateway stdout/stderr | `MaxRetentionSec=7day`, `SystemMaxUse=200M`. Host journald is untouched. |
| `/var/backups/hermes-gateway-dev/pre-*` | HH tar + **Core API DB copies** (career data) | root 0700. Owner purge after acceptance (D-7). |
| `rollback-*` quarantine | anything Hermes wrote | root 0700. Owner review, then purge. |

- Nothing from Hermes is admitted to First Memory: no capture (`/os/conversation/evidence` stays 403), no
  `lilith_memory` import, and canonical LTM is off.
- **Gap to know:** the L18_V2 FORGET path (F4) covers the capture DB, **not** Hermes `state.db`. Until that changes, the only
  erasure for DEV console text is retention, R-2 quarantine or a purge. Use synthetic text on the DEV console.

## 9. Owner decisions required

| # | Decision | Recommendation |
|---|---|---|
| **D-0** | Authorize Phase A install (G-0…G-10) of package `4e1167bb…` on lilith-dev-01 | — |
| **D-1** | DEV model provider + model (independent DEV credential, spend-capped), authorized separately as Phase B | API-key provider with a provider-side cap; Router V2 stays shadow |
| D-2 | Service identity: `lilith` vs a dedicated account | `lilith`: the Core API relay reads `$HH/.env`, and `/etc/passwd`/`group` stay unchanged |
| D-3 | Accept the F8 config deltas vs F7: slash gating, tirith off, decisions `log_path`, logging caps, cron pin | accept (all tested) |
| D-4 | `SOUL.md`: Hermes seeds its default persona at first start (lilith-writable) vs a DEV persona file | default for Phase A; decide before Phase B. Never PROD `SOUL.md`. |
| D-5 | Optional GCE disk snapshot before G-3 (whole-host rollback is still NOT ESTABLISHED per PR-2) | optional. F8 is additive and R-2 is tested. |
| D-6 | Enable the gateway at boot after acceptance | not until accepted |
| D-7 | Backup / quarantine purge timing | purge after acceptance + 14 days |

## 10. Installation runbook (Phase A; every step needs D-0; stop on any FAIL)

`G` = gcloud (`…\google-cloud-sdk\bin\gcloud.cmd`). Every SSH command targets **lilith-dev-01 only**:
`--zone=asia-southeast1-b --project=lilith-agent-260823-27389 --tunnel-through-iap`.
Pass multi-line scripts as gzip+base64 in `--command` (no stdin: Windows plink injects `y`). Treat rc `0xC0000005` as
the known local plink crash: never accept that output, re-read instead.

**G-0 Authorization:** the owner records D-0 (+ D-2…D-7) and the package hash `4e1167bb…cac7`.

**G-1 Baseline + backup:**
- Run the established DR-5 query-only proof. Expect EQUAL to the current accepted baseline.
- Optionally, take the authority host observation (`observe_authority_dev_host.py`, read-only).
- After G-2 has extracted the package, run `sudo bash bin/backup_pre_install.sh`. Expect `F8_BACKUP_DONE /var/backups/hermes-gateway-dev/pre-<ts>`, holding:
  - the HH tar + listing;
  - online copies of the Core API DBs;
  - `services.baseline` (PIDs/NRestarts of the four services), `listen.baseline`, `etc.baseline`.

**G-2 Transfer + verify:**
- `G compute scp package/hermes-gateway-dev-f293e72-f8r1.tar.gz* lilith-dev-01:/var/tmp/ …`
- On the host: `sudo install -d -m 0700 /var/tmp/f8`, move the files in, then:
  - `sha256sum -c hermes-gateway-dev-f293e72-f8r1.tar.gz.sha256` → OK;
  - `tar -xzf`, then `cd hermes-gateway-dev-f293e72-f8r1 && sha256sum --quiet -c MANIFEST.sha256` → silent.
  - Free space must stay at least 2 GiB after extraction (package 152 MiB plus 365 MiB extracted).

**G-3 Install (staged only):**
- `sudo bash bin/install.sh`. Expect `F8_INSTALL_STAGED f293e72-f8r1`; the only FAIL line allowed is `MISSING …/.env`.
- It installs offline with `--require-hashes`, checks that `INSTALLED-DISTS` equals `EXPECTED-DISTS` (61), runs the import check and writes `RELEASE.sha256`.
- It creates no token, enables nothing and starts nothing.

**G-4 F7 suite on the DEV host** (as `lilith` in a throwaway dir, F7 config):
```
B=$(sudo mktemp -d /var/tmp/f8-g4-XXXXXX); R=/opt/hermes-gateway-dev/current; P=<extracted pkg>
sudo ln -s $R/src $B/hermes-agent; sudo mkdir $B/hermes-home-dev $B/tests
sudo cp -a $P/home/lilith_router $P/home/plugins $B/hermes-home-dev/
sudo cp $P/tests/f7-home/config.yaml $B/hermes-home-dev/; sudo cp $P/tests/f7-home/router.yaml $B/hermes-home-dev/lilith_router/
sudo cp $P/tests/test_f7_offline.py $B/tests/; sudo chown -R lilith:lilith $B; sudo chmod 700 $B
sudo runuser -u lilith -- env -i PATH=/usr/bin:/bin HOME=$B PYTHONUNBUFFERED=1 $R/venv/bin/python -B $B/tests/test_f7_offline.py
sudo rm -rf $B
```
Expect `Ran 19 tests … OK` (Linux simulation: 19/19).

**G-5 DEV console token + full verify:**
- `sudo bash bin/provision_console_token.sh` → `F8_TOKEN_PROVISIONED sha256_prefix=…` (record the prefix only).
- `sudo /opt/hermes-gateway-dev/current/venv/bin/python -I -B /opt/hermes-gateway-dev/current/bin/verify_release.py --full`
  → `F8_VERIFY_PASS full f293e72-f8r1`.

**G-6 Start + health:**
- `sudo systemctl start hermes-gateway-dev`, then about 20 s later check:
  - `systemctl show hermes-gateway-dev -p ActiveState,SubState,NRestarts,MemoryCurrent` = active/running/0, memory below 450 MB;
  - `ss -Hltnup | grep hermes` shows exactly one listener, `127.0.0.1:9901`;
  - `journalctl --namespace=hermes-gateway-dev -u hermes-gateway-dev` has `F8_VERIFY_PASS pre-start` and no Traceback. Two warnings are expected: slack-platform/aiohttp and "No env user allowlists".
- Then `sudo systemctl enable --now hermes-gateway-dev-retention.timer`.

**G-7 Synthetic console tests:** `sudo /opt/hermes-gateway-dev/current/venv/bin/python -I -B /opt/hermes-gateway-dev/current/bin/smoke_console.py --phase A --core-api`

| Check | Expected |
|---|---|
| S1 | health 200 |
| S2 | missing or wrong token → 401 |
| S3 | 70 KiB → 413 |
| S4 | bad JSON → 400 |
| S5 | turn → "⚠️ Provider authentication failed…" with no network |
| S6 | 9 slash commands not executed; `config.yaml` unchanged |
| S7 | 9901 loopback only |
| S8 | no non-loopback connections |
| S9 | same PID |
| S10 | Core API `/os/conversation` relays (was 502) |
| S11 | `/os/conversation/evidence` → 403 (capture inactive) |

Pass line: `F8_SMOKE_PASS phase=A 21/21`.

**G-8 Retention dry check:** `sudo systemctl start hermes-gateway-dev-retention.service`. Result=success; the journal says "No sessions match".

**G-9 Post-install equality:**
- The four existing services show the same MainPID / NRestarts / ExecMainStartTimestamp as `services.baseline`.
- `listen.baseline` plus exactly `127.0.0.1:9901`.
- `etc.baseline` unchanged, apart from the new `hermes-gateway-dev*` unit files.
- DR-5 query-only proof EQUAL. Optional authority observation: the IDENTICAL sections are unchanged.
- From the laptop over the existing IAP tunnel (`start-iap-tunnel lilith-dev-01 8765 --local-host-port=localhost:18765`):
  `/system/status` is still served (the tunnel route is preserved).

**G-10 UI (no code change):**
- Run the existing local UI against DEV with process env `LILITH_API_URL=http://127.0.0.1:18765` and the capture token cleared, as in `lilith-os-devui`.
- One Command Center message must show the provider-failure reply. No visual or functional change to the Next.js UI.

Then **stop for owner acceptance**. Phase B (D-1) is a separate package revision and authorization.

## 11. Rollback (tested twice in the simulation)

- **R-1 stop:** `sudo bash bin/rollback.sh stop`. Stops and disables the gateway + timer and checks that 9901 is closed. The Core API
  console returns to 502 exactly as before. No other unit is touched.
- **R-2 remove:** `sudo bash bin/rollback.sh remove`. R-1, then **moves (never deletes)** every F8 artifact to
  `/var/backups/hermes-gateway-dev/rollback-<ts>/` (root 0700):
  - the units, the journald namespace config and journal, and `/etc/hermes-gateway-dev`;
  - `/opt/hermes-gateway-dev`;
  - everything in HERMES_HOME except the pre-existing `memories/`.

  It then runs `daemon-reload` and diffs HERMES_HOME against the G-1 listing (simulation: `HERMES_HOME listing == G-1 backup`).
- **R-3 token rotation:** R-1, move `.env` to quarantine, G-5, start.
- Re-run G-9 after any rollback: services, sockets and DR-5 must equal the baseline.
- If a Core API DB were ever damaged (F8 never writes to it), the G-1 online copies are the restore source. That restore is a
  separate, owner-authorized operation.

## 12. Blockers and risks

- **No blocker for Phase A** beyond the owner's authorization (D-0).
- **Phase B is blocked on D-1:** a provider credential plus package revision `f8r2`.
- Any cognitive lane is blocked on the Stage 2 `world_context` export. The stub is not a World Model, and the gate refuses
  start unless every lane is off.
- Owner recording stays blocked: no live owner authentication exists (F5).
- Hermes `state.db` is outside FORGET coverage (section 8).
- Residuals:
  - the Core API shares uid `lilith` and HERMES_HOME (`.env` readable by design, so it can relay);
  - unattended-upgrades may restart the gateway through needrestart;
  - e2-small headroom is about 1.4 GB with no swap (the caps above protect the other services);
  - the 152 MiB IAP scp may hit the known plink crash, which the hash check catches.
