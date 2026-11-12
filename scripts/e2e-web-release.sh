#!/usr/bin/env bash
# Isolated end-to-end test of a LILITH web release, using ONLY the release
# artifact and its documented installation procedure (INSTALL.md).
# Destructive to the host it runs on (creates a system user, /opt/lilith-web,
# /etc/lilith-web, systemd units): run it ONLY on an ephemeral machine, such
# as the GitHub-hosted runner in ci.yml. Requires root and systemd.
#
#   sudo bash scripts/e2e-web-release.sh dist/lilith-web
set -uo pipefail
[ "$(id -u)" -eq 0 ] || { echo "run as root on an ephemeral host"; exit 2; }
[ -n "${CI:-}" ] || [ "${LILITH_E2E_EPHEMERAL:-}" = "1" ] || { echo "refusing: set CI or LILITH_E2E_EPHEMERAL=1 on a throwaway host"; exit 2; }
SRC="$(cd "$1" && pwd)"
BASE=/opt/lilith-web
fails=0
ok()   { echo "E2E PASS  $*"; }
bad()  { echo "E2E FAIL  $*"; fails=$((fails + 1)); }
expect() { local name="$1"; shift; if "$@"; then ok "$name"; else bad "$name"; fi; }
status() { curl -s -o /tmp/e2e-body -w '%{http_code}' "$@"; }
body_has() { grep -q "$1" /tmp/e2e-body; }

# 1. Transfer the artifact exactly as an operator would (a tarball), unpack elsewhere.
tar -C "$(dirname "$SRC")" -czf /tmp/lilith-web.tgz "$(basename "$SRC")"
rm -rf /tmp/xfer && mkdir -p /tmp/xfer && tar -xzf /tmp/lilith-web.tgz -C /tmp/xfer
ART=/tmp/xfer/$(basename "$SRC")
expect "artifact carries its install kit" test -f "$ART/INSTALL.md" -a -f "$ART/bin/install-release.sh" -a -f "$ART/bin/check-readiness.mjs"
expect "artifact has no full node_modules (no typescript/esbuild)" test ! -e "$ART/node_modules/typescript" -a ! -e "$ART/node_modules/esbuild"

# Host prerequisite from INSTALL.md: Node 20+ at /usr/bin/node (test accommodation for the runner's toolcache Node).
[ -x /usr/bin/node ] || ln -s "$(command -v node)" /usr/bin/node

# 2. Owner-provided configuration (as the owner would create it; fake values, no real secrets).
install -d -m 0755 /etc/lilith-web /etc/cloudflared
cat > /etc/lilith-web/env <<EOF
LILITH_HOSTED=1
LILITH_ACCESS_TEAM_DOMAIN=lilith-e2e.cloudflareaccess.com
LILITH_ACCESS_AUD=$(printf 'a%.0s' $(seq 64))
LILITH_OWNER_EMAILS=owner@example.com
LILITH_PUBLIC_ORIGIN=https://os.example.com
LILITH_API_URL=http://10.255.255.1:8765
LILITH_OS_READ_TOKEN=$(printf 'r%.0s' $(seq 40))
LILITH_OS_WRITE_TOKEN=$(printf 'w%.0s' $(seq 40))
EOF
chmod 0600 /etc/lilith-web/env
sed -e 's/<TUNNEL_ID>/0f1e2d3c-4b5a-6978-8796-a5b4c3d2e1f0/g' -e 's/<PUBLIC_HOSTNAME>/os.example.com/g' \
  "$ART/deploy/cloudflared.yml.template" > /etc/cloudflared/config.yml

# 3. Install release 1 with the documented command.
t0=$(date +%s)
expect "install-release.sh installs release 1" env RELEASE_ID=e2e-1 "$ART/bin/install-release.sh" "$ART"
echo "E2E INFO  install + start + health: $(( $(date +%s) - t0 ))s"
expect "current -> releases/e2e-1" test "$(readlink $BASE/current)" = "releases/e2e-1"
expect "service is active" systemctl is-active --quiet lilith-web.service
expect "health timer is active" systemctl is-active --quiet lilith-web-health.timer
pid=$(systemctl show -p MainPID --value lilith-web.service)
expect "server runs as the unprivileged lilith-web user" test "$(ps -o user= -p "$pid" | tr -d ' ')" = "lilith-web"
expect "server holds no capabilities" test "$(grep CapEff /proc/$pid/status | awk '{print $2}')" = "0000000000000000"
expect "env file fixed to root:lilith-web 0640" test "$(stat -c '%U:%G %a' /etc/lilith-web/env)" = "root:lilith-web 640"
expect "release files are not writable by the service user" test "$(stat -c '%U' $BASE/releases/e2e-1/server.js)" = "root"
listeners=$(ss -ltnH | awk '{print $4}' | grep -E ':3000$' | sort -u | tr '\n' ' ')
expect "listens only on 127.0.0.1:3000 (got: $listeners)" test "$listeners" = "127.0.0.1:3000 "

# 4. Authentication enforced on every path (no Cloudflare in front: direct-origin access).
for path in / /assets/avatars/Hsin_FINAL_EXPORT_WORKING_FIXED.vrm "/avatar/hsin-$(node -p "require('$ART/web-artifact.json').avatar.version").vrm" /api/lilith/system/status; do
  expect "direct-origin GET $path -> 401 EDGE_AUTH_REQUIRED" bash -c "[ \"\$(curl -s -o /tmp/e2e-body -w '%{http_code}' http://127.0.0.1:3000$path)\" = 401 ] && grep -q EDGE_AUTH_REQUIRED /tmp/e2e-body"
done
expect "forged/malformed Access token -> 401" test "$(status -H 'Cf-Access-Jwt-Assertion: a.b.c' http://127.0.0.1:3000/)" = "401"
expect "cross-origin POST -> 401 (authentication first)" test "$(status -X POST -H 'Origin: https://evil.example.com' -H 'Content-Type: application/json' -d '{}' http://127.0.0.1:3000/api/lilith/conversation)" = "401"
expect "security headers present (CSP frame-ancestors, nosniff)" bash -c "curl -sI http://127.0.0.1:3000/ | grep -qi \"frame-ancestors 'none'\" && curl -sI http://127.0.0.1:3000/ | grep -qi 'x-content-type-options: nosniff'"
expect "health check: healthy" "$BASE/bin/healthcheck.sh"
expect "bundled readiness check passes on the installed release" /usr/bin/node "$BASE/current/bin/check-readiness.mjs" \
  --artifact "$BASE/current" --env /etc/lilith-web/env --unit /etc/systemd/system/lilith-web.service --cloudflared /etc/cloudflared/config.yml
expect "systemd-analyze verify accepts the units" systemd-analyze verify /etc/systemd/system/lilith-web.service /etc/systemd/system/lilith-web-health.service /etc/systemd/system/lilith-web-health.timer
echo "E2E INFO  $(systemd-analyze security lilith-web.service --no-pager 2>/dev/null | tail -1)"
echo "E2E INFO  memory: $(systemctl show -p MemoryCurrent --value lilith-web.service) bytes current, peak $(systemctl show -p MemoryPeak --value lilith-web.service 2>/dev/null) bytes"

# 5. Upgrade to release 2, then roll back.
expect "install-release.sh installs release 2" env RELEASE_ID=e2e-2 "$ART/bin/install-release.sh" "$ART"
expect "current -> releases/e2e-2, previous recorded" test "$(readlink $BASE/current)" = "releases/e2e-2" -a "$(cat $BASE/previous)" = "releases/e2e-1"
t0=$(date +%s)
expect "rollback.sh returns to release 1 and is healthy" "$BASE/current/bin/rollback.sh"
echo "E2E INFO  rollback restart + health: $(( $(date +%s) - t0 ))s"
expect "current -> releases/e2e-1 after rollback" test "$(readlink $BASE/current)" = "releases/e2e-1"

# 6. A release that fails readiness is refused and leaves the live release untouched.
rm -rf /tmp/badrel && cp -a "$ART" /tmp/badrel && rm -f /tmp/badrel/bin/scan-prod-bundle.mjs
if RELEASE_ID=e2e-bad "$ART/bin/install-release.sh" /tmp/badrel >/dev/null 2>&1; then bad "a broken release is refused"; else ok "a broken release is refused"; fi
expect "refused release was removed; live release unchanged and healthy" bash -c "[ ! -e $BASE/releases/e2e-bad ] && [ \"\$(readlink $BASE/current)\" = releases/e2e-1 ] && $BASE/bin/healthcheck.sh >/dev/null"

# 7. Fail-closed behaviour of the running service.
cp /etc/lilith-web/env /tmp/env.good
sed -i '/^LILITH_ACCESS_AUD=/d' /etc/lilith-web/env
if systemctl restart lilith-web.service 2>/dev/null; then bad "misconfigured hosted auth refuses to start healthy"; else ok "misconfigured hosted auth refuses to start healthy"; fi
"$BASE/bin/healthcheck.sh" >/dev/null 2>&1; rc=$?
expect "health check reports misconfiguration (exit 2) or down (exit 1), never healthy (got $rc)" test "$rc" -eq 2 -o "$rc" -eq 1
cp /tmp/env.good /etc/lilith-web/env && sed -i 's/^LILITH_HOSTED=1/LILITH_HOSTED=0/' /etc/lilith-web/env
if systemctl restart lilith-web.service 2>/dev/null; then bad "a server that would serve WITHOUT auth fails its startup check"; else ok "a server that would serve WITHOUT auth fails its startup check"; fi
systemctl start lilith-web.service >/dev/null 2>&1 || true
"$BASE/bin/healthcheck.sh" --wait 20 >/dev/null 2>&1; rc=$?
[ "$rc" -eq 3 ] && ok "health check flags serving without auth (exit 3)" || echo "E2E INFO  unauthenticated server not running (rc $rc): startup check already refused it"
systemctl start lilith-web-health.service >/dev/null 2>&1 || true
expect "periodic health check stops a server serving without auth" bash -c "! systemctl is-active --quiet lilith-web.service"
cp /tmp/env.good /etc/lilith-web/env && chmod 0640 /etc/lilith-web/env && chown root:lilith-web /etc/lilith-web/env
expect "restored configuration starts healthy again (documented recovery: reset-failed + restart)" bash -c "systemctl reset-failed lilith-web.service; systemctl restart lilith-web.service && $BASE/bin/healthcheck.sh"

if [ "$fails" -gt 0 ]; then
  echo "E2E DIAG  ---- systemctl status / journal (failure diagnostics) ----"
  systemctl status lilith-web.service --no-pager 2>&1 | sed "s/^/E2E DIAG  /" | tail -15
  journalctl -u lilith-web.service -n 40 --no-pager 2>&1 | sed "s/^/E2E DIAG  /"
fi
echo
if [ "$fails" -eq 0 ]; then echo "E2E RESULT: PASS"; else echo "E2E RESULT: FAIL ($fails)"; fi
exit $(( fails > 0 ))
