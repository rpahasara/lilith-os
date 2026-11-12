# Installing a LILITH web release (from the artifact only)

This file ships inside every release artifact (`dist/lilith-web/INSTALL.md`). Everything below uses **only** the artifact. The web VM needs no repository checkout, no `npm` and no development dependencies.

## Host prerequisites (web VM, Debian/Ubuntu)
- Node.js **20+** at `/usr/bin/node` (for example the distribution or NodeSource package). `curl`, `ss` (iproute2) and systemd **254+** (Ubuntu 24.04 or newer; needed so the tunnel returns after an automatic restart).
- A **separate VM** from the Core API, which is reachable on its **private** address. The web server must never run on the Core API host.
- `/etc/lilith-web/env`, created by the owner from `deploy/lilith-web.env.template` with real values. The install script fixes its owner and mode (`root:lilith-web`, `0640`). It never creates or rotates secrets.
- Optional for the readiness check: `/etc/cloudflared/config.yml`, created from `deploy/cloudflared.yml.template`.

## Install or upgrade
```bash
tar -xzf lilith-web-<sha>.tar.gz -C /tmp           # or any transfer method
sudo /tmp/lilith-web/bin/install-release.sh /tmp/lilith-web
```
The script:
1. Checks the artifact, the Node version and that the env file exists.
2. Creates the unprivileged `lilith-web` system user if it is missing.
3. Copies the release to `/opt/lilith-web/releases/<time>-<sha>` (root-owned, not writable by the service).
4. Installs `lilith-web.service`, the health service and timer, `/opt/lilith-web/bin/healthcheck.sh`, and the Cloudflare Tunnel binding `/etc/systemd/system/cloudflared.service.d/10-lilith-web.conf`.
5. Runs `bin/check-readiness.mjs` against the **new** release, the env file, the unit and the tunnel config, **before** anything switches. A failure removes the new release and leaves the running one untouched.
6. Atomically points `/opt/lilith-web/current` at the new release, installs its startup gate as `/opt/lilith-web/bin/check-readiness.mjs`, and restarts the service.
7. Requires the health check to pass: answering, authentication enforced, loopback only. If it fails, it switches back to the previous release automatically.

## Startup security gate (W-SEC-1)
The service can never serve unauthenticated, including during startup, restarts and configuration mistakes:
- **Before the server binds:** `ExecStartPre` runs `check-readiness.mjs --env /etc/lilith-web/env --startup`. If `LILITH_HOSTED` is not `1`, or any hosted setting is missing or invalid, the check fails. systemd then never runs the server, and nothing listens on port 3000, on every automatic restart too.
- **Hosted mode is required by the unit itself:** `ExecStart=/usr/bin/env LILITH_REQUIRE_HOSTED=1 …`. The env file cannot override it, and it must not contain `LILITH_REQUIRE_HOSTED`. If the gate is ever bypassed, every page, API, static asset and the avatar answer `503`.
- **The tunnel follows the verified service:** `cloudflared` requires, binds to and starts after `lilith-web`. It stops whenever the web service stops, fails or crashes, and starts only after the startup gate and the authentication health check pass.

## Verify at any time
```bash
sudo /usr/bin/node /opt/lilith-web/current/bin/check-readiness.mjs \
  --artifact /opt/lilith-web/current --env /etc/lilith-web/env \
  --unit /etc/systemd/system/lilith-web.service --cloudflared /etc/cloudflared/config.yml
/opt/lilith-web/bin/healthcheck.sh     # 0 healthy; 2 misconfigured; 3 serving without auth (CRITICAL)
```

## Roll back
```bash
sudo /opt/lilith-web/current/bin/rollback.sh                 # to the previous release
sudo /opt/lilith-web/current/bin/rollback.sh releases/<id>   # to a specific one
```

## Recover after fixing the configuration
A misconfigured or failing service is refused at startup, and repeated failures trip systemd's start-rate limit. After fixing `/etc/lilith-web/env`, clear the failed state, then restart:
```bash
sudo systemctl reset-failed lilith-web.service && sudo systemctl restart lilith-web.service
/opt/lilith-web/bin/healthcheck.sh
sudo systemctl start cloudflared     # re-expose deliberately; the tunnel stays down after a configuration failure
```
`journalctl -u lilith-web` shows the gate's `FAIL` lines, which name the setting to fix (never its value).

## Stop
```bash
sudo systemctl stop cloudflared                                           # stop public access only
sudo systemctl disable --now lilith-web-health.timer lilith-web.service   # stop the web service (also stops the tunnel)
```
Stopping the web VM affects only the web preview. The Core API, Hermes, memory and DEV/PROD are untouched.
