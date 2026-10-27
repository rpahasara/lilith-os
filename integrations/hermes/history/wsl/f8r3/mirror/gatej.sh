#!/usr/bin/env bash
Q=$(ls -d /var/backups/hermes-gateway-dev/rollback-* | head -n 3 | tail -1)
for q in /var/backups/hermes-gateway-dev/rollback-*; do
  j=$(ls -d $q/*.hermes-gateway-dev 2>/dev/null) || continue
  n=$(journalctl --directory=$j -u hermes-provider-gate-dev --no-pager 2>/dev/null | grep -c -E 'credential|Failed|START')
  [[ $n -gt 0 ]] && { echo "== $q"; journalctl --directory=$j --no-pager 2>/dev/null | grep -E 'provider-gate|credential|Start request|start-limit|F8_GATE \{"decision": "START' | cut -c1-200 | head -25; break; }
done
journalctl --no-pager -u hermes-provider-gate-dev --since "-40min" | grep -E 'credential|Failed|limit|Started|Stopped' | cut -c1-200 | head -25
