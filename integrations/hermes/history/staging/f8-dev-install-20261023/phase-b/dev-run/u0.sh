#!/usr/bin/env bash
# U-0 (DEV, root, READ-ONLY except the DR-5 output file under /var/backups/hermes-gateway-dev): F8r2 identity + preconditions.
set -uo pipefail
[[ $(hostname) == lilith-dev-01 ]] || { echo "WRONG HOST"; exit 1; }
R=/opt/hermes-gateway-dev/current; P2=/var/tmp/f8/hermes-gateway-dev-f293e72-f8r2; B=/var/backups/hermes-gateway-dev
echo "date=$(date -u +%FT%TZ)"
echo "current=$(readlink $R)"
echo "F8R2_SHA=$(sha256sum < $R/RELEASE.sha256 | cut -c1-64) files=$(wc -l < $R/RELEASE.sha256)"
echo "critical=$(sha256sum < /etc/hermes-gateway-dev/critical.sha256 | cut -c1-16)"
for u in hermes-gateway-dev lilith-os-api-dev lilith-memory-broker lilith-authority-dev lilith-recovery-witness; do
  printf '%-26s %s\n' $u "$(for k in ActiveState SubState MainPID NRestarts InvocationID UnitFileState; do systemctl show $u -p $k --value; done | paste -sd' ')"; done
echo "listeners(hermes): $(ss -Hltnup | grep '"hermes"' | awk '{print $1,$5}' | paste -sd';')"
echo "9911: $(ss -Hltn 'sport = :9911' | wc -l)"
echo "gate unit: $(systemctl show hermes-provider-gate-dev -p LoadState --value)"
echo "gate paths: $(ls -d /etc/hermes-provider-gate-dev /var/lib/private/hermes-provider-gate-dev /var/lib/hermes-provider-gate-dev 2>&1 | paste -sd' ')"
echo "HH: $(ls -A /home/lilith/.hermes-dev | paste -sd' ')"
echo "provider.env: $([[ -e /etc/hermes-gateway-dev/provider.env ]] && echo PRESENT || echo ABSENT)"
echo "var/tmp/f8: $(ls -A /var/tmp/f8 | paste -sd' ')"; ls -la /var/tmp/ | grep -i hermes
echo "backups: $(ls -A $B | paste -sd' ')"
echo "free_MiB=$(df -Pm / | awk 'NR==2{print $4}') mem_available_MiB=$(free -m | awk 'NR==2{print $7}')"
echo "jobs=$(systemctl list-jobs --no-legend | wc -l) dpkg_lockers=[$(find /proc/[0-9]*/fd -lname '/var/lib/dpkg/lock*' 2>/dev/null | cut -d/ -f3 | sort -u | paste -sd' ')]"
for t in apt-daily.timer apt-daily-upgrade.timer; do echo "$t next=$(systemctl show $t -p NextElapseUSecRealtime --value)"; done
pending=$(systemctl list-units --all --no-legend --plain | awk '{print $1}' | while read -r u; do [[ $(systemctl show "$u" -p NeedDaemonReload --value 2>/dev/null) == yes ]] && echo "$u"; done | paste -sd' ')
echo "units_pending_reload=[${pending}]"
echo "core api health: $(curl -s -m 5 http://127.0.0.1:8765/health)"
echo "--- DR-5 (f8r2 tooling)"
bash $P2/bin/dr5_check.sh $B/dr5-f8r4-u0.txt | tail -3
echo U0_DONE
