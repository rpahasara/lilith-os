#!/usr/bin/env bash
# READ-ONLY re-read of the stop-point evidence saved on DEV.
set -u
B=/var/backups/hermes-gateway-dev; PRE=$(ls -d $B/pre-* | tail -1)
for s in services units sockets custody coreapi accounts; do cmp -s $PRE/observation/$s $B/stop-g7b/$s && echo "EQUAL $s" || echo "DIFF $s"; done
sha256sum < $B/dr5-stop-g7b.txt; tail -2 $B/dr5-stop-g7b.txt
for u in lilith-os-api-dev lilith-memory-broker lilith-authority-dev lilith-recovery-witness hermes-gateway-dev; do
  printf '%-26s %s\n' $u "$(for k in ActiveState MainPID NRestarts; do systemctl show $u -p $k --value; done | paste -sd' ')"; done
ls $B
