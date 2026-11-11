#!/usr/bin/env bash
# Roll the LILITH web preview back to the previous release (or a named one).
#   sudo /opt/lilith-web/current/bin/rollback.sh [releases/<id>]
# Only the web VM changes; the Core API, DEV and PROD are untouched.
set -euo pipefail
BASE=/opt/lilith-web
die() { echo "rollback: $*" >&2; exit 1; }
[ "$(id -u)" -eq 0 ] || die "run as root"
TARGET="${1:-$(cat "$BASE/previous" 2>/dev/null || true)}"
[ -n "$TARGET" ] || die "no previous release recorded"
[ -f "$BASE/$TARGET/server.js" ] || die "$TARGET is not an installed release"
CURRENT="$(readlink "$BASE/current")"
ln -sfn "$TARGET" "$BASE/current.new" && mv -Tf "$BASE/current.new" "$BASE/current"
echo "$CURRENT" > "$BASE/previous"
systemctl restart lilith-web.service
"$BASE/bin/healthcheck.sh" --wait 30 || die "rolled back to $TARGET but it is not healthy"
echo "rollback: now serving $TARGET (previous: $CURRENT)"
