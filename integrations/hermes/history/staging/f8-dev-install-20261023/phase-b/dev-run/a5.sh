#!/usr/bin/env bash
# A5 (owner-approved): READ-ONLY final verification after the G-10 UI request (#5): gate record #5, budget 5/5 exhausted,
# ledger = A2 ledger + exactly one R/T pair, Router V2 decision for the UI session, no refused POST, key isolation,
# final observation vs G-1 + DR-5 + verify + service parity. No provider call, no restart.
set -uo pipefail
[[ $(hostname) == lilith-dev-01 ]] || { echo "WRONG HOST"; exit 1; }
R=/opt/hermes-gateway-dev/current; P=/var/tmp/f8/hermes-gateway-dev-f293e72-f8r4; B=/var/backups/hermes-gateway-dev
HH=/home/lilith/.hermes-dev; L=/var/lib/private/hermes-provider-gate-dev/ledger.log; DEC=$HH/logs/lilith-router-decisions.log
E=$B/f8r4-evidence; OUT=$B/A5.txt; UISESS=lilith-os-b4734155-e4da-4e22-a03f-4305f2bd0f3c; PY=$R/venv/bin/python
main() {
  echo "== A5 $(date -u +%FT%TZ)"
  local bud; bud=$(bash $R/bin/gate_budget.sh show); echo "budget: $bud"
  echo "== ledger"; cat $L
  local head8; head8=$(head -n 9 $L | sha256sum | cut -c1-64)
  echo "first 9 lines sha=$head8 (A2 ledger f30152d2…: $([[ $head8 == f30152d28183a67a123174c0e91572a6f2ef8b685b78cee0c8a86d59d0fe217b ]] && echo identical || echo DIFFERENT))"
  echo "R=$(grep -c '^R ' $L) RESET=$(grep -c '^RESET' $L) lines=$(wc -l < $L)"
  echo "== gate records since A3 evidence snapshot"
  journalctl --namespace=hermes-gateway-dev -u hermes-provider-gate-dev -o short-iso --no-pager | grep 'F8_GATE' > $B/a5-gate-journal.txt
  local n0; n0=$(wc -l < $E/gate-journal.txt)
  tail -n +$(( n0 + 1 )) $B/a5-gate-journal.txt | cut -c1-700
  local fw5; fw5=$(tail -n +$(( n0 + 1 )) $B/a5-gate-journal.txt | grep -c '"decision": "FORWARDED"')
  local refp; refp=$(tail -n +$(( n0 + 1 )) $B/a5-gate-journal.txt | grep '"decision": "REFUSED"' | grep -vc '"method": "GET"')
  echo "since A3: FORWARDED=$fw5 refused_non_GET=$refp; all-time FORWARDED=$(grep -c '"decision": "FORWARDED"' $B/a5-gate-journal.txt)"
  local v5; v5=$(tail -n +$(( n0 + 1 )) $B/a5-gate-journal.txt | grep '"decision": "FORWARDED"' | sed 's/^.*F8_GATE //' | $PY -I -B -c '
import json, sys
l = json.loads(sys.stdin.readline())
ok = l.get("status") == 200 and l.get("model") == "openai/gpt-oss-120b" and l.get("token_cap_anomaly") is False and int(l.get("max_completion_tokens", 0)) <= 1024 and bool(l.get("ratelimit")) and int(l.get("completion_tokens") or 0) > 0 and l.get("budget_used") == 5
print("OK" if ok else "BAD")')
  echo "request #5 record: $v5"
  echo "== Router V2"
  echo "decisions total=$(wc -l < $DEC) (A3 copy had $(wc -l < $E/lilith-router-decisions.log)); first lines unchanged: $(head -n 4 $DEC | cmp -s - $E/lilith-router-decisions.log && echo yes || echo NO)"
  tail -n +5 $DEC | cut -c1-400
  local rv; rv=$(tail -n +5 $DEC | $PY -I -B -c '
import json, sys
ls = [json.loads(x) for x in sys.stdin if x.strip()]
print("OK" if len(ls) == 1 and ls[0].get("live") is False and ls[0].get("platform") == "lilith_os" and ls[0].get("mode") and "confidence" in ls[0] else "BAD", [str(d.get("chat_id")) for d in ls])')
  echo "UI decision: $rv"
  echo "UI session turns in gateway log: $(grep -c 'F8-SYNTHETIC G-10 UI check' $HH/logs/gateway.log 2>/dev/null)"
  echo "== key isolation"
  local key; key=$(tr -d '\n' < /etc/hermes-provider-gate-dev/credentials/groq-api-key)
  local hits=0; grep -rqlF -- "$key" $HH && hits=1; journalctl --namespace=hermes-gateway-dev -o cat --no-pager | grep -qF -- "$key" && hits=1
  grep -qF -- "$key" /proc/$(systemctl show -p MainPID --value hermes-gateway-dev)/environ && hits=1; unset key
  echo "key found in HERMES_HOME/gateway journal/gateway environ: $([[ $hits -eq 0 ]] && echo no || echo YES)"
  echo "== final parity"
  local G1; G1=$(ls -d $B/upgrade-pre-* | tail -1)
  bash $P/bin/observe_host.sh $B/a5-final >/dev/null; bash $P/bin/compare_observations.sh $G1/observation $B/a5-final; local orc=$?
  bash $P/bin/dr5_check.sh $B/dr5-f8r4-a5.txt > $B/dr5-f8r4-a5.summary 2>&1; local drc=$?; tail -1 $B/dr5-f8r4-a5.summary
  $PY -I -B $R/bin/verify_release.py --full; local vrc=$?
  echo "core api health: $(curl -s -m 5 http://127.0.0.1:8765/health)"
  for u in hermes-gateway-dev hermes-provider-gate-dev hermes-gateway-dev-retention.timer lilith-os-api-dev lilith-memory-broker lilith-authority-dev lilith-recovery-witness; do
    printf '%-36s %s\n' $u "$(for k in ActiveState SubState MainPID NRestarts InvocationID UnitFileState; do systemctl show $u -p $k --value; done | paste -sd' ')"; done
  echo "listeners(9901/9911): [$(ss -Hltn | awk '{print $4}' | grep -E ':(9901|9911)$' | sort | paste -sd' ')]"
  echo "gateway non-loopback established: $(ss -Htnp state established | grep "pid=$(systemctl show -p MainPID --value hermes-gateway-dev)," | grep -vc 127.0.0.1)"
  echo "router: $(grep -E '^(mode|cognitive_enabled|canonical_ltm_enabled):' $HH/lilith_router/router.yaml | paste -sd' ')"
  echo "mem gw=$(( $(systemctl show hermes-gateway-dev -p MemoryCurrent --value)/1048576 ))MiB host_avail=$(free -m | awk 'NR==2{print $7}')MiB disk_free=$(df -Pm / | awk 'NR==2{print $4}')MiB"
  cp -p $B/a5-gate-journal.txt $E/gate-journal-a5.txt; cp -p $DEC $E/lilith-router-decisions-a5.log; cp -p $L $E/gate-ledger-a5.log; chmod 0600 $E/*
  (cd $E && sha256sum gate-journal-a5.txt lilith-router-decisions-a5.log gate-ledger-a5.log >> SHA256SUMS)
  local ok=1
  echo "$bud" | grep -qE '"budget_used": 5[,}]' && echo "$bud" | grep -q 'BUDGET_EXHAUSTED' || ok=0
  [[ $head8 == f30152d28183a67a123174c0e91572a6f2ef8b685b78cee0c8a86d59d0fe217b && $(grep -c '^R ' $L) -eq 5 && $(grep -c '^RESET' $L) -eq 1 ]] || ok=0
  [[ $fw5 -eq 1 && $refp -eq 0 && $v5 == OK && $rv == OK* && $hits -eq 0 && $orc -eq 0 && $drc -eq 0 && $vrc -eq 0 ]] || ok=0
  [[ $ok -eq 1 ]] && echo A5_PASS || echo A5_FAIL
}
main > $OUT 2>&1; echo "main_rc=$?" >> $OUT
cat $OUT; echo "OUT_SHA $(sha256sum < $OUT | cut -c1-64)"
