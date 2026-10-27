#!/usr/bin/env bash
# R-1 (runbook stop condition after G6_FAIL): stop gateway + gate + timer. Then read-only parity: observation vs G-1, DR-5.
set -u
[[ $(hostname) == lilith-dev-01 ]] || { echo "WRONG HOST"; exit 1; }
R=/opt/hermes-gateway-dev/current; P=/var/tmp/f8/hermes-gateway-dev-f293e72-f8r4; B=/var/backups/hermes-gateway-dev
{
echo "== pre-stop budget: $(bash $R/bin/gate_budget.sh show)"
journalctl --namespace=hermes-gateway-dev -u hermes-provider-gate-dev -o cat --no-pager | grep -c FORWARDED | sed 's/^/gate FORWARDED lines: /'
echo "== R-1"
bash $R/bin/rollback.sh stop
for u in hermes-gateway-dev hermes-provider-gate-dev hermes-gateway-dev-retention.timer lilith-os-api-dev lilith-memory-broker lilith-authority-dev lilith-recovery-witness; do
  printf '%-36s %s\n' $u "$(for k in ActiveState SubState MainPID NRestarts InvocationID; do systemctl show $u -p $k --value; done | paste -sd' ')"; done
echo "listeners 9901/9911: [$(ss -Hltn | awk '{print $4}' | grep -E ':(9901|9911)$' | paste -sd' ')]"
echo "ledger: $(cat /var/lib/private/hermes-provider-gate-dev/ledger.log | cut -c1-80)"
echo "== parity"
G1=$(ls -d $B/upgrade-pre-* | tail -1)
bash $P/bin/observe_host.sh $B/r1-stop >/dev/null; bash $P/bin/compare_observations.sh $G1/observation $B/r1-stop
bash $P/bin/dr5_check.sh $B/dr5-f8r4-r1.txt | tail -1
echo "core api health: $(curl -s -m 5 http://127.0.0.1:8765/health)"
} > $B/R-1-after-G6.txt 2>&1
cat $B/R-1-after-G6.txt; echo "OUT_SHA $(sha256sum < $B/R-1-after-G6.txt | cut -c1-64)"
