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
expect "W-SEC-1 startup gate installed root-owned at a fixed path" test "$(stat -c '%U %a' $BASE/bin/check-readiness.mjs)" = "root 755"
expect "W-SEC-1 tunnel binding installed" test -f /etc/systemd/system/cloudflared.service.d/10-lilith-web.conf
expect "W-SEC-1 service runs with the hosted requirement on its command line" \
  bash -c "tr '\0' ' ' < /proc/\$(systemctl show -p MainPID --value lilith-web.service)/environ | grep -q 'LILITH_REQUIRE_HOSTED=1'"
pid=$(systemctl show -p MainPID --value lilith-web.service)
expect "server runs as the unprivileged lilith-web user" test "$(ps -o user= -p "$pid" | tr -d ' ')" = "lilith-web"
expect "server holds no capabilities" test "$(grep CapEff /proc/$pid/status | awk '{print $2}')" = "0000000000000000"
expect "env file fixed to root:lilith-web 0640" test "$(stat -c '%U:%G %a' /etc/lilith-web/env)" = "root:lilith-web 640"
expect "release files are not writable by the service user" test "$(stat -c '%U' $BASE/releases/e2e-1/server.js)" = "root"
listeners=$(ss -ltnH | awk '{print $4}' | grep -E ':3000$' | sort -u | tr '\n' ' ')
expect "listens only on 127.0.0.1:3000 (got: $listeners)" test "$listeners" = "127.0.0.1:3000 "

# 4. Authentication enforced on every path (no Cloudflare in front: direct-origin access).
CHUNK="/_next/static/chunks/$(cd "$ART/.next/static/chunks" && ls *.js | head -1)"
PATHS=(/ /assets/avatars/Hsin_FINAL_EXPORT_WORKING_FIXED.vrm "/avatar/hsin-$(node -p "require('$ART/web-artifact.json').avatar.version").vrm" /api/lilith/system/status "$CHUNK")
for path in "${PATHS[@]}"; do
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

# ---- W-SEC-1: no unauthenticated serving window (sections 7-11) ----
echo "E2E INFO  systemd $(systemctl --version | head -1 | awk '{print $2}') on $(. /etc/os-release && echo "$PRETTY_NAME")"
systemctl stop lilith-web-health.timer   # keep the periodic check from restarting the service mid-scenario (re-enabled in 11)
cp /etc/lilith-web/env /tmp/env.good
mono() { systemctl show -p "$2" --value "$1"; }
wait_for() { local t=$1; shift; local end=$(( $(date +%s) + t )); until "$@"; do [ "$(date +%s)" -ge "$end" ] && return 1; sleep 0.2; done; }
good_env() { cp /tmp/env.good /etc/lilith-web/env && chmod 0640 /etc/lilith-web/env && chown root:lilith-web /etc/lilith-web/env; }
both_up() {  # deliberate exposure: starting the tunnel starts and verifies the web service first
  systemctl reset-failed lilith-web.service cloudflared.service 2>/dev/null
  systemctl start cloudflared.service && systemctl is-active --quiet lilith-web.service && "$BASE/bin/healthcheck.sh" >/dev/null
}
tunnel_down() { ! systemctl is-active --quiet cloudflared.service; }
has_dep() { systemctl show -p "$1" --value cloudflared.service | tr ' ' '\n' | grep -qx lilith-web.service; }

# 7. The tunnel follows the verified web service (a stand-in cloudflared unit; the real binding drop-in applies).
cat > /etc/systemd/system/cloudflared.service <<'UNIT'
[Unit]
Description=cloudflared stand-in for the e2e test (the installed 10-lilith-web.conf binding applies)
[Service]
ExecStart=/usr/bin/sleep infinity
[Install]
WantedBy=multi-user.target
UNIT
systemctl daemon-reload
systemctl enable --quiet cloudflared.service   # the owner's intent to be exposed (as `cloudflared service install` does)
for d in Requires BindsTo After; do expect "tunnel binding: cloudflared $d=lilith-web.service" has_dep "$d"; done
systemctl stop cloudflared.service lilith-web.service
expect "cold start: starting the tunnel starts and verifies the web service first" both_up
web_up=$(mono lilith-web.service ActiveEnterTimestampMonotonic); cf_exec=$(mono cloudflared.service ExecMainStartTimestampMonotonic)
expect "cold start: the tunnel process started only after lilith-web passed its gate and auth health check ($web_up <= $cf_exec)" test "$web_up" -le "$cf_exec"
old=$(mono lilith-web.service MainPID); kill -9 "$old"
expect "crash: the tunnel stops with the web service" wait_for 4 tunnel_down
expect "crash recovery: the web service restarts through its gate (new process, healthy)" wait_for 40 bash -c \
  "systemctl is-active --quiet lilith-web.service && [ \"\$(systemctl show -p MainPID --value lilith-web.service)\" != $old ] && $BASE/bin/healthcheck.sh >/dev/null"
expect "crash recovery: the tunnel does not return by itself" tunnel_down
systemctl disable --quiet cloudflared.service
systemctl start lilith-web-health.service
expect "crash recovery: the health check leaves a DISABLED tunnel down (emergency stop holds)" tunnel_down
systemctl enable --quiet cloudflared.service
systemctl start lilith-web-health.service
expect "crash recovery: the health check restores an enabled tunnel once the web service is verified" wait_for 10 systemctl is-active --quiet cloudflared.service
web_up=$(mono lilith-web.service ActiveEnterTimestampMonotonic); cf_exec=$(mono cloudflared.service ExecMainStartTimestampMonotonic)
expect "crash recovery: the tunnel returned only after the new server was verified ($web_up <= $cf_exec)" test "$web_up" -le "$cf_exec"
systemctl stop lilith-web.service
expect "stopping the web service stops the tunnel" tunnel_down

# 8. Startup gate: a disabled or broken hosted setting never binds, on the restart or any automatic retry.
sample_3000() {  # every 50 ms for $1 s: record any listener on :3000 and any HTTP answer from it
  local end=$(( $(date +%s) + $1 )) c; : > /tmp/e2e-sample
  while [ "$(date +%s)" -lt "$end" ]; do
    ss -ltnH 'sport = :3000' | grep -q . && echo "BOUND" >> /tmp/e2e-sample
    c=$(curl -s -o /dev/null -m 1 -w '%{http_code}' http://127.0.0.1:3000/ 2>/dev/null); [ "$c" = "000" ] || echo "HTTP-$c" >> /tmp/e2e-sample
    sleep 0.05
  done
}
gate_case() {  # $1 label; then sed expressions (or append:<line>) applied to the good env file
  local label="$1" since e; shift
  good_env; expect "$label: starts from a healthy, exposed service" both_up
  sleep 1; since=$(date '+%Y-%m-%d %H:%M:%S')
  for e in "$@"; do case "$e" in append:*) echo "${e#append:}" >> /etc/lilith-web/env ;; *) sed -i "$e" /etc/lilith-web/env ;; esac; done
  if systemctl restart lilith-web.service >/dev/null 2>&1; then bad "$label: restart refused"; else ok "$label: restart refused"; fi
  sample_3000 12
  expect "$label: nothing listened or answered on :3000 for 12 s across the restart and automatic retries [$(sort /tmp/e2e-sample | uniq -c | tr -s ' \n' ' ')]" test ! -s /tmp/e2e-sample
  expect "$label: the server never started (no server startup output in the journal since the change; MainPID=0)" bash -c \
    "[ \"\$(journalctl -u lilith-web.service --since '$since' --no-pager | grep -cE 'Ready in|- Local:')\" = 0 ] && [ \"\$(systemctl show -p MainPID --value lilith-web.service)\" = 0 ]"
  expect "$label: automatic retries happened and were refused too (NRestarts=$(mono lilith-web.service NRestarts))" test "$(mono lilith-web.service NRestarts)" -ge 1
  expect "$label: the gate logged why" bash -c "journalctl -u lilith-web.service -n 60 --no-pager | grep -q 'NOT READY'"
  systemctl start lilith-web-health.service >/dev/null 2>&1
  expect "$label: the health check does not restore the tunnel while the gate fails" tunnel_down
  expect "$label: the tunnel was stopped" tunnel_down
  expect "$label: the tunnel cannot start while the gate fails" bash -c "! systemctl start cloudflared.service 2>/dev/null && ! ss -ltnH 'sport = :3000' | grep -q ."
  systemctl stop lilith-web.service cloudflared.service >/dev/null 2>&1
}
gate_case "LILITH_HOSTED removed" '/^LILITH_HOSTED=/d'
gate_case "LILITH_HOSTED=0" 's/^LILITH_HOSTED=1/LILITH_HOSTED=0/'
gate_case "Access AUD missing" '/^LILITH_ACCESS_AUD=/d'
gate_case "env file disables hosting and tries to lift the requirement" 's/^LILITH_HOSTED=1/LILITH_HOSTED=0/' 'append:LILITH_REQUIRE_HOSTED=0'

# 9. Defence in depth: with the gate removed by a unit edit, the unit's own hosted requirement still refuses everything.
refuse_all() {  # $1 base URL, $2 label: every path and a POST answer 503 HOSTED_AUTH_MISCONFIGURED; zero 200s
  local p c n200=0 failed=""
  for p in "${PATHS[@]}"; do
    c=$(curl -s -o /tmp/e2e-body -w '%{http_code}' "$1$p"); [ "$c" = 200 ] && n200=$((n200 + 1))
    { [ "$c" = 503 ] && grep -q HOSTED_AUTH_MISCONFIGURED /tmp/e2e-body; } || failed+=" $p=$c"
  done
  c=$(curl -s -o /tmp/e2e-body -w '%{http_code}' -X POST -H "Origin: $1" -H 'Content-Type: application/json' -d '{"message":"hi"}' "$1/api/lilith/conversation")
  [ "$c" = 503 ] || failed+=" POST=$c"
  expect "$2: page, API, avatar, public file, static chunk and POST all 503 (200s: $n200)${failed:+ unexpected:$failed}" test -z "$failed" -a "$n200" -eq 0
}
good_env; sed -i 's/^LILITH_HOSTED=1/LILITH_HOSTED=0/' /etc/lilith-web/env; echo 'LILITH_REQUIRE_HOSTED=0' >> /etc/lilith-web/env
install -d /etc/systemd/system/lilith-web.service.d
printf '[Service]\nExecStartPre=\nExecStartPost=\n' > /etc/systemd/system/lilith-web.service.d/99-e2e-gate-removed.conf
systemctl daemon-reload; systemctl reset-failed lilith-web.service; systemctl start lilith-web.service
expect "gate removed (test-only drop-in): the server binds (precondition)" wait_for 20 curl -s -o /dev/null -m 1 http://127.0.0.1:3000/
refuse_all http://127.0.0.1:3000 "gate removed, env file disables hosting and sets LILITH_REQUIRE_HOSTED=0"
systemctl stop lilith-web.service; rm -f /etc/systemd/system/lilith-web.service.d/99-e2e-gate-removed.conf; systemctl daemon-reload

# 10. A manually started server: refuses everything with the requirement; local development is unchanged without it.
manual() {  # $1 port, then extra environment; runs the installed release as the service user
  local port=$1; shift
  (cd "$BASE/current" && exec runuser -u lilith-web -- env -i PATH=/usr/bin:/bin NODE_ENV=production HOSTNAME=127.0.0.1 PORT="$port" "$@" \
    /usr/bin/node server.js > "/tmp/e2e-manual-$port.log" 2>&1) &
  wait_for 20 curl -s -o /dev/null -m 1 "http://127.0.0.1:$port/"
}
stop_port() { kill $(ss -ltnpH "sport = :$1" | grep -o 'pid=[0-9]*' | cut -d= -f2 | sort -u) 2>/dev/null; wait_for 10 bash -c "! ss -ltnH 'sport = :$1' | grep -q ."; }
expect "manual start, LILITH_REQUIRE_HOSTED=1 and no hosted configuration (precondition: binds)" manual 3001 LILITH_REQUIRE_HOSTED=1
refuse_all http://127.0.0.1:3001 "manual start, hosted required, no configuration"
stop_port 3001
expect "manual start, LILITH_REQUIRE_HOSTED=1 and LILITH_HOSTED=0 (precondition: binds)" manual 3001 LILITH_REQUIRE_HOSTED=1 LILITH_HOSTED=0
refuse_all http://127.0.0.1:3001 "manual start, hosted required, hosting disabled"
stop_port 3001
expect "local development (no requirement, no LILITH_HOSTED): starts" manual 3002
expect "local development unchanged: the page is served (200)" test "$(curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:3002/)" = 200
stop_port 3002

# 11. Recovery after fixing the configuration (INSTALL.md): reset-failed + restart, then re-expose deliberately.
good_env
expect "restored configuration starts healthy again (reset-failed + restart)" bash -c "systemctl reset-failed lilith-web.service; systemctl restart lilith-web.service && $BASE/bin/healthcheck.sh"
expect "the tunnel does not return by itself on the restart" tunnel_down
systemctl start lilith-web-health.service
expect "re-exposure: the health check starts the enabled tunnel after the verified web service" wait_for 10 systemctl is-active --quiet cloudflared.service
expect "re-exposure: deliberate start also works and is healthy" both_up
systemctl start lilith-web-health.timer
expect "health timer re-enabled" systemctl is-active --quiet lilith-web-health.timer

if [ "$fails" -gt 0 ]; then
  echo "E2E DIAG  ---- systemctl status / journal (failure diagnostics) ----"
  systemctl status lilith-web.service cloudflared.service --no-pager 2>&1 | sed "s/^/E2E DIAG  /" | tail -30
  journalctl -u lilith-web.service -u cloudflared.service -n 60 --no-pager 2>&1 | sed "s/^/E2E DIAG  /"
fi
echo
if [ "$fails" -eq 0 ]; then echo "E2E RESULT: PASS"; else echo "E2E RESULT: FAIL ($fails)"; fi
exit $(( fails > 0 ))
