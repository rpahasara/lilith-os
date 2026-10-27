#!/usr/bin/env bash
for q in /var/backups/hermes-gateway-dev/rollback-*; do
  for j in "$q"/*.hermes-gateway-dev; do
    [[ -d $j ]] || continue
    echo "== $q"; journalctl --directory="$j" --no-pager 2>/dev/null | grep -E 'F8_VERIFY|FORBIDDEN|Failed' | cut -c1-200 | head -4
  done
done
journalctl --no-pager -u hermes-gateway-dev --since "-3h" | grep -E 'F8_|Failed|ExecStartPre' | cut -c1-200 | tail -6
systemctl list-timers apt-daily.timer apt-daily-upgrade.timer --no-pager | head -4
