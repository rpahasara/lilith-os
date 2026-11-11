# Installing a LILITH web release (from the artifact only)

This file ships inside every release artifact (`dist/lilith-web/INSTALL.md`). Everything below uses **only** the artifact. The web VM needs no repository checkout, no `npm` and no development dependencies.

## Host prerequisites (web VM, Debian/Ubuntu)
- Node.js **20+** at `/usr/bin/node` (for example the distribution or NodeSource package). `curl`, `ss` (iproute2) and systemd.
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
4. Installs `lilith-web.service`, the health service and timer, and `/opt/lilith-web/bin/healthcheck.sh`.
5. Runs `bin/check-readiness.mjs` against the **new** release, the env file, the unit and the tunnel config, **before** anything switches. A failure removes the new release and leaves the running one untouched.
6. Atomically points `/opt/lilith-web/current` at the new release and restarts the service.
7. Requires the health check to pass: answering, authentication enforced, loopback only. If it fails, it switches back to the previous release automatically.

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
```

## Stop
```bash
sudo systemctl disable --now lilith-web-health.timer lilith-web.service
```
Stopping the web VM affects only the web preview. The Core API, Hermes, memory and DEV/PROD are untouched.
