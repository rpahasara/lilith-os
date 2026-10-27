#!/usr/bin/env bash
# F8r3 complete validation in the WSL DEV-mirror with a SYNTHETIC Groq provider (refuses on lilith-dev-01).
set -uo pipefail
[[ $(hostname) != lilith-dev-01 ]] || { echo "refused on lilith-dev-01"; exit 1; }
W=/root/f8r3; REL=f293e72-f8r3; PKGN=hermes-gateway-dev-$REL; P=/var/tmp/f8/$PKGN
HH=/home/lilith/.hermes-dev; R=/opt/hermes-gateway-dev/current; SY=$W/synth
RES=$W/results.tsv; : > "$RES"; EV=$W/evidence; rm -rf "$EV"; mkdir -p "$EV"
MARK=F8R3-SYNTHETIC-PROVIDER-REPLY
rec() { printf '%s\t%s\t%s\n' "$1" "$2" "$3" | tee -a "$RES"; }
s() { echo; echo "################ $* ################"; }
latest_pre() { ls -d /var/backups/hermes-gateway-dev/pre-* | tail -1; }
fakecount() { grep -c . $SY/requests.jsonl 2>/dev/null || echo 0; }
TOK() { grep '^LILITH_OS_TOKEN=' $HH/.env | cut -d= -f2; }
turn() { curl -s -m 150 -o $EV/turn.json -w '%{http_code}' -H "X-LILITH-OS-Token: $(TOK)" -H 'Content-Type: application/json' \
          -d "{\"message\":\"$1\",\"session\":\"$2\"}" http://127.0.0.1:9901/; }
reply() { python3 -c 'import json;d=json.load(open("'$EV'/turn.json"));print(d.get("state"),"|",(d.get("reply") or d.get("error") or "")[:90])'; }
budget_reset() { bash $P/bin/gate_budget.sh reset --owner-approved >/dev/null 2>&1; }
EXISTING_UNITS="lilith-os-api-dev.service lilith-memory-broker.service lilith-memory-broker.socket lilith-authority-dev.service lilith-authority-dev.socket lilith-recovery-witness.service lilith-recovery-witness-owner.socket lilith-recovery-witness-signer.socket lilith-stage3-a2-final.service"
service_state() { for u in ${EXISTING_UNITS}; do printf '%s ' "$u"; for k in ActiveState SubState MainPID InvocationID NRestarts; do printf '%s ' "$(systemctl show $u -p $k --value)"; done; echo; done; }
wait_listen() { for i in $(seq 1 45); do ss -Hltn "sport = :$1" | grep -q . && return 0; sleep 2; done; return 1; }
wait_ready() { for i in $(seq 1 60); do grep -q 'Press Ctrl+C to stop' $HH/logs/gateway.log 2>/dev/null && return 0; sleep 1; done; return 1; }

clean_check() {   # <scenario> <G-1 dir>
  local sc=$1 pre=$2 ok=1 left
  bash $P/bin/observe_host.sh $EV/$sc-post >/dev/null
  bash $P/bin/compare_observations.sh "$pre/observation" $EV/$sc-post > $EV/$sc-cmp-g1.txt || ok=0
  bash $P/bin/compare_observations.sh $EV/M0 $EV/$sc-post > $EV/$sc-cmp-m0.txt || ok=0
  bash $P/bin/dr5_check.sh $EV/$sc-dr5.txt > $EV/$sc-dr5-check.txt || ok=0
  left=$(ls -d /opt/hermes-gateway-dev /etc/hermes-gateway-dev /etc/hermes-provider-gate-dev /etc/systemd/system/hermes-* \
         /etc/systemd/journald@hermes-gateway-dev.conf /var/lib/private/hermes-provider-gate-dev /var/lib/hermes-provider-gate-dev 2>/dev/null | tr '\n' ' ')
  [[ -z $left ]] || ok=0
  [[ $(ls -A $HH) == memories ]] || ok=0
  ! ss -Hltn 'sport = :9901' | grep -q . || ok=0
  ! ss -Hltn 'sport = :9911' | grep -q . || ok=0
  if [[ $ok == 1 ]]; then rec "$sc" CLEAN "obs==G-1==M0; $(tail -1 $EV/$sc-dr5-check.txt | cut -c1-28); no F8/gate paths; 9901+9911 closed; HH=memories"
  else rec "$sc" NOT_CLEAN "left=[$left] HH=[$(ls -A $HH | tr '\n' ' ')] $(grep -h DIFF $EV/$sc-cmp-*.txt | tr '\n' ' ') $(tail -1 $EV/$sc-dr5-check.txt)"; fi
}
install_f8r3() {  # <tag>
  bash $P/bin/backup_pre_install.sh >/dev/null
  F8_SIM=1 bash $P/bin/install.sh > $EV/$1-install.log 2>&1 && bash $P/bin/provision_console_token.sh >/dev/null
}
provision_key() {  # owner action G-5b, exercised through a pty exactly as the owner would type it
  printf '%s\n' "$(cat $SY/synthetic-key)" | script -qec "bash $P/bin/provision_provider_key.sh" /dev/null > $EV/key-$1.log 2>&1
  grep -q F8_KEY_PROVISIONED $EV/key-$1.log
}

s "S0 prepare: remove leftovers, synthetic provider, package, mirror baseline"
for rb in /var/tmp/f8/$PKGN/bin/rollback.sh; do [[ -x $rb ]] && bash $rb remove >/dev/null 2>&1; done
systemctl daemon-reload
mkdir -p $W/old && [[ -d /var/backups/hermes-gateway-dev ]] && mv /var/backups/hermes-gateway-dev $W/old/backups-$(date +%s)
bash $W/mirror/synthprov.sh up >/dev/null
rm -rf /var/tmp/f8 && install -d -m 0700 /var/tmp/f8 && cp $W/out/$PKGN.tar.gz* /var/tmp/f8/
(cd /var/tmp/f8 && sha256sum -c $PKGN.tar.gz.sha256 >/dev/null && tar -xzf $PKGN.tar.gz && cd $PKGN && sha256sum --quiet -c MANIFEST.sha256) \
  && rec G-2 PASS "f8r3 tarball + MANIFEST verified" || { rec G-2 FAIL ""; exit 1; }
systemctl start lilith-memory-broker.service lilith-authority-dev.service lilith-recovery-witness.service lilith-os-api-dev.service; sleep 4
bash $P/bin/observe_host.sh $EV/M0 >/dev/null
bash $P/bin/dr5_check.sh $EV/dr5-M0.txt > $EV/dr5-M0-check.txt && rec M0-DR5 PASS "$(tail -1 $EV/dr5-M0-check.txt)" || { rec M0-DR5 FAIL ""; exit 1; }

s "U upgrade path: DEV Phase A replica (f8r2 installed + running) -> f8r2 R-1/R-2 -> clean"
rm -rf /var/tmp/f8r2 && install -d -m 0700 /var/tmp/f8r2 && tar -xzf $W/f8r2pkg/hermes-gateway-dev-f293e72-f8r2.tar.gz -C /var/tmp/f8r2
P2=/var/tmp/f8r2/hermes-gateway-dev-f293e72-f8r2
bash $P2/bin/backup_pre_install.sh >/dev/null; PRE=$(latest_pre)
F8_SIM=1 bash $P2/bin/install.sh > $EV/U-f8r2-install.log 2>&1 && bash $P2/bin/provision_console_token.sh >/dev/null && systemctl start hermes-gateway-dev
wait_listen 9901 && rec U-f8r2-running PASS "Phase A state replicated (f8r2 running)" || rec U-f8r2-running FAIL ""
bash $P2/bin/rollback.sh stop > $EV/U-R1.log 2>&1 && bash $P2/bin/rollback.sh remove > $EV/U-R2.log 2>&1 \
  && rec U-f8r2-removed PASS "$(tail -1 $EV/U-R2.log | cut -c1-70)" || rec U-f8r2-removed FAIL "$(tail -2 $EV/U-R2.log)"
clean_check U "$PRE"

s "H happy path f8r3"
bash $P/bin/backup_pre_install.sh | tail -1; PRE=$(latest_pre)
F8_SIM=1 bash $P/bin/install.sh > $EV/H-install.log 2>&1
grep -q "F8_INSTALL_STAGED $REL" $EV/H-install.log && rec H-G3 PASS "install staged (gate unit + config + empty root-only credentials dir)" || rec H-G3 FAIL "$(tail -2 $EV/H-install.log)"
bash $P/bin/dr5_check.sh $EV/H-dr5-installed.txt > $EV/H-dr5i.txt && rec H-DR5-installed PASS "$(tail -1 $EV/H-dr5i.txt)" || rec H-DR5-installed FAIL ""
B=$(mktemp -d /var/tmp/f8-g4-XXXXXX); ln -s $R/src $B/hermes-agent; mkdir $B/hermes-home-dev $B/tests
cp -a $P/home/lilith_router $P/home/plugins $B/hermes-home-dev/; cp $P/tests/f7-home/config.yaml $B/hermes-home-dev/
cp $P/tests/f7-home/router.yaml $B/hermes-home-dev/lilith_router/; cp $P/tests/test_f7_offline.py $B/tests/; chown -R lilith:lilith $B; chmod 700 $B
runuser -u lilith -- env -i PATH=/usr/bin:/bin HOME=$B PYTHONUNBUFFERED=1 $R/venv/bin/python -B $B/tests/test_f7_offline.py > $EV/H-G4-f7.log 2>&1
grep -q '^OK$' $EV/H-G4-f7.log && rec H-G4 PASS "$(grep '^Ran ' $EV/H-G4-f7.log) OK (incl. B-4 adapter)" || rec H-G4 FAIL "$(tail -3 $EV/H-G4-f7.log)"
rm -rf -- "$B"
bash $P/bin/provision_console_token.sh > $EV/H-G5.log 2>&1
$R/venv/bin/python -I -B $R/bin/verify_release.py --full >> $EV/H-G5.log 2>&1 && rec H-G5 PASS "$(tail -1 $EV/H-G5.log) (no key yet)" || rec H-G5 FAIL "$(tail -3 $EV/H-G5.log)"
script -qec "bash $P/bin/provision_provider_key.sh" /dev/null < /dev/null > $EV/key-notty.log 2>&1; [[ ! -e /etc/hermes-provider-gate-dev/credentials/groq-api-key ]] \
  && rec H-G5b-guard PASS "key provisioning refuses an empty/non-key input" || rec H-G5b-guard FAIL ""
provision_key H && rec H-G5b PASS "$(grep -o 'F8_KEY_PROVISIONED.*' $EV/key-H.log | cut -c1-60) (synthetic key, typed via pty)" || rec H-G5b FAIL "$(cat $EV/key-H.log)"
$R/venv/bin/python -I -B $R/bin/verify_release.py --full > $EV/H-G5c.log 2>&1 && rec H-G5c PASS "verify full with key provisioned" || rec H-G5c FAIL "$(cat $EV/H-G5c.log)"
pre_start=$(service_state)
systemctl start hermes-gateway-dev; wait_listen 9901; wait_listen 9911
st=$(for u in hermes-gateway-dev hermes-provider-gate-dev; do for k in ActiveState NRestarts UnitFileState; do systemctl show $u -p $k --value; done; done | paste -sd' ')
lst=$(ss -Hltnup | grep -E '"(hermes|python)",pid=('$(systemctl show -p MainPID --value hermes-gateway-dev)'|'$(systemctl show -p MainPID --value hermes-provider-gate-dev)')' | awk '{print $5}' | sort | paste -sd' ')
[[ $st == "active 0 static active 0 static" && $lst == "127.0.0.1:9901 127.0.0.1:9911" ]] && rec H-G6 PASS "gateway+gate active, 0 restarts, static; listeners=[$lst]; gate user=$(ps -o user= -p $(systemctl show -p MainPID --value hermes-provider-gate-dev))" || rec H-G6 FAIL "st=[$st] lst=[$lst]"
wait_ready
s "H-RACE B-4: turns sent at listener-up after a restart"
budget_reset; f0=$(fakecount)
systemctl restart hermes-gateway-dev; wait_listen 9901
codes=""; for i in 1 2 3; do c=$(turn "F8-SYNTHETIC race $i" "race-$i"); codes="$codes $c:$(reply | cut -c1-40)"; done
empty=$(grep -c 'without a text reply' <<< "$codes")
[[ $empty -eq 0 ]] && rec H-RACE PASS "no empty replies:$codes" || rec H-RACE FAIL "$codes"
wait_ready; sleep 2
s "H-G7 smoke (4 model turns)"
budget_reset; f0=$(fakecount)
$R/venv/bin/python -I -B $R/bin/smoke_console.py --phase B --core-api --expect-marker $MARK > $EV/H-G7-smoke.txt 2>&1 \
  && rec H-G7 PASS "$(tail -1 $EV/H-G7-smoke.txt)" || rec H-G7 FAIL "$(grep -E '^FAIL|F8_SMOKE' $EV/H-G7-smoke.txt | tr '\n' ' ' | cut -c1-400)"
f1=$(fakecount)
python3 - "$SY/requests.jsonl" "$f0" "$f1" > $EV/H-provider-evidence.txt <<'PY'
import json,sys
rows=[json.loads(l) for l in open(sys.argv[1])][int(sys.argv[2]):int(sys.argv[3])]
ok=len(rows)==4 and all(r.get("auth_ok") and r.get("model")=="openai/gpt-oss-120b" and (r.get("max_completion_tokens") or 0)<=1024
   and r.get("max_tokens") is None and not r.get("tools") and r.get("reasoning_effort")=="low" and r.get("ua")=="lilith-f8-gate/1" for r in rows)
print("PROVIDER_EVIDENCE", "PASS" if ok else "FAIL", len(rows), json.dumps([{k:r.get(k) for k in ("auth_ok","model","max_completion_tokens","reasoning_effort","stream","fields")} for r in rows][:1]))
PY
grep -q "PROVIDER_EVIDENCE PASS" $EV/H-provider-evidence.txt && rec H-provider PASS "$(cut -c1-300 $EV/H-provider-evidence.txt)" || rec H-provider FAIL "$(cat $EV/H-provider-evidence.txt)"
bash $R/bin/sandbox_probe.sh > $EV/H-G7b-probe.txt 2>&1 && rec H-G7b PASS "$(tail -1 $EV/H-G7b-probe.txt); P7=$(grep -o 'P7 [^:]*: [A-Z_()0-9.,]*' $EV/H-G7b-probe.txt | sed 's/.*: //')" || rec H-G7b FAIL "$(grep -E '^FAIL|F8_PROBE' $EV/H-G7b-probe.txt | tr '\n' ' ')"
bash $R/bin/gate_probe.sh > $EV/H-G7c-gate-probe.txt 2>&1 && rec H-G7c PASS "$(tail -1 $EV/H-G7c-gate-probe.txt); $(head -1 $EV/H-G7c-gate-probe.txt)" || rec H-G7c FAIL "$(grep -E 'FAIL|key_in' $EV/H-G7c-gate-probe.txt | tr '\n' ' ')"
s "H-G10eq: 5th turn (the UI slot) via the Core API relay, then budget exhaustion"
f0=$(fakecount)
c=$(curl -s -m 150 -o $EV/turn.json -w '%{http_code}' -H 'Content-Type: application/json' -d '{"message":"F8-SYNTHETIC turn 5 (UI slot)","session":"f8b-ui"}' http://127.0.0.1:8765/os/conversation)
r5=$(reply); [[ $c == 200 && $r5 == completed* && $r5 == *$MARK* ]] && rec H-turn5 PASS "$c $r5" || rec H-turn5 FAIL "$c $r5"
used=$(curl -s http://127.0.0.1:9911/healthz | python3 -c 'import json,sys;print(json.load(sys.stdin)["budget_used"])')
[[ $used -eq 5 ]] && rec H-budget-5 PASS "acceptance budget fully used by exactly 5 model turns" || rec H-budget-5 FAIL "used=$used"
c=$(turn "F8-SYNTHETIC turn 6 must be refused" "f8b-over"); r6=$(reply); f1=$(fakecount)
[[ $((f1 - f0)) -eq 1 && $r6 != *$MARK* ]] && grep -q 'BUDGET_EXHAUSTED' <(journalctl --namespace=hermes-gateway-dev -u hermes-provider-gate-dev -o cat --no-pager | tail -5) \
  && rec H-budget-stop PASS "6th turn refused by the gate (BUDGET_EXHAUSTED), no upstream request; reply: ${r6:0:70}" || rec H-budget-stop FAIL "fake+$((f1 - f0)) $r6"
s "H-policy: direct gate requests that must never reach the provider"
f0=$(fakecount); budget_reset; pol=""
g() { curl -s -m 10 -o /dev/null -w '%{http_code}' "$@"; }
pol="$pol tools:$(g -H 'Authorization: Bearer __LILITH_GATE_CLIENT_TOKEN__' -H 'Content-Type: application/json' -d '{"model":"openai/gpt-oss-120b","messages":[{"role":"user","content":"x"}],"tools":[{"type":"browser_search"}]}' http://127.0.0.1:9911/openai/v1/chat/completions)"
pol="$pol model:$(g -H 'Authorization: Bearer __LILITH_GATE_CLIENT_TOKEN__' -H 'Content-Type: application/json' -d '{"model":"llama-3.3-70b-versatile","messages":[{"role":"user","content":"x"}]}' http://127.0.0.1:9911/openai/v1/chat/completions)"
pol="$pol token:$(g -H 'Authorization: Bearer wrong' -H 'Content-Type: application/json' -d '{"model":"openai/gpt-oss-120b","messages":[{"role":"user","content":"x"}]}' http://127.0.0.1:9911/openai/v1/chat/completions)"
pol="$pol path:$(g -H 'Authorization: Bearer __LILITH_GATE_CLIENT_TOKEN__' -d '{}' http://127.0.0.1:9911/openai/v1/embeddings)"
pol="$pol size:$(head -c 300000 /dev/zero | tr '\0' a | g -H 'Authorization: Bearer __LILITH_GATE_CLIENT_TOKEN__' -H 'Content-Type: application/json' --data-binary @- http://127.0.0.1:9911/openai/v1/chat/completions)"
pol="$pol get:$(g http://127.0.0.1:9911/openai/v1/models)"
pol="$pol connect:$(python3 -c 'import socket;s=socket.create_connection(("127.0.0.1",9911),5);s.sendall(b"CONNECT example.com:443 HTTP/1.1\r\nHost: example.com:443\r\n\r\n");print(s.recv(64).split()[1].decode())')"
f1=$(fakecount)
[[ $pol == " tools:400 model:400 token:401 path:404 size:413 get:404 connect:405" && $f1 -eq $f0 ]] && rec H-policy PASS "$pol; provider requests +0" || rec H-policy FAIL "$pol; provider +$((f1 - f0))"
s "H-fail: upstream 500 -> exactly one attempt, no retry"
budget_reset; f0=$(fakecount); echo fail500 > $SY/mode
c=$(turn "F8-SYNTHETIC upstream failure test" "f8b-fail"); rf=$(reply); f1=$(fakecount); echo ok > $SY/mode
[[ $((f1 - f0)) -eq 1 && $rf != *$MARK* && $(systemctl is-active hermes-gateway-dev) == active ]] && rec H-upstream-500 PASS "1 upstream attempt, no retry, gateway alive; reply: ${rf:0:70}" || rec H-upstream-500 FAIL "attempts=$((f1 - f0)) $rf"
s "H-nokey: gate without a provisioned key"
budget_reset; f0=$(fakecount); systemctl stop hermes-provider-gate-dev
mv /etc/hermes-provider-gate-dev/credentials/groq-api-key $W/key.held; systemctl start hermes-provider-gate-dev; wait_listen 9911
kl=$(curl -s http://127.0.0.1:9911/healthz | python3 -c 'import json,sys;print(json.load(sys.stdin)["key_loaded"])')
c=$(turn "F8-SYNTHETIC no key test" "f8b-nokey"); rk=$(reply); f1=$(fakecount)
mv $W/key.held /etc/hermes-provider-gate-dev/credentials/groq-api-key; systemctl restart hermes-provider-gate-dev; wait_listen 9911
[[ $kl == False && $((f1 - f0)) -eq 0 && $rk != *$MARK* ]] && rec H-nokey PASS "gate runs, key_loaded=False, 503 KEY_NOT_PROVISIONED, provider +0; reply: ${rk:0:60}" || rec H-nokey FAIL "kl=$kl +$((f1 - f0)) $rk"
s "H-G8 / G-9"
systemctl start hermes-gateway-dev-retention.service; rec H-G8 "$(systemctl show hermes-gateway-dev-retention.service -p Result --value | tr a-z A-Z)" "retention oneshot"
post_start=$(service_state)
[[ "$pre_start" == "$post_start" ]] && rec H-services PASS "protected services identical across start/turns/probes/gate restarts" || rec H-services FAIL ""
bash $P/bin/observe_host.sh $EV/H-G9 >/dev/null
bash $P/bin/compare_observations.sh $PRE/observation $EV/H-G9 > $EV/H-G9-cmp.txt && rec H-G9-obs PASS "observation EQUAL to G-1 with gateway+gate running" || rec H-G9-obs FAIL "$(grep DIFF $EV/H-G9-cmp.txt | tr '\n' ' ')"
bash $P/bin/dr5_check.sh $EV/H-G9-dr5.txt > $EV/H-G9-dr5c.txt && rec H-G9-DR5 PASS "$(tail -1 $EV/H-G9-dr5c.txt)" || rec H-G9-DR5 FAIL ""
s "H-OPERATE B-5 profile"
F8_SIM=1 bash $P/bin/apply_profile.sh operate > $EV/H-operate.log 2>&1 && rec H-operate PASS "$(tail -1 $EV/H-operate.log)" || rec H-operate FAIL "$(tail -3 $EV/H-operate.log)"
wait_listen 9901; wait_ready; sleep 3; budget_reset
c=$(turn "F8-SYNTHETIC operate profile turn" "f8b-op"); ro=$(reply)
prev=$(grep -c "chat=f8b-op msg=" $HH/logs/gateway.log)
[[ $ro == completed* && $ro == *$MARK* && $prev -eq 0 ]] && rec H-operate-turn PASS "turn ok; INFO message preview NOT written (WARNING level)" || rec H-operate-turn FAIL "$ro previews=$prev"
grep -q 'MaxRetentionSec=2day' /etc/systemd/journald@hermes-gateway-dev.conf && grep -q 'older-than 1 ' /etc/systemd/system/hermes-gateway-dev-retention.service.d/10-operate.conf \
  && systemctl start hermes-gateway-dev-retention.service && [[ $(systemctl show hermes-gateway-dev-retention.service -p Result --value) == success ]] \
  && rec H-operate-retention PASS "journal 2 d, history 24 h, logs 2 d; retention run success" || rec H-operate-retention FAIL ""
bash $P/bin/rollback.sh stop > $EV/H-R1.log 2>&1 && rec H-R1 PASS "$(tail -1 $EV/H-R1.log)" || rec H-R1 FAIL "$(tail -2 $EV/H-R1.log)"
bash $P/bin/rollback.sh remove > $EV/H-R2.log 2>&1 && rec H-R2 PASS "$(tail -1 $EV/H-R2.log | cut -c1-70)" || rec H-R2 FAIL "$(tail -3 $EV/H-R2.log)"
Q=$(grep -o 'quarantine=.*' $EV/H-R2.log | cut -d= -f2)
[[ -f $Q/etc/hermes-provider-gate-dev/credentials/groq-api-key && $(stat -c '%U %a' $Q) == "root 700" ]] && rec H-R2-key PASS "key moved to root-only quarantine (owner: revoke at Groq, then purge)" || rec H-R2-key FAIL ""
clean_check H "$PRE"

s "FI install-stage failure injection"
for stage in preconditions stage venv home etc units reload verify; do
  bash $P/bin/backup_pre_install.sh >/dev/null; PRE=$(latest_pre)
  F8_SIM=1 F8_FAIL_AT=$stage bash $P/bin/install.sh > $EV/FI-$stage.log 2>&1; rc=$?
  [[ $rc -ne 0 ]] && grep -q "INJECTED_FAILURE at $stage" $EV/FI-$stage.log && rec FI-$stage-stop PASS "install exit $rc at '$stage'" || rec FI-$stage-stop FAIL "rc=$rc $(tail -1 $EV/FI-$stage.log)"
  bash $P/bin/rollback.sh remove > $EV/FI-$stage-R2.log 2>&1 || true
  clean_check FI-$stage "$PRE"
done

s "PF post-install failures"
install_f8r3 PF-crash; PRE=$(latest_pre); provision_key PF >/dev/null
systemctl start hermes-gateway-dev; wait_listen 9911; sleep 3
for i in 1 2 3 4; do pid=$(systemctl show -p MainPID --value hermes-provider-gate-dev); [[ $pid != 0 ]] && kill -9 $pid; sleep 12; done
rec PF-gate-crash "$( [[ $(systemctl show hermes-provider-gate-dev -p ActiveState --value) == failed && $(systemctl is-active hermes-gateway-dev) == active ]] && echo PASS || echo FAIL )" \
  "gate after 4 SIGKILLs: $(systemctl show hermes-provider-gate-dev -p ActiveState --value) (StartLimitBurst); gateway still $(systemctl is-active hermes-gateway-dev)"
bash $P/bin/rollback.sh remove > $EV/PF-crash-R2.log 2>&1; systemctl reset-failed hermes-provider-gate-dev hermes-gateway-dev 2>/dev/null; clean_check PF-crash "$PRE"

install_f8r3 PF-tamper; PRE=$(latest_pre)
sed -i 's/"max_output_tokens": 1024/"max_output_tokens": 4096/' /etc/hermes-provider-gate-dev/gate.json
systemctl start hermes-gateway-dev 2>/dev/null; sleep 3
[[ $(systemctl show hermes-gateway-dev -p ActiveState --value) != active ]] && journalctl --namespace=hermes-gateway-dev -u hermes-gateway-dev -o cat --no-pager | grep -q 'gate.json' \
  && rec PF-gate-config-tamper PASS "gateway start refused: $(journalctl --namespace=hermes-gateway-dev -u hermes-gateway-dev -o cat --no-pager | grep -o 'F8_VERIFY_FAIL [A-Z_]*[^;]*' | head -2 | tr '\n' ';' | cut -c1-140)" \
  || rec PF-gate-config-tamper FAIL "state=$(systemctl show hermes-gateway-dev -p ActiveState --value)"
bash $P/bin/rollback.sh remove > $EV/PF-tamper-R2.log 2>&1; systemctl reset-failed hermes-gateway-dev 2>/dev/null; clean_check PF-tamper "$PRE"

s "PG precondition guards"
SD=/etc/systemd/system; cp -p $SD/lilith-authority-dev.service $W/authority.unit.orig
bash $P/bin/backup_pre_install.sh >/dev/null; PRE=$(latest_pre)
echo "# f8r3 pending-reload trigger" >> $SD/lilith-authority-dev.service
F8_SIM=1 bash $P/bin/install.sh > $EV/PG-reload.log 2>&1; rc=$?
[[ $rc -ne 0 ]] && grep -q "NEED_DAEMON_RELOAD_PENDING lilith-authority-dev.service" $EV/PG-reload.log && [[ ! -e /opt/hermes-gateway-dev ]] \
  && rec PG-reload-pending PASS "install refused before any write" || rec PG-reload-pending FAIL "rc=$rc"
cp -p $W/authority.unit.orig $SD/lilith-authority-dev.service; systemctl daemon-reload
bash $P/bin/rollback.sh remove > $EV/PG-reload-R2.log 2>&1; clean_check PG-reload "$PRE"
install_f8r3 PG-rbhold; PRE=$(latest_pre); provision_key PG >/dev/null
systemctl start hermes-gateway-dev; wait_listen 9901; sleep 3
echo "# f8r3 pending-reload trigger" >> $SD/lilith-authority-dev.service
bash $P/bin/rollback.sh remove > $EV/PG-rbhold-R2.log 2>&1
grep -q "F8_ROLLBACK_HOLD" $EV/PG-rbhold-R2.log && ! ss -Hltn 'sport = :9901' | grep -q . && ! ss -Hltn 'sport = :9911' | grep -q . \
  && rec PG-rollback-hold PASS "R-2 moved F8+gate files, withheld daemon-reload, 9901+9911 closed" || rec PG-rollback-hold FAIL "$(tail -2 $EV/PG-rbhold-R2.log)"
cp -p $W/authority.unit.orig $SD/lilith-authority-dev.service; systemctl daemon-reload
clean_check PG-rbhold "$PRE"

s "FINAL"
bash $P/bin/observe_host.sh $EV/FINAL >/dev/null
bash $P/bin/compare_observations.sh $EV/M0 $EV/FINAL > $EV/FINAL-cmp.txt && rec FINAL-obs PASS "M0 == FINAL" || rec FINAL-obs FAIL "$(grep DIFF $EV/FINAL-cmp.txt | tr '\n' ' ')"
bash $P/bin/dr5_check.sh $EV/FINAL-dr5.txt > $EV/FINAL-dr5c.txt && rec FINAL-DR5 PASS "$(tail -1 $EV/FINAL-dr5c.txt)" || rec FINAL-DR5 FAIL ""
echo; echo "TOTAL: $(grep -cE $'\t(PASS|CLEAN|SUCCESS)\t' $RES) ok / $(wc -l < $RES) rows; NOT ok: $(grep -vcE $'\t(PASS|CLEAN|SUCCESS)\t' $RES)"
