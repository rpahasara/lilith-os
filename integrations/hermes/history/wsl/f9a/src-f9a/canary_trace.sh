#!/usr/bin/env bash
# MIRROR ONLY, READ-ONLY: show the synthetic canary lines left in the last F9-A rehearsal's quarantined Hermes logs.
set -u
[[ $(hostname) != lilith-dev-01 ]] || exit 1
Q=$(ls -d /var/backups/hermes-gateway-dev/rollback-* 2>/dev/null | tail -1)
echo "quarantine=$Q"; ls -la "$Q/hermes-dev/logs" 2>&1
for f in gateway.log agent.log errors.log; do echo "== $f"; grep -n "F9A-CANARY" "$Q/hermes-dev/logs/$f" 2>/dev/null | cut -c1-300; done
echo "== all logger names in agent.log (INFO+)"; awk '{print $3, $4}' "$Q/hermes-dev/logs/agent.log" | sort | uniq -c | sort -rn | head -30
echo "== other files with the canary anywhere in quarantined HERMES_HOME"; grep -rlF "F9A-CANARY" "$Q/hermes-dev" 2>/dev/null
