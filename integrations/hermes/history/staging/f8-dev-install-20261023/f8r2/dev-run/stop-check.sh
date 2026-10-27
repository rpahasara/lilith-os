#!/usr/bin/env bash
# READ-ONLY stop-point check: observation vs G-1, DR-5, Core API health. Writes only under /var/backups/hermes-gateway-dev.
set -u
[[ $(hostname) == lilith-dev-01 ]] || { echo "WRONG HOST"; exit 1; }
P=/var/tmp/f8/hermes-gateway-dev-f293e72-f8r2
PRE=$(ls -d /var/backups/hermes-gateway-dev/pre-* | tail -1)
bash $P/bin/observe_host.sh /var/backups/hermes-gateway-dev/stop-g7b >/dev/null
bash $P/bin/compare_observations.sh $PRE/observation /var/backups/hermes-gateway-dev/stop-g7b
bash $P/bin/dr5_check.sh /var/backups/hermes-gateway-dev/dr5-stop-g7b.txt | tail -2
curl -s -m 5 http://127.0.0.1:8765/health; echo
for u in lilith-os-api-dev lilith-memory-broker lilith-authority-dev lilith-recovery-witness hermes-gateway-dev; do
  printf '%-26s %s\n' $u "$(for k in ActiveState SubState MainPID NRestarts; do systemctl show $u -p $k --value; done | paste -sd' ')"; done
