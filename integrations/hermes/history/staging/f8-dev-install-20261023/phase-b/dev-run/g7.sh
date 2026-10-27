#!/usr/bin/env bash
# G-7 (4 real synthetic Groq requests via the unmodified smoke) with an owner-required FIRST-REQUEST HOLD, then G-7d.
# Hold: the smoke client is SIGSTOPped as soon as the gate ledger reserves request #1 (the client is then blocked on
# turn 1's reply, so no 2nd request can start). Turn 1 is validated (gate FORWARDED record, budget, Router V2 shadow
# decision) and only then is the client resumed (SIGCONT); otherwise it is killed and R-1 is applied.
set -uo pipefail
[[ $(hostname) == lilith-dev-01 ]] || { echo "WRONG HOST"; exit 1; }
R=/opt/hermes-gateway-dev/current; B=/var/backups/hermes-gateway-dev; HH=/home/lilith/.hermes-dev
L=/var/lib/private/hermes-provider-gate-dev/ledger.log; DEC=$HH/logs/lilith-router-decisions.log
OUT=$B/G-7.txt; SMOKE=$B/G-7-smoke.txt; PY=$R/venv/bin/python
gatelog() { journalctl --namespace=hermes-gateway-dev -u hermes-provider-gate-dev -o cat --no-pager 2>/dev/null | grep '^F8_GATE {'; }
rcount() { grep -c '^R ' $L; }
fwd() { gatelog | grep -c '"decision": "FORWARDED"'; }
dcount() { [[ -f $DEC ]] && wc -l < $DEC || echo 0; }
# Validator: reads gate F8_GATE lines on stdin; prints a summary of FORWARDED lines; exit 1 on any defect.
read -r -d '' VAL <<'PYEOF'
import json, sys
want = int(sys.argv[1]); bad = []
lines = [json.loads(l[len("F8_GATE "):]) for l in sys.stdin if l.startswith("F8_GATE {")]
fw = [l for l in lines if l.get("decision") == "FORWARDED"]
ref = [l for l in lines if l.get("decision") == "REFUSED" and l.get("method") != "GET"]
for i, l in enumerate(fw, 1):
    ok = (l.get("status") == 200 and l.get("model") == "openai/gpt-oss-120b" and l.get("token_cap_anomaly") is False
          and int(l.get("max_completion_tokens", 0)) <= 1024 and bool(l.get("ratelimit"))
          and int(l.get("completion_tokens") or 0) > 0)
    bad += [] if ok else [f"FORWARDED#{i}"]
    print(f"FWD#{i} " + json.dumps({k: l.get(k) for k in ("ts", "request_id", "status", "model", "stream",
          "max_completion_tokens", "completion_tokens", "token_cap_anomaly", "budget_used", "ratelimit")}, sort_keys=True))
if len(fw) != want: bad.append(f"forwarded={len(fw)} want={want}")
if ref: bad.append("refused POST: " + ";".join(f"{l.get('reason')}:{l.get('path')}" for l in ref))
print("VALIDATE " + ("OK" if not bad else "FAIL " + ",".join(bad)))
sys.exit(1 if bad else 0)
PYEOF
r1() { echo "== R-1 (stop condition)"; bash $R/bin/rollback.sh stop; }
main() {
  echo "== G-7 pre $(date -u +%FT%TZ)"
  local b0; b0=$(bash $R/bin/gate_budget.sh show); echo "budget: $b0"
  echo "$b0" | grep -qE '"budget_used": 0[,}]' && echo "$b0" | grep -q '"key_loaded": true' || { echo "G7_FAIL budget not 0 / key not loaded"; return 1; }
  [[ $(rcount) -eq 0 && $(fwd) -eq 0 ]] || { echo "G7_FAIL ledger/forwarded not empty"; return 1; }
  local d0; d0=$(dcount); echo "decisions log lines before: $d0"
  $PY -I -B $R/bin/smoke_console.py --phase B --core-api > $SMOKE 2>&1 &
  local SP=$! t0; t0=$(date +%s); echo "smoke pid=$SP"
  local held=0
  for _ in $(seq 1 6000); do   # <= 300 s at 50 ms
    if [[ $(rcount) -ge 1 ]]; then kill -STOP $SP && held=1; break; fi
    kill -0 $SP 2>/dev/null || break
    sleep 0.05
  done
  if [[ $held -ne 1 ]]; then echo "G7_FAIL no reservation observed (smoke exited or 300 s)"; kill -KILL $SP 2>/dev/null; cat $SMOKE; r1; return 1; fi
  echo "HOLD: smoke frozen at reservation #1 after $(( $(date +%s) - t0 )) s; ledger R lines=$(rcount)"
  for _ in $(seq 1 240); do [[ $(fwd) -ge 1 ]] && break; gatelog | grep -q '"decision": "REFUSED"' && break; sleep 0.5; done
  sleep 1
  echo "== FIRST REQUEST CHECK"
  local rc1; gatelog | $PY -I -B -c "$VAL" 1; rc1=$?
  local b1; b1=$(bash $R/bin/gate_budget.sh show); echo "budget after #1: $b1"
  echo "ledger R lines=$(rcount)"
  [[ $(rcount) -eq 1 ]] && echo "$b1" | grep -qE '"budget_used": 1[,}]' || rc1=1
  local dn; dn=$(( $(dcount) - d0 )); echo "new Router V2 decision lines: $dn"
  [[ -f $DEC ]] && tail -n +$(( d0 + 1 )) $DEC | cut -c1-400
  [[ $dn -ge 1 ]] && tail -n +$(( d0 + 1 )) $DEC | head -1 | $PY -I -B -c 'import json,sys; d=json.loads(sys.stdin.readline()); sys.exit(0 if d.get("live") is False and d.get("platform")=="lilith_os" and str(d.get("chat_id"))=="f8b-s1" and d.get("mode") and "confidence" in d else 1)' || rc1=1
  echo "gateway non-loopback established: $(ss -Htnp state established | grep "pid=$(systemctl show -p MainPID --value hermes-gateway-dev)," | grep -vc 127.0.0.1)"
  if [[ $rc1 -ne 0 ]]; then echo "FIRST_REQUEST_FAIL: smoke killed before any 2nd request"; kill -KILL $SP; wait $SP 2>/dev/null; cat $SMOKE; r1; echo G7_FAIL; return 1; fi
  echo "FIRST_REQUEST_OK: resuming smoke"
  kill -CONT $SP; wait $SP; local src=$?
  echo "== smoke output (rc=$src)"; cat $SMOKE | cut -c1-260
  echo "== G-7d"
  local all; gatelog | $PY -I -B -c "$VAL" 4; all=$?
  echo "budget: $(bash $R/bin/gate_budget.sh show)"
  echo "ledger: R lines=$(rcount) total lines=$(wc -l < $L)"
  echo "new Router V2 decision lines total: $(( $(dcount) - d0 ))"
  tail -n +$(( d0 + 1 )) $DEC | cut -c1-400
  echo "gateway non-loopback established: $(ss -Htnp state established | grep "pid=$(systemctl show -p MainPID --value hermes-gateway-dev)," | grep -vc 127.0.0.1)"
  for u in hermes-gateway-dev hermes-provider-gate-dev lilith-os-api-dev lilith-memory-broker lilith-authority-dev lilith-recovery-witness; do
    printf '%-26s %s\n' $u "$(for k in ActiveState SubState MainPID NRestarts InvocationID; do systemctl show $u -p $k --value; done | paste -sd' ')"; done
  if [[ $src -eq 0 && $all -eq 0 && $(rcount) -eq 4 ]] && grep -q '^F8_SMOKE_PASS phase=B turns=4 35/35' $SMOKE; then echo G7_PASS; echo G7D_CHECKS_OK; else echo G7_FAIL; r1; return 1; fi
}
main > $OUT 2>&1; echo "main_rc=$?" >> $OUT
cat $OUT; echo "OUT_SHA $(sha256sum < $OUT | cut -c1-64)"
