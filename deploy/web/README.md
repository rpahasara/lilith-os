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

## Build, package, verify (local; no deployment)
```bash
npm ci && npm run build && npm run package:web      # -> dist/lilith-web
node scripts/check-web-readiness.mjs --artifact dist/lilith-web \
  --unit deploy/web/lilith-web.service
# On the VM, with the filled-in files:
node scripts/check-web-readiness.mjs --artifact /opt/lilith-web/current \
  --env /etc/lilith-web/env --cloudflared /etc/cloudflared/config.yml \
  --unit /etc/systemd/system/lilith-web.service
```
The artifact contains the standalone server, its traced runtime dependencies (not the full `node_modules`), `.next/static`, `public/` and `avatar-cache/hsin-<version>.vrm.gz`. It is verified to decompress to the original avatar bytes.

## Releases and rollback
Unpack each artifact to `/opt/lilith-web/releases/<git-sha>/` and point `/opt/lilith-web/current` at it, then run `systemctl restart lilith-web`. To roll back, re-point the symlink to the previous release and restart. Nothing on the Core API or DEV/PROD changes.
