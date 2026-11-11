#!/usr/bin/env bash
# LILITH web preview health check (TEMPLATE, not installed).
#
# Healthy means BOTH "the server answers on 127.0.0.1:3000" AND "it enforces
# authentication": an unauthenticated local request must get
# 401 {"error":"EDGE_AUTH_REQUIRED"}. Exit codes:
#   0 healthy
#   1 not answering (startup failure)
#   2 misconfigured (503 HOSTED_AUTH_MISCONFIGURED): fail closed, fix the env file
#   3 AUTHENTICATION NOT ENFORCED (200 without a token): the caller must stop the service
#   4 listening on something other than 127.0.0.1:3000
# Usage: healthcheck.sh [--wait SECONDS]
set -u
wait_s=0
[ "${1:-}" = "--wait" ] && wait_s="${2:-30}"
deadline=$(( $(date +%s) + wait_s ))

while :; do
  body="$(curl -s -m 5 -o - -w '\n%{http_code}' http://127.0.0.1:3000/ 2>/dev/null)"
  code="${body##*$'\n'}"
  [ -n "$code" ] && [ "$code" != "000" ] && break
  [ "$(date +%s)" -ge "$deadline" ] && { echo "lilith-web: not answering on 127.0.0.1:3000"; exit 1; }
  sleep 1
done

case "$code" in
  401) grep -q 'EDGE_AUTH_REQUIRED' <<<"$body" || { echo "lilith-web: unexpected 401 body"; exit 1; } ;;
  503) echo "lilith-web: HOSTED_AUTH_MISCONFIGURED (refusing all requests)"; exit 2 ;;
  200) echo "lilith-web: CRITICAL: served a page WITHOUT authentication"; exit 3 ;;
  *)   echo "lilith-web: unexpected status $code"; exit 1 ;;
esac

# Must listen only on loopback port 3000 (never 0.0.0.0 / a public interface).
if command -v ss >/dev/null 2>&1; then
  listeners="$(ss -ltnH 2>/dev/null | awk '{print $4}' | grep -E ':3000$' || true)"
  if [ -n "$listeners" ] && grep -vqE '^127\.0\.0\.1:3000$' <<<"$listeners"; then
    echo "lilith-web: listening beyond loopback: $listeners"; exit 4
  fi
fi
echo "lilith-web: healthy (answering, authentication enforced, loopback only)"
exit 0
