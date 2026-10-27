#!/usr/bin/env bash
# G-8 retention oneshot + G-9 post-install observation vs G-1 + DR-5 (DEV, root). Results saved under /var/backups/hermes-gateway-dev.
set -u
[[ $(hostname) == lilith-dev-01 ]] || { echo "WRONG HOST"; exit 1; }
B=/var/backups/hermes-gateway-dev; P=/var/tmp/f8/hermes-gateway-dev-f293e72-f8r2
{
echo "== G-8"
systemctl start hermes-gateway-dev-retention.service; echo "start_rc=$?"
echo "retention: $(systemctl show hermes-gateway-dev-retention.service -p Result,ExecMainStatus,ActiveState --value | paste -sd' ')"
journalctl --namespace=hermes-gateway-dev -u hermes-gateway-dev-retention --no-pager -n 4 | cut -c1-170
echo "timer: $(systemctl is-active hermes-gateway-dev-retention.timer) next=$(systemctl show hermes-gateway-dev-retention.timer -p NextElapseUSecRealtime --value)"
echo "== G-9"
PRE=$(ls -d $B/pre-* | tail -1)
bash $P/bin/observe_host.sh $B/post >/dev/null
bash $P/bin/compare_observations.sh $PRE/observation $B/post
bash $P/bin/dr5_check.sh $B/dr5-post.txt
curl -s -m 5 http://127.0.0.1:8765/health; echo
for u in lilith-os-api-dev lilith-memory-broker lilith-authority-dev lilith-recovery-witness hermes-gateway-dev; do
  printf '%-26s %s\n' $u "$(for k in ActiveState SubState MainPID NRestarts InvocationID; do systemctl show $u -p $k --value; done | paste -sd' ')"; done
echo "gateway: mem=$(( $(systemctl show hermes-gateway-dev -p MemoryCurrent --value)/1048576 ))MiB peak=$(( $(systemctl show hermes-gateway-dev -p MemoryPeak --value)/1048576 ))MiB cpu=$(systemctl show hermes-gateway-dev -p CPUUsageNSec --value)ns tasks=$(systemctl show hermes-gateway-dev -p TasksCurrent --value) enabled=$(systemctl is-enabled hermes-gateway-dev)"
echo "host: avail=$(free -m | awk 'NR==2{print $7}')MiB disk_free=$(df -Pm / | awk 'NR==2{print $4}')MiB load=$(cut -d' ' -f1-3 /proc/loadavg)"
echo "listeners(hermes): $(ss -Hltnup | grep '"hermes"' | awk '{print $1,$5}' | paste -sd';')"
echo "installed: $(readlink /opt/hermes-gateway-dev/current) RELEASE.sha256=$(sha256sum < /opt/hermes-gateway-dev/current/RELEASE.sha256 | cut -c1-16) files=$(wc -l < /opt/hermes-gateway-dev/current/RELEASE.sha256) critical=$(sha256sum < /etc/hermes-gateway-dev/critical.sha256 | cut -c1-16)"
/opt/hermes-gateway-dev/current/venv/bin/python -I -B /opt/hermes-gateway-dev/current/bin/verify_release.py --full
echo "provider.env: $([[ -e /etc/hermes-gateway-dev/provider.env ]] && echo PRESENT || echo ABSENT)"
} > $B/G-8-9.txt 2>&1
cat $B/G-8-9.txt; echo "G89_SHA $(sha256sum < $B/G-8-9.txt | cut -c1-64)"
