#!/usr/bin/env bash
# Final post-G-10 check (DEV, read-only except evidence under /var/backups/hermes-gateway-dev/final).
set -u
[[ $(hostname) == lilith-dev-01 ]] || { echo "WRONG HOST"; exit 1; }
B=/var/backups/hermes-gateway-dev; P=/var/tmp/f8/hermes-gateway-dev-f293e72-f8r2; HH=/home/lilith/.hermes-dev
PRE=$(ls -d $B/pre-* | tail -1)
{
bash $P/bin/observe_host.sh $B/final >/dev/null
bash $P/bin/compare_observations.sh $PRE/observation $B/final
bash $P/bin/dr5_check.sh $B/dr5-final.txt | tail -3
curl -s -m 5 http://127.0.0.1:8765/health; echo
for u in lilith-os-api-dev lilith-memory-broker lilith-authority-dev lilith-recovery-witness hermes-gateway-dev; do
  printf '%-26s %s\n' $u "$(for k in ActiveState SubState MainPID NRestarts InvocationID; do systemctl show $u -p $k --value; done | paste -sd' ')"; done
echo "gateway mem=$(( $(systemctl show hermes-gateway-dev -p MemoryCurrent --value)/1048576 ))MiB peak=$(( $(systemctl show hermes-gateway-dev -p MemoryPeak --value)/1048576 ))MiB tasks=$(systemctl show hermes-gateway-dev -p TasksCurrent --value) cpu_s=$(( $(systemctl show hermes-gateway-dev -p CPUUsageNSec --value)/1000000000 )) enabled=$(systemctl is-enabled hermes-gateway-dev) timer=$(systemctl is-active hermes-gateway-dev-retention.timer)/$(systemctl is-enabled hermes-gateway-dev-retention.timer)"
echo "gateway sockets: listen=[$(ss -Hltnup | grep '"hermes"' | awk '{print $5}' | paste -sd' ')] established_nonloopback=[$(ss -Htnp state established | grep "pid=$(systemctl show -p MainPID --value hermes-gateway-dev)," | grep -vc 127.0.0.1)]"
echo "UI turn in gateway log: $(grep -c 'F8-SYNTHETIC UI check' $HH/logs/gateway.log) ; decisions log lines: $(wc -l < $HH/logs/lilith-router-decisions.log 2>/dev/null || echo 0)"
echo "router mode: $(grep -E '^(mode|cognitive_enabled|canonical_ltm_enabled):' $HH/lilith_router/router.yaml | paste -sd' ')"
echo "provider.env: $([[ -e /etc/hermes-gateway-dev/provider.env ]] && echo PRESENT || echo ABSENT); .env keys: $(cut -d= -f1 $HH/.env | paste -sd,)"
/opt/hermes-gateway-dev/current/venv/bin/python -I -B /opt/hermes-gateway-dev/current/bin/verify_release.py --pre-start
echo "host: avail=$(free -m | awk 'NR==2{print $7}')MiB disk_free=$(df -Pm / | awk 'NR==2{print $4}')MiB"
} > $B/final.txt 2>&1
cat $B/final.txt; echo "FINAL_SHA $(sha256sum < $B/final.txt | cut -c1-64)"
