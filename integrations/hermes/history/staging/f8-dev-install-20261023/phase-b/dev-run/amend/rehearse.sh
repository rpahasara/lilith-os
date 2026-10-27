#!/usr/bin/env bash
# LOCAL WSL MIRROR ONLY (refused on lilith-dev-01): rehearse the amended F8r4 continuation with the SYNTHETIC Groq.
# Reproduces DEV exactly: fresh install (budget 0/5, no reset anywhere), G-6b probes (leaves the stale CONNECT refusal),
# attempt 1 = unmodified smoke held at reservation #1 then killed + R-1 (what happened on DEV), then the amended path:
# turn-1 evidence (read-only), G-6 restart, g7r.sh (requests #2-#4), G-8, G-9, the G-10 slot (#5) and BUDGET_EXHAUSTED.
set -uo pipefail
[[ $(hostname) != lilith-dev-01 ]] || { echo "refused on lilith-dev-01"; exit 1; }
W=/root/f8r4; A=$W/amend; REL=f293e72-f8r4; PKGN=hermes-gateway-dev-$REL; P=/var/tmp/f8/$PKGN
HH=/home/lilith/.hermes-dev; R=/opt/hermes-gateway-dev/current; SY=$W/synth; B=/var/backups/hermes-gateway-dev
L=/var/lib/private/hermes-provider-gate-dev/ledger.log
MARK=F8R3-SYNTHETIC-PROVIDER-REPLY; RES=$A/rehearsal.tsv; : > $RES; EV=$A/ev; rm -rf $EV; mkdir -p $EV
rec() { printf '%s\t%s\t%s\n' "$1" "$2" "$3" | tee -a "$RES"; }
fakecount() { local c; c=$(grep -c '"path": "/openai/v1/chat/completions"' $SY/requests.jsonl 2>/dev/null); echo "${c:-0}"; }
gatelog() { journalctl --namespace=hermes-gateway-dev -u hermes-provider-gate-dev -o cat --no-pager 2>/dev/null | grep '^F8_GATE {'; }
wait_ready() {  # same criterion as the corrected DEV G-6 wrapper: 9901, 9911 and the gate START line, <= 90 s
  local since=$1 i; for i in $(seq 1 90); do
    ss -Hltn 'sport = :9901' | grep -q . && ss -Hltn 'sport = :9911' | grep -q . \
      && journalctl --namespace=hermes-gateway-dev -u hermes-provider-gate-dev --since "$since" -o cat --no-pager | grep -q '"decision": "START"' && return 0
    sleep 1; done; return 1; }
OLDVAL='import json,sys
l=[json.loads(x[8:]) for x in sys.stdin if x.startswith("F8_GATE {")]
r=[x for x in l if x.get("decision")=="REFUSED" and x.get("method")!="GET"]
print("refused_non_GET=%d %s" % (len(r), ";".join("%s:%s" % (x.get("reason"), x.get("path")) for x in r))); sys.exit(1 if r else 0)'

echo "#### S0 mirror baseline"
MIRROR_SET_UP=0
if [[ ! -f /etc/systemd/system/lilith-memory-broker.service ]]; then
  bash /root/f8r2/mirror/mirror_setup.sh /root/f8r2/repo /root/f8hd/build/pkg/uv/uv > $EV/mirror-setup.log 2>&1 \
    && MIRROR_SET_UP=1 && rec mirror-setup PASS "stand-in Core API/broker/authority/witness (mirror_setup.sh)" || { rec mirror-setup FAIL "$(tail -3 $EV/mirror-setup.log)"; exit 1; }
fi
for rb in /var/tmp/f8/$PKGN/bin/rollback.sh; do [[ -x $rb ]] && bash $rb remove >/dev/null 2>&1; done
systemctl daemon-reload
[[ -d $B ]] && mkdir -p $W/old && mv $B $W/old/backups-amend-$(date +%s)
python3 -I $A/patch_fake_groq.py $W/mirror/fake_groq.py; python3 -I $A/patch_fake_groq_msgs.py $W/mirror/fake_groq.py; bash $W/mirror/synthprov.sh up >/dev/null
rm -rf /var/tmp/f8 && install -d -m 0700 /var/tmp/f8 && cp $W/out/$PKGN.tar.gz* /var/tmp/f8/
(cd /var/tmp/f8 && sha256sum -c $PKGN.tar.gz.sha256 >/dev/null && tar -xzf $PKGN.tar.gz && cd $PKGN && sha256sum --quiet -c MANIFEST.sha256) \
  && rec G-2 PASS "f8r4 $(sha256sum < /var/tmp/f8/$PKGN.tar.gz | cut -c1-16) + MANIFEST" || { rec G-2 FAIL ""; exit 1; }
systemctl start lilith-memory-broker.service lilith-authority-dev.service lilith-recovery-witness.service lilith-os-api-dev.service; sleep 4
bash $P/bin/observe_host.sh $EV/M0 >/dev/null
bash $P/bin/dr5_check.sh $EV/dr5-M0.txt > $EV/dr5-M0-check.txt && rec M0-DR5 PASS "$(tail -1 $EV/dr5-M0-check.txt | cut -c1-40)" || { rec M0-DR5 FAIL ""; exit 1; }
# the amend harness is staged exactly as on DEV: root 0700 dir, hash list checked by g7r.sh
rm -rf /var/tmp/f8/amend && install -d -m 0700 /var/tmp/f8/amend && cp $A/smoke_resume.py $A/turn1_evidence.py $A/g7r.sh $A/continuity_evidence.py /var/tmp/f8/amend/
(cd /var/tmp/f8/amend && sha256sum smoke_resume.py turn1_evidence.py g7r.sh continuity_evidence.py > SHA256SUMS)

echo "#### install f8r4 (G-1, G-3, G-5, G-5b synthetic key via pty, G-5c)"
bash $P/bin/backup_pre_install.sh >/dev/null; PRE=$(ls -d $B/pre-* | tail -1)
F8_SIM=1 bash $P/bin/install.sh > $EV/install.log 2>&1 && grep -q "F8_INSTALL_STAGED $REL" $EV/install.log && rec G-3 PASS staged || { rec G-3 FAIL "$(tail -2 $EV/install.log)"; exit 1; }
bash $P/bin/provision_console_token.sh >/dev/null
printf '%s\n' "$(cat $SY/synthetic-key)" | script -qec "bash $P/bin/provision_provider_key.sh" /dev/null > $EV/key.log 2>&1
$R/venv/bin/python -I -B $R/bin/verify_release.py --full > $EV/g5c.log 2>&1 && rec G-5c PASS "$(tail -1 $EV/g5c.log)" || { rec G-5c FAIL ""; exit 1; }
$R/venv/bin/python -I -B $A/test_continuity.py /var/tmp/f8/amend > $EV/test-continuity.txt 2>&1 && rec T-continuity PASS "$(tail -1 $EV/test-continuity.txt)" || rec T-continuity FAIL "$(grep -E "^FAIL|CONTINUITY_TESTS" $EV/test-continuity.txt | tr '
' ' ')"

echo "#### G-6 + G-6b (leaves the stale CONNECT refusal in the gate journal, as on DEV)"
since=$(date '+%Y-%m-%d %H:%M:%S'); systemctl start hermes-gateway-dev
wait_ready "$since" && rec G-6 PASS "ready (9901+9911+START)" || { rec G-6 FAIL ""; exit 1; }
bash $R/bin/sandbox_probe.sh > $EV/probe.txt 2>&1 && rec G-6b-sandbox PASS "$(tail -1 $EV/probe.txt)" || rec G-6b-sandbox FAIL "$(grep FAIL $EV/probe.txt | tr '\n' ' ')"
bash $R/bin/gate_probe.sh > $EV/gprobe.txt 2>&1 && rec G-6b-gate PASS "$(tail -1 $EV/gprobe.txt)" || rec G-6b-gate FAIL ""
gatelog | grep -q CONNECT_NOT_ALLOWED && rec stale-CONNECT PRESENT "G-6b P20 refusal in the gate journal before G-7" || rec stale-CONNECT ABSENT ""

echo "#### attempt 1 = what happened on DEV: unmodified smoke, held at reservation #1, then killed + R-1"
N0=$(gatelog | wc -l); f0=$(fakecount)
$R/venv/bin/python -I -B $R/bin/smoke_console.py --phase B --core-api --expect-marker $MARK > $EV/attempt1-smoke.txt 2>&1 &
SP=$!; held=0
for _ in $(seq 1 6000); do [[ $(grep -c '^R ' $L) -ge 1 ]] && { kill -STOP $SP; held=1; break; }; sleep 0.05; done
for _ in $(seq 1 240); do gatelog | tail -n +$((N0 + 1)) | grep -q FORWARDED && break; sleep 0.5; done; sleep 1
[[ $held == 1 ]] && rec A1-hold PASS "frozen at R=$(grep -c '^R ' $L), provider +$(( $(fakecount) - f0 ))" || rec A1-hold FAIL ""
gatelog | python3 -c "$OLDVAL" > $EV/old-validator.txt; o=$?
[[ $o -ne 0 ]] && rec A1-old-validator REPRODUCED "whole-journal check FAILS: $(cat $EV/old-validator.txt)" || rec A1-old-validator NOT_REPRODUCED "$(cat $EV/old-validator.txt)"
gatelog | tail -n +$((N0 + 1)) | python3 -c "$OLDVAL" > $EV/new-validator.txt && rec A1-new-validator PASS "since-start check: $(cat $EV/new-validator.txt)" || rec A1-new-validator FAIL "$(cat $EV/new-validator.txt)"
PRIOR=$(grep '^R ' $L | head -1 | cut -d' ' -f3)
kill -KILL $SP; wait $SP 2>/dev/null; bash $R/bin/rollback.sh stop > $EV/r1.log 2>&1
[[ $(grep -c '^R ' $L) -eq 1 && $(( $(fakecount) - f0 )) -eq 1 ]] && rec A1-state PASS "budget 1/5, provider requests 1, prior=$PRIOR, $(tail -1 $EV/r1.log)" || rec A1-state FAIL "R=$(grep -c '^R ' $L) prov=$(( $(fakecount) - f0 ))"

echo "#### amended step 1: request #1 reply evidence, read-only, gateway stopped"
sha256sum $HH/state.db $HH/state.db-wal $HH/state.db-shm 2>/dev/null > $EV/statedb-sha-before.txt; ls -la $HH/state.db* > $EV/statedb-ls-before.txt
$R/venv/bin/python -I -B /var/tmp/f8/amend/turn1_evidence.py > $EV/turn1.txt 2>&1 && rec T1-reply PASS "$(grep 'turn-1 reply' $EV/turn1.txt | cut -c1-150)" || rec T1-reply FAIL "$(tail -3 $EV/turn1.txt | tr '\n' ' ')"
ls -la $HH/state.db* > $EV/statedb-ls-after.txt
sha256sum -c --quiet $EV/statedb-sha-before.txt && diff -q <(awk '{print $1,$3,$4,$5,$9}' $EV/statedb-ls-before.txt) <(awk '{print $1,$3,$4,$5,$9}' $EV/statedb-ls-after.txt) >/dev/null \
  && rec T1-readonly PASS "state.db/-wal/-shm bytes + file set/owner/size unchanged; $(grep -c 'private copy removed: True' $EV/turn1.txt) private copy removed" || rec T1-readonly FAIL "$(diff $EV/statedb-ls-before.txt $EV/statedb-ls-after.txt | tr '\n' ' ')"

echo "#### amended step 2: G-6 restart (corrected wrapper criterion), then g7r.sh = requests #2-#4 + G-7d"
T1SID=$(grep -o "'id': '[^']*'" $EV/turn1.txt | head -1 | cut -d"'" -f4); RESTART=$(date +%s)
since=$(date '+%Y-%m-%d %H:%M:%S'); systemctl start hermes-gateway-dev
wait_ready "$since" && rec G-6r PASS "ready; turn-1 session=$T1SID restart_epoch=$RESTART" || { rec G-6r FAIL ""; exit 1; }
f0=$(fakecount)
F8_SIM=1 bash /var/tmp/f8/amend/g7r.sh /var/tmp/f8/amend "$PRIOR" "$MARK" > $EV/g7r.txt 2>&1
grep -q '^G7R_PASS' $EV/g7r.txt && rec G-7r PASS "$(grep -E '^F8_RESUME_' $B/G-7r-resume.txt); provider +$(( $(fakecount) - f0 ))" || rec G-7r FAIL "$(grep -E '^FAIL|G7R_|REQUEST2|VALIDATE' $EV/g7r.txt | tr '\n' ' ' | cut -c1-400)"
grep -q '^REQUEST2_OK' $EV/g7r.txt && rec G-7r-hold PASS "$(grep '^HOLD' $EV/g7r.txt)" || rec G-7r-hold FAIL ""
grep -q '^PASS C3 ' $B/G-7r-resume.txt && rec C3-continuity PASS "$(grep '^PASS C3 ' $B/G-7r-resume.txt | cut -c1-120)" || rec C3-continuity FAIL "$(grep 'C3 ' $B/G-7r-resume.txt)"
python3 - $SY/requests.jsonl > $EV/nmsg.txt <<'PY'
import json,sys
rows=[json.loads(l) for l in open(sys.argv[1]) if '"/openai/v1/chat/completions"' in l]
print("n_messages per provider request:", [r.get("n_messages") for r in rows], "auth_ok:", all(r.get("auth_ok") for r in rows),
      "tools:", [r.get("tools") for r in rows])
PY
rec provider-view INFO "$(cat $EV/nmsg.txt)"
echo "#### amended step 2b: continuity (gateway stopped; stored history from a private copy + actual turn-2 request)"
bash $R/bin/rollback.sh stop > $EV/r1b.log 2>&1
sha256sum $HH/state.db $HH/state.db-wal $HH/state.db-shm $L $HH/logs/lilith-router-decisions.log 2>/dev/null > $EV/c-sha-before.txt
$R/venv/bin/python -I -B /var/tmp/f8/amend/continuity_evidence.py --expect-session "$T1SID" --restart-epoch "$RESTART" > $EV/continuity.txt 2>&1   && rec C5-C8-stored PASS "$(grep -cE '^PASS C[5-8] ' $EV/continuity.txt)/4 $(grep -o 'CONTINUITY_STORED_OK' $EV/continuity.txt)" || rec C5-C8-stored FAIL "$(grep -E '^FAIL|CONTINUITY' $EV/continuity.txt | tr '
' ' ' | cut -c1-300)"
sha256sum -c --quiet $EV/c-sha-before.txt && [[ $(ls -d /var/tmp/f8/amend/c-* 2>/dev/null | wc -l) -eq 0 ]]   && rec C-readonly PASS "state.db/-wal/-shm, ledger, decisions unchanged; private copy removed" || rec C-readonly FAIL ""
grep -q 'sha=' $EV/continuity.txt && grep -qvE 'F8-SYNTHETIC|hello from' $EV/continuity.txt && ! grep -qE 'F8-SYNTHETIC turn|SYNTHETIC-PROVIDER-REPLY' $EV/continuity.txt   && rec C-no-content PASS "verifier output carries roles/lengths/hashes only, no dialogue text" || rec C-no-content FAIL ""
EFF=$(grep '^EFFECTIVE_SHAS ' $EV/continuity.txt)
python3 - $SY/requests.jsonl "$EFF" > $EV/request-structure.txt <<'PY'
import json, sys
e = dict(kv.split("=") for kv in sys.argv[2].split()[1:])          # stored EFFECTIVE sent-text hashes u1 a1 u2 a2
rows = [json.loads(l) for l in open(sys.argv[1]) if '"/openai/v1/chat/completions"' in l]
conv = lambda r: [(m["role"], m["sha"]) for m in r.get("msgs", []) if m["role"] in ("user", "assistant")]
r1, r2 = conv(rows[0]), conv(rows[1])
print("request #1 conversational:", r1); print("request #2 conversational:", r2)
print("request #2 system messages:", sum(1 for m in rows[1].get("msgs", []) if m["role"] == "system"))
ok1 = r1 == [("user", e["u1"])]
ok2 = r2 == [("user", e["u1"]), ("assistant", e["a1"]), ("user", e["u2"])]
print("C9 request #1 = [user(turn 1 as sent)]:", ok1)
print("C9 request #2 = [user(turn 1 as sent), assistant(turn-1 reply), user(turn 2)] exactly, in order:", ok2)
sys.exit(0 if ok1 and ok2 else 1)
PY
[[ $? -eq 0 ]] && rec C9-request PASS "turn-2 request = user(t1) -> assistant(t1 reply) -> user(t2), byte-exact vs stored sent text ($EFF)" || rec C9-request FAIL "$(cat $EV/request-structure.txt | tr '
' ' ' | cut -c1-300)"
grep -q 'rewritten for the provider (api_content present): True' $EV/continuity.txt && rec onboarding-note OBSERVED "Hermes appends a first-message onboarding system note to turn 1 (profile offer)" || rec onboarding-note INFO "no first-message rewrite"
since=$(date '+%Y-%m-%d %H:%M:%S'); systemctl start hermes-gateway-dev
wait_ready "$since" && rec G-6r2 PASS "ready after continuity check" || { rec G-6r2 FAIL ""; exit 1; }
echo "#### G-8 + G-9"
systemctl start hermes-gateway-dev-retention.service; [[ $(systemctl show hermes-gateway-dev-retention.service -p Result --value) == success ]] && rec G-8 PASS retention || rec G-8 FAIL ""
bash $P/bin/observe_host.sh $EV/g9 >/dev/null
bash $P/bin/compare_observations.sh $PRE/observation $EV/g9 > $EV/g9-cmp.txt && rec G-9-obs PASS "$(tail -1 $EV/g9-cmp.txt)" || rec G-9-obs FAIL "$(grep DIFF $EV/g9-cmp.txt | tr '\n' ' ')"
bash $P/bin/dr5_check.sh $EV/dr5-g9.txt > $EV/dr5-g9-check.txt && rec G-9-DR5 PASS "$(tail -1 $EV/dr5-g9-check.txt | cut -c1-40)" || rec G-9-DR5 FAIL ""

echo "#### G-10 slot = request #5 via the Core API relay (the UI's server-side path), then budget state"
f0=$(fakecount)
c=$(curl -s -m 150 -o $EV/t5.json -w '%{http_code}' -H 'Content-Type: application/json' -d '{"message":"F8-SYNTHETIC G-10 UI check: one short sentence.","session":"f8b-ui"}' http://127.0.0.1:8765/os/conversation)
r5=$(python3 -c 'import json;d=json.load(open("'$EV'/t5.json"));print(d.get("state"),"|",(d.get("reply") or "")[:80])')
[[ $c == 200 && $r5 == completed* && $r5 == *$MARK* ]] && rec G-10-slot PASS "$c $r5" || rec G-10-slot FAIL "$c $r5"
tail -1 $HH/logs/lilith-router-decisions.log | python3 -c 'import json,sys; d=json.loads(sys.stdin.readline()); sys.exit(0 if d.get("chat_id")=="f8b-ui" and d.get("live") is False and d.get("platform")=="lilith_os" else 1)'   && rec G-10-router PASS "shadow decision for f8b-ui, live false; total $(wc -l < $HH/logs/lilith-router-decisions.log)" || rec G-10-router FAIL ""
bud=$(bash $R/bin/gate_budget.sh show)
echo "$bud" | grep -qE '"budget_used": 5[,}]' && echo "$bud" | grep -q BUDGET_EXHAUSTED && rec budget-final PASS "$bud" || rec budget-final FAIL "$bud"
rec provider-total INFO "chat requests at the synthetic provider this rehearsal: $(fakecount) (expected 5); ledger R=$(grep -c '^R ' $L); RESET lines=$(grep -c '^RESET' $L)"

echo "#### cleanup to the mirror baseline"
bash $R/bin/rollback.sh stop >/dev/null 2>&1; bash /var/tmp/f8/$PKGN/bin/rollback.sh remove > $EV/r2.log 2>&1
systemctl daemon-reload; bash $P/bin/observe_host.sh $EV/final >/dev/null
bash $P/bin/compare_observations.sh $EV/M0 $EV/final > $EV/final-cmp.txt && [[ $(ls -A $HH) == memories ]] && rec FINAL CLEAN "M0 == FINAL, HH=memories" || rec FINAL NOT_CLEAN "$(grep DIFF $EV/final-cmp.txt | tr '\n' ' ') HH=$(ls -A $HH | tr '\n' ' ')"
bash $W/mirror/synthprov.sh down >/dev/null
[[ $MIRROR_SET_UP == 1 ]] && { bash /root/f8r2/mirror/mirror_teardown.sh > $EV/mirror-teardown.log 2>&1; rec mirror-teardown INFO "$(tail -1 $EV/mirror-teardown.log)"; }
echo; echo "TOTAL: $(grep -cP '\t(PASS|CLEAN|PRESENT|REPRODUCED|INFO|OBSERVED)\t' $RES) ok / $(wc -l < $RES) rows; NOT ok: $(grep -cvP '\t(PASS|CLEAN|PRESENT|REPRODUCED|INFO|OBSERVED)\t' $RES)"
