#!/usr/bin/env bash
# A3 (owner-approved): preserve Router V2 / gate / ledger evidence (root-only copies, synthetic content only), then G-8
# retention oneshot, then G-9 observation vs G-1 + DR-5 + verify + service parity. NO provider call.
set -uo pipefail
[[ $(hostname) == lilith-dev-01 ]] || { echo "WRONG HOST"; exit 1; }
R=/opt/hermes-gateway-dev/current; P=/var/tmp/f8/hermes-gateway-dev-f293e72-f8r4; B=/var/backups/hermes-gateway-dev
HH=/home/lilith/.hermes-dev; L=/var/lib/private/hermes-provider-gate-dev/ledger.log; DEC=$HH/logs/lilith-router-decisions.log
E=$B/f8r4-evidence; OUT=$B/A3.txt
main() {
  echo "== A3 evidence $(date -u +%FT%TZ)"
  [[ ! -e $E ]] || { echo "A3_FAIL $E exists"; return 1; }
  install -d -o root -g root -m 0700 $E
  cp -p $DEC $E/lilith-router-decisions.log; cp -p $L $E/gate-ledger.log
  journalctl --namespace=hermes-gateway-dev -u hermes-provider-gate-dev -o short-iso --no-pager | grep 'F8_GATE' > $E/gate-journal.txt
  chmod 0600 $E/*; (cd $E && sha256sum lilith-router-decisions.log gate-ledger.log gate-journal.txt > SHA256SUMS && cat SHA256SUMS)
  echo "decisions=$(wc -l < $E/lilith-router-decisions.log) forwarded=$(grep -c '"decision": "FORWARDED"' $E/gate-journal.txt) R=$(grep -c '^R ' $E/gate-ledger.log)"
  local dec0; dec0=$(sha256sum < $DEC)
  echo "== G-8"
  systemctl start hermes-gateway-dev-retention.service; echo "start_rc=$?"
  local res; res=$(systemctl show hermes-gateway-dev-retention.service -p Result --value)
  echo "retention: $(systemctl show hermes-gateway-dev-retention.service -p Result,ExecMainStatus,ActiveState --value | paste -sd' ')"
  journalctl --namespace=hermes-gateway-dev -u hermes-gateway-dev-retention --no-pager -n 4 -o cat | cut -c1-170
  echo "timer: $(systemctl is-active hermes-gateway-dev-retention.timer) next=$(systemctl show hermes-gateway-dev-retention.timer -p NextElapseUSecRealtime --value)"
  [[ $(sha256sum < $DEC) == "$dec0" ]] && echo "decisions log unchanged by retention" || echo "NOTE decisions log changed by retention (evidence copy kept)"
  echo "== G-9"
  local G1; G1=$(ls -d $B/upgrade-pre-* | tail -1)
  bash $P/bin/observe_host.sh $B/a3-post >/dev/null; bash $P/bin/compare_observations.sh $G1/observation $B/a3-post; local orc=$?
  bash $P/bin/dr5_check.sh $B/dr5-f8r4-a3.txt > $B/dr5-f8r4-a3.summary 2>&1; local drc=$?; tail -1 $B/dr5-f8r4-a3.summary
  $R/venv/bin/python -I -B $R/bin/verify_release.py --full; local vrc=$?
  echo "core api health: $(curl -s -m 5 http://127.0.0.1:8765/health)"
  echo "budget: $(bash $R/bin/gate_budget.sh show)"
  for u in hermes-gateway-dev hermes-provider-gate-dev lilith-os-api-dev lilith-memory-broker lilith-authority-dev lilith-recovery-witness; do
    printf '%-26s %s\n' $u "$(for k in ActiveState SubState MainPID NRestarts InvocationID; do systemctl show $u -p $k --value; done | paste -sd' ')"; done
  echo "gateway non-loopback established: $(ss -Htnp state established | grep "pid=$(systemctl show -p MainPID --value hermes-gateway-dev)," | grep -vc 127.0.0.1)"
  [[ $res == success && $orc -eq 0 && $drc -eq 0 && $vrc -eq 0 ]] && echo A3_PASS || { echo A3_FAIL; return 1; }
}
main > $OUT 2>&1; echo "main_rc=$?" >> $OUT
cat $OUT; echo "OUT_SHA $(sha256sum < $OUT | cut -c1-64)"
