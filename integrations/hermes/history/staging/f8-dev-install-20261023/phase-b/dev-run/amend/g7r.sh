#!/usr/bin/env bash
# F8r4 amended G-7 continuation + G-7d (root). Requests #2-#4 via smoke_resume.py with a POSITION-BASED first-request
# hold: every gate/decision record is read from offsets taken at THIS run's start (the defect that stopped attempt 1
# read the whole journal and matched G-6b's CONNECT probe). The client is SIGSTOPped as soon as the ledger gains its
# first new reservation; request #2 is validated; only then is the client resumed. Any failure: kill client, R-1.
#   bash g7r.sh <amend-dir> <prior-request-id> [marker]          (F8_SIM=1 = WSL mirror; refused on lilith-dev-01)
set -uo pipefail
if [[ ${F8_SIM:-} == 1 ]]; then [[ $(hostname) != lilith-dev-01 ]] || exit 1; else [[ $(hostname) == lilith-dev-01 ]] || { echo "WRONG HOST"; exit 1; }; fi
A=${1:?amend dir}; PRIOR=${2:?prior request id}; MARKER=${3:-}
R=/opt/hermes-gateway-dev/current; B=/var/backups/hermes-gateway-dev; HH=/home/lilith/.hermes-dev
L=/var/lib/private/hermes-provider-gate-dev/ledger.log; DEC=$HH/logs/lilith-router-decisions.log
OUT=$B/G-7r.txt; SMOKE=$B/G-7r-resume.txt; PY=$R/venv/bin/python
gatelog() { journalctl --namespace=hermes-gateway-dev -u hermes-provider-gate-dev -o cat --no-pager 2>/dev/null | grep '^F8_GATE {'; }
since_start() { gatelog | tail -n +$(( N0 + 1 )); }        # only gate records written after this run started
rcount() { grep -c '^R ' $L; }
dcount() { [[ -f $DEC ]] && wc -l < $DEC || echo 0; }
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
    print(f"FWD#{i} " + json.dumps({k: l.get(k) for k in ("ts", "request_id", "status", "model", "stream", "max_completion_tokens",
          "prompt_tokens", "completion_tokens", "token_cap_anomaly", "budget_used", "ratelimit")}, sort_keys=True))
if len(fw) != want: bad.append(f"forwarded={len(fw)} want={want}")
if ref: bad.append("refused non-GET: " + ";".join(f"{l.get('reason')}:{l.get('path')}" for l in ref))
print("VALIDATE " + ("OK" if not bad else "FAIL " + ",".join(bad)))
sys.exit(1 if bad else 0)
PYEOF
r1() { echo "== R-1 (stop condition)"; bash $R/bin/rollback.sh stop; }
main() {
  echo "== G-7r pre $(date -u +%FT%TZ)"
  [[ -f $A/smoke_resume.py && -f $A/SHA256SUMS ]] && (cd $A && sha256sum -c SHA256SUMS) || { echo "G7R_FAIL harness hash"; return 1; }
  local b0; b0=$(bash $R/bin/gate_budget.sh show); echo "budget: $b0"
  echo "$b0" | grep -qE '"budget_used": 1[,}]' && echo "$b0" | grep -q '"key_loaded": true' || { echo "G7R_FAIL budget not exactly 1 used / key"; return 1; }
  [[ $(rcount) -eq 1 && $(grep '^R ' $L | cut -d' ' -f3) == "$PRIOR" ]] || { echo "G7R_FAIL ledger is not exactly the prior request"; return 1; }
  N0=$(gatelog | wc -l); local d0; d0=$(dcount); echo "offsets: gate_lines=$N0 decisions=$d0"
  local mk=(); [[ -n $MARKER ]] && mk=(--expect-marker "$MARKER")
  $PY -I -B $A/smoke_resume.py --prior-request-id "$PRIOR" "${mk[@]}" > $SMOKE 2>&1 &
  local SP=$! t0; t0=$(date +%s); echo "resume pid=$SP"
  local held=0
  for _ in $(seq 1 6000); do
    if [[ $(rcount) -ge 2 ]]; then kill -STOP $SP && held=1; break; fi
    kill -0 $SP 2>/dev/null || break
    sleep 0.05
  done
  if [[ $held -ne 1 ]]; then echo "G7R_FAIL no new reservation (client exited or 300 s)"; kill -KILL $SP 2>/dev/null; cat $SMOKE; r1; return 1; fi
  echo "HOLD: client frozen at reservation #2 after $(( $(date +%s) - t0 )) s; ledger R=$(rcount)"
  for _ in $(seq 1 240); do since_start | grep -q '"decision": "FORWARDED"' && break; since_start | grep '"decision": "REFUSED"' | grep -vq '"method": "GET"' && break; sleep 0.5; done
  sleep 1
  echo "== REQUEST #2 CHECK (records since this run's start only)"
  local rc2; since_start | $PY -I -B -c "$VAL" 1; rc2=$?
  local b2; b2=$(bash $R/bin/gate_budget.sh show); echo "budget after #2: $b2"
  [[ $(rcount) -eq 2 ]] && echo "$b2" | grep -qE '"budget_used": 2[,}]' || rc2=1
  echo "new Router V2 decision lines: $(( $(dcount) - d0 ))"; tail -n +$(( d0 + 1 )) $DEC | cut -c1-400
  tail -n +$(( d0 + 1 )) $DEC | head -1 | $PY -I -B -c 'import json,sys; d=json.loads(sys.stdin.readline()); sys.exit(0 if d.get("live") is False and d.get("platform")=="lilith_os" and str(d.get("chat_id"))=="f8b-s1" and d.get("mode") and "confidence" in d else 1)' || rc2=1
  echo "gateway non-loopback established: $(ss -Htnp state established | grep "pid=$(systemctl show -p MainPID --value hermes-gateway-dev)," | grep -vc 127.0.0.1)"
  if [[ $rc2 -ne 0 ]]; then echo "REQUEST2_FAIL: client killed before request #3"; kill -KILL $SP; wait $SP 2>/dev/null; cat $SMOKE; r1; echo G7R_FAIL; return 1; fi
  echo "REQUEST2_OK: resuming"
  kill -CONT $SP; wait $SP; local src=$?
  echo "== resume output (rc=$src)"; cut -c1-260 $SMOKE
  echo "== G-7d (this run: 3 FORWARDED; all runs: 4)"
  local a3 a4; since_start | $PY -I -B -c "$VAL" 3; a3=$?
  gatelog | grep '"decision": "FORWARDED"' | $PY -I -B -c "$VAL" 4 | tail -1; a4=${PIPESTATUS[2]}
  echo "budget: $(bash $R/bin/gate_budget.sh show)"
  echo "ledger: R=$(rcount) lines=$(wc -l < $L) sha256=$(sha256sum < $L | cut -c1-64)"; cat $L
  echo "decisions total: $(dcount)"
  for u in hermes-gateway-dev hermes-provider-gate-dev lilith-os-api-dev lilith-memory-broker lilith-authority-dev lilith-recovery-witness; do
    printf '%-26s %s\n' $u "$(for k in ActiveState SubState MainPID NRestarts InvocationID; do systemctl show $u -p $k --value; done | paste -sd' ')"; done
  if [[ $src -eq 0 && $a3 -eq 0 && $a4 -eq 0 && $(rcount) -eq 4 ]] && grep -qE '^F8_RESUME_PASS turns=3 ' $SMOKE && ! grep -q '^FAIL ' $SMOKE; then
    echo G7R_PASS; echo G7D_CHECKS_OK
  else echo G7R_FAIL; r1; return 1; fi
}
main > $OUT 2>&1; echo "main_rc=$?" >> $OUT
cat $OUT; echo "OUT_SHA $(sha256sum < $OUT | cut -c1-64)"
