# LILITH private web preview: hosting package (templates)

Status: **templates only**. Nothing here is installed by CI or by any deployment workflow. Provisioning the web VM, the Cloudflare Tunnel and the Access application requires separate owner authorization.

## Architecture
```
owner browser ── Cloudflare Access (owner email only)
                   │ Cloudflare Tunnel (outbound from the web VM; no inbound ports)
                   ▼
web VM (no external IP)
  cloudflared ── one hostname → http://127.0.0.1:3000, everything else → 404
  lilith-web.service (user lilith-web) ── Next.js standalone on 127.0.0.1:3000
        │  H1: proxy.ts + per-route Cloudflare Access JWT checks
        ▼  private network only, read/write tokens enforced
Core API VM: <internal address>:8765 (never in tunnel ingress)
```
The web server must **not** run on the Core API VM. A loopback caller there is treated as the trusted on-host router (`LILITH_OS_TRUST_LOOPBACK`).

## Files
| File | Installs as |
|---|---|
| `lilith-web.service` | `/etc/systemd/system/lilith-web.service`: hardened, unprivileged, 127.0.0.1:3000, startup check |
| `healthcheck.sh` | `/opt/lilith-web/bin/healthcheck.sh` (0755): "up and enforcing auth"; exit codes documented in the file |
| `lilith-web-health.service`, `lilith-web-health.timer` | Every 5 minutes. Restarts the server when it is not answering, and **stops** it if it ever serves without authentication. |
| `cloudflared.yml.template` | `/etc/cloudflared/config.yml`: one hostname plus a 404 catch-all, with `warp-routing` disabled |
| `lilith-web.env.template` | `/etc/lilith-web/env` (root:lilith-web, 0640): server-only secrets and settings |

## Build and package (release environment: a repository checkout)
```bash
git lfs pull                                          # the avatar VRM is a Git LFS object
npm ci && npm run build && npm run package:web      # -> dist/lilith-web
node scripts/check-web-readiness.mjs --artifact dist/lilith-web --unit deploy/web/lilith-web.service
```
Packaging refuses a Git LFS pointer in place of the avatar, and so does the readiness check on the VM.

The artifact contains:
- the standalone server and its traced runtime dependencies (not the full `node_modules`);
- `.next/static`, `public/`, and `avatar-cache/hsin-<version>.vrm.gz`, verified to decompress to the original avatar;
- an **install kit**:
  - `bin/check-readiness.mjs`, a single dependency-free file bundled at packaging time;
  - `bin/install-release.sh`, `bin/rollback.sh`, `bin/healthcheck.sh` and `bin/scan-prod-bundle.mjs`;
  - `deploy/`, with the units and templates;
  - `INSTALL.md`.

## Install, verify and roll back (web VM: the artifact only)
Follow `INSTALL.md` **inside the artifact**. The web VM needs Node.js 20+ and no repository, `npm` or development dependencies:
```bash
sudo ./bin/install-release.sh /path/to/lilith-web
sudo /usr/bin/node /opt/lilith-web/current/bin/check-readiness.mjs --artifact /opt/lilith-web/current \
  --env /etc/lilith-web/env --unit /etc/systemd/system/lilith-web.service --cloudflared /etc/cloudflared/config.yml
sudo /opt/lilith-web/current/bin/rollback.sh
```
`install-release.sh` runs the readiness check on the new release **before** switching, switches `/opt/lilith-web/current` atomically, and rolls back automatically if the health check fails. Nothing on the Core API or DEV/PROD changes.

CI exercises this exact procedure on every PR: `scripts/e2e-web-release.sh` runs against the packaged artifact on an ephemeral GitHub runner with real systemd. It is destructive to its host, so it refuses to run outside CI unless explicitly told.
