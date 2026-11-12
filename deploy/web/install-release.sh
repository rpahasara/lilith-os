#!/usr/bin/env bash
# Install a LILITH web release from its artifact ONLY (no repository, no dev
# dependencies). Run as root on the web VM:
#
#   sudo ./bin/install-release.sh /path/to/unpacked/lilith-web
#
# Steps: verify the artifact and host prerequisites -> copy to
# /opt/lilith-web/releases/<id> -> install units and the health check ->
# run the bundled readiness check against the NEW release BEFORE switching ->
# atomically switch /opt/lilith-web/current -> restart -> health check ->
# on any failure, switch back to the previous release automatically.
# It never creates or rotates secrets: /etc/lilith-web/env must already exist.
set -euo pipefail

BASE=/opt/lilith-web
ENV_FILE=/etc/lilith-web/env
UNITS=(lilith-web.service lilith-web-health.service lilith-web-health.timer)
die() { echo "install-release: $*" >&2; exit 1; }

[ "$(id -u)" -eq 0 ] || die "run as root"
[ $# -ge 1 ] || die "usage: install-release.sh <artifact dir>"
ART="$(cd "$1" && pwd)"
for f in server.js web-artifact.json bin/check-readiness.mjs bin/healthcheck.sh deploy/lilith-web.service; do
  [ -e "$ART/$f" ] || die "not a lilith-web artifact (missing $f)"
done
[ -x /usr/bin/node ] || die "Node.js 20+ is required at /usr/bin/node"
node_major="$(/usr/bin/node -p 'process.versions.node.split(".")[0]')"
[ "$node_major" -ge 20 ] || die "Node.js 20+ is required (found $node_major)"
[ -f "$ENV_FILE" ] || die "create $ENV_FILE from deploy/lilith-web.env.template first (root:lilith-web, 0640)"

id lilith-web >/dev/null 2>&1 || useradd --system --no-create-home --home-dir /nonexistent --shell /usr/sbin/nologin lilith-web
chown root:lilith-web "$ENV_FILE"
chmod 0640 "$ENV_FILE"

sha="$(/usr/bin/node -p 'require(process.argv[1]).gitSha || "nogit"' "$ART/web-artifact.json" | cut -c1-12)"
ID="${RELEASE_ID:-$(date -u +%Y%m%dT%H%M%SZ)-$sha}"
NEW="$BASE/releases/$ID"
[ -e "$NEW" ] && die "release $ID already exists"

install -d -m 0755 -o root -g root "$BASE" "$BASE/releases" "$BASE/bin"
cp -a "$ART" "$NEW"
chown -R root:root "$NEW"
chmod -R u+rwX,go+rX,go-w "$NEW"
install -m 0755 -o root -g root "$NEW/bin/healthcheck.sh" "$BASE/bin/healthcheck.sh"
for u in "${UNITS[@]}"; do install -m 0644 -o root -g root "$NEW/deploy/$u" "/etc/systemd/system/$u"; done

readiness=(/usr/bin/node "$NEW/bin/check-readiness.mjs" --artifact "$NEW" --env "$ENV_FILE" --unit /etc/systemd/system/lilith-web.service)
[ -f /etc/cloudflared/config.yml ] && readiness+=(--cloudflared /etc/cloudflared/config.yml)
if ! "${readiness[@]}"; then
  rm -rf "$NEW"
  die "readiness check failed; release $ID removed, current release unchanged"
fi

PREV="$(readlink "$BASE/current" 2>/dev/null || true)"
switch_to() { ln -sfn "$1" "$BASE/current.new" && mv -Tf "$BASE/current.new" "$BASE/current"; }
switch_to "releases/$ID"
[ -n "$PREV" ] && echo "$PREV" > "$BASE/previous"

systemctl daemon-reload
systemctl enable --quiet lilith-web.service lilith-web-health.timer
systemctl reset-failed lilith-web.service 2>/dev/null || true   # clear earlier failures / start-rate limit
if systemctl restart lilith-web.service && "$BASE/bin/healthcheck.sh" --wait 30; then
  systemctl start lilith-web-health.timer
  echo "install-release: release $ID is live (previous: ${PREV:-none})"
  # keep the 3 newest releases
  ls -1dt "$BASE"/releases/* | tail -n +4 | while read -r old; do [ "$(readlink -f "$BASE/current")" = "$old" ] || rm -rf "$old"; done
  exit 0
fi

echo "install-release: release $ID failed its health check; rolling back" >&2
if [ -n "$PREV" ]; then
  switch_to "$PREV"
  systemctl reset-failed lilith-web.service 2>/dev/null || true
  systemctl restart lilith-web.service && "$BASE/bin/healthcheck.sh" --wait 30 && echo "install-release: rolled back to $PREV" >&2
else
  systemctl stop lilith-web.service || true
fi
exit 1
