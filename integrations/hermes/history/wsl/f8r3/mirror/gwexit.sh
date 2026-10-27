#!/usr/bin/env bash
for q in $(ls -d /var/backups/hermes-gateway-dev/rollback-* | tail -6); do
  f=$q/hermes-dev/logs/gateway-exit-diag.log
  [[ -s $f ]] || continue
  echo "== $q"; tail -n 25 $f | cut -c1-230
  grep -n -E 'ERROR|Traceback|exit|Exception' $q/hermes-dev/logs/gateway.log | tail -8 | cut -c1-230
done
