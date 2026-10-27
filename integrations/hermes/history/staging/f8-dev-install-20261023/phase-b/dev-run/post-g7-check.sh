#!/usr/bin/env bash
# READ-ONLY after the G-7 stop: every gate journal line with timestamps (no key is ever logged), ledger, smoke output,
# then parity (observation vs G-1, DR-5) and service state. No start, no provider call.
set -u
[[ $(hostname) == lilith-dev-01 ]] || { echo "WRONG HOST"; exit 1; }
P=/var/tmp/f8/hermes-gateway-dev-f293e72-f8r4; B=/var/backups/hermes-gateway-dev
OUT=$B/post-G7-check.txt
{
echo "== gate journal (all F8_GATE lines, systemd timestamps)"
journalctl --namespace=hermes-gateway-dev -u hermes-provider-gate-dev -o short-iso --no-pager | grep 'F8_GATE' | cut -c1-330
echo "== ledger"; cat /var/lib/private/hermes-provider-gate-dev/ledger.log
echo "== smoke output (killed while held)"; cat $B/G-7-smoke.txt | cut -c1-200
echo "== gateway log turns"; grep -c 'F8-SYNTHETIC' /home/lilith/.hermes-dev/logs/gateway.log 2>/dev/null
echo "== decisions"; wc -l < /home/lilith/.hermes-dev/logs/lilith-router-decisions.log
echo "== state"
for u in hermes-gateway-dev hermes-provider-gate-dev hermes-gateway-dev-retention.timer lilith-os-api-dev lilith-memory-broker lilith-authority-dev lilith-recovery-witness; do
  printf '%-36s %s\n' $u "$(for k in ActiveState SubState MainPID NRestarts InvocationID; do systemctl show $u -p $k --value; done | paste -sd' ')"; done
echo "listeners 9901/9911: [$(ss -Hltn | awk '{print $4}' | grep -E ':(9901|9911)$' | paste -sd' ')]"
echo "== parity"
G1=$(ls -d $B/upgrade-pre-* | tail -1)
bash $P/bin/observe_host.sh $B/post-g7-stop >/dev/null; bash $P/bin/compare_observations.sh $G1/observation $B/post-g7-stop
bash $P/bin/dr5_check.sh $B/dr5-f8r4-post-g7.txt | tail -1
echo "core api health: $(curl -s -m 5 http://127.0.0.1:8765/health)"
} > $OUT 2>&1
cat $OUT; echo "OUT_SHA $(sha256sum < $OUT | cut -c1-64)"
